"""
ATC Protocol v7 Gossip Protocol
Part XIII of Technical Specification

Heartbeat and transaction propagation.
"""

from __future__ import annotations
import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Callable, TYPE_CHECKING

from atc.core.types import Hash
from atc.network.messages import (
    Message,
    HeartbeatMessage,
    TransactionMessage,
)
from atc.network.peer import Peer, PeerManager

if TYPE_CHECKING:
    from atc.core.heartbeat import Heartbeat
    from atc.core.transaction import Transaction

logger = logging.getLogger(__name__)


@dataclass
class GossipCache:
    """
    LRU cache for tracking seen items.

    Prevents re-propagation of already-seen heartbeats/transactions.
    """
    max_size: int = 10000
    _items: OrderedDict = field(default_factory=OrderedDict)

    def __post_init__(self):
        self._items = OrderedDict()

    def add(self, item_id: bytes) -> bool:
        """
        Add item to cache.

        Returns:
            True if item was new, False if already seen
        """
        if item_id in self._items:
            # Move to end (most recently used)
            self._items.move_to_end(item_id)
            return False

        self._items[item_id] = time.time()

        # Evict oldest if over capacity
        while len(self._items) > self.max_size:
            self._items.popitem(last=False)

        return True

    def contains(self, item_id: bytes) -> bool:
        """Check if item is in cache."""
        return item_id in self._items

    def size(self) -> int:
        """Get cache size."""
        return len(self._items)

    def clear(self) -> None:
        """Clear cache."""
        self._items.clear()


@dataclass
class GossipStats:
    """Gossip statistics."""
    heartbeats_received: int = 0
    heartbeats_propagated: int = 0
    heartbeats_duplicate: int = 0
    transactions_received: int = 0
    transactions_propagated: int = 0
    transactions_duplicate: int = 0
    propagation_errors: int = 0


@dataclass
class GossipProtocol:
    """
    Gossip protocol for heartbeats and transactions.

    Handles receiving, validating, and propagating items to peers.
    """
    peer_manager: PeerManager
    propagation_factor: int = 3  # Number of peers to propagate to

    # Caches
    _heartbeat_cache: GossipCache = field(default_factory=lambda: GossipCache(10000))
    _transaction_cache: GossipCache = field(default_factory=lambda: GossipCache(50000))

    # Statistics
    stats: GossipStats = field(default_factory=GossipStats)

    # Callbacks
    _on_heartbeat: Optional[Callable] = None
    _on_transaction: Optional[Callable] = None

    # Queue for batching
    _heartbeat_queue: List[bytes] = field(default_factory=list)
    _transaction_queue: List[bytes] = field(default_factory=list)
    _queue_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Background tasks
    _flush_task: Optional[asyncio.Task] = None
    _running: bool = False

    def __post_init__(self):
        self._heartbeat_cache = GossipCache(10000)
        self._transaction_cache = GossipCache(50000)
        self.stats = GossipStats()
        self._heartbeat_queue = []
        self._transaction_queue = []
        self._queue_lock = asyncio.Lock()

    def set_callbacks(
        self,
        on_heartbeat: Callable = None,
        on_transaction: Callable = None
    ) -> None:
        """Set callbacks for received items."""
        self._on_heartbeat = on_heartbeat
        self._on_transaction = on_transaction

    async def start(self) -> None:
        """Start the gossip protocol."""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Gossip protocol started")

    async def stop(self) -> None:
        """Stop the gossip protocol."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        logger.info("Gossip protocol stopped")

    async def _flush_loop(self) -> None:
        """Background loop to flush queued items."""
        while self._running:
            try:
                await asyncio.sleep(0.1)  # 100ms batching window
                await self._flush_queues()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")

    async def _flush_queues(self) -> None:
        """Flush queued items to peers."""
        async with self._queue_lock:
            # Flush heartbeats
            if self._heartbeat_queue:
                heartbeats = self._heartbeat_queue.copy()
                self._heartbeat_queue.clear()
                await self._propagate_heartbeats(heartbeats)

            # Flush transactions
            if self._transaction_queue:
                transactions = self._transaction_queue.copy()
                self._transaction_queue.clear()
                await self._propagate_transactions(transactions)

    async def handle_heartbeat(
        self,
        peer: Peer,
        heartbeat_data: bytes,
        propagate: bool = True
    ) -> bool:
        """
        Handle received heartbeat.

        Args:
            peer: Source peer
            heartbeat_data: Serialized heartbeat
            propagate: Whether to propagate to other peers

        Returns:
            True if heartbeat was new and valid
        """
        from atc.crypto.hash import sha3_256

        # Compute heartbeat ID
        heartbeat_id = sha3_256(heartbeat_data).data

        self.stats.heartbeats_received += 1

        # Check if already seen
        if not self._heartbeat_cache.add(heartbeat_id):
            self.stats.heartbeats_duplicate += 1
            return False

        # Call validation callback
        if self._on_heartbeat:
            try:
                valid = await self._on_heartbeat(heartbeat_data)
                if not valid:
                    return False
            except Exception as e:
                logger.error(f"Heartbeat callback error: {e}")
                return False

        # Queue for propagation
        if propagate:
            async with self._queue_lock:
                self._heartbeat_queue.append(heartbeat_data)

        return True

    async def handle_transaction(
        self,
        peer: Peer,
        transaction_data: bytes,
        propagate: bool = True
    ) -> bool:
        """
        Handle received transaction.

        Args:
            peer: Source peer
            transaction_data: Serialized transaction
            propagate: Whether to propagate to other peers

        Returns:
            True if transaction was new and valid
        """
        from atc.crypto.hash import sha3_256

        # Compute transaction ID
        tx_id = sha3_256(transaction_data).data

        self.stats.transactions_received += 1

        # Check if already seen
        if not self._transaction_cache.add(tx_id):
            self.stats.transactions_duplicate += 1
            return False

        # Call validation callback
        if self._on_transaction:
            try:
                valid = await self._on_transaction(transaction_data)
                if not valid:
                    return False
            except Exception as e:
                logger.error(f"Transaction callback error: {e}")
                return False

        # Queue for propagation
        if propagate:
            async with self._queue_lock:
                self._transaction_queue.append(transaction_data)

        return True

    async def _propagate_heartbeats(
        self,
        heartbeats: List[bytes]
    ) -> int:
        """Propagate heartbeats to peers."""
        if not heartbeats:
            return 0

        message = HeartbeatMessage(heartbeats=heartbeats)
        msg = message.to_message()

        # Get random subset of peers
        peers = self.peer_manager.get_active_peers()
        import random
        targets = random.sample(peers, min(self.propagation_factor, len(peers)))

        sent_count = 0
        for peer in targets:
            try:
                if await peer.send_message(msg):
                    sent_count += 1
            except Exception as e:
                logger.debug(f"Failed to propagate to {peer.peer_id}: {e}")
                self.stats.propagation_errors += 1

        self.stats.heartbeats_propagated += len(heartbeats) * sent_count
        return sent_count

    async def _propagate_transactions(
        self,
        transactions: List[bytes]
    ) -> int:
        """Propagate transactions to peers."""
        if not transactions:
            return 0

        message = TransactionMessage(transactions=transactions)
        msg = message.to_message()

        # Get random subset of peers
        peers = self.peer_manager.get_active_peers()
        import random
        targets = random.sample(peers, min(self.propagation_factor, len(peers)))

        sent_count = 0
        for peer in targets:
            try:
                if await peer.send_message(msg):
                    sent_count += 1
            except Exception as e:
                logger.debug(f"Failed to propagate to {peer.peer_id}: {e}")
                self.stats.propagation_errors += 1

        self.stats.transactions_propagated += len(transactions) * sent_count
        return sent_count

    async def broadcast_heartbeat(
        self,
        heartbeat: "Heartbeat"
    ) -> int:
        """
        Broadcast a locally created heartbeat.

        Args:
            heartbeat: Heartbeat to broadcast

        Returns:
            Number of peers it was sent to
        """
        heartbeat_data = heartbeat.serialize()

        # Add to cache
        from atc.crypto.hash import sha3_256
        heartbeat_id = sha3_256(heartbeat_data).data
        self._heartbeat_cache.add(heartbeat_id)

        # Broadcast immediately
        message = HeartbeatMessage(heartbeats=[heartbeat_data])
        return await self.peer_manager.broadcast(message.to_message())

    async def broadcast_transaction(
        self,
        transaction: "Transaction"
    ) -> int:
        """
        Broadcast a locally created transaction.

        Args:
            transaction: Transaction to broadcast

        Returns:
            Number of peers it was sent to
        """
        tx_data = transaction.serialize()

        # Add to cache
        from atc.crypto.hash import sha3_256
        tx_id = sha3_256(tx_data).data
        self._transaction_cache.add(tx_id)

        # Broadcast immediately
        message = TransactionMessage(transactions=[tx_data])
        return await self.peer_manager.broadcast(message.to_message())

    def has_seen_heartbeat(self, heartbeat_id: bytes) -> bool:
        """Check if heartbeat was already seen."""
        return self._heartbeat_cache.contains(heartbeat_id)

    def has_seen_transaction(self, tx_id: bytes) -> bool:
        """Check if transaction was already seen."""
        return self._transaction_cache.contains(tx_id)

    def get_statistics(self) -> dict:
        """Get gossip statistics."""
        return {
            "heartbeats_received": self.stats.heartbeats_received,
            "heartbeats_propagated": self.stats.heartbeats_propagated,
            "heartbeats_duplicate": self.stats.heartbeats_duplicate,
            "heartbeat_cache_size": self._heartbeat_cache.size(),
            "transactions_received": self.stats.transactions_received,
            "transactions_propagated": self.stats.transactions_propagated,
            "transactions_duplicate": self.stats.transactions_duplicate,
            "transaction_cache_size": self._transaction_cache.size(),
            "propagation_errors": self.stats.propagation_errors,
        }

    def clear_caches(self) -> None:
        """Clear all caches."""
        self._heartbeat_cache.clear()
        self._transaction_cache.clear()


def get_gossip_info() -> dict:
    """Get information about gossip protocol."""
    return {
        "default_propagation_factor": 3,
        "heartbeat_cache_size": 10000,
        "transaction_cache_size": 50000,
        "batching_window_ms": 100,
    }
