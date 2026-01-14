#!/usr/bin/env python3
"""
Montana Bot Watchdog — Mesh Failover

Each node checks neighbors (before and after in priority chain).
Priority: Amsterdam(1) → Moscow(2) → Almaty(3)
"""

import os
import sys
import time
import subprocess
import socket
import requests
from pathlib import Path

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Node configuration (sorted by priority)
NODES = {
    "amsterdam": {"host": "72.56.102.240", "priority": 1},
    "moscow":    {"host": "176.124.208.93", "priority": 2},
    "almaty":    {"host": "91.200.148.93",  "priority": 3},
}

BOT_TOKEN = os.getenv("THOUGHTS_BOT_TOKEN", "")
CHECK_INTERVAL = 5  # seconds
TIMEOUT = 5  # seconds

def get_my_node():
    """Determine which node we're running on."""
    hostname = socket.gethostname()
    try:
        my_ip = subprocess.check_output(
            "hostname -I | awk '{print $1}'",
            shell=True, text=True
        ).strip()
    except:
        my_ip = ""

    for name, info in NODES.items():
        if info["host"] in my_ip or name in hostname.lower():
            return name, info
    return None, None

def check_node_health(host: str) -> bool:
    """Check if a node's bot is responding."""
    try:
        cmd = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no root@{host} \"pgrep -f '[u]nified_bot.py'\" 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=TIMEOUT)
        return result.returncode == 0
    except:
        return False

def start_local_bot():
    """Start the bot on this node."""
    bot_dir = Path(__file__).parent
    subprocess.run("pkill -9 -f unified_bot.py", shell=True, capture_output=True)
    time.sleep(2)
    cmd = f"cd {bot_dir} && nohup python3 -u unified_bot.py > /var/log/juno_bot.log 2>&1 &"
    subprocess.run(cmd, shell=True)
    print(f"[WATCHDOG] Started bot on this node")

def stop_local_bot():
    """Stop the bot on this node."""
    subprocess.run("pkill -9 -f unified_bot.py", shell=True, capture_output=True)
    print(f"[WATCHDOG] Stopped local bot")

def is_local_bot_running() -> bool:
    """Check if bot is running locally."""
    result = subprocess.run("pgrep -f '[u]nified_bot.py'", shell=True, capture_output=True)
    return result.returncode == 0

def get_neighbors(my_priority: int) -> dict:
    """Get nodes before and after in priority chain."""
    sorted_nodes = sorted(NODES.items(), key=lambda x: x[1]["priority"])

    before = None  # Higher priority (lower number)
    after = None   # Lower priority (higher number)

    for i, (name, info) in enumerate(sorted_nodes):
        if info["priority"] == my_priority:
            if i > 0:
                before = sorted_nodes[i-1]
            if i < len(sorted_nodes) - 1:
                after = sorted_nodes[i+1]
            break

    return {"before": before, "after": after}

def main():
    my_name, my_info = get_my_node()
    if not my_name:
        print("[WATCHDOG] Cannot determine which node I am. Exiting.")
        sys.exit(1)

    my_priority = my_info["priority"]
    neighbors = get_neighbors(my_priority)

    before_name = neighbors["before"][0] if neighbors["before"] else "none"
    after_name = neighbors["after"][0] if neighbors["after"] else "none"

    print(f"[WATCHDOG] Node: {my_name} (priority {my_priority})")
    print(f"[WATCHDOG] Checking: ← {before_name} | {after_name} →")
    print(f"[WATCHDOG] Interval: {CHECK_INTERVAL}s")

    while True:
        try:
            status = []

            # Check node BEFORE me (higher priority)
            before_active = False
            if neighbors["before"]:
                name, info = neighbors["before"]
                before_active = check_node_health(info["host"])
                status.append(f"←{name}:{'UP' if before_active else 'DOWN'}")

            # Check node AFTER me (lower priority)
            after_active = False
            if neighbors["after"]:
                name, info = neighbors["after"]
                after_active = check_node_health(info["host"])
                status.append(f"{name}→:{'UP' if after_active else 'DOWN'}")

            # My status
            my_bot_running = is_local_bot_running()
            status.append(f"[ME:{'RUN' if my_bot_running else 'STOP'}]")

            print(f"[WATCHDOG] {' | '.join(status)}")

            # Decision logic
            if before_active:
                # Higher priority node is active - I should NOT run
                if my_bot_running:
                    print(f"[WATCHDOG] Higher priority active - stopping")
                    stop_local_bot()
            else:
                # No higher priority node - I should run
                if not my_bot_running:
                    print(f"[WATCHDOG] No higher priority - TAKING OVER")
                    start_local_bot()

        except Exception as e:
            print(f"[WATCHDOG] Error: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
