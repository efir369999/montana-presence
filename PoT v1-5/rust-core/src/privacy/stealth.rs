//! Stealth Addresses
//!
//! Stealth addresses provide recipient privacy:
//! - Sender generates unique one-time address for each transaction
//! - Only recipient can detect and spend funds
//! - No reuse of addresses on chain
//!
//! Based on Monero's subaddress scheme (CryptoNote)

use crate::{Error, Result};
use curve25519_dalek::{
    constants::ED25519_BASEPOINT_POINT,
    edwards::{CompressedEdwardsY, EdwardsPoint},
    scalar::Scalar,
};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

/// Public address (view key + spend key)
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StealthAddress {
    /// View public key (for scanning incoming transactions)
    pub view_public: [u8; 32],
    /// Spend public key (for spending funds)
    pub spend_public: [u8; 32],
}

impl StealthAddress {
    /// Create from keys
    pub fn new(view_public: [u8; 32], spend_public: [u8; 32]) -> Self {
        Self { view_public, spend_public }
    }

    /// Create from key pair secrets
    pub fn from_secret_keys(view_secret: &[u8; 32], spend_secret: &[u8; 32]) -> Self {
        let view_scalar = Scalar::from_bytes_mod_order(*view_secret);
        let spend_scalar = Scalar::from_bytes_mod_order(*spend_secret);

        let view_public = (&view_scalar * ED25519_BASEPOINT_POINT).compress().to_bytes();
        let spend_public = (&spend_scalar * ED25519_BASEPOINT_POINT).compress().to_bytes();

        Self { view_public, spend_public }
    }

    /// Serialize to bytes (64 bytes)
    pub fn to_bytes(&self) -> [u8; 64] {
        let mut result = [0u8; 64];
        result[..32].copy_from_slice(&self.view_public);
        result[32..].copy_from_slice(&self.spend_public);
        result
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8]) -> Option<Self> {
        if bytes.len() != 64 {
            return None;
        }
        let mut view_public = [0u8; 32];
        let mut spend_public = [0u8; 32];
        view_public.copy_from_slice(&bytes[..32]);
        spend_public.copy_from_slice(&bytes[32..]);
        Some(Self { view_public, spend_public })
    }

    /// Validate keys are valid curve points
    pub fn is_valid(&self) -> bool {
        let view_ok = CompressedEdwardsY(self.view_public).decompress().is_some();
        let spend_ok = CompressedEdwardsY(self.spend_public).decompress().is_some();
        view_ok && spend_ok
    }
}

/// One-time output key
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OneTimeKey {
    /// Ephemeral public key R (included in transaction)
    pub ephemeral: [u8; 32],
    /// One-time public key P (destination key)
    pub public_key: [u8; 32],
}

impl OneTimeKey {
    /// Generate one-time key for recipient
    ///
    /// Sender generates:
    /// - Random r
    /// - R = r * G (ephemeral public key)
    /// - P = Hs(r * A) * G + B (one-time public key)
    ///
    /// Where A = view public key, B = spend public key
    pub fn generate<R: RngCore>(
        recipient: &StealthAddress,
        output_index: u64,
        rng: &mut R,
    ) -> Result<Self> {
        // Decompress view public key
        let a = CompressedEdwardsY(recipient.view_public)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid view public key".into()))?;

        let b = CompressedEdwardsY(recipient.spend_public)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid spend public key".into()))?;

        // Generate random scalar r
        let mut r_bytes = [0u8; 32];
        rng.fill_bytes(&mut r_bytes);
        let r = Scalar::from_bytes_mod_order(r_bytes);

        // R = r * G
        let r_point = &r * ED25519_BASEPOINT_POINT;
        let ephemeral = r_point.compress().to_bytes();

        // Shared secret: r * A
        let shared = &r * a;

        // Hs(shared || output_index)
        let hs = hash_to_scalar(&shared.compress().to_bytes(), output_index);

        // P = Hs * G + B
        let p = &hs * ED25519_BASEPOINT_POINT + b;
        let public_key = p.compress().to_bytes();

        Ok(Self { ephemeral, public_key })
    }

    /// Derive one-time private key (for recipient to spend)
    ///
    /// Recipient computes:
    /// - x = Hs(a * R) + b
    ///
    /// Where a = view secret key, b = spend secret key
    pub fn derive_secret_key(
        ephemeral: &[u8; 32],
        output_index: u64,
        view_secret: &[u8; 32],
        spend_secret: &[u8; 32],
    ) -> Result<[u8; 32]> {
        // Decompress ephemeral
        let r_point = CompressedEdwardsY(*ephemeral)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid ephemeral key".into()))?;

        let a = Scalar::from_bytes_mod_order(*view_secret);
        let b = Scalar::from_bytes_mod_order(*spend_secret);

        // Shared secret: a * R
        let shared = &a * r_point;

        // Hs(shared || output_index)
        let hs = hash_to_scalar(&shared.compress().to_bytes(), output_index);

        // x = Hs + b
        let x = hs + b;

        Ok(x.to_bytes())
    }

    /// Check if this output belongs to us
    ///
    /// Recipient checks:
    /// - P' = Hs(a * R) * G + B
    /// - Return P' == P
    pub fn check_ownership(
        ephemeral: &[u8; 32],
        public_key: &[u8; 32],
        output_index: u64,
        view_secret: &[u8; 32],
        spend_public: &[u8; 32],
    ) -> Result<bool> {
        // Decompress ephemeral
        let r_point = CompressedEdwardsY(*ephemeral)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid ephemeral key".into()))?;

        let b = CompressedEdwardsY(*spend_public)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid spend public key".into()))?;

        let a = Scalar::from_bytes_mod_order(*view_secret);

        // Shared secret: a * R
        let shared = &a * r_point;

        // Hs(shared || output_index)
        let hs = hash_to_scalar(&shared.compress().to_bytes(), output_index);

        // P' = Hs * G + B
        let p_expected = &hs * ED25519_BASEPOINT_POINT + b;

        Ok(p_expected.compress().to_bytes() == *public_key)
    }

    /// Serialize to bytes (64 bytes)
    pub fn to_bytes(&self) -> [u8; 64] {
        let mut result = [0u8; 64];
        result[..32].copy_from_slice(&self.ephemeral);
        result[32..].copy_from_slice(&self.public_key);
        result
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8]) -> Option<Self> {
        if bytes.len() != 64 {
            return None;
        }
        let mut ephemeral = [0u8; 32];
        let mut public_key = [0u8; 32];
        ephemeral.copy_from_slice(&bytes[..32]);
        public_key.copy_from_slice(&bytes[32..]);
        Some(Self { ephemeral, public_key })
    }
}

/// Hash to scalar: Hs(data || index)
fn hash_to_scalar(data: &[u8], index: u64) -> Scalar {
    let mut hasher = Sha256::new();
    hasher.update(b"PoT-stealth-hs-v1");
    hasher.update(data);
    hasher.update(&index.to_le_bytes());
    let hash: [u8; 32] = hasher.finalize().into();
    Scalar::from_bytes_mod_order(hash)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    fn generate_keypair() -> ([u8; 32], [u8; 32]) {
        let mut secret = [0u8; 32];
        OsRng.fill_bytes(&mut secret);
        let scalar = Scalar::from_bytes_mod_order(secret);
        let public = (&scalar * ED25519_BASEPOINT_POINT).compress().to_bytes();
        (secret, public)
    }

    #[test]
    fn test_stealth_address_creation() {
        let (view_secret, _) = generate_keypair();
        let (spend_secret, _) = generate_keypair();

        let addr = StealthAddress::from_secret_keys(&view_secret, &spend_secret);
        assert!(addr.is_valid());
    }

    #[test]
    fn test_one_time_key_generation() {
        let (view_secret, view_public) = generate_keypair();
        let (_, spend_public) = generate_keypair();

        let addr = StealthAddress::new(view_public, spend_public);
        let otk = OneTimeKey::generate(&addr, 0, &mut OsRng).unwrap();

        // Check ownership
        let is_ours = OneTimeKey::check_ownership(
            &otk.ephemeral,
            &otk.public_key,
            0,
            &view_secret,
            &spend_public,
        ).unwrap();

        assert!(is_ours);
    }

    #[test]
    fn test_wrong_recipient() {
        let (view_secret1, view_public1) = generate_keypair();
        let (_, spend_public1) = generate_keypair();
        let (view_secret2, _) = generate_keypair();
        let (_, spend_public2) = generate_keypair();

        let addr = StealthAddress::new(view_public1, spend_public1);
        let otk = OneTimeKey::generate(&addr, 0, &mut OsRng).unwrap();

        // Check with wrong keys
        let is_ours = OneTimeKey::check_ownership(
            &otk.ephemeral,
            &otk.public_key,
            0,
            &view_secret2,
            &spend_public2,
        ).unwrap();

        assert!(!is_ours);
    }

    #[test]
    fn test_derive_secret_key() {
        let (view_secret, view_public) = generate_keypair();
        let (spend_secret, spend_public) = generate_keypair();

        let addr = StealthAddress::new(view_public, spend_public);
        let otk = OneTimeKey::generate(&addr, 0, &mut OsRng).unwrap();

        // Derive secret key
        let derived = OneTimeKey::derive_secret_key(
            &otk.ephemeral,
            0,
            &view_secret,
            &spend_secret,
        ).unwrap();

        // Verify derived key matches public key
        let derived_scalar = Scalar::from_bytes_mod_order(derived);
        let derived_public = (&derived_scalar * ED25519_BASEPOINT_POINT).compress().to_bytes();

        assert_eq!(derived_public, otk.public_key);
    }

    #[test]
    fn test_different_output_indices() {
        let (_, view_public) = generate_keypair();
        let (_, spend_public) = generate_keypair();

        let addr = StealthAddress::new(view_public, spend_public);

        let otk1 = OneTimeKey::generate(&addr, 0, &mut OsRng).unwrap();
        let otk2 = OneTimeKey::generate(&addr, 1, &mut OsRng).unwrap();

        // Different indices produce different public keys
        assert_ne!(otk1.public_key, otk2.public_key);
    }

    #[test]
    fn test_serialization() {
        let (_, view_public) = generate_keypair();
        let (_, spend_public) = generate_keypair();

        let addr = StealthAddress::new(view_public, spend_public);
        let bytes = addr.to_bytes();
        let parsed = StealthAddress::from_bytes(&bytes).unwrap();

        assert_eq!(addr, parsed);
    }
}
