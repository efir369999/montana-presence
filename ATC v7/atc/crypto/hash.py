"""
ATC Protocol v7 Hash Functions
Part XII of Technical Specification

SHA3-256 and SHAKE256 per NIST FIPS 202.
"""

from __future__ import annotations
import hashlib
from typing import Union

from atc.constants import SHA3_256_OUTPUT_SIZE, SHAKE256_OUTPUT_SIZE
from atc.core.types import Hash


def sha3_256(data: Union[bytes, bytearray, memoryview]) -> Hash:
    """
    SHA3-256 hash function per NIST FIPS 202.

    Args:
        data: Input data to hash

    Returns:
        Hash: 32-byte hash output wrapped in Hash type
    """
    hasher = hashlib.sha3_256()
    hasher.update(data)
    return Hash(hasher.digest())


def sha3_256_raw(data: Union[bytes, bytearray, memoryview]) -> bytes:
    """
    SHA3-256 hash function returning raw bytes.

    Args:
        data: Input data to hash

    Returns:
        bytes: 32-byte hash output
    """
    return hashlib.sha3_256(data).digest()


def shake256(data: Union[bytes, bytearray, memoryview], output_length: int = SHAKE256_OUTPUT_SIZE) -> bytes:
    """
    SHAKE256 extendable output function per NIST FIPS 202.

    Args:
        data: Input data
        output_length: Desired output length in bytes (default: 32)

    Returns:
        bytes: Output of specified length
    """
    hasher = hashlib.shake_256()
    hasher.update(data)
    return hasher.digest(output_length)


def shake256_hash(data: Union[bytes, bytearray, memoryview]) -> Hash:
    """
    SHAKE256 with 32-byte output wrapped in Hash type.

    Args:
        data: Input data

    Returns:
        Hash: 32-byte hash output
    """
    return Hash(shake256(data, SHA3_256_OUTPUT_SIZE))


def tagged_hash(tag: bytes, data: bytes) -> Hash:
    """
    Domain-separated hash using tagged hashing.

    Computes: SHA3-256(SHA3-256(tag) || SHA3-256(tag) || data)

    This provides domain separation to prevent cross-protocol attacks.

    Args:
        tag: Domain separation tag
        data: Data to hash

    Returns:
        Hash: Tagged hash output
    """
    tag_hash = sha3_256_raw(tag)
    return sha3_256(tag_hash + tag_hash + data)


def double_sha3_256(data: bytes) -> Hash:
    """
    Double SHA3-256 hash (for additional security).

    Args:
        data: Input data

    Returns:
        Hash: SHA3-256(SHA3-256(data))
    """
    return sha3_256(sha3_256_raw(data))


class HashBuilder:
    """
    Builder pattern for constructing hashes from multiple inputs.

    Example:
        hash = HashBuilder().update(b"hello").update(b"world").finalize()
    """

    def __init__(self):
        self._hasher = hashlib.sha3_256()

    def update(self, data: bytes) -> "HashBuilder":
        """Add data to the hash computation."""
        self._hasher.update(data)
        return self

    def update_u8(self, value: int) -> "HashBuilder":
        """Add a u8 to the hash computation."""
        self._hasher.update(bytes([value]))
        return self

    def update_u16(self, value: int) -> "HashBuilder":
        """Add a u16 (big-endian) to the hash computation."""
        self._hasher.update(value.to_bytes(2, "big"))
        return self

    def update_u32(self, value: int) -> "HashBuilder":
        """Add a u32 (big-endian) to the hash computation."""
        self._hasher.update(value.to_bytes(4, "big"))
        return self

    def update_u64(self, value: int) -> "HashBuilder":
        """Add a u64 (big-endian) to the hash computation."""
        self._hasher.update(value.to_bytes(8, "big"))
        return self

    def update_hash(self, h: Hash) -> "HashBuilder":
        """Add another hash to the computation."""
        self._hasher.update(h.data)
        return self

    def finalize(self) -> Hash:
        """Complete the hash computation and return the result."""
        return Hash(self._hasher.digest())

    def finalize_raw(self) -> bytes:
        """Complete the hash computation and return raw bytes."""
        return self._hasher.digest()

    def copy(self) -> "HashBuilder":
        """Create a copy of the current state."""
        builder = HashBuilder()
        builder._hasher = self._hasher.copy()
        return builder


class SHAKE256Builder:
    """
    Builder pattern for SHAKE256 XOF.
    """

    def __init__(self):
        self._hasher = hashlib.shake_256()

    def update(self, data: bytes) -> "SHAKE256Builder":
        """Add data to the computation."""
        self._hasher.update(data)
        return self

    def finalize(self, output_length: int = SHAKE256_OUTPUT_SIZE) -> bytes:
        """Complete the computation and return output of specified length."""
        return self._hasher.digest(output_length)

    def finalize_hash(self) -> Hash:
        """Complete the computation and return 32-byte Hash."""
        return Hash(self._hasher.digest(SHA3_256_OUTPUT_SIZE))

    def copy(self) -> "SHAKE256Builder":
        """Create a copy of the current state."""
        builder = SHAKE256Builder()
        builder._hasher = self._hasher.copy()
        return builder
