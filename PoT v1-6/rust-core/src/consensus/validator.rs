//! Block Validation for PoT Consensus
//!
//! Validates:
//! - Block header (version, timestamp, previous hash)
//! - Merkle root of transactions
//! - VDF proof (for checkpoint blocks)
//! - Leader VRF proof
//! - All transactions in block

use crate::{Error, Result};
use crate::crypto::vdf::{VDF, VDFProof};
use crate::crypto::hash::{sha256, merkle_root};
use crate::constants::{
    GENESIS_TIMESTAMP, POT_CHECKPOINT_INTERVAL, VDF_ITERATIONS,
    PROTOCOL_VERSION, MAX_BLOCK_SIZE,
};

/// Block validation result
#[derive(Debug, Clone)]
pub enum ValidationResult {
    /// Block is valid
    Valid,
    /// Block is invalid with reason
    Invalid(String),
    /// Block needs more data (e.g., missing parent)
    NeedsData(String),
}

impl ValidationResult {
    pub fn is_valid(&self) -> bool {
        matches!(self, ValidationResult::Valid)
    }
}

/// Block validator
pub struct BlockValidator {
    /// VDF engine for checkpoint verification
    vdf: VDF,
    /// Maximum allowed timestamp drift (seconds)
    max_future_time: u64,
    /// Timestamp tolerance for height matching
    timestamp_tolerance: u64,
}

impl BlockValidator {
    /// Create new validator
    pub fn new() -> Self {
        Self {
            vdf: VDF::new(VDF_ITERATIONS),
            max_future_time: 600, // 10 minutes
            timestamp_tolerance: 60, // 60 seconds
        }
    }

    /// Validate block header
    pub fn validate_header(
        &self,
        height: u64,
        timestamp: u64,
        version: u32,
        prev_hash: &[u8; 32],
        prev_timestamp: Option<u64>,
        current_time: u64,
    ) -> ValidationResult {
        // Protocol version
        if version > PROTOCOL_VERSION {
            return ValidationResult::Invalid(
                format!("Unknown protocol version: {}", version)
            );
        }

        // Timestamp must be after previous block
        if let Some(prev_ts) = prev_timestamp {
            if timestamp <= prev_ts {
                return ValidationResult::Invalid(
                    "Timestamp must be after previous block".into()
                );
            }
        }

        // Not too far in future
        if timestamp > current_time + self.max_future_time {
            return ValidationResult::Invalid(
                format!("Timestamp {} too far in future (max +{}s)",
                    timestamp, self.max_future_time)
            );
        }

        // Height-timestamp correspondence
        let expected_ts = GENESIS_TIMESTAMP + height;
        if timestamp.abs_diff(expected_ts) > self.timestamp_tolerance {
            return ValidationResult::Invalid(
                format!("Timestamp {} doesn't match height {} (expected ~{})",
                    timestamp, height, expected_ts)
            );
        }

        // Previous hash must not be all zeros (except for genesis)
        if height > 0 && prev_hash == &[0u8; 32] {
            return ValidationResult::Invalid("Invalid previous hash".into());
        }

        ValidationResult::Valid
    }

    /// Validate merkle root
    pub fn validate_merkle_root(
        &self,
        claimed_root: &[u8; 32],
        tx_hashes: &[[u8; 32]],
    ) -> ValidationResult {
        let computed = merkle_root(tx_hashes);
        if &computed != claimed_root {
            return ValidationResult::Invalid(
                "Merkle root mismatch".into()
            );
        }
        ValidationResult::Valid
    }

    /// Validate VDF proof (for checkpoint blocks)
    pub fn validate_vdf_proof(
        &self,
        height: u64,
        proof: &VDFProof,
    ) -> ValidationResult {
        // Only checkpoint blocks need VDF proof
        if height % POT_CHECKPOINT_INTERVAL != 0 {
            // Non-checkpoint block should not have VDF proof
            if proof.iterations > 0 {
                return ValidationResult::Invalid(
                    "Non-checkpoint block should not have VDF proof".into()
                );
            }
            return ValidationResult::Valid;
        }

        // Checkpoint block must have valid VDF proof
        if proof.iterations != VDF_ITERATIONS {
            return ValidationResult::Invalid(
                format!("Wrong VDF iterations: {} (expected {})",
                    proof.iterations, VDF_ITERATIONS)
            );
        }

        match self.vdf.verify(proof) {
            Ok(true) => ValidationResult::Valid,
            Ok(false) => ValidationResult::Invalid("VDF proof verification failed".into()),
            Err(e) => ValidationResult::Invalid(format!("VDF verification error: {}", e)),
        }
    }

    /// Validate block size
    pub fn validate_size(&self, size_bytes: usize) -> ValidationResult {
        if size_bytes > MAX_BLOCK_SIZE {
            return ValidationResult::Invalid(
                format!("Block too large: {} bytes (max {})", size_bytes, MAX_BLOCK_SIZE)
            );
        }
        ValidationResult::Valid
    }

    /// Check if height is a checkpoint
    pub fn is_checkpoint(height: u64) -> bool {
        height > 0 && height % POT_CHECKPOINT_INTERVAL == 0
    }

    /// Get checkpoint number for height
    pub fn checkpoint_number(height: u64) -> u64 {
        height / POT_CHECKPOINT_INTERVAL
    }

    /// Get blocks until next checkpoint
    pub fn blocks_until_checkpoint(height: u64) -> u64 {
        POT_CHECKPOINT_INTERVAL - (height % POT_CHECKPOINT_INTERVAL)
    }
}

impl Default for BlockValidator {
    fn default() -> Self {
        Self::new()
    }
}

/// Transaction validation rules
pub struct TxValidator {
    /// Minimum transaction fee in seconds
    pub min_fee: u64,
}

impl TxValidator {
    pub fn new() -> Self {
        Self {
            min_fee: 0, // No minimum fee for now
        }
    }

    /// Validate transaction structure
    pub fn validate_structure(
        &self,
        inputs_count: usize,
        outputs_count: usize,
        size_bytes: usize,
    ) -> ValidationResult {
        if inputs_count == 0 && outputs_count == 0 {
            return ValidationResult::Invalid("Empty transaction".into());
        }

        if size_bytes > 1_000_000 {
            return ValidationResult::Invalid("Transaction too large".into());
        }

        ValidationResult::Valid
    }
}

impl Default for TxValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_header() {
        let validator = BlockValidator::new();
        let now = GENESIS_TIMESTAMP + 1000;

        // Valid header
        let result = validator.validate_header(
            1000, // height
            now,  // timestamp
            PROTOCOL_VERSION,
            &[1u8; 32], // prev_hash
            Some(now - 1), // prev_timestamp
            now + 1, // current_time
        );
        assert!(result.is_valid());

        // Future timestamp
        let result = validator.validate_header(
            1000,
            now + 1000, // way in future
            PROTOCOL_VERSION,
            &[1u8; 32],
            Some(now - 1),
            now,
        );
        assert!(!result.is_valid());

        // Wrong height-timestamp
        let result = validator.validate_header(
            1000,
            GENESIS_TIMESTAMP + 2000, // doesn't match height 1000
            PROTOCOL_VERSION,
            &[1u8; 32],
            Some(GENESIS_TIMESTAMP + 999),
            GENESIS_TIMESTAMP + 2000,
        );
        assert!(!result.is_valid());
    }

    #[test]
    fn test_merkle_root() {
        let validator = BlockValidator::new();

        let h1 = sha256(b"tx1");
        let h2 = sha256(b"tx2");
        let root = merkle_root(&[h1, h2]);

        assert!(validator.validate_merkle_root(&root, &[h1, h2]).is_valid());
        assert!(!validator.validate_merkle_root(&[0u8; 32], &[h1, h2]).is_valid());
    }

    #[test]
    fn test_checkpoint_detection() {
        assert!(!BlockValidator::is_checkpoint(0));
        assert!(!BlockValidator::is_checkpoint(1));
        assert!(!BlockValidator::is_checkpoint(599));
        assert!(BlockValidator::is_checkpoint(600));
        assert!(!BlockValidator::is_checkpoint(601));
        assert!(BlockValidator::is_checkpoint(1200));
    }

    #[test]
    fn test_blocks_until_checkpoint() {
        assert_eq!(BlockValidator::blocks_until_checkpoint(0), 600);
        assert_eq!(BlockValidator::blocks_until_checkpoint(1), 599);
        assert_eq!(BlockValidator::blocks_until_checkpoint(599), 1);
        assert_eq!(BlockValidator::blocks_until_checkpoint(600), 600);
        assert_eq!(BlockValidator::blocks_until_checkpoint(601), 599);
    }
}
