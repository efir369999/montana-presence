//! Privacy Module for PoT Blockchain
//!
//! Implements Monero-style privacy features:
//! - LSAG Ring Signatures (Linkable Spontaneous Anonymous Group)
//! - Stealth Addresses (one-time keys for each transaction)
//! - Pedersen Commitments (hiding amounts)
//! - Bulletproofs (compact range proofs) [optional]

pub mod ring;
pub mod stealth;
pub mod pedersen;

pub use ring::{RingSignature, LSAG};
pub use stealth::StealthAddress;
pub use pedersen::PedersenCommitment;
