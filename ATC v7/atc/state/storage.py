"""
ATC Protocol v7 State Storage
Part XV of Technical Specification

SQLite persistence for blockchain state.
"""

from __future__ import annotations
import logging
import sqlite3
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from atc.core.types import Hash, PublicKey
from atc.core.state import AccountState, GlobalState

if TYPE_CHECKING:
    from atc.core.block import Block, BlockHeader

logger = logging.getLogger(__name__)


# Schema version for migrations
SCHEMA_VERSION = 1


CREATE_TABLES_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Global state
CREATE TABLE IF NOT EXISTS global_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    chain_height INTEGER NOT NULL DEFAULT 0,
    chain_tip_hash BLOB,
    btc_height INTEGER NOT NULL DEFAULT 0,
    btc_hash BLOB,
    btc_epoch INTEGER NOT NULL DEFAULT 0,
    total_supply INTEGER NOT NULL DEFAULT 0,
    total_heartbeats INTEGER NOT NULL DEFAULT 0,
    active_accounts INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL
);

-- Accounts
CREATE TABLE IF NOT EXISTS accounts (
    pubkey BLOB PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    nonce INTEGER NOT NULL DEFAULT 0,
    epoch_heartbeats INTEGER NOT NULL DEFAULT 0,
    epoch_tx_count INTEGER NOT NULL DEFAULT 0,
    total_heartbeats INTEGER NOT NULL DEFAULT 0,
    last_heartbeat_height INTEGER NOT NULL DEFAULT 0,
    second_tx_count INTEGER NOT NULL DEFAULT 0,
    last_tx_second INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Blocks
CREATE TABLE IF NOT EXISTS blocks (
    height INTEGER PRIMARY KEY,
    hash BLOB NOT NULL UNIQUE,
    parent_hash BLOB NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    heartbeats_count INTEGER NOT NULL,
    transactions_count INTEGER NOT NULL,
    signers_count INTEGER NOT NULL,
    total_weight REAL NOT NULL,
    btc_height INTEGER NOT NULL,
    state_root BLOB,
    raw_header BLOB NOT NULL,
    created_at INTEGER NOT NULL
);

-- Block contents (heartbeats, transactions stored separately for efficiency)
CREATE TABLE IF NOT EXISTS block_heartbeats (
    block_height INTEGER NOT NULL,
    heartbeat_idx INTEGER NOT NULL,
    heartbeat_id BLOB NOT NULL,
    pubkey BLOB NOT NULL,
    raw_data BLOB NOT NULL,
    PRIMARY KEY (block_height, heartbeat_idx),
    FOREIGN KEY (block_height) REFERENCES blocks(height)
);

CREATE TABLE IF NOT EXISTS block_transactions (
    block_height INTEGER NOT NULL,
    tx_idx INTEGER NOT NULL,
    tx_id BLOB NOT NULL,
    sender BLOB NOT NULL,
    receiver BLOB NOT NULL,
    amount INTEGER NOT NULL,
    raw_data BLOB NOT NULL,
    PRIMARY KEY (block_height, tx_idx),
    FOREIGN KEY (block_height) REFERENCES blocks(height)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash);
CREATE INDEX IF NOT EXISTS idx_accounts_balance ON accounts(balance DESC);
CREATE INDEX IF NOT EXISTS idx_accounts_heartbeats ON accounts(epoch_heartbeats DESC);
CREATE INDEX IF NOT EXISTS idx_block_heartbeats_pubkey ON block_heartbeats(pubkey);
CREATE INDEX IF NOT EXISTS idx_block_transactions_sender ON block_transactions(sender);
CREATE INDEX IF NOT EXISTS idx_block_transactions_receiver ON block_transactions(receiver);
"""


@dataclass
class StateStorage:
    """
    SQLite-based state storage.

    Provides persistent storage for:
    - Global state
    - Account states
    - Block headers and contents
    """
    db_path: str
    _conn: Optional[sqlite3.Connection] = None

    def __post_init__(self):
        self._conn = None

    def connect(self) -> None:
        """Open database connection and initialize schema."""
        if self._conn is not None:
            return

        # Create parent directories
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # Autocommit by default
            check_same_thread=False
        )

        # Enable WAL mode for better concurrency
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        # Initialize schema
        self._init_schema()

        logger.info(f"Connected to state storage: {self.db_path}")

    def _init_schema(self) -> None:
        """Initialize database schema."""
        self._conn.executescript(CREATE_TABLES_SQL)

        # Check schema version
        cursor = self._conn.execute(
            "SELECT value FROM schema_info WHERE key = 'version'"
        )
        row = cursor.fetchone()

        if row is None:
            # New database
            self._conn.execute(
                "INSERT INTO schema_info (key, value) VALUES ('version', ?)",
                (str(SCHEMA_VERSION),)
            )

            # Initialize global state
            import time
            self._conn.execute(
                """INSERT INTO global_state
                   (id, chain_height, btc_height, btc_epoch, total_supply,
                    total_heartbeats, active_accounts, updated_at)
                   VALUES (1, 0, 0, 0, 0, 0, 0, ?)""",
                (int(time.time() * 1000),)
            )

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Closed state storage")

    def __enter__(self) -> "StateStorage":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _ensure_connected(self) -> None:
        if self._conn is None:
            self.connect()

    # =========================================================================
    # Global State Operations
    # =========================================================================

    def save_global_state(self, state: GlobalState) -> None:
        """Save global state to database."""
        self._ensure_connected()
        import time

        self._conn.execute(
            """UPDATE global_state SET
               chain_height = ?,
               chain_tip_hash = ?,
               btc_height = ?,
               btc_hash = ?,
               btc_epoch = ?,
               total_supply = ?,
               total_heartbeats = ?,
               active_accounts = ?,
               updated_at = ?
               WHERE id = 1""",
            (
                state.chain_height,
                state.chain_tip_hash.data,
                state.btc_height,
                state.btc_hash.data,
                state.btc_epoch,
                state.total_supply,
                state.total_heartbeats,
                state.active_accounts,
                int(time.time() * 1000),
            )
        )

    def load_global_state(self) -> GlobalState:
        """Load global state from database."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT chain_height, chain_tip_hash, btc_height, btc_hash,
                      btc_epoch, total_supply, total_heartbeats, active_accounts
               FROM global_state WHERE id = 1"""
        )
        row = cursor.fetchone()

        if row is None:
            return GlobalState()

        state = GlobalState(
            chain_height=row[0],
            chain_tip_hash=Hash(row[1]) if row[1] else Hash.zero(),
            btc_height=row[2],
            btc_hash=Hash(row[3]) if row[3] else Hash.zero(),
            btc_epoch=row[4],
            total_supply=row[5],
            total_heartbeats=row[6],
            active_accounts=row[7],
        )

        # Load all accounts
        for account in self.load_all_accounts():
            state.set_account(account.pubkey, account)

        return state

    # =========================================================================
    # Account Operations
    # =========================================================================

    def save_account(self, account: AccountState) -> None:
        """Save account to database."""
        self._ensure_connected()
        import time

        now = int(time.time() * 1000)

        self._conn.execute(
            """INSERT INTO accounts
               (pubkey, balance, nonce, epoch_heartbeats, epoch_tx_count,
                total_heartbeats, last_heartbeat_height, second_tx_count,
                last_tx_second, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(pubkey) DO UPDATE SET
                balance = excluded.balance,
                nonce = excluded.nonce,
                epoch_heartbeats = excluded.epoch_heartbeats,
                epoch_tx_count = excluded.epoch_tx_count,
                total_heartbeats = excluded.total_heartbeats,
                last_heartbeat_height = excluded.last_heartbeat_height,
                second_tx_count = excluded.second_tx_count,
                last_tx_second = excluded.last_tx_second,
                updated_at = excluded.updated_at""",
            (
                account.pubkey.data,
                account.balance,
                account.nonce,
                account.epoch_heartbeats,
                account.epoch_tx_count,
                account.total_heartbeats,
                account.last_heartbeat_height,
                account.second_tx_count,
                account.last_tx_second,
                now,
                now,
            )
        )

    def load_account(self, pubkey: PublicKey) -> Optional[AccountState]:
        """Load account from database."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT balance, nonce, epoch_heartbeats, epoch_tx_count,
                      total_heartbeats, last_heartbeat_height,
                      second_tx_count, last_tx_second
               FROM accounts WHERE pubkey = ?""",
            (pubkey.data,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return AccountState(
            pubkey=pubkey,
            balance=row[0],
            nonce=row[1],
            epoch_heartbeats=row[2],
            epoch_tx_count=row[3],
            total_heartbeats=row[4],
            last_heartbeat_height=row[5],
            second_tx_count=row[6],
            last_tx_second=row[7],
        )

    def load_all_accounts(self) -> List[AccountState]:
        """Load all accounts from database."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT pubkey, balance, nonce, epoch_heartbeats, epoch_tx_count,
                      total_heartbeats, last_heartbeat_height,
                      second_tx_count, last_tx_second
               FROM accounts"""
        )

        accounts = []
        for row in cursor:
            account = AccountState(
                pubkey=PublicKey(row[0]),
                balance=row[1],
                nonce=row[2],
                epoch_heartbeats=row[3],
                epoch_tx_count=row[4],
                total_heartbeats=row[5],
                last_heartbeat_height=row[6],
                second_tx_count=row[7],
                last_tx_second=row[8],
            )
            accounts.append(account)

        return accounts

    def delete_account(self, pubkey: PublicKey) -> bool:
        """Delete account from database."""
        self._ensure_connected()

        cursor = self._conn.execute(
            "DELETE FROM accounts WHERE pubkey = ?",
            (pubkey.data,)
        )
        return cursor.rowcount > 0

    def get_account_count(self) -> int:
        """Get total number of accounts."""
        self._ensure_connected()

        cursor = self._conn.execute("SELECT COUNT(*) FROM accounts")
        return cursor.fetchone()[0]

    def get_rich_list(self, limit: int = 100) -> List[AccountState]:
        """Get top accounts by balance."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT pubkey, balance, nonce, epoch_heartbeats, total_heartbeats
               FROM accounts
               WHERE balance > 0
               ORDER BY balance DESC
               LIMIT ?""",
            (limit,)
        )

        accounts = []
        for row in cursor:
            account = AccountState(
                pubkey=PublicKey(row[0]),
                balance=row[1],
                nonce=row[2],
                epoch_heartbeats=row[3],
                total_heartbeats=row[4],
            )
            accounts.append(account)

        return accounts

    # =========================================================================
    # Block Operations
    # =========================================================================

    def save_block(self, block: "Block") -> None:
        """Save block header and contents to database."""
        self._ensure_connected()
        import time

        now = int(time.time() * 1000)
        block_hash = block.block_hash()

        # Save block header
        self._conn.execute(
            """INSERT INTO blocks
               (height, hash, parent_hash, timestamp_ms, heartbeats_count,
                transactions_count, signers_count, total_weight, btc_height,
                state_root, raw_header, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                block.header.height,
                block_hash.data,
                block.header.parent_hash.data,
                block.header.timestamp_ms,
                len(block.heartbeats),
                len(block.transactions),
                len(block.signers),
                block.total_score(),
                block.header.btc_anchor.height,
                block.header.state_root.data,
                block.header.serialize(),
                now,
            )
        )

        # Save heartbeats
        for idx, hb in enumerate(block.heartbeats):
            self._conn.execute(
                """INSERT INTO block_heartbeats
                   (block_height, heartbeat_idx, heartbeat_id, pubkey, raw_data)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    block.header.height,
                    idx,
                    hb.heartbeat_id().data,
                    hb.pubkey.data,
                    hb.serialize(),
                )
            )

        # Save transactions
        for idx, tx in enumerate(block.transactions):
            self._conn.execute(
                """INSERT INTO block_transactions
                   (block_height, tx_idx, tx_id, sender, receiver, amount, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    block.header.height,
                    idx,
                    tx.transaction_id().data,
                    tx.sender.data,
                    tx.receiver.data,
                    tx.amount,
                    tx.serialize(),
                )
            )

    def load_block_header(self, height: int) -> Optional[Dict[str, Any]]:
        """Load block header metadata by height."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT hash, parent_hash, timestamp_ms, heartbeats_count,
                      transactions_count, signers_count, total_weight,
                      btc_height, state_root
               FROM blocks WHERE height = ?""",
            (height,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "height": height,
            "hash": Hash(row[0]).hex(),
            "parent_hash": Hash(row[1]).hex(),
            "timestamp_ms": row[2],
            "heartbeats_count": row[3],
            "transactions_count": row[4],
            "signers_count": row[5],
            "total_weight": row[6],
            "btc_height": row[7],
            "state_root": Hash(row[8]).hex() if row[8] else None,
        }

    def load_block_by_hash(self, block_hash: Hash) -> Optional[Dict[str, Any]]:
        """Load block header metadata by hash."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT height FROM blocks WHERE hash = ?""",
            (block_hash.data,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return self.load_block_header(row[0])

    def get_chain_height(self) -> int:
        """Get current chain height."""
        self._ensure_connected()

        cursor = self._conn.execute("SELECT MAX(height) FROM blocks")
        row = cursor.fetchone()

        return row[0] if row[0] is not None else 0

    def get_block_hash_at(self, height: int) -> Optional[Hash]:
        """Get block hash at height."""
        self._ensure_connected()

        cursor = self._conn.execute(
            "SELECT hash FROM blocks WHERE height = ?",
            (height,)
        )
        row = cursor.fetchone()

        return Hash(row[0]) if row else None

    def get_blocks_range(
        self,
        start_height: int,
        end_height: int
    ) -> List[Dict[str, Any]]:
        """Get block headers in height range."""
        self._ensure_connected()

        cursor = self._conn.execute(
            """SELECT height, hash, parent_hash, timestamp_ms,
                      heartbeats_count, transactions_count, total_weight
               FROM blocks
               WHERE height >= ? AND height <= ?
               ORDER BY height""",
            (start_height, end_height)
        )

        blocks = []
        for row in cursor:
            blocks.append({
                "height": row[0],
                "hash": Hash(row[1]).hex(),
                "parent_hash": Hash(row[2]).hex(),
                "timestamp_ms": row[3],
                "heartbeats_count": row[4],
                "transactions_count": row[5],
                "total_weight": row[6],
            })

        return blocks

    # =========================================================================
    # Transaction Operations
    # =========================================================================

    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        self._ensure_connected()
        self._conn.execute("BEGIN TRANSACTION")

    def commit(self) -> None:
        """Commit current transaction."""
        self._ensure_connected()
        self._conn.execute("COMMIT")

    def rollback(self) -> None:
        """Rollback current transaction."""
        self._ensure_connected()
        self._conn.execute("ROLLBACK")

    # =========================================================================
    # Utility Operations
    # =========================================================================

    def vacuum(self) -> None:
        """Compact database."""
        self._ensure_connected()
        self._conn.execute("VACUUM")
        logger.info("Database vacuumed")

    def get_database_size(self) -> int:
        """Get database file size in bytes."""
        path = Path(self.db_path)
        if path.exists():
            return path.stat().st_size
        return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        self._ensure_connected()

        stats = {
            "file_size_bytes": self.get_database_size(),
            "chain_height": self.get_chain_height(),
            "account_count": self.get_account_count(),
        }

        # Block count
        cursor = self._conn.execute("SELECT COUNT(*) FROM blocks")
        stats["block_count"] = cursor.fetchone()[0]

        # Total transactions
        cursor = self._conn.execute("SELECT COUNT(*) FROM block_transactions")
        stats["transaction_count"] = cursor.fetchone()[0]

        # Total heartbeats
        cursor = self._conn.execute("SELECT COUNT(*) FROM block_heartbeats")
        stats["heartbeat_count"] = cursor.fetchone()[0]

        return stats


def get_storage_info() -> dict:
    """Get information about state storage."""
    return {
        "backend": "SQLite",
        "schema_version": SCHEMA_VERSION,
        "tables": [
            "global_state",
            "accounts",
            "blocks",
            "block_heartbeats",
            "block_transactions",
        ],
        "features": [
            "WAL mode",
            "indexed queries",
            "atomic transactions",
        ],
    }
