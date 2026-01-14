//! Montana Consensus Engine (Event-Driven)
//!
//! Architecture: Event-driven, не polling.
//! Network.rs эмитит события → Engine обрабатывает.

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::consensus::{
    FullNodePresence, Lottery, LotteryParticipant, LotteryResult,
    NodeTier, Slice, SliceHeader, TAU1_SECS, TAU2_SECS,
};
use crate::cooldown::AdaptiveCooldown;
use crate::crypto::Keypair;
use crate::finality::FinalityTracker;
use crate::fork_choice::{ChainHead, ForkChoice, ReorgResult};
use crate::merkle::MerkleTree;
use crate::net::{NetEvent, Network};
use crate::types::{Hash, NodeType, PresenceProof, PublicKey, Transaction, Slice as NetSlice};

// ============================================================================
// CONSTANTS
// ============================================================================

/// Max presences per τ₂ (memory bound)
const MAX_PRESENCES_PER_TAU2: usize = 100_000;

/// Slice wait timeout (seconds)
const SLICE_WAIT_TIMEOUT_SECS: u64 = 60;

/// Backup slots per τ₂
const BACKUP_SLOTS: u32 = 10;

// ============================================================================
// CONFIG
// ============================================================================

#[derive(Debug, Clone)]
pub struct Config {
    pub node_type: NodeType,
    pub genesis_hash: Hash,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            node_type: NodeType::Full,
            genesis_hash: [0u8; 32],
        }
    }
}

// ============================================================================
// CONSENSUS ENGINE (Event-Driven)
// ============================================================================

pub struct ConsensusEngine {
    config: Config,
    keypair: Keypair,
    fork_choice: RwLock<ForkChoice>,
    finality: RwLock<FinalityTracker>,
    cooldown: RwLock<AdaptiveCooldown>,

    // State
    current_tau2: RwLock<u64>,
    presence_pool: RwLock<PresencePool>,
    pending_slices: RwLock<Vec<Slice>>,
}

/// Bounded presence pool
struct PresencePool {
    presences: HashMap<[u8; 32], FullNodePresence>,
    tau2_index: u64,
}

impl PresencePool {
    fn new() -> Self {
        Self {
            presences: HashMap::new(),
            tau2_index: 0,
        }
    }

    fn add(&mut self, presence: FullNodePresence) -> bool {
        if self.presences.len() >= MAX_PRESENCES_PER_TAU2 {
            return false;
        }
        if presence.tau2_index != self.tau2_index {
            return false;
        }
        self.presences.insert(presence.pubkey, presence);
        true
    }

    fn clear_for_tau2(&mut self, tau2_index: u64) {
        self.presences.clear();
        self.tau2_index = tau2_index;
    }

    fn get_all(&self) -> Vec<FullNodePresence> {
        self.presences.values().cloned().collect()
    }

    fn len(&self) -> usize {
        self.presences.len()
    }
}

impl ConsensusEngine {
    pub fn new(config: Config) -> Self {
        let fork_choice = ForkChoice::new(config.genesis_hash);
        let finality = FinalityTracker::new();
        let cooldown = AdaptiveCooldown::new();

        Self {
            config,
            keypair: Keypair::generate(),
            fork_choice: RwLock::new(fork_choice),
            finality: RwLock::new(finality),
            cooldown: RwLock::new(cooldown),
            current_tau2: RwLock::new(0),
            presence_pool: RwLock::new(PresencePool::new()),
            pending_slices: RwLock::new(Vec::new()),
        }
    }

    /// Load keypair from storage (production)
    pub fn with_keypair(mut self, keypair: Keypair) -> Self {
        self.keypair = keypair;
        self
    }

    /// Main event handler
    pub async fn handle_event(
        &self,
        event: NetEvent,
        network: &Network,
    ) -> Result<Option<EngineAction>, EngineError> {
        match event {
            // τ₁ tick: sign presence
            NetEvent::Tau1Tick { tau1_index, network_time } => {
                self.on_tau1_tick(tau1_index, network_time, network).await
            }

            // τ₂ ended: run lottery
            NetEvent::Tau2Ended { tau2_index, network_time } => {
                self.on_tau2_ended(tau2_index, network_time, network).await
            }

            // Received presence from peer
            NetEvent::Presence(addr, presence) => {
                self.on_presence_received(*presence).await
            }

            // Received slice from peer
            NetEvent::Slice(addr, slice) => {
                let internal_slice = self.convert_net_slice(*slice)?;
                self.on_slice_received(internal_slice, network).await
            }

            // Finality update
            NetEvent::FinalityUpdate { tau3_index, checkpoint_hash } => {
                self.on_finality_update(tau3_index, checkpoint_hash).await
            }

            // P2P events (not consensus-critical)
            NetEvent::PeerConnected(_) |
            NetEvent::PeerDisconnected(_) |
            NetEvent::Tx(_, _) |
            NetEvent::NeedSlices(_, _, _) |
            NetEvent::PeerAhead(_, _) => {
                Ok(None)
            }
        }
    }

    // ========================================================================
    // EVENT HANDLERS
    // ========================================================================

    async fn on_tau1_tick(
        &self,
        tau1_index: u64,
        network_time: u64,
        network: &Network,
    ) -> Result<Option<EngineAction>, EngineError> {
        if !matches!(self.config.node_type, NodeType::Full) {
            return Ok(None);
        }

        let current_tau2 = *self.current_tau2.read().await;
        let presence = self.create_presence(current_tau2, network_time)?;

        // Add to own pool
        self.presence_pool.write().await.add(presence.clone());

        // Broadcast to network
        // network.broadcast_presence(&presence).await;

        Ok(Some(EngineAction::PresenceSigned { tau2_index: current_tau2 }))
    }

    async fn on_tau2_ended(
        &self,
        tau2_index: u64,
        network_time: u64,
        network: &Network,
    ) -> Result<Option<EngineAction>, EngineError> {
        let presences = self.presence_pool.read().await.get_all();
        if presences.is_empty() {
            return Err(EngineError::NoPresences);
        }

        // Run lottery
        let prev_hash = self.get_prev_slice_hash().await;
        let mut lottery = Lottery::new(prev_hash, tau2_index);

        for presence in &presences {
            let participant = self.presence_to_participant(presence);
            lottery.add_participant(participant);
        }

        let result = lottery.run();
        let winner_pubkey = result.winners[0].pubkey;

        // Check if we won
        let our_pubkey = self.get_our_pubkey();
        if winner_pubkey == our_pubkey {
            let slice = self.produce_slice(presences, result, tau2_index).await?;
            // network.broadcast_slice(&slice).await;

            // Prepare for next τ₂
            self.presence_pool.write().await.clear_for_tau2(tau2_index + 1);
            *self.current_tau2.write().await = tau2_index + 1;

            return Ok(Some(EngineAction::LotteryWon {
                tau2_index,
                slice_hash: slice.header.hash(),
            }));
        }

        // Prepare for next τ₂
        self.presence_pool.write().await.clear_for_tau2(tau2_index + 1);
        *self.current_tau2.write().await = tau2_index + 1;

        Ok(Some(EngineAction::WaitingForSlice {
            tau2_index,
            winner: winner_pubkey,
        }))
    }

    async fn on_presence_received(
        &self,
        presence: PresenceProof,
    ) -> Result<Option<EngineAction>, EngineError> {
        // Convert Vec<u8> pubkey to [u8; 32]
        let mut pubkey_array = [0u8; 32];
        let len = presence.pubkey.len().min(32);
        pubkey_array[..len].copy_from_slice(&presence.pubkey[..len]);

        // Convert PresenceProof to FullNodePresence
        let full_presence = FullNodePresence {
            pubkey: pubkey_array,
            tau2_index: presence.tau2_index,
            timestamp: presence.timestamp,
            prev_slice_hash: presence.prev_slice_hash,
            tier: 0, // FullNode
            signature: presence.signature,
        };

        let added = self.presence_pool.write().await.add(full_presence);
        if added {
            Ok(Some(EngineAction::PresenceAccepted {
                pubkey: pubkey_array,
            }))
        } else {
            Ok(None)
        }
    }

    async fn on_slice_received(
        &self,
        slice: Slice,
        network: &Network,
    ) -> Result<Option<EngineAction>, EngineError> {
        // Verify slice
        self.verify_slice(&slice).await?;

        // Add to fork choice
        let head = ChainHead::from_slice_header(
            slice.header.hash(),
            slice.header.height,
            slice.header.tau2_index,
            self.calculate_slice_weight(&slice),
        );

        let mut fc = self.fork_choice.write().await;
        fc.add_head(head.clone())?;

        // Check for reorg
        if fc.should_reorg(&head) {
            let result = fc.reorg_to(head.clone())?;
            drop(fc);
            self.handle_reorg(result).await?;

            return Ok(Some(EngineAction::Reorg {
                new_head: head.hash,
                depth: 1,
            }));
        }

        Ok(Some(EngineAction::SliceAccepted {
            hash: slice.header.hash(),
            height: slice.header.height,
        }))
    }

    async fn on_finality_update(
        &self,
        tau3_index: u64,
        checkpoint_hash: [u8; 32],
    ) -> Result<Option<EngineAction>, EngineError> {
        // Phase 2F: Full finality integration
        // For now, just acknowledge the event
        Ok(Some(EngineAction::CheckpointFinalized { tau3_index }))
    }

    // ========================================================================
    // HELPERS
    // ========================================================================

    fn create_presence(
        &self,
        tau2_index: u64,
        timestamp: u64,
    ) -> Result<FullNodePresence, EngineError> {
        let pubkey = self.get_our_pubkey();
        let prev_hash = [0u8; 32]; // TODO: get from fork_choice

        let presence = FullNodePresence {
            pubkey,
            tau2_index,
            timestamp,
            prev_slice_hash: prev_hash,
            tier: 0,
            signature: vec![], // TODO: sign with keypair
        };

        Ok(presence)
    }

    fn get_our_pubkey(&self) -> [u8; 32] {
        let pubkey_vec = self.keypair.public_key();
        let mut pubkey_array = [0u8; 32];
        pubkey_array.copy_from_slice(&pubkey_vec[..32.min(pubkey_vec.len())]);
        pubkey_array
    }

    async fn get_prev_slice_hash(&self) -> Hash {
        self.fork_choice.read().await.canonical_head().hash
    }

    fn presence_to_participant(&self, presence: &FullNodePresence) -> LotteryParticipant {
        let tier = match presence.tier {
            0 => NodeTier::FullNode,
            _ => NodeTier::VerifiedUser,
        };

        let weight = match tier {
            NodeTier::FullNode => 1000,
            NodeTier::VerifiedUser => 20000,
        };

        LotteryParticipant {
            pubkey: presence.pubkey,
            tier,
            weight,
            presence_hash: crate::crypto::sha3(&presence.pubkey),
        }
    }

    fn convert_net_slice(&self, net_slice: NetSlice) -> Result<Slice, EngineError> {
        // Convert types::Slice (network format) to consensus::Slice (internal format)

        // Convert presences
        let full_node_presences: Vec<FullNodePresence> = net_slice.presences
            .into_iter()
            .map(|p| {
                let mut pubkey_array = [0u8; 32];
                let len = p.pubkey.len().min(32);
                pubkey_array[..len].copy_from_slice(&p.pubkey[..len]);

                FullNodePresence {
                    pubkey: pubkey_array,
                    tau2_index: p.tau2_index,
                    timestamp: p.timestamp,
                    prev_slice_hash: p.prev_slice_hash,
                    tier: 0,
                    signature: p.signature,
                }
            })
            .collect();

        // Convert header
        let mut winner_pubkey = [0u8; 32];
        let pk_len = net_slice.header.winner_pubkey.len().min(32);
        winner_pubkey[..pk_len].copy_from_slice(&net_slice.header.winner_pubkey[..pk_len]);
        let tau2_index = net_slice.header.slice_index / 10; // slice_index / SLOTS_PER_TAU2

        let internal_header = SliceHeader {
            version: 1,
            height: net_slice.header.slice_index,
            tau2_index,
            timestamp: net_slice.header.timestamp,
            prev_slice_hash: net_slice.header.prev_hash,
            presence_root: net_slice.presence_root,
            tx_root: net_slice.tx_root,
            producer_pubkey: winner_pubkey,
            lottery_ticket: [0u8; 32], // Network doesn't send ticket, will be verified
            slot: 0,
            finality_checkpoint: None,
        };

        // Convert transactions
        let transactions: Vec<Vec<u8>> = net_slice.transactions
            .into_iter()
            .map(|tx| bincode::serialize(&tx).unwrap_or_default())
            .collect();

        Ok(Slice {
            header: internal_header,
            full_node_presences,
            verified_user_presences: vec![],
            transactions,
            producer_signature: net_slice.signature.to_vec(),
            attestations: vec![],
        })
    }

    async fn produce_slice(
        &self,
        presences: Vec<FullNodePresence>,
        lottery_result: LotteryResult,
        tau2_index: u64,
    ) -> Result<Slice, EngineError> {
        let prev_hash = self.get_prev_slice_hash().await;

        // Merkle tree for presences
        let presence_hashes: Vec<Hash> = presences.iter()
            .map(|p| crate::crypto::sha3(&p.pubkey))
            .collect();
        let presence_tree = MerkleTree::new(presence_hashes);
        let presence_root = presence_tree.root();

        let header = SliceHeader {
            version: 1,
            height: tau2_index,
            tau2_index,
            timestamp: crate::types::now(),
            prev_slice_hash: prev_hash,
            presence_root,
            tx_root: [0u8; 32],
            producer_pubkey: self.get_our_pubkey(),
            lottery_ticket: lottery_result.winners[0].ticket,
            slot: 0,
            finality_checkpoint: None,
        };

        Ok(Slice {
            header,
            full_node_presences: presences,
            verified_user_presences: vec![],
            transactions: vec![],
            producer_signature: vec![], // TODO: sign
            attestations: vec![],
        })
    }

    async fn verify_slice(&self, slice: &Slice) -> Result<(), EngineError> {
        // Verify lottery winner
        let prev_hash = slice.header.prev_slice_hash;
        let mut lottery = Lottery::new(prev_hash, slice.header.tau2_index);

        for presence in &slice.full_node_presences {
            let participant = self.presence_to_participant(presence);
            lottery.add_participant(participant);
        }

        let result = lottery.run();
        if result.winners[0].pubkey != slice.header.producer_pubkey {
            return Err(EngineError::InvalidLotteryWinner);
        }

        // Verify presence root
        let presence_hashes: Vec<Hash> = slice.full_node_presences.iter()
            .map(|p| crate::crypto::sha3(&p.pubkey))
            .collect();
        let presence_tree = MerkleTree::new(presence_hashes);
        if presence_tree.root() != slice.header.presence_root {
            return Err(EngineError::InvalidPresenceRoot);
        }

        Ok(())
    }

    fn calculate_slice_weight(&self, slice: &Slice) -> u64 {
        slice.full_node_presences.len() as u64 * 1000
    }

    async fn handle_reorg(&self, result: ReorgResult) -> Result<(), EngineError> {
        // TODO: Update mempool, return orphaned txs
        Ok(())
    }
}

// ============================================================================
// ACTIONS (output from engine)
// ============================================================================

#[derive(Debug)]
pub enum EngineAction {
    PresenceSigned { tau2_index: u64 },
    PresenceAccepted { pubkey: [u8; 32] },
    LotteryWon { tau2_index: u64, slice_hash: Hash },
    WaitingForSlice { tau2_index: u64, winner: [u8; 32] },
    SliceAccepted { hash: Hash, height: u64 },
    Reorg { new_head: Hash, depth: u32 },
    CheckpointFinalized { tau3_index: u64 },
}

// ============================================================================
// ERRORS
// ============================================================================

#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("no presences collected")]
    NoPresences,
    #[error("invalid lottery winner")]
    InvalidLotteryWinner,
    #[error("invalid presence root")]
    InvalidPresenceRoot,
    #[error("fork choice error: {0}")]
    ForkChoice(#[from] crate::fork_choice::ForkChoiceError),
    #[error("finality error: {0}")]
    Finality(#[from] crate::finality::FinalityError),
    #[error("slice timeout")]
    SliceTimeout,
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_presence_pool_bounds() {
        let mut pool = PresencePool::new();
        pool.tau2_index = 1;

        for i in 0..MAX_PRESENCES_PER_TAU2 {
            let presence = FullNodePresence {
                pubkey: {
                    let mut pk = [0u8; 32];
                    pk[0] = (i % 256) as u8;
                    pk[1] = ((i / 256) % 256) as u8;
                    pk[2] = ((i / 65536) % 256) as u8;
                    pk
                },
                tau2_index: 1,
                timestamp: 0,
                prev_slice_hash: [0u8; 32],
                tier: 0,
                signature: vec![],
            };
            assert!(pool.add(presence));
        }

        // Pool is full
        let overflow = FullNodePresence {
            pubkey: [0xff; 32],
            tau2_index: 1,
            timestamp: 0,
            prev_slice_hash: [0u8; 32],
            tier: 0,
            signature: vec![],
        };
        assert!(!pool.add(overflow));
        assert_eq!(pool.len(), MAX_PRESENCES_PER_TAU2);
    }

    #[test]
    fn test_presence_pool_tau2_filter() {
        let mut pool = PresencePool::new();
        pool.tau2_index = 5;

        // Wrong tau2_index rejected
        let wrong_tau2 = FullNodePresence {
            pubkey: [1u8; 32],
            tau2_index: 4,
            timestamp: 0,
            prev_slice_hash: [0u8; 32],
            tier: 0,
            signature: vec![],
        };
        assert!(!pool.add(wrong_tau2));

        // Correct tau2_index accepted
        let correct_tau2 = FullNodePresence {
            pubkey: [2u8; 32],
            tau2_index: 5,
            timestamp: 0,
            prev_slice_hash: [0u8; 32],
            tier: 0,
            signature: vec![],
        };
        assert!(pool.add(correct_tau2));
    }

    #[tokio::test]
    async fn test_engine_creation() {
        let config = Config::default();
        let engine = ConsensusEngine::new(config);
        assert_eq!(*engine.current_tau2.read().await, 0);
    }
}
