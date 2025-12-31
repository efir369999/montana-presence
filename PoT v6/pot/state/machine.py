"""
PoT Protocol v6 State Machine
Part XV of Technical Specification

State transitions: apply_heartbeat, apply_transaction, apply_block.
"""

from __future__ import annotations
import logging
import copy
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from pot.constants import (
    EPOCH_DURATION_BLOCKS,
    TX_EPOCH_DURATION_SEC,
    INITIAL_REWARD,
    BTC_HALVING_INTERVAL,
)
from pot.core.types import Hash, PublicKey
from pot.core.state import GlobalState, AccountState
from pot.crypto.hash import sha3_256
from pot.crypto.merkle import merkle_root

if TYPE_CHECKING:
    from pot.core.heartbeat import Heartbeat
    from pot.core.transaction import Transaction
    from pot.core.block import Block

logger = logging.getLogger(__name__)


class StateTransitionError(Exception):
    """Exception raised when a state transition fails."""
    pass


def apply_heartbeat(
    state: GlobalState,
    heartbeat: "Heartbeat",
    block_height: int
) -> GlobalState:
    """
    Apply a heartbeat to the state.

    Per specification (Part XV):
    1. Get or create account
    2. Increment epoch heartbeat count
    3. Update last heartbeat height
    4. Update global heartbeat count

    Args:
        state: Current global state
        heartbeat: Heartbeat to apply
        block_height: Current block height

    Returns:
        New state with heartbeat applied
    """
    new_state = state.copy()

    # Get or create account
    account = new_state.get_account(heartbeat.pubkey)
    if account is None:
        account = AccountState(pubkey=heartbeat.pubkey)
        new_state.active_accounts += 1

    # Update account
    account.epoch_heartbeats += 1
    account.total_heartbeats += 1
    account.last_heartbeat_height = block_height

    # Save account
    new_state.set_account(heartbeat.pubkey, account)

    # Update global stats
    new_state.total_heartbeats += 1

    logger.debug(
        f"Applied heartbeat from {heartbeat.pubkey.data.hex()[:16]}, "
        f"epoch_hb={account.epoch_heartbeats}"
    )

    return new_state


def apply_transaction(
    state: GlobalState,
    transaction: "Transaction",
    block_height: int,
    timestamp_ms: int
) -> GlobalState:
    """
    Apply a transaction to the state.

    Per specification (Part XV):
    1. Verify sender exists
    2. Debit sender
    3. Credit receiver (create account if needed)
    4. Update nonces and transaction counts
    5. Update rate limiting counters

    Args:
        state: Current global state
        transaction: Transaction to apply
        block_height: Current block height
        timestamp_ms: Current timestamp in milliseconds

    Returns:
        New state with transaction applied

    Raises:
        StateTransitionError: If transition fails
    """
    new_state = state.copy()

    # Get sender account
    sender = new_state.get_account(transaction.sender)
    if sender is None:
        raise StateTransitionError(
            f"Sender not found: {transaction.sender.data.hex()[:16]}"
        )

    # Verify balance
    if sender.balance < transaction.amount:
        raise StateTransitionError(
            f"Insufficient balance: {sender.balance} < {transaction.amount}"
        )

    # Verify nonce
    expected_nonce = sender.nonce + 1
    if transaction.nonce != expected_nonce:
        raise StateTransitionError(
            f"Invalid nonce: {transaction.nonce} != {expected_nonce}"
        )

    # Get or create receiver account
    receiver = new_state.get_account(transaction.receiver)
    if receiver is None:
        receiver = AccountState(pubkey=transaction.receiver)
        new_state.active_accounts += 1

    # Transfer
    sender.balance -= transaction.amount
    receiver.balance += transaction.amount

    # Update sender nonce and counts
    sender.nonce = transaction.nonce
    sender.epoch_tx_count += 1

    # Update per-second tracking
    current_second = timestamp_ms // 1000
    if sender.last_tx_second == current_second:
        sender.second_tx_count += 1
    else:
        sender.last_tx_second = current_second
        sender.second_tx_count = 1

    # Save accounts
    new_state.set_account(transaction.sender, sender)
    new_state.set_account(transaction.receiver, receiver)

    logger.debug(
        f"Applied tx: {transaction.sender.data.hex()[:8]} -> "
        f"{transaction.receiver.data.hex()[:8]}, amount={transaction.amount}"
    )

    return new_state


def apply_block(
    state: GlobalState,
    block: "Block",
    parent: Optional["Block"] = None
) -> GlobalState:
    """
    Apply a complete block to the state.

    Per specification (Part XV):
    1. Apply all heartbeats
    2. Apply all transactions
    3. Handle epoch transitions
    4. Distribute block rewards
    5. Update chain state

    Args:
        state: Current global state
        block: Block to apply
        parent: Parent block (for validation)

    Returns:
        New state with block applied

    Raises:
        StateTransitionError: If transition fails
    """
    new_state = state.copy()

    block_height = block.header.height
    timestamp_ms = block.header.timestamp_ms

    # Check for epoch transition
    old_epoch = new_state.btc_epoch
    new_epoch = block.header.btc_anchor.epoch
    epoch_changed = new_epoch != old_epoch

    if epoch_changed:
        new_state = handle_epoch_change(new_state, new_epoch)

    # Apply all heartbeats
    for hb in block.heartbeats:
        new_state = apply_heartbeat(new_state, hb, block_height)

    # Apply all transactions
    for tx in block.transactions:
        new_state = apply_transaction(new_state, tx, block_height, timestamp_ms)

    # Distribute block rewards to signers
    if block.signers:
        new_state = distribute_block_rewards(
            new_state,
            block,
            block_height
        )

    # Update chain state
    new_state.chain_height = block_height
    new_state.chain_tip_hash = block.block_hash()
    new_state.btc_height = block.header.btc_anchor.height
    new_state.btc_hash = block.header.btc_anchor.block_hash
    new_state.btc_epoch = new_epoch

    logger.info(
        f"Applied block {block_height}: "
        f"hb={len(block.heartbeats)}, tx={len(block.transactions)}, "
        f"signers={len(block.signers)}"
    )

    return new_state


def handle_epoch_change(
    state: GlobalState,
    new_epoch: int
) -> GlobalState:
    """
    Handle epoch transition.

    Per specification (Part XV):
    1. Reset epoch counters for all accounts
    2. Check for halving epoch
    3. Apply halving if needed

    Args:
        state: Current global state
        new_epoch: New epoch number

    Returns:
        New state with epoch changes applied
    """
    new_state = state.copy()

    logger.info(f"Epoch transition: {state.btc_epoch} -> {new_epoch}")

    # Reset epoch counters for all accounts
    for pk in new_state.get_all_pubkeys():
        account = new_state.get_account(pk)
        if account is not None:
            account.epoch_heartbeats = 0
            account.epoch_tx_count = 0
            new_state.set_account(pk, account)

    # Check for halving
    current_halving = state.btc_height // BTC_HALVING_INTERVAL
    new_halving = (state.btc_height + 1) // BTC_HALVING_INTERVAL  # Estimate

    if new_halving > current_halving:
        logger.info(f"Bitcoin halving occurred at epoch {new_epoch}")
        # Additional halving logic could be added here

    return new_state


def distribute_block_rewards(
    state: GlobalState,
    block: "Block",
    block_height: int
) -> GlobalState:
    """
    Distribute block rewards to signers.

    Per specification (Part XV):
    - Reward = INITIAL_REWARD / 2^halvings
    - Distributed proportionally to signer scores

    Args:
        state: Current global state
        block: Block being finalized
        block_height: Current block height

    Returns:
        New state with rewards distributed
    """
    new_state = state.copy()

    # Calculate reward based on halvings
    halvings = state.btc_height // BTC_HALVING_INTERVAL
    reward = INITIAL_REWARD >> halvings  # Divide by 2^halvings

    if reward == 0:
        return new_state

    # Calculate total score
    total_score = sum(signer.score() for signer in block.signers)
    if total_score == 0:
        return new_state

    # Distribute proportionally
    for signer in block.signers:
        share = (signer.score() / total_score) * reward
        share_int = int(share)

        if share_int > 0:
            account = new_state.get_account(signer.pubkey)
            if account is not None:
                account.balance += share_int
                new_state.set_account(signer.pubkey, account)
                new_state.total_supply += share_int

    logger.debug(
        f"Distributed {reward} reward to {len(block.signers)} signers"
    )

    return new_state


def compute_state_root(state: GlobalState) -> Hash:
    """
    Compute Merkle root of state.

    Per specification (Part XV):
    - Sorted list of account hashes
    - Merkle tree over account states

    Args:
        state: Global state

    Returns:
        State Merkle root
    """
    # Get all accounts sorted by pubkey
    pubkeys = sorted(state.get_all_pubkeys(), key=lambda pk: pk.data)

    if not pubkeys:
        return Hash.zero()

    # Hash each account
    account_hashes = []
    for pk in pubkeys:
        account = state.get_account(pk)
        if account is not None:
            account_bytes = account.serialize()
            account_hash = sha3_256(account_bytes)
            account_hashes.append(account_hash)

    # Compute Merkle root
    return merkle_root(account_hashes)


def validate_state_transition(
    old_state: GlobalState,
    new_state: GlobalState,
    block: "Block"
) -> bool:
    """
    Validate that state transition is correct.

    Args:
        old_state: State before block
        new_state: State after block
        block: Applied block

    Returns:
        True if transition is valid
    """
    # Height increased by 1
    if new_state.chain_height != old_state.chain_height + 1:
        logger.debug("Invalid height transition")
        return False

    # Tip hash matches block
    if new_state.chain_tip_hash != block.block_hash():
        logger.debug("Invalid tip hash")
        return False

    # Total heartbeats increased by correct amount
    expected_hb = old_state.total_heartbeats + len(block.heartbeats)
    if new_state.total_heartbeats != expected_hb:
        logger.debug("Invalid heartbeat count")
        return False

    return True


@dataclass
class StateMachine:
    """
    Complete state machine with history and rollback support.
    """
    current_state: GlobalState = field(default_factory=GlobalState)
    state_history: List[Tuple[int, GlobalState]] = field(default_factory=list)
    max_history: int = 100

    def apply_block(self, block: "Block", parent: Optional["Block"] = None) -> bool:
        """
        Apply a block and save to history.

        Returns:
            True if block was applied successfully
        """
        try:
            # Save current state to history
            self._save_history()

            # Apply block
            self.current_state = apply_block(
                self.current_state,
                block,
                parent
            )

            return True

        except StateTransitionError as e:
            logger.error(f"State transition failed: {e}")
            return False

    def _save_history(self) -> None:
        """Save current state to history."""
        self.state_history.append((
            self.current_state.chain_height,
            self.current_state.copy()
        ))

        # Trim history
        while len(self.state_history) > self.max_history:
            self.state_history.pop(0)

    def rollback_to(self, height: int) -> bool:
        """
        Rollback state to a previous height.

        Args:
            height: Target block height

        Returns:
            True if rollback succeeded
        """
        for i, (h, state) in enumerate(reversed(self.state_history)):
            if h == height:
                self.current_state = state.copy()
                # Remove rolled-back history
                self.state_history = self.state_history[:len(self.state_history) - i - 1]
                logger.info(f"Rolled back to height {height}")
                return True

        logger.error(f"Cannot rollback to height {height}: not in history")
        return False

    def get_state_at(self, height: int) -> Optional[GlobalState]:
        """Get state at a specific height from history."""
        if self.current_state.chain_height == height:
            return self.current_state.copy()

        for h, state in self.state_history:
            if h == height:
                return state.copy()

        return None

    def get_account(self, pubkey: PublicKey) -> Optional[AccountState]:
        """Get account from current state."""
        return self.current_state.get_account(pubkey)

    def get_balance(self, pubkey: PublicKey) -> int:
        """Get balance for a public key."""
        account = self.current_state.get_account(pubkey)
        return account.balance if account else 0

    def get_nonce(self, pubkey: PublicKey) -> int:
        """Get nonce for a public key."""
        account = self.current_state.get_account(pubkey)
        return account.nonce if account else 0

    def get_chain_height(self) -> int:
        """Get current chain height."""
        return self.current_state.chain_height

    def get_chain_tip(self) -> Hash:
        """Get current chain tip hash."""
        return self.current_state.chain_tip_hash

    def compute_state_root(self) -> Hash:
        """Compute current state root."""
        return compute_state_root(self.current_state)


def get_state_machine_info() -> dict:
    """Get information about state machine."""
    return {
        "operations": [
            "apply_heartbeat",
            "apply_transaction",
            "apply_block",
        ],
        "epoch_duration_blocks": EPOCH_DURATION_BLOCKS,
        "halving_interval": BTC_HALVING_INTERVAL,
        "initial_reward": INITIAL_REWARD,
    }
