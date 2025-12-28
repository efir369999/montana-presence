#!/usr/bin/env python3
"""
Proof of Time - Unified Node + Dashboard

Single script to run the complete PoT node with live terminal dashboard.

Usage:
    python pot.py              # Run node with dashboard
    python pot.py --demo       # Demo mode with sample data
    python pot.py --web 8080   # Also start web dashboard on port 8080

Controls:
    q - Quit
    r - Refresh
    1-5 - Switch tabs (Gods/Adonis/Geo/Nodes/Events)
"""

import os
import sys
import time
import signal
import threading
import argparse
import logging
from datetime import datetime

# Simple ANSI colors (work on all terminals)
if sys.stdout.isatty():
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BG_BLUE = '\033[44m'
else:
    RESET = BOLD = DIM = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = BG_BLUE = ''

# ============================================================================
# PANTHEON GODS - Full data for each god
# ============================================================================

GODS = [
    {"num": 1,  "name": "Chronos",    "domain": "Time/VDF",     "status": "active",  "module": "crypto.py",    "desc": "VDF proof generation"},
    {"num": 2,  "name": "Adonis",     "domain": "Reputation",   "status": "active",  "module": "adonis.py",    "desc": "6-dimension scoring"},
    {"num": 3,  "name": "Hermes",     "domain": "Network/P2P",  "status": "active",  "module": "network.py",   "desc": "Noise protocol"},
    {"num": 4,  "name": "Hades",      "domain": "Storage",      "status": "active",  "module": "database.py",  "desc": "SQLite + DAG"},
    {"num": 5,  "name": "Athena",     "domain": "Consensus",    "status": "active",  "module": "consensus.py", "desc": "VRF leader select"},
    {"num": 6,  "name": "Prometheus", "domain": "Cryptography", "status": "active",  "module": "crypto.py",    "desc": "ECVRF + Ed25519"},
    {"num": 7,  "name": "Mnemosyne",  "domain": "Memory",       "status": "active",  "module": "structures.py","desc": "Mempool + cache"},
    {"num": 8,  "name": "Plutus",     "domain": "Wallet",       "status": "active",  "module": "wallet.py",    "desc": "Key management"},
    {"num": 9,  "name": "Nyx",        "domain": "Privacy",      "status": "limited", "module": "privacy.py",   "desc": "Stealth + Ring"},
    {"num": 10, "name": "Themis",     "domain": "Validation",   "status": "active",  "module": "node.py",      "desc": "Block validation"},
    {"num": 11, "name": "Iris",       "domain": "API/RPC",      "status": "active",  "module": "node.py",      "desc": "JSON-RPC server"},
    {"num": 12, "name": "Ananke",     "domain": "Governance",   "status": "planned", "module": "-",            "desc": "Protocol upgrades"},
]

# ============================================================================
# DASHBOARD
# ============================================================================

class TerminalDashboard:
    def __init__(self, engine=None, demo=False):
        self.engine = engine
        self.demo = demo
        self.running = True
        self.current_tab = 0
        self.tabs = ["PANTHEON", "ADONIS", "GEOGRAPHY", "NODES", "EVENTS"]

    def clear(self):
        os.system('clear' if os.name != 'nt' else 'cls')

    def box(self, title, width=70):
        """Draw box header."""
        print(f"+{'-' * (width-2)}+")
        padding = width - 4 - len(title)
        print(f"| {BOLD}{title}{RESET}{' ' * padding} |")
        print(f"+{'-' * (width-2)}+")

    def line(self, text, width=70):
        """Draw line inside box."""
        # Strip ANSI codes for length calculation
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', text)
        padding = width - 4 - len(clean)
        if padding < 0:
            padding = 0
        print(f"| {text}{' ' * padding} |")

    def end_box(self, width=70):
        """Draw box footer."""
        print(f"+{'-' * (width-2)}+")

    def header(self):
        """Draw header."""
        print()
        print(f"  {BOLD}{YELLOW}PROOF OF TIME{RESET} - Pantheon Protocol v2.2")
        print(f"  {DIM}\"Chronos proves, Athena selects, Adonis trusts.\"{RESET}")
        print()

    def tab_bar(self):
        """Draw tab bar."""
        tabs_str = "  "
        for i, tab in enumerate(self.tabs):
            if i == self.current_tab:
                tabs_str += f"[{BOLD}{i+1}:{tab}{RESET}] "
            else:
                tabs_str += f" {DIM}{i+1}:{tab}{RESET}  "
        print(tabs_str)
        print(f"  {'=' * 68}")
        print()

    def render_gods(self):
        """Render Pantheon gods with all parameters."""
        self.box("THE 12 GODS OF PROTOCOL")
        self.line("")
        self.line(f"{DIM}#   Name         Domain         Status    Module         Description{RESET}")
        self.line(f"{DIM}{'-' * 66}{RESET}")

        for god in GODS:
            # Status with color
            if god["status"] == "active":
                status = f"{GREEN}ACTIVE {RESET}"
                icon = "*"
            elif god["status"] == "limited":
                status = f"{YELLOW}LIMITED{RESET}"
                icon = "~"
            else:
                status = f"{DIM}PLANNED{RESET}"
                icon = "-"

            self.line(
                f"{icon} {god['num']:2}  {BOLD}{god['name']:10}{RESET}  "
                f"{god['domain']:13}  {status}  "
                f"{CYAN}{god['module']:13}{RESET}  {DIM}{god['desc']}{RESET}"
            )

        self.line("")
        self.line(f"  {GREEN}* Active: 10{RESET}   {YELLOW}~ Limited: 1{RESET}   {DIM}- Planned: 1{RESET}")
        self.end_box()

    def render_adonis(self):
        """Render Adonis reputation data."""
        self.box("ADONIS REPUTATION ENGINE")

        if self.engine:
            stats = self.engine.get_stats()

            self.line("")
            self.line(f"{BOLD}Network Statistics:{RESET}")
            self.line(f"  Total Nodes:     {CYAN}{stats['total_profiles']:5}{RESET}")
            self.line(f"  Active Nodes:    {GREEN}{stats['active_profiles']:5}{RESET}")
            self.line(f"  Penalized:       {RED}{stats['penalized_profiles']:5}{RESET}")
            self.line(f"  Total Vouches:   {YELLOW}{stats['total_vouches']:5}{RESET}")
            self.line(f"  Average Score:   {MAGENTA}{stats['average_score']:.3f}{RESET}")
            self.line(f"  Unique Cities:   {CYAN}{stats['unique_cities']:5}{RESET}")
            self.line("")
            self.line(f"{BOLD}Dimension Weights:{RESET}")
            self.line(f"{DIM}{'=' * 50}{RESET}")

            dim_colors = {
                'INTEGRITY': RED, 'RELIABILITY': BLUE,
                'LONGEVITY': MAGENTA, 'CONTRIBUTION': GREEN,
                'COMMUNITY': YELLOW, 'GEOGRAPHY': CYAN
            }

            for name, weight in stats['dimension_weights'].items():
                color = dim_colors.get(name, WHITE)
                bar_len = int(weight * 40)
                bar = "#" * bar_len + "." * (40 - bar_len)
                pct = int(weight * 100)
                self.line(f"  {color}{name:12}{RESET} [{bar}] {pct:2}%")
        else:
            self.line(f"{DIM}No data available{RESET}")

        self.end_box()

    def render_geography(self):
        """Render geographic data."""
        self.box("GEOGRAPHIC DIVERSITY")

        if self.engine:
            diversity = self.engine.get_geographic_diversity_score()
            cities = self.engine.get_city_distribution()

            self.line("")
            self.line(f"  Unique Cities:     {CYAN}{len(cities)}{RESET}")
            self.line(f"  Diversity Score:   {MAGENTA}{diversity*100:.1f}%{RESET}")
            self.line("")

            if cities:
                self.line(f"{BOLD}City Distribution (by hash prefix):{RESET}")
                self.line(f"{DIM}{'=' * 50}{RESET}")

                sorted_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)
                for hash_prefix, count in sorted_cities[:12]:
                    bar_len = min(count * 2, 30)
                    bar = "#" * bar_len
                    self.line(f"  {CYAN}{hash_prefix}{RESET} {bar} {count}")
        else:
            self.line(f"{DIM}No data available{RESET}")

        self.end_box()

    def render_nodes(self):
        """Render top nodes."""
        self.box("TOP NODES BY REPUTATION")

        if self.engine:
            top = self.engine.get_top_nodes(15)

            self.line("")
            self.line(f"{DIM}  #   Node ID            Score   City      Vouches{RESET}")
            self.line(f"{DIM}  {'-' * 55}{RESET}")

            for i, (pubkey, score) in enumerate(top, 1):
                profile = self.engine.get_profile(pubkey)
                city = profile.city_hash.hex()[:8] if profile and profile.city_hash else "--------"
                vouches = len(profile.trusted_by) if profile else 0

                if score > 0.7:
                    score_color = GREEN
                elif score > 0.4:
                    score_color = YELLOW
                else:
                    score_color = RED

                self.line(
                    f"  {i:2}.  {pubkey.hex()[:16]}..  "
                    f"{score_color}{score:.3f}{RESET}   {CYAN}{city}{RESET}   {vouches:3}"
                )
        else:
            self.line(f"{DIM}No data available{RESET}")

        self.end_box()

    def render_events(self):
        """Render recent events."""
        self.box("RECENT EVENTS")

        if self.engine:
            events = []
            for pubkey, profile in self.engine.profiles.items():
                for e in profile.history[-5:]:
                    events.append((e.timestamp, pubkey, e.event_type.name, e.impact))

            events.sort(key=lambda x: x[0], reverse=True)

            self.line("")
            self.line(f"{DIM}  Time      Node ID         Event             Impact{RESET}")
            self.line(f"{DIM}  {'-' * 55}{RESET}")

            for ts, pk, event, impact in events[:15]:
                time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")

                if impact >= 0:
                    impact_color = GREEN
                    impact_str = f"+{impact:.2f}"
                else:
                    impact_color = RED
                    impact_str = f"{impact:.2f}"

                self.line(
                    f"  {DIM}{time_str}{RESET}  {pk.hex()[:12]}..  "
                    f"{event:16}  {impact_color}{impact_str}{RESET}"
                )
        else:
            self.line(f"{DIM}No data available{RESET}")

        self.end_box()

    def footer(self):
        """Draw footer."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print()
        print(f"  {DIM}Updated: {now}  |  [1-5] Switch Tab  [r] Refresh  [q] Quit{RESET}")
        print()

    def render(self):
        """Render current view."""
        self.clear()
        self.header()
        self.tab_bar()

        if self.current_tab == 0:
            self.render_gods()
        elif self.current_tab == 1:
            self.render_adonis()
        elif self.current_tab == 2:
            self.render_geography()
        elif self.current_tab == 3:
            self.render_nodes()
        elif self.current_tab == 4:
            self.render_events()

        self.footer()

    def handle_input(self):
        """Handle keyboard input."""
        import select
        import tty
        import termios

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())

            while self.running:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)

                    if ch == 'q' or ch == 'Q':
                        self.running = False
                    elif ch == 'r' or ch == 'R':
                        self.render()
                    elif ch in '12345':
                        self.current_tab = int(ch) - 1
                        self.render()

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def run(self):
        """Main loop."""
        self.render()

        # Input thread
        input_thread = threading.Thread(target=self.handle_input, daemon=True)
        input_thread.start()

        # Auto-refresh loop
        while self.running:
            time.sleep(5)
            if self.running:
                self.render()


# ============================================================================
# DEMO DATA
# ============================================================================

def generate_demo_data(engine):
    """Generate demo data for testing."""
    import random
    from adonis import ReputationEvent

    cities = [
        ("US", "New York"), ("US", "Los Angeles"), ("JP", "Tokyo"),
        ("DE", "Berlin"), ("GB", "London"), ("FR", "Paris"),
        ("SG", "Singapore"), ("AU", "Sydney"), ("KR", "Seoul"),
        ("CA", "Toronto"), ("NL", "Amsterdam"), ("BR", "Sao Paulo")
    ]

    for i in range(20):
        pk = bytes([i + 1] * 32)
        country, city = random.choice(cities)
        engine.register_node_location(pk, country, city)

        for _ in range(random.randint(10, 40)):
            evt = random.choice([
                ReputationEvent.BLOCK_PRODUCED,
                ReputationEvent.BLOCK_VALIDATED,
                ReputationEvent.TX_RELAYED,
                ReputationEvent.UPTIME_CHECKPOINT
            ]) if random.random() > 0.1 else ReputationEvent.DOWNTIME
            engine.record_event(pk, evt, height=random.randint(1, 10000))

        if i > 0 and random.random() > 0.6:
            voucher = bytes([random.randint(1, i)] * 32)
            engine.add_vouch(voucher, pk)


# ============================================================================
# WEB SERVER (optional)
# ============================================================================

def start_web_server(engine, port):
    """Start web dashboard in background thread."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == '/api/overview':
                stats = engine.get_stats()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(stats).encode())
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<h1>Pantheon Dashboard</h1><p>API: /api/overview</p>")

    def run_server():
        HTTPServer(('0.0.0.0', port), Handler).serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Proof of Time Node + Dashboard")
    parser.add_argument("--demo", action="store_true", help="Demo mode with sample data")
    parser.add_argument("--web", type=int, metavar="PORT", help="Start web dashboard on port")
    parser.add_argument("--no-tui", action="store_true", help="Disable terminal UI")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize Adonis engine
    from adonis import AdonisEngine
    engine = AdonisEngine()

    if args.demo:
        generate_demo_data(engine)

    # Start web server if requested
    if args.web:
        start_web_server(engine, args.web)
        print(f"Web dashboard: http://0.0.0.0:{args.web}")

    # Run terminal dashboard
    if not args.no_tui:
        dashboard = TerminalDashboard(engine=engine, demo=args.demo)

        def signal_handler(sig, frame):
            dashboard.running = False
            print(f"\n{DIM}Shutting down...{RESET}")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            dashboard.run()
        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n{DIM}Goodbye!{RESET}\n")
    else:
        # Just run without TUI
        print("Node running... Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
