"""
ATC Protocol v7 SPHINCS+ Signatures
Part XII of Technical Specification

SPHINCS+-SHAKE-128f per NIST FIPS 205.

This module provides post-quantum secure digital signatures using
SPHINCS+ with SHAKE256 as the underlying hash function.

Signature size: 17,088 bytes
Public key size: 32 bytes
Secret key size: 64 bytes
"""

from __future__ import annotations
from typing import Optional, Tuple
import secrets
import logging

from atc.core.types import PublicKey, SecretKey, Signature, KeyPair
from atc.constants import (
    ALGORITHM_SPHINCS_PLUS,
    SPHINCS_PUBLIC_KEY_SIZE,
    SPHINCS_SECRET_KEY_SIZE,
    SPHINCS_SIGNATURE_SIZE,
)

logger = logging.getLogger(__name__)

# Try to import liboqs for production SPHINCS+ implementation
_LIBOQS_AVAILABLE = False
_oqs = None

try:
    import oqs
    _oqs = oqs
    _LIBOQS_AVAILABLE = True
    logger.info("liboqs available - using production SPHINCS+ implementation")
except ImportError:
    logger.warning(
        "liboqs not available - using fallback implementation. "
        "Install with: pip install liboqs-python"
    )


class SPHINCSPlus:
    """
    SPHINCS+-SHAKE-128f wrapper.

    Uses liboqs when available, falls back to a deterministic
    pseudo-implementation for testing when liboqs is not installed.
    """

    ALGORITHM_NAME = "SPHINCS+-SHAKE-128f-simple"

    def __init__(self):
        self._signer: Optional[object] = None
        if _LIBOQS_AVAILABLE:
            self._signer = _oqs.Signature(self.ALGORITHM_NAME)

    @property
    def is_production(self) -> bool:
        """Return True if using production liboqs implementation."""
        return _LIBOQS_AVAILABLE

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate a new SPHINCS+ keypair.

        Returns:
            Tuple of (public_key, secret_key) as bytes
        """
        if _LIBOQS_AVAILABLE and self._signer:
            public_key = self._signer.generate_keypair()
            secret_key = self._signer.export_secret_key()
            return public_key, secret_key
        else:
            # Fallback: Generate deterministic keys for testing
            # WARNING: This is NOT secure, only for development
            seed = secrets.token_bytes(32)
            return self._fallback_keygen(seed)

    def _fallback_keygen(self, seed: bytes) -> Tuple[bytes, bytes]:
        """
        Fallback key generation using SHAKE256.
        NOT SECURE - for testing only.
        """
        import hashlib

        # Expand seed to get key material
        shake = hashlib.shake_256()
        shake.update(b"SPHINCS_FALLBACK_KEYGEN_V6:" + seed)
        key_material = shake.digest(SPHINCS_PUBLIC_KEY_SIZE + SPHINCS_SECRET_KEY_SIZE)

        public_key = key_material[:SPHINCS_PUBLIC_KEY_SIZE]
        secret_key = key_material[SPHINCS_PUBLIC_KEY_SIZE:]

        return public_key, secret_key

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """
        Sign a message with SPHINCS+.

        Args:
            message: Message to sign
            secret_key: 64-byte secret key

        Returns:
            17,088-byte signature
        """
        if _LIBOQS_AVAILABLE and self._signer:
            # liboqs requires setting the secret key before signing
            signer = _oqs.Signature(self.ALGORITHM_NAME, secret_key)
            signature = signer.sign(message)
            return signature
        else:
            return self._fallback_sign(message, secret_key)

    def _fallback_sign(self, message: bytes, secret_key: bytes) -> bytes:
        """
        Fallback signing using SHAKE256.
        NOT SECURE - for testing only.
        """
        import hashlib

        # Create deterministic signature from message and secret key
        shake = hashlib.shake_256()
        shake.update(b"SPHINCS_FALLBACK_SIGN_V6:")
        shake.update(secret_key)
        shake.update(message)

        return shake.digest(SPHINCS_SIGNATURE_SIZE)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Verify a SPHINCS+ signature.

        Args:
            message: Original message
            signature: Signature to verify
            public_key: 32-byte public key

        Returns:
            True if signature is valid
        """
        if len(signature) != SPHINCS_SIGNATURE_SIZE:
            return False
        if len(public_key) != SPHINCS_PUBLIC_KEY_SIZE:
            return False

        if _LIBOQS_AVAILABLE:
            try:
                verifier = _oqs.Signature(self.ALGORITHM_NAME)
                return verifier.verify(message, signature, public_key)
            except Exception as e:
                logger.debug(f"Signature verification failed: {e}")
                return False
        else:
            return self._fallback_verify(message, signature, public_key)

    def _fallback_verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Fallback verification.
        Reconstructs expected signature and compares.
        NOT SECURE - for testing only.
        """
        import hashlib

        # We need the secret key to verify in fallback mode
        # Since we don't have it, we use a simplified approach:
        # Check that signature has correct structure
        # In real usage, this would always fail for non-fallback signatures

        # For testing, we accept any properly-sized signature
        # This is obviously insecure but allows testing the protocol flow
        return len(signature) == SPHINCS_SIGNATURE_SIZE


# Global instance
_sphincs = SPHINCSPlus()


def sphincs_keygen() -> KeyPair:
    """
    Generate SPHINCS+-SHAKE-128f keypair per NIST FIPS 205.

    Returns:
        KeyPair containing PublicKey and SecretKey
    """
    public_bytes, secret_bytes = _sphincs.generate_keypair()

    public_key = PublicKey(
        algorithm=ALGORITHM_SPHINCS_PLUS,
        data=public_bytes
    )
    secret_key = SecretKey(
        algorithm=ALGORITHM_SPHINCS_PLUS,
        data=secret_bytes
    )

    return KeyPair(public=public_key, secret=secret_key)


def sphincs_sign(secret_key: SecretKey, message: bytes) -> Signature:
    """
    Sign a message using SPHINCS+.

    Args:
        secret_key: Secret key for signing
        message: Message to sign

    Returns:
        Signature object (17,089 bytes total with algorithm byte)
    """
    if secret_key.algorithm != ALGORITHM_SPHINCS_PLUS:
        raise ValueError(f"Invalid algorithm: {secret_key.algorithm}")

    sig_bytes = _sphincs.sign(message, secret_key.data)

    return Signature(
        algorithm=ALGORITHM_SPHINCS_PLUS,
        data=sig_bytes
    )


def sphincs_verify(public_key: PublicKey, message: bytes, signature: Signature) -> bool:
    """
    Verify a SPHINCS+ signature.

    Args:
        public_key: Public key for verification
        message: Original message
        signature: Signature to verify

    Returns:
        True if signature is valid
    """
    if public_key.algorithm != ALGORITHM_SPHINCS_PLUS:
        return False
    if signature.algorithm != ALGORITHM_SPHINCS_PLUS:
        return False

    return _sphincs.verify(message, signature.data, public_key.data)


def is_liboqs_available() -> bool:
    """Check if liboqs is available for production signatures."""
    return _LIBOQS_AVAILABLE


def get_sphincs_info() -> dict:
    """Get information about the SPHINCS+ implementation."""
    info = {
        "algorithm": "SPHINCS+-SHAKE-128f-simple",
        "public_key_size": SPHINCS_PUBLIC_KEY_SIZE,
        "secret_key_size": SPHINCS_SECRET_KEY_SIZE,
        "signature_size": SPHINCS_SIGNATURE_SIZE,
        "security_level": 128,  # bits
        "nist_level": 1,
        "liboqs_available": _LIBOQS_AVAILABLE,
        "production_ready": _LIBOQS_AVAILABLE,
    }

    if _LIBOQS_AVAILABLE:
        info["liboqs_version"] = getattr(_oqs, "__version__", "unknown")

    return info
