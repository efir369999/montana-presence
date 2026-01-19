# junona_bot_simple.py
# Юнона — простой чат-бот Montana
# Живое общение, без глав и книги

import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.error import TelegramError, NetworkError, Conflict, TimedOut, RetryAfter

from junona_ai import junona

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA")
BOT_CREATOR_ID = 8552053404

BOT_DIR = Path(__file__).parent
USERS_FILE = BOT_DIR / "data" / "users.json"
STREAM_FILE = BOT_DIR / "data" / "stream.jsonl"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        'first_name': '',
        'username': '',
        'history': []
    })

def save_user(user_id: int, data: dict):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

# ═══════════════════════════════════════════════════════════════════════════════
#                              ПОТОК МЫСЛЕЙ
# ═══════════════════════════════════════════════════════════════════════════════

def save_to_stream(user_id: int, username: str, thought: str):
    """Сохранить мысль в поток"""
    entry = {
        "user_id": user_id,
        "username": username,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "thought": thought
    }

    with open(STREAM_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_user_stream(user_id: int, limit: int = 10) -> list[dict]:
    """Загрузить мысли пользователя из потока"""
    if not STREAM_FILE.exists():
        return []

    thoughts = []
    with open(STREAM_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    if entry.get("user_id") == user_id:
                        thoughts.append(entry)
                except json.JSONDecodeError:
                    continue

    return thoughts[-limit:]  # Последние N мыслей


def stream_to_markdown(thoughts: list[dict], username: str) -> str:
    """Конвертировать мысли в Markdown"""
    if not thoughts:
        return None

    lines = [
        f"# Поток мыслей @{username}",
        "",
        f"**Всего мыслей:** {len(thoughts)}",
        "",
        "---",
        ""
    ]

    current_date = None
    for t in thoughts:
        date = t.get("timestamp", "")[:10]
        time = t.get("timestamp", "")[11:16]
        thought = t.get("thought", "")

        if date != current_date:
            current_date = date
            lines.append(f"## {date}")
            lines.append("")

        lines.append(f"**[{time}]** {thought}")
        lines.append("")

    lines.extend([
        "---",
        "",
        f"*Экспорт: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "金元Ɉ Montana — Внешний гиппокамп"
    ])

    return "\n".join(lines)


async def stream_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stream — показать свои последние мысли"""
    user = update.effective_user
    user_id = user.id

    # Загружаем мысли пользователя
    thoughts = load_user_stream(user_id, limit=10)

    if not thoughts:
        await update.message.reply_text(
            "Ɉ Твой поток мыслей пуст.\n\n"
            "Напиши мне любую мысль — я сохраню её во внешний гиппокамп.\n"
            "Пример: «Время не движется, я движусь»"
        )
        return

    # Форматируем для Telegram
    lines = [f"Ɉ Твой поток мыслей ({len(thoughts)} последних):", ""]

    for t in thoughts:
        date = t.get("timestamp", "")[:10]
        time = t.get("timestamp", "")[11:16]
        thought = t.get("thought", "")
        lines.append(f"[{date} {time}]")
        lines.append(f"  {thought}")
        lines.append("")

    lines.append("Для экспорта в файл: /export")

    await update.message.reply_text("\n".join(lines))


async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /export — экспортировать мысли в MD файл"""
    user = update.effective_user
    user_id = user.id
    username = user.username or "аноним"

    # Загружаем ВСЕ мысли пользователя
    thoughts = load_user_stream(user_id, limit=10000)

    if not thoughts:
        await update.message.reply_text(
            "Ɉ Твой поток мыслей пуст.\n"
            "Напиши мне мысль — я сохраню её."
        )
        return

    # Конвертируем в Markdown
    markdown = stream_to_markdown(thoughts, username)

    # Отправляем как файл
    from io import BytesIO
    file_content = markdown.encode('utf-8')
    file_obj = BytesIO(file_content)
    file_obj.name = f"мысли_{username}_{datetime.now().strftime('%Y%m%d')}.md"

    await update.message.reply_document(
        document=file_obj,
        filename=file_obj.name,
        caption=f"Ɉ Твой поток мыслей ({len(thoughts)} записей)\n\n金元Ɉ Montana — Внешний гиппокамп"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#                              HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало — приветствие от Юноны"""
    user = update.message.from_user
    user_id = user.id

    # Сохраняем данные пользователя
    data = {
        'first_name': user.first_name,
        'username': user.username,
        'history': []
    }
    save_user(user_id, data)

    # Показываем "печатает..."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Юнона приветствует
    if junona:
        try:
            greeting = await junona.welcome_guest({
                'name': user.first_name,
                'lang': 'ru'
            })
            await update.message.reply_text(f"Ɉ\n\n{greeting}")
        except Exception as e:
            logger.error(f"Junona error: {e}")
            await update.message.reply_text(
                "Ɉ Привет. Я Юнона.\n\n"
                "Зачем ты тут? О чем хочешь поговорить?"
            )
    else:
        await update.message.reply_text(
            "Ɉ Привет. Я Юнона.\n\n"
            "Зачем ты тут? О чем хочешь поговорить?"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста — живое общение"""
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    user_data = get_user(user_id)
    history = user_data.get('history', [])

    # Сохраняем мысль в поток
    save_to_stream(user_id, user.username or "аноним", text)
    logger.info(f"💭 {user.first_name}: {text[:50]}...")

    # Показываем "печатает..." как в обычном чате
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Юнона отвечает
    if junona:
        try:
            response = await junona.respond(text, {
                'name': user.first_name,
                'lang': 'ru'
            }, history)

            # Сохраняем в историю
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": response})

            # Оставляем только последние 10 сообщений
            user_data['history'] = history[-10:]
            save_user(user_id, user_data)

            await update.message.reply_text(f"Ɉ\n\n{response}")
        except Exception as e:
            logger.error(f"Junona error: {e}")
            await update.message.reply_text("...")
    else:
        await update.message.reply_text("Ɉ")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    error = context.error
    if isinstance(error, Conflict):
        logger.error("Конфликт: несколько экземпляров бота")
    elif isinstance(error, NetworkError):
        logger.error(f"Сеть: {error}")
    elif isinstance(error, RetryAfter):
        logger.warning(f"Rate limit: {error.retry_after}s")
    else:
        logger.error(f"Ошибка: {error}", exc_info=error)

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN_JUNONA not set")
        exit(1)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stream", stream_cmd))
    application.add_handler(CommandHandler("export", export_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Ɉ Юнона — простое живое общение")
    application.run_polling()
