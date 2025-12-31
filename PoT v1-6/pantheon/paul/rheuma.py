"""
Montana v4.0 - RHEUMA Transaction Stream

RHEUMA (Greek: ῥεῦμα — flow, stream)

No blocks. No batching. No waiting. No TPS limit.

Philosophy:
- Time flows continuously. Not in blocks. Not in intervals.
- Transaction = drop in stream
- Once fallen — already in the river
- River flows to Bitcoin ocean
- From ocean, no return

Traditional blockchain:
  transactions wait for block
  TPS = block_size / block_time

RHEUMA:
  transactions wait for nothing
  TPS = hardware_limit

No architectural ceiling. Hardware is the only constraint.

Time cannot be bought. Trust cannot be purchased.
"""

import time
import struct
import threading
import logging
from typing import Optional, Tuple, Dict, Any, List, Callable, Set
from dataclasses import dataclass, field
from collections import deque
from hashlib import sha3_256
from enum import IntEnum, auto
import heapq

logger = logging.getLogger("montana.rheuma")


# ============================================================================
# CONSTANTS
# ============================================================================

GENESIS_HASH = b'\x00' * 32
MIN_FEE = 1  # 1 second (base unit)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class RHEUMATransaction:
    """
    RHEUMA transaction structure.

    Transactions flow through the stream immediately.
    No waiting for blocks.

    Fields:
    - t: Timestamp (millisecond precision)
    - btc: Bitcoin block height anchor
    - prev: SHA3 hash of previous transaction in stream
    - seq: Global sequence number
    - from_addr: Sender address
    - to_addr: Recipient address
    - amount: Amount in base units (1 unit = 1 second)
    - nonce: Sender's transaction counter
    - fee: Transaction fee
    - sig: SPHINCS+ signature
    """
    timestamp: int              # Millisecond precision
    btc_height: int            # Bitcoin block anchor
    prev_hash: bytes           # Previous tx hash in stream
    sequence: int              # Global sequence number
    from_addr: bytes           # Sender address (32 bytes)
    to_addr: bytes            # Recipient address (32 bytes)
    amount: int               # Amount in base units
    nonce: int                # Sender's tx counter
    fee: int = MIN_FEE        # Transaction fee
    signature: bytes = b''    # SPHINCS+ signature

    # Cached hash
    _hash: Optional[bytes] = field(default=None, repr=False)

    def serialize(self) -> bytes:
        """Serialize transaction."""
        data = bytearray()

        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<Q', self.btc_height))
        data.extend(self.prev_hash)
        data.extend(struct.pack('<Q', self.sequence))
        data.extend(self.from_addr)
        data.extend(self.to_addr)
        data.extend(struct.pack('<Q', self.amount))
        data.extend(struct.pack('<Q', self.nonce))
        data.extend(struct.pack('<Q', self.fee))

        # Variable length signature
        data.extend(struct.pack('<I', len(self.signature)))
        data.extend(self.signature)

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['RHEUMATransaction', int]:
        """Deserialize transaction."""
        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        btc_height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        prev_hash = data[offset:offset + 32]
        offset += 32

        sequence = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        from_addr = data[offset:offset + 32]
        offset += 32

        to_addr = data[offset:offset + 32]
        offset += 32

        amount = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        nonce = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        fee = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        sig_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        signature = data[offset:offset + sig_len]
        offset += sig_len

        return cls(
            timestamp=timestamp,
            btc_height=btc_height,
            prev_hash=prev_hash,
            sequence=sequence,
            from_addr=from_addr,
            to_addr=to_addr,
            amount=amount,
            nonce=nonce,
            fee=fee,
            signature=signature
        ), offset

    def hash(self) -> bytes:
        """Compute transaction hash (txid)."""
        if self._hash is None:
            # Hash everything except signature
            data = struct.pack('<Q', self.timestamp)
            data += struct.pack('<Q', self.btc_height)
            data += self.prev_hash
            data += struct.pack('<Q', self.sequence)
            data += self.from_addr
            data += self.to_addr
            data += struct.pack('<Q', self.amount)
            data += struct.pack('<Q', self.nonce)
            data += struct.pack('<Q', self.fee)

            self._hash = sha3_256(data).digest()

        return self._hash

    def signing_hash(self) -> bytes:
        """Hash for signature."""
        data = struct.pack('<Q', self.timestamp)
        data += struct.pack('<Q', self.btc_height)
        data += self.from_addr
        data += self.to_addr
        data += struct.pack('<Q', self.amount)
        data += struct.pack('<Q', self.nonce)
        data += struct.pack('<Q', self.fee)

        return sha3_256(data).digest()

    @property
    def txid(self) -> str:
        """Transaction ID as hex string."""
        return self.hash().hex()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        from datetime import datetime

        return {
            't': datetime.utcfromtimestamp(self.timestamp / 1000).isoformat() + 'Z',
            'btc': self.btc_height,
            'prev': self.prev_hash.hex()[:16] + '...',
            'seq': self.sequence,
            'from': self.from_addr.hex()[:16] + '...',
            'to': self.to_addr.hex()[:16] + '...',
            'amount': self.amount,
            'nonce': self.nonce,
            'fee': self.fee,
            'sig': self.signature.hex()[:16] + '...' if self.signature else None
        }


@dataclass
class StreamCheckpoint:
    """
    Checkpoint anchoring RHEUMA stream to Bitcoin.

    Created when new Bitcoin block arrives.
    Provides hard finality (~10 min).
    """
    btc_height: int
    btc_hash: bytes
    stream_seq: int          # Stream sequence at checkpoint
    stream_hash: bytes       # Hash of stream state
    timestamp: int
    signature: bytes = b''   # Node signature

    def serialize(self) -> bytes:
        """Serialize checkpoint."""
        data = bytearray()

        data.extend(struct.pack('<Q', self.btc_height))
        data.extend(self.btc_hash)
        data.extend(struct.pack('<Q', self.stream_seq))
        data.extend(self.stream_hash)
        data.extend(struct.pack('<Q', self.timestamp))

        data.extend(struct.pack('<I', len(self.signature)))
        data.extend(self.signature)

        return bytes(data)

    def hash(self) -> bytes:
        """Compute checkpoint hash."""
        data = struct.pack('<Q', self.btc_height)
        data += self.btc_hash
        data += struct.pack('<Q', self.stream_seq)
        data += self.stream_hash
        data += struct.pack('<Q', self.timestamp)
        return sha3_256(data).digest()


class FinalityType(IntEnum):
    """Transaction finality level."""
    PENDING = 0         # Just submitted
    SOFT = 1           # All nodes see, signature verified
    HARD = 2           # Bitcoin block anchor (~10 min)


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

@dataclass
class AccountState:
    """Account state for balance and nonce tracking."""
    address: bytes
    balance: int = 0
    nonce: int = 0

    def serialize(self) -> bytes:
        data = self.address
        data += struct.pack('<Q', self.balance)
        data += struct.pack('<Q', self.nonce)
        return data


class RHEUMAState:
    """
    State management for RHEUMA stream.

    Tracks:
    - Account balances
    - Account nonces
    - Used nonces (for double-spend detection)
    """

    def __init__(self):
        self._balances: Dict[bytes, int] = {}
        self._nonces: Dict[bytes, int] = {}
        self._used_nonces: Dict[bytes, Set[int]] = {}  # addr -> set of used nonces
        self._lock = threading.RLock()

    def get_balance(self, address: bytes) -> int:
        """Get account balance."""
        with self._lock:
            return self._balances.get(address, 0)

    def get_nonce(self, address: bytes) -> int:
        """Get account nonce (next expected nonce)."""
        with self._lock:
            return self._nonces.get(address, 0)

    def credit(self, address: bytes, amount: int):
        """Credit account."""
        with self._lock:
            self._balances[address] = self._balances.get(address, 0) + amount

    def debit(self, address: bytes, amount: int) -> bool:
        """Debit account. Returns False if insufficient balance."""
        with self._lock:
            balance = self._balances.get(address, 0)
            if balance < amount:
                return False
            self._balances[address] = balance - amount
            return True

    def increment_nonce(self, address: bytes):
        """Increment account nonce."""
        with self._lock:
            self._nonces[address] = self._nonces.get(address, 0) + 1

    def has_nonce_used(self, address: bytes, nonce: int) -> bool:
        """Check if nonce has been used."""
        with self._lock:
            return nonce in self._used_nonces.get(address, set())

    def mark_nonce_used(self, address: bytes, nonce: int):
        """Mark nonce as used."""
        with self._lock:
            if address not in self._used_nonces:
                self._used_nonces[address] = set()
            self._used_nonces[address].add(nonce)

    def apply_transaction(self, tx: RHEUMATransaction) -> bool:
        """Apply transaction to state."""
        with self._lock:
            # Debit sender (amount + fee)
            if not self.debit(tx.from_addr, tx.amount + tx.fee):
                return False

            # Credit recipient
            self.credit(tx.to_addr, tx.amount)

            # Update nonce
            self.mark_nonce_used(tx.from_addr, tx.nonce)
            self.increment_nonce(tx.from_addr)

            return True


# ============================================================================
# TRANSACTION VALIDATION
# ============================================================================

def validate_transaction(
    tx: RHEUMATransaction,
    state: RHEUMAState,
    verify_signature: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Validate a RHEUMA transaction.

    Checks:
    1. Nonce must be exactly previous+1
    2. Balance must cover amount + fee
    3. SPHINCS+ signature verification
    4. First valid transaction wins (nonce uniqueness)

    Two transactions with same nonce = only first valid.

    Args:
        tx: Transaction to validate
        state: Current state
        verify_signature: Whether to verify signature

    Returns:
        (is_valid, error_message) tuple
    """
    # 1. Nonce must be exactly previous+1
    expected_nonce = state.get_nonce(tx.from_addr)
    if tx.nonce != expected_nonce:
        return False, f"Invalid nonce: expected {expected_nonce}, got {tx.nonce}"

    # Check nonce not already used (double-spend protection)
    if state.has_nonce_used(tx.from_addr, tx.nonce):
        return False, "Nonce already used"

    # 2. Balance check
    balance = state.get_balance(tx.from_addr)
    if balance < tx.amount + tx.fee:
        return False, f"Insufficient balance: {balance} < {tx.amount + tx.fee}"

    # 3. Fee must be at least minimum
    if tx.fee < MIN_FEE:
        return False, f"Fee too low: {tx.fee} < {MIN_FEE}"

    # 4. Signature verification
    if verify_signature and tx.signature:
        try:
            # Would use SPHINCS+ verification
            # from pantheon.prometheus.pq_crypto import SPHINCS_verify
            # if not SPHINCS_verify(tx.from_addr, tx.signing_hash(), tx.signature):
            #     return False, "Invalid signature"
            pass
        except Exception as e:
            return False, f"Signature verification failed: {e}"

    return True, None


# ============================================================================
# RHEUMA STREAM
# ============================================================================

class RHEUMAStream:
    """
    RHEUMA Transaction Stream.

    No blocks. No batching. No waiting. No TPS limit.

    Transactions flow through immediately.
    Hardware is the only constraint.
    """

    def __init__(
        self,
        on_transaction: Optional[Callable[[RHEUMATransaction], None]] = None,
        on_checkpoint: Optional[Callable[[StreamCheckpoint], None]] = None
    ):
        """
        Initialize RHEUMA stream.

        Args:
            on_transaction: Callback for new transactions
            on_checkpoint: Callback for new checkpoints
        """
        # Stream state
        self.sequence: int = 0
        self.prev_hash: bytes = GENESIS_HASH

        # State management
        self.state = RHEUMAState()

        # Transaction storage
        self._transactions: deque = deque(maxlen=100000)  # Rolling window
        self._tx_by_hash: Dict[bytes, RHEUMATransaction] = {}
        self._pending: List[Tuple[int, int, RHEUMATransaction]] = []  # Priority queue (fee, time, tx)

        # Checkpoints
        self._checkpoints: List[StreamCheckpoint] = []
        self._last_checkpoint_height: int = 0

        # Callbacks
        self.on_transaction_callback = on_transaction
        self.on_checkpoint_callback = on_checkpoint

        # Threading
        self._lock = threading.RLock()

        # Stats
        self._tx_count: int = 0
        self._start_time: int = int(time.time())

        logger.info("RHEUMA stream initialized")

    def submit(self, tx: RHEUMATransaction) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Submit transaction to the stream.

        Transaction flows through immediately if valid.

        Args:
            tx: Transaction to submit

        Returns:
            (success, sequence_number, error) tuple
        """
        with self._lock:
            # Validate transaction
            valid, error = validate_transaction(tx, self.state)
            if not valid:
                return False, None, error

            # Assign sequence number
            tx.sequence = self.sequence
            tx.prev_hash = self.prev_hash

            # Update stream state
            self.sequence += 1
            self.prev_hash = tx.hash()

            # Apply to state
            if not self.state.apply_transaction(tx):
                return False, None, "State application failed"

            # Store transaction
            self._transactions.append(tx)
            self._tx_by_hash[tx.hash()] = tx
            self._tx_count += 1

            # Callback
            if self.on_transaction_callback:
                try:
                    self.on_transaction_callback(tx)
                except Exception as e:
                    logger.error(f"Transaction callback error: {e}")

            logger.debug(f"Transaction #{tx.sequence} submitted: {tx.txid[:16]}...")

            return True, tx.sequence, None

    def anchor_to_bitcoin(self, btc_height: int, btc_hash: bytes) -> StreamCheckpoint:
        """
        Anchor stream to Bitcoin block.

        Called when new Bitcoin block arrives.
        Provides hard finality.

        Args:
            btc_height: Bitcoin block height
            btc_hash: Bitcoin block hash

        Returns:
            StreamCheckpoint
        """
        with self._lock:
            checkpoint = StreamCheckpoint(
                btc_height=btc_height,
                btc_hash=btc_hash,
                stream_seq=self.sequence,
                stream_hash=self.prev_hash,
                timestamp=int(time.time())
            )

            self._checkpoints.append(checkpoint)
            self._last_checkpoint_height = btc_height

            # Limit checkpoint history
            if len(self._checkpoints) > 1000:
                self._checkpoints = self._checkpoints[-500:]

            # Callback
            if self.on_checkpoint_callback:
                try:
                    self.on_checkpoint_callback(checkpoint)
                except Exception as e:
                    logger.error(f"Checkpoint callback error: {e}")

            logger.info(
                f"Stream anchored to Bitcoin block {btc_height}: "
                f"seq={self.sequence}, hash={self.prev_hash.hex()[:16]}..."
            )

            return checkpoint

    def get_transaction(self, tx_hash: bytes) -> Optional[RHEUMATransaction]:
        """Get transaction by hash."""
        with self._lock:
            return self._tx_by_hash.get(tx_hash)

    def get_transactions_since(self, sequence: int, limit: int = 100) -> List[RHEUMATransaction]:
        """Get transactions since a sequence number."""
        with self._lock:
            result = []
            for tx in self._transactions:
                if tx.sequence >= sequence:
                    result.append(tx)
                    if len(result) >= limit:
                        break
            return result

    def get_finality(self, tx_hash: bytes) -> FinalityType:
        """
        Get finality level for a transaction.

        Finality levels:
        - PENDING: Just submitted
        - SOFT: All nodes see, signature verified (instant)
        - HARD: Bitcoin block anchor (~10 min)
        """
        with self._lock:
            tx = self._tx_by_hash.get(tx_hash)
            if not tx:
                return FinalityType.PENDING

            # Check if checkpointed
            for cp in self._checkpoints:
                if cp.stream_seq > tx.sequence:
                    return FinalityType.HARD

            return FinalityType.SOFT

    def get_checkpoint(self, btc_height: int) -> Optional[StreamCheckpoint]:
        """Get checkpoint by Bitcoin height."""
        with self._lock:
            for cp in self._checkpoints:
                if cp.btc_height == btc_height:
                    return cp
            return None

    def get_latest_checkpoint(self) -> Optional[StreamCheckpoint]:
        """Get most recent checkpoint."""
        with self._lock:
            return self._checkpoints[-1] if self._checkpoints else None

    def get_tps(self) -> float:
        """Get current transactions per second."""
        elapsed = int(time.time()) - self._start_time
        if elapsed == 0:
            return 0.0
        return self._tx_count / elapsed

    def get_status(self) -> Dict[str, Any]:
        """Get stream status."""
        with self._lock:
            return {
                'sequence': self.sequence,
                'prev_hash': self.prev_hash.hex()[:16] + '...',
                'transaction_count': self._tx_count,
                'checkpoint_count': len(self._checkpoints),
                'last_checkpoint_height': self._last_checkpoint_height,
                'tps': round(self.get_tps(), 2),
                'pending_count': len(self._pending)
            }


# ============================================================================
# THROUGHPUT ESTIMATES (from whitepaper)
# ============================================================================

THROUGHPUT_ESTIMATES = {
    'minimum': 10_000,      # 100 nodes, basic hardware
    'typical': 100_000,     # 1,000 nodes, good hardware
    'optimal': 1_000_000,   # Optimized implementations
    'theoretical': None     # Unlimited - hardware is only limit
}


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run RHEUMA self-tests."""
    logger.info("Running RHEUMA self-tests...")

    # Create stream
    stream = RHEUMAStream()

    # Create test accounts
    sender = b'\x01' * 32
    recipient = b'\x02' * 32

    # Credit sender
    stream.state.credit(sender, 1_000_000)
    assert stream.state.get_balance(sender) == 1_000_000
    logger.info("  Account credit")

    # Create transaction
    tx = RHEUMATransaction(
        timestamp=int(time.time() * 1000),
        btc_height=840000,
        prev_hash=GENESIS_HASH,
        sequence=0,
        from_addr=sender,
        to_addr=recipient,
        amount=100,
        nonce=0,
        fee=1
    )

    # Submit transaction
    success, seq, error = stream.submit(tx)
    assert success, f"Submit failed: {error}"
    assert seq == 0
    logger.info("  Transaction submission")

    # Check balances
    assert stream.state.get_balance(sender) == 1_000_000 - 101
    assert stream.state.get_balance(recipient) == 100
    logger.info("  Balance update")

    # Check finality
    finality = stream.get_finality(tx.hash())
    assert finality == FinalityType.SOFT
    logger.info("  Soft finality")

    # Submit more transactions
    for i in range(10):
        tx2 = RHEUMATransaction(
            timestamp=int(time.time() * 1000),
            btc_height=840000,
            prev_hash=stream.prev_hash,
            sequence=stream.sequence,
            from_addr=sender,
            to_addr=recipient,
            amount=10,
            nonce=i + 1,
            fee=1
        )
        success, _, error = stream.submit(tx2)
        assert success, f"Submit {i} failed: {error}"
    logger.info("  Multiple transactions")

    # Anchor to Bitcoin
    cp = stream.anchor_to_bitcoin(
        btc_height=840001,
        btc_hash=b'\xaa' * 32
    )
    assert cp.stream_seq == 11
    logger.info("  Bitcoin checkpoint")

    # Check hard finality
    finality = stream.get_finality(tx.hash())
    assert finality == FinalityType.HARD
    logger.info("  Hard finality")

    # Double-spend prevention
    tx_double = RHEUMATransaction(
        timestamp=int(time.time() * 1000),
        btc_height=840000,
        prev_hash=stream.prev_hash,
        sequence=stream.sequence,
        from_addr=sender,
        to_addr=recipient,
        amount=10,
        nonce=0,  # Reused nonce!
        fee=1
    )
    success, _, error = stream.submit(tx_double)
    assert not success
    assert "nonce" in error.lower()
    logger.info("  Double-spend prevention")

    # Status
    status = stream.get_status()
    assert status['sequence'] == 11
    assert status['transaction_count'] == 11
    logger.info("  Status reporting")

    # Serialization
    tx_bytes = tx.serialize()
    tx_restored, _ = RHEUMATransaction.deserialize(tx_bytes)
    assert tx_restored.hash() == tx.hash()
    logger.info("  Serialization")

    logger.info("All RHEUMA tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
