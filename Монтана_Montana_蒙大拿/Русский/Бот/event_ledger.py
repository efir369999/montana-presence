#!/usr/bin/env python3
"""
EVENT LEDGER — Event Sourcing для Montana Protocol
====================================================

ИДЕАЛЬНОЕ РЕШЕНИЕ синхронизации:
- Все изменения балансов через неизменяемые события
- События реплицируются между узлами
- Баланс = сумма всех событий для адреса
- Конфликты невозможны (append-only log)

СОБЫТИЯ:
- EMISSION: начисление от TIME_BANK
- TRANSFER: перевод между пользователями
- ESCROW_LOCK: заморозка для контракта
- ESCROW_RELEASE: освобождение escrow

ИДЕНТИФИКАТОР СОБЫТИЯ:
{timestamp_ms}.{node_id}.{counter}
Гарантирует глобальную уникальность + сортировку

Автор: Montana Protocol
"""

import json
import time
import threading
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EVENT_LEDGER")


# ============================================================
# ТИПЫ СОБЫТИЙ
# ============================================================

class EventType:
    """Типы событий Montana"""
    EMISSION = "EMISSION"           # TIME_BANK начисление
    TRANSFER = "TRANSFER"           # Перевод между адресами
    ESCROW_LOCK = "ESCROW_LOCK"     # Заморозка для контракта
    ESCROW_RELEASE = "ESCROW_RELEASE"  # Освобождение escrow
    GENESIS = "GENESIS"             # Начальное событие


@dataclass
class Event:
    """
    Неизменяемое событие Montana

    Поля:
        event_id: Уникальный ID (timestamp_ms.node_id.counter)
        event_type: Тип события (EMISSION, TRANSFER, etc)
        timestamp: Unix timestamp создания
        from_addr: Адрес отправителя (или "TIME_BANK" для эмиссии)
        to_addr: Адрес получателя
        amount: Сумма в Ɉ
        metadata: Дополнительные данные (JSON)
        node_id: ID узла-создателя
        prev_hash: Hash предыдущего события (цепочка)
        event_hash: Hash этого события
    """
    event_id: str
    event_type: str
    timestamp: float
    from_addr: str
    to_addr: str
    amount: int
    metadata: Dict[str, Any]
    node_id: str
    prev_hash: str
    event_hash: str = ""

    def __post_init__(self):
        if not self.event_hash:
            self.event_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """SHA-256 хеш события для верификации"""
        data = f"{self.event_id}:{self.event_type}:{self.timestamp}:{self.from_addr}:{self.to_addr}:{self.amount}:{json.dumps(self.metadata, sort_keys=True)}:{self.node_id}:{self.prev_hash}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        """Проверяет целостность события"""
        return self.event_hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        return cls(**data)


# ============================================================
# EVENT LEDGER
# ============================================================

class EventLedger:
    """
    Event Sourcing для Montana Protocol

    АРХИТЕКТУРА:
    1. Все изменения балансов = события
    2. События неизменяемы (append-only)
    3. Баланс = replay всех событий
    4. Синхронизация = репликация событий

    ХРАНЕНИЕ:
    - events.jsonl — append-only log событий
    - balances.json — кэш балансов (rebuild из событий)
    """

    GENESIS_HASH = "0" * 64
    TIME_BANK_ADDR = "TIME_BANK"
    ESCROW_PREFIX = "escrow:"

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.events_file = self.data_dir / "events.jsonl"
        self.balances_cache_file = self.data_dir / "balances_cache.json"

        # Node ID для уникальности событий
        self.node_id = self._get_node_id()

        # Счётчик событий для уникальности в пределах ms
        self._event_counter = 0
        self._counter_lock = threading.Lock()

        # Кэш балансов (пересчитывается из событий)
        self._balances: Dict[str, int] = {}
        self._balances_lock = threading.RLock()

        # Последний hash для цепочки
        self._last_hash = self.GENESIS_HASH

        # Загружаем существующие события
        self._load_events()

        logger.info(f"EVENT_LEDGER initialized: node={self.node_id}")
        logger.info(f"  Events: {self.events_file}")
        logger.info(f"  Total events: {self._event_counter}")
        logger.info(f"  Addresses: {len(self._balances)}")

    def _get_node_id(self) -> str:
        """Получает уникальный ID узла"""
        # Пробуем из environment
        node_id = os.environ.get("MONTANA_NODE_ID")
        if node_id:
            return node_id

        # Из файла
        node_file = self.data_dir / "node_id.txt"
        if node_file.exists():
            return node_file.read_text().strip()

        # Генерируем новый
        import socket
        hostname = socket.gethostname()
        node_id = hashlib.sha256(f"{hostname}:{time.time()}".encode()).hexdigest()[:8]

        node_file.write_text(node_id)
        return node_id

    def _generate_event_id(self) -> str:
        """
        Генерирует глобально уникальный ID события.

        Формат: {timestamp_ms}.{node_id}.{counter}

        Гарантии:
        - Уникальность: node_id + counter
        - Сортировка: timestamp первый
        - Читаемость: человекочитаемый формат
        """
        with self._counter_lock:
            timestamp_ms = int(time.time() * 1000)
            self._event_counter += 1
            return f"{timestamp_ms}.{self.node_id}.{self._event_counter}"

    # --------------------------------------------------------
    # PERSISTENCE
    # --------------------------------------------------------

    def _load_events(self):
        """Загружает события из файла и пересчитывает балансы"""
        if not self.events_file.exists():
            logger.info("No events file, starting fresh")
            return

        events_loaded = 0
        with open(self.events_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event = Event.from_dict(data)

                    # Верифицируем событие
                    if not event.verify():
                        logger.error(f"Invalid event hash: {event.event_id}")
                        continue

                    # Применяем к балансам
                    self._apply_event_to_balances(event)

                    # Обновляем last_hash
                    self._last_hash = event.event_hash

                    # Обновляем counter
                    parts = event.event_id.split('.')
                    if len(parts) >= 3 and parts[1] == self.node_id:
                        counter = int(parts[2])
                        if counter > self._event_counter:
                            self._event_counter = counter

                    events_loaded += 1

                except Exception as e:
                    logger.error(f"Error loading event: {e}")

        logger.info(f"Loaded {events_loaded} events")

    def _append_event(self, event: Event):
        """Записывает событие в файл (append-only)"""
        with open(self.events_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + '\n')

    def _apply_event_to_balances(self, event: Event):
        """Применяет событие к кэшу балансов"""
        with self._balances_lock:
            # Инициализируем балансы если нужно
            if event.from_addr not in self._balances:
                self._balances[event.from_addr] = 0
            if event.to_addr not in self._balances:
                self._balances[event.to_addr] = 0

            # Применяем изменение
            if event.from_addr != self.TIME_BANK_ADDR:
                self._balances[event.from_addr] -= event.amount
            self._balances[event.to_addr] += event.amount

    def _save_balances_cache(self):
        """Сохраняет кэш балансов для быстрой загрузки"""
        with self._balances_lock:
            with open(self.balances_cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "last_hash": self._last_hash,
                    "balances": self._balances,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------
    # СОЗДАНИЕ СОБЫТИЙ
    # --------------------------------------------------------

    def emit(
        self,
        to_addr: str,
        amount: int,
        metadata: Optional[Dict] = None
    ) -> Event:
        """
        Создаёт событие EMISSION (начисление от TIME_BANK).

        Args:
            to_addr: Адрес получателя
            amount: Сумма в Ɉ
            metadata: Дополнительные данные

        Returns:
            Созданное событие
        """
        event = Event(
            event_id=self._generate_event_id(),
            event_type=EventType.EMISSION,
            timestamp=time.time(),
            from_addr=self.TIME_BANK_ADDR,
            to_addr=str(to_addr),
            amount=amount,
            metadata=metadata or {},
            node_id=self.node_id,
            prev_hash=self._last_hash
        )

        # Сохраняем и применяем
        self._append_event(event)
        self._apply_event_to_balances(event)
        self._last_hash = event.event_hash

        logger.info(f"EMIT: {amount} Ɉ → {to_addr} [{event.event_id}]")
        return event

    def transfer(
        self,
        from_addr: str,
        to_addr: str,
        amount: int,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[Event]]:
        """
        Создаёт событие TRANSFER (перевод).

        Args:
            from_addr: Адрес отправителя
            to_addr: Адрес получателя
            amount: Сумма в Ɉ
            metadata: Дополнительные данные

        Returns:
            (success, message, event)
        """
        from_addr = str(from_addr)
        to_addr = str(to_addr)

        # Проверяем баланс
        with self._balances_lock:
            balance = self._balances.get(from_addr, 0)
            if balance < amount:
                return False, f"Недостаточно средств: {balance} < {amount}", None

        event = Event(
            event_id=self._generate_event_id(),
            event_type=EventType.TRANSFER,
            timestamp=time.time(),
            from_addr=from_addr,
            to_addr=to_addr,
            amount=amount,
            metadata=metadata or {},
            node_id=self.node_id,
            prev_hash=self._last_hash
        )

        # Сохраняем и применяем
        self._append_event(event)
        self._apply_event_to_balances(event)
        self._last_hash = event.event_hash

        logger.info(f"TRANSFER: {from_addr} → {to_addr}, {amount} Ɉ [{event.event_id}]")
        return True, "OK", event

    def escrow_lock(
        self,
        from_addr: str,
        contract_id: str,
        amount: int,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[Event]]:
        """
        Создаёт событие ESCROW_LOCK (заморозка для контракта).

        Args:
            from_addr: Адрес создателя контракта
            contract_id: ID контракта
            amount: Сумма в Ɉ
            metadata: Дополнительные данные

        Returns:
            (success, message, event)
        """
        from_addr = str(from_addr)
        escrow_addr = f"{self.ESCROW_PREFIX}{contract_id}"

        # Проверяем баланс
        with self._balances_lock:
            balance = self._balances.get(from_addr, 0)
            if balance < amount:
                return False, f"Недостаточно средств: {balance} < {amount}", None

        event = Event(
            event_id=self._generate_event_id(),
            event_type=EventType.ESCROW_LOCK,
            timestamp=time.time(),
            from_addr=from_addr,
            to_addr=escrow_addr,
            amount=amount,
            metadata={**(metadata or {}), "contract_id": contract_id},
            node_id=self.node_id,
            prev_hash=self._last_hash
        )

        self._append_event(event)
        self._apply_event_to_balances(event)
        self._last_hash = event.event_hash

        logger.info(f"ESCROW_LOCK: {from_addr} → {escrow_addr}, {amount} Ɉ")
        return True, "OK", event

    def escrow_release(
        self,
        contract_id: str,
        to_addr: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[Event]]:
        """
        Создаёт событие ESCROW_RELEASE (освобождение escrow).

        Args:
            contract_id: ID контракта
            to_addr: Адрес получателя (победитель или создатель при отмене)
            metadata: Дополнительные данные

        Returns:
            (success, message, event)
        """
        escrow_addr = f"{self.ESCROW_PREFIX}{contract_id}"
        to_addr = str(to_addr)

        # Проверяем баланс escrow
        with self._balances_lock:
            amount = self._balances.get(escrow_addr, 0)
            if amount <= 0:
                return False, "Escrow пуст", None

        event = Event(
            event_id=self._generate_event_id(),
            event_type=EventType.ESCROW_RELEASE,
            timestamp=time.time(),
            from_addr=escrow_addr,
            to_addr=to_addr,
            amount=amount,
            metadata={**(metadata or {}), "contract_id": contract_id},
            node_id=self.node_id,
            prev_hash=self._last_hash
        )

        self._append_event(event)
        self._apply_event_to_balances(event)
        self._last_hash = event.event_hash

        logger.info(f"ESCROW_RELEASE: {escrow_addr} → {to_addr}, {amount} Ɉ")
        return True, "OK", event

    # --------------------------------------------------------
    # QUERY API
    # --------------------------------------------------------

    def balance(self, address: str) -> int:
        """Возвращает баланс адреса"""
        with self._balances_lock:
            return self._balances.get(str(address), 0)

    def balances(self) -> Dict[str, int]:
        """Возвращает все балансы"""
        with self._balances_lock:
            return dict(self._balances)

    def get_events(
        self,
        address: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Возвращает события с фильтрацией.

        Args:
            address: Фильтр по адресу (from или to)
            event_type: Фильтр по типу события
            limit: Максимальное количество

        Returns:
            Список событий (newest first)
        """
        events = []

        if not self.events_file.exists():
            return events

        # Читаем в обратном порядке (newest first)
        with open(self.events_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in reversed(lines):
            if len(events) >= limit:
                break

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                event = Event.from_dict(data)

                # Фильтр по адресу
                if address:
                    addr = str(address)
                    if event.from_addr != addr and event.to_addr != addr:
                        continue

                # Фильтр по типу
                if event_type and event.event_type != event_type:
                    continue

                events.append(event)

            except Exception as e:
                logger.error(f"Error parsing event: {e}")

        return events

    def get_events_since(self, last_event_id: str) -> List[Event]:
        """
        Возвращает события после указанного ID.

        Используется для синхронизации между узлами.

        Args:
            last_event_id: ID последнего известного события

        Returns:
            Список новых событий
        """
        events = []
        found = False if last_event_id else True

        if not self.events_file.exists():
            return events

        with open(self.events_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = Event.from_dict(data)

                    if found:
                        events.append(event)
                    elif event.event_id == last_event_id:
                        found = True

                except Exception as e:
                    logger.error(f"Error parsing event: {e}")

        return events

    def merge_events(self, remote_events: List[Dict[str, Any]]) -> int:
        """
        Мержит события от другого узла.

        Дедупликация по event_id.

        Args:
            remote_events: Список событий от удалённого узла

        Returns:
            Количество добавленных событий
        """
        # Загружаем существующие event_id
        existing_ids = set()
        if self.events_file.exists():
            with open(self.events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        existing_ids.add(data.get("event_id"))
                    except:
                        pass

        added = 0
        for event_data in remote_events:
            event_id = event_data.get("event_id")

            # Пропускаем дубликаты
            if event_id in existing_ids:
                continue

            try:
                event = Event.from_dict(event_data)

                # Верифицируем
                if not event.verify():
                    logger.warning(f"Invalid remote event: {event_id}")
                    continue

                # Добавляем
                self._append_event(event)
                self._apply_event_to_balances(event)
                existing_ids.add(event_id)
                added += 1

                logger.info(f"MERGED: {event.event_type} {event_id}")

            except Exception as e:
                logger.error(f"Error merging event {event_id}: {e}")

        if added > 0:
            self._save_balances_cache()
            logger.info(f"Merged {added} events from remote")

        return added

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Статистика ledger'а"""
        with self._balances_lock:
            total_supply = sum(
                b for addr, b in self._balances.items()
                if not addr.startswith(self.ESCROW_PREFIX)
                and addr != self.TIME_BANK_ADDR
            )

            locked_in_escrow = sum(
                b for addr, b in self._balances.items()
                if addr.startswith(self.ESCROW_PREFIX)
            )

        return {
            "node_id": self.node_id,
            "event_counter": self._event_counter,
            "last_hash": self._last_hash[:16] + "...",
            "addresses": len(self._balances),
            "total_supply": total_supply,
            "locked_in_escrow": locked_in_escrow,
            "events_file": str(self.events_file)
        }


# ============================================================
# SINGLETON
# ============================================================

_instance: Optional[EventLedger] = None
_lock = threading.Lock()

def get_event_ledger() -> EventLedger:
    """Возвращает глобальный экземпляр EventLedger"""
    global _instance
    with _lock:
        if _instance is None:
            _instance = EventLedger()
        return _instance


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    ledger = get_event_ledger()

    if len(sys.argv) < 2:
        print("""
EVENT LEDGER — Event Sourcing для Montana Protocol
===================================================

Команды:
    stats           — статистика
    balance <addr>  — баланс адреса
    emit <addr> <amount>  — начислить (эмиссия)
    transfer <from> <to> <amount>  — перевод
    events [addr] [limit]  — история событий
    export          — экспорт событий в JSON
        """)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        s = ledger.stats()
        print("EVENT LEDGER Stats:")
        print("=" * 50)
        for k, v in s.items():
            print(f"  {k}: {v}")

    elif cmd == "balance" and len(sys.argv) > 2:
        addr = sys.argv[2]
        print(f"Balance {addr}: {ledger.balance(addr)} Ɉ")

    elif cmd == "emit" and len(sys.argv) > 3:
        addr = sys.argv[2]
        amount = int(sys.argv[3])
        event = ledger.emit(addr, amount)
        print(f"EMISSION: {amount} Ɉ → {addr}")
        print(f"Event ID: {event.event_id}")

    elif cmd == "transfer" and len(sys.argv) > 4:
        from_addr = sys.argv[2]
        to_addr = sys.argv[3]
        amount = int(sys.argv[4])
        ok, msg, event = ledger.transfer(from_addr, to_addr, amount)
        if ok:
            print(f"TRANSFER: {from_addr} → {to_addr}, {amount} Ɉ")
            print(f"Event ID: {event.event_id}")
        else:
            print(f"ERROR: {msg}")

    elif cmd == "events":
        addr = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        events = ledger.get_events(address=addr, limit=limit)
        print(f"Events ({len(events)}):")
        print("-" * 60)
        for e in events:
            ts = datetime.fromtimestamp(e.timestamp).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{ts} {e.event_type}: {e.from_addr} → {e.to_addr}, {e.amount} Ɉ")

    elif cmd == "export":
        events = ledger.get_events(limit=10000)
        output = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "node_id": ledger.node_id,
            "events": [e.to_dict() for e in reversed(events)]
        }
        output_file = ledger.data_dir / "events_export.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Exported to {output_file}")

    else:
        print(f"Unknown command: {cmd}")
