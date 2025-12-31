"""
Proof of Time - Cryptographic Provider Abstraction Layer

This module provides a crypto-agile architecture allowing seamless switching
between cryptographic backends (legacy vs post-quantum).

The abstraction enables:
1. Easy migration to post-quantum algorithms
2. Backward compatibility during transition period
3. Runtime switching for testing and gradual rollout
4. Clean separation between crypto interface and implementation

Usage:
    from crypto_provider import get_crypto_provider, CryptoBackend

    # Get current provider (based on config)
    provider = get_crypto_provider()

    # Or explicitly request a backend
    pq_provider = get_crypto_provider(CryptoBackend.POST_QUANTUM)

    # Use unified API
    hash_val = provider.hash(b"data")
    signature = provider.sign(private_key, message)
    valid = provider.verify(public_key, message, signature)

Time is the ultimate proof.
"""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Tuple, List, Optional, Union, Dict, Any
import logging

logger = logging.getLogger("proof_of_time.crypto_provider")


# ============================================================================
# CRYPTO BACKEND ENUM
# ============================================================================

class CryptoBackend(Enum):
    """Available cryptographic backends."""
    LEGACY = auto()          # Ed25519 + SHA-256 + Wesolowski VDF
    POST_QUANTUM = auto()    # SPHINCS+ + SHA3-256 + SHAKE256/STARK VDF
    HYBRID = auto()          # Both signatures (for transition period)


# ============================================================================
# VDF PROOF DATA STRUCTURES
# ============================================================================

@dataclass
class VDFProofBase:
    """Base VDF proof container - backend agnostic."""
    input_hash: bytes          # 32 bytes - input to VDF
    output_hash: bytes         # 32 bytes - VDF output
    difficulty: int            # Number of iterations/steps
    proof_data: bytes          # Backend-specific proof (Wesolowski or STARK)
    backend: str               # "wesolowski" or "stark"

    def serialize(self) -> bytes:
        """Serialize to bytes."""
        import struct
        data = bytearray()

        # Backend identifier (1 byte)
        backend_byte = 0x01 if self.backend == "wesolowski" else 0x02
        data.append(backend_byte)

        # Input hash (32 bytes)
        data.extend(self.input_hash)

        # Output hash (32 bytes)
        data.extend(self.output_hash)

        # Difficulty (8 bytes)
        data.extend(struct.pack('<Q', self.difficulty))

        # Proof data (variable length with 4-byte prefix)
        data.extend(struct.pack('<I', len(self.proof_data)))
        data.extend(self.proof_data)

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'VDFProofBase':
        """Deserialize from bytes."""
        import struct
        offset = 0

        backend_byte = data[offset]
        backend = "wesolowski" if backend_byte == 0x01 else "stark"
        offset += 1

        input_hash = data[offset:offset + 32]
        offset += 32

        output_hash = data[offset:offset + 32]
        offset += 32

        difficulty = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        proof_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        proof_data = data[offset:offset + proof_len]

        return cls(
            input_hash=input_hash,
            output_hash=output_hash,
            difficulty=difficulty,
            proof_data=proof_data,
            backend=backend
        )


@dataclass
class SignatureBundle:
    """Signature bundle supporting hybrid signatures."""
    primary_signature: bytes       # Main signature (Ed25519 or SPHINCS+)
    primary_algorithm: str         # "ed25519" or "sphincs+"
    secondary_signature: Optional[bytes] = None  # For hybrid mode
    secondary_algorithm: Optional[str] = None

    def serialize(self) -> bytes:
        """Serialize to bytes."""
        import struct
        data = bytearray()

        # Primary algorithm (1 byte: 0x01=ed25519, 0x02=sphincs+)
        algo_byte = 0x01 if self.primary_algorithm == "ed25519" else 0x02
        data.append(algo_byte)

        # Primary signature
        data.extend(struct.pack('<I', len(self.primary_signature)))
        data.extend(self.primary_signature)

        # Secondary signature (optional)
        if self.secondary_signature:
            data.append(0x01)  # Has secondary
            algo_byte = 0x01 if self.secondary_algorithm == "ed25519" else 0x02
            data.append(algo_byte)
            data.extend(struct.pack('<I', len(self.secondary_signature)))
            data.extend(self.secondary_signature)
        else:
            data.append(0x00)  # No secondary

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'SignatureBundle':
        """Deserialize from bytes."""
        import struct
        offset = 0

        algo_byte = data[offset]
        primary_algorithm = "ed25519" if algo_byte == 0x01 else "sphincs+"
        offset += 1

        sig_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        primary_signature = data[offset:offset + sig_len]
        offset += sig_len

        has_secondary = data[offset] == 0x01
        offset += 1

        secondary_signature = None
        secondary_algorithm = None

        if has_secondary:
            algo_byte = data[offset]
            secondary_algorithm = "ed25519" if algo_byte == 0x01 else "sphincs+"
            offset += 1

            sig_len = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            secondary_signature = data[offset:offset + sig_len]

        return cls(
            primary_signature=primary_signature,
            primary_algorithm=primary_algorithm,
            secondary_signature=secondary_signature,
            secondary_algorithm=secondary_algorithm
        )


# ============================================================================
# CRYPTO PROVIDER ABSTRACT BASE CLASS
# ============================================================================

class CryptoProvider(ABC):
    """
    Abstract base class for cryptographic providers.

    All cryptographic operations go through this interface,
    allowing seamless switching between backends.
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return backend identifier string."""
        pass

    @property
    @abstractmethod
    def is_post_quantum(self) -> bool:
        """Return True if this backend uses post-quantum algorithms."""
        pass

    # ========================================================================
    # HASH FUNCTIONS
    # ========================================================================

    @abstractmethod
    def hash(self, data: bytes) -> bytes:
        """
        Compute cryptographic hash.

        Args:
            data: Input bytes

        Returns:
            32-byte hash
        """
        pass

    @abstractmethod
    def hash_double(self, data: bytes) -> bytes:
        """
        Compute double hash (for Merkle trees).

        Args:
            data: Input bytes

        Returns:
            32-byte hash
        """
        pass

    @abstractmethod
    def hmac(self, key: bytes, data: bytes) -> bytes:
        """
        Compute HMAC.

        Args:
            key: HMAC key
            data: Input data

        Returns:
            32-byte HMAC
        """
        pass

    # ========================================================================
    # KEY GENERATION
    # ========================================================================

    @abstractmethod
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate new signing keypair.

        Returns:
            (private_key, public_key) tuple
        """
        pass

    @abstractmethod
    def derive_public_key(self, private_key: bytes) -> bytes:
        """
        Derive public key from private key.

        Args:
            private_key: Private key bytes

        Returns:
            Public key bytes
        """
        pass

    @abstractmethod
    def get_public_key_size(self) -> int:
        """Return size of public key in bytes."""
        pass

    @abstractmethod
    def get_signature_size(self) -> int:
        """Return size of signature in bytes."""
        pass

    # ========================================================================
    # SIGNATURES
    # ========================================================================

    @abstractmethod
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """
        Sign message.

        Args:
            private_key: Private signing key
            message: Message bytes to sign

        Returns:
            Signature bytes
        """
        pass

    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify signature.

        Args:
            public_key: Public verification key
            message: Original message
            signature: Signature to verify

        Returns:
            True if valid
        """
        pass

    def batch_verify(
        self,
        public_keys: List[bytes],
        messages: List[bytes],
        signatures: List[bytes]
    ) -> bool:
        """
        Batch verify multiple signatures.

        Default implementation verifies sequentially.
        Subclasses may override for optimization.
        """
        if len(public_keys) != len(messages) or len(messages) != len(signatures):
            return False

        for pk, msg, sig in zip(public_keys, messages, signatures):
            if not self.verify(pk, msg, sig):
                return False
        return True

    # ========================================================================
    # VDF (VERIFIABLE DELAY FUNCTION)
    # ========================================================================

    @abstractmethod
    def vdf_compute(
        self,
        input_data: bytes,
        difficulty: int,
        progress_callback: Optional[callable] = None
    ) -> VDFProofBase:
        """
        Compute VDF output and proof.

        Args:
            input_data: Input seed (32 bytes)
            difficulty: Number of iterations/steps
            progress_callback: Optional callback(current, total)

        Returns:
            VDFProofBase with output and proof
        """
        pass

    @abstractmethod
    def vdf_verify(self, proof: VDFProofBase) -> bool:
        """
        Verify VDF proof.

        Args:
            proof: VDF proof to verify

        Returns:
            True if valid
        """
        pass

    @abstractmethod
    def vdf_calibrate(self, target_seconds: float) -> int:
        """
        Calibrate VDF difficulty for target time.

        Args:
            target_seconds: Target computation time

        Returns:
            Recommended difficulty value
        """
        pass

    # ========================================================================
    # VRF (VERIFIABLE RANDOM FUNCTION)
    # ========================================================================

    @abstractmethod
    def vrf_prove(self, private_key: bytes, alpha: bytes) -> Tuple[bytes, bytes]:
        """
        Generate VRF proof.

        Args:
            private_key: VRF private key
            alpha: VRF input

        Returns:
            (beta, proof) tuple - beta is 32-byte output
        """
        pass

    @abstractmethod
    def vrf_verify(
        self,
        public_key: bytes,
        alpha: bytes,
        beta: bytes,
        proof: bytes
    ) -> bool:
        """
        Verify VRF proof.

        Args:
            public_key: VRF public key
            alpha: VRF input
            beta: VRF output to verify
            proof: VRF proof

        Returns:
            True if valid
        """
        pass

    # ========================================================================
    # KEY EXCHANGE (OPTIONAL)
    # ========================================================================

    def key_exchange_generate(self) -> Tuple[bytes, bytes]:
        """
        Generate key exchange keypair.

        Returns:
            (private_key, public_key) for key exchange
        """
        raise NotImplementedError("Key exchange not supported by this backend")

    def key_exchange_derive(
        self,
        private_key: bytes,
        peer_public_key: bytes
    ) -> bytes:
        """
        Derive shared secret.

        Args:
            private_key: Own private key
            peer_public_key: Peer's public key

        Returns:
            32-byte shared secret
        """
        raise NotImplementedError("Key exchange not supported by this backend")


# ============================================================================
# LEGACY CRYPTO PROVIDER (Ed25519 + SHA-256 + Wesolowski)
# ============================================================================

class LegacyCryptoProvider(CryptoProvider):
    """
    Legacy cryptographic provider using pre-quantum algorithms.

    Uses:
    - Ed25519 for signatures
    - SHA-256 for hashing
    - Wesolowski VDF over RSA groups
    - ECVRF for verifiable randomness
    - X25519 for key exchange
    """

    def __init__(self):
        # Lazy import to avoid circular dependencies
        from pantheon.prometheus.crypto import (
            Ed25519, sha256, sha256d, hmac_sha256,
            WesolowskiVDF, VDFProof, ECVRF, VRFOutput, X25519
        )

        self._ed25519 = Ed25519
        self._sha256 = sha256
        self._sha256d = sha256d
        self._hmac_sha256 = hmac_sha256
        self._vdf = WesolowskiVDF()
        self._ecvrf = ECVRF
        self._x25519 = X25519
        self._VDFProof = VDFProof
        self._VRFOutput = VRFOutput

    @property
    def backend_name(self) -> str:
        return "legacy"

    @property
    def is_post_quantum(self) -> bool:
        return False

    # Hash functions
    def hash(self, data: bytes) -> bytes:
        return self._sha256(data)

    def hash_double(self, data: bytes) -> bytes:
        return self._sha256d(data)

    def hmac(self, key: bytes, data: bytes) -> bytes:
        return self._hmac_sha256(key, data)

    # Key generation
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        return self._ed25519.generate_keypair()

    def derive_public_key(self, private_key: bytes) -> bytes:
        return self._ed25519.derive_public_key(private_key)

    def get_public_key_size(self) -> int:
        return 32  # Ed25519

    def get_signature_size(self) -> int:
        return 64  # Ed25519

    # Signatures
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        return self._ed25519.sign(private_key, message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return self._ed25519.verify(public_key, message, signature)

    def batch_verify(
        self,
        public_keys: List[bytes],
        messages: List[bytes],
        signatures: List[bytes]
    ) -> bool:
        return self._ed25519.batch_verify(public_keys, messages, signatures)

    # VDF
    def vdf_compute(
        self,
        input_data: bytes,
        difficulty: int,
        progress_callback: Optional[callable] = None
    ) -> VDFProofBase:
        proof = self._vdf.compute(input_data, difficulty, progress_callback=progress_callback)

        return VDFProofBase(
            input_hash=proof.input_hash,
            output_hash=self._sha256(proof.output),  # Hash the output for uniformity
            difficulty=proof.iterations,
            proof_data=proof.serialize(),
            backend="wesolowski"
        )

    def vdf_verify(self, proof: VDFProofBase) -> bool:
        if proof.backend != "wesolowski":
            logger.warning(f"Cannot verify {proof.backend} proof with legacy provider")
            return False

        wesolowski_proof = self._VDFProof.deserialize(proof.proof_data)
        return self._vdf.verify(wesolowski_proof)

    def vdf_calibrate(self, target_seconds: float) -> int:
        return self._vdf.calibrate(target_seconds)

    # VRF
    def vrf_prove(self, private_key: bytes, alpha: bytes) -> Tuple[bytes, bytes]:
        output = self._ecvrf.prove(private_key, alpha)
        return output.beta, output.proof

    def vrf_verify(
        self,
        public_key: bytes,
        alpha: bytes,
        beta: bytes,
        proof: bytes
    ) -> bool:
        vrf_output = self._VRFOutput(beta=beta, proof=proof)
        return self._ecvrf.verify(public_key, alpha, vrf_output)

    # Key exchange
    def key_exchange_generate(self) -> Tuple[bytes, bytes]:
        return self._x25519.generate_keypair()

    def key_exchange_derive(
        self,
        private_key: bytes,
        peer_public_key: bytes
    ) -> bytes:
        return self._x25519.shared_secret(private_key, peer_public_key)


# ============================================================================
# PROVIDER REGISTRY AND FACTORY
# ============================================================================

# Global provider cache
_provider_cache: Dict[CryptoBackend, CryptoProvider] = {}

# Current default backend (can be changed at runtime)
_current_backend: CryptoBackend = CryptoBackend.LEGACY


def set_default_backend(backend: CryptoBackend):
    """Set the default cryptographic backend."""
    global _current_backend
    _current_backend = backend
    logger.info(f"Default crypto backend set to: {backend.name}")


def get_default_backend() -> CryptoBackend:
    """Get the current default backend."""
    return _current_backend


def get_crypto_provider(backend: Optional[CryptoBackend] = None) -> CryptoProvider:
    """
    Get a cryptographic provider instance.

    Args:
        backend: Specific backend to use, or None for default

    Returns:
        CryptoProvider instance
    """
    if backend is None:
        backend = _current_backend

    if backend in _provider_cache:
        return _provider_cache[backend]

    if backend == CryptoBackend.LEGACY:
        provider = LegacyCryptoProvider()
    elif backend == CryptoBackend.POST_QUANTUM:
        # Lazy import post-quantum provider
        from pantheon.prometheus.pq_crypto import PostQuantumCryptoProvider
        provider = PostQuantumCryptoProvider()
    elif backend == CryptoBackend.HYBRID:
        # Lazy import hybrid provider
        from pantheon.prometheus.pq_crypto import HybridCryptoProvider
        provider = HybridCryptoProvider()
    else:
        raise ValueError(f"Unknown crypto backend: {backend}")

    _provider_cache[backend] = provider
    logger.info(f"Initialized crypto provider: {provider.backend_name}")

    return provider


def clear_provider_cache():
    """Clear the provider cache (useful for testing)."""
    global _provider_cache
    _provider_cache.clear()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def hash_data(data: bytes, backend: Optional[CryptoBackend] = None) -> bytes:
    """Hash data using current provider."""
    return get_crypto_provider(backend).hash(data)


def sign_message(
    private_key: bytes,
    message: bytes,
    backend: Optional[CryptoBackend] = None
) -> bytes:
    """Sign message using current provider."""
    return get_crypto_provider(backend).sign(private_key, message)


def verify_signature(
    public_key: bytes,
    message: bytes,
    signature: bytes,
    backend: Optional[CryptoBackend] = None
) -> bool:
    """Verify signature using current provider."""
    return get_crypto_provider(backend).verify(public_key, message, signature)


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run crypto provider self-tests."""
    logger.info("Running crypto provider self-tests...")

    # Test legacy provider
    legacy = get_crypto_provider(CryptoBackend.LEGACY)

    # Hash test
    h = legacy.hash(b"test")
    assert len(h) == 32
    logger.info("  Legacy hash")

    # Signature test
    sk, pk = legacy.generate_keypair()
    msg = b"test message"
    sig = legacy.sign(sk, msg)
    assert legacy.verify(pk, msg, sig)
    assert not legacy.verify(pk, b"wrong", sig)
    logger.info("  Legacy signatures")

    # VDF test (minimal iterations)
    proof = legacy.vdf_compute(b"test_input" * 3 + b"12", 1000)
    assert proof.backend == "wesolowski"
    assert legacy.vdf_verify(proof)
    logger.info("  Legacy VDF")

    # VRF test
    beta, vrf_proof = legacy.vrf_prove(sk, b"vrf_input")
    assert len(beta) == 32
    logger.info("  Legacy VRF")

    # Key exchange test
    sk1, pk1 = legacy.key_exchange_generate()
    sk2, pk2 = legacy.key_exchange_generate()
    shared1 = legacy.key_exchange_derive(sk1, pk2)
    shared2 = legacy.key_exchange_derive(sk2, pk1)
    assert shared1 == shared2
    logger.info("  Legacy key exchange")

    logger.info("All crypto provider tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
