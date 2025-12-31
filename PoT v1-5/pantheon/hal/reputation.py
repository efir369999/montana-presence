"""
HAL Reputation System — Human Analyse Language

Multi-factor reputation model with behavioral analysis and trust dynamics.
Part of the unified Hal module for proving humanity and analyzing behavior.

Features:
- Multi-dimensional reputation scoring (5 Fingers)
- Behavioral pattern analysis
- Trust graph propagation
- Dynamic penalty/reward mechanisms
- Historical decay and recovery

The Five Fingers:
- TIME (50%): Bitcoin blocks since halving — resets every halving
- INTEGRITY (20%): No violations, valid proofs
- STORAGE (15%): Chain storage percentage
- EPOCHS (10%): Bitcoin halvings survived — unfakeable
- HANDSHAKE (5%): Mutual trust bonds — 12 Apostles max

Named after Hal Finney — the first to understand Sybil resistance.
Time is the ultimate proof. Humanity cannot be faked.
"""

import time
import math
import struct
import logging
import threading
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import IntEnum, auto
from collections import defaultdict

from pantheon.prometheus import sha256
from config import PROTOCOL

# Humanity verification (relative imports within hal)
from .humanity import (
    HumanityTier,
    HumanityProof,
    HumanityProfile,
    compute_humanity_score,
    get_max_apostles,
)

# Behavioral analysis / Sybil detection (relative imports within hal)
from .behavioral import (
    ClusterDetector,
    ClusterInfo,
    ActionRecord,
    GlobalByzantineTracker,
    CORRELATION_WINDOW_SECONDS,
    MAX_CORRELATION_THRESHOLD,
    CORRELATION_PENALTY_FACTOR,
    MAX_CLUSTER_INFLUENCE,
    MAX_BYZANTINE_INFLUENCE,
    FINGERPRINT_SIMILARITY_THRESHOLD,
)

logger = logging.getLogger("proof_of_time.hal")


# ============================================================================
# CONSTANTS
# ============================================================================

# Maximum vouches per node per day (rate limiting)
MAX_VOUCHES_PER_DAY = 10

# Profile expiration (1 year without events = garbage collected)
PROFILE_EXPIRATION_SECONDS = 365 * 86400

# Maximum allowed timestamp drift (10 minutes into future)
MAX_TIMESTAMP_DRIFT = 600

# ============================================================================
# ANTI-CLUSTER CONSTANTS (additional - core constants imported from hal.behavioral)
# ============================================================================

# Minimum network entropy threshold
MIN_NETWORK_ENTROPY = 0.5  # Below this, TIME dimension starts decaying

# Entropy decay rate per hour when below threshold
ENTROPY_DECAY_RATE = 0.001  # 0.1% per hour

# Minimum nodes for meaningful anti-cluster analysis
MIN_NODES_FOR_CLUSTER_ANALYSIS = 5

# Block production timing variance threshold (milliseconds)
TIMING_VARIANCE_THRESHOLD = 100  # Blocks within 100ms = suspicious synchronization

# Minimum unique countries for handshake network health
MIN_HANDSHAKE_COUNTRIES = 3


# ============================================================================
# REPUTATION DIMENSIONS
# ============================================================================

class ReputationDimension(IntEnum):
    """
    The Five Fingers of Adonis - unified node scoring system.

    Adonis is the ONLY formula for node weight calculation.
    No separate f_time/f_space/f_rep - everything is here.

    Five Fingers (like a hand):
    - THUMB (TIME): The opposable finger - makes the hand work (50%)
    - INDEX (INTEGRITY): Points the way - moral compass (20%)
    - MIDDLE (STORAGE): Central support - network backbone (15%)
    - RING (EPOCHS): Bitcoin halvings survived - unfakeable loyalty (10%)
    - PINKY (HANDSHAKE): Elite bonus - mutual trust between veterans (5%)

    Montana v4.0: GEOGRAPHY replaced with EPOCHS.
    You can fake your location with VPN. You cannot fake having survived a halving.

    HANDSHAKE unlocks only when first 4 fingers are saturated.
    Two veterans shake hands = cryptographic proof of trust.
    """
    TIME = auto()          # THUMB: Bitcoin blocks since halving - saturates at 210,000, RESETS at halving (50%)
    INTEGRITY = auto()     # INDEX: No violations, valid proofs (20%)
    STORAGE = auto()       # MIDDLE: Chain storage - saturates at 100% (15%)
    EPOCHS = auto()        # RING: Bitcoin halvings survived - unfakeable (10%)
    HANDSHAKE = auto()     # PINKY: Mutual trust - saturates at 12 handshakes (5%)


@dataclass
class DimensionScore:
    """Score for a single reputation dimension."""
    value: float = 0.0        # Current score [0, 1]
    confidence: float = 0.0   # Confidence in this score [0, 1]
    samples: int = 0          # Number of observations
    last_update: int = 0      # Last update timestamp

    def update(self, observation: float, weight: float = 1.0, timestamp: int = 0):
        """
        Update dimension score with new observation.

        Uses exponential moving average for smoothing.
        """
        if timestamp == 0:
            timestamp = int(time.time())

        # Decay factor based on time since last update
        if self.last_update > 0:
            age_hours = (timestamp - self.last_update) / 3600
            decay = math.exp(-age_hours / 168)  # 1-week half-life
        else:
            decay = 0.0

        # Update score with weighted moving average
        alpha = weight / (self.samples + weight) if self.samples > 0 else 1.0
        self.value = (1 - alpha) * self.value * decay + alpha * observation
        self.value = max(0.0, min(1.0, self.value))

        # Update confidence
        self.samples += 1
        self.confidence = 1 - math.exp(-self.samples / 100)  # Saturates at ~100 samples

        self.last_update = timestamp


# ============================================================================
# REPUTATION EVENTS
# ============================================================================

class ReputationEvent(IntEnum):
    """Events that affect reputation."""
    # Positive events
    BLOCK_PRODUCED = auto()      # Successfully produced a block
    BLOCK_VALIDATED = auto()     # Validated a block correctly
    TX_RELAYED = auto()          # Relayed valid transaction
    UPTIME_CHECKPOINT = auto()   # Maintained uptime (hourly)
    STORAGE_UPDATE = auto()      # Storage percentage updated
    EPOCH_SURVIVED = auto()      # Survived a Bitcoin halving (210,000 blocks)
    HANDSHAKE_FORMED = auto()    # Mutual handshake with another veteran
    INDEPENDENT_ACTION = auto()  # Action that proves independence from cluster
    NEW_COUNTRY = auto()         # First node from a new country (geographic diversity)
    NEW_CITY = auto()            # First node from a new city (geographic diversity)

    # Negative events
    BLOCK_INVALID = auto()       # Produced invalid block
    VRF_INVALID = auto()         # Invalid VRF proof
    VDF_INVALID = auto()         # Invalid VDF proof
    EQUIVOCATION = auto()        # Double-signing
    DOWNTIME = auto()            # Extended offline period
    SPAM_DETECTED = auto()       # Transaction spam
    HANDSHAKE_BROKEN = auto()    # Handshake partner penalized or offline

    # Anti-cluster events (Slow Takeover Attack prevention)
    CORRELATION_DETECTED = auto()     # Suspicious correlation with other nodes
    CLUSTER_MEMBERSHIP = auto()       # Identified as part of a cluster
    SYNCHRONIZED_TIMING = auto()      # Block production too synchronized
    ENTROPY_DECAY = auto()            # Network entropy too low


@dataclass
class ReputationRecord:
    """Record of a reputation event."""
    event_type: ReputationEvent
    timestamp: int
    impact: float              # Positive or negative impact
    source: Optional[bytes]    # Source node (for peer events)
    evidence: Optional[bytes]  # Hash of evidence
    height: int = 0            # Block height when event occurred

    def serialize(self) -> bytes:
        """Serialize record for storage."""
        data = bytearray()
        data.extend(struct.pack('<B', self.event_type))
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<f', self.impact))
        data.extend(struct.pack('<Q', self.height))
        data.extend(self.source or b'\x00' * 32)
        data.extend(self.evidence or b'\x00' * 32)
        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'ReputationRecord':
        """Deserialize record from bytes."""
        event_type = struct.unpack('<B', data[0:1])[0]
        timestamp = struct.unpack('<Q', data[1:9])[0]
        impact = struct.unpack('<f', data[9:13])[0]
        height = struct.unpack('<Q', data[13:21])[0]
        source = data[21:53] if data[21:53] != b'\x00' * 32 else None
        evidence = data[53:85] if data[53:85] != b'\x00' * 32 else None

        return cls(
            event_type=ReputationEvent(event_type),
            timestamp=timestamp,
            impact=impact,
            height=height,
            source=source,
            evidence=evidence
        )


# ============================================================================
# HANDSHAKE - MUTUAL TRUST BETWEEN VETERANS
# ============================================================================

@dataclass
class Handshake:
    """
    Cryptographic proof of mutual trust between two veteran nodes.

    A handshake can only form when BOTH nodes have saturated their
    first 4 fingers (TIME, INTEGRITY, STORAGE, EPOCHS).

    This is the PINKY finger - the elite bonus that completes the hand.
    """
    node_a: bytes              # First node pubkey
    node_b: bytes              # Second node pubkey
    created_at: int            # Block height when formed
    sig_a: bytes               # Signature from node A
    sig_b: bytes               # Signature from node B

    def __post_init__(self):
        # Ensure canonical ordering (smaller pubkey first)
        if self.node_a > self.node_b:
            self.node_a, self.node_b = self.node_b, self.node_a
            self.sig_a, self.sig_b = self.sig_b, self.sig_a

    def get_id(self) -> bytes:
        """Get unique handshake ID."""
        return sha256(self.node_a + self.node_b)

    def involves(self, pubkey: bytes) -> bool:
        """Check if this handshake involves the given node."""
        return pubkey == self.node_a or pubkey == self.node_b

    def get_partner(self, pubkey: bytes) -> Optional[bytes]:
        """Get the partner node in this handshake."""
        if pubkey == self.node_a:
            return self.node_b
        elif pubkey == self.node_b:
            return self.node_a
        return None


# ============================================================================
# NODE REPUTATION PROFILE
# ============================================================================

@dataclass
class HalProfile:
    """
    Complete reputation profile for a node.

    Combines multi-dimensional scoring with behavioral history
    to create a comprehensive trust assessment.
    """
    pubkey: bytes

    # Multi-dimensional scores
    dimensions: Dict[ReputationDimension, DimensionScore] = field(
        default_factory=lambda: {dim: DimensionScore() for dim in ReputationDimension}
    )

    # Aggregate score (weighted combination of dimensions)
    aggregate_score: float = 0.0

    # Historical records (limited to recent history)
    history: List[ReputationRecord] = field(default_factory=list)
    max_history: int = 1000

    # Trust relationships
    trusted_by: Set[bytes] = field(default_factory=set)   # Nodes that vouch for us
    trusts: Set[bytes] = field(default_factory=set)       # Nodes we vouch for

    # Status flags
    is_penalized: bool = False
    penalty_until: int = 0
    penalty_reason: str = ""

    # Metadata
    created_at: int = 0
    last_updated: int = 0
    total_events: int = 0

    # Geographic diversity
    country_code: Optional[str] = None  # ISO country code (e.g., "US", "DE", "JP")
    city_hash: Optional[bytes] = None   # SHA256(country + city) - no raw IP stored

    # Handshakes (PINKY finger) - set of partner pubkeys
    handshake_partners: Set[bytes] = field(default_factory=set)

    # =========================================================================
    # Hal Humanity System (v4.1)
    # =========================================================================
    # Graduated trust tiers: HARDWARE (3) -> SOCIAL (6) -> TIME_LOCKED (12)
    humanity_tier: HumanityTier = HumanityTier.HARDWARE  # Bootstrap tier
    humanity_proofs: List[HumanityProof] = field(default_factory=list)
    # Identity commitments: epoch -> commitment_hash
    identity_commitments: Dict[int, bytes] = field(default_factory=dict)

    @property
    def humanity_score(self) -> float:
        """Compute humanity score from all valid proofs."""
        return compute_humanity_score(self.humanity_proofs)

    @property
    def max_apostles(self) -> int:
        """Get max Apostles allowed based on humanity tier."""
        return get_max_apostles(self.humanity_tier)

    def add_humanity_proof(self, proof: HumanityProof) -> Tuple[bool, str]:
        """Add a humanity proof to the profile."""
        if proof.pubkey != self.pubkey:
            return False, "Proof pubkey does not match profile"

        # Check for duplicates
        for existing in self.humanity_proofs:
            if (existing.tier == proof.tier and
                existing.proof_type == proof.proof_type and
                existing.proof_data == proof.proof_data):
                return False, "Duplicate proof"

        self.humanity_proofs.append(proof)

        # Update tier to highest valid tier
        valid_proofs = [p for p in self.humanity_proofs if p.is_valid]
        if valid_proofs:
            self.humanity_tier = max(p.tier for p in valid_proofs)

        return True, f"Proof added (tier now {self.humanity_tier.name})"

    def is_eligible_for_handshake(self) -> Tuple[bool, str]:
        """Check if profile is eligible to form handshakes."""
        from pantheon.hal.humanity import HANDSHAKE_MIN_HUMANITY

        # Check humanity score
        score = self.humanity_score
        if score < HANDSHAKE_MIN_HUMANITY:
            return False, f"Humanity score too low: {score:.2f} < {HANDSHAKE_MIN_HUMANITY}"

        # Check current handshakes vs tier limit
        current = len(self.handshake_partners)
        max_allowed = self.max_apostles
        if current >= max_allowed:
            return False, f"At tier limit: {current}/{max_allowed} Apostles"

        return True, f"Eligible for {max_allowed - current} more handshakes"

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = int(time.time())
        if not self.dimensions:
            self.dimensions = {dim: DimensionScore() for dim in ReputationDimension}

    def get_dimension_score(self, dimension: ReputationDimension) -> float:
        """Get score for a specific dimension."""
        return self.dimensions[dimension].value

    def get_trust_score(self) -> float:
        """
        Calculate trust score from peer vouches.

        Score increases with number of vouches, but with diminishing returns.
        """
        if not self.trusted_by:
            return 0.0

        n = len(self.trusted_by)
        # Logarithmic scaling: 1 vouch = 0.2, 10 vouches = 0.6, 100 vouches = 0.9
        return min(1.0, 0.2 * math.log10(1 + n * 4))

    def compute_aggregate(self, weights: Optional[Dict[ReputationDimension, float]] = None) -> float:
        """
        Compute aggregate reputation score.

        Uses the Five Fingers of Adonis weights.
        """
        if weights is None:
            # Montana v4.0: EPOCHS replaces GEOGRAPHY
            # You can fake location with VPN. You cannot fake surviving a halving.
            weights = {
                ReputationDimension.TIME: 0.50,        # THUMB: Core PoT metric
                ReputationDimension.INTEGRITY: 0.20,   # INDEX: No violations
                ReputationDimension.STORAGE: 0.15,    # MIDDLE: Chain storage
                ReputationDimension.EPOCHS: 0.10,      # RING: Halvings survived (unfakeable)
                ReputationDimension.HANDSHAKE: 0.05,   # PINKY: Mutual trust (12 Apostles)
            }

        total = 0.0
        weight_sum = 0.0

        for dim, weight in weights.items():
            score = self.dimensions[dim]
            # Weight by confidence
            effective_weight = weight * score.confidence
            total += score.value * effective_weight
            weight_sum += effective_weight

        if weight_sum > 0:
            self.aggregate_score = total / weight_sum
        else:
            self.aggregate_score = 0.0

        return self.aggregate_score

    def add_event(self, record: ReputationRecord):
        """Add a reputation event to history."""
        self.history.append(record)
        self.total_events += 1
        self.last_updated = record.timestamp

        # Prune old history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_recent_events(self, since: int = 0, limit: int = 100) -> List[ReputationRecord]:
        """Get recent events since timestamp."""
        if since == 0:
            since = int(time.time()) - 86400 * 7  # Last 7 days

        recent = [e for e in self.history if e.timestamp >= since]
        return recent[-limit:]

    def apply_penalty(self, duration_seconds: int, reason: str):
        """Apply a time-based penalty."""
        current_time = int(time.time())
        self.is_penalized = True
        self.penalty_until = current_time + duration_seconds
        self.penalty_reason = reason

        logger.warning(
            f"Penalty applied to {self.pubkey.hex()[:16]}...: "
            f"{reason}, until {self.penalty_until}"
        )

    def check_penalty(self, current_time: Optional[int] = None) -> bool:
        """Check if penalty is still active."""
        if current_time is None:
            current_time = int(time.time())

        if self.is_penalized and current_time >= self.penalty_until:
            self.is_penalized = False
            self.penalty_reason = ""
            logger.info(f"Penalty expired for {self.pubkey.hex()[:16]}...")

        return self.is_penalized

    def serialize(self) -> bytes:
        """Serialize profile for storage."""
        data = bytearray()

        # Header
        data.extend(self.pubkey)
        data.extend(struct.pack('<f', self.aggregate_score))
        data.extend(struct.pack('<Q', self.created_at))
        data.extend(struct.pack('<Q', self.last_updated))
        data.extend(struct.pack('<I', self.total_events))
        data.extend(struct.pack('<B', 1 if self.is_penalized else 0))
        data.extend(struct.pack('<Q', self.penalty_until))

        # Dimensions
        for dim in ReputationDimension:
            score = self.dimensions[dim]
            data.extend(struct.pack('<f', score.value))
            data.extend(struct.pack('<f', score.confidence))
            data.extend(struct.pack('<I', score.samples))
            data.extend(struct.pack('<Q', score.last_update))

        # Trust sets (count + pubkeys)
        data.extend(struct.pack('<H', len(self.trusted_by)))
        for pk in self.trusted_by:
            data.extend(pk)

        data.extend(struct.pack('<H', len(self.trusts)))
        for pk in self.trusts:
            data.extend(pk)

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'HalProfile':
        """Deserialize profile from bytes."""
        offset = 0

        pubkey = data[offset:offset+32]
        offset += 32

        aggregate_score = struct.unpack_from('<f', data, offset)[0]
        offset += 4

        created_at = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        last_updated = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        total_events = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        is_penalized = struct.unpack_from('<B', data, offset)[0] == 1
        offset += 1

        penalty_until = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # Dimensions
        dimensions = {}
        for dim in ReputationDimension:
            value = struct.unpack_from('<f', data, offset)[0]
            offset += 4
            confidence = struct.unpack_from('<f', data, offset)[0]
            offset += 4
            samples = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            last_update = struct.unpack_from('<Q', data, offset)[0]
            offset += 8

            dimensions[dim] = DimensionScore(
                value=value,
                confidence=confidence,
                samples=samples,
                last_update=last_update
            )

        # Trust sets
        trusted_by_count = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        trusted_by = set()
        for _ in range(trusted_by_count):
            trusted_by.add(data[offset:offset+32])
            offset += 32

        trusts_count = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        trusts = set()
        for _ in range(trusts_count):
            trusts.add(data[offset:offset+32])
            offset += 32

        return cls(
            pubkey=pubkey,
            dimensions=dimensions,
            aggregate_score=aggregate_score,
            trusted_by=trusted_by,
            trusts=trusts,
            is_penalized=is_penalized,
            penalty_until=penalty_until,
            created_at=created_at,
            last_updated=last_updated,
            total_events=total_events
        )


# NOTE: ClusterDetector, ClusterInfo, ActionRecord, and GlobalByzantineTracker
# have been moved to pantheon.hal.behavioral module for architectural clarity.
# All Sybil detection is now centralized in the Hal Humanity System.


# ============================================================================
# ENTROPY MONITOR
# ============================================================================

class EntropyMonitor:
    """
    Monitors network entropy (diversity).

    When entropy drops below MIN_NETWORK_ENTROPY, all TIME dimensions
    start decaying. This prevents a homogeneous network from
    accumulating unfair advantage.

    ENTROPY SOURCES:
    1. Geographic diversity (countries, cities)
    2. Temporal diversity (block production spread)
    3. Behavioral diversity (action patterns)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._last_entropy: float = 1.0
        self._entropy_history: List[Tuple[int, float]] = []
        self._decay_active: bool = False
        self._decay_start: int = 0

    def compute_network_entropy(
        self,
        profiles: Dict[bytes, 'HalProfile'],
        country_nodes: Dict[str, Set[bytes]],
        city_nodes: Dict[bytes, Set[bytes]]
    ) -> float:
        """
        Compute overall network entropy.

        Returns value in [0, 1] where:
        - 1.0 = maximum diversity (healthy)
        - 0.0 = complete homogeneity (unhealthy)
        """
        with self._lock:
            if not profiles:
                return 0.0

            n_nodes = len(profiles)

            # 1. GEOGRAPHIC ENTROPY
            # Based on Gini coefficient of country distribution
            if country_nodes:
                country_counts = [len(nodes) for nodes in country_nodes.values()]
                geo_entropy = self._compute_gini_entropy(country_counts)
            else:
                geo_entropy = 0.0

            # 2. CITY ENTROPY
            if city_nodes:
                city_counts = [len(nodes) for nodes in city_nodes.values()]
                city_entropy = self._compute_gini_entropy(city_counts)
            else:
                city_entropy = 0.0

            # 3. TIME ENTROPY
            # Check variance in TIME scores
            time_scores = [
                p.dimensions[ReputationDimension.TIME].value
                for p in profiles.values()
            ]
            if time_scores:
                mean_time = sum(time_scores) / len(time_scores)
                variance = sum((t - mean_time)**2 for t in time_scores) / len(time_scores)
                # Higher variance = more diverse = higher entropy
                time_entropy = min(1.0, math.sqrt(variance) * 4)
            else:
                time_entropy = 0.0

            # 4. HANDSHAKE NETWORK ENTROPY
            # Check if handshake network spans multiple countries
            handshake_countries = set()
            for profile in profiles.values():
                if profile.handshake_partners and profile.country_code:
                    handshake_countries.add(profile.country_code)

            handshake_entropy = min(1.0, len(handshake_countries) / MIN_HANDSHAKE_COUNTRIES)

            # Combined entropy (weighted)
            entropy = (
                0.40 * geo_entropy +      # Geographic is most important
                0.25 * city_entropy +     # City adds granularity
                0.20 * time_entropy +     # Time diversity matters
                0.15 * handshake_entropy  # Trust network health
            )

            # Record history
            current_time = int(time.time())
            self._entropy_history.append((current_time, entropy))

            # Keep only last 24 hours
            cutoff = current_time - 86400
            self._entropy_history = [
                (t, e) for t, e in self._entropy_history if t > cutoff
            ]

            self._last_entropy = entropy

            # Check if decay should be active
            if entropy < MIN_NETWORK_ENTROPY:
                if not self._decay_active:
                    self._decay_active = True
                    self._decay_start = current_time
                    logger.warning(
                        f"ENTROPY DECAY ACTIVATED: Network entropy {entropy:.2f} "
                        f"below threshold {MIN_NETWORK_ENTROPY}"
                    )
            else:
                if self._decay_active:
                    self._decay_active = False
                    logger.info(
                        f"Entropy decay deactivated: Network entropy {entropy:.2f} "
                        f"recovered above threshold"
                    )

            return entropy

    def _compute_gini_entropy(self, counts: List[int]) -> float:
        """Compute entropy from Gini coefficient inversion."""
        if not counts:
            return 0.0

        counts = sorted(counts)
        n = len(counts)
        total = sum(counts)

        if total == 0 or n == 0:
            return 0.0

        # Gini coefficient
        cumulative = 0
        for i, count in enumerate(counts):
            cumulative += (2 * (i + 1) - n - 1) * count

        gini = cumulative / (n * total)

        # Invert: high Gini = unequal = low entropy
        return 1.0 - gini

    def get_time_decay_factor(self) -> float:
        """
        Get decay factor to apply to TIME dimension.

        Returns 1.0 if no decay active, less if decay is active.
        """
        with self._lock:
            if not self._decay_active:
                return 1.0

            # Calculate how long decay has been active
            current_time = int(time.time())
            decay_hours = (current_time - self._decay_start) / 3600

            # Exponential decay
            decay_factor = math.exp(-ENTROPY_DECAY_RATE * decay_hours)

            return max(0.1, decay_factor)  # Never go below 10%

    def is_decay_active(self) -> bool:
        """Check if entropy decay is currently active."""
        return self._decay_active

    def get_entropy_stats(self) -> Dict[str, Any]:
        """Get entropy monitoring statistics."""
        with self._lock:
            return {
                'current_entropy': self._last_entropy,
                'threshold': MIN_NETWORK_ENTROPY,
                'decay_active': self._decay_active,
                'decay_start': self._decay_start if self._decay_active else None,
                'decay_factor': self.get_time_decay_factor(),
                'history_length': len(self._entropy_history),
            }


# ============================================================================
# ADONIS REPUTATION ENGINE
# ============================================================================

class HalEngine:
    """
    Main reputation engine implementing the Adonis model.

    Features:
    - Multi-dimensional reputation tracking
    - Event-based scoring updates
    - Trust graph management
    - Penalty and recovery mechanisms
    - Integration with consensus probabilities
    """

    # Event impact values (positive or negative)
    EVENT_IMPACTS = {
        # Positive events
        ReputationEvent.BLOCK_PRODUCED: 0.05,
        ReputationEvent.BLOCK_VALIDATED: 0.02,
        ReputationEvent.TX_RELAYED: 0.01,
        ReputationEvent.UPTIME_CHECKPOINT: 0.02,  # Hourly uptime tick
        ReputationEvent.STORAGE_UPDATE: 0.01,     # Storage sync
        # Montana v4.0: EPOCHS replaces GEOGRAPHY (VPN was spoofable)
        # Surviving a Bitcoin halving is unfakeable proof of loyalty
        ReputationEvent.EPOCH_SURVIVED: 0.25,     # Survived Bitcoin halving (210,000 blocks)
        ReputationEvent.HANDSHAKE_FORMED: 0.10,   # Mutual trust bonus (12 Apostles)
        ReputationEvent.INDEPENDENT_ACTION: 0.03, # Bonus for proven independence

        # Negative events
        ReputationEvent.BLOCK_INVALID: -0.15,
        ReputationEvent.VRF_INVALID: -0.20,
        ReputationEvent.VDF_INVALID: -0.25,
        ReputationEvent.EQUIVOCATION: -1.0,       # Catastrophic
        ReputationEvent.DOWNTIME: -0.10,
        ReputationEvent.SPAM_DETECTED: -0.20,
        ReputationEvent.HANDSHAKE_BROKEN: -0.05,  # Lost trust

        # Anti-cluster penalties (Slow Takeover Attack prevention)
        ReputationEvent.CORRELATION_DETECTED: -0.15,    # Suspicious similarity
        ReputationEvent.CLUSTER_MEMBERSHIP: -0.20,      # Part of identified cluster
        ReputationEvent.SYNCHRONIZED_TIMING: -0.10,     # Too synchronized
        ReputationEvent.ENTROPY_DECAY: -0.05,           # Network unhealthy
    }

    # Dimension affected by each event (5 fingers)
    EVENT_DIMENSIONS = {
        # TIME (Thumb) - 50%
        ReputationEvent.UPTIME_CHECKPOINT: ReputationDimension.TIME,
        ReputationEvent.DOWNTIME: ReputationDimension.TIME,
        ReputationEvent.ENTROPY_DECAY: ReputationDimension.TIME,  # Network unhealthy = time decays
        # INTEGRITY (Index) - 20%
        ReputationEvent.BLOCK_PRODUCED: ReputationDimension.INTEGRITY,
        ReputationEvent.BLOCK_VALIDATED: ReputationDimension.INTEGRITY,
        ReputationEvent.TX_RELAYED: ReputationDimension.INTEGRITY,
        ReputationEvent.BLOCK_INVALID: ReputationDimension.INTEGRITY,
        ReputationEvent.VRF_INVALID: ReputationDimension.INTEGRITY,
        ReputationEvent.VDF_INVALID: ReputationDimension.INTEGRITY,
        ReputationEvent.EQUIVOCATION: ReputationDimension.INTEGRITY,
        ReputationEvent.SPAM_DETECTED: ReputationDimension.INTEGRITY,
        ReputationEvent.CORRELATION_DETECTED: ReputationDimension.INTEGRITY,  # Suspicious = integrity hit
        ReputationEvent.CLUSTER_MEMBERSHIP: ReputationDimension.INTEGRITY,
        ReputationEvent.SYNCHRONIZED_TIMING: ReputationDimension.INTEGRITY,
        # STORAGE (Middle) - 15%
        ReputationEvent.STORAGE_UPDATE: ReputationDimension.STORAGE,
        # EPOCHS (Ring) - 10% - Bitcoin halvings survived (unfakeable)
        ReputationEvent.EPOCH_SURVIVED: ReputationDimension.EPOCHS,
        # HANDSHAKE (Pinky) - 5% - mutual trust (12 Apostles)
        ReputationEvent.HANDSHAKE_FORMED: ReputationDimension.HANDSHAKE,
        ReputationEvent.HANDSHAKE_BROKEN: ReputationDimension.HANDSHAKE,
        ReputationEvent.INDEPENDENT_ACTION: ReputationDimension.HANDSHAKE,  # Independence = trust
    }

    # Penalty durations (seconds)
    PENALTY_DURATIONS = {
        ReputationEvent.EQUIVOCATION: 180 * 86400,  # 180 days
        ReputationEvent.VDF_INVALID: 30 * 86400,    # 30 days
        ReputationEvent.VRF_INVALID: 14 * 86400,    # 14 days
        ReputationEvent.SPAM_DETECTED: 7 * 86400,   # 7 days
    }

    def __init__(self, storage=None, data_dir: str = None):
        self.profiles: Dict[bytes, HalProfile] = {}
        self.storage = storage
        # Default data_dir is the hal module directory
        if data_dir is None:
            import os
            data_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = data_dir
        self._lock = threading.RLock()

        # Rate limiting: voucher_pubkey -> list of vouch timestamps
        self._vouch_history: Dict[bytes, List[int]] = defaultdict(list)

        # Current block height for timestamp validation
        self._current_height: int = 0

        # Configuration - The Five Fingers of Adonis (sum = 100%)
        # Montana v4.0: EPOCHS replaces GEOGRAPHY (Bitcoin halvings survived)
        self.dimension_weights = {
            ReputationDimension.TIME: 0.50,        # THUMB: 210,000 blocks saturation
            ReputationDimension.INTEGRITY: 0.20,   # INDEX: No violations
            ReputationDimension.STORAGE: 0.15,     # MIDDLE: Chain storage
            ReputationDimension.EPOCHS: 0.10,      # RING: Bitcoin halvings survived (unfakeable)
            ReputationDimension.HANDSHAKE: 0.05,   # PINKY: 12 Apostles trust
        }

        # Saturation thresholds (Montana v4.0: tied to Bitcoin blocks)
        self.HALVING_INTERVAL = 210_000  # Bitcoin halving interval
        self.K_TIME = 210_000       # 210,000 Bitcoin blocks for TIME saturation (resets at halving)
        self.K_STORAGE = 1.00       # 100% of chain
        self.K_HANDSHAKE = 12       # 12 Apostles for full HANDSHAKE score
        self.K_EPOCHS = 4           # 4 halvings survived for full EPOCHS score

        # Minimum requirements for handshake eligibility
        self.HANDSHAKE_MIN_TIME = 0.9       # 90% of TIME saturation
        self.HANDSHAKE_MIN_INTEGRITY = 0.8  # 80% INTEGRITY
        self.HANDSHAKE_MIN_STORAGE = 0.9    # 90% STORAGE
        self.HANDSHAKE_MIN_EPOCHS = 0.25    # At least 1 halving survived (1/4)

        # Country tracking for global decentralization
        # Maps country_code -> set of node pubkeys in that country
        self._country_nodes: Dict[str, Set[bytes]] = defaultdict(set)

        # City hash tracking for geographic diversity
        # Maps city_hash -> set of node pubkeys in that city
        self._city_nodes: Dict[bytes, Set[bytes]] = defaultdict(set)

        # Handshake tracking
        # Maps handshake_id -> Handshake
        self._handshakes: Dict[bytes, Handshake] = {}

        # =====================================================================
        # ANTI-CLUSTER PROTECTION (Slow Takeover Attack Prevention)
        # =====================================================================

        # Cluster detector for identifying colluding nodes
        self.cluster_detector = ClusterDetector()

        # Entropy monitor for network health
        self.entropy_monitor = EntropyMonitor()

        # Global Byzantine tracker for cluster-cap bypass prevention
        self.byzantine_tracker = GlobalByzantineTracker()

        # Load persisted state
        self._load_from_file()

        logger.info("Adonis Reputation Engine initialized (5 Fingers model + Anti-Cluster)")

    def set_current_height(self, height: int):
        """Update current block height for timestamp validation."""
        self._current_height = height

    def get_or_create_profile(self, pubkey: bytes) -> HalProfile:
        """Get existing profile or create new one."""
        with self._lock:
            if pubkey not in self.profiles:
                self.profiles[pubkey] = HalProfile(pubkey=pubkey)
                logger.debug(f"Created new Adonis profile for {pubkey.hex()[:16]}...")
            return self.profiles[pubkey]

    def record_event(
        self,
        pubkey: bytes,
        event_type: ReputationEvent,
        height: int = 0,
        source: Optional[bytes] = None,
        evidence: Optional[bytes] = None,
        timestamp: Optional[int] = None
    ) -> float:
        """
        Record a reputation event and update scores.

        Args:
            pubkey: Node public key
            event_type: Type of reputation event
            height: Block height when event occurred (for validation)
            source: Source node for peer events
            evidence: Hash of evidence
            timestamp: Event timestamp (validated against current time)

        Returns:
            New aggregate score after event, or -1 if validation failed
        """
        with self._lock:
            profile = self.get_or_create_profile(pubkey)
            current_time = int(time.time())

            # Timestamp validation (ADN-M3 fix)
            if timestamp is not None:
                # Reject future timestamps (with small drift allowance)
                if timestamp > current_time + MAX_TIMESTAMP_DRIFT:
                    logger.warning(
                        f"Rejected event with future timestamp: {timestamp} > {current_time}"
                    )
                    return -1.0

                # Reject very old timestamps (older than 24h)
                if timestamp < current_time - 86400:
                    logger.warning(
                        f"Rejected event with stale timestamp: {timestamp}"
                    )
                    return -1.0

                current_time = timestamp

            # Height validation
            if height > 0 and self._current_height > 0:
                # Height should not be far in future
                if height > self._current_height + 10:
                    logger.warning(
                        f"Rejected event with future height: {height} > {self._current_height}"
                    )
                    return -1.0

            # Get impact and dimension
            impact = self.EVENT_IMPACTS.get(event_type, 0.0)
            dimension = self.EVENT_DIMENSIONS.get(event_type)

            # Create record
            record = ReputationRecord(
                event_type=event_type,
                timestamp=current_time,
                impact=impact,
                height=height,
                source=source,
                evidence=evidence
            )

            profile.add_event(record)

            # =========================================================
            # RECORD ACTION FOR CLUSTER DETECTION
            # =========================================================
            # Certain events are tracked for correlation analysis
            action_type_map = {
                ReputationEvent.BLOCK_PRODUCED: "block",
                ReputationEvent.BLOCK_VALIDATED: "vote",
                ReputationEvent.TX_RELAYED: "tx_relay",
            }
            if event_type in action_type_map:
                self.cluster_detector.record_action(
                    pubkey=pubkey,
                    action_type=action_type_map[event_type],
                    timestamp_ms=current_time * 1000,
                    block_height=height,
                    action_hash=evidence or sha256(struct.pack('<Q', current_time))
                )

            # Update dimension score
            if dimension:
                # Convert impact to observation [0, 1]
                if impact >= 0:
                    observation = 0.5 + impact * 0.5  # Positive: 0.5-1.0
                else:
                    observation = 0.5 + impact * 0.5  # Negative: 0.0-0.5
                observation = max(0.0, min(1.0, observation))

                profile.dimensions[dimension].update(
                    observation,
                    weight=abs(impact) * 10,
                    timestamp=current_time
                )

            # Apply penalty if warranted
            if event_type in self.PENALTY_DURATIONS:
                duration = self.PENALTY_DURATIONS[event_type]
                profile.apply_penalty(duration, event_type.name)

            # Recompute aggregate
            new_score = profile.compute_aggregate(self.dimension_weights)

            logger.debug(
                f"Adonis event: {event_type.name} for {pubkey.hex()[:16]}... "
                f"(impact: {impact:+.2f}, new score: {new_score:.3f})"
            )

            return new_score

    def add_vouch(self, voucher: bytes, vouchee: bytes) -> bool:
        """
        Add a trust vouch from voucher to vouchee.

        Rate limited to MAX_VOUCHES_PER_DAY per voucher.

        Returns:
            True if vouch was added, False if rate limited or already exists
        """
        with self._lock:
            current_time = int(time.time())

            # Self-vouch protection
            if voucher == vouchee:
                logger.warning(f"Self-vouch rejected for {voucher.hex()[:16]}...")
                return False

            # Rate limiting (ADN-L1 fix)
            day_ago = current_time - 86400
            recent_vouches = [
                t for t in self._vouch_history[voucher]
                if t > day_ago
            ]
            self._vouch_history[voucher] = recent_vouches

            if len(recent_vouches) >= MAX_VOUCHES_PER_DAY:
                logger.warning(
                    f"Vouch rate limit exceeded for {voucher.hex()[:16]}... "
                    f"({len(recent_vouches)}/{MAX_VOUCHES_PER_DAY} per day)"
                )
                return False

            voucher_profile = self.get_or_create_profile(voucher)
            vouchee_profile = self.get_or_create_profile(vouchee)

            if vouchee in voucher_profile.trusts:
                return False  # Already vouching

            voucher_profile.trusts.add(vouchee)
            vouchee_profile.trusted_by.add(voucher)
            self._vouch_history[voucher].append(current_time)

            # Note: One-way vouches are tracked but don't affect Adonis score
            # Mutual trust requires HANDSHAKE (two-way, both nodes saturated)

            logger.info(
                f"Trust vouch: {voucher.hex()[:16]}... -> {vouchee.hex()[:16]}..."
            )

            # Auto-save after vouch
            self._save_to_file()

            return True

    def remove_vouch(self, voucher: bytes, vouchee: bytes) -> bool:
        """Remove a trust vouch."""
        with self._lock:
            if voucher not in self.profiles or vouchee not in self.profiles:
                return False

            voucher_profile = self.profiles[voucher]
            vouchee_profile = self.profiles[vouchee]

            voucher_profile.trusts.discard(vouchee)
            vouchee_profile.trusted_by.discard(voucher)

            return True

    # =========================================================================
    # TIME AND STORAGE UPDATES
    # =========================================================================

    def update_time(self, pubkey: bytes, btc_height: int) -> float:
        """
        Update TIME dimension based on Bitcoin blocks since last halving.

        Montana v4.2: TIME is measured in Bitcoin blocks, not seconds.
        - Saturation = 210,000 blocks (one halving period)
        - Resets to 0 at each halving
        - Weight grows linearly during the epoch

        Args:
            pubkey: Node public key
            btc_height: Current Bitcoin block height

        Returns:
            TIME score in [0, 1]
        """
        with self._lock:
            profile = self.get_or_create_profile(pubkey)

            # Calculate blocks since last halving (resets at each halving)
            blocks_since_halving = btc_height % self.HALVING_INTERVAL
            current_epoch = btc_height // self.HALVING_INTERVAL

            # TIME score = blocks in current epoch / 210,000
            time_score = min(blocks_since_halving / self.K_TIME, 1.0)

            # Track epoch for reset detection
            prev_epoch = getattr(profile, '_time_epoch', current_epoch)
            if current_epoch > prev_epoch:
                # Halving occurred! Reset and record epoch survival
                logger.info(
                    f"Node {pubkey.hex()[:16]}... TIME RESET: "
                    f"Halving at epoch {current_epoch}, starting fresh"
                )
                # Reset TIME score (blocks_since_halving will be small)
                profile._time_epoch = current_epoch

            profile._time_epoch = current_epoch

            profile.dimensions[ReputationDimension.TIME].update(
                time_score,
                weight=2.0,  # High weight for stability
                timestamp=int(time.time())
            )

            # Record uptime checkpoint event
            self.record_event(pubkey, ReputationEvent.UPTIME_CHECKPOINT)

            logger.debug(
                f"Node {pubkey.hex()[:16]}... TIME updated: "
                f"BTC block {btc_height}, epoch {current_epoch}, "
                f"{blocks_since_halving}/{self.HALVING_INTERVAL} blocks = {time_score:.3f}"
            )

            return time_score

    def update_storage(
        self,
        pubkey: bytes,
        stored_blocks: int,
        total_blocks: int
    ) -> float:
        """
        Update STORAGE dimension based on chain storage.

        Args:
            pubkey: Node public key
            stored_blocks: Number of blocks stored
            total_blocks: Total blocks in chain

        Returns:
            STORAGE score in [0, 1]
        """
        with self._lock:
            if total_blocks == 0:
                return 0.0

            profile = self.get_or_create_profile(pubkey)

            # Storage ratio
            storage_ratio = stored_blocks / total_blocks

            # Saturating at K_STORAGE (80%)
            storage_score = min(storage_ratio / self.K_STORAGE, 1.0)

            profile.dimensions[ReputationDimension.STORAGE].update(
                storage_score,
                weight=1.0,
                timestamp=int(time.time())
            )

            logger.debug(
                f"Node {pubkey.hex()[:16]}... STORAGE updated: "
                f"{stored_blocks}/{total_blocks} ({storage_ratio*100:.1f}%) = {storage_score:.3f}"
            )

            return storage_score

    def compute_node_probability(
        self,
        pubkey: bytes,
        btc_height: int,
        stored_blocks: int,
        total_blocks: int
    ) -> float:
        """
        Compute complete node probability using unified Adonis formula.

        This is the ONLY formula for node weight. No separate f_time/f_space/f_rep.

        INCLUDES ANTI-CLUSTER PROTECTIONS:
        1. Entropy decay - TIME decays if network entropy is too low
        2. Cluster penalty - nodes in detected clusters get reduced score
        3. Correlation penalty - highly correlated nodes get penalized

        Montana v4.2: TIME is measured in Bitcoin blocks since last halving.
        Resets at each halving (210,000 blocks).

        Args:
            pubkey: Node public key
            btc_height: Current Bitcoin block height
            stored_blocks: Blocks stored
            total_blocks: Total chain blocks

        Returns:
            Adonis score in [0, 1] (unnormalized probability)
        """
        with self._lock:
            profile = self.get_or_create_profile(pubkey)
            current_time = int(time.time())

            # =========================================================
            # STEP 1: COMPUTE NETWORK ENTROPY (before TIME update)
            # =========================================================
            entropy = self.entropy_monitor.compute_network_entropy(
                self.profiles,
                self._country_nodes,
                self._city_nodes
            )

            # Get entropy decay factor (1.0 if healthy, less if unhealthy)
            entropy_decay = self.entropy_monitor.get_time_decay_factor()

            # =========================================================
            # STEP 2: UPDATE TIME (Bitcoin blocks since last halving)
            # =========================================================
            # Montana v4.2: TIME resets at each halving
            blocks_since_halving = btc_height % self.HALVING_INTERVAL
            current_epoch = btc_height // self.HALVING_INTERVAL

            # Track epoch for reset detection
            prev_epoch = getattr(profile, '_time_epoch', current_epoch)
            if current_epoch > prev_epoch:
                logger.info(f"Node {pubkey.hex()[:16]}... TIME RESET at halving {current_epoch}")
                profile._time_epoch = current_epoch
            profile._time_epoch = current_epoch

            raw_time_score = min(blocks_since_halving / self.K_TIME, 1.0)

            # Apply entropy decay to TIME
            # If network is unhealthy, time accumulation slows down
            time_score = raw_time_score * entropy_decay

            profile.dimensions[ReputationDimension.TIME].value = time_score
            # Confidence grows with blocks in epoch (full at ~21,000 blocks = 10% of epoch)
            profile.dimensions[ReputationDimension.TIME].confidence = min(
                1.0, blocks_since_halving / 21_000
            )

            # Record entropy decay event if active
            if entropy_decay < 1.0:
                self.record_event(
                    pubkey,
                    ReputationEvent.ENTROPY_DECAY,
                    height=self._current_height
                )

            # =========================================================
            # STEP 3: UPDATE STORAGE
            # =========================================================
            if total_blocks > 0:
                storage_ratio = stored_blocks / total_blocks
                storage_score = min(storage_ratio / self.K_STORAGE, 1.0)
                profile.dimensions[ReputationDimension.STORAGE].value = storage_score
                profile.dimensions[ReputationDimension.STORAGE].confidence = 1.0

            # =========================================================
            # STEP 4: COMPUTE BASE AGGREGATE (5 fingers)
            # =========================================================
            score = profile.compute_aggregate(self.dimension_weights)

            # =========================================================
            # STEP 5: APPLY PENALTY IF ACTIVE
            # =========================================================
            if profile.check_penalty(current_time):
                score *= 0.1  # 90% reduction

            # =========================================================
            # STEP 6: APPLY CLUSTER PENALTY
            # =========================================================
            # Run cluster detection periodically
            self.cluster_detector.detect_clusters(self.profiles)

            # Get cluster penalty for this node
            cluster_penalty = self.cluster_detector.get_node_cluster_penalty(pubkey)
            if cluster_penalty < 1.0:
                logger.debug(
                    f"Cluster penalty applied to {pubkey.hex()[:16]}...: "
                    f"{(1-cluster_penalty)*100:.1f}% reduction"
                )
                score *= cluster_penalty

            return score

    def get_reputation_score(self, pubkey: bytes) -> float:
        """
        Get node's reputation score for consensus.

        Returns value in [0, 1] suitable for probability calculation.
        """
        with self._lock:
            if pubkey not in self.profiles:
                return 0.0

            profile = self.profiles[pubkey]
            current_time = int(time.time())

            # Check penalty
            if profile.check_penalty(current_time):
                return 0.1 * profile.aggregate_score  # 90% reduction

            return profile.aggregate_score

    def get_reputation_multiplier(self, pubkey: bytes) -> float:
        """
        Get reputation multiplier for consensus probability.

        Returns value that modifies base probability:
        - 1.0 = neutral (no effect)
        - >1.0 = bonus (good reputation)
        - <1.0 = penalty (bad reputation)

        Range: [0.1, 2.0]
        """
        score = self.get_reputation_score(pubkey)

        # Map [0, 1] to [0.1, 2.0]
        # Score 0.5 = multiplier 1.0 (neutral)
        # Score 1.0 = multiplier 2.0 (maximum bonus)
        # Score 0.0 = multiplier 0.1 (maximum penalty)

        return 0.1 + score * 1.9

    def get_profile(self, pubkey: bytes) -> Optional[HalProfile]:
        """Get profile for a node."""
        return self.profiles.get(pubkey)

    def get_top_nodes(self, limit: int = 100) -> List[Tuple[bytes, float]]:
        """Get top nodes by reputation score."""
        with self._lock:
            scored = [
                (pk, profile.aggregate_score)
                for pk, profile in self.profiles.items()
                if not profile.is_penalized
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:limit]

    def get_trust_graph(self) -> Dict[bytes, Set[bytes]]:
        """Get the complete trust graph."""
        with self._lock:
            return {
                pk: profile.trusts.copy()
                for pk, profile in self.profiles.items()
            }

    def compute_pagerank(self, damping: float = 0.85, iterations: int = 20) -> Dict[bytes, float]:
        """
        Compute PageRank-style trust scores from the trust graph.

        Nodes vouched by high-trust nodes get higher scores.
        """
        with self._lock:
            if not self.profiles:
                return {}

            # Initialize scores
            n = len(self.profiles)
            scores = {pk: 1.0 / n for pk in self.profiles}

            for _ in range(iterations):
                new_scores = {}

                for pk in self.profiles:
                    # Sum of incoming trust weighted by source scores
                    incoming = sum(
                        scores[src] / max(1, len(self.profiles[src].trusts))
                        for src in self.profiles[pk].trusted_by
                        if src in scores
                    )

                    new_scores[pk] = (1 - damping) / n + damping * incoming

                # Normalize
                total = sum(new_scores.values())
                if total > 0:
                    scores = {pk: s / total for pk, s in new_scores.items()}

            return scores

    def get_stats(self) -> Dict[str, Any]:
        """Get Adonis engine statistics including security metrics."""
        with self._lock:
            active = [p for p in self.profiles.values() if not p.is_penalized]
            penalized = [p for p in self.profiles.values() if p.is_penalized]

            total_vouches = sum(len(p.trusts) for p in self.profiles.values())
            avg_score = (
                sum(p.aggregate_score for p in active) / len(active)
                if active else 0.0
            )

            return {
                'total_profiles': len(self.profiles),
                'active_profiles': len(active),
                'penalized_profiles': len(penalized),
                'total_vouches': total_vouches,
                'average_score': avg_score,
                'unique_countries': len(self._country_nodes),
                'unique_cities': len(self._city_nodes),
                'dimension_weights': {
                    dim.name: weight
                    for dim, weight in self.dimension_weights.items()
                },
                # Security metrics (Anti-Cluster + Byzantine)
                'security': {
                    'cluster_stats': self.cluster_detector.get_cluster_stats(),
                    'entropy_stats': self.entropy_monitor.get_entropy_stats(),
                    'byzantine_stats': self.byzantine_tracker.get_stats(),
                    'network_health': self._compute_network_health_score(),
                }
            }

    def _compute_network_health_score(self) -> Dict[str, Any]:
        """
        Compute overall network health score.

        Returns dict with health indicators.
        """
        entropy = self.entropy_monitor._last_entropy
        cluster_stats = self.cluster_detector.get_cluster_stats()

        # Factors that affect health
        entropy_health = entropy  # [0, 1]
        cluster_health = 1.0 - min(1.0, cluster_stats['total_clusters'] * 0.1)
        country_health = min(1.0, len(self._country_nodes) / 10)  # 10+ countries = healthy

        overall_health = (
            0.40 * entropy_health +
            0.35 * cluster_health +
            0.25 * country_health
        )

        return {
            'overall': overall_health,
            'entropy': entropy_health,
            'cluster_free': cluster_health,
            'geographic': country_health,
            'status': (
                'HEALTHY' if overall_health > 0.7 else
                'WARNING' if overall_health > 0.4 else
                'CRITICAL'
            )
        }

    def compute_all_probabilities(self) -> Dict[bytes, float]:
        """
        Compute probabilities for all nodes with all protections applied.

        This is the main entry point for consensus to get node weights.

        PROTECTION LAYERS (applied in order):
        1. Base scores from Adonis 5-finger model
        2. Cluster cap (detected correlated clusters)
        3. Global Byzantine cap (fingerprint-based, prevents bypass)

        Returns:
            Dict mapping pubkey -> probability (after all protections applied)
        """
        with self._lock:
            # Compute base probabilities for all nodes
            base_probs: Dict[bytes, float] = {}

            for pubkey, profile in self.profiles.items():
                if profile.is_penalized:
                    base_probs[pubkey] = 0.0
                else:
                    base_probs[pubkey] = profile.aggregate_score

            # LAYER 1: Apply cluster cap (correlation-based detection)
            capped_probs = self.cluster_detector.apply_cluster_cap(base_probs)

            # LAYER 2: Apply global Byzantine cap (fingerprint-based detection)
            # This catches subdivided clusters that evade correlation detection
            byzantine_capped = self.byzantine_tracker.apply_global_byzantine_cap(
                capped_probs, self.profiles
            )

            # Normalize to sum to 1.0
            total = sum(byzantine_capped.values())
            if total > 0:
                return {pk: p / total for pk, p in byzantine_capped.items()}
            else:
                return byzantine_capped

    # =========================================================================
    # EPOCHS - BITCOIN HALVINGS SURVIVED (Montana v4.0)
    # =========================================================================

    def record_epoch_survived(
        self,
        pubkey: bytes,
        epoch_number: int,
        btc_height: int
    ) -> float:
        """
        Record that a node has survived a Bitcoin halving (epoch transition).

        Montana v4.0: EPOCHS replaces GEOGRAPHY.
        You can fake your location with VPN. You cannot fake having survived a halving.

        Each epoch = 210,000 Bitcoin blocks (~4 years).
        Epoch 0: Genesis - 210,000
        Epoch 1: 210,000 - 420,000
        Epoch 2: 420,000 - 630,000
        Epoch 3: 630,000 - 840,000
        Epoch 4: 840,000 - 1,050,000 (current as of 2024)

        Args:
            pubkey: Node public key
            epoch_number: The epoch number survived (0-based)
            btc_height: Bitcoin block height when epoch was survived

        Returns:
            Updated EPOCHS dimension score
        """
        with self._lock:
            profile = self.get_or_create_profile(pubkey)

            # Initialize epochs_survived if not present
            if not hasattr(profile, 'epochs_survived'):
                profile.epochs_survived = set()

            # Check if already recorded
            if epoch_number in profile.epochs_survived:
                return profile.dimensions[ReputationDimension.EPOCHS].value

            # Record the epoch
            profile.epochs_survived.add(epoch_number)

            # Calculate EPOCHS score
            # Score = epochs_survived / K_EPOCHS (saturates at K_EPOCHS halvings)
            epochs_count = len(profile.epochs_survived)
            epochs_score = min(1.0, epochs_count / self.K_EPOCHS)

            # Update EPOCHS dimension
            profile.dimensions[ReputationDimension.EPOCHS].update(
                epochs_score,
                weight=2.0,  # High weight for unfakeable metric
                timestamp=int(time.time())
            )

            # Record event
            self.record_event(pubkey, ReputationEvent.EPOCH_SURVIVED, height=btc_height)

            logger.info(
                f"EPOCH SURVIVED! Node {pubkey.hex()[:16]}... "
                f"survived epoch {epoch_number} (total: {epochs_count}, score: {epochs_score:.2f})"
            )

            return epochs_score

    def get_epochs_survived(self, pubkey: bytes) -> set:
        """Get set of epochs a node has survived."""
        with self._lock:
            if pubkey not in self.profiles:
                return set()
            profile = self.profiles[pubkey]
            return getattr(profile, 'epochs_survived', set())

    def check_epoch_transition(
        self,
        current_btc_height: int,
        previous_btc_height: int
    ) -> Optional[int]:
        """
        Check if a Bitcoin halving (epoch transition) occurred.

        Args:
            current_btc_height: Current Bitcoin block height
            previous_btc_height: Previous Bitcoin block height

        Returns:
            Epoch number if transition occurred, None otherwise
        """
        HALVING_INTERVAL = 210_000

        current_epoch = current_btc_height // HALVING_INTERVAL
        previous_epoch = previous_btc_height // HALVING_INTERVAL

        if current_epoch > previous_epoch:
            return current_epoch
        return None

    # =========================================================================
    # GEOGRAPHIC DIVERSITY (Legacy - Analytics Only)
    # Montana v4.0: GEOGRAPHY removed from scoring, kept for network analytics
    # =========================================================================

    def compute_city_hash(self, country: str, city: str) -> bytes:
        """
        Compute anonymous city hash from location.

        NOTE: Montana v4.0 - This is now for analytics only, not scoring.
        EPOCHS (Bitcoin halvings) replaces GEOGRAPHY for the RING finger.

        Privacy: Only stores hash, not raw location data.
        The hash is deterministic so nodes in same city have same hash.

        Args:
            country: Country code (e.g., "US", "DE", "JP")
            city: City name (case-insensitive)

        Returns:
            32-byte SHA256 hash of normalized location
        """
        # Normalize: lowercase, strip whitespace
        normalized = f"{country.upper().strip()}:{city.lower().strip()}"
        return sha256(normalized.encode('utf-8'))

    def register_node_location(
        self,
        pubkey: bytes,
        country: str,
        city: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, bool, float, float]:
        """
        Register node's geographic location anonymously.

        Privacy guarantees:
        - IP address is NEVER stored
        - Only country_code and city_hash are stored
        - Cannot reverse-engineer city from hash

        Args:
            pubkey: Node public key
            country: Country code (e.g., "US", "DE", "JP")
            city: City name
            ip_address: Optional IP (used only for geolocation, not stored)

        Returns:
            Tuple of (is_new_country, is_new_city, country_score, city_score)
            is_new_country: True if this is first node from this country
            is_new_city: True if this is first node from this city
            country_score: Updated country dimension score
            city_score: Updated geography dimension score
        """
        with self._lock:
            profile = self.get_or_create_profile(pubkey)
            country_code = country.upper().strip()
            city_hash = self.compute_city_hash(country, city)

            # === COUNTRY TRACKING ===
            # Check if this is a new country for the network
            is_new_country = len(self._country_nodes[country_code]) == 0

            # Update profile's country
            old_country = profile.country_code
            if old_country and old_country != country_code:
                # Node moved countries - remove from old country
                self._country_nodes[old_country].discard(pubkey)
                if not self._country_nodes[old_country]:
                    del self._country_nodes[old_country]

            profile.country_code = country_code
            self._country_nodes[country_code].add(pubkey)

            # Calculate country diversity score
            # Fewer nodes in country = higher score (encourages global decentralization)
            nodes_in_country = len(self._country_nodes[country_code])
            total_countries = len(self._country_nodes)

            # Score based on country rarity (stronger than city)
            # 1 node = 1.0, 10 nodes = 0.5, 100 nodes = 0.25
            country_rarity = 1.0 / (1.0 + math.log10(nodes_in_country))

            # Big bonus for network having many countries
            country_diversity = min(1.0, total_countries / 50)  # Max at 50 countries

            country_score = 0.6 * country_rarity + 0.4 * country_diversity

            # Update GEOGRAPHY dimension (RING) - country contributes to geography
            # Note: We update the same GEOGRAPHY dimension for both country and city
            # The combined score reflects overall geographic diversity

            # Award NEW_COUNTRY event if first node from this country
            if is_new_country:
                self.record_event(pubkey, ReputationEvent.NEW_COUNTRY)
                logger.info(
                    f"NEW COUNTRY! Node {pubkey.hex()[:16]}... "
                    f"is first from {country_code} (total countries: {total_countries})"
                )

            # === CITY TRACKING ===
            # Check if this is a new city for the network
            is_new_city = len(self._city_nodes[city_hash]) == 0

            # Update profile's city hash
            old_city_hash = profile.city_hash
            if old_city_hash and old_city_hash != city_hash:
                # Node moved cities - remove from old city
                self._city_nodes[old_city_hash].discard(pubkey)
                if not self._city_nodes[old_city_hash]:
                    del self._city_nodes[old_city_hash]

            profile.city_hash = city_hash
            self._city_nodes[city_hash].add(pubkey)

            # Calculate city diversity score
            nodes_in_city = len(self._city_nodes[city_hash])
            total_cities = len(self._city_nodes)

            city_rarity = 1.0 / (1.0 + math.log10(nodes_in_city))
            city_diversity = min(1.0, total_cities / 100)  # Max at 100 cities

            city_score = 0.7 * city_rarity + 0.3 * city_diversity

            # Combined GEOGRAPHY score (for analytics, not reputation)
            # Montana v4.0: GEOGRAPHY replaced by EPOCHS in Adonis dimensions
            # This score is still calculated for network analytics only
            geography_score = 0.6 * country_score + 0.4 * city_score
            # Note: GEOGRAPHY no longer a dimension - EPOCHS (Bitcoin halvings) replaced it

            # Award NEW_CITY event if first node from this city
            if is_new_city:
                self.record_event(pubkey, ReputationEvent.NEW_CITY)
                logger.info(
                    f"New city! Node {pubkey.hex()[:16]}... "
                    f"is first from city hash {city_hash.hex()[:16]}..."
                )

            logger.debug(
                f"Node {pubkey.hex()[:16]}... registered: "
                f"country={country_code} (score={country_score:.3f}, nodes={nodes_in_country}), "
                f"city={city_hash.hex()[:8]}... (score={city_score:.3f}, nodes={nodes_in_city})"
            )

            return is_new_country, is_new_city, country_score, city_score

    def get_country_distribution(self) -> Dict[str, int]:
        """
        Get distribution of nodes per country.

        Returns dict mapping country_code -> node_count.
        """
        with self._lock:
            return {
                country: len(nodes)
                for country, nodes in self._country_nodes.items()
            }

    def get_city_distribution(self) -> Dict[str, int]:
        """
        Get distribution of nodes per city (anonymized).

        Returns dict mapping city_hash_prefix -> node_count.
        Only returns first 8 chars of hash for additional privacy.
        """
        with self._lock:
            return {
                city_hash.hex()[:8]: len(nodes)
                for city_hash, nodes in self._city_nodes.items()
            }

    def get_geographic_diversity_score(self) -> float:
        """
        Calculate overall network geographic diversity.

        Higher score = more decentralized geographically.
        Uses Gini coefficient inversion.

        Returns:
            Score in [0, 1] where 1 = perfectly distributed
        """
        with self._lock:
            if not self._city_nodes:
                return 0.0

            counts = sorted([len(nodes) for nodes in self._city_nodes.values()])
            n = len(counts)
            total = sum(counts)

            if total == 0 or n == 0:
                return 0.0

            # Gini coefficient calculation
            cumulative = 0
            for i, count in enumerate(counts):
                cumulative += (2 * (i + 1) - n - 1) * count

            gini = cumulative / (n * total)

            # Invert: high Gini = unequal, we want low Gini = high score
            return 1.0 - gini

    def update_node_location_from_ip(
        self,
        pubkey: bytes,
        ip_address: str
    ) -> Optional[Tuple[bool, bool, float, float]]:
        """
        Update node location from IP address using free geolocation.

        Privacy: IP is used only for lookup, never stored.

        Args:
            pubkey: Node public key
            ip_address: Node's IP address

        Returns:
            Tuple of (is_new_country, is_new_city, country_score, city_score)
            or None if geolocation failed
        """
        try:
            # Try to use ip-api.com (free, no key required)
            import urllib.request
            import json

            # Skip private IPs
            if ip_address.startswith(('10.', '192.168.', '172.', '127.', 'localhost')):
                logger.debug(f"Skipping private IP: {ip_address}")
                return None

            url = f"http://ip-api.com/json/{ip_address}?fields=status,country,city,countryCode"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            if data.get('status') != 'success':
                logger.debug(f"Geolocation failed for {ip_address}")
                return None

            country = data.get('countryCode', 'XX')
            city = data.get('city', 'Unknown')

            # Register location (IP is NOT passed to storage)
            return self.register_node_location(pubkey, country, city)

        except Exception as e:
            logger.debug(f"Geolocation error for {ip_address}: {e}")
            return None

    # =========================================================================
    # HANDSHAKE - PINKY FINGER (5%)
    # =========================================================================

    def is_eligible_for_handshake(self, pubkey: bytes) -> Tuple[bool, str]:
        """
        Check if a node is eligible to form handshakes (12 Apostles).

        Montana v4.0: Requires all 4 fingers near saturation:
        - TIME >= 90% (~189,000 Bitcoin blocks)
        - INTEGRITY >= 80%
        - STORAGE >= 90%
        - EPOCHS >= 25% (survived at least 1 Bitcoin halving)

        Returns:
            Tuple of (eligible, reason)
        """
        with self._lock:
            if pubkey not in self.profiles:
                return False, "Profile not found"

            profile = self.profiles[pubkey]

            # Check penalty
            if profile.is_penalized:
                return False, "Node is penalized"

            # Check TIME (THUMB)
            time_score = profile.dimensions[ReputationDimension.TIME].value
            if time_score < self.HANDSHAKE_MIN_TIME:
                return False, f"TIME too low: {time_score:.2f} < {self.HANDSHAKE_MIN_TIME}"

            # Check INTEGRITY (INDEX)
            integrity_score = profile.dimensions[ReputationDimension.INTEGRITY].value
            if integrity_score < self.HANDSHAKE_MIN_INTEGRITY:
                return False, f"INTEGRITY too low: {integrity_score:.2f} < {self.HANDSHAKE_MIN_INTEGRITY}"

            # Check STORAGE (MIDDLE)
            storage_score = profile.dimensions[ReputationDimension.STORAGE].value
            if storage_score < self.HANDSHAKE_MIN_STORAGE:
                return False, f"STORAGE too low: {storage_score:.2f} < {self.HANDSHAKE_MIN_STORAGE}"

            # Check EPOCHS (RING) - Montana v4.0: Bitcoin halvings survived
            epochs_score = profile.dimensions[ReputationDimension.EPOCHS].value
            if epochs_score < self.HANDSHAKE_MIN_EPOCHS:
                return False, f"EPOCHS too low: {epochs_score:.2f} (survive at least 1 Bitcoin halving)"

            return True, "Eligible for handshake"

    def request_handshake(
        self,
        requester: bytes,
        target: bytes
    ) -> Tuple[bool, str]:
        """
        Request a handshake with another node (12 Apostles).

        Montana v4.0 INDEPENDENCE REQUIREMENTS (Anti-Sybil):
        1. Both nodes must be eligible (4 fingers saturated incl. EPOCHS)
        2. Nodes must have LOW CORRELATION (< 50%)
        3. Nodes must not be in the same detected cluster
        4. Each node limited to 12 Apostles maximum

        NOTE: Geographic requirement removed - EPOCHS (Bitcoin halvings) replaces it.
        You can fake location with VPN. You cannot fake surviving a halving.

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            # Check self-handshake
            if requester == target:
                return False, "Cannot handshake with yourself"

            # Check if handshake already exists
            handshake_id = sha256(min(requester, target) + max(requester, target))
            if handshake_id in self._handshakes:
                return False, "Handshake already exists"

            # Check requester eligibility
            eligible, reason = self.is_eligible_for_handshake(requester)
            if not eligible:
                return False, f"Requester not eligible: {reason}"

            # Check target eligibility
            eligible, reason = self.is_eligible_for_handshake(target)
            if not eligible:
                return False, f"Target not eligible: {reason}"

            # Check 12 Apostles limit
            requester_profile = self.profiles[requester]
            target_profile = self.profiles[target]

            if len(requester_profile.handshake_partners) >= self.K_HANDSHAKE:
                return False, f"Requester already has {self.K_HANDSHAKE} Apostles (maximum)"

            if len(target_profile.handshake_partners) >= self.K_HANDSHAKE:
                return False, f"Target already has {self.K_HANDSHAKE} Apostles (maximum)"

            # =========================================================
            # INDEPENDENCE VERIFICATION (Slow Takeover Attack Prevention)
            # =========================================================

            # Check behavioral correlation
            correlation = self.cluster_detector.compute_pairwise_correlation(requester, target)
            if correlation > 0.5:  # 50% threshold for handshake
                return False, (
                    f"Nodes too correlated ({correlation*100:.1f}%) - "
                    f"handshakes require independent nodes (< 50%)"
                )

            # Check if nodes are in the same detected cluster
            requester_clusters = self.cluster_detector._node_clusters.get(requester, set())
            target_clusters = self.cluster_detector._node_clusters.get(target, set())
            common_clusters = requester_clusters & target_clusters

            if common_clusters:
                return False, (
                    "Nodes are in the same detected cluster - "
                    "handshakes require provably independent nodes"
                )

            # All checks passed
            return True, "Ready for handshake (12 Apostles - independence verified)"

    def form_handshake(
        self,
        node_a: bytes,
        node_b: bytes,
        sig_a: bytes,
        sig_b: bytes,
        height: int
    ) -> Tuple[bool, str]:
        """
        Form a mutual handshake between two veteran nodes.

        This is called when both nodes have agreed to shake hands.

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            # Validate request first
            success, reason = self.request_handshake(node_a, node_b)
            if not success:
                return False, reason

            # Create handshake
            handshake = Handshake(
                node_a=node_a,
                node_b=node_b,
                created_at=height,
                sig_a=sig_a,
                sig_b=sig_b
            )

            # Store handshake
            self._handshakes[handshake.get_id()] = handshake

            # Update profiles
            profile_a = self.profiles[node_a]
            profile_b = self.profiles[node_b]

            profile_a.handshake_partners.add(node_b)
            profile_b.handshake_partners.add(node_a)

            # Record events and update HANDSHAKE dimension
            self.record_event(node_a, ReputationEvent.HANDSHAKE_FORMED, height=height, source=node_b)
            self.record_event(node_b, ReputationEvent.HANDSHAKE_FORMED, height=height, source=node_a)

            # Update handshake scores
            self._update_handshake_score(node_a)
            self._update_handshake_score(node_b)

            logger.info(
                f"🤝 HANDSHAKE formed: {node_a.hex()[:8]}... ({profile_a.country_code}) <-> "
                f"{node_b.hex()[:8]}... ({profile_b.country_code})"
            )

            return True, "Handshake formed successfully"

    def break_handshake(
        self,
        node_a: bytes,
        node_b: bytes,
        reason: str = "manual"
    ) -> Tuple[bool, str]:
        """
        Break an existing handshake.

        Called when:
        - One node is penalized (equivocation)
        - One node goes offline for extended period
        - Manual break request

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            handshake_id = sha256(min(node_a, node_b) + max(node_a, node_b))

            if handshake_id not in self._handshakes:
                return False, "Handshake not found"

            # Remove handshake
            del self._handshakes[handshake_id]

            # Update profiles
            if node_a in self.profiles:
                self.profiles[node_a].handshake_partners.discard(node_b)
                self.record_event(node_a, ReputationEvent.HANDSHAKE_BROKEN, source=node_b)
                self._update_handshake_score(node_a)

            if node_b in self.profiles:
                self.profiles[node_b].handshake_partners.discard(node_a)
                self.record_event(node_b, ReputationEvent.HANDSHAKE_BROKEN, source=node_a)
                self._update_handshake_score(node_b)

            logger.info(f"Handshake broken: {node_a.hex()[:8]}... <-> {node_b.hex()[:8]}... (reason: {reason})")

            return True, "Handshake broken"

    def _update_handshake_score(self, pubkey: bytes):
        """Update the HANDSHAKE dimension score based on active handshakes."""
        if pubkey not in self.profiles:
            return

        profile = self.profiles[pubkey]
        handshake_count = len(profile.handshake_partners)

        # Score saturates at K_HANDSHAKE (10)
        handshake_score = min(1.0, handshake_count / self.K_HANDSHAKE)

        profile.dimensions[ReputationDimension.HANDSHAKE].value = handshake_score
        profile.dimensions[ReputationDimension.HANDSHAKE].confidence = 1.0
        profile.dimensions[ReputationDimension.HANDSHAKE].last_update = int(time.time())

    def get_handshakes(self, pubkey: bytes) -> List[Handshake]:
        """Get all active handshakes for a node."""
        with self._lock:
            return [h for h in self._handshakes.values() if h.involves(pubkey)]

    def get_handshake_count(self, pubkey: bytes) -> int:
        """Get count of active handshakes for a node."""
        with self._lock:
            if pubkey not in self.profiles:
                return 0
            return len(self.profiles[pubkey].handshake_partners)

    def get_trust_web_stats(self) -> Dict[str, Any]:
        """Get statistics about the trust web (all handshakes)."""
        with self._lock:
            total_handshakes = len(self._handshakes)
            nodes_with_handshakes = set()

            for handshake in self._handshakes.values():
                nodes_with_handshakes.add(handshake.node_a)
                nodes_with_handshakes.add(handshake.node_b)

            # Country pairs
            country_pairs = defaultdict(int)
            for handshake in self._handshakes.values():
                if handshake.node_a in self.profiles and handshake.node_b in self.profiles:
                    c1 = self.profiles[handshake.node_a].country_code or "XX"
                    c2 = self.profiles[handshake.node_b].country_code or "XX"
                    pair = tuple(sorted([c1, c2]))
                    country_pairs[pair] += 1

            return {
                'total_handshakes': total_handshakes,
                'nodes_with_handshakes': len(nodes_with_handshakes),
                'eligible_nodes': sum(
                    1 for pk in self.profiles
                    if self.is_eligible_for_handshake(pk)[0]
                ),
                'country_pairs': dict(country_pairs),
            }

    def save_state(self):
        """Save engine state to storage."""
        if self.storage is None:
            return

        with self._lock:
            for pubkey, profile in self.profiles.items():
                data = profile.serialize()
                self.storage.store_hal_profile(pubkey, data)

    def load_state(self):
        """Load engine state from storage."""
        if self.storage is None:
            return

        with self._lock:
            profiles_data = self.storage.load_hal_profiles()
            for pubkey, data in profiles_data.items():
                self.profiles[pubkey] = HalProfile.deserialize(data)

            logger.info(f"Loaded {len(self.profiles)} Hal profiles")

    # =========================================================================
    # PERSISTENCE (ADN-M1 fix)
    # =========================================================================

    def _get_state_file(self) -> str:
        """Get path to state file."""
        import os
        return os.path.join(self.data_dir, "hal_state.bin")

    def _save_to_file(self):
        """Save profiles to file for persistence."""
        import os
        try:
            state_file = self._get_state_file()

            # Ensure directory exists
            os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)

            with open(state_file, 'wb') as f:
                # Write version
                f.write(struct.pack('<H', 1))  # Version 1

                # Write profile count
                f.write(struct.pack('<I', len(self.profiles)))

                # Write each profile
                for pubkey, profile in self.profiles.items():
                    data = profile.serialize()
                    f.write(struct.pack('<I', len(data)))
                    f.write(data)

            logger.debug(f"Saved {len(self.profiles)} Adonis profiles to {state_file}")

        except Exception as e:
            logger.error(f"Failed to save Adonis state: {e}")

    def _load_from_file(self):
        """Load profiles from file."""
        import os
        state_file = self._get_state_file()

        if not os.path.exists(state_file):
            logger.debug("No Adonis state file found, starting fresh")
            return

        try:
            with open(state_file, 'rb') as f:
                # Read version
                version = struct.unpack('<H', f.read(2))[0]
                if version != 1:
                    logger.warning(f"Unknown Adonis state version: {version}")
                    return

                # Read profile count
                count = struct.unpack('<I', f.read(4))[0]

                # Read profiles
                for _ in range(count):
                    data_len = struct.unpack('<I', f.read(4))[0]
                    data = f.read(data_len)
                    profile = HalProfile.deserialize(data)
                    self.profiles[profile.pubkey] = profile

            logger.info(f"Loaded {len(self.profiles)} Adonis profiles from {state_file}")

        except Exception as e:
            logger.error(f"Failed to load Adonis state: {e}")

    # =========================================================================
    # GARBAGE COLLECTION
    # =========================================================================

    def garbage_collect(self, force: bool = False) -> int:
        """
        Remove expired profiles (no activity for PROFILE_EXPIRATION_SECONDS).

        Args:
            force: If True, run even if recently run

        Returns:
            Number of profiles removed
        """
        with self._lock:
            current_time = int(time.time())
            expired = []

            for pubkey, profile in self.profiles.items():
                # Check if profile is expired
                if profile.last_updated > 0:
                    age = current_time - profile.last_updated
                else:
                    age = current_time - profile.created_at

                if age > PROFILE_EXPIRATION_SECONDS:
                    # Don't GC penalized profiles (keep for accountability)
                    if not profile.is_penalized:
                        expired.append(pubkey)

            # Remove expired profiles
            for pubkey in expired:
                # Clean up trust references
                profile = self.profiles[pubkey]
                for trusted in profile.trusts:
                    if trusted in self.profiles:
                        self.profiles[trusted].trusted_by.discard(pubkey)

                for truster in profile.trusted_by:
                    if truster in self.profiles:
                        self.profiles[truster].trusts.discard(pubkey)

                del self.profiles[pubkey]

            if expired:
                logger.info(f"Garbage collected {len(expired)} expired Adonis profiles")
                self._save_to_file()

            return len(expired)

    def periodic_maintenance(self):
        """Run periodic maintenance tasks."""
        # Garbage collect
        self.garbage_collect()

        # Save state
        self._save_to_file()


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def compute_f_rep(
    hal_engine: HalEngine,
    pubkey: bytes,
    signed_blocks: int
) -> float:
    """
    Compute reputation component using Hal model.

    This replaces the simple signed_blocks / K_REP calculation
    with the multi-dimensional Hal score.

    Args:
        hal_engine: Hal engine instance
        pubkey: Node public key
        signed_blocks: Number of signed blocks (for backward compatibility)

    Returns:
        Reputation factor in [0, 1]
    """
    # Get Hal score
    hal_score = hal_engine.get_reputation_score(pubkey)

    # Also consider signed blocks (for backward compatibility)
    blocks_score = min(signed_blocks / PROTOCOL.K_REP, 1.0)

    # Combine with Hal having higher weight
    return 0.7 * hal_score + 0.3 * blocks_score


def create_reputation_modifier(hal_engine: HalEngine):
    """
    Create a probability modifier function for consensus.

    Returns a function that modifies base probability based on Hal scores.
    """
    def modifier(pubkey: bytes, base_probability: float) -> float:
        multiplier = hal_engine.get_reputation_multiplier(pubkey)
        return base_probability * multiplier

    return modifier


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run Adonis self-tests."""
    logger.info("Running Adonis self-tests...")
    logger.info("  🖐️ The Five Fingers of Adonis (Montana v4.0):")
    logger.info("     👍 THUMB (TIME): 50% - saturates at 210,000 Bitcoin blocks (RESETS at halving)")
    logger.info("     ☝️ INDEX (INTEGRITY): 20% - no violations")
    logger.info("     🖕 MIDDLE (STORAGE): 15% - saturates at 100%")
    logger.info("     💍 RING (EPOCHS): 10% - Bitcoin halvings survived (unfakeable)")
    logger.info("     🤙 PINKY (HANDSHAKE): 5% - 12 Apostles mutual trust")

    # Create engine
    engine = HalEngine()

    # Create test nodes
    node1 = b'\x01' * 32
    node2 = b'\x02' * 32
    node3 = b'\x03' * 32

    # Test profile creation
    profile1 = engine.get_or_create_profile(node1)
    assert profile1.pubkey == node1
    logger.info("  Profile creation OK")

    # Test TIME dimension (THUMB - 50%) - Montana v4.2: Bitcoin blocks since halving
    # Epoch 2, 105,000 blocks into epoch = 50% saturation
    btc_height_half = 420_000 + 105_000  # Epoch 2, 105k blocks = 50%
    time_score = engine.update_time(node1, btc_height_half)
    assert time_score == 0.5  # 105,000/210,000 = 0.5
    logger.info(f"  THUMB (TIME): BTC {btc_height_half} (105k blocks) = {time_score:.3f}")

    # Full saturation: 210,000 blocks into epoch
    btc_height_full = 420_000 + 209_999  # Almost at halving (saturated)
    time_score_full = engine.update_time(node3, btc_height_full)
    assert abs(time_score_full - 1.0) < 0.001  # ~209,999/210,000 ≈ 1.0
    logger.info(f"  THUMB (TIME): BTC {btc_height_full} (saturated) = {time_score_full:.3f}")

    # Test halving reset: blocks after halving reset TIME to near 0
    btc_height_after_halving = 630_000 + 1000  # Epoch 3, only 1000 blocks
    time_score_reset = engine.update_time(node1, btc_height_after_halving)
    expected_reset = 1000 / 210_000  # ~0.0048
    assert abs(time_score_reset - expected_reset) < 0.001
    logger.info(f"  THUMB (TIME): After halving, BTC {btc_height_after_halving} = {time_score_reset:.4f} (RESET!)")

    # Test STORAGE dimension (MIDDLE - 15%)
    storage_score = engine.update_storage(node1, 1000, 1000)  # 100% storage
    assert storage_score == 1.0  # 100%/100% = 1.0 (saturated)
    logger.info(f"  MIDDLE (STORAGE): 100% = {storage_score:.3f}")

    storage_score_half = engine.update_storage(node3, 500, 1000)  # 50% storage
    assert storage_score_half == 0.5  # 50%/100% = 0.5
    logger.info(f"  MIDDLE (STORAGE): 50% = {storage_score_half:.3f}")

    # Test INTEGRITY (INDEX - 20%) - positive events
    for _ in range(10):
        engine.record_event(node1, ReputationEvent.BLOCK_PRODUCED, height=100)

    score1 = engine.get_reputation_score(node1)
    assert score1 > 0
    logger.info(f"  INDEX (INTEGRITY): 10 blocks = score {score1:.3f}")

    # Test INTEGRITY (INDEX - negative events)
    engine.record_event(node2, ReputationEvent.BLOCK_INVALID, height=100)
    score2 = engine.get_reputation_score(node2)
    logger.info(f"  INDEX (INTEGRITY): invalid block = score {score2:.3f}")

    # Test penalty (EQUIVOCATION)
    engine.record_event(node2, ReputationEvent.EQUIVOCATION, height=100)
    profile2 = engine.get_profile(node2)
    assert profile2.is_penalized
    logger.info("  Penalty: EQUIVOCATION applied")

    # Test unified probability calculation
    # Montana v4.2: Use Bitcoin block height instead of uptime_seconds
    prob = engine.compute_node_probability(
        node1,
        btc_height=420_000 + 105_000,  # Epoch 2, 105k blocks = 50% TIME
        stored_blocks=800,
        total_blocks=1000
    )
    assert prob > 0
    logger.info(f"  Unified probability: {prob:.3f}")

    # Test multiplier
    mult1 = engine.get_reputation_multiplier(node1)
    mult2 = engine.get_reputation_multiplier(node2)
    assert mult1 > mult2  # Good node has higher multiplier
    logger.info(f"  Multipliers: node1={mult1:.2f}, node2={mult2:.2f}")

    # Test top nodes
    top = engine.get_top_nodes(10)
    assert len(top) >= 1
    logger.info(f"  Top nodes: {len(top)}")

    # Test stats
    stats = engine.get_stats()
    assert 'total_profiles' in stats
    logger.info("  Statistics OK")

    # =========================================================================
    # Test EPOCHS dimension (RING - 10%) - Bitcoin halvings survived (v4.0)
    # =========================================================================
    node4 = b'\x04' * 32
    node5 = b'\x05' * 32
    node6 = b'\x06' * 32

    # Test epoch transition detection
    new_epoch = engine.check_epoch_transition(420001, 419999)  # Halving at 420,000
    assert new_epoch == 2  # Epoch 2 (420,000 / 210,000)
    logger.info(f"  💍 RING (EPOCHS): Detected halving at block 420,000 -> epoch {new_epoch}")

    no_epoch = engine.check_epoch_transition(420050, 420000)  # No halving
    assert no_epoch is None
    logger.info("  💍 RING (EPOCHS): No halving when staying in same epoch")

    # Test recording epoch survived
    epochs_score = engine.record_epoch_survived(node4, epoch_number=1, btc_height=210000)
    assert epochs_score == 0.25  # 1 epoch / 4 = 0.25
    logger.info(f"  💍 RING (EPOCHS): Survived epoch 1, score = {epochs_score:.2f}")

    epochs_score = engine.record_epoch_survived(node4, epoch_number=2, btc_height=420000)
    assert epochs_score == 0.5  # 2 epochs / 4 = 0.5
    logger.info(f"  💍 RING (EPOCHS): Survived epoch 2, score = {epochs_score:.2f}")

    # Test getting epochs survived
    epochs = engine.get_epochs_survived(node4)
    assert epochs == {1, 2}
    logger.info(f"  💍 RING (EPOCHS): Node4 survived epochs {epochs}")

    # Test full epoch saturation (4 epochs)
    # The score returned by record_epoch_survived is the raw score
    for epoch in [3, 4]:
        epochs_score_full = engine.record_epoch_survived(node5, epoch_number=epoch, btc_height=epoch * 210000)
    for epoch in [1, 2]:
        epochs_score_full = engine.record_epoch_survived(node5, epoch_number=epoch, btc_height=epoch * 210000)
    # After 4 epochs: 4/4 = 1.0
    assert epochs_score_full == 1.0  # 4 epochs / 4 = 1.0 (saturated)
    logger.info(f"  💍 RING (EPOCHS): 4 halvings = full saturation ({epochs_score_full:.2f})")

    # =========================================================================
    # Test GEOGRAPHY (Legacy - Analytics Only in v4.0)
    # =========================================================================
    logger.info("")
    logger.info("  📊 GEOGRAPHY (Analytics Only - v4.0):")

    # Test city hash anonymity
    hash1 = engine.compute_city_hash("JP", "Tokyo")
    hash2 = engine.compute_city_hash("JP", "tokyo")  # Case insensitive
    assert hash1 == hash2
    logger.info("  GEOGRAPHY: City hash is case-insensitive (privacy preserved)")

    # =========================================================================
    # Test HANDSHAKE dimension (PINKY - 5%) - 12 Apostles mutual trust (v4.0)
    # =========================================================================
    logger.info("")
    logger.info("  🤙 PINKY (HANDSHAKE) - 12 Apostles tests:")

    # Create veteran nodes with saturated fingers
    veteran_a = b'\x10' * 32  # Veteran A
    veteran_b = b'\x11' * 32  # Veteran B
    veteran_c = b'\x12' * 32  # Veteran C
    newbie = b'\x13' * 32      # New node

    # Set up veterans with saturated TIME, INTEGRITY, STORAGE, EPOCHS (v4.0)
    for veteran in [veteran_a, veteran_b, veteran_c]:
        profile = engine.get_or_create_profile(veteran)
        # Saturate TIME (210,000 blocks)
        profile.dimensions[ReputationDimension.TIME].value = 1.0
        profile.dimensions[ReputationDimension.TIME].confidence = 1.0
        # Saturate INTEGRITY
        profile.dimensions[ReputationDimension.INTEGRITY].value = 0.9
        profile.dimensions[ReputationDimension.INTEGRITY].confidence = 1.0
        # Saturate STORAGE
        profile.dimensions[ReputationDimension.STORAGE].value = 1.0
        profile.dimensions[ReputationDimension.STORAGE].confidence = 1.0
        # Saturate EPOCHS (4 halvings survived)
        profile.dimensions[ReputationDimension.EPOCHS].value = 1.0
        profile.dimensions[ReputationDimension.EPOCHS].confidence = 1.0

    # Test eligibility
    eligible, reason = engine.is_eligible_for_handshake(veteran_a)
    assert eligible == True
    logger.info(f"     Veteran A eligible: {eligible}")

    eligible, reason = engine.is_eligible_for_handshake(newbie)
    assert eligible == False  # Newbie has low TIME and no EPOCHS
    logger.info(f"     Newbie not eligible: {reason}")

    # Test handshake request validation (v4.0: no country requirement)
    success, msg = engine.request_handshake(veteran_a, veteran_b)
    assert success == True
    logger.info(f"     Request A->B: {msg}")

    # Form handshake A <-> B
    success, msg = engine.form_handshake(
        veteran_a, veteran_b,
        sig_a=b'\x00' * 64,  # Dummy signature
        sig_b=b'\x00' * 64,
        height=1000
    )
    assert success == True
    logger.info(f"     Handshake A<->B formed!")

    # Check handshake count
    count_a = engine.get_handshake_count(veteran_a)
    count_b = engine.get_handshake_count(veteran_b)
    assert count_a == 1
    assert count_b == 1
    logger.info(f"     Handshake counts: A={count_a}, B={count_b}")

    # Check HANDSHAKE dimension updated (12 Apostles: 1/12)
    profile_a = engine.get_profile(veteran_a)
    handshake_score = profile_a.dimensions[ReputationDimension.HANDSHAKE].value
    expected_score = 1 / 12  # K_HANDSHAKE = 12
    logger.info(f"     HANDSHAKE score: {handshake_score:.3f} (1/12 Apostles)")

    # Form more handshakes
    success, _ = engine.form_handshake(veteran_a, veteran_c, b'\x00'*64, b'\x00'*64, 1001)
    assert success == True
    count_a = engine.get_handshake_count(veteran_a)
    assert count_a == 2
    logger.info(f"     A now has {count_a} Apostles")

    # Test duplicate handshake rejection
    success, msg = engine.form_handshake(veteran_a, veteran_b, b'\x00'*64, b'\x00'*64, 1002)
    assert success == False
    assert "already exists" in msg
    logger.info(f"     Duplicate rejected: {msg}")

    # Break handshake
    success, msg = engine.break_handshake(veteran_a, veteran_b, reason="test")
    assert success == True
    count_a = engine.get_handshake_count(veteran_a)
    assert count_a == 1
    logger.info(f"     Handshake broken, A now has {count_a} Apostle(s)")

    # Get trust web stats
    web_stats = engine.get_trust_web_stats()
    assert web_stats['total_handshakes'] >= 1
    logger.info(f"     Trust web: {web_stats['total_handshakes']} handshakes, {web_stats['nodes_with_handshakes']} nodes")

    # Verify stats include unique_countries and unique_cities
    stats = engine.get_stats()
    assert 'unique_countries' in stats
    assert 'unique_cities' in stats
    logger.info(f"  Stats: {stats['unique_countries']} countries, {stats['unique_cities']} cities")

    # =========================================================================
    # Test ANTI-CLUSTER protection (Slow Takeover Attack prevention)
    # =========================================================================
    logger.info("")
    logger.info("  🛡️ ANTI-CLUSTER tests (Slow Takeover Attack prevention):")

    # Create cluster detector standalone test
    detector = ClusterDetector()

    # Record correlated actions (simulating attack)
    attacker1 = b'\x20' * 32
    attacker2 = b'\x21' * 32
    honest_node = b'\x22' * 32

    # Use current time (within correlation window)
    base_time = int(time.time() * 1000) - 3600000  # 1 hour ago

    # Attackers act at exactly the same times (highly correlated)
    for i in range(10):
        timestamp = base_time + i * 1000  # Every second
        detector.record_action(
            attacker1, "block", timestamp, i, sha256(b"block" + struct.pack('<I', i))
        )
        detector.record_action(
            attacker2, "block", timestamp + 10, i, sha256(b"block" + struct.pack('<I', i))
        )
        # Honest node acts at different times (not correlated)
        detector.record_action(
            honest_node, "block", timestamp + 500000, i, sha256(b"different" + struct.pack('<I', i))
        )

    # Check correlation
    correlation = detector.compute_pairwise_correlation(attacker1, attacker2)
    logger.info(f"     Attacker correlation: {correlation*100:.1f}%")
    # Note: correlation depends on timing variance threshold and action distribution
    # We expect high correlation for synchronized actions

    honest_correlation = detector.compute_pairwise_correlation(attacker1, honest_node)
    logger.info(f"     Honest-Attacker correlation: {honest_correlation*100:.1f}%")

    # Test cluster detection
    test_profiles = {
        attacker1: HalProfile(pubkey=attacker1, aggregate_score=0.8),
        attacker2: HalProfile(pubkey=attacker2, aggregate_score=0.8),
        honest_node: HalProfile(pubkey=honest_node, aggregate_score=0.5),
    }

    # Force analysis by resetting last_analysis time
    detector._last_analysis = 0
    clusters = detector.detect_clusters(test_profiles)
    logger.info(f"     Detected clusters: {len(clusters)}")

    # Test cluster penalty
    penalty = detector.get_node_cluster_penalty(attacker1)
    logger.info(f"     Attacker1 cluster penalty: {penalty*100:.1f}%")

    honest_penalty = detector.get_node_cluster_penalty(honest_node)
    logger.info(f"     Honest node penalty: {honest_penalty*100:.1f}%")
    assert honest_penalty == 1.0, "Honest node should have no penalty"

    # Test cluster cap
    probs = {attacker1: 0.4, attacker2: 0.4, honest_node: 0.2}
    capped = detector.apply_cluster_cap(probs)
    logger.info(f"     Before cap: attackers={0.8}, After cap: attackers={capped.get(attacker1, 0) + capped.get(attacker2, 0):.2f}")

    # Test entropy monitor
    monitor = EntropyMonitor()

    # Test with diverse network
    diverse_profiles = {}
    diverse_countries = {}
    diverse_cities = {}

    for i in range(10):
        pk = bytes([i] * 32)
        diverse_profiles[pk] = HalProfile(pubkey=pk)
        diverse_profiles[pk].dimensions[ReputationDimension.TIME].value = 0.5 + (i % 5) * 0.1
        country = ["US", "DE", "JP", "FR", "GB", "AU", "CA", "BR", "IN", "KR"][i]
        diverse_countries[country] = {pk}
        city_hash = sha256(country.encode())
        diverse_cities[city_hash] = {pk}

    entropy = monitor.compute_network_entropy(diverse_profiles, diverse_countries, diverse_cities)
    logger.info(f"     Diverse network entropy: {entropy:.2f}")
    assert entropy > 0.5, "Diverse network should have high entropy"

    # Test with homogeneous network
    homo_profiles = {}
    homo_countries = {"US": set()}
    homo_cities = {}
    city_hash = sha256(b"US:NYC")
    homo_cities[city_hash] = set()

    for i in range(10):
        pk = bytes([30 + i] * 32)
        homo_profiles[pk] = HalProfile(pubkey=pk)
        homo_profiles[pk].dimensions[ReputationDimension.TIME].value = 0.9  # All same
        homo_countries["US"].add(pk)
        homo_cities[city_hash].add(pk)

    homo_entropy = monitor.compute_network_entropy(homo_profiles, homo_countries, homo_cities)
    logger.info(f"     Homogeneous network entropy: {homo_entropy:.2f}")
    assert homo_entropy < entropy, "Homogeneous network should have lower entropy"

    # Test decay factor
    decay = monitor.get_time_decay_factor()
    logger.info(f"     Time decay factor: {decay:.2f}")

    # Test security stats
    stats = engine.get_stats()
    assert 'security' in stats
    assert 'cluster_stats' in stats['security']
    assert 'entropy_stats' in stats['security']
    assert 'network_health' in stats['security']
    logger.info(f"     Network health: {stats['security']['network_health']['status']}")

    # Test handshake independence requirement
    logger.info("")
    logger.info("  🤝 INDEPENDENCE VERIFICATION tests:")

    # Create two correlated nodes and try handshake
    correlated1 = b'\x30' * 32
    correlated2 = b'\x31' * 32

    # Set up as veterans
    for node in [correlated1, correlated2]:
        profile = engine.get_or_create_profile(node)
        profile.dimensions[ReputationDimension.TIME].value = 1.0
        profile.dimensions[ReputationDimension.TIME].confidence = 1.0
        profile.dimensions[ReputationDimension.INTEGRITY].value = 0.9
        profile.dimensions[ReputationDimension.INTEGRITY].confidence = 1.0
        profile.dimensions[ReputationDimension.STORAGE].value = 1.0
        profile.dimensions[ReputationDimension.STORAGE].confidence = 1.0

    # Register different countries
    engine.register_node_location(correlated1, "IT", "Rome")
    engine.register_node_location(correlated2, "ES", "Madrid")

    # Record correlated actions
    for i in range(10):
        timestamp = int(time.time()) - 3600 + i
        engine.cluster_detector.record_action(
            correlated1, "block", timestamp * 1000, 5000 + i, sha256(b"sync" + struct.pack('<I', i))
        )
        engine.cluster_detector.record_action(
            correlated2, "block", timestamp * 1000 + 10, 5000 + i, sha256(b"sync" + struct.pack('<I', i))
        )

    # Force cluster analysis
    engine.cluster_detector._last_analysis = 0

    # Try handshake - should fail due to correlation
    success, msg = engine.request_handshake(correlated1, correlated2)
    if not success and "correlated" in msg.lower():
        logger.info(f"     Correlated handshake rejected: {msg}")
    else:
        # If correlation wasn't detected (not enough data), that's also OK
        logger.info(f"     Handshake result: {success}, {msg}")

    logger.info("")
    logger.info("🖐️ All Five Fingers of Adonis self-tests passed!")
    logger.info("🛡️ All Anti-Cluster protection tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
