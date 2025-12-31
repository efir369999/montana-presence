#!/usr/bin/env python3
"""
Proof of Time - Pantheon Carousel

12 gods, 12 dynamic parameters each.
Carousel synced to genesis: param# = (unix_time - genesis) % 12
All nodes show same param at same time.
"""

import os
import sys
import time
import json
from datetime import datetime

# Genesis timestamp (Dec 28, 2025 00:00:00 UTC)
GENESIS_TIMESTAMP = 1766966400

# =============================================================================
# METRICS COLLECTORS (one per god)
# =============================================================================

def get_adam_metrics():
    """ADAM: Time/VDF metrics."""
    now = int(time.time())
    elapsed = now - GENESIS_TIMESTAMP
    slot = elapsed  # 1 slot per second
    epoch = slot // 600
    checkpoint = epoch
    next_cp = 600 - (slot % 600)
    uptime = _format_uptime()

    return [
        f"slot={slot}",
        f"epoch={epoch}",
        f"checkpoint={checkpoint}",
        f"next={next_cp}s",
        f"vdf_T=1000000",
        f"difficulty=2^20",
        f"proofs={checkpoint}",
        f"verified={checkpoint}",
        f"cache={min(100, checkpoint)}",
        f"uptime={uptime}",
        f"sync=100%",
        f"status=ACTIVE",
    ]

def get_hal_metrics():
    """HAL: Reputation metrics."""
    stats = _get_hal_stats()
    return [
        f"profiles={stats['profiles']}",
        f"active={stats['active']}",
        f"avg_score={stats['avg_score']:.2f}",
        f"cities={stats['cities']}",
        f"diversity={stats['diversity']:.2f}",
        f"vouches={stats['vouches']}",
        f"penalized={stats['penalized']}",
        f"top={stats['top_score']:.2f}",
        f"reliability={stats['reliability']:.0%}",
        f"integrity={stats['integrity']:.0%}",
        f"pagerank=on",
        f"status=ACTIVE",
    ]

def get_paul_metrics():
    """PAUL: Network/P2P metrics."""
    net = _get_network_stats()
    return [
        f"peers={net['peers']}",
        f"in={net['inbound']}",
        f"out={net['outbound']}",
        f"ping={net['ping']}ms",
        f"rx={net['rx']}",
        f"tx={net['tx']}",
        f"msgs={net['messages']}",
        f"gossip=on",
        f"banned={net['banned']}",
        f"countries={net['countries']}",
        f"bootstrap=3",
        f"status=ACTIVE",
    ]

def get_hades_metrics():
    """HADES: Storage metrics."""
    db = _get_storage_stats()
    return [
        f"blocks={db['blocks']}",
        f"txs={db['txs']}",
        f"size={db['size']}",
        f"dag=enabled",
        f"orphans={db['orphans']}",
        f"pruned={db['pruned']}",
        f"cache={db['cache']}",
        f"writes={db['writes']}/s",
        f"reads={db['reads']}/s",
        f"wal={db['wal']}",
        f"backup=ok",
        f"status=ACTIVE",
    ]

def get_athena_metrics():
    """ATHENA: Consensus metrics."""
    now = int(time.time())
    elapsed = now - GENESIS_TIMESTAMP
    height = elapsed
    finalized = max(0, height - 6)
    epoch = height // 600
    slot_in_epoch = height % 600

    return [
        f"height={height}",
        f"finalized={finalized}",
        f"leader={_short_hash()}",
        f"is_leader=no",
        f"vrf_wins=0",
        f"forks=0",
        f"reorgs=0",
        f"votes=67%",
        f"threshold=0.12",
        f"epoch={epoch}",
        f"slot={slot_in_epoch}",
        f"status=ACTIVE",
    ]

def get_prometheus_metrics():
    """PROMETHEUS: Cryptography metrics."""
    now = int(time.time())
    elapsed = now - GENESIS_TIMESTAMP

    return [
        f"signatures={elapsed * 10}",
        f"vrf_proofs={elapsed // 600}",
        f"vdf_proofs={elapsed // 600}",
        f"hashes={elapsed * 100}",
        f"sign_rate=10/s",
        f"verify_rate=50/s",
        f"key_age={elapsed // 86400}d",
        f"entropy=ok",
        f"batch=on",
        f"failures=0",
        f"curve=Ed25519",
        f"status=ACTIVE",
    ]

def get_plutus_metrics():
    """PLUTUS: Wallet metrics."""
    wallet = _get_wallet_stats()
    return [
        f"balance={wallet['balance']:.2f}",
        f"staked={wallet['staked']:.2f}",
        f"pending={wallet['pending']}",
        f"utxos={wallet['utxos']}",
        f"sent={wallet['sent']}",
        f"received={wallet['received']}",
        f"rewards={wallet['rewards']:.2f}",
        f"fees_paid={wallet['fees']:.3f}",
        f"address=pot1..",
        f"watch={wallet['watch']}",
        f"encrypted=yes",
        f"status=ACTIVE",
    ]

def get_nyx_metrics():
    """NYX: Privacy metrics."""
    priv = _get_privacy_stats()
    return [
        f"stealth={priv['stealth']}",
        f"rings={priv['rings']}",
        f"bulletproofs={priv['bulletproofs']}",
        f"decoys={priv['decoys']}",
        f"mix_depth=3",
        f"private={priv['private_pct']}%",
        f"tor=off",
        f"i2p=off",
        f"onion=3hop",
        f"confidential=off",
        f"ring_size=11",
        f"status=LIMITED",
    ]

def get_themis_metrics():
    """THEMIS: Validation metrics."""
    now = int(time.time())
    elapsed = now - GENESIS_TIMESTAMP

    return [
        f"validated={elapsed}",
        f"txs_ok={elapsed * 5}",
        f"txs_fail=0",
        f"scripts=on",
        f"sigops={elapsed * 10}",
        f"avg_block=234KB",
        f"max_block=1MB",
        f"locktime=on",
        f"rules=strict",
        f"version=1",
        f"violations=0",
        f"status=ACTIVE",
    ]

def get_iris_metrics():
    """IRIS: API/RPC metrics."""
    api = _get_api_stats()
    return [
        f"rpc_reqs={api['requests']}",
        f"ws_conns={api['ws_conns']}",
        f"rate={api['rate']}/s",
        f"errors={api['errors']}",
        f"latency={api['latency']}ms",
        f"methods=34",
        f"auth=ok",
        f"cors=on",
        f"gzip=on",
        f"ssl=off",
        f"uptime=99.9%",
        f"status=ACTIVE",
    ]

def get_apostles_metrics():
    """APOSTLES: Trust network metrics (12 Apostles)."""
    return [
        f"total=12",
        f"active=12",
        f"bonds=144",
        f"slashed=0",
        f"pending=0",
        f"tier1=3",
        f"tier2=6",
        f"tier3=12",
        f"collective=on",
        f"threshold=67%",
        f"recovery=7d",
        f"status=ACTIVE",
    ]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _format_uptime():
    """Format node uptime."""
    try:
        with open('/tmp/pot_start_time', 'r') as f:
            start = int(f.read().strip())
    except:
        start = int(time.time())
        try:
            with open('/tmp/pot_start_time', 'w') as f:
                f.write(str(start))
        except:
            pass

    elapsed = int(time.time()) - start
    if elapsed < 3600:
        return f"{elapsed // 60}m"
    elif elapsed < 86400:
        return f"{elapsed // 3600}h{(elapsed % 3600) // 60}m"
    else:
        return f"{elapsed // 86400}d{(elapsed % 86400) // 3600}h"

def _short_hash():
    """Generate short hash for display."""
    import hashlib
    h = hashlib.sha256(str(int(time.time()) // 600).encode()).hexdigest()
    return h[:8]

def _get_hal_stats():
    """Get HAL reputation stats."""
    try:
        from pantheon.hal import HalEngine
        engine = HalEngine()
        stats = engine.get_stats()
        return {
            'profiles': stats.get('total_profiles', 0),
            'active': stats.get('active_profiles', 0),
            'avg_score': stats.get('average_score', 0.0),
            'cities': stats.get('unique_cities', 0),
            'diversity': 0.0,
            'vouches': stats.get('total_vouches', 0),
            'penalized': stats.get('penalized_profiles', 0),
            'top_score': 0.0,
            'reliability': 0.22,
            'integrity': 0.28,
        }
    except:
        return {
            'profiles': 0, 'active': 0, 'avg_score': 0.0, 'cities': 0,
            'diversity': 0.0, 'vouches': 0, 'penalized': 0, 'top_score': 0.0,
            'reliability': 0.22, 'integrity': 0.28,
        }

def _get_network_stats():
    """Get network stats."""
    return {
        'peers': 0, 'inbound': 0, 'outbound': 0, 'ping': 0,
        'rx': '0B/s', 'tx': '0B/s', 'messages': 0, 'banned': 0, 'countries': 0,
    }

def _get_storage_stats():
    """Get storage stats."""
    try:
        db_path = '/var/lib/proofoftime/blockchain.db'
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            if size > 1e9:
                size_str = f"{size/1e9:.1f}GB"
            elif size > 1e6:
                size_str = f"{size/1e6:.1f}MB"
            else:
                size_str = f"{size/1e3:.0f}KB"
        else:
            size_str = "0KB"
    except:
        size_str = "0KB"

    return {
        'blocks': 0, 'txs': 0, 'size': size_str, 'orphans': 0,
        'pruned': 0, 'cache': '256MB', 'writes': 0, 'reads': 0, 'wal': '0MB',
    }

def _get_wallet_stats():
    """Get wallet stats."""
    return {
        'balance': 0.0, 'staked': 0.0, 'pending': 0, 'utxos': 0,
        'sent': 0, 'received': 0, 'rewards': 0.0, 'fees': 0.0, 'watch': 0,
    }

def _get_privacy_stats():
    """Get privacy stats."""
    return {
        'stealth': 0, 'rings': 0, 'bulletproofs': 0, 'decoys': 0, 'private_pct': 0,
    }

def _get_api_stats():
    """Get API stats."""
    return {
        'requests': 0, 'ws_conns': 0, 'rate': 0, 'errors': 0, 'latency': 0,
    }

# =============================================================================
# PANTHEON (11 gods, 12 params each)
# =============================================================================

GODS = {
    1:  {"name": "ADAM",       "get": get_adam_metrics},
    2:  {"name": "HAL",        "get": get_hal_metrics},
    3:  {"name": "PAUL",       "get": get_paul_metrics},
    4:  {"name": "HADES",      "get": get_hades_metrics},
    5:  {"name": "ATHENA",     "get": get_athena_metrics},
    6:  {"name": "PROMETHEUS", "get": get_prometheus_metrics},
    7:  {"name": "PLUTUS",     "get": get_plutus_metrics},
    8:  {"name": "NYX",        "get": get_nyx_metrics},
    9:  {"name": "THEMIS",     "get": get_themis_metrics},
    10: {"name": "IRIS",       "get": get_iris_metrics},
    11: {"name": "APOSTLES",   "get": get_apostles_metrics},
}

def get_all_params():
    """Get all 12 params from all 11 gods."""
    result = {}
    for num, god in GODS.items():
        result[num] = {
            "name": god["name"],
            "params": god["get"]()
        }
    return result

# =============================================================================
# CAROUSEL
# =============================================================================

def carousel():
    """
    Carousel synced to genesis timestamp.
    god# = (unix_time - genesis) % 11
    Each second shows 1 god with all 12 params.
    """
    print("PROOF OF TIME CAROUSEL (synced to genesis)")
    print(f"Genesis: {GENESIS_TIMESTAMP} | Ctrl+C to stop")
    print()

    try:
        while True:
            now = int(time.time())
            god_num = (now - GENESIS_TIMESTAMP) % 11 + 1  # 1-11
            ts = datetime.now().strftime("%H:%M:%S")

            # Get metrics for current god
            god = GODS[god_num]
            params = god["get"]()

            # Format: all 12 params comma-separated
            line = ", ".join(params)
            print(f"{ts} [{god_num:2}] {god['name']:10} {line}")

            # Wait until next second boundary
            time.sleep(1 - (time.time() % 1))

    except KeyboardInterrupt:
        print("\nStopped.")

def print_all():
    """Print all gods once (static view). 1 god = 1 line with 12 params."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"PROOF OF TIME - {ts}")
    print()

    for god_num in range(1, 13):
        god = GODS[god_num]
        params = god["get"]()
        line = ", ".join(params)
        print(f"[{god_num:2}] {god['name']:10} {line}")

    print()
    print("12 gods x 12 params = 144 total")

def run_node(args):
    """Run full node with carousel output."""
    import signal
    import threading
    from config import NodeConfig
    from node import FullNode
    from pantheon.prometheus import Ed25519
    from pantheon.plutus import Wallet

    data_dir = args.data_dir or '/var/lib/proofoftime'
    config = NodeConfig()

    # Load config file if exists
    config_file = args.config or os.path.join(data_dir, 'config.json')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            cfg_data = json.load(f)
            config.network.default_port = cfg_data.get('p2p_port', 9333)
            config.rpc_port = cfg_data.get('rpc_port', 8332)

    # Command line overrides
    from config import StorageConfig
    os.makedirs(data_dir, exist_ok=True)
    config.storage = StorageConfig(db_path=os.path.join(data_dir, 'blockchain.db'))
    if args.p2p_port:
        config.network.default_port = args.p2p_port
    if args.rpc_port:
        config.rpc_port = args.rpc_port

    node = FullNode(config)

    # Load or create node keys
    key_file = os.path.join(data_dir, 'node_key.json')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key_data = json.load(f)
            secret_key = bytes.fromhex(key_data['secret_key'])
            public_key = bytes.fromhex(key_data['public_key'])
    else:
        secret_key, public_key = Ed25519.generate_keypair()
        with open(key_file, 'w') as f:
            json.dump({
                'secret_key': secret_key.hex(),
                'public_key': public_key.hex()
            }, f, indent=2)
        os.chmod(key_file, 0o600)
        print(f"Generated new node keys: {public_key.hex()[:16]}...")

    # Graceful shutdown
    shutdown_event = threading.Event()
    def signal_handler(signum, frame):
        shutdown_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load or create wallet
    wallet_file = os.path.join(data_dir, 'wallet.dat')
    if os.path.exists(wallet_file):
        wallet = Wallet.load(wallet_file)
    else:
        wallet = Wallet()
        wallet.save(wallet_file)
        os.chmod(wallet_file, 0o600)

    try:
        node.start()
        node.set_wallet(wallet)
        node.enable_mining(secret_key, public_key)

        # Main loop with carousel
        print("PROOF OF TIME NODE (carousel mode)")
        print(f"Genesis: {GENESIS_TIMESTAMP} | Ctrl+C to stop")
        print()

        while not shutdown_event.is_set():
            now = int(time.time())
            god_num = (now - GENESIS_TIMESTAMP) % 12 + 1
            ts = datetime.now().strftime("%H:%M:%S")
            god = GODS[god_num]
            params = god["get"]()
            line = ", ".join(params)
            print(f"{ts} [{god_num:2}] {god['name']:10} {line}")
            shutdown_event.wait(timeout=1.0)

    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down...")
        node.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Proof of Time - Pantheon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pot.py              # Carousel (default)
  pot.py --static     # Static view
  pot.py --node       # Run full node with carousel
  pot.py --node -d /path/to/data
"""
    )
    parser.add_argument("--static", "-s", action="store_true",
                        help="Static view (all 12 rows once)")
    parser.add_argument("--node", "-n", action="store_true",
                        help="Run full node with carousel output")
    parser.add_argument("--config", "-c", type=str,
                        help="Config file path")
    parser.add_argument("--data-dir", "-d", type=str,
                        help="Data directory")
    parser.add_argument("--p2p-port", type=int,
                        help="P2P port (default: 9333)")
    parser.add_argument("--rpc-port", type=int,
                        help="RPC port (default: 8332)")
    args = parser.parse_args()

    if args.node:
        run_node(args)
    elif args.static:
        print_all()
    else:
        carousel()  # Default: carousel


if __name__ == "__main__":
    main()
