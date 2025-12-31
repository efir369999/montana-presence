"""
PoT Protocol v6 Constants
Part II of Technical Specification

All protocol constants defined here for single source of truth.
"""

from typing import Final, List, Dict
from dataclasses import dataclass

# ==============================================================================
# LAYER 0: GLOBAL ATOMIC TIME CONSTANTS
# ==============================================================================

NTP_TOTAL_SOURCES: Final[int] = 34              # Total atomic time sources
NTP_MIN_SOURCES_CONSENSUS: Final[int] = 18      # >50% required
NTP_MIN_SOURCES_CONTINENT: Final[int] = 2       # Per inhabited continent
NTP_MIN_SOURCES_POLE: Final[int] = 1            # Per polar region
NTP_MIN_REGIONS_TOTAL: Final[int] = 5           # Minimum distinct regions
NTP_QUERY_TIMEOUT_MS: Final[int] = 2000         # Individual query timeout
NTP_MAX_DRIFT_MS: Final[int] = 1000             # Maximum acceptable drift
NTP_RETRY_COUNT: Final[int] = 3                 # Retries per server
NTP_QUERY_INTERVAL_SEC: Final[int] = 60         # Interval between queries

# Region identifiers
REGION_EUROPE: Final[int] = 0x01
REGION_ASIA: Final[int] = 0x02
REGION_NORTH_AMERICA: Final[int] = 0x03
REGION_SOUTH_AMERICA: Final[int] = 0x04
REGION_AFRICA: Final[int] = 0x05
REGION_OCEANIA: Final[int] = 0x06
REGION_ANTARCTICA: Final[int] = 0x07
REGION_ARCTIC: Final[int] = 0x08

# Region bit positions for bitmap
REGION_BIT_EUROPE: Final[int] = 0
REGION_BIT_ASIA: Final[int] = 1
REGION_BIT_NORTH_AMERICA: Final[int] = 2
REGION_BIT_SOUTH_AMERICA: Final[int] = 3
REGION_BIT_AFRICA: Final[int] = 4
REGION_BIT_OCEANIA: Final[int] = 5
REGION_BIT_ANTARCTICA: Final[int] = 6
REGION_BIT_ARCTIC: Final[int] = 7

# Inhabited continents (for minimum source checking)
INHABITED_CONTINENTS: Final[List[int]] = [
    REGION_EUROPE,
    REGION_ASIA,
    REGION_NORTH_AMERICA,
    REGION_SOUTH_AMERICA,
    REGION_AFRICA,
    REGION_OCEANIA,
]

# Polar regions (relaxed requirements)
POLAR_REGIONS: Final[List[int]] = [
    REGION_ANTARCTICA,
    REGION_ARCTIC,
]

ALL_REGIONS: Final[List[int]] = INHABITED_CONTINENTS + POLAR_REGIONS


@dataclass(frozen=True)
class AtomicTimeSource:
    """NTP server configuration."""
    region: int
    server_id: int
    lab: str
    host: str
    country: str
    city: str


# 34 Atomic Time Sources across 8 regions
ATOMIC_SOURCES: Dict[int, List[AtomicTimeSource]] = {
    REGION_EUROPE: [
        AtomicTimeSource(REGION_EUROPE, 0, "PTB", "ptbtime1.ptb.de", "Germany", "Braunschweig"),
        AtomicTimeSource(REGION_EUROPE, 1, "NPL", "ntp1.npl.co.uk", "UK", "London"),
        AtomicTimeSource(REGION_EUROPE, 2, "LNE-SYRTE", "ntp.obspm.fr", "France", "Paris"),
        AtomicTimeSource(REGION_EUROPE, 3, "METAS", "ntp.metas.ch", "Switzerland", "Bern"),
        AtomicTimeSource(REGION_EUROPE, 4, "INRIM", "ntp1.inrim.it", "Italy", "Turin"),
        AtomicTimeSource(REGION_EUROPE, 5, "VSL", "ntp.vsl.nl", "Netherlands", "Delft"),
        AtomicTimeSource(REGION_EUROPE, 6, "ROA", "ntp.roa.es", "Spain", "Cadiz"),
        AtomicTimeSource(REGION_EUROPE, 7, "GUM", "tempus1.gum.gov.pl", "Poland", "Warsaw"),
    ],
    REGION_ASIA: [
        AtomicTimeSource(REGION_ASIA, 0, "NICT", "ntp.nict.jp", "Japan", "Tokyo"),
        AtomicTimeSource(REGION_ASIA, 1, "NIM", "ntp.nim.ac.cn", "China", "Beijing"),
        AtomicTimeSource(REGION_ASIA, 2, "KRISS", "time.kriss.re.kr", "S. Korea", "Daejeon"),
        AtomicTimeSource(REGION_ASIA, 3, "NPLI", "time.nplindia.org", "India", "New Delhi"),
        AtomicTimeSource(REGION_ASIA, 4, "VNIIFTRI", "ntp2.vniiftri.ru", "Russia", "Moscow"),
        AtomicTimeSource(REGION_ASIA, 5, "TL", "time.stdtime.gov.tw", "Taiwan", "Taipei"),
        AtomicTimeSource(REGION_ASIA, 6, "INPL", "ntp.inpl.gov.il", "Israel", "Jerusalem"),
    ],
    REGION_NORTH_AMERICA: [
        AtomicTimeSource(REGION_NORTH_AMERICA, 0, "NIST", "time.nist.gov", "USA", "Boulder, CO"),
        AtomicTimeSource(REGION_NORTH_AMERICA, 1, "USNO", "tock.usno.navy.mil", "USA", "Washington"),
        AtomicTimeSource(REGION_NORTH_AMERICA, 2, "NRC", "time.nrc.ca", "Canada", "Ottawa"),
        AtomicTimeSource(REGION_NORTH_AMERICA, 3, "CENAM", "ntp.cenam.mx", "Mexico", "Queretaro"),
    ],
    REGION_SOUTH_AMERICA: [
        AtomicTimeSource(REGION_SOUTH_AMERICA, 0, "INMETRO", "ntp.inmetro.gov.br", "Brazil", "Rio de Janeiro"),
        AtomicTimeSource(REGION_SOUTH_AMERICA, 1, "INTI", "ntp.inti.gob.ar", "Argentina", "Buenos Aires"),
        AtomicTimeSource(REGION_SOUTH_AMERICA, 2, "INN", "ntp.inn.cl", "Chile", "Santiago"),
    ],
    REGION_AFRICA: [
        AtomicTimeSource(REGION_AFRICA, 0, "NMISA", "ntp.nmisa.org", "S. Africa", "Pretoria"),
        AtomicTimeSource(REGION_AFRICA, 1, "NIS", "ntp.nis.sci.eg", "Egypt", "Cairo"),
        AtomicTimeSource(REGION_AFRICA, 2, "KEBS", "ntp.kebs.org", "Kenya", "Nairobi"),
    ],
    REGION_OCEANIA: [
        AtomicTimeSource(REGION_OCEANIA, 0, "NMI", "time.nmi.gov.au", "Australia", "Sydney"),
        AtomicTimeSource(REGION_OCEANIA, 1, "MSL", "ntp.measurement.govt.nz", "New Zealand", "Wellington"),
        AtomicTimeSource(REGION_OCEANIA, 2, "NMC", "ntp.nmc.a-star.edu.sg", "Singapore", "Singapore"),
    ],
    REGION_ANTARCTICA: [
        AtomicTimeSource(REGION_ANTARCTICA, 0, "McMurdo", "ntp.mcmurdo.usap.gov", "USA/NSF", "Ross Island"),
        AtomicTimeSource(REGION_ANTARCTICA, 1, "Amundsen-Scott", "ntp.southpole.usap.gov", "USA/NSF", "South Pole"),
        AtomicTimeSource(REGION_ANTARCTICA, 2, "Concordia", "ntp.concordia.ipev.fr", "FR/IT", "Dome C"),
    ],
    REGION_ARCTIC: [
        AtomicTimeSource(REGION_ARCTIC, 0, "Ny-Alesund", "ntp.npolar.no", "Norway", "Svalbard"),
        AtomicTimeSource(REGION_ARCTIC, 1, "Thule", "ntp.thule.mil", "USA/DK", "Greenland"),
        AtomicTimeSource(REGION_ARCTIC, 2, "Alert", "ntp.alert.forces.gc.ca", "Canada", "Nunavut"),
    ],
}

# ==============================================================================
# LAYER 1: POT NETWORK CONSTANTS
# ==============================================================================

# VDF Parameters
VDF_HASH_FUNCTION: Final[str] = "SHAKE256"      # NIST FIPS 202
VDF_OUTPUT_BYTES: Final[int] = 32               # 256 bits
VDF_BASE_ITERATIONS: Final[int] = 16777216      # 2^24 (~2.5 seconds)
VDF_MAX_ITERATIONS: Final[int] = 268435456      # 2^28 (~40 seconds)
VDF_CHECKPOINT_INTERVAL: Final[int] = 1000      # For STARK proof generation
VDF_DIFFICULTY_SCALE: Final[int] = 1000         # Heartbeats per difficulty doubling
VDF_SEED_PREFIX: Final[bytes] = b"MONTANA_VDF_V6_"

# Cryptography
HASH_FUNCTION: Final[str] = "SHA3-256"          # NIST FIPS 202
SIGNATURE_SCHEME: Final[str] = "SPHINCS+-SHAKE-128f"  # NIST FIPS 205
KEY_ENCAPSULATION: Final[str] = "ML-KEM-768"    # NIST FIPS 203
PROOF_SYSTEM: Final[str] = "STARK"              # Transparent, post-quantum

# Key/Signature Sizes (bytes)
SPHINCS_PUBLIC_KEY_SIZE: Final[int] = 32
SPHINCS_SECRET_KEY_SIZE: Final[int] = 64
SPHINCS_SIGNATURE_SIZE: Final[int] = 17088
SHA3_256_OUTPUT_SIZE: Final[int] = 32
SHAKE256_OUTPUT_SIZE: Final[int] = 32           # Default, configurable

# Algorithm identifiers
ALGORITHM_SPHINCS_PLUS: Final[int] = 0x01

# ==============================================================================
# LAYER 2: BITCOIN ANCHOR CONSTANTS
# ==============================================================================

BTC_BLOCK_TIME_SECONDS: Final[int] = 600        # ~10 minutes average
BTC_DIFFICULTY_PERIOD: Final[int] = 2016        # Blocks per adjustment
BTC_HALVING_INTERVAL: Final[int] = 210000       # Blocks per halving (~4 years)
BTC_CONFIRMATIONS_SOFT: Final[int] = 1          # Soft finality
BTC_CONFIRMATIONS_MEDIUM: Final[int] = 6        # Standard finality
BTC_CONFIRMATIONS_STRONG: Final[int] = 100      # Deep finality
BTC_MAX_DRIFT_BLOCKS: Final[int] = 6            # Maximum blocks behind tip

# Bitcoin API endpoints (multiple for redundancy)
BTC_API_ENDPOINTS: Final[List[str]] = [
    "https://blockstream.info/api",
    "https://mempool.space/api",
    "https://blockchain.info",
    "https://api.blockcypher.com/v1/btc/main"
]
BTC_API_CONSENSUS_MIN: Final[int] = 2           # Minimum agreeing sources

# ==============================================================================
# TRANSACTION RATE LIMITING CONSTANTS
# ==============================================================================

TX_FREE_PER_SECOND: Final[int] = 1              # Free transactions per second
TX_FREE_PER_EPOCH: Final[int] = 10              # Free transactions per 10-min epoch
TX_EPOCH_DURATION_SEC: Final[int] = 600         # 10 minutes

POW_BASE_DIFFICULTY_BITS: Final[int] = 16       # ~65ms computation
POW_EXCESS_PENALTY_BITS: Final[int] = 2         # Per excess transaction
POW_BURST_PENALTY_BITS: Final[int] = 4          # Per same-second transaction
POW_MAX_DIFFICULTY_BITS: Final[int] = 32        # ~18 hours maximum
POW_MEMORY_COST_KB: Final[int] = 65536          # 64 MB for Argon2id
POW_TIME_COST: Final[int] = 1                   # Argon2id iterations
POW_PARALLELISM: Final[int] = 1                 # Argon2id lanes

# ==============================================================================
# SCORE SYSTEM CONSTANTS
# ==============================================================================

SCORE_FUNCTION: Final[str] = "SQRT"             # sqrt(heartbeats)
SCORE_PRECISION: Final[int] = 1_000_000         # Fixed-point precision (10^6)
SCORE_MIN_HEARTBEATS: Final[int] = 1            # Minimum heartbeats to have score
SCORE_MAX_MULTIPLIER: Final[float] = 1.0        # Maximum activity multiplier
ACTIVITY_WINDOW_BLOCKS: Final[int] = 2016       # ~2 weeks in BTC blocks
INACTIVITY_PENALTY_RATE: Final[float] = 0.001   # Penalty per inactive block
EPOCH_RESET_ON_HALVING: Final[bool] = True      # Scores reset at halving
EPOCH_DURATION_BLOCKS: Final[int] = 144         # Blocks per epoch (~144 BTC blocks/day)

# ==============================================================================
# NETWORK CONSTANTS
# ==============================================================================

NETWORK_ID_MAINNET: Final[int] = 0x4D4F4E5441   # "MONTA"
NETWORK_ID_TESTNET: Final[int] = 0x544553544E   # "TESTN"
PROTOCOL_VERSION: Final[int] = 6
MAX_BLOCK_SIZE_BYTES: Final[int] = 4194304      # 4 MB
MAX_HEARTBEATS_PER_BLOCK: Final[int] = 1000
MAX_TRANSACTIONS_PER_BLOCK: Final[int] = 5000
BLOCK_TIME_TARGET_SEC: Final[int] = 60          # 1 minute
BLOCK_INTERVAL_MS: Final[int] = 60000           # 1 minute in milliseconds
DEFAULT_PORT: Final[int] = 19656

# Fork choice parameters
FORK_CHOICE_DEPTH: Final[int] = 6               # Blocks to consider for fork choice
FINALITY_DEPTH: Final[int] = 100                # Blocks until finality
MAX_REORG_DEPTH: Final[int] = 100               # Maximum reorg depth allowed

# Aliases for common usage
NTP_MIN_SOURCES: Final[int] = NTP_MIN_SOURCES_CONSENSUS
NTP_MIN_REGIONS: Final[int] = NTP_MIN_REGIONS_TOTAL

# Message magic bytes
MESSAGE_MAGIC_MAINNET: Final[bytes] = b"MONT"
MESSAGE_MAGIC_TESTNET: Final[bytes] = b"TEST"

# ==============================================================================
# GENESIS CONSTANTS
# ==============================================================================

INITIAL_REWARD: Final[int] = 50_00000000        # 50 MONTANA (8 decimals)
DECIMALS: Final[int] = 8                        # Token decimals

# ==============================================================================
# SERIALIZATION CONSTANTS
# ==============================================================================

# Field sizes in bytes
HASH_SIZE: Final[int] = 32
PUBLIC_KEY_SIZE: Final[int] = 33                # algorithm (1) + data (32)
SIGNATURE_SIZE: Final[int] = 17089              # algorithm (1) + data (17088)
MEMO_MAX_SIZE: Final[int] = 256

# Byte order
BIG_ENDIAN: Final[str] = "big"
LITTLE_ENDIAN: Final[str] = "little"
