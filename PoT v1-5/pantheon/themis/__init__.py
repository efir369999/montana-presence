"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         THEMIS - GODDESS OF VALIDATION                        ║
║                                                                               ║
║       Block and transaction structures with full serialization,               ║
║       validation rules, and Merkle tree computation.                          ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  CORE STRUCTURES:                                                             ║
║  ─────────────────                                                            ║
║  - Block:           Complete block with header and transactions               ║
║  - BlockHeader:     Block metadata (hash, height, timestamps, proofs)         ║
║  - Transaction:     Ring signature transaction with inputs/outputs            ║
║  - TxInput:         Transaction input with ring signature                     ║
║  - TxOutput:        Transaction output with stealth address                   ║
║  - TxType:          Transaction type enumeration                              ║
║                                                                               ║
║  VALIDATION:                                                                  ║
║  ───────────                                                                  ║
║  - BlockValidator:  Full block validation (structure, proofs, Merkle)         ║
║  - BlockValidationError: Validation error with details                        ║
║                                                                               ║
║  UTILITIES:                                                                   ║
║  ──────────                                                                   ║
║  - Serializable:    Base class for serialization                              ║
║  - write_varint/read_varint: Bitcoin-style variable integers                  ║
║  - write_bytes/read_bytes: Length-prefixed byte arrays                        ║
║  - create_genesis_block: Genesis block creation                               ║
║                                                                               ║
║  TRANSACTION TYPES:                                                           ║
║  ──────────────────                                                           ║
║  - COINBASE:          Block reward                                            ║
║  - STANDARD:          Regular transfer                                        ║
║  - APOSTLE_HANDSHAKE: 12 Apostles mutual trust                                ║
║  - EPOCH_PROOF:       Bitcoin halving survival proof                          ║
║  - BTC_ANCHOR:        Bitcoin timestamp anchor                                ║
║  - RHEUMA_CHECKPOINT: Blockless stream checkpoint                             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .structures import (
    # Base serialization
    Serializable,
    write_varint,
    read_varint,
    write_bytes,
    read_bytes,

    # Transaction structures
    TxType,
    TxInput,
    TxOutput,
    Transaction,

    # Block structures
    BlockHeader,
    Block,

    # Validation
    BlockValidator,
    BlockValidationError,

    # Genesis
    create_genesis_block,
)

__all__ = [
    # Base
    'Serializable',
    'write_varint',
    'read_varint',
    'write_bytes',
    'read_bytes',

    # Transactions
    'TxType',
    'TxInput',
    'TxOutput',
    'Transaction',

    # Blocks
    'BlockHeader',
    'Block',

    # Validation
    'BlockValidator',
    'BlockValidationError',

    # Genesis
    'create_genesis_block',
]
