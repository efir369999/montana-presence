#!/usr/bin/env python3
"""
Proof of Time - Matrix-style Dashboard

Vertical columns showing all 12 gods with their parameters.
"""

import os
import sys
import time
import signal
import random

# ANSI
G = '\033[92m'  # Green (Matrix style)
D = '\033[32m'  # Dark green
W = '\033[97m'  # White
Y = '\033[93m'  # Yellow
R = '\033[0m'   # Reset
B = '\033[1m'   # Bold

# Gods data
GODS = [
    ("CHRONOS",    "Time/VDF",     "ACTIVE",  ["T=1M", "interval=600", "diff=2^20"]),
    ("ADONIS",     "Reputation",   "ACTIVE",  ["dims=6", "decay=0.99", "vouches=10/d"]),
    ("HERMES",     "Network",      "ACTIVE",  ["Noise_XX", "peers=50", "port=9333"]),
    ("HADES",      "Storage",      "ACTIVE",  ["SQLite", "DAG=on", "100GB"]),
    ("ATHENA",     "Consensus",    "ACTIVE",  ["VRF", "finality=6", "epoch=600"]),
    ("PROMETHEUS", "Crypto",       "ACTIVE",  ["Ed25519", "ECVRF", "SHA256"]),
    ("MNEMOSYNE",  "Memory",       "ACTIVE",  ["pool=10k", "ttl=300", "gc=60"]),
    ("PLUTUS",     "Wallet",       "ACTIVE",  ["Ed25519", "pot1", "dust=1k"]),
    ("NYX",        "Privacy",      "LIMITED", ["ring=11", "stealth", "conf=off"]),
    ("THEMIS",     "Validation",   "ACTIVE",  ["blk=1MB", "tx=100k", "sigops=20k"]),
    ("IRIS",       "API/RPC",      "ACTIVE",  ["rpc=8332", "ws=8333", "cors=on"]),
    ("ANANKE",     "Governance",   "PLANNED", ["vote=7d", "quorum=10%", "pass=67%"]),
]

def clear():
    print('\033[2J\033[H', end='')

def matrix_display():
    """Matrix-style vertical display."""
    clear()

    # Header
    print()
    print(f"{G}{B}  PROOF OF TIME - PANTHEON v2.2{R}")
    print(f"{D}  \"Chronos proves, Athena selects, Adonis trusts.\"{R}")
    print()
    print(f"{G}{'=' * 78}{R}")
    print()

    # Each god as vertical block
    for i, (name, domain, status, params) in enumerate(GODS, 1):
        # Status indicator
        if status == "ACTIVE":
            st = f"{G}[*]{R}"
        elif status == "LIMITED":
            st = f"{Y}[~]{R}"
        else:
            st = f"{D}[-]{R}"

        # God header
        print(f"{st} {G}{B}{i:2}. {name}{R}")
        print(f"    {D}|{R} Domain: {W}{domain}{R}")
        print(f"    {D}|{R} Status: {G if status == 'ACTIVE' else Y if status == 'LIMITED' else D}{status}{R}")
        print(f"    {D}|{R} Params:")
        for p in params:
            print(f"    {D}|{R}   {G}-{R} {p}")
        print(f"    {D}|{R}")

    print(f"{G}{'=' * 78}{R}")
    print()
    print(f"{D}  [q] Quit  [r] Refresh  [2] Adonis  [3] Geography{R}")
    print()

def adonis_display(engine):
    """Show Adonis stats."""
    clear()
    print()
    print(f"{G}{B}  ADONIS - REPUTATION ENGINE{R}")
    print(f"{G}{'=' * 50}{R}")
    print()

    if engine:
        stats = engine.get_stats()
        print(f"  {D}|{R} Total Nodes:   {G}{stats['total_profiles']}{R}")
        print(f"  {D}|{R} Active:        {G}{stats['active_profiles']}{R}")
        print(f"  {D}|{R} Penalized:     {Y}{stats['penalized_profiles']}{R}")
        print(f"  {D}|{R} Vouches:       {G}{stats['total_vouches']}{R}")
        print(f"  {D}|{R} Avg Score:     {G}{stats['average_score']:.4f}{R}")
        print(f"  {D}|{R} Cities:        {G}{stats['unique_cities']}{R}")
        print(f"  {D}|{R}")
        print(f"  {D}|{R} Dimensions:")
        for dim, weight in stats['dimension_weights'].items():
            pct = int(weight * 100)
            bar = f"{G}{'#' * (pct // 5)}{D}{'.' * (20 - pct // 5)}{R}"
            print(f"  {D}|{R}   {dim:12} [{bar}] {pct}%")
    else:
        print(f"  {D}No data{R}")

    print()
    print(f"{G}{'=' * 50}{R}")
    print(f"{D}  [1] Gods  [q] Quit{R}")
    print()

def geography_display(engine):
    """Show geography stats."""
    clear()
    print()
    print(f"{G}{B}  GEOGRAPHY - NETWORK DISTRIBUTION{R}")
    print(f"{G}{'=' * 50}{R}")
    print()

    if engine:
        diversity = engine.get_geographic_diversity_score()
        cities = engine.get_city_distribution()

        print(f"  {D}|{R} Unique Cities:   {G}{len(cities)}{R}")
        print(f"  {D}|{R} Diversity Score: {G}{diversity*100:.1f}%{R}")
        print(f"  {D}|{R}")

        if cities:
            print(f"  {D}|{R} City Distribution:")
            sorted_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)
            for hash_prefix, count in sorted_cities[:10]:
                bar = f"{G}{'#' * min(count * 2, 20)}{R}"
                print(f"  {D}|{R}   {hash_prefix}: {bar} ({count})")
    else:
        print(f"  {D}No data{R}")

    print()
    print(f"{G}{'=' * 50}{R}")
    print(f"{D}  [1] Gods  [q] Quit{R}")
    print()

def run_dashboard(engine=None):
    """Main loop."""
    import select
    import tty
    import termios

    view = 1  # 1=gods, 2=adonis, 3=geo
    running = True

    def render():
        if view == 1:
            matrix_display()
        elif view == 2:
            adonis_display(engine)
        elif view == 3:
            geography_display(engine)

    render()

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())

        while running:
            if select.select([sys.stdin], [], [], 0.5)[0]:
                ch = sys.stdin.read(1)

                if ch in 'qQ':
                    running = False
                elif ch in 'rR1':
                    view = 1
                    render()
                elif ch == '2':
                    view = 2
                    render()
                elif ch == '3':
                    view = 3
                    render()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    clear()
    print(f"{G}Goodbye!{R}\n")

def main():
    import argparse
    import logging

    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-tui", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    engine = None
    if args.demo:
        try:
            from adonis import AdonisEngine, ReputationEvent
            engine = AdonisEngine()

            cities = [("US", "NYC"), ("JP", "Tokyo"), ("DE", "Berlin"),
                      ("GB", "London"), ("FR", "Paris"), ("SG", "Singapore")]

            for i in range(15):
                pk = bytes([i + 1] * 32)
                country, city = random.choice(cities)
                engine.register_node_location(pk, country, city)

                for _ in range(random.randint(5, 20)):
                    evt = random.choice([
                        ReputationEvent.BLOCK_PRODUCED,
                        ReputationEvent.BLOCK_VALIDATED,
                        ReputationEvent.UPTIME_CHECKPOINT
                    ])
                    engine.record_event(pk, evt)
        except:
            pass

    if args.no_tui:
        matrix_display()
    else:
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
        run_dashboard(engine)

if __name__ == "__main__":
    main()
