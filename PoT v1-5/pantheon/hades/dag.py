"""
Proof of Time - DAG Architecture
Directed Acyclic Graph block structure for horizontal scalability.

Based on: ProofOfTime_DAG_Addendum.pdf

Features:
- Multiple parent references (1-8 parents per block)
- PHANTOM-PoT ordering algorithm
- VDF-weighted block ordering
- Concurrent block production
- Linear TPS scaling with network size

Time is the ultimate proof.
"""

import struct
import time
import logging
import threading
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import IntEnum
from collections import defaultdict

import os
from pantheon.prometheus import sha256, sha256d, Ed25519, WesolowskiVDF, VDFProof, ECVRF
from config import PROTOCOL
from pantheon.nyx import TierValidator

logger = logging.getLogger("proof_of_time.dag")


# ============================================================================
# CONSTANTS
# ============================================================================

# DAG Parameters (from spec)
MAX_PARENTS = 8
MIN_PARENTS = 1
PHANTOM_K = 8  # Anticone threshold for blue set
MIN_WEIGHT_THRESHOLD = 0.1  # 10% of maximum possible weight
PARENT_DIVERSITY_MIN = 3  # Minimum unique parent producers
DIVERSITY_PENALTY = 0.5  # Weight penalty for insufficient diversity

# Timing
TIMESTAMP_TOLERANCE = 30  # ±30 seconds from VDF expectation

# Safety gate: disable block production by default unless explicitly allowed.
UNSAFE_ALLOWED = os.getenv("POT_ALLOW_UNSAFE") == "1"

# Economic / anti-spam limits
MAX_TX_PER_BLOCK = 2000
# Minimal fee rate in seconds per KiB (fallback if mempool config not available)
MIN_FEE_RATE_PER_KIB = 1

# Finality thresholds (explicit state machine)
FINALITY_CONFIRMATIONS_TENTATIVE = 3   # 3 blue descendants = TENTATIVE
FINALITY_CONFIRMATIONS_CONFIRMED = 6   # 6 blue descendants = CONFIRMED
FINALITY_SCORE_FINALIZED = 0.95        # 95% score = FINALIZED
FINALITY_SCORE_IRREVERSIBLE = 0.99     # 99% score = IRREVERSIBLE
MAX_REORG_DEPTH = 100                  # Never reorg beyond 100 blocks


# ============================================================================
# BLOCK FINALITY STATE MACHINE
# ============================================================================

class BlockFinalityState(IntEnum):
    """
    Explicit block finality state machine.

    State transitions are one-way (increasing finality only):

    PENDING → TENTATIVE → CONFIRMED → FINALIZED → IRREVERSIBLE

    States:
    - PENDING: Block just received, no confirmations
    - TENTATIVE: 3+ blue block descendants (soft confirmation)
    - CONFIRMED: 6+ blue block descendants (safe for most use cases)
    - FINALIZED: Finality score ≥ 0.95 (practically safe for high-value)
    - IRREVERSIBLE: Finality score ≥ 0.99 + VDF checkpoint (absolute)

    Reorg protection:
    - Blocks in CONFIRMED+ state can only be reorged with competing chain
      that has higher VDF weight AND was not previously seen
    - Blocks in IRREVERSIBLE state CANNOT be reorged under any circumstances
    """
    PENDING = 0
    TENTATIVE = 1
    CONFIRMED = 2
    FINALIZED = 3
    IRREVERSIBLE = 4


# ============================================================================
# DAG BLOCK HEADER
# ============================================================================

@dataclass
class DAGBlockHeader:
    """
    DAG Block Header with multiple parent references.
    
    Unlike linear chain where each block has single parent,
    DAG blocks reference 1-8 parent blocks for concurrent production.
    """
    # Protocol version
    version: int = PROTOCOL.PROTOCOL_VERSION
    
    # Parent references (1-8 parent block hashes)
    parents: List[bytes] = field(default_factory=list)
    
    # Merkle root of transactions
    merkle_root: bytes = b'\x00' * 32
    
    # Timestamp (soft constraint: ±30s from VDF expectation)
    timestamp: int = 0
    
    # VDF proof components
    vdf_input: bytes = b'\x00' * 32
    vdf_output: bytes = b''
    vdf_proof: bytes = b''
    vdf_iterations: int = 0
    vdf_weight: int = 0  # Accumulated VDF difficulty from genesis
    
    # VRF proof (leader selection)
    vrf_output: bytes = b''
    vrf_proof: bytes = b''
    
    # Producer identity
    producer_pubkey: bytes = b'\x00' * 32
    producer_signature: bytes = b'\x00' * 64
    
    # Node weight at time of production
    node_weight: float = 0.0
    
    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)
    
    def serialize(self) -> bytes:
        """Serialize DAG header."""
        data = bytearray()
        
        # Version
        data.extend(struct.pack('<I', self.version))
        
        # Parents (variable count)
        data.extend(struct.pack('<B', len(self.parents)))
        for parent in self.parents:
            data.extend(parent)
        
        # Merkle root
        data.extend(self.merkle_root)
        
        # Timestamp
        data.extend(struct.pack('<Q', self.timestamp))
        
        # VDF components
        data.extend(self.vdf_input)
        data.extend(struct.pack('<I', len(self.vdf_output)))
        data.extend(self.vdf_output)
        data.extend(struct.pack('<I', len(self.vdf_proof)))
        data.extend(self.vdf_proof)
        data.extend(struct.pack('<Q', self.vdf_iterations))
        data.extend(struct.pack('<Q', self.vdf_weight))
        
        # VRF components
        data.extend(struct.pack('<I', len(self.vrf_output)))
        data.extend(self.vrf_output)
        data.extend(struct.pack('<I', len(self.vrf_proof)))
        data.extend(self.vrf_proof)
        
        # Producer
        data.extend(self.producer_pubkey)
        data.extend(self.producer_signature)
        data.extend(struct.pack('<d', self.node_weight))
        
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['DAGBlockHeader', int]:
        """Deserialize DAG header."""
        # Version
        version = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        # Parents
        num_parents = data[offset]
        offset += 1
        if num_parents > MAX_PARENTS:
            raise ValueError(f"Too many parents: {num_parents}")
        
        parents = []
        for _ in range(num_parents):
            parents.append(data[offset:offset + 32])
            offset += 32
        
        # Merkle root
        merkle_root = data[offset:offset + 32]
        offset += 32
        
        # Timestamp
        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        # VDF components
        vdf_input = data[offset:offset + 32]
        offset += 32
        
        vdf_output_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        vdf_output = data[offset:offset + vdf_output_len]
        offset += vdf_output_len
        
        vdf_proof_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        vdf_proof = data[offset:offset + vdf_proof_len]
        offset += vdf_proof_len
        
        vdf_iterations = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        vdf_weight = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        # VRF components
        vrf_output_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        vrf_output = data[offset:offset + vrf_output_len]
        offset += vrf_output_len
        
        vrf_proof_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        vrf_proof = data[offset:offset + vrf_proof_len]
        offset += vrf_proof_len
        
        # Producer
        producer_pubkey = data[offset:offset + 32]
        offset += 32
        producer_signature = data[offset:offset + 64]
        offset += 64
        node_weight = struct.unpack_from('<d', data, offset)[0]
        offset += 8
        
        return cls(
            version=version,
            parents=parents,
            merkle_root=merkle_root,
            timestamp=timestamp,
            vdf_input=vdf_input,
            vdf_output=vdf_output,
            vdf_proof=vdf_proof,
            vdf_iterations=vdf_iterations,
            vdf_weight=vdf_weight,
            vrf_output=vrf_output,
            vrf_proof=vrf_proof,
            producer_pubkey=producer_pubkey,
            producer_signature=producer_signature,
            node_weight=node_weight
        ), offset
    
    def hash(self) -> bytes:
        """Compute block hash."""
        if self._hash is None:
            # Hash all fields except signature
            data = bytearray()
            data.extend(struct.pack('<I', self.version))
            data.extend(struct.pack('<B', len(self.parents)))
            for parent in self.parents:
                data.extend(parent)
            data.extend(self.merkle_root)
            data.extend(struct.pack('<Q', self.timestamp))
            data.extend(self.vdf_input)
            data.extend(self.vdf_output)
            data.extend(self.vdf_proof)
            data.extend(struct.pack('<Q', self.vdf_iterations))
            data.extend(struct.pack('<Q', self.vdf_weight))
            data.extend(self.vrf_output)
            data.extend(self.vrf_proof)
            data.extend(self.producer_pubkey)
            data.extend(struct.pack('<d', self.node_weight))
            
            self._hash = sha256d(bytes(data))
        return self._hash
    
    def signing_hash(self) -> bytes:
        """Hash for signing (excludes signature)."""
        return self.hash()
    
    def validate_parents(self) -> bool:
        """Validate parent references."""
        if len(self.parents) < MIN_PARENTS:
            return False
        if len(self.parents) > MAX_PARENTS:
            return False
        # Check for duplicate parents
        if len(set(self.parents)) != len(self.parents):
            return False
        return True


# ============================================================================
# DAG BLOCK
# ============================================================================

@dataclass
class DAGBlock:
    """
    Complete DAG block with header and transactions.
    """
    header: DAGBlockHeader = field(default_factory=DAGBlockHeader)
    transactions: List = field(default_factory=list)  # List[Transaction]
    
    # DAG metadata (computed, not serialized)
    _is_blue: Optional[bool] = field(default=None, repr=False)
    _blue_score: int = field(default=0, repr=False)
    
    def serialize(self) -> bytes:
        """Serialize DAG block."""
        from pantheon.themis.structures import write_varint, write_bytes
        
        data = bytearray()
        
        # Header
        header_bytes = self.header.serialize()
        data.extend(write_bytes(header_bytes))
        
        # Transactions
        data.extend(write_varint(len(self.transactions)))
        for tx in self.transactions:
            data.extend(write_bytes(tx.serialize()))
        
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['DAGBlock', int]:
        """Deserialize DAG block."""
        from pantheon.themis.structures import read_varint, read_bytes, Transaction
        
        # Header
        header_bytes, offset = read_bytes(data, offset)
        header, _ = DAGBlockHeader.deserialize(header_bytes)
        
        # Transactions
        num_txs, offset = read_varint(data, offset)
        transactions = []
        for _ in range(num_txs):
            tx_bytes, offset = read_bytes(data, offset)
            tx, _ = Transaction.deserialize(tx_bytes)
            transactions.append(tx)
        
        return cls(header=header, transactions=transactions), offset
    
    @property
    def block_hash(self) -> bytes:
        """Block hash."""
        return self.header.hash()
    
    @property
    def parents(self) -> List[bytes]:
        """Parent block hashes."""
        return self.header.parents
    
    @property
    def vdf_weight(self) -> int:
        """Accumulated VDF weight."""
        return self.header.vdf_weight
    
    @property
    def producer(self) -> bytes:
        """Producer public key."""
        return self.header.producer_pubkey


# ============================================================================
# PHANTOM-PoT ORDERING
# ============================================================================

class PHANTOMOrdering:
    """
    PHANTOM protocol adapted for Proof of Time.
    
    Replaces proof-of-work with VDF weight for block ordering.
    Identifies "blue set" of well-connected honest blocks.
    
    Algorithm:
    1. For each block B, compute anticone(B) = blocks neither ancestor nor descendant
    2. Block B is "blue" if |anticone(B) ∩ blue_set| ≤ k
    3. Order blue blocks by cumulative_vdf_weight descending
    4. Insert red blocks between blue ancestors and descendants
    """
    
    def __init__(self, k: int = PHANTOM_K):
        self.k = k

        # DAG structure
        self.blocks: Dict[bytes, DAGBlock] = {}  # hash -> block
        self.children: Dict[bytes, Set[bytes]] = defaultdict(set)  # hash -> child hashes
        self.tips: Set[bytes] = set()  # Current DAG tips (blocks with no children)

        # Blue set
        self.blue_set: Set[bytes] = set()
        self.blue_scores: Dict[bytes, int] = {}  # hash -> blue score

        # Ordering cache
        self._ordered_blocks: Optional[List[bytes]] = None
        self._order_dirty: bool = True

        # Finality state machine tracking
        self.finality_states: Dict[bytes, BlockFinalityState] = {}
        self.irreversible_blocks: Set[bytes] = set()  # Cannot be reorged ever

        # Orphan block pool (blocks with unknown parents)
        self.orphans: Dict[bytes, DAGBlock] = {}  # hash -> block
        self.orphan_by_parent: Dict[bytes, Set[bytes]] = defaultdict(set)  # parent -> orphan hashes

        self._lock = threading.RLock()
    
    def add_block(self, block: DAGBlock) -> bool:
        """
        Add block to DAG.

        Returns True if block was added, False if already exists or invalid.
        Blocks with unknown parents are added to orphan pool for later processing.
        """
        with self._lock:
            block_hash = block.block_hash

            if block_hash in self.blocks:
                return False

            # Check if all parents exist
            missing_parents = []
            for parent in block.parents:
                if parent != b'\x00' * 32 and parent not in self.blocks:
                    missing_parents.append(parent)

            # If missing parents, add to orphan pool
            if missing_parents:
                self.orphans[block_hash] = block
                for parent in missing_parents:
                    self.orphan_by_parent[parent].add(block_hash)
                logger.debug(f"Block {block_hash.hex()[:16]} added to orphan pool, waiting for {len(missing_parents)} parents")
                return False

            # Add to DAG
            self.blocks[block_hash] = block

            # Set initial finality state
            self.finality_states[block_hash] = BlockFinalityState.PENDING

            # Update children relationships
            for parent in block.parents:
                if parent in self.tips:
                    self.tips.remove(parent)
                self.children[parent].add(block_hash)

            # New block is a tip
            self.tips.add(block_hash)

            # Update blue set
            self._update_blue_set(block_hash)

            # Update finality states for affected blocks
            self._update_finality_states(block_hash)

            # Check if any orphans can now be processed
            self._process_orphans(block_hash)

            # Invalidate ordering cache
            self._order_dirty = True

            return True

    def _process_orphans(self, new_block_hash: bytes) -> int:
        """
        Process orphans that were waiting for this block.

        Returns number of orphans that were successfully added.
        """
        added = 0
        waiting = self.orphan_by_parent.pop(new_block_hash, set())

        for orphan_hash in waiting:
            if orphan_hash not in self.orphans:
                continue

            orphan = self.orphans.pop(orphan_hash)

            # Clean up other parent references
            for parent in orphan.parents:
                if parent in self.orphan_by_parent:
                    self.orphan_by_parent[parent].discard(orphan_hash)

            # Try to add again (recursively)
            if self.add_block(orphan):
                added += 1
                logger.debug(f"Orphan {orphan_hash.hex()[:16]} resolved and added to DAG")

        return added

    def _update_finality_states(self, new_block_hash: bytes) -> None:
        """
        Update finality states for all affected blocks after a new block is added.

        State transitions:
        - PENDING → TENTATIVE: 3+ blue descendants
        - TENTATIVE → CONFIRMED: 6+ blue descendants
        - CONFIRMED → FINALIZED: finality score ≥ 0.95
        - FINALIZED → IRREVERSIBLE: finality score ≥ 0.99
        """
        # Get all ancestors that might be affected
        ancestors = self._get_ancestors(new_block_hash)

        for block_hash in ancestors:
            if block_hash not in self.finality_states:
                self.finality_states[block_hash] = BlockFinalityState.PENDING

            current_state = self.finality_states[block_hash]

            # Already at maximum finality
            if current_state == BlockFinalityState.IRREVERSIBLE:
                continue

            # Count blue descendants
            descendants = self._get_descendants(block_hash)
            blue_descendants = len(descendants & self.blue_set)

            # Get finality score
            score = self.get_finality_score(block_hash)

            # Determine new state (only increases allowed)
            new_state = current_state

            if score >= FINALITY_SCORE_IRREVERSIBLE:
                new_state = BlockFinalityState.IRREVERSIBLE
                self.irreversible_blocks.add(block_hash)
            elif score >= FINALITY_SCORE_FINALIZED:
                new_state = max(new_state, BlockFinalityState.FINALIZED)
            elif blue_descendants >= FINALITY_CONFIRMATIONS_CONFIRMED:
                new_state = max(new_state, BlockFinalityState.CONFIRMED)
            elif blue_descendants >= FINALITY_CONFIRMATIONS_TENTATIVE:
                new_state = max(new_state, BlockFinalityState.TENTATIVE)

            if new_state != current_state:
                self.finality_states[block_hash] = new_state
                logger.debug(f"Block {block_hash.hex()[:16]} finality: {current_state.name} → {new_state.name}")

    def get_finality_state(self, block_hash: bytes) -> BlockFinalityState:
        """Get the finality state of a block."""
        return self.finality_states.get(block_hash, BlockFinalityState.PENDING)

    def can_reorg(self, block_hash: bytes) -> bool:
        """
        Check if a block can be reorganized (removed from main chain).

        Blocks in IRREVERSIBLE state cannot be reorged under any circumstances.
        """
        if block_hash in self.irreversible_blocks:
            return False
        return self.finality_states.get(block_hash, BlockFinalityState.PENDING) != BlockFinalityState.IRREVERSIBLE
    
    def _get_ancestors(self, block_hash: bytes) -> Set[bytes]:
        """Get all ancestors of a block."""
        ancestors = set()
        queue = list(self.blocks[block_hash].parents)
        
        while queue:
            parent = queue.pop()
            if parent in ancestors or parent == b'\x00' * 32:
                continue
            if parent not in self.blocks:
                continue
            ancestors.add(parent)
            queue.extend(self.blocks[parent].parents)
        
        return ancestors
    
    def _get_descendants(self, block_hash: bytes) -> Set[bytes]:
        """Get all descendants of a block."""
        descendants = set()
        queue = list(self.children[block_hash])
        
        while queue:
            child = queue.pop()
            if child in descendants:
                continue
            descendants.add(child)
            queue.extend(self.children[child])
        
        return descendants
    
    def _get_anticone(self, block_hash: bytes) -> Set[bytes]:
        """
        Get anticone of a block.
        
        Anticone(B) = blocks that are neither ancestors nor descendants of B.
        """
        ancestors = self._get_ancestors(block_hash)
        descendants = self._get_descendants(block_hash)
        
        anticone = set()
        for h in self.blocks:
            if h != block_hash and h not in ancestors and h not in descendants:
                anticone.add(h)
        
        return anticone
    
    def _update_blue_set(self, block_hash: bytes):
        """
        Update blue set after adding a block.
        
        Block B is blue if |anticone(B) ∩ blue_set| ≤ k
        """
        anticone = self._get_anticone(block_hash)
        blue_anticone = anticone & self.blue_set
        
        if len(blue_anticone) <= self.k:
            self.blue_set.add(block_hash)
            self.blocks[block_hash]._is_blue = True
            
            # Compute blue score
            parent_scores = [
                self.blue_scores.get(p, 0) 
                for p in self.blocks[block_hash].parents 
                if p in self.blocks
            ]
            self.blue_scores[block_hash] = max(parent_scores, default=0) + 1
            self.blocks[block_hash]._blue_score = self.blue_scores[block_hash]
        else:
            self.blocks[block_hash]._is_blue = False
    
    def get_ordered_blocks(self) -> List[bytes]:
        """
        Get topologically ordered blocks using PHANTOM ordering.
        
        1. Order blue blocks by cumulative VDF weight descending
        2. Insert red blocks between their blue ancestors and descendants
        """
        with self._lock:
            if not self._order_dirty and self._ordered_blocks is not None:
                return self._ordered_blocks
            
            # Separate blue and red blocks
            blue_blocks = [(self.blocks[h].vdf_weight, h) for h in self.blue_set]
            red_blocks = [h for h in self.blocks if h not in self.blue_set]
            
            # Sort blue blocks by VDF weight (descending)
            blue_blocks.sort(reverse=True)
            blue_order = [h for _, h in blue_blocks]
            
            # Insert red blocks
            ordered = []
            blue_index = {h: i for i, h in enumerate(blue_order)}
            
            for blue_hash in blue_order:
                ordered.append(blue_hash)
                
                # Find red blocks that should come after this blue block
                for red_hash in red_blocks:
                    red_block = self.blocks[red_hash]
                    
                    # Check if any parent is this blue block or earlier
                    should_insert = False
                    for parent in red_block.parents:
                        if parent == blue_hash:
                            should_insert = True
                            break
                        if parent in blue_index and blue_index[parent] <= blue_index[blue_hash]:
                            should_insert = True
                            break
                    
                    if should_insert and red_hash not in ordered:
                        ordered.append(red_hash)
            
            # Add any remaining red blocks
            for red_hash in red_blocks:
                if red_hash not in ordered:
                    ordered.append(red_hash)
            
            self._ordered_blocks = ordered
            self._order_dirty = False
            
            return ordered
    
    def get_tips(self) -> List[bytes]:
        """Get current DAG tips."""
        with self._lock:
            return list(self.tips)
    
    def get_block(self, block_hash: bytes) -> Optional[DAGBlock]:
        """Get block by hash."""
        return self.blocks.get(block_hash)
    
    def is_blue(self, block_hash: bytes) -> bool:
        """Check if block is in blue set."""
        return block_hash in self.blue_set

    def get_main_chain(self) -> List[bytes]:
        """
        Get the main chain of blue blocks from genesis to tip.

        The main chain is the path through the DAG with highest
        cumulative VDF weight. This is the canonical chain.

        Returns:
            List of block hashes from genesis to tip
        """
        with self._lock:
            if not self.blocks:
                return []

            # Find genesis (block with null parent)
            genesis = None
            for h, block in self.blocks.items():
                if block.parents == [b'\x00' * 32]:
                    genesis = h
                    break

            if genesis is None:
                # No genesis, return empty
                return []

            # Build main chain by following highest-weight path
            chain = [genesis]
            current = genesis

            while True:
                children = self.children.get(current, set())
                if not children:
                    break

                # Select child with highest VDF weight that is in blue set
                best_child = None
                best_weight = -1

                for child_hash in children:
                    child = self.blocks.get(child_hash)
                    if child and child_hash in self.blue_set:
                        if child.vdf_weight > best_weight:
                            best_weight = child.vdf_weight
                            best_child = child_hash

                # If no blue child, take any child with highest weight
                if best_child is None:
                    for child_hash in children:
                        child = self.blocks.get(child_hash)
                        if child and child.vdf_weight > best_weight:
                            best_weight = child.vdf_weight
                            best_child = child_hash

                if best_child is None:
                    break

                chain.append(best_child)
                current = best_child

            return chain

    def get_finality_score(self, block_hash: bytes) -> float:
        """
        Compute finality score for a block.

        Finality is based on:
        1. Number of blue descendants
        2. Cumulative VDF weight of descendants
        3. Confirmation depth

        Score in [0, 1] where 1.0 = practically irreversible.

        A block is considered final when score > 0.99.
        """
        with self._lock:
            if block_hash not in self.blocks:
                return 0.0

            descendants = self._get_descendants(block_hash)
            if not descendants:
                return 0.0

            # Count blue descendants
            blue_descendants = len(descendants & self.blue_set)

            # Sum VDF weight of descendants
            desc_weight = sum(
                self.blocks[d].vdf_weight
                for d in descendants
                if d in self.blocks
            )

            # Block's own weight
            block_weight = self.blocks[block_hash].vdf_weight

            # Finality score components:
            # 1. Confirmation depth (sigmoid)
            depth_score = 1.0 - (1.0 / (1.0 + blue_descendants / 6))

            # 2. Weight ratio (descendant weight / block weight)
            if block_weight > 0:
                weight_score = min(1.0, desc_weight / (block_weight * 10))
            else:
                weight_score = 0.0

            # Combined score (weighted average)
            score = 0.7 * depth_score + 0.3 * weight_score

            return min(1.0, score)

    def is_finalized(self, block_hash: bytes, threshold: float = 0.99) -> bool:
        """Check if block is finalized (practically irreversible)."""
        return self.get_finality_score(block_hash) >= threshold

    def resolve_fork(self, fork_point: bytes, chain_a: List[bytes], chain_b: List[bytes]) -> List[bytes]:
        """
        Resolve fork between two chains starting from fork_point.

        Uses PHANTOM-PoT rules:
        1. Chain with more blue blocks wins
        2. If equal, chain with higher cumulative VDF weight wins
        3. If still equal, lexicographically lower tip hash wins

        Args:
            fork_point: Common ancestor block hash
            chain_a: List of block hashes in fork A
            chain_b: List of block hashes in fork B

        Returns:
            Winning chain (chain_a or chain_b)
        """
        with self._lock:
            # Count blue blocks in each chain
            blue_a = sum(1 for h in chain_a if h in self.blue_set)
            blue_b = sum(1 for h in chain_b if h in self.blue_set)

            if blue_a > blue_b:
                return chain_a
            elif blue_b > blue_a:
                return chain_b

            # Equal blue count, compare VDF weight
            weight_a = sum(self.blocks[h].vdf_weight for h in chain_a if h in self.blocks)
            weight_b = sum(self.blocks[h].vdf_weight for h in chain_b if h in self.blocks)

            if weight_a > weight_b:
                return chain_a
            elif weight_b > weight_a:
                return chain_b

            # Equal weight, use lexicographic tie-breaker on tip
            tip_a = chain_a[-1] if chain_a else b''
            tip_b = chain_b[-1] if chain_b else b''

            return chain_a if tip_a < tip_b else chain_b

    def detect_fork(self, new_block: DAGBlock) -> Optional[Tuple[bytes, List[bytes], List[bytes]]]:
        """
        Detect if a new block creates a fork.

        Returns:
            None if no fork, or (fork_point, existing_chain, new_chain)
        """
        with self._lock:
            # Check if any parent has multiple children (potential fork)
            for parent_hash in new_block.parents:
                siblings = self.children.get(parent_hash, set())

                # More than one child = potential fork
                if len(siblings) > 1:
                    # Find the fork point and chains
                    for sibling_hash in siblings:
                        if sibling_hash != new_block.block_hash:
                            # Build chains from fork point
                            existing_chain = self._build_chain_from(sibling_hash)
                            new_chain = [new_block.block_hash]

                            return (parent_hash, existing_chain, new_chain)

            return None

    def _build_chain_from(self, start_hash: bytes) -> List[bytes]:
        """Build chain of blocks from start to current tips."""
        chain = [start_hash]
        current = start_hash

        while True:
            children = self.children.get(current, set())
            if not children:
                break

            # Follow highest weight child
            best_child = max(
                children,
                key=lambda h: self.blocks[h].vdf_weight if h in self.blocks else 0
            )
            chain.append(best_child)
            current = best_child

        return chain

    def get_confirmation_depth(self, block_hash: bytes) -> int:
        """
        Get confirmation depth (number of blocks built on top).

        This is the number of blue descendants in the main chain.
        """
        with self._lock:
            if block_hash not in self.blocks:
                return 0

            main_chain = self.get_main_chain()
            if block_hash not in main_chain:
                return 0

            idx = main_chain.index(block_hash)
            return len(main_chain) - idx - 1

    def reorg_blocks(self, new_tip: bytes) -> Tuple[List[bytes], List[bytes]]:
        """
        Compute blocks to disconnect and connect for reorg to new_tip.

        IMPORTANT: Respects finality state machine:
        - IRREVERSIBLE blocks CANNOT be disconnected under any circumstances
        - CONFIRMED+ blocks can only be disconnected if reorg depth < MAX_REORG_DEPTH

        Returns:
            (blocks_to_disconnect, blocks_to_connect)
            Empty lists if reorg is rejected due to finality constraints
        """
        with self._lock:
            current_chain = self.get_main_chain()
            if not current_chain:
                return ([], [new_tip])

            # Find common ancestor
            new_ancestors = self._get_ancestors(new_tip) | {new_tip}

            common_ancestor = None
            for block_hash in reversed(current_chain):
                if block_hash in new_ancestors:
                    common_ancestor = block_hash
                    break

            if common_ancestor is None:
                # Complete reorg from genesis - DANGEROUS, check for irreversible blocks
                for block_hash in current_chain:
                    if block_hash in self.irreversible_blocks:
                        logger.warning(f"Reorg rejected: would disconnect IRREVERSIBLE block {block_hash.hex()[:16]}")
                        return ([], [])
                return (current_chain, self._build_chain_from(new_tip))

            # Blocks to disconnect (after common ancestor in current chain)
            disconnect_idx = current_chain.index(common_ancestor) + 1
            to_disconnect = current_chain[disconnect_idx:]

            # FINALITY PROTECTION: Check if any block to disconnect is irreversible
            for block_hash in to_disconnect:
                if block_hash in self.irreversible_blocks:
                    logger.warning(f"Reorg rejected: would disconnect IRREVERSIBLE block {block_hash.hex()[:16]}")
                    return ([], [])

            # REORG DEPTH PROTECTION: Limit maximum reorg depth
            if len(to_disconnect) > MAX_REORG_DEPTH:
                logger.warning(f"Reorg rejected: depth {len(to_disconnect)} exceeds MAX_REORG_DEPTH {MAX_REORG_DEPTH}")
                return ([], [])

            # CONFIRMED BLOCK PROTECTION: Warn if disconnecting confirmed blocks
            confirmed_count = sum(
                1 for h in to_disconnect
                if self.finality_states.get(h, BlockFinalityState.PENDING) >= BlockFinalityState.CONFIRMED
            )
            if confirmed_count > 0:
                logger.warning(f"Reorg will disconnect {confirmed_count} CONFIRMED+ blocks - this is unusual")

            # Blocks to connect (from common ancestor to new tip)
            to_connect = []
            current = new_tip
            while current != common_ancestor and current in self.blocks:
                to_connect.insert(0, current)
                parents = self.blocks[current].parents
                if parents and parents[0] in self.blocks:
                    current = parents[0]
                else:
                    break

            return (to_disconnect, to_connect)


# ============================================================================
# DAG CONSENSUS ENGINE
# ============================================================================

class DAGConsensusEngine:
    """
    DAG-based consensus engine for Proof of Time.
    
    Features:
    - Concurrent block production
    - PHANTOM-PoT ordering
    - VDF-weighted finality
    - Parent diversity enforcement
    """
    
    def __init__(self):
        self.dag = PHANTOMOrdering()
        self.vdf = WesolowskiVDF(2048, auto_calibrate=False)
        
        # Node weights
        self.node_weights: Dict[bytes, float] = {}  # pubkey -> weight
        
        # Finality tracking
        self.finalized_height: int = 0
        self.finalized_blocks: Set[bytes] = set()
        
        self._lock = threading.RLock()
    
    def can_produce_block(self, node_pubkey: bytes) -> bool:
        """
        Check if node can produce a block.
        
        Node must have weight ≥ θ_min (10% of maximum).
        """
        if not UNSAFE_ALLOWED:
            return False
        weight = self.node_weights.get(node_pubkey, 0.0)
        return weight >= MIN_WEIGHT_THRESHOLD
    
    def calculate_parent_diversity(self, block: DAGBlock) -> int:
        """
        Count unique producers among parent blocks.
        
        Blocks with < 3 unique parent producers receive 50% weight penalty.
        """
        unique_producers = set()
        
        for parent_hash in block.parents:
            parent = self.dag.get_block(parent_hash)
            if parent:
                unique_producers.add(parent.producer)
        
        return len(unique_producers)
    
    def calculate_effective_weight(self, block: DAGBlock) -> int:
        """
        Calculate effective VDF weight with penalties.
        """
        base_weight = block.vdf_weight
        
        # Apply diversity penalty
        diversity = self.calculate_parent_diversity(block)
        if diversity < PARENT_DIVERSITY_MIN:
            base_weight = int(base_weight * DIVERSITY_PENALTY)
        
        return base_weight
    
    def add_block(self, block: DAGBlock) -> Tuple[bool, str]:
        """
        Add block to DAG with validation.
        
        Returns (success, reason).
        """
        with self._lock:
            # Validate header
            if not block.header.validate_parents():
                return False, "Invalid parent references"
            
            # Validate VDF proof
            if block.header.vdf_output and block.header.vdf_proof:
                vdf_proof = VDFProof(
                    output=block.header.vdf_output,
                    proof=block.header.vdf_proof,
                    iterations=block.header.vdf_iterations,
                    input_hash=block.header.vdf_input
                )
                if not self.vdf.verify(vdf_proof):
                    return False, "Invalid VDF proof"
            
            # Validate producer signature
            if not Ed25519.verify(
                block.producer,
                block.header.signing_hash(),
                block.header.producer_signature
            ):
                return False, "Invalid producer signature"

            # Validate transactions (basic safety) and block size
            max_block_bytes = 2 * 1024 * 1024  # 2 MB safety cap
            if len(block.transactions) > MAX_TX_PER_BLOCK:
                return False, "Too many transactions in block"
            tx_bytes_total = 0
            key_images_seen = set()
            for tx in block.transactions:
                valid, reason = TierValidator.validate_transaction(tx)
                if not valid:
                    return False, f"Invalid transaction: {reason}"
                tx_bytes = len(tx.serialize())
                tx_fee = getattr(tx, "fee", 0)
                # Enforce minimal fee rate per KiB (round up)
                min_fee = max(1, ((tx_bytes + 1023) // 1024) * MIN_FEE_RATE_PER_KIB)
                if tx_fee < min_fee:
                    return False, "Transaction fee below minimum rate"
                tx_bytes_total += tx_bytes
                # Collect key images for duplicate detection
                if hasattr(tx, "inputs"):
                    for inp in tx.inputs:
                        ki = getattr(inp, "key_image", None)
                        if ki:
                            if ki in key_images_seen:
                                return False, "Duplicate key image in block"
                            key_images_seen.add(ki)

            if tx_bytes_total > max_block_bytes:
                return False, "Block too large"
            
            # Validate timestamp
            expected_time = self._estimate_block_time(block)
            if abs(block.header.timestamp - expected_time) > TIMESTAMP_TOLERANCE:
                logger.warning(f"Block timestamp deviates by {abs(block.header.timestamp - expected_time)}s")
            
            # Add to DAG
            if not self.dag.add_block(block):
                return False, "Failed to add to DAG"
            
            logger.info(f"Added DAG block {block.block_hash.hex()[:16]} with {len(block.parents)} parents")
            
            return True, "OK"
    
    def _estimate_block_time(self, block: DAGBlock) -> int:
        """Estimate expected block time based on VDF iterations."""
        # Use parent timestamps as baseline
        if not block.parents:
            return int(time.time())
        
        parent_times = []
        for parent_hash in block.parents:
            parent = self.dag.get_block(parent_hash)
            if parent:
                parent_times.append(parent.header.timestamp)
        
        if not parent_times:
            return int(time.time())
        
        # Expected time is max parent time + VDF duration
        vdf_duration = block.header.vdf_iterations / 50000  # Rough estimate
        return int(max(parent_times) + vdf_duration)
    
    def get_ordered_transactions(self) -> List:
        """
        Get all transactions in canonical order.
        
        Follows PHANTOM block ordering, then transaction order within blocks.
        """
        from pantheon.themis.structures import Transaction
        
        ordered_txs = []
        seen_txids = set()
        
        for block_hash in self.dag.get_ordered_blocks():
            block = self.dag.get_block(block_hash)
            if block:
                for tx in block.transactions:
                    txid = tx.hash()
                    if txid not in seen_txids:
                        ordered_txs.append(tx)
                        seen_txids.add(txid)
        
        return ordered_txs
    
    def resolve_conflicts(self, tx1, tx2) -> int:
        """
        Resolve transaction conflict.
        
        Returns index of winning transaction (0 or 1).
        First-seen in ordered sequence wins.
        """
        ordered = self.get_ordered_transactions()
        
        for tx in ordered:
            if tx.hash() == tx1.hash():
                return 0
            if tx.hash() == tx2.hash():
                return 1
        
        return 0  # Default to first
    
    def get_confirmation_depth(self, block_hash: bytes) -> int:
        """
        Get number of descendant blocks (confirmation depth).
        """
        descendants = self.dag._get_descendants(block_hash)
        return len(descendants)
    
    def is_finalized(self, block_hash: bytes) -> bool:
        """
        Check if block is finalized.
        
        Block is finalized when it has sufficient confirmation depth
        from blue blocks.
        """
        return block_hash in self.finalized_blocks
    
    def update_node_weight(self, pubkey: bytes, weight: float):
        """Update node weight for block production eligibility."""
        with self._lock:
            self.node_weights[pubkey] = weight


# ============================================================================
# DAG BLOCK PRODUCER
# ============================================================================

class DAGBlockProducer:
    """
    Produces DAG blocks when eligible.
    
    Unlike linear chains with leader election, DAG allows any node
    above minimum weight threshold to produce blocks.
    """
    
    def __init__(
        self,
        engine: DAGConsensusEngine,
        node_secret_key: bytes,
        node_public_key: bytes
    ):
        self.engine = engine
        self.sk = node_secret_key
        self.pk = node_public_key
        self.vdf = engine.vdf
    
    def create_block(
        self,
        transactions: List,
        mempool_select_count: int = 1000
    ) -> Optional[DAGBlock]:
        """
        Create a new DAG block.
        """
        from pantheon.themis.structures import MerkleTree
        
        # Check eligibility
        if not self.engine.can_produce_block(self.pk):
            logger.warning("Node weight too low to produce blocks")
            return None
        
        # Select parents (current tips, up to MAX_PARENTS)
        tips = self.engine.dag.get_tips()
        if not tips:
            # Genesis case
            parents = [b'\x00' * 32]
        else:
            # Select tips with highest VDF weight
            tip_weights = []
            for tip in tips:
                block = self.engine.dag.get_block(tip)
                weight = block.vdf_weight if block else 0
                tip_weights.append((weight, tip))
            
            tip_weights.sort(reverse=True)
            parents = [h for _, h in tip_weights[:MAX_PARENTS]]
        
        # Compute VDF input from parents
        vdf_input = sha256(b''.join(sorted(parents)))
        
        # Compute VDF proof (this is the time-consuming part)
        iterations = self.vdf.recommended_iterations or self.vdf.MIN_ITERATIONS
        vdf_proof = self.vdf.compute(vdf_input, iterations)
        
        # Calculate accumulated VDF weight
        parent_weights = []
        for parent in parents:
            block = self.engine.dag.get_block(parent)
            if block:
                parent_weights.append(block.vdf_weight)
        
        vdf_weight = max(parent_weights, default=0) + iterations
        
        # Compute VRF proof
        vrf_input = sha256(vdf_proof.output + struct.pack('<Q', int(time.time())))
        vrf_output = ECVRF.prove(self.sk, vrf_input)
        
        # Compute merkle root
        tx_hashes = [tx.hash() for tx in transactions]
        merkle_root = MerkleTree.compute_root(tx_hashes) if tx_hashes else b'\x00' * 32
        
        # Create header
        header = DAGBlockHeader(
            version=PROTOCOL.PROTOCOL_VERSION,
            parents=parents,
            merkle_root=merkle_root,
            timestamp=int(time.time()),
            vdf_input=vdf_input,
            vdf_output=vdf_proof.output,
            vdf_proof=vdf_proof.proof,
            vdf_iterations=iterations,
            vdf_weight=vdf_weight,
            vrf_output=vrf_output.beta,
            vrf_proof=vrf_output.proof,
            producer_pubkey=self.pk,
            node_weight=self.engine.node_weights.get(self.pk, 0.0)
        )
        
        # Sign header
        header.producer_signature = Ed25519.sign(self.sk, header.signing_hash())
        
        # Create block
        block = DAGBlock(header=header, transactions=transactions)
        
        logger.info(f"Produced DAG block {block.block_hash.hex()[:16]} "
                   f"with {len(parents)} parents, weight {vdf_weight}")
        
        return block


# ============================================================================
# SCALABILITY ESTIMATION
# ============================================================================

def estimate_throughput(active_nodes: int, avg_tx_size: int = 500) -> dict:
    """
    Estimate network throughput based on active nodes.
    
    From spec:
    | Active Nodes | Blocks/min | Est. TPS | Storage/year |
    | 100          | ~50        | ~5,000   | ~5 GB        |
    | 1,000        | ~500       | ~50,000  | ~50 GB       |
    | 10,000       | ~5,000     | ~500,000 | ~500 GB      |
    """
    # Linear scaling with node count
    blocks_per_minute = active_nodes * 0.5  # ~0.5 blocks per eligible node per minute
    
    # Assuming ~100 transactions per block
    tps = blocks_per_minute * 100 / 60
    
    # Storage per year (assuming avg block size)
    avg_block_size = 100 * avg_tx_size  # 100 txs * avg_tx_size
    blocks_per_year = blocks_per_minute * 60 * 24 * 365
    storage_per_year_gb = (blocks_per_year * avg_block_size) / (1024**3)
    
    return {
        'active_nodes': active_nodes,
        'blocks_per_minute': blocks_per_minute,
        'estimated_tps': tps,
        'storage_per_year_gb': storage_per_year_gb
    }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run DAG module self-tests."""
    logger.info("Running DAG self-tests...")
    
    # Test DAG block header serialization
    header = DAGBlockHeader(
        parents=[b'\x01' * 32, b'\x02' * 32],
        merkle_root=b'\x03' * 32,
        timestamp=int(time.time()),
        vdf_weight=1000000
    )
    
    data = header.serialize()
    restored, _ = DAGBlockHeader.deserialize(data)
    
    assert len(restored.parents) == 2
    assert restored.merkle_root == header.merkle_root
    assert restored.vdf_weight == header.vdf_weight
    logger.info("✓ DAG header serialization")
    
    # Test PHANTOM ordering
    phantom = PHANTOMOrdering()
    
    # Create genesis block
    genesis = DAGBlock(header=DAGBlockHeader(
        parents=[b'\x00' * 32],
        vdf_weight=0
    ))
    phantom.add_block(genesis)
    
    # Create child blocks
    child1 = DAGBlock(header=DAGBlockHeader(
        parents=[genesis.block_hash],
        vdf_weight=1000,
        producer_pubkey=b'\x01' * 32
    ))
    phantom.add_block(child1)
    
    child2 = DAGBlock(header=DAGBlockHeader(
        parents=[genesis.block_hash],
        vdf_weight=2000,
        producer_pubkey=b'\x02' * 32
    ))
    phantom.add_block(child2)
    
    # Both children should be tips
    tips = phantom.get_tips()
    assert len(tips) == 2
    logger.info("✓ PHANTOM tip tracking")
    
    # Get ordered blocks
    ordered = phantom.get_ordered_blocks()
    assert len(ordered) == 3
    logger.info("✓ PHANTOM ordering")
    
    # Test blue set
    assert phantom.is_blue(genesis.block_hash)
    logger.info("✓ Blue set membership")
    
    # Test throughput estimation
    est = estimate_throughput(1000)
    assert est['estimated_tps'] > 0
    logger.info(f"✓ Throughput estimation ({est['estimated_tps']:.0f} TPS for 1000 nodes)")
    
    logger.info("All DAG self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()

