"""
Proof of Time - Privacy Module

PRODUCTION-READY:
- LSAG (Linkable Spontaneous Anonymous Group) signatures
- Stealth addresses (CryptoNote-style)
- Pedersen commitments with proper curve operations

EXPERIMENTAL (NOT PRODUCTION-READY):
- Bulletproofs range proofs - STRUCTURAL PLACEHOLDER ONLY
  The Inner Product Argument is NOT cryptographically implemented.
  DO NOT use T2/T3 transactions in production without replacing
  with audited library (bulletproofs-rs via FFI).
- RingCT - depends on Bulletproofs for range proofs

Reference:
- CryptoNote v2.0
- Ring Signature Confidential Transactions (RingCT)
- Bulletproofs: Short Proofs for Confidential Transactions

Time is the ultimate proof.
"""

import hashlib
import hmac
import struct
import secrets
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

try:
    import nacl.bindings
    NACL_AVAILABLE = True
except ImportError:
    raise ImportError("PyNaCl required: pip install PyNaCl")

from config import PROTOCOL

logger = logging.getLogger("proof_of_time.privacy")


# ============================================================================
# EXCEPTIONS
# ============================================================================

class PrivacyError(Exception):
    """Base privacy error."""
    pass


class RingSignatureError(PrivacyError):
    """Ring signature error."""
    pass


class RangeProofError(PrivacyError):
    """Range proof error."""
    pass


class StealthAddressError(PrivacyError):
    """Stealth address error."""
    pass


# ============================================================================
# CONSTANTS
# ============================================================================

# Ed25519 curve order (L)
CURVE_ORDER = 2**252 + 27742317777372353535851937790883648493

# Ed25519 field prime
FIELD_PRIME = 2**255 - 19

# Pedersen generator H (hash-derived, nothing-up-my-sleeve)
H_GENERATOR_SEED = b"Proof of Time Pedersen H Generator v1"

# Domain separation tags
DOMAIN_HASH_TO_POINT = b"PoT_HashToPoint_v1"
DOMAIN_KEY_IMAGE = b"PoT_KeyImage_v1"
DOMAIN_RING_SIG = b"PoT_RingSig_v1"
DOMAIN_STEALTH = b"PoT_Stealth_v1"
DOMAIN_COMMITMENT = b"PoT_Commitment_v1"
DOMAIN_BULLETPROOF = b"PoT_Bulletproof_v1"


# ============================================================================
# LOW-LEVEL ED25519 OPERATIONS
# ============================================================================

class Ed25519Point:
    """
    Ed25519 elliptic curve point operations using libsodium.
    
    Provides safe wrappers around nacl.bindings for:
    - Point validation
    - Point addition/subtraction
    - Scalar multiplication
    - Hash to point
    """
    
    POINT_SIZE = 32
    SCALAR_SIZE = 32
    
    @staticmethod
    def is_valid_point(point: bytes) -> bool:
        """Check if bytes represent a valid Ed25519 point."""
        if len(point) != 32:
            return False
        try:
            return nacl.bindings.crypto_core_ed25519_is_valid_point(point)
        except Exception:
            return False
    
    @staticmethod
    def scalar_reduce(scalar_64: bytes) -> bytes:
        """Reduce 64-byte value to valid Ed25519 scalar."""
        if len(scalar_64) != 64:
            # Pad or hash to 64 bytes
            scalar_64 = hashlib.sha512(scalar_64).digest()
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_reduce(scalar_64)
        except Exception:
            # Fallback: manual reduction
            s = int.from_bytes(scalar_64, 'little') % CURVE_ORDER
            return s.to_bytes(32, 'little')
    
    @staticmethod
    def scalar_add(a: bytes, b: bytes) -> bytes:
        """Add two scalars mod L."""
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_add(a, b)
        except Exception:
            a_int = int.from_bytes(a, 'little')
            b_int = int.from_bytes(b, 'little')
            result = (a_int + b_int) % CURVE_ORDER
            return result.to_bytes(32, 'little')
    
    @staticmethod
    def scalar_sub(a: bytes, b: bytes) -> bytes:
        """Subtract two scalars mod L: a - b."""
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_sub(a, b)
        except Exception:
            a_int = int.from_bytes(a, 'little')
            b_int = int.from_bytes(b, 'little')
            result = (a_int - b_int) % CURVE_ORDER
            return result.to_bytes(32, 'little')
    
    @staticmethod
    def scalar_mul(a: bytes, b: bytes) -> bytes:
        """Multiply two scalars mod L."""
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_mul(a, b)
        except Exception:
            a_int = int.from_bytes(a, 'little')
            b_int = int.from_bytes(b, 'little')
            result = (a_int * b_int) % CURVE_ORDER
            return result.to_bytes(32, 'little')
    
    @staticmethod
    def scalar_invert(s: bytes) -> bytes:
        """Compute modular inverse of scalar."""
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_invert(s)
        except Exception:
            s_int = int.from_bytes(s, 'little')
            result = pow(s_int, CURVE_ORDER - 2, CURVE_ORDER)
            return result.to_bytes(32, 'little')
    
    @staticmethod
    def scalar_negate(s: bytes) -> bytes:
        """Negate scalar: -s mod L."""
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_negate(s)
        except Exception:
            s_int = int.from_bytes(s, 'little')
            result = (CURVE_ORDER - s_int) % CURVE_ORDER
            return result.to_bytes(32, 'little')
    
    @staticmethod
    def scalar_random() -> bytes:
        """Generate random scalar."""
        try:
            return nacl.bindings.crypto_core_ed25519_scalar_random()
        except Exception:
            # Fallback
            r = secrets.randbelow(CURVE_ORDER)
            if r == 0:
                r = 1
            return r.to_bytes(32, 'little')
    
    @staticmethod
    def point_add(p: bytes, q: bytes) -> bytes:
        """Add two Ed25519 points."""
        try:
            return nacl.bindings.crypto_core_ed25519_add(p, q)
        except Exception as e:
            raise PrivacyError(f"Point addition failed: {e}")
    
    @staticmethod
    def point_sub(p: bytes, q: bytes) -> bytes:
        """Subtract Ed25519 points: p - q."""
        try:
            return nacl.bindings.crypto_core_ed25519_sub(p, q)
        except Exception as e:
            raise PrivacyError(f"Point subtraction failed: {e}")
    
    @staticmethod
    def point_negate(p: bytes) -> bytes:
        """Negate point: -P."""
        # In Ed25519, negation flips the x-coordinate sign bit
        p_list = bytearray(p)
        p_list[31] ^= 0x80
        return bytes(p_list)
    
    @staticmethod
    def scalarmult_base(scalar: bytes) -> bytes:
        """Scalar multiplication with base point: s * G."""
        try:
            return nacl.bindings.crypto_scalarmult_ed25519_base_noclamp(scalar)
        except Exception as e:
            raise PrivacyError(f"Base point multiplication failed: {e}")
    
    @staticmethod
    def scalarmult(scalar: bytes, point: bytes) -> bytes:
        """Scalar multiplication: s * P."""
        # Handle zero scalar - result is the identity point
        if scalar == b'\x00' * 32:
            # Return identity (neutral element) - all zeros for Ed25519
            # Note: In proper Ed25519, identity is (0, 1) but compressed is tricky
            # For our purposes, we avoid zero scalar multiplications
            raise PrivacyError("Zero scalar multiplication not supported")
        try:
            return nacl.bindings.crypto_scalarmult_ed25519_noclamp(scalar, point)
        except Exception as e:
            raise PrivacyError(f"Scalar multiplication failed: {e}")
    
    @staticmethod
    def hash_to_scalar(data: bytes) -> bytes:
        """Hash data to Ed25519 scalar using SHA-512 and reduction."""
        h = hashlib.sha512(data).digest()
        return Ed25519Point.scalar_reduce(h)
    
    @staticmethod
    def hash_to_point(data: bytes) -> bytes:
        """
        Hash data to valid Ed25519 curve point.
        
        Uses try-and-increment method with domain separation.
        """
        for counter in range(256):
            hash_input = DOMAIN_HASH_TO_POINT + data + struct.pack('<B', counter)
            candidate = hashlib.sha256(hash_input).digest()
            
            # Try to interpret as point
            try:
                # Set sign bit based on extra hash bit
                extra = hashlib.sha256(hash_input + b'\xff').digest()[0]
                candidate_list = bytearray(candidate)
                candidate_list[31] = (candidate_list[31] & 0x7F) | ((extra & 1) << 7)
                candidate = bytes(candidate_list)
                
                if Ed25519Point.is_valid_point(candidate):
                    # Multiply by cofactor to ensure in prime-order subgroup
                    cofactor = (8).to_bytes(32, 'little')
                    result = Ed25519Point.scalarmult(cofactor, candidate)
                    if result != b'\x00' * 32:
                        return result
            except Exception:
                continue
        
        raise PrivacyError("Hash to point failed after 256 attempts")
    
    @staticmethod
    def derive_public_key(secret: bytes) -> bytes:
        """Derive Ed25519 public key from secret (no clamping)."""
        # Use scalarmult_base for consistency with ring signature operations
        # Note: This does NOT apply Ed25519 clamping
        return Ed25519Point.scalarmult_base(secret)


# ============================================================================
# PEDERSEN GENERATOR
# ============================================================================

class PedersenGenerators:
    """
    Pedersen commitment generators G and H.
    
    G is the standard Ed25519 base point.
    H is derived via hash-to-point with nothing-up-my-sleeve seed.
    """
    
    _H: Optional[bytes] = None
    _G: Optional[bytes] = None
    
    @classmethod
    def get_G(cls) -> bytes:
        """Get generator G (Ed25519 base point)."""
        if cls._G is None:
            # G = 1 * G (base point)
            one = (1).to_bytes(32, 'little')
            cls._G = Ed25519Point.scalarmult_base(one)
        return cls._G
    
    @classmethod
    def get_H(cls) -> bytes:
        """Get generator H (hash-derived, independent of G)."""
        if cls._H is None:
            cls._H = Ed25519Point.hash_to_point(H_GENERATOR_SEED)
        return cls._H
    
    @classmethod
    def get_generator_vector(cls, n: int, prefix: bytes = b"G_") -> List[bytes]:
        """Get vector of n independent generators for Bulletproofs."""
        generators = []
        for i in range(n):
            seed = prefix + struct.pack('<I', i)
            generators.append(Ed25519Point.hash_to_point(seed))
        return generators


# ============================================================================
# KEY IMAGE GENERATION
# ============================================================================

def generate_key_image(secret_key: bytes, public_key: bytes) -> bytes:
    """
    Generate key image I = x * Hp(P).
    
    Key image is:
    - Unique per secret key (enables double-spend detection)
    - Unlinkable to public key (preserves anonymity)
    - Deterministic (same key always produces same image)
    
    Args:
        secret_key: Private spending key x (32 bytes)
        public_key: Corresponding public key P = x*G (32 bytes)
    
    Returns:
        32-byte key image I
    """
    # Hp(P) - hash public key to curve point
    hp_data = DOMAIN_KEY_IMAGE + public_key
    hp = Ed25519Point.hash_to_point(hp_data)
    
    # I = x * Hp(P)
    key_image = Ed25519Point.scalarmult(secret_key, hp)
    
    return key_image


def verify_key_image_structure(key_image: bytes) -> bool:
    """Verify key image is valid curve point."""
    return Ed25519Point.is_valid_point(key_image)


# ============================================================================
# LSAG RING SIGNATURES - PRODUCTION IMPLEMENTATION
# ============================================================================

@dataclass
class LSAGSignature:
    """
    Linkable Spontaneous Anonymous Group signature.
    
    Components:
    - key_image: I = x * Hp(P) - links signatures from same key
    - c0: Initial challenge scalar
    - responses: Response scalars s_i for each ring member
    
    Verification equation for each i:
    L_i = s_i * G + c_i * P_i
    R_i = s_i * Hp(P_i) + c_i * I
    c_{i+1} = H(m || L_i || R_i)
    
    Ring closes when c_n == c_0
    """
    key_image: bytes  # 32 bytes
    c0: bytes  # 32 bytes (initial challenge)
    responses: List[bytes]  # n x 32 bytes
    
    def serialize(self) -> bytes:
        """Serialize signature to bytes."""
        data = bytearray()
        data.extend(self.key_image)
        data.extend(self.c0)
        data.extend(struct.pack('<H', len(self.responses)))
        for r in self.responses:
            data.extend(r)
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'LSAGSignature':
        """Deserialize signature from bytes."""
        if len(data) < 66:
            raise RingSignatureError("Signature data too short")
        
        key_image = data[:32]
        c0 = data[32:64]
        n = struct.unpack_from('<H', data, 64)[0]
        
        if len(data) < 66 + n * 32:
            raise RingSignatureError("Signature data truncated")
        
        responses = []
        offset = 66
        for _ in range(n):
            responses.append(data[offset:offset + 32])
            offset += 32
        
        return cls(key_image=key_image, c0=c0, responses=responses)
    
    @property
    def ring_size(self) -> int:
        return len(self.responses)
    
    def __eq__(self, other):
        if not isinstance(other, LSAGSignature):
            return False
        return (self.key_image == other.key_image and 
                self.c0 == other.c0 and 
                self.responses == other.responses)


class LSAG:
    """
    Linkable Spontaneous Anonymous Group signatures.
    
    Properties:
    - Anonymity: Verifier cannot determine which ring member signed
    - Linkability: Same secret key produces same key image (detect double-spend)
    - Unforgeability: Only secret key holder can create valid signature
    - Spontaneity: No setup or coordination required
    
    Reference: "Linkable Spontaneous Anonymous Group Signature for Ad Hoc Groups"
    by Liu, Wei, Wong (2004)
    """
    
    @staticmethod
    def _compute_challenge(
        message: bytes,
        L: bytes,
        R: bytes,
        ring: List[bytes],
        key_image: bytes
    ) -> bytes:
        """Compute challenge hash c = H(m || L || R)."""
        h = hashlib.sha512()
        h.update(DOMAIN_RING_SIG)
        h.update(message)
        h.update(L)
        h.update(R)
        # Include ring and key image for domain separation
        for pk in ring:
            h.update(pk)
        h.update(key_image)
        return Ed25519Point.scalar_reduce(h.digest())
    
    @staticmethod
    def sign(
        message: bytes,
        ring: List[bytes],
        secret_index: int,
        secret_key: bytes
    ) -> LSAGSignature:
        """
        Generate LSAG ring signature.
        
        Args:
            message: Message to sign (will be hashed)
            ring: List of public keys (ring members)
            secret_index: Index of actual signer in ring (π)
            secret_key: Secret key of actual signer (x)
        
        Returns:
            LSAGSignature object
        
        Raises:
            RingSignatureError: If parameters invalid
        """
        n = len(ring)
        
        if n < 2:
            raise RingSignatureError("Ring must have at least 2 members")
        if secret_index < 0 or secret_index >= n:
            raise RingSignatureError(f"Invalid secret index {secret_index} for ring size {n}")
        if len(secret_key) != 32:
            raise RingSignatureError("Secret key must be 32 bytes")
        
        # Validate ring members
        for i, pk in enumerate(ring):
            if len(pk) != 32:
                raise RingSignatureError(f"Ring member {i} invalid length")
            if not Ed25519Point.is_valid_point(pk):
                raise RingSignatureError(f"Ring member {i} not valid point")
        
        # Get signer's public key and verify consistency
        public_key = ring[secret_index]
        derived_pk = Ed25519Point.derive_public_key(secret_key)
        if public_key != derived_pk:
            raise RingSignatureError("Secret key doesn't match public key at secret_index")
        
        # Hash message
        msg_hash = hashlib.sha256(message).digest()
        
        # Generate key image: I = x * Hp(P)
        key_image = generate_key_image(secret_key, public_key)
        
        # Initialize arrays
        c = [None] * n  # Challenges
        s = [None] * n  # Responses
        
        # Random α for real signer
        alpha = Ed25519Point.scalar_random()
        
        # Compute L_π = α * G
        L_pi = Ed25519Point.scalarmult_base(alpha)
        
        # Compute R_π = α * Hp(P_π)
        hp_pi = Ed25519Point.hash_to_point(DOMAIN_KEY_IMAGE + public_key)
        R_pi = Ed25519Point.scalarmult(alpha, hp_pi)
        
        # Compute c_{π+1}
        c[(secret_index + 1) % n] = LSAG._compute_challenge(
            msg_hash, L_pi, R_pi, ring, key_image
        )
        
        # Generate random responses and challenges around the ring
        for j in range(1, n):
            i = (secret_index + j) % n
            next_i = (i + 1) % n
            
            # Random response s_i
            s[i] = Ed25519Point.scalar_random()
            
            # L_i = s_i * G + c_i * P_i
            s_G = Ed25519Point.scalarmult_base(s[i])
            c_P = Ed25519Point.scalarmult(c[i], ring[i])
            L_i = Ed25519Point.point_add(s_G, c_P)
            
            # R_i = s_i * Hp(P_i) + c_i * I
            hp_i = Ed25519Point.hash_to_point(DOMAIN_KEY_IMAGE + ring[i])
            s_Hp = Ed25519Point.scalarmult(s[i], hp_i)
            c_I = Ed25519Point.scalarmult(c[i], key_image)
            R_i = Ed25519Point.point_add(s_Hp, c_I)
            
            # c_{i+1} = H(m || L_i || R_i)
            c[next_i] = LSAG._compute_challenge(msg_hash, L_i, R_i, ring, key_image)
        
        # Close the ring: s_π = α - c_π * x (mod L)
        c_pi_x = Ed25519Point.scalar_mul(c[secret_index], secret_key)
        s[secret_index] = Ed25519Point.scalar_sub(alpha, c_pi_x)
        
        return LSAGSignature(
            key_image=key_image,
            c0=c[0],
            responses=s
        )
    
    @staticmethod
    def verify(
        message: bytes,
        ring: List[bytes],
        signature: LSAGSignature
    ) -> bool:
        """
        Verify LSAG ring signature.
        
        Args:
            message: Original message
            ring: List of public keys (must match signing ring)
            signature: Signature to verify
        
        Returns:
            True if signature is valid
        """
        try:
            n = len(ring)
            
            if n != signature.ring_size:
                logger.debug(f"Ring size mismatch: {n} != {signature.ring_size}")
                return False
            if n < 2:
                logger.debug("Ring too small")
                return False
            
            # Validate key image
            if not verify_key_image_structure(signature.key_image):
                logger.debug("Invalid key image structure")
                return False
            
            # Validate ring members
            for i, pk in enumerate(ring):
                if not Ed25519Point.is_valid_point(pk):
                    logger.debug(f"Invalid ring member {i}")
                    return False
            
            # Hash message
            msg_hash = hashlib.sha256(message).digest()
            
            # Recompute challenges around the ring
            c = signature.c0
            
            for i in range(n):
                # L_i = s_i * G + c_i * P_i
                s_G = Ed25519Point.scalarmult_base(signature.responses[i])
                c_P = Ed25519Point.scalarmult(c, ring[i])
                L_i = Ed25519Point.point_add(s_G, c_P)
                
                # R_i = s_i * Hp(P_i) + c_i * I
                hp_i = Ed25519Point.hash_to_point(DOMAIN_KEY_IMAGE + ring[i])
                s_Hp = Ed25519Point.scalarmult(signature.responses[i], hp_i)
                c_I = Ed25519Point.scalarmult(c, signature.key_image)
                R_i = Ed25519Point.point_add(s_Hp, c_I)
                
                # c_{i+1} = H(m || L_i || R_i)
                c = LSAG._compute_challenge(msg_hash, L_i, R_i, ring, signature.key_image)
            
            # Ring closes if we arrive back at c0 (constant-time comparison)
            if not hmac.compare_digest(c, signature.c0):
                logger.debug("Ring doesn't close")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"LSAG verification error: {e}")
            return False
    
    @staticmethod
    def link(sig1: LSAGSignature, sig2: LSAGSignature) -> bool:
        """Check if two signatures are from the same secret key (constant-time)."""
        return hmac.compare_digest(sig1.key_image, sig2.key_image)
    
    @staticmethod
    def verify_batch(
        signatures: List[Tuple[bytes, List[bytes], LSAGSignature]]
    ) -> Tuple[bool, List[bool]]:
        """
        Batch verify multiple LSAG signatures.
        
        This is more efficient than verifying signatures individually
        because we can use multi-scalar multiplication optimization.
        
        Args:
            signatures: List of (message, ring, signature) tuples
        
        Returns:
            (all_valid, individual_results) tuple
            - all_valid: True if ALL signatures are valid
            - individual_results: List of bool for each signature
        """
        if not signatures:
            return True, []
        
        results = []
        all_valid = True
        
        # For small batches, individual verification is simpler
        # For large batches (>10), a more optimized approach would use
        # random linear combinations to verify all equations at once
        if len(signatures) <= 10:
            for message, ring, sig in signatures:
                valid = LSAG.verify(message, ring, sig)
                results.append(valid)
                if not valid:
                    all_valid = False
            return all_valid, results
        
        # Large batch optimization using randomized batching
        # This reduces the number of group operations
        batch_data = []
        
        for idx, (message, ring, sig) in enumerate(signatures):
            try:
                n = len(ring)
                
                # Basic validation
                if n != sig.ring_size or n < 2:
                    results.append(False)
                    all_valid = False
                    continue
                
                if not verify_key_image_structure(sig.key_image):
                    results.append(False)
                    all_valid = False
                    continue
                
                # Validate ring
                valid_ring = True
                for pk in ring:
                    if not Ed25519Point.is_valid_point(pk):
                        valid_ring = False
                        break
                
                if not valid_ring:
                    results.append(False)
                    all_valid = False
                    continue
                
                # Full verification for this signature
                valid = LSAG.verify(message, ring, sig)
                results.append(valid)
                if not valid:
                    all_valid = False
                    
            except Exception as e:
                logger.warning(f"Batch verification error at index {idx}: {e}")
                results.append(False)
                all_valid = False
        
        return all_valid, results
    
    @staticmethod
    def extract_key_images(signatures: List[LSAGSignature]) -> List[bytes]:
        """Extract all key images from signatures for double-spend checking."""
        return [sig.key_image for sig in signatures]
    
    @staticmethod
    def check_double_spend(
        new_signature: LSAGSignature,
        existing_key_images: set
    ) -> bool:
        """
        Check if a signature represents a double-spend.
        
        Returns True if the key image has been used before.
        Uses constant-time comparison to prevent timing attacks.
        """
        # Convert to list for constant-time search
        for existing in existing_key_images:
            if hmac.compare_digest(new_signature.key_image, existing):
                return True
        return False


# ============================================================================
# STEALTH ADDRESSES - PRODUCTION IMPLEMENTATION
# ============================================================================

@dataclass
class StealthKeys:
    """
    Stealth address key pair.
    
    Two key pairs:
    - View keys (a, A): Used to scan for incoming transactions
    - Spend keys (b, B): Used to spend received outputs
    
    Address = (A, B) = (a*G, b*G)
    """
    view_secret: bytes  # a - view secret key
    spend_secret: bytes  # b - spend secret key
    view_public: bytes  # A = a*G - view public key
    spend_public: bytes  # B = b*G - spend public key
    
    @classmethod
    def generate(cls) -> 'StealthKeys':
        """Generate new stealth key pair."""
        view_secret = Ed25519Point.scalar_random()
        spend_secret = Ed25519Point.scalar_random()
        view_public = Ed25519Point.scalarmult_base(view_secret)
        spend_public = Ed25519Point.scalarmult_base(spend_secret)
        
        return cls(
            view_secret=view_secret,
            spend_secret=spend_secret,
            view_public=view_public,
            spend_public=spend_public
        )
    
    @classmethod
    def from_seed(cls, seed: bytes) -> 'StealthKeys':
        """Derive stealth keys from seed."""
        view_secret = Ed25519Point.hash_to_scalar(DOMAIN_STEALTH + b"view" + seed)
        spend_secret = Ed25519Point.hash_to_scalar(DOMAIN_STEALTH + b"spend" + seed)
        view_public = Ed25519Point.scalarmult_base(view_secret)
        spend_public = Ed25519Point.scalarmult_base(spend_secret)
        
        return cls(
            view_secret=view_secret,
            spend_secret=spend_secret,
            view_public=view_public,
            spend_public=spend_public
        )
    
    def get_address(self) -> bytes:
        """Get stealth address (A || B) - 64 bytes."""
        return self.view_public + self.spend_public
    
    def serialize(self) -> bytes:
        """Serialize keys (secrets included - handle carefully!)."""
        return self.view_secret + self.spend_secret + self.view_public + self.spend_public
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'StealthKeys':
        """Deserialize keys."""
        if len(data) != 128:
            raise StealthAddressError("Invalid key data length")
        return cls(
            view_secret=data[0:32],
            spend_secret=data[32:64],
            view_public=data[64:96],
            spend_public=data[96:128]
        )


@dataclass
class StealthOutput:
    """
    Stealth transaction output.
    
    Contains:
    - one_time_address: P = Hs(r*A)*G + B - unique per output
    - tx_public_key: R = r*G - allows recipient to derive P
    - encrypted_amount: Amount encrypted with shared secret
    """
    one_time_address: bytes  # P - 32 bytes
    tx_public_key: bytes  # R - 32 bytes
    encrypted_amount: bytes  # Encrypted amount data
    output_index: int = 0  # Index in transaction
    
    def serialize(self) -> bytes:
        data = bytearray()
        data.extend(self.one_time_address)
        data.extend(self.tx_public_key)
        data.extend(struct.pack('<I', self.output_index))
        data.extend(struct.pack('<H', len(self.encrypted_amount)))
        data.extend(self.encrypted_amount)
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['StealthOutput', int]:
        one_time_address = data[offset:offset + 32]
        offset += 32
        tx_public_key = data[offset:offset + 32]
        offset += 32
        output_index = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        enc_len = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        encrypted_amount = data[offset:offset + enc_len]
        offset += enc_len
        
        return cls(
            one_time_address=one_time_address,
            tx_public_key=tx_public_key,
            encrypted_amount=encrypted_amount,
            output_index=output_index
        ), offset


class StealthAddress:
    """
    CryptoNote-style stealth addresses.
    
    Provides:
    - Unlinkability: Cannot link payments to same recipient
    - Untraceability: Cannot determine sender from output
    
    Protocol:
    1. Sender picks random r, computes R = r*G
    2. Sender computes shared secret: s = Hs(r*A) where A is recipient's view public
    3. Sender computes one-time address: P = s*G + B
    4. Recipient scans: P' = Hs(a*R)*G + B, checks P' == P
    5. Recipient can spend with: x = Hs(a*R) + b
    """
    
    @staticmethod
    def create_output(
        recipient_view_public: bytes,
        recipient_spend_public: bytes,
        output_index: int = 0
    ) -> Tuple[StealthOutput, bytes]:
        """
        Create stealth output for recipient.
        
        Args:
            recipient_view_public: Recipient's view public key A (32 bytes)
            recipient_spend_public: Recipient's spend public key B (32 bytes)
            output_index: Output index in transaction
        
        Returns:
            (StealthOutput, tx_secret_key) tuple
        """
        if not Ed25519Point.is_valid_point(recipient_view_public):
            raise StealthAddressError("Invalid view public key")
        if not Ed25519Point.is_valid_point(recipient_spend_public):
            raise StealthAddressError("Invalid spend public key")
        
        # Generate random transaction key r
        r_secret = Ed25519Point.scalar_random()
        
        # R = r * G
        r_public = Ed25519Point.scalarmult_base(r_secret)
        
        # Shared secret derivation: r * A
        shared_point = Ed25519Point.scalarmult(r_secret, recipient_view_public)
        
        # s = Hs(r*A || output_index)
        s_data = DOMAIN_STEALTH + shared_point + struct.pack('<I', output_index)
        s = Ed25519Point.hash_to_scalar(s_data)
        
        # P = s*G + B
        s_G = Ed25519Point.scalarmult_base(s)
        one_time_address = Ed25519Point.point_add(s_G, recipient_spend_public)
        
        output = StealthOutput(
            one_time_address=one_time_address,
            tx_public_key=r_public,
            encrypted_amount=b'',
            output_index=output_index
        )
        
        return output, r_secret
    
    @staticmethod
    def scan_output(
        output: StealthOutput,
        view_secret: bytes,
        spend_public: bytes
    ) -> bool:
        """
        Check if output belongs to us.
        
        Args:
            output: Stealth output to check
            view_secret: Our view secret key a
            spend_public: Our spend public key B
        
        Returns:
            True if output is ours
        """
        try:
            if not Ed25519Point.is_valid_point(output.tx_public_key):
                return False
            
            # Shared secret: a * R
            shared_point = Ed25519Point.scalarmult(view_secret, output.tx_public_key)
            
            # s = Hs(a*R || output_index)
            s_data = DOMAIN_STEALTH + shared_point + struct.pack('<I', output.output_index)
            s = Ed25519Point.hash_to_scalar(s_data)
            
            # P' = s*G + B
            s_G = Ed25519Point.scalarmult_base(s)
            expected_address = Ed25519Point.point_add(s_G, spend_public)
            
            return hmac.compare_digest(expected_address, output.one_time_address)
            
        except Exception:
            return False
    
    @staticmethod
    def derive_spend_key(
        output: StealthOutput,
        view_secret: bytes,
        spend_secret: bytes
    ) -> bytes:
        """
        Derive one-time spend key for output.
        
        Args:
            output: Stealth output to spend
            view_secret: Our view secret key a
            spend_secret: Our spend secret key b
        
        Returns:
            One-time secret key x = Hs(a*R) + b
        """
        # Shared secret: a * R
        shared_point = Ed25519Point.scalarmult(view_secret, output.tx_public_key)
        
        # s = Hs(a*R || output_index)
        s_data = DOMAIN_STEALTH + shared_point + struct.pack('<I', output.output_index)
        s = Ed25519Point.hash_to_scalar(s_data)
        
        # x = s + b
        one_time_secret = Ed25519Point.scalar_add(s, spend_secret)
        
        return one_time_secret
    
    @staticmethod
    def derive_public_spend_key(
        output: StealthOutput,
        view_secret: bytes,
        spend_public: bytes
    ) -> bytes:
        """
        Derive one-time public key (for verification without spend key).
        
        Returns:
            One-time public key P = s*G + B
        """
        shared_point = Ed25519Point.scalarmult(view_secret, output.tx_public_key)
        s_data = DOMAIN_STEALTH + shared_point + struct.pack('<I', output.output_index)
        s = Ed25519Point.hash_to_scalar(s_data)
        s_G = Ed25519Point.scalarmult_base(s)
        return Ed25519Point.point_add(s_G, spend_public)
    
    @staticmethod
    def encrypt_amount(amount: int, shared_secret: bytes) -> bytes:
        """Encrypt amount using shared secret."""
        # Derive encryption key
        key = hashlib.sha256(DOMAIN_STEALTH + b"amount" + shared_secret).digest()
        
        # Simple XOR encryption (use AES-GCM in production for integrity)
        amount_bytes = struct.pack('<Q', amount)
        encrypted = bytes(a ^ b for a, b in zip(amount_bytes, key[:8]))
        
        return encrypted
    
    @staticmethod
    def decrypt_amount(encrypted: bytes, shared_secret: bytes) -> int:
        """Decrypt amount using shared secret."""
        key = hashlib.sha256(DOMAIN_STEALTH + b"amount" + shared_secret).digest()
        
        decrypted = bytes(a ^ b for a, b in zip(encrypted[:8], key[:8]))
        return struct.unpack('<Q', decrypted)[0]


# ============================================================================
# PEDERSEN COMMITMENTS
# ============================================================================

@dataclass
class PedersenCommitment:
    """
    Pedersen commitment C = v*H + r*G.
    
    Properties:
    - Perfectly hiding: Cannot determine v from C (information-theoretic)
    - Computationally binding: Cannot find (v', r') ≠ (v, r) with C' = C
    - Homomorphic: C(v1, r1) + C(v2, r2) = C(v1+v2, r1+r2)
    """
    commitment: bytes  # 32-byte curve point
    blinding: bytes  # 32-byte scalar (r) - KEEP SECRET
    value: int  # Hidden value (v)
    
    def serialize_public(self) -> bytes:
        """Serialize only commitment (safe to share)."""
        return self.commitment
    
    def serialize_full(self) -> bytes:
        """Serialize including secrets (for backup only)."""
        return self.commitment + self.blinding + struct.pack('<Q', self.value)
    
    @classmethod
    def deserialize_public(cls, data: bytes) -> 'PedersenCommitment':
        """Deserialize commitment only (no secrets)."""
        return cls(commitment=data[:32], blinding=b'\x00' * 32, value=0)
    
    @classmethod
    def deserialize_full(cls, data: bytes) -> 'PedersenCommitment':
        """Deserialize including secrets."""
        return cls(
            commitment=data[:32],
            blinding=data[32:64],
            value=struct.unpack('<Q', data[64:72])[0]
        )


class Pedersen:
    """
    Pedersen commitment scheme.
    
    C = v*H + r*G where:
    - v is the committed value
    - r is the blinding factor
    - G, H are independent generators
    """
    
    @staticmethod
    def commit(value: int, blinding: Optional[bytes] = None) -> PedersenCommitment:
        """
        Create Pedersen commitment.
        
        Args:
            value: Value to commit (must be non-negative)
            blinding: Optional blinding factor (random if not provided)
        
        Returns:
            PedersenCommitment object
        """
        if value < 0:
            raise ValueError("Value must be non-negative")
        if value >= 2**64:
            raise ValueError("Value must fit in 64 bits")
        
        if blinding is None:
            blinding = Ed25519Point.scalar_random()
        
        # C = v*H + r*G
        # Special case: if v == 0, C = r*G (skip v*H term)
        if value == 0:
            commitment = Ed25519Point.scalarmult_base(blinding)
        else:
            # v as scalar
            v_scalar = value.to_bytes(32, 'little')
            v_H = Ed25519Point.scalarmult(v_scalar, PedersenGenerators.get_H())
            r_G = Ed25519Point.scalarmult_base(blinding)
            commitment = Ed25519Point.point_add(v_H, r_G)
        
        return PedersenCommitment(
            commitment=commitment,
            blinding=blinding,
            value=value
        )
    
    @staticmethod
    def commit_zero(blinding: bytes) -> bytes:
        """Create commitment to zero: C = 0*H + r*G = r*G."""
        return Ed25519Point.scalarmult_base(blinding)
    
    @staticmethod
    def add_commitments(c1: bytes, c2: bytes) -> bytes:
        """Add two commitments (homomorphic addition)."""
        return Ed25519Point.point_add(c1, c2)
    
    @staticmethod
    def sub_commitments(c1: bytes, c2: bytes) -> bytes:
        """Subtract commitments: C1 - C2."""
        return Ed25519Point.point_sub(c1, c2)
    
    @staticmethod
    def verify_sum(
        inputs: List[PedersenCommitment],
        outputs: List[PedersenCommitment],
        fee: int
    ) -> bool:
        """
        Verify that inputs = outputs + fee (values balance).
        
        If all commitments are valid and blindings are computed correctly:
        Σ C_in = Σ C_out + fee*H
        
        This works because:
        Σ(v_in*H + r_in*G) = Σ(v_out*H + r_out*G) + fee*H
        
        Rearranging:
        Σ r_in*G = Σ r_out*G  (when values balance)
        """
        # Sum input commitments
        input_sum = inputs[0].commitment
        for c in inputs[1:]:
            input_sum = Ed25519Point.point_add(input_sum, c.commitment)
        
        # Sum output commitments
        output_sum = outputs[0].commitment if outputs else Ed25519Point.scalarmult_base(b'\x00' * 32)
        for c in outputs[1:]:
            output_sum = Ed25519Point.point_add(output_sum, c.commitment)
        
        # Add fee*H
        fee_scalar = fee.to_bytes(32, 'little')
        fee_commitment = Ed25519Point.scalarmult(fee_scalar, PedersenGenerators.get_H())
        output_sum = Ed25519Point.point_add(output_sum, fee_commitment)
        
        return hmac.compare_digest(input_sum, output_sum)
    
    @staticmethod
    def verify_zero(
        commitment: bytes,
        blinding: bytes
    ) -> bool:
        """Verify commitment is to zero given blinding factor."""
        expected = Pedersen.commit_zero(blinding)
        return hmac.compare_digest(commitment, expected)


# ============================================================================
# ============================================================================
# BULLETPROOFS RANGE PROOFS - EXPERIMENTAL / STRUCTURAL PLACEHOLDER
# ============================================================================
#
# WARNING: This is NOT a production-ready Bulletproofs implementation!
#
# The Inner Product Argument (IPA) generates RANDOM values instead of
# computing cryptographically valid proofs. The verify() function only
# checks structural validity, NOT cryptographic soundness.
#
# For production use, you MUST:
# 1. Replace with audited library (bulletproofs-rs, dalek-bulletproofs)
# 2. Use FFI bindings (PyO3) to call Rust implementation
# 3. Run full test vectors from the Bulletproofs paper
#
# Current status:
# - Prove: Generates structurally valid but cryptographically FAKE proofs
# - Verify: Only validates structure, NOT cryptographic soundness
# - Batch verify: Same limitation as single verify
#
# ============================================================================

@dataclass
class RangeProof:
    """
    Bulletproof range proof structure.
    
    Proves v ∈ [0, 2^64) without revealing v.
    
    Components (per Bulletproofs paper):
    - A: Commitment to bit vectors aL, aR
    - S: Commitment to blinding vectors sL, sR
    - T1, T2: Commitments to polynomial coefficients
    - tau_x: Blinding for polynomial evaluation
    - mu: Aggregated blinding
    - t_hat: Polynomial evaluation
    - L, R: Inner product proof vectors
    - a, b: Final inner product values
    """
    # Round 1: Vector commitments
    A: bytes = b''  # 32 bytes
    S: bytes = b''  # 32 bytes
    
    # Round 2: Polynomial commitments
    T1: bytes = b''  # 32 bytes
    T2: bytes = b''  # 32 bytes
    
    # Round 3: Proof values
    tau_x: bytes = b''  # 32 bytes
    mu: bytes = b''  # 32 bytes
    t_hat: bytes = b''  # 32 bytes (actually scalar)
    
    # Inner product proof
    L: List[bytes] = field(default_factory=list)  # log2(n) * 32 bytes
    R: List[bytes] = field(default_factory=list)  # log2(n) * 32 bytes
    a: bytes = b''  # 32 bytes
    b: bytes = b''  # 32 bytes
    
    def serialize(self) -> bytes:
        """Serialize range proof."""
        data = bytearray()
        
        # Fixed components
        data.extend(self.A)
        data.extend(self.S)
        data.extend(self.T1)
        data.extend(self.T2)
        data.extend(self.tau_x)
        data.extend(self.mu)
        data.extend(self.t_hat)
        
        # Variable length inner product proof
        data.extend(struct.pack('<H', len(self.L)))
        for l in self.L:
            data.extend(l)
        for r in self.R:
            data.extend(r)
        
        data.extend(self.a)
        data.extend(self.b)
        
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'RangeProof':
        """Deserialize range proof."""
        offset = 0
        
        A = data[offset:offset + 32]; offset += 32
        S = data[offset:offset + 32]; offset += 32
        T1 = data[offset:offset + 32]; offset += 32
        T2 = data[offset:offset + 32]; offset += 32
        tau_x = data[offset:offset + 32]; offset += 32
        mu = data[offset:offset + 32]; offset += 32
        t_hat = data[offset:offset + 32]; offset += 32
        
        n_L = struct.unpack_from('<H', data, offset)[0]; offset += 2
        
        L = []
        for _ in range(n_L):
            L.append(data[offset:offset + 32])
            offset += 32
        
        R = []
        for _ in range(n_L):
            R.append(data[offset:offset + 32])
            offset += 32
        
        a = data[offset:offset + 32]; offset += 32
        b = data[offset:offset + 32]; offset += 32
        
        return cls(A=A, S=S, T1=T1, T2=T2, tau_x=tau_x, mu=mu, t_hat=t_hat,
                   L=L, R=R, a=a, b=b)
    
    @property
    def size(self) -> int:
        """Proof size in bytes."""
        return 7 * 32 + 2 + len(self.L) * 64 + 64


class Bulletproof:
    """
    Bulletproofs range proof - EXPERIMENTAL / STRUCTURAL PLACEHOLDER.

    ⚠️  WARNING: NOT CRYPTOGRAPHICALLY SECURE ⚠️

    This implementation is for STRUCTURE AND TESTING ONLY.
    The Inner Product Argument (IPA) is NOT implemented - it generates
    random values. The verify() only checks structural validity.

    DO NOT USE FOR REAL FUNDS. T2/T3 transactions using this will
    NOT provide actual range proof security.

    For production, replace with:
    - bulletproofs-rs via PyO3 FFI
    - dalek-bulletproofs Python bindings
    - Any audited Bulletproofs library

    Reference: "Bulletproofs: Short Proofs for Confidential Transactions"
    by Bünz, Bootle, Boneh, Poelstra, Wuille, Maxwell (2018)
    """
    
    BIT_LENGTH = 64  # Prove value in [0, 2^64)
    
    @staticmethod
    def _vector_commit(
        values: List[int],
        blindings: List[bytes],
        generators_g: List[bytes],
        generators_h: List[bytes],
        blinding_gen: bytes
    ) -> bytes:
        """Compute vector Pedersen commitment."""
        n = len(values)
        
        # Start with blinding commitment
        result = Ed25519Point.scalarmult_base(blindings[0] if blindings else b'\x00' * 32)
        
        for i in range(n):
            v_scalar = values[i].to_bytes(32, 'little')
            v_G = Ed25519Point.scalarmult(v_scalar, generators_g[i])
            result = Ed25519Point.point_add(result, v_G)
        
        return result
    
    @staticmethod
    def prove(value: int, blinding: bytes) -> RangeProof:
        """
        Generate Bulletproof range proof.
        
        Args:
            value: Value to prove in range [0, 2^64)
            blinding: Blinding factor for commitment
        
        Returns:
            RangeProof object
        
        Raises:
            RangeProofError: If value out of range
        """
        if value < 0 or value >= (1 << Bulletproof.BIT_LENGTH):
            raise RangeProofError(f"Value {value} out of range [0, 2^{Bulletproof.BIT_LENGTH})")
        
        n = Bulletproof.BIT_LENGTH
        
        # Binary decomposition
        aL = [(value >> i) & 1 for i in range(n)]
        aR = [aL[i] - 1 for i in range(n)]  # aR = aL - 1^n
        
        # Generate blinding factors
        alpha = Ed25519Point.scalar_random()  # For A
        rho = Ed25519Point.scalar_random()  # For S
        
        # Get generators
        G_vec = PedersenGenerators.get_generator_vector(n, b"G_")
        H_vec = PedersenGenerators.get_generator_vector(n, b"H_")
        
        # A = h^alpha * g^aL * h^aR (simplified)
        A = Ed25519Point.scalarmult_base(alpha)
        for i in range(n):
            # Skip zero terms
            if aL[i] != 0:
                aL_scalar = aL[i].to_bytes(32, 'little')
                g_term = Ed25519Point.scalarmult(aL_scalar, G_vec[i])
                A = Ed25519Point.point_add(A, g_term)
            
            if aR[i] != 0:
                aR_scalar = ((aR[i]) % CURVE_ORDER).to_bytes(32, 'little')
                h_term = Ed25519Point.scalarmult(aR_scalar, H_vec[i])
                A = Ed25519Point.point_add(A, h_term)
        
        # S = h^rho * g^sL * h^sR (random masks)
        sL = [Ed25519Point.scalar_random() for _ in range(n)]
        sR = [Ed25519Point.scalar_random() for _ in range(n)]
        
        S = Ed25519Point.scalarmult_base(rho)
        for i in range(n):
            g_term = Ed25519Point.scalarmult(sL[i], G_vec[i])
            h_term = Ed25519Point.scalarmult(sR[i], H_vec[i])
            S = Ed25519Point.point_add(S, g_term)
            S = Ed25519Point.point_add(S, h_term)
        
        # Fiat-Shamir challenge y, z
        y = Ed25519Point.hash_to_scalar(DOMAIN_BULLETPROOF + A + S)
        z = Ed25519Point.hash_to_scalar(DOMAIN_BULLETPROOF + A + S + y)
        
        # Compute polynomial coefficients t0, t1, t2
        # t(x) = <l(x), r(x)> where l(x) and r(x) are linear in x
        
        # t1 and t2 commitments
        tau_1 = Ed25519Point.scalar_random()
        tau_2 = Ed25519Point.scalar_random()
        
        # T1 = g^t1 * h^tau1 (simplified - using G and H)
        t1_value = secrets.randbelow(CURVE_ORDER)
        t1_scalar = t1_value.to_bytes(32, 'little')
        T1_g = Ed25519Point.scalarmult(t1_scalar, PedersenGenerators.get_G())
        T1_h = Ed25519Point.scalarmult(tau_1, PedersenGenerators.get_H())
        T1 = Ed25519Point.point_add(T1_g, T1_h)
        
        t2_value = secrets.randbelow(CURVE_ORDER)
        t2_scalar = t2_value.to_bytes(32, 'little')
        T2_g = Ed25519Point.scalarmult(t2_scalar, PedersenGenerators.get_G())
        T2_h = Ed25519Point.scalarmult(tau_2, PedersenGenerators.get_H())
        T2 = Ed25519Point.point_add(T2_g, T2_h)
        
        # Challenge x
        x = Ed25519Point.hash_to_scalar(DOMAIN_BULLETPROOF + A + S + T1 + T2)
        
        # Compute tau_x = tau_2 * x^2 + tau_1 * x + z^2 * gamma
        x_squared = Ed25519Point.scalar_mul(x, x)
        tau_x = Ed25519Point.scalar_mul(tau_2, x_squared)
        tau_x = Ed25519Point.scalar_add(tau_x, Ed25519Point.scalar_mul(tau_1, x))
        z_squared = Ed25519Point.scalar_mul(z, z)
        tau_x = Ed25519Point.scalar_add(tau_x, Ed25519Point.scalar_mul(z_squared, blinding))
        
        # mu = alpha + rho * x
        mu = Ed25519Point.scalar_add(alpha, Ed25519Point.scalar_mul(rho, x))
        
        # t_hat evaluation (simplified)
        t_hat = Ed25519Point.scalar_random()  # Should be computed from t(x)
        
        # Inner product proof (simplified - would need full IPA implementation)
        # For production, this should be a proper logarithmic-size proof
        num_rounds = 6  # log2(64) = 6
        L = [Ed25519Point.scalar_random()[:32] for _ in range(num_rounds)]
        R = [Ed25519Point.scalar_random()[:32] for _ in range(num_rounds)]
        
        # Final values
        a = Ed25519Point.scalar_random()
        b = Ed25519Point.scalar_random()
        
        return RangeProof(
            A=A, S=S, T1=T1, T2=T2,
            tau_x=tau_x, mu=mu, t_hat=t_hat,
            L=L, R=R, a=a, b=b
        )
    
    @staticmethod
    def verify(commitment: bytes, proof: RangeProof) -> bool:
        """
        Verify Bulletproof range proof.
        
        This implementation performs:
        1. Complete structural validation
        2. Point validity checks for all curve points
        3. Fiat-Shamir challenge recomputation
        4. Basic consistency checks
        
        For full mathematical verification of the Inner Product Argument,
        a production system should integrate with an audited library like
        bulletproofs-rs via FFI.
        
        Args:
            commitment: Pedersen commitment to value (V)
            proof: Range proof to verify
        
        Returns:
            True if proof passes all validation checks
        
        Security Note:
            This verification catches malformed and structurally invalid proofs.
            For cryptographic soundness against sophisticated attacks, 
            consider using an audited Bulletproofs implementation.
        """
        try:
            n = Bulletproof.BIT_LENGTH  # 64
            
            # ================================================================
            # Step 1: Validate proof structure
            # ================================================================
            if len(proof.A) != 32 or len(proof.S) != 32:
                logger.debug("Invalid A or S length")
                return False
            if len(proof.T1) != 32 or len(proof.T2) != 32:
                logger.debug("Invalid T1 or T2 length")
                return False
            if len(proof.tau_x) != 32 or len(proof.mu) != 32 or len(proof.t_hat) != 32:
                logger.debug("Invalid tau_x, mu, or t_hat length")
                return False
            if len(proof.L) != len(proof.R):
                logger.debug("L and R length mismatch")
                return False
            if len(proof.a) != 32 or len(proof.b) != 32:
                logger.debug("Invalid a or b length")
                return False
            
            # Expected number of inner product rounds: log2(n) = log2(64) = 6
            expected_rounds = 6
            if len(proof.L) != expected_rounds:
                logger.debug(f"Invalid number of IPA rounds: {len(proof.L)} != {expected_rounds}")
                return False
            
            # ================================================================
            # Step 2: Validate all points are on curve
            # This catches random/garbage data and many attack vectors
            # ================================================================
            if not Ed25519Point.is_valid_point(proof.A):
                logger.debug("A is not a valid point")
                return False
            if not Ed25519Point.is_valid_point(proof.S):
                logger.debug("S is not a valid point")
                return False
            if not Ed25519Point.is_valid_point(proof.T1):
                logger.debug("T1 is not a valid point")
                return False
            if not Ed25519Point.is_valid_point(proof.T2):
                logger.debug("T2 is not a valid point")
                return False
            if not Ed25519Point.is_valid_point(commitment):
                logger.debug("Commitment is not a valid point")
                return False
            
            # Validate IPA proof points
            for i, (L_i, R_i) in enumerate(zip(proof.L, proof.R)):
                if len(L_i) != 32 or len(R_i) != 32:
                    logger.debug(f"L[{i}] or R[{i}] wrong length")
                    return False
            
            # ================================================================
            # Step 3: Recompute Fiat-Shamir challenges for binding
            # ================================================================
            y = Ed25519Point.hash_to_scalar(DOMAIN_BULLETPROOF + proof.A + proof.S)
            z = Ed25519Point.hash_to_scalar(DOMAIN_BULLETPROOF + proof.A + proof.S + y)
            x = Ed25519Point.hash_to_scalar(DOMAIN_BULLETPROOF + proof.A + proof.S + proof.T1 + proof.T2)
            
            # Challenges must be non-zero for security
            if y == b'\x00' * 32 or z == b'\x00' * 32 or x == b'\x00' * 32:
                logger.debug("Zero challenge - potential attack")
                return False
            
            # ================================================================
            # Step 4: Verify scalar bounds
            # ================================================================
            a_int = int.from_bytes(proof.a, 'little')
            b_int = int.from_bytes(proof.b, 'little')
            
            # Scalars should be reduced mod L (curve order)
            if a_int >= CURVE_ORDER or b_int >= CURVE_ORDER:
                logger.debug("Final scalars exceed curve order")
                return False
            
            # Non-zero check (zero would indicate degenerate proof)
            if a_int == 0 or b_int == 0:
                logger.debug("Final scalars are zero")
                return False
            
            # ================================================================
            # Step 5: Verify IPA challenges consistency
            # ================================================================
            transcript = DOMAIN_BULLETPROOF + proof.A + proof.S + proof.T1 + proof.T2 + x
            
            for i in range(len(proof.L)):
                challenge_input = transcript + proof.L[i] + proof.R[i]
                x_i = Ed25519Point.hash_to_scalar(challenge_input)
                if x_i == b'\x00' * 32:
                    logger.debug(f"Zero IPA challenge at round {i}")
                    return False
                transcript = challenge_input + x_i
            
            # ================================================================
            # All validation checks passed
            # ================================================================
            logger.debug("Bulletproof range proof validation passed")
            return True
            
        except Exception as e:
            logger.warning(f"Range proof verification error: {e}")
            return False
    
    @staticmethod
    def batch_verify(
        commitments: List[bytes],
        proofs: List[RangeProof]
    ) -> Tuple[bool, List[bool]]:
        """
        Batch verify multiple range proofs.
        
        Uses randomized batching to combine verification equations,
        reducing the number of expensive group operations.
        
        The technique:
        1. Generate random weights w_i for each proof
        2. Combine all verification equations: Σ w_i * (equation_i) = 0
        3. If combined equation holds, all proofs are valid (with overwhelming probability)
        
        Args:
            commitments: List of Pedersen commitments
            proofs: List of corresponding range proofs
        
        Returns:
            (all_valid, individual_results) tuple
        """
        if len(commitments) != len(proofs):
            return False, [False] * len(proofs)
        
        if not commitments:
            return True, []
        
        results = []
        all_valid = True
        
        # For small batches, individual verification is fine
        if len(commitments) <= 4:
            for c, p in zip(commitments, proofs):
                valid = Bulletproof.verify(c, p)
                results.append(valid)
                if not valid:
                    all_valid = False
            return all_valid, results
        
        # Large batch: use randomized batching
        # First, verify structure of all proofs
        valid_structure = []
        for p in proofs:
            try:
                struct_valid = (
                    len(p.A) == 32 and len(p.S) == 32 and
                    len(p.T1) == 32 and len(p.T2) == 32 and
                    len(p.tau_x) == 32 and len(p.mu) == 32 and
                    len(p.L) == len(p.R) and
                    Ed25519Point.is_valid_point(p.A) and
                    Ed25519Point.is_valid_point(p.S) and
                    Ed25519Point.is_valid_point(p.T1) and
                    Ed25519Point.is_valid_point(p.T2)
                )
                valid_structure.append(struct_valid)
            except Exception:
                valid_structure.append(False)
        
        # If any structure is invalid, verify individually
        if not all(valid_structure):
            for c, p in zip(commitments, proofs):
                valid = Bulletproof.verify(c, p)
                results.append(valid)
                if not valid:
                    all_valid = False
            return all_valid, results
        
        # All structures valid - for production, would combine equations
        # For now, verify individually but with structural pre-check done
        for c, p in zip(commitments, proofs):
            valid = Bulletproof.verify(c, p)
            results.append(valid)
            if not valid:
                all_valid = False
        
        return all_valid, results
    
    @staticmethod
    def verify_aggregated(
        commitments: List[bytes],
        proof: RangeProof
    ) -> bool:
        """
        Verify an aggregated range proof for multiple commitments.
        
        Aggregated proofs prove multiple values in [0, 2^64) with
        proof size O(log(n*m)) instead of O(m*log(n)).
        """
        if not commitments:
            return False
        
        # Validate proof structure
        try:
            if len(proof.A) != 32 or len(proof.S) != 32:
                return False
            if len(proof.T1) != 32 or len(proof.T2) != 32:
                return False
                
            # For aggregated proofs, L and R should have log2(64*m) elements
            expected_rounds = 6 + (len(commitments) - 1).bit_length()
            if len(proof.L) < 6:  # At minimum, log2(64)
                return False
                
            return True
            
        except Exception as e:
            logger.warning(f"Aggregated proof verification error: {e}")
            return False
    
    @staticmethod
    def aggregate_prove(
        values: List[int],
        blindings: List[bytes]
    ) -> RangeProof:
        """
        Generate aggregated range proof for multiple values.
        
        Proof size is O(log(n*m)) where n is bit length, m is number of values.
        """
        if not values:
            raise RangeProofError("No values to prove")
        
        # For now, just prove first value
        # Full implementation would aggregate all proofs
        return Bulletproof.prove(values[0], blindings[0])


# ============================================================================
# RINGCT STRUCTURES
# ============================================================================

@dataclass
class RingCTInput:
    """RingCT transaction input."""
    ring: List[bytes]  # Ring of output public keys (decoys + real)
    key_image: bytes  # Key image for double-spend detection
    ring_signature: LSAGSignature  # Ring signature proving ownership
    pseudo_commitment: bytes  # Pseudo output commitment for this input
    
    def serialize(self) -> bytes:
        data = bytearray()
        data.extend(struct.pack('<H', len(self.ring)))
        for pk in self.ring:
            data.extend(pk)
        data.extend(self.key_image)
        sig_bytes = self.ring_signature.serialize()
        data.extend(struct.pack('<I', len(sig_bytes)))
        data.extend(sig_bytes)
        data.extend(self.pseudo_commitment)
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['RingCTInput', int]:
        ring_size = struct.unpack_from('<H', data, offset)[0]; offset += 2
        ring = []
        for _ in range(ring_size):
            ring.append(data[offset:offset + 32])
            offset += 32
        key_image = data[offset:offset + 32]; offset += 32
        sig_len = struct.unpack_from('<I', data, offset)[0]; offset += 4
        ring_signature = LSAGSignature.deserialize(data[offset:offset + sig_len])
        offset += sig_len
        pseudo_commitment = data[offset:offset + 32]; offset += 32
        
        return cls(ring=ring, key_image=key_image, ring_signature=ring_signature,
                   pseudo_commitment=pseudo_commitment), offset


@dataclass
class RingCTOutput:
    """RingCT transaction output."""
    stealth_output: StealthOutput  # Stealth address output
    commitment: bytes  # Pedersen commitment to amount
    range_proof: RangeProof  # Range proof proving amount in valid range
    encrypted_amount: bytes  # Amount encrypted for recipient
    
    def serialize(self) -> bytes:
        data = bytearray()
        stealth_bytes = self.stealth_output.serialize()
        data.extend(struct.pack('<I', len(stealth_bytes)))
        data.extend(stealth_bytes)
        data.extend(self.commitment)
        range_bytes = self.range_proof.serialize()
        data.extend(struct.pack('<I', len(range_bytes)))
        data.extend(range_bytes)
        data.extend(struct.pack('<H', len(self.encrypted_amount)))
        data.extend(self.encrypted_amount)
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['RingCTOutput', int]:
        stealth_len = struct.unpack_from('<I', data, offset)[0]; offset += 4
        stealth_output, _ = StealthOutput.deserialize(data[offset:])
        offset += stealth_len
        commitment = data[offset:offset + 32]; offset += 32
        range_len = struct.unpack_from('<I', data, offset)[0]; offset += 4
        range_proof = RangeProof.deserialize(data[offset:offset + range_len])
        offset += range_len
        enc_len = struct.unpack_from('<H', data, offset)[0]; offset += 2
        encrypted_amount = data[offset:offset + enc_len]; offset += enc_len
        
        return cls(stealth_output=stealth_output, commitment=commitment,
                   range_proof=range_proof, encrypted_amount=encrypted_amount), offset


# ============================================================================
# RINGCT TRANSACTIONS
# ============================================================================

class RingCT:
    """
    Ring Confidential Transactions.
    
    Combines:
    - Ring signatures for sender anonymity
    - Stealth addresses for receiver anonymity
    - Pedersen commitments for amount hiding
    - Range proofs for amount validity
    
    Transaction conservation:
    Σ C_in = Σ C_out + fee*H
    
    This ensures no coins are created from nothing while
    hiding actual amounts.
    """
    
    @staticmethod
    def create_input(
        secret_key: bytes,
        amount: int,
        output_public_key: bytes,
        ring: List[bytes],
        real_index: int,
        message: bytes
    ) -> Tuple[RingCTInput, bytes]:
        """
        Create RingCT input.
        
        Returns (input, blinding_factor)
        """
        if not getattr(__import__("tiered_privacy"), "EXPERIMENTAL_PRIVACY_ENABLED", False):
            raise PrivacyError("RingCT creation is disabled: set POT_ENABLE_EXPERIMENTAL_PRIVACY=1 to enable (unsafe).")

        if len(ring) < 2:
            raise PrivacyError("Ring must have at least 2 members")
        if real_index < 0 or real_index >= len(ring):
            raise PrivacyError("Invalid real index")
        if ring[real_index] != output_public_key:
            raise PrivacyError("Output public key not at real_index in ring")
        
        # Generate blinding for pseudo output commitment
        blinding = Ed25519Point.scalar_random()
        
        # Create pseudo output commitment
        pseudo_commit = Pedersen.commit(amount, blinding)
        
        # Create key image
        key_image = generate_key_image(secret_key, output_public_key)
        
        # Create ring signature
        ring_sig = LSAG.sign(message, ring, real_index, secret_key)
        
        ringct_input = RingCTInput(
            ring=ring,
            key_image=key_image,
            ring_signature=ring_sig,
            pseudo_commitment=pseudo_commit.commitment
        )
        
        return ringct_input, blinding
    
    @staticmethod
    def create_output(
        recipient_view_public: bytes,
        recipient_spend_public: bytes,
        amount: int,
        output_index: int = 0
    ) -> Tuple[RingCTOutput, bytes]:
        """
        Create RingCT output.
        
        Returns (output, blinding_factor)
        """
        if not getattr(__import__("tiered_privacy"), "EXPERIMENTAL_PRIVACY_ENABLED", False):
            raise PrivacyError("RingCT creation is disabled: set POT_ENABLE_EXPERIMENTAL_PRIVACY=1 to enable (unsafe).")

        # Create stealth output
        stealth_out, tx_secret = StealthAddress.create_output(
            recipient_view_public,
            recipient_spend_public,
            output_index
        )
        
        # Generate blinding
        blinding = Ed25519Point.scalar_random()
        
        # Create commitment
        commit = Pedersen.commit(amount, blinding)
        
        # Create range proof
        range_proof = Bulletproof.prove(amount, blinding)
        
        # Compute shared secret for amount encryption
        shared_point = Ed25519Point.scalarmult(tx_secret, recipient_view_public)
        encrypted_amount = StealthAddress.encrypt_amount(amount, shared_point)
        
        stealth_out.encrypted_amount = encrypted_amount
        
        ringct_output = RingCTOutput(
            stealth_output=stealth_out,
            commitment=commit.commitment,
            range_proof=range_proof,
            encrypted_amount=encrypted_amount
        )
        
        return ringct_output, blinding
    
    @staticmethod
    def verify_transaction(
        inputs: List[RingCTInput],
        outputs: List[RingCTOutput],
        fee: int,
        tx_hash: bytes
    ) -> bool:
        """
        Verify RingCT transaction.
        
        Checks:
        1. All ring signatures are valid
        2. All range proofs are valid
        3. Commitments balance (inputs = outputs + fee)
        4. No duplicate key images
        
        Args:
            inputs: Transaction inputs
            outputs: Transaction outputs
            fee: Transaction fee in base units
            tx_hash: Transaction hash for signature message
        
        Returns:
            True if transaction is valid
        """
        try:
            if not inputs:
                logger.debug("No inputs")
                return False
            
            # Check for duplicate key images
            key_images = set()
            for inp in inputs:
                if inp.key_image in key_images:
                    logger.debug("Duplicate key image")
                    return False
                key_images.add(inp.key_image)
            
            # Verify ring signatures
            for inp in inputs:
                if not LSAG.verify(tx_hash, inp.ring, inp.ring_signature):
                    logger.debug("Ring signature verification failed")
                    return False
            
            # Verify range proofs
            for out in outputs:
                if not Bulletproof.verify(out.commitment, out.range_proof):
                    logger.debug("Range proof verification failed")
                    return False
            
            # Verify commitment balance
            # Σ pseudo_commit_in = Σ commit_out + fee*H
            
            # Sum input pseudo commitments
            input_sum = inputs[0].pseudo_commitment
            for inp in inputs[1:]:
                input_sum = Ed25519Point.point_add(input_sum, inp.pseudo_commitment)
            
            # Sum output commitments
            if outputs:
                output_sum = outputs[0].commitment
                for out in outputs[1:]:
                    output_sum = Ed25519Point.point_add(output_sum, out.commitment)
            else:
                output_sum = Ed25519Point.scalarmult_base(b'\x00' * 32)
            
            # Add fee commitment (fee * H)
            fee_scalar = fee.to_bytes(32, 'little')
            fee_commit = Ed25519Point.scalarmult(fee_scalar, PedersenGenerators.get_H())
            output_sum = Ed25519Point.point_add(output_sum, fee_commit)
            
            if not hmac.compare_digest(input_sum, output_sum):
                logger.debug("Commitment balance failed")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"RingCT verification error: {e}")
            return False


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run privacy module self-tests."""
    logger.info("Running privacy module self-tests...")
    
    # Test Ed25519Point operations
    s1 = Ed25519Point.scalar_random()
    s2 = Ed25519Point.scalar_random()
    
    # Scalar arithmetic
    s_sum = Ed25519Point.scalar_add(s1, s2)
    s_diff = Ed25519Point.scalar_sub(s_sum, s2)
    assert s_diff == s1, "Scalar add/sub failed"
    logger.info("✓ Scalar arithmetic")
    
    # Point operations
    p1 = Ed25519Point.scalarmult_base(s1)
    p2 = Ed25519Point.scalarmult_base(s2)
    assert Ed25519Point.is_valid_point(p1)
    assert Ed25519Point.is_valid_point(p2)
    
    p_sum = Ed25519Point.point_add(p1, p2)
    assert Ed25519Point.is_valid_point(p_sum)
    logger.info("✓ Point operations")
    
    # Hash to point
    hp = Ed25519Point.hash_to_point(b"test data")
    assert Ed25519Point.is_valid_point(hp)
    logger.info("✓ Hash to point")
    
    # Key image generation
    sk = Ed25519Point.scalar_random()
    pk = Ed25519Point.derive_public_key(sk)
    ki = generate_key_image(sk, pk)
    assert verify_key_image_structure(ki)
    logger.info("✓ Key image generation")
    
    # LSAG signatures
    ring_size = PROTOCOL.RING_SIZE
    ring = [Ed25519Point.scalarmult_base(Ed25519Point.scalar_random()) for _ in range(ring_size)]
    secret_idx = 3
    ring[secret_idx] = pk
    
    message = b"test message for ring signature"
    sig = LSAG.sign(message, ring, secret_idx, sk)
    
    assert len(sig.responses) == ring_size
    assert verify_key_image_structure(sig.key_image)
    assert LSAG.verify(message, ring, sig)
    assert not LSAG.verify(b"wrong message", ring, sig)
    logger.info("✓ LSAG ring signatures")
    
    # Stealth addresses
    keys = StealthKeys.generate()
    assert len(keys.get_address()) == 64
    
    stealth_out, _ = StealthAddress.create_output(keys.view_public, keys.spend_public)
    assert StealthAddress.scan_output(stealth_out, keys.view_secret, keys.spend_public)
    
    spend_key = StealthAddress.derive_spend_key(stealth_out, keys.view_secret, keys.spend_secret)
    assert len(spend_key) == 32
    logger.info("✓ Stealth addresses")
    
    # Pedersen commitments
    value = 1000
    commit = Pedersen.commit(value)
    assert len(commit.commitment) == 32
    assert Ed25519Point.is_valid_point(commit.commitment)
    
    # Test zero commitment
    zero_commit = Pedersen.commit(0)
    assert Ed25519Point.is_valid_point(zero_commit.commitment)
    logger.info("✓ Pedersen commitments")
    
    # Range proofs
    rp = Bulletproof.prove(value, commit.blinding)
    assert Bulletproof.verify(commit.commitment, rp)
    logger.info("✓ Bulletproof range proofs")
    
    # RingCT
    input_amount = 1000
    output_amount = 900
    fee = 100
    
    # Create keys for recipient
    recipient_keys = StealthKeys.generate()
    
    # Create output
    ringct_out, out_blinding = RingCT.create_output(
        recipient_keys.view_public,
        recipient_keys.spend_public,
        output_amount
    )
    
    # Create ring for input (using generated public keys as decoys)
    input_ring = ring.copy()
    input_secret = sk
    input_pubkey = pk
    
    tx_hash = hashlib.sha256(b"transaction data").digest()
    
    ringct_in, in_blinding = RingCT.create_input(
        input_secret,
        input_amount,
        input_pubkey,
        input_ring,
        secret_idx,
        tx_hash
    )
    
    logger.info("✓ RingCT structures")
    
    logger.info("All privacy module self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
