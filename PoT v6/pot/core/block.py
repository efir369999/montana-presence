"""
PoT Protocol v6 Block Structure
Part III Section 3.8 and Part XI of Technical Specification

Block header and body with Merkle commitments.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple

from pot.constants import (
    PROTOCOL_VERSION,
    MAX_BLOCK_SIZE_BYTES,
    MAX_HEARTBEATS_PER_BLOCK,
    MAX_TRANSACTIONS_PER_BLOCK,
)
from pot.core.types import Hash, PublicKey, Signature
from pot.core.bitcoin import BitcoinAnchor
from pot.core.heartbeat import Heartbeat
from pot.core.transaction import Transaction
from pot.core.serialization import ByteReader, ByteWriter
from pot.crypto.hash import sha3_256
from pot.crypto.merkle import merkle_root


@dataclass(slots=True)
class BlockHeader:
    """
    Block header with commitments.

    SIZE: 282 bytes
    """
    version: int                        # u32 - Protocol version
    height: int                         # u64 - Block height
    parent_hash: Hash                   # Previous block hash
    timestamp_ms: int                   # u64 - Atomic timestamp

    # Merkle roots
    heartbeats_root: Hash               # Merkle root of heartbeats
    transactions_root: Hash             # Merkle root of transactions
    state_root: Hash                    # State trie root

    # Layer 2 anchor
    btc_anchor: BitcoinAnchor           # Bitcoin reference

    def serialize(self) -> bytes:
        """Serialize block header."""
        writer = ByteWriter()

        writer.write_u32(self.version)
        writer.write_u64(self.height)
        writer.write_raw(self.parent_hash.serialize())
        writer.write_u64(self.timestamp_ms)
        writer.write_raw(self.heartbeats_root.serialize())
        writer.write_raw(self.transactions_root.serialize())
        writer.write_raw(self.state_root.serialize())
        writer.write_raw(self.btc_anchor.serialize())

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["BlockHeader", int]:
        """Deserialize block header."""
        reader = ByteReader(data[offset:])

        version = reader.read_u32()
        height = reader.read_u64()
        parent_hash = Hash(reader.read_fixed_bytes(32))
        timestamp_ms = reader.read_u64()
        heartbeats_root = Hash(reader.read_fixed_bytes(32))
        transactions_root = Hash(reader.read_fixed_bytes(32))
        state_root = Hash(reader.read_fixed_bytes(32))

        remaining = data[offset + reader.offset:]
        btc_anchor, btc_consumed = BitcoinAnchor.deserialize(remaining)

        return cls(
            version=version,
            height=height,
            parent_hash=parent_hash,
            timestamp_ms=timestamp_ms,
            heartbeats_root=heartbeats_root,
            transactions_root=transactions_root,
            state_root=state_root,
            btc_anchor=btc_anchor
        ), reader.offset + btc_consumed

    @classmethod
    def size(cls) -> int:
        """Return fixed size in bytes."""
        return 4 + 8 + 32 + 8 + 32 + 32 + 32 + 90  # 238 bytes

    def block_hash(self) -> Hash:
        """Compute block hash from header."""
        return sha3_256(self.serialize())


@dataclass(slots=True)
class BlockSigner:
    """
    Block signer with score.

    Per specification: Signers contribute their score-weighted signature.
    """
    pubkey: PublicKey                   # Signer identity
    score_fixed: int                    # Score x 10^6 (fixed-point, u64)
    signature: Signature                # Block signature

    def serialize(self) -> bytes:
        """Serialize block signer."""
        writer = ByteWriter()
        writer.write_raw(self.pubkey.serialize())
        writer.write_u64(self.score_fixed)
        writer.write_raw(self.signature.serialize())
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["BlockSigner", int]:
        """Deserialize block signer."""
        pk_data = data[offset:offset + 33]
        pubkey, _ = PublicKey.deserialize(pk_data)
        offset_local = 33

        reader = ByteReader(data[offset + offset_local:])
        score_fixed = reader.read_u64()
        offset_local += reader.offset

        remaining = data[offset + offset_local:]
        signature, sig_consumed = Signature.deserialize(remaining)

        return cls(
            pubkey=pubkey,
            score_fixed=score_fixed,
            signature=signature
        ), offset_local + sig_consumed

    def score(self) -> float:
        """Get score as float."""
        return self.score_fixed / 1_000_000.0


@dataclass
class Block:
    """
    Complete block with header, content, and signatures.
    """
    header: BlockHeader
    heartbeats: List[Heartbeat] = field(default_factory=list)
    transactions: List[Transaction] = field(default_factory=list)
    signers: List[BlockSigner] = field(default_factory=list)

    def serialize(self) -> bytes:
        """Serialize complete block."""
        writer = ByteWriter()

        # Header
        writer.write_raw(self.header.serialize())

        # Heartbeats
        writer.write_varint(len(self.heartbeats))
        for hb in self.heartbeats:
            hb_bytes = hb.serialize()
            writer.write_varint(len(hb_bytes))
            writer.write_raw(hb_bytes)

        # Transactions
        writer.write_varint(len(self.transactions))
        for tx in self.transactions:
            tx_bytes = tx.serialize()
            writer.write_varint(len(tx_bytes))
            writer.write_raw(tx_bytes)

        # Signers
        writer.write_varint(len(self.signers))
        for signer in self.signers:
            writer.write_raw(signer.serialize())

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["Block", int]:
        """Deserialize complete block."""
        start_offset = offset

        # Header
        header, consumed = BlockHeader.deserialize(data, offset)
        offset += consumed

        reader = ByteReader(data[offset:])

        # Heartbeats
        hb_count = reader.read_varint()
        heartbeats = []
        for _ in range(hb_count):
            hb_len = reader.read_varint()
            hb_data = reader.read_fixed_bytes(hb_len)
            hb, _ = Heartbeat.deserialize(hb_data)
            heartbeats.append(hb)

        # Transactions
        tx_count = reader.read_varint()
        transactions = []
        for _ in range(tx_count):
            tx_len = reader.read_varint()
            tx_data = reader.read_fixed_bytes(tx_len)
            tx, _ = Transaction.deserialize(tx_data)
            transactions.append(tx)

        # Signers
        signer_count = reader.read_varint()
        signers = []
        remaining = data[offset + reader.offset:]
        signer_offset = 0
        for _ in range(signer_count):
            signer, consumed = BlockSigner.deserialize(remaining, signer_offset)
            signers.append(signer)
            signer_offset += consumed

        return cls(
            header=header,
            heartbeats=heartbeats,
            transactions=transactions,
            signers=signers
        ), offset + reader.offset + signer_offset - start_offset

    def block_hash(self) -> Hash:
        """Compute block hash from header."""
        return self.header.block_hash()

    def compute_heartbeats_root(self) -> Hash:
        """Compute Merkle root of heartbeats."""
        if not self.heartbeats:
            return Hash.zero()
        hashes = [hb.heartbeat_id() for hb in self.heartbeats]
        return merkle_root(hashes)

    def compute_transactions_root(self) -> Hash:
        """Compute Merkle root of transactions."""
        if not self.transactions:
            return Hash.zero()
        hashes = [tx.transaction_id() for tx in self.transactions]
        return merkle_root(hashes)

    def verify_merkle_roots(self) -> bool:
        """Verify that Merkle roots in header match content."""
        expected_hb = self.compute_heartbeats_root()
        if self.header.heartbeats_root != expected_hb:
            return False

        expected_tx = self.compute_transactions_root()
        if self.header.transactions_root != expected_tx:
            return False

        return True

    def size(self) -> int:
        """Return block size in bytes."""
        return len(self.serialize())

    def is_within_size_limit(self) -> bool:
        """Check if block is within size limit."""
        return self.size() <= MAX_BLOCK_SIZE_BYTES

    def is_within_content_limits(self) -> bool:
        """Check if block content counts are within limits."""
        if len(self.heartbeats) > MAX_HEARTBEATS_PER_BLOCK:
            return False
        if len(self.transactions) > MAX_TRANSACTIONS_PER_BLOCK:
            return False
        return True

    def total_score(self) -> float:
        """Get total score from all signers."""
        return sum(s.score() for s in self.signers)

    @classmethod
    def empty(cls, parent_hash: Hash = None) -> "Block":
        """Create an empty block."""
        if parent_hash is None:
            parent_hash = Hash.zero()

        return cls(
            header=BlockHeader(
                version=PROTOCOL_VERSION,
                height=0,
                parent_hash=parent_hash,
                timestamp_ms=0,
                heartbeats_root=Hash.zero(),
                transactions_root=Hash.zero(),
                state_root=Hash.zero(),
                btc_anchor=BitcoinAnchor.empty()
            )
        )

    def __repr__(self) -> str:
        return (
            f"Block(height={self.header.height}, "
            f"hash={self.block_hash().hex()[:16]}..., "
            f"hb={len(self.heartbeats)}, tx={len(self.transactions)}, "
            f"signers={len(self.signers)})"
        )


def block_hash(block: Block) -> Hash:
    """Compute block hash."""
    return block.block_hash()
