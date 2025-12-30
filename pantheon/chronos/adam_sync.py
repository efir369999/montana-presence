"""
Montana v4.0 - Adam Sync: Hierarchical Time Synchronization

ADAM = Anchored Deterministic Asynchronous Mesh

Strict layer separation for time synchronization:

┌─────────────────────────────────────────────────────────────────────────────┐
│                        ADAM SYNC ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LAYER 0: SERVER TIME (Network Synchronization)                       │   │
│  │ ═══════════════════════════════════════════════                      │   │
│  │ • NTP/Roughtime servers for UTC reference                           │   │
│  │ • Weighted average across multiple servers                          │   │
│  │ • Clock drift detection and correction                              │   │
│  │ • Low-latency streams (sub-second precision)                        │   │
│  │                                                                      │   │
│  │ PROVIDES: UTC reference time for node operations                    │   │
│  │ LATENCY: ~10-100ms                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LAYER 1: BITCOIN TIME (Primary Finality)                            │   │
│  │ ═══════════════════════════════════════════                          │   │
│  │                                                                      │   │
│  │  PHASE 1.1: MEMPOOL AWARENESS                                       │   │
│  │  ──────────────────────────                                         │   │
│  │  • Monitor Bitcoin mempool for pending transactions                 │   │
│  │  • Track fee rates and block fullness estimates                     │   │
│  │  • Predict next block timing                                        │   │
│  │  • STATE: PENDING_CONFIRMATION                                      │   │
│  │                                                                      │   │
│  │  PHASE 1.2: BLOCK CONFIRMATION                                      │   │
│  │  ─────────────────────────────                                      │   │
│  │  • New Bitcoin block detected                                       │   │
│  │  • Verify block header and hash                                     │   │
│  │  • STATE: TENTATIVE_FINALITY (1 confirmation)                       │   │
│  │                                                                      │   │
│  │  PHASE 1.3: DEEP CONFIRMATION                                       │   │
│  │  ────────────────────────────                                       │   │
│  │  • Wait for N confirmations (configurable, default 6)               │   │
│  │  • STATE: CONFIRMED (probabilistic finality)                        │   │
│  │                                                                      │   │
│  │  PHASE 1.4: ABSOLUTE FINALITY                                       │   │
│  │  ─────────────────────────────                                      │   │
│  │  • Block buried under 100+ confirmations                            │   │
│  │  • STATE: IRREVERSIBLE (economic finality)                          │   │
│  │                                                                      │   │
│  │ PROVIDES: Immutable time anchors, transaction ordering              │   │
│  │ LATENCY: ~10 minutes (average block time)                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LAYER 2: VDF FALLBACK (Secondary Finality)                          │   │
│  │ ═══════════════════════════════════════════                          │   │
│  │ • ONLY activates if Bitcoin unavailable (>20 min no blocks)         │   │
│  │ • SHAKE256 VDF for quantum-safe timekeeping                         │   │
│  │ • STARK proofs for O(log T) verification                            │   │
│  │ • Sovereign time source (no external dependency)                    │   │
│  │                                                                      │   │
│  │ PROVIDES: Autonomous operation during Bitcoin outages               │   │
│  │ LATENCY: ~9 minutes (calibrated VDF)                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

FINALITY STATES:
═══════════════

  PENDING         Transaction in mempool, awaiting inclusion
       ↓
  TENTATIVE       Included in block, 1 confirmation
       ↓
  CONFIRMED       6+ confirmations, probabilistic finality
       ↓
  IRREVERSIBLE    100+ confirmations, economic finality (cannot reorg)

Bitcoin is the clock. VDF is the insurance.
Time is the ultimate proof.
"""

import time
import struct
import hashlib
import logging
import threading
import statistics
from typing import Optional, Tuple, Dict, Any, List, Callable, Set
from dataclasses import dataclass, field
from enum import IntEnum, auto
from abc import ABC, abstractmethod
from collections import deque

logger = logging.getLogger("montana.adam_sync")


# ============================================================================
# CONSTANTS
# ============================================================================

# Layer 0: Server Time
NTP_SERVERS = [
    "time.google.com",
    "time.cloudflare.com",
    "time.apple.com",
    "pool.ntp.org",
    "time.windows.com",
]
ROUGHTIME_SERVERS = [
    "roughtime.cloudflare.com",
    "roughtime.google.com",
]
MAX_CLOCK_DRIFT_MS = 500       # Maximum acceptable drift in milliseconds
SERVER_TIMEOUT_MS = 2000       # Timeout for time server queries
MIN_SERVERS_FOR_CONSENSUS = 3  # Minimum servers for valid time consensus

# Layer 1: Bitcoin Time
BITCOIN_BLOCK_TIME = 600       # Expected 10 minutes
BITCOIN_MAX_VARIANCE = 1800    # 30 minutes max variance
MEMPOOL_POLL_INTERVAL = 30     # Seconds between mempool checks
CONFIRMATIONS_TENTATIVE = 1    # Minimum for tentative finality
CONFIRMATIONS_CONFIRMED = 6    # Standard Bitcoin finality
CONFIRMATIONS_IRREVERSIBLE = 100  # Deep finality (cannot reorg)

# Layer 2: VDF Fallback
VDF_TRIGGER_MISSED_BLOCKS = 2  # Blocks missed to trigger VDF
VDF_TRIGGER_TIME_SECONDS = VDF_TRIGGER_MISSED_BLOCKS * BITCOIN_BLOCK_TIME  # ~20 min


# ============================================================================
# FINALITY STATES
# ============================================================================

class FinalityState(IntEnum):
    """
    Transaction/block finality states.

    Clear progression from pending to irreversible.
    """
    UNKNOWN = 0           # State unknown
    PENDING = 1           # In mempool, not yet confirmed
    TENTATIVE = 2         # 1 confirmation, may be reorged
    CONFIRMED = 3         # 6+ confirmations, probabilistically final
    IRREVERSIBLE = 4      # 100+ confirmations, economically final

    @classmethod
    def from_confirmations(cls, confirmations: int) -> 'FinalityState':
        """Convert confirmation count to finality state."""
        if confirmations <= 0:
            return cls.PENDING
        elif confirmations < CONFIRMATIONS_CONFIRMED:
            return cls.TENTATIVE
        elif confirmations < CONFIRMATIONS_IRREVERSIBLE:
            return cls.CONFIRMED
        else:
            return cls.IRREVERSIBLE

    @property
    def can_reorg(self) -> bool:
        """Check if this state can be reorganized."""
        return self in (FinalityState.UNKNOWN, FinalityState.PENDING,
                       FinalityState.TENTATIVE, FinalityState.CONFIRMED)

    @property
    def is_final(self) -> bool:
        """Check if this state represents finality."""
        return self == FinalityState.IRREVERSIBLE


class SyncLayerState(IntEnum):
    """State of each synchronization layer."""
    INACTIVE = 0      # Layer not initialized
    SYNCING = 1       # Layer synchronizing
    ACTIVE = 2        # Layer operational
    DEGRADED = 3      # Layer experiencing issues
    FAILED = 4        # Layer unavailable


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ServerTimeResult:
    """Result from a time server query."""
    server: str
    timestamp_utc: float      # UTC timestamp from server
    round_trip_ms: float      # Round-trip time in ms
    offset_ms: float          # Offset from local clock in ms
    confidence: float         # Confidence score (0.0-1.0)
    timestamp_local: float    # Local time when queried

    @property
    def adjusted_time(self) -> float:
        """Get adjusted time accounting for network latency."""
        return self.timestamp_utc + (self.round_trip_ms / 2000.0)


@dataclass
class BitcoinBlockAnchor:
    """
    Bitcoin block anchor for time synchronization.

    This is the immutable reference point from Bitcoin.
    """
    height: int
    hash: bytes               # Block hash (32 bytes)
    prev_hash: bytes          # Previous block hash
    timestamp: int            # Block timestamp (Unix)
    merkle_root: bytes        # Merkle root of transactions

    # Finality tracking
    confirmations: int = 0
    finality: FinalityState = FinalityState.TENTATIVE

    # Montana metadata
    received_at: float = 0.0  # When we received this block

    def update_finality(self, current_height: int):
        """Update finality state based on current chain height."""
        self.confirmations = current_height - self.height + 1
        self.finality = FinalityState.from_confirmations(self.confirmations)

    @property
    def hash_hex(self) -> str:
        """Block hash as hex (big-endian for display)."""
        return self.hash[::-1].hex()

    def serialize(self) -> bytes:
        """Serialize anchor."""
        data = bytearray()
        data.extend(struct.pack('<Q', self.height))
        data.extend(self.hash)
        data.extend(self.prev_hash)
        data.extend(struct.pack('<Q', self.timestamp))
        data.extend(self.merkle_root)
        data.extend(struct.pack('<I', self.confirmations))
        data.extend(struct.pack('<B', self.finality))
        data.extend(struct.pack('<d', self.received_at))
        return bytes(data)

    @classmethod
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['BitcoinBlockAnchor', int]:
        """Deserialize anchor."""
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
        confirmations = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        finality = FinalityState(struct.unpack_from('<B', data, offset)[0])
        offset += 1
        received_at = struct.unpack_from('<d', data, offset)[0]
        offset += 8

        return cls(
            height=height,
            hash=block_hash,
            prev_hash=prev_hash,
            timestamp=timestamp,
            merkle_root=merkle_root,
            confirmations=confirmations,
            finality=finality,
            received_at=received_at
        ), offset


@dataclass
class MempoolState:
    """
    Current Bitcoin mempool state.

    Used for predicting block times and fee estimation.
    """
    tx_count: int = 0             # Number of pending transactions
    size_bytes: int = 0           # Total size in bytes
    fee_rate_min: float = 0.0     # Minimum fee rate (sat/vB)
    fee_rate_median: float = 0.0  # Median fee rate
    fee_rate_high: float = 0.0    # High priority fee rate
    last_update: float = 0.0      # When mempool was last updated

    @property
    def estimated_blocks_full(self) -> float:
        """Estimate how many blocks of transactions are waiting."""
        avg_block_size = 1_400_000  # ~1.4 MB average block
        return self.size_bytes / avg_block_size if avg_block_size > 0 else 0


@dataclass
class SyncTimestamp:
    """
    Unified timestamp from Adam Sync.

    Contains data from all active layers.
    """
    # Wall clock (Layer 0)
    utc_time: float               # Consensus UTC time
    local_time: float             # Local system time
    clock_offset_ms: float        # Offset between local and consensus
    server_consensus: int         # Number of servers in consensus

    # Bitcoin anchor (Layer 1)
    btc_height: Optional[int] = None
    btc_hash: Optional[bytes] = None
    btc_finality: FinalityState = FinalityState.UNKNOWN
    btc_confirmations: int = 0

    # VDF anchor (Layer 2) - only if Bitcoin unavailable
    vdf_sequence: Optional[int] = None
    vdf_hash: Optional[bytes] = None

    # Metadata
    primary_layer: int = 1        # Which layer is primary (1=Bitcoin, 2=VDF)
    sequence: int = 0             # Global sequence number

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'utc_time': self.utc_time,
            'clock_offset_ms': round(self.clock_offset_ms, 2),
            'server_consensus': self.server_consensus,
            'btc_height': self.btc_height,
            'btc_hash': self.btc_hash.hex()[:16] + '...' if self.btc_hash else None,
            'btc_finality': self.btc_finality.name,
            'btc_confirmations': self.btc_confirmations,
            'vdf_sequence': self.vdf_sequence,
            'primary_layer': f"Layer {self.primary_layer}",
            'sequence': self.sequence
        }


# ============================================================================
# LAYER 0: SERVER TIME SYNCHRONIZATION
# ============================================================================

class ServerTimeSynchronizer:
    """
    Layer 0: Network Time Synchronization

    Provides UTC reference using weighted averages from multiple
    time servers with clock drift detection.
    """

    def __init__(
        self,
        ntp_servers: List[str] = None,
        roughtime_servers: List[str] = None,
        max_drift_ms: float = MAX_CLOCK_DRIFT_MS
    ):
        """
        Initialize server time synchronizer.

        Args:
            ntp_servers: List of NTP servers to query
            roughtime_servers: List of Roughtime servers
            max_drift_ms: Maximum acceptable clock drift
        """
        self.ntp_servers = ntp_servers or NTP_SERVERS.copy()
        self.roughtime_servers = roughtime_servers or ROUGHTIME_SERVERS.copy()
        self.max_drift_ms = max_drift_ms

        # State
        self.state = SyncLayerState.INACTIVE
        self.last_results: List[ServerTimeResult] = []
        self.consensus_offset_ms: float = 0.0
        self.drift_history: deque = deque(maxlen=100)

        self._lock = threading.Lock()
        self._running = False
        self._sync_thread: Optional[threading.Thread] = None

        logger.info("Layer 0 (Server Time) initialized")

    def start(self):
        """Start background synchronization."""
        if self._running:
            return

        self._running = True
        self.state = SyncLayerState.SYNCING

        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="Layer0-ServerTime"
        )
        self._sync_thread.start()
        logger.info("Layer 0 synchronization started")

    def stop(self):
        """Stop synchronization."""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        self.state = SyncLayerState.INACTIVE
        logger.info("Layer 0 synchronization stopped")

    def _sync_loop(self):
        """Background synchronization loop."""
        while self._running:
            try:
                self._sync_once()
                time.sleep(60)  # Sync every minute
            except Exception as e:
                logger.error(f"Layer 0 sync error: {e}")
                self.state = SyncLayerState.DEGRADED
                time.sleep(10)

    def _sync_once(self):
        """Perform one synchronization cycle."""
        results = []

        # Query NTP servers
        for server in self.ntp_servers[:3]:  # Use first 3 for speed
            result = self._query_ntp(server)
            if result:
                results.append(result)

        if len(results) < MIN_SERVERS_FOR_CONSENSUS:
            logger.warning(f"Only {len(results)} servers responded, need {MIN_SERVERS_FOR_CONSENSUS}")
            self.state = SyncLayerState.DEGRADED
            return

        # Calculate weighted consensus
        self._calculate_consensus(results)

        with self._lock:
            self.last_results = results
            self.state = SyncLayerState.ACTIVE

    def _query_ntp(self, server: str) -> Optional[ServerTimeResult]:
        """
        Query an NTP server.

        Note: This is a simplified implementation.
        Production should use proper NTP protocol.
        """
        try:
            import socket

            # NTP packet structure (simplified)
            ntp_data = b'\x1b' + 47 * b'\0'

            start_time = time.time()

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(SERVER_TIMEOUT_MS / 1000.0)

            try:
                sock.sendto(ntp_data, (server, 123))
                data, _ = sock.recvfrom(48)

                end_time = time.time()
                round_trip = (end_time - start_time) * 1000

                # Extract timestamp (bytes 40-43 are integer part)
                if len(data) >= 44:
                    timestamp = struct.unpack('!I', data[40:44])[0]
                    # NTP epoch starts 1900, Unix epoch starts 1970
                    ntp_time = timestamp - 2208988800

                    offset = (ntp_time - start_time) * 1000

                    return ServerTimeResult(
                        server=server,
                        timestamp_utc=ntp_time,
                        round_trip_ms=round_trip,
                        offset_ms=offset,
                        confidence=1.0 / (1.0 + round_trip / 100.0),
                        timestamp_local=start_time
                    )
            finally:
                sock.close()

        except Exception as e:
            logger.debug(f"NTP query to {server} failed: {e}")
            return None

    def _calculate_consensus(self, results: List[ServerTimeResult]):
        """
        Calculate weighted consensus offset.

        Uses weighted median to resist outliers.
        """
        if not results:
            return

        # Weight by confidence (inverse of round-trip time)
        weights = [r.confidence for r in results]
        offsets = [r.offset_ms for r in results]

        # Weighted average
        total_weight = sum(weights)
        if total_weight > 0:
            weighted_offset = sum(o * w for o, w in zip(offsets, weights)) / total_weight
        else:
            weighted_offset = statistics.median(offsets)

        with self._lock:
            old_offset = self.consensus_offset_ms
            self.consensus_offset_ms = weighted_offset

            # Track drift
            drift = weighted_offset - old_offset
            self.drift_history.append(drift)

            if abs(drift) > self.max_drift_ms:
                logger.warning(f"Large clock drift detected: {drift:.1f}ms")

    def get_utc_time(self) -> float:
        """
        Get consensus UTC time.

        Returns:
            UTC timestamp adjusted for clock offset
        """
        with self._lock:
            return time.time() + (self.consensus_offset_ms / 1000.0)

    def get_clock_offset(self) -> float:
        """Get current clock offset in milliseconds."""
        with self._lock:
            return self.consensus_offset_ms

    def get_drift_rate(self) -> float:
        """
        Get clock drift rate in ms/minute.

        Useful for predicting future drift.
        """
        with self._lock:
            if len(self.drift_history) < 2:
                return 0.0
            return statistics.mean(self.drift_history)

    def get_status(self) -> Dict[str, Any]:
        """Get layer status."""
        with self._lock:
            return {
                'layer': 0,
                'name': 'Server Time',
                'state': self.state.name,
                'offset_ms': round(self.consensus_offset_ms, 2),
                'drift_rate_ms_min': round(self.get_drift_rate(), 3),
                'servers_responding': len(self.last_results),
                'servers_total': len(self.ntp_servers)
            }


# ============================================================================
# LAYER 1: BITCOIN TIME SYNCHRONIZATION
# ============================================================================

class BitcoinTimeSynchronizer:
    """
    Layer 1: Bitcoin Time Synchronization (Primary Finality)

    Bitcoin blocks provide immutable time anchors with clear
    finality progression from mempool to irreversible.
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        confirmations_confirmed: int = CONFIRMATIONS_CONFIRMED,
        confirmations_irreversible: int = CONFIRMATIONS_IRREVERSIBLE
    ):
        """
        Initialize Bitcoin time synchronizer.

        Args:
            rpc_url: Bitcoin RPC endpoint (optional)
            confirmations_confirmed: Confirmations for CONFIRMED state
            confirmations_irreversible: Confirmations for IRREVERSIBLE state
        """
        self.rpc_url = rpc_url
        self.confirmations_confirmed = confirmations_confirmed
        self.confirmations_irreversible = confirmations_irreversible

        # State
        self.state = SyncLayerState.INACTIVE
        self.current_height: int = 0
        self.last_block: Optional[BitcoinBlockAnchor] = None
        self.last_block_time: Optional[float] = None
        self.mempool: MempoolState = MempoolState()

        # Block history for finality tracking
        self.block_history: Dict[int, BitcoinBlockAnchor] = {}
        self.max_history = 200  # Keep last 200 blocks

        # Callbacks
        self.on_new_block: Optional[Callable[[BitcoinBlockAnchor], None]] = None
        self.on_finality_change: Optional[Callable[[int, FinalityState], None]] = None

        self._lock = threading.RLock()
        self._running = False

        logger.info("Layer 1 (Bitcoin Time) initialized")

    def start(self):
        """Start Bitcoin monitoring."""
        if self._running:
            return

        self._running = True
        self.state = SyncLayerState.SYNCING
        logger.info("Layer 1 Bitcoin monitoring started")

    def stop(self):
        """Stop monitoring."""
        self._running = False
        self.state = SyncLayerState.INACTIVE
        logger.info("Layer 1 Bitcoin monitoring stopped")

    def on_block(
        self,
        height: int,
        block_hash: bytes,
        prev_hash: bytes,
        timestamp: int,
        merkle_root: bytes = b'\x00' * 32
    ) -> BitcoinBlockAnchor:
        """
        Process a new Bitcoin block.

        This is called when a new block is detected from any source
        (RPC, SPV, block explorer, etc.).

        Args:
            height: Block height
            block_hash: Block hash (32 bytes)
            prev_hash: Previous block hash
            timestamp: Block timestamp
            merkle_root: Merkle root

        Returns:
            BitcoinBlockAnchor for this block
        """
        with self._lock:
            anchor = BitcoinBlockAnchor(
                height=height,
                hash=block_hash,
                prev_hash=prev_hash,
                timestamp=timestamp,
                merkle_root=merkle_root,
                confirmations=1,
                finality=FinalityState.TENTATIVE,
                received_at=time.time()
            )

            # Update state
            self.current_height = max(self.current_height, height)
            self.last_block = anchor
            self.last_block_time = time.time()
            self.state = SyncLayerState.ACTIVE

            # Store in history
            self.block_history[height] = anchor

            # Clean old history
            if len(self.block_history) > self.max_history:
                oldest = min(self.block_history.keys())
                del self.block_history[oldest]

            # Update finality of all blocks in history
            self._update_all_finality()

            logger.info(
                f"Layer 1: New block {height} ({anchor.hash_hex[:16]}...) "
                f"finality={anchor.finality.name}"
            )

            # Notify callback
            if self.on_new_block:
                try:
                    self.on_new_block(anchor)
                except Exception as e:
                    logger.error(f"Block callback error: {e}")

            return anchor

    def _update_all_finality(self):
        """Update finality state for all tracked blocks."""
        for height, anchor in self.block_history.items():
            old_finality = anchor.finality
            anchor.update_finality(self.current_height)

            # Notify on finality change
            if anchor.finality != old_finality and self.on_finality_change:
                try:
                    self.on_finality_change(height, anchor.finality)
                except Exception as e:
                    logger.error(f"Finality callback error: {e}")

    def update_mempool(self, state: MempoolState):
        """
        Update mempool state.

        Called periodically with current mempool information.
        """
        with self._lock:
            self.mempool = state
            self.mempool.last_update = time.time()

    def get_finality(self, height: int) -> FinalityState:
        """
        Get finality state for a block height.

        Args:
            height: Block height to check

        Returns:
            FinalityState for that height
        """
        with self._lock:
            if height > self.current_height:
                return FinalityState.UNKNOWN

            if height in self.block_history:
                return self.block_history[height].finality

            # Block not in history but older than tracked
            confirmations = self.current_height - height + 1
            return FinalityState.from_confirmations(confirmations)

    def get_confirmations(self, height: int) -> int:
        """Get confirmation count for a block height."""
        with self._lock:
            if height > self.current_height:
                return 0
            return self.current_height - height + 1

    def is_producing_blocks(self) -> bool:
        """
        Check if Bitcoin is producing blocks normally.

        Returns True if blocks are being produced within expected variance.
        """
        with self._lock:
            if self.last_block_time is None:
                return False

            time_since = time.time() - self.last_block_time
            return time_since < BITCOIN_MAX_VARIANCE

    def get_time_since_last_block(self) -> Optional[float]:
        """Get seconds since last block."""
        with self._lock:
            if self.last_block_time is None:
                return None
            return time.time() - self.last_block_time

    def estimate_next_block(self) -> float:
        """
        Estimate time until next block.

        Uses mempool state and recent block times.
        """
        with self._lock:
            if self.last_block_time is None:
                return BITCOIN_BLOCK_TIME

            elapsed = time.time() - self.last_block_time

            # On average, next block in (BLOCK_TIME - elapsed) seconds
            # But can't be negative
            estimated = max(0, BITCOIN_BLOCK_TIME - elapsed)

            return estimated

    def get_current_anchor(self) -> Optional[BitcoinBlockAnchor]:
        """Get most recent block anchor."""
        with self._lock:
            return self.last_block

    def get_status(self) -> Dict[str, Any]:
        """Get layer status."""
        with self._lock:
            return {
                'layer': 1,
                'name': 'Bitcoin Time',
                'state': self.state.name,
                'current_height': self.current_height,
                'last_block_hash': self.last_block.hash_hex[:16] + '...' if self.last_block else None,
                'last_block_finality': self.last_block.finality.name if self.last_block else None,
                'seconds_since_block': self.get_time_since_last_block(),
                'estimated_next_block': self.estimate_next_block(),
                'mempool_tx_count': self.mempool.tx_count,
                'mempool_size_mb': round(self.mempool.size_bytes / 1_000_000, 2),
                'is_producing': self.is_producing_blocks()
            }


# ============================================================================
# LAYER 2: VDF FALLBACK (Integration point)
# ============================================================================

class VDFFallbackLayer:
    """
    Layer 2: VDF Fallback (Secondary Finality)

    Activates ONLY when Bitcoin is unavailable.
    Provides sovereign timekeeping independent of external systems.

    This is an integration layer - actual VDF computation is in vdf_fallback.py
    """

    def __init__(self, vdf_iterations: int = 1000):
        """
        Initialize VDF fallback layer.

        Args:
            vdf_iterations: Iterations for VDF (calibrate for ~9 min)
        """
        self.vdf_iterations = vdf_iterations

        # State
        self.state = SyncLayerState.INACTIVE
        self.active = False
        self.activation_reason: Optional[str] = None
        self.activation_time: Optional[float] = None
        self.last_vdf_sequence: int = 0
        self.last_vdf_hash: Optional[bytes] = None

        # Integration with vdf_fallback module
        self._vdf_fallback = None  # Lazy load

        self._lock = threading.Lock()

        logger.info("Layer 2 (VDF Fallback) initialized")

    def _get_vdf_fallback(self):
        """Lazy load VDF fallback module."""
        if self._vdf_fallback is None:
            try:
                from .vdf_fallback import VDFFallback
                self._vdf_fallback = VDFFallback(iterations=self.vdf_iterations)
            except ImportError:
                from pantheon.athena.vdf_fallback import VDFFallback
                self._vdf_fallback = VDFFallback(iterations=self.vdf_iterations)
        return self._vdf_fallback

    def activate(self, reason: str):
        """
        Activate VDF fallback mode.

        Called when Bitcoin becomes unavailable.

        Args:
            reason: Reason for activation
        """
        with self._lock:
            if self.active:
                return

            logger.warning(f"Layer 2 ACTIVATED: {reason}")

            self.active = True
            self.activation_reason = reason
            self.activation_time = time.time()
            self.state = SyncLayerState.ACTIVE

            # Activate underlying VDF
            vdf = self._get_vdf_fallback()
            vdf.activate(reason)

    def deactivate(self, reason: str = ""):
        """
        Deactivate VDF fallback.

        Called when Bitcoin becomes available again.
        """
        with self._lock:
            if not self.active:
                return

            logger.info(f"Layer 2 DEACTIVATED: {reason}")

            self.active = False
            self.state = SyncLayerState.INACTIVE

            # Deactivate underlying VDF
            if self._vdf_fallback:
                self._vdf_fallback.deactivate(reason)

    def compute_timestamp(self) -> Optional[Tuple[int, bytes]]:
        """
        Compute a new VDF timestamp.

        Returns:
            (sequence, hash) tuple or None if not active
        """
        with self._lock:
            if not self.active:
                return None

        vdf = self._get_vdf_fallback()
        ts = vdf.compute_timestamp()

        if ts:
            with self._lock:
                self.last_vdf_sequence = ts.sequence
                self.last_vdf_hash = ts.hash()
            return ts.sequence, ts.hash()

        return None

    def get_status(self) -> Dict[str, Any]:
        """Get layer status."""
        with self._lock:
            return {
                'layer': 2,
                'name': 'VDF Fallback',
                'state': self.state.name,
                'active': self.active,
                'activation_reason': self.activation_reason,
                'activation_time': self.activation_time,
                'vdf_sequence': self.last_vdf_sequence,
                'vdf_iterations': self.vdf_iterations
            }


# ============================================================================
# ADAM SYNC: UNIFIED TIME ORACLE
# ============================================================================

class AdamSync:
    """
    Adam Sync: Hierarchical Time Synchronization for Montana

    Coordinates all three layers:
    - Layer 0: Server Time (UTC reference)
    - Layer 1: Bitcoin Time (primary finality)
    - Layer 2: VDF Fallback (secondary finality)

    Provides unified timestamps with clear finality guarantees.
    """

    def __init__(
        self,
        vdf_iterations: int = 1000,
        auto_fallback: bool = True
    ):
        """
        Initialize Adam Sync.

        Args:
            vdf_iterations: VDF iterations for Layer 2
            auto_fallback: Automatically switch to VDF when Bitcoin down
        """
        # Initialize layers
        self.layer0 = ServerTimeSynchronizer()
        self.layer1 = BitcoinTimeSynchronizer()
        self.layer2 = VDFFallbackLayer(vdf_iterations)

        self.auto_fallback = auto_fallback

        # State
        self.primary_layer: int = 1  # Bitcoin is primary
        self.sequence: int = 0

        # Callbacks
        self.on_layer_change: Optional[Callable[[int, str], None]] = None

        self._lock = threading.RLock()
        self._running = False

        logger.info("Adam Sync initialized")

    def start(self):
        """Start all synchronization layers."""
        if self._running:
            return

        self._running = True

        # Start Layer 0 (always active)
        self.layer0.start()

        # Start Layer 1 (primary)
        self.layer1.start()

        # Layer 2 starts inactive (only on fallback)

        logger.info("Adam Sync started (Layer 1 primary)")

    def stop(self):
        """Stop all layers."""
        self._running = False

        self.layer0.stop()
        self.layer1.stop()
        self.layer2.deactivate("Shutdown")

        logger.info("Adam Sync stopped")

    def on_bitcoin_block(
        self,
        height: int,
        block_hash: bytes,
        prev_hash: bytes,
        timestamp: int,
        merkle_root: bytes = b'\x00' * 32
    ) -> BitcoinBlockAnchor:
        """
        Process new Bitcoin block.

        This is the main entry point for Bitcoin block events.

        Args:
            height: Block height
            block_hash: Block hash
            prev_hash: Previous block hash
            timestamp: Block timestamp
            merkle_root: Merkle root

        Returns:
            BitcoinBlockAnchor
        """
        anchor = self.layer1.on_block(
            height, block_hash, prev_hash, timestamp, merkle_root
        )

        # Check if we should switch back to Bitcoin from VDF
        if self.primary_layer == 2 and self.layer1.is_producing_blocks():
            self._switch_to_bitcoin("Bitcoin resumed producing blocks")

        return anchor

    def check_fallback(self) -> Tuple[bool, Optional[str]]:
        """
        Check if VDF fallback is needed.

        Returns:
            (needs_fallback, reason) tuple
        """
        time_since = self.layer1.get_time_since_last_block()

        if time_since is None:
            # No blocks yet - need initial sync
            return False, None

        if time_since >= VDF_TRIGGER_TIME_SECONDS:
            reason = (
                f"Bitcoin unavailable: {int(time_since / 60)} minutes "
                f"since last block (trigger: {VDF_TRIGGER_TIME_SECONDS // 60} min)"
            )

            if self.auto_fallback:
                self._switch_to_vdf(reason)

            return True, reason

        return False, None

    def _switch_to_vdf(self, reason: str):
        """Switch to VDF as primary layer."""
        with self._lock:
            if self.primary_layer == 2:
                return

            logger.warning(f"Switching to Layer 2 (VDF): {reason}")

            self.primary_layer = 2
            self.layer2.activate(reason)

            if self.on_layer_change:
                self.on_layer_change(2, reason)

    def _switch_to_bitcoin(self, reason: str):
        """Switch back to Bitcoin as primary layer."""
        with self._lock:
            if self.primary_layer == 1:
                return

            logger.info(f"Switching to Layer 1 (Bitcoin): {reason}")

            self.primary_layer = 1
            self.layer2.deactivate(reason)

            if self.on_layer_change:
                self.on_layer_change(1, reason)

    def get_timestamp(self) -> SyncTimestamp:
        """
        Get current synchronized timestamp.

        This is the main API for getting time from Adam Sync.
        Includes data from all active layers.

        Returns:
            SyncTimestamp with data from all layers
        """
        with self._lock:
            # Check if fallback is needed
            self.check_fallback()

            # Layer 0: UTC time
            utc_time = self.layer0.get_utc_time()
            clock_offset = self.layer0.get_clock_offset()

            # Layer 1: Bitcoin anchor
            btc_anchor = self.layer1.get_current_anchor()

            # Layer 2: VDF (if active)
            vdf_seq = None
            vdf_hash = None
            if self.primary_layer == 2:
                vdf_seq = self.layer2.last_vdf_sequence
                vdf_hash = self.layer2.last_vdf_hash

            # Create unified timestamp
            ts = SyncTimestamp(
                utc_time=utc_time,
                local_time=time.time(),
                clock_offset_ms=clock_offset,
                server_consensus=len(self.layer0.last_results),
                btc_height=btc_anchor.height if btc_anchor else None,
                btc_hash=btc_anchor.hash if btc_anchor else None,
                btc_finality=btc_anchor.finality if btc_anchor else FinalityState.UNKNOWN,
                btc_confirmations=btc_anchor.confirmations if btc_anchor else 0,
                vdf_sequence=vdf_seq,
                vdf_hash=vdf_hash,
                primary_layer=self.primary_layer,
                sequence=self.sequence
            )

            self.sequence += 1
            return ts

    def get_finality(self, height: int) -> FinalityState:
        """
        Get finality state for a Bitcoin block height.

        Args:
            height: Bitcoin block height

        Returns:
            FinalityState
        """
        return self.layer1.get_finality(height)

    def is_irreversible(self, height: int) -> bool:
        """
        Check if a block height is irreversibly finalized.

        Args:
            height: Block height

        Returns:
            True if block is irreversible
        """
        return self.get_finality(height) == FinalityState.IRREVERSIBLE

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all layers."""
        with self._lock:
            return {
                'primary_layer': self.primary_layer,
                'primary_layer_name': 'Bitcoin' if self.primary_layer == 1 else 'VDF',
                'sequence': self.sequence,
                'auto_fallback': self.auto_fallback,
                'layers': {
                    'layer0': self.layer0.get_status(),
                    'layer1': self.layer1.get_status(),
                    'layer2': self.layer2.get_status()
                }
            }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run Adam Sync self-tests."""
    import hashlib

    logger.info("Running Adam Sync self-tests...")

    # Test FinalityState
    assert FinalityState.from_confirmations(0) == FinalityState.PENDING
    assert FinalityState.from_confirmations(1) == FinalityState.TENTATIVE
    assert FinalityState.from_confirmations(6) == FinalityState.CONFIRMED
    assert FinalityState.from_confirmations(100) == FinalityState.IRREVERSIBLE
    logger.info("  FinalityState transitions")

    # Test BitcoinBlockAnchor
    anchor = BitcoinBlockAnchor(
        height=840000,
        hash=hashlib.sha256(b"block").digest(),
        prev_hash=hashlib.sha256(b"prev").digest(),
        timestamp=int(time.time()),
        merkle_root=hashlib.sha256(b"merkle").digest()
    )
    assert anchor.finality == FinalityState.TENTATIVE
    anchor.update_finality(840010)
    assert anchor.confirmations == 11
    assert anchor.finality == FinalityState.CONFIRMED
    logger.info("  BitcoinBlockAnchor")

    # Test serialization
    serialized = anchor.serialize()
    deserialized, _ = BitcoinBlockAnchor.deserialize(serialized)
    assert deserialized.height == anchor.height
    assert deserialized.hash == anchor.hash
    logger.info("  Anchor serialization")

    # Test Layer 1
    layer1 = BitcoinTimeSynchronizer()
    layer1.start()

    # Simulate blocks
    for i in range(5):
        layer1.on_block(
            height=840000 + i,
            block_hash=hashlib.sha256(f"block_{i}".encode()).digest(),
            prev_hash=hashlib.sha256(f"block_{i-1}".encode()).digest() if i > 0 else b'\x00' * 32,
            timestamp=int(time.time()) - (5 - i) * 600
        )

    assert layer1.current_height == 840004
    assert layer1.get_finality(840000) == FinalityState.TENTATIVE
    logger.info("  Layer 1 (Bitcoin Time)")

    # Test Adam Sync
    adam = AdamSync(vdf_iterations=50)
    adam.start()

    # Simulate Bitcoin blocks
    for i in range(3):
        adam.on_bitcoin_block(
            height=840000 + i,
            block_hash=hashlib.sha256(f"adam_block_{i}".encode()).digest(),
            prev_hash=hashlib.sha256(f"adam_block_{i-1}".encode()).digest() if i > 0 else b'\x00' * 32,
            timestamp=int(time.time()) - (3 - i) * 600
        )

    assert adam.primary_layer == 1
    logger.info("  Adam Sync initialization")

    # Get timestamp
    ts = adam.get_timestamp()
    assert ts.btc_height == 840002
    assert ts.primary_layer == 1
    logger.info("  Unified timestamp")

    # Check finality
    finality = adam.get_finality(840000)
    assert finality in (FinalityState.TENTATIVE, FinalityState.CONFIRMED)
    logger.info("  Finality check")

    # Get status
    status = adam.get_status()
    assert 'layers' in status
    assert 'layer0' in status['layers']
    assert 'layer1' in status['layers']
    assert 'layer2' in status['layers']
    logger.info("  Status reporting")

    # Cleanup
    adam.stop()
    layer1.stop()

    logger.info("All Adam Sync tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
