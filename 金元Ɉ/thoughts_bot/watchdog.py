#!/usr/bin/env python3
"""
Montana Bot Watchdog — Active-Passive Failover

Priority: Amsterdam → Moscow → Almaty
Each node checks higher-priority nodes. If all higher nodes are down, take over.
"""

import os
import sys
import time
import subprocess
import socket
import requests
from pathlib import Path

# Node configuration
NODES = {
    "amsterdam": {"host": "72.56.102.240", "priority": 1},
    "moscow":    {"host": "176.124.208.93", "priority": 2},
    "almaty":    {"host": "91.200.148.93",  "priority": 3},
}

# Bot token for health check
BOT_TOKEN = os.getenv("THOUGHTS_BOT_TOKEN", "")
CHECK_INTERVAL = 30  # seconds
TIMEOUT = 10  # seconds

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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((host, 22))
        sock.close()

        if result != 0:
            return False

        # Check if bot process is running on that node
        cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@{host} 'pgrep -f unified_bot.py' 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=TIMEOUT)
        return result.returncode == 0
    except:
        return False

def check_telegram_polling() -> bool:
    """Check if our bot is successfully polling Telegram."""
    if not BOT_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        r = requests.get(url, timeout=5)
        return r.status_code == 200 and r.json().get("ok", False)
    except:
        return False

def start_local_bot():
    """Start the bot on this node."""
    bot_dir = Path(__file__).parent
    bot_script = bot_dir / "unified_bot.py"
    log_file = "/var/log/juno_bot.log"

    # Kill any existing instance
    subprocess.run("pkill -9 -f unified_bot.py", shell=True, capture_output=True)
    time.sleep(2)

    # Start new instance
    cmd = f"cd {bot_dir} && nohup python3 -u unified_bot.py > {log_file} 2>&1 &"
    subprocess.run(cmd, shell=True)
    print(f"[WATCHDOG] Started bot on this node")

def stop_local_bot():
    """Stop the bot on this node."""
    subprocess.run("pkill -9 -f unified_bot.py", shell=True, capture_output=True)
    print(f"[WATCHDOG] Stopped local bot")

def is_local_bot_running() -> bool:
    """Check if bot is running locally."""
    result = subprocess.run("pgrep -f unified_bot.py", shell=True, capture_output=True)
    return result.returncode == 0

def main():
    my_name, my_info = get_my_node()
    if not my_name:
        print("[WATCHDOG] Cannot determine which node I am. Exiting.")
        sys.exit(1)

    my_priority = my_info["priority"]
    print(f"[WATCHDOG] Running on {my_name} (priority {my_priority})")
    print(f"[WATCHDOG] Checking every {CHECK_INTERVAL}s")

    while True:
        try:
            # Find all higher-priority nodes
            higher_nodes = [
                (name, info) for name, info in NODES.items()
                if info["priority"] < my_priority
            ]

            # Check if any higher-priority node has a running bot
            higher_node_active = False
            for name, info in higher_nodes:
                if check_node_health(info["host"]):
                    print(f"[WATCHDOG] {name} is active (priority {info['priority']})")
                    higher_node_active = True
                    break
                else:
                    print(f"[WATCHDOG] {name} is DOWN")

            if higher_node_active:
                # Higher priority node is handling it
                if is_local_bot_running():
                    print(f"[WATCHDOG] Stopping local bot - higher priority node is active")
                    stop_local_bot()
            else:
                # No higher priority node is active - we should take over
                if not is_local_bot_running():
                    print(f"[WATCHDOG] No higher priority node active - TAKING OVER")
                    start_local_bot()
                else:
                    print(f"[WATCHDOG] Bot running locally (we are primary)")

        except Exception as e:
            print(f"[WATCHDOG] Error: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
