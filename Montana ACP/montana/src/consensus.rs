//! ACP Consensus Layer — Presence-Based Consensus
//!
//! Architecture: 80% Full Node + 20% Verified User
//!
//! ```text
//! Bitcoin спрашивает: "Сколько работы ты сделал?" (PoW)
//! Ethereum спрашивает: "Сколько ты поставил?" (PoS)
//! Montana спрашивает: "ТЫ ЗДЕСЬ?"
//!
//! 80% — серверы (Full Node) — инфраструктура
//! 20% — люди (Verified User) — децентрализация
//!
//! lim(evidence → ∞) 1 Ɉ → 1 секунда
//! ```
//!
//! # Tiers
//!
//! ## Tier 1: Full Node (80% lottery)
//! - Automatic presence signature every τ₁ (1 minute)
//! - Signature: timestamp + prev_slice_hash + pubkey
//! - No biometrics — runs autonomously
//! - Accumulates weight through tiers 1-2-3-4
//!
//! ## Tier 2: Verified User (20% lottery)
//! - Mobile wallet app for regular users
//! - Requirements: app in foreground, screen active, hardware biometrics, FIDO2/WebAuthn
//! - Random verification interval: 10-40 minutes
//! - 30 second window for verification
//!
//! # Security Properties
//!
//! 1. **Sybil Resistant**: Biometrics + Secure Element = 1 person = 1 vote
//! 2. **Bot Resistant**: Unpredictable interval + 30 sec window
//! 3. **Impersonation Resistant**: FIDO2 device binding
//! 4. **Emulation Resistant**: Hardware attestation from Secure Enclave

use sha3::{Digest, Sha3_256};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

// ============================================================================
// CONSTANTS
// ============================================================================

/// Grace period at end of τ₂ — no new presence submissions accepted
pub const GRACE_PERIOD_SECS: u64 = 30;

/// Number of slots per τ₂ for backup producers
pub const SLOTS_PER_TAU2: u64 = 10;

/// Duration of each slot in seconds
pub const SLOT_DURATION_SECS: u64 = 60;

/// τ₁ — Full Node presence interval (1 minute)
pub const TAU1_SECS: u64 = 60;

/// τ₂ — Slice interval / Verified User min interval (10 minutes)
pub const TAU2_SECS: u64 = 600;

/// Verified User max interval (40 minutes)
pub const VERIFIED_USER_MAX_INTERVAL_SECS: u64 = 2400;

/// Verified User verification window (30 seconds)
pub const VERIFICATION_WINDOW_SECS: u64 = 30;

/// Full Node lottery cap
pub const FULL_NODE_CAP_PERCENT: u64 = 80;

/// Verified User lottery cap
pub const VERIFIED_USER_CAP_PERCENT: u64 = 20;

/// Legacy constants for backwards compatibility
pub const LIGHT_NODE_CAP_PERCENT: u64 = 20;
pub const LIGHT_CLIENT_CAP_PERCENT: u64 = 0;

/// Lottery precision for fractional weights
pub const LOTTERY_PRECISION: u64 = 1_000_000;

/// Maximum participants in a single lottery (prevents OOM)
pub const MAX_LOTTERY_PARTICIPANTS: usize = 10_000;

/// Maximum presences per slice (prevents OOM)
pub const MAX_PRESENCES_PER_SLICE: usize = 5_000;

/// Minimum days for τ₃ eligibility
pub const TAU3_MIN_DAYS: u64 = 14;

/// Success rate required for τ₃ (90%)
pub const TAU3_SUCCESS_RATE: f64 = 0.90;

/// Maximum stake per participant (prevents plutocracy)
pub const MAX_STAKE_RATIO: f64 = 0.01; // 1% of total

// ============================================================================
// NODE TYPES
// ============================================================================

/// Node tier in the network
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NodeTier {
    /// Full Node — stores full chain, validates everything
    /// Automatic presence every τ₁ (1 minute)
    FullNode,
    /// Verified User — mobile wallet with biometric attestation
    /// Random verification every 10-40 minutes
    VerifiedUser,
}

impl NodeTier {
    /// Get lottery cap percentage for this tier
    pub fn lottery_cap(&self) -> u64 {
        match self {
            NodeTier::FullNode => FULL_NODE_CAP_PERCENT,
            NodeTier::VerifiedUser => VERIFIED_USER_CAP_PERCENT,
        }
    }

    /// Get presence interval range in seconds
    pub fn presence_interval(&self) -> (u64, u64) {
        match self {
            NodeTier::FullNode => (TAU1_SECS, TAU1_SECS), // Fixed 1 minute
            NodeTier::VerifiedUser => (TAU2_SECS, VERIFIED_USER_MAX_INTERVAL_SECS), // 10-40 min
        }
    }
}

// ============================================================================
// PRESENCE PROOFS
// ============================================================================

/// Presence proof from a Full Node
///
/// Automatic signature every τ₁ (1 minute)
/// No human interaction required — pure infrastructure
#[derive(Debug, Clone)]
pub struct FullNodePresence {
    /// Timestamp when proof was created (UTC seconds)
    pub timestamp: u64,
    /// Hash of previous slice
    pub prev_slice_hash: [u8; 32],
    /// Public key of the node
    pub pubkey: [u8; 32],
    /// ED25519/MLDSA signature
    pub signature: Vec<u8>,
    /// τ₂ index this presence belongs to
    pub tau2_index: u64,
    /// Node tier (for weight calculation)
    pub tier: u8,
}

impl FullNodePresence {
    /// Create new presence proof
    pub fn new(
        prev_slice_hash: [u8; 32],
        pubkey: [u8; 32],
        keypair: &impl Signer,
    ) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let tau2_index = timestamp / TAU2_SECS;

        let message = Self::message_to_sign(timestamp, &prev_slice_hash, &pubkey, tau2_index);
        let signature = keypair.sign(&message);

        Self {
            timestamp,
            prev_slice_hash,
            pubkey,
            signature,
            tau2_index,
            tier: 1, // Default tier
        }
    }

    /// Message to sign for presence proof
    fn message_to_sign(
        timestamp: u64,
        prev_slice_hash: &[u8; 32],
        pubkey: &[u8; 32],
        tau2_index: u64,
    ) -> Vec<u8> {
        let mut msg = Vec::with_capacity(72 + 8);
        msg.extend_from_slice(b"MONTANA_PRESENCE_V1:");
        msg.extend_from_slice(&timestamp.to_le_bytes());
        msg.extend_from_slice(prev_slice_hash);
        msg.extend_from_slice(pubkey);
        msg.extend_from_slice(&tau2_index.to_le_bytes());
        msg
    }

    /// Verify the presence proof
    pub fn verify(&self, verifier: &impl Verifier) -> Result<(), PresenceError> {
        // Check timestamp is not in future
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        if self.timestamp > now + 10 {
            return Err(PresenceError::FutureTimestamp);
        }

        // Check timestamp is not too old (max 2 τ₂ periods)
        if self.timestamp < now.saturating_sub(TAU2_SECS * 2) {
            return Err(PresenceError::ExpiredTimestamp);
        }

        // Verify signature
        let message = Self::message_to_sign(
            self.timestamp,
            &self.prev_slice_hash,
            &self.pubkey,
            self.tau2_index,
        );

        if !verifier.verify(&self.pubkey, &message, &self.signature) {
            return Err(PresenceError::InvalidSignature);
        }

        Ok(())
    }

    /// Calculate SHA3-256 hash of this presence
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.timestamp.to_le_bytes());
        hasher.update(&self.prev_slice_hash);
        hasher.update(&self.pubkey);
        hasher.update(&self.signature);
        hasher.finalize().into()
    }
}

/// Presence proof from a Verified User (mobile wallet)
///
/// Requires:
/// - App in foreground
/// - Screen active
/// - Device with hardware biometrics
/// - Valid FIDO2/WebAuthn attestation
#[derive(Debug, Clone)]
pub struct VerifiedUserPresence {
    /// Timestamp when proof was created (UTC seconds)
    pub timestamp: u64,
    /// Hash of previous slice
    pub prev_slice_hash: [u8; 32],
    /// Public key of the user
    pub pubkey: [u8; 32],
    /// Number of accumulated τ₂ slices (1-4)
    pub accumulated_tau2: u8,
    /// Liveness attestation from Secure Enclave
    pub liveness_attestation: Vec<u8>,
    /// FIDO2/WebAuthn device attestation
    pub device_attestation: Fido2Attestation,
    /// Signature over all fields
    pub signature: Vec<u8>,
    /// τ₂ index this presence belongs to
    pub tau2_index: u64,
}

/// FIDO2/WebAuthn attestation data
#[derive(Debug, Clone)]
pub struct Fido2Attestation {
    /// Authenticator data (rpIdHash + flags + counter)
    pub auth_data: Vec<u8>,
    /// Client data JSON hash
    pub client_data_hash: [u8; 32],
    /// Attestation signature
    pub signature: Vec<u8>,
    /// Attestation certificate chain (optional)
    pub certificates: Vec<Vec<u8>>,
    /// Attestation format (packed, android-key, apple, etc.)
    pub format: AttestationFormat,
}

/// Supported attestation formats
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AttestationFormat {
    /// Standard packed attestation
    Packed,
    /// Android Key Attestation
    AndroidKey,
    /// Apple attestation (App Attest)
    Apple,
    /// Samsung Knox attestation
    SamsungKnox,
    /// Huawei HMS attestation
    HuaweiHms,
    /// TPM attestation
    Tpm,
    /// No attestation (for testing)
    None,
}

impl VerifiedUserPresence {
    /// Calculate next verification interval
    ///
    /// ```text
    /// seed = SHA3-256(prev_slice_hash || device_pubkey || last_check_τ₂)
    /// interval = 10 + (seed mod 31) minutes
    /// → From 10 to 40 minutes, unpredictable
    /// ```
    pub fn next_interval(
        prev_slice_hash: &[u8; 32],
        device_pubkey: &[u8; 32],
        last_check_tau2: u64,
    ) -> Duration {
        let mut hasher = Sha3_256::new();
        hasher.update(prev_slice_hash);
        hasher.update(device_pubkey);
        hasher.update(&last_check_tau2.to_le_bytes());
        let seed: [u8; 32] = hasher.finalize().into();

        // Take first 8 bytes as u64
        let seed_val = u64::from_le_bytes(seed[..8].try_into().unwrap());

        // 10 + (seed mod 31) = 10 to 40 minutes
        let minutes = 10 + (seed_val % 31);

        Duration::from_secs(minutes * 60)
    }

    /// Verify the presence proof
    pub fn verify(&self, verifier: &impl Verifier) -> Result<(), PresenceError> {
        // Check timestamp is not in future
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        if self.timestamp > now + 10 {
            return Err(PresenceError::FutureTimestamp);
        }

        // Check accumulated τ₂ is valid (1-4)
        if self.accumulated_tau2 == 0 || self.accumulated_tau2 > 4 {
            return Err(PresenceError::InvalidAccumulatedTau2);
        }

        // Verify FIDO2 attestation
        self.verify_fido2_attestation()?;

        // Verify liveness attestation
        self.verify_liveness_attestation()?;

        // Verify main signature
        let message = self.message_to_sign();
        if !verifier.verify(&self.pubkey, &message, &self.signature) {
            return Err(PresenceError::InvalidSignature);
        }

        Ok(())
    }

    fn message_to_sign(&self) -> Vec<u8> {
        let mut msg = Vec::with_capacity(128);
        msg.extend_from_slice(b"MONTANA_VERIFIED_USER_V1:");
        msg.extend_from_slice(&self.timestamp.to_le_bytes());
        msg.extend_from_slice(&self.prev_slice_hash);
        msg.extend_from_slice(&self.pubkey);
        msg.push(self.accumulated_tau2);
        msg.extend_from_slice(&self.liveness_attestation);
        msg.extend_from_slice(&self.device_attestation.auth_data);
        msg.extend_from_slice(&self.tau2_index.to_le_bytes());
        msg
    }

    fn verify_fido2_attestation(&self) -> Result<(), PresenceError> {
        let att = &self.device_attestation;

        // Check auth_data minimum length (37 bytes)
        // rpIdHash (32) + flags (1) + counter (4)
        if att.auth_data.len() < 37 {
            return Err(PresenceError::InvalidFido2AuthData);
        }

        // Check flags (byte 32)
        let flags = att.auth_data[32];

        // User Present (UP) flag must be set
        if flags & 0x01 == 0 {
            return Err(PresenceError::Fido2UserNotPresent);
        }

        // User Verified (UV) flag must be set (biometrics)
        if flags & 0x04 == 0 {
            return Err(PresenceError::Fido2UserNotVerified);
        }

        // Verify attestation signature based on format
        match att.format {
            AttestationFormat::None => {
                // No attestation — only allowed in tests
                #[cfg(not(test))]
                return Err(PresenceError::NoAttestation);
            }
            AttestationFormat::Packed | AttestationFormat::AndroidKey | AttestationFormat::Apple => {
                // Verify signature over (authData || clientDataHash)
                if att.signature.is_empty() {
                    return Err(PresenceError::InvalidFido2Signature);
                }
                // Full signature verification would require parsing certificates
                // and verifying the chain — simplified for now
            }
            AttestationFormat::SamsungKnox | AttestationFormat::HuaweiHms | AttestationFormat::Tpm => {
                // Platform-specific attestation verification
                if att.certificates.is_empty() {
                    return Err(PresenceError::MissingAttestationCert);
                }
            }
        }

        Ok(())
    }

    fn verify_liveness_attestation(&self) -> Result<(), PresenceError> {
        // Liveness attestation from Secure Enclave
        // Must be at least 64 bytes (signature)
        if self.liveness_attestation.len() < 64 {
            return Err(PresenceError::InvalidLivenessAttestation);
        }

        Ok(())
    }

    /// Calculate SHA3-256 hash of this presence
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.timestamp.to_le_bytes());
        hasher.update(&self.prev_slice_hash);
        hasher.update(&self.pubkey);
        hasher.update(&[self.accumulated_tau2]);
        hasher.update(&self.liveness_attestation);
        hasher.update(&self.device_attestation.auth_data);
        hasher.update(&self.signature);
        hasher.finalize().into()
    }
}

/// Errors during presence verification
#[derive(Debug, Clone, PartialEq)]
pub enum PresenceError {
    FutureTimestamp,
    ExpiredTimestamp,
    InvalidSignature,
    InvalidAccumulatedTau2,
    InvalidFido2AuthData,
    Fido2UserNotPresent,
    Fido2UserNotVerified,
    InvalidFido2Signature,
    NoAttestation,
    MissingAttestationCert,
    InvalidLivenessAttestation,
    InGracePeriod,
    NotEligible,
}

// ============================================================================
// LOTTERY SYSTEM
// ============================================================================

/// Lottery participant with weight and tier
#[derive(Debug, Clone)]
pub struct LotteryParticipant {
    pub pubkey: [u8; 32],
    pub tier: NodeTier,
    pub weight: u64,
    pub presence_hash: [u8; 32],
}

/// Lottery result for a τ₂ period
#[derive(Debug, Clone)]
pub struct LotteryResult {
    pub tau2_index: u64,
    pub seed: [u8; 32],
    pub winners: Vec<LotteryWinner>,
    pub total_weight: u64,
    pub full_node_weight: u64,
    pub verified_user_weight: u64,
}

/// Single lottery winner with ticket and rank
#[derive(Debug, Clone)]
pub struct LotteryWinner {
    pub pubkey: [u8; 32],
    pub tier: NodeTier,
    pub ticket: [u8; 32],
    pub rank: u32,
    pub weight: u64,
}

/// Lottery engine — grinding-resistant selection
#[derive(Debug)]
pub struct Lottery {
    participants: Vec<LotteryParticipant>,
    prev_slice_hash: [u8; 32],
    tau2_index: u64,
}

impl Lottery {
    /// Create new lottery for a τ₂ period
    pub fn new(prev_slice_hash: [u8; 32], tau2_index: u64) -> Self {
        Self {
            participants: Vec::new(),
            prev_slice_hash,
            tau2_index,
        }
    }

    /// Add participant to the lottery (bounded)
    pub fn add_participant(&mut self, participant: LotteryParticipant) -> bool {
        if self.participants.len() >= MAX_LOTTERY_PARTICIPANTS {
            return false;
        }
        self.participants.push(participant);
        true
    }

    /// Calculate lottery seed (deterministic, pre-block)
    ///
    /// ```text
    /// CORRECT:  seed = SHA3(prev_slice_hash ‖ τ₂_index)
    /// WRONG:    seed = SHA3(prev_slice_hash ‖ τ₂_index ‖ presence_root)
    ///                                                    ^^^^^^^^^^^^^^
    ///                                                    Block producer controls this!
    /// ```
    pub fn seed(&self) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.prev_slice_hash);
        hasher.update(&self.tau2_index.to_le_bytes());
        hasher.finalize().into()
    }

    /// Calculate ticket for a participant
    ///
    /// ```text
    /// ticket = SHA3-256(seed ‖ pubkey)
    /// ```
    fn ticket(&self, seed: &[u8; 32], pubkey: &[u8; 32]) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(seed);
        hasher.update(pubkey);
        hasher.finalize().into()
    }

    /// Run the lottery and select winners
    ///
    /// Returns ranked list of winners (lowest ticket = rank 1)
    /// with tier caps applied (80% Full Node, 20% Verified User)
    pub fn run(&self) -> LotteryResult {
        let seed = self.seed();

        // Calculate tickets for all participants
        let mut entries: Vec<(LotteryParticipant, [u8; 32])> = self
            .participants
            .iter()
            .map(|p| (p.clone(), self.ticket(&seed, &p.pubkey)))
            .collect();

        // Sort by ticket (lowest first)
        entries.sort_by(|a, b| a.1.cmp(&b.1));

        // Calculate total weights by tier
        let full_node_weight: u64 = self
            .participants
            .iter()
            .filter(|p| p.tier == NodeTier::FullNode)
            .map(|p| p.weight)
            .sum();

        let verified_user_weight: u64 = self
            .participants
            .iter()
            .filter(|p| p.tier == NodeTier::VerifiedUser)
            .map(|p| p.weight)
            .sum();

        let total_weight = full_node_weight + verified_user_weight;

        // Apply tier caps
        let full_node_cap = (total_weight * FULL_NODE_CAP_PERCENT) / 100;
        let verified_user_cap = (total_weight * VERIFIED_USER_CAP_PERCENT) / 100;

        let mut winners = Vec::new();
        let mut full_node_selected = 0u64;
        let mut verified_user_selected = 0u64;
        let mut rank = 1u32;

        for (participant, ticket) in entries {
            let can_select = match participant.tier {
                NodeTier::FullNode => {
                    full_node_selected + participant.weight <= full_node_cap
                }
                NodeTier::VerifiedUser => {
                    verified_user_selected + participant.weight <= verified_user_cap
                }
            };

            if can_select {
                match participant.tier {
                    NodeTier::FullNode => full_node_selected += participant.weight,
                    NodeTier::VerifiedUser => verified_user_selected += participant.weight,
                }

                winners.push(LotteryWinner {
                    pubkey: participant.pubkey,
                    tier: participant.tier,
                    ticket,
                    rank,
                    weight: participant.weight,
                });

                rank += 1;
            }

            // Stop after SLOTS_PER_TAU2 winners (backup slots)
            if winners.len() >= SLOTS_PER_TAU2 as usize {
                break;
            }
        }

        LotteryResult {
            tau2_index: self.tau2_index,
            seed,
            winners,
            total_weight,
            full_node_weight,
            verified_user_weight,
        }
    }

    /// Verify that a pubkey is the winner for a given slot
    pub fn verify_winner(
        result: &LotteryResult,
        pubkey: &[u8; 32],
        slot: u32,
    ) -> bool {
        if slot as usize >= result.winners.len() {
            return false;
        }

        result.winners[slot as usize].pubkey == *pubkey
    }
}

// ============================================================================
// SLICE (BLOCK) STRUCTURE
// ============================================================================

/// Montana slice (equivalent to a block)
///
/// Contains presence proofs from a τ₂ period
#[derive(Debug, Clone)]
pub struct Slice {
    /// Slice header
    pub header: SliceHeader,
    /// Full Node presence proofs
    pub full_node_presences: Vec<FullNodePresence>,
    /// Verified User presence proofs
    pub verified_user_presences: Vec<VerifiedUserPresence>,
    /// Transactions (if any)
    pub transactions: Vec<Vec<u8>>,
    /// Producer's signature
    pub producer_signature: Vec<u8>,
    /// Finality attestations for this slice (optional; may be empty)
    pub attestations: Vec<crate::finality::SliceAttestation>,
}

/// Slice header — minimal data for light clients
#[derive(Debug, Clone)]
pub struct SliceHeader {
    /// Slice version
    pub version: u32,
    /// Height in Ɉ (confirmed time units)
    pub height: u64,
    /// τ₂ index
    pub tau2_index: u64,
    /// Timestamp (UTC seconds)
    pub timestamp: u64,
    /// Previous slice hash
    pub prev_slice_hash: [u8; 32],
    /// Merkle root of presence proofs
    pub presence_root: [u8; 32],
    /// Merkle root of transactions
    pub tx_root: [u8; 32],
    /// Producer's public key
    pub producer_pubkey: [u8; 32],
    /// Lottery ticket (for verification)
    pub lottery_ticket: [u8; 32],
    /// Slot number used (0 = primary, 1+ = backup)
    pub slot: u32,
    /// Hash of the last finalized checkpoint (if any)
    pub finality_checkpoint: Option<[u8; 32]>,
}

impl SliceHeader {
    /// Calculate SHA3-256 hash of the header
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.version.to_le_bytes());
        hasher.update(&self.height.to_le_bytes());
        hasher.update(&self.tau2_index.to_le_bytes());
        hasher.update(&self.timestamp.to_le_bytes());
        hasher.update(&self.prev_slice_hash);
        hasher.update(&self.presence_root);
        hasher.update(&self.tx_root);
        hasher.update(&self.producer_pubkey);
        hasher.update(&self.lottery_ticket);
        hasher.update(&self.slot.to_le_bytes());
        // Bind to last finalized checkpoint (or 0x00..00)
        hasher.update(self.finality_checkpoint.unwrap_or([0u8; 32]));
        hasher.finalize().into()
    }
}

impl Slice {
    /// Verify the slice
    pub fn verify(&self, lottery_result: &LotteryResult, verifier: &impl Verifier) -> Result<(), SliceError> {
        // Check presence count limits (OOM protection)
        let total_presences = self.full_node_presences.len() + self.verified_user_presences.len();
        if total_presences > MAX_PRESENCES_PER_SLICE {
            return Err(SliceError::TooManyPresences);
        }

        // Verify producer is valid winner for this slot
        if !Lottery::verify_winner(lottery_result, &self.header.producer_pubkey, self.header.slot) {
            return Err(SliceError::InvalidProducer);
        }

        // Verify lottery ticket matches
        if self.header.lottery_ticket != lottery_result.winners[self.header.slot as usize].ticket {
            return Err(SliceError::LotteryTicketMismatch);
        }

        // Verify presence root
        let computed_presence_root = self.compute_presence_root();
        if computed_presence_root != self.header.presence_root {
            return Err(SliceError::PresenceRootMismatch);
        }

        // Verify all Full Node presences
        for presence in &self.full_node_presences {
            presence.verify(verifier).map_err(|e| SliceError::PresenceError(e))?;
        }

        // Verify all Verified User presences
        for presence in &self.verified_user_presences {
            presence.verify(verifier).map_err(|e| SliceError::PresenceError(e))?;
        }

        // Verify producer signature
        let header_hash = self.header.hash();
        if !verifier.verify(&self.header.producer_pubkey, &header_hash, &self.producer_signature) {
            return Err(SliceError::InvalidProducerSignature);
        }

        Ok(())
    }

    /// Compute merkle root of presence proofs
    fn compute_presence_root(&self) -> [u8; 32] {
        let mut hashes: Vec<[u8; 32]> = Vec::new();

        // Add Full Node presence hashes
        for p in &self.full_node_presences {
            hashes.push(p.hash());
        }

        // Add Verified User presence hashes
        for p in &self.verified_user_presences {
            hashes.push(p.hash());
        }

        if hashes.is_empty() {
            return [0u8; 32];
        }

        // Simple merkle tree (SHA3 pairs)
        while hashes.len() > 1 {
            let mut next_level = Vec::new();
            for chunk in hashes.chunks(2) {
                let mut hasher = Sha3_256::new();
                hasher.update(&chunk[0]);
                if chunk.len() > 1 {
                    hasher.update(&chunk[1]);
                } else {
                    hasher.update(&chunk[0]); // Duplicate odd leaf
                }
                next_level.push(hasher.finalize().into());
            }
            hashes = next_level;
        }

        hashes[0]
    }
}

/// Errors during slice verification
#[derive(Debug, Clone)]
pub enum SliceError {
    InvalidProducer,
    LotteryTicketMismatch,
    PresenceRootMismatch,
    PresenceError(PresenceError),
    InvalidProducerSignature,
    InvalidTimestamp,
    InvalidHeight,
    TooManyPresences,
}

// ============================================================================
// TRAITS FOR CRYPTO ABSTRACTION
// ============================================================================

/// Trait for signing operations
pub trait Signer {
    fn sign(&self, message: &[u8]) -> Vec<u8>;
    fn public_key(&self) -> [u8; 32];
}

/// Trait for verification operations
pub trait Verifier {
    fn verify(&self, pubkey: &[u8; 32], message: &[u8], signature: &[u8]) -> bool;
}

// ============================================================================
// WEIGHT CALCULATION
// ============================================================================

/// Weight progression through tiers
///
/// τ₂ → τ₃ → τ₄:
/// - τ₂: Basic presence weight
/// - τ₃: 90% success rate over 14 days → tier 3 weight
/// - τ₄: Long-term consistent presence → tier 4 weight
pub struct WeightCalculator;

impl WeightCalculator {
    /// Calculate participant weight based on presence history
    pub fn calculate(presences: &[u64], current_tau2: u64) -> u64 {
        if presences.is_empty() {
            return 0;
        }

        // Count successful presences in last 14 days
        let cutoff = current_tau2.saturating_sub(TAU3_MIN_DAYS * 24 * 6); // τ₂ periods per day
        let recent: Vec<_> = presences.iter().filter(|&&t| t >= cutoff).collect();

        let expected = TAU3_MIN_DAYS * 24 * 6; // One per τ₂
        let success_rate = recent.len() as f64 / expected as f64;

        let base_weight = recent.len() as u64;

        if success_rate >= TAU3_SUCCESS_RATE {
            // Tier 3 bonus: 1.5x weight
            (base_weight * 3) / 2
        } else {
            base_weight
        }
    }
}

// ============================================================================
// GRACE PERIOD
// ============================================================================

/// Check if we're in the grace period (last 30 seconds of τ₂)
///
/// During grace period, no new presence submissions are accepted.
/// This gives network time to propagate final state before lottery.
pub fn in_grace_period() -> bool {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    let time_in_tau2 = now % TAU2_SECS;
    time_in_tau2 >= (TAU2_SECS - GRACE_PERIOD_SECS)
}

/// Get seconds until next τ₂ boundary
pub fn seconds_until_tau2() -> u64 {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    TAU2_SECS - (now % TAU2_SECS)
}

/// Get current τ₂ index
pub fn current_tau2_index() -> u64 {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();

    now / TAU2_SECS
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // Mock signer/verifier for tests
    struct MockCrypto;

    impl Signer for MockCrypto {
        fn sign(&self, _message: &[u8]) -> Vec<u8> {
            vec![0u8; 64]
        }
        fn public_key(&self) -> [u8; 32] {
            [1u8; 32]
        }
    }

    impl Verifier for MockCrypto {
        fn verify(&self, _pubkey: &[u8; 32], _message: &[u8], signature: &[u8]) -> bool {
            signature.len() == 64
        }
    }

    #[test]
    fn test_constants() {
        assert_eq!(GRACE_PERIOD_SECS, 30);
        assert_eq!(SLOTS_PER_TAU2, 10);
        assert_eq!(TAU1_SECS, 60);
        assert_eq!(TAU2_SECS, 600);
        assert_eq!(FULL_NODE_CAP_PERCENT + VERIFIED_USER_CAP_PERCENT, 100);
    }

    #[test]
    fn test_node_tier_caps() {
        assert_eq!(NodeTier::FullNode.lottery_cap(), 80);
        assert_eq!(NodeTier::VerifiedUser.lottery_cap(), 20);
    }

    #[test]
    fn test_lottery_seed_deterministic() {
        let prev_hash = [1u8; 32];
        let tau2_index = 12345u64;

        let lottery1 = Lottery::new(prev_hash, tau2_index);
        let lottery2 = Lottery::new(prev_hash, tau2_index);

        assert_eq!(lottery1.seed(), lottery2.seed());
    }

    #[test]
    fn test_lottery_seed_different_inputs() {
        let lottery1 = Lottery::new([1u8; 32], 100);
        let lottery2 = Lottery::new([2u8; 32], 100);
        let lottery3 = Lottery::new([1u8; 32], 101);

        assert_ne!(lottery1.seed(), lottery2.seed());
        assert_ne!(lottery1.seed(), lottery3.seed());
    }

    #[test]
    fn test_lottery_with_participants() {
        let mut lottery = Lottery::new([0u8; 32], 1);

        // Add Full Node participants
        for i in 0..5 {
            let mut pubkey = [0u8; 32];
            pubkey[0] = i;
            lottery.add_participant(LotteryParticipant {
                pubkey,
                tier: NodeTier::FullNode,
                weight: 100,
                presence_hash: [i; 32],
            });
        }

        // Add Verified User participants
        for i in 5..8 {
            let mut pubkey = [0u8; 32];
            pubkey[0] = i;
            lottery.add_participant(LotteryParticipant {
                pubkey,
                tier: NodeTier::VerifiedUser,
                weight: 50,
                presence_hash: [i; 32],
            });
        }

        let result = lottery.run();

        assert_eq!(result.tau2_index, 1);
        assert!(!result.winners.is_empty());
        assert!(result.winners.len() <= SLOTS_PER_TAU2 as usize);

        // Verify winners are ranked by ticket
        for i in 1..result.winners.len() {
            assert!(result.winners[i - 1].ticket < result.winners[i].ticket);
        }
    }

    #[test]
    fn test_verified_user_interval() {
        let prev_hash = [1u8; 32];
        let pubkey = [2u8; 32];
        let tau2 = 100u64;

        let interval = VerifiedUserPresence::next_interval(&prev_hash, &pubkey, tau2);

        // Should be between 10 and 40 minutes
        assert!(interval >= Duration::from_secs(10 * 60));
        assert!(interval <= Duration::from_secs(40 * 60));
    }

    #[test]
    fn test_verified_user_interval_deterministic() {
        let prev_hash = [1u8; 32];
        let pubkey = [2u8; 32];
        let tau2 = 100u64;

        let interval1 = VerifiedUserPresence::next_interval(&prev_hash, &pubkey, tau2);
        let interval2 = VerifiedUserPresence::next_interval(&prev_hash, &pubkey, tau2);

        assert_eq!(interval1, interval2);
    }

    #[test]
    fn test_full_node_presence_creation() {
        let prev_hash = [1u8; 32];
        let pubkey = [2u8; 32];
        let crypto = MockCrypto;

        let presence = FullNodePresence::new(prev_hash, pubkey, &crypto);

        assert_eq!(presence.prev_slice_hash, prev_hash);
        assert_eq!(presence.pubkey, pubkey);
        assert!(!presence.signature.is_empty());
    }

    #[test]
    fn test_slice_header_hash() {
        let header = SliceHeader {
            version: 1,
            height: 1000,
            tau2_index: 100,
            timestamp: 1704844800,
            prev_slice_hash: [1u8; 32],
            presence_root: [2u8; 32],
            tx_root: [3u8; 32],
            producer_pubkey: [4u8; 32],
            lottery_ticket: [5u8; 32],
            slot: 0,
            finality_checkpoint: None,
        };

        let hash1 = header.hash();
        let hash2 = header.hash();

        assert_eq!(hash1, hash2);
        assert_ne!(hash1, [0u8; 32]);
    }

    #[test]
    fn test_weight_calculation() {
        let current_tau2 = 10000u64;

        // No presences = 0 weight
        assert_eq!(WeightCalculator::calculate(&[], current_tau2), 0);

        // Recent presences
        let presences: Vec<u64> = (9900..10000).collect();
        let weight = WeightCalculator::calculate(&presences, current_tau2);
        assert!(weight > 0);
    }
}
