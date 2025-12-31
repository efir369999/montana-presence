"""
ATC Protocol v7 Genesis Block
Part XVI of Technical Specification

Genesis block creation and validation.
FAIR LAUNCH - No pre-mine, no founder allocation.
"""

from __future__ import annotations
import logging

from atc.constants import (
    PROTOCOL_VERSION,
    INITIAL_REWARD,
)
from atc.core.types import Hash
from atc.core.block import Block, BlockHeader
from atc.core.bitcoin import BitcoinAnchor
from atc.core.state import GlobalState

logger = logging.getLogger(__name__)


# Genesis constants
GENESIS_TIMESTAMP_MS = 1704067200000  # 2024-01-01 00:00:00 UTC
GENESIS_BTC_HEIGHT = 824000           # Bitcoin block height at genesis
GENESIS_BTC_HASH = bytes.fromhex(
    "00000000000000000001f15342e917a8a1f8c99f3add89e5a7e5e8f0a8c85a9c"
)


# Testnet genesis (different values)
TESTNET_GENESIS_TIMESTAMP_MS = 1704067200000
TESTNET_GENESIS_BTC_HEIGHT = 824000
TESTNET_GENESIS_BTC_HASH = bytes.fromhex(
    "0000000000000000000000000000000000000000000000000000000000000000"
)


def create_genesis_block(testnet: bool = False) -> Block:
    """
    Create the genesis block.

    FAIR LAUNCH: No pre-mine, no founder allocation.
    All coins come from block rewards only.

    Per specification (Part XVI):
    - Height 0
    - Parent hash is all zeros
    - Empty heartbeats and transactions
    - Zero initial supply

    Args:
        testnet: Create testnet genesis

    Returns:
        Genesis block
    """
    if testnet:
        timestamp_ms = TESTNET_GENESIS_TIMESTAMP_MS
        btc_height = TESTNET_GENESIS_BTC_HEIGHT
        btc_hash = Hash(TESTNET_GENESIS_BTC_HASH)
    else:
        timestamp_ms = GENESIS_TIMESTAMP_MS
        btc_height = GENESIS_BTC_HEIGHT
        btc_hash = Hash(GENESIS_BTC_HASH)

    # Create Bitcoin anchor
    btc_anchor = BitcoinAnchor(
        height=btc_height,
        block_hash=btc_hash,
        merkle_root=Hash.zero(),
        timestamp=timestamp_ms // 1000,
        difficulty=0,
        epoch=btc_height // 210000,  # Bitcoin halving interval
        confirmations=0,  # Genesis has no confirmations yet
    )

    # Empty Merkle roots for genesis (fair launch)
    heartbeats_root = Hash.zero()
    transactions_root = Hash.zero()
    state_root = Hash.zero()  # Empty state - no pre-mine

    # Create header
    header = BlockHeader(
        version=PROTOCOL_VERSION,
        height=0,
        parent_hash=Hash.zero(),
        timestamp_ms=timestamp_ms,
        heartbeats_root=heartbeats_root,
        transactions_root=transactions_root,
        state_root=state_root,
        btc_anchor=btc_anchor,
    )

    # Genesis block has no signers, heartbeats, or transactions
    genesis = Block(
        header=header,
        heartbeats=[],
        transactions=[],
        signers=[],
    )

    logger.info(f"Created genesis block (fair launch): hash={genesis.block_hash().hex()[:16]}")

    return genesis


def create_genesis_state(testnet: bool = False) -> GlobalState:
    """
    Create the genesis state.

    FAIR LAUNCH: Zero initial supply.
    All coins come from block rewards only.

    Args:
        testnet: Create testnet state

    Returns:
        Genesis global state
    """
    genesis_block = create_genesis_block(testnet)

    state = GlobalState(
        chain_height=0,
        chain_tip_hash=genesis_block.block_hash(),
        btc_height=genesis_block.header.btc_anchor.height,
        btc_hash=genesis_block.header.btc_anchor.block_hash,
        btc_epoch=genesis_block.header.btc_anchor.epoch,
        total_supply=0,  # Fair launch - no pre-mine
        total_heartbeats=0,
        active_accounts=0,
    )

    logger.info("Created genesis state (fair launch): total_supply=0")

    return state


def validate_genesis_block(block: Block, testnet: bool = False) -> bool:
    """
    Validate a genesis block.

    Args:
        block: Block to validate
        testnet: Whether this is testnet

    Returns:
        True if valid genesis block
    """
    # Height must be 0
    if block.header.height != 0:
        logger.debug("Genesis height must be 0")
        return False

    # Parent hash must be zero
    if block.header.parent_hash != Hash.zero():
        logger.debug("Genesis parent hash must be zero")
        return False

    # No heartbeats
    if block.heartbeats:
        logger.debug("Genesis must have no heartbeats")
        return False

    # No transactions
    if block.transactions:
        logger.debug("Genesis must have no transactions")
        return False

    # No signers
    if block.signers:
        logger.debug("Genesis must have no signers")
        return False

    # Validate timestamp
    expected_timestamp = (
        TESTNET_GENESIS_TIMESTAMP_MS if testnet else GENESIS_TIMESTAMP_MS
    )
    if block.header.timestamp_ms != expected_timestamp:
        logger.debug("Genesis timestamp mismatch")
        return False

    # Validate Bitcoin anchor
    expected_btc_height = (
        TESTNET_GENESIS_BTC_HEIGHT if testnet else GENESIS_BTC_HEIGHT
    )
    if block.header.btc_anchor.height != expected_btc_height:
        logger.debug("Genesis Bitcoin height mismatch")
        return False

    return True


def get_genesis_hash(testnet: bool = False) -> Hash:
    """
    Get the expected genesis block hash.

    Args:
        testnet: Whether this is testnet

    Returns:
        Genesis block hash
    """
    genesis = create_genesis_block(testnet)
    return genesis.block_hash()


def get_genesis_info(testnet: bool = False) -> dict:
    """Get information about genesis block."""
    from atc.constants import TOTAL_SUPPLY, HALVING_INTERVAL, TOTAL_BLOCKS

    return {
        "timestamp_ms": TESTNET_GENESIS_TIMESTAMP_MS if testnet else GENESIS_TIMESTAMP_MS,
        "btc_height": TESTNET_GENESIS_BTC_HEIGHT if testnet else GENESIS_BTC_HEIGHT,
        "genesis_hash": get_genesis_hash(testnet).hex(),
        "initial_reward": INITIAL_REWARD,
        "total_supply": TOTAL_SUPPLY,
        "halving_interval": HALVING_INTERVAL,
        "total_blocks": TOTAL_BLOCKS,
        "fair_launch": True,
        "pre_mine": 0,
    }
