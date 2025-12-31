"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                            PLUTUS - GOD OF WEALTH                             ║
║                                                                               ║
║       Cryptocurrency wallet with HD derivation, stealth addresses,           ║
║       encrypted storage, and privacy-preserving transactions.                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  CORE COMPONENTS:                                                             ║
║  ─────────────────                                                            ║
║  - Wallet:           Main wallet interface for balance and transactions       ║
║  - WalletOutput:     UTXO representation with stealth key management          ║
║  - WalletTransaction: Transaction history record                              ║
║  - WalletCrypto:     AES-256-GCM encryption with Argon2id KDF                 ║
║  - KeyDerivation:    HD key derivation (BIP32-like) and subaddresses          ║
║                                                                               ║
║  SECURITY FEATURES:                                                           ║
║  ──────────────────                                                           ║
║  - Argon2id key derivation (OWASP recommended, GPU/ASIC resistant)            ║
║  - AES-256-GCM authenticated encryption                                       ║
║  - Stealth addresses (one-time keys per transaction)                          ║
║  - Key images prevent double-spending                                         ║
║  - Encrypted wallet storage with password protection                          ║
║                                                                               ║
║  PRIVACY FEATURES:                                                            ║
║  ─────────────────                                                            ║
║  - Stealth addresses: Receiver privacy (unlinkable outputs)                   ║
║  - Ring signatures: Sender privacy (plausible deniability)                    ║
║  - Pedersen commitments: Amount hiding                                        ║
║  - Bulletproofs: Range proofs (compact, no trusted setup)                     ║
║                                                                               ║
║  CRITICAL SECURITY NOTES:                                                     ║
║  ────────────────────────                                                     ║
║  1. Always use strong passwords (minimum 8 characters enforced)               ║
║  2. Backup seed phrase securely - loss = loss of funds                        ║
║  3. Keep wallet file encrypted at rest                                        ║
║  4. Verify addresses before sending                                           ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .wallet import (
    # Main wallet class
    Wallet,

    # Data structures
    WalletOutput,
    WalletTransaction,
    OutputStatus,

    # Encryption and key derivation
    WalletCrypto,
    KeyDerivation,

    # Constants
    WALLET_VERSION,
    KEY_DERIVATION_ROUNDS,
    SALT_SIZE,
    NONCE_SIZE,
    TAG_SIZE,

    # Argon2 parameters
    ARGON2_TIME_COST,
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_HASH_LEN,

    # Scrypt fallback parameters
    SCRYPT_N,
    SCRYPT_R,
    SCRYPT_P,

    # Availability flags
    CRYPTO_AVAILABLE,
    ARGON2_AVAILABLE,
)

__all__ = [
    # Main wallet
    'Wallet',

    # Data structures
    'WalletOutput',
    'WalletTransaction',
    'OutputStatus',

    # Encryption
    'WalletCrypto',
    'KeyDerivation',

    # Constants
    'WALLET_VERSION',
    'KEY_DERIVATION_ROUNDS',
    'SALT_SIZE',
    'NONCE_SIZE',
    'TAG_SIZE',

    # KDF parameters
    'ARGON2_TIME_COST',
    'ARGON2_MEMORY_COST',
    'ARGON2_PARALLELISM',
    'ARGON2_HASH_LEN',
    'SCRYPT_N',
    'SCRYPT_R',
    'SCRYPT_P',

    # Availability
    'CRYPTO_AVAILABLE',
    'ARGON2_AVAILABLE',
]
