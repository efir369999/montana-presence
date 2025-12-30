"""
Montana v4.0 - Unified Time Oracle

Bitcoin as Clock with VDF as Backup.

The TimeOracle provides a unified interface for:
- Bitcoin block anchoring (primary)
- VDF fallback (when Bitcoin unavailable)

Montana survives Bitcoin's death - VDF provides sovereign backup.

NOTE: This module is maintained for backward compatibility.
For new code, use AdamSync from pantheon.chronos which provides:
- Clear layer separation (Server Time → Bitcoin → VDF)
- Explicit finality states (PENDING → TENTATIVE → CONFIRMED → IRREVERSIBLE)
- Better clock drift handling with weighted UTC averages

Time cannot be bought. Trust cannot be purchased.
"""

import time
import logging
import threading
from typing import Optional, Tuple, Dict, Any, Union
from dataclasses import dataclass
from enum import IntEnum, auto

from .bitcoin_oracle import (
    BitcoinOracle, BitcoinBlock, AnchorRecord, MontanaTime,
    OracleStatus, HALVING_INTERVAL, EXPECTED_BLOCK_TIME
)
from .vdf_fallback import (
    VDFFallback, VDFTimestamp, VDFStatus, VDF_MIN_ITERATIONS
)

logger = logging.getLogger("montana.time_oracle")


# ============================================================================
# TIME ORACLE MODE
# ============================================================================

class TimeOracleMode(IntEnum):
    """Time oracle operating mode."""
    BITCOIN = auto()    # Bitcoin is primary time source
    VDF = auto()        # VDF fallback is active
    HYBRID = auto()     # Both sources available, transitioning


# ============================================================================
# UNIFIED TIMESTAMP
# ============================================================================

@dataclass
class Timestamp:
    """
    Unified timestamp from either source.

    Can be anchored to Bitcoin block or VDF computation.
    """
    # Common fields
    timestamp: int              # Wall clock time
    sequence: int              # Global sequence number

    # Bitcoin anchor (if available)
    btc_height: Optional[int] = None
    btc_hash: Optional[bytes] = None
    anchor: Optional[AnchorRecord] = None

    # VDF anchor (if used)
    vdf_timestamp: Optional[VDFTimestamp] = None

    # Source
    source: TimeOracleMode = TimeOracleMode.BITCOIN

    @property
    def is_bitcoin_anchored(self) -> bool:
        """Check if timestamp is Bitcoin-anchored."""
        return self.btc_height is not None

    @property
    def is_vdf_anchored(self) -> bool:
        """Check if timestamp uses VDF."""
        return self.vdf_timestamp is not None

    def get_montana_time(self) -> Optional[MontanaTime]:
        """Get Montana time if Bitcoin-anchored."""
        if self.btc_height:
            return MontanaTime.from_btc_height(self.btc_height)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'timestamp': self.timestamp,
            'sequence': self.sequence,
            'source': TimeOracleMode(self.source).name
        }

        if self.btc_height:
            result['btc_height'] = self.btc_height
            result['btc_hash'] = self.btc_hash.hex()[:16] + '...' if self.btc_hash else None

        if self.vdf_timestamp:
            result['vdf_sequence'] = self.vdf_timestamp.sequence

        return result


# ============================================================================
# UNIFIED TIME ORACLE
# ============================================================================

class TimeOracle:
    """
    Unified Time Oracle for Montana v4.0.

    Provides seamless switching between Bitcoin and VDF time sources.

    Philosophy:
    - Bitcoin has not had downtime since 2013
    - VDF is insurance against an event that may never occur
    - But it exists — Montana survives Bitcoin's death
    """

    def __init__(
        self,
        vdf_iterations: int = VDF_MIN_ITERATIONS,
        auto_fallback: bool = True
    ):
        """
        Initialize Time Oracle.

        Args:
            vdf_iterations: VDF iterations for fallback
            auto_fallback: Automatically switch to VDF when needed
        """
        # Initialize both oracles
        self.bitcoin_oracle = BitcoinOracle(
            on_fallback_needed=self._on_fallback_needed if auto_fallback else None
        )
        self.vdf_fallback = VDFFallback(iterations=vdf_iterations)

        self.auto_fallback = auto_fallback

        # State
        self.mode = TimeOracleMode.BITCOIN
        self.sequence = 0
        self._lock = threading.RLock()

        # Callbacks
        self._mode_change_callbacks = []

        logger.info("Time Oracle initialized (mode=BITCOIN)")

    def _on_fallback_needed(self, reason: str):
        """Handle fallback trigger from Bitcoin oracle."""
        self.switch_to_vdf(reason)

    def switch_to_vdf(self, reason: str = ""):
        """
        Switch to VDF fallback mode.

        Called when Bitcoin becomes unavailable.
        """
        with self._lock:
            if self.mode == TimeOracleMode.VDF:
                return

            logger.warning(f"Switching to VDF: {reason}")
            self.mode = TimeOracleMode.VDF
            self.vdf_fallback.activate(reason)

            self._notify_mode_change(TimeOracleMode.VDF, reason)

    def switch_to_bitcoin(self, reason: str = ""):
        """
        Switch back to Bitcoin mode.

        Called when Bitcoin becomes available again.
        """
        with self._lock:
            if self.mode == TimeOracleMode.BITCOIN:
                return

            logger.info(f"Bitcoin restored, switching back: {reason}")
            self.mode = TimeOracleMode.BITCOIN
            self.vdf_fallback.deactivate(reason)

            self._notify_mode_change(TimeOracleMode.BITCOIN, reason)

    def get_timestamp(self) -> Timestamp:
        """
        Get current timestamp from active source.

        Returns:
            Unified Timestamp from Bitcoin or VDF
        """
        with self._lock:
            # Check if we need to switch modes
            if self.mode == TimeOracleMode.BITCOIN:
                needs_fallback, reason = self.bitcoin_oracle.check_fallback_needed()
                if needs_fallback and self.auto_fallback:
                    self.switch_to_vdf(reason)

            elif self.mode == TimeOracleMode.VDF:
                # Check if Bitcoin is back
                if self.bitcoin_oracle.is_producing_blocks():
                    self.switch_to_bitcoin("Bitcoin restored")

            # Get timestamp from current source
            if self.mode == TimeOracleMode.BITCOIN:
                return self._get_bitcoin_timestamp()
            else:
                return self._get_vdf_timestamp()

    def _get_bitcoin_timestamp(self) -> Timestamp:
        """Get timestamp from Bitcoin oracle."""
        anchor = self.bitcoin_oracle.get_current_anchor()

        ts = Timestamp(
            timestamp=int(time.time()),
            sequence=self.sequence,
            source=TimeOracleMode.BITCOIN
        )

        if anchor:
            ts.btc_height = anchor.btc_height
            ts.btc_hash = anchor.btc_hash
            ts.anchor = anchor

        self.sequence += 1
        return ts

    def _get_vdf_timestamp(self) -> Timestamp:
        """Get timestamp from VDF fallback."""
        vdf_ts = self.vdf_fallback.get_current_timestamp()

        # If no VDF timestamp yet, compute one
        if vdf_ts is None:
            vdf_ts = self.vdf_fallback.compute_timestamp()

        ts = Timestamp(
            timestamp=int(time.time()),
            sequence=self.sequence,
            source=TimeOracleMode.VDF,
            vdf_timestamp=vdf_ts
        )

        self.sequence += 1
        return ts

    def on_bitcoin_block(
        self,
        height: int,
        block_hash: bytes,
        timestamp: int,
        prev_hash: bytes = b'\x00' * 32
    ) -> AnchorRecord:
        """
        Process new Bitcoin block.

        Args:
            height: Block height
            block_hash: Block hash
            timestamp: Block timestamp
            prev_hash: Previous block hash

        Returns:
            AnchorRecord
        """
        anchor = self.bitcoin_oracle.on_new_block(
            height, block_hash, timestamp, prev_hash
        )

        # Check if we should switch back to Bitcoin
        if self.mode == TimeOracleMode.VDF and self.bitcoin_oracle.is_producing_blocks():
            self.switch_to_bitcoin("Bitcoin resumed producing blocks")

        return anchor

    def get_montana_time(self) -> Optional[MontanaTime]:
        """Get current Montana time (Bitcoin-based)."""
        return self.bitcoin_oracle.get_montana_time()

    def get_time_saturation(self, node_join_height: int) -> float:
        """
        Get TIME score saturation for a node.

        TIME resets at halving - no permanent dynasties.
        """
        return self.bitcoin_oracle.get_time_saturation(node_join_height)

    def register_mode_callback(self, callback):
        """Register callback for mode changes."""
        self._mode_change_callbacks.append(callback)

    def _notify_mode_change(self, new_mode: TimeOracleMode, reason: str):
        """Notify registered callbacks of mode change."""
        for callback in self._mode_change_callbacks:
            try:
                callback(new_mode, reason)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get oracle status."""
        with self._lock:
            bitcoin_status = self.bitcoin_oracle.get_status()
            vdf_status = self.vdf_fallback.get_status()

            return {
                'mode': TimeOracleMode(self.mode).name,
                'sequence': self.sequence,
                'bitcoin': bitcoin_status,
                'vdf': vdf_status,
                'auto_fallback': self.auto_fallback
            }

    def verify_timestamp(self, ts: Timestamp) -> Tuple[bool, str]:
        """
        Verify a timestamp.

        Args:
            ts: Timestamp to verify

        Returns:
            (is_valid, reason) tuple
        """
        if ts.source == TimeOracleMode.BITCOIN:
            if ts.anchor:
                return self.bitcoin_oracle.verify_anchor(ts.anchor)
            return True, "Valid (no anchor to verify)"

        elif ts.source == TimeOracleMode.VDF:
            if ts.vdf_timestamp:
                return self.vdf_fallback.verify_timestamp(ts.vdf_timestamp)
            return True, "Valid (no VDF timestamp to verify)"

        return False, "Unknown source"


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run Time Oracle self-tests."""
    import hashlib

    logger.info("Running Time Oracle self-tests...")

    # Create oracle
    oracle = TimeOracle(vdf_iterations=50)
    assert oracle.mode == TimeOracleMode.BITCOIN
    logger.info("  Oracle initialization")

    # Simulate Bitcoin blocks
    for i in range(3):
        oracle.on_bitcoin_block(
            height=840000 + i,
            block_hash=hashlib.sha256(f"block_{i}".encode()).digest(),
            timestamp=int(time.time()) - (3 - i) * 600
        )
    logger.info("  Bitcoin block processing")

    # Get timestamp
    ts = oracle.get_timestamp()
    assert ts.source == TimeOracleMode.BITCOIN
    assert ts.btc_height == 840002
    logger.info("  Bitcoin timestamp")

    # Get Montana time
    mt = oracle.get_montana_time()
    assert mt is not None
    assert mt.epoch == 4
    logger.info("  Montana time")

    # Force fallback
    oracle.switch_to_vdf("Test fallback")
    assert oracle.mode == TimeOracleMode.VDF
    logger.info("  VDF fallback switch")

    # Get VDF timestamp
    ts_vdf = oracle.get_timestamp()
    assert ts_vdf.source == TimeOracleMode.VDF
    logger.info("  VDF timestamp")

    # Switch back
    oracle.switch_to_bitcoin("Test restore")
    assert oracle.mode == TimeOracleMode.BITCOIN
    logger.info("  Bitcoin restore")

    # Status check
    status = oracle.get_status()
    assert 'mode' in status
    assert 'bitcoin' in status
    assert 'vdf' in status
    logger.info("  Status reporting")

    logger.info("All Time Oracle tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()
