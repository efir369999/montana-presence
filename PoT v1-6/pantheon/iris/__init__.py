"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        IRIS - GODDESS OF COMMUNICATION                        ║
║                                                                               ║
║       JSON-RPC API server for node interaction, dashboards,                   ║
║       and real-time monitoring of the Proof of Time network.                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  RPC SERVER:                                                                  ║
║  ───────────                                                                  ║
║  - RPCServer:       JSON-RPC 2.0 compliant HTTP server                        ║
║  - RPCHandler:      Request handler with authentication                       ║
║  - RPCMethods:      Blockchain, wallet, and node control methods              ║
║  - RPCError:        RPC error with code and message                           ║
║  - RateLimiter:     Per-IP rate limiting                                      ║
║                                                                               ║
║  METHODS:                                                                     ║
║  ────────                                                                     ║
║  Blockchain:                                                                  ║
║  - getinfo:         Node status and sync information                          ║
║  - getblockcount:   Current block height                                      ║
║  - getblock:        Block by hash or height                                   ║
║  - getblockhash:    Block hash by height                                      ║
║  - getrawtransaction: Transaction by txid                                     ║
║  - getmempoolinfo:  Mempool statistics                                        ║
║                                                                               ║
║  Wallet:                                                                      ║
║  - getbalance:      Wallet balance                                            ║
║  - getnewaddress:   Generate new stealth address                              ║
║  - sendtoaddress:   Send transaction                                          ║
║  - listunspent:     List unspent outputs                                      ║
║                                                                               ║
║  Network:                                                                     ║
║  - getpeerinfo:     Connected peers                                           ║
║  - addnode:         Add/remove peer                                           ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .rpc import (
    # Server
    RPCServer,
    RPCHandler,
    RPCMethods,

    # Errors
    RPCError,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    WALLET_ERROR,
    INSUFFICIENT_FUNDS,
    INVALID_ADDRESS,
    INVALID_TRANSACTION,
    NOT_SYNCED,

    # Rate limiting
    RateLimiter,
)

__all__ = [
    # Server
    'RPCServer',
    'RPCHandler',
    'RPCMethods',

    # Errors
    'RPCError',
    'PARSE_ERROR',
    'INVALID_REQUEST',
    'METHOD_NOT_FOUND',
    'INVALID_PARAMS',
    'INTERNAL_ERROR',
    'WALLET_ERROR',
    'INSUFFICIENT_FUNDS',
    'INVALID_ADDRESS',
    'INVALID_TRANSACTION',
    'NOT_SYNCED',

    # Rate limiting
    'RateLimiter',
]
