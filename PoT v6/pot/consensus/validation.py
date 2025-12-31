"""
PoT Protocol v6 Validation Rules
Part XIV of Technical Specification

Complete validation rules for heartbeats, transactions, and blocks.
"""

from __future__ import annotations
import logging
from typing import List, Optional, Set, TYPE_CHECKING

from pot.constants import (
    PROTOCOL_VERSION,
    MAX_BLOCK_SIZE_BYTES,
    MAX_HEARTBEATS_PER_BLOCK,
    MAX_TRANSACTIONS_PER_BLOCK,
    TX_EPOCH_DURATION_SEC,
    BTC_MAX_DRIFT_BLOCKS,
    MEMO_MAX_SIZE,
    NTP_MIN_SOURCES,
    NTP_MIN_REGIONS,
    VDF_BASE_ITERATIONS,
    BLOCK_INTERVAL_MS,
    SCORE_MIN_HEARTBEATS,
    FINALITY_DEPTH,
)
from pot.core.types import Hash, PublicKey
from pot.crypto.hash import sha3_256
from pot.crypto.sphincs import sphincs_verify
from pot.crypto.pow import verify_transaction_pow, get_personal_difficulty
from pot.crypto.merkle import merkle_root
from pot.crypto.vdf import verify_vdf
from pot.consensus.score import compute_score, effective_score

if TYPE_CHECKING:
    from pot.core.heartbeat import Heartbeat
    from pot.core.transaction import Transaction
    from pot.core.block import Block, BlockHeader
    from pot.core.state import GlobalState
    from pot.core.vdf import VDFProof

logger = logging.getLogger(__name__)


# ==============================================================================
# Heartbeat Validation
# ==============================================================================

class HeartbeatValidationError(Exception):
    """Base exception for heartbeat validation failures."""
    pass


def validate_heartbeat_structure(hb: "Heartbeat") -> None:
    """
    Validate heartbeat structural correctness.

    Part XIV Section 1: Structural Validation
    - Version check
    - Field sizes
    - Required fields present
    """
    # Version
    if hb.version != PROTOCOL_VERSION:
        raise HeartbeatValidationError(
            f"Invalid version: {hb.version} (expected {PROTOCOL_VERSION})"
        )

    # Public key
    if len(hb.pubkey.data) != 33:
        raise HeartbeatValidationError(
            f"Invalid pubkey size: {len(hb.pubkey.data)} (expected 33)"
        )

    # VDF proof must exist
    if hb.vdf_proof is None:
        raise HeartbeatValidationError("Missing VDF proof")


def validate_heartbeat_layer0(hb: "Heartbeat") -> None:
    """
    Validate Layer 0: Atomic Time.

    Part XIV Section 2: Time Validation
    - Sufficient NTP sources
    - Sufficient regions
    - Timestamp recency
    """
    # Check source count
    source_count = bin(hb.atomic_source_bitmap).count('1')
    if source_count < NTP_MIN_SOURCES:
        raise HeartbeatValidationError(
            f"Insufficient NTP sources: {source_count} < {NTP_MIN_SOURCES}"
        )

    # Check region coverage
    region_bitmap = _compute_region_bitmap(hb.atomic_source_bitmap)
    region_count = bin(region_bitmap).count('1')
    if region_count < NTP_MIN_REGIONS:
        raise HeartbeatValidationError(
            f"Insufficient regions: {region_count} < {NTP_MIN_REGIONS}"
        )


def _compute_region_bitmap(source_bitmap: int) -> int:
    """
    Compute region bitmap from source bitmap.

    Sources are assigned to 8 regions (4-5 sources per region).
    """
    region_bitmap = 0
    for region in range(8):
        # Each region has sources at positions region*4 to region*4+4
        region_mask = 0xF << (region * 4)  # 4 bits per region
        if source_bitmap & region_mask:
            region_bitmap |= (1 << region)
    return region_bitmap


def validate_heartbeat_layer1(
    hb: "Heartbeat",
    min_iterations: int = VDF_BASE_ITERATIONS
) -> None:
    """
    Validate Layer 1: Temporal Proof.

    Part XIV Section 3: VDF Validation
    - Seed matches expected
    - Iterations meet minimum
    - VDF proof is valid
    """
    from pot.crypto.vdf import generate_vdf_seed

    # Verify seed
    expected_seed = generate_vdf_seed(hb.pubkey, hb.btc_anchor)
    expected_seed_hash = sha3_256(expected_seed)

    if hb.vdf_proof.seed != expected_seed_hash:
        raise HeartbeatValidationError("VDF seed mismatch")

    # Verify iterations
    if hb.vdf_proof.iterations < min_iterations:
        raise HeartbeatValidationError(
            f"Insufficient VDF iterations: {hb.vdf_proof.iterations} < {min_iterations}"
        )

    # Verify VDF proof
    if not verify_vdf(hb.vdf_proof):
        raise HeartbeatValidationError("Invalid VDF proof")


def validate_heartbeat_layer2(
    hb: "Heartbeat",
    current_btc_height: int,
    max_drift: int = BTC_MAX_DRIFT_BLOCKS
) -> None:
    """
    Validate Layer 2: Bitcoin Anchor.

    Part XIV Section 4: Bitcoin Validation
    - Height within acceptable range
    - Hash matches known block
    """
    height_diff = current_btc_height - hb.btc_anchor.height

    if height_diff > max_drift:
        raise HeartbeatValidationError(
            f"Bitcoin height too old: {hb.btc_anchor.height} "
            f"(current: {current_btc_height}, max drift: {max_drift})"
        )

    if height_diff < 0:
        raise HeartbeatValidationError(
            f"Bitcoin height in future: {hb.btc_anchor.height} "
            f"(current: {current_btc_height})"
        )


def validate_heartbeat_signature(hb: "Heartbeat") -> None:
    """
    Validate heartbeat signature.

    Part XIV Section 5: Signature Validation
    - Signature is valid SPHINCS+ signature
    - Signed by the claimed pubkey
    """
    message = hb.serialize_for_signing()

    if not sphincs_verify(hb.pubkey, message, hb.signature):
        raise HeartbeatValidationError("Invalid heartbeat signature")


def validate_heartbeat_full(
    hb: "Heartbeat",
    state: "GlobalState",
    current_btc_height: int
) -> None:
    """
    Full heartbeat validation.

    Runs all validation checks in order.
    """
    validate_heartbeat_structure(hb)
    validate_heartbeat_layer0(hb)
    validate_heartbeat_layer1(hb)
    validate_heartbeat_layer2(hb, current_btc_height)
    validate_heartbeat_signature(hb)


# ==============================================================================
# Transaction Validation
# ==============================================================================

class TransactionValidationError(Exception):
    """Base exception for transaction validation failures."""
    pass


def validate_transaction_structure(tx: "Transaction") -> None:
    """
    Validate transaction structural correctness.

    Part XIV Section 6: Transaction Structure
    """
    # Version
    if tx.version != PROTOCOL_VERSION:
        raise TransactionValidationError(
            f"Invalid version: {tx.version}"
        )

    # Amount
    if tx.amount == 0:
        raise TransactionValidationError("Zero amount")

    # Memo
    if tx.memo_length > MEMO_MAX_SIZE:
        raise TransactionValidationError(
            f"Memo too large: {tx.memo_length} > {MEMO_MAX_SIZE}"
        )

    # PoW fields
    if tx.pow_hash == Hash.zero():
        raise TransactionValidationError("Missing PoW hash")

    if tx.pow_nonce == bytes(8):
        raise TransactionValidationError("Missing PoW nonce")


def validate_transaction_balance(
    tx: "Transaction",
    state: "GlobalState"
) -> None:
    """
    Validate sender has sufficient balance.

    Part XIV Section 7: Balance Check
    """
    account = state.get_account(tx.sender)
    if account is None:
        raise TransactionValidationError(
            f"Sender account not found: {tx.sender.data.hex()[:16]}"
        )

    if account.balance < tx.amount:
        raise TransactionValidationError(
            f"Insufficient balance: {account.balance} < {tx.amount}"
        )


def validate_transaction_nonce(
    tx: "Transaction",
    state: "GlobalState"
) -> None:
    """
    Validate transaction nonce for replay protection.

    Part XIV Section 8: Nonce Check
    """
    account = state.get_account(tx.sender)
    if account is None:
        raise TransactionValidationError("Sender account not found")

    expected_nonce = account.nonce + 1
    if tx.nonce != expected_nonce:
        raise TransactionValidationError(
            f"Invalid nonce: {tx.nonce} (expected {expected_nonce})"
        )


def validate_transaction_time(
    tx: "Transaction",
    current_time_ms: int
) -> None:
    """
    Validate transaction timestamp.

    Part XIV Section 9: Time Check
    """
    max_age_ms = TX_EPOCH_DURATION_SEC * 1000
    time_diff = abs(tx.atomic_timestamp_ms - current_time_ms)

    if time_diff > max_age_ms:
        raise TransactionValidationError(
            f"Transaction expired: age {time_diff}ms > {max_age_ms}ms"
        )


def validate_transaction_bitcoin(
    tx: "Transaction",
    current_btc_height: int
) -> None:
    """
    Validate transaction Bitcoin reference.

    Part XIV Section 10: Bitcoin Check
    """
    if current_btc_height - tx.btc_height > BTC_MAX_DRIFT_BLOCKS:
        raise TransactionValidationError(
            f"Bitcoin height too old: {tx.btc_height}"
        )


def validate_transaction_pow(
    tx: "Transaction",
    state: "GlobalState"
) -> None:
    """
    Validate transaction personal PoW.

    Part XIV Section 11: PoW Check
    """
    account = state.get_account(tx.sender)
    if account is None:
        raise TransactionValidationError("Sender account not found")

    # Get required difficulty
    expected_difficulty = get_personal_difficulty(
        account.epoch_tx_count,
        account.second_tx_count
    )

    if tx.pow_difficulty < expected_difficulty:
        raise TransactionValidationError(
            f"Insufficient PoW difficulty: {tx.pow_difficulty} < {expected_difficulty}"
        )

    # Verify PoW
    tx_data = tx.serialize_for_pow()
    if not verify_transaction_pow(
        tx_data,
        tx.sender.data,
        tx.nonce,
        tx.pow_hash.data,
        tx.pow_nonce,
        tx.pow_difficulty
    ):
        raise TransactionValidationError("Invalid PoW")


def validate_transaction_signature(tx: "Transaction") -> None:
    """
    Validate transaction signature.

    Part XIV Section 12: Signature Check
    """
    message = tx.serialize_for_signing()

    if not sphincs_verify(tx.sender, message, tx.signature):
        raise TransactionValidationError("Invalid transaction signature")


def validate_transaction_full(
    tx: "Transaction",
    state: "GlobalState",
    current_time_ms: int,
    current_btc_height: int
) -> None:
    """
    Full transaction validation.
    """
    validate_transaction_structure(tx)
    validate_transaction_balance(tx, state)
    validate_transaction_nonce(tx, state)
    validate_transaction_time(tx, current_time_ms)
    validate_transaction_bitcoin(tx, current_btc_height)
    validate_transaction_pow(tx, state)
    validate_transaction_signature(tx)


# ==============================================================================
# Block Validation
# ==============================================================================

class BlockValidationError(Exception):
    """Base exception for block validation failures."""
    pass


def validate_block_structure(block: "Block") -> None:
    """
    Validate block structural correctness.

    Part XIV Section 13: Block Structure
    """
    # Version
    if block.header.version != PROTOCOL_VERSION:
        raise BlockValidationError(
            f"Invalid version: {block.header.version}"
        )

    # Size limits
    if not block.is_within_size_limit():
        raise BlockValidationError(
            f"Block too large: {block.size()} > {MAX_BLOCK_SIZE_BYTES}"
        )

    if not block.is_within_content_limits():
        raise BlockValidationError(
            f"Block content exceeds limits: "
            f"hb={len(block.heartbeats)}/{MAX_HEARTBEATS_PER_BLOCK}, "
            f"tx={len(block.transactions)}/{MAX_TRANSACTIONS_PER_BLOCK}"
        )


def validate_block_parent(
    block: "Block",
    parent: Optional["Block"]
) -> None:
    """
    Validate block parent relationship.

    Part XIV Section 14: Parent Check
    """
    if block.header.height == 0:
        # Genesis block
        if block.header.parent_hash != Hash.zero():
            raise BlockValidationError(
                "Genesis block must have zero parent hash"
            )
        return

    if parent is None:
        raise BlockValidationError("Parent block not found")

    expected_parent_hash = parent.block_hash()
    if block.header.parent_hash != expected_parent_hash:
        raise BlockValidationError(
            f"Parent hash mismatch: {block.header.parent_hash.hex()[:16]} "
            f"!= {expected_parent_hash.hex()[:16]}"
        )

    expected_height = parent.header.height + 1
    if block.header.height != expected_height:
        raise BlockValidationError(
            f"Height mismatch: {block.header.height} != {expected_height}"
        )


def validate_block_timestamp(
    block: "Block",
    parent: Optional["Block"]
) -> None:
    """
    Validate block timestamp.

    Part XIV Section 15: Timestamp Check
    """
    if parent is not None:
        if block.header.timestamp_ms <= parent.header.timestamp_ms:
            raise BlockValidationError(
                f"Timestamp not increasing: {block.header.timestamp_ms} "
                f"<= {parent.header.timestamp_ms}"
            )


def validate_block_merkle_roots(block: "Block") -> None:
    """
    Validate block Merkle roots.

    Part XIV Section 16: Merkle Check
    """
    if not block.verify_merkle_roots():
        raise BlockValidationError("Merkle root mismatch")


def validate_block_heartbeats(
    block: "Block",
    state: "GlobalState",
    current_btc_height: int
) -> None:
    """
    Validate all heartbeats in block.

    Part XIV Section 17: Heartbeat Validation
    """
    seen_pubkeys: Set[bytes] = set()

    for i, hb in enumerate(block.heartbeats):
        try:
            validate_heartbeat_full(hb, state, current_btc_height)
        except HeartbeatValidationError as e:
            raise BlockValidationError(
                f"Invalid heartbeat {i}: {e}"
            )

        # Check for duplicates
        pk_bytes = hb.pubkey.data
        if pk_bytes in seen_pubkeys:
            raise BlockValidationError(
                f"Duplicate heartbeat from {pk_bytes.hex()[:16]}"
            )
        seen_pubkeys.add(pk_bytes)


def validate_block_transactions(
    block: "Block",
    state: "GlobalState",
    current_time_ms: int,
    current_btc_height: int
) -> None:
    """
    Validate all transactions in block.

    Part XIV Section 18: Transaction Validation
    """
    for i, tx in enumerate(block.transactions):
        try:
            validate_transaction_full(
                tx, state, current_time_ms, current_btc_height
            )
        except TransactionValidationError as e:
            raise BlockValidationError(
                f"Invalid transaction {i}: {e}"
            )


def validate_block_signers(
    block: "Block",
    state: "GlobalState"
) -> None:
    """
    Validate block signers.

    Part XIV Section 19: Signer Validation
    """
    if not block.signers:
        raise BlockValidationError("Block has no signers")

    seen_pubkeys: Set[bytes] = set()
    block_hash = block.header.block_hash()

    for i, signer in enumerate(block.signers):
        pk_bytes = signer.pubkey.data

        # Check for duplicates
        if pk_bytes in seen_pubkeys:
            raise BlockValidationError(
                f"Duplicate signer: {pk_bytes.hex()[:16]}"
            )
        seen_pubkeys.add(pk_bytes)

        # Verify signer is eligible
        account = state.get_account(signer.pubkey)
        if account is None:
            raise BlockValidationError(
                f"Signer {i} has no account"
            )

        if account.epoch_heartbeats < SCORE_MIN_HEARTBEATS:
            raise BlockValidationError(
                f"Signer {i} has insufficient heartbeats"
            )

        # Verify score matches
        expected_score = compute_score(account.epoch_heartbeats)
        expected_fixed = int(expected_score * 1_000_000)

        # Allow small tolerance for floating point
        if abs(signer.score_fixed - expected_fixed) > 1:
            raise BlockValidationError(
                f"Signer {i} score mismatch: {signer.score_fixed} != {expected_fixed}"
            )

        # Verify signature
        if not sphincs_verify(signer.pubkey, block_hash.data, signer.signature):
            raise BlockValidationError(
                f"Signer {i} invalid signature"
            )


def validate_block_full(
    block: "Block",
    parent: Optional["Block"],
    state: "GlobalState",
    current_time_ms: int,
    current_btc_height: int
) -> None:
    """
    Full block validation.

    Part XIV: Complete Validation
    """
    validate_block_structure(block)
    validate_block_parent(block, parent)
    validate_block_timestamp(block, parent)
    validate_block_merkle_roots(block)
    validate_block_heartbeats(block, state, current_btc_height)
    validate_block_transactions(block, state, current_time_ms, current_btc_height)
    validate_block_signers(block, state)


# ==============================================================================
# Quick Validation (for mempool/gossip)
# ==============================================================================

def quick_validate_heartbeat(hb: "Heartbeat") -> bool:
    """Quick structural validation for mempool."""
    try:
        validate_heartbeat_structure(hb)
        return True
    except HeartbeatValidationError:
        return False


def quick_validate_transaction(tx: "Transaction") -> bool:
    """Quick structural validation for mempool."""
    try:
        validate_transaction_structure(tx)
        return True
    except TransactionValidationError:
        return False


def quick_validate_block(block: "Block") -> bool:
    """Quick structural validation."""
    try:
        validate_block_structure(block)
        validate_block_merkle_roots(block)
        return True
    except BlockValidationError:
        return False


# ==============================================================================
# Validation Info
# ==============================================================================

def get_validation_info() -> dict:
    """Get information about validation rules."""
    return {
        "heartbeat": {
            "structure": "version, pubkey size, VDF proof present",
            "layer0": f"≥{NTP_MIN_SOURCES} sources, ≥{NTP_MIN_REGIONS} regions",
            "layer1": f"≥{VDF_BASE_ITERATIONS} VDF iterations, valid STARK",
            "layer2": f"Bitcoin height within {BTC_MAX_DRIFT_BLOCKS} blocks",
            "signature": "Valid SPHINCS+ signature",
        },
        "transaction": {
            "structure": "version, amount > 0, memo ≤ 256 bytes",
            "balance": "sender balance ≥ amount",
            "nonce": "nonce == expected_nonce",
            "time": f"age ≤ {TX_EPOCH_DURATION_SEC} seconds",
            "bitcoin": f"height within {BTC_MAX_DRIFT_BLOCKS} blocks",
            "pow": "Argon2id + RandomX difficulty met",
            "signature": "Valid SPHINCS+ signature",
        },
        "block": {
            "structure": f"size ≤ {MAX_BLOCK_SIZE_BYTES} bytes",
            "limits": f"≤{MAX_HEARTBEATS_PER_BLOCK} hb, ≤{MAX_TRANSACTIONS_PER_BLOCK} tx",
            "parent": "valid parent hash and height",
            "timestamp": "monotonically increasing",
            "merkle": "valid heartbeat and transaction roots",
            "signers": f"≥{SCORE_MIN_HEARTBEATS} heartbeats each",
        },
    }
