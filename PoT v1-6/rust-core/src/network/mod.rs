//! Network Module for PoT Blockchain
//!
//! Implements P2P networking with:
//! - Noise Protocol XX for encryption
//! - Peer discovery and management
//! - Message framing and routing

pub mod noise;
pub mod peer;
pub mod protocol;

pub use noise::NoiseSession;
pub use peer::{Peer, PeerInfo};
pub use protocol::{Message, MessageType};
