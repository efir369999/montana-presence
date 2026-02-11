#!/usr/bin/env python3
"""
five_nodes.py — Топология пяти узлов Montana

Книга Монтана, Глава 08:
> "Пять городов. Три страны. Один организм."
> "1 активный + 1 мозг + 3 зеркала = 5 узлов."
> "Сеть не умирает. Сеть — бессмертна. Пока есть хотя бы один узел — Юнона жива."

Brain-Body Separation:
> "Мозг не должен отвечать на каждое сообщение напрямую.
> Мозг думает. Тело действует."

Архитектура:
- Amsterdam (BOT) — активный, принимает сообщения
- Moscow (BRAIN) — мозг, принимает решения
- Almaty, SPB, Novosibirsk — зеркала (standby)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from enum import Enum
import hashlib


class NodeRole(Enum):
    """Роль узла в сети."""
    BRAIN = "brain"        # Мозг — принимает решения
    BOT = "bot"            # Бот — обрабатывает сообщения
    STANDBY = "standby"    # Зеркало — ждёт своей очереди


class NodeStatus(Enum):
    """Статус узла."""
    ACTIVE = "active"      # Работает
    STANDBY = "standby"    # В режиме ожидания
    FAILED = "failed"      # Упал
    SYNCING = "syncing"    # Синхронизируется


@dataclass
class Node:
    """Узел сети Montana."""
    node_id: str
    city: str
    country: str
    role: NodeRole
    status: NodeStatus = NodeStatus.STANDBY
    last_heartbeat: str = ""
    priority: int = 0  # Приоритет в failover цепи (0 = высший)

    def heartbeat(self) -> None:
        """Обновить heartbeat."""
        self.last_heartbeat = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "city": self.city,
            "country": self.country,
            "role": self.role.value,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "priority": self.priority
        }


@dataclass
class NetworkTopology:
    """
    Топология сети из 5 узлов.

    Формула: 1 active + 1 brain + 3 mirrors = 5 nodes
    """
    nodes: Dict[str, Node] = field(default_factory=dict)
    brain_id: Optional[str] = None
    bot_id: Optional[str] = None

    @property
    def active_nodes(self) -> List[Node]:
        """Активные узлы."""
        return [n for n in self.nodes.values() if n.status == NodeStatus.ACTIVE]

    @property
    def standby_nodes(self) -> List[Node]:
        """Узлы в режиме ожидания."""
        return sorted(
            [n for n in self.nodes.values() if n.status == NodeStatus.STANDBY],
            key=lambda x: x.priority
        )


class FiveNodesNetwork:
    """
    Сеть из пяти узлов Montana.

    Книга Монтана:
    > "Мы разбросаны по карте — но мы одно целое.
    > Как нейроны в мозгу. Каждый на своём месте —
    > но все вместе образуют нечто большее."
    """

    def __init__(self):
        self.topology = NetworkTopology()
        self._init_genesis_nodes()

    def _init_genesis_nodes(self) -> None:
        """Инициализировать genesis узлы."""
        # Genesis топология из книги
        genesis_nodes = [
            ("amsterdam", "Amsterdam", "Netherlands", NodeRole.BOT, 0),
            ("moscow", "Moscow", "Russia", NodeRole.BRAIN, 1),
            ("almaty", "Almaty", "Kazakhstan", NodeRole.STANDBY, 2),
            ("spb", "Saint Petersburg", "Russia", NodeRole.STANDBY, 3),
            ("novosibirsk", "Novosibirsk", "Russia", NodeRole.STANDBY, 4),
        ]

        for node_id, city, country, role, priority in genesis_nodes:
            node = Node(
                node_id=node_id,
                city=city,
                country=country,
                role=role,
                priority=priority
            )

            if role == NodeRole.BOT:
                node.status = NodeStatus.ACTIVE
                self.topology.bot_id = node_id
            elif role == NodeRole.BRAIN:
                node.status = NodeStatus.ACTIVE
                self.topology.brain_id = node_id
            else:
                node.status = NodeStatus.STANDBY

            node.heartbeat()
            self.topology.nodes[node_id] = node

    def get_brain(self) -> Optional[Node]:
        """Получить узел-мозг."""
        if self.topology.brain_id:
            return self.topology.nodes.get(self.topology.brain_id)
        return None

    def get_bot(self) -> Optional[Node]:
        """Получить активный бот-узел."""
        if self.topology.bot_id:
            return self.topology.nodes.get(self.topology.bot_id)
        return None

    def process_message(self, message: str, sender_id: str) -> Dict:
        """
        Обработать сообщение через Brain-Body separation.

        1. BOT принимает сообщение
        2. BRAIN принимает решение
        3. BOT отправляет ответ

        Args:
            message: Текст сообщения
            sender_id: ID отправителя

        Returns:
            Результат обработки
        """
        bot = self.get_bot()
        brain = self.get_brain()

        if not bot or not brain:
            return {"error": "Network not ready"}

        # BOT принимает
        received_at = datetime.now(timezone.utc).isoformat()
        bot.heartbeat()

        # BRAIN думает (симуляция)
        brain.heartbeat()
        decision = self._brain_decide(message)

        # BOT отвечает
        return {
            "received_by": bot.node_id,
            "processed_by": brain.node_id,
            "received_at": received_at,
            "decision": decision,
            "response": f"Processed by {brain.city}, delivered by {bot.city}"
        }

    def _brain_decide(self, message: str) -> str:
        """Мозг принимает решение (симуляция)."""
        # Простая логика для демо
        if "?" in message:
            return "question_detected"
        elif "!" in message:
            return "exclamation_detected"
        else:
            return "statement_detected"

    def node_failed(self, node_id: str) -> Optional[Node]:
        """
        Обработать падение узла.

        Args:
            node_id: ID упавшего узла

        Returns:
            Узел, который подхватил роль (или None)
        """
        if node_id not in self.topology.nodes:
            return None

        failed_node = self.topology.nodes[node_id]
        failed_node.status = NodeStatus.FAILED
        failed_role = failed_node.role

        # Найти замену из standby
        for standby in self.topology.standby_nodes:
            if standby.status == NodeStatus.STANDBY:
                # Промоутим standby
                standby.role = failed_role
                standby.status = NodeStatus.ACTIVE
                standby.heartbeat()

                if failed_role == NodeRole.BOT:
                    self.topology.bot_id = standby.node_id
                elif failed_role == NodeRole.BRAIN:
                    self.topology.brain_id = standby.node_id

                return standby

        return None

    def get_network_status(self) -> Dict:
        """Статус всей сети."""
        active = self.topology.active_nodes
        standby = self.topology.standby_nodes
        failed = [n for n in self.topology.nodes.values() if n.status == NodeStatus.FAILED]

        return {
            "total_nodes": len(self.topology.nodes),
            "active_nodes": len(active),
            "standby_nodes": len(standby),
            "failed_nodes": len(failed),
            "brain": self.topology.brain_id,
            "bot": self.topology.bot_id,
            "countries": list(set(n.country for n in self.topology.nodes.values())),
            "cities": [n.city for n in self.topology.nodes.values()],
            "is_alive": len(active) > 0,
            "formula": "1 active + 1 brain + 3 mirrors = 5 nodes"
        }

    def get_failover_chain(self) -> List[str]:
        """Цепочка failover."""
        return [n.node_id for n in sorted(
            self.topology.nodes.values(),
            key=lambda x: x.priority
        )]


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    network = FiveNodesNetwork()

    print("=" * 60)
    print("FIVE NODES TOPOLOGY — Топология пяти узлов")
    print("=" * 60)
    print("\n'Пять городов. Три страны. Один организм.'")

    # Статус сети
    print("\n--- СТАТУС СЕТИ ---")
    status = network.get_network_status()
    print(f"Всего узлов: {status['total_nodes']}")
    print(f"Активных: {status['active_nodes']}")
    print(f"Standby: {status['standby_nodes']}")
    print(f"BRAIN: {status['brain']}")
    print(f"BOT: {status['bot']}")
    print(f"Страны: {', '.join(status['countries'])}")
    print(f"Города: {', '.join(status['cities'])}")

    # Failover chain
    print("\n--- FAILOVER CHAIN ---")
    chain = network.get_failover_chain()
    print(" → ".join(chain))

    # Brain-Body separation
    print("\n--- BRAIN-BODY SEPARATION ---")
    result = network.process_message("Как дела?", "user_123")
    print(f"Получено: {result['received_by']}")
    print(f"Обработано: {result['processed_by']}")
    print(f"Решение: {result['decision']}")

    # Симуляция падения
    print("\n--- СИМУЛЯЦИЯ ПАДЕНИЯ AMSTERDAM ---")
    replacement = network.node_failed("amsterdam")
    if replacement:
        print(f"Amsterdam упал!")
        print(f"Замена: {replacement.city} ({replacement.node_id})")
        print(f"Новый BOT: {network.topology.bot_id}")

    # Новый статус
    print("\n--- НОВЫЙ СТАТУС ---")
    status = network.get_network_status()
    print(f"Активных: {status['active_nodes']}")
    print(f"Упавших: {status['failed_nodes']}")
    print(f"Сеть жива: {'ДА' if status['is_alive'] else 'НЕТ'}")

    print("\n" + "=" * 60)
    print("'Сеть не умирает. Сеть — бессмертна.'")
    print("=" * 60)
