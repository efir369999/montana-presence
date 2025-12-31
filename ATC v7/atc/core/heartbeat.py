"""
ATC Protocol v7 Heartbeat Structure
Part III Section 3.6 and Part VII of Technical Specification

A heartbeat is proof of temporal presence across all three layers.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from atc.constants import PROTOCOL_VERSION
from atc.core.types import Hash, PublicKey, Signature
from atc.core.atomic import AtomicTimeProof
from atc.core.vdf import VDFProof
from atc.core.bitcoin import BitcoinAnchor
from atc.core.serialization import ByteReader, ByteWriter
from atc.crypto.hash import sha3_256


@dataclass(slots=True)
class Heartbeat:
    """
    Proof of temporal presence across all three layers.

    A heartbeat combines:
    - Layer 0: Physical time from atomic sources
    - Layer 1: VDF proof of elapsed time
    - Layer 2: Bitcoin anchor for finalization

    SIZE: Variable (depends on atomic sources and STARK proof)
    """
    # Identity
    pubkey: PublicKey                   # 33 bytes

    # Layer 0: Physical Time
    atomic_time: AtomicTimeProof        # Variable

    # Layer 1: Temporal Proof
    vdf_proof: VDFProof                 # Variable

    # Layer 2: Bitcoin Anchor
    btc_anchor: BitcoinAnchor           # 90 bytes

    # Metadata
    sequence: int                       # u64 - Heartbeat sequence number
    version: int                        # u8 - Heartbeat version

    # Signature
    signature: Signature                # 17089 bytes

    def serialize(self) -> bytes:
        """Serialize complete heartbeat."""
        writer = ByteWriter()

        # Identity
        writer.write_raw(self.pubkey.serialize())

        # Layer 0
        writer.write_raw(self.atomic_time.serialize())

        # Layer 1
        writer.write_raw(self.vdf_proof.serialize())

        # Layer 2
        writer.write_raw(self.btc_anchor.serialize())

        # Metadata
        writer.write_u64(self.sequence)
        writer.write_u8(self.version)

        # Signature
        writer.write_raw(self.signature.serialize())

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["Heartbeat", int]:
        """Deserialize from bytes."""
        start_offset = offset

        # Identity
        pubkey, consumed = PublicKey.deserialize(data, offset)
        offset += consumed

        # Layer 0
        atomic_time, consumed = AtomicTimeProof.deserialize(data, offset)
        offset += consumed

        # Layer 1
        vdf_proof, consumed = VDFProof.deserialize(data, offset)
        offset += consumed

        # Layer 2
        btc_anchor, consumed = BitcoinAnchor.deserialize(data, offset)
        offset += consumed

        # Metadata
        reader = ByteReader(data[offset:])
        sequence = reader.read_u64()
        version = reader.read_u8()
        offset += reader.offset

        # Signature
        signature, consumed = Signature.deserialize(data, offset)
        offset += consumed

        return cls(
            pubkey=pubkey,
            atomic_time=atomic_time,
            vdf_proof=vdf_proof,
            btc_anchor=btc_anchor,
            sequence=sequence,
            version=version,
            signature=signature
        ), offset - start_offset

    def serialize_for_signing(self) -> bytes:
        """
        Serialize heartbeat for signing.

        Per specification (Part VII):
        version || pubkey || atomic_time || vdf_proof || btc_anchor || sequence

        Does NOT include signature.
        """
        writer = ByteWriter()

        # Order per specification
        writer.write_u8(self.version)
        writer.write_raw(self.pubkey.serialize())
        writer.write_raw(self.atomic_time.serialize())
        writer.write_raw(self.vdf_proof.serialize())
        writer.write_raw(self.btc_anchor.serialize())
        writer.write_u64(self.sequence)

        return writer.to_bytes()

    def heartbeat_id(self) -> Hash:
        """
        Compute heartbeat ID.

        Per specification: SHA3-256 of serialized heartbeat for signing.
        """
        return sha3_256(self.serialize_for_signing())

    def size(self) -> int:
        """Return size in bytes."""
        return len(self.serialize())

    def is_cross_layer_consistent(self, max_time_diff_ms: int = 1200000) -> bool:
        """
        Check cross-layer time consistency.

        Per specification: Atomic time should be within 20 minutes of BTC block time.

        Args:
            max_time_diff_ms: Maximum allowed difference (default: 20 min = 1,200,000 ms)

        Returns:
            True if times are consistent
        """
        btc_time_ms = self.btc_anchor.timestamp * 1000
        time_diff = abs(self.atomic_time.timestamp_ms - btc_time_ms)
        return time_diff <= max_time_diff_ms

    @classmethod
    def empty(cls) -> "Heartbeat":
        """Create an empty heartbeat (for initialization)."""
        from atc.core.types import empty_signature

        return cls(
            pubkey=PublicKey(),
            atomic_time=AtomicTimeProof.empty(),
            vdf_proof=VDFProof.empty(),
            btc_anchor=BitcoinAnchor.empty(),
            sequence=0,
            version=PROTOCOL_VERSION,
            signature=empty_signature()
        )

    def __repr__(self) -> str:
        return (
            f"Heartbeat(pubkey={self.pubkey.data.hex()[:8]}..., "
            f"seq={self.sequence}, btc_height={self.btc_anchor.height})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Heartbeat):
            return False
        return self.heartbeat_id() == other.heartbeat_id()

    def __hash__(self) -> int:
        return hash(self.heartbeat_id().data)


def heartbeat_id(hb: Heartbeat) -> Hash:
    """
    Compute heartbeat ID.

    Per specification (Part VII): SHA3-256 of serialized heartbeat for signing.
    """
    return hb.heartbeat_id()
