"""
Hal Social Graph Module

Tier 2 humanity verification using the Montana handshake system.

Instead of relying on external services (BrightID, Gitcoin Passport),
we build our own social graph from the Apostle handshake network.

Key insight: If you have mutual handshakes with multiple unrelated
parties who themselves have diverse connections, you're likely human.

Sybil cost: Building a believable social graph takes real time and
effort. A single attacker controlling multiple fake identities will
show telltale clustering patterns.

Detection mechanisms:
1. Graph clustering coefficient
2. Temporal correlation analysis
3. IP/behavior correlation (RHEUMA integration)
4. Cross-reference with hardware proofs
"""

from __future__ import annotations

import struct
import hashlib
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any
from datetime import datetime
from collections import defaultdict

from .humanity import (
    HumanityTier,
    HumanityProof,
    ProofStatus,
    SOCIAL_PROOF_VALIDITY,
)


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Social proof version
SOCIAL_VERSION = 1

# Minimum handshakes for social proof
MIN_HANDSHAKES_FOR_SOCIAL = 3

# Minimum unique connections (not in same cluster)
MIN_DIVERSE_CONNECTIONS = 2

# Maximum clustering coefficient for validity
MAX_CLUSTERING_COEFFICIENT = 0.8

# Time correlation threshold (seconds)
# Handshakes formed within this window are suspicious
CORRELATION_TIME_WINDOW = 3600  # 1 hour

# Maximum fraction of handshakes in correlation window
MAX_CORRELATED_FRACTION = 0.5

# Graph analysis depth
ANALYSIS_DEPTH = 2


# ==============================================================================
# ENUMS
# ==============================================================================

class SybilRisk(IntEnum):
    """Risk level for Sybil detection."""
    LOW = 0           # Diverse connections, no patterns
    MEDIUM = 1        # Some clustering, needs monitoring
    HIGH = 2          # Strong patterns, likely Sybil
    CRITICAL = 3      # Confirmed Sybil attack


class ConnectionStrength(IntEnum):
    """Strength of social connection."""
    WEAK = 1          # Recent handshake
    MODERATE = 2      # Established handshake
    STRONG = 3        # Long-term + activity


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SocialConnection:
    """
    A single social connection (handshake-based).
    """
    peer_pubkey: bytes           # The connected peer
    handshake_id: bytes          # Reference to Apostles handshake
    formed_at: int               # Timestamp when formed
    strength: ConnectionStrength = ConnectionStrength.WEAK
    last_activity: int = 0       # Last interaction timestamp
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_days(self) -> float:
        """Get age of connection in days."""
        now = int(datetime.utcnow().timestamp())
        return (now - self.formed_at) / 86400

    def serialize(self) -> bytes:
        """Serialize connection."""
        data = bytearray()
        data.extend(self.peer_pubkey)
        data.extend(self.handshake_id)
        data.extend(struct.pack('<Q', self.formed_at))
        data.append(self.strength)
        data.extend(struct.pack('<Q', self.last_activity))
        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'SocialConnection':
        """Deserialize connection."""
        peer_pubkey = data[0:32]
        handshake_id = data[32:64]
        formed_at = struct.unpack('<Q', data[64:72])[0]
        strength = ConnectionStrength(data[72])
        last_activity = struct.unpack('<Q', data[73:81])[0]
        return cls(
            peer_pubkey=peer_pubkey,
            handshake_id=handshake_id,
            formed_at=formed_at,
            strength=strength,
            last_activity=last_activity
        )


@dataclass
class SocialProof:
    """
    Proof of social connections for Tier 2 humanity.
    """
    pubkey: bytes                              # Owner of this proof
    connections: List[SocialConnection] = field(default_factory=list)
    graph_hash: bytes = b""                    # Merkle root of connection graph
    clustering_coefficient: float = 0.0        # Self-reported clustering
    created_at: int = field(default_factory=lambda: int(datetime.utcnow().timestamp()))
    signature: Optional[bytes] = None          # Self-attestation

    @property
    def connection_count(self) -> int:
        """Get number of connections."""
        return len(self.connections)

    @property
    def diverse_connections(self) -> int:
        """
        Estimate number of diverse (non-clustered) connections.

        This is a heuristic - true diversity requires graph analysis.
        """
        if not self.connections:
            return 0

        # Count connections formed at different times
        timestamps = sorted(c.formed_at for c in self.connections)
        diverse = 1
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i-1] > CORRELATION_TIME_WINDOW:
                diverse += 1

        return diverse

    def serialize(self) -> bytes:
        """Serialize social proof."""
        data = bytearray()

        # Version
        data.append(SOCIAL_VERSION)

        # Pubkey
        data.extend(self.pubkey)

        # Connections count + connections
        data.extend(struct.pack('<H', len(self.connections)))
        for conn in self.connections:
            conn_data = conn.serialize()
            data.extend(struct.pack('<H', len(conn_data)))
            data.extend(conn_data)

        # Graph hash
        data.extend(self.graph_hash if len(self.graph_hash) == 32 else b'\x00' * 32)

        # Clustering coefficient (fixed point, 2 decimal places)
        data.extend(struct.pack('<H', int(self.clustering_coefficient * 100)))

        # Created at
        data.extend(struct.pack('<Q', self.created_at))

        # Signature (optional)
        if self.signature:
            data.extend(struct.pack('<H', len(self.signature)))
            data.extend(self.signature)
        else:
            data.extend(struct.pack('<H', 0))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'SocialProof':
        """Deserialize social proof."""
        offset = 0

        # Version
        version = data[offset]
        offset += 1
        if version != SOCIAL_VERSION:
            raise ValueError(f"Unsupported social version: {version}")

        # Pubkey
        pubkey = data[offset:offset + 32]
        offset += 32

        # Connections
        conn_count = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        connections = []
        for _ in range(conn_count):
            conn_len = struct.unpack('<H', data[offset:offset + 2])[0]
            offset += 2
            conn_data = data[offset:offset + conn_len]
            offset += conn_len
            connections.append(SocialConnection.deserialize(conn_data))

        # Graph hash
        graph_hash = data[offset:offset + 32]
        offset += 32

        # Clustering coefficient
        cc_int = struct.unpack('<H', data[offset:offset + 2])[0]
        clustering_coefficient = cc_int / 100.0
        offset += 2

        # Created at
        created_at = struct.unpack('<Q', data[offset:offset + 8])[0]
        offset += 8

        # Signature
        sig_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        signature = data[offset:offset + sig_len] if sig_len > 0 else None

        return cls(
            pubkey=pubkey,
            connections=connections,
            graph_hash=graph_hash,
            clustering_coefficient=clustering_coefficient,
            created_at=created_at,
            signature=signature
        )


@dataclass
class SocialGraph:
    """
    Local view of the social graph for analysis.

    Maintained by each node to detect Sybil patterns.
    """
    # Adjacency list: pubkey -> set of connected pubkeys
    edges: Dict[bytes, Set[bytes]] = field(default_factory=lambda: defaultdict(set))
    # Node metadata
    node_info: Dict[bytes, Dict[str, Any]] = field(default_factory=dict)
    # Edge timestamps
    edge_times: Dict[Tuple[bytes, bytes], int] = field(default_factory=dict)

    def add_connection(
        self,
        pubkey_a: bytes,
        pubkey_b: bytes,
        timestamp: int
    ) -> None:
        """Add a bidirectional connection."""
        self.edges[pubkey_a].add(pubkey_b)
        self.edges[pubkey_b].add(pubkey_a)

        # Normalize edge key for timestamp
        edge_key = tuple(sorted([pubkey_a, pubkey_b]))
        self.edge_times[edge_key] = timestamp

    def get_neighbors(self, pubkey: bytes) -> Set[bytes]:
        """Get all neighbors of a node."""
        return self.edges.get(pubkey, set())

    def get_degree(self, pubkey: bytes) -> int:
        """Get degree (number of connections) of a node."""
        return len(self.edges.get(pubkey, set()))

    def compute_clustering_coefficient(self, pubkey: bytes) -> float:
        """
        Compute local clustering coefficient for a node.

        CC = (actual triangles) / (possible triangles)

        High CC means neighbors are connected to each other (clique-like).
        Low CC means diverse connections.
        """
        neighbors = list(self.get_neighbors(pubkey))
        n = len(neighbors)

        if n < 2:
            return 0.0

        # Count triangles (edges between neighbors)
        triangles = 0
        for i in range(n):
            for j in range(i + 1, n):
                if neighbors[j] in self.edges.get(neighbors[i], set()):
                    triangles += 1

        # Possible triangles = C(n, 2) = n(n-1)/2
        possible = n * (n - 1) / 2

        return triangles / possible if possible > 0 else 0.0

    def get_temporal_correlation(self, pubkey: bytes) -> float:
        """
        Compute temporal correlation of connections.

        Returns fraction of connections formed within correlation window.
        High value = suspicious (batch created).
        """
        neighbors = list(self.get_neighbors(pubkey))
        if len(neighbors) < 2:
            return 0.0

        timestamps = []
        for neighbor in neighbors:
            edge_key = tuple(sorted([pubkey, neighbor]))
            if edge_key in self.edge_times:
                timestamps.append(self.edge_times[edge_key])

        if len(timestamps) < 2:
            return 0.0

        timestamps.sort()
        correlated = 0
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i-1] <= CORRELATION_TIME_WINDOW:
                correlated += 1

        return correlated / (len(timestamps) - 1)

    def find_clusters(self) -> List[Set[bytes]]:
        """
        Find connected components (clusters) in the graph.

        Large isolated clusters may indicate Sybil groups.
        """
        visited: Set[bytes] = set()
        clusters: List[Set[bytes]] = []

        for node in self.edges:
            if node in visited:
                continue

            # BFS from this node
            cluster: Set[bytes] = set()
            queue = [node]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                cluster.add(current)

                for neighbor in self.edges.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if cluster:
                clusters.append(cluster)

        return clusters


# ==============================================================================
# SOCIAL VERIFIER
# ==============================================================================

class SocialVerifier:
    """
    Verifier for social proofs.

    Uses graph analysis to detect Sybil patterns.
    """

    def __init__(self):
        # Global social graph
        self.graph = SocialGraph()
        # Known Sybil clusters
        self._sybil_clusters: List[Set[bytes]] = []
        # Flagged pubkeys
        self._flagged: Set[bytes] = set()

    def add_handshake(
        self,
        pubkey_a: bytes,
        pubkey_b: bytes,
        timestamp: int
    ) -> None:
        """Register a new handshake in the social graph."""
        self.graph.add_connection(pubkey_a, pubkey_b, timestamp)

    def verify_social_proof(
        self,
        proof: SocialProof
    ) -> Tuple[bool, str, SybilRisk]:
        """
        Verify a social proof.

        Checks:
        1. Minimum connection count
        2. Diverse connections
        3. Clustering coefficient
        4. Temporal correlation
        5. Known Sybil patterns

        Returns: (is_valid, message, risk_level)
        """
        # Check minimum connections
        if proof.connection_count < MIN_HANDSHAKES_FOR_SOCIAL:
            return False, f"Need {MIN_HANDSHAKES_FOR_SOCIAL}+ connections, have {proof.connection_count}", SybilRisk.HIGH

        # Check diverse connections
        if proof.diverse_connections < MIN_DIVERSE_CONNECTIONS:
            return False, f"Need {MIN_DIVERSE_CONNECTIONS}+ diverse connections", SybilRisk.HIGH

        # Check clustering coefficient
        cc = self.graph.compute_clustering_coefficient(proof.pubkey)
        if cc > MAX_CLUSTERING_COEFFICIENT:
            return False, f"Clustering coefficient {cc:.2f} too high (max {MAX_CLUSTERING_COEFFICIENT})", SybilRisk.HIGH

        # Check temporal correlation
        tc = self.graph.get_temporal_correlation(proof.pubkey)
        if tc > MAX_CORRELATED_FRACTION:
            return False, f"Temporal correlation {tc:.2f} too high", SybilRisk.MEDIUM

        # Check against known Sybil clusters
        for sybil_cluster in self._sybil_clusters:
            if proof.pubkey in sybil_cluster:
                return False, "Pubkey in known Sybil cluster", SybilRisk.CRITICAL

        # Check if any connections are flagged
        flagged_count = 0
        for conn in proof.connections:
            if conn.peer_pubkey in self._flagged:
                flagged_count += 1

        if flagged_count > 0:
            risk = SybilRisk.MEDIUM if flagged_count == 1 else SybilRisk.HIGH
            return True, f"Warning: {flagged_count} flagged connections", risk

        return True, f"Social proof valid (CC={cc:.2f}, TC={tc:.2f})", SybilRisk.LOW

    def analyze_sybil_patterns(self, pubkey: bytes) -> Dict[str, Any]:
        """
        Deep analysis for Sybil detection.

        Returns analysis report.
        """
        report = {
            'pubkey': pubkey.hex(),
            'degree': self.graph.get_degree(pubkey),
            'clustering_coefficient': self.graph.compute_clustering_coefficient(pubkey),
            'temporal_correlation': self.graph.get_temporal_correlation(pubkey),
            'risk_factors': [],
            'risk_level': SybilRisk.LOW,
        }

        # Check clustering
        if report['clustering_coefficient'] > MAX_CLUSTERING_COEFFICIENT:
            report['risk_factors'].append('High clustering coefficient')

        # Check correlation
        if report['temporal_correlation'] > MAX_CORRELATED_FRACTION:
            report['risk_factors'].append('High temporal correlation')

        # Check if in isolated cluster
        clusters = self.graph.find_clusters()
        for cluster in clusters:
            if pubkey in cluster:
                cluster_size = len(cluster)
                if cluster_size > 2 and cluster_size < 20:
                    # Small isolated cluster is suspicious
                    avg_cc = sum(
                        self.graph.compute_clustering_coefficient(p)
                        for p in cluster
                    ) / cluster_size
                    if avg_cc > 0.7:
                        report['risk_factors'].append(f'In suspicious cluster (size={cluster_size}, avg_cc={avg_cc:.2f})')

        # Compute overall risk
        if len(report['risk_factors']) >= 3:
            report['risk_level'] = SybilRisk.CRITICAL
        elif len(report['risk_factors']) >= 2:
            report['risk_level'] = SybilRisk.HIGH
        elif len(report['risk_factors']) >= 1:
            report['risk_level'] = SybilRisk.MEDIUM

        return report

    def flag_sybil(self, pubkey: bytes, reason: str) -> None:
        """Flag a pubkey as suspected Sybil."""
        self._flagged.add(pubkey)

    def register_sybil_cluster(self, cluster: Set[bytes]) -> None:
        """Register a known Sybil cluster."""
        self._sybil_clusters.append(cluster)
        self._flagged.update(cluster)

    def get_stats(self) -> Dict[str, Any]:
        """Get verifier statistics."""
        return {
            'total_nodes': len(self.graph.edges),
            'total_edges': sum(len(e) for e in self.graph.edges.values()) // 2,
            'flagged_pubkeys': len(self._flagged),
            'sybil_clusters': len(self._sybil_clusters),
        }


# ==============================================================================
# HIGH-LEVEL API
# ==============================================================================

def create_social_proof(
    pubkey: bytes,
    connections: List[SocialConnection]
) -> SocialProof:
    """
    Create a SocialProof from handshake connections.

    Args:
        pubkey: Owner's pubkey
        connections: List of social connections (from handshakes)

    Returns: SocialProof ready for verification
    """
    # Compute graph hash (Merkle root of connections)
    conn_hashes = [
        hashlib.sha3_256(c.serialize()).digest()
        for c in connections
    ]

    # Simple Merkle root (production would use proper tree)
    if conn_hashes:
        combined = b''.join(sorted(conn_hashes))
        graph_hash = hashlib.sha3_256(combined).digest()
    else:
        graph_hash = b'\x00' * 32

    return SocialProof(
        pubkey=pubkey,
        connections=connections,
        graph_hash=graph_hash,
    )


def verify_social_proof(
    proof: SocialProof,
    verifier: SocialVerifier
) -> Tuple[bool, str]:
    """
    Verify a social proof.

    Args:
        proof: SocialProof to verify
        verifier: SocialVerifier instance

    Returns: (is_valid, message)
    """
    is_valid, msg, risk = verifier.verify_social_proof(proof)
    if risk >= SybilRisk.HIGH and is_valid:
        # Downgrade to invalid if high risk
        return False, f"High Sybil risk: {msg}"
    return is_valid, msg


def analyze_sybil_patterns(
    pubkey: bytes,
    verifier: SocialVerifier
) -> Dict[str, Any]:
    """
    Analyze a pubkey for Sybil patterns.

    Args:
        pubkey: Pubkey to analyze
        verifier: SocialVerifier with graph data

    Returns: Analysis report
    """
    return verifier.analyze_sybil_patterns(pubkey)


def create_humanity_proof_from_social(
    proof: SocialProof
) -> HumanityProof:
    """
    Convert SocialProof to HumanityProof.
    """
    now = int(datetime.utcnow().timestamp())

    return HumanityProof(
        tier=HumanityTier.SOCIAL,
        proof_type="social_graph",
        proof_data=proof.serialize(),
        pubkey=proof.pubkey,
        created_at=now,
        expires_at=now + SOCIAL_PROOF_VALIDITY,
        status=ProofStatus.VALID,
        metadata={
            'connection_count': proof.connection_count,
            'clustering_coefficient': proof.clustering_coefficient,
        }
    )


# ==============================================================================
# SELF-TEST
# ==============================================================================

def _self_test():
    """Run self-test for social module."""
    import os

    print("=" * 60)
    print("HAL SOCIAL MODULE - SELF TEST")
    print("=" * 60)

    # Create test pubkeys
    alice = os.urandom(32)
    bob = os.urandom(32)
    carol = os.urandom(32)
    dave = os.urandom(32)
    eve = os.urandom(32)

    # Test 1: SocialConnection
    print("\n[1] Testing SocialConnection...")
    conn = SocialConnection(
        peer_pubkey=bob,
        handshake_id=os.urandom(32),
        formed_at=int(datetime.utcnow().timestamp()) - 86400,  # 1 day ago
        strength=ConnectionStrength.MODERATE,
    )
    serialized = conn.serialize()
    deserialized = SocialConnection.deserialize(serialized)
    assert deserialized.peer_pubkey == bob
    assert deserialized.strength == ConnectionStrength.MODERATE
    print(f"    PASS: SocialConnection serialization ({len(serialized)} bytes)")

    # Test 2: SocialProof
    print("\n[2] Testing SocialProof...")
    connections = [
        SocialConnection(
            peer_pubkey=bob,
            handshake_id=os.urandom(32),
            formed_at=int(datetime.utcnow().timestamp()) - 86400 * 30,
        ),
        SocialConnection(
            peer_pubkey=carol,
            handshake_id=os.urandom(32),
            formed_at=int(datetime.utcnow().timestamp()) - 86400 * 20,
        ),
        SocialConnection(
            peer_pubkey=dave,
            handshake_id=os.urandom(32),
            formed_at=int(datetime.utcnow().timestamp()) - 86400 * 10,
        ),
    ]

    proof = create_social_proof(alice, connections)
    assert proof.connection_count == 3
    assert proof.diverse_connections >= 2  # Different times

    serialized = proof.serialize()
    deserialized = SocialProof.deserialize(serialized)
    assert deserialized.pubkey == alice
    assert len(deserialized.connections) == 3
    print(f"    PASS: SocialProof serialization ({len(serialized)} bytes)")

    # Test 3: SocialGraph
    print("\n[3] Testing SocialGraph...")
    graph = SocialGraph()

    # Add connections forming a triangle (alice-bob-carol-alice)
    now = int(datetime.utcnow().timestamp())
    graph.add_connection(alice, bob, now - 86400 * 30)
    graph.add_connection(bob, carol, now - 86400 * 20)
    graph.add_connection(alice, carol, now - 86400 * 10)

    # Check degree
    assert graph.get_degree(alice) == 2
    assert graph.get_degree(bob) == 2

    # Check clustering coefficient (should be 1.0 for triangle)
    cc = graph.compute_clustering_coefficient(alice)
    assert cc == 1.0, f"Expected 1.0, got {cc}"
    print(f"    PASS: SocialGraph clustering (CC={cc})")

    # Test 4: Add diverse connections
    print("\n[4] Testing diverse connections...")
    # Add dave and eve (not connected to each other)
    graph.add_connection(alice, dave, now - 86400 * 5)
    graph.add_connection(alice, eve, now - 86400 * 1)

    # Clustering should decrease
    cc = graph.compute_clustering_coefficient(alice)
    assert cc < 1.0, f"CC should be < 1.0 with diverse connections, got {cc}"
    print(f"    PASS: Diverse connections reduce clustering (CC={cc:.2f})")

    # Test 5: SocialVerifier
    print("\n[5] Testing SocialVerifier...")
    verifier = SocialVerifier()

    # Add connections to verifier's graph
    verifier.add_handshake(alice, bob, now - 86400 * 30)
    verifier.add_handshake(bob, carol, now - 86400 * 20)
    verifier.add_handshake(alice, carol, now - 86400 * 10)
    verifier.add_handshake(alice, dave, now - 86400 * 5)

    # Verify proof
    is_valid, msg, risk = verifier.verify_social_proof(proof)
    assert is_valid, f"Verification failed: {msg}"
    print(f"    PASS: Social proof verified (risk={risk.name})")

    # Test 6: Temporal correlation detection
    print("\n[6] Testing temporal correlation detection...")
    # Create proof with correlated timestamps (suspicious)
    batch_time = int(datetime.utcnow().timestamp())
    correlated_connections = [
        SocialConnection(
            peer_pubkey=os.urandom(32),
            handshake_id=os.urandom(32),
            formed_at=batch_time,
        ),
        SocialConnection(
            peer_pubkey=os.urandom(32),
            handshake_id=os.urandom(32),
            formed_at=batch_time + 60,  # 1 minute later
        ),
        SocialConnection(
            peer_pubkey=os.urandom(32),
            handshake_id=os.urandom(32),
            formed_at=batch_time + 120,  # 2 minutes later
        ),
    ]

    correlated_proof = create_social_proof(os.urandom(32), correlated_connections)
    assert correlated_proof.diverse_connections < MIN_DIVERSE_CONNECTIONS
    print("    PASS: Temporal correlation detected")

    # Test 7: Sybil analysis
    print("\n[7] Testing Sybil analysis...")
    report = verifier.analyze_sybil_patterns(alice)
    assert 'clustering_coefficient' in report
    assert 'risk_level' in report
    print(f"    PASS: Sybil analysis (risk={SybilRisk(report['risk_level']).name})")

    # Test 8: HumanityProof conversion
    print("\n[8] Testing HumanityProof conversion...")
    humanity_proof = create_humanity_proof_from_social(proof)
    assert humanity_proof.tier == HumanityTier.SOCIAL
    assert humanity_proof.proof_type == "social_graph"
    assert humanity_proof.pubkey == alice
    print(f"    PASS: HumanityProof created (type={humanity_proof.proof_type})")

    # Test 9: Cluster detection
    print("\n[9] Testing cluster detection...")
    clusters = graph.find_clusters()
    assert len(clusters) >= 1
    print(f"    PASS: Found {len(clusters)} clusters")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
