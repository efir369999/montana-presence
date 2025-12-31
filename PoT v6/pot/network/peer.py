"""
PoT Protocol v6 Peer Management
Part XIII of Technical Specification

Peer connections and management.
"""

from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Callable, Any

from pot.constants import (
    DEFAULT_PORT,
    PROTOCOL_VERSION,
)
from pot.core.types import Hash, PublicKey
from pot.network.messages import (
    Message,
    MessageType,
    HelloMessage,
    PingMessage,
    PongMessage,
    parse_message,
)

logger = logging.getLogger(__name__)


class PeerState(Enum):
    """Peer connection state."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    HANDSHAKING = auto()
    ACTIVE = auto()
    BANNED = auto()


@dataclass
class PeerStats:
    """Statistics for a peer connection."""
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    heartbeats_received: int = 0
    transactions_received: int = 0
    blocks_received: int = 0
    ping_count: int = 0
    last_ping_time_ms: int = 0
    avg_latency_ms: float = 0.0
    connect_time: int = 0
    last_message_time: int = 0


@dataclass
class Peer:
    """
    Represents a remote peer.

    Manages connection state, message handling, and statistics.
    """
    address: str
    port: int = DEFAULT_PORT
    node_id: Optional[PublicKey] = None

    # State
    state: PeerState = PeerState.DISCONNECTED
    inbound: bool = False

    # Peer's reported info
    version: int = 0
    best_height: int = 0
    best_hash: Optional[Hash] = None
    services: int = 0

    # Statistics
    stats: PeerStats = field(default_factory=PeerStats)

    # Connection
    _reader: Optional[asyncio.StreamReader] = None
    _writer: Optional[asyncio.StreamWriter] = None
    _read_task: Optional[asyncio.Task] = None
    _ping_task: Optional[asyncio.Task] = None
    _pending_pings: Dict[int, float] = field(default_factory=dict)

    # Callbacks
    _message_handler: Optional[Callable] = None

    def __post_init__(self):
        self.stats = PeerStats()
        self._pending_pings = {}

    @property
    def peer_id(self) -> str:
        """Get unique peer identifier."""
        if self.node_id:
            return self.node_id.data.hex()[:16]
        return f"{self.address}:{self.port}"

    @property
    def is_connected(self) -> bool:
        """Check if peer is connected."""
        return self.state in (PeerState.CONNECTED, PeerState.HANDSHAKING, PeerState.ACTIVE)

    @property
    def is_active(self) -> bool:
        """Check if peer completed handshake."""
        return self.state == PeerState.ACTIVE

    @property
    def uptime_seconds(self) -> int:
        """Get connection uptime in seconds."""
        if self.stats.connect_time == 0:
            return 0
        return int(time.time() - self.stats.connect_time / 1000)

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to the peer.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connection succeeded
        """
        if self.is_connected:
            return True

        self.state = PeerState.CONNECTING

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.address, self.port),
                timeout=timeout
            )

            self.state = PeerState.CONNECTED
            self.stats.connect_time = int(time.time() * 1000)

            logger.info(f"Connected to peer {self.peer_id}")
            return True

        except asyncio.TimeoutError:
            logger.warning(f"Connection to {self.peer_id} timed out")
            self.state = PeerState.DISCONNECTED
            return False

        except Exception as e:
            logger.warning(f"Connection to {self.peer_id} failed: {e}")
            self.state = PeerState.DISCONNECTED
            return False

    async def disconnect(self) -> None:
        """Disconnect from the peer."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None
        self.state = PeerState.DISCONNECTED

        logger.info(f"Disconnected from peer {self.peer_id}")

    async def send_message(self, message: Message) -> bool:
        """
        Send a message to the peer.

        Args:
            message: Message to send

        Returns:
            True if message was sent
        """
        if not self._writer:
            return False

        try:
            data = message.serialize()
            self._writer.write(data)
            await self._writer.drain()

            self.stats.messages_sent += 1
            self.stats.bytes_sent += len(data)

            return True

        except Exception as e:
            logger.warning(f"Failed to send message to {self.peer_id}: {e}")
            await self.disconnect()
            return False

    async def read_message(self, timeout: float = 30.0) -> Optional[Message]:
        """
        Read a message from the peer.

        Args:
            timeout: Read timeout in seconds

        Returns:
            Message or None if failed
        """
        if not self._reader:
            return None

        try:
            # Read header first
            header_data = await asyncio.wait_for(
                self._reader.readexactly(14),
                timeout=timeout
            )

            from pot.network.messages import MessageHeader
            header = MessageHeader.deserialize(header_data)

            # Read payload
            payload = await asyncio.wait_for(
                self._reader.readexactly(header.payload_size),
                timeout=timeout
            )

            self.stats.messages_received += 1
            self.stats.bytes_received += 14 + header.payload_size
            self.stats.last_message_time = int(time.time() * 1000)

            return Message(header=header, payload=payload)

        except asyncio.TimeoutError:
            logger.debug(f"Read timeout from {self.peer_id}")
            return None

        except asyncio.IncompleteReadError:
            logger.warning(f"Incomplete read from {self.peer_id}, disconnecting")
            await self.disconnect()
            return None

        except Exception as e:
            logger.warning(f"Read error from {self.peer_id}: {e}")
            await self.disconnect()
            return None

    async def handshake(
        self,
        our_node_id: PublicKey,
        our_height: int,
        our_best_hash: Hash,
        testnet: bool = False
    ) -> bool:
        """
        Perform handshake with peer.

        Args:
            our_node_id: Our node's public key
            our_height: Our best block height
            our_best_hash: Our best block hash
            testnet: Whether this is testnet

        Returns:
            True if handshake succeeded
        """
        self.state = PeerState.HANDSHAKING

        # Send HELLO
        from pot.constants import NETWORK_ID_MAINNET, NETWORK_ID_TESTNET

        hello = HelloMessage(
            version=PROTOCOL_VERSION,
            network_id=NETWORK_ID_TESTNET if testnet else NETWORK_ID_MAINNET,
            node_id=our_node_id,
            best_height=our_height,
            best_hash=our_best_hash,
            services=0x01,  # Full node
            timestamp_ms=int(time.time() * 1000),
        )

        if not await self.send_message(hello.to_message(testnet)):
            self.state = PeerState.DISCONNECTED
            return False

        # Wait for HELLO response
        response = await self.read_message(timeout=30.0)
        if response is None:
            self.state = PeerState.DISCONNECTED
            return False

        if response.header.msg_type != MessageType.HELLO:
            logger.warning(f"Expected HELLO, got {response.header.msg_type}")
            self.state = PeerState.DISCONNECTED
            return False

        # Parse peer's HELLO
        peer_hello = HelloMessage.deserialize(response.payload)

        self.version = peer_hello.version
        self.node_id = peer_hello.node_id
        self.best_height = peer_hello.best_height
        self.best_hash = peer_hello.best_hash
        self.services = peer_hello.services

        self.state = PeerState.ACTIVE

        logger.info(
            f"Handshake complete with {self.peer_id}, "
            f"height={self.best_height}"
        )

        return True

    async def ping(self) -> Optional[float]:
        """
        Send ping and wait for pong.

        Returns:
            Latency in milliseconds or None if failed
        """
        import random

        nonce = random.randint(0, 2**64 - 1)
        start_time = time.time()

        ping_msg = PingMessage(nonce=nonce)
        if not await self.send_message(ping_msg.to_message()):
            return None

        self._pending_pings[nonce] = start_time
        self.stats.ping_count += 1

        # Wait for pong (handled by message loop)
        for _ in range(100):  # 10 second timeout
            if nonce not in self._pending_pings:
                # Pong received
                return self.stats.avg_latency_ms

            await asyncio.sleep(0.1)

        # Timeout
        self._pending_pings.pop(nonce, None)
        return None

    def handle_pong(self, nonce: int) -> None:
        """Handle pong response."""
        if nonce in self._pending_pings:
            start_time = self._pending_pings.pop(nonce)
            latency = (time.time() - start_time) * 1000
            self.stats.last_ping_time_ms = int(latency)

            # Update average
            if self.stats.avg_latency_ms == 0:
                self.stats.avg_latency_ms = latency
            else:
                self.stats.avg_latency_ms = (
                    self.stats.avg_latency_ms * 0.9 + latency * 0.1
                )

    def set_message_handler(self, handler: Callable) -> None:
        """Set callback for received messages."""
        self._message_handler = handler

    async def start_read_loop(self) -> None:
        """Start background message reading loop."""
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Background message reading loop."""
        while self.is_connected:
            try:
                message = await self.read_message(timeout=60.0)

                if message is None:
                    continue

                # Handle pong internally
                if message.header.msg_type == MessageType.PONG:
                    pong = PongMessage.deserialize(message.payload)
                    self.handle_pong(pong.nonce)
                    continue

                # Handle ping internally
                if message.header.msg_type == MessageType.PING:
                    ping = PingMessage.deserialize(message.payload)
                    pong = PongMessage(nonce=ping.nonce)
                    await self.send_message(pong.to_message())
                    continue

                # Pass to handler
                if self._message_handler:
                    try:
                        await self._message_handler(self, message)
                    except Exception as e:
                        logger.error(f"Message handler error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Read loop error: {e}")
                break

    def to_dict(self) -> dict:
        """Export peer info as dictionary."""
        return {
            "address": self.address,
            "port": self.port,
            "node_id": self.node_id.data.hex() if self.node_id else None,
            "state": self.state.name,
            "version": self.version,
            "best_height": self.best_height,
            "services": self.services,
            "uptime_seconds": self.uptime_seconds,
            "messages_sent": self.stats.messages_sent,
            "messages_received": self.stats.messages_received,
            "avg_latency_ms": self.stats.avg_latency_ms,
        }


@dataclass
class PeerManager:
    """
    Manages multiple peer connections.

    Handles peer discovery, connection management, and message routing.
    """
    max_peers: int = 50
    max_inbound: int = 25

    # Peer collections
    _peers: Dict[str, Peer] = field(default_factory=dict)
    _banned: Set[str] = field(default_factory=set)

    # State
    _our_node_id: Optional[PublicKey] = None
    _our_height: int = 0
    _our_best_hash: Optional[Hash] = None
    _testnet: bool = False

    # Callbacks
    _message_handler: Optional[Callable] = None

    def __post_init__(self):
        self._peers = {}
        self._banned = set()

    def set_node_info(
        self,
        node_id: PublicKey,
        height: int,
        best_hash: Hash,
        testnet: bool = False
    ) -> None:
        """Set our node information for handshakes."""
        self._our_node_id = node_id
        self._our_height = height
        self._our_best_hash = best_hash
        self._testnet = testnet

    def update_height(self, height: int, best_hash: Hash) -> None:
        """Update our best block info."""
        self._our_height = height
        self._our_best_hash = best_hash

    def set_message_handler(self, handler: Callable) -> None:
        """Set callback for received messages."""
        self._message_handler = handler

    @property
    def peer_count(self) -> int:
        """Get number of connected peers."""
        return len([p for p in self._peers.values() if p.is_connected])

    @property
    def active_peer_count(self) -> int:
        """Get number of active (handshaked) peers."""
        return len([p for p in self._peers.values() if p.is_active])

    def get_peer(self, peer_id: str) -> Optional[Peer]:
        """Get peer by ID."""
        return self._peers.get(peer_id)

    def get_active_peers(self) -> List[Peer]:
        """Get all active peers."""
        return [p for p in self._peers.values() if p.is_active]

    def get_best_peers(self, count: int = 10) -> List[Peer]:
        """Get peers with highest block height."""
        active = self.get_active_peers()
        active.sort(key=lambda p: p.best_height, reverse=True)
        return active[:count]

    async def add_peer(
        self,
        address: str,
        port: int = DEFAULT_PORT,
        inbound: bool = False
    ) -> Optional[Peer]:
        """
        Add and connect to a new peer.

        Args:
            address: Peer address
            port: Peer port
            inbound: Whether this is an inbound connection

        Returns:
            Peer if connection succeeded
        """
        peer_key = f"{address}:{port}"

        # Check if banned
        if peer_key in self._banned:
            logger.debug(f"Peer {peer_key} is banned")
            return None

        # Check if already connected
        if peer_key in self._peers:
            return self._peers[peer_key]

        # Check limits
        if len(self._peers) >= self.max_peers:
            logger.debug("Max peers reached")
            return None

        inbound_count = len([p for p in self._peers.values() if p.inbound])
        if inbound and inbound_count >= self.max_inbound:
            logger.debug("Max inbound peers reached")
            return None

        # Create and connect peer
        peer = Peer(address=address, port=port, inbound=inbound)

        if not await peer.connect():
            return None

        # Perform handshake
        if self._our_node_id and self._our_best_hash:
            if not await peer.handshake(
                self._our_node_id,
                self._our_height,
                self._our_best_hash,
                self._testnet
            ):
                await peer.disconnect()
                return None

        # Set message handler
        if self._message_handler:
            peer.set_message_handler(self._message_handler)

        # Start read loop
        await peer.start_read_loop()

        self._peers[peer_key] = peer

        logger.info(f"Added peer {peer.peer_id}")
        return peer

    async def remove_peer(self, peer_key: str) -> None:
        """Remove and disconnect a peer."""
        if peer_key in self._peers:
            peer = self._peers.pop(peer_key)
            await peer.disconnect()
            logger.info(f"Removed peer {peer.peer_id}")

    def ban_peer(self, peer_key: str, reason: str = "") -> None:
        """Ban a peer."""
        self._banned.add(peer_key)
        logger.warning(f"Banned peer {peer_key}: {reason}")

        # Disconnect if connected
        if peer_key in self._peers:
            asyncio.create_task(self.remove_peer(peer_key))

    def unban_peer(self, peer_key: str) -> None:
        """Remove peer from ban list."""
        self._banned.discard(peer_key)

    async def broadcast(
        self,
        message: Message,
        exclude: Optional[Set[str]] = None
    ) -> int:
        """
        Broadcast message to all active peers.

        Args:
            message: Message to broadcast
            exclude: Set of peer IDs to exclude

        Returns:
            Number of peers message was sent to
        """
        exclude = exclude or set()
        sent_count = 0

        for peer_key, peer in self._peers.items():
            if not peer.is_active:
                continue

            if peer.peer_id in exclude or peer_key in exclude:
                continue

            if await peer.send_message(message):
                sent_count += 1

        return sent_count

    async def send_to_peer(
        self,
        peer_key: str,
        message: Message
    ) -> bool:
        """Send message to a specific peer."""
        peer = self._peers.get(peer_key)
        if peer and peer.is_active:
            return await peer.send_message(message)
        return False

    async def disconnect_all(self) -> None:
        """Disconnect all peers."""
        for peer in list(self._peers.values()):
            await peer.disconnect()
        self._peers.clear()

    def get_statistics(self) -> dict:
        """Get peer manager statistics."""
        active = self.get_active_peers()

        total_sent = sum(p.stats.messages_sent for p in active)
        total_received = sum(p.stats.messages_received for p in active)
        avg_height = sum(p.best_height for p in active) / len(active) if active else 0

        return {
            "peer_count": self.peer_count,
            "active_count": self.active_peer_count,
            "banned_count": len(self._banned),
            "total_messages_sent": total_sent,
            "total_messages_received": total_received,
            "average_peer_height": avg_height,
        }

    def to_dict(self) -> List[dict]:
        """Export all peers as list of dictionaries."""
        return [peer.to_dict() for peer in self._peers.values()]


def get_peer_info() -> dict:
    """Get information about peer management."""
    return {
        "default_port": DEFAULT_PORT,
        "max_peers_default": 50,
        "max_inbound_default": 25,
        "handshake_timeout_sec": 30,
        "ping_interval_sec": 60,
    }
