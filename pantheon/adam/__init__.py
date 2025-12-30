"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              ADAM - GOD OF TIME                               ║
║                                                                               ║
║       ADAM = Anchored Deterministic Asynchronous Mesh                         ║
║                                                                               ║
║       THE ONLY SOURCE OF TRUTH FOR TIME IN MONTANA.                           ║
║       All time-related operations MUST go through Adam.                       ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  ADAM LEVELS (0-6):                                                           ║
║  ─────────────────                                                            ║
║  0 - NODE_UTC:        Node hardware clock (UTC)                               ║
║  1 - GLOBAL_NTP:      12 national laboratories (NIST, PTB, ВНИИФТРИ, etc.)    ║
║  2 - MEMPOOL_TIME:    Bitcoin mempool observation                             ║
║  3 - BLOCK_TIME:      Bitcoin block confirmation                              ║
║  4 - BITCOIN_ACTIVE:  Normal operation, VDF not needed                        ║
║  5 - VDF_FALLBACK:    Bitcoin down 2 blocks, SHAKE256 VDF active              ║
║  6 - VDF_DEACTIVATE:  Bitcoin returned +20 blocks, VDF shutting down          ║
║                                                                               ║
║  VDF FALLBACK:                                                                ║
║  ─────────────                                                                ║
║  Trigger: Bitcoin missing 2 blocks (~20 min)                                  ║
║  Return:  Bitcoin stable 20 blocks (~3.3 hours)                               ║
║  VDF: SHAKE256 finalization every 600 seconds (quantum-resistant)             ║
║  PoH: SHA3-256 chain for instant transaction ordering                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .adam import (
    Adam,
    AdamLevel,
    AdamTimestamp,
    FinalityState,
    LevelState,
    Level0_NodeUTC,
    Level1_NetworkNodes,
    Level2_GlobalNTP,
    Level3_MempoolTime,
    Level4_BlockTime,
    Level56_SystemState,
    Level0State,
    Level1State,
    Level2Result,
    Level3State,
    Level4Block,
    VDFStateTransition,
    GLOBAL_NTP_SERVERS,
    NTP_SERVER_LIST,
    NTP_MIN_SERVERS,
    MAX_CLOCK_DRIFT_MS,
    MIN_PEER_NODES,
    BITCOIN_BLOCK_TIME,
    CONFIRMATIONS_TENTATIVE,
    CONFIRMATIONS_CONFIRMED,
    CONFIRMATIONS_IRREVERSIBLE,
    VDF_TRIGGER_BLOCKS,
    VDF_TRIGGER_SECONDS,
    VDF_MONITOR_INTERVAL,
    VDF_DEACTIVATION_BLOCKS,
    VDF_DEACTIVATION_HYSTERESIS,
    VDF_FINALIZATION_INTERVAL,
    VDF_CHECKPOINT_INTERVAL,
)

__all__ = [
    'Adam',
    'AdamLevel',
    'AdamTimestamp',
    'FinalityState',
    'LevelState',
    'Level0_NodeUTC',
    'Level1_NetworkNodes',
    'Level2_GlobalNTP',
    'Level3_MempoolTime',
    'Level4_BlockTime',
    'Level56_SystemState',
    'Level0State',
    'Level1State',
    'Level2Result',
    'Level3State',
    'Level4Block',
    'VDFStateTransition',
    'GLOBAL_NTP_SERVERS',
    'NTP_SERVER_LIST',
    'NTP_MIN_SERVERS',
    'MAX_CLOCK_DRIFT_MS',
    'MIN_PEER_NODES',
    'BITCOIN_BLOCK_TIME',
    'CONFIRMATIONS_TENTATIVE',
    'CONFIRMATIONS_CONFIRMED',
    'CONFIRMATIONS_IRREVERSIBLE',
    'VDF_TRIGGER_BLOCKS',
    'VDF_TRIGGER_SECONDS',
    'VDF_MONITOR_INTERVAL',
    'VDF_DEACTIVATION_BLOCKS',
    'VDF_DEACTIVATION_HYSTERESIS',
    'VDF_FINALIZATION_INTERVAL',
    'VDF_CHECKPOINT_INTERVAL',
]
