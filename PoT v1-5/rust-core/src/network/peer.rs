//! Peer Management

use crate::{Error, Result};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::time::{Duration, Instant};

/// Peer connection state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PeerState {
    /// Not connected
    Disconnected,
    /// Connecting (handshake in progress)
    Connecting,
    /// Connected and authenticated
    Connected,
    /// Banned (misbehaving peer)
    Banned,
}

/// Peer information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerInfo {
    /// Peer's public key
    pub public_key: [u8; 32],
    /// Socket address
    pub address: String,
    /// Protocol version
    pub version: u32,
    /// User agent string
    pub user_agent: String,
    /// Chain height
    pub height: u64,
    /// Last seen timestamp
    pub last_seen: u64,
}

impl PeerInfo {
    /// Create new peer info
    pub fn new(public_key: [u8; 32], address: String) -> Self {
        Self {
            public_key,
            address,
            version: 1,
            user_agent: "pot-core/1.2.0".into(),
            height: 0,
            last_seen: 0,
        }
    }

    /// Update height
    pub fn update_height(&mut self, height: u64) {
        self.height = height;
        self.last_seen = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
    }
}

/// Active peer connection
pub struct Peer {
    /// Peer info
    pub info: PeerInfo,
    /// Connection state
    pub state: PeerState,
    /// Time of connection
    connected_at: Option<Instant>,
    /// Bytes sent
    bytes_sent: u64,
    /// Bytes received
    bytes_received: u64,
    /// Messages sent
    messages_sent: u64,
    /// Messages received
    messages_received: u64,
    /// Last ping time
    last_ping: Option<Instant>,
    /// Last pong latency
    latency: Option<Duration>,
    /// Ban reason (if banned)
    ban_reason: Option<String>,
}

impl Peer {
    /// Create new peer
    pub fn new(info: PeerInfo) -> Self {
        Self {
            info,
            state: PeerState::Disconnected,
            connected_at: None,
            bytes_sent: 0,
            bytes_received: 0,
            messages_sent: 0,
            messages_received: 0,
            last_ping: None,
            latency: None,
            ban_reason: None,
        }
    }

    /// Mark as connecting
    pub fn connect(&mut self) {
        self.state = PeerState::Connecting;
    }

    /// Mark as connected
    pub fn connected(&mut self) {
        self.state = PeerState::Connected;
        self.connected_at = Some(Instant::now());
    }

    /// Mark as disconnected
    pub fn disconnect(&mut self) {
        self.state = PeerState::Disconnected;
        self.connected_at = None;
    }

    /// Ban peer
    pub fn ban(&mut self, reason: &str) {
        self.state = PeerState::Banned;
        self.ban_reason = Some(reason.into());
    }

    /// Check if connected
    pub fn is_connected(&self) -> bool {
        self.state == PeerState::Connected
    }

    /// Check if banned
    pub fn is_banned(&self) -> bool {
        self.state == PeerState::Banned
    }

    /// Get connection duration
    pub fn connection_duration(&self) -> Option<Duration> {
        self.connected_at.map(|t| t.elapsed())
    }

    /// Record bytes sent
    pub fn record_sent(&mut self, bytes: u64) {
        self.bytes_sent += bytes;
        self.messages_sent += 1;
    }

    /// Record bytes received
    pub fn record_received(&mut self, bytes: u64) {
        self.bytes_received += bytes;
        self.messages_received += 1;
    }

    /// Start ping
    pub fn start_ping(&mut self) {
        self.last_ping = Some(Instant::now());
    }

    /// Record pong
    pub fn record_pong(&mut self) {
        if let Some(ping_time) = self.last_ping {
            self.latency = Some(ping_time.elapsed());
        }
    }

    /// Get latency
    pub fn latency(&self) -> Option<Duration> {
        self.latency
    }

    /// Get statistics
    pub fn stats(&self) -> PeerStats {
        PeerStats {
            bytes_sent: self.bytes_sent,
            bytes_received: self.bytes_received,
            messages_sent: self.messages_sent,
            messages_received: self.messages_received,
            connection_duration: self.connection_duration(),
            latency: self.latency,
        }
    }
}

/// Peer statistics
#[derive(Debug, Clone)]
pub struct PeerStats {
    pub bytes_sent: u64,
    pub bytes_received: u64,
    pub messages_sent: u64,
    pub messages_received: u64,
    pub connection_duration: Option<Duration>,
    pub latency: Option<Duration>,
}

/// Peer manager for tracking all peers
pub struct PeerManager {
    /// Known peers
    peers: Vec<Peer>,
    /// Maximum peers
    max_peers: usize,
    /// Minimum peers
    min_peers: usize,
}

impl PeerManager {
    /// Create new peer manager
    pub fn new(max_peers: usize, min_peers: usize) -> Self {
        Self {
            peers: Vec::new(),
            max_peers,
            min_peers,
        }
    }

    /// Add peer
    pub fn add_peer(&mut self, info: PeerInfo) -> bool {
        // Check if already known
        if self.find_by_pubkey(&info.public_key).is_some() {
            return false;
        }

        if self.peers.len() >= self.max_peers {
            return false;
        }

        self.peers.push(Peer::new(info));
        true
    }

    /// Find peer by public key
    pub fn find_by_pubkey(&self, pubkey: &[u8; 32]) -> Option<&Peer> {
        self.peers.iter().find(|p| &p.info.public_key == pubkey)
    }

    /// Find peer by public key (mutable)
    pub fn find_by_pubkey_mut(&mut self, pubkey: &[u8; 32]) -> Option<&mut Peer> {
        self.peers.iter_mut().find(|p| &p.info.public_key == pubkey)
    }

    /// Remove peer
    pub fn remove_peer(&mut self, pubkey: &[u8; 32]) {
        self.peers.retain(|p| &p.info.public_key != pubkey);
    }

    /// Get connected peers
    pub fn connected_peers(&self) -> Vec<&Peer> {
        self.peers.iter().filter(|p| p.is_connected()).collect()
    }

    /// Get peer count
    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }

    /// Get connected peer count
    pub fn connected_count(&self) -> usize {
        self.peers.iter().filter(|p| p.is_connected()).count()
    }

    /// Check if we need more peers
    pub fn needs_more_peers(&self) -> bool {
        self.connected_count() < self.min_peers
    }

    /// Get all peer infos
    pub fn peer_infos(&self) -> Vec<&PeerInfo> {
        self.peers.iter().map(|p| &p.info).collect()
    }

    /// Prune disconnected peers
    pub fn prune_disconnected(&mut self) {
        self.peers.retain(|p| p.state != PeerState::Disconnected);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_peer_lifecycle() {
        let info = PeerInfo::new([1u8; 32], "127.0.0.1:8333".into());
        let mut peer = Peer::new(info);

        assert!(!peer.is_connected());

        peer.connect();
        assert!(!peer.is_connected()); // Still connecting

        peer.connected();
        assert!(peer.is_connected());

        peer.disconnect();
        assert!(!peer.is_connected());
    }

    #[test]
    fn test_peer_manager() {
        let mut pm = PeerManager::new(10, 3);

        let info1 = PeerInfo::new([1u8; 32], "127.0.0.1:8333".into());
        let info2 = PeerInfo::new([2u8; 32], "127.0.0.2:8333".into());

        assert!(pm.add_peer(info1.clone()));
        assert!(pm.add_peer(info2));
        assert!(!pm.add_peer(info1)); // Duplicate

        assert_eq!(pm.peer_count(), 2);
    }

    #[test]
    fn test_peer_stats() {
        let info = PeerInfo::new([1u8; 32], "127.0.0.1:8333".into());
        let mut peer = Peer::new(info);

        peer.record_sent(100);
        peer.record_received(200);

        let stats = peer.stats();
        assert_eq!(stats.bytes_sent, 100);
        assert_eq!(stats.bytes_received, 200);
        assert_eq!(stats.messages_sent, 1);
        assert_eq!(stats.messages_received, 1);
    }
}
