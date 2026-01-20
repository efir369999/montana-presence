#!/usr/bin/env python3
"""
test_breathing_sync.py — Unit tests для breathing_sync.py

Montana Protocol
Тестирование механизма Breathing Synchronization (12-секундный цикл git sync)
"""

import sys
import os
import unittest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../бот'))
from breathing_sync import (
    BreathingConfig,
    BreathingSync,
    get_breathing_sync
)


class TestBreathingConfig(unittest.TestCase):
    """Тесты конфигурации Breathing Sync"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         КОНСТАНТЫ
    # ═══════════════════════════════════════════════════════════════════════

    def test_sync_interval(self):
        """Интервал синхронизации = 12 секунд"""
        self.assertEqual(BreathingConfig.SYNC_INTERVAL_SEC, 12)

    def test_startup_delay(self):
        """Задержка перед первой синхронизацией = 5 секунд"""
        self.assertEqual(BreathingConfig.STARTUP_DELAY_SEC, 5)

    def test_remote_name(self):
        """Git remote = origin"""
        self.assertEqual(BreathingConfig.REMOTE_NAME, "origin")

    def test_branch_name(self):
        """Git branch = main"""
        self.assertEqual(BreathingConfig.BRANCH_NAME, "main")

    def test_git_timeout(self):
        """Таймаут git операций = 30 секунд"""
        self.assertEqual(BreathingConfig.GIT_TIMEOUT_SEC, 30)

    def test_sync_paths(self):
        """Проверка списка синхронизируемых файлов"""
        self.assertIsInstance(BreathingConfig.SYNC_PATHS, list)
        self.assertIn("data/users.json", BreathingConfig.SYNC_PATHS)
        self.assertIn("node_crypto/nodes.json", BreathingConfig.SYNC_PATHS)


class TestBreathingSyncInit(unittest.TestCase):
    """Тесты инициализации BreathingSync"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_init_default_path(self):
        """Инициализация с дефолтным путём"""
        sync = BreathingSync()

        self.assertIsNotNone(sync.repo_path)
        self.assertIsInstance(sync.repo_path, Path)
        self.assertFalse(sync._running)

    def test_init_custom_path(self):
        """Инициализация с кастомным путём"""
        custom_path = Path("/tmp/montana_test")
        sync = BreathingSync(repo_path=custom_path)

        self.assertEqual(sync.repo_path, custom_path)

    def test_init_stats(self):
        """Инициализация создаёт статистику"""
        sync = BreathingSync()

        self.assertIsInstance(sync.stats, dict)
        self.assertEqual(sync.stats["total_inhales"], 0)
        self.assertEqual(sync.stats["total_exhales"], 0)
        self.assertEqual(sync.stats["failed_inhales"], 0)
        self.assertEqual(sync.stats["failed_exhales"], 0)
        self.assertIsNone(sync.stats["last_inhale"])
        self.assertIsNone(sync.stats["last_exhale"])
        self.assertIsNone(sync.stats["last_error"])

    def test_init_stop_event(self):
        """Инициализация создаёт stop event"""
        sync = BreathingSync()

        self.assertIsInstance(sync._stop_event, asyncio.Event)
        self.assertFalse(sync._stop_event.is_set())


class TestBreathingSyncGitCommand(unittest.TestCase):
    """Тесты выполнения git команд"""

    def setUp(self):
        """Создаём BreathingSync перед каждым тестом"""
        self.sync = BreathingSync()

    # ═══════════════════════════════════════════════════════════════════════
    #                         GIT COMMAND EXECUTION
    # ═══════════════════════════════════════════════════════════════════════

    @patch('breathing_sync.subprocess.run')
    def test_run_git_command_success(self, mock_run):
        """Успешное выполнение git команды"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Already up to date.",
            stderr=""
        )

        result = self.sync._run_git_command(["pull"])

        self.assertTrue(result["success"])
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "Already up to date.")
        self.assertEqual(result["stderr"], "")

    @patch('breathing_sync.subprocess.run')
    def test_run_git_command_failure(self, mock_run):
        """Неудачное выполнение git команды"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="fatal: not a git repository"
        )

        result = self.sync._run_git_command(["status"])

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], 1)
        self.assertIn("not a git repository", result["stderr"])

    @patch('breathing_sync.subprocess.run')
    def test_run_git_command_timeout(self, mock_run):
        """Таймаут git команды"""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("git", 30)

        result = self.sync._run_git_command(["pull"], timeout=30)

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], -1)
        self.assertIn("Timeout", result["stderr"])

    @patch('breathing_sync.subprocess.run')
    def test_run_git_command_exception(self, mock_run):
        """Исключение при выполнении git команды"""
        mock_run.side_effect = Exception("Network error")

        result = self.sync._run_git_command(["fetch"])

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], -1)
        self.assertIn("Network error", result["stderr"])

    @patch('breathing_sync.subprocess.run')
    def test_run_git_command_uses_correct_path(self, mock_run):
        """Git команда выполняется в правильной директории"""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        custom_path = Path("/custom/repo")
        sync = BreathingSync(repo_path=custom_path)
        sync._run_git_command(["status"])

        # Проверяем что git вызван с правильным -C флагом
        call_args = mock_run.call_args[0][0]
        self.assertIn("-C", call_args)
        self.assertIn(str(custom_path), call_args)


class TestBreathingSyncInhale(unittest.TestCase):
    """Тесты inhale (git pull)"""

    def setUp(self):
        """Создаём BreathingSync перед каждым тестом"""
        self.sync = BreathingSync()

    # ═══════════════════════════════════════════════════════════════════════
    #                         INHALE (GIT PULL)
    # ═══════════════════════════════════════════════════════════════════════

    @patch.object(BreathingSync, '_run_git_command')
    def test_inhale_success(self, mock_git):
        """Успешный inhale (получены изменения)"""
        mock_git.return_value = {
            "success": True,
            "stdout": "Updating abc123..def456",
            "stderr": "",
            "returncode": 0
        }

        result = self.sync.inhale()

        self.assertTrue(result)
        self.assertEqual(self.sync.stats["total_inhales"], 1)
        self.assertEqual(self.sync.stats["failed_inhales"], 0)
        self.assertIsNotNone(self.sync.stats["last_inhale"])

    @patch.object(BreathingSync, '_run_git_command')
    def test_inhale_already_up_to_date(self, mock_git):
        """Inhale когда уже up to date"""
        mock_git.return_value = {
            "success": True,
            "stdout": "Already up to date.",
            "stderr": "",
            "returncode": 0
        }

        result = self.sync.inhale()

        self.assertTrue(result)
        self.assertEqual(self.sync.stats["total_inhales"], 1)

    @patch.object(BreathingSync, '_run_git_command')
    def test_inhale_failure(self, mock_git):
        """Неудачный inhale"""
        mock_git.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "error: cannot pull",
            "returncode": 1
        }

        result = self.sync.inhale()

        self.assertFalse(result)
        self.assertEqual(self.sync.stats["total_inhales"], 1)
        self.assertEqual(self.sync.stats["failed_inhales"], 1)
        self.assertEqual(self.sync.stats["last_error"], "error: cannot pull")

    @patch.object(BreathingSync, '_run_git_command')
    def test_inhale_uses_rebase(self, mock_git):
        """Inhale использует --rebase"""
        mock_git.return_value = {
            "success": True,
            "stdout": "Already up to date.",
            "stderr": "",
            "returncode": 0
        }

        self.sync.inhale()

        # Проверяем что вызван git pull с --rebase
        call_args = mock_git.call_args[0][0]
        self.assertIn("pull", call_args)
        self.assertIn("--rebase", call_args)
        self.assertIn("origin", call_args)
        self.assertIn("main", call_args)


class TestBreathingSyncExhale(unittest.TestCase):
    """Тесты exhale (git push)"""

    def setUp(self):
        """Создаём BreathingSync перед каждым тестом"""
        self.sync = BreathingSync()

    # ═══════════════════════════════════════════════════════════════════════
    #                         EXHALE (GIT PUSH)
    # ═══════════════════════════════════════════════════════════════════════

    @patch.object(BreathingSync, '_run_git_command')
    def test_exhale_no_changes(self, mock_git):
        """Exhale когда нет изменений"""
        # git status --porcelain возвращает пусто (нет изменений)
        mock_git.return_value = {
            "success": True,
            "stdout": "",  # Пусто = нет изменений
            "stderr": "",
            "returncode": 0
        }

        result = self.sync.exhale()

        # Должно быть успешно (нечего пушить)
        self.assertTrue(result)

    @patch.object(BreathingSync, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_exhale_with_changes(self, mock_exists, mock_git):
        """Exhale когда есть изменения"""
        mock_exists.return_value = True

        # Последовательность git команд
        def git_side_effect(args):
            if "status" in args:
                return {"success": True, "stdout": "M data/users.json", "stderr": "", "returncode": 0}
            elif "add" in args:
                return {"success": True, "stdout": "", "stderr": "", "returncode": 0}
            elif "commit" in args:
                return {"success": True, "stdout": "[main abc123]", "stderr": "", "returncode": 0}
            elif "push" in args:
                return {"success": True, "stdout": "Everything up-to-date", "stderr": "", "returncode": 0}
            return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

        mock_git.side_effect = git_side_effect

        result = self.sync.exhale()

        self.assertTrue(result)
        self.assertEqual(self.sync.stats["total_exhales"], 1)
        self.assertEqual(self.sync.stats["failed_exhales"], 0)
        self.assertIsNotNone(self.sync.stats["last_exhale"])

    @patch.object(BreathingSync, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_exhale_push_failure(self, mock_exists, mock_git):
        """Exhale когда push не удался"""
        mock_exists.return_value = True

        def git_side_effect(args):
            if "status" in args:
                return {"success": True, "stdout": "M data/users.json", "stderr": "", "returncode": 0}
            elif "add" in args:
                return {"success": True, "stdout": "", "stderr": "", "returncode": 0}
            elif "commit" in args:
                return {"success": True, "stdout": "[main abc123]", "stderr": "", "returncode": 0}
            elif "push" in args:
                return {"success": False, "stdout": "", "stderr": "error: failed to push", "returncode": 1}
            return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

        mock_git.side_effect = git_side_effect

        result = self.sync.exhale()

        self.assertFalse(result)
        self.assertEqual(self.sync.stats["failed_exhales"], 1)
        self.assertEqual(self.sync.stats["last_error"], "error: failed to push")

    @patch.object(BreathingSync, '_run_git_command')
    def test_exhale_nothing_to_commit(self, mock_git):
        """Exhale когда нечего коммитить"""

        def git_side_effect(args):
            if "status" in args:
                return {"success": True, "stdout": "M data/users.json", "stderr": "", "returncode": 0}
            elif "commit" in args:
                return {"success": False, "stdout": "", "stderr": "nothing to commit", "returncode": 1}
            return {"success": True, "stdout": "", "stderr": "", "returncode": 0}

        mock_git.side_effect = git_side_effect

        result = self.sync.exhale()

        # Должно быть успешно (нечего коммитить — нормально)
        self.assertTrue(result)


class TestBreathingSyncBreathe(unittest.TestCase):
    """Тесты breathe (полный цикл дыхания)"""

    def setUp(self):
        """Создаём BreathingSync перед каждым тестом"""
        self.sync = BreathingSync()

    # ═══════════════════════════════════════════════════════════════════════
    #                         BREATHE (ЦИКЛ)
    # ═══════════════════════════════════════════════════════════════════════

    @patch.object(BreathingSync, 'exhale')
    @patch.object(BreathingSync, 'inhale')
    def test_breathe_both_success(self, mock_inhale, mock_exhale):
        """Breathe когда оба успешны"""
        mock_inhale.return_value = True
        mock_exhale.return_value = True

        result = self.sync.breathe()

        self.assertTrue(result["inhale"])
        self.assertTrue(result["exhale"])
        mock_inhale.assert_called_once()
        mock_exhale.assert_called_once()

    @patch.object(BreathingSync, 'exhale')
    @patch.object(BreathingSync, 'inhale')
    def test_breathe_inhale_fails(self, mock_inhale, mock_exhale):
        """Breathe когда inhale не удался"""
        mock_inhale.return_value = False
        mock_exhale.return_value = True

        result = self.sync.breathe()

        self.assertFalse(result["inhale"])
        self.assertTrue(result["exhale"])

    @patch.object(BreathingSync, 'exhale')
    @patch.object(BreathingSync, 'inhale')
    def test_breathe_exhale_fails(self, mock_inhale, mock_exhale):
        """Breathe когда exhale не удался"""
        mock_inhale.return_value = True
        mock_exhale.return_value = False

        result = self.sync.breathe()

        self.assertTrue(result["inhale"])
        self.assertFalse(result["exhale"])

    @patch.object(BreathingSync, 'exhale')
    @patch.object(BreathingSync, 'inhale')
    def test_breathe_both_fail(self, mock_inhale, mock_exhale):
        """Breathe когда оба не удались"""
        mock_inhale.return_value = False
        mock_exhale.return_value = False

        result = self.sync.breathe()

        self.assertFalse(result["inhale"])
        self.assertFalse(result["exhale"])

    @patch.object(BreathingSync, 'exhale')
    @patch.object(BreathingSync, 'inhale')
    def test_breathe_order(self, mock_inhale, mock_exhale):
        """Breathe выполняется в правильном порядке: inhale → exhale"""
        mock_inhale.return_value = True
        mock_exhale.return_value = True

        # Используем side_effect чтобы проверить порядок
        call_order = []
        mock_inhale.side_effect = lambda: call_order.append("inhale") or True
        mock_exhale.side_effect = lambda: call_order.append("exhale") or True

        self.sync.breathe()

        self.assertEqual(call_order, ["inhale", "exhale"])


class TestBreathingSyncControl(unittest.TestCase):
    """Тесты управления синхронизацией"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         CONTROL
    # ═══════════════════════════════════════════════════════════════════════

    def test_stop(self):
        """stop() останавливает синхронизацию"""
        sync = BreathingSync()

        self.assertFalse(sync._stop_event.is_set())
        self.assertFalse(sync._running)

        sync._running = True
        sync.stop()

        self.assertTrue(sync._stop_event.is_set())
        self.assertFalse(sync._running)

    def test_stop_idempotent(self):
        """Множественный stop() безопасен"""
        sync = BreathingSync()

        sync.stop()
        sync.stop()
        sync.stop()

        self.assertTrue(sync._stop_event.is_set())

    def test_get_stats(self):
        """get_stats() возвращает статистику"""
        sync = BreathingSync()

        stats = sync.get_stats()

        self.assertIsInstance(stats, dict)
        self.assertIn("total_inhales", stats)
        self.assertIn("total_exhales", stats)
        self.assertIn("failed_inhales", stats)
        self.assertIn("failed_exhales", stats)
        self.assertIn("repo_path", stats)
        self.assertIn("interval_sec", stats)
        self.assertIn("is_running", stats)

    def test_get_stats_values(self):
        """get_stats() содержит правильные значения"""
        sync = BreathingSync()
        sync.stats["total_inhales"] = 10
        sync.stats["total_exhales"] = 8
        sync._running = True

        stats = sync.get_stats()

        self.assertEqual(stats["total_inhales"], 10)
        self.assertEqual(stats["total_exhales"], 8)
        self.assertTrue(stats["is_running"])
        self.assertEqual(stats["interval_sec"], 12)


class TestBreathingSyncLoop(unittest.TestCase):
    """Тесты async цикла синхронизации"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         ASYNC LOOP
    # ═══════════════════════════════════════════════════════════════════════

    @patch.object(BreathingSync, 'breathe')
    async def test_run_breathing_loop_basic(self, mock_breathe):
        """Базовый тест цикла"""
        mock_breathe.return_value = {"inhale": True, "exhale": True}

        sync = BreathingSync()

        # Запускаем цикл на 0.2 секунды
        task = asyncio.create_task(
            sync.run_breathing_loop(interval=0.1, only_when_master=False)
        )

        await asyncio.sleep(0.3)
        sync.stop()
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Должно быть хотя бы 1 вызов breathe
        self.assertGreater(mock_breathe.call_count, 0)

    @patch.object(BreathingSync, 'breathe')
    async def test_run_breathing_loop_only_when_master(self, mock_breathe):
        """Цикл работает только когда узел — мастер"""
        mock_breathe.return_value = {"inhale": True, "exhale": True}

        sync = BreathingSync()
        is_master = False

        def check_master():
            return is_master

        # Запускаем цикл
        task = asyncio.create_task(
            sync.run_breathing_loop(
                interval=0.1,
                only_when_master=True,
                is_master_func=check_master
            )
        )

        # Ждём немного (не мастер)
        await asyncio.sleep(0.3)
        call_count_not_master = mock_breathe.call_count

        # Становимся мастером
        is_master = True
        await asyncio.sleep(0.3)
        call_count_as_master = mock_breathe.call_count

        sync.stop()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Когда не мастер — breathe не вызывается (или очень редко)
        self.assertEqual(call_count_not_master, 0)

        # Когда мастер — breathe вызывается
        self.assertGreater(call_count_as_master, 0)


class TestBreathingSyncSingleton(unittest.TestCase):
    """Тесты singleton паттерна"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         SINGLETON
    # ═══════════════════════════════════════════════════════════════════════

    def test_get_breathing_sync_returns_instance(self):
        """get_breathing_sync() возвращает экземпляр"""
        sync = get_breathing_sync()

        self.assertIsNotNone(sync)
        self.assertIsInstance(sync, BreathingSync)

    def test_get_breathing_sync_singleton(self):
        """get_breathing_sync() возвращает один и тот же экземпляр"""
        sync1 = get_breathing_sync()
        sync2 = get_breathing_sync()

        self.assertIs(sync1, sync2)

    def test_singleton_shared_state(self):
        """Singleton делит состояние между вызовами"""
        sync1 = get_breathing_sync()
        sync1.stats["total_inhales"] = 42

        sync2 = get_breathing_sync()

        # Должен быть тот же объект с тем же состоянием
        self.assertEqual(sync2.stats["total_inhales"], 42)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
