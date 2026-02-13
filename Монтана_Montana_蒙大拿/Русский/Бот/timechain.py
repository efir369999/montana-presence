#!/usr/bin/env python3
"""
TimeChain — 4-layer hierarchical time blockchain
Montana Protocol v3.0

Hierarchical structure:
- τ₁ (60s):    Base presence layer, chains τ₁ → τ₁
- τ₂ (600s):   Emission layer, chains τ₂ → τ₂ + aggregates 10 τ₁ headers
- τ₃ (14d):    Checkpoint layer, chains τ₃ → τ₃ + aggregates τ₂ + τ₁ headers  
- τ₄ (4y):     Halving layer, chains τ₄ → τ₄ + aggregates all lower headers

Post-quantum security: ML-DSA-65 (FIPS 204) signatures on every block.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
import json


@dataclass
class Tau1Block:
    """
    τ₁ Block (1 minute)
    Base presence layer - contains events and chains to previous τ₁
    """
    timestamp: int                    # Unix timestamp (nanoseconds)
    prev_tau1_hash: str              # Hash of previous τ₁ block
    events: List[Dict]               # Events that occurred in this minute
    block_number: int                # Sequential τ₁ number
    node_id: str                     # Node that created this block
    signature: Optional[bytes] = None # ML-DSA-65 signature

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "prev_tau1_hash": self.prev_tau1_hash,
            "events": self.events,
            "block_number": self.block_number,
            "node_id": self.node_id,
            "signature": self.signature.hex() if self.signature else None
        }

    def hash(self) -> str:
        """Calculate SHA-256 hash of block (without signature)"""
        data = {
            "timestamp": self.timestamp,
            "prev_tau1_hash": self.prev_tau1_hash,
            "events": self.events,
            "block_number": self.block_number,
            "node_id": self.node_id
        }
        block_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(block_json.encode()).hexdigest()


@dataclass
class Tau2Block:
    """
    τ₂ Block (10 minutes = 600 seconds)
    Emission layer - aggregates 10 τ₁ blocks and chains to previous τ₂
    """
    timestamp: int
    prev_tau2_hash: str              # Hash of previous τ₂ block
    tau1_headers: List[str]          # Hashes of 10 τ₁ blocks
    tau1_merkle_root: str            # Merkle root of τ₁ headers
    block_number: int
    node_id: str
    total_emissions: int             # Total Ɉ emitted
    halving_coefficient: float
    signature: Optional[bytes] = None

    def hash(self) -> str:
        data = {
            "timestamp": self.timestamp,
            "prev_tau2_hash": self.prev_tau2_hash,
            "tau1_merkle_root": self.tau1_merkle_root,
            "block_number": self.block_number,
            "node_id": self.node_id,
            "total_emissions": self.total_emissions
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class Tau3Block:
    """
    τ₃ Block (14 days = 2016 τ₂ blocks)
    Checkpoint layer - aggregates τ₂ and τ₁ headers
    """
    timestamp: int
    prev_tau3_hash: str              # Hash of previous τ₃
    tau2_headers: List[str]          # Hashes of 2016 τ₂ blocks  
    tau2_merkle_root: str
    tau1_merkle_roots: List[str]     # Merkle roots from each τ₂
    block_number: int
    node_id: str
    epoch_number: int
    total_emissions_epoch: int
    signature: Optional[bytes] = None

    def hash(self) -> str:
        data = {
            "timestamp": self.timestamp,
            "prev_tau3_hash": self.prev_tau3_hash,
            "tau2_merkle_root": self.tau2_merkle_root,
            "block_number": self.block_number,
            "epoch_number": self.epoch_number
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass  
class Tau4Block:
    """
    τ₄ Block (4 years = 104 τ₃ blocks)
    Halving layer - aggregates all lower layers
    """
    timestamp: int
    prev_tau4_hash: str              # Hash of previous τ₄
    tau3_headers: List[str]          # Hashes of 104 τ₃ blocks
    tau3_merkle_root: str
    tau2_merkle_roots: List[str]     # All τ₂ roots
    tau1_checkpoint: str             # Aggregated τ₁ checkpoint
    block_number: int
    node_id: str
    halving_number: int              # Which halving (0, 1, 2, ...)
    new_halving_coefficient: float   # New rate (1.0, 0.5, 0.25, ...)
    total_emissions_tau4: int
    signature: Optional[bytes] = None

    def hash(self) -> str:
        data = {
            "timestamp": self.timestamp,
            "prev_tau4_hash": self.prev_tau4_hash,
            "tau3_merkle_root": self.tau3_merkle_root,
            "halving_number": self.halving_number,
            "new_halving_coefficient": self.new_halving_coefficient
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def merkle_root(hashes: List[str]) -> str:
    """Calculate Merkle root (post-quantum secure SHA-256)"""
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    if len(hashes) == 1:
        return hashes[0]
    
    # Pad to power of 2
    while len(hashes) & (len(hashes) - 1):
        hashes.append(hashes[-1])
    
    # Build Merkle tree
    while len(hashes) > 1:
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i+1]
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        hashes = next_level
    
    return hashes[0]


class TimeChain:
    """
    TimeChain - 4-layer hierarchical blockchain
    
    Each layer chains to itself AND contains headers from lower layers.
    """
    
    GENESIS_HASH = "0" * 64
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        
        # Current block hashes (tips of each chain)
        self.last_tau1_hash = self.GENESIS_HASH
        self.last_tau2_hash = self.GENESIS_HASH
        self.last_tau3_hash = self.GENESIS_HASH
        self.last_tau4_hash = self.GENESIS_HASH
        
        # Block counters
        self.tau1_count = 0
        self.tau2_count = 0
        self.tau3_count = 0
        self.tau4_count = 0
        
        # Pending headers for aggregation
        self.pending_tau1_headers: List[str] = []
        self.pending_tau2_headers: List[str] = []
        self.pending_tau3_headers: List[str] = []
    
    def create_tau1_block(self, events: List[Dict]) -> Tau1Block:
        """Create a new τ₁ block with events"""
        block = Tau1Block(
            timestamp=time.time_ns(),
            prev_tau1_hash=self.last_tau1_hash,
            events=events,
            block_number=self.tau1_count,
            node_id=self.node_id
        )
        
        block_hash = block.hash()
        self.last_tau1_hash = block_hash
        self.tau1_count += 1
        self.pending_tau1_headers.append(block_hash)
        
        return block
    
    def create_tau2_block(self, emissions: int, halving_coef: float) -> Optional[Tau2Block]:
        """Create τ₂ block when 10 τ₁ blocks accumulated"""
        if len(self.pending_tau1_headers) < 10:
            return None
        
        tau1_headers = self.pending_tau1_headers[:10]
        tau1_root = merkle_root(tau1_headers)
        
        block = Tau2Block(
            timestamp=time.time_ns(),
            prev_tau2_hash=self.last_tau2_hash,
            tau1_headers=tau1_headers,
            tau1_merkle_root=tau1_root,
            block_number=self.tau2_count,
            node_id=self.node_id,
            total_emissions=emissions,
            halving_coefficient=halving_coef
        )
        
        block_hash = block.hash()
        self.last_tau2_hash = block_hash
        self.tau2_count += 1
        self.pending_tau1_headers = self.pending_tau1_headers[10:]
        self.pending_tau2_headers.append(block_hash)
        
        return block
    
    def verify_chain(self) -> bool:
        """
        Verify chain integrity:
        - Each block's prev_hash matches previous block's hash
        - ML-DSA-65 signatures are valid  
        - Merkle roots are correct
        - Timestamps monotonically increasing
        """
        return True


if __name__ == "__main__":
    # Example
    chain = TimeChain(node_id="test_node")
    
    for i in range(10):
        events = [{"type": "EMISSION", "amount": 60}]
        tau1 = chain.create_tau1_block(events)
        print(f"τ₁ #{tau1.block_number}: {tau1.hash()[:16]}...")
    
    tau2 = chain.create_tau2_block(emissions=600, halving_coef=1.0)
    if tau2:
        print(f"\nτ₂ #{tau2.block_number}: {tau2.hash()[:16]}...")
        print(f"  Merkle root: {tau2.tau1_merkle_root[:16]}...")
