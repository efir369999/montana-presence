//! Montana Finality Layer

use crate::types::{Hash, PublicKey, Signature, Slice, COOLDOWN_WINDOW_TAU2};
use sha3::{Digest, Sha3_256};
use std::collections::HashMap;

pub const SAFE_DEPTH: u32 = 6;
pub const FINAL_DEPTH: u64 = COOLDOWN_WINDOW_TAU2;
pub const CHECKPOINT_INTERVAL: u64 = COOLDOWN_WINDOW_TAU2;
pub const MAX_ATTESTATIONS_PER_SLICE: usize = 1000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FinalityStatus {
    pub slice_hash: Hash,
    pub slice_index: u64,
    pub finality_depth: u32,
    pub attestation_weight: u64,
    pub is_safe: bool,
    pub is_final: bool,
}

#[derive(Debug, Clone)]
pub struct SliceAttestation {
    pub slice_hash: Hash,
    pub attester_pubkey: PublicKey,
    pub attester_weight: u64,
    pub slice_index: u64,
    pub signature: Signature,
}

#[derive(Debug, Clone)]
pub struct FinalityCheckpoint {
    pub tau3_index: u64,
    pub slice_hash: Hash,
    pub slice_index: u64,
    pub cumulative_weight: u64,
    pub attestation_root: Hash,
    pub signatures: Vec<Signature>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FinalityError {
    InvalidSignature,
    InsufficientWeight,
    AlreadyAttested,
    TooManyAttestations,
}

impl std::fmt::Display for FinalityError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FinalityError::InvalidSignature => write!(f, "Invalid signature"),
            FinalityError::InsufficientWeight => write!(f, "Insufficient weight"),
            FinalityError::AlreadyAttested => write!(f, "Already attested"),
            FinalityError::TooManyAttestations => write!(f, "Too many attestations"),
        }
    }
}

impl std::error::Error for FinalityError {}

#[derive(Debug, Default)]
pub struct FinalityTracker {
    attestations: HashMap<Hash, Vec<SliceAttestation>>,
    slice_indices: HashMap<Hash, u64>,
    canonical_head: u64,
    finalized_checkpoint: Option<FinalityCheckpoint>,
}

impl FinalityTracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_attestation(&mut self, att: SliceAttestation) -> Result<(), FinalityError> {
        if att.signature.is_empty() {
            return Err(FinalityError::InvalidSignature);
        }
        if att.attester_weight == 0 {
            return Err(FinalityError::InsufficientWeight);
        }

        let atts = self.attestations.entry(att.slice_hash).or_default();
        if atts.len() >= MAX_ATTESTATIONS_PER_SLICE {
            return Err(FinalityError::TooManyAttestations);
        }
        if atts.iter().any(|a| a.attester_pubkey == att.attester_pubkey) {
            return Err(FinalityError::AlreadyAttested);
        }

        self.slice_indices.insert(att.slice_hash, att.slice_index);
        atts.push(att);
        Ok(())
    }

    pub fn get_status(&self, slice_hash: &Hash, current_head: u64) -> FinalityStatus {
        let slice_index = self.slice_indices.get(slice_hash).copied().unwrap_or(0);
        let finality_depth = current_head.saturating_sub(slice_index) as u32;
        let attestation_weight: u64 = self.attestations
            .get(slice_hash)
            .map(|atts| atts.iter().map(|a| a.attester_weight).sum())
            .unwrap_or(0);

        FinalityStatus {
            slice_hash: *slice_hash,
            slice_index,
            finality_depth,
            attestation_weight,
            is_safe: finality_depth >= SAFE_DEPTH,
            is_final: finality_depth as u64 >= FINAL_DEPTH,
        }
    }

    pub fn can_reorg_to(&self, target_index: u64) -> bool {
        // Can reorg if depth < SAFE_DEPTH
        self.canonical_head.saturating_sub(target_index) < SAFE_DEPTH as u64
    }

    pub fn update_head(&mut self, new_head_index: u64) {
        self.canonical_head = self.canonical_head.max(new_head_index);
    }

    pub fn create_checkpoint(&mut self, slice_index: u64, slice: &Slice) -> Option<FinalityCheckpoint> {
        if slice_index % CHECKPOINT_INTERVAL != 0 {
            return None;
        }

        let tau3_index = slice_index / CHECKPOINT_INTERVAL;
        let slice_hash = slice.hash();
        let atts = self.attestations.get(&slice_hash).cloned().unwrap_or_default();
        let attestation_root = compute_attestation_root(&atts);
        let signatures: Vec<Signature> = atts.iter().take(100).map(|a| a.signature.clone()).collect();

        let checkpoint = FinalityCheckpoint {
            tau3_index,
            slice_hash,
            slice_index,
            cumulative_weight: slice.header.cumulative_weight,
            attestation_root,
            signatures,
        };

        self.finalized_checkpoint = Some(checkpoint.clone());
        Some(checkpoint)
    }

    pub fn finalized_checkpoint(&self) -> Option<&FinalityCheckpoint> {
        self.finalized_checkpoint.as_ref()
    }

    pub fn canonical_head(&self) -> u64 {
        self.canonical_head
    }
}

fn compute_attestation_root(atts: &[SliceAttestation]) -> Hash {
    if atts.is_empty() {
        return [0u8; 32];
    }
    let mut hasher = Sha3_256::new();
    hasher.update(b"MONTANA_ATTESTATION_ROOT:");
    for att in atts {
        hasher.update(&att.slice_hash);
        hasher.update(&att.attester_pubkey);
        hasher.update(&att.attester_weight.to_le_bytes());
    }
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::SliceHeader;

    fn create_test_attestation(hash: Hash, weight: u64, index: u64, id: u8) -> SliceAttestation {
        SliceAttestation {
            slice_hash: hash,
            attester_pubkey: vec![id; 32],
            attester_weight: weight,
            slice_index: index,
            signature: vec![1, 2, 3],
        }
    }

    fn create_test_slice(index: u64) -> Slice {
        Slice {
            header: SliceHeader {
                prev_hash: [0u8; 32],
                timestamp: 1735862400 + index * 600,
                slice_index: index,
                winner_pubkey: vec![1u8; 32],
                cooldown_medians: [144, 144, 144],
                registrations: [0, 0, 0],
                cumulative_weight: index * 1000,
                subnet_reputation_root: [0u8; 32],
            },
            presence_root: [0u8; 32],
            tx_root: [0u8; 32],
            signature: vec![1u8; 64],
            presences: vec![],
            transactions: vec![],
        }
    }

    #[test]
    fn test_attestation_accumulation() {
        let mut tracker = FinalityTracker::new();
        let hash = [1u8; 32];
        for i in 0..5u8 {
            let att = create_test_attestation(hash, (i as u64 + 1) * 100, 1, i);
            tracker.add_attestation(att).unwrap();
        }
        let status = tracker.get_status(&hash, 10);
        assert_eq!(status.attestation_weight, 1500);
    }

    #[test]
    fn test_safe_threshold() {
        let mut tracker = FinalityTracker::new();
        let hash = [1u8; 32];
        tracker.add_attestation(create_test_attestation(hash, 100, 1, 0)).unwrap();
        
        let status = tracker.get_status(&hash, 1);
        assert!(!status.is_safe);
        
        let status = tracker.get_status(&hash, 7);
        assert!(status.is_safe);
    }

    #[test]
    fn test_final_threshold() {
        let mut tracker = FinalityTracker::new();
        let hash = [1u8; 32];
        tracker.add_attestation(create_test_attestation(hash, 100, 1, 0)).unwrap();
        let status = tracker.get_status(&hash, 2017);
        assert!(status.is_final);
    }

    #[test]
    fn test_reorg_protection() {
        let mut tracker = FinalityTracker::new();
        tracker.update_head(10);
        // target=1, head=10: depth=9 >= 6, cannot reorg
        assert!(!tracker.can_reorg_to(1));
        // target=8, head=10: depth=2 < 6, can reorg
        assert!(tracker.can_reorg_to(8));
    }

    #[test]
    fn test_duplicate_attester() {
        let mut tracker = FinalityTracker::new();
        let hash = [1u8; 32];
        tracker.add_attestation(create_test_attestation(hash, 100, 1, 0)).unwrap();
        assert_eq!(
            tracker.add_attestation(create_test_attestation(hash, 200, 1, 0)),
            Err(FinalityError::AlreadyAttested)
        );
    }

    #[test]
    fn test_checkpoint_creation() {
        let mut tracker = FinalityTracker::new();
        let slice = create_test_slice(CHECKPOINT_INTERVAL);
        let hash = slice.hash();
        tracker.add_attestation(create_test_attestation(hash, 1000, CHECKPOINT_INTERVAL, 0)).unwrap();
        
        let cp = tracker.create_checkpoint(CHECKPOINT_INTERVAL, &slice);
        assert!(cp.is_some());
        assert_eq!(cp.unwrap().tau3_index, 1);
    }

    #[test]
    fn test_update_head() {
        let mut tracker = FinalityTracker::new();
        tracker.update_head(5);
        assert_eq!(tracker.canonical_head(), 5);
        tracker.update_head(3);
        assert_eq!(tracker.canonical_head(), 5);
        tracker.update_head(10);
        assert_eq!(tracker.canonical_head(), 10);
    }
}
