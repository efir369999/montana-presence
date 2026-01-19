#!/usr/bin/env python3
"""
TIME_BANK v3.0 — Протокол начисления монет времени Montana
===========================================================

ЭМИССИЯ:
- 5 узлов × 3000 Ɉ = 15,000 Ɉ за слайс T2
- T2 = 10 минут (600 секунд)
- Без лотереи 80/20

НАЧИСЛЕНИЕ:
- 1 секунда присутствия = 1 монета Ɉ
- Параллельно каждому пользователю
- Излишек эмиссии → резерв

Привязка: Telegram ID
База данных: SQLite (montana.db)
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List
import logging

from montana_db import get_db, MontanaDB

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
    EMISSION_PER_NODE = 3000               # Каждый узел эмитирует 3000 Ɉ за T2
    TOTAL_EMISSION_PER_T2 = NODES_COUNT * EMISSION_PER_NODE  # 15,000 Ɉ

    # Время
    T2_DURATION_SEC = 10 * 60              # T2 = 10 минут = 600 секунд
    INACTIVITY_LIMIT_SEC = 3 * 60          # 3 минуты без активности = пауза
    TICK_INTERVAL_SEC = 1                  # Интервал обновления

    # Монеты
    COINS_PER_SECOND = 1                   # 1 секунда = 1 монета (без лотереи)


# ============================================================
# КЭШ СЕССИЙ
# ============================================================

class PresenceCache:
    """Кэш присутствия по адресам (telegram_id или ip)"""

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
        with self._lock:
            return dict(self.entries)

    def count_active(self) -> int:
        with self._lock:
            return sum(1 for e in self.entries.values() if e.get("is_active"))


# ============================================================
# ОСНОВНОЙ КЛАСС
# ============================================================

class TimeBank:
    """
    TIME_BANK v3.0 — Банк Времени Montana

    Эмиссия: 5 узлов × 3000 = 15,000 Ɉ за T2
    Начисление: 1 секунда = 1 Ɉ (параллельно)
    """

    def __init__(self, db: Optional[MontanaDB] = None):
        self.db = db or get_db()
        self.presence = PresenceCache()    # Все адреса (tg_id или ip)

        # Счётчики
        self.current_t2_start = time.time()
        self.t2_emission = 0
        self.t2_distributed = 0
        self.total_reserve = 0
        self.total_emitted = 0
        self.total_distributed = 0
        self.t2_count = 0

        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info(f"TIME_BANK v{Protocol.VERSION}")
        logger.info(f"📡 Эмиссия/T2: {Protocol.TOTAL_EMISSION_PER_T2} Ɉ")

    # --------------------------------------------------------
    # ПРИСУТСТВИЕ (по адресу = ключу)
    # --------------------------------------------------------

    def start(self, address: str, addr_type: str = "unknown") -> Dict[str, Any]:
        """
        Начинает присутствие по адресу.
        address = telegram_id (str) или ip_address
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

    def activity(self, address: str, addr_type: str = "unknown") -> bool:
        """Регистрирует активность по адресу"""
        entry = self.presence.get(address)
        if not entry:
            self.start(address, addr_type)
            entry = self.presence.get(address)

        entry["last_activity"] = time.time()

        if not entry.get("is_active"):
            entry["is_active"] = True
            logger.info(f"▶️ Возобновлено: {address}")

        return True

    def end(self, address: str) -> Optional[Dict[str, Any]]:
        """Завершает присутствие, начисляет монеты"""
        entry = self.presence.get(address)
        if not entry:
            return None

        # Начисляем за T2
        if entry["t2_seconds"] > 0:
            self.db.credit(address, entry["t2_seconds"], entry["addr_type"])

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
    # КОШЕЛЁК API
    # --------------------------------------------------------

    def balance(self, address: str) -> int:
        """Баланс по адресу (ключу)"""
        return self.db.balance(address)

    def send(self, from_addr: str, to_addr: str, amount: int) -> Dict[str, Any]:
        """Перевод"""
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

    def wallets(self, addr_type: str = None) -> List[Dict[str, Any]]:
        """Все кошельки"""
        return self.db.wallets(addr_type)

    def stats(self) -> Dict[str, Any]:
        """Статистика TIME_BANK"""
        t2_elapsed = int(time.time() - self.current_t2_start)

        return {
            "version": Protocol.VERSION,
            "emission_per_t2": Protocol.TOTAL_EMISSION_PER_T2,
            "t2_count": self.t2_count,
            "t2_elapsed_sec": t2_elapsed,
            "t2_remaining_sec": max(0, Protocol.T2_DURATION_SEC - t2_elapsed),
            "total_emitted": self.total_emitted,
            "total_distributed": self.total_distributed,
            "total_reserve": self.total_reserve,
            "active_presence": self.presence.count_active(),
            "wallets": len(self.db.wallets())
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

        # Обновляем все адреса
        for address, entry in list(self.presence.all().items()):
            inactive = now - entry["last_activity"]

            if inactive > Protocol.INACTIVITY_LIMIT_SEC:
                if entry["is_active"]:
                    entry["is_active"] = False
                    logger.debug(f"⏸️ Пауза: {address}")
            else:
                entry["presence_seconds"] += 1
                entry["t2_seconds"] += 1

    def _finalize_t2(self):
        """Завершает T2, начисляет монеты"""
        self.t2_count += 1

        # Эмиссия
        emission = Protocol.TOTAL_EMISSION_PER_T2
        self.t2_emission = emission
        self.total_emitted += emission

        # Распределяем по адресам
        distributed = 0
        for address, entry in self.presence.all().items():
            if entry["t2_seconds"] > 0:
                coins = entry["t2_seconds"] * Protocol.COINS_PER_SECOND
                self.db.credit(address, coins, entry.get("addr_type", "unknown"))
                distributed += coins
                entry["t2_seconds"] = 0

        self.t2_distributed = distributed
        self.total_distributed += distributed

        # Резерв
        surplus = emission - distributed
        self.total_reserve += surplus

        logger.info(f"═══ T2 #{self.t2_count} ═══")
        logger.info(f"📡 Эмиссия: {emission} Ɉ")
        logger.info(f"💰 Распределено: {distributed} Ɉ")
        logger.info(f"💎 Резерв: +{surplus} Ɉ (всего: {self.total_reserve})")

        self.current_t2_start = time.time()

    def _sync_all_sessions(self):
        """Синхронизирует все активные сессии с БД"""
        for address, entry in self.presence.all().items():
            if entry["t2_seconds"] > 0:
                self.db.credit(address, entry["t2_seconds"], entry.get("addr_type", "unknown"))
                self.total_distributed += entry["t2_seconds"]
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
  • {Protocol.TOTAL_EMISSION_PER_T2} Ɉ за T2 ({Protocol.T2_DURATION_SEC // 60} мин)

АДРЕС = КЛЮЧ:
  • telegram_id или ip_address
  • 1 секунда = 1 монета Ɉ

Команды:
  balance <addr>  — баланс
  start <addr>    — начать присутствие
  activity <addr> — активность
  end <addr>      — завершить
  send <from> <to> <amount> — перевод
  wallets         — все кошельки
  stats           — статистика
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

    else:
        print(f"Неизвестная команда: {cmd}")
