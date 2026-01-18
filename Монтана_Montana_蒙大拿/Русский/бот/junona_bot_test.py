# junona_bot_test.py
# Юнона — Montana Test Edition
# ТЕСТОВАЯ ВЕРСИЯ: только параллельные агенты + статус сети

import os
import json
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# Montana Evolution
from session_manager import get_session_manager
from junona_agents import get_orchestrator

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA")
BOT_DIR = Path(__file__).parent

# Montana Evolution
ENABLE_PARALLEL_AGENTS = os.getenv("ENABLE_PARALLEL_AGENTS", "true").lower() == "true"
AGENT_MODE = os.getenv("AGENT_MODE", "synthesize")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#                              MONTANA NETWORK
# ═══════════════════════════════════════════════════════════════════════════════

NODES = {
    "amsterdam": {"ip": "72.56.102.240", "location": "🇳🇱 Amsterdam"},
    "moscow": {"ip": "176.124.208.93", "location": "🇷🇺 Moscow"},
    "almaty": {"ip": "91.200.148.93", "location": "🇰🇿 Almaty"},
    "spb": {"ip": "188.225.58.98", "location": "🇷🇺 St.Petersburg"},
    "novosibirsk": {"ip": "147.45.147.247", "location": "🇷🇺 Novosibirsk"}
}

def check_node_status(ip: str) -> bool:
    """Проверить статус узла через ping"""
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '1', ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2
        )
        return result.returncode == 0
    except:
        return False

async def get_network_status() -> str:
    """Получить статус сети Montana"""
    response = "🏔 Montana Network Status\n\n"

    online_count = 0
    for node_name, node_info in NODES.items():
        online = check_node_status(node_info["ip"])
        status_emoji = "●" if online else "○"
        status_text = "ONLINE" if online else "OFFLINE"

        response += f"{status_emoji} {node_info['location']}\n"
        response += f"   {node_info['ip']} — {status_text}\n\n"

        if online:
            online_count += 1

    health = int((online_count / len(NODES)) * 100)
    response += f"Network Health: {health}%\n"
    response += f"Online: {online_count}/{len(NODES)} nodes"

    return response

# ═══════════════════════════════════════════════════════════════════════════════
#                              MONTANA AGENTS
# ═══════════════════════════════════════════════════════════════════════════════

session_manager = get_session_manager()

try:
    orchestrator = get_orchestrator()
    logger.info("🏔 Montana Evolution: агенты инициализированы")
except Exception as e:
    orchestrator = None
    logger.warning(f"⚠️ Параллельные агенты недоступны: {e}")
    ENABLE_PARALLEL_AGENTS = False

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОМАНДЫ
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало — тестовая версия"""
    user = update.message.from_user

    welcome = f"""Ɉ Montana Test Edition

Привет, {user.first_name}.

Это тестовая версия Юноны.
Доступны только тестируемые функции:

/network - статус сети Montana
/help - помощь

Просто пиши — и Claude + GPT работают параллельно."""

    await update.message.reply_text(welcome)

async def network_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус сети"""
    await update.message.chat.send_action("typing")
    status = await get_network_status()
    await update.message.reply_text(f"Ɉ\n\n{status}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = """Ɉ Montana Test Edition

**Тестируемые функции:**

1. Параллельные агенты
   • Claude Sonnet 4.5 + GPT-4o работают одновременно
   • Каждый агент думает независимо
   • Юнона синтезирует финальный ответ

2. Статус сети
   • /network — статус 5 узлов Montana
   • Мониторинг в реальном времени

**Dashboard:**
https://1394793-cy33234.tw1.ru

Просто пиши что угодно — система всё записывает."""

    await update.message.reply_text(help_text)

# ═══════════════════════════════════════════════════════════════════════════════
#                              ОСНОВНОЙ ОБРАБОТЧИК
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений — параллельные агенты"""
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    session = session_manager.get_active_session(user_id)
    await session.log_message("user", text)

    if ENABLE_PARALLEL_AGENTS and orchestrator:
        try:
            await update.message.chat.send_action("typing")

            response = await orchestrator.respond_parallel(
                prompt=text,
                context={
                    "prompt": text,
                    "lang": "ru",
                    "user_id": user_id,
                    "first_name": user.first_name
                },
                mode=AGENT_MODE
            )

            if response.thinking:
                await session.log_reasoning(
                    agent=response.agent,
                    thinking=response.thinking,
                    metadata={"tokens": response.tokens_used}
                )

            if response.signature_features:
                await session.save_cognitive_signature(
                    agent=response.agent,
                    signature=response.signature_features
                )

            await session.log_message("assistant", response.content, agent=response.agent)
            await update.message.reply_text(f"Ɉ\n\n{response.content}")

            logger.info(f"✓ {user.first_name}: {response.agent} ({response.tokens_used} tokens)")

        except Exception as e:
            logger.error(f"Montana Evolution error: {e}")
            await update.message.reply_text("Ɉ Временная ошибка. Попробуй ещё раз.")
    else:
        await update.message.reply_text("Ɉ Параллельные агенты временно недоступны.\n\nПроверь API ключи в .env")

# ═══════════════════════════════════════════════════════════════════════════════
#                              ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN_JUNONA not set")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_error_handler(error_handler)

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("network", network_command))
    application.add_handler(CommandHandler("help", help_command))

    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🏔 Юнона Montana Test Edition — запущена")
    logger.info(f"   Параллельные агенты: {'включены' if ENABLE_PARALLEL_AGENTS else 'выключены'}")
    logger.info(f"   Режим: {AGENT_MODE}")
    logger.info("   Dashboard: https://1394793-cy33234.tw1.ru")

    application.run_polling()
