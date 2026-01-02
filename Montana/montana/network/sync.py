"""
Ɉ Montana Synchronization v3.1

Initial Block Download and sync per MONTANA_TECHNICAL_SPECIFICATION.md §18.
"""

from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import IntEnum, auto

from montana.constants import (
    MAX_BLOCKS_PER_REQUEST,
    SYNC_TIMEOUT_SEC,
    IBD_BATCH_SIZE,
)
from montana.core.types import Hash
from montana.core.block import Block, BlockHeader
from montana.network.protocol import MessageType, InventoryType
from montana.network.messages import (
    InventoryItem,
    InvMessage,
    GetDataMessage,
)
from montana.network.peer import Peer, PeerManager

logger = logging.getLogger(__name__)


class SyncState(IntEnum):
    """Synchronization state."""
    IDLE = 0
    HEADERS = 1           # Downloading headers
    BLOCKS = 2            # Downloading blocks
    CAUGHT_UP = 3         # Fully synchronized
    STALLED = 4           # Sync stalled


@dataclass
class SyncProgress:
    """Track synchronization progress."""
    state: SyncState = SyncState.IDLE
    start_height: int = 0
    current_height: int = 0
    target_height: int = 0
    start_time: float = 0.0
    blocks_downloaded: int = 0
    bytes_downloaded: int = 0

    @property
    def progress_percent(self) -> float:
        if self.target_height <= self.start_height:
            return 100.0
        total = self.target_height - self.start_height
        done = self.current_height - self.start_height
        return min(100.0, (done / total) * 100)

    @property
    def blocks_per_second(self) -> float:
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0.0
        return self.blocks_downloaded / elapsed

    @property
    def eta_seconds(self) -> float:
        bps = self.blocks_per_second
        if bps <= 0:
            return float('inf')
        remaining = self.target_height - self.current_height
        return remaining / bps


@dataclass
class PeerSyncState:
    """Track sync state for a specific peer."""
    peer: Peer
    best_height: int = 0
    common_height: int = 0
    pending_requests: Set[Hash] = field(default_factory=set)
    last_request_time: float = 0.0
    stall_count: int = 0


class SyncManager:
    """
    Manages timechain synchronization.

    Handles:
    - Initial Block Download (IBD)
    - Ongoing sync with new blocks
    - Orphan block management
    - Parallel download from multiple peers
    """

    def __init__(
        self,
        peer_manager: PeerManager,
        get_best_height: callable,
        get_block: callable,
        add_block: callable,
    ):
        self.peer_manager = peer_manager
        self.get_best_height = get_best_height
        self.get_block = get_block
        self.add_block = add_block

        # Sync state
        self.progress = SyncProgress()
        self.peer_states: Dict[Tuple[str, int], PeerSyncState] = {}

        # Block queue
        self.pending_blocks: Dict[Hash, Block] = {}
        self.orphan_blocks: Dict[Hash, Block] = {}
        self.downloading: Set[Hash] = set()

        # Sync control
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def is_syncing(self) -> bool:
        return self.progress.state in (SyncState.HEADERS, SyncState.BLOCKS)

    @property
    def is_caught_up(self) -> bool:
        return self.progress.state == SyncState.CAUGHT_UP

    def get_best_peer(self) -> Optional[Peer]:
        """Get peer with highest known height."""
        best_peer = None
        best_height = 0

        for peer in self.peer_manager.ready_peers:
            if peer.info.start_height > best_height:
                best_height = peer.info.start_height
                best_peer = peer

        return best_peer

    async def start_sync(self):
        """Start synchronization."""
        if self._running:
            return

        self._running = True
        self.progress.state = SyncState.HEADERS
        self.progress.start_time = time.time()
        self.progress.start_height = self.get_best_height()
        self.progress.current_height = self.progress.start_height

        # Find best peer
        best_peer = self.get_best_peer()
        if not best_peer:
            logger.warning("No peers available for sync")
            self.progress.state = SyncState.STALLED
            return

        self.progress.target_height = best_peer.info.start_height

        logger.info(
            f"Starting sync from height {self.progress.start_height} "
            f"to {self.progress.target_height}"
        )

        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop_sync(self):
        """Stop synchronization."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None

    async def _sync_loop(self):
        """Main synchronization loop."""
        while self._running:
            try:
                if self.progress.current_height >= self.progress.target_height:
                    # Check if any peer has higher height
                    best_peer = self.get_best_peer()
                    if best_peer and best_peer.info.start_height > self.progress.target_height:
                        self.progress.target_height = best_peer.info.start_height
                    else:
                        self.progress.state = SyncState.CAUGHT_UP
                        logger.info(f"Sync complete at height {self.progress.current_height}")
                        await asyncio.sleep(10.0)
                        continue

                # Request blocks from peers
                await self._request_blocks()

                # Process received blocks
                await self._process_pending_blocks()

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")
                await asyncio.sleep(5.0)

    async def _request_blocks(self):
        """Request blocks from peers."""
        peers = self.peer_manager.ready_peers
        if not peers:
            return

        # Calculate what blocks we need
        start = self.progress.current_height + 1
        end = min(start + IBD_BATCH_SIZE, self.progress.target_height + 1)

        # For DAG, we'd request by hash rather than height
        # This is simplified for the chain-like case
        blocks_needed = end - start

        if blocks_needed <= 0:
            return

        # Distribute requests across peers
        blocks_per_peer = (blocks_needed + len(peers) - 1) // len(peers)
        blocks_per_peer = min(blocks_per_peer, MAX_BLOCKS_PER_REQUEST)

        # In a real implementation, we would:
        # 1. Send GetHeaders to get header chain
        # 2. Send GetData for blocks by hash
        # This is a simplified placeholder

        logger.debug(f"Requesting blocks {start} to {end}")

    async def _process_pending_blocks(self):
        """Process received blocks."""
        if not self.pending_blocks:
            return

        processed = []
        for block_hash, block in self.pending_blocks.items():
            try:
                # Verify and add block
                if await self.add_block(block):
                    self.progress.blocks_downloaded += 1
                    self.progress.current_height = max(
                        self.progress.current_height,
                        block.height
                    )
                    processed.append(block_hash)
                    logger.debug(f"Added block at height {block.height}")
            except Exception as e:
                logger.warning(f"Failed to add block: {e}")
                # Move to orphans if parent missing
                self.orphan_blocks[block_hash] = block
                processed.append(block_hash)

        for h in processed:
            del self.pending_blocks[h]

    async def handle_inv(self, peer: Peer, inv: InvMessage):
        """
        Handle inventory announcement.

        Request data for unknown items.
        """
        request_items = []

        for item in inv.items:
            if item.inv_type == InventoryType.BLOCK:
                # Check if we have this block
                if not self.get_block(item.hash) and item.hash not in self.downloading:
                    request_items.append(item)
                    self.downloading.add(item.hash)

        if request_items:
            getdata = GetDataMessage(items=request_items)
            await peer.send_message(
                MessageType.GET_DATA,
                getdata.serialize()
            )

    async def handle_block(self, peer: Peer, block: Block):
        """Handle received block."""
        block_hash = block.hash()
        self.downloading.discard(block_hash)

        # Validate basic structure
        valid, error = block.validate_structure()
        if not valid:
            logger.warning(f"Invalid block from {peer.address}: {error}")
            return

        # Add to pending
        self.pending_blocks[block_hash] = block

        # Update peer height if needed
        if block.height > peer.info.start_height:
            peer.info.start_height = block.height

    def get_sync_status(self) -> Dict:
        """Get current sync status."""
        return {
            "state": self.progress.state.name,
            "current_height": self.progress.current_height,
            "target_height": self.progress.target_height,
            "progress_percent": round(self.progress.progress_percent, 2),
            "blocks_downloaded": self.progress.blocks_downloaded,
            "blocks_per_second": round(self.progress.blocks_per_second, 2),
            "eta_seconds": round(self.progress.eta_seconds, 1) if self.progress.eta_seconds < float('inf') else None,
            "peer_count": len(self.peer_manager.ready_peers),
        }


class HeaderSync:
    """
    Headers-first synchronization.

    Downloads headers first, then bodies in parallel.
    More efficient for initial sync.
    """

    def __init__(
        self,
        peer_manager: PeerManager,
        validate_header: callable,
        get_header: callable,
    ):
        self.peer_manager = peer_manager
        self.validate_header = validate_header
        self.get_header = get_header

        # Header chain
        self.headers: Dict[Hash, BlockHeader] = {}
        self.header_chain: List[Hash] = []
        self.tip_hash: Optional[Hash] = None

    async def sync_headers(
        self,
        from_hash: Hash,
        peer: Peer,
    ) -> List[BlockHeader]:
        """
        Download headers from peer starting after from_hash.

        Args:
            from_hash: Hash of last known header
            peer: Peer to sync from

        Returns:
            List of new headers
        """
        # In real implementation:
        # 1. Send GetHeaders message with locator hashes
        # 2. Receive Headers message
        # 3. Validate and add to chain
        # 4. Repeat until caught up

        return []

    def add_header(self, header: BlockHeader) -> bool:
        """Add header to chain."""
        header_hash = header.hash()

        if header_hash in self.headers:
            return False

        # Validate
        if not self.validate_header(header):
            return False

        self.headers[header_hash] = header
        return True
