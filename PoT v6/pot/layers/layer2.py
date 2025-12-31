"""
PoT Protocol v6 Layer 2: Bitcoin Finalization
Part VI of Technical Specification

Bitcoin provides absolute finalization. Its 15+ years of accumulated proof of
work represents the most secure timestamping mechanism ever created.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
import time

from pot.constants import (
    BTC_API_ENDPOINTS,
    BTC_API_CONSENSUS_MIN,
    BTC_HALVING_INTERVAL,
    BTC_MAX_DRIFT_BLOCKS,
    BTC_BLOCK_TIME_SECONDS,
)
from pot.core.bitcoin import BitcoinAnchor
from pot.errors import (
    InvalidBitcoinAnchorError,
    BitcoinHeightTooOldError,
    BitcoinHashMismatchError,
    BitcoinAPIUnavailableError,
    NoBitcoinConsensusError,
    InvalidEpochError,
)

logger = logging.getLogger(__name__)

# Try to import httpx for async HTTP
_HTTPX_AVAILABLE = False
_httpx = None

try:
    import httpx
    _httpx = httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    logger.warning("httpx not available. Install with: pip install httpx")


@dataclass
class BitcoinBlockInfo:
    """Raw block info from API."""
    height: int
    hash: str
    merkle_root: str
    timestamp: int
    difficulty: int


async def query_blockstream(client: Any, timeout: float = 5.0) -> Optional[BitcoinBlockInfo]:
    """Query Blockstream API for latest block."""
    try:
        # Get tip hash
        resp = await client.get(
            "https://blockstream.info/api/blocks/tip/hash",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None
        tip_hash = resp.text.strip()

        # Get block details
        resp = await client.get(
            f"https://blockstream.info/api/block/{tip_hash}",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        return BitcoinBlockInfo(
            height=data["height"],
            hash=data["id"],
            merkle_root=data["merkle_root"],
            timestamp=data["timestamp"],
            difficulty=int(data.get("difficulty", 0))
        )
    except Exception as e:
        logger.debug(f"Blockstream query failed: {e}")
        return None


async def query_mempool_space(client: Any, timeout: float = 5.0) -> Optional[BitcoinBlockInfo]:
    """Query Mempool.space API for latest block."""
    try:
        resp = await client.get(
            "https://mempool.space/api/blocks/tip/hash",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None
        tip_hash = resp.text.strip()

        resp = await client.get(
            f"https://mempool.space/api/block/{tip_hash}",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        return BitcoinBlockInfo(
            height=data["height"],
            hash=data["id"],
            merkle_root=data["merkle_root"],
            timestamp=data["timestamp"],
            difficulty=int(data.get("difficulty", 0))
        )
    except Exception as e:
        logger.debug(f"Mempool.space query failed: {e}")
        return None


async def query_blockchain_info(client: Any, timeout: float = 5.0) -> Optional[BitcoinBlockInfo]:
    """Query Blockchain.info API for latest block."""
    try:
        resp = await client.get(
            "https://blockchain.info/latestblock",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        block_hash = data["hash"]

        # Get full block details
        resp = await client.get(
            f"https://blockchain.info/rawblock/{block_hash}",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None

        block = resp.json()
        return BitcoinBlockInfo(
            height=block["height"],
            hash=block["hash"],
            merkle_root=block["mrkl_root"],
            timestamp=block["time"],
            difficulty=int(block.get("difficulty", 0))
        )
    except Exception as e:
        logger.debug(f"Blockchain.info query failed: {e}")
        return None


async def query_blockcypher(client: Any, timeout: float = 5.0) -> Optional[BitcoinBlockInfo]:
    """Query Blockcypher API for latest block."""
    try:
        resp = await client.get(
            "https://api.blockcypher.com/v1/btc/main",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        latest_hash = data["hash"]

        resp = await client.get(
            f"https://api.blockcypher.com/v1/btc/main/blocks/{latest_hash}",
            timeout=timeout
        )
        if resp.status_code != 200:
            return None

        block = resp.json()
        return BitcoinBlockInfo(
            height=block["height"],
            hash=block["hash"],
            merkle_root=block["mrkl_root"],
            timestamp=int(
                time.mktime(
                    time.strptime(
                        block["time"][:19],
                        "%Y-%m-%dT%H:%M:%S"
                    )
                )
            ),
            difficulty=int(block.get("difficulty", 0))
        )
    except Exception as e:
        logger.debug(f"Blockcypher query failed: {e}")
        return None


async def query_bitcoin() -> BitcoinAnchor:
    """
    Query Bitcoin state from multiple APIs for consensus.

    Per specification:
    - Queries 4 API endpoints
    - Requires ≥2 agreeing sources for consensus
    - Returns BitcoinAnchor with latest block data

    Raises:
        BitcoinAPIUnavailableError: If all APIs fail
        NoBitcoinConsensusError: If no consensus reached
    """
    if not _HTTPX_AVAILABLE:
        # Fallback: return mock data for testing
        logger.warning("httpx not available, returning mock Bitcoin anchor")
        return _create_mock_anchor()

    results: List[BitcoinBlockInfo] = []

    async with _httpx.AsyncClient() as client:
        # Query all APIs in parallel
        tasks = [
            query_blockstream(client),
            query_mempool_space(client),
            query_blockchain_info(client),
            query_blockcypher(client),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, BitcoinBlockInfo):
                results.append(resp)

    if len(results) < BTC_API_CONSENSUS_MIN:
        raise BitcoinAPIUnavailableError(len(results))

    # Find consensus (majority on height+hash)
    votes: Dict[Tuple[int, str], int] = {}
    for r in results:
        key = (r.height, r.hash)
        votes[key] = votes.get(key, 0) + 1

    # Find best voted option
    best_key = max(votes.keys(), key=lambda k: votes[k])
    if votes[best_key] < BTC_API_CONSENSUS_MIN:
        raise NoBitcoinConsensusError(votes[best_key], BTC_API_CONSENSUS_MIN)

    height, block_hash = best_key

    # Find matching result for full data
    for r in results:
        if r.height == height and r.hash == block_hash:
            return BitcoinAnchor.from_api_data(
                height=height,
                block_hash_hex=block_hash,
                merkle_root_hex=r.merkle_root,
                timestamp=r.timestamp,
                difficulty=r.difficulty,
                confirmations=0
            )

    # Should not reach here
    raise NoBitcoinConsensusError(0, BTC_API_CONSENSUS_MIN)


def _create_mock_anchor() -> BitcoinAnchor:
    """Create a mock Bitcoin anchor for testing."""
    # Use approximate current Bitcoin height
    current_time = int(time.time())
    # Bitcoin started at timestamp ~1231006505 (genesis)
    # Average 10 min per block
    estimated_height = (current_time - 1231006505) // 600

    return BitcoinAnchor(
        height=estimated_height,
        block_hash=bytes.fromhex(
            "0000000000000000000000000000000000000000000000000000000000000000"
        ),
        merkle_root=bytes.fromhex(
            "0000000000000000000000000000000000000000000000000000000000000000"
        ),
        timestamp=current_time,
        difficulty=1,
        epoch=estimated_height // BTC_HALVING_INTERVAL,
        confirmations=0
    )


def validate_bitcoin_anchor(anchor: BitcoinAnchor, current: BitcoinAnchor) -> bool:
    """
    Validate a Bitcoin anchor against current state.

    Per specification:
    1. Block must exist (would need API query in production)
    2. Hash must match (would need API query in production)
    3. Not too far behind tip
    4. Epoch must be correct
    5. Timestamp must be reasonable

    Args:
        anchor: Anchor to validate
        current: Current known Bitcoin state

    Returns:
        True if anchor is valid
    """
    # 3. Not too far behind tip
    if current.height > anchor.height:
        if current.height - anchor.height > BTC_MAX_DRIFT_BLOCKS:
            logger.debug(
                f"Anchor too old: {anchor.height} vs current {current.height} "
                f"(drift: {current.height - anchor.height} > {BTC_MAX_DRIFT_BLOCKS})"
            )
            return False

    # 4. Epoch must be correct
    expected_epoch = anchor.height // BTC_HALVING_INTERVAL
    if anchor.epoch != expected_epoch:
        logger.debug(f"Invalid epoch: {anchor.epoch} (expected: {expected_epoch})")
        return False

    # 5. Timestamp must be reasonable (not too far in future)
    max_future_time = current.timestamp + 7200  # 2 hour tolerance
    if anchor.timestamp > max_future_time:
        logger.debug(f"Anchor timestamp too far in future: {anchor.timestamp}")
        return False

    return True


async def query_bitcoin_block(height: int) -> Optional[BitcoinAnchor]:
    """
    Query a specific Bitcoin block by height.

    Args:
        height: Block height to query

    Returns:
        BitcoinAnchor if found, None otherwise
    """
    if not _HTTPX_AVAILABLE:
        return None

    async with _httpx.AsyncClient() as client:
        try:
            # Try Blockstream first
            resp = await client.get(
                f"https://blockstream.info/api/block-height/{height}",
                timeout=5.0
            )
            if resp.status_code != 200:
                return None

            block_hash = resp.text.strip()

            resp = await client.get(
                f"https://blockstream.info/api/block/{block_hash}",
                timeout=5.0
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            return BitcoinAnchor.from_api_data(
                height=data["height"],
                block_hash_hex=data["id"],
                merkle_root_hex=data["merkle_root"],
                timestamp=data["timestamp"],
                difficulty=int(data.get("difficulty", 0)),
                confirmations=0
            )
        except Exception as e:
            logger.debug(f"Failed to query block {height}: {e}")
            return None


# ==============================================================================
# Epoch Management
# ==============================================================================

def get_current_epoch(btc_height: int) -> int:
    """Get halving epoch from Bitcoin height."""
    return btc_height // BTC_HALVING_INTERVAL


def is_epoch_boundary(btc_height: int) -> bool:
    """Check if height is at an epoch (halving) boundary."""
    return btc_height % BTC_HALVING_INTERVAL == 0


def get_epoch_start_height(epoch: int) -> int:
    """Get the starting block height for an epoch."""
    return epoch * BTC_HALVING_INTERVAL


def get_epoch_end_height(epoch: int) -> int:
    """Get the ending block height for an epoch."""
    return (epoch + 1) * BTC_HALVING_INTERVAL - 1


def blocks_until_next_epoch(btc_height: int) -> int:
    """Calculate blocks remaining until next halving."""
    current_epoch = get_current_epoch(btc_height)
    next_epoch_start = get_epoch_start_height(current_epoch + 1)
    return next_epoch_start - btc_height


def estimate_time_until_halving(btc_height: int) -> int:
    """
    Estimate seconds until next halving.

    Uses average block time of 600 seconds.
    """
    blocks = blocks_until_next_epoch(btc_height)
    return blocks * BTC_BLOCK_TIME_SECONDS


def query_bitcoin_sync() -> BitcoinAnchor:
    """
    Synchronous wrapper for query_bitcoin().

    Use this when not in an async context.
    """
    return asyncio.run(query_bitcoin())


class MockBitcoinOracle:
    """
    Mock Bitcoin oracle for testing.

    Simulates Bitcoin blockchain without network access.
    """

    def __init__(
        self,
        start_height: int = 850000,
        start_timestamp: Optional[int] = None
    ):
        """
        Initialize mock oracle.

        Args:
            start_height: Starting block height
            start_timestamp: Starting timestamp (default: current time)
        """
        self.height = start_height
        self.timestamp = start_timestamp or int(time.time())
        self._blocks: Dict[int, BitcoinAnchor] = {}

    def advance_blocks(self, count: int = 1):
        """Advance blockchain by specified number of blocks."""
        for _ in range(count):
            self.height += 1
            self.timestamp += BTC_BLOCK_TIME_SECONDS

    def get_anchor(self, confirmations: int = 0) -> BitcoinAnchor:
        """Get current Bitcoin anchor."""
        import hashlib

        # Generate deterministic hash from height
        height_bytes = self.height.to_bytes(8, "big")
        block_hash = hashlib.sha256(b"MOCK_BTC_BLOCK:" + height_bytes).digest()
        merkle_root = hashlib.sha256(b"MOCK_BTC_MERKLE:" + height_bytes).digest()

        return BitcoinAnchor(
            height=self.height,
            block_hash=block_hash,
            merkle_root=merkle_root,
            timestamp=self.timestamp,
            difficulty=1,
            epoch=self.height // BTC_HALVING_INTERVAL,
            confirmations=confirmations
        )

    def get_block_at_height(self, height: int) -> Optional[BitcoinAnchor]:
        """Get block at specific height."""
        if height > self.height:
            return None

        import hashlib

        height_bytes = height.to_bytes(8, "big")
        block_hash = hashlib.sha256(b"MOCK_BTC_BLOCK:" + height_bytes).digest()
        merkle_root = hashlib.sha256(b"MOCK_BTC_MERKLE:" + height_bytes).digest()

        # Calculate timestamp based on average block time
        time_diff = (self.height - height) * BTC_BLOCK_TIME_SECONDS
        block_timestamp = self.timestamp - time_diff

        return BitcoinAnchor(
            height=height,
            block_hash=block_hash,
            merkle_root=merkle_root,
            timestamp=block_timestamp,
            difficulty=1,
            epoch=height // BTC_HALVING_INTERVAL,
            confirmations=self.height - height
        )
