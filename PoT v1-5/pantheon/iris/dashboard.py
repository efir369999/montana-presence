#!/usr/bin/env python3
"""
Proof of Time - Real-time Node Dashboard

Displays dual-layer consensus metrics:
- PoH: Fast layer (1 block/second)
- PoT: Finality layer (1 checkpoint/10 minutes)
"""

import os
import sys
import time
import json
from datetime import datetime

# Colors
G = '\033[92m'   # Green
Y = '\033[93m'   # Yellow
R = '\033[91m'   # Red
C = '\033[96m'   # Cyan
M = '\033[95m'   # Magenta
B = '\033[1m'    # Bold
D = '\033[2m'    # Dim
N = '\033[0m'    # Reset

def c(text, color):
    """Colorize text."""
    return f"{color}{text}{N}" if sys.stdout.isatty() else str(text)

def get_metrics():
    """Get metrics from node."""
    m = {
        # PoH layer (fast, 1 sec blocks)
        'poh_slot': 0,
        'poh_tps': 0.0,
        'poh_last': 0,

        # PoT layer (finality, 10 min checkpoints)
        'pot_checkpoint': 0,
        'pot_last': 0,
        'pot_next': 600,
        'pot_finalized': 0,

        # Network
        'nodes': 1,  # At least self
        'mempool': 0,
        'status': 'offline',
    }

    # Try RPC call to running node
    try:
        import urllib.request
        req = urllib.request.Request(
            'http://127.0.0.1:8332/',
            data=json.dumps({"method": "getinfo"}).encode(),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            if 'result' in data:
                r = data['result']
                m['poh_slot'] = r.get('poh_slot', r.get('height', 0))
                m['pot_checkpoint'] = r.get('pot_checkpoint', m['poh_slot'] // 600)
                m['nodes'] = 1 + r.get('peers', 0)  # Add 1 for self
                m['mempool'] = r.get('mempool_size', 0)
                m['poh_tps'] = r.get('tps', 0.0)
                m['status'] = 'producing'
    except:
        pass

    # Try database directly (fallback)
    try:
        from pantheon.hades.database import BlockchainDB
        from config import StorageConfig

        db_path = '/var/lib/proofoftime/blockchain.db'
        if os.path.exists(db_path):
            db = BlockchainDB(StorageConfig(db_path=db_path))

            state = db.get_chain_state()
            if state:
                m['poh_slot'] = state.get('tip_height', 0)
                m['pot_checkpoint'] = m['poh_slot'] // 600

            latest = db.get_latest_block()
            if latest:
                m['poh_last'] = int(time.time()) - latest.timestamp
                # PoT checkpoint timing
                slots_in_epoch = m['poh_slot'] % 600
                m['pot_next'] = 600 - slots_in_epoch
                m['pot_last'] = slots_in_epoch
                m['pot_finalized'] = m['pot_checkpoint'] * 600

            db.close()
            if m['status'] == 'offline':
                m['status'] = 'synced'
    except:
        pass

    # Check if node process running
    try:
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'node.py.*--run'],
                              capture_output=True, timeout=1)
        if result.returncode == 0:
            if m['status'] == 'offline':
                m['status'] = 'running'
            # If running and recent blocks, it's producing
            if m['poh_last'] < 5:
                m['status'] = 'producing'
    except:
        pass

    return m

def format_time(seconds):
    """Format seconds to MM:SS or HH:MM:SS."""
    if seconds < 0:
        return "--:--"
    if seconds < 3600:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

def render(m):
    """Render dashboard."""
    now = datetime.now().strftime('%H:%M:%S')

    # Status color
    if m['status'] == 'producing':
        status = c('PRODUCING', G)
    elif m['status'] in ('running', 'synced'):
        status = c(m['status'].upper(), Y)
    else:
        status = c('OFFLINE', R)

    # PoT next checkpoint color
    pot_next = m['pot_next']
    if pot_next > 300:
        pot_color = G
    elif pot_next > 60:
        pot_color = Y
    else:
        pot_color = R

    print()
    print(c("  PROOF OF TIME", G))
    print(c("  ═══════════════════════════════════════════════", D))
    print()
    print(f"  {c('STATUS', C)}        {status}")
    print(f"  {c('NODES', C)}         {m['nodes']}")
    print(f"  {c('MEMPOOL', C)}       {m['mempool']} tx")
    print()
    print(c("  ─── PoH Layer (1 sec blocks) ─────────────────", D))
    print(f"  {c('SLOT', M)}          {c(m['poh_slot'], B)}")
    print(f"  {c('TPS', M)}           {m['poh_tps']:.1f}")
    print(f"  {c('LAST BLOCK', M)}    {m['poh_last']}s ago")
    print()
    print(c("  ─── PoT Layer (10 min finality) ──────────────", D))
    print(f"  {c('CHECKPOINT', C)}    {c(m['pot_checkpoint'], B)}")
    print(f"  {c('FINALIZED', C)}     slot {m['pot_finalized']}")
    print(f"  {c('NEXT', C)}          {c(format_time(pot_next), pot_color)}")
    print()
    print(c(f"  ═══════════════════════════════════════════════", D))
    print(c(f"  Updated: {now}  │  Ctrl+C to exit", D))

def clear():
    """Clear screen."""
    os.system('clear' if os.name != 'nt' else 'cls')

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', '-l', action='store_true', help='Live mode')
    parser.add_argument('--json', '-j', action='store_true', help='JSON output')
    parser.add_argument('--interval', '-i', type=int, default=1, help='Update interval')
    args = parser.parse_args()

    if args.json:
        print(json.dumps(get_metrics(), indent=2))
        return

    if args.live:
        try:
            while True:
                clear()
                render(get_metrics())
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n")
    else:
        render(get_metrics())
        print()

if __name__ == '__main__':
    main()
