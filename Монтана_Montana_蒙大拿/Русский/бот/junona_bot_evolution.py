# junona_bot_evolution.py
# Юнона — Montana Evolution Edition
# Параллельные агенты + Cognitive Signatures + Система уровней

import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import TelegramError

# Montana Evolution
from session_manager import get_session_manager
from junona_agents import get_orchestrator
from knowledge import get_knowledge

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA")
BOT_CREATOR_ID = 8552053404

BOT_DIR = Path(__file__).parent
USERS_FILE = BOT_DIR / "data" / "users.json"
STREAM_FILE = BOT_DIR / "data" / "stream.jsonl"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Montana Evolution
ENABLE_PARALLEL_AGENTS = os.getenv("ENABLE_PARALLEL_AGENTS", "true").lower() == "true"
AGENT_MODE = os.getenv("AGENT_MODE", "synthesize")  # synthesize | claude | gpt | both_visible

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#                              MONTANA EVOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

# Инициализация
session_manager = get_session_manager()

# Orchestrator (с fallback если нет API ключей)
try:
    orchestrator = get_orchestrator()
    logger.info("🏔 Montana Evolution: агенты инициализированы")
except Exception as e:
    orchestrator = None
    logger.warning(f"⚠️ Параллельные агенты недоступны: {e}")
    ENABLE_PARALLEL_AGENTS = False

# ═══════════════════════════════════════════════════════════════════════════════
#                              БАЗА ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════════

def load_users() -> dict:
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def get_user(user_id: int) -> dict:
    users = load_users()
    return users.get(str(user_id), {
        'lang': 'ru',
        'chapter': 0,
        'state': 'ready',
        'history': []
    })

def save_user(user_id: int, data: dict):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

# ═══════════════════════════════════════════════════════════════════════════════
#                              УРОВНИ: ОРАНГУТАНГ → АТЛАНТ
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_level(stats: dict) -> dict:
    """
    Расчёт уровня Орангутанга на основе статистики

    Факторы:
    - Сырые мысли (главный)
    - Качество reasoning (если доступно)
    - Дни активности
    - Консистентность
    """
    raw_thoughts = stats.get('raw_thoughts', 0)
    days_active = stats.get('days_active', 0)

    # Базовый уровень: 1 уровень за 10 мыслей
    base_level = min(99, raw_thoughts // 10)

    # Бонус за длительное участие: +1 уровень за каждые 30 дней
    time_bonus = min(10, days_active // 30)

    level = min(99, base_level + time_bonus)

    # Расчёт до следующего уровня и до Атланта
    to_next_level = 10 - (raw_thoughts % 10)
    to_atlant = max(0, 1000 - raw_thoughts)  # 1000 мыслей до уровня 100

    # Novelty и consistency (mock - можно реализовать ML)
    novelty_score = min(0.95, 0.5 + (raw_thoughts / 2000))  # растёт с опытом
    consistency_score = min(0.95, 0.6 + (days_active / 200))  # растёт со временем

    # Проверка условий для Атланта
    is_atlant_ready = (
        level >= 99 and
        days_active >= 100 and
        novelty_score >= 0.75 and
        consistency_score >= 0.85
    )

    role = "atlant" if is_atlant_ready else "orangutan"
    display_level = 100 if is_atlant_ready else level

    return {
        "level": display_level,
        "role": role,
        "to_next_level": to_next_level if not is_atlant_ready else 0,
        "to_atlant": to_atlant if not is_atlant_ready else 0,
        "novelty_score": novelty_score,
        "consistency_score": consistency_score,
        "is_atlant_ready": is_atlant_ready
    }

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОМАНДЫ
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало — приветствие с Montana Evolution"""
    user = update.message.from_user
    user_id = user.id

    # Создаём/получаем сессию
    session = session_manager.get_active_session(user_id)

    data = get_user(user_id)
    data['first_name'] = user.first_name
    data['username'] = user.username
    save_user(user_id, data)

    # Логируем в сессию
    await session.log_message("system", f"/start from {user.first_name}")

    welcome = f"""Ɉ Montana Evolution

Привет, {user.first_name}.

Я Юнона — хранитель Montana.
Теперь со мной работают Claude и GPT одновременно.

Каждая твоя сессия изолирована.
Каждая мысль записывается навсегда.
Каждый агент оставляет свой след.

/level - твой уровень Орангутанга
/cognitive - cognitive signatures
/sessions - история сессий
/help - помощь

Спрашивай что угодно."""

    await update.message.reply_text(welcome)

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать уровень Орангутанга"""
    user_id = update.message.from_user.id

    # Получить статистику
    stats = session_manager.get_user_stats(user_id)
    level_info = calculate_level(stats)

    # Визуализация
    if level_info['role'] == 'atlant':
        emoji = "🏔"
        title = f"Атлант уровня {level_info['level']}"
        extra = "\n\n✓ Хранитель 5 узлов\n✓ Голос в Совете Montana Guardian"
    else:
        emoji = "🦧"
        title = f"Орангутанг #{level_info['level']}"
        extra = f"\n\nДо следующего уровня: {level_info['to_next_level']} мыслей\nДо Атланта 🏔: {level_info['to_atlant']} мыслей"

    # Полоски
    novelty_bar = "█" * int(level_info['novelty_score'] * 10) + "░" * (10 - int(level_info['novelty_score'] * 10))
    consistency_bar = "█" * int(level_info['consistency_score'] * 10) + "░" * (10 - int(level_info['consistency_score'] * 10))

    response = f"""Ɉ Твой уровень в Montana

{emoji} {title}
├─ Сырых мыслей: {stats['raw_thoughts']:,}
├─ Дней в сети: {stats['days_active']}
├─ Новизна: {novelty_bar} {int(level_info['novelty_score']*100)}%
└─ Подпись: {consistency_bar} {int(level_info['consistency_score']*100)}%{extra}

Сессий: {stats['sessions']}
Reasoning логов: {stats['reasoning_logs']}"""

    await update.message.reply_text(response)

async def cognitive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать Cognitive Signatures текущей сессии"""
    user_id = update.message.from_user.id

    session = session_manager.get_active_session(user_id)
    signatures = session.get_cognitive_signatures()
    logs = session.get_reasoning_logs()

    if not signatures:
        await update.message.reply_text("Ɉ Cognitive Signatures пока не записаны.\n\nНапиши что-нибудь, чтобы агенты начали работать.")
        return

    response = "Ɉ Cognitive Signatures:\n\n"

    for agent, data in signatures.items():
        sig = data.get('signature', {})
        response += f"**{agent.title()}:**\n"

        # Style
        if 'style' in sig:
            style = sig['style']
            response += f"  Стиль: {style.get('avg_sentence_length', 0):.1f} слов/предложение\n"

        # Reasoning patterns
        if 'reasoning_pattern' in sig and sig['reasoning_pattern']:
            patterns = sig['reasoning_pattern']
            for key, val in patterns.items():
                if val > 0:
                    bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                    response += f"  {key}: {bar} {int(val*100)}%\n"

        response += "\n"

    response += f"Reasoning logs: {len(logs)} записей\n"
    response += f"Сессия: {session.id}"

    await update.message.reply_text(response, parse_mode="Markdown")

async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю сессий"""
    user_id = update.message.from_user.id

    sessions = session_manager.list_sessions(user_id, limit=10)

    if not sessions:
        await update.message.reply_text("Ɉ Сессий пока нет.")
        return

    response = "Ɉ Твои сессии:\n\n"

    for i, sess in enumerate(sessions):
        messages = sess.get_messages()
        created = datetime.fromisoformat(sess.created_at.replace("Z", ""))

        response += f"{i+1}. {created.strftime('%d.%m %H:%M')}\n"
        response += f"   {len(messages)} сообщений\n"

        if i == 0:
            response += "   ← текущая\n"

        response += "\n"

    await update.message.reply_text(response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = """Ɉ Montana Evolution

**Команды:**
/start - начало
/level - твой уровень Орангутанга
/cognitive - cognitive signatures агентов
/sessions - история сессий
/help - эта помощь

**Как работает:**
1. Каждый твой чат = изолированная сессия
2. Claude + GPT работают параллельно
3. Каждый агент оставляет cognitive signature
4. Всё записывается в append-only лог

**Система уровней:**
• Орангутанг 1-99: растёшь через сырые мысли
• Атлант 100+: хранитель 5 узлов Montana

**Cognitive Signature:**
Каждый агент имеет уникальный стиль мышления.
Claude = security + architecture
GPT = education + analysis

Просто пиши. Система сама всё записывает."""

    await update.message.reply_text(help_text, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════════════════════════
#                              ОСНОВНОЙ ОБРАБОТЧИК
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений с Montana Evolution"""
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    user_data = get_user(user_id)
    lang = user_data.get('lang', 'ru')

    # Получить активную сессию
    session = session_manager.get_active_session(user_id)

    # Логировать входящее сообщение
    await session.log_message("user", text)

    # ПАРАЛЛЕЛЬНЫЕ АГЕНТЫ
    if ENABLE_PARALLEL_AGENTS and orchestrator:
        try:
            # Показать "печатает..."
            await update.message.chat.send_action("typing")

            # Параллельный запрос
            response = await orchestrator.respond_parallel(
                prompt=text,
                context={
                    "prompt": text,
                    "lang": lang,
                    "user_id": user_id,
                    "first_name": user.first_name
                },
                mode=AGENT_MODE  # synthesize | claude | gpt | both_visible
            )

            # Логировать reasoning patterns
            if response.thinking:
                await session.log_reasoning(
                    agent=response.agent,
                    thinking=response.thinking,
                    metadata={"tokens": response.tokens_used}
                )

            # Сохранить cognitive signature
            if response.signature_features:
                await session.save_cognitive_signature(
                    agent=response.agent,
                    signature=response.signature_features
                )

            # Логировать ответ
            await session.log_message("assistant", response.content, agent=response.agent)

            # Отправить пользователю
            await update.message.reply_text(f"Ɉ\n\n{response.content}")

            logger.info(f"✓ {user.first_name}: {response.agent} ({response.tokens_used} tokens)")

        except Exception as e:
            logger.error(f"Montana Evolution error: {e}")
            await update.message.reply_text("Ɉ Временная ошибка. Попробуй ещё раз.")

    else:
        # Fallback: старый метод (если агенты недоступны)
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
    application.add_handler(CommandHandler("level", level_command))
    application.add_handler(CommandHandler("cognitive", cognitive_command))
    application.add_handler(CommandHandler("sessions", sessions_command))
    application.add_handler(CommandHandler("help", help_command))

    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🏔 Юнона Montana Evolution — запущена")
    if ENABLE_PARALLEL_AGENTS:
        logger.info(f"   Режим агентов: {AGENT_MODE}")
    else:
        logger.info("   Параллельные агенты: выключены")

    application.run_polling()
