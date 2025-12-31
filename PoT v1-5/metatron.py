#!/usr/bin/env python3
"""
METATRON - The Angel Who Governs the Pantheon

One-click deploy with real-time dashboard showing all 12 gods.
Full node operation with mining and wallet integration.

Usage:
    python metatron.py              # Status check
    python metatron.py --deploy     # Deploy + mine + dashboard
    python metatron.py --peer IP    # Connect to peer
"""

import os
import sys
import time
import threading
import argparse
import logging
import signal
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone

# ============================================================================
# CONFIGURATION
# ============================================================================

class GodStatus(Enum):
    """Status of a Pantheon god."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    ERROR = "ERROR"
    STUB = "STUB"


@dataclass
class God:
    """Pantheon god with live metrics."""
    name: str
    symbol: str
    domain: str
    modules: List[str]
    status: GodStatus = GodStatus.OFFLINE
    error: Optional[str] = None
    metrics: Dict = field(default_factory=dict)


# The 13 Gods of Pantheon
PANTHEON = {
    "adam": God(
        name="Adam",
        symbol="⏱",
        domain="Time (Bitcoin Oracle)",
        modules=["pantheon.adam.adam"]
    ),
    "hal": God(
        name="Hal",
        symbol="✋",
        domain="Humanity/Reputation",
        modules=["pantheon.hal.reputation"]
    ),
    "paul": God(
        name="Paul",
        symbol="📡",
        domain="P2P Network",
        modules=["pantheon.paul.network", "pantheon.paul.bootstrap"]
    ),
    "hades": God(
        name="Hades",
        symbol="💾",
        domain="Storage",
        modules=["pantheon.hades.database", "pantheon.hades.dag", "pantheon.hades.dag_storage"]
    ),
    "athena": God(
        name="Athena",
        symbol="⚖",
        domain="Consensus",
        modules=["pantheon.athena.consensus", "pantheon.athena.engine"]
    ),
    "prometheus": God(
        name="Prometheus",
        symbol="🔐",
        domain="Cryptography",
        modules=["pantheon.prometheus.crypto"]
    ),
    "plutus": God(
        name="Plutus",
        symbol="💰",
        domain="Wallet",
        modules=["pantheon.plutus.wallet"]
    ),
    "nyx": God(
        name="Nyx",
        symbol="🌙",
        domain="Privacy",
        modules=["pantheon.nyx.privacy", "pantheon.nyx.tiered_privacy", "pantheon.nyx.ristretto"]
    ),
    "themis": God(
        name="Themis",
        symbol="📜",
        domain="Validation",
        modules=["pantheon.themis.structures"]
    ),
    "iris": God(
        name="Iris",
        symbol="🌈",
        domain="RPC",
        modules=["pantheon.iris.rpc"]
    ),
}


# ============================================================================
# METATRON CORE
# ============================================================================

class Metatron:
    """
    The angel who governs the Pantheon.
    Orchestrates all 12 gods with real-time monitoring.
    """

    def __init__(self, data_dir: str = "/var/lib/proofoftime"):
        self.gods = {k: God(
            name=v.name,
            symbol=v.symbol,
            domain=v.domain,
            modules=v.modules.copy(),
            status=v.status,
            error=v.error,
            metrics={}
        ) for k, v in PANTHEON.items()}
        self.data_dir = data_dir
        self.node = None
        self.wallet = None
        self.running = False
        self._lock = threading.Lock()
        self._shutdown = threading.Event()

        # Metrics
        self.start_time = 0
        self.session_blocks = 0
        self.session_rewards = 0

    def analyze(self) -> Dict[str, GodStatus]:
        """Analyze all gods and return their status."""
        results = {}

        for god_id, god in self.gods.items():
            if not god.modules:
                god.status = GodStatus.STUB
                results[god_id] = GodStatus.STUB
                continue

            try:
                for module in god.modules:
                    __import__(module)
                god.status = GodStatus.OFFLINE  # Importable but not running
                results[god_id] = GodStatus.OFFLINE
            except Exception as e:
                god.status = GodStatus.ERROR
                god.error = str(e)
                results[god_id] = GodStatus.ERROR

        return results

    def deploy(self, peer_address: Optional[str] = None) -> bool:
        """Deploy a full node with all gods active."""
        os.environ.setdefault("POT_NETWORK", "TESTNET")
        os.environ.setdefault("POT_ALLOW_UNSAFE", "1")

        if peer_address:
            os.environ["POT_BOOTSTRAP_PEERS"] = peer_address

        # Analyze gods
        results = self.analyze()
        ready = sum(1 for s in results.values() if s != GodStatus.ERROR)

        if ready < 8:
            print(f"\n  ERROR: Only {ready}/12 gods ready. Cannot deploy.\n")
            return False

        try:
            from node import FullNode, BlockProducer
            from config import NodeConfig, StorageConfig
            from pantheon.plutus import Wallet

            # Configure node
            os.makedirs(self.data_dir, exist_ok=True)
            config = NodeConfig()
            config.storage = StorageConfig(db_path=os.path.join(self.data_dir, 'blockchain.db'))

            # Load or create keys
            key_file = os.path.join(self.data_dir, 'node_key.json')
            if os.path.exists(key_file):
                with open(key_file, 'r') as f:
                    key_data = json.load(f)
                    secret_key = bytes.fromhex(key_data['secret_key'])
                    public_key = bytes.fromhex(key_data['public_key'])
            else:
                from pantheon.prometheus import Ed25519
                secret_key, public_key = Ed25519.generate_keypair()
                with open(key_file, 'w') as f:
                    json.dump({
                        'secret_key': secret_key.hex(),
                        'public_key': public_key.hex()
                    }, f, indent=2)
                os.chmod(key_file, 0o600)

            # Load or create wallet (testnet uses empty password)
            wallet_file = os.path.join(self.data_dir, 'wallet.dat')
            testnet_password = ""  # Empty password for testnet convenience
            if os.path.exists(wallet_file):
                self.wallet = Wallet.load(wallet_file, testnet_password)
            else:
                self.wallet = Wallet()
                self.wallet.save(wallet_file, testnet_password)
                os.chmod(wallet_file, 0o600)

            # Start node
            self.node = FullNode(config)
            self.node.start()
            self.node.set_wallet(self.wallet)
            self.node.enable_mining(secret_key, public_key)

            # Mark gods as online
            for god_id in self.gods:
                if self.gods[god_id].status != GodStatus.STUB:
                    self.gods[god_id].status = GodStatus.ONLINE

            self.running = True
            self.start_time = time.time()
            return True

        except Exception as e:
            print(f"\n  ERROR: {e}\n")
            import traceback
            traceback.print_exc()
            return False

    def stop(self):
        """Stop the node."""
        self._shutdown.set()
        if self.node:
            self.node.stop()
            self.running = False
            for god in self.gods.values():
                if god.status == GodStatus.ONLINE:
                    god.status = GodStatus.OFFLINE

    def update_metrics(self):
        """Update live metrics from all gods."""
        if not self.node:
            return

        try:
            # ADAM - Time/Bitcoin Oracle
            if self.node.chain_tip:
                self.gods["adam"].metrics = {
                    "height": self.node.chain_tip.height,
                    "checkpoint": self.node.chain_tip.height // 600,
                    "next_vdf": 600 - (self.node.chain_tip.height % 600),
                    "timestamp": self.node.chain_tip.timestamp
                }

            if self.node.producer:
                self.gods["adam"].metrics["produced"] = self.node.producer.blocks_produced
                self.session_blocks = self.node.producer.blocks_produced

            # HAL - Humanity/Reputation
            if hasattr(self.node, 'consensus') and self.node.consensus:
                nodes = self.node.consensus.nodes if hasattr(self.node.consensus, 'nodes') else {}
                self.gods["hal"].metrics = {
                    "nodes": len(nodes),
                    "our_uptime": int(time.time() - self.start_time) if self.start_time else 0,
                }

            # PAUL - Network
            if hasattr(self.node, 'network') and self.node.network:
                self.gods["paul"].metrics = {
                    "peers": self.node.network.get_peer_count(),
                    "connected": self.node.network.get_peer_count() > 0,
                }

            # HADES - Storage
            if hasattr(self.node, 'db') and self.node.db:
                self.gods["hades"].metrics = {
                    "blocks": self.node.chain_tip.height + 1 if self.node.chain_tip else 0,
                    "db_path": self.node.db.db_path if hasattr(self.node.db, 'db_path') else "N/A",
                }

            # ATHENA - Consensus
            if hasattr(self.node, 'consensus') and self.node.consensus:
                self.gods["athena"].metrics = {
                    "state": "PRODUCING" if self.node.producer and self.node.producer.running else "IDLE",
                    "sync": self.node.sync_state.name if hasattr(self.node, 'sync_state') else "UNKNOWN",
                }

            # PROMETHEUS - Crypto
            self.gods["prometheus"].metrics = {
                "vdf_bits": 2048,
                "ring_size": 16,
            }

            # PLUTUS - Wallet
            if self.wallet:
                try:
                    bal = self.wallet.get_balance()  # Returns (confirmed, pending)
                    balance = bal[0] if isinstance(bal, tuple) else bal
                except:
                    balance = 0

                from config import get_block_reward
                height = self.node.chain_tip.height if self.node.chain_tip else 0
                reward = get_block_reward(height)
                self.session_rewards = self.session_blocks * reward

                try:
                    addr = self.wallet.get_primary_address()[:16].hex() + "..."
                except:
                    addr = "N/A"

                self.gods["plutus"].metrics = {
                    "balance": balance,
                    "session_earned": self.session_rewards,
                    "reward_per_block": reward,
                    "address": addr
                }

            # NYX - Privacy
            self.gods["nyx"].metrics = {
                "tiers": "T0-T3",
                "stealth": "enabled",
            }

            # THEMIS - Validation
            self.gods["themis"].metrics = {
                "validated": self.node.chain_tip.height if self.node.chain_tip else 0,
            }

            # IRIS - RPC
            self.gods["iris"].metrics = {
                "port": 8332,
                "status": "ready",
            }

        except Exception as e:
            logging.debug(f"Metrics update error: {e}")

    def render_dashboard(self):
        """Render full Pantheon dashboard."""
        self.update_metrics()

        # Colors
        G, Y, R, C, M, B, D, W, N = (
            '\033[92m', '\033[93m', '\033[91m', '\033[96m',
            '\033[95m', '\033[1m', '\033[2m', '\033[97m', '\033[0m'
        )

        def col(text, color):
            return f"{color}{text}{N}" if sys.stdout.isatty() else str(text)

        def fmt_time(secs):
            if secs < 60: return f"{secs}s"
            if secs < 3600: return f"{secs // 60}m {secs % 60}s"
            return f"{secs // 3600}h {(secs % 3600) // 60}m"

        def fmt_amount(secs):
            mins = secs / 60
            if mins >= 1_000_000: return f"{mins / 1_000_000:.2f}M Ɉ"
            if mins >= 1_000: return f"{mins / 1_000:.2f}K Ɉ"
            return f"{mins:.2f} Ɉ"

        # Clear screen
        print("\033[2J\033[H", end="")

        # Header
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        print()
        print(col("  ╔═══════════════════════════════════════════════════════════════╗", G))
        print(col("  ║", G) + col("   M E T A T R O N  -  Pantheon Dashboard                  ", W) + col("║", G))
        print(col("  ║", G) + col(f"   {now}                            ", D) + col("║", G))
        print(col("  ╚═══════════════════════════════════════════════════════════════╝", G))
        print()

        # Adam - Time Layer
        ad = self.gods["adam"].metrics
        height = ad.get("height", 0)
        checkpoint = ad.get("checkpoint", 0)
        next_vdf = ad.get("next_vdf", 600)
        produced = ad.get("produced", 0)

        print(col("  ⏱ ADAM ", M) + col("───────────────────────────────────────────────────", D))
        print(f"    Height: {col(height, W)}  │  Checkpoint: {col(checkpoint, C)}  │  Next VDF: {col(fmt_time(next_vdf), Y)}")
        print(f"    Blocks Produced: {col(produced, G)}")
        print()

        # Hal - Humanity/Reputation
        hl = self.gods["hal"].metrics
        uptime = hl.get("our_uptime", 0)
        nodes = hl.get("nodes", 1)

        print(col("  ✋ HAL ", M) + col("────────────────────────────────────────────────────", D))
        print(f"    Uptime: {col(fmt_time(uptime), W)}  │  Nodes: {col(nodes, C)}")
        print()

        # Paul - Network
        pa = self.gods["paul"].metrics
        peers = pa.get("peers", 0)

        print(col("  📡 PAUL ", M) + col("────────────────────────────────────────────────────", D))
        status = col("●", G) + " Connected" if peers > 0 else col("○", R) + " Solo"
        print(f"    Peers: {col(peers, W)}  │  {status}")
        print()

        # Hades - Storage
        ha = self.gods["hades"].metrics
        blocks = ha.get("blocks", 0)

        print(col("  💾 HADES ", M) + col("───────────────────────────────────────────────────", D))
        print(f"    Blocks Stored: {col(blocks, W)}")
        print()

        # Athena - Consensus
        at = self.gods["athena"].metrics
        state = at.get("state", "IDLE")
        state_col = G if state == "PRODUCING" else Y

        print(col("  ⚖ ATHENA ", M) + col("──────────────────────────────────────────────────", D))
        print(f"    State: {col(state, state_col)}  │  Sync: {at.get('sync', 'N/A')}")
        print()

        # Plutus - Wallet (larger section)
        pl = self.gods["plutus"].metrics
        balance = pl.get("balance", 0)
        session = pl.get("session_earned", 0)
        reward = pl.get("reward_per_block", 3000)
        addr = pl.get("address", "N/A")

        print(col("  💰 PLUTUS ", M) + col("──────────────────────────────────────────────────", D))
        print(f"    Address:  {col(addr, C)}")
        print(f"    Balance:  {col(fmt_amount(balance), W)}")
        print(f"    Session:  {col(fmt_amount(session), G)} ({self.session_blocks} blocks)")
        print(f"    Reward:   {col(fmt_amount(reward), Y)} per block")
        print()

        # Nyx - Privacy
        print(col("  🌙 NYX ", M) + col("─────────────────────────────────────────────────────", D))
        print(f"    Privacy Tiers: T0 (Public) → T3 (Full Ring)")
        print()

        # Bottom status bar
        print(col("  ─────────────────────────────────────────────────────────────────", D))

        # Gods summary
        online = sum(1 for g in self.gods.values() if g.status == GodStatus.ONLINE)
        stubs = sum(1 for g in self.gods.values() if g.status == GodStatus.STUB)

        gods_line = "  "
        for gid, g in self.gods.items():
            if g.status == GodStatus.ONLINE:
                gods_line += col(g.symbol, G) + " "
            elif g.status == GodStatus.STUB:
                gods_line += col(g.symbol, D) + " "
            elif g.status == GodStatus.ERROR:
                gods_line += col(g.symbol, R) + " "
            else:
                gods_line += col(g.symbol, Y) + " "

        print(gods_line + f"  │  {col(f'{online}/{12-stubs} ONLINE', G if online > 8 else Y)}")
        print()
        print(col("  Ctrl+C to stop", D))

    def dashboard_loop(self, refresh: float = 1.0):
        """Run live dashboard with refresh."""
        try:
            while not self._shutdown.is_set():
                self.render_dashboard()
                self._shutdown.wait(timeout=refresh)
        except KeyboardInterrupt:
            pass


# ============================================================================
# CLI
# ============================================================================

def print_banner():
    """Print Metatron banner."""
    G, N = '\033[92m', '\033[0m'
    banner = f"""
{G}    ███╗   ███╗███████╗████████╗ █████╗ ████████╗██████╗  ██████╗ ███╗   ██╗
    ████╗ ████║██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║
    ██╔████╔██║█████╗     ██║   ███████║   ██║   ██████╔╝██║   ██║██╔██╗ ██║
    ██║╚██╔╝██║██╔══╝     ██║   ██╔══██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║
    ██║ ╚═╝ ██║███████╗   ██║   ██║  ██║   ██║   ██║  ██║╚██████╔╝██║ ╚████║
    ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝{N}

                     The Angel Who Governs the Pantheon
                        Time Testnet • One-Click Deploy
    """
    print(banner)


def main():
    parser = argparse.ArgumentParser(
        description="METATRON - One-Click Deploy for Time Testnet"
    )
    parser.add_argument(
        "--deploy", "-d",
        action="store_true",
        help="Deploy testnet node with mining"
    )
    parser.add_argument(
        "--peer", "-p",
        type=str,
        default=None,
        help="Bootstrap peer (ip:port)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="/var/lib/proofoftime",
        help="Data directory"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show Pantheon status"
    )

    args = parser.parse_args()

    # Use local directory if default not writable
    data_dir = args.data_dir
    if data_dir == "/var/lib/proofoftime":
        # Try to create, fall back to local
        try:
            os.makedirs(data_dir, exist_ok=True)
        except PermissionError:
            data_dir = os.path.expanduser("~/.proofoftime")
            os.makedirs(data_dir, exist_ok=True)

    # Logging to file when dashboard is active
    if args.deploy:
        log_dir = os.path.join(data_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            filename=os.path.join(log_dir, 'metatron.log'),
            filemode='a'
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s | %(levelname)-8s | %(message)s"
        )

    print_banner()
    metatron = Metatron(data_dir)

    # Signal handler
    def signal_handler(signum, frame):
        print("\n\n  Shutting down Pantheon...")
        metatron.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.status or (not args.deploy):
        # Status mode
        print("  Analyzing Pantheon...\n")
        results = metatron.analyze()

        for god_id, god in metatron.gods.items():
            status_sym = "✓" if god.status == GodStatus.OFFLINE else ("◌" if god.status == GodStatus.STUB else "✗")
            status_col = "\033[92m" if god.status == GodStatus.OFFLINE else ("\033[90m" if god.status == GodStatus.STUB else "\033[91m")
            print(f"  {status_col}{status_sym}\033[0m {god.symbol} {god.name.ljust(12)} │ {god.domain}")
            if god.error:
                print(f"      └─ {god.error}")

        errors = [g for g in metatron.gods.values() if g.status == GodStatus.ERROR]
        print()
        if errors:
            print(f"  \033[91m{len(errors)} gods have errors\033[0m")
        else:
            print("  \033[92mAll gods ready.\033[0m Run: python metatron.py --deploy")
        print()

    elif args.deploy:
        # Deploy mode
        print("  Deploying Pantheon...\n")

        if metatron.deploy(args.peer):
            print("\n  \033[92mNode deployed. Starting dashboard...\033[0m\n")
            time.sleep(1)
            metatron.dashboard_loop()
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
