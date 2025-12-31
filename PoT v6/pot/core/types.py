"""
PoT Protocol v6 Cryptographic Types
Part III Section 3.2 of Technical Specification

All multi-byte integers are BIG-ENDIAN unless noted.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import hashlib

from pot.constants import (
    HASH_SIZE,
    SPHINCS_PUBLIC_KEY_SIZE,
    SPHINCS_SECRET_KEY_SIZE,
    SPHINCS_SIGNATURE_SIZE,
    ALGORITHM_SPHINCS_PLUS,
    BIG_ENDIAN,
)


@dataclass(frozen=True, slots=True)
class Hash:
    """
    SHA3-256 hash output.

    SIZE: 32 bytes
    SERIALIZATION: raw bytes
    """
    data: bytes = field(default_factory=lambda: bytes(HASH_SIZE))

    def __post_init__(self):
        if len(self.data) != HASH_SIZE:
            raise ValueError(f"Hash must be {HASH_SIZE} bytes, got {len(self.data)}")

    def __bytes__(self) -> bytes:
        return self.data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Hash):
            return self.data == other.data
        if isinstance(other, bytes):
            return self.data == other
        return False

    def __hash__(self) -> int:
        return hash(self.data)

    def __repr__(self) -> str:
        return f"Hash({self.data.hex()[:16]}...)"

    def hex(self) -> str:
        return self.data.hex()

    @classmethod
    def from_hex(cls, hex_string: str) -> Hash:
        return cls(bytes.fromhex(hex_string))

    @classmethod
    def zero(cls) -> Hash:
        return cls(bytes(HASH_SIZE))

    @classmethod
    def from_bytes(cls, data: bytes) -> Hash:
        return cls(data)

    def serialize(self) -> bytes:
        """Serialize to raw bytes."""
        return self.data

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple[Hash, int]:
        """Deserialize from bytes, return (Hash, bytes_consumed)."""
        return cls(data[offset:offset + HASH_SIZE]), HASH_SIZE


@dataclass(frozen=True, slots=True)
class PublicKey:
    """
    Public key with algorithm identifier.

    SIZE: 33 bytes (algorithm: 1 byte, data: 32 bytes)
    SERIALIZATION: algorithm || data
    """
    algorithm: int = ALGORITHM_SPHINCS_PLUS
    data: bytes = field(default_factory=lambda: bytes(SPHINCS_PUBLIC_KEY_SIZE))

    def __post_init__(self):
        if len(self.data) != SPHINCS_PUBLIC_KEY_SIZE:
            raise ValueError(
                f"PublicKey data must be {SPHINCS_PUBLIC_KEY_SIZE} bytes, got {len(self.data)}"
            )

    def __bytes__(self) -> bytes:
        return bytes([self.algorithm]) + self.data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PublicKey):
            return self.algorithm == other.algorithm and self.data == other.data
        return False

    def __hash__(self) -> int:
        return hash((self.algorithm, self.data))

    def __repr__(self) -> str:
        return f"PublicKey(alg={self.algorithm}, data={self.data.hex()[:16]}...)"

    def hex(self) -> str:
        return bytes(self).hex()

    @classmethod
    def from_hex(cls, hex_string: str) -> PublicKey:
        data = bytes.fromhex(hex_string)
        return cls(algorithm=data[0], data=data[1:])

    def serialize(self) -> bytes:
        """Serialize to bytes: algorithm || data."""
        return bytes([self.algorithm]) + self.data

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple[PublicKey, int]:
        """Deserialize from bytes, return (PublicKey, bytes_consumed)."""
        algorithm = data[offset]
        key_data = data[offset + 1:offset + 1 + SPHINCS_PUBLIC_KEY_SIZE]
        return cls(algorithm=algorithm, data=key_data), 1 + SPHINCS_PUBLIC_KEY_SIZE

    def to_address(self) -> Hash:
        """Derive address (hash of public key)."""
        return Hash(hashlib.sha3_256(bytes(self)).digest())


@dataclass(frozen=True, slots=True)
class SecretKey:
    """
    Secret key with algorithm identifier.

    SIZE: 65 bytes (algorithm: 1 byte, data: 64 bytes)
    NOTE: Never transmitted over network.
    """
    algorithm: int = ALGORITHM_SPHINCS_PLUS
    data: bytes = field(default_factory=lambda: bytes(SPHINCS_SECRET_KEY_SIZE))

    def __post_init__(self):
        if len(self.data) != SPHINCS_SECRET_KEY_SIZE:
            raise ValueError(
                f"SecretKey data must be {SPHINCS_SECRET_KEY_SIZE} bytes, got {len(self.data)}"
            )

    def __bytes__(self) -> bytes:
        return bytes([self.algorithm]) + self.data

    def __repr__(self) -> str:
        # Never expose secret key data
        return f"SecretKey(alg={self.algorithm}, data=<redacted>)"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretKey):
            return self.algorithm == other.algorithm and self.data == other.data
        return False

    def __hash__(self) -> int:
        return hash((self.algorithm, self.data))

    def serialize(self) -> bytes:
        """Serialize to bytes: algorithm || data. Use with caution!"""
        return bytes([self.algorithm]) + self.data

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple[SecretKey, int]:
        """Deserialize from bytes, return (SecretKey, bytes_consumed)."""
        algorithm = data[offset]
        key_data = data[offset + 1:offset + 1 + SPHINCS_SECRET_KEY_SIZE]
        return cls(algorithm=algorithm, data=key_data), 1 + SPHINCS_SECRET_KEY_SIZE


@dataclass(frozen=True, slots=True)
class Signature:
    """
    Cryptographic signature with algorithm identifier.

    SIZE: 17089 bytes (algorithm: 1 byte, data: 17088 bytes for SPHINCS+-SHAKE-128f)
    SERIALIZATION: algorithm || data
    """
    algorithm: int = ALGORITHM_SPHINCS_PLUS
    data: bytes = field(default_factory=lambda: bytes(SPHINCS_SIGNATURE_SIZE))

    def __post_init__(self):
        if len(self.data) != SPHINCS_SIGNATURE_SIZE:
            raise ValueError(
                f"Signature data must be {SPHINCS_SIGNATURE_SIZE} bytes, got {len(self.data)}"
            )

    def __bytes__(self) -> bytes:
        return bytes([self.algorithm]) + self.data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Signature):
            return self.algorithm == other.algorithm and self.data == other.data
        return False

    def __hash__(self) -> int:
        return hash((self.algorithm, self.data))

    def __repr__(self) -> str:
        return f"Signature(alg={self.algorithm}, data={self.data.hex()[:16]}...)"

    def hex(self) -> str:
        return bytes(self).hex()

    @classmethod
    def empty(cls) -> Signature:
        """Create an empty signature (for signing preparation)."""
        return cls(algorithm=ALGORITHM_SPHINCS_PLUS, data=bytes(SPHINCS_SIGNATURE_SIZE))

    def serialize(self) -> bytes:
        """Serialize to bytes: algorithm || data."""
        return bytes([self.algorithm]) + self.data

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> tuple[Signature, int]:
        """Deserialize from bytes, return (Signature, bytes_consumed)."""
        algorithm = data[offset]
        sig_data = data[offset + 1:offset + 1 + SPHINCS_SIGNATURE_SIZE]
        return cls(algorithm=algorithm, data=sig_data), 1 + SPHINCS_SIGNATURE_SIZE


@dataclass(frozen=True, slots=True)
class KeyPair:
    """
    Public/Secret key pair for signing operations.
    """
    public: PublicKey
    secret: SecretKey

    def __post_init__(self):
        if self.public.algorithm != self.secret.algorithm:
            raise ValueError("PublicKey and SecretKey must use same algorithm")

    def __repr__(self) -> str:
        return f"KeyPair(public={self.public})"

    @property
    def algorithm(self) -> int:
        return self.public.algorithm

    def to_address(self) -> Hash:
        """Derive address from public key."""
        return self.public.to_address()


def empty_hash() -> Hash:
    """Create a zeroed hash (for initialization)."""
    return Hash.zero()


def empty_signature() -> Signature:
    """Create an empty signature (for signing preparation)."""
    return Signature.empty()
