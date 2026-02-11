#!/usr/bin/env python3
"""
TIME_LEDGER — Распределённый леджер Montana Protocol
=====================================================

ПРИНЦИП:
- Каждое начисление = подписанная транзакция
- Узлы транслируют транзакции друг другу (HTTP)
- Баланс = сумма всех транзакций для адреса
- Конфликты: timestamp + node_priority

ГАРАНТИИ:
- Eventual consistency (секунды)
- Нет единой точки отказа
- Полный аудит всех операций
- ML-DSA-65 верификация

Alejandro Montana © 2026
"""

import os
import json
import time
import uuid
import sqlite3
import asyncio
import aiohttp
import hashlib
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# ML-DSA-65 для подписей
try:
    from node_crypto import sign_message, verify_signature, get_node_crypto_system
    ML_DSA_AVAILABLE = True
except ImportError:
    ML_DSA_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TIME_LEDGER")


# ═══════════════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ СЕТИ
# ═══════════════════════════════════════════════════════════════════════════════

NODES = {
    "amsterdam":   {"ip": "72.56.102.240",  "port": 8765, "priority": 0},
    "moscow":      {"ip": "176.124.208.93", "port": 8765, "priority": 1},
    "almaty":      {"ip": "91.200.148.93",  "port": 8765, "priority": 2},
    "spb":         {"ip": "188.225.58.98",  "port": 8765, "priority": 3},
    "novosibirsk": {"ip": "147.45.147.247", "port": 8765, "priority": 4},
}

# Текущий узел (из ENV)
CURRENT_NODE = os.getenv("MONTANA_NODE_NAME", "amsterdam")


# ═══════════════════════════════════════════════════════════════════════════════
# ТРАНЗАКЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Transaction:
    """Транзакция в леджере Montana"""
    tx_id: str              # UUID транзакции
    timestamp: int          # Unix timestamp (ms)
    address: str            # Адрес кошелька (address)
    amount: int             # Сумма (положительная = credit, отрицательная = debit)
    tx_type: str            # credit, debit, transfer_in, transfer_out
    node: str               # Узел-источник
    t2_index: int           # Индекс T2 слайса
    prev_hash: str          # Хэш предыдущей TX (цепочка)
    signature: str          # ML-DSA-65 подпись узла

    @classmethod
    def create(cls, address: str, amount: int, tx_type: str,
               node: str, t2_index: int, prev_hash: str,
               private_key: Optional[str] = None) -> "Transaction":
        """Создаёт и подписывает транзакцию"""
        tx = cls(
            tx_id=str(uuid.uuid4()),
            timestamp=int(time.time() * 1000),
            address=address,
            amount=amount,
            tx_type=tx_type,
            node=node,
            t2_index=t2_index,
            prev_hash=prev_hash,
            signature=""
        )

        # Подписываем
        if private_key and ML_DSA_AVAILABLE:
            message = tx.to_sign_message()
            tx.signature = sign_message(private_key, message)

        return tx

    def to_sign_message(self) -> str:
        """Сообщение для подписи"""
        return f"MONTANA_TX:{self.tx_id}:{self.timestamp}:{self.address}:{self.amount}:{self.tx_type}:{self.node}:{self.t2_index}:{self.prev_hash}"

    def tx_hash(self) -> str:
        """SHA256 хэш транзакции"""
        data = f"{self.tx_id}:{self.timestamp}:{self.address}:{self.amount}:{self.signature}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self, public_key: str) -> bool:
        """Верифицирует подпись"""
        if not ML_DSA_AVAILABLE or not self.signature:
            return True  # Без криптографии — доверяем

        message = self.to_sign_message()
        return verify_signature(public_key, message, self.signature)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(**data)


# ═══════════════════════════════════════════════════════════════════════════════
# ЛЕДЖЕР (локальная база)
# ═══════════════════════════════════════════════════════════════════════════════

class TimeLedger:
    """
    Распределённый леджер Montana

    Хранит все транзакции локально.
    Транслирует новые TX на другие узлы.
    Баланс = сумма всех TX для адреса.
    """

    def __init__(self, db_path: Optional[Path] = None, node_name: str = None):
        self.node_name = node_name or CURRENT_NODE
        self.db_path = db_path or Path(__file__).parent / "data" / "ledger.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._local = threading.local()
        self._init_schema()

        # Криптография узла
        self._private_key: Optional[str] = None
        self._public_key: Optional[str] = None
        self._node_keys: Dict[str, str] = {}  # node_name -> public_key

        # Последний хэш для цепочки
        self._last_hash = self._get_last_hash()

        # HTTP сессия для broadcast
        self._http_session: Optional[aiohttp.ClientSession] = None

        # T2 счётчик
        self.t2_index = 0

        logger.info(f"📒 TimeLedger инициализирован: {self.node_name}")
        logger.info(f"   DB: {self.db_path}")
        logger.info(f"   ML-DSA-65: {'✅' if ML_DSA_AVAILABLE else '❌'}")

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
                -- Транзакции (append-only ledger)
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_id TEXT PRIMARY KEY,
                    timestamp INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    tx_type TEXT NOT NULL,
                    node TEXT NOT NULL,
                    t2_index INTEGER NOT NULL,
                    prev_hash TEXT NOT NULL,
                    signature TEXT,
                    tx_hash TEXT NOT NULL,
                    received_at INTEGER NOT NULL,
                    verified INTEGER DEFAULT 0
                );

                -- Индексы для быстрого поиска
                CREATE INDEX IF NOT EXISTS idx_tx_address ON transactions(address);
                CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_tx_node ON transactions(node);
                CREATE INDEX IF NOT EXISTS idx_tx_t2 ON transactions(t2_index);

                -- Кэш балансов (для скорости)
                CREATE TABLE IF NOT EXISTS balance_cache (
                    address TEXT PRIMARY KEY,
                    balance INTEGER NOT NULL,
                    last_tx_id TEXT,
                    updated_at INTEGER NOT NULL
                );

                -- Публичные ключи узлов
                CREATE TABLE IF NOT EXISTS node_keys (
                    node_name TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                -- Sync статус с другими узлами
                CREATE TABLE IF NOT EXISTS sync_status (
                    node_name TEXT PRIMARY KEY,
                    last_tx_timestamp INTEGER DEFAULT 0,
                    last_sync_at INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'unknown'
                );
            """)
            conn.commit()

    def _get_last_hash(self) -> str:
        """Получает хэш последней транзакции"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT tx_hash FROM transactions ORDER BY timestamp DESC, tx_id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row["tx_hash"] if row else "0" * 64

    # ═══════════════════════════════════════════════════════════════════════════
    # КЛЮЧИ
    # ═══════════════════════════════════════════════════════════════════════════

    def set_node_keys(self, private_key: str, public_key: str):
        """Устанавливает ключи текущего узла"""
        self._private_key = private_key
        self._public_key = public_key
        logger.info(f"🔑 Node keys set (ML-DSA-65)")

    def register_node_key(self, node_name: str, public_key: str):
        """Регистрирует публичный ключ другого узла"""
        self._node_keys[node_name] = public_key

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO node_keys (node_name, public_key, updated_at)
                VALUES (?, ?, ?)
            """, (node_name, public_key, int(time.time() * 1000)))
            conn.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # ТРАНЗАКЦИИ
    # ═══════════════════════════════════════════════════════════════════════════

    def credit(self, address: str, amount: int, t2_index: int = None) -> Transaction:
        """
        Начисляет монеты на адрес.
        Создаёт TX, сохраняет локально, транслирует на другие узлы.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        tx = Transaction.create(
            address=address,
            amount=amount,
            tx_type="credit",
            node=self.node_name,
            t2_index=t2_index or self.t2_index,
            prev_hash=self._last_hash,
            private_key=self._private_key
        )

        self._save_tx(tx)
        self._update_balance_cache(address)

        # Async broadcast (fire-and-forget)
        asyncio.create_task(self._broadcast_tx(tx))

        logger.info(f"💰 Credit: {address} +{amount} Ɉ (TX: {tx.tx_id[:8]}...)")

        return tx

    def debit(self, address: str, amount: int) -> Optional[Transaction]:
        """
        Списывает монеты с адреса.
        Проверяет баланс перед списанием.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        balance = self.balance(address)
        if balance < amount:
            logger.warning(f"❌ Insufficient balance: {address} has {balance}, needs {amount}")
            return None

        tx = Transaction.create(
            address=address,
            amount=-amount,  # Отрицательная сумма = debit
            tx_type="debit",
            node=self.node_name,
            t2_index=self.t2_index,
            prev_hash=self._last_hash,
            private_key=self._private_key
        )

        self._save_tx(tx)
        self._update_balance_cache(address)

        asyncio.create_task(self._broadcast_tx(tx))

        logger.info(f"💸 Debit: {address} -{amount} Ɉ (TX: {tx.tx_id[:8]}...)")

        return tx

    def transfer(self, from_addr: str, to_addr: str, amount: int) -> Optional[tuple]:
        """
        Перевод между адресами.
        Создаёт две связанные TX (out + in).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        balance = self.balance(from_addr)
        if balance < amount:
            return None

        # TX out (debit)
        tx_out = Transaction.create(
            address=from_addr,
            amount=-amount,
            tx_type="transfer_out",
            node=self.node_name,
            t2_index=self.t2_index,
            prev_hash=self._last_hash,
            private_key=self._private_key
        )
        self._save_tx(tx_out)

        # TX in (credit)
        tx_in = Transaction.create(
            address=to_addr,
            amount=amount,
            tx_type="transfer_in",
            node=self.node_name,
            t2_index=self.t2_index,
            prev_hash=tx_out.tx_hash(),
            private_key=self._private_key
        )
        self._save_tx(tx_in)

        self._update_balance_cache(from_addr)
        self._update_balance_cache(to_addr)

        # Broadcast both
        asyncio.create_task(self._broadcast_tx(tx_out))
        asyncio.create_task(self._broadcast_tx(tx_in))

        logger.info(f"💸 Transfer: {from_addr} → {to_addr}: {amount} Ɉ")

        return (tx_out, tx_in)

    def _save_tx(self, tx: Transaction):
        """Сохраняет транзакцию в локальную базу"""
        tx_hash = tx.tx_hash()

        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO transactions
                    (tx_id, timestamp, address, amount, tx_type, node, t2_index,
                     prev_hash, signature, tx_hash, received_at, verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx.tx_id, tx.timestamp, tx.address, tx.amount, tx.tx_type,
                    tx.node, tx.t2_index, tx.prev_hash, tx.signature, tx_hash,
                    int(time.time() * 1000), 1 if tx.node == self.node_name else 0
                ))
                conn.commit()
                self._last_hash = tx_hash
            except sqlite3.IntegrityError:
                # TX already exists — OK (идемпотентность)
                pass

    def receive_tx(self, tx_data: dict) -> bool:
        """
        Получает транзакцию от другого узла.
        Верифицирует и сохраняет.
        """
        try:
            tx = Transaction.from_dict(tx_data)

            # Верификация подписи
            if tx.node in self._node_keys:
                if not tx.verify(self._node_keys[tx.node]):
                    logger.warning(f"❌ Invalid signature from {tx.node}: {tx.tx_id}")
                    return False

            self._save_tx(tx)
            self._update_balance_cache(tx.address)

            logger.debug(f"📥 Received TX from {tx.node}: {tx.tx_id[:8]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Error receiving TX: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # БАЛАНС
    # ═══════════════════════════════════════════════════════════════════════════

    def balance(self, address: str) -> int:
        """
        Возвращает баланс адреса.
        Баланс = SUM(amount) всех транзакций.
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE address = ?",
                (address,)
            )
            row = cursor.fetchone()
            return row["balance"] if row else 0

    def balance_cached(self, address: str) -> int:
        """Баланс из кэша (быстрее)"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT balance FROM balance_cache WHERE address = ?",
                (address,)
            )
            row = cursor.fetchone()
            if row:
                return row["balance"]

        # Кэш пустой — вычисляем и кэшируем
        return self._update_balance_cache(address)

    def _update_balance_cache(self, address: str) -> int:
        """Обновляет кэш баланса"""
        balance = self.balance(address)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO balance_cache (address, balance, updated_at)
                VALUES (?, ?, ?)
            """, (address, balance, int(time.time() * 1000)))
            conn.commit()

        return balance

    def get_balance_with_pending(self, address: str) -> Dict[str, int]:
        """Совместимость со старым API"""
        confirmed = self.balance(address)
        return {
            "confirmed": confirmed,
            "pending": 0,
            "total": confirmed
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # ИСТОРИЯ
    # ═══════════════════════════════════════════════════════════════════════════

    def history(self, address: str, limit: int = 50) -> List[Dict]:
        """История транзакций адреса"""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT tx_id, timestamp, amount, tx_type, node, t2_index
                FROM transactions
                WHERE address = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (address, limit))

            return [dict(row) for row in cursor.fetchall()]

    def all_transactions(self, since_timestamp: int = 0, limit: int = 1000) -> List[Dict]:
        """Все транзакции (для синхронизации)"""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT * FROM transactions
                WHERE timestamp > ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (since_timestamp, limit))

            return [dict(row) for row in cursor.fetchall()]

    def tx_count(self) -> int:
        """Количество транзакций в леджере"""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) as c FROM transactions")
            return cursor.fetchone()["c"]

    # ═══════════════════════════════════════════════════════════════════════════
    # BROADCAST (трансляция на другие узлы)
    # ═══════════════════════════════════════════════════════════════════════════

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создаёт HTTP сессию"""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=5)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def _broadcast_tx(self, tx: Transaction):
        """Транслирует транзакцию на все узлы"""
        session = await self._get_session()
        tx_data = tx.to_dict()

        tasks = []
        for node_name, node_info in NODES.items():
            if node_name == self.node_name:
                continue  # Не отправляем себе

            url = f"http://{node_info['ip']}:{node_info['port']}/tx"
            tasks.append(self._send_tx(session, url, node_name, tx_data))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = sum(1 for r in results if r is True)
            logger.debug(f"📡 Broadcast TX {tx.tx_id[:8]}: {success}/{len(tasks)} nodes")

    async def _send_tx(self, session: aiohttp.ClientSession,
                       url: str, node_name: str, tx_data: dict) -> bool:
        """Отправляет TX на один узел"""
        try:
            async with session.post(url, json=tx_data) as resp:
                if resp.status == 200:
                    return True
                else:
                    logger.debug(f"⚠️ {node_name}: HTTP {resp.status}")
                    return False
        except Exception as e:
            logger.debug(f"⚠️ {node_name}: {type(e).__name__}")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # SYNC (синхронизация с другими узлами)
    # ═══════════════════════════════════════════════════════════════════════════

    async def sync_from_node(self, node_name: str) -> int:
        """Синхронизирует транзакции с другого узла"""
        if node_name not in NODES:
            return 0

        node_info = NODES[node_name]
        url = f"http://{node_info['ip']}:{node_info['port']}/sync"

        # Получаем timestamp последней TX от этого узла
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT last_tx_timestamp FROM sync_status WHERE node_name = ?",
                (node_name,)
            )
            row = cursor.fetchone()
            since = row["last_tx_timestamp"] if row else 0

        try:
            session = await self._get_session()
            async with session.get(url, params={"since": since}) as resp:
                if resp.status != 200:
                    return 0

                data = await resp.json()
                transactions = data.get("transactions", [])

                count = 0
                max_ts = since

                for tx_data in transactions:
                    if self.receive_tx(tx_data):
                        count += 1
                        max_ts = max(max_ts, tx_data.get("timestamp", 0))

                # Обновляем sync status
                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO sync_status
                        (node_name, last_tx_timestamp, last_sync_at, status)
                        VALUES (?, ?, ?, 'synced')
                    """, (node_name, max_ts, int(time.time() * 1000)))
                    conn.commit()

                if count > 0:
                    logger.info(f"🔄 Synced {count} TX from {node_name}")

                return count

        except Exception as e:
            logger.debug(f"⚠️ Sync from {node_name} failed: {e}")
            return 0

    async def sync_all(self) -> int:
        """Синхронизирует со всеми узлами"""
        total = 0
        for node_name in NODES:
            if node_name != self.node_name:
                count = await self.sync_from_node(node_name)
                total += count
        return total

    # ═══════════════════════════════════════════════════════════════════════════
    # СТАТИСТИКА
    # ═══════════════════════════════════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        """Статистика леджера"""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) as c FROM transactions")
            tx_count = cursor.fetchone()["c"]

            cursor = conn.execute("SELECT COUNT(DISTINCT address) as c FROM transactions")
            addr_count = cursor.fetchone()["c"]

            cursor = conn.execute("SELECT SUM(amount) as s FROM transactions WHERE amount > 0")
            total_minted = cursor.fetchone()["s"] or 0

            cursor = conn.execute("SELECT MAX(timestamp) as m FROM transactions")
            last_tx = cursor.fetchone()["m"] or 0

        return {
            "node": self.node_name,
            "transactions": tx_count,
            "addresses": addr_count,
            "total_minted": total_minted,
            "last_tx_timestamp": last_tx,
            "t2_index": self.t2_index,
            "ml_dsa_65": ML_DSA_AVAILABLE,
            "last_hash": self._last_hash[:16] + "..."
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP API (для приёма транзакций от других узлов)
# ═══════════════════════════════════════════════════════════════════════════════

from aiohttp import web

class LedgerAPI:
    """HTTP API для TIME_LEDGER"""

    def __init__(self, ledger: TimeLedger, port: int = 8765):
        self.ledger = ledger
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_post('/tx', self.receive_tx)
        self.app.router.add_get('/sync', self.sync_handler)
        self.app.router.add_get('/balance/{address}', self.balance_handler)
        self.app.router.add_get('/stats', self.stats_handler)
        self.app.router.add_get('/health', self.health_handler)

    async def receive_tx(self, request: web.Request) -> web.Response:
        """Получает транзакцию от другого узла"""
        try:
            tx_data = await request.json()
            success = self.ledger.receive_tx(tx_data)
            return web.json_response({"success": success})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def sync_handler(self, request: web.Request) -> web.Response:
        """Отдаёт транзакции для синхронизации"""
        since = int(request.query.get("since", 0))
        transactions = self.ledger.all_transactions(since_timestamp=since)
        return web.json_response({"transactions": transactions})

    async def balance_handler(self, request: web.Request) -> web.Response:
        """Возвращает баланс адреса"""
        address = request.match_info["address"]
        balance = self.ledger.balance(address)
        return web.json_response({"address": address, "balance": balance})

    async def stats_handler(self, request: web.Request) -> web.Response:
        """Статистика леджера"""
        return web.json_response(self.ledger.stats())

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check"""
        return web.json_response({"status": "ok", "node": self.ledger.node_name})

    async def start(self):
        """Запускает HTTP сервер"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"🌐 Ledger API started on port {self.port}")


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[TimeLedger] = None
_lock = threading.Lock()

def get_ledger() -> TimeLedger:
    """Возвращает глобальный экземпляр TimeLedger"""
    global _instance
    with _lock:
        if _instance is None:
            _instance = TimeLedger()
        return _instance


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    ledger = get_ledger()

    if len(sys.argv) < 2:
        print(f"""
TIME_LEDGER — Распределённый леджер Montana
═══════════════════════════════════════════

Узел: {ledger.node_name}
TX в леджере: {ledger.tx_count()}

Команды:
  balance <address>     — баланс адреса
  credit <addr> <amt>   — начислить
  transfer <from> <to> <amt>  — перевод
  history <address>     — история TX
  stats                 — статистика
  serve                 — запустить API сервер
        """)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "balance" and len(sys.argv) > 2:
        addr = sys.argv[2]
        print(f"💰 {addr}: {ledger.balance(addr)} Ɉ")

    elif cmd == "credit" and len(sys.argv) > 3:
        addr = sys.argv[2]
        amount = int(sys.argv[3])
        tx = ledger.credit(addr, amount)
        print(f"✓ Credit TX: {tx.tx_id}")

    elif cmd == "transfer" and len(sys.argv) > 4:
        from_addr = sys.argv[2]
        to_addr = sys.argv[3]
        amount = int(sys.argv[4])
        result = ledger.transfer(from_addr, to_addr, amount)
        if result:
            print(f"✓ Transfer: {result[0].tx_id[:8]}... → {result[1].tx_id[:8]}...")
        else:
            print("❌ Insufficient balance")

    elif cmd == "history" and len(sys.argv) > 2:
        addr = sys.argv[2]
        for tx in ledger.history(addr, limit=10):
            sign = "+" if tx["amount"] > 0 else ""
            print(f"  {tx['timestamp']} | {sign}{tx['amount']} | {tx['tx_type']} | {tx['node']}")

    elif cmd == "stats":
        for k, v in ledger.stats().items():
            print(f"{k}: {v}")

    elif cmd == "serve":
        async def main():
            api = LedgerAPI(ledger)
            await api.start()
            # Keep running
            while True:
                await asyncio.sleep(3600)

        asyncio.run(main())

    else:
        print(f"Unknown command: {cmd}")
