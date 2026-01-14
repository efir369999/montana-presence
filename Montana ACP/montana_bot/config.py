"""
Montana Bot Configuration
"""

import os

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Montana Network
MONTANA_P2P_HOST = os.getenv("MONTANA_P2P_HOST", "176.124.208.93")
MONTANA_P2P_PORT = int(os.getenv("MONTANA_P2P_PORT", "19333"))

# Node configuration
NODE_TYPE = "light_client"  # Light Client (10% шанс в лотерее)
SIGN_INTERVAL_SECONDS = 600  # 10 минут (τ₂)

# Cryptography
MNEMONIC_WORDS = 24  # BIP-39 (24 words)
KEY_DERIVATION_PATH = "m/44'/463'/0'/0/0"  # Montana (coin type 463)

# Storage
DATA_DIR = os.getenv("DATA_DIR", "./data")
DB_FILE = os.path.join(DATA_DIR, "montana_bot.db")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(DATA_DIR, "montana_bot.log")

# Rate limiting
MAX_SIGNS_PER_HOUR = 10  # Max 10 signatures per hour per user

# Genesis
GENESIS_TIMESTAMP = 1735516800  # 2025-01-01 00:00:00 UTC (placeholder)
TAU2_SECONDS = 600  # 10 minutes
