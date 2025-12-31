//! P2P Protocol Messages

use crate::structures::block::Block;
use crate::structures::transaction::Transaction;
use crate::structures::types::Hash256;
use serde::{Deserialize, Serialize};

/// Protocol version
pub const PROTOCOL_VERSION: u32 = 1;

/// Message types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum MessageType {
    /// Version handshake
    Version = 0,
    /// Version acknowledgment
    VerAck = 1,
    /// Ping (keep-alive)
    Ping = 2,
    /// Pong (ping response)
    Pong = 3,
    /// Get peers request
    GetPeers = 4,
    /// Peers response
    Peers = 5,
    /// Inventory announcement
    Inv = 6,
    /// Get data request
    GetData = 7,
    /// Block data
    Block = 8,
    /// Transaction data
    Tx = 9,
    /// Get blocks request
    GetBlocks = 10,
    /// Block headers
    Headers = 11,
    /// Mempool request
    Mempool = 12,
    /// Reject message
    Reject = 13,
}

impl From<u8> for MessageType {
    fn from(v: u8) -> Self {
        match v {
            0 => Self::Version,
            1 => Self::VerAck,
            2 => Self::Ping,
            3 => Self::Pong,
            4 => Self::GetPeers,
            5 => Self::Peers,
            6 => Self::Inv,
            7 => Self::GetData,
            8 => Self::Block,
            9 => Self::Tx,
            10 => Self::GetBlocks,
            11 => Self::Headers,
            12 => Self::Mempool,
            13 => Self::Reject,
            _ => Self::Reject,
        }
    }
}

/// Network message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    /// Message type
    pub msg_type: MessageType,
    /// Payload
    pub payload: Vec<u8>,
}

impl Message {
    /// Create new message
    pub fn new(msg_type: MessageType, payload: Vec<u8>) -> Self {
        Self { msg_type, payload }
    }

    /// Create version message
    pub fn version(height: u64, user_agent: &str) -> Self {
        let payload = VersionPayload {
            version: PROTOCOL_VERSION,
            height,
            user_agent: user_agent.into(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        };
        Self::new(MessageType::Version, bincode::serialize(&payload).unwrap_or_default())
    }

    /// Create verack message
    pub fn verack() -> Self {
        Self::new(MessageType::VerAck, Vec::new())
    }

    /// Create ping message
    pub fn ping(nonce: u64) -> Self {
        Self::new(MessageType::Ping, nonce.to_le_bytes().to_vec())
    }

    /// Create pong message
    pub fn pong(nonce: u64) -> Self {
        Self::new(MessageType::Pong, nonce.to_le_bytes().to_vec())
    }

    /// Create inventory message
    pub fn inv(items: &[InvItem]) -> Self {
        let payload = bincode::serialize(items).unwrap_or_default();
        Self::new(MessageType::Inv, payload)
    }

    /// Create getdata message
    pub fn getdata(items: &[InvItem]) -> Self {
        let payload = bincode::serialize(items).unwrap_or_default();
        Self::new(MessageType::GetData, payload)
    }

    /// Create block message
    pub fn block(block: &Block) -> Self {
        let payload = block.to_bytes();
        Self::new(MessageType::Block, payload)
    }

    /// Create transaction message
    pub fn tx(tx: &Transaction) -> Self {
        let payload = tx.to_bytes();
        Self::new(MessageType::Tx, payload)
    }

    /// Serialize message
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(1 + 4 + self.payload.len());
        buf.push(self.msg_type as u8);
        buf.extend_from_slice(&(self.payload.len() as u32).to_le_bytes());
        buf.extend_from_slice(&self.payload);
        buf
    }

    /// Deserialize message
    pub fn from_bytes(bytes: &[u8]) -> Option<Self> {
        if bytes.len() < 5 {
            return None;
        }

        let msg_type = MessageType::from(bytes[0]);
        let len = u32::from_le_bytes(bytes[1..5].try_into().ok()?) as usize;

        if bytes.len() < 5 + len {
            return None;
        }

        let payload = bytes[5..5 + len].to_vec();
        Some(Self { msg_type, payload })
    }

    /// Get payload size
    pub fn payload_size(&self) -> usize {
        self.payload.len()
    }
}

/// Version payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionPayload {
    pub version: u32,
    pub height: u64,
    pub user_agent: String,
    pub timestamp: u64,
}

/// Inventory item type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum InvType {
    /// Transaction
    Tx = 1,
    /// Block
    Block = 2,
}

/// Inventory item
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvItem {
    pub inv_type: InvType,
    pub hash: Hash256,
}

impl InvItem {
    pub fn tx(hash: Hash256) -> Self {
        Self { inv_type: InvType::Tx, hash }
    }

    pub fn block(hash: Hash256) -> Self {
        Self { inv_type: InvType::Block, hash }
    }
}

/// Reject payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RejectPayload {
    pub message: String,
    pub code: u8,
    pub reason: String,
}

/// Reject codes
pub mod reject_code {
    pub const MALFORMED: u8 = 0x01;
    pub const INVALID: u8 = 0x10;
    pub const OBSOLETE: u8 = 0x11;
    pub const DUPLICATE: u8 = 0x12;
    pub const NONSTANDARD: u8 = 0x40;
    pub const DUST: u8 = 0x41;
    pub const INSUFFICIENTFEE: u8 = 0x42;
    pub const CHECKPOINT: u8 = 0x43;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_serialization() {
        let msg = Message::ping(12345);
        let bytes = msg.to_bytes();
        let parsed = Message::from_bytes(&bytes).unwrap();

        assert_eq!(parsed.msg_type, MessageType::Ping);
        assert_eq!(parsed.payload, 12345u64.to_le_bytes().to_vec());
    }

    #[test]
    fn test_version_message() {
        let msg = Message::version(1000, "pot-core/1.0");
        assert_eq!(msg.msg_type, MessageType::Version);

        let payload: VersionPayload = bincode::deserialize(&msg.payload).unwrap();
        assert_eq!(payload.version, PROTOCOL_VERSION);
        assert_eq!(payload.height, 1000);
    }

    #[test]
    fn test_inv_item() {
        let hash = Hash256([1u8; 32]);
        let item = InvItem::block(hash);
        assert_eq!(item.inv_type, InvType::Block);
        assert_eq!(item.hash, hash);
    }
}
