# junona_bot_full.py
# Юнона Montana — Full Edition + Hippocampus
# Параллельные агенты + Статус сети + Внешний гиппокамп

import os
import json
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from io import BytesIO

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)

# Montana Evolution
from session_manager import get_session_manager
from junona_agents import get_orchestrator
from channel_parser import get_parser, list_knowledge_files
from language_detector import detect_language, get_text
from hippocampus import ExternalHippocampus

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA")
BOT_DIR = Path(__file__).parent

# Montana Evolution
ENABLE_PARALLEL_AGENTS = os.getenv("ENABLE_PARALLEL_AGENTS", "true").lower() == "true"
AGENT_MODE = os.getenv("AGENT_MODE", "synthesize")

# Channel Parser
CHANNEL_CHECK_INTERVAL = 300  # 5 минут

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

async def get_network_status(lang="en") -> str:
    mission_control_url = f"http://72.56.102.240:5000?lang={lang}"
    response = "🏔 Montana Network\n\n"
    response += "📡 Nodes:\n"
    online_count = 0
    for node_name, node_info in NODES.items():
        online = check_node_status(node_info["ip"])
        status_emoji = "●" if online else "○"
        response += f"{status_emoji} {node_info['location']}\n"
        response += f"   {node_info['ip']}\n"
        if online:
            online_count += 1
    health = int((online_count / len(NODES)) * 100)
    response += f"\n✓ Online: {online_count}/{len(NODES)} ({health}%)\n"
    response += f"\n🎛 Dashboard:\n   {mission_control_url}\n"
    response += f"\n📊 Slices:\n   τ₁: 1 min | τ₂: 10 min | τ₃: 14 days | τ₄: 4 years\n"
    response += f"\n💰 Montana (Ɉ):\n   1 second = 1 Ɉ | Emission: 31.5M/year\n"
    return response

# ═══════════════════════════════════════════════════════════════════════════════
#                              MONTANA AGENTS + ГИППОКАМП
# ═══════════════════════════════════════════════════════════════════════════════

session_manager = get_session_manager()
hippocampus = ExternalHippocampus(data_dir=str(BOT_DIR / "data"))

try:
    orchestrator = get_orchestrator()
    logger.info("🏔 Montana Evolution: агенты инициализированы")
except Exception as e:
    orchestrator = None
    logger.warning(f"⚠️ Параллельные агенты недоступны: {e}")
    ENABLE_PARALLEL_AGENTS = False

channel_parser = None
try:
    channel_parser = get_parser(use_telethon=True)
    logger.info("📖 Channel Parser: инициализирован")
except Exception as e:
    logger.warning(f"⚠️ Channel Parser недоступен: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОМАНДЫ
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
            InlineKeyboardButton("🇬🇧 English", callback_data='lang_en'),
            InlineKeyboardButton("🇨🇳 中文", callback_data='lang_zh')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        get_text('choose_language', 'ru'),
        reply_markup=reply_markup
    )

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split('_')[1]
    context.user_data['lang'] = lang
    user = query.from_user
    welcome = get_text('welcome', lang, name=user.first_name)
    await query.edit_message_text(
        text=get_text('language_set', lang) + '\n\n' + welcome
    )

async def network_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    lang = context.user_data.get("lang", "en")
    status = await get_network_status(lang)
    await update.message.reply_text(f"Ɉ\n\n{status}")

async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    files = list_knowledge_files()
    if not files:
        await update.message.reply_text("Ɉ\n\nБаза знаний Благаявести пока пуста.")
        return
    response = f"📖 Благаявесть (Книга 1)\n\n"
    for i, file in enumerate(files[-10:][::-1], 1):
        title = file['title'].replace('# ', '')
        response += f"{i}. {title}\n"
    response += f"\n✓ Всего частей: {len(files)}"
    await update.message.reply_text(f"Ɉ\n\n{response}")

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not channel_parser:
        await update.message.reply_text("Ɉ Channel Parser не инициализирован")
        return
    await update.message.reply_text("🔄 Проверяю @mylifesound369...")
    await update.message.chat.send_action("typing")
    try:
        new_posts = await channel_parser.check_new_posts()
        if new_posts:
            response = f"✓ Найдено: {len(new_posts)}\n\n"
            for post in new_posts:
                response += f"• Книга {post.get('book', 1)}, Глава {post.get('chapter', '?')}\n"
        else:
            response = "✓ Новых частей не найдено"
        await update.message.reply_text(f"Ɉ\n\n{response}")
    except Exception as e:
        logger.error(f"Sync error: {e}")
        await update.message.reply_text(f"Ɉ Ошибка: {e}")
    finally:
        if hasattr(channel_parser, 'close'):
            await channel_parser.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """Ɉ Montana Full Edition

/start - начало
/network - статус 5 узлов
/book - Благаявесть
/sync - проверить @mylifesound369

🧠 Гиппокамп:
/stream - последние мысли
/search <запрос> - поиск
/density - статистика
/export - скачать MD
/memory - справка

Просто пиши. Мысли сохраняются автоматически."""
    await update.message.reply_text(help_text)

# ═══════════════════════════════════════════════════════════════════════════════
#                              ГИППОКАМП (ВНЕШНЯЯ ПАМЯТЬ)
# ═══════════════════════════════════════════════════════════════════════════════

async def stream_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    thoughts = hippocampus.view_stream(limit=10, user_id=user_id)
    if not thoughts:
        await update.message.reply_text("Ɉ Поток пуст.\n\nНапиши мысль — она сохранится.")
        return
    response = f"🧠 Твой поток ({len(thoughts)}):\n\n"
    for t in thoughts:
        time = t.timestamp[:16].replace("T", " ")
        response += f"[{time}] {t.thought}\n\n"
    await update.message.reply_text(response)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Ɉ /search <запрос>")
        return
    query = " ".join(context.args)
    results = hippocampus.search(query, limit=10)
    if not results:
        await update.message.reply_text(f"Ɉ По \"{query}\" ничего не найдено.")
        return
    response = f"🔍 \"{query}\" ({len(results)}):\n\n"
    for t in results:
        response += f"[{t.timestamp[:10]}] {t.thought}\n\n"
    await update.message.reply_text(response)

async def density_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    stats = hippocampus.memory_stats(user_id=user_id)
    response = f"""🧠 Внешний Гиппокамп

Мыслей: {stats["total_thoughts"]}
Плотность: {stats["density"]} мыслей/день
Первая: {stats.get("first_thought", "—")[:10] if stats.get("first_thought") else "—"}
Последняя: {stats.get("last_thought", "—")[:10] if stats.get("last_thought") else "—"}

Биологический гиппокамп умирает. Montana — нет."""
    await update.message.reply_text(response)

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = """🧠 Внешний Гиппокамп Montana

Цифровая эмуляция биологического механизма памяти.
Переживает смерть носителя.

Как работает:
1. Детектор новизны — определяет сырые мысли
2. Pattern separation — каждая мысль = координата  
3. Консолидация — синхронизация каждые 12 сек

Команды:
/stream — последние мысли
/search — поиск по памяти
/density — статистика
/export — скачать MD файл

Просто напиши мысль — она сохранится автоматически.

> "Координата зафиксирована. Внешний гиппокамп помнит."

金元Ɉ Montana"""
    await update.message.reply_text(response)

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    markdown = hippocampus.export_markdown(user_id=user_id)
    if not markdown or "Всего мыслей:** 0" in markdown:
        await update.message.reply_text("Ɉ Поток пуст. Напиши первую мысль!")
        return
    file = BytesIO(markdown.encode("utf-8"))
    file.name = f"memory_{user_id}.md"
    await update.message.reply_document(
        document=file,
        filename=file.name,
        caption="🧠 Твой внешний гиппокамп Montana"
    )

# ═══════════════════════════════════════════════════════════════════════════════
#                              ОСНОВНОЙ ОБРАБОТЧИК
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    text = update.message.text
    username = user.username or user.first_name

    detected_lang = detect_language(text)
    if 'lang' not in context.user_data:
        context.user_data['lang'] = detected_lang
    lang = detected_lang

    # ГИППОКАМП: сохранить мысль если это сырая мысль
    if hippocampus.is_raw_thought(text):
        hippocampus.save_to_stream(user_id, username, text, lang)
        logger.info(f"🧠 Координата зафиксирована: {user.first_name}")

    session = session_manager.get_active_session(user_id)
    await session.log_message("user", text)

    if ENABLE_PARALLEL_AGENTS and orchestrator:
        try:
            await update.message.chat.send_action("typing")
            response = await orchestrator.respond_parallel(
                prompt=text,
                context={
                    "prompt": text,
                    "lang": lang,
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
        await update.message.reply_text("Ɉ Агенты недоступны. Проверь API ключи.")

# ═══════════════════════════════════════════════════════════════════════════════
#                              ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)

# ═══════════════════════════════════════════════════════════════════════════════
#                              POST INIT — MENU
# ═══════════════════════════════════════════════════════════════════════════════

async def post_init(application):
    """Установить команды меню бота"""
    commands = [
        BotCommand("start", "Начало"),
        BotCommand("help", "Помощь"),
        BotCommand("network", "Статус сети"),
        BotCommand("stream", "Мои мысли"),
        BotCommand("search", "Поиск по памяти"),
        BotCommand("density", "Статистика"),
        BotCommand("export", "Скачать память"),
        BotCommand("memory", "О гиппокампе"),
        BotCommand("book", "Благаявесть"),
        BotCommand("sync", "Синхронизация"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✓ Меню бота установлено")

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN_JUNONA not set")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    application.add_error_handler(error_handler)

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("network", network_command))
    application.add_handler(CommandHandler("book", book_command))
    application.add_handler(CommandHandler("sync", sync_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Гиппокамп
    application.add_handler(CommandHandler("stream", stream_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("density", density_command))
    application.add_handler(CommandHandler("memory", memory_command))
    application.add_handler(CommandHandler("export", export_command))

    # Callback для выбора языка
    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))

    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🏔 Юнона Montana + Гиппокамп — запущена")
    logger.info(f"   Агенты: {'✓' if ENABLE_PARALLEL_AGENTS else '✗'}")
    logger.info(f"   Гиппокамп: ✓")

    application.run_polling()
