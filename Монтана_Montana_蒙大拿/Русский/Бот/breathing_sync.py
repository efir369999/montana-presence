#!/usr/bin/env python3
"""
breathing_sync.py
Montana Protocol — P2P Rsync Synchronization

Прямая синхронизация файлов между узлами через rsync + SSH.
БЕЗ GIT, БЕЗ GITHUB — только P2P.

Механизм:
- Мастер (текущий активный) → ВЫДЫХАЕТ (rsync push) ко ВСЕМ остальным узлам
- Остальные узлы → ВДЫХАЮТ (rsync pull) от МАСТЕРА
- При изменении кода (.py) → автоматический перезапуск сервиса

Цепочка приоритетов (для определения мастера):
  Amsterdam → Moscow → Almaty → SPB → Novosibirsk
     1           2         3       4         5
"""

import os
import asyncio
import logging
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                              CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════

class NodeCircuitBreaker:
    """
    Circuit Breaker для узлов — подавление спама ошибок.
    """

    FAILURE_THRESHOLD = 3
    SUCCESS_THRESHOLD = 2
    BASE_BACKOFF_SEC = 30
    MAX_BACKOFF_SEC = 300

    def __init__(self):
        self.states = {}
        self.failures = {}
        self.successes = {}
        self.backoff_until = {}

    def can_request(self, node_name: str) -> bool:
        state = self.states.get(node_name, "closed")

        if state == "closed":
            return True

        if state == "open":
            if time.time() >= self.backoff_until.get(node_name, 0):
                self.states[node_name] = "half_open"
                self.successes[node_name] = 0
                return True
            return False

        return True

    def record_success(self, node_name: str):
        state = self.states.get(node_name, "closed")

        if state == "half_open":
            self.successes[node_name] = self.successes.get(node_name, 0) + 1
            if self.successes[node_name] >= self.SUCCESS_THRESHOLD:
                self.states[node_name] = "closed"
                self.failures[node_name] = 0
                logger.info(f"✅ Circuit CLOSED: узел {node_name} восстановлен")
        else:
            self.failures[node_name] = 0

    def record_failure(self, node_name: str) -> bool:
        self.failures[node_name] = self.failures.get(node_name, 0) + 1
        count = self.failures[node_name]
        state = self.states.get(node_name, "closed")

        if state == "half_open":
            self._open_circuit(node_name)
            return False

        if count >= self.FAILURE_THRESHOLD:
            if state != "open":
                self._open_circuit(node_name)
                return True
            return False

        return count < self.FAILURE_THRESHOLD

    def _open_circuit(self, node_name: str):
        self.states[node_name] = "open"
        multiplier = min(self.failures.get(node_name, 1), 5)
        backoff = min(self.BASE_BACKOFF_SEC * (2 ** (multiplier - 1)), self.MAX_BACKOFF_SEC)
        self.backoff_until[node_name] = time.time() + backoff
        logger.warning(f"🔴 Circuit OPEN: узел {node_name} недоступен, backoff {backoff}s")

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        return {
            node: {
                "state": self.states.get(node, "closed"),
                "failures": self.failures.get(node, 0),
                "backoff_remaining": max(0, int(self.backoff_until.get(node, 0) - now))
            }
            for node in set(list(self.states.keys()) + list(self.failures.keys()))
        }


_circuit_breaker = NodeCircuitBreaker()


# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

class BreathingConfig:
    """Конфигурация P2P Rsync Sync"""

    # Интервалы
    SYNC_INTERVAL_SEC = 12
    STARTUP_DELAY_SEC = 5

    # Таймауты
    RSYNC_TIMEOUT_SEC = 60

    # Исключения для rsync
    RSYNC_EXCLUDE = [
        ".git",
        "__pycache__",
        "*.pyc",
        "*.log",
        ".env",
        "*.tmp",
        "*.swp",
    ]

    # Файлы, изменение которых требует перезапуска сервиса
    CODE_FILES = [
        "junomontanaagibot.py",
        "leader_election.py",
        "junona_ai.py",
        "junona_agents.py",
        "node_crypto.py",
        "time_bank.py",
        "breathing_sync.py",
        "contracts.py",
        "montana_db.py",
        "event_ledger.py",
        "junona_rag.py",
        "wallet_wizard.py",
        "sms_gateway.py",
        "webrtc_signaling.py",
    ]

    # Узлы сети
    NODE_CHAIN = [
        {
            "name": "amsterdam",
            "priority": 1,
            "ssh": "root@72.56.102.240",
            "path": "/root/bot"
        },
        {
            "name": "moscow",
            "priority": 2,
            "ssh": "root@176.124.208.93",
            "path": "/root/bot"
        },
        {
            "name": "almaty",
            "priority": 3,
            "ssh": "root@91.200.148.93",
            "path": "/root/bot"
        },
        {
            "name": "spb",
            "priority": 4,
            "ssh": "root@188.225.58.98",
            "path": "/root/bot"
        },
        {
            "name": "novosibirsk",
            "priority": 5,
            "ssh": "root@147.45.147.247",
            "path": "/root/bot"
        },
    ]

    @classmethod
    def get_node_by_name(cls, name: str) -> Optional[Dict]:
        for node in cls.NODE_CHAIN:
            if node["name"] == name:
                return node
        return None

    @classmethod
    def get_all_other_nodes(cls, current_name: str) -> List[Dict]:
        return [node for node in cls.NODE_CHAIN if node["name"] != current_name]

    @classmethod
    def get_default_master(cls) -> Dict:
        return cls.NODE_CHAIN[0]


# ═══════════════════════════════════════════════════════════════════════════════
#                              BREATHING SYNC (RSYNC)
# ═══════════════════════════════════════════════════════════════════════════════

class BreathingSync:
    """
    P2P Rsync Synchronization — прямая синхронизация без git/github

    Метафора дыхания:
    - Мастер: ВЫДЫХАЕТ (rsync push) ко ВСЕМ остальным узлам
    - Не-мастер: ВДЫХАЕТ (rsync pull) от текущего МАСТЕРА

    При изменении кода → автоматический перезапуск сервиса
    """

    def __init__(self, local_path: Path = None, node_name: str = None, get_master_func=None):
        self.local_path = local_path or Path(__file__).parent
        self.node_name = node_name or self._detect_node_name()
        self._running = False
        self._stop_event = asyncio.Event()
        self._get_master_func = get_master_func

        self.current_node = BreathingConfig.get_node_by_name(self.node_name)
        self.other_nodes = BreathingConfig.get_all_other_nodes(self.node_name)

        # Статистика
        self.stats = {
            "total_inhales": 0,
            "total_exhales": 0,
            "failed_inhales": 0,
            "failed_exhales": 0,
            "last_inhale": None,
            "last_exhale": None,
            "last_inhale_from": None,
            "last_exhale_to": [],
            "last_error": None,
            "restarts_triggered": 0,
            "node_name": self.node_name,
        }

        logger.info(f"🌬 BreathingSync P2P (rsync) инициализирован")
        logger.info(f"   Узел: {self.node_name}")
        logger.info(f"   Путь: {self.local_path}")
        logger.info(f"   Связан с: {[n['name'] for n in self.other_nodes]}")

    def _detect_node_name(self) -> str:
        node_name = os.environ.get("MONTANA_NODE_NAME")
        if node_name:
            return node_name.lower()

        import socket
        hostname = socket.gethostname().lower()

        for node in BreathingConfig.NODE_CHAIN:
            if node["name"] in hostname:
                return node["name"]

        return "amsterdam"

    def get_current_master(self) -> str:
        if self._get_master_func:
            try:
                return self._get_master_func()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка get_master_func: {e}")
        return BreathingConfig.get_default_master()["name"]

    def is_master(self) -> bool:
        return self.node_name == self.get_current_master()

    def _get_code_hashes(self) -> Dict[str, str]:
        """Получить хэши всех Python файлов кода"""
        hashes = {}
        for filename in BreathingConfig.CODE_FILES:
            filepath = self.local_path / filename
            if filepath.exists():
                try:
                    content = filepath.read_bytes()
                    hashes[filename] = hashlib.md5(content).hexdigest()
                except Exception:
                    pass
        return hashes

    def _check_code_changed(self, before_hashes: Dict[str, str]) -> List[str]:
        """Проверить какие файлы кода изменились"""
        after_hashes = self._get_code_hashes()
        changed = []

        for filename in BreathingConfig.CODE_FILES:
            before = before_hashes.get(filename)
            after = after_hashes.get(filename)
            if before != after:
                changed.append(filename)

        return changed

    async def _restart_service(self, changed_files: List[str]):
        """Перезапустить сервис после обновления кода"""
        logger.warning(f"🔄 Код обновлён ({len(changed_files)} файлов) — перезапуск сервиса...")
        for f in changed_files[:5]:
            logger.info(f"   📝 {f}")

        self.stats["restarts_triggered"] += 1

        await asyncio.sleep(3)

        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl", "restart", "junona",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 0:
                logger.info("✅ Сервис junona перезапущен")
            else:
                logger.error(f"❌ Ошибка перезапуска: {stderr.decode()}")

        except Exception as e:
            logger.error(f"❌ Не удалось перезапустить сервис: {e}")

    def _build_rsync_cmd(self, source: str, dest: str, push: bool = True) -> List[str]:
        """Построить команду rsync"""
        cmd = [
            "rsync",
            "-avz",                    # archive, verbose, compress
            "--delete",                # удалять лишние файлы на dest
            "-e", "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10",
        ]

        # Исключения
        for pattern in BreathingConfig.RSYNC_EXCLUDE:
            cmd.extend(["--exclude", pattern])

        cmd.extend([source, dest])
        return cmd

    async def _run_rsync(self, cmd: List[str], timeout: int = None) -> Dict[str, Any]:
        """Выполнить rsync команду асинхронно"""
        timeout = timeout or BreathingConfig.RSYNC_TIMEOUT_SEC

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode().strip() if stdout else "",
                "stderr": stderr.decode().strip() if stderr else "",
                "returncode": proc.returncode
            }

        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Timeout after {timeout} seconds",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }

    async def inhale(self) -> bool:
        """
        Вдох — rsync pull от мастера

        Если обновился код → автоматический перезапуск сервиса
        """
        if self.is_master():
            logger.debug("🫁 Inhale: мы мастер, пропуск")
            return True

        master_name = self.get_current_master()
        master_node = BreathingConfig.get_node_by_name(master_name)

        if not master_node:
            logger.error(f"❌ Мастер {master_name} не найден в конфигурации")
            return False

        if not _circuit_breaker.can_request(master_name):
            logger.debug(f"🫁 Inhale: мастер {master_name} в backoff, пропуск")
            return False

        # Сохраняем хэши кода ПЕРЕД sync
        code_hashes_before = self._get_code_hashes()

        # rsync pull: master → local
        source = f"{master_node['ssh']}:{master_node['path']}/"
        dest = f"{self.local_path}/"

        cmd = self._build_rsync_cmd(source, dest, push=False)
        result = await self._run_rsync(cmd)

        self.stats["total_inhales"] += 1
        self.stats["last_inhale"] = datetime.now(timezone.utc).isoformat()
        self.stats["last_inhale_from"] = master_name

        if result["success"]:
            _circuit_breaker.record_success(master_name)

            # Проверяем изменился ли код
            changed_files = self._check_code_changed(code_hashes_before)
            if changed_files:
                logger.info(f"🫁 Inhale: получены изменения от {master_name}")
                await self._restart_service(changed_files)
            else:
                logger.debug(f"🫁 Inhale: синхронизировано с {master_name} (без изменений кода)")

            return True
        else:
            self.stats["failed_inhales"] += 1
            self.stats["last_error"] = result["stderr"]

            should_log = _circuit_breaker.record_failure(master_name)
            if should_log:
                logger.warning(f"🫁 Inhale от {master_name} failed: {result['stderr'][:100]}")

            return False

    async def exhale(self) -> bool:
        """
        Выдох — rsync push ко всем остальным узлам (только мастер)
        """
        if not self.is_master():
            logger.debug("💨 Exhale: не мастер, пропуск")
            return True

        # Фильтруем узлы через Circuit Breaker
        nodes_to_push = [
            node for node in self.other_nodes
            if _circuit_breaker.can_request(node["name"])
        ]

        if not nodes_to_push:
            logger.debug("💨 Exhale: все узлы в backoff, пропуск")
            return True

        # Параллельный rsync ко всем узлам
        async def push_to_node(node):
            source = f"{self.local_path}/"
            dest = f"{node['ssh']}:{node['path']}/"

            cmd = self._build_rsync_cmd(source, dest, push=True)
            result = await self._run_rsync(cmd, timeout=30)
            return node["name"], result

        results = await asyncio.gather(
            *[push_to_node(node) for node in nodes_to_push],
            return_exceptions=True
        )

        # Обработка результатов
        success_nodes = []
        failed_nodes = []

        for item in results:
            if isinstance(item, Exception):
                continue

            node_name, result = item

            if result["success"]:
                success_nodes.append(node_name)
                _circuit_breaker.record_success(node_name)
            else:
                failed_nodes.append(node_name)
                should_log = _circuit_breaker.record_failure(node_name)
                if should_log:
                    logger.warning(f"💨 Push к {node_name} failed: {result['stderr'][:80]}")

        self.stats["total_exhales"] += 1
        self.stats["last_exhale"] = datetime.now(timezone.utc).isoformat()
        self.stats["last_exhale_to"] = success_nodes

        if success_nodes:
            logger.info(f"💨 Exhale: {len(success_nodes)}/{len(nodes_to_push)} узлов обновлено")
            return True
        else:
            self.stats["failed_exhales"] += 1
            logger.error("💨 Exhale FAILED: ни один узел недоступен")
            return False

    async def breathe(self) -> Dict[str, bool]:
        """Один цикл дыхания: вдох + выдох"""
        inhale_ok = await self.inhale()
        exhale_ok = await self.exhale()

        return {
            "inhale": inhale_ok,
            "exhale": exhale_ok
        }

    def stop(self):
        """Остановить синхронизацию"""
        self._stop_event.set()
        self._running = False

    async def run_breathing_loop(
        self,
        interval: int = None,
        only_when_master: bool = False,
        is_master_func=None
    ):
        """
        Основной цикл дыхания

        Args:
            interval: Интервал в секундах
            only_when_master: Синхронизировать только когда мастер (для exhale)
            is_master_func: Функция проверки мастерства
        """
        interval = interval or BreathingConfig.SYNC_INTERVAL_SEC

        logger.info(f"🌬 Breathing Sync P2P запущен (интервал {interval}s)")

        await asyncio.sleep(BreathingConfig.STARTUP_DELAY_SEC)

        self._running = True
        consecutive_errors = 0

        while not self._stop_event.is_set():
            try:
                result = await self.breathe()

                if result["inhale"] and result["exhale"]:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                self.stats["last_error"] = str(e)

                if consecutive_errors <= 3:
                    logger.error(f"🌬 Breathing error: {e}")

                await asyncio.sleep(interval)

        logger.info("🌬 Breathing Sync остановлен")

    def get_stats(self) -> Dict[str, Any]:
        """Статистика синхронизации"""
        return {
            **self.stats,
            "local_path": str(self.local_path),
            "interval_sec": BreathingConfig.SYNC_INTERVAL_SEC,
            "is_running": self._running,
            "is_master": self.is_master(),
            "current_master": self.get_current_master(),
            "circuit_breaker": _circuit_breaker.get_status()
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                              SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_breathing_sync: Optional[BreathingSync] = None


def get_breathing_sync(
    local_path: Path = None,
    node_name: str = None,
    get_master_func=None
) -> BreathingSync:
    """Получить singleton экземпляр BreathingSync"""
    global _breathing_sync
    if _breathing_sync is None:
        _breathing_sync = BreathingSync(local_path, node_name, get_master_func)
    return _breathing_sync


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🌬 Montana P2P Breathing Sync (rsync)")
    print("=" * 60)
    print("Без git, без GitHub — только rsync через SSH")
    print("Мастер пушит ВСЕМ, остальные пуллят от МАСТЕРА")
    print("=" * 60)

    node_name = None
    master_override = None

    for arg in sys.argv[1:]:
        if arg.startswith("--node="):
            node_name = arg.split("=")[1]
        elif arg.startswith("--master="):
            master_override = arg.split("=")[1]

    get_master = (lambda: master_override) if master_override else None
    sync = get_breathing_sync(node_name=node_name, get_master_func=get_master)

    print(f"\n📍 Узел: {sync.node_name}")
    print(f"👑 Мастер: {sync.get_current_master()}")
    print(f"   {'Мы МАСТЕР — пушим всем' if sync.is_master() else f'Пуллим от {sync.get_current_master()}'}")
    print()

    async def run_cli(sync, cmd):
        if cmd == "inhale":
            print("🫁 Вдох (rsync pull от мастера)...")
            result = await sync.inhale()
            print(f"   Результат: {'✅' if result else '❌'}")

        elif cmd == "exhale":
            print("💨 Выдох (rsync push ко всем)...")
            result = await sync.exhale()
            print(f"   Результат: {'✅' if result else '❌'}")

        elif cmd == "breathe":
            print("🌬 Дыхание...")
            result = await sync.breathe()
            print(f"   Вдох: {'✅' if result['inhale'] else '❌'}")
            print(f"   Выдох: {'✅' if result['exhale'] else '❌'}")

        elif cmd == "loop":
            print("🔄 Запуск цикла (Ctrl+C для остановки)...")
            await sync.run_breathing_loop()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd in ["inhale", "exhale", "breathe", "loop"]:
            try:
                asyncio.run(run_cli(sync, cmd))
            except KeyboardInterrupt:
                print("\n⏹ Остановлено")

        elif cmd == "stats":
            stats = sync.get_stats()
            print("📊 Статистика:")
            for k, v in stats.items():
                print(f"   {k}: {v}")

        elif cmd == "nodes":
            print("🔗 Узлы сети:")
            for node in BreathingConfig.NODE_CHAIN:
                is_current = node["name"] == sync.node_name
                is_master = node["name"] == sync.get_current_master()
                marker = " 👈 (мы)" if is_current else ""
                master_mark = " 👑" if is_master else ""
                print(f"   {node['priority']}. {node['name']}{master_mark}{marker}")
                print(f"      {node['ssh']}:{node['path']}")
    else:
        print("""
Использование:
  python breathing_sync.py inhale    — rsync pull от мастера
  python breathing_sync.py exhale    — rsync push ко всем (если мастер)
  python breathing_sync.py breathe   — один цикл
  python breathing_sync.py loop      — запуск цикла
  python breathing_sync.py stats     — статистика
  python breathing_sync.py nodes     — список узлов

Опции:
  --node=NAME     — указать имя узла
  --master=NAME   — указать мастера (для теста)
        """)
