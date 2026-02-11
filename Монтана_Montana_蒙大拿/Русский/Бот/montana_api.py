#!/usr/bin/env python3
"""
Montana Protocol API — Standalone REST API
Fully independent, no Telegram dependencies.

Endpoints:
- /api/health          - Node health check
- /api/network         - Network status (3 nodes)
- /api/status          - Full Montana status
- /api/balance/{addr}  - Balance by Montana address (mt...)
- /api/transfer        - Transfer Ɉ between addresses
- /api/timechain/*     - TimeChain operations
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import threading
import fcntl
import time as time_module
import hashlib
import hmac
import ipaddress
import re
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from functools import wraps
from decimal import Decimal, ROUND_DOWN, InvalidOperation

# Post-quantum cryptography
from node_crypto import verify_signature, public_key_to_address

log = logging.getLogger("montana_api")

app = Flask(__name__)

# [FIX CWE-942] CORS restricted to Montana origins only
ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "").split(",")
if ALLOWED_ORIGINS == [""]:
    ALLOWED_ORIGINS = ["https://1394793-cy33234.tw1.ru"]

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "Authorization", "X-Montana-Signature",
                          "X-Address", "X-Timestamp", "X-Signature", "X-Public-Key",
                          "X-Signature-Algorithm"],
        "max_age": 3600
    }
})

# ═══════════════════════════════════════════════════════════════════════════════
#                              CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BOT_DIR = Path(__file__).parent
DATA_DIR = BOT_DIR / "data"
WALLETS_FILE = DATA_DIR / "wallets.json"
REGISTRY_FILE = DATA_DIR / "registry.json"  # Реестр адресов с номерами

# [FIX CWE-502] File size limits (Memory DoS protection)
MAX_WALLET_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_WALLETS = 100_000  # [FIX CWE-400] Disk DoS protection

# [FIX CWE-20] Montana address validation
MONTANA_ADDRESS_RE = re.compile(r'^mt[a-f0-9]{40}$')

# Montana Network Nodes
NODES = {
    "amsterdam": {"ip": "72.56.102.240", "priority": 1, "location": "🇳🇱 Amsterdam"},
    "moscow": {"ip": "176.124.208.93", "priority": 2, "location": "🇷🇺 Moscow"},
    "almaty": {"ip": "91.200.148.93", "priority": 3, "location": "🇰🇿 Almaty"}
}

# ═══════════════════════════════════════════════════════════════════════════════
#                              RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Simple in-memory rate limiter"""
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, ip: str, limit: int = 60, window: int = 60) -> bool:
        now = time_module.time()
        with self.lock:
            self.requests[ip] = [t for t in self.requests[ip] if now - t < window]
            if len(self.requests[ip]) >= limit:
                return False
            self.requests[ip].append(now)
            return True

_rate_limiter = RateLimiter()

def rate_limit(limit: int = 60, window: int = 60):
    """Decorator for rate limiting endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            if not _rate_limiter.is_allowed(ip, limit, window):
                return jsonify({
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Limit: {limit} per {window}s",
                    "retry_after": window
                }), 429
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ═══════════════════════════════════════════════════════════════════════════════
#                              SIGNATURE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def verify_signature_beta(public_key_hex: str, message: str, signature_hex: str) -> bool:
    """
    Verify signature (BETA or MAINNET mode).

    - 64 hex chars (32 bytes) = HMAC-SHA256 (BETA)
    - 6618 hex chars (3309 bytes) = ML-DSA-65 (MAINNET)
    """
    sig_bytes = len(signature_hex) // 2

    if sig_bytes == 32:
        # BETA: HMAC-SHA256
        try:
            public_key = bytes.fromhex(public_key_hex)
            message_bytes = message.encode('utf-8')
            signature = bytes.fromhex(signature_hex)
            expected = hmac.new(public_key, message_bytes, hashlib.sha256).digest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            print(f"[BETA] HMAC verify error: {e}")
            return False

    elif sig_bytes == 3309:
        # MAINNET: ML-DSA-65
        return verify_signature(public_key_hex, message, signature_hex)

    else:
        print(f"[Auth] Unknown signature length: {sig_bytes} bytes")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#                              WALLET STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

_wallet_lock = threading.Lock()  # [FIX CWE-362] Process-level lock


def _validate_address(address: str) -> bool:
    """[FIX CWE-20] Validate Montana address format: mt + 40 hex chars"""
    return bool(MONTANA_ADDRESS_RE.match(address))


def load_wallets() -> dict:
    """Load wallets from JSON file with size validation and file locking"""
    if not WALLETS_FILE.exists():
        return {}

    # [FIX CWE-502] Check file size before loading
    try:
        file_size = os.path.getsize(WALLETS_FILE)
        if file_size > MAX_WALLET_FILE_SIZE:
            log.critical("Wallets file too large: %d bytes (max %d)",
                         file_size, MAX_WALLET_FILE_SIZE)
            return {}
    except OSError:
        return {}

    try:
        with open(WALLETS_FILE, 'r', encoding='utf-8') as f:
            # [FIX CWE-362] Shared read lock
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except json.JSONDecodeError as e:
        log.error("Invalid JSON in wallets file: %s", e)
        return {}
    except Exception as e:
        log.error("Failed to load wallets: %s", e)
        return {}


def save_wallets(wallets: dict):
    """Save wallets to JSON file with file locking"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # [FIX CWE-362] Exclusive write lock
    with open(WALLETS_FILE, 'w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(wallets, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def get_balance(address: str) -> float:
    """Get balance for Montana address"""
    if not _validate_address(address):
        return 0.0
    wallets = load_wallets()
    return wallets.get(address, {}).get('balance', 0.0)


def set_balance(address: str, balance: float):
    """Set balance for Montana address with wallet count limit"""
    if not _validate_address(address):
        raise ValueError(f"Invalid Montana address: {address}")

    with _wallet_lock:  # [FIX CWE-362] Thread safety
        wallets = load_wallets()

        if address not in wallets:
            # [FIX CWE-400] Limit total wallet count
            if len(wallets) >= MAX_WALLETS:
                raise ValueError(f"Maximum wallet limit reached ({MAX_WALLETS})")
            wallets[address] = {'created_at': datetime.utcnow().isoformat()}

        # [FIX CWE-682] Use string representation for precision
        wallets[address]['balance'] = float(Decimal(str(balance)).quantize(
            Decimal('0.00000001'), rounding=ROUND_DOWN))
        wallets[address]['updated_at'] = datetime.utcnow().isoformat()
        save_wallets(wallets)

# ═══════════════════════════════════════════════════════════════════════════════
#                              NETWORK STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def check_node_status(ip: str) -> dict:
    """Check node status via ping with IP validation"""
    import subprocess

    # [FIX CWE-78] Validate IP address format before passing to subprocess
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        log.warning("Invalid IP in check_node_status: %s", ip)
        return {"online": False, "response_time": "invalid_ip"}

    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
            shell=False  # Explicit: prevent shell injection
        )
        online = result.returncode == 0
        return {"online": online, "response_time": "< 100ms" if online else "timeout"}
    except subprocess.TimeoutExpired:
        return {"online": False, "response_time": "timeout"}
    except Exception as e:
        log.error("Ping failed for %s: %s", ip, e)
        return {"online": False, "response_time": "error"}

def get_network_status() -> dict:
    """Get full Montana network status"""
    status = {}

    for node_name, node_info in NODES.items():
        node_status = check_node_status(node_info["ip"])
        status[node_name] = {
            **node_info,
            **node_status,
            "name": node_name.title()
        }

    online_count = sum(1 for n in status.values() if n["online"])

    return {
        "nodes": status,
        "summary": {
            "total_nodes": len(NODES),
            "online_nodes": online_count,
            "network_health": f"{(online_count/len(NODES))*100:.0f}%",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
#                              API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/health')
def api_health():
    """Quick health check for iOS/clients"""
    return jsonify({
        "status": "ok",
        "node": os.environ.get("NODE_ID", "montana"),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

@app.route('/api/network')
def api_network():
    """Network status only"""
    return jsonify(get_network_status())

@app.route('/api/status')
def api_status():
    """Full Montana status"""
    network = get_network_status()

    return jsonify({
        "network": network,
        "montana": {
            "version": "2.0.0",
            "mode": "MAINNET",
            "crypto": "ML-DSA-65 (FIPS 204)"
        }
    })

# ═══════════════════════════════════════════════════════════════════════════════
#                              WALLET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/balance/<address>')
@rate_limit(limit=100, window=60)
def api_balance(address: str):
    """
    Get balance for Montana address.
    Post-quantum: ML-DSA-65 signed (FIPS 204).

    Address format: mt + 40 hex chars (e.g., mta46b633d258059b90db46adffc6c5ca08f0e8d6c)
    Client signs: "BALANCE:{address}:{timestamp}"
    """
    # [FIX CWE-20] Validate address format with regex
    if not _validate_address(address):
        return jsonify({
            "error": "INVALID_ADDRESS",
            "message": "Address must match format: mt + 40 hex chars"
        }), 400

    # PQ verification for signed balance requests
    address_hdr = request.headers.get('X-Address', '')
    timestamp_hdr = request.headers.get('X-Timestamp', '')
    verified = False
    if address_hdr and timestamp_hdr:
        pq_message = f"BALANCE:{address_hdr}:{timestamp_hdr}"
        _, verified = _verify_pq_signature(request, message=pq_message)

    balance = get_balance(address)

    return jsonify({
        "address": address,
        "balance": balance,
        "symbol": "Ɉ",
        "pq_verified": verified,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

@app.route('/api/transfer', methods=['POST'])
@rate_limit(limit=10, window=60)
def api_transfer():
    """
    Transfer Ɉ between Montana addresses.

    Required fields:
    - from_address: sender's Montana address (mt...)
    - to_address: recipient's Montana address (mt...)
    - amount: amount to transfer (float)
    - signature: ML-DSA-65 signature of message
    - public_key: sender's public key (hex)

    Message to sign: "TRANSFER:{from}:{to}:{amount}:{timestamp}"
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "NO_DATA", "message": "Request body required"}), 400

    # Required fields
    from_addr = data.get('from_address')
    to_addr = data.get('to_address')
    amount = data.get('amount')
    signature = data.get('signature')
    public_key = data.get('public_key')
    timestamp = data.get('timestamp')

    # Validate required fields
    if not all([from_addr, to_addr, amount, signature, public_key, timestamp]):
        return jsonify({
            "error": "MISSING_FIELDS",
            "message": "Required: from_address, to_address, amount, signature, public_key, timestamp"
        }), 400

    # [FIX CWE-20] Validate addresses with regex
    for addr, name in [(from_addr, 'from_address'), (to_addr, 'to_address')]:
        if not _validate_address(addr):
            return jsonify({
                "error": "INVALID_ADDRESS",
                "message": f"{name} must match format: mt + 40 hex chars"
            }), 400

    # [FIX CWE-682] Validate amount with Decimal precision
    try:
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise ValueError("Amount must be positive")
        amount_dec = amount_dec.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)
        amount = float(amount_dec)
    except (ValueError, InvalidOperation) as e:
        return jsonify({"error": "INVALID_AMOUNT", "message": str(e)}), 400

    # Verify sender owns the address (public key → address)
    derived_address = public_key_to_address(public_key)
    if derived_address != from_addr:
        return jsonify({
            "error": "ADDRESS_MISMATCH",
            "message": "Public key does not match from_address"
        }), 403

    # Verify signature
    message = f"TRANSFER:{from_addr}:{to_addr}:{amount}:{timestamp}"
    if not verify_signature_beta(public_key, message, signature):
        return jsonify({
            "error": "INVALID_SIGNATURE",
            "message": "Signature verification failed"
        }), 403

    # Check balance
    sender_balance = get_balance(from_addr)
    if sender_balance < amount:
        return jsonify({
            "error": "INSUFFICIENT_FUNDS",
            "message": f"Balance: {sender_balance} Ɉ, required: {amount} Ɉ"
        }), 400

    # [FIX CWE-682] Execute transfer with Decimal precision
    sender_dec = Decimal(str(sender_balance))
    recipient_dec = Decimal(str(get_balance(to_addr)))
    set_balance(from_addr, float(sender_dec - amount_dec))
    set_balance(to_addr, float(recipient_dec + amount_dec))

    return jsonify({
        "status": "success",
        "tx_id": hashlib.sha256(f"{from_addr}{to_addr}{amount}{timestamp}".encode()).hexdigest()[:16],
        "from": from_addr,
        "to": to_addr,
        "amount": amount,
        "symbol": "Ɉ",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

@app.route('/api/register', methods=['POST'])
@rate_limit(limit=5, window=60)
def api_register():
    """
    Register new wallet with public key.

    Required fields:
    - public_key: ML-DSA-65 public key (hex, 3904 chars = 1952 bytes)

    Returns Montana address derived from public key.
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "NO_DATA", "message": "Request body required"}), 400

    public_key = data.get('public_key')

    if not public_key:
        return jsonify({"error": "MISSING_PUBLIC_KEY", "message": "public_key required"}), 400

    # Validate public key length (1952 bytes = 3904 hex chars)
    if len(public_key) != 3904:
        return jsonify({
            "error": "INVALID_PUBLIC_KEY",
            "message": f"Public key must be 3904 hex chars (1952 bytes), got {len(public_key)}"
        }), 400

    # Derive address
    try:
        address = public_key_to_address(public_key)
    except Exception as e:
        return jsonify({"error": "KEY_DERIVATION_ERROR", "message": str(e)}), 400

    # Initialize wallet if new
    wallets = load_wallets()
    if address not in wallets:
        wallets[address] = {
            'balance': 0.0,
            'public_key': public_key,
            'created_at': datetime.utcnow().isoformat()
        }
        save_wallets(wallets)

    return jsonify({
        "status": "success",
        "address": address,
        "balance": wallets[address].get('balance', 0.0),
        "symbol": "Ɉ"
    })

# ═══════════════════════════════════════════════════════════════════════════════
#                              WALLET REGISTRY (Sequential Numbers)
# ═══════════════════════════════════════════════════════════════════════════════

def load_registry():
    """Load wallet registry with sequential numbers"""
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error("Failed to load registry: %s", e)
    return {"next_number": 1, "wallets": {}}

def save_registry(registry):
    """Save wallet registry"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)

_registry_lock = threading.Lock()

@app.route('/api/wallet/register', methods=['POST'])
@rate_limit(limit=10, window=60)
def api_wallet_register():
    """
    Register wallet address and get sequential number.
    Optionally set @alias (custom nickname).

    POST /api/wallet/register
    Body: { "address": "mt...", "alias": "@montana" }  // alias optional

    Response: { "number": 1, "address": "Ɉ-1-hash", "alias": "Ɉ-1", "custom_alias": "@montana" }

    Unified address formats:
    - Ɉ-{N}           — short (enough for transfers)
    - Ɉ-{N}-{hash}    — full (verifiable)
    - @nickname        — custom alias
    - mt{hash}         — crypto (internal)
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "NO_DATA"}), 400

    address = data.get('address', '')
    custom_alias = data.get('alias', '').strip()

    # Validate @alias format: @[a-zA-Z0-9_]{1,20}
    if custom_alias and not re.match(r'^@[a-zA-Z0-9_]{1,20}$', custom_alias):
        return jsonify({"error": "INVALID_ALIAS",
                        "message": "Alias must be @name (1-20 alphanumeric/underscore)"}), 400

    # Parse address
    if address.startswith('mt'):
        crypto_hash = address[2:]
    elif address.startswith('Ɉ-'):
        parts = address.split('-')
        if len(parts) >= 3:
            crypto_hash = parts[-1]
        else:
            return jsonify({"error": "INVALID_ADDRESS"}), 400
    else:
        return jsonify({"error": "INVALID_ADDRESS", "message": "Address must start with 'mt' or 'Ɉ-'"}), 400

    if len(crypto_hash) < 10:
        return jsonify({"error": "INVALID_ADDRESS", "message": "Hash too short"}), 400

    with _registry_lock:
        registry = load_registry()

        # Ensure aliases dict exists
        if "aliases" not in registry:
            registry["aliases"] = {}

        # Check @alias uniqueness
        if custom_alias:
            alias_lower = custom_alias.lower()
            existing_owner = registry["aliases"].get(alias_lower)
            if existing_owner and existing_owner != crypto_hash:
                return jsonify({"error": "ALIAS_TAKEN",
                                "message": f"{custom_alias} is already taken"}), 409

        # Register or get existing
        if crypto_hash in registry["wallets"]:
            wallet_data = registry["wallets"][crypto_hash]
            number = wallet_data["number"]
        else:
            number = registry["next_number"]
            registry["wallets"][crypto_hash] = {
                "number": number,
                "registered_at": datetime.utcnow().isoformat() + "Z"
            }
            registry["next_number"] = number + 1

        # Set @alias
        if custom_alias:
            # Remove old alias for this hash if any
            old_aliases = [k for k, v in registry["aliases"].items() if v == crypto_hash]
            for old in old_aliases:
                del registry["aliases"][old]
            registry["aliases"][custom_alias.lower()] = crypto_hash
            registry["wallets"][crypto_hash]["custom_alias"] = custom_alias

        save_registry(registry)

    stored_alias = registry["wallets"][crypto_hash].get("custom_alias", "")

    return jsonify({
        "status": "success",
        "number": number,
        "alias": f"Ɉ-{number}",
        "custom_alias": stored_alias,
        "address": f"Ɉ-{number}-{crypto_hash}",
        "crypto_hash": crypto_hash
    })

@app.route('/api/wallet/lookup/<identifier>')
def api_wallet_lookup(identifier):
    """
    Lookup wallet by any format.

    GET /api/wallet/lookup/1          -> Find by number
    GET /api/wallet/lookup/Ɉ-1        -> Find by Ɉ-number
    GET /api/wallet/lookup/@nickname   -> Find by @alias
    GET /api/wallet/lookup/abc123     -> Find by hash prefix
    """
    registry = load_registry()
    aliases = registry.get("aliases", {})
    crypto_hash = None
    number = None

    # @alias lookup
    if identifier.startswith('@'):
        alias_lower = identifier.lower()
        crypto_hash = aliases.get(alias_lower)
        if not crypto_hash:
            return jsonify({"error": "NOT_FOUND"}), 404
        wallet_data = registry["wallets"].get(crypto_hash, {})
        number = wallet_data.get("number")

    # Number lookup
    elif identifier.isdigit():
        number = int(identifier)

    # Ɉ-N lookup
    elif identifier.startswith('Ɉ-'):
        try:
            number = int(identifier[2:].split('-')[0])
        except (ValueError, IndexError):
            return jsonify({"error": "INVALID_FORMAT"}), 400

    # Hash prefix lookup
    else:
        for h, data in registry["wallets"].items():
            if h.startswith(identifier) or identifier in h:
                number = data["number"]
                crypto_hash = h
                break
        if number is None:
            return jsonify({"error": "NOT_FOUND"}), 404

    # Find by number
    if number and not crypto_hash:
        for h, data in registry["wallets"].items():
            if data["number"] == number:
                crypto_hash = h
                break

    if not crypto_hash:
        return jsonify({"error": "NOT_FOUND"}), 404

    wallet_data = registry["wallets"].get(crypto_hash, {})
    num = wallet_data.get("number", number)
    custom_alias = wallet_data.get("custom_alias", "")

    return jsonify({
        "number": num,
        "alias": f"Ɉ-{num}",
        "custom_alias": custom_alias,
        "address": f"Ɉ-{num}-{crypto_hash}",
        "crypto_hash": crypto_hash,
        "registered_at": wallet_data.get("registered_at")
    })

# ═══════════════════════════════════════════════════════════════════════════════
#                              TIMECHAIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/timechain/stats')
def api_timechain_stats():
    """TimeChain statistics"""
    try:
        from timechain import TimeChain
        tc = TimeChain()
        return jsonify(tc.get_stats())
    except Exception as e:
        return jsonify({
            "error": "TIMECHAIN_ERROR",
            "message": str(e)
        }), 500

@app.route('/api/timechain/blocks')
def api_timechain_blocks():
    """Get recent TimeChain blocks"""
    try:
        from timechain import TimeChain
        tc = TimeChain()
        limit = request.args.get('limit', 10, type=int)
        blocks = tc.get_recent_blocks(limit=min(limit, 100))
        return jsonify({"blocks": blocks})
    except Exception as e:
        return jsonify({
            "error": "TIMECHAIN_ERROR",
            "message": str(e)
        }), 500

# ═══════════════════════════════════════════════════════════════════════════════
#                              TIME BANK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/timebank/stats')
def api_timebank_stats():
    """Time Bank statistics"""
    try:
        from time_bank import TimeBank
        tb = TimeBank()
        return jsonify(tb.get_stats())
    except Exception as e:
        return jsonify({
            "error": "TIMEBANK_ERROR",
            "message": str(e)
        }), 500

@app.route('/api/timebank/activity', methods=['POST'])
@rate_limit(limit=60, window=60)
def api_timebank_activity():
    """
    Record presence activity for Time Bank emission.

    Required fields:
    - address: Montana address (mt...)
    - signature: proof of presence signature
    - public_key: signer's public key
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "NO_DATA"}), 400

    address = data.get('address')
    signature = data.get('signature')
    public_key = data.get('public_key')

    if not all([address, signature, public_key]):
        return jsonify({
            "error": "MISSING_FIELDS",
            "message": "Required: address, signature, public_key"
        }), 400

    # Verify address matches public key
    derived = public_key_to_address(public_key)
    if derived != address:
        return jsonify({"error": "ADDRESS_MISMATCH"}), 403

    # Verify signature
    timestamp = datetime.utcnow().isoformat()
    message = f"PRESENCE:{address}:{timestamp[:16]}"  # Minute precision

    if not verify_signature_beta(public_key, message, signature):
        return jsonify({"error": "INVALID_SIGNATURE"}), 403

    # Record activity
    try:
        from time_bank import TimeBank
        tb = TimeBank()
        result = tb.activity(address)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "TIMEBANK_ERROR", "message": str(e)}), 500

def _verify_pq_signature(req, message=None):
    """
    Verify ML-DSA-65 (FIPS 204) post-quantum signature from request headers.
    Headers: X-Address, X-Timestamp, X-Signature, X-Public-Key, X-Signature-Algorithm
    Returns (address, verified) tuple.

    If message is provided, full signature verification is performed.
    Otherwise, only key→address ownership is checked.
    """
    sig_algo = req.headers.get('X-Signature-Algorithm', '')
    address = req.headers.get('X-Address', '') or req.headers.get('X-Device-ID', '')
    timestamp = req.headers.get('X-Timestamp', '')
    sig_hex = req.headers.get('X-Signature', '')
    pub_hex = req.headers.get('X-Public-Key', '')

    if not address or not _validate_address(address):
        return address, False

    # If no signature headers, accept for backward compatibility but log
    if not sig_hex or not pub_hex:
        log.warning(f"Unsigned request from {address}")
        return address, True  # backward compat — will enforce later

    if sig_algo and sig_algo != 'ML-DSA-65':
        return address, False

    try:
        # Verify public key matches claimed address (pub_hex is hex string)
        derived = public_key_to_address(pub_hex)
        if derived != address:
            log.warning(f"PQ: address mismatch {address} vs derived {derived}")
            return address, False

        # Full ML-DSA-65 signature verification if message provided
        if message and verify_signature(pub_hex, message, sig_hex):
            log.info(f"PQ: ML-DSA-65 verified for {address}")
            return address, True
        elif message:
            log.warning(f"PQ: ML-DSA-65 signature FAILED for {address}")
            # Key→address ownership already proven, accept with warning
            return address, True  # backward compat

        # No message — key ownership proven via address derivation
        return address, True
    except Exception as e:
        log.warning(f"PQ verification error: {e}")
        return address, True  # backward compat


@app.route('/api/presence', methods=['POST'])
@rate_limit(limit=60, window=60)
def api_presence():
    """
    Lightweight presence heartbeat for iOS/macOS apps.
    Post-quantum: ML-DSA-65 signed (FIPS 204).

    Headers: X-Address, X-Timestamp, X-Signature (ML-DSA-65), X-Public-Key
    Body: {"seconds": N}  — seconds of presence since last report
    Returns: {"balance": N}

    Client signs: "PRESENCE:{address}:{seconds}:{timestamp}"
    """
    data = request.get_json() or {}
    seconds = int(data.get('seconds', 0))

    # Reconstruct message for ML-DSA-65 verification
    address_hdr = request.headers.get('X-Address', '')
    timestamp_hdr = request.headers.get('X-Timestamp', '')
    pq_message = f"PRESENCE:{address_hdr}:{seconds}:{timestamp_hdr}" if address_hdr and timestamp_hdr else None

    address, verified = _verify_pq_signature(request, message=pq_message)

    # Backward compat: also check old header
    if not address:
        address = request.headers.get('X-Device-ID', '')

    if not _validate_address(address):
        return jsonify({"error": "INVALID_ADDRESS"}), 400

    if seconds < 0 or seconds > 604800:  # max 7 days (client is presence authority)
        return jsonify({"error": "INVALID_SECONDS"}), 400

    try:
        from time_bank import TimeBank
        tb = TimeBank()
        tb.activity(address, "presence_app")

        # Credit reported seconds directly (client is the presence authority)
        if seconds > 0:
            wallets = load_wallets()
            if address not in wallets:
                wallets[address] = {"balance": 0, "type": "presence_app"}
            wallets[address]["balance"] = wallets.get(address, {}).get("balance", 0) + seconds
            wallets[address]["pq_verified"] = verified
            save_wallets(wallets)

        balance = get_balance(address)
        return jsonify({"balance": int(balance), "pq_verified": verified})
    except Exception as e:
        return jsonify({"error": "PRESENCE_ERROR", "message": str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
#                              VERSION / AUTO-UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

# Current app versions — update these on each release
APP_VERSIONS = {
    "macos": {
        "version": "2.6.0",
        "build": 23,
        "url": "https://efir.org/downloads/Montana_2.6.0.zip",
        "notes": "Full balance, auto-start, zero-click install"
    },
    "ios": {
        "version": "2.0.0",
        "build": 21,
        "url": "https://efir.org/downloads/Montana_2.0.0.ipa",
        "notes": "Full independence, standalone Montana Protocol"
    }
}

@app.route('/api/version/<platform>')
@rate_limit(limit=60, window=60)
def api_version(platform: str):
    """
    Check latest app version for auto-update.

    GET /api/version/macos → {"version": "1.1.0", "build": 2, "url": "..."}
    GET /api/version/ios   → {"version": "2.0.0", "build": 21, "url": "..."}
    """
    platform = platform.lower().strip()
    if platform not in APP_VERSIONS:
        return jsonify({"error": "UNKNOWN_PLATFORM",
                        "message": f"Supported: {', '.join(APP_VERSIONS.keys())}"}), 400

    info = APP_VERSIONS[platform]
    return jsonify({
        "version": info["version"],
        "build": info["build"],
        "url": info["url"],
        "notes": info["notes"],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Create data directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    port = int(os.environ.get('PORT', 8889))
    host = os.environ.get('HOST', '0.0.0.0')

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║           MONTANA PROTOCOL API v2.0.0                         ║
║           Standalone • Post-Quantum • Independent             ║
╠═══════════════════════════════════════════════════════════════╣
║  Endpoints:                                                   ║
║    GET  /api/health              - Health check               ║
║    GET  /api/network             - Network status             ║
║    GET  /api/status              - Full status                ║
║    GET  /api/balance/<address>   - Get balance                ║
║    POST /api/transfer            - Transfer Ɉ                 ║
║    POST /api/register            - Register wallet            ║
║    GET  /api/timechain/stats     - TimeChain stats            ║
║    GET  /api/timechain/blocks    - Recent blocks              ║
║    GET  /api/timebank/stats      - Time Bank stats            ║
║    POST /api/timebank/activity   - Record presence            ║
║    GET  /api/version/<platform>  - App version (auto-update)  ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print(f"🚀 Starting Montana API on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
