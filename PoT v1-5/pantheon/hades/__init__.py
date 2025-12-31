"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                             HADES - GOD OF STORAGE                            ║
║                                                                               ║
║       Persistent storage layer with SQLite backend and DAG structure.         ║
║       Manages blockchain data, transactions, and DAG-PHANTOM ordering.        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  COMPONENTS:                                                                  ║
║  ───────────                                                                  ║
║  - BlockchainDB:      Main database interface for blocks and transactions     ║
║  - DAGStorage:        Persistent storage for DAG blocks with LRU cache        ║
║  - DAGBlock:          DAG block structure with multiple parents               ║
║  - DAGConsensusEngine: PHANTOM ordering and finality scoring                  ║
║  - DAGBlockProducer:  Block production with parent selection                  ║
║                                                                               ║
║  FEATURES:                                                                    ║
║  ─────────                                                                    ║
║  - SQLite with WAL mode for concurrent access                                 ║
║  - Connection pooling for performance                                         ║
║  - DAG-PHANTOM ordering algorithm                                             ║
║  - Finality scoring (tentative → confirmed → irreversible)                    ║
║  - Hot/warm/cold block caching                                                ║
║  - Key image tracking for double-spend prevention                             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .database import (
    BlockchainDB,
    ConnectionPool,
    DatabaseError,
    BlockNotFoundError,
    TransactionNotFoundError,
    DuplicateKeyImageError,
    DatabaseIntegrityError,
    SCHEMA,
    SCHEMA_VERSION,
)

from .dag_storage import (
    DAGStorage,
    LRUCache,
    DAG_SCHEMA,
    HOT_CACHE_SIZE_MB,
    HOT_TIPS_LIMIT,
    WARM_BLOCKS,
    WARM_DAYS,
)

from .dag import (
    DAGBlock,
    DAGBlockHeader,
    DAGConsensusEngine,
    DAGBlockProducer,
    PHANTOMOrdering,
    BlockFinalityState,
    estimate_throughput,
    # Constants
    PHANTOM_K,
    MIN_PARENTS,
    MAX_PARENTS,
    PARENT_DIVERSITY_MIN,
    DIVERSITY_PENALTY,
    MIN_WEIGHT_THRESHOLD,
    FINALITY_SCORE_FINALIZED,
    FINALITY_SCORE_IRREVERSIBLE,
    FINALITY_CONFIRMATIONS_TENTATIVE,
    FINALITY_CONFIRMATIONS_CONFIRMED,
)

__all__ = [
    # Database
    'BlockchainDB',
    'ConnectionPool',
    'DatabaseError',
    'BlockNotFoundError',
    'TransactionNotFoundError',
    'DuplicateKeyImageError',
    'DatabaseIntegrityError',
    'SCHEMA',
    'SCHEMA_VERSION',
    # DAG Storage
    'DAGStorage',
    'LRUCache',
    'DAG_SCHEMA',
    'HOT_CACHE_SIZE_MB',
    'HOT_TIPS_LIMIT',
    'WARM_BLOCKS',
    'WARM_DAYS',
    # DAG Core
    'DAGBlock',
    'DAGBlockHeader',
    'DAGConsensusEngine',
    'DAGBlockProducer',
    'PHANTOMOrdering',
    'BlockFinalityState',
    'estimate_throughput',
    # DAG Constants
    'PHANTOM_K',
    'MIN_PARENTS',
    'MAX_PARENTS',
    'PARENT_DIVERSITY_MIN',
    'DIVERSITY_PENALTY',
    'MIN_WEIGHT_THRESHOLD',
    'FINALITY_SCORE_FINALIZED',
    'FINALITY_SCORE_IRREVERSIBLE',
    'FINALITY_CONFIRMATIONS_TENTATIVE',
    'FINALITY_CONFIRMATIONS_CONFIRMED',
]
