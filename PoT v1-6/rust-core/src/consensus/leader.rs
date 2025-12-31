//! Leader Selection for PoT Consensus
//!
//! Uses VRF (Verifiable Random Function) to select block producers:
//! - Each node generates VRF proof using slot number as input
//! - If VRF output < threshold (based on stake), node is leader
//! - Multiple leaders possible (probabilistic)
//! - VRF proof included in block for verification
//!
//! ## Security Properties
//!
//! - **Unpredictability**: Next leader unknown until VRF revealed
//! - **Verifiability**: Anyone can verify leader was legitimately selected
//! - **Fairness**: Selection probability proportional to stake
//!
//! ## Integer Arithmetic
//!
//! CRITICAL: All threshold comparisons use 128-bit integer arithmetic.
//! Never use floating-point for consensus-critical calculations!
//! (float64 mantissa is only 53 bits, insufficient for 256-bit VRF output)

use crate::crypto::vrf::{VRF, VRFOutput, VRFProof};
use crate::{Error, Result};
use crate::constants::GENESIS_TIMESTAMP;

/// Leader selection parameters
#[derive(Debug, Clone)]
pub struct LeaderParams {
    /// Base threshold in parts per million (ppm)
    /// 1_000_000 = 100%, 100_000 = 10%, etc.
    pub base_threshold_ppm: u64,

    /// Minimum stake required to be eligible
    pub min_stake: u64,

    /// Total active stake in the network
    pub total_stake: u64,
}

impl Default for LeaderParams {
    fn default() -> Self {
        Self {
            // 10% base probability per block (adjusted by stake ratio)
            base_threshold_ppm: 100_000,
            min_stake: 1_000, // 1000 seconds minimum
            total_stake: 1_000_000_000, // 1B seconds total (placeholder)
        }
    }
}

/// Leader selector using VRF
pub struct LeaderSelector {
    params: LeaderParams,
}

impl LeaderSelector {
    /// Create new leader selector with parameters
    pub fn new(params: LeaderParams) -> Self {
        Self { params }
    }

    /// Create with default parameters
    pub fn default() -> Self {
        Self::new(LeaderParams::default())
    }

    /// Check if a node is leader for given slot
    ///
    /// # Arguments
    /// * `vrf` - Node's VRF instance (requires secret key)
    /// * `slot` - Slot number to check
    /// * `stake` - Node's stake amount
    ///
    /// # Returns
    /// * `Ok(Some((output, proof)))` if node is leader
    /// * `Ok(None)` if node is not leader
    pub fn check_leader(
        &self,
        vrf: &VRF,
        slot: u64,
        stake: u64,
    ) -> Result<Option<(VRFOutput, VRFProof)>> {
        // Check minimum stake
        if stake < self.params.min_stake {
            return Ok(None);
        }

        // Compute VRF for this slot
        let input = self.slot_to_input(slot);
        let (output, proof) = vrf.prove(&input)?;

        // Check if output is below threshold
        if self.is_leader(&output, stake) {
            Ok(Some((output, proof)))
        } else {
            Ok(None)
        }
    }

    /// Verify that a node was legitimately selected as leader
    ///
    /// # Arguments
    /// * `public_key` - Node's VRF public key
    /// * `slot` - Slot number
    /// * `proof` - VRF proof from block
    /// * `stake` - Node's stake amount
    pub fn verify_leader(
        &self,
        public_key: &[u8; 32],
        slot: u64,
        proof: &VRFProof,
        stake: u64,
    ) -> Result<bool> {
        // Check minimum stake
        if stake < self.params.min_stake {
            return Ok(false);
        }

        // Verify VRF proof
        let input = self.slot_to_input(slot);
        let output = VRF::verify(public_key, &input, proof)?;

        // Check threshold
        Ok(self.is_leader(&output, stake))
    }

    /// Check if VRF output qualifies as leader
    ///
    /// Uses 128-bit integer arithmetic to avoid precision loss.
    /// The probability of being leader is: (stake / total_stake) * base_threshold
    fn is_leader(&self, output: &VRFOutput, stake: u64) -> bool {
        output.is_below_threshold(
            stake,
            self.params.total_stake,
            self.params.base_threshold_ppm,
        )
    }

    /// Convert slot number to VRF input
    fn slot_to_input(&self, slot: u64) -> Vec<u8> {
        let mut input = Vec::with_capacity(24);
        input.extend_from_slice(b"PoT-slot-v1-");
        input.extend_from_slice(&slot.to_le_bytes());
        // Include genesis timestamp to make inputs unique per chain
        input.extend_from_slice(&GENESIS_TIMESTAMP.to_le_bytes());
        input
    }

    /// Calculate expected timestamp for a slot
    pub fn slot_timestamp(slot: u64) -> u64 {
        GENESIS_TIMESTAMP + slot
    }

    /// Calculate slot number for a timestamp
    pub fn timestamp_to_slot(timestamp: u64) -> Option<u64> {
        timestamp.checked_sub(GENESIS_TIMESTAMP)
    }

    /// Update total stake
    pub fn set_total_stake(&mut self, total_stake: u64) {
        self.params.total_stake = total_stake;
    }

    /// Get current parameters
    pub fn params(&self) -> &LeaderParams {
        &self.params
    }
}

/// Represents a leader slot assignment
#[derive(Debug, Clone)]
pub struct SlotLeader {
    /// Slot number
    pub slot: u64,

    /// Leader's public key
    pub public_key: [u8; 32],

    /// VRF output
    pub vrf_output: VRFOutput,

    /// VRF proof
    pub vrf_proof: VRFProof,

    /// Leader's stake at time of selection
    pub stake: u64,
}

impl SlotLeader {
    /// Verify this slot assignment
    pub fn verify(&self, selector: &LeaderSelector) -> Result<bool> {
        selector.verify_leader(
            &self.public_key,
            self.slot,
            &self.vrf_proof,
            self.stake,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    #[test]
    fn test_leader_selection() {
        let selector = LeaderSelector::default();
        let vrf = VRF::generate(&mut OsRng);

        // High stake should have higher probability
        let high_stake = 100_000_000; // 100M seconds

        let mut found_leader = false;
        for slot in 0..100 {
            if let Ok(Some(_)) = selector.check_leader(&vrf, slot, high_stake) {
                found_leader = true;
                break;
            }
        }

        // With 10% threshold and high stake, should find at least one leader
        assert!(found_leader, "Should find at least one leader in 100 slots");
    }

    #[test]
    fn test_low_stake_rarely_leads() {
        let selector = LeaderSelector::default();
        let vrf = VRF::generate(&mut OsRng);

        let low_stake = 1_000; // Minimum stake
        let mut leader_count = 0;

        for slot in 0..1000 {
            if let Ok(Some(_)) = selector.check_leader(&vrf, slot, low_stake) {
                leader_count += 1;
            }
        }

        // Low stake should rarely be leader
        assert!(leader_count < 10, "Low stake should rarely lead (found {})", leader_count);
    }

    #[test]
    fn test_below_min_stake() {
        let selector = LeaderSelector::default();
        let vrf = VRF::generate(&mut OsRng);

        // Below minimum stake
        let result = selector.check_leader(&vrf, 0, 100);
        assert!(result.unwrap().is_none());
    }

    #[test]
    fn test_verify_leader() {
        let selector = LeaderSelector::default();
        let vrf = VRF::generate(&mut OsRng);
        let pk = vrf.public_key_bytes();
        let stake = 500_000_000; // High stake

        // Find a slot where we're leader
        for slot in 0..1000 {
            if let Ok(Some((output, proof))) = selector.check_leader(&vrf, slot, stake) {
                // Verify the proof
                let verified = selector.verify_leader(&pk, slot, &proof, stake);
                assert!(verified.unwrap(), "Leader proof should verify");

                // Wrong slot should fail
                let wrong_slot = selector.verify_leader(&pk, slot + 1, &proof, stake);
                assert!(wrong_slot.is_err() || !wrong_slot.unwrap());

                return;
            }
        }

        panic!("Should find at least one leader slot with high stake");
    }

    #[test]
    fn test_slot_timestamp() {
        let slot = 1000;
        let ts = LeaderSelector::slot_timestamp(slot);
        assert_eq!(ts, GENESIS_TIMESTAMP + 1000);

        let back = LeaderSelector::timestamp_to_slot(ts);
        assert_eq!(back, Some(slot));
    }

    #[test]
    fn test_deterministic() {
        let vrf = VRF::generate(&mut OsRng);
        let selector = LeaderSelector::default();
        let stake = 100_000_000;

        // Same VRF key + same slot = same result
        let r1 = selector.check_leader(&vrf, 42, stake);
        let r2 = selector.check_leader(&vrf, 42, stake);

        match (r1, r2) {
            (Ok(Some((o1, _))), Ok(Some((o2, _)))) => assert_eq!(o1, o2),
            (Ok(None), Ok(None)) => {}
            _ => panic!("Results should match"),
        }
    }
}
