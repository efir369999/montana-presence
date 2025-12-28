"""
Adonis - Advanced Reputation System for Proof of Time
Multi-factor reputation model with behavioral analysis and trust dynamics.

The Adonis system extends the basic f_rep component with:
- Multi-dimensional reputation scoring
- Behavioral pattern analysis
- Trust graph propagation
- Dynamic penalty/reward mechanisms
- Historical decay and recovery

Named after Adonis - symbolizing the pursuit of perfection through time.

Time is the ultimate proof.
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

from crypto import sha256
from config import PROTOCOL

logger = logging.getLogger("proof_of_time.adonis")


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
# REPUTATION DIMENSIONS
# ============================================================================

class ReputationDimension(IntEnum):
    """
    Multi-dimensional reputation scoring.

    Each dimension captures a different aspect of node behavior:
    - RELIABILITY: Uptime and consistent block production
    - INTEGRITY: No slashing events, valid proofs
    - CONTRIBUTION: Storage, relay, validation work
    - LONGEVITY: Time in network with good standing
    - COMMUNITY: Peer vouching and trust delegation
    - GEOGRAPHY: Geographic diversity bonus
    """
    RELIABILITY = auto()   # Block production consistency
    INTEGRITY = auto()     # No violations, valid proofs
    CONTRIBUTION = auto()  # Network contribution (storage, relay)
    LONGEVITY = auto()     # Time-weighted presence
    COMMUNITY = auto()     # Peer trust and vouching
    GEOGRAPHY = auto()     # Geographic diversity (city uniqueness)


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
    UPTIME_CHECKPOINT = auto()   # Maintained uptime
    PEER_VOUCH = auto()          # Received vouch from peer
    NEW_CITY = auto()            # First node from a new city

    # Negative events
    BLOCK_INVALID = auto()       # Produced invalid block
    VRF_INVALID = auto()         # Invalid VRF proof
    VDF_INVALID = auto()         # Invalid VDF proof
    EQUIVOCATION = auto()        # Double-signing
    DOWNTIME = auto()            # Extended offline period
    SPAM_DETECTED = auto()       # Transaction spam
    PEER_COMPLAINT = auto()      # Complaint from peer


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
# NODE REPUTATION PROFILE
# ============================================================================

@dataclass
class AdonisProfile:
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

    # Geographic diversity (anonymous city hash)
    city_hash: Optional[bytes] = None  # SHA256(country + city) - no raw IP stored

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

        Default weights prioritize integrity and reliability.
        """
        if weights is None:
            weights = {
                ReputationDimension.RELIABILITY: 0.25,
                ReputationDimension.INTEGRITY: 0.30,
                ReputationDimension.CONTRIBUTION: 0.15,
                ReputationDimension.LONGEVITY: 0.20,
                ReputationDimension.COMMUNITY: 0.10,
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
    def deserialize(cls, data: bytes) -> 'AdonisProfile':
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


# ============================================================================
# ADONIS REPUTATION ENGINE
# ============================================================================

class AdonisEngine:
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
        ReputationEvent.BLOCK_PRODUCED: 0.05,
        ReputationEvent.BLOCK_VALIDATED: 0.02,
        ReputationEvent.TX_RELAYED: 0.01,
        ReputationEvent.UPTIME_CHECKPOINT: 0.03,
        ReputationEvent.PEER_VOUCH: 0.10,
        ReputationEvent.NEW_CITY: 0.15,          # Bonus for geographic diversity
        ReputationEvent.BLOCK_INVALID: -0.15,
        ReputationEvent.VRF_INVALID: -0.20,
        ReputationEvent.VDF_INVALID: -0.25,
        ReputationEvent.EQUIVOCATION: -1.0,  # Catastrophic
        ReputationEvent.DOWNTIME: -0.10,
        ReputationEvent.SPAM_DETECTED: -0.20,
        ReputationEvent.PEER_COMPLAINT: -0.05,
    }

    # Dimension affected by each event
    EVENT_DIMENSIONS = {
        ReputationEvent.BLOCK_PRODUCED: ReputationDimension.RELIABILITY,
        ReputationEvent.BLOCK_VALIDATED: ReputationDimension.CONTRIBUTION,
        ReputationEvent.TX_RELAYED: ReputationDimension.CONTRIBUTION,
        ReputationEvent.UPTIME_CHECKPOINT: ReputationDimension.RELIABILITY,
        ReputationEvent.PEER_VOUCH: ReputationDimension.COMMUNITY,
        ReputationEvent.NEW_CITY: ReputationDimension.GEOGRAPHY,
        ReputationEvent.BLOCK_INVALID: ReputationDimension.INTEGRITY,
        ReputationEvent.VRF_INVALID: ReputationDimension.INTEGRITY,
        ReputationEvent.VDF_INVALID: ReputationDimension.INTEGRITY,
        ReputationEvent.EQUIVOCATION: ReputationDimension.INTEGRITY,
        ReputationEvent.DOWNTIME: ReputationDimension.RELIABILITY,
        ReputationEvent.SPAM_DETECTED: ReputationDimension.INTEGRITY,
        ReputationEvent.PEER_COMPLAINT: ReputationDimension.COMMUNITY,
    }

    # Penalty durations (seconds)
    PENALTY_DURATIONS = {
        ReputationEvent.EQUIVOCATION: 180 * 86400,  # 180 days
        ReputationEvent.VDF_INVALID: 30 * 86400,    # 30 days
        ReputationEvent.VRF_INVALID: 14 * 86400,    # 14 days
        ReputationEvent.SPAM_DETECTED: 7 * 86400,   # 7 days
    }

    def __init__(self, storage=None, data_dir: str = "."):
        self.profiles: Dict[bytes, AdonisProfile] = {}
        self.storage = storage
        self.data_dir = data_dir
        self._lock = threading.RLock()

        # Rate limiting: voucher_pubkey -> list of vouch timestamps
        self._vouch_history: Dict[bytes, List[int]] = defaultdict(list)

        # Current block height for timestamp validation
        self._current_height: int = 0

        # Configuration
        self.dimension_weights = {
            ReputationDimension.RELIABILITY: 0.22,
            ReputationDimension.INTEGRITY: 0.28,
            ReputationDimension.CONTRIBUTION: 0.13,
            ReputationDimension.LONGEVITY: 0.17,
            ReputationDimension.COMMUNITY: 0.10,
            ReputationDimension.GEOGRAPHY: 0.10,  # Geographic diversity bonus
        }

        # City hash tracking for geographic diversity
        # Maps city_hash -> set of node pubkeys in that city
        self._city_nodes: Dict[bytes, Set[bytes]] = defaultdict(set)

        # Load persisted state
        self._load_from_file()

        logger.info("Adonis Reputation Engine initialized")

    def set_current_height(self, height: int):
        """Update current block height for timestamp validation."""
        self._current_height = height

    def get_or_create_profile(self, pubkey: bytes) -> AdonisProfile:
        """Get existing profile or create new one."""
        with self._lock:
            if pubkey not in self.profiles:
                self.profiles[pubkey] = AdonisProfile(pubkey=pubkey)
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

            # Update longevity dimension based on time in network
            age_days = (current_time - profile.created_at) / 86400
            longevity_score = min(1.0, age_days / 180)  # Max at 180 days
            profile.dimensions[ReputationDimension.LONGEVITY].update(
                longevity_score,
                weight=0.1,
                timestamp=current_time
            )

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

            # Record event for vouchee
            self.record_event(
                vouchee,
                ReputationEvent.PEER_VOUCH,
                source=voucher
            )

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

    def get_profile(self, pubkey: bytes) -> Optional[AdonisProfile]:
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
        """Get Adonis engine statistics."""
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
                'unique_cities': len(self._city_nodes),
                'dimension_weights': {
                    dim.name: weight
                    for dim, weight in self.dimension_weights.items()
                }
            }

    # =========================================================================
    # GEOGRAPHIC DIVERSITY
    # =========================================================================

    def compute_city_hash(self, country: str, city: str) -> bytes:
        """
        Compute anonymous city hash from location.

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
    ) -> Tuple[bool, float]:
        """
        Register node's geographic location anonymously.

        Privacy guarantees:
        - IP address is NEVER stored
        - Only city_hash (SHA256) is stored
        - Cannot reverse-engineer location from hash

        Args:
            pubkey: Node public key
            country: Country code
            city: City name
            ip_address: Optional IP (used only for geolocation, not stored)

        Returns:
            Tuple of (is_new_city, geographic_score)
            is_new_city: True if this is first node from this city
            geographic_score: Updated geography dimension score
        """
        with self._lock:
            profile = self.get_or_create_profile(pubkey)
            city_hash = self.compute_city_hash(country, city)

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

            # Calculate geographic diversity score
            # Fewer nodes in city = higher score (encourages decentralization)
            nodes_in_city = len(self._city_nodes[city_hash])
            total_cities = len(self._city_nodes)

            # Score based on city rarity
            # 1 node in city = 1.0, 10 nodes = 0.5, 100 nodes = 0.25
            rarity_score = 1.0 / (1.0 + math.log10(nodes_in_city))

            # Bonus for network having many cities
            diversity_bonus = min(1.0, total_cities / 100)  # Max at 100 cities

            geo_score = 0.7 * rarity_score + 0.3 * diversity_bonus

            # Update geography dimension
            profile.dimensions[ReputationDimension.GEOGRAPHY].update(
                geo_score,
                weight=1.0,
                timestamp=int(time.time())
            )

            # Award NEW_CITY event if first node from this city
            if is_new_city:
                self.record_event(pubkey, ReputationEvent.NEW_CITY)
                logger.info(
                    f"New city registered! Node {pubkey.hex()[:16]}... "
                    f"is first from city hash {city_hash.hex()[:16]}..."
                )

            logger.debug(
                f"Node {pubkey.hex()[:16]}... registered in city "
                f"{city_hash.hex()[:16]}... (score: {geo_score:.3f}, "
                f"nodes_in_city: {nodes_in_city}, total_cities: {total_cities})"
            )

            return is_new_city, geo_score

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
    ) -> Optional[Tuple[bool, float]]:
        """
        Update node location from IP address using free geolocation.

        Privacy: IP is used only for lookup, never stored.

        Args:
            pubkey: Node public key
            ip_address: Node's IP address

        Returns:
            Tuple of (is_new_city, score) or None if geolocation failed
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

    def save_state(self):
        """Save engine state to storage."""
        if self.storage is None:
            return

        with self._lock:
            for pubkey, profile in self.profiles.items():
                data = profile.serialize()
                self.storage.store_adonis_profile(pubkey, data)

    def load_state(self):
        """Load engine state from storage."""
        if self.storage is None:
            return

        with self._lock:
            profiles_data = self.storage.load_adonis_profiles()
            for pubkey, data in profiles_data.items():
                self.profiles[pubkey] = AdonisProfile.deserialize(data)

            logger.info(f"Loaded {len(self.profiles)} Adonis profiles")

    # =========================================================================
    # PERSISTENCE (ADN-M1 fix)
    # =========================================================================

    def _get_state_file(self) -> str:
        """Get path to state file."""
        import os
        return os.path.join(self.data_dir, "adonis_state.bin")

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
                    profile = AdonisProfile.deserialize(data)
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

def compute_f_rep_adonis(
    adonis_engine: AdonisEngine,
    pubkey: bytes,
    signed_blocks: int
) -> float:
    """
    Compute reputation component using Adonis model.

    This replaces the simple signed_blocks / K_REP calculation
    with the multi-dimensional Adonis score.

    Args:
        adonis_engine: Adonis engine instance
        pubkey: Node public key
        signed_blocks: Number of signed blocks (for backward compatibility)

    Returns:
        Reputation factor in [0, 1]
    """
    # Get Adonis score
    adonis_score = adonis_engine.get_reputation_score(pubkey)

    # Also consider signed blocks (for backward compatibility)
    blocks_score = min(signed_blocks / PROTOCOL.K_REP, 1.0)

    # Combine with Adonis having higher weight
    return 0.7 * adonis_score + 0.3 * blocks_score


def create_reputation_modifier(adonis_engine: AdonisEngine):
    """
    Create a probability modifier function for consensus.

    Returns a function that modifies base probability based on Adonis scores.
    """
    def modifier(pubkey: bytes, base_probability: float) -> float:
        multiplier = adonis_engine.get_reputation_multiplier(pubkey)
        return base_probability * multiplier

    return modifier


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run Adonis self-tests."""
    logger.info("Running Adonis self-tests...")

    # Create engine
    engine = AdonisEngine()

    # Create test nodes
    node1 = b'\x01' * 32
    node2 = b'\x02' * 32
    node3 = b'\x03' * 32

    # Test profile creation
    profile1 = engine.get_or_create_profile(node1)
    assert profile1.pubkey == node1
    logger.info("  Profile creation")

    # Test positive events
    for _ in range(10):
        engine.record_event(node1, ReputationEvent.BLOCK_PRODUCED, height=100)

    score1 = engine.get_reputation_score(node1)
    assert score1 > 0
    logger.info(f"  Positive events (score: {score1:.3f})")

    # Test negative events
    engine.record_event(node2, ReputationEvent.BLOCK_INVALID, height=100)
    score2 = engine.get_reputation_score(node2)
    logger.info(f"  Negative events (score: {score2:.3f})")

    # Test vouching
    engine.add_vouch(node1, node3)
    profile3 = engine.get_profile(node3)
    assert node1 in profile3.trusted_by
    logger.info("  Trust vouching")

    # Test penalty
    engine.record_event(node2, ReputationEvent.EQUIVOCATION, height=100)
    profile2 = engine.get_profile(node2)
    assert profile2.is_penalized
    logger.info("  Penalty application")

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
    assert stats['total_profiles'] == 3
    logger.info("  Statistics")

    # Test PageRank
    pagerank = engine.compute_pagerank()
    assert len(pagerank) == 3
    logger.info("  PageRank computation")

    # Test geographic diversity
    node4 = b'\x04' * 32
    node5 = b'\x05' * 32
    node6 = b'\x06' * 32

    # First node from Tokyo - should get NEW_CITY bonus
    is_new, geo_score1 = engine.register_node_location(node4, "JP", "Tokyo")
    assert is_new == True
    assert geo_score1 > 0
    logger.info(f"  Geographic: Tokyo first node (score: {geo_score1:.3f})")

    # Second node from Tokyo - no NEW_CITY bonus
    is_new, geo_score2 = engine.register_node_location(node5, "JP", "Tokyo")
    assert is_new == False
    assert geo_score2 <= geo_score1  # Lower score due to more nodes in city
    logger.info(f"  Geographic: Tokyo second node (score: {geo_score2:.3f})")

    # First node from Berlin - NEW_CITY bonus
    is_new, geo_score3 = engine.register_node_location(node6, "DE", "Berlin")
    assert is_new == True
    logger.info(f"  Geographic: Berlin first node (score: {geo_score3:.3f})")

    # Check city distribution
    distribution = engine.get_city_distribution()
    assert len(distribution) == 2  # Tokyo and Berlin
    logger.info(f"  Geographic: {len(distribution)} unique cities")

    # Check network diversity
    diversity = engine.get_geographic_diversity_score()
    assert diversity > 0
    logger.info(f"  Geographic: Network diversity = {diversity:.3f}")

    # Test city hash anonymity
    hash1 = engine.compute_city_hash("JP", "Tokyo")
    hash2 = engine.compute_city_hash("JP", "tokyo")  # Case insensitive
    assert hash1 == hash2
    logger.info("  Geographic: City hash anonymity")

    # Verify stats include unique_cities
    stats = engine.get_stats()
    assert 'unique_cities' in stats
    assert stats['unique_cities'] == 2
    logger.info(f"  Geographic: Stats include unique_cities={stats['unique_cities']}")

    logger.info("All Adonis self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
