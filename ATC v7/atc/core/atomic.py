"""
ATC Protocol v7 Atomic Time Structures
Part III Section 3.3 and Part IV of Technical Specification

Layer 0: Physical Time from Global Atomic Nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple

from atc.constants import (
    REGION_EUROPE,
    REGION_ASIA,
    REGION_NORTH_AMERICA,
    REGION_SOUTH_AMERICA,
    REGION_AFRICA,
    REGION_OCEANIA,
    REGION_ANTARCTICA,
    REGION_ARCTIC,
    REGION_BIT_EUROPE,
    REGION_BIT_ASIA,
    REGION_BIT_NORTH_AMERICA,
    REGION_BIT_SOUTH_AMERICA,
    REGION_BIT_AFRICA,
    REGION_BIT_OCEANIA,
    REGION_BIT_ANTARCTICA,
    REGION_BIT_ARCTIC,
    NTP_MIN_SOURCES_CONSENSUS,
    NTP_MIN_REGIONS_TOTAL,
    NTP_MAX_DRIFT_MS,
)
from atc.core.serialization import (
    ByteReader,
    ByteWriter,
    serialize_u8,
    serialize_u16,
    serialize_u64,
    serialize_i32,
    serialize_varint,
)


# Mapping from region code to bit position
REGION_TO_BIT = {
    REGION_EUROPE: REGION_BIT_EUROPE,
    REGION_ASIA: REGION_BIT_ASIA,
    REGION_NORTH_AMERICA: REGION_BIT_NORTH_AMERICA,
    REGION_SOUTH_AMERICA: REGION_BIT_SOUTH_AMERICA,
    REGION_AFRICA: REGION_BIT_AFRICA,
    REGION_OCEANIA: REGION_BIT_OCEANIA,
    REGION_ANTARCTICA: REGION_BIT_ANTARCTICA,
    REGION_ARCTIC: REGION_BIT_ARCTIC,
}


def popcount(x: int) -> int:
    """Count number of set bits in an integer."""
    count = 0
    while x:
        count += x & 1
        x >>= 1
    return count


def region_to_bitmap(region: int) -> int:
    """Convert region code to bitmap with single bit set."""
    bit_pos = REGION_TO_BIT.get(region, 0)
    return 1 << bit_pos


def regions_from_bitmap(bitmap: int) -> List[int]:
    """Extract list of regions from bitmap."""
    regions = []
    for region, bit_pos in REGION_TO_BIT.items():
        if bitmap & (1 << bit_pos):
            regions.append(region)
    return regions


@dataclass(slots=True)
class AtomicSource:
    """
    Single atomic time source response.

    SIZE: 12 bytes
    """
    region: int           # u8 - Region code (0x01-0x08)
    server_id: int        # u8 - Server within region (0-indexed)
    timestamp_ms: int     # u64 - Milliseconds since Unix epoch
    rtt_ms: int           # u16 - Round-trip time in milliseconds

    def __post_init__(self):
        if not 0x01 <= self.region <= 0x08:
            raise ValueError(f"Invalid region: {self.region}")
        if not 0 <= self.server_id <= 255:
            raise ValueError(f"Invalid server_id: {self.server_id}")
        if not 0 <= self.timestamp_ms <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Invalid timestamp_ms: {self.timestamp_ms}")
        if not 0 <= self.rtt_ms <= 65535:
            raise ValueError(f"Invalid rtt_ms: {self.rtt_ms}")

    def serialize(self) -> bytes:
        """Serialize to bytes (12 bytes total)."""
        writer = ByteWriter()
        writer.write_u8(self.region)
        writer.write_u8(self.server_id)
        writer.write_u64(self.timestamp_ms)
        writer.write_u16(self.rtt_ms)
        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["AtomicSource", int]:
        """Deserialize from bytes."""
        reader = ByteReader(data[offset:])
        region = reader.read_u8()
        server_id = reader.read_u8()
        timestamp_ms = reader.read_u64()
        rtt_ms = reader.read_u16()
        return cls(
            region=region,
            server_id=server_id,
            timestamp_ms=timestamp_ms,
            rtt_ms=rtt_ms
        ), reader.offset

    @classmethod
    def size(cls) -> int:
        """Return fixed size in bytes."""
        return 12


@dataclass(slots=True)
class AtomicTimeProof:
    """
    Proof of atomic time consensus.

    SIZE: 14 + (12 * source_count) bytes

    Region bitmap:
        bit 0: Europe
        bit 1: Asia
        bit 2: North America
        bit 3: South America
        bit 4: Africa
        bit 5: Oceania
        bit 6: Antarctica
        bit 7: Arctic
    """
    timestamp_ms: int                     # u64 - Consensus timestamp
    source_count: int                     # u16 - Number of responding sources
    sources: List[AtomicSource]           # Individual responses
    median_drift_ms: int                  # i32 - Drift from median
    region_bitmap: int                    # u8 - Bitmask of responding regions

    def __post_init__(self):
        if self.source_count != len(self.sources):
            raise ValueError(
                f"source_count ({self.source_count}) != len(sources) ({len(self.sources)})"
            )

    def serialize(self) -> bytes:
        """Serialize to bytes."""
        writer = ByteWriter()
        writer.write_u64(self.timestamp_ms)
        writer.write_u16(self.source_count)

        for source in self.sources:
            writer.write_raw(source.serialize())

        writer.write_i32(self.median_drift_ms)
        writer.write_u8(self.region_bitmap)

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["AtomicTimeProof", int]:
        """Deserialize from bytes."""
        reader = ByteReader(data[offset:])

        timestamp_ms = reader.read_u64()
        source_count = reader.read_u16()

        sources = []
        for _ in range(source_count):
            source_data = reader.read_fixed_bytes(AtomicSource.size())
            source, _ = AtomicSource.deserialize(source_data)
            sources.append(source)

        median_drift_ms = reader.read_i32()
        region_bitmap = reader.read_u8()

        return cls(
            timestamp_ms=timestamp_ms,
            source_count=source_count,
            sources=sources,
            median_drift_ms=median_drift_ms,
            region_bitmap=region_bitmap
        ), reader.offset

    def size(self) -> int:
        """Return size in bytes."""
        return 14 + (12 * self.source_count)

    def region_count(self) -> int:
        """Return number of regions represented."""
        return popcount(self.region_bitmap)

    def has_region(self, region: int) -> bool:
        """Check if a specific region is represented."""
        bit_pos = REGION_TO_BIT.get(region, 0)
        return bool(self.region_bitmap & (1 << bit_pos))

    def get_regions(self) -> List[int]:
        """Get list of represented regions."""
        return regions_from_bitmap(self.region_bitmap)

    def count_sources_in_region(self, region: int) -> int:
        """Count number of sources from a specific region."""
        return sum(1 for s in self.sources if s.region == region)

    def get_timestamps(self) -> List[int]:
        """Get all source timestamps."""
        return [s.timestamp_ms for s in self.sources]

    def compute_median_timestamp(self) -> int:
        """Compute median of source timestamps."""
        if not self.sources:
            return 0
        timestamps = sorted(s.timestamp_ms for s in self.sources)
        mid = len(timestamps) // 2
        if len(timestamps) % 2 == 0:
            return (timestamps[mid - 1] + timestamps[mid]) // 2
        return timestamps[mid]

    def is_valid_basic(self) -> bool:
        """
        Perform basic validity checks.

        Returns True if:
        - Has minimum required sources
        - Has minimum required regions
        - Drift is within acceptable range
        """
        if self.source_count < NTP_MIN_SOURCES_CONSENSUS:
            return False

        if self.region_count() < NTP_MIN_REGIONS_TOTAL:
            return False

        if abs(self.median_drift_ms) > NTP_MAX_DRIFT_MS:
            return False

        return True

    @classmethod
    def empty(cls) -> "AtomicTimeProof":
        """Create an empty atomic time proof."""
        return cls(
            timestamp_ms=0,
            source_count=0,
            sources=[],
            median_drift_ms=0,
            region_bitmap=0
        )

    def __repr__(self) -> str:
        return (
            f"AtomicTimeProof(timestamp_ms={self.timestamp_ms}, "
            f"sources={self.source_count}, regions={self.region_count()}, "
            f"drift_ms={self.median_drift_ms})"
        )
