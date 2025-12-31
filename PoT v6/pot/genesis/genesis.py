"""
PoT Protocol v6 Genesis Block
Part XVI of Technical Specification

Genesis block creation and validation.
"""

from __future__ import annotations
import logging
from typing import List, Optional

from pot.constants import (
    PROTOCOL_VERSION,
    INITIAL_REWARD,
    DECIMALS,
)
from pot.core.types import Hash, PublicKey
from pot.core.block import Block, BlockHeader, BlockSigner
from pot.core.bitcoin import BitcoinAnchor
from pot.core.state import GlobalState, AccountState
from pot.crypto.hash import sha3_256

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


def create_genesis_block(
    testnet: bool = False,
    founders: Optional[List[PublicKey]] = None
) -> Block:
    """
    Create the genesis block.

    Per specification (Part XVI):
    - Height 0
    - Parent hash is all zeros
    - Empty heartbeats and transactions
    - Initial state with founder allocations

    Args:
        testnet: Create testnet genesis
        founders: List of founder public keys for initial allocation

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
    )

    # Empty Merkle roots for genesis
    heartbeats_root = Hash.zero()
    transactions_root = Hash.zero()

    # Initial state root (computed from founder allocations)
    state_root = _compute_genesis_state_root(founders)

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

    logger.info(f"Created genesis block: hash={genesis.block_hash().hex()[:16]}")

    return genesis


def create_genesis_state(
    testnet: bool = False,
    founders: Optional[List[PublicKey]] = None
) -> GlobalState:
    """
    Create the genesis state.

    Per specification (Part XVI):
    - Initial allocations to founders
    - Empty account states otherwise

    Args:
        testnet: Create testnet state
        founders: List of founder public keys

    Returns:
        Genesis global state
    """
    genesis_block = create_genesis_block(testnet, founders)

    state = GlobalState(
        chain_height=0,
        chain_tip_hash=genesis_block.block_hash(),
        btc_height=genesis_block.header.btc_anchor.height,
        btc_hash=genesis_block.header.btc_anchor.block_hash,
        btc_epoch=genesis_block.header.btc_anchor.epoch,
        total_supply=0,
        total_heartbeats=0,
        active_accounts=0,
    )

    # Add founder allocations
    if founders:
        allocation_per_founder = _get_founder_allocation(len(founders))

        for pubkey in founders:
            account = AccountState(
                pubkey=pubkey,
                balance=allocation_per_founder,
                nonce=0,
            )
            state.set_account(pubkey, account)
            state.total_supply += allocation_per_founder
            state.active_accounts += 1

        logger.info(
            f"Created genesis state with {len(founders)} founders, "
            f"total supply: {state.total_supply}"
        )

    return state


def _get_founder_allocation(num_founders: int) -> int:
    """
    Calculate allocation per founder.

    Genesis allocation is 10% of max supply distributed among founders.
    Max supply = 21,000,000 * 10^8 (like Bitcoin with 8 decimals)
    """
    max_supply = 21_000_000 * (10 ** DECIMALS)
    genesis_allocation = max_supply // 10  # 10%

    if num_founders == 0:
        return 0

    return genesis_allocation // num_founders


def _compute_genesis_state_root(founders: Optional[List[PublicKey]]) -> Hash:
    """Compute state root for genesis block."""
    if not founders:
        return Hash.zero()

    # Hash of founder allocations
    hasher_data = b"GENESIS_STATE:"

    allocation = _get_founder_allocation(len(founders))

    for pubkey in sorted(founders, key=lambda p: p.data):
        hasher_data += pubkey.data
        hasher_data += allocation.to_bytes(8, "big")

    return sha3_256(hasher_data)


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
    return {
        "timestamp_ms": TESTNET_GENESIS_TIMESTAMP_MS if testnet else GENESIS_TIMESTAMP_MS,
        "btc_height": TESTNET_GENESIS_BTC_HEIGHT if testnet else GENESIS_BTC_HEIGHT,
        "genesis_hash": get_genesis_hash(testnet).hex(),
        "initial_reward": INITIAL_REWARD,
        "decimals": DECIMALS,
        "max_supply": 21_000_000 * (10 ** DECIMALS),
    }
