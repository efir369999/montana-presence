//! Consensus Module
//!
//! Implements Proof of Time consensus:
//! - PoH (Proof of History): 1 block per second
//! - PoT (Proof of Time): VDF checkpoint every 600 blocks
//! - Leader selection via VRF
//! - Block validation

pub mod leader;
pub mod validator;
pub mod chain;

pub use leader::LeaderSelector;
pub use validator::BlockValidator;
pub use chain::ChainState;
