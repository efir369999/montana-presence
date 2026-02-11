#!/usr/bin/env python3
"""
failover_chain.py — Цепочка отказоустойчивости Montana

Книга Монтана, Глава 08:
> "Failover цепь: Amsterdam → Almaty → SPB → Novosibirsk"
> "Если Amsterdam падает — Almaty подхватывает автоматически."
> "Пользователь отправил сообщение в Амстердам — получил ответ из Алматы.
> Разница — пять секунд."

Механика:
1. Primary узел падает
2. Standby ждёт 5 секунд (может быть глитч)
3. Проверяет ещё раз
4. Если всё ещё молчит — подхватывает
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum
import time
import threading


class FailoverEvent(Enum):
    """Типы событий failover."""
    NODE_TIMEOUT = "timeout"
    NODE_RECOVERED = "recovered"
    TAKEOVER_STARTED = "takeover_started"
    TAKEOVER_COMPLETE = "takeover_complete"
    CHAIN_BROKEN = "chain_broken"


@dataclass
class HealthCheck:
    """Результат проверки здоровья узла."""
    node_id: str
    is_healthy: bool
    latency_ms: float
    checked_at: str
    error: Optional[str] = None


@dataclass
class FailoverRecord:
    """Запись о событии failover."""
    event_id: str
    event_type: FailoverEvent
    from_node: str
    to_node: Optional[str]
    timestamp: str
    detection_time_sec: float
    takeover_time_sec: float = 0.0


class FailoverChain:
    """
    Цепочка отказоустойчивости.

    Книга Монтана:
    > "Almaty видит это. Ждёт пять секунд — может, просто глитч.
    > Проверяет ещё раз. Amsterdam молчит."
    > "Almaty подхватывает. Бот продолжает работать."
    """

    # Константы из книги
    DETECTION_TIMEOUT_SEC = 5.0  # Ожидание перед takeover
    HEALTH_CHECK_INTERVAL_SEC = 1.0  # Интервал проверки
    MAX_RETRIES = 2  # Количество повторных проверок

    def __init__(self):
        # Цепочка узлов (из книги)
        self.bot_chain = ["amsterdam", "almaty", "spb", "novosibirsk"]
        self.brain_chain = ["moscow", "almaty", "spb", "novosibirsk"]

        # Текущие активные узлы
        self.active_bot: str = self.bot_chain[0]
        self.active_brain: str = self.brain_chain[0]

        # Состояние узлов
        self.node_health: Dict[str, bool] = {
            node: True for node in set(self.bot_chain + self.brain_chain)
        }

        # История событий
        self.events: List[FailoverRecord] = []

        # Callbacks
        self.on_failover: Optional[Callable[[FailoverRecord], None]] = None

    def check_node(self, node_id: str) -> HealthCheck:
        """
        Проверить здоровье узла.

        Args:
            node_id: ID узла

        Returns:
            HealthCheck
        """
        start = time.time()
        is_healthy = self.node_health.get(node_id, False)
        latency = (time.time() - start) * 1000

        return HealthCheck(
            node_id=node_id,
            is_healthy=is_healthy,
            latency_ms=latency,
            checked_at=datetime.now(timezone.utc).isoformat(),
            error=None if is_healthy else "Node not responding"
        )

    def simulate_failure(self, node_id: str) -> FailoverRecord:
        """
        Симулировать падение узла.

        Args:
            node_id: ID узла

        Returns:
            FailoverRecord с результатом
        """
        if node_id not in self.node_health:
            raise ValueError(f"Unknown node: {node_id}")

        # Узел падает
        self.node_health[node_id] = False
        detection_start = time.time()

        # Определяем какую роль занимал узел
        is_bot = node_id == self.active_bot
        is_brain = node_id == self.active_brain
        chain = self.bot_chain if is_bot else self.brain_chain

        # Ждём DETECTION_TIMEOUT (как в книге — 5 секунд)
        # В симуляции просто записываем
        detection_time = self.DETECTION_TIMEOUT_SEC

        # Находим следующий в цепи
        current_idx = chain.index(node_id) if node_id in chain else -1
        next_node = None

        for i in range(current_idx + 1, len(chain)):
            candidate = chain[i]
            if self.node_health.get(candidate, False):
                next_node = candidate
                break

        # Takeover
        takeover_start = time.time()
        if next_node:
            if is_bot:
                self.active_bot = next_node
            elif is_brain:
                self.active_brain = next_node

        takeover_time = time.time() - takeover_start

        # Создаём запись
        record = FailoverRecord(
            event_id=f"fo_{int(time.time()*1000)}",
            event_type=FailoverEvent.TAKEOVER_COMPLETE if next_node else FailoverEvent.CHAIN_BROKEN,
            from_node=node_id,
            to_node=next_node,
            timestamp=datetime.now(timezone.utc).isoformat(),
            detection_time_sec=detection_time,
            takeover_time_sec=takeover_time
        )

        self.events.append(record)

        if self.on_failover:
            self.on_failover(record)

        return record

    def recover_node(self, node_id: str) -> None:
        """
        Восстановить узел (не возвращает роль автоматически).

        Args:
            node_id: ID узла
        """
        self.node_health[node_id] = True

        record = FailoverRecord(
            event_id=f"rec_{int(time.time()*1000)}",
            event_type=FailoverEvent.NODE_RECOVERED,
            from_node=node_id,
            to_node=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            detection_time_sec=0,
            takeover_time_sec=0
        )

        self.events.append(record)

    def get_chain_status(self) -> Dict:
        """Статус цепочки failover."""
        healthy_bots = [n for n in self.bot_chain if self.node_health.get(n, False)]
        healthy_brains = [n for n in self.brain_chain if self.node_health.get(n, False)]

        return {
            "bot_chain": self.bot_chain,
            "brain_chain": self.brain_chain,
            "active_bot": self.active_bot,
            "active_brain": self.active_brain,
            "healthy_nodes": [n for n, h in self.node_health.items() if h],
            "failed_nodes": [n for n, h in self.node_health.items() if not h],
            "bot_chain_depth": len(healthy_bots),
            "brain_chain_depth": len(healthy_brains),
            "detection_timeout_sec": self.DETECTION_TIMEOUT_SEC,
            "total_failovers": len([e for e in self.events
                                   if e.event_type == FailoverEvent.TAKEOVER_COMPLETE])
        }

    def get_next_in_chain(self, role: str) -> Optional[str]:
        """
        Получить следующий узел в цепи.

        Args:
            role: "bot" или "brain"

        Returns:
            ID следующего узла или None
        """
        if role == "bot":
            chain = self.bot_chain
            current = self.active_bot
        else:
            chain = self.brain_chain
            current = self.active_brain

        current_idx = chain.index(current) if current in chain else -1

        for i in range(current_idx + 1, len(chain)):
            candidate = chain[i]
            if self.node_health.get(candidate, False):
                return candidate

        return None


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    chain = FailoverChain()

    print("=" * 60)
    print("FAILOVER CHAIN — Цепочка отказоустойчивости")
    print("=" * 60)
    print("\n'Если Amsterdam падает — Almaty подхватывает автоматически.'")

    # Статус цепи
    print("\n--- НАЧАЛЬНЫЙ СТАТУС ---")
    status = chain.get_chain_status()
    print(f"BOT цепь: {' → '.join(status['bot_chain'])}")
    print(f"BRAIN цепь: {' → '.join(status['brain_chain'])}")
    print(f"Активный BOT: {status['active_bot']}")
    print(f"Активный BRAIN: {status['active_brain']}")
    print(f"Timeout детекции: {status['detection_timeout_sec']} сек")

    # Симуляция падения Amsterdam
    print("\n--- ПАДЕНИЕ AMSTERDAM ---")
    print("[ERROR] Amsterdam: connection timeout")
    print(f"[INFO] Ожидание {chain.DETECTION_TIMEOUT_SEC} секунд...")

    record = chain.simulate_failure("amsterdam")

    print(f"[INFO] {record.to_node}: taking over bot")
    print(f"\nСобытие: {record.event_type.value}")
    print(f"От узла: {record.from_node}")
    print(f"К узлу: {record.to_node}")
    print(f"Время детекции: {record.detection_time_sec} сек")

    # Новый статус
    print("\n--- НОВЫЙ СТАТУС ---")
    status = chain.get_chain_status()
    print(f"Активный BOT: {status['active_bot']}")
    print(f"Здоровые узлы: {', '.join(status['healthy_nodes'])}")
    print(f"Упавшие узлы: {', '.join(status['failed_nodes'])}")

    # Следующий в цепи
    print("\n--- СЛЕДУЮЩИЙ В ЦЕПИ ---")
    next_bot = chain.get_next_in_chain("bot")
    print(f"Если {status['active_bot']} упадёт, следующий: {next_bot}")

    # Каскадное падение
    print("\n--- КАСКАДНОЕ ПАДЕНИЕ ---")
    for node in ["almaty", "spb"]:
        record = chain.simulate_failure(node)
        print(f"{node} упал → замена: {record.to_node or 'НЕТ'}")

    # Финальный статус
    print("\n--- ФИНАЛЬНЫЙ СТАТУС ---")
    status = chain.get_chain_status()
    print(f"Активный BOT: {status['active_bot']}")
    print(f"Глубина BOT цепи: {status['bot_chain_depth']}")
    print(f"Всего failover: {status['total_failovers']}")

    print("\n" + "=" * 60)
    print("'Пользователь не замечает падения. Разница — 5 секунд.'")
    print("=" * 60)
