#!/usr/bin/env python3
"""
TIME_BANK v3.0 — Протокол начисления монет времени Montana
===========================================================

ЭМИССИЯ:
- Динамическая: зависит от количества участников
- 1 секунда присутствия = 1 Ɉ × halving_coefficient
- Халвинг каждые τ₄ (4 года)

РЕЗЕРВ TIME_BANK:
- 21,000,000 минут (~40 лет)
- Банк тратит 10 мин/T2, подтверждая время
- После исчерпания → Oracle Mode

Привязка: Montana address
База данных: SQLite (montana.db)
"""

import time
import threading
import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List, Tuple
import logging

from montana_db import get_db, MontanaDB

# EVENT SOURCING — идеальная синхронизация между узлами
try:
    from event_ledger import get_event_ledger, EventLedger
    EVENT_SOURCING_ENABLED = True
except ImportError:
    EVENT_SOURCING_ENABLED = False

# ML-DSA-65 для криптографических доказательств присутствия
try:
    from node_crypto import sign_message, verify_signature, get_node_crypto_system
    ML_DSA_AVAILABLE = True
except ImportError:
    ML_DSA_AVAILABLE = False

# TIMECHAIN — Immutable Time Ledger (append-only, hash chaining)
try:
    from timechain import get_timechain, TimeChain
    TIMECHAIN_ENABLED = True
except ImportError:
    TIMECHAIN_ENABLED = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TIME_BANK")


# ============================================================
# КОНСТАНТЫ ПРОТОКОЛА v3.0
# ============================================================

class Protocol:
    """Константы протокола TIME_BANK v3.0"""
    VERSION = "3.0"

    # Сеть
    NODES_COUNT = 5                        # 5 узлов Montana
    BANK_PRESENCE_PER_T2 = 600             # Банк всегда присутствует 600 сек (10 мин)

    # КОГНИТИВНЫЙ ГЕНЕЗИС: 9 января 2026 00:00:00 МСК
    # = 8 января 2026 21:00:00 UTC
    GENESIS_YEAR = 2026
    GENESIS_MONTH = 1
    GENESIS_DAY = 9
    GENESIS_HOUR = 0  # по МСК
    GENESIS_MINUTE = 0
    GENESIS_SECOND = 0
    GENESIS_TIMEZONE = "Europe/Moscow"

    # TIME_BANK RESERVE — ровно 40 лет в секундах (с реальными високосными)
    # Високосные: 2028,2032,2036,2040,2044,2048,2052,2056,2060,2064 = 10 лет
    # Обычные: 30 лет
    # 30 × 365 × 86400 = 946,080,000
    # 10 × 366 × 86400 = 316,224,000
    # ИТОГО: 1,262,304,000 секунд
    # Конец: 9 января 2066 00:00:00 МСК
    BANK_TOTAL_SECONDS = 1_262_304_000     # Ровно 40 лет
    BANK_TOTAL_MINUTES = BANK_TOTAL_SECONDS // 60  # 21,038,400 минут

    # Эмиссия (динамическая, зависит от участников)
    # Нет фиксированной эмиссии — каждый получает свои секунды × halving

    # Временные координаты (Temporal Coordinates)
    TAU1_INTERVAL_SEC = 60                 # τ₁ = 1 минута — интервал подписи присутствия
    T2_DURATION_SEC = 10 * 60              # τ₂ = 10 минут = 600 секунд (slice/block)
    TAU3_DURATION_SEC = 14 * 24 * 60 * 60  # τ₃ = 14 дней = 1,209,600 сек (checkpoint)
    TAU4_DURATION_SEC = 4 * 365 * 24 * 60 * 60  # τ₄ = 4 года = 126,144,000 сек (epoch)

    # Иерархия
    T2_PER_TAU3 = 2016                     # 2016 × τ₂ в τ₃ (14 дней / 10 минут)
    TAU3_PER_YEAR = 26                     # 26 × τ₃ в году (365 / 14)
    TAU3_PER_TAU4 = 104                    # 104 × τ₃ в τ₄ (4 года)

    # Другие временные параметры
    INACTIVITY_LIMIT_SEC = 1 * 60          # τ₁ = 1 минута без активности = пауза
    TICK_INTERVAL_SEC = 1                  # Интервал обновления

    # Монеты
    COINS_PER_SECOND = 1                   # 1 секунда = 1 монета (без лотереи)

    # Presence Proof
    PRESENCE_PROOF_VERSION = "MONTANA_PRESENCE_V1"
    GENESIS_HASH = "0" * 64                # Genesis prev_hash

    @classmethod
    def get_genesis_datetime(cls) -> datetime:
        """Возвращает дату когнитивного генезиса (9 января 2026 00:00:00 МСК)"""
        import pytz
        tz = pytz.timezone(cls.GENESIS_TIMEZONE)
        return tz.localize(datetime(
            cls.GENESIS_YEAR, cls.GENESIS_MONTH, cls.GENESIS_DAY,
            cls.GENESIS_HOUR, cls.GENESIS_MINUTE, cls.GENESIS_SECOND
        ))

    @classmethod
    def get_end_datetime(cls) -> datetime:
        """Возвращает дату конца эмиссии (9 января 2066 00:00:00 МСК)"""
        from datetime import timedelta
        return cls.get_genesis_datetime() + timedelta(seconds=cls.BANK_TOTAL_SECONDS)

    @classmethod
    def seconds_since_genesis(cls) -> float:
        """Секунды с момента генезиса"""
        import pytz
        now = datetime.now(pytz.timezone(cls.GENESIS_TIMEZONE))
        genesis = cls.get_genesis_datetime()
        return max(0, (now - genesis).total_seconds())

    @classmethod
    def seconds_until_end(cls) -> float:
        """Секунды до конца эмиссии"""
        return max(0, cls.BANK_TOTAL_SECONDS - cls.seconds_since_genesis())


# ============================================================
# HALVING — Деление эмиссии на 2 каждые τ₄
# ============================================================

def halving_coefficient(tau4_count: int) -> float:
    """
    Коэффициент халвинга — деление на 2 каждые τ₄ (4 года)

    Эмиссия уменьшается в 2 раза каждую эпоху τ₄

    Args:
        tau4_count: Количество пройденных τ₄ эпох

    Returns:
        Коэффициент эмиссии (1.0, 0.5, 0.25, 0.125...)

    Формула:
        emission_per_second = 1.0 / (2 ** tau4_count)

    Пример:
        >>> halving_coefficient(0)  # τ₄ #0 (первые 4 года)
        1.0
        >>> halving_coefficient(1)  # τ₄ #1 (4-8 лет)
        0.5
        >>> halving_coefficient(2)  # τ₄ #2 (8-12 лет)
        0.25
        >>> halving_coefficient(3)  # τ₄ #3 (12-16 лет)
        0.125
    """
    return 1.0 / (2 ** tau4_count)


# ============================================================
# КЭШ СЕССИЙ
# ============================================================

class PresenceCache:
    """Кэш присутствия по адресам (address или ip)"""

    def __init__(self):
        self.entries: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, address: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.entries.get(address)

    def set(self, address: str, data: Dict[str, Any]):
        with self._lock:
            self.entries[address] = data

    def remove(self, address: str):
        with self._lock:
            self.entries.pop(address, None)

    def all(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает копию (для безопасного итерирования снаружи lock)"""
        with self._lock:
            return dict(self.entries)

    def items_snapshot(self) -> list:
        """
        ULTRA-LIGHTWEIGHT: Снимок items для итерации.
        Создаёт список один раз, не копирует весь dict.
        """
        with self._lock:
            return list(self.entries.items())

    def count_active(self) -> int:
        with self._lock:
            return sum(1 for e in self.entries.values() if e.get("is_active"))


# ============================================================
# ОСНОВНОЙ КЛАСС
# ============================================================

class TimeBank:
    """
    TIME_BANK v3.0 — Банк Времени Montana

    Эмиссия: динамическая, 1 сек = 1 Ɉ × halving
    Резерв: 21,000,000 минут (~40 лет)
    Халвинг: каждые τ₄ (4 года)
    """

    def __init__(self, db: Optional[MontanaDB] = None):
        self.db = db or get_db()
        self.presence = PresenceCache()    # Все адреса (tg_id или ip)

        # EVENT SOURCING — идеальная синхронизация
        self.ledger: Optional[EventLedger] = None
        if EVENT_SOURCING_ENABLED:
            self.ledger = get_event_ledger()

        # TIMECHAIN — Immutable Time Ledger (append-only, hash chaining)
        self.timechain: Optional[TimeChain] = None
        if TIMECHAIN_ENABLED:
            self.timechain = get_timechain()
            logger.info("⛓️ TimeChain: ENABLED (immutable ledger)")

        # Счётчики T2
        self.current_t2_start = time.time()
        self.t2_emission = 0
        self.t2_distributed = 0
        self.total_reserve = 0
        self.total_emitted = 0
        self.total_distributed = 0
        self.t2_count = 0

        # Счётчики τ₃ и τ₄
        self.tau3_count = 0                               # Количество пройденных τ₃ (14 дней)
        self.tau4_count = 0                               # Количество пройденных τ₄ (4 года)
        self.current_halving_coefficient = 1.0            # Текущий коэффициент халвинга

        # TIME_BANK RESERVE — отслеживание расхода 21 млн минут
        self.bank_seconds_spent = 0                       # Сколько секунд банк уже потратил
        self.bank_exhausted = False                       # True когда 21 млн минут исчерпаны

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # ML-DSA-65 Presence Proof
        self._presence_proofs: List[Dict[str, Any]] = []  # Подписанные доказательства
        self._last_proof_hash = Protocol.GENESIS_HASH     # Prev hash для цепочки
        self._tau1_counter = 0                            # Счётчик секунд до τ₁
        self._node_private_key: Optional[str] = None      # Private key узла
        self._node_public_key: Optional[str] = None       # Public key узла

        logger.info(f"TIME_BANK v{Protocol.VERSION}")
        logger.info(f"📡 Эмиссия: динамическая (1 сек = 1 Ɉ × halving)")
        logger.info(f"⏳ Резерв: {Protocol.BANK_TOTAL_MINUTES:,} минут (~40 лет)")
        logger.info(f"🔐 ML-DSA-65: {'✅' if ML_DSA_AVAILABLE else '❌'}")
        logger.info(f"📊 Event Sourcing: {'✅' if EVENT_SOURCING_ENABLED else '❌'}")
        logger.info(f"⛓️ TimeChain: {'✅ IMMUTABLE' if TIMECHAIN_ENABLED else '❌'}")

    # --------------------------------------------------------
    # ПРИСУТСТВИЕ (по адресу = ключу)
    # --------------------------------------------------------

    def start(self, address: str, addr_type: str = "unknown") -> Dict[str, Any]:
        """
        Начинает присутствие по адресу.
        address = address (str) или ip_address
        """
        self.db.wallet(address, addr_type)

        entry = {
            "address": address,
            "addr_type": addr_type,
            "presence_seconds": 0,
            "last_activity": time.time(),
            "t2_seconds": 0,
            "is_active": True
        }
        self.presence.set(address, entry)

        logger.info(f"📍 Присутствие: {address} [{addr_type}]")
        return entry

    def activity(self, address: str, addr_type: str = "unknown") -> dict:
        """
        Регистрирует активность по адресу.

        Returns:
            {
                "is_new": True если новая сессия,
                "was_paused": True если возобновлена после паузы,
                "presence_seconds": текущие секунды присутствия
            }
        """
        entry = self.presence.get(address)
        is_new = False
        was_paused = False

        if not entry:
            self.start(address, addr_type)
            entry = self.presence.get(address)
            is_new = True
            logger.info(f"📍 Новое присутствие: {address}")

        entry["last_activity"] = time.time()

        if not entry.get("is_active") and not is_new:
            entry["is_active"] = True
            was_paused = True
            logger.info(f"▶️ Возобновлено: {address}")

        return {
            "is_new": is_new,
            "was_paused": was_paused,
            "presence_seconds": entry.get("presence_seconds", 0),
            "t2_seconds": entry.get("t2_seconds", 0)
        }

    def end(self, address: str) -> Optional[Dict[str, Any]]:
        """Завершает присутствие, начисляет монеты с халвингом"""
        entry = self.presence.get(address)
        if not entry:
            return None

        # Начисляем за T2 с учётом халвинга
        if entry["t2_seconds"] > 0:
            coins = int(entry["t2_seconds"] * self.current_halving_coefficient)

            if self.ledger:
                # EVENT SOURCING
                self.ledger.emit(
                    to_addr=address,
                    amount=coins,
                    metadata={"reason": "session_end", "halving": self.current_halving_coefficient}
                )
            else:
                self.db.credit(address, coins, entry["addr_type"])

            # TIMECHAIN — IMMUTABLE LEDGER (append-only, hash chaining)
            if self.timechain:
                self.timechain.append(address, entry["t2_seconds"])

        self.presence.remove(address)
        logger.info(f"🏁 Завершено: {address}, {entry['presence_seconds']} сек")
        return entry

    def get(self, address: str) -> Optional[Dict[str, Any]]:
        """Информация о присутствии"""
        entry = self.presence.get(address)
        if not entry:
            return None

        return {
            "address": address,
            "presence_seconds": entry["presence_seconds"],
            "t2_seconds": entry["t2_seconds"],
            "is_active": entry["is_active"],
            "balance": self.db.balance(address)
        }

    # --------------------------------------------------------
    # ML-DSA-65 PRESENCE PROOF
    # --------------------------------------------------------

    def set_node_keys(self, private_key_hex: str, public_key_hex: str):
        """
        Устанавливает ключи узла для подписи присутствия

        POST-QUANTUM: ML-DSA-65 (FIPS 204)

        Args:
            private_key_hex: Приватный ключ (4032 байта в hex)
            public_key_hex: Публичный ключ (1952 байта в hex)
        """
        self._node_private_key = private_key_hex
        self._node_public_key = public_key_hex
        logger.info(f"🔑 Node keys set (ML-DSA-65)")

        # Передаём ключи в TimeChain для подписи блоков
        if self.timechain:
            self.timechain.set_node_keys(private_key_hex, public_key_hex)
            logger.info(f"⛓️🔐 TimeChain keys set (ML-DSA-65)")

    def _sign_presence_proof(self) -> Optional[Dict[str, Any]]:
        """
        Подписывает доказательство присутствия каждую τ₁ (1 минуту)

        Формат сообщения:
        MONTANA_PRESENCE_V1:{timestamp}:{prev_hash}:{pubkey}:{t2_index}

        Returns:
            Signed proof dict или None если нет ключей
        """
        if not ML_DSA_AVAILABLE:
            logger.warning("ML-DSA-65 недоступен")
            return None

        if not self._node_private_key or not self._node_public_key:
            logger.debug("Node keys не установлены, пропуск подписи")
            return None

        timestamp = int(time.time())
        t2_index = self.t2_count

        # Формируем сообщение для подписи
        message = f"{Protocol.PRESENCE_PROOF_VERSION}:{timestamp}:{self._last_proof_hash}:{self._node_public_key}:{t2_index}"

        # Подписываем ML-DSA-65
        signature = sign_message(self._node_private_key, message)

        # Вычисляем hash этого proof для цепочки
        proof_hash = hashlib.sha256(
            f"{message}:{signature}".encode('utf-8')
        ).hexdigest()

        proof = {
            "version": Protocol.PRESENCE_PROOF_VERSION,
            "timestamp": timestamp,
            "prev_hash": self._last_proof_hash,
            "pubkey": self._node_public_key,
            "t2_index": t2_index,
            "message": message,
            "signature": signature,
            "proof_hash": proof_hash,
            "active_addresses": self.presence.count_active()
        }

        # Обновляем prev_hash для следующего proof
        self._last_proof_hash = proof_hash

        # Сохраняем proof
        self._presence_proofs.append(proof)

        # Ограничиваем хранимые proofs (последние 100)
        if len(self._presence_proofs) > 100:
            self._presence_proofs = self._presence_proofs[-100:]

        logger.info(f"✍️ Presence Proof #{len(self._presence_proofs)} signed (τ₁)")

        return proof

    def get_presence_proofs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получает последние подписанные доказательства присутствия

        Returns:
            List of signed proofs (newest first)
        """
        return list(reversed(self._presence_proofs[-limit:]))

    def verify_presence_proof(self, proof: Dict[str, Any]) -> bool:
        """
        Верифицирует подпись доказательства присутствия ML-DSA-65

        Args:
            proof: Proof dict с message и signature

        Returns:
            True если подпись валидна
        """
        if not ML_DSA_AVAILABLE:
            return False

        try:
            pubkey = proof.get("pubkey")
            message = proof.get("message")
            signature = proof.get("signature")

            if not all([pubkey, message, signature]):
                return False

            return verify_signature(pubkey, message, signature)
        except Exception as e:
            logger.error(f"Verify error: {e}")
            return False

    def get_proof_chain_status(self) -> Dict[str, Any]:
        """
        Статус цепочки доказательств присутствия

        Returns:
            Chain status dict
        """
        return {
            "ml_dsa_available": ML_DSA_AVAILABLE,
            "node_keys_set": bool(self._node_private_key),
            "total_proofs": len(self._presence_proofs),
            "last_proof_hash": self._last_proof_hash,
            "tau1_interval_sec": Protocol.TAU1_INTERVAL_SEC,
            "genesis_hash": Protocol.GENESIS_HASH
        }

    # --------------------------------------------------------
    # КОШЕЛЁК API
    # --------------------------------------------------------

    def balance(self, address: str) -> int:
        """Баланс по адресу (ключу) — EVENT SOURCING приоритет"""
        if self.ledger:
            return self.ledger.balance(address)
        return self.db.balance(address)

    def timechain_balance(self, address: str) -> int:
        """
        IMMUTABLE баланс из TimeChain (сумма всех секунд)

        TimeChain — единственный источник истины.
        Каждый блок хэшируется с предыдущим.
        Без права перезаписи, отката, восстановления.
        """
        if self.timechain:
            return self.timechain.balance(address)
        return 0

    def verify_timechain(self, address: str) -> bool:
        """Проверяет целостность цепочки для адреса"""
        if self.timechain:
            return self.timechain.verify_chain(address)
        return False

    def get_timechain_blocks(self, address: str, limit: int = 100) -> list:
        """Получает блоки timechain для адреса"""
        if self.timechain:
            return self.timechain.get_blocks(address, limit)
        return []

    def get_balance_with_pending(self, address: str) -> Dict[str, Any]:
        """
        Баланс с учётом pending монет (ещё не подтверждённых в T2)

        Args:
            address: Адрес кошелька

        Returns:
            Dict с тремя значениями:
            - confirmed: Подтверждённый баланс (в DB)
            - pending: Накапливается в текущем T2 (в cache)
            - total: Сумма confirmed + pending
        """
        # Подтверждённый баланс (в БД)
        confirmed = self.db.balance(address)

        # Pending монеты (в кэше присутствия)
        entry = self.presence.get(address)
        pending_seconds = entry.get("t2_seconds", 0) if entry else 0

        # Умножаем на текущий коэффициент халвинга
        pending = int(pending_seconds * self.current_halving_coefficient)

        return {
            "confirmed": confirmed,
            "pending": pending,
            "total": confirmed + pending
        }

    def send(self, from_addr: str, to_addr: str, amount: int) -> Dict[str, Any]:
        """Перевод — EVENT SOURCING приоритет"""
        if self.ledger:
            ok, msg, event = self.ledger.transfer(from_addr, to_addr, amount)
            if ok:
                return {"success": True, "proof": event.event_id, "event_hash": event.event_hash}
            return {"success": False, "error": msg}

        # Fallback на старый метод
        proof = self.db.send(from_addr, to_addr, amount)
        if proof:
            return {"success": True, "proof": proof}
        return {"success": False}

    def tx_feed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Публичная лента TX"""
        return self.db.tx_feed(limit)

    def tx_verify(self, proof: str) -> Dict[str, Any]:
        """Верификация TX"""
        return self.db.tx_verify(proof)

    def my_txs(self, address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Личная история TX"""
        return self.db.my_txs(address, limit)

    def get_reserve_info(self) -> Dict[str, Any]:
        """
        Информация о резерве TIME_BANK (21 млн минут).

        Returns:
            {
                "reserve_minutes": int,         # Осталось минут
                "reserve_years": float,         # Осталось лет (~40 изначально)
                "total_minutes": int,           # Всего (21,000,000)
                "spent_minutes": int,           # Потрачено
                "halving_coefficient": float,   # Текущий коэффициент халвинга
                "exhausted": bool               # True если резерв исчерпан
            }
        """
        spent_minutes = self.bank_seconds_spent // 60
        remaining_minutes = max(0, Protocol.BANK_TOTAL_MINUTES - spent_minutes)
        remaining_years = remaining_minutes / (60 * 24 * 365)

        return {
            "reserve_minutes": remaining_minutes,
            "reserve_years": remaining_years,
            "total_minutes": Protocol.BANK_TOTAL_MINUTES,
            "spent_minutes": spent_minutes,
            "halving_coefficient": self.current_halving_coefficient,
            "exhausted": self.bank_exhausted
        }

    def wallets(self, addr_type: str = None) -> List[Dict[str, Any]]:
        """Все кошельки"""
        return self.db.wallets(addr_type)

    def stats(self) -> Dict[str, Any]:
        """Статистика TIME_BANK"""
        t2_elapsed = int(time.time() - self.current_t2_start)

        return {
            "version": Protocol.VERSION,
            "emission_model": "dynamic",  # Динамическая эмиссия
            "last_t2_emission": self.t2_emission,
            "t2_count": self.t2_count,
            "t2_elapsed_sec": t2_elapsed,
            "t2_remaining_sec": max(0, Protocol.T2_DURATION_SEC - t2_elapsed),
            "total_emitted": self.total_emitted,
            "total_distributed": self.total_distributed,
            "active_presence": self.presence.count_active(),
            "wallets": len(self.db.wallets()),
            # Temporal Coordinates
            "tau3_count": self.tau3_count,
            "tau4_count": self.tau4_count,
            "current_year": self.tau3_count // Protocol.TAU3_PER_YEAR,
            "halving_coefficient": self.current_halving_coefficient,
            "t2_to_next_tau3": Protocol.T2_PER_TAU3 - (self.t2_count % Protocol.T2_PER_TAU3),
            # TIME_BANK RESERVE (21 млн минут)
            "bank_total_minutes": Protocol.BANK_TOTAL_MINUTES,
            "bank_seconds_spent": self.bank_seconds_spent,
            "bank_minutes_spent": self.bank_seconds_spent // 60,
            "bank_minutes_remaining": max(0, Protocol.BANK_TOTAL_MINUTES - self.bank_seconds_spent // 60),
            "bank_exhausted": self.bank_exhausted,
            "bank_years_remaining": max(0, (Protocol.BANK_TOTAL_SECONDS - self.bank_seconds_spent) / (525600 * 60)),
            # ML-DSA-65 Presence Proof
            "ml_dsa_65": ML_DSA_AVAILABLE,
            "presence_proofs": len(self._presence_proofs),
            "tau1_counter": self._tau1_counter,
            "node_keys_set": bool(self._node_private_key),
            # Event Sourcing
            "event_sourcing": EVENT_SOURCING_ENABLED,
            "ledger_stats": self.ledger.stats() if self.ledger else None,
            # TimeChain — Immutable Ledger
            "timechain_enabled": TIMECHAIN_ENABLED,
            "timechain_blocks": self.timechain.total_blocks() if self.timechain else 0
        }

    # --------------------------------------------------------
    # ФОНОВЫЙ ПРОЦЕСС
    # --------------------------------------------------------

    def run(self):
        """Запускает фоновый процесс"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()
        logger.info("⏱️ TIME_BANK запущен")

    def stop(self):
        """Останавливает"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("⏹️ TIME_BANK остановлен")

    def _tick_loop(self):
        """Основной цикл"""
        sync_counter = 0
        while self._running:
            self._tick()
            sync_counter += 1

            # Синхронизация с БД каждые 30 секунд
            if sync_counter >= 30:
                self._sync_all_sessions()
                sync_counter = 0

            time.sleep(Protocol.TICK_INTERVAL_SEC)

    def _tick(self):
        """Обновление каждую секунду"""
        now = time.time()

        # Проверяем окончание T2
        if now - self.current_t2_start >= Protocol.T2_DURATION_SEC:
            self._finalize_t2()

        # τ₁ — подпись присутствия каждую минуту (ML-DSA-65)
        self._tau1_counter += 1
        if self._tau1_counter >= Protocol.TAU1_INTERVAL_SEC:
            self._sign_presence_proof()
            self._tau1_counter = 0

        # Обновляем все адреса
        for address, entry in self.presence.items_snapshot():
            inactive = now - entry["last_activity"]

            if inactive > Protocol.INACTIVITY_LIMIT_SEC:
                if entry["is_active"]:
                    entry["is_active"] = False
                    logger.debug(f"⏸️ Пауза: {address}")
            else:
                entry["presence_seconds"] += 1
                entry["t2_seconds"] += 1

    def _finalize_t2(self):
        """
        Завершает T2, начисляет монеты с халвингом

        Механизм эмиссии:
        1. Считаем сумму всех секунд присутствия
        2. Банк всегда присутствует 600 секунд (подтверждает что прошло 10 минут)
        3. Эмиссия = (total_seconds - bank_seconds) × halving_coefficient
        4. Распределяем каждому: user_seconds × halving_coefficient
        """
        self.t2_count += 1

        # Вычисляем коэффициент халвинга
        self.current_halving_coefficient = halving_coefficient(self.tau4_count)

        # Считаем общую сумму секунд присутствия всех участников
        total_users_seconds = 0
        for address, entry in self.presence.items_snapshot():
            total_users_seconds += entry["t2_seconds"]

        # Банк подтверждает что прошло 10 минут (600 секунд)
        bank_seconds = Protocol.BANK_PRESENCE_PER_T2

        # TIME_BANK RESERVE — отслеживание расхода 21 млн минут
        # Банк всегда тратит 10 мин/T2, независимо от халвинга
        self.bank_seconds_spent += bank_seconds

        # Проверяем исчерпание резерва (21 млн минут = ~40 лет)
        if not self.bank_exhausted and self.bank_seconds_spent >= Protocol.BANK_TOTAL_SECONDS:
            self.bank_exhausted = True
            logger.info(f"")
            logger.info(f"╔═══════════════════════════════════════════════════════════╗")
            logger.info(f"║  ⏳ TIME_BANK RESERVE EXHAUSTED — ORACLE MODE            ║")
            logger.info(f"╚═══════════════════════════════════════════════════════════╝")
            logger.info(f"🏦 Банк потратил все 21 млн минут")
            logger.info(f"📡 Теперь чистый оракул — продолжает верифицировать время")

        # Эмиссия = сумма секунд участников × халвинг
        # Банк НЕ получает монеты — только тратит резерв времени
        emission = int(total_users_seconds * self.current_halving_coefficient)

        self.t2_emission = emission
        self.total_emitted += emission

        # Распределяем по адресам (каждый получает свои секунды × halving)
        # EVENT SOURCING: используем ledger.emit() для неизменяемого лога
        distributed = 0
        for address, entry in self.presence.items_snapshot():
            if entry["t2_seconds"] > 0:
                seconds_earned = entry["t2_seconds"]
                coins = int(seconds_earned * self.current_halving_coefficient)

                if self.ledger:
                    # EVENT SOURCING — создаём событие EMISSION
                    self.ledger.emit(
                        to_addr=address,
                        amount=coins,
                        metadata={
                            "t2_index": self.t2_count,
                            "seconds": seconds_earned,
                            "halving": self.current_halving_coefficient,
                            "addr_type": entry.get("addr_type", "unknown")
                        }
                    )
                else:
                    # Fallback на старый метод
                    self.db.credit(address, coins, entry.get("addr_type", "unknown"))

                # TIMECHAIN — IMMUTABLE LEDGER (append-only, hash chaining)
                # Записываем секунды (не монеты) — это сырое время присутствия
                if self.timechain:
                    self.timechain.append(address, seconds_earned)

                distributed += coins
                entry["t2_seconds"] = 0

        self.t2_distributed = distributed
        self.total_distributed += distributed

        # Проверяем τ₃ checkpoint (каждые 2016 T2 = 14 дней)
        if self.t2_count % Protocol.T2_PER_TAU3 == 0:
            self.tau3_count += 1
            logger.info(f"")
            logger.info(f"╔═══════════════════════════════════════════════════════════╗")
            logger.info(f"║  τ₃ CHECKPOINT #{self.tau3_count} — 14 ДНЕЙ ПРОЙДЕНО      ║")
            logger.info(f"╚═══════════════════════════════════════════════════════════╝")
            logger.info(f"⏰ τ₃ Index: {self.tau3_count}")
            logger.info(f"📅 Year: {self.tau3_count // Protocol.TAU3_PER_YEAR}")
            logger.info(f"📊 Halving: {self.current_halving_coefficient:.4f}x")
            logger.info(f"💰 Total Emitted: {self.total_emitted:,} Ɉ")

        # Проверяем τ₄ epoch (каждые 104 τ₃ = 4 года) — ХАЛВИНГ!
        if self.tau3_count > 0 and self.tau3_count % Protocol.TAU3_PER_TAU4 == 0:
            self.tau4_count += 1
            logger.info(f"")
            logger.info(f"╔═══════════════════════════════════════════════════════════╗")
            logger.info(f"║  🔥 τ₄ HALVING #{self.tau4_count} — ЭМИССИЯ ÷ 2          ║")
            logger.info(f"╚═══════════════════════════════════════════════════════════╝")
            logger.info(f"🎉 τ₄ Epoch: {self.tau4_count}")
            logger.info(f"📊 Новый коэффициент: {halving_coefficient(self.tau4_count):.4f}x")
            logger.info(f"💰 Total Emitted: {self.total_emitted:,} Ɉ")

        logger.info(f"═══ T2 #{self.t2_count} ═══")
        logger.info(f"👥 Участники: {total_users_seconds} сек")
        logger.info(f"🏦 Банк: {bank_seconds} сек (из резерва 21M)")
        logger.info(f"📊 Халвинг: {self.current_halving_coefficient:.4f}x")
        logger.info(f"📡 Эмиссия: {emission} Ɉ")
        logger.info(f"💰 Распределено: {distributed} Ɉ")
        # TIME_BANK RESERVE status
        bank_minutes_remaining = Protocol.BANK_TOTAL_MINUTES - self.bank_seconds_spent // 60
        bank_years_remaining = bank_minutes_remaining / 525600
        logger.info(f"⏳ Резерв: {bank_minutes_remaining:,} мин (~{bank_years_remaining:.1f} лет)")

        self.current_t2_start = time.time()

    def _sync_all_sessions(self):
        """Синхронизирует все активные сессии с БД (с учётом халвинга)"""
        for address, entry in self.presence.items_snapshot():
            if entry["t2_seconds"] > 0:
                seconds_earned = entry["t2_seconds"]
                coins = int(seconds_earned * self.current_halving_coefficient)

                if self.ledger:
                    # EVENT SOURCING
                    self.ledger.emit(
                        to_addr=address,
                        amount=coins,
                        metadata={
                            "t2_index": self.t2_count,
                            "sync": True,
                            "halving": self.current_halving_coefficient
                        }
                    )
                else:
                    self.db.credit(address, coins, entry.get("addr_type", "unknown"))

                # TIMECHAIN — IMMUTABLE LEDGER (append-only, hash chaining)
                if self.timechain:
                    self.timechain.append(address, seconds_earned)

                self.total_distributed += coins
                entry["t2_seconds"] = 0

# ============================================================
# SINGLETON
# ============================================================

_instance: Optional[TimeBank] = None
_lock = threading.Lock()

def get_time_bank() -> TimeBank:
    """Возвращает глобальный экземпляр TimeBank"""
    global _instance
    with _lock:
        if _instance is None:
            _instance = TimeBank()
            _instance.run()
        return _instance


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys
    import json

    bank = get_time_bank()

    if len(sys.argv) < 2:
        print(f"""
TIME_BANK v{Protocol.VERSION} — Банк Времени Montana
═══════════════════════════════════════════════════

ЭМИССИЯ:
  • Динамическая: 1 сек = 1 Ɉ × halving
  • T2 = {Protocol.T2_DURATION_SEC // 60} мин
  • Халвинг каждые 4 года (τ₄)

РЕЗЕРВ:
  • {Protocol.BANK_TOTAL_MINUTES:,} минут (~40 лет)

Команды:
  balance <addr>  — баланс
  start <addr>    — начать присутствие
  activity <addr> — активность
  end <addr>      — завершить
  send <from> <to> <amount> — перевод
  wallets         — все кошельки
  stats           — статистика
  proofs          — ML-DSA-65 presence proofs
  proof-status    — статус цепочки proofs
  demo            — демо
        """)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "demo":
        print(f"🎬 Демо TIME_BANK v{Protocol.VERSION}")
        print("=" * 50)

        addr = "demo_123"
        bank.start(addr, "demo")

        print(f"▶️ Присутствие: {addr}")
        print(f"💰 Баланс: {bank.balance(addr)} Ɉ")

        print("\n⏱️ Симуляция 15 секунд...")
        for i in range(15):
            bank.activity(addr, "demo")
            bank._tick()
            time.sleep(0.1)

        info = bank.get(addr)
        print(f"📊 Присутствие: {info['presence_seconds']} сек")
        print(f"📊 T2: {info['t2_seconds']} сек")

        bank.end(addr)
        print(f"\n🏁 Завершено")
        print(f"💰 Итого: {bank.balance(addr)} Ɉ")

    elif cmd == "stats":
        s = bank.stats()
        print("📊 Статистика TIME_BANK:")
        print("=" * 50)
        for k, v in s.items():
            print(f"{k}: {v}")

    elif cmd == "balance" and len(sys.argv) > 2:
        addr = sys.argv[2]
        print(f"💰 {addr}: {bank.balance(addr)} Ɉ")

    elif cmd == "start" and len(sys.argv) > 2:
        addr = sys.argv[2]
        addr_type = sys.argv[3] if len(sys.argv) > 3 else "cli"
        bank.start(addr, addr_type)
        print(f"▶️ Присутствие: {addr}")

    elif cmd == "activity" and len(sys.argv) > 2:
        addr = sys.argv[2]
        bank.activity(addr)
        print(f"✓ Активность: {addr}")

    elif cmd == "end" and len(sys.argv) > 2:
        addr = sys.argv[2]
        result = bank.end(addr)
        if result:
            print(f"🏁 Завершено")
            print(f"💰 Баланс: {bank.balance(addr)} Ɉ")
        else:
            print(f"Нет присутствия: {addr}")

    elif cmd == "send" and len(sys.argv) > 4:
        from_addr = sys.argv[2]
        to_addr = sys.argv[3]
        amount = int(sys.argv[4])
        result = bank.send(from_addr, to_addr, amount)
        if result.get("success"):
            print(f"✓ TX: {result['proof'][:16]}...")
        else:
            print("❌ Ошибка")

    elif cmd == "wallets":
        ws = bank.wallets()
        print("💼 Кошельки:")
        print("-" * 40)
        for w in ws[:20]:
            print(f"{w['address']}: {w['balance']} Ɉ [{w['address_type']}]")

    elif cmd == "proofs":
        proofs = bank.get_presence_proofs(10)
        print("🔐 ML-DSA-65 Presence Proofs:")
        print("=" * 50)
        if not proofs:
            print("Нет подписанных proofs")
        for p in proofs:
            print(f"\n#{p['t2_index']} @ {p['timestamp']}")
            print(f"  hash: {p['proof_hash'][:32]}...")
            print(f"  prev: {p['prev_hash'][:32]}...")
            print(f"  sig:  {p['signature'][:32]}...")
            print(f"  active: {p['active_addresses']} addresses")

    elif cmd == "proof-status":
        status = bank.get_proof_chain_status()
        print("🔐 Presence Proof Chain Status:")
        print("=" * 50)
        print(f"ML-DSA-65:    {'✅' if status['ml_dsa_available'] else '❌'}")
        print(f"Node keys:    {'✅' if status['node_keys_set'] else '❌'}")
        print(f"Total proofs: {status['total_proofs']}")
        print(f"τ₁ interval:  {status['tau1_interval_sec']} sec")
        print(f"Last hash:    {status['last_proof_hash'][:32]}...")

    else:
        print(f"Неизвестная команда: {cmd}")
