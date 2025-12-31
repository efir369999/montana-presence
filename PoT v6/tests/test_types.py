"""
PoT Protocol v6 Type Tests
"""

import pytest
from pot.core.types import Hash, PublicKey, SecretKey, Signature, KeyPair


class TestHash:
    """Tests for Hash type."""

    def test_hash_creation(self):
        """Test hash creation from bytes."""
        data = bytes(range(32))
        h = Hash(data)
        assert h.data == data
        assert len(h.data) == 32

    def test_hash_zero(self):
        """Test zero hash creation."""
        h = Hash.zero()
        assert h.data == bytes(32)
        assert h == Hash.zero()

    def test_hash_hex(self):
        """Test hash hex conversion."""
        data = bytes([0xAB, 0xCD] + [0] * 30)
        h = Hash(data)
        assert h.hex().startswith("abcd")

    def test_hash_from_hex(self):
        """Test hash from hex string."""
        hex_str = "ab" * 32
        h = Hash.from_hex(hex_str)
        assert h.data == bytes.fromhex(hex_str)

    def test_hash_equality(self):
        """Test hash equality."""
        data = bytes(range(32))
        h1 = Hash(data)
        h2 = Hash(data)
        assert h1 == h2

    def test_hash_inequality(self):
        """Test hash inequality."""
        h1 = Hash(bytes(32))
        h2 = Hash(bytes([1] + [0] * 31))
        assert h1 != h2

    def test_hash_serialization(self):
        """Test hash serialization."""
        data = bytes(range(32))
        h = Hash(data)
        serialized = h.serialize()
        assert serialized == data


class TestPublicKey:
    """Tests for PublicKey type."""

    def test_pubkey_creation(self):
        """Test public key creation."""
        data = bytes([0x21] + list(range(32)))
        pk = PublicKey(data)
        assert pk.data == data
        assert len(pk.data) == 33

    def test_pubkey_serialization(self):
        """Test public key serialization."""
        data = bytes([0x21] + list(range(32)))
        pk = PublicKey(data)
        serialized = pk.serialize()
        assert serialized == data


class TestSecretKey:
    """Tests for SecretKey type."""

    def test_secret_key_creation(self):
        """Test secret key creation."""
        data = bytes(range(64))
        sk = SecretKey(data)
        assert sk.data == data
        assert len(sk.data) == 64


class TestSignature:
    """Tests for Signature type."""

    def test_signature_creation(self):
        """Test signature creation."""
        data = bytes(range(100))
        sig = Signature(data)
        assert sig.data == data


class TestKeyPair:
    """Tests for KeyPair type."""

    def test_keypair_creation(self, mock_keypair):
        """Test keypair creation."""
        assert mock_keypair.public is not None
        assert mock_keypair.secret is not None
        assert len(mock_keypair.public.data) == 33
        assert len(mock_keypair.secret.data) == 64
