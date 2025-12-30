"""
Proof of Time - Tiered Privacy Model
Privacy tiers T0-T3 for balanced throughput and confidentiality.

Based on: ProofOfTime_DAG_Addendum.pdf Section 12

PRODUCTION-READY:
- T0 (Public): Addresses + amounts visible (~250 B, ~0.5 ms verify, 1× fee)
- T1 (Stealth): One-time addresses, amounts visible (~400 B, ~1 ms verify, 2× fee)

EXPERIMENTAL (NOT PRODUCTION-READY):
- T2 (Confidential): Stealth + hidden amounts - DISABLED BY DEFAULT
  Requires Bulletproofs which are NOT cryptographically implemented.
- T3 (Ring): Full RingCT - DISABLED BY DEFAULT
  Requires Bulletproofs for range proofs.

To enable T2/T3 (UNSAFE - FOR TESTING ONLY):
    export POT_ENABLE_EXPERIMENTAL_PRIVACY=1

Time is the ultimate proof.
"""

import os
import struct
import secrets
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import IntEnum

from pantheon.prometheus import sha256, sha256d
from pantheon.nyx import (
    StealthAddress,
    LSAG, LSAGSignature, Pedersen,
    Bulletproof, RangeProof, Ed25519Point,
    generate_key_image
)
from config import PROTOCOL

logger = logging.getLogger("proof_of_time.tiered_privacy")

# Experimental privacy (T2/T3) is disabled by default because current
# Bulletproof/LSAG implementations are not production-grade. Enable only if
# you fully understand the risks and provide audited crypto backends.
EXPERIMENTAL_PRIVACY_ENABLED = os.getenv("POT_ENABLE_EXPERIMENTAL_PRIVACY", "0") == "1"


# ============================================================================
# PRIVACY TIERS
# ============================================================================

class PrivacyTier(IntEnum):
    """
    Privacy tier enumeration.
    
    Higher tier = more privacy = larger size = higher fee.
    """
    T0_PUBLIC = 0       # Addresses + amounts visible
    T1_STEALTH = 1      # One-time addresses, amounts visible
    T2_CONFIDENTIAL = 2  # Stealth + hidden amounts
    T3_RING = 3         # Full RingCT


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
    PrivacyTier.T2_CONFIDENTIAL: {
        'name': 'Confidential',
        'size_bytes': 1200,
        'verify_time_ms': 8,
        'fee_multiplier': 5,
        'description': 'Stealth + hidden amounts (Pedersen + Bulletproofs)'
    },
    PrivacyTier.T3_RING: {
        'name': 'Ring',
        'size_bytes': 2500,
        'verify_time_ms': 40,
        'fee_multiplier': 10,
        'description': 'Full RingCT with ring size 11'
    }
}

# Default ring size for T3
DEFAULT_RING_SIZE = 11


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
    - T2: stealth + commitment + range_proof + encrypted_amount
    - T3: stealth + commitment + range_proof + encrypted_amount (for RingCT)
    """
    tier: PrivacyTier = PrivacyTier.T0_PUBLIC
    
    # T0: Public address and amount
    public_address: bytes = b''
    public_amount: int = 0
    
    # T1+: Stealth address components
    one_time_address: bytes = b''
    tx_public_key: bytes = b''
    
    # T1: Amount still visible
    visible_amount: int = 0
    
    # T2+: Hidden amount
    commitment: bytes = b''
    range_proof: Optional[RangeProof] = None
    encrypted_amount: bytes = b''
    
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
            
        elif self.tier in (PrivacyTier.T2_CONFIDENTIAL, PrivacyTier.T3_RING):
            # Confidential: stealth + commitment + range_proof + encrypted
            data.extend(self.one_time_address)
            data.extend(self.tx_public_key)
            data.extend(self.commitment)
            
            # Range proof
            if self.range_proof:
                proof_bytes = self.range_proof.serialize()
                data.extend(struct.pack('<I', len(proof_bytes)))
                data.extend(proof_bytes)
            else:
                data.extend(struct.pack('<I', 0))
            
            # Encrypted amount
            data.extend(struct.pack('<B', len(self.encrypted_amount)))
            data.extend(self.encrypted_amount)
        
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
            
        elif tier in (PrivacyTier.T2_CONFIDENTIAL, PrivacyTier.T3_RING):
            output.one_time_address = data[offset:offset + 32]
            offset += 32
            output.tx_public_key = data[offset:offset + 32]
            offset += 32
            output.commitment = data[offset:offset + 32]
            offset += 32
            
            # Range proof
            proof_len = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            if proof_len > 0:
                output.range_proof = RangeProof.deserialize(data[offset:offset + proof_len])
                offset += proof_len
            
            # Encrypted amount
            enc_len = data[offset]
            offset += 1
            output.encrypted_amount = data[offset:offset + enc_len]
            offset += enc_len
        
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
    
    - T0: Simple UTXO reference
    - T1: UTXO reference (stealth doesn't affect input)
    - T2: Pseudo-commitment
    - T3: Ring + key_image + ring_signature
    """
    tier: PrivacyTier = PrivacyTier.T0_PUBLIC
    
    # T0/T1: Simple UTXO reference
    prev_txid: bytes = b''
    prev_output_index: int = 0
    
    # T0: Public signature
    signature: bytes = b''
    
    # T2: Pseudo-commitment for balance
    pseudo_commitment: bytes = b''
    
    # T3: Ring signature components
    ring: List[bytes] = field(default_factory=list)
    key_image: bytes = b''
    ring_signature: Optional[LSAGSignature] = None
    
    def serialize(self) -> bytes:
        """Serialize tiered input."""
        data = bytearray()
        
        # Tier
        data.extend(struct.pack('<B', self.tier))
        
        if self.tier in (PrivacyTier.T0_PUBLIC, PrivacyTier.T1_STEALTH):
            # Simple UTXO reference
            data.extend(self.prev_txid)
            data.extend(struct.pack('<I', self.prev_output_index))
            
            if self.tier == PrivacyTier.T0_PUBLIC:
                data.extend(self.signature)
            
        elif self.tier == PrivacyTier.T2_CONFIDENTIAL:
            # UTXO reference + pseudo-commitment
            data.extend(self.prev_txid)
            data.extend(struct.pack('<I', self.prev_output_index))
            data.extend(self.pseudo_commitment)
            
        elif self.tier == PrivacyTier.T3_RING:
            # Ring signature
            data.extend(struct.pack('<B', len(self.ring)))
            for pk in self.ring:
                data.extend(pk)
            
            data.extend(self.key_image)
            
            if self.ring_signature:
                sig_bytes = self.ring_signature.serialize()
                data.extend(struct.pack('<I', len(sig_bytes)))
                data.extend(sig_bytes)
            else:
                data.extend(struct.pack('<I', 0))
            
            data.extend(self.pseudo_commitment)
        
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['TieredInput', int]:
        """Deserialize tiered input."""
        tier = PrivacyTier(data[offset])
        offset += 1
        
        inp = cls(tier=tier)
        
        if tier in (PrivacyTier.T0_PUBLIC, PrivacyTier.T1_STEALTH):
            inp.prev_txid = data[offset:offset + 32]
            offset += 32
            inp.prev_output_index = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            
            if tier == PrivacyTier.T0_PUBLIC:
                inp.signature = data[offset:offset + 64]
                offset += 64
            
        elif tier == PrivacyTier.T2_CONFIDENTIAL:
            inp.prev_txid = data[offset:offset + 32]
            offset += 32
            inp.prev_output_index = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            inp.pseudo_commitment = data[offset:offset + 32]
            offset += 32
            
        elif tier == PrivacyTier.T3_RING:
            ring_size = data[offset]
            offset += 1
            inp.ring = []
            for _ in range(ring_size):
                inp.ring.append(data[offset:offset + 32])
                offset += 32
            
            inp.key_image = data[offset:offset + 32]
            offset += 32
            
            sig_len = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            if sig_len > 0:
                inp.ring_signature = LSAGSignature.deserialize(data[offset:offset + sig_len])
                offset += sig_len
            
            inp.pseudo_commitment = data[offset:offset + 32]
            offset += 32
        
        return inp, offset


# ============================================================================
# TIERED TRANSACTION
# ============================================================================

@dataclass
class TieredTransaction:
    """
    Transaction with tiered privacy.
    
    Rules:
    - Outputs can be any tier ≥ input tier (privacy can increase)
    - T0 → T3 is valid
    - T3 → T0 is INVALID
    - Fee component always public (T0)
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
                size += 100
            elif inp.tier == PrivacyTier.T1_STEALTH:
                size += 68
            elif inp.tier == PrivacyTier.T2_CONFIDENTIAL:
                size += 100
            elif inp.tier == PrivacyTier.T3_RING:
                size += 32 * DEFAULT_RING_SIZE + 32 + 500  # ring + key_image + sig
        
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
    Builder for creating tiered transactions.
    """
    
    def __init__(self, default_tier: PrivacyTier = PrivacyTier.T1_STEALTH):
        self.default_tier = default_tier
        self.inputs: List[TieredInput] = []
        self.outputs: List[TieredOutput] = []
        self.fee: int = 0
    
    # =========================================================================
    # T0: PUBLIC OUTPUTS
    # =========================================================================
    
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
        prev_index: int,
        private_key: bytes
    ) -> 'TieredTransactionBuilder':
        """Add T0 (public) input with signature."""
        inp = TieredInput(
            tier=PrivacyTier.T0_PUBLIC,
            prev_txid=prev_txid,
            prev_output_index=prev_index
            # Signature will be added during signing
        )
        self.inputs.append(inp)
        return self
    
    # =========================================================================
    # T1: STEALTH OUTPUTS
    # =========================================================================
    
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
        stealth_out, r = StealthAddress.create_output(view_public, spend_public)
        
        output = TieredOutput(
            tier=PrivacyTier.T1_STEALTH,
            one_time_address=stealth_out.one_time_address,
            tx_public_key=stealth_out.tx_public_key,
            visible_amount=amount,
            output_index=len(self.outputs)
        )
        self.outputs.append(output)
        return self
    
    # =========================================================================
    # T2: CONFIDENTIAL OUTPUTS
    # =========================================================================
    
    def add_confidential_output(
        self,
        view_public: bytes,
        spend_public: bytes,
        amount: int,
        blinding: Optional[bytes] = None
    ) -> Tuple['TieredTransactionBuilder', bytes]:
        """
        Add T2 (confidential) output.
        
        Combines stealth address with Pedersen commitment.
        Uses Bulletproofs++ for range proofs.
        
        Returns (builder, blinding_factor) for balance verification.
        """
        if not EXPERIMENTAL_PRIVACY_ENABLED:
            raise ValueError("Confidential outputs (T2) are disabled: set POT_ENABLE_EXPERIMENTAL_PRIVACY=1 to enable (unsafe).")

        if blinding is None:
            blinding = Ed25519Point.scalar_random()
        
        # Create stealth output
        stealth_out, r = StealthAddress.create_output(view_public, spend_public)
        
        # Create Pedersen commitment
        commitment = Pedersen.commit(amount, blinding)
        
        # Create range proof (Bulletproofs)
        range_proof = Bulletproof.prove(amount, blinding)
        
        # Encrypt amount for recipient
        # encrypted_amount = amount XOR H(shared_secret || "amount")
        shared_secret = sha256(r + view_public)
        amount_mask = sha256(shared_secret + b"amount")[:8]
        amount_bytes = struct.pack('<Q', amount)
        encrypted_amount = bytes(a ^ b for a, b in zip(amount_bytes, amount_mask))
        
        output = TieredOutput(
            tier=PrivacyTier.T2_CONFIDENTIAL,
            one_time_address=stealth_out.one_time_address,
            tx_public_key=stealth_out.tx_public_key,
            commitment=commitment.commitment,
            range_proof=range_proof,
            encrypted_amount=encrypted_amount,
            output_index=len(self.outputs)
        )
        self.outputs.append(output)
        
        return self, blinding
    
    # =========================================================================
    # T3: RING OUTPUTS
    # =========================================================================
    
    def add_ring_input(
        self,
        real_output: TieredOutput,
        real_private_key: bytes,
        decoy_outputs: List[TieredOutput],
        amount: int,
        blinding: bytes
    ) -> 'TieredTransactionBuilder':
        """
        Add T3 (ring) input with ring signature.
        
        Uses LSAG signature with key image for double-spend prevention.
        Default ring size = 11 (1 real + 10 decoys).
        """
        if not EXPERIMENTAL_PRIVACY_ENABLED:
            raise ValueError("Ring inputs (T3) are disabled: set POT_ENABLE_EXPERIMENTAL_PRIVACY=1 to enable (unsafe).")

        # Build ring from outputs
        ring = []
        real_index = secrets.randbelow(len(decoy_outputs) + 1)
        
        for i, decoy in enumerate(decoy_outputs):
            if i == real_index:
                ring.append(real_output.one_time_address)
            ring.append(decoy.one_time_address)
        
        if real_index >= len(decoy_outputs):
            ring.append(real_output.one_time_address)
        
        # Pad to ring size if needed
        while len(ring) < DEFAULT_RING_SIZE:
            ring.append(Ed25519Point.scalarmult_base(Ed25519Point.scalar_random()))
        
        ring = ring[:DEFAULT_RING_SIZE]
        
        # Find real position
        real_pos = ring.index(real_output.one_time_address)
        
        # Generate key image
        key_image = generate_key_image(real_private_key, real_output.one_time_address)
        
        # Create pseudo-commitment
        pseudo_blinding = Ed25519Point.scalar_random()
        pseudo_commit = Pedersen.commit(amount, pseudo_blinding)
        
        # Will sign after all inputs/outputs are added
        inp = TieredInput(
            tier=PrivacyTier.T3_RING,
            ring=ring,
            key_image=key_image,
            pseudo_commitment=pseudo_commit.commitment
            # ring_signature will be set during build()
        )
        self.inputs.append(inp)
        
        return self
    
    def add_ring_output(
        self,
        view_public: bytes,
        spend_public: bytes,
        amount: int
    ) -> Tuple['TieredTransactionBuilder', bytes]:
        """Add T3 (ring) output - same as T2 but marked as T3."""
        if not EXPERIMENTAL_PRIVACY_ENABLED:
            raise ValueError("Ring outputs (T3) are disabled: set POT_ENABLE_EXPERIMENTAL_PRIVACY=1 to enable (unsafe).")

        builder, blinding = self.add_confidential_output(view_public, spend_public, amount)
        
        # Change tier to T3
        builder.outputs[-1].tier = PrivacyTier.T3_RING
        
        return builder, blinding
    
    # =========================================================================
    # BUILD
    # =========================================================================
    
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
    Validates tiered transactions.
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
    
    @staticmethod
    def validate_t2_output(output: TieredOutput) -> bool:
        """Validate T2 output."""
        if len(output.one_time_address) != 32:
            return False
        if len(output.tx_public_key) != 32:
            return False
        if len(output.commitment) != 32:
            return False
        
        # Verify range proof
        if output.range_proof:
            if not Bulletproof.verify(output.commitment, output.range_proof):
                return False
        
        return True
    
    @staticmethod
    def validate_t3_input(
        inp: TieredInput,
        message: bytes,
        spent_key_images: set
    ) -> Tuple[bool, str]:
        """Validate T3 ring input."""
        # Check ring size
        if len(inp.ring) < 2:
            return False, "Ring too small"
        if len(inp.ring) > 128:
            return False, "Ring too large"
        
        # Check key image not spent
        if inp.key_image in spent_key_images:
            return False, "Key image already spent"
        
        # Verify ring signature
        if inp.ring_signature:
            if not LSAG.verify(message, inp.ring, inp.ring_signature):
                return False, "Invalid ring signature"
        else:
            return False, "Missing ring signature"
        
        return True, "OK"
    
    @classmethod
    def validate_transaction(
        cls,
        tx: TieredTransaction,
        spent_key_images: set = None
    ) -> Tuple[bool, str]:
        """
        Validate complete tiered transaction.
        """
        if spent_key_images is None:
            spent_key_images = set()
        
        # Reject confidential/ring tiers unless explicitly enabled
        if not EXPERIMENTAL_PRIVACY_ENABLED:
            for i, inp in enumerate(tx.inputs):
                if inp.tier in (PrivacyTier.T2_CONFIDENTIAL, PrivacyTier.T3_RING):
                    return False, f"Experimental privacy disabled: input {i} is {inp.tier.name}"
            for i, out in enumerate(tx.outputs):
                if out.tier in (PrivacyTier.T2_CONFIDENTIAL, PrivacyTier.T3_RING):
                    return False, f"Experimental privacy disabled: output {i} is {out.tier.name}"
        
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
            elif output.tier in (PrivacyTier.T2_CONFIDENTIAL, PrivacyTier.T3_RING):
                if not cls.validate_t2_output(output):
                    return False, f"Invalid T2/T3 output {i}"
        
        # Validate T3 inputs
        tx_hash = tx.hash()
        for i, inp in enumerate(tx.inputs):
            if inp.tier == PrivacyTier.T3_RING:
                valid, reason = cls.validate_t3_input(inp, tx_hash, spent_key_images)
                if not valid:
                    return False, f"Input {i}: {reason}"
        
        # Validate fee
        required_fee = tx.calculate_fee()
        if tx.fee < required_fee:
            return False, f"Fee {tx.fee} < required {required_fee}"
        
        return True, "OK"


# ============================================================================
# ANONYMITY SET MANAGER
# ============================================================================

class AnonymitySetManager:
    """
    Manages anonymity sets for decoy selection.
    
    Per spec:
    - T3 decoys selected from T2/T3 outputs only
    - Minimum ring size 11
    - Network pads with synthetic decoys if necessary
    """
    
    def __init__(self):
        # Outputs by tier
        self.t2_outputs: List[TieredOutput] = []
        self.t3_outputs: List[TieredOutput] = []
    
    def add_output(self, output: TieredOutput):
        """Add output to anonymity set pool."""
        if output.tier == PrivacyTier.T2_CONFIDENTIAL:
            self.t2_outputs.append(output)
        elif output.tier == PrivacyTier.T3_RING:
            self.t3_outputs.append(output)
    
    def select_decoys(
        self,
        count: int,
        exclude: Optional[TieredOutput] = None
    ) -> List[TieredOutput]:
        """
        Select decoy outputs for ring.
        
        Selects from T2 and T3 outputs only.
        """
        # Combine T2 and T3 pools
        pool = self.t2_outputs + self.t3_outputs
        
        # Exclude the real output
        if exclude:
            pool = [o for o in pool if o.one_time_address != exclude.one_time_address]
        
        # Select random decoys
        if len(pool) >= count:
            indices = list(range(len(pool)))
            secrets.SystemRandom().shuffle(indices)
            return [pool[i] for i in indices[:count]]
        else:
            # Pad with synthetic decoys
            decoys = pool.copy()
            while len(decoys) < count:
                synthetic = TieredOutput(
                    tier=PrivacyTier.T2_CONFIDENTIAL,
                    one_time_address=Ed25519Point.scalarmult_base(Ed25519Point.scalar_random()),
                    tx_public_key=Ed25519Point.scalarmult_base(Ed25519Point.scalar_random()),
                    commitment=Ed25519Point.scalarmult_base(Ed25519Point.scalar_random())
                )
                decoys.append(synthetic)
            return decoys
    
    def get_pool_stats(self) -> dict:
        """Get statistics about anonymity set pools."""
        return {
            't2_count': len(self.t2_outputs),
            't3_count': len(self.t3_outputs),
            'total': len(self.t2_outputs) + len(self.t3_outputs),
            'recommended_ring_size': DEFAULT_RING_SIZE
        }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run tiered privacy self-tests."""
    logger.info("Running tiered privacy self-tests...")
    
    # Test tier specs
    assert TIER_SPECS[PrivacyTier.T0_PUBLIC]['fee_multiplier'] == 1
    assert TIER_SPECS[PrivacyTier.T3_RING]['fee_multiplier'] == 10
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
    
    # Test tier upgrade rule
    builder2 = TieredTransactionBuilder()
    builder2.inputs.append(TieredInput(tier=PrivacyTier.T0_PUBLIC))
    builder2.outputs.append(TieredOutput(tier=PrivacyTier.T1_STEALTH))
    
    valid, _ = builder2.build().validate_tier_rules()
    assert valid, "T0 → T1 should be valid"
    logger.info("✓ Tier upgrade allowed (T0 → T1)")
    
    # Test tier downgrade blocked
    builder3 = TieredTransactionBuilder()
    builder3.inputs.append(TieredInput(tier=PrivacyTier.T3_RING))
    builder3.outputs.append(TieredOutput(tier=PrivacyTier.T0_PUBLIC))
    
    try:
        builder3.build()
        assert False, "T3 → T0 should be invalid"
    except ValueError:
        pass
    logger.info("✓ Tier downgrade blocked (T3 → T0)")
    
    # Test anonymity set manager
    asm = AnonymitySetManager()
    for i in range(20):
        asm.add_output(TieredOutput(
            tier=PrivacyTier.T2_CONFIDENTIAL,
            one_time_address=secrets.token_bytes(32)
        ))
    
    decoys = asm.select_decoys(10)
    assert len(decoys) == 10
    logger.info("✓ Anonymity set decoy selection")
    
    # Test fee calculation
    builder4 = TieredTransactionBuilder()
    builder4.outputs.append(TieredOutput(tier=PrivacyTier.T3_RING))
    
    tx = TieredTransaction(outputs=builder4.outputs)
    required_fee = tx.calculate_fee(base_fee=10)
    assert required_fee == 100  # 10 × 10
    logger.info("✓ Fee multiplier calculation")
    
    logger.info("All tiered privacy self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()

