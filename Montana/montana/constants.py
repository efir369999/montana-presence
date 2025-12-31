"""
Ɉ Montana Constants

All protocol constants for the Montana application.
These extend PoT v6 constants with application-specific values.
"""

# =============================================================================
# Network Identification
# =============================================================================

NAME = "Montana"
SYMBOL = "Ɉ"
TICKER = "MONT"

NETWORK_ID = 0x4D4F4E54           # "MONT" in ASCII hex
NETWORK_MAGIC = b'\x4d\x4f\x4e\x54'  # Magic bytes
PROTOCOL_VERSION = 1

# Ports
DEFAULT_P2P_PORT = 9333
DEFAULT_RPC_PORT = 8332
DEFAULT_WS_PORT = 9334

# =============================================================================
# Token Parameters
# =============================================================================

DECIMALS = 0                      # Atomic unit is 1 second

# Supply (in seconds)
TOTAL_SUPPLY = 1_260_000_000      # 21 million minutes
MAX_SUPPLY = TOTAL_SUPPLY

# Emission
INITIAL_REWARD = 3000             # 50 minutes = 3000 seconds
HALVING_INTERVAL = 210_000        # Blocks per epoch (~4 years)
BLOCK_TIME = 600                  # 10 minutes in seconds

# Conversion helpers
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

# =============================================================================
# Participation Layers
# =============================================================================

# Layer weights (must sum to 1.0)
LAYER_WEIGHT_SERVER = 0.50        # Full node operators
LAYER_WEIGHT_BOT = 0.30           # Telegram bot users
LAYER_WEIGHT_USER = 0.15          # Chico Time players
LAYER_WEIGHT_RESERVED = 0.05      # Future extension

# Layer IDs
LAYER_SERVER = 0
LAYER_BOT = 1
LAYER_USER = 2
LAYER_RESERVED = 3

# Participation frequencies (seconds)
BOT_FREQ_MIN = 60                 # 1 minute minimum
BOT_FREQ_MAX = 86400              # 1 day maximum
BOT_FREQ_DEFAULT = 3600           # 1 hour default

# =============================================================================
# Chico Time Game
# =============================================================================

# Game parameters
CHICO_TIME_OPTIONS = 5            # Number of time choices
CHICO_TIME_TOLERANCE_MS = 120_000 # ±2 minutes tolerance
CHICO_TIME_EXPIRY_MS = 30_000     # Challenge expires in 30s
CHICO_TIME_COOLDOWN_MS = 60_000   # 1 minute between games
CHICO_TIME_INTERVAL_MS = 120_000  # 2 minutes between options

# Scoring
CHICO_CORRECT_POINTS = 10
CHICO_WRONG_PENALTY = 2
CHICO_TIMEOUT_PENALTY = 5

# =============================================================================
# Five Fingers of Adonis (Reputation)
# =============================================================================

# Weights
WEIGHT_TIME = 0.50                # THUMB
WEIGHT_INTEGRITY = 0.20           # INDEX
WEIGHT_STORAGE = 0.15             # MIDDLE
WEIGHT_EPOCHS = 0.10              # RING
WEIGHT_HANDSHAKE = 0.05           # PINKY

# Saturation thresholds
TIME_SATURATION_BLOCKS = 210_000  # 1 epoch (~4 years)
EPOCHS_SATURATION = 4             # 4 halvings (~16 years)
MAX_APOSTLES = 12                 # Maximum trust bonds

# Integrity penalties
INTEGRITY_VIOLATION_PENALTY = 0.10  # -10% per violation

# =============================================================================
# Twelve Apostles
# =============================================================================

MAX_APOSTLES = 12
MIN_INTEGRITY_FOR_HANDSHAKE = 0.50  # 50% minimum
HANDSHAKE_COOLDOWN = 86400          # 24 hours between handshakes

# =============================================================================
# HAL: Human Analyse Language
# =============================================================================

# Humanity tiers
HUMANITY_TIER_NONE = 0
HUMANITY_TIER_HARDWARE = 1
HUMANITY_TIER_SOCIAL = 2
HUMANITY_TIER_TIMELOCKED = 3

# Apostle limits per tier
MAX_APOSTLES_HARDWARE = 3         # Tier 1
MAX_APOSTLES_SOCIAL = 6           # Tier 2
MAX_APOSTLES_TIMELOCKED = 12      # Tier 3

# Weights
HUMANITY_WEIGHT_HARDWARE = 0.3
HUMANITY_WEIGHT_SOCIAL = 0.6
HUMANITY_WEIGHT_TIMELOCKED = 1.0

# Minimum humanity for handshake
HANDSHAKE_MIN_HUMANITY = 0.3

# Validity periods (seconds)
HARDWARE_PROOF_VALIDITY = 31_536_000     # 1 year
SOCIAL_PROOF_VALIDITY = 63_072_000       # 2 years
TIMELOCK_PROOF_VALIDITY = 126_144_000    # 4 years

# =============================================================================
# Slashing
# =============================================================================

ATTACKER_QUARANTINE_BLOCKS = 180_000     # ~3 years
VOUCHER_INTEGRITY_PENALTY = 0.25         # -25%
ASSOCIATE_INTEGRITY_PENALTY = 0.10       # -10%

# =============================================================================
# Anti-Cluster Protection
# =============================================================================

MAX_CLUSTER_INFLUENCE = 0.33
MAX_CORRELATION_THRESHOLD = 0.7
MIN_NETWORK_ENTROPY = 0.5

# =============================================================================
# Rate Limiting
# =============================================================================

# Per-IP limits
MAX_RPC_REQUESTS_PER_MINUTE = 60
MAX_WS_MESSAGES_PER_MINUTE = 100

# Per-account limits
MAX_CHICO_GAMES_PER_HOUR = 30
MAX_PARTICIPATION_PROOFS_PER_MINUTE = 10
MAX_HANDSHAKE_REQUESTS_PER_DAY = 5

# =============================================================================
# Telegram Bot
# =============================================================================

BOT_COMMAND_START = "/start"
BOT_COMMAND_TIME = "/time"
BOT_COMMAND_BALANCE = "/balance"
BOT_COMMAND_SEND = "/send"
BOT_COMMAND_APOSTLES = "/apostles"
BOT_COMMAND_STATS = "/stats"
BOT_COMMAND_FREQUENCY = "/frequency"
BOT_COMMAND_EXPORT = "/export"
BOT_COMMAND_IMPORT = "/import"

# =============================================================================
# Database
# =============================================================================

DB_FILE = "montana.db"
DB_SCHEMA_VERSION = 1

# =============================================================================
# Emission Schedule
# =============================================================================

def get_block_reward(height: int) -> int:
    """
    Calculate block reward at given height with halving.

    Args:
        height: Block height

    Returns:
        Reward in seconds (Ɉ)
    """
    halvings = height // HALVING_INTERVAL
    if halvings >= 33:
        return 0
    return INITIAL_REWARD >> halvings


def get_epoch(height: int) -> int:
    """Get halving epoch number for block height."""
    return height // HALVING_INTERVAL


def blocks_until_halving(height: int) -> int:
    """Calculate blocks remaining until next halving."""
    return HALVING_INTERVAL - (height % HALVING_INTERVAL)


def estimate_total_supply_at_height(height: int) -> int:
    """Estimate total supply emitted by given height."""
    if height <= 0:
        return 0

    total = 0
    remaining = height
    reward = INITIAL_REWARD

    while remaining > 0 and reward > 0:
        blocks_in_epoch = min(remaining, HALVING_INTERVAL)
        total += blocks_in_epoch * reward
        remaining -= blocks_in_epoch
        reward >>= 1

    return total


# =============================================================================
# Utility Functions
# =============================================================================

def seconds_to_human(seconds: int) -> str:
    """Convert seconds to human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"


def format_balance(balance: int) -> str:
    """Format balance with Ɉ symbol."""
    return f"{balance:,} {SYMBOL}"
