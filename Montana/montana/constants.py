"""
Ɉ Montana Protocol Constants v3.5

All protocol constants per MONTANA_TECHNICAL_SPECIFICATION.md §19, §28.

v3.5: Timechain architecture, UTC finality, ±5s tolerance, platform-independent light clients.
"""

from typing import Dict, List, Tuple

# ==============================================================================
# Ɉ MONTANA — TIMECHAIN: MECHANISM FOR ASYMPTOTIC TRUST IN TIME VALUE
# ==============================================================================
PROJECT: str = "Ɉ Montana"
SYMBOL: str = "Ɉ"
TICKER: str = "$MONT"
ARCHITECTURE: str = "Timechain"
DEFINITION: str = "lim(evidence → ∞) 1 Ɉ → 1 second"
TYPE: str = "Temporal Time Unit"

# Montana is a Timechain
# Timechain:  chain of time, bounded by physics

# ==============================================================================
# SUPPLY
# ==============================================================================
TOTAL_SUPPLY: int = 1_260_000_000          # 21 million minutes in seconds
INITIAL_DISTRIBUTION: int = 3000            # 50 minutes per block
HALVING_INTERVAL: int = 210_000             # Blocks per halving
TOTAL_BLOCKS: int = 6_930_000               # 33 eras × 210,000 blocks
TOTAL_ERAS: int = 33                        # Halving count

# Zero pre-allocation
PRE_ALLOCATION: int = 0
FOUNDER_UNITS: int = 0
RESERVED_UNITS: int = 0

# ==============================================================================
# NODE TYPES (2 types only)
# ==============================================================================
NODE_TYPE_FULL: int = 1                     # Full Node: Full history + VDF
NODE_TYPE_LIGHT: int = 2                    # Light Node: History from connection only
NODE_TYPES_TOTAL: int = 2                   # Exactly 2 node types in protocol

# ==============================================================================
# PARTICIPATION TIERS (3 tiers only, numbered 1-2-3)
# ==============================================================================
TIER_1: int = 1                             # Full Node operators
TIER_2: int = 2                             # Light Node operators OR Light Client owners
TIER_3: int = 3                             # Light Client users (any platform)
TIERS_TOTAL: int = 3                        # Exactly 3 tiers in protocol

# Lottery probability by tier
# Security from Tier 1, scale from Tier 2+3
TIER_1_WEIGHT: float = 0.70                 # 70% → Full Node (network security)
TIER_2_WEIGHT: float = 0.20                 # 20% → Light Node / Light Client owners
TIER_3_WEIGHT: float = 0.10                 # 10% → Light Client users (mass adoption)

# ==============================================================================
# LIGHT CLIENT PLATFORMS
# ==============================================================================
# Montana has NO dependency on any specific platform.
# Light clients are interchangeable interfaces to the same network.
# Time passes equally for all — no platform provides advantage.
LIGHT_CLIENT_PLATFORMS: list = [
    "telegram",      # Initial implementation
    "discord",       # Planned
    "wechat",        # Planned
    "ios_app",       # App Store — Planned
    "android_app",   # Google Play — Planned
    "web_app",       # Browser — Planned
]

TIER_WEIGHTS: Dict[int, float] = {
    TIER_1: TIER_1_WEIGHT,
    TIER_2: TIER_2_WEIGHT,
    TIER_3: TIER_3_WEIGHT,
}

# ==============================================================================
# LAYER 0-1: VDF (Class Group, Wesolowski 2019)
# ==============================================================================
# Type B security: reduction to class group order problem
VDF_TYPE: str = "class_group"               # Wesolowski construction
VDF_BASE_ITERATIONS: int = 16_777_216       # 2^24 sequential squarings
VDF_MAX_ITERATIONS: int = 268_435_456       # 2^28
VDF_MIN_ITERATIONS: int = 1_048_576         # 2^20

# Class Group parameters
VDF_DISCRIMINANT_BITS: int = 2048           # Security parameter for Δ
VDF_DISCRIMINANT_PRIMALITY_TESTS: int = 64  # Miller-Rabin rounds
VDF_CHALLENGE_BITS: int = 128               # Wesolowski challenge size

# Wesolowski proof parameters
WESOLOWSKI_HASH_TO_PRIME_ATTEMPTS: int = 1000  # Max attempts for hash-to-prime
WESOLOWSKI_PROOF_SECURITY_BITS: int = 128      # Security level

# ==============================================================================
# LAYER 2: UTC FINALITY (v3.4)
# ==============================================================================
# Time consensus
TIME_TOLERANCE_SEC: int = 5                  # ±5 seconds UTC tolerance between nodes
FINALITY_INTERVAL_SEC: int = 60              # 1 minute — finality boundary interval

# Finality levels (UTC boundaries passed)
FINALITY_SOFT_BOUNDARIES: int = 1            # 1 minute (1 boundary)
FINALITY_MEDIUM_BOUNDARIES: int = 2          # 2 minutes (2 boundaries)
FINALITY_HARD_BOUNDARIES: int = 3            # 3 minutes (3 boundaries)

# Legacy aliases for compatibility
FINALITY_SOFT_CHECKPOINTS: int = FINALITY_SOFT_BOUNDARIES
FINALITY_MEDIUM_CHECKPOINTS: int = FINALITY_MEDIUM_BOUNDARIES
FINALITY_HARD_CHECKPOINTS: int = FINALITY_HARD_BOUNDARIES

# ==============================================================================
# MINIMUM VIABLE NETWORK (v3.5)
# ==============================================================================
# BFT threshold: n ≥ 3f+1, f=2 → n≥7 for meaningful Byzantine tolerance
MIN_FINALITY_PARTICIPANTS: int = 7          # Minimum for meaningful BFT (f=2)
MIN_GEOGRAPHIC_REGIONS: int = 2             # Avoid single-region failure
MIN_AUTONOMOUS_SYSTEMS: int = 3             # Network path diversity
MIN_FULL_NODES: int = 3                     # Minimum for checkpoint creation

# Confidence thresholds
CONFIDENCE_FULL_PARTICIPANTS: int = 21      # Production BFT (f=6)
CONFIDENCE_FULL_REGIONS: int = 3            # Multi-region production
CONFIDENCE_HIGH_PARTICIPANTS: int = 7       # Meaningful BFT (f=2)
CONFIDENCE_HIGH_REGIONS: int = 2            # Multi-region minimum

# Confidence level labels
CONFIDENCE_FULL: str = "full"               # ≥21 participants, ≥3 regions
CONFIDENCE_HIGH: str = "high"               # ≥7 participants, ≥2 regions
CONFIDENCE_LOW: str = "low"                 # <7 participants OR <2 regions

# ==============================================================================
# SCORE SYSTEM
# ==============================================================================
SCORE_PRECISION: int = 1_000_000
SCORE_MIN_HEARTBEATS: int = 1
ACTIVITY_WINDOW_BLOCKS: int = 2016          # ~2 weeks
INACTIVITY_PENALTY_RATE: float = 0.001

# ==============================================================================
# BLOCK
# ==============================================================================
BLOCK_TIME_TARGET_SEC: int = 600            # 10 minutes
BLOCK_INTERVAL_MS: int = 600_000
GENESIS_TIMESTAMP_MS: int = 1704067200000   # 2024-01-01 00:00:00 UTC
MAX_BLOCK_SIZE: int = 4_194_304             # 4 MB
MAX_HEARTBEATS_PER_BLOCK: int = 1000
MAX_TRANSACTIONS_PER_BLOCK: int = 5000
VDF_TX_CHECKPOINT_SEC: int = 1              # Soft finality for tx ordering

# ==============================================================================
# TRANSACTIONS
# ==============================================================================
TX_FREE_PER_SECOND: int = 1
TX_FREE_PER_EPOCH: int = 10
TX_EPOCH_DURATION_SEC: int = 600            # 10 minutes

# Anti-spam PoW
POW_BASE_DIFFICULTY_BITS: int = 16          # ~65ms
POW_EXCESS_PENALTY_BITS: int = 2            # Per excess tx
POW_BURST_PENALTY_BITS: int = 4             # Per same-second tx
POW_MAX_DIFFICULTY_BITS: int = 32           # ~18 hours max
POW_MEMORY_COST_KB: int = 65536             # 64 MB Argon2id
POW_TIME_COST: int = 1
POW_PARALLELISM: int = 1

# ==============================================================================
# PRIVACY TIERS
# ==============================================================================
PRIVACY_T0: int = 0                         # Transparent
PRIVACY_T1: int = 1                         # Hidden receiver (stealth)
PRIVACY_T2: int = 2                         # Hidden receiver + amount
PRIVACY_T3: int = 3                         # Fully private (ring)

RING_SIZE: int = 11

PRIVACY_FEE_MULTIPLIERS: Dict[int, int] = {
    PRIVACY_T0: 1,
    PRIVACY_T1: 2,
    PRIVACY_T2: 5,
    PRIVACY_T3: 10,
}

# Pedersen generator
PEDERSEN_H_GENERATOR_SEED: bytes = b"MONTANA_PEDERSEN_H_V1"

# ==============================================================================
# NETWORK PROTOCOL
# ==============================================================================
PROTOCOL_VERSION: int = 9
NETWORK_ID_MAINNET: int = 0x4D4F4E5441      # "MONTA"
NETWORK_ID_TESTNET: int = 0x544553544E      # "TESTN"
DEFAULT_PORT: int = 19656
MESSAGE_MAGIC_MAINNET: bytes = b"MONT"
MESSAGE_MAGIC_TESTNET: bytes = b"TEST"

# Connection limits
MIN_OUTBOUND_CONNECTIONS: int = 8
MAX_OUTBOUND_CONNECTIONS: int = 12
MAX_INBOUND_CONNECTIONS: int = 125
MAX_TOTAL_CONNECTIONS: int = 137
MAX_CONNECTIONS_PER_SUBNET: int = 2

# Message limits
MAX_MESSAGE_SIZE: int = 4_194_304           # 4 MB
MAX_INV_COUNT: int = 50000
MAX_ADDR_COUNT: int = 1000
MAX_HEADERS_COUNT: int = 2000
MAX_GETDATA_COUNT: int = 50000
MESSAGE_RATE_LIMIT_PER_SEC: int = 100
MESSAGE_RATE_WINDOW_SEC: int = 10
MESSAGE_HEADER_SIZE: int = 13               # 4 + 1 + 4 + 4

# Handshake
HANDSHAKE_TIMEOUT_SEC: int = 30
HELLO_MAX_USER_AGENT_LENGTH: int = 256
HELLO_MAX_TIME_DRIFT_SEC: int = 7200        # 2 hours

# Keepalive
PING_INTERVAL_SEC: int = 120
PING_TIMEOUT_SEC: int = 20

# Address relay
ADDR_RELAY_INTERVAL_SEC: int = 30
ADDR_RELAY_MAX_PER_PEER: int = 10
ADDR_RELAY_PROBABILITY: float = 0.25
PEER_HORIZON_DAYS: int = 30
PEER_DB_MAX_ADDRESSES: int = 5000

# Inventory
INV_REQUEST_TIMEOUT_SEC: int = 60

# Block relay
ORPHAN_MAX_COUNT: int = 100
ORPHAN_EXPIRY_SEC: int = 3600               # 1 hour

# Ban system
MISBEHAVIOR_THRESHOLD: int = 100
BAN_DURATION_SEC: int = 86400               # 24 hours
BAN_DURATION_PERMANENT: int = -1

# Service flags
SERVICE_FULL_NODE: int = 0x01
SERVICE_LIGHT_NODE: int = 0x02
SERVICE_VDF: int = 0x04
SERVICE_RELAY: int = 0x10

# Bootstrap nodes
BOOTSTRAP_NODES: List[Dict] = [
    {
        "name": "montana-genesis-1",
        "ip": "176.124.208.93",
        "port": 19656,
        "region": "EU",
        "services": SERVICE_FULL_NODE | SERVICE_VDF,
    },
]

# ==============================================================================
# CRYPTOGRAPHY
# ==============================================================================
BIG_ENDIAN: str = "big"
LITTLE_ENDIAN: str = "little"

HASH_SIZE: int = 32
SHA3_256_OUTPUT_SIZE: int = 32
SHAKE256_OUTPUT_SIZE: int = 32

ALGORITHM_SPHINCS_PLUS: int = 0x01
ALGORITHM_ML_KEM: int = 0x02
ALGORITHM_ECVRF: int = 0x03

SPHINCS_PUBLIC_KEY_SIZE: int = 32
SPHINCS_SECRET_KEY_SIZE: int = 64
SPHINCS_SIGNATURE_SIZE: int = 17088

# ==============================================================================
# SYNC PROTOCOL
# ==============================================================================
IBD_BATCH_SIZE: int = 500
IBD_PARALLEL_DOWNLOADS: int = 4
IBD_CHECKPOINT_INTERVAL: int = 10000
BLOCK_PROPAGATION_TIMEOUT_MS: int = 5000
MAX_BLOCKS_IN_FLIGHT: int = 16
MAX_REORG_DEPTH: int = 100

# ==============================================================================
# MEMPOOL
# ==============================================================================
MEMPOOL_MAX_SIZE_MB: int = 300
MEMPOOL_MAX_TX_COUNT: int = 50000
MEMPOOL_EXPIRY_HOURS: int = 336             # 2 weeks
MEMPOOL_MIN_FEE_RATE: int = 1
RBF_ENABLED: bool = True
RBF_MIN_INCREMENT: float = 1.1              # 10% fee increase

# ==============================================================================
# STORAGE
# ==============================================================================
DB_PATH_DEFAULT: str = "montana.db"
BLOCKS_DIR: str = "blocks"
CHAINSTATE_DIR: str = "chainstate"
VDF_DIR: str = "vdf"
CACHE_SIZE_MB: int = 512
WRITE_BUFFER_MB: int = 64
MAX_OPEN_FILES: int = 1000
PRUNE_KEEP_BLOCKS: int = 10000

# ==============================================================================
# GOVERNANCE
# ==============================================================================
SOFT_FORK_THRESHOLD: float = 0.95
HARD_FORK_THRESHOLD: float = 0.95
ACTIVATION_WINDOW_BLOCKS: int = 2016
TIMEOUT_EPOCHS: int = 2

# ==============================================================================
# TELEGRAM BOT
# ==============================================================================
CHALLENGE_TIMEOUT_SEC: int = 60
TIME_VARIANCE_MINUTES: int = 2
BOT_MIN_FREQUENCY_SEC: int = 60
BOT_MAX_FREQUENCY_SEC: int = 86400

# ==============================================================================
# WALLET
# ==============================================================================
MIN_PASSWORD_LENGTH: int = 8
ARGON2_MEMORY_COST_KB: int = 65536
ARGON2_TIME_COST: int = 3
ARGON2_PARALLELISM: int = 4
AES_KEY_SIZE: int = 32
AES_NONCE_SIZE: int = 12
AES_TAG_SIZE: int = 16

# ==============================================================================
# PEER MANAGEMENT
# ==============================================================================
MAX_PEERS: int = 137
MAX_INBOUND_PEERS: int = 125
MAX_OUTBOUND_PEERS: int = 12
PEER_HANDSHAKE_TIMEOUT_SEC: int = 30
PEER_PING_INTERVAL_SEC: int = 120
PEER_TIMEOUT_SEC: int = 300

# ==============================================================================
# SYNC
# ==============================================================================
SYNC_TIMEOUT_SEC: int = 300
MAX_BLOCKS_PER_REQUEST: int = 500

# ==============================================================================
# VDF TIMING
# ==============================================================================
# VDF proves participation in finality window (not speed competition)
# Hardware that completes faster simply waits for UTC boundary
VDF_CHECKPOINT_INTERVAL_SEC: float = 60.0    # 1 minute (aligned with finality)
VDF_CHECKPOINT_TIME_SEC: float = VDF_CHECKPOINT_INTERVAL_SEC  # Alias for compatibility
HEARTBEAT_INTERVAL_MS: int = 60000           # 1 minute

# ==============================================================================
# FEES
# ==============================================================================
MIN_TRANSACTION_FEE: int = 1000           # 0.001 MONT in microMONT
INITIAL_BALANCE: int = 0

# Fee multipliers by privacy tier
PRIVACY_T0_FEE_MULTIPLIER: float = 1.0
PRIVACY_T1_FEE_MULTIPLIER: float = 2.0
PRIVACY_T2_FEE_MULTIPLIER: float = 5.0
PRIVACY_T3_FEE_MULTIPLIER: float = 10.0

# ==============================================================================
# SCORE
# ==============================================================================
SCORE_SQRT_COEFFICIENT: float = 1.0

# ==============================================================================
# MEMPOOL
# ==============================================================================
MAX_MEMPOOL_SIZE: int = 50000
MAX_MEMPOOL_TX_AGE_SEC: float = 1209600   # 2 weeks

# ==============================================================================
# TELEGRAM
# ==============================================================================
TELEGRAM_MIN_HEARTBEAT_INTERVAL_SEC: int = 60
CHALLENGE_PRECISION_BONUS_THRESHOLD_MS: int = 1000
MAX_CHALLENGE_ATTEMPTS: int = 3

# ==============================================================================
# API PORTS
# ==============================================================================
RPC_PORT: int = 19657
WS_PORT: int = 19658
