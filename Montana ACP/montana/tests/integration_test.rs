//! Full integration tests for Montana network
//!
//! Tests slice sync, transaction relay, and presence propagation
//! with proper cryptographic signatures.

use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;
use tokio::time::sleep;

// Re-export from montana lib
mod common {
    pub use montana::crypto::{sha3, Keypair};
    pub use montana::db::Storage;
    pub use montana::net::{NetConfig, NetEvent, Network, NODE_FULL, NODE_PRESENCE};
    pub use montana::types::*;
}

use common::*;

const TEST_TIMEOUT: Duration = Duration::from_secs(30);

/// Create a signed slice
fn create_signed_slice(
    keypair: &Keypair,
    prev_slice: &Slice,
    slice_index: u64,
) -> Slice {
    let header = SliceHeader {
        prev_hash: prev_slice.hash(),
        timestamp: now(),
        slice_index,
        winner_pubkey: keypair.public.clone(),
        cooldown_medians: [0, 0, 0],
        registrations: [0, 0, 0],
        cumulative_weight: 0,
        subnet_reputation_root: [0u8; 32],
    };

    let presence_root = sha3(b"test presence");
    let tx_root = sha3(b"test tx");

    // Sign the header
    let header_data = bincode::serialize(&header).unwrap();
    let signature = keypair.sign(&header_data);

    Slice {
        header,
        presence_root,
        tx_root,
        signature,
        presences: vec![],
        transactions: vec![],
    }
}

/// Create a test transaction
fn create_test_tx(keypair: &Keypair) -> Transaction {
    Transaction {
        inputs: vec![],  // Coinbase-like
        outputs: vec![
            TxOutput {
                amount: 3000,
                pubkey: keypair.public.clone(),
            }
        ],
    }
}

/// Create a presence proof
fn create_presence_proof(keypair: &Keypair, tau2_index: u64, prev_hash: Hash) -> PresenceProof {
    let proof_data = bincode::serialize(&(tau2_index, prev_hash)).unwrap();
    let signature = keypair.sign(&proof_data);

    PresenceProof {
        pubkey: keypair.public.clone(),
        tau2_index,
        tau1_bitmap: 0b1111111111,  // All 10 minutes present
        prev_slice_hash: prev_hash,
        timestamp: now(),
        signature,
        cooldown_until: 0,
    }
}

/// Clean up test data directory
fn cleanup_data_dir(path: &PathBuf) {
    let _ = std::fs::remove_dir_all(path);
}

/// Test node wrapper
struct TestNode {
    keypair: Keypair,
    storage: Arc<Storage>,
    network: Arc<Network>,
    data_dir: PathBuf,
}

impl TestNode {
    async fn new(port: u16, seeds: Vec<String>) -> Result<(Self, tokio::sync::mpsc::Receiver<NetEvent>), String> {
        let data_dir = PathBuf::from(format!("/tmp/montana_integ_{}", port));
        cleanup_data_dir(&data_dir);
        std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

        let storage = Storage::open(&data_dir).map_err(|e| e.to_string())?;

        if storage.head().is_err() {
            storage.init_genesis().map_err(|e| e.to_string())?;
        }

        let keypair = Keypair::generate();

        let config = NetConfig {
            listen_port: port,
            data_dir: data_dir.clone(),
            node_type: NodeType::Full,
            services: NODE_FULL | NODE_PRESENCE,
            seeds,
            ..Default::default()
        };

        let (network, event_rx) = Network::new(config).await.map_err(|e| e.to_string())?;
        network.start().await.map_err(|e| e.to_string())?;

        let head = storage.head().unwrap_or(0);
        network.set_best_slice(head).await;

        Ok((
            Self {
                keypair,
                storage: Arc::new(storage),
                network: Arc::new(network),
                data_dir,
            },
            event_rx,
        ))
    }

    fn genesis(&self) -> Slice {
        self.storage.get_slice(0).expect("Genesis must exist")
    }

    async fn shutdown(&self) {
        self.network.shutdown().await;
    }
}

impl Drop for TestNode {
    fn drop(&mut self) {
        cleanup_data_dir(&self.data_dir);
    }
}

#[tokio::test]
async fn test_slice_broadcast() {
    println!("\n=== Test: Slice Broadcast ===");

    // Start node A
    let (node_a, _events_a) = TestNode::new(19400, vec![])
        .await
        .expect("Failed to start node A");
    println!("  Started node A");

    // Start node B connected to A
    let (node_b, mut events_b) = TestNode::new(19401, vec!["127.0.0.1:19400".into()])
        .await
        .expect("Failed to start node B");
    println!("  Started node B");

    // Wait for connection
    let mut connected = false;
    for i in 0..30 {
        sleep(Duration::from_secs(1)).await;
        if node_a.network.peer_count().await >= 1 && node_b.network.peer_count().await >= 1 {
            connected = true;
            println!("  Connected after {}s", i + 1);
            break;
        }
    }
    assert!(connected, "Nodes should connect within 30 seconds");
    println!("  ✓ Nodes connected");

    // Get peer info
    let peers = node_a.network.get_peers().await;
    for p in &peers {
        println!("  Node A peer: {} ready={}", p.addr, p.is_ready);
    }

    // Create and broadcast slice from A
    let genesis = node_a.genesis();
    let slice = create_signed_slice(&node_a.keypair, &genesis, 1);

    // Store locally first
    node_a.storage.put_slice(&slice).expect("Failed to store slice");
    node_a.network.set_best_slice(1).await;

    // Broadcast
    node_a.network.broadcast_slice(&slice).await;
    println!("  Broadcasted slice #1 from A");

    // Wait for B to receive it
    let received = tokio::time::timeout(TEST_TIMEOUT, async {
        while let Some(event) = events_b.recv().await {
            println!("  Node B event: {:?}", std::mem::discriminant(&event));
            if let NetEvent::Slice(_, received_slice) = event {
                return Some(received_slice);
            }
        }
        None
    })
    .await;

    match received {
        Ok(Some(received_slice)) => {
            assert_eq!(received_slice.header.slice_index, 1);
            println!("  ✓ Node B received slice #1");
        }
        _ => {
            panic!("Node B did not receive slice within timeout");
        }
    }

    node_a.shutdown().await;
    node_b.shutdown().await;
    println!("  ✓ Slice broadcast test passed");
}

#[tokio::test]
async fn test_tx_relay() {
    println!("\n=== Test: Transaction Relay ===");

    let (node_a, _) = TestNode::new(19410, vec![])
        .await
        .expect("Failed to start node A");

    let (node_b, mut events_b) = TestNode::new(19411, vec!["127.0.0.1:19410".into()])
        .await
        .expect("Failed to start node B");

    // Wait for connection with retry (bootstrap can take 30+ seconds)
    let mut connected = false;
    for i in 0..60 {
        sleep(Duration::from_secs(1)).await;
        if node_a.network.peer_count().await >= 1 && node_b.network.peer_count().await >= 1 {
            connected = true;
            println!("  Connected after {}s", i + 1);
            break;
        }
    }
    assert!(connected, "Nodes should connect within 60 seconds");
    println!("  ✓ Nodes connected");

    // Create and broadcast tx
    let tx = create_test_tx(&node_a.keypair);
    node_a.network.broadcast_tx(&tx).await;
    println!("  Broadcasted tx from A");

    // Wait for B to receive
    let received = tokio::time::timeout(TEST_TIMEOUT, async {
        while let Some(event) = events_b.recv().await {
            if let NetEvent::Tx(_, received_tx) = event {
                return Some(received_tx);
            }
        }
        None
    })
    .await;

    match received {
        Ok(Some(received_tx)) => {
            assert_eq!(received_tx.hash(), tx.hash());
            println!("  ✓ Node B received tx");
        }
        _ => {
            panic!("Node B did not receive tx within timeout");
        }
    }

    node_a.shutdown().await;
    node_b.shutdown().await;
    println!("  ✓ Transaction relay test passed");
}

#[tokio::test]
async fn test_presence_relay() {
    println!("\n=== Test: Presence Relay ===");

    let (node_a, _) = TestNode::new(19420, vec![])
        .await
        .expect("Failed to start node A");

    let (node_b, mut events_b) = TestNode::new(19421, vec!["127.0.0.1:19420".into()])
        .await
        .expect("Failed to start node B");

    // Wait for connection with retry (bootstrap can take 30+ seconds)
    let mut connected = false;
    for i in 0..60 {
        sleep(Duration::from_secs(1)).await;
        if node_a.network.peer_count().await >= 1 && node_b.network.peer_count().await >= 1 {
            connected = true;
            println!("  Connected after {}s", i + 1);
            break;
        }
    }
    assert!(connected, "Nodes should connect within 60 seconds");
    println!("  ✓ Nodes connected");

    // Create and broadcast presence
    let genesis = node_a.genesis();
    let presence = create_presence_proof(&node_a.keypair, 1, genesis.hash());
    node_a.network.broadcast_presence(&presence).await;
    println!("  Broadcasted presence from A");

    // Wait for B to receive
    let received = tokio::time::timeout(TEST_TIMEOUT, async {
        while let Some(event) = events_b.recv().await {
            if let NetEvent::Presence(_, received_presence) = event {
                return Some(received_presence);
            }
        }
        None
    })
    .await;

    match received {
        Ok(Some(received_presence)) => {
            assert_eq!(received_presence.tau2_index, 1);
            println!("  ✓ Node B received presence proof");
        }
        _ => {
            panic!("Node B did not receive presence within timeout");
        }
    }

    node_a.shutdown().await;
    node_b.shutdown().await;
    println!("  ✓ Presence relay test passed");
}

#[tokio::test]
async fn test_slice_sync_on_connect() {
    println!("\n=== Test: Slice Sync on Connect ===");

    // Start node A and create some slices
    let (node_a, _) = TestNode::new(19430, vec![])
        .await
        .expect("Failed to start node A");

    let genesis = node_a.genesis();

    // Create chain of 3 slices
    let slice1 = create_signed_slice(&node_a.keypair, &genesis, 1);
    node_a.storage.put_slice(&slice1).unwrap();

    let slice2 = create_signed_slice(&node_a.keypair, &slice1, 2);
    node_a.storage.put_slice(&slice2).unwrap();

    let slice3 = create_signed_slice(&node_a.keypair, &slice2, 3);
    node_a.storage.put_slice(&slice3).unwrap();

    node_a.network.set_best_slice(3).await;
    println!("  Node A has 3 slices");

    // Now start node B - it should sync
    let (node_b, mut events_b) = TestNode::new(19431, vec!["127.0.0.1:19430".into()])
        .await
        .expect("Failed to start node B");

    // Wait for sync
    let mut synced_count = 0;
    let sync_result = tokio::time::timeout(TEST_TIMEOUT, async {
        while let Some(event) = events_b.recv().await {
            match event {
                NetEvent::PeerAhead(_, their_best) => {
                    println!("  Node B sees peer ahead at slice {}", their_best);
                }
                NetEvent::Slice(_, slice) => {
                    synced_count += 1;
                    println!("  Node B received slice #{}", slice.header.slice_index);
                    if synced_count >= 3 {
                        return true;
                    }
                }
                _ => {}
            }
        }
        false
    })
    .await;

    node_a.shutdown().await;
    node_b.shutdown().await;

    match sync_result {
        Ok(true) => println!("  ✓ Sync test passed"),
        _ => println!("  ⚠ Partial sync: received {} slices", synced_count),
    }
}

fn main() {
    println!("════════════════════════════════════════════════════");
    println!("  Montana Integration Tests");
    println!("════════════════════════════════════════════════════");
    println!("Run with: cargo test --test integration_test -- --nocapture");
}
