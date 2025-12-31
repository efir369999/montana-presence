# ATC: ASYMPTOTIC TRUST CONSENSUS
# Complete Technical Specification v7
# Implementation Reference Document

================================================================================
DOCUMENT PURPOSE
================================================================================

This document provides complete specifications for implementing the ATC
(Asymptotic Trust Consensus) protocol. It is designed to be self-sufficient: given only this document as input,
an implementation can be created from scratch.

Dedication: Hal Finney (1956-2014) — First Bitcoin recipient, RPOW creator.

================================================================================
TABLE OF CONTENTS
================================================================================

PART I:   ARCHITECTURE OVERVIEW
PART II:  CONSTANTS AND CONFIGURATION
PART III: DATA STRUCTURES
PART IV:  LAYER 0 — PHYSICAL TIME (Global Atomic Nodes)
PART V:   LAYER 1 — TEMPORAL PROOF (ATC Network Nodes)
PART VI:  LAYER 2 — FINALIZATION (Bitcoin Anchor)
PART VII: HEARTBEAT SYSTEM
PART VIII: TRANSACTION SYSTEM
PART IX:  PERSONAL RATE LIMITING
PART X:   SCORE AND CONSENSUS
PART XI:  BLOCK STRUCTURE
PART XII: CRYPTOGRAPHIC PRIMITIVES
PART XIII: NETWORK PROTOCOL
PART XIV: VALIDATION RULES
PART XV:  STATE MACHINE
PART XVI: GENESIS AND EMISSION
PART XVII: API SPECIFICATION
PART XVIII: ERROR HANDLING
PART XIX: TEST VECTORS

================================================================================
PART I: ARCHITECTURE OVERVIEW
================================================================================

CORE CONCEPT: ASYMPTOTIC TRUST
------------------------------

Trust in the system approaches zero as confirmations increase across layers.

    Trust(t) → 0 as t → ∞

The architecture achieves this through three layers:

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  LAYER 2: BITCOIN ANCHOR                                                    │
│  ─────────────────────                                                      │
│  Trust: T₂(c) = 2^(-c) where c = confirmations                             │
│  Purpose: Absolute finalization, epoch boundaries                          │
│  Mechanism: Block hash references, halving cycles                          │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: ATC NETWORK NODES                                                 │
│  ─────────────────────────                                                  │
│  Trust: T₁(c) = 1/√c where c = heartbeat count                             │
│  Purpose: Temporal proof, network consensus                                │
│  Mechanism: VDF (SHAKE256), STARK proofs, cryptographic signatures         │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 0: GLOBAL ATOMIC TIME NODES                                          │
│  ─────────────────────────────────                                          │
│  Trust: T₀ = 0 (no cryptographic proof required)                           │
│  Purpose: Physical time reference                                          │
│  Mechanism: NTP queries to national metrology laboratories                 │
│  Key Insight: Time is observable physical reality, not a cryptographic claim│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

FOUR ABSOLUTES
--------------

α (ALPHA): Time is sequential
    - VDF computation requires previous output
    - Cannot be parallelized with any amount of hardware

β (BETA): Time is universal
    - 34 atomic sources across 8 regions including both poles
    - Physical measurement, not cryptographic claim

γ (GAMMA): Time is irreversible
    - Bitcoin blocks are immutable
    - Halving events provide absolute epoch boundaries

δ (DELTA): Spam is personal
    - Each sender pays for their own excess
    - Network is not affected by individual spammers

================================================================================
PART II: CONSTANTS AND CONFIGURATION
================================================================================

# ==============================================================================
# LAYER 0: GLOBAL ATOMIC TIME CONSTANTS
# ==============================================================================

NTP_TOTAL_SOURCES           = 34              # Total atomic time sources
NTP_MIN_SOURCES_CONSENSUS   = 18              # >50% required
NTP_MIN_SOURCES_CONTINENT   = 2               # Per inhabited continent
NTP_MIN_SOURCES_POLE        = 1               # Per polar region
NTP_MIN_REGIONS_TOTAL       = 5               # Minimum distinct regions
NTP_QUERY_TIMEOUT_MS        = 2000            # Individual query timeout
NTP_MAX_DRIFT_MS            = 1000            # Maximum acceptable drift
NTP_RETRY_COUNT             = 3               # Retries per server
NTP_QUERY_INTERVAL_SEC      = 60              # Interval between queries

# Region identifiers
REGION_EUROPE               = 0x01
REGION_ASIA                 = 0x02
REGION_NORTH_AMERICA        = 0x03
REGION_SOUTH_AMERICA        = 0x04
REGION_AFRICA               = 0x05
REGION_OCEANIA              = 0x06
REGION_ANTARCTICA           = 0x07
REGION_ARCTIC               = 0x08

# ==============================================================================
# LAYER 1: ATC NETWORK CONSTANTS
# ==============================================================================

# VDF Parameters
VDF_HASH_FUNCTION           = "SHAKE256"      # NIST FIPS 202
VDF_OUTPUT_BYTES            = 32              # 256 bits
VDF_BASE_ITERATIONS         = 16777216        # 2^24 (~2.5 seconds)
VDF_MAX_ITERATIONS          = 268435456       # 2^28 (~40 seconds)
VDF_CHECKPOINT_INTERVAL     = 1000            # For STARK proof generation
VDF_DIFFICULTY_SCALE        = 1000            # Heartbeats per difficulty doubling
VDF_SEED_PREFIX             = b"MONTANA_VDF_V6_"

# Cryptography
HASH_FUNCTION               = "SHA3-256"      # NIST FIPS 202
SIGNATURE_SCHEME            = "SPHINCS+-SHAKE-128f"  # NIST FIPS 205
KEY_ENCAPSULATION           = "ML-KEM-768"    # NIST FIPS 203
PROOF_SYSTEM                = "STARK"         # Transparent, post-quantum

# Key/Signature Sizes (bytes)
SPHINCS_PUBLIC_KEY_SIZE     = 32
SPHINCS_SECRET_KEY_SIZE     = 64
SPHINCS_SIGNATURE_SIZE      = 17088
SHA3_256_OUTPUT_SIZE        = 32
SHAKE256_OUTPUT_SIZE        = 32              # Default, configurable

# ==============================================================================
# LAYER 2: BITCOIN ANCHOR CONSTANTS
# ==============================================================================

BTC_BLOCK_TIME_SECONDS      = 600             # ~10 minutes average
BTC_DIFFICULTY_PERIOD       = 2016            # Blocks per adjustment
BTC_HALVING_INTERVAL        = 210000          # Blocks per halving (~4 years)
BTC_CONFIRMATIONS_SOFT      = 1               # Soft finality
BTC_CONFIRMATIONS_MEDIUM    = 6               # Standard finality
BTC_CONFIRMATIONS_STRONG    = 100             # Deep finality
BTC_MAX_DRIFT_BLOCKS        = 6               # Maximum blocks behind tip

# Bitcoin API endpoints (multiple for redundancy)
BTC_API_ENDPOINTS = [
    "https://blockstream.info/api",
    "https://mempool.space/api",
    "https://blockchain.info",
    "https://api.blockcypher.com/v1/btc/main"
]
BTC_API_CONSENSUS_MIN       = 2               # Minimum agreeing sources

# ==============================================================================
# TRANSACTION RATE LIMITING CONSTANTS
# ==============================================================================

TX_FREE_PER_SECOND          = 1               # Free transactions per second
TX_FREE_PER_EPOCH           = 10              # Free transactions per 10-min epoch
TX_EPOCH_DURATION_SEC       = 600             # 10 minutes

POW_BASE_DIFFICULTY_BITS    = 16              # ~65ms computation
POW_EXCESS_PENALTY_BITS     = 2               # Per excess transaction
POW_BURST_PENALTY_BITS      = 4               # Per same-second transaction
POW_MAX_DIFFICULTY_BITS     = 32              # ~18 hours maximum
POW_MEMORY_COST_KB          = 65536           # 64 MB for Argon2id
POW_TIME_COST               = 1               # Argon2id iterations
POW_PARALLELISM             = 1               # Argon2id lanes

# ==============================================================================
# SCORE SYSTEM CONSTANTS
# ==============================================================================

SCORE_FUNCTION              = "SQRT"          # √(heartbeats)
ACTIVITY_WINDOW_BLOCKS      = 2016            # ~2 weeks in BTC blocks
EPOCH_RESET_ON_HALVING      = True            # Scores reset at halving

# ==============================================================================
# NETWORK CONSTANTS
# ==============================================================================

NETWORK_ID_MAINNET          = 0x4D4F4E5441    # "MONTA"
NETWORK_ID_TESTNET          = 0x544553544E    # "TESTN"
PROTOCOL_VERSION            = 6
MAX_BLOCK_SIZE_BYTES        = 4194304         # 4 MB
MAX_HEARTBEATS_PER_BLOCK    = 1000
MAX_TRANSACTIONS_PER_BLOCK  = 5000
BLOCK_TIME_TARGET_SEC       = 60              # 1 minute
DEFAULT_PORT                = 19656

================================================================================
PART III: DATA STRUCTURES
================================================================================

# ==============================================================================
# 3.1 PRIMITIVE TYPES
# ==============================================================================

# All multi-byte integers are BIG-ENDIAN unless noted

type u8   = unsigned 8-bit integer
type u16  = unsigned 16-bit integer
type u32  = unsigned 32-bit integer
type u64  = unsigned 64-bit integer
type i32  = signed 32-bit integer
type i64  = signed 64-bit integer
type f64  = 64-bit IEEE 754 float

type bytes[N] = fixed-size byte array of N bytes
type Vec<T>   = variable-length array of type T
type Map<K,V> = key-value mapping

# ==============================================================================
# 3.2 CRYPTOGRAPHIC TYPES
# ==============================================================================

struct Hash {
    data: bytes[32]                 # SHA3-256 output
}
# SIZE: 32 bytes
# SERIALIZATION: raw bytes

struct PublicKey {
    algorithm: u8                   # 0x01 = SPHINCS+
    data: bytes[32]                 # Key material
}
# SIZE: 33 bytes
# SERIALIZATION: algorithm || data

struct SecretKey {
    algorithm: u8                   # 0x01 = SPHINCS+
    data: bytes[64]                 # Key material
}
# SIZE: 65 bytes
# NOTE: Never transmitted over network

struct Signature {
    algorithm: u8                   # 0x01 = SPHINCS+
    data: bytes[17088]              # SPHINCS+-SHAKE-128f
}
# SIZE: 17089 bytes
# SERIALIZATION: algorithm || data

struct KeyPair {
    public: PublicKey
    secret: SecretKey
}

# ==============================================================================
# 3.3 LAYER 0: ATOMIC TIME STRUCTURES
# ==============================================================================

struct AtomicSource {
    region: u8                      # Region code (0x01-0x08)
    server_id: u8                   # Server within region (0-indexed)
    timestamp_ms: u64               # Milliseconds since Unix epoch
    rtt_ms: u16                     # Round-trip time in milliseconds
}
# SIZE: 12 bytes

struct AtomicTimeProof {
    timestamp_ms: u64               # Consensus timestamp
    source_count: u16               # Number of responding sources
    sources: Vec<AtomicSource>      # Individual responses
    median_drift_ms: i32            # Drift from median
    region_bitmap: u8               # Bitmask of responding regions
}
# SIZE: 14 + (12 * source_count) bytes

# Region bitmap:
#   bit 0: Europe
#   bit 1: Asia
#   bit 2: North America
#   bit 3: South America
#   bit 4: Africa
#   bit 5: Oceania
#   bit 6: Antarctica
#   bit 7: Arctic

# ==============================================================================
# 3.4 LAYER 1: VDF STRUCTURES
# ==============================================================================

struct VDFProof {
    seed: Hash                      # Input seed (SHA3-256 of inputs)
    output: Hash                    # Final VDF output
    iterations: u64                 # Number of sequential hashes
    checkpoint_count: u32           # Number of checkpoints
    checkpoints: Vec<Hash>          # STARK checkpoints
    stark_proof: bytes              # STARK proof (~50-200 KB)
}
# SIZE: 72 + (32 * checkpoint_count) + len(stark_proof) bytes

# ==============================================================================
# 3.5 LAYER 2: BITCOIN STRUCTURES
# ==============================================================================

struct BitcoinAnchor {
    height: u64                     # Block height
    block_hash: bytes[32]           # Block hash (little-endian as in Bitcoin)
    merkle_root: bytes[32]          # Merkle root
    timestamp: u64                  # Block timestamp (Unix seconds)
    difficulty: u64                 # Compact difficulty (nBits expanded)
    epoch: u32                      # Halving epoch (height / 210000)
    confirmations: u16              # Confirmations at anchor time
}
# SIZE: 90 bytes

# ==============================================================================
# 3.6 HEARTBEAT STRUCTURE
# ==============================================================================

struct Heartbeat {
    # Identity
    pubkey: PublicKey               # 33 bytes

    # Layer 0: Physical Time
    atomic_time: AtomicTimeProof    # Variable

    # Layer 1: Temporal Proof  
    vdf_proof: VDFProof             # Variable

    # Layer 2: Bitcoin Anchor
    btc_anchor: BitcoinAnchor       # 90 bytes

    # Metadata
    sequence: u64                   # Heartbeat sequence number
    version: u8                     # Heartbeat version

    # Signature
    signature: Signature            # 17089 bytes
}

fn heartbeat_id(hb: Heartbeat) -> Hash {
    return sha3_256(serialize_for_signing(hb))
}

# Serialization order for signing:
# version || pubkey || atomic_time || vdf_proof || btc_anchor || sequence

# ==============================================================================
# 3.7 TRANSACTION STRUCTURE
# ==============================================================================

struct Transaction {
    # Version
    version: u8                     # Transaction version

    # Parties
    sender: PublicKey               # 33 bytes
    receiver: PublicKey             # 33 bytes
    amount: u64                     # Atomic units (8 decimals)

    # Layer 0: Physical Time
    atomic_timestamp_ms: u64        # Atomic time at creation
    atomic_source_bitmap: u8        # Regions that responded

    # Layer 2: Bitcoin Reference
    btc_height: u64                 # Bitcoin block height
    btc_hash: bytes[32]             # Bitcoin block hash

    # Anti-spam PoW
    pow_difficulty: u8              # Difficulty in bits
    pow_nonce: bytes[8]             # Solution nonce
    pow_hash: Hash                  # Argon2id intermediate hash

    # Metadata
    nonce: u64                      # Replay protection (per-sender)
    epoch: u32                      # 10-minute epoch number
    memo: bytes[256]                # Optional memo (zero-padded)
    memo_length: u8                 # Actual memo length

    # Signature
    signature: Signature            # 17089 bytes
}

fn transaction_id(tx: Transaction) -> Hash {
    # Hash everything except signature
    return sha3_256(serialize_for_signing(tx))
}

# ==============================================================================
# 3.8 BLOCK STRUCTURE
# ==============================================================================

struct BlockHeader {
    version: u32                    # Protocol version
    height: u64                     # Block height
    parent_hash: Hash               # Previous block hash
    timestamp_ms: u64               # Atomic timestamp

    # Merkle roots
    heartbeats_root: Hash           # Merkle root of heartbeats
    transactions_root: Hash         # Merkle root of transactions
    state_root: Hash                # State trie root

    # Layer 2 anchor
    btc_anchor: BitcoinAnchor       # Bitcoin reference
}
# SIZE: 282 bytes

struct BlockSigner {
    pubkey: PublicKey               # Signer identity
    score_fixed: u64                # Score × 10^6 (fixed-point)
    signature: Signature            # Block signature
}

struct Block {
    header: BlockHeader
    heartbeats: Vec<Heartbeat>
    transactions: Vec<Transaction>
    signers: Vec<BlockSigner>
}

fn block_hash(block: Block) -> Hash {
    return sha3_256(serialize(block.header))
}

# ==============================================================================
# 3.9 STATE STRUCTURES
# ==============================================================================

struct AccountState {
    # Identity
    pubkey: PublicKey

    # Balance
    balance: u64                    # Token balance (atomic units)
    nonce: u64                      # Last transaction nonce

    # Heartbeat tracking
    total_heartbeats: u64           # Lifetime total
    epoch_heartbeats: u64           # Current epoch count
    last_hb_btc_height: u64         # BTC height of last heartbeat
    last_hb_atomic_ms: u64          # Atomic time of last heartbeat

    # Transaction tracking (for rate limiting)
    epoch_tx_count: u32             # Transactions this epoch
    current_second: u64             # Current second (atomic time / 1000)
    second_tx_count: u8             # Transactions in current second
}

struct GlobalState {
    # Current chain state
    chain_height: u64
    chain_tip_hash: Hash

    # Bitcoin state
    btc_height: u64
    btc_hash: Hash
    btc_epoch: u32                  # Current halving epoch

    # Network statistics
    total_supply: u64
    total_heartbeats: u64
    active_accounts: u64            # Accounts with recent activity

    # Account states
    accounts: Map<PublicKey, AccountState>
}

================================================================================
PART IV: LAYER 0 — PHYSICAL TIME (Global Atomic Nodes)
================================================================================

CONCEPT
-------
Layer 0 requires NO cryptographic proof. Atomic time is physical reality.

The key insight: time from cesium-133 atomic transitions at national metrology
laboratories is not a claim to be verified—it is a measurement to be observed.

ATOMIC TIME SOURCES (34 TOTAL)
------------------------------

REGION_EUROPE (8 sources):
┌────┬───────────┬─────────────────────────┬─────────────┬──────────────┐
│ ID │ Lab       │ NTP Server              │ Country     │ City         │
├────┼───────────┼─────────────────────────┼─────────────┼──────────────┤
│ 00 │ PTB       │ ptbtime1.ptb.de         │ Germany     │ Braunschweig │
│ 01 │ NPL       │ ntp1.npl.co.uk          │ UK          │ London       │
│ 02 │ LNE-SYRTE │ ntp.obspm.fr            │ France      │ Paris        │
│ 03 │ METAS     │ ntp.metas.ch            │ Switzerland │ Bern         │
│ 04 │ INRIM     │ ntp1.inrim.it           │ Italy       │ Turin        │
│ 05 │ VSL       │ ntp.vsl.nl              │ Netherlands │ Delft        │
│ 06 │ ROA       │ ntp.roa.es              │ Spain       │ Cádiz        │
│ 07 │ GUM       │ tempus1.gum.gov.pl      │ Poland      │ Warsaw       │
└────┴───────────┴─────────────────────────┴─────────────┴──────────────┘

REGION_ASIA (7 sources):
┌────┬───────────┬─────────────────────────┬─────────────┬──────────────┐
│ ID │ Lab       │ NTP Server              │ Country     │ City         │
├────┼───────────┼─────────────────────────┼─────────────┼──────────────┤
│ 00 │ NICT      │ ntp.nict.jp             │ Japan       │ Tokyo        │
│ 01 │ NIM       │ ntp.nim.ac.cn           │ China       │ Beijing      │
│ 02 │ KRISS     │ time.kriss.re.kr        │ S. Korea    │ Daejeon      │
│ 03 │ NPLI      │ time.nplindia.org       │ India       │ New Delhi    │
│ 04 │ VNIIFTRI  │ ntp2.vniiftri.ru        │ Russia      │ Moscow       │
│ 05 │ TL        │ time.stdtime.gov.tw     │ Taiwan      │ Taipei       │
│ 06 │ INPL      │ ntp.inpl.gov.il         │ Israel      │ Jerusalem    │
└────┴───────────┴─────────────────────────┴─────────────┴──────────────┘

REGION_NORTH_AMERICA (4 sources):
┌────┬───────────┬─────────────────────────┬─────────────┬──────────────┐
│ ID │ Lab       │ NTP Server              │ Country     │ City         │
├────┼───────────┼─────────────────────────┼─────────────┼──────────────┤
│ 00 │ NIST      │ time.nist.gov           │ USA         │ Boulder, CO  │
│ 01 │ USNO      │ tock.usno.navy.mil      │ USA         │ Washington   │
│ 02 │ NRC       │ time.nrc.ca             │ Canada      │ Ottawa       │
│ 03 │ CENAM     │ ntp.cenam.mx            │ Mexico      │ Querétaro    │
└────┴───────────┴─────────────────────────┴─────────────┴──────────────┘

REGION_SOUTH_AMERICA (3 sources):
┌────┬───────────┬─────────────────────────┬─────────────┬──────────────┐
│ ID │ Lab       │ NTP Server              │ Country     │ City         │
├────┼───────────┼─────────────────────────┼─────────────┼──────────────┤
│ 00 │ INMETRO   │ ntp.inmetro.gov.br      │ Brazil      │ Rio de Janeiro│
│ 01 │ INTI      │ ntp.inti.gob.ar         │ Argentina   │ Buenos Aires │
│ 02 │ INN       │ ntp.inn.cl              │ Chile       │ Santiago     │
└────┴───────────┴─────────────────────────┴─────────────┴──────────────┘

REGION_AFRICA (3 sources):
┌────┬───────────┬─────────────────────────┬─────────────┬──────────────┐
│ ID │ Lab       │ NTP Server              │ Country     │ City         │
├────┼───────────┼─────────────────────────┼─────────────┼──────────────┤
│ 00 │ NMISA     │ ntp.nmisa.org           │ S. Africa   │ Pretoria     │
│ 01 │ NIS       │ ntp.nis.sci.eg          │ Egypt       │ Cairo        │
│ 02 │ KEBS      │ ntp.kebs.org            │ Kenya       │ Nairobi      │
└────┴───────────┴─────────────────────────┴─────────────┴──────────────┘

REGION_OCEANIA (3 sources):
┌────┬───────────┬─────────────────────────┬─────────────┬──────────────┐
│ ID │ Lab       │ NTP Server              │ Country     │ City         │
├────┼───────────┼─────────────────────────┼─────────────┼──────────────┤
│ 00 │ NMI       │ time.nmi.gov.au         │ Australia   │ Sydney       │
│ 01 │ MSL       │ ntp.measurement.govt.nz │ New Zealand │ Wellington   │
│ 02 │ NMC       │ ntp.nmc.a-star.edu.sg   │ Singapore   │ Singapore    │
└────┴───────────┴─────────────────────────┴─────────────┴──────────────┘

REGION_ANTARCTICA (3 sources):
┌────┬───────────────┬─────────────────────────┬───────────┬──────────────┐
│ ID │ Station       │ NTP Server              │ Operator  │ Location     │
├────┼───────────────┼─────────────────────────┼───────────┼──────────────┤
│ 00 │ McMurdo       │ ntp.mcmurdo.usap.gov    │ USA/NSF   │ Ross Island  │
│ 01 │ Amundsen-Scott│ ntp.southpole.usap.gov  │ USA/NSF   │ South Pole   │
│ 02 │ Concordia     │ ntp.concordia.ipev.fr   │ FR/IT     │ Dome C       │
└────┴───────────────┴─────────────────────────┴───────────┴──────────────┘

REGION_ARCTIC (3 sources):
┌────┬───────────────┬─────────────────────────┬───────────┬──────────────┐
│ ID │ Station       │ NTP Server              │ Operator  │ Location     │
├────┼───────────────┼─────────────────────────┼───────────┼──────────────┤
│ 00 │ Ny-Ålesund    │ ntp.npolar.no           │ Norway    │ Svalbard     │
│ 01 │ Thule         │ ntp.thule.mil           │ USA/DK    │ Greenland    │
│ 02 │ Alert         │ ntp.alert.forces.gc.ca  │ Canada    │ Nunavut      │
└────┴───────────────┴─────────────────────────┴───────────┴──────────────┘

ATOMIC TIME QUERY ALGORITHM
---------------------------

fn query_atomic_time() -> Result<AtomicTimeProof, Error> {
    responses: Vec<AtomicSource> = []
    region_bitmap: u8 = 0

    for region in ALL_REGIONS:
        for server_id, server in ATOMIC_SOURCES[region]:
            for retry in 0..NTP_RETRY_COUNT:
                try:
                    t1 = local_monotonic_time_ms()
                    server_time = ntp_query(server.host, NTP_QUERY_TIMEOUT_MS)
                    t2 = local_monotonic_time_ms()

                    rtt = t2 - t1
                    # Adjust for network latency (assumes symmetric)
                    adjusted_time = server_time + (rtt / 2)

                    responses.push(AtomicSource {
                        region: region.code,
                        server_id: server_id,
                        timestamp_ms: adjusted_time,
                        rtt_ms: min(rtt, 65535)  # u16 cap
                    })

                    region_bitmap |= (1 << region.bit_position)
                    break  # Success, no more retries

                catch TimeoutError:
                    continue  # Try next retry
                catch NetworkError:
                    continue

    # Check consensus requirements
    if len(responses) < NTP_MIN_SOURCES_CONSENSUS:
        return Error::InsufficientSources(len(responses))

    regions_present = popcount(region_bitmap)
    if regions_present < NTP_MIN_REGIONS_TOTAL:
        return Error::InsufficientRegions(regions_present)

    # Verify per-continent minimums
    for region in INHABITED_CONTINENTS:  # Excludes poles
        count = count_sources_in_region(responses, region)
        if count < NTP_MIN_SOURCES_CONTINENT:
            return Error::InsufficientContinentSources(region, count)

    # Compute median timestamp
    timestamps = sort([r.timestamp_ms for r in responses])
    median_time = timestamps[len(timestamps) / 2]

    # Compute drift from median
    drifts = [r.timestamp_ms - median_time for r in responses]
    median_drift = sort(drifts)[len(drifts) / 2]

    if abs(median_drift) > NTP_MAX_DRIFT_MS:
        return Error::ExcessiveDrift(median_drift)

    return AtomicTimeProof {
        timestamp_ms: median_time,
        source_count: len(responses),
        sources: responses,
        median_drift_ms: median_drift,
        region_bitmap: region_bitmap
    }
}

ATOMIC TIME VALIDATION
----------------------

fn validate_atomic_time(proof: AtomicTimeProof) -> bool {
    # 1. Minimum total sources
    if proof.source_count < NTP_MIN_SOURCES_CONSENSUS:
        return false

    # 2. Verify region coverage
    regions_present = popcount(proof.region_bitmap)
    if regions_present < NTP_MIN_REGIONS_TOTAL:
        return false

    # 3. Per-continent verification
    region_counts = count_by_region(proof.sources)
    for region in [EUROPE, ASIA, NORTH_AMERICA, SOUTH_AMERICA, AFRICA, OCEANIA]:
        if region_counts[region] < NTP_MIN_SOURCES_CONTINENT:
            return false

    # 4. Polar regions (relaxed requirement)
    for region in [ANTARCTICA, ARCTIC]:
        if region_counts[region] < NTP_MIN_SOURCES_POLE:
            # Polar sources optional but preferred
            pass

    # 5. Verify drift is reasonable
    if abs(proof.median_drift_ms) > NTP_MAX_DRIFT_MS:
        return false

    # 6. Verify timestamp consistency
    timestamps = [s.timestamp_ms for s in proof.sources]
    if max(timestamps) - min(timestamps) > NTP_MAX_DRIFT_MS * 10:
        return false  # Sources too far apart

    return true
}

W-MSR CONSENSUS ALGORITHM
-------------------------

The Weighted-Mean Subsequence Reduced (W-MSR) algorithm is the primary consensus
mechanism for Layer 0. It provides optimal Byzantine fault tolerance while
maintaining high precision through weighted averaging.

ALGORITHM OVERVIEW:

1. Sort all n timestamps
2. Remove f smallest and f largest values (Byzantine trimming)
3. Compute weighted mean of remaining n-2f values
4. Weights based on source quality metrics

MATHEMATICAL FOUNDATION:

For Byzantine fault tolerance with f faulty sources:
- Require: n ≥ 3f + 1 total sources
- After removing 2f extreme values: n - 2f ≥ f + 1 honest sources remain
- Weighted mean of honest sources provides accurate consensus

With 34 sources and f=5: 34 ≥ 16 ✓ (3×5+1)

fn wmsr_consensus(
    sources: Vec<AtomicSource>,
    stratums: HashMap<(u8, u8), u8>,
    max_faults: u8 = 5
) -> (i64, WMSRDiagnostics) {

    n = len(sources)
    min_required = 3 * max_faults + 1

    if n < min_required:
        return fallback_to_median(sources)

    # Step 1: Compute weights for each source
    weighted_sources = []
    for source in sources:
        weight = compute_weight(source, stratums[source.key])
        weighted_sources.push((source, weight))

    # Step 2: Sort by timestamp
    weighted_sources.sort_by(|a, b| a.0.timestamp_ms.cmp(b.0.timestamp_ms))

    # Step 3: Remove f smallest and f largest (W-MSR core step)
    trimmed = weighted_sources[max_faults..(n - max_faults)]

    # Step 4: Compute weighted mean
    total_weight = sum(ws.1 for ws in trimmed)
    weighted_sum = sum(ws.0.timestamp_ms * ws.1 for ws in trimmed)
    consensus_ts = weighted_sum / total_weight

    return (consensus_ts, diagnostics)
}

WEIGHT COMPUTATION:

fn compute_weight(source: AtomicSource, stratum: u8) -> f64 {
    # Stratum weight: favor atomic clocks (stratum 1)
    stratum_weight = match stratum {
        1 => 1.0,    # Primary reference (atomic clock)
        2 => 0.8,    # Secondary reference
        3 => 0.6,    # Tertiary reference
        _ => 0.4     # Lower quality
    }

    # RTT weight: lower latency = higher weight
    rtt_normalized = min(source.rtt_ms, 500) / 500
    rtt_weight = 1.0 - (rtt_normalized * 0.5)  # Range: [0.5, 1.0]

    # Region weight: boost underrepresented regions
    region_weight = expected_per_region / actual_count_in_region
    region_weight = min(region_weight, 2.0)  # Cap at 2x

    # Combined weight (geometric mean)
    return (stratum_weight * rtt_weight * region_weight) ** (1/3)
}

FALLBACK CHAIN:

If W-MSR requirements cannot be met, the system falls back gracefully:

1. Full W-MSR (f=5): n ≥ 16 sources required
2. Reduced W-MSR (f=4): n ≥ 13 sources required
3. Reduced W-MSR (f=3): n ≥ 10 sources required
4. Reduced W-MSR (f=2): n ≥ 7 sources required
5. Reduced W-MSR (f=1): n ≥ 4 sources required
6. MAD-filtered median: Reject outliers > 3σ, then median
7. Simple median: Last resort

EDGE CASE HANDLING
------------------

1. OUTLIER REJECTION (MAD-based)
   Method: Median Absolute Deviation
   Formula: MAD = median(|Xi - median(X)|)
   Outlier if: |Xi - median| > 3.0 × MAD × 1.4826
   Note: 1.4826 is consistency constant for normal distribution

2. RTT COMPENSATION
   Method: timestamp + RTT/2
   Assumption: Symmetric network latency
   Threshold: Skip compensation if RTT > 500ms (asymmetry likely)

3. BYZANTINE FAULT TOLERANCE
   Algorithm: W-MSR (Weighted-Mean Subsequence Reduced)
   Requirement: n ≥ 3f+1 sources
   Default: f=5 (tolerates 5 Byzantine sources)
   Fallback: Graceful degradation to lower f values

4. STRATUM VALIDATION
   Accept: Stratum 1 (atomic clock), 2, 3
   Reject: Stratum 0 (KoD), 4+ (too far from atomic)

5. KISS-OF-DEATH (KoD) HANDLING
   Codes: DENY (permanent ban), RSTR (restricted), RATE (rate limited)
   Action: Add to blacklist, skip in future queries
   Recovery: Blacklist cleared on node restart

6. LEAP SECOND DETECTION
   Indicators: LI=0 (none), LI=1 (+1s), LI=2 (-1s), LI=3 (unsync)
   Alarm: >33% sources with LI=3 triggers warning
   Action: Consensus on leap indicator if >50% agree

7. WEIGHTED CONSENSUS
   Factors: stratum (quality), RTT (latency), region (diversity)
   Method: Geometric mean of factor weights
   Purpose: Higher quality sources have more influence

DIAGNOSTICS OUTPUT:

WMSRDiagnostics {
    algorithm: "W-MSR" | "MAD-median" | "simple-median",
    total_sources: u32,
    trimmed_sources: u32,
    removed_low: u32,
    removed_high: u32,
    total_weight: f64,
    variance_ms: f64,
    std_dev_ms: f64,
    confidence_interval_ms: f64,  # 95% CI
    spread_ms: i64,               # max - min
}

================================================================================
PART V: LAYER 1 — TEMPORAL PROOF (ATC Network Nodes)
================================================================================

VERIFIABLE DELAY FUNCTION (VDF)
-------------------------------

The VDF provides cryptographic proof that real time has elapsed.

Properties:
- Sequential: Output depends on all previous computations
- Non-parallelizable: 10,000 CPUs = 1 CPU in elapsed time
- Verifiable: O(log n) verification via STARK proofs
- Quantum-resistant: Hash-based construction

VDF COMPUTATION
---------------

fn compute_vdf(seed: bytes, iterations: u64) -> (Hash, VDFProof) {
    """
    Compute SHAKE256-based VDF.

    Input: seed (any length), iterations (required sequential steps)
    Output: (final_hash, proof)

    Time complexity: O(iterations)
    Space complexity: O(iterations / VDF_CHECKPOINT_INTERVAL) for checkpoints
    """

    # Initialize state with domain separation
    initial_state = sha3_256(VDF_SEED_PREFIX || seed)
    state = initial_state
    checkpoints = [initial_state]

    # Sequential hashing - CANNOT be parallelized
    for i in 0..iterations:
        state = shake256(state, VDF_OUTPUT_BYTES)

        # Store checkpoints for STARK proof
        if (i + 1) % VDF_CHECKPOINT_INTERVAL == 0:
            checkpoints.push(state)

    # Final checkpoint
    if iterations % VDF_CHECKPOINT_INTERVAL != 0:
        checkpoints.push(state)

    # Generate STARK proof
    stark_proof = generate_stark_proof(
        function: "SHAKE256",
        input: initial_state,
        output: state,
        iterations: iterations,
        checkpoints: checkpoints
    )

    proof = VDFProof {
        seed: sha3_256(seed),
        output: state,
        iterations: iterations,
        checkpoint_count: len(checkpoints),
        checkpoints: checkpoints,
        stark_proof: stark_proof
    }

    return (state, proof)
}

VDF VERIFICATION
----------------

fn verify_vdf(proof: VDFProof) -> bool {
    """
    Verify VDF proof in O(log n) time using STARK.
    """

    # Verify checkpoint count is correct
    expected_checkpoints = (proof.iterations / VDF_CHECKPOINT_INTERVAL) + 1
    if proof.checkpoint_count != expected_checkpoints:
        return false

    # Verify first checkpoint matches seed
    expected_initial = sha3_256(VDF_SEED_PREFIX || proof.seed)
    if proof.checkpoints[0] != expected_initial:
        return false

    # Verify last checkpoint matches output
    if proof.checkpoints[proof.checkpoint_count - 1] != proof.output:
        return false

    # Verify STARK proof
    return stark_verify(
        function: "SHAKE256",
        claimed_input: proof.checkpoints[0],
        claimed_output: proof.output,
        claimed_iterations: proof.iterations,
        checkpoints: proof.checkpoints,
        proof: proof.stark_proof
    )
}

VDF SEED GENERATION
-------------------

fn generate_vdf_seed(pubkey: PublicKey, btc: BitcoinAnchor) -> bytes {
    """
    Generate VDF seed deterministically from identity and Bitcoin block.
    Cannot be predicted before Bitcoin block is mined.
    """

    return sha3_256(
        VDF_SEED_PREFIX ||
        pubkey.algorithm.to_bytes(1) ||
        pubkey.data ||
        btc.height.to_bytes(8, BE) ||
        btc.block_hash ||
        btc.epoch.to_bytes(4, BE)
    )
}

ADAPTIVE VDF DIFFICULTY
-----------------------

fn get_vdf_iterations(pubkey: PublicKey, state: GlobalState) -> u64 {
    """
    Calculate required VDF iterations based on participation.
    More heartbeats = longer VDF required.
    """

    account = state.accounts.get(pubkey)
    if account is None:
        return VDF_BASE_ITERATIONS

    epoch_hb = account.epoch_heartbeats

    # Difficulty doubles every VDF_DIFFICULTY_SCALE heartbeats
    multiplier = 2.0 ** (epoch_hb / VDF_DIFFICULTY_SCALE)
    iterations = VDF_BASE_ITERATIONS * multiplier

    return min(u64(iterations), VDF_MAX_ITERATIONS)
}

================================================================================
PART VI: LAYER 2 — FINALIZATION (Bitcoin Anchor)
================================================================================

Bitcoin provides absolute finalization. Its 15+ years of accumulated proof of
work represents the most secure timestamping mechanism ever created.

BITCOIN QUERY
-------------

fn query_bitcoin() -> Result<BitcoinAnchor, Error> {
    """
    Query Bitcoin state from multiple APIs for consensus.
    """

    results: Vec<BitcoinBlockInfo> = []

    for api in BTC_API_ENDPOINTS:
        try:
            # Get latest block
            tip = http_get(f"{api}/blocks/tip", timeout=5000)

            results.push(BitcoinBlockInfo {
                height: tip.height,
                hash: bytes.fromhex(tip.id),
                merkle_root: bytes.fromhex(tip.merkle_root),
                timestamp: tip.timestamp,
                difficulty: tip.difficulty
            })
        catch:
            continue

    if len(results) < BTC_API_CONSENSUS_MIN:
        return Error::InsufficientBitcoinSources

    # Find consensus (majority on height+hash)
    votes: Map<(u64, bytes), u32> = {}
    for r in results:
        key = (r.height, r.hash)
        votes[key] = votes.get(key, 0) + 1

    best_key = max(votes.keys(), key=lambda k: votes[k])
    if votes[best_key] < BTC_API_CONSENSUS_MIN:
        return Error::NoBitcoinConsensus

    height, block_hash = best_key

    # Find matching result for full data
    for r in results:
        if r.height == height and r.hash == block_hash:
            return BitcoinAnchor {
                height: height,
                block_hash: block_hash,
                merkle_root: r.merkle_root,
                timestamp: r.timestamp,
                difficulty: r.difficulty,
                epoch: height / BTC_HALVING_INTERVAL,
                confirmations: 0
            }

    return Error::BitcoinDataInconsistent
}

BITCOIN VALIDATION
------------------

fn validate_bitcoin_anchor(anchor: BitcoinAnchor, current: BitcoinAnchor) -> bool {
    # 1. Block must exist (query API)
    block_data = query_bitcoin_block(anchor.height)
    if block_data is None:
        return false

    # 2. Hash must match
    if block_data.hash != anchor.block_hash:
        return false

    # 3. Not too far behind tip
    if current.height - anchor.height > BTC_MAX_DRIFT_BLOCKS:
        return false

    # 4. Epoch must be correct
    expected_epoch = anchor.height / BTC_HALVING_INTERVAL
    if anchor.epoch != expected_epoch:
        return false

    # 5. Timestamp must be reasonable
    if anchor.timestamp > current.timestamp + 7200:  # 2 hour future tolerance
        return false

    return true
}

EPOCH MANAGEMENT
----------------

fn get_current_epoch(btc_height: u64) -> u32 {
    return btc_height / BTC_HALVING_INTERVAL
}

fn is_epoch_boundary(btc_height: u64) -> bool {
    return btc_height % BTC_HALVING_INTERVAL == 0
}

fn get_epoch_start_height(epoch: u32) -> u64 {
    return epoch * BTC_HALVING_INTERVAL
}

fn get_epoch_end_height(epoch: u32) -> u64 {
    return (epoch + 1) * BTC_HALVING_INTERVAL - 1
}

================================================================================
PART VII: HEARTBEAT SYSTEM
================================================================================

A heartbeat is proof of temporal presence across all three layers.

HEARTBEAT CREATION
------------------

fn create_heartbeat(keypair: KeyPair, state: GlobalState) -> Result<Heartbeat, Error> {
    # Layer 0: Query physical time
    atomic_time = query_atomic_time()?

    # Layer 2: Query Bitcoin (needed for VDF seed)
    btc_anchor = query_bitcoin()?

    # Layer 1: Compute VDF
    vdf_seed = generate_vdf_seed(keypair.public, btc_anchor)
    iterations = get_vdf_iterations(keypair.public, state)
    vdf_output, vdf_proof = compute_vdf(vdf_seed, iterations)

    # Get sequence number
    account = state.accounts.get(keypair.public)
    sequence = if account then account.total_heartbeats + 1 else 1

    # Create unsigned heartbeat
    hb = Heartbeat {
        pubkey: keypair.public,
        atomic_time: atomic_time,
        vdf_proof: vdf_proof,
        btc_anchor: btc_anchor,
        sequence: sequence,
        version: PROTOCOL_VERSION,
        signature: empty_signature()
    }

    # Sign
    message = serialize_heartbeat_for_signing(hb)
    hb.signature = sphincs_sign(keypair.secret, message)

    return hb
}

HEARTBEAT VALIDATION
--------------------

fn validate_heartbeat(hb: Heartbeat, state: GlobalState) -> Result<(), Error> {
    # === LAYER 0: PHYSICAL TIME ===

    if not validate_atomic_time(hb.atomic_time):
        return Error::InvalidAtomicTime

    # === LAYER 1: TEMPORAL PROOF ===

    # Verify VDF seed
    expected_seed = generate_vdf_seed(hb.pubkey, hb.btc_anchor)
    if hb.vdf_proof.seed != sha3_256(expected_seed):
        return Error::VDFSeedMismatch

    # Verify iterations meet minimum
    required = get_vdf_iterations(hb.pubkey, state)
    if hb.vdf_proof.iterations < required:
        return Error::InsufficientVDFIterations

    # Verify VDF proof
    if not verify_vdf(hb.vdf_proof):
        return Error::InvalidVDFProof

    # === LAYER 2: BITCOIN ===

    current_btc = query_bitcoin()?
    if not validate_bitcoin_anchor(hb.btc_anchor, current_btc):
        return Error::InvalidBitcoinAnchor

    # === CROSS-LAYER CONSISTENCY ===

    # Atomic time should be close to BTC block time
    btc_time_ms = hb.btc_anchor.timestamp * 1000
    time_diff = abs(hb.atomic_time.timestamp_ms - btc_time_ms)
    if time_diff > BTC_BLOCK_TIME_SECONDS * 2 * 1000:
        return Error::CrossLayerTimeInconsistent

    # === SEQUENCE ===

    account = state.accounts.get(hb.pubkey)
    expected_seq = if account then account.total_heartbeats + 1 else 1
    if hb.sequence != expected_seq:
        return Error::InvalidSequence

    # === SIGNATURE ===

    message = serialize_heartbeat_for_signing(hb)
    if not sphincs_verify(hb.pubkey, message, hb.signature):
        return Error::InvalidSignature

    return Ok(())
}

HEARTBEAT SERIALIZATION
-----------------------

fn serialize_heartbeat_for_signing(hb: Heartbeat) -> bytes {
    # Everything except signature, in deterministic order
    return concat([
        hb.version.to_bytes(1),
        hb.pubkey.algorithm.to_bytes(1),
        hb.pubkey.data,
        serialize_atomic_time(hb.atomic_time),
        serialize_vdf_proof(hb.vdf_proof),
        serialize_bitcoin_anchor(hb.btc_anchor),
        hb.sequence.to_bytes(8, BE)
    ])
}

================================================================================
PART VIII: TRANSACTION SYSTEM
================================================================================

TRANSACTION CREATION
--------------------

fn create_transaction(
    keypair: KeyPair,
    receiver: PublicKey,
    amount: u64,
    state: GlobalState,
    memo: bytes = []
) -> Result<Transaction, Error> {
    # Query time sources
    atomic_time = query_atomic_time()?
    btc = query_bitcoin()?

    # Get account state
    account = state.accounts.get(keypair.public)
    if account is None:
        return Error::AccountNotFound

    if account.balance < amount:
        return Error::InsufficientBalance

    nonce = account.nonce + 1
    epoch = atomic_time.timestamp_ms / (TX_EPOCH_DURATION_SEC * 1000)

    # Calculate PoW difficulty
    difficulty = get_personal_difficulty(keypair.public, state, atomic_time)

    # Create unsigned transaction
    tx = Transaction {
        version: PROTOCOL_VERSION,
        sender: keypair.public,
        receiver: receiver,
        amount: amount,
        atomic_timestamp_ms: atomic_time.timestamp_ms,
        atomic_source_bitmap: atomic_time.region_bitmap,
        btc_height: btc.height,
        btc_hash: btc.block_hash,
        pow_difficulty: difficulty,
        pow_nonce: zeros(8),
        pow_hash: empty_hash(),
        nonce: nonce,
        epoch: epoch,
        memo: pad_to_256(memo),
        memo_length: len(memo),
        signature: empty_signature()
    }

    # Compute PoW
    tx.pow_hash, tx.pow_nonce = compute_transaction_pow(tx, difficulty)

    # Sign
    message = serialize_tx_for_signing(tx)
    tx.signature = sphincs_sign(keypair.secret, message)

    return tx
}

TRANSACTION VALIDATION
----------------------

fn validate_transaction(tx: Transaction, state: GlobalState) -> Result<(), Error> {
    # === BASIC CHECKS ===

    if tx.amount == 0:
        return Error::ZeroAmount

    sender_account = state.accounts.get(tx.sender)
    if sender_account is None:
        return Error::SenderNotFound

    if sender_account.balance < tx.amount:
        return Error::InsufficientBalance

    # === REPLAY PROTECTION ===

    if tx.nonce != sender_account.nonce + 1:
        return Error::InvalidNonce

    # === LAYER 0: TIME CHECK ===

    current_time = query_atomic_time()?
    time_diff = abs(tx.atomic_timestamp_ms - current_time.timestamp_ms)
    if time_diff > TX_EPOCH_DURATION_SEC * 1000:  # 10 minutes
        return Error::TransactionExpired

    # === LAYER 2: BITCOIN CHECK ===

    current_btc = query_bitcoin()?
    if current_btc.height - tx.btc_height > BTC_MAX_DRIFT_BLOCKS:
        return Error::BitcoinAnchorTooOld

    # === PERSONAL POW ===

    expected_difficulty = get_personal_difficulty(tx.sender, state, tx.atomic_timestamp_ms)
    if tx.pow_difficulty < expected_difficulty:
        return Error::InsufficientPOWDifficulty

    if not verify_transaction_pow(tx):
        return Error::InvalidPOW

    # === SIGNATURE ===

    message = serialize_tx_for_signing(tx)
    if not sphincs_verify(tx.sender, message, tx.signature):
        return Error::InvalidSignature

    return Ok(())
}

================================================================================
PART IX: PERSONAL RATE LIMITING
================================================================================

PRINCIPLE: "Your spam is your problem, not the network's."

DIFFICULTY CALCULATION
----------------------

fn get_personal_difficulty(
    sender: PublicKey,
    state: GlobalState,
    current_time_ms: u64
) -> u8 {
    account = state.accounts.get(sender)
    if account is None:
        return POW_BASE_DIFFICULTY_BITS

    current_epoch = current_time_ms / (TX_EPOCH_DURATION_SEC * 1000)
    current_second = current_time_ms / 1000

    # === EPOCH PENALTY ===
    # +2 bits per transaction beyond free tier

    epoch_penalty = 0
    if account.epoch_tx_count >= TX_FREE_PER_EPOCH:
        excess = account.epoch_tx_count - TX_FREE_PER_EPOCH + 1
        epoch_penalty = excess * POW_EXCESS_PENALTY_BITS

    # === BURST PENALTY ===
    # +4 bits per transaction in same second

    burst_penalty = 0
    if account.current_second == current_second:
        burst_penalty = account.second_tx_count * POW_BURST_PENALTY_BITS

    # === TOTAL ===

    total = POW_BASE_DIFFICULTY_BITS + epoch_penalty + burst_penalty
    return min(total, POW_MAX_DIFFICULTY_BITS)
}

PERSONAL POW COMPUTATION (ASIC-RESISTANT)
-----------------------------------------

fn compute_transaction_pow(tx: Transaction, difficulty: u8) -> (Hash, bytes[8]) {
    """
    Two-stage ASIC-resistant PoW:
    Stage 1: Argon2id (memory-hard, 64 MB)
    Stage 2: RandomX (random execution, CPU-optimized)
    """

    # Prepare transaction data (without PoW fields)
    tx_data = serialize_tx_for_pow(tx)

    # Generate salt from sender + nonce
    salt = sha3_256(tx.sender.data || tx.nonce.to_bytes(8, BE))

    # Stage 1: Memory-hard hash
    argon_hash = argon2id(
        password: tx_data,
        salt: salt,
        time_cost: POW_TIME_COST,
        memory_cost: POW_MEMORY_COST_KB,
        parallelism: POW_PARALLELISM,
        output_length: 32
    )

    # Stage 2: RandomX mining
    target = 2^256 / 2^difficulty  # Equivalent to 2^(256-difficulty)
    nonce: u64 = 0

    while true:
        input_data = argon_hash || nonce.to_bytes(8, BE)
        hash_output = randomx_hash(input_data)

        if bytes_to_uint256(hash_output) < target:
            return (Hash(argon_hash), nonce.to_bytes(8, BE))

        nonce += 1

        if nonce == MAX_U64:
            return Error::POWExhausted
}

POW VERIFICATION
----------------

fn verify_transaction_pow(tx: Transaction) -> bool {
    # Recompute Argon2id
    tx_data = serialize_tx_for_pow(tx)
    salt = sha3_256(tx.sender.data || tx.nonce.to_bytes(8, BE))

    expected_argon = argon2id(
        password: tx_data,
        salt: salt,
        time_cost: POW_TIME_COST,
        memory_cost: POW_MEMORY_COST_KB,
        parallelism: POW_PARALLELISM,
        output_length: 32
    )

    if tx.pow_hash.data != expected_argon:
        return false

    # Verify RandomX
    input_data = tx.pow_hash.data || tx.pow_nonce
    hash_output = randomx_hash(input_data)

    target = 2^256 / 2^tx.pow_difficulty
    return bytes_to_uint256(hash_output) < target
}

DIFFICULTY TABLE
----------------

┌──────────────┬──────────┬────────────┬──────────────┬──────────┐
│ Behavior     │ TX/Epoch │ Difficulty │ Est. Time    │ Status   │
├──────────────┼──────────┼────────────┼──────────────┼──────────┤
│ Normal       │ 1-10     │ 16 bits    │ ~65 ms       │ FREE     │
│ Active       │ 11       │ 18 bits    │ ~260 ms      │ +1 excess│
│ Active       │ 12       │ 20 bits    │ ~1 sec       │ +2 excess│
│ Active       │ 13       │ 22 bits    │ ~4 sec       │ +3 excess│
│ Active       │ 14       │ 24 bits    │ ~16 sec      │ +4 excess│
│ Spam         │ 15       │ 26 bits    │ ~1 min       │ +5 excess│
│ Spam         │ 16       │ 28 bits    │ ~4 min       │ +6 excess│
│ Spam         │ 17       │ 30 bits    │ ~17 min      │ +7 excess│
│ Heavy spam   │ 18+      │ 32 bits    │ ~18 hours    │ MAX      │
└──────────────┴──────────┴────────────┴──────────────┴──────────┘

Burst penalty (same second): +4 bits per additional transaction

================================================================================
PART X: SCORE AND CONSENSUS
================================================================================

SCORE CALCULATION
-----------------

fn compute_score(pubkey: PublicKey, state: GlobalState) -> f64 {
    account = state.accounts.get(pubkey)
    if account is None:
        return 0.0

    return sqrt(account.epoch_heartbeats)
}

ACTIVITY CHECK
--------------

fn is_active(pubkey: PublicKey, state: GlobalState) -> bool {
    account = state.accounts.get(pubkey)
    if account is None:
        return false

    # Must have heartbeat within activity window
    window_start = state.btc_height - ACTIVITY_WINDOW_BLOCKS
    return account.last_hb_btc_height >= window_start
}

EFFECTIVE SCORE
---------------

fn effective_score(pubkey: PublicKey, state: GlobalState) -> f64 {
    if not is_active(pubkey, state):
        return 0.0

    return compute_score(pubkey, state)
}

CHAIN WEIGHT
------------

fn chain_weight(chain: Vec<Block>, state: GlobalState) -> f64 {
    weight = 0.0
    signer_heights: Map<PublicKey, Set<u64>> = {}

    for block in chain:
        for signer in block.signers:
            # Detect equivocation (signing multiple blocks at same height)
            if block.header.height in signer_heights.get(signer.pubkey, {}):
                continue  # Skip equivocating signer

            signer_heights.entry(signer.pubkey).or_default().insert(block.header.height)

            # Add score (convert from fixed-point)
            weight += signer.score_fixed / 1_000_000.0

    return weight
}

FORK CHOICE RULE
----------------

fn select_best_chain(chains: Vec<Vec<Block>>, state: GlobalState) -> Vec<Block> {
    return max(chains, key=lambda c: chain_weight(c, state))
}

EPOCH RESET
-----------

fn handle_epoch_change(state: GlobalState, new_epoch: u32) -> GlobalState {
    if not EPOCH_RESET_ON_HALVING:
        return state

    # Reset epoch heartbeats for all accounts
    for pubkey, account in state.accounts:
        account.epoch_heartbeats = 0
        account.epoch_tx_count = 0

    state.btc_epoch = new_epoch
    return state
}

================================================================================
PART XI: BLOCK STRUCTURE
================================================================================

BLOCK CREATION
--------------

fn create_block(
    parent: Block,
    heartbeats: Vec<Heartbeat>,
    transactions: Vec<Transaction>,
    state: GlobalState
) -> Result<Block, Error> {
    # Validate limits
    if len(heartbeats) > MAX_HEARTBEATS_PER_BLOCK:
        return Error::TooManyHeartbeats

    if len(transactions) > MAX_TRANSACTIONS_PER_BLOCK:
        return Error::TooManyTransactions

    # Query time sources
    atomic_time = query_atomic_time()?
    btc_anchor = query_bitcoin()?

    # Compute Merkle roots
    hb_hashes = [heartbeat_id(hb) for hb in heartbeats]
    tx_hashes = [transaction_id(tx) for tx in transactions]

    hb_root = merkle_root(hb_hashes)
    tx_root = merkle_root(tx_hashes)

    # Apply changes to compute state root
    new_state = apply_block(state, heartbeats, transactions)
    state_root = compute_state_root(new_state)

    header = BlockHeader {
        version: PROTOCOL_VERSION,
        height: parent.header.height + 1,
        parent_hash: block_hash(parent),
        timestamp_ms: atomic_time.timestamp_ms,
        heartbeats_root: hb_root,
        transactions_root: tx_root,
        state_root: state_root,
        btc_anchor: btc_anchor
    }

    return Block {
        header: header,
        heartbeats: heartbeats,
        transactions: transactions,
        signers: []  # Added via sign_block
    }
}

BLOCK SIGNING
-------------

fn sign_block(block: Block, keypair: KeyPair, state: GlobalState) -> BlockSigner {
    score = effective_score(keypair.public, state)
    score_fixed = u64(score * 1_000_000)  # 6 decimal places

    message = block_hash(block).data || score_fixed.to_bytes(8, BE)
    signature = sphincs_sign(keypair.secret, message)

    return BlockSigner {
        pubkey: keypair.public,
        score_fixed: score_fixed,
        signature: signature
    }
}

BLOCK VALIDATION
----------------

fn validate_block(block: Block, parent: Block, state: GlobalState) -> Result<(), Error> {
    # === HEADER ===

    if block.header.version != PROTOCOL_VERSION:
        return Error::InvalidVersion

    if block.header.height != parent.header.height + 1:
        return Error::InvalidHeight

    if block.header.parent_hash != block_hash(parent):
        return Error::InvalidParentHash

    # === SIZE LIMITS ===

    if serialize_size(block) > MAX_BLOCK_SIZE_BYTES:
        return Error::BlockTooLarge

    if len(block.heartbeats) > MAX_HEARTBEATS_PER_BLOCK:
        return Error::TooManyHeartbeats

    if len(block.transactions) > MAX_TRANSACTIONS_PER_BLOCK:
        return Error::TooManyTransactions

    # === BITCOIN ANCHOR ===

    if not validate_bitcoin_anchor(block.header.btc_anchor, state.btc_height):
        return Error::InvalidBitcoinAnchor

    # === CONTENT VALIDATION ===

    for hb in block.heartbeats:
        validate_heartbeat(hb, state)?

    for tx in block.transactions:
        validate_transaction(tx, state)?

    # === MERKLE ROOTS ===

    expected_hb_root = merkle_root([heartbeat_id(hb) for hb in block.heartbeats])
    if block.header.heartbeats_root != expected_hb_root:
        return Error::InvalidHeartbeatsRoot

    expected_tx_root = merkle_root([transaction_id(tx) for tx in block.transactions])
    if block.header.transactions_root != expected_tx_root:
        return Error::InvalidTransactionsRoot

    # === STATE ROOT ===

    new_state = apply_block(state, block.heartbeats, block.transactions)
    expected_state_root = compute_state_root(new_state)
    if block.header.state_root != expected_state_root:
        return Error::InvalidStateRoot

    # === SIGNERS ===

    for signer in block.signers:
        expected_score = u64(effective_score(signer.pubkey, state) * 1_000_000)
        if signer.score_fixed != expected_score:
            return Error::InvalidSignerScore

        message = block_hash(block).data || signer.score_fixed.to_bytes(8, BE)
        if not sphincs_verify(signer.pubkey, message, signer.signature):
            return Error::InvalidSignerSignature

    return Ok(())
}

================================================================================
PART XII: CRYPTOGRAPHIC PRIMITIVES
================================================================================

HASH FUNCTIONS
--------------

fn sha3_256(data: bytes) -> bytes[32]:
    """SHA3-256 per NIST FIPS 202"""
    return Keccak-1600(data, capacity=512, output_length=256)

fn shake256(data: bytes, output_length: int) -> bytes:
    """SHAKE256 extendable output function per NIST FIPS 202"""
    return Keccak-1600(data, capacity=512, output_length=output_length*8)

SIGNATURES (SPHINCS+)
---------------------

fn sphincs_keygen() -> (PublicKey, SecretKey):
    """Generate SPHINCS+-SHAKE-128f keypair per NIST FIPS 205"""
    (sk, pk) = SPHINCS_SHAKE_128f.keygen()
    return (
        PublicKey { algorithm: 0x01, data: pk },
        SecretKey { algorithm: 0x01, data: sk }
    )

fn sphincs_sign(sk: SecretKey, message: bytes) -> Signature:
    sig = SPHINCS_SHAKE_128f.sign(message, sk.data)
    return Signature { algorithm: 0x01, data: sig }

fn sphincs_verify(pk: PublicKey, message: bytes, sig: Signature) -> bool:
    return SPHINCS_SHAKE_128f.verify(message, sig.data, pk.data)

KEY EXCHANGE (ML-KEM)
---------------------

fn mlkem_keygen() -> (bytes[800], bytes[1632]):
    """ML-KEM-768 key generation per NIST FIPS 203"""
    return ML_KEM_768.keygen()

fn mlkem_encapsulate(pk: bytes[800]) -> (bytes[1088], bytes[32]):
    """Returns (ciphertext, shared_secret)"""
    return ML_KEM_768.encapsulate(pk)

fn mlkem_decapsulate(sk: bytes[1632], ct: bytes[1088]) -> bytes[32]:
    """Returns shared_secret"""
    return ML_KEM_768.decapsulate(ct, sk)

MERKLE TREE
-----------

fn merkle_root(hashes: Vec<Hash>) -> Hash:
    if len(hashes) == 0:
        return Hash { data: zeros(32) }

    if len(hashes) == 1:
        return hashes[0]

    # Pad to power of 2
    while not is_power_of_two(len(hashes)):
        hashes.push(hashes[len(hashes) - 1])

    # Build tree bottom-up
    while len(hashes) > 1:
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i].data || hashes[i + 1].data
            next_level.push(Hash { data: sha3_256(combined) })
        hashes = next_level

    return hashes[0]

ARGON2ID
--------

fn argon2id(
    password: bytes,
    salt: bytes,
    time_cost: u32,
    memory_cost: u32,  # KB
    parallelism: u32,
    output_length: u32
) -> bytes:
    """Argon2id per RFC 9106"""
    return Argon2.hash(
        type: Argon2id,
        password: password,
        salt: salt,
        t_cost: time_cost,
        m_cost: memory_cost,
        p_cost: parallelism,
        output_len: output_length
    )

RANDOMX
-------

fn randomx_hash(data: bytes) -> bytes[32]:
    """RandomX hash (Monero PoW algorithm)"""
    # Initialize VM with current epoch key
    vm = RandomX.create_vm(flags=RANDOMX_FLAG_FULL_MEM)
    return vm.hash(data)

================================================================================
PART XIII: NETWORK PROTOCOL
================================================================================

MESSAGE FORMAT
--------------

struct Message {
    magic: bytes[4]     # Network ID
    type: u8            # Message type
    length: u32         # Payload length
    checksum: bytes[4]  # SHA3-256(payload)[0:4]
    payload: bytes      # Variable
}

MESSAGE TYPES
-------------

0x01  HELLO          Initial handshake
0x02  HELLO_ACK      Handshake response
0x03  PING           Keep-alive
0x04  PONG           Keep-alive response

0x10  GET_BLOCKS     Request blocks by height/hash
0x11  BLOCKS         Block response
0x12  GET_HEADERS    Request headers only
0x13  HEADERS        Headers response

0x20  ANNOUNCE_HB    Announce new heartbeat
0x21  ANNOUNCE_TX    Announce new transaction
0x22  ANNOUNCE_BLOCK Announce new block

0x30  GET_PEERS      Request peer list
0x31  PEERS          Peer list response

0x40  GET_STATE      Request state snapshot
0x41  STATE          State response

HANDSHAKE
---------

struct HelloMessage {
    version: u32
    network_id: u32
    best_height: u64
    best_hash: Hash
    btc_height: u64
    timestamp_ms: u64
    pubkey: PublicKey
    listen_port: u16
    user_agent: bytes[64]
}

================================================================================
PART XIV: VALIDATION RULES
================================================================================

HEARTBEAT VALIDATION CHECKLIST
------------------------------

[ ] Version matches protocol version
[ ] Pubkey is valid SPHINCS+ public key
[ ] Atomic time proof has >= 18 sources
[ ] Atomic time covers >= 5 regions
[ ] Atomic time drift <= 1000ms
[ ] VDF seed = SHA3(prefix || pubkey || btc_height || btc_hash || epoch)
[ ] VDF iterations >= get_vdf_iterations(pubkey, state)
[ ] VDF STARK proof verifies
[ ] Bitcoin height within 6 blocks of tip
[ ] Bitcoin hash matches known block
[ ] Bitcoin epoch matches height / 210000
[ ] Cross-layer: atomic_time within 20 minutes of btc_timestamp
[ ] Sequence = previous_sequence + 1
[ ] SPHINCS+ signature verifies

TRANSACTION VALIDATION CHECKLIST
--------------------------------

[ ] Version matches protocol version
[ ] Sender account exists
[ ] Sender balance >= amount
[ ] Amount > 0
[ ] Nonce = sender.nonce + 1
[ ] Atomic timestamp within 10 minutes of current
[ ] Bitcoin height within 6 blocks of tip
[ ] POW difficulty >= get_personal_difficulty(sender, state, timestamp)
[ ] Argon2id hash is correct
[ ] RandomX hash < target
[ ] SPHINCS+ signature verifies
[ ] Memo length <= 256

BLOCK VALIDATION CHECKLIST
--------------------------

[ ] Version matches protocol version
[ ] Height = parent.height + 1
[ ] Parent hash matches actual parent
[ ] Block size <= 4 MB
[ ] Heartbeat count <= 1000
[ ] Transaction count <= 5000
[ ] Bitcoin anchor is valid
[ ] All heartbeats valid
[ ] All transactions valid
[ ] Heartbeats Merkle root correct
[ ] Transactions Merkle root correct
[ ] State root correct after applying changes
[ ] All signer scores correct
[ ] All signer signatures verify

================================================================================
PART XV: STATE MACHINE
================================================================================

APPLY HEARTBEAT
---------------

fn apply_heartbeat(state: GlobalState, hb: Heartbeat) -> GlobalState {
    account = state.accounts.get_or_create(hb.pubkey)

    # Update counts
    account.total_heartbeats += 1
    account.epoch_heartbeats += 1
    account.last_hb_btc_height = hb.btc_anchor.height
    account.last_hb_atomic_ms = hb.atomic_time.timestamp_ms

    # Check for epoch change
    if hb.btc_anchor.epoch > state.btc_epoch:
        state = handle_epoch_change(state, hb.btc_anchor.epoch)
        account.epoch_heartbeats = 1

    state.accounts[hb.pubkey] = account
    state.total_heartbeats += 1

    return state
}

APPLY TRANSACTION
-----------------

fn apply_transaction(state: GlobalState, tx: Transaction) -> GlobalState {
    sender = state.accounts[tx.sender]
    receiver = state.accounts.get_or_create(tx.receiver)

    # Transfer
    sender.balance -= tx.amount
    receiver.balance += tx.amount

    # Update sender metadata
    sender.nonce = tx.nonce

    current_second = tx.atomic_timestamp_ms / 1000
    if sender.current_second == current_second:
        sender.second_tx_count += 1
    else:
        sender.current_second = current_second
        sender.second_tx_count = 1

    sender.epoch_tx_count += 1

    state.accounts[tx.sender] = sender
    state.accounts[tx.receiver] = receiver

    return state
}

APPLY BLOCK
-----------

fn apply_block(
    state: GlobalState,
    heartbeats: Vec<Heartbeat>,
    transactions: Vec<Transaction>
) -> GlobalState {
    # Heartbeats first
    for hb in heartbeats:
        state = apply_heartbeat(state, hb)

    # Then transactions
    for tx in transactions:
        state = apply_transaction(state, tx)

    return state
}

================================================================================
PART XVI: GENESIS AND EMISSION
================================================================================

GENESIS BLOCK
-------------

GENESIS_BLOCK = Block {
    header: BlockHeader {
        version: 6,
        height: 0,
        parent_hash: Hash { data: zeros(32) },
        timestamp_ms: <LAUNCH_TIMESTAMP>,
        heartbeats_root: Hash { data: zeros(32) },
        transactions_root: Hash { data: zeros(32) },
        state_root: <EMPTY_STATE_ROOT>,
        btc_anchor: BitcoinAnchor {
            height: <BTC_HEIGHT_AT_LAUNCH>,
            block_hash: <BTC_HASH_AT_LAUNCH>,
            merkle_root: <BTC_MERKLE_AT_LAUNCH>,
            timestamp: <BTC_TIMESTAMP_AT_LAUNCH>,
            difficulty: <BTC_DIFFICULTY_AT_LAUNCH>,
            epoch: <BTC_HEIGHT_AT_LAUNCH> / 210000,
            confirmations: 0
        }
    },
    heartbeats: [],
    transactions: [],
    signers: []
}

EMISSION SCHEDULE
-----------------

fn get_block_reward(btc_height: u64) -> u64 {
    """
    Block reward halves with Bitcoin halvings.
    Initial: 50 MONTANA per block
    """
    INITIAL_REWARD = 50_000_000_00  # 50 MONTANA (8 decimals)

    epoch = btc_height / BTC_HALVING_INTERVAL
    return INITIAL_REWARD >> epoch  # Halve each epoch
}

================================================================================
PART XVII: API SPECIFICATION
================================================================================

JSON-RPC METHODS
----------------

# Chain
getBlockByHash(hash: string) -> Block
getBlockByHeight(height: number) -> Block
getLatestBlock() -> Block
getBlockCount() -> number
getChainWeight() -> number

# Accounts
getAccount(pubkey: string) -> AccountState
getBalance(pubkey: string) -> number
getScore(pubkey: string) -> number
getEffectiveScore(pubkey: string) -> number
isActive(pubkey: string) -> bool

# Heartbeats
submitHeartbeat(heartbeat: Heartbeat) -> string  # Returns ID
getHeartbeat(id: string) -> Heartbeat
getHeartbeatsByPubkey(pubkey: string, limit: number) -> Heartbeat[]

# Transactions
submitTransaction(tx: Transaction) -> string  # Returns ID
getTransaction(id: string) -> Transaction
getPersonalDifficulty(pubkey: string) -> number
estimateTransactionTime(pubkey: string) -> number  # Milliseconds

# Network
getPeers() -> PeerInfo[]
getNetworkInfo() -> NetworkInfo

# Time
getAtomicTime() -> AtomicTimeProof
getBitcoinAnchor() -> BitcoinAnchor
getCurrentEpoch() -> number

================================================================================
PART XVIII: ERROR HANDLING
================================================================================

ERROR CODES
-----------

1xxx - General errors
1000  UNKNOWN_ERROR
1001  INVALID_PARAMETER
1002  INTERNAL_ERROR
1003  NOT_IMPLEMENTED

2xxx - Layer 0 (Atomic Time) errors
2001  INSUFFICIENT_TIME_SOURCES
2002  INSUFFICIENT_REGIONS
2003  EXCESSIVE_TIME_DRIFT
2004  NTP_TIMEOUT
2005  NTP_NETWORK_ERROR

3xxx - Layer 1 (VDF) errors
3001  VDF_SEED_MISMATCH
3002  INSUFFICIENT_VDF_ITERATIONS
3003  INVALID_VDF_PROOF
3004  VDF_CHECKPOINT_ERROR
3005  STARK_VERIFICATION_FAILED

4xxx - Layer 2 (Bitcoin) errors
4001  INVALID_BITCOIN_ANCHOR
4002  BITCOIN_HEIGHT_TOO_OLD
4003  BITCOIN_HASH_MISMATCH
4004  BITCOIN_API_UNAVAILABLE
4005  NO_BITCOIN_CONSENSUS
4006  INVALID_EPOCH

5xxx - Heartbeat errors
5001  INVALID_HEARTBEAT_SEQUENCE
5002  INVALID_HEARTBEAT_SIGNATURE
5003  CROSS_LAYER_INCONSISTENT
5004  DUPLICATE_HEARTBEAT

6xxx - Transaction errors
6001  SENDER_NOT_FOUND
6002  INSUFFICIENT_BALANCE
6003  INVALID_NONCE
6004  ZERO_AMOUNT
6005  INSUFFICIENT_POW_DIFFICULTY
6006  INVALID_POW
6007  INVALID_TX_SIGNATURE
6008  TRANSACTION_EXPIRED
6009  INVALID_MEMO_LENGTH

7xxx - Block errors
7001  INVALID_VERSION
7002  INVALID_HEIGHT
7003  INVALID_PARENT_HASH
7004  BLOCK_TOO_LARGE
7005  TOO_MANY_HEARTBEATS
7006  TOO_MANY_TRANSACTIONS
7007  INVALID_MERKLE_ROOT
7008  INVALID_STATE_ROOT
7009  INVALID_SIGNER

8xxx - Network errors
8001  PEER_UNREACHABLE
8002  HANDSHAKE_FAILED
8003  PROTOCOL_MISMATCH
8004  MESSAGE_TOO_LARGE
8005  INVALID_CHECKSUM

================================================================================
PART XIX: TEST VECTORS
================================================================================

SHA3-256 TEST VECTORS
---------------------

Input: "" (empty)
Output: a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a

Input: "MONTANA"
Output: <compute at implementation time>

Input: VDF_SEED_PREFIX (b"MONTANA_VDF_V6_")
Output: <compute at implementation time>

VDF TEST VECTORS
----------------

Seed: zeros(32)
Iterations: 1000
Expected checkpoints: 2 (at 0, 1000)
Expected output: <compute at implementation time>

DIFFICULTY CALCULATION TEST VECTORS
-----------------------------------

Test 1:
  epoch_tx_count: 0
  second_tx_count: 0
  Expected: 16 bits

Test 2:
  epoch_tx_count: 10
  second_tx_count: 0
  Expected: 16 bits (still free)

Test 3:
  epoch_tx_count: 11
  second_tx_count: 0
  Expected: 18 bits (+2)

Test 4:
  epoch_tx_count: 10
  second_tx_count: 1
  Expected: 20 bits (+4 burst)

Test 5:
  epoch_tx_count: 15
  second_tx_count: 3
  Expected: 32 bits (capped at max)

================================================================================
END OF SPECIFICATION
================================================================================

Version: 7.0.0
Date: December 2025
Status: COMPLETE

Hash: SHA3-256(this_document)

"All Sybil identities are equal in time."
"Your spam is your problem, not the network's."

Trust(t) → 0 as t → ∞

Dedicated to Hal Finney (1956-2014)
"Running bitcoin" — January 11, 2009

Ɉ
