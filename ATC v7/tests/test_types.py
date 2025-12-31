"""
ATC Protocol v7 Type Tests
"""

import pytest
from atc.core.types import Hash, PublicKey, SecretKey, Signature, KeyPair
from atc.constants import (
    SPHINCS_PUBLIC_KEY_SIZE,
    SPHINCS_SECRET_KEY_SIZE,
    SPHINCS_SIGNATURE_SIZE,
    ALGORITHM_SPHINCS_PLUS,
)


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
        data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        pk = PublicKey(data=data)
        assert pk.data == data
        assert len(pk.data) == SPHINCS_PUBLIC_KEY_SIZE
        assert pk.algorithm == ALGORITHM_SPHINCS_PLUS

    def test_pubkey_with_algorithm(self):
        """Test public key with explicit algorithm."""
        data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        pk = PublicKey(algorithm=0x01, data=data)
        assert pk.algorithm == 0x01
        assert pk.data == data

    def test_pubkey_serialization(self):
        """Test public key serialization."""
        data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        pk = PublicKey(data=data)
        serialized = pk.serialize()
        # Serialized = algorithm (1 byte) + data
        assert len(serialized) == 1 + SPHINCS_PUBLIC_KEY_SIZE
        assert serialized[0] == ALGORITHM_SPHINCS_PLUS
        assert serialized[1:] == data

    def test_pubkey_deserialization(self):
        """Test public key deserialization."""
        data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        pk = PublicKey(data=data)
        serialized = pk.serialize()
        pk2, consumed = PublicKey.deserialize(serialized)
        assert pk == pk2
        assert consumed == 1 + SPHINCS_PUBLIC_KEY_SIZE

    def test_pubkey_equality(self):
        """Test public key equality."""
        data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        pk1 = PublicKey(data=data)
        pk2 = PublicKey(data=data)
        assert pk1 == pk2

    def test_pubkey_to_address(self):
        """Test address derivation from public key."""
        data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        pk = PublicKey(data=data)
        address = pk.to_address()
        assert len(address.data) == 32


class TestSecretKey:
    """Tests for SecretKey type."""

    def test_secret_key_creation(self):
        """Test secret key creation."""
        data = bytes(range(SPHINCS_SECRET_KEY_SIZE))
        sk = SecretKey(data=data)
        assert sk.data == data
        assert len(sk.data) == SPHINCS_SECRET_KEY_SIZE
        assert sk.algorithm == ALGORITHM_SPHINCS_PLUS

    def test_secret_key_with_algorithm(self):
        """Test secret key with explicit algorithm."""
        data = bytes(range(SPHINCS_SECRET_KEY_SIZE))
        sk = SecretKey(algorithm=0x01, data=data)
        assert sk.algorithm == 0x01
        assert sk.data == data

    def test_secret_key_repr_redacted(self):
        """Test secret key representation is redacted."""
        data = bytes(range(SPHINCS_SECRET_KEY_SIZE))
        sk = SecretKey(data=data)
        repr_str = repr(sk)
        assert "<redacted>" in repr_str
        # Should NOT expose the actual data
        assert data.hex() not in repr_str


class TestSignature:
    """Tests for Signature type."""

    def test_signature_creation(self):
        """Test signature creation."""
        data = bytes(range(256)) * (SPHINCS_SIGNATURE_SIZE // 256 + 1)
        data = data[:SPHINCS_SIGNATURE_SIZE]
        sig = Signature(data=data)
        assert sig.data == data
        assert len(sig.data) == SPHINCS_SIGNATURE_SIZE

    def test_signature_empty(self):
        """Test empty signature creation."""
        sig = Signature.empty()
        assert len(sig.data) == SPHINCS_SIGNATURE_SIZE
        assert sig.data == bytes(SPHINCS_SIGNATURE_SIZE)

    def test_signature_serialization(self):
        """Test signature serialization."""
        data = bytes([0xAB] * SPHINCS_SIGNATURE_SIZE)
        sig = Signature(data=data)
        serialized = sig.serialize()
        # Serialized = algorithm (1 byte) + data
        assert len(serialized) == 1 + SPHINCS_SIGNATURE_SIZE
        assert serialized[0] == ALGORITHM_SPHINCS_PLUS
        assert serialized[1:] == data


class TestKeyPair:
    """Tests for KeyPair type."""

    def test_keypair_creation(self):
        """Test keypair creation."""
        pk_data = bytes(range(SPHINCS_PUBLIC_KEY_SIZE))
        sk_data = bytes(range(SPHINCS_SECRET_KEY_SIZE))
        pk = PublicKey(data=pk_data)
        sk = SecretKey(data=sk_data)
        kp = KeyPair(public=pk, secret=sk)

        assert kp.public == pk
        assert kp.secret == sk
        assert len(kp.public.data) == SPHINCS_PUBLIC_KEY_SIZE
        assert len(kp.secret.data) == SPHINCS_SECRET_KEY_SIZE

    def test_keypair_algorithm_consistency(self):
        """Test keypair requires consistent algorithms."""
        pk = PublicKey(algorithm=0x01, data=bytes(SPHINCS_PUBLIC_KEY_SIZE))
        sk = SecretKey(algorithm=0x02, data=bytes(SPHINCS_SECRET_KEY_SIZE))

        with pytest.raises(ValueError):
            KeyPair(public=pk, secret=sk)

    def test_keypair_to_address(self):
        """Test keypair address derivation."""
        pk = PublicKey(data=bytes(range(SPHINCS_PUBLIC_KEY_SIZE)))
        sk = SecretKey(data=bytes(range(SPHINCS_SECRET_KEY_SIZE)))
        kp = KeyPair(public=pk, secret=sk)

        address = kp.to_address()
        assert address == pk.to_address()
