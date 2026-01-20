#!/usr/bin/env python3
"""
test_leader_election.py — Unit tests для leader_election.py

Montana Protocol
Тестирование 3-Mirror Leader Election системы
"""

import sys
import os
import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from collections import deque

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../бот'))
from leader_election import (
    BOT_CHAIN,
    CHECK_INTERVAL,
    PING_TIMEOUT,
    STARTUP_DELAY,
    AttackDetector,
    LeaderElection,
    get_leader_election
)


class TestConstants(unittest.TestCase):
    """Тесты констант Montana Protocol"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         КОНСТАНТЫ
    # ═══════════════════════════════════════════════════════════════════════

    def test_bot_chain_structure(self):
        """Цепочка BOT_CHAIN имеет правильную структуру"""
        self.assertIsInstance(BOT_CHAIN, list)
        self.assertEqual(len(BOT_CHAIN), 5)  # 5 узлов

        for node in BOT_CHAIN:
            self.assertIsInstance(node, tuple)
            self.assertEqual(len(node), 2)  # (name, ip)
            name, ip = node
            self.assertIsInstance(name, str)
            self.assertIsInstance(ip, str)

    def test_bot_chain_order(self):
        """Проверка правильного порядка узлов в цепочке"""
        expected_order = [
            "amsterdam",
            "moscow",
            "almaty",
            "spb",
            "novosibirsk"
        ]

        for i, (name, ip) in enumerate(BOT_CHAIN):
            self.assertEqual(name, expected_order[i])

    def test_bot_chain_primary(self):
        """PRIMARY узел — Amsterdam (первый в цепочке)"""
        primary = BOT_CHAIN[0]
        self.assertEqual(primary[0], "amsterdam")
        self.assertEqual(primary[1], "72.56.102.240")

    def test_constants_values(self):
        """Проверка значений констант мониторинга"""
        self.assertEqual(CHECK_INTERVAL, 5)  # 5 секунд
        self.assertEqual(PING_TIMEOUT, 2)    # 2 секунды
        self.assertEqual(STARTUP_DELAY, 3)   # 3 секунды


class TestAttackDetector(unittest.TestCase):
    """Тесты AttackDetector"""

    def setUp(self):
        """Создаём новый detector перед каждым тестом"""
        self.detector = AttackDetector()

    # ═══════════════════════════════════════════════════════════════════════
    #                         INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_init_default_values(self):
        """Инициализация с правильными дефолтными значениями"""
        self.assertEqual(self.detector.failure_count, 0)
        self.assertEqual(self.detector.max_failures, 10)
        self.assertEqual(self.detector.cpu_threshold, 80.0)
        self.assertEqual(self.detector.response_time_threshold, 5.0)
        self.assertFalse(self.detector.under_attack)
        self.assertIsInstance(self.detector.response_times, deque)
        self.assertEqual(self.detector.response_times.maxlen, 10)

    # ═══════════════════════════════════════════════════════════════════════
    #                         FAILURE RECORDING
    # ═══════════════════════════════════════════════════════════════════════

    def test_record_failure_increments(self):
        """record_failure() увеличивает счётчик"""
        self.assertEqual(self.detector.failure_count, 0)

        self.detector.record_failure()
        self.assertEqual(self.detector.failure_count, 1)

        self.detector.record_failure()
        self.assertEqual(self.detector.failure_count, 2)

    def test_record_failure_triggers_attack(self):
        """10 failures → атака обнаружена"""
        for i in range(9):
            self.detector.record_failure()
            self.assertFalse(self.detector.under_attack)

        # 10-я ошибка триггерит атаку
        self.detector.record_failure()
        self.assertTrue(self.detector.under_attack)
        self.assertEqual(self.detector.failure_count, 10)

    def test_record_success_decreases(self):
        """record_success() уменьшает счётчик failures"""
        self.detector.failure_count = 5

        self.detector.record_success()
        self.assertEqual(self.detector.failure_count, 4)

        self.detector.record_success()
        self.assertEqual(self.detector.failure_count, 3)

    def test_record_success_not_below_zero(self):
        """record_success() не уходит в отрицательные"""
        self.detector.failure_count = 0

        self.detector.record_success()
        self.assertEqual(self.detector.failure_count, 0)

        self.detector.record_success()
        self.assertEqual(self.detector.failure_count, 0)

    # ═══════════════════════════════════════════════════════════════════════
    #                         RESPONSE TIME TRACKING
    # ═══════════════════════════════════════════════════════════════════════

    def test_record_response_time(self):
        """Запись времени отклика"""
        self.detector.record_response_time(1.0)
        self.assertEqual(len(self.detector.response_times), 1)
        self.assertEqual(self.detector.response_times[0], 1.0)

        self.detector.record_response_time(2.0)
        self.assertEqual(len(self.detector.response_times), 2)

    def test_response_time_maxlen(self):
        """Очередь response_times ограничена 10 элементами"""
        for i in range(15):
            self.detector.record_response_time(float(i))

        # Должно быть только последние 10
        self.assertEqual(len(self.detector.response_times), 10)
        self.assertEqual(list(self.detector.response_times), list(range(5, 15, 1.0)))

    def test_slow_response_triggers_attack(self):
        """Медленный отклик (> 5 сек в среднем) → атака"""
        # 5 медленных ответов
        for _ in range(5):
            self.detector.record_response_time(6.0)  # > 5 сек порог

        # Должна быть обнаружена атака
        self.assertTrue(self.detector.under_attack)

    def test_fast_response_no_attack(self):
        """Быстрый отклик не триггерит атаку"""
        for _ in range(10):
            self.detector.record_response_time(0.5)  # < 5 сек

        self.assertFalse(self.detector.under_attack)

    # ═══════════════════════════════════════════════════════════════════════
    #                         CPU MONITORING
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.psutil.cpu_percent')
    def test_check_cpu_normal(self, mock_cpu):
        """Нормальный CPU usage (< 80%)"""
        mock_cpu.return_value = 50.0

        result = self.detector.check_cpu_usage()

        self.assertFalse(result)
        self.assertFalse(self.detector.under_attack)

    @patch('leader_election.psutil.cpu_percent')
    def test_check_cpu_high(self, mock_cpu):
        """Высокий CPU usage (> 80%) → атака"""
        mock_cpu.return_value = 90.0

        result = self.detector.check_cpu_usage()

        self.assertTrue(result)
        self.assertTrue(self.detector.under_attack)

    @patch('leader_election.psutil.cpu_percent')
    def test_check_cpu_exactly_threshold(self, mock_cpu):
        """CPU ровно на пороге (80%)"""
        mock_cpu.return_value = 80.0

        result = self.detector.check_cpu_usage()

        self.assertFalse(result)  # 80% не > 80%

    @patch('leader_election.psutil.cpu_percent')
    def test_check_cpu_error_handling(self, mock_cpu):
        """Ошибка при проверке CPU не ломает систему"""
        mock_cpu.side_effect = Exception("CPU check failed")

        result = self.detector.check_cpu_usage()

        self.assertFalse(result)
        self.assertFalse(self.detector.under_attack)

    # ═══════════════════════════════════════════════════════════════════════
    #                         NETWORK MONITORING
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.psutil.net_io_counters')
    @patch('leader_election.time.time')
    def test_check_network_normal(self, mock_time, mock_net_io):
        """Нормальный network traffic"""
        mock_time.return_value = 100.0
        self.detector.last_check_time = 99.0  # 1 секунда назад

        # 10 MB за секунду (нормально)
        mock_net_io.return_value = Mock(bytes_recv=10 * 1024 * 1024)

        result = self.detector.check_network_traffic()

        self.assertFalse(result)
        self.assertFalse(self.detector.under_attack)

    @patch('leader_election.psutil.net_io_counters')
    @patch('leader_election.time.time')
    def test_check_network_high(self, mock_time, mock_net_io):
        """Высокий network traffic (> 100 MB/s) → атака"""
        mock_time.return_value = 100.0
        self.detector.last_check_time = 99.0  # 1 секунда назад

        # 150 MB за секунду (атака)
        mock_net_io.return_value = Mock(bytes_recv=150 * 1024 * 1024)

        result = self.detector.check_network_traffic()

        self.assertTrue(result)
        self.assertTrue(self.detector.under_attack)

    # ═══════════════════════════════════════════════════════════════════════
    #                         IS UNDER ATTACK
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.psutil.cpu_percent')
    @patch('leader_election.psutil.net_io_counters')
    def test_is_under_attack_false(self, mock_net, mock_cpu):
        """Нормальные метрики → не под атакой"""
        mock_cpu.return_value = 50.0
        mock_net.return_value = Mock(bytes_recv=10 * 1024 * 1024)

        result = self.detector.is_under_attack()

        self.assertFalse(result)

    @patch('leader_election.psutil.cpu_percent')
    @patch('leader_election.psutil.net_io_counters')
    def test_is_under_attack_cpu_high(self, mock_net, mock_cpu):
        """Высокий CPU → под атакой"""
        mock_cpu.return_value = 95.0
        mock_net.return_value = Mock(bytes_recv=10 * 1024 * 1024)

        result = self.detector.is_under_attack()

        self.assertTrue(result)

    # ═══════════════════════════════════════════════════════════════════════
    #                         RESET
    # ═══════════════════════════════════════════════════════════════════════

    def test_reset_clears_attack(self):
        """reset() сбрасывает флаг атаки"""
        # Симулируем атаку
        self.detector.under_attack = True
        self.detector.failure_count = 10
        self.detector.response_times.extend([6.0, 7.0, 8.0])

        self.detector.reset()

        self.assertFalse(self.detector.under_attack)
        self.assertEqual(self.detector.failure_count, 0)
        self.assertEqual(len(self.detector.response_times), 0)

    def test_reset_idempotent(self):
        """Множественный reset() безопасен"""
        self.detector.reset()
        self.detector.reset()
        self.detector.reset()

        self.assertFalse(self.detector.under_attack)
        self.assertEqual(self.detector.failure_count, 0)


class TestLeaderElectionBasic(unittest.TestCase):
    """Базовые тесты LeaderElection"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_init_default_chain(self):
        """Инициализация с дефолтной цепочкой"""
        le = LeaderElection()

        self.assertEqual(le.chain, BOT_CHAIN)
        self.assertEqual(len(le.chain), 5)

    def test_init_custom_chain(self):
        """Инициализация с кастомной цепочкой"""
        custom_chain = [
            ("node1", "1.1.1.1"),
            ("node2", "2.2.2.2")
        ]

        le = LeaderElection(chain=custom_chain)

        self.assertEqual(le.chain, custom_chain)
        self.assertEqual(len(le.chain), 2)

    def test_init_creates_attack_detector(self):
        """Инициализация создаёт AttackDetector"""
        le = LeaderElection()

        self.assertIsNotNone(le.attack_detector)
        self.assertIsInstance(le.attack_detector, AttackDetector)

    def test_init_saves_original_chain(self):
        """Инициализация сохраняет оригинальную цепочку"""
        custom_chain = [("node1", "1.1.1.1"), ("node2", "2.2.2.2")]
        le = LeaderElection(chain=custom_chain)

        self.assertEqual(le.original_chain, custom_chain)
        self.assertIsNot(le.original_chain, le.chain)  # Копия

    # ═══════════════════════════════════════════════════════════════════════
    #                         SELF DETECTION
    # ═══════════════════════════════════════════════════════════════════════

    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'moscow'})
    def test_detect_self_by_node_name(self):
        """Определение себя по NODE_NAME"""
        le = LeaderElection()

        self.assertEqual(le.my_name, "moscow")
        self.assertEqual(le.my_ip, "176.124.208.93")
        self.assertEqual(le.my_position, 1)

    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'amsterdam'})
    def test_detect_self_primary_node(self):
        """Определение PRIMARY узла"""
        le = LeaderElection()

        self.assertEqual(le.my_name, "amsterdam")
        self.assertEqual(le.my_position, 0)

    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'novosibirsk'})
    def test_detect_self_last_node(self):
        """Определение последнего узла в цепочке"""
        le = LeaderElection()

        self.assertEqual(le.my_name, "novosibirsk")
        self.assertEqual(le.my_position, 4)  # Последний в 5-узловой цепочке

    @patch.dict(os.environ, {}, clear=True)
    def test_detect_self_fallback(self):
        """Fallback на первый узел если не определён"""
        le = LeaderElection()

        # Должен выбрать первый узел как fallback
        self.assertEqual(le.my_name, "amsterdam")
        self.assertEqual(le.my_position, 0)

    # ═══════════════════════════════════════════════════════════════════════
    #                         CHAIN STATUS
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.check_node_health')
    def test_get_chain_status_all_alive(self, mock_health):
        """Статус цепочки: все живы"""
        mock_health.return_value = True

        le = LeaderElection()
        status = le.get_chain_status()

        # Должны быть зелёные кружки для всех узлов
        self.assertIn("🟢", status)
        self.assertNotIn("🔴", status)

    @patch('leader_election.check_node_health')
    def test_get_chain_status_all_dead(self, mock_health):
        """Статус цепочки: все мертвы"""
        mock_health.return_value = False

        le = LeaderElection()
        status = le.get_chain_status()

        # Должны быть красные кружки для всех узлов
        self.assertIn("🔴", status)
        self.assertNotIn("🟢", status)

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'moscow'})
    def test_get_chain_status_marks_self(self, mock_health):
        """Статус цепочки: отмечает свой узел"""
        mock_health.return_value = True

        le = LeaderElection()
        status = le.get_chain_status()

        # Должна быть метка "← я" для своего узла
        self.assertIn("moscow ← я", status)


class TestLeaderElectionMasterLogic(unittest.TestCase):
    """Тесты логики определения мастера"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         AM I THE MASTER
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'amsterdam'})
    def test_am_i_master_primary_always(self, mock_health):
        """PRIMARY (amsterdam) всегда мастер"""
        mock_health.return_value = True

        le = LeaderElection()
        result = le.am_i_the_master()

        # Amsterdam — первый в цепочке, всегда мастер
        self.assertTrue(result)

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'moscow'})
    def test_am_i_master_second_when_first_dead(self, mock_health):
        """MIRROR 1 (moscow) — мастер если amsterdam мертв"""

        def health_check(ip):
            # Amsterdam мертв, остальные живы
            return ip != "72.56.102.240"

        mock_health.side_effect = health_check

        le = LeaderElection()
        result = le.am_i_the_master()

        # Moscow становится мастером
        self.assertTrue(result)

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'moscow'})
    def test_am_i_master_second_when_first_alive(self, mock_health):
        """MIRROR 1 (moscow) НЕ мастер если amsterdam жив"""
        mock_health.return_value = True  # Все живы

        le = LeaderElection()
        result = le.am_i_the_master()

        # Amsterdam жив → Moscow не мастер
        self.assertFalse(result)

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'novosibirsk'})
    def test_am_i_master_last_when_all_dead(self, mock_health):
        """Последний узел (novosibirsk) — мастер если все выше мертвы"""
        mock_health.return_value = False  # Все мертвы

        le = LeaderElection()
        result = le.am_i_the_master()

        # Все выше мертвы → Novosibirsk становится мастером
        self.assertTrue(result)

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'spb'})
    def test_am_i_master_middle_selective(self, mock_health):
        """Средний узел (spb) — мастер только если все выше мертвы"""

        def health_check(ip):
            # Amsterdam и Moscow мертвы, Almaty жив
            dead_nodes = ["72.56.102.240", "176.124.208.93"]
            return ip not in dead_nodes

        mock_health.side_effect = health_check

        le = LeaderElection()
        result = le.am_i_the_master()

        # Almaty (выше) жив → SPB не мастер
        self.assertFalse(result)


class TestLeaderElectionAttackHandling(unittest.TestCase):
    """Тесты обработки атак"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         CHAIN SHUFFLING
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'moscow'})
    def test_shuffle_chain_on_attack(self, mock_health):
        """При атаке цепочка перемешивается"""
        mock_health.return_value = True  # Все узлы живы

        le = LeaderElection()
        original_order = [name for name, _ in le.chain]

        # Симулируем атаку
        le.attack_detector.under_attack = True

        le.shuffle_chain_on_attack()

        # Цепочка должна быть перемешана
        new_order = [name for name, _ in le.chain]
        self.assertNotEqual(original_order, new_order)
        self.assertTrue(le.chain_shuffled)

    @patch('leader_election.check_node_health')
    def test_shuffle_filters_dead_nodes(self, mock_health):
        """shuffle_chain_on_attack() фильтрует мертвые узлы"""

        def health_check(ip):
            # Только Amsterdam и Moscow живы
            alive_nodes = ["72.56.102.240", "176.124.208.93"]
            return ip in alive_nodes

        mock_health.side_effect = health_check

        le = LeaderElection()
        le.attack_detector.under_attack = True

        le.shuffle_chain_on_attack()

        # В новой цепочке должны быть только 2 живых узла
        self.assertEqual(len(le.chain), 2)

        chain_ips = [ip for _, ip in le.chain]
        self.assertIn("72.56.102.240", chain_ips)
        self.assertIn("176.124.208.93", chain_ips)

    @patch('leader_election.check_node_health')
    def test_shuffle_no_attack_no_shuffle(self, mock_health):
        """Без атаки цепочка не перемешивается"""
        mock_health.return_value = True

        le = LeaderElection()
        original_chain = list(le.chain)

        # НЕТ атаки
        le.attack_detector.under_attack = False

        le.shuffle_chain_on_attack()

        # Цепочка НЕ изменилась
        self.assertEqual(le.chain, original_chain)
        self.assertFalse(le.chain_shuffled)

    # ═══════════════════════════════════════════════════════════════════════
    #                         CHAIN RESTORATION
    # ═══════════════════════════════════════════════════════════════════════

    @patch('leader_election.check_node_health')
    def test_restore_original_chain(self, mock_health):
        """Восстановление оригинальной цепочки"""
        mock_health.return_value = True

        le = LeaderElection()
        original = list(le.original_chain)

        # Перемешиваем
        le.attack_detector.under_attack = True
        le.shuffle_chain_on_attack()

        # Восстанавливаем
        le.restore_original_chain()

        # Цепочка восстановлена
        self.assertEqual(le.chain, original)
        self.assertFalse(le.chain_shuffled)

    def test_restore_when_not_shuffled(self):
        """Восстановление когда цепочка не была перемешана"""
        le = LeaderElection()
        original = list(le.chain)

        le.restore_original_chain()

        # Ничего не изменилось
        self.assertEqual(le.chain, original)
        self.assertFalse(le.chain_shuffled)


class TestLeaderElectionSingleton(unittest.TestCase):
    """Тесты singleton паттерна"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         SINGLETON
    # ═══════════════════════════════════════════════════════════════════════

    def test_get_leader_election_returns_instance(self):
        """get_leader_election() возвращает экземпляр"""
        le = get_leader_election()

        self.assertIsNotNone(le)
        self.assertIsInstance(le, LeaderElection)

    def test_get_leader_election_singleton(self):
        """get_leader_election() возвращает один и тот же экземпляр"""
        le1 = get_leader_election()
        le2 = get_leader_election()

        self.assertIs(le1, le2)

    def test_singleton_shared_state(self):
        """Singleton делит состояние между вызовами"""
        le1 = get_leader_election()
        le1.is_master = True

        le2 = get_leader_election()

        # Должен быть тот же объект с тем же состоянием
        self.assertTrue(le2.is_master)


class TestLeaderElectionEdgeCases(unittest.TestCase):
    """Тесты граничных случаев"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════

    def test_empty_chain(self):
        """Пустая цепочка"""
        le = LeaderElection(chain=[])

        self.assertEqual(len(le.chain), 0)
        self.assertIsNone(le.my_name)
        self.assertIsNone(le.my_ip)
        self.assertEqual(le.my_position, -1)

    @patch('leader_election.check_node_health')
    def test_single_node_chain(self, mock_health):
        """Цепочка из одного узла"""
        mock_health.return_value = True

        single_chain = [("solo", "1.1.1.1")]
        le = LeaderElection(chain=single_chain)

        # Единственный узел всегда мастер
        self.assertTrue(le.am_i_the_master())

    @patch('leader_election.check_node_health')
    @patch.dict(os.environ, {'MONTANA_NODE_NAME': 'unknown'})
    def test_node_not_in_chain(self, mock_health):
        """Узел не найден в цепочке"""
        mock_health.return_value = True

        le = LeaderElection()

        # Должен fallback на первый узел
        self.assertIn(le.my_name, [name for name, _ in BOT_CHAIN])

    @patch('leader_election.check_node_health')
    def test_all_nodes_dead_last_becomes_master(self, mock_health):
        """Все узлы мертвы → последний становится мастером"""
        mock_health.return_value = False  # Все мертвы

        # Создаём узел как последний в цепочке
        with patch.dict(os.environ, {'MONTANA_NODE_NAME': 'novosibirsk'}):
            le = LeaderElection()
            result = le.am_i_the_master()

        # Все мертвы → последний мастер
        self.assertTrue(result)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
