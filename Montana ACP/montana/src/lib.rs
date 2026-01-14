pub mod consensus;
pub mod cooldown;
pub mod crypto;
pub mod db;
pub mod engine;
pub mod finality;
pub mod fork_choice;
pub mod merkle;
pub mod net;
pub mod types;

// Consensus exports
pub use consensus::{
    GRACE_PERIOD_SECS, SLOTS_PER_TAU2, SLOT_DURATION_SECS,
    FULL_NODE_CAP_PERCENT, LIGHT_NODE_CAP_PERCENT, LIGHT_CLIENT_CAP_PERCENT,
    LOTTERY_PRECISION, in_grace_period,
};
pub use cooldown::AdaptiveCooldown;
pub use crypto::{sha3, Keypair, verify};
pub use db::Storage;
pub use net::{NetConfig, NetEvent, Network, NODE_FULL, NODE_PRESENCE};
pub use types::*;

// Phase 1 modules
pub use finality::{FinalityTracker, FinalityStatus, FinalityCheckpoint, SAFE_DEPTH, FINAL_DEPTH};
pub use fork_choice::{ForkChoice, ChainHead, ChainComparison, MAX_REORG_DEPTH};
pub use merkle::{MerkleTree, MerkleProof, ProofRequest, ProofResponse, ProofType};

// Phase 2: Engine
pub use engine::{ConsensusEngine, Config as EngineConfig, EngineAction, EngineError};
