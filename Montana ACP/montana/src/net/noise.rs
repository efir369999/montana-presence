//! Hybrid Noise XX + ML-KEM-768 transport encryption

use chacha20poly1305::{
    aead::{Aead, KeyInit, Payload},
    ChaCha20Poly1305, Nonce,
};
use pqcrypto_kyber::kyber768;
use pqcrypto_traits::kem::{Ciphertext, PublicKey as KemPublicKey, SharedSecret as KemSharedSecret};
use rand::{CryptoRng, RngCore};
use sha3::{Digest, Sha3_256};
use std::io::{self, Read, Write};
use thiserror::Error;
use x25519_dalek::{StaticSecret as X25519Secret, PublicKey as X25519PublicKey};

// =============================================================================
// CONSTANTS
// =============================================================================

/// Noise protocol name for hybrid handshake
pub const NOISE_PROTOCOL_NAME: &[u8] = b"Noise_XX_25519+Kyber768_ChaChaPoly_SHA3-256";

/// Maximum Noise message size (64KB)
pub const MAX_NOISE_MESSAGE_SIZE: usize = 65535;

/// Noise frame overhead: length (2) + tag (16)
pub const NOISE_FRAME_OVERHEAD: usize = 2 + 16;

/// X25519 public key size
pub const X25519_PUBKEY_SIZE: usize = 32;

/// Kyber768 public key size (pqcrypto-kyber)
/// NIST ML-KEM-768 equivalent
pub const MLKEM768_PUBKEY_SIZE: usize = kyber768::public_key_bytes();

/// Kyber768 ciphertext size
pub const MLKEM768_CIPHERTEXT_SIZE: usize = kyber768::ciphertext_bytes();

/// Kyber768 shared secret size
pub const MLKEM768_SHARED_SIZE: usize = kyber768::shared_secret_bytes();

/// ChaCha20-Poly1305 key size
pub const CHACHA_KEY_SIZE: usize = 32;

/// ChaCha20-Poly1305 nonce size
pub const CHACHA_NONCE_SIZE: usize = 12;

/// ChaCha20-Poly1305 tag size
pub const CHACHA_TAG_SIZE: usize = 16;

// =============================================================================
// ERRORS
// =============================================================================

#[derive(Error, Debug)]
pub enum NoiseError {
    #[error("handshake failed: {0}")]
    Handshake(String),

    #[error("decryption failed")]
    Decryption,

    #[error("message too large: {size} > {max}")]
    MessageTooLarge { size: usize, max: usize },

    #[error("invalid state: expected {expected}, got {got}")]
    InvalidState { expected: &'static str, got: &'static str },

    #[error("io error: {0}")]
    Io(#[from] io::Error),

    #[error("ml-kem error: {0}")]
    MlKem(String),
}

// =============================================================================
// CIPHER STATE
// =============================================================================

/// Symmetric cipher state for encryption/decryption
#[derive(Clone)]
struct CipherState {
    /// ChaCha20-Poly1305 key (32 bytes)
    key: [u8; CHACHA_KEY_SIZE],
    /// Nonce counter (incremented after each encryption)
    nonce: u64,
    /// Whether this cipher is initialized
    initialized: bool,
}

impl CipherState {
    fn new() -> Self {
        Self {
            key: [0u8; CHACHA_KEY_SIZE],
            nonce: 0,
            initialized: false,
        }
    }

    fn init(&mut self, key: &[u8; CHACHA_KEY_SIZE]) {
        self.key = *key;
        self.nonce = 0;
        self.initialized = true;
    }

    fn encrypt(&mut self, plaintext: &[u8], ad: &[u8]) -> Result<Vec<u8>, NoiseError> {
        if !self.initialized {
            return Ok(plaintext.to_vec());
        }

        let cipher = ChaCha20Poly1305::new_from_slice(&self.key)
            .map_err(|_| NoiseError::Handshake("invalid key".into()))?;

        let nonce = self.make_nonce();
        self.nonce = self.nonce.wrapping_add(1);

        // Use Payload to include AAD in authentication
        cipher
            .encrypt(&nonce, Payload { msg: plaintext, aad: ad })
            .map_err(|_| NoiseError::Handshake("encryption failed".into()))
    }

    fn decrypt(&mut self, ciphertext: &[u8], ad: &[u8]) -> Result<Vec<u8>, NoiseError> {
        if !self.initialized {
            return Ok(ciphertext.to_vec());
        }

        let cipher = ChaCha20Poly1305::new_from_slice(&self.key)
            .map_err(|_| NoiseError::Handshake("invalid key".into()))?;

        let nonce = self.make_nonce();
        self.nonce = self.nonce.wrapping_add(1);

        // Use Payload to verify AAD in authentication
        cipher
            .decrypt(&nonce, Payload { msg: ciphertext, aad: ad })
            .map_err(|_| NoiseError::Decryption)
    }

    fn make_nonce(&self) -> Nonce {
        let mut nonce_bytes = [0u8; CHACHA_NONCE_SIZE];
        nonce_bytes[4..12].copy_from_slice(&self.nonce.to_le_bytes());
        Nonce::from(nonce_bytes)
    }
}

// =============================================================================
// SYMMETRIC STATE
// =============================================================================

/// Noise symmetric state (chaining key + cipher)
struct SymmetricState {
    /// Chaining key for key derivation
    ck: [u8; 32],
    /// Running hash of handshake transcript
    h: [u8; 32],
    /// Cipher for encrypting handshake payloads
    cipher: CipherState,
}

impl SymmetricState {
    fn new() -> Self {
        // Initialize with protocol name
        let mut h = [0u8; 32];
        if NOISE_PROTOCOL_NAME.len() <= 32 {
            h[..NOISE_PROTOCOL_NAME.len()].copy_from_slice(NOISE_PROTOCOL_NAME);
        } else {
            h = sha3_256(NOISE_PROTOCOL_NAME);
        }

        Self {
            ck: h,
            h,
            cipher: CipherState::new(),
        }
    }

    /// Mix data into handshake hash
    fn mix_hash(&mut self, data: &[u8]) {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.h);
        hasher.update(data);
        self.h = hasher.finalize().into();
    }

    /// Mix key material into chaining key
    fn mix_key(&mut self, input_key_material: &[u8]) {
        let (new_ck, temp_k) = hkdf_sha3(&self.ck, input_key_material);
        self.ck = new_ck;

        let mut key = [0u8; CHACHA_KEY_SIZE];
        key.copy_from_slice(&temp_k[..CHACHA_KEY_SIZE]);
        self.cipher.init(&key);
    }

    /// Encrypt and authenticate with handshake hash as AD
    fn encrypt_and_hash(&mut self, plaintext: &[u8]) -> Result<Vec<u8>, NoiseError> {
        let ciphertext = self.cipher.encrypt(plaintext, &self.h)?;
        self.mix_hash(&ciphertext);
        Ok(ciphertext)
    }

    /// Decrypt and verify with handshake hash as AD
    fn decrypt_and_hash(&mut self, ciphertext: &[u8]) -> Result<Vec<u8>, NoiseError> {
        let plaintext = self.cipher.decrypt(ciphertext, &self.h)?;
        self.mix_hash(ciphertext);
        Ok(plaintext)
    }

    /// Split into two cipher states for transport
    fn split(&self) -> (CipherState, CipherState) {
        let (k1, k2) = hkdf_sha3(&self.ck, &[]);

        let mut send = CipherState::new();
        let mut recv = CipherState::new();

        let mut key1 = [0u8; CHACHA_KEY_SIZE];
        let mut key2 = [0u8; CHACHA_KEY_SIZE];
        key1.copy_from_slice(&k1[..CHACHA_KEY_SIZE]);
        key2.copy_from_slice(&k2[..CHACHA_KEY_SIZE]);

        send.init(&key1);
        recv.init(&key2);

        (send, recv)
    }
}

// =============================================================================
// HANDSHAKE STATE
// =============================================================================

/// Noise handshake state machine
pub struct HandshakeState {
    /// Symmetric state
    symmetric: SymmetricState,
    /// Our static keypair (X25519)
    static_keypair: Option<StaticKeypair>,
    /// Our ephemeral keypair (X25519)
    ephemeral_keypair: Option<EphemeralKeypair>,
    /// Remote static public key
    remote_static: Option<[u8; X25519_PUBKEY_SIZE]>,
    /// Remote ephemeral public key
    remote_ephemeral: Option<[u8; X25519_PUBKEY_SIZE]>,
    /// ML-KEM keypair (initiator generates)
    mlkem_keypair: Option<MlKemKeypair>,
    /// Remote ML-KEM public key bytes (responder stores this)
    remote_kem_pk: Option<Vec<u8>>,
    /// ML-KEM shared secret
    mlkem_shared: Option<[u8; MLKEM768_SHARED_SIZE]>,
    /// Are we the initiator?
    initiator: bool,
    /// Current message pattern index
    message_index: usize,
}

/// Static X25519 keypair
pub struct StaticKeypair {
    pub secret: [u8; 32],
    pub public: [u8; X25519_PUBKEY_SIZE],
}

impl StaticKeypair {
    /// Generate new random keypair
    pub fn generate<R: RngCore + CryptoRng>(rng: &mut R) -> Self {
        let mut secret = [0u8; 32];
        rng.fill_bytes(&mut secret);

        let secret_key = X25519Secret::from(secret);
        let public_key = X25519PublicKey::from(&secret_key);

        Self {
            secret,
            public: public_key.to_bytes(),
        }
    }

    /// Create from existing secret
    pub fn from_secret(secret: [u8; 32]) -> Self {
        let secret_key = X25519Secret::from(secret);
        let public_key = X25519PublicKey::from(&secret_key);

        Self {
            secret,
            public: public_key.to_bytes(),
        }
    }
}

/// Ephemeral X25519 keypair
struct EphemeralKeypair {
    secret: [u8; 32],
    public: [u8; X25519_PUBKEY_SIZE],
}

impl EphemeralKeypair {
    fn generate<R: RngCore + CryptoRng>(rng: &mut R) -> Self {
        let mut secret = [0u8; 32];
        rng.fill_bytes(&mut secret);

        let secret_key = X25519Secret::from(secret);
        let public_key = X25519PublicKey::from(&secret_key);

        Self {
            secret,
            public: public_key.to_bytes(),
        }
    }
}

/// Kyber768 keypair for post-quantum key exchange
struct MlKemKeypair {
    /// Decapsulation key (secret key)
    dk: kyber768::SecretKey,
    /// Encapsulation key (public key)
    ek: kyber768::PublicKey,
}

impl HandshakeState {
    /// Create initiator handshake state
    pub fn new_initiator(static_keypair: StaticKeypair) -> Self {
        let mut state = Self {
            symmetric: SymmetricState::new(),
            static_keypair: Some(static_keypair),
            ephemeral_keypair: None,
            remote_static: None,
            remote_ephemeral: None,
            mlkem_keypair: None,
            remote_kem_pk: None,
            mlkem_shared: None,
            initiator: true,
            message_index: 0,
        };

        // Initialize protocol-specific mixing
        state.symmetric.mix_hash(&[]);

        state
    }

    /// Create responder handshake state
    pub fn new_responder(static_keypair: StaticKeypair) -> Self {
        let mut state = Self {
            symmetric: SymmetricState::new(),
            static_keypair: Some(static_keypair),
            ephemeral_keypair: None,
            remote_static: None,
            remote_ephemeral: None,
            mlkem_keypair: None,
            remote_kem_pk: None,
            mlkem_shared: None,
            initiator: false,
            message_index: 0,
        };

        state.symmetric.mix_hash(&[]);

        state
    }

    /// Write next handshake message
    ///
    /// XX Pattern with ML-KEM hybrid:
    /// - Message 0 (initiator): e, kem_pk
    /// - Message 1 (responder): e, ee, s, es, kem_ct
    /// - Message 2 (initiator): s, se
    pub fn write_message<R: RngCore + CryptoRng>(
        &mut self,
        rng: &mut R,
        payload: &[u8],
    ) -> Result<Vec<u8>, NoiseError> {
        let mut message = Vec::new();

        match (self.initiator, self.message_index) {
            // Initiator message 0: -> e, kem_pk
            (true, 0) => {
                // Generate ephemeral keypair
                let ephemeral = EphemeralKeypair::generate(rng);
                message.extend_from_slice(&ephemeral.public);
                self.symmetric.mix_hash(&ephemeral.public);
                self.ephemeral_keypair = Some(ephemeral);

                // Generate ML-KEM-768 keypair (production Kyber768)
                let (ek, dk) = kyber768::keypair();
                let ek_bytes = ek.as_bytes();
                message.extend_from_slice(ek_bytes);
                self.symmetric.mix_hash(ek_bytes);
                self.mlkem_keypair = Some(MlKemKeypair { dk, ek });

                // Encrypt payload (no key yet, so plaintext)
                let encrypted = self.symmetric.encrypt_and_hash(payload)?;
                message.extend_from_slice(&encrypted);
            }

            // Responder message 1: <- e, ee, s, es, kem_ct
            // Pattern updated: responder is at index 1 after reading msg0
            (false, 1) => {
                // Generate ephemeral keypair
                let ephemeral = EphemeralKeypair::generate(rng);
                message.extend_from_slice(&ephemeral.public);
                self.symmetric.mix_hash(&ephemeral.public);

                // DH: ee (our ephemeral, their ephemeral)
                let remote_e = self.remote_ephemeral.ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "remote_ephemeral",
                        got: "none",
                    }
                })?;
                let ee_shared = dh(&ephemeral.secret, &remote_e);
                self.symmetric.mix_key(&ee_shared);

                // Send static public key (encrypted)
                let static_kp = self.static_keypair.as_ref().ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "static_keypair",
                        got: "none",
                    }
                })?;
                let encrypted_s = self.symmetric.encrypt_and_hash(&static_kp.public)?;
                message.extend_from_slice(&encrypted_s);

                // DH: es (our static, their ephemeral)
                let es_shared = dh(&static_kp.secret, &remote_e);
                self.symmetric.mix_key(&es_shared);

                // ML-KEM-768 encapsulation (production Kyber768)
                let remote_kem_pk_bytes = self.remote_kem_pk.as_ref().ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "remote_kem_pk",
                        got: "none",
                    }
                })?;
                let remote_kem_pk = kyber768::PublicKey::from_bytes(remote_kem_pk_bytes)
                    .map_err(|_| NoiseError::MlKem("invalid remote KEM public key".into()))?;
                let (ss, ct) = kyber768::encapsulate(&remote_kem_pk);
                let ct_bytes = ct.as_bytes();
                message.extend_from_slice(ct_bytes);

                // Extract shared secret bytes
                let mut ss_array = [0u8; MLKEM768_SHARED_SIZE];
                ss_array.copy_from_slice(ss.as_bytes());
                self.symmetric.mix_key(&ss_array);
                self.mlkem_shared = Some(ss_array);

                self.ephemeral_keypair = Some(ephemeral);

                // Encrypt payload
                let encrypted = self.symmetric.encrypt_and_hash(payload)?;
                message.extend_from_slice(&encrypted);
            }

            // Initiator message 2: -> s, se
            // Pattern updated: initiator is at index 2 after reading msg1
            (true, 2) => {
                // Send static public key (encrypted)
                let static_kp = self.static_keypair.as_ref().ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "static_keypair",
                        got: "none",
                    }
                })?;
                let encrypted_s = self.symmetric.encrypt_and_hash(&static_kp.public)?;
                message.extend_from_slice(&encrypted_s);

                // DH: se (our static, their ephemeral)
                let remote_e = self.remote_ephemeral.ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "remote_ephemeral",
                        got: "none",
                    }
                })?;
                let se_shared = dh(&static_kp.secret, &remote_e);
                self.symmetric.mix_key(&se_shared);

                // Encrypt payload
                let encrypted = self.symmetric.encrypt_and_hash(payload)?;
                message.extend_from_slice(&encrypted);
            }

            _ => {
                return Err(NoiseError::InvalidState {
                    expected: "valid message index",
                    got: "out of range",
                });
            }
        }

        self.message_index += 1;
        Ok(message)
    }

    /// Read next handshake message
    pub fn read_message(&mut self, message: &[u8]) -> Result<Vec<u8>, NoiseError> {
        let mut cursor = 0;

        match (self.initiator, self.message_index) {
            // Responder reads message 0: -> e, kem_pk
            (false, 0) => {
                // Read ephemeral
                if message.len() < X25519_PUBKEY_SIZE {
                    return Err(NoiseError::Handshake("message too short".into()));
                }
                let mut remote_e = [0u8; X25519_PUBKEY_SIZE];
                remote_e.copy_from_slice(&message[..X25519_PUBKEY_SIZE]);
                cursor += X25519_PUBKEY_SIZE;
                self.symmetric.mix_hash(&remote_e);
                self.remote_ephemeral = Some(remote_e);

                // Read ML-KEM-768 public key
                if message.len() < cursor + MLKEM768_PUBKEY_SIZE {
                    return Err(NoiseError::Handshake("message too short for kem_pk".into()));
                }
                // Store raw bytes for later encapsulation
                let kem_pk_bytes = message[cursor..cursor + MLKEM768_PUBKEY_SIZE].to_vec();
                self.symmetric.mix_hash(&kem_pk_bytes);
                self.remote_kem_pk = Some(kem_pk_bytes);
                cursor += MLKEM768_PUBKEY_SIZE;

                // Decrypt payload (no key yet)
                let payload = self.symmetric.decrypt_and_hash(&message[cursor..])?;
                self.message_index += 1;
                return Ok(payload);
            }

            // Initiator reads message 1: <- e, ee, s, es, kem_ct
            (true, 1) => {
                // Read ephemeral
                if message.len() < X25519_PUBKEY_SIZE {
                    return Err(NoiseError::Handshake("message too short".into()));
                }
                let mut remote_e = [0u8; X25519_PUBKEY_SIZE];
                remote_e.copy_from_slice(&message[..X25519_PUBKEY_SIZE]);
                cursor += X25519_PUBKEY_SIZE;
                self.symmetric.mix_hash(&remote_e);
                self.remote_ephemeral = Some(remote_e);

                // DH: ee
                let ephemeral = self.ephemeral_keypair.as_ref().ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "ephemeral_keypair",
                        got: "none",
                    }
                })?;
                let ee_shared = dh(&ephemeral.secret, &remote_e);
                self.symmetric.mix_key(&ee_shared);

                // Read encrypted static
                let encrypted_s_len = X25519_PUBKEY_SIZE + CHACHA_TAG_SIZE;
                if message.len() < cursor + encrypted_s_len {
                    return Err(NoiseError::Handshake("message too short for static".into()));
                }
                let remote_s_bytes = self
                    .symmetric
                    .decrypt_and_hash(&message[cursor..cursor + encrypted_s_len])?;
                cursor += encrypted_s_len;

                let mut remote_s = [0u8; X25519_PUBKEY_SIZE];
                remote_s.copy_from_slice(&remote_s_bytes);
                self.remote_static = Some(remote_s);

                // DH: es (our ephemeral, their static)
                let es_shared = dh(&ephemeral.secret, &remote_s);
                self.symmetric.mix_key(&es_shared);

                // Read ML-KEM-768 ciphertext and decapsulate (production Kyber768)
                if message.len() < cursor + MLKEM768_CIPHERTEXT_SIZE {
                    return Err(NoiseError::Handshake("message too short for kem_ct".into()));
                }
                let kem_ct_bytes = &message[cursor..cursor + MLKEM768_CIPHERTEXT_SIZE];
                cursor += MLKEM768_CIPHERTEXT_SIZE;

                let mlkem_kp = self.mlkem_keypair.as_ref().ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "mlkem_keypair",
                        got: "none",
                    }
                })?;

                // Decapsulate using production Kyber768
                let ct = kyber768::Ciphertext::from_bytes(kem_ct_bytes)
                    .map_err(|_| NoiseError::MlKem("invalid KEM ciphertext".into()))?;
                let ss = kyber768::decapsulate(&ct, &mlkem_kp.dk);

                // Extract shared secret bytes
                let mut ss_array = [0u8; MLKEM768_SHARED_SIZE];
                ss_array.copy_from_slice(ss.as_bytes());
                self.symmetric.mix_key(&ss_array);
                self.mlkem_shared = Some(ss_array);

                // Decrypt payload
                let payload = self.symmetric.decrypt_and_hash(&message[cursor..])?;
                self.message_index += 1;
                return Ok(payload);
            }

            // Responder reads message 2: -> s, se
            // Pattern updated: responder is at index 2 after writing msg1
            (false, 2) => {
                // Read encrypted static
                let encrypted_s_len = X25519_PUBKEY_SIZE + CHACHA_TAG_SIZE;
                if message.len() < encrypted_s_len {
                    return Err(NoiseError::Handshake("message too short".into()));
                }
                let remote_s_bytes = self
                    .symmetric
                    .decrypt_and_hash(&message[..encrypted_s_len])?;
                cursor += encrypted_s_len;

                let mut remote_s = [0u8; X25519_PUBKEY_SIZE];
                remote_s.copy_from_slice(&remote_s_bytes);
                self.remote_static = Some(remote_s);

                // DH: se (our ephemeral, their static)
                let ephemeral = self.ephemeral_keypair.as_ref().ok_or_else(|| {
                    NoiseError::InvalidState {
                        expected: "ephemeral_keypair",
                        got: "none",
                    }
                })?;
                let se_shared = dh(&ephemeral.secret, &remote_s);
                self.symmetric.mix_key(&se_shared);

                // Decrypt payload
                let payload = self.symmetric.decrypt_and_hash(&message[cursor..])?;
                self.message_index += 1;
                return Ok(payload);
            }

            _ => {
                return Err(NoiseError::InvalidState {
                    expected: "valid message index",
                    got: "out of range",
                });
            }
        }
    }

    /// Check if handshake is complete
    /// After full XX handshake (3 messages), both parties reach index 3
    pub fn is_complete(&self) -> bool {
        self.message_index >= 3
    }

    /// Finalize handshake and get transport state
    pub fn finalize(self) -> Result<NoiseTransport, NoiseError> {
        if !self.is_complete() {
            return Err(NoiseError::InvalidState {
                expected: "complete handshake",
                got: "incomplete",
            });
        }

        let (send, recv) = self.symmetric.split();

        // Initiator sends with first key, responder with second
        let (send_cipher, recv_cipher) = if self.initiator {
            (send, recv)
        } else {
            (recv, send)
        };

        Ok(NoiseTransport {
            send_cipher,
            recv_cipher,
            remote_static: self.remote_static,
        })
    }

}

// =============================================================================
// TRANSPORT STATE
// =============================================================================

/// Noise transport state for encrypted communication
pub struct NoiseTransport {
    /// Cipher for sending
    send_cipher: CipherState,
    /// Cipher for receiving
    recv_cipher: CipherState,
    /// Remote peer's static public key (for identity verification)
    pub remote_static: Option<[u8; X25519_PUBKEY_SIZE]>,
}

impl NoiseTransport {
    /// Encrypt a message for sending
    pub fn encrypt(&mut self, plaintext: &[u8]) -> Result<Vec<u8>, NoiseError> {
        if plaintext.len() > MAX_NOISE_MESSAGE_SIZE - CHACHA_TAG_SIZE - 2 {
            return Err(NoiseError::MessageTooLarge {
                size: plaintext.len(),
                max: MAX_NOISE_MESSAGE_SIZE - CHACHA_TAG_SIZE - 2,
            });
        }

        let ciphertext = self.send_cipher.encrypt(plaintext, &[])?;

        // Frame: length (2 bytes) + ciphertext
        let mut frame = Vec::with_capacity(2 + ciphertext.len());
        frame.extend_from_slice(&(ciphertext.len() as u16).to_be_bytes());
        frame.extend_from_slice(&ciphertext);

        Ok(frame)
    }

    /// Decrypt a received message
    pub fn decrypt(&mut self, frame: &[u8]) -> Result<Vec<u8>, NoiseError> {
        if frame.len() < 2 {
            return Err(NoiseError::Handshake("frame too short".into()));
        }

        let len = u16::from_be_bytes([frame[0], frame[1]]) as usize;

        if frame.len() < 2 + len {
            return Err(NoiseError::Handshake("incomplete frame".into()));
        }

        let ciphertext = &frame[2..2 + len];
        self.recv_cipher.decrypt(ciphertext, &[])
    }

    /// Encrypt and write to stream
    pub fn write_encrypted<W: Write>(&mut self, writer: &mut W, data: &[u8]) -> io::Result<()> {
        let frame = self.encrypt(data).map_err(|e| {
            io::Error::new(io::ErrorKind::InvalidData, e.to_string())
        })?;
        writer.write_all(&frame)?;
        writer.flush()
    }

    /// Read and decrypt from stream
    pub fn read_encrypted<R: Read>(&mut self, reader: &mut R) -> io::Result<Vec<u8>> {
        // Read length
        let mut len_bytes = [0u8; 2];
        reader.read_exact(&mut len_bytes)?;
        let len = u16::from_be_bytes(len_bytes) as usize;

        if len > MAX_NOISE_MESSAGE_SIZE {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "message too large",
            ));
        }

        // Read ciphertext
        let mut ciphertext = vec![0u8; len];
        reader.read_exact(&mut ciphertext)?;

        // Decrypt
        let mut frame = Vec::with_capacity(2 + len);
        frame.extend_from_slice(&len_bytes);
        frame.extend_from_slice(&ciphertext);

        self.decrypt(&frame).map_err(|e| {
            io::Error::new(io::ErrorKind::InvalidData, e.to_string())
        })
    }
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/// SHA3-256 hash
fn sha3_256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha3_256::new();
    hasher.update(data);
    hasher.finalize().into()
}

/// HKDF with SHA3-256
fn hkdf_sha3(chaining_key: &[u8; 32], input_key_material: &[u8]) -> ([u8; 32], [u8; 32]) {
    // Extract
    let mut hasher = Sha3_256::new();
    hasher.update(chaining_key);
    hasher.update(input_key_material);
    let temp_key: [u8; 32] = hasher.finalize().into();

    // Expand (output 1)
    let mut hasher = Sha3_256::new();
    hasher.update(&temp_key);
    hasher.update(&[0x01]);
    let output1: [u8; 32] = hasher.finalize().into();

    // Expand (output 2)
    let mut hasher = Sha3_256::new();
    hasher.update(&temp_key);
    hasher.update(&output1);
    hasher.update(&[0x02]);
    let output2: [u8; 32] = hasher.finalize().into();

    (output1, output2)
}

/// X25519 Diffie-Hellman
fn dh(secret: &[u8; 32], public: &[u8; 32]) -> [u8; 32] {
    let secret_key = x25519_dalek::StaticSecret::from(*secret);
    let public_key = x25519_dalek::PublicKey::from(*public);
    let shared = secret_key.diffie_hellman(&public_key);
    *shared.as_bytes()
}


// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::OsRng;

    #[test]
    fn test_static_keypair_generation() {
        let keypair = StaticKeypair::generate(&mut OsRng);
        assert_eq!(keypair.public.len(), X25519_PUBKEY_SIZE);
    }

    #[test]
    fn test_cipher_state() {
        let mut cipher = CipherState::new();
        let key = [1u8; CHACHA_KEY_SIZE];
        cipher.init(&key);

        let plaintext = b"Hello, Montana!";
        let ciphertext = cipher.encrypt(plaintext, &[]).unwrap();

        assert_ne!(&ciphertext[..plaintext.len()], plaintext);
        assert_eq!(ciphertext.len(), plaintext.len() + CHACHA_TAG_SIZE);

        // Reset nonce for decryption test
        let mut cipher2 = CipherState::new();
        cipher2.init(&key);
        let decrypted = cipher2.decrypt(&ciphertext, &[]).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_full_handshake() {
        let mut rng = OsRng;

        // Generate static keypairs
        let initiator_static = StaticKeypair::generate(&mut rng);
        let responder_static = StaticKeypair::generate(&mut rng);

        // Create handshake states
        let mut initiator = HandshakeState::new_initiator(initiator_static);
        let mut responder = HandshakeState::new_responder(responder_static);

        // Message 0: initiator -> responder
        let msg0 = initiator.write_message(&mut rng, b"init_payload_0").unwrap();
        let payload0 = responder.read_message(&msg0).unwrap();
        assert_eq!(payload0, b"init_payload_0");

        // Message 1: responder -> initiator
        let msg1 = responder.write_message(&mut rng, b"resp_payload_1").unwrap();
        let payload1 = initiator.read_message(&msg1).unwrap();
        assert_eq!(payload1, b"resp_payload_1");

        // Message 2: initiator -> responder
        let msg2 = initiator.write_message(&mut rng, b"init_payload_2").unwrap();
        let payload2 = responder.read_message(&msg2).unwrap();
        assert_eq!(payload2, b"init_payload_2");

        // Finalize
        assert!(initiator.is_complete());
        assert!(responder.is_complete());

        let mut initiator_transport = initiator.finalize().unwrap();
        let mut responder_transport = responder.finalize().unwrap();

        // Test transport encryption
        let message = b"Hello, encrypted world!";
        let encrypted = initiator_transport.encrypt(message).unwrap();
        let decrypted = responder_transport.decrypt(&encrypted).unwrap();
        assert_eq!(decrypted, message);

        // Test reverse direction
        let response = b"Hello back!";
        let encrypted_resp = responder_transport.encrypt(response).unwrap();
        let decrypted_resp = initiator_transport.decrypt(&encrypted_resp).unwrap();
        assert_eq!(decrypted_resp, response);
    }

    #[test]
    fn test_hkdf() {
        let ck = [0u8; 32];
        let ikm = b"input key material";
        let (k1, k2) = hkdf_sha3(&ck, ikm);

        // Keys should be different
        assert_ne!(k1, k2);

        // Same input should produce same output
        let (k1_2, k2_2) = hkdf_sha3(&ck, ikm);
        assert_eq!(k1, k1_2);
        assert_eq!(k2, k2_2);
    }
}
