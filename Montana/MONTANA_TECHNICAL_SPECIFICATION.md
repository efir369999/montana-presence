# Ɉ MONTANA: TEMPORAL CONSENSUS GAMING PROTOCOL
# Complete Technical Specification v1.0
# Implementation Reference Document

================================================================================
DOCUMENT PURPOSE
================================================================================

This document provides complete specifications for implementing the Montana
protocol. It is designed to be self-sufficient: given only this document as
input, an implementation can be created from scratch.

Built on: Proof of Time: Asymptotic Trust Consensus (PoT:ATC v6)
Author: Alejandro Montana
Dedication: Hal Finney (1956-2014) — First Bitcoin recipient, RPOW creator.

================================================================================
TABLE OF CONTENTS
================================================================================

PART I:    ARCHITECTURE OVERVIEW
PART II:   CONSTANTS AND CONFIGURATION
PART III:  DATA STRUCTURES
PART IV:   LAYER 0 — SERVER NODES (Infrastructure)
PART V:    LAYER 1 — TELEGRAM BOTS (Aggregators)
PART VI:   LAYER 2 — END USERS (Participants)
PART VII:  TIME VERIFICATION GAME
PART VIII: REWARD DISTRIBUTION
PART IX:   ANTI-CHEAT SYSTEM
PART X:    TOKEN ECONOMICS
PART XI:   CRYPTOGRAPHIC PRIMITIVES
PART XII:  TELEGRAM BOT API INTEGRATION
PART XIII: NETWORK PROTOCOL
PART XIV:  VALIDATION RULES
PART XV:   STATE MACHINE
PART XVI:  GENESIS AND EMISSION
PART XVII: API SPECIFICATION
PART XVIII: ERROR HANDLING
PART XIX:  TEST VECTORS

================================================================================
PART I: ARCHITECTURE OVERVIEW
================================================================================

CORE CONCEPT: GAMIFIED TEMPORAL CONSENSUS
-----------------------------------------

Montana transforms time verification into an interactive game while maintaining
cryptographic integrity through PoT:ATC anchoring.

    User Engagement + Cryptographic Rigor = Montana

The architecture consists of three participation layers with weighted rewards:

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  LAYER 0: SERVER NODES                                                      │
│  ─────────────────────                                                      │
│  Weight: 0.50 (50% of rewards)                                              │
│  Purpose: Infrastructure, atomic time sync, validation                      │
│  Mechanism: Continuous time stream, Bitcoin anchoring                       │
│  Trust: T₀ = 0 (physical time observation)                                  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: TELEGRAM BOTS                                                     │
│  ──────────────────────                                                     │
│  Weight: 0.30 (30% of rewards)                                              │
│  Purpose: User aggregation, challenge delivery, proof batching              │
│  Mechanism: Telegram Bot API, batch submissions                             │
│  Trust: T₁(n) = 1/√n where n = verified interactions                       │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 2: END USERS                                                         │
│  ────────────────────                                                       │
│  Weight: 0.15 (15% of rewards)                                              │
│  Purpose: Time verification, game participation                             │
│  Mechanism: "What time is it, Chico?" challenge-response                    │
│  Trust: T₂(c) = 1/√c where c = correct verifications                       │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  RESERVE: DEVELOPMENT FUND                                                  │
│  ─────────────────────────                                                  │
│  Weight: 0.05 (5% of rewards)                                               │
│  Purpose: Protocol development, bug bounties, grants                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

FOUR ABSOLUTES (Inherited from PoT:ATC)
---------------------------------------

α (ALPHA): Time is sequential
    - VDF computation requires previous output
    - Cannot be parallelized with any amount of hardware

β (BETA): Time is universal
    - 34 atomic sources across 8 regions
    - Physical measurement, not cryptographic claim

γ (GAMMA): Time is irreversible
    - Bitcoin blocks are immutable
    - Epoch boundaries at halving events

δ (DELTA): Spam is personal
    - Each participant pays for their own excess
    - Rate limiting through verification frequency

================================================================================
PART II: CONSTANTS AND CONFIGURATION
================================================================================

# ==============================================================================
# LAYER 0: SERVER NODE CONSTANTS
# ==============================================================================

NODE_MIN_STAKE_MONT            = 1000_00000000    # 1,000 MONT (8 decimals)
NODE_SLASH_PERCENTAGE          = 10               # 10% slash for violations
NODE_MIN_UPTIME_PERCENT        = 95               # Minimum uptime for rewards
NODE_VALIDATION_TIMEOUT_MS     = 5000             # Max validation time
NODE_SYNC_INTERVAL_SEC         = 60               # Atomic time sync interval

# Inherited from PoT:ATC Layer 0
NTP_TOTAL_SOURCES              = 34               # Total atomic time sources
NTP_MIN_SOURCES_CONSENSUS      = 18               # >50% required
NTP_MIN_REGIONS_TOTAL          = 5                # Minimum distinct regions
NTP_QUERY_TIMEOUT_MS           = 2000             # Individual query timeout
NTP_MAX_DRIFT_MS               = 1000             # Maximum acceptable drift

# ==============================================================================
# LAYER 1: TELEGRAM BOT CONSTANTS
# ==============================================================================

BOT_MIN_STAKE_MONT             = 100_00000000     # 100 MONT (8 decimals)
BOT_MIN_ACTIVE_USERS           = 100              # Minimum users for rewards
BOT_BATCH_SIZE_MAX             = 1000             # Max proofs per batch
BOT_BATCH_INTERVAL_SEC         = 60               # Batch submission interval
BOT_SLASH_PERCENTAGE           = 20               # 20% slash for fraud

# ==============================================================================
# LAYER 2: USER CONSTANTS
# ==============================================================================

USER_MIN_ACCOUNT_AGE_DAYS      = 30               # Telegram account age
USER_MAX_DEVICE_DRIFT_MS       = 5000             # 5 seconds max drift
USER_RESPONSE_TIMEOUT_SEC      = 60               # Challenge response timeout
USER_CHALLENGE_OPTIONS         = 5                # Number of time options
USER_CHALLENGE_DRIFT_MINUTES   = 2                # ±2 minutes for options

# Frequency options (seconds between challenges)
FREQ_1_MINUTE                  = 60
FREQ_5_MINUTES                 = 300
FREQ_15_MINUTES                = 900
FREQ_1_HOUR                    = 3600
FREQ_6_HOURS                   = 21600
FREQ_24_HOURS                  = 86400

# ==============================================================================
# GAME MECHANICS CONSTANTS
# ==============================================================================

# Response time multipliers
RESPONSE_QUICK_THRESHOLD_SEC   = 5                # Quick response threshold
RESPONSE_STANDARD_THRESHOLD_SEC= 30               # Standard response threshold
RESPONSE_SLOW_THRESHOLD_SEC    = 60               # Slow response threshold

RESPONSE_QUICK_MULTIPLIER      = 1.5              # 1.5× for quick response
RESPONSE_STANDARD_MULTIPLIER   = 1.0              # 1.0× for standard
RESPONSE_SLOW_MULTIPLIER       = 0.5              # 0.5× for slow

# Streak multipliers
STREAK_TIER_1_MAX              = 10               # 1-10: 1.0×
STREAK_TIER_2_MAX              = 50               # 11-50: 1.2×
STREAK_TIER_3_MAX              = 100              # 51-100: 1.5×
STREAK_TIER_4_MAX              = 500              # 101-500: 2.0×
                                                   # 500+: 3.0×

STREAK_TIER_1_MULT             = 1.0
STREAK_TIER_2_MULT             = 1.2
STREAK_TIER_3_MULT             = 1.5
STREAK_TIER_4_MULT             = 2.0
STREAK_TIER_5_MULT             = 3.0

# ==============================================================================
# TOKEN ECONOMICS CONSTANTS
# ==============================================================================

TOKEN_NAME                     = "Montana"
TOKEN_SYMBOL                   = "MONT"
TOKEN_DECIMALS                 = 8
TOKEN_MAX_SUPPLY               = 21_000_000_00000000  # 21M MONT

INITIAL_BLOCK_REWARD           = 50_00000000      # 50 MONT per block
BLOCK_TIME_TARGET_SEC          = 60               # 1 minute blocks
HALVING_INTERVAL_BTC_BLOCKS    = 210000           # Follow BTC halvings

# Reward distribution weights (must sum to 1.0)
WEIGHT_LAYER_0                 = 0.50             # 50% to server nodes
WEIGHT_LAYER_1                 = 0.30             # 30% to bot operators
WEIGHT_LAYER_2                 = 0.15             # 15% to end users
WEIGHT_RESERVE                 = 0.05             # 5% to development fund

# ==============================================================================
# NETWORK CONSTANTS
# ==============================================================================

NETWORK_ID_MAINNET             = 0x4D4F4E54       # "MONT"
NETWORK_ID_TESTNET             = 0x54455354       # "TEST"
PROTOCOL_VERSION               = 1
MAX_BLOCK_SIZE_BYTES           = 4194304          # 4 MB
DEFAULT_PORT                   = 19657

# ==============================================================================
# CRYPTOGRAPHIC CONSTANTS (Inherited from PoT:ATC)
# ==============================================================================

HASH_FUNCTION                  = "SHA3-256"
SIGNATURE_SCHEME               = "SPHINCS+-SHAKE-128f"
VDF_HASH_FUNCTION              = "SHAKE256"
VDF_OUTPUT_BYTES               = 32

================================================================================
PART III: DATA STRUCTURES
================================================================================

# ==============================================================================
# 3.1 PRIMITIVE TYPES
# ==============================================================================

type u8    = unsigned 8-bit integer
type u16   = unsigned 16-bit integer
type u32   = unsigned 32-bit integer
type u64   = unsigned 64-bit integer
type i32   = signed 32-bit integer
type i64   = signed 64-bit integer
type f64   = 64-bit IEEE 754 float

type bytes[N] = fixed-size byte array of N bytes
type Vec<T>   = variable-length array of type T
type Map<K,V> = key-value mapping
type Option<T> = T or None

# ==============================================================================
# 3.2 IDENTITY TYPES
# ==============================================================================

struct TelegramUserId {
    id: i64                         # Telegram user ID
}
# SIZE: 8 bytes

struct TelegramBotId {
    id: i64                         # Telegram bot ID
    token_hash: bytes[32]           # SHA3-256(bot_token) for verification
}
# SIZE: 40 bytes

struct NodeId {
    pubkey: bytes[32]               # SPHINCS+ public key
}
# SIZE: 32 bytes

# ==============================================================================
# 3.3 TIME STRUCTURES
# ==============================================================================

struct AtomicTimestamp {
    milliseconds: u64               # Milliseconds since Unix epoch
    source_count: u16               # Number of atomic sources queried
    region_bitmap: u8               # Bitmask of responding regions
    drift_ms: i32                   # Drift from median
}
# SIZE: 15 bytes

struct DeviceTime {
    reported_ms: u64                # Device-reported timestamp
    drift_from_atomic_ms: i32       # Difference from atomic time
}
# SIZE: 12 bytes

# ==============================================================================
# 3.4 CHALLENGE STRUCTURES
# ==============================================================================

struct TimeChallenge {
    challenge_id: bytes[16]         # Unique challenge identifier
    bot_id: TelegramBotId           # Issuing bot
    user_id: TelegramUserId         # Target user
    atomic_time: AtomicTimestamp    # Atomic time at challenge creation
    correct_minute: u8              # Correct answer (0-59)
    options: [u8; 5]                # Shuffled options (minutes)
    created_at: u64                 # Challenge creation timestamp
    expires_at: u64                 # Challenge expiration timestamp
}
# SIZE: 40 + 15 + 13 + 8 = 76 bytes + padding

struct ChallengeResponse {
    challenge_id: bytes[16]         # Reference to challenge
    user_id: TelegramUserId         # Responding user
    selected_option: u8             # User's selection (0-4 index)
    response_time_ms: u64           # Time taken to respond
    device_time: DeviceTime         # User's device time
    is_correct: bool                # Validation result
}
# SIZE: 16 + 8 + 1 + 8 + 12 + 1 = 46 bytes

# ==============================================================================
# 3.5 PROOF STRUCTURES
# ==============================================================================

struct TimeProof {
    user_id: TelegramUserId         # 8 bytes
    bot_id: TelegramBotId           # 40 bytes
    challenge_id: bytes[16]         # 16 bytes
    atomic_time: AtomicTimestamp    # 15 bytes
    device_time: DeviceTime         # 12 bytes
    response_time_ms: u32           # 4 bytes
    is_correct: bool                # 1 byte
    streak_count: u32               # 4 bytes
    reward_multiplier: u16          # Fixed-point × 100 (e.g., 150 = 1.5×)
}
# SIZE: 100 bytes

struct ProofBatch {
    batch_id: bytes[16]             # Unique batch identifier
    bot_id: TelegramBotId           # Submitting bot
    epoch: u32                      # Montana epoch number
    btc_height: u64                 # Bitcoin reference height
    proofs: Vec<TimeProof>          # Individual proofs
    proof_count: u32                # Number of proofs
    merkle_root: bytes[32]          # Merkle root of proofs
    created_at: u64                 # Batch creation time
    bot_signature: bytes[17088]     # SPHINCS+ signature
}

# ==============================================================================
# 3.6 USER STATE
# ==============================================================================

struct UserState {
    user_id: TelegramUserId         # Telegram user ID
    total_challenges: u64           # Lifetime challenges received
    correct_responses: u64          # Lifetime correct answers
    current_streak: u32             # Current consecutive correct
    best_streak: u32                # All-time best streak
    total_rewards: u64              # Total MONT earned (atomic units)
    frequency_setting: u32          # Seconds between challenges
    last_challenge_at: u64          # Last challenge timestamp
    registered_at: u64              # First interaction timestamp
    banned_until: u64               # Ban expiration (0 if not banned)
    drift_violations: u16           # Count of drift violations
}

# ==============================================================================
# 3.7 BOT STATE
# ==============================================================================

struct BotState {
    bot_id: TelegramBotId           # Bot identifier
    operator_pubkey: bytes[32]      # Operator's public key
    stake_amount: u64               # Staked MONT
    active_users: u32               # Currently active users
    total_users: u32                # All-time users
    total_batches: u64              # Batches submitted
    total_proofs: u64               # Proofs processed
    total_rewards: u64              # Total MONT earned
    fraud_score: u16                # Accumulated fraud indicators
    registered_at: u64              # Registration timestamp
    last_batch_at: u64              # Last batch submission
    slashed: bool                   # Whether stake was slashed
}

# ==============================================================================
# 3.8 NODE STATE
# ==============================================================================

struct NodeState {
    node_id: NodeId                 # Node identifier
    stake_amount: u64               # Staked MONT
    uptime_percent: u16             # Uptime × 100 (e.g., 9950 = 99.50%)
    total_validations: u64          # Batches validated
    total_rewards: u64              # Total MONT earned
    last_atomic_sync: u64           # Last atomic time sync
    last_validation: u64            # Last batch validation
    registered_at: u64              # Registration timestamp
    slashed: bool                   # Whether stake was slashed
}

# ==============================================================================
# 3.9 BLOCK STRUCTURE
# ==============================================================================

struct BlockHeader {
    version: u32                    # Protocol version
    height: u64                     # Block height
    parent_hash: bytes[32]          # Previous block hash
    timestamp_ms: u64               # Atomic timestamp
    batches_root: bytes[32]         # Merkle root of proof batches
    rewards_root: bytes[32]         # Merkle root of reward distributions
    state_root: bytes[32]           # Global state root
    btc_height: u64                 # Bitcoin anchor height
    btc_hash: bytes[32]             # Bitcoin anchor hash
}

struct RewardDistribution {
    layer: u8                       # 0, 1, or 2
    recipient_type: u8              # Node, Bot, or User
    recipient_id: bytes[40]         # Recipient identifier
    amount: u64                     # MONT amount (atomic units)
    reason: u8                      # Reward reason code
}

struct Block {
    header: BlockHeader
    batches: Vec<ProofBatch>
    rewards: Vec<RewardDistribution>
    node_signatures: Vec<NodeSignature>
}

================================================================================
PART IV: LAYER 0 — SERVER NODES (Infrastructure)
================================================================================

PURPOSE
-------
Server nodes form the infrastructure backbone of Montana, inheriting atomic time
synchronization from PoT:ATC Layer 0 and adding batch validation capabilities.

NODE RESPONSIBILITIES
---------------------

1. ATOMIC TIME SYNCHRONIZATION
   - Query 34 atomic time sources every NODE_SYNC_INTERVAL_SEC
   - Maintain consensus timestamp for the network
   - Inherit W-MSR algorithm from PoT:ATC

2. BATCH VALIDATION
   - Receive ProofBatch submissions from Layer 1 bots
   - Validate all TimeProofs within batches
   - Check device drift, response times, streak calculations

3. BLOCK PRODUCTION
   - Aggregate validated batches into blocks
   - Calculate reward distributions
   - Anchor to Bitcoin blockchain

4. FRAUD DETECTION
   - Statistical analysis of bot submission patterns
   - Random audit challenges to bots
   - Slash stakes for detected fraud

NODE REGISTRATION
-----------------

fn register_node(
    pubkey: bytes[32],
    stake: u64,
    endpoint: String
) -> Result<NodeId, Error> {

    # Verify minimum stake
    if stake < NODE_MIN_STAKE_MONT:
        return Error::InsufficientStake

    # Verify pubkey is valid SPHINCS+ key
    if not is_valid_sphincs_pubkey(pubkey):
        return Error::InvalidPublicKey

    # Create node state
    node = NodeState {
        node_id: NodeId { pubkey },
        stake_amount: stake,
        uptime_percent: 10000,      # Start at 100%
        total_validations: 0,
        total_rewards: 0,
        last_atomic_sync: current_atomic_time(),
        last_validation: 0,
        registered_at: current_atomic_time(),
        slashed: false
    }

    state.nodes[node.node_id] = node
    return node.node_id
}

BATCH VALIDATION ALGORITHM
--------------------------

fn validate_batch(batch: ProofBatch, state: GlobalState) -> Result<(), Error> {

    # 1. Verify bot exists and is not slashed
    bot = state.bots.get(batch.bot_id)
    if bot is None:
        return Error::BotNotFound
    if bot.slashed:
        return Error::BotSlashed

    # 2. Verify bot signature
    message = serialize_batch_for_signing(batch)
    if not sphincs_verify(bot.operator_pubkey, message, batch.bot_signature):
        return Error::InvalidSignature

    # 3. Verify merkle root
    computed_root = merkle_root([hash_proof(p) for p in batch.proofs])
    if computed_root != batch.merkle_root:
        return Error::InvalidMerkleRoot

    # 4. Validate each proof
    for proof in batch.proofs:
        validate_time_proof(proof, state)?

    # 5. Statistical fraud checks
    fraud_score = compute_fraud_score(batch, state)
    if fraud_score > FRAUD_THRESHOLD:
        slash_bot(batch.bot_id, state)
        return Error::FraudDetected

    return Ok(())
}

fn validate_time_proof(proof: TimeProof, state: GlobalState) -> Result<(), Error> {

    # 1. Check device drift
    drift = abs(proof.device_time.drift_from_atomic_ms)
    if drift > USER_MAX_DEVICE_DRIFT_MS:
        return Error::ExcessiveDeviceDrift

    # 2. Verify response time is reasonable
    if proof.response_time_ms > USER_RESPONSE_TIMEOUT_SEC * 1000:
        return Error::ResponseTimeout
    if proof.response_time_ms < 100:  # Suspiciously fast
        return Error::SuspiciousResponseTime

    # 3. Verify reward multiplier calculation
    expected_mult = calculate_multiplier(
        proof.response_time_ms,
        proof.streak_count
    )
    if proof.reward_multiplier != expected_mult:
        return Error::InvalidMultiplier

    return Ok(())
}

================================================================================
PART V: LAYER 1 — TELEGRAM BOTS (Aggregators)
================================================================================

PURPOSE
-------
Telegram bots serve as the interface between infrastructure (Layer 0) and end
users (Layer 2), delivering challenges and aggregating proofs.

BOT RESPONSIBILITIES
--------------------

1. USER MANAGEMENT
   - Register new users
   - Track user state (streaks, frequency settings)
   - Enforce account age requirements

2. CHALLENGE DELIVERY
   - Generate time challenges at user-selected intervals
   - Present "What time is it, Chico?" interface
   - Record responses and calculate correctness

3. PROOF AGGREGATION
   - Collect TimeProofs from user interactions
   - Batch proofs for Layer 0 submission
   - Sign batches with operator key

4. REWARD DISTRIBUTION
   - Receive MONT allocations from blocks
   - Distribute to users based on participation
   - Handle withdrawal requests

BOT REGISTRATION
----------------

fn register_bot(
    bot_token_hash: bytes[32],
    operator_pubkey: bytes[32],
    stake: u64
) -> Result<TelegramBotId, Error> {

    # Verify minimum stake
    if stake < BOT_MIN_STAKE_MONT:
        return Error::InsufficientStake

    # Create bot ID
    bot_id = TelegramBotId {
        id: derive_bot_id(bot_token_hash),
        token_hash: bot_token_hash
    }

    # Create bot state
    bot = BotState {
        bot_id: bot_id,
        operator_pubkey: operator_pubkey,
        stake_amount: stake,
        active_users: 0,
        total_users: 0,
        total_batches: 0,
        total_proofs: 0,
        total_rewards: 0,
        fraud_score: 0,
        registered_at: current_atomic_time(),
        last_batch_at: 0,
        slashed: false
    }

    state.bots[bot_id] = bot
    return bot_id
}

CHALLENGE GENERATION
--------------------

fn generate_challenge(
    bot_id: TelegramBotId,
    user_id: TelegramUserId,
    atomic_time: AtomicTimestamp
) -> TimeChallenge {

    # Get correct minute from atomic time
    correct_minute = (atomic_time.milliseconds / 60000) % 60

    # Generate options: correct ± 1, ± 2 minutes
    options = [
        (correct_minute - 2 + 60) % 60,
        (correct_minute - 1 + 60) % 60,
        correct_minute,
        (correct_minute + 1) % 60,
        (correct_minute + 2) % 60
    ]

    # Shuffle options
    shuffle(options)

    # Generate unique challenge ID
    challenge_id = sha3_256(
        bot_id.id.to_bytes() ||
        user_id.id.to_bytes() ||
        atomic_time.milliseconds.to_bytes() ||
        random_bytes(8)
    )[0:16]

    return TimeChallenge {
        challenge_id: challenge_id,
        bot_id: bot_id,
        user_id: user_id,
        atomic_time: atomic_time,
        correct_minute: correct_minute,
        options: options,
        created_at: atomic_time.milliseconds,
        expires_at: atomic_time.milliseconds + (USER_RESPONSE_TIMEOUT_SEC * 1000)
    }
}

BATCH SUBMISSION
----------------

fn create_and_submit_batch(
    bot: BotState,
    proofs: Vec<TimeProof>,
    keypair: KeyPair
) -> Result<ProofBatch, Error> {

    if len(proofs) > BOT_BATCH_SIZE_MAX:
        return Error::BatchTooLarge

    if len(proofs) == 0:
        return Error::EmptyBatch

    # Get current Bitcoin anchor
    btc = query_bitcoin()

    # Compute merkle root
    proof_hashes = [sha3_256(serialize(p)) for p in proofs]
    root = merkle_root(proof_hashes)

    # Create batch
    batch = ProofBatch {
        batch_id: random_bytes(16),
        bot_id: bot.bot_id,
        epoch: get_current_epoch(),
        btc_height: btc.height,
        proofs: proofs,
        proof_count: len(proofs),
        merkle_root: root,
        created_at: current_atomic_time(),
        bot_signature: empty_signature()
    }

    # Sign batch
    message = serialize_batch_for_signing(batch)
    batch.bot_signature = sphincs_sign(keypair.secret, message)

    # Submit to Layer 0
    submit_to_nodes(batch)

    return batch
}

================================================================================
PART VI: LAYER 2 — END USERS (Participants)
================================================================================

PURPOSE
-------
End users participate in time verification challenges through Telegram bots,
earning MONT tokens for correct responses.

USER REGISTRATION
-----------------

fn register_user(
    user_id: TelegramUserId,
    telegram_account_age_days: u32,
    initial_frequency: u32
) -> Result<UserState, Error> {

    # Check account age requirement
    if telegram_account_age_days < USER_MIN_ACCOUNT_AGE_DAYS:
        return Error::AccountTooNew

    # Validate frequency setting
    if not is_valid_frequency(initial_frequency):
        return Error::InvalidFrequency

    user = UserState {
        user_id: user_id,
        total_challenges: 0,
        correct_responses: 0,
        current_streak: 0,
        best_streak: 0,
        total_rewards: 0,
        frequency_setting: initial_frequency,
        last_challenge_at: 0,
        registered_at: current_atomic_time(),
        banned_until: 0,
        drift_violations: 0
    }

    state.users[user_id] = user
    return user
}

fn is_valid_frequency(freq: u32) -> bool {
    return freq in [
        FREQ_1_MINUTE,
        FREQ_5_MINUTES,
        FREQ_15_MINUTES,
        FREQ_1_HOUR,
        FREQ_6_HOURS,
        FREQ_24_HOURS
    ]
}

USER CHALLENGE FLOW
-------------------

fn process_user_response(
    user: UserState,
    challenge: TimeChallenge,
    selected_index: u8,
    device_time: DeviceTime,
    response_time_ms: u32
) -> Result<TimeProof, Error> {

    # Check if challenge expired
    if current_atomic_time() > challenge.expires_at:
        return Error::ChallengeExpired

    # Check device drift
    if abs(device_time.drift_from_atomic_ms) > USER_MAX_DEVICE_DRIFT_MS:
        user.drift_violations += 1
        if user.drift_violations >= 10:
            ban_user(user, 24 * 3600 * 1000)  # 24 hour ban
        return Error::ExcessiveDeviceDrift

    # Determine correctness
    selected_minute = challenge.options[selected_index]
    is_correct = (selected_minute == challenge.correct_minute)

    # Update streak
    if is_correct:
        user.current_streak += 1
        user.correct_responses += 1
        if user.current_streak > user.best_streak:
            user.best_streak = user.current_streak
    else:
        user.current_streak = 0

    user.total_challenges += 1
    user.last_challenge_at = current_atomic_time()

    # Calculate multiplier
    multiplier = calculate_multiplier(response_time_ms, user.current_streak)

    # Create proof
    proof = TimeProof {
        user_id: user.user_id,
        bot_id: challenge.bot_id,
        challenge_id: challenge.challenge_id,
        atomic_time: challenge.atomic_time,
        device_time: device_time,
        response_time_ms: response_time_ms,
        is_correct: is_correct,
        streak_count: user.current_streak,
        reward_multiplier: multiplier
    }

    return proof
}

================================================================================
PART VII: TIME VERIFICATION GAME
================================================================================

CHALLENGE PRESENTATION
----------------------

The bot presents challenges in the following format:

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  🎬 Tony Montana asks:                                          │
│                                                                 │
│  "What time is it on your watch, Chico?"                        │
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │  14:32  │ │  14:35  │ │  14:33  │ │  14:31  │ │  14:34  │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│                                                                 │
│  ⏱️ Time remaining: 60 seconds                                  │
│  🔥 Current streak: 47                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

MULTIPLIER CALCULATION
----------------------

fn calculate_multiplier(response_time_ms: u32, streak: u32) -> u16 {
    # Response time multiplier
    response_mult: f64
    if response_time_ms < RESPONSE_QUICK_THRESHOLD_SEC * 1000:
        response_mult = RESPONSE_QUICK_MULTIPLIER
    elif response_time_ms < RESPONSE_STANDARD_THRESHOLD_SEC * 1000:
        response_mult = RESPONSE_STANDARD_MULTIPLIER
    elif response_time_ms < RESPONSE_SLOW_THRESHOLD_SEC * 1000:
        response_mult = RESPONSE_SLOW_MULTIPLIER
    else:
        response_mult = 0.0  # Timeout

    # Streak multiplier
    streak_mult: f64
    if streak <= STREAK_TIER_1_MAX:
        streak_mult = STREAK_TIER_1_MULT
    elif streak <= STREAK_TIER_2_MAX:
        streak_mult = STREAK_TIER_2_MULT
    elif streak <= STREAK_TIER_3_MAX:
        streak_mult = STREAK_TIER_3_MULT
    elif streak <= STREAK_TIER_4_MAX:
        streak_mult = STREAK_TIER_4_MULT
    else:
        streak_mult = STREAK_TIER_5_MULT

    # Combined multiplier (fixed-point × 100)
    combined = response_mult * streak_mult
    return u16(combined * 100)
}

BASE REWARDS BY FREQUENCY
-------------------------

fn get_base_reward(frequency: u32) -> u64 {
    # Rewards calibrated so daily total is equal regardless of frequency
    # Daily potential = 1.44 MONT

    match frequency:
        FREQ_1_MINUTE:   return 100000       # 0.001 MONT × 1440/day
        FREQ_5_MINUTES:  return 500000       # 0.005 MONT × 288/day
        FREQ_15_MINUTES: return 1500000      # 0.015 MONT × 96/day
        FREQ_1_HOUR:     return 6000000      # 0.060 MONT × 24/day
        FREQ_6_HOURS:    return 36000000     # 0.360 MONT × 4/day
        FREQ_24_HOURS:   return 144000000    # 1.440 MONT × 1/day
        _: return 0
}

================================================================================
PART VIII: REWARD DISTRIBUTION
================================================================================

PER-BLOCK REWARD CALCULATION
----------------------------

fn calculate_block_rewards(
    block: Block,
    state: GlobalState
) -> Vec<RewardDistribution> {

    rewards: Vec<RewardDistribution> = []

    # Get block reward based on BTC epoch
    btc_epoch = block.header.btc_height / HALVING_INTERVAL_BTC_BLOCKS
    block_reward = INITIAL_BLOCK_REWARD >> btc_epoch

    # Calculate layer allocations
    layer_0_pool = block_reward * WEIGHT_LAYER_0
    layer_1_pool = block_reward * WEIGHT_LAYER_1
    layer_2_pool = block_reward * WEIGHT_LAYER_2
    reserve_pool = block_reward * WEIGHT_RESERVE

    # === LAYER 0 DISTRIBUTION ===
    # Proportional to uptime and validations

    active_nodes = get_active_nodes(state)
    total_node_score = sum([node_score(n) for n in active_nodes])

    for node in active_nodes:
        share = node_score(node) / total_node_score
        amount = u64(layer_0_pool * share)
        rewards.push(RewardDistribution {
            layer: 0,
            recipient_type: RECIPIENT_NODE,
            recipient_id: node.node_id.pubkey,
            amount: amount,
            reason: REWARD_VALIDATION
        })

    # === LAYER 1 DISTRIBUTION ===
    # Proportional to verified proofs in block

    bot_proofs: Map<TelegramBotId, u64> = {}
    for batch in block.batches:
        correct_proofs = count([p for p in batch.proofs if p.is_correct])
        bot_proofs[batch.bot_id] += correct_proofs

    total_proofs = sum(bot_proofs.values())
    for bot_id, proofs in bot_proofs:
        share = proofs / total_proofs
        amount = u64(layer_1_pool * share)
        rewards.push(RewardDistribution {
            layer: 1,
            recipient_type: RECIPIENT_BOT,
            recipient_id: serialize(bot_id),
            amount: amount,
            reason: REWARD_AGGREGATION
        })

    # === LAYER 2 DISTRIBUTION ===
    # Proportional to individual proof rewards

    user_rewards: Map<TelegramUserId, u64> = {}
    for batch in block.batches:
        for proof in batch.proofs:
            if proof.is_correct:
                base = get_base_reward(get_user_frequency(proof.user_id))
                multiplied = base * proof.reward_multiplier / 100
                user_rewards[proof.user_id] += multiplied

    total_user_rewards = sum(user_rewards.values())
    scale_factor = layer_2_pool / total_user_rewards

    for user_id, raw_reward in user_rewards:
        amount = u64(raw_reward * scale_factor)
        rewards.push(RewardDistribution {
            layer: 2,
            recipient_type: RECIPIENT_USER,
            recipient_id: serialize(user_id),
            amount: amount,
            reason: REWARD_VERIFICATION
        })

    # === RESERVE ===
    rewards.push(RewardDistribution {
        layer: 255,  # Special layer for reserve
        recipient_type: RECIPIENT_RESERVE,
        recipient_id: RESERVE_ADDRESS,
        amount: reserve_pool,
        reason: REWARD_RESERVE
    })

    return rewards
}

fn node_score(node: NodeState) -> f64 {
    # Score based on uptime and validation count
    uptime_factor = node.uptime_percent / 10000.0
    validation_factor = sqrt(node.total_validations)
    return uptime_factor * validation_factor
}

================================================================================
PART IX: ANTI-CHEAT SYSTEM
================================================================================

DEVICE TIME MANIPULATION DETECTION
----------------------------------

fn detect_time_manipulation(
    proof: TimeProof,
    history: Vec<TimeProof>
) -> f64 {
    # Returns fraud probability 0.0 - 1.0

    fraud_score = 0.0

    # Check 1: Drift consistency
    # Legitimate devices have consistent drift
    if len(history) >= 10:
        recent_drifts = [p.device_time.drift_from_atomic_ms for p in history[-10:]]
        drift_variance = variance(recent_drifts)
        if drift_variance < 10:  # Suspiciously consistent
            fraud_score += 0.3

    # Check 2: Always correct with minimal drift
    if proof.device_time.drift_from_atomic_ms < 100 and proof.is_correct:
        correct_rate = count([p for p in history if p.is_correct]) / len(history)
        if correct_rate > 0.99 and len(history) > 100:
            fraud_score += 0.4

    # Check 3: Drift suddenly changed
    if len(history) >= 2:
        prev_drift = history[-1].device_time.drift_from_atomic_ms
        curr_drift = proof.device_time.drift_from_atomic_ms
        if abs(curr_drift - prev_drift) > 3000:  # >3 second jump
            fraud_score += 0.2

    return min(fraud_score, 1.0)
}

BOT AUTOMATION DETECTION
------------------------

fn detect_automation(
    proof: TimeProof,
    history: Vec<TimeProof>
) -> f64 {
    fraud_score = 0.0

    # Check 1: Response time too consistent
    if len(history) >= 20:
        response_times = [p.response_time_ms for p in history[-20:]]
        rt_variance = variance(response_times)
        if rt_variance < 1000:  # <1 second variance is suspicious
            fraud_score += 0.4

    # Check 2: Response time too fast
    if proof.response_time_ms < 500:  # <0.5 second
        fraud_score += 0.3

    # Check 3: Perfect timing pattern
    if len(history) >= 10:
        intervals = []
        for i in range(1, len(history[-10:])):
            interval = history[i].atomic_time.milliseconds - \
                       history[i-1].atomic_time.milliseconds
            intervals.append(interval)

        interval_variance = variance(intervals)
        if interval_variance < 100:  # Almost perfect intervals
            fraud_score += 0.3

    return min(fraud_score, 1.0)
}

SYBIL DETECTION
---------------

fn detect_sybil_cluster(
    user_ids: Vec<TelegramUserId>,
    proofs: Vec<TimeProof>
) -> Vec<Vec<TelegramUserId>> {
    # Returns clusters of suspected Sybil accounts

    clusters: Vec<Vec<TelegramUserId>> = []

    # Build similarity matrix
    similarity: Map<(TelegramUserId, TelegramUserId), f64> = {}

    for i in range(len(user_ids)):
        for j in range(i + 1, len(user_ids)):
            user_a = user_ids[i]
            user_b = user_ids[j]

            proofs_a = [p for p in proofs if p.user_id == user_a]
            proofs_b = [p for p in proofs if p.user_id == user_b]

            sim = compute_behavioral_similarity(proofs_a, proofs_b)
            similarity[(user_a, user_b)] = sim

    # Cluster using similarity threshold
    SYBIL_THRESHOLD = 0.9

    # Union-Find clustering
    parent: Map<TelegramUserId, TelegramUserId> = {}
    for uid in user_ids:
        parent[uid] = uid

    for (a, b), sim in similarity:
        if sim >= SYBIL_THRESHOLD:
            union(parent, a, b)

    # Extract clusters
    cluster_map: Map<TelegramUserId, Vec<TelegramUserId>> = {}
    for uid in user_ids:
        root = find(parent, uid)
        cluster_map.entry(root).or_default().push(uid)

    return [c for c in cluster_map.values() if len(c) > 1]
}

fn compute_behavioral_similarity(
    proofs_a: Vec<TimeProof>,
    proofs_b: Vec<TimeProof>
) -> f64 {
    # Compare response time distributions
    rt_a = [p.response_time_ms for p in proofs_a]
    rt_b = [p.response_time_ms for p in proofs_b]
    rt_sim = 1.0 - ks_test(rt_a, rt_b)  # Kolmogorov-Smirnov test

    # Compare drift distributions
    drift_a = [p.device_time.drift_from_atomic_ms for p in proofs_a]
    drift_b = [p.device_time.drift_from_atomic_ms for p in proofs_b]
    drift_sim = 1.0 - ks_test(drift_a, drift_b)

    # Compare activity patterns
    times_a = [p.atomic_time.milliseconds % 86400000 for p in proofs_a]
    times_b = [p.atomic_time.milliseconds % 86400000 for p in proofs_b]
    time_sim = 1.0 - ks_test(times_a, times_b)

    return (rt_sim + drift_sim + time_sim) / 3.0
}

STAKE SLASHING
--------------

fn slash_bot(bot_id: TelegramBotId, state: GlobalState, reason: SlashReason) {
    bot = state.bots[bot_id]

    slash_amount = bot.stake_amount * BOT_SLASH_PERCENTAGE / 100
    bot.stake_amount -= slash_amount
    bot.slashed = true

    # Transfer slashed amount to reserve
    state.reserve_balance += slash_amount

    # Log slashing event
    emit SlashEvent {
        bot_id: bot_id,
        amount: slash_amount,
        reason: reason,
        timestamp: current_atomic_time()
    }
}

fn slash_node(node_id: NodeId, state: GlobalState, reason: SlashReason) {
    node = state.nodes[node_id]

    slash_amount = node.stake_amount * NODE_SLASH_PERCENTAGE / 100
    node.stake_amount -= slash_amount
    node.slashed = true

    state.reserve_balance += slash_amount

    emit SlashEvent {
        node_id: node_id,
        amount: slash_amount,
        reason: reason,
        timestamp: current_atomic_time()
    }
}

================================================================================
PART X: TOKEN ECONOMICS
================================================================================

EMISSION SCHEDULE
-----------------

Montana follows Bitcoin's halving schedule:

┌─────────┬──────────────────┬──────────────┬────────────────┬───────────────┐
│ Epoch   │ BTC Block Range  │ Block Reward │ Daily Emission │ Total Supply  │
├─────────┼──────────────────┼──────────────┼────────────────┼───────────────┤
│ 0       │ 0 - 209,999      │ 50 MONT      │ 72,000 MONT    │ 10,500,000    │
│ 1       │ 210K - 419,999   │ 25 MONT      │ 36,000 MONT    │ 15,750,000    │
│ 2       │ 420K - 629,999   │ 12.5 MONT    │ 18,000 MONT    │ 18,375,000    │
│ 3       │ 630K - 839,999   │ 6.25 MONT    │ 9,000 MONT     │ 19,687,500    │
│ 4       │ 840K - 1,049,999 │ 3.125 MONT   │ 4,500 MONT     │ 20,343,750    │
│ ...     │ ...              │ ...          │ ...            │ ...           │
│ ∞       │ -                │ → 0          │ → 0            │ 21,000,000    │
└─────────┴──────────────────┴──────────────┴────────────────┴───────────────┘

fn get_block_reward(btc_height: u64) -> u64 {
    epoch = btc_height / HALVING_INTERVAL_BTC_BLOCKS
    return INITIAL_BLOCK_REWARD >> epoch
}

DISTRIBUTION WEIGHTS
--------------------

Per-block distribution:

┌────────────────┬────────┬─────────────────────────────────────────────────┐
│ Recipient      │ Weight │ Description                                     │
├────────────────┼────────┼─────────────────────────────────────────────────┤
│ Layer 0 Nodes  │ 50%    │ Infrastructure operators                        │
│ Layer 1 Bots   │ 30%    │ Bot operators (aggregators)                     │
│ Layer 2 Users  │ 15%    │ End users (verifiers)                           │
│ Reserve        │ 5%     │ Development, bounties, grants                   │
└────────────────┴────────┴─────────────────────────────────────────────────┘

STAKING REQUIREMENTS
--------------------

┌────────────────┬─────────────────┬─────────────────┬─────────────────────┐
│ Participant    │ Min Stake       │ Slash Rate      │ Slash Conditions    │
├────────────────┼─────────────────┼─────────────────┼─────────────────────┤
│ Server Node    │ 1,000 MONT      │ 10%             │ Downtime, invalid   │
│                │                 │                 │ validation          │
├────────────────┼─────────────────┼─────────────────┼─────────────────────┤
│ Telegram Bot   │ 100 MONT        │ 20%             │ Fraud detection,    │
│                │                 │                 │ fake proofs         │
├────────────────┼─────────────────┼─────────────────┼─────────────────────┤
│ End User       │ None            │ N/A             │ Ban for violations  │
└────────────────┴─────────────────┴─────────────────┴─────────────────────┘

================================================================================
PART XI: CRYPTOGRAPHIC PRIMITIVES
================================================================================

Inherited from PoT:ATC v6 with Montana-specific additions.

HASH FUNCTIONS
--------------

fn sha3_256(data: bytes) -> bytes[32]:
    """SHA3-256 per NIST FIPS 202"""
    return Keccak-1600(data, capacity=512, output_length=256)

SIGNATURES (SPHINCS+)
---------------------

fn sphincs_keygen() -> (bytes[32], bytes[64]):
    """Generate SPHINCS+-SHAKE-128f keypair per NIST FIPS 205"""
    return SPHINCS_SHAKE_128f.keygen()

fn sphincs_sign(sk: bytes[64], message: bytes) -> bytes[17088]:
    return SPHINCS_SHAKE_128f.sign(message, sk)

fn sphincs_verify(pk: bytes[32], message: bytes, sig: bytes[17088]) -> bool:
    return SPHINCS_SHAKE_128f.verify(message, sig, pk)

MERKLE TREE
-----------

fn merkle_root(hashes: Vec<bytes[32]>) -> bytes[32]:
    if len(hashes) == 0:
        return zeros(32)

    if len(hashes) == 1:
        return hashes[0]

    # Pad to power of 2
    while not is_power_of_two(len(hashes)):
        hashes.push(hashes[-1])

    # Build tree
    while len(hashes) > 1:
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] || hashes[i + 1]
            next_level.push(sha3_256(combined))
        hashes = next_level

    return hashes[0]

================================================================================
PART XII: TELEGRAM BOT API INTEGRATION
================================================================================

BOT SETUP
---------

1. Create bot via @BotFather
2. Obtain bot token
3. Register with Montana protocol (stake required)
4. Implement Montana Bot SDK

REQUIRED BOT COMMANDS
---------------------

/start          - Register user, show welcome message
/play           - Start/resume time verification game
/settings       - Configure verification frequency
/stats          - Show user statistics
/withdraw       - Withdraw MONT to external wallet
/help           - Show help message

INLINE KEYBOARD FOR CHALLENGES
------------------------------

fn create_challenge_keyboard(options: [u8; 5]) -> InlineKeyboardMarkup {
    buttons = []
    for i, minute in enumerate(options):
        time_str = format_time_option(minute)
        callback_data = f"answer:{i}"
        buttons.push(InlineKeyboardButton {
            text: time_str,
            callback_data: callback_data
        })

    return InlineKeyboardMarkup {
        inline_keyboard: [buttons]  # Single row
    }
}

fn format_time_option(minute: u8) -> str {
    # Get current hour from atomic time
    atomic = query_atomic_time()
    hour = (atomic.milliseconds / 3600000) % 24
    return f"{hour:02d}:{minute:02d}"
}

WEBHOOK HANDLER
---------------

async fn handle_callback_query(update: Update) {
    query = update.callback_query
    user_id = TelegramUserId { id: query.from.id }

    if query.data.starts_with("answer:"):
        selected_index = int(query.data.split(":")[1])

        # Get active challenge for user
        challenge = get_active_challenge(user_id)
        if challenge is None:
            await answer_callback_query(query.id, "Challenge expired!")
            return

        # Get device time from Telegram (approximate)
        device_time = DeviceTime {
            reported_ms: query.message.date * 1000,
            drift_from_atomic_ms: calculate_drift(query.message.date)
        }

        # Calculate response time
        response_time = current_atomic_time() - challenge.created_at

        # Process response
        result = process_user_response(
            get_user(user_id),
            challenge,
            selected_index,
            device_time,
            response_time
        )

        match result:
            Ok(proof):
                if proof.is_correct:
                    msg = f"✅ Correct! Streak: {proof.streak_count}"
                else:
                    msg = "❌ Wrong! Streak reset."
                await answer_callback_query(query.id, msg)
                queue_proof_for_batch(proof)

            Err(e):
                await answer_callback_query(query.id, f"Error: {e}")
}

================================================================================
PART XIII: NETWORK PROTOCOL
================================================================================

MESSAGE TYPES
-------------

0x01  NODE_HELLO         Node handshake
0x02  NODE_HELLO_ACK     Node handshake response
0x10  BATCH_SUBMIT       Bot submits proof batch
0x11  BATCH_ACK          Node acknowledges batch
0x12  BATCH_REJECT       Node rejects batch (with reason)
0x20  BLOCK_ANNOUNCE     New block announcement
0x21  GET_BLOCK          Request block by height/hash
0x22  BLOCK_RESPONSE     Block data response
0x30  STATE_SYNC         State synchronization
0x40  AUDIT_CHALLENGE    Random audit from node to bot
0x41  AUDIT_RESPONSE     Bot response to audit

NODE-TO-NODE PROTOCOL
---------------------

# Inherited from PoT:ATC v6 with Montana extensions

struct NodeMessage {
    magic: bytes[4]         # 0x4D4F4E54 ("MONT")
    type: u8
    length: u32
    checksum: bytes[4]
    payload: bytes
}

BOT-TO-NODE PROTOCOL
--------------------

struct BotMessage {
    magic: bytes[4]         # 0x4D4F4E54 ("MONT")
    bot_id: TelegramBotId
    type: u8
    length: u32
    payload: bytes
    signature: bytes[17088] # SPHINCS+ signature
}

================================================================================
PART XIV: VALIDATION RULES
================================================================================

TIME PROOF VALIDATION CHECKLIST
-------------------------------

[ ] User ID exists and is not banned
[ ] Bot ID exists and is not slashed
[ ] Challenge ID matches known challenge
[ ] Challenge not expired
[ ] Device drift within USER_MAX_DEVICE_DRIFT_MS
[ ] Response time within timeout
[ ] Response time >= 100ms (not suspiciously fast)
[ ] Reward multiplier correctly calculated
[ ] Streak count matches user state

PROOF BATCH VALIDATION CHECKLIST
--------------------------------

[ ] Batch size <= BOT_BATCH_SIZE_MAX
[ ] Batch not empty
[ ] Bot ID exists and is not slashed
[ ] Bot has minimum stake
[ ] Merkle root matches computed root
[ ] Bot signature valid (SPHINCS+)
[ ] All individual proofs valid
[ ] No duplicate challenge IDs
[ ] Fraud score below threshold

BLOCK VALIDATION CHECKLIST
--------------------------

[ ] Version matches protocol version
[ ] Height = parent height + 1
[ ] Parent hash correct
[ ] Timestamp > parent timestamp
[ ] Bitcoin anchor valid
[ ] All batches valid
[ ] Batches merkle root correct
[ ] Rewards correctly calculated
[ ] Rewards merkle root correct
[ ] State root correct after applying
[ ] Node signatures valid (>50% stake)

================================================================================
PART XV: STATE MACHINE
================================================================================

APPLY TIME PROOF
----------------

fn apply_time_proof(state: GlobalState, proof: TimeProof) -> GlobalState {
    user = state.users[proof.user_id]

    user.total_challenges += 1

    if proof.is_correct:
        user.correct_responses += 1
        user.current_streak = proof.streak_count
        if proof.streak_count > user.best_streak:
            user.best_streak = proof.streak_count
    else:
        user.current_streak = 0

    user.last_challenge_at = proof.atomic_time.milliseconds

    state.users[proof.user_id] = user
    return state
}

APPLY PROOF BATCH
-----------------

fn apply_batch(state: GlobalState, batch: ProofBatch) -> GlobalState {
    bot = state.bots[batch.bot_id]

    bot.total_batches += 1
    bot.total_proofs += batch.proof_count
    bot.last_batch_at = batch.created_at

    for proof in batch.proofs:
        state = apply_time_proof(state, proof)

    state.bots[batch.bot_id] = bot
    return state
}

APPLY REWARD
------------

fn apply_reward(state: GlobalState, reward: RewardDistribution) -> GlobalState {
    match reward.layer:
        0:  # Node reward
            node_id = NodeId { pubkey: reward.recipient_id[0:32] }
            state.nodes[node_id].total_rewards += reward.amount

        1:  # Bot reward
            bot_id = deserialize_bot_id(reward.recipient_id)
            state.bots[bot_id].total_rewards += reward.amount

        2:  # User reward
            user_id = deserialize_user_id(reward.recipient_id)
            state.users[user_id].total_rewards += reward.amount

        255:  # Reserve
            state.reserve_balance += reward.amount

    state.total_supply += reward.amount
    return state
}

APPLY BLOCK
-----------

fn apply_block(state: GlobalState, block: Block) -> GlobalState {
    # Apply batches
    for batch in block.batches:
        state = apply_batch(state, batch)

    # Apply rewards
    for reward in block.rewards:
        state = apply_reward(state, reward)

    # Update chain state
    state.chain_height = block.header.height
    state.chain_tip_hash = block_hash(block)
    state.btc_height = block.header.btc_height
    state.btc_hash = block.header.btc_hash

    return state
}

================================================================================
PART XVI: GENESIS AND EMISSION
================================================================================

GENESIS BLOCK
-------------

GENESIS_BLOCK = Block {
    header: BlockHeader {
        version: 1,
        height: 0,
        parent_hash: zeros(32),
        timestamp_ms: <LAUNCH_TIMESTAMP>,
        batches_root: zeros(32),
        rewards_root: zeros(32),
        state_root: <EMPTY_STATE_ROOT>,
        btc_height: <BTC_HEIGHT_AT_LAUNCH>,
        btc_hash: <BTC_HASH_AT_LAUNCH>
    },
    batches: [],
    rewards: [],
    node_signatures: []
}

GENESIS STATE
-------------

GENESIS_STATE = GlobalState {
    chain_height: 0,
    chain_tip_hash: block_hash(GENESIS_BLOCK),
    btc_height: <BTC_HEIGHT_AT_LAUNCH>,
    btc_hash: <BTC_HASH_AT_LAUNCH>,
    total_supply: 0,
    reserve_balance: 0,
    nodes: {},
    bots: {},
    users: {}
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

# Nodes
getNode(pubkey: string) -> NodeState
getActiveNodes() -> NodeState[]
registerNode(pubkey: string, stake: number) -> NodeId

# Bots
getBot(bot_id: string) -> BotState
getActiveBots() -> BotState[]
registerBot(token_hash: string, pubkey: string, stake: number) -> BotId
submitBatch(batch: ProofBatch) -> BatchResult

# Users
getUser(user_id: number) -> UserState
getUserStats(user_id: number) -> UserStats
getLeaderboard(limit: number) -> LeaderboardEntry[]

# Game
getActiveChallenge(user_id: number) -> TimeChallenge | null
submitResponse(challenge_id: string, selected: number) -> TimeProof

# Token
getBalance(address: string) -> number
getTotalSupply() -> number
getCirculatingSupply() -> number

================================================================================
PART XVIII: ERROR HANDLING
================================================================================

ERROR CODES
-----------

1xxx - General errors
1000  UNKNOWN_ERROR
1001  INVALID_PARAMETER
1002  INTERNAL_ERROR

2xxx - Node errors
2001  NODE_NOT_FOUND
2002  NODE_SLASHED
2003  INSUFFICIENT_NODE_STAKE
2004  NODE_VALIDATION_FAILED

3xxx - Bot errors
3001  BOT_NOT_FOUND
3002  BOT_SLASHED
3003  INSUFFICIENT_BOT_STAKE
3004  BATCH_TOO_LARGE
3005  EMPTY_BATCH
3006  INVALID_BATCH_SIGNATURE
3007  FRAUD_DETECTED

4xxx - User errors
4001  USER_NOT_FOUND
4002  USER_BANNED
4003  ACCOUNT_TOO_NEW
4004  INVALID_FREQUENCY
4005  EXCESSIVE_DEVICE_DRIFT
4006  CHALLENGE_EXPIRED
4007  SUSPICIOUS_RESPONSE_TIME

5xxx - Proof errors
5001  INVALID_PROOF
5002  DUPLICATE_CHALLENGE
5003  INVALID_MULTIPLIER
5004  MERKLE_ROOT_MISMATCH

6xxx - Block errors
6001  INVALID_VERSION
6002  INVALID_HEIGHT
6003  INVALID_PARENT_HASH
6004  INVALID_BITCOIN_ANCHOR
6005  INSUFFICIENT_SIGNATURES

================================================================================
PART XIX: TEST VECTORS
================================================================================

CHALLENGE GENERATION TEST
-------------------------

Input:
    atomic_time.milliseconds = 1735660800000  # 2025-01-01 00:00:00 UTC
    user_id = 123456789
    bot_id = 987654321

Expected:
    correct_minute = 0  # (1735660800000 / 60000) % 60 = 0
    options (before shuffle) = [58, 59, 0, 1, 2]

MULTIPLIER CALCULATION TEST
---------------------------

Test 1:
    response_time_ms = 3000  # 3 seconds (quick)
    streak = 5
    Expected: 150  # 1.5 × 1.0 × 100

Test 2:
    response_time_ms = 15000  # 15 seconds (standard)
    streak = 75
    Expected: 150  # 1.0 × 1.5 × 100

Test 3:
    response_time_ms = 45000  # 45 seconds (slow)
    streak = 250
    Expected: 100  # 0.5 × 2.0 × 100

Test 4:
    response_time_ms = 2000  # 2 seconds (quick)
    streak = 600
    Expected: 450  # 1.5 × 3.0 × 100

REWARD DISTRIBUTION TEST
------------------------

Input:
    block_reward = 50_00000000  # 50 MONT
    active_nodes = 10 (equal score)
    active_bots = 5 (equal proofs)
    active_users = 100 (equal rewards)

Expected:
    layer_0_pool = 25_00000000  # 25 MONT
    per_node = 2_50000000       # 2.5 MONT each

    layer_1_pool = 15_00000000  # 15 MONT
    per_bot = 3_00000000        # 3 MONT each

    layer_2_pool = 7_50000000   # 7.5 MONT
    per_user = 7500000          # 0.075 MONT each

    reserve = 2_50000000        # 2.5 MONT

================================================================================
END OF SPECIFICATION
================================================================================

Version: 1.0.0
Date: December 2025
Status: COMPLETE
Built on: Proof of Time: Asymptotic Trust Consensus v6

Hash: SHA3-256(this_document)

"What time is it on your watch, Chico?"

Dedicated to Hal Finney (1956-2014)
"Running bitcoin" — January 11, 2009

Ɉ
