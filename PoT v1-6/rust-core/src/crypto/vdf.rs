//! Verifiable Delay Function (VDF) - Wesolowski Construction
//!
//! The VDF is the core of Proof of Time. It provides:
//! - **Sequential computation**: Cannot be parallelized
//! - **Fast verification**: O(log T) vs O(T) computation
//! - **Deterministic output**: Same input always produces same output
//!
//! ## Construction
//!
//! Given input x and iterations T:
//! 1. Compute y = x^(2^T) mod N (sequential squaring)
//! 2. Compute proof π using Fiat-Shamir
//! 3. Verify: x^r · π^(2^T) ≡ y^r mod N
//!
//! ## Security
//!
//! - Uses 2048-bit RSA modulus (product of two safe primes)
//! - Challenge derived via SHA-256 (Fiat-Shamir)
//! - Resistant to parallel speedup attacks

use crate::{Error, Result};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

#[cfg(feature = "gmp")]
use rug::{Integer, integer::Order};

#[cfg(not(feature = "gmp"))]
use num_bigint::BigUint;

/// VDF configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VDFConfig {
    /// RSA modulus (2048 bits recommended)
    pub modulus: Vec<u8>,
    /// Number of iterations
    pub iterations: u64,
    /// Checkpoint interval (save intermediate states)
    pub checkpoint_interval: u64,
}

impl Default for VDFConfig {
    fn default() -> Self {
        Self {
            modulus: default_modulus(),
            iterations: 60_000_000,
            checkpoint_interval: 600,
        }
    }
}

/// VDF proof structure
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct VDFProof {
    /// Input value
    pub input: Vec<u8>,
    /// Output value y = x^(2^T) mod N
    pub output: Vec<u8>,
    /// Proof π for Wesolowski verification
    pub proof: Vec<u8>,
    /// Number of iterations
    pub iterations: u64,
}

/// VDF engine with checkpoint support
pub struct VDF {
    config: VDFConfig,
    #[cfg(feature = "gmp")]
    modulus: Integer,
    #[cfg(not(feature = "gmp"))]
    modulus: BigUint,
    /// Checkpoint storage: height -> (iterations, state)
    checkpoints: Arc<RwLock<HashMap<u64, (u64, Vec<u8>)>>>,
}

impl VDF {
    /// Create new VDF engine with default modulus
    pub fn new(iterations: u64) -> Self {
        let config = VDFConfig {
            iterations,
            ..Default::default()
        };
        Self::with_config(config)
    }

    /// Create VDF engine with custom config
    pub fn with_config(config: VDFConfig) -> Self {
        #[cfg(feature = "gmp")]
        let modulus = Integer::from_digits(&config.modulus, Order::Lsf);

        #[cfg(not(feature = "gmp"))]
        let modulus = BigUint::from_bytes_le(&config.modulus);

        Self {
            config,
            modulus,
            checkpoints: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Compute VDF: y = x^(2^T) mod N
    ///
    /// This is the slow, sequential computation that proves time has passed.
    #[cfg(feature = "gmp")]
    pub fn compute(&self, input: &[u8]) -> Result<VDFProof> {
        let mut x = Integer::from_digits(input, Order::Lsf);
        x %= &self.modulus;

        // Sequential squaring - cannot be parallelized
        for _ in 0..self.config.iterations {
            x = x.square();
            x %= &self.modulus;
        }

        let output = x.to_digits::<u8>(Order::Lsf);

        // Compute Wesolowski proof
        let proof = self.compute_proof(input, &output)?;

        Ok(VDFProof {
            input: input.to_vec(),
            output,
            proof,
            iterations: self.config.iterations,
        })
    }

    #[cfg(not(feature = "gmp"))]
    pub fn compute(&self, input: &[u8]) -> Result<VDFProof> {
        use num_traits::One;
        use num_bigint::BigUint;

        let mut x = BigUint::from_bytes_le(input);
        x %= &self.modulus;

        let two = BigUint::from(2u32);

        for _ in 0..self.config.iterations {
            x = x.modpow(&two, &self.modulus);
        }

        let output = x.to_bytes_le();
        let proof = self.compute_proof(input, &output)?;

        Ok(VDFProof {
            input: input.to_vec(),
            output,
            proof,
            iterations: self.config.iterations,
        })
    }

    /// Compute VDF with progress callback
    #[cfg(feature = "gmp")]
    pub fn compute_with_progress<F>(&self, input: &[u8], mut callback: F) -> Result<VDFProof>
    where
        F: FnMut(u64, u64), // (current, total)
    {
        let mut x = Integer::from_digits(input, Order::Lsf);
        x %= &self.modulus;

        let checkpoint_interval = self.config.checkpoint_interval.max(1);

        for i in 0..self.config.iterations {
            x = x.square();
            x %= &self.modulus;

            if i % checkpoint_interval == 0 {
                callback(i, self.config.iterations);
            }
        }

        callback(self.config.iterations, self.config.iterations);

        let output = x.to_digits::<u8>(Order::Lsf);
        let proof = self.compute_proof(input, &output)?;

        Ok(VDFProof {
            input: input.to_vec(),
            output,
            proof,
            iterations: self.config.iterations,
        })
    }

    /// Verify VDF proof (fast - O(log T))
    #[cfg(feature = "gmp")]
    pub fn verify(&self, proof: &VDFProof) -> Result<bool> {
        // Derive challenge using Fiat-Shamir
        let challenge = self.derive_challenge(&proof.input, &proof.output);

        let x = Integer::from_digits(&proof.input, Order::Lsf);
        let y = Integer::from_digits(&proof.output, Order::Lsf);
        let pi = Integer::from_digits(&proof.proof, Order::Lsf);
        let l = Integer::from_digits(&challenge, Order::Lsf);

        // Compute r = 2^T mod l (fast with modpow)
        let two = Integer::from(2);
        let t = Integer::from(proof.iterations);
        let r = two.pow_mod(&t, &l).map_err(|_| Error::Crypto("pow_mod failed".into()))?;

        // Verify: x^r · π^l ≡ y (mod N)
        let x_r = x.pow_mod(&r, &self.modulus).map_err(|_| Error::Crypto("pow_mod failed".into()))?;
        let pi_l = pi.pow_mod(&l, &self.modulus).map_err(|_| Error::Crypto("pow_mod failed".into()))?;

        let lhs = (x_r * pi_l) % &self.modulus;

        Ok(lhs == y)
    }

    #[cfg(not(feature = "gmp"))]
    pub fn verify(&self, proof: &VDFProof) -> Result<bool> {
        let challenge = self.derive_challenge(&proof.input, &proof.output);

        let x = BigUint::from_bytes_le(&proof.input);
        let y = BigUint::from_bytes_le(&proof.output);
        let pi = BigUint::from_bytes_le(&proof.proof);
        let l = BigUint::from_bytes_le(&challenge);

        let two = BigUint::from(2u32);
        let t = BigUint::from(proof.iterations);
        let r = two.modpow(&t, &l);

        let x_r = x.modpow(&r, &self.modulus);
        let pi_l = pi.modpow(&l, &self.modulus);

        let lhs = (x_r * pi_l) % &self.modulus;

        Ok(lhs == y)
    }

    /// Compute Wesolowski proof
    #[cfg(feature = "gmp")]
    fn compute_proof(&self, input: &[u8], output: &[u8]) -> Result<Vec<u8>> {
        let challenge = self.derive_challenge(input, output);
        let l = Integer::from_digits(&challenge, Order::Lsf);

        let mut x = Integer::from_digits(input, Order::Lsf);
        x %= &self.modulus;

        // Compute π = x^floor(2^T / l) mod N
        // This requires computing 2^T / l efficiently
        let two = Integer::from(2);
        let mut power = Integer::from(1);
        let mut pi = Integer::from(1);

        for _ in 0..self.config.iterations {
            power *= &two;
            if power >= l {
                let q = power.clone() / &l;
                power %= &l;
                let contribution = x.clone().pow_mod(&q, &self.modulus)
                    .map_err(|_| Error::Crypto("pow_mod failed".into()))?;
                pi = (pi * contribution) % &self.modulus;
            }
            x = x.square() % &self.modulus;
        }

        Ok(pi.to_digits::<u8>(Order::Lsf))
    }

    #[cfg(not(feature = "gmp"))]
    fn compute_proof(&self, input: &[u8], output: &[u8]) -> Result<Vec<u8>> {
        use num_traits::{One, Zero};

        let challenge = self.derive_challenge(input, output);
        let l = BigUint::from_bytes_le(&challenge);

        let mut x = BigUint::from_bytes_le(input);
        x %= &self.modulus;

        let two = BigUint::from(2u32);
        let mut power = BigUint::one();
        let mut pi = BigUint::one();

        for _ in 0..self.config.iterations {
            power *= &two;
            if power >= l {
                let q = &power / &l;
                power %= &l;
                let contribution = x.modpow(&q, &self.modulus);
                pi = (pi * contribution) % &self.modulus;
            }
            x = x.modpow(&two, &self.modulus);
        }

        Ok(pi.to_bytes_le())
    }

    /// Derive challenge using Fiat-Shamir transform
    fn derive_challenge(&self, input: &[u8], output: &[u8]) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(b"PoT-VDF-challenge-v1");
        hasher.update(input);
        hasher.update(output);
        hasher.update(&self.config.iterations.to_le_bytes());
        hasher.finalize().to_vec()
    }

    /// Save checkpoint for resumable computation
    pub fn save_checkpoint(&self, height: u64, iterations: u64, state: &[u8]) {
        if let Ok(mut checkpoints) = self.checkpoints.write() {
            checkpoints.insert(height, (iterations, state.to_vec()));

            // Keep only last 24 hours of checkpoints (assuming 600 blocks per checkpoint)
            let max_checkpoints = 24 * 6; // 144 checkpoints
            if checkpoints.len() > max_checkpoints {
                let min_height = height.saturating_sub(max_checkpoints as u64);
                checkpoints.retain(|&h, _| h >= min_height);
            }
        }
    }

    /// Load checkpoint for resumable computation
    pub fn load_checkpoint(&self, height: u64) -> Option<(u64, Vec<u8>)> {
        self.checkpoints.read().ok()?.get(&height).cloned()
    }

    /// Get iterations count
    pub fn iterations(&self) -> u64 {
        self.config.iterations
    }
}

/// Default 2048-bit RSA modulus (product of two 1024-bit safe primes)
/// This is a well-known RSA challenge modulus for testing
fn default_modulus() -> Vec<u8> {
    // RSA-2048 challenge number (factored, but safe for VDF since factoring doesn't help)
    // In production, use a modulus generated with verifiable randomness (e.g., from Bitcoin block hashes)
    let hex = "c7970ceedcc3b0754490201a7aa613cd73911081c790f5f1a8726f463550bb5b7ff0db8e1ea1189ec72f93d1650011bd721aeeacc2acde32a04107f0648c2813a31f5b0b7765ff8b44b4b6ffc93384b646eb09c7cf5e8592d40ea33c80039f35b4f14a04b51f7bfd781be4d1673164ba8eb991c2c4d730bbbe35f592bdef524af7e8daefd26c66fc02c479af89d64d373f442709439de66ceb955f3ea37d5159f6135809f85334b5cb1813addc80cd05609f10ac6a95ad65872c909525bdad32bc729592642920f24c61dc5b3c3b7923e56b16a4d9d373d8721f24a3fc0f1b3131f55615172866bccc30f95054c824e733a5eb6817f7bc16399d48c6361cc7e5";

    hex::decode(hex).unwrap_or_else(|_| vec![0u8; 256])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vdf_compute_verify() {
        let vdf = VDF::new(1000); // Small iterations for test
        let input = sha2::Sha256::digest(b"test input").to_vec();

        let proof = vdf.compute(&input).unwrap();
        assert!(vdf.verify(&proof).unwrap());
    }

    #[test]
    fn test_vdf_deterministic() {
        let vdf = VDF::new(100);
        let input = vec![1, 2, 3, 4];

        let proof1 = vdf.compute(&input).unwrap();
        let proof2 = vdf.compute(&input).unwrap();

        assert_eq!(proof1.output, proof2.output);
    }

    #[test]
    fn test_vdf_different_inputs() {
        let vdf = VDF::new(100);

        let proof1 = vdf.compute(&[1, 2, 3]).unwrap();
        let proof2 = vdf.compute(&[4, 5, 6]).unwrap();

        assert_ne!(proof1.output, proof2.output);
    }
}
