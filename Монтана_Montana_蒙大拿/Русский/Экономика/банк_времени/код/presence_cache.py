"""
presence_cache.py — Кэш присутствия участников

Montana Protocol
Отслеживание присутствия пользователей в реальном времени
"""

import threading
from typing import Dict, Optional, Any


class PresenceCache:
    """
    Кэш присутствия по адресам (telegram_id или ip)

    Хранит информацию о присутствии каждого участника:
    - Адрес (telegram_id, ip, или другой идентификатор)
    - Секунды присутствия
    - Последняя активность
    - Статус (активен/пауза)
    """

    def __init__(self):
        self.entries: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Получить запись по адресу

        Args:
            address: Адрес участника

        Returns:
            Dict с данными присутствия или None
        """
        with self._lock:
            return self.entries.get(address)

    def set(self, address: str, data: Dict[str, Any]):
        """
        Установить запись

        Args:
            address: Адрес участника
            data: Данные присутствия
        """
        with self._lock:
            self.entries[address] = data

    def remove(self, address: str):
        """
        Удалить запись

        Args:
            address: Адрес участника
        """
        with self._lock:
            self.entries.pop(address, None)

    def all(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить все записи (копию)

        Returns:
            Dict всех записей присутствия
        """
        with self._lock:
            return dict(self.entries)

    def count_active(self) -> int:
        """
        Подсчитать количество активных участников

        Returns:
            Количество участников с is_active=True
        """
        with self._lock:
            return sum(1 for e in self.entries.values() if e.get("is_active"))

    def total_seconds(self) -> int:
        """
        Общее количество секунд присутствия всех участников за текущий τ₂

        Returns:
            Сумма t2_seconds всех участников
        """
        with self._lock:
            return sum(e.get("t2_seconds", 0) for e in self.entries.values())

    def clear(self):
        """Очистить весь кэш"""
        with self._lock:
            self.entries.clear()

    def __len__(self) -> int:
        """Количество участников в кэше"""
        with self._lock:
            return len(self.entries)

    def __contains__(self, address: str) -> bool:
        """Проверить наличие адреса в кэше"""
        with self._lock:
            return address in self.entries


# Экспорт
__all__ = ['PresenceCache']


if __name__ == "__main__":
    # Тесты
    import time

    cache = PresenceCache()

    # Добавляем участников
    cache.set("user_123", {
        "address": "user_123",
        "presence_seconds": 100,
        "t2_seconds": 100,
        "last_activity": time.time(),
        "is_active": True
    })

    cache.set("user_456", {
        "address": "user_456",
        "presence_seconds": 200,
        "t2_seconds": 200,
        "last_activity": time.time(),
        "is_active": True
    })

    cache.set("user_789", {
        "address": "user_789",
        "presence_seconds": 50,
        "t2_seconds": 50,
        "last_activity": time.time(),
        "is_active": False  # На паузе
    })

    # Проверяем
    print(f"Total participants: {len(cache)}")
    print(f"Active participants: {cache.count_active()}")
    print(f"Total T2 seconds: {cache.total_seconds()}")
    print(f"Contains user_123: {'user_123' in cache}")

    # Получаем все
    for address, entry in cache.all().items():
        status = "✅ Active" if entry['is_active'] else "⏸️ Paused"
        print(f"{address}: {entry['t2_seconds']} sec - {status}")
