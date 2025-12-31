"""
Proof of Time - JSON-RPC API Module
Production-grade RPC server for node interaction.

Includes:
- JSON-RPC 2.0 compliant server
- Authentication support
- Rate limiting
- Blockchain query methods
- Wallet methods
- Node control methods

Time is the ultimate proof.
"""

import json
import threading
import logging
import time
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Any

from node import FullNode
from pantheon.plutus import Wallet
from pantheon.themis import Block, Transaction
from config import PROTOCOL

logger = logging.getLogger("proof_of_time.rpc")


# ============================================================================
# RPC ERRORS
# ============================================================================

class RPCError(Exception):
    """RPC error with code."""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)
    
    def to_dict(self) -> Dict:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom error codes
WALLET_ERROR = -1
INSUFFICIENT_FUNDS = -2
INVALID_ADDRESS = -3
INVALID_TRANSACTION = -4
NOT_SYNCED = -5


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Simple rate limiter per IP."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, ip: str) -> bool:
        """Check if request is allowed."""
        now = time.time()
        
        with self._lock:
            if ip not in self.requests:
                self.requests[ip] = []
            
            # Clean old entries
            cutoff = now - self.window
            self.requests[ip] = [t for t in self.requests[ip] if t > cutoff]
            
            # Check limit
            if len(self.requests[ip]) >= self.max_requests:
                return False
            
            self.requests[ip].append(now)
            return True
    
    def cleanup(self):
        """Remove old entries."""
        now = time.time()
        cutoff = now - self.window
        
        with self._lock:
            for ip in list(self.requests.keys()):
                self.requests[ip] = [t for t in self.requests[ip] if t > cutoff]
                if not self.requests[ip]:
                    del self.requests[ip]


# ============================================================================
# RPC METHODS
# ============================================================================

class RPCMethods:
    """RPC method implementations."""
    
    def __init__(self, node: FullNode, wallet: Optional[Wallet] = None):
        self.node = node
        self.wallet = wallet
    
    # =========================================================================
    # BLOCKCHAIN METHODS
    # =========================================================================
    
    def getblockchaininfo(self) -> Dict:
        """Get blockchain information."""
        tip = self.node.get_chain_tip()
        state = self.node.db.get_chain_state()
        
        return {
            "chain": "mainnet",
            "blocks": tip.height if tip else 0,
            "headers": tip.height if tip else 0,
            "bestblockhash": tip.hash.hex() if tip else "",
            "difficulty": 1,
            "mediantime": tip.timestamp if tip else 0,
            "verificationprogress": 1.0 if self.node.sync_state.name == "SYNCED" else 0.99,
            "initialblockdownload": self.node.sync_state.name != "SYNCED",
            "chainwork": "0" * 64,
            "size_on_disk": self.node.db.get_database_stats().get("db_size_bytes", 0),
            "pruned": False,
            "totalsupply": state.get("total_supply", 0) if state else 0,
        }
    
    def getblock(self, blockhash: str, verbosity: int = 1) -> Any:
        """Get block by hash."""
        try:
            block_hash = bytes.fromhex(blockhash)
        except:
            raise RPCError(INVALID_PARAMS, "Invalid block hash")
        
        block = self.node.db.get_block_by_hash(block_hash)
        if not block:
            raise RPCError(INVALID_PARAMS, "Block not found")
        
        if verbosity == 0:
            return block.serialize().hex()
        
        return self._block_to_dict(block, verbosity >= 2)
    
    def getblockbyheight(self, height: int, verbosity: int = 1) -> Any:
        """Get block by height."""
        block = self.node.get_block(height)
        if not block:
            raise RPCError(INVALID_PARAMS, "Block not found")
        
        if verbosity == 0:
            return block.serialize().hex()
        
        return self._block_to_dict(block, verbosity >= 2)
    
    def getblockhash(self, height: int) -> str:
        """Get block hash at height."""
        block = self.node.get_block(height)
        if not block:
            raise RPCError(INVALID_PARAMS, "Block not found")
        return block.hash.hex()
    
    def getblockheader(self, blockhash: str, verbose: bool = True) -> Any:
        """Get block header."""
        try:
            block_hash = bytes.fromhex(blockhash)
        except:
            raise RPCError(INVALID_PARAMS, "Invalid block hash")
        
        block = self.node.db.get_block_by_hash(block_hash)
        if not block:
            raise RPCError(INVALID_PARAMS, "Block not found")
        
        if not verbose:
            return block.header.serialize().hex()
        
        return self._header_to_dict(block.header)
    
    def getblockcount(self) -> int:
        """Get current block height."""
        tip = self.node.get_chain_tip()
        return tip.height if tip else 0
    
    def getbestblockhash(self) -> str:
        """Get best block hash."""
        tip = self.node.get_chain_tip()
        return tip.hash.hex() if tip else ""
    
    def _block_to_dict(self, block: Block, include_txs: bool = False) -> Dict:
        """Convert block to dictionary."""
        result = {
            "hash": block.hash.hex(),
            "confirmations": self.node.get_chain_tip().height - block.height + 1,
            "height": block.height,
            "version": block.header.version,
            "merkleroot": block.header.merkle_root.hex(),
            "time": block.timestamp,
            "nonce": 0,
            "difficulty": 1,
            "previousblockhash": block.header.prev_block_hash.hex(),
            "nTx": len(block.transactions),
            "size": block.size,
            "leader": block.header.leader_pubkey.hex(),
        }
        
        if include_txs:
            result["tx"] = [self._tx_to_dict(tx) for tx in block.transactions]
        else:
            result["tx"] = [tx.hash().hex() for tx in block.transactions]
        
        # Next block hash
        next_block = self.node.get_block(block.height + 1)
        if next_block:
            result["nextblockhash"] = next_block.hash.hex()
        
        return result
    
    def _header_to_dict(self, header) -> Dict:
        """Convert header to dictionary."""
        return {
            "hash": header.hash().hex(),
            "height": header.height,
            "version": header.version,
            "merkleroot": header.merkle_root.hex(),
            "time": header.timestamp,
            "previousblockhash": header.prev_block_hash.hex(),
            "leader": header.leader_pubkey.hex(),
        }
    
    # =========================================================================
    # TRANSACTION METHODS
    # =========================================================================
    
    def getrawtransaction(self, txid: str, verbose: bool = False) -> Any:
        """Get raw transaction."""
        try:
            tx_hash = bytes.fromhex(txid)
        except:
            raise RPCError(INVALID_PARAMS, "Invalid txid")
        
        tx = self.node.get_transaction(tx_hash)
        if not tx:
            # Check mempool
            if tx_hash in self.node.mempool.transactions:
                tx = self.node.mempool.transactions[tx_hash]
            else:
                raise RPCError(INVALID_PARAMS, "Transaction not found")
        
        if not verbose:
            return tx.serialize().hex()
        
        return self._tx_to_dict(tx)
    
    def sendrawtransaction(self, hexstring: str) -> str:
        """Submit raw transaction."""
        try:
            tx_data = bytes.fromhex(hexstring)
            tx, _ = Transaction.deserialize(tx_data)
        except Exception as e:
            raise RPCError(INVALID_TRANSACTION, f"Invalid transaction: {e}")
        
        if not self.node.submit_transaction(tx):
            raise RPCError(INVALID_TRANSACTION, "Transaction rejected")
        
        return tx.hash().hex()
    
    def getmempoolinfo(self) -> Dict:
        """Get mempool information."""
        return {
            "size": self.node.mempool.get_count(),
            "bytes": self.node.mempool.get_size(),
            "usage": self.node.mempool.get_size(),
            "maxmempool": self.node.mempool.max_size,
            "mempoolminfee": PROTOCOL.MIN_FEE,
        }
    
    def getrawmempool(self, verbose: bool = False) -> Any:
        """Get mempool contents."""
        txids = list(self.node.mempool.transactions.keys())
        
        if not verbose:
            return [txid.hex() for txid in txids]
        
        result = {}
        for txid in txids:
            tx = self.node.mempool.transactions.get(txid)
            if tx:
                result[txid.hex()] = {
                    "size": len(tx.serialize()),
                    "fee": tx.fee,
                    "time": int(time.time()),
                }
        return result
    
    def _tx_to_dict(self, tx: Transaction) -> Dict:
        """Convert transaction to dictionary."""
        return {
            "txid": tx.hash().hex(),
            "version": tx.version,
            "type": tx.tx_type.name,
            "size": tx.size,
            "fee": tx.fee,
            "vin": [
                {
                    "ring_size": len(inp.ring),
                    "key_image": inp.key_image.hex(),
                }
                for inp in tx.inputs
            ],
            "vout": [
                {
                    "n": out.output_index,
                    "stealth_address": out.stealth_address.hex(),
                    "commitment": out.commitment.hex(),
                }
                for out in tx.outputs
            ],
        }
    
    # =========================================================================
    # NETWORK METHODS
    # =========================================================================
    
    def getnetworkinfo(self) -> Dict:
        """Get network information."""
        return {
            "version": PROTOCOL.PROTOCOL_VERSION,
            "subversion": "/ProofOfTime:1.0.0/",
            "protocolversion": PROTOCOL.PROTOCOL_VERSION,
            "connections": self.node.network.get_peer_count(),
            "networks": [
                {"name": "ipv4", "reachable": True},
            ],
            "relayfee": PROTOCOL.MIN_FEE,
            "localaddresses": [],
        }
    
    def getpeerinfo(self) -> List[Dict]:
        """Get peer information."""
        return self.node.network.get_peer_info()
    
    def getconnectioncount(self) -> int:
        """Get connection count."""
        return self.node.network.get_peer_count()
    
    def addnode(self, node: str, command: str) -> None:
        """Add/remove node."""
        parts = node.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else PROTOCOL.PROTOCOL_VERSION
        
        if command == "add":
            self.node.connect_peer(host, port)
        elif command == "remove":
            self.node.disconnect_peer(host, port)
        elif command == "onetry":
            self.node.connect_peer(host, port)
    
    # =========================================================================
    # WALLET METHODS
    # =========================================================================
    
    def getbalance(self) -> Dict:
        """Get wallet balance."""
        if not self.wallet:
            raise RPCError(WALLET_ERROR, "Wallet not loaded")
        
        confirmed, pending = self.wallet.get_balance()
        return {
            "confirmed": confirmed,
            "pending": pending,
            "total": confirmed + pending,
            "confirmed_formatted": self._format_time(confirmed),
            "pending_formatted": self._format_time(pending),
        }
    
    def getnewaddress(self, account: int = 0) -> str:
        """Generate new address."""
        if not self.wallet:
            raise RPCError(WALLET_ERROR, "Wallet not loaded")
        
        address, index = self.wallet.generate_new_address(account)
        return address.hex()
    
    def getaddress(self, major: int = 0, minor: int = 0) -> str:
        """Get address at index."""
        if not self.wallet:
            raise RPCError(WALLET_ERROR, "Wallet not loaded")
        
        return self.wallet.get_address(major, minor).hex()
    
    def sendtoaddress(self, address: str, amount: int, fee: int = PROTOCOL.MIN_FEE) -> str:
        """Send to address."""
        if not self.wallet:
            raise RPCError(WALLET_ERROR, "Wallet not loaded")
        
        try:
            addr_bytes = bytes.fromhex(address)
        except:
            raise RPCError(INVALID_ADDRESS, "Invalid address")
        
        if len(addr_bytes) != 64:
            raise RPCError(INVALID_ADDRESS, "Invalid address length")
        
        tx = self.wallet.create_transaction(
            destinations=[(addr_bytes, amount)],
            fee=fee
        )
        
        if not tx:
            raise RPCError(INSUFFICIENT_FUNDS, "Insufficient funds")
        
        if not self.node.submit_transaction(tx):
            raise RPCError(INVALID_TRANSACTION, "Transaction rejected")
        
        return tx.hash().hex()
    
    def listtransactions(self, count: int = 10) -> List[Dict]:
        """List wallet transactions."""
        if not self.wallet:
            raise RPCError(WALLET_ERROR, "Wallet not loaded")
        
        history = self.wallet.get_transaction_history(count)
        return [
            {
                "txid": tx.txid.hex(),
                "type": tx.tx_type.name,
                "amount": tx.net_amount,
                "amount_formatted": self._format_time(abs(tx.net_amount)),
                "direction": "receive" if tx.net_amount > 0 else "send",
                "fee": tx.fee,
                "confirmations": self.node.get_chain_tip().height - tx.block_height + 1
                    if tx.block_height > 0 else 0,
                "time": tx.timestamp,
            }
            for tx in history
        ]
    
    def listunspent(self) -> List[Dict]:
        """List unspent outputs."""
        if not self.wallet:
            raise RPCError(WALLET_ERROR, "Wallet not loaded")
        
        outputs = self.wallet.get_spendable_outputs()
        return [
            {
                "txid": o.txid.hex(),
                "vout": o.output_index,
                "amount": o.amount,
                "amount_formatted": self._format_time(o.amount),
                "confirmations": self.node.get_chain_tip().height - o.block_height + 1,
            }
            for o in outputs
        ]
    
    def _format_time(self, seconds: int) -> str:
        """Format time in human-readable format."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            return f"{seconds // 60} minutes {seconds % 60} seconds"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} hours {minutes} minutes"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days} days {hours} hours"
    
    # =========================================================================
    # MINING/STAKING METHODS
    # =========================================================================
    
    def getmininginfo(self) -> Dict:
        """Get mining information."""
        tip = self.node.get_chain_tip()
        
        return {
            "blocks": tip.height if tip else 0,
            "currentblockreward": get_block_reward(tip.height if tip else 0),
            "currentblockreward_formatted": self._format_time(
                get_block_reward(tip.height if tip else 0)
            ),
            "difficulty": 1,
            "networkhashps": 0,
            "pooledtx": self.node.mempool.get_count(),
            "chain": "mainnet",
        }
    
    def getnodeprobabilities(self) -> Dict[str, float]:
        """Get node selection probabilities."""
        probs = self.node.consensus.compute_probabilities()
        return {pk.hex(): p for pk, p in probs.items()}
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def validateaddress(self, address: str) -> Dict:
        """Validate address."""
        try:
            addr_bytes = bytes.fromhex(address)
            is_valid = len(addr_bytes) == 64
        except:
            is_valid = False
        
        return {
            "isvalid": is_valid,
            "address": address if is_valid else "",
        }
    
    def getinfo(self) -> Dict:
        """Get general node info."""
        return self.node.get_info()
    
    def stop(self) -> str:
        """Stop the node."""
        threading.Thread(target=self.node.stop, daemon=True).start()
        return "Node stopping"
    
    def help(self, command: str = "") -> str:
        """Get help for commands."""
        methods = [
            # Blockchain
            ("getblockchaininfo", "Get blockchain state"),
            ("getblock", "Get block by hash"),
            ("getblockbyheight", "Get block by height"),
            ("getblockhash", "Get block hash at height"),
            ("getblockheader", "Get block header"),
            ("getblockcount", "Get block count"),
            ("getbestblockhash", "Get best block hash"),
            # Transaction
            ("getrawtransaction", "Get raw transaction"),
            ("sendrawtransaction", "Submit raw transaction"),
            ("getmempoolinfo", "Get mempool info"),
            ("getrawmempool", "Get mempool contents"),
            # Network
            ("getnetworkinfo", "Get network info"),
            ("getpeerinfo", "Get peer info"),
            ("getconnectioncount", "Get connection count"),
            ("addnode", "Add peer"),
            # Wallet
            ("getbalance", "Get wallet balance"),
            ("getnewaddress", "Generate new address"),
            ("getaddress", "Get address at index"),
            ("sendtoaddress", "Send to address"),
            ("listtransactions", "List transactions"),
            ("listunspent", "List unspent outputs"),
            # Mining
            ("getmininginfo", "Get mining info"),
            ("getnodeprobabilities", "Get node probabilities"),
            # Utility
            ("validateaddress", "Validate address"),
            ("getinfo", "Get node info"),
            ("stop", "Stop node"),
            ("help", "Get help"),
        ]
        
        if command:
            for name, desc in methods:
                if name == command:
                    return f"{name}: {desc}"
            return f"Unknown command: {command}"
        
        return "\n".join(f"{name}: {desc}" for name, desc in methods)


def get_block_reward(height: int) -> int:
    """Calculate block reward."""
    halvings = height // PROTOCOL.HALVING_INTERVAL
    if halvings >= 33:
        return 0
    return PROTOCOL.INITIAL_REWARD >> halvings


# ============================================================================
# HTTP SERVER
# ============================================================================

class RPCHandler(BaseHTTPRequestHandler):
    """HTTP request handler for JSON-RPC."""
    
    rpc_methods: Optional[RPCMethods] = None
    rate_limiter: Optional[RateLimiter] = None
    auth_required: bool = False
    auth_username: str = ""
    auth_password: str = ""
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.debug(f"RPC: {args[0]}")
    
    def do_POST(self):
        """Handle POST request."""
        # Rate limiting
        client_ip = self.client_address[0]
        if self.rate_limiter and not self.rate_limiter.is_allowed(client_ip):
            self._send_error(429, "Rate limit exceeded")
            return
        
        # Authentication
        if self.auth_required:
            if not self._check_auth():
                self._send_error(401, "Unauthorized")
                return
        
        # Parse request
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
        except Exception as e:
            self._send_json_error(None, PARSE_ERROR, str(e))
            return
        
        # Handle request
        response = self._handle_request(request)
        self._send_json_response(response)
    
    def _handle_request(self, request: Dict) -> Dict:
        """Handle JSON-RPC request."""
        request_id = request.get("id")
        
        # Validate request
        if request.get("jsonrpc") != "2.0":
            return self._error_response(request_id, INVALID_REQUEST, "Invalid JSON-RPC version")
        
        method = request.get("method")
        if not method:
            return self._error_response(request_id, INVALID_REQUEST, "Missing method")
        
        params = request.get("params", [])
        
        # Get method
        if not hasattr(self.rpc_methods, method):
            return self._error_response(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")
        
        func = getattr(self.rpc_methods, method)
        
        # Call method
        try:
            if isinstance(params, list):
                result = func(*params)
            elif isinstance(params, dict):
                result = func(**params)
            else:
                result = func()
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        
        except RPCError as e:
            return self._error_response(request_id, e.code, e.message, e.data)
        except TypeError as e:
            return self._error_response(request_id, INVALID_PARAMS, str(e))
        except Exception as e:
            logger.error(f"RPC error in {method}: {e}")
            return self._error_response(request_id, INTERNAL_ERROR, str(e))
    
    def _error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> Dict:
        """Create error response."""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error
        }
    
    def _check_auth(self) -> bool:
        """Check HTTP Basic authentication."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return False
        
        try:
            credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, password = credentials.split(":", 1)
            return username == self.auth_username and password == self.auth_password
        except:
            return False
    
    def _send_json_response(self, response: Dict):
        """Send JSON response."""
        body = json.dumps(response).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def _send_json_error(self, request_id: Any, code: int, message: str):
        """Send JSON-RPC error."""
        response = self._error_response(request_id, code, message)
        self._send_json_response(response)
    
    def _send_error(self, code: int, message: str):
        """Send HTTP error."""
        self.send_error(code, message)


# ============================================================================
# RPC SERVER
# ============================================================================

class RPCServer:
    """JSON-RPC server for node."""
    
    def __init__(
        self,
        node: FullNode,
        wallet: Optional[Wallet] = None,
        host: str = "127.0.0.1",
        port: int = 8332,
        username: str = "",
        password: str = ""
    ):
        self.node = node
        self.wallet = wallet
        self.host = host
        self.port = port
        
        # Set up handler
        self.methods = RPCMethods(node, wallet)
        self.rate_limiter = RateLimiter()
        
        RPCHandler.rpc_methods = self.methods
        RPCHandler.rate_limiter = self.rate_limiter
        RPCHandler.auth_required = bool(username and password)
        RPCHandler.auth_username = username
        RPCHandler.auth_password = password
        
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start RPC server."""
        self.server = HTTPServer((self.host, self.port), RPCHandler)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"RPC server started on {self.host}:{self.port}")
    
    def stop(self):
        """Stop RPC server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        logger.info("RPC server stopped")


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    logger.info("Running RPC self-tests...")
    
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        from config import StorageConfig, NodeConfig
        
        config = NodeConfig()
        config.storage = StorageConfig(db_path=os.path.join(tmpdir, "test.db"))
        
        # Create node
        node = FullNode(config)
        node._init_chain()
        
        # Create RPC methods
        methods = RPCMethods(node)
        
        # Test blockchain methods
        info = methods.getblockchaininfo()
        assert "blocks" in info
        assert "bestblockhash" in info
        logger.info("✓ getblockchaininfo")
        
        count = methods.getblockcount()
        assert count == 0
        logger.info("✓ getblockcount")
        
        # Test network methods
        netinfo = methods.getnetworkinfo()
        assert "version" in netinfo
        logger.info("✓ getnetworkinfo")
        
        # Test mempool methods
        mpinfo = methods.getmempoolinfo()
        assert "size" in mpinfo
        logger.info("✓ getmempoolinfo")
        
        # Test help
        help_text = methods.help()
        assert "getblock" in help_text
        logger.info("✓ help")
        
        # Test general info
        node_info = methods.getinfo()
        assert "height" in node_info
        logger.info("✓ getinfo")
        
        # Cleanup
        node.db.close()
    
    logger.info("All RPC self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
