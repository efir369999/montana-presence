# Ɉ Montana Technical Specification v1.0

**Protocol Version:** 7
**Document Version:** 1.0
**Date:** December 31, 2025
**Author:** Alejandro Montana

---

## Table of Contents

1. [Overview](#1-overview)
2. [Token Specification](#2-token-specification)
3. [Asymptotic Trust Consensus (ATC)](#3-asymptotic-trust-consensus-atc)
4. [Layer 0: Atomic Time](#4-layer-0-atomic-time)
5. [Layer 1: Temporal Proof](#5-layer-1-temporal-proof)
6. [Layer 2: Bitcoin Anchor](#6-layer-2-bitcoin-anchor)
7. [Heartbeat Structure](#7-heartbeat-structure)
8. [Score System](#8-score-system)
9. [Block Structure](#9-block-structure)
10. [Block Production](#10-block-production)
11. [Block Reward Distribution](#11-block-reward-distribution)
12. [Transaction Structure](#12-transaction-structure)
13. [Transaction Fees](#13-transaction-fees)
14. [Privacy Tiers](#14-privacy-tiers)
15. [Telegram Bot Protocol](#15-telegram-bot-protocol)
16. [Cryptographic Primitives](#16-cryptographic-primitives)
17. [Network Protocol](#17-network-protocol)
18. [Governance](#18-governance)
19. [Constants Reference](#19-constants-reference)
20. [API Reference](#20-api-reference)
21. [Account State](#21-account-state)
22. [Wallet (PLUTUS)](#22-wallet-plutus)
23. [Mempool Management](#23-mempool-management)
24. [Sync Protocol](#24-sync-protocol)
25. [Storage Structure](#25-storage-structure)
26. [Node Configuration](#26-node-configuration)
27. [Genesis Block](#27-genesis-block)
28. [Constants Reference (Complete)](#28-constants-reference-complete)

---

## 1. Overview

### 1.1 Purpose

This document provides the complete technical specification for implementing the Ɉ Montana protocol. It serves as:
- Implementation guide for developers
- Reference for auditors
- Specification for interoperability

### 1.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Ɉ MONTANA ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  FULL NODE  │  │  TG BOT     │  │  TG USER                │  │
│  │  (Tier 0)   │  │  (Tier 1)   │  │  (Tier 2)               │  │
│  │  70% weight │  │  20% weight │  │  10% weight             │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
│         └────────────────┼──────────────────────┘                │
│                          │                                       │
│  ┌───────────────────────▼───────────────────────────────────┐  │
│  │                    ATC CONSENSUS                           │  │
│  │  Layer 2: Bitcoin Anchor (Finalization)                    │  │
│  │  Layer 1: VDF Temporal Proof (Heartbeats)                  │  │
│  │  Layer 0: Atomic Time (34 sources, 8 regions)              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    DAG-PHANTOM                             │  │
│  │  Block ordering without leader selection                   │  │
│  │  ECVRF eligibility, not selection                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Token Specification

### 2.1 Identity

```python
TOKEN_NAME: str = "Montana"
TOKEN_SYMBOL: str = "Ɉ"
TOKEN_TICKER: str = "MONT"
UNIT: str = "seconds"
```

### 2.2 Supply Parameters

```python
TOTAL_SUPPLY: int = 1_260_000_000        # 21 million minutes in seconds
INITIAL_REWARD: int = 3000               # 50 minutes in seconds
HALVING_INTERVAL: int = 210_000          # Blocks per halving
TOTAL_BLOCKS: int = 6_930_000            # 33 eras × 210,000 blocks
TOTAL_ERAS: int = 33                     # Number of halvings
```

### 2.3 Fair Launch

```python
PRE_MINE: int = 0
FOUNDER_ALLOCATION: int = 0
ICO_ALLOCATION: int = 0
TEAM_ALLOCATION: int = 0
```

### 2.4 Unit Conversions

```python
def seconds_to_minutes(seconds: int) -> float:
    return seconds / 60

def seconds_to_hours(seconds: int) -> float:
    return seconds / 3600

def seconds_to_days(seconds: int) -> float:
    return seconds / 86400

def format_montana(amount: int) -> str:
    """Format amount with appropriate unit."""
    if amount >= 86400:
        return f"{amount / 86400:.2f} days"
    elif amount >= 3600:
        return f"{amount / 3600:.2f} hours"
    elif amount >= 60:
        return f"{amount / 60:.2f} minutes"
    else:
        return f"{amount} Ɉ"
```

### 2.5 Block Reward Function

```python
def get_block_reward(height: int) -> int:
    """
    Calculate block reward for given height.

    Args:
        height: Block height

    Returns:
        Block reward in seconds (Ɉ)
    """
    halvings = height // HALVING_INTERVAL
    if halvings >= TOTAL_ERAS:
        return 0
    return INITIAL_REWARD >> halvings
```

### 2.6 Emission Schedule

| Era | Height Range | Block Reward | Era Supply | Cumulative |
|-----|--------------|--------------|------------|------------|
| 1 | 0 - 209,999 | 3,000 Ɉ | 630,000,000 | 630,000,000 |
| 2 | 210,000 - 419,999 | 1,500 Ɉ | 315,000,000 | 945,000,000 |
| 3 | 420,000 - 629,999 | 750 Ɉ | 157,500,000 | 1,102,500,000 |
| 4 | 630,000 - 839,999 | 375 Ɉ | 78,750,000 | 1,181,250,000 |
| 5 | 840,000 - 1,049,999 | 187 Ɉ | 39,270,000 | 1,220,520,000 |
| ... | ... | ... | ... | ... |
| 33 | 6,720,000 - 6,929,999 | 0 Ɉ | 0 | 1,260,000,000 |

---

## 3. Asymptotic Trust Consensus (ATC)

### 3.1 Core Principle

Trust requirements approach zero asymptotically across three layers:

```
T_total = T₀ × T₁ × T₂ → 0

Where:
- T₀ = 0 (physical observation, no cryptographic trust)
- T₁ = 1/√c (c = heartbeat count)
- T₂ = 2^(-c) (c = Bitcoin confirmations)
```

### 3.2 Layer Summary

| Layer | Name | Trust Model | Data Source |
|-------|------|-------------|-------------|
| 0 | Atomic Time | Zero (physical) | 34 NTP servers |
| 1 | Temporal Proof | Diminishing | VDF heartbeats |
| 2 | Bitcoin Anchor | Exponential decay | Bitcoin blockchain |

---

## 4. Layer 0: Atomic Time

### 4.1 Time Sources

```python
NTP_TOTAL_SOURCES: int = 34
NTP_MIN_SOURCES_CONSENSUS: int = 18      # >50% required
NTP_MIN_SOURCES_CONTINENT: int = 2       # Per inhabited continent
NTP_MIN_SOURCES_POLE: int = 1            # Per polar region
NTP_MIN_REGIONS_TOTAL: int = 5           # Minimum distinct regions
```

### 4.2 Region Configuration

```python
REGIONS = {
    "EUROPE": {
        "id": 0x01,
        "sources": [
            ("PTB", "ptbtime1.ptb.de", "Germany"),
            ("NPL", "ntp1.npl.co.uk", "UK"),
            ("LNE-SYRTE", "ntp.obspm.fr", "France"),
            ("METAS", "ntp.metas.ch", "Switzerland"),
            ("INRIM", "ntp1.inrim.it", "Italy"),
            ("VSL", "ntp.vsl.nl", "Netherlands"),
            ("ROA", "ntp.roa.es", "Spain"),
            ("GUM", "tempus1.gum.gov.pl", "Poland"),
        ]
    },
    "ASIA": {
        "id": 0x02,
        "sources": [
            ("NICT", "ntp.nict.jp", "Japan"),
            ("NIM", "ntp.nim.ac.cn", "China"),
            ("KRISS", "time.kriss.re.kr", "South Korea"),
            ("NPLI", "time.nplindia.org", "India"),
            ("VNIIFTRI", "ntp2.vniiftri.ru", "Russia"),
            ("TL", "time.stdtime.gov.tw", "Taiwan"),
            ("INPL", "ntp.inpl.gov.il", "Israel"),
        ]
    },
    "NORTH_AMERICA": {
        "id": 0x03,
        "sources": [
            ("NIST", "time.nist.gov", "USA"),
            ("USNO", "tock.usno.navy.mil", "USA"),
            ("NRC", "time.nrc.ca", "Canada"),
            ("CENAM", "ntp.cenam.mx", "Mexico"),
        ]
    },
    "SOUTH_AMERICA": {
        "id": 0x04,
        "sources": [
            ("INMETRO", "ntp.inmetro.gov.br", "Brazil"),
            ("INTI", "ntp.inti.gob.ar", "Argentina"),
            ("INN", "ntp.inn.cl", "Chile"),
        ]
    },
    "AFRICA": {
        "id": 0x05,
        "sources": [
            ("NMISA", "ntp.nmisa.org", "South Africa"),
            ("NIS", "ntp.nis.sci.eg", "Egypt"),
            ("KEBS", "ntp.kebs.org", "Kenya"),
        ]
    },
    "OCEANIA": {
        "id": 0x06,
        "sources": [
            ("NMI", "time.nmi.gov.au", "Australia"),
            ("MSL", "ntp.measurement.govt.nz", "New Zealand"),
            ("NMC", "ntp.nmc.a-star.edu.sg", "Singapore"),
        ]
    },
    "ANTARCTICA": {
        "id": 0x07,
        "sources": [
            ("McMurdo", "ntp.mcmurdo.usap.gov", "Ross Island"),
            ("Amundsen-Scott", "ntp.southpole.usap.gov", "South Pole"),
            ("Concordia", "ntp.concordia.ipev.fr", "Dome C"),
        ]
    },
    "ARCTIC": {
        "id": 0x08,
        "sources": [
            ("Ny-Alesund", "ntp.npolar.no", "Svalbard"),
            ("Thule", "ntp.thule.mil", "Greenland"),
            ("Alert", "ntp.alert.forces.gc.ca", "Nunavut"),
        ]
    }
}
```

### 4.3 Time Query Protocol

```python
NTP_QUERY_TIMEOUT_MS: int = 2000
NTP_MAX_DRIFT_MS: int = 1000
NTP_RETRY_COUNT: int = 3
NTP_QUERY_INTERVAL_SEC: int = 60

@dataclass
class AtomicTimeProof:
    timestamp_ms: int           # Consensus timestamp
    source_bitmap: int          # u64 - Which sources responded
    source_count: int           # u8 - Number of agreeing sources
    region_bitmap: int          # u8 - Which regions covered
    max_drift_ms: int           # u16 - Maximum observed drift

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u64(self.timestamp_ms)
        writer.write_u64(self.source_bitmap)
        writer.write_u8(self.source_count)
        writer.write_u8(self.region_bitmap)
        writer.write_u16(self.max_drift_ms)
        return writer.to_bytes()

    def is_valid(self) -> bool:
        return (
            self.source_count >= NTP_MIN_SOURCES_CONSENSUS and
            bin(self.region_bitmap).count('1') >= NTP_MIN_REGIONS_TOTAL and
            self.max_drift_ms <= NTP_MAX_DRIFT_MS
        )
```

---

## 5. Layer 1: Temporal Proof

### 5.1 VDF Parameters

```python
VDF_HASH_FUNCTION: str = "SHAKE256"
VDF_OUTPUT_BYTES: int = 32
VDF_BASE_ITERATIONS: int = 16777216      # 2^24 (~2.5 seconds)
VDF_MAX_ITERATIONS: int = 268435456      # 2^28 (~40 seconds)
VDF_STARK_CHECKPOINT_INTERVAL: int = 1000  # Save state every N iterations for STARK proof
VDF_SEED_PREFIX: bytes = b"MONTANA_VDF_V7_"
```

### 5.2 VDF Structure

```python
@dataclass
class VDFProof:
    input_hash: bytes           # 32 bytes - Input to VDF
    output_hash: bytes          # 32 bytes - VDF output
    iterations: int             # u64 - Number of iterations
    checkpoints: List[bytes]    # STARK proof checkpoints
    proof: bytes                # STARK proof

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_raw(self.input_hash)
        writer.write_raw(self.output_hash)
        writer.write_u64(self.iterations)
        writer.write_u16(len(self.checkpoints))
        for cp in self.checkpoints:
            writer.write_raw(cp)
        writer.write_var_bytes(self.proof)
        return writer.to_bytes()

def compute_vdf(input_data: bytes, iterations: int) -> VDFProof:
    """
    Compute VDF with SHAKE256.

    Sequential: state[i+1] = SHAKE256(state[i])
    """
    state = VDF_SEED_PREFIX + input_data
    checkpoints = []

    for i in range(iterations):
        state = shake_256(state).digest(VDF_OUTPUT_BYTES)
        if i % VDF_STARK_CHECKPOINT_INTERVAL == 0:
            checkpoints.append(state)

    proof = generate_stark_proof(checkpoints)

    return VDFProof(
        input_hash=sha3_256(input_data),
        output_hash=state,
        iterations=iterations,
        checkpoints=checkpoints,
        proof=proof
    )
```

---

## 6. Layer 2: Bitcoin Anchor

### 6.1 Bitcoin Parameters

```python
BTC_BLOCK_TIME_SECONDS: int = 600
BTC_DIFFICULTY_PERIOD: int = 2016
BTC_HALVING_INTERVAL: int = 210000
BTC_CONFIRMATIONS_SOFT: int = 1
BTC_CONFIRMATIONS_MEDIUM: int = 6
BTC_CONFIRMATIONS_STRONG: int = 100
BTC_MAX_DRIFT_BLOCKS: int = 6
```

### 6.2 Bitcoin Anchor Structure

```python
@dataclass
class BitcoinAnchor:
    height: int                 # u64 - Block height
    block_hash: bytes           # 32 bytes - Block hash
    merkle_root: bytes          # 32 bytes - Merkle root
    timestamp: int              # u64 - Block timestamp
    difficulty: int             # u64 - Compact difficulty
    epoch: int                  # u32 - Halving epoch
    confirmations: int          # u16 - Confirmations at anchor

    SIZE: int = 90  # bytes

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u64(self.height)
        writer.write_raw(self.block_hash)
        writer.write_raw(self.merkle_root)
        writer.write_u64(self.timestamp)
        writer.write_u64(self.difficulty)
        writer.write_u32(self.epoch)
        writer.write_u16(self.confirmations)
        return writer.to_bytes()
```

### 6.3 Bitcoin API Endpoints

```python
BTC_API_ENDPOINTS: List[str] = [
    "https://blockstream.info/api",
    "https://mempool.space/api",
    "https://blockchain.info",
    "https://api.blockcypher.com/v1/btc/main"
]
BTC_API_CONSENSUS_MIN: int = 2  # Minimum agreeing sources

async def get_bitcoin_block(height: int) -> Optional[BitcoinAnchor]:
    """
    Fetch Bitcoin block from multiple APIs.
    Requires consensus from at least 2 sources.
    """
    results = []
    for api in BTC_API_ENDPOINTS:
        try:
            block = await fetch_block(api, height)
            results.append(block)
        except Exception:
            continue

    if len(results) < BTC_API_CONSENSUS_MIN:
        return None

    # Verify consensus
    hashes = [r.block_hash for r in results]
    if len(set(hashes)) > 1:
        return None  # Disagreement

    return results[0]
```

---

## 7. Heartbeat Structure

### 7.1 Definition

A heartbeat is proof of temporal presence across all three layers.

```python
@dataclass
class Heartbeat:
    # Identity
    pubkey: PublicKey               # 33 bytes

    # Layer 0: Physical Time
    atomic_time: AtomicTimeProof    # Variable

    # Layer 1: Temporal Proof
    vdf_proof: VDFProof             # Variable

    # Layer 2: Bitcoin Anchor
    btc_anchor: BitcoinAnchor       # 90 bytes

    # Metadata
    sequence: int                   # u64 - Heartbeat sequence
    version: int                    # u8 - Protocol version

    # Signature
    signature: Signature            # 17,089 bytes (SPHINCS+)

    def heartbeat_id(self) -> Hash:
        return sha3_256(self.serialize_for_signing())

    def is_cross_layer_consistent(self) -> bool:
        """Atomic time must be within 20 minutes of BTC block time."""
        btc_time_ms = self.btc_anchor.timestamp * 1000
        diff = abs(self.atomic_time.timestamp_ms - btc_time_ms)
        return diff <= 1_200_000  # 20 minutes
```

### 7.2 Heartbeat Validation

```python
def validate_heartbeat(hb: Heartbeat, state: GlobalState) -> bool:
    """
    Validate heartbeat across all layers.
    """
    # 1. Verify signature
    if not verify_sphincs(hb.pubkey, hb.serialize_for_signing(), hb.signature):
        return False

    # 2. Verify atomic time proof
    if not hb.atomic_time.is_valid():
        return False

    # 3. Verify VDF proof
    if not verify_stark_proof(hb.vdf_proof):
        return False

    # 4. Verify Bitcoin anchor
    expected_btc = state.btc_hash
    if hb.btc_anchor.block_hash != expected_btc:
        # Allow up to BTC_MAX_DRIFT_BLOCKS behind
        if not is_ancestor(hb.btc_anchor.block_hash, expected_btc, BTC_MAX_DRIFT_BLOCKS):
            return False

    # 5. Cross-layer consistency
    if not hb.is_cross_layer_consistent():
        return False

    # 6. Sequence must increment
    account = state.get_account(hb.pubkey)
    if account and hb.sequence <= account.last_heartbeat_sequence:
        return False

    return True
```

---

## 8. Score System

### 8.1 Score Formula

```python
SCORE_PRECISION: int = 1_000_000
SCORE_MIN_HEARTBEATS: int = 1
ACTIVITY_WINDOW_BLOCKS: int = 2016       # ~2 weeks in BTC blocks
INACTIVITY_PENALTY_RATE: float = 0.001

def compute_score(epoch_heartbeats: int) -> float:
    """
    Score = √(epoch_heartbeats)

    Provides:
    - Diminishing returns for more heartbeats
    - Sybil resistance (N identities = 1/√N efficiency)
    """
    if epoch_heartbeats < SCORE_MIN_HEARTBEATS:
        return 0.0
    return math.sqrt(epoch_heartbeats)

def effective_score(pubkey: PublicKey, state: GlobalState) -> float:
    """
    Effective Score = base_score × activity_multiplier
    """
    account = state.get_account(pubkey)
    if not account:
        return 0.0

    base = compute_score(account.epoch_heartbeats)
    multiplier = compute_activity_multiplier(
        account.last_heartbeat_height,
        state.chain_height
    )
    return base * multiplier

def compute_activity_multiplier(last_height: int, current_height: int) -> float:
    """
    Full multiplier if active within window.
    Decay for inactivity.
    """
    if last_height <= 0:
        return 0.0

    blocks_inactive = current_height - last_height

    if blocks_inactive <= ACTIVITY_WINDOW_BLOCKS:
        return 1.0

    decay = (blocks_inactive - ACTIVITY_WINDOW_BLOCKS) * INACTIVITY_PENALTY_RATE
    return max(0.1, 1.0 - decay)
```

### 8.2 Sybil Resistance Analysis

| Identities (N) | Time Each | Total Score | Efficiency |
|----------------|-----------|-------------|------------|
| 1 | T | √T | 100% |
| 4 | T/4 | 2√(T/4) = √T | 50% |
| 100 | T/100 | 10√(T/100) = √T | 10% |
| 10,000 | T/10,000 | 100√(T/10,000) = √T | 1% |

---

## 9. Block Structure

### 9.1 Block Header

```python
@dataclass
class BlockHeader:
    version: int                    # u8
    height: int                     # u64
    parent_hash: Hash               # 32 bytes
    timestamp_ms: int               # u64
    heartbeats_root: Hash           # 32 bytes (Merkle root)
    transactions_root: Hash         # 32 bytes (Merkle root)
    state_root: Hash                # 32 bytes
    btc_anchor: BitcoinAnchor       # 90 bytes

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_u8(self.version)
        writer.write_u64(self.height)
        writer.write_raw(self.parent_hash.data)
        writer.write_u64(self.timestamp_ms)
        writer.write_raw(self.heartbeats_root.data)
        writer.write_raw(self.transactions_root.data)
        writer.write_raw(self.state_root.data)
        writer.write_raw(self.btc_anchor.serialize())
        return writer.to_bytes()
```

### 9.2 Block

```python
@dataclass
class Block:
    header: BlockHeader
    heartbeats: List[Heartbeat]
    transactions: List[Transaction]
    signers: List[BlockSigner]

    MAX_HEARTBEATS: int = 1000
    MAX_TRANSACTIONS: int = 5000
    MAX_SIZE_BYTES: int = 4_194_304  # 4 MB

    def block_hash(self) -> Hash:
        return sha3_256(self.header.serialize())
```

### 9.3 Block Signer

```python
@dataclass
class BlockSigner:
    pubkey: PublicKey
    score_fixed: int        # Score × SCORE_PRECISION
    signature: Signature

    def score(self) -> float:
        return self.score_fixed / SCORE_PRECISION
```

---

## 10. Block Production

### 10.1 DAG-PHANTOM

Montana uses DAG structure with PHANTOM ordering:

```python
# No leader selection - eligibility only
def is_eligible_producer(pubkey: PublicKey, state: GlobalState) -> bool:
    account = state.get_account(pubkey)
    if not account:
        return False

    # Minimum heartbeats requirement
    if account.epoch_heartbeats < SCORE_MIN_HEARTBEATS:
        return False

    # Activity requirement
    blocks_since = state.chain_height - account.last_heartbeat_height
    if blocks_since > ACTIVITY_WINDOW_BLOCKS * 2:
        return False

    return True

def verify_eligibility_vrf(
    pubkey: PublicKey,
    vrf_proof: bytes,
    block_seed: bytes
) -> bool:
    """
    ECVRF proves eligibility without revealing identity until block creation.
    """
    vrf_output = ecvrf_verify(pubkey, block_seed, vrf_proof)
    if not vrf_output:
        return False

    # Threshold based on score
    threshold = compute_eligibility_threshold(pubkey)
    return int.from_bytes(vrf_output[:8], 'big') < threshold
```

### 10.2 Block Time

```python
BLOCK_TIME_TARGET_SEC: int = 600         # 10 minutes
BLOCK_INTERVAL_MS: int = 600_000         # 10 minutes in ms
VDF_TX_CHECKPOINT_SEC: int = 1           # Soft finality every second
```

### 10.3 Transaction Ordering

Montana separates transaction ordering from block rewards:

```python
# Two-layer timing
VDF_TX_CHECKPOINT_INTERVAL: int = 1      # 1 second - soft finality
BLOCK_REWARD_INTERVAL: int = 600         # 10 minutes - reward distribution

# UTC-aligned blocks from genesis
GENESIS_TIMESTAMP_MS: int = 1704067200000  # 2024-01-01 00:00:00 UTC

def get_block_number(timestamp_ms: int) -> int:
    """Get block number for given timestamp."""
    return (timestamp_ms - GENESIS_TIMESTAMP_MS) // BLOCK_INTERVAL_MS

def get_block_start_time(block_number: int) -> int:
    """Get UTC start time for block N."""
    return GENESIS_TIMESTAMP_MS + (block_number * BLOCK_INTERVAL_MS)
```

**Transaction Flow:**

1. User submits transaction with `timestamp_ms` from atomic time
2. Transaction enters mempool, propagates to network
3. VDF checkpoint every 1 second provides ordering
4. DAG-PHANTOM determines deterministic order across nodes
5. Bitcoin anchor every ~10 minutes provides hard finality

**No TPS ceiling** — network processes transactions as they arrive.

---

## 11. Block Reward Distribution

### 11.1 Three-Tier Lottery

```python
TIER_0_WEIGHT: float = 0.70  # Full nodes
TIER_1_WEIGHT: float = 0.20  # TG bot validators
TIER_2_WEIGHT: float = 0.10  # TG bot users

@dataclass
class RewardCandidate:
    pubkey: PublicKey
    tier: int               # 0, 1, or 2
    score: float

def select_block_winner(
    candidates: List[RewardCandidate],
    vrf_seed: bytes
) -> RewardCandidate:
    """
    Two-stage weighted lottery:
    1. Select tier based on tier weights
    2. Within tier, select by score-weighted random
    """
    # Stage 1: Select tier
    tier_rand = int.from_bytes(sha3_256(vrf_seed + b"tier")[:8], 'big')
    tier_value = (tier_rand % 100) / 100.0

    if tier_value < TIER_0_WEIGHT:
        selected_tier = 0
    elif tier_value < TIER_0_WEIGHT + TIER_1_WEIGHT:
        selected_tier = 1
    else:
        selected_tier = 2

    # Stage 2: Filter to selected tier
    tier_candidates = [c for c in candidates if c.tier == selected_tier]
    if not tier_candidates:
        # Fallback to any tier
        tier_candidates = candidates

    # Stage 3: Score-weighted selection within tier
    total_score = sum(c.score for c in tier_candidates)
    if total_score == 0:
        return random.choice(tier_candidates)

    pick_rand = int.from_bytes(sha3_256(vrf_seed + b"pick")[:8], 'big')
    pick_value = (pick_rand % 1_000_000) / 1_000_000 * total_score

    cumulative = 0.0
    for candidate in tier_candidates:
        cumulative += candidate.score
        if cumulative >= pick_value:
            return candidate

    return tier_candidates[-1]
```

### 11.2 Reward Calculation

```python
def calculate_block_reward(height: int, fees: int) -> int:
    """
    Winner receives: block_reward + accumulated_fees
    """
    base_reward = get_block_reward(height)
    return base_reward + fees
```

---

## 12. Transaction Structure

### 12.1 Transaction

```python
@dataclass
class Transaction:
    version: int                    # u8
    sender: PublicKey               # 33 bytes
    receiver: PublicKey             # 33 bytes
    amount: int                     # u64

    # Layer 0
    atomic_timestamp_ms: int        # u64
    atomic_source_bitmap: int       # u8

    # Layer 2
    btc_height: int                 # u64
    btc_hash: bytes                 # 32 bytes

    # Anti-spam PoW
    pow_difficulty: int             # u8
    pow_nonce: bytes                # 8 bytes
    pow_hash: Hash                  # 32 bytes

    # Metadata
    nonce: int                      # u64
    epoch: int                      # u32
    memo: bytes                     # 256 bytes (zero-padded)
    memo_length: int                # u8

    # Privacy
    privacy_tier: int               # u8 (0-3)
    privacy_data: bytes             # Variable (stealth/ring/commitment)

    # Signature
    signature: Signature            # 17,089 bytes

    def transaction_id(self) -> Hash:
        return sha3_256(self.serialize_for_signing())
```

### 12.2 Transaction Types

```python
class TxType(IntEnum):
    STANDARD = 0            # Regular transfer
    COINBASE = 1            # Block reward
    PRIVACY_T1 = 2          # Hidden receiver
    PRIVACY_T2 = 3          # Hidden receiver + amount
    PRIVACY_T3 = 4          # Fully private
```

---

## 13. Transaction Fees

### 13.1 Free Tier

```python
TX_FREE_PER_SECOND: int = 1
TX_FREE_PER_EPOCH: int = 10
TX_EPOCH_DURATION_SEC: int = 600  # 10 minutes
```

### 13.2 Anti-Spam PoW

```python
POW_BASE_DIFFICULTY_BITS: int = 16       # ~65ms
POW_EXCESS_PENALTY_BITS: int = 2         # Per excess tx
POW_BURST_PENALTY_BITS: int = 4          # Per same-second tx
POW_MAX_DIFFICULTY_BITS: int = 32        # ~18 hours max
POW_MEMORY_COST_KB: int = 65536          # 64 MB Argon2id
POW_TIME_COST: int = 1
POW_PARALLELISM: int = 1

def compute_required_pow(
    sender: PublicKey,
    state: GlobalState,
    current_second: int
) -> int:
    """
    Calculate required PoW difficulty.
    """
    account = state.get_account(sender)
    if not account:
        return POW_BASE_DIFFICULTY_BITS

    # Count transactions this epoch
    epoch_tx = account.epoch_tx_count

    # Count transactions this second
    second_tx = 0
    if account.last_tx_second == current_second:
        second_tx = account.second_tx_count

    # Free tier
    if epoch_tx < TX_FREE_PER_EPOCH and second_tx < TX_FREE_PER_SECOND:
        return 0

    # Calculate difficulty
    excess = max(0, epoch_tx - TX_FREE_PER_EPOCH)
    burst = max(0, second_tx - TX_FREE_PER_SECOND)

    difficulty = POW_BASE_DIFFICULTY_BITS
    difficulty += excess * POW_EXCESS_PENALTY_BITS
    difficulty += burst * POW_BURST_PENALTY_BITS

    return min(difficulty, POW_MAX_DIFFICULTY_BITS)
```

### 13.3 Privacy Fee Multipliers

```python
PRIVACY_FEE_MULTIPLIERS = {
    0: 1,   # T0: Transparent
    1: 2,   # T1: Hidden receiver
    2: 5,   # T2: + Hidden amount
    3: 10,  # T3: + Hidden sender
}
```

---

## 14. Privacy Tiers

### 14.1 T0: Transparent

All fields visible. No additional cryptography.

### 14.2 T1: Stealth Addresses (Hidden Receiver)

```python
@dataclass
class StealthKeys:
    view_secret: bytes      # a
    spend_secret: bytes     # b
    view_public: bytes      # A = a*G
    spend_public: bytes     # B = b*G

def create_stealth_output(
    recipient_view_public: bytes,
    recipient_spend_public: bytes
) -> Tuple[bytes, bytes]:
    """
    Create one-time stealth address.

    1. Generate random r
    2. R = r*G (ephemeral public key)
    3. s = H(r*A) (shared secret)
    4. P = s*G + B (one-time address)
    """
    r = os.urandom(32)
    R = scalarmult_base(r)

    shared = scalarmult(r, recipient_view_public)
    s = sha3_256(shared)

    sG = scalarmult_base(s)
    P = point_add(sG, recipient_spend_public)

    return P, R  # One-time address, ephemeral key
```

### 14.3 T2: Pedersen Commitments (Hidden Amount)

```python
# C = v*H + r*G
# Where H is second generator (nothing-up-my-sleeve)

H_GENERATOR = sha3_256(b"MONTANA_PEDERSEN_H_V1")

def pedersen_commit(value: int, blinding: bytes = None) -> Tuple[bytes, bytes]:
    """
    Create Pedersen commitment.
    Returns (commitment, blinding_factor).
    """
    if blinding is None:
        blinding = os.urandom(32)

    vH = scalarmult(int_to_scalar(value), H_GENERATOR)
    rG = scalarmult_base(blinding)
    C = point_add(vH, rG)

    return C, blinding

def verify_pedersen_sum(
    inputs: List[bytes],
    outputs: List[bytes],
    fee: int
) -> bool:
    """
    Verify: Σ(input_commitments) = Σ(output_commitments) + fee*H
    """
    sum_in = POINT_ZERO
    for c in inputs:
        sum_in = point_add(sum_in, c)

    sum_out = POINT_ZERO
    for c in outputs:
        sum_out = point_add(sum_out, c)

    fee_commitment = scalarmult(int_to_scalar(fee), H_GENERATOR)
    sum_out = point_add(sum_out, fee_commitment)

    return sum_in == sum_out
```

### 14.4 T3: Ring Signatures (Hidden Sender)

```python
RING_SIZE: int = 11

@dataclass
class LSAGSignature:
    key_image: bytes            # I = x * Hp(P)
    c0: bytes                   # Initial challenge
    responses: List[bytes]      # Response scalars

def lsag_sign(
    message: bytes,
    ring: List[bytes],          # Public keys
    secret_index: int,
    secret_key: bytes
) -> LSAGSignature:
    """
    Linkable Spontaneous Anonymous Group signature.
    """
    n = len(ring)
    assert n >= 2

    # Key image (for linkability)
    P = ring[secret_index]
    Hp = hash_to_point(P)
    I = scalarmult(secret_key, Hp)

    # Generate random scalars
    alpha = os.urandom(32)
    responses = [os.urandom(32) for _ in range(n)]

    # Compute challenges in ring
    L = [None] * n
    R = [None] * n

    L[secret_index] = scalarmult_base(alpha)
    R[secret_index] = scalarmult(alpha, Hp)

    c = [None] * n
    c[(secret_index + 1) % n] = challenge_hash(message, L[secret_index], R[secret_index])

    for i in range(secret_index + 1, secret_index + n):
        idx = i % n
        next_idx = (i + 1) % n

        L[idx] = point_add(
            scalarmult_base(responses[idx]),
            scalarmult(c[idx], ring[idx])
        )
        R[idx] = point_add(
            scalarmult(responses[idx], Hp),
            scalarmult(c[idx], I)
        )

        if next_idx != secret_index:
            c[next_idx] = challenge_hash(message, L[idx], R[idx])

    # Close the ring
    responses[secret_index] = scalar_sub(
        alpha,
        scalar_mul(c[secret_index], secret_key)
    )

    return LSAGSignature(
        key_image=I,
        c0=c[0],
        responses=responses
    )
```

---

## 15. Telegram Bot Protocol

### 15.1 Bot Registration

```python
@dataclass
class BotValidator:
    bot_id: str                 # Telegram bot ID
    owner_pubkey: PublicKey     # Owner's Montana pubkey
    registered_height: int      # Block height at registration
    user_count: int             # Active users
    validation_count: int       # Total validations

class BotUser:
    user_id: str                # Telegram user ID
    bot_id: str                 # Which bot they use
    pubkey: PublicKey           # Montana pubkey
    frequency_seconds: int      # Validation frequency (60 - 86400)
    correct_answers: int
    total_answers: int
```

### 15.2 Time Verification Protocol

```python
@dataclass
class TimeChallenge:
    challenge_id: bytes         # Unique ID
    timestamp_ms: int           # When challenge was issued
    correct_time: str           # Correct answer (HH:MM)
    options: List[str]          # 5 shuffled options
    expires_at: int             # Challenge expiry

CHALLENGE_TIMEOUT_SEC: int = 60
TIME_VARIANCE_MINUTES: int = 2

def generate_time_challenge(device_time_ms: int) -> TimeChallenge:
    """
    Generate "What time is it, Chico?" challenge.
    """
    # Convert to HH:MM
    dt = datetime.fromtimestamp(device_time_ms / 1000)
    correct = dt.strftime("%H:%M")

    # Generate options: correct ± 1-2 minutes
    options = [correct]
    for delta in [-2, -1, 1, 2]:
        variant = (dt + timedelta(minutes=delta)).strftime("%H:%M")
        if variant not in options:
            options.append(variant)

    # Shuffle
    random.shuffle(options)

    return TimeChallenge(
        challenge_id=os.urandom(16),
        timestamp_ms=device_time_ms,
        correct_time=correct,
        options=options[:5],  # Exactly 5 options
        expires_at=int(time.time()) + CHALLENGE_TIMEOUT_SEC
    )

def verify_challenge_response(
    challenge: TimeChallenge,
    response: str,
    response_time: int
) -> bool:
    """
    Verify user's answer.
    """
    # Check expiry
    if response_time > challenge.expires_at:
        return False

    # Check answer
    return response == challenge.correct_time
```

### 15.3 Bot Messages

```python
# Challenge message
CHALLENGE_MESSAGE = """
🎬 *¿Qué hora es en tu reloj, Chico?*

_"What time is it on your clock, Chico?"_
— Tony Montana

Choose the correct time:
"""

# Success message
SUCCESS_MESSAGE = """
✅ *Correcto!*

Your validation has been recorded.
Current score: {score}
Next challenge in: {next_time}
"""

# Failure message
FAILURE_MESSAGE = """
❌ *Incorrecto.*

The correct time was: {correct}
Your answer: {answer}

Score penalty applied.
"""
```

---

## 16. Cryptographic Primitives

### 16.1 Hash Functions

```python
HASH_FUNCTION: str = "SHA3-256"

def sha3_256(data: bytes) -> bytes:
    return hashlib.sha3_256(data).digest()

def shake_256(data: bytes, length: int = 32) -> bytes:
    return hashlib.shake_256(data).digest(length)
```

### 16.2 Signatures (SPHINCS+)

```python
SIGNATURE_SCHEME: str = "SPHINCS+-SHAKE-128f"
SPHINCS_PUBLIC_KEY_SIZE: int = 32
SPHINCS_SECRET_KEY_SIZE: int = 64
SPHINCS_SIGNATURE_SIZE: int = 17088

def sphincs_keygen() -> Tuple[bytes, bytes]:
    """Generate SPHINCS+ keypair."""
    return liboqs.sign.generate_keypair("SPHINCS+-SHAKE-128f-simple")

def sphincs_sign(message: bytes, secret_key: bytes) -> bytes:
    """Sign message with SPHINCS+."""
    return liboqs.sign.sign(message, secret_key)

def sphincs_verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify SPHINCS+ signature."""
    return liboqs.sign.verify(message, signature, public_key)
```

### 16.3 Key Encapsulation (ML-KEM)

```python
KEY_ENCAPSULATION: str = "ML-KEM-768"

def mlkem_keygen() -> Tuple[bytes, bytes]:
    return liboqs.kem.generate_keypair("ML-KEM-768")

def mlkem_encapsulate(public_key: bytes) -> Tuple[bytes, bytes]:
    return liboqs.kem.encapsulate(public_key)

def mlkem_decapsulate(ciphertext: bytes, secret_key: bytes) -> bytes:
    return liboqs.kem.decapsulate(ciphertext, secret_key)
```

### 16.4 VRF (ECVRF)

```python
def ecvrf_prove(secret_key: bytes, input_data: bytes) -> bytes:
    """Generate VRF proof."""
    pass

def ecvrf_verify(public_key: bytes, input_data: bytes, proof: bytes) -> Optional[bytes]:
    """Verify VRF proof and return output."""
    pass
```

---

## 17. Network Protocol

### 17.1 Network Constants

```python
NETWORK_ID_MAINNET: int = 0x4D4F4E5441   # "MONTA"
NETWORK_ID_TESTNET: int = 0x544553544E   # "TESTN"
PROTOCOL_VERSION: int = 7
DEFAULT_PORT: int = 19656
MESSAGE_MAGIC_MAINNET: bytes = b"MONT"
MESSAGE_MAGIC_TESTNET: bytes = b"TEST"
```

### 17.2 Peer Connections

```python
MIN_OUTBOUND_CONNECTIONS: int = 8
MAX_INBOUND_CONNECTIONS: int = 125
```

### 17.3 Message Types

```python
class MessageType(IntEnum):
    HELLO = 0x01
    PING = 0x02
    PONG = 0x03
    GET_BLOCKS = 0x10
    BLOCKS = 0x11
    GET_HEARTBEATS = 0x12
    HEARTBEATS = 0x13
    NEW_BLOCK = 0x20
    NEW_HEARTBEAT = 0x21
    NEW_TRANSACTION = 0x22
```

---

## 18. Governance

### 18.1 MIP Process

```python
class MIPStatus(IntEnum):
    DRAFT = 0
    PROPOSED = 1
    SIGNALING = 2
    LOCKED_IN = 3
    ACTIVE = 4
    REJECTED = 5
    WITHDRAWN = 6
```

### 18.2 Activation Parameters

```python
SOFT_FORK_THRESHOLD: float = 0.95
HARD_FORK_THRESHOLD: float = 0.95
ACTIVATION_WINDOW: int = 2016            # BTC blocks (~2 weeks)
TIMEOUT_EPOCHS: int = 2                  # ~8 years
```

### 18.3 Version Signaling

```python
# Heartbeat version field structure:
# Bits 0-7:   Protocol version
# Bits 8-15:  Reserved
# Bits 16-31: MIP signaling bits

def signal_mip_support(heartbeat: Heartbeat, mip_number: int) -> None:
    """Set MIP support bit in heartbeat version."""
    bit_position = 16 + (mip_number % 16)
    heartbeat.version |= (1 << bit_position)
```

---

## 19. Constants Reference

```python
# ==============================================================================
# TOKEN
# ==============================================================================
TOKEN_NAME = "Montana"
TOKEN_SYMBOL = "Ɉ"
TOKEN_TICKER = "MONT"
TOTAL_SUPPLY = 1_260_000_000
INITIAL_REWARD = 3000
HALVING_INTERVAL = 210_000
TOTAL_BLOCKS = 6_930_000
TOTAL_ERAS = 33

# ==============================================================================
# LAYER 0: ATOMIC TIME
# ==============================================================================
NTP_TOTAL_SOURCES = 34
NTP_MIN_SOURCES_CONSENSUS = 18
NTP_MIN_SOURCES_CONTINENT = 2
NTP_QUERY_TIMEOUT_MS = 2000
NTP_MAX_DRIFT_MS = 1000

# ==============================================================================
# LAYER 1: VDF
# ==============================================================================
VDF_HASH_FUNCTION = "SHAKE256"
VDF_BASE_ITERATIONS = 16777216
VDF_STARK_CHECKPOINT_INTERVAL = 1000

# ==============================================================================
# LAYER 2: BITCOIN
# ==============================================================================
BTC_HALVING_INTERVAL = 210000
BTC_CONFIRMATIONS_MEDIUM = 6
BTC_MAX_DRIFT_BLOCKS = 6

# ==============================================================================
# SCORE
# ==============================================================================
SCORE_PRECISION = 1_000_000
SCORE_MIN_HEARTBEATS = 1
ACTIVITY_WINDOW_BLOCKS = 2016
INACTIVITY_PENALTY_RATE = 0.001

# ==============================================================================
# BLOCK REWARDS
# ==============================================================================
TIER_0_WEIGHT = 0.70
TIER_1_WEIGHT = 0.20
TIER_2_WEIGHT = 0.10

# ==============================================================================
# TRANSACTIONS
# ==============================================================================
TX_FREE_PER_SECOND = 1
TX_FREE_PER_EPOCH = 10
TX_EPOCH_DURATION_SEC = 600
POW_BASE_DIFFICULTY_BITS = 16
POW_MEMORY_COST_KB = 65536

# ==============================================================================
# PRIVACY
# ==============================================================================
RING_SIZE = 11
PRIVACY_FEE_T0 = 1
PRIVACY_FEE_T1 = 2
PRIVACY_FEE_T2 = 5
PRIVACY_FEE_T3 = 10

# ==============================================================================
# NETWORK
# ==============================================================================
PROTOCOL_VERSION = 7
DEFAULT_PORT = 19656
MAX_BLOCK_SIZE = 4_194_304
BLOCK_TIME_TARGET_SEC = 600
VDF_TX_CHECKPOINT_SEC = 1

# ==============================================================================
# CRYPTOGRAPHY
# ==============================================================================
SPHINCS_SIGNATURE_SIZE = 17088
SHA3_256_OUTPUT_SIZE = 32

# ==============================================================================
# GOVERNANCE
# ==============================================================================
SOFT_FORK_THRESHOLD = 0.95
ACTIVATION_WINDOW = 2016
```

---

## 20. API Reference

### 20.1 RPC Methods

```python
# Node information
getinfo() -> dict
getblockchaininfo() -> dict
getnetworkinfo() -> dict

# Blocks
getblock(hash: str) -> Block
getblockheader(hash: str) -> BlockHeader
getblockhash(height: int) -> str
getbestblockhash() -> str

# Heartbeats
getheartbeat(id: str) -> Heartbeat
submitheartbeat(heartbeat: Heartbeat) -> str

# Transactions
gettransaction(txid: str) -> Transaction
sendtransaction(tx: Transaction) -> str
getmempool() -> List[str]

# Accounts
getaccount(pubkey: str) -> AccountState
getbalance(pubkey: str) -> int
getscore(pubkey: str) -> float

# Bot
registerbot(bot_id: str, owner_pubkey: str) -> bool
submitvalidation(user_id: str, challenge_id: str, response: str) -> bool
```

### 20.2 WebSocket Events

```python
# Subscribe to events
subscribe("new_block")
subscribe("new_heartbeat")
subscribe("new_transaction")

# Event payloads
NewBlockEvent {
    hash: str
    height: int
    timestamp: int
}

NewHeartbeatEvent {
    id: str
    pubkey: str
    sequence: int
}
```

---

## 21. Account State

### 21.1 Account Structure

```python
@dataclass
class AccountState:
    """Per-account state tracking."""
    pubkey: PublicKey               # 33 bytes - Account identity
    balance: int                    # u64 - Current balance in Ɉ (seconds)
    nonce: int                      # u64 - Transaction nonce (anti-replay)

    # Heartbeat tracking
    epoch_heartbeats: int           # u32 - Heartbeats in current epoch
    total_heartbeats: int           # u64 - Lifetime heartbeats
    last_heartbeat_height: int      # u64 - Block height of last heartbeat
    last_heartbeat_sequence: int    # u64 - Sequence of last heartbeat
    first_seen_height: int          # u64 - When account was created

    # Participation tier
    tier: int                       # u8 - 0=node, 1=bot_validator, 2=bot_user

    # Transaction tracking
    epoch_tx_count: int             # u32 - Transactions this epoch
    last_tx_second: int             # u64 - Last transaction timestamp (seconds)
    second_tx_count: int            # u8 - Transactions in current second

    def serialize(self) -> bytes:
        writer = ByteWriter()
        writer.write_raw(self.pubkey.serialize())
        writer.write_u64(self.balance)
        writer.write_u64(self.nonce)
        writer.write_u32(self.epoch_heartbeats)
        writer.write_u64(self.total_heartbeats)
        writer.write_u64(self.last_heartbeat_height)
        writer.write_u64(self.last_heartbeat_sequence)
        writer.write_u64(self.first_seen_height)
        writer.write_u8(self.tier)
        writer.write_u32(self.epoch_tx_count)
        writer.write_u64(self.last_tx_second)
        writer.write_u8(self.second_tx_count)
        return writer.to_bytes()
```

### 21.2 Global State

```python
@dataclass
class GlobalState:
    """Network-wide state."""
    chain_height: int               # Current block height
    chain_tip_hash: Hash            # Current chain tip

    # Bitcoin anchor
    btc_height: int                 # Last anchored BTC height
    btc_hash: Hash                  # Last anchored BTC hash
    btc_epoch: int                  # Current BTC halving epoch

    # Supply tracking
    total_supply: int               # Total minted supply
    circulating_supply: int         # Circulating (minus burned)

    # Network stats
    total_heartbeats: int           # Total heartbeats ever
    active_accounts: int            # Accounts with activity this epoch

    # Account index
    accounts: Dict[PublicKey, AccountState]

    def get_account(self, pubkey: PublicKey) -> Optional[AccountState]:
        return self.accounts.get(pubkey)

    def get_all_pubkeys(self) -> List[PublicKey]:
        return list(self.accounts.keys())
```

---

## 22. Wallet (PLUTUS)

### 22.1 Key Derivation

```python
# HD-like key derivation from seed
def derive_master_keys(seed: bytes) -> Tuple[bytes, bytes]:
    """
    Derive master view and spend keys from 256-bit seed.

    Returns (view_secret, spend_secret)
    """
    view_data = hmac_sha3_256(b"montana_view_key", seed)
    spend_data = hmac_sha3_256(b"montana_spend_key", seed)

    view_secret = scalar_reduce(view_data)
    spend_secret = scalar_reduce(spend_data)

    return view_secret, spend_secret

def derive_subaddress(
    view_secret: bytes,
    spend_secret: bytes,
    major: int,      # Account index
    minor: int       # Address index
) -> Tuple[bytes, bytes]:
    """
    Derive subaddress keys for account hierarchy.

    Returns (subaddress_view_public, subaddress_spend_public)
    """
    data = b"SubAddr" + view_secret + struct.pack('<II', major, minor)
    m = scalar_reduce(sha3_256(data))

    spend_public = scalarmult_base(spend_secret)
    m_point = scalarmult_base(m)

    sub_spend = point_add(spend_public, m_point)
    sub_view = scalarmult(view_secret, sub_spend)

    return sub_view, sub_spend
```

### 22.2 Wallet Encryption

```python
# Wallet encryption parameters
ARGON2_TIME_COST: int = 3
ARGON2_MEMORY_COST: int = 65536      # 64 MB
ARGON2_PARALLELISM: int = 4
ARGON2_HASH_LEN: int = 32

AES_KEY_SIZE: int = 32               # AES-256
AES_NONCE_SIZE: int = 12             # GCM nonce
AES_TAG_SIZE: int = 16               # GCM auth tag

MIN_PASSWORD_LENGTH: int = 8

def derive_encryption_key(password: str, salt: bytes) -> bytes:
    """
    Derive encryption key using Argon2id.

    Argon2id provides:
    - Memory-hard: Resistant to GPU/ASIC attacks
    - Time-hard: Adjustable computation time
    - Hybrid: Combines Argon2i and Argon2d benefits
    """
    return argon2id(
        password=password.encode('utf-8'),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN
    )

def encrypt_wallet(plaintext: bytes, password: str) -> bytes:
    """
    Encrypt wallet data with AES-256-GCM.

    Format: version (1) || salt (32) || nonce (12) || ciphertext || tag (16)
    """
    salt = os.urandom(32)
    nonce = os.urandom(AES_NONCE_SIZE)
    key = derive_encryption_key(password, salt)

    ciphertext, tag = aes_gcm_encrypt(key, nonce, plaintext)

    return bytes([WALLET_VERSION]) + salt + nonce + ciphertext + tag

def decrypt_wallet(encrypted: bytes, password: str) -> bytes:
    """Decrypt wallet data."""
    version = encrypted[0]
    salt = encrypted[1:33]
    nonce = encrypted[33:45]
    ciphertext_and_tag = encrypted[45:]

    key = derive_encryption_key(password, salt)
    return aes_gcm_decrypt(key, nonce, ciphertext_and_tag)
```

### 22.3 Wallet Structure

```python
WALLET_VERSION: int = 1

@dataclass
class Wallet:
    """Montana wallet."""
    # Master keys
    seed: bytes                     # 32 bytes - BIP39-style seed
    view_secret: bytes              # 32 bytes
    view_public: bytes              # 33 bytes
    spend_secret: bytes             # 32 bytes
    spend_public: bytes             # 33 bytes

    # Subaddresses: (major, minor) -> (view_pub, spend_pub)
    subaddresses: Dict[Tuple[int, int], Tuple[bytes, bytes]]

    # Tracked outputs
    outputs: Dict[bytes, WalletOutput]
    key_images: Set[bytes]

    # State
    synced_height: int

    def get_balance(self) -> Tuple[int, int]:
        """Returns (confirmed, pending) balance."""
        confirmed = sum(o.amount for o in self.outputs.values()
                       if o.status == OutputStatus.UNSPENT)
        pending = sum(o.amount for o in self.outputs.values()
                     if o.status == OutputStatus.PENDING)
        return confirmed, pending

    def get_primary_address(self) -> bytes:
        """Get main address (account 0, index 0)."""
        return self.view_public + self.spend_public

@dataclass
class WalletOutput:
    """Tracked wallet output."""
    txid: bytes                     # 32 bytes
    output_index: int               # u32
    amount: int                     # u64
    stealth_address: bytes          # 33 bytes
    tx_public_key: bytes            # 33 bytes
    one_time_secret: bytes          # 32 bytes (derived)
    key_image: bytes                # 32 bytes (for spending)
    status: OutputStatus            # UNSPENT, PENDING, SPENT
    block_height: int               # u64
    timestamp: int                  # u64

class OutputStatus(IntEnum):
    UNSPENT = 0
    PENDING = 1      # In mempool
    SPENT = 2
    LOCKED = 3       # Coinbase maturity
```

### 22.4 Output Scanning

```python
def scan_transaction(
    tx: Transaction,
    view_secret: bytes,
    spend_public: bytes
) -> List[WalletOutput]:
    """
    Scan transaction for outputs belonging to wallet.

    For each output:
    1. Compute shared secret: s = Hs(view_secret * tx_public_key)
    2. Derive expected address: P' = s*G + spend_public
    3. Compare with output address
    """
    found = []

    for i, output in enumerate(tx.outputs):
        # Compute shared secret
        shared = scalarmult(view_secret, output.tx_public_key)
        s = sha3_256(shared)

        # Derive expected one-time address
        sG = scalarmult_base(s)
        expected_address = point_add(sG, spend_public)

        if expected_address == output.stealth_address:
            # This output is ours!
            one_time_secret = scalar_add(s, spend_secret)
            key_image = generate_key_image(one_time_secret, output.stealth_address)

            found.append(WalletOutput(
                txid=tx.transaction_id(),
                output_index=i,
                amount=decrypt_amount(output.encrypted_amount, shared),
                stealth_address=output.stealth_address,
                tx_public_key=output.tx_public_key,
                one_time_secret=one_time_secret,
                key_image=key_image,
                status=OutputStatus.UNSPENT
            ))

    return found
```

---

## 23. Mempool Management

### 23.1 Mempool Configuration

```python
MEMPOOL_MAX_SIZE_MB: int = 300
MEMPOOL_MAX_TX_COUNT: int = 50000
MEMPOOL_EXPIRY_HOURS: int = 336      # 2 weeks
MEMPOOL_MIN_FEE_RATE: int = 1        # Minimum fee per KB

# Replace-by-fee
RBF_ENABLED: bool = True
RBF_MIN_INCREMENT: float = 1.1       # 10% fee increase required
```

### 23.2 Mempool Structure

```python
@dataclass
class MempoolEntry:
    tx: Transaction
    received_at: int                 # Unix timestamp
    fee_rate: float                  # Fee per KB
    ancestors: Set[bytes]            # Parent tx IDs
    descendants: Set[bytes]          # Child tx IDs

class Mempool:
    entries: Dict[bytes, MempoolEntry]  # txid -> entry
    by_fee: SortedList[MempoolEntry]    # Sorted by fee_rate desc
    total_size: int                     # Current size in bytes

    def add_transaction(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Add transaction to mempool.

        Validation:
        1. Transaction is valid (signatures, amounts)
        2. Inputs exist and unspent
        3. No double-spend with existing mempool tx
        4. Fee meets minimum
        5. Mempool not full (or tx pays higher fee)
        """
        txid = tx.transaction_id()

        # Check duplicate
        if txid in self.entries:
            return False, "Already in mempool"

        # Validate transaction
        if not validate_transaction(tx):
            return False, "Invalid transaction"

        # Check inputs
        for inp in tx.inputs:
            if inp.key_image in self.spent_key_images:
                return False, "Double-spend detected"

        # Check fee
        fee_rate = tx.fee / (len(tx.serialize()) / 1024)
        if fee_rate < MEMPOOL_MIN_FEE_RATE:
            return False, "Fee too low"

        # Add to mempool
        entry = MempoolEntry(
            tx=tx,
            received_at=int(time.time()),
            fee_rate=fee_rate
        )
        self.entries[txid] = entry
        self.by_fee.add(entry)

        return True, "Added to mempool"

    def get_transactions_for_block(self, max_size: int) -> List[Transaction]:
        """Get highest-fee transactions that fit in block."""
        selected = []
        current_size = 0

        for entry in self.by_fee:
            tx_size = len(entry.tx.serialize())
            if current_size + tx_size <= max_size:
                selected.append(entry.tx)
                current_size += tx_size

        return selected

    def remove_expired(self):
        """Remove transactions older than MEMPOOL_EXPIRY_HOURS."""
        cutoff = int(time.time()) - (MEMPOOL_EXPIRY_HOURS * 3600)
        expired = [txid for txid, e in self.entries.items()
                   if e.received_at < cutoff]
        for txid in expired:
            self.remove_transaction(txid)
```

---

## 24. Sync Protocol

### 24.1 Initial Block Download (IBD)

```python
IBD_BATCH_SIZE: int = 500            # Blocks per request
IBD_PARALLEL_DOWNLOADS: int = 4      # Concurrent download streams
IBD_CHECKPOINT_INTERVAL: int = 10000 # Verify checkpoint every N blocks

class SyncManager:
    def initial_sync(self, peers: List[Peer]):
        """
        Perform initial block download.

        1. Get best chain from peers
        2. Download headers first
        3. Verify header chain
        4. Download blocks in parallel
        5. Validate and apply blocks
        """
        # Get chain tips from peers
        tips = [peer.get_chain_tip() for peer in peers]
        best_height = max(tip.height for tip in tips)

        # Download headers
        headers = self.download_headers(peers, best_height)

        # Verify header chain
        if not self.verify_header_chain(headers):
            raise SyncError("Invalid header chain")

        # Download blocks in batches
        for start in range(0, best_height, IBD_BATCH_SIZE):
            end = min(start + IBD_BATCH_SIZE, best_height)
            blocks = self.download_blocks(peers, start, end)

            # Validate and apply
            for block in blocks:
                if not self.validate_and_apply(block):
                    raise SyncError(f"Invalid block at height {block.height}")

            # Checkpoint verification
            if end % IBD_CHECKPOINT_INTERVAL == 0:
                if not self.verify_checkpoint(end):
                    raise SyncError(f"Checkpoint mismatch at {end}")
```

### 24.2 Block Propagation

```python
BLOCK_PROPAGATION_TIMEOUT_MS: int = 5000
MAX_BLOCKS_IN_FLIGHT: int = 16

class BlockPropagation:
    def announce_block(self, block: Block):
        """Announce new block to peers."""
        inv = Inventory(type=INV_BLOCK, hash=block.block_hash())
        for peer in self.peers:
            peer.send(Message(type=MSG_INV, payload=inv))

    def handle_block(self, block: Block, from_peer: Peer):
        """Handle received block."""
        # Quick validation
        if not self.quick_validate(block):
            from_peer.misbehaving(10)
            return

        # Full validation
        if self.validate_block(block):
            # Apply to chain
            self.apply_block(block)
            # Relay to other peers
            self.announce_block(block)
        else:
            from_peer.misbehaving(100)
```

### 24.3 Chain Reorganization

```python
MAX_REORG_DEPTH: int = 100           # Maximum reorg depth

def reorganize_chain(
    current_tip: Block,
    new_tip: Block,
    state: GlobalState
) -> bool:
    """
    Reorganize chain to new tip.

    1. Find common ancestor
    2. Roll back to ancestor
    3. Apply new chain
    """
    # Find common ancestor
    old_chain = get_chain_to_ancestor(current_tip, MAX_REORG_DEPTH)
    new_chain = get_chain_to_ancestor(new_tip, MAX_REORG_DEPTH)

    ancestor = find_common_ancestor(old_chain, new_chain)
    if ancestor is None:
        return False  # Reorg too deep

    # Calculate chain scores
    old_score = compute_chain_score(old_chain)
    new_score = compute_chain_score(new_chain)

    if new_score <= old_score:
        return False  # New chain not better

    # Roll back
    for block in reversed(old_chain):
        if block.height <= ancestor.height:
            break
        unapply_block(block, state)

    # Apply new chain
    for block in new_chain:
        if block.height <= ancestor.height:
            continue
        if not apply_block(block, state):
            return False

    return True
```

---

## 25. Storage Structure

### 25.1 Database Schema

```python
# SQLite schema for node storage

SCHEMA = """
-- Blocks
CREATE TABLE blocks (
    height INTEGER PRIMARY KEY,
    hash BLOB NOT NULL UNIQUE,
    parent_hash BLOB NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    btc_height INTEGER NOT NULL,
    data BLOB NOT NULL,  -- Serialized block

    INDEX idx_blocks_hash (hash),
    INDEX idx_blocks_parent (parent_hash)
);

-- Transactions
CREATE TABLE transactions (
    txid BLOB PRIMARY KEY,
    block_height INTEGER,
    tx_index INTEGER,
    data BLOB NOT NULL,

    FOREIGN KEY (block_height) REFERENCES blocks(height)
);

-- UTXO Set
CREATE TABLE utxos (
    txid BLOB NOT NULL,
    output_index INTEGER NOT NULL,
    stealth_address BLOB NOT NULL,
    amount INTEGER NOT NULL,
    block_height INTEGER NOT NULL,

    PRIMARY KEY (txid, output_index),
    INDEX idx_utxos_address (stealth_address)
);

-- Key Images (spent outputs)
CREATE TABLE key_images (
    key_image BLOB PRIMARY KEY,
    txid BLOB NOT NULL,
    block_height INTEGER NOT NULL
);

-- Accounts
CREATE TABLE accounts (
    pubkey BLOB PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    nonce INTEGER NOT NULL DEFAULT 0,
    epoch_heartbeats INTEGER NOT NULL DEFAULT 0,
    total_heartbeats INTEGER NOT NULL DEFAULT 0,
    last_heartbeat_height INTEGER NOT NULL DEFAULT 0,
    first_seen_height INTEGER NOT NULL,
    tier INTEGER NOT NULL DEFAULT 0,
    data BLOB  -- Full serialized AccountState
);

-- Heartbeats
CREATE TABLE heartbeats (
    id BLOB PRIMARY KEY,
    pubkey BLOB NOT NULL,
    block_height INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    data BLOB NOT NULL,

    INDEX idx_heartbeats_pubkey (pubkey),
    INDEX idx_heartbeats_height (block_height)
);
""";
```

### 25.2 Storage Configuration

```python
@dataclass
class StorageConfig:
    db_path: str = "montana.db"
    blocks_dir: str = "blocks"
    chainstate_dir: str = "chainstate"

    # Performance
    cache_size_mb: int = 512
    write_buffer_mb: int = 64
    max_open_files: int = 1000

    # Pruning (optional)
    prune_enabled: bool = False
    prune_keep_blocks: int = 10000   # Keep last N blocks
```

---

## 26. Node Configuration

### 26.1 Configuration Structure

```python
class NetworkType(IntEnum):
    MAINNET = 1
    TESTNET = 2
    REGTEST = 3

@dataclass
class NodeConfig:
    """Complete node configuration."""
    # Identity
    data_dir: str = "~/.montana"
    node_name: str = "Montana-Node"

    # Network
    network_type: NetworkType = NetworkType.MAINNET
    listen_port: int = 19656
    max_inbound: int = 125
    max_outbound: int = 8

    # RPC
    rpc_enabled: bool = True
    rpc_bind: str = "127.0.0.1"
    rpc_port: int = 19657
    rpc_user: Optional[str] = None
    rpc_password: Optional[str] = None

    # Wallet
    wallet_enabled: bool = True
    wallet_file: str = "wallet.dat"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Performance
    db_cache_mb: int = 512
    mempool_size_mb: int = 300

    # Features
    enable_heartbeat: bool = True
    enable_mining: bool = False

    @classmethod
    def from_file(cls, path: str) -> 'NodeConfig':
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)

    def validate(self) -> bool:
        if self.max_outbound < 4:
            raise ValueError("max_outbound must be >= 4")
        if self.rpc_enabled and not self.rpc_password:
            raise ValueError("RPC password required when RPC enabled")
        return True
```

### 26.2 Network Seeds

```python
# DNS seeds for peer discovery
MAINNET_SEEDS = [
    "seed1.montana.network",
    "seed2.montana.network",
    "seed3.montana.network",
]

TESTNET_SEEDS = [
    "testnet-seed1.montana.network",
    "testnet-seed2.montana.network",
]

# Hardcoded bootstrap nodes
BOOTSTRAP_NODES = [
    ("node1.montana.network", 19656),
    ("node2.montana.network", 19656),
]
```

---

## 27. Genesis Block

### 27.1 Genesis Parameters

```python
# Genesis block parameters (to be set at launch)
GENESIS_TIMESTAMP_MS: int = 0        # TBD: Launch timestamp (UTC)
GENESIS_BTC_HEIGHT: int = 0          # TBD: Bitcoin block at launch
GENESIS_BTC_HASH: bytes = b''        # TBD: Bitcoin block hash at launch

# Genesis block structure
def create_genesis_block() -> Block:
    """
    Create genesis block.

    FAIR LAUNCH:
    - No pre-mine
    - No founder allocation
    - All coins from block rewards only
    """
    btc_anchor = BitcoinAnchor(
        height=GENESIS_BTC_HEIGHT,
        block_hash=Hash(GENESIS_BTC_HASH),
        merkle_root=Hash.zero(),
        timestamp=GENESIS_TIMESTAMP_MS // 1000,
        difficulty=0,
        epoch=GENESIS_BTC_HEIGHT // 210000,
        confirmations=0,
    )

    header = BlockHeader(
        version=PROTOCOL_VERSION,
        height=0,
        parent_hash=Hash.zero(),
        timestamp_ms=GENESIS_TIMESTAMP_MS,
        heartbeats_root=Hash.zero(),
        transactions_root=Hash.zero(),
        state_root=Hash.zero(),
        btc_anchor=btc_anchor,
    )

    return Block(
        header=header,
        heartbeats=[],
        transactions=[],
        signers=[],
    )
```

### 27.2 Genesis State

```python
def create_genesis_state() -> GlobalState:
    """
    Create genesis state.

    FAIR LAUNCH: Zero initial supply.
    """
    genesis = create_genesis_block()

    return GlobalState(
        chain_height=0,
        chain_tip_hash=genesis.block_hash(),
        btc_height=GENESIS_BTC_HEIGHT,
        btc_hash=Hash(GENESIS_BTC_HASH),
        btc_epoch=GENESIS_BTC_HEIGHT // 210000,
        total_supply=0,           # Fair launch - no pre-mine
        circulating_supply=0,
        total_heartbeats=0,
        active_accounts=0,
        accounts={},
    )
```

---

## 28. Constants Reference (Complete)

```python
# ==============================================================================
# TOKEN
# ==============================================================================
TOKEN_NAME = "Montana"
TOKEN_SYMBOL = "Ɉ"
TOKEN_TICKER = "MONT"
TOTAL_SUPPLY = 1_260_000_000
INITIAL_REWARD = 3000
HALVING_INTERVAL = 210_000
TOTAL_BLOCKS = 6_930_000
TOTAL_ERAS = 33

# ==============================================================================
# LAYER 0: ATOMIC TIME
# ==============================================================================
NTP_TOTAL_SOURCES = 34
NTP_MIN_SOURCES_CONSENSUS = 18
NTP_MIN_SOURCES_CONTINENT = 2
NTP_MIN_REGIONS_TOTAL = 5
NTP_QUERY_TIMEOUT_MS = 2000
NTP_MAX_DRIFT_MS = 1000

# ==============================================================================
# LAYER 1: VDF
# ==============================================================================
VDF_HASH_FUNCTION = "SHAKE256"
VDF_OUTPUT_BYTES = 32
VDF_BASE_ITERATIONS = 16777216
VDF_MAX_ITERATIONS = 268435456
VDF_STARK_CHECKPOINT_INTERVAL = 1000

# ==============================================================================
# LAYER 2: BITCOIN
# ==============================================================================
BTC_BLOCK_TIME_SECONDS = 600
BTC_HALVING_INTERVAL = 210000
BTC_CONFIRMATIONS_SOFT = 1
BTC_CONFIRMATIONS_MEDIUM = 6
BTC_CONFIRMATIONS_STRONG = 100
BTC_MAX_DRIFT_BLOCKS = 6

# ==============================================================================
# BLOCK TIMING
# ==============================================================================
BLOCK_TIME_TARGET_SEC = 600
BLOCK_INTERVAL_MS = 600_000
VDF_TX_CHECKPOINT_SEC = 1

# ==============================================================================
# SCORE
# ==============================================================================
SCORE_PRECISION = 1_000_000
SCORE_MIN_HEARTBEATS = 1
ACTIVITY_WINDOW_BLOCKS = 2016
INACTIVITY_PENALTY_RATE = 0.001

# ==============================================================================
# BLOCK REWARDS
# ==============================================================================
TIER_0_WEIGHT = 0.70              # Full nodes
TIER_1_WEIGHT = 0.20              # TG bot validators
TIER_2_WEIGHT = 0.10              # TG bot users

# ==============================================================================
# TRANSACTIONS
# ==============================================================================
TX_FREE_PER_SECOND = 1
TX_FREE_PER_EPOCH = 10
TX_EPOCH_DURATION_SEC = 600
POW_BASE_DIFFICULTY_BITS = 16
POW_EXCESS_PENALTY_BITS = 2
POW_BURST_PENALTY_BITS = 4
POW_MAX_DIFFICULTY_BITS = 32
POW_MEMORY_COST_KB = 65536

# ==============================================================================
# PRIVACY
# ==============================================================================
RING_SIZE = 11
PRIVACY_FEE_T0 = 1
PRIVACY_FEE_T1 = 2
PRIVACY_FEE_T2 = 5
PRIVACY_FEE_T3 = 10

# ==============================================================================
# NETWORK
# ==============================================================================
PROTOCOL_VERSION = 7
NETWORK_ID_MAINNET = 0x4D4F4E5441
NETWORK_ID_TESTNET = 0x544553544E
DEFAULT_PORT = 19656
DEFAULT_RPC_PORT = 19657
MIN_OUTBOUND_CONNECTIONS = 8
MAX_INBOUND_CONNECTIONS = 125
MAX_BLOCK_SIZE = 4_194_304
MAX_HEARTBEATS_PER_BLOCK = 1000
MAX_TRANSACTIONS_PER_BLOCK = 5000

# ==============================================================================
# MEMPOOL
# ==============================================================================
MEMPOOL_MAX_SIZE_MB = 300
MEMPOOL_MAX_TX_COUNT = 50000
MEMPOOL_EXPIRY_HOURS = 336
MEMPOOL_MIN_FEE_RATE = 1
RBF_ENABLED = True
RBF_MIN_INCREMENT = 1.1

# ==============================================================================
# SYNC
# ==============================================================================
IBD_BATCH_SIZE = 500
IBD_PARALLEL_DOWNLOADS = 4
MAX_REORG_DEPTH = 100

# ==============================================================================
# WALLET
# ==============================================================================
WALLET_VERSION = 1
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
MIN_PASSWORD_LENGTH = 8

# ==============================================================================
# CRYPTOGRAPHY
# ==============================================================================
HASH_FUNCTION = "SHA3-256"
SIGNATURE_SCHEME = "SPHINCS+-SHAKE-128f"
SPHINCS_PUBLIC_KEY_SIZE = 32
SPHINCS_SECRET_KEY_SIZE = 64
SPHINCS_SIGNATURE_SIZE = 17088
KEY_ENCAPSULATION = "ML-KEM-768"

# ==============================================================================
# GENESIS (TBD at launch)
# ==============================================================================
GENESIS_TIMESTAMP_MS = 0             # Set at launch
GENESIS_BTC_HEIGHT = 0               # Set at launch
GENESIS_BTC_HASH = bytes(32)         # Set at launch
```

---

*Ɉ Montana Technical Specification v1.0*
*December 2025*
