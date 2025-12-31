"""
ATC Protocol v7 Layer 2 Tests
Tests for Bitcoin Finalization
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import time

from atc.core.bitcoin import BitcoinAnchor
from atc.core.types import Hash
from atc.layers.layer2 import (
    # Query functions
    query_bitcoin,
    query_bitcoin_block,
    query_bitcoin_sync,
    validate_bitcoin_anchor,
    # Epoch management
    get_current_epoch,
    is_epoch_boundary,
    get_epoch_start_height,
    get_epoch_end_height,
    blocks_until_next_epoch,
    estimate_time_until_halving,
    # API queries
    query_blockstream,
    query_mempool_space,
    query_blockchain_info,
    query_blockcypher,
    # Mock oracle
    MockBitcoinOracle,
    BitcoinBlockInfo,
)
from atc.constants import (
    BTC_HALVING_INTERVAL,
    BTC_MAX_DRIFT_BLOCKS,
    BTC_BLOCK_TIME_SECONDS,
    BTC_API_CONSENSUS_MIN,
)
from atc.errors import (
    InvalidBitcoinAnchorError,
    BitcoinHeightTooOldError,
    BitcoinHashMismatchError,
    BitcoinAPIUnavailableError,
    NoBitcoinConsensusError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_oracle():
    """Create a mock Bitcoin oracle."""
    return MockBitcoinOracle(start_height=850000)


@pytest.fixture
def current_anchor(mock_oracle):
    """Get current Bitcoin anchor from oracle."""
    return mock_oracle.get_anchor()


@pytest.fixture
def old_anchor(mock_oracle):
    """Create an old Bitcoin anchor (too many blocks behind)."""
    mock_oracle.advance_blocks(BTC_MAX_DRIFT_BLOCKS + 10)
    return mock_oracle.get_block_at_height(850000)


@pytest.fixture
def mock_block_info():
    """Create mock BitcoinBlockInfo."""
    return BitcoinBlockInfo(
        height=850000,
        hash="0000000000000000000000000000000000000000000000000000000000000000",
        merkle_root="1111111111111111111111111111111111111111111111111111111111111111",
        timestamp=int(time.time()),
        difficulty=1
    )


# =============================================================================
# Test: Epoch Management
# =============================================================================

class TestEpochManagement:
    """Tests for epoch/halving management."""

    def test_get_current_epoch(self):
        """Test epoch calculation from height."""
        # Epoch 0: blocks 0-209999
        assert get_current_epoch(0) == 0
        assert get_current_epoch(100000) == 0
        assert get_current_epoch(209999) == 0

        # Epoch 1: blocks 210000-419999
        assert get_current_epoch(210000) == 1
        assert get_current_epoch(300000) == 1
        assert get_current_epoch(419999) == 1

        # Epoch 2: blocks 420000-629999
        assert get_current_epoch(420000) == 2

        # Current epoch (~4 as of 2024)
        assert get_current_epoch(850000) == 4

    def test_is_epoch_boundary(self):
        """Test epoch boundary detection."""
        assert is_epoch_boundary(0) is True
        assert is_epoch_boundary(210000) is True
        assert is_epoch_boundary(420000) is True
        assert is_epoch_boundary(630000) is True
        assert is_epoch_boundary(840000) is True

        assert is_epoch_boundary(1) is False
        assert is_epoch_boundary(209999) is False
        assert is_epoch_boundary(210001) is False
        assert is_epoch_boundary(850000) is False

    def test_get_epoch_start_height(self):
        """Test epoch start height calculation."""
        assert get_epoch_start_height(0) == 0
        assert get_epoch_start_height(1) == 210000
        assert get_epoch_start_height(2) == 420000
        assert get_epoch_start_height(4) == 840000

    def test_get_epoch_end_height(self):
        """Test epoch end height calculation."""
        assert get_epoch_end_height(0) == 209999
        assert get_epoch_end_height(1) == 419999
        assert get_epoch_end_height(2) == 629999
        assert get_epoch_end_height(4) == 1049999

    def test_blocks_until_next_epoch(self):
        """Test blocks until next halving."""
        # At epoch start
        assert blocks_until_next_epoch(0) == BTC_HALVING_INTERVAL
        assert blocks_until_next_epoch(210000) == BTC_HALVING_INTERVAL

        # Middle of epoch
        assert blocks_until_next_epoch(100000) == 110000
        assert blocks_until_next_epoch(850000) == 1050000 - 850000

        # One block before halving
        assert blocks_until_next_epoch(209999) == 1
        assert blocks_until_next_epoch(839999) == 1

    def test_estimate_time_until_halving(self):
        """Test time estimation until halving."""
        blocks = blocks_until_next_epoch(850000)
        expected_seconds = blocks * BTC_BLOCK_TIME_SECONDS

        assert estimate_time_until_halving(850000) == expected_seconds

    def test_estimate_time_is_reasonable(self):
        """Test time estimation is reasonable."""
        # Current height ~850000, next halving at 1050000
        # ~200000 blocks * 600 seconds = ~120 million seconds
        time_estimate = estimate_time_until_halving(850000)

        # Should be roughly 3-4 years in seconds
        assert time_estimate > 0
        assert time_estimate <= 210000 * 600  # Max blocks in epoch * block time


# =============================================================================
# Test: Bitcoin Anchor Validation
# =============================================================================

class TestAnchorValidation:
    """Tests for Bitcoin anchor validation."""

    def test_valid_anchor(self, mock_oracle):
        """Test validation of valid anchor."""
        current = mock_oracle.get_anchor()
        # Same height anchor is valid
        assert validate_bitcoin_anchor(current, current) is True

    def test_anchor_slightly_behind(self, mock_oracle):
        """Test anchor slightly behind is valid."""
        anchor = mock_oracle.get_anchor()
        mock_oracle.advance_blocks(5)  # Less than max drift
        current = mock_oracle.get_anchor()

        assert validate_bitcoin_anchor(anchor, current) is True

    def test_anchor_too_old(self, mock_oracle):
        """Test anchor too far behind is invalid."""
        anchor = mock_oracle.get_anchor()
        mock_oracle.advance_blocks(BTC_MAX_DRIFT_BLOCKS + 1)
        current = mock_oracle.get_anchor()

        assert validate_bitcoin_anchor(anchor, current) is False

    def test_anchor_at_max_drift(self, mock_oracle):
        """Test anchor at exactly max drift is valid."""
        anchor = mock_oracle.get_anchor()
        mock_oracle.advance_blocks(BTC_MAX_DRIFT_BLOCKS)
        current = mock_oracle.get_anchor()

        assert validate_bitcoin_anchor(anchor, current) is True

    def test_anchor_wrong_epoch(self, mock_oracle):
        """Test anchor with wrong epoch is invalid."""
        anchor = mock_oracle.get_anchor()
        # Manually set wrong epoch
        anchor.epoch = 999

        current = mock_oracle.get_anchor()
        assert validate_bitcoin_anchor(anchor, current) is False

    def test_anchor_future_timestamp(self, mock_oracle):
        """Test anchor with future timestamp is invalid."""
        current = mock_oracle.get_anchor()

        # Create anchor with timestamp too far in future
        future_anchor = BitcoinAnchor(
            height=current.height,
            block_hash=current.block_hash,
            merkle_root=current.merkle_root,
            timestamp=current.timestamp + 10000,  # Way in future
            difficulty=current.difficulty,
            epoch=current.epoch,
            confirmations=0
        )

        assert validate_bitcoin_anchor(future_anchor, current) is False


# =============================================================================
# Test: Mock Bitcoin Oracle
# =============================================================================

class TestMockBitcoinOracle:
    """Tests for MockBitcoinOracle."""

    def test_oracle_initialization(self):
        """Test oracle creates with correct initial state."""
        oracle = MockBitcoinOracle(start_height=800000)
        assert oracle.height == 800000

    def test_oracle_advance_blocks(self, mock_oracle):
        """Test advancing blocks."""
        initial_height = mock_oracle.height
        initial_time = mock_oracle.timestamp

        mock_oracle.advance_blocks(10)

        assert mock_oracle.height == initial_height + 10
        assert mock_oracle.timestamp == initial_time + (10 * BTC_BLOCK_TIME_SECONDS)

    def test_oracle_get_anchor(self, mock_oracle):
        """Test getting anchor from oracle."""
        anchor = mock_oracle.get_anchor()

        assert anchor.height == mock_oracle.height
        assert anchor.epoch == mock_oracle.height // BTC_HALVING_INTERVAL
        assert len(anchor.block_hash) == 32
        assert len(anchor.merkle_root) == 32

    def test_oracle_get_block_at_height(self, mock_oracle):
        """Test getting block at specific height."""
        mock_oracle.advance_blocks(100)

        block = mock_oracle.get_block_at_height(850000)
        assert block is not None
        assert block.height == 850000
        assert block.confirmations == 100

    def test_oracle_get_future_block(self, mock_oracle):
        """Test getting block that doesn't exist yet."""
        block = mock_oracle.get_block_at_height(mock_oracle.height + 100)
        assert block is None

    def test_oracle_deterministic_hashes(self, mock_oracle):
        """Test oracle generates deterministic hashes."""
        anchor1 = mock_oracle.get_anchor()
        anchor2 = mock_oracle.get_anchor()

        assert anchor1.block_hash == anchor2.block_hash
        assert anchor1.merkle_root == anchor2.merkle_root

    def test_oracle_different_heights_different_hashes(self, mock_oracle):
        """Test different heights produce different hashes."""
        anchor1 = mock_oracle.get_anchor()
        mock_oracle.advance_blocks(1)
        anchor2 = mock_oracle.get_anchor()

        assert anchor1.block_hash != anchor2.block_hash
        assert anchor1.merkle_root != anchor2.merkle_root


# =============================================================================
# Test: API Query Functions (Mocked)
# =============================================================================

class TestAPIQueries:
    """Tests for Bitcoin API queries with mocks."""

    @pytest.mark.asyncio
    async def test_query_blockstream_success(self, mock_block_info):
        """Test successful Blockstream query."""
        mock_client = AsyncMock()

        # Mock tip hash response
        mock_hash_resp = Mock()
        mock_hash_resp.status_code = 200
        mock_hash_resp.text = mock_block_info.hash

        # Mock block details response
        mock_block_resp = Mock()
        mock_block_resp.status_code = 200
        mock_block_resp.json.return_value = {
            "height": mock_block_info.height,
            "id": mock_block_info.hash,
            "merkle_root": mock_block_info.merkle_root,
            "timestamp": mock_block_info.timestamp,
            "difficulty": mock_block_info.difficulty
        }

        mock_client.get = AsyncMock(side_effect=[mock_hash_resp, mock_block_resp])

        result = await query_blockstream(mock_client)

        assert result is not None
        assert result.height == mock_block_info.height
        assert result.hash == mock_block_info.hash

    @pytest.mark.asyncio
    async def test_query_blockstream_timeout(self):
        """Test Blockstream query timeout."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await query_blockstream(mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_query_blockstream_error(self):
        """Test Blockstream query error."""
        mock_client = AsyncMock()
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_client.get = AsyncMock(return_value=mock_resp)

        result = await query_blockstream(mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_query_mempool_space_success(self, mock_block_info):
        """Test successful Mempool.space query."""
        mock_client = AsyncMock()

        mock_hash_resp = Mock()
        mock_hash_resp.status_code = 200
        mock_hash_resp.text = mock_block_info.hash

        mock_block_resp = Mock()
        mock_block_resp.status_code = 200
        mock_block_resp.json.return_value = {
            "height": mock_block_info.height,
            "id": mock_block_info.hash,
            "merkle_root": mock_block_info.merkle_root,
            "timestamp": mock_block_info.timestamp,
            "difficulty": mock_block_info.difficulty
        }

        mock_client.get = AsyncMock(side_effect=[mock_hash_resp, mock_block_resp])

        result = await query_mempool_space(mock_client)

        assert result is not None
        assert result.height == mock_block_info.height


# =============================================================================
# Test: Bitcoin Query with Consensus
# =============================================================================

class TestBitcoinConsensus:
    """Tests for Bitcoin multi-API consensus."""

    @pytest.mark.asyncio
    @patch('pot.layers.layer2._HTTPX_AVAILABLE', False)
    async def test_query_bitcoin_fallback(self):
        """Test fallback when httpx not available."""
        anchor = await query_bitcoin()
        assert anchor is not None
        assert anchor.height > 0

    @pytest.mark.asyncio
    @patch('pot.layers.layer2._HTTPX_AVAILABLE', True)
    @patch('pot.layers.layer2._httpx')
    async def test_query_bitcoin_all_fail(self, mock_httpx):
        """Test error when all APIs fail."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        with pytest.raises(BitcoinAPIUnavailableError):
            await query_bitcoin()


# =============================================================================
# Test: Sync Wrapper
# =============================================================================

class TestSyncWrapper:
    """Tests for synchronous wrapper."""

    @patch('pot.layers.layer2._HTTPX_AVAILABLE', False)
    def test_query_bitcoin_sync(self):
        """Test synchronous query wrapper."""
        anchor = query_bitcoin_sync()
        assert anchor is not None
        assert anchor.height > 0
