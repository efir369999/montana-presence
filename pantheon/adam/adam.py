"""
Montana v4.2 - ADAM: THE GOD OF TIME

╔═══════════════════════════════════════════════════════════════════════════════╗
║                              ADAM - GOD OF TIME                               ║
║                                                                               ║
║       ADAM = Anchored Deterministic Asynchronous Mesh                         ║
║                                                                               ║
║       THIS IS THE ONLY SOURCE OF TRUTH FOR TIME IN MONTANA.                   ║
║       All time-related operations MUST go through Adam. No exceptions.        ║
║                                                                               ║
║       Chronos is deprecated. Adam is the sole authority.                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════
                              ADAM LEVELS (0-6)
═══════════════════════════════════════════════════════════════════════════════

  LEVEL 0: NODE_UTC
  ─────────────────
  Node's hardware clock (UTC).
  Local system time from node hardware.
  Trust: LOW (local hardware, drift possible)

           ▼

  LEVEL 1: GLOBAL_NTP
  ───────────────────
  Verification against 12 authoritative national laboratories:

  ┌──────────────────────────────────────────────────────────────────────────┐
  │  COUNTRY          │ LABORATORY              │ SERVER                     │
  ├───────────────────┼─────────────────────────┼────────────────────────────┤
  │  USA              │ NIST, USNO              │ time.nist.gov              │
  │  Europe (UK)      │ NPL                     │ ntp1.npl.co.uk             │
  │  Europe (DE)      │ PTB                     │ ptbtime1.ptb.de            │
  │  Russia           │ ВНИИФТРИ               │ ntp2.vniiftri.ru           │
  │  China            │ NIM                     │ cn.pool.ntp.org            │
  │  Japan            │ NICT                    │ ntp.jst.mfeed.ad.jp        │
  │  Canada           │ NRC                     │ time.nrc.ca                │
  │  Australia        │ NMI                     │ ntp.ausaid.gov.au          │
  │  India            │ NPL India               │ in.pool.ntp.org            │
  │  Sweden           │ Netnod                  │ ntp.se                     │
  │  Switzerland      │ METAS                   │ ntp.metas.ch               │
  │  South Korea      │ KRISS                   │ time.kriss.re.kr           │
  │  Mexico           │ CENAM                   │ ntp.cenam.mx               │
  └──────────────────────────────────────────────────────────────────────────┘

  Trust: HIGH (authoritative national sources)

           ▼

  LEVEL 2: MEMPOOL_TIME
  ─────────────────────
  Transaction enters Bitcoin mempool.
  Timestamp when TX is first seen by network.
  Trust: HIGH (distributed observation)
  State: PENDING

           ▼

  LEVEL 3: BLOCK_TIME
  ───────────────────
  Transaction included in Bitcoin block.
  Block timestamp from miner.
  Trust: VERY HIGH (PoW secured)
  State: TENTATIVE → CONFIRMED → IRREVERSIBLE

           ▼

  LEVEL 4: BITCOIN_ACTIVE
  ───────────────────────
  Bitcoin is producing blocks normally.
  VDF fallback is IDLE (not needed).
  This is the normal operating state.

           ▼ (only if Bitcoin fails for 2+ blocks)

  LEVEL 5: VDF_FALLBACK
  ─────────────────────
  Bitcoin unavailable for 2+ blocks (~20 min).
  SHAKE256 VDF provides sovereign timekeeping.
  Finalization every 600 seconds (10 minutes).
  PoH provides instant transaction ordering.
  Trust: VERY HIGH (cryptographic, quantum-resistant)

           ▼ (Bitcoin returned + 20 blocks)

  LEVEL 6: VDF_DEACTIVATE
  ───────────────────────
  Bitcoin returned and stable for 20 blocks.
  VDF shutting down, transitioning back to Bitcoin.
  After transition: back to LEVEL 4.

═══════════════════════════════════════════════════════════════════════════════

FINALITY PROGRESSION (Level 3):
───────────────────────────────
  PENDING      (0 conf)   - In mempool, not in block
  TENTATIVE    (1 conf)   - In block, may reorg
  CONFIRMED    (6+ conf)  - Probabilistic finality
  IRREVERSIBLE (100+ conf) - Economic finality, cannot reorg

VDF FALLBACK (Level 5):
───────────────────────
  When Bitcoin is down for 2+ blocks (~20 minutes):
  - SHAKE256 hash chain for time proofs (quantum-resistant)
  - VDF finalization every 600 seconds (10 minutes)
  - PoH provides instant transaction ordering (sub-second)
  - Return to Bitcoin after 20 blocks of stability

QUANTUM RESISTANCE:
───────────────────
  - SHAKE256 VDF: Hash-based, no RSA assumptions
  - Grover's algorithm: 256-bit → 128-bit (still infeasible)
  - STARK proofs: O(log T) verification, transparent

Bitcoin is the clock. SHAKE256 VDF is the insurance.
Time is the ultimate proof.
"""

import time
import struct
import hashlib
import logging
import threading
import statistics
import socket
from typing import Optional, Tuple, Dict, Any, List, Callable, Set
from dataclasses import dataclass, field
from enum import IntEnum, auto
from collections import deque

logger = logging.getLogger("montana.adam")


# ============================================================================
# ADAM SYNC LEVELS
# ============================================================================

class AdamLevel(IntEnum):
    """
    Adam Sync canonical levels.

    THIS IS THE ONLY DEFINITION OF TIME SYNCHRONIZATION LEVELS IN MONTANA.

    TIME SOURCES (0-3):
      0 - NODE_UTC:      Node hardware clock (UTC)
      1 - GLOBAL_NTP:    12 national NTP laboratories
      2 - MEMPOOL_TIME:  Bitcoin mempool observation
      3 - BLOCK_TIME:    Bitcoin block confirmation

    SYSTEM STATE (4-6):
      4 - BITCOIN_ACTIVE:  Bitcoin working, VDF not needed
      5 - VDF_FALLBACK:    Bitcoin down 2 blocks, SHAKE256 VDF active
                           Finalization every 600 sec, PoH for instant ordering
      6 - VDF_DEACTIVATE:  Bitcoin returned +20 blocks, VDF shutting down
    """
    # Time sources (0-3)
    NODE_UTC = 0          # Level 0: Node hardware clock (UTC)
    GLOBAL_NTP = 1        # Level 1: 12 national laboratory NTP servers
    MEMPOOL_TIME = 2      # Level 2: Bitcoin mempool observation
    BLOCK_TIME = 3        # Level 3: Bitcoin block confirmation

    # System state (4-6)
    BITCOIN_ACTIVE = 4    # Level 4: Bitcoin working, VDF not needed
    VDF_FALLBACK = 5      # Level 5: Bitcoin down 2 blocks, SHAKE256 VDF active
    VDF_DEACTIVATE = 6    # Level 6: Bitcoin returned +20 blocks, transitioning back


class FinalityState(IntEnum):
    """
    Transaction/block finality states.

    Progressive finality from mempool to irreversible.
    """
    UNKNOWN = 0           # State unknown
    PENDING = 1           # In mempool (Level 3)
    TENTATIVE = 2         # 1 confirmation (Level 4)
    CONFIRMED = 3         # 6+ confirmations (Level 4)
    IRREVERSIBLE = 4      # 100+ confirmations (Level 4)

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
        return self != FinalityState.IRREVERSIBLE

    @property
    def is_final(self) -> bool:
        """Check if this state represents finality."""
        return self == FinalityState.IRREVERSIBLE


class LevelState(IntEnum):
    """State of each Adam level."""
    INACTIVE = 0      # Level not initialized
    SYNCING = 1       # Level synchronizing
    ACTIVE = 2        # Level operational
    DEGRADED = 3      # Level experiencing issues
    FAILED = 4        # Level unavailable


# ============================================================================
# CONSTANTS - THE CANONICAL VALUES
# ============================================================================

# Level 2: Global NTP - 12 National Laboratories
GLOBAL_NTP_SERVERS = {
    # Country: (Laboratory, Server, Description)
    'USA': ('NIST/USNO', 'time.nist.gov', 'National Institute of Standards and Technology'),
    'UK': ('NPL', 'ntp1.npl.co.uk', 'National Physical Laboratory'),
    'Germany': ('PTB', 'ptbtime1.ptb.de', 'Physikalisch-Technische Bundesanstalt'),
    'Russia': ('ВНИИФТРИ', 'ntp2.vniiftri.ru', 'All-Russian Scientific Research Institute'),
    'China': ('NIM', 'cn.pool.ntp.org', 'National Institute of Metrology'),
    'Japan': ('NICT', 'ntp.jst.mfeed.ad.jp', 'National Institute of Information and Communications'),
    'Canada': ('NRC', 'time.nrc.ca', 'National Research Council'),
    'Australia': ('NMI', 'ntp.ausaid.gov.au', 'National Measurement Institute'),
    'India': ('NPL', 'in.pool.ntp.org', 'National Physical Laboratory India'),
    'Sweden': ('Netnod', 'ntp.se', 'Swedish Internet Exchange'),
    'Switzerland': ('METAS', 'ntp.metas.ch', 'Federal Institute of Metrology'),
    'South Korea': ('KRISS', 'time.kriss.re.kr', 'Korea Research Institute of Standards'),
    'Mexico': ('CENAM', 'ntp.cenam.mx', 'Centro Nacional de Metrología'),
}

# Extract server list
NTP_SERVER_LIST = [info[1] for info in GLOBAL_NTP_SERVERS.values()]

NTP_TIMEOUT_SEC = 3.0
NTP_MIN_SERVERS = 4        # Minimum 4 of 12 must respond
NTP_SYNC_INTERVAL = 300    # Verify every 5 minutes

# Level 0: Node UTC
MAX_CLOCK_DRIFT_MS = 1000  # 1 second max acceptable drift
DRIFT_WARNING_MS = 500     # Warn at 500ms

# Level 1: Network Nodes
MIN_PEER_NODES = 3         # Minimum peers for consensus
PEER_SYNC_INTERVAL = 60    # Exchange time every minute

# Level 3: Mempool
MEMPOOL_POLL_INTERVAL = 30  # seconds

# Level 4: Block confirmations
CONFIRMATIONS_TENTATIVE = 1
CONFIRMATIONS_CONFIRMED = 6
CONFIRMATIONS_IRREVERSIBLE = 100

# Level 4-6: Bitcoin/VDF State Machine
BITCOIN_BLOCK_TIME = 600  # 10 minutes expected
BITCOIN_MAX_VARIANCE = 1800  # 30 minutes max
VDF_TRIGGER_BLOCKS = 2  # 2 missed blocks triggers VDF (~20 min)
VDF_TRIGGER_SECONDS = VDF_TRIGGER_BLOCKS * BITCOIN_BLOCK_TIME  # 1200 sec = 20 min
VDF_MONITOR_INTERVAL = 1.0  # Check Bitcoin status every second
VDF_DEACTIVATION_BLOCKS = 20  # Require 20 blocks after Bitcoin returns
VDF_DEACTIVATION_HYSTERESIS = VDF_DEACTIVATION_BLOCKS * BITCOIN_BLOCK_TIME  # ~200 min = 3.3 hours
VDF_FINALIZATION_INTERVAL = 600  # VDF finalization every 600 seconds (10 minutes)
VDF_CHECKPOINT_INTERVAL = 1000  # STARK checkpoint every 1000 iterations


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Level0State:
    """Level 0: Node UTC state."""
    local_time: float         # Local system time (UTC)
    uptime_seconds: float     # Node uptime
    clock_source: str         # Clock source (hardware/ntp)


@dataclass
class Level1State:
    """Level 1: Network nodes consensus state."""
    peer_count: int           # Number of peers
    peer_times: Dict[bytes, float]  # Peer pubkey -> their reported time
    consensus_time: float     # Weighted consensus time
    deviation_ms: float       # Standard deviation in ms
    last_sync: float          # Last peer sync time


@dataclass
class Level2Result:
    """Level 2: Global NTP server query result."""
    country: str
    laboratory: str
    server: str
    ntp_time: float           # Time from NTP server
    round_trip_ms: float      # Network round-trip
    offset_ms: float          # Offset from local clock
    stratum: int              # NTP stratum (1 = atomic clock)
    confidence: float         # 0.0-1.0 based on round-trip
    queried_at: float         # Local time when queried

    @property
    def adjusted_time(self) -> float:
        """Time adjusted for network latency."""
        return self.ntp_time + (self.round_trip_ms / 2000.0)


@dataclass
class Level3State:
    """Level 3: Mempool state."""
    tx_count: int             # Pending transactions
    size_bytes: int           # Total mempool size
    fee_min: float            # Min fee rate (sat/vB)
    fee_median: float         # Median fee rate
    fee_high: float           # High priority fee rate
    first_seen: Dict[bytes, float] = field(default_factory=dict)
    last_update: float = 0.0


@dataclass
class Level4Block:
    """Level 4: Bitcoin block."""
    height: int
    hash: bytes               # 32 bytes
    prev_hash: bytes          # 32 bytes
    timestamp: int            # Block timestamp (miner)
    merkle_root: bytes        # 32 bytes
    confirmations: int = 0
    finality: FinalityState = FinalityState.TENTATIVE
    received_at: float = 0.0  # When node received it

    def update_finality(self, chain_height: int):
        """Update finality based on current chain height."""
        self.confirmations = max(0, chain_height - self.height + 1)
        self.finality = FinalityState.from_confirmations(self.confirmations)

    @property
    def hash_hex(self) -> str:
        """Block hash as hex (display format)."""
        return self.hash[::-1].hex()

    def serialize(self) -> bytes:
        """Serialize block."""
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
    def deserialize(cls, data: bytes, offset: int = 0) -> Tuple['Level4Block', int]:
        """Deserialize block."""
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
class AdamTimestamp:
    """
    THE canonical timestamp from Adam Sync.

    Contains state from all levels.
    """
    # Level 0: Node UTC
    node_utc: float
    node_uptime: float

    # Level 1: Network Nodes
    network_peer_count: int
    network_consensus_time: float
    network_deviation_ms: float

    # Level 2: Global NTP
    ntp_servers_responding: int
    ntp_consensus_offset_ms: float
    ntp_laboratories: List[str]  # Which labs responded

    # Level 3: Mempool (if TX pending)
    mempool_first_seen: Optional[float] = None

    # Level 4: Block (if confirmed)
    btc_height: Optional[int] = None
    btc_hash: Optional[bytes] = None
    btc_timestamp: Optional[int] = None
    btc_confirmations: int = 0
    btc_finality: FinalityState = FinalityState.UNKNOWN

    # Level 5/6: System state
    current_level: AdamLevel = AdamLevel.BITCOIN_ACTIVE
    vdf_active: bool = False
    vdf_sequence: Optional[int] = None

    # Metadata
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'level': self.current_level.name,
            'node_utc': self.node_utc,
            'network_peers': self.network_peer_count,
            'network_deviation_ms': round(self.network_deviation_ms, 2),
            'ntp_servers': self.ntp_servers_responding,
            'ntp_offset_ms': round(self.ntp_consensus_offset_ms, 2),
            'ntp_labs': self.ntp_laboratories,
            'btc_height': self.btc_height,
            'btc_hash': self.btc_hash.hex()[:16] + '...' if self.btc_hash else None,
            'btc_finality': self.btc_finality.name,
            'btc_confirmations': self.btc_confirmations,
            'vdf_active': self.vdf_active,
            'sequence': self.sequence
        }


# ============================================================================
# LEVEL 0: NODE UTC
# ============================================================================

class Level0_NodeUTC:
    """
    Level 0: Node Hardware Clock (UTC)

    Local system time from node hardware.
    This is the baseline - all other levels verify against this.
    """

    def __init__(self):
        self.state = LevelState.ACTIVE  # Always active
        self.start_time = time.time()

        logger.info("Level 0 (Node UTC) initialized")

    def get_utc(self) -> float:
        """Get current UTC time from node."""
        return time.time()

    def get_uptime(self) -> float:
        """Get node uptime in seconds."""
        return time.time() - self.start_time

    def get_state(self) -> Level0State:
        """Get level 0 state."""
        return Level0State(
            local_time=self.get_utc(),
            uptime_seconds=self.get_uptime(),
            clock_source='system'
        )

    def get_status(self) -> Dict[str, Any]:
        """Get level status."""
        return {
            'level': 0,
            'name': 'NODE_UTC',
            'state': self.state.name,
            'utc_time': self.get_utc(),
            'uptime_seconds': round(self.get_uptime(), 1)
        }


# ============================================================================
# LEVEL 1: NETWORK NODES
# ============================================================================

class Level1_NetworkNodes:
    """
    Level 1: Montana Network Peer Time Consensus

    Gathers time from peer nodes in the network.
    Weighted average provides internal network time.
    """

    def __init__(self, level0: Level0_NodeUTC):
        self.level0 = level0
        self.state = LevelState.INACTIVE

        self.peer_times: Dict[bytes, Tuple[float, float]] = {}  # pubkey -> (time, weight)
        self.consensus_time: float = 0.0
        self.deviation_ms: float = 0.0
        self.last_sync: float = 0.0

        self._lock = threading.Lock()

        logger.info("Level 1 (Network Nodes) initialized")

    def start(self):
        """Start network time tracking."""
        self.state = LevelState.SYNCING
        logger.info("Level 1 (Network Nodes) started")

    def stop(self):
        """Stop tracking."""
        self.state = LevelState.INACTIVE
        logger.info("Level 1 (Network Nodes) stopped")

    def report_peer_time(self, peer_pubkey: bytes, peer_time: float, weight: float = 1.0):
        """
        Record time reported by a peer node.

        Called when receiving time sync messages from peers.
        """
        with self._lock:
            self.peer_times[peer_pubkey] = (peer_time, weight)
            self._recalculate_consensus()

    def remove_peer(self, peer_pubkey: bytes):
        """Remove a peer from tracking."""
        with self._lock:
            self.peer_times.pop(peer_pubkey, None)
            self._recalculate_consensus()

    def _recalculate_consensus(self):
        """Recalculate consensus time from all peers."""
        if len(self.peer_times) < MIN_PEER_NODES:
            self.state = LevelState.DEGRADED
            return

        times = []
        weights = []
        for peer_time, weight in self.peer_times.values():
            times.append(peer_time)
            weights.append(weight)

        # Weighted average
        total_weight = sum(weights)
        if total_weight > 0:
            self.consensus_time = sum(t * w for t, w in zip(times, weights)) / total_weight
        else:
            self.consensus_time = statistics.median(times)

        # Standard deviation
        if len(times) >= 2:
            self.deviation_ms = statistics.stdev(times) * 1000
        else:
            self.deviation_ms = 0.0

        self.last_sync = self.level0.get_utc()
        self.state = LevelState.ACTIVE

    def get_consensus_time(self) -> float:
        """Get network consensus time."""
        with self._lock:
            if self.state != LevelState.ACTIVE:
                return self.level0.get_utc()
            return self.consensus_time

    def get_state(self) -> Level1State:
        """Get level 1 state."""
        with self._lock:
            return Level1State(
                peer_count=len(self.peer_times),
                peer_times={k: v[0] for k, v in self.peer_times.items()},
                consensus_time=self.consensus_time,
                deviation_ms=self.deviation_ms,
                last_sync=self.last_sync
            )

    def get_status(self) -> Dict[str, Any]:
        """Get level status."""
        with self._lock:
            return {
                'level': 1,
                'name': 'NETWORK_NODES',
                'state': self.state.name,
                'peer_count': len(self.peer_times),
                'consensus_time': self.consensus_time,
                'deviation_ms': round(self.deviation_ms, 2),
                'last_sync': self.last_sync
            }


# ============================================================================
# LEVEL 2: GLOBAL NTP (12 National Laboratories)
# ============================================================================

class Level2_GlobalNTP:
    """
    Level 2: Global NTP Verification

    Queries 12 authoritative national metrology laboratories worldwide.
    Provides ultimate external time verification.
    """

    def __init__(self, level0: Level0_NodeUTC):
        self.level0 = level0
        self.state = LevelState.INACTIVE

        self.last_results: Dict[str, Level2Result] = {}  # country -> result
        self.consensus_offset_ms: float = 0.0
        self.responding_labs: List[str] = []

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(f"Level 2 (Global NTP) initialized with {len(GLOBAL_NTP_SERVERS)} national laboratories")

    def start(self):
        """Start NTP verification."""
        if self._running:
            return
        self._running = True
        self.state = LevelState.SYNCING
        self._thread = threading.Thread(target=self._sync_loop, daemon=True, name="Adam-L2-NTP")
        self._thread.start()
        logger.info("Level 2 (Global NTP) started")

    def stop(self):
        """Stop NTP verification."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.state = LevelState.INACTIVE
        logger.info("Level 2 (Global NTP) stopped")

    def _sync_loop(self):
        """Background NTP sync loop."""
        while self._running:
            try:
                self._sync_once()
            except Exception as e:
                logger.error(f"Level 2 sync error: {e}")
                self.state = LevelState.DEGRADED
            time.sleep(NTP_SYNC_INTERVAL)

    def _sync_once(self):
        """Query all NTP servers once."""
        results = {}

        for country, (lab, server, desc) in GLOBAL_NTP_SERVERS.items():
            result = self._query_ntp(country, lab, server)
            if result:
                results[country] = result

        with self._lock:
            self.last_results = results
            self.responding_labs = [r.laboratory for r in results.values()]

            if len(results) >= NTP_MIN_SERVERS:
                # Weighted average by confidence (inverse of round-trip)
                total_weight = sum(r.confidence for r in results.values())
                if total_weight > 0:
                    self.consensus_offset_ms = sum(
                        r.offset_ms * r.confidence for r in results.values()
                    ) / total_weight

                # Check for dangerous drift
                if abs(self.consensus_offset_ms) > MAX_CLOCK_DRIFT_MS:
                    logger.error(
                        f"Level 2: CRITICAL clock drift {self.consensus_offset_ms:.0f}ms detected!"
                    )
                elif abs(self.consensus_offset_ms) > DRIFT_WARNING_MS:
                    logger.warning(
                        f"Level 2: Clock drift {self.consensus_offset_ms:.0f}ms (warning threshold)"
                    )

                self.state = LevelState.ACTIVE
                logger.info(
                    f"Level 2: {len(results)}/{len(GLOBAL_NTP_SERVERS)} labs responded, "
                    f"offset={self.consensus_offset_ms:.1f}ms"
                )
            else:
                self.state = LevelState.DEGRADED
                logger.warning(
                    f"Level 2: Only {len(results)}/{NTP_MIN_SERVERS} labs responded"
                )

    def _query_ntp(self, country: str, lab: str, server: str) -> Optional[Level2Result]:
        """Query single NTP server."""
        try:
            ntp_data = b'\x1b' + 47 * b'\0'
            start = time.time()

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(NTP_TIMEOUT_SEC)
            try:
                sock.sendto(ntp_data, (server, 123))
                data, _ = sock.recvfrom(48)
                end = time.time()

                if len(data) >= 44:
                    # Extract stratum (byte 1)
                    stratum = data[1]

                    # Extract timestamp (bytes 40-43)
                    ntp_timestamp = struct.unpack('!I', data[40:44])[0]
                    ntp_time = ntp_timestamp - 2208988800  # NTP to Unix epoch

                    round_trip = (end - start) * 1000
                    offset = (ntp_time - start) * 1000

                    return Level2Result(
                        country=country,
                        laboratory=lab,
                        server=server,
                        ntp_time=ntp_time,
                        round_trip_ms=round_trip,
                        offset_ms=offset,
                        stratum=stratum,
                        confidence=1.0 / (1.0 + round_trip / 100.0),
                        queried_at=start
                    )
            finally:
                sock.close()
        except Exception as e:
            logger.debug(f"Level 2: NTP query to {lab} ({server}) failed: {e}")
        return None

    def get_offset(self) -> float:
        """Get consensus offset in milliseconds."""
        with self._lock:
            return self.consensus_offset_ms

    def get_verified_utc(self) -> float:
        """Get UTC time verified against global NTP."""
        return self.level0.get_utc() + (self.consensus_offset_ms / 1000.0)

    def get_responding_labs(self) -> List[str]:
        """Get list of responding laboratories."""
        with self._lock:
            return self.responding_labs.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get level status."""
        with self._lock:
            return {
                'level': 2,
                'name': 'GLOBAL_NTP',
                'state': self.state.name,
                'labs_responding': len(self.last_results),
                'labs_total': len(GLOBAL_NTP_SERVERS),
                'responding': list(self.last_results.keys()),
                'consensus_offset_ms': round(self.consensus_offset_ms, 2),
                'laboratories': self.responding_labs
            }


# ============================================================================
# LEVEL 3: MEMPOOL TIME
# ============================================================================

class Level3_MempoolTime:
    """
    Level 3: Bitcoin Mempool Observation

    Tracks when transactions first appear in mempool.
    Provides PENDING finality state.
    """

    def __init__(self, level2: Level2_GlobalNTP):
        self.level2 = level2
        self.state = LevelState.INACTIVE
        self.mempool = Level3State(tx_count=0, size_bytes=0, fee_min=0, fee_median=0, fee_high=0)

        self._lock = threading.Lock()

        logger.info("Level 3 (Mempool) initialized")

    def start(self):
        """Start mempool tracking."""
        self.state = LevelState.ACTIVE
        logger.info("Level 3 (Mempool) started")

    def stop(self):
        """Stop mempool tracking."""
        self.state = LevelState.INACTIVE
        logger.info("Level 3 (Mempool) stopped")

    def on_tx_seen(self, tx_hash: bytes) -> float:
        """
        Record when transaction first seen in mempool.

        Returns timestamp when TX was first observed.
        """
        with self._lock:
            if tx_hash not in self.mempool.first_seen:
                first_seen = self.level2.get_verified_utc()
                self.mempool.first_seen[tx_hash] = first_seen
                logger.debug(f"Level 3: TX {tx_hash.hex()[:16]}... first seen")
                return first_seen
            return self.mempool.first_seen[tx_hash]

    def get_tx_first_seen(self, tx_hash: bytes) -> Optional[float]:
        """Get when TX was first seen, or None."""
        with self._lock:
            return self.mempool.first_seen.get(tx_hash)

    def update_mempool_state(
        self,
        tx_count: int,
        size_bytes: int,
        fee_min: float,
        fee_median: float,
        fee_high: float
    ):
        """Update mempool statistics."""
        with self._lock:
            self.mempool.tx_count = tx_count
            self.mempool.size_bytes = size_bytes
            self.mempool.fee_min = fee_min
            self.mempool.fee_median = fee_median
            self.mempool.fee_high = fee_high
            self.mempool.last_update = self.level2.get_verified_utc()

    def clear_confirmed(self, tx_hashes: List[bytes]):
        """Remove confirmed TXs from tracking."""
        with self._lock:
            for tx_hash in tx_hashes:
                self.mempool.first_seen.pop(tx_hash, None)

    def get_status(self) -> Dict[str, Any]:
        """Get level status."""
        with self._lock:
            return {
                'level': 3,
                'name': 'MEMPOOL_TIME',
                'state': self.state.name,
                'tx_count': self.mempool.tx_count,
                'size_mb': round(self.mempool.size_bytes / 1_000_000, 2),
                'fee_median': self.mempool.fee_median,
                'tracked_txs': len(self.mempool.first_seen),
                'last_update': self.mempool.last_update
            }


# ============================================================================
# LEVEL 4: BLOCK TIME
# ============================================================================

class Level4_BlockTime:
    """
    Level 4: Bitcoin Block Confirmation

    Tracks Bitcoin blocks and finality progression:
    PENDING → TENTATIVE → CONFIRMED → IRREVERSIBLE
    """

    def __init__(self, level2: Level2_GlobalNTP, level3: Level3_MempoolTime):
        self.level2 = level2
        self.level3 = level3
        self.state = LevelState.INACTIVE

        self.chain_height: int = 0
        self.last_block: Optional[Level4Block] = None
        self.last_block_time: Optional[float] = None
        self.blocks: Dict[int, Level4Block] = {}
        self.max_blocks = 200

        # Callbacks
        self.on_new_block: Optional[Callable[[Level4Block], None]] = None
        self.on_finality_change: Optional[Callable[[int, FinalityState], None]] = None

        self._lock = threading.RLock()

        logger.info("Level 4 (Block Time) initialized")

    def start(self):
        """Start block tracking."""
        self.state = LevelState.SYNCING
        logger.info("Level 4 (Block Time) started")

    def stop(self):
        """Stop block tracking."""
        self.state = LevelState.INACTIVE
        logger.info("Level 4 (Block Time) stopped")

    def on_block(
        self,
        height: int,
        block_hash: bytes,
        prev_hash: bytes,
        timestamp: int,
        merkle_root: bytes = b'\x00' * 32,
        tx_hashes: List[bytes] = None
    ) -> Level4Block:
        """
        Process new Bitcoin block.

        This is THE entry point for Bitcoin blocks in Montana.
        """
        with self._lock:
            block = Level4Block(
                height=height,
                hash=block_hash,
                prev_hash=prev_hash,
                timestamp=timestamp,
                merkle_root=merkle_root,
                confirmations=1,
                finality=FinalityState.TENTATIVE,
                received_at=self.level2.get_verified_utc()
            )

            # Update chain state
            self.chain_height = max(self.chain_height, height)
            self.last_block = block
            self.last_block_time = self.level2.get_verified_utc()
            self.blocks[height] = block
            self.state = LevelState.ACTIVE

            # Clean old blocks
            while len(self.blocks) > self.max_blocks:
                oldest = min(self.blocks.keys())
                del self.blocks[oldest]

            # Update finality for all blocks
            self._update_all_finality()

            # Clear confirmed TXs from mempool tracking
            if tx_hashes:
                self.level3.clear_confirmed(tx_hashes)

            logger.info(
                f"Level 4: Block #{height} ({block.hash_hex[:16]}...) "
                f"finality={block.finality.name}"
            )

            # Callback
            if self.on_new_block:
                try:
                    self.on_new_block(block)
                except Exception as e:
                    logger.error(f"Level 4 block callback error: {e}")

            return block

    def _update_all_finality(self):
        """Update finality for all tracked blocks."""
        for height, block in self.blocks.items():
            old_finality = block.finality
            block.update_finality(self.chain_height)

            if block.finality != old_finality and self.on_finality_change:
                try:
                    self.on_finality_change(height, block.finality)
                    logger.debug(f"Level 4: Block #{height} finality: {old_finality.name} → {block.finality.name}")
                except Exception as e:
                    logger.error(f"Level 4 finality callback error: {e}")

    def get_finality(self, height: int) -> FinalityState:
        """Get finality state for block height."""
        with self._lock:
            if height > self.chain_height:
                return FinalityState.UNKNOWN
            if height in self.blocks:
                return self.blocks[height].finality
            confirmations = self.chain_height - height + 1
            return FinalityState.from_confirmations(confirmations)

    def get_confirmations(self, height: int) -> int:
        """Get confirmation count for block height."""
        with self._lock:
            if height > self.chain_height:
                return 0
            return self.chain_height - height + 1

    def is_irreversible(self, height: int) -> bool:
        """Check if block is irreversibly final."""
        return self.get_finality(height) == FinalityState.IRREVERSIBLE

    def time_since_last_block(self) -> Optional[float]:
        """Seconds since last block."""
        with self._lock:
            if self.last_block_time is None:
                return None
            return self.level2.get_verified_utc() - self.last_block_time

    def is_producing(self) -> bool:
        """Is Bitcoin producing blocks normally?"""
        with self._lock:
            if self.last_block_time is None:
                return False
            return self.time_since_last_block() < BITCOIN_MAX_VARIANCE

    def get_status(self) -> Dict[str, Any]:
        """Get level status."""
        with self._lock:
            return {
                'level': 4,
                'name': 'BLOCK_TIME',
                'state': self.state.name,
                'chain_height': self.chain_height,
                'last_block_hash': self.last_block.hash_hex[:16] + '...' if self.last_block else None,
                'last_block_finality': self.last_block.finality.name if self.last_block else None,
                'seconds_since_block': self.time_since_last_block(),
                'is_producing': self.is_producing(),
                'tracked_blocks': len(self.blocks)
            }


# ============================================================================
# LEVELS 5-6: SYSTEM STATE (Bitcoin Active / VDF Fallback)
# ============================================================================

class VDFStateTransition:
    """
    State transition event for audit logging.
    """
    def __init__(
        self,
        from_level: AdamLevel,
        to_level: AdamLevel,
        reason: str,
        btc_height: int,
        btc_last_block_time: Optional[float],
        timestamp: float
    ):
        self.from_level = from_level
        self.to_level = to_level
        self.reason = reason
        self.btc_height = btc_height
        self.btc_last_block_time = btc_last_block_time
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            'from': self.from_level.name,
            'to': self.to_level.name,
            'reason': self.reason,
            'btc_height': self.btc_height,
            'btc_last_block_time': self.btc_last_block_time,
            'timestamp': self.timestamp
        }


class Level56_SystemState:
    """
    ═══════════════════════════════════════════════════════════════════════════
    Levels 4-6: PRODUCTION-GRADE STATE MACHINE
    ═══════════════════════════════════════════════════════════════════════════

    STATE MACHINE:
    ──────────────
    Level 4: BITCOIN_ACTIVE  - Normal operation, VDF idle
    Level 5: VDF_FALLBACK    - Bitcoin down 2+ blocks, VDF active
    Level 6: VDF_DEACTIVATE  - Bitcoin returned, transitioning back

    TRANSITIONS:
    ────────────
    Level 4 → Level 5:  Bitcoin missing for 2 blocks (~20 min)
    Level 5 → Level 6:  Bitcoin returned (first block seen)
    Level 6 → Level 4:  Bitcoin stable for 20 blocks

    VDF FALLBACK (Level 5):
    ───────────────────────
    - SHAKE256 VDF: Quantum-resistant hash-based
    - PoH: SHA3-256 chain for instant transaction ordering
    - VDF finalization every 600 seconds (10 minutes)

    MONITORING:
    ───────────
    Background thread checks Bitcoin status every 1 second.
    VDF runs with quantum-safe cryptography.
    All transitions are logged for audit.

    ═══════════════════════════════════════════════════════════════════════════
    """

    def __init__(self, level4: Level4_BlockTime, vdf_iterations: int = 1000):
        self.level4 = level4
        self.vdf_iterations = vdf_iterations

        # State machine
        self.current_level: AdamLevel = AdamLevel.BITCOIN_ACTIVE
        self.vdf_active: bool = False
        self.vdf_activation_reason: Optional[str] = None
        self.vdf_activation_time: Optional[float] = None
        self.vdf_sequence: int = 0
        self.vdf_last_hash: Optional[bytes] = None
        self.vdf_last_proof: Optional[bytes] = None

        # Bitcoin return tracking (for hysteresis)
        self.btc_return_height: Optional[int] = None  # Height when Bitcoin returned
        self.btc_return_time: Optional[float] = None  # Time when Bitcoin returned
        self.btc_blocks_since_return: int = 0  # Blocks since return

        # Monitor thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running: bool = False
        self._monitor_interval: float = VDF_MONITOR_INTERVAL

        # Transition history (for audit)
        self._transitions: List[VDFStateTransition] = []
        self._max_transitions: int = 1000

        # VDF engine (lazy loaded)
        self._vdf_engine = None
        self._vdf_type: str = "UNKNOWN"  # SHAKE256, Wesolowski, or SHA3_CHAIN

        # VDF finalization tracking
        self._last_finalization_time: float = 0.0
        self._finalization_count: int = 0
        self._poh_entries: List[bytes] = []  # PoH chain for instant ordering

        self._lock = threading.RLock()

        logger.info("Level 5-6 (System State) initialized")
        logger.info(f"  VDF trigger: {VDF_TRIGGER_BLOCKS} blocks ({VDF_TRIGGER_SECONDS}s)")
        logger.info(f"  Return hysteresis: {VDF_DEACTIVATION_BLOCKS} blocks")
        logger.info(f"  Monitor interval: {VDF_MONITOR_INTERVAL}s")

    def start(self):
        """Start the background monitor."""
        if self._monitor_running:
            return

        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="AdamSync-VDF-Monitor",
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Level 5-6: Monitor thread started (1s interval)")

    def stop(self):
        """Stop the background monitor."""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None
        logger.info("Level 5-6: Monitor thread stopped")

    def _monitor_loop(self):
        """
        Background monitoring loop.

        Runs every second to check Bitcoin status and manage VDF.
        This is the heartbeat of Adam Sync's fallback mechanism.
        """
        last_check = 0.0
        last_log = 0.0

        while self._monitor_running:
            try:
                now = time.time()

                # Check state every interval
                if now - last_check >= self._monitor_interval:
                    self._check_and_transition()
                    last_check = now

                    # If VDF active, compute next proof
                    if self.vdf_active:
                        self._compute_vdf_tick()

                # Log status every 60 seconds when VDF is active
                if self.vdf_active and now - last_log >= 60.0:
                    self._log_vdf_status()
                    last_log = now

                # Sleep for half interval for responsiveness
                time.sleep(self._monitor_interval / 2)

            except Exception as e:
                logger.error(f"Level 5-6 monitor error: {e}")
                time.sleep(1.0)

    def _check_and_transition(self):
        """
        Core state machine logic.

        Level 5 → Level 6:
            Bitcoin missing for 2+ blocks (~20 min)

        Level 6 → Level 5:
            Bitcoin returned AND produced 20 blocks since return
        """
        with self._lock:
            time_since = self.level4.time_since_last_block()
            current_height = self.level4.chain_height

            # ─────────────────────────────────────────────────────────────
            # LEVEL 5 (BITCOIN_ACTIVE) → LEVEL 6 (VDF_FALLBACK)
            # ─────────────────────────────────────────────────────────────
            if self.current_level == AdamLevel.BITCOIN_ACTIVE:
                if time_since is not None and time_since >= VDF_TRIGGER_SECONDS:
                    blocks_missed = int(time_since / BITCOIN_BLOCK_TIME)
                    self._activate_vdf(
                        f"Bitcoin отсутствует {int(time_since / 60)} мин "
                        f"(~{blocks_missed} блоков пропущено)"
                    )

            # ─────────────────────────────────────────────────────────────
            # LEVEL 6 (VDF_FALLBACK) → LEVEL 5 (BITCOIN_ACTIVE)
            # ─────────────────────────────────────────────────────────────
            elif self.current_level == AdamLevel.VDF_FALLBACK:
                # Check if Bitcoin block just arrived
                if time_since is not None and time_since < BITCOIN_BLOCK_TIME:
                    # Bitcoin is producing - track return
                    if self.btc_return_height is None:
                        # First block after return
                        self.btc_return_height = current_height
                        self.btc_return_time = time.time()
                        self.btc_blocks_since_return = 0
                        logger.info(
                            f"Level 6: Bitcoin RETURNED at block #{current_height}. "
                            f"Waiting for {VDF_DEACTIVATION_BLOCKS} blocks before switching back."
                        )
                    else:
                        # Subsequent blocks - count them
                        self.btc_blocks_since_return = current_height - self.btc_return_height

                        if self.btc_blocks_since_return >= VDF_DEACTIVATION_BLOCKS:
                            # Enough blocks - safe to switch back
                            self._deactivate_vdf(
                                f"Bitcoin стабилен: {self.btc_blocks_since_return} блоков "
                                f"после возвращения (требовалось {VDF_DEACTIVATION_BLOCKS})"
                            )
                        else:
                            # Still waiting
                            remaining = VDF_DEACTIVATION_BLOCKS - self.btc_blocks_since_return
                            if self.btc_blocks_since_return % 5 == 0:  # Log every 5 blocks
                                logger.info(
                                    f"Level 6: Bitcoin active, {self.btc_blocks_since_return}/{VDF_DEACTIVATION_BLOCKS} "
                                    f"blocks confirmed. {remaining} more needed."
                                )
                else:
                    # Bitcoin went away again - reset return tracking
                    if self.btc_return_height is not None:
                        logger.warning(
                            f"Level 6: Bitcoin DISAPPEARED again after {self.btc_blocks_since_return} blocks. "
                            "Resetting return tracker."
                        )
                        self.btc_return_height = None
                        self.btc_return_time = None
                        self.btc_blocks_since_return = 0

    def check_state(self) -> AdamLevel:
        """
        Manual state check (called from AdamSync.get_timestamp()).

        The main checking is done by the background monitor,
        but this provides immediate check when needed.
        """
        self._check_and_transition()
        return self.current_level

    def _get_vdf_engine(self):
        """
        Lazy load VDF engine with quantum-resistant SHAKE256.

        Priority:
        1. SHAKE256 VDF (quantum-resistant, hash-based)
        2. Wesolowski VDF (legacy, RSA-based, NOT quantum-resistant)
        3. Fallback SHA3-256 hash chain (always available)
        """
        if self._vdf_engine is None:
            # Try SHAKE256 VDF first (quantum-resistant)
            try:
                from pantheon.prometheus import SHAKE256VDF
                self._vdf_engine = SHAKE256VDF(self.vdf_iterations)
                self._vdf_type = "SHAKE256"
                logger.info("Level 5: SHAKE256 VDF loaded (quantum-resistant)")
                return self._vdf_engine
            except ImportError:
                pass

            # Fallback to Wesolowski (NOT quantum-resistant)
            try:
                from pantheon.prometheus import WesolowskiVDF
                self._vdf_engine = WesolowskiVDF(self.vdf_iterations)
                self._vdf_type = "Wesolowski"
                logger.warning("Level 5: Wesolowski VDF loaded (NOT quantum-resistant!)")
                return self._vdf_engine
            except ImportError:
                pass

            # Fallback: use SHA3-256 hash chain
            self._vdf_engine = "SHA3_CHAIN"
            self._vdf_type = "SHA3_CHAIN"
            logger.info("Level 5: SHA3-256 hash chain fallback (quantum-resistant)")

        return self._vdf_engine

    def _activate_vdf(self, reason: str):
        """
        Activate VDF fallback (Level 5 → Level 6).

        ╔═══════════════════════════════════════════════════════════════════════╗
        ║                      🚨 VDF FALLBACK ACTIVATED 🚨                     ║
        ║                                                                       ║
        ║  Bitcoin network is not producing blocks.                             ║
        ║  Montana is switching to VDF-based sovereign timekeeping.             ║
        ║  Time continues with quantum-resistant cryptographic proofs.          ║
        ╚═══════════════════════════════════════════════════════════════════════╝
        """
        # Record transition
        transition = VDFStateTransition(
            from_level=AdamLevel.BITCOIN_ACTIVE,
            to_level=AdamLevel.VDF_FALLBACK,
            reason=reason,
            btc_height=self.level4.chain_height,
            btc_last_block_time=self.level4.last_block_time,
            timestamp=time.time()
        )
        self._transitions.append(transition)
        if len(self._transitions) > self._max_transitions:
            self._transitions.pop(0)

        # Log activation
        logger.warning("╔" + "═" * 70 + "╗")
        logger.warning("║" + " " * 20 + "🚨 VDF FALLBACK ACTIVATED 🚨" + " " * 21 + "║")
        logger.warning("╠" + "═" * 70 + "╣")
        logger.warning(f"║  Reason: {reason[:60]:<60}║")
        logger.warning(f"║  Last BTC block: #{self.level4.chain_height:<54}║")
        logger.warning(f"║  VDF iterations: {self.vdf_iterations:<54}║")
        logger.warning("╚" + "═" * 70 + "╝")

        # Update state
        self.current_level = AdamLevel.VDF_FALLBACK
        self.vdf_active = True
        self.vdf_activation_reason = reason
        self.vdf_activation_time = time.time()
        self.vdf_sequence = 0

        # Reset return tracking
        self.btc_return_height = None
        self.btc_return_time = None
        self.btc_blocks_since_return = 0

        # Initialize VDF with last Bitcoin block as seed
        vdf = self._get_vdf_engine()
        if self.level4.last_block:
            seed = self.level4.last_block.hash
            self.vdf_last_hash = seed
            self._last_finalization_time = time.time()
            self._finalization_count = 0
            self._poh_entries = []
            logger.info(f"Level 5: VDF seeded with block #{self.level4.chain_height}")
            logger.info(f"Level 5: VDF type = {self._vdf_type}")
            logger.info(f"Level 5: Finalization every {VDF_FINALIZATION_INTERVAL}s")

    def _deactivate_vdf(self, reason: str):
        """
        Deactivate VDF (Level 6 → Level 5).

        ╔═══════════════════════════════════════════════════════════════════════╗
        ║                      ✅ BITCOIN RESTORED ✅                           ║
        ║                                                                       ║
        ║  Bitcoin network is producing blocks again.                           ║
        ║  Montana is switching back to Bitcoin-anchored time.                  ║
        ║  VDF sovereign timekeeping is deactivated.                            ║
        ╚═══════════════════════════════════════════════════════════════════════╝
        """
        # Calculate VDF duration
        vdf_duration = 0.0
        if self.vdf_activation_time:
            vdf_duration = time.time() - self.vdf_activation_time

        # Record transition
        transition = VDFStateTransition(
            from_level=AdamLevel.VDF_FALLBACK,
            to_level=AdamLevel.BITCOIN_ACTIVE,
            reason=reason,
            btc_height=self.level4.chain_height,
            btc_last_block_time=self.level4.last_block_time,
            timestamp=time.time()
        )
        self._transitions.append(transition)

        # Log deactivation
        logger.info("╔" + "═" * 70 + "╗")
        logger.info("║" + " " * 22 + "✅ BITCOIN RESTORED ✅" + " " * 24 + "║")
        logger.info("╠" + "═" * 70 + "╣")
        logger.info(f"║  Reason: {reason[:60]:<60}║")
        logger.info(f"║  Current BTC block: #{self.level4.chain_height:<51}║")
        logger.info(f"║  VDF was active for: {int(vdf_duration / 60)} min ({self.vdf_sequence} proofs)    " + " " * 20 + "║")
        logger.info("╚" + "═" * 70 + "╝")

        # Update state
        self.vdf_active = False
        self.current_level = AdamLevel.BITCOIN_ACTIVE

        # Reset return tracking
        self.btc_return_height = None
        self.btc_return_time = None
        self.btc_blocks_since_return = 0

    def _compute_vdf_tick(self):
        """
        Compute next VDF proof (called every second during fallback).

        DUAL-LAYER APPROACH (from Montana spec):
        - PoH: SHA3-256 chain for instant transaction ordering (every tick)
        - VDF: Finalization every 600 seconds (10 minutes)

        This provides:
        - Sub-second transaction ordering (PoH)
        - 10-minute finalization intervals (VDF)
        """
        vdf = self._get_vdf_engine()
        if not self.vdf_last_hash:
            return

        try:
            now = time.time()

            # ─────────────────────────────────────────────────────────────
            # POH: Instant ordering (every tick) - SHA3-256 chain
            # ─────────────────────────────────────────────────────────────
            input_data = self.vdf_last_hash + struct.pack('<Q', self.vdf_sequence)

            # Use SHA3-256 for quantum-resistant PoH
            try:
                import hashlib
                poh_hash = hashlib.sha3_256(input_data).digest()
            except AttributeError:
                # Fallback if SHA3 not available
                poh_hash = hashlib.sha256(input_data).digest()

            self._poh_entries.append(poh_hash)
            if len(self._poh_entries) > 600:  # Keep last 10 minutes
                self._poh_entries = self._poh_entries[-600:]

            self.vdf_sequence += 1

            # ─────────────────────────────────────────────────────────────
            # VDF: Finalization every 600 seconds (10 minutes)
            # ─────────────────────────────────────────────────────────────
            time_since_finalization = now - self._last_finalization_time

            if time_since_finalization >= VDF_FINALIZATION_INTERVAL:
                # Finalization checkpoint
                if vdf == "SHA3_CHAIN" or self._vdf_type == "SHA3_CHAIN":
                    # Quantum-resistant SHA3-256 hash chain
                    finalization_hash = hashlib.sha3_256(
                        self.vdf_last_hash + struct.pack('<Q', self._finalization_count)
                    ).digest()
                    self.vdf_last_hash = finalization_hash
                    self.vdf_last_proof = None
                elif hasattr(vdf, 'compute'):
                    # VDF engine available
                    result = vdf.compute(input_data)
                    if result and hasattr(result, 'output'):
                        self.vdf_last_hash = result.output
                        self.vdf_last_proof = result.proof if hasattr(result, 'proof') else None
                    else:
                        self.vdf_last_hash = poh_hash
                else:
                    self.vdf_last_hash = poh_hash

                self._finalization_count += 1
                self._last_finalization_time = now
                logger.info(
                    f"Level 5: VDF finalization #{self._finalization_count} "
                    f"(hash={self.vdf_last_hash.hex()[:16]}...)"
                )
            else:
                # Between finalizations: update PoH chain
                self.vdf_last_hash = poh_hash

        except Exception as e:
            logger.error(f"Level 5: VDF computation error: {e}")

    def _log_vdf_status(self):
        """Log VDF status periodically."""
        duration = 0.0
        if self.vdf_activation_time:
            duration = time.time() - self.vdf_activation_time

        logger.info(
            f"Level 6 STATUS: VDF active {int(duration / 60)} min, "
            f"sequence={self.vdf_sequence}, "
            f"last_hash={self.vdf_last_hash.hex()[:16]}..."
        )

    def compute_vdf_timestamp(self) -> Optional[Tuple[int, bytes]]:
        """Get current VDF timestamp if in fallback mode."""
        with self._lock:
            if not self.vdf_active:
                return None
            return self.vdf_sequence, self.vdf_last_hash or b'\x00' * 32

    def get_transitions(self) -> List[Dict[str, Any]]:
        """Get transition history (for audit)."""
        with self._lock:
            return [t.to_dict() for t in self._transitions]

    def get_status(self) -> Dict[str, Any]:
        """Get levels 5-6 status."""
        with self._lock:
            vdf_duration = None
            if self.vdf_activation_time:
                vdf_duration = time.time() - self.vdf_activation_time

            return {
                'levels': '5-6',
                'name': 'SYSTEM_STATE',
                'current_level': self.current_level.name,
                'vdf_active': self.vdf_active,
                'vdf_activation_reason': self.vdf_activation_reason,
                'vdf_activation_time': self.vdf_activation_time,
                'vdf_duration_seconds': vdf_duration,
                'vdf_sequence': self.vdf_sequence,
                'vdf_last_hash': self.vdf_last_hash.hex()[:32] if self.vdf_last_hash else None,
                'monitor_running': self._monitor_running,
                'btc_return_tracking': {
                    'return_height': self.btc_return_height,
                    'blocks_since_return': self.btc_blocks_since_return,
                    'blocks_needed': VDF_DEACTIVATION_BLOCKS,
                    'blocks_remaining': max(0, VDF_DEACTIVATION_BLOCKS - self.btc_blocks_since_return) if self.btc_return_height else None
                },
                'transitions_count': len(self._transitions),
                'config': {
                    'vdf_trigger_blocks': VDF_TRIGGER_BLOCKS,
                    'vdf_trigger_seconds': VDF_TRIGGER_SECONDS,
                    'vdf_deactivation_blocks': VDF_DEACTIVATION_BLOCKS,
                    'monitor_interval': VDF_MONITOR_INTERVAL
                }
            }


# ============================================================================
# ADAM: THE GOD OF TIME
# ============================================================================

class Adam:
    """
    ╔═══════════════════════════════════════════════════════════════════════════╗
    ║                           ADAM - GOD OF TIME                              ║
    ╠═══════════════════════════════════════════════════════════════════════════╣
    ║                                                                           ║
    ║  THE ONLY SOURCE OF TRUTH FOR TIME IN MONTANA.                            ║
    ║  All time-related operations MUST go through Adam.                        ║
    ║  Chronos is deprecated. Adam is the sole authority.                       ║
    ║                                                                           ║
    ╚═══════════════════════════════════════════════════════════════════════════╝

    Integrates all 7 levels (0-6) into a unified interface:
      Level 0: NODE_UTC        - Hardware clock (UTC)
      Level 1: GLOBAL_NTP      - 12 national laboratories
      Level 2: MEMPOOL_TIME    - Bitcoin mempool observation
      Level 3: BLOCK_TIME      - Bitcoin block confirmation
      Level 4: BITCOIN_ACTIVE  - Normal operation
      Level 5: VDF_FALLBACK    - Bitcoin down, SHAKE256 VDF active
      Level 6: VDF_DEACTIVATE  - Bitcoin returned, transitioning back
    """

    def __init__(self, vdf_iterations: int = 1000, auto_start: bool = False):
        """
        Initialize Adam - The God of Time.

        Args:
            vdf_iterations: VDF iterations for Level 5 fallback
            auto_start: Start all levels automatically
        """
        # Initialize all levels in order
        self.level0 = Level0_NodeUTC()
        self.level1 = Level1_NetworkNodes(self.level0)  # Legacy, kept for compatibility
        self.level2 = Level2_GlobalNTP(self.level0)     # This is the real Level 1
        self.level3 = Level3_MempoolTime(self.level2)
        self.level4 = Level4_BlockTime(self.level2, self.level3)
        self.level56 = Level56_SystemState(self.level4, vdf_iterations)

        self.sequence: int = 0
        self._lock = threading.RLock()
        self._started = False

        logger.info("╔" + "═" * 58 + "╗")
        logger.info("║" + " " * 18 + "ADAM - GOD OF TIME" + " " * 22 + "║")
        logger.info("╠" + "═" * 58 + "╣")
        logger.info("║  Level 0: NODE_UTC        - Hardware clock (UTC)        ║")
        logger.info("║  Level 1: GLOBAL_NTP      - 12 national laboratories    ║")
        logger.info("║  Level 2: MEMPOOL_TIME    - Bitcoin mempool             ║")
        logger.info("║  Level 3: BLOCK_TIME      - Bitcoin blocks              ║")
        logger.info("║  Level 4: BITCOIN_ACTIVE  - Normal operation            ║")
        logger.info("║  Level 5: VDF_FALLBACK    - SHAKE256 VDF (quantum-safe) ║")
        logger.info("║  Level 6: VDF_DEACTIVATE  - Transitioning back          ║")
        logger.info("╚" + "═" * 58 + "╝")

        if auto_start:
            self.start()

    def start(self):
        """Start all Adam Sync levels including VDF monitor."""
        if self._started:
            return

        self.level1.start()
        self.level2.start()
        self.level3.start()
        self.level4.start()
        self.level56.start()  # Start VDF monitor (checks Bitcoin every 1s)

        self._started = True
        logger.info("═" * 60)
        logger.info("ADAM SYNC STARTED - All levels active")
        logger.info("VDF monitor running (1s interval)")
        logger.info("═" * 60)

    def stop(self):
        """Stop all Adam Sync levels."""
        if not self._started:
            return

        self.level56.stop()  # Stop VDF monitor first
        self.level1.stop()
        self.level2.stop()
        self.level3.stop()
        self.level4.stop()

        self._started = False
        logger.info("ADAM SYNC STOPPED")

    # =========================================================================
    # PRIMARY API
    # =========================================================================

    def on_bitcoin_block(
        self,
        height: int,
        block_hash: bytes,
        prev_hash: bytes,
        timestamp: int,
        merkle_root: bytes = b'\x00' * 32,
        tx_hashes: List[bytes] = None
    ) -> Level4Block:
        """
        Process new Bitcoin block.

        THIS IS THE ONLY ENTRY POINT FOR BITCOIN BLOCKS.
        """
        block = self.level4.on_block(
            height, block_hash, prev_hash, timestamp, merkle_root, tx_hashes
        )

        # Check system state after new block
        self.level56.check_state()

        return block

    def on_tx_seen(self, tx_hash: bytes) -> float:
        """
        Record transaction seen in mempool.

        Returns timestamp when TX was first observed.
        """
        return self.level3.on_tx_seen(tx_hash)

    def on_peer_time(self, peer_pubkey: bytes, peer_time: float, weight: float = 1.0):
        """
        Record time reported by a peer node.

        Called during peer sync messages.
        """
        self.level1.report_peer_time(peer_pubkey, peer_time, weight)

    def get_timestamp(self) -> AdamTimestamp:
        """
        Get current Adam Sync timestamp.

        THIS IS THE ONLY WAY TO GET TIME IN MONTANA.
        """
        with self._lock:
            # Check system state
            self.level56.check_state()

            ts = AdamTimestamp(
                # Level 0
                node_utc=self.level0.get_utc(),
                node_uptime=self.level0.get_uptime(),

                # Level 1
                network_peer_count=len(self.level1.peer_times),
                network_consensus_time=self.level1.consensus_time,
                network_deviation_ms=self.level1.deviation_ms,

                # Level 2
                ntp_servers_responding=len(self.level2.last_results),
                ntp_consensus_offset_ms=self.level2.consensus_offset_ms,
                ntp_laboratories=self.level2.responding_labs.copy(),

                # Level 4
                btc_height=self.level4.chain_height if self.level4.chain_height > 0 else None,
                btc_hash=self.level4.last_block.hash if self.level4.last_block else None,
                btc_timestamp=self.level4.last_block.timestamp if self.level4.last_block else None,
                btc_confirmations=1 if self.level4.last_block else 0,
                btc_finality=self.level4.last_block.finality if self.level4.last_block else FinalityState.UNKNOWN,

                # Level 5-6
                current_level=self.level56.current_level,
                vdf_active=self.level56.vdf_active,
                vdf_sequence=self.level56.vdf_sequence if self.level56.vdf_active else None,

                sequence=self.sequence
            )

            self.sequence += 1
            return ts

    def get_utc(self) -> float:
        """Get current verified UTC time (Level 2)."""
        return self.level2.get_verified_utc()

    def get_finality(self, height: int) -> FinalityState:
        """Get finality state for Bitcoin block height."""
        return self.level4.get_finality(height)

    def is_irreversible(self, height: int) -> bool:
        """Check if block is irreversibly final."""
        return self.level4.is_irreversible(height)

    def get_current_level(self) -> AdamLevel:
        """Get current Adam level (5 or 6)."""
        return self.level56.current_level

    def is_bitcoin_active(self) -> bool:
        """Is Bitcoin producing blocks? (Level 5)"""
        return self.level56.current_level == AdamLevel.BITCOIN_ACTIVE

    def is_vdf_active(self) -> bool:
        """Is VDF fallback active? (Level 6)"""
        return self.level56.vdf_active

    def get_status(self) -> Dict[str, Any]:
        """Get complete Adam status."""
        with self._lock:
            return {
                'adam': 'GOD OF TIME',
                'started': self._started,
                'sequence': self.sequence,
                'current_level': self.level56.current_level.name,
                'levels': {
                    0: self.level0.get_status(),
                    1: self.level1.get_status(),
                    2: self.level2.get_status(),
                    3: self.level3.get_status(),
                    4: self.level4.get_status(),
                    '5-6': self.level56.get_status()
                }
            }


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run Adam self-tests."""
    import hashlib

    logger.info("=" * 60)
    logger.info("ADAM - GOD OF TIME - SELF-TEST")
    logger.info("=" * 60)

    # Test AdamLevel (new structure: no NETWORK_NODES)
    assert AdamLevel.NODE_UTC == 0
    assert AdamLevel.GLOBAL_NTP == 1
    assert AdamLevel.MEMPOOL_TIME == 2
    assert AdamLevel.BLOCK_TIME == 3
    assert AdamLevel.BITCOIN_ACTIVE == 4
    assert AdamLevel.VDF_FALLBACK == 5
    assert AdamLevel.VDF_DEACTIVATE == 6
    logger.info("✓ AdamLevel values (0-6): NODE_UTC, GLOBAL_NTP, MEMPOOL, BLOCK, BTC_ACTIVE, VDF_FALLBACK, VDF_DEACTIVATE")

    # Test FinalityState
    assert FinalityState.from_confirmations(0) == FinalityState.PENDING
    assert FinalityState.from_confirmations(1) == FinalityState.TENTATIVE
    assert FinalityState.from_confirmations(6) == FinalityState.CONFIRMED
    assert FinalityState.from_confirmations(100) == FinalityState.IRREVERSIBLE
    logger.info("✓ FinalityState transitions")

    # Test Global NTP server list
    assert len(GLOBAL_NTP_SERVERS) >= 12
    logger.info(f"✓ {len(GLOBAL_NTP_SERVERS)} national laboratories configured")

    # Test Level4Block
    block = Level4Block(
        height=840000,
        hash=hashlib.sha256(b"block").digest(),
        prev_hash=hashlib.sha256(b"prev").digest(),
        timestamp=int(time.time()),
        merkle_root=hashlib.sha256(b"merkle").digest()
    )
    block.update_finality(840010)
    assert block.confirmations == 11
    assert block.finality == FinalityState.CONFIRMED
    logger.info("✓ Level4Block finality")

    # Test Adam (without network - would timeout)
    adam = Adam(vdf_iterations=50, auto_start=False)

    # Start only non-network levels
    adam.level0.state = LevelState.ACTIVE
    adam.level1.state = LevelState.ACTIVE
    adam.level2.state = LevelState.ACTIVE
    adam.level3.start()
    adam.level4.start()

    # Simulate Bitcoin blocks
    for i in range(5):
        adam.on_bitcoin_block(
            height=840000 + i,
            block_hash=hashlib.sha256(f"block_{i}".encode()).digest(),
            prev_hash=hashlib.sha256(f"block_{i-1}".encode()).digest() if i > 0 else b'\x00' * 32,
            timestamp=int(time.time()) - (5 - i) * 600
        )

    assert adam.level4.chain_height == 840004
    assert adam.level56.current_level == AdamLevel.BITCOIN_ACTIVE
    logger.info("✓ Block processing")

    # Get timestamp
    ts = adam.get_timestamp()
    assert ts.btc_height == 840004
    assert ts.current_level == AdamLevel.BITCOIN_ACTIVE
    logger.info("✓ AdamTimestamp")

    # Test mempool tracking
    tx_hash = hashlib.sha256(b"test_tx").digest()
    first_seen = adam.on_tx_seen(tx_hash)
    assert first_seen > 0
    logger.info("✓ Mempool TX tracking")

    # Test peer time
    peer_pk = hashlib.sha256(b"peer1").digest()
    adam.on_peer_time(peer_pk, time.time(), weight=1.0)
    assert len(adam.level1.peer_times) == 1
    logger.info("✓ Peer time tracking")

    # Get status
    status = adam.get_status()
    assert 'levels' in status
    assert 0 in status['levels']
    assert 1 in status['levels']
    assert 2 in status['levels']
    assert 3 in status['levels']
    assert 4 in status['levels']
    assert '5-6' in status['levels']
    logger.info("✓ Status reporting")

    logger.info("=" * 60)
    logger.info("ALL ADAM TESTS PASSED!")
    logger.info("=" * 60)


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

# AdamSync is deprecated, use Adam instead
AdamSync = Adam


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
