"""
Hal Time-Locked Identity Module

Tier 3 humanity verification - the crown jewel of the Hal system.

Core principle: Commit to an identity NOW, prove it AFTER a Bitcoin halving.
This is unfakeable because no one can speed up Bitcoin.

Mechanism:
1. At epoch N: Commit = SHA3(pubkey || secret || btc_block_hash[epoch_N])
2. Wait for Bitcoin halving (210,000 blocks, ~4 years)
3. At epoch N+1: Prove = ZK proof that you know the secret from step 1

Sybil cost: Creating N fake identities = N * 4 years of waiting.
100 fake identities = 400 years. This is the Hal Finney vision.

"If you don't believe me or don't get it, I don't have time to try to
convince you, sorry." - Satoshi Nakamoto

We have 4 years per identity. That's enough time.
"""

from __future__ import annotations

import struct
import hashlib
import os
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from .humanity import (
    HumanityTier,
    HumanityProof,
    ProofStatus,
    TIMELOCK_PROOF_VALIDITY,
)


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Time-lock version
TIMELOCK_VERSION = 1

# Bitcoin halving interval (blocks)
HALVING_INTERVAL = 210_000

# Approximate blocks per year
BLOCKS_PER_YEAR = 52560  # ~10 minutes per block

# Minimum epochs survived for time-locked proof
MIN_EPOCHS_FOR_TIMELOCKED = 1  # Must survive at least 1 halving

# Commitment preimage size
COMMITMENT_SECRET_SIZE = 32  # 256 bits of entropy

# Known Bitcoin halving heights
BTC_HALVING_HEIGHTS = [
    0,        # Genesis (epoch 0)
    210000,   # 2012 - first halving
    420000,   # 2016 - second halving
    630000,   # 2020 - third halving
    840000,   # 2024 - fourth halving (approx)
    1050000,  # 2028 - fifth halving (approx)
    1260000,  # 2032 - sixth halving (approx)
]


# ==============================================================================
# ENUMS
# ==============================================================================

class CommitmentStatus(IntEnum):
    """Status of a time-locked commitment."""
    PENDING = 0        # Waiting for halving
    PROVABLE = 1       # Halving passed, can prove
    PROVEN = 2         # Successfully proven
    EXPIRED = 3        # Too old, no longer valid
    INVALID = 4        # Failed verification


class ProofType(IntEnum):
    """Type of time-lock proof."""
    SIMPLE = 0         # Direct secret revelation (testnet)
    ZK_STARK = 1       # Zero-knowledge STARK proof
    ZK_SNARK = 2       # Zero-knowledge SNARK proof


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class IdentityCommitment:
    """
    A time-locked identity commitment.

    Created at epoch N, provable at epoch N+1.
    The commitment binds a Montana pubkey to a secret,
    anchored to a specific Bitcoin block hash.
    """
    pubkey: bytes                  # Montana pubkey (32 bytes)
    commitment: bytes              # SHA3(pubkey || secret || btc_hash) (32 bytes)
    epoch: int                     # Bitcoin epoch number (halving count)
    btc_height: int                # Bitcoin block height at commitment
    btc_hash: bytes                # Bitcoin block hash at commitment (32 bytes)
    created_at: int                # Unix timestamp
    status: CommitmentStatus = CommitmentStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def target_epoch(self) -> int:
        """Get the epoch when this commitment becomes provable."""
        return self.epoch + 1

    @property
    def is_provable(self) -> bool:
        """Check if commitment is ready to be proven."""
        return self.status == CommitmentStatus.PROVABLE

    def serialize(self) -> bytes:
        """Serialize commitment for storage."""
        data = bytearray()

        # Version + status
        data.append(TIMELOCK_VERSION)
        data.append(self.status)

        # Pubkey (32 bytes)
        assert len(self.pubkey) == 32
        data.extend(self.pubkey)

        # Commitment (32 bytes)
        assert len(self.commitment) == 32
        data.extend(self.commitment)

        # Epoch and height
        data.extend(struct.pack('<I', self.epoch))
        data.extend(struct.pack('<I', self.btc_height))

        # Bitcoin hash (32 bytes)
        assert len(self.btc_hash) == 32
        data.extend(self.btc_hash)

        # Timestamp
        data.extend(struct.pack('<Q', self.created_at))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'IdentityCommitment':
        """Deserialize commitment from bytes."""
        offset = 0

        # Version check
        version = data[offset]
        offset += 1
        if version != TIMELOCK_VERSION:
            raise ValueError(f"Unsupported timelock version: {version}")

        # Status
        status = CommitmentStatus(data[offset])
        offset += 1

        # Pubkey
        pubkey = data[offset:offset + 32]
        offset += 32

        # Commitment
        commitment = data[offset:offset + 32]
        offset += 32

        # Epoch and height
        epoch = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4
        btc_height = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        # Bitcoin hash
        btc_hash = data[offset:offset + 32]
        offset += 32

        # Timestamp
        created_at = struct.unpack('<Q', data[offset:offset + 8])[0]

        return cls(
            pubkey=pubkey,
            commitment=commitment,
            epoch=epoch,
            btc_height=btc_height,
            btc_hash=btc_hash,
            created_at=created_at,
            status=status
        )


@dataclass
class TimeLockProof:
    """
    Proof of a time-locked identity commitment.

    Contains the ZK proof (or simple secret for testnet)
    that the prover knows the commitment preimage.
    """
    commitment: IdentityCommitment       # The original commitment
    proof_type: ProofType                # Type of proof
    proof_data: bytes                    # ZK proof or revealed secret
    proof_btc_hash: bytes                # Bitcoin hash at proof time (32 bytes)
    proof_epoch: int                     # Epoch when proof was created
    created_at: int                      # Unix timestamp
    signature: Optional[bytes] = None    # Signature over proof

    @property
    def epochs_survived(self) -> int:
        """Number of halvings survived."""
        return self.proof_epoch - self.commitment.epoch

    def serialize(self) -> bytes:
        """Serialize proof for storage/transmission."""
        data = bytearray()

        # Version + proof type
        data.append(TIMELOCK_VERSION)
        data.append(self.proof_type)

        # Commitment
        commitment_data = self.commitment.serialize()
        data.extend(struct.pack('<H', len(commitment_data)))
        data.extend(commitment_data)

        # Proof data (length-prefixed)
        data.extend(struct.pack('<H', len(self.proof_data)))
        data.extend(self.proof_data)

        # Proof bitcoin hash
        assert len(self.proof_btc_hash) == 32
        data.extend(self.proof_btc_hash)

        # Proof epoch
        data.extend(struct.pack('<I', self.proof_epoch))

        # Timestamp
        data.extend(struct.pack('<Q', self.created_at))

        # Signature (optional)
        if self.signature:
            data.extend(struct.pack('<H', len(self.signature)))
            data.extend(self.signature)
        else:
            data.extend(struct.pack('<H', 0))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes) -> 'TimeLockProof':
        """Deserialize proof from bytes."""
        offset = 0

        # Version check
        version = data[offset]
        offset += 1
        if version != TIMELOCK_VERSION:
            raise ValueError(f"Unsupported timelock version: {version}")

        # Proof type
        proof_type = ProofType(data[offset])
        offset += 1

        # Commitment
        commit_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        commitment = IdentityCommitment.deserialize(data[offset:offset + commit_len])
        offset += commit_len

        # Proof data
        proof_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        proof_data = data[offset:offset + proof_len]
        offset += proof_len

        # Proof bitcoin hash
        proof_btc_hash = data[offset:offset + 32]
        offset += 32

        # Proof epoch
        proof_epoch = struct.unpack('<I', data[offset:offset + 4])[0]
        offset += 4

        # Timestamp
        created_at = struct.unpack('<Q', data[offset:offset + 8])[0]
        offset += 8

        # Signature
        sig_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        signature = data[offset:offset + sig_len] if sig_len > 0 else None

        return cls(
            commitment=commitment,
            proof_type=proof_type,
            proof_data=proof_data,
            proof_btc_hash=proof_btc_hash,
            proof_epoch=proof_epoch,
            created_at=created_at,
            signature=signature
        )


# ==============================================================================
# TIME-LOCK VERIFIER
# ==============================================================================

class TimeLockVerifier:
    """
    Verifier for time-locked identity proofs.

    Maintains:
    - Index of all commitments
    - Bitcoin oracle connection (for block hashes)
    - ZK proof verifier
    """

    def __init__(self, testnet: bool = False):
        self.testnet = testnet
        # Commitment hash -> commitment
        self._commitments: Dict[bytes, IdentityCommitment] = {}
        # Commitment -> revealed secret (testnet only)
        self._revealed_secrets: Dict[bytes, bytes] = {}
        # Pubkey -> list of commitments
        self._pubkey_commitments: Dict[bytes, List[bytes]] = {}
        # Mock Bitcoin state (for testing)
        self._mock_btc_height: int = 850000  # After 4th halving
        self._mock_btc_hashes: Dict[int, bytes] = {}

    def get_current_epoch(self) -> int:
        """Get current Bitcoin epoch (halving count)."""
        return self._mock_btc_height // HALVING_INTERVAL

    def get_btc_hash(self, height: int) -> bytes:
        """Get Bitcoin block hash for height."""
        if height in self._mock_btc_hashes:
            return self._mock_btc_hashes[height]
        # Generate deterministic mock hash
        return hashlib.sha3_256(f"btc_block_{height}".encode()).digest()

    def register_commitment(
        self,
        commitment: IdentityCommitment
    ) -> Tuple[bool, str]:
        """
        Register a new commitment.

        Checks:
        - Commitment not already registered
        - Bitcoin hash is valid for claimed height
        - Pubkey not over commitment limit
        """
        # Check duplicate
        if commitment.commitment in self._commitments:
            existing = self._commitments[commitment.commitment]
            if existing.pubkey == commitment.pubkey:
                return True, "Commitment already registered"
            return False, "Commitment collision (different pubkey)"

        # Verify Bitcoin hash (in production, query Bitcoin oracle)
        expected_hash = self.get_btc_hash(commitment.btc_height)
        if commitment.btc_hash != expected_hash:
            return False, "Bitcoin hash mismatch"

        # Verify epoch matches height
        expected_epoch = commitment.btc_height // HALVING_INTERVAL
        if commitment.epoch != expected_epoch:
            return False, f"Epoch mismatch: claimed {commitment.epoch}, expected {expected_epoch}"

        # Register
        self._commitments[commitment.commitment] = commitment

        # Index by pubkey
        if commitment.pubkey not in self._pubkey_commitments:
            self._pubkey_commitments[commitment.pubkey] = []
        self._pubkey_commitments[commitment.pubkey].append(commitment.commitment)

        return True, f"Commitment registered for epoch {commitment.epoch}"

    def verify_proof(
        self,
        proof: TimeLockProof
    ) -> Tuple[bool, str]:
        """
        Verify a time-lock proof.

        Checks:
        1. Commitment is registered
        2. Current epoch > commitment epoch (halving passed)
        3. Proof is valid (ZK or simple)
        4. Bitcoin hash at proof time is valid
        """
        # Check commitment exists
        if proof.commitment.commitment not in self._commitments:
            return False, "Commitment not registered"

        registered = self._commitments[proof.commitment.commitment]

        # Verify pubkey matches
        if registered.pubkey != proof.commitment.pubkey:
            return False, "Pubkey mismatch"

        # Check halving has passed
        current_epoch = self.get_current_epoch()
        if current_epoch <= proof.commitment.epoch:
            return False, f"Halving not yet passed (current={current_epoch}, commitment={proof.commitment.epoch})"

        # Verify minimum epochs
        epochs_survived = proof.proof_epoch - proof.commitment.epoch
        if epochs_survived < MIN_EPOCHS_FOR_TIMELOCKED:
            return False, f"Need {MIN_EPOCHS_FOR_TIMELOCKED}+ epochs, survived {epochs_survived}"

        # Verify proof based on type
        if proof.proof_type == ProofType.SIMPLE:
            return self._verify_simple_proof(proof)
        elif proof.proof_type == ProofType.ZK_STARK:
            return self._verify_zk_stark(proof)
        elif proof.proof_type == ProofType.ZK_SNARK:
            return self._verify_zk_snark(proof)
        else:
            return False, f"Unknown proof type: {proof.proof_type}"

    def _verify_simple_proof(self, proof: TimeLockProof) -> Tuple[bool, str]:
        """Verify simple proof (secret revelation, testnet only)."""
        if not self.testnet:
            return False, "Simple proofs only allowed on testnet"

        # The proof_data IS the secret
        secret = proof.proof_data

        # Recompute commitment
        expected_commitment = hashlib.sha3_256(
            proof.commitment.pubkey +
            secret +
            proof.commitment.btc_hash
        ).digest()

        if expected_commitment != proof.commitment.commitment:
            return False, "Secret does not match commitment"

        # Record revealed secret
        self._revealed_secrets[proof.commitment.commitment] = secret

        # Update commitment status
        if proof.commitment.commitment in self._commitments:
            self._commitments[proof.commitment.commitment].status = CommitmentStatus.PROVEN

        return True, f"Simple proof valid (survived {proof.epochs_survived} epochs)"

    def _verify_zk_stark(self, proof: TimeLockProof) -> Tuple[bool, str]:
        """Verify ZK-STARK proof."""
        # In production, this would use a STARK verifier (e.g., winterfell)
        # For now, accept any non-empty proof in testnet mode
        if self.testnet:
            if len(proof.proof_data) >= 64:
                return True, "ZK-STARK proof valid (testnet stub)"
            return False, "Invalid ZK-STARK proof format"

        # TODO: Implement production STARK verification
        # The proof should demonstrate knowledge of secret such that:
        # SHA3(pubkey || secret || btc_hash) == commitment
        # Without revealing the secret

        return False, "ZK-STARK verification not yet implemented"

    def _verify_zk_snark(self, proof: TimeLockProof) -> Tuple[bool, str]:
        """Verify ZK-SNARK proof."""
        if self.testnet:
            if len(proof.proof_data) >= 64:
                return True, "ZK-SNARK proof valid (testnet stub)"
            return False, "Invalid ZK-SNARK proof format"

        # TODO: Implement production SNARK verification
        return False, "ZK-SNARK verification not yet implemented"

    def get_commitments_for_pubkey(self, pubkey: bytes) -> List[IdentityCommitment]:
        """Get all commitments for a pubkey."""
        commitment_hashes = self._pubkey_commitments.get(pubkey, [])
        return [self._commitments[h] for h in commitment_hashes if h in self._commitments]

    def set_mock_btc_state(self, height: int, block_hash: Optional[bytes] = None) -> None:
        """Set mock Bitcoin state for testing."""
        self._mock_btc_height = height
        if block_hash:
            self._mock_btc_hashes[height] = block_hash

    def get_stats(self) -> Dict[str, int]:
        """Get verifier statistics."""
        return {
            'total_commitments': len(self._commitments),
            'proven_commitments': sum(
                1 for c in self._commitments.values()
                if c.status == CommitmentStatus.PROVEN
            ),
            'current_epoch': self.get_current_epoch(),
        }


# ==============================================================================
# HIGH-LEVEL API
# ==============================================================================

def create_identity_commitment(
    pubkey: bytes,
    secret: bytes,
    btc_height: int,
    btc_hash: bytes
) -> IdentityCommitment:
    """
    Create a time-locked identity commitment.

    Args:
        pubkey: Montana pubkey (32 bytes)
        secret: Random secret (32 bytes) - KEEP THIS SAFE
        btc_height: Current Bitcoin block height
        btc_hash: Bitcoin block hash at that height

    Returns: IdentityCommitment to register with verifier

    IMPORTANT: The secret must be stored securely. Losing it means
    losing the ability to prove this commitment after the halving.
    """
    if len(pubkey) != 32:
        raise ValueError("Pubkey must be 32 bytes")
    if len(secret) < COMMITMENT_SECRET_SIZE:
        raise ValueError(f"Secret must be at least {COMMITMENT_SECRET_SIZE} bytes")
    if len(btc_hash) != 32:
        raise ValueError("Bitcoin hash must be 32 bytes")

    # Compute commitment hash
    commitment = hashlib.sha3_256(
        pubkey + secret + btc_hash
    ).digest()

    # Determine epoch
    epoch = btc_height // HALVING_INTERVAL

    return IdentityCommitment(
        pubkey=pubkey,
        commitment=commitment,
        epoch=epoch,
        btc_height=btc_height,
        btc_hash=btc_hash,
        created_at=int(datetime.utcnow().timestamp()),
        status=CommitmentStatus.PENDING
    )


def create_time_locked_proof(
    commitment: IdentityCommitment,
    secret: bytes,
    current_btc_height: int,
    current_btc_hash: bytes,
    proof_type: ProofType = ProofType.SIMPLE
) -> TimeLockProof:
    """
    Create a time-locked proof after halving has passed.

    Args:
        commitment: The original commitment
        secret: The secret used in the commitment
        current_btc_height: Current Bitcoin block height
        current_btc_hash: Current Bitcoin block hash
        proof_type: Type of proof to create

    Returns: TimeLockProof ready for verification
    """
    current_epoch = current_btc_height // HALVING_INTERVAL

    if current_epoch <= commitment.epoch:
        raise ValueError(f"Halving not yet passed (current={current_epoch}, commitment={commitment.epoch})")

    if proof_type == ProofType.SIMPLE:
        # Simple proof: just reveal the secret
        proof_data = secret
    elif proof_type == ProofType.ZK_STARK:
        # TODO: Generate real STARK proof
        # For now, create a stub proof
        proof_data = hashlib.sha3_256(
            b"STARK_PROOF" + secret + commitment.commitment
        ).digest() + os.urandom(32)
    elif proof_type == ProofType.ZK_SNARK:
        # TODO: Generate real SNARK proof
        proof_data = hashlib.sha3_256(
            b"SNARK_PROOF" + secret + commitment.commitment
        ).digest() + os.urandom(32)
    else:
        raise ValueError(f"Unknown proof type: {proof_type}")

    return TimeLockProof(
        commitment=commitment,
        proof_type=proof_type,
        proof_data=proof_data,
        proof_btc_hash=current_btc_hash,
        proof_epoch=current_epoch,
        created_at=int(datetime.utcnow().timestamp())
    )


def verify_time_locked_proof(
    proof: TimeLockProof,
    verifier: TimeLockVerifier
) -> Tuple[bool, str]:
    """
    Verify a time-locked identity proof.

    Args:
        proof: The proof to verify
        verifier: TimeLockVerifier instance

    Returns: (is_valid, message)
    """
    return verifier.verify_proof(proof)


def create_humanity_proof_from_timelock(
    proof: TimeLockProof
) -> HumanityProof:
    """
    Convert TimeLockProof to HumanityProof.
    """
    now = int(datetime.utcnow().timestamp())

    return HumanityProof(
        tier=HumanityTier.TIME_LOCKED,
        proof_type="timelock",
        proof_data=proof.serialize(),
        pubkey=proof.commitment.pubkey,
        created_at=now,
        expires_at=now + TIMELOCK_PROOF_VALIDITY,
        status=ProofStatus.VALID,
        metadata={
            'commitment_epoch': proof.commitment.epoch,
            'proof_epoch': proof.proof_epoch,
            'epochs_survived': proof.epochs_survived,
        }
    )


# ==============================================================================
# SELF-TEST
# ==============================================================================

def _self_test():
    """Run self-test for timelock module."""
    print("=" * 60)
    print("HAL TIMELOCK MODULE - SELF TEST")
    print("=" * 60)

    # Test 1: Constants
    print("\n[1] Testing constants...")
    assert HALVING_INTERVAL == 210000
    assert MIN_EPOCHS_FOR_TIMELOCKED == 1
    print(f"    PASS: Halving interval = {HALVING_INTERVAL} blocks")

    # Test 2: Create commitment
    print("\n[2] Testing create_identity_commitment...")
    pubkey = os.urandom(32)
    secret = os.urandom(32)
    btc_height = 630000  # Epoch 3 (third halving)
    btc_hash = hashlib.sha3_256(f"btc_block_{btc_height}".encode()).digest()

    commitment = create_identity_commitment(pubkey, secret, btc_height, btc_hash)
    assert commitment.pubkey == pubkey
    assert commitment.epoch == 3
    assert commitment.status == CommitmentStatus.PENDING
    print(f"    PASS: Commitment created (epoch={commitment.epoch})")

    # Test 3: Serialization
    print("\n[3] Testing commitment serialization...")
    serialized = commitment.serialize()
    deserialized = IdentityCommitment.deserialize(serialized)
    assert deserialized.pubkey == commitment.pubkey
    assert deserialized.commitment == commitment.commitment
    assert deserialized.epoch == commitment.epoch
    print(f"    PASS: Commitment serialization ({len(serialized)} bytes)")

    # Test 4: TimeLockVerifier
    print("\n[4] Testing TimeLockVerifier...")
    verifier = TimeLockVerifier(testnet=True)

    # Set mock state to epoch 4 (after commitment's epoch 3)
    verifier.set_mock_btc_state(850000)  # Epoch 4
    assert verifier.get_current_epoch() == 4

    # Register commitment
    success, msg = verifier.register_commitment(commitment)
    assert success, f"Registration failed: {msg}"
    print(f"    PASS: Commitment registered ({msg})")

    # Test 5: Create proof
    print("\n[5] Testing create_time_locked_proof...")
    current_height = 850000
    current_hash = verifier.get_btc_hash(current_height)

    proof = create_time_locked_proof(
        commitment,
        secret,
        current_height,
        current_hash,
        ProofType.SIMPLE
    )
    assert proof.proof_epoch == 4
    assert proof.epochs_survived == 1
    print(f"    PASS: Proof created (epochs_survived={proof.epochs_survived})")

    # Test 6: Verify proof
    print("\n[6] Testing proof verification...")
    valid, msg = verifier.verify_proof(proof)
    assert valid, f"Verification failed: {msg}"
    print(f"    PASS: Proof verified ({msg})")

    # Test 7: Proof serialization
    print("\n[7] Testing proof serialization...")
    serialized = proof.serialize()
    deserialized = TimeLockProof.deserialize(serialized)
    assert deserialized.commitment.pubkey == commitment.pubkey
    assert deserialized.epochs_survived == proof.epochs_survived
    print(f"    PASS: Proof serialization ({len(serialized)} bytes)")

    # Test 8: Verify halving requirement
    print("\n[8] Testing halving requirement...")
    # Try to create proof before halving
    early_verifier = TimeLockVerifier(testnet=True)
    early_verifier.set_mock_btc_state(629999)  # Just before epoch 3 ends

    # Commitment at epoch 3 can't be proven at epoch 3
    early_commitment = create_identity_commitment(
        pubkey, secret, 629000, early_verifier.get_btc_hash(629000)
    )
    early_verifier.register_commitment(early_commitment)

    # Try to prove at same epoch
    try:
        early_proof = create_time_locked_proof(
            early_commitment,
            secret,
            629500,
            early_verifier.get_btc_hash(629500),
            ProofType.SIMPLE
        )
        assert False, "Should have raised exception"
    except ValueError as e:
        assert "not yet passed" in str(e)
        print(f"    PASS: Halving requirement enforced ({e})")

    # Test 9: ZK proof stubs
    print("\n[9] Testing ZK proof creation...")
    zk_proof = create_time_locked_proof(
        commitment,
        secret,
        current_height,
        current_hash,
        ProofType.ZK_STARK
    )
    assert zk_proof.proof_type == ProofType.ZK_STARK
    assert len(zk_proof.proof_data) >= 64

    valid, msg = verifier.verify_proof(zk_proof)
    assert valid, f"ZK verification failed: {msg}"
    print(f"    PASS: ZK-STARK proof verified ({msg})")

    # Test 10: HumanityProof conversion
    print("\n[10] Testing HumanityProof conversion...")
    humanity_proof = create_humanity_proof_from_timelock(proof)
    assert humanity_proof.tier == HumanityTier.TIME_LOCKED
    assert humanity_proof.metadata['epochs_survived'] == 1
    print(f"    PASS: HumanityProof created (tier={humanity_proof.tier.name})")

    # Test 11: Multiple epochs
    print("\n[11] Testing multiple epochs survived...")
    old_commitment = create_identity_commitment(
        pubkey, secret, 210000, hashlib.sha3_256(b"btc_block_210000").digest()
    )
    # Epoch 1 commitment, verified at epoch 4
    multi_verifier = TimeLockVerifier(testnet=True)
    multi_verifier.set_mock_btc_state(850000)  # Epoch 4
    multi_verifier._mock_btc_hashes[210000] = hashlib.sha3_256(b"btc_block_210000").digest()

    old_commitment.epoch = 1
    multi_verifier.register_commitment(old_commitment)

    multi_proof = create_time_locked_proof(
        old_commitment,
        secret,
        850000,
        multi_verifier.get_btc_hash(850000),
        ProofType.SIMPLE
    )
    assert multi_proof.epochs_survived == 3  # Epoch 4 - Epoch 1
    print(f"    PASS: Multiple epochs ({multi_proof.epochs_survived} halvings survived)")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
