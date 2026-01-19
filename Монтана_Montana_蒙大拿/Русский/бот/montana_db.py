#!/usr/bin/env python3
"""
MONTANA DATABASE — Единая база данных Montana
==============================================

Хранит:
- Пользователей (telegram_id)
- Монеты времени (TIME_BANK)
- Мысли (Гиппокамп)
- Сессии присутствия

SQLite + JSON backup
"""

import sqlite3
import json
import threading
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
import logging


def hash_address(address: str) -> str:
    """Хэширует адрес для публичного отображения"""
    return hashlib.sha256(address.encode()).hexdigest()[:16]


def generate_tx_proof() -> str:
    """Генерирует криптографическое доказательство транзакции"""
    return secrets.token_hex(32)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MONTANA_DB")


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

class MontanaDB:
    """Единая база данных Montana"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent / "data" / "montana.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._init_schema()

        logger.info(f"📦 MontanaDB инициализирована: {self.db_path}")

    @contextmanager
    def _get_conn(self):
        """Thread-safe соединение"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
        yield self._local.conn

    def _init_schema(self):
        """Создаёт таблицы"""
        with self._get_conn() as conn:
            conn.executescript("""
                -- Пользователи
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT DEFAULT 'ru',
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    total_coins INTEGER DEFAULT 0,
                    total_presence_seconds INTEGER DEFAULT 0,
                    sessions_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );

                -- Сессии присутствия
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    presence_seconds INTEGER DEFAULT 0,
                    coins_earned INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    last_activity REAL NOT NULL,
                    last_awarded_at INTEGER DEFAULT 0,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
                );

                -- Транзакции монет
                CREATE TABLE IF NOT EXISTS coin_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event TEXT NOT NULL,
                    coins_amount INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    session_id INTEGER,
                    source TEXT DEFAULT 'time_bank',
                    metadata TEXT,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                -- Мысли (Гиппокамп)
                CREATE TABLE IF NOT EXISTS thoughts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    message TEXT NOT NULL,
                    response TEXT,
                    source TEXT DEFAULT 'miniapp',
                    session_id INTEGER,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                -- КВАНТОВЫЕ КОШЕЛЬКИ (независимые адреса)
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    address_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    balance INTEGER DEFAULT 0,
                    total_presence_seconds INTEGER DEFAULT 0
                );

                -- Переводы монет между аккаунтами (АНОНИМНЫЕ)
                CREATE TABLE IF NOT EXISTS coin_transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tx_proof TEXT UNIQUE NOT NULL,
                    from_hash TEXT NOT NULL,
                    to_hash TEXT NOT NULL,
                    amount_hidden INTEGER DEFAULT 1,
                    tx_type TEXT DEFAULT 'transfer'
                );

                -- Индексы
                CREATE INDEX IF NOT EXISTS idx_sessions_telegram ON sessions(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active);
                CREATE INDEX IF NOT EXISTS idx_transactions_telegram ON coin_transactions(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_thoughts_telegram ON thoughts(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_thoughts_timestamp ON thoughts(timestamp);
                CREATE INDEX IF NOT EXISTS idx_wallets_type ON wallets(address_type);
            """)
            conn.commit()

    # --------------------------------------------------------
    # ПОЛЬЗОВАТЕЛИ
    # --------------------------------------------------------

    def get_or_create_user(
        self,
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
        language_code: str = "ru"
    ) -> Dict[str, Any]:
        """Получает или создаёт пользователя"""
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()

            if row:
                # Обновляем last_seen
                conn.execute(
                    "UPDATE users SET last_seen = ?, username = COALESCE(?, username) WHERE telegram_id = ?",
                    (now, username, telegram_id)
                )
                conn.commit()
                return dict(row)

            # Создаём нового
            conn.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name, language_code, created_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (telegram_id, username, first_name, last_name, language_code, now, now))
            conn.commit()

            logger.info(f"👤 Новый пользователь: {telegram_id} ({username})")

            return {
                "telegram_id": telegram_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
                "created_at": now,
                "last_seen": now,
                "total_coins": 0,
                "total_presence_seconds": 0,
                "sessions_count": 0,
                "is_active": 1
            }

    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает пользователя по telegram_id"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_balance(self, telegram_id: int) -> int:
        """Возвращает баланс монет"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT total_coins FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            return row["total_coins"] if row else 0

    def update_coins(self, telegram_id: int, delta: int) -> int:
        """Обновляет баланс монет, возвращает новый баланс"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET total_coins = total_coins + ? WHERE telegram_id = ?",
                (delta, telegram_id)
            )
            conn.commit()
            return self.get_balance(telegram_id)

    # --------------------------------------------------------
    # СЕССИИ (TIME_BANK)
    # --------------------------------------------------------

    def start_session(self, telegram_id: int) -> int:
        """Начинает сессию, возвращает session_id"""
        import time
        now = datetime.now(timezone.utc).isoformat()

        # Убеждаемся что пользователь существует
        self.get_or_create_user(telegram_id)

        with self._get_conn() as conn:
            # Закрываем старые активные сессии
            conn.execute(
                "UPDATE sessions SET is_active = 0, ended_at = ? WHERE telegram_id = ? AND is_active = 1",
                (now, telegram_id)
            )

            # Создаём новую
            cursor = conn.execute("""
                INSERT INTO sessions (telegram_id, started_at, last_activity, is_active)
                VALUES (?, ?, ?, 1)
            """, (telegram_id, now, time.time()))

            # Увеличиваем счётчик сессий
            conn.execute(
                "UPDATE users SET sessions_count = sessions_count + 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            conn.commit()

            session_id = cursor.lastrowid
            logger.info(f"📍 Сессия #{session_id} начата: user={telegram_id}")
            return session_id

    def get_active_session(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает активную сессию"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE telegram_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
                (telegram_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session(
        self,
        session_id: int,
        presence_seconds: int = None,
        last_activity: float = None,
        last_awarded_at: int = None,
        coins_earned: int = None
    ):
        """Обновляет сессию"""
        updates = []
        params = []

        if presence_seconds is not None:
            updates.append("presence_seconds = ?")
            params.append(presence_seconds)
        if last_activity is not None:
            updates.append("last_activity = ?")
            params.append(last_activity)
        if last_awarded_at is not None:
            updates.append("last_awarded_at = ?")
            params.append(last_awarded_at)
        if coins_earned is not None:
            updates.append("coins_earned = coins_earned + ?")
            params.append(coins_earned)

        if not updates:
            return

        params.append(session_id)
        sql = f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?"

        with self._get_conn() as conn:
            conn.execute(sql, params)
            conn.commit()

    def end_session(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Завершает сессию"""
        session = self.get_active_session(telegram_id)
        if not session:
            return None

        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET is_active = 0, ended_at = ? WHERE id = ?",
                (now, session["id"])
            )

            # Обновляем total_presence_seconds пользователя
            conn.execute(
                "UPDATE users SET total_presence_seconds = total_presence_seconds + ?, last_seen = ? WHERE telegram_id = ?",
                (session["presence_seconds"], now, telegram_id)
            )
            conn.commit()

        logger.info(f"🏁 Сессия #{session['id']} завершена: {session['presence_seconds']} сек")
        return session

    def get_all_active_sessions(self) -> List[Dict[str, Any]]:
        """Возвращает все активные сессии"""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM sessions WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]

    # --------------------------------------------------------
    # ТРАНЗАКЦИИ МОНЕТ
    # --------------------------------------------------------

    def add_coin_transaction(
        self,
        telegram_id: int,
        event: str,
        coins_amount: int,
        session_id: int = None,
        source: str = "time_bank",
        metadata: dict = None
    ) -> int:
        """Добавляет транзакцию и обновляет баланс"""
        now = datetime.now(timezone.utc).isoformat()

        # Обновляем баланс
        new_balance = self.update_coins(telegram_id, coins_amount)

        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO coin_transactions (telegram_id, timestamp, event, coins_amount, balance_after, session_id, source, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                telegram_id, now, event, coins_amount, new_balance,
                session_id, source, json.dumps(metadata) if metadata else None
            ))
            conn.commit()

            logger.info(f"💰 {event}: user={telegram_id}, {'+' if coins_amount > 0 else ''}{coins_amount} Ɉ, balance={new_balance}")
            return cursor.lastrowid

    def get_transactions(self, telegram_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает историю транзакций"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM coin_transactions WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
                (telegram_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    # --------------------------------------------------------
    # МЫСЛИ (ГИППОКАМП)
    # --------------------------------------------------------

    def save_thought(
        self,
        telegram_id: int,
        message: str,
        response: str = None,
        source: str = "miniapp",
        session_id: int = None
    ) -> int:
        """Сохраняет мысль в Гиппокамп"""
        now = datetime.now(timezone.utc).isoformat()

        # Убеждаемся что пользователь существует
        self.get_or_create_user(telegram_id)

        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO thoughts (telegram_id, timestamp, message, response, source, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, now, message, response, source, session_id))
            conn.commit()

            logger.info(f"💭 Мысль сохранена: user={telegram_id}")
            return cursor.lastrowid

    def get_thoughts(self, telegram_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Получает мысли пользователя"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM thoughts WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
                (telegram_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_thoughts(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Получает все мысли"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM thoughts ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # --------------------------------------------------------
    # КОШЕЛЬКИ (адрес = ключ = telegram_id или ip)
    # --------------------------------------------------------

    def wallet(self, address: str, addr_type: str = "unknown") -> Dict[str, Any]:
        """
        Получает или создаёт кошелёк.
        address = telegram_id (str) или ip_address
        address = ключ к кошельку
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM wallets WHERE address = ?",
                (address,)
            )
            row = cursor.fetchone()

            if row:
                conn.execute(
                    "UPDATE wallets SET last_seen = ? WHERE address = ?",
                    (now, address)
                )
                conn.commit()
                return dict(row)

            conn.execute("""
                INSERT INTO wallets (address, address_type, created_at, last_seen)
                VALUES (?, ?, ?, ?)
            """, (address, addr_type, now, now))
            conn.commit()

            logger.info(f"⚛️ Кошелёк: {address} [{addr_type}]")

            return {
                "address": address,
                "address_type": addr_type,
                "created_at": now,
                "last_seen": now,
                "balance": 0,
                "total_presence_seconds": 0
            }

    def balance(self, address: str) -> int:
        """Баланс кошелька по адресу (ключу)"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT balance FROM wallets WHERE address = ?",
                (address,)
            )
            row = cursor.fetchone()
            return row["balance"] if row else 0

    def credit(self, address: str, amount: int, addr_type: str = "unknown") -> int:
        """Начисляет монеты на кошелёк"""
        self.wallet(address, addr_type)

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallets SET balance = balance + ? WHERE address = ?",
                (amount, address)
            )
            conn.commit()
            return self.balance(address)

    def debit(self, address: str, amount: int) -> bool:
        """Списывает монеты с кошелька"""
        if self.balance(address) < amount:
            return False

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallets SET balance = balance - ? WHERE address = ?",
                (amount, address)
            )
            conn.commit()
            return True

    def presence(self, address: str, seconds: int) -> None:
        """Обновляет время присутствия"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallets SET total_presence_seconds = total_presence_seconds + ? WHERE address = ?",
                (seconds, address)
            )
            conn.commit()

    def wallets(self, addr_type: str = None) -> List[Dict[str, Any]]:
        """Все кошельки"""
        with self._get_conn() as conn:
            if addr_type:
                cursor = conn.execute(
                    "SELECT * FROM wallets WHERE address_type = ? ORDER BY balance DESC",
                    (addr_type,)
                )
            else:
                cursor = conn.execute("SELECT * FROM wallets ORDER BY balance DESC")
            return [dict(row) for row in cursor.fetchall()]

    # --------------------------------------------------------
    # ПЕРЕВОДЫ (между адресами)
    # --------------------------------------------------------

    def send(
        self,
        from_addr: str,
        to_addr: str,
        amount: int
    ) -> Optional[str]:
        """
        Перевод между кошельками.
        Возвращает tx_proof или None.

        АНОНИМНОСТЬ:
        - Публично только хэши адресов
        - Сумма не хранится
        """
        if amount <= 0:
            return None

        if not self.debit(from_addr, amount):
            return None

        self.credit(to_addr, amount)

        # Генерируем proof, храним только хэши
        tx_proof = generate_tx_proof()
        from_hash = hash_address(from_addr)
        to_hash = hash_address(to_addr)

        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO coin_transfers (timestamp, tx_proof, from_hash, to_hash, tx_type)
                VALUES (?, ?, ?, ?, 'send')
            """, (now, tx_proof, from_hash, to_hash))
            conn.commit()

        logger.info(f"💸 TX: {tx_proof[:12]}...")
        return tx_proof

    # --------------------------------------------------------
    # ЛИДЕРБОРД
    # --------------------------------------------------------

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Топ пользователей по монетам"""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT telegram_id, username, first_name, total_coins, total_presence_seconds
                FROM users
                ORDER BY total_coins DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --------------------------------------------------------
    # TX HISTORY (анонимный)
    # --------------------------------------------------------

    def tx_feed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Публичная лента TX (только proof, type, timestamp)"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT id, timestamp, tx_proof, tx_type FROM coin_transfers ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [{
                "id": r["id"],
                "timestamp": r["timestamp"],
                "proof": r["tx_proof"][:16] + "...",
                "type": r["tx_type"]
            } for r in cursor.fetchall()]

    def tx_verify(self, proof: str) -> Dict[str, Any]:
        """Верификация TX по proof"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT timestamp, tx_type FROM coin_transfers WHERE tx_proof = ?",
                (proof,)
            )
            row = cursor.fetchone()
            if row:
                return {"valid": True, "timestamp": row["timestamp"], "type": row["tx_type"]}
            return {"valid": False}

    def my_txs(self, address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Личная история TX (in/out направление)"""
        my_hash = hash_address(address)

        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, tx_proof, from_hash, to_hash, tx_type
                FROM coin_transfers
                WHERE from_hash = ? OR to_hash = ?
                ORDER BY id DESC LIMIT ?
            """, (my_hash, my_hash, limit))

            return [{
                "id": r["id"],
                "timestamp": r["timestamp"],
                "proof": r["tx_proof"][:16] + "...",
                "direction": "out" if r["from_hash"] == my_hash else "in",
                "type": r["tx_type"]
            } for r in cursor.fetchall()]

    # --------------------------------------------------------
    # ЭКСПОРТ
    # --------------------------------------------------------

    def export_json(self, output_path: Path = None) -> str:
        """Экспортирует базу в JSON"""
        output_path = output_path or self.db_path.parent / "montana_export.json"

        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "users": [],
            "thoughts": [],
            "transactions": []
        }

        with self._get_conn() as conn:
            # Пользователи
            cursor = conn.execute("SELECT * FROM users")
            data["users"] = [dict(row) for row in cursor.fetchall()]

            # Мысли
            cursor = conn.execute("SELECT * FROM thoughts ORDER BY id")
            data["thoughts"] = [dict(row) for row in cursor.fetchall()]

            # Транзакции
            cursor = conn.execute("SELECT * FROM coin_transactions ORDER BY id")
            data["transactions"] = [dict(row) for row in cursor.fetchall()]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"📤 Экспорт: {output_path}")
        return str(output_path)

    # --------------------------------------------------------
    # СТАТИСТИКА
    # --------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Общая статистика"""
        with self._get_conn() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as c FROM users")
            stats["total_users"] = cursor.fetchone()["c"]

            cursor = conn.execute("SELECT SUM(total_coins) as c FROM users")
            stats["total_coins_minted"] = cursor.fetchone()["c"] or 0

            cursor = conn.execute("SELECT SUM(total_presence_seconds) as c FROM users")
            stats["total_presence_seconds"] = cursor.fetchone()["c"] or 0

            cursor = conn.execute("SELECT COUNT(*) as c FROM thoughts")
            stats["total_thoughts"] = cursor.fetchone()["c"]

            cursor = conn.execute("SELECT COUNT(*) as c FROM sessions WHERE is_active = 1")
            stats["active_sessions"] = cursor.fetchone()["c"]

            return stats


# ============================================================
# SINGLETON
# ============================================================

_db_instance: Optional[MontanaDB] = None

def get_db() -> MontanaDB:
    """Возвращает глобальный экземпляр базы"""
    global _db_instance
    if _db_instance is None:
        _db_instance = MontanaDB()
    return _db_instance


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    db = get_db()

    if len(sys.argv) < 2:
        print("""
MONTANA DATABASE — Единая база данных

Команды:
    python montana_db.py stats              — общая статистика
    python montana_db.py user <telegram_id> — информация о пользователе
    python montana_db.py balance <tg_id>    — баланс монет
    python montana_db.py leaderboard        — топ по монетам
    python montana_db.py thoughts <tg_id>   — мысли пользователя
    python montana_db.py export             — экспорт в JSON
        """)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        stats = db.get_stats()
        print("📊 Статистика Montana:")
        print("-" * 40)
        print(f"Пользователей: {stats['total_users']}")
        print(f"Монет выпущено: {stats['total_coins_minted']} Ɉ")
        print(f"Секунд присутствия: {stats['total_presence_seconds']}")
        print(f"Мыслей записано: {stats['total_thoughts']}")
        print(f"Активных сессий: {stats['active_sessions']}")

    elif cmd == "user" and len(sys.argv) > 2:
        telegram_id = int(sys.argv[2])
        user = db.get_user(telegram_id)
        if user:
            print(json.dumps(user, indent=2, ensure_ascii=False))
        else:
            print(f"Пользователь {telegram_id} не найден")

    elif cmd == "balance" and len(sys.argv) > 2:
        telegram_id = int(sys.argv[2])
        balance = db.get_balance(telegram_id)
        print(f"💰 Баланс {telegram_id}: {balance} Ɉ")

    elif cmd == "leaderboard":
        leaders = db.get_leaderboard()
        print("🏆 Топ Montana:")
        print("-" * 40)
        for i, u in enumerate(leaders, 1):
            name = u.get("username") or u.get("first_name") or str(u["telegram_id"])
            print(f"{i}. {name}: {u['total_coins']} Ɉ ({u['total_presence_seconds']} сек)")

    elif cmd == "thoughts" and len(sys.argv) > 2:
        telegram_id = int(sys.argv[2])
        thoughts = db.get_thoughts(telegram_id, limit=20)
        print(f"💭 Мысли {telegram_id}:")
        print("-" * 40)
        for t in thoughts:
            print(f"[{t['timestamp']}] {t['message'][:50]}...")

    elif cmd == "export":
        path = db.export_json()
        print(f"✓ Экспортировано: {path}")

    else:
        print(f"Неизвестная команда: {cmd}")
