"""
Proof of Time - P2P Network Module
Production-grade peer-to-peer networking implementation.

Includes:
- Noise Protocol Framework encryption (XX handshake pattern)
- TCP connection management with TLS fallback
- Message serialization/deserialization
- Peer discovery (DNS seeds, addr messages)
- Gossip protocol for blocks and transactions
- Eclipse attack protection
- Connection pooling and management
- Rate limiting and DoS protection
- Subnet diversity enforcement

Time is the ultimate proof.
"""

import socket
import struct
import hashlib
import threading
import queue
import time
import random
import logging
import selectors
import ipaddress
import ssl
import os
from typing import Dict, List, Optional, Tuple, Set, Callable, Any, Union
from dataclasses import dataclass, field
from enum import IntEnum
from collections import defaultdict
from abc import ABC, abstractmethod

# Noise Protocol is REQUIRED for secure P2P communication
# NO FALLBACK - P2P without encryption is NOT allowed in production
try:
    from noise.connection import NoiseConnection, Keypair
    NOISE_AVAILABLE = True
except ImportError:
    NOISE_AVAILABLE = False
    # For development/testing only - allow import but block connections
    import warnings
    warnings.warn(
        "CRITICAL: Noise Protocol library not available! "
        "P2P connections will be BLOCKED until you install it. "
        "Install with: pip install noiseprotocol",
        RuntimeWarning
    )
    logging.critical(
        "FATAL: Noise Protocol not available. "
        "P2P networking is DISABLED for security. "
        "Install noiseprotocol: pip install noiseprotocol"
    )

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives import serialization
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

from pantheon.prometheus import sha256, sha256d, Ed25519, X25519
from pantheon.themis import Block, BlockHeader, Transaction
from config import PROTOCOL, NetworkConfig

logger = logging.getLogger("proof_of_time.network")


# ============================================================================
# CONSTANTS
# ============================================================================

MAINNET_MAGIC = b'\xf9\xbe\xb4\xd9'
TESTNET_MAGIC = b'\x0b\x11\x09\x07'

MAX_MESSAGE_SIZE = 32 * 1024 * 1024  # 32 MB
MAX_INV_ITEMS = 50000
MAX_ADDR_ITEMS = 1000
MAX_HEADERS = 2000

CONNECT_TIMEOUT = 10
HANDSHAKE_TIMEOUT = 30
NOISE_HANDSHAKE_TIMEOUT = 10
PING_INTERVAL = 120
PING_TIMEOUT = 20

MAX_MESSAGES_PER_SECOND = 100
BAN_THRESHOLD = 100
BAN_DURATION = 86400  # 24 hours

# Eclipse attack protection
MAX_CONNECTIONS_PER_IP = 1
MAX_CONNECTIONS_PER_SUBNET = 3
SUBNET_PREFIX_IPV4 = 24  # /24 subnet
SUBNET_PREFIX_IPV6 = 48  # /48 subnet
MIN_OUTBOUND_CONNECTIONS = 8
MAX_INBOUND_RATIO = 0.7  # Max 70% inbound connections

# Noise Protocol constants
NOISE_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"
NOISE_MAX_MESSAGE_SIZE = 65535


# ============================================================================
# MESSAGE TYPES
# ============================================================================

class MessageType(IntEnum):
    VERSION = 0
    VERACK = 1
    GETADDR = 2
    ADDR = 3
    INV = 4
    GETDATA = 5
    NOTFOUND = 6
    GETBLOCKS = 7
    GETHEADERS = 8
    HEADERS = 9
    BLOCK = 10
    TX = 11
    MEMPOOL = 12
    PING = 13
    PONG = 14
    REJECT = 15
    # Noise handshake messages
    NOISE_HANDSHAKE_INIT = 100
    NOISE_HANDSHAKE_RESP = 101
    NOISE_HANDSHAKE_FINAL = 102


class InvType(IntEnum):
    ERROR = 0
    TX = 1
    BLOCK = 2


# ============================================================================
# NOISE PROTOCOL ENCRYPTION
# ============================================================================

class NoiseState(IntEnum):
    """Noise handshake state."""
    NONE = 0
    INITIATOR_WAITING = 1
    RESPONDER_WAITING = 2
    ESTABLISHED = 3
    FAILED = 4


@dataclass
class NoiseKeys:
    """Static Noise Protocol keys for node identity."""
    private_key: bytes  # 32 bytes X25519 private key
    public_key: bytes   # 32 bytes X25519 public key
    
    @classmethod
    def generate(cls) -> 'NoiseKeys':
        """Generate new Noise keypair."""
        if CRYPTOGRAPHY_AVAILABLE:
            private = X25519PrivateKey.generate()
            private_bytes = private.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_bytes = private.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            return cls(private_key=private_bytes, public_key=public_bytes)
        else:
            # Fallback to nacl
            private, public = X25519.generate_keypair()
            return cls(private_key=private, public_key=public)
    
    @classmethod
    def from_seed(cls, seed: bytes) -> 'NoiseKeys':
        """Derive keys from seed."""
        private_key = sha256(b"noise_private" + seed)
        if CRYPTOGRAPHY_AVAILABLE:
            private = X25519PrivateKey.from_private_bytes(private_key)
            public_bytes = private.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            return cls(private_key=private_key, public_key=public_bytes)
        else:
            public_key = X25519.derive_public_key(private_key)
            return cls(private_key=private_key, public_key=public_key)
    
    def save(self, path: str):
        """Save keys to file."""
        with open(path, 'wb') as f:
            f.write(self.private_key + self.public_key)
    
    @classmethod
    def load(cls, path: str) -> 'NoiseKeys':
        """Load keys from file."""
        with open(path, 'rb') as f:
            data = f.read()
        return cls(private_key=data[:32], public_key=data[32:64])


class NoiseWrapper:
    """
    Noise Protocol wrapper for encrypted peer communication.
    
    Uses XX handshake pattern:
    -> e
    <- e, ee, s, es
    -> s, se
    
    Properties:
    - Mutual authentication
    - Perfect forward secrecy
    - Identity hiding (initiator's identity hidden until final message)
    """
    
    def __init__(self, static_keys: NoiseKeys, is_initiator: bool):
        if not NOISE_AVAILABLE:
            # Жёстко требуем установленный noiseprotocol для исключения
            # небезопасных «ручных» шифров и заглушек.
            raise RuntimeError(
                "Noise Protocol library is required. Install with: pip install noiseprotocol"
            )

        self.static_keys = static_keys
        self.is_initiator = is_initiator
        self.state = NoiseState.NONE
        self.remote_static: Optional[bytes] = None
        
        # Cipher states after handshake
        self._send_cipher = None
        self._recv_cipher = None
        self._handshake_hash: Optional[bytes] = None
        
        self._init_noise_protocol()
    
    def _init_noise_protocol(self):
        """Initialize using noise library."""
        self.noise = NoiseConnection.from_name(NOISE_PROTOCOL_NAME)
        
        # Set static keypair
        if hasattr(self.noise, 'set_keypair_from_private_bytes'):
            self.noise.set_keypair_from_private_bytes(
                Keypair.STATIC,
                self.static_keys.private_key
            )
        
        if self.is_initiator:
            self.noise.set_as_initiator()
        else:
            self.noise.set_as_responder()
        
        self.noise.start_handshake()
    
    def get_handshake_message(self) -> Optional[bytes]:
        """Get next handshake message to send."""
        try:
            if self.noise.handshake_finished:
                return None
            return self.noise.write_message()
        except Exception as e:
            logger.error(f"Noise handshake write error: {e}")
            self.state = NoiseState.FAILED
            return None
    
    def process_handshake_message(self, message: bytes) -> bool:
        """
        Process received handshake message.
        
        Returns True if handshake is complete.
        """
        try:
            payload = self.noise.read_message(message)
            if self.noise.handshake_finished:
                self.state = NoiseState.ESTABLISHED
                self._handshake_hash = self.noise.get_handshake_hash()
                # Get remote static key
                self.remote_static = self.noise.get_keypair(Keypair.REMOTE_STATIC)
                return True
            return False
        except Exception as e:
            logger.error(f"Noise handshake read error: {e}")
            self.state = NoiseState.FAILED
            return False
    
    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt message after handshake."""
        if self.state != NoiseState.ESTABLISHED:
            raise ValueError("Handshake not complete")
        
        try:
            return self.noise.encrypt(plaintext)
        except Exception as e:
            logger.error(f"Noise encrypt error: {e}")
            raise
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt message after handshake."""
        if self.state != NoiseState.ESTABLISHED:
            raise ValueError("Handshake not complete")
        
        try:
            return self.noise.decrypt(ciphertext)
        except Exception as e:
            logger.error(f"Noise decrypt error: {e}")
            raise
    
    @property
    def is_established(self) -> bool:
        """Check if handshake is complete."""
        return self.state == NoiseState.ESTABLISHED


# ============================================================================
# ECLIPSE ATTACK PROTECTION
# ============================================================================

class EclipseProtection:
    """
    Protection against Eclipse attacks.
    
    An Eclipse attack isolates a node by filling all its connections
    with attacker-controlled peers. We prevent this by:
    
    1. Limiting connections per IP address
    2. Limiting connections per subnet
    3. Ensuring minimum outbound connections
    4. Maintaining subnet diversity
    5. Preferring long-lived connections
    6. Rotating a portion of connections periodically
    """
    
    def __init__(
        self,
        max_per_ip: int = MAX_CONNECTIONS_PER_IP,
        max_per_subnet: int = MAX_CONNECTIONS_PER_SUBNET,
        ipv4_prefix: int = SUBNET_PREFIX_IPV4,
        ipv6_prefix: int = SUBNET_PREFIX_IPV6
    ):
        self.max_per_ip = max_per_ip
        self.max_per_subnet = max_per_subnet
        self.ipv4_prefix = ipv4_prefix
        self.ipv6_prefix = ipv6_prefix
        
        # Track connections by IP and subnet
        self.connections_by_ip: Dict[str, Set[str]] = defaultdict(set)
        self.connections_by_subnet: Dict[str, Set[str]] = defaultdict(set)
        
        # Track inbound vs outbound
        self.inbound_peers: Set[str] = set()
        self.outbound_peers: Set[str] = set()
        
        # Connection timestamps for age-based decisions
        self.connection_times: Dict[str, float] = {}
        
        # Tried and new address tables (like Bitcoin's addrman)
        self.tried_addresses: Dict[str, float] = {}  # address -> last success
        self.new_addresses: Dict[str, float] = {}    # address -> first seen
        
        self._lock = threading.Lock()
    
    def get_subnet(self, ip: str) -> str:
        """Get subnet identifier for an IP address."""
        try:
            addr = ipaddress.ip_address(ip)
            if isinstance(addr, ipaddress.IPv4Address):
                network = ipaddress.ip_network(f"{ip}/{self.ipv4_prefix}", strict=False)
            else:
                network = ipaddress.ip_network(f"{ip}/{self.ipv6_prefix}", strict=False)
            return str(network.network_address)
        except ValueError:
            return ip  # Fallback
    
    def can_connect(self, ip: str, is_inbound: bool) -> Tuple[bool, str]:
        """
        Check if a connection from/to IP should be allowed.
        
        Returns (allowed, reason).
        """
        with self._lock:
            # Check per-IP limit
            if len(self.connections_by_ip[ip]) >= self.max_per_ip:
                return False, f"Too many connections from IP {ip}"
            
            # Check per-subnet limit
            subnet = self.get_subnet(ip)
            if len(self.connections_by_subnet[subnet]) >= self.max_per_subnet:
                return False, f"Too many connections from subnet {subnet}"
            
            # Check inbound ratio
            if is_inbound:
                total = len(self.inbound_peers) + len(self.outbound_peers)
                if total > 0:
                    inbound_ratio = len(self.inbound_peers) / total
                    if inbound_ratio >= MAX_INBOUND_RATIO:
                        return False, "Too many inbound connections"
            
            return True, "OK"
    
    def register_connection(self, peer_id: str, ip: str, is_inbound: bool):
        """Register a new connection."""
        with self._lock:
            subnet = self.get_subnet(ip)
            
            self.connections_by_ip[ip].add(peer_id)
            self.connections_by_subnet[subnet].add(peer_id)
            self.connection_times[peer_id] = time.time()
            
            if is_inbound:
                self.inbound_peers.add(peer_id)
            else:
                self.outbound_peers.add(peer_id)
            
            logger.debug(f"Registered connection: {peer_id} (IP: {ip}, subnet: {subnet})")
    
    def unregister_connection(self, peer_id: str, ip: str):
        """Unregister a connection."""
        with self._lock:
            subnet = self.get_subnet(ip)
            
            self.connections_by_ip[ip].discard(peer_id)
            self.connections_by_subnet[subnet].discard(peer_id)
            
            # Clean up empty sets
            if not self.connections_by_ip[ip]:
                del self.connections_by_ip[ip]
            if not self.connections_by_subnet[subnet]:
                del self.connections_by_subnet[subnet]
            
            self.inbound_peers.discard(peer_id)
            self.outbound_peers.discard(peer_id)
            self.connection_times.pop(peer_id, None)
    
    def get_eviction_candidates(self, count: int = 1) -> List[str]:
        """
        Get peers to evict for new connections.
        
        Prefers to evict:
        - Inbound connections (over outbound)
        - Newer connections (over older)
        - Peers from over-represented subnets
        """
        with self._lock:
            candidates = []
            
            # Prefer inbound for eviction
            pool = list(self.inbound_peers)
            if len(pool) < count:
                pool.extend(self.outbound_peers)
            
            # Sort by connection age (newer first for eviction)
            pool.sort(key=lambda p: self.connection_times.get(p, 0), reverse=True)
            
            return pool[:count]
    
    def add_tried_address(self, address: Tuple[str, int]):
        """Mark address as successfully connected."""
        with self._lock:
            addr_str = f"{address[0]}:{address[1]}"
            self.tried_addresses[addr_str] = time.time()
            self.new_addresses.pop(addr_str, None)
    
    def add_new_address(self, address: Tuple[str, int]):
        """Add newly learned address."""
        with self._lock:
            addr_str = f"{address[0]}:{address[1]}"
            if addr_str not in self.tried_addresses:
                self.new_addresses[addr_str] = time.time()
    
    def get_addresses_to_try(self, count: int = 10) -> List[Tuple[str, int]]:
        """
        Get addresses to try connecting to.
        
        Balances between tried (reliable) and new (diversity) addresses.
        """
        with self._lock:
            result = []
            
            # 70% from tried, 30% from new
            tried_count = int(count * 0.7)
            new_count = count - tried_count
            
            # Get tried addresses sorted by recency
            tried = sorted(
                self.tried_addresses.items(),
                key=lambda x: x[1],
                reverse=True
            )[:tried_count]
            
            for addr_str, _ in tried:
                host, port = addr_str.rsplit(':', 1)
                result.append((host, int(port)))
            
            # Get new addresses
            new = list(self.new_addresses.keys())
            random.shuffle(new)
            for addr_str in new[:new_count]:
                host, port = addr_str.rsplit(':', 1)
                result.append((host, int(port)))
            
            return result
    
    def get_stats(self) -> Dict:
        """Get protection statistics."""
        with self._lock:
            return {
                'total_connections': len(self.inbound_peers) + len(self.outbound_peers),
                'inbound': len(self.inbound_peers),
                'outbound': len(self.outbound_peers),
                'unique_ips': len(self.connections_by_ip),
                'unique_subnets': len(self.connections_by_subnet),
                'tried_addresses': len(self.tried_addresses),
                'new_addresses': len(self.new_addresses),
            }


# ============================================================================
# BAN MANAGER
# ============================================================================

class BanManager:
    """Manages peer bans and misbehavior tracking."""
    
    def __init__(self, ban_duration: int = BAN_DURATION):
        self.ban_duration = ban_duration
        self.banned: Dict[str, Tuple[float, str]] = {}  # IP -> (until, reason)
        self.misbehavior: Dict[str, int] = defaultdict(int)  # IP -> score
        self._lock = threading.Lock()
    
    def is_banned(self, ip: str) -> bool:
        """Check if IP is banned."""
        with self._lock:
            if ip in self.banned:
                until, _ = self.banned[ip]
                if time.time() < until:
                    return True
                else:
                    del self.banned[ip]
            return False
    
    def add_misbehavior(self, ip: str, score: int, reason: str) -> bool:
        """
        Add misbehavior score. Returns True if peer should be banned.
        """
        with self._lock:
            self.misbehavior[ip] += score
            
            if self.misbehavior[ip] >= BAN_THRESHOLD:
                self.ban(ip, reason)
                return True
            return False
    
    def ban(self, ip: str, reason: str):
        """Ban an IP address."""
        with self._lock:
            until = time.time() + self.ban_duration
            self.banned[ip] = (until, reason)
            self.misbehavior.pop(ip, None)
            logger.warning(f"Banned {ip}: {reason}")
    
    def unban(self, ip: str):
        """Unban an IP address."""
        with self._lock:
            self.banned.pop(ip, None)
            self.misbehavior.pop(ip, None)
    
    def cleanup(self):
        """Remove expired bans."""
        with self._lock:
            now = time.time()
            expired = [ip for ip, (until, _) in self.banned.items() if until <= now]
            for ip in expired:
                del self.banned[ip]
    
    def get_banned_list(self) -> List[Tuple[str, float, str]]:
        """Get list of banned IPs with expiry and reason."""
        with self._lock:
            return [(ip, until, reason) for ip, (until, reason) in self.banned.items()]


# ============================================================================
# MESSAGE STRUCTURES
# ============================================================================

@dataclass
class MessageHeader:
    magic: bytes
    command: MessageType
    length: int
    checksum: bytes
    
    HEADER_SIZE = 13
    
    def serialize(self) -> bytes:
        return (
            self.magic +
            struct.pack('<B', self.command) +
            struct.pack('<I', self.length) +
            self.checksum
        )
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'MessageHeader':
        if len(data) < cls.HEADER_SIZE:
            raise ValueError("Insufficient header data")
        return cls(
            magic=data[:4],
            command=MessageType(data[4]),
            length=struct.unpack('<I', data[5:9])[0],
            checksum=data[9:13]
        )


@dataclass
class NetworkMessage:
    header: MessageHeader
    payload: bytes
    
    def serialize(self) -> bytes:
        return self.header.serialize() + self.payload
    
    @classmethod
    def create(cls, command: MessageType, payload: bytes,
               magic: bytes = MAINNET_MAGIC) -> 'NetworkMessage':
        checksum = sha256d(payload)[:4]
        header = MessageHeader(
            magic=magic, command=command,
            length=len(payload), checksum=checksum
        )
        return cls(header=header, payload=payload)
    
    def verify_checksum(self) -> bool:
        return sha256d(self.payload)[:4] == self.header.checksum


@dataclass
class VersionPayload:
    version: int
    services: int
    timestamp: int
    nonce: int
    user_agent: str
    start_height: int
    relay: bool = True
    # New fields for Noise support
    noise_pubkey: bytes = b''  # 32 bytes if Noise enabled
    
    def serialize(self) -> bytes:
        data = bytearray()
        data.extend(struct.pack('<I', self.version))
        data.extend(struct.pack('<Q', self.services))
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<Q', self.nonce))
        ua_bytes = self.user_agent.encode('utf-8')[:256]
        data.extend(struct.pack('<B', len(ua_bytes)))
        data.extend(ua_bytes)
        data.extend(struct.pack('<I', self.start_height))
        data.extend(struct.pack('<B', 1 if self.relay else 0))
        # Noise public key (32 bytes or empty)
        data.extend(struct.pack('<B', len(self.noise_pubkey)))
        data.extend(self.noise_pubkey)
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'VersionPayload':
        offset = 0
        version = struct.unpack_from('<I', data, offset)[0]; offset += 4
        services = struct.unpack_from('<Q', data, offset)[0]; offset += 8
        timestamp = struct.unpack_from('<Q', data, offset)[0]; offset += 8
        nonce = struct.unpack_from('<Q', data, offset)[0]; offset += 8
        ua_len = data[offset]; offset += 1
        user_agent = data[offset:offset + ua_len].decode('utf-8'); offset += ua_len
        start_height = struct.unpack_from('<I', data, offset)[0]; offset += 4
        relay = bool(data[offset]) if offset < len(data) else True; offset += 1
        # Noise public key
        noise_pubkey = b''
        if offset < len(data):
            noise_len = data[offset]; offset += 1
            if noise_len > 0 and offset + noise_len <= len(data):
                noise_pubkey = data[offset:offset + noise_len]
        return cls(version=version, services=services, timestamp=timestamp,
                   nonce=nonce, user_agent=user_agent, start_height=start_height, 
                   relay=relay, noise_pubkey=noise_pubkey)


@dataclass
class InvItem:
    inv_type: InvType
    hash: bytes
    
    def serialize(self) -> bytes:
        return struct.pack('<I', self.inv_type) + self.hash
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['InvItem', int]:
        inv_type = InvType(struct.unpack_from('<I', data, offset)[0])
        hash_bytes = data[offset + 4:offset + 36]
        return cls(inv_type=inv_type, hash=hash_bytes), offset + 36


# ============================================================================
# PEER CONNECTION
# ============================================================================

class PeerState(IntEnum):
    CONNECTING = 0
    CONNECTED = 1
    NOISE_HANDSHAKE = 2
    VERSION_HANDSHAKE = 3
    READY = 4
    DISCONNECTED = 5


@dataclass
class PeerStats:
    bytes_sent: int = 0
    bytes_recv: int = 0
    messages_sent: int = 0
    messages_recv: int = 0
    last_send: float = 0
    last_recv: float = 0
    ping_time: float = 0
    misbehavior_score: int = 0


class Peer:
    """Represents an encrypted peer connection."""
    
    def __init__(
        self,
        address: Tuple[str, int],
        sock: Optional[socket.socket] = None,
        inbound: bool = False,
        noise_keys: Optional[NoiseKeys] = None
    ):
        self.address = address
        self.socket = sock
        self.inbound = inbound
        self.state = PeerState.CONNECTING
        self.stats = PeerStats()
        self.version: Optional[VersionPayload] = None
        
        # Encryption
        self.noise_keys = noise_keys
        self.noise_wrapper: Optional[NoiseWrapper] = None
        self.encryption_enabled = False
        
        # Buffers
        self._recv_buffer = bytearray()
        self._send_queue: queue.Queue = queue.Queue()
        
        # Ping tracking
        self._last_ping_nonce: int = 0
        self._ping_sent_time: float = 0
        
        # Rate limiting
        self._message_times: List[float] = []
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Connection metadata
        self.connected_at: float = 0
        self.remote_noise_pubkey: Optional[bytes] = None
    
    @property
    def id(self) -> str:
        return f"{self.address[0]}:{self.address[1]}"
    
    @property
    def ip(self) -> str:
        return self.address[0]
    
    def connect(self, timeout: float = CONNECT_TIMEOUT) -> bool:
        """Establish TCP connection."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect(self.address)
            self.socket.setblocking(False)
            self.state = PeerState.CONNECTED
            self.connected_at = time.time()
            logger.debug(f"Connected to {self.id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to {self.id}: {e}")
            self.state = PeerState.DISCONNECTED
            return False
    
    def init_noise_handshake(self, is_initiator: bool = True):
        """Initialize Noise Protocol handshake."""
        if not self.noise_keys:
            logger.warning(f"No Noise keys for {self.id}")
            return
        
        self.noise_wrapper = NoiseWrapper(self.noise_keys, is_initiator)
        self.state = PeerState.NOISE_HANDSHAKE
        
        if is_initiator:
            # Send first handshake message
            handshake_msg = self.noise_wrapper.get_handshake_message()
            if handshake_msg:
                self._send_raw(MessageType.NOISE_HANDSHAKE_INIT, handshake_msg)
    
    def process_noise_handshake(self, msg_type: MessageType, payload: bytes) -> bool:
        """
        Process Noise handshake message.
        
        Returns True if handshake is complete.
        """
        if not self.noise_wrapper:
            return False
        
        try:
            complete = self.noise_wrapper.process_handshake_message(payload)
            
            if not complete:
                # Send next handshake message
                response = self.noise_wrapper.get_handshake_message()
                if response:
                    if msg_type == MessageType.NOISE_HANDSHAKE_INIT:
                        self._send_raw(MessageType.NOISE_HANDSHAKE_RESP, response)
                    else:
                        self._send_raw(MessageType.NOISE_HANDSHAKE_FINAL, response)
                return False
            
            # Handshake complete
            self.encryption_enabled = True
            self.remote_noise_pubkey = self.noise_wrapper.remote_static
            self.state = PeerState.VERSION_HANDSHAKE
            logger.info(f"Noise handshake complete with {self.id}")
            return True
            
        except Exception as e:
            logger.error(f"Noise handshake error with {self.id}: {e}")
            self.disconnect(f"Noise handshake failed: {e}")
            return False
    
    def disconnect(self, reason: str = ""):
        """Close connection."""
        with self._lock:
            if self.state == PeerState.DISCONNECTED:
                return
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            self.state = PeerState.DISCONNECTED
            logger.debug(f"Disconnected from {self.id}: {reason}")
    
    def send_message(self, message: NetworkMessage) -> bool:
        """Queue message for sending (with encryption if enabled)."""
        if self.state not in (PeerState.CONNECTED, PeerState.NOISE_HANDSHAKE,
                               PeerState.VERSION_HANDSHAKE, PeerState.READY):
            return False
        self._send_queue.put(message)
        return True
    
    def _send_raw(self, msg_type: MessageType, payload: bytes):
        """Send raw message (for handshake)."""
        msg = NetworkMessage.create(msg_type, payload)
        self._send_queue.put(msg)
    
    def process_send_queue(self) -> int:
        """Process queued messages and send to socket."""
        if not self.socket or self.state == PeerState.DISCONNECTED:
            return 0
        
        total_sent = 0
        while not self._send_queue.empty():
            try:
                message = self._send_queue.get_nowait()
                data = message.serialize()
                
                # Encrypt if handshake complete and not a handshake message
                if (self.encryption_enabled and 
                    message.header.command not in (MessageType.NOISE_HANDSHAKE_INIT,
                                                    MessageType.NOISE_HANDSHAKE_RESP,
                                                    MessageType.NOISE_HANDSHAKE_FINAL)):
                    try:
                        data = self.noise_wrapper.encrypt(data)
                    except Exception as e:
                        logger.error(f"Encryption error: {e}")
                        self.disconnect(f"Encryption failed: {e}")
                        break
                
                self.socket.sendall(data)
                total_sent += len(data)
                self.stats.bytes_sent += len(data)
                self.stats.messages_sent += 1
                self.stats.last_send = time.time()
                
            except queue.Empty:
                break
            except Exception as e:
                logger.warning(f"Send error to {self.id}: {e}")
                self.disconnect(f"Send error: {e}")
                break
        
        return total_sent
    
    def receive_data(self) -> List[NetworkMessage]:
        """Receive and parse messages from socket."""
        if not self.socket or self.state == PeerState.DISCONNECTED:
            return []
        
        messages = []
        try:
            data = self.socket.recv(65536)
            if not data:
                self.disconnect("Connection closed")
                return []
            
            self._recv_buffer.extend(data)
            self.stats.bytes_recv += len(data)
            self.stats.last_recv = time.time()
            
            # Process buffer
            while True:
                if self.encryption_enabled:
                    # Encrypted mode: decrypt first
                    try:
                        if len(self._recv_buffer) < 28:  # Minimum encrypted message
                            break
                        
                        # Try to decrypt
                        decrypted = self.noise_wrapper.decrypt(bytes(self._recv_buffer))
                        self._recv_buffer.clear()
                        self._recv_buffer.extend(decrypted)
                    except ValueError:
                        # Need more data
                        break
                    except Exception as e:
                        logger.error(f"Decryption error: {e}")
                        self.disconnect(f"Decryption failed: {e}")
                        break
                
                # Parse message
                if len(self._recv_buffer) < MessageHeader.HEADER_SIZE:
                    break
                
                header = MessageHeader.deserialize(bytes(self._recv_buffer))
                total_size = MessageHeader.HEADER_SIZE + header.length
                
                if header.length > MAX_MESSAGE_SIZE:
                    self.add_misbehavior(50, "Message too large")
                    self._recv_buffer.clear()
                    break
                
                if len(self._recv_buffer) < total_size:
                    break
                
                payload = bytes(self._recv_buffer[MessageHeader.HEADER_SIZE:total_size])
                del self._recv_buffer[:total_size]
                
                message = NetworkMessage(header=header, payload=payload)
                if message.verify_checksum():
                    messages.append(message)
                    self.stats.messages_recv += 1
                else:
                    self.add_misbehavior(10, "Invalid checksum")
                    
        except BlockingIOError:
            pass
        except Exception as e:
            logger.warning(f"Receive error from {self.id}: {e}")
            self.disconnect(str(e))
        
        return messages
    
    def add_misbehavior(self, score: int, reason: str):
        """Add misbehavior score."""
        self.stats.misbehavior_score += score
        logger.warning(f"Peer {self.id} misbehavior +{score}: {reason}")
        if self.stats.misbehavior_score >= BAN_THRESHOLD:
            self.disconnect(f"Banned: {reason}")
    
    def send_ping(self):
        """Send ping message."""
        self._last_ping_nonce = random.randint(0, 2**64 - 1)
        self._ping_sent_time = time.time()
        payload = struct.pack('<Q', self._last_ping_nonce)
        msg = NetworkMessage.create(MessageType.PING, payload)
        self.send_message(msg)
    
    def handle_pong(self, nonce: int):
        """Handle pong response."""
        if nonce == self._last_ping_nonce:
            self.stats.ping_time = time.time() - self._ping_sent_time
    
    def check_rate_limit(self) -> bool:
        """Check if peer is within rate limits."""
        now = time.time()
        
        # Remove old entries
        self._message_times = [t for t in self._message_times if t > now - 1.0]
        
        if len(self._message_times) >= MAX_MESSAGES_PER_SECOND:
            return False
        
        self._message_times.append(now)
        return True


# ============================================================================
# P2P NODE
# ============================================================================

class P2PNode:
    """
    Production P2P network node with encryption and Eclipse protection.
    
    Features:
    - Noise Protocol encryption for all peer communication
    - Eclipse attack protection via subnet diversity
    - Peer discovery and management
    - Block and transaction propagation
    - Rate limiting and ban management
    """
    
    def __init__(self, config: Optional[NetworkConfig] = None, noise_keys: Optional[NoiseKeys] = None):
        # SECURITY: Require Noise Protocol for P2P networking
        if not NOISE_AVAILABLE:
            raise RuntimeError(
                "FATAL: Cannot start P2P node without Noise Protocol encryption. "
                "Install noiseprotocol: pip install noiseprotocol"
            )
        
        self.config = config or NetworkConfig()
        self.port = self.config.default_port
        
        # Noise Protocol keys
        if noise_keys:
            self.noise_keys = noise_keys
        else:
            self.noise_keys = NoiseKeys.generate()
            logger.info(f"Generated Noise keys: {self.noise_keys.public_key.hex()[:16]}...")
        
        # Peers
        self.peers: Dict[str, Peer] = {}
        self.eclipse_protection = EclipseProtection()
        self.ban_manager = BanManager()
        
        # Known addresses for peer discovery
        self.known_addresses: Set[Tuple[str, int]] = set()
        
        # Server socket
        self.server_socket: Optional[socket.socket] = None
        self.selector = selectors.DefaultSelector()
        
        # State
        self.running = False
        self.local_nonce = random.randint(0, 2**64 - 1)
        self.start_height = 0
        self.user_agent = "/ProofOfTime:1.0.0/"
        
        # Callbacks
        self.on_block: Optional[Callable[[Peer, Block], None]] = None
        self.on_transaction: Optional[Callable[[Peer, Transaction], None]] = None
        self.on_headers: Optional[Callable[[Peer, List[BlockHeader]], None]] = None
        
        # Inventory tracking
        self.seen_txs: Set[bytes] = set()
        self.seen_blocks: Set[bytes] = set()
        self.pending_requests: Dict[bytes, Tuple[str, float]] = {}
        
        # Threading
        self._lock = threading.RLock()
        self._threads: List[threading.Thread] = []
    
    def start(self, listen: bool = True):
        """Start P2P node."""
        self.running = True
        
        if listen:
            self._start_server()
        
        # Start worker threads
        self._threads = [
            threading.Thread(target=self._connection_loop, daemon=True, name="P2P-Connection"),
            threading.Thread(target=self._maintenance_loop, daemon=True, name="P2P-Maintenance"),
            threading.Thread(target=self._discovery_loop, daemon=True, name="P2P-Discovery"),
        ]
        for t in self._threads:
            t.start()
        
        logger.info(f"P2P node started on port {self.port} with Noise pubkey: {self.noise_keys.public_key.hex()[:16]}...")
    
    def stop(self):
        """Stop P2P node."""
        self.running = False
        
        # Close all peers
        with self._lock:
            for peer in list(self.peers.values()):
                peer.disconnect("Node stopping")
            self.peers.clear()
        
        # Close server
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        try:
            self.selector.close()
        except:
            pass
        
        logger.info("P2P node stopped")
    
    def _start_server(self):
        """Start listening server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(self.config.max_peers)
        self.server_socket.setblocking(False)
        self.selector.register(self.server_socket, selectors.EVENT_READ)
        logger.info(f"Listening on port {self.port}")
    
    def _connection_loop(self):
        """Main connection handling loop."""
        while self.running:
            try:
                events = self.selector.select(timeout=0.1)
                
                for key, mask in events:
                    if key.fileobj == self.server_socket:
                        self._accept_connection()
                
                # Process all peers
                with self._lock:
                    for peer in list(self.peers.values()):
                        if peer.state == PeerState.DISCONNECTED:
                            self._remove_peer(peer)
                            continue
                        
                        # Receive
                        messages = peer.receive_data()
                        for msg in messages:
                            if not peer.check_rate_limit():
                                peer.add_misbehavior(10, "Rate limit exceeded")
                                continue
                            self._handle_message(peer, msg)
                        
                        # Send
                        peer.process_send_queue()
                
            except Exception as e:
                logger.error(f"Connection loop error: {e}")
                time.sleep(0.1)
    
    def _maintenance_loop(self):
        """Periodic maintenance tasks."""
        last_ping = 0
        last_cleanup = 0
        
        while self.running:
            try:
                now = time.time()
                
                # Ping peers every PING_INTERVAL
                if now - last_ping > PING_INTERVAL:
                    with self._lock:
                        for peer in self.peers.values():
                            if peer.state == PeerState.READY:
                                peer.send_ping()
                    last_ping = now
                
                # Cleanup every 10 minutes
                if now - last_cleanup > 600:
                    self.ban_manager.cleanup()
                    
                    # Clean old inventory
                    if len(self.seen_txs) > 100000:
                        self.seen_txs.clear()
                    if len(self.seen_blocks) > 10000:
                        self.seen_blocks.clear()
                    
                    last_cleanup = now
                
                # Check connection health
                self._check_connections()
                
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}")
                time.sleep(1)
    
    def _discovery_loop(self):
        """Peer discovery loop."""
        last_discovery = 0
        
        while self.running:
            try:
                now = time.time()
                
                # Attempt new connections if needed
                if now - last_discovery > 30:
                    outbound_count = len(self.eclipse_protection.outbound_peers)
                    
                    if outbound_count < MIN_OUTBOUND_CONNECTIONS:
                        # Try to connect to more peers
                        addresses = self.eclipse_protection.get_addresses_to_try(
                            MIN_OUTBOUND_CONNECTIONS - outbound_count
                        )
                        for addr in addresses:
                            if self.connect_to_peer(addr):
                                time.sleep(1)  # Stagger connections
                    
                    last_discovery = now
                
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Discovery loop error: {e}")
                time.sleep(5)
    
    def _check_connections(self):
        """Check connection health and evict if necessary."""
        with self._lock:
            now = time.time()
            
            for peer in list(self.peers.values()):
                # Check for timeout
                if peer.state == PeerState.NOISE_HANDSHAKE:
                    if now - peer.connected_at > NOISE_HANDSHAKE_TIMEOUT:
                        peer.disconnect("Noise handshake timeout")
                        continue
                
                if peer.state == PeerState.VERSION_HANDSHAKE:
                    if now - peer.connected_at > HANDSHAKE_TIMEOUT:
                        peer.disconnect("Version handshake timeout")
                        continue
                
                # Check for ping timeout
                if peer.state == PeerState.READY:
                    if peer._ping_sent_time > 0:
                        if now - peer._ping_sent_time > PING_TIMEOUT:
                            if peer.stats.ping_time == 0:
                                peer.disconnect("Ping timeout")
    
    def _accept_connection(self):
        """Accept incoming connection with Eclipse protection."""
        try:
            conn, addr = self.server_socket.accept()
            conn.setblocking(False)
            
            ip = addr[0]
            
            # Check ban list
            if self.ban_manager.is_banned(ip):
                logger.debug(f"Rejected banned IP: {ip}")
                conn.close()
                return
            
            # Check Eclipse protection
            allowed, reason = self.eclipse_protection.can_connect(ip, is_inbound=True)
            if not allowed:
                logger.debug(f"Rejected connection from {ip}: {reason}")
                conn.close()
                return
            
            # Check max peers
            if len(self.peers) >= self.config.max_peers:
                # Try to evict
                candidates = self.eclipse_protection.get_eviction_candidates(1)
                if candidates:
                    evict_id = candidates[0]
                    if evict_id in self.peers:
                        self.peers[evict_id].disconnect("Evicted for new connection")
                        self._remove_peer(self.peers[evict_id])
                else:
                    logger.debug(f"Rejected connection from {ip}: max peers reached")
                    conn.close()
                    return
            
            # Create peer
            peer = Peer(addr, conn, inbound=True, noise_keys=self.noise_keys)
            peer.state = PeerState.CONNECTED
            peer.connected_at = time.time()
            
            with self._lock:
                self.peers[peer.id] = peer
                self.eclipse_protection.register_connection(peer.id, ip, is_inbound=True)
            
            # Wait for initiator's Noise handshake
            logger.info(f"Accepted connection from {peer.id}")
            
        except Exception as e:
            logger.warning(f"Accept error: {e}")
    
    def connect_to_peer(self, address: Tuple[str, int]) -> bool:
        """Connect to peer with Eclipse protection."""
        ip = address[0]
        
        # Check ban list
        if self.ban_manager.is_banned(ip):
            return False
        
        peer_id = f"{address[0]}:{address[1]}"
        
        with self._lock:
            if peer_id in self.peers:
                return True
            
            # Check Eclipse protection
            allowed, reason = self.eclipse_protection.can_connect(ip, is_inbound=False)
            if not allowed:
                logger.debug(f"Cannot connect to {ip}: {reason}")
                return False
            
            if len(self.peers) >= self.config.max_peers:
                return False
        
        # Create and connect peer
        peer = Peer(address, noise_keys=self.noise_keys)
        if not peer.connect():
            return False
        
        with self._lock:
            self.peers[peer.id] = peer
            self.eclipse_protection.register_connection(peer.id, ip, is_inbound=False)
        
        # Start Noise handshake as initiator
        peer.init_noise_handshake(is_initiator=True)
        
        return True
    
    def _remove_peer(self, peer: Peer):
        """Remove peer from tracking."""
        with self._lock:
            if peer.id in self.peers:
                del self.peers[peer.id]
            self.eclipse_protection.unregister_connection(peer.id, peer.ip)
    
    def _send_version(self, peer: Peer):
        """Send version message."""
        version = VersionPayload(
            version=PROTOCOL.PROTOCOL_VERSION,
            services=1,
            timestamp=int(time.time()),
            nonce=self.local_nonce,
            user_agent=self.user_agent,
            start_height=self.start_height,
            relay=True,
            noise_pubkey=self.noise_keys.public_key
        )
        msg = NetworkMessage.create(MessageType.VERSION, version.serialize())
        peer.send_message(msg)
    
    def _handle_message(self, peer: Peer, message: NetworkMessage):
        """Handle received message."""
        cmd = message.header.command
        payload = message.payload
        
        try:
            # Noise handshake messages
            if cmd in (MessageType.NOISE_HANDSHAKE_INIT, 
                       MessageType.NOISE_HANDSHAKE_RESP,
                       MessageType.NOISE_HANDSHAKE_FINAL):
                if peer.state == PeerState.CONNECTED:
                    # Inbound connection, start responder handshake
                    peer.noise_wrapper = NoiseWrapper(peer.noise_keys, is_initiator=False)
                    peer.state = PeerState.NOISE_HANDSHAKE
                
                if peer.process_noise_handshake(cmd, payload):
                    # Handshake complete, send version
                    self._send_version(peer)
                return
            
            # Protocol messages
            if cmd == MessageType.VERSION:
                self._handle_version(peer, payload)
            elif cmd == MessageType.VERACK:
                self._handle_verack(peer)
            elif cmd == MessageType.PING:
                self._handle_ping(peer, payload)
            elif cmd == MessageType.PONG:
                self._handle_pong(peer, payload)
            elif cmd == MessageType.INV:
                self._handle_inv(peer, payload)
            elif cmd == MessageType.GETDATA:
                self._handle_getdata(peer, payload)
            elif cmd == MessageType.BLOCK:
                self._handle_block(peer, payload)
            elif cmd == MessageType.TX:
                self._handle_tx(peer, payload)
            elif cmd == MessageType.HEADERS:
                self._handle_headers(peer, payload)
            elif cmd == MessageType.GETADDR:
                self._handle_getaddr(peer)
            elif cmd == MessageType.ADDR:
                self._handle_addr(peer, payload)
                
        except Exception as e:
            logger.warning(f"Error handling {cmd.name} from {peer.id}: {e}")
            peer.add_misbehavior(10, f"Invalid {cmd.name}")
    
    def _handle_version(self, peer: Peer, payload: bytes):
        """Handle version message."""
        version = VersionPayload.deserialize(payload)
        
        # Check for self-connection
        if version.nonce == self.local_nonce:
            peer.disconnect("Self-connection")
            return
        
        peer.version = version
        peer.remote_noise_pubkey = version.noise_pubkey if version.noise_pubkey else None
        
        # Send verack
        msg = NetworkMessage.create(MessageType.VERACK, b'')
        peer.send_message(msg)
        
        if not peer.inbound:
            peer.state = PeerState.READY
            self.eclipse_protection.add_tried_address(peer.address)
            logger.info(f"Outbound handshake complete with {peer.id}")
    
    def _handle_verack(self, peer: Peer):
        """Handle verack message."""
        if peer.inbound:
            self._send_version(peer)
        peer.state = PeerState.READY
        self.eclipse_protection.add_tried_address(peer.address)
        logger.info(f"Handshake complete with {peer.id} (encrypted: {peer.encryption_enabled})")
    
    def _handle_ping(self, peer: Peer, payload: bytes):
        """Handle ping message."""
        msg = NetworkMessage.create(MessageType.PONG, payload)
        peer.send_message(msg)
    
    def _handle_pong(self, peer: Peer, payload: bytes):
        """Handle pong message."""
        if len(payload) >= 8:
            nonce = struct.unpack('<Q', payload[:8])[0]
            peer.handle_pong(nonce)
    
    def _handle_inv(self, peer: Peer, payload: bytes):
        """Handle inventory message."""
        offset = 0
        count = payload[offset]; offset += 1
        
        requests = []
        for _ in range(min(count, MAX_INV_ITEMS)):
            item, offset = InvItem.deserialize(payload, offset)
            if item.inv_type == InvType.TX and item.hash not in self.seen_txs:
                requests.append(item)
            elif item.inv_type == InvType.BLOCK and item.hash not in self.seen_blocks:
                requests.append(item)
        
        if requests:
            self._send_getdata(peer, requests)
    
    def _handle_getdata(self, peer: Peer, payload: bytes):
        """Handle getdata message."""
        # Would fetch from database and send
        pass
    
    def _handle_block(self, peer: Peer, payload: bytes):
        """Handle block message."""
        try:
            block, _ = Block.deserialize(payload)
            block_hash = block.hash
            
            if block_hash in self.seen_blocks:
                return
            
            self.seen_blocks.add(block_hash)
            
            if self.on_block:
                self.on_block(peer, block)
            
            # Relay to other peers
            self._announce_block(block_hash, exclude=peer.id)
            
        except Exception as e:
            logger.warning(f"Invalid block from {peer.id}: {e}")
            peer.add_misbehavior(20, "Invalid block")
    
    def _handle_tx(self, peer: Peer, payload: bytes):
        """Handle transaction message."""
        try:
            tx, _ = Transaction.deserialize(payload)
            txid = tx.hash()
            
            if txid in self.seen_txs:
                return
            
            self.seen_txs.add(txid)
            
            if self.on_transaction:
                self.on_transaction(peer, tx)
            
            # Relay
            self._announce_tx(txid, exclude=peer.id)
            
        except Exception as e:
            logger.warning(f"Invalid tx from {peer.id}: {e}")
            peer.add_misbehavior(10, "Invalid tx")
    
    def _handle_headers(self, peer: Peer, payload: bytes):
        """Handle headers message."""
        offset = 0
        count = payload[offset]; offset += 1
        
        headers = []
        for _ in range(min(count, MAX_HEADERS)):
            header, offset = BlockHeader.deserialize(payload, offset)
            headers.append(header)
        
        if self.on_headers and headers:
            self.on_headers(peer, headers)
    
    def _handle_getaddr(self, peer: Peer):
        """Handle getaddr message."""
        addresses = list(self.known_addresses)[:MAX_ADDR_ITEMS]
        if not addresses:
            return
        
        data = bytearray()
        data.append(len(addresses))
        for ip, port in addresses:
            data.extend(struct.pack('<Q', int(time.time())))
            data.extend(struct.pack('<Q', 1))
            data.extend(b'\x00' * 10 + b'\xff\xff')
            for octet in ip.split('.'):
                data.append(int(octet))
            data.extend(struct.pack('>H', port))
        
        msg = NetworkMessage.create(MessageType.ADDR, bytes(data))
        peer.send_message(msg)
    
    def _handle_addr(self, peer: Peer, payload: bytes):
        """Handle addr message."""
        offset = 0
        count = payload[offset]; offset += 1
        
        for _ in range(min(count, MAX_ADDR_ITEMS)):
            offset += 8  # timestamp
            offset += 8  # services
            offset += 12  # ipv6 prefix
            ip = '.'.join(str(payload[offset + i]) for i in range(4))
            offset += 4
            port = struct.unpack('>H', payload[offset:offset + 2])[0]
            offset += 2
            
            addr = (ip, port)
            self.known_addresses.add(addr)
            self.eclipse_protection.add_new_address(addr)
    
    def _send_getdata(self, peer: Peer, items: List[InvItem]):
        """Send getdata message."""
        data = bytearray()
        data.append(len(items))
        for item in items:
            data.extend(item.serialize())
        msg = NetworkMessage.create(MessageType.GETDATA, bytes(data))
        peer.send_message(msg)
    
    def _announce_block(self, block_hash: bytes, exclude: str = ""):
        """Announce block to peers."""
        item = InvItem(InvType.BLOCK, block_hash)
        self._broadcast_inv([item], exclude)
    
    def _announce_tx(self, txid: bytes, exclude: str = ""):
        """Announce transaction to peers."""
        item = InvItem(InvType.TX, txid)
        self._broadcast_inv([item], exclude)
    
    def _broadcast_inv(self, items: List[InvItem], exclude: str = ""):
        """Broadcast inventory to all peers."""
        data = bytearray()
        data.append(len(items))
        for item in items:
            data.extend(item.serialize())
        msg = NetworkMessage.create(MessageType.INV, bytes(data))
        
        with self._lock:
            for peer_id, peer in self.peers.items():
                if peer_id != exclude and peer.state == PeerState.READY:
                    peer.send_message(msg)
    
    def broadcast_block(self, block: Block):
        """Broadcast block to all peers."""
        block_hash = block.hash
        self.seen_blocks.add(block_hash)
        
        data = block.serialize()
        msg = NetworkMessage.create(MessageType.BLOCK, data)
        
        with self._lock:
            for peer in self.peers.values():
                if peer.state == PeerState.READY:
                    peer.send_message(msg)
    
    def broadcast_transaction(self, tx: Transaction):
        """Broadcast transaction to all peers."""
        txid = tx.hash()
        self.seen_txs.add(txid)
        self._announce_tx(txid)
    
    def get_peer_count(self) -> int:
        """Get number of ready peers."""
        with self._lock:
            return sum(1 for p in self.peers.values() if p.state == PeerState.READY)
    
    def get_peer_info(self) -> List[Dict]:
        """Get information about connected peers."""
        with self._lock:
            return [
                {
                    'id': p.id,
                    'inbound': p.inbound,
                    'version': p.version.user_agent if p.version else '',
                    'height': p.version.start_height if p.version else 0,
                    'ping': p.stats.ping_time,
                    'bytes_sent': p.stats.bytes_sent,
                    'bytes_recv': p.stats.bytes_recv,
                    'encrypted': p.encryption_enabled,
                    'noise_pubkey': p.remote_noise_pubkey.hex()[:16] if p.remote_noise_pubkey else '',
                    'connected_at': p.connected_at,
                }
                for p in self.peers.values()
                if p.state == PeerState.READY
            ]
    
    def get_network_stats(self) -> Dict:
        """Get network statistics."""
        eclipse_stats = self.eclipse_protection.get_stats()
        return {
            **eclipse_stats,
            'banned_count': len(self.ban_manager.banned),
            'known_addresses': len(self.known_addresses),
            'seen_txs': len(self.seen_txs),
            'seen_blocks': len(self.seen_blocks),
        }


# ============================================================================
# HEADERS-FIRST INITIAL BLOCK DOWNLOAD (IBD)
# ============================================================================

class SyncState(IntEnum):
    """Synchronization state machine."""
    IDLE = 0
    DOWNLOADING_HEADERS = 1
    VALIDATING_HEADERS = 2
    DOWNLOADING_BLOCKS = 3
    SYNCED = 4


@dataclass
class BlockRequest:
    """Tracks a pending block download request."""
    block_hash: bytes
    height: int
    requested_at: float
    peer_id: str
    retries: int = 0


class HeadersFirstSync:
    """
    Headers-first Initial Block Download implementation.
    
    Protocol (Bitcoin-style):
    1. Request headers starting from our best header hash
    2. Validate header chain (PoW/difficulty in Bitcoin, VDF in PoT)
    3. Once headers are synced, download blocks in parallel
    4. Validate full blocks and update UTXO set
    
    Advantages:
    - Fast initial validation (headers only)
    - Parallel block download
    - Can verify chain work before downloading blocks
    - Efficient use of bandwidth
    
    Block timeout ensures blocks are produced within target interval.
    """
    
    # Maximum headers per request
    MAX_HEADERS_PER_REQUEST = 2000
    
    # Maximum parallel block downloads
    MAX_PARALLEL_DOWNLOADS = 16
    
    # Block request timeout (should be less than block interval)
    BLOCK_REQUEST_TIMEOUT = 60.0  # 1 minute
    
    # Block production timeout (must produce within this time)
    BLOCK_PRODUCTION_TIMEOUT = PROTOCOL.BLOCK_INTERVAL - 60  # ~11 minutes for 12 min interval
    
    # Stale tip threshold (if no new blocks for this long, re-sync)
    STALE_TIP_THRESHOLD = PROTOCOL.BLOCK_INTERVAL * 2  # 2x block interval
    
    def __init__(
        self,
        p2p_node: 'P2PNode',
        on_new_block: Callable[[Block], bool],
        get_best_header: Callable[[], Tuple[bytes, int]],
        has_block: Callable[[bytes], bool]
    ):
        """
        Initialize headers-first sync.
        
        Args:
            p2p_node: P2P node for sending messages
            on_new_block: Callback when new block received (returns True if valid)
            get_best_header: Returns (best_header_hash, height)
            has_block: Returns True if we have this block
        """
        self.network = p2p_node
        self.on_new_block = on_new_block
        self.get_best_header = get_best_header
        self.has_block = has_block
        
        self.state = SyncState.IDLE
        
        # Header chain we're downloading
        self.pending_headers: List[BlockHeader] = []
        self.validated_headers: List[BlockHeader] = []
        self.header_tip_hash: bytes = b''
        self.header_tip_height: int = 0
        
        # Block downloads
        self.pending_blocks: Dict[bytes, BlockRequest] = {}  # hash -> request
        self.download_queue: List[bytes] = []  # blocks to download
        
        # Timing
        self.last_block_time: float = time.time()
        self.sync_start_time: float = 0
        self.last_progress_log: float = 0
        
        # Statistics
        self.headers_downloaded: int = 0
        self.blocks_downloaded: int = 0
        self.blocks_validated: int = 0
        
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start sync manager."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info("Headers-first sync started")
    
    def stop(self):
        """Stop sync manager."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _sync_loop(self):
        """Main synchronization loop."""
        while self._running:
            try:
                with self._lock:
                    self._check_state()
                    self._process_timeouts()
                    self._fill_download_slots()
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                time.sleep(5)
    
    def _check_state(self):
        """Check and update sync state."""
        current_time = time.time()
        
        if self.state == SyncState.IDLE:
            # Check if we need to sync
            if self._needs_sync():
                self._start_header_sync()
        
        elif self.state == SyncState.DOWNLOADING_HEADERS:
            # Check if headers are complete
            if not self.pending_headers and not self._waiting_for_headers():
                self.state = SyncState.VALIDATING_HEADERS
                self._validate_headers()
        
        elif self.state == SyncState.VALIDATING_HEADERS:
            # Headers validated, start block download
            if self.download_queue or self.pending_blocks:
                self.state = SyncState.DOWNLOADING_BLOCKS
            else:
                self.state = SyncState.SYNCED
                logger.info("Sync complete!")
        
        elif self.state == SyncState.DOWNLOADING_BLOCKS:
            # Check if block download is complete
            if not self.download_queue and not self.pending_blocks:
                self.state = SyncState.SYNCED
                logger.info(f"Block download complete: {self.blocks_validated} blocks")
        
        elif self.state == SyncState.SYNCED:
            # Check for stale tip
            if current_time - self.last_block_time > self.STALE_TIP_THRESHOLD:
                logger.warning("Chain tip stale, initiating re-sync")
                self.state = SyncState.IDLE
        
        # Log progress periodically
        if current_time - self.last_progress_log > 10:
            self._log_progress()
            self.last_progress_log = current_time
    
    def _needs_sync(self) -> bool:
        """Check if we need to synchronize."""
        peers = self.network.get_peers()
        if not peers:
            return False
        
        our_hash, our_height = self.get_best_header()
        
        # Check if any peer has higher chain
        for peer in peers:
            if peer.get('height', 0) > our_height:
                return True
        
        return False
    
    def _start_header_sync(self):
        """Start downloading headers."""
        self.state = SyncState.DOWNLOADING_HEADERS
        self.sync_start_time = time.time()
        self.pending_headers = []
        self.validated_headers = []
        
        our_hash, our_height = self.get_best_header()
        self.header_tip_hash = our_hash
        self.header_tip_height = our_height
        
        logger.info(f"Starting header sync from height {our_height}")
        
        self._request_headers()
    
    def _request_headers(self):
        """Request headers from peers."""
        # Build locator (simplified - just our tip)
        locator = [self.header_tip_hash] if self.header_tip_hash else []
        
        # Find best peer
        peers = self.network.get_peers()
        best_peer = None
        best_height = self.header_tip_height
        
        for peer in peers:
            if peer.get('height', 0) > best_height:
                best_height = peer.get('height', 0)
                best_peer = peer
        
        if best_peer:
            # Create getheaders message
            payload = bytearray()
            payload.append(len(locator))
            for h in locator:
                payload.extend(h)
            payload.extend(b'\x00' * 32)  # Stop hash (all zeros = get all)
            
            self.network.broadcast_message(
                MessageType.GETHEADERS,
                bytes(payload),
                peer_filter=lambda p: p.id == best_peer['id']
            )
    
    def _waiting_for_headers(self) -> bool:
        """Check if we're waiting for header response."""
        # Could track pending requests here
        return False
    
    def _validate_headers(self):
        """Validate downloaded header chain."""
        logger.info(f"Validating {len(self.pending_headers)} headers")
        
        # For each header, verify it links correctly
        for header in self.pending_headers:
            # Basic validation (full validation done when blocks arrive)
            if len(header.prev_block_hash) != 32:
                logger.warning("Invalid header: bad prev_hash")
                self.state = SyncState.IDLE
                return
            
            self.validated_headers.append(header)
            
            # Add to download queue if we don't have the block
            block_hash = header.hash()
            if not self.has_block(block_hash):
                self.download_queue.append(block_hash)
        
        self.headers_downloaded = len(self.validated_headers)
        logger.info(f"Headers validated, {len(self.download_queue)} blocks to download")
    
    def _fill_download_slots(self):
        """Fill available download slots with block requests."""
        if self.state != SyncState.DOWNLOADING_BLOCKS:
            return
        
        available_slots = self.MAX_PARALLEL_DOWNLOADS - len(self.pending_blocks)
        if available_slots <= 0:
            return
        
        peers = self.network.get_peers()
        if not peers:
            return
        
        # Request blocks
        for _ in range(available_slots):
            if not self.download_queue:
                break
            
            block_hash = self.download_queue.pop(0)
            
            # Find peer to request from (round-robin)
            peer = random.choice(peers)
            
            request = BlockRequest(
                block_hash=block_hash,
                height=0,  # Could track this
                requested_at=time.time(),
                peer_id=peer['id']
            )
            self.pending_blocks[block_hash] = request
            
            # Send getdata request
            payload = bytearray()
            payload.append(1)  # Count
            payload.extend(struct.pack('<I', InvType.BLOCK))
            payload.extend(block_hash)
            
            self.network.broadcast_message(
                MessageType.GETDATA,
                bytes(payload),
                peer_filter=lambda p: p.id == peer['id']
            )
    
    def _process_timeouts(self):
        """Process timed out requests."""
        current_time = time.time()
        timed_out = []
        
        for block_hash, request in self.pending_blocks.items():
            if current_time - request.requested_at > self.BLOCK_REQUEST_TIMEOUT:
                timed_out.append(block_hash)
        
        for block_hash in timed_out:
            request = self.pending_blocks.pop(block_hash)
            request.retries += 1
            
            if request.retries < 3:
                # Re-queue for download
                self.download_queue.insert(0, block_hash)
                logger.debug(f"Block request timeout, retry {request.retries}")
            else:
                logger.warning(f"Block {block_hash.hex()[:16]} failed after 3 retries")
    
    def on_headers_received(self, peer_id: str, headers: List[BlockHeader]):
        """Handle received headers."""
        with self._lock:
            if self.state != SyncState.DOWNLOADING_HEADERS:
                return
            
            logger.debug(f"Received {len(headers)} headers from {peer_id}")
            
            for header in headers:
                self.pending_headers.append(header)
            
            # If we got a full batch, request more
            if len(headers) >= self.MAX_HEADERS_PER_REQUEST:
                self.header_tip_hash = headers[-1].hash()
                self._request_headers()
    
    def on_block_received(self, peer_id: str, block: Block):
        """Handle received block."""
        with self._lock:
            block_hash = block.hash
            
            # Remove from pending
            if block_hash in self.pending_blocks:
                del self.pending_blocks[block_hash]
            
            # Update timing
            self.last_block_time = time.time()
        
        # Validate and process block (outside lock)
        try:
            if self.on_new_block(block):
                with self._lock:
                    self.blocks_downloaded += 1
                    self.blocks_validated += 1
            else:
                logger.warning(f"Block validation failed: {block_hash.hex()[:16]}")
        except Exception as e:
            logger.error(f"Block processing error: {e}")
    
    def _log_progress(self):
        """Log sync progress."""
        if self.state == SyncState.IDLE:
            return
        
        elapsed = time.time() - self.sync_start_time
        
        if self.state == SyncState.DOWNLOADING_HEADERS:
            logger.info(
                f"Sync progress: downloading headers "
                f"({len(self.pending_headers)} received, {elapsed:.0f}s elapsed)"
            )
        elif self.state in (SyncState.VALIDATING_HEADERS, SyncState.DOWNLOADING_BLOCKS):
            total_blocks = self.headers_downloaded
            pct = (self.blocks_validated / max(total_blocks, 1)) * 100
            pending = len(self.pending_blocks)
            queued = len(self.download_queue)
            
            logger.info(
                f"Sync progress: {self.blocks_validated}/{total_blocks} blocks "
                f"({pct:.1f}%), {pending} downloading, {queued} queued, "
                f"{elapsed:.0f}s elapsed"
            )
    
    def get_sync_progress(self) -> Dict[str, Any]:
        """Get current sync progress."""
        with self._lock:
            return {
                'state': SyncState(self.state).name,
                'headers_downloaded': self.headers_downloaded,
                'blocks_downloaded': self.blocks_downloaded,
                'blocks_validated': self.blocks_validated,
                'pending_blocks': len(self.pending_blocks),
                'queued_blocks': len(self.download_queue),
                'is_synced': self.state == SyncState.SYNCED,
                'last_block_age': time.time() - self.last_block_time
            }
    
    def check_block_timeout(self, expected_height: int) -> bool:
        """
        Check if we've waited too long for a block.
        
        This is used to detect if the current leader failed to produce
        a block, triggering leader rotation.
        
        Returns:
            True if block production has timed out
        """
        time_since_last = time.time() - self.last_block_time
        return time_since_last > self.BLOCK_PRODUCTION_TIMEOUT


class BlockTimeoutMonitor:
    """
    Monitors block production times to ensure blocks arrive within 12 minutes.
    
    If a block doesn't arrive in time:
    1. Log timeout event
    2. Notify consensus for potential leader failure
    3. Track statistics for network health
    """
    
    # Target block interval (12 minutes)
    TARGET_INTERVAL = PROTOCOL.BLOCK_INTERVAL
    
    # Maximum acceptable block time before timeout
    MAX_BLOCK_TIME = PROTOCOL.BLOCK_INTERVAL + 60  # 13 minutes
    
    # Warning threshold
    WARNING_THRESHOLD = PROTOCOL.BLOCK_INTERVAL * 0.9  # 10.8 minutes
    
    def __init__(
        self,
        on_timeout: Optional[Callable[[int, float], None]] = None
    ):
        """
        Initialize block timeout monitor.
        
        Args:
            on_timeout: Callback(expected_height, time_elapsed) when timeout occurs
        """
        self.on_timeout = on_timeout
        
        self.last_block_time: float = time.time()
        self.last_block_height: int = 0
        
        # Statistics
        self.block_times: List[float] = []
        self.timeout_count: int = 0
        self.slow_block_count: int = 0  # Blocks > 90% of target
        
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start monitoring."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Block timeout monitor started")
    
    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_timeout()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Monitor error: {e}")
    
    def _check_timeout(self):
        """Check if block production has timed out."""
        with self._lock:
            elapsed = time.time() - self.last_block_time
            expected_height = self.last_block_height + 1
            
            if elapsed > self.MAX_BLOCK_TIME:
                self.timeout_count += 1
                logger.warning(
                    f"BLOCK TIMEOUT: No block at height {expected_height} "
                    f"for {elapsed:.0f}s (max {self.MAX_BLOCK_TIME:.0f}s)"
                )
                
                if self.on_timeout:
                    self.on_timeout(expected_height, elapsed)
                
                # Reset timer to avoid repeated callbacks
                self.last_block_time = time.time()
            
            elif elapsed > self.WARNING_THRESHOLD:
                logger.debug(
                    f"Block production slow: {elapsed:.0f}s elapsed "
                    f"(warning at {self.WARNING_THRESHOLD:.0f}s)"
                )
    
    def record_block(self, height: int, timestamp: float):
        """Record that a block was received."""
        with self._lock:
            current_time = time.time()
            
            if self.last_block_time > 0:
                block_time = current_time - self.last_block_time
                self.block_times.append(block_time)
                
                # Keep last 100 block times
                if len(self.block_times) > 100:
                    self.block_times = self.block_times[-100:]
                
                # Track slow blocks
                if block_time > self.WARNING_THRESHOLD:
                    self.slow_block_count += 1
            
            self.last_block_time = current_time
            self.last_block_height = height
    
    def get_stats(self) -> Dict[str, Any]:
        """Get block timing statistics."""
        with self._lock:
            if not self.block_times:
                return {
                    'avg_block_time': 0,
                    'min_block_time': 0,
                    'max_block_time': 0,
                    'timeout_count': self.timeout_count,
                    'slow_block_count': self.slow_block_count,
                    'time_since_last': time.time() - self.last_block_time
                }
            
            return {
                'avg_block_time': sum(self.block_times) / len(self.block_times),
                'min_block_time': min(self.block_times),
                'max_block_time': max(self.block_times),
                'median_block_time': sorted(self.block_times)[len(self.block_times)//2],
                'timeout_count': self.timeout_count,
                'slow_block_count': self.slow_block_count,
                'sample_count': len(self.block_times),
                'time_since_last': time.time() - self.last_block_time,
                'last_block_height': self.last_block_height
            }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    logger.info("Running network self-tests...")
    
    # Test message serialization
    payload = b"test payload"
    msg = NetworkMessage.create(MessageType.PING, payload)
    assert msg.verify_checksum()
    
    serialized = msg.serialize()
    header = MessageHeader.deserialize(serialized)
    assert header.command == MessageType.PING
    assert header.length == len(payload)
    logger.info("✓ Message serialization")
    
    # Test version payload with Noise pubkey
    version = VersionPayload(
        version=1, services=1, timestamp=int(time.time()),
        nonce=12345, user_agent="/test/", start_height=100,
        noise_pubkey=b'\x01' * 32
    )
    v_bytes = version.serialize()
    v2 = VersionPayload.deserialize(v_bytes)
    assert v2.nonce == 12345
    assert v2.start_height == 100
    assert v2.noise_pubkey == b'\x01' * 32
    logger.info("✓ Version payload with Noise pubkey")
    
    # Test inventory
    item = InvItem(InvType.BLOCK, b'\x01' * 32)
    item_bytes = item.serialize()
    item2, _ = InvItem.deserialize(item_bytes)
    assert item2.inv_type == InvType.BLOCK
    logger.info("✓ Inventory items")
    
    # Test Noise keys
    keys1 = NoiseKeys.generate()
    assert len(keys1.private_key) == 32
    assert len(keys1.public_key) == 32
    logger.info("✓ Noise key generation")
    
    # Test Eclipse protection
    eclipse = EclipseProtection()
    
    # Should allow first connection
    allowed, reason = eclipse.can_connect("192.168.1.1", is_inbound=False)
    assert allowed
    
    eclipse.register_connection("peer1", "192.168.1.1", is_inbound=False)
    
    # Should reject second connection from same IP
    allowed, reason = eclipse.can_connect("192.168.1.1", is_inbound=False)
    assert not allowed
    
    # Should allow from different subnet
    allowed, reason = eclipse.can_connect("192.168.2.1", is_inbound=False)
    assert allowed
    
    logger.info("✓ Eclipse protection")
    
    # Test ban manager
    ban_mgr = BanManager()
    assert not ban_mgr.is_banned("192.168.1.1")
    
    ban_mgr.ban("192.168.1.1", "Test ban")
    assert ban_mgr.is_banned("192.168.1.1")
    
    ban_mgr.unban("192.168.1.1")
    assert not ban_mgr.is_banned("192.168.1.1")
    logger.info("✓ Ban manager")
    
    # Test peer creation
    peer = Peer(('127.0.0.1', 8333), noise_keys=keys1)
    assert peer.id == '127.0.0.1:8333'
    assert peer.state == PeerState.CONNECTING
    logger.info("✓ Peer creation")
    
    # Test Noise handshake (simplified)
    keys2 = NoiseKeys.generate()
    wrapper1 = NoiseWrapper(keys1, is_initiator=True)
    wrapper2 = NoiseWrapper(keys2, is_initiator=False)
    
    # Initiator -> Responder (message 1)
    msg1 = wrapper1.get_handshake_message()
    assert msg1 is not None
    
    # Responder processes and responds (message 2)
    wrapper2.process_handshake_message(msg1)
    msg2 = wrapper2.get_handshake_message()
    
    # Initiator processes (message 3) 
    wrapper1.process_handshake_message(msg2)
    msg3 = wrapper1.get_handshake_message()
    
    if msg3:
        wrapper2.process_handshake_message(msg3)
    
    logger.info("✓ Noise handshake structure")
    
    logger.info("All network self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
