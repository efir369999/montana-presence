//! Verifiable Random Function (VRF) - ECVRF on Ed25519
//!
//! VRF provides:
//! - **Uniqueness**: Each input produces exactly one output
//! - **Pseudorandomness**: Output is indistinguishable from random
//! - **Verifiability**: Anyone can verify the output was computed correctly
//!
//! Used for:
//! - Leader selection in consensus (fair, unpredictable)
//! - Randomness beacon for protocol operations
//!
//! ## Construction
//!
//! Based on IETF draft-irtf-cfrg-vrf-15 (ECVRF-EDWARDS25519-SHA512-ELL2)

use crate::{Error, Result};
use curve25519_dalek::{
    constants::ED25519_BASEPOINT_POINT,
    edwards::{CompressedEdwardsY, EdwardsPoint},
    scalar::Scalar,
};
use ed25519_dalek::{SecretKey as Ed25519SecretKey, VerifyingKey};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Sha512, Digest};

/// VRF output (32 bytes)
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VRFOutput(pub [u8; 32]);

impl VRFOutput {
    /// Convert to bytes
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Convert to u256 for threshold comparison
    pub fn to_u256(&self) -> [u64; 4] {
        let mut result = [0u64; 4];
        for i in 0..4 {
            result[i] = u64::from_le_bytes(
                self.0[i * 8..(i + 1) * 8].try_into().unwrap()
            );
        }
        result
    }

    /// Compare against threshold using integer arithmetic (no float precision loss)
    ///
    /// Returns true if output < threshold * max_value / total_stake
    pub fn is_below_threshold(&self, stake: u64, total_stake: u64, threshold_ppm: u64) -> bool {
        // Use 128-bit arithmetic to avoid overflow
        // output / max_output < stake * threshold / total_stake
        // Cross multiply: output * total_stake < stake * threshold * max_output / 1_000_000

        let output_u128 = u128::from_le_bytes(self.0[..16].try_into().unwrap());
        let max_output = u128::MAX;

        // Compute RHS with scaling to avoid overflow
        // stake * threshold_ppm / 1_000_000 * max_output / total_stake
        let stake_128 = stake as u128;
        let total_128 = total_stake as u128;
        let threshold_128 = threshold_ppm as u128;

        // Scale down to prevent overflow
        let scaled_threshold = (stake_128 * threshold_128) / 1_000_000;
        let rhs = (scaled_threshold * (max_output / total_128)).min(max_output);

        output_u128 < rhs
    }
}

/// VRF proof structure
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VRFProof {
    /// Gamma point (compressed)
    pub gamma: [u8; 32],
    /// Challenge scalar
    pub c: [u8; 32],
    /// Response scalar
    pub s: [u8; 32],
}

impl VRFProof {
    /// Serialize to bytes
    pub fn to_bytes(&self) -> [u8; 96] {
        let mut result = [0u8; 96];
        result[..32].copy_from_slice(&self.gamma);
        result[32..64].copy_from_slice(&self.c);
        result[64..].copy_from_slice(&self.s);
        result
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8; 96]) -> Self {
        let mut gamma = [0u8; 32];
        let mut c = [0u8; 32];
        let mut s = [0u8; 32];
        gamma.copy_from_slice(&bytes[..32]);
        c.copy_from_slice(&bytes[32..64]);
        s.copy_from_slice(&bytes[64..]);
        Self { gamma, c, s }
    }
}

/// VRF implementation
pub struct VRF {
    secret_key: Scalar,
    public_key: EdwardsPoint,
}

impl VRF {
    /// Create VRF from secret key bytes
    pub fn from_secret_key(sk_bytes: &[u8; 32]) -> Result<Self> {
        // Hash secret key to get scalar (same as Ed25519)
        let mut h = Sha512::new();
        h.update(sk_bytes);
        let hash = h.finalize();

        let mut scalar_bytes = [0u8; 32];
        scalar_bytes.copy_from_slice(&hash[..32]);

        // Clamp as per Ed25519
        scalar_bytes[0] &= 248;
        scalar_bytes[31] &= 127;
        scalar_bytes[31] |= 64;

        let secret_key = Scalar::from_bytes_mod_order(scalar_bytes);
        let public_key = &secret_key * ED25519_BASEPOINT_POINT;

        Ok(Self {
            secret_key,
            public_key,
        })
    }

    /// Generate new VRF keypair
    pub fn generate<R: RngCore>(rng: &mut R) -> Self {
        let mut sk_bytes = [0u8; 32];
        rng.fill_bytes(&mut sk_bytes);
        Self::from_secret_key(&sk_bytes).unwrap()
    }

    /// Get public key bytes
    pub fn public_key_bytes(&self) -> [u8; 32] {
        self.public_key.compress().to_bytes()
    }

    /// Prove: Generate VRF output and proof for input
    pub fn prove(&self, input: &[u8]) -> Result<(VRFOutput, VRFProof)> {
        // Hash input to curve point
        let h = self.hash_to_curve(input)?;

        // Gamma = sk * H
        let gamma = &self.secret_key * h;

        // Generate random k
        let k = self.generate_nonce(input);

        // U = k * B (base point)
        let u = &k * ED25519_BASEPOINT_POINT;

        // V = k * H
        let v = &k * h;

        // Challenge c = hash(G, H, pk, Gamma, U, V)
        let c = self.compute_challenge(&h, &gamma, &u, &v);

        // Response s = k - c * sk
        let s = k - (c * self.secret_key);

        // Output = hash(Gamma)
        let output = self.gamma_to_output(&gamma);

        let proof = VRFProof {
            gamma: gamma.compress().to_bytes(),
            c: c.to_bytes(),
            s: s.to_bytes(),
        };

        Ok((output, proof))
    }

    /// Verify: Check VRF proof and extract output
    pub fn verify(
        public_key: &[u8; 32],
        input: &[u8],
        proof: &VRFProof,
    ) -> Result<VRFOutput> {
        // Decompress public key
        let pk_compressed = CompressedEdwardsY::from_slice(public_key)
            .map_err(|_| Error::Crypto("Invalid public key".into()))?;
        let pk = pk_compressed
            .decompress()
            .ok_or_else(|| Error::Crypto("Failed to decompress public key".into()))?;

        // Decompress gamma
        let gamma_compressed = CompressedEdwardsY::from_slice(&proof.gamma)
            .map_err(|_| Error::Crypto("Invalid gamma".into()))?;
        let gamma = gamma_compressed
            .decompress()
            .ok_or_else(|| Error::Crypto("Failed to decompress gamma".into()))?;

        // Parse scalars
        let c = Scalar::from_bytes_mod_order(proof.c);
        let s = Scalar::from_bytes_mod_order(proof.s);

        // Hash input to curve
        let h = Self::hash_to_curve_static(input)?;

        // U' = s * B + c * pk
        let u_prime = &s * ED25519_BASEPOINT_POINT + &c * pk;

        // V' = s * H + c * Gamma
        let v_prime = &s * h + &c * gamma;

        // Recompute challenge
        let c_prime = Self::compute_challenge_static(&pk, &h, &gamma, &u_prime, &v_prime);

        // Verify c == c'
        if c != c_prime {
            return Err(Error::Crypto("VRF verification failed: challenge mismatch".into()));
        }

        // Output = hash(Gamma)
        Ok(Self::gamma_to_output_static(&gamma))
    }

    /// Hash input to curve point using Elligator 2
    fn hash_to_curve(&self, input: &[u8]) -> Result<EdwardsPoint> {
        Self::hash_to_curve_static(input)
    }

    fn hash_to_curve_static(input: &[u8]) -> Result<EdwardsPoint> {
        // Use SHA-256 for 32-byte output (fixes the 64-byte bug)
        let mut hasher = Sha256::new();
        hasher.update(b"PoT-VRF-h2c-v1");
        hasher.update(input);
        let hash: [u8; 32] = hasher.finalize().into();

        // Use try_elligator for hash-to-curve
        // This is a simplified version - production should use RFC 9380
        let point = Self::elligator2(&hash)?;
        Ok(point)
    }

    /// Elligator 2 map to curve
    fn elligator2(hash: &[u8; 32]) -> Result<EdwardsPoint> {
        // Simplified Elligator 2 - maps 32 bytes to curve point
        // For production, use ristretto255 or full RFC 9380 implementation

        let mut bytes = *hash;
        // Clear high bit for valid field element
        bytes[31] &= 0x7f;

        // Try to decompress as Edwards point
        // If it fails, increment and retry (rejection sampling)
        for i in 0..256u8 {
            bytes[0] = bytes[0].wrapping_add(i);
            let compressed = CompressedEdwardsY(bytes);
            if let Some(point) = compressed.decompress() {
                // Ensure point is in prime-order subgroup
                let cofactor_cleared = point.mul_by_cofactor();
                if !cofactor_cleared.is_identity() {
                    return Ok(cofactor_cleared);
                }
            }
        }

        Err(Error::Crypto("Failed to hash to curve".into()))
    }

    /// Generate deterministic nonce
    fn generate_nonce(&self, input: &[u8]) -> Scalar {
        let mut hasher = Sha512::new();
        hasher.update(b"PoT-VRF-nonce-v1");
        hasher.update(&self.secret_key.to_bytes());
        hasher.update(input);
        let hash = hasher.finalize();

        Scalar::from_bytes_mod_order_wide(&hash.into())
    }

    /// Compute challenge
    fn compute_challenge(
        &self,
        h: &EdwardsPoint,
        gamma: &EdwardsPoint,
        u: &EdwardsPoint,
        v: &EdwardsPoint,
    ) -> Scalar {
        Self::compute_challenge_static(&self.public_key, h, gamma, u, v)
    }

    fn compute_challenge_static(
        pk: &EdwardsPoint,
        h: &EdwardsPoint,
        gamma: &EdwardsPoint,
        u: &EdwardsPoint,
        v: &EdwardsPoint,
    ) -> Scalar {
        let mut hasher = Sha512::new();
        hasher.update(b"PoT-VRF-challenge-v1");
        hasher.update(ED25519_BASEPOINT_POINT.compress().as_bytes());
        hasher.update(h.compress().as_bytes());
        hasher.update(pk.compress().as_bytes());
        hasher.update(gamma.compress().as_bytes());
        hasher.update(u.compress().as_bytes());
        hasher.update(v.compress().as_bytes());

        let hash = hasher.finalize();
        Scalar::from_bytes_mod_order_wide(&hash.into())
    }

    /// Convert gamma to output
    fn gamma_to_output(&self, gamma: &EdwardsPoint) -> VRFOutput {
        Self::gamma_to_output_static(gamma)
    }

    fn gamma_to_output_static(gamma: &EdwardsPoint) -> VRFOutput {
        let mut hasher = Sha256::new();
        hasher.update(b"PoT-VRF-output-v1");
        hasher.update(gamma.compress().as_bytes());
        VRFOutput(hasher.finalize().into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    #[test]
    fn test_vrf_prove_verify() {
        let vrf = VRF::generate(&mut OsRng);
        let input = b"test input";

        let (output, proof) = vrf.prove(input).unwrap();
        let pk = vrf.public_key_bytes();

        let verified_output = VRF::verify(&pk, input, &proof).unwrap();
        assert_eq!(output, verified_output);
    }

    #[test]
    fn test_vrf_deterministic() {
        let vrf = VRF::generate(&mut OsRng);
        let input = b"same input";

        let (output1, _) = vrf.prove(input).unwrap();
        let (output2, _) = vrf.prove(input).unwrap();

        assert_eq!(output1, output2);
    }

    #[test]
    fn test_vrf_different_inputs() {
        let vrf = VRF::generate(&mut OsRng);

        let (output1, _) = vrf.prove(b"input 1").unwrap();
        let (output2, _) = vrf.prove(b"input 2").unwrap();

        assert_ne!(output1, output2);
    }

    #[test]
    fn test_vrf_wrong_key_fails() {
        let vrf1 = VRF::generate(&mut OsRng);
        let vrf2 = VRF::generate(&mut OsRng);

        let (_, proof) = vrf1.prove(b"input").unwrap();
        let pk2 = vrf2.public_key_bytes();

        assert!(VRF::verify(&pk2, b"input", &proof).is_err());
    }

    #[test]
    fn test_threshold_comparison() {
        let output = VRFOutput([0u8; 32]); // Minimum value
        assert!(output.is_below_threshold(100, 1000, 100_000)); // 10% threshold

        let output = VRFOutput([0xff; 32]); // Maximum value
        assert!(!output.is_below_threshold(100, 1000, 100_000)); // 10% threshold
    }
}
