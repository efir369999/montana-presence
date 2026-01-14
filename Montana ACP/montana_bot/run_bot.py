#!/usr/bin/env python3
"""
Montana Bot — Standalone Launcher
==================================

Запуск:
    cd "/Users/kh./Python/ACP_1/Montana ACP"
    source venv_junona3/bin/activate
    python montana_bot/run_bot.py

Токен (в порядке приоритета):
    1. Bitwarden (USE_BITWARDEN=True)
    2. Переменная окружения MONTANA_BOT_TOKEN
    3. .env файл
"""

import os
import sys
import asyncio
import logging
import subprocess
import json
import getpass
from pathlib import Path
from dotenv import load_dotenv

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent))

from telegram import BotCommand
from telegram.ext import ApplicationBuilder
from bot_handlers import register_montana_handlers, storage

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Filter noisy logs from httpx/urllib3
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

class HttpxFilter(logging.Filter):
    def filter(self, record):
        return "httpx" not in record.getMessage() and "POST https://api.telegram.org" not in record.getMessage()

logger = logging.getLogger(__name__)
logger.addFilter(HttpxFilter())

# Переключатель: True = Bitwarden, False = .env
USE_BITWARDEN = False
BITWARDEN_ITEM_NAME = "telegram_token_stat_20250711_001626"


def get_session_key() -> str:
    """Получить session key от Bitwarden."""
    print("\n" + "="*50)
    print("BITWARDEN AUTH")
    print("="*50)
    print("\nВыполни в другом терминале: bw login --raw")
    print("Введи email, пароль, 2FA код.")
    print("Вставь полученный session key ниже.\n")

    for attempt in range(3):
        session_key = getpass.getpass("Session key: ").strip()
        if session_key:
            return session_key
        print(f"Попытка {attempt + 1}/3. Повтори ввод.")

    raise Exception("Session key не введён")


def get_from_bitwarden(session_key: str, item_name: str) -> str:
    """Получить значение из Bitwarden по имени item."""
    cmd = ["bw", "get", "item", item_name, "--session", session_key]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=30)

        if process.returncode != 0:
            raise Exception(f"Bitwarden error: {stderr.strip()}")

        if not stdout.strip():
            raise Exception(f"Empty response for {item_name}")

        item = json.loads(stdout)
        return item['notes']

    except subprocess.TimeoutExpired:
        process.kill()
        raise Exception("Bitwarden timeout")
    except json.JSONDecodeError as e:
        raise Exception(f"JSON parse error: {e}")


def get_token() -> str:
    """Получить токен бота."""

    # 1. Bitwarden
    if USE_BITWARDEN:
        try:
            session_key = get_session_key()
            token = get_from_bitwarden(session_key, BITWARDEN_ITEM_NAME)
            logger.info(f"Token from Bitwarden: {token[:10]}...")
            return token
        except Exception as e:
            logger.error(f"Bitwarden failed: {e}")
            print("\nFallback to env/manual input...")

    # 2. Переменная окружения
    token = os.getenv('MONTANA_BOT_TOKEN')
    if token:
        return token

    # 3. .env файл
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        token = os.getenv('MONTANA_BOT_TOKEN')
        if token:
            return token

    # 4. Ввод вручную
    print("\nТокен не найден. Введи вручную:")
    token = input("Token: ").strip()

    if not token:
        print("Токен не введён. Выход.")
        sys.exit(1)

    return token


async def post_init(application):
    """Callback после инициализации бота — установить команды меню."""
    commands = [
        BotCommand("start", "Полное API Montana"),
        BotCommand("montana", "Genesis Identity"),
        BotCommand("montana_stats", "Статистика"),
        BotCommand("montana_rate", "Эмиссия Ɉ"),
        BotCommand("montana_info", "Протокол Montana"),
        BotCommand("montana_map", "Карта узлов"),
        BotCommand("thoughts", "Поток мыслей по маркеру"),
        BotCommand("node", "Управление Full Node"),
        BotCommand("bots", "Управление ботами"),
    ]
    await application.bot.set_my_commands(commands)
    print("Bot menu commands set")


def main():
    """Запуск бота."""
    token = get_token()

    print("\n" + "="*50)
    print("MONTANA VERIFIED USERS BOT")
    print("="*50)
    print(f"\nData directory: {storage.data_dir}")
    print(f"Keys loaded: {len(storage._keys)}")
    print("")

    # Build application с post_init для установки команд меню
    application = ApplicationBuilder().token(token).post_init(post_init).build()

    # Register Montana handlers
    register_montana_handlers(application)

    print("Starting bot...")
    print("Press Ctrl+C to stop\n")

    # Run (blocking call)
    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBot stopped.")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
