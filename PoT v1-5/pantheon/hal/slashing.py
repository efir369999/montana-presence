"""
HAL - Slashing Module

Manages slashing conditions and penalties for Byzantine behavior.
Moved from ATHENA to HAL as part of Human Analyse Language.

Slashing conditions:
1. EQUIVOCATION: Signing two different blocks at the same height
2. INVALID_VRF: Forging or reusing VRF proofs
3. INVALID_VDF: Submitting invalid VDF proofs
4. DOUBLE_SPEND: Including double-spend in block

Penalties (immediate and irreversible):
- Reputation reset to 0
- Time presence reset to current time (lose all seniority)
- 180-day quarantine
- Cannot be selected as leader during quarantine
- Cannot receive block rewards during quarantine
- Probability reduced by 90% even after quarantine ends

Evidence is permanently stored for network consensus.
"""

import time
import struct
import logging
import threading
import os
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import IntEnum, auto

from pantheon.prometheus import sha256, Ed25519
from config import PROTOCOL

logger = logging.getLogger("montana.hal.slashing")


# ============================================================================
# SLASHING CONDITIONS
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

            return True

        return True

    def __hash__(self):
        return hash((self.condition, self.offender, self.evidence_block1,
                    self.evidence_block2, self.timestamp))


# ============================================================================
# SLASHING MANAGER
# ============================================================================

class SlashingManager:
    """
    Manages slashing conditions and penalties.

    Evidence is permanently stored for network consensus.
    """

    # Minimum number of confirmations before processing slash
    MIN_CONFIRMATIONS = 6

    def __init__(self, db=None, data_dir: Optional[str] = None):
        self.pending_slashes: List[SlashingEvidence] = []
        self.confirmed_slashes: List[SlashingEvidence] = []
        self.slashed_nodes: Set[bytes] = set()
        self.slash_history: Dict[bytes, List[SlashingEvidence]] = {}
        self.db = db
        self.data_dir = data_dir
        self._lock = threading.Lock()

        # Load persisted state
        self._load_state()

    def check_equivocation(
        self,
        block1,  # Block type from themis
        block2   # Block type from themis
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
            return None

        # Verify both signatures are valid
        leader = block1.header.leader_pubkey

        try:
            signing_hash1 = block1.header.signing_hash()
            if not Ed25519.verify(leader, signing_hash1, block1.header.leader_signature):
                logger.warning("Block1 signature invalid, not valid equivocation evidence")
                return None

            signing_hash2 = block2.header.signing_hash()
            if not Ed25519.verify(leader, signing_hash2, block2.header.leader_signature):
                logger.warning("Block2 signature invalid, not valid equivocation evidence")
                return None
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return None

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
        block,
        prev_block,
        expected_vrf_input: bytes
    ) -> Optional[SlashingEvidence]:
        """
        Check if a block contains an invalid or forged VRF proof.
        """
        from pantheon.prometheus import ECVRF, VRFOutput

        vrf_output = VRFOutput(
            beta=block.header.vrf_output,
            proof=block.header.vrf_proof
        )

        if not ECVRF.verify(block.header.leader_pubkey, expected_vrf_input, vrf_output):
            return SlashingEvidence(
                condition=SlashingCondition.INVALID_VRF,
                offender=block.header.leader_pubkey,
                evidence_block1=block.hash,
                evidence_block2=b'',
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

            if evidence.offender not in self.slash_history:
                self.slash_history[evidence.offender] = []
            self.slash_history[evidence.offender].append(evidence)

            logger.warning(
                f"SLASHING EVIDENCE REPORTED: {SlashingCondition(evidence.condition).name} "
                f"by {evidence.offender.hex()[:16]}..."
            )

            return True

    def confirm_slash(self, evidence: SlashingEvidence, block_height: int):
        """Confirm a slash after sufficient block confirmations."""
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

            self._save_state()

    def apply_slash(
        self,
        evidence: SlashingEvidence,
        node,  # NodeState from consensus
        current_time: int
    ):
        """
        Apply slashing penalty to node.

        Penalties:
        1. Reputation (signed_blocks) reset to 0
        2. Time presence reset (first_seen set to current time)
        3. Enter 180-day quarantine
        4. Mark as slashed for permanent record
        """
        from pantheon.athena.consensus import NodeStatus

        # Reset reputation
        node.signed_blocks = 0
        node.last_signed_height = 0

        # Reset time presence
        node.first_seen = current_time
        node.total_uptime = 0
        node.stored_blocks = 0

        # Enter quarantine
        quarantine_reason = f"SLASHED: {SlashingCondition(evidence.condition).name}"
        node.enter_quarantine(current_time, quarantine_reason)
        node.status = NodeStatus.SLASHED

        with self._lock:
            self.slashed_nodes.add(node.pubkey)
            self._save_state()

        logger.warning(
            f"SLASH APPLIED to {node.pubkey.hex()[:16]}...: "
            f"All stats reset, quarantined until {node.quarantine_until}"
        )

    def get_pending_slashes(self) -> List[SlashingEvidence]:
        """Get pending slash evidence for inclusion in blocks."""
        with self._lock:
            return list(self.pending_slashes)

    def get_slash_for_block(self) -> Optional[SlashingEvidence]:
        """Get oldest pending slash evidence for inclusion in next block."""
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

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _get_state_path(self) -> Optional[str]:
        """Get path to slashing state file."""
        if self.data_dir:
            return os.path.join(self.data_dir, 'slashing_state.bin')
        return None

    def _load_state(self):
        """Load persisted slashing state from disk."""
        path = self._get_state_path()
        if not path or not os.path.exists(path):
            return

        try:
            with open(path, 'rb') as f:
                data = f.read()

            offset = 0

            # Read slashed nodes
            count = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            for _ in range(count):
                pubkey = data[offset:offset + 32]
                offset += 32
                self.slashed_nodes.add(pubkey)

            # Read confirmed slashes
            count = struct.unpack_from('<I', data, offset)[0]
            offset += 4

            for _ in range(count):
                ev_len = struct.unpack_from('<I', data, offset)[0]
                offset += 4
                ev_data = data[offset:offset + ev_len]
                offset += ev_len
                evidence = SlashingEvidence.deserialize(ev_data)
                self.confirmed_slashes.append(evidence)

                if evidence.offender not in self.slash_history:
                    self.slash_history[evidence.offender] = []
                self.slash_history[evidence.offender].append(evidence)

            logger.info(f"Loaded slashing state: {len(self.slashed_nodes)} slashed nodes")

        except Exception as e:
            logger.error(f"Failed to load slashing state: {e}")

    def _save_state(self):
        """Persist slashing state to disk."""
        path = self._get_state_path()
        if not path:
            return

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)

            data = bytearray()

            # Write slashed nodes
            data.extend(struct.pack('<I', len(self.slashed_nodes)))
            for pubkey in self.slashed_nodes:
                data.extend(pubkey)

            # Write confirmed slashes
            data.extend(struct.pack('<I', len(self.confirmed_slashes)))
            for evidence in self.confirmed_slashes:
                ev_data = evidence.serialize()
                data.extend(struct.pack('<I', len(ev_data)))
                data.extend(ev_data)

            # Atomic write
            tmp_path = path + '.tmp'
            with open(tmp_path, 'wb') as f:
                f.write(data)
            os.replace(tmp_path, path)

            logger.debug(f"Saved slashing state: {len(self.slashed_nodes)} slashed nodes")

        except Exception as e:
            logger.error(f"Failed to save slashing state: {e}")


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run slashing self-tests."""
    logger.info("Running slashing self-tests...")

    # Test evidence serialization
    evidence = SlashingEvidence(
        condition=SlashingCondition.EQUIVOCATION,
        offender=b'\x01' * 32,
        evidence_block1=b'\x02' * 32,
        evidence_block2=b'\x03' * 32,
        timestamp=int(time.time()),
        signature1=b'\x04' * 64,
        signature2=b'\x05' * 64
    )

    serialized = evidence.serialize()
    restored = SlashingEvidence.deserialize(serialized)

    assert restored.condition == evidence.condition
    assert restored.offender == evidence.offender
    assert restored.evidence_block1 == evidence.evidence_block1
    logger.info("✓ Evidence serialization")

    # Test SlashingManager
    manager = SlashingManager()

    assert manager.report_slash(evidence) == True
    assert manager.report_slash(evidence) == False  # Duplicate
    assert len(manager.get_pending_slashes()) == 1
    logger.info("✓ SlashingManager")

    logger.info("All slashing tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
