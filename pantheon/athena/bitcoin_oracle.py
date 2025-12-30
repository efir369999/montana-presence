"""
Montana v4.0 - Bitcoin Time Oracle

Bitcoin block anchoring as the primary time source.
Every Montana record references the latest Bitcoin block hash.

Bitcoin provides:
- Immutable ordering: Block N always precedes block N+1
- Global consensus: All nodes agree on block sequence
- Unforgeable timestamps: Cannot create fake blocks
- 15 years of security: Battle-tested infrastructure
- Decentralized: No single point of failure

99.98% uptime since 2009. Only 2 outages in history:
- 2010: 8h 27m
- 2013: 6h 20m
- Zero outages since 2013 (over 12 years)

Time is the ultimate proof.
"""

import time
import struct
import hashlib
import logging
import threading
import json
from typing import Optional, Tuple, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import IntEnum, auto
from datetime import datetime

logger = logging.getLogger("montana.bitcoin_oracle")


# ============================================================================
# CONSTANTS
# ============================================================================

HALVING_INTERVAL = 210_000  # blocks (~4 years)
EXPECTED_BLOCK_TIME = 600   # 10 minutes in seconds
MAX_BLOCK_VARIANCE = 1800   # 30 minutes max variance
FALLBACK_TRIGGER = 2        # 2 consecutive missed blocks triggers VDF fallback


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class BitcoinBlock:
    """Bitcoin block header for anchoring."""
    height: int
    hash: bytes
    prev_hash: bytes
    timestamp: int
    merkle_root: bytes = b'\x00' * 32
    version: int = 0
    bits: int = 0
    nonce: int = 0

    def serialize(self) -> bytes:
        """Serialize block header."""
        data = bytearray()
        data.extend(struct.pack('<Q', self.height))
        data.extend(self.hash)
        data.extend(self.prev_hash)
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(self.merkle_root)
        data.extend(struct.pack('<I', self.version))
        data.extend(struct.pack('<I', self.bits))
        data.extend(struct.pack('<I', self.nonce))
        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['BitcoinBlock', int]:
        """Deserialize block header."""
        height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        block_hash = data[offset:offset + 32]
        offset += 32

        prev_hash = data[offset:offset + 32]
        offset += 32

        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        merkle_root = data[offset:offset + 32]
        offset += 32

        version = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        bits = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        nonce = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        return cls(
            height=height,
            hash=block_hash,
            prev_hash=prev_hash,
            timestamp=timestamp,
            merkle_root=merkle_root,
            version=version,
            bits=bits,
            nonce=nonce
        ), offset

    @property
    def hash_hex(self) -> str:
        """Block hash as hex string (big-endian for display)."""
        return self.hash[::-1].hex()


@dataclass
class AnchorRecord:
    """
    Montana anchor record referencing Bitcoin block.

    Key Property: A record with btc_height N cannot exist
    before block N existed. Window of certainty: ~10 minutes.
    """
    timestamp: int              # Montana timestamp (wall clock)
    btc_height: int            # Bitcoin block height
    btc_hash: bytes            # Bitcoin block hash
    prev_anchor: bytes         # Previous anchor hash (SHA3)
    signature: bytes = b''     # SPHINCS+ signature

    def serialize(self) -> bytes:
        """Serialize anchor record."""
        data = bytearray()
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(struct.pack('<Q', self.btc_height))
        data.extend(self.btc_hash)
        data.extend(self.prev_anchor)

        # Variable length signature
        data.extend(struct.pack('<I', len(self.signature)))
        data.extend(self.signature)

        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['AnchorRecord', int]:
        """Deserialize anchor record."""
        timestamp = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        btc_height = struct.unpack_from('<Q', data, offset)[0]
        offset += 8

        btc_hash = data[offset:offset + 32]
        offset += 32

        prev_anchor = data[offset:offset + 32]
        offset += 32

        sig_len = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        signature = data[offset:offset + sig_len]
        offset += sig_len

        return cls(
            timestamp=timestamp,
            btc_height=btc_height,
            btc_hash=btc_hash,
            prev_anchor=prev_anchor,
            signature=signature
        ), offset

    def hash(self) -> bytes:
        """Compute anchor hash (SHA3-256)."""
        from hashlib import sha3_256
        data = struct.pack('<Q', self.timestamp)
        data += struct.pack('<Q', self.btc_height)
        data += self.btc_hash
        data += self.prev_anchor
        return sha3_256(data).digest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            't': datetime.utcfromtimestamp(self.timestamp).isoformat() + 'Z',
            'btc_height': self.btc_height,
            'btc_hash': self.btc_hash.hex()[:16] + '...',
            'prev': self.prev_anchor.hex()[:16] + '...',
            'sig': self.signature.hex()[:16] + '...' if self.signature else None
        }


@dataclass
class MontanaTime:
    """
    Montana time measured relative to Bitcoin halvings.
    Each halving resets the epoch counter.
    """
    epoch: int              # Halving epoch (0, 1, 2, ...)
    blocks: int             # Blocks since last halving
    saturation: float       # TIME saturation (0.0 to 1.0)
    btc_height: int         # Current Bitcoin height

    @classmethod
    def from_btc_height(cls, btc_height: int) -> 'MontanaTime':
        """
        Create Montana time from Bitcoin height.

        Montana measures time in Bitcoin blocks, not wall-clock seconds.
        """
        epoch = btc_height // HALVING_INTERVAL
        blocks_since_halving = btc_height % HALVING_INTERVAL
        saturation = min(blocks_since_halving / HALVING_INTERVAL, 1.0)

        return cls(
            epoch=epoch,
            blocks=blocks_since_halving,
            saturation=saturation,
            btc_height=btc_height
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'epoch': self.epoch,
            'blocks': self.blocks,
            'saturation': round(self.saturation, 6),
            'btc_height': self.btc_height,
            'approx_years': round(self.blocks / 52500, 2)  # ~52500 blocks/year
        }


class OracleStatus(IntEnum):
    """Bitcoin oracle status."""
    CONNECTED = auto()      # Connected to Bitcoin network
    SYNCING = auto()        # Syncing with Bitcoin network
    DISCONNECTED = auto()   # No connection
    FALLBACK = auto()       # Using VDF fallback


# ============================================================================
# BITCOIN ORACLE
# ============================================================================

class BitcoinOracle:
    """
    Bitcoin Time Oracle for Montana v4.0.

    Monitors Bitcoin blocks and provides time anchoring.
    Triggers VDF fallback if Bitcoin becomes unavailable.
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        on_new_block: Optional[Callable[[BitcoinBlock], None]] = None,
        on_fallback_needed: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize Bitcoin Oracle.

        Args:
            rpc_url: Bitcoin RPC endpoint (optional, can use SPV)
            on_new_block: Callback when new block arrives
            on_fallback_needed: Callback when VDF fallback is needed
        """
        self.rpc_url = rpc_url
        self.on_new_block_callback = on_new_block
        self.on_fallback_callback = on_fallback_needed

        # Block tracking
        self.last_block: Optional[BitcoinBlock] = None
        self.last_block_time: Optional[int] = None
        self.last_block_height: int = 0
        self.missed_blocks: int = 0

        # Anchor chain
        self.anchors: List[AnchorRecord] = []
        self.last_anchor_hash: bytes = b'\x00' * 32  # Genesis

        # Status
        self.status = OracleStatus.DISCONNECTED
        self._running = False
        self._lock = threading.RLock()

        # Block cache (limited size)
        self._block_cache: Dict[int, BitcoinBlock] = {}
        self._cache_max_size = 1000

        logger.info("Bitcoin Oracle initialized")

    def on_new_block(self, height: int, block_hash: bytes, timestamp: int,
                     prev_hash: bytes = b'\x00' * 32) -> AnchorRecord:
        """
        Process new Bitcoin block.

        Called when a new Bitcoin block is detected.
        Creates an anchor record and updates oracle state.

        Args:
            height: Bitcoin block height
            block_hash: Block hash (32 bytes)
            timestamp: Block timestamp
            prev_hash: Previous block hash

        Returns:
            AnchorRecord anchoring to this block
        """
        with self._lock:
            # Create block object
            block = BitcoinBlock(
                height=height,
                hash=block_hash,
                prev_hash=prev_hash,
                timestamp=timestamp
            )

            # Update state
            self.last_block = block
            self.last_block_time = int(time.time())
            self.last_block_height = height
            self.missed_blocks = 0
            self.status = OracleStatus.CONNECTED

            # Cache block
            self._cache_block(block)

            # Create anchor record
            anchor = AnchorRecord(
                timestamp=int(time.time()),
                btc_height=height,
                btc_hash=block_hash,
                prev_anchor=self.last_anchor_hash
            )

            # Update anchor chain
            self.last_anchor_hash = anchor.hash()
            self.anchors.append(anchor)

            # Limit anchor history
            if len(self.anchors) > 10000:
                self.anchors = self.anchors[-5000:]

            logger.info(
                f"New Bitcoin block: height={height}, "
                f"hash={block.hash_hex[:16]}..."
            )

            # Notify callback
            if self.on_new_block_callback:
                try:
                    self.on_new_block_callback(block)
                except Exception as e:
                    logger.error(f"Block callback error: {e}")

            return anchor

    def check_fallback_needed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if VDF fallback is needed.

        Trigger condition: 2 consecutive expected blocks not produced
        (~20+ minutes without progress).

        Rationale:
        - Normal variance can reach 30 minutes for a single block
        - Two consecutive missed blocks indicates serious network issue
        - False positives are acceptable (VDF is valid fallback)

        Returns:
            (needs_fallback, reason) tuple
        """
        with self._lock:
            if self.last_block_time is None:
                # No blocks yet - need initial sync
                return False, None

            current_time = int(time.time())
            time_since_last = current_time - self.last_block_time

            # Calculate expected blocks
            expected_blocks = time_since_last // EXPECTED_BLOCK_TIME

            if expected_blocks >= FALLBACK_TRIGGER:
                reason = (
                    f"Bitcoin appears down: {expected_blocks} expected blocks missed "
                    f"({time_since_last // 60} minutes since last block)"
                )

                self.missed_blocks = expected_blocks
                self.status = OracleStatus.FALLBACK

                logger.warning(f"VDF fallback triggered: {reason}")

                # Notify callback
                if self.on_fallback_callback:
                    try:
                        self.on_fallback_callback(reason)
                    except Exception as e:
                        logger.error(f"Fallback callback error: {e}")

                return True, reason

            return False, None

    def is_producing_blocks(self) -> bool:
        """
        Check if Bitcoin is producing blocks normally.

        Returns True if blocks are being produced within expected variance.
        """
        with self._lock:
            if self.last_block_time is None:
                return False

            current_time = int(time.time())
            time_since_last = current_time - self.last_block_time

            return time_since_last < MAX_BLOCK_VARIANCE

    def get_current_anchor(self) -> Optional[AnchorRecord]:
        """Get the most recent anchor record."""
        with self._lock:
            if self.anchors:
                return self.anchors[-1]
            return None

    def get_montana_time(self) -> Optional[MontanaTime]:
        """
        Get current Montana time based on latest Bitcoin block.

        Montana time is measured relative to Bitcoin halvings.
        """
        with self._lock:
            if self.last_block_height == 0:
                return None

            return MontanaTime.from_btc_height(self.last_block_height)

    def get_time_saturation(self, node_join_height: int) -> float:
        """
        Calculate TIME score saturation for a node.

        TIME resets to zero at every Bitcoin halving.
        No permanent dynasties - everyone competes fresh each epoch.

        Args:
            node_join_height: Bitcoin height when node joined

        Returns:
            Saturation value in [0.0, 1.0]
        """
        with self._lock:
            if self.last_block_height == 0:
                return 0.0

            current_height = self.last_block_height
            current_epoch = current_height // HALVING_INTERVAL
            node_epoch = node_join_height // HALVING_INTERVAL

            # If node joined in a previous epoch, reset their time
            if node_epoch < current_epoch:
                # Node gets credit only from start of current epoch
                epoch_start = current_epoch * HALVING_INTERVAL
                blocks_this_epoch = current_height - epoch_start
            else:
                # Node joined this epoch
                blocks_this_epoch = current_height - node_join_height

            return min(blocks_this_epoch / HALVING_INTERVAL, 1.0)

    def verify_anchor(self, anchor: AnchorRecord) -> Tuple[bool, str]:
        """
        Verify an anchor record.

        Checks:
        1. BTC height is valid (not in future)
        2. BTC hash matches cached block (if available)
        3. Timestamp is reasonable

        Args:
            anchor: Anchor record to verify

        Returns:
            (is_valid, reason) tuple
        """
        with self._lock:
            # Check height
            if anchor.btc_height > self.last_block_height + 10:
                return False, f"Height {anchor.btc_height} is too far in future"

            # Check cached block
            cached = self._block_cache.get(anchor.btc_height)
            if cached and cached.hash != anchor.btc_hash:
                return False, "Block hash mismatch with cache"

            # Check timestamp
            current_time = int(time.time())
            if anchor.timestamp > current_time + 3600:  # 1 hour tolerance
                return False, "Timestamp too far in future"

            return True, "Valid"

    def _cache_block(self, block: BitcoinBlock):
        """Cache a block with LRU eviction."""
        self._block_cache[block.height] = block

        # Evict oldest if over limit
        if len(self._block_cache) > self._cache_max_size:
            oldest = min(self._block_cache.keys())
            del self._block_cache[oldest]

    def get_block(self, height: int) -> Optional[BitcoinBlock]:
        """Get cached block by height."""
        return self._block_cache.get(height)

    def get_status(self) -> Dict[str, Any]:
        """Get oracle status."""
        with self._lock:
            montana_time = self.get_montana_time()

            return {
                'status': OracleStatus(self.status).name,
                'last_block_height': self.last_block_height,
                'last_block_hash': self.last_block.hash_hex[:16] + '...' if self.last_block else None,
                'last_block_time': self.last_block_time,
                'seconds_since_block': int(time.time()) - self.last_block_time if self.last_block_time else None,
                'missed_blocks': self.missed_blocks,
                'anchor_count': len(self.anchors),
                'montana_time': montana_time.to_dict() if montana_time else None,
                'is_producing': self.is_producing_blocks()
            }


# ============================================================================
# BLOCK MONITOR (for real Bitcoin node connection)
# ============================================================================

class BitcoinBlockMonitor:
    """
    Monitors Bitcoin network for new blocks.

    Can connect via:
    - Bitcoin Core RPC
    - Electrum servers
    - Block explorers API (fallback)
    - ZMQ notifications
    """

    def __init__(
        self,
        oracle: BitcoinOracle,
        poll_interval: int = 30  # seconds
    ):
        self.oracle = oracle
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start monitoring."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Bitcoin block monitor started")

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Bitcoin block monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Check if Bitcoin is producing blocks
                self.oracle.check_fallback_needed()

                # Poll for new blocks (implementation depends on connection method)
                self._poll_new_blocks()

            except Exception as e:
                logger.error(f"Monitor error: {e}")

            time.sleep(self.poll_interval)

    def _poll_new_blocks(self):
        """
        Poll for new Bitcoin blocks.

        Override this method to implement actual Bitcoin connection.
        Default implementation is a stub for testing.
        """
        pass

    def simulate_block(self, height: int, block_hash: Optional[bytes] = None):
        """
        Simulate receiving a new block (for testing).

        Args:
            height: Block height
            block_hash: Block hash (generated if not provided)
        """
        from hashlib import sha256

        if block_hash is None:
            block_hash = sha256(f"block_{height}".encode()).digest()

        prev_hash = sha256(f"block_{height - 1}".encode()).digest() if height > 0 else b'\x00' * 32
        timestamp = int(time.time())

        self.oracle.on_new_block(height, block_hash, timestamp, prev_hash)


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run Bitcoin Oracle self-tests."""
    logger.info("Running Bitcoin Oracle self-tests...")

    # Test MontanaTime
    mt = MontanaTime.from_btc_height(630000)  # 3rd halving
    assert mt.epoch == 3
    assert mt.blocks == 0
    assert mt.saturation == 0.0
    logger.info("  MontanaTime epoch calculation")

    mt2 = MontanaTime.from_btc_height(735000)  # Mid epoch 3
    assert mt2.epoch == 3
    assert mt2.blocks == 105000
    assert mt2.saturation == 0.5
    logger.info("  MontanaTime mid-epoch saturation")

    # Test BitcoinOracle
    oracle = BitcoinOracle()

    # Simulate blocks
    for i in range(5):
        anchor = oracle.on_new_block(
            height=840000 + i,  # Post 4th halving
            block_hash=hashlib.sha256(f"block_{i}".encode()).digest(),
            timestamp=int(time.time()) - (5 - i) * 600
        )
        assert anchor.btc_height == 840000 + i
    logger.info("  Block processing")

    # Check Montana time
    mt = oracle.get_montana_time()
    assert mt is not None
    assert mt.epoch == 4
    logger.info("  Montana time calculation")

    # Check no fallback needed
    needs_fallback, _ = oracle.check_fallback_needed()
    assert not needs_fallback
    logger.info("  Fallback check (normal)")

    # Simulate timeout
    oracle.last_block_time = int(time.time()) - 1500  # 25 minutes ago
    needs_fallback, reason = oracle.check_fallback_needed()
    assert needs_fallback
    assert "missed" in reason.lower()
    logger.info("  Fallback trigger")

    # Test TIME saturation
    saturation = oracle.get_time_saturation(840000)
    assert saturation > 0
    assert saturation < 0.001  # Very small for ~5 blocks
    logger.info("  TIME saturation")

    # Test status
    status = oracle.get_status()
    assert 'status' in status
    assert 'montana_time' in status
    logger.info("  Status reporting")

    logger.info("All Bitcoin Oracle tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
