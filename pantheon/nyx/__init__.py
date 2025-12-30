"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                            NYX - GODDESS OF PRIVACY                           ║
║                                                                               ║
║       Ring signatures, stealth addresses, Pedersen commitments,               ║
║       and tiered privacy model for Proof of Time protocol.                    ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  PRODUCTION-READY (T0/T1):                                                    ║
║  ─────────────────────────                                                    ║
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
║  TIERED PRIVACY (T0-T3):                                                      ║
║  ───────────────────────                                                      ║
║  - PrivacyTier:       T0=Public, T1=Stealth, T2=Confidential, T3=Ring         ║
║  - TieredOutput:      Output with privacy tier                                ║
║  - TieredInput:       Input with privacy tier                                 ║
║  - TieredTransaction: Multi-tier transaction                                  ║
║  - TierValidator:     Transaction validation                                  ║
║                                                                               ║
║  EXPERIMENTAL (T2/T3 - DISABLED BY DEFAULT):                                  ║
║  ───────────────────────────────────────────                                  ║
║  - Bulletproof:       Range proofs (IPA NOT cryptographically implemented)    ║
║  - RangeProof:        Range proof structure                                   ║
║  - RingCT:            Ring Confidential Transactions                          ║
║                                                                               ║
║  ⚠️  To enable experimental features (UNSAFE):                                ║
║      export POT_ENABLE_EXPERIMENTAL_PRIVACY=1                                 ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

# =============================================================================
# PRODUCTION-READY PRIMITIVES (privacy.py)
# =============================================================================

from .privacy import (
    # Low-level curve operations
    Ed25519Point,

    # Key image
    generate_key_image,
    verify_key_image_structure,

    # Ring signatures - PRODUCTION
    LSAG,
    LSAGSignature,

    # Stealth addresses - PRODUCTION
    StealthKeys,
    StealthAddress,
    StealthOutput,

    # Pedersen commitments - PRODUCTION
    Pedersen,
    PedersenCommitment,
    PedersenGenerators,

    # Range proofs - EXPERIMENTAL (structure OK, crypto NOT production)
    Bulletproof,
    RangeProof,

    # RingCT - EXPERIMENTAL
    RingCT,
    RingCTInput,
    RingCTOutput,

    # Exceptions
    PrivacyError,
    RingSignatureError,
    RangeProofError,
    StealthAddressError,

    # Constants
    CURVE_ORDER,
    FIELD_PRIME,
    DOMAIN_KEY_IMAGE,
    DOMAIN_RING_SIG,
    DOMAIN_STEALTH,
    DOMAIN_COMMITMENT,
    DOMAIN_BULLETPROOF,

    # Availability
    NACL_AVAILABLE,
)

# =============================================================================
# TIERED PRIVACY MODEL (tiered_privacy.py)
# =============================================================================

from .tiered_privacy import (
    # Privacy tiers
    PrivacyTier,
    TIER_SPECS,
    DEFAULT_RING_SIZE,

    # Tiered structures
    TieredOutput,
    TieredInput,
    TieredTransaction,

    # Builder and validator
    TieredTransactionBuilder,
    TierValidator,
    AnonymitySetManager,

    # Experimental flag
    EXPERIMENTAL_PRIVACY_ENABLED,
)

# =============================================================================
# RISTRETTO255 (ristretto.py) - EXPERIMENTAL
# =============================================================================

from .ristretto import (
    # Ristretto group (for Bulletproofs++)
    RistrettoPoint,
    RistrettoScalar,
    RistrettoGenerators,
    RistrettoPedersenCommitment,

    # Bulletproofs++ - EXPERIMENTAL
    BulletproofPP,

    # Key image for T3
    generate_ristretto_key_image,

    # Curve order
    L,
)

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # === PRODUCTION-READY ===

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
    'DEFAULT_RING_SIZE',

    # Tiered structures
    'TieredOutput',
    'TieredInput',
    'TieredTransaction',
    'TieredTransactionBuilder',
    'TierValidator',
    'AnonymitySetManager',

    # Exceptions
    'PrivacyError',
    'RingSignatureError',
    'RangeProofError',
    'StealthAddressError',

    # Constants
    'CURVE_ORDER',
    'FIELD_PRIME',
    'DOMAIN_KEY_IMAGE',
    'DOMAIN_RING_SIG',
    'DOMAIN_STEALTH',
    'DOMAIN_COMMITMENT',
    'DOMAIN_BULLETPROOF',

    # Availability flags
    'NACL_AVAILABLE',
    'EXPERIMENTAL_PRIVACY_ENABLED',

    # === EXPERIMENTAL (require POT_ENABLE_EXPERIMENTAL_PRIVACY=1) ===

    # Range proofs (IPA not implemented)
    'Bulletproof',
    'RangeProof',

    # RingCT
    'RingCT',
    'RingCTInput',
    'RingCTOutput',

    # Ristretto255 (for advanced Bulletproofs++)
    'RistrettoPoint',
    'RistrettoScalar',
    'RistrettoGenerators',
    'RistrettoPedersenCommitment',
    'BulletproofPP',
    'generate_ristretto_key_image',
    'L',
]
