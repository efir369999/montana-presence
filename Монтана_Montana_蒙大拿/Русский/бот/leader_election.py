# leader_election.py
# Montana Protocol — 3-Mirror Leader Election
#
# Архитектура из 003_ТРОЙНОЕ_ЗЕРКАЛО.md:
# - Детерминированный выбор лидера по цепочке
# - Активная проверка "кто жив" каждые 5 сек
# - Я лидер если ВСЕ узлы ДО меня в цепочке мертвы
# - Failover < 10 секунд
# - Breathing Sync: git pull/push каждые 12 сек

import os
import asyncio
import logging
import socket
import subprocess
import random
import time
import psutil
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from datetime import datetime
from collections import deque

# Breathing Sync
try:
    from breathing_sync import get_breathing_sync, BreathingSync
    BREATHING_SYNC_AVAILABLE = True
except ImportError:
    BREATHING_SYNC_AVAILABLE = False

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#                         ЦЕПОЧКА УЗЛОВ (из документации)
# ═══════════════════════════════════════════════════════════════════════════════

# BOT_CHAIN — цепочка для Telegram бота (кто делает polling)
# Порядок = приоритет. Первый живой = master.
BOT_CHAIN: List[Tuple[str, str]] = [
    ("amsterdam",   "72.56.102.240"),    # PRIMARY
    ("moscow",      "176.124.208.93"),   # MIRROR 1
    ("almaty",      "91.200.148.93"),    # MIRROR 2
    ("spb",         "188.225.58.98"),    # MIRROR 3
    ("novosibirsk", "147.45.147.247"),   # MIRROR 4
]

# Константы мониторинга
CHECK_INTERVAL = 5    # секунд между проверками
PING_TIMEOUT = 2      # секунд таймаут пинга
STARTUP_DELAY = 3     # секунд перед первой проверкой


# ═══════════════════════════════════════════════════════════════════════════════
#                              ПРОВЕРКА УЗЛОВ
# ═══════════════════════════════════════════════════════════════════════════════

def is_node_alive(ip: str, timeout: int = PING_TIMEOUT) -> bool:
    """
    Проверить жив ли узел через ping.

    Returns:
        True если узел отвечает на ping
    """
    try:
        # Linux/macOS ping с таймаутом
        if os.name == 'nt':
            cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip]
        else:
            cmd = ['ping', '-c', '1', '-W', str(timeout), ip]

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        logger.debug(f"Ping error {ip}: {e}")
        return False


def is_node_alive_tcp(ip: str, port: int = 22, timeout: int = PING_TIMEOUT) -> bool:
    """
    Проверить жив ли узел через TCP connect (SSH порт).
    Более надёжно чем ICMP ping если firewall блокирует ping.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.debug(f"TCP check error {ip}:{port}: {e}")
        return False


def check_node_health(ip: str) -> bool:
    """
    Комплексная проверка здоровья узла.
    Пробуем ping, затем TCP если ping не работает.
    """
    # Сначала ping (быстро)
    if is_node_alive(ip):
        return True

    # Fallback на TCP порт 22 (SSH)
    if is_node_alive_tcp(ip, 22):
        return True

    # Fallback на TCP порт 443 (HTTPS)
    if is_node_alive_tcp(ip, 443):
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
#                              ATTACK DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class AttackDetector:
    """
    Обнаружение атак на узел Montana.

    Метрики атаки:
    - Высокий CPU usage (> 80%)
    - Высокий network traffic (аномальный)
    - Много повторных ошибок/failures
    - Медленное время отклика (> 5 сек)
    - Недоступность узла
    """

    def __init__(self):
        # Счетчики ошибок
        self.failure_count = 0
        self.max_failures = 10  # Порог для обнаружения атаки

        # История времени отклика (последние 10 проверок)
        self.response_times: deque = deque(maxlen=10)

        # Пороги
        self.cpu_threshold = 80.0  # %
        self.response_time_threshold = 5.0  # секунды

        # Последняя проверка
        self.last_check_time = time.time()

        # Network traffic tracking (для расчёта delta)
        self.last_bytes_recv = 0
        try:
            self.last_bytes_recv = psutil.net_io_counters().bytes_recv
        except:
            pass

        # Флаг атаки
        self.under_attack = False

    def record_failure(self):
        """Зарегистрировать ошибку"""
        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            self.under_attack = True
            logger.warning(f"🚨 АТАКА ОБНАРУЖЕНА: {self.failure_count} failures")

    def record_success(self):
        """Зарегистрировать успех (сбрасывает счетчик)"""
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)

    def record_response_time(self, response_time: float):
        """Зарегистрировать время отклика"""
        self.response_times.append(response_time)

        # Проверяем среднее время отклика
        if len(self.response_times) >= 5:
            avg_time = sum(self.response_times) / len(self.response_times)
            if avg_time > self.response_time_threshold:
                self.under_attack = True
                logger.warning(f"🚨 АТАКА ОБНАРУЖЕНА: медленный отклик {avg_time:.2f}s")

    def check_cpu_usage(self) -> bool:
        """
        Проверить CPU usage.

        Returns:
            True если CPU > порога (возможная атака)
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > self.cpu_threshold:
                logger.warning(f"🚨 АТАКА ОБНАРУЖЕНА: высокий CPU {cpu_percent}%")
                self.under_attack = True
                return True
        except Exception as e:
            logger.debug(f"Ошибка проверки CPU: {e}")
        return False

    def check_network_traffic(self) -> bool:
        """
        Проверить network traffic (базовая проверка).

        Returns:
            True если обнаружена аномалия
        """
        try:
            net_io = psutil.net_io_counters()
            current_bytes = net_io.bytes_recv
            current_time = time.time()

            # Рассчитываем DELTA bytes за период
            time_delta = current_time - self.last_check_time
            bytes_delta = current_bytes - self.last_bytes_recv

            # Обновляем для следующей проверки
            self.last_bytes_recv = current_bytes
            self.last_check_time = current_time

            # Защита от первого запуска или отрицательного delta
            if time_delta <= 0 or bytes_delta < 0:
                return False

            bytes_per_sec = bytes_delta / time_delta

            # Порог: > 500 MB/s входящего трафика (реальная DDoS атака)
            if bytes_per_sec > 500 * 1024 * 1024:  # 500 MB/s
                logger.warning(f"🚨 АТАКА ОБНАРУЖЕНА: высокий трафик {bytes_per_sec / 1024 / 1024:.1f} MB/s")
                self.under_attack = True
                return True
        except Exception as e:
            logger.debug(f"Ошибка проверки network: {e}")
        return False

    def is_under_attack(self) -> bool:
        """
        Проверить все метрики и определить состояние атаки.

        Returns:
            True если узел под атакой
        """
        # Проверяем все метрики
        self.check_cpu_usage()
        self.check_network_traffic()

        return self.under_attack

    def reset(self):
        """Сбросить флаг атаки после успешного failover"""
        self.under_attack = False
        self.failure_count = 0
        self.response_times.clear()
        logger.info("✅ Attack detector reset")


# ═══════════════════════════════════════════════════════════════════════════════
#                              LEADER ELECTION
# ═══════════════════════════════════════════════════════════════════════════════

class LeaderElection:
    """
    3-Mirror Leader Election по документации Montana.

    Логика:
    - Цепочка узлов определяет приоритет
    - Я лидер если ВСЕ узлы ДО меня в цепочке мертвы
    - Проверка каждые 5 секунд
    - Failover < 10 секунд
    """

    def __init__(self, chain: List[Tuple[str, str]] = None):
        self.chain = chain or BOT_CHAIN
        self.original_chain = list(self.chain)  # Сохраняем оригинальную цепочку
        self.my_name: Optional[str] = None
        self.my_ip: Optional[str] = None
        self.my_position: int = -1  # Позиция в цепочке (-1 = не в цепочке)
        self.is_master: bool = False
        self._stop_event = asyncio.Event()

        # Breathing Sync
        self._breathing_sync: Optional[BreathingSync] = None
        self._breathing_task: Optional[asyncio.Task] = None

        # Attack Detection
        self.attack_detector = AttackDetector()
        self.chain_shuffled = False  # Флаг - цепочка перемешана?

        # Определяем себя
        self._detect_self()

    def _detect_self(self):
        """Определить текущий узел по NODE_NAME или IP"""

        # Способ 1: через env variable MONTANA_NODE_NAME
        node_name = os.getenv('MONTANA_NODE_NAME', '').lower()
        if node_name:
            for i, (name, ip) in enumerate(self.chain):
                if name.lower() == node_name:
                    self.my_name = name
                    self.my_ip = ip
                    self.my_position = i
                    logger.info(f"🏔 Узел определён по NODE_NAME: {name} (позиция {i} в цепочке)")
                    return

        # Способ 2: через локальные IP адреса
        local_ips = self._get_local_ips()
        for i, (name, ip) in enumerate(self.chain):
            if ip in local_ips:
                self.my_name = name
                self.my_ip = ip
                self.my_position = i
                logger.info(f"🏔 Узел определён по IP: {name} ({ip}, позиция {i})")
                return

        # Способ 3: fallback на первый узел (для локальной разработки)
        if self.chain:
            self.my_name = self.chain[0][0]
            self.my_ip = self.chain[0][1]
            self.my_position = 0
            logger.warning(f"⚠️ Узел не определён, fallback на {self.my_name} (позиция 0)")

    def _get_local_ips(self) -> set:
        """Получить все локальные IP адреса"""
        ips = set()

        try:
            hostname = socket.gethostname()
            ips.add(socket.gethostbyname(hostname))
        except:
            pass

        try:
            # Внешний IP через connect
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
            s.close()
        except:
            pass

        return ips

    def am_i_the_master(self) -> bool:
        """
        Я мастер если ВСЕ узлы ДО меня в цепочке мертвы.

        Из документации 003_ТРОЙНОЕ_ЗЕРКАЛО.md:
        ```
        def am_i_the_brain(my_name: str) -> bool:
            for name, ip in BRAIN_CHAIN:
                if name == my_name:
                    return True  # Дошли до себя - я лидер
                if is_node_alive(ip):
                    return False  # Кто-то выше меня жив
            return False
        ```
        """
        if self.my_position < 0:
            return False

        # Проверяем всех кто выше в цепочке
        for i, (name, ip) in enumerate(self.chain):
            if name == self.my_name:
                # Дошли до себя — все выше мертвы, я мастер
                return True

            # Проверяем жив ли узел выше меня
            if check_node_health(ip):
                logger.debug(f"  {name} ({ip}) — ALIVE, я не мастер")
                return False
            else:
                logger.debug(f"  {name} ({ip}) — DEAD")

        return False

    def get_chain_status(self) -> str:
        """Получить статус всей цепочки для логов"""
        status = []
        for name, ip in self.chain:
            alive = check_node_health(ip)
            marker = "🟢" if alive else "🔴"
            is_me = " ← я" if name == self.my_name else ""
            status.append(f"{marker} {name}{is_me}")
        return " | ".join(status)

    def _pq_secure_shuffle(self, items: list) -> list:
        """
        Постквантово-безопасное перемешивание списка.

        Использует:
        1. ML-DSA-65 подпись текущего timestamp для seed
        2. secrets.SystemRandom() как fallback (CSPRNG)

        Атакующий НЕ может предсказать порядок даже с квантовым компьютером.
        """
        import secrets
        import hashlib

        # Пробуем использовать ML-DSA-65 для генерации seed
        try:
            from node_crypto import get_node_crypto_system
            node_crypto = get_node_crypto_system()

            # Данные для подписи: timestamp + список узлов
            entropy_data = f"{time.time()}:{','.join([n for n, _ in items])}".encode()

            # Подписываем ML-DSA-65
            signature = node_crypto.sign(entropy_data)
            if signature:
                # Хэш подписи = криптографически безопасный seed
                seed_bytes = hashlib.sha256(signature).digest()
                seed = int.from_bytes(seed_bytes[:8], 'big')
                logger.info(f"🔐 PQ-shuffle: ML-DSA-65 seed generated")
            else:
                # Fallback на secrets
                seed = secrets.randbits(64)
                logger.info(f"🔐 PQ-shuffle: secrets fallback")
        except Exception as e:
            # Fallback на CSPRNG
            seed = secrets.randbits(64)
            logger.warning(f"⚠️ ML-DSA-65 unavailable, using secrets: {e}")

        # Перемешиваем используя seed
        shuffled = list(items)
        rng = random.Random(seed)
        rng.shuffle(shuffled)

        return shuffled

    def shuffle_chain_on_attack(self, external_trigger: bool = False):
        """
        При обнаружении атаки — случайный порядок failover.

        ПОСТКВАНТОВАЯ БЕЗОПАСНОСТЬ:
        - Используется ML-DSA-65 для генерации seed
        - Атакующий НЕ может предсказать следующего мастера
        - Цепочка перемешивается криптографически безопасно
        - Только здоровые узлы учитываются

        Args:
            external_trigger: True если вызван внешне (AtlantGuard)
        """
        if not external_trigger and not self.attack_detector.is_under_attack():
            return

        logger.warning("🚨 АТАКА ОБНАРУЖЕНА! Переход на PQ-случайный failover")

        # Постквантово-безопасное перемешивание
        shuffled = self._pq_secure_shuffle(self.chain)

        # Фильтруем только живые узлы
        healthy_nodes = []
        for name, ip in shuffled:
            if check_node_health(ip):
                healthy_nodes.append((name, ip))
                logger.info(f"  ✅ {name} ({ip}) — ЗДОРОВ")
            else:
                logger.warning(f"  ❌ {name} ({ip}) — НЕДОСТУПЕН")

        if healthy_nodes:
            self.chain = healthy_nodes
            self.chain_shuffled = True
            logger.info(f"🎲 Новый случайный порядок: {' → '.join([n for n, _ in self.chain])}")

            # Обновляем мою позицию
            for i, (name, ip) in enumerate(self.chain):
                if name == self.my_name:
                    self.my_position = i
                    break
        else:
            logger.error("❌ НЕТ ЗДОРОВЫХ УЗЛОВ! Оставляем старую цепочку")

        # Сбрасываем attack detector после failover
        self.attack_detector.reset()

    def restore_original_chain(self):
        """Восстановить оригинальную детерминированную цепочку"""
        if self.chain_shuffled:
            logger.info("🔄 Восстановление оригинальной цепочки")
            self.chain = list(self.original_chain)
            self.chain_shuffled = False

            # Обновляем позицию
            for i, (name, ip) in enumerate(self.chain):
                if name == self.my_name:
                    self.my_position = i
                    break

    # ═══════════════════════════════════════════════════════════════════════════════
    #                    PULSE MODE — РЕЖИМ ПУЛЬСАЦИИ
    # ═══════════════════════════════════════════════════════════════════════════════

    def check_majority_under_attack(self) -> tuple:
        """
        Проверяет, атаковано ли большинство узлов.

        Returns:
            (is_majority_attack: bool, healthy_count: int, total: int)
        """
        total = len(self.original_chain)
        healthy_count = 0
        unhealthy_nodes = []

        for name, ip in self.original_chain:
            if check_node_health(ip):
                healthy_count += 1
            else:
                unhealthy_nodes.append(name)

        # Большинство = более 50% недоступны
        majority_threshold = total // 2 + 1
        is_majority_attack = (total - healthy_count) >= majority_threshold

        if is_majority_attack:
            logger.warning(f"🚨 MAJORITY ATTACK: {total - healthy_count}/{total} узлов недоступны")
            logger.warning(f"   Недоступны: {', '.join(unhealthy_nodes)}")

        return is_majority_attack, healthy_count, total

    def enter_pulse_mode(self) -> dict:
        """
        Входит в режим пульсации при атаке на большинство.

        PULSE MODE:
        - Сеть "засыпает"
        - Узлы пульсируют поочерёдно
        - Только один узел активен в момент времени
        - Минимизация поверхности атаки

        Returns:
            {
                "mode": "pulse",
                "pulse_duration": int (секунды активности),
                "sleep_duration": int (секунды сна),
                "my_pulse_slot": int (мой слот в очереди),
                "total_slots": int
            }
        """
        import hashlib
        import secrets

        # Параметры пульсации
        PULSE_DURATION = 30  # 30 сек активности
        SLEEP_DURATION = 60  # 60 сек сна между пульсами

        # Находим живые узлы
        healthy_nodes = []
        for name, ip in self.original_chain:
            if check_node_health(ip):
                healthy_nodes.append((name, ip))

        if not healthy_nodes:
            logger.error("❌ PULSE MODE: Нет живых узлов!")
            return None

        total_slots = len(healthy_nodes)

        # Определяем мой слот через PQ-хэш
        # Используем ML-DSA-65 если доступен, иначе SHA256
        try:
            from node_crypto import get_node_crypto_system
            node_crypto = get_node_crypto_system()

            # Подписываем текущий час (все узлы получат одинаковый результат)
            hour_marker = int(time.time() // 3600)
            entropy = f"PULSE:{hour_marker}:{','.join([n for n, _ in healthy_nodes])}".encode()

            signature = node_crypto.sign(entropy)
            if signature:
                seed_bytes = hashlib.sha256(signature).digest()
            else:
                seed_bytes = hashlib.sha256(entropy).digest()
        except Exception:
            hour_marker = int(time.time() // 3600)
            entropy = f"PULSE:{hour_marker}:{','.join([n for n, _ in healthy_nodes])}".encode()
            seed_bytes = hashlib.sha256(entropy).digest()

        # Перемешиваем узлы детерминированно
        seed = int.from_bytes(seed_bytes[:8], 'big')
        rng = random.Random(seed)
        pulse_order = list(healthy_nodes)
        rng.shuffle(pulse_order)

        # Находим мой слот
        my_pulse_slot = -1
        for i, (name, ip) in enumerate(pulse_order):
            if name == self.my_name:
                my_pulse_slot = i
                break

        if my_pulse_slot < 0:
            logger.warning(f"⚠️ PULSE MODE: Я ({self.my_name}) не в списке живых узлов")
            return None

        logger.warning(f"💓 PULSE MODE ACTIVATED")
        logger.warning(f"   Порядок: {' → '.join([n for n, _ in pulse_order])}")
        logger.warning(f"   Мой слот: #{my_pulse_slot + 1}/{total_slots}")
        logger.warning(f"   Пульс: {PULSE_DURATION}s активен, {SLEEP_DURATION}s сон")

        return {
            "mode": "pulse",
            "pulse_duration": PULSE_DURATION,
            "sleep_duration": SLEEP_DURATION,
            "my_pulse_slot": my_pulse_slot,
            "total_slots": total_slots,
            "pulse_order": [n for n, _ in pulse_order]
        }

    def is_my_pulse_active(self, pulse_config: dict) -> bool:
        """
        Проверяет, активен ли сейчас мой пульс.

        В режиме пульсации узлы работают по очереди:
        - Узел 0: активен 0-30 сек, спит 30-120 сек
        - Узел 1: активен 30-60 сек, спит 0-30 + 60-120 сек
        - и т.д.

        Returns:
            True если сейчас моя очередь быть активным
        """
        if not pulse_config:
            return False

        pulse_duration = pulse_config["pulse_duration"]
        sleep_duration = pulse_config["sleep_duration"]
        my_slot = pulse_config["my_pulse_slot"]
        total_slots = pulse_config["total_slots"]

        # Полный цикл = все узлы по очереди
        cycle_duration = total_slots * pulse_duration + sleep_duration

        # Текущая позиция в цикле
        current_time = time.time()
        position_in_cycle = current_time % cycle_duration

        # Мой активный период в цикле
        my_start = my_slot * pulse_duration
        my_end = my_start + pulse_duration

        is_active = my_start <= position_in_cycle < my_end

        if is_active:
            remaining = my_end - position_in_cycle
            logger.debug(f"💓 Мой пульс АКТИВЕН (осталось {remaining:.0f}s)")
        else:
            # Когда следующий пульс
            if position_in_cycle < my_start:
                next_pulse = my_start - position_in_cycle
            else:
                next_pulse = cycle_duration - position_in_cycle + my_start
            logger.debug(f"😴 Сплю (следующий пульс через {next_pulse:.0f}s)")

        return is_active

    def exit_pulse_mode(self):
        """Выход из режима пульсации"""
        logger.info("💓 PULSE MODE DEACTIVATED — возврат к нормальной работе")
        self.restore_original_chain()

    def stop(self):
        """Остановить leader election и breathing sync"""
        self._stop_event.set()
        if self._breathing_sync:
            self._breathing_sync.stop()
        if self._breathing_task:
            self._breathing_task.cancel()

    async def start_breathing_sync(self):
        """Запустить Breathing Sync"""
        if not BREATHING_SYNC_AVAILABLE:
            logger.warning("⚠️ Breathing Sync недоступен")
            return

        self._breathing_sync = get_breathing_sync()
        self._breathing_task = asyncio.create_task(
            self._breathing_sync.run_breathing_loop(
                only_when_master=True,
                is_master_func=lambda: self.is_master
            )
        )
        logger.info("🌬 Breathing Sync запущен")

    async def run_leader_loop(
        self,
        on_become_master,
        on_become_standby,
        check_interval: int = CHECK_INTERVAL
    ):
        """
        Основной цикл проверки лидерства.

        РЕЖИМЫ РАБОТЫ:
        1. NORMAL — стандартная цепочка приоритетов
        2. ATTACK — PQ-случайный failover при атаке на узел
        3. PULSE — поочерёдная пульсация при атаке на большинство

        Каждые check_interval секунд:
        1. Проверяем состояние сети
        2. Определяем режим работы
        3. Принимаем решение о мастерстве
        """
        logger.info(f"🔄 Запуск leader election loop (интервал {check_interval} сек)")
        logger.info(f"📍 Моя позиция: {self.my_name} #{self.my_position}")
        logger.info(f"🌬 Breathing Sync: {'✅' if BREATHING_SYNC_AVAILABLE else '❌'}")

        # Запускаем Breathing Sync
        if BREATHING_SYNC_AVAILABLE:
            await self.start_breathing_sync()

        # Начальная задержка
        await asyncio.sleep(STARTUP_DELAY)

        was_master = False
        pulse_mode_config = None  # Конфигурация режима пульсации
        pulse_mode_active = False

        while not self._stop_event.is_set():
            try:
                check_start_time = time.time()

                # ═══════════════════════════════════════════════════════════════
                # ПРОВЕРКА 1: Атака на большинство → PULSE MODE
                # ═══════════════════════════════════════════════════════════════
                is_majority_attack, healthy_count, total_nodes = self.check_majority_under_attack()

                if is_majority_attack and not pulse_mode_active:
                    # ВХОДИМ В РЕЖИМ ПУЛЬСАЦИИ
                    logger.warning(f"🚨 MAJORITY ATTACK DETECTED! {total_nodes - healthy_count}/{total_nodes} узлов недоступны")
                    logger.warning(f"💓 Переход в PULSE MODE — сеть засыпает и пульсирует")

                    pulse_mode_config = self.enter_pulse_mode()
                    pulse_mode_active = pulse_mode_config is not None

                    # Уходим в standby пока не наш пульс
                    if was_master:
                        self.is_master = False
                        was_master = False
                        await on_become_standby()

                elif not is_majority_attack and pulse_mode_active:
                    # ВЫХОДИМ ИЗ РЕЖИМА ПУЛЬСАЦИИ
                    logger.info(f"✅ Сеть восстановлена: {healthy_count}/{total_nodes} узлов здоровы")
                    self.exit_pulse_mode()
                    pulse_mode_active = False
                    pulse_mode_config = None

                # ═══════════════════════════════════════════════════════════════
                # РЕЖИМ ПУЛЬСАЦИИ — поочерёдная работа узлов
                # ═══════════════════════════════════════════════════════════════
                if pulse_mode_active and pulse_mode_config:
                    is_my_pulse = self.is_my_pulse_active(pulse_mode_config)

                    if is_my_pulse and not was_master:
                        # МОЙ ПУЛЬС — становлюсь мастером
                        self.is_master = True
                        was_master = True
                        logger.info(f"💓 {self.my_name} → PULSE MASTER (слот #{pulse_mode_config['my_pulse_slot'] + 1})")
                        self.attack_detector.record_success()
                        await on_become_master()

                    elif not is_my_pulse and was_master:
                        # НЕ МОЙ ПУЛЬС — засыпаю
                        self.is_master = False
                        was_master = False
                        logger.info(f"😴 {self.my_name} → PULSE SLEEP")
                        await on_become_standby()

                    # В режиме пульсации пропускаем обычную логику
                    await asyncio.sleep(check_interval)
                    continue

                # ═══════════════════════════════════════════════════════════════
                # ПРОВЕРКА 2: Атака на узел → PQ-FAILOVER
                # ═══════════════════════════════════════════════════════════════
                if self.attack_detector.is_under_attack():
                    # Атака обнаружена — переход на случайный failover
                    self.shuffle_chain_on_attack()

                    # Если я был мастером — передаём управление
                    if was_master:
                        logger.warning("🚨 Передача мастерства из-за атаки")
                        self.is_master = False
                        was_master = False
                        await on_become_standby()

                # ═══════════════════════════════════════════════════════════════
                # НОРМАЛЬНЫЙ РЕЖИМ — стандартная цепочка
                # ═══════════════════════════════════════════════════════════════
                should_be_master = self.am_i_the_master()

                # Записываем время отклика
                check_duration = time.time() - check_start_time
                self.attack_detector.record_response_time(check_duration)

                if should_be_master and not was_master:
                    # Стали мастером
                    self.is_master = True
                    was_master = True
                    logger.info(f"👑 {self.my_name} → MASTER")
                    logger.info(f"   Цепочка: {self.get_chain_status()}")
                    self.attack_detector.record_success()
                    await on_become_master()

                elif not should_be_master and was_master:
                    # Потеряли мастерство (кто-то выше ожил)
                    self.is_master = False
                    was_master = False
                    logger.info(f"😴 {self.my_name} → STANDBY (узел выше ожил)")
                    logger.info(f"   Цепочка: {self.get_chain_status()}")
                    await on_become_standby()

                elif not should_be_master and not was_master:
                    # Всё ещё standby
                    logger.debug(f"😴 {self.my_name} — STANDBY")

                # Ждём до следующей проверки
                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в leader loop: {e}")
                self.attack_detector.record_failure()
                await asyncio.sleep(check_interval)


# ═══════════════════════════════════════════════════════════════════════════════
#                              SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_leader_election: Optional[LeaderElection] = None

def get_leader_election() -> LeaderElection:
    """Получить singleton экземпляр LeaderElection"""
    global _leader_election
    if _leader_election is None:
        _leader_election = LeaderElection()
    return _leader_election


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🏔 Montana 3-Mirror Leader Election Test")
    print("=" * 50)

    le = get_leader_election()

    print(f"\nМой узел: {le.my_name}")
    print(f"Мой IP: {le.my_ip}")
    print(f"Моя позиция: {le.my_position}")
    print(f"\nЦепочка узлов:")

    for i, (name, ip) in enumerate(le.chain):
        alive = check_node_health(ip)
        status = "🟢 ALIVE" if alive else "🔴 DEAD"
        is_me = " ← Я" if name == le.my_name else ""
        print(f"  {i}. {name:12} {ip:16} {status}{is_me}")

    print(f"\nЯ мастер? {le.am_i_the_master()}")
    print(f"\nСтатус: {le.get_chain_status()}")
