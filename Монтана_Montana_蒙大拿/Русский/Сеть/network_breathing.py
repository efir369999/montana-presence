#!/usr/bin/env python3
"""
network_breathing.py — Дыхание сети Montana

Книга Монтана, Глава 08:
> "Каждые двенадцать секунд — синхронизация. Git pull. Git push. Вдох — выдох."
> "Пять узлов. Один организм. Одно дыхание."
> "Watchdog. Сервис, который следит за всеми.
> Если кто-то отстал — подтягивает. Если кто-то упал — поднимает тревогу."

Дыхание сети:
- 12 секунд цикл
- Pull = вдох (получить данные)
- Push = выдох (отдать данные)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from enum import Enum
import hashlib
import time


class BreathPhase(Enum):
    """Фаза дыхания."""
    INHALE = "inhale"    # Вдох — pull
    EXHALE = "exhale"    # Выдох — push
    PAUSE = "pause"      # Пауза между


class NodeSyncStatus(Enum):
    """Статус синхронизации узла."""
    SYNCED = "synced"
    BEHIND = "behind"
    AHEAD = "ahead"
    DISCONNECTED = "disconnected"


@dataclass
class SyncState:
    """Состояние синхронизации узла."""
    node_id: str
    last_commit: str
    last_sync: str
    status: NodeSyncStatus
    commits_behind: int = 0
    commits_ahead: int = 0


@dataclass
class BreathCycle:
    """Один цикл дыхания сети."""
    cycle_id: int
    started_at: str
    completed_at: Optional[str] = None
    phase: BreathPhase = BreathPhase.INHALE
    nodes_synced: int = 0
    nodes_failed: int = 0
    data_transferred_bytes: int = 0


class NetworkBreathing:
    """
    Дыхание сети — синхронизация каждые 12 секунд.

    Книга Монтана:
    > "Видишь? Москва только что обновилась.
    > Через секунду — Амстердам получит те же данные.
    > Потом — Алматы. Петербург. Новосибирск."
    """

    # Константы из книги
    BREATH_INTERVAL_SEC = 12  # 12 секунд между циклами
    INHALE_DURATION_SEC = 4   # Вдох
    EXHALE_DURATION_SEC = 4   # Выдох
    PAUSE_DURATION_SEC = 4    # Пауза

    def __init__(self, nodes: List[str] = None):
        self.nodes = nodes or ["moscow", "amsterdam", "almaty", "spb", "novosibirsk"]
        self.node_states: Dict[str, SyncState] = {}
        self.cycles: List[BreathCycle] = []
        self.current_cycle: Optional[BreathCycle] = None
        self.is_breathing = False
        self.cycle_count = 0

        # Инициализация состояний узлов
        for node in self.nodes:
            self.node_states[node] = SyncState(
                node_id=node,
                last_commit=self._generate_commit_hash(),
                last_sync=datetime.now(timezone.utc).isoformat(),
                status=NodeSyncStatus.SYNCED
            )

    def _generate_commit_hash(self) -> str:
        """Сгенерировать hash коммита."""
        data = f"{time.time()}:{id(self)}"
        return hashlib.sha256(data.encode()).hexdigest()[:8]

    def start_breathing(self) -> None:
        """Начать дыхание сети."""
        self.is_breathing = True

    def stop_breathing(self) -> None:
        """Остановить дыхание сети."""
        self.is_breathing = False

    def inhale(self) -> Dict[str, bool]:
        """
        Вдох — pull данные от всех узлов.

        Returns:
            Результат pull для каждого узла
        """
        results = {}

        for node_id in self.nodes:
            state = self.node_states[node_id]

            if state.status == NodeSyncStatus.DISCONNECTED:
                results[node_id] = False
                continue

            # Симуляция pull
            state.last_sync = datetime.now(timezone.utc).isoformat()
            results[node_id] = True

        return results

    def exhale(self) -> Dict[str, bool]:
        """
        Выдох — push данные ко всем узлам.

        Returns:
            Результат push для каждого узла
        """
        results = {}
        new_commit = self._generate_commit_hash()

        for node_id in self.nodes:
            state = self.node_states[node_id]

            if state.status == NodeSyncStatus.DISCONNECTED:
                results[node_id] = False
                continue

            # Симуляция push
            state.last_commit = new_commit
            state.last_sync = datetime.now(timezone.utc).isoformat()
            state.status = NodeSyncStatus.SYNCED
            results[node_id] = True

        return results

    def breath_cycle(self) -> BreathCycle:
        """
        Выполнить один полный цикл дыхания.

        Returns:
            BreathCycle
        """
        self.cycle_count += 1

        cycle = BreathCycle(
            cycle_id=self.cycle_count,
            started_at=datetime.now(timezone.utc).isoformat(),
            phase=BreathPhase.INHALE
        )

        self.current_cycle = cycle

        # Вдох
        inhale_results = self.inhale()
        cycle.phase = BreathPhase.PAUSE

        # Выдох
        exhale_results = self.exhale()
        cycle.phase = BreathPhase.EXHALE

        # Подсчёт результатов
        cycle.nodes_synced = sum(1 for r in exhale_results.values() if r)
        cycle.nodes_failed = sum(1 for r in exhale_results.values() if not r)
        cycle.completed_at = datetime.now(timezone.utc).isoformat()

        self.cycles.append(cycle)
        self.current_cycle = None

        return cycle

    def watchdog_check(self) -> Dict:
        """
        Watchdog проверка всех узлов.

        Книга Монтана:
        > "Watchdog. Сервис, который следит за всеми."

        Returns:
            Отчёт watchdog
        """
        alerts = []
        healthy = []
        behind = []

        for node_id, state in self.node_states.items():
            if state.status == NodeSyncStatus.DISCONNECTED:
                alerts.append({
                    "node": node_id,
                    "alert": "disconnected",
                    "last_seen": state.last_sync
                })
            elif state.status == NodeSyncStatus.BEHIND:
                behind.append({
                    "node": node_id,
                    "commits_behind": state.commits_behind
                })
            else:
                healthy.append(node_id)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "healthy_nodes": healthy,
            "behind_nodes": behind,
            "alerts": alerts,
            "total_nodes": len(self.nodes),
            "health_percentage": len(healthy) / len(self.nodes) * 100
        }

    def disconnect_node(self, node_id: str) -> None:
        """Симулировать отключение узла."""
        if node_id in self.node_states:
            self.node_states[node_id].status = NodeSyncStatus.DISCONNECTED

    def reconnect_node(self, node_id: str) -> None:
        """Восстановить узел."""
        if node_id in self.node_states:
            state = self.node_states[node_id]
            state.status = NodeSyncStatus.BEHIND
            state.commits_behind = self.cycle_count  # Примерно

    def get_breathing_status(self) -> Dict:
        """Статус дыхания сети."""
        return {
            "is_breathing": self.is_breathing,
            "cycle_interval_sec": self.BREATH_INTERVAL_SEC,
            "total_cycles": self.cycle_count,
            "current_phase": self.current_cycle.phase.value if self.current_cycle else "idle",
            "nodes": len(self.nodes),
            "last_cycle": self.cycles[-1].completed_at if self.cycles else None,
            "metaphor": "inhale (pull) → pause → exhale (push)"
        }


class Watchdog:
    """
    Watchdog — сервис наблюдения за сетью.

    Книга Монтана:
    > "Если кто-то отстал — подтягивает.
    > Если кто-то упал — поднимает тревогу."
    """

    def __init__(self, breathing: NetworkBreathing):
        self.breathing = breathing
        self.alerts: List[Dict] = []
        self.is_running = False

    def check(self) -> Dict:
        """Выполнить проверку."""
        report = self.breathing.watchdog_check()

        # Сохранить алерты
        if report["alerts"]:
            self.alerts.extend(report["alerts"])

        return report

    def auto_heal(self) -> int:
        """
        Автоматическое восстановление отставших узлов.

        Returns:
            Количество восстановленных узлов
        """
        healed = 0

        for node_id, state in self.breathing.node_states.items():
            if state.status == NodeSyncStatus.BEHIND:
                # Форсированная синхронизация
                state.last_commit = self.breathing._generate_commit_hash()
                state.last_sync = datetime.now(timezone.utc).isoformat()
                state.status = NodeSyncStatus.SYNCED
                state.commits_behind = 0
                healed += 1

        return healed


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    breathing = NetworkBreathing()
    watchdog = Watchdog(breathing)

    print("=" * 60)
    print("NETWORK BREATHING — Дыхание сети")
    print("=" * 60)
    print("\n'Каждые 12 секунд — синхронизация. Вдох — выдох.'")

    # Статус дыхания
    print("\n--- НАСТРОЙКИ ---")
    status = breathing.get_breathing_status()
    print(f"Интервал: {status['cycle_interval_sec']} секунд")
    print(f"Узлов: {status['nodes']}")
    print(f"Метафора: {status['metaphor']}")

    # Несколько циклов дыхания
    print("\n--- ЦИКЛЫ ДЫХАНИЯ ---")
    for i in range(3):
        cycle = breathing.breath_cycle()
        print(f"\nЦикл #{cycle.cycle_id}")
        print(f"  Фаза: INHALE → PAUSE → EXHALE")
        print(f"  Синхронизировано: {cycle.nodes_synced}/{len(breathing.nodes)}")
        print(f"  Время: {cycle.started_at[:19]} → {cycle.completed_at[:19]}")

    # Watchdog проверка
    print("\n--- WATCHDOG ---")
    report = watchdog.check()
    print(f"Здоровые узлы: {', '.join(report['healthy_nodes'])}")
    print(f"Здоровье сети: {report['health_percentage']:.0f}%")

    # Симуляция отключения
    print("\n--- СИМУЛЯЦИЯ ОТКЛЮЧЕНИЯ SPB ---")
    breathing.disconnect_node("spb")

    report = watchdog.check()
    print(f"Алертов: {len(report['alerts'])}")
    if report["alerts"]:
        for alert in report["alerts"]:
            print(f"  ⚠️  {alert['node']}: {alert['alert']}")

    # Автовосстановление
    print("\n--- АВТОВОССТАНОВЛЕНИЕ ---")
    breathing.reconnect_node("spb")
    healed = watchdog.auto_heal()
    print(f"Восстановлено узлов: {healed}")

    # Финальный статус
    print("\n--- ФИНАЛЬНЫЙ СТАТУС ---")
    report = watchdog.check()
    print(f"Здоровье сети: {report['health_percentage']:.0f}%")
    print(f"Всего циклов: {breathing.cycle_count}")

    print("\n" + "=" * 60)
    print("'Пять узлов. Один организм. Одно дыхание.'")
    print("=" * 60)
