"""
PoT Protocol v6 Personal Rate Limiting
Part IX of Technical Specification

PRINCIPLE: "Your spam is your problem, not the network's."

Each sender pays for their own excess through increasing PoW difficulty.
The network is not affected by individual spammers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional
import time

from pot.constants import (
    TX_FREE_PER_SECOND,
    TX_FREE_PER_EPOCH,
    TX_EPOCH_DURATION_SEC,
    POW_BASE_DIFFICULTY_BITS,
    POW_EXCESS_PENALTY_BITS,
    POW_BURST_PENALTY_BITS,
    POW_MAX_DIFFICULTY_BITS,
)
from pot.core.types import PublicKey


def get_current_epoch(timestamp_ms: int) -> int:
    """Get epoch number from timestamp."""
    return timestamp_ms // (TX_EPOCH_DURATION_SEC * 1000)


def get_current_second(timestamp_ms: int) -> int:
    """Get second from timestamp."""
    return timestamp_ms // 1000


def calculate_epoch_penalty(epoch_tx_count: int) -> int:
    """
    Calculate epoch penalty in difficulty bits.

    +2 bits per transaction beyond free tier (10/epoch).

    Args:
        epoch_tx_count: Number of transactions in current epoch

    Returns:
        Additional difficulty bits from epoch penalty
    """
    if epoch_tx_count < TX_FREE_PER_EPOCH:
        return 0

    excess = epoch_tx_count - TX_FREE_PER_EPOCH + 1
    return excess * POW_EXCESS_PENALTY_BITS


def calculate_burst_penalty(second_tx_count: int) -> int:
    """
    Calculate burst penalty in difficulty bits.

    +4 bits per transaction in same second.

    Args:
        second_tx_count: Number of transactions in current second

    Returns:
        Additional difficulty bits from burst penalty
    """
    return second_tx_count * POW_BURST_PENALTY_BITS


def get_personal_difficulty(
    epoch_tx_count: int,
    second_tx_count: int
) -> int:
    """
    Calculate total personal PoW difficulty.

    Per specification (Part IX):
    - Base difficulty: 16 bits (~65ms)
    - Epoch penalty: +2 bits per excess transaction
    - Burst penalty: +4 bits per same-second transaction
    - Maximum: 32 bits (~18 hours)

    Args:
        epoch_tx_count: Transactions in current epoch
        second_tx_count: Transactions in current second

    Returns:
        Required difficulty in bits
    """
    difficulty = POW_BASE_DIFFICULTY_BITS

    # Add epoch penalty
    difficulty += calculate_epoch_penalty(epoch_tx_count)

    # Add burst penalty
    difficulty += calculate_burst_penalty(second_tx_count)

    return min(difficulty, POW_MAX_DIFFICULTY_BITS)


@dataclass
class SenderState:
    """Rate limiting state for a single sender."""
    pubkey: PublicKey
    epoch_tx_count: int = 0
    current_epoch: int = 0
    current_second: int = 0
    second_tx_count: int = 0
    last_tx_time_ms: int = 0

    def update_for_tx(self, timestamp_ms: int):
        """Update state after a transaction."""
        epoch = get_current_epoch(timestamp_ms)
        second = get_current_second(timestamp_ms)

        # Handle epoch change
        if epoch != self.current_epoch:
            self.current_epoch = epoch
            self.epoch_tx_count = 0

        # Handle second change
        if second != self.current_second:
            self.current_second = second
            self.second_tx_count = 0

        # Increment counters
        self.epoch_tx_count += 1
        self.second_tx_count += 1
        self.last_tx_time_ms = timestamp_ms

    def get_difficulty(self, timestamp_ms: int) -> int:
        """Get current difficulty for new transaction."""
        epoch = get_current_epoch(timestamp_ms)
        second = get_current_second(timestamp_ms)

        # Use fresh counts for new epoch/second
        epoch_count = self.epoch_tx_count if epoch == self.current_epoch else 0
        second_count = self.second_tx_count if second == self.current_second else 0

        return get_personal_difficulty(epoch_count, second_count)


class RateLimitTracker:
    """
    Tracks rate limiting state for all senders.

    Thread-safe for concurrent access.
    """

    def __init__(self):
        self._states: Dict[bytes, SenderState] = {}
        self._lock = None  # Initialize lazily for threading

    def _ensure_lock(self):
        """Lazily create lock for thread safety."""
        if self._lock is None:
            import threading
            self._lock = threading.Lock()

    def get_state(self, pubkey: PublicKey) -> SenderState:
        """Get or create state for a sender."""
        key = pubkey.data
        if key not in self._states:
            self._states[key] = SenderState(pubkey=pubkey)
        return self._states[key]

    def get_difficulty(self, pubkey: PublicKey, timestamp_ms: int) -> int:
        """
        Get required difficulty for a sender's next transaction.

        Args:
            pubkey: Sender's public key
            timestamp_ms: Current timestamp in milliseconds

        Returns:
            Required difficulty in bits
        """
        self._ensure_lock()
        with self._lock:
            state = self.get_state(pubkey)
            return state.get_difficulty(timestamp_ms)

    def record_transaction(self, pubkey: PublicKey, timestamp_ms: int):
        """
        Record that a transaction was sent.

        Call this after a transaction is confirmed.

        Args:
            pubkey: Sender's public key
            timestamp_ms: Transaction timestamp
        """
        self._ensure_lock()
        with self._lock:
            state = self.get_state(pubkey)
            state.update_for_tx(timestamp_ms)

    def get_epoch_tx_count(self, pubkey: PublicKey, timestamp_ms: int) -> int:
        """Get current epoch transaction count for a sender."""
        state = self.get_state(pubkey)
        epoch = get_current_epoch(timestamp_ms)
        if epoch != state.current_epoch:
            return 0
        return state.epoch_tx_count

    def get_remaining_free(self, pubkey: PublicKey, timestamp_ms: int) -> int:
        """Get remaining free transactions in current epoch."""
        used = self.get_epoch_tx_count(pubkey, timestamp_ms)
        return max(0, TX_FREE_PER_EPOCH - used)

    def reset_epoch(self, pubkey: PublicKey):
        """Reset epoch counters for a sender."""
        if pubkey.data in self._states:
            state = self._states[pubkey.data]
            state.epoch_tx_count = 0
            state.current_epoch = 0

    def clear(self):
        """Clear all tracked state."""
        self._states.clear()

    def get_stats(self) -> dict:
        """Get tracker statistics."""
        return {
            "tracked_senders": len(self._states),
            "total_epoch_txs": sum(s.epoch_tx_count for s in self._states.values()),
        }


# Global rate limit tracker
_rate_tracker = RateLimitTracker()


def get_rate_tracker() -> RateLimitTracker:
    """Get the global rate limit tracker."""
    return _rate_tracker


def estimate_wait_time(difficulty: int) -> float:
    """
    Estimate time to solve PoW at given difficulty.

    Based on difficulty table:
    - 16 bits: ~65ms
    - Each additional bit doubles the time

    Args:
        difficulty: Difficulty in bits

    Returns:
        Estimated time in seconds
    """
    base_time = 0.065  # 65ms for 16 bits
    extra_bits = max(0, difficulty - POW_BASE_DIFFICULTY_BITS)
    return base_time * (2 ** extra_bits)


def format_wait_time(seconds: float) -> str:
    """Format wait time as human-readable string."""
    if seconds < 1:
        return f"~{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"~{int(seconds)} sec"
    elif seconds < 3600:
        return f"~{int(seconds / 60)} min"
    else:
        return f"~{seconds / 3600:.1f} hours"
