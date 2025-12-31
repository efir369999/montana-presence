"""
PoT Protocol v6 Block Synchronization
Part XIII of Technical Specification

Block download and synchronization.
"""

from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Set, TYPE_CHECKING

from pot.core.types import Hash
from pot.network.messages import (
    Message,
    MessageType,
    GetBlocksMessage,
    BlockMessage,
    BlockInvMessage,
)
from pot.network.peer import Peer, PeerManager

if TYPE_CHECKING:
    from pot.core.block import Block

logger = logging.getLogger(__name__)


class SyncState(Enum):
    """Synchronization state."""
    IDLE = auto()
    HEADERS = auto()
    BLOCKS = auto()
    CATCHUP = auto()
    SYNCED = auto()


@dataclass
class SyncProgress:
    """Synchronization progress tracking."""
    state: SyncState = SyncState.IDLE
    target_height: int = 0
    current_height: int = 0
    blocks_downloaded: int = 0
    blocks_pending: int = 0
    start_time: float = 0.0
    bytes_downloaded: int = 0

    @property
    def progress_percent(self) -> float:
        """Get sync progress as percentage."""
        if self.target_height <= self.current_height:
            return 100.0

        total = self.target_height - self.current_height
        if total <= 0:
            return 100.0

        return (self.blocks_downloaded / total) * 100.0

    @property
    def blocks_per_second(self) -> float:
        """Get download speed in blocks per second."""
        import time
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0.0
        return self.blocks_downloaded / elapsed


@dataclass
class BlockSynchronizer:
    """
    Block synchronization manager.

    Handles downloading blocks from peers to catch up with the network.
    """
    peer_manager: PeerManager
    max_concurrent_requests: int = 8
    batch_size: int = 50
    request_timeout: float = 30.0

    # State
    progress: SyncProgress = field(default_factory=SyncProgress)
    _pending_requests: Dict[bytes, float] = field(default_factory=dict)
    _downloaded_blocks: Dict[int, bytes] = field(default_factory=dict)
    _known_hashes: Set[bytes] = field(default_factory=set)

    # Callbacks
    _on_block: Optional[callable] = None
    _on_progress: Optional[callable] = None

    def __post_init__(self):
        self.progress = SyncProgress()
        self._pending_requests = {}
        self._downloaded_blocks = {}
        self._known_hashes = set()

    def set_callbacks(
        self,
        on_block: callable = None,
        on_progress: callable = None
    ) -> None:
        """Set callbacks for sync events."""
        self._on_block = on_block
        self._on_progress = on_progress

    async def start_sync(
        self,
        current_height: int,
        current_tip: Hash
    ) -> None:
        """
        Start synchronization from current state.

        Args:
            current_height: Our current block height
            current_tip: Our current chain tip hash
        """
        import time

        # Find best peer to sync from
        best_peers = self.peer_manager.get_best_peers(5)
        if not best_peers:
            logger.warning("No peers available for sync")
            return

        # Get target height
        target_height = max(p.best_height for p in best_peers)

        if target_height <= current_height:
            logger.info("Already synced to best known height")
            self.progress.state = SyncState.SYNCED
            return

        logger.info(
            f"Starting sync from height {current_height} to {target_height}"
        )

        self.progress = SyncProgress(
            state=SyncState.BLOCKS,
            target_height=target_height,
            current_height=current_height,
            start_time=time.time(),
        )

        # Start downloading blocks
        await self._download_blocks(current_height, target_height, current_tip)

    async def _download_blocks(
        self,
        start_height: int,
        end_height: int,
        start_hash: Hash
    ) -> None:
        """Download blocks in batches."""
        current_hash = start_hash
        height = start_height

        while height < end_height and self.progress.state == SyncState.BLOCKS:
            # Get available peers
            peers = self.peer_manager.get_active_peers()
            if not peers:
                logger.warning("No peers available")
                await asyncio.sleep(5)
                continue

            # Calculate batch end
            batch_end = min(height + self.batch_size, end_height)
            self.progress.blocks_pending = batch_end - height

            # Request blocks from best peer
            peer = max(peers, key=lambda p: p.best_height)

            try:
                blocks = await self._request_blocks(
                    peer,
                    current_hash,
                    batch_end - height
                )

                if not blocks:
                    logger.warning(f"No blocks received from {peer.peer_id}")
                    await asyncio.sleep(1)
                    continue

                # Process received blocks
                for block_data in blocks:
                    if self._on_block:
                        await self._on_block(block_data)

                    self.progress.blocks_downloaded += 1
                    self.progress.bytes_downloaded += len(block_data)
                    height += 1

                    # Update progress callback
                    if self._on_progress:
                        await self._on_progress(self.progress)

                # Update hash for next batch
                from pot.core.block import Block
                if blocks:
                    last_block, _ = Block.deserialize(blocks[-1])
                    current_hash = last_block.block_hash()
                    self.progress.current_height = last_block.header.height

            except Exception as e:
                logger.error(f"Error downloading blocks: {e}")
                await asyncio.sleep(5)

        if height >= end_height:
            self.progress.state = SyncState.SYNCED
            logger.info("Synchronization complete")

    async def _request_blocks(
        self,
        peer: Peer,
        start_hash: Hash,
        count: int
    ) -> List[bytes]:
        """Request blocks from a peer."""
        # Send GET_BLOCKS request
        request = GetBlocksMessage(
            start_hash=start_hash,
            stop_hash=Hash.zero(),
            max_count=count,
        )

        if not await peer.send_message(request.to_message()):
            return []

        # Collect responses
        blocks = []
        deadline = asyncio.get_event_loop().time() + self.request_timeout

        while len(blocks) < count:
            remaining_time = deadline - asyncio.get_event_loop().time()
            if remaining_time <= 0:
                break

            message = await peer.read_message(timeout=remaining_time)
            if message is None:
                break

            if message.header.msg_type == MessageType.BLOCK:
                block_msg = BlockMessage.deserialize(message.payload)
                blocks.append(block_msg.block_data)

            elif message.header.msg_type == MessageType.BLOCK_INV:
                # End of available blocks
                break

        return blocks

    async def handle_block_announcement(
        self,
        peer: Peer,
        hashes: List[Hash]
    ) -> None:
        """Handle block inventory announcement."""
        # Filter unknown hashes
        unknown = [h for h in hashes if h.data not in self._known_hashes]

        if not unknown:
            return

        # Request unknown blocks
        for hash in unknown:
            self._known_hashes.add(hash.data)

        # If we're synced, download immediately
        if self.progress.state == SyncState.SYNCED:
            blocks = await self._request_blocks(
                peer,
                unknown[0] if unknown else Hash.zero(),
                len(unknown)
            )

            for block_data in blocks:
                if self._on_block:
                    await self._on_block(block_data)

    def get_progress(self) -> dict:
        """Get current sync progress."""
        return {
            "state": self.progress.state.name,
            "target_height": self.progress.target_height,
            "current_height": self.progress.current_height,
            "blocks_downloaded": self.progress.blocks_downloaded,
            "blocks_pending": self.progress.blocks_pending,
            "progress_percent": round(self.progress.progress_percent, 2),
            "blocks_per_second": round(self.progress.blocks_per_second, 2),
            "bytes_downloaded": self.progress.bytes_downloaded,
        }

    def is_synced(self) -> bool:
        """Check if sync is complete."""
        return self.progress.state == SyncState.SYNCED


def get_sync_info() -> dict:
    """Get information about block synchronization."""
    return {
        "states": [s.name for s in SyncState],
        "default_batch_size": 50,
        "default_max_concurrent": 8,
        "default_timeout_sec": 30,
    }
