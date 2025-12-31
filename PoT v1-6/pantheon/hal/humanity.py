"""
Hal Humanity System - Core Verification Module

This module provides the foundation for humanity verification in Montana v4.1.
It implements the Graduated Trust Model with three tiers:
- Hardware (TPM/SecureEnclave/FIDO2)
- Social (Custom social graph)
- Time-Locked (Bitcoin halving anchored)

The core insight: TIME proves existence, HUMANITY proves uniqueness.
"""

from __future__ import annotations

import struct
import hashlib
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Apostle limits per tier
MAX_APOSTLES_HARDWARE = 3      # Bootstrap tier
MAX_APOSTLES_SOCIAL = 6        # Bridge tier
MAX_APOSTLES_TIMELOCKED = 12   # Ultimate tier (full Apostles)

# Weights for humanity score calculation
HUMANITY_WEIGHT_HARDWARE = 0.3
HUMANITY_WEIGHT_SOCIAL = 0.6
HUMANITY_WEIGHT_TIMELOCKED = 1.0

# Minimum humanity score for handshake eligibility
HANDSHAKE_MIN_HUMANITY = 0.3  # At least one hardware attestation

# Proof validity periods (in seconds)
HARDWARE_PROOF_VALIDITY = 86400 * 365      # 1 year
SOCIAL_PROOF_VALIDITY = 86400 * 365 * 2    # 2 years
TIMELOCK_PROOF_VALIDITY = 86400 * 365 * 4  # 4 years (one epoch)

# Version for serialization
HAL_VERSION = 1


# ==============================================================================
# ENUMS
# ==============================================================================

class HumanityTier(IntEnum):
    """
    Graduated trust tiers for humanity verification.

    Higher tiers require more effort to fake, providing stronger
    Sybil resistance at the cost of accessibility.
    """
    NONE = 0           # No humanity proof (legacy/bootstrap)
    HARDWARE = 1       # TPM/SecureEnclave/FIDO2 attestation
    SOCIAL = 2         # Custom social graph verification
    TIME_LOCKED = 3    # Bitcoin halving anchored proof


class ProofStatus(IntEnum):
    """Status of a humanity proof."""
    PENDING = 0        # Proof submitted, not yet verified
    VALID = 1          # Proof verified and active
    EXPIRED = 2        # Proof past validity period
    REVOKED = 3        # Proof revoked (slashing, fraud)
    CHALLENGED = 4     # Proof under challenge


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class HumanityProof:
    """
    A proof of humanity at a specific tier.

    Multiple proofs can be combined to increase trust score.
    Higher tier proofs override lower tier proofs for Apostle limits.
    """
    tier: HumanityTier
    proof_type: str                        # e.g., "tpm", "fido2", "timelock"
    proof_data: bytes                      # Opaque proof payload
    pubkey: bytes                          # 32 bytes, bound identity
    created_at: int                        # Unix timestamp
    expires_at: int                        # Unix timestamp
    status: ProofStatus = ProofStatus.VALID
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[bytes] = None      # Self-attestation signature

    @property
    def weight(self) -> float:
        """Get the trust weight for this proof's tier."""
        return get_tier_weight(self.tier)

    @property
    def is_valid(self) -> bool:
        """Check if proof is currently valid."""
        if self.status != ProofStatus.VALID:
            return False
        now = int(datetime.utcnow().timestamp())
        return self.created_at <= now <= self.expires_at

    @property
    def max_apostles(self) -> int:
        """Get max Apostles allowed for this proof's tier."""
        return get_max_apostles(self.tier)

    def serialize(self) -> bytes:
        """Serialize proof for storage/transmission."""
        data = bytearray()

        # Version + tier + type
        data.append(HAL_VERSION)
        data.append(self.tier)
        data.append(self.status)

        # Proof type (length-prefixed string)
        type_bytes = self.proof_type.encode('utf-8')
        data.append(len(type_bytes))
        data.extend(type_bytes)

        # Proof data (length-prefixed)
        data.extend(struct.pack('<H', len(self.proof_data)))
        data.extend(self.proof_data)

        # Pubkey (fixed 32 bytes)
        assert len(self.pubkey) == 32, "Pubkey must be 32 bytes"
        data.extend(self.pubkey)

        # Timestamps
        data.extend(struct.pack('<Q', self.created_at))
        data.extend(struct.pack('<Q', self.expires_at))

        # Signature (optional, length-prefixed)
        if self.signature:
            data.extend(struct.pack('<H', len(self.signature)))
            data.extend(self.signature)
        else:
            data.extend(struct.pack('<H', 0))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'HumanityProof':
        """Deserialize proof from bytes."""
        offset = 0

        # Version check
        version = data[offset]
        offset += 1
        if version != HAL_VERSION:
            raise ValueError(f"Unsupported HAL version: {version}")

        # Tier + status
        tier = HumanityTier(data[offset])
        offset += 1
        status = ProofStatus(data[offset])
        offset += 1

        # Proof type
        type_len = data[offset]
        offset += 1
        proof_type = data[offset:offset + type_len].decode('utf-8')
        offset += type_len

        # Proof data
        proof_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        proof_data = data[offset:offset + proof_len]
        offset += proof_len

        # Pubkey
        pubkey = data[offset:offset + 32]
        offset += 32

        # Timestamps
        created_at = struct.unpack('<Q', data[offset:offset + 8])[0]
        offset += 8
        expires_at = struct.unpack('<Q', data[offset:offset + 8])[0]
        offset += 8

        # Signature (optional)
        sig_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        signature = data[offset:offset + sig_len] if sig_len > 0 else None

        return cls(
            tier=tier,
            proof_type=proof_type,
            proof_data=proof_data,
            pubkey=pubkey,
            created_at=created_at,
            expires_at=expires_at,
            status=status,
            signature=signature
        )


@dataclass
class HumanityProfile:
    """
    Complete humanity profile for a network participant.

    Aggregates all proofs and computes effective tier/score.
    """
    pubkey: bytes
    proofs: List[HumanityProof] = field(default_factory=list)
    created_at: int = field(default_factory=lambda: int(datetime.utcnow().timestamp()))

    @property
    def effective_tier(self) -> HumanityTier:
        """Get highest valid tier from all proofs."""
        valid_proofs = [p for p in self.proofs if p.is_valid]
        if not valid_proofs:
            return HumanityTier.NONE
        return max(p.tier for p in valid_proofs)

    @property
    def humanity_score(self) -> float:
        """Compute aggregate humanity score from all valid proofs."""
        return compute_humanity_score(self.proofs)

    @property
    def max_apostles(self) -> int:
        """Get max Apostles allowed based on effective tier."""
        return get_max_apostles(self.effective_tier)

    def add_proof(self, proof: HumanityProof) -> Tuple[bool, str]:
        """Add a new proof after validation."""
        # Verify pubkey matches
        if proof.pubkey != self.pubkey:
            return False, "Proof pubkey does not match profile"

        # Check for duplicates
        for existing in self.proofs:
            if (existing.tier == proof.tier and
                existing.proof_type == proof.proof_type and
                existing.proof_data == proof.proof_data):
                return False, "Duplicate proof"

        self.proofs.append(proof)
        return True, "Proof added"

    def get_proofs_by_tier(self, tier: HumanityTier) -> List[HumanityProof]:
        """Get all proofs for a specific tier."""
        return [p for p in self.proofs if p.tier == tier and p.is_valid]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_tier_weight(tier: HumanityTier) -> float:
    """Get the trust weight for a humanity tier."""
    weights = {
        HumanityTier.NONE: 0.0,
        HumanityTier.HARDWARE: HUMANITY_WEIGHT_HARDWARE,
        HumanityTier.SOCIAL: HUMANITY_WEIGHT_SOCIAL,
        HumanityTier.TIME_LOCKED: HUMANITY_WEIGHT_TIMELOCKED,
    }
    return weights.get(tier, 0.0)


def get_max_apostles(tier: HumanityTier) -> int:
    """Get maximum Apostles allowed for a tier."""
    limits = {
        HumanityTier.NONE: 0,
        HumanityTier.HARDWARE: MAX_APOSTLES_HARDWARE,
        HumanityTier.SOCIAL: MAX_APOSTLES_SOCIAL,
        HumanityTier.TIME_LOCKED: MAX_APOSTLES_TIMELOCKED,
    }
    return limits.get(tier, 0)


def compute_humanity_score(proofs: List[HumanityProof]) -> float:
    """
    Compute aggregate humanity score from multiple proofs.

    Scoring rules:
    1. Only valid proofs count
    2. Higher tier proofs take precedence
    3. Multiple proofs of same tier don't stack (max is taken)
    4. Cross-tier proofs can add small bonuses

    Returns: Score between 0.0 and 1.0
    """
    valid_proofs = [p for p in proofs if p.is_valid]
    if not valid_proofs:
        return 0.0

    # Group by tier and take max weight per tier
    tier_scores: Dict[HumanityTier, float] = {}
    for proof in valid_proofs:
        tier = proof.tier
        current = tier_scores.get(tier, 0.0)
        tier_scores[tier] = max(current, proof.weight)

    # Highest tier is primary score
    max_tier = max(tier_scores.keys())
    primary_score = tier_scores[max_tier]

    # Lower tiers add small bonuses (up to 0.1 total)
    bonus = 0.0
    for tier, score in tier_scores.items():
        if tier < max_tier:
            bonus += score * 0.1  # 10% of lower tier weights
    bonus = min(bonus, 0.1)  # Cap at 0.1

    return min(primary_score + bonus, 1.0)


def verify_different_humans(
    proof1: HumanityProof,
    proof2: HumanityProof
) -> Tuple[bool, str]:
    """
    Verify that two proofs represent different humans.

    This is the core Sybil resistance check:
    - Same pubkey = same identity (obviously)
    - Same hardware attestation = same device
    - Same social graph patterns = suspicious
    - Same time-lock commitment = impossible (by design)

    Returns: (is_different, reason)
    """
    # Same pubkey is same identity
    if proof1.pubkey == proof2.pubkey:
        return False, "Same pubkey"

    # Same proof data = same underlying identity
    if proof1.proof_data == proof2.proof_data:
        return False, "Identical proof data - same hardware/identity"

    # For hardware proofs, check device binding
    if proof1.tier == HumanityTier.HARDWARE and proof2.tier == HumanityTier.HARDWARE:
        # Extract device IDs if present in metadata
        device1 = proof1.metadata.get('device_id')
        device2 = proof2.metadata.get('device_id')
        if device1 and device2 and device1 == device2:
            return False, "Same hardware device"

    # For time-locked proofs, commitment collision is impossible
    # (SHA3 collision resistant + different secrets)
    if proof1.tier == HumanityTier.TIME_LOCKED and proof2.tier == HumanityTier.TIME_LOCKED:
        # If they passed commitment verification, they're different
        return True, "Different time-locked commitments"

    # Cross-tier comparisons are harder - rely on binding
    # The pubkey binding ensures each proof is tied to one identity
    return True, "Different proof bindings"


# ==============================================================================
# HUMANITY VERIFIER
# ==============================================================================

class HumanityVerifier:
    """
    Main verification engine for humanity proofs.

    Handles:
    - Individual proof verification
    - Cross-proof Sybil detection
    - Score computation
    - Tier upgrades
    """

    def __init__(self):
        # Index of proof_hash -> pubkey for duplicate detection
        self._proof_index: Dict[bytes, bytes] = {}
        # Index of device_id -> pubkey for hardware Sybil detection
        self._device_index: Dict[str, bytes] = {}
        # Index of proof_data_hash -> pubkey for Sybil detection
        self._proof_data_index: Dict[bytes, bytes] = {}
        # Known fraudulent proofs
        self._blacklist: set = set()

    def register_proof(
        self,
        proof: HumanityProof
    ) -> Tuple[bool, str]:
        """
        Register a new proof in the verification system.

        Checks for:
        - Duplicate proofs
        - Device reuse (hardware tier)
        - Blacklisted proofs
        """
        # Compute proof hash
        proof_hash = hashlib.sha3_256(proof.serialize()).digest()
        # Compute proof_data hash (for Sybil detection - same attestation, different pubkeys)
        proof_data_hash = hashlib.sha3_256(proof.proof_data).digest()

        # Check blacklist
        if proof_hash in self._blacklist:
            return False, "Proof is blacklisted"

        # Check for exact duplicate
        if proof_hash in self._proof_index:
            existing_pubkey = self._proof_index[proof_hash]
            if existing_pubkey != proof.pubkey:
                return False, "Proof already registered to different pubkey"
            return True, "Proof already registered"

        # Check for proof_data reuse (different pubkey, same underlying attestation)
        if proof_data_hash in self._proof_data_index:
            existing = self._proof_data_index[proof_data_hash]
            if existing != proof.pubkey:
                return False, "Proof data already bound to different identity"

        # Check device reuse for hardware proofs
        if proof.tier == HumanityTier.HARDWARE:
            device_id = proof.metadata.get('device_id')
            if device_id:
                if device_id in self._device_index:
                    existing = self._device_index[device_id]
                    if existing != proof.pubkey:
                        return False, "Device already bound to different identity"
                self._device_index[device_id] = proof.pubkey

        # Register the proof
        self._proof_index[proof_hash] = proof.pubkey
        self._proof_data_index[proof_data_hash] = proof.pubkey
        return True, "Proof registered"

    def verify_humanity(
        self,
        profile: HumanityProfile,
        min_tier: HumanityTier = HumanityTier.HARDWARE
    ) -> Tuple[bool, str]:
        """
        Verify that a profile meets humanity requirements.

        Args:
            profile: HumanityProfile to verify
            min_tier: Minimum required tier

        Returns: (is_valid, reason)
        """
        # Check effective tier
        if profile.effective_tier < min_tier:
            return False, f"Tier {profile.effective_tier.name} below minimum {min_tier.name}"

        # Check humanity score
        if profile.humanity_score < HANDSHAKE_MIN_HUMANITY:
            return False, f"Humanity score {profile.humanity_score:.2f} below minimum {HANDSHAKE_MIN_HUMANITY}"

        # Verify all proofs are registered
        for proof in profile.proofs:
            if proof.is_valid:
                success, msg = self.register_proof(proof)
                if not success and "already registered" not in msg:
                    return False, f"Proof verification failed: {msg}"

        return True, f"Humanity verified at tier {profile.effective_tier.name}"

    def can_form_handshake(
        self,
        profile: HumanityProfile,
        current_apostle_count: int
    ) -> Tuple[bool, str]:
        """
        Check if profile can form a new Apostle handshake.

        Args:
            profile: HumanityProfile of the requester
            current_apostle_count: Number of current Apostles

        Returns: (can_form, reason)
        """
        max_allowed = profile.max_apostles

        if current_apostle_count >= max_allowed:
            return False, f"Tier {profile.effective_tier.name} limited to {max_allowed} Apostles"

        if profile.humanity_score < HANDSHAKE_MIN_HUMANITY:
            return False, f"Humanity score too low: {profile.humanity_score:.2f}"

        remaining = max_allowed - current_apostle_count
        return True, f"Can form {remaining} more handshakes"

    def blacklist_proof(self, proof_hash: bytes, reason: str) -> None:
        """Add a proof to the blacklist (fraud detection)."""
        self._blacklist.add(proof_hash)

    def get_stats(self) -> Dict[str, int]:
        """Get verification statistics."""
        return {
            'total_proofs': len(self._proof_index),
            'total_devices': len(self._device_index),
            'blacklisted': len(self._blacklist),
        }


# ==============================================================================
# SELF-TEST
# ==============================================================================

def _self_test():
    """Run self-test for humanity module."""
    import os

    print("=" * 60)
    print("HAL HUMANITY SYSTEM - SELF TEST")
    print("=" * 60)

    # Test 1: HumanityTier
    print("\n[1] Testing HumanityTier...")
    assert HumanityTier.HARDWARE < HumanityTier.SOCIAL < HumanityTier.TIME_LOCKED
    assert get_tier_weight(HumanityTier.HARDWARE) == 0.3
    assert get_tier_weight(HumanityTier.TIME_LOCKED) == 1.0
    print("    PASS: Tier ordering and weights correct")

    # Test 2: Max Apostles
    print("\n[2] Testing Apostle limits...")
    assert get_max_apostles(HumanityTier.HARDWARE) == 3
    assert get_max_apostles(HumanityTier.SOCIAL) == 6
    assert get_max_apostles(HumanityTier.TIME_LOCKED) == 12
    print("    PASS: Apostle limits correct")

    # Test 3: HumanityProof serialization
    print("\n[3] Testing HumanityProof serialization...")
    pubkey = os.urandom(32)
    proof = HumanityProof(
        tier=HumanityTier.HARDWARE,
        proof_type="tpm",
        proof_data=os.urandom(64),
        pubkey=pubkey,
        created_at=int(datetime.utcnow().timestamp()),
        expires_at=int(datetime.utcnow().timestamp()) + HARDWARE_PROOF_VALIDITY,
        signature=os.urandom(64)
    )

    serialized = proof.serialize()
    deserialized = HumanityProof.deserialize(serialized)
    assert deserialized.tier == proof.tier
    assert deserialized.proof_type == proof.proof_type
    assert deserialized.pubkey == proof.pubkey
    assert deserialized.signature == proof.signature
    print(f"    PASS: Serialization roundtrip ({len(serialized)} bytes)")

    # Test 4: Humanity score computation
    print("\n[4] Testing humanity score computation...")

    # Single hardware proof
    proofs = [proof]
    score = compute_humanity_score(proofs)
    assert abs(score - 0.3) < 0.01, f"Expected ~0.3, got {score}"

    # Add social proof
    social_proof = HumanityProof(
        tier=HumanityTier.SOCIAL,
        proof_type="social",
        proof_data=os.urandom(64),
        pubkey=pubkey,
        created_at=int(datetime.utcnow().timestamp()),
        expires_at=int(datetime.utcnow().timestamp()) + SOCIAL_PROOF_VALIDITY,
    )
    proofs.append(social_proof)
    score = compute_humanity_score(proofs)
    assert score > 0.6, f"Expected >0.6, got {score}"  # Social + hardware bonus

    # Add time-locked proof
    timelock_proof = HumanityProof(
        tier=HumanityTier.TIME_LOCKED,
        proof_type="timelock",
        proof_data=os.urandom(64),
        pubkey=pubkey,
        created_at=int(datetime.utcnow().timestamp()),
        expires_at=int(datetime.utcnow().timestamp()) + TIMELOCK_PROOF_VALIDITY,
    )
    proofs.append(timelock_proof)
    score = compute_humanity_score(proofs)
    assert score == 1.0, f"Expected 1.0, got {score}"  # Max score with time-locked
    print(f"    PASS: Score computation correct (final: {score})")

    # Test 5: Different humans verification
    print("\n[5] Testing different humans verification...")
    pubkey2 = os.urandom(32)
    proof2 = HumanityProof(
        tier=HumanityTier.HARDWARE,
        proof_type="tpm",
        proof_data=os.urandom(64),  # Different proof data
        pubkey=pubkey2,
        created_at=int(datetime.utcnow().timestamp()),
        expires_at=int(datetime.utcnow().timestamp()) + HARDWARE_PROOF_VALIDITY,
    )

    is_different, reason = verify_different_humans(proof, proof2)
    assert is_different, f"Should be different: {reason}"

    # Same proof data should fail
    proof3 = HumanityProof(
        tier=HumanityTier.HARDWARE,
        proof_type="tpm",
        proof_data=proof.proof_data,  # SAME proof data
        pubkey=os.urandom(32),
        created_at=int(datetime.utcnow().timestamp()),
        expires_at=int(datetime.utcnow().timestamp()) + HARDWARE_PROOF_VALIDITY,
    )
    is_different, reason = verify_different_humans(proof, proof3)
    assert not is_different, f"Should be same: {reason}"
    print("    PASS: Different humans detection works")

    # Test 6: HumanityVerifier
    print("\n[6] Testing HumanityVerifier...")
    verifier = HumanityVerifier()

    # Register proof
    success, msg = verifier.register_proof(proof)
    assert success, f"Registration failed: {msg}"

    # Duplicate registration should succeed (same pubkey)
    success, msg = verifier.register_proof(proof)
    assert success, f"Re-registration failed: {msg}"

    # Same proof data, different pubkey should fail
    success, msg = verifier.register_proof(proof3)
    assert not success, f"Should have failed: {msg}"

    print("    PASS: Verifier registration works")

    # Test 7: HumanityProfile
    print("\n[7] Testing HumanityProfile...")
    profile = HumanityProfile(pubkey=pubkey)
    profile.add_proof(proof)
    profile.add_proof(social_proof)
    profile.add_proof(timelock_proof)

    assert profile.effective_tier == HumanityTier.TIME_LOCKED
    assert profile.max_apostles == 12
    assert profile.humanity_score == 1.0
    print(f"    PASS: Profile aggregation works (tier={profile.effective_tier.name})")

    # Test 8: Handshake eligibility
    print("\n[8] Testing handshake eligibility...")
    can_form, reason = verifier.can_form_handshake(profile, current_apostle_count=5)
    assert can_form, f"Should be able to form: {reason}"

    # At limit
    hardware_profile = HumanityProfile(pubkey=os.urandom(32))
    hardware_profile.add_proof(HumanityProof(
        tier=HumanityTier.HARDWARE,
        proof_type="tpm",
        proof_data=os.urandom(64),
        pubkey=hardware_profile.pubkey,
        created_at=int(datetime.utcnow().timestamp()),
        expires_at=int(datetime.utcnow().timestamp()) + HARDWARE_PROOF_VALIDITY,
    ))

    can_form, reason = verifier.can_form_handshake(hardware_profile, current_apostle_count=3)
    assert not can_form, f"Should not be able to form: {reason}"
    print("    PASS: Handshake eligibility checks work")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
