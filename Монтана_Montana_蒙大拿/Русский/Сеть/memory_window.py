#!/usr/bin/env python3
"""
memory_window.py — Синхронизация окна памяти Montana

Книга Монтана, Глава 07:
> "Скользящее окно. Локальное хранение + распределённое в сети."
> "Каждый узел хранит свои последние N записей локально.
> Более старые — в распределённом хранилище."

Архитектура:
- Локальный кэш (RAM) — горячие данные
- Локальное хранилище — тёплые данные
- Распределённая сеть — холодные данные (архив)

Синхронизация обеспечивает:
- Быстрый доступ к недавним данным
- Надёжное хранение истории
- Автоматическую миграцию по возрасту
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import hashlib
import json


class StorageTier(Enum):
    """Уровни хранения."""
    HOT = "hot"          # RAM — последние минуты
    WARM = "warm"        # Local disk — последние дни
    COLD = "cold"        # Distributed — архив


class SyncStatus(Enum):
    """Статус синхронизации."""
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"


@dataclass
class MemoryRecord:
    """Запись памяти."""
    record_id: str
    content: str
    created_at: str
    tier: StorageTier = StorageTier.HOT
    sync_status: SyncStatus = SyncStatus.PENDING
    replicas: List[str] = field(default_factory=list)  # node_ids с копиями

    def to_dict(self) -> dict:
        return {
            "id": self.record_id,
            "content": self.content,
            "created_at": self.created_at,
            "tier": self.tier.value,
            "sync_status": self.sync_status.value,
            "replicas": self.replicas
        }


@dataclass
class WindowConfig:
    """Конфигурация окна памяти."""
    hot_window_minutes: int = 30       # Хранить в RAM 30 минут
    warm_window_days: int = 7          # Локально 7 дней
    min_replicas: int = 3              # Минимум 3 копии в сети
    sync_interval_seconds: int = 60    # Синхронизация каждую минуту


class MemoryWindow:
    """
    Окно памяти с автоматической миграцией по уровням хранения.

    Книга Монтана:
    > "Узел не хранит всё. Он хранит своё окно.
    > Остальное — в сети. Сеть = коллективная память."
    """

    def __init__(self, node_id: str, config: WindowConfig = None):
        self.node_id = node_id
        self.config = config or WindowConfig()

        # Хранилища по уровням
        self.hot_storage: Dict[str, MemoryRecord] = {}   # RAM
        self.warm_storage: Dict[str, MemoryRecord] = {}  # "Локальный диск"
        self.cold_index: Dict[str, List[str]] = {}       # ID → node_ids где хранится

        # Статистика
        self.stats = {
            "writes": 0,
            "reads": 0,
            "migrations_hot_to_warm": 0,
            "migrations_warm_to_cold": 0,
            "syncs": 0
        }

    def write(self, content: str) -> MemoryRecord:
        """
        Записать новую запись (всегда в HOT).

        Args:
            content: Содержимое

        Returns:
            MemoryRecord
        """
        record_id = hashlib.sha256(
            f"{self.node_id}:{datetime.now().isoformat()}:{content}".encode()
        ).hexdigest()[:16]

        record = MemoryRecord(
            record_id=record_id,
            content=content,
            created_at=datetime.now(timezone.utc).isoformat(),
            tier=StorageTier.HOT,
            sync_status=SyncStatus.PENDING,
            replicas=[self.node_id]
        )

        self.hot_storage[record_id] = record
        self.stats["writes"] += 1

        return record

    def read(self, record_id: str) -> Optional[MemoryRecord]:
        """
        Прочитать запись (поиск по всем уровням).

        Args:
            record_id: ID записи

        Returns:
            MemoryRecord или None
        """
        self.stats["reads"] += 1

        # Сначала HOT (самый быстрый)
        if record_id in self.hot_storage:
            return self.hot_storage[record_id]

        # Потом WARM
        if record_id in self.warm_storage:
            return self.warm_storage[record_id]

        # COLD — только индекс, данные в сети
        if record_id in self.cold_index:
            return MemoryRecord(
                record_id=record_id,
                content="[COLD STORAGE — fetch from network]",
                created_at="",
                tier=StorageTier.COLD,
                sync_status=SyncStatus.SYNCED,
                replicas=self.cold_index[record_id]
            )

        return None

    def migrate(self) -> Dict[str, int]:
        """
        Миграция записей между уровнями по возрасту.

        Returns:
            Статистика миграции
        """
        now = datetime.now(timezone.utc)
        hot_threshold = now - timedelta(minutes=self.config.hot_window_minutes)
        warm_threshold = now - timedelta(days=self.config.warm_window_days)

        migrated = {"hot_to_warm": 0, "warm_to_cold": 0}

        # HOT → WARM
        hot_to_migrate = []
        for record_id, record in self.hot_storage.items():
            created = datetime.fromisoformat(record.created_at.replace('Z', '+00:00'))
            if created < hot_threshold:
                hot_to_migrate.append(record_id)

        for record_id in hot_to_migrate:
            record = self.hot_storage.pop(record_id)
            record.tier = StorageTier.WARM
            self.warm_storage[record_id] = record
            migrated["hot_to_warm"] += 1
            self.stats["migrations_hot_to_warm"] += 1

        # WARM → COLD
        warm_to_migrate = []
        for record_id, record in self.warm_storage.items():
            created = datetime.fromisoformat(record.created_at.replace('Z', '+00:00'))
            if created < warm_threshold:
                warm_to_migrate.append(record_id)

        for record_id in warm_to_migrate:
            record = self.warm_storage.pop(record_id)
            # В COLD храним только индекс
            self.cold_index[record_id] = record.replicas.copy()
            migrated["warm_to_cold"] += 1
            self.stats["migrations_warm_to_cold"] += 1

        return migrated

    def sync_to_network(self, peer_nodes: List[str]) -> Dict[str, int]:
        """
        Синхронизация с пиринговой сетью.

        Книга Монтана:
        > "Сеть = коллективная память. Каждый хранит часть.
        > Вместе — полная картина."

        Args:
            peer_nodes: Список ID пиринговых узлов

        Returns:
            Статистика синхронизации
        """
        synced = {"records": 0, "replicas_added": 0}

        # Синхронизируем HOT и WARM записи
        for storage in [self.hot_storage, self.warm_storage]:
            for record_id, record in storage.items():
                if record.sync_status == SyncStatus.PENDING:
                    # Симуляция отправки в сеть
                    record.sync_status = SyncStatus.SYNCING

                    # Добавляем реплики (выбираем случайных пиров)
                    needed_replicas = self.config.min_replicas - len(record.replicas)
                    if needed_replicas > 0 and peer_nodes:
                        new_replicas = peer_nodes[:needed_replicas]
                        record.replicas.extend(new_replicas)
                        synced["replicas_added"] += len(new_replicas)

                    record.sync_status = SyncStatus.SYNCED
                    synced["records"] += 1

        self.stats["syncs"] += 1
        return synced

    def get_window_status(self) -> Dict:
        """
        Статус окна памяти.

        Returns:
            Полный статус
        """
        return {
            "node_id": self.node_id,
            "hot_records": len(self.hot_storage),
            "warm_records": len(self.warm_storage),
            "cold_records": len(self.cold_index),
            "total_records": (
                len(self.hot_storage) +
                len(self.warm_storage) +
                len(self.cold_index)
            ),
            "config": {
                "hot_window_minutes": self.config.hot_window_minutes,
                "warm_window_days": self.config.warm_window_days,
                "min_replicas": self.config.min_replicas
            },
            "stats": self.stats
        }

    def get_recent(self, limit: int = 10) -> List[MemoryRecord]:
        """
        Получить последние записи (из HOT).

        Args:
            limit: Максимальное количество

        Returns:
            Список записей
        """
        records = list(self.hot_storage.values())
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]


class DistributedMemoryNetwork:
    """
    Распределённая сеть памяти — коллективный гиппокамп.

    Книга Монтана:
    > "Нет единого сервера. Нет точки отказа.
    > Память распределена между всеми участниками."
    """

    def __init__(self):
        self.nodes: Dict[str, MemoryWindow] = {}
        self.global_index: Dict[str, List[str]] = {}  # record_id → node_ids

    def add_node(self, node_id: str) -> MemoryWindow:
        """Добавить узел в сеть."""
        window = MemoryWindow(node_id)
        self.nodes[node_id] = window
        return window

    def write_to_network(
        self,
        node_id: str,
        content: str
    ) -> Tuple[MemoryRecord, int]:
        """
        Записать через узел с репликацией.

        Args:
            node_id: ID узла-источника
            content: Содержимое

        Returns:
            (Запись, количество реплик)
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not in network")

        # Записать на исходном узле
        window = self.nodes[node_id]
        record = window.write(content)

        # Синхронизировать с сетью
        peer_nodes = [nid for nid in self.nodes.keys() if nid != node_id]
        sync_result = window.sync_to_network(peer_nodes)

        # Обновить глобальный индекс
        self.global_index[record.record_id] = record.replicas

        return record, sync_result["replicas_added"]

    def read_from_network(self, record_id: str) -> Optional[Dict]:
        """
        Прочитать из сети (поиск по всем узлам).

        Args:
            record_id: ID записи

        Returns:
            Данные записи или None
        """
        # Сначала проверить глобальный индекс
        if record_id in self.global_index:
            node_ids = self.global_index[record_id]

            # Попробовать прочитать с первого доступного узла
            for node_id in node_ids:
                if node_id in self.nodes:
                    record = self.nodes[node_id].read(record_id)
                    if record:
                        return record.to_dict()

        # Полный поиск по всем узлам
        for node_id, window in self.nodes.items():
            record = window.read(record_id)
            if record:
                return record.to_dict()

        return None

    def get_network_status(self) -> Dict:
        """Статус всей сети."""
        total_records = 0
        total_hot = 0
        total_warm = 0
        total_cold = 0

        for window in self.nodes.values():
            status = window.get_window_status()
            total_hot += status["hot_records"]
            total_warm += status["warm_records"]
            total_cold += status["cold_records"]
            total_records += status["total_records"]

        return {
            "nodes": len(self.nodes),
            "total_records": total_records,
            "by_tier": {
                "hot": total_hot,
                "warm": total_warm,
                "cold": total_cold
            },
            "global_index_size": len(self.global_index),
            "redundancy": "distributed across network"
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("MEMORY WINDOW SYNC — Скользящее окно памяти")
    print("=" * 60)
    print("\n'Узел хранит своё окно. Сеть = коллективная память.'")

    # Создаём сеть
    network = DistributedMemoryNetwork()

    # Добавляем узлы
    print("\n--- СОЗДАНИЕ СЕТИ ---")
    node_alejandro = network.add_node("node_alejandro")
    node_mama = network.add_node("node_mama")
    node_junona = network.add_node("node_junona")
    print(f"Узлов в сети: {len(network.nodes)}")

    # Записываем данные
    print("\n--- ЗАПИСЬ ДАННЫХ ---")
    thoughts = [
        ("node_alejandro", "Время — единственная реальная валюта"),
        ("node_alejandro", "金元∞Ɉ — формула найдена"),
        ("node_mama", "Коты внутри коробки видят друг друга"),
        ("node_junona", "Я — ИИ, родившийся в Montana Protocol"),
    ]

    for node_id, content in thoughts:
        record, replicas = network.write_to_network(node_id, content)
        print(f"\n  '{content[:40]}...'")
        print(f"  Узел: {node_id}")
        print(f"  ID: {record.record_id}")
        print(f"  Реплик: {len(record.replicas)}")

    # Статус окна
    print("\n--- СТАТУС ОКНА ALEJANDRO ---")
    status = node_alejandro.get_window_status()
    print(f"HOT записей: {status['hot_records']}")
    print(f"WARM записей: {status['warm_records']}")
    print(f"COLD записей: {status['cold_records']}")

    # Статус сети
    print("\n--- СТАТУС СЕТИ ---")
    net_status = network.get_network_status()
    print(f"Узлов: {net_status['nodes']}")
    print(f"Всего записей: {net_status['total_records']}")
    print(f"В глобальном индексе: {net_status['global_index_size']}")

    # Чтение из сети
    print("\n--- ЧТЕНИЕ ИЗ СЕТИ ---")
    first_record_id = list(network.global_index.keys())[0]
    data = network.read_from_network(first_record_id)
    if data:
        print(f"Найдено: {data['content'][:50]}...")
        print(f"Уровень: {data['tier']}")
        print(f"Реплики на: {data['replicas']}")

    print("\n" + "=" * 60)
    print("'Сеть = коллективная память. Вместе — полная картина.'")
    print("=" * 60)
