"""
ATC Protocol v7 Bitcoin Anchor Structure
Part III Section 3.5 and Part VI of Technical Specification

Layer 2: Finalization through Bitcoin blockchain.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from atc.constants import (
    BTC_HALVING_INTERVAL,
    BTC_MAX_DRIFT_BLOCKS,
    LITTLE_ENDIAN,
)
from atc.core.serialization import ByteReader, ByteWriter


@dataclass(slots=True)
class BitcoinAnchor:
    """
    Bitcoin block reference for finalization.

    SIZE: 90 bytes

    Bitcoin provides absolute finalization. Its 15+ years of accumulated
    proof of work represents the most secure timestamping mechanism ever created.
    """
    height: int              # u64 - Block height
    block_hash: bytes        # bytes[32] - Block hash (little-endian as in Bitcoin)
    merkle_root: bytes       # bytes[32] - Merkle root
    timestamp: int           # u64 - Block timestamp (Unix seconds)
    difficulty: int          # u64 - Compact difficulty (nBits expanded)
    epoch: int               # u32 - Halving epoch (height / 210000)
    confirmations: int       # u16 - Confirmations at anchor time

    def __post_init__(self):
        if len(self.block_hash) != 32:
            raise ValueError(f"block_hash must be 32 bytes, got {len(self.block_hash)}")
        if len(self.merkle_root) != 32:
            raise ValueError(f"merkle_root must be 32 bytes, got {len(self.merkle_root)}")
        if not 0 <= self.height <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Invalid height: {self.height}")
        if not 0 <= self.epoch <= 0xFFFFFFFF:
            raise ValueError(f"Invalid epoch: {self.epoch}")
        if not 0 <= self.confirmations <= 0xFFFF:
            raise ValueError(f"Invalid confirmations: {self.confirmations}")

    def serialize(self) -> bytes:
        """Serialize to bytes (90 bytes total)."""
        writer = ByteWriter()
        writer.write_u64(self.height)
        writer.write_raw(self.block_hash)  # 32 bytes, little-endian
        writer.write_raw(self.merkle_root)  # 32 bytes
        writer.write_u64(self.timestamp)
        writer.write_u64(self.difficulty)
        writer.write_u32(self.epoch)
        writer.write_u16(self.confirmations)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["BitcoinAnchor", int]:
        """Deserialize from bytes."""
        reader = ByteReader(data[offset:])

        height = reader.read_u64()
        block_hash = reader.read_fixed_bytes(32)
        merkle_root = reader.read_fixed_bytes(32)
        timestamp = reader.read_u64()
        difficulty = reader.read_u64()
        epoch = reader.read_u32()
        confirmations = reader.read_u16()

        return cls(
            height=height,
            block_hash=block_hash,
            merkle_root=merkle_root,
            timestamp=timestamp,
            difficulty=difficulty,
            epoch=epoch,
            confirmations=confirmations
        ), reader.offset

    @classmethod
    def size(cls) -> int:
        """Return fixed size in bytes."""
        return 90

    def block_hash_hex(self) -> str:
        """
        Return block hash as hex string in Bitcoin display format.

        Bitcoin displays hashes with bytes reversed (big-endian for display).
        """
        return self.block_hash[::-1].hex()

    def merkle_root_hex(self) -> str:
        """Return merkle root as hex string in Bitcoin display format."""
        return self.merkle_root[::-1].hex()

    @classmethod
    def from_api_data(
        cls,
        height: int,
        block_hash_hex: str,
        merkle_root_hex: str,
        timestamp: int,
        difficulty: int,
        confirmations: int = 0
    ) -> "BitcoinAnchor":
        """
        Create from API response data.

        Block hash and merkle root hex strings are expected in Bitcoin's
        display format (reversed bytes).
        """
        # Reverse bytes for internal storage (Bitcoin's native format)
        block_hash = bytes.fromhex(block_hash_hex)[::-1]
        merkle_root = bytes.fromhex(merkle_root_hex)[::-1]

        epoch = height // BTC_HALVING_INTERVAL

        return cls(
            height=height,
            block_hash=block_hash,
            merkle_root=merkle_root,
            timestamp=timestamp,
            difficulty=difficulty,
            epoch=epoch,
            confirmations=confirmations
        )

    def is_within_drift(self, current_height: int) -> bool:
        """Check if this anchor is within acceptable drift of current height."""
        if current_height < self.height:
            return False
        return (current_height - self.height) <= BTC_MAX_DRIFT_BLOCKS

    def expected_epoch(self) -> int:
        """Calculate expected epoch from height."""
        return self.height // BTC_HALVING_INTERVAL

    def is_epoch_valid(self) -> bool:
        """Check if epoch matches height."""
        return self.epoch == self.expected_epoch()

    def is_epoch_boundary(self) -> bool:
        """Check if this block is at an epoch (halving) boundary."""
        return self.height % BTC_HALVING_INTERVAL == 0

    def blocks_until_halving(self) -> int:
        """Return number of blocks until next halving."""
        next_halving = (self.epoch + 1) * BTC_HALVING_INTERVAL
        return next_halving - self.height

    def timestamp_ms(self) -> int:
        """Return timestamp in milliseconds."""
        return self.timestamp * 1000

    @classmethod
    def empty(cls) -> "BitcoinAnchor":
        """Create an empty Bitcoin anchor (for initialization)."""
        return cls(
            height=0,
            block_hash=bytes(32),
            merkle_root=bytes(32),
            timestamp=0,
            difficulty=0,
            epoch=0,
            confirmations=0
        )

    def __repr__(self) -> str:
        return (
            f"BitcoinAnchor(height={self.height}, "
            f"hash={self.block_hash_hex()[:16]}..., "
            f"epoch={self.epoch}, confs={self.confirmations})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BitcoinAnchor):
            return False
        return (
            self.height == other.height and
            self.block_hash == other.block_hash and
            self.merkle_root == other.merkle_root and
            self.timestamp == other.timestamp and
            self.difficulty == other.difficulty and
            self.epoch == other.epoch and
            self.confirmations == other.confirmations
        )

    def __hash__(self) -> int:
        return hash((
            self.height,
            self.block_hash,
            self.merkle_root,
            self.timestamp,
            self.difficulty,
            self.epoch,
            self.confirmations
        ))
