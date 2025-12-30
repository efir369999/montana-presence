"""
Proof of Time - Post-Quantum Cryptographic Provider

This module implements quantum-resistant cryptographic primitives:
- SPHINCS+ signatures (NIST FIPS 205)
- SHA3-256 hashing (NIST FIPS 202)
- SHAKE256-based VDF with STARK proofs
- ML-KEM/Kyber key encapsulation (NIST FIPS 203)

Security assumptions:
- Hash-based signatures (SPHINCS+) are secure against quantum computers
- SHA3/SHAKE are quantum-resistant (Grover gives only sqrt speedup)
- STARK proofs are hash-based and quantum-resistant

Dependencies:
- liboqs-python: SPHINCS+ and ML-KEM implementations
- hashlib: SHA3-256 (built-in Python 3.6+)
- winterfell (Rust FFI): STARK proof generation/verification

Time is the ultimate proof.
"""

import hashlib
import hmac
import struct
import secrets
import logging
import os
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Dict, Any
from pathlib import Path

from pantheon.prometheus.crypto_provider import (
    CryptoProvider, VDFProofBase, SignatureBundle
)

logger = logging.getLogger("proof_of_time.pq_crypto")


# ============================================================================
# OPTIONAL DEPENDENCIES CHECK
# ============================================================================

# SPHINCS+ via liboqs
try:
    import oqs
    LIBOQS_AVAILABLE = True
    logger.debug("liboqs available - using SPHINCS+ signatures")
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("liboqs not available - SPHINCS+ signatures disabled")
    logger.warning("Install with: pip install liboqs-python")

# ML-KEM via liboqs
MLKEM_AVAILABLE = LIBOQS_AVAILABLE  # Same library

# Winterfell STARK prover (Rust FFI)
try:
    from . import winterfell_ffi
    WINTERFELL_AVAILABLE = True
    logger.debug("Winterfell FFI available - using STARK proofs")
except ImportError:
    WINTERFELL_AVAILABLE = False
    logger.warning("Winterfell FFI not available - using hash-chain VDF fallback")


# ============================================================================
# SHA3 HASH FUNCTIONS
# ============================================================================

def sha3_256(data: bytes) -> bytes:
    """Compute SHA3-256 hash (NIST FIPS 202)."""
    return hashlib.sha3_256(data).digest()


def sha3_256d(data: bytes) -> bytes:
    """Compute double SHA3-256 hash."""
    return sha3_256(sha3_256(data))


def sha3_512(data: bytes) -> bytes:
    """Compute SHA3-512 hash."""
    return hashlib.sha3_512(data).digest()


def shake256(data: bytes, length: int = 32) -> bytes:
    """
    Compute SHAKE256 extendable output function (XOF).

    SHAKE256 is the basis for our quantum-resistant VDF.
    """
    return hashlib.shake_256(data).digest(length)


def hmac_sha3_256(key: bytes, data: bytes) -> bytes:
    """Compute HMAC-SHA3-256."""
    return hmac.new(key, data, hashlib.sha3_256).digest()


# ============================================================================
# SPHINCS+ SIGNATURES (NIST FIPS 205)
# ============================================================================

class SPHINCSPlus:
    """
    SPHINCS+ signature scheme wrapper.

    SPHINCS+ is a stateless hash-based signature scheme standardized
    as NIST FIPS 205 (August 2024). It is quantum-resistant because
    its security relies only on the properties of hash functions.

    We use SPHINCS+-SHAKE-128f for normal transactions (fast, 17KB sigs)
    and SPHINCS+-SHAKE-256s for critical operations (secure, 29KB sigs).

    Properties:
    - Quantum-resistant (hash-based)
    - Stateless (no state management needed)
    - Conservative security assumptions
    - Larger signatures than classical schemes (~17-29KB vs 64B)
    """

    # Algorithm variants
    FAST_VARIANT = "SPHINCS+-SHAKE-128f"      # Fast signing, 17KB signatures
    SECURE_VARIANT = "SPHINCS+-SHAKE-256s"    # Small signatures, 29KB

    # Key and signature sizes (approximate)
    FAST_PUBLIC_KEY_SIZE = 32
    FAST_SECRET_KEY_SIZE = 64
    FAST_SIGNATURE_SIZE = 17088  # ~17KB

    SECURE_PUBLIC_KEY_SIZE = 64
    SECURE_SECRET_KEY_SIZE = 128
    SECURE_SIGNATURE_SIZE = 29792  # ~29KB

    def __init__(self, variant: str = "fast"):
        """
        Initialize SPHINCS+ wrapper.

        Args:
            variant: "fast" for SPHINCS+-SHAKE-128f, "secure" for SPHINCS+-SHAKE-256s
        """
        if not LIBOQS_AVAILABLE:
            raise RuntimeError("liboqs not available. Install with: pip install liboqs-python")

        if variant == "fast":
            self.algorithm = self.FAST_VARIANT
            self.public_key_size = self.FAST_PUBLIC_KEY_SIZE
            self.secret_key_size = self.FAST_SECRET_KEY_SIZE
            self.signature_size = self.FAST_SIGNATURE_SIZE
        else:
            self.algorithm = self.SECURE_VARIANT
            self.public_key_size = self.SECURE_PUBLIC_KEY_SIZE
            self.secret_key_size = self.SECURE_SECRET_KEY_SIZE
            self.signature_size = self.SECURE_SIGNATURE_SIZE

        # Verify algorithm is available
        available = oqs.get_enabled_sig_mechanisms()
        if self.algorithm not in available:
            # Try alternative naming
            alt_names = [
                self.algorithm.replace("+-", "_").replace("-", "_"),
                self.algorithm.replace("+-SHAKE-", "-SHAKE-"),
                "SPHINCS+-SHAKE-128f-simple" if variant == "fast" else "SPHINCS+-SHAKE-256s-simple",
            ]
            for alt in alt_names:
                if alt in available:
                    self.algorithm = alt
                    break
            else:
                logger.warning(f"SPHINCS+ variant {self.algorithm} not available")
                logger.warning(f"Available: {[a for a in available if 'SPHINCS' in a]}")
                # Use first available SPHINCS+ variant
                sphincs_variants = [a for a in available if 'SPHINCS' in a.upper()]
                if sphincs_variants:
                    self.algorithm = sphincs_variants[0]
                    logger.info(f"Using fallback: {self.algorithm}")
                else:
                    raise RuntimeError("No SPHINCS+ variants available in liboqs")

        self._signer = oqs.Signature(self.algorithm)

        # Update sizes from actual implementation
        self.public_key_size = self._signer.details['length_public_key']
        self.secret_key_size = self._signer.details['length_secret_key']
        self.signature_size = self._signer.details['length_signature']

        logger.info(f"SPHINCS+ initialized: {self.algorithm}")
        logger.info(f"  Public key: {self.public_key_size} bytes")
        logger.info(f"  Secret key: {self.secret_key_size} bytes")
        logger.info(f"  Signature: {self.signature_size} bytes")

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate SPHINCS+ keypair.

        Returns:
            (secret_key, public_key) tuple
        """
        public_key = self._signer.generate_keypair()
        secret_key = self._signer.export_secret_key()
        return secret_key, public_key

    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        """
        Sign message with SPHINCS+.

        Args:
            secret_key: SPHINCS+ secret key
            message: Message to sign

        Returns:
            SPHINCS+ signature (~17-29KB)
        """
        # Create new signer with the secret key
        signer = oqs.Signature(self.algorithm, secret_key)
        return signer.sign(message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify SPHINCS+ signature.

        Args:
            public_key: SPHINCS+ public key
            message: Original message
            signature: Signature to verify

        Returns:
            True if valid
        """
        try:
            verifier = oqs.Signature(self.algorithm)
            return verifier.verify(message, signature, public_key)
        except Exception as e:
            logger.warning(f"SPHINCS+ verification error: {e}")
            return False


# ============================================================================
# FALLBACK SPHINCS+ SIMULATION (for testing without liboqs)
# ============================================================================

class SPHINCSPlusFallback:
    """
    Fallback SPHINCS+ simulation for testing without liboqs.

    WARNING: This is NOT cryptographically secure!
    Only use for testing and development.
    """

    # Simulated sizes (realistic for SPHINCS+-SHAKE-128f)
    public_key_size = 32
    secret_key_size = 64
    signature_size = 17088

    def __init__(self, variant: str = "fast"):
        logger.warning("Using SPHINCS+ FALLBACK - NOT SECURE FOR PRODUCTION")
        self.variant = variant

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate simulated keypair."""
        secret_key = secrets.token_bytes(self.secret_key_size)
        # Derive "public key" from secret using a specific derivation
        public_key = sha3_256(secret_key + b"FALLBACK_PK_DERIVE")
        return secret_key, public_key

    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        """Create simulated signature."""
        # Create deterministic "signature" that encodes the message hash
        # Structure: [message_commitment (32)] || [secret_proof (32)] || [padding]
        message_hash = sha3_256(message)
        secret_proof = sha3_256(secret_key + message_hash + b"FALLBACK_SIG")

        sig_seed = message_hash + secret_proof
        # Expand to signature size
        sig_data = sig_seed
        while len(sig_data) < self.signature_size:
            sig_data += sha3_256(sig_data + sig_seed)
        return sig_data[:self.signature_size]

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify simulated signature."""
        # This is NOT cryptographically secure - just for testing
        if len(signature) != self.signature_size:
            return False

        # Extract message hash from signature (first 32 bytes)
        sig_message_hash = signature[:32]

        # Compute expected message hash
        expected_message_hash = sha3_256(message)

        # Signature is valid only if message hash matches
        return sig_message_hash == expected_message_hash


# ============================================================================
# SHAKE256 VDF (QUANTUM-RESISTANT)
# ============================================================================

@dataclass
class SHAKE256VDFCheckpoint:
    """Checkpoint for resumable SHAKE256 VDF computation."""
    input_hash: bytes
    current_state: bytes
    current_iteration: int
    target_iterations: int
    checkpoints: List[bytes] = field(default_factory=list)  # For STARK proof

    def serialize(self) -> bytes:
        """Serialize checkpoint."""
        data = bytearray()
        data.extend(self.input_hash)
        data.extend(self.current_state)
        data.extend(struct.pack('<Q', self.current_iteration))
        data.extend(struct.pack('<Q', self.target_iterations))
        data.extend(struct.pack('<I', len(self.checkpoints)))
        for cp in self.checkpoints:
            data.extend(cp)
        return bytes(data)


class SHAKE256VDF:
    """
    Quantum-resistant VDF using SHAKE256 hash iterations.

    The VDF computes:
        output = SHAKE256(SHAKE256(SHAKE256(...SHAKE256(input)...)))
                                   ^ T iterations

    This is provably sequential because each iteration depends on
    the previous output. Verification uses STARK proofs for O(log T).

    Properties:
    - Quantum-resistant (SHAKE256 is secure against Grover)
    - Sequential computation (cannot be parallelized)
    - O(log T) verification via STARK proofs
    - No trusted setup required
    """

    # Configuration
    STATE_SIZE = 32  # SHAKE256 output size per iteration
    CHECKPOINT_INTERVAL = 1000  # Save checkpoint every N iterations
    MIN_ITERATIONS = 100
    MAX_ITERATIONS = 10_000_000_000

    def __init__(self):
        self._cached_ips: Optional[float] = None

    def _shake256_iteration(self, state: bytes) -> bytes:
        """Single SHAKE256 iteration."""
        return shake256(state, self.STATE_SIZE)

    def compute(
        self,
        input_data: bytes,
        iterations: int,
        progress_callback: Optional[callable] = None,
        collect_checkpoints: bool = True
    ) -> Tuple[bytes, List[bytes]]:
        """
        Compute SHAKE256 VDF.

        Args:
            input_data: Input seed (will be hashed to 32 bytes)
            iterations: Number of sequential iterations T
            progress_callback: Optional callback(current, total)
            collect_checkpoints: Whether to collect checkpoints for STARK proof

        Returns:
            (output, checkpoints) tuple
        """
        import time as time_module

        if iterations < self.MIN_ITERATIONS:
            raise ValueError(f"Iterations {iterations} below minimum {self.MIN_ITERATIONS}")
        if iterations > self.MAX_ITERATIONS:
            raise ValueError(f"Iterations {iterations} exceeds maximum {self.MAX_ITERATIONS}")

        # Normalize input to 32 bytes
        if len(input_data) != 32:
            input_data = sha3_256(input_data)

        state = input_data
        checkpoints = [input_data] if collect_checkpoints else []

        start_time = time_module.perf_counter()

        for i in range(iterations):
            # Collect checkpoint BEFORE iteration (at multiples of interval)
            # This ensures each segment has exactly CHECKPOINT_INTERVAL iterations
            if collect_checkpoints and i > 0 and i % self.CHECKPOINT_INTERVAL == 0:
                checkpoints.append(state)

            state = self._shake256_iteration(state)

            # Progress callback
            if progress_callback and i % 10000 == 0:
                progress_callback(i, iterations)

            # Logging for long computations
            if iterations > 100000 and i % 100000 == 0 and i > 0:
                elapsed = time_module.perf_counter() - start_time
                eta = elapsed * (iterations - i) / i
                logger.debug(f"SHAKE256 VDF: {i}/{iterations} ({100*i/iterations:.1f}%), ETA: {eta:.1f}s")

        if collect_checkpoints:
            checkpoints.append(state)

        elapsed = time_module.perf_counter() - start_time
        logger.debug(f"SHAKE256 VDF computed in {elapsed:.2f}s ({iterations/elapsed:.0f} iter/s)")

        return state, checkpoints

    def verify_sequential(
        self,
        input_data: bytes,
        output: bytes,
        iterations: int
    ) -> bool:
        """
        Verify VDF by recomputing (slow, O(T)).

        This is the fallback when STARK proofs are not available.
        """
        if len(input_data) != 32:
            input_data = sha3_256(input_data)

        state = input_data
        for _ in range(iterations):
            state = self._shake256_iteration(state)

        return state == output

    def verify_with_checkpoints(
        self,
        input_data: bytes,
        output: bytes,
        checkpoints: List[bytes],
        checkpoint_interval: int
    ) -> bool:
        """
        Verify VDF using checkpoints (faster than full recomputation).

        Verifies random segments between checkpoints.
        """
        if not checkpoints:
            return self.verify_sequential(input_data, output, checkpoint_interval)

        if len(input_data) != 32:
            input_data = sha3_256(input_data)

        # Verify first checkpoint matches input
        if checkpoints[0] != input_data:
            logger.warning("VDF checkpoint 0 doesn't match input")
            return False

        # Verify last checkpoint matches output
        if checkpoints[-1] != output:
            logger.warning("VDF final checkpoint doesn't match output")
            return False

        # Verify random segments (probabilistic verification)
        # Use SystemRandom for unpredictable segment selection
        num_segments = min(len(checkpoints) - 1, 10)  # Check up to 10 segments
        rng = secrets.SystemRandom()
        all_segments = list(range(len(checkpoints) - 1))
        rng.shuffle(all_segments)
        segments_to_check = all_segments[:num_segments]

        for seg_idx in segments_to_check:
            start = checkpoints[seg_idx]
            expected_end = checkpoints[seg_idx + 1]

            # Recompute segment
            state = start
            for _ in range(checkpoint_interval):
                state = self._shake256_iteration(state)

            if state != expected_end:
                logger.warning(f"VDF checkpoint segment {seg_idx} verification failed")
                return False

        return True

    def calibrate(self, target_seconds: float, sample_iterations: int = 10000) -> int:
        """
        Calibrate iterations for target computation time.

        Args:
            target_seconds: Target computation time
            sample_iterations: Sample size for calibration

        Returns:
            Recommended iterations for target time
        """
        import time as time_module

        test_input = sha3_256(b"vdf_calibration")
        state = test_input

        start = time_module.perf_counter()
        for _ in range(sample_iterations):
            state = self._shake256_iteration(state)
        elapsed = time_module.perf_counter() - start

        ips = sample_iterations / elapsed
        self._cached_ips = ips

        recommended = max(self.MIN_ITERATIONS, int(ips * target_seconds))

        logger.info(f"SHAKE256 VDF calibration: {ips:.0f} iter/sec")
        logger.info(f"  Recommended: {recommended:,} iterations for {target_seconds}s")

        return recommended

    def get_iterations_per_second(self) -> float:
        """Get cached IPS or measure."""
        if self._cached_ips:
            return self._cached_ips
        self.calibrate(1.0)
        return self._cached_ips


# ============================================================================
# STARK PROOF FOR VDF (PLACEHOLDER)
# ============================================================================

class STARKProver:
    """
    STARK proof generation for SHAKE256 VDF verification.

    STARK (Scalable Transparent ARguments of Knowledge) provides:
    - O(log T) verification time
    - No trusted setup (transparent)
    - Quantum-resistant (hash-based)
    - ~50-200KB proof size

    This is a placeholder implementation. The real implementation
    requires Winterfell (Rust) integration via PyO3.

    AIR (Algebraic Intermediate Representation) constraints:
        Constraint: next_state = SHAKE256(current_state)
        Boundary: state[0] = input, state[T] = output
    """

    def __init__(self):
        if WINTERFELL_AVAILABLE:
            logger.info("STARK prover using Winterfell backend")
        else:
            logger.warning("STARK prover using fallback (checkpoints only)")

    def generate_proof(
        self,
        input_hash: bytes,
        output_hash: bytes,
        checkpoints: List[bytes],
        iterations: int
    ) -> bytes:
        """
        Generate STARK proof for VDF computation.

        Args:
            input_hash: VDF input
            output_hash: VDF output
            checkpoints: Intermediate states
            iterations: Total iterations

        Returns:
            STARK proof bytes (~50-200KB)
        """
        if WINTERFELL_AVAILABLE:
            return winterfell_ffi.prove_vdf(input_hash, output_hash, checkpoints, iterations)

        # Fallback: serialize checkpoints as "proof"
        # This is NOT a real STARK proof - just for testing
        logger.warning("Using checkpoint-based proof (not a real STARK)")
        return self._serialize_checkpoint_proof(input_hash, output_hash, checkpoints, iterations)

    def verify_proof(
        self,
        input_hash: bytes,
        output_hash: bytes,
        proof: bytes,
        iterations: int
    ) -> bool:
        """
        Verify STARK proof.

        Args:
            input_hash: VDF input
            output_hash: VDF output
            proof: STARK proof to verify
            iterations: Expected iterations

        Returns:
            True if proof is valid
        """
        if WINTERFELL_AVAILABLE:
            return winterfell_ffi.verify_vdf(input_hash, output_hash, proof, iterations)

        # Fallback: verify checkpoint proof
        return self._verify_checkpoint_proof(input_hash, output_hash, proof, iterations)

    def _serialize_checkpoint_proof(
        self,
        input_hash: bytes,
        output_hash: bytes,
        checkpoints: List[bytes],
        iterations: int
    ) -> bytes:
        """Serialize checkpoint-based proof (fallback)."""
        data = bytearray()

        # Magic bytes to identify fallback proof
        data.extend(b'CPPT')  # CheckPoint Proof Type

        # Metadata
        data.extend(struct.pack('<Q', iterations))
        data.extend(struct.pack('<I', len(checkpoints)))

        # Checkpoints
        for cp in checkpoints:
            data.extend(cp)

        return bytes(data)

    def _verify_checkpoint_proof(
        self,
        input_hash: bytes,
        output_hash: bytes,
        proof: bytes,
        iterations: int
    ) -> bool:
        """Verify checkpoint-based proof (fallback)."""
        try:
            if proof[:4] != b'CPPT':
                logger.warning("Unknown proof type")
                return False

            offset = 4
            proof_iterations = struct.unpack_from('<Q', proof, offset)[0]
            offset += 8

            if proof_iterations != iterations:
                logger.warning(f"Proof iterations mismatch: {proof_iterations} vs {iterations}")
                return False

            num_checkpoints = struct.unpack_from('<I', proof, offset)[0]
            offset += 4

            checkpoints = []
            for _ in range(num_checkpoints):
                checkpoints.append(proof[offset:offset + 32])
                offset += 32

            # Verify checkpoints
            if not checkpoints:
                return False

            if checkpoints[0] != input_hash:
                logger.warning("Proof input mismatch")
                return False

            if checkpoints[-1] != output_hash:
                logger.warning("Proof output mismatch")
                return False

            # Verify checkpoint chain (sample-based)
            vdf = SHAKE256VDF()
            checkpoint_interval = iterations // (len(checkpoints) - 1) if len(checkpoints) > 1 else iterations

            return vdf.verify_with_checkpoints(
                input_hash, output_hash, checkpoints, checkpoint_interval
            )

        except Exception as e:
            logger.error(f"Proof verification error: {e}")
            return False


# ============================================================================
# ML-KEM/KYBER KEY ENCAPSULATION (NIST FIPS 203)
# ============================================================================

class MLKEM:
    """
    ML-KEM (Module-Lattice-Based Key Encapsulation) wrapper.

    ML-KEM (formerly Kyber) is standardized as NIST FIPS 203 (August 2024).
    It provides quantum-resistant key encapsulation for secure key exchange.

    Security levels:
    - ML-KEM-512: ~128-bit security
    - ML-KEM-768: ~192-bit security (recommended)
    - ML-KEM-1024: ~256-bit security
    """

    def __init__(self, security_level: str = "768"):
        """
        Initialize ML-KEM wrapper.

        Args:
            security_level: "512", "768", or "1024"
        """
        if not MLKEM_AVAILABLE:
            raise RuntimeError("liboqs not available for ML-KEM")

        # Map security level to algorithm name
        self.algorithm = f"Kyber{security_level}"

        # Check availability
        available = oqs.get_enabled_kem_mechanisms()
        if self.algorithm not in available:
            # Try ML-KEM naming
            alt_names = [f"ML-KEM-{security_level}", f"MLKEM{security_level}"]
            for alt in alt_names:
                if alt in available:
                    self.algorithm = alt
                    break
            else:
                kyber_variants = [a for a in available if 'Kyber' in a or 'KEM' in a]
                if kyber_variants:
                    self.algorithm = kyber_variants[0]
                    logger.info(f"Using fallback KEM: {self.algorithm}")
                else:
                    raise RuntimeError("No ML-KEM/Kyber variants available")

        self._kem = oqs.KeyEncapsulation(self.algorithm)

        logger.info(f"ML-KEM initialized: {self.algorithm}")

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate ML-KEM keypair.

        Returns:
            (secret_key, public_key) tuple
        """
        public_key = self._kem.generate_keypair()
        secret_key = self._kem.export_secret_key()
        return secret_key, public_key

    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate shared secret.

        Args:
            public_key: Recipient's public key

        Returns:
            (ciphertext, shared_secret) tuple
        """
        kem = oqs.KeyEncapsulation(self.algorithm)
        ciphertext, shared_secret = kem.encap_secret(public_key)
        return ciphertext, shared_secret

    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate shared secret.

        Args:
            secret_key: Own secret key
            ciphertext: Ciphertext from encapsulate()

        Returns:
            32-byte shared secret
        """
        kem = oqs.KeyEncapsulation(self.algorithm, secret_key)
        return kem.decap_secret(ciphertext)


# ============================================================================
# POST-QUANTUM CRYPTO PROVIDER
# ============================================================================

class PostQuantumCryptoProvider(CryptoProvider):
    """
    Post-quantum cryptographic provider.

    Uses:
    - SPHINCS+ for signatures (NIST FIPS 205)
    - SHA3-256 for hashing (NIST FIPS 202)
    - SHAKE256 VDF with STARK proofs
    - ML-KEM for key exchange (NIST FIPS 203)
    """

    def __init__(self, sphincs_variant: str = "fast"):
        """
        Initialize post-quantum provider.

        Args:
            sphincs_variant: "fast" or "secure" for SPHINCS+ variant
        """
        # Initialize SPHINCS+
        if LIBOQS_AVAILABLE:
            self._sphincs = SPHINCSPlus(sphincs_variant)
        else:
            logger.warning("Using SPHINCS+ fallback - NOT SECURE")
            self._sphincs = SPHINCSPlusFallback(sphincs_variant)

        # Initialize VDF
        self._vdf = SHAKE256VDF()
        self._stark = STARKProver()

        # Initialize ML-KEM (optional)
        self._mlkem: Optional[MLKEM] = None
        if MLKEM_AVAILABLE:
            try:
                self._mlkem = MLKEM("768")
            except Exception as e:
                logger.warning(f"ML-KEM initialization failed: {e}")

    @property
    def backend_name(self) -> str:
        return "post_quantum"

    @property
    def is_post_quantum(self) -> bool:
        return True

    # ========================================================================
    # HASH FUNCTIONS
    # ========================================================================

    def hash(self, data: bytes) -> bytes:
        return sha3_256(data)

    def hash_double(self, data: bytes) -> bytes:
        return sha3_256d(data)

    def hmac(self, key: bytes, data: bytes) -> bytes:
        return hmac_sha3_256(key, data)

    # ========================================================================
    # KEY GENERATION
    # ========================================================================

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        return self._sphincs.generate_keypair()

    def derive_public_key(self, private_key: bytes) -> bytes:
        # SPHINCS+ doesn't support direct derivation, generate new and compare
        # This is a limitation - store public key alongside private
        raise NotImplementedError(
            "SPHINCS+ doesn't support public key derivation. "
            "Store public key alongside private key."
        )

    def get_public_key_size(self) -> int:
        return self._sphincs.public_key_size

    def get_signature_size(self) -> int:
        return self._sphincs.signature_size

    # ========================================================================
    # SIGNATURES
    # ========================================================================

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        return self._sphincs.sign(private_key, message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        return self._sphincs.verify(public_key, message, signature)

    # ========================================================================
    # VDF
    # ========================================================================

    def vdf_compute(
        self,
        input_data: bytes,
        difficulty: int,
        progress_callback: Optional[callable] = None
    ) -> VDFProofBase:
        # Compute VDF
        output, checkpoints = self._vdf.compute(
            input_data, difficulty,
            progress_callback=progress_callback,
            collect_checkpoints=True
        )

        # Normalize input
        if len(input_data) != 32:
            input_data = sha3_256(input_data)

        # Generate STARK proof
        stark_proof = self._stark.generate_proof(
            input_data, output, checkpoints, difficulty
        )

        return VDFProofBase(
            input_hash=input_data,
            output_hash=output,
            difficulty=difficulty,
            proof_data=stark_proof,
            backend="stark"
        )

    def vdf_verify(self, proof: VDFProofBase) -> bool:
        if proof.backend != "stark":
            logger.warning(f"Cannot verify {proof.backend} proof with PQ provider")
            return False

        return self._stark.verify_proof(
            proof.input_hash,
            proof.output_hash,
            proof.proof_data,
            proof.difficulty
        )

    def vdf_calibrate(self, target_seconds: float) -> int:
        return self._vdf.calibrate(target_seconds)

    # ========================================================================
    # VRF (POST-QUANTUM)
    # ========================================================================

    def vrf_prove(self, private_key: bytes, alpha: bytes) -> Tuple[bytes, bytes]:
        """
        Generate post-quantum VRF proof.

        Uses hash-based VRF construction:
            beta = H(private_key || alpha || "vrf_output")
            proof = SPHINCS+.sign(private_key, alpha || beta)
        """
        # Compute VRF output
        beta = sha3_256(private_key + alpha + b"vrf_output")

        # Generate proof (signature over input and output)
        proof_message = alpha + beta
        proof = self._sphincs.sign(private_key, proof_message)

        return beta, proof

    def vrf_verify(
        self,
        public_key: bytes,
        alpha: bytes,
        beta: bytes,
        proof: bytes
    ) -> bool:
        """
        Verify post-quantum VRF proof.

        Verifies that:
        1. Signature is valid over (alpha || beta)
        2. Beta could only have been produced by private key holder
        """
        try:
            proof_message = alpha + beta
            return self._sphincs.verify(public_key, proof_message, proof)
        except Exception as e:
            logger.warning(f"VRF verification error: {e}")
            return False

    # ========================================================================
    # KEY EXCHANGE
    # ========================================================================

    def key_exchange_generate(self) -> Tuple[bytes, bytes]:
        if self._mlkem is None:
            raise NotImplementedError("ML-KEM not available")
        return self._mlkem.generate_keypair()

    def key_exchange_derive(
        self,
        private_key: bytes,
        peer_public_key: bytes
    ) -> bytes:
        """
        Derive shared secret using ML-KEM.

        Note: This is encapsulation-based, not DH-style.
        For actual key exchange, use encapsulate/decapsulate.
        """
        if self._mlkem is None:
            raise NotImplementedError("ML-KEM not available")

        # For compatibility, we do encapsulation and return shared secret
        # In practice, the peer would send ciphertext, we'd decapsulate
        ciphertext, shared_secret = self._mlkem.encapsulate(peer_public_key)
        return shared_secret


# ============================================================================
# HYBRID CRYPTO PROVIDER (TRANSITION PERIOD)
# ============================================================================

class HybridCryptoProvider(CryptoProvider):
    """
    Hybrid cryptographic provider for transition period.

    Signs with BOTH Ed25519 (legacy) and SPHINCS+ (post-quantum).
    Verification succeeds if EITHER signature is valid (for compatibility)
    or BOTH are valid (for maximum security).

    This allows:
    1. New nodes to verify old transactions (Ed25519)
    2. Old nodes to verify new transactions (Ed25519 part)
    3. Post-quantum security for forward secrecy
    """

    def __init__(self, require_both: bool = False):
        """
        Initialize hybrid provider.

        Args:
            require_both: If True, both signatures must verify.
                         If False, either signature is sufficient.
        """
        from pantheon.prometheus.crypto_provider import LegacyCryptoProvider

        self._legacy = LegacyCryptoProvider()
        self._pq = PostQuantumCryptoProvider()
        self._require_both = require_both

    @property
    def backend_name(self) -> str:
        return "hybrid"

    @property
    def is_post_quantum(self) -> bool:
        return True  # Has PQ component

    # Hash functions use SHA3 (post-quantum safe)
    def hash(self, data: bytes) -> bytes:
        return self._pq.hash(data)

    def hash_double(self, data: bytes) -> bytes:
        return self._pq.hash_double(data)

    def hmac(self, key: bytes, data: bytes) -> bytes:
        return self._pq.hmac(key, data)

    # Key generation produces hybrid keys
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate hybrid keypair (Ed25519 + SPHINCS+)."""
        legacy_sk, legacy_pk = self._legacy.generate_keypair()
        pq_sk, pq_pk = self._pq.generate_keypair()

        # Combine keys with length prefixes
        combined_sk = struct.pack('<I', len(legacy_sk)) + legacy_sk + pq_sk
        combined_pk = struct.pack('<I', len(legacy_pk)) + legacy_pk + pq_pk

        return combined_sk, combined_pk

    def derive_public_key(self, private_key: bytes) -> bytes:
        # Extract legacy SK and derive
        legacy_sk_len = struct.unpack_from('<I', private_key, 0)[0]
        legacy_sk = private_key[4:4 + legacy_sk_len]
        legacy_pk = self._legacy.derive_public_key(legacy_sk)

        # PQ doesn't support derivation - would need stored PK
        raise NotImplementedError("Hybrid keys require stored public key")

    def get_public_key_size(self) -> int:
        return 4 + 32 + self._pq.get_public_key_size()

    def get_signature_size(self) -> int:
        return 4 + 64 + self._pq.get_signature_size()

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Sign with both algorithms."""
        # Parse hybrid private key
        legacy_sk_len = struct.unpack_from('<I', private_key, 0)[0]
        legacy_sk = private_key[4:4 + legacy_sk_len]
        pq_sk = private_key[4 + legacy_sk_len:]

        # Sign with both
        legacy_sig = self._legacy.sign(legacy_sk, message)
        pq_sig = self._pq.sign(pq_sk, message)

        # Combine signatures
        return struct.pack('<I', len(legacy_sig)) + legacy_sig + pq_sig

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify hybrid signature."""
        try:
            # Parse hybrid public key
            legacy_pk_len = struct.unpack_from('<I', public_key, 0)[0]
            legacy_pk = public_key[4:4 + legacy_pk_len]
            pq_pk = public_key[4 + legacy_pk_len:]

            # Parse hybrid signature
            legacy_sig_len = struct.unpack_from('<I', signature, 0)[0]
            legacy_sig = signature[4:4 + legacy_sig_len]
            pq_sig = signature[4 + legacy_sig_len:]

            # Verify both
            legacy_valid = self._legacy.verify(legacy_pk, message, legacy_sig)
            pq_valid = self._pq.verify(pq_pk, message, pq_sig)

            if self._require_both:
                return legacy_valid and pq_valid
            else:
                return legacy_valid or pq_valid

        except Exception as e:
            logger.warning(f"Hybrid verification error: {e}")
            return False

    # VDF uses post-quantum (SHAKE256 + STARK)
    def vdf_compute(self, input_data: bytes, difficulty: int,
                   progress_callback: Optional[callable] = None) -> VDFProofBase:
        return self._pq.vdf_compute(input_data, difficulty, progress_callback)

    def vdf_verify(self, proof: VDFProofBase) -> bool:
        # Can verify both types
        if proof.backend == "wesolowski":
            return self._legacy.vdf_verify(proof)
        else:
            return self._pq.vdf_verify(proof)

    def vdf_calibrate(self, target_seconds: float) -> int:
        return self._pq.vdf_calibrate(target_seconds)

    # VRF uses post-quantum
    def vrf_prove(self, private_key: bytes, alpha: bytes) -> Tuple[bytes, bytes]:
        # Extract PQ key and use PQ VRF
        legacy_sk_len = struct.unpack_from('<I', private_key, 0)[0]
        pq_sk = private_key[4 + legacy_sk_len:]
        return self._pq.vrf_prove(pq_sk, alpha)

    def vrf_verify(self, public_key: bytes, alpha: bytes,
                   beta: bytes, proof: bytes) -> bool:
        legacy_pk_len = struct.unpack_from('<I', public_key, 0)[0]
        pq_pk = public_key[4 + legacy_pk_len:]
        return self._pq.vrf_verify(pq_pk, alpha, beta, proof)

    # Key exchange uses ML-KEM
    def key_exchange_generate(self) -> Tuple[bytes, bytes]:
        return self._pq.key_exchange_generate()

    def key_exchange_derive(self, private_key: bytes, peer_public_key: bytes) -> bytes:
        return self._pq.key_exchange_derive(private_key, peer_public_key)


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run post-quantum crypto self-tests."""
    logger.info("Running post-quantum crypto self-tests...")

    # Test SHA3
    h = sha3_256(b"test")
    assert len(h) == 32
    expected = bytes.fromhex("36f028580bb02cc8272a9a020f4200e346e276ae664e45ee80745574e2f5ab80")
    assert h == expected, f"SHA3-256 mismatch: {h.hex()}"
    logger.info("  SHA3-256")

    # Test SHAKE256
    s = shake256(b"test", 64)
    assert len(s) == 64
    logger.info("  SHAKE256")

    # Test SPHINCS+ (or fallback)
    if LIBOQS_AVAILABLE:
        sphincs = SPHINCSPlus("fast")
    else:
        sphincs = SPHINCSPlusFallback("fast")

    sk, pk = sphincs.generate_keypair()
    msg = b"test message"
    sig = sphincs.sign(sk, msg)
    assert sphincs.verify(pk, msg, sig)
    logger.info(f"  SPHINCS+ signatures ({len(sig)} bytes)")

    # Test SHAKE256 VDF
    vdf = SHAKE256VDF()
    output, checkpoints = vdf.compute(b"test_input", 1000)
    assert len(output) == 32
    assert vdf.verify_sequential(sha3_256(b"test_input"), output, 1000)
    logger.info("  SHAKE256 VDF")

    # Test STARK prover (or fallback)
    stark = STARKProver()
    input_hash = sha3_256(b"test_input")
    proof = stark.generate_proof(input_hash, output, checkpoints, 1000)
    assert stark.verify_proof(input_hash, output, proof, 1000)
    logger.info(f"  STARK proof ({len(proof)} bytes)")

    # Test ML-KEM if available
    if MLKEM_AVAILABLE:
        try:
            mlkem = MLKEM("768")
            sk, pk = mlkem.generate_keypair()
            ct, ss1 = mlkem.encapsulate(pk)
            ss2 = mlkem.decapsulate(sk, ct)
            assert ss1 == ss2
            logger.info("  ML-KEM key encapsulation")
        except Exception as e:
            logger.warning(f"  ML-KEM test skipped: {e}")

    # Test PostQuantumCryptoProvider
    pq = PostQuantumCryptoProvider()
    sk, pk = pq.generate_keypair()
    sig = pq.sign(sk, b"test")
    assert pq.verify(pk, b"test", sig)
    logger.info("  PostQuantumCryptoProvider")

    # Test VDF through provider
    vdf_proof = pq.vdf_compute(b"provider_test", 500)
    assert pq.vdf_verify(vdf_proof)
    logger.info("  PQ VDF via provider")

    # Test VRF through provider
    beta, vrf_proof = pq.vrf_prove(sk, b"vrf_input")
    assert len(beta) == 32
    assert pq.vrf_verify(pk, b"vrf_input", beta, vrf_proof)
    logger.info("  PQ VRF via provider")

    logger.info("All post-quantum crypto tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
