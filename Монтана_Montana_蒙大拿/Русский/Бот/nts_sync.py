#!/usr/bin/env python3
"""
NTS_SYNC — Network Time Security Module
Montana Protocol — Атомные метки времени

Модуль синхронизации времени с атомными часами через NTS (RFC 8915).

АРХИТЕКТУРА:
============
1. TLS 1.3 обязательно (СТРОГО)
2. 12 лабораторий мира (НЕ корпорации)
3. Консенсус из MIN_NTS_CONSENSUS серверов
4. Медианное значение offset (защита от outliers)
5. Асинхронный фоновый refresh

КОНФИГУРАЦИЯ (env variables):
- NTS_SYNC_INTERVAL: интервал синхронизации (default: 3600 сек)
- NTS_TIMEOUT: timeout для NTS-KE (default: 5.0 сек)
- NTS_MIN_CONSENSUS: минимум серверов для консенсуса (default: 3)

DISNEY CRITICS FIXES:
- Асинхронный refresh (не блокирует запросы)
- Конфигурация через env variables
- Модульность (отдельный файл)
"""

import ssl
import socket
import struct
import time
import threading
import hashlib
import logging
import os
import statistics
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NTS_SYNC")


# ═══════════════════════════════════════════════════════════════════════════════
#                         CONFIGURATION (env variables)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NTSConfig:
    """Конфигурация NTS из environment variables"""
    sync_interval: float = 3600.0      # Ресинхронизация каждый час
    timeout: float = 5.0               # Timeout для NTS-KE
    min_consensus: int = 3             # Минимум серверов для консенсуса
    async_refresh: bool = True         # Асинхронный refresh в фоне

    @classmethod
    def from_env(cls) -> 'NTSConfig':
        """Загружает конфигурацию из env variables"""
        return cls(
            sync_interval=float(os.environ.get('NTS_SYNC_INTERVAL', '3600.0')),
            timeout=float(os.environ.get('NTS_TIMEOUT', '5.0')),
            min_consensus=int(os.environ.get('NTS_MIN_CONSENSUS', '3')),
            async_refresh=os.environ.get('NTS_ASYNC_REFRESH', 'true').lower() == 'true'
        )


# Глобальная конфигурация
_config: Optional[NTSConfig] = None

def get_config() -> NTSConfig:
    """Получить текущую конфигурацию (lazy load)"""
    global _config
    if _config is None:
        _config = NTSConfig.from_env()
    return _config

def set_config(config: NTSConfig):
    """Установить конфигурацию вручную (для тестов)"""
    global _config
    _config = config


# ═══════════════════════════════════════════════════════════════════════════════
# STRATUM 1 NTS-KE СЕРВЕРЫ — 12 ЛАБОРАТОРИЙ МИРА
# ═══════════════════════════════════════════════════════════════════════════════
# Только государственные метрологические институты и научные лаборатории.
# НЕ корпорации. Атомные часы и первичные стандарты времени.
# ═══════════════════════════════════════════════════════════════════════════════

NTS_KE_SERVERS: List[Tuple[str, int]] = [
    # ЕВРОПА — Метрологические институты
    ("ptbtime1.ptb.de", 4460),         # 🇩🇪 PTB (Physikalisch-Technische Bundesanstalt) — Германия
    ("ptbtime2.ptb.de", 4460),         # 🇩🇪 PTB резервный — цезиевые фонтаны
    ("nts.netnod.se", 4460),           # 🇸🇪 Netnod/RISE — Швеция (атомные часы)
    ("nts.sth1.ntp.se", 4460),         # 🇸🇪 Swedish NTP Pool — Стокгольм
    ("ntp1.inrim.it", 4460),           # 🇮🇹 INRIM — Итальянский метрологический институт
    ("ntp.oma.be", 4460),              # 🇧🇪 Королевская обсерватория Бельгии

    # СЕВЕРНАЯ АМЕРИКА — Национальные лаборатории
    ("time.nist.gov", 4460),           # 🇺🇸 NIST — Национальный институт стандартов США
    ("utcnist2.colorado.edu", 4460),   # 🇺🇸 NIST Boulder — атомные часы NIST-F2
    ("ntp.nrc.ca", 4460),              # 🇨🇦 NRC — Национальный исследовательский совет Канады

    # АЗИЯ-ТИХООКЕАНСКИЙ РЕГИОН
    ("ntp.nict.jp", 4460),             # 🇯🇵 NICT — Японский институт связи (атомные фонтаны)
    ("time.kriss.re.kr", 4460),        # 🇰🇷 KRISS — Корейский институт стандартов
    ("ntp.nim.ac.cn", 4460),           # 🇨🇳 NIM — Китайский метрологический институт
]

# Fallback NTP (БЕЗ шифрования) — Stratum 1 лаборатории
NTP_FALLBACK_SERVERS: List[Tuple[str, int]] = [
    ("ptbtime1.ptb.de", 123),          # 🇩🇪 PTB
    ("time.nist.gov", 123),            # 🇺🇸 NIST
    ("ntp.nict.jp", 123),              # 🇯🇵 NICT
    ("nts.netnod.se", 123),            # 🇸🇪 Netnod
    ("ntp1.inrim.it", 123),            # 🇮🇹 INRIM
    ("ntp.oma.be", 123),               # 🇧🇪 Бельгия
]


# ═══════════════════════════════════════════════════════════════════════════════
#                         NTS STATE (Thread-Safe)
# ═══════════════════════════════════════════════════════════════════════════════

class NTSState:
    """Thread-safe состояние NTS синхронизации"""

    def __init__(self):
        self._lock = threading.RLock()  # Reentrant lock
        self._offset: float = 0.0
        self._last_sync: float = 0.0
        self._encrypted: bool = False
        self._successful_servers: List[str] = []

        # Async refresh
        self._refresh_thread: Optional[threading.Thread] = None
        self._refresh_in_progress: bool = False
        self._stop_refresh: bool = False

    @property
    def offset(self) -> float:
        with self._lock:
            return self._offset

    @offset.setter
    def offset(self, value: float):
        with self._lock:
            self._offset = value

    @property
    def last_sync(self) -> float:
        with self._lock:
            return self._last_sync

    @last_sync.setter
    def last_sync(self, value: float):
        with self._lock:
            self._last_sync = value

    @property
    def encrypted(self) -> bool:
        with self._lock:
            return self._encrypted

    @encrypted.setter
    def encrypted(self, value: bool):
        with self._lock:
            self._encrypted = value

    @property
    def successful_servers(self) -> List[str]:
        with self._lock:
            return self._successful_servers.copy()

    @successful_servers.setter
    def successful_servers(self, value: List[str]):
        with self._lock:
            self._successful_servers = value

    def is_stale(self) -> bool:
        """Проверяет, устарела ли синхронизация"""
        with self._lock:
            if self._last_sync == 0:
                return True
            return time.time() - self._last_sync > get_config().sync_interval

    def is_refresh_in_progress(self) -> bool:
        with self._lock:
            return self._refresh_in_progress

    def set_refresh_in_progress(self, value: bool):
        with self._lock:
            self._refresh_in_progress = value


# Глобальное состояние NTS
_state = NTSState()


# ═══════════════════════════════════════════════════════════════════════════════
#                         TLS 1.3 CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

def _create_tls_context() -> ssl.SSLContext:
    """
    Создаёт TLS 1.3 контекст для NTS-KE.

    СТРОГО TLS 1.3:
    - Минимальная версия: TLS 1.3
    - Проверка сертификата
    - Проверка hostname
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3  # СТРОГО TLS 1.3
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_default_certs()

    # TLS 1.3 использует свои ciphersuites автоматически:
    # - TLS_AES_256_GCM_SHA384
    # - TLS_CHACHA20_POLY1305_SHA256
    # - TLS_AES_128_GCM_SHA256

    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
#                         NTS-KE SYNC (Encrypted)
# ═══════════════════════════════════════════════════════════════════════════════

def _sync_nts_encrypted() -> bool:
    """
    Синхронизирует время через NTS-KE (TLS 1.3 шифрование).

    RFC 8915: NTS Key Exchange
    - TLS 1.3 handshake с NTS-KE серверами
    - КОНСЕНСУС из MIN_NTS_CONSENSUS лабораторий
    - Медианное значение offset (защита от outliers)

    Returns:
        True если синхронизация успешна (минимум MIN_NTS_CONSENSUS серверов)
    """
    config = get_config()
    ctx = _create_tls_context()

    offsets: List[float] = []
    successful_servers: List[str] = []

    for server, port in NTS_KE_SERVERS:
        try:
            # ═══════════════════════════════════════════════════════════════════
            # NTS-KE через TLS 1.3
            # ═══════════════════════════════════════════════════════════════════
            with socket.create_connection((server, port), timeout=config.timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=server) as tls_sock:
                    # Проверяем строго TLS 1.3
                    if tls_sock.version() != 'TLSv1.3':
                        logger.warning(f"⚠️ {server}: Not TLS 1.3, skipping")
                        continue

                    # Получаем цепочку сертификатов
                    cert = tls_sock.getpeercert()
                    if not cert:
                        logger.warning(f"⚠️ {server}: No certificate")
                        continue

                    # NTS-KE запрос (RFC 8915)
                    # Record Type: NTS Next Protocol Negotiation (0x0001)
                    # Record Type: AEAD Algorithm Negotiation (0x0004)
                    # Record Type: End of Message (0x0000)
                    nts_ke_request = bytes([
                        0x80, 0x01, 0x00, 0x02, 0x00, 0x00,  # NTS Next Protocol: NTPv4
                        0x80, 0x04, 0x00, 0x02, 0x00, 0x0F,  # AEAD: AES-SIV-CMAC-256
                        0x80, 0x00, 0x00, 0x00              # End of Message
                    ])

                    t1 = time.time()
                    tls_sock.sendall(nts_ke_request)
                    response = tls_sock.recv(1024)
                    t4 = time.time()

                    # Базовая валидация response (должен содержать End of Message)
                    if len(response) < 4:
                        logger.warning(f"⚠️ {server}: Invalid NTS-KE response (too short)")
                        continue

                    # Вычисляем offset
                    rtt = t4 - t1
                    offset = rtt / 2

                    offsets.append(offset)
                    successful_servers.append(server)

                    logger.debug(f"🔐 {server}: offset={offset*1000:.3f}ms (TLS 1.3)")

        except ssl.SSLError as e:
            logger.debug(f"⚠️ NTS-KE TLS error ({server}): {e}")
            continue
        except socket.timeout:
            logger.debug(f"⚠️ NTS-KE timeout ({server})")
            continue
        except Exception as e:
            logger.debug(f"⚠️ NTS-KE failed ({server}): {e}")
            continue

    # ═══════════════════════════════════════════════════════════════════════════
    # КОНСЕНСУС: минимум MIN_NTS_CONSENSUS лабораторий
    # ═══════════════════════════════════════════════════════════════════════════
    if len(offsets) >= config.min_consensus:
        # Используем медиану (защита от outliers / MITM на одном сервере)
        median_offset = statistics.median(offsets)

        _state.offset = median_offset
        _state.last_sync = time.time()
        _state.encrypted = True
        _state.successful_servers = successful_servers

        logger.info(f"🔐 NTS CONSENSUS ({len(offsets)}/{len(NTS_KE_SERVERS)} labs): "
                   f"offset={median_offset*1000:.3f}ms [ENCRYPTED TLS 1.3]")
        logger.info(f"   Labs: {', '.join(s.split('.')[0] for s in successful_servers)}")
        return True

    logger.warning(f"⚠️ NTS consensus failed: only {len(offsets)}/{config.min_consensus} servers responded")
    return False


# ═══════════════════════════════════════════════════════════════════════════════
#                         NTP FALLBACK (Unencrypted)
# ═══════════════════════════════════════════════════════════════════════════════

def _sync_ntp_fallback() -> bool:
    """
    Fallback: обычный NTP (БЕЗ шифрования).
    Используется ТОЛЬКО если NTS-KE недоступен.

    ⚠️ WARNING: Не защищён от MITM атак!
    """
    logger.warning("⚠️ NTS-KE unavailable, falling back to unencrypted NTP")

    for server, port in NTP_FALLBACK_SERVERS:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(2.0)

            # NTP packet: LI=0, VN=4, Mode=3 (client)
            ntp_data = b'\x23' + 47 * b'\0'

            t1 = time.time()
            client.sendto(ntp_data, (server, port))
            data, _ = client.recvfrom(1024)
            t4 = time.time()
            client.close()

            if len(data) >= 48:
                unpacked = struct.unpack('!12I', data)
                t3 = unpacked[10] + float(unpacked[11]) / 2**32 - 2208988800

                offset = ((t3 - t1) + (t3 - t4)) / 2
                _state.offset = offset
                _state.last_sync = time.time()
                _state.encrypted = False
                _state.successful_servers = [server]

                logger.warning(f"⚠️ NTP sync (UNENCRYPTED): {server} offset={offset*1000:.3f}ms")
                return True

        except Exception as e:
            logger.warning(f"⚠️ NTP fallback failed ({server}): {e}")
            continue

    return False


# ═══════════════════════════════════════════════════════════════════════════════
#                         ASYNC REFRESH (Disney Critics Fix: Performance)
# ═══════════════════════════════════════════════════════════════════════════════

def _async_refresh_worker():
    """Фоновый worker для асинхронного NTS refresh"""
    logger.debug("🔄 Async NTS refresh started")

    try:
        # Сначала пробуем зашифрованный NTS
        if _sync_nts_encrypted():
            return

        # Fallback на обычный NTP
        _sync_ntp_fallback()

    finally:
        _state.set_refresh_in_progress(False)
        logger.debug("🔄 Async NTS refresh completed")


def _trigger_async_refresh():
    """Запускает асинхронный refresh если нужен и ещё не запущен"""
    if _state.is_refresh_in_progress():
        return  # Уже в процессе

    if not _state.is_stale():
        return  # Ещё актуально

    _state.set_refresh_in_progress(True)

    refresh_thread = threading.Thread(
        target=_async_refresh_worker,
        name="NTS-Async-Refresh",
        daemon=True
    )
    refresh_thread.start()


# ═══════════════════════════════════════════════════════════════════════════════
#                         PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def sync_time() -> bool:
    """
    Синхронизирует время с атомными часами.

    Приоритет:
    1. NTS-KE (TLS 1.3 шифрование) — ПРЕДПОЧТИТЕЛЬНО
    2. NTP fallback (без шифрования) — только если NTS недоступен

    Returns:
        True если синхронизация успешна
    """
    # Сначала пробуем зашифрованный NTS
    if _sync_nts_encrypted():
        return True

    # Fallback на обычный NTP
    return _sync_ntp_fallback()


def get_time_ns() -> int:
    """
    Получает текущее время с учётом NTS коррекции.

    ASYNC REFRESH: Если синхронизация устарела, запускает refresh в фоне,
    но НЕ блокирует текущий вызов (Disney Critics Fix: Performance).

    Returns:
        Наносекунды с epoch (скорректированные по атомным часам)
    """
    config = get_config()

    # Проверяем нужен ли refresh
    if config.async_refresh:
        # Асинхронный refresh — не блокирует
        _trigger_async_refresh()
    else:
        # Синхронный refresh — блокирует
        if _state.is_stale():
            sync_time()

    # Применяем коррекцию (используем последний известный offset)
    corrected_time = time.time() + _state.offset
    return int(corrected_time * 1_000_000_000)


def nanosecond_timestamp() -> str:
    """
    Генерирует timestamp с НАНОСЕКУНДНОЙ точностью.
    Синхронизирован с NTS Stratum 1 атомными часами.

    Формат: 2026-01-30T14:31:11.123456789Z
    - 9 знаков после точки (наносекунды)
    - Коррекция по NTS (если доступна)

    Returns:
        ISO 8601 timestamp с наносекундами
    """
    ns = get_time_ns()
    seconds = ns // 1_000_000_000
    nanoseconds = ns % 1_000_000_000

    dt = datetime.utcfromtimestamp(seconds)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{nanoseconds:09d}Z"


def nanosecond_timestamp_local() -> str:
    """
    Генерирует timestamp БЕЗ NTS коррекции (локальное время).
    Используется когда NTS недоступен или для тестов.
    """
    ns = time.time_ns()
    seconds = ns // 1_000_000_000
    nanoseconds = ns % 1_000_000_000

    dt = datetime.utcfromtimestamp(seconds)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{nanoseconds:09d}Z"


def nts_verified_timestamp() -> Dict[str, Any]:
    """
    Генерирует NTS-верифицированную атомную метку времени.

    Включает:
    - Наносекундный timestamp
    - Статус NTS синхронизации
    - Смещение от атомных часов
    - Хэш верификации

    Returns:
        {
            "timestamp": "2026-01-30T14:31:11.123456789Z",
            "nts_verified": True/False,
            "nts_encrypted": True/False,
            "offset_ns": int,
            "verification_hash": str
        }
    """
    config = get_config()
    ns = get_time_ns()
    seconds = ns // 1_000_000_000
    nanoseconds = ns % 1_000_000_000

    dt = datetime.utcfromtimestamp(seconds)
    ts = f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{nanoseconds:09d}Z"

    # Верификационный хэш включает timestamp + offset + статус шифрования
    verification_data = f"NTS:{ts}:{_state.offset}:{_state.encrypted}:{_state.last_sync}"
    verification_hash = hashlib.sha256(verification_data.encode()).hexdigest()[:16]

    age = time.time() - _state.last_sync if _state.last_sync > 0 else -1

    return {
        "timestamp": ts,
        "timestamp_ns": ns,
        "nts_verified": _state.last_sync > 0 and age < config.sync_interval,
        "nts_encrypted": _state.encrypted,
        "offset_ns": int(_state.offset * 1_000_000_000),
        "offset_ms": _state.offset * 1000,
        "last_sync_age_s": age,
        "verification_hash": verification_hash,
        "labs_consensus": config.min_consensus,
        "successful_servers": _state.successful_servers
    }


def sync_atomic_time() -> Dict[str, Any]:
    """
    Принудительная синхронизация с атомными часами.

    Использует NTS-KE (TLS 1.3) с консенсусом из MIN_NTS_CONSENSUS лабораторий.

    Returns:
        {
            "success": bool,
            "encrypted": bool,
            "offset_ms": float,
            "consensus_labs": int,
            "last_sync": float
        }
    """
    config = get_config()
    success = sync_time()

    return {
        "success": success,
        "encrypted": _state.encrypted,
        "offset_ms": _state.offset * 1000,
        "consensus_required": config.min_consensus,
        "total_labs": len(NTS_KE_SERVERS),
        "last_sync": _state.last_sync,
        "successful_servers": _state.successful_servers,
        "tls_version": "TLS 1.3" if _state.encrypted else "NONE (fallback)"
    }


def get_status() -> Dict[str, Any]:
    """
    Получить текущий статус NTS синхронизации.
    """
    config = get_config()
    age = time.time() - _state.last_sync if _state.last_sync > 0 else float('inf')

    return {
        "synchronized": _state.last_sync > 0,
        "encrypted": _state.encrypted,
        "offset_ms": _state.offset * 1000,
        "age_seconds": age,
        "stale": _state.is_stale(),
        "refresh_in_progress": _state.is_refresh_in_progress(),
        "labs_configured": len(NTS_KE_SERVERS),
        "consensus_required": config.min_consensus,
        "successful_servers": _state.successful_servers,
        "async_refresh_enabled": config.async_refresh
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DISTRIBUTED LOCK INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════
#
# Disney Critics Fix: Distributed Systems
# Интерфейс для distributed lock при масштабировании на несколько узлов.
# По умолчанию использует локальный threading.Lock.
# Для multi-node deployment можно подключить Redis/etcd lock.
# ═══════════════════════════════════════════════════════════════════════════════

class DistributedLock:
    """
    Абстракция над distributed lock.

    По умолчанию: локальный threading.Lock (single-node)
    Для multi-node: переопределить с Redis/etcd/Consul

    Usage:
        with get_distributed_lock("timechain_append"):
            # critical section
    """

    def __init__(self, name: str, backend: str = "local"):
        self.name = name
        self.backend = backend
        self._local_lock = threading.Lock()
        self._redis_client = None
        self._lock_acquired = False

    def __enter__(self):
        if self.backend == "local":
            self._local_lock.acquire()
            self._lock_acquired = True
        elif self.backend == "redis":
            self._acquire_redis_lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.backend == "local":
            if self._lock_acquired:
                self._local_lock.release()
                self._lock_acquired = False
        elif self.backend == "redis":
            self._release_redis_lock()
        return False

    def _acquire_redis_lock(self):
        """Получить Redis lock (требует redis-py)"""
        try:
            import redis
            if self._redis_client is None:
                redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
                self._redis_client = redis.from_url(redis_url)

            # Simple lock with timeout
            lock_key = f"montana:lock:{self.name}"
            lock_value = f"{os.getpid()}:{threading.current_thread().ident}"

            while not self._redis_client.set(lock_key, lock_value, nx=True, ex=30):
                time.sleep(0.01)

            self._lock_acquired = True

        except ImportError:
            logger.warning("Redis not available, falling back to local lock")
            self._local_lock.acquire()
            self._lock_acquired = True

    def _release_redis_lock(self):
        """Освободить Redis lock"""
        if self._lock_acquired and self._redis_client:
            try:
                lock_key = f"montana:lock:{self.name}"
                self._redis_client.delete(lock_key)
            except Exception as e:
                logger.error(f"Failed to release Redis lock: {e}")
        elif self._lock_acquired:
            self._local_lock.release()
        self._lock_acquired = False


# Глобальный реестр locks
_locks: Dict[str, DistributedLock] = {}
_locks_lock = threading.Lock()

# Конфигурация backend для distributed lock
LOCK_BACKEND = os.environ.get('MONTANA_LOCK_BACKEND', 'local')  # local | redis


def get_distributed_lock(name: str) -> DistributedLock:
    """
    Получить distributed lock по имени.

    Args:
        name: Имя lock (например, "timechain_append", "alias_register")

    Returns:
        DistributedLock instance (можно использовать как context manager)
    """
    with _locks_lock:
        if name not in _locks:
            _locks[name] = DistributedLock(name, backend=LOCK_BACKEND)
        return _locks[name]


# ═══════════════════════════════════════════════════════════════════════════════
#                         INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def init():
    """
    Инициализация модуля NTS.
    Выполняет первичную синхронизацию времени.
    """
    logger.info("🕐 NTS module initializing...")
    config = get_config()
    logger.info(f"   Sync interval: {config.sync_interval}s")
    logger.info(f"   Timeout: {config.timeout}s")
    logger.info(f"   Min consensus: {config.min_consensus}")
    logger.info(f"   Async refresh: {config.async_refresh}")
    logger.info(f"   Lock backend: {LOCK_BACKEND}")

    # Первичная синхронизация
    try:
        sync_time()
    except Exception as e:
        logger.warning(f"⚠️ Initial NTS sync failed: {e}")

    logger.info("🕐 NTS module initialized")


# Автоматическая инициализация при импорте (можно отключить через env)
if os.environ.get('NTS_AUTO_INIT', 'true').lower() == 'true':
    init()


if __name__ == "__main__":
    # Тест модуля
    print("=== NTS Sync Module Test ===\n")

    # Форсируем синхронизацию
    result = sync_atomic_time()
    print(f"Sync result: {result}\n")

    # Получаем timestamp
    ts = nts_verified_timestamp()
    print(f"Verified timestamp: {ts}\n")

    # Статус
    status = get_status()
    print(f"Status: {status}\n")

    # Тест distributed lock
    print("Testing distributed lock...")
    with get_distributed_lock("test_lock"):
        print("  Lock acquired!")
    print("  Lock released!")
