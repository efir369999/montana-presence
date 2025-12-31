//! Ed25519 Signatures
//!
//! Provides high-level wrapper around ed25519-dalek for:
//! - Key generation
//! - Message signing
//! - Signature verification
//!
//! All operations are constant-time to prevent timing attacks.

use crate::{Error, Result};
use ed25519_dalek::{
    Signature as Ed25519Signature,
    Signer, SigningKey, Verifier, VerifyingKey,
};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

/// 32-byte secret key
#[derive(Clone)]
pub struct SecretKey(Zeroizing<[u8; 32]>);

impl SecretKey {
    /// Generate random secret key
    pub fn generate<R: RngCore>(rng: &mut R) -> Self {
        let mut bytes = Zeroizing::new([0u8; 32]);
        rng.fill_bytes(&mut *bytes);
        Self(bytes)
    }

    /// Create from bytes
    pub fn from_bytes(bytes: &[u8; 32]) -> Self {
        Self(Zeroizing::new(*bytes))
    }

    /// Get bytes (use carefully - exposes secret)
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Derive public key
    pub fn public_key(&self) -> PublicKey {
        let signing_key = SigningKey::from_bytes(&self.0);
        let verifying_key = signing_key.verifying_key();
        PublicKey(verifying_key.to_bytes())
    }
}

impl std::fmt::Debug for SecretKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "SecretKey([REDACTED])")
    }
}

/// 32-byte public key
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PublicKey(pub [u8; 32]);

impl PublicKey {
    /// Create from bytes
    pub fn from_bytes(bytes: &[u8; 32]) -> Self {
        Self(*bytes)
    }

    /// Try to create from slice
    pub fn try_from_slice(slice: &[u8]) -> Result<Self> {
        if slice.len() != 32 {
            return Err(Error::InvalidInput("Public key must be 32 bytes".into()));
        }
        let mut bytes = [0u8; 32];
        bytes.copy_from_slice(slice);
        Ok(Self(bytes))
    }

    /// Get bytes
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Verify this is a valid Ed25519 public key
    pub fn validate(&self) -> Result<()> {
        VerifyingKey::from_bytes(&self.0)
            .map_err(|_| Error::Crypto("Invalid Ed25519 public key".into()))?;
        Ok(())
    }
}

impl AsRef<[u8]> for PublicKey {
    fn as_ref(&self) -> &[u8] {
        &self.0
    }
}

impl std::fmt::Display for PublicKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", hex::encode(&self.0[..8]))
    }
}

/// 64-byte Ed25519 signature
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Signature(pub [u8; 64]);

impl Signature {
    /// Create from bytes
    pub fn from_bytes(bytes: &[u8; 64]) -> Self {
        Self(*bytes)
    }

    /// Try to create from slice
    pub fn try_from_slice(slice: &[u8]) -> Result<Self> {
        if slice.len() != 64 {
            return Err(Error::InvalidInput("Signature must be 64 bytes".into()));
        }
        let mut bytes = [0u8; 64];
        bytes.copy_from_slice(slice);
        Ok(Self(bytes))
    }

    /// Get bytes
    pub fn as_bytes(&self) -> &[u8; 64] {
        &self.0
    }
}

impl AsRef<[u8]> for Signature {
    fn as_ref(&self) -> &[u8] {
        &self.0
    }
}

/// Keypair for signing operations
#[derive(Clone)]
pub struct Keypair {
    secret: SecretKey,
    public: PublicKey,
}

impl Keypair {
    /// Generate new random keypair
    pub fn generate<R: RngCore>(rng: &mut R) -> Self {
        let secret = SecretKey::generate(rng);
        let public = secret.public_key();
        Self { secret, public }
    }

    /// Create from secret key bytes
    pub fn from_secret_key(sk_bytes: &[u8; 32]) -> Self {
        let secret = SecretKey::from_bytes(sk_bytes);
        let public = secret.public_key();
        Self { secret, public }
    }

    /// Get public key
    pub fn public_key(&self) -> &PublicKey {
        &self.public
    }

    /// Get secret key
    pub fn secret_key(&self) -> &SecretKey {
        &self.secret
    }

    /// Sign a message
    pub fn sign(&self, message: &[u8]) -> Signature {
        let signing_key = SigningKey::from_bytes(self.secret.as_bytes());
        let sig = signing_key.sign(message);
        Signature(sig.to_bytes())
    }

    /// Verify a signature
    pub fn verify(&self, message: &[u8], signature: &Signature) -> Result<()> {
        verify(&self.public, message, signature)
    }
}

impl std::fmt::Debug for Keypair {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Keypair")
            .field("public", &self.public)
            .field("secret", &"[REDACTED]")
            .finish()
    }
}

/// Sign a message with secret key
pub fn sign(secret_key: &SecretKey, message: &[u8]) -> Signature {
    let signing_key = SigningKey::from_bytes(secret_key.as_bytes());
    let sig = signing_key.sign(message);
    Signature(sig.to_bytes())
}

/// Verify a signature with public key
pub fn verify(public_key: &PublicKey, message: &[u8], signature: &Signature) -> Result<()> {
    let verifying_key = VerifyingKey::from_bytes(&public_key.0)
        .map_err(|_| Error::Crypto("Invalid public key".into()))?;

    let sig = Ed25519Signature::from_bytes(&signature.0);

    verifying_key
        .verify(message, &sig)
        .map_err(|_| Error::Crypto("Signature verification failed".into()))
}

/// Batch verify multiple signatures (faster than individual verification)
pub fn batch_verify(
    public_keys: &[PublicKey],
    messages: &[&[u8]],
    signatures: &[Signature],
) -> Result<()> {
    if public_keys.len() != messages.len() || messages.len() != signatures.len() {
        return Err(Error::InvalidInput("Mismatched input lengths".into()));
    }

    // Convert to ed25519-dalek types
    let verifying_keys: Vec<VerifyingKey> = public_keys
        .iter()
        .map(|pk| VerifyingKey::from_bytes(&pk.0))
        .collect::<std::result::Result<Vec<_>, _>>()
        .map_err(|_| Error::Crypto("Invalid public key in batch".into()))?;

    let sigs: Vec<Ed25519Signature> = signatures
        .iter()
        .map(|s| Ed25519Signature::from_bytes(&s.0))
        .collect();

    // Use ed25519-dalek batch verification
    ed25519_dalek::verify_batch(
        messages,
        &sigs,
        &verifying_keys,
    ).map_err(|_| Error::Crypto("Batch signature verification failed".into()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    #[test]
    fn test_keypair_generation() {
        let kp = Keypair::generate(&mut OsRng);
        assert_eq!(kp.public_key().as_bytes().len(), 32);
    }

    #[test]
    fn test_sign_verify() {
        let kp = Keypair::generate(&mut OsRng);
        let message = b"Hello, Proof of Time!";

        let sig = kp.sign(message);
        assert!(kp.verify(message, &sig).is_ok());
    }

    #[test]
    fn test_wrong_message_fails() {
        let kp = Keypair::generate(&mut OsRng);
        let sig = kp.sign(b"message 1");

        assert!(kp.verify(b"message 2", &sig).is_err());
    }

    #[test]
    fn test_wrong_key_fails() {
        let kp1 = Keypair::generate(&mut OsRng);
        let kp2 = Keypair::generate(&mut OsRng);

        let sig = kp1.sign(b"message");
        assert!(verify(kp2.public_key(), b"message", &sig).is_err());
    }

    #[test]
    fn test_batch_verify() {
        let kps: Vec<Keypair> = (0..10).map(|_| Keypair::generate(&mut OsRng)).collect();
        let messages: Vec<Vec<u8>> = (0..10).map(|i| format!("message {}", i).into_bytes()).collect();

        let sigs: Vec<Signature> = kps
            .iter()
            .zip(messages.iter())
            .map(|(kp, msg)| kp.sign(msg))
            .collect();

        let pks: Vec<PublicKey> = kps.iter().map(|kp| *kp.public_key()).collect();
        let msg_refs: Vec<&[u8]> = messages.iter().map(|m| m.as_slice()).collect();

        assert!(batch_verify(&pks, &msg_refs, &sigs).is_ok());
    }

    #[test]
    fn test_deterministic_signature() {
        let kp = Keypair::from_secret_key(&[42u8; 32]);
        let message = b"deterministic";

        let sig1 = kp.sign(message);
        let sig2 = kp.sign(message);

        assert_eq!(sig1, sig2);
    }
}
