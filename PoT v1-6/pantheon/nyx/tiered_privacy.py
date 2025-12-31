"""
Proof of Time - Tiered Privacy Model
Privacy tiers T0-T1 for balanced throughput and privacy.

Based on: ProofOfTime_DAG_Addendum.pdf Section 12

PRODUCTION:
- T0 (Public): Addresses + amounts visible (~250 B, ~0.5 ms verify, 1× fee)
- T1 (Stealth): One-time addresses, amounts visible (~400 B, ~1 ms verify, 2× fee)

Time is the ultimate proof.
"""

import struct
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import IntEnum

from pantheon.prometheus import sha256d
from pantheon.nyx.privacy import StealthAddress
from config import PROTOCOL

logger = logging.getLogger("proof_of_time.tiered_privacy")


# ============================================================================
# PRIVACY TIERS
# ============================================================================

class PrivacyTier(IntEnum):
    """
    Privacy tier enumeration.

    Higher tier = more privacy = larger size = higher fee.
    """
    T0_PUBLIC = 0   # Addresses + amounts visible
    T1_STEALTH = 1  # One-time addresses, amounts visible


# Tier specifications from spec
TIER_SPECS = {
    PrivacyTier.T0_PUBLIC: {
        'name': 'Public',
        'size_bytes': 250,
        'verify_time_ms': 0.5,
        'fee_multiplier': 1,
        'description': 'Addresses and amounts visible on-chain'
    },
    PrivacyTier.T1_STEALTH: {
        'name': 'Stealth',
        'size_bytes': 400,
        'verify_time_ms': 1,
        'fee_multiplier': 2,
        'description': 'One-time addresses, amounts visible'
    },
}


# ============================================================================
# TIERED TRANSACTION OUTPUT
# ============================================================================

@dataclass
class TieredOutput:
    """
    Transaction output with privacy tier.

    Structure varies by tier:
    - T0: address + amount (public)
    - T1: one_time_address + tx_public_key + amount
    """
    tier: PrivacyTier = PrivacyTier.T0_PUBLIC

    # T0: Public address and amount
    public_address: bytes = b''
    public_amount: int = 0

    # T1: Stealth address components
    one_time_address: bytes = b''
    tx_public_key: bytes = b''
    visible_amount: int = 0

    # Output index
    output_index: int = 0

    def get_fee_multiplier(self) -> int:
        """Get fee multiplier for this tier."""
        return TIER_SPECS[self.tier]['fee_multiplier']

    def estimate_size(self) -> int:
        """Estimate serialized size."""
        return TIER_SPECS[self.tier]['size_bytes']

    def serialize(self) -> bytes:
        """Serialize tiered output."""
        data = bytearray()

        # Tier
        data.extend(struct.pack('<B', self.tier))

        if self.tier == PrivacyTier.T0_PUBLIC:
            # Public: address (32) + amount (8)
            data.extend(self.public_address)
            data.extend(struct.pack('<Q', self.public_amount))

        elif self.tier == PrivacyTier.T1_STEALTH:
            # Stealth: one_time_address (32) + tx_pub (32) + amount (8)
            data.extend(self.one_time_address)
            data.extend(self.tx_public_key)
            data.extend(struct.pack('<Q', self.visible_amount))

        # Output index
        data.extend(struct.pack('<I', self.output_index))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['TieredOutput', int]:
        """Deserialize tiered output."""
        tier = PrivacyTier(data[offset])
        offset += 1

        output = cls(tier=tier)

        if tier == PrivacyTier.T0_PUBLIC:
            output.public_address = data[offset:offset + 32]
            offset += 32
            output.public_amount = struct.unpack_from('<Q', data, offset)[0]
            offset += 8

        elif tier == PrivacyTier.T1_STEALTH:
            output.one_time_address = data[offset:offset + 32]
            offset += 32
            output.tx_public_key = data[offset:offset + 32]
            offset += 32
            output.visible_amount = struct.unpack_from('<Q', data, offset)[0]
            offset += 8

        output.output_index = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        return output, offset


# ============================================================================
# TIERED TRANSACTION INPUT
# ============================================================================

@dataclass
class TieredInput:
    """
    Transaction input with privacy tier.

    - T0: Simple UTXO reference + signature
    - T1: UTXO reference (stealth doesn't affect input structure)
    """
    tier: PrivacyTier = PrivacyTier.T0_PUBLIC

    # UTXO reference
    prev_txid: bytes = b''
    prev_output_index: int = 0

    # T0: Public signature
    signature: bytes = b''

    def serialize(self) -> bytes:
        """Serialize tiered input."""
        data = bytearray()

        # Tier
        data.extend(struct.pack('<B', self.tier))

        # UTXO reference
        data.extend(self.prev_txid)
        data.extend(struct.pack('<I', self.prev_output_index))

        if self.tier == PrivacyTier.T0_PUBLIC:
            data.extend(self.signature)

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['TieredInput', int]:
        """Deserialize tiered input."""
        tier = PrivacyTier(data[offset])
        offset += 1

        inp = cls(tier=tier)

        inp.prev_txid = data[offset:offset + 32]
        offset += 32
        inp.prev_output_index = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        if tier == PrivacyTier.T0_PUBLIC:
            inp.signature = data[offset:offset + 64]
            offset += 64

        return inp, offset


# ============================================================================
# TIERED TRANSACTION
# ============================================================================

@dataclass
class TieredTransaction:
    """
    Transaction with tiered privacy (T0/T1).

    Rules:
    - Outputs can be any tier ≥ input tier
    - T0 → T1 is valid
    - T1 → T0 is INVALID (cannot downgrade privacy)
    - Fee is always public
    """
    version: int = PROTOCOL.PROTOCOL_VERSION

    inputs: List[TieredInput] = field(default_factory=list)
    outputs: List[TieredOutput] = field(default_factory=list)

    # Fee is always public
    fee: int = 0

    # Extra data
    extra: bytes = b''

    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)

    def get_input_tier(self) -> PrivacyTier:
        """Get highest privacy tier among inputs."""
        if not self.inputs:
            return PrivacyTier.T0_PUBLIC
        return max(inp.tier for inp in self.inputs)

    def get_output_tier(self) -> PrivacyTier:
        """Get highest privacy tier among outputs."""
        if not self.outputs:
            return PrivacyTier.T0_PUBLIC
        return max(out.tier for out in self.outputs)

    def validate_tier_rules(self) -> Tuple[bool, str]:
        """
        Validate cross-tier rules.

        - Outputs must be ≥ input tier
        - Cannot downgrade privacy
        """
        input_tier = self.get_input_tier()

        for i, output in enumerate(self.outputs):
            if output.tier < input_tier:
                return False, f"Output {i} tier {output.tier.name} < input tier {input_tier.name}"

        return True, "OK"

    def calculate_fee(self, base_fee: int = PROTOCOL.MIN_FEE) -> int:
        """
        Calculate required fee based on tiers.

        Fee = base_fee × max(tier_multipliers)
        """
        max_multiplier = 1

        for out in self.outputs:
            max_multiplier = max(max_multiplier, out.get_fee_multiplier())

        return base_fee * max_multiplier

    def estimate_size(self) -> int:
        """Estimate transaction size."""
        size = 2 + 8  # version + fee

        for inp in self.inputs:
            if inp.tier == PrivacyTier.T0_PUBLIC:
                size += 100  # txid + index + signature
            elif inp.tier == PrivacyTier.T1_STEALTH:
                size += 36  # txid + index

        for out in self.outputs:
            size += out.estimate_size()

        size += len(self.extra)

        return size

    def hash(self) -> bytes:
        """Compute transaction hash."""
        if self._hash is None:
            self._hash = sha256d(self.serialize())
        return self._hash

    def serialize(self) -> bytes:
        """Serialize transaction."""
        from pantheon.themis.structures import write_varint, write_bytes

        data = bytearray()

        # Version
        data.extend(struct.pack('<H', self.version))

        # Inputs
        data.extend(write_varint(len(self.inputs)))
        for inp in self.inputs:
            data.extend(inp.serialize())

        # Outputs
        data.extend(write_varint(len(self.outputs)))
        for out in self.outputs:
            data.extend(out.serialize())

        # Fee
        data.extend(struct.pack('<Q', self.fee))

        # Extra
        data.extend(write_bytes(self.extra))

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['TieredTransaction', int]:
        """Deserialize transaction."""
        from pantheon.themis.structures import read_varint, read_bytes

        version = struct.unpack_from('<H', data, offset)[0]
        offset += 2

        # Inputs
        num_inputs, offset = read_varint(data, offset)
        inputs = []
        for _ in range(num_inputs):
            inp, offset = TieredInput.deserialize(data, offset)
            inputs.append(inp)

        # Outputs
        num_outputs, offset = read_varint(data, offset)
        outputs = []
        for _ in range(num_outputs):
            out, offset = TieredOutput.deserialize(data, offset)
            outputs.append(out)

        # Fee
        fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        # Extra
        extra, offset = read_bytes(data, offset)

        return cls(
            version=version,
            inputs=inputs,
            outputs=outputs,
            fee=fee,
            extra=extra
        ), offset


# ============================================================================
# TIERED TRANSACTION BUILDER
# ============================================================================

class TieredTransactionBuilder:
    """
    Builder for creating tiered transactions (T0/T1).
    """

    def __init__(self, default_tier: PrivacyTier = PrivacyTier.T1_STEALTH):
        self.default_tier = default_tier
        self.inputs: List[TieredInput] = []
        self.outputs: List[TieredOutput] = []
        self.fee: int = 0

    def add_public_output(
        self,
        address: bytes,
        amount: int
    ) -> 'TieredTransactionBuilder':
        """Add T0 (public) output."""
        output = TieredOutput(
            tier=PrivacyTier.T0_PUBLIC,
            public_address=address,
            public_amount=amount,
            output_index=len(self.outputs)
        )
        self.outputs.append(output)
        return self

    def add_public_input(
        self,
        prev_txid: bytes,
        prev_index: int
    ) -> 'TieredTransactionBuilder':
        """Add T0 (public) input."""
        inp = TieredInput(
            tier=PrivacyTier.T0_PUBLIC,
            prev_txid=prev_txid,
            prev_output_index=prev_index
        )
        self.inputs.append(inp)
        return self

    def add_stealth_output(
        self,
        view_public: bytes,
        spend_public: bytes,
        amount: int
    ) -> 'TieredTransactionBuilder':
        """
        Add T1 (stealth) output.

        Creates one-time address using Diffie-Hellman:
        R = r·G (ephemeral public key)
        P' = H(r·A)·G + B (one-time address)
        """
        # Create stealth output
        stealth_out, _ = StealthAddress.create_output(view_public, spend_public)

        output = TieredOutput(
            tier=PrivacyTier.T1_STEALTH,
            one_time_address=stealth_out.one_time_address,
            tx_public_key=stealth_out.tx_public_key,
            visible_amount=amount,
            output_index=len(self.outputs)
        )
        self.outputs.append(output)
        return self

    def add_stealth_input(
        self,
        prev_txid: bytes,
        prev_index: int
    ) -> 'TieredTransactionBuilder':
        """Add T1 (stealth) input."""
        inp = TieredInput(
            tier=PrivacyTier.T1_STEALTH,
            prev_txid=prev_txid,
            prev_output_index=prev_index
        )
        self.inputs.append(inp)
        return self

    def set_fee(self, fee: int) -> 'TieredTransactionBuilder':
        """Set transaction fee."""
        self.fee = fee
        return self

    def build(self) -> TieredTransaction:
        """Build the transaction."""
        tx = TieredTransaction(
            inputs=self.inputs,
            outputs=self.outputs,
            fee=self.fee
        )

        # Validate tier rules
        valid, reason = tx.validate_tier_rules()
        if not valid:
            raise ValueError(f"Invalid tier transition: {reason}")

        return tx


# ============================================================================
# TIER VALIDATOR
# ============================================================================

class TierValidator:
    """
    Validates tiered transactions (T0/T1).
    """

    @staticmethod
    def validate_t0_output(output: TieredOutput) -> bool:
        """Validate T0 output."""
        if len(output.public_address) != 32:
            return False
        if output.public_amount < 0:
            return False
        return True

    @staticmethod
    def validate_t1_output(output: TieredOutput) -> bool:
        """Validate T1 output."""
        if len(output.one_time_address) != 32:
            return False
        if len(output.tx_public_key) != 32:
            return False
        if output.visible_amount < 0:
            return False
        return True

    @classmethod
    def validate_transaction(
        cls,
        tx: TieredTransaction,
        spent_key_images: set = None
    ) -> Tuple[bool, str]:
        """
        Validate complete tiered transaction.
        """
        # Validate tier rules
        valid, reason = tx.validate_tier_rules()
        if not valid:
            return False, reason

        # Validate outputs
        for i, output in enumerate(tx.outputs):
            if output.tier == PrivacyTier.T0_PUBLIC:
                if not cls.validate_t0_output(output):
                    return False, f"Invalid T0 output {i}"
            elif output.tier == PrivacyTier.T1_STEALTH:
                if not cls.validate_t1_output(output):
                    return False, f"Invalid T1 output {i}"

        # Validate fee
        required_fee = tx.calculate_fee()
        if tx.fee < required_fee:
            return False, f"Fee {tx.fee} < required {required_fee}"

        return True, "OK"


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run tiered privacy self-tests."""
    logger.info("Running tiered privacy self-tests...")

    # Test tier specs
    assert TIER_SPECS[PrivacyTier.T0_PUBLIC]['fee_multiplier'] == 1
    assert TIER_SPECS[PrivacyTier.T1_STEALTH]['fee_multiplier'] == 2
    logger.info("✓ Tier specifications")

    # Test T0 output
    t0_out = TieredOutput(
        tier=PrivacyTier.T0_PUBLIC,
        public_address=b'\x01' * 32,
        public_amount=1000
    )
    data = t0_out.serialize()
    restored, _ = TieredOutput.deserialize(data)
    assert restored.tier == PrivacyTier.T0_PUBLIC
    assert restored.public_amount == 1000
    logger.info("✓ T0 output serialization")

    # Test T1 output
    t1_out = TieredOutput(
        tier=PrivacyTier.T1_STEALTH,
        one_time_address=b'\x02' * 32,
        tx_public_key=b'\x03' * 32,
        visible_amount=2000
    )
    data = t1_out.serialize()
    restored, _ = TieredOutput.deserialize(data)
    assert restored.tier == PrivacyTier.T1_STEALTH
    assert restored.visible_amount == 2000
    logger.info("✓ T1 output serialization")

    # Test tier validation
    builder = TieredTransactionBuilder()
    builder.add_public_output(b'\x01' * 32, 1000)
    builder.set_fee(PROTOCOL.MIN_FEE)
    tx = builder.build()

    valid, reason = TierValidator.validate_transaction(tx)
    assert valid, reason
    logger.info("✓ Transaction tier validation")

    # Test tier upgrade rule (T0 → T1)
    builder2 = TieredTransactionBuilder()
    builder2.inputs.append(TieredInput(tier=PrivacyTier.T0_PUBLIC))
    builder2.outputs.append(TieredOutput(tier=PrivacyTier.T1_STEALTH))

    valid, _ = builder2.build().validate_tier_rules()
    assert valid, "T0 → T1 should be valid"
    logger.info("✓ Tier upgrade allowed (T0 → T1)")

    # Test tier downgrade blocked (T1 → T0)
    builder3 = TieredTransactionBuilder()
    builder3.inputs.append(TieredInput(tier=PrivacyTier.T1_STEALTH))
    builder3.outputs.append(TieredOutput(tier=PrivacyTier.T0_PUBLIC))

    try:
        builder3.build()
        assert False, "T1 → T0 should be invalid"
    except ValueError:
        pass
    logger.info("✓ Tier downgrade blocked (T1 → T0)")

    # Test fee calculation
    builder4 = TieredTransactionBuilder()
    builder4.outputs.append(TieredOutput(tier=PrivacyTier.T1_STEALTH))

    tx = TieredTransaction(outputs=builder4.outputs)
    required_fee = tx.calculate_fee(base_fee=10)
    assert required_fee == 20  # 10 × 2
    logger.info("✓ Fee multiplier calculation")

    logger.info("All tiered privacy self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
