use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};
use crate::merkle::{MerkleTree, MerkleProof};

pub const GENESIS_TIMESTAMP: u64 = 1735862400;  // 2026-01-03 00:00:00 UTC

pub const TAU1_MINUTES: u64 = 1;
pub const TAU2_MINUTES: u64 = 10;

/// Grace period for accepting signatures after τ₂ closes (30 seconds)
pub const GRACE_PERIOD_SECS: u64 = 30;
pub const TAU3_MINUTES: u64 = 20_160;  // 14 days
pub const TAU4_MINUTES: u64 = 2_102_400;  // 4 years

/// Adaptive cooldown constants
pub const COOLDOWN_MIN_TAU2: u64 = 144;         // 1 day minimum (144 τ₂/day)
pub const COOLDOWN_MAX_TAU2: u64 = 25_920;      // 180 days maximum (180 * 144 τ₂/day)
pub const COOLDOWN_WINDOW_TAU2: u64 = 2_016;    // 14 days median window (τ₃)
pub const COOLDOWN_DEFAULT_TAU2: u64 = 144;     // Genesis default: 1 day
/// Smoothing window: 4 τ₃ (56 days) for sliding average
pub const COOLDOWN_SMOOTH_WINDOWS: u64 = 4;
/// Maximum cooldown change per τ₃ (20%)
pub const COOLDOWN_MAX_CHANGE_PERCENT: u64 = 20;

pub const REWARD_PER_TAU2: u64 = 3000;
pub const TOTAL_SUPPLY: u64 = 1_260_000_000;
pub const HALVING_INTERVAL: u64 = 210_000;  // tau2 slices (~4 years)

/// Calculate reward for given slice index (with halving)
pub fn calculate_reward(slice_index: u64) -> u64 {
    let halvings = slice_index / HALVING_INTERVAL;
    if halvings >= 64 {
        return 0;  // After 64 halvings, reward is 0
    }
    REWARD_PER_TAU2 >> halvings
}

pub const TIER1_WEIGHT: u64 = 1;
pub const TIER2_WEIGHT: u64 = 20;
pub const TIER3_WEIGHT: u64 = 60_480;
pub const TIER4_WEIGHT: u64 = 8_409_600;

pub const FULL_NODE_CHANCE: u8 = 70;
pub const LIGHT_NODE_CHANCE: u8 = 20;
pub const LIGHT_CLIENT_CHANCE: u8 = 10;

pub type Hash = [u8; 32];
pub type PublicKey = Vec<u8>;  // ML-DSA-65: 1952 bytes
pub type Signature = Vec<u8>;  // ML-DSA-65: 3309 bytes

// =============================================================================
// SUBNET TYPES FOR RATE LIMITING
// =============================================================================
//
// IPv4: /16 subnet (65,536 possible) — hard cap, typical ISP assignment
// IPv6: /32 subnet (4B possible) — soft cap 50K with LRU eviction
//
// Rationale:
// - IPv4 /16: Standard ISP allocation, bounded by protocol (2^16 max)
// - IPv6 /32: Typical ISP allocation per RFC 6177, needs soft cap + eviction

/// IPv4 /16 subnet (first two octets)
/// Hard cap: 65,536 possible subnets
pub type Subnet16 = u16;

/// IPv6 /32 subnet (first four octets)
/// Soft cap: MAX_TRACKED_SUBNETS_V6 with LRU eviction
pub type Subnet32 = u32;

/// Unified subnet key for dual-stack rate limiting
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SubnetKey {
    /// IPv4 /16 subnet — hard cap 65,536
    V4(Subnet16),
    /// IPv6 /32 subnet — soft cap with LRU eviction
    V6(Subnet32),
}

/// Extract subnet key from IP address
///
/// IPv4: /16 (first 2 octets) — typical ISP assignment, hard cap 65,536
/// IPv6: /32 (first 4 octets) — typical ISP allocation per RFC 6177
pub fn ip_to_subnet(ip: std::net::IpAddr) -> SubnetKey {
    match ip {
        std::net::IpAddr::V4(ipv4) => {
            let octets = ipv4.octets();
            SubnetKey::V4(((octets[0] as u16) << 8) | (octets[1] as u16))
        }
        std::net::IpAddr::V6(ipv6) => {
            let segments = ipv6.segments();
            // /32 = first two 16-bit segments
            SubnetKey::V6(((segments[0] as u32) << 16) | (segments[1] as u32))
        }
    }
}

/// Legacy: Extract /16 subnet from IP address (IPv4 only meaningful)
#[deprecated(note = "Use ip_to_subnet() for proper IPv6 handling")]
pub fn ip_to_subnet16(ip: std::net::IpAddr) -> Subnet16 {
    match ip {
        std::net::IpAddr::V4(ipv4) => {
            let octets = ipv4.octets();
            ((octets[0] as u16) << 8) | (octets[1] as u16)
        }
        std::net::IpAddr::V6(ipv6) => {
            // DEPRECATED: /16 is useless for IPv6
            let segments = ipv6.segments();
            segments[0]
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum NodeType {
    Full,
    Light,
    Client,
}

impl NodeType {
    pub fn stage1_chance(&self) -> u8 {
        match self {
            NodeType::Full => FULL_NODE_CHANCE,
            NodeType::Light => LIGHT_NODE_CHANCE,
            NodeType::Client => LIGHT_CLIENT_CHANCE,
        }
    }

    pub fn from_seed(seed: u8) -> Self {
        match seed {
            0..=69 => NodeType::Full,
            70..=89 => NodeType::Light,
            _ => NodeType::Client,
        }
    }

    pub fn tier_index(&self) -> u8 {
        match self {
            NodeType::Full => 0,
            NodeType::Light => 1,
            NodeType::Client => 2,
        }
    }
}

/// Cooldown status for a node
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CooldownStatus {
    /// Node is in cooldown period (signs, visible, no weight)
    Active { until_tau2: u64 },
    /// Node has completed cooldown
    Completed,
}

impl CooldownStatus {
    pub fn is_active(&self, current_tau2: u64) -> bool {
        match self {
            CooldownStatus::Active { until_tau2 } => current_tau2 < *until_tau2,
            CooldownStatus::Completed => false,
        }
    }
}

/// Registration entry for median calculation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistrationEntry {
    pub pubkey: PublicKey,
    pub node_type: NodeType,
    pub registered_tau2: u64,
    pub cooldown_until: u64,
}

/// Median snapshot for cooldown calculation (per tier)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MedianSnapshot {
    /// Registration counts per τ₂ within the window (last τ₃)
    pub counts_per_tau2: Vec<(u64, u64)>,  // (tau2_index, count)
    /// Current median value
    pub median: u64,
    /// Last updated τ₂
    pub last_tau2: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PresenceProof {
    pub pubkey: PublicKey,
    pub tau2_index: u64,
    pub tau1_bitmap: u16,  // 10 bits for 10 minutes
    pub prev_slice_hash: Hash,
    pub timestamp: u64,    // P2P time attestation
    pub signature: Signature,
    /// Cooldown status (0 = active, >0 = cooldown_until τ₂)
    pub cooldown_until: u64,
}

impl PresenceProof {
    pub fn tau1_count(&self) -> u32 {
        self.tau1_bitmap.count_ones()
    }

    pub fn meets_threshold(&self) -> bool {
        self.tau1_count() >= 9  // 90% = 9/10
    }

    /// Node is in cooldown at this τ₂
    pub fn in_cooldown(&self) -> bool {
        self.cooldown_until > self.tau2_index
    }

    pub fn hash(&self) -> Hash {
        use sha3::{Digest, Sha3_256};
        let data = bincode::serialize(self).unwrap();
        Sha3_256::digest(&data).into()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SliceHeader {
    pub prev_hash: Hash,
    pub timestamp: u64,
    pub slice_index: u64,
    pub winner_pubkey: PublicKey,
    /// Cooldown medians at this slice [Full, Light, Client]
    pub cooldown_medians: [u64; 3],
    /// New registrations in this τ₂ [Full, Light, Client]
    pub registrations: [u64; 3],
    /// Cumulative chain weight (sum of all presence weights from genesis)
    /// Winner calculates: prev_cumulative + sum(presence_weights_in_slice)
    pub cumulative_weight: u64,
    /// Merkle root of subnet (/16) reputations
    /// Reputation = sum of weights of all nodes that ever signed from this subnet
    /// Updated every slice, snapshot every τ₃ (2016 slices)
    pub subnet_reputation_root: Hash,
}

impl SliceHeader {
    pub fn hash(&self) -> Hash {
        use sha3::{Digest, Sha3_256};
        let data = bincode::serialize(self).unwrap();
        Sha3_256::digest(&data).into()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Slice {
    pub header: SliceHeader,
    pub presence_root: Hash,
    pub tx_root: Hash,
    pub signature: Signature,
    /// Presences included in this slice
    #[serde(default)] // For backward compatibility if needed, though we are changing the protocol
    pub presences: Vec<PresenceProof>,
    /// Transactions included in this slice
    #[serde(default)]
    pub transactions: Vec<Transaction>,
}

impl Slice {
    pub fn hash(&self) -> Hash {
        use sha3::{Digest, Sha3_256};
        let data = bincode::serialize(&self.header).unwrap();
        let mut hasher = Sha3_256::new();
        hasher.update(&data);
        hasher.update(self.presence_root);
        hasher.update(self.tx_root);
        hasher.finalize().into()
    }

    /// Get Merkle proof for presence
    pub fn presence_proof(&self, pubkey: &[u8; 32]) -> Option<MerkleProof> {
        // Collect all presence hashes
        let leaves: Vec<[u8; 32]> = self.presences
            .iter()
            .map(|p| p.hash())
            .collect();

        let tree = MerkleTree::new(leaves);
        // Find index of pubkey
        let leaf_hash = self.presences.iter().find(|p| {
             p.pubkey.as_slice() == pubkey.as_slice()
        })?.hash();

        tree.proof_by_hash(&leaf_hash)
    }

    /// Get Merkle proof for transaction
    pub fn tx_proof(&self, tx_hash: &[u8; 32]) -> Option<MerkleProof> {
        let leaves: Vec<[u8; 32]> = self.transactions
            .iter()
            .map(|tx| tx.hash())
            .collect();
        
        let tree = MerkleTree::new(leaves);
        tree.proof_by_hash(tx_hash)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxInput {
    pub prev_tx: Hash,
    pub output_index: u32,
    pub signature: Signature,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TxOutput {
    pub amount: u64,
    pub pubkey: PublicKey,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub inputs: Vec<TxInput>,
    pub outputs: Vec<TxOutput>,
}

impl Transaction {
    pub fn hash(&self) -> Hash {
        use sha3::{Digest, Sha3_256};
        let data = bincode::serialize(self).unwrap();
        Sha3_256::digest(&data).into()
    }

    pub fn is_coinbase(&self) -> bool {
        self.inputs.is_empty()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeWeight {
    pub pubkey: PublicKey,
    pub node_type: NodeType,
    pub tier1_slices: u64,
    pub tier2_slices: u64,
    pub tier3_slices: u64,
    pub tier4_slices: u64,
    pub first_seen: u64,
    /// Cooldown until this τ₂ index (0 = no cooldown, genesis node)
    pub cooldown_until: u64,
    /// Last active τ₂ (for reactivation detection)
    pub last_active_tau2: u64,
    /// Is genesis node (no cooldown)
    pub is_genesis: bool,
}

impl NodeWeight {
    pub fn new(pubkey: PublicKey, node_type: NodeType, cooldown_until: u64) -> Self {
        Self {
            pubkey,
            node_type,
            tier1_slices: 0,
            tier2_slices: 0,
            tier3_slices: 0,
            tier4_slices: 0,
            first_seen: now(),
            cooldown_until,
            last_active_tau2: 0,
            is_genesis: false,
        }
    }

    pub fn genesis(pubkey: PublicKey, node_type: NodeType) -> Self {
        Self {
            pubkey,
            node_type,
            tier1_slices: 0,
            tier2_slices: 0,
            tier3_slices: 0,
            tier4_slices: 0,
            first_seen: now(),
            cooldown_until: 0,
            last_active_tau2: 0,
            is_genesis: true,
        }
    }

    pub fn total_weight(&self) -> u64 {
        self.tier1_slices * TIER1_WEIGHT
            + self.tier2_slices * TIER2_WEIGHT
            + self.tier3_slices * TIER3_WEIGHT
            + self.tier4_slices * TIER4_WEIGHT
    }

    /// Node can participate in lottery (completed cooldown only)
    pub fn can_participate(&self, current_tau2: u64) -> bool {
        !self.in_cooldown(current_tau2)
    }

    /// Node is currently in cooldown
    pub fn in_cooldown(&self, current_tau2: u64) -> bool {
        if self.is_genesis {
            return false;
        }
        current_tau2 < self.cooldown_until
    }

    /// Add presence for a τ₂ slice (only for active nodes)
    pub fn add_tier2(&mut self, current_tau2: u64) -> bool {
        if self.in_cooldown(current_tau2) {
            return false;  // No weight accumulation during cooldown
        }

        self.tier2_slices += 1;
        self.tier1_slices = 0;  // reset tier1 counter
        self.last_active_tau2 = current_tau2;

        if self.tier2_slices >= (TAU3_MINUTES / TAU2_MINUTES) {
            self.tier3_slices += 1;
            self.tier2_slices = 0;
        }
        true
    }

    /// Check if node needs reactivation cooldown (offline > τ₃)
    pub fn needs_reactivation(&self, current_tau2: u64) -> bool {
        if self.is_genesis || self.last_active_tau2 == 0 {
            return false;
        }
        let tau3_in_tau2 = TAU3_MINUTES / TAU2_MINUTES;  // 2016
        current_tau2.saturating_sub(self.last_active_tau2) > tau3_in_tau2
    }

    /// Set reactivation cooldown
    pub fn set_reactivation_cooldown(&mut self, cooldown_until: u64) {
        self.cooldown_until = cooldown_until;
    }

    /// Cooldown status for presence_root
    pub fn cooldown_status(&self, current_tau2: u64) -> CooldownStatus {
        if self.in_cooldown(current_tau2) {
            CooldownStatus::Active { until_tau2: self.cooldown_until }
        } else {
            CooldownStatus::Completed
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Utxo {
    pub tx_hash: Hash,
    pub output_index: u32,
    pub output: TxOutput,
}

pub fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

/// Seconds since genesis
pub fn secs_since_genesis() -> u64 {
    now().saturating_sub(GENESIS_TIMESTAMP)
}

/// Current tau1 (1-minute slice) from genesis
pub fn current_tau1() -> u64 {
    secs_since_genesis() / 60
}

/// Current tau2 (10-minute slice) from genesis
pub fn current_tau2() -> u64 {
    secs_since_genesis() / (TAU2_MINUTES * 60)
}

/// Seconds until next tau1 boundary (aligned to UTC minute)
pub fn secs_until_next_tau1() -> u64 {
    let secs = now();
    let elapsed_in_minute = secs % 60;
    if elapsed_in_minute == 0 { 0 } else { 60 - elapsed_in_minute }
}

/// Format tau1 for logging
pub fn tau1_to_string(tau1: u64) -> String {
    let start_secs = GENESIS_TIMESTAMP + tau1 * 60;

    use chrono::{TimeZone, Utc};
    let start = Utc.timestamp_opt(start_secs as i64, 0).unwrap();

    format!(
        "τ₁ #{} ({})",
        tau1,
        start.format("%Y-%m-%d %H:%M UTC")
    )
}

/// Format tau2 for logging
pub fn tau2_to_string(tau2: u64) -> String {
    let start_secs = GENESIS_TIMESTAMP + tau2 * TAU2_MINUTES * 60;
    let end_secs = start_secs + TAU2_MINUTES * 60;

    use chrono::{TimeZone, Utc};
    let start = Utc.timestamp_opt(start_secs as i64, 0).unwrap();
    let end = Utc.timestamp_opt(end_secs as i64, 0).unwrap();

    format!(
        "τ₂ #{} ({} — {} UTC)",
        tau2,
        start.format("%Y-%m-%d %H:%M"),
        end.format("%H:%M")
    )
}
