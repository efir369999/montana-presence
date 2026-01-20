#!/usr/bin/env python3
"""
test_presence_cache.py — Unit tests для presence_cache.py

Montana Protocol
Тестирование кэша присутствия участников
"""

import sys
import os
import unittest
import time
import threading
from typing import Dict, Any

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../экономика/банк_времени/код'))
from presence_cache import PresenceCache


class TestPresenceCacheBasic(unittest.TestCase):
    """Базовые тесты PresenceCache"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         GET/SET OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def test_set_and_get(self):
        """Установка и получение записи"""
        data = {
            "address": "user_123",
            "presence_seconds": 100,
            "t2_seconds": 100,
            "last_activity": time.time(),
            "is_active": True
        }

        self.cache.set("user_123", data)
        result = self.cache.get("user_123")

        self.assertIsNotNone(result)
        self.assertEqual(result["address"], "user_123")
        self.assertEqual(result["t2_seconds"], 100)
        self.assertTrue(result["is_active"])

    def test_get_nonexistent(self):
        """Получение несуществующей записи"""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_set_overwrite(self):
        """Перезапись существующей записи"""
        data1 = {"t2_seconds": 100, "is_active": True}
        data2 = {"t2_seconds": 200, "is_active": False}

        self.cache.set("user_123", data1)
        self.cache.set("user_123", data2)

        result = self.cache.get("user_123")
        self.assertEqual(result["t2_seconds"], 200)
        self.assertFalse(result["is_active"])

    # ═══════════════════════════════════════════════════════════════════════
    #                         REMOVE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def test_remove_existing(self):
        """Удаление существующей записи"""
        self.cache.set("user_123", {"t2_seconds": 100})
        self.assertIn("user_123", self.cache)

        self.cache.remove("user_123")
        self.assertNotIn("user_123", self.cache)
        self.assertIsNone(self.cache.get("user_123"))

    def test_remove_nonexistent(self):
        """Удаление несуществующей записи (не должно вызывать ошибку)"""
        # Не должно выбросить исключение
        self.cache.remove("nonexistent")
        self.assertEqual(len(self.cache), 0)

    def test_remove_from_empty_cache(self):
        """Удаление из пустого кэша"""
        self.cache.remove("user_123")
        self.assertEqual(len(self.cache), 0)

    # ═══════════════════════════════════════════════════════════════════════
    #                         LENGTH AND CONTAINS
    # ═══════════════════════════════════════════════════════════════════════

    def test_len_empty(self):
        """Длина пустого кэша"""
        self.assertEqual(len(self.cache), 0)

    def test_len_with_entries(self):
        """Длина кэша с записями"""
        self.cache.set("user_1", {"t2_seconds": 100})
        self.cache.set("user_2", {"t2_seconds": 200})
        self.cache.set("user_3", {"t2_seconds": 300})

        self.assertEqual(len(self.cache), 3)

    def test_contains_true(self):
        """Проверка наличия существующего адреса"""
        self.cache.set("user_123", {"t2_seconds": 100})
        self.assertIn("user_123", self.cache)
        self.assertTrue("user_123" in self.cache)

    def test_contains_false(self):
        """Проверка наличия несуществующего адреса"""
        self.assertNotIn("user_123", self.cache)
        self.assertFalse("user_123" in self.cache)

    # ═══════════════════════════════════════════════════════════════════════
    #                         ALL ENTRIES
    # ═══════════════════════════════════════════════════════════════════════

    def test_all_empty(self):
        """Получение всех записей из пустого кэша"""
        result = self.cache.all()
        self.assertEqual(result, {})
        self.assertIsInstance(result, dict)

    def test_all_with_entries(self):
        """Получение всех записей"""
        self.cache.set("user_1", {"t2_seconds": 100})
        self.cache.set("user_2", {"t2_seconds": 200})

        result = self.cache.all()

        self.assertEqual(len(result), 2)
        self.assertIn("user_1", result)
        self.assertIn("user_2", result)
        self.assertEqual(result["user_1"]["t2_seconds"], 100)
        self.assertEqual(result["user_2"]["t2_seconds"], 200)

    def test_all_returns_copy(self):
        """all() возвращает копию, не оригинал"""
        self.cache.set("user_1", {"t2_seconds": 100})

        result1 = self.cache.all()
        result2 = self.cache.all()

        # Должны быть разные объекты
        self.assertIsNot(result1, result2)

        # Изменение копии не должно влиять на кэш
        result1["user_1"]["t2_seconds"] = 999
        original = self.cache.get("user_1")
        self.assertEqual(original["t2_seconds"], 100)


class TestPresenceCacheActiveCount(unittest.TestCase):
    """Тесты подсчёта активных участников"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         COUNT ACTIVE
    # ═══════════════════════════════════════════════════════════════════════

    def test_count_active_empty(self):
        """Подсчёт активных в пустом кэше"""
        self.assertEqual(self.cache.count_active(), 0)

    def test_count_active_all_active(self):
        """Все участники активны"""
        self.cache.set("user_1", {"is_active": True})
        self.cache.set("user_2", {"is_active": True})
        self.cache.set("user_3", {"is_active": True})

        self.assertEqual(self.cache.count_active(), 3)

    def test_count_active_all_inactive(self):
        """Все участники неактивны"""
        self.cache.set("user_1", {"is_active": False})
        self.cache.set("user_2", {"is_active": False})

        self.assertEqual(self.cache.count_active(), 0)

    def test_count_active_mixed(self):
        """Смешанный случай: активные и неактивные"""
        self.cache.set("user_1", {"is_active": True})
        self.cache.set("user_2", {"is_active": False})
        self.cache.set("user_3", {"is_active": True})
        self.cache.set("user_4", {"is_active": False})
        self.cache.set("user_5", {"is_active": True})

        self.assertEqual(self.cache.count_active(), 3)

    def test_count_active_missing_field(self):
        """Участник без поля is_active считается неактивным"""
        self.cache.set("user_1", {"t2_seconds": 100})  # Нет is_active
        self.cache.set("user_2", {"is_active": True})

        self.assertEqual(self.cache.count_active(), 1)


class TestPresenceCacheTotalSeconds(unittest.TestCase):
    """Тесты подсчёта общих секунд"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         TOTAL SECONDS
    # ═══════════════════════════════════════════════════════════════════════

    def test_total_seconds_empty(self):
        """Общее количество секунд в пустом кэше"""
        self.assertEqual(self.cache.total_seconds(), 0)

    def test_total_seconds_single_user(self):
        """Один пользователь"""
        self.cache.set("user_1", {"t2_seconds": 600})
        self.assertEqual(self.cache.total_seconds(), 600)

    def test_total_seconds_multiple_users(self):
        """Несколько пользователей"""
        self.cache.set("user_1", {"t2_seconds": 100})
        self.cache.set("user_2", {"t2_seconds": 200})
        self.cache.set("user_3", {"t2_seconds": 300})

        self.assertEqual(self.cache.total_seconds(), 600)

    def test_total_seconds_missing_field(self):
        """Пользователь без t2_seconds считается как 0"""
        self.cache.set("user_1", {"t2_seconds": 100})
        self.cache.set("user_2", {})  # Нет t2_seconds
        self.cache.set("user_3", {"t2_seconds": 200})

        self.assertEqual(self.cache.total_seconds(), 300)

    def test_total_seconds_large_numbers(self):
        """Большие числа (1000 пользователей по 600 секунд)"""
        for i in range(1000):
            self.cache.set(f"user_{i}", {"t2_seconds": 600})

        self.assertEqual(self.cache.total_seconds(), 600_000)


class TestPresenceCacheClear(unittest.TestCase):
    """Тесты очистки кэша"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         CLEAR
    # ═══════════════════════════════════════════════════════════════════════

    def test_clear_empty(self):
        """Очистка пустого кэша"""
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)

    def test_clear_with_entries(self):
        """Очистка кэша с записями"""
        self.cache.set("user_1", {"t2_seconds": 100})
        self.cache.set("user_2", {"t2_seconds": 200})
        self.cache.set("user_3", {"t2_seconds": 300})

        self.assertEqual(len(self.cache), 3)

        self.cache.clear()

        self.assertEqual(len(self.cache), 0)
        self.assertEqual(self.cache.count_active(), 0)
        self.assertEqual(self.cache.total_seconds(), 0)
        self.assertNotIn("user_1", self.cache)

    def test_clear_idempotent(self):
        """Многократная очистка не вызывает ошибок"""
        self.cache.set("user_1", {"t2_seconds": 100})

        self.cache.clear()
        self.cache.clear()
        self.cache.clear()

        self.assertEqual(len(self.cache), 0)


class TestPresenceCacheEdgeCases(unittest.TestCase):
    """Тесты граничных случаев"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════

    def test_empty_address(self):
        """Пустой адрес"""
        self.cache.set("", {"t2_seconds": 100})

        self.assertIn("", self.cache)
        self.assertEqual(len(self.cache), 1)

        result = self.cache.get("")
        self.assertEqual(result["t2_seconds"], 100)

    def test_unicode_address(self):
        """Unicode символы в адресе"""
        address = "пользователь_123_蒙大拿_Ɉ"
        self.cache.set(address, {"t2_seconds": 100})

        self.assertIn(address, self.cache)
        result = self.cache.get(address)
        self.assertEqual(result["t2_seconds"], 100)

    def test_zero_seconds(self):
        """Ноль секунд присутствия"""
        self.cache.set("user_1", {"t2_seconds": 0})

        self.assertEqual(self.cache.total_seconds(), 0)
        self.assertEqual(len(self.cache), 1)

    def test_negative_seconds(self):
        """Отрицательные секунды (некорректные данные)"""
        self.cache.set("user_1", {"t2_seconds": -100})

        # Кэш не валидирует данные, хранит как есть
        self.assertEqual(self.cache.total_seconds(), -100)

    def test_none_data(self):
        """None как данные"""
        self.cache.set("user_1", None)

        result = self.cache.get("user_1")
        self.assertIsNone(result)

    def test_empty_dict_data(self):
        """Пустой словарь как данные"""
        self.cache.set("user_1", {})

        result = self.cache.get("user_1")
        self.assertEqual(result, {})
        self.assertEqual(len(self.cache), 1)


class TestPresenceCacheThreadSafety(unittest.TestCase):
    """Тесты потокобезопасности"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         THREAD SAFETY
    # ═══════════════════════════════════════════════════════════════════════

    def test_concurrent_writes(self):
        """Одновременная запись из нескольких потоков"""
        num_threads = 10
        num_writes = 100

        def write_worker(thread_id):
            for i in range(num_writes):
                address = f"user_{thread_id}_{i}"
                self.cache.set(address, {"t2_seconds": i})

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=write_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Должно быть num_threads * num_writes записей
        self.assertEqual(len(self.cache), num_threads * num_writes)

    def test_concurrent_reads(self):
        """Одновременное чтение из нескольких потоков"""
        # Подготовка данных
        for i in range(100):
            self.cache.set(f"user_{i}", {"t2_seconds": i})

        results = []

        def read_worker():
            for i in range(100):
                result = self.cache.get(f"user_{i}")
                results.append(result)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=read_worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Все чтения должны быть успешными
        self.assertEqual(len(results), 1000)  # 10 потоков × 100 чтений

    def test_concurrent_read_write(self):
        """Одновременное чтение и запись"""
        num_iterations = 1000

        def writer():
            for i in range(num_iterations):
                self.cache.set(f"user_{i}", {"t2_seconds": i})

        def reader():
            for i in range(num_iterations):
                self.cache.get(f"user_{i}")

        write_thread = threading.Thread(target=writer)
        read_thread = threading.Thread(target=reader)

        write_thread.start()
        read_thread.start()

        write_thread.join()
        read_thread.join()

        # Не должно быть race conditions или deadlocks
        self.assertGreater(len(self.cache), 0)

    def test_concurrent_clear(self):
        """Одновременная очистка из нескольких потоков"""
        # Подготовка данных
        for i in range(100):
            self.cache.set(f"user_{i}", {"t2_seconds": i})

        def clear_worker():
            self.cache.clear()

        threads = []
        for i in range(5):
            thread = threading.Thread(target=clear_worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # В конце кэш должен быть пустым
        self.assertEqual(len(self.cache), 0)


class TestPresenceCachePractical(unittest.TestCase):
    """Практические сценарии использования"""

    def setUp(self):
        """Создаём новый кэш перед каждым тестом"""
        self.cache = PresenceCache()

    # ═══════════════════════════════════════════════════════════════════════
    #                         PRACTICAL SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════

    def test_typical_session(self):
        """Типичная сессия: добавление, обновление, удаление"""
        # Пользователь заходит
        self.cache.set("user_123", {
            "address": "user_123",
            "t2_seconds": 0,
            "is_active": True,
            "last_activity": time.time()
        })

        self.assertEqual(len(self.cache), 1)
        self.assertEqual(self.cache.count_active(), 1)

        # Обновляем активность
        self.cache.set("user_123", {
            "address": "user_123",
            "t2_seconds": 600,
            "is_active": True,
            "last_activity": time.time()
        })

        self.assertEqual(self.cache.total_seconds(), 600)

        # Пользователь уходит
        self.cache.remove("user_123")

        self.assertEqual(len(self.cache), 0)
        self.assertEqual(self.cache.count_active(), 0)

    def test_multiple_users_scenario(self):
        """Сценарий с несколькими пользователями"""
        # 3 активных, 2 на паузе
        self.cache.set("user_1", {"t2_seconds": 600, "is_active": True})
        self.cache.set("user_2", {"t2_seconds": 300, "is_active": True})
        self.cache.set("user_3", {"t2_seconds": 450, "is_active": True})
        self.cache.set("user_4", {"t2_seconds": 200, "is_active": False})
        self.cache.set("user_5", {"t2_seconds": 150, "is_active": False})

        self.assertEqual(len(self.cache), 5)
        self.assertEqual(self.cache.count_active(), 3)
        self.assertEqual(self.cache.total_seconds(), 1700)  # 600+300+450+200+150

    def test_t2_reset_scenario(self):
        """Сценарий сброса τ₂ (каждые 10 минут)"""
        # Начальное состояние
        self.cache.set("user_1", {"t2_seconds": 600, "is_active": True})
        self.cache.set("user_2", {"t2_seconds": 450, "is_active": True})

        total_before = self.cache.total_seconds()
        self.assertEqual(total_before, 1050)

        # Сброс τ₂ — очищаем кэш
        self.cache.clear()

        self.assertEqual(len(self.cache), 0)
        self.assertEqual(self.cache.total_seconds(), 0)

        # Пользователи начинают новый τ₂
        self.cache.set("user_1", {"t2_seconds": 0, "is_active": True})
        self.cache.set("user_2", {"t2_seconds": 0, "is_active": True})

        self.assertEqual(len(self.cache), 2)
        self.assertEqual(self.cache.total_seconds(), 0)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
