"""
ATC Protocol v7 Transaction Structure
Part III Section 3.7 and Part VIII of Technical Specification

Transaction with personal PoW for rate limiting.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from atc.constants import (
    PROTOCOL_VERSION,
    MEMO_MAX_SIZE,
)
from atc.core.types import Hash, PublicKey, Signature
from atc.core.serialization import ByteReader, ByteWriter, pad_to_size
from atc.crypto.hash import sha3_256


@dataclass(slots=True)
class Transaction:
    """
    Transaction with personal proof of work.

    Per specification (Part VIII):
    - Version
    - Sender/Receiver public keys
    - Amount
    - Time references (Layer 0 + Layer 2)
    - Anti-spam PoW
    - Metadata (nonce, epoch, memo)
    - Signature
    """
    # Version
    version: int                        # u8

    # Parties
    sender: PublicKey                   # 33 bytes
    receiver: PublicKey                 # 33 bytes
    amount: int                         # u64 - Atomic units (8 decimals)

    # Layer 0: Physical Time
    atomic_timestamp_ms: int            # u64 - Atomic time at creation
    atomic_source_bitmap: int           # u8 - Regions that responded

    # Layer 2: Bitcoin Reference
    btc_height: int                     # u64 - Bitcoin block height
    btc_hash: bytes                     # bytes[32] - Bitcoin block hash

    # Anti-spam PoW
    pow_difficulty: int                 # u8 - Difficulty in bits
    pow_nonce: bytes                    # bytes[8] - Solution nonce
    pow_hash: Hash                      # Argon2id intermediate hash

    # Metadata
    nonce: int                          # u64 - Replay protection (per-sender)
    epoch: int                          # u32 - 10-minute epoch number
    memo: bytes                         # bytes[256] - Optional memo (zero-padded)
    memo_length: int                    # u8 - Actual memo length

    # Signature
    signature: Signature                # 17089 bytes

    def __post_init__(self):
        if len(self.btc_hash) != 32:
            raise ValueError(f"btc_hash must be 32 bytes, got {len(self.btc_hash)}")
        if len(self.pow_nonce) != 8:
            raise ValueError(f"pow_nonce must be 8 bytes, got {len(self.pow_nonce)}")
        if len(self.memo) != MEMO_MAX_SIZE:
            raise ValueError(f"memo must be {MEMO_MAX_SIZE} bytes, got {len(self.memo)}")
        if self.memo_length > MEMO_MAX_SIZE:
            raise ValueError(f"memo_length exceeds max: {self.memo_length}")

    def serialize(self) -> bytes:
        """Serialize complete transaction."""
        writer = ByteWriter()

        # Version
        writer.write_u8(self.version)

        # Parties
        writer.write_raw(self.sender.serialize())
        writer.write_raw(self.receiver.serialize())
        writer.write_u64(self.amount)

        # Layer 0
        writer.write_u64(self.atomic_timestamp_ms)
        writer.write_u8(self.atomic_source_bitmap)

        # Layer 2
        writer.write_u64(self.btc_height)
        writer.write_raw(self.btc_hash)

        # Anti-spam PoW
        writer.write_u8(self.pow_difficulty)
        writer.write_raw(self.pow_nonce)
        writer.write_raw(self.pow_hash.serialize())

        # Metadata
        writer.write_u64(self.nonce)
        writer.write_u32(self.epoch)
        writer.write_raw(self.memo)  # Full 256 bytes
        writer.write_u8(self.memo_length)

        # Signature
        writer.write_raw(self.signature.serialize())

        return writer.to_bytes()

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple["Transaction", int]:
        """Deserialize from bytes."""
        reader = ByteReader(data[offset:])

        # Version
        version = reader.read_u8()

        # Parties
        sender_data = reader.read_fixed_bytes(33)
        sender, _ = PublicKey.deserialize(sender_data)

        receiver_data = reader.read_fixed_bytes(33)
        receiver, _ = PublicKey.deserialize(receiver_data)

        amount = reader.read_u64()

        # Layer 0
        atomic_timestamp_ms = reader.read_u64()
        atomic_source_bitmap = reader.read_u8()

        # Layer 2
        btc_height = reader.read_u64()
        btc_hash = reader.read_fixed_bytes(32)

        # Anti-spam PoW
        pow_difficulty = reader.read_u8()
        pow_nonce = reader.read_fixed_bytes(8)
        pow_hash_data = reader.read_fixed_bytes(32)
        pow_hash = Hash(pow_hash_data)

        # Metadata
        nonce = reader.read_u64()
        epoch = reader.read_u32()
        memo = reader.read_fixed_bytes(MEMO_MAX_SIZE)
        memo_length = reader.read_u8()

        # Signature
        remaining = data[offset + reader.offset:]
        signature, sig_consumed = Signature.deserialize(remaining)

        return cls(
            version=version,
            sender=sender,
            receiver=receiver,
            amount=amount,
            atomic_timestamp_ms=atomic_timestamp_ms,
            atomic_source_bitmap=atomic_source_bitmap,
            btc_height=btc_height,
            btc_hash=btc_hash,
            pow_difficulty=pow_difficulty,
            pow_nonce=pow_nonce,
            pow_hash=pow_hash,
            nonce=nonce,
            epoch=epoch,
            memo=memo,
            memo_length=memo_length,
            signature=signature
        ), reader.offset + sig_consumed

    def serialize_for_signing(self) -> bytes:
        """
        Serialize transaction for signing.

        Everything except signature, in deterministic order.
        """
        writer = ByteWriter()

        writer.write_u8(self.version)
        writer.write_raw(self.sender.serialize())
        writer.write_raw(self.receiver.serialize())
        writer.write_u64(self.amount)
        writer.write_u64(self.atomic_timestamp_ms)
        writer.write_u8(self.atomic_source_bitmap)
        writer.write_u64(self.btc_height)
        writer.write_raw(self.btc_hash)
        writer.write_u8(self.pow_difficulty)
        writer.write_raw(self.pow_nonce)
        writer.write_raw(self.pow_hash.serialize())
        writer.write_u64(self.nonce)
        writer.write_u32(self.epoch)
        writer.write_raw(self.memo)
        writer.write_u8(self.memo_length)

        return writer.to_bytes()

    def serialize_for_pow(self) -> bytes:
        """
        Serialize transaction for PoW computation.

        Excludes PoW fields and signature.
        """
        writer = ByteWriter()

        writer.write_u8(self.version)
        writer.write_raw(self.sender.serialize())
        writer.write_raw(self.receiver.serialize())
        writer.write_u64(self.amount)
        writer.write_u64(self.atomic_timestamp_ms)
        writer.write_u8(self.atomic_source_bitmap)
        writer.write_u64(self.btc_height)
        writer.write_raw(self.btc_hash)
        writer.write_u64(self.nonce)
        writer.write_u32(self.epoch)
        writer.write_raw(self.memo)
        writer.write_u8(self.memo_length)

        return writer.to_bytes()

    def transaction_id(self) -> Hash:
        """
        Compute transaction ID.

        Per specification: SHA3-256 of serialized transaction for signing.
        """
        return sha3_256(self.serialize_for_signing())

    def get_memo(self) -> bytes:
        """Get actual memo content (without padding)."""
        return self.memo[:self.memo_length]

    def get_memo_str(self) -> str:
        """Get memo as UTF-8 string (if valid)."""
        try:
            return self.get_memo().decode("utf-8")
        except UnicodeDecodeError:
            return self.get_memo().hex()

    def size(self) -> int:
        """Return size in bytes."""
        return len(self.serialize())

    @classmethod
    def create(
        cls,
        sender: PublicKey,
        receiver: PublicKey,
        amount: int,
        atomic_timestamp_ms: int,
        atomic_source_bitmap: int,
        btc_height: int,
        btc_hash: bytes,
        nonce: int,
        memo: bytes = b""
    ) -> "Transaction":
        """
        Create a new unsigned transaction (without PoW or signature).

        Call compute_pow() and sign() after creation.
        """
        from atc.constants import TX_EPOCH_DURATION_SEC
        from atc.core.types import empty_signature

        epoch = atomic_timestamp_ms // (TX_EPOCH_DURATION_SEC * 1000)

        return cls(
            version=PROTOCOL_VERSION,
            sender=sender,
            receiver=receiver,
            amount=amount,
            atomic_timestamp_ms=atomic_timestamp_ms,
            atomic_source_bitmap=atomic_source_bitmap,
            btc_height=btc_height,
            btc_hash=btc_hash,
            pow_difficulty=0,
            pow_nonce=bytes(8),
            pow_hash=Hash.zero(),
            nonce=nonce,
            epoch=epoch,
            memo=pad_to_size(memo, MEMO_MAX_SIZE),
            memo_length=min(len(memo), MEMO_MAX_SIZE),
            signature=empty_signature()
        )

    def __repr__(self) -> str:
        return (
            f"Transaction(sender={self.sender.data.hex()[:8]}..., "
            f"receiver={self.receiver.data.hex()[:8]}..., "
            f"amount={self.amount}, nonce={self.nonce})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Transaction):
            return False
        return self.transaction_id() == other.transaction_id()

    def __hash__(self) -> int:
        return hash(self.transaction_id().data)


def transaction_id(tx: Transaction) -> Hash:
    """
    Compute transaction ID.

    Per specification: SHA3-256 of serialized transaction for signing.
    """
    return tx.transaction_id()
