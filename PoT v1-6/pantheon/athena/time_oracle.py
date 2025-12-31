"""
Montana v4.2 - Time Oracle (DEPRECATED)

═══════════════════════════════════════════════════════════════════════════════
                              DEPRECATION NOTICE
═══════════════════════════════════════════════════════════════════════════════

This module is DEPRECATED. Use Adam directly:

    from pantheon.adam import Adam, AdamLevel, FinalityState

    adam = Adam()
    adam.start()
    ts = adam.get_timestamp()

═══════════════════════════════════════════════════════════════════════════════
"""

import warnings
import logging
from typing import Dict, Any

from pantheon.adam import (
    Adam, AdamLevel, FinalityState, AdamTimestamp,
    Level4Block, VDF_TRIGGER_SECONDS
)

logger = logging.getLogger("montana.time_oracle")


class TimeOracleMode:
    """DEPRECATED: Use AdamLevel instead."""
    BITCOIN = AdamLevel.BITCOIN_ACTIVE
    VDF = AdamLevel.VDF_FALLBACK
    HYBRID = AdamLevel.BITCOIN_ACTIVE


class TimeOracle:
    """DEPRECATED: Use Adam instead."""

    def __init__(self, vdf_iterations: int = 1000, auto_fallback: bool = True):
        warnings.warn(
            "TimeOracle is deprecated. Use Adam from pantheon.adam instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._adam = Adam(vdf_iterations=vdf_iterations)
        self.auto_fallback = auto_fallback
        self.mode = TimeOracleMode.BITCOIN
        self.sequence = 0

    def start(self):
        self._adam.start()

    def stop(self):
        self._adam.stop()

    def get_timestamp(self):
        return self._adam.get_timestamp()

    def on_bitcoin_block(self, height: int, block_hash: bytes, timestamp: int, prev_hash: bytes = b'\x00' * 32):
        return self._adam.on_bitcoin_block(height=height, block_hash=block_hash, prev_hash=prev_hash, timestamp=timestamp)

    def get_status(self) -> Dict[str, Any]:
        adam_status = self._adam.get_status()
        levels = adam_status.get('levels', {})
        return {
            'mode': self._adam.level56.current_level.name,
            'sequence': self._adam.sequence,
            'bitcoin': levels.get('4', levels.get(4, {})),
            'vdf': levels.get('5-6', {}),
            'auto_fallback': self.auto_fallback,
            '_deprecated': True,
            '_use': 'Adam from pantheon.adam'
        }
