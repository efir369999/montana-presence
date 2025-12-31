//! Chain State Management
//!
//! Tracks:
//! - Current chain tip (height, hash)
//! - Total supply (emission tracking)
//! - Difficulty (for future adjustment)
//! - UTXO set summary

use crate::{Error, Result};
use crate::constants::{GENESIS_TIMESTAMP, INITIAL_BLOCK_REWARD, HALVING_INTERVAL, MAX_SUPPLY_SECONDS};
use serde::{Deserialize, Serialize};

/// Current chain state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainState {
    /// Current tip height
    pub height: u64,

    /// Current tip hash
    pub tip_hash: [u8; 32],

    /// Total emitted supply in seconds
    pub total_supply: u64,

    /// Current difficulty
    pub difficulty: u64,

    /// Last update timestamp
    pub last_update: u64,
}

impl ChainState {
    /// Create genesis state
    pub fn genesis() -> Self {
        Self {
            height: 0,
            tip_hash: [0u8; 32],
            total_supply: 0,
            difficulty: 1,
            last_update: GENESIS_TIMESTAMP,
        }
    }

    /// Update state with new block
    pub fn apply_block(&mut self, height: u64, hash: [u8; 32], reward: u64, timestamp: u64) {
        self.height = height;
        self.tip_hash = hash;
        self.total_supply = self.total_supply.saturating_add(reward);
        self.last_update = timestamp;
    }

    /// Get current block reward for given height
    pub fn get_block_reward(height: u64) -> u64 {
        let epoch = height / HALVING_INTERVAL;
        if epoch >= 33 {
            return 0; // All supply mined
        }
        INITIAL_BLOCK_REWARD >> epoch
    }

    /// Get halving epoch for height
    pub fn get_halving_epoch(height: u64) -> u64 {
        (height / HALVING_INTERVAL) + 1
    }

    /// Get blocks until next halving
    pub fn blocks_until_halving(height: u64) -> u64 {
        HALVING_INTERVAL - (height % HALVING_INTERVAL)
    }

    /// Estimate total supply at height
    pub fn estimate_supply_at_height(height: u64) -> u64 {
        let mut supply = 0u64;
        let mut remaining_height = height;
        let mut epoch = 0u64;

        while remaining_height > 0 && epoch < 33 {
            let epoch_blocks = remaining_height.min(HALVING_INTERVAL - (height.saturating_sub(remaining_height)) % HALVING_INTERVAL);
            let reward = INITIAL_BLOCK_REWARD >> epoch;

            supply = supply.saturating_add(epoch_blocks.saturating_mul(reward));
            remaining_height = remaining_height.saturating_sub(epoch_blocks);
            epoch += 1;
        }

        supply.min(MAX_SUPPLY_SECONDS)
    }

    /// Get remaining supply
    pub fn remaining_supply(&self) -> u64 {
        MAX_SUPPLY_SECONDS.saturating_sub(self.total_supply)
    }

    /// Get emission percentage
    pub fn emission_percent(&self) -> f64 {
        (self.total_supply as f64 / MAX_SUPPLY_SECONDS as f64) * 100.0
    }

    /// Expected timestamp for height
    pub fn expected_timestamp(height: u64) -> u64 {
        GENESIS_TIMESTAMP + height
    }

    /// Check if chain is synchronized with UTC
    pub fn is_synchronized(&self, current_time: u64, tolerance: u64) -> bool {
        let expected_height = current_time.saturating_sub(GENESIS_TIMESTAMP);
        self.height.abs_diff(expected_height) <= tolerance
    }
}

/// Chain tip reference
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ChainTip {
    pub height: u64,
    pub hash: [u8; 32],
    pub timestamp: u64,
}

impl ChainTip {
    pub fn genesis() -> Self {
        Self {
            height: 0,
            hash: [0u8; 32],
            timestamp: GENESIS_TIMESTAMP,
        }
    }

    /// Calculate time since last block
    pub fn age(&self, current_time: u64) -> u64 {
        current_time.saturating_sub(self.timestamp)
    }

    /// Check if this tip is stale
    pub fn is_stale(&self, current_time: u64, max_age: u64) -> bool {
        self.age(current_time) > max_age
    }
}

/// Emission schedule info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmissionInfo {
    /// Current block reward in seconds
    pub current_reward: u64,

    /// Current halving epoch (1-33)
    pub epoch: u64,

    /// Blocks until next halving
    pub blocks_to_halving: u64,

    /// Total emitted so far
    pub total_emitted: u64,

    /// Remaining to emit
    pub remaining: u64,

    /// Emission percentage
    pub percent: f64,
}

impl EmissionInfo {
    /// Calculate emission info for height
    pub fn at_height(height: u64, current_supply: u64) -> Self {
        Self {
            current_reward: ChainState::get_block_reward(height),
            epoch: ChainState::get_halving_epoch(height),
            blocks_to_halving: ChainState::blocks_until_halving(height),
            total_emitted: current_supply,
            remaining: MAX_SUPPLY_SECONDS.saturating_sub(current_supply),
            percent: (current_supply as f64 / MAX_SUPPLY_SECONDS as f64) * 100.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_block_reward() {
        // Initial reward: 3000 seconds (50 minutes)
        assert_eq!(ChainState::get_block_reward(0), 3000);
        assert_eq!(ChainState::get_block_reward(1), 3000);

        // After first halving
        assert_eq!(ChainState::get_block_reward(HALVING_INTERVAL), 1500);

        // After second halving
        assert_eq!(ChainState::get_block_reward(2 * HALVING_INTERVAL), 750);

        // After 33 halvings - zero
        assert_eq!(ChainState::get_block_reward(33 * HALVING_INTERVAL), 0);
    }

    #[test]
    fn test_halving_epoch() {
        assert_eq!(ChainState::get_halving_epoch(0), 1);
        assert_eq!(ChainState::get_halving_epoch(HALVING_INTERVAL - 1), 1);
        assert_eq!(ChainState::get_halving_epoch(HALVING_INTERVAL), 2);
        assert_eq!(ChainState::get_halving_epoch(2 * HALVING_INTERVAL), 3);
    }

    #[test]
    fn test_blocks_until_halving() {
        assert_eq!(ChainState::blocks_until_halving(0), HALVING_INTERVAL);
        assert_eq!(ChainState::blocks_until_halving(1), HALVING_INTERVAL - 1);
        assert_eq!(ChainState::blocks_until_halving(HALVING_INTERVAL), HALVING_INTERVAL);
    }

    #[test]
    fn test_chain_state_apply() {
        let mut state = ChainState::genesis();
        assert_eq!(state.height, 0);
        assert_eq!(state.total_supply, 0);

        state.apply_block(1, [1u8; 32], 3000, GENESIS_TIMESTAMP + 1);
        assert_eq!(state.height, 1);
        assert_eq!(state.total_supply, 3000);

        state.apply_block(2, [2u8; 32], 3000, GENESIS_TIMESTAMP + 2);
        assert_eq!(state.height, 2);
        assert_eq!(state.total_supply, 6000);
    }

    #[test]
    fn test_synchronization_check() {
        let mut state = ChainState::genesis();
        state.height = 1000;

        let current_time = GENESIS_TIMESTAMP + 1000;
        assert!(state.is_synchronized(current_time, 5));

        let current_time = GENESIS_TIMESTAMP + 1100;
        assert!(!state.is_synchronized(current_time, 5)); // 100 blocks behind
    }

    #[test]
    fn test_emission_info() {
        let info = EmissionInfo::at_height(0, 0);
        assert_eq!(info.current_reward, 3000);
        assert_eq!(info.epoch, 1);
        assert_eq!(info.remaining, MAX_SUPPLY_SECONDS);
        assert!((info.percent - 0.0).abs() < 0.001);
    }
}
