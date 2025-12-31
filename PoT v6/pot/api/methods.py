"""
PoT Protocol v6 JSON-RPC Methods
Part XVII of Technical Specification

All RPC methods for the API server.
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from pot.constants import PROTOCOL_VERSION
from pot.core.types import Hash, PublicKey

if TYPE_CHECKING:
    from pot.node.node import Node

logger = logging.getLogger(__name__)


class RPCError(Exception):
    """RPC error with code and message."""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# Error codes
ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32603
ERROR_NOT_FOUND = -32000
ERROR_INVALID_TX = -32001
ERROR_INSUFFICIENT_FUNDS = -32002


# ==============================================================================
# Status Methods
# ==============================================================================

async def get_status(node: "Node") -> dict:
    """
    Get node status.

    Returns:
        Node status information
    """
    return node.get_status()


async def get_version(node: "Node") -> dict:
    """
    Get protocol version information.

    Returns:
        Version information
    """
    return {
        "protocol_version": PROTOCOL_VERSION,
        "node_version": "0.6.0",
        "network": "testnet" if node.config.testnet else "mainnet",
    }


async def get_sync_status(node: "Node") -> dict:
    """
    Get synchronization status.

    Returns:
        Sync status and progress
    """
    if node.synchronizer:
        return node.synchronizer.get_progress()
    return {"syncing": False}


# ==============================================================================
# Chain Methods
# ==============================================================================

async def get_chain_info(node: "Node") -> dict:
    """
    Get blockchain information.

    Returns:
        Chain info including height, tip hash, etc.
    """
    state = node.state_machine.current_state
    return {
        "height": state.chain_height,
        "best_hash": state.chain_tip_hash.hex(),
        "btc_height": state.btc_height,
        "btc_epoch": state.btc_epoch,
        "total_supply": state.total_supply,
        "total_heartbeats": state.total_heartbeats,
        "active_accounts": state.active_accounts,
    }


async def get_block(
    node: "Node",
    block_id: str,
    full_transactions: bool = False
) -> dict:
    """
    Get block by height or hash.

    Args:
        block_id: Block height (number) or hash (hex string)
        full_transactions: Include full transaction data

    Returns:
        Block information
    """
    if node.storage is None:
        raise RPCError(ERROR_INTERNAL, "Storage not available")

    # Parse block_id
    if block_id.isdigit():
        height = int(block_id)
        block_info = node.storage.load_block_header(height)
    else:
        block_hash = Hash(bytes.fromhex(block_id))
        block_info = node.storage.load_block_by_hash(block_hash)

    if block_info is None:
        raise RPCError(ERROR_NOT_FOUND, "Block not found")

    return block_info


async def get_block_by_height(
    node: "Node",
    height: int
) -> dict:
    """
    Get block by height.

    Args:
        height: Block height

    Returns:
        Block information
    """
    return await get_block(node, str(height))


async def get_block_by_hash(
    node: "Node",
    block_hash: str
) -> dict:
    """
    Get block by hash.

    Args:
        block_hash: Block hash (hex)

    Returns:
        Block information
    """
    return await get_block(node, block_hash)


async def get_block_count(node: "Node") -> int:
    """
    Get current block height.

    Returns:
        Current block height
    """
    return node.state_machine.get_chain_height()


async def get_best_block_hash(node: "Node") -> str:
    """
    Get best block hash.

    Returns:
        Best block hash (hex)
    """
    return node.state_machine.get_chain_tip().hex()


# ==============================================================================
# Transaction Methods
# ==============================================================================

async def get_transaction(
    node: "Node",
    tx_hash: str
) -> dict:
    """
    Get transaction by hash.

    Args:
        tx_hash: Transaction hash (hex)

    Returns:
        Transaction information
    """
    # Check mempool first
    tx_id = Hash(bytes.fromhex(tx_hash))
    if node.mempool.has_transaction(tx_id):
        return {
            "hash": tx_hash,
            "status": "pending",
            "in_mempool": True,
        }

    # Check storage
    # Note: Would need to implement transaction lookup in storage
    raise RPCError(ERROR_NOT_FOUND, "Transaction not found")


async def send_transaction(
    node: "Node",
    tx_data: str
) -> dict:
    """
    Submit a signed transaction.

    Args:
        tx_data: Serialized transaction (hex)

    Returns:
        Transaction hash and status
    """
    from pot.core.transaction import Transaction

    try:
        tx_bytes = bytes.fromhex(tx_data)
        tx, _ = Transaction.deserialize(tx_bytes)

        success = await node.submit_transaction(tx)

        if success:
            return {
                "hash": tx.transaction_id().hex(),
                "status": "pending",
            }
        else:
            raise RPCError(ERROR_INVALID_TX, "Transaction rejected")

    except ValueError as e:
        raise RPCError(ERROR_INVALID_PARAMS, f"Invalid transaction data: {e}")
    except Exception as e:
        raise RPCError(ERROR_INTERNAL, str(e))


async def get_transaction_receipt(
    node: "Node",
    tx_hash: str
) -> Optional[dict]:
    """
    Get transaction receipt (confirmation status).

    Args:
        tx_hash: Transaction hash (hex)

    Returns:
        Receipt or None if not confirmed
    """
    # Would need to implement receipt storage
    raise RPCError(ERROR_NOT_FOUND, "Receipt not found")


# ==============================================================================
# Account Methods
# ==============================================================================

async def get_account(
    node: "Node",
    address: str
) -> dict:
    """
    Get account information.

    Args:
        address: Public key (hex)

    Returns:
        Account information
    """
    try:
        pubkey = PublicKey(bytes.fromhex(address))
    except ValueError:
        raise RPCError(ERROR_INVALID_PARAMS, "Invalid address format")

    account = node.state_machine.get_account(pubkey)

    if account is None:
        return {
            "address": address,
            "balance": 0,
            "nonce": 0,
            "epoch_heartbeats": 0,
            "total_heartbeats": 0,
            "exists": False,
        }

    return {
        "address": address,
        "balance": account.balance,
        "nonce": account.nonce,
        "epoch_heartbeats": account.epoch_heartbeats,
        "total_heartbeats": account.total_heartbeats,
        "last_heartbeat_height": account.last_heartbeat_height,
        "exists": True,
    }


async def get_balance(
    node: "Node",
    address: str
) -> int:
    """
    Get account balance.

    Args:
        address: Public key (hex)

    Returns:
        Balance in atomic units
    """
    try:
        pubkey = PublicKey(bytes.fromhex(address))
    except ValueError:
        raise RPCError(ERROR_INVALID_PARAMS, "Invalid address format")

    return node.get_balance(pubkey)


async def get_nonce(
    node: "Node",
    address: str
) -> int:
    """
    Get account nonce.

    Args:
        address: Public key (hex)

    Returns:
        Current nonce
    """
    try:
        pubkey = PublicKey(bytes.fromhex(address))
    except ValueError:
        raise RPCError(ERROR_INVALID_PARAMS, "Invalid address format")

    return node.get_nonce(pubkey)


# ==============================================================================
# Mempool Methods
# ==============================================================================

async def get_mempool_info(node: "Node") -> dict:
    """
    Get mempool information.

    Returns:
        Mempool statistics
    """
    return node.get_mempool_info()


async def get_raw_mempool(
    node: "Node",
    verbose: bool = False
) -> List:
    """
    Get mempool contents.

    Args:
        verbose: Include full transaction data

    Returns:
        List of transaction hashes or full data
    """
    # Return transaction hashes
    # Would need to expose mempool transaction list
    return []


# ==============================================================================
# Network Methods
# ==============================================================================

async def get_peer_info(node: "Node") -> List[dict]:
    """
    Get connected peers.

    Returns:
        List of peer information
    """
    return node.get_peers()


async def get_peer_count(node: "Node") -> int:
    """
    Get connected peer count.

    Returns:
        Number of connected peers
    """
    return node.peer_manager.active_peer_count


async def add_peer(
    node: "Node",
    address: str,
    port: int = None
) -> bool:
    """
    Add a peer.

    Args:
        address: Peer address
        port: Peer port (optional)

    Returns:
        True if peer was added
    """
    from pot.constants import DEFAULT_PORT

    if port is None:
        port = DEFAULT_PORT

    peer = await node.peer_manager.add_peer(address, port)
    return peer is not None


async def remove_peer(
    node: "Node",
    peer_id: str
) -> bool:
    """
    Remove a peer.

    Args:
        peer_id: Peer identifier

    Returns:
        True if peer was removed
    """
    await node.peer_manager.remove_peer(peer_id)
    return True


# ==============================================================================
# Heartbeat Methods
# ==============================================================================

async def get_heartbeat(
    node: "Node",
    heartbeat_hash: str
) -> dict:
    """
    Get heartbeat by hash.

    Args:
        heartbeat_hash: Heartbeat hash (hex)

    Returns:
        Heartbeat information
    """
    raise RPCError(ERROR_NOT_FOUND, "Heartbeat not found")


async def get_pending_heartbeats(node: "Node") -> int:
    """
    Get number of pending heartbeats in mempool.

    Returns:
        Heartbeat count
    """
    return node.mempool.get_heartbeat_count()


# ==============================================================================
# Score Methods
# ==============================================================================

async def get_score(
    node: "Node",
    address: str
) -> dict:
    """
    Get account score information.

    Args:
        address: Public key (hex)

    Returns:
        Score information
    """
    from pot.consensus.score import compute_score, effective_score

    try:
        pubkey = PublicKey(bytes.fromhex(address))
    except ValueError:
        raise RPCError(ERROR_INVALID_PARAMS, "Invalid address format")

    account = node.state_machine.get_account(pubkey)

    if account is None:
        return {
            "address": address,
            "raw_score": 0.0,
            "effective_score": 0.0,
            "epoch_heartbeats": 0,
        }

    raw = compute_score(account.epoch_heartbeats)
    eff = effective_score(pubkey, node.state_machine.current_state)

    return {
        "address": address,
        "raw_score": raw,
        "effective_score": eff,
        "epoch_heartbeats": account.epoch_heartbeats,
    }


# ==============================================================================
# Method Registry
# ==============================================================================

METHOD_REGISTRY = {
    # Status
    "pot_status": get_status,
    "pot_version": get_version,
    "pot_syncStatus": get_sync_status,

    # Chain
    "pot_chainInfo": get_chain_info,
    "pot_getBlock": get_block,
    "pot_getBlockByHeight": get_block_by_height,
    "pot_getBlockByHash": get_block_by_hash,
    "pot_blockCount": get_block_count,
    "pot_bestBlockHash": get_best_block_hash,

    # Transactions
    "pot_getTransaction": get_transaction,
    "pot_sendTransaction": send_transaction,
    "pot_getTransactionReceipt": get_transaction_receipt,

    # Accounts
    "pot_getAccount": get_account,
    "pot_getBalance": get_balance,
    "pot_getNonce": get_nonce,

    # Mempool
    "pot_mempoolInfo": get_mempool_info,
    "pot_rawMempool": get_raw_mempool,

    # Network
    "pot_peerInfo": get_peer_info,
    "pot_peerCount": get_peer_count,
    "pot_addPeer": add_peer,
    "pot_removePeer": remove_peer,

    # Heartbeats
    "pot_getHeartbeat": get_heartbeat,
    "pot_pendingHeartbeats": get_pending_heartbeats,

    # Score
    "pot_getScore": get_score,
}


def get_method(name: str):
    """Get method by name."""
    return METHOD_REGISTRY.get(name)


def list_methods() -> List[str]:
    """List all available methods."""
    return list(METHOD_REGISTRY.keys())
