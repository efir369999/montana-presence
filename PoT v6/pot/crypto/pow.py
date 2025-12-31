"""
PoT Protocol v6 Personal Proof of Work
Part IX of Technical Specification

Two-stage ASIC-resistant PoW for transaction rate limiting:
- Stage 1: Argon2id (memory-hard, 64 MB)
- Stage 2: RandomX (random execution, CPU-optimized)

PRINCIPLE: "Your spam is your problem, not the network's."
"""

from __future__ import annotations
import logging
from typing import Tuple, Optional
import hashlib
import struct

from pot.constants import (
    POW_BASE_DIFFICULTY_BITS,
    POW_EXCESS_PENALTY_BITS,
    POW_BURST_PENALTY_BITS,
    POW_MAX_DIFFICULTY_BITS,
    POW_MEMORY_COST_KB,
    POW_TIME_COST,
    POW_PARALLELISM,
    TX_FREE_PER_EPOCH,
)
from pot.core.types import Hash, PublicKey
from pot.crypto.hash import sha3_256

logger = logging.getLogger(__name__)

# Try to import argon2
_ARGON2_AVAILABLE = False
_argon2 = None

try:
    import argon2
    from argon2.low_level import hash_secret_raw, Type
    _argon2 = argon2
    _ARGON2_AVAILABLE = True
except ImportError:
    logger.warning("argon2-cffi not available. Install with: pip install argon2-cffi")

# Try to import RandomX
_RANDOMX_AVAILABLE = False
_pot_randomx = None

try:
    import pot_randomx
    _pot_randomx = pot_randomx
    _RANDOMX_AVAILABLE = True
    logger.info(f"pot_randomx available (v{pot_randomx.version()})")
except ImportError:
    logger.warning(
        "pot_randomx not available. "
        "Build with: cd rust/randomx && maturin develop"
    )


def get_personal_difficulty(
    epoch_tx_count: int,
    second_tx_count: int
) -> int:
    """
    Calculate personal PoW difficulty based on usage patterns.

    Per specification (Part IX):
    - Base difficulty: 16 bits (~65ms)
    - +2 bits per transaction beyond free tier (10/epoch)
    - +4 bits per transaction in same second (burst penalty)
    - Maximum: 32 bits (~18 hours)

    Args:
        epoch_tx_count: Transactions sent in current epoch
        second_tx_count: Transactions sent in current second

    Returns:
        Required difficulty in bits
    """
    # Base difficulty
    difficulty = POW_BASE_DIFFICULTY_BITS

    # Epoch penalty: +2 bits per excess transaction
    if epoch_tx_count >= TX_FREE_PER_EPOCH:
        excess = epoch_tx_count - TX_FREE_PER_EPOCH + 1
        difficulty += excess * POW_EXCESS_PENALTY_BITS

    # Burst penalty: +4 bits per same-second transaction
    if second_tx_count > 0:
        difficulty += second_tx_count * POW_BURST_PENALTY_BITS

    return min(difficulty, POW_MAX_DIFFICULTY_BITS)


def compute_argon2id(
    data: bytes,
    salt: bytes,
    output_length: int = 32
) -> bytes:
    """
    Compute Argon2id hash.

    Per specification (Part XII):
    - Memory cost: 64 MB
    - Time cost: 1 iteration
    - Parallelism: 1 lane

    Args:
        data: Input data (password)
        salt: Salt value (32 bytes recommended)
        output_length: Output length in bytes

    Returns:
        Argon2id hash output
    """
    if _ARGON2_AVAILABLE:
        from argon2.low_level import hash_secret_raw, Type
        return hash_secret_raw(
            secret=data,
            salt=salt,
            time_cost=POW_TIME_COST,
            memory_cost=POW_MEMORY_COST_KB,
            parallelism=POW_PARALLELISM,
            hash_len=output_length,
            type=Type.ID
        )
    else:
        # Fallback: Use SHAKE256 (NOT memory-hard - for testing only)
        logger.warning("Using SHAKE256 fallback for Argon2id (NOT SECURE)")
        hasher = hashlib.shake_256()
        hasher.update(b"ARGON2ID_FALLBACK:")
        hasher.update(data)
        hasher.update(salt)
        return hasher.digest(output_length)


def compute_randomx(data: bytes) -> bytes:
    """
    Compute RandomX hash.

    RandomX is designed to be optimal on CPUs and resistant to
    ASIC/FPGA optimization.

    Args:
        data: Input data to hash

    Returns:
        32-byte RandomX hash
    """
    if _RANDOMX_AVAILABLE and _pot_randomx.is_initialized():
        return bytes(_pot_randomx.randomx_hash(data))
    else:
        # Fallback: Use SHA3-256 (NOT ASIC-resistant - for testing only)
        logger.debug("Using SHA3-256 fallback for RandomX")
        return sha3_256(b"RANDOMX_FALLBACK:" + data).data


def init_randomx(epoch_key: bytes, full_mem: bool = False):
    """
    Initialize RandomX VM with epoch key.

    Should be called once per epoch. The key is typically derived
    from the Bitcoin block at epoch start.

    Args:
        epoch_key: Key for RandomX initialization
        full_mem: Use full memory mode (2GB, faster but more RAM)
    """
    if _RANDOMX_AVAILABLE:
        _pot_randomx.init_vm(epoch_key, full_mem)
        logger.info(f"RandomX initialized with key: {epoch_key.hex()[:16]}...")
    else:
        logger.warning("RandomX not available, using fallback")


def compute_transaction_pow(
    tx_data: bytes,
    sender_pubkey: bytes,
    nonce: int,
    difficulty: int
) -> Tuple[bytes, bytes]:
    """
    Compute two-stage ASIC-resistant PoW for transactions.

    Per specification (Part IX):
    Stage 1: Argon2id (memory-hard, 64 MB)
    Stage 2: RandomX (random execution, CPU-optimized)

    Args:
        tx_data: Serialized transaction data (without PoW fields)
        sender_pubkey: Sender's public key bytes
        nonce: Transaction nonce
        difficulty: Required difficulty in bits

    Returns:
        Tuple of (argon2_hash, pow_nonce) where pow_nonce solves the puzzle
    """
    # Generate salt from sender + nonce
    salt = sha3_256(sender_pubkey + nonce.to_bytes(8, "big")).data

    # Stage 1: Memory-hard hash
    argon_hash = compute_argon2id(tx_data, salt)

    # Stage 2: RandomX mining
    target = (1 << 256) // (1 << difficulty)  # 2^(256-difficulty)
    pow_nonce = 0

    while True:
        # Combine argon hash with nonce
        input_data = argon_hash + pow_nonce.to_bytes(8, "big")
        hash_output = compute_randomx(input_data)

        # Check if hash meets difficulty
        hash_value = int.from_bytes(hash_output, "big")
        if hash_value < target:
            return argon_hash, pow_nonce.to_bytes(8, "big")

        pow_nonce += 1

        if pow_nonce > 0xFFFFFFFFFFFFFFFF:
            raise RuntimeError("PoW nonce exhausted")

        # Progress logging for high difficulty
        if pow_nonce % 100000 == 0:
            logger.debug(f"PoW mining: nonce={pow_nonce}, difficulty={difficulty}")


def verify_transaction_pow(
    tx_data: bytes,
    sender_pubkey: bytes,
    nonce: int,
    pow_hash: bytes,
    pow_nonce: bytes,
    difficulty: int
) -> bool:
    """
    Verify transaction proof of work.

    Args:
        tx_data: Serialized transaction data (without PoW fields)
        sender_pubkey: Sender's public key bytes
        nonce: Transaction nonce
        pow_hash: Argon2id hash from transaction
        pow_nonce: PoW nonce from transaction
        difficulty: Required difficulty in bits

    Returns:
        True if PoW is valid
    """
    # Recompute Argon2id
    salt = sha3_256(sender_pubkey + nonce.to_bytes(8, "big")).data
    expected_argon = compute_argon2id(tx_data, salt)

    if pow_hash != expected_argon:
        logger.debug("Argon2id hash mismatch")
        return False

    # Verify RandomX
    input_data = pow_hash + pow_nonce
    hash_output = compute_randomx(input_data)

    target = (1 << 256) // (1 << difficulty)
    hash_value = int.from_bytes(hash_output, "big")

    if hash_value >= target:
        logger.debug(f"RandomX hash doesn't meet difficulty: {hash_value} >= {target}")
        return False

    return True


def estimate_pow_time(difficulty: int) -> float:
    """
    Estimate PoW computation time in seconds.

    Based on difficulty table from specification:
    - 16 bits: ~65ms
    - Each additional bit doubles the time

    Args:
        difficulty: Difficulty in bits

    Returns:
        Estimated time in seconds
    """
    base_time = 0.065  # 65ms for 16 bits
    extra_bits = difficulty - POW_BASE_DIFFICULTY_BITS
    return base_time * (2 ** extra_bits)


def get_pow_info() -> dict:
    """Get information about PoW implementation."""
    return {
        "stage1": "Argon2id",
        "stage1_available": _ARGON2_AVAILABLE,
        "stage1_memory_kb": POW_MEMORY_COST_KB,
        "stage1_time_cost": POW_TIME_COST,
        "stage1_parallelism": POW_PARALLELISM,
        "stage2": "RandomX",
        "stage2_available": _RANDOMX_AVAILABLE,
        "stage2_initialized": _RANDOMX_AVAILABLE and _pot_randomx.is_initialized() if _RANDOMX_AVAILABLE else False,
        "base_difficulty": POW_BASE_DIFFICULTY_BITS,
        "max_difficulty": POW_MAX_DIFFICULTY_BITS,
        "free_tx_per_epoch": TX_FREE_PER_EPOCH,
        "excess_penalty_bits": POW_EXCESS_PENALTY_BITS,
        "burst_penalty_bits": POW_BURST_PENALTY_BITS,
    }


# Difficulty estimation table (from specification)
DIFFICULTY_TABLE = [
    # (tx_per_epoch, difficulty, est_time, status)
    (1, 16, "~65ms", "FREE"),
    (10, 16, "~65ms", "FREE"),
    (11, 18, "~260ms", "+1 excess"),
    (12, 20, "~1 sec", "+2 excess"),
    (13, 22, "~4 sec", "+3 excess"),
    (14, 24, "~16 sec", "+4 excess"),
    (15, 26, "~1 min", "+5 excess"),
    (16, 28, "~4 min", "+6 excess"),
    (17, 30, "~17 min", "+7 excess"),
    (18, 32, "~18 hours", "MAX"),
]


def print_difficulty_table():
    """Print the difficulty table for reference."""
    print("\nPoT Personal PoW Difficulty Table")
    print("=" * 60)
    print(f"{'TX/Epoch':<12} {'Difficulty':<12} {'Est. Time':<15} {'Status':<15}")
    print("-" * 60)
    for tx, diff, time_est, status in DIFFICULTY_TABLE:
        print(f"{tx:<12} {diff:<12} {time_est:<15} {status:<15}")
    print("=" * 60)
    print("Burst penalty (same second): +4 bits per additional transaction")
    print()
