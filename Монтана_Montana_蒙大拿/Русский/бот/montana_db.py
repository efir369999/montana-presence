#!/usr/bin/env python3
"""
Montana Protocol Database — Standalone SQLite Database
Fully independent, no Telegram dependencies.

Primary identifier: Montana address (mt + 40 hex chars)

Tables:
- wallets: Montana addresses and balances
- transactions: Transfer history
- presence: Time Bank presence records
"""

import sqlite3
import json
import time
import logging
import threading
import secrets
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("montana_db")

# Database path
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "montana.db"


class MontanaDB:
    """
    Montana Protocol Database.

    Primary identifier: Montana address (mt...)
    All operations use Montana addresses, not external IDs.
    """

    def __init__(self, db_path: Path = DB_PATH):
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        """Thread-safe connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    @contextmanager
    def transaction(self):
        """Context manager for transactions"""
        try:
            yield self.conn
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def _init_db(self):
        """Initialize database schema"""
        with self.transaction():
            self.conn.executescript("""
                -- Wallets: Montana addresses and keys
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    public_key TEXT,
                    balance REAL DEFAULT 0.0,
                    alias TEXT UNIQUE,
                    phone TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );

                -- Transactions: Transfer history
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_id TEXT UNIQUE NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    signature TEXT,
                    status TEXT DEFAULT 'confirmed'
                );

                -- Presence: Time Bank activity records
                CREATE TABLE IF NOT EXISTS presence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    seconds INTEGER DEFAULT 1,
                    coins_earned REAL DEFAULT 0.0,
                    signature TEXT
                );

                -- Sessions: Active presence sessions
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_activity REAL NOT NULL,
                    ended_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    presence_seconds INTEGER DEFAULT 0,
                    coins_earned REAL DEFAULT 0.0
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_transactions_from ON transactions(from_address);
                CREATE INDEX IF NOT EXISTS idx_transactions_to ON transactions(to_address);
                CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_presence_address ON presence(address);
                CREATE INDEX IF NOT EXISTS idx_sessions_address ON sessions(address);
                CREATE INDEX IF NOT EXISTS idx_wallets_alias ON wallets(alias);
                CREATE INDEX IF NOT EXISTS idx_wallets_phone ON wallets(phone);
            """)

    # ═══════════════════════════════════════════════════════════════════════════════
    #                              WALLET OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════════

    def create_wallet(self, address: str, public_key: str = None) -> Dict[str, Any]:
        """Create or get existing wallet."""
        if not address.startswith('mt') or len(address) != 42:
            raise ValueError(f"Invalid address format: {address}")

        now = datetime.utcnow().isoformat()

        with self.transaction():
            cursor = self.conn.execute(
                "SELECT * FROM wallets WHERE address = ?",
                (address,)
            )
            row = cursor.fetchone()

            if row:
                return dict(row)

            self.conn.execute("""
                INSERT INTO wallets (address, public_key, balance, created_at)
                VALUES (?, ?, 0.0, ?)
            """, (address, public_key, now))

            logger.info(f"🔐 Wallet created: {address[:16]}...")

            return {
                "address": address,
                "public_key": public_key,
                "balance": 0.0,
                "alias": None,
                "phone": None,
                "created_at": now,
                "updated_at": None
            }

    def get_wallet(self, address: str) -> Optional[Dict[str, Any]]:
        """Get wallet by address"""
        cursor = self.conn.execute(
            "SELECT * FROM wallets WHERE address = ?",
            (address,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_balance(self, address: str) -> float:
        """Get balance for address"""
        cursor = self.conn.execute(
            "SELECT balance FROM wallets WHERE address = ?",
            (address,)
        )
        row = cursor.fetchone()
        return row["balance"] if row else 0.0

    def update_balance(self, address: str, delta: float) -> float:
        """Update balance by delta. Returns new balance."""
        now = datetime.utcnow().isoformat()

        with self.transaction():
            self.create_wallet(address)

            self.conn.execute("""
                UPDATE wallets
                SET balance = balance + ?, updated_at = ?
                WHERE address = ?
            """, (delta, now, address))

            return self.get_balance(address)

    def set_balance(self, address: str, balance: float) -> float:
        """Set absolute balance"""
        now = datetime.utcnow().isoformat()

        with self.transaction():
            self.create_wallet(address)

            self.conn.execute("""
                UPDATE wallets
                SET balance = ?, updated_at = ?
                WHERE address = ?
            """, (balance, now, address))

            return balance

    def set_alias(self, address: str, alias: str) -> Tuple[bool, str]:
        """Set human-readable alias for address."""
        alias = alias.lower().strip()
        if not alias.isalnum() or len(alias) < 3 or len(alias) > 32:
            return False, "Alias must be 3-32 alphanumeric characters"

        now = datetime.utcnow().isoformat()

        try:
            with self.transaction():
                self.create_wallet(address)

                self.conn.execute("""
                    UPDATE wallets
                    SET alias = ?, updated_at = ?
                    WHERE address = ?
                """, (alias, now, address))

                logger.info(f"🏷️ Alias set: {address[:16]}... → {alias}.montana")
                return True, alias

        except sqlite3.IntegrityError:
            return False, "Alias already taken"

    def set_phone(self, address: str, phone: str) -> Tuple[bool, str]:
        """Link phone number to address"""
        now = datetime.utcnow().isoformat()

        try:
            with self.transaction():
                self.create_wallet(address)

                self.conn.execute("""
                    UPDATE wallets
                    SET phone = ?, updated_at = ?
                    WHERE address = ?
                """, (phone, now, address))

                logger.info(f"📱 Phone linked: {address[:16]}... → {phone}")
                return True, phone

        except sqlite3.IntegrityError:
            return False, "Phone already linked to another address"

    def resolve_address(self, identifier: str) -> Optional[str]:
        """Resolve any identifier to Montana address."""
        if identifier.startswith('mt') and len(identifier) == 42:
            return identifier

        alias = identifier.lower().replace('.montana', '').strip()
        cursor = self.conn.execute(
            "SELECT address FROM wallets WHERE alias = ?",
            (alias,)
        )
        row = cursor.fetchone()
        if row:
            return row["address"]

        if identifier.startswith('+'):
            cursor = self.conn.execute(
                "SELECT address FROM wallets WHERE phone = ?",
                (identifier,)
            )
            row = cursor.fetchone()
            if row:
                return row["address"]

        return None

    # ═══════════════════════════════════════════════════════════════════════════════
    #                              TRANSACTIONS
    # ═══════════════════════════════════════════════════════════════════════════════

    def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        signature: str = None
    ) -> Dict[str, Any]:
        """Transfer Ɉ between addresses."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        sender_balance = self.get_balance(from_address)
        if sender_balance < amount:
            raise ValueError(f"Insufficient funds: {sender_balance} < {amount}")

        now = datetime.utcnow().isoformat()
        tx_id = hashlib.sha256(
            f"{from_address}{to_address}{amount}{now}".encode()
        ).hexdigest()[:16]

        with self.transaction():
            self.create_wallet(from_address)
            self.create_wallet(to_address)

            self.conn.execute("""
                UPDATE wallets SET balance = balance - ?, updated_at = ?
                WHERE address = ?
            """, (amount, now, from_address))

            self.conn.execute("""
                UPDATE wallets SET balance = balance + ?, updated_at = ?
                WHERE address = ?
            """, (amount, now, to_address))

            self.conn.execute("""
                INSERT INTO transactions
                (tx_id, from_address, to_address, amount, timestamp, signature, status)
                VALUES (?, ?, ?, ?, ?, ?, 'confirmed')
            """, (tx_id, from_address, to_address, amount, now, signature))

            logger.info(f"💸 Transfer: {from_address[:10]}→{to_address[:10]}: {amount} Ɉ")

            return {
                "tx_id": tx_id,
                "from": from_address,
                "to": to_address,
                "amount": amount,
                "timestamp": now,
                "status": "confirmed"
            }

    def get_transactions(self, address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get transactions for address"""
        cursor = self.conn.execute("""
            SELECT * FROM transactions
            WHERE from_address = ? OR to_address = ?
            ORDER BY id DESC LIMIT ?
        """, (address, address, limit))

        return [dict(row) for row in cursor.fetchall()]

    def record_transaction(
        self,
        address: str,
        event: str,
        amount: float,
        source: str = "system"
    ) -> Dict[str, Any]:
        """Record a system transaction (emission, reward, etc.)"""
        now = datetime.utcnow().isoformat()
        tx_id = hashlib.sha256(
            f"{address}{event}{amount}{now}".encode()
        ).hexdigest()[:16]

        with self.transaction():
            self.create_wallet(address)

            new_balance = self.update_balance(address, amount)

            self.conn.execute("""
                INSERT INTO transactions
                (tx_id, from_address, to_address, amount, timestamp, status)
                VALUES (?, 'SYSTEM', ?, ?, ?, 'confirmed')
            """, (tx_id, address, amount, now))

            logger.info(f"💰 {event}: {address[:10]}... +{amount} Ɉ (balance: {new_balance})")

            return {
                "tx_id": tx_id,
                "event": event,
                "address": address,
                "amount": amount,
                "balance": new_balance,
                "timestamp": now
            }

    # ═══════════════════════════════════════════════════════════════════════════════
    #                              PRESENCE / TIME BANK
    # ═══════════════════════════════════════════════════════════════════════════════

    def start_session(self, address: str) -> int:
        """Start presence session for address"""
        now = datetime.utcnow().isoformat()

        with self.transaction():
            self.create_wallet(address)

            self.conn.execute("""
                UPDATE sessions
                SET is_active = 0, ended_at = ?
                WHERE address = ? AND is_active = 1
            """, (now, address))

            cursor = self.conn.execute("""
                INSERT INTO sessions (address, started_at, last_activity, is_active)
                VALUES (?, ?, ?, 1)
            """, (address, now, time.time()))

            session_id = cursor.lastrowid
            logger.info(f"📍 Session #{session_id} started: {address[:16]}...")
            return session_id

    def get_active_session(self, address: str) -> Optional[Dict[str, Any]]:
        """Get active session for address"""
        cursor = self.conn.execute("""
            SELECT * FROM sessions
            WHERE address = ? AND is_active = 1
            ORDER BY id DESC LIMIT 1
        """, (address,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_presence(self, address: str, seconds: int = 1) -> Dict[str, Any]:
        """Record presence activity"""
        now = datetime.utcnow().isoformat()

        with self.transaction():
            session = self.get_active_session(address)

            if not session:
                self.start_session(address)
                session = self.get_active_session(address)

            self.conn.execute("""
                UPDATE sessions
                SET last_activity = ?, presence_seconds = presence_seconds + ?
                WHERE id = ?
            """, (time.time(), seconds, session["id"]))

            self.conn.execute("""
                INSERT INTO presence (address, timestamp, seconds)
                VALUES (?, ?, ?)
            """, (address, now, seconds))

            return {
                "address": address,
                "session_id": session["id"],
                "presence_seconds": session["presence_seconds"] + seconds
            }

    def end_session(self, address: str) -> Optional[Dict[str, Any]]:
        """End active session"""
        session = self.get_active_session(address)
        if not session:
            return None

        now = datetime.utcnow().isoformat()

        with self.transaction():
            self.conn.execute("""
                UPDATE sessions
                SET is_active = 0, ended_at = ?
                WHERE id = ?
            """, (now, session["id"]))

            logger.info(f"📍 Session #{session['id']} ended: {address[:16]}... ({session['presence_seconds']}s)")

            return {
                "session_id": session["id"],
                "address": address,
                "presence_seconds": session["presence_seconds"],
                "coins_earned": session["coins_earned"]
            }

    def get_total_presence(self, address: str) -> int:
        """Get total presence seconds for address"""
        cursor = self.conn.execute("""
            SELECT COALESCE(SUM(presence_seconds), 0) as total
            FROM sessions WHERE address = ?
        """, (address,))
        row = cursor.fetchone()
        return row["total"] if row else 0

    # ═══════════════════════════════════════════════════════════════════════════════
    #                              TIME_BANK COMPATIBILITY API
    # ═══════════════════════════════════════════════════════════════════════════════

    def wallet(self, address: str, addr_type: str = "unknown") -> Dict[str, Any]:
        """Create/get wallet (TIME_BANK compatibility)"""
        return self.create_wallet(address)

    def credit(self, address: str, amount: float, addr_type: str = "unknown") -> float:
        """Credit balance (TIME_BANK compatibility)"""
        return self.update_balance(address, amount)

    def balance(self, address: str) -> float:
        """Get balance (TIME_BANK compatibility — alias for get_balance)"""
        return self.get_balance(address)

    def send(self, from_addr: str, to_addr: str, amount: float) -> Dict[str, Any]:
        """Send coins (TIME_BANK compatibility)"""
        return self.transfer(from_addr, to_addr, amount)

    def tx_feed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Transaction feed (TIME_BANK compatibility)"""
        cursor = self.conn.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def tx_verify(self, proof: Dict) -> bool:
        """Verify transaction (TIME_BANK compatibility)"""
        tx_id = proof.get("tx_id", "")
        if not tx_id:
            return False
        cursor = self.conn.execute(
            "SELECT * FROM transactions WHERE tx_id = ?",
            (tx_id,)
        )
        return cursor.fetchone() is not None

    def my_txs(self, address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """User's transactions (TIME_BANK compatibility)"""
        return self.get_transactions(address, limit)

    def wallets(self, addr_type: str = None) -> List[Dict[str, Any]]:
        """List wallets (TIME_BANK compatibility)"""
        cursor = self.conn.execute(
            "SELECT * FROM wallets ORDER BY balance DESC LIMIT 1000"
        )
        return [dict(row) for row in cursor.fetchall()]

    # ═══════════════════════════════════════════════════════════════════════════════
    #                              STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}

        cursor = self.conn.execute("SELECT COUNT(*) as count FROM wallets")
        stats["total_wallets"] = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COALESCE(SUM(balance), 0) as total FROM wallets")
        stats["total_supply"] = cursor.fetchone()["total"]

        cursor = self.conn.execute("SELECT COUNT(*) as count FROM transactions")
        stats["total_transactions"] = cursor.fetchone()["count"]

        cursor = self.conn.execute(
            "SELECT COALESCE(SUM(presence_seconds), 0) as total FROM sessions"
        )
        stats["total_presence_seconds"] = cursor.fetchone()["total"]

        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE is_active = 1"
        )
        stats["active_sessions"] = cursor.fetchone()["count"]

        cursor = self.conn.execute("""
            SELECT address, balance, alias
            FROM wallets
            ORDER BY balance DESC
            LIMIT 10
        """)
        stats["top_balances"] = [dict(row) for row in cursor.fetchall()]

        return stats

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get balance leaderboard"""
        cursor = self.conn.execute("""
            SELECT address, balance, alias,
                   (SELECT COALESCE(SUM(presence_seconds), 0) FROM sessions s WHERE s.address = w.address) as presence
            FROM wallets w
            WHERE balance > 0
            ORDER BY balance DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════════
#                              SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_db_instance: Optional[MontanaDB] = None
_db_lock = threading.Lock()

def get_db() -> MontanaDB:
    """Get singleton database instance (thread-safe)"""
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = MontanaDB()
    return _db_instance


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    db = MontanaDB()

    if len(sys.argv) < 2:
        print("""
Montana Database CLI

Usage:
    python montana_db.py stats              - Database statistics
    python montana_db.py balance <address>  - Get balance
    python montana_db.py wallet <address>   - Get wallet info
    python montana_db.py leaderboard        - Top balances
    python montana_db.py tx <address>       - Transaction history
        """)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        stats = db.get_stats()
        print("\n📊 Montana Database Statistics:")
        print(f"   Wallets:      {stats['total_wallets']}")
        print(f"   Total Supply: {stats['total_supply']:.2f} Ɉ")
        print(f"   Transactions: {stats['total_transactions']}")
        print(f"   Presence:     {stats['total_presence_seconds']} seconds")
        print(f"   Active:       {stats['active_sessions']} sessions")

    elif cmd == "balance" and len(sys.argv) > 2:
        address = sys.argv[2]
        balance = db.get_balance(address)
        print(f"💰 Balance {address[:16]}...: {balance} Ɉ")

    elif cmd == "wallet" and len(sys.argv) > 2:
        address = sys.argv[2]
        wallet = db.get_wallet(address)
        if wallet:
            print(f"\n🔐 Wallet: {wallet['address']}")
            print(f"   Balance: {wallet['balance']} Ɉ")
            print(f"   Alias:   {wallet['alias'] or '-'}")
            print(f"   Phone:   {wallet['phone'] or '-'}")
            print(f"   Created: {wallet['created_at']}")
        else:
            print(f"Wallet not found: {address}")

    elif cmd == "leaderboard":
        leaders = db.get_leaderboard()
        print("\n🏆 Leaderboard:")
        for i, w in enumerate(leaders, 1):
            name = w.get("alias") or w["address"][:16] + "..."
            print(f"   {i}. {name}: {w['balance']:.2f} Ɉ")

    elif cmd == "tx" and len(sys.argv) > 2:
        address = sys.argv[2]
        txs = db.get_transactions(address, limit=10)
        print(f"\n📜 Transactions for {address[:16]}...:")
        for tx in txs:
            direction = "→" if tx["from_address"] == address else "←"
            other = tx["to_address"] if direction == "→" else tx["from_address"]
            print(f"   {direction} {tx['amount']} Ɉ ({other[:10]}...) [{tx['timestamp'][:10]}]")

    else:
        print("Unknown command. Run without arguments for help.")
