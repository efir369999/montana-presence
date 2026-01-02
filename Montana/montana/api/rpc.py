"""
Ɉ Montana JSON-RPC Server v3.1

JSON-RPC 2.0 API per MONTANA_TECHNICAL_SPECIFICATION.md §20.1.
"""

from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from aiohttp import web

from montana.constants import RPC_PORT
from montana.core.types import Hash

logger = logging.getLogger(__name__)


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class RPCMethod:
    """RPC method definition."""
    name: str
    handler: Callable
    params: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class RPCRequest:
    """JSON-RPC request."""
    jsonrpc: str
    method: str
    params: Any = None
    id: Any = None


@dataclass
class RPCResponse:
    """JSON-RPC response."""
    jsonrpc: str = "2.0"
    result: Any = None
    error: Optional[Dict] = None
    id: Any = None

    def to_dict(self) -> Dict:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


class RPCServer:
    """
    JSON-RPC 2.0 server.

    Provides API endpoints for:
    - Node status
    - Timechain queries
    - Transaction submission
    - Account information
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = RPC_PORT,
    ):
        self.host = host
        self.port = port

        self._methods: Dict[str, RPCMethod] = {}
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._running = False

        # Register default methods
        self._register_default_methods()

    def _register_default_methods(self):
        """Register built-in RPC methods."""

        @self.method("montana_version")
        async def get_version():
            """Get Montana protocol version."""
            from montana.constants import PROTOCOL_VERSION
            return {
                "protocol": PROTOCOL_VERSION,
                "client": "Montana/0.1.0",
            }

        @self.method("montana_nodeInfo")
        async def get_node_info():
            """Get node information."""
            return {
                "node_type": "FULL",
                "services": 7,  # NODE_NETWORK | NODE_VDF 
                "version": "0.1.0",
            }

        @self.method("montana_syncing")
        async def get_syncing():
            """Get sync status."""
            return {
                "syncing": False,
                "current_block": 0,
                "highest_block": 0,
            }

    def method(self, name: str, params: List[str] = None, description: str = ""):
        """Decorator to register RPC method."""
        def decorator(func: Callable) -> Callable:
            self._methods[name] = RPCMethod(
                name=name,
                handler=func,
                params=params or [],
                description=description or func.__doc__ or "",
            )
            return func
        return decorator

    def register_method(self, method: RPCMethod):
        """Register an RPC method."""
        self._methods[method.name] = method

    async def start(self):
        """Start the RPC server."""
        if self._running:
            return

        self._app = web.Application()
        self._app.router.add_post("/", self._handle_request)
        self._app.router.add_get("/", self._handle_get)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

        self._running = True
        logger.info(f"RPC server listening on http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the RPC server."""
        if not self._running:
            return

        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        self._running = False
        logger.info("RPC server stopped")

    async def _handle_get(self, request: web.Request) -> web.Response:
        """Handle GET request (health check)."""
        return web.json_response({
            "status": "ok",
            "methods": list(self._methods.keys()),
        })

    async def _handle_request(self, request: web.Request) -> web.Response:
        """Handle JSON-RPC request."""
        try:
            body = await request.text()
            data = json.loads(body)
        except json.JSONDecodeError:
            return web.json_response(
                RPCResponse(error={"code": PARSE_ERROR, "message": "Parse error"}).to_dict()
            )

        # Handle batch requests
        if isinstance(data, list):
            responses = await asyncio.gather(*[
                self._process_request(req) for req in data
            ])
            return web.json_response([r.to_dict() for r in responses])

        # Single request
        response = await self._process_request(data)
        return web.json_response(response.to_dict())

    async def _process_request(self, data: Dict) -> RPCResponse:
        """Process a single RPC request."""
        # Validate request
        if not isinstance(data, dict):
            return RPCResponse(error={"code": INVALID_REQUEST, "message": "Invalid request"})

        if data.get("jsonrpc") != "2.0":
            return RPCResponse(error={"code": INVALID_REQUEST, "message": "Invalid JSON-RPC version"})

        method_name = data.get("method")
        if not method_name:
            return RPCResponse(error={"code": INVALID_REQUEST, "message": "Missing method"})

        req_id = data.get("id")
        params = data.get("params", [])

        # Find method
        if method_name not in self._methods:
            return RPCResponse(
                id=req_id,
                error={"code": METHOD_NOT_FOUND, "message": f"Method not found: {method_name}"}
            )

        method = self._methods[method_name]

        # Execute method
        try:
            if isinstance(params, list):
                result = await method.handler(*params)
            elif isinstance(params, dict):
                result = await method.handler(**params)
            else:
                result = await method.handler()

            return RPCResponse(id=req_id, result=result)

        except TypeError as e:
            return RPCResponse(
                id=req_id,
                error={"code": INVALID_PARAMS, "message": str(e)}
            )
        except Exception as e:
            logger.error(f"RPC error in {method_name}: {e}")
            return RPCResponse(
                id=req_id,
                error={"code": INTERNAL_ERROR, "message": str(e)}
            )


def create_node_rpc(node) -> RPCServer:
    """
    Create RPC server with node methods.

    Args:
        node: FullNode or LightNode instance

    Returns:
        Configured RPCServer
    """
    rpc = RPCServer()

    @rpc.method("montana_blockNumber")
    async def get_block_number():
        """Get current block height."""
        if hasattr(node, 'block_store') and node.block_store:
            return await node.block_store.get_height()
        return 0

    @rpc.method("montana_getBlockByNumber")
    async def get_block_by_number(number: int, full: bool = False):
        """Get block by height."""
        if hasattr(node, 'block_store') and node.block_store:
            blocks = await node.block_store.get_blocks_at_height(number)
            if blocks:
                block = blocks[0]
                return {
                    "hash": block.hash().hex(),
                    "height": block.height,
                    "timestamp": block.timestamp_ms,
                    "parent_hashes": [h.hex() for h in block.parent_hashes],
                    "heartbeat_count": len(block.heartbeats),
                    "tx_count": len(block.transactions),
                }
        return None

    @rpc.method("montana_getBlockByHash")
    async def get_block_by_hash(hash_hex: str, full: bool = False):
        """Get block by hash."""
        if hasattr(node, 'block_store') and node.block_store:
            block_hash = Hash(bytes.fromhex(hash_hex))
            block = await node.block_store.get_block(block_hash)
            if block:
                return {
                    "hash": block.hash().hex(),
                    "height": block.height,
                    "timestamp": block.timestamp_ms,
                    "parent_hashes": [h.hex() for h in block.parent_hashes],
                    "heartbeat_count": len(block.heartbeats),
                    "tx_count": len(block.transactions),
                }
        return None

    @rpc.method("montana_getBalance")
    async def get_balance(address: str):
        """Get account balance."""
        if hasattr(node, 'accounts') and node.accounts:
            addr_hash = Hash(bytes.fromhex(address))
            account = await node.accounts.get_account(addr_hash)
            return {
                "balance": account.balance,
                "balance_mont": account.balance_mont,
                "nonce": account.nonce,
            }
        return {"balance": 0, "balance_mont": 0.0, "nonce": 0}

    @rpc.method("montana_getScore")
    async def get_score(address: str):
        """Get account participation score."""
        if hasattr(node, 'accounts') and node.accounts:
            addr_hash = Hash(bytes.fromhex(address))
            account = await node.accounts.get_account(addr_hash)
            return {
                "score": account.score,
                "heartbeat_count": account.heartbeat_count,
                "tier": account.privacy_tier.name,
            }
        return {"score": 0.0, "heartbeat_count": 0}

    @rpc.method("montana_sendRawTransaction")
    async def send_raw_transaction(tx_hex: str):
        """Submit raw transaction."""
        tx_data = bytes.fromhex(tx_hex)
        # Would validate and add to mempool
        return {"txHash": Hash(tx_data[:32]).hex()}

    @rpc.method("montana_peerCount")
    async def get_peer_count():
        """Get number of connected peers."""
        if hasattr(node, 'peer_manager') and node.peer_manager:
            return node.peer_manager.peer_count
        return 0

    @rpc.method("montana_vdfStatus")
    async def get_vdf_status():
        """Get VDF status."""
        if hasattr(node, 'vdf') and node.vdf:
            return {
                "iterations": node.vdf.total_iterations,
                "output": node.vdf.current_output.hex() if node.vdf.current_output else None,
            }
        return {"iterations": 0, "output": None}

    @rpc.method("montana_mempoolSize")
    async def get_mempool_size():
        """Get mempool size."""
        if hasattr(node, 'mempool') and node.mempool:
            return {
                "size": node.mempool.size,
                "bytes": node.mempool.total_bytes,
            }
        return {"size": 0, "bytes": 0}

    return rpc
