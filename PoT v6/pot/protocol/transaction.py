"""
PoT Protocol v6 Transaction Protocol
Part VIII of Technical Specification

Transaction creation and validation with personal PoW.
"""

from __future__ import annotations
import logging
from typing import Optional

from pot.constants import (
    PROTOCOL_VERSION,
    TX_EPOCH_DURATION_SEC,
    BTC_MAX_DRIFT_BLOCKS,
    MEMO_MAX_SIZE,
)
from pot.core.types import Hash, PublicKey, KeyPair, empty_signature
from pot.core.transaction import Transaction
from pot.core.state import AccountState, GlobalState
from pot.core.serialization import pad_to_size
from pot.layers.layer0 import query_atomic_time
from pot.layers.layer2 import query_bitcoin
from pot.crypto.sphincs import sphincs_sign, sphincs_verify
from pot.crypto.pow import (
    compute_transaction_pow,
    verify_transaction_pow,
    get_personal_difficulty,
)
from pot.protocol.rate_limit import get_rate_tracker
from pot.errors import (
    SenderNotFoundError,
    InsufficientBalanceError,
    InvalidNonceError,
    ZeroAmountError,
    InsufficientPOWDifficultyError,
    InvalidPOWError,
    InvalidTxSignatureError,
    TransactionExpiredError,
    InvalidMemoLengthError,
    BitcoinHeightTooOldError,
)

logger = logging.getLogger(__name__)


async def create_transaction(
    keypair: KeyPair,
    receiver: PublicKey,
    amount: int,
    state: GlobalState,
    memo: bytes = b""
) -> Transaction:
    """
    Create a new signed transaction with personal PoW.

    Per specification (Part VIII):
    1. Query time sources
    2. Get sender account state
    3. Calculate PoW difficulty
    4. Compute PoW
    5. Sign transaction

    Args:
        keypair: Sender's key pair
        receiver: Receiver's public key
        amount: Amount to transfer (atomic units)
        state: Current global state
        memo: Optional memo (max 256 bytes)

    Returns:
        Complete signed Transaction

    Raises:
        SenderNotFoundError: If sender account doesn't exist
        InsufficientBalanceError: If sender doesn't have enough balance
        InvalidMemoLengthError: If memo exceeds 256 bytes
    """
    if amount == 0:
        raise ZeroAmountError()

    if len(memo) > MEMO_MAX_SIZE:
        raise InvalidMemoLengthError(len(memo), MEMO_MAX_SIZE)

    # Query time sources
    atomic_time = await query_atomic_time()
    btc = await query_bitcoin()

    # Get sender account
    account = state.get_account(keypair.public)
    if account is None:
        raise SenderNotFoundError(keypair.public.data)

    if account.balance < amount:
        raise InsufficientBalanceError(account.balance, amount)

    nonce = account.nonce + 1
    epoch = atomic_time.timestamp_ms // (TX_EPOCH_DURATION_SEC * 1000)

    # Calculate PoW difficulty
    difficulty = get_personal_difficulty(
        account.epoch_tx_count,
        account.second_tx_count
    )

    # Create unsigned transaction
    tx = Transaction(
        version=PROTOCOL_VERSION,
        sender=keypair.public,
        receiver=receiver,
        amount=amount,
        atomic_timestamp_ms=atomic_time.timestamp_ms,
        atomic_source_bitmap=atomic_time.region_bitmap,
        btc_height=btc.height,
        btc_hash=btc.block_hash,
        pow_difficulty=difficulty,
        pow_nonce=bytes(8),
        pow_hash=Hash.zero(),
        nonce=nonce,
        epoch=epoch,
        memo=pad_to_size(memo, MEMO_MAX_SIZE),
        memo_length=len(memo),
        signature=empty_signature()
    )

    # Compute PoW
    tx_data = tx.serialize_for_pow()
    pow_hash, pow_nonce = compute_transaction_pow(
        tx_data,
        keypair.public.data,
        nonce,
        difficulty
    )

    # Update transaction with PoW
    tx = Transaction(
        version=tx.version,
        sender=tx.sender,
        receiver=tx.receiver,
        amount=tx.amount,
        atomic_timestamp_ms=tx.atomic_timestamp_ms,
        atomic_source_bitmap=tx.atomic_source_bitmap,
        btc_height=tx.btc_height,
        btc_hash=tx.btc_hash,
        pow_difficulty=difficulty,
        pow_nonce=pow_nonce,
        pow_hash=Hash(pow_hash),
        nonce=tx.nonce,
        epoch=tx.epoch,
        memo=tx.memo,
        memo_length=tx.memo_length,
        signature=empty_signature()
    )

    # Sign
    message = tx.serialize_for_signing()
    signature = sphincs_sign(keypair.secret, message)

    # Update with signature
    tx = Transaction(
        version=tx.version,
        sender=tx.sender,
        receiver=tx.receiver,
        amount=tx.amount,
        atomic_timestamp_ms=tx.atomic_timestamp_ms,
        atomic_source_bitmap=tx.atomic_source_bitmap,
        btc_height=tx.btc_height,
        btc_hash=tx.btc_hash,
        pow_difficulty=tx.pow_difficulty,
        pow_nonce=tx.pow_nonce,
        pow_hash=tx.pow_hash,
        nonce=tx.nonce,
        epoch=tx.epoch,
        memo=tx.memo,
        memo_length=tx.memo_length,
        signature=signature
    )

    return tx


def create_transaction_sync(
    keypair: KeyPair,
    receiver: PublicKey,
    amount: int,
    state: GlobalState,
    memo: bytes = b""
) -> Transaction:
    """Synchronous wrapper for create_transaction."""
    import asyncio
    return asyncio.run(create_transaction(keypair, receiver, amount, state, memo))


async def validate_transaction(tx: Transaction, state: GlobalState) -> bool:
    """
    Validate a transaction against all protocol rules.

    Per specification (Part VIII):
    1. Basic checks (amount > 0, sender exists, balance)
    2. Replay protection (nonce)
    3. Time checks (Layer 0)
    4. Bitcoin checks (Layer 2)
    5. Personal PoW verification
    6. Signature verification

    Args:
        tx: Transaction to validate
        state: Current global state

    Returns:
        True if transaction is valid
    """
    try:
        await validate_transaction_strict(tx, state)
        return True
    except Exception as e:
        logger.debug(f"Transaction validation failed: {e}")
        return False


async def validate_transaction_strict(tx: Transaction, state: GlobalState) -> None:
    """
    Strictly validate transaction, raising exceptions on failure.
    """
    # === BASIC CHECKS ===

    if tx.amount == 0:
        raise ZeroAmountError()

    sender_account = state.get_account(tx.sender)
    if sender_account is None:
        raise SenderNotFoundError(tx.sender.data)

    if sender_account.balance < tx.amount:
        raise InsufficientBalanceError(sender_account.balance, tx.amount)

    # === REPLAY PROTECTION ===

    if tx.nonce != sender_account.nonce + 1:
        raise InvalidNonceError(tx.nonce, sender_account.nonce + 1)

    # === LAYER 0: TIME CHECK ===

    current_time = await query_atomic_time()
    time_diff = abs(tx.atomic_timestamp_ms - current_time.timestamp_ms)
    max_age_ms = TX_EPOCH_DURATION_SEC * 1000  # 10 minutes

    if time_diff > max_age_ms:
        raise TransactionExpiredError(time_diff, max_age_ms)

    # === LAYER 2: BITCOIN CHECK ===

    current_btc = await query_bitcoin()
    if current_btc.height - tx.btc_height > BTC_MAX_DRIFT_BLOCKS:
        raise BitcoinHeightTooOldError(
            tx.btc_height,
            current_btc.height,
            BTC_MAX_DRIFT_BLOCKS
        )

    # === PERSONAL POW ===

    expected_difficulty = get_personal_difficulty(
        sender_account.epoch_tx_count,
        sender_account.second_tx_count
    )

    if tx.pow_difficulty < expected_difficulty:
        raise InsufficientPOWDifficultyError(tx.pow_difficulty, expected_difficulty)

    tx_data = tx.serialize_for_pow()
    if not verify_transaction_pow(
        tx_data,
        tx.sender.data,
        tx.nonce,
        tx.pow_hash.data,
        tx.pow_nonce,
        tx.pow_difficulty
    ):
        raise InvalidPOWError()

    # === SIGNATURE ===

    message = tx.serialize_for_signing()
    if not sphincs_verify(tx.sender, message, tx.signature):
        raise InvalidTxSignatureError()


def validate_transaction_basic(tx: Transaction) -> bool:
    """
    Perform basic structural validation (no state or network required).

    Checks:
    - Version is correct
    - Amount > 0
    - Memo length is valid
    - PoW hash and nonce are present
    """
    # Version check
    if tx.version != PROTOCOL_VERSION:
        logger.debug(f"Invalid version: {tx.version}")
        return False

    # Amount check
    if tx.amount == 0:
        logger.debug("Zero amount")
        return False

    # Memo check
    if tx.memo_length > MEMO_MAX_SIZE:
        logger.debug(f"Invalid memo length: {tx.memo_length}")
        return False

    # PoW fields present
    if tx.pow_hash == Hash.zero():
        logger.debug("Missing PoW hash")
        return False

    if tx.pow_nonce == bytes(8):
        logger.debug("Missing PoW nonce")
        return False

    return True


def validate_transaction_sync(tx: Transaction, state: GlobalState) -> bool:
    """Synchronous wrapper for validate_transaction."""
    import asyncio
    return asyncio.run(validate_transaction(tx, state))


def serialize_tx_for_signing(tx: Transaction) -> bytes:
    """Serialize transaction for signing."""
    return tx.serialize_for_signing()


def serialize_tx_for_pow(tx: Transaction) -> bytes:
    """Serialize transaction for PoW computation."""
    return tx.serialize_for_pow()
