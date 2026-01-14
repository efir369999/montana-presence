"""
Montana Node Control — управление Full Node через Telegram
============================================================

API для управления Montana Full Node и другими ботами через бот.
"""

import subprocess
import psutil
import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple


# ============================================================================
# PATHS
# ============================================================================

MONTANA_ROOT = Path(__file__).resolve().parents[1]
MONTANA_BIN = MONTANA_ROOT / "montana" / "target" / "release" / "montana"
MONTANA_DATA = MONTANA_ROOT / "montana" / "montana-data"

# Боты
BOTS_ROOT = Path("/root/projects/venv_junona3")
VENV_PYTHON = BOTS_ROOT / "bin/python3"

KNOWN_BOTS = {
    "j3_statbot": BOTS_ROOT / "j3_statbot_120.py",
    "j3_463": BOTS_ROOT / "j3_463.py",
    "j3_bot_111": BOTS_ROOT / "j3_bot_111.py",
}


# ============================================================================
# NODE CONTROL
# ============================================================================

def get_node_process() -> Optional[psutil.Process]:
    """Найти процесс Montana Full Node"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and 'montana' in ' '.join(cmdline):
                # Проверяем что это именно Full Node, а не montana_bot
                if 'target/release/montana' in ' '.join(cmdline) or 'montana/src/main.rs' in ' '.join(cmdline):
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def is_node_running() -> bool:
    """Проверить запущен ли Full Node"""
    return get_node_process() is not None


def start_node() -> Tuple[bool, str]:
    """Запустить Montana Full Node"""
    if is_node_running():
        return False, "Node уже запущен"

    if not MONTANA_BIN.exists():
        return False, f"Бинарник не найден: {MONTANA_BIN}\nСобери: cargo build --release"

    try:
        # Запуск в фоне
        cmd = f"cd {MONTANA_ROOT / 'montana'} && nohup {MONTANA_BIN} > montana-data/node.log 2>&1 &"
        subprocess.Popen(cmd, shell=True, start_new_session=True)
        return True, "Full Node запущен"
    except Exception as e:
        return False, f"Ошибка запуска: {e}"


def stop_node() -> Tuple[bool, str]:
    """Остановить Montana Full Node"""
    proc = get_node_process()
    if not proc:
        return False, "Node не запущен"

    try:
        proc.terminate()
        proc.wait(timeout=10)
        return True, "Full Node остановлен"
    except psutil.TimeoutExpired:
        proc.kill()
        return True, "Full Node убит (SIGKILL)"
    except Exception as e:
        return False, f"Ошибка остановки: {e}"


def get_node_status() -> Dict[str, any]:
    """Получить статус Full Node"""
    proc = get_node_process()

    if not proc:
        return {
            "running": False,
            "pid": None,
            "uptime": 0,
            "cpu": 0,
            "memory": 0,
        }

    try:
        return {
            "running": True,
            "pid": proc.pid,
            "uptime": psutil.time.time() - proc.create_time(),
            "cpu": proc.cpu_percent(interval=1),
            "memory": proc.memory_info().rss // (1024 * 1024),  # MB
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"running": False}


def get_node_logs(lines: int = 50) -> str:
    """Получить последние логи Full Node"""
    log_file = MONTANA_DATA / "node.log"

    if not log_file.exists():
        return "Логи не найдены"

    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            return ''.join(all_lines[-lines:])
    except Exception as e:
        return f"Ошибка чтения логов: {e}"


# ============================================================================
# BOTS CONTROL
# ============================================================================

def get_bot_process(bot_name: str) -> Optional[psutil.Process]:
    """Найти процесс бота по имени"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and bot_name in ' '.join(cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def is_bot_running(bot_name: str) -> bool:
    """Проверить запущен ли бот"""
    return get_bot_process(bot_name) is not None


def list_bots() -> List[Dict[str, any]]:
    """Список всех известных ботов и их статус"""
    bots = []

    for name, script_path in KNOWN_BOTS.items():
        proc = get_bot_process(name)
        bots.append({
            "name": name,
            "running": proc is not None,
            "pid": proc.pid if proc else None,
            "script": str(script_path),
        })

    return bots


def start_bot(bot_name: str) -> Tuple[bool, str]:
    """Запустить бота"""
    if bot_name not in KNOWN_BOTS:
        return False, f"Неизвестный бот: {bot_name}"

    if is_bot_running(bot_name):
        return False, f"{bot_name} уже запущен"

    script = KNOWN_BOTS[bot_name]
    if not script.exists():
        return False, f"Скрипт не найден: {script}"

    try:
        cmd = f"cd {BOTS_ROOT} && source bin/activate && nohup python3 {script.name} > logs/{bot_name}.log 2>&1 &"
        subprocess.Popen(cmd, shell=True, start_new_session=True, executable='/bin/bash')
        return True, f"{bot_name} запущен"
    except Exception as e:
        return False, f"Ошибка запуска: {e}"


def stop_bot(bot_name: str) -> Tuple[bool, str]:
    """Остановить бота"""
    proc = get_bot_process(bot_name)
    if not proc:
        return False, f"{bot_name} не запущен"

    try:
        proc.terminate()
        proc.wait(timeout=5)
        return True, f"{bot_name} остановлен"
    except psutil.TimeoutExpired:
        proc.kill()
        return True, f"{bot_name} убит (SIGKILL)"
    except Exception as e:
        return False, f"Ошибка остановки: {e}"


# ============================================================================
# NETWORK INFO
# ============================================================================

def get_peers_count() -> int:
    """Получить количество подключённых пиров"""
    # TODO: Реализовать через RPC Montana Full Node
    # Пока заглушка
    return 0


def get_sync_status() -> Dict[str, any]:
    """Получить статус синхронизации"""
    # TODO: Реализовать через RPC Montana Full Node
    return {
        "synced": False,
        "current_slice": 0,
        "target_slice": 0,
        "progress": 0.0,
    }
