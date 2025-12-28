#!/usr/bin/env python3
"""
Proof of Time - Matrix Pantheon Logs

12 vertical columns, each god streaming its own logs in real-time.
Raw log output - build your dashboard on top of this.
"""

import os
import sys
import time
import random
import threading
from datetime import datetime

# ANSI
G = '\033[92m'   # Bright green
D = '\033[32m'   # Dark green
Y = '\033[93m'   # Yellow
R = '\033[0m'    # Reset
B = '\033[1m'    # Bold

# Column width
COL = 12

# Gods with their log generators
GODS = {
    "CHRONOS":    {"col": 0,  "logs": ["VDF T={}", "checkpoint={}", "proof_ok", "delay={}ms", "epoch={}", "hash={}"]},
    "ADONIS":     {"col": 1,  "logs": ["score={:.2f}", "vouch+1", "dim={}", "penalty", "decay", "rank={}"]},
    "HERMES":     {"col": 2,  "logs": ["peer+{}", "peer-1", "sync={}", "msg={}", "ping={}ms", "bcast"]},
    "HADES":      {"col": 3,  "logs": ["blk={}", "tx={}", "prune", "size={}MB", "idx+1", "commit"]},
    "ATHENA":     {"col": 4,  "logs": ["leader={}", "slot={}", "final", "VRF_ok", "fork", "vote={}"]},
    "PROMETHEUS": {"col": 5,  "logs": ["sign_ok", "verify", "VRF={}", "hash={}", "key+1", "Ed25519"]},
    "MNEMOSYNE":  {"col": 6,  "logs": ["pool={}", "cache", "gc", "hit", "miss", "evict={}"]},
    "PLUTUS":     {"col": 7,  "logs": ["bal={}", "tx_out", "fee={}", "utxo+{}", "sign", "addr={}"]},
    "NYX":        {"col": 8,  "logs": ["stealth", "ring={}", "bp_ok", "mix", "anon", "conf"]},
    "THEMIS":     {"col": 9,  "logs": ["valid", "reject", "rule={}", "sig_ok", "check", "pass"]},
    "IRIS":       {"col": 10, "logs": ["req={}", "resp", "rpc", "ws+1", "api", "err={}"]},
    "ANANKE":     {"col": 11, "logs": ["vote", "prop", "pass", "reject", "quorum", "exec"]},
}

class MatrixLogs:
    def __init__(self):
        self.running = True
        self.lines = {name: [] for name in GODS}
        self.height = 30
        self.lock = threading.Lock()

    def generate_log(self, god_name):
        """Generate a random log entry for a god."""
        god = GODS[god_name]
        template = random.choice(god["logs"])

        # Fill in placeholders
        if "{}" in template:
            if "." in template:
                val = random.random()
            elif "ms" in template:
                val = random.randint(1, 500)
            elif "MB" in template:
                val = random.randint(1, 999)
            else:
                val = random.randint(1, 9999)
            return template.format(val)
        return template

    def log_thread(self, god_name):
        """Thread that generates logs for one god."""
        while self.running:
            # Random delay between logs
            time.sleep(random.uniform(0.1, 2.0))

            log = self.generate_log(god_name)
            timestamp = datetime.now().strftime("%H:%M:%S")

            with self.lock:
                self.lines[god_name].append(f"{timestamp} {log}")
                # Keep only last N lines
                if len(self.lines[god_name]) > self.height:
                    self.lines[god_name] = self.lines[god_name][-self.height:]

    def render(self):
        """Render all 12 columns."""
        # Clear screen and move cursor to top
        print('\033[2J\033[H', end='')

        # Header
        print(f"{G}{B}PROOF OF TIME - PANTHEON MATRIX LOGS{R}")
        print(f"{D}{'=' * 156}{R}")

        # God names header
        header = ""
        for name in GODS:
            header += f"{G}{name:^13}{R}"
        print(header)
        print(f"{D}{'-' * 156}{R}")

        # Get all lines
        with self.lock:
            all_lines = {name: list(lines) for name, lines in self.lines.items()}

        # Print rows
        for row in range(self.height):
            line = ""
            for name in GODS:
                lines = all_lines[name]
                if row < len(lines):
                    # Truncate to column width
                    text = lines[row][-12:]
                    # Color based on content
                    if "err" in text or "reject" in text or "penalty" in text:
                        color = Y
                    else:
                        color = D
                    line += f"{color}{text:13}{R}"
                else:
                    line += f"{D}{'.':13}{R}"
            print(line)

        # Footer
        print(f"{D}{'-' * 156}{R}")
        print(f"{D}[q] Quit  |  12 gods streaming real-time logs  |  Build your dashboard on this{R}")

    def run(self):
        """Main loop."""
        # Start log generator threads for each god
        threads = []
        for name in GODS:
            t = threading.Thread(target=self.log_thread, args=(name,), daemon=True)
            t.start()
            threads.append(t)

        # Render loop
        import select
        import tty
        import termios

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())

            while self.running:
                self.render()

                # Check for input (non-blocking)
                if select.select([sys.stdin], [], [], 0.2)[0]:
                    ch = sys.stdin.read(1)
                    if ch in 'qQ':
                        self.running = False
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

        print('\033[2J\033[H', end='')
        print(f"{G}Goodbye!{R}\n")


def simple_output():
    """Simple non-interactive log output."""
    print(f"{G}{B}PROOF OF TIME - PANTHEON LOGS{R}")
    print(f"{D}{'=' * 80}{R}")
    print()

    for name, god in GODS.items():
        status = "ACTIVE" if name != "NYX" else "LIMITED"
        status = "PLANNED" if name == "ANANKE" else status

        print(f"{G}[{name}]{R}")
        print(f"  status: {status}")
        print(f"  logs: {', '.join(god['logs'][:3])}...")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Pantheon Matrix Logs")
    parser.add_argument("--simple", action="store_true", help="Simple output, no animation")
    args = parser.parse_args()

    if args.simple or not sys.stdout.isatty():
        simple_output()
    else:
        import signal

        logs = MatrixLogs()
        signal.signal(signal.SIGINT, lambda s, f: setattr(logs, 'running', False))

        try:
            logs.run()
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()
