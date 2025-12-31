# Ɉ Montana Technical Specification v1.0

December 31, 2025

---

## Part I: Protocol Overview

### 1.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ɉ MONTANA                                │
│                    Application Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Telegram │  │   Node   │  │   API    │  │ Storage  │        │
│  │   Bot    │  │          │  │ (RPC)    │  │ (SQLite) │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴─────────────┴─────────────┘               │
│                           │                                     │
├───────────────────────────┴─────────────────────────────────────┤
│                     PoT v6 Library                              │
│                    Protocol Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Layer 0 │  │ Layer 1 │  │ Layer 2 │  │ Crypto  │            │
│  │ Atomic  │  │   VDF   │  │ Bitcoin │  │ SPHINCS+│            │
│  │  Time   │  │  STARK  │  │ Anchor  │  │ SHA3    │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                         │
│  │  State  │  │Consensus│  │ Network │                         │
│  │ Machine │  │  Score  │  │ Gossip  │                         │
│  └─────────┘  └─────────┘  └─────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **PoT v6 as Library**: All cryptographic primitives, consensus, and state management from PoT v6
2. **Montana as Application**: Telegram bot, gamification, user-facing features
3. **Clean Separation**: Montana imports from `pot.*`, never modifies protocol

---

## Part II: Constants

### 2.1 Network Identification

```python
# Network
NETWORK_ID = 0x4D4F4E54           # "MONT" in ASCII hex
NETWORK_MAGIC = b'\x4d\x4f\x4e\x54'  # Magic bytes
PROTOCOL_VERSION = 1

# Ports
DEFAULT_P2P_PORT = 9333
DEFAULT_RPC_PORT = 8332
DEFAULT_WS_PORT = 9334
```

### 2.2 Token Parameters

```python
# Identity
NAME = "Montana"
SYMBOL = "Ɉ"
TICKER = "MONT"
DECIMALS = 0                      # Atomic unit is 1 second

# Supply (in seconds)
TOTAL_SUPPLY = 1_260_000_000      # 21 million minutes
MAX_SUPPLY = TOTAL_SUPPLY

# Emission
INITIAL_REWARD = 3000             # 50 minutes = 3000 seconds
HALVING_INTERVAL = 210_000        # Blocks per epoch
BLOCK_TIME = 600                  # 10 minutes in seconds
```

### 2.3 Participation Weights

```python
# Layer weights (must sum to 1.0)
LAYER_WEIGHT_SERVER = 0.50        # Full node operators
LAYER_WEIGHT_BOT = 0.30           # Telegram bot users
LAYER_WEIGHT_USER = 0.15          # Chico Time players
LAYER_WEIGHT_RESERVED = 0.05     # Future extension

# Participation frequencies (seconds)
BOT_FREQ_MIN = 60                 # 1 minute minimum
BOT_FREQ_MAX = 86400              # 1 day maximum
BOT_FREQ_DEFAULT = 3600           # 1 hour default
```

### 2.4 Chico Time Game

```python
# Game parameters
CHICO_TIME_OPTIONS = 5            # Number of time choices
CHICO_TIME_TOLERANCE_MS = 120_000 # ±2 minutes tolerance
CHICO_TIME_EXPIRY_MS = 30_000     # Challenge expires in 30s
CHICO_TIME_COOLDOWN_MS = 60_000   # 1 minute between games

# Scoring
CHICO_CORRECT_POINTS = 10
CHICO_WRONG_PENALTY = 2
CHICO_TIMEOUT_PENALTY = 5
```

### 2.5 Reputation (Five Fingers)

```python
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
```

### 2.6 HAL Humanity Tiers

```python
# Tier limits
MAX_APOSTLES_HARDWARE = 3         # Tier 1
MAX_APOSTLES_SOCIAL = 6           # Tier 2
MAX_APOSTLES_TIMELOCKED = 12      # Tier 3

# Weights
HUMANITY_WEIGHT_HARDWARE = 0.3
HUMANITY_WEIGHT_SOCIAL = 0.6
HUMANITY_WEIGHT_TIMELOCKED = 1.0

# Validity periods (seconds)
HARDWARE_PROOF_VALIDITY = 31_536_000     # 1 year
SOCIAL_PROOF_VALIDITY = 63_072_000       # 2 years
TIMELOCK_PROOF_VALIDITY = 126_144_000    # 4 years
```

### 2.7 Slashing

```python
# Penalties
ATTACKER_QUARANTINE_BLOCKS = 180_000     # ~3 years
VOUCHER_INTEGRITY_PENALTY = 0.25         # -25%
ASSOCIATE_INTEGRITY_PENALTY = 0.10       # -10%
MIN_INTEGRITY_FOR_HANDSHAKE = 0.50       # 50% minimum
```

---

## Part III: Data Structures

### 3.1 MontanaAccount

```python
@dataclass
class MontanaAccount:
    """Extended account with Montana-specific fields."""

    # Base (from PoT v6)
    pubkey: PublicKey              # 32 bytes (SPHINCS+ public key hash)
    balance: int                   # In seconds (Ɉ)
    nonce: int                     # Transaction counter

    # Participation
    layer0_heartbeats: int         # Server layer heartbeats
    layer1_heartbeats: int         # Bot layer heartbeats
    layer2_heartbeats: int         # User layer (Chico Time wins)
    last_participation_ms: int     # Last activity timestamp
    participation_frequency: int    # Chosen frequency (seconds)

    # Reputation (Five Fingers)
    first_seen_height: int         # Bitcoin height at registration
    violations: int                # Protocol violations count
    stored_blocks: int             # Blocks stored locally
    epochs_survived: int           # Bitcoin halvings survived

    # Trust (Twelve Apostles)
    apostles: List[PublicKey]      # Up to 12 trust bonds
    apostle_timestamps: List[int]  # When each bond was formed

    # HAL
    humanity_tier: int             # 0=NONE, 1=HARDWARE, 2=SOCIAL, 3=TIMELOCKED
    humanity_proof_expiry: int     # Proof expiration timestamp

    # Telegram
    telegram_id: Optional[int]     # Telegram user ID (if linked)
    telegram_username: Optional[str]
```

### 3.2 ParticipationProof

```python
@dataclass
class ParticipationProof:
    """Proof of participation in a layer."""

    layer: int                     # 0=SERVER, 1=BOT, 2=USER
    pubkey: PublicKey              # Participant's public key
    timestamp_ms: int              # When participation occurred

    # Layer-specific data
    layer0_data: Optional[HeartbeatData]      # For servers
    layer1_data: Optional[BotInteractionData] # For bot users
    layer2_data: Optional[ChicoTimeResult]    # For game players

    # Signature
    signature: Signature           # SPHINCS+ signature over proof
```

### 3.3 ChicoTimeChallenge

```python
@dataclass
class ChicoTimeChallenge:
    """Challenge for the Chico Time game."""

    challenge_id: Hash             # SHA3-256, 32 bytes
    participant: PublicKey         # Who is being challenged

    # Time options (5 choices)
    options: List[int]             # 5 timestamps in milliseconds
    correct_index: int             # Index of correct answer (0-4)

    # Timing
    created_at_ms: int             # Challenge creation time
    expires_at_ms: int             # Challenge expiration (+30s)

    # Atomic time reference
    atomic_proof: AtomicTimeProof  # From Layer 0
```

### 3.4 ChicoTimeResult

```python
@dataclass
class ChicoTimeResult:
    """Result of a Chico Time game."""

    challenge_id: Hash             # Reference to challenge
    participant: PublicKey         # Who played
    chosen_index: int              # User's choice (0-4)

    # Outcome
    correct: bool                  # Was the answer correct?
    response_time_ms: int          # How fast they answered
    points_earned: int             # Points gained/lost

    # Verification
    atomic_time_at_response: int   # Actual atomic time when responded
    within_tolerance: bool         # Within ±2 minutes?
```

### 3.5 TrustBond (Apostle)

```python
@dataclass
class TrustBond:
    """Mutual trust bond between two participants."""

    party_a: PublicKey             # First party
    party_b: PublicKey             # Second party

    # Formation
    btc_height_formed: int         # Bitcoin height when formed
    timestamp_formed: int          # Unix timestamp

    # Signatures (both parties must sign)
    signature_a: Signature         # Party A's signature
    signature_b: Signature         # Party B's signature

    # Status
    status: TrustBondStatus        # PENDING, ACTIVE, DISSOLVED
    dissolved_at: Optional[int]    # When dissolved (if applicable)
    dissolved_reason: Optional[str]
```

### 3.6 HeartbeatData

```python
@dataclass
class HeartbeatData:
    """Server heartbeat data."""

    # From PoT v6
    atomic_proof: AtomicTimeProof  # Layer 0
    vdf_proof: VDFProof            # Layer 1
    bitcoin_anchor: BitcoinAnchor  # Layer 2

    # Montana extensions
    layer_participation: int       # Which layer (0 for server)
    participation_weight: float    # Weight contribution
```

---

## Part IV: Telegram Bot Protocol

### 4.1 Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Register account, generate keypair | `/start` |
| `/time` | Play Chico Time game | `/time` |
| `/balance` | Check Ɉ balance | `/balance` |
| `/send` | Send Ɉ to user | `/send @user 100` |
| `/apostles` | Manage trust bonds | `/apostles` |
| `/stats` | View Five Fingers reputation | `/stats` |
| `/frequency` | Set participation frequency | `/frequency 1h` |
| `/export` | Export keypair (encrypted) | `/export` |
| `/import` | Import keypair | `/import <key>` |

### 4.2 Bot States (FSM)

```python
class BotState(IntEnum):
    IDLE = 0
    PLAYING_CHICO = 1
    AWAITING_SEND_AMOUNT = 2
    AWAITING_SEND_RECIPIENT = 3
    AWAITING_APOSTLE_CONFIRM = 4
    AWAITING_FREQUENCY_CHOICE = 5
    AWAITING_EXPORT_PASSWORD = 6
    AWAITING_IMPORT_KEY = 7
```

### 4.3 Chico Time Flow

```
User: /time

Bot: "Сколько на твоих часах, Чико?"

    [12:34]  [12:36]  [12:38]  [12:40]  [12:42]

    ⏱ 30 seconds remaining

User: [clicks 12:38]

Bot: ✅ Correct! +10 points
     Atomic time: 12:37:42
     Your answer: 12:38 (within ±2 min tolerance)

     Total Ɉ earned: 1,234
     Layer 2 rank: #456
```

### 4.4 Inline Keyboards

```python
# Chico Time options
chico_keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("12:34", callback_data="chico_0"),
        InlineKeyboardButton("12:36", callback_data="chico_1"),
        InlineKeyboardButton("12:38", callback_data="chico_2"),
        InlineKeyboardButton("12:40", callback_data="chico_3"),
        InlineKeyboardButton("12:42", callback_data="chico_4"),
    ]
])

# Frequency selection
frequency_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("1 min", callback_data="freq_60")],
    [InlineKeyboardButton("5 min", callback_data="freq_300")],
    [InlineKeyboardButton("1 hour", callback_data="freq_3600")],
    [InlineKeyboardButton("1 day", callback_data="freq_86400")],
])
```

### 4.5 Bot → Node Communication

```python
# WebSocket for real-time events
ws://node:9334/ws

# JSON-RPC for queries
POST http://node:8332/rpc

# Example: Submit participation proof
{
    "jsonrpc": "2.0",
    "method": "montana_submitParticipation",
    "params": {
        "layer": 2,
        "pubkey": "0x...",
        "challenge_id": "0x...",
        "chosen_index": 2,
        "signature": "0x..."
    },
    "id": 1
}
```

---

## Part V: Layer Integration

### 5.1 Using PoT v6

```python
# Core types
from pot.core.types import Hash, PublicKey, SecretKey, Signature, KeyPair

# Cryptography
from pot.crypto.hash import sha3_256, shake256, tagged_hash
from pot.crypto.sphincs import sphincs_keygen, sphincs_sign, sphincs_verify

# Layers
from pot.layers.layer0 import query_atomic_time, validate_atomic_time
from pot.layers.layer1 import compute_vdf, verify_vdf
from pot.layers.layer2 import query_bitcoin, get_current_epoch, is_epoch_boundary

# State
from pot.core.state import GlobalState, AccountState

# Consensus
from pot.consensus.score import compute_score, effective_score
```

### 5.2 Extended Heartbeat

```python
from pot.core.heartbeat import Heartbeat

@dataclass
class MontanaHeartbeat(Heartbeat):
    """Heartbeat with Montana participation proof."""

    # Inherited from Heartbeat
    pubkey: PublicKey
    atomic_proof: AtomicTimeProof
    vdf_proof: VDFProof
    bitcoin_anchor: BitcoinAnchor
    signature: Signature

    # Montana extension
    participation_layer: int       # 0, 1, or 2
    participation_proof: ParticipationProof
```

### 5.3 Account Mapping

```python
def pot_account_to_montana(pot_account: AccountState) -> MontanaAccount:
    """Convert PoT account to Montana account with extensions."""
    return MontanaAccount(
        pubkey=pot_account.pubkey,
        balance=pot_account.balance,
        nonce=pot_account.nonce,
        layer0_heartbeats=pot_account.epoch_heartbeats,  # Map heartbeats
        # ... initialize Montana-specific fields
    )
```

---

## Part VI: Reputation System

### 6.1 Five Fingers Score Calculation

```python
def compute_five_fingers(account: MontanaAccount, state: GlobalState) -> float:
    """Compute total reputation score."""

    # THUMB: TIME (50%)
    current_height = state.current_btc_height
    blocks_in_epoch = current_height % HALVING_INTERVAL
    time_score = min(blocks_in_epoch / TIME_SATURATION_BLOCKS, 1.0)

    # INDEX: INTEGRITY (20%)
    integrity_score = max(0.0, 1.0 - account.violations * 0.1)

    # MIDDLE: STORAGE (15%)
    if state.chain_height > 0:
        storage_score = account.stored_blocks / state.chain_height
    else:
        storage_score = 1.0

    # RING: EPOCHS (10%)
    epochs_score = min(account.epochs_survived / EPOCHS_SATURATION, 1.0)

    # PINKY: HANDSHAKE (5%)
    handshake_score = len(account.apostles) / MAX_APOSTLES

    # Weighted sum
    return (
        WEIGHT_TIME * time_score +
        WEIGHT_INTEGRITY * integrity_score +
        WEIGHT_STORAGE * storage_score +
        WEIGHT_EPOCHS * epochs_score +
        WEIGHT_HANDSHAKE * handshake_score
    )
```

### 6.2 Participation Score

```python
def compute_participation_score(account: MontanaAccount) -> float:
    """Compute layer participation score."""

    total_heartbeats = (
        account.layer0_heartbeats +
        account.layer1_heartbeats +
        account.layer2_heartbeats
    )

    if total_heartbeats == 0:
        return 0.0

    # Weighted by layer
    weighted_score = (
        LAYER_WEIGHT_SERVER * account.layer0_heartbeats +
        LAYER_WEIGHT_BOT * account.layer1_heartbeats +
        LAYER_WEIGHT_USER * account.layer2_heartbeats
    ) / total_heartbeats

    return weighted_score
```

### 6.3 Twelve Apostles Handshake Protocol

```python
async def initiate_handshake(
    initiator: KeyPair,
    target: PublicKey,
    state: GlobalState
) -> TrustBond:
    """Initiate a trust bond with another participant."""

    # Check prerequisites
    initiator_account = state.get_account(initiator.public)
    target_account = state.get_account(target)

    if len(initiator_account.apostles) >= MAX_APOSTLES:
        raise TooManyApostlesError()

    if initiator_account.integrity_score < MIN_INTEGRITY_FOR_HANDSHAKE:
        raise InsufficientIntegrityError()

    # Create bond request
    bond = TrustBond(
        party_a=initiator.public,
        party_b=target,
        btc_height_formed=state.current_btc_height,
        timestamp_formed=int(time.time()),
        status=TrustBondStatus.PENDING,
    )

    # Sign from initiator
    bond.signature_a = sphincs_sign(bond.serialize_unsigned(), initiator.secret)

    return bond


async def accept_handshake(
    bond: TrustBond,
    acceptor: KeyPair,
    state: GlobalState
) -> TrustBond:
    """Accept a pending trust bond."""

    if bond.party_b != acceptor.public:
        raise NotTargetError()

    # Sign from acceptor
    bond.signature_b = sphincs_sign(bond.serialize_unsigned(), acceptor.secret)
    bond.status = TrustBondStatus.ACTIVE

    return bond
```

---

## Part VII: API Specification

### 7.1 JSON-RPC Methods

#### Account Methods

| Method | Description |
|--------|-------------|
| `montana_getAccount` | Get account info |
| `montana_getBalance` | Get balance only |
| `montana_getReputation` | Get Five Fingers score |
| `montana_getApostles` | Get trust bonds |

#### Participation Methods

| Method | Description |
|--------|-------------|
| `montana_submitParticipation` | Submit participation proof |
| `montana_getChallenge` | Get new Chico Time challenge |
| `montana_submitChallengeResult` | Submit game result |
| `montana_getLeaderboard` | Get participation leaderboard |

#### Trust Methods

| Method | Description |
|--------|-------------|
| `montana_initiateHandshake` | Start trust bond |
| `montana_acceptHandshake` | Accept trust bond |
| `montana_dissolveHandshake` | End trust bond |

### 7.2 Example Requests

```json
// Get account
{
    "jsonrpc": "2.0",
    "method": "montana_getAccount",
    "params": ["0x1234..."],
    "id": 1
}

// Response
{
    "jsonrpc": "2.0",
    "result": {
        "pubkey": "0x1234...",
        "balance": 123456,
        "layer0_heartbeats": 100,
        "layer1_heartbeats": 500,
        "layer2_heartbeats": 50,
        "reputation": 0.75,
        "apostles_count": 8
    },
    "id": 1
}
```

```json
// Get Chico Time challenge
{
    "jsonrpc": "2.0",
    "method": "montana_getChallenge",
    "params": ["0x1234..."],
    "id": 2
}

// Response
{
    "jsonrpc": "2.0",
    "result": {
        "challenge_id": "0xabcd...",
        "options": [1735660440000, 1735660560000, 1735660680000, 1735660800000, 1735660920000],
        "expires_at": 1735660710000
    },
    "id": 2
}
```

### 7.3 WebSocket Events

```json
// New block
{
    "type": "new_block",
    "data": {
        "height": 12345,
        "hash": "0x...",
        "heartbeats_count": 50
    }
}

// Participation update
{
    "type": "participation_update",
    "data": {
        "pubkey": "0x...",
        "layer": 2,
        "points": 10
    }
}
```

---

## Part VIII: Security Considerations

### 8.1 Rate Limiting

```python
# Per-IP limits
MAX_RPC_REQUESTS_PER_MINUTE = 60
MAX_WS_MESSAGES_PER_MINUTE = 100

# Per-account limits
MAX_CHICO_GAMES_PER_HOUR = 30
MAX_PARTICIPATION_PROOFS_PER_MINUTE = 10
MAX_HANDSHAKE_REQUESTS_PER_DAY = 5
```

### 8.2 Anti-Spam (Personal PoW)

All transactions require Personal PoW from PoT v6:

```python
from pot.crypto.pow import compute_transaction_pow, verify_transaction_pow

# Difficulty scales with frequency
def get_spam_difficulty(account: MontanaAccount, state: GlobalState) -> int:
    base_difficulty = state.base_pow_difficulty

    # Higher frequency = higher difficulty
    time_since_last = time.time() - account.last_participation_ms / 1000
    if time_since_last < 60:  # Less than 1 minute
        return base_difficulty * 4
    elif time_since_last < 300:  # Less than 5 minutes
        return base_difficulty * 2

    return base_difficulty
```

### 8.3 Sybil Detection

```python
def detect_sybil_cluster(accounts: List[MontanaAccount]) -> float:
    """Detect correlated behavior indicating Sybil attack."""

    # Timing correlation
    timing_corr = compute_timing_correlation(accounts)

    # Action distribution similarity
    action_corr = compute_action_similarity(accounts)

    # Apostle overlap
    apostle_overlap = compute_apostle_overlap(accounts)

    # Combined score
    correlation = (
        0.5 * timing_corr +
        0.3 * action_corr +
        0.2 * apostle_overlap
    )

    return correlation  # > 0.7 indicates likely Sybil cluster
```

---

## Part IX: Test Vectors

### 9.1 Sample Account

```python
test_account = MontanaAccount(
    pubkey=PublicKey(bytes.fromhex("0123456789abcdef...")),
    balance=1_000_000,  # 1M seconds ≈ 11.5 days
    nonce=42,
    layer0_heartbeats=100,
    layer1_heartbeats=500,
    layer2_heartbeats=50,
    first_seen_height=840_000,
    violations=0,
    stored_blocks=10_000,
    epochs_survived=1,
    apostles=[...],  # 8 trust bonds
    humanity_tier=2,  # SOCIAL
)

# Expected reputation: ~0.72
expected_time_score = 0.5 * (850000 % 210000) / 210000  # ~0.24
expected_integrity_score = 0.2 * 1.0  # = 0.20
expected_storage_score = 0.15 * 0.8  # = 0.12
expected_epochs_score = 0.10 * 0.25  # = 0.025
expected_handshake_score = 0.05 * (8/12)  # = 0.033
# Total: ~0.618
```

### 9.2 Chico Time Challenge

```python
test_challenge = ChicoTimeChallenge(
    challenge_id=sha3_256(b"test_challenge_001"),
    participant=test_account.pubkey,
    options=[
        1735660440000,  # 12:34
        1735660560000,  # 12:36
        1735660680000,  # 12:38 (correct)
        1735660800000,  # 12:40
        1735660920000,  # 12:42
    ],
    correct_index=2,
    created_at_ms=1735660620000,  # 12:37
    expires_at_ms=1735660650000,  # +30s
)

# Atomic time at creation: 12:37:00
# Correct answer: 12:38 (within ±2 min of 12:37)
# Options spread: 2 minutes apart
```

### 9.3 Trust Bond

```python
test_bond = TrustBond(
    party_a=alice_pubkey,
    party_b=bob_pubkey,
    btc_height_formed=850_000,
    timestamp_formed=1735660000,
    signature_a=sphincs_sign(bond_data, alice_secret),
    signature_b=sphincs_sign(bond_data, bob_secret),
    status=TrustBondStatus.ACTIVE,
)

# Seniority bonus: Alice is node #1000, Bob is node #5000
# Alice→Bob handshake value: 1.0 (Bob is newer)
# Bob→Alice handshake value: 1 + log10(5000/1000) = 1.70
```

---

## Appendix A: File Structure

```
Montana/
├── WHITEPAPER.md
├── TECHNICAL_SPEC.md
├── README.md
├── requirements.txt
│
├── montana/
│   ├── __init__.py
│   ├── constants.py
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   ├── states.py
│   │   └── game.py
│   │
│   ├── layers/
│   │   ├── __init__.py
│   │   ├── layer0_server.py
│   │   ├── layer1_bot.py
│   │   └── layer2_user.py
│   │
│   ├── reputation/
│   │   ├── __init__.py
│   │   ├── five_fingers.py
│   │   ├── twelve_apostles.py
│   │   └── hal.py
│   │
│   ├── node/
│   │   ├── __init__.py
│   │   ├── node.py
│   │   ├── mempool.py
│   │   └── producer.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── methods.py
│   │
│   └── storage/
│       ├── __init__.py
│       └── database.py
│
└── tests/
    ├── __init__.py
    ├── test_bot.py
    ├── test_layers.py
    ├── test_reputation.py
    └── test_integration.py
```

---

## Appendix B: Dependencies

```
# requirements.txt

# Telegram
python-telegram-bot>=20.0
aiogram>=3.0.0

# PoT v6 (local)
-e ../PoT\ v6/

# Core
pycryptodome>=3.19.0
httpx>=0.25.0
aiosqlite>=0.19.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

*Ɉ Montana Technical Specification v1.0*
*December 2025*
