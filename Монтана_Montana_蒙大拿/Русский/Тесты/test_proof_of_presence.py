#!/usr/bin/env python3
"""
test_proof_of_presence.py — Unit tests для proof_of_presence.py

Montana Protocol
Тестирование механизма Proof of Presence (случайные проверки Face ID / Touch ID)
"""

import sys
import os
import unittest
import json
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../бот'))
from proof_of_presence import (
    ProofOfPresenceManager,
    get_pop_manager
)


class TestProofOfPresenceInit(unittest.TestCase):
    """Тесты инициализации ProofOfPresenceManager"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════

    def setUp(self):
        """Создаём временную директорию для тестов"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")

    def tearDown(self):
        """Очистка временных файлов"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    def test_init_creates_storage(self):
        """Инициализация создаёт файл хранения"""
        pop = ProofOfPresenceManager(storage_path=self.storage_path)

        self.assertTrue(os.path.exists(self.storage_path))

    def test_init_default_parameters(self):
        """Проверка дефолтных параметров"""
        pop = ProofOfPresenceManager(storage_path=self.storage_path)

        self.assertEqual(pop.base_interval, 40)  # 40 минут
        self.assertEqual(pop.randomness, 10)     # ±10 минут

    def test_init_custom_parameters(self):
        """Инициализация с кастомными параметрами"""
        pop = ProofOfPresenceManager(
            storage_path=self.storage_path,
            base_interval_minutes=30,
            randomness_minutes=5
        )

        self.assertEqual(pop.base_interval, 30)
        self.assertEqual(pop.randomness, 5)

    def test_init_creates_data_structure(self):
        """Инициализация создаёт правильную структуру данных"""
        pop = ProofOfPresenceManager(storage_path=self.storage_path)

        self.assertIn("users", pop.data)
        self.assertIn("checks", pop.data)
        self.assertIsInstance(pop.data["users"], dict)
        self.assertIsInstance(pop.data["checks"], list)

    def test_init_loads_existing_data(self):
        """Инициализация загружает существующие данные"""
        # Создаём файл с данными
        existing_data = {
            "users": {
                "123": {
                    "telegram_id": 123,
                    "username": "test_user"
                }
            },
            "checks": []
        }

        with open(self.storage_path, 'w') as f:
            json.dump(existing_data, f)

        pop = ProofOfPresenceManager(storage_path=self.storage_path)

        self.assertIn("123", pop.data["users"])
        self.assertEqual(pop.data["users"]["123"]["username"], "test_user")


class TestProofOfPresenceUserRegistration(unittest.TestCase):
    """Тесты регистрации пользователей"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(storage_path=self.storage_path)

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         USER REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_register_new_user(self):
        """Регистрация нового пользователя"""
        telegram_id = 123456789
        username = "test_user"

        self.pop.register_user(telegram_id, username)

        user_key = str(telegram_id)
        self.assertIn(user_key, self.pop.data["users"])

        user = self.pop.data["users"][user_key]
        self.assertEqual(user["telegram_id"], telegram_id)
        self.assertEqual(user["username"], username)
        self.assertEqual(user["status"], "active")
        self.assertEqual(user["checks_completed"], 0)
        self.assertEqual(user["checks_failed"], 0)
        self.assertIsNotNone(user["registered_at"])
        self.assertIsNotNone(user["next_check"])

    def test_register_user_idempotent(self):
        """Повторная регистрация не дублирует пользователя"""
        telegram_id = 123456789
        username = "test_user"

        self.pop.register_user(telegram_id, username)
        self.pop.register_user(telegram_id, username)  # Повторно

        user_key = str(telegram_id)
        self.assertEqual(len([k for k in self.pop.data["users"] if k == user_key]), 1)

    def test_register_user_sets_next_check(self):
        """Регистрация устанавливает следующую проверку"""
        telegram_id = 123456789

        self.pop.register_user(telegram_id, "user")

        user = self.pop.data["users"][str(telegram_id)]
        next_check = datetime.fromisoformat(user["next_check"])
        now = datetime.now(timezone.utc)

        # Следующая проверка должна быть в будущем
        self.assertGreater(next_check, now)

    def test_register_multiple_users(self):
        """Регистрация нескольких пользователей"""
        self.pop.register_user(111, "user1")
        self.pop.register_user(222, "user2")
        self.pop.register_user(333, "user3")

        self.assertEqual(len(self.pop.data["users"]), 3)
        self.assertIn("111", self.pop.data["users"])
        self.assertIn("222", self.pop.data["users"])
        self.assertIn("333", self.pop.data["users"])


class TestProofOfPresenceCheckDue(unittest.TestCase):
    """Тесты определения необходимости проверки"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(storage_path=self.storage_path)

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         CHECK DUE
    # ═══════════════════════════════════════════════════════════════════════

    def test_is_check_due_unregistered_user(self):
        """Проверка для незарегистрированного пользователя"""
        result = self.pop.is_check_due(999999)

        self.assertFalse(result)

    def test_is_check_due_time_not_yet(self):
        """Проверка когда время ещё не пришло"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        # Next check в будущем
        user = self.pop.data["users"][str(telegram_id)]
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user["next_check"] = future_time.isoformat()
        self.pop._save()

        result = self.pop.is_check_due(telegram_id)

        self.assertFalse(result)

    def test_is_check_due_time_has_come(self):
        """Проверка когда время пришло"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        # Next check в прошлом
        user = self.pop.data["users"][str(telegram_id)]
        past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        user["next_check"] = past_time.isoformat()
        self.pop._save()

        result = self.pop.is_check_due(telegram_id)

        self.assertTrue(result)

    def test_is_check_due_inactive_user(self):
        """Проверка для неактивного пользователя"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        # Делаем пользователя неактивным
        user = self.pop.data["users"][str(telegram_id)]
        user["status"] = "inactive"
        user["next_check"] = datetime.now(timezone.utc).isoformat()  # Время пришло
        self.pop._save()

        result = self.pop.is_check_due(telegram_id)

        # Неактивный пользователь — проверка не нужна
        self.assertFalse(result)


class TestProofOfPresenceRequestCheck(unittest.TestCase):
    """Тесты запроса проверки"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(storage_path=self.storage_path)

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         REQUEST CHECK
    # ═══════════════════════════════════════════════════════════════════════

    def test_request_check_success(self):
        """Успешный запрос проверки"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        result = self.pop.request_check(telegram_id)

        self.assertIn("check_id", result)
        self.assertIn("telegram_id", result)
        self.assertIn("requested_at", result)
        self.assertIn("expires_at", result)
        self.assertIn("message", result)
        self.assertEqual(result["telegram_id"], telegram_id)

    def test_request_check_creates_check(self):
        """Запрос создаёт check в данных"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        before_count = len(self.pop.data["checks"])

        self.pop.request_check(telegram_id)

        after_count = len(self.pop.data["checks"])
        self.assertEqual(after_count, before_count + 1)

    def test_request_check_unregistered_user(self):
        """Запрос проверки для незарегистрированного пользователя"""
        telegram_id = 999999

        with self.assertRaises(ValueError):
            self.pop.request_check(telegram_id)

    def test_request_check_expires_in_5_minutes(self):
        """Проверка истекает через 5 минут"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        result = self.pop.request_check(telegram_id)

        requested_at = datetime.fromisoformat(result["requested_at"])
        expires_at = datetime.fromisoformat(result["expires_at"])

        duration = expires_at - requested_at
        self.assertAlmostEqual(duration.total_seconds(), 5 * 60, delta=1)

    def test_request_check_id_format(self):
        """Формат check_id"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        result = self.pop.request_check(telegram_id)

        check_id = result["check_id"]
        self.assertTrue(check_id.startswith("pop_"))
        self.assertIn(str(telegram_id), check_id)


class TestProofOfPresenceVerifyCheck(unittest.TestCase):
    """Тесты верификации проверки"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(storage_path=self.storage_path)

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         VERIFY CHECK
    # ═══════════════════════════════════════════════════════════════════════

    @patch.object(ProofOfPresenceManager, '_save')
    def test_verify_check_success(self, mock_save):
        """Успешная верификация"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        # Регистрируем биометрию
        self.pop.fido.register_biometric(telegram_id, "Test Device")

        # Запрашиваем проверку
        check_data = self.pop.request_check(telegram_id)
        check_id = check_data["check_id"]

        # Верифицируем
        result = self.pop.verify_check(telegram_id, check_id)

        self.assertTrue(result)

    def test_verify_check_updates_user_stats(self):
        """Верификация обновляет статистику пользователя"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")
        self.pop.fido.register_biometric(telegram_id, "Test Device")

        check_data = self.pop.request_check(telegram_id)
        check_id = check_data["check_id"]

        before_checks = self.pop.data["users"][str(telegram_id)]["checks_completed"]

        self.pop.verify_check(telegram_id, check_id)

        after_checks = self.pop.data["users"][str(telegram_id)]["checks_completed"]
        self.assertEqual(after_checks, before_checks + 1)

    def test_verify_check_nonexistent(self):
        """Верификация несуществующей проверки"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        result = self.pop.verify_check(telegram_id, "nonexistent_check_id")

        self.assertFalse(result)

    def test_verify_check_expired(self):
        """Верификация истёкшей проверки"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")
        self.pop.fido.register_biometric(telegram_id, "Test Device")

        check_data = self.pop.request_check(telegram_id)
        check_id = check_data["check_id"]

        # Делаем проверку истёкшей
        for check in self.pop.data["checks"]:
            if check["check_id"] == check_id:
                past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
                check["expires_at"] = past_time.isoformat()
                break

        result = self.pop.verify_check(telegram_id, check_id)

        self.assertFalse(result)

        # Должен увеличить failed checks
        user = self.pop.data["users"][str(telegram_id)]
        self.assertEqual(user["checks_failed"], 1)

    @patch.object(ProofOfPresenceManager, '_save')
    def test_verify_check_no_biometric(self, mock_save):
        """Верификация без зарегистрированной биометрии"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        check_data = self.pop.request_check(telegram_id)
        check_id = check_data["check_id"]

        # НЕ регистрируем биометрию
        result = self.pop.verify_check(telegram_id, check_id)

        # Должно быть False (нет биометрии)
        self.assertFalse(result)


class TestProofOfPresenceUserStatus(unittest.TestCase):
    """Тесты получения статуса пользователя"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(storage_path=self.storage_path)

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         USER STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def test_get_user_status_registered(self):
        """Получение статуса зарегистрированного пользователя"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "test_user")

        status = self.pop.get_user_status(telegram_id)

        self.assertIsNotNone(status)
        self.assertEqual(status["telegram_id"], telegram_id)
        self.assertEqual(status["username"], "test_user")

    def test_get_user_status_unregistered(self):
        """Получение статуса незарегистрированного пользователя"""
        status = self.pop.get_user_status(999999)

        self.assertIsNone(status)

    def test_get_user_status_fields(self):
        """Проверка полей в статусе"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        status = self.pop.get_user_status(telegram_id)

        self.assertIn("telegram_id", status)
        self.assertIn("username", status)
        self.assertIn("registered_at", status)
        self.assertIn("last_check", status)
        self.assertIn("next_check", status)
        self.assertIn("checks_completed", status)
        self.assertIn("checks_failed", status)
        self.assertIn("status", status)


class TestProofOfPresencePendingChecks(unittest.TestCase):
    """Тесты получения незавершённых проверок"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(storage_path=self.storage_path)

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         PENDING CHECKS
    # ═══════════════════════════════════════════════════════════════════════

    def test_get_pending_checks_empty(self):
        """Получение pending checks когда их нет"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        pending = self.pop.get_pending_checks(telegram_id)

        self.assertEqual(len(pending), 0)

    def test_get_pending_checks_one(self):
        """Получение одной pending check"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        self.pop.request_check(telegram_id)

        pending = self.pop.get_pending_checks(telegram_id)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["telegram_id"], telegram_id)
        self.assertFalse(pending[0]["completed"])

    def test_get_pending_checks_multiple(self):
        """Получение нескольких pending checks"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        self.pop.request_check(telegram_id)
        self.pop.request_check(telegram_id)
        self.pop.request_check(telegram_id)

        pending = self.pop.get_pending_checks(telegram_id)

        self.assertEqual(len(pending), 3)

    def test_get_pending_checks_filters_completed(self):
        """pending checks не включает завершённые"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")
        self.pop.fido.register_biometric(telegram_id, "Device")

        # Создаём 2 проверки
        check1 = self.pop.request_check(telegram_id)
        check2 = self.pop.request_check(telegram_id)

        # Завершаем одну
        self.pop.verify_check(telegram_id, check1["check_id"])

        pending = self.pop.get_pending_checks(telegram_id)

        # Должна быть только 1 незавершённая
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["check_id"], check2["check_id"])

    def test_get_pending_checks_filters_expired(self):
        """pending checks не включает истёкшие"""
        telegram_id = 123456789
        self.pop.register_user(telegram_id, "user")

        check_data = self.pop.request_check(telegram_id)

        # Делаем проверку истёкшей
        for check in self.pop.data["checks"]:
            if check["check_id"] == check_data["check_id"]:
                past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
                check["expires_at"] = past_time.isoformat()
                break

        pending = self.pop.get_pending_checks(telegram_id)

        # Истёкшая не должна быть в pending
        self.assertEqual(len(pending), 0)


class TestProofOfPresenceRandomness(unittest.TestCase):
    """Тесты случайности проверок"""

    def setUp(self):
        """Создаём ProofOfPresenceManager для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "pop_test.json")
        self.pop = ProofOfPresenceManager(
            storage_path=self.storage_path,
            base_interval_minutes=40,
            randomness_minutes=10
        )

    def tearDown(self):
        """Очистка"""
        if os.path.exists(self.storage_path):
            os.remove(self.storage_path)
        os.rmdir(self.temp_dir)

    # ═══════════════════════════════════════════════════════════════════════
    #                         RANDOMNESS
    # ═══════════════════════════════════════════════════════════════════════

    def test_next_check_time_in_range(self):
        """Следующая проверка в диапазоне base ± randomness"""
        now = datetime.now(timezone.utc)

        # Генерируем несколько next check times
        next_times = [self.pop._get_next_check_time() for _ in range(10)]

        for next_time in next_times:
            duration = (next_time - now).total_seconds() / 60

            # Должно быть в диапазоне [30, 50] минут (40 ± 10)
            self.assertGreaterEqual(duration, 30)
            self.assertLessEqual(duration, 50)

    def test_next_check_time_varies(self):
        """Следующая проверка варьируется (не всегда одинаковая)"""
        times = [self.pop._get_next_check_time() for _ in range(20)]

        # Должно быть больше 1 уникального значения
        unique_times = set([t.isoformat() for t in times])
        self.assertGreater(len(unique_times), 1)


class TestProofOfPresenceFactory(unittest.TestCase):
    """Тесты фабричной функции"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         FACTORY
    # ═══════════════════════════════════════════════════════════════════════

    def test_get_pop_manager_returns_instance(self):
        """get_pop_manager() возвращает экземпляр"""
        pop = get_pop_manager()

        self.assertIsNotNone(pop)
        self.assertIsInstance(pop, ProofOfPresenceManager)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
