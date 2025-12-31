#!/usr/bin/env python3
"""
Proof of Time Testnet Faucet

Simple HTTP faucet that distributes testnet tokens.
"""

import json
import time
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pot.faucet")


# Configuration
FAUCET_AMOUNT = int(os.environ.get("POT_FAUCET_AMOUNT", 1000))
COOLDOWN_SECONDS = int(os.environ.get("POT_FAUCET_COOLDOWN", 3600))
RPC_ENDPOINT = os.environ.get("POT_RPC_ENDPOINT", "http://localhost:9334")
PORT = int(os.environ.get("POT_FAUCET_PORT", 8080))


# Rate limiting
request_history = defaultdict(float)  # address -> last_request_time


class FaucetHandler(BaseHTTPRequestHandler):
    """HTTP handler for faucet requests."""

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.serve_index()
        elif parsed.path == "/health":
            self.send_json({"status": "ok", "faucet_amount": FAUCET_AMOUNT})
        elif parsed.path == "/stats":
            self.serve_stats()
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)

        if parsed.path == "/request":
            self.handle_faucet_request()
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def serve_index(self):
        """Serve the faucet HTML page."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Proof of Time Testnet Faucet</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{
            color: #00d4ff;
            text-align: center;
        }}
        .info {{
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        input {{
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: none;
            border-radius: 5px;
            margin-bottom: 10px;
            box-sizing: border-box;
        }}
        button {{
            width: 100%;
            padding: 15px;
            font-size: 18px;
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }}
        button:hover {{
            background: #00b8e6;
        }}
        #result {{
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
            display: none;
        }}
        .success {{
            background: #0f5132;
            color: #d1e7dd;
        }}
        .error {{
            background: #842029;
            color: #f8d7da;
        }}
    </style>
</head>
<body>
    <h1>POT Testnet Faucet</h1>
    <div class="info">
        <p><strong>Amount:</strong> {FAUCET_AMOUNT} POT per request</p>
        <p><strong>Cooldown:</strong> {COOLDOWN_SECONDS // 60} minutes between requests</p>
        <p><strong>Network:</strong> pot-testnet-1</p>
    </div>
    <input type="text" id="address" placeholder="Enter your POT address (hex)">
    <button onclick="requestTokens()">Request Tokens</button>
    <div id="result"></div>

    <script>
        async function requestTokens() {{
            const address = document.getElementById('address').value.trim();
            const result = document.getElementById('result');

            if (!address) {{
                result.className = 'error';
                result.textContent = 'Please enter an address';
                result.style.display = 'block';
                return;
            }}

            try {{
                const response = await fetch('/request', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{address: address}})
                }});
                const data = await response.json();

                if (data.success) {{
                    result.className = 'success';
                    result.textContent = 'Success! TX: ' + data.tx_hash;
                }} else {{
                    result.className = 'error';
                    result.textContent = 'Error: ' + data.error;
                }}
            }} catch (e) {{
                result.className = 'error';
                result.textContent = 'Network error: ' + e.message;
            }}
            result.style.display = 'block';
        }}
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_stats(self):
        """Serve faucet statistics."""
        stats = {
            "faucet_amount": FAUCET_AMOUNT,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "total_requests": len(request_history),
            "rpc_endpoint": RPC_ENDPOINT
        }
        self.send_json(stats)

    def handle_faucet_request(self):
        """Handle token request."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body) if body else {}
        except Exception as e:
            self.send_json({"success": False, "error": f"Invalid request: {e}"}, 400)
            return

        address = data.get("address", "").strip()

        # Validate address
        if not address:
            self.send_json({"success": False, "error": "Address required"}, 400)
            return

        if len(address) != 64:
            self.send_json({"success": False, "error": "Invalid address format (expected 64 hex chars)"}, 400)
            return

        try:
            bytes.fromhex(address)
        except ValueError:
            self.send_json({"success": False, "error": "Invalid hex address"}, 400)
            return

        # Check rate limit
        current_time = time.time()
        last_request = request_history.get(address, 0)

        if current_time - last_request < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - (current_time - last_request))
            self.send_json({
                "success": False,
                "error": f"Rate limited. Try again in {remaining} seconds"
            }, 429)
            return

        # Send tokens (mock for now - would call RPC in production)
        tx_hash = self.send_tokens(address)

        if tx_hash:
            request_history[address] = current_time
            logger.info(f"Sent {FAUCET_AMOUNT} POT to {address[:16]}... TX: {tx_hash}")
            self.send_json({
                "success": True,
                "tx_hash": tx_hash,
                "amount": FAUCET_AMOUNT
            })
        else:
            self.send_json({"success": False, "error": "Failed to send tokens"}, 500)

    def send_tokens(self, address: str) -> str:
        """Send tokens to address (mock implementation)."""
        # In production, this would call the RPC endpoint
        # For now, generate a mock transaction hash
        import hashlib
        tx_data = f"{address}{time.time()}{FAUCET_AMOUNT}".encode()
        tx_hash = hashlib.sha256(tx_data).hexdigest()
        return tx_hash


def main():
    """Run the faucet server."""
    server = HTTPServer(("0.0.0.0", PORT), FaucetHandler)
    logger.info(f"Faucet running on http://0.0.0.0:{PORT}")
    logger.info(f"Amount: {FAUCET_AMOUNT} POT, Cooldown: {COOLDOWN_SECONDS}s")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down faucet...")
        server.shutdown()


if __name__ == "__main__":
    main()
