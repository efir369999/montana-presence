"""
Proof of Time - DAG Storage Architecture
Layered storage model for DAG blockchain.

Based on: ProofOfTime_DAG_Addendum.pdf Section 13

Storage Layers:
- Hot Layer (RAM + NVMe SSD): Recent tips, UTXO set, node states, mempool
- Warm Layer (SSD): Last 30 days blocks, transaction index
- Cold Layer (HDD/Archival): Full history, prunable after checkpoints

Time is the ultimate proof.
"""

import sqlite3
import struct
import time
import logging
import threading
from pathlib import Path
from typing import List, Optional, Tuple
from collections import OrderedDict
from contextlib import contextmanager

from config import StorageConfig

logger = logging.getLogger("proof_of_time.dag_storage")


# ============================================================================
# CONSTANTS
# ============================================================================

# Hot layer config
HOT_TIPS_LIMIT = 100  # Recent tips per branch
HOT_CACHE_SIZE_MB = 512

# Warm layer config  
WARM_DAYS = 30
WARM_BLOCKS = WARM_DAYS * 24 * 6  # ~4320 blocks at 10 min/block

# Checkpoint config
CHECKPOINT_INTERVAL = 10000  # blocks (~70 days)


# ============================================================================
# LRU CACHE
# ============================================================================

class LRUCache:
    """Thread-safe LRU cache for hot layer."""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
    
    def get(self, key: bytes) -> Optional[bytes]:
        """Get item, moving to end (most recent)."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None
    
    def put(self, key: bytes, value: bytes):
        """Put item, evicting oldest if full."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
            self._cache[key] = value
    
    def delete(self, key: bytes):
        """Delete item."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        """Clear cache."""
        with self._lock:
            self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: bytes) -> bool:
        return key in self._cache


# ============================================================================
# DAG STORAGE SCHEMA
# ============================================================================

DAG_SCHEMA = """
-- Schema version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- DAG blocks (with parent references)
CREATE TABLE IF NOT EXISTS dag_blocks (
    block_hash BLOB PRIMARY KEY,
    header_data BLOB NOT NULL,
    block_data BLOB NOT NULL,
    vdf_weight INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    producer BLOB NOT NULL,
    is_blue INTEGER DEFAULT 0,
    blue_score INTEGER DEFAULT 0,
    layer TEXT DEFAULT 'warm'  -- 'hot', 'warm', 'cold'
);

CREATE INDEX IF NOT EXISTS idx_dag_blocks_weight ON dag_blocks(vdf_weight DESC);
CREATE INDEX IF NOT EXISTS idx_dag_blocks_timestamp ON dag_blocks(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_dag_blocks_layer ON dag_blocks(layer);
CREATE INDEX IF NOT EXISTS idx_dag_blocks_blue ON dag_blocks(is_blue);

-- Parent-child relationships (DAG edges)
CREATE TABLE IF NOT EXISTS dag_edges (
    child_hash BLOB NOT NULL,
    parent_hash BLOB NOT NULL,
    PRIMARY KEY (child_hash, parent_hash)
);

CREATE INDEX IF NOT EXISTS idx_dag_edges_parent ON dag_edges(parent_hash);
CREATE INDEX IF NOT EXISTS idx_dag_edges_child ON dag_edges(child_hash);

-- DAG tips (blocks with no children)
CREATE TABLE IF NOT EXISTS dag_tips (
    block_hash BLOB PRIMARY KEY,
    vdf_weight INTEGER NOT NULL,
    timestamp INTEGER NOT NULL
);

-- Transactions with tier information
CREATE TABLE IF NOT EXISTS dag_transactions (
    txid BLOB PRIMARY KEY,
    block_hash BLOB NOT NULL,
    tx_index INTEGER NOT NULL,
    tier INTEGER NOT NULL,
    tx_data BLOB NOT NULL,
    fee INTEGER NOT NULL,
    FOREIGN KEY (block_hash) REFERENCES dag_blocks(block_hash)
);

CREATE INDEX IF NOT EXISTS idx_dag_tx_block ON dag_transactions(block_hash);
CREATE INDEX IF NOT EXISTS idx_dag_tx_tier ON dag_transactions(tier);

-- UTXO set with tier
CREATE TABLE IF NOT EXISTS dag_utxos (
    output_id BLOB PRIMARY KEY,  -- txid || output_index
    txid BLOB NOT NULL,
    output_index INTEGER NOT NULL,
    tier INTEGER NOT NULL,
    output_data BLOB NOT NULL,
    amount INTEGER,  -- NULL for T2/T3 (hidden)
    block_hash BLOB NOT NULL,
    spent INTEGER DEFAULT 0,
    spent_by BLOB
);

CREATE INDEX IF NOT EXISTS idx_dag_utxo_unspent ON dag_utxos(spent) WHERE spent = 0;
CREATE INDEX IF NOT EXISTS idx_dag_utxo_tier ON dag_utxos(tier);

-- Key images (T3 double-spend prevention)
CREATE TABLE IF NOT EXISTS dag_key_images (
    key_image BLOB PRIMARY KEY,
    spent_txid BLOB NOT NULL,
    block_hash BLOB NOT NULL,
    timestamp INTEGER NOT NULL
);

-- Node states for consensus
CREATE TABLE IF NOT EXISTS dag_nodes (
    pubkey BLOB PRIMARY KEY,
    weight REAL NOT NULL,
    uptime INTEGER NOT NULL,
    stored_blocks INTEGER NOT NULL,
    signed_blocks INTEGER NOT NULL,
    status INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    node_data BLOB
);

CREATE INDEX IF NOT EXISTS idx_dag_nodes_weight ON dag_nodes(weight DESC);

-- Checkpoints
CREATE TABLE IF NOT EXISTS dag_checkpoints (
    checkpoint_id INTEGER PRIMARY KEY,
    block_hash BLOB NOT NULL,
    utxo_root BLOB NOT NULL,
    node_root BLOB NOT NULL,
    cumulative_vdf_weight INTEGER NOT NULL,
    timestamp INTEGER NOT NULL
);

-- Mempool with fee-priority
CREATE TABLE IF NOT EXISTS dag_mempool (
    txid BLOB PRIMARY KEY,
    tx_data BLOB NOT NULL,
    tier INTEGER NOT NULL,
    fee INTEGER NOT NULL,
    fee_rate REAL NOT NULL,
    added_time INTEGER NOT NULL,
    expires_time INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dag_mempool_fee ON dag_mempool(fee_rate DESC);
CREATE INDEX IF NOT EXISTS idx_dag_mempool_tier ON dag_mempool(tier);
"""


# ============================================================================
# DAG DATABASE
# ============================================================================

class DAGStorage:
    """
    Layered storage for DAG blockchain.
    
    Hot Layer (in-memory):
    - Recent DAG tips
    - UTXO cache
    - Mempool
    
    Warm Layer (SQLite):
    - Last 30 days of blocks
    - Transaction index
    
    Cold Layer (Archive):
    - Full history (optional pruning)
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.db_path = self.config.db_path
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Hot layer caches
        self.tip_cache = LRUCache(HOT_TIPS_LIMIT)
        self.utxo_cache = LRUCache(100000)  # 100k UTXOs
        self.block_cache = LRUCache(1000)  # Recent blocks
        
        # Initialize database
        self._init_db()
        
        self._lock = threading.RLock()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='schema_version'
        """)
        
        if cursor.fetchone() is None:
            cursor.executescript(DAG_SCHEMA)
            cursor.execute("INSERT INTO schema_version VALUES (1)")
            conn.commit()
            logger.info("DAG storage initialized")
        
        conn.close()
    
    @contextmanager
    def _connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # =========================================================================
    # BLOCK OPERATIONS
    # =========================================================================
    
    def store_dag_block(self, block) -> bool:
        """
        Store DAG block with parent relationships.
        """
        from pantheon.hades.dag import DAGBlock
        
        block_hash = block.block_hash
        
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                
                # Store block
                cursor.execute("""
                    INSERT OR REPLACE INTO dag_blocks
                    (block_hash, header_data, block_data, vdf_weight, 
                     timestamp, producer, is_blue, blue_score, layer)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'hot')
                """, (
                    block_hash,
                    block.header.serialize(),
                    block.serialize(),
                    block.vdf_weight,
                    block.header.timestamp,
                    block.producer,
                    1 if block._is_blue else 0,
                    block._blue_score
                ))
                
                # Store parent edges
                for parent in block.parents:
                    cursor.execute("""
                        INSERT OR IGNORE INTO dag_edges (child_hash, parent_hash)
                        VALUES (?, ?)
                    """, (block_hash, parent))
                    
                    # Parent is no longer a tip
                    cursor.execute(
                        "DELETE FROM dag_tips WHERE block_hash = ?",
                        (parent,)
                    )
                
                # New block is a tip
                cursor.execute("""
                    INSERT OR REPLACE INTO dag_tips (block_hash, vdf_weight, timestamp)
                    VALUES (?, ?, ?)
                """, (block_hash, block.vdf_weight, block.header.timestamp))
                
                # Store transactions
                for i, tx in enumerate(block.transactions):
                    txid = tx.hash()
                    tier = getattr(tx, 'tier', 0)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO dag_transactions
                        (txid, block_hash, tx_index, tier, tx_data, fee)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        txid, block_hash, i, tier,
                        tx.serialize(), tx.fee
                    ))
                    
                    # Store outputs as UTXOs
                    for j, output in enumerate(tx.outputs):
                        output_id = txid + struct.pack('<I', j)
                        tier = getattr(output, 'tier', 0)
                        
                        # Amount is visible for T0/T1, NULL for T2/T3
                        if hasattr(output, 'public_amount'):
                            amount = output.public_amount
                        elif hasattr(output, 'visible_amount'):
                            amount = output.visible_amount
                        else:
                            amount = None
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO dag_utxos
                            (output_id, txid, output_index, tier, output_data,
                             amount, block_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            output_id, txid, j, tier,
                            output.serialize() if hasattr(output, 'serialize') else b'',
                            amount, block_hash
                        ))
                    
                    # Record key images for T3 inputs
                    for inp in tx.inputs:
                        if hasattr(inp, 'key_image') and inp.key_image:
                            cursor.execute("""
                                INSERT OR IGNORE INTO dag_key_images
                                (key_image, spent_txid, block_hash, timestamp)
                                VALUES (?, ?, ?, ?)
                            """, (
                                inp.key_image, txid, block_hash,
                                block.header.timestamp
                            ))
            
            # Update hot cache
            self.block_cache.put(block_hash, block.serialize())
            self.tip_cache.put(block_hash, block.serialize())
            
            logger.debug(f"Stored DAG block {block_hash.hex()[:16]}")
            return True
    
    def get_dag_block(self, block_hash: bytes):
        """Get DAG block by hash."""
        from pantheon.hades.dag import DAGBlock
        
        # Check hot cache
        cached = self.block_cache.get(block_hash)
        if cached:
            block, _ = DAGBlock.deserialize(cached)
            return block
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT block_data, is_blue, blue_score FROM dag_blocks WHERE block_hash = ?",
                (block_hash,)
            )
            row = cursor.fetchone()
            
            if row:
                block, _ = DAGBlock.deserialize(row[0])
                block._is_blue = bool(row[1])
                block._blue_score = row[2]
                
                # Update cache
                self.block_cache.put(block_hash, row[0])
                
                return block
        
        return None
    
    def get_dag_tips(self) -> List[bytes]:
        """Get current DAG tips."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT block_hash FROM dag_tips ORDER BY vdf_weight DESC"
            )
            return [row[0] for row in cursor.fetchall()]
    
    def get_block_parents(self, block_hash: bytes) -> List[bytes]:
        """Get parent hashes of a block."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT parent_hash FROM dag_edges WHERE child_hash = ?",
                (block_hash,)
            )
            return [row[0] for row in cursor.fetchall()]
    
    def get_block_children(self, block_hash: bytes) -> List[bytes]:
        """Get child hashes of a block."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT child_hash FROM dag_edges WHERE parent_hash = ?",
                (block_hash,)
            )
            return [row[0] for row in cursor.fetchall()]
    
    # =========================================================================
    # UTXO OPERATIONS
    # =========================================================================
    
    def get_utxo(self, txid: bytes, output_index: int):
        """Get unspent output."""
        from tiered_privacy import TieredOutput
        
        output_id = txid + struct.pack('<I', output_index)
        
        # Check cache
        cached = self.utxo_cache.get(output_id)
        if cached:
            output, _ = TieredOutput.deserialize(cached)
            return output
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT output_data FROM dag_utxos WHERE output_id = ? AND spent = 0",
                (output_id,)
            )
            row = cursor.fetchone()
            
            if row and row[0]:
                output, _ = TieredOutput.deserialize(row[0])
                self.utxo_cache.put(output_id, row[0])
                return output
        
        return None
    
    def mark_utxo_spent(self, txid: bytes, output_index: int, spent_by: bytes):
        """Mark UTXO as spent."""
        output_id = txid + struct.pack('<I', output_index)
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dag_utxos SET spent = 1, spent_by = ?
                WHERE output_id = ?
            """, (spent_by, output_id))
        
        # Remove from cache
        self.utxo_cache.delete(output_id)
    
    def is_key_image_spent(self, key_image: bytes) -> bool:
        """Check if T3 key image is already spent."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM dag_key_images WHERE key_image = ?",
                (key_image,)
            )
            return cursor.fetchone() is not None
    
    def get_random_utxos(
        self,
        count: int,
        tier_filter: Optional[int] = None
    ) -> List[Tuple[bytes, int]]:
        """
        Get random UTXOs for ring decoy selection.
        
        For T3, should only return T2/T3 outputs.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            if tier_filter is not None:
                cursor.execute("""
                    SELECT txid, output_index FROM dag_utxos
                    WHERE spent = 0 AND tier >= ?
                    ORDER BY RANDOM()
                    LIMIT ?
                """, (tier_filter, count))
            else:
                cursor.execute("""
                    SELECT txid, output_index FROM dag_utxos
                    WHERE spent = 0
                    ORDER BY RANDOM()
                    LIMIT ?
                """, (count,))
            
            return [(row[0], row[1]) for row in cursor.fetchall()]
    
    # =========================================================================
    # MEMPOOL OPERATIONS
    # =========================================================================
    
    def add_to_mempool(self, tx, expires_hours: int = 336):
        """Add transaction to mempool with fee-priority indexing."""
        txid = tx.hash()
        tier = getattr(tx, 'tier', 0)
        tx_data = tx.serialize()
        fee_rate = tx.fee / len(tx_data) if tx_data else 0
        now = int(time.time())
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO dag_mempool
                (txid, tx_data, tier, fee, fee_rate, added_time, expires_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                txid, tx_data, tier, tx.fee, fee_rate,
                now, now + expires_hours * 3600
            ))
    
    def get_mempool_by_fee(self, limit: int = 1000) -> List:
        """Get transactions from mempool ordered by fee rate."""
        from pantheon.themis.structures import Transaction
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tx_data FROM dag_mempool
                WHERE expires_time > ?
                ORDER BY fee_rate DESC
                LIMIT ?
            """, (int(time.time()), limit))
            
            txs = []
            for row in cursor.fetchall():
                tx, _ = Transaction.deserialize(row[0])
                txs.append(tx)
            
            return txs
    
    def remove_from_mempool(self, txid: bytes):
        """Remove transaction from mempool."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dag_mempool WHERE txid = ?", (txid,))
    
    # =========================================================================
    # NODE STATE OPERATIONS
    # =========================================================================
    
    def store_node_state(self, pubkey: bytes, weight: float, uptime: int,
                         stored_blocks: int, signed_blocks: int, status: int):
        """Store or update node state."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO dag_nodes
                (pubkey, weight, uptime, stored_blocks, signed_blocks, status, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pubkey, weight, uptime, stored_blocks, signed_blocks,
                  status, int(time.time())))
    
    def get_node_weight(self, pubkey: bytes) -> Optional[float]:
        """Get node's consensus weight."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT weight FROM dag_nodes WHERE pubkey = ?",
                (pubkey,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_top_nodes(self, limit: int = 100) -> List[Tuple[bytes, float]]:
        """Get top nodes by weight."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pubkey, weight FROM dag_nodes ORDER BY weight DESC LIMIT ?",
                (limit,)
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]
    
    # =========================================================================
    # CHECKPOINT OPERATIONS
    # =========================================================================
    
    def create_checkpoint(
        self,
        block_hash: bytes,
        utxo_root: bytes,
        node_root: bytes,
        vdf_weight: int
    ) -> int:
        """Create a new checkpoint."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dag_checkpoints
                (block_hash, utxo_root, node_root, cumulative_vdf_weight, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (block_hash, utxo_root, node_root, vdf_weight, int(time.time())))
            
            checkpoint_id = cursor.lastrowid
            
            logger.info(f"Created checkpoint {checkpoint_id} at block {block_hash.hex()[:16]}")
            return checkpoint_id
    
    def get_latest_checkpoint(self) -> Optional[dict]:
        """Get most recent checkpoint."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM dag_checkpoints
                ORDER BY checkpoint_id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'block_hash': row[1],
                    'utxo_root': row[2],
                    'node_root': row[3],
                    'vdf_weight': row[4],
                    'timestamp': row[5]
                }
        
        return None
    
    # =========================================================================
    # LAYER MANAGEMENT
    # =========================================================================
    
    def migrate_to_warm(self, older_than_hours: int = 24):
        """Move old hot blocks to warm layer."""
        cutoff = int(time.time()) - older_than_hours * 3600
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dag_blocks SET layer = 'warm'
                WHERE layer = 'hot' AND timestamp < ?
            """, (cutoff,))
            
            moved = cursor.rowcount
            if moved > 0:
                logger.info(f"Migrated {moved} blocks to warm layer")
    
    def migrate_to_cold(self, older_than_days: int = WARM_DAYS):
        """Move old warm blocks to cold layer."""
        cutoff = int(time.time()) - older_than_days * 86400
        
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dag_blocks SET layer = 'cold'
                WHERE layer = 'warm' AND timestamp < ?
            """, (cutoff,))
            
            moved = cursor.rowcount
            if moved > 0:
                logger.info(f"Migrated {moved} blocks to cold layer")
    
    def prune_cold_layer(self, keep_checkpoints: int = 10):
        """
        Prune cold layer blocks older than oldest kept checkpoint.
        
        Per spec: Full nodes must retain ≥80% of post-checkpoint history.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Get checkpoint to prune before
            cursor.execute("""
                SELECT block_hash FROM dag_checkpoints
                ORDER BY checkpoint_id DESC
                LIMIT 1 OFFSET ?
            """, (keep_checkpoints,))
            row = cursor.fetchone()
            
            if not row:
                return 0
            
            # Get timestamp of checkpoint block
            cursor.execute(
                "SELECT timestamp FROM dag_blocks WHERE block_hash = ?",
                (row[0],)
            )
            checkpoint_row = cursor.fetchone()
            
            if not checkpoint_row:
                return 0
            
            # Delete blocks before checkpoint (except checkpoint block itself)
            cursor.execute("""
                DELETE FROM dag_blocks
                WHERE layer = 'cold' AND timestamp < ?
            """, (checkpoint_row[0],))
            
            pruned = cursor.rowcount
            if pruned > 0:
                logger.info(f"Pruned {pruned} cold layer blocks")
            
            return pruned
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Block counts by layer
            cursor.execute("""
                SELECT layer, COUNT(*) FROM dag_blocks GROUP BY layer
            """)
            stats['blocks_by_layer'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Total blocks
            cursor.execute("SELECT COUNT(*) FROM dag_blocks")
            stats['total_blocks'] = cursor.fetchone()[0]
            
            # Tips
            cursor.execute("SELECT COUNT(*) FROM dag_tips")
            stats['tip_count'] = cursor.fetchone()[0]
            
            # UTXOs
            cursor.execute("SELECT COUNT(*) FROM dag_utxos WHERE spent = 0")
            stats['unspent_utxos'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM dag_utxos")
            stats['total_utxos'] = cursor.fetchone()[0]
            
            # Key images
            cursor.execute("SELECT COUNT(*) FROM dag_key_images")
            stats['key_images'] = cursor.fetchone()[0]
            
            # Mempool
            cursor.execute("SELECT COUNT(*) FROM dag_mempool")
            stats['mempool_size'] = cursor.fetchone()[0]
            
            # Nodes
            cursor.execute("SELECT COUNT(*) FROM dag_nodes")
            stats['node_count'] = cursor.fetchone()[0]
            
            # Checkpoints
            cursor.execute("SELECT COUNT(*) FROM dag_checkpoints")
            stats['checkpoint_count'] = cursor.fetchone()[0]
            
            # Cache stats
            stats['block_cache_size'] = len(self.block_cache)
            stats['utxo_cache_size'] = len(self.utxo_cache)
            stats['tip_cache_size'] = len(self.tip_cache)
            
            return stats
    
    def close(self):
        """Close storage."""
        self.block_cache.clear()
        self.utxo_cache.clear()
        self.tip_cache.clear()
        logger.info("DAG storage closed")


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run DAG storage self-tests."""
    import tempfile
    import os
    
    logger.info("Running DAG storage self-tests...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "dag_test.db")
        config = StorageConfig(db_path=db_path)
        storage = DAGStorage(config)
        
        # Test LRU cache
        cache = LRUCache(3)
        cache.put(b'a', b'1')
        cache.put(b'b', b'2')
        cache.put(b'c', b'3')
        assert cache.get(b'a') == b'1'
        cache.put(b'd', b'4')  # Should evict 'b' (oldest)
        assert cache.get(b'b') is None
        logger.info("✓ LRU cache")
        
        # Test tip tracking
        tips = storage.get_dag_tips()
        assert isinstance(tips, list)
        logger.info("✓ Tip tracking")
        
        # Test node state
        storage.store_node_state(
            pubkey=b'\x01' * 32,
            weight=0.5,
            uptime=86400,
            stored_blocks=1000,
            signed_blocks=100,
            status=1
        )
        weight = storage.get_node_weight(b'\x01' * 32)
        assert weight == 0.5
        logger.info("✓ Node state storage")
        
        # Test key image
        assert not storage.is_key_image_spent(b'\xaa' * 32)
        logger.info("✓ Key image check")
        
        # Test checkpoint
        cp_id = storage.create_checkpoint(
            block_hash=b'\x02' * 32,
            utxo_root=b'\x03' * 32,
            node_root=b'\x04' * 32,
            vdf_weight=1000000
        )
        assert cp_id > 0
        
        latest = storage.get_latest_checkpoint()
        assert latest is not None
        assert latest['vdf_weight'] == 1000000
        logger.info("✓ Checkpoint creation")
        
        # Test statistics
        stats = storage.get_stats()
        assert 'total_blocks' in stats
        assert 'unspent_utxos' in stats
        logger.info("✓ Statistics")
        
        storage.close()
    
    logger.info("All DAG storage self-tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _self_test()

