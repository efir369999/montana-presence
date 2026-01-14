"""
Montana Bot Storage

Manages user state (NOT private keys — keys stay on user device)
"""

import json
import os
import sqlite3
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from config import DATA_DIR, DB_FILE


@dataclass
class UserState:
    """
    User state (stored on bot server)

    SECURITY: Private keys NOT stored here — only on user device
    """
    telegram_id: int
    public_key: str  # Montana address (0x...)
    created_at: int
    last_sign: Optional[int] = None
    sign_count: int = 0
    balance: int = 0  # Cached balance (in smallest unit)
    nonce: int = 0  # Transaction nonce


class Storage:
    """
    SQLite storage for user state
    """

    def __init__(self, db_path: str = DB_FILE):
        """Initialize storage"""
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tables if not exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_sign INTEGER,
                    sign_count INTEGER DEFAULT 0,
                    balance INTEGER DEFAULT 0,
                    nonce INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS signatures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    tau2_index INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    signature BLOB NOT NULL,
                    broadcasted INTEGER DEFAULT 0,
                    FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    recipient TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    nonce INTEGER NOT NULL,
                    signature BLOB NOT NULL,
                    timestamp INTEGER NOT NULL,
                    confirmed INTEGER DEFAULT 0,
                    FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
                )
            """)

            conn.commit()

    def create_user(self, telegram_id: int, public_key: str) -> UserState:
        """
        Create new user

        Args:
            telegram_id: Telegram user ID
            public_key: Montana address (0x...)

        Returns:
            UserState instance
        """
        now = int(datetime.now().timestamp())

        user = UserState(
            telegram_id=telegram_id,
            public_key=public_key,
            created_at=now
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO users (telegram_id, public_key, created_at)
                VALUES (?, ?, ?)
            """, (telegram_id, public_key, now))
            conn.commit()

        return user

    def get_user(self, telegram_id: int) -> Optional[UserState]:
        """Get user by Telegram ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM users WHERE telegram_id = ?
            """, (telegram_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return UserState(**dict(row))

    def update_user(self, user: UserState):
        """Update user state"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE users
                SET last_sign = ?, sign_count = ?, balance = ?, nonce = ?
                WHERE telegram_id = ?
            """, (user.last_sign, user.sign_count, user.balance, user.nonce, user.telegram_id))
            conn.commit()

    def save_signature(
        self,
        telegram_id: int,
        tau2_index: int,
        timestamp: int,
        signature: bytes
    ):
        """Save presence signature"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO signatures (telegram_id, tau2_index, timestamp, signature)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, tau2_index, timestamp, signature))
            conn.commit()

    def save_transaction(
        self,
        telegram_id: int,
        recipient: str,
        amount: int,
        nonce: int,
        signature: bytes
    ):
        """Save transaction"""
        now = int(datetime.now().timestamp())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO transactions
                (telegram_id, recipient, amount, nonce, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, recipient, amount, nonce, signature, now))
            conn.commit()

    def get_user_count(self) -> int:
        """Get total user count"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def get_signature_count(self) -> int:
        """Get total signature count"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM signatures")
            return cursor.fetchone()[0]


# Singleton instance
_storage = None

def get_storage() -> Storage:
    """Get storage singleton"""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
