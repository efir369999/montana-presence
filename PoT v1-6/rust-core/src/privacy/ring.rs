//! LSAG Ring Signatures
//!
//! Linkable Spontaneous Anonymous Group signatures allow:
//! - Spending funds without revealing which output is being spent
//! - Preventing double-spends via key images (linkability)
//! - Verification without knowing the real signer
//!
//! Based on Monero's implementation (mlsag.cpp)

use crate::{Error, Result};
use crate::crypto::hash::sha256;
use curve25519_dalek::{
    constants::ED25519_BASEPOINT_POINT,
    edwards::{CompressedEdwardsY, EdwardsPoint},
    scalar::Scalar,
};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

/// Key image for double-spend prevention
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct KeyImage(pub [u8; 32]);

impl KeyImage {
    /// Compute key image from private key: I = x * Hp(P)
    pub fn compute(secret_key: &Scalar, public_key: &EdwardsPoint) -> Self {
        let hp = hash_to_point(&public_key.compress().to_bytes());
        let image = secret_key * hp;
        Self(image.compress().to_bytes())
    }

    /// Check if key image is valid (on curve and in subgroup)
    pub fn is_valid(&self) -> bool {
        let compressed = CompressedEdwardsY(self.0);
        if let Some(point) = compressed.decompress() {
            // Check subgroup membership
            !point.is_small_order()
        } else {
            false
        }
    }
}

/// Ring signature (LSAG)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RingSignature {
    /// Ring size
    pub ring_size: usize,

    /// Key image
    pub key_image: KeyImage,

    /// Signature components (c, s_0, s_1, ..., s_{n-1})
    pub c: [u8; 32],
    pub s: Vec<[u8; 32]>,
}

impl RingSignature {
    /// Serialize to bytes
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(64 + self.s.len() * 32);
        buf.extend_from_slice(&self.key_image.0);
        buf.extend_from_slice(&self.c);
        for s_i in &self.s {
            buf.extend_from_slice(s_i);
        }
        buf
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8], ring_size: usize) -> Option<Self> {
        let expected_len = 64 + ring_size * 32;
        if bytes.len() != expected_len {
            return None;
        }

        let mut key_image = [0u8; 32];
        let mut c = [0u8; 32];
        key_image.copy_from_slice(&bytes[..32]);
        c.copy_from_slice(&bytes[32..64]);

        let mut s = Vec::with_capacity(ring_size);
        for i in 0..ring_size {
            let mut s_i = [0u8; 32];
            s_i.copy_from_slice(&bytes[64 + i * 32..64 + (i + 1) * 32]);
            s.push(s_i);
        }

        Some(Self {
            ring_size,
            key_image: KeyImage(key_image),
            c,
            s,
        })
    }
}

/// LSAG implementation
pub struct LSAG;

impl LSAG {
    /// Sign a message with ring signature
    ///
    /// # Arguments
    /// * `message` - Message to sign
    /// * `ring` - Public keys in the ring
    /// * `secret_key` - Signer's secret key
    /// * `secret_index` - Index of signer in the ring
    pub fn sign<R: RngCore>(
        message: &[u8],
        ring: &[[u8; 32]],
        secret_key: &[u8; 32],
        secret_index: usize,
        rng: &mut R,
    ) -> Result<RingSignature> {
        let n = ring.len();
        if n < 2 {
            return Err(Error::InvalidInput("Ring size must be at least 2".into()));
        }
        if secret_index >= n {
            return Err(Error::InvalidInput("Secret index out of range".into()));
        }

        // Parse secret key
        let x = Scalar::from_bytes_mod_order(*secret_key);

        // Decompress ring members
        let mut pk_points = Vec::with_capacity(n);
        for pk_bytes in ring {
            let compressed = CompressedEdwardsY(*pk_bytes);
            let point = compressed.decompress()
                .ok_or_else(|| Error::Crypto("Invalid public key in ring".into()))?;
            pk_points.push(point);
        }

        // Compute key image: I = x * Hp(P)
        let key_image = KeyImage::compute(&x, &pk_points[secret_index]);

        // Decompress key image for computation
        let i_point = CompressedEdwardsY(key_image.0).decompress()
            .ok_or_else(|| Error::Crypto("Failed to decompress key image".into()))?;

        // Generate random scalar for real signer
        let mut alpha_bytes = [0u8; 32];
        rng.fill_bytes(&mut alpha_bytes);
        let alpha = Scalar::from_bytes_mod_order(alpha_bytes);

        // Compute L and R for real signer
        let l_real = &alpha * ED25519_BASEPOINT_POINT;
        let hp_real = hash_to_point(&ring[secret_index]);
        let r_real = &alpha * hp_real;

        // Initialize arrays
        let mut c = vec![[0u8; 32]; n];
        let mut s = vec![[0u8; 32]; n];

        // Random s values for decoys
        for i in 0..n {
            if i != secret_index {
                let mut s_bytes = [0u8; 32];
                rng.fill_bytes(&mut s_bytes);
                s[i] = s_bytes;
            }
        }

        // Start at secret_index + 1
        let mut idx = (secret_index + 1) % n;

        // Compute c_{secret_index + 1}
        c[idx] = hash_ring(message, &l_real, &r_real);

        // Loop through ring
        while idx != secret_index {
            let s_i = Scalar::from_bytes_mod_order(s[idx]);
            let c_i = Scalar::from_bytes_mod_order(c[idx]);

            // L_i = s_i * G + c_i * P_i
            let l_i = &s_i * ED25519_BASEPOINT_POINT + &c_i * pk_points[idx];

            // R_i = s_i * Hp(P_i) + c_i * I
            let hp_i = hash_to_point(&ring[idx]);
            let r_i = &s_i * hp_i + &c_i * i_point;

            // c_{i+1} = H(m, L_i, R_i)
            let next_idx = (idx + 1) % n;
            c[next_idx] = hash_ring(message, &l_i, &r_i);

            idx = next_idx;
        }

        // Close the ring: s_real = alpha - c_real * x
        let c_real = Scalar::from_bytes_mod_order(c[secret_index]);
        let s_real = alpha - c_real * x;
        s[secret_index] = s_real.to_bytes();

        Ok(RingSignature {
            ring_size: n,
            key_image,
            c: c[0], // Return c_0
            s,
        })
    }

    /// Verify ring signature
    pub fn verify(
        message: &[u8],
        ring: &[[u8; 32]],
        signature: &RingSignature,
    ) -> Result<bool> {
        let n = ring.len();
        if n != signature.ring_size {
            return Err(Error::InvalidInput("Ring size mismatch".into()));
        }
        if n < 2 {
            return Err(Error::InvalidInput("Ring size must be at least 2".into()));
        }

        // Check key image validity
        if !signature.key_image.is_valid() {
            return Ok(false);
        }

        // Decompress ring members
        let mut pk_points = Vec::with_capacity(n);
        for pk_bytes in ring {
            let compressed = CompressedEdwardsY(*pk_bytes);
            let point = compressed.decompress()
                .ok_or_else(|| Error::Crypto("Invalid public key in ring".into()))?;
            pk_points.push(point);
        }

        // Decompress key image
        let i_point = CompressedEdwardsY(signature.key_image.0).decompress()
            .ok_or_else(|| Error::Crypto("Failed to decompress key image".into()))?;

        // Verify ring: recompute all c values and check c_0 matches
        let mut c_current = signature.c;

        for i in 0..n {
            let s_i = Scalar::from_bytes_mod_order(signature.s[i]);
            let c_i = Scalar::from_bytes_mod_order(c_current);

            // L_i = s_i * G + c_i * P_i
            let l_i = &s_i * ED25519_BASEPOINT_POINT + &c_i * pk_points[i];

            // R_i = s_i * Hp(P_i) + c_i * I
            let hp_i = hash_to_point(&ring[i]);
            let r_i = &s_i * hp_i + &c_i * i_point;

            // c_{i+1} = H(m, L_i, R_i)
            c_current = hash_ring(message, &l_i, &r_i);
        }

        // Check c_0 matches
        Ok(c_current == signature.c)
    }
}

/// Hash to curve point (Hp function)
fn hash_to_point(data: &[u8]) -> EdwardsPoint {
    let mut hasher = Sha256::new();
    hasher.update(b"PoT-LSAG-Hp-v1");
    hasher.update(data);
    let hash: [u8; 32] = hasher.finalize().into();

    // Try to find valid point (rejection sampling)
    let mut bytes = hash;
    for i in 0..256u8 {
        bytes[0] = bytes[0].wrapping_add(i);
        let compressed = CompressedEdwardsY(bytes);
        if let Some(point) = compressed.decompress() {
            // Clear cofactor
            let cleared = point.mul_by_cofactor();
            if !cleared.is_identity() {
                return cleared;
            }
        }
    }

    // Fallback (should never happen with random input)
    ED25519_BASEPOINT_POINT
}

/// Hash for ring signature
fn hash_ring(message: &[u8], l: &EdwardsPoint, r: &EdwardsPoint) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"PoT-LSAG-hash-v1");
    hasher.update(message);
    hasher.update(l.compress().as_bytes());
    hasher.update(r.compress().as_bytes());
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;
    use crate::crypto::signatures::Keypair;

    fn generate_ring(size: usize) -> (Vec<[u8; 32]>, usize, [u8; 32]) {
        let mut ring = Vec::with_capacity(size);
        let secret_index = size / 2;

        for _ in 0..size {
            let kp = Keypair::generate(&mut OsRng);
            ring.push(*kp.public_key().as_bytes());
        }

        let real_kp = Keypair::generate(&mut OsRng);
        ring[secret_index] = *real_kp.public_key().as_bytes();

        (ring, secret_index, *real_kp.secret_key().as_bytes())
    }

    #[test]
    fn test_lsag_sign_verify() {
        let (ring, secret_index, secret_key) = generate_ring(4);
        let message = b"test message";

        let sig = LSAG::sign(message, &ring, &secret_key, secret_index, &mut OsRng).unwrap();
        assert!(LSAG::verify(message, &ring, &sig).unwrap());
    }

    #[test]
    fn test_lsag_wrong_message() {
        let (ring, secret_index, secret_key) = generate_ring(4);

        let sig = LSAG::sign(b"message 1", &ring, &secret_key, secret_index, &mut OsRng).unwrap();
        assert!(!LSAG::verify(b"message 2", &ring, &sig).unwrap());
    }

    #[test]
    fn test_lsag_key_image_unique() {
        let (ring, secret_index, secret_key) = generate_ring(4);
        let message = b"test";

        let sig1 = LSAG::sign(message, &ring, &secret_key, secret_index, &mut OsRng).unwrap();
        let sig2 = LSAG::sign(message, &ring, &secret_key, secret_index, &mut OsRng).unwrap();

        // Same key image for same signer
        assert_eq!(sig1.key_image, sig2.key_image);
    }

    #[test]
    fn test_lsag_different_signers() {
        let (ring1, secret_index1, secret_key1) = generate_ring(4);
        let (ring2, secret_index2, secret_key2) = generate_ring(4);
        let message = b"test";

        let sig1 = LSAG::sign(message, &ring1, &secret_key1, secret_index1, &mut OsRng).unwrap();
        let sig2 = LSAG::sign(message, &ring2, &secret_key2, secret_index2, &mut OsRng).unwrap();

        // Different key images for different signers
        assert_ne!(sig1.key_image, sig2.key_image);
    }

    #[test]
    fn test_lsag_ring_size_16() {
        let (ring, secret_index, secret_key) = generate_ring(16);
        let message = b"large ring test";

        let sig = LSAG::sign(message, &ring, &secret_key, secret_index, &mut OsRng).unwrap();
        assert!(LSAG::verify(message, &ring, &sig).unwrap());
    }

    #[test]
    fn test_key_image_valid() {
        let kp = Keypair::generate(&mut OsRng);
        let sk = Scalar::from_bytes_mod_order(*kp.secret_key().as_bytes());
        let pk_bytes = kp.public_key().as_bytes();
        let pk = CompressedEdwardsY(*pk_bytes).decompress().unwrap();

        let ki = KeyImage::compute(&sk, &pk);
        assert!(ki.is_valid());
    }

    #[test]
    fn test_serialization() {
        let (ring, secret_index, secret_key) = generate_ring(4);
        let sig = LSAG::sign(b"test", &ring, &secret_key, secret_index, &mut OsRng).unwrap();

        let bytes = sig.to_bytes();
        let parsed = RingSignature::from_bytes(&bytes, 4).unwrap();

        assert_eq!(sig.key_image, parsed.key_image);
        assert_eq!(sig.c, parsed.c);
        assert_eq!(sig.s, parsed.s);
    }
}
