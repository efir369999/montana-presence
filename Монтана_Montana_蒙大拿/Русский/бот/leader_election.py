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
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

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
        self.my_name: Optional[str] = None
        self.my_ip: Optional[str] = None
        self.my_position: int = -1  # Позиция в цепочке (-1 = не в цепочке)
        self.is_master: bool = False
        self._stop_event = asyncio.Event()

        # Breathing Sync
        self._breathing_sync: Optional[BreathingSync] = None
        self._breathing_task: Optional[asyncio.Task] = None

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

        Каждые check_interval секунд:
        1. Проверяем всех кто выше в цепочке
        2. Если все мертвы — становимся мастером
        3. Если кто-то жив — уходим в standby
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

        while not self._stop_event.is_set():
            try:
                # Проверяем статус цепочки
                should_be_master = self.am_i_the_master()

                if should_be_master and not was_master:
                    # Стали мастером
                    self.is_master = True
                    was_master = True
                    logger.info(f"👑 {self.my_name} → MASTER")
                    logger.info(f"   Цепочка: {self.get_chain_status()}")
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
