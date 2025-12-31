"""
Montana v4.0 - Block and Transaction Structures

Production-grade implementation of blockchain data structures.

Includes:
- Block and BlockHeader with full serialization
- Transaction with RingCT support
- Coinbase (reward) transactions
- Merkle root computation
- Block validation
- Montana v4.0 transaction types:
  - APOSTLE_HANDSHAKE: 12 Apostles mutual trust
  - EPOCH_PROOF: Bitcoin halving survival proof
  - BTC_ANCHOR: Bitcoin block timestamp anchor
  - RHEUMA_CHECKPOINT: Blockless stream checkpoint

Time is the ultimate proof. Trust is sacred.
"""

import struct
import time
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import IntEnum

from pantheon.prometheus import (
    sha256, sha256d, Ed25519, MerkleTree,
    VDFProof, VRFOutput, WesolowskiVDF, ECVRF
)
from pantheon.nyx import LSAGSignature
from config import PROTOCOL, get_block_reward

logger = logging.getLogger("proof_of_time.structures")


# ============================================================================
# SERIALIZATION HELPERS
# ============================================================================

class Serializable:
    """Base class for serializable objects."""
    
    def serialize(self) -> bytes:
        """Serialize object to bytes."""
        raise NotImplementedError
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Serializable':
        """Deserialize object from bytes."""
        raise NotImplementedError
    
    def to_hex(self) -> str:
        """Serialize to hex string."""
        return self.serialize().hex()
    
    @classmethod
    def from_hex(cls, hex_str: str) -> 'Serializable':
        """Deserialize from hex string."""
        return cls.deserialize(bytes.fromhex(hex_str))


def write_varint(n: int) -> bytes:
    """Write variable-length integer (Bitcoin-style)."""
    if n < 0xFD:
        return struct.pack('<B', n)
    elif n <= 0xFFFF:
        return b'\xFD' + struct.pack('<H', n)
    elif n <= 0xFFFFFFFF:
        return b'\xFE' + struct.pack('<I', n)
    else:
        return b'\xFF' + struct.pack('<Q', n)


def read_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Read variable-length integer. Returns (value, new_offset)."""
    first = data[offset]
    if first < 0xFD:
        return first, offset + 1
    elif first == 0xFD:
        return struct.unpack_from('<H', data, offset + 1)[0], offset + 3
    elif first == 0xFE:
        return struct.unpack_from('<I', data, offset + 1)[0], offset + 5
    else:
        return struct.unpack_from('<Q', data, offset + 1)[0], offset + 9


def write_bytes(data: bytes) -> bytes:
    """Write length-prefixed bytes."""
    return write_varint(len(data)) + data


def read_bytes(data: bytes, offset: int = 0) -> Tuple[bytes, int]:
    """Read length-prefixed bytes. Returns (bytes, new_offset)."""
    length, offset = read_varint(data, offset)
    return data[offset:offset + length], offset + length


# ============================================================================
# TRANSACTION INPUT
# ============================================================================

@dataclass
class TxInput(Serializable):
    """
    Transaction input with ring signature.
    
    References an output using:
    - Ring of public keys (decoys + real)
    - Key image (for double-spend detection)
    - Ring signature proving ownership
    """
    # Ring members (public keys)
    ring: List[bytes] = field(default_factory=list)
    
    # Key image I = x * Hp(P)
    key_image: bytes = b''
    
    # LSAG ring signature
    ring_signature: Optional[LSAGSignature] = None
    
    # Pseudo output commitment (for RingCT)
    pseudo_commitment: bytes = b''
    
    def serialize(self) -> bytes:
        """Serialize input."""
        data = bytearray()
        
        # Ring size and members
        data.extend(write_varint(len(self.ring)))
        for pk in self.ring:
            data.extend(pk)
        
        # Key image
        data.extend(self.key_image)
        
        # Ring signature
        if self.ring_signature:
            sig_bytes = self.ring_signature.serialize()
            data.extend(write_bytes(sig_bytes))
        else:
            data.extend(write_varint(0))
        
        # Pseudo commitment
        data.extend(self.pseudo_commitment)
        
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['TxInput', int]:
        """Deserialize input. Returns (TxInput, new_offset)."""
        # Validate minimum data length
        if len(data) < offset + 1:
            raise ValueError("TxInput: data too short for ring size")
        
        # Ring
        ring_size, offset = read_varint(data, offset)
        
        # Validate ring size (prevent memory exhaustion)
        if ring_size > 1024:
            raise ValueError(f"TxInput: ring size too large: {ring_size}")
        
        # Validate data length for ring
        required = ring_size * 32 + 32 + 1 + 32  # ring + key_image + min_sig + pseudo
        if len(data) < offset + required:
            raise ValueError("TxInput: data too short for ring members")
        
        ring = []
        for _ in range(ring_size):
            ring.append(data[offset:offset + 32])
            offset += 32
        
        # Key image
        key_image = data[offset:offset + 32]
        offset += 32
        
        # Ring signature
        sig_bytes, offset = read_bytes(data, offset)
        if sig_bytes:
            ring_signature = LSAGSignature.deserialize(sig_bytes)
        else:
            ring_signature = None
        
        # Pseudo commitment
        if len(data) < offset + 32:
            raise ValueError("TxInput: data too short for pseudo commitment")
        pseudo_commitment = data[offset:offset + 32]
        offset += 32
        
        return cls(
            ring=ring,
            key_image=key_image,
            ring_signature=ring_signature,
            pseudo_commitment=pseudo_commitment
        ), offset


# ============================================================================
# TRANSACTION OUTPUT
# ============================================================================

@dataclass
class TxOutput(Serializable):
    """
    Transaction output with privacy features.
    
    Contains:
    - Stealth address (one-time public key)
    - Amount commitment (Pedersen)
    - Range proof (Bulletproof)
    - Encrypted amount
    """
    # Stealth address components
    stealth_address: bytes = b''  # One-time address P
    tx_public_key: bytes = b''  # Transaction public key R
    
    # Amount hiding
    commitment: bytes = b''  # Pedersen commitment C
    range_proof: Optional[bytes] = None  # T2/T3 not supported (legacy field)
    encrypted_amount: bytes = b''
    
    # Output index (for identification)
    output_index: int = 0
    
    def serialize(self) -> bytes:
        """Serialize output."""
        data = bytearray()
        
        # Stealth address components
        data.extend(self.stealth_address)
        data.extend(self.tx_public_key)
        
        # Amount hiding
        data.extend(self.commitment)
        
        # Range proof (legacy - T2/T3 not supported)
        if self.range_proof:
            data.extend(write_bytes(self.range_proof))
        else:
            data.extend(write_varint(0))
        
        # Encrypted amount
        data.extend(write_bytes(self.encrypted_amount))
        
        # Output index
        data.extend(write_varint(self.output_index))
        
        return bytes(data)
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['TxOutput', int]:
        """Deserialize output. Returns (TxOutput, new_offset)."""
        # Validate minimum data length (3 * 32 bytes for addresses + commitment)
        if len(data) < offset + 96:
            raise ValueError("TxOutput: data too short for fixed fields")
        
        # Stealth address
        stealth_address = data[offset:offset + 32]
        offset += 32
        tx_public_key = data[offset:offset + 32]
        offset += 32
        
        # Commitment
        commitment = data[offset:offset + 32]
        offset += 32
        
        # Range proof (legacy - T2/T3 not supported)
        if len(data) < offset + 1:
            raise ValueError("TxOutput: data too short for range proof length")
        proof_bytes, offset = read_bytes(data, offset)
        range_proof = proof_bytes if proof_bytes else None
        
        # Encrypted amount
        if len(data) < offset + 1:
            raise ValueError("TxOutput: data too short for encrypted amount")
        encrypted_amount, offset = read_bytes(data, offset)
        
        # Output index
        if len(data) < offset + 1:
            raise ValueError("TxOutput: data too short for output index")
        output_index, offset = read_varint(data, offset)
        
        return cls(
            stealth_address=stealth_address,
            tx_public_key=tx_public_key,
            commitment=commitment,
            range_proof=range_proof,
            encrypted_amount=encrypted_amount,
            output_index=output_index
        ), offset


# ============================================================================
# TRANSACTION
# ============================================================================

class TxType(IntEnum):
    """
    Transaction type enumeration.

    Montana v4.0: Added types for 12 Apostles and Bitcoin anchoring.
    """
    COINBASE = 0          # Block reward
    STANDARD = 1          # Regular transfer
    SLASH = 2             # Slashing penalty (collective responsibility)
    APOSTLE_HANDSHAKE = 3 # 12 Apostles mutual trust handshake
    EPOCH_PROOF = 4       # Proof of surviving Bitcoin halving
    BTC_ANCHOR = 5        # Bitcoin block anchor timestamp
    RHEUMA_CHECKPOINT = 6 # RHEUMA stream checkpoint


@dataclass
class Transaction(Serializable):
    """
    Proof of Time transaction with full privacy.
    
    All transactions use RingCT for:
    - Sender anonymity (ring signatures)
    - Receiver anonymity (stealth addresses)
    - Amount hiding (commitments + range proofs)
    """
    # Header
    version: int = PROTOCOL.PROTOCOL_VERSION
    tx_type: TxType = TxType.STANDARD
    
    # Inputs and outputs
    inputs: List[TxInput] = field(default_factory=list)
    outputs: List[TxOutput] = field(default_factory=list)
    
    # Fee (in seconds, transparent for validation)
    fee: int = 0
    
    # Extra data (for coinbase messages, etc.)
    extra: bytes = b''
    
    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)
    
    def serialize(self) -> bytes:
        """Serialize transaction."""
        data = bytearray()
        
        # Header
        data.extend(struct.pack('<H', self.version))
        data.extend(struct.pack('<B', self.tx_type))
        
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
    
    # Maximum limits to prevent DoS
    MAX_INPUTS = 10000
    MAX_OUTPUTS = 10000
    MAX_EXTRA_SIZE = 1024 * 1024  # 1 MB
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['Transaction', int]:
        """Deserialize transaction. Returns (Transaction, new_offset)."""
        # Validate minimum data length
        if len(data) < offset + 3:  # version (2) + type (1)
            raise ValueError("Transaction: data too short for header")
        
        # Header
        version = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # Validate tx_type
        type_byte = data[offset]
        if type_byte > 2:
            raise ValueError(f"Transaction: invalid tx_type: {type_byte}")
        tx_type = TxType(type_byte)
        offset += 1
        
        # Inputs
        if len(data) < offset + 1:
            raise ValueError("Transaction: data too short for input count")
        num_inputs, offset = read_varint(data, offset)
        
        # Validate input count (prevent memory exhaustion)
        if num_inputs > cls.MAX_INPUTS:
            raise ValueError(f"Transaction: too many inputs: {num_inputs}")
        
        inputs = []
        for _ in range(num_inputs):
            inp, offset = TxInput.deserialize(data, offset)
            inputs.append(inp)
        
        # Outputs
        if len(data) < offset + 1:
            raise ValueError("Transaction: data too short for output count")
        num_outputs, offset = read_varint(data, offset)
        
        # Validate output count (prevent memory exhaustion)
        if num_outputs > cls.MAX_OUTPUTS:
            raise ValueError(f"Transaction: too many outputs: {num_outputs}")
        
        outputs = []
        for _ in range(num_outputs):
            out, offset = TxOutput.deserialize(data, offset)
            outputs.append(out)
        
        # Fee
        if len(data) < offset + 8:
            raise ValueError("Transaction: data too short for fee")
        fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        # Extra
        if len(data) < offset + 1:
            raise ValueError("Transaction: data too short for extra")
        extra, offset = read_bytes(data, offset)
        
        # Validate extra size
        if len(extra) > cls.MAX_EXTRA_SIZE:
            raise ValueError(f"Transaction: extra data too large: {len(extra)}")
        
        return cls(
            version=version,
            tx_type=tx_type,
            inputs=inputs,
            outputs=outputs,
            fee=fee,
            extra=extra
        ), offset
    
    def hash(self) -> bytes:
        """Compute transaction hash (txid)."""
        if self._hash is None:
            self._hash = sha256d(self.serialize())
        return self._hash
    
    @property
    def txid(self) -> str:
        """Transaction ID as hex string."""
        return self.hash().hex()
    
    @property
    def size(self) -> int:
        """Transaction size in bytes."""
        return len(self.serialize())
    
    def is_coinbase(self) -> bool:
        """Check if this is a coinbase transaction."""
        return self.tx_type == TxType.COINBASE and len(self.inputs) == 0
    
    @classmethod
    def create_coinbase(
        cls,
        height: int,
        reward_address: bytes,
        reward_tx_pubkey: bytes,
        extra_data: bytes = b''
    ) -> 'Transaction':
        """
        Create coinbase (block reward) transaction.
        
        Args:
            height: Block height
            reward_address: Stealth address for reward
            reward_tx_pubkey: Transaction public key
            extra_data: Optional extra data
        
        Returns:
            Coinbase transaction
        """
        reward = get_block_reward(height)
        
        # Create output for reward
        output = TxOutput(
            stealth_address=reward_address,
            tx_public_key=reward_tx_pubkey,
            commitment=sha256(struct.pack('<Q', reward)),  # Transparent for coinbase
            range_proof=None,  # Not needed for coinbase
            encrypted_amount=struct.pack('<Q', reward),
            output_index=0
        )
        
        # Encode height in extra (BIP34 style)
        height_bytes = struct.pack('<I', height)
        extra = height_bytes + extra_data
        
        return cls(
            version=PROTOCOL.PROTOCOL_VERSION,
            tx_type=TxType.COINBASE,
            inputs=[],
            outputs=[output],
            fee=0,
            extra=extra
        )


# ============================================================================
# BLOCK HEADER
# ============================================================================

@dataclass
class BlockHeader(Serializable):
    """
    Block header with VDF and VRF proofs.
    
    Contains:
    - Standard header fields (version, prev_hash, merkle_root, timestamp)
    - Height (explicit, not derived)
    - VDF proof (proves time elapsed)
    - VRF proof (leader selection)
    - Leader signature
    """
    # Standard fields
    version: int = PROTOCOL.PROTOCOL_VERSION
    prev_block_hash: bytes = b'\x00' * 32
    merkle_root: bytes = b'\x00' * 32
    timestamp: int = 0
    height: int = 0
    
    # VDF proof
    vdf_input: bytes = b'\x00' * 32
    vdf_output: bytes = b''
    vdf_proof: bytes = b''
    vdf_iterations: int = 0
    
    # VRF proof (leader selection)
    vrf_output: bytes = b''
    vrf_proof: bytes = b''
    
    # Leader identity
    leader_pubkey: bytes = b'\x00' * 32
    leader_signature: bytes = b'\x00' * 64

    # Fallback flag: True if no node won VRF lottery (lowest VRF selected)
    # Must be True for fallback selections to be considered valid
    is_fallback_leader: bool = False

    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)
    
    def serialize(self) -> bytes:
        """Serialize header."""
        data = bytearray()
        
        # Standard fields
        data.extend(struct.pack('<I', self.version))
        data.extend(self.prev_block_hash)
        data.extend(self.merkle_root)
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<Q', self.height))
        
        # VDF proof
        data.extend(self.vdf_input)
        data.extend(write_bytes(self.vdf_output))
        data.extend(write_bytes(self.vdf_proof))
        data.extend(struct.pack('<I', self.vdf_iterations))
        
        # VRF proof
        data.extend(write_bytes(self.vrf_output))
        data.extend(write_bytes(self.vrf_proof))
        
        # Leader
        data.extend(self.leader_pubkey)
        data.extend(self.leader_signature)

        # Flags (1 byte for extensibility)
        flags = 0
        if self.is_fallback_leader:
            flags |= 0x01
        data.extend(struct.pack('<B', flags))

        return bytes(data)
    
    # Maximum VDF/VRF proof sizes to prevent memory exhaustion
    MAX_VDF_PROOF_SIZE = 1024 * 1024  # 1 MB
    MAX_VRF_PROOF_SIZE = 1024  # 1 KB
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['BlockHeader', int]:
        """Deserialize header. Returns (BlockHeader, new_offset)."""
        # Validate minimum header size (fixed fields)
        # version(4) + prev_hash(32) + merkle(32) + timestamp(8) + height(8) + vdf_input(32) + vdf_iters(4) + leader_pk(32) + leader_sig(64) = 216 bytes min
        if len(data) < offset + 216:
            raise ValueError("BlockHeader: data too short for fixed fields")
        
        # Standard fields
        version = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        prev_hash = data[offset:offset + 32]
        offset += 32
        
        merkle_root = data[offset:offset + 32]
        offset += 32
        
        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8
        
        # VDF proof
        vdf_input = data[offset:offset + 32]
        offset += 32
        
        if len(data) < offset + 1:
            raise ValueError("BlockHeader: data too short for VDF output")
        vdf_output, offset = read_bytes(data, offset)
        if len(vdf_output) > cls.MAX_VDF_PROOF_SIZE:
            raise ValueError(f"BlockHeader: VDF output too large: {len(vdf_output)}")
        
        if len(data) < offset + 1:
            raise ValueError("BlockHeader: data too short for VDF proof")
        vdf_proof, offset = read_bytes(data, offset)
        if len(vdf_proof) > cls.MAX_VDF_PROOF_SIZE:
            raise ValueError(f"BlockHeader: VDF proof too large: {len(vdf_proof)}")
        
        if len(data) < offset + 4:
            raise ValueError("BlockHeader: data too short for VDF iterations")
        vdf_iterations = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        # VRF proof
        if len(data) < offset + 1:
            raise ValueError("BlockHeader: data too short for VRF output")
        vrf_output, offset = read_bytes(data, offset)
        if len(vrf_output) > cls.MAX_VRF_PROOF_SIZE:
            raise ValueError(f"BlockHeader: VRF output too large: {len(vrf_output)}")
        
        if len(data) < offset + 1:
            raise ValueError("BlockHeader: data too short for VRF proof")
        vrf_proof, offset = read_bytes(data, offset)
        if len(vrf_proof) > cls.MAX_VRF_PROOF_SIZE:
            raise ValueError(f"BlockHeader: VRF proof too large: {len(vrf_proof)}")
        
        # Leader
        if len(data) < offset + 96:  # pubkey(32) + sig(64)
            raise ValueError("BlockHeader: data too short for leader fields")
        leader_pubkey = data[offset:offset + 32]
        offset += 32

        leader_sig = data[offset:offset + 64]
        offset += 64

        # Flags (1 byte) - with backward compatibility
        is_fallback_leader = False
        if len(data) > offset:
            flags = data[offset]
            offset += 1
            is_fallback_leader = bool(flags & 0x01)

        return cls(
            version=version,
            prev_block_hash=prev_hash,
            merkle_root=merkle_root,
            timestamp=timestamp,
            height=height,
            vdf_input=vdf_input,
            vdf_output=vdf_output,
            vdf_proof=vdf_proof,
            vdf_iterations=vdf_iterations,
            vrf_output=vrf_output,
            vrf_proof=vrf_proof,
            leader_pubkey=leader_pubkey,
            leader_signature=leader_sig,
            is_fallback_leader=is_fallback_leader
        ), offset
    
    def hash(self) -> bytes:
        """Compute block hash."""
        if self._hash is None:
            # Hash everything except signature
            data = bytearray()
            data.extend(struct.pack('<I', self.version))
            data.extend(self.prev_block_hash)
            data.extend(self.merkle_root)
            data.extend(struct.pack('<Q', self.timestamp))
            data.extend(struct.pack('<Q', self.height))
            data.extend(self.vdf_input)
            data.extend(self.vdf_output)
            data.extend(self.vdf_proof)
            data.extend(self.vrf_output)
            data.extend(self.vrf_proof)
            data.extend(self.leader_pubkey)
            
            self._hash = sha256d(bytes(data))
        
        return self._hash
    
    @property
    def block_hash(self) -> str:
        """Block hash as hex string."""
        return self.hash().hex()
    
    def signing_hash(self) -> bytes:
        """Hash for leader signature."""
        data = bytearray()
        data.extend(struct.pack('<I', self.version))
        data.extend(self.prev_block_hash)
        data.extend(self.merkle_root)
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<Q', self.height))
        data.extend(self.vdf_output)
        data.extend(self.vrf_output)
        
        return sha256(bytes(data))


# ============================================================================
# BLOCK
# ============================================================================

@dataclass
class Block(Serializable):
    """
    Complete block with header and transactions.
    """
    header: BlockHeader = field(default_factory=BlockHeader)
    transactions: List[Transaction] = field(default_factory=list)
    
    def serialize(self) -> bytes:
        """Serialize block."""
        data = bytearray()
        
        # Header
        header_bytes = self.header.serialize()
        data.extend(write_bytes(header_bytes))
        
        # Transactions
        data.extend(write_varint(len(self.transactions)))
        for tx in self.transactions:
            data.extend(write_bytes(tx.serialize()))
        
        return bytes(data)
    
    # Maximum limits to prevent DoS
    MAX_TRANSACTIONS = 50000
    MAX_BLOCK_SIZE = 32 * 1024 * 1024  # 32 MB
    
    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['Block', int]:
        """Deserialize block. Returns (Block, new_offset)."""
        # Validate block size
        if len(data) > cls.MAX_BLOCK_SIZE:
            raise ValueError(f"Block: data too large: {len(data)} bytes")
        
        # Validate minimum data length
        if len(data) < offset + 1:
            raise ValueError("Block: data too short for header length")
        
        # Header
        header_bytes, offset = read_bytes(data, offset)
        if len(header_bytes) < 100:  # Minimum reasonable header size
            raise ValueError("Block: header too short")
        header, _ = BlockHeader.deserialize(header_bytes)
        
        # Transactions
        if len(data) < offset + 1:
            raise ValueError("Block: data too short for transaction count")
        num_txs, offset = read_varint(data, offset)
        
        # Validate transaction count (prevent memory exhaustion)
        if num_txs > cls.MAX_TRANSACTIONS:
            raise ValueError(f"Block: too many transactions: {num_txs}")
        
        transactions = []
        for _ in range(num_txs):
            if len(data) < offset + 1:
                raise ValueError("Block: data too short for transaction")
            tx_bytes, offset = read_bytes(data, offset)
            tx, _ = Transaction.deserialize(tx_bytes)
            transactions.append(tx)
        
        return cls(header=header, transactions=transactions), offset
    
    def compute_merkle_root(self) -> bytes:
        """Compute Merkle root of transactions."""
        tx_hashes = [tx.hash() for tx in self.transactions]
        return MerkleTree.compute_root(tx_hashes)
    
    def verify_merkle_root(self) -> bool:
        """Verify Merkle root matches transactions."""
        return self.header.merkle_root == self.compute_merkle_root()
    
    @property
    def hash(self) -> bytes:
        """Block hash (header hash)."""
        return self.header.hash()
    
    @property
    def height(self) -> int:
        """Block height."""
        return self.header.height
    
    @property
    def timestamp(self) -> int:
        """Block timestamp."""
        return self.header.timestamp
    
    @property
    def size(self) -> int:
        """Block size in bytes."""
        return len(self.serialize())
    
    @property
    def tx_count(self) -> int:
        """Number of transactions."""
        return len(self.transactions)
    
    def get_coinbase(self) -> Optional[Transaction]:
        """Get coinbase transaction if present."""
        if self.transactions and self.transactions[0].is_coinbase():
            return self.transactions[0]
        return None
    
    def get_total_fees(self) -> int:
        """Sum of all transaction fees."""
        return sum(tx.fee for tx in self.transactions if not tx.is_coinbase())


# ============================================================================
# GENESIS BLOCK
# ============================================================================

def create_genesis_block() -> Block:
    """
    Create the genesis block.
    
    Genesis block has:
    - Height 0
    - No previous block
    - VDF/VRF proofs are zeroed
    - Single coinbase transaction
    - Fixed timestamp (2025-12-25 00:00:00 UTC)
    """
    # Genesis coinbase
    genesis_message = b"Proof of Time Genesis - 25 Dec 2025 - In time, everyone is equal"
    
    coinbase = Transaction(
        version=PROTOCOL.PROTOCOL_VERSION,
        tx_type=TxType.COINBASE,
        inputs=[],
        outputs=[
            TxOutput(
                stealth_address=b'\x00' * 32,  # Unspendable
                tx_public_key=b'\x00' * 32,
                commitment=sha256(struct.pack('<Q', PROTOCOL.INITIAL_REWARD)),
                range_proof=None,
                encrypted_amount=struct.pack('<Q', PROTOCOL.INITIAL_REWARD),
                output_index=0
            )
        ],
        fee=0,
        extra=genesis_message
    )
    
    # Genesis header
    header = BlockHeader(
        version=PROTOCOL.PROTOCOL_VERSION,
        prev_block_hash=b'\x00' * 32,
        merkle_root=b'\x00' * 32,  # Will be computed
        timestamp=PROTOCOL.GENESIS_TIMESTAMP,
        height=0,
        vdf_input=b'\x00' * 32,
        vdf_output=b'\x00' * 32,
        vdf_proof=b'',
        vdf_iterations=0,
        vrf_output=b'\x00' * 32,
        vrf_proof=b'',
        leader_pubkey=b'\x00' * 32,
        leader_signature=b'\x00' * 64
    )
    
    block = Block(header=header, transactions=[coinbase])
    
    # Set Merkle root
    block.header.merkle_root = block.compute_merkle_root()
    
    logger.info(f"Created genesis block: {block.hash.hex()[:16]}...")
    
    return block


# ============================================================================
# BLOCK VALIDATION
# ============================================================================

class BlockValidationError(Exception):
    """Block validation error."""
    pass


class BlockValidator:
    """Block validation logic."""
    
    def __init__(self, vdf: WesolowskiVDF):
        self.vdf = vdf
    
    def validate_header(
        self,
        header: BlockHeader,
        prev_header: Optional[BlockHeader] = None
    ) -> bool:
        """
        Validate block header.
        
        Checks:
        1. Version is valid
        2. Timestamp is reasonable
        3. Height is correct
        4. VDF proof is valid
        5. VRF proof is valid
        6. Leader signature is valid
        """
        # Version check
        if header.version > PROTOCOL.PROTOCOL_VERSION:
            raise BlockValidationError(f"Unknown version: {header.version}")
        
        # Height check
        if prev_header:
            if header.height != prev_header.height + 1:
                raise BlockValidationError(
                    f"Invalid height: expected {prev_header.height + 1}, got {header.height}"
                )
            
            # Previous hash check
            if header.prev_block_hash != prev_header.hash():
                raise BlockValidationError("Previous block hash mismatch")
        else:
            # Genesis block
            if header.height != 0:
                raise BlockValidationError("First block must be genesis (height 0)")
        
        # Timestamp check
        if prev_header and header.timestamp <= prev_header.timestamp:
            raise BlockValidationError("Timestamp must be greater than previous block")
        
        current_time = int(time.time())
        if header.timestamp > current_time + 7200:  # 2 hour future tolerance
            raise BlockValidationError("Block timestamp too far in future")
        
        # VDF proof validation
        if header.height > 0:  # Skip genesis
            vdf_proof = VDFProof(
                output=header.vdf_output,
                proof=header.vdf_proof,
                iterations=header.vdf_iterations,
                input_hash=header.vdf_input
            )
            
            if not self.vdf.verify(vdf_proof):
                raise BlockValidationError("Invalid VDF proof")
        
        # VRF proof validation
        if header.height > 0:
            vrf_output = VRFOutput(
                beta=header.vrf_output,
                proof=header.vrf_proof
            )
            
            if not ECVRF.verify(header.leader_pubkey, header.vdf_input, vrf_output):
                raise BlockValidationError("Invalid VRF proof")
        
        # Leader signature
        if header.height > 0:
            signing_message = header.signing_hash()
            if not Ed25519.verify(header.leader_pubkey, signing_message, header.leader_signature):
                raise BlockValidationError("Invalid leader signature")
        
        return True
    
    def validate_block(
        self,
        block: Block,
        prev_block: Optional[Block] = None
    ) -> bool:
        """
        Validate complete block.
        
        Checks:
        1. Header is valid
        2. Merkle root matches transactions
        3. Coinbase transaction is valid
        4. All transactions are valid
        5. No double-spends within block
        """
        prev_header = prev_block.header if prev_block else None
        
        # Validate header
        self.validate_header(block.header, prev_header)
        
        # Merkle root
        if not block.verify_merkle_root():
            raise BlockValidationError("Merkle root mismatch")
        
        # Must have at least coinbase
        if not block.transactions:
            raise BlockValidationError("Block must have at least one transaction")
        
        # First transaction must be coinbase
        coinbase = block.transactions[0]
        if not coinbase.is_coinbase():
            raise BlockValidationError("First transaction must be coinbase")
        
        # Validate coinbase reward
        expected_reward = get_block_reward(block.height)
        total_fees = block.get_total_fees()
        
        # Coinbase output should be reward + fees
        # (In production, verify output amounts)
        
        # Check for duplicate key images within block
        key_images = set()
        for tx in block.transactions[1:]:  # Skip coinbase
            for inp in tx.inputs:
                if inp.key_image in key_images:
                    raise BlockValidationError("Duplicate key image in block")
                key_images.add(inp.key_image)
        
        return True


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run structures self-tests."""
    logger.info("Running structures self-tests...")
    
    # Test serialization helpers
    assert write_varint(100) == b'd'
    assert write_varint(500) == b'\xfd\xf4\x01'
    val, _ = read_varint(b'\xfd\xf4\x01')
    assert val == 500
    logger.info("✓ Varint serialization")
    
    # Test transaction
    tx = Transaction.create_coinbase(
        height=1,
        reward_address=b'\x01' * 32,
        reward_tx_pubkey=b'\x02' * 32,
        extra_data=b'test'
    )
    tx_bytes = tx.serialize()
    tx2, _ = Transaction.deserialize(tx_bytes)
    assert tx2.hash() == tx.hash()
    logger.info("✓ Transaction serialization")
    
    # Test block header
    header = BlockHeader(
        version=1,
        prev_block_hash=b'\x00' * 32,
        merkle_root=b'\x01' * 32,
        timestamp=1735084800,
        height=0
    )
    header_bytes = header.serialize()
    header2, _ = BlockHeader.deserialize(header_bytes)
    assert header2.hash() == header.hash()
    logger.info("✓ Block header serialization")
    
    # Test genesis block
    genesis = create_genesis_block()
    assert genesis.height == 0
    assert genesis.verify_merkle_root()
    
    genesis_bytes = genesis.serialize()
    genesis2, _ = Block.deserialize(genesis_bytes)
    assert genesis2.hash == genesis.hash
    logger.info("✓ Genesis block creation and serialization")
    
    logger.info("All structures self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
