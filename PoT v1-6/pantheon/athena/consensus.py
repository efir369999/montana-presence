"""
Proof of Time - Consensus Module (DAG Architecture)

Production-grade implementation of the Proof of Time consensus mechanism.

Includes:
- Node state management
- Probability calculations for DAG block eligibility
- Weight rebalancing

Note: In DAG architecture, there is no leader selection.
Any eligible node can produce blocks, ordered by PHANTOM + VDF.
Slashing is handled by HAL (pantheon.hal.slashing).
Sybil detection is handled by HAL behavioral analysis.

Time is the ultimate proof.
"""

import time
import struct
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum, auto

from pantheon.prometheus import Ed25519
from pantheon.themis import Block, create_genesis_block
from config import PROTOCOL, NodeConfig

# HAL integration
try:
    from pantheon.hal import HalEngine, SlashingManager
    HAL_AVAILABLE = True
except ImportError:
    HalEngine = None
    SlashingManager = None
    HAL_AVAILABLE = False

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
    first_seen: int = 0
    uptime_start: int = 0
    total_uptime: int = 0

    # Space component (f_space)
    stored_blocks: int = 0

    # Reputation component (f_rep)
    signed_blocks: int = 0
    last_signed_height: int = 0

    # Status
    status: NodeStatus = NodeStatus.OFFLINE
    quarantine_until: int = 0
    quarantine_reason: str = ""

    # Last seen
    last_seen: int = 0

    def get_uptime(self, current_time: int) -> int:
        """Get current uptime in seconds."""
        if self.status != NodeStatus.ACTIVE:
            return 0
        return min(
            self.total_uptime + (current_time - self.uptime_start),
            PROTOCOL.K_TIME
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
                return
            self.status = NodeStatus.ACTIVE
            self.quarantine_reason = ""

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
    Calculates node probabilities for DAG block eligibility.

    In DAG architecture, probability determines:
    - Weight of node's blocks in PHANTOM ordering
    - Eligibility to produce blocks (threshold check)

    Probability formula (per whitepaper):
    P_i = (w_time * f_time(t_i) + w_space * f_space(s_i) + w_rep * f_rep(r_i)) / Z

    Weights: w_time=0.60, w_space=0.20, w_rep=0.20
    """

    def __init__(
        self,
        weights: Optional[ProbabilityWeights] = None,
        hal: Optional['HalEngine'] = None
    ):
        self.weights = weights or ProbabilityWeights()
        self.weights.normalize()
        self.hal = hal

    def compute_f_time(self, uptime_seconds: int) -> float:
        """Compute time component (saturating at k_time = 180 days)."""
        if uptime_seconds <= 0:
            return 0.0
        return min(uptime_seconds / PROTOCOL.K_TIME, 1.0)

    def compute_f_space(self, stored_blocks: int, total_blocks: int) -> float:
        """Compute space component (saturating at k_space = 80% of chain)."""
        if total_blocks == 0:
            return 0.0
        storage_ratio = stored_blocks / total_blocks
        return min(storage_ratio / PROTOCOL.K_SPACE, 1.0)

    def compute_f_rep(
        self,
        signed_blocks: int,
        pubkey: Optional[bytes] = None
    ) -> float:
        """
        Compute reputation component (saturating at k_rep = 2016 blocks).

        With HAL integration, reputation is enhanced with multi-dimensional
        scoring including TIME, INTEGRITY, STORAGE, EPOCHS, and HANDSHAKE.
        """
        if signed_blocks <= 0:
            base_rep = 0.0
        else:
            base_rep = min(signed_blocks / PROTOCOL.K_REP, 1.0)

        if self.hal is not None and pubkey is not None and HAL_AVAILABLE:
            hal_score = self.hal.get_reputation_score(pubkey)
            return 0.3 * base_rep + 0.7 * hal_score

        return base_rep

    def compute_raw_probability(
        self,
        node: NodeState,
        current_time: int,
        total_blocks: int,
        is_probation: bool = False
    ) -> float:
        """Compute raw (unnormalized) probability for a node."""
        if node.status == NodeStatus.OFFLINE:
            return 0.0
        if node.status == NodeStatus.SLASHED:
            return 0.0

        uptime = node.get_uptime(current_time)
        f_time = self.compute_f_time(uptime)
        f_space = self.compute_f_space(node.stored_blocks, total_blocks)
        f_rep = self.compute_f_rep(node.signed_blocks, pubkey=node.pubkey)

        raw_prob = (
            self.weights.w_time * f_time +
            self.weights.w_space * f_space +
            self.weights.w_rep * f_rep
        )

        if node.status == NodeStatus.QUARANTINE:
            raw_prob *= 0.1

        if is_probation and uptime < (30 * 24 * 3600):
            raw_prob *= 0.1

        return raw_prob

    def compute_probabilities(
        self,
        nodes: List[NodeState],
        current_time: int,
        total_blocks: int,
        is_probation: bool = False
    ) -> Dict[bytes, float]:
        """Compute normalized probabilities for all nodes."""
        raw_probs = {}
        for node in nodes:
            if node.status in (NodeStatus.ACTIVE, NodeStatus.QUARANTINE):
                prob = self.compute_raw_probability(
                    node, current_time, total_blocks, is_probation
                )
                if prob > 0:
                    raw_probs[node.pubkey] = prob

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
        """Get detailed breakdown of probability components."""
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

        if self.hal is not None and HAL_AVAILABLE:
            profile = self.hal.get_profile(node.pubkey)
            if profile:
                result['hal'] = {
                    'aggregate_score': profile.aggregate_score,
                    'is_penalized': profile.is_penalized,
                    'trust_score': profile.get_trust_score(),
                }

        return result


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
        """Analyze component distributions across nodes."""
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
        """Rebalance weights based on current distribution."""
        dist = self.analyze_distribution(nodes, current_time, total_blocks)

        total = sum(dist.values())
        if total == 0:
            return self.current

        time_ratio = (self.current.w_time * dist["time"]) / total
        space_ratio = (self.current.w_space * dist["space"]) / total
        rep_ratio = (self.current.w_rep * dist["rep"]) / total

        threshold = 0.70

        if time_ratio > threshold:
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

        self.current.normalize()

        logger.debug(
            f"Weights rebalanced: time={self.current.w_time:.2f}, "
            f"space={self.current.w_space:.2f}, rep={self.current.w_rep:.2f}"
        )

        return self.current


# ============================================================================
# CONSENSUS ENGINE (DAG)
# ============================================================================

class ConsensusEngine:
    """
    Main consensus engine for Proof of Time (DAG architecture).

    Coordinates:
    - Node state management
    - Block eligibility (any node with weight >= 10% can produce)
    - Block validation
    - Weight rebalancing

    Note: In DAG, there is no leader selection.
    Slashing is handled by HAL (pantheon.hal.slashing).
    """

    # Minimum weight threshold to produce blocks (10% of max)
    MIN_WEIGHT_THRESHOLD = 0.10

    def __init__(self, config: Optional[NodeConfig] = None, hal: Optional['HalEngine'] = None):
        self.config = config or NodeConfig()
        self.hal = hal

        # Components
        self.weights = ProbabilityWeights()
        self.calculator = ConsensusCalculator(self.weights, hal=hal)
        self.rebalancer = WeightRebalancer(self.weights)

        # Slashing via HAL
        if HAL_AVAILABLE and SlashingManager is not None:
            self.slashing_manager = SlashingManager()
        else:
            self.slashing_manager = None

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

            logger.info(f"Node registered: {pubkey.hex()[:16]}...")

    def is_node_registered(self, pubkey: bytes) -> bool:
        """Check if a node is registered."""
        with self._lock:
            return pubkey in self.nodes

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

    def can_produce_block(self, pubkey: bytes) -> Tuple[bool, str]:
        """
        Check if a node can produce a block (DAG architecture).

        In DAG, any node with weight >= MIN_WEIGHT_THRESHOLD can produce.
        """
        with self._lock:
            if pubkey not in self.nodes:
                return False, "Unknown node"

            node = self.nodes[pubkey]
            if node.status == NodeStatus.OFFLINE:
                return False, "Node offline"
            if node.status == NodeStatus.SLASHED:
                return False, "Node slashed"

            probs = self.compute_probabilities()
            weight = probs.get(pubkey, 0.0)

            if weight < self.MIN_WEIGHT_THRESHOLD:
                return False, f"Weight {weight:.4f} < threshold {self.MIN_WEIGHT_THRESHOLD}"

            return True, f"Eligible (weight={weight:.4f})"

    def validate_block(self, block: Block, prev_block: Block) -> bool:
        """
        Validate block in DAG context.

        Checks:
        1. Producer is a known node
        2. Producer has sufficient weight
        3. Block signature is valid
        """
        producer = block.header.leader_pubkey

        if producer not in self.nodes:
            logger.warning(f"Unknown block producer: {producer.hex()[:16]}...")
            return False

        can_produce, reason = self.can_produce_block(producer)
        if not can_produce:
            logger.warning(f"Producer not eligible: {reason}")
            return False

        # Verify signature
        try:
            signing_hash = block.header.signing_hash()
            if not Ed25519.verify(producer, signing_hash, block.header.leader_signature):
                logger.warning("Invalid block signature")
                return False
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

        return True

    def process_block(self, block: Block) -> bool:
        """
        Process a new block.

        Updates chain state and node reputation.
        """
        with self._lock:
            self.chain_tip = block
            self.total_blocks = block.height + 1

            # Update producer reputation
            producer = block.header.leader_pubkey
            if producer in self.nodes:
                self.nodes[producer].record_signed_block(block.height)

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
        """Check and report equivocation via HAL slashing."""
        if self.slashing_manager is None:
            logger.warning("Slashing manager not available")
            return

        evidence = self.slashing_manager.check_equivocation(block1, block2)
        if evidence:
            self.slashing_manager.report_slash(evidence)

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
    NORMAL = 0
    BOOTSTRAP = 1
    RECOVERY = 2


class BootstrapManager:
    """
    Manages network bootstrapping with minimum 3 nodes.

    Strategy:
    - Allow block production with as few as 1 node (founder mode)
    - Require increasing confirmations as network grows
    - Track network health metrics
    """

    MIN_NODES_NORMAL = PROTOCOL.MIN_NODES
    MIN_NODES_CONSENSUS = 1

    CONFIRMATIONS_BY_SIZE = {
        1: 12,
        2: 6,
        3: 3,
    }
    DEFAULT_CONFIRMATIONS = 1

    def __init__(self, consensus_engine: ConsensusEngine):
        self.consensus = consensus_engine
        self.mode = BootstrapMode.BOOTSTRAP

        self.bootstrap_start: int = 0
        self.last_node_count: int = 0
        self.founder_pubkey: Optional[bytes] = None
        self.founder_blocks_produced: int = 0
        self.last_healthy_time: int = 0
        self.disconnect_events: List[Tuple[int, int]] = []

        self._lock = threading.Lock()

    def initialize(self, founder_pubkey: Optional[bytes] = None):
        """Initialize bootstrap manager."""
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
        """Check and update network mode."""
        node_count = self.get_active_node_count()
        current_time = int(time.time())

        with self._lock:
            if node_count < self.last_node_count:
                nodes_lost = self.last_node_count - node_count
                self.disconnect_events.append((current_time, nodes_lost))

                cutoff = current_time - 86400
                self.disconnect_events = [
                    (t, n) for t, n in self.disconnect_events if t > cutoff
                ]

            self.last_node_count = node_count

            if node_count >= self.MIN_NODES_NORMAL:
                if self.mode != BootstrapMode.NORMAL:
                    logger.info(f"Entering NORMAL mode with {node_count} nodes")
                self.mode = BootstrapMode.NORMAL
                self.last_healthy_time = current_time

            elif node_count < self.MIN_NODES_NORMAL:
                if self.last_healthy_time > self.bootstrap_start:
                    if self.mode != BootstrapMode.RECOVERY:
                        logger.warning(f"Entering RECOVERY mode: only {node_count} nodes active")
                    self.mode = BootstrapMode.RECOVERY
                else:
                    self.mode = BootstrapMode.BOOTSTRAP

        return self.mode

    def can_produce_block(self, node_pubkey: bytes) -> Tuple[bool, str]:
        """Check if a node can produce a block in current mode."""
        mode = self.check_mode()
        node_count = self.get_active_node_count()

        if mode == BootstrapMode.NORMAL:
            return True, "Normal operation"

        elif mode == BootstrapMode.BOOTSTRAP:
            if node_count == 0:
                return False, "No active nodes"

            if node_count == 1:
                if self.founder_pubkey and node_pubkey != self.founder_pubkey:
                    return False, "Only founder can produce during single-node bootstrap"
                return True, "Single-node bootstrap mode"

            return True, "Bootstrap mode with multiple nodes"

        elif mode == BootstrapMode.RECOVERY:
            if node_count >= self.MIN_NODES_CONSENSUS:
                return True, "Recovery mode"
            return False, f"Insufficient nodes for recovery: {node_count}"

        return False, "Unknown mode"

    def get_required_confirmations(self) -> int:
        """Get required block confirmations for current network state."""
        node_count = self.get_active_node_count()

        if node_count in self.CONFIRMATIONS_BY_SIZE:
            return self.CONFIRMATIONS_BY_SIZE[node_count]

        if node_count < self.MIN_NODES_NORMAL:
            return max(1, 6 - node_count)

        return self.DEFAULT_CONFIRMATIONS

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
    node1.total_uptime = PROTOCOL.K_TIME
    node1.stored_blocks = 8000
    node1.signed_blocks = PROTOCOL.K_REP
    node1.status = NodeStatus.ACTIVE

    node2 = NodeState(pubkey=b'\x02' * 32)
    node2.total_uptime = PROTOCOL.K_TIME // 2
    node2.stored_blocks = 4000
    node2.signed_blocks = PROTOCOL.K_REP // 2
    node2.status = NodeStatus.ACTIVE

    current_time = int(time.time())
    probs = calc.compute_probabilities([node1, node2], current_time, 10000)

    assert len(probs) == 2
    assert abs(sum(probs.values()) - 1.0) < 0.001
    assert probs[node1.pubkey] > probs[node2.pubkey]
    logger.info("  Probability calculation")

    # Test consensus engine
    engine = ConsensusEngine()
    engine.initialize()

    sk1, pk1 = Ed25519.generate_keypair()
    sk2, pk2 = Ed25519.generate_keypair()

    engine.register_node(pk1, stored_blocks=8000)
    engine.register_node(pk2, stored_blocks=4000)

    active = engine.get_active_nodes()
    assert len(active) == 2

    probs = engine.compute_probabilities()
    assert len(probs) == 2
    logger.info("  Consensus engine")

    # Test block eligibility (DAG)
    can_produce, reason = engine.can_produce_block(pk1)
    assert can_produce
    logger.info("  Block eligibility")

    # Test slashing via HAL
    if engine.slashing_manager:
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

        signing_hash1 = block1.header.signing_hash()
        signing_hash2 = block2.header.signing_hash()
        block1.header.leader_signature = Ed25519.sign(sk1, signing_hash1)
        block2.header.leader_signature = Ed25519.sign(sk1, signing_hash2)

        evidence = engine.slashing_manager.check_equivocation(block1, block2)
        assert evidence is not None
        logger.info("  Equivocation detection via HAL")

    logger.info("All consensus self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
