#!/usr/bin/env python3
"""
Montana Watchdog — Central Brain Architecture

One brain controls the network. If it dies, next becomes brain.
Brain chain: Moscow → Almaty → SPB → Novosibirsk
Bot chain:   Amsterdam → Almaty → SPB → Novosibirsk

Brain monitors all, decides who runs bot, syncs files.
"""

import os
import sys
import time
import subprocess
import socket
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK TOPOLOGY
# ═══════════════════════════════════════════════════════════════════════════════

# Brain chain (controllers) - who can be the central brain
BRAIN_CHAIN = [
    ("moscow",      "176.124.208.93"),
    ("almaty",      "91.200.148.93"),
    ("spb",         "188.225.58.98"),
    ("novosibirsk", "147.45.147.247"),
]

# Bot chain (workers) - who can run the bot
BOT_CHAIN = [
    ("amsterdam",   "72.56.102.240"),
    ("almaty",      "91.200.148.93"),
    ("spb",         "188.225.58.98"),
    ("novosibirsk", "147.45.147.247"),
]

CHECK_INTERVAL = 5   # seconds
SYNC_INTERVAL = 12   # seconds (breathing)
REPO_PATH = "/root/ACP_1"
BOT_DIR = "/root/ACP_1/金元Ɉ/thoughts_bot"
FLAG_FILE = "/tmp/juno_bot_active"  # Lock file

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_my_ip():
    """Get this node's IP."""
    try:
        return subprocess.check_output(
            "hostname -I | awk '{print $1}'", shell=True, text=True
        ).strip()
    except:
        return ""

def get_my_name():
    """Determine which node we are."""
    my_ip = get_my_ip()
    hostname = socket.gethostname().lower()

    all_nodes = {name: ip for name, ip in BRAIN_CHAIN + BOT_CHAIN}
    for name, ip in all_nodes.items():
        if ip in my_ip or name[:3] in hostname:
            return name, ip
    return None, None

def is_node_alive(ip: str) -> bool:
    """Check if node is reachable via SSH."""
    try:
        cmd = f"ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no root@{ip} 'echo ok' 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def is_bot_running_on(ip: str) -> bool:
    """Check if bot is running on remote node."""
    try:
        cmd = f"ssh -o ConnectTimeout=3 root@{ip} \"pgrep -f '[u]nified_bot.py'\" 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def is_bot_running_local() -> bool:
    """Check if bot is running locally."""
    result = subprocess.run("pgrep -f '[u]nified_bot.py'", shell=True, capture_output=True)
    return result.returncode == 0

def set_flag_on(ip: str):
    """Set active flag on remote node."""
    cmd = f"ssh root@{ip} 'echo active > {FLAG_FILE}' 2>/dev/null"
    subprocess.run(cmd, shell=True, capture_output=True)

def clear_flag_on(ip: str):
    """Clear active flag on remote node."""
    cmd = f"ssh root@{ip} 'rm -f {FLAG_FILE}' 2>/dev/null"
    subprocess.run(cmd, shell=True, capture_output=True)

def has_flag_on(ip: str) -> bool:
    """Check if flag exists on remote node."""
    try:
        cmd = f"ssh -o ConnectTimeout=2 root@{ip} 'test -f {FLAG_FILE}' 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def start_bot_on(ip: str):
    """Start bot on remote node with flag."""
    # Clear flags on ALL other nodes first
    for name, other_ip in BOT_CHAIN:
        if other_ip != ip:
            clear_flag_on(other_ip)
            stop_bot_on(other_ip)

    # Set flag and start (only if not already running)
    set_flag_on(ip)
    cmd = f"ssh root@{ip} 'pgrep -f unified_bot.py || (cd {BOT_DIR} && nohup python3 -u unified_bot.py > /var/log/juno_bot.log 2>&1 &)'"
    subprocess.run(cmd, shell=True, capture_output=True)

def stop_bot_on(ip: str):
    """Stop bot on remote node and clear flag."""
    clear_flag_on(ip)
    cmd = f"ssh root@{ip} 'pkill -9 -f unified_bot.py' 2>/dev/null"
    subprocess.run(cmd, shell=True, capture_output=True)

def start_bot_local():
    """Start bot locally."""
    subprocess.run("pkill -9 -f unified_bot.py", shell=True, capture_output=True)
    time.sleep(2)
    cmd = f"cd {BOT_DIR} && nohup python3 -u unified_bot.py > /var/log/juno_bot.log 2>&1 &"
    subprocess.run(cmd, shell=True)

def stop_bot_local():
    """Stop bot locally."""
    subprocess.run("pkill -9 -f unified_bot.py", shell=True, capture_output=True)

def sync_pull():
    """Inhale: git pull."""
    try:
        cmd = f"cd {REPO_PATH} && git pull origin main --rebase 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
        return result.returncode == 0
    except:
        return False

def sync_push():
    """Exhale: git push."""
    try:
        cmd = f"cd {REPO_PATH} && git push origin main 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
        return result.returncode == 0
    except:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# BRAIN LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

def am_i_the_brain(my_name: str) -> bool:
    """
    Am I the current brain?
    I'm the brain if all brains BEFORE me in chain are dead.
    """
    for name, ip in BRAIN_CHAIN:
        if name == my_name:
            return True  # Reached myself - I'm the brain
        if is_node_alive(ip):
            return False  # Someone before me is alive - they're the brain
    return False

def find_best_bot_node() -> tuple:
    """Find the first alive node in bot chain."""
    for name, ip in BOT_CHAIN:
        if is_node_alive(ip):
            return name, ip
    return None, None

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    my_name, my_ip = get_my_name()
    if not my_name:
        print("[WATCHDOG] Unknown node. Exiting.")
        sys.exit(1)

    # Am I in brain chain?
    is_brain_candidate = any(name == my_name for name, _ in BRAIN_CHAIN)
    # Am I in bot chain?
    is_bot_candidate = any(name == my_name for name, _ in BOT_CHAIN)

    print(f"[WATCHDOG] Node: {my_name} ({my_ip})")
    print(f"[WATCHDOG] Brain candidate: {is_brain_candidate} | Bot candidate: {is_bot_candidate}")
    print(f"[WATCHDOG] Check: {CHECK_INTERVAL}s | Sync: {SYNC_INTERVAL}s")

    last_sync = 0

    while True:
        try:
            i_am_brain = am_i_the_brain(my_name) if is_brain_candidate else False

            if i_am_brain:
                # ═══ BRAIN MODE ═══
                # I control the network

                # Find who should run the bot
                best_name, best_ip = find_best_bot_node()

                # Check current bot status on all nodes
                bot_status = []
                current_bot_node = None
                for name, ip in BOT_CHAIN:
                    if is_bot_running_on(ip):
                        bot_status.append(f"{name}:RUN")
                        current_bot_node = name
                    else:
                        bot_status.append(f"{name}:STOP")

                print(f"[BRAIN] {' | '.join(bot_status)} | Best: {best_name}")

                # Ensure only the best node runs the bot
                if best_name and current_bot_node != best_name:
                    # Stop bot on wrong nodes
                    for name, ip in BOT_CHAIN:
                        if name != best_name and is_bot_running_on(ip):
                            print(f"[BRAIN] Stopping bot on {name}")
                            stop_bot_on(ip)

                    # Start bot on best node
                    if not current_bot_node:  # No bot running anywhere
                        print(f"[BRAIN] Starting bot on {best_name}")
                        start_bot_on(best_ip)
                        time.sleep(10)  # Wait for bot to start

            else:
                # ═══ STANDBY MODE ═══
                # Not the brain - just monitor and sync

                # Find current brain
                current_brain = "unknown"
                for name, ip in BRAIN_CHAIN:
                    if is_node_alive(ip):
                        current_brain = name
                        break

                # Check if I should run the bot (if I'm in bot chain)
                my_bot_running = is_bot_running_local() if is_bot_candidate else False

                print(f"[STANDBY] Brain: {current_brain} | Me: {'BOT' if my_bot_running else 'IDLE'}")

            # ═══ BREATHING (all nodes) ═══
            now = time.time()
            if now - last_sync >= SYNC_INTERVAL:
                pull_ok = sync_pull()
                push_ok = sync_push()
                print(f"[BREATH] ↓{'OK' if pull_ok else 'SKIP'} ↑{'OK' if push_ok else 'SKIP'}")
                last_sync = now

        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
