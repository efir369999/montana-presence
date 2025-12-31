//! Proof of Time - Core Library
//!
//! High-performance cryptographic and consensus modules for the PoT blockchain.
//!
//! ## Modules
//!
//! - `crypto`: VDF (Wesolowski), VRF (ECVRF), Ed25519 signatures
//! - `consensus`: Leader selection, block validation, chain state
//! - `structures`: Block, Transaction, Header serialization
//! - `network`: P2P networking with Noise Protocol XX
//! - `privacy`: LSAG ring signatures, Pedersen commitments, stealth addresses
//!
//! ## Design Philosophy
//!
//! - **Memory Safety**: Rust's ownership model prevents use-after-free, buffer overflows
//! - **Constant-Time**: All cryptographic operations are constant-time to prevent timing attacks
//! - **Zero-Copy**: Efficient serialization with minimal allocations
//! - **Deterministic**: No floating-point in consensus-critical paths

pub mod crypto;
pub mod consensus;
pub mod structures;
pub mod network;
pub mod privacy;

// Re-exports for convenience
pub use crypto::{
    vdf::{VDF, VDFProof, VDFConfig},
    vrf::{VRF, VRFProof, VRFOutput},
    signatures::{Keypair, PublicKey, SecretKey, Signature},
};

pub use consensus::{
    leader::LeaderSelector,
    validator::BlockValidator,
};

pub use structures::{
    block::{Block, BlockHeader},
    transaction::{Transaction, TxInput, TxOutput},
    types::{Hash256, Timestamp, Height},
};

pub use privacy::{
    ring::{RingSignature, LSAG},
    stealth::StealthAddress,
    pedersen::PedersenCommitment,
};

/// Protocol constants
pub mod constants {
    /// Genesis timestamp: 2025-12-25 00:00:00 UTC
    pub const GENESIS_TIMESTAMP: u64 = 1735084800;

    /// Blocks per PoT checkpoint
    pub const POT_CHECKPOINT_INTERVAL: u64 = 600;

    /// VDF iterations per checkpoint (10 minutes at ~100k iter/sec)
    pub const VDF_ITERATIONS: u64 = 60_000_000;

    /// Maximum block size in bytes
    pub const MAX_BLOCK_SIZE: usize = 32 * 1024 * 1024; // 32 MB

    /// Ring signature size
    pub const DEFAULT_RING_SIZE: usize = 16;
    pub const MIN_RING_SIZE: usize = 2;
    pub const MAX_RING_SIZE: usize = 1024;

    /// Initial block reward in seconds (50 minutes = 3000 seconds)
    pub const INITIAL_BLOCK_REWARD: u64 = 3000;

    /// Halving interval in blocks (~4 years at 1 block/sec)
    pub const HALVING_INTERVAL: u64 = 126_144_000;

    /// Maximum supply in seconds (21M minutes)
    pub const MAX_SUPPLY_SECONDS: u64 = 1_260_000_000;

    /// Protocol version
    pub const PROTOCOL_VERSION: u32 = 1;
}

/// Error types
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Cryptographic error: {0}")]
    Crypto(String),

    #[error("Consensus error: {0}")]
    Consensus(String),

    #[error("Serialization error: {0}")]
    Serialization(String),

    #[error("Network error: {0}")]
    Network(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Database error: {0}")]
    Database(String),

    #[error("Invalid input: {0}")]
    InvalidInput(String),
}

pub type Result<T> = std::result::Result<T, Error>;

#[cfg(feature = "python")]
mod python;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pymodule]
fn pot_core(_py: Python, m: &PyModule) -> PyResult<()> {
    python::register_module(m)?;
    Ok(())
}
