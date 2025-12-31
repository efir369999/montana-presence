"""
Proof of Time - Configuration Module
Production-grade configuration with validation and environment support.

Time is the ultimate proof.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum, auto
import json
import logging

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure production logging with rotation support."""
    logger = logging.getLogger("proof_of_time")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=50*1024*1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# ============================================================================
# PROTOCOL CONSTANTS (IMMUTABLE)
# ============================================================================

class ProtocolConstants:
    """Immutable protocol constants - changing these breaks consensus."""

    # Dual-layer timing
    # PoH layer: fast blocks (1 second)
    POH_SLOT_TIME: int = 1  # 1 second per PoH slot
    POH_TICKS_PER_SLOT: int = 64  # Ticks per slot
    POH_HASHES_PER_TICK: int = 12500  # Hash operations per tick

    # PoT layer: finality checkpoints (10 minutes)
    POT_CHECKPOINT_INTERVAL: int = 600  # 600 PoH slots = 10 minutes
    POT_VDF_TIME: int = 600  # VDF computation time (10 minutes)

    # Legacy (PoT blocks for halving calculation)
    BLOCK_INTERVAL: int = 600  # 10 minutes in seconds
    HALVING_INTERVAL: int = 210_000  # Blocks per halving epoch
    MAX_BLOCKS: int = 6_930_000  # Total blocks (33 halvings)
    
    # Rewards (in seconds)
    INITIAL_REWARD: int = 3000  # 50 minutes
    MIN_FEE: int = 1  # 1 second minimum
    
    # Total supply
    TOTAL_SUPPLY: int = 1_260_000_000  # 21 million minutes in seconds
    
    # Consensus weights
    W_TIME: float = 0.60
    W_SPACE: float = 0.20
    W_REP: float = 0.20
    
    # Saturation thresholds
    K_TIME: int = 15_552_000  # 180 days in seconds
    K_SPACE: float = 0.80  # 80% of chain history
    K_REP: int = 2016  # Signed blocks for max reputation
    
    # Network
    # SECURITY NOTE: MIN_NODES increased from 3 to 12 for production BFT
    # BFT requires n >= 3f+1 where f is max Byzantine nodes
    # With f=3 (tolerate 3 malicious), need n >= 10
    # Using 12 for safety margin and better decentralization
    MIN_NODES: int = 12
    ADJUSTMENT_WINDOW: int = 2016  # Blocks for difficulty adjustment
    QUARANTINE_BLOCKS: int = 26_000  # ~180 days penalty
    
    # Privacy
    RING_SIZE: int = 16  # Ring signature anonymity set
    MIN_RING_SIZE: int = 2  # Minimum ring size for valid transactions
    
    # Cryptographic parameters
    VDF_MODULUS_BITS: int = 2048
    HASH_SIZE: int = 32  # SHA-256 output
    SIGNATURE_SIZE: int = 64  # Ed25519 signature
    PUBLIC_KEY_SIZE: int = 32  # Ed25519 public key
    
    # Protocol versioning
    PROTOCOL_VERSION: int = 1
    MAGIC_BYTES: bytes = b'\xf9\xbe\xb4\xd9'
    
    # Genesis timestamp (2025-12-25 00:00:00 UTC)
    GENESIS_TIMESTAMP: int = 1735084800


class NetworkType(IntEnum):
    """Network type enumeration."""
    MAINNET = auto()
    TESTNET = auto()
    REGTEST = auto()


# ============================================================================
# RUNTIME CONFIGURATION
# ============================================================================

@dataclass
class NetworkConfig:
    """Network-specific configuration."""
    network_type: NetworkType = NetworkType.MAINNET
    default_port: int = 8333
    max_peers: int = 125
    connection_timeout: int = 30
    handshake_timeout: int = 10
    ping_interval: int = 120
    max_message_size: int = 32 * 1024 * 1024  # 32 MB
    
    # DNS seeds for peer discovery
    dns_seeds: list = field(default_factory=lambda: [
        "seed1.proofoftime.network",
        "seed2.proofoftime.network",
        "seed3.proofoftime.network",
    ])
    
    def __post_init__(self):
        if self.network_type == NetworkType.TESTNET:
            self.default_port = 18333
        elif self.network_type == NetworkType.REGTEST:
            self.default_port = 18444


@dataclass
class VDFConfig:
    """
    VDF computation configuration.

    IMPORTANT: VDF computation requires 2T sequential squarings:
    - Phase 1: T squarings to compute y = g^(2^T)
    - Phase 2: T squarings to compute proof π = g^(2^T/l)

    The 'iterations' parameter is T. Total time = 2T/ips seconds.

    SECURITY CONSIDERATIONS (ASIC/Quantum):

    1. ASIC RESISTANCE:
       - Wesolowski VDF uses RSA group squarings which are inherently sequential
       - ASIC can accelerate individual squarings by ~10x vs CPU
       - MITIGATION: Dynamic calibration adjusts iterations to maintain 10-min target
       - If ASICs appear, network automatically increases iterations
       - WARNING: An attacker with ASIC advantage could pre-compute VDFs

    2. QUANTUM COMPUTING:
       - Shor's algorithm breaks RSA in polynomial time
       - A quantum computer with ~4000 logical qubits could factor 2048-bit RSA
       - MITIGATION TIMELINE: ~10-15 years until cryptographically relevant QC
       - FUTURE UPGRADE: Migrate to quantum-resistant VDF (isogeny-based or lattice)

    3. CURRENT SAFETY:
       - 2048-bit RSA modulus provides ~112-bit classical security
       - Trusted setup ensures nobody knows factorization
       - Pre-computation protection: VDF input includes recent block hash

    4. RECOMMENDED MONITORING:
       - Track VDF completion times across network
       - Alert if any node consistently completes VDFs faster than expected
       - Consider increasing modulus_bits to 3072 for higher security margin
    """
    # Base iterations T (will be calibrated dynamically if auto_calibrate=True)
    # Default: ~15M iterations ≈ 5 minutes per phase ≈ 10 minutes total @ 50k ips
    iterations: int = 15_000_000

    # Modulus configuration
    modulus_bits: int = 2048

    # Performance options
    parallel_verify: bool = True
    cache_proofs: bool = True

    # Dynamic calibration
    auto_calibrate: bool = True  # Calibrate on startup
    calibration_sample: int = 50_000  # Iterations for calibration

    # Timing targets (seconds) - used when auto_calibrate=True
    # Note: This is TOTAL time including proof computation
    target_compute_time: float = 540.0  # Target 9 minutes (10 min block - 1 min margin)
    min_compute_time: float = 300.0  # Minimum 5 minutes
    max_compute_time: float = 600.0  # Maximum 10 minutes

    # Checkpointing
    checkpoint_enabled: bool = True
    checkpoint_interval: int = 1_000_000  # Save state every 1M iterations
    checkpoint_dir: str = "vdf_checkpoints"
    
    # Pre-computation protection
    # VDF input must include recent block hash (within this many blocks)
    max_input_age_blocks: int = 1  # Input must be from previous block

    def get_iterations_for_time(self, target_seconds: float, ips: float) -> int:
        """
        Calculate iterations T needed for target TOTAL time.
        
        Args:
            target_seconds: Target total computation time (2T squarings)
            ips: Measured iterations per second
            
        Returns:
            Iterations T such that 2T/ips ≈ target_seconds
        """
        # 2T = ips * target_seconds => T = ips * target_seconds / 2
        return max(1000, int(ips * target_seconds / 2))
    
    def validate_time(self, actual_seconds: float) -> bool:
        """Check if computation time is within acceptable bounds."""
        return self.min_compute_time <= actual_seconds <= self.max_compute_time


@dataclass
class StorageConfig:
    """Database and storage configuration."""
    db_path: str = "blockchain.db"
    blocks_dir: str = "blocks"
    chainstate_dir: str = "chainstate"
    
    # Performance
    cache_size_mb: int = 512
    write_buffer_mb: int = 64
    max_open_files: int = 1000
    
    # Pruning (optional)
    prune_enabled: bool = False
    prune_target_mb: int = 10_000


@dataclass
class MempoolConfig:
    """Transaction mempool configuration."""
    max_size_mb: int = 300
    max_tx_count: int = 50_000
    min_fee_rate: int = 1  # Seconds per KB
    expiry_hours: int = 336  # 2 weeks

    # Replace-by-fee
    rbf_enabled: bool = True
    rbf_min_increment: float = 1.1  # 10% fee increase


@dataclass
class CryptoConfig:
    """
    Cryptographic backend configuration.

    Supports switching between:
    - LEGACY: Ed25519 + SHA-256 + Wesolowski VDF (pre-quantum)
    - POST_QUANTUM: SPHINCS+ + SHA3-256 + SHAKE256/STARK VDF
    - HYBRID: Both signatures for transition period

    QUANTUM RESISTANCE NOTES:

    1. CURRENT VULNERABILITY (LEGACY mode):
       - Ed25519 signatures: BROKEN by Shor's algorithm
       - Wesolowski VDF (RSA): BROKEN by Shor's algorithm
       - SHA-256: Weakened to ~128-bit by Grover (still usable)

    2. POST-QUANTUM MODE:
       - SPHINCS+ (NIST FIPS 205): Hash-based, quantum-resistant
       - SHA3-256 (NIST FIPS 202): Quantum-resistant (Grover gives sqrt speedup)
       - SHAKE256 VDF + STARK: Hash-based, quantum-resistant
       - ML-KEM/Kyber (NIST FIPS 203): Lattice-based key encapsulation

    3. MIGRATION STRATEGY:
       - Phase 1: Use HYBRID mode (both signatures)
       - Phase 2: Announce deprecation of LEGACY
       - Phase 3: Switch to POST_QUANTUM only

    4. PERFORMANCE IMPACT:
       - SPHINCS+ signatures: ~17KB vs 64B (Ed25519)
       - SPHINCS+ signing: ~100ms vs <1ms (Ed25519)
       - SPHINCS+ verify: ~10ms vs <1ms (Ed25519)
       - Blocks will be larger due to signature size
    """
    # Backend selection: "legacy", "post_quantum", or "hybrid"
    backend: str = "legacy"

    # SPHINCS+ variant: "fast" (~17KB sigs) or "secure" (~29KB sigs)
    sphincs_variant: str = "fast"

    # Hybrid mode: require BOTH signatures to verify (True) or EITHER (False)
    hybrid_require_both: bool = False

    # VDF backend: "wesolowski" (legacy RSA) or "shake256" (post-quantum)
    vdf_backend: str = "wesolowski"

    # Enable STARK proofs for SHAKE256 VDF (requires Winterfell)
    stark_proofs_enabled: bool = True

    # Checkpoint interval for STARK proof generation
    stark_checkpoint_interval: int = 1000

    def get_crypto_backend(self):
        """Get CryptoBackend enum value."""
        from pantheon.prometheus.crypto_provider import CryptoBackend

        backend_map = {
            "legacy": CryptoBackend.LEGACY,
            "post_quantum": CryptoBackend.POST_QUANTUM,
            "hybrid": CryptoBackend.HYBRID,
        }
        return backend_map.get(self.backend.lower(), CryptoBackend.LEGACY)

    def initialize_provider(self):
        """Initialize and return the configured crypto provider."""
        from pantheon.prometheus.crypto_provider import (
            get_crypto_provider, set_default_backend
        )

        backend = self.get_crypto_backend()
        set_default_backend(backend)
        return get_crypto_provider(backend)


@dataclass
class NodeConfig:
    """Complete node configuration."""
    # Sub-configurations
    network: NetworkConfig = field(default_factory=NetworkConfig)
    vdf: VDFConfig = field(default_factory=VDFConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    mempool: MempoolConfig = field(default_factory=MempoolConfig)
    crypto: CryptoConfig = field(default_factory=CryptoConfig)
    
    # Node identity
    data_dir: str = "~/.proofoftime"
    node_name: str = "PoT-Node"
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Features
    enable_mining: bool = True
    enable_wallet: bool = True
    enable_rpc: bool = True
    rpc_port: int = 8332
    rpc_bind: str = "127.0.0.1"
    
    @classmethod
    def from_file(cls, path: str) -> 'NodeConfig':
        """Load configuration from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls._from_dict(data)
    
    @classmethod
    def from_env(cls) -> 'NodeConfig':
        """Load configuration from environment variables."""
        config = cls()
        
        # Override from environment
        if os.getenv("POT_DATA_DIR"):
            config.data_dir = os.getenv("POT_DATA_DIR")
        if os.getenv("POT_NETWORK"):
            config.network.network_type = NetworkType[os.getenv("POT_NETWORK").upper()]
        if os.getenv("POT_LOG_LEVEL"):
            config.log_level = os.getenv("POT_LOG_LEVEL")
        if os.getenv("POT_PORT"):
            config.network.default_port = int(os.getenv("POT_PORT"))
        if os.getenv("POT_RPC_PORT"):
            config.rpc_port = int(os.getenv("POT_RPC_PORT"))
        if os.getenv("POT_MAX_PEERS"):
            config.network.max_peers = int(os.getenv("POT_MAX_PEERS"))

        # Crypto backend configuration
        if os.getenv("POT_CRYPTO_BACKEND"):
            config.crypto.backend = os.getenv("POT_CRYPTO_BACKEND")
        if os.getenv("POT_SPHINCS_VARIANT"):
            config.crypto.sphincs_variant = os.getenv("POT_SPHINCS_VARIANT")
        if os.getenv("POT_VDF_BACKEND"):
            config.crypto.vdf_backend = os.getenv("POT_VDF_BACKEND")

        return config
    
    @classmethod
    def _from_dict(cls, data: dict) -> 'NodeConfig':
        """Create config from dictionary."""
        config = cls()
        
        for key, value in data.items():
            if hasattr(config, key):
                if isinstance(value, dict):
                    sub_config = getattr(config, key)
                    for sub_key, sub_value in value.items():
                        if hasattr(sub_config, sub_key):
                            setattr(sub_config, sub_key, sub_value)
                else:
                    setattr(config, key, value)
        
        return config
    
    def to_dict(self) -> dict:
        """Export configuration to dictionary."""
        from dataclasses import asdict
        return asdict(self)
    
    def save(self, path: str):
        """Save configuration to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
    
    def validate(self) -> bool:
        """Validate configuration values."""
        errors = []
        
        if self.network.max_peers < 1:
            errors.append("max_peers must be >= 1")
        if self.vdf.iterations < 1000:
            errors.append("VDF iterations must be >= 1000")
        if self.storage.cache_size_mb < 64:
            errors.append("cache_size_mb must be >= 64")
        if self.mempool.max_size_mb < 10:
            errors.append("mempool max_size_mb must be >= 10")
            
        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")
        
        return True


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Default configuration (can be overridden)
DEFAULT_CONFIG = NodeConfig()

# Protocol constants (immutable)
PROTOCOL = ProtocolConstants()


# ============================================================================
# EMISSION CONSTANTS AND CALCULATIONS
# ============================================================================

# Maximum supply: 21 million minutes = 21,000,000 * 60 = 1,260,000,000 seconds
MAX_SUPPLY_SECONDS = 21_000_000 * 60  # 1.26 billion seconds

# Maximum supply in "minutes" (display units)
MAX_SUPPLY_MINUTES = 21_000_000


def get_block_reward(height: int) -> int:
    """
    Calculate block reward at given height with halving.
    
    The emission schedule follows Bitcoin's model:
    - Initial reward: 50 minutes (3000 seconds)
    - Halving every 210,000 blocks (~4 years)
    - Total supply: ~21 million minutes
    
    Args:
        height: Block height
        
    Returns:
        Reward in seconds (time tokens)
    """
    halvings = height // PROTOCOL.HALVING_INTERVAL
    if halvings >= 33:
        return 0
    return PROTOCOL.INITIAL_REWARD >> halvings


def get_halving_epoch(height: int) -> int:
    """Get halving epoch number for block height."""
    return height // PROTOCOL.HALVING_INTERVAL + 1


def blocks_until_halving(height: int) -> int:
    """Calculate blocks remaining until next halving."""
    return PROTOCOL.HALVING_INTERVAL - (height % PROTOCOL.HALVING_INTERVAL)


def estimate_total_supply_at_height(height: int) -> int:
    """
    Estimate total supply emitted by given height.
    
    Returns supply in seconds (time tokens).
    """
    if height <= 0:
        return 0
    
    total = 0
    remaining = height
    reward = PROTOCOL.INITIAL_REWARD
    
    while remaining > 0 and reward > 0:
        blocks_in_epoch = min(remaining, PROTOCOL.HALVING_INTERVAL)
        total += blocks_in_epoch * reward
        remaining -= blocks_in_epoch
        reward >>= 1
    
    return total


def calculate_max_supply() -> int:
    """
    Calculate the maximum possible supply.
    
    Sum of all block rewards over all halving epochs.
    
    Returns:
        Maximum supply in seconds
    """
    total = 0
    reward = PROTOCOL.INITIAL_REWARD
    
    for epoch in range(33):  # 33 halvings before reward reaches 0
        blocks_in_epoch = PROTOCOL.HALVING_INTERVAL
        total += blocks_in_epoch * reward
        reward >>= 1
        if reward == 0:
            break
    
    return total


def seconds_to_minutes(seconds: int) -> float:
    """Convert seconds to minutes (display units)."""
    return seconds / 60.0


def minutes_to_seconds(minutes: float) -> int:
    """Convert minutes to seconds (internal units)."""
    return int(minutes * 60)


def validate_supply_limit(current_supply: int, new_emission: int) -> bool:
    """
    Validate that emission won't exceed maximum supply.
    
    Args:
        current_supply: Current total supply in seconds
        new_emission: Proposed new emission in seconds
    
    Returns:
        True if emission is within limits
    """
    return current_supply + new_emission <= MAX_SUPPLY_SECONDS


# ============================================================================
# TEMPORAL COMPRESSION
# ============================================================================

class TemporalCompression:
    """
    Temporal compression for long-term value stability.
    
    As the network ages, earlier time has more "gravity" (value)
    than recently minted time. This creates deflationary pressure
    and rewards early participation.
    
    Compression formula:
    effective_age = log2(1 + actual_age_blocks / COMPRESSION_BASE)
    
    This means:
    - Age 0: effective_age = 0
    - Age COMPRESSION_BASE: effective_age = 1
    - Age 2*COMPRESSION_BASE: effective_age = 1.58
    - Age 4*COMPRESSION_BASE: effective_age = 2.32
    
    The logarithmic scaling ensures:
    1. Early time maintains relative value
    2. Late time doesn't dilute early time too much
    3. Predictable value dynamics
    """
    
    # Base for compression calculation (in blocks)
    # ~1 year worth of blocks (52560 blocks at 12 min/block)
    COMPRESSION_BASE = 52560
    
    @staticmethod
    def effective_age(creation_height: int, current_height: int) -> float:
        """
        Calculate effective age of time tokens.
        
        Args:
            creation_height: Block height when tokens were minted
            current_height: Current block height
        
        Returns:
            Effective age multiplier (>= 0)
        """
        if current_height <= creation_height:
            return 0.0
        
        actual_age = current_height - creation_height
        import math
        return math.log2(1 + actual_age / TemporalCompression.COMPRESSION_BASE)
    
    @staticmethod
    def age_weight(creation_height: int, current_height: int) -> float:
        """
        Calculate weight multiplier based on age.
        
        Older tokens have higher weight.
        
        Returns:
            Weight multiplier (1.0 for new tokens, higher for older)
        """
        effective = TemporalCompression.effective_age(creation_height, current_height)
        return 1.0 + effective * 0.1  # 10% bonus per effective year
    
    @staticmethod
    def weighted_amount(
        amount: int,
        creation_height: int,
        current_height: int
    ) -> int:
        """
        Calculate weighted amount considering temporal compression.
        
        Args:
            amount: Raw amount in seconds
            creation_height: When tokens were created
            current_height: Current height
        
        Returns:
            Weighted amount (may be higher than raw for old tokens)
        """
        weight = TemporalCompression.age_weight(creation_height, current_height)
        return int(amount * weight)


# ============================================================================
# EMISSION TRACKER
# ============================================================================

class EmissionTracker:
    """
    Tracks and validates emission to ensure 21M limit is never exceeded.
    
    Features:
    - Real-time supply tracking
    - Emission validation before block acceptance
    - Statistical projections
    - Burn tracking (lost coins)
    """
    
    def __init__(self):
        self.total_emitted: int = 0  # Total ever emitted
        self.total_burned: int = 0   # Burned (provably lost)
        self.height: int = 0
        
        # Per-epoch statistics
        self.epoch_emissions: dict = {}  # epoch -> amount emitted
    
    @property
    def circulating_supply(self) -> int:
        """Get current circulating supply."""
        return self.total_emitted - self.total_burned
    
    @property
    def remaining_supply(self) -> int:
        """Get remaining supply that can be emitted."""
        return max(0, MAX_SUPPLY_SECONDS - self.total_emitted)
    
    @property
    def percent_emitted(self) -> float:
        """Get percentage of max supply that has been emitted."""
        return (self.total_emitted / MAX_SUPPLY_SECONDS) * 100
    
    def record_emission(self, height: int, reward: int) -> bool:
        """
        Record block reward emission.
        
        Args:
            height: Block height
            reward: Reward amount in seconds
        
        Returns:
            True if emission is valid, False if exceeds limit
        """
        if not validate_supply_limit(self.total_emitted, reward):
            return False
        
        self.total_emitted += reward
        self.height = height
        
        # Track per-epoch
        epoch = get_halving_epoch(height)
        if epoch not in self.epoch_emissions:
            self.epoch_emissions[epoch] = 0
        self.epoch_emissions[epoch] += reward
        
        return True
    
    def record_burn(self, amount: int):
        """Record burned (provably unspendable) tokens."""
        self.total_burned += amount
    
    def validate_block_reward(self, height: int, claimed_reward: int) -> tuple:
        """
        Validate that a block's claimed reward is correct.
        
        Returns:
            (is_valid, expected_reward, reason)
        """
        expected = get_block_reward(height)
        
        if claimed_reward > expected:
            return False, expected, f"Reward too high: {claimed_reward} > {expected}"
        
        if claimed_reward < expected and height < PROTOCOL.MAX_BLOCKS:
            # Miner can claim less, but not more
            pass
        
        if not validate_supply_limit(self.total_emitted, claimed_reward):
            return False, expected, "Would exceed maximum supply"
        
        return True, expected, "Valid"
    
    def get_emission_schedule(self, from_height: int, to_height: int) -> list:
        """
        Get emission schedule for a range of heights.
        
        Returns list of (height, reward, cumulative) tuples.
        """
        schedule = []
        cumulative = estimate_total_supply_at_height(from_height)
        
        for h in range(from_height, to_height + 1):
            reward = get_block_reward(h)
            cumulative += reward
            
            if h % PROTOCOL.HALVING_INTERVAL == 0 or h == from_height:
                schedule.append({
                    'height': h,
                    'reward': reward,
                    'reward_minutes': seconds_to_minutes(reward),
                    'cumulative': cumulative,
                    'cumulative_minutes': seconds_to_minutes(cumulative),
                    'epoch': get_halving_epoch(h)
                })
        
        return schedule
    
    def project_to_max_supply(self) -> dict:
        """
        Project when maximum supply will be reached.
        
        Returns projection details.
        """
        # Calculate remaining blocks until max supply
        remaining = MAX_SUPPLY_SECONDS - self.total_emitted
        
        height = self.height
        blocks_needed = 0
        
        while remaining > 0:
            reward = get_block_reward(height)
            if reward == 0:
                break
            
            remaining -= reward
            height += 1
            blocks_needed += 1
        
        # Estimate time
        estimated_time = blocks_needed * PROTOCOL.BLOCK_INTERVAL
        
        return {
            'current_height': self.height,
            'blocks_until_max': blocks_needed,
            'final_height': height,
            'estimated_seconds': estimated_time,
            'estimated_days': estimated_time / 86400,
            'estimated_years': estimated_time / (86400 * 365)
        }
    
    def get_stats(self) -> dict:
        """Get emission statistics."""
        return {
            'total_emitted': self.total_emitted,
            'total_emitted_minutes': seconds_to_minutes(self.total_emitted),
            'total_burned': self.total_burned,
            'circulating_supply': self.circulating_supply,
            'circulating_supply_minutes': seconds_to_minutes(self.circulating_supply),
            'remaining_supply': self.remaining_supply,
            'remaining_supply_minutes': seconds_to_minutes(self.remaining_supply),
            'percent_emitted': self.percent_emitted,
            'current_height': self.height,
            'current_reward': get_block_reward(self.height),
            'current_epoch': get_halving_epoch(self.height),
            'blocks_until_halving': blocks_until_halving(self.height),
            'max_supply_minutes': MAX_SUPPLY_MINUTES
        }
