//! Common Types for PoT Blockchain

use serde::{Deserialize, Serialize};
use std::fmt;

/// 256-bit hash (32 bytes)
#[derive(Clone, Copy, PartialEq, Eq, Hash, Default, Serialize, Deserialize)]
pub struct Hash256(pub [u8; 32]);

impl Hash256 {
    /// Zero hash
    pub const ZERO: Self = Self([0u8; 32]);

    /// Create from bytes
    pub fn from_bytes(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    /// Try to create from slice
    pub fn try_from_slice(slice: &[u8]) -> Option<Self> {
        if slice.len() != 32 {
            return None;
        }
        let mut bytes = [0u8; 32];
        bytes.copy_from_slice(slice);
        Some(Self(bytes))
    }

    /// Get as bytes
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Check if zero
    pub fn is_zero(&self) -> bool {
        self.0 == [0u8; 32]
    }

    /// Convert to hex string
    pub fn to_hex(&self) -> String {
        hex::encode(&self.0)
    }

    /// Parse from hex string
    pub fn from_hex(s: &str) -> Option<Self> {
        let bytes = hex::decode(s).ok()?;
        Self::try_from_slice(&bytes)
    }
}

impl fmt::Debug for Hash256 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Hash256({})", &hex::encode(&self.0[..8]))
    }
}

impl fmt::Display for Hash256 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}...{}", &hex::encode(&self.0[..4]), &hex::encode(&self.0[28..]))
    }
}

impl AsRef<[u8]> for Hash256 {
    fn as_ref(&self) -> &[u8] {
        &self.0
    }
}

impl From<[u8; 32]> for Hash256 {
    fn from(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }
}

impl From<Hash256> for [u8; 32] {
    fn from(hash: Hash256) -> Self {
        hash.0
    }
}

/// Block timestamp (Unix epoch seconds)
pub type Timestamp = u64;

/// Block height
pub type Height = u64;

/// Amount in seconds (atomic unit)
pub type Amount = u64;

/// Key image (for double-spend prevention)
#[derive(Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct KeyImage(pub [u8; 32]);

impl KeyImage {
    pub fn from_bytes(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    pub fn to_hex(&self) -> String {
        hex::encode(&self.0)
    }
}

impl fmt::Debug for KeyImage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "KeyImage({})", &hex::encode(&self.0[..8]))
    }
}

/// Public key for stealth address
#[derive(Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct StealthPubKey {
    /// Ephemeral public key R
    pub ephemeral: [u8; 32],
    /// One-time public key P
    pub one_time: [u8; 32],
}

impl StealthPubKey {
    pub fn new(ephemeral: [u8; 32], one_time: [u8; 32]) -> Self {
        Self { ephemeral, one_time }
    }

    pub fn to_bytes(&self) -> [u8; 64] {
        let mut result = [0u8; 64];
        result[..32].copy_from_slice(&self.ephemeral);
        result[32..].copy_from_slice(&self.one_time);
        result
    }

    pub fn from_bytes(bytes: &[u8; 64]) -> Self {
        let mut ephemeral = [0u8; 32];
        let mut one_time = [0u8; 32];
        ephemeral.copy_from_slice(&bytes[..32]);
        one_time.copy_from_slice(&bytes[32..]);
        Self { ephemeral, one_time }
    }
}

impl fmt::Debug for StealthPubKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("StealthPubKey")
            .field("ephemeral", &hex::encode(&self.ephemeral[..8]))
            .field("one_time", &hex::encode(&self.one_time[..8]))
            .finish()
    }
}

/// Pedersen commitment
#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Commitment(pub [u8; 32]);

impl Commitment {
    pub fn from_bytes(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    pub fn to_hex(&self) -> String {
        hex::encode(&self.0)
    }
}

impl fmt::Debug for Commitment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Commitment({})", &hex::encode(&self.0[..8]))
    }
}

/// VRF proof for leader selection
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VrfProofData {
    /// VRF output (32 bytes)
    pub output: [u8; 32],
    /// VRF proof (96 bytes)
    pub proof: [u8; 96],
}

impl VrfProofData {
    pub fn new(output: [u8; 32], proof: [u8; 96]) -> Self {
        Self { output, proof }
    }

    pub fn to_bytes(&self) -> [u8; 128] {
        let mut result = [0u8; 128];
        result[..32].copy_from_slice(&self.output);
        result[32..].copy_from_slice(&self.proof);
        result
    }

    pub fn from_bytes(bytes: &[u8; 128]) -> Self {
        let mut output = [0u8; 32];
        let mut proof = [0u8; 96];
        output.copy_from_slice(&bytes[..32]);
        proof.copy_from_slice(&bytes[32..]);
        Self { output, proof }
    }
}

impl fmt::Debug for VrfProofData {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("VrfProofData")
            .field("output", &hex::encode(&self.output[..8]))
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash256_hex() {
        let hash = Hash256([0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0,
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]);

        let hex = hash.to_hex();
        let parsed = Hash256::from_hex(&hex).unwrap();
        assert_eq!(hash, parsed);
    }

    #[test]
    fn test_hash256_zero() {
        assert!(Hash256::ZERO.is_zero());
        assert!(!Hash256([1u8; 32]).is_zero());
    }

    #[test]
    fn test_stealth_pubkey() {
        let spk = StealthPubKey::new([1u8; 32], [2u8; 32]);
        let bytes = spk.to_bytes();
        let parsed = StealthPubKey::from_bytes(&bytes);
        assert_eq!(spk, parsed);
    }
}
