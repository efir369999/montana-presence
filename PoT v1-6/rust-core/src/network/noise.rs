//! Noise Protocol XX Implementation
//!
//! Provides encrypted, authenticated communication between nodes:
//! - Noise_XX_25519_ChaChaPoly_SHA256
//! - Mutual authentication
//! - Forward secrecy
//!
//! See: https://noiseprotocol.org/

use crate::{Error, Result};
use snow::{Builder, HandshakeState, TransportState};
use std::sync::Arc;
use tokio::sync::Mutex;

/// Noise protocol pattern
const NOISE_PATTERN: &str = "Noise_XX_25519_ChaChaPoly_SHA256";

/// Maximum message size
const MAX_MESSAGE_SIZE: usize = 65535;

/// Noise session state
pub enum SessionState {
    /// Handshake in progress
    Handshaking(HandshakeState),
    /// Transport ready
    Transport(TransportState),
}

/// Noise protocol session
pub struct NoiseSession {
    state: Arc<Mutex<SessionState>>,
    local_keypair: snow::Keypair,
    remote_public_key: Option<[u8; 32]>,
    is_initiator: bool,
}

impl NoiseSession {
    /// Create new session as initiator
    pub fn new_initiator(keypair: snow::Keypair) -> Result<Self> {
        let builder = Builder::new(NOISE_PATTERN.parse().unwrap())
            .local_private_key(&keypair.private)
            .build_initiator()
            .map_err(|e| Error::Network(format!("Failed to build noise initiator: {}", e)))?;

        Ok(Self {
            state: Arc::new(Mutex::new(SessionState::Handshaking(builder))),
            local_keypair: keypair,
            remote_public_key: None,
            is_initiator: true,
        })
    }

    /// Create new session as responder
    pub fn new_responder(keypair: snow::Keypair) -> Result<Self> {
        let builder = Builder::new(NOISE_PATTERN.parse().unwrap())
            .local_private_key(&keypair.private)
            .build_responder()
            .map_err(|e| Error::Network(format!("Failed to build noise responder: {}", e)))?;

        Ok(Self {
            state: Arc::new(Mutex::new(SessionState::Handshaking(builder))),
            local_keypair: keypair,
            remote_public_key: None,
            is_initiator: false,
        })
    }

    /// Generate new keypair
    pub fn generate_keypair() -> snow::Keypair {
        Builder::new(NOISE_PATTERN.parse().unwrap())
            .generate_keypair()
            .unwrap()
    }

    /// Get local public key
    pub fn local_public_key(&self) -> &[u8] {
        &self.local_keypair.public
    }

    /// Get remote public key (after handshake)
    pub fn remote_public_key(&self) -> Option<&[u8; 32]> {
        self.remote_public_key.as_ref()
    }

    /// Check if handshake is complete
    pub async fn is_transport_ready(&self) -> bool {
        matches!(*self.state.lock().await, SessionState::Transport(_))
    }

    /// Process handshake message
    pub async fn read_handshake_message(&mut self, message: &[u8]) -> Result<Option<Vec<u8>>> {
        let mut state = self.state.lock().await;

        match &mut *state {
            SessionState::Handshaking(hs) => {
                let mut buf = vec![0u8; MAX_MESSAGE_SIZE];

                // Read incoming message
                let len = hs.read_message(message, &mut buf)
                    .map_err(|e| Error::Network(format!("Handshake read error: {}", e)))?;
                buf.truncate(len);

                // Check if we need to write a response
                if hs.is_handshake_finished() {
                    // Extract remote public key before transitioning
                    if let Some(remote_static) = hs.get_remote_static() {
                        let mut key = [0u8; 32];
                        key.copy_from_slice(remote_static);
                        self.remote_public_key = Some(key);
                    }

                    // Move to transport mode
                    let transport = std::mem::replace(&mut *state, SessionState::Transport(
                        hs.into_transport_mode()
                            .map_err(|e| Error::Network(format!("Transport transition error: {}", e)))?
                    ));

                    Ok(None)
                } else {
                    // Generate response
                    let mut response = vec![0u8; MAX_MESSAGE_SIZE];
                    let len = hs.write_message(&[], &mut response)
                        .map_err(|e| Error::Network(format!("Handshake write error: {}", e)))?;
                    response.truncate(len);

                    // Check again after writing
                    if hs.is_handshake_finished() {
                        if let Some(remote_static) = hs.get_remote_static() {
                            let mut key = [0u8; 32];
                            key.copy_from_slice(remote_static);
                            self.remote_public_key = Some(key);
                        }
                    }

                    Ok(Some(response))
                }
            }
            SessionState::Transport(_) => {
                Err(Error::Network("Handshake already complete".into()))
            }
        }
    }

    /// Write handshake message (for initiator)
    pub async fn write_handshake_message(&mut self, payload: &[u8]) -> Result<Vec<u8>> {
        let mut state = self.state.lock().await;

        match &mut *state {
            SessionState::Handshaking(hs) => {
                let mut message = vec![0u8; MAX_MESSAGE_SIZE];
                let len = hs.write_message(payload, &mut message)
                    .map_err(|e| Error::Network(format!("Handshake write error: {}", e)))?;
                message.truncate(len);

                Ok(message)
            }
            SessionState::Transport(_) => {
                Err(Error::Network("Handshake already complete".into()))
            }
        }
    }

    /// Encrypt message for transport
    pub async fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>> {
        let mut state = self.state.lock().await;

        match &mut *state {
            SessionState::Transport(ts) => {
                let mut ciphertext = vec![0u8; plaintext.len() + 16]; // +16 for tag
                let len = ts.write_message(plaintext, &mut ciphertext)
                    .map_err(|e| Error::Network(format!("Encryption error: {}", e)))?;
                ciphertext.truncate(len);
                Ok(ciphertext)
            }
            SessionState::Handshaking(_) => {
                Err(Error::Network("Handshake not complete".into()))
            }
        }
    }

    /// Decrypt message from transport
    pub async fn decrypt(&self, ciphertext: &[u8]) -> Result<Vec<u8>> {
        let mut state = self.state.lock().await;

        match &mut *state {
            SessionState::Transport(ts) => {
                let mut plaintext = vec![0u8; ciphertext.len()];
                let len = ts.read_message(ciphertext, &mut plaintext)
                    .map_err(|e| Error::Network(format!("Decryption error: {}", e)))?;
                plaintext.truncate(len);
                Ok(plaintext)
            }
            SessionState::Handshaking(_) => {
                Err(Error::Network("Handshake not complete".into()))
            }
        }
    }
}

/// Perform full handshake as initiator
pub async fn perform_initiator_handshake<R, W>(
    session: &mut NoiseSession,
    mut read: R,
    mut write: W,
) -> Result<()>
where
    R: FnMut() -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<Vec<u8>>> + Send>>,
    W: FnMut(Vec<u8>) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<()>> + Send>>,
{
    // -> e
    let msg1 = session.write_handshake_message(&[]).await?;
    write(msg1).await?;

    // <- e, ee, s, es
    let msg2 = read().await?;
    session.read_handshake_message(&msg2).await?;

    // -> s, se
    let msg3 = session.write_handshake_message(&[]).await?;
    write(msg3).await?;

    Ok(())
}

/// Perform full handshake as responder
pub async fn perform_responder_handshake<R, W>(
    session: &mut NoiseSession,
    mut read: R,
    mut write: W,
) -> Result<()>
where
    R: FnMut() -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<Vec<u8>>> + Send>>,
    W: FnMut(Vec<u8>) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<()>> + Send>>,
{
    // <- e
    let msg1 = read().await?;
    let response = session.read_handshake_message(&msg1).await?;

    // -> e, ee, s, es
    if let Some(msg2) = response {
        write(msg2).await?;
    }

    // <- s, se
    let msg3 = read().await?;
    session.read_handshake_message(&msg3).await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_keypair_generation() {
        let kp = NoiseSession::generate_keypair();
        assert_eq!(kp.public.len(), 32);
        assert_eq!(kp.private.len(), 32);
    }

    #[tokio::test]
    async fn test_session_creation() {
        let kp = NoiseSession::generate_keypair();
        let initiator = NoiseSession::new_initiator(kp.clone()).unwrap();
        assert!(!initiator.is_transport_ready().await);

        let responder = NoiseSession::new_responder(kp).unwrap();
        assert!(!responder.is_transport_ready().await);
    }

    // Full handshake test would require mock I/O
}
