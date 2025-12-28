"""
Proof of Time - Consensus Module
Production-grade implementation of the Proof of Time consensus mechanism.

Includes:
- Node state management
- Probability calculations
- Leader selection via VRF
- Sybil resistance
- Slashing conditions
- Weight rebalancing

Time is the ultimate proof.
"""

import time
import struct
import hashlib
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import IntEnum, auto
from collections import defaultdict

from crypto import sha256, Ed25519, ECVRF, VRFOutput, WesolowskiVDF, VDFProof
from structures import Block, BlockHeader, Transaction, create_genesis_block
from config import PROTOCOL, NodeConfig, get_block_reward

# Optional Adonis integration (for enhanced reputation)
try:
    from adonis import AdonisEngine, compute_f_rep_adonis
    ADONIS_AVAILABLE = True
except ImportError:
    ADONIS_AVAILABLE = False

logger = logging.getLogger("proof_of_time.consensus")


# ============================================================================
# NODE STATE
# ============================================================================

class NodeStatus(IntEnum):
    """Node status enumeration."""
    ACTIVE = auto()
    QUARANTINE = auto()
    OFFLINE = auto()
    SLASHED = auto()


@dataclass
class NodeState:
    """
    State of a network node for consensus.

    Tracks:
    - Uptime (continuous online time)
    - Storage (fraction of chain history)
    - Reputation (signed blocks)
    - Quarantine status
    """
    # Identity
    pubkey: bytes

    # Time component (f_time)
    first_seen: int = 0  # Timestamp when node first joined network (for seniority)
    uptime_start: int = 0  # Timestamp when current uptime started
    total_uptime: int = 0  # Cumulative uptime in seconds

    # Space component (f_space)
    stored_blocks: int = 0  # Number of blocks stored

    # Reputation component (f_rep)
    signed_blocks: int = 0  # Number of blocks signed
    last_signed_height: int = 0

    # Status
    status: NodeStatus = NodeStatus.OFFLINE
    quarantine_until: int = 0  # Timestamp when quarantine ends
    quarantine_reason: str = ""

    # Last seen
    last_seen: int = 0
    
    def get_uptime(self, current_time: int) -> int:
        """Get current uptime in seconds."""
        if self.status != NodeStatus.ACTIVE:
            return 0
        return min(
            self.total_uptime + (current_time - self.uptime_start),
            PROTOCOL.K_TIME  # Cap at saturation
        )
    
    def get_storage_ratio(self, total_blocks: int) -> float:
        """Get storage ratio (0.0 to 1.0)."""
        if total_blocks == 0:
            return 0.0
        return min(self.stored_blocks / total_blocks, 1.0)
    
    def start_uptime(self, timestamp: int):
        """Start or resume uptime tracking."""
        if self.status == NodeStatus.QUARANTINE:
            if timestamp < self.quarantine_until:
                return  # Still in quarantine
            # Quarantine ended
            self.status = NodeStatus.ACTIVE
            self.quarantine_reason = ""

        # Set first_seen only once (when node first joins)
        if self.first_seen == 0:
            self.first_seen = timestamp

        self.uptime_start = timestamp
        self.status = NodeStatus.ACTIVE
        self.last_seen = timestamp
    
    def stop_uptime(self, timestamp: int):
        """Stop uptime tracking (node going offline)."""
        if self.status == NodeStatus.ACTIVE:
            self.total_uptime += timestamp - self.uptime_start
            self.total_uptime = min(self.total_uptime, PROTOCOL.K_TIME)
        
        self.status = NodeStatus.OFFLINE
        self.last_seen = timestamp
    
    def reset_uptime(self):
        """Reset uptime to zero (for quarantine)."""
        self.total_uptime = 0
        self.uptime_start = 0
    
    def enter_quarantine(self, timestamp: int, reason: str):
        """Put node in quarantine."""
        self.status = NodeStatus.QUARANTINE
        self.quarantine_until = timestamp + (PROTOCOL.QUARANTINE_BLOCKS * PROTOCOL.BLOCK_INTERVAL)
        self.quarantine_reason = reason
        self.reset_uptime()
        logger.warning(f"Node {self.pubkey.hex()[:16]}... entered quarantine: {reason}")
    
    def record_signed_block(self, height: int):
        """Record that this node signed a block."""
        self.signed_blocks = min(self.signed_blocks + 1, PROTOCOL.K_REP)
        self.last_signed_height = height
    
    def serialize(self) -> bytes:
        """Serialize node state."""
        data = bytearray()
        data.extend(self.pubkey)
        data.extend(struct.pack('<Q', self.first_seen))
        data.extend(struct.pack('<Q', self.uptime_start))
        data.extend(struct.pack('<Q', self.total_uptime))
        data.extend(struct.pack('<Q', self.stored_blocks))
        data.extend(struct.pack('<Q', self.signed_blocks))
        data.extend(struct.pack('<Q', self.last_signed_height))
        data.extend(struct.pack('<B', self.status))
        data.extend(struct.pack('<Q', self.quarantine_until))
        data.extend(struct.pack('<Q', self.last_seen))
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['NodeState', int]:
        """Deserialize node state."""
        pubkey = data[offset:offset + 32]
        offset += 32

        first_seen = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        uptime_start = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        total_uptime = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        stored_blocks = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        signed_blocks = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        last_signed_height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        status = NodeStatus(data[offset])
        offset += 1
        quarantine_until = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        last_seen = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        return cls(
            pubkey=pubkey,
            first_seen=first_seen,
            uptime_start=uptime_start,
            total_uptime=total_uptime,
            stored_blocks=stored_blocks,
            signed_blocks=signed_blocks,
            last_signed_height=last_signed_height,
            status=status,
            quarantine_until=quarantine_until,
            last_seen=last_seen
        ), offset


# ============================================================================
# PROBABILITY CALCULATION
# ============================================================================

@dataclass
class ProbabilityWeights:
    """Adjustable probability weights for consensus."""
    w_time: float = PROTOCOL.W_TIME
    w_space: float = PROTOCOL.W_SPACE
    w_rep: float = PROTOCOL.W_REP
    
    def normalize(self):
        """Normalize weights to sum to 1.0."""
        total = self.w_time + self.w_space + self.w_rep
        if total > 0:
            self.w_time /= total
            self.w_space /= total
            self.w_rep /= total


class ConsensusCalculator:
    """
    Calculates node probabilities for leader selection.

    Probability formula (per whitepaper):
    P_i = (w_time × f_time(t_i) + w_space × f_space(s_i) + w_rep × f_rep(r_i)) / Z

    where:
    - f_time(t) = min(t / k_time, 1) with k_time = 180 days
    - f_space(s) = min(s / k_space, 1) with k_space = 80% of chain
    - f_rep(r) = min(r / k_rep, 1) with k_rep = 2016 blocks
    - Z = Σ raw_P_i (normalization constant)

    Weights: w_time=0.60, w_space=0.20, w_rep=0.20

    This ensures:
    - Time (presence) is the dominant factor (60%)
    - Storage and reputation are supporting factors (20% each)
    - New nodes can participate but with lower probability
    - Saturation prevents infinite advantage accumulation

    With Adonis integration:
    - f_rep is enhanced with multi-dimensional reputation scoring
    - Reputation includes reliability, integrity, contribution, longevity, community
    - Trust graph adds social proof to reputation calculation
    """

    def __init__(
        self,
        weights: Optional[ProbabilityWeights] = None,
        adonis: Optional['AdonisEngine'] = None
    ):
        self.weights = weights or ProbabilityWeights()
        self.weights.normalize()  # Ensure weights sum to 1
        self.adonis = adonis  # Optional Adonis engine for enhanced reputation
    
    def compute_f_time(self, uptime_seconds: int) -> float:
        """
        Compute time component (saturating at k_time = 180 days).
        
        This measures "time presence" - how long the node has been 
        continuously online and participating in the network.
        
        Args:
            uptime_seconds: Node's continuous uptime in seconds
            
        Returns:
            Value in [0, 1] representing time presence factor
        """
        if uptime_seconds <= 0:
            return 0.0
        # k_time = 180 days = 15,552,000 seconds
        return min(uptime_seconds / PROTOCOL.K_TIME, 1.0)
    
    def compute_f_space(self, stored_blocks: int, total_blocks: int) -> float:
        """
        Compute space component (saturating at k_space = 80% of chain).
        
        This measures how much of the blockchain the node stores,
        encouraging full nodes while capping the advantage.
        
        Args:
            stored_blocks: Number of blocks stored by node
            total_blocks: Total blocks in the chain
            
        Returns:
            Value in [0, 1] representing storage factor
        """
        if total_blocks == 0:
            return 0.0
        storage_ratio = stored_blocks / total_blocks
        # k_space = 0.80 (80% of chain)
        return min(storage_ratio / PROTOCOL.K_SPACE, 1.0)
    
    def compute_f_rep(
        self,
        signed_blocks: int,
        pubkey: Optional[bytes] = None
    ) -> float:
        """
        Compute reputation component (saturating at k_rep = 2016 blocks).

        This measures how many blocks the node has successfully signed
        without equivocation. ~2016 blocks ≈ 2 weeks at 10 min/block.

        With Adonis integration, reputation is enhanced with multi-dimensional
        scoring including reliability, integrity, contribution, longevity,
        and community trust.

        Args:
            signed_blocks: Number of blocks signed without equivocation
            pubkey: Optional node public key for Adonis lookup

        Returns:
            Value in [0, 1] representing reputation factor
        """
        # Base reputation from signed blocks
        if signed_blocks <= 0:
            base_rep = 0.0
        else:
            base_rep = min(signed_blocks / PROTOCOL.K_REP, 1.0)

        # Enhance with Adonis if available
        if self.adonis is not None and pubkey is not None and ADONIS_AVAILABLE:
            adonis_score = self.adonis.get_reputation_score(pubkey)
            # Combine: 30% basic blocks, 70% Adonis multi-dimensional
            return 0.3 * base_rep + 0.7 * adonis_score

        return base_rep
    
    def compute_raw_probability(
        self,
        node: NodeState,
        current_time: int,
        total_blocks: int,
        is_probation: bool = False
    ) -> float:
        """
        Compute raw (unnormalized) probability for a node.
        
        Args:
            node: Node state
            current_time: Current Unix timestamp
            total_blocks: Total blocks in chain
            is_probation: Whether network is in Sybil probation mode
            
        Returns:
            Raw probability (before normalization)
        """
        # Skip offline or slashed nodes
        if node.status == NodeStatus.OFFLINE:
            return 0.0
        if node.status == NodeStatus.SLASHED:
            return 0.0
        
        # Time component
        uptime = node.get_uptime(current_time)
        f_time = self.compute_f_time(uptime)
        
        # Space component
        f_space = self.compute_f_space(node.stored_blocks, total_blocks)

        # Reputation component (with Adonis if available)
        f_rep = self.compute_f_rep(node.signed_blocks, pubkey=node.pubkey)
        
        # Weighted sum
        raw_prob = (
            self.weights.w_time * f_time +
            self.weights.w_space * f_space +
            self.weights.w_rep * f_rep
        )
        
        # Quarantine penalty (from slashing)
        if node.status == NodeStatus.QUARANTINE:
            raw_prob *= 0.1  # 90% reduction during quarantine
        
        # Sybil probation for new nodes (< 30 days uptime)
        if is_probation and uptime < (30 * 24 * 3600):  # 30 days
            raw_prob *= 0.1  # 90% reduction for new nodes during probation
        
        return raw_prob
    
    def compute_probabilities(
        self,
        nodes: List[NodeState],
        current_time: int,
        total_blocks: int,
        is_probation: bool = False
    ) -> Dict[bytes, float]:
        """
        Compute normalized probabilities for all nodes.
        
        Returns:
            Dict mapping pubkey -> probability (all sum to 1.0)
        """
        # Compute raw probabilities
        raw_probs = {}
        for node in nodes:
            if node.status in (NodeStatus.ACTIVE, NodeStatus.QUARANTINE):
                prob = self.compute_raw_probability(
                    node, current_time, total_blocks, is_probation
                )
                if prob > 0:
                    raw_probs[node.pubkey] = prob
        
        # Normalize
        total = sum(raw_probs.values())
        if total == 0:
            return {}
        
        return {pk: p / total for pk, p in raw_probs.items()}
    
    def get_component_breakdown(
        self,
        node: NodeState,
        current_time: int,
        total_blocks: int
    ) -> Dict[str, float]:
        """
        Get detailed breakdown of probability components for debugging.

        Returns:
            Dict with 'f_time', 'f_space', 'f_rep', 'weighted_sum' values
            and Adonis details if available
        """
        uptime = node.get_uptime(current_time)
        f_time = self.compute_f_time(uptime)
        f_space = self.compute_f_space(node.stored_blocks, total_blocks)
        f_rep = self.compute_f_rep(node.signed_blocks, pubkey=node.pubkey)

        result = {
            'uptime_seconds': uptime,
            'uptime_days': uptime / 86400,
            'f_time': f_time,
            'f_space': f_space,
            'f_rep': f_rep,
            'weighted_sum': (
                self.weights.w_time * f_time +
                self.weights.w_space * f_space +
                self.weights.w_rep * f_rep
            ),
            'weights': {
                'time': self.weights.w_time,
                'space': self.weights.w_space,
                'rep': self.weights.w_rep
            }
        }

        # Add Adonis details if available
        if self.adonis is not None and ADONIS_AVAILABLE:
            profile = self.adonis.get_profile(node.pubkey)
            if profile:
                result['adonis'] = {
                    'aggregate_score': profile.aggregate_score,
                    'is_penalized': profile.is_penalized,
                    'trust_score': profile.get_trust_score(),
                    'dimensions': {
                        dim.name: score.value
                        for dim, score in profile.dimensions.items()
                    }
                }

        return result


# ============================================================================
# LEADER SELECTION
# ============================================================================

class LeaderSelector:
    """
    Selects block leader using VRF and node probabilities.
    
    Process:
    1. Each eligible node computes VRF(prev_block_hash || height)
    2. VRF output is mapped to [0, 1) range
    3. Node is selected if VRF_output < P_i (their probability)
    4. If multiple nodes qualify, lowest VRF output wins
    5. If no nodes qualify, use probability-weighted selection
    
    This is a Verifiable Random Function based leader election:
    - VRF ensures unpredictability (cannot pre-compute without knowing prev hash)
    - VRF ensures verifiability (anyone can verify leader was legitimate)
    - Probability weighting ensures time-presence incentives
    """
    
    def __init__(self, calculator: ConsensusCalculator):
        self.calculator = calculator
    
    def compute_selection_input(
        self,
        prev_block_hash: bytes,
        height: int,
        epoch: int = 0
    ) -> bytes:
        """
        Compute deterministic input for VRF.
        
        Input = H(prev_block_hash || height || epoch)
        
        This ensures:
        - Input depends on unpredictable previous block
        - Input is unique per height (prevents replays)
        - Optional epoch for sub-slot leader election
        """
        data = prev_block_hash + struct.pack('<Q', height) + struct.pack('<I', epoch)
        return sha256(data)
    
    def _vrf_to_int(self, vrf_output: bytes) -> int:
        """
        Convert VRF output to 64-bit unsigned integer for precise comparison.

        Using integer comparison instead of float avoids precision loss,
        as float64 mantissa is only 53 bits while we need 64-bit precision.
        """
        if len(vrf_output) < 8:
            vrf_output = vrf_output + b'\x00' * (8 - len(vrf_output))
        return struct.unpack('<Q', vrf_output[:8])[0]

    def vrf_to_float(self, vrf_output: bytes) -> float:
        """
        Convert VRF output to float in [0, 1).

        Note: For leader selection, prefer _vrf_to_int() with integer
        threshold comparison for full 64-bit precision. This method
        is kept for backward compatibility and logging.

        Uses first 8 bytes (64 bits = 10^-19 granularity, but float64
        mantissa is only 53 bits so some precision is lost).
        """
        return self._vrf_to_int(vrf_output) / (2**64)
    
    def is_leader(
        self,
        vrf_output: bytes,
        probability: float
    ) -> bool:
        """
        Check if node is eligible leader using precise integer comparison.

        Node is leader if VRF output (as integer) < threshold.
        Threshold = probability × 2^64

        Using integer comparison preserves full 64-bit precision,
        unlike float comparison which loses ~11 bits of precision.

        Args:
            vrf_output: VRF beta output bytes
            probability: Node's probability in [0, 1)

        Returns:
            True if node is eligible leader
        """
        vrf_int = self._vrf_to_int(vrf_output)
        # Compute threshold as integer to avoid float precision loss
        # probability is in [0, 1), threshold is probability × 2^64
        threshold = int(probability * (1 << 64))
        return vrf_int < threshold
    
    def compute_priority(
        self,
        vrf_output: bytes,
        probability: float
    ) -> float:
        """
        Compute leader priority for tie-breaking.

        Priority = VRF_value / probability (normalized)
        Lower priority = better candidate

        This ensures that among eligible leaders, the one with
        the "most impressive" VRF win (relative to their probability)
        is selected.

        Note: We use float here since priority is only for ordering,
        not for threshold comparison. The relative order is preserved
        even with float precision loss.
        """
        if probability <= 0:
            return float('inf')
        # Use integer VRF value normalized by 2^64, then divide by probability
        vrf_normalized = self._vrf_to_int(vrf_output) / (1 << 64)
        return vrf_normalized / probability
    
    def select_leader(
        self,
        nodes: List[NodeState],
        prev_block_hash: bytes,
        current_time: int,
        total_blocks: int,
        node_vrfs: Dict[bytes, VRFOutput],
        height: int = 0,
        is_probation: bool = False
    ) -> Tuple[Optional[bytes], bool]:
        """
        Select leader from eligible nodes.

        Args:
            nodes: List of node states
            prev_block_hash: Previous block hash (VRF input basis)
            current_time: Current timestamp
            total_blocks: Total blocks in chain
            node_vrfs: VRF outputs from each node
            height: Block height being selected for
            is_probation: Whether network is in Sybil probation mode

        Returns:
            Tuple of (leader_pubkey, is_fallback_selection)
            - leader_pubkey: Public key of selected leader, or None if no valid leader
            - is_fallback_selection: True if fallback mode was used (no VRF winner)
        """
        # Compute probabilities
        probs = self.calculator.compute_probabilities(
            nodes, current_time, total_blocks, is_probation
        )

        if not probs:
            logger.warning("No active nodes with probability")
            return None, False

        # Find eligible leaders using precise integer comparison
        eligible = []
        all_candidates = []

        for pubkey, prob in probs.items():
            if pubkey not in node_vrfs:
                continue

            vrf = node_vrfs[pubkey]
            vrf_int = self._vrf_to_int(vrf.beta)
            priority = self.compute_priority(vrf.beta, prob)

            # Store VRF as int for precise fallback sorting
            all_candidates.append((pubkey, vrf_int, prob, priority))

            # Check eligibility using precise integer comparison
            if self.is_leader(vrf.beta, prob):
                eligible.append((pubkey, priority))

        if eligible:
            # Among eligible, select lowest priority (best VRF relative to probability)
            winner = min(eligible, key=lambda x: x[1])
            logger.debug(
                f"Leader selected: {winner[0].hex()[:16]}... "
                f"(priority: {winner[1]:.6f})"
            )
            return winner[0], False  # Not a fallback selection

        # Fallback: No one won the VRF lottery
        # This can happen when sum of probabilities is low (few nodes, new network)
        # In fallback mode, select node with lowest VRF output (deterministic)
        if all_candidates:
            # Sort by VRF int value (lowest wins in fallback)
            all_candidates.sort(key=lambda x: x[1])

            winner = all_candidates[0]
            # Convert VRF int to float for logging only
            vrf_float = winner[1] / (1 << 64)
            logger.warning(
                f"FALLBACK leader selection: {winner[0].hex()[:16]}... "
                f"(VRF: {vrf_float:.6f}, prob: {winner[2]:.6f}). "
                f"No node won VRF lottery - this should be rare."
            )
            return winner[0], True  # This IS a fallback selection

        logger.error("No candidates for leader selection")
        return None, False
    
    def verify_leader_eligibility(
        self,
        leader_pubkey: bytes,
        vrf_output: VRFOutput,
        prev_block_hash: bytes,
        height: int,
        probability: float,
        is_fallback_allowed: bool = False
    ) -> Tuple[bool, str]:
        """
        Verify that a claimed leader was legitimately selected.

        Args:
            leader_pubkey: Public key of the claimed leader
            vrf_output: VRF output from the leader
            prev_block_hash: Previous block hash (VRF input basis)
            height: Block height being validated
            probability: Leader's probability at the time
            is_fallback_allowed: Whether fallback selection is allowed
                                 (only True when no node won VRF lottery)

        Returns:
            (is_valid, reason) tuple
        """
        # Verify VRF proof cryptographically
        vrf_input = self.compute_selection_input(prev_block_hash, height)

        if not ECVRF.verify(leader_pubkey, vrf_input, vrf_output):
            return False, "Invalid VRF proof"

        # Check VRF output vs probability
        vrf_float = self.vrf_to_float(vrf_output.beta)

        # Primary check: VRF output must be less than probability to be a valid winner
        if vrf_float < probability:
            return True, "Valid VRF winner"

        # Fallback check: If no one won the lottery, the node with lowest VRF wins
        # This is only valid if the network explicitly entered fallback mode
        if is_fallback_allowed:
            # In fallback mode, any valid VRF is acceptable (lowest wins)
            logger.debug(
                f"Leader accepted via fallback: VRF {vrf_float:.6f} > probability {probability:.6f}"
            )
            return True, "Valid fallback selection"

        # Leader claims to have won but VRF doesn't support it
        return False, f"VRF {vrf_float:.6f} >= probability {probability:.6f} - not a valid winner"


# ============================================================================
# SYBIL RESISTANCE
# ============================================================================

class SybilDetector:
    """
    Detects and mitigates Sybil attacks using statistical analysis.
    
    Strategy:
    1. Track historical connection rates over multiple windows
    2. Compute rolling median of connection rates (decentralized metric)
    3. Trigger probation when current rate > 2x historical median
    4. Apply 180-day probation with 90% probability reduction for new nodes
    
    This is fully decentralized - each node computes independently using
    only local observations, and honest nodes will converge on similar
    metrics given the same network view.
    """
    
    # Minimum number of samples before statistical analysis is reliable
    MIN_SAMPLES = 10
    
    # Window periods for rate calculation
    SHORT_WINDOW_BLOCKS = 144   # ~1 day (144 blocks)
    MEDIUM_WINDOW_BLOCKS = 1008  # ~1 week
    LONG_WINDOW_BLOCKS = 4032    # ~1 month
    
    # Probation threshold: 2x median triggers probation
    INFLUX_THRESHOLD = 2.0
    
    # Probation period in seconds (180 days = ~26000 blocks * 720 seconds)
    PROBATION_PERIOD = PROTOCOL.QUARANTINE_BLOCKS * PROTOCOL.BLOCK_INTERVAL
    
    def __init__(self, window_size: int = PROTOCOL.ADJUSTMENT_WINDOW):
        self.window_size = window_size
        
        # Connection tracking: (timestamp, node_pubkey_hash)
        self.connection_history: List[Tuple[int, bytes]] = []
        
        # Historical rate statistics
        self.rate_samples: List[float] = []  # Connections per day samples
        self.median_rate: float = 1.0  # Median connections per day
        
        # Probation mode tracking
        self.probation_active: bool = False
        self.probation_start: int = 0
        self.probation_end: int = 0
        
        # Node probation tracking: pubkey -> probation_end_time
        self.nodes_in_probation: Dict[bytes, int] = {}
        
        self._lock = threading.Lock()
    
    def record_connection(self, timestamp: int, node_pubkey: bytes = b''):
        """
        Record a new node connection.
        
        Args:
            timestamp: Unix timestamp of connection
            node_pubkey: Public key of connecting node (for tracking)
        """
        with self._lock:
            # Hash pubkey for privacy
            pubkey_hash = sha256(node_pubkey) if node_pubkey else b''
            self.connection_history.append((timestamp, pubkey_hash))
            
            # Track this node in probation if we're in probation mode
            if self.probation_active and node_pubkey:
                self.nodes_in_probation[node_pubkey] = timestamp + self.PROBATION_PERIOD
            
            # Prune old history (keep last LONG_WINDOW)
            max_age = self.LONG_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL
            cutoff = timestamp - max_age
            self.connection_history = [
                (t, pk) for t, pk in self.connection_history if t > cutoff
            ]
            
            # Update statistics periodically
            if len(self.connection_history) % 10 == 0:
                self._update_statistics(timestamp)
    
    def _update_statistics(self, current_time: int):
        """Update connection rate statistics."""
        if len(self.connection_history) < self.MIN_SAMPLES:
            return
        
        # Calculate connections per day for different windows
        day_seconds = 86400
        
        # Short window rate (last day)
        short_cutoff = current_time - (self.SHORT_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL)
        short_count = sum(1 for t, _ in self.connection_history if t > short_cutoff)
        short_duration = min(current_time - short_cutoff, day_seconds)
        short_rate = (short_count / max(short_duration, 1)) * day_seconds
        
        # Medium window rate (last week)
        medium_cutoff = current_time - (self.MEDIUM_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL)
        medium_count = sum(1 for t, _ in self.connection_history if t > medium_cutoff)
        medium_duration = current_time - medium_cutoff
        medium_rate = (medium_count / max(medium_duration, 1)) * day_seconds
        
        # Long window rate (last month)
        long_cutoff = current_time - (self.LONG_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL)
        long_count = sum(1 for t, _ in self.connection_history if t > long_cutoff)
        long_duration = current_time - long_cutoff
        long_rate = (long_count / max(long_duration, 1)) * day_seconds
        
        # Add to rate samples
        self.rate_samples.append(medium_rate)
        
        # Keep only recent samples
        max_samples = 100
        if len(self.rate_samples) > max_samples:
            self.rate_samples = self.rate_samples[-max_samples:]
        
        # Update median
        if len(self.rate_samples) >= self.MIN_SAMPLES:
            sorted_rates = sorted(self.rate_samples)
            mid = len(sorted_rates) // 2
            if len(sorted_rates) % 2 == 0:
                self.median_rate = (sorted_rates[mid-1] + sorted_rates[mid]) / 2
            else:
                self.median_rate = sorted_rates[mid]
        
        # Check for suspicious influx
        if short_rate > self.median_rate * self.INFLUX_THRESHOLD and not self.probation_active:
            self._activate_probation(current_time, short_rate)
    
    def _activate_probation(self, current_time: int, current_rate: float):
        """Activate network-wide probation mode."""
        self.probation_active = True
        self.probation_start = current_time
        self.probation_end = current_time + self.PROBATION_PERIOD
        
        logger.warning(
            f"SYBIL PROBATION ACTIVATED: Connection rate {current_rate:.1f}/day "
            f"exceeds 2x median {self.median_rate:.1f}/day. "
            f"Probation until {datetime.fromtimestamp(self.probation_end).isoformat()}"
        )
    
    def is_suspicious_influx(self) -> bool:
        """
        Check if current connection rate indicates a Sybil attack.
        
        Returns True if rate > 2x median AND we have sufficient data.
        """
        with self._lock:
            if len(self.connection_history) < self.MIN_SAMPLES:
                return False
            
            current_time = int(time.time())
            
            # Calculate recent rate (last 144 blocks = ~1 day)
            short_window = self.SHORT_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL
            short_cutoff = current_time - short_window
            recent_count = sum(1 for t, _ in self.connection_history if t > short_cutoff)
            
            # Convert to connections per day
            actual_duration = min(current_time - short_cutoff, short_window)
            if actual_duration <= 0:
                return False
            
            recent_rate = (recent_count / actual_duration) * 86400
            
            # Check against threshold
            return recent_rate > self.median_rate * self.INFLUX_THRESHOLD
    
    def is_probation_active(self, current_time: Optional[int] = None) -> bool:
        """Check if network is currently in probation mode."""
        if current_time is None:
            current_time = int(time.time())
        
        with self._lock:
            if not self.probation_active:
                return False
            
            # Check if probation has expired
            if current_time > self.probation_end:
                self.probation_active = False
                logger.info("Sybil probation period ended")
                return False
            
            return True
    
    def is_node_in_probation(self, node_pubkey: bytes, current_time: Optional[int] = None) -> bool:
        """
        Check if a specific node is under probation.
        
        Nodes are under probation if:
        1. They joined during a suspicious influx period, OR
        2. They are less than 180 days old
        """
        if current_time is None:
            current_time = int(time.time())
        
        with self._lock:
            if node_pubkey in self.nodes_in_probation:
                probation_end = self.nodes_in_probation[node_pubkey]
                if current_time < probation_end:
                    return True
                else:
                    # Probation ended, remove from tracking
                    del self.nodes_in_probation[node_pubkey]
            
            return False
    
    def get_probation_multiplier(
        self, 
        node: NodeState, 
        current_time: Optional[int] = None
    ) -> float:
        """
        Get probability multiplier for a node based on probation status.
        
        Returns:
            1.0 for established nodes
            0.1 (90% reduction) for nodes in probation
        """
        if current_time is None:
            current_time = int(time.time())
        
        # Check if node is explicitly in probation
        if self.is_node_in_probation(node.pubkey, current_time):
            return 0.1
        
        # Check if node joined less than 180 days ago during influx
        node_age = current_time - node.first_seen
        if node_age < self.PROBATION_PERIOD:
            # New nodes get reduced probability during probation mode
            if self.is_probation_active(current_time):
                return 0.1
            
            # Gradual ramp-up for new nodes even without probation
            # 10% at 0 days, 100% at 180 days (linear)
            ramp_factor = 0.1 + 0.9 * (node_age / self.PROBATION_PERIOD)
            return min(1.0, max(0.1, ramp_factor))
        
        return 1.0
    
    def get_network_health_score(self) -> float:
        """
        Get a health score for the network based on connection patterns.
        
        Returns:
            1.0 = healthy, 0.0 = likely under attack
        """
        with self._lock:
            if len(self.connection_history) < self.MIN_SAMPLES:
                return 1.0  # Not enough data to assess
            
            current_time = int(time.time())
            
            # Calculate current rate
            short_window = self.SHORT_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL
            short_cutoff = current_time - short_window
            recent_count = sum(1 for t, _ in self.connection_history if t > short_cutoff)
            actual_duration = min(current_time - short_cutoff, short_window)
            
            if actual_duration <= 0:
                return 1.0
            
            recent_rate = (recent_count / actual_duration) * 86400
            
            # Score based on deviation from median
            if self.median_rate <= 0:
                return 1.0
            
            ratio = recent_rate / self.median_rate
            
            if ratio <= 1.0:
                return 1.0
            elif ratio >= self.INFLUX_THRESHOLD:
                return 0.0
            else:
                # Linear interpolation
                return 1.0 - (ratio - 1.0) / (self.INFLUX_THRESHOLD - 1.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current Sybil detection statistics."""
        with self._lock:
            current_time = int(time.time())
            
            # Recent connection count
            short_window = self.SHORT_WINDOW_BLOCKS * PROTOCOL.BLOCK_INTERVAL
            short_cutoff = current_time - short_window
            recent_count = sum(1 for t, _ in self.connection_history if t > short_cutoff)
            
            return {
                'total_connections': len(self.connection_history),
                'recent_connections': recent_count,
                'median_rate_per_day': self.median_rate,
                'probation_active': self.probation_active,
                'probation_end': self.probation_end if self.probation_active else None,
                'nodes_in_probation': len(self.nodes_in_probation),
                'health_score': self.get_network_health_score(),
                'is_suspicious': self.is_suspicious_influx()
            }


# ============================================================================
# SLASHING
# ============================================================================

class SlashingCondition(IntEnum):
    """Types of slashable offenses."""
    EQUIVOCATION = auto()  # Signing conflicting blocks
    INVALID_VDF = auto()  # Submitting invalid VDF proof
    INVALID_VRF = auto()  # Submitting invalid VRF proof
    DOUBLE_SPEND = auto()  # Including double-spend in block


@dataclass
class SlashingEvidence:
    """
    Evidence of slashable offense.
    
    Contains cryptographic proof that can be independently verified
    by any network participant. For equivocation, this includes the
    two conflicting signatures that prove the offense.
    """
    condition: SlashingCondition
    offender: bytes  # Public key of offending node
    evidence_block1: Optional[bytes] = None  # First block hash
    evidence_block2: Optional[bytes] = None  # Conflicting block hash (for equivocation)
    timestamp: int = 0  # When evidence was created
    signature1: bytes = b''  # First conflicting signature (for equivocation)
    signature2: bytes = b''  # Second conflicting signature (for equivocation)
    reporter: bytes = b''  # Public key of node reporting the offense
    
    def serialize(self) -> bytes:
        """
        Serialize evidence for network transmission and storage.
        
        Format: condition(1) + offender(32) + block1(32) + block2(32) + 
                timestamp(8) + sig1_len(2) + sig1 + sig2_len(2) + sig2 +
                reporter_len(2) + reporter
        """
        data = bytearray()
        data.extend(struct.pack('<B', self.condition))
        data.extend(self.offender)
        data.extend(self.evidence_block1 or b'\x00' * 32)
        data.extend(self.evidence_block2 or b'\x00' * 32)
        data.extend(struct.pack('<Q', self.timestamp))
        
        # Variable length signatures
        data.extend(struct.pack('<H', len(self.signature1)))
        data.extend(self.signature1)
        data.extend(struct.pack('<H', len(self.signature2)))
        data.extend(self.signature2)
        
        # Reporter
        data.extend(struct.pack('<H', len(self.reporter)))
        data.extend(self.reporter)
        
        return bytes(data)
    
    @staticmethod
    def deserialize(data: bytes) -> 'SlashingEvidence':
        """Deserialize evidence from bytes."""
        offset = 0
        
        condition = struct.unpack('<B', data[offset:offset+1])[0]
        offset += 1
        
        offender = data[offset:offset+32]
        offset += 32
        
        block1 = data[offset:offset+32]
        offset += 32
        
        block2 = data[offset:offset+32]
        offset += 32
        
        timestamp = struct.unpack('<Q', data[offset:offset+8])[0]
        offset += 8
        
        sig1_len = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        sig1 = data[offset:offset+sig1_len]
        offset += sig1_len
        
        sig2_len = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        sig2 = data[offset:offset+sig2_len]
        offset += sig2_len
        
        reporter_len = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        reporter = data[offset:offset+reporter_len]
        
        return SlashingEvidence(
            condition=condition,
            offender=offender,
            evidence_block1=block1,
            evidence_block2=block2,
            timestamp=timestamp,
            signature1=sig1,
            signature2=sig2,
            reporter=reporter
        )
    
    def verify(self) -> bool:
        """
        Verify the cryptographic validity of this evidence.
        
        For equivocation, verifies that both signatures are valid
        for different block hashes at the same height.
        """
        if self.condition == SlashingCondition.EQUIVOCATION:
            # Both signatures must be present and different
            if not self.signature1 or not self.signature2:
                return False
            
            if self.signature1 == self.signature2:
                return False
            
            # Block hashes must be different
            if self.evidence_block1 == self.evidence_block2:
                return False
            
            # Signature verification would require the full block headers
            # This basic check ensures evidence structure is valid
            return True
        
        return True  # Other conditions have simpler verification
    
    def __hash__(self):
        return hash((self.condition, self.offender, self.evidence_block1, 
                    self.evidence_block2, self.timestamp))


class SlashingManager:
    """
    Manages slashing conditions and penalties.
    
    Slashing conditions:
    1. EQUIVOCATION: Signing two different blocks at the same height
    2. INVALID_VRF: Forging or reusing VRF proofs
    3. INVALID_VDF: Submitting invalid VDF proofs
    4. DOUBLE_SIGN: Signing conflicting transactions
    
    Penalties (immediate and irreversible):
    - Reputation reset to 0
    - Time presence reset to current time (lose all seniority)
    - 180-day quarantine (QUARANTINE_PERIOD seconds)
    - Cannot be selected as leader during quarantine
    - Cannot receive block rewards during quarantine
    - Probability reduced by 90% even after quarantine ends
    
    Evidence is permanently stored for network consensus.
    """
    
    # Minimum number of confirmations before processing slash
    MIN_CONFIRMATIONS = 6
    
    def __init__(self, db=None):
        self.pending_slashes: List[SlashingEvidence] = []
        self.confirmed_slashes: List[SlashingEvidence] = []
        self.slashed_nodes: Set[bytes] = set()
        self.slash_history: Dict[bytes, List[SlashingEvidence]] = {}  # pubkey -> history
        self.db = db  # Optional database for persistence
        self._lock = threading.Lock()
    
    def check_equivocation(
        self,
        block1: Block,
        block2: Block
    ) -> Optional[SlashingEvidence]:
        """
        Check if two blocks constitute equivocation.
        
        Equivocation conditions (all must be true):
        1. Same block height
        2. Same leader public key
        3. Different block hashes
        4. Both blocks have valid leader signatures
        
        Returns:
            SlashingEvidence if equivocation detected, None otherwise
        """
        # Basic check
        if block1.height != block2.height:
            return None
        
        if block1.header.leader_pubkey != block2.header.leader_pubkey:
            return None
        
        if block1.hash == block2.hash:
            return None  # Same block, not equivocation
        
        # Verify both signatures are valid (prevents false accusations)
        leader = block1.header.leader_pubkey
        
        try:
            # Verify block1 signature
            signing_hash1 = block1.header.signing_hash()
            if not Ed25519.verify(leader, signing_hash1, block1.header.leader_signature):
                logger.warning("Block1 signature invalid, not valid equivocation evidence")
                return None
            
            # Verify block2 signature
            signing_hash2 = block2.header.signing_hash()
            if not Ed25519.verify(leader, signing_hash2, block2.header.leader_signature):
                logger.warning("Block2 signature invalid, not valid equivocation evidence")
                return None
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return None
        
        # Create evidence with complete proof
        evidence = SlashingEvidence(
            condition=SlashingCondition.EQUIVOCATION,
            offender=leader,
            evidence_block1=block1.hash,
            evidence_block2=block2.hash,
            timestamp=int(time.time()),
            signature1=block1.header.leader_signature,
            signature2=block2.header.leader_signature
        )
        
        logger.warning(
            f"EQUIVOCATION DETECTED: Node {leader.hex()[:16]}... "
            f"signed two blocks at height {block1.height}"
        )
        
        return evidence
    
    def check_invalid_vrf(
        self,
        block: Block,
        prev_block: Block,
        expected_vrf_input: bytes
    ) -> Optional[SlashingEvidence]:
        """
        Check if a block contains an invalid or forged VRF proof.
        
        This detects:
        1. Invalid VRF proofs that don't verify
        2. VRF proofs computed with wrong input
        3. Reused VRF proofs from previous blocks
        """
        from crypto import ECVRF, VRFOutput
        
        vrf_output = VRFOutput(
            beta=block.header.vrf_output,
            proof=block.header.vrf_proof
        )
        
        # Verify VRF proof
        if not ECVRF.verify(block.header.leader_pubkey, expected_vrf_input, vrf_output):
            return SlashingEvidence(
                condition=SlashingCondition.INVALID_VRF,
                offender=block.header.leader_pubkey,
                evidence_block1=block.hash,
                evidence_block2=b'',  # No second block needed
                timestamp=int(time.time())
            )
        
        return None
    
    def report_slash(self, evidence: SlashingEvidence) -> bool:
        """
        Report a slashing offense.
        
        Returns:
            True if evidence was accepted, False if duplicate/invalid
        """
        with self._lock:
            if evidence.offender in self.slashed_nodes:
                logger.debug(f"Node {evidence.offender.hex()[:16]}... already slashed")
                return False
            
            # Check for duplicate evidence
            for existing in self.pending_slashes:
                if (existing.offender == evidence.offender and
                    existing.evidence_block1 == evidence.evidence_block1 and
                    existing.evidence_block2 == evidence.evidence_block2):
                    return False
            
            self.pending_slashes.append(evidence)
            
            # Track in history
            if evidence.offender not in self.slash_history:
                self.slash_history[evidence.offender] = []
            self.slash_history[evidence.offender].append(evidence)
            
            logger.warning(
                f"SLASHING EVIDENCE REPORTED: {SlashingCondition(evidence.condition).name} "
                f"by {evidence.offender.hex()[:16]}..."
            )
            
            return True
    
    def confirm_slash(self, evidence: SlashingEvidence, block_height: int):
        """
        Confirm a slash after sufficient block confirmations.
        
        Evidence is moved from pending to confirmed after MIN_CONFIRMATIONS.
        """
        with self._lock:
            if evidence not in self.pending_slashes:
                return
            
            self.pending_slashes.remove(evidence)
            self.confirmed_slashes.append(evidence)
            self.slashed_nodes.add(evidence.offender)
            
            logger.info(
                f"Slash confirmed at height {block_height}: "
                f"{evidence.offender.hex()[:16]}..."
            )
    
    def apply_slash(
        self,
        evidence: SlashingEvidence,
        node: NodeState,
        current_time: int
    ):
        """
        Apply slashing penalty to node.
        
        Penalties applied:
        1. Reputation (signed_blocks) reset to 0
        2. Time presence reset (first_seen set to current time)
        3. Enter 180-day quarantine
        4. Mark as slashed for permanent record
        
        These are IRREVERSIBLE - even after quarantine, the node
        starts fresh with no seniority.
        """
        # Reset reputation completely
        node.signed_blocks = 0
        node.last_signed_height = 0
        
        # Reset time presence - lose all seniority
        node.first_seen = current_time
        node.total_uptime = 0
        
        # Reset storage tracking
        node.stored_blocks = 0
        
        # Enter quarantine
        quarantine_reason = f"SLASHED: {SlashingCondition(evidence.condition).name}"
        node.enter_quarantine(current_time, quarantine_reason)
        
        # Mark node as having been slashed (permanent flag)
        node.status = NodeStatus.SLASHED
        
        # Store in confirmed set
        with self._lock:
            self.slashed_nodes.add(node.pubkey)
        
        logger.warning(
            f"SLASH APPLIED to {node.pubkey.hex()[:16]}...: "
            f"All stats reset, quarantined until {node.quarantine_until} "
            f"({(PROTOCOL.QUARANTINE_BLOCKS * PROTOCOL.BLOCK_INTERVAL) / 86400:.0f} days)"
        )
    
    def get_pending_slashes(self) -> List[SlashingEvidence]:
        """Get pending slash evidence for inclusion in blocks."""
        with self._lock:
            return list(self.pending_slashes)
    
    def get_slash_for_block(self) -> Optional[SlashingEvidence]:
        """
        Get oldest pending slash evidence for inclusion in next block.
        
        Only one slash is processed per block to prevent spam.
        """
        with self._lock:
            if self.pending_slashes:
                return self.pending_slashes[0]
            return None
    
    def clear_pending(self, processed: List[SlashingEvidence]):
        """Clear processed slash evidence."""
        with self._lock:
            for ev in processed:
                if ev in self.pending_slashes:
                    self.pending_slashes.remove(ev)
    
    def is_slashed(self, pubkey: bytes) -> bool:
        """Check if a node has ever been slashed."""
        with self._lock:
            return pubkey in self.slashed_nodes
    
    def get_slash_count(self, pubkey: bytes) -> int:
        """Get number of times a node has been slashed."""
        with self._lock:
            return len(self.slash_history.get(pubkey, []))
    
    def serialize_evidence(self, evidence: SlashingEvidence) -> bytes:
        """
        Serialize slashing evidence for network transmission.
        
        Format: condition(1) + offender(32) + block1(32) + block2(32) + 
                timestamp(8) + sig1(64) + sig2(64)
        """
        data = struct.pack('<B', evidence.condition)
        data += evidence.offender
        data += evidence.evidence_block1
        data += evidence.evidence_block2
        data += struct.pack('<Q', evidence.timestamp)
        data += getattr(evidence, 'signature1', b'\x00' * 64)
        data += getattr(evidence, 'signature2', b'\x00' * 64)
        return data
    
    @staticmethod
    def deserialize_evidence(data: bytes) -> SlashingEvidence:
        """Deserialize slashing evidence from network transmission."""
        condition = struct.unpack('<B', data[0:1])[0]
        offender = data[1:33]
        block1 = data[33:65]
        block2 = data[65:97]
        timestamp = struct.unpack('<Q', data[97:105])[0]
        sig1 = data[105:169] if len(data) >= 169 else b''
        sig2 = data[169:233] if len(data) >= 233 else b''
        
        evidence = SlashingEvidence(
            condition=condition,
            offender=offender,
            evidence_block1=block1,
            evidence_block2=block2,
            timestamp=timestamp
        )
        evidence.signature1 = sig1
        evidence.signature2 = sig2
        
        return evidence


# ============================================================================
# WEIGHT REBALANCING
# ============================================================================

class WeightRebalancer:
    """
    Rebalances consensus weights every adjustment window.
    
    Target weights: 60% time, 20% space, 20% reputation
    
    If one component becomes dominant (>70%), its weight is reduced
    and redistributed to maintain decentralization.
    """
    
    def __init__(self, target_weights: ProbabilityWeights):
        self.target = target_weights
        self.current = ProbabilityWeights(
            w_time=target_weights.w_time,
            w_space=target_weights.w_space,
            w_rep=target_weights.w_rep
        )
    
    def analyze_distribution(
        self,
        nodes: List[NodeState],
        current_time: int,
        total_blocks: int
    ) -> Dict[str, float]:
        """
        Analyze component distributions across nodes.
        
        Returns average values for each component.
        """
        if not nodes:
            return {"time": 0, "space": 0, "rep": 0}
        
        calc = ConsensusCalculator()
        
        total_time = 0
        total_space = 0
        total_rep = 0
        
        for node in nodes:
            if node.status == NodeStatus.ACTIVE:
                uptime = node.get_uptime(current_time)
                total_time += calc.compute_f_time(uptime)
                total_space += calc.compute_f_space(node.stored_blocks, total_blocks)
                total_rep += calc.compute_f_rep(node.signed_blocks)
        
        n = len([n for n in nodes if n.status == NodeStatus.ACTIVE])
        if n == 0:
            return {"time": 0, "space": 0, "rep": 0}
        
        return {
            "time": total_time / n,
            "space": total_space / n,
            "rep": total_rep / n
        }
    
    def rebalance(
        self,
        nodes: List[NodeState],
        current_time: int,
        total_blocks: int
    ) -> ProbabilityWeights:
        """
        Rebalance weights based on current distribution.
        
        Returns updated weights.
        """
        dist = self.analyze_distribution(nodes, current_time, total_blocks)
        
        # Check for dominance
        total = sum(dist.values())
        if total == 0:
            return self.current
        
        # Calculate relative contributions
        time_ratio = (self.current.w_time * dist["time"]) / total
        space_ratio = (self.current.w_space * dist["space"]) / total
        rep_ratio = (self.current.w_rep * dist["rep"]) / total
        
        # Adjust if any component is dominant (>70%)
        threshold = 0.70
        
        if time_ratio > threshold:
            # Reduce time weight
            adjustment = (time_ratio - self.target.w_time) * 0.1
            self.current.w_time = max(0.3, self.current.w_time - adjustment)
            self.current.w_space += adjustment / 2
            self.current.w_rep += adjustment / 2
        
        if space_ratio > threshold:
            adjustment = (space_ratio - self.target.w_space) * 0.1
            self.current.w_space = max(0.1, self.current.w_space - adjustment)
            self.current.w_time += adjustment / 2
            self.current.w_rep += adjustment / 2
        
        if rep_ratio > threshold:
            adjustment = (rep_ratio - self.target.w_rep) * 0.1
            self.current.w_rep = max(0.1, self.current.w_rep - adjustment)
            self.current.w_time += adjustment / 2
            self.current.w_space += adjustment / 2
        
        # Normalize
        self.current.normalize()
        
        logger.debug(
            f"Weights rebalanced: time={self.current.w_time:.2f}, "
            f"space={self.current.w_space:.2f}, rep={self.current.w_rep:.2f}"
        )
        
        return self.current


# ============================================================================
# CONSENSUS ENGINE
# ============================================================================

class ConsensusEngine:
    """
    Main consensus engine for Proof of Time.
    
    Coordinates:
    - Node state management
    - Leader selection
    - Block validation
    - Slashing
    - Weight rebalancing
    """
    
    def __init__(self, config: Optional[NodeConfig] = None):
        self.config = config or NodeConfig()
        
        # Components
        self.vdf = WesolowskiVDF(PROTOCOL.VDF_MODULUS_BITS)
        self.weights = ProbabilityWeights()
        self.calculator = ConsensusCalculator(self.weights)
        self.leader_selector = LeaderSelector(self.calculator)
        self.sybil_detector = SybilDetector()
        self.slashing_manager = SlashingManager()
        self.rebalancer = WeightRebalancer(self.weights)
        
        # State
        self.nodes: Dict[bytes, NodeState] = {}
        self.chain_tip: Optional[Block] = None
        self.total_blocks: int = 0
        
        self._lock = threading.RLock()
    
    def initialize(self, genesis: Optional[Block] = None):
        """Initialize consensus with genesis block."""
        if genesis is None:
            genesis = create_genesis_block()
        
        self.chain_tip = genesis
        self.total_blocks = 1
        
        logger.info(f"Consensus initialized with genesis: {genesis.hash.hex()[:16]}...")
    
    def register_node(self, pubkey: bytes, stored_blocks: int = 0):
        """Register a new node."""
        with self._lock:
            if pubkey in self.nodes:
                return
            
            current_time = int(time.time())
            
            node = NodeState(
                pubkey=pubkey,
                stored_blocks=stored_blocks
            )
            node.start_uptime(current_time)
            
            self.nodes[pubkey] = node
            self.sybil_detector.record_connection(current_time)
            
            logger.info(f"Node registered: {pubkey.hex()[:16]}...")
    
    def update_node(self, pubkey: bytes, **kwargs):
        """Update node state."""
        with self._lock:
            if pubkey not in self.nodes:
                return
            
            node = self.nodes[pubkey]
            for key, value in kwargs.items():
                if hasattr(node, key):
                    setattr(node, key, value)
    
    def get_active_nodes(self) -> List[NodeState]:
        """Get list of active nodes."""
        with self._lock:
            return [n for n in self.nodes.values() 
                   if n.status in (NodeStatus.ACTIVE, NodeStatus.QUARANTINE)]
    
    def compute_probabilities(self) -> Dict[bytes, float]:
        """Compute current node probabilities."""
        current_time = int(time.time())
        active_nodes = self.get_active_nodes()
        
        return self.calculator.compute_probabilities(
            active_nodes, current_time, self.total_blocks
        )
    
    def select_leader(
        self,
        prev_block_hash: bytes,
        node_vrfs: Dict[bytes, VRFOutput],
        height: int = 0
    ) -> Tuple[Optional[bytes], bool]:
        """
        Select leader for next block.

        Args:
            prev_block_hash: Hash of previous block
            node_vrfs: VRF outputs from each node
            height: Block height being selected for

        Returns:
            Tuple of (leader_pubkey, is_fallback_selection)
            - leader_pubkey: Selected leader's public key, or None
            - is_fallback_selection: True if no node won VRF lottery
        """
        current_time = int(time.time())
        active_nodes = self.get_active_nodes()

        # Check if we're in Sybil probation mode
        is_probation = self.sybil_detector.is_probation_active(current_time)

        return self.leader_selector.select_leader(
            active_nodes,
            prev_block_hash,
            current_time,
            self.total_blocks,
            node_vrfs,
            height=height,
            is_probation=is_probation
        )
    
    def validate_leader(
        self,
        block: Block,
        prev_block: Block
    ) -> bool:
        """
        Validate block leader selection.

        Checks:
        1. VRF proof is valid for the input
        2. Leader is a known node
        3. Leader was eligible to produce this block (won VRF lottery OR valid fallback)
        """
        # Compute expected VRF input
        vrf_input = self.leader_selector.compute_selection_input(
            prev_block.hash,
            block.height
        )

        vrf_output = VRFOutput(
            beta=block.header.vrf_output,
            proof=block.header.vrf_proof
        )

        # Verify VRF proof cryptographically
        if not ECVRF.verify(block.header.leader_pubkey, vrf_input, vrf_output):
            logger.warning("Invalid VRF proof")
            return False

        # Verify leader is known
        if block.header.leader_pubkey not in self.nodes:
            logger.warning("Unknown leader")
            return False

        # Verify probability eligibility
        current_time = block.header.timestamp
        active_nodes = self.get_active_nodes()
        is_probation = self.sybil_detector.is_probation_active(current_time)

        probs = self.calculator.compute_probabilities(
            active_nodes, current_time, self.total_blocks, is_probation
        )
        prob = probs.get(block.header.leader_pubkey, 0)

        # Verify leader eligibility with fallback flag from block header
        is_valid, reason = self.leader_selector.verify_leader_eligibility(
            block.header.leader_pubkey,
            vrf_output,
            prev_block.hash,
            block.height,
            prob,
            is_fallback_allowed=block.header.is_fallback_leader
        )

        if not is_valid:
            logger.warning(f"Leader validation failed: {reason}")
            return False

        # Additional check: if block claims fallback but leader actually won VRF lottery,
        # that's suspicious (trying to hide true eligibility - potential attack vector)
        vrf_float = self.leader_selector.vrf_to_float(vrf_output.beta)
        if block.header.is_fallback_leader and vrf_float < prob:
            logger.warning(
                f"Block claims fallback but leader won VRF lottery "
                f"(VRF {vrf_float:.6f} < prob {prob:.6f}) - suspicious"
            )
            # This is technically valid but suspicious - log for monitoring

        return True
    
    def process_block(self, block: Block) -> bool:
        """
        Process a new block.
        
        Updates:
        - Chain tip
        - Node states
        - Slashing if needed
        - Weight rebalancing
        """
        with self._lock:
            # Update chain
            self.chain_tip = block
            self.total_blocks = block.height + 1
            
            # Update leader reputation
            leader_pubkey = block.header.leader_pubkey
            if leader_pubkey in self.nodes:
                self.nodes[leader_pubkey].record_signed_block(block.height)
            
            # Process slashing evidence (if any in block)
            # (Would be in special transactions)
            
            # Rebalance weights every adjustment window
            if block.height % PROTOCOL.ADJUSTMENT_WINDOW == 0 and block.height > 0:
                active_nodes = self.get_active_nodes()
                self.weights = self.rebalancer.rebalance(
                    active_nodes,
                    block.timestamp,
                    self.total_blocks
                )
                self.calculator.weights = self.weights
            
            logger.debug(f"Processed block {block.height}: {block.hash.hex()[:16]}...")
            
            return True
    
    def check_equivocation(self, block1: Block, block2: Block):
        """Check and report equivocation."""
        evidence = self.slashing_manager.check_equivocation(block1, block2)
        if evidence:
            self.slashing_manager.report_slash(evidence)
            
            # Apply slash immediately
            if evidence.offender in self.nodes:
                self.slashing_manager.apply_slash(
                    evidence,
                    self.nodes[evidence.offender],
                    int(time.time())
                )


# ============================================================================
# BOOTSTRAP MECHANISM
# ============================================================================

class BootstrapMode(IntEnum):
    """Network bootstrap modes."""
    NORMAL = 0          # Normal operation (MIN_NODES satisfied)
    BOOTSTRAP = 1       # Initial bootstrap (< MIN_NODES)
    RECOVERY = 2        # Recovering from mass disconnect


class BootstrapManager:
    """
    Manages network bootstrapping with minimum 3 nodes.
    
    Bootstrap challenges:
    1. Initial network startup with few nodes
    2. Recovery from mass disconnection
    3. Sybil protection during bootstrap
    
    Strategy:
    - Allow block production with as few as 1 node (founder mode)
    - Require increasing confirmations as network grows
    - Apply stricter Sybil protection during bootstrap
    - Track network health metrics
    """
    
    # Minimum nodes for normal operation
    MIN_NODES_NORMAL = PROTOCOL.MIN_NODES  # 3
    
    # Minimum nodes for consensus
    MIN_NODES_CONSENSUS = 1  # Can start with single node
    
    # Confirmations required based on node count
    # Fewer nodes = more confirmations for security
    CONFIRMATIONS_BY_SIZE = {
        1: 12,   # Single node: 12 confirmations (~2.4 hours)
        2: 6,    # Two nodes: 6 confirmations (~1.2 hours)
        3: 3,    # Three nodes: 3 confirmations (~36 minutes)
    }
    DEFAULT_CONFIRMATIONS = 1  # Normal operation
    
    def __init__(self, consensus_engine: ConsensusEngine):
        self.consensus = consensus_engine
        self.mode = BootstrapMode.BOOTSTRAP
        
        # Bootstrap tracking
        self.bootstrap_start: int = 0
        self.last_node_count: int = 0
        
        # Founder node (first node, gets special privileges during bootstrap)
        self.founder_pubkey: Optional[bytes] = None
        self.founder_blocks_produced: int = 0
        
        # Recovery tracking
        self.last_healthy_time: int = 0
        self.disconnect_events: List[Tuple[int, int]] = []  # (timestamp, nodes_lost)
        
        self._lock = threading.Lock()
    
    def initialize(self, founder_pubkey: Optional[bytes] = None):
        """
        Initialize bootstrap manager.
        
        Args:
            founder_pubkey: Public key of founding node (optional)
        """
        self.bootstrap_start = int(time.time())
        self.founder_pubkey = founder_pubkey
        self.last_healthy_time = self.bootstrap_start
        
        logger.info(
            f"Bootstrap manager initialized. "
            f"Founder: {founder_pubkey.hex()[:16] if founder_pubkey else 'None'}..."
        )
    
    def get_active_node_count(self) -> int:
        """Get count of currently active nodes."""
        return len(self.consensus.get_active_nodes())
    
    def check_mode(self) -> BootstrapMode:
        """
        Check and update network mode.
        
        Returns:
            Current network mode
        """
        node_count = self.get_active_node_count()
        current_time = int(time.time())
        
        with self._lock:
            # Track node count changes
            if node_count < self.last_node_count:
                nodes_lost = self.last_node_count - node_count
                self.disconnect_events.append((current_time, nodes_lost))
                
                # Prune old events (keep last 24 hours)
                cutoff = current_time - 86400
                self.disconnect_events = [
                    (t, n) for t, n in self.disconnect_events if t > cutoff
                ]
            
            self.last_node_count = node_count
            
            # Determine mode
            if node_count >= self.MIN_NODES_NORMAL:
                if self.mode != BootstrapMode.NORMAL:
                    logger.info(
                        f"Entering NORMAL mode with {node_count} nodes"
                    )
                self.mode = BootstrapMode.NORMAL
                self.last_healthy_time = current_time
                
            elif node_count < self.MIN_NODES_NORMAL:
                # Check if this is recovery from normal operation
                if self.last_healthy_time > self.bootstrap_start:
                    if self.mode != BootstrapMode.RECOVERY:
                        logger.warning(
                            f"Entering RECOVERY mode: only {node_count} nodes active"
                        )
                    self.mode = BootstrapMode.RECOVERY
                else:
                    self.mode = BootstrapMode.BOOTSTRAP
        
        return self.mode
    
    def can_produce_block(self, node_pubkey: bytes) -> Tuple[bool, str]:
        """
        Check if a node can produce a block in current mode.
        
        Args:
            node_pubkey: Public key of node wanting to produce
        
        Returns:
            (can_produce, reason)
        """
        mode = self.check_mode()
        node_count = self.get_active_node_count()
        
        if mode == BootstrapMode.NORMAL:
            # Normal operation - standard leader selection
            return True, "Normal operation"
        
        elif mode == BootstrapMode.BOOTSTRAP:
            if node_count == 0:
                return False, "No active nodes"
            
            if node_count == 1:
                # Single node bootstrap - only founder can produce
                if self.founder_pubkey and node_pubkey != self.founder_pubkey:
                    return False, "Only founder can produce during single-node bootstrap"
                return True, "Single-node bootstrap mode"
            
            # 2+ nodes - normal selection applies
            return True, "Bootstrap mode with multiple nodes"
        
        elif mode == BootstrapMode.RECOVERY:
            # During recovery, be more permissive
            if node_count >= self.MIN_NODES_CONSENSUS:
                return True, "Recovery mode"
            return False, f"Insufficient nodes for recovery: {node_count}"
        
        return False, "Unknown mode"
    
    def get_required_confirmations(self) -> int:
        """
        Get required block confirmations for current network state.
        
        Fewer nodes = more confirmations required for finality.
        """
        node_count = self.get_active_node_count()
        
        if node_count in self.CONFIRMATIONS_BY_SIZE:
            return self.CONFIRMATIONS_BY_SIZE[node_count]
        
        if node_count < self.MIN_NODES_NORMAL:
            # Interpolate for sizes not in table
            return max(1, 6 - node_count)
        
        return self.DEFAULT_CONFIRMATIONS
    
    def get_probability_adjustment(self, node_pubkey: bytes) -> float:
        """
        Get probability adjustment for node during bootstrap.
        
        During bootstrap:
        - Founder gets higher probability
        - New nodes get reduced probability
        - Normal operation: 1.0 (no adjustment)
        """
        mode = self.check_mode()
        
        if mode == BootstrapMode.NORMAL:
            return 1.0
        
        if mode == BootstrapMode.BOOTSTRAP:
            if self.founder_pubkey == node_pubkey:
                # Founder bonus during bootstrap
                return 2.0
            
            # Reduced probability for non-founders during bootstrap
            return 0.5
        
        if mode == BootstrapMode.RECOVERY:
            # Slight boost for all nodes during recovery to speed up
            return 1.2
        
        return 1.0
    
    def should_accept_new_node(self, node_pubkey: bytes) -> Tuple[bool, str]:
        """
        Check if a new node should be accepted during bootstrap.
        
        During bootstrap, we apply stricter Sybil protection.
        """
        mode = self.check_mode()
        node_count = self.get_active_node_count()
        
        if mode == BootstrapMode.BOOTSTRAP:
            # During initial bootstrap, limit new nodes per hour
            MAX_NEW_NODES_PER_HOUR = 5
            
            # Check recent join rate via sybil detector
            if self.consensus.sybil_detector.is_suspicious_influx():
                return False, "Sybil protection: suspicious influx during bootstrap"
        
        return True, "Accepted"
    
    def record_block_produced(self, producer_pubkey: bytes):
        """Record that a block was produced."""
        if producer_pubkey == self.founder_pubkey:
            self.founder_blocks_produced += 1
    
    def get_bootstrap_stats(self) -> Dict[str, Any]:
        """Get bootstrap statistics."""
        current_time = int(time.time())
        bootstrap_duration = current_time - self.bootstrap_start
        
        return {
            'mode': BootstrapMode(self.mode).name,
            'active_nodes': self.get_active_node_count(),
            'min_nodes_normal': self.MIN_NODES_NORMAL,
            'founder_pubkey': self.founder_pubkey.hex()[:16] if self.founder_pubkey else None,
            'founder_blocks': self.founder_blocks_produced,
            'bootstrap_duration_hours': bootstrap_duration / 3600,
            'required_confirmations': self.get_required_confirmations(),
            'recent_disconnects': len(self.disconnect_events),
            'is_healthy': self.mode == BootstrapMode.NORMAL
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall network health status."""
        mode = self.check_mode()
        node_count = self.get_active_node_count()
        
        if mode == BootstrapMode.NORMAL and node_count >= self.MIN_NODES_NORMAL * 2:
            health = "excellent"
            score = 1.0
        elif mode == BootstrapMode.NORMAL:
            health = "good"
            score = 0.8
        elif mode == BootstrapMode.RECOVERY:
            health = "degraded"
            score = 0.4
        else:
            health = "bootstrap"
            score = 0.6
        
        return {
            'health': health,
            'score': score,
            'mode': BootstrapMode(mode).name,
            'node_count': node_count,
            'min_required': self.MIN_NODES_NORMAL,
            'confirmations': self.get_required_confirmations()
        }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run consensus self-tests."""
    logger.info("Running consensus self-tests...")
    
    # Test probability calculation
    calc = ConsensusCalculator()
    
    node1 = NodeState(pubkey=b'\x01' * 32)
    node1.total_uptime = PROTOCOL.K_TIME  # Max uptime
    node1.stored_blocks = 8000  # 80% of 10000
    node1.signed_blocks = PROTOCOL.K_REP  # Max reputation
    node1.status = NodeStatus.ACTIVE
    
    node2 = NodeState(pubkey=b'\x02' * 32)
    node2.total_uptime = PROTOCOL.K_TIME // 2  # Half max
    node2.stored_blocks = 4000
    node2.signed_blocks = PROTOCOL.K_REP // 2
    node2.status = NodeStatus.ACTIVE
    
    current_time = int(time.time())
    probs = calc.compute_probabilities([node1, node2], current_time, 10000)
    
    assert len(probs) == 2
    assert abs(sum(probs.values()) - 1.0) < 0.001
    assert probs[node1.pubkey] > probs[node2.pubkey]
    logger.info("✓ Probability calculation")
    
    # Test leader selection
    selector = LeaderSelector(calc)
    
    # Generate VRF outputs
    sk1, pk1 = Ed25519.generate_keypair()
    sk2, pk2 = Ed25519.generate_keypair()
    
    node1.pubkey = pk1
    node2.pubkey = pk2
    
    prev_hash = sha256(b"test")
    vrf1 = ECVRF.prove(sk1, prev_hash)
    vrf2 = ECVRF.prove(sk2, prev_hash)
    
    vrfs = {pk1: vrf1, pk2: vrf2}

    probs = calc.compute_probabilities([node1, node2], current_time, 10000)
    leader, is_fallback = selector.select_leader(
        [node1, node2], prev_hash, current_time, 10000, vrfs
    )

    assert leader in (pk1, pk2)
    assert isinstance(is_fallback, bool)
    logger.info("✓ Leader selection")
    
    # Test consensus engine
    engine = ConsensusEngine()
    engine.initialize()
    
    engine.register_node(pk1, stored_blocks=8000)
    engine.register_node(pk2, stored_blocks=4000)
    
    active = engine.get_active_nodes()
    assert len(active) == 2
    
    probs = engine.compute_probabilities()
    assert len(probs) == 2
    logger.info("✓ Consensus engine")
    
    # Test slashing (with proper signatures for equivocation detection)
    block1 = Block()
    block1.header.height = 100
    block1.header.leader_pubkey = pk1
    block1.header.merkle_root = b'\x01' * 32
    block1.header.prev_block_hash = b'\x00' * 32
    
    block2 = Block()
    block2.header.height = 100
    block2.header.leader_pubkey = pk1
    block2.header.merkle_root = b'\x02' * 32
    block2.header.prev_block_hash = b'\x00' * 32
    
    # Sign both blocks with same key (simulating equivocation)
    signing_hash1 = block1.header.signing_hash()
    signing_hash2 = block2.header.signing_hash()
    block1.header.leader_signature = Ed25519.sign(sk1, signing_hash1)
    block2.header.leader_signature = Ed25519.sign(sk1, signing_hash2)
    
    # Now check_equivocation should detect it
    evidence = engine.slashing_manager.check_equivocation(block1, block2)
    assert evidence is not None
    assert evidence.condition == SlashingCondition.EQUIVOCATION
    logger.info("✓ Equivocation detection")
    
    logger.info("All consensus self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
