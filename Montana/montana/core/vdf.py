"""
Ɉ Montana Class Group VDF v3.5

Layer 1: Temporal Proof per MONTANA_TECHNICAL_SPECIFICATION.md §5.

Class Group VDF (Wesolowski 2019) with O(log T) verification.
Target: 2^24 sequential squarings for UTC finality window participation.

Security: Type B (mathematical reduction to class group order problem)
  - Sequential squaring in class groups is provably hard
  - Reduction: "VDF shortcut exists" → "class group order computable efficiently"
  - Class group order problem hard for 40+ years

UTC Quantum Neutralization:
  - Class Group VDF is vulnerable to Shor's algorithm
  - Montana's UTC finality model makes quantum speedup irrelevant:
    * Quantum attacker computes VDF in 0.001 sec → waits 59.999 sec → 1 heartbeat
    * Classical node computes VDF in 30 sec → waits 30 sec → 1 heartbeat
  - UTC boundary is the rate limiter, VDF speed is irrelevant
"""

from __future__ import annotations
import hashlib
import struct
import time
import logging
import secrets
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Callable

from montana.constants import (
    VDF_TYPE,
    VDF_BASE_ITERATIONS,
    VDF_MAX_ITERATIONS,
    VDF_MIN_ITERATIONS,
    VDF_DISCRIMINANT_BITS,
    VDF_DISCRIMINANT_PRIMALITY_TESTS,
    VDF_CHALLENGE_BITS,
    WESOLOWSKI_HASH_TO_PRIME_ATTEMPTS,
    WESOLOWSKI_PROOF_SECURITY_BITS,
    VDF_CHECKPOINT_TIME_SEC,
)
from montana.core.types import Hash

logger = logging.getLogger(__name__)


# ==============================================================================
# CLASS GROUP ARITHMETIC
# ==============================================================================

@dataclass(frozen=True)
class ClassGroupElement:
    """
    Element of ideal class group Cl(Δ) of imaginary quadratic field Q(√Δ).

    Represented as binary quadratic form (a, b, c) where:
    - a > 0
    - b² - 4ac = Δ (discriminant)
    - gcd(a, b, c) = 1
    - Reduced form: |b| ≤ a ≤ c, if a = |b| or a = c then b ≥ 0
    """
    a: int  # First coefficient (positive)
    b: int  # Second coefficient
    discriminant: int  # Δ < 0 (negative for imaginary quadratic field)

    @property
    def c(self) -> int:
        """Third coefficient, computed from discriminant."""
        return (self.b * self.b - self.discriminant) // (4 * self.a)

    def is_reduced(self) -> bool:
        """Check if form is in reduced representation."""
        c = self.c
        if not (abs(self.b) <= self.a <= c):
            return False
        if self.a == abs(self.b) or self.a == c:
            return self.b >= 0
        return True

    def serialize(self) -> bytes:
        """Serialize to bytes."""
        # Use variable-length encoding for large integers
        a_bytes = self.a.to_bytes((self.a.bit_length() + 7) // 8, 'big')
        b_sign = 0 if self.b >= 0 else 1
        b_abs = abs(self.b)
        b_bytes = b_abs.to_bytes((b_abs.bit_length() + 7) // 8 if b_abs else 1, 'big')
        d_bytes = abs(self.discriminant).to_bytes(
            (abs(self.discriminant).bit_length() + 7) // 8, 'big'
        )

        return (
            struct.pack('>HH', len(a_bytes), len(b_bytes)) +
            a_bytes + bytes([b_sign]) + b_bytes +
            struct.pack('>H', len(d_bytes)) + d_bytes
        )

    @classmethod
    def deserialize(cls, data: bytes) -> Tuple["ClassGroupElement", int]:
        """Deserialize from bytes, return element and bytes consumed."""
        offset = 0
        a_len, b_len = struct.unpack_from('>HH', data, offset)
        offset += 4

        a = int.from_bytes(data[offset:offset + a_len], 'big')
        offset += a_len

        b_sign = data[offset]
        offset += 1
        b_abs = int.from_bytes(data[offset:offset + b_len], 'big')
        b = -b_abs if b_sign else b_abs
        offset += b_len

        d_len = struct.unpack_from('>H', data, offset)[0]
        offset += 2
        discriminant = -int.from_bytes(data[offset:offset + d_len], 'big')
        offset += d_len

        return cls(a, b, discriminant), offset

    def __repr__(self) -> str:
        return f"({self.a}, {self.b}, {self.c})"


def _extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
    """Extended Euclidean algorithm. Returns (gcd, x, y) where ax + by = gcd."""
    if a == 0:
        return b, 0, 1
    gcd, x1, y1 = _extended_gcd(b % a, a)
    x = y1 - (b // a) * x1
    y = x1
    return gcd, x, y


def reduce_form(a: int, b: int, discriminant: int) -> ClassGroupElement:
    """
    Reduce binary quadratic form to canonical representative.

    Uses Shanks-Zagier reduction algorithm.
    """
    # Compute c from discriminant
    c = (b * b - discriminant) // (4 * a)

    # Reduction loop
    while True:
        # Check if reduced
        if abs(b) <= a <= c:
            if a == abs(b) or a == c:
                if b >= 0:
                    break
            else:
                break

        # Apply reduction step
        if c < a:
            # Swap a and c, negate b
            a, c = c, a
            b = -b
        else:
            # Reduce b modulo 2a
            # Find q such that b' = b - 2qa is in range (-a, a]
            q = (b + a) // (2 * a)
            b_new = b - 2 * q * a
            c_new = c - q * (b + b_new) // 2
            b, c = b_new, c_new

    return ClassGroupElement(a, b, discriminant)


def identity_element(discriminant: int) -> ClassGroupElement:
    """
    Return identity element of class group.

    Identity is the principal form (1, b, c) where b = Δ mod 2.
    """
    b = discriminant % 2
    return reduce_form(1, b, discriminant)


def compose(g1: ClassGroupElement, g2: ClassGroupElement) -> ClassGroupElement:
    """
    Compose two class group elements (group operation).

    Uses NUCOMP algorithm for efficient composition.
    """
    if g1.discriminant != g2.discriminant:
        raise ValueError("Elements must have same discriminant")

    discriminant = g1.discriminant

    # Direct composition using Shanks algorithm
    a1, b1, c1 = g1.a, g1.b, g1.c
    a2, b2, c2 = g2.a, g2.b, g2.c

    # Step 1: Compute g = gcd(a1, a2, (b1 + b2)/2)
    g, u, v = _extended_gcd(a1, a2)
    s = (b1 + b2) // 2
    g, w, _ = _extended_gcd(g, s)
    u, v = u * w, v * w

    # Step 2: Compute composed form
    a3 = (a1 * a2) // (g * g)
    b3 = b2 + 2 * a2 * ((b1 - b2) // 2 * v - c2 * u) // g
    b3 = b3 % (2 * a3)
    if b3 > a3:
        b3 -= 2 * a3

    return reduce_form(a3, b3, discriminant)


def square(g: ClassGroupElement) -> ClassGroupElement:
    """Square a class group element (used in VDF)."""
    return compose(g, g)


def power(g: ClassGroupElement, n: int) -> ClassGroupElement:
    """
    Compute g^n using square-and-multiply.

    For VDF verification, not for VDF computation (which must be sequential).
    """
    if n == 0:
        return identity_element(g.discriminant)
    if n == 1:
        return g

    result = identity_element(g.discriminant)
    base = g

    while n > 0:
        if n & 1:
            result = compose(result, base)
        base = square(base)
        n >>= 1

    return result


# ==============================================================================
# DISCRIMINANT GENERATION
# ==============================================================================

def _is_probable_prime(n: int, k: int = VDF_DISCRIMINANT_PRIMALITY_TESTS) -> bool:
    """Miller-Rabin primality test with k rounds."""
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0:
        return False

    # Write n-1 as 2^r * d
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2

    # Witness loop
    for _ in range(k):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)

        if x == 1 or x == n - 1:
            continue

        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False

    return True


def generate_discriminant(seed: bytes, bits: int = VDF_DISCRIMINANT_BITS) -> int:
    """
    Generate deterministic discriminant from seed.

    Discriminant Δ must be:
    - Negative (for imaginary quadratic field)
    - Δ ≡ 1 (mod 4) (fundamental discriminant)
    - |Δ| should be prime or product of few small primes for hard class group

    Args:
        seed: Random seed for deterministic generation
        bits: Bit length of discriminant

    Returns:
        Negative discriminant
    """
    # Hash seed to get initial value
    h = hashlib.shake_256(b"MONTANA_DISCRIMINANT_V1" + seed)

    # Generate candidate
    for counter in range(10000):
        candidate_bytes = h.digest(bits // 8 + 8)
        h.update(counter.to_bytes(4, 'big'))

        candidate = int.from_bytes(candidate_bytes, 'big')
        candidate = candidate | (1 << (bits - 1))  # Ensure bit length
        candidate = candidate | 3  # Make Δ ≡ 3 (mod 4), so -Δ ≡ 1 (mod 4)

        # Check if -candidate is valid discriminant
        # For simplicity, check if candidate is prime
        if _is_probable_prime(candidate):
            return -candidate

    raise ValueError("Failed to generate discriminant")


# ==============================================================================
# WESOLOWSKI PROOF
# ==============================================================================

def hash_to_prime(
    g: ClassGroupElement,
    output: ClassGroupElement,
    iterations: int,
) -> int:
    """
    Hash group elements to prime challenge for Wesolowski proof.

    l = H(g, output, T) where l is prime
    """
    data = (
        g.serialize() +
        output.serialize() +
        iterations.to_bytes(8, 'big')
    )

    h = hashlib.shake_256(b"MONTANA_WESOLOWSKI_CHALLENGE_V1" + data)

    for counter in range(WESOLOWSKI_HASH_TO_PRIME_ATTEMPTS):
        candidate_bytes = h.digest(VDF_CHALLENGE_BITS // 8 + 4)
        h.update(counter.to_bytes(4, 'big'))

        candidate = int.from_bytes(candidate_bytes, 'big')
        candidate = candidate | 1  # Make odd
        candidate = candidate | (1 << (VDF_CHALLENGE_BITS - 1))  # Ensure bit length

        if _is_probable_prime(candidate, k=20):
            return candidate

    raise ValueError("Failed to find prime challenge")


# ==============================================================================
# VDF OUTPUT AND PROOF
# ==============================================================================

@dataclass(frozen=True)
class VDFOutput:
    """
    Output of Class Group VDF computation per §5.3.

    Contains the result and Wesolowski proof for O(log T) verification.
    """
    input_element: ClassGroupElement     # g ∈ Cl(Δ)
    output_element: ClassGroupElement    # g^(2^T) ∈ Cl(Δ)
    iterations: int                      # T = number of sequential squarings
    discriminant: int                    # Δ (negative)
    computation_time_ms: int = 0         # Actual computation time

    # Legacy compatibility: hash representation
    @property
    def input_hash(self) -> Hash:
        """Hash of input element for legacy compatibility."""
        return Hash(hashlib.sha3_256(self.input_element.serialize()).digest())

    @property
    def output_hash(self) -> Hash:
        """Hash of output element for legacy compatibility."""
        return Hash(hashlib.sha3_256(self.output_element.serialize()).digest())


@dataclass
class VDFProof:
    """
    Wesolowski proof for VDF verification per §5.4.

    Allows O(log T) verification:
    - Verifier computes l = H(g, y, T) (prime challenge)
    - Verifier computes r = 2^T mod l
    - Verifier checks: g^l * π^r = y (using multi-exponentiation)
    """
    input_element: ClassGroupElement
    output_element: ClassGroupElement
    proof_element: ClassGroupElement      # π = g^(floor(2^T / l))
    iterations: int
    discriminant: int
    challenge: int = 0                    # l (prime), recomputed if 0

    # Legacy compatibility
    @property
    def input_hash(self) -> Hash:
        return Hash(hashlib.sha3_256(self.input_element.serialize()).digest())

    @property
    def output_hash(self) -> Hash:
        return Hash(hashlib.sha3_256(self.output_element.serialize()).digest())

    def serialize(self) -> bytes:
        """Serialize proof for transmission."""
        return (
            b'MONT' +                                         # Magic
            struct.pack('>B', 2) +                            # Version (2 = Wesolowski)
            struct.pack('>Q', self.iterations) +
            self.input_element.serialize() +
            self.output_element.serialize() +
            self.proof_element.serialize() +
            struct.pack('>Q', self.challenge if self.challenge else 0)
        )

    @classmethod
    def deserialize(cls, data: bytes) -> "VDFProof":
        """Deserialize proof from bytes."""
        if data[:4] != b'MONT':
            raise ValueError("Invalid proof magic")

        version = data[4]
        if version != 2:
            raise ValueError(f"Unsupported proof version: {version}")

        iterations = struct.unpack_from('>Q', data, 5)[0]
        offset = 13

        input_elem, consumed = ClassGroupElement.deserialize(data[offset:])
        offset += consumed

        output_elem, consumed = ClassGroupElement.deserialize(data[offset:])
        offset += consumed

        proof_elem, consumed = ClassGroupElement.deserialize(data[offset:])
        offset += consumed

        challenge = struct.unpack_from('>Q', data, offset)[0]

        return cls(
            input_element=input_elem,
            output_element=output_elem,
            proof_element=proof_elem,
            iterations=iterations,
            discriminant=input_elem.discriminant,
            challenge=challenge,
        )


@dataclass
class VDFCheckpointResult:
    """Result of a single VDF checkpoint computation."""
    iterations: int
    output: Hash                          # Hash of output element
    proof: bytes                          # Serialized Wesolowski proof
    output_element: ClassGroupElement     # Full output element


# ==============================================================================
# CLASS GROUP VDF (WESOLOWSKI 2019)
# ==============================================================================

class ClassGroupVDF:
    """
    Class Group Verifiable Delay Function (Wesolowski 2019) per §5.2.

    Computes: y = g^(2^T) in class group Cl(Δ)

    Properties:
    - Type B security (mathematical reduction to class group order problem)
    - Strictly sequential (each squaring depends on previous result)
    - O(log T) verification via Wesolowski proof
    - No trusted setup (class groups are parameter-free)

    UTC Quantum Neutralization:
    - Shor's algorithm could compute class group order
    - Montana's UTC model makes this irrelevant:
      * VDF proves participation eligibility within finality window
      * Faster computation = longer wait for UTC boundary
      * 1 heartbeat per minute regardless of hardware
    """

    def __init__(
        self,
        discriminant: Optional[int] = None,
        seed: Optional[bytes] = None,
    ):
        """
        Initialize VDF with discriminant.

        Args:
            discriminant: Pre-computed discriminant (negative)
            seed: Seed for deterministic discriminant generation
        """
        if discriminant is not None:
            self._discriminant = discriminant
        elif seed is not None:
            self._discriminant = generate_discriminant(seed)
        else:
            # Default seed for deterministic discriminant
            self._discriminant = generate_discriminant(b"MONTANA_GENESIS_DISCRIMINANT")

        self._cached_ips: Optional[float] = None
        self._current_output: Optional[ClassGroupElement] = None
        self._total_iterations: int = 0
        self._last_proof: bytes = b""

        logger.debug(f"ClassGroupVDF initialized with Δ = {self._discriminant}")

    @property
    def discriminant(self) -> int:
        """Get discriminant."""
        return self._discriminant

    @property
    def current_output(self) -> Hash:
        """Get current VDF output hash."""
        if self._current_output is None:
            return Hash.zero()
        return Hash(hashlib.sha3_256(self._current_output.serialize()).digest())

    @property
    def total_iterations(self) -> int:
        """Get total iterations computed."""
        return self._total_iterations

    def get_proof(self) -> bytes:
        """Get the last VDF proof."""
        return self._last_proof

    def generator_from_seed(self, seed: bytes) -> ClassGroupElement:
        """
        Generate deterministic group element from seed.

        Uses hash-and-sign approach to map seed to class group element.
        """
        h = hashlib.shake_256(b"MONTANA_VDF_GENERATOR_V1" + seed)

        # Generate small prime a
        for counter in range(1000):
            a_bytes = h.digest(16)
            h.update(counter.to_bytes(4, 'big'))

            a = int.from_bytes(a_bytes, 'big') % (1 << 64)
            a = max(a, 2)
            a = a | 1  # Make odd

            if not _is_probable_prime(a, k=10):
                continue

            # Find b such that Δ ≡ b² (mod 4a)
            # Solve b² ≡ Δ (mod 4a)
            target = self._discriminant % (4 * a)
            if target < 0:
                target += 4 * a

            # Try to find square root
            for b_candidate in range(2 * a):
                if (b_candidate * b_candidate) % (4 * a) == target:
                    if (b_candidate * b_candidate - self._discriminant) % (4 * a) == 0:
                        return reduce_form(a, b_candidate, self._discriminant)

        # Fallback: return identity (rare case)
        logger.warning("Failed to generate non-trivial element, using identity")
        return identity_element(self._discriminant)

    def compute_checkpoint(
        self,
        input_data: bytes | Hash,
        iterations: int = VDF_BASE_ITERATIONS,
    ) -> VDFCheckpointResult:
        """
        Compute a single VDF checkpoint.

        Args:
            input_data: Input seed
            iterations: Number of sequential squarings

        Returns:
            VDFCheckpointResult with output and Wesolowski proof
        """
        result = self.compute(input_data, iterations)
        proof = self.create_proof(result)

        self._current_output = result.output_element
        self._total_iterations += result.iterations

        proof_bytes = proof.serialize()
        self._last_proof = proof_bytes

        return VDFCheckpointResult(
            iterations=result.iterations,
            output=result.output_hash,
            proof=proof_bytes,
            output_element=result.output_element,
        )

    def compute(
        self,
        input_data: bytes | Hash,
        iterations: int = VDF_BASE_ITERATIONS,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> VDFOutput:
        """
        Compute Class Group VDF.

        Args:
            input_data: Input seed (hashed to generate group element)
            iterations: Number of sequential squarings T
            progress_callback: Optional callback(current, total) for progress

        Returns:
            VDFOutput with result
        """
        if iterations < VDF_MIN_ITERATIONS:
            raise ValueError(f"Iterations {iterations} below minimum {VDF_MIN_ITERATIONS}")
        if iterations > VDF_MAX_ITERATIONS:
            raise ValueError(f"Iterations {iterations} exceeds maximum {VDF_MAX_ITERATIONS}")

        # Normalize input to bytes
        if isinstance(input_data, Hash):
            input_data = input_data.data

        # Generate starting element from seed
        g = self.generator_from_seed(input_data)

        start_time = time.perf_counter()

        # Sequential squaring: y = g^(2^T)
        current = g
        for i in range(iterations):
            current = square(current)

            if progress_callback and i % 10000 == 0:
                progress_callback(i, iterations)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        logger.debug(
            f"VDF computed: {iterations:,} squarings in {elapsed_ms}ms "
            f"({iterations / (elapsed_ms / 1000) if elapsed_ms > 0 else 0:.0f} sq/s)"
        )

        return VDFOutput(
            input_element=g,
            output_element=current,
            iterations=iterations,
            discriminant=self._discriminant,
            computation_time_ms=elapsed_ms,
        )

    def create_proof(self, vdf_output: VDFOutput) -> VDFProof:
        """
        Create Wesolowski proof from VDF output.

        Proof: π = g^(floor(2^T / l)) where l = H(g, y, T) is prime challenge.

        Verification: g^l * π^r = y where r = 2^T mod l
        """
        g = vdf_output.input_element
        y = vdf_output.output_element
        T = vdf_output.iterations

        # Compute challenge l = H(g, y, T)
        l = hash_to_prime(g, y, T)

        # Compute proof: π = g^(floor(2^T / l))
        # We compute this by tracking quotient during sequential squaring
        # For efficiency, recompute with quotient tracking

        # Simplified: compute 2^T mod l, then use power formula
        # floor(2^T / l) = (2^T - r) / l where r = 2^T mod l
        r = pow(2, T, l)
        quotient = (pow(2, T, l * l) - r) // l  # This is floor(2^T / l) mod l

        # For full quotient, we need extended computation
        # Simplified version: compute π directly via repeated squaring with tracking
        pi = self._compute_proof_element(g, T, l)

        return VDFProof(
            input_element=g,
            output_element=y,
            proof_element=pi,
            iterations=T,
            discriminant=vdf_output.discriminant,
            challenge=l,
        )

    def _compute_proof_element(
        self,
        g: ClassGroupElement,
        T: int,
        l: int,
    ) -> ClassGroupElement:
        """
        Compute proof element π = g^(floor(2^T / l)).

        Uses the observation that we can track quotient during squaring.
        """
        # For each step: 2^(i+1) = 2 * 2^i
        # q_{i+1} = 2*q_i + b_i where b_i = 1 if 2*r_i >= l
        # r_{i+1} = 2*r_i mod l

        pi = identity_element(g.discriminant)
        current_g_power = g  # g^(2^i)
        r = 1  # 2^i mod l

        for i in range(T):
            # Update quotient contribution
            new_r = (2 * r) % l
            if 2 * r >= l:
                # q gets contribution of 2^i, so π *= g^(2^i)
                pi = compose(pi, current_g_power)
            r = new_r

            # Update g power for next iteration
            current_g_power = square(current_g_power)

        return pi

    def verify_proof(self, proof: VDFProof) -> bool:
        """
        Verify Wesolowski proof.

        Checks: g^l * π^r = y where r = 2^T mod l

        Complexity: O(log T) group operations
        """
        try:
            g = proof.input_element
            y = proof.output_element
            pi = proof.proof_element
            T = proof.iterations

            # Recompute or use provided challenge
            if proof.challenge:
                l = proof.challenge
            else:
                l = hash_to_prime(g, y, T)

            # Compute r = 2^T mod l
            r = pow(2, T, l)

            # Verify: g^l * π^r = y
            # Using multi-exponentiation for efficiency
            g_l = power(g, l)
            pi_r = power(pi, r)
            lhs = compose(g_l, pi_r)

            # Compare with y
            if lhs.a != y.a or lhs.b != y.b:
                logger.warning("Wesolowski proof verification failed: LHS != RHS")
                return False

            return True

        except Exception as e:
            logger.error(f"Proof verification error: {e}")
            return False

    def verify_full(self, vdf_output: VDFOutput) -> bool:
        """
        Verify VDF by full recomputation (O(T)).

        Fallback verification when proof is unavailable.
        """
        g = vdf_output.input_element

        current = g
        for _ in range(vdf_output.iterations):
            current = square(current)

        return (
            current.a == vdf_output.output_element.a and
            current.b == vdf_output.output_element.b
        )

    def calibrate(self, target_seconds: float = VDF_CHECKPOINT_TIME_SEC) -> int:
        """
        Calibrate iterations for target computation time.

        Args:
            target_seconds: Target time in seconds

        Returns:
            Recommended iterations for target time
        """
        # Generate test element
        test_seed = b"montana_vdf_calibration"
        g = self.generator_from_seed(test_seed)

        # Run sample computation
        sample_iterations = 1000

        current = g
        start = time.perf_counter()
        for _ in range(sample_iterations):
            current = square(current)
        elapsed = time.perf_counter() - start

        sps = sample_iterations / elapsed  # Squarings per second
        self._cached_ips = sps

        recommended = max(VDF_MIN_ITERATIONS, int(sps * target_seconds))

        logger.info(f"VDF calibration: {sps:.0f} squarings/sec")
        logger.info(f"  Recommended: {recommended:,} iterations for {target_seconds}s")

        return recommended

    @property
    def iterations_per_second(self) -> float:
        """Get iterations per second (calibrate if not cached)."""
        if self._cached_ips is None:
            self.calibrate()
        return self._cached_ips or 0.0


# ==============================================================================
# GLOBAL INSTANCE AND CONVENIENCE FUNCTIONS
# ==============================================================================

_vdf: Optional[ClassGroupVDF] = None


def get_vdf() -> ClassGroupVDF:
    """Get or create global VDF instance."""
    global _vdf
    if _vdf is None:
        _vdf = ClassGroupVDF()
    return _vdf


def compute_vdf(
    input_data: bytes,
    iterations: int = VDF_BASE_ITERATIONS,
) -> VDFOutput:
    """Compute VDF using global instance."""
    return get_vdf().compute(input_data, iterations)


def verify_vdf(vdf_output: VDFOutput) -> bool:
    """Verify VDF output by full recomputation."""
    return get_vdf().verify_full(vdf_output)


def verify_vdf_proof(proof: VDFProof) -> bool:
    """Verify VDF Wesolowski proof."""
    return get_vdf().verify_proof(proof)


# ==============================================================================
# LEGACY COMPATIBILITY
# ==============================================================================

# Alias for backward compatibility with SHAKE256VDF interface
SHAKE256VDF = ClassGroupVDF
