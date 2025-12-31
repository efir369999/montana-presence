//! Cryptographic Hash Functions
//!
//! Provides:
//! - SHA-256 (transaction/block hashing)
//! - SHA-512 (key derivation)
//! - BLAKE2b-256 (fast hashing)
//!
//! All functions are constant-time and use stack allocation where possible.

use sha2::{Sha256, Sha512, Digest};
use blake2::{Blake2b, digest::consts::U32};

/// SHA-256 hash (32 bytes)
#[inline]
pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().into()
}

/// SHA-256 of multiple inputs
pub fn sha256_multi(inputs: &[&[u8]]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    for input in inputs {
        hasher.update(input);
    }
    hasher.finalize().into()
}

/// Double SHA-256 (Bitcoin-style)
#[inline]
pub fn sha256d(data: &[u8]) -> [u8; 32] {
    sha256(&sha256(data))
}

/// SHA-512 hash (64 bytes)
#[inline]
pub fn sha512(data: &[u8]) -> [u8; 64] {
    let mut hasher = Sha512::new();
    hasher.update(data);
    hasher.finalize().into()
}

/// BLAKE2b-256 hash (32 bytes, faster than SHA-256)
#[inline]
pub fn blake2b_256(data: &[u8]) -> [u8; 32] {
    use blake2::Digest as Blake2Digest;
    type Blake2b256 = Blake2b<U32>;

    let mut hasher = Blake2b256::new();
    hasher.update(data);
    hasher.finalize().into()
}

/// BLAKE2b-256 of multiple inputs
pub fn blake2b_256_multi(inputs: &[&[u8]]) -> [u8; 32] {
    use blake2::Digest as Blake2Digest;
    type Blake2b256 = Blake2b<U32>;

    let mut hasher = Blake2b256::new();
    for input in inputs {
        hasher.update(input);
    }
    hasher.finalize().into()
}

/// Compute Merkle root from leaf hashes
pub fn merkle_root(hashes: &[[u8; 32]]) -> [u8; 32] {
    if hashes.is_empty() {
        return [0u8; 32];
    }
    if hashes.len() == 1 {
        return hashes[0];
    }

    let mut current_level: Vec<[u8; 32]> = hashes.to_vec();

    while current_level.len() > 1 {
        let mut next_level = Vec::with_capacity((current_level.len() + 1) / 2);

        for chunk in current_level.chunks(2) {
            let hash = if chunk.len() == 2 {
                sha256_multi(&[&chunk[0], &chunk[1]])
            } else {
                // Odd number of hashes - duplicate last one (Bitcoin-style)
                sha256_multi(&[&chunk[0], &chunk[0]])
            };
            next_level.push(hash);
        }

        current_level = next_level;
    }

    current_level[0]
}

/// HMAC-SHA256
pub fn hmac_sha256(key: &[u8], data: &[u8]) -> [u8; 32] {
    use hmac::{Hmac, Mac};
    type HmacSha256 = Hmac<Sha256>;

    let mut mac = HmacSha256::new_from_slice(key)
        .expect("HMAC accepts any key length");
    mac.update(data);
    mac.finalize().into_bytes().into()
}

/// HKDF-SHA256 key derivation
pub fn hkdf_sha256(ikm: &[u8], salt: &[u8], info: &[u8], output_len: usize) -> Vec<u8> {
    use hkdf::Hkdf;

    let hkdf = Hkdf::<Sha256>::new(Some(salt), ikm);
    let mut output = vec![0u8; output_len];
    hkdf.expand(info, &mut output)
        .expect("Output length should be valid");
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sha256() {
        let hash = sha256(b"hello");
        assert_eq!(hash.len(), 32);
        // Known test vector
        assert_eq!(
            hex::encode(hash),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );
    }

    #[test]
    fn test_sha256d() {
        let hash = sha256d(b"hello");
        assert_eq!(hash.len(), 32);
        assert_ne!(hash, sha256(b"hello")); // Should be different from single hash
    }

    #[test]
    fn test_blake2b_256() {
        let hash = blake2b_256(b"hello");
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_merkle_root_empty() {
        let root = merkle_root(&[]);
        assert_eq!(root, [0u8; 32]);
    }

    #[test]
    fn test_merkle_root_single() {
        let hash = sha256(b"tx1");
        let root = merkle_root(&[hash]);
        assert_eq!(root, hash);
    }

    #[test]
    fn test_merkle_root_two() {
        let h1 = sha256(b"tx1");
        let h2 = sha256(b"tx2");
        let root = merkle_root(&[h1, h2]);

        let expected = sha256_multi(&[&h1, &h2]);
        assert_eq!(root, expected);
    }

    #[test]
    fn test_merkle_root_odd() {
        let h1 = sha256(b"tx1");
        let h2 = sha256(b"tx2");
        let h3 = sha256(b"tx3");

        let root = merkle_root(&[h1, h2, h3]);
        assert_eq!(root.len(), 32);
    }

    #[test]
    fn test_hmac() {
        let mac = hmac_sha256(b"key", b"message");
        assert_eq!(mac.len(), 32);
    }
}
