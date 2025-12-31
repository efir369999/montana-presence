"""
Behavioral Analysis for Sybil Detection

Part of the Hal Humanity System - detecting coordinated fake nodes
through behavioral patterns rather than just identity proofs.

Named after Hal Finney (1956-2014), who understood that Sybil attacks
are fundamentally about behavior, not just identity.

DETECTION LAYERS:
1. ClusterDetector - Pairwise correlation detection
2. GlobalByzantineTracker - Behavioral fingerprinting (defeats jitter)

These work alongside hardware/social/timelock proofs to provide
defense-in-depth against sophisticated Sybil attacks.
"""

import hashlib
import logging
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .reputation import HalProfile, ReputationDimension

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Correlation detection thresholds
CORRELATION_WINDOW_SECONDS = 86400  # 24 hours of action history
TIMING_VARIANCE_THRESHOLD = 100  # 100ms timing similarity threshold
MAX_CORRELATION_THRESHOLD = 0.7  # 70% action similarity = suspicious
CORRELATION_PENALTY_FACTOR = 0.5  # 50% reduction when highly correlated

# Cluster detection
MIN_NODES_FOR_CLUSTER_ANALYSIS = 10
MAX_CLUSTER_INFLUENCE = 0.33  # 33% max influence per cluster

# Byzantine detection
MAX_BYZANTINE_INFLUENCE = 0.33  # 33% cap on ALL suspected nodes
FINGERPRINT_SIMILARITY_THRESHOLD = 0.80  # 80% similarity for same operator
MIN_NODES_FOR_TRACKING = 10


# ============================================================================
# DATA STRUCTURES
# ============================================================================

def sha256(data: bytes) -> bytes:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data).digest()


@dataclass
class ActionRecord:
    """Record of a node's action for correlation analysis."""
    pubkey: bytes
    action_type: str  # "block", "vote", "tx_relay"
    timestamp: int    # Milliseconds
    block_height: int
    action_hash: bytes


@dataclass
class ClusterInfo:
    """Information about a detected cluster."""
    cluster_id: bytes
    members: Set[bytes]
    correlation_score: float       # How correlated the members are [0, 1]
    total_influence: float         # Sum of member reputation scores
    detected_at: int               # Unix timestamp
    evidence: List[str]            # Evidence of correlation

    def get_capped_influence(self) -> float:
        """Get influence after cluster cap is applied."""
        return min(self.total_influence, MAX_CLUSTER_INFLUENCE)


# ============================================================================
# CLUSTER DETECTOR
# ============================================================================

class ClusterDetector:
    """
    Detects clusters of potentially colluding nodes.

    SECURITY MODEL:
    The "Slow Takeover Attack" works by gradually accumulating TIME
    across multiple coordinated nodes. This detector identifies:

    1. BEHAVIORAL CORRELATION
       - Nodes that consistently act together
       - Block production at suspiciously similar times
       - Identical voting patterns

    2. NETWORK TOPOLOGY
       - Nodes that only connect to each other
       - Isolated subgraphs in the trust network

    3. TIMING ANALYSIS
       - Block production too synchronized
       - Predictable action patterns

    LIMITATIONS (HONEST DISCLOSURE):
    - Cannot detect sophisticated attacks with random delays (150ms+ jitter)
    - Cannot prove nodes are controlled by same entity
    - Geographic verification relies on IP which can be spoofed
    - This is probabilistic defense, not cryptographic proof

    NOTE: Use GlobalByzantineTracker for jitter-resistant detection.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._action_history: Dict[bytes, List[ActionRecord]] = defaultdict(list)
        self._clusters: Dict[bytes, ClusterInfo] = {}
        self._node_clusters: Dict[bytes, Set[bytes]] = defaultdict(set)
        self._correlation_cache: Dict[Tuple[bytes, bytes], float] = {}
        self._last_analysis: int = 0
        self._analysis_interval = 3600  # 1 hour

        logger.info("ClusterDetector initialized (Hal Behavioral Layer 1)")

    def record_action(
        self,
        pubkey: bytes,
        action_type: str,
        timestamp_ms: int,
        block_height: int,
        action_hash: bytes
    ):
        """Record a node action for correlation analysis."""
        with self._lock:
            record = ActionRecord(
                pubkey=pubkey,
                action_type=action_type,
                timestamp=timestamp_ms,
                block_height=block_height,
                action_hash=action_hash
            )
            self._action_history[pubkey].append(record)

            # Keep only last 24 hours
            cutoff = int(time.time() * 1000) - CORRELATION_WINDOW_SECONDS * 1000
            self._action_history[pubkey] = [
                r for r in self._action_history[pubkey]
                if r.timestamp > cutoff
            ]

    def compute_pairwise_correlation(
        self,
        pubkey_a: bytes,
        pubkey_b: bytes
    ) -> float:
        """
        Compute correlation coefficient between two nodes.

        Returns value in [0, 1] where:
        - 0 = completely independent (good)
        - 1 = perfectly correlated (suspicious)
        """
        with self._lock:
            cache_key = tuple(sorted([pubkey_a, pubkey_b]))
            if cache_key in self._correlation_cache:
                return self._correlation_cache[cache_key]

            actions_a = self._action_history.get(pubkey_a, [])
            actions_b = self._action_history.get(pubkey_b, [])

            if len(actions_a) < 5 or len(actions_b) < 5:
                return 0.0

            # 1. TIMING CORRELATION
            timing_matches = 0
            total_comparisons = 0

            for action_a in actions_a:
                for action_b in actions_b:
                    if action_a.action_type == action_b.action_type:
                        time_diff = abs(action_a.timestamp - action_b.timestamp)
                        if time_diff <= TIMING_VARIANCE_THRESHOLD:
                            timing_matches += 1
                        total_comparisons += 1

            timing_correlation = (
                timing_matches / total_comparisons if total_comparisons > 0 else 0
            )

            # 2. ACTION TYPE DISTRIBUTION
            def get_action_distribution(actions: List[ActionRecord]) -> Dict[str, float]:
                counts: Dict[str, int] = defaultdict(int)
                for action in actions:
                    counts[action.action_type] += 1
                total = len(actions)
                return {k: v / total for k, v in counts.items()}

            dist_a = get_action_distribution(actions_a)
            dist_b = get_action_distribution(actions_b)

            # Cosine similarity
            all_types = set(dist_a.keys()) | set(dist_b.keys())
            dot_product = sum(dist_a.get(t, 0) * dist_b.get(t, 0) for t in all_types)
            norm_a = math.sqrt(sum(v**2 for v in dist_a.values()))
            norm_b = math.sqrt(sum(v**2 for v in dist_b.values()))

            distribution_correlation = (
                dot_product / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0
            )

            # 3. BLOCK HEIGHT PATTERNS
            heights_a = set(a.block_height for a in actions_a)
            heights_b = set(a.block_height for a in actions_b)

            height_overlap = len(heights_a & heights_b)
            height_union = len(heights_a | heights_b)

            height_correlation = (
                height_overlap / height_union if height_union > 0 else 0
            )

            # Combined correlation (weighted)
            correlation = (
                0.5 * timing_correlation +
                0.3 * distribution_correlation +
                0.2 * height_correlation
            )

            self._correlation_cache[cache_key] = correlation
            return correlation

    def detect_clusters(
        self,
        profiles: Dict[bytes, Any],
        min_cluster_size: int = 2
    ) -> List[ClusterInfo]:
        """Detect clusters of correlated nodes."""
        with self._lock:
            if len(profiles) < MIN_NODES_FOR_CLUSTER_ANALYSIS:
                return []

            current_time = int(time.time())
            if current_time - self._last_analysis < self._analysis_interval:
                return list(self._clusters.values())

            self._last_analysis = current_time
            self._correlation_cache.clear()

            nodes = list(profiles.keys())
            n = len(nodes)

            # Find pairs with high correlation
            high_correlation_pairs: List[Tuple[bytes, bytes, float]] = []
            for i in range(n):
                for j in range(i + 1, n):
                    correlation = self.compute_pairwise_correlation(nodes[i], nodes[j])
                    if correlation >= MAX_CORRELATION_THRESHOLD:
                        high_correlation_pairs.append((nodes[i], nodes[j], correlation))

            # Union-find clustering
            parent: Dict[bytes, bytes] = {node: node for node in nodes}

            def find(x: bytes) -> bytes:
                if parent[x] != x:
                    parent[x] = find(parent[x])
                return parent[x]

            def union(x: bytes, y: bytes):
                px, py = find(x), find(y)
                if px != py:
                    parent[px] = py

            for node_a, node_b, _ in high_correlation_pairs:
                union(node_a, node_b)

            # Group nodes
            cluster_groups: Dict[bytes, Set[bytes]] = defaultdict(set)
            for node in nodes:
                root = find(node)
                cluster_groups[root].add(node)

            # Create ClusterInfo
            new_clusters: Dict[bytes, ClusterInfo] = {}
            for root, members in cluster_groups.items():
                if len(members) >= min_cluster_size:
                    correlations = []
                    member_list = list(members)
                    for i in range(len(member_list)):
                        for j in range(i + 1, len(member_list)):
                            corr = self.compute_pairwise_correlation(
                                member_list[i], member_list[j]
                            )
                            correlations.append(corr)

                    avg_correlation = (
                        sum(correlations) / len(correlations) if correlations else 0
                    )

                    total_influence = sum(
                        profiles[m].aggregate_score for m in members if m in profiles
                    )

                    cluster_id = sha256(b''.join(sorted(members)))

                    evidence = [
                        f"Members: {len(members)}",
                        f"Avg correlation: {avg_correlation:.2f}",
                        f"Total influence: {total_influence:.2f}",
                    ]

                    cluster_info = ClusterInfo(
                        cluster_id=cluster_id,
                        members=members,
                        correlation_score=avg_correlation,
                        total_influence=total_influence,
                        detected_at=current_time,
                        evidence=evidence
                    )

                    new_clusters[cluster_id] = cluster_info
                    for member in members:
                        self._node_clusters[member].add(cluster_id)

            self._clusters = new_clusters

            if new_clusters:
                logger.warning(
                    f"ClusterDetector: {len(new_clusters)} clusters, "
                    f"{sum(len(c.members) for c in new_clusters.values())} nodes"
                )

            return list(new_clusters.values())

    def get_node_cluster_penalty(self, pubkey: bytes) -> float:
        """Get penalty factor based on cluster membership."""
        with self._lock:
            cluster_ids = self._node_clusters.get(pubkey, set())
            if not cluster_ids:
                return 1.0

            max_correlation = 0.0
            for cluster_id in cluster_ids:
                if cluster_id in self._clusters:
                    cluster = self._clusters[cluster_id]
                    max_correlation = max(max_correlation, cluster.correlation_score)

            if max_correlation < MAX_CORRELATION_THRESHOLD:
                return 1.0

            penalty = 1.0 - (max_correlation - MAX_CORRELATION_THRESHOLD) * CORRELATION_PENALTY_FACTOR / (1.0 - MAX_CORRELATION_THRESHOLD)
            return max(CORRELATION_PENALTY_FACTOR, penalty)

    def apply_cluster_cap(
        self,
        probabilities: Dict[bytes, float]
    ) -> Dict[bytes, float]:
        """Apply global cap to cluster influence."""
        with self._lock:
            result = probabilities.copy()
            total_network = sum(probabilities.values())

            if total_network == 0:
                return result

            for cluster in self._clusters.values():
                cluster_total = sum(
                    probabilities.get(m, 0) for m in cluster.members
                )
                cluster_share = cluster_total / total_network

                if cluster_share > MAX_CLUSTER_INFLUENCE:
                    target_total = MAX_CLUSTER_INFLUENCE * total_network
                    reduction_factor = target_total / cluster_total

                    logger.warning(
                        f"Cluster cap: {len(cluster.members)} nodes "
                        f"{cluster_share*100:.1f}% -> {MAX_CLUSTER_INFLUENCE*100:.1f}%"
                    )

                    for member in cluster.members:
                        if member in result:
                            result[member] *= reduction_factor

            return result

    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get cluster detection statistics."""
        with self._lock:
            return {
                'total_clusters': len(self._clusters),
                'total_nodes': sum(len(c.members) for c in self._clusters.values()),
                'highest_correlation': max(
                    (c.correlation_score for c in self._clusters.values()),
                    default=0.0
                ),
            }


# ============================================================================
# GLOBAL BYZANTINE TRACKER
# ============================================================================

class GlobalByzantineTracker:
    """
    Tracks total suspected Byzantine influence via behavioral fingerprinting.

    PROBLEM SOLVED:
    - 100 nodes divided into 10 groups of 10
    - Each group behaves differently (correlation < 0.7)
    - ClusterDetector misses them (evasion via 150ms jitter)
    - Each group < 33%, but total = 50%+

    SOLUTION:
    Track nodes by BEHAVIORAL FINGERPRINT, not just pairwise correlation.
    Fingerprints capture patterns that jitter cannot hide:
    1. Join time proximity
    2. Reputation growth rate similarity
    3. Timing entropy (low = scripted)
    4. Dimension balance patterns

    Named after Hal Finney who understood Sybil detection fundamentally.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._fingerprints: Dict[bytes, Tuple[float, ...]] = {}
        self._byzantine_groups: Dict[int, Set[bytes]] = {}
        self._node_to_group: Dict[bytes, int] = {}
        self._last_analysis: int = 0
        self._analysis_interval = 1800  # 30 minutes

        logger.info("GlobalByzantineTracker initialized (Hal Behavioral Layer 2)")

    def compute_fingerprint(
        self,
        profile: Any,
        all_profiles: Dict[bytes, Any],
        ReputationDimension: Any
    ) -> Tuple[float, ...]:
        """Compute behavioral fingerprint for a node."""
        current_time = int(time.time())

        # Feature 1: Join time
        if all_profiles:
            min_created = min(p.created_at for p in all_profiles.values())
            max_created = max(p.created_at for p in all_profiles.values())
            time_range = max(1, max_created - min_created)
            join_time_norm = (profile.created_at - min_created) / time_range
        else:
            join_time_norm = 0.5

        # Feature 2: Reputation growth rate
        age_days = max(1, (current_time - profile.created_at) / 86400)
        growth_rate = profile.aggregate_score / age_days
        growth_rate_norm = min(1.0, growth_rate / 0.05)

        # Feature 3: TIME velocity
        time_score = profile.dimensions[ReputationDimension.TIME].value
        time_velocity = time_score / age_days
        time_velocity_norm = min(1.0, time_velocity / 0.01)

        # Feature 4: Event frequency
        events_per_day = profile.total_events / age_days
        event_freq_norm = min(1.0, events_per_day / 50)

        # Feature 5: Timing entropy
        recent_events = profile.get_recent_events(since=current_time - 86400)
        if len(recent_events) >= 2:
            timestamps = [e.timestamp for e in recent_events]
            deltas = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
            if deltas:
                mean_delta = sum(deltas) / len(deltas)
                variance = sum((d - mean_delta)**2 for d in deltas) / len(deltas)
                timing_entropy = min(1.0, math.sqrt(variance) / 100)
            else:
                timing_entropy = 0.5
        else:
            timing_entropy = 0.5

        # Feature 6: Dimension balance
        dim_values = [d.value for d in profile.dimensions.values()]
        if dim_values:
            mean_dim = sum(dim_values) / len(dim_values)
            dim_variance = sum((v - mean_dim)**2 for v in dim_values) / len(dim_values)
            dim_balance = min(1.0, math.sqrt(dim_variance) * 5)
        else:
            dim_balance = 0.5

        return (
            join_time_norm,
            growth_rate_norm,
            time_velocity_norm,
            event_freq_norm,
            timing_entropy,
            dim_balance,
        )

    def fingerprint_distance(self, fp1: Tuple[float, ...], fp2: Tuple[float, ...]) -> float:
        """Distance between fingerprints [0, 1]."""
        if len(fp1) != len(fp2):
            return 1.0
        sum_sq = sum((a - b)**2 for a, b in zip(fp1, fp2))
        return math.sqrt(sum_sq / len(fp1))

    def detect_byzantine_groups(
        self,
        profiles: Dict[bytes, Any]
    ) -> Dict[int, Set[bytes]]:
        """
        Detect groups of potentially Byzantine nodes.

        Attack signature:
        1. Created within SHORT time window (coordinated deployment)
        2. HIGH TIME scores (patient accumulation)
        3. Similar dimension profiles (automated management)
        """
        # Import at runtime to avoid circular imports
        from .reputation import ReputationDimension

        with self._lock:
            current_time = int(time.time())

            if len(profiles) < MIN_NODES_FOR_TRACKING:
                return {}

            if current_time - self._last_analysis < self._analysis_interval:
                return self._byzantine_groups

            self._last_analysis = current_time

            # Group by creation time (7 day window)
            CREATION_WINDOW = 7 * 24 * 3600
            sorted_profiles = sorted(profiles.items(), key=lambda x: x[1].created_at)

            time_clusters: List[Set[bytes]] = []
            current_cluster: Set[bytes] = set()
            cluster_start_time = 0

            for pk, profile in sorted_profiles:
                if not current_cluster:
                    current_cluster = {pk}
                    cluster_start_time = profile.created_at
                elif profile.created_at - cluster_start_time <= CREATION_WINDOW:
                    current_cluster.add(pk)
                else:
                    if len(current_cluster) >= 3:
                        time_clusters.append(current_cluster)
                    current_cluster = {pk}
                    cluster_start_time = profile.created_at

            if len(current_cluster) >= 3:
                time_clusters.append(current_cluster)

            # Filter by suspicious characteristics
            suspicious_groups: Dict[int, Set[bytes]] = {}
            group_id = 0

            for cluster in time_clusters:
                if len(cluster) < 3:
                    continue

                time_scores = [
                    profiles[pk].dimensions[ReputationDimension.TIME].value
                    for pk in cluster
                ]

                avg_time = sum(time_scores) / len(time_scores)
                time_variance = sum((t - avg_time)**2 for t in time_scores) / len(time_scores)

                # HIGH average TIME + LOW variance = suspicious
                is_high_time = avg_time > 0.6
                is_low_variance = time_variance < 0.05

                if is_high_time and is_low_variance:
                    # Check dimension similarity
                    dim_profiles = []
                    for pk in cluster:
                        p = profiles[pk]
                        dim_profiles.append([
                            p.dimensions[d].value
                            for d in ReputationDimension
                        ])

                    similarities = []
                    for i in range(len(dim_profiles)):
                        for j in range(i + 1, len(dim_profiles)):
                            dot = sum(a * b for a, b in zip(dim_profiles[i], dim_profiles[j]))
                            norm_i = math.sqrt(sum(a**2 for a in dim_profiles[i]))
                            norm_j = math.sqrt(sum(a**2 for a in dim_profiles[j]))
                            if norm_i > 0 and norm_j > 0:
                                similarities.append(dot / (norm_i * norm_j))

                    avg_similarity = sum(similarities) / len(similarities) if similarities else 0

                    if avg_similarity > FINGERPRINT_SIMILARITY_THRESHOLD:
                        suspicious_groups[group_id] = cluster
                        group_id += 1
                        logger.warning(
                            f"Byzantine group: {len(cluster)} nodes, "
                            f"time={avg_time:.2f}, var={time_variance:.4f}, "
                            f"similarity={avg_similarity:.2f}"
                        )

            self._byzantine_groups = suspicious_groups

            self._node_to_group.clear()
            for gid, members in self._byzantine_groups.items():
                for member in members:
                    self._node_to_group[member] = gid

            if self._byzantine_groups:
                total = sum(len(g) for g in self._byzantine_groups.values())
                logger.warning(
                    f"GlobalByzantineTracker: {len(self._byzantine_groups)} groups, "
                    f"{total} suspected nodes"
                )

            return self._byzantine_groups

    def apply_global_byzantine_cap(
        self,
        probabilities: Dict[bytes, float],
        profiles: Dict[bytes, Any]
    ) -> Dict[bytes, float]:
        """Apply global cap to suspected Byzantine nodes."""
        with self._lock:
            result = probabilities.copy()
            total_network = sum(probabilities.values())

            if total_network == 0:
                return result

            groups = self.detect_byzantine_groups(profiles)

            all_suspected = set()
            for members in groups.values():
                all_suspected.update(members)

            suspected_total = sum(probabilities.get(pk, 0) for pk in all_suspected)
            suspected_share = suspected_total / total_network if total_network > 0 else 0

            if suspected_share > MAX_BYZANTINE_INFLUENCE:
                target_total = MAX_BYZANTINE_INFLUENCE * total_network
                reduction_factor = target_total / suspected_total

                logger.warning(
                    f"BYZANTINE CAP: {len(all_suspected)} nodes "
                    f"{suspected_share*100:.1f}% -> {MAX_BYZANTINE_INFLUENCE*100:.1f}%"
                )

                for pk in all_suspected:
                    if pk in result:
                        result[pk] *= reduction_factor

            return result

    def get_byzantine_stats(self) -> Dict[str, Any]:
        """Get Byzantine detection statistics."""
        with self._lock:
            return {
                'groups': len(self._byzantine_groups),
                'suspected_nodes': sum(len(g) for g in self._byzantine_groups.values()),
                'fingerprints': len(self._fingerprints),
            }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run behavioral analysis self-tests."""
    logger.info("Running Hal Behavioral self-tests...")

    # Test ClusterDetector
    detector = ClusterDetector()

    node1 = b'\x01' * 32
    node2 = b'\x02' * 32
    node3 = b'\x03' * 32

    now = int(time.time() * 1000)

    # Record synchronized actions (should correlate)
    for i in range(10):
        detector.record_action(node1, "block", now + i * 1000, 100 + i, b'\x00' * 32)
        detector.record_action(node2, "block", now + i * 1000 + 50, 100 + i, b'\x00' * 32)

    # Record independent actions
    for i in range(10):
        detector.record_action(node3, "block", now + i * 5000, 100 + i * 2, b'\x00' * 32)

    corr_12 = detector.compute_pairwise_correlation(node1, node2)
    corr_13 = detector.compute_pairwise_correlation(node1, node3)

    logger.info(f"  Correlation node1-node2: {corr_12:.2f} (expected high)")
    logger.info(f"  Correlation node1-node3: {corr_13:.2f} (expected low)")

    assert corr_12 > corr_13, "Synchronized nodes should correlate more"
    logger.info("  PASS: Correlation detection working")

    # Test GlobalByzantineTracker
    tracker = GlobalByzantineTracker()
    stats = tracker.get_byzantine_stats()
    assert 'groups' in stats
    logger.info("  PASS: GlobalByzantineTracker initialized")

    logger.info("Hal Behavioral self-tests PASSED")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
