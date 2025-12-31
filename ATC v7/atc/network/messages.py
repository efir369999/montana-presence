"""
ATC Protocol v7 Network Messages
Part XIII of Technical Specification

Message types and serialization for P2P communication.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple, TYPE_CHECKING

from atc.constants import (
    PROTOCOL_VERSION,
    NETWORK_ID_MAINNET,
    NETWORK_ID_TESTNET,
    MESSAGE_MAGIC_MAINNET,
    MESSAGE_MAGIC_TESTNET,
    MAX_BLOCK_SIZE_BYTES,
)
from atc.core.types import Hash, PublicKey
from atc.core.serialization import ByteReader, ByteWriter

if TYPE_CHECKING:
    from atc.core.heartbeat import Heartbeat
    from atc.core.transaction import Transaction
    from atc.core.block import Block

logger = logging.getLogger(__name__)


class MessageType(IntEnum):
    """Network message types."""
    # Handshake
    HELLO = 0x01
    HELLO_ACK = 0x02

    # Heartbeat gossip
    HEARTBEAT = 0x10
    HEARTBEAT_INV = 0x11

    # Transaction gossip
    TRANSACTION = 0x20
    TRANSACTION_INV = 0x21

    # Block sync
    BLOCK = 0x30
    BLOCK_INV = 0x31
    GET_BLOCKS = 0x32
    GET_BLOCK_DATA = 0x33

    # Peer discovery
    GET_PEERS = 0x40
    PEERS = 0x41

    # Status
    PING = 0x50
    PONG = 0x51

    # Error
    REJECT = 0xF0


@dataclass
class MessageHeader:
    """
    Network message header.

    Size: 16 bytes
    """
    magic: bytes                # 4 bytes - Network identifier
    msg_type: MessageType       # 1 byte - Message type
    version: int                # 1 byte - Protocol version
    payload_size: int           # 4 bytes - Payload size
    checksum: bytes             # 4 bytes - First 4 bytes of SHA3-256(payload)

    @classmethod
    def size(cls) -> int:
        return 14

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_raw(self.magic)
        writer.write_u8(self.msg_type)
        writer.write_u8(self.version)
        writer.write_u32(self.payload_size)
        writer.write_raw(self.checksum)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "MessageHeader":
        reader = ByteReader(data)
        return cls(
            magic=reader.read_fixed_bytes(4),
            msg_type=MessageType(reader.read_u8()),
            version=reader.read_u8(),
            payload_size=reader.read_u32(),
            checksum=reader.read_fixed_bytes(4),
        )


@dataclass
class Message:
    """Base class for network messages."""
    header: MessageHeader
    payload: bytes

    def serialize(self) -> bytes:
        return self.header.serialize() + self.payload

    @classmethod
    def create(
        cls,
        msg_type: MessageType,
        payload: bytes,
        testnet: bool = False
    ) -> "Message":
        """Create a message with proper header."""
        from atc.crypto.hash import sha3_256

        magic = MESSAGE_MAGIC_TESTNET if testnet else MESSAGE_MAGIC_MAINNET
        checksum = sha3_256(payload).data[:4]

        header = MessageHeader(
            magic=magic,
            msg_type=msg_type,
            version=PROTOCOL_VERSION,
            payload_size=len(payload),
            checksum=checksum,
        )

        return cls(header=header, payload=payload)


@dataclass
class HelloMessage:
    """
    Hello handshake message.

    Sent when connecting to a peer.
    """
    version: int                    # Protocol version
    network_id: int                 # Network identifier
    node_id: PublicKey              # Node's public key
    best_height: int                # Best known block height
    best_hash: Hash                 # Best known block hash
    services: int                   # Supported services bitmap
    timestamp_ms: int               # Current timestamp

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u8(self.version)
        writer.write_u32(self.network_id)
        writer.write_raw(self.node_id.serialize())
        writer.write_u64(self.best_height)
        writer.write_raw(self.best_hash.serialize())
        writer.write_u32(self.services)
        writer.write_u64(self.timestamp_ms)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "HelloMessage":
        reader = ByteReader(data)
        return cls(
            version=reader.read_u8(),
            network_id=reader.read_u32(),
            node_id=PublicKey(reader.read_fixed_bytes(33)),
            best_height=reader.read_u64(),
            best_hash=Hash(reader.read_fixed_bytes(32)),
            services=reader.read_u32(),
            timestamp_ms=reader.read_u64(),
        )

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.HELLO, self.serialize(), testnet)


@dataclass
class HeartbeatMessage:
    """
    Heartbeat gossip message.

    Contains one or more heartbeats for propagation.
    """
    heartbeats: List[bytes]         # Serialized heartbeats

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_varint(len(self.heartbeats))
        for hb_data in self.heartbeats:
            writer.write_varint(len(hb_data))
            writer.write_raw(hb_data)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "HeartbeatMessage":
        reader = ByteReader(data)
        count = reader.read_varint()
        heartbeats = []
        for _ in range(count):
            hb_len = reader.read_varint()
            heartbeats.append(reader.read_fixed_bytes(hb_len))
        return cls(heartbeats=heartbeats)

    @classmethod
    def from_heartbeats(cls, heartbeats: List["Heartbeat"]) -> "HeartbeatMessage":
        return cls(heartbeats=[hb.serialize() for hb in heartbeats])

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.HEARTBEAT, self.serialize(), testnet)


@dataclass
class TransactionMessage:
    """
    Transaction gossip message.

    Contains one or more transactions for propagation.
    """
    transactions: List[bytes]       # Serialized transactions

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_varint(len(self.transactions))
        for tx_data in self.transactions:
            writer.write_varint(len(tx_data))
            writer.write_raw(tx_data)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "TransactionMessage":
        reader = ByteReader(data)
        count = reader.read_varint()
        transactions = []
        for _ in range(count):
            tx_len = reader.read_varint()
            transactions.append(reader.read_fixed_bytes(tx_len))
        return cls(transactions=transactions)

    @classmethod
    def from_transactions(cls, txs: List["Transaction"]) -> "TransactionMessage":
        return cls(transactions=[tx.serialize() for tx in txs])

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.TRANSACTION, self.serialize(), testnet)


@dataclass
class BlockMessage:
    """
    Block message.

    Contains a complete block.
    """
    block_data: bytes              # Serialized block

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_varint(len(self.block_data))
        writer.write_raw(self.block_data)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "BlockMessage":
        reader = ByteReader(data)
        block_len = reader.read_varint()
        return cls(block_data=reader.read_fixed_bytes(block_len))

    @classmethod
    def from_block(cls, block: "Block") -> "BlockMessage":
        return cls(block_data=block.serialize())

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.BLOCK, self.serialize(), testnet)


@dataclass
class GetBlocksMessage:
    """
    Request blocks message.

    Request blocks starting from a hash.
    """
    start_hash: Hash               # Start from this block (exclusive)
    stop_hash: Hash                # Stop at this block (inclusive, or zero for tip)
    max_count: int                 # Maximum blocks to return

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_raw(self.start_hash.serialize())
        writer.write_raw(self.stop_hash.serialize())
        writer.write_u32(self.max_count)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "GetBlocksMessage":
        reader = ByteReader(data)
        return cls(
            start_hash=Hash(reader.read_fixed_bytes(32)),
            stop_hash=Hash(reader.read_fixed_bytes(32)),
            max_count=reader.read_u32(),
        )

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.GET_BLOCKS, self.serialize(), testnet)


@dataclass
class BlockInvMessage:
    """
    Block inventory message.

    Announces available blocks.
    """
    hashes: List[Hash]             # Block hashes (in order)

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_varint(len(self.hashes))
        for h in self.hashes:
            writer.write_raw(h.serialize())
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "BlockInvMessage":
        reader = ByteReader(data)
        count = reader.read_varint()
        hashes = []
        for _ in range(count):
            hashes.append(Hash(reader.read_fixed_bytes(32)))
        return cls(hashes=hashes)

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.BLOCK_INV, self.serialize(), testnet)


@dataclass
class PeerInfo:
    """Peer connection information."""
    address: str                   # IP address or hostname
    port: int                      # Port number
    node_id: Optional[PublicKey]   # Node's public key (if known)
    services: int                  # Supported services
    last_seen: int                 # Last seen timestamp


@dataclass
class PeersMessage:
    """
    Peer list message.

    Response to GET_PEERS.
    """
    peers: List[PeerInfo]

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_varint(len(self.peers))
        for peer in self.peers:
            # Address as string with length prefix
            addr_bytes = peer.address.encode('utf-8')
            writer.write_varint(len(addr_bytes))
            writer.write_raw(addr_bytes)
            writer.write_u16(peer.port)
            # Optional node_id
            if peer.node_id:
                writer.write_u8(1)
                writer.write_raw(peer.node_id.serialize())
            else:
                writer.write_u8(0)
            writer.write_u32(peer.services)
            writer.write_u64(peer.last_seen)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "PeersMessage":
        reader = ByteReader(data)
        count = reader.read_varint()
        peers = []
        for _ in range(count):
            addr_len = reader.read_varint()
            address = reader.read_fixed_bytes(addr_len).decode('utf-8')
            port = reader.read_u16()
            has_node_id = reader.read_u8()
            node_id = None
            if has_node_id:
                node_id = PublicKey(reader.read_fixed_bytes(33))
            services = reader.read_u32()
            last_seen = reader.read_u64()
            peers.append(PeerInfo(
                address=address,
                port=port,
                node_id=node_id,
                services=services,
                last_seen=last_seen,
            ))
        return cls(peers=peers)

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.PEERS, self.serialize(), testnet)


@dataclass
class PingMessage:
    """Ping message for keepalive."""
    nonce: int                     # Random nonce

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u64(self.nonce)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "PingMessage":
        reader = ByteReader(data)
        return cls(nonce=reader.read_u64())

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.PING, self.serialize(), testnet)


@dataclass
class PongMessage:
    """Pong response to ping."""
    nonce: int                     # Echo back the nonce

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u64(self.nonce)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "PongMessage":
        reader = ByteReader(data)
        return cls(nonce=reader.read_u64())

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.PONG, self.serialize(), testnet)


@dataclass
class RejectMessage:
    """Rejection message."""
    rejected_type: MessageType     # Type of rejected message
    code: int                      # Rejection code
    reason: str                    # Human-readable reason
    data: bytes                    # Related data (e.g., block hash)

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u8(self.rejected_type)
        writer.write_u16(self.code)
        reason_bytes = self.reason.encode('utf-8')
        writer.write_varint(len(reason_bytes))
        writer.write_raw(reason_bytes)
        writer.write_varint(len(self.data))
        writer.write_raw(self.data)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes) -> "RejectMessage":
        reader = ByteReader(data)
        rejected_type = MessageType(reader.read_u8())
        code = reader.read_u16()
        reason_len = reader.read_varint()
        reason = reader.read_fixed_bytes(reason_len).decode('utf-8')
        data_len = reader.read_varint()
        data_bytes = reader.read_fixed_bytes(data_len)
        return cls(
            rejected_type=rejected_type,
            code=code,
            reason=reason,
            data=data_bytes,
        )

    def to_message(self, testnet: bool = False) -> Message:
        return Message.create(MessageType.REJECT, self.serialize(), testnet)


def parse_message(data: bytes) -> Tuple[MessageHeader, bytes]:
    """
    Parse a raw message.

    Returns:
        Tuple of (header, payload)
    """
    header_size = MessageHeader.size()

    if len(data) < header_size:
        raise ValueError(f"Data too short for header: {len(data)} < {header_size}")

    header = MessageHeader.deserialize(data[:header_size])

    if len(data) < header_size + header.payload_size:
        raise ValueError(
            f"Data too short for payload: {len(data)} < "
            f"{header_size + header.payload_size}"
        )

    payload = data[header_size:header_size + header.payload_size]

    # Verify checksum
    from atc.crypto.hash import sha3_256
    expected_checksum = sha3_256(payload).data[:4]
    if header.checksum != expected_checksum:
        raise ValueError("Checksum mismatch")

    return header, payload


def get_message_info() -> dict:
    """Get information about message types."""
    return {
        "header_size": MessageHeader.size(),
        "message_types": {
            name: value for name, value in MessageType.__members__.items()
        },
        "max_payload_size": MAX_BLOCK_SIZE_BYTES,
    }
