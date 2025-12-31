"""
ATC Protocol v7 JSON-RPC Server
Part XVII of Technical Specification

HTTP JSON-RPC server for node interaction.
"""

from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from atc.api.methods import (
    METHOD_REGISTRY,
    RPCError,
    ERROR_PARSE,
    ERROR_INVALID_REQUEST,
    ERROR_METHOD_NOT_FOUND,
    ERROR_INVALID_PARAMS,
    ERROR_INTERNAL,
)

if TYPE_CHECKING:
    from atc.node.node import Node

logger = logging.getLogger(__name__)


@dataclass
class RPCRequest:
    """JSON-RPC request."""
    jsonrpc: str
    method: str
    params: Any
    id: Any


@dataclass
class RPCResponse:
    """JSON-RPC response."""
    jsonrpc: str = "2.0"
    result: Any = None
    error: Optional[dict] = None
    id: Any = None

    def to_dict(self) -> dict:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


@dataclass
class APIServer:
    """
    JSON-RPC API Server.

    Provides HTTP interface for interacting with the ATC node.
    """
    node: "Node"
    host: str = "127.0.0.1"
    port: int = 8545
    cors_origins: List[str] = field(default_factory=list)
    max_batch_size: int = 100

    _server: Any = None
    _running: bool = False

    def __post_init__(self):
        if not self.cors_origins:
            self.cors_origins = ["*"]

    async def start(self) -> None:
        """Start the API server."""
        from aiohttp import web

        app = web.Application()

        # Routes
        app.router.add_post("/", self._handle_rpc)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/methods", self._handle_methods)

        # CORS middleware
        app.middlewares.append(self._cors_middleware)

        runner = web.AppRunner(app)
        await runner.setup()

        self._server = web.TCPSite(runner, self.host, self.port)
        await self._server.start()

        self._running = True
        logger.info(f"API server started on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            await self._server.stop()
            self._running = False
            logger.info("API server stopped")

    @staticmethod
    async def _cors_middleware(app, handler):
        """CORS middleware."""
        async def middleware_handler(request):
            if request.method == "OPTIONS":
                from aiohttp import web
                return web.Response(
                    status=200,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type",
                    }
                )

            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            return response

        return middleware_handler

    async def _handle_health(self, request) -> Any:
        """Handle health check."""
        from aiohttp import web

        status = self.node.get_status()
        return web.json_response({
            "status": "ok",
            "syncing": status.get("syncing", False),
            "height": status.get("chain_height", 0),
        })

    async def _handle_methods(self, request) -> Any:
        """Handle methods listing."""
        from aiohttp import web

        methods = list(METHOD_REGISTRY.keys())
        return web.json_response({"methods": methods})

    async def _handle_rpc(self, request) -> Any:
        """Handle JSON-RPC request."""
        from aiohttp import web

        try:
            body = await request.text()
            data = json.loads(body)
        except json.JSONDecodeError as e:
            return web.json_response(
                RPCResponse(
                    error={"code": ERROR_PARSE, "message": f"Parse error: {e}"}
                ).to_dict(),
                status=400
            )

        # Handle batch request
        if isinstance(data, list):
            if len(data) > self.max_batch_size:
                return web.json_response(
                    RPCResponse(
                        error={
                            "code": ERROR_INVALID_REQUEST,
                            "message": f"Batch size exceeds maximum ({self.max_batch_size})"
                        }
                    ).to_dict(),
                    status=400
                )

            responses = await asyncio.gather(
                *[self._process_request(req) for req in data]
            )
            return web.json_response([r.to_dict() for r in responses])

        # Handle single request
        response = await self._process_request(data)
        return web.json_response(response.to_dict())

    async def _process_request(self, data: dict) -> RPCResponse:
        """Process a single JSON-RPC request."""
        # Validate request structure
        if not isinstance(data, dict):
            return RPCResponse(
                error={"code": ERROR_INVALID_REQUEST, "message": "Invalid request"}
            )

        jsonrpc = data.get("jsonrpc")
        if jsonrpc != "2.0":
            return RPCResponse(
                error={"code": ERROR_INVALID_REQUEST, "message": "Invalid JSON-RPC version"},
                id=data.get("id")
            )

        method = data.get("method")
        if not method or not isinstance(method, str):
            return RPCResponse(
                error={"code": ERROR_INVALID_REQUEST, "message": "Missing method"},
                id=data.get("id")
            )

        params = data.get("params", [])
        req_id = data.get("id")

        # Execute method
        try:
            result = await self._execute_method(method, params)
            return RPCResponse(result=result, id=req_id)

        except RPCError as e:
            return RPCResponse(
                error={"code": e.code, "message": e.message, "data": e.data},
                id=req_id
            )

        except Exception as e:
            logger.error(f"RPC error: {e}", exc_info=True)
            return RPCResponse(
                error={"code": ERROR_INTERNAL, "message": str(e)},
                id=req_id
            )

    async def _execute_method(self, method: str, params: Any) -> Any:
        """Execute an RPC method."""
        handler = METHOD_REGISTRY.get(method)

        if handler is None:
            raise RPCError(ERROR_METHOD_NOT_FOUND, f"Method not found: {method}")

        # Convert params
        if isinstance(params, list):
            # Positional params
            return await handler(self.node, *params)
        elif isinstance(params, dict):
            # Named params
            return await handler(self.node, **params)
        elif params is None:
            return await handler(self.node)
        else:
            raise RPCError(ERROR_INVALID_PARAMS, "Invalid params format")


# Simple HTTP server fallback (no aiohttp dependency)
class SimpleAPIServer:
    """
    Simple API server using built-in http.server.

    Fallback when aiohttp is not available.
    """

    def __init__(
        self,
        node: "Node",
        host: str = "127.0.0.1",
        port: int = 8545
    ):
        self.node = node
        self.host = host
        self.port = port
        self._server = None
        self._running = False

    async def start(self) -> None:
        """Start the server."""
        import http.server
        import socketserver
        import threading

        node = self.node

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')

                try:
                    data = json.loads(body)
                    method = data.get("method", "")
                    params = data.get("params", [])
                    req_id = data.get("id")

                    handler = METHOD_REGISTRY.get(method)
                    if handler:
                        # Run async method in event loop
                        loop = asyncio.new_event_loop()
                        try:
                            if isinstance(params, list):
                                result = loop.run_until_complete(handler(node, *params))
                            elif isinstance(params, dict):
                                result = loop.run_until_complete(handler(node, **params))
                            else:
                                result = loop.run_until_complete(handler(node))

                            response = {
                                "jsonrpc": "2.0",
                                "result": result,
                                "id": req_id
                            }
                        except Exception as e:
                            response = {
                                "jsonrpc": "2.0",
                                "error": {"code": -32000, "message": str(e)},
                                "id": req_id
                            }
                        finally:
                            loop.close()
                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "error": {"code": -32601, "message": "Method not found"},
                            "id": req_id
                        }

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode('utf-8'))

                except Exception as e:
                    self.send_response(400)
                    self.end_headers()

            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress logging

        self._server = socketserver.TCPServer((self.host, self.port), Handler)
        self._running = True

        thread = threading.Thread(target=self._server.serve_forever)
        thread.daemon = True
        thread.start()

        logger.info(f"Simple API server started on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._running = False
            logger.info("Simple API server stopped")


def create_api_server(
    node: "Node",
    host: str = "127.0.0.1",
    port: int = 8545,
    **kwargs
) -> APIServer:
    """
    Create an API server.

    Tries to use aiohttp, falls back to simple server.
    """
    try:
        import aiohttp
        return APIServer(node, host, port, **kwargs)
    except ImportError:
        logger.warning("aiohttp not available, using simple server")
        return SimpleAPIServer(node, host, port)


def get_api_info() -> dict:
    """Get information about API server."""
    return {
        "protocol": "JSON-RPC 2.0",
        "default_port": 8545,
        "methods_count": len(METHOD_REGISTRY),
        "batch_support": True,
    }
