"""
PoT Protocol v6 Mempool
Pending heartbeat and transaction management.
"""

from __future__ import annotations
import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from pot.constants import (
    MAX_HEARTBEATS_PER_BLOCK,
    MAX_TRANSACTIONS_PER_BLOCK,
)
from pot.core.types import Hash, PublicKey

if TYPE_CHECKING:
    from pot.core.heartbeat import Heartbeat
    from pot.core.transaction import Transaction
    from pot.core.state import GlobalState

logger = logging.getLogger(__name__)


@dataclass
class MempoolEntry:
    """Entry in the mempool."""
    data: bytes
    id: Hash
    received_time: float
    size: int
    priority: float = 0.0
    source_peer: Optional[str] = None


@dataclass
class MempoolStats:
    """Mempool statistics."""
    heartbeat_count: int = 0
    transaction_count: int = 0
    total_size_bytes: int = 0
    evictions: int = 0
    additions: int = 0
    removals: int = 0


@dataclass
class Mempool:
    """
    Mempool for pending heartbeats and transactions.

    Holds validated items waiting to be included in blocks.
    """
    max_heartbeats: int = 10000
    max_transactions: int = 50000
    max_size_bytes: int = 100_000_000

    # Storage
    _heartbeats: OrderedDict = field(default_factory=OrderedDict)
    _transactions: OrderedDict = field(default_factory=OrderedDict)

    # Tracking
    _heartbeat_by_pubkey: Dict[bytes, Hash] = field(default_factory=dict)
    _transaction_by_sender: Dict[bytes, List[Hash]] = field(default_factory=dict)

    # Statistics
    stats: MempoolStats = field(default_factory=MempoolStats)

    # Lock for thread safety
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self):
        self._heartbeats = OrderedDict()
        self._transactions = OrderedDict()
        self._heartbeat_by_pubkey = {}
        self._transaction_by_sender = {}
        self.stats = MempoolStats()
        self._lock = asyncio.Lock()

    async def add_heartbeat(
        self,
        heartbeat: "Heartbeat",
        source_peer: Optional[str] = None
    ) -> bool:
        """
        Add heartbeat to mempool.

        Args:
            heartbeat: Heartbeat to add
            source_peer: ID of peer that sent this heartbeat

        Returns:
            True if heartbeat was added
        """
        async with self._lock:
            hb_id = heartbeat.heartbeat_id()
            hb_bytes = hb_id.data

            # Check if already in mempool
            if hb_bytes in self._heartbeats:
                return False

            # Check if we already have a heartbeat from this pubkey
            pk_bytes = heartbeat.pubkey.data
            if pk_bytes in self._heartbeat_by_pubkey:
                # Replace if newer (by timestamp)
                old_id = self._heartbeat_by_pubkey[pk_bytes]
                old_entry = self._heartbeats.get(old_id.data)
                if old_entry:
                    # Remove old heartbeat
                    del self._heartbeats[old_id.data]
                    self.stats.total_size_bytes -= old_entry.size

            # Check capacity
            if len(self._heartbeats) >= self.max_heartbeats:
                self._evict_oldest_heartbeat()

            # Add entry
            hb_data = heartbeat.serialize()
            entry = MempoolEntry(
                data=hb_data,
                id=hb_id,
                received_time=time.time(),
                size=len(hb_data),
                source_peer=source_peer,
            )

            self._heartbeats[hb_bytes] = entry
            self._heartbeat_by_pubkey[pk_bytes] = hb_id
            self.stats.total_size_bytes += entry.size
            self.stats.heartbeat_count = len(self._heartbeats)
            self.stats.additions += 1

            return True

    async def add_transaction(
        self,
        transaction: "Transaction",
        priority: float = 0.0,
        source_peer: Optional[str] = None
    ) -> bool:
        """
        Add transaction to mempool.

        Args:
            transaction: Transaction to add
            priority: Priority score (higher = more likely to be included)
            source_peer: ID of peer that sent this transaction

        Returns:
            True if transaction was added
        """
        async with self._lock:
            tx_id = transaction.transaction_id()
            tx_bytes = tx_id.data

            # Check if already in mempool
            if tx_bytes in self._transactions:
                return False

            # Check capacity
            if len(self._transactions) >= self.max_transactions:
                self._evict_lowest_priority_transaction()

            # Check size
            tx_data = transaction.serialize()
            if self.stats.total_size_bytes + len(tx_data) > self.max_size_bytes:
                self._evict_to_make_room(len(tx_data))

            # Add entry
            entry = MempoolEntry(
                data=tx_data,
                id=tx_id,
                received_time=time.time(),
                size=len(tx_data),
                priority=priority,
                source_peer=source_peer,
            )

            self._transactions[tx_bytes] = entry

            # Track by sender
            sender_bytes = transaction.sender.data
            if sender_bytes not in self._transaction_by_sender:
                self._transaction_by_sender[sender_bytes] = []
            self._transaction_by_sender[sender_bytes].append(tx_id)

            self.stats.total_size_bytes += entry.size
            self.stats.transaction_count = len(self._transactions)
            self.stats.additions += 1

            return True

    def _evict_oldest_heartbeat(self) -> None:
        """Evict oldest heartbeat."""
        if not self._heartbeats:
            return

        # Get oldest (first item)
        oldest_id, oldest_entry = next(iter(self._heartbeats.items()))
        del self._heartbeats[oldest_id]

        # Remove from pubkey index
        for pk, hb_id in list(self._heartbeat_by_pubkey.items()):
            if hb_id.data == oldest_id:
                del self._heartbeat_by_pubkey[pk]
                break

        self.stats.total_size_bytes -= oldest_entry.size
        self.stats.evictions += 1

    def _evict_lowest_priority_transaction(self) -> None:
        """Evict lowest priority transaction."""
        if not self._transactions:
            return

        # Find lowest priority
        min_priority = float('inf')
        min_id = None
        for tx_id, entry in self._transactions.items():
            if entry.priority < min_priority:
                min_priority = entry.priority
                min_id = tx_id

        if min_id:
            self._remove_transaction_by_id(min_id)
            self.stats.evictions += 1

    def _evict_to_make_room(self, needed_bytes: int) -> None:
        """Evict transactions until we have enough room."""
        while (
            self.stats.total_size_bytes + needed_bytes > self.max_size_bytes
            and self._transactions
        ):
            self._evict_lowest_priority_transaction()

    def _remove_transaction_by_id(self, tx_id: bytes) -> None:
        """Remove transaction by ID."""
        if tx_id in self._transactions:
            entry = self._transactions.pop(tx_id)
            self.stats.total_size_bytes -= entry.size
            self.stats.removals += 1

    async def remove_heartbeat(self, heartbeat_id: Hash) -> bool:
        """Remove heartbeat from mempool."""
        async with self._lock:
            hb_bytes = heartbeat_id.data

            if hb_bytes not in self._heartbeats:
                return False

            entry = self._heartbeats.pop(hb_bytes)

            # Remove from pubkey index
            for pk, hb_id in list(self._heartbeat_by_pubkey.items()):
                if hb_id.data == hb_bytes:
                    del self._heartbeat_by_pubkey[pk]
                    break

            self.stats.total_size_bytes -= entry.size
            self.stats.heartbeat_count = len(self._heartbeats)
            self.stats.removals += 1

            return True

    async def remove_transaction(self, tx_id: Hash) -> bool:
        """Remove transaction from mempool."""
        async with self._lock:
            tx_bytes = tx_id.data

            if tx_bytes not in self._transactions:
                return False

            self._remove_transaction_by_id(tx_bytes)
            self.stats.transaction_count = len(self._transactions)

            return True

    async def remove_confirmed(
        self,
        heartbeat_ids: List[Hash],
        tx_ids: List[Hash]
    ) -> None:
        """Remove confirmed heartbeats and transactions."""
        async with self._lock:
            for hb_id in heartbeat_ids:
                hb_bytes = hb_id.data
                if hb_bytes in self._heartbeats:
                    entry = self._heartbeats.pop(hb_bytes)
                    self.stats.total_size_bytes -= entry.size

                    # Remove from pubkey index
                    for pk, id in list(self._heartbeat_by_pubkey.items()):
                        if id.data == hb_bytes:
                            del self._heartbeat_by_pubkey[pk]
                            break

            for tx_id in tx_ids:
                tx_bytes = tx_id.data
                if tx_bytes in self._transactions:
                    self._remove_transaction_by_id(tx_bytes)

            self.stats.heartbeat_count = len(self._heartbeats)
            self.stats.transaction_count = len(self._transactions)

    def get_heartbeats_for_block(
        self,
        max_count: int = MAX_HEARTBEATS_PER_BLOCK
    ) -> List[bytes]:
        """
        Get heartbeats to include in a block.

        Returns serialized heartbeat data, oldest first.
        """
        heartbeats = []
        for entry in self._heartbeats.values():
            if len(heartbeats) >= max_count:
                break
            heartbeats.append(entry.data)
        return heartbeats

    def get_transactions_for_block(
        self,
        max_count: int = MAX_TRANSACTIONS_PER_BLOCK,
        state: Optional["GlobalState"] = None
    ) -> List[bytes]:
        """
        Get transactions to include in a block.

        Sorted by priority (highest first), then by received time.
        """
        # Sort by priority (descending) then by time (ascending)
        sorted_entries = sorted(
            self._transactions.values(),
            key=lambda e: (-e.priority, e.received_time)
        )

        transactions = []
        for entry in sorted_entries[:max_count]:
            transactions.append(entry.data)

        return transactions

    def has_heartbeat(self, heartbeat_id: Hash) -> bool:
        """Check if heartbeat is in mempool."""
        return heartbeat_id.data in self._heartbeats

    def has_heartbeat_from(self, pubkey: PublicKey) -> bool:
        """Check if we have a heartbeat from this pubkey."""
        return pubkey.data in self._heartbeat_by_pubkey

    def has_transaction(self, tx_id: Hash) -> bool:
        """Check if transaction is in mempool."""
        return tx_id.data in self._transactions

    def get_pending_transactions(
        self,
        sender: PublicKey
    ) -> List[Hash]:
        """Get pending transaction IDs from sender."""
        return self._transaction_by_sender.get(sender.data, [])

    def get_heartbeat_count(self) -> int:
        """Get number of heartbeats in mempool."""
        return len(self._heartbeats)

    def get_transaction_count(self) -> int:
        """Get number of transactions in mempool."""
        return len(self._transactions)

    def get_size(self) -> int:
        """Get total mempool size in bytes."""
        return self.stats.total_size_bytes

    async def clear(self) -> None:
        """Clear all mempool contents."""
        async with self._lock:
            self._heartbeats.clear()
            self._transactions.clear()
            self._heartbeat_by_pubkey.clear()
            self._transaction_by_sender.clear()
            self.stats = MempoolStats()

    def get_statistics(self) -> dict:
        """Get mempool statistics."""
        return {
            "heartbeat_count": self.stats.heartbeat_count,
            "transaction_count": self.stats.transaction_count,
            "total_size_bytes": self.stats.total_size_bytes,
            "max_heartbeats": self.max_heartbeats,
            "max_transactions": self.max_transactions,
            "max_size_bytes": self.max_size_bytes,
            "additions": self.stats.additions,
            "removals": self.stats.removals,
            "evictions": self.stats.evictions,
        }


def get_mempool_info() -> dict:
    """Get information about mempool."""
    return {
        "default_max_heartbeats": 10000,
        "default_max_transactions": 50000,
        "default_max_size_mb": 100,
        "eviction_policy": "lowest priority / oldest",
    }
