"""
ATC Protocol v7 Serialization Utilities
Part III of Technical Specification

All multi-byte integers are BIG-ENDIAN unless noted.
"""

from __future__ import annotations
from typing import Tuple
import struct

from atc.constants import BIG_ENDIAN, LITTLE_ENDIAN


# ==============================================================================
# Integer Serialization (Big-Endian)
# ==============================================================================

def serialize_u8(value: int) -> bytes:
    """Serialize unsigned 8-bit integer."""
    if not 0 <= value <= 0xFF:
        raise ValueError(f"u8 value out of range: {value}")
    return bytes([value])


def serialize_u16(value: int) -> bytes:
    """Serialize unsigned 16-bit integer (big-endian)."""
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"u16 value out of range: {value}")
    return value.to_bytes(2, BIG_ENDIAN)


def serialize_u32(value: int) -> bytes:
    """Serialize unsigned 32-bit integer (big-endian)."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"u32 value out of range: {value}")
    return value.to_bytes(4, BIG_ENDIAN)


def serialize_u64(value: int) -> bytes:
    """Serialize unsigned 64-bit integer (big-endian)."""
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"u64 value out of range: {value}")
    return value.to_bytes(8, BIG_ENDIAN)


def serialize_i32(value: int) -> bytes:
    """Serialize signed 32-bit integer (big-endian)."""
    if not -0x80000000 <= value <= 0x7FFFFFFF:
        raise ValueError(f"i32 value out of range: {value}")
    return struct.pack(">i", value)


def serialize_i64(value: int) -> bytes:
    """Serialize signed 64-bit integer (big-endian)."""
    if not -0x8000000000000000 <= value <= 0x7FFFFFFFFFFFFFFF:
        raise ValueError(f"i64 value out of range: {value}")
    return struct.pack(">q", value)


# ==============================================================================
# Integer Deserialization (Big-Endian)
# ==============================================================================

def deserialize_u8(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize unsigned 8-bit integer.
    Returns (value, bytes_consumed).
    """
    return data[offset], 1


def deserialize_u16(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize unsigned 16-bit integer (big-endian).
    Returns (value, bytes_consumed).
    """
    return int.from_bytes(data[offset:offset + 2], BIG_ENDIAN), 2


def deserialize_u32(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize unsigned 32-bit integer (big-endian).
    Returns (value, bytes_consumed).
    """
    return int.from_bytes(data[offset:offset + 4], BIG_ENDIAN), 4


def deserialize_u64(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize unsigned 64-bit integer (big-endian).
    Returns (value, bytes_consumed).
    """
    return int.from_bytes(data[offset:offset + 8], BIG_ENDIAN), 8


def deserialize_i32(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize signed 32-bit integer (big-endian).
    Returns (value, bytes_consumed).
    """
    return struct.unpack(">i", data[offset:offset + 4])[0], 4


def deserialize_i64(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize signed 64-bit integer (big-endian).
    Returns (value, bytes_consumed).
    """
    return struct.unpack(">q", data[offset:offset + 8])[0], 8


# ==============================================================================
# Byte Array Serialization
# ==============================================================================

def serialize_bytes(data: bytes) -> bytes:
    """
    Serialize variable-length byte array with length prefix (varint).
    Format: varint(length) || data
    """
    return serialize_varint(len(data)) + data


def serialize_fixed_bytes(data: bytes, size: int) -> bytes:
    """
    Serialize fixed-length byte array.
    Pads with zeros if data is shorter, truncates if longer.
    """
    if len(data) < size:
        return data + bytes(size - len(data))
    return data[:size]


def deserialize_bytes(data: bytes, offset: int = 0) -> Tuple[bytes, int]:
    """
    Deserialize variable-length byte array.
    Returns (bytes_data, total_bytes_consumed).
    """
    length, length_size = deserialize_varint(data, offset)
    start = offset + length_size
    end = start + length
    return data[start:end], length_size + length


def deserialize_fixed_bytes(data: bytes, size: int, offset: int = 0) -> Tuple[bytes, int]:
    """
    Deserialize fixed-length byte array.
    Returns (bytes_data, bytes_consumed).
    """
    return data[offset:offset + size], size


# ==============================================================================
# Varint Encoding (Bitcoin-style)
# ==============================================================================

def serialize_varint(value: int) -> bytes:
    """
    Serialize integer as variable-length integer (Bitcoin-style).

    - 0x00-0xFC: 1 byte
    - 0xFD-0xFFFF: 0xFD + 2 bytes (little-endian)
    - 0x10000-0xFFFFFFFF: 0xFE + 4 bytes (little-endian)
    - 0x100000000+: 0xFF + 8 bytes (little-endian)
    """
    if value < 0:
        raise ValueError(f"Varint cannot be negative: {value}")

    if value <= 0xFC:
        return bytes([value])
    elif value <= 0xFFFF:
        return bytes([0xFD]) + value.to_bytes(2, LITTLE_ENDIAN)
    elif value <= 0xFFFFFFFF:
        return bytes([0xFE]) + value.to_bytes(4, LITTLE_ENDIAN)
    else:
        return bytes([0xFF]) + value.to_bytes(8, LITTLE_ENDIAN)


def deserialize_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Deserialize variable-length integer.
    Returns (value, bytes_consumed).
    """
    first_byte = data[offset]

    if first_byte <= 0xFC:
        return first_byte, 1
    elif first_byte == 0xFD:
        return int.from_bytes(data[offset + 1:offset + 3], LITTLE_ENDIAN), 3
    elif first_byte == 0xFE:
        return int.from_bytes(data[offset + 1:offset + 5], LITTLE_ENDIAN), 5
    else:  # 0xFF
        return int.from_bytes(data[offset + 1:offset + 9], LITTLE_ENDIAN), 9


def varint_size(value: int) -> int:
    """Return the number of bytes needed to encode value as varint."""
    if value <= 0xFC:
        return 1
    elif value <= 0xFFFF:
        return 3
    elif value <= 0xFFFFFFFF:
        return 5
    else:
        return 9


# ==============================================================================
# Helper Functions
# ==============================================================================

def concat(*parts: bytes) -> bytes:
    """Concatenate multiple byte arrays."""
    return b"".join(parts)


def pad_to_size(data: bytes, size: int, pad_byte: int = 0) -> bytes:
    """Pad byte array to specified size."""
    if len(data) >= size:
        return data[:size]
    return data + bytes([pad_byte] * (size - len(data)))


def split_at(data: bytes, index: int) -> Tuple[bytes, bytes]:
    """Split byte array at index."""
    return data[:index], data[index:]


class ByteReader:
    """
    Helper class for sequential deserialization.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def read_u8(self) -> int:
        value, size = deserialize_u8(self.data, self.offset)
        self.offset += size
        return value

    def read_u16(self) -> int:
        value, size = deserialize_u16(self.data, self.offset)
        self.offset += size
        return value

    def read_u32(self) -> int:
        value, size = deserialize_u32(self.data, self.offset)
        self.offset += size
        return value

    def read_u64(self) -> int:
        value, size = deserialize_u64(self.data, self.offset)
        self.offset += size
        return value

    def read_i32(self) -> int:
        value, size = deserialize_i32(self.data, self.offset)
        self.offset += size
        return value

    def read_i64(self) -> int:
        value, size = deserialize_i64(self.data, self.offset)
        self.offset += size
        return value

    def read_varint(self) -> int:
        value, size = deserialize_varint(self.data, self.offset)
        self.offset += size
        return value

    def read_bytes(self) -> bytes:
        """Read variable-length byte array (varint-prefixed)."""
        value, size = deserialize_bytes(self.data, self.offset)
        self.offset += size
        return value

    def read_fixed_bytes(self, size: int) -> bytes:
        """Read fixed-length byte array."""
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def remaining(self) -> int:
        """Return number of bytes remaining."""
        return len(self.data) - self.offset

    def is_empty(self) -> bool:
        """Check if all bytes have been read."""
        return self.offset >= len(self.data)


class ByteWriter:
    """
    Helper class for sequential serialization.
    """

    def __init__(self):
        self.buffer = bytearray()

    def write_u8(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_u8(value))
        return self

    def write_u16(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_u16(value))
        return self

    def write_u32(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_u32(value))
        return self

    def write_u64(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_u64(value))
        return self

    def write_i32(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_i32(value))
        return self

    def write_i64(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_i64(value))
        return self

    def write_varint(self, value: int) -> "ByteWriter":
        self.buffer.extend(serialize_varint(value))
        return self

    def write_bytes(self, data: bytes) -> "ByteWriter":
        """Write variable-length byte array (varint-prefixed)."""
        self.buffer.extend(serialize_bytes(data))
        return self

    def write_fixed_bytes(self, data: bytes, size: int) -> "ByteWriter":
        """Write fixed-length byte array."""
        self.buffer.extend(serialize_fixed_bytes(data, size))
        return self

    def write_raw(self, data: bytes) -> "ByteWriter":
        """Write raw bytes without length prefix."""
        self.buffer.extend(data)
        return self

    def to_bytes(self) -> bytes:
        """Return the serialized bytes."""
        return bytes(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)
