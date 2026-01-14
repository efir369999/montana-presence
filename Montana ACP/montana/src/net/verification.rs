//! Verification client — ephemeral queries before network start
//!
//! Uses Noise XX + ML-KEM-768 encryption for all connections.
//! This ensures compatibility with the main P2P protocol (protocol.rs).

use super::bootstrap::{
    BootstrapError, BootstrapVerifier, PeerChainInfo, PeerSource,
    P2P_PEER_COUNT, min_hardcoded_responses, min_consensus_peers,
};
use super::encrypted::{EncryptedStream, EncryptedReader, EncryptedWriter};
use super::hardcoded_identity::{
    get_hardcoded_addrs, get_hardcoded_pubkey, is_hardcoded_addr, verify_hardcoded_response,
    Challenge,
};
use super::noise::StaticKeypair;
use crate::crypto::mldsa::verify_mldsa65;
use super::message::Message;
use super::subnet::MIN_DIVERSE_SUBNETS;
use super::types::{
    NetAddress, VersionPayload, PROTOCOL_MAGIC, PROTOCOL_VERSION,
    NODE_FULL, CHECKSUM_SIZE, MAX_TX_SIZE,
};
use crate::crypto::sha3;
use crate::types::{ip_to_subnet16, now, NodeType, Slice, Subnet16};
use std::collections::{HashMap, HashSet};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;
use thiserror::Error;
use tokio::net::TcpStream;
use tokio::sync::{Mutex, Semaphore};
use tokio::time::timeout;
use tracing::{debug, error, info, warn};

// =============================================================================
// CONSTANTS
// =============================================================================

/// Timeout for TCP connection establishment.
const CONNECT_TIMEOUT_SECS: u64 = 10;

/// Timeout for handshake completion (Version + Verack).
const HANDSHAKE_TIMEOUT_SECS: u64 = 15;

/// Timeout for chain info request after handshake.
const QUERY_TIMEOUT_SECS: u64 = 10;

/// Maximum concurrent verification connections.
/// Bounded to prevent resource exhaustion during verification.
const MAX_CONCURRENT_QUERIES: usize = 32;

/// Maximum addresses to accept per peer for P2P discovery.
/// Security: Limits memory usage during verification.
const MAX_ADDRS_PER_PEER: usize = 100;

// =============================================================================
// ERRORS
// =============================================================================

#[derive(Error, Debug)]
pub enum VerificationError {
    #[error("connection failed: {0}")]
    Connection(String),

    #[error("handshake failed: {0}")]
    Handshake(String),

    #[error("protocol error: {0}")]
    Protocol(String),

    #[error("timeout: {0}")]
    Timeout(String),

    #[error("insufficient hardcoded responses: need {need}, have {have}")]
    InsufficientHardcoded { need: usize, have: usize },

    #[error("insufficient peer responses: need {need}, have {have}")]
    InsufficientPeers { need: usize, have: usize },

    #[error("insufficient subnet diversity: need {need}, have {have}")]
    InsufficientSubnets { need: usize, have: usize },

    #[error("hardcoded node disagreement: {0}")]
    HardcodedDisagreement(String),

    #[error("clock divergence: local={local}, network={network}, diff={diff}s")]
    ClockDivergence { local: u64, network: u64, diff: u64 },

    #[error("bootstrap verification failed: {0}")]
    Bootstrap(#[from] BootstrapError),

    #[error("io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("authentication failed: {0} did not provide valid signature")]
    AuthenticationFailed(SocketAddr),

    #[error("unknown hardcoded node: {0}")]
    UnknownHardcoded(SocketAddr),
}

// =============================================================================
// VERIFICATION CLIENT
// =============================================================================

/// Minimal client for startup verification.
///
/// This client is intentionally separate from the main Network struct
/// to ensure verification runs BEFORE any network state is established.
///
/// Uses ephemeral Noise keypair for encrypted connections.
pub struct VerificationClient {
    /// Testnet mode (uses different hardcoded seeds)
    testnet: bool,
    /// Our listen port (for Version message)
    listen_port: u16,
    /// Semaphore for connection concurrency control
    semaphore: Arc<Semaphore>,
    /// Genesis slice for BootstrapVerifier
    genesis: Slice,
    /// Ephemeral Noise keypair for encrypted connections
    keypair: Arc<StaticKeypair>,
}

impl VerificationClient {
    /// Create new verification client with ephemeral Noise keypair.
    pub fn new(testnet: bool, listen_port: u16, genesis: Slice) -> Self {
        // Generate ephemeral keypair for verification connections
        // This keypair is only used during bootstrap and discarded after
        let keypair = StaticKeypair::generate(&mut rand::thread_rng());
        info!("Generated ephemeral Noise keypair for verification");

        Self {
            testnet,
            listen_port,
            semaphore: Arc::new(Semaphore::new(MAX_CONCURRENT_QUERIES)),
            genesis,
            keypair: Arc::new(keypair),
        }
    }

    /// Run full bootstrap verification.
    ///
    /// This is the main entry point. It:
    /// 1. Queries all hardcoded nodes
    /// 2. Discovers P2P peers via gossip
    /// 3. Queries P2P peers for chain info
    /// 4. Verifies consensus requirements
    ///
    /// Returns verified chain height and weight on success.
    pub async fn verify(&self) -> Result<VerificationResult, VerificationError> {
        info!("Starting bootstrap verification...");
        let start_time = std::time::Instant::now();
        let local_time = now();

        // Step 1: Get hardcoded addresses (from hardcoded_identity.rs)
        // Each address is bound to a cryptographic public key
        let hardcoded_addrs = get_hardcoded_addrs(self.testnet);

        // Calculate dynamic thresholds based on actual hardcoded count
        let hardcoded_count = hardcoded_addrs.len();
        let min_hardcoded = min_hardcoded_responses(hardcoded_count);
        let total_target = hardcoded_count + P2P_PEER_COUNT;
        let min_consensus = min_consensus_peers(total_target);

        info!(
            "Querying {} hardcoded nodes (need {}%, min {} responses)...",
            hardcoded_count,
            super::bootstrap::MIN_HARDCODED_RESPONSE_PERCENT,
            min_hardcoded
        );

        // Step 2: Query hardcoded nodes in parallel
        let (hardcoded_responses, discovered_addrs) =
            self.query_hardcoded_nodes(&hardcoded_addrs).await;

        info!(
            "Hardcoded responses: {}/{} (discovered {} P2P addresses)",
            hardcoded_responses.len(),
            hardcoded_count,
            discovered_addrs.len()
        );

        // Check minimum hardcoded responses (75% of total hardcoded)
        if hardcoded_responses.len() < min_hardcoded {
            error!(
                "CRITICAL: Insufficient hardcoded responses ({}/{}, need {})",
                hardcoded_responses.len(),
                hardcoded_count,
                min_hardcoded
            );
            error!("Possible causes:");
            error!("  1. Network connectivity issues");
            error!("  2. Hardcoded nodes are down");
            error!("  3. Firewall blocking port 19333");
            error!("Bootstrap ABORTED.");

            return Err(VerificationError::InsufficientHardcoded {
                need: min_hardcoded,
                have: hardcoded_responses.len(),
            });
        }

        // Step 3: Query 100 P2P peers discovered from hardcoded nodes
        let p2p_responses = self
            .query_p2p_peers(&discovered_addrs, &hardcoded_addrs)
            .await;

        info!(
            "P2P responses: {}/{} (target: {})",
            p2p_responses.len(),
            discovered_addrs.len(),
            P2P_PEER_COUNT
        );

        // Step 4: Combine all responses
        let mut all_responses: Vec<PeerChainInfo> = hardcoded_responses;
        all_responses.extend(p2p_responses);

        // Check total peer count (hardcoded + P2P)
        if all_responses.len() < min_consensus {
            // Allow bootstrap with fewer peers at genesis (network is small)
            // But require at least minimum hardcoded responses
            if all_responses.len() < min_hardcoded {
                return Err(VerificationError::InsufficientPeers {
                    need: min_consensus,
                    have: all_responses.len(),
                });
            }

            warn!(
                "Fewer peers than target ({}/{}) — continuing with available peers",
                all_responses.len(),
                total_target
            );
        }

        // Step 5: Check subnet diversity
        let subnets: HashSet<Subnet16> = all_responses
            .iter()
            .map(|r| ip_to_subnet16(r.peer.ip()))
            .collect();

        info!("Subnet diversity: {} unique /16 subnets", subnets.len());

        if subnets.len() < MIN_DIVERSE_SUBNETS {
            // Allow lower diversity at genesis (network is starting)
            // But require at least some diversity
            let min_genesis_subnets = MIN_DIVERSE_SUBNETS / 2; // 12-13 subnets at genesis
            if subnets.len() < min_genesis_subnets {
                return Err(VerificationError::InsufficientSubnets {
                    need: MIN_DIVERSE_SUBNETS,
                    have: subnets.len(),
                });
            }

            warn!(
                "Lower subnet diversity than target ({}/{}) — network may be young",
                subnets.len(),
                MIN_DIVERSE_SUBNETS
            );
        }

        // Step 6: Run full verification through BootstrapVerifier
        let verifier = BootstrapVerifier::new(&self.genesis, hardcoded_addrs);

        // Verify network time
        let (network_time, time_warning) =
            verifier.verify_network_time(&all_responses, local_time)?;

        if let Some(ref warning) = time_warning {
            warn!("Time warning: {}", warning);
        }

        // Get verified consensus (uses hardcoded nodes as trusted source)
        // verify_hardcoded_consensus is called internally
        let (median_height, median_weight, hardcoded_count, p2p_count) =
            verifier.get_verified_consensus(&all_responses)?;

        // Verify height against network time
        let height_warning = verifier.verify_height(median_height, network_time)?;

        if let Some(ref warning) = height_warning {
            warn!("{}", warning);
        }

        let elapsed = start_time.elapsed();
        info!(
            "Bootstrap verification PASSED in {:.2}s: height={}, weight={}, peers={} ({} hardcoded + {} P2P), subnets={}",
            elapsed.as_secs_f64(),
            median_height,
            median_weight,
            all_responses.len(),
            hardcoded_count,
            p2p_count,
            subnets.len()
        );

        Ok(VerificationResult {
            height: median_height,
            weight: median_weight,
            network_time,
            hardcoded_responses: hardcoded_count,
            p2p_responses: p2p_count,
            unique_subnets: subnets.len(),
            time_warning,
            height_warning,
        })
    }

    /// Query all hardcoded nodes in parallel.
    ///
    /// Returns (responses, discovered_addresses).
    async fn query_hardcoded_nodes(
        &self,
        addrs: &[SocketAddr],
    ) -> (Vec<PeerChainInfo>, Vec<SocketAddr>) {
        let responses = Arc::new(Mutex::new(Vec::new()));
        let discovered = Arc::new(Mutex::new(HashSet::new()));
        let testnet = self.testnet;

        let mut handles = Vec::new();

        for addr in addrs {
            let addr = *addr;
            let sem = self.semaphore.clone();
            let responses = responses.clone();
            let discovered = discovered.clone();
            let listen_port = self.listen_port;
            let keypair = self.keypair.clone();

            let handle = tokio::spawn(async move {
                // Acquire semaphore permit
                let _permit = sem.acquire().await.ok()?;

                match query_single_node(addr, listen_port, true, testnet, &keypair).await {
                    Ok((info, peer_addrs)) => {
                        debug!("Hardcoded {} responded: height={}", addr, info.slice_height);

                        responses.lock().await.push(info);

                        // Collect discovered addresses
                        for peer_addr in peer_addrs {
                            discovered.lock().await.insert(peer_addr);
                        }

                        Some(())
                    }
                    Err(e) => {
                        debug!("Hardcoded {} failed: {}", addr, e);
                        None
                    }
                }
            });

            handles.push(handle);
        }

        // Wait for all queries
        for handle in handles {
            let _ = handle.await;
        }

        let responses = Arc::try_unwrap(responses)
            .unwrap()
            .into_inner();
        let discovered: Vec<_> = Arc::try_unwrap(discovered)
            .unwrap()
            .into_inner()
            .into_iter()
            .collect();

        (responses, discovered)
    }

    /// Query P2P peers discovered via gossip.
    ///
    /// Filters out hardcoded addresses (already queried).
    async fn query_p2p_peers(
        &self,
        discovered: &[SocketAddr],
        hardcoded: &[SocketAddr],
    ) -> Vec<PeerChainInfo> {
        let hardcoded_set: HashSet<_> = hardcoded.iter().copied().collect();

        // Filter to non-hardcoded addresses only
        let p2p_candidates: Vec<_> = discovered
            .iter()
            .filter(|addr| !hardcoded_set.contains(addr))
            .copied()
            .collect();

        if p2p_candidates.is_empty() {
            warn!("No P2P peers discovered from hardcoded nodes");
            return Vec::new();
        }

        info!(
            "Querying {} P2P peers (target: {})...",
            p2p_candidates.len().min(P2P_PEER_COUNT),
            P2P_PEER_COUNT
        );

        // Select up to P2P_PEER_COUNT peers with subnet diversity
        let selected = select_diverse_peers(&p2p_candidates, P2P_PEER_COUNT);

        let responses = Arc::new(Mutex::new(Vec::new()));
        let testnet = self.testnet;
        let mut handles = Vec::new();

        for addr in selected {
            let sem = self.semaphore.clone();
            let responses = responses.clone();
            let listen_port = self.listen_port;
            let keypair = self.keypair.clone();

            let handle = tokio::spawn(async move {
                let _permit = sem.acquire().await.ok()?;

                match query_single_node(addr, listen_port, false, testnet, &keypair).await {
                    Ok((info, _)) => {
                        debug!("P2P {} responded: height={}", addr, info.slice_height);
                        responses.lock().await.push(info);
                        Some(())
                    }
                    Err(e) => {
                        debug!("P2P {} failed: {}", addr, e);
                        None
                    }
                }
            });

            handles.push(handle);
        }

        for handle in handles {
            let _ = handle.await;
        }

        Arc::try_unwrap(responses).unwrap().into_inner()
    }
}

// =============================================================================
// SINGLE NODE QUERY
// =============================================================================

/// Noise handshake timeout for verification connections.
const NOISE_TIMEOUT_SECS: u64 = 30;

/// Query a single node for chain info.
///
/// # Protocol (All Nodes)
///
/// 1. TCP connect with timeout
/// 2. Noise XX handshake (ML-KEM-768 hybrid encryption)
/// 3. For hardcoded: AuthChallenge → AuthResponse (ML-DSA-65 signature)
/// 4. For P2P: Version → Version exchange
/// 5. Verack exchange
/// 6. GetAddr → Addr/SignedAddr
/// 7. Disconnect
///
/// # Security
///
/// All connections use Noise XX encryption (compatible with protocol.rs).
/// Hardcoded nodes additionally prove identity via ML-DSA-65 challenge-response.
/// P2P nodes are verified through consensus, not authentication.
///
/// Returns (chain_info, discovered_addresses).
async fn query_single_node(
    addr: SocketAddr,
    listen_port: u16,
    is_hardcoded: bool,
    testnet: bool,
    keypair: &StaticKeypair,
) -> Result<(PeerChainInfo, Vec<SocketAddr>), VerificationError> {
    // Connect with timeout
    let stream = timeout(
        Duration::from_secs(CONNECT_TIMEOUT_SECS),
        TcpStream::connect(addr),
    )
    .await
    .map_err(|_| VerificationError::Timeout("connection".into()))?
    .map_err(|e| VerificationError::Connection(e.to_string()))?;

    // Noise XX handshake (compatible with protocol.rs)
    let encrypted = timeout(
        Duration::from_secs(NOISE_TIMEOUT_SECS),
        EncryptedStream::connect(stream, keypair),
    )
    .await
    .map_err(|_| VerificationError::Timeout("noise_handshake".into()))?
    .map_err(|e| VerificationError::Handshake(format!("noise: {}", e)))?;

    debug!("Noise handshake complete with {}", addr);

    let (mut reader, mut writer) = encrypted.split();

    let peer_version = if is_hardcoded {
        // =================================================================
        // AUTHENTICATED PROTOCOL FOR HARDCODED NODES
        // =================================================================
        // Hardcoded nodes must prove identity via challenge-response.
        // Noise encryption prevents MITM, but we need to verify the node
        // is actually the expected hardcoded node (not a Noise-capable attacker).
        // =================================================================

        // Verify this is a known hardcoded address
        if !is_hardcoded_addr(&addr, testnet) {
            return Err(VerificationError::UnknownHardcoded(addr));
        }

        // Generate random challenge (32 bytes of entropy)
        let challenge: Challenge = rand::random();

        // Send AuthChallenge
        write_message_encrypted(&mut writer, &Message::AuthChallenge(challenge)).await?;

        // Read AuthResponse with timeout
        let msg = timeout(
            Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
            read_message_encrypted(&mut reader),
        )
        .await
        .map_err(|_| VerificationError::Timeout("auth_response".into()))??;

        let (version, signature) = match msg {
            Message::AuthResponse { version, signature } => (version, signature),
            _ => return Err(VerificationError::Protocol("expected AuthResponse".into())),
        };

        // Verify signature against expected public key
        if let Err(_) = verify_hardcoded_response(&addr, &challenge, &signature, testnet) {
            return Err(VerificationError::AuthenticationFailed(addr));
        }

        // Validate protocol version
        if version.version < PROTOCOL_VERSION {
            return Err(VerificationError::Protocol(format!(
                "obsolete version: {} < {}",
                version.version, PROTOCOL_VERSION
            )));
        }

        // Send Verack
        write_message_encrypted(&mut writer, &Message::Verack).await?;

        // Read their Verack
        let msg = timeout(
            Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
            read_message_encrypted(&mut reader),
        )
        .await
        .map_err(|_| VerificationError::Timeout("verack".into()))??;

        match msg {
            Message::Verack => {}
            _ => return Err(VerificationError::Protocol("expected Verack".into())),
        }

        version
    } else {
        // =================================================================
        // UNAUTHENTICATED PROTOCOL FOR P2P NODES
        // =================================================================
        // P2P nodes are verified through consensus, not authentication.
        // Their reports are weighted against hardcoded + other P2P peers.
        // =================================================================

        // Prepare our Version message
        let our_addr = NetAddress::new("0.0.0.0".parse().unwrap(), listen_port, NODE_FULL);
        let their_addr = NetAddress::from_socket_addr(addr, 0);
        let version = VersionPayload::new(NODE_FULL, their_addr, our_addr, 0, NodeType::Full);

        // Send Version
        write_message_encrypted(&mut writer, &Message::Version(version)).await?;

        // Read their Version with timeout
        let msg = timeout(
            Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
            read_message_encrypted(&mut reader),
        )
        .await
        .map_err(|_| VerificationError::Timeout("version".into()))??;

        let peer_version = match msg {
            Message::Version(v) => v,
            _ => return Err(VerificationError::Protocol("expected Version".into())),
        };

        // Validate protocol version
        if peer_version.version < PROTOCOL_VERSION {
            return Err(VerificationError::Protocol(format!(
                "obsolete version: {} < {}",
                peer_version.version, PROTOCOL_VERSION
            )));
        }

        // Send Verack
        write_message_encrypted(&mut writer, &Message::Verack).await?;

        // Read their Verack
        let msg = timeout(
            Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
            read_message_encrypted(&mut reader),
        )
        .await
        .map_err(|_| VerificationError::Timeout("verack".into()))??;

        match msg {
            Message::Verack => {}
            _ => return Err(VerificationError::Protocol("expected Verack".into())),
        }

        peer_version
    };

    // Handshake complete — request addresses
    write_message_encrypted(&mut writer, &Message::GetAddr).await?;

    // Collect addresses with timeout
    let mut discovered_addrs = Vec::new();

    // Read Addr/SignedAddr message (with short timeout)
    if let Ok(Ok(msg)) = timeout(
        Duration::from_secs(QUERY_TIMEOUT_SECS),
        read_message_encrypted(&mut reader),
    )
    .await
    {
        match msg {
            Message::SignedAddr { addrs, signature } if is_hardcoded => {
                let pubkey = get_hardcoded_pubkey(&addr, testnet)
                    .ok_or_else(|| VerificationError::UnknownHardcoded(addr))?;

                let addrs_vec: Vec<_> = addrs.iter().cloned().collect();
                let addrs_bytes = bincode::serialize(&addrs_vec)
                    .map_err(|e| VerificationError::Protocol(format!("serialize addrs: {}", e)))?;

                if verify_mldsa65(pubkey, &addrs_bytes, &signature) {
                    debug!("SignedAddr from {} verified ({} addrs)", addr, addrs.len());
                    for net_addr in addrs.iter().take(MAX_ADDRS_PER_PEER) {
                        if net_addr.is_routable() {
                            discovered_addrs.push(net_addr.socket_addr());
                        }
                    }
                } else {
                    warn!("SignedAddr signature verification FAILED from {}", addr);
                }
            }
            // P2P nodes can send unsigned Addr (verified via consensus)
            Message::Addr(addrs) if !is_hardcoded => {
                for net_addr in addrs.iter().take(MAX_ADDRS_PER_PEER) {
                    if net_addr.is_routable() {
                        discovered_addrs.push(net_addr.socket_addr());
                    }
                }
            }
            // Hardcoded sending unsigned Addr is suspicious (downgrade attack)
            Message::Addr(_) if is_hardcoded => {
                warn!("Hardcoded {} sent unsigned Addr (expected SignedAddr) — ignoring", addr);
                // Do not use unsigned addresses from hardcoded nodes
            }
            _ => {
                debug!("Unexpected message type from {}, ignoring", addr);
            }
        }
    }

    // Build chain info from Version message
    let info = PeerChainInfo {
        peer: addr,
        slice_height: peer_version.best_slice,
        cumulative_weight: 0, // Version doesn't include weight, use height for consensus
        tip_hash: [0u8; 32],  // Not available in Version
        source: if is_hardcoded {
            PeerSource::Hardcoded
        } else {
            PeerSource::Gossip
        },
        peer_timestamp: peer_version.timestamp,
    };

    Ok((info, discovered_addrs))
}

// =============================================================================
// ENCRYPTED MESSAGE I/O
// =============================================================================

/// Write a message to the encrypted stream.
///
/// Uses Montana protocol framing: magic (4) + length (4) + checksum (4) + payload.
async fn write_message_encrypted(
    writer: &mut EncryptedWriter,
    msg: &Message,
) -> Result<(), VerificationError> {
    let payload = postcard::to_allocvec(msg)
        .map_err(|e| VerificationError::Protocol(format!("serialize: {}", e)))?;

    let checksum = &sha3(&payload)[..CHECKSUM_SIZE];

    // Build framed message: magic (4) + length (4) + checksum (4) + payload
    let mut framed = Vec::with_capacity(12 + payload.len());
    framed.extend_from_slice(&PROTOCOL_MAGIC);
    framed.extend_from_slice(&(payload.len() as u32).to_le_bytes());
    framed.extend_from_slice(checksum);
    framed.extend_from_slice(&payload);

    // Write encrypted (EncryptedWriter handles chunking for large messages)
    writer.write(&framed).await
        .map_err(|e| VerificationError::Protocol(format!("write: {}", e)))?;

    Ok(())
}

/// Read a message from the encrypted stream.
///
/// Uses Montana protocol framing: magic (4) + length (4) + checksum (4) + payload.
async fn read_message_encrypted(
    reader: &mut EncryptedReader,
) -> Result<Message, VerificationError> {
    // Read decrypted data (EncryptedReader handles chunk reassembly)
    let data = reader.read().await
        .map_err(|e| VerificationError::Protocol(format!("read: {}", e)))?;

    // Need at least 12 bytes for header
    if data.len() < 12 {
        return Err(VerificationError::Protocol("message too short".into()));
    }

    // Verify magic
    if &data[0..4] != &PROTOCOL_MAGIC {
        return Err(VerificationError::Protocol("invalid magic".into()));
    }

    // Parse length
    let length = u32::from_le_bytes([data[4], data[5], data[6], data[7]]) as usize;

    // Security: Limit message size
    if length > MAX_TX_SIZE {
        return Err(VerificationError::Protocol(format!(
            "message too large: {} (max: {})",
            length, MAX_TX_SIZE
        )));
    }

    // Verify we have enough data
    if data.len() < 12 + length {
        return Err(VerificationError::Protocol("incomplete message".into()));
    }

    let checksum = &data[8..12];
    let payload = &data[12..12 + length];

    // Verify checksum
    let computed = &sha3(payload)[..CHECKSUM_SIZE];
    if computed != checksum {
        return Err(VerificationError::Protocol("checksum mismatch".into()));
    }

    // Deserialize with postcard
    let msg: Message = postcard::from_bytes(payload)
        .map_err(|e| VerificationError::Protocol(format!("deserialize: {}", e)))?;

    // Validate collection sizes
    if !msg.validate_collection_sizes() {
        return Err(VerificationError::Protocol("collection size limit exceeded".into()));
    }

    Ok(msg)
}

// =============================================================================
// PEER SELECTION
// =============================================================================

/// Select diverse peers (max 5 per /16 subnet).
fn select_diverse_peers(candidates: &[SocketAddr], count: usize) -> Vec<SocketAddr> {
    let mut selected = Vec::new();
    let mut subnet_counts: HashMap<Subnet16, usize> = HashMap::new();
    const MAX_PER_SUBNET: usize = 5;

    for addr in candidates {
        if selected.len() >= count {
            break;
        }

        let subnet = ip_to_subnet16(addr.ip());
        let current = subnet_counts.entry(subnet).or_insert(0);

        if *current < MAX_PER_SUBNET {
            selected.push(*addr);
            *current += 1;
        }
    }

    selected
}

// =============================================================================
// RESULT TYPE
// =============================================================================

/// Verification result.
#[derive(Debug, Clone)]
pub struct VerificationResult {
    /// Verified chain height
    pub height: u64,
    /// Verified cumulative weight
    pub weight: u64,
    /// Network time (median from peers)
    pub network_time: u64,
    /// Number of hardcoded responses
    pub hardcoded_responses: usize,
    /// Number of P2P responses
    pub p2p_responses: usize,
    /// Unique /16 subnets
    pub unique_subnets: usize,
    /// Time warning (if any)
    pub time_warning: Option<String>,
    /// Height warning (if any)
    pub height_warning: Option<String>,
}

// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_select_diverse_peers() {
        let candidates: Vec<SocketAddr> = vec![
            "1.2.3.4:19333".parse().unwrap(),
            "1.2.3.5:19333".parse().unwrap(),
            "1.2.3.6:19333".parse().unwrap(),
            "1.2.3.7:19333".parse().unwrap(),
            "1.2.3.8:19333".parse().unwrap(),
            "1.2.3.9:19333".parse().unwrap(),  // 6th from same /16
            "2.3.4.5:19333".parse().unwrap(),
            "3.4.5.6:19333".parse().unwrap(),
        ];

        let selected = select_diverse_peers(&candidates, 10);

        // Should have 5 from 1.2.x.x + 1 from 2.3.x.x + 1 from 3.4.x.x = 7
        assert_eq!(selected.len(), 7);

        // Count per subnet
        let mut counts: HashMap<Subnet16, usize> = HashMap::new();
        for addr in &selected {
            let subnet = ip_to_subnet16(addr.ip());
            *counts.entry(subnet).or_insert(0) += 1;
        }

        // No subnet should have more than 5
        for (_, count) in counts {
            assert!(count <= 5);
        }
    }

    #[test]
    fn test_verification_result_defaults() {
        let result = VerificationResult {
            height: 1000,
            weight: 50000,
            network_time: 1735900000,
            hardcoded_responses: 18,
            p2p_responses: 75,
            unique_subnets: 30,
            time_warning: None,
            height_warning: None,
        };

        assert_eq!(result.hardcoded_responses + result.p2p_responses, 93);
    }
}
