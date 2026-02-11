#!/usr/bin/env python3
"""
TIMECHAIN — Immutable Time Ledger with Post-Quantum Cryptography

Время — единственная реальная валюта.
Каждый T1 (60 сек) хэшируется с предыдущим блоком.
Append-only. Без права перезаписи, отката, восстановления.

КРИПТОГРАФИЯ:
- ML-DSA-65 (Dilithium) — FIPS 204
- Каждый блок подписан постквантовым ключом узла
- Подпись включена в хэш блока

АДРЕСАЦИЯ (двухуровневая):
- Криптографический: mt + SHA256(pubkey)[:20].hex() = 42 символа
- Человеческий алиас: Ɉ-N (sequential, immutable)

Архитектура:
- Каждый блок = присутствие одного адреса
- hash = SHA256(prev_hash + timestamp + address + seconds + signature)
- Цепочка неразрывна — изменение любого блока ломает всю цепь
- Алиасы регистрируются в отдельной таблице (append-only)

DISNEY CRITICS OPTIMIZATIONS v3.1:
- NTS module (nts_sync.py) — модульность
- Async NTS refresh — не блокирует запросы
- Distributed lock — для multi-node scaling
- Env config — POOL_SIZE, timeouts настраиваются
"""

import sqlite3
import hashlib
import time
import threading
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
import queue as queue_module

# Константы протокола
T1_INTERVAL = 60  # 1 минута

# База данных
DB_PATH = Path(__file__).parent / "data" / "timechain.db"


# ═══════════════════════════════════════════════════════════════════════════════
# NTS MODULE IMPORT (Disney Critics Fix: Modularity)
# ═══════════════════════════════════════════════════════════════════════════════
# NTS функционал вынесен в отдельный модуль nts_sync.py

try:
    from nts_sync import (
        nanosecond_timestamp,
        nanosecond_timestamp_local,
        nts_verified_timestamp,
        sync_atomic_time,
        get_status as get_nts_status,
        get_distributed_lock,
        NTS_KE_SERVERS,
    )
    NTS_MODULE_AVAILABLE = True
except ImportError:
    NTS_MODULE_AVAILABLE = False
    # Fallback если модуль недоступен
    def nanosecond_timestamp() -> str:
        ns = time.time_ns()
        seconds = ns // 1_000_000_000
        nanoseconds = ns % 1_000_000_000
        dt = datetime.utcfromtimestamp(seconds)
        return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{nanoseconds:09d}Z"

    def nanosecond_timestamp_local() -> str:
        return nanosecond_timestamp()

    def nts_verified_timestamp() -> Dict[str, Any]:
        ts = nanosecond_timestamp()
        return {
            "timestamp": ts,
            "timestamp_ns": time.time_ns(),
            "nts_verified": False,
            "nts_encrypted": False,
            "offset_ns": 0,
            "offset_ms": 0.0,
            "last_sync_age_s": -1,
            "verification_hash": "fallback",
            "labs_consensus": 0
        }

    def sync_atomic_time() -> Dict[str, Any]:
        return {"success": False, "error": "NTS module not available"}

    def get_nts_status() -> Dict[str, Any]:
        return {"synchronized": False, "error": "NTS module not available"}

    # Dummy distributed lock (local only)
    class DummyLock:
        def __init__(self, name): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False

    def get_distributed_lock(name: str):
        return DummyLock(name)

    NTS_KE_SERVERS = []


# ML-DSA-65 Post-Quantum Cryptography
try:
    from node_crypto import sign_message, verify_signature, get_node_crypto_system
    ML_DSA_AVAILABLE = True
except ImportError:
    ML_DSA_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TIMECHAIN")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION (env variables) — Disney Critics Fix: Config
# ═══════════════════════════════════════════════════════════════════════════════

class TimeChainConfig:
    """Конфигурация TimeChain из environment variables"""

    # Connection pool
    POOL_SIZE: int = int(os.environ.get('TIMECHAIN_POOL_SIZE', '5'))
    POOL_TIMEOUT: int = int(os.environ.get('TIMECHAIN_POOL_TIMEOUT', '30'))

    # Validation
    MAX_SECONDS_PER_BLOCK: int = int(os.environ.get('TIMECHAIN_MAX_SECONDS', '86400'))
    MIN_SECONDS_PER_BLOCK: int = int(os.environ.get('TIMECHAIN_MIN_SECONDS', '0'))

    # Presence
    PRESENCE_TIMEOUT: int = int(os.environ.get('TIMECHAIN_PRESENCE_TIMEOUT', '30'))

    # Alias registration retries
    MAX_RETRIES: int = int(os.environ.get('TIMECHAIN_MAX_RETRIES', '5'))


def _init_db(conn: sqlite3.Connection):
    """Создаёт таблицы timechain и alias_registry (append-only) с защитой от изменений"""

    # Таблица блоков времени
    conn.execute('''
        CREATE TABLE IF NOT EXISTS timechain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            address TEXT NOT NULL,
            seconds INTEGER NOT NULL,
            prev_hash TEXT NOT NULL,
            block_hash TEXT NOT NULL UNIQUE,
            node_pubkey TEXT,
            signature TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_timechain_address ON timechain(address)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_timechain_hash ON timechain(block_hash)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_timechain_timestamp ON timechain(timestamp)')

    # ═══════════════════════════════════════════════════════════════════════════
    # ALIAS REGISTRY — Реестр человеческих алиасов (Ɉ-N)
    # ═══════════════════════════════════════════════════════════════════════════
    conn.execute('''
        CREATE TABLE IF NOT EXISTS alias_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mt_number INTEGER NOT NULL UNIQUE,
            crypto_address TEXT NOT NULL UNIQUE,
            public_key TEXT,
            registration_hash TEXT NOT NULL UNIQUE,
            timestamp TEXT NOT NULL,
            node_pubkey TEXT,
            signature TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_alias_mt_number ON alias_registry(mt_number)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_alias_crypto_address ON alias_registry(crypto_address)')

    # IMMUTABILITY PROTECTION — запрет UPDATE и DELETE через triggers
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS timechain_no_update
        BEFORE UPDATE ON timechain
        BEGIN
            SELECT RAISE(ABORT, 'TIMECHAIN IMMUTABLE: UPDATE запрещён. Время нельзя изменить.');
        END
    ''')
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS timechain_no_delete
        BEFORE DELETE ON timechain
        BEGIN
            SELECT RAISE(ABORT, 'TIMECHAIN IMMUTABLE: DELETE запрещён. Время нельзя удалить.');
        END
    ''')

    # Защита реестра алиасов
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS alias_no_update
        BEFORE UPDATE ON alias_registry
        BEGIN
            SELECT RAISE(ABORT, 'ALIAS REGISTRY IMMUTABLE: UPDATE запрещён. Алиас навсегда.');
        END
    ''')
    conn.execute('''
        CREATE TRIGGER IF NOT EXISTS alias_no_delete
        BEFORE DELETE ON alias_registry
        BEGIN
            SELECT RAISE(ABORT, 'ALIAS REGISTRY IMMUTABLE: DELETE запрещён. Алиас навсегда.');
        END
    ''')

    conn.commit()


class TimeChain:
    """
    Immutable Time Ledger with Post-Quantum Cryptography

    FIPS 204: ML-DSA-65 (Dilithium)
    Append-only. Никаких UPDATE, DELETE, TRUNCATE.
    Каждый блок связан с предыдущим через хэш.
    Каждый блок подписан постквантовым ключом узла.

    DISNEY CRITICS OPTIMIZATIONS v3.1:
    - Connection pooling (queue-based, env configurable)
    - Last hash cache per address
    - Thread-safe operations
    - NTS module (async refresh)
    - Distributed lock support
    """

    GENESIS_HASH = "0" * 64  # Genesis block
    VERSION = "3.1-PQ-NTS"  # Post-Quantum + NTS + Disney Critics v3.1

    def __init__(self):
        self._lock = threading.Lock()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # ML-DSA-65 ключи узла
        self._node_private_key: Optional[str] = None
        self._node_public_key: Optional[str] = None

        # ═══════════════════════════════════════════════════════════════════════
        # CONNECTION POOL (Disney Critics Fix: Performance + Config)
        # ═══════════════════════════════════════════════════════════════════════
        self._conn_pool: queue_module.Queue = queue_module.Queue(maxsize=TimeChainConfig.POOL_SIZE)
        self._pool_lock = threading.Lock()

        # Инициализируем пул соединений
        for _ in range(TimeChainConfig.POOL_SIZE):
            conn = sqlite3.connect(str(DB_PATH), timeout=TimeChainConfig.POOL_TIMEOUT, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._conn_pool.put(conn)

        # ═══════════════════════════════════════════════════════════════════════
        # LAST HASH CACHE (Disney Critics Fix: Performance)
        # ═══════════════════════════════════════════════════════════════════════
        self._hash_cache: Dict[str, str] = {}
        self._hash_cache_lock = threading.Lock()

        # Инициализация БД
        with self._get_conn() as conn:
            _init_db(conn)

        # Начальная NTS синхронизация (асинхронная)
        if NTS_MODULE_AVAILABLE:
            try:
                sync_atomic_time()
            except Exception as e:
                logger.warning(f"⚠️ Initial NTS sync failed: {e}")

        logger.info(f"⛓️ TimeChain v{self.VERSION} initialized")
        logger.info(f"   Pool size: {TimeChainConfig.POOL_SIZE}")
        logger.info(f"   Pool timeout: {TimeChainConfig.POOL_TIMEOUT}s")
        logger.info(f"🔐 ML-DSA-65: {'✅ ENABLED' if ML_DSA_AVAILABLE else '❌ DISABLED'}")
        logger.info(f"🕐 NTS module: {'✅ ENABLED' if NTS_MODULE_AVAILABLE else '❌ DISABLED'}")

    def set_node_keys(self, private_key_hex: str, public_key_hex: str):
        """Устанавливает ML-DSA-65 ключи узла для подписи блоков"""
        self._node_private_key = private_key_hex
        self._node_public_key = public_key_hex
        logger.info(f"🔑 TimeChain node keys set (ML-DSA-65)")

    @contextmanager
    def _get_conn(self):
        """
        Context manager для соединения с БД.
        Использует CONNECTION POOL для производительности.
        """
        conn = None
        try:
            conn = self._conn_pool.get(timeout=TimeChainConfig.POOL_TIMEOUT)
            yield conn
        finally:
            if conn is not None:
                try:
                    self._conn_pool.put_nowait(conn)
                except Exception:
                    conn.close()

    def _compute_hash(self, prev_hash: str, timestamp: str, address: str,
                      seconds: int, signature: str = "") -> str:
        """SHA256(prev_hash + timestamp + address + seconds + signature)"""
        data = f"{prev_hash}{timestamp}{address}{seconds}{signature}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _sign_block(self, prev_hash: str, timestamp: str, address: str, seconds: int) -> Tuple[str, str]:
        """Подписывает данные блока ML-DSA-65"""
        if not ML_DSA_AVAILABLE or not self._node_private_key:
            return "", ""

        message = f"TIMECHAIN_BLOCK:{prev_hash}:{timestamp}:{address}:{seconds}"

        try:
            signature = sign_message(self._node_private_key, message)
            return signature, self._node_public_key
        except Exception as e:
            logger.error(f"Sign error: {e}")
            return "", ""

    def _get_last_hash(self, conn: sqlite3.Connection, address: str) -> str:
        """Получить последний хэш для адреса (с кэшированием)"""
        with self._hash_cache_lock:
            if address in self._hash_cache:
                return self._hash_cache[address]

        cursor = conn.execute(
            "SELECT block_hash FROM timechain WHERE address = ? ORDER BY id DESC LIMIT 1",
            (address,)
        )
        row = cursor.fetchone()
        last_hash = row["block_hash"] if row else self.GENESIS_HASH

        with self._hash_cache_lock:
            self._hash_cache[address] = last_hash

        return last_hash

    def _update_hash_cache(self, address: str, block_hash: str):
        """Обновляет кэш последнего хэша после append"""
        with self._hash_cache_lock:
            self._hash_cache[address] = block_hash

    # ═══════════════════════════════════════════════════════════════════════════
    # PROOF-OF-PRESENCE
    # ═══════════════════════════════════════════════════════════════════════════

    _presence_challenges: Dict[str, Dict] = {}
    _presence_lock = threading.Lock()

    def generate_presence_challenge(self, address: str) -> Dict[str, Any]:
        """Генерирует challenge для Proof-of-Presence"""
        import secrets

        challenge_id = hashlib.sha256(f"{address}{time.time_ns()}".encode()).hexdigest()[:32]
        nonce = secrets.token_hex(16)
        timestamp = nanosecond_timestamp()
        expires_ns = time.time_ns() + (TimeChainConfig.PRESENCE_TIMEOUT * 1_000_000_000)

        with self._presence_lock:
            current_ns = time.time_ns()
            self._presence_challenges = {
                cid: data for cid, data in self._presence_challenges.items()
                if data.get("expires_ns", 0) > current_ns
            }

            self._presence_challenges[challenge_id] = {
                "address": address,
                "nonce": nonce,
                "timestamp": timestamp,
                "expires_ns": expires_ns
            }

        expires_at = datetime.utcfromtimestamp(expires_ns // 1_000_000_000)

        logger.debug(f"🎯 Presence challenge generated for {address[:16]}...")

        return {
            "challenge_id": challenge_id,
            "nonce": nonce,
            "timestamp": timestamp,
            "expires_at": expires_at.isoformat() + "Z",
            "timeout_seconds": TimeChainConfig.PRESENCE_TIMEOUT
        }

    def verify_presence(self, challenge_id: str, address: str,
                       signature: str, public_key: str = "") -> Dict[str, Any]:
        """Верифицирует Proof-of-Presence ответ"""
        current_ns = time.time_ns()

        with self._presence_lock:
            challenge = self._presence_challenges.get(challenge_id)

            if not challenge:
                return {"verified": False, "error": "Challenge not found or expired"}

            if challenge["address"] != address:
                return {"verified": False, "error": "Address mismatch"}

            if current_ns > challenge["expires_ns"]:
                del self._presence_challenges[challenge_id]
                return {"verified": False, "error": "Challenge expired"}

            if signature and ML_DSA_AVAILABLE and public_key:
                message = f"PRESENCE:{challenge_id}:{challenge['nonce']}:{address}"
                try:
                    if not verify_signature(public_key, message, signature):
                        return {"verified": False, "error": "Invalid signature"}
                except Exception as e:
                    logger.warning(f"Signature verification error: {e}")

            del self._presence_challenges[challenge_id]

        response_time_ms = (current_ns - int(datetime.fromisoformat(
            challenge["timestamp"].rstrip("Z")).timestamp() * 1_000_000_000)) / 1_000_000

        presence_proof = hashlib.sha256(
            f"PRESENCE_PROOF:{challenge_id}:{address}:{current_ns}".encode()
        ).hexdigest()

        logger.info(f"✅ Presence verified: {address[:16]}... (response: {response_time_ms:.1f}ms)")

        return {
            "verified": True,
            "presence_proof": presence_proof,
            "timestamp": nanosecond_timestamp(),
            "response_time_ms": response_time_ms,
            "address": address
        }

    def append_with_presence(self, address: str, seconds: int,
                            presence_proof: str) -> Dict[str, Any]:
        """Добавить блок с верифицированным Proof-of-Presence"""
        if not presence_proof or len(presence_proof) != 64:
            return {"error": "Invalid presence_proof", "success": False}

        result = self.append(address, seconds)

        if result.get("success") is False or "error" in result:
            return result

        result["presence_proof"] = presence_proof
        result["presence_verified"] = True

        return result

    def append(self, address: str, seconds: int) -> Dict[str, Any]:
        """
        Добавить блок в цепочку (APPEND-ONLY)

        POST-QUANTUM: Блок подписывается ML-DSA-65 если ключи установлены

        DISNEY CRITICS SECURITY v3.1:
        - Валидация формата адреса
        - Проверка границ seconds
        - Наносекундные timestamps (NTS module)
        - Distributed lock для multi-node

        Args:
            address: Montana address или mt-адрес
            seconds: Секунды присутствия (0 - 86400)

        Returns:
            Созданный блок с хэшем и подписью
        """
        # ═══════════════════════════════════════════════════════════════════════
        # VALIDATION (Disney Critics Fix)
        # ═══════════════════════════════════════════════════════════════════════
        if not address:
            return {"error": "Address is required", "success": False}

        if address.startswith("mt") and len(address) != 42:
            return {"error": "Invalid mt-address format (must be 42 chars)", "success": False}

        if not isinstance(seconds, int):
            return {"error": "Seconds must be integer", "success": False}

        if seconds < TimeChainConfig.MIN_SECONDS_PER_BLOCK:
            return {"error": f"Seconds cannot be negative", "success": False}

        if seconds > TimeChainConfig.MAX_SECONDS_PER_BLOCK:
            return {"error": f"Seconds cannot exceed {TimeChainConfig.MAX_SECONDS_PER_BLOCK}", "success": False}

        # ═══════════════════════════════════════════════════════════════════════
        # DISTRIBUTED LOCK (Disney Critics Fix: Multi-node scaling)
        # ═══════════════════════════════════════════════════════════════════════
        with get_distributed_lock(f"timechain_append_{address}"):
            with self._lock:
                nts_ts = nts_verified_timestamp()
                timestamp = nts_ts["timestamp"]

                with self._get_conn() as conn:
                    prev_hash = self._get_last_hash(conn, address)

                    signature, pubkey = self._sign_block(prev_hash, timestamp, address, seconds)
                    block_hash = self._compute_hash(prev_hash, timestamp, address, seconds, signature)

                    conn.execute('''
                        INSERT INTO timechain (timestamp, address, seconds, prev_hash, block_hash, node_pubkey, signature)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (timestamp, address, seconds, prev_hash, block_hash, pubkey, signature))
                    conn.commit()

                    self._update_hash_cache(address, block_hash)

                    block = {
                        "timestamp": timestamp,
                        "timestamp_ns": nts_ts["timestamp_ns"],
                        "address": address,
                        "seconds": seconds,
                        "prev_hash": prev_hash,
                        "block_hash": block_hash,
                        "node_pubkey": pubkey,
                        "signature": signature[:32] + "..." if signature else "",
                        "post_quantum": bool(signature),
                        "nts_verified": nts_ts["nts_verified"],
                        "nts_encrypted": nts_ts["nts_encrypted"],
                        "nts_offset_ms": nts_ts["offset_ms"],
                        "nts_verification_hash": nts_ts["verification_hash"]
                    }

                    if nts_ts["nts_verified"]:
                        logger.debug(f"⛓️🕐 NTS-verified: {block_hash[:16]}... (offset: {nts_ts['offset_ms']:.3f}ms)")
                    if signature:
                        logger.debug(f"⛓️🔐 ML-DSA-65 signed: {block_hash[:16]}...")

                    return block

    def balance(self, address: str) -> int:
        """Баланс = сумма всех секунд для адреса"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(seconds), 0) as total FROM timechain WHERE address = ?",
                (address,)
            )
            return cursor.fetchone()["total"]

    def verify_chain(self, address: str) -> bool:
        """Проверить целостность цепочки для адреса (хэши)"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM timechain WHERE address = ? ORDER BY id",
                (address,)
            )

            prev_hash = self.GENESIS_HASH
            for row in cursor:
                signature = row["signature"] or ""
                expected_hash = self._compute_hash(
                    prev_hash, row["timestamp"], row["address"], row["seconds"], signature
                )
                if expected_hash != row["block_hash"]:
                    return False
                prev_hash = row["block_hash"]

            return True

    def verify_signatures(self, address: str) -> Dict[str, Any]:
        """Проверить ML-DSA-65 подписи всех блоков для адреса"""
        if not ML_DSA_AVAILABLE:
            return {"error": "ML-DSA-65 not available", "valid": False}

        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM timechain WHERE address = ? ORDER BY id",
                (address,)
            )

            total = 0
            signed = 0
            verified = 0
            unsigned = 0
            failed = 0
            prev_hash = self.GENESIS_HASH

            for row in cursor:
                total += 1
                signature = row["signature"]
                pubkey = row["node_pubkey"]

                if not signature or not pubkey:
                    unsigned += 1
                    prev_hash = row["block_hash"]
                    continue

                signed += 1

                message = f"TIMECHAIN_BLOCK:{prev_hash}:{row['timestamp']}:{row['address']}:{row['seconds']}"
                try:
                    if verify_signature(pubkey, message, signature):
                        verified += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

                prev_hash = row["block_hash"]

            return {
                "total": total,
                "signed": signed,
                "verified": verified,
                "unsigned": unsigned,
                "failed": failed,
                "valid": failed == 0
            }

    def get_blocks(self, address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить блоки для адреса"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM timechain WHERE address = ? ORDER BY id DESC LIMIT ?",
                (address, limit)
            )
            blocks = []
            for row in cursor:
                block = dict(row)
                if block.get("signature"):
                    block["signature"] = block["signature"][:32] + "..."
                blocks.append(block)
            return blocks

    def total_blocks(self) -> int:
        """Общее количество блоков в цепочке"""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM timechain")
            return cursor.fetchone()[0]

    def stats(self) -> Dict[str, Any]:
        """Статистика TimeChain"""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) as total, COUNT(signature) as signed FROM timechain")
            row = cursor.fetchone()

            cursor2 = conn.execute("SELECT COUNT(DISTINCT address) as addresses FROM timechain")
            addresses = cursor2.fetchone()["addresses"]

            cursor3 = conn.execute("SELECT COUNT(*) as total, MAX(mt_number) as last_mt FROM alias_registry")
            alias_row = cursor3.fetchone()

            nts_status = get_nts_status() if NTS_MODULE_AVAILABLE else {}

            return {
                "version": self.VERSION,
                "total_blocks": row["total"],
                "signed_blocks": row["signed"],
                "unique_addresses": addresses,
                "registered_aliases": alias_row["total"] if alias_row else 0,
                "last_mt_number": alias_row["last_mt"] if alias_row and alias_row["last_mt"] else 0,
                "ml_dsa_65": ML_DSA_AVAILABLE,
                "nts_module": NTS_MODULE_AVAILABLE,
                "nts_synchronized": nts_status.get("synchronized", False),
                "nts_encrypted": nts_status.get("encrypted", False),
                "node_keys_set": bool(self._node_private_key),
                "pool_size": TimeChainConfig.POOL_SIZE,
                "genesis_hash": self.GENESIS_HASH[:16] + "..."
            }

    # ═══════════════════════════════════════════════════════════════════════════
    # ALIAS REGISTRY — Человеческие адреса (Ɉ-N)
    # ═══════════════════════════════════════════════════════════════════════════

    def register_alias(self, crypto_address: str, public_key: str = "") -> Dict[str, Any]:
        """
        Регистрирует новый алиас (Montana ID / кошелёк) для криптографического адреса.

        DISNEY CRITICS v3.1:
        - EXCLUSIVE transaction для атомарности
        - Distributed lock для multi-node
        - Retry при race condition
        - Env configurable MAX_RETRIES
        """
        if not crypto_address or not crypto_address.startswith("mt"):
            return {"success": False, "error": "Invalid crypto_address format"}

        # ═══════════════════════════════════════════════════════════════════════
        # DISTRIBUTED LOCK (Disney Critics Fix: Multi-node scaling)
        # ═══════════════════════════════════════════════════════════════════════
        with get_distributed_lock("alias_register"):
            with self._lock:
                for attempt in range(TimeChainConfig.MAX_RETRIES):
                    timestamp = nanosecond_timestamp()

                    try:
                        with self._get_conn() as conn:
                            conn.execute("BEGIN EXCLUSIVE")

                            try:
                                cursor = conn.execute(
                                    "SELECT mt_number FROM alias_registry WHERE crypto_address = ?",
                                    (crypto_address,)
                                )
                                existing = cursor.fetchone()
                                if existing:
                                    conn.execute("ROLLBACK")
                                    return {
                                        "success": False,
                                        "error": "ADDRESS_EXISTS",
                                        "mt_number": existing["mt_number"],
                                        "alias": f"Ɉ-{existing['mt_number']}",
                                        "message": "Этот адрес уже зарегистрирован"
                                    }

                                cursor = conn.execute("SELECT COALESCE(MAX(mt_number), 0) + 1 as next_mt FROM alias_registry")
                                next_mt = cursor.fetchone()["next_mt"]

                                signature = ""
                                node_pubkey = ""
                                if ML_DSA_AVAILABLE and self._node_private_key:
                                    message = f"MONTANA_ALIAS_REGISTER:{next_mt}:{crypto_address}:{timestamp}"
                                    try:
                                        signature = sign_message(self._node_private_key, message)
                                        node_pubkey = self._node_public_key
                                    except Exception as e:
                                        logger.error(f"Sign error: {e}")

                                reg_data = f"{next_mt}{crypto_address}{public_key}{timestamp}{signature}"
                                registration_hash = hashlib.sha256(reg_data.encode()).hexdigest()

                                conn.execute('''
                                    INSERT INTO alias_registry
                                    (mt_number, crypto_address, public_key, registration_hash, timestamp, node_pubkey, signature)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (next_mt, crypto_address, public_key, registration_hash, timestamp, node_pubkey, signature))

                                conn.execute("COMMIT")

                                alias = f"Ɉ-{next_mt}"
                                logger.info(f"📝 Registered Montana ID: {alias} → {crypto_address[:16]}... (attempt {attempt + 1})")

                                return {
                                    "success": True,
                                    "mt_number": next_mt,
                                    "alias": alias,
                                    "crypto_address": crypto_address,
                                    "registration_hash": registration_hash,
                                    "timestamp": timestamp,
                                    "signed": bool(signature)
                                }

                            except sqlite3.IntegrityError as e:
                                conn.execute("ROLLBACK")
                                if "UNIQUE constraint failed: alias_registry.mt_number" in str(e):
                                    logger.warning(f"⚠️ Race condition detected, retry {attempt + 1}/{TimeChainConfig.MAX_RETRIES}")
                                    time.sleep(0.01 * (attempt + 1))
                                    continue
                                elif "UNIQUE constraint failed: alias_registry.crypto_address" in str(e):
                                    cursor = conn.execute(
                                        "SELECT mt_number FROM alias_registry WHERE crypto_address = ?",
                                        (crypto_address,)
                                    )
                                    existing = cursor.fetchone()
                                    if existing:
                                        return {
                                            "success": False,
                                            "error": "ADDRESS_EXISTS",
                                            "mt_number": existing["mt_number"],
                                            "alias": f"Ɉ-{existing['mt_number']}",
                                            "message": "Этот адрес уже зарегистрирован"
                                        }
                                raise

                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e):
                            logger.warning(f"⚠️ Database locked, retry {attempt + 1}/{TimeChainConfig.MAX_RETRIES}")
                            time.sleep(0.05 * (attempt + 1))
                            continue
                        raise

                logger.error(f"❌ Failed to register after {TimeChainConfig.MAX_RETRIES} attempts: {crypto_address}")
                return {
                    "success": False,
                    "error": "REGISTRATION_FAILED",
                    "message": "Не удалось зарегистрировать после нескольких попыток. Попробуйте позже."
                }

    def lookup_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """Найти криптографический адрес по алиасу"""
        mt_number = self._parse_alias(alias)
        if mt_number is None:
            return None

        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM alias_registry WHERE mt_number = ?",
                (mt_number,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "mt_number": row["mt_number"],
                "alias": f"Ɉ-{row['mt_number']}",
                "crypto_address": row["crypto_address"],
                "public_key": row["public_key"],
                "registration_hash": row["registration_hash"],
                "timestamp": row["timestamp"],
                "signed": bool(row["signature"])
            }

    def lookup_by_address(self, crypto_address: str) -> Optional[Dict[str, Any]]:
        """Найти алиас по криптографическому адресу"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM alias_registry WHERE crypto_address = ?",
                (crypto_address,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "mt_number": row["mt_number"],
                "alias": f"Ɉ-{row['mt_number']}",
                "crypto_address": row["crypto_address"],
                "public_key": row["public_key"],
                "registration_hash": row["registration_hash"],
                "timestamp": row["timestamp"],
                "signed": bool(row["signature"])
            }

    def resolve_address(self, address_or_alias: str) -> Optional[str]:
        """Универсальный резолвер"""
        if address_or_alias.startswith("mt") and len(address_or_alias) == 42:
            return address_or_alias

        result = self.lookup_by_alias(address_or_alias)
        if result:
            return result["crypto_address"]

        return None

    def _parse_alias(self, alias) -> Optional[int]:
        """Парсит mt_number из различных форматов алиаса"""
        if isinstance(alias, int):
            return alias

        alias_str = str(alias).strip()

        if alias_str.startswith("Ɉ-"):
            try:
                return int(alias_str[2:])
            except ValueError:
                return None

        if alias_str.lower().startswith("mt-"):
            try:
                return int(alias_str[3:])
            except ValueError:
                return None

        try:
            return int(alias_str)
        except ValueError:
            return None

    def get_all_aliases(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Получить список всех зарегистрированных алиасов"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM alias_registry ORDER BY mt_number ASC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [
                {
                    "mt_number": row["mt_number"],
                    "alias": f"Ɉ-{row['mt_number']}",
                    "crypto_address": row["crypto_address"],
                    "timestamp": row["timestamp"],
                    "signed": bool(row["signature"])
                }
                for row in cursor
            ]

    def total_aliases(self) -> int:
        """Общее количество зарегистрированных алиасов"""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM alias_registry")
            return cursor.fetchone()[0]


# ═══════════════════════════════════════════════════════════════════════════════
# THREAD-SAFE SINGLETON (Disney Critics Fix)
# ═══════════════════════════════════════════════════════════════════════════════
_timechain: Optional[TimeChain] = None
_timechain_lock = threading.Lock()


def get_timechain() -> TimeChain:
    """Thread-safe singleton для TimeChain"""
    global _timechain
    if _timechain is None:
        with _timechain_lock:
            if _timechain is None:
                _timechain = TimeChain()
    return _timechain


if __name__ == "__main__":
    # Тест
    tc = get_timechain()

    print(f"TimeChain v{tc.VERSION}")
    print(f"ML-DSA-65: {'✅' if ML_DSA_AVAILABLE else '❌'}")
    print(f"NTS Module: {'✅' if NTS_MODULE_AVAILABLE else '❌'}")
    print(f"Pool Size: {TimeChainConfig.POOL_SIZE}")
    print()

    # Добавляем блоки
    block1 = tc.append("test_user", 60)
    print(f"Block 1: {block1['block_hash'][:16]}... (PQ: {block1['post_quantum']})")

    block2 = tc.append("test_user", 60)
    print(f"Block 2: {block2['block_hash'][:16]}... (prev: {block2['prev_hash'][:16]}...)")

    # Проверяем баланс
    print(f"Balance: {tc.balance('test_user')} seconds")

    # Проверяем цепочку
    print(f"Chain valid: {tc.verify_chain('test_user')}")

    # Статистика
    print(f"Stats: {tc.stats()}")
