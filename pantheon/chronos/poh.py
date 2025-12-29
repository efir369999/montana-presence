"""
Proof of Time - Proof of History (PoH) Module

Dual-layer consensus:
- PoH: 1 block per second (fast transactions)
- PoT: 1 checkpoint every 10 minutes (VDF finality)

PoH provides verifiable passage of time through sequential hashing.
PoT provides objective finality through VDF proofs.

Time is the ultimate proof.
"""

import struct
import time
import hashlib
import threading
import logging
from typing import List, Optional, Dict, Tuple, Set
from dataclasses import dataclass, field
from enum import IntEnum

from pantheon.prometheus import sha256, sha256d, Ed25519
from config import PROTOCOL

logger = logging.getLogger("proof_of_time.poh")


# ============================================================================
# CONFIGURATION
# ============================================================================

class PoHConfig:
    """PoH layer configuration."""

    # Block timing
    POH_BLOCK_TIME: int = 1          # 1 second per PoH block
    POT_CHECKPOINT_INTERVAL: int = 600  # 600 PoH blocks = 10 minutes

    # PoH hash chain
    HASHES_PER_TICK: int = 12500     # Hash operations per tick
    TICKS_PER_BLOCK: int = 64        # Ticks per PoH block

    # Leader schedule
    SLOTS_PER_EPOCH: int = 432000    # ~5 days at 1 block/sec
    LEADER_SCHEDULE_LOOKAHEAD: int = 2  # Epochs ahead to compute schedule


# ============================================================================
# POH TICK
# ============================================================================

@dataclass
class PoHTick:
    """
    Single PoH tick - atomic unit of the hash chain.

    Each tick contains:
    - Hash value (result of sequential hashing)
    - Number of hashes computed
    - Optional transaction hashes mixed in
    """
    hash: bytes                      # Current hash state
    hash_count: int                  # Total hashes so far
    tx_hashes: List[bytes] = field(default_factory=list)  # Mixed-in tx hashes

    def serialize(self) -> bytes:
        """Serialize tick."""
        data = bytearray()
        data.extend(self.hash)
        data.extend(struct.pack('<Q', self.hash_count))
        data.extend(struct.pack('<H', len(self.tx_hashes)))
        for txh in self.tx_hashes:
            data.extend(txh)
        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['PoHTick', int]:
        """Deserialize tick."""
        hash_val = data[offset:offset + 32]
        offset += 32
        hash_count = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        num_tx = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        tx_hashes = []
        for _ in range(num_tx):
            tx_hashes.append(data[offset:offset + 32])
            offset += 32
        return cls(hash=hash_val, hash_count=hash_count, tx_hashes=tx_hashes), offset


# ============================================================================
# POH BLOCK
# ============================================================================

@dataclass
class PoHBlock:
    """
    PoH block - 1 second of hash chain history.

    Contains:
    - Slot number (block height in PoH chain)
    - Ticks (hash chain segments)
    - Transactions
    - Leader signature
    - Reference to last PoT checkpoint
    """
    # Identity
    slot: int = 0                    # PoH slot number
    parent_hash: bytes = b'\x00' * 32

    # Hash chain
    ticks: List[PoHTick] = field(default_factory=list)

    # Transactions (hashes only, full tx in separate store)
    tx_hashes: List[bytes] = field(default_factory=list)

    # Leader
    leader_pubkey: bytes = b'\x00' * 32
    leader_signature: bytes = b'\x00' * 64

    # PoT anchor (last finalized checkpoint)
    pot_checkpoint_slot: int = 0     # Last PoT checkpoint slot
    pot_checkpoint_hash: bytes = b'\x00' * 32

    # Timestamp (wall clock, for reference only)
    timestamp: int = 0

    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)

    def hash(self) -> bytes:
        """Compute block hash."""
        if self._hash is None:
            data = bytearray()
            data.extend(struct.pack('<Q', self.slot))
            data.extend(self.parent_hash)
            # Hash of all ticks
            if self.ticks:
                tick_data = b''.join(t.serialize() for t in self.ticks)
                data.extend(sha256(tick_data))
            else:
                data.extend(b'\x00' * 32)
            # Transaction merkle root
            if self.tx_hashes:
                data.extend(sha256(b''.join(self.tx_hashes)))
            else:
                data.extend(b'\x00' * 32)
            data.extend(self.leader_pubkey)
            data.extend(struct.pack('<Q', self.pot_checkpoint_slot))
            self._hash = sha256d(bytes(data))
        return self._hash

    @property
    def final_tick_hash(self) -> bytes:
        """Get final tick hash of this block."""
        if self.ticks:
            return self.ticks[-1].hash
        return self.parent_hash

    def serialize(self) -> bytes:
        """Serialize block."""
        data = bytearray()

        # Header
        data.extend(struct.pack('<Q', self.slot))
        data.extend(self.parent_hash)
        data.extend(struct.pack('<Q', self.timestamp))

        # Ticks
        data.extend(struct.pack('<H', len(self.ticks)))
        for tick in self.ticks:
            tick_bytes = tick.serialize()
            data.extend(struct.pack('<H', len(tick_bytes)))
            data.extend(tick_bytes)

        # Transactions
        data.extend(struct.pack('<I', len(self.tx_hashes)))
        for txh in self.tx_hashes:
            data.extend(txh)

        # Leader
        data.extend(self.leader_pubkey)
        data.extend(self.leader_signature)

        # PoT anchor
        data.extend(struct.pack('<Q', self.pot_checkpoint_slot))
        data.extend(self.pot_checkpoint_hash)

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['PoHBlock', int]:
        """Deserialize block."""
        # Header
        slot = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        parent_hash = data[offset:offset + 32]
        offset += 32
        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # Ticks
        num_ticks = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        ticks = []
        for _ in range(num_ticks):
            tick_len = struct.unpack_from('<H', data, offset)[0]
            offset += 2
            tick, _ = PoHTick.deserialize(data, offset)
            ticks.append(tick)
            offset += tick_len

        # Transactions
        num_tx = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        tx_hashes = []
        for _ in range(num_tx):
            tx_hashes.append(data[offset:offset + 32])
            offset += 32

        # Leader
        leader_pubkey = data[offset:offset + 32]
        offset += 32
        leader_signature = data[offset:offset + 64]
        offset += 64

        # PoT anchor
        pot_checkpoint_slot = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        pot_checkpoint_hash = data[offset:offset + 32]
        offset += 32

        return cls(
            slot=slot,
            parent_hash=parent_hash,
            timestamp=timestamp,
            ticks=ticks,
            tx_hashes=tx_hashes,
            leader_pubkey=leader_pubkey,
            leader_signature=leader_signature,
            pot_checkpoint_slot=pot_checkpoint_slot,
            pot_checkpoint_hash=pot_checkpoint_hash
        ), offset


# ============================================================================
# POT CHECKPOINT
# ============================================================================

@dataclass
class PoTCheckpoint:
    """
    PoT checkpoint - VDF-based finality anchor.

    Every 600 PoH blocks (10 minutes), a PoT checkpoint is created.
    This provides objective finality through VDF proofs.
    """
    # Identity
    checkpoint_id: int = 0           # Checkpoint sequence number

    # PoH range covered
    start_slot: int = 0              # First PoH slot in this checkpoint
    end_slot: int = 0                # Last PoH slot in this checkpoint

    # PoH state
    poh_hash: bytes = b'\x00' * 32   # Final PoH hash at end_slot

    # VDF proof (10 minutes of computation)
    vdf_input: bytes = b'\x00' * 32  # Input to VDF
    vdf_output: bytes = b''          # VDF result
    vdf_proof: bytes = b''           # VDF verification proof
    vdf_iterations: int = 0          # Number of squarings

    # VRF for checkpoint leader
    vrf_output: bytes = b''
    vrf_proof: bytes = b''

    # Leader
    leader_pubkey: bytes = b'\x00' * 32
    leader_signature: bytes = b'\x00' * 64

    # Previous checkpoint
    prev_checkpoint_hash: bytes = b'\x00' * 32

    # Timestamp
    timestamp: int = 0

    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)

    def hash(self) -> bytes:
        """Compute checkpoint hash."""
        if self._hash is None:
            data = bytearray()
            data.extend(struct.pack('<Q', self.checkpoint_id))
            data.extend(struct.pack('<Q', self.start_slot))
            data.extend(struct.pack('<Q', self.end_slot))
            data.extend(self.poh_hash)
            data.extend(self.vdf_output)
            data.extend(self.vrf_output)
            data.extend(self.leader_pubkey)
            data.extend(self.prev_checkpoint_hash)
            self._hash = sha256d(bytes(data))
        return self._hash

    def serialize(self) -> bytes:
        """Serialize checkpoint."""
        data = bytearray()

        # Header
        data.extend(struct.pack('<Q', self.checkpoint_id))
        data.extend(struct.pack('<Q', self.start_slot))
        data.extend(struct.pack('<Q', self.end_slot))
        data.extend(struct.pack('<Q', self.timestamp))

        # PoH state
        data.extend(self.poh_hash)

        # VDF
        data.extend(self.vdf_input)
        data.extend(struct.pack('<I', len(self.vdf_output)))
        data.extend(self.vdf_output)
        data.extend(struct.pack('<I', len(self.vdf_proof)))
        data.extend(self.vdf_proof)
        data.extend(struct.pack('<I', self.vdf_iterations))

        # VRF
        data.extend(struct.pack('<I', len(self.vrf_output)))
        data.extend(self.vrf_output)
        data.extend(struct.pack('<I', len(self.vrf_proof)))
        data.extend(self.vrf_proof)

        # Leader
        data.extend(self.leader_pubkey)
        data.extend(self.leader_signature)

        # Previous
        data.extend(self.prev_checkpoint_hash)

        return bytes(data)


# ============================================================================
# POH GENERATOR
# ============================================================================

class PoHGenerator:
    """
    Proof of History hash chain generator.

    Continuously computes sequential SHA-256 hashes to prove
    passage of time. Transactions are mixed into the hash chain.
    """

    def __init__(self, initial_hash: bytes = b'\x00' * 32):
        self.current_hash = initial_hash
        self.hash_count = 0
        self.ticks: List[PoHTick] = []

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Pending transactions to mix in
        self._pending_tx: List[bytes] = []

    def _hash_step(self) -> bytes:
        """Single hash step."""
        self.current_hash = sha256(self.current_hash)
        self.hash_count += 1
        return self.current_hash

    def _mix_transaction(self, tx_hash: bytes):
        """Mix transaction hash into PoH chain."""
        self.current_hash = sha256(self.current_hash + tx_hash)
        self.hash_count += 1

    def generate_tick(self, hashes_per_tick: int = PoHConfig.HASHES_PER_TICK) -> PoHTick:
        """Generate one tick (segment of hash chain)."""
        with self._lock:
            # Collect pending transactions
            tx_hashes = self._pending_tx.copy()
            self._pending_tx.clear()

            # Mix transactions
            for txh in tx_hashes:
                self._mix_transaction(txh)

            # Compute remaining hashes
            remaining = hashes_per_tick - len(tx_hashes)
            for _ in range(remaining):
                self._hash_step()

            return PoHTick(
                hash=self.current_hash,
                hash_count=self.hash_count,
                tx_hashes=tx_hashes
            )

    def generate_block_ticks(self) -> List[PoHTick]:
        """Generate ticks for one PoH block (1 second)."""
        ticks = []
        for _ in range(PoHConfig.TICKS_PER_BLOCK):
            tick = self.generate_tick()
            ticks.append(tick)
        return ticks

    def add_transaction(self, tx_hash: bytes):
        """Queue transaction to be mixed into hash chain."""
        with self._lock:
            self._pending_tx.append(tx_hash)

    def verify_chain(self, ticks: List[PoHTick], start_hash: bytes) -> bool:
        """
        Verify a sequence of ticks.

        This is fast verification - we don't recompute all hashes,
        just verify the structure is valid.
        """
        if not ticks:
            return True

        prev_count = 0
        for tick in ticks:
            # Hash count must increase
            if tick.hash_count <= prev_count:
                return False
            prev_count = tick.hash_count

            # Hash must be 32 bytes
            if len(tick.hash) != 32:
                return False

        return True

    @staticmethod
    def verify_tick(tick: PoHTick, prev_hash: bytes, expected_hashes: int) -> bool:
        """
        Fully verify a tick by recomputing hashes.

        This is expensive but provides cryptographic verification.
        """
        current = prev_hash

        # Mix transactions
        for txh in tick.tx_hashes:
            current = sha256(current + txh)

        # Remaining hashes
        remaining = expected_hashes - len(tick.tx_hashes)
        for _ in range(remaining):
            current = sha256(current)

        return current == tick.hash


# ============================================================================
# POH CHAIN
# ============================================================================

class PoHChain:
    """
    PoH blockchain manager.

    Manages the fast PoH chain and its relationship
    to PoT checkpoints for finality.
    """

    def __init__(self):
        self.blocks: Dict[int, PoHBlock] = {}  # slot -> block
        self.checkpoints: Dict[int, PoTCheckpoint] = {}  # id -> checkpoint

        self.current_slot: int = 0
        self.last_checkpoint_id: int = 0

        self._lock = threading.RLock()

        # Generator for producing PoH
        self.generator = PoHGenerator()

    def add_block(self, block: PoHBlock) -> bool:
        """Add a PoH block to the chain."""
        with self._lock:
            # Validate slot
            if block.slot in self.blocks:
                logger.warning(f"Duplicate PoH block at slot {block.slot}")
                return False

            # Validate parent (except genesis)
            if block.slot > 0:
                if block.slot - 1 not in self.blocks:
                    logger.warning(f"Missing parent for slot {block.slot}")
                    return False
                parent = self.blocks[block.slot - 1]
                if block.parent_hash != parent.hash():
                    logger.warning(f"Parent hash mismatch at slot {block.slot}")
                    return False

            # Verify PoH chain
            prev_hash = block.parent_hash
            if not self.generator.verify_chain(block.ticks, prev_hash):
                logger.warning(f"Invalid PoH chain at slot {block.slot}")
                return False

            # Store block
            self.blocks[block.slot] = block
            self.current_slot = max(self.current_slot, block.slot)

            logger.debug(f"Added PoH block slot={block.slot} txs={len(block.tx_hashes)}")
            return True

    def add_checkpoint(self, checkpoint: PoTCheckpoint) -> bool:
        """Add a PoT checkpoint."""
        with self._lock:
            # Validate checkpoint ID
            if checkpoint.checkpoint_id in self.checkpoints:
                logger.warning(f"Duplicate checkpoint {checkpoint.checkpoint_id}")
                return False

            # Validate PoH range exists
            for slot in range(checkpoint.start_slot, checkpoint.end_slot + 1):
                if slot not in self.blocks:
                    logger.warning(f"Checkpoint refers to missing slot {slot}")
                    return False

            # Validate PoH hash
            end_block = self.blocks[checkpoint.end_slot]
            if checkpoint.poh_hash != end_block.final_tick_hash:
                logger.warning(f"Checkpoint PoH hash mismatch")
                return False

            # Store checkpoint
            self.checkpoints[checkpoint.checkpoint_id] = checkpoint
            self.last_checkpoint_id = max(self.last_checkpoint_id, checkpoint.checkpoint_id)

            logger.info(
                f"Added PoT checkpoint {checkpoint.checkpoint_id}: "
                f"slots {checkpoint.start_slot}-{checkpoint.end_slot}"
            )
            return True

    def get_finalized_slot(self) -> int:
        """Get the highest finalized (checkpointed) slot."""
        with self._lock:
            if not self.checkpoints:
                return 0
            latest = self.checkpoints[self.last_checkpoint_id]
            return latest.end_slot

    def get_confirmations(self, slot: int) -> Tuple[int, bool]:
        """
        Get confirmations for a slot.

        Returns:
            (confirmations, is_finalized)
            - confirmations: number of PoH blocks on top
            - is_finalized: True if covered by PoT checkpoint
        """
        with self._lock:
            if slot not in self.blocks:
                return 0, False

            confirmations = self.current_slot - slot
            finalized_slot = self.get_finalized_slot()
            is_finalized = slot <= finalized_slot

            return confirmations, is_finalized

    def should_create_checkpoint(self) -> bool:
        """Check if it's time to create a new checkpoint."""
        with self._lock:
            # Find last checkpointed slot
            if self.checkpoints:
                latest = self.checkpoints[self.last_checkpoint_id]
                last_checkpointed = latest.end_slot
            else:
                last_checkpointed = 0

            # Check if enough slots have passed
            slots_since = self.current_slot - last_checkpointed
            return slots_since >= PoHConfig.POT_CHECKPOINT_INTERVAL


# ============================================================================
# LEADER SCHEDULE
# ============================================================================

class LeaderSchedule:
    """
    Leader schedule for PoH slots.

    Determines which validator produces each PoH block.
    Schedule is deterministic based on stake and epoch seed.
    """

    def __init__(self):
        self._schedule: Dict[int, bytes] = {}  # slot -> leader pubkey
        self._epoch_seeds: Dict[int, bytes] = {}  # epoch -> seed

    def compute_epoch(self, slot: int) -> int:
        """Get epoch number for a slot."""
        return slot // PoHConfig.SLOTS_PER_EPOCH

    def compute_schedule(
        self,
        epoch: int,
        validators: List[Tuple[bytes, int]],  # (pubkey, stake)
        seed: bytes
    ):
        """
        Compute leader schedule for an epoch.

        Uses stake-weighted random selection based on epoch seed.
        """
        if not validators:
            return

        # Store seed
        self._epoch_seeds[epoch] = seed

        # Compute total stake
        total_stake = sum(stake for _, stake in validators)
        if total_stake == 0:
            return

        # Generate schedule
        start_slot = epoch * PoHConfig.SLOTS_PER_EPOCH

        for i in range(PoHConfig.SLOTS_PER_EPOCH):
            slot = start_slot + i

            # Deterministic random from seed + slot
            slot_seed = sha256(seed + struct.pack('<Q', slot))
            value = int.from_bytes(slot_seed[:8], 'little')

            # Weighted selection
            target = value % total_stake
            cumulative = 0

            for pubkey, stake in validators:
                cumulative += stake
                if cumulative > target:
                    self._schedule[slot] = pubkey
                    break

    def get_leader(self, slot: int) -> Optional[bytes]:
        """Get leader for a slot."""
        return self._schedule.get(slot)

    def is_leader(self, slot: int, pubkey: bytes) -> bool:
        """Check if pubkey is leader for slot."""
        return self._schedule.get(slot) == pubkey


# ============================================================================
# DUAL CONSENSUS ENGINE
# ============================================================================

class DualConsensusEngine:
    """
    Dual-layer consensus: PoH + PoT.

    - PoH layer: Fast 1-second blocks for transactions
    - PoT layer: 10-minute VDF checkpoints for finality

    PoH provides speed, PoT provides security.
    """

    def __init__(self):
        self.poh_chain = PoHChain()
        self.leader_schedule = LeaderSchedule()

        self._running = False
        self._poh_thread: Optional[threading.Thread] = None
        self._pot_thread: Optional[threading.Thread] = None

        # My identity
        self.keypair: Optional[Tuple[bytes, bytes]] = None  # (pubkey, privkey)

        # Callbacks
        self.on_poh_block: Optional[callable] = None
        self.on_pot_checkpoint: Optional[callable] = None

    def start(self, keypair: Tuple[bytes, bytes]):
        """Start consensus engine."""
        self.keypair = keypair
        self._running = True

        # Start PoH production thread
        self._poh_thread = threading.Thread(
            target=self._poh_loop,
            name="PoH-Producer",
            daemon=True
        )
        self._poh_thread.start()

        logger.info("Dual consensus engine started")

    def stop(self):
        """Stop consensus engine."""
        self._running = False
        if self._poh_thread:
            self._poh_thread.join(timeout=2.0)
        logger.info("Dual consensus engine stopped")

    def _poh_loop(self):
        """PoH block production loop."""
        next_slot_time = time.time()

        while self._running:
            now = time.time()

            # Wait for next slot
            if now < next_slot_time:
                time.sleep(next_slot_time - now)

            slot = self.poh_chain.current_slot + 1

            # Check if we're the leader
            if self.keypair and self.leader_schedule.is_leader(slot, self.keypair[0]):
                block = self._produce_poh_block(slot)
                if block:
                    self.poh_chain.add_block(block)
                    if self.on_poh_block:
                        self.on_poh_block(block)

            # Schedule next slot
            next_slot_time += PoHConfig.POH_BLOCK_TIME

            # Check for checkpoint
            if self.poh_chain.should_create_checkpoint():
                self._trigger_checkpoint()

    def _produce_poh_block(self, slot: int) -> Optional[PoHBlock]:
        """Produce a PoH block."""
        if not self.keypair:
            return None

        pubkey, privkey = self.keypair

        # Get parent
        if slot > 0 and (slot - 1) in self.poh_chain.blocks:
            parent = self.poh_chain.blocks[slot - 1]
            parent_hash = parent.hash()
        else:
            parent_hash = b'\x00' * 32

        # Generate ticks
        ticks = self.poh_chain.generator.generate_block_ticks()

        # Get latest checkpoint
        if self.poh_chain.checkpoints:
            latest_cp = self.poh_chain.checkpoints[self.poh_chain.last_checkpoint_id]
            pot_slot = latest_cp.end_slot
            pot_hash = latest_cp.hash()
        else:
            pot_slot = 0
            pot_hash = b'\x00' * 32

        # Create block
        block = PoHBlock(
            slot=slot,
            parent_hash=parent_hash,
            ticks=ticks,
            tx_hashes=[],  # TODO: collect from mempool
            leader_pubkey=pubkey,
            pot_checkpoint_slot=pot_slot,
            pot_checkpoint_hash=pot_hash,
            timestamp=int(time.time())
        )

        # Sign
        signing_data = block.hash()
        block.leader_signature = Ed25519.sign(privkey, signing_data)

        return block

    def _trigger_checkpoint(self):
        """Trigger PoT checkpoint creation."""
        # This will be called when enough PoH blocks have accumulated
        # The PoT checkpoint creation requires VDF computation
        logger.info("PoT checkpoint triggered (VDF computation starting)")

        # TODO: Start VDF computation in background
        # When complete, create and broadcast PoTCheckpoint

    def add_transaction(self, tx_hash: bytes):
        """Add transaction to be included in next block."""
        self.poh_chain.generator.add_transaction(tx_hash)


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run PoH self-tests."""
    logger.info("Running PoH self-tests...")

    # Test PoH generator
    gen = PoHGenerator(b'\x00' * 32)
    tick1 = gen.generate_tick(hashes_per_tick=100)
    tick2 = gen.generate_tick(hashes_per_tick=100)

    assert tick2.hash_count > tick1.hash_count
    assert tick1.hash != tick2.hash
    logger.info("  PoH generator")

    # Test tick verification
    gen2 = PoHGenerator(b'\x00' * 32)
    tick = gen2.generate_tick(hashes_per_tick=100)
    assert PoHGenerator.verify_tick(tick, b'\x00' * 32, 100)
    logger.info("  Tick verification")

    # Test PoH block
    block = PoHBlock(
        slot=0,
        parent_hash=b'\x00' * 32,
        ticks=[tick1, tick2],
        tx_hashes=[sha256(b'tx1'), sha256(b'tx2')],
        leader_pubkey=b'\x01' * 32,
        timestamp=int(time.time())
    )

    block_bytes = block.serialize()
    block2, _ = PoHBlock.deserialize(block_bytes)
    assert block2.slot == block.slot
    assert block2.hash() == block.hash()
    logger.info("  PoH block serialization")

    # Test chain
    chain = PoHChain()

    # Create genesis block
    gen = PoHGenerator()
    genesis_ticks = gen.generate_block_ticks()
    genesis = PoHBlock(
        slot=0,
        parent_hash=b'\x00' * 32,
        ticks=genesis_ticks,
        timestamp=int(time.time())
    )
    assert chain.add_block(genesis)

    # Create second block
    block1_ticks = gen.generate_block_ticks()
    block1 = PoHBlock(
        slot=1,
        parent_hash=genesis.hash(),
        ticks=block1_ticks,
        timestamp=int(time.time())
    )
    assert chain.add_block(block1)

    assert chain.current_slot == 1
    logger.info("  PoH chain")

    # Test leader schedule
    schedule = LeaderSchedule()
    validators = [
        (b'\x01' * 32, 100),
        (b'\x02' * 32, 200),
        (b'\x03' * 32, 300),
    ]
    schedule.compute_schedule(0, validators, sha256(b'epoch0'))

    leader = schedule.get_leader(0)
    assert leader in [v[0] for v in validators]
    logger.info("  Leader schedule")

    logger.info("All PoH self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
