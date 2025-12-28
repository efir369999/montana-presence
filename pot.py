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

# Terminal colors
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    BLACK = '\033[30m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_BLUE = '\033[44m'

    @staticmethod
    def rgb(r, g, b):
        return f'\033[38;2;{r};{g};{b}m'

# Disable if not TTY
if not sys.stdout.isatty():
    for attr in dir(C):
        if not attr.startswith('_') and attr != 'rgb':
            setattr(C, attr, '')

# ============================================================================
# PANTHEON GODS
# ============================================================================

GODS = [
    ("Chronos",    "Time/VDF",     C.YELLOW,  "active"),
    ("Adonis",     "Reputation",   C.MAGENTA, "active"),
    ("Hermes",     "Network",      C.CYAN,    "active"),
    ("Hades",      "Storage",      C.BLUE,    "active"),
    ("Athena",     "Consensus",    C.rgb(147,112,219), "active"),
    ("Prometheus", "Crypto",       C.RED,     "active"),
    ("Mnemosyne",  "Memory",       C.rgb(32,178,170), "active"),
    ("Plutus",     "Wallet",       C.GREEN,   "active"),
    ("Nyx",        "Privacy",      C.rgb(25,25,112), "limited"),
    ("Themis",     "Validation",   C.rgb(220,20,60), "active"),
    ("Iris",       "API",          C.rgb(255,20,147), "active"),
    ("Ananke",     "Governance",   C.rgb(139,69,19), "planned"),
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
        self.width = 80
        self.last_refresh = 0

    def clear(self):
        os.system('clear' if os.name != 'nt' else 'cls')

    def get_terminal_size(self):
        try:
            size = os.get_terminal_size()
            self.width = max(60, size.columns)
        except:
            self.width = 80

    def header(self):
        """Draw header."""
        print()
        title = "PANTHEON"
        subtitle = "Proof of Time Protocol"

        print(f"  {C.BOLD}{C.YELLOW}{title}{C.RESET}  {C.DIM}{subtitle}{C.RESET}")
        print(f"  {C.DIM}{'─' * 50}{C.RESET}")
        print(f"  {C.DIM}\"Chronos proves, Athena selects, Adonis trusts.\"{C.RESET}")
        print()

    def tab_bar(self):
        """Draw tab bar."""
        tabs_str = "  "
        for i, tab in enumerate(self.tabs):
            if i == self.current_tab:
                tabs_str += f"{C.BG_BLUE}{C.WHITE} {i+1}:{tab} {C.RESET} "
            else:
                tabs_str += f"{C.DIM}[{i+1}:{tab}]{C.RESET} "
        print(tabs_str)
        print(f"  {C.DIM}{'─' * 50}{C.RESET}")
        print()

    def render_gods(self):
        """Render Pantheon gods."""
        print(f"  {C.BOLD}The 12 Gods of Protocol{C.RESET}")
        print()

        for i, (name, domain, color, status) in enumerate(GODS, 1):
            status_icon = "●" if status == "active" else "○" if status == "limited" else "◌"
            status_color = C.GREEN if status == "active" else C.YELLOW if status == "limited" else C.DIM

            print(f"  {C.DIM}{i:2}.{C.RESET} {color}{C.BOLD}{name:12}{C.RESET} "
                  f"{C.DIM}│{C.RESET} {domain:12} "
                  f"{status_color}{status_icon} {status}{C.RESET}")

        print()

    def render_adonis(self):
        """Render Adonis reputation data."""
        print(f"  {C.BOLD}Adonis Reputation Engine{C.RESET}")
        print()

        if self.engine:
            stats = self.engine.get_stats()

            # Stats grid
            print(f"  {C.CYAN}Total Nodes:{C.RESET}    {stats['total_profiles']}")
            print(f"  {C.GREEN}Active:{C.RESET}         {stats['active_profiles']}")
            print(f"  {C.RED}Penalized:{C.RESET}      {stats['penalized_profiles']}")
            print(f"  {C.YELLOW}Vouches:{C.RESET}        {stats['total_vouches']}")
            print(f"  {C.MAGENTA}Avg Score:{C.RESET}      {stats['average_score']:.3f}")
            print(f"  {C.CYAN}Cities:{C.RESET}         {stats['unique_cities']}")
            print()

            # Dimensions
            print(f"  {C.BOLD}Dimensions:{C.RESET}")
            dim_colors = {
                'INTEGRITY': C.RED, 'RELIABILITY': C.BLUE,
                'LONGEVITY': C.MAGENTA, 'CONTRIBUTION': C.GREEN,
                'COMMUNITY': C.YELLOW, 'GEOGRAPHY': C.CYAN
            }
            for name, weight in stats['dimension_weights'].items():
                color = dim_colors.get(name, C.WHITE)
                bar_len = int(weight * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                print(f"  {color}{name:12}{C.RESET} {bar} {int(weight*100):3}%")
        else:
            print(f"  {C.DIM}No data available{C.RESET}")
        print()

    def render_geography(self):
        """Render geographic data."""
        print(f"  {C.BOLD}Geographic Diversity{C.RESET}")
        print()

        if self.engine:
            diversity = self.engine.get_geographic_diversity_score()
            cities = self.engine.get_city_distribution()

            print(f"  {C.CYAN}Unique Cities:{C.RESET}  {len(cities)}")
            print(f"  {C.MAGENTA}Diversity:{C.RESET}      {diversity*100:.1f}%")
            print()

            if cities:
                print(f"  {C.BOLD}City Distribution:{C.RESET}")
                sorted_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)
                for hash_prefix, count in sorted_cities[:10]:
                    bar = "█" * min(count, 20)
                    print(f"  {C.CYAN}{hash_prefix}{C.RESET} {bar} {count}")
        else:
            print(f"  {C.DIM}No data available{C.RESET}")
        print()

    def render_nodes(self):
        """Render top nodes."""
        print(f"  {C.BOLD}Top Nodes by Reputation{C.RESET}")
        print()

        if self.engine:
            top = self.engine.get_top_nodes(15)

            print(f"  {C.DIM}{'#':3} {'Node':18} {'Score':8} {'City':10} {'Vouches':8}{C.RESET}")
            print(f"  {C.DIM}{'─'*50}{C.RESET}")

            for i, (pubkey, score) in enumerate(top, 1):
                profile = self.engine.get_profile(pubkey)
                city = profile.city_hash.hex()[:8] if profile and profile.city_hash else "-"
                vouches = len(profile.trusted_by) if profile else 0

                score_color = C.GREEN if score > 0.5 else C.YELLOW
                print(f"  {i:3} {pubkey.hex()[:16]}.. {score_color}{score:.3f}{C.RESET}   "
                      f"{C.CYAN}{city}{C.RESET}   {vouches}")
        else:
            print(f"  {C.DIM}No data available{C.RESET}")
        print()

    def render_events(self):
        """Render recent events."""
        print(f"  {C.BOLD}Recent Events{C.RESET}")
        print()

        if self.engine:
            events = []
            for pubkey, profile in self.engine.profiles.items():
                for e in profile.history[-5:]:
                    events.append((e.timestamp, pubkey, e.event_type.name, e.impact))

            events.sort(key=lambda x: x[0], reverse=True)

            for ts, pk, event, impact in events[:15]:
                time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                impact_color = C.GREEN if impact >= 0 else C.RED
                impact_str = f"+{impact:.2f}" if impact >= 0 else f"{impact:.2f}"

                print(f"  {C.DIM}{time_str}{C.RESET}  {pk.hex()[:12]}..  "
                      f"{event:16}  {impact_color}{impact_str}{C.RESET}")
        else:
            print(f"  {C.DIM}No data available{C.RESET}")
        print()

    def footer(self):
        """Draw footer."""
        now = datetime.now().strftime("%H:%M:%S")
        print(f"  {C.DIM}{'─' * 50}{C.RESET}")
        print(f"  {C.DIM}Updated: {now}  │  [1-5] Tabs  [r] Refresh  [q] Quit{C.RESET}")
        print()

    def render(self):
        """Render current view."""
        self.get_terminal_size()
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
            print(f"\n{C.DIM}Shutting down...{C.RESET}")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        try:
            dashboard.run()
        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n{C.DIM}Goodbye!{C.RESET}\n")
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
