"""
Ɉ Montana Storage v3.1

SQLite-based storage per MONTANA_TECHNICAL_SPECIFICATION.md §25.
"""

from __future__ import annotations
import asyncio
import logging
import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager

from montana.core.types import Hash
from montana.core.block import Block, BlockHeader

logger = logging.getLogger(__name__)


# Schema version for migrations
SCHEMA_VERSION = 1


# SQL statements for table creation
CREATE_TABLES_SQL = """
-- Blocks table
CREATE TABLE IF NOT EXISTS blocks (
    hash BLOB PRIMARY KEY,
    height INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    version INTEGER NOT NULL,
    parent_hashes BLOB NOT NULL,
    vdf_output BLOB NOT NULL,
    vdf_iterations INTEGER NOT NULL,
    heartbeat_root BLOB NOT NULL,
    tx_root BLOB NOT NULL,
    state_root BLOB NOT NULL,
    producer_id BLOB NOT NULL,
    data BLOB NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height);
CREATE INDEX IF NOT EXISTS idx_blocks_timestamp ON blocks(timestamp_ms);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    hash BLOB PRIMARY KEY,
    block_hash BLOB,
    privacy_tier INTEGER NOT NULL,
    sender BLOB,
    recipient BLOB,
    amount INTEGER,
    fee INTEGER NOT NULL,
    nonce INTEGER NOT NULL,
    data BLOB NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (block_hash) REFERENCES blocks(hash)
);

CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_hash);
CREATE INDEX IF NOT EXISTS idx_tx_sender ON transactions(sender);

-- Heartbeats table
CREATE TABLE IF NOT EXISTS heartbeats (
    hash BLOB PRIMARY KEY,
    block_hash BLOB,
    node_id BLOB NOT NULL,
    node_type INTEGER NOT NULL,
    source INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    data BLOB NOT NULL,
    FOREIGN KEY (block_hash) REFERENCES blocks(hash)
);

CREATE INDEX IF NOT EXISTS idx_hb_block ON heartbeats(block_hash);
CREATE INDEX IF NOT EXISTS idx_hb_node ON heartbeats(node_id);

-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    address BLOB PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    nonce INTEGER NOT NULL DEFAULT 0,
    privacy_tier INTEGER NOT NULL DEFAULT 0,
    heartbeat_count INTEGER NOT NULL DEFAULT 0,
    score REAL NOT NULL DEFAULT 0.0,
    last_heartbeat_ms INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_accounts_balance ON accounts(balance);
CREATE INDEX IF NOT EXISTS idx_accounts_score ON accounts(score);

-- VDF checkpoints table
CREATE TABLE IF NOT EXISTS vdf_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_hash BLOB NOT NULL,
    iteration INTEGER NOT NULL,
    output BLOB NOT NULL,
    proof BLOB,
    timestamp_ms INTEGER NOT NULL,
    accumulated_iterations INTEGER NOT NULL,
    FOREIGN KEY (block_hash) REFERENCES blocks(hash)
);

CREATE INDEX IF NOT EXISTS idx_vdf_block ON vdf_checkpoints(block_hash);
CREATE INDEX IF NOT EXISTS idx_vdf_iteration ON vdf_checkpoints(iteration);

-- Node state table (for persistence)
CREATE TABLE IF NOT EXISTS node_state (
    key TEXT PRIMARY KEY,
    value BLOB NOT NULL,
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Peers table (for address book)
CREATE TABLE IF NOT EXISTS peers (
    address TEXT PRIMARY KEY,
    port INTEGER NOT NULL,
    services INTEGER NOT NULL DEFAULT 0,
    last_seen INTEGER NOT NULL,
    last_success INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    banned_until INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_peers_last_seen ON peers(last_seen);

-- Schema version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

INSERT OR IGNORE INTO schema_version (version) VALUES ({version});
""".format(version=SCHEMA_VERSION)


class Database:
    """
    SQLite database wrapper with async support.

    Uses a connection pool for concurrent access.
    """

    def __init__(self, path: str = "montana.db"):
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

    async def open(self):
        """Open database connection and initialize schema."""
        async with self._lock:
            self._conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
                isolation_level=None,  # Autocommit
            )
            self._conn.row_factory = sqlite3.Row

            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")

            # Create tables
            self._conn.executescript(CREATE_TABLES_SQL)

            logger.info(f"Database opened: {self.path}")

    async def close(self):
        """Close database connection."""
        async with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("Database closed")

    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        async with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    async def execute(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute SQL statement."""
        async with self._lock:
            return self._conn.execute(sql, params)

    async def executemany(self, sql: str, params_list: List[Tuple]) -> sqlite3.Cursor:
        """Execute SQL statement with multiple parameter sets."""
        async with self._lock:
            return self._conn.executemany(sql, params_list)

    async def fetchone(self, sql: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        """Fetch single row."""
        cursor = await self.execute(sql, params)
        return cursor.fetchone()

    async def fetchall(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Fetch all rows."""
        cursor = await self.execute(sql, params)
        return cursor.fetchall()


class BlockStore:
    """
    Block storage with efficient lookups.

    Provides:
    - Block storage by hash
    - Height index
    - DAG parent traversal
    """

    def __init__(self, db: Database):
        self.db = db
        self._cache: Dict[Hash, Block] = {}
        self._height_index: Dict[int, List[Hash]] = {}
        self._tip_hash: Optional[Hash] = None

    @property
    def tip(self) -> Optional[Hash]:
        return self._tip_hash

    async def get_block(self, block_hash: Hash) -> Optional[Block]:
        """Get block by hash."""
        # Check cache
        if block_hash in self._cache:
            return self._cache[block_hash]

        # Query database
        row = await self.db.fetchone(
            "SELECT data FROM blocks WHERE hash = ?",
            (block_hash.data,)
        )

        if not row:
            return None

        block, _ = Block.deserialize(row["data"])
        self._cache[block_hash] = block
        return block

    async def get_header(self, block_hash: Hash) -> Optional[BlockHeader]:
        """Get block header by hash."""
        block = await self.get_block(block_hash)
        return block.header if block else None

    async def get_blocks_at_height(self, height: int) -> List[Block]:
        """Get all blocks at height (DAG may have multiple)."""
        rows = await self.db.fetchall(
            "SELECT data FROM blocks WHERE height = ?",
            (height,)
        )

        blocks = []
        for row in rows:
            block, _ = Block.deserialize(row["data"])
            blocks.append(block)
        return blocks

    async def add_block(self, block: Block) -> bool:
        """
        Add block to store.

        Returns:
            True if added, False if already exists
        """
        block_hash = block.hash()

        # Check if exists
        if block_hash in self._cache:
            return False

        existing = await self.db.fetchone(
            "SELECT 1 FROM blocks WHERE hash = ?",
            (block_hash.data,)
        )
        if existing:
            return False

        # Serialize parent hashes
        parent_data = b"".join(h.data for h in block.parent_hashes)

        # Insert
        await self.db.execute(
            """
            INSERT INTO blocks
            (hash, height, timestamp_ms, version, parent_hashes,
             vdf_output, vdf_iterations, heartbeat_root, tx_root,
             state_root, producer_id, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block_hash.data,
                block.height,
                block.timestamp_ms,
                block.header.version,
                parent_data,
                block.header.vdf_output.data,
                block.header.vdf_iterations,
                block.header.heartbeat_root.data,
                block.header.tx_root.data,
                block.header.state_root.data,
                block.header.producer_id.data,
                block.serialize(),
            )
        )

        # Update cache
        self._cache[block_hash] = block

        # Update height index
        if block.height not in self._height_index:
            self._height_index[block.height] = []
        self._height_index[block.height].append(block_hash)

        # Update tip if this is highest
        if self._tip_hash is None or block.height > (await self.get_height()):
            self._tip_hash = block_hash

        logger.debug(f"Added block {block_hash.hex()[:16]} at height {block.height}")
        return True

    async def get_height(self) -> int:
        """Get current timechain height."""
        row = await self.db.fetchone("SELECT MAX(height) as height FROM blocks")
        return row["height"] if row and row["height"] is not None else -1

    async def get_tip(self) -> Optional[Block]:
        """Get tip block."""
        if self._tip_hash:
            return await self.get_block(self._tip_hash)

        # Find highest block
        row = await self.db.fetchone(
            "SELECT data FROM blocks ORDER BY height DESC, timestamp_ms DESC LIMIT 1"
        )
        if not row:
            return None

        block, _ = Block.deserialize(row["data"])
        self._tip_hash = block.hash()
        return block


class StateStore:
    """
    Key-value state storage.

    For persistent node state like:
    - Best block hash
    - VDF accumulator state
    - Configuration
    """

    def __init__(self, db: Database):
        self.db = db

    async def get(self, key: str) -> Optional[bytes]:
        """Get value by key."""
        row = await self.db.fetchone(
            "SELECT value FROM node_state WHERE key = ?",
            (key,)
        )
        return row["value"] if row else None

    async def set(self, key: str, value: bytes):
        """Set key-value pair."""
        await self.db.execute(
            """
            INSERT OR REPLACE INTO node_state (key, value, updated_at)
            VALUES (?, ?, strftime('%s', 'now'))
            """,
            (key, value)
        )

    async def delete(self, key: str):
        """Delete key."""
        await self.db.execute(
            "DELETE FROM node_state WHERE key = ?",
            (key,)
        )

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value."""
        data = await self.get(key)
        if data:
            return json.loads(data.decode('utf-8'))
        return None

    async def set_json(self, key: str, value: Any):
        """Set JSON value."""
        data = json.dumps(value).encode('utf-8')
        await self.set(key, data)

    async def get_best_block_hash(self) -> Optional[Hash]:
        """Get best block hash."""
        data = await self.get("best_block_hash")
        return Hash(data) if data else None

    async def set_best_block_hash(self, block_hash: Hash):
        """Set best block hash."""
        await self.set("best_block_hash", block_hash.data)

    async def get_vdf_state(self) -> Optional[Dict]:
        """Get VDF accumulator state."""
        return await self.get_json("vdf_state")

    async def set_vdf_state(self, state: Dict):
        """Set VDF accumulator state."""
        await self.set_json("vdf_state", state)
