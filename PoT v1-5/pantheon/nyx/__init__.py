"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                            NYX - GODDESS OF PRIVACY                           ║
║                                                                               ║
║       Ring signatures, stealth addresses, Pedersen commitments,               ║
║       and tiered privacy model for Proof of Time protocol.                    ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  PRODUCTION COMPONENTS:                                                       ║
║  ─────────────────────                                                        ║
║  - Ed25519Point:      Low-level curve operations via libsodium                ║
║  - LSAG:              Linkable Spontaneous Anonymous Group signatures         ║
║  - LSAGSignature:     Ring signature structure                                ║
║  - StealthKeys:       View/spend key pairs for stealth addresses              ║
║  - StealthAddress:    CryptoNote-style one-time addresses                     ║
║  - StealthOutput:     Stealth transaction output                              ║
║  - Pedersen:          Pedersen commitment scheme                              ║
║  - PedersenCommitment: Commitment structure (C = v*H + r*G)                   ║
║  - generate_key_image: Key image for double-spend prevention                  ║
║                                                                               ║
║  TIERED PRIVACY:                                                              ║
║  ───────────────                                                              ║
║  - T0 (Public):    Addresses + amounts visible (~250 B, 1× fee)               ║
║  - T1 (Stealth):   One-time addresses, amounts visible (~400 B, 2× fee)       ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

# =============================================================================
# PRODUCTION PRIMITIVES (privacy.py)
# =============================================================================

from .privacy import (
    # Low-level curve operations
    Ed25519Point,

    # Key image
    generate_key_image,
    verify_key_image_structure,

    # Ring signatures
    LSAG,
    LSAGSignature,

    # Stealth addresses
    StealthKeys,
    StealthAddress,
    StealthOutput,

    # Pedersen commitments
    Pedersen,
    PedersenCommitment,
    PedersenGenerators,

    # Exceptions
    PrivacyError,
    RingSignatureError,
    StealthAddressError,

    # Constants
    CURVE_ORDER,
    FIELD_PRIME,
    DOMAIN_KEY_IMAGE,
    DOMAIN_RING_SIG,
    DOMAIN_STEALTH,
    DOMAIN_COMMITMENT,

    # Availability
    NACL_AVAILABLE,
)


# =============================================================================
# STUB CLASSES (Planned features - not yet implemented)
# =============================================================================

class RangeProof:
    """Placeholder for Bulletproofs range proofs (planned feature)."""
    pass


class RingCTInput:
    """Placeholder for RingCT input (planned feature)."""
    pass


class RingCTOutput:
    """Placeholder for RingCT output (planned feature)."""
    pass


class AnonymitySetManager:
    """Placeholder for anonymity set management (planned feature)."""

    def __init__(self):
        self.outputs = []

    def add_output(self, output):
        """Add output to anonymity pool."""
        self.outputs.append(output)

    def get_pool_stats(self):
        """Get pool statistics."""
        return {'total_outputs': len(self.outputs)}


# Default ring size for ring signatures (11 members = 1 real + 10 decoys)
DEFAULT_RING_SIZE = 11


# =============================================================================
# TIERED PRIVACY MODEL (tiered_privacy.py)
# =============================================================================

from .tiered_privacy import (
    # Privacy tiers (T0/T1 only)
    PrivacyTier,
    TIER_SPECS,

    # Tiered structures
    TieredOutput,
    TieredInput,
    TieredTransaction,

    # Builder and validator
    TieredTransactionBuilder,
    TierValidator,
)

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Curve operations
    'Ed25519Point',

    # Key image
    'generate_key_image',
    'verify_key_image_structure',

    # Ring signatures
    'LSAG',
    'LSAGSignature',

    # Stealth addresses
    'StealthKeys',
    'StealthAddress',
    'StealthOutput',

    # Pedersen commitments
    'Pedersen',
    'PedersenCommitment',
    'PedersenGenerators',

    # Privacy tiers
    'PrivacyTier',
    'TIER_SPECS',

    # Tiered structures
    'TieredOutput',
    'TieredInput',
    'TieredTransaction',
    'TieredTransactionBuilder',
    'TierValidator',

    # Stub classes (planned features)
    'RangeProof',
    'RingCTInput',
    'RingCTOutput',
    'AnonymitySetManager',
    'DEFAULT_RING_SIZE',

    # Exceptions
    'PrivacyError',
    'RingSignatureError',
    'StealthAddressError',

    # Constants
    'CURVE_ORDER',
    'FIELD_PRIME',
    'DOMAIN_KEY_IMAGE',
    'DOMAIN_RING_SIG',
    'DOMAIN_STEALTH',
    'DOMAIN_COMMITMENT',

    # Availability
    'NACL_AVAILABLE',
]
