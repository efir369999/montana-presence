//! Cryptographic primitives for Proof of Time
//!
//! This module provides:
//! - VDF (Verifiable Delay Function) using Wesolowski's construction
//! - VRF (Verifiable Random Function) using ECVRF on Ed25519
//! - Ed25519 signatures for transactions and blocks
//! - Hash functions (SHA-256, SHA-512, BLAKE2b)

pub mod vdf;
pub mod vrf;
pub mod signatures;
pub mod hash;

pub use vdf::{VDF, VDFProof, VDFConfig};
pub use vrf::{VRF, VRFProof, VRFOutput};
pub use signatures::{Keypair, PublicKey, SecretKey, Signature};
pub use hash::{sha256, sha512, blake2b_256};
