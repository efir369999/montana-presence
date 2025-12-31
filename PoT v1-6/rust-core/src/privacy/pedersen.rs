//! Pedersen Commitments
//!
//! Pedersen commitments hide transaction amounts:
//! - C = v*H + r*G (commitment to value v with blinding factor r)
//! - Perfectly hiding: reveals nothing about v
//! - Computationally binding: can't change v without knowing r
//!
//! Used with Bulletproofs for range proofs (proving v >= 0 without revealing v)

use crate::{Error, Result};
use curve25519_dalek::{
    constants::ED25519_BASEPOINT_POINT,
    edwards::{CompressedEdwardsY, EdwardsPoint},
    scalar::Scalar,
};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

/// Second generator H for Pedersen commitments
/// H = hash_to_point("PoT-pedersen-H-v1")
fn generator_h() -> EdwardsPoint {
    let mut hasher = Sha256::new();
    hasher.update(b"PoT-pedersen-H-v1");
    let hash: [u8; 32] = hasher.finalize().into();

    // Hash to curve
    let mut bytes = hash;
    for i in 0..256u8 {
        bytes[0] = bytes[0].wrapping_add(i);
        let compressed = CompressedEdwardsY(bytes);
        if let Some(point) = compressed.decompress() {
            let cleared = point.mul_by_cofactor();
            if !cleared.is_identity() {
                return cleared;
            }
        }
    }

    // Fallback (should never happen)
    panic!("Failed to generate H")
}

lazy_static::lazy_static! {
    static ref H: EdwardsPoint = generator_h();
}

/// Pedersen commitment
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct PedersenCommitment(pub [u8; 32]);

impl PedersenCommitment {
    /// Commit to value with random blinding factor
    pub fn commit<R: RngCore>(value: u64, rng: &mut R) -> (Self, Scalar) {
        let mut blind_bytes = [0u8; 32];
        rng.fill_bytes(&mut blind_bytes);
        let blinding = Scalar::from_bytes_mod_order(blind_bytes);

        let commitment = Self::commit_with_blinding(value, &blinding);
        (commitment, blinding)
    }

    /// Commit with specific blinding factor
    pub fn commit_with_blinding(value: u64, blinding: &Scalar) -> Self {
        let v = Scalar::from(value);

        // C = v*H + r*G
        let commitment = &v * *H + blinding * ED25519_BASEPOINT_POINT;
        Self(commitment.compress().to_bytes())
    }

    /// Verify commitment opens to given value and blinding
    pub fn verify(&self, value: u64, blinding: &Scalar) -> bool {
        let expected = Self::commit_with_blinding(value, blinding);
        self.0 == expected.0
    }

    /// Add two commitments (for balance verification)
    /// C1 + C2 = (v1 + v2)*H + (r1 + r2)*G
    pub fn add(&self, other: &Self) -> Result<Self> {
        let p1 = CompressedEdwardsY(self.0)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid commitment".into()))?;
        let p2 = CompressedEdwardsY(other.0)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid commitment".into()))?;

        let sum = p1 + p2;
        Ok(Self(sum.compress().to_bytes()))
    }

    /// Subtract two commitments
    /// C1 - C2 = (v1 - v2)*H + (r1 - r2)*G
    pub fn sub(&self, other: &Self) -> Result<Self> {
        let p1 = CompressedEdwardsY(self.0)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid commitment".into()))?;
        let p2 = CompressedEdwardsY(other.0)
            .decompress()
            .ok_or_else(|| Error::Crypto("Invalid commitment".into()))?;

        let diff = p1 - p2;
        Ok(Self(diff.compress().to_bytes()))
    }

    /// Check if commitment is zero (for balance verification)
    /// If inputs = outputs, then sum(input_commitments) - sum(output_commitments) = 0
    pub fn is_zero(&self) -> bool {
        self.0 == [0u8; 32] || {
            // Also check if it's the identity point
            if let Some(point) = CompressedEdwardsY(self.0).decompress() {
                point.is_identity()
            } else {
                false
            }
        }
    }

    /// Get as bytes
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Create from bytes
    pub fn from_bytes(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }
}

/// Verify transaction balance (sum of inputs = sum of outputs + fee)
pub fn verify_balance(
    input_commitments: &[PedersenCommitment],
    output_commitments: &[PedersenCommitment],
    fee: u64,
) -> Result<bool> {
    if input_commitments.is_empty() || output_commitments.is_empty() {
        return Ok(false);
    }

    // Sum inputs
    let mut input_sum = input_commitments[0];
    for c in &input_commitments[1..] {
        input_sum = input_sum.add(c)?;
    }

    // Sum outputs
    let mut output_sum = output_commitments[0];
    for c in &output_commitments[1..] {
        output_sum = output_sum.add(c)?;
    }

    // Add fee commitment (fee has zero blinding since it's public)
    let fee_commitment = PedersenCommitment::commit_with_blinding(fee, &Scalar::ZERO);
    output_sum = output_sum.add(&fee_commitment)?;

    // Difference should be zero
    let diff = input_sum.sub(&output_sum)?;

    Ok(diff.is_zero())
}

/// Range proof (placeholder - would use Bulletproofs in production)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RangeProof {
    /// Proof data
    pub proof: Vec<u8>,
}

impl RangeProof {
    /// Create range proof for value (placeholder)
    pub fn create(value: u64, blinding: &Scalar) -> Self {
        // In production, this would use bulletproofs
        // For now, just store value + blinding hash (not secure!)
        let mut hasher = Sha256::new();
        hasher.update(b"PoT-rangeproof-placeholder");
        hasher.update(&value.to_le_bytes());
        hasher.update(&blinding.to_bytes());
        let hash = hasher.finalize();

        Self {
            proof: hash.to_vec(),
        }
    }

    /// Verify range proof (placeholder)
    pub fn verify(&self, _commitment: &PedersenCommitment) -> bool {
        // Placeholder - always returns true
        // In production, would verify bulletproof
        self.proof.len() == 32
    }

    /// Get proof size
    pub fn size(&self) -> usize {
        self.proof.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    #[test]
    fn test_commitment_verify() {
        let value = 1000u64;
        let (commitment, blinding) = PedersenCommitment::commit(value, &mut OsRng);

        assert!(commitment.verify(value, &blinding));
        assert!(!commitment.verify(value + 1, &blinding));
    }

    #[test]
    fn test_commitment_hiding() {
        let value = 1000u64;
        let (c1, _) = PedersenCommitment::commit(value, &mut OsRng);
        let (c2, _) = PedersenCommitment::commit(value, &mut OsRng);

        // Same value, different commitments (different blinding)
        assert_ne!(c1.0, c2.0);
    }

    #[test]
    fn test_commitment_addition() {
        let v1 = 100u64;
        let v2 = 200u64;

        let mut r1_bytes = [0u8; 32];
        let mut r2_bytes = [0u8; 32];
        OsRng.fill_bytes(&mut r1_bytes);
        OsRng.fill_bytes(&mut r2_bytes);
        let r1 = Scalar::from_bytes_mod_order(r1_bytes);
        let r2 = Scalar::from_bytes_mod_order(r2_bytes);

        let c1 = PedersenCommitment::commit_with_blinding(v1, &r1);
        let c2 = PedersenCommitment::commit_with_blinding(v2, &r2);
        let c_sum = c1.add(&c2).unwrap();

        // C1 + C2 should equal commitment to v1 + v2 with r1 + r2
        let r_sum = r1 + r2;
        let expected = PedersenCommitment::commit_with_blinding(v1 + v2, &r_sum);

        assert_eq!(c_sum.0, expected.0);
    }

    #[test]
    fn test_balance_verification() {
        // Simulate transaction: 100 + 200 = 250 + 50 (fee = 0)
        let v_in1 = 100u64;
        let v_in2 = 200u64;
        let v_out1 = 150u64;
        let v_out2 = 150u64;

        let mut r_in1_bytes = [0u8; 32];
        let mut r_in2_bytes = [0u8; 32];
        let mut r_out1_bytes = [0u8; 32];
        OsRng.fill_bytes(&mut r_in1_bytes);
        OsRng.fill_bytes(&mut r_in2_bytes);
        OsRng.fill_bytes(&mut r_out1_bytes);

        let r_in1 = Scalar::from_bytes_mod_order(r_in1_bytes);
        let r_in2 = Scalar::from_bytes_mod_order(r_in2_bytes);
        let r_out1 = Scalar::from_bytes_mod_order(r_out1_bytes);

        // r_out2 must balance: r_in1 + r_in2 = r_out1 + r_out2
        let r_out2 = (r_in1 + r_in2) - r_out1;

        let c_in1 = PedersenCommitment::commit_with_blinding(v_in1, &r_in1);
        let c_in2 = PedersenCommitment::commit_with_blinding(v_in2, &r_in2);
        let c_out1 = PedersenCommitment::commit_with_blinding(v_out1, &r_out1);
        let c_out2 = PedersenCommitment::commit_with_blinding(v_out2, &r_out2);

        assert!(verify_balance(&[c_in1, c_in2], &[c_out1, c_out2], 0).unwrap());
    }

    #[test]
    fn test_balance_with_fee() {
        let v_in = 100u64;
        let v_out = 90u64;
        let fee = 10u64;

        let mut r_bytes = [0u8; 32];
        OsRng.fill_bytes(&mut r_bytes);
        let r = Scalar::from_bytes_mod_order(r_bytes);

        let c_in = PedersenCommitment::commit_with_blinding(v_in, &r);
        let c_out = PedersenCommitment::commit_with_blinding(v_out, &r);

        assert!(verify_balance(&[c_in], &[c_out], fee).unwrap());
    }

    #[test]
    fn test_unbalanced_fails() {
        let v_in = 100u64;
        let v_out = 101u64; // More output than input!

        let (c_in, _) = PedersenCommitment::commit(v_in, &mut OsRng);
        let (c_out, _) = PedersenCommitment::commit(v_out, &mut OsRng);

        assert!(!verify_balance(&[c_in], &[c_out], 0).unwrap());
    }

    #[test]
    fn test_range_proof() {
        let value = 1000u64;
        let (commitment, blinding) = PedersenCommitment::commit(value, &mut OsRng);
        let proof = RangeProof::create(value, &blinding);

        assert!(proof.verify(&commitment));
    }
}
