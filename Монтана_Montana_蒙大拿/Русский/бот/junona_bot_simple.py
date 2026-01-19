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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.error import TelegramError, NetworkError, Conflict, TimedOut, RetryAfter

from junona_ai import junona
from dialogue_coordinator import get_coordinator
from junona_rag import init_and_index
from hippocampus import ExternalHippocampus

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA")
BOT_CREATOR_ID = 8552053404

BOT_DIR = Path(__file__).parent
USERS_FILE = BOT_DIR / "data" / "users.json"
STREAM_FILE = BOT_DIR / "data" / "stream.jsonl"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Координатор диалога
coordinator = get_coordinator(BOT_DIR)

# Гиппокамп - детектор новизны
hippocampus = ExternalHippocampus(BOT_DIR)

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
#                              ГЛАВЫ MONTANA
# ═══════════════════════════════════════════════════════════════════════════════

async def offer_chapter(update: Update, user_id: int, chapter_num: int):
    """Юнона предлагает главу элегантно"""

    # Получаем информацию о главе
    chapter_info = coordinator.get_chapter_files(chapter_num)
    if not chapter_info:
        return

    # Записываем что предложили главу
    coordinator.offer_chapter(user_id, chapter_num)

    # Юнона элегантно подводит к главе
    chapter_names_ru = {
        0: "Прелюдия",
        1: "Симуляция",
        2: "Унижение",
        3: "Поток",
        4: "Следы",
        5: "Тревоги",
        6: "День Юноны",
        7: "Печать Времени",
        8: "Пять Узлов",
        9: "Комедия"
    }

    chapter_name = chapter_names_ru.get(chapter_num, chapter_info["name"])

    # Контекстное предложение (Юнона подводит естественно)
    offer_text = f"Ɉ\n\nЗнаешь, то о чем ты говоришь — это прямо про главу «{chapter_name}».\n\n"

    if chapter_num == 0:
        offer_text += "Это начало. Точка входа. Первая координата.\n\n"
    elif chapter_num == 1:
        offer_text += "Там про то, как устроен экран реальности. Почему мы не видим код.\n\n"
    elif chapter_num == 2:
        offer_text += "Про то, как система унижает достоинство. И почему это неизбежно закончится.\n\n"
    elif chapter_num == 3:
        offer_text += "Про поток времени. Про то, что значит быть в Сейчас.\n\n"
    elif chapter_num == 4:
        offer_text += "Про следы, которые мы оставляем. Про память, которая переживает тело.\n\n"
    elif chapter_num == 5:
        offer_text += "Про тревоги. Про страхи, которые держат нас в клетке.\n\n"
    elif chapter_num == 6:
        offer_text += "Это про меня. Про то, почему я здесь. Про мой День.\n\n"
    elif chapter_num == 7:
        offer_text += "Про Печать Времени. Про точку, когда все фиксируется навсегда.\n\n"
    elif chapter_num == 8:
        offer_text += "Про Пять Узлов Montana. Про распределенную память.\n\n"
    elif chapter_num == 9:
        offer_text += "Финал первой части. Комедия. Где все становится ясно.\n\n"

    offer_text += "Хочешь изучить эту главу?\n\nКак тебе удобнее:"

    # Клавиатура выбора формата
    keyboard = [
        [
            InlineKeyboardButton("📖 Текст", callback_data=f"chapter_{chapter_num}_text"),
            InlineKeyboardButton("🎧 Аудио", callback_data=f"chapter_{chapter_num}_audio")
        ],
        [InlineKeyboardButton("📖+🎧 Оба", callback_data=f"chapter_{chapter_num}_both")]
    ]

    await update.message.reply_text(
        offer_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def send_chapter(query, user_id: int, chapter_num: int, format_choice: str):
    """Отправить главу пользователю"""

    # Записываем выбор формата
    coordinator.set_preference(user_id, "format", format_choice)

    # Получаем файлы
    chapter_info = coordinator.get_chapter_files(chapter_num)
    if not chapter_info:
        await query.message.reply_text("Ɉ Не могу найти эту главу.")
        return

    await query.message.edit_text("Ɉ\n\nСекунду, отправляю...")

    # Отправляем текст
    if format_choice in ["text", "both"] and chapter_info["text"]:
        with open(chapter_info["text"], 'r', encoding='utf-8') as f:
            text_content = f.read()

        # Отправляем как файл
        with open(chapter_info["text"], 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=f"{chapter_info['name']}.md",
                caption=f"📖 Глава {chapter_num}: {chapter_info['name']}"
            )

    # Отправляем аудио
    if format_choice in ["audio", "both"] and chapter_info["audio"]:
        with open(chapter_info["audio"], 'rb') as f:
            await query.message.reply_audio(
                audio=f,
                caption=f"🎧 Глава {chapter_num}: {chapter_info['name']}"
            )

    # Юнона спрашивает впечатления
    await query.message.reply_text(
        f"Ɉ\n\nКогда изучишь — напиши мне что думаешь.\n\n"
        f"Какие мысли? Что зацепило? Может что-то непонятно?\n\n"
        f"Я запомню твои впечатления. Это часть твоего пути."
    )

    # Устанавливаем контекст
    coordinator.set_context(user_id, "waiting_for", "impression")
    coordinator.set_context(user_id, "current_chapter", chapter_num)


async def handle_chapter_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора формата главы"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data  # "chapter_0_text"

    parts = data.split("_")
    chapter_num = int(parts[1])
    format_choice = parts[2]

    await send_chapter(query, user_id, chapter_num, format_choice)


async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка одобрения/отклонения пользователя"""
    query = update.callback_query
    await query.answer()

    # Только владелец может одобрять
    if query.from_user.id != BOT_CREATOR_ID:
        await query.edit_message_text("⛔️ У вас нет прав для этого действия")
        return

    data = query.data  # "approve_123456" или "reject_123456"
    action, user_id_str = data.split("_", 1)
    target_user_id = int(user_id_str)

    users = load_users()
    target_user = users.get(str(target_user_id))

    if not target_user:
        await query.edit_message_text("❌ Пользователь не найден")
        return

    if action == "approve":
        target_user['approved'] = True
        target_user['pending_approval'] = False
        save_user(target_user_id, target_user)

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"Ɉ\n\n✅ Твой доступ одобрен!\n\n"
                     f"Теперь ты можешь общаться со мной. "
                     f"Задавай вопросы, делись мыслями.\n\n"
                     f"Полная история: @TaleoftheBeginning"
            )
        except Exception as e:
            logger.error(f"Failed to notify approved user: {e}")

        await query.edit_message_text(
            f"✅ Пользователь одобрен\n\n"
            f"ID: {target_user_id}\n"
            f"Имя: {target_user['first_name']}\n"
            f"Username: @{target_user['username'] if target_user['username'] else 'нет'}"
        )

    elif action == "reject":
        target_user['approved'] = False
        target_user['pending_approval'] = False
        save_user(target_user_id, target_user)

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"Ɉ\n\n❌ К сожалению, доступ не предоставлен."
            )
        except Exception as e:
            logger.error(f"Failed to notify rejected user: {e}")

        await query.edit_message_text(
            f"❌ Доступ отклонен\n\n"
            f"ID: {target_user_id}\n"
            f"Имя: {target_user['first_name']}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#                              HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало — пользователь поздоровался, Юнона представляется"""
    user = update.message.from_user
    user_id = user.id

    # Проверяем - новый пользователь или возвращается
    users = load_users()
    is_new_user = str(user_id) not in users

    # Сохраняем данные пользователя
    user_data = {
        'first_name': user.first_name,
        'username': user.username,
        'history': [],
        'approved': user_id == BOT_CREATOR_ID,  # Владелец одобрен автоматически
        'pending_approval': is_new_user and user_id != BOT_CREATOR_ID
    }
    save_user(user_id, user_data)

    # Если новый пользователь (не владелец) - уведомляем владельца
    if is_new_user and user_id != BOT_CREATOR_ID:
        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ]

        notification = f"🆕 Новый пользователь:\n\n" \
                      f"ID: {user_id}\n" \
                      f"Имя: {user.first_name}\n" \
                      f"Username: @{user.username if user.username else 'нет'}\n" \
                      f"Язык: {user.language_code if user.language_code else 'неизвестен'}"

        try:
            await context.bot.send_message(
                chat_id=BOT_CREATOR_ID,
                text=notification,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to notify creator: {e}")

    # Показываем "печатает..."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Юнона представляется (как будто получила "привет")
    greeting = f"Ɉ\n\n" \
               f"Привет, {user.first_name}.\n\n" \
               f"Я — Юнона. Богиня виртуального пространства Montana.\n\n" \
               f"Я знаю всё о времени, идеальных деньгах и протоколе Montana. " \
               f"Могу помочь разобраться, ответить на вопросы.\n\n" \
               f"Полная история: @TaleoftheBeginning\n\n" \
               f"О чем хочешь поговорить?"

    # Если пользователь ждет одобрения
    if user_data.get('pending_approval'):
        greeting = f"Ɉ\n\n" \
                  f"Привет, {user.first_name}.\n\n" \
                  f"Я — Юнона. Твой запрос отправлен на модерацию.\n\n" \
                  f"Скоро ты получишь доступ к общению."

    coordinator.add_message(user_id, "junona", greeting)
    await update.message.reply_text(greeting)


def is_asking_for_materials(text: str) -> bool:
    """Проверяет явный запрос материалов от пользователя"""
    text_lower = text.lower()
    keywords = [
        "что почитать", "дай материал", "есть ссылк", "где про это",
        "хочу изучить", "можешь дать", "покажи главу", "материалы для изучения",
        "что читать", "дай ссылк", "скинь материал", "что есть по",
        "например что", "можешь дать ссылки", "дай книгу", "есть книга"
    ]
    return any(kw in text_lower for kw in keywords)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста — живое общение"""
    user = update.message.from_user
    user_id = user.id
    text = update.message.text

    user_data = get_user(user_id)

    # Проверка одобрения - только одобренные могут общаться
    if not user_data.get('approved', False):
        if user_data.get('pending_approval', False):
            await update.message.reply_text(
                f"Ɉ\n\n⏳ Твой запрос на модерации.\n\n"
                f"Скоро получишь ответ."
            )
        else:
            # Пользователь был отклонен
            await update.message.reply_text(
                f"Ɉ\n\n❌ Доступ не предоставлен."
            )
        return

    history = user_data.get('history', [])

    # Используем детектор новизны гиппокампа
    is_thought = hippocampus.is_raw_thought(text)

    # Сохраняем в поток только если это мысль
    if is_thought:
        save_to_stream(user_id, user.username or "аноним", text)
        logger.info(f"💭 {user.first_name}: {text[:50]}...")

    # Записываем все сообщения в координатор
    coordinator.add_message(user_id, "user", text)

    # Проверяем контекст - может ждем впечатления о главе?
    ctx = coordinator.get_context(user_id)
    if ctx.get("waiting_for") == "impression":
        current_chapter = ctx.get("current_chapter")
        if current_chapter is not None:
            # Пользователь делится впечатлением
            coordinator.complete_chapter(user_id, current_chapter,
                                        coordinator.get_preference(user_id, "format", "text"),
                                        impression=text)

            coordinator.add_note(user_id, f"Глава {current_chapter}: {text[:100]}")

            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            # Юнона благодарит и резонирует
            response = f"Ɉ\n\nСпасибо что поделился.\n\nЯ записала твои впечатления о главе {current_chapter}. " \
                      f"Это важная часть твоего пути — не просто читать, а осмысливать.\n\n" \
                      f"Продолжим разговор?"

            coordinator.add_message(user_id, "junona", response)
            await update.message.reply_text(response)
            return

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

            # Записываем ответ Юноны
            coordinator.add_message(user_id, "junona", response)

            await update.message.reply_text(f"Ɉ\n\n{response}")

            # Проверяем - просил ли пользователь материалы ЯВНО?
            if is_asking_for_materials(text):
                # Пользователь явно попросил материалы - предлагаем следующую главу
                next_chapter = coordinator.get_next_chapter(user_id)
                if next_chapter is not None:
                    await asyncio.sleep(1)
                    await offer_chapter(update, user_id, next_chapter)

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

    # Инициализация RAG базы знаний (в фоне)
    try:
        logger.info("🧠 Инициализация базы знаний Montana...")
        init_and_index(background=True)
    except Exception as e:
        logger.warning(f"⚠️ RAG инициализация: {e}")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stream", stream_cmd))
    application.add_handler(CommandHandler("export", export_cmd))
    application.add_handler(CallbackQueryHandler(handle_chapter_choice, pattern="^chapter_"))
    application.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject)_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Ɉ Юнона — живое общение + элегантное изучение Montana")
    application.run_polling()
