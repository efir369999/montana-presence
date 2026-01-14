// Montana P2P Network Protocol
// Copyright (c) 2024-2026 Alejandro Montana
// Distributed under the MIT software license.

//! Core P2P network protocol implementation.
//!
//! # Architecture Overview
//!
//! The network layer handles all peer-to-peer communication:
//!
//! ```text
//!                    ┌─────────────────┐
//!                    │   Application   │
//!                    └────────┬────────┘
//!                             │ NetEvent (channel)
//!                    ┌────────▼────────┐
//!                    │    Network      │ ◄── This module
//!                    │  (protocol.rs)  │
//!                    └────────┬────────┘
//!                             │
//!        ┌────────────────────┼────────────────────┐
//!        │                    │                    │
//! ┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐
//! │  AddrMan    │      │  Inventory  │      │ Connection  │
//! │(addresses)  │      │  (relay)    │      │  Manager    │
//! └─────────────┘      └─────────────┘      └─────────────┘
//! ```
//!
//! # Security Model
//!
//! ## Trust Levels
//!
//! | Source | Trust | Reason |
//! |--------|-------|--------|
//! | Hardcoded nodes | Trusted | ML-DSA-65 authenticated |
//! | Outbound peers | Partial | We chose them, but data untrusted |
//! | Inbound peers | Untrusted | May be Sybil attackers |
//! | P2P messages | Untrusted | Always validate before use |
//!
//! ## DoS Resistance
//!
//! 1. **Connection limits**: MAX_PEERS, MAX_CONNECTIONS_PER_IP, MAX_PEERS_PER_NETGROUP
//! 2. **Rate limiting**: Per-peer token buckets for each message type
//! 3. **Message size limits**: All messages bounded by type-specific constants
//! 4. **Subnet limiting**: GlobalSubnetLimiter prevents /16 flooding (Erebus protection)
//! 5. **Bans**: Misbehaving peers are banned for 24h
//!
//! ## Eclipse Resistance
//!
//! - Netgroup diversity ensures no single /16 subnet dominates connections
//! - Hardcoded nodes provide trusted bootstrap anchors
//! - External IP discovered only from OUTBOUND connections (not controllable by attacker)
//!
//! # Key Invariants
//!
//! 1. **sent_nonces bounded**: Size = active connections (MAX_PEERS max), cleaned on disconnect
//! 2. **ip_votes bounded**: Size = outbound connections (MAX_OUTBOUND max), keyed by peer.addr
//! 3. **No unbounded allocations**: All HashMaps/Vecs have explicit size limits
//! 4. **Message validation before processing**: Size checked before payload read
//!
//! # Self-Connection Detection
//!
//! Nodes generate random nonces in Version messages. If we receive our own nonce back,
//! we're connecting to ourselves (possibly through NAT/proxy). This is detected and
//! the connection is dropped.
//!
//! ```text
//! Node A                          Node A (via NAT)
//!   │                                  │
//!   │──── Version(nonce=12345) ───────►│
//!   │                                  │
//!   │◄─── Version(nonce=12345) ────────│
//!   │                                  │
//!   │  nonce matches sent_nonces!      │
//!   │  → disconnect (self-connection)  │
//! ```

#![allow(clippy::too_many_arguments)]

use super::addrman::AddrMan;
use super::connection::ConnectionManager;
use super::encrypted::{EncryptedStream, load_or_generate_keypair};
use super::inventory::Inventory;
use super::message::{Message, Addrs, InvItems, Signature};
use super::noise::StaticKeypair;
use super::peer::{Peer, PeerInfo};
use super::rate_limit::GlobalSubnetLimiter;
use super::types::*;
use crate::types::{now, NodeType, PresenceProof, Slice, Transaction};
use std::collections::{HashMap, HashSet};
use std::net::{IpAddr, SocketAddr};
use std::path::PathBuf;
use std::sync::Arc;
use thiserror::Error;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, RwLock};
use tokio::time::{interval, Duration};
use tracing::{debug, error, info, warn};

#[derive(Error, Debug)]
pub enum NetError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("serialization error: {0}")]
    Serialize(#[from] postcard::Error),
    #[error("legacy bincode error: {0}")]
    LegacyBincode(#[from] bincode::Error),
    #[error("invalid magic bytes")]
    InvalidMagic,
    #[error("invalid checksum")]
    InvalidChecksum,
    #[error("message too large: {0} bytes (max: {1})")]
    MessageTooLarge(usize, usize),
    #[error("handshake timeout")]
    HandshakeTimeout,
    #[error("noise handshake failed: {0}")]
    NoiseHandshake(String),
    #[error("protocol error: {0}")]
    Protocol(String),
    #[error("peer banned")]
    Banned,
    #[error("max connections reached")]
    MaxConnections,
    #[error("netgroup limit reached")]
    NetgroupLimit,
}

/// Network event for main loop
#[derive(Debug)]
pub enum NetEvent {
    /// New peer connected
    PeerConnected(SocketAddr),
    /// Peer disconnected
    PeerDisconnected(SocketAddr),
    /// Received slice
    Slice(SocketAddr, Box<Slice>),
    /// Received transaction
    Tx(SocketAddr, Box<Transaction>),
    /// Received presence proof
    Presence(SocketAddr, Box<PresenceProof>),
    /// Sync request: need slices from peer
    NeedSlices(SocketAddr, u64, u64),
    /// Peer has newer slices
    PeerAhead(SocketAddr, u64),
}

/// Network configuration
#[derive(Clone)]
pub struct NetConfig {
    pub listen_port: u16,
    pub data_dir: PathBuf,
    pub node_type: NodeType,
    pub services: u64,
    pub max_outbound: usize,
    pub max_inbound: usize,
    pub seeds: Vec<String>,
    /// Manually specified external IP (optional)
    pub external_ip: Option<IpAddr>,
    /// Testnet mode (uses testnet hardcoded nodes)
    pub testnet: bool,
    /// ML-DSA-65 secret key for hardcoded node authentication (4000 bytes)
    /// Only set this if you operate a hardcoded bootstrap node.
    /// Load from secure storage (HSM, encrypted file, env var).
    pub hardcoded_secret_key: Option<Vec<u8>>,
}

impl Default for NetConfig {
    fn default() -> Self {
        Self {
            listen_port: DEFAULT_PORT,
            data_dir: PathBuf::from("data"),
            node_type: NodeType::Full,
            services: NODE_FULL | NODE_PRESENCE,
            max_outbound: MAX_OUTBOUND,
            max_inbound: MAX_INBOUND,
            seeds: vec![],
            external_ip: None,
            testnet: false,
            hardcoded_secret_key: None,
        }
    }
}

/// Minimum votes required to accept external IP discovery.
///
/// Security analysis:
/// - Only outbound peer votes are counted (we initiated those connections)
/// - Inbound peers could be Sybil-controlled, so their votes are ignored
/// - With 8 outbound peers, attacker needs to control 4+ to spoof our IP
/// - Each outbound connection targets different /16 subnet (diversity)
/// - Therefore attacker needs 4+ IPs in different /16 subnets
///
/// Increased from 2 to 4 after security audit (Anthropic network_audit.md).
const MIN_IP_VOTES: usize = 4;

/// Main network manager
pub struct Network {
    config: NetConfig,
    /// Noise Protocol static keypair for P2P encryption
    keypair: Arc<StaticKeypair>,
    peers: Arc<RwLock<HashMap<SocketAddr, Peer>>>,
    addresses: Arc<RwLock<AddrMan>>,
    connections: Arc<ConnectionManager>,
    inventory: Arc<RwLock<Inventory>>,
    event_tx: mpsc::Sender<NetEvent>,
    best_slice: Arc<RwLock<u64>>,
    local_addr: Arc<RwLock<Option<NetAddress>>>,
    shutdown: Arc<RwLock<bool>>,
    /// External IP discovery via peer votes.
    ///
    /// SECURITY: Only OUTBOUND connections vote (inbound could be Sybil).
    /// BOUNDED: Key = peer.addr, max size = MAX_OUTBOUND (8 entries).
    /// We discover our external IP by consensus among trusted outbound peers.
    ip_votes: Arc<RwLock<HashMap<SocketAddr, IpAddr>>>,

    /// Nonces for self-connection detection.
    ///
    /// When we send Version, we store its nonce here. If we receive a Version
    /// with a nonce in this set, we're connecting to ourselves.
    ///
    /// BOUNDED: One entry per active connection, removed on disconnect.
    /// Max size = MAX_PEERS (125 entries × 8 bytes = 1KB).
    sent_nonces: Arc<RwLock<HashSet<u64>>>,

    /// Global subnet rate limiter (Erebus protection).
    ///
    /// Two-tier adaptive limiting:
    /// - Fast tier: Minute-scale DoS detection (bursts)
    /// - Slow tier: Day-scale Erebus detection (gradual subnet takeover)
    ///
    /// See rate_limit.rs for implementation details.
    subnet_limiter: Arc<RwLock<GlobalSubnetLimiter>>,
}

impl Network {
    pub async fn new(config: NetConfig) -> Result<(Self, mpsc::Receiver<NetEvent>), NetError> {
        let (event_tx, event_rx) = mpsc::channel(10000);

        let keypair = load_or_generate_keypair(&config.data_dir)?;
        info!(
            "Noise keypair loaded, pubkey: {}",
            super::encrypted::pubkey_fingerprint(&keypair.public)
        );

        let addr_path = config.data_dir.join("addresses.dat");
        let addresses = if addr_path.exists() {
            AddrMan::load(&addr_path).unwrap_or_else(|e| {
                warn!("Failed to load addresses: {}", e);
                AddrMan::new()
            })
        } else {
            AddrMan::new()
        };

        let connections = ConnectionManager::with_limits(config.max_outbound, config.max_inbound);

        let initial_local_addr = config.external_ip.map(|ip| {
            info!("Using external IP: {}", ip);
            NetAddress::new(ip, config.listen_port, config.services)
        });

        let network = Self {
            config,
            keypair: Arc::new(keypair),
            peers: Arc::new(RwLock::new(HashMap::new())),
            addresses: Arc::new(RwLock::new(addresses)),
            connections: Arc::new(connections),
            inventory: Arc::new(RwLock::new(Inventory::new())),
            event_tx,
            best_slice: Arc::new(RwLock::new(0)),
            local_addr: Arc::new(RwLock::new(initial_local_addr)),
            shutdown: Arc::new(RwLock::new(false)),
            ip_votes: Arc::new(RwLock::new(HashMap::new())),
            sent_nonces: Arc::new(RwLock::new(HashSet::new())),
            subnet_limiter: Arc::new(RwLock::new(GlobalSubnetLimiter::new())),
        };

        Ok((network, event_rx))
    }

    pub async fn start(&self) -> Result<(), NetError> {
        let listener = TcpListener::bind(format!("0.0.0.0:{}", self.config.listen_port)).await?;
        info!("Listening on port {}", self.config.listen_port);

        let peers = self.peers.clone();
        let addresses = self.addresses.clone();
        let connections = self.connections.clone();
        let inventory = self.inventory.clone();
        let event_tx = self.event_tx.clone();
        let config = self.config.clone();
        let keypair = self.keypair.clone();
        let best_slice = self.best_slice.clone();
        let local_addr = self.local_addr.clone();
        let shutdown = self.shutdown.clone();
        let ip_votes = self.ip_votes.clone();
        let sent_nonces = self.sent_nonces.clone();
        let subnet_limiter = self.subnet_limiter.clone();

        tokio::spawn(async move {
            Self::listener_loop(
                listener,
                peers,
                addresses,
                connections,
                inventory,
                event_tx,
                config,
                keypair,
                best_slice,
                local_addr,
                shutdown,
                ip_votes,
                sent_nonces,
                subnet_limiter,
            )
            .await;
        });

        let peers = self.peers.clone();
        let addresses = self.addresses.clone();
        let connections = self.connections.clone();
        let inventory = self.inventory.clone();
        let event_tx = self.event_tx.clone();
        let config = self.config.clone();
        let keypair = self.keypair.clone();
        let best_slice = self.best_slice.clone();
        let local_addr = self.local_addr.clone();
        let shutdown = self.shutdown.clone();
        let ip_votes = self.ip_votes.clone();
        let sent_nonces = self.sent_nonces.clone();
        let subnet_limiter = self.subnet_limiter.clone();

        tokio::spawn(async move {
            Self::connection_loop(
                peers,
                addresses,
                connections,
                inventory,
                event_tx,
                config,
                keypair,
                best_slice,
                local_addr,
                shutdown,
                ip_votes,
                sent_nonces,
                subnet_limiter,
            )
            .await;
        });

        let peers = self.peers.clone();
        let addresses = self.addresses.clone();
        let connections = self.connections.clone();
        let inventory = self.inventory.clone();
        let config = self.config.clone();
        let shutdown = self.shutdown.clone();

        tokio::spawn(async move {
            Self::maintenance_loop(peers, addresses, connections, inventory, config, shutdown).await;
        });

        for seed in &self.config.seeds {
            if let Ok(addr) = seed.parse::<SocketAddr>() {
                let net_addr = NetAddress::from_socket_addr(addr, NODE_FULL);
                self.addresses.write().await.add_seed(net_addr);
            }
        }

        Ok(())
    }

    async fn listener_loop(
        listener: TcpListener,
        peers: Arc<RwLock<HashMap<SocketAddr, Peer>>>,
        addresses: Arc<RwLock<AddrMan>>,
        connections: Arc<ConnectionManager>,
        inventory: Arc<RwLock<Inventory>>,
        event_tx: mpsc::Sender<NetEvent>,
        config: NetConfig,
        keypair: Arc<StaticKeypair>,
        best_slice: Arc<RwLock<u64>>,
        local_addr: Arc<RwLock<Option<NetAddress>>>,
        shutdown: Arc<RwLock<bool>>,
        ip_votes: Arc<RwLock<HashMap<SocketAddr, IpAddr>>>,
        sent_nonces: Arc<RwLock<HashSet<u64>>>,
        subnet_limiter: Arc<RwLock<GlobalSubnetLimiter>>,
    ) {
        loop {
            if *shutdown.read().await {
                break;
            }

            match listener.accept().await {
                Ok((stream, addr)) => {
                    if connections.is_banned(&addr).await {
                        debug!("Rejected banned peer: {}", addr);
                        continue;
                    }

                    // Erebus protection: two-tier adaptive subnet rate limiting
                    // Fast tier: minute-scale DoS protection
                    // Slow tier: day-scale Erebus attack protection
                    let now_secs = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map(|d| d.as_secs())
                        .unwrap_or(0);

                    if !subnet_limiter.write().await.check(addr.ip(), now_secs) {
                        debug!("Subnet rate limit exceeded, rejecting: {}", addr);
                        continue;
                    }

                    if !connections.can_accept_inbound() {
                        let peer_infos: Vec<_> = peers.read().await.values()
                            .map(super::peer::PeerInfo::from)
                            .collect();

                        if let Some(evict_addr) = super::eviction::select_peer_to_evict(&peer_infos) {
                            info!("Evicting {} to accept new inbound from {}", evict_addr, addr);

                            if let Some(evicted_peer) = peers.write().await.remove(&evict_addr) {
                                drop(evicted_peer.tx);
                            }
                            connections.remove_peer(&evict_addr, true).await;
                        } else {
                            debug!("Max inbound reached, all protected, rejecting: {}", addr);
                            continue;
                        }
                    }

                    if !connections.can_connect(&addr).await {
                        debug!("Netgroup limit reached, rejecting: {}", addr);
                        continue;
                    }

                    if !connections.can_accept_from_ip(&addr).await {
                        debug!("Per-IP limit reached, rejecting: {}", addr);
                        continue;
                    }

                    info!("Incoming connection from {}", addr);
                    connections.add_inbound(&addr).await;

                    let peers = peers.clone();
                    let addresses = addresses.clone();
                    let connections = connections.clone();
                    let inventory = inventory.clone();
                    let event_tx = event_tx.clone();
                    let config = config.clone();
                    let keypair = keypair.clone();
                    let best_slice = best_slice.clone();
                    let local_addr = local_addr.clone();
                    let ip_votes = ip_votes.clone();
                    let sent_nonces = sent_nonces.clone();

                    tokio::spawn(async move {
                        if let Err(e) = Self::handle_connection(
                            stream,
                            addr,
                            true,
                            peers,
                            addresses,
                            connections.clone(),
                            inventory,
                            event_tx,
                            config,
                            keypair,
                            best_slice,
                            local_addr,
                            ip_votes,
                            sent_nonces,
                        )
                        .await
                        {
                            debug!("Connection error from {}: {}", addr, e);
                        }
                        connections.remove_peer(&addr, true).await;
                    });
                }
                Err(e) => {
                    error!("Accept error: {}", e);
                }
            }
        }
    }

    async fn connection_loop(
        peers: Arc<RwLock<HashMap<SocketAddr, Peer>>>,
        addresses: Arc<RwLock<AddrMan>>,
        connections: Arc<ConnectionManager>,
        inventory: Arc<RwLock<Inventory>>,
        event_tx: mpsc::Sender<NetEvent>,
        config: NetConfig,
        keypair: Arc<StaticKeypair>,
        best_slice: Arc<RwLock<u64>>,
        local_addr: Arc<RwLock<Option<NetAddress>>>,
        shutdown: Arc<RwLock<bool>>,
        ip_votes: Arc<RwLock<HashMap<SocketAddr, IpAddr>>>,
        sent_nonces: Arc<RwLock<HashSet<u64>>>,
        subnet_limiter: Arc<RwLock<GlobalSubnetLimiter>>,
    ) {
        let mut interval = interval(Duration::from_secs(5));

        loop {
            interval.tick().await;

            if *shutdown.read().await {
                break;
            }

            if !connections.need_outbound() {
                continue;
            }

            let net_addr = {
                let mut addrman = addresses.write().await;
                match addrman.select() {
                    Some(addr) => addr,
                    None => continue,
                }
            };

            let socket_addr = net_addr.socket_addr();

            if peers.read().await.contains_key(&socket_addr) {
                continue;
            }

            if connections.is_banned(&socket_addr).await {
                continue;
            }

            // Erebus protection for outbound: prevent connecting to too many peers
            // from the same subnet (attacker could poison AddrMan with many IPs)
            let now_secs = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0);

            if !subnet_limiter.write().await.check(socket_addr.ip(), now_secs) {
                debug!("Subnet rate limit for outbound, skipping: {}", socket_addr);
                continue;
            }

            if !connections.can_connect(&socket_addr).await {
                continue;
            }

            if !connections.can_accept_from_ip(&socket_addr).await {
                continue;
            }

            if !connections.can_retry(&socket_addr).await {
                continue;
            }

            if !connections.start_connecting(socket_addr).await {
                continue;
            }

            info!("Connecting to {}", socket_addr);

            let connect_result = tokio::time::timeout(
                Duration::from_secs(HANDSHAKE_TIMEOUT_SECS),
                TcpStream::connect(socket_addr),
            )
            .await;

            connections.finish_connecting(&socket_addr).await;

            match connect_result {
                Ok(Ok(stream)) => {
                    info!("TCP connected to {}", socket_addr);
                    connections.add_outbound(&socket_addr).await;
                    connections.record_success(&socket_addr).await;

                    let peers = peers.clone();
                    let addresses = addresses.clone();
                    let connections = connections.clone();
                    let inventory = inventory.clone();
                    let event_tx = event_tx.clone();
                    let config = config.clone();
                    let keypair = keypair.clone();
                    let best_slice = best_slice.clone();
                    let local_addr = local_addr.clone();
                    let ip_votes = ip_votes.clone();
                    let sent_nonces = sent_nonces.clone();

                    tokio::spawn(async move {
                        if let Err(e) = Self::handle_connection(
                            stream,
                            socket_addr,
                            false,
                            peers,
                            addresses.clone(),
                            connections.clone(),
                            inventory,
                            event_tx,
                            config,
                            keypair,
                            best_slice,
                            local_addr,
                            ip_votes,
                            sent_nonces,
                        )
                        .await
                        {
                            debug!("Connection error to {}: {}", socket_addr, e);
                            addresses.write().await.mark_failed(&socket_addr);
                        }
                        connections.remove_peer(&socket_addr, false).await;
                        addresses.write().await.mark_disconnected(&socket_addr);
                    });
                }
                Ok(Err(e)) => {
                    debug!("Connect failed to {}: {}", socket_addr, e);
                    connections.record_failure(&socket_addr).await;
                    addresses.write().await.mark_failed(&socket_addr);
                }
                Err(_) => {
                    debug!("Connect timeout to {}", socket_addr);
                    connections.record_failure(&socket_addr).await;
                    addresses.write().await.mark_failed(&socket_addr);
                }
            }
        }
    }

    async fn maintenance_loop(
        peers: Arc<RwLock<HashMap<SocketAddr, Peer>>>,
        addresses: Arc<RwLock<AddrMan>>,
        connections: Arc<ConnectionManager>,
        inventory: Arc<RwLock<Inventory>>,
        config: NetConfig,
        shutdown: Arc<RwLock<bool>>,
    ) {
        let mut interval = interval(Duration::from_secs(60));

        loop {
            interval.tick().await;

            if *shutdown.read().await {
                break;
            }

            inventory.write().await.expire();
            addresses.write().await.expire();
            connections.expire_bans().await;

            let addr_path = config.data_dir.join("addresses.dat");
            if let Err(e) = addresses.read().await.save(&addr_path) {
                warn!("Failed to save addresses: {}", e);
            }

            let ban_path = config.data_dir.join("banlist.dat");
            if let Err(e) = connections.save_bans(&ban_path).await {
                warn!("Failed to save ban list: {}", e);
            }

            let peers_read = peers.read().await;
            for peer in peers_read.values() {
                if peer.is_ready() && peer.needs_ping() {
                    let nonce = rand::random();
                    let _ = peer.tx.send(Message::Ping(nonce)).await;
                }
            }
        }
    }

    async fn handle_connection(
        stream: TcpStream,
        addr: SocketAddr,
        inbound: bool,
        peers: Arc<RwLock<HashMap<SocketAddr, Peer>>>,
        addresses: Arc<RwLock<AddrMan>>,
        connections: Arc<ConnectionManager>,
        inventory: Arc<RwLock<Inventory>>,
        event_tx: mpsc::Sender<NetEvent>,
        config: NetConfig,
        keypair: Arc<StaticKeypair>,
        best_slice: Arc<RwLock<u64>>,
        local_addr: Arc<RwLock<Option<NetAddress>>>,
        ip_votes: Arc<RwLock<HashMap<SocketAddr, IpAddr>>>,
        sent_nonces: Arc<RwLock<HashSet<u64>>>,
    ) -> Result<(), NetError> {
        let noise_timeout = Duration::from_secs(super::encrypted::NOISE_HANDSHAKE_TIMEOUT_SECS);

        let encrypted_result = if inbound {
            tokio::time::timeout(noise_timeout, EncryptedStream::accept(stream, &keypair)).await
        } else {
            tokio::time::timeout(noise_timeout, EncryptedStream::connect(stream, &keypair)).await
        };

        let encrypted = match encrypted_result {
            Ok(Ok(enc)) => {
                info!(
                    "Noise handshake complete with {} (remote: {})",
                    addr,
                    enc.remote_pubkey
                        .map(|pk| super::encrypted::pubkey_fingerprint(&pk))
                        .unwrap_or_else(|| "unknown".into())
                );
                enc
            }
            Ok(Err(e)) => {
                debug!("Noise handshake failed with {}: {}", addr, e);
                return Err(NetError::NoiseHandshake(e.to_string()));
            }
            Err(_) => {
                debug!("Noise handshake timeout with {}", addr);
                return Err(NetError::HandshakeTimeout);
            }
        };

        let (peer_tx, mut peer_rx) = mpsc::channel::<Message>(1000);
        let (mut enc_reader, mut enc_writer) = encrypted.split();
        let mut peer = Peer::new(addr, inbound, peer_tx.clone());
        let mut our_sent_nonce: Option<u64> = None;

        let addr_clone = addr;
        tokio::spawn(async move {
            while let Some(msg) = peer_rx.recv().await {
                if let Err(e) = Self::write_message_encrypted(&mut enc_writer, &msg).await {
                    debug!("Write error to {}: {}", addr_clone, e);
                    break;
                }
            }
        });

        if !inbound {
            let local = local_addr.read().await.clone().unwrap_or_else(|| {
                NetAddress::new(
                    "0.0.0.0".parse().unwrap(),
                    config.listen_port,
                    config.services,
                )
            });

            let version = VersionPayload::new(
                config.services,
                NetAddress::from_socket_addr(addr, 0),
                local,
                *best_slice.read().await,
                config.node_type,
            );

            // Store nonce for self-connection detection
            sent_nonces.write().await.insert(version.nonce);
            our_sent_nonce = Some(version.nonce);

            peer_tx.send(Message::Version(version)).await.map_err(|_| {
                NetError::Protocol("Failed to send version".into())
            })?;
        }

        let handshake_deadline = tokio::time::Instant::now()
            + Duration::from_secs(HANDSHAKE_TIMEOUT_SECS);

        /// 50 pauses × 100ms = 5s max wait; prevents memory exhaustion
        const MAX_FLOW_CONTROL_PAUSES: u32 = 50;
        let mut flow_control_pauses: u32 = 0;

        loop {
            if !peer.is_ready() && tokio::time::Instant::now() > handshake_deadline {
                return Err(NetError::HandshakeTimeout);
            }

            if peer.flow_control.should_pause_recv() {
                flow_control_pauses += 1;
                if flow_control_pauses >= MAX_FLOW_CONTROL_PAUSES {
                    warn!("Flow control: disconnecting {} after {} pauses (queue: {} bytes)",
                          addr, flow_control_pauses, peer.flow_control.recv_queue_size);
                    break;
                }
                debug!("Flow control: delaying read from {} ({}/{})",
                       addr, flow_control_pauses, MAX_FLOW_CONTROL_PAUSES);
                tokio::time::sleep(Duration::from_millis(100)).await;
                continue;
            }
            flow_control_pauses = 0;

            let read_result = if peer.is_ready() {
                Self::read_message_encrypted(&mut enc_reader).await
            } else {
                tokio::time::timeout(
                    Duration::from_secs(30),
                    Self::read_message_encrypted(&mut enc_reader),
                )
                .await
                .map_err(|_| NetError::HandshakeTimeout)?
            };

            let (msg, wire_size) = match read_result {
                Ok((msg, size)) => (msg, size),
                Err(e) => {
                    debug!("Read error from {}: {}", addr, e);
                    break;
                }
            };

            let result = Self::process_message(
                &mut peer,
                msg,
                wire_size,
                &peer_tx,
                &peers,
                &addresses,
                &connections,
                &inventory,
                &event_tx,
                &config,
                &best_slice,
                &local_addr,
                &ip_votes,
                &sent_nonces,
                &mut our_sent_nonce,
            )
            .await;

            match result {
                Ok(true) => {
                    peers.write().await.insert(addr, Peer::new_ready(addr, inbound, peer_tx.clone()));
                    let _ = event_tx.send(NetEvent::PeerConnected(addr)).await;
                }
                Ok(false) => {}
                Err(e) => {
                    if peer.misbehaving(20, &e.to_string()) {
                        connections.ban_default(addr).await;
                        break;
                    }
                }
            }
        }

        peers.write().await.remove(&addr);
        let _ = event_tx.send(NetEvent::PeerDisconnected(addr)).await;

        if let Some(nonce) = our_sent_nonce {
            sent_nonces.write().await.remove(&nonce);
        }

        Ok(())
    }

    /// Process a single message
    async fn process_message(
        peer: &mut Peer,
        msg: Message,
        wire_size: usize,
        peer_tx: &mpsc::Sender<Message>,
        peers: &Arc<RwLock<HashMap<SocketAddr, Peer>>>,
        addresses: &Arc<RwLock<AddrMan>>,
        _connections: &Arc<ConnectionManager>,
        inventory: &Arc<RwLock<Inventory>>,
        event_tx: &mpsc::Sender<NetEvent>,
        config: &NetConfig,
        best_slice: &Arc<RwLock<u64>>,
        local_addr: &Arc<RwLock<Option<NetAddress>>>,
        ip_votes: &Arc<RwLock<HashMap<SocketAddr, IpAddr>>>,
        sent_nonces: &Arc<RwLock<HashSet<u64>>>,
        our_sent_nonce: &mut Option<u64>,
    ) -> Result<bool, NetError> {

        if !peer.is_ready() && !msg.allowed_pre_handshake() {
            return Err(NetError::Protocol("Message not allowed before handshake".into()));
        }

        peer.flow_control.add_recv(wire_size);
        let result: Result<bool, NetError> = (async {
            let mut just_connected = false;

            match msg {
            Message::Version(version) => {
                if version.version < PROTOCOL_VERSION {
                    return Err(NetError::Protocol("Obsolete version".into()));
                }

                if sent_nonces.read().await.contains(&version.nonce) {
                    warn!("Self-connection detected (nonce match), disconnecting {}", peer.addr);
                    return Err(NetError::Protocol("Self-connection detected".into()));
                }

                // Only outbound votes count; inbound could be Sybil
                let their_view_of_us = version.addr_recv.ip;
                if !peer.inbound
                    && !their_view_of_us.is_loopback()
                    && !their_view_of_us.is_unspecified()
                {
                    // Single lock for insert + count (cleaner, no functional difference)
                    let votes = ip_votes.read().await;
                    let mut ip_counts: HashMap<IpAddr, usize> = HashMap::new();
                    for ip in votes.values() {
                        *ip_counts.entry(*ip).or_insert(0) += 1;
                    }
                    *ip_counts.entry(their_view_of_us).or_insert(0) += 1;
                    drop(votes);

                    // Now persist the vote
                    ip_votes.write().await.insert(peer.addr, their_view_of_us);

                    if let Some((consensus_ip, count)) = ip_counts.iter().max_by_key(|(_, c)| *c)
                        && *count >= MIN_IP_VOTES
                    {
                        let mut local = local_addr.write().await;
                        let should_update = match &*local {
                            None => true,
                            Some(addr) => addr.ip != *consensus_ip,
                        };
                        if should_update {
                            info!("External IP discovered: {} ({} peers agree)", consensus_ip, count);
                            *local = Some(NetAddress::new(*consensus_ip, config.listen_port, config.services));
                        }
                    }
                }

                peer.apply_version(&version);

                peer_tx.send(Message::Verack).await.map_err(|_| {
                    NetError::Protocol("Failed to send verack".into())
                })?;

                if peer.inbound {
                    let local = local_addr.read().await.clone().unwrap_or_else(|| {
                        NetAddress::new(
                            "0.0.0.0".parse().unwrap(),
                            config.listen_port,
                            config.services,
                        )
                    });

                    let our_version = VersionPayload::new(
                        config.services,
                        NetAddress::from_socket_addr(peer.addr, version.services),
                        local,
                        *best_slice.read().await,
                        config.node_type,
                    );

                    sent_nonces.write().await.insert(our_version.nonce);
                    *our_sent_nonce = Some(our_version.nonce);

                    peer_tx.send(Message::Version(our_version)).await.map_err(|_| {
                        NetError::Protocol("Failed to send version".into())
                    })?;
                }
            }

            Message::Verack => {
                peer.handshake_complete();
                just_connected = true;

                // After handshake to prevent TRIED table poisoning
                addresses.write().await.mark_connected(&peer.addr);

                info!(
                    "Handshake complete with {} ({}bound, services={})",
                    peer.addr,
                    if peer.inbound { "in" } else { "out" },
                    peer.services
                );

                let our_best = *best_slice.read().await;
                if peer.best_known_slice > our_best {
                    let _ = event_tx
                        .send(NetEvent::PeerAhead(peer.addr, peer.best_known_slice))
                        .await;
                }
            }

            Message::Addr(addrs) => {
                if addrs.len() > MAX_ADDR_SIZE {
                    return Err(NetError::Protocol("Too many addresses".into()));
                }

                let allowed = peer.rate_limits.addr.process(addrs.len());
                if allowed == 0 {
                    debug!("Rate limited addr from {}", peer.addr);
                    return Ok(false);
                }

                let to_process: Vec<_> = addrs.into_iter().take(allowed).collect();
                let added = addresses.write().await.add_many(to_process, peer.addr);
                debug!("Added {} addresses from {} (rate limited to {})", added, peer.addr, allowed);
            }

            Message::GetAddr => {
                let addrs_vec = addresses.read().await.get_addr(MAX_ADDR_SIZE);
                if !addrs_vec.is_empty() {
                    let addrs = Addrs::new_unchecked(addrs_vec.clone());
                    if let Some(ref secret_key) = config.hardcoded_secret_key {
                        let addrs_bytes = bincode::serialize(&addrs_vec).unwrap_or_default();
                        if let Some(sig) = crate::crypto::sign_mldsa65(secret_key, &addrs_bytes) {
                            let signature = Signature::new_unchecked(sig);
                            peer_tx.send(Message::SignedAddr { addrs, signature }).await.ok();
                        } else {
                            warn!("Failed to sign Addr message, sending unsigned");
                            peer_tx.send(Message::Addr(addrs)).await.ok();
                        }
                    } else {
                        peer_tx.send(Message::Addr(addrs)).await.ok();
                    }
                }
            }

            Message::Inv(items) => {
                if items.len() > MAX_INV_SIZE {
                    return Err(NetError::Protocol("Too many inv items".into()));
                }

                if !peer.rate_limits.inv.try_consume(items.len()) {
                    debug!("Rate limited inv from {} ({} items)", peer.addr, items.len());
                    return Ok(false);
                }

                for item in items.iter() {
                    peer.add_known_inv(item.hash);
                }

                let needed = inventory.read().await.filter_needed(&*items);
                if !needed.is_empty() {
                    let requested = inventory.write().await.request_batch(&needed, peer.addr);
                    if !requested.is_empty() {
                        peer_tx.send(Message::GetData(InvItems::new_unchecked(requested))).await.ok();
                    }
                }
            }

            Message::GetData(items) => {
                if items.len() > MAX_GETDATA_SIZE {
                    return Err(NetError::Protocol("Too many getdata items".into()));
                }

                if !peer.rate_limits.getdata.try_consume(items.len()) {
                    debug!("Rate limited getdata from {} ({} items)", peer.addr, items.len());
                    return Ok(false);
                }

                let mut not_found = Vec::new();

                for item in items.iter() {
                    if let Some(data) = inventory.read().await.get_relay(&item.hash) {
                        match item.inv_type {
                            InvType::Slice => {
                                if let Ok(slice) = bincode::deserialize::<Slice>(data) {
                                    peer_tx.send(Message::Slice(Box::new(slice))).await.ok();
                                } else {
                                    not_found.push(item.clone());
                                }
                            }
                            InvType::Tx => {
                                if let Ok(tx) = bincode::deserialize::<Transaction>(data) {
                                    peer_tx.send(Message::Tx(Box::new(tx))).await.ok();
                                } else {
                                    not_found.push(item.clone());
                                }
                            }
                            InvType::Presence => {
                                if let Ok(presence) = bincode::deserialize::<PresenceProof>(data) {
                                    peer_tx.send(Message::Presence(Box::new(presence))).await.ok();
                                } else {
                                    not_found.push(item.clone());
                                }
                            }
                        }
                    } else {
                        not_found.push(item.clone());
                    }
                }

                if !not_found.is_empty() {
                    peer_tx.send(Message::NotFound(InvItems::new_unchecked(not_found))).await.ok();
                }
            }

            Message::NotFound(items) => {
                for item in items.iter() {
                    inventory.write().await.received(&item.hash);
                }
            }

            Message::Slice(slice) => {
                if !peer.rate_limits.slice.try_consume() {
                    debug!("Rate limited slice from {}", peer.addr);
                    return Ok(false);
                }

                let hash = slice.hash();
                inventory.write().await.add_slice(hash);
                peer.add_known_inv(hash);
                peer.last_slice_time = now();

                let inv = InvItems::new_unchecked(vec![InvItem::slice(hash)]);
                let peers_read = peers.read().await;
                for (addr, p) in peers_read.iter() {
                    if *addr != peer.addr && !p.has_inv(&hash) {
                        p.tx.send(Message::Inv(inv.clone())).await.ok();
                    }
                }
                drop(peers_read);
                let _ = event_tx.send(NetEvent::Slice(peer.addr, slice)).await;
            }

            Message::Tx(tx) => {
                let hash = tx.hash();
                inventory.write().await.add_tx(hash);
                peer.add_known_inv(hash);
                peer.last_tx_time = now();

                let inv = InvItems::new_unchecked(vec![InvItem::tx(hash)]);
                let peers_read = peers.read().await;
                for (addr, p) in peers_read.iter() {
                    if *addr != peer.addr && !p.has_inv(&hash) {
                        p.tx.send(Message::Inv(inv.clone())).await.ok();
                    }
                }
                drop(peers_read);

                let _ = event_tx.send(NetEvent::Tx(peer.addr, tx)).await;
            }

            Message::Presence(presence) => {
                let hash = crate::crypto::sha3(&bincode::serialize(&*presence).unwrap_or_default());
                inventory.write().await.add_presence(hash);
                peer.add_known_inv(hash);

                let inv = InvItems::new_unchecked(vec![InvItem::presence(hash)]);
                let peers_read = peers.read().await;
                for (addr, p) in peers_read.iter() {
                    if *addr != peer.addr && !p.has_inv(&hash) {
                        p.tx.send(Message::Inv(inv.clone())).await.ok();
                    }
                }
                drop(peers_read);

                let _ = event_tx.send(NetEvent::Presence(peer.addr, presence)).await;
            }

            Message::GetSlice(index) => {
                let _ = event_tx.send(NetEvent::NeedSlices(peer.addr, index, 1)).await;
            }

            Message::GetSlices { start, count } => {
                if !peer.rate_limits.getslices.try_consume() {
                    debug!("Rate limited getslices from {}", peer.addr);
                    return Ok(false);
                }
                let count = count.min(500);
                let _ = event_tx.send(NetEvent::NeedSlices(peer.addr, start, count)).await;
            }

            Message::SliceHeaders(headers) => {
                if !peer.rate_limits.headers.try_consume(headers.len()) {
                    debug!("Rate limited headers from {} ({} headers)", peer.addr, headers.len());
                    return Ok(false);
                }
                debug!("Received {} slice headers from {}", headers.len(), peer.addr);
            }

            Message::Ping(nonce) => {
                peer_tx.send(Message::Pong(nonce)).await.ok();
            }

            Message::Pong(nonce) => {
                peer.complete_ping(nonce);
            }

            Message::Reject(reject) => {
                warn!(
                    "Peer {} rejected: {:?} - {}",
                    peer.addr, reject.code, reject.reason
                );
            }

            Message::AuthChallenge(challenge) => {
                // Rate limit check FIRST — prevents CPU exhaustion (Dilithium Storm)
                if !peer.rate_limits.auth_challenge.try_consume() {
                    debug!("Rate limited AuthChallenge from {}", peer.addr);
                    return Ok(false);
                }

                if let Some(ref secret_key) = config.hardcoded_secret_key {
                    // Clone for move into spawn_blocking
                    let sk = secret_key.clone();
                    let ch = challenge.clone();
                    let testnet = config.testnet;

                    // CRITICAL: Use spawn_blocking to avoid blocking async runtime
                    // ML-DSA-65 signing is CPU-intensive (~1-5ms)
                    let sig = tokio::task::spawn_blocking(move || {
                        // Domain separation: prevents cross-network replay attacks
                        // Format: "Montana.Auth.v1.<network>.<challenge>"
                        let network = if testnet { b"testnet" } else { b"mainnet" };
                        let mut msg = Vec::with_capacity(32 + 32);
                        msg.extend_from_slice(b"Montana.Auth.v1.");
                        msg.extend_from_slice(network);
                        msg.push(b'.');
                        msg.extend_from_slice(&ch);
                        crate::crypto::sign_mldsa65(&sk, &msg)
                    })
                    .await
                    .ok()
                    .flatten();

                    let sig = match sig {
                        Some(s) => s,
                        None => {
                            warn!("Failed to sign AuthChallenge (invalid secret key?)");
                            return Ok(false);
                        }
                    };

                    let local = local_addr.read().await.clone().unwrap_or_else(|| {
                        NetAddress::new(
                            "0.0.0.0".parse().unwrap(),
                            config.listen_port,
                            config.services,
                        )
                    });

                    let version = VersionPayload::new(
                        config.services,
                        NetAddress::from_socket_addr(peer.addr, 0),
                        local,
                        *best_slice.read().await,
                        config.node_type,
                    );

                    let signature = Signature::new_unchecked(sig);
                    info!("Responding to AuthChallenge from {}", peer.addr);
                    peer_tx.send(Message::AuthResponse { version, signature }).await.ok();
                }
            }

            Message::AuthResponse { .. } => {
                debug!("Unexpected AuthResponse from {}", peer.addr);
            }

            _ => {
                debug!("Unhandled message from {}: {}", peer.addr, msg.command());
            }
        }

            Ok(just_connected)
        })
        .await;

        peer.flow_control.remove_recv(wire_size);

        result
    }

    fn compute_checksum(data: &[u8]) -> [u8; 4] {
        let hash = crate::crypto::sha3(data);
        [hash[0], hash[1], hash[2], hash[3]]
    }

    /// Wire format: MAGIC (4) + LENGTH (4) + CHECKSUM (4) + PAYLOAD
    async fn write_message<W: AsyncWriteExt + Unpin>(
        writer: &mut W,
        msg: &Message,
    ) -> Result<(), NetError> {
        let data = postcard::to_allocvec(msg)?;
        let max_size = Message::max_size_for_command(msg.command());

        if data.len() > max_size {
            return Err(NetError::MessageTooLarge(data.len(), max_size));
        }

        let checksum = Self::compute_checksum(&data);

        writer.write_all(&PROTOCOL_MAGIC).await?;
        writer.write_all(&(data.len() as u32).to_le_bytes()).await?;
        writer.write_all(&checksum).await?;
        writer.write_all(&data).await?;
        writer.flush().await?;

        Ok(())
    }

    async fn read_message<R: AsyncReadExt + Unpin>(reader: &mut R) -> Result<Message, NetError> {
        let mut magic = [0u8; 4];
        reader.read_exact(&mut magic).await?;
        if magic != PROTOCOL_MAGIC {
            return Err(NetError::InvalidMagic);
        }

        let mut len_bytes = [0u8; 4];
        reader.read_exact(&mut len_bytes).await?;
        let len = u32::from_le_bytes(len_bytes) as usize;

        // Early size check prevents memory exhaustion
        if len > MAX_TX_SIZE {
            return Err(NetError::MessageTooLarge(len, MAX_TX_SIZE));
        }

        let mut checksum = [0u8; 4];
        reader.read_exact(&mut checksum).await?;

        let mut data = vec![0u8; len];
        reader.read_exact(&mut data).await?;

        let computed = Self::compute_checksum(&data);
        if computed != checksum {
            return Err(NetError::InvalidChecksum);
        }

        let msg: Message = postcard::from_bytes(&data)?;

        if !msg.validate_collection_sizes() {
            return Err(NetError::Protocol("collection size limit exceeded".into()));
        }

        let max_size = Message::max_size_for_command(msg.command());
        if len > max_size {
            return Err(NetError::MessageTooLarge(len, max_size));
        }

        Ok(msg)
    }

    async fn write_message_encrypted(
        writer: &mut super::encrypted::EncryptedWriter,
        msg: &Message,
    ) -> Result<(), NetError> {
        let data = postcard::to_allocvec(msg)?;
        let max_size = Message::max_size_for_command(msg.command());

        if data.len() > max_size {
            return Err(NetError::MessageTooLarge(data.len(), max_size));
        }

        let checksum = Self::compute_checksum(&data);

        let mut frame = Vec::with_capacity(12 + data.len());
        frame.extend_from_slice(&PROTOCOL_MAGIC);
        frame.extend_from_slice(&(data.len() as u32).to_le_bytes());
        frame.extend_from_slice(&checksum);
        frame.extend_from_slice(&data);

        writer.write(&frame).await?;

        Ok(())
    }

    async fn read_message_encrypted(
        reader: &mut super::encrypted::EncryptedReader,
    ) -> Result<(Message, usize), NetError> {
        let frame = reader.read().await?;
        let wire_size = frame.len();

        if wire_size < 12 {
            return Err(NetError::Protocol("frame too short".into()));
        }

        let magic = [frame[0], frame[1], frame[2], frame[3]];
        if magic != PROTOCOL_MAGIC {
            return Err(NetError::InvalidMagic);
        }

        let len_bytes = [frame[4], frame[5], frame[6], frame[7]];
        let len = u32::from_le_bytes(len_bytes) as usize;

        if len > MAX_TX_SIZE {
            return Err(NetError::MessageTooLarge(len, MAX_TX_SIZE));
        }

        if wire_size < 12 + len {
            return Err(NetError::Protocol("incomplete frame".into()));
        }

        let checksum = [frame[8], frame[9], frame[10], frame[11]];
        let data = &frame[12..12 + len];

        let computed = Self::compute_checksum(data);
        if computed != checksum {
            return Err(NetError::InvalidChecksum);
        }

        let msg: Message = postcard::from_bytes(data)?;

        if !msg.validate_collection_sizes() {
            return Err(NetError::Protocol("collection size limit exceeded".into()));
        }

        let max_size = Message::max_size_for_command(msg.command());
        if len > max_size {
            return Err(NetError::MessageTooLarge(len, max_size));
        }

        Ok((msg, wire_size))
    }

    pub async fn set_best_slice(&self, index: u64) {
        *self.best_slice.write().await = index;
    }

    pub async fn get_best_slice(&self) -> u64 {
        *self.best_slice.read().await
    }

    pub async fn broadcast_slice(&self, slice: &Slice) {
        let hash = slice.hash();
        self.inventory.write().await.add_slice(hash);
        let data = bincode::serialize(slice).unwrap_or_default();
        self.inventory.write().await.cache_relay(hash, data);

        let msg = Message::Slice(Box::new(slice.clone()));
        let peers = self.peers.read().await;
        for peer in peers.values() {
            if peer.is_ready() && !peer.has_inv(&hash) {
                peer.tx.send(msg.clone()).await.ok();
            }
        }
    }

    pub async fn broadcast_tx(&self, tx: &Transaction) {
        let hash = tx.hash();
        self.inventory.write().await.add_tx(hash);
        let data = bincode::serialize(tx).unwrap_or_default();
        self.inventory.write().await.cache_relay(hash, data);

        let msg = Message::Tx(Box::new(tx.clone()));
        let peers = self.peers.read().await;
        for peer in peers.values() {
            if peer.is_ready() && !peer.has_inv(&hash) {
                peer.tx.send(msg.clone()).await.ok();
            }
        }
    }

    pub async fn broadcast_presence(&self, presence: &PresenceProof) {
        let data = bincode::serialize(presence).unwrap_or_default();
        let hash = crate::crypto::sha3(&data);
        self.inventory.write().await.add_presence(hash);
        self.inventory.write().await.cache_relay(hash, data);

        let msg = Message::Presence(Box::new(presence.clone()));
        let peers = self.peers.read().await;
        for peer in peers.values() {
            if peer.is_ready() && !peer.has_inv(&hash) {
                peer.tx.send(msg.clone()).await.ok();
            }
        }
    }

    pub async fn send_slice(&self, peer: &SocketAddr, slice: Slice) {
        if let Some(p) = self.peers.read().await.get(peer) {
            p.tx.send(Message::Slice(Box::new(slice))).await.ok();
        }
    }

    pub async fn request_slices(&self, peer: &SocketAddr, start: u64, count: u64) {
        if let Some(p) = self.peers.read().await.get(peer) {
            p.tx.send(Message::GetSlices { start, count }).await.ok();
        }
    }

    pub async fn peer_count(&self) -> usize {
        self.peers.read().await.len()
    }

    pub async fn addr_stats(&self) -> (usize, usize) {
        self.addresses.read().await.size()
    }

    pub async fn get_peers(&self) -> Vec<PeerInfo> {
        self.peers
            .read()
            .await
            .values()
            .map(PeerInfo::from)
            .collect()
    }

    pub async fn add_seed(&self, addr: &str) {
        if let Ok(socket_addr) = addr.parse::<SocketAddr>() {
            let net_addr = NetAddress::from_socket_addr(socket_addr, NODE_FULL);
            self.addresses.write().await.add(net_addr, None);
        }
    }

    pub async fn shutdown(&self) {
        *self.shutdown.write().await = true;

        let addr_path = self.config.data_dir.join("addresses.dat");
        if let Err(e) = self.addresses.read().await.save(&addr_path) {
            warn!("Failed to save addresses on shutdown: {}", e);
        }

        let ban_path = self.config.data_dir.join("banlist.dat");
        if let Err(e) = self.connections.save_bans(&ban_path).await {
            warn!("Failed to save ban list on shutdown: {}", e);
        }
    }

    pub async fn load_state(&self) -> Result<(), NetError> {
        let addr_path = self.config.data_dir.join("addresses.dat");
        if addr_path.exists() {
            match super::addrman::AddrMan::load(&addr_path) {
                Ok(loaded) => {
                    *self.addresses.write().await = loaded;
                    info!("Loaded {} addresses", self.addresses.read().await.len());
                }
                Err(e) => {
                    warn!("Failed to load addresses: {}", e);
                }
            }
        }

        let ban_path = self.config.data_dir.join("banlist.dat");
        if ban_path.exists() {
            if let Err(e) = self.connections.load_bans(&ban_path).await {
                warn!("Failed to load ban list: {}", e);
            } else {
                let stats = self.connections.stats().await;
                info!("Loaded {} bans", stats.banned);
            }
        }

        Ok(())
    }

    pub async fn connection_stats(&self) -> super::connection::ConnectionStats {
        self.connections.stats().await
    }

    /// Get subnet limiter statistics for monitoring
    /// Shows fast tier (DoS protection) and slow tier (Erebus protection) stats
    pub async fn subnet_limiter_stats(&self) -> super::rate_limit::GlobalSubnetStats {
        self.subnet_limiter.read().await.stats()
    }

    /// Reset subnet limiter counters (for testing/monitoring)
    pub async fn reset_subnet_limiter_counters(&self) {
        self.subnet_limiter.write().await.reset_counters();
    }
}
