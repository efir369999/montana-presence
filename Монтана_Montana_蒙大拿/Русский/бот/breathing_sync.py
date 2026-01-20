#!/usr/bin/env python3
"""
breathing_sync.py
Montana Protocol — Breathing Synchronization

Механизм синхронизации через git:
- Каждые 12 секунд все узлы "дышат"
- Inhale (вдох): git pull — получаем изменения
- Exhale (выдох): git push — отправляем свои изменения

Из документации 003_ТРОЙНОЕ_ЗЕРКАЛО.md
"""

import os
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════════════════════

class BreathingConfig:
    """Конфигурация Breathing Sync"""

    # Интервалы
    SYNC_INTERVAL_SEC = 12          # Интервал синхронизации (секунды)
    STARTUP_DELAY_SEC = 5           # Задержка перед первой синхронизацией

    # Git
    REMOTE_NAME = "origin"
    BRANCH_NAME = "main"

    # Таймауты
    GIT_TIMEOUT_SEC = 30            # Таймаут git операций

    # Файлы для синхронизации
    SYNC_PATHS = [
        "data/users.json",
        "node_crypto/nodes.json",
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#                              BREATHING SYNC
# ═══════════════════════════════════════════════════════════════════════════════

class BreathingSync:
    """
    Breathing Sync — синхронизация узлов через git

    Метафора дыхания:
    - Inhale (вдох): получаем изменения из сети (git pull)
    - Exhale (выдох): отдаём свои изменения в сеть (git push)

    Цикл каждые 12 секунд = ~5 "вдохов" в минуту
    """

    def __init__(self, repo_path: Path = None):
        """
        Args:
            repo_path: Путь к git репозиторию (по умолчанию текущая директория)
        """
        self.repo_path = repo_path or Path(__file__).parent
        self._running = False
        self._stop_event = asyncio.Event()

        # Статистика
        self.stats = {
            "total_inhales": 0,
            "total_exhales": 0,
            "failed_inhales": 0,
            "failed_exhales": 0,
            "last_inhale": None,
            "last_exhale": None,
            "last_error": None
        }

        logger.info(f"🌬 BreathingSync инициализирован")
        logger.info(f"   Репозиторий: {self.repo_path}")
        logger.info(f"   Интервал: {BreathingConfig.SYNC_INTERVAL_SEC} сек")

    def _run_git_command(self, args: list, timeout: int = None) -> Dict[str, Any]:
        """
        Выполняет git команду

        Args:
            args: Аргументы git (например ['pull', 'origin', 'main'])
            timeout: Таймаут в секундах

        Returns:
            {
                "success": bool,
                "stdout": str,
                "stderr": str,
                "returncode": int
            }
        """
        timeout = timeout or BreathingConfig.GIT_TIMEOUT_SEC
        cmd = ["git", "-C", str(self.repo_path)] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode
            }

        except subprocess.TimeoutExpired:
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

    def inhale(self) -> bool:
        """
        Вдох — получаем изменения из сети (git pull)

        Returns:
            True если успешно
        """
        logger.debug("🫁 Inhale (git pull)...")

        # git pull origin main --rebase
        result = self._run_git_command([
            "pull",
            BreathingConfig.REMOTE_NAME,
            BreathingConfig.BRANCH_NAME,
            "--rebase"
        ])

        self.stats["total_inhales"] += 1
        self.stats["last_inhale"] = datetime.now(timezone.utc).isoformat()

        if result["success"]:
            if "Already up to date" not in result["stdout"]:
                logger.info(f"🫁 Inhale: получены изменения")
            return True
        else:
            self.stats["failed_inhales"] += 1
            self.stats["last_error"] = result["stderr"]
            logger.warning(f"🫁 Inhale failed: {result['stderr']}")
            return False

    def exhale(self) -> bool:
        """
        Выдох — отправляем изменения в сеть (git push)

        Returns:
            True если успешно
        """
        logger.debug("💨 Exhale (git push)...")

        # Сначала проверяем есть ли что пушить
        status = self._run_git_command(["status", "--porcelain"])
        if not status["stdout"]:
            # Нет изменений — пропускаем push
            logger.debug("💨 Exhale: нет изменений для отправки")
            return True

        # Добавляем изменения
        for path in BreathingConfig.SYNC_PATHS:
            full_path = self.repo_path / path
            if full_path.exists():
                self._run_git_command(["add", path])

        # Коммитим
        commit_result = self._run_git_command([
            "commit",
            "-m",
            f"[sync] breathing {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ])

        if not commit_result["success"] and "nothing to commit" not in commit_result["stderr"]:
            logger.debug(f"💨 Exhale: nothing to commit")
            return True

        # Пушим
        result = self._run_git_command([
            "push",
            BreathingConfig.REMOTE_NAME,
            BreathingConfig.BRANCH_NAME
        ])

        self.stats["total_exhales"] += 1
        self.stats["last_exhale"] = datetime.now(timezone.utc).isoformat()

        if result["success"]:
            logger.info(f"💨 Exhale: изменения отправлены")
            return True
        else:
            self.stats["failed_exhales"] += 1
            self.stats["last_error"] = result["stderr"]
            logger.warning(f"💨 Exhale failed: {result['stderr']}")
            return False

    def breathe(self) -> Dict[str, bool]:
        """
        Один цикл дыхания: вдох + выдох

        Returns:
            {"inhale": bool, "exhale": bool}
        """
        inhale_ok = self.inhale()
        exhale_ok = self.exhale()

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
        only_when_master: bool = True,
        is_master_func=None
    ):
        """
        Основной цикл дыхания

        Args:
            interval: Интервал в секундах (по умолчанию 12)
            only_when_master: Синхронизировать только когда узел — мастер
            is_master_func: Функция проверки мастерства (возвращает bool)
        """
        interval = interval or BreathingConfig.SYNC_INTERVAL_SEC

        logger.info(f"🌬 Запуск Breathing Sync (интервал {interval} сек)")

        # Начальная задержка
        await asyncio.sleep(BreathingConfig.STARTUP_DELAY_SEC)

        self._running = True

        while not self._stop_event.is_set():
            try:
                # Проверяем мастерство если нужно
                if only_when_master and is_master_func:
                    if not is_master_func():
                        logger.debug("🌬 Пропуск sync (не мастер)")
                        await asyncio.sleep(interval)
                        continue

                # Дышим
                result = self.breathe()

                if result["inhale"] and result["exhale"]:
                    logger.debug(f"🌬 Breathing OK")

                # Ждём следующий цикл
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"🌬 Breathing error: {e}")
                self.stats["last_error"] = str(e)
                await asyncio.sleep(interval)

        logger.info("🌬 Breathing Sync остановлен")

    def get_stats(self) -> Dict[str, Any]:
        """Статистика синхронизации"""
        return {
            **self.stats,
            "repo_path": str(self.repo_path),
            "interval_sec": BreathingConfig.SYNC_INTERVAL_SEC,
            "is_running": self._running
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                              SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_breathing_sync: Optional[BreathingSync] = None


def get_breathing_sync(repo_path: Path = None) -> BreathingSync:
    """Получить singleton экземпляр BreathingSync"""
    global _breathing_sync
    if _breathing_sync is None:
        _breathing_sync = BreathingSync(repo_path)
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

    print("🌬 Montana Breathing Sync")
    print("=" * 50)

    sync = get_breathing_sync()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "inhale":
            print("🫁 Вдох...")
            result = sync.inhale()
            print(f"   Результат: {'✅' if result else '❌'}")

        elif cmd == "exhale":
            print("💨 Выдох...")
            result = sync.exhale()
            print(f"   Результат: {'✅' if result else '❌'}")

        elif cmd == "breathe":
            print("🌬 Дыхание...")
            result = sync.breathe()
            print(f"   Вдох: {'✅' if result['inhale'] else '❌'}")
            print(f"   Выдох: {'✅' if result['exhale'] else '❌'}")

        elif cmd == "stats":
            stats = sync.get_stats()
            print("📊 Статистика:")
            for k, v in stats.items():
                print(f"   {k}: {v}")

        elif cmd == "loop":
            print("🔄 Запуск цикла (Ctrl+C для остановки)...")
            try:
                asyncio.run(sync.run_breathing_loop(only_when_master=False))
            except KeyboardInterrupt:
                print("\n⏹ Остановлено")
        else:
            print(f"Неизвестная команда: {cmd}")
    else:
        print("""
Использование:
  python breathing_sync.py inhale   — вдох (git pull)
  python breathing_sync.py exhale   — выдох (git push)
  python breathing_sync.py breathe  — один цикл дыхания
  python breathing_sync.py stats    — статистика
  python breathing_sync.py loop     — запуск цикла
        """)
