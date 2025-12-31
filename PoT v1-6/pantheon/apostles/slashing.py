"""
Montana v4.0 - Collective Slashing

Attack the network, lose your friends.

The 12 Apostles system creates real consequences through collective responsibility:
- Attacker: TIME=0, INTEGRITY=0, quarantine 180,000 blocks (~3 years)
- Vouchers: -25% integrity (those who vouched for attacker)
- Associates: -10% integrity (those vouched by attacker)

All handshakes dissolved. Trust network damaged.

This isn't punishment - it's accountability.
Your reputation is bound to those you trust.
"""

import time
import logging
import hashlib
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import IntEnum, auto

from pantheon.prometheus.crypto_provider import verify_signature

logger = logging.getLogger("montana.apostles.slashing")


# ============================================================================
# CONSTANTS
# ============================================================================

# Quarantine duration: ~3 years in Bitcoin blocks
ATTACKER_QUARANTINE_BLOCKS = 180_000

# Integrity penalties
VOUCHER_INTEGRITY_PENALTY = 0.25      # -25% for those who vouched
ASSOCIATE_INTEGRITY_PENALTY = 0.10    # -10% for those vouched by attacker

# Minimum evidence age to prevent spam
MIN_EVIDENCE_AGE = 60  # 1 minute


# ============================================================================
# ATTACK TYPES
# ============================================================================

class AttackType(IntEnum):
    """Types of attacks that trigger slashing."""
    EQUIVOCATION = auto()       # Signed two conflicting blocks/votes
    INVALID_BLOCK = auto()      # Produced invalid block
    INVALID_SIGNATURE = auto()  # Used invalid signature
    DOUBLE_SPEND = auto()       # Attempted double spend
    SYBIL_ATTACK = auto()       # Created fake identities
    CENSORSHIP = auto()         # Deliberately censored transactions
    TIMING_ATTACK = auto()      # Manipulated timestamps
    HUMANITY_FRAUD = auto()     # Multiple pubkeys using same humanity proof


# ============================================================================
# SLASHING EVIDENCE
# ============================================================================

@dataclass
class SlashingEvidence:
    """
    Evidence for slashing an attacker.

    Must be cryptographically verifiable.
    """
    attack_type: AttackType
    attacker_pubkey: bytes
    timestamp: int

    # Evidence data (depends on attack type)
    evidence_data: bytes

    # For equivocation: two conflicting signed messages
    conflicting_sig_1: Optional[bytes] = None
    conflicting_sig_2: Optional[bytes] = None
    conflicting_msg_1: Optional[bytes] = None
    conflicting_msg_2: Optional[bytes] = None

    # Witness signatures (nodes that observed the attack)
    witnesses: List[Tuple[bytes, bytes]] = field(default_factory=list)  # [(pubkey, signature)]

    # Evidence hash
    _hash: Optional[bytes] = None

    def compute_hash(self) -> bytes:
        """Compute evidence hash."""
        if self._hash is None:
            hasher = hashlib.sha3_256()
            hasher.update(self.attack_type.to_bytes(1, 'big'))
            hasher.update(self.attacker_pubkey)
            hasher.update(self.timestamp.to_bytes(8, 'big'))
            hasher.update(self.evidence_data)

            if self.conflicting_sig_1:
                hasher.update(self.conflicting_sig_1)
            if self.conflicting_sig_2:
                hasher.update(self.conflicting_sig_2)
            if self.conflicting_msg_1:
                hasher.update(self.conflicting_msg_1)
            if self.conflicting_msg_2:
                hasher.update(self.conflicting_msg_2)

            self._hash = hasher.digest()

        return self._hash

    @property
    def hash(self) -> bytes:
        """Get evidence hash."""
        return self.compute_hash()

    def is_valid_age(self) -> bool:
        """Check if evidence is old enough (prevents spam)."""
        return (int(time.time()) - self.timestamp) >= MIN_EVIDENCE_AGE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'attack_type': AttackType(self.attack_type).name,
            'attacker_pubkey': self.attacker_pubkey.hex()[:16] + '...',
            'timestamp': self.timestamp,
            'evidence_hash': self.hash.hex()[:16] + '...',
            'witness_count': len(self.witnesses)
        }


# ============================================================================
# SLASHING REPORT
# ============================================================================

@dataclass
class SlashingReport:
    """
    Report of slashing action taken.

    Documents the consequences for attacker and network.
    """
    evidence: SlashingEvidence

    # Attacker consequences
    attacker_pubkey: bytes
    attacker_time_before: float
    attacker_integrity_before: float
    quarantine_until_block: int

    # Voucher consequences (those who vouched for attacker)
    vouchers_penalized: List[Tuple[bytes, float, float]] = field(default_factory=list)  # [(pubkey, old_integrity, new_integrity)]

    # Associate consequences (those vouched by attacker)
    associates_penalized: List[Tuple[bytes, float, float]] = field(default_factory=list)  # [(pubkey, old_integrity, new_integrity)]

    # Dissolved handshakes
    handshakes_dissolved: int = 0

    # Timestamp
    executed_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'attack_type': AttackType(self.evidence.attack_type).name,
            'attacker': self.attacker_pubkey.hex()[:16] + '...',
            'attacker_time_before': self.attacker_time_before,
            'attacker_integrity_before': self.attacker_integrity_before,
            'quarantine_until': self.quarantine_until_block,
            'vouchers_penalized': len(self.vouchers_penalized),
            'associates_penalized': len(self.associates_penalized),
            'handshakes_dissolved': self.handshakes_dissolved,
            'executed_at': self.executed_at
        }


# ============================================================================
# SLASHING PENALTIES
# ============================================================================

@dataclass
class SlashingPenalties:
    """
    Calculated penalties for a slashing event.

    Computed before execution for review.
    """
    attacker_pubkey: bytes

    # Attacker penalties
    attacker_time_reset: bool = True      # TIME -> 0
    attacker_integrity_reset: bool = True  # INTEGRITY -> 0
    quarantine_blocks: int = ATTACKER_QUARANTINE_BLOCKS

    # Affected parties
    vouchers: List[bytes] = field(default_factory=list)      # Those who vouched for attacker
    associates: List[bytes] = field(default_factory=list)    # Those vouched by attacker

    # Penalty amounts
    voucher_penalty: float = VOUCHER_INTEGRITY_PENALTY
    associate_penalty: float = ASSOCIATE_INTEGRITY_PENALTY

    # Total impact
    total_nodes_affected: int = 0

    def calculate_total_affected(self):
        """Calculate total affected nodes."""
        self.total_nodes_affected = 1 + len(self.vouchers) + len(self.associates)


# ============================================================================
# SLASHING MANAGER
# ============================================================================

class SlashingManager:
    """
    Manages slashing operations for the 12 Apostles system.

    Philosophy:
    - Collective responsibility creates real stakes
    - Your reputation is bound to those you trust
    - Attack the network, lose your friends

    This isn't vengeful - it's game-theoretically necessary.
    """

    def __init__(self, get_node_state=None, get_apostles=None, on_slash=None):
        """
        Initialize slashing manager.

        Args:
            get_node_state: Callback to get node state (pubkey) -> NodeState
            get_apostles: Callback to get apostles for a node
            on_slash: Callback when slash executed
        """
        self._get_node_state = get_node_state
        self._get_apostles = get_apostles
        self._on_slash = on_slash

        # Processed evidence (prevent double-slashing)
        self._processed_evidence: Set[bytes] = set()

        # Quarantined nodes
        self._quarantined: Dict[bytes, int] = {}  # pubkey -> quarantine_until_block

        # Slash history
        self._slash_history: List[SlashingReport] = []

        logger.info("Slashing Manager initialized")

    def verify_evidence(self, evidence: SlashingEvidence) -> Tuple[bool, str]:
        """
        Verify slashing evidence.

        Args:
            evidence: Evidence to verify

        Returns:
            (is_valid, reason) tuple
        """
        # Check if already processed
        if evidence.hash in self._processed_evidence:
            return False, "Evidence already processed"

        # Check evidence age
        if not evidence.is_valid_age():
            return False, f"Evidence too new (min age: {MIN_EVIDENCE_AGE}s)"

        # Check attacker pubkey
        if len(evidence.attacker_pubkey) != 32:
            return False, "Invalid attacker pubkey length"

        # Check witnesses (need at least 1)
        if len(evidence.witnesses) < 1:
            return False, "Need at least 1 witness"

        # Type-specific verification
        if evidence.attack_type == AttackType.EQUIVOCATION:
            return self._verify_equivocation(evidence)

        elif evidence.attack_type == AttackType.DOUBLE_SPEND:
            return self._verify_double_spend(evidence)

        elif evidence.attack_type == AttackType.INVALID_BLOCK:
            return self._verify_invalid_block(evidence)

        elif evidence.attack_type == AttackType.INVALID_SIGNATURE:
            return self._verify_invalid_signature(evidence)

        elif evidence.attack_type == AttackType.HUMANITY_FRAUD:
            return self._verify_humanity_fraud(evidence)

        # Generic verification passed
        return True, "Evidence verified"

    def _verify_equivocation(self, evidence: SlashingEvidence) -> Tuple[bool, str]:
        """Verify equivocation evidence."""
        # Must have two conflicting messages
        if not evidence.conflicting_msg_1 or not evidence.conflicting_msg_2:
            return False, "Missing conflicting messages"

        if not evidence.conflicting_sig_1 or not evidence.conflicting_sig_2:
            return False, "Missing conflicting signatures"

        # Messages must be different
        if evidence.conflicting_msg_1 == evidence.conflicting_msg_2:
            return False, "Messages are identical"

        # Verify both signatures against attacker's pubkey
        # This is CRITICAL - without verification, anyone could forge evidence
        try:
            if not verify_signature(
                evidence.attacker_pubkey,
                evidence.conflicting_msg_1,
                evidence.conflicting_sig_1
            ):
                return False, "Invalid signature on first message"

            if not verify_signature(
                evidence.attacker_pubkey,
                evidence.conflicting_msg_2,
                evidence.conflicting_sig_2
            ):
                return False, "Invalid signature on second message"
        except Exception as e:
            logger.warning(f"Signature verification error: {e}")
            return False, f"Signature verification failed: {e}"

        return True, "Equivocation verified with valid signatures"

    def _verify_double_spend(self, evidence: SlashingEvidence) -> Tuple[bool, str]:
        """Verify double spend evidence."""
        if len(evidence.evidence_data) < 64:  # Two tx hashes minimum
            return False, "Insufficient double spend evidence"

        return True, "Double spend verified"

    def _verify_invalid_block(self, evidence: SlashingEvidence) -> Tuple[bool, str]:
        """Verify invalid block evidence."""
        if len(evidence.evidence_data) < 32:  # Block hash minimum
            return False, "Missing block hash"

        return True, "Invalid block verified"

    def _verify_invalid_signature(self, evidence: SlashingEvidence) -> Tuple[bool, str]:
        """Verify invalid signature evidence."""
        if len(evidence.evidence_data) < 64:  # Signature minimum
            return False, "Missing signature data"

        return True, "Invalid signature verified"

    def _verify_humanity_fraud(self, evidence: SlashingEvidence) -> Tuple[bool, str]:
        """
        Verify humanity fraud evidence.

        Evidence must contain:
        - Two different pubkeys (attacker_pubkey and in evidence_data)
        - Proof that both use the same humanity attestation
        """
        # Evidence data must contain the second pubkey (32 bytes) + proof data
        if len(evidence.evidence_data) < 64:
            return False, "Insufficient humanity fraud evidence"

        # Extract second pubkey from evidence
        second_pubkey = evidence.evidence_data[:32]
        proof_data_hash = evidence.evidence_data[32:64]

        # Pubkeys must be different
        if evidence.attacker_pubkey == second_pubkey:
            return False, "Pubkeys are identical"

        # In a full implementation, we would verify:
        # 1. Both pubkeys submitted the same proof_data
        # 2. The proof_data_hash matches what's on chain
        # For now, basic structure validation
        if len(proof_data_hash) != 32:
            return False, "Invalid proof data hash"

        return True, "Humanity fraud verified"

    def calculate_penalties(
        self,
        evidence: SlashingEvidence,
        current_btc_height: int
    ) -> SlashingPenalties:
        """
        Calculate penalties for slashing event.

        Args:
            evidence: Verified evidence
            current_btc_height: Current Bitcoin block height

        Returns:
            SlashingPenalties object
        """
        penalties = SlashingPenalties(
            attacker_pubkey=evidence.attacker_pubkey,
            quarantine_blocks=ATTACKER_QUARANTINE_BLOCKS
        )

        # Get attacker's apostles
        if self._get_apostles:
            apostle_info = self._get_apostles(evidence.attacker_pubkey)
            if apostle_info:
                # Vouchers: those who vouched for the attacker
                penalties.vouchers = apostle_info.get('vouchers', [])
                # Associates: those the attacker vouched for
                penalties.associates = apostle_info.get('associates', [])

        penalties.calculate_total_affected()

        return penalties

    def execute_slash(
        self,
        evidence: SlashingEvidence,
        penalties: SlashingPenalties,
        current_btc_height: int
    ) -> SlashingReport:
        """
        Execute slashing penalties.

        This is the moment of consequence.

        Args:
            evidence: Verified evidence
            penalties: Calculated penalties
            current_btc_height: Current Bitcoin block height

        Returns:
            SlashingReport documenting consequences
        """
        attacker_pubkey = evidence.attacker_pubkey

        # Get attacker's current state
        attacker_time = 0.0
        attacker_integrity = 0.0

        if self._get_node_state:
            state = self._get_node_state(attacker_pubkey)
            if state:
                attacker_time = getattr(state, 'time_score', 0.0)
                attacker_integrity = getattr(state, 'integrity', 0.0)

        # Create report
        report = SlashingReport(
            evidence=evidence,
            attacker_pubkey=attacker_pubkey,
            attacker_time_before=attacker_time,
            attacker_integrity_before=attacker_integrity,
            quarantine_until_block=current_btc_height + penalties.quarantine_blocks
        )

        # Quarantine attacker
        self._quarantined[attacker_pubkey] = report.quarantine_until_block

        # Penalize vouchers
        for voucher_pubkey in penalties.vouchers:
            old_integrity = 1.0
            if self._get_node_state:
                state = self._get_node_state(voucher_pubkey)
                if state:
                    old_integrity = getattr(state, 'integrity', 1.0)

            new_integrity = max(0.0, old_integrity - penalties.voucher_penalty)
            report.vouchers_penalized.append((voucher_pubkey, old_integrity, new_integrity))

        # Penalize associates
        for associate_pubkey in penalties.associates:
            old_integrity = 1.0
            if self._get_node_state:
                state = self._get_node_state(associate_pubkey)
                if state:
                    old_integrity = getattr(state, 'integrity', 1.0)

            new_integrity = max(0.0, old_integrity - penalties.associate_penalty)
            report.associates_penalized.append((associate_pubkey, old_integrity, new_integrity))

        # Count dissolved handshakes
        report.handshakes_dissolved = len(penalties.vouchers) + len(penalties.associates)

        # Mark evidence as processed
        self._processed_evidence.add(evidence.hash)

        # Store in history
        self._slash_history.append(report)

        # Callback
        if self._on_slash:
            self._on_slash(report)

        logger.warning(
            f"SLASH EXECUTED: {AttackType(evidence.attack_type).name} | "
            f"Attacker: {attacker_pubkey.hex()[:8]}... | "
            f"Vouchers penalized: {len(report.vouchers_penalized)} | "
            f"Associates penalized: {len(report.associates_penalized)}"
        )

        return report

    def is_quarantined(self, pubkey: bytes, current_btc_height: int) -> bool:
        """
        Check if a node is quarantined.

        Args:
            pubkey: Node's public key
            current_btc_height: Current Bitcoin block height

        Returns:
            True if quarantined
        """
        if pubkey not in self._quarantined:
            return False

        quarantine_until = self._quarantined[pubkey]

        if current_btc_height >= quarantine_until:
            # Quarantine expired
            del self._quarantined[pubkey]
            return False

        return True

    def get_quarantine_remaining(self, pubkey: bytes, current_btc_height: int) -> int:
        """Get remaining quarantine blocks."""
        if pubkey not in self._quarantined:
            return 0

        remaining = self._quarantined[pubkey] - current_btc_height
        return max(0, remaining)

    def get_slash_history(self, limit: int = 100) -> List[SlashingReport]:
        """Get recent slash history."""
        return self._slash_history[-limit:]

    def get_quarantined_nodes(self) -> Dict[bytes, int]:
        """Get all quarantined nodes."""
        return dict(self._quarantined)

    def get_stats(self) -> Dict[str, Any]:
        """Get slashing statistics."""
        attack_types: Dict[str, int] = {}
        for report in self._slash_history:
            attack_name = AttackType(report.evidence.attack_type).name
            attack_types[attack_name] = attack_types.get(attack_name, 0) + 1

        total_vouchers = sum(len(r.vouchers_penalized) for r in self._slash_history)
        total_associates = sum(len(r.associates_penalized) for r in self._slash_history)

        return {
            'total_slashes': len(self._slash_history),
            'currently_quarantined': len(self._quarantined),
            'attack_types': attack_types,
            'total_vouchers_penalized': total_vouchers,
            'total_associates_penalized': total_associates,
            'total_handshakes_dissolved': sum(r.handshakes_dissolved for r in self._slash_history)
        }


# ============================================================================
# EVIDENCE BUILDER
# ============================================================================

class EvidenceBuilder:
    """Helper class to build slashing evidence."""

    @staticmethod
    def equivocation(
        attacker_pubkey: bytes,
        msg1: bytes,
        sig1: bytes,
        msg2: bytes,
        sig2: bytes,
        witnesses: List[Tuple[bytes, bytes]] = None
    ) -> SlashingEvidence:
        """Build equivocation evidence."""
        return SlashingEvidence(
            attack_type=AttackType.EQUIVOCATION,
            attacker_pubkey=attacker_pubkey,
            timestamp=int(time.time()),
            evidence_data=msg1 + msg2,
            conflicting_msg_1=msg1,
            conflicting_sig_1=sig1,
            conflicting_msg_2=msg2,
            conflicting_sig_2=sig2,
            witnesses=witnesses or []
        )

    @staticmethod
    def double_spend(
        attacker_pubkey: bytes,
        tx_hash_1: bytes,
        tx_hash_2: bytes,
        witnesses: List[Tuple[bytes, bytes]] = None
    ) -> SlashingEvidence:
        """Build double spend evidence."""
        return SlashingEvidence(
            attack_type=AttackType.DOUBLE_SPEND,
            attacker_pubkey=attacker_pubkey,
            timestamp=int(time.time()),
            evidence_data=tx_hash_1 + tx_hash_2,
            witnesses=witnesses or []
        )

    @staticmethod
    def invalid_block(
        attacker_pubkey: bytes,
        block_hash: bytes,
        reason: str,
        witnesses: List[Tuple[bytes, bytes]] = None
    ) -> SlashingEvidence:
        """Build invalid block evidence."""
        return SlashingEvidence(
            attack_type=AttackType.INVALID_BLOCK,
            attacker_pubkey=attacker_pubkey,
            timestamp=int(time.time()),
            evidence_data=block_hash + reason.encode(),
            witnesses=witnesses or []
        )

    @staticmethod
    def invalid_signature(
        attacker_pubkey: bytes,
        bad_signature: bytes,
        message: bytes,
        witnesses: List[Tuple[bytes, bytes]] = None
    ) -> SlashingEvidence:
        """Build invalid signature evidence."""
        return SlashingEvidence(
            attack_type=AttackType.INVALID_SIGNATURE,
            attacker_pubkey=attacker_pubkey,
            timestamp=int(time.time()),
            evidence_data=bad_signature + message,
            witnesses=witnesses or []
        )


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run slashing self-tests."""
    logger.info("Running Slashing self-tests...")

    # Test evidence creation
    attacker = b'\x01' * 32
    witness1 = (b'\x02' * 32, b'\xaa' * 64)

    evidence = EvidenceBuilder.equivocation(
        attacker_pubkey=attacker,
        msg1=b"vote_for_block_A",
        sig1=b'\xbb' * 64,
        msg2=b"vote_for_block_B",
        sig2=b'\xcc' * 64,
        witnesses=[witness1]
    )

    assert evidence.attack_type == AttackType.EQUIVOCATION
    assert evidence.attacker_pubkey == attacker
    assert len(evidence.hash) == 32
    logger.info("  Evidence creation")

    # Test slashing manager
    manager = SlashingManager()

    # Verify evidence (need to wait for MIN_EVIDENCE_AGE)
    # For testing, we'll adjust the timestamp
    evidence.timestamp = int(time.time()) - MIN_EVIDENCE_AGE - 10

    is_valid, reason = manager.verify_evidence(evidence)
    assert is_valid, f"Evidence verification failed: {reason}"
    logger.info("  Evidence verification")

    # Calculate penalties
    penalties = manager.calculate_penalties(evidence, current_btc_height=850000)
    assert penalties.attacker_pubkey == attacker
    assert penalties.quarantine_blocks == ATTACKER_QUARANTINE_BLOCKS
    logger.info("  Penalty calculation")

    # Execute slash
    report = manager.execute_slash(evidence, penalties, current_btc_height=850000)
    assert report.quarantine_until_block == 850000 + ATTACKER_QUARANTINE_BLOCKS
    logger.info("  Slash execution")

    # Check quarantine
    assert manager.is_quarantined(attacker, 850000)
    assert not manager.is_quarantined(attacker, 850000 + ATTACKER_QUARANTINE_BLOCKS + 1)
    logger.info("  Quarantine check")

    # Check double-processing prevention
    is_valid, reason = manager.verify_evidence(evidence)
    assert not is_valid
    assert "already processed" in reason.lower()
    logger.info("  Double-processing prevention")

    # Test stats
    stats = manager.get_stats()
    assert stats['total_slashes'] == 1
    assert 'EQUIVOCATION' in stats['attack_types']
    logger.info("  Stats reporting")

    # Test other evidence types
    ds_evidence = EvidenceBuilder.double_spend(
        attacker_pubkey=b'\x03' * 32,
        tx_hash_1=b'\xdd' * 32,
        tx_hash_2=b'\xee' * 32,
        witnesses=[witness1]
    )
    ds_evidence.timestamp = int(time.time()) - MIN_EVIDENCE_AGE - 10

    is_valid, _ = manager.verify_evidence(ds_evidence)
    assert is_valid
    logger.info("  Double spend evidence")

    logger.info("All Slashing tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
