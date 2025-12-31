"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          PROMETHEUS - GOD OF CRYPTOGRAPHY                     ║
║                                                                               ║
║       All cryptographic primitives for Proof of Time protocol.                ║
║       Ed25519 signatures, ECVRF, Wesolowski VDF, Post-Quantum ready.          ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  CORE PRIMITIVES:                                                             ║
║  ────────────────                                                             ║
║  - Ed25519:        Digital signatures (RFC 8032)                              ║
║  - X25519:         Key exchange (Diffie-Hellman)                              ║
║  - ECVRF:          Verifiable Random Function (RFC 9381)                      ║
║  - WesolowskiVDF:  Verifiable Delay Function (RSA-2048)                       ║
║  - MerkleTree:     Merkle tree construction and proofs                        ║
║                                                                               ║
║  HASH FUNCTIONS:                                                              ║
║  ───────────────                                                              ║
║  - sha256, sha256d:    SHA-256 single/double                                  ║
║  - sha512:             SHA-512                                                ║
║  - sha3_256, sha3_512: SHA-3 (Keccak)                                         ║
║  - shake256:           SHAKE256 XOF (quantum-resistant)                       ║
║  - hash160:            RIPEMD160(SHA256(x))                                   ║
║                                                                               ║
║  POST-QUANTUM (OPTIONAL):                                                     ║
║  ────────────────────────                                                     ║
║  - SHAKE256VDF:    Hash-based VDF (no trusted setup)                          ║
║  - SPHINCSPlus:    Post-quantum signatures (liboqs)                           ║
║  - MLKEM:          Post-quantum key encapsulation                             ║
║  - STARKProver:    STARK proof generation                                     ║
║                                                                               ║
║  CRITICAL SECURITY NOTES:                                                     ║
║  ────────────────────────                                                     ║
║  1. VDF uses RSA-2048 challenge modulus ($200K prize, unfactored since 1991)  ║
║  2. ECVRF uses cofactor multiplication for prime-order subgroup               ║
║  3. All comparisons use constant-time operations                              ║
║  4. Ed25519 via libsodium (PyNaCl) - audited implementation                   ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

# =============================================================================
# CORE CRYPTOGRAPHIC PRIMITIVES (crypto.py)
# =============================================================================

from .crypto import (
    # Hash functions
    sha256,
    sha256d,
    sha512,
    ripemd160,
    hash160,
    tagged_hash,
    hmac_sha256,
    hmac_sha512,

    # Digital signatures
    Ed25519,

    # Key exchange
    X25519,

    # Verifiable Random Function
    ECVRF,
    VRFOutput,

    # Verifiable Delay Function
    WesolowskiVDF,
    VDFProof,
    VDFCheckpoint,
    VDFSetupParameters,
    VDFTrustedSetup,

    # Merkle trees
    MerkleTree,

    # Exceptions
    CryptoError,
    VDFError,
    VRFError,
    SignatureError,
    TrustedSetupError,

    # Utilities
    secure_random_bytes,
    constant_time_compare,
    int_to_bytes,
    bytes_to_int,
    secure_zero,

    # Availability flags
    NACL_AVAILABLE,
    PYCRYPTODOME_AVAILABLE,
    CRYPTOGRAPHY_AVAILABLE,
    USE_GMP_VDF,
)

# =============================================================================
# CRYPTO AGILITY LAYER (crypto_provider.py)
# =============================================================================

from .crypto_provider import (
    CryptoProvider,
    CryptoBackend,
    VDFProofBase,
    SignatureBundle,
    LegacyCryptoProvider,
    get_crypto_provider,
    set_default_backend,
    get_default_backend,
    clear_provider_cache,
)

# =============================================================================
# POST-QUANTUM CRYPTOGRAPHY (pq_crypto.py)
# =============================================================================

from .pq_crypto import (
    # SHA-3 hash functions
    sha3_256,
    sha3_256d,
    sha3_512,
    shake256,
    hmac_sha3_256,

    # Hash-based VDF (no trusted setup, quantum-resistant)
    SHAKE256VDF,

    # STARK proofs
    STARKProver,

    # Post-quantum providers
    PostQuantumCryptoProvider,
    HybridCryptoProvider,

    # Availability flags
    LIBOQS_AVAILABLE,
    MLKEM_AVAILABLE,
    WINTERFELL_AVAILABLE,
)

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Hash functions (SHA-2)
    'sha256',
    'sha256d',
    'sha512',
    'ripemd160',
    'hash160',
    'tagged_hash',
    'hmac_sha256',
    'hmac_sha512',

    # Hash functions (SHA-3)
    'sha3_256',
    'sha3_256d',
    'sha3_512',
    'shake256',
    'hmac_sha3_256',

    # Digital signatures
    'Ed25519',

    # Key exchange
    'X25519',

    # VRF
    'ECVRF',
    'VRFOutput',

    # VDF (Wesolowski)
    'WesolowskiVDF',
    'VDFProof',
    'VDFCheckpoint',
    'VDFSetupParameters',
    'VDFTrustedSetup',

    # VDF (SHAKE256 - quantum-resistant)
    'SHAKE256VDF',

    # Merkle trees
    'MerkleTree',

    # STARK proofs
    'STARKProver',

    # Crypto providers
    'CryptoProvider',
    'CryptoBackend',
    'LegacyCryptoProvider',
    'PostQuantumCryptoProvider',
    'HybridCryptoProvider',
    'get_crypto_provider',
    'set_default_backend',
    'get_default_backend',

    # Exceptions
    'CryptoError',
    'VDFError',
    'VRFError',
    'SignatureError',
    'TrustedSetupError',

    # Utilities
    'secure_random_bytes',
    'constant_time_compare',
    'int_to_bytes',
    'bytes_to_int',
    'secure_zero',

    # Availability flags
    'NACL_AVAILABLE',
    'PYCRYPTODOME_AVAILABLE',
    'CRYPTOGRAPHY_AVAILABLE',
    'USE_GMP_VDF',
    'LIBOQS_AVAILABLE',
    'MLKEM_AVAILABLE',
    'WINTERFELL_AVAILABLE',
]
