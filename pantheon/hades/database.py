"""
Proof of Time - Database Module
Production-grade blockchain storage with SQLite.

Includes:
- Block storage and retrieval
- Transaction indexing
- Key image tracking (double-spend prevention)
- Node state persistence
- Chain state management
- UTXO-like output tracking

Time is the ultimate proof.
"""

import sqlite3
import struct
import logging
import threading
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from pantheon.themis import Block, BlockHeader, Transaction, TxOutput
from pantheon.athena import NodeState, NodeStatus
from config import PROTOCOL, StorageConfig

logger = logging.getLogger("proof_of_time.database")


# ============================================================================
# DATABASE EXCEPTIONS
# ============================================================================

class DatabaseError(Exception):
    """Base database error."""
    pass


class BlockNotFoundError(DatabaseError):
    """Block not found in database."""
    pass


class TransactionNotFoundError(DatabaseError):
    """Transaction not found in database."""
    pass


class DuplicateKeyImageError(DatabaseError):
    """Key image already spent."""
    pass


# ============================================================================
# DATABASE SCHEMA
# ============================================================================

SCHEMA_VERSION = 2

SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Block headers (indexed for fast lookup)
CREATE TABLE IF NOT EXISTS blocks (
    height INTEGER PRIMARY KEY,
    hash BLOB UNIQUE NOT NULL,
    prev_hash BLOB NOT NULL,
    merkle_root BLOB NOT NULL,
    timestamp INTEGER NOT NULL,
    header_data BLOB NOT NULL,
    block_size INTEGER NOT NULL,
    tx_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash);
CREATE INDEX IF NOT EXISTS idx_blocks_timestamp ON blocks(timestamp);

-- Full block data (separate for efficient header-only queries)
CREATE TABLE IF NOT EXISTS block_data (
    height INTEGER PRIMARY KEY,
    data BLOB NOT NULL,
    FOREIGN KEY (height) REFERENCES blocks(height) ON DELETE CASCADE
);

-- Transactions
CREATE TABLE IF NOT EXISTS transactions (
    txid BLOB PRIMARY KEY,
    block_height INTEGER NOT NULL,
    block_index INTEGER NOT NULL,
    tx_type INTEGER NOT NULL,
    fee INTEGER NOT NULL,
    tx_data BLOB NOT NULL,
    FOREIGN KEY (block_height) REFERENCES blocks(height) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_height);
CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(tx_type);

-- Spent key images (for double-spend detection)
CREATE TABLE IF NOT EXISTS spent_key_images (
    key_image BLOB PRIMARY KEY,
    spent_txid BLOB NOT NULL,
    spent_height INTEGER NOT NULL,
    spent_timestamp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_spent_height ON spent_key_images(spent_height);

-- Unspent outputs (simplified UTXO)
CREATE TABLE IF NOT EXISTS outputs (
    output_id BLOB PRIMARY KEY,  -- txid || output_index
    txid BLOB NOT NULL,
    output_index INTEGER NOT NULL,
    stealth_address BLOB NOT NULL,
    commitment BLOB NOT NULL,
    amount_encrypted BLOB,
    block_height INTEGER NOT NULL,
    spent INTEGER DEFAULT 0,
    spent_txid BLOB,
    FOREIGN KEY (block_height) REFERENCES blocks(height) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_outputs_stealth ON outputs(stealth_address);
CREATE INDEX IF NOT EXISTS idx_outputs_unspent ON outputs(spent) WHERE spent = 0;
CREATE INDEX IF NOT EXISTS idx_outputs_block ON outputs(block_height);
CREATE INDEX IF NOT EXISTS idx_outputs_txid ON outputs(txid);

-- Node states
CREATE TABLE IF NOT EXISTS nodes (
    pubkey BLOB PRIMARY KEY,
    uptime_start INTEGER NOT NULL,
    total_uptime INTEGER NOT NULL,
    stored_blocks INTEGER NOT NULL,
    signed_blocks INTEGER NOT NULL,
    last_signed_height INTEGER NOT NULL,
    status INTEGER NOT NULL,
    quarantine_until INTEGER,
    last_seen INTEGER NOT NULL,
    node_data BLOB
);

CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes(last_seen);
CREATE INDEX IF NOT EXISTS idx_nodes_uptime ON nodes(total_uptime);

-- Chain state (singleton)
CREATE TABLE IF NOT EXISTS chain_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    tip_height INTEGER NOT NULL,
    tip_hash BLOB NOT NULL,
    total_supply INTEGER NOT NULL,
    difficulty INTEGER NOT NULL,
    last_update INTEGER NOT NULL
);

-- Mempool (pending transactions)
CREATE TABLE IF NOT EXISTS mempool (
    txid BLOB PRIMARY KEY,
    tx_data BLOB NOT NULL,
    fee INTEGER NOT NULL,
    fee_rate REAL NOT NULL,
    added_timestamp INTEGER NOT NULL,
    expires_timestamp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mempool_fee ON mempool(fee_rate DESC);
"""


# ============================================================================
# DATABASE CONNECTION POOL
# ============================================================================

class ConnectionPool:
    """Thread-safe SQLite connection pool."""
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._local = threading.local()
        self._lock = threading.Lock()
        
    def get_connection(self) -> sqlite3.Connection:
        """Get connection for current thread."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level='DEFERRED'
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-65536")  # 64MB cache
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        
        return self._local.conn
    
    def close_all(self):
        """Close all connections."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# ============================================================================
# BLOCKCHAIN DATABASE
# ============================================================================

class BlockchainDB:
    """
    Production blockchain database.
    
    Features:
    - Efficient block/transaction storage
    - Key image tracking for privacy
    - Node state persistence
    - Chain state management
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.db_path = self.config.db_path
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Connection pool
        self.pool = ConnectionPool(self.db_path)
        
        # Initialize schema
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        # Check schema version
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='schema_version'
        """)
        
        if cursor.fetchone() is None:
            # Fresh database - create schema
            cursor.executescript(SCHEMA)
            cursor.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()
            logger.info(f"Database initialized with schema version {SCHEMA_VERSION}")
        else:
            # Check version and migrate if needed
            cursor.execute("SELECT version FROM schema_version")
            version = cursor.fetchone()[0]
            
            if version < SCHEMA_VERSION:
                self._migrate_schema(version, SCHEMA_VERSION)
    
    def _migrate_schema(self, from_version: int, to_version: int):
        """Migrate database schema between versions."""
        logger.info(f"Migrating database from v{from_version} to v{to_version}")

        conn = self.pool.get_connection()
        cursor = conn.cursor()

        # Migration from v1 to v2: add performance indexes
        if from_version < 2 <= to_version:
            logger.info("Applying migration v1 -> v2: adding performance indexes")

            # New indexes added in v2
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(tx_type)",
                "CREATE INDEX IF NOT EXISTS idx_spent_height ON spent_key_images(spent_height)",
                "CREATE INDEX IF NOT EXISTS idx_outputs_block ON outputs(block_height)",
                "CREATE INDEX IF NOT EXISTS idx_outputs_txid ON outputs(txid)",
                "CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes(last_seen)",
                "CREATE INDEX IF NOT EXISTS idx_nodes_uptime ON nodes(total_uptime)",
            ]

            for idx_sql in indexes:
                try:
                    cursor.execute(idx_sql)
                except sqlite3.OperationalError as e:
                    logger.warning(f"Index creation skipped: {e}")

            cursor.execute("UPDATE schema_version SET version = ?", (2,))
            conn.commit()
            logger.info("Migration v1 -> v2 complete")
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.pool.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Transaction failed: {e}") from e
    
    # =========================================================================
    # BLOCK OPERATIONS
    # =========================================================================
    
    def store_block(self, block: Block):
        """Store block and all its transactions."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            # Store block header
            header_data = block.header.serialize()
            block_data = block.serialize()
            
            cursor.execute("""
                INSERT OR REPLACE INTO blocks 
                (height, hash, prev_hash, merkle_root, timestamp, 
                 header_data, block_size, tx_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block.height,
                block.hash,
                block.header.prev_block_hash,
                block.header.merkle_root,
                block.timestamp,
                header_data,
                len(block_data),
                len(block.transactions)
            ))
            
            # Store full block data
            cursor.execute("""
                INSERT OR REPLACE INTO block_data (height, data)
                VALUES (?, ?)
            """, (block.height, block_data))
            
            # Store transactions
            for idx, tx in enumerate(block.transactions):
                txid = tx.hash()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO transactions
                    (txid, block_height, block_index, tx_type, fee, tx_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    txid,
                    block.height,
                    idx,
                    tx.tx_type,
                    tx.fee,
                    tx.serialize()
                ))
                
                # Store outputs
                for out_idx, output in enumerate(tx.outputs):
                    output_id = txid + struct.pack('<I', out_idx)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO outputs
                        (output_id, txid, output_index, stealth_address,
                         commitment, amount_encrypted, block_height)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        output_id,
                        txid,
                        out_idx,
                        output.stealth_address,
                        output.commitment,
                        output.encrypted_amount,
                        block.height
                    ))
                
                # Mark spent key images
                for inp in tx.inputs:
                    if inp.key_image:
                        cursor.execute("""
                            INSERT INTO spent_key_images
                            (key_image, spent_txid, spent_height, spent_timestamp)
                            VALUES (?, ?, ?, ?)
                        """, (
                            inp.key_image,
                            txid,
                            block.height,
                            block.timestamp
                        ))
            
            # Update chain state
            self._update_chain_state(cursor, block)
            
            logger.debug(f"Stored block {block.height}: {block.hash.hex()[:16]}...")
    
    def get_block(self, height: int) -> Optional[Block]:
        """Get block by height."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT data FROM block_data WHERE height = ?", (height,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        block, _ = Block.deserialize(row[0])
        return block
    
    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        """Get block by hash."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT height FROM blocks WHERE hash = ?", (block_hash,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return self.get_block(row[0])
    
    def get_block_header(self, height: int) -> Optional[BlockHeader]:
        """Get block header only (faster than full block)."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT header_data FROM blocks WHERE height = ?", (height,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        header, _ = BlockHeader.deserialize(row[0])
        return header
    
    def get_block_headers(
        self,
        start_height: int,
        count: int
    ) -> List[BlockHeader]:
        """Get multiple block headers."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT header_data FROM blocks 
            WHERE height >= ? AND height < ?
            ORDER BY height
        """, (start_height, start_height + count))
        
        headers = []
        for row in cursor.fetchall():
            header, _ = BlockHeader.deserialize(row[0])
            headers.append(header)
        
        return headers
    
    def get_latest_block(self) -> Optional[Block]:
        """Get the latest (tip) block."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(height) FROM blocks")
        row = cursor.fetchone()
        
        if row[0] is None:
            return None
        
        return self.get_block(row[0])
    
    def get_chain_height(self) -> int:
        """Get current chain height."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(height) FROM blocks")
        row = cursor.fetchone()
        
        return row[0] if row[0] is not None else -1
    
    # =========================================================================
    # TRANSACTION OPERATIONS
    # =========================================================================
    
    def get_transaction(self, txid: bytes) -> Optional[Transaction]:
        """Get transaction by ID."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT tx_data FROM transactions WHERE txid = ?", (txid,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        tx, _ = Transaction.deserialize(row[0])
        return tx
    
    def get_transaction_block(self, txid: bytes) -> Optional[int]:
        """Get block height containing transaction."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT block_height FROM transactions WHERE txid = ?", (txid,))
        row = cursor.fetchone()
        
        return row[0] if row else None
    
    # =========================================================================
    # KEY IMAGE OPERATIONS
    # =========================================================================
    
    def is_key_image_spent(self, key_image: bytes) -> bool:
        """Check if key image has been spent."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM spent_key_images WHERE key_image = ?",
            (key_image,)
        )
        
        return cursor.fetchone() is not None
    
    def get_key_image_spend_info(
        self,
        key_image: bytes
    ) -> Optional[Tuple[bytes, int, int]]:
        """Get spending info for key image."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT spent_txid, spent_height, spent_timestamp 
            FROM spent_key_images 
            WHERE key_image = ?
        """, (key_image,))
        
        row = cursor.fetchone()
        if row:
            return (row[0], row[1], row[2])
        return None
    
    def check_key_images_batch(
        self,
        key_images: List[bytes]
    ) -> Dict[bytes, bool]:
        """Batch check multiple key images."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(key_images))
        cursor.execute(f"""
            SELECT key_image FROM spent_key_images 
            WHERE key_image IN ({placeholders})
        """, key_images)
        
        spent = {row[0] for row in cursor.fetchall()}
        return {ki: ki in spent for ki in key_images}
    
    # =========================================================================
    # OUTPUT OPERATIONS
    # =========================================================================
    
    def get_outputs_for_address(
        self,
        stealth_address: bytes,
        unspent_only: bool = True
    ) -> List[Tuple[bytes, int, bytes, bytes]]:
        """
        Get outputs for stealth address.
        
        Returns list of (txid, output_index, commitment, encrypted_amount).
        """
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        if unspent_only:
            cursor.execute("""
                SELECT txid, output_index, commitment, amount_encrypted
                FROM outputs
                WHERE stealth_address = ? AND spent = 0
            """, (stealth_address,))
        else:
            cursor.execute("""
                SELECT txid, output_index, commitment, amount_encrypted
                FROM outputs
                WHERE stealth_address = ?
            """, (stealth_address,))
        
        return [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()]
    
    def get_random_outputs(
        self,
        count: int,
        exclude_txids: Optional[List[bytes]] = None
    ) -> List[Tuple[bytes, int, bytes]]:
        """
        Get random outputs for ring construction.
        
        Returns list of (stealth_address, output_index, commitment).
        """
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        if exclude_txids:
            placeholders = ','.join('?' * len(exclude_txids))
            cursor.execute(f"""
                SELECT stealth_address, output_index, commitment
                FROM outputs
                WHERE spent = 0 AND txid NOT IN ({placeholders})
                ORDER BY RANDOM()
                LIMIT ?
            """, exclude_txids + [count])
        else:
            cursor.execute("""
                SELECT stealth_address, output_index, commitment
                FROM outputs
                WHERE spent = 0
                ORDER BY RANDOM()
                LIMIT ?
            """, (count,))
        
        return [(row[0], row[1], row[2]) for row in cursor.fetchall()]
    
    def mark_output_spent(
        self,
        txid: bytes,
        output_index: int,
        spent_txid: bytes
    ):
        """Mark output as spent."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            output_id = txid + struct.pack('<I', output_index)
            
            cursor.execute("""
                UPDATE outputs 
                SET spent = 1, spent_txid = ?
                WHERE output_id = ?
            """, (spent_txid, output_id))
    
    # =========================================================================
    # NODE STATE OPERATIONS
    # =========================================================================
    
    def store_node_state(self, node: NodeState):
        """Store or update node state."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO nodes
                (pubkey, uptime_start, total_uptime, stored_blocks,
                 signed_blocks, last_signed_height, status, 
                 quarantine_until, last_seen, node_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.pubkey,
                node.uptime_start,
                node.total_uptime,
                node.stored_blocks,
                node.signed_blocks,
                node.last_signed_height,
                node.status,
                node.quarantine_until,
                node.last_seen,
                node.serialize()
            ))
    
    def get_node_state(self, pubkey: bytes) -> Optional[NodeState]:
        """Get node state by public key."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT node_data FROM nodes WHERE pubkey = ?", (pubkey,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        node, _ = NodeState.deserialize(row[0])
        return node
    
    def get_all_nodes(
        self,
        status: Optional[NodeStatus] = None
    ) -> List[NodeState]:
        """Get all node states, optionally filtered by status."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        if status is not None:
            cursor.execute(
                "SELECT node_data FROM nodes WHERE status = ?",
                (status,)
            )
        else:
            cursor.execute("SELECT node_data FROM nodes")
        
        nodes = []
        for row in cursor.fetchall():
            node, _ = NodeState.deserialize(row[0])
            nodes.append(node)
        
        return nodes
    
    def get_active_node_count(self) -> int:
        """Get count of active nodes."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM nodes WHERE status = ?",
            (NodeStatus.ACTIVE,)
        )
        
        return cursor.fetchone()[0]
    
    # =========================================================================
    # CHAIN STATE OPERATIONS
    # =========================================================================
    
    def _update_chain_state(self, cursor: sqlite3.Cursor, block: Block):
        """Update chain state after new block."""
        from config import MAX_SUPPLY_SECONDS

        # Calculate new total supply
        reward = 0
        coinbase = block.get_coinbase()
        if coinbase:
            # Get reward from coinbase output
            for output in coinbase.outputs:
                if output.encrypted_amount and len(output.encrypted_amount) >= 8:
                    try:
                        amount = struct.unpack('<Q', output.encrypted_amount[:8])[0]
                        # Validate amount is within reasonable bounds
                        if amount <= MAX_SUPPLY_SECONDS:
                            reward += amount
                    except struct.error:
                        pass  # Invalid data, skip
        
        cursor.execute("""
            INSERT INTO chain_state (id, tip_height, tip_hash, total_supply, 
                                    difficulty, last_update)
            VALUES (1, ?, ?, 
                    COALESCE((SELECT total_supply FROM chain_state WHERE id = 1), 0) + ?,
                    1, ?)
            ON CONFLICT(id) DO UPDATE SET
                tip_height = excluded.tip_height,
                tip_hash = excluded.tip_hash,
                total_supply = chain_state.total_supply + excluded.total_supply,
                last_update = excluded.last_update
        """, (block.height, block.hash, reward, block.timestamp))
    
    def get_chain_state(self) -> Optional[Dict]:
        """Get current chain state."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM chain_state WHERE id = 1")
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return {
            'tip_height': row['tip_height'],
            'tip_hash': row['tip_hash'],
            'total_supply': row['total_supply'],
            'difficulty': row['difficulty'],
            'last_update': row['last_update']
        }
    
    # =========================================================================
    # MEMPOOL OPERATIONS
    # =========================================================================
    
    def add_to_mempool(self, tx: Transaction, expires_hours: int = 336):
        """Add transaction to mempool."""
        import time
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            txid = tx.hash()
            tx_data = tx.serialize()
            fee_rate = tx.fee / len(tx_data) if tx_data else 0
            now = int(time.time())
            expires = now + (expires_hours * 3600)
            
            cursor.execute("""
                INSERT OR REPLACE INTO mempool
                (txid, tx_data, fee, fee_rate, added_timestamp, expires_timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (txid, tx_data, tx.fee, fee_rate, now, expires))
    
    def get_mempool_transactions(
        self,
        limit: int = 1000,
        min_fee_rate: float = 0
    ) -> List[Transaction]:
        """Get transactions from mempool ordered by fee rate."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tx_data FROM mempool
            WHERE fee_rate >= ? AND expires_timestamp > ?
            ORDER BY fee_rate DESC
            LIMIT ?
        """, (min_fee_rate, int(time.time()), limit))
        
        txs = []
        for row in cursor.fetchall():
            tx, _ = Transaction.deserialize(row[0])
            txs.append(tx)
        
        return txs
    
    def remove_from_mempool(self, txid: bytes):
        """Remove transaction from mempool."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM mempool WHERE txid = ?", (txid,))
    
    def prune_mempool(self):
        """Remove expired transactions from mempool."""
        import time
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM mempool WHERE expires_timestamp < ?",
                (int(time.time()),)
            )
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.debug(f"Pruned {deleted} expired mempool transactions")
    
    # =========================================================================
    # MAINTENANCE
    # =========================================================================
    
    def vacuum(self):
        """Optimize database by vacuuming."""
        conn = self.pool.get_connection()
        conn.execute("VACUUM")
        logger.info("Database vacuumed")
    
    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Block count
        cursor.execute("SELECT COUNT(*) FROM blocks")
        stats['block_count'] = cursor.fetchone()[0]
        
        # Transaction count
        cursor.execute("SELECT COUNT(*) FROM transactions")
        stats['tx_count'] = cursor.fetchone()[0]
        
        # Spent key images
        cursor.execute("SELECT COUNT(*) FROM spent_key_images")
        stats['spent_key_images'] = cursor.fetchone()[0]
        
        # Output count
        cursor.execute("SELECT COUNT(*) FROM outputs")
        stats['output_count'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM outputs WHERE spent = 0")
        stats['unspent_outputs'] = cursor.fetchone()[0]
        
        # Node count
        cursor.execute("SELECT COUNT(*) FROM nodes")
        stats['node_count'] = cursor.fetchone()[0]
        
        # Mempool size
        cursor.execute("SELECT COUNT(*) FROM mempool")
        stats['mempool_size'] = cursor.fetchone()[0]
        
        # Database size
        cursor.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
        stats['db_size_bytes'] = cursor.fetchone()[0]
        
        return stats
    
    def close(self):
        """Close all database connections."""
        self.pool.close_all()
        logger.info("Database connections closed")


# ============================================================================
# SELF-TEST
# ============================================================================

def _self_test():
    """Run database self-tests."""
    import tempfile
    import os
    
    logger.info("Running database self-tests...")
    
    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        config = StorageConfig(db_path=db_path)
        db = BlockchainDB(config)
        
        # Test block storage
        from structures import create_genesis_block
        genesis = create_genesis_block()
        db.store_block(genesis)
        
        retrieved = db.get_block(0)
        assert retrieved is not None
        assert retrieved.hash == genesis.hash
        logger.info("✓ Block storage and retrieval")
        
        # Test chain height
        height = db.get_chain_height()
        assert height == 0
        logger.info("✓ Chain height")
        
        # Test key image
        test_ki = b'\x01' * 32
        assert not db.is_key_image_spent(test_ki)
        logger.info("✓ Key image check")
        
        # Test node state
        node = NodeState(pubkey=b'\x02' * 32)
        node.total_uptime = 1000
        node.stored_blocks = 100
        node.status = NodeStatus.ACTIVE
        
        db.store_node_state(node)
        retrieved_node = db.get_node_state(b'\x02' * 32)
        assert retrieved_node is not None
        assert retrieved_node.total_uptime == 1000
        logger.info("✓ Node state storage")
        
        # Test chain state
        state = db.get_chain_state()
        assert state is not None
        assert state['tip_height'] == 0
        logger.info("✓ Chain state")
        
        # Test database stats
        stats = db.get_database_stats()
        assert stats['block_count'] == 1
        logger.info("✓ Database stats")
        
        # Cleanup
        db.close()
    
    logger.info("All database self-tests passed!")


if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    _self_test()
