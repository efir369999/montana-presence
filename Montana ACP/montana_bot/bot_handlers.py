"""
Montana Bot Handlers — интеграция с j3_statbot
==============================================

╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ЗАКОН: ОДИН КЛЮЧ. ОДНА ПОДПИСЬ. ОДИН РАЗ.                     ║
║                                                                  ║
║   Это касается ВСЕХ без исключения.                              ║
║   Когнитивная цепочка уникальных подписей начинается с Genesis. ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

Принцип Парето 80/20:
- 80% Full Nodes — инфраструктура (серверы, автоматика)
- 20% Verified Users — люди ("Ты здесь?" в боте)

Добавь эти handlers в j3_statbot_120.py
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
import asyncio
import time
import random
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps

try:
    from .presence import (
        PresenceStorage, CognitiveKey, PresenceChallenge, PresenceRecord,
        SpatialAnchor, create_spatial_signature,
        create_challenge, verify_challenge_response, calculate_next_challenge_interval,
        format_genesis_message, format_challenge_message, format_stats_message,
        TAU2_SECS, VERIFICATION_WINDOW_SECS
    )
    from .node_map import get_node_map, NodeMap
except ImportError:
    from presence import (
        PresenceStorage, CognitiveKey, PresenceChallenge, PresenceRecord,
        SpatialAnchor, create_spatial_signature,
        create_challenge, verify_challenge_response, calculate_next_challenge_interval,
        format_genesis_message, format_challenge_message, format_stats_message,
        TAU2_SECS, VERIFICATION_WINDOW_SECS
    )
    from node_map import get_node_map, NodeMap


# ============================================================================
# STORAGE (инициализировать при старте бота)
# ============================================================================

MONTANA_DATA_DIR = Path("./montana_data")
storage = PresenceStorage(MONTANA_DATA_DIR)

# ID владельца бота (для авторизации новых пользователей)
OWNER_ID = 8552053404  # @junomoneta

# Genesis владельца
OWNER_MARKER = "#Благаявесть"
OWNER_LINKS = [
    "https://t.me/mylifethoughts369",
    "https://t.me/mylifeprogram369"
]

# Список авторизованных пользователей (загружается из файла)
AUTHORIZED_FILE = MONTANA_DATA_DIR / "authorized_users.json"


def load_authorized_users() -> set:
    """Загрузить список авторизованных пользователей."""
    if AUTHORIZED_FILE.exists():
        import json
        with open(AUTHORIZED_FILE, 'r') as f:
            return set(json.load(f))
    return {OWNER_ID}  # Владелец всегда авторизован


def save_authorized_users(users: set):
    """Сохранить список авторизованных пользователей."""
    import json
    MONTANA_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUTHORIZED_FILE, 'w') as f:
        json.dump(list(users), f)


authorized_users = load_authorized_users()


# ============================================================================
# AUTHORIZATION DECORATORS
# ============================================================================

def authorized_only(func):
    """
    Доступ только авторизованным пользователям Montana сети.
    Проверяет наличие user_id в authorized_users set.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Получить user_id из message или callback_query
        if update.message:
            user_id = update.message.from_user.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            return

        # Проверка авторизации
        if user_id not in authorized_users:
            if update.message:
                await update.message.reply_text(
                    "❌ **ТЫ НЕ ПОДКЛЮЧЕН К СЕТИ MONTANA**\n\n"
                    "Создай Genesis Identity через /montana\n\n"
                    "После создания владелец сети одобрит твоё подключение.",
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.answer(
                    "Доступ только для участников сети Montana.",
                    show_alert=True
                )
            return

        return await func(update, context)

    return wrapper


def owner_only(func):
    """
    Доступ только владельцу Full Node (OWNER_ID).
    Для команд управления сервером: /node, /bots.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            user_id = update.message.from_user.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            return

        if user_id != OWNER_ID:
            if update.message:
                await update.message.reply_text(
                    "❌ **ДОСТУП ЗАПРЕЩЁН**\n\n"
                    "Эта команда доступна только владельцу узла.",
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.answer(
                    "Только для владельца узла.",
                    show_alert=True
                )
            return

        return await func(update, context)

    return wrapper


# ============================================================================
# CONVERSATION STATES
# ============================================================================

WAITING_MARKER = 1
WAITING_COGNITIVE_PROMPT = 2
WAITING_FIRST_RESPONSE = 3


# ============================================================================
# NETWORK CONNECTION AUTHORIZATION (после создания Genesis)
# ============================================================================

async def request_network_connection(user_id: int, key: CognitiveKey, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправить запрос на подключение к сети владельцу.
    Вызывается после создания Genesis Identity.
    """
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подключить к сети", callback_data=f"net_approve_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"net_deny_{user_id}")
        ]
    ])

    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"Ɉ **ЗАПРОС ПОДКЛЮЧЕНИЯ К СЕТИ MONTANA**\n\n"
                 f"**Маркер:** `{key.marker}`\n"
                 f"**Genesis Hash:** `{key.genesis_hash[:32]}...`\n"
                 f"**Public Key:** `{key.public_key[:32]}...`\n"
                 f"**User ID:** `{user_id}`\n\n"
                 f"Подключить к сети Montana?",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return True
    except Exception as e:
        print(f"Error sending network request: {e}")
        return False


async def handle_network_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопок подключения к сети.
    """
    query = update.callback_query
    await query.answer()

    # Только владелец может одобрять подключения
    if query.from_user.id != OWNER_ID:
        await query.edit_message_text("❌ Только владелец может управлять подключениями к сети.")
        return

    data = query.data

    if data.startswith("net_approve_"):
        user_id = int(data.replace("net_approve_", ""))
        authorized_users.add(user_id)
        save_authorized_users(authorized_users)

        key = storage.get_key(user_id)
        marker = key.marker if key else "Unknown"

        await query.edit_message_text(
            f"Ɉ **ПОДКЛЮЧЕН К СЕТИ MONTANA**\n\n"
            f"**Маркер:** {marker}\n"
            f"**User ID:** {user_id}\n\n"
            f"Участник добавлен в сеть. Проверка «Ты здесь?» запланирована.",
            parse_mode='Markdown'
        )

        # Уведомить пользователя и запланировать challenge
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Ɉ **ПОДКЛЮЧЕН К СЕТИ MONTANA**\n\n"
                     f"Твой Genesis Identity `{marker}` добавлен в сеть!\n\n"
                     f"Теперь ты участник Ɉ Montana Verified Users (20%).\n\n"
                     f"**Следующий шаг:**\n"
                     f"Первая проверка «Ты здесь?» придёт через ~1 минуту.\n\n"
                     f"Успей нажать за 30 сек — накопишь время присутствия.",
                parse_mode='Markdown'
            )

            # Запланировать первый challenge (сразу, 30-60 сек)
            context.job_queue.run_once(
                schedule_challenge,
                when=random.randint(30, 60),
                data={'user_id': user_id, 'chat_id': user_id},
                name=f"challenge_{user_id}"
            )
        except Exception as e:
            print(f"Error notifying user {user_id}: {e}")

    elif data.startswith("net_deny_"):
        user_id = int(data.replace("net_deny_", ""))

        # Удалить Genesis если отклонено
        key = storage.get_key(user_id)
        marker = key.marker if key else "Unknown"

        await query.edit_message_text(
            f"❌ **ПОДКЛЮЧЕНИЕ ОТКЛОНЕНО**\n\n"
            f"**Маркер:** {marker}\n"
            f"**User ID:** {user_id}",
            parse_mode='Markdown'
        )

        # Уведомить пользователя
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ **ПОДКЛЮЧЕНИЕ К СЕТИ ОТКЛОНЕНО**\n\n"
                     f"Твой Genesis Identity `{marker}` не был добавлен в сеть.\n\n"
                     f"Обратись к владельцу для уточнения.",
                parse_mode='Markdown'
            )
        except Exception:
            pass


# ============================================================================
# GENESIS CREATION FLOW
# ============================================================================

async def montana_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /montana — начать регистрацию в Montana Verified Users.

    Добавь в main():
        application.add_handler(CommandHandler("montana", montana_start))
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Проверить есть ли уже ключ
    # ПРАВИЛО: Один ключ, одна подпись, один раз. Это касается всех.
    if storage.has_key(user.id):
        key = storage.get_key(user.id)
        stats = storage.get_user_stats(user.id)
        await update.message.reply_text(
            f"🔑 *ПРАВИЛО: Один ключ, одна подпись, один раз\\.*\n\n"
            f"У тебя уже есть Genesis Identity\\!\n\n"
            f"*Маркер:* {key.marker}\n"
            f"*Genesis Hash:* `{key.genesis_hash[:32]}\\.\\.\\.`\n"
            f"*Создан:* {datetime.fromtimestamp(key.genesis_timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"Это твой единственный genesis\\. Используй /montana\\_stats для статистики\\.",
            parse_mode='MarkdownV2'
        )
        return ConversationHandler.END

    # Начать создание
    await update.message.reply_text(
        "Ɉ *GENESIS IDENTITY — Montana Verified Users (20%)*\n\n"
        "*ЗАКОН: Один ключ\\. Одна подпись\\. Один раз\\.*\n"
        "Это касается всех без исключения\\.\n\n"
        "Ты создаёшь свой единственный Genesis\\.\n"
        "Это начало твоей когнитивной цепочки подписей\\.\n\n"
        "*Принцип Парето 80/20:*\n"
        "• 80% — Full Nodes \\(серверы\\)\n"
        "• 20% — Verified Users \\(люди\\)\n\n"
        "*Шаг 1/3:* Придумай свой когнитивный маркер\\.\n\n"
        "Это твоя уникальная подпись в сети\\.\n\n"
        "Маркер должен:\n"
        "• Начинаться с \\#\n"
        "• Быть уникальным\n\n"
        "Примеры: \\#Благаявесть, \\#МойПуть, \\#Странник\n\n"
        "Введи свой маркер:",
        parse_mode='MarkdownV2'
    )
    return WAITING_MARKER


async def receive_marker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить когнитивный маркер от пользователя."""
    marker = update.message.text.strip()

    # Валидация
    if not marker.startswith('#'):
        await update.message.reply_text(
            "❌ Маркер должен начинаться с #\n\nПопробуй снова:"
        )
        return WAITING_MARKER

    if ' ' in marker:
        await update.message.reply_text(
            "❌ Маркер не должен содержать пробелов\n\nПопробуй снова:"
        )
        return WAITING_MARKER

    if len(marker) < 3:
        await update.message.reply_text(
            "❌ Маркер слишком короткий (минимум 3 символа)\n\nПопробуй снова:"
        )
        return WAITING_MARKER

    # Проверить уникальность
    existing_keys = storage.get_all_keys()
    for key in existing_keys:
        if key.marker.lower() == marker.lower():
            await update.message.reply_text(
                f"❌ Маркер {marker} уже занят\n\nВыбери другой:"
            )
            return WAITING_MARKER

    # Сохранить маркер и перейти к когнитивному промпту
    context.user_data['montana_marker'] = marker

    await update.message.reply_text(
        f"✅ Маркер **{marker}** принят!\n\n"
        f"**Шаг 2/3:** Твой когнитивный промпт.\n\n"
        f"Это твоя философия, аффирмация или мантра.\n"
        f"Что-то важное для тебя.\n\n"
        f"**Пример:**\n"
        f"_Жизнь складывается для меня Идеально!_\n"
        f"_Все правильные вещи происходят в моей жизни._\n\n"
        f"Введи свой когнитивный промпт:",
        parse_mode='Markdown'
    )
    return WAITING_COGNITIVE_PROMPT


async def receive_cognitive_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить когнитивный промпт от пользователя."""
    cognitive_prompt = update.message.text.strip()

    # Минимальная валидация
    if len(cognitive_prompt) < 3:
        await update.message.reply_text(
            "❌ Когнитивный промпт слишком короткий.\n\n"
            "Напиши хотя бы одно предложение:"
        )
        return WAITING_COGNITIVE_PROMPT

    # Сохранить и перейти к последнему шагу
    context.user_data['montana_cognitive_prompt'] = cognitive_prompt

    await update.message.reply_text(
        f"✅ Когнитивный промпт сохранён!\n\n"
        f"**Шаг 3/3:** Ответь на вопрос:\n\n"
        f"**ТЫ ЗДЕСЬ?**\n\n"
        f"Напиши что угодно — это будет твой первый ответ,\n"
        f"часть твоего Genesis Block.",
        parse_mode='Markdown'
    )
    return WAITING_FIRST_RESPONSE


async def receive_first_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить первый ответ и создать Genesis."""
    user = update.effective_user
    first_response = update.message.text.strip()
    marker = context.user_data.get('montana_marker', '#Unknown')
    cognitive_prompt = context.user_data.get('montana_cognitive_prompt', '')

    try:
        # Создать когнитивный ключ
        # ПРАВИЛО: Один ключ, одна подпись, один раз. Это касается всех.
        key = storage.create_key(
            user_id=user.id,
            telegram_username=user.username,
            marker=marker,
            cognitive_prompt=cognitive_prompt,
            first_response=first_response
        )

        # Отправить genesis сообщение
        await update.message.reply_text(
            format_genesis_message(key),
            parse_mode='Markdown'
        )

        # Отправить запрос на подключение к сети владельцу
        if user.id == OWNER_ID:
            # Владелец автоматически подключается
            authorized_users.add(user.id)
            save_authorized_users(authorized_users)
            await update.message.reply_text(
                "✅ **АВТОМАТИЧЕСКИ ПОДКЛЮЧЕН К СЕТИ**\n\n"
                "Как владелец, ты автоматически добавлен в сеть Montana.\n\n"
                "Первая проверка «Ты здесь?» придёт через ~1 минуту.",
                parse_mode='Markdown'
            )
            # Запланировать первый challenge (сразу, 30-60 сек)
            context.job_queue.run_once(
                schedule_challenge,
                when=random.randint(30, 60),
                data={'user_id': user.id, 'chat_id': update.effective_chat.id},
                name=f"challenge_{user.id}"
            )
        else:
            # Отправить запрос владельцу
            sent = await request_network_connection(user.id, key, context)
            if sent:
                await update.message.reply_text(
                    "⏳ **ЗАПРОС НА ПОДКЛЮЧЕНИЕ ОТПРАВЛЕН**\n\n"
                    "Твой Genesis Identity создан и отправлен на проверку.\n\n"
                    "Ожидай подтверждения от владельца сети.\n"
                    "После подтверждения начнутся проверки «Ты здесь?»",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "⚠️ Genesis создан, но не удалось отправить запрос владельцу.\n"
                    "Обратись к @junomoneta напрямую."
                )

        return ConversationHandler.END

    except ValueError as e:
        # Ошибка создания ключа (скорее всего, ключ уже существует)
        # ПРАВИЛО: Один ключ, одна подпись, один раз.
        error_msg = str(e)
        if "уже имеет когнитивный ключ" in error_msg or "ПРАВИЛО" in error_msg:
            await update.message.reply_text(
                f"❌ **ПРАВИЛО: Один ключ, одна подпись, один раз.**\n\n"
                f"{error_msg}\n\n"
                f"Это касается всех без исключения.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END


async def cancel_genesis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить создание Genesis."""
    await update.message.reply_text("❌ Создание Genesis отменено.")
    return ConversationHandler.END


# ============================================================================
# CHALLENGE SYSTEM
# ============================================================================

async def schedule_challenge(context: ContextTypes.DEFAULT_TYPE):
    """Job callback — отправить challenge "Ты здесь?"."""
    job_data = context.job.data
    user_id = job_data['user_id']
    chat_id = job_data['chat_id']

    # Проверить что пользователь всё ещё зарегистрирован
    if not storage.has_key(user_id):
        return

    # Создать challenge
    tau2_index = int(time.time()) // TAU2_SECS
    challenge = create_challenge(user_id, tau2_index)
    storage.set_challenge(challenge)

    # Отправить сообщение с кнопкой
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я ЗДЕСЬ", callback_data=f"presence_{challenge.challenge_id}")]
    ])

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=format_challenge_message(),
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

        # Запланировать проверку через 30 секунд
        context.job_queue.run_once(
            check_challenge_expired,
            when=VERIFICATION_WINDOW_SECS + 1,
            data={'user_id': user_id, 'challenge_id': challenge.challenge_id, 'chat_id': chat_id},
            name=f"check_{challenge.challenge_id}"
        )

    except Exception as e:
        print(f"Error sending challenge to {user_id}: {e}")

    # Запланировать следующий challenge
    key = storage.get_key(user_id)
    if key:
        # Получить prev_slice_hash (заглушка — в реальности из сети)
        prev_slice_hash = "0" * 64
        next_interval = calculate_next_challenge_interval(
            prev_slice_hash,
            key.public_key,
            tau2_index
        )

        context.job_queue.run_once(
            schedule_challenge,
            when=next_interval,
            data={'user_id': user_id, 'chat_id': chat_id},
            name=f"challenge_{user_id}"
        )


async def check_challenge_expired(context: ContextTypes.DEFAULT_TYPE):
    """Проверить что challenge не был отвечен."""
    job_data = context.job.data
    user_id = job_data['user_id']
    challenge_id = job_data['challenge_id']
    chat_id = job_data['chat_id']

    challenge = storage.get_challenge(user_id)
    if challenge and challenge.challenge_id == challenge_id and not challenge.answered:
        # Challenge пропущен
        storage.clear_challenge(user_id)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Время вышло. Проверка пропущена.\n\n"
                     "Следующая придёт через 1-40 минут."
            )
        except Exception:
            pass


@authorized_only
async def handle_presence_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Я ЗДЕСЬ" — Шаг 1.

    После нажатия кнопки просит ввести маркер.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    challenge_id = query.data.replace("presence_", "")

    challenge = storage.get_challenge(user_id)
    if not challenge:
        await query.edit_message_text("❌ Проверка не найдена или истекла.")
        return

    if challenge.challenge_id != challenge_id:
        await query.edit_message_text("❌ Эта проверка уже неактуальна.")
        return

    # Проверить время
    response_time = int(time.time())
    success, message = verify_challenge_response(challenge, response_time)

    if not success:
        storage.clear_challenge(user_id)
        await query.edit_message_text(f"❌ {message}")
        return

    # Шаг 2: Запросить любой ответ для подписи
    context.user_data['pending_challenge'] = {
        'challenge_id': challenge_id,
        'challenge': challenge,
        'button_time': response_time
    }

    await query.edit_message_text(
        f"⏱ **ШАГ 2: НАПИШИ ЧТО УГОДНО**\n\n"
        f"Любой текст. Сеть подпишет его твоим ключом.\n\n"
        f"У тебя 20 секунд.",
        parse_mode='Markdown'
    )


@authorized_only
async def handle_marker_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ответа пользователя на challenge.

    Принимает:
    - Текст
    - Геолокацию
    - Файлы (документы, фото, видео, голосовые)
    - Любую комбинацию выше
    """
    user_id = update.effective_user.id
    pending = context.user_data.get('pending_challenge')

    if not pending:
        return

    now = int(time.time())
    button_time = pending['button_time']
    tau2_index = pending['tau2_index']
    challenge_id = pending['challenge_id']
    marker = storage.get_key(user_id).marker

    # Проверка: 20 секунд на ответ
    if now - button_time > 20:
        storage.clear_challenge(user_id)
        del context.user_data['pending_challenge']
        await update.message.reply_text(
            "❌ Время истекло (20 сек).\n\n"
            "Попробуй в следующий раз ответить быстрее.",
            parse_mode='Markdown'
        )
        return

    # === СОЗДАНИЕ SPATIAL ANCHOR ===

    anchor_type = "text"
    text = None
    latitude = None
    longitude = None
    file_id = None
    file_name = None
    file_hash = None
    file_size = None
    mime_type = None

    # Текст
    if update.message.text:
        text = update.message.text.strip()
        anchor_type = "text"

    # Геолокация
    if update.message.location:
        latitude = round(update.message.location.latitude, 3)
        longitude = round(update.message.location.longitude, 3)
        anchor_type = "location" if not text else "composite"

    # Файл
    if update.message.document:
        doc = update.message.document
        file_id = doc.file_id
        file_name = doc.file_name
        file_size = doc.file_size
        mime_type = doc.mime_type

        # Лимит 10MB
        if file_size > 10 * 1024 * 1024:
            await update.message.reply_text(
                f"❌ Файл слишком большой: {file_size / 1024 / 1024:.1f} MB\n\n"
                f"Максимум: 10 MB",
                parse_mode='Markdown'
            )
            storage.clear_challenge(user_id)
            del context.user_data['pending_challenge']
            return

        # Скачать файл для хеша
        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        file_hash = hashlib.sha3_256(file_bytes).hexdigest()

        anchor_type = "file" if not text and not latitude else "composite"

    # Фото
    if update.message.photo:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        file_size = photo.file_size
        mime_type = "image/jpeg"
        file_name = f"photo_{now}.jpg"

        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        file_hash = hashlib.sha3_256(file_bytes).hexdigest()

        anchor_type = "photo" if not text and not latitude else "composite"

    # Видео
    if update.message.video:
        video = update.message.video
        file_id = video.file_id
        file_size = video.file_size
        mime_type = video.mime_type
        file_name = f"video_{now}.mp4"

        if file_size > 10 * 1024 * 1024:
            await update.message.reply_text(
                f"❌ Файл слишком большой: {file_size / 1024 / 1024:.1f} MB\n\n"
                f"Максимум: 10 MB",
                parse_mode='Markdown'
            )
            storage.clear_challenge(user_id)
            del context.user_data['pending_challenge']
            return

        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        file_hash = hashlib.sha3_256(file_bytes).hexdigest()

        anchor_type = "video" if not text and not latitude else "composite"

    # Голосовое сообщение
    if update.message.voice:
        voice = update.message.voice
        file_id = voice.file_id
        file_size = voice.file_size
        mime_type = voice.mime_type
        file_name = f"voice_{now}.ogg"

        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        file_hash = hashlib.sha3_256(file_bytes).hexdigest()

        anchor_type = "voice" if not text and not latitude else "composite"

    # Проверка: хоть что-то должно быть
    if not text and not latitude and not file_id:
        await update.message.reply_text(
            "❌ Пустой ответ не принимается.\n\n"
            "Отправь текст, локацию, файл или фото.",
            parse_mode='Markdown'
        )
        storage.clear_challenge(user_id)
        del context.user_data['pending_challenge']
        return

    # Создать spatial anchor
    spatial_anchor = SpatialAnchor(
        anchor_type=anchor_type,
        timestamp=now,
        text=text,
        latitude=latitude,
        longitude=longitude,
        file_id=file_id,
        file_name=file_name,
        file_hash=file_hash,
        file_size=file_size,
        mime_type=mime_type,
    )

    # Создать пространственно-временную подпись
    anchor_signature = create_spatial_signature(marker, spatial_anchor)

    # Backward compatibility: старый response_hash (для текста)
    if text:
        response_prefix = text[:20]
        old_signature = hashlib.sha3_256(f"{marker}:{text}:{now}".encode()).hexdigest()[:16]
        response_hash = f"{old_signature}:{response_prefix}"
    else:
        response_hash = f"{anchor_signature[:16]}:[{anchor_type}]"

    # Сохранить presence record
    record = PresenceRecord(
        user_id=user_id,
        tau2_index=tau2_index,
        timestamp=now,
        challenge_id=challenge_id,
        response_hash=response_hash,
        spatial_anchor=spatial_anchor,
        anchor_signature=anchor_signature,
    )

    storage.add_presence(record)
    storage.clear_challenge(user_id)
    del context.user_data['pending_challenge']

    # Получить статистику
    stats = storage.get_user_stats(user_id)

    # Сформировать ответ
    response_text = (
        f"✅ **PRESENCE VERIFIED**\n\n"
        f"**Anchor Type:** {anchor_type}\n"
        f"**Timestamp:** {now}\n"
    )

    if text:
        text_display = text if len(text) <= 50 else text[:50] + "..."
        response_text += f"**Text:** {text_display}\n"

    if latitude:
        response_text += f"**Location:** {latitude:.3f}, {longitude:.3f}\n"

    if file_name:
        response_text += f"**File:** {file_name}\n"
        response_text += f"**File Hash:** `{file_hash[:16]}...`\n"
        response_text += f"**File Size:** {file_size} bytes\n"

    response_text += (
        f"\n**Signature:** `{anchor_signature[:32]}...`\n\n"
        f"**Total Records:** {stats.total_records}\n"
        f"**Weight:** {stats.weight}\n"
        f"**Next Challenge:** ~{stats.next_challenge_eta // 60} минут\n\n"
        f"Ɉ **Пространственный якорь зафиксирован.**"
    )

    await update.message.reply_text(response_text, parse_mode='Markdown')


# ============================================================================
# THOUGHTS STREAM — ПУБЛИЧНЫЙ ДОСТУП К МЫСЛЯМ ПО КОГНИТИВНОЙ ПОДПИСИ
# ============================================================================

async def get_thoughts_by_marker(marker: str) -> str:
    """
    Получить поток мыслей по когнитивному маркеру.

    Читает файл [маркер]_thoughts.md из Council/thoughts/
    Возвращает последние 2000 символов (ограничение Telegram).
    """
    # Убрать # если есть
    clean_marker = marker.lstrip('#').lower()

    # Путь к файлу мыслей
    thoughts_file = Path(__file__).parent.parent / "Council" / "thoughts" / f"{clean_marker}_thoughts.md"

    if not thoughts_file.exists():
        return None

    try:
        with open(thoughts_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Telegram лимит ~4096 символов, берём последние 3500 для безопасности
        if len(content) > 3500:
            content = "...\n\n" + content[-3500:]

        return content
    except Exception as e:
        return f"Ошибка чтения мыслей: {e}"


async def thoughts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /thoughts #маркер — прочитать поток мыслей по когнитивной подписи.

    Публичная команда. Доступна всем. Это публичный API мыслей Montana.
    """
    text = update.message.text

    # Извлечь маркер из команды
    # Формат: /thoughts #Благаявесть или просто #Благаявесть
    import re
    markers = re.findall(r'#\w+', text)

    if not markers:
        await update.message.reply_text(
            "Ɉ **MONTANA THOUGHTS STREAM**\n\n"
            "Используй: /thoughts #маркер\n\n"
            "Пример: /thoughts #Благаявесть\n\n"
            "Публичный API мыслей Montana.\n"
            "Каждая когнитивная подпись создаёт поток мыслей.\n\n"
            "lim(evidence → ∞) 1 Ɉ = 1 секунда",
            parse_mode='Markdown'
        )
        return

    marker = markers[0]
    thoughts = await get_thoughts_by_marker(marker)

    if thoughts is None:
        await update.message.reply_text(
            f"❌ Мысли для {marker} не найдены.\n\n"
            f"Когнитивная подпись не зарегистрирована в сети Montana.",
            parse_mode='Markdown'
        )
        return

    # Отправить мысли
    await update.message.reply_text(
        f"Ɉ **MONTANA THOUGHTS STREAM**\n\n"
        f"**Когнитивная подпись:** {marker}\n\n"
        f"────────────────────────\n\n",
        parse_mode='Markdown'
    )

    # Разбить на части если нужно (Telegram лимит 4096 символов)
    chunks = [thoughts[i:i+4000] for i in range(0, len(thoughts), 4000)]

    for chunk in chunks:
        await update.message.reply_text(chunk)


async def handle_hashtag_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик любого текста с хэштегом.

    Если сообщение содержит #маркер и ничего больше — отдать поток мыслей.
    """
    text = update.message.text.strip()

    # Проверить что это только хэштег
    import re
    if re.match(r'^#\w+$', text):
        marker = text
        thoughts = await get_thoughts_by_marker(marker)

        if thoughts:
            await update.message.reply_text(
                f"Ɉ **THOUGHTS STREAM: {marker}**\n\n",
                parse_mode='Markdown'
            )

            # Разбить на части
            chunks = [thoughts[i:i+4000] for i in range(0, len(thoughts), 4000)]

            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(
                f"Мысли для {marker} не найдены в сети Montana.",
                parse_mode='Markdown'
            )


# ============================================================================
# STATS & INFO COMMANDS
# ============================================================================

@authorized_only
async def montana_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /montana_stats — показать статистику присутствия.

    Добавь в main():
        application.add_handler(CommandHandler("montana_stats", montana_stats))
    """
    user = update.effective_user

    if not storage.has_key(user.id):
        await update.message.reply_text(
            "❌ У тебя нет Genesis Identity.\n\n"
            "Используй /montana для регистрации."
        )
        return

    key = storage.get_key(user.id)
    stats = storage.get_user_stats(user.id)

    await update.message.reply_text(
        format_stats_message(stats, key),
        parse_mode='Markdown'
    )



async def montana_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /montana_info — полная информация о протоколе Montana
    """
    keyboard = [
        [InlineKeyboardButton("📖 Протокол", callback_data="info_protocol")],
        [InlineKeyboardButton("⛏️ Консенсус ACP", callback_data="info_consensus")],
        [InlineKeyboardButton("🎰 Лотерея и эмиссия", callback_data="info_emission")],
        [InlineKeyboardButton("🔐 Криптография", callback_data="info_crypto")],
        [InlineKeyboardButton("💾 GitHub / Docs", callback_data="info_links")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"<b>Ɉ Montana</b> — Atemporal Coordinate Presence Protocol\n\n"
        f"<b>Определение:</b>\n"
        f"Montana — сеть, производящая юниты времени Ɉ через протокол АКП.\n\n"
        f"<b>Основной принцип:</b>\n"
        f"<code>lim(evidence → ∞) 1 Ɉ → 1 секунда</code>\n\n"
        f"<i>\"Время — единственный ресурс, распределённый одинаково между всеми людьми.\"</i>\n\n"
        f"Выбери раздел для изучения протокола:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )


@authorized_only
async def montana_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /montana_rate — информация о текущей эмиссии Ɉ
    """
    import time
    from datetime import datetime, timezone

    # Константы из Montana протокола
    GENESIS_TIMESTAMP = 1767916800  # 09.01.2026 00:00:00 UTC
    TAU2_SECS = 600                  # 10 минут
    REWARD_PER_TAU2 = 3000           # 3000 Ɉ каждые 10 минут
    HALVING_TAU2 = 210000            # Халвинг каждые 210,000 τ₂ (~4 года)

    now = int(time.time())
    elapsed_secs = max(1, now - GENESIS_TIMESTAMP)
    tau2_index = elapsed_secs // TAU2_SECS

    # Текущий халвинг период
    halving_epoch = tau2_index // HALVING_TAU2
    current_reward = REWARD_PER_TAU2 // (2 ** halving_epoch)

    # Следующий халвинг
    next_halving_tau2 = (halving_epoch + 1) * HALVING_TAU2
    tau2_until_halving = next_halving_tau2 - tau2_index
    days_until_halving = (tau2_until_halving * TAU2_SECS) / 86400

    await update.message.reply_text(
        f"<b>Ɉ Montana Эмиссия</b>\n\n"
        f"<b>Текущая награда:</b> {current_reward} Ɉ за 10 мин\n"
        f"<b>В день:</b> {current_reward * 144:,} Ɉ\n"
        f"<b>Халвинг #{halving_epoch + 1}:</b> через {days_until_halving:.0f} дней\n\n"
        f"<b>Лотерея:</b>\n"
        f"• 70% Full Nodes\n"
        f"• 20% Light Nodes (бот)\n"
        f"• 10% Light Clients\n\n"
        f"<b>lim(evidence → ∞) 1 Ɉ = 1 секунда</b>\n\n"
        f"/montana_stats — Твоя статистика",
        parse_mode='HTML'
    )


@authorized_only
async def montana_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /montana_map — показать карту Full Nodes.

    Добавь в main():
        application.add_handler(CommandHandler("montana_map", montana_map))
    """
    node_map = get_node_map()

    # Отправить текстовую статистику
    text_map = node_map.render_text()
    await update.message.reply_text(text_map)

    # Попробовать отправить изображение карты
    try:
        image_bytes = node_map.render_image()
        if image_bytes:
            from io import BytesIO
            await update.message.reply_photo(
                photo=BytesIO(image_bytes),
                caption="Карта Full Nodes Montana. Страны с узлами закрашены золотым."
            )
        else:
            # Если не удалось сгенерировать изображение, отправить ASCII
            ascii_map = node_map.render_ascii_map()
            await update.message.reply_text(f"```\n{ascii_map}\n```", parse_mode='Markdown')
    except Exception as e:
        # Fallback на ASCII карту
        ascii_map = node_map.render_ascii_map()
        await update.message.reply_text(f"```\n{ascii_map}\n```", parse_mode='Markdown')


# ============================================================================


# ============================================================================
# INFO CALLBACKS
# ============================================================================


async def handle_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок montana_info"""
    query = update.callback_query
    await query.answer()

    if query.data == "info_protocol":
        await query.message.edit_text(
            f"<b>📖 Протокол Montana</b>\n\n"
            f"<b>Определение:</b>\n"
            f"Ɉ (J с двумя чертами, U+0248) — Temporal Time Unit\n\n"
            f"<b>Как это работает:</b>\n"
            f"• Каждую τ₁ (1 мин) узлы подписывают координату времени\n"
            f"• За τ₃ (14 дней) = 20,160 подписей\n"
            f"• Подписи накапливаются → вес в лотерее\n\n"
            f"<b>Временные периоды:</b>\n"
            f"• τ₁ = 1 минута (подпись присутствия)\n"
            f"• τ₂ = 10 минут (слайс, лотерея)\n"
            f"• τ₃ = 14 дней (checkpoint)\n"
            f"• τ₄ = 4 года (халвинг)\n\n"
            f"<code>lim(evidence → ∞) 1 Ɉ = 1 секунда</code>\n\n"
            f"/montana_info — Назад",
            parse_mode='HTML'
        )

    elif query.data == "info_consensus":
        await query.message.edit_text(
            f"<b>⛏️ Консенсус ACP</b>\n\n"
            f"<b>Atemporal Coordinate Presence</b>\n\n"
            f"<b>Принцип:</b>\n"
            f"Консенсус достигается через доказательство присутствия,\n"
            f"а не через хеширование (PoW) или стейк (PoS).\n\n"
            f"<b>Лотерея присутствия:</b>\n"
            f"1. Каждые 10 минут (τ₂) узлы участвуют в лотерее\n"
            f"2. Вероятность выигрыша = вес подписей\n"
            f"3. Победитель подписывает слайс\n"
            f"4. Получает 3000 Ɉ + комиссии\n\n"
            f"<b>Детерминированность:</b>\n"
            f"seed = SHA3-256(prev_slice_hash ‖ τ₂_index)\n"
            f"Все узлы вычисляют одного победителя.\n\n"
            f"<b>Защита:</b>\n"
            f"• Grinding невозможен (seed фиксирован)\n"
            f"• Sybil дорог (кулдаун до 180 дней)\n"
            f"• Eclipse требует контроля сети\n\n"
            f"/montana_info — Назад",
            parse_mode='HTML'
        )

    elif query.data == "info_emission":
        await query.message.edit_text(
            f"<b>🎰 Лотерея и эмиссия</b>\n\n"
            f"<b>Текущая эмиссия:</b>\n"
            f"• Каждые τ₂ (10 мин): 3000 Ɉ\n"
            f"• В час: 18,000 Ɉ\n"
            f"• В день: 432,000 Ɉ\n"
            f"• В год: 157,680,000 Ɉ\n\n"
            f"<b>Распределение лотереи:</b>\n"
            f"• 70% → Full Nodes (серверы)\n"
            f"• 20% → Light Nodes (ты через бота)\n"
            f"• 10% → Light Clients (мобильные)\n\n"
            f"<b>Халвинг:</b>\n"
            f"Каждые 210,000 τ₂ (~4 года) награда уменьшается вдвое.\n\n"
            f"<b>Общий запас:</b>\n"
            f"1,260,000,000 Ɉ\n\n"
            f"<b>Пре-аллокация:</b> 0\n"
            f"<b>Фаундеры:</b> 0\n"
            f"<b>Резерв:</b> 0\n\n"
            f"Всё через лотерею присутствия.\n\n"
            f"/montana_info — Назад",
            parse_mode='HTML'
        )

    elif query.data == "info_crypto":
        await query.message.edit_text(
            f"<b>🔐 Криптография Montana</b>\n\n"
            f"<b>Post-Quantum (NIST FIPS):</b>\n\n"
            f"<b>Подписи:</b>\n"
            f"• ML-DSA-65 (Dilithium3, FIPS 204)\n"
            f"• Для всех подписей: присутствия, транзакции, слайсы\n\n"
            f"<b>Обмен ключами:</b>\n"
            f"• ML-KEM-768 (Kyber, FIPS 203)\n"
            f"• P2P шифрование\n\n"
            f"<b>Хеши:</b>\n"
            f"• SHA3-256 (FIPS 202)\n"
            f"• Для Merkle roots, commitments\n\n"
            f"<b>VDF (Verifiable Delay Function):</b>\n"
            f"• Доказательство прохождения времени\n"
            f"• Защита от time-travel атак\n\n"
            f"<b>Domain Separation:</b>\n"
            f"Каждая подпись содержит контекст:\n"
            f"• \"MONTANA_PRESENCE_V1\"\n"
            f"• \"MONTANA_TX_V1\"\n"
            f"• \"MONTANA_SLICE_V1\"\n\n"
            f"Защита от key reuse между контекстами.\n\n"
            f"/montana_info — Назад",
            parse_mode='HTML'
        )

    elif query.data == "info_links":
        await query.message.edit_text(
            f"<b>💾 GitHub / Документация</b>\n\n"
            f"<b>Репозиторий:</b>\n"
            f"Coming soon (после Genesis)\n\n"
            f"<b>Документация:</b>\n"
            f"• MONTANA.md — основной протокол\n"
            f"• layer_minus_1.md — физические инварианты\n"
            f"• layer_0.md — вычислительная основа\n"
            f"• layer_1.md — протокольные примитивы\n"
            f"• layer_2.md — консенсус\n\n"
            f"<b>Full Node (Rust):</b>\n"
            f"• Cargo.toml — зависимости\n"
            f"• src/consensus.rs — ACP консенсус\n"
            f"• src/net/ — P2P сеть\n"
            f"• src/crypto.rs — ML-DSA/ML-KEM\n\n"
            f"<b>Verified Users Bot (Python):</b>\n"
            f"• montana_bot/presence.py — логика\n"
            f"• montana_bot/bot_handlers.py — Telegram\n\n"
            f"<b>Whitepaper:</b>\n"
            f"Coming soon\n\n"
            f"<b>Контакт:</b>\n"
            f"@junomoneta\n\n"
            f"/montana_info — Назад",
            parse_mode='HTML'
        )


# START COMMAND
# ============================================================================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — полное API Montana через Telegram
    Показывает разное меню в зависимости от статуса авторизации.
    """
    user = update.effective_user
    user_id = user.id

    is_authorized = user_id in authorized_users
    is_owner = user_id == OWNER_ID

    if is_owner:
        # Полное меню для владельца (с управлением сервером)
        menu = (
            f"Привет, {user.first_name}! Я <b>Montana Full Node API</b>\n\n"
            f"<b>1 Ɉ → 1 секунда</b> (асимптотически)\n\n"
            f"<b>👤 Verified Users (20%):</b>\n"
            f"/montana — Создать Genesis Identity\n"
            f"/montana_stats — Моя статистика\n"
            f"/montana_rate — Эмиссия Ɉ\n\n"
            f"<b>⚙️ Full Node Control (owner):</b>\n"
            f"/node — Управление узлом\n"
            f"/bots — Управление ботами\n\n"
            f"<b>📖 Протокол:</b>\n"
            f"/montana_info — Полная спецификация\n"
            f"/montana_map — Карта узлов"
        )
    elif is_authorized:
        # Меню для авторизованных участников сети
        menu = (
            f"Привет, {user.first_name}! Я <b>Montana Full Node API</b>\n\n"
            f"<b>1 Ɉ → 1 секунда</b> (асимптотически)\n\n"
            f"<b>👤 Verified Users (20%):</b>\n"
            f"/montana — Создать Genesis Identity\n"
            f"/montana_stats — Моя статистика\n"
            f"/montana_rate — Эмиссия Ɉ\n\n"
            f"<b>📖 Протокол:</b>\n"
            f"/montana_info — Полная спецификация\n"
            f"/montana_map — Карта узлов"
        )
    else:
        # Ограниченное меню для неавторизованных
        menu = (
            f"Привет, {user.first_name}!\n\n"
            f"Я <b>Montana Full Node API</b> — подключение к сети Montana.\n\n"
            f"<b>1 Ɉ → 1 секунда</b> (асимптотически)\n\n"
            f"<b>Создай Genesis Identity:</b>\n"
            f"/montana — Запустить процесс создания\n\n"
            f"<b>Протокол Montana:</b>\n"
            f"/montana_info — Полная спецификация\n\n"
            f"<i>После создания Genesis владелец сети одобрит твоё подключение.</i>"
        )

    await update.message.reply_text(menu, parse_mode='HTML')


def register_montana_handlers(application):
    """
    Зарегистрировать все Montana handlers.

    Добавь в main() после создания application:
        from montana_bot.bot_handlers import register_montana_handlers
        register_montana_handlers(application)
    """
    # Start command
    application.add_handler(CommandHandler("start", start_command))

    # Genesis conversation
    genesis_handler = ConversationHandler(
        entry_points=[CommandHandler("montana", montana_start)],
        states={
            WAITING_MARKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_marker)],
            WAITING_COGNITIVE_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cognitive_prompt)],
            WAITING_FIRST_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_first_response)],
        },
        fallbacks=[CommandHandler("cancel", cancel_genesis)],
    )
    application.add_handler(genesis_handler)

    # Commands
    application.add_handler(CommandHandler("montana_stats", montana_stats))
    application.add_handler(CommandHandler("montana_info", montana_info))
    application.add_handler(CommandHandler("montana_rate", montana_rate))
    application.add_handler(CommandHandler("montana_map", montana_map))
    application.add_handler(CommandHandler("thoughts", thoughts_command))

    # Node & Bots control
    application.add_handler(CommandHandler("node", node_menu))
    application.add_handler(CommandHandler("bots", bots_menu))

    # Callbacks
    application.add_handler(CallbackQueryHandler(handle_presence_button, pattern="^presence_"))
    application.add_handler(CallbackQueryHandler(handle_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(handle_node_callback, pattern="^node_"))
    application.add_handler(CallbackQueryHandler(handle_bot_callback, pattern="^bot_"))
    application.add_handler(CallbackQueryHandler(handle_network_callback, pattern="^net_"))

    # Обработчик хэштегов (публичный API мыслей)
    # group=0 (выше чем marker_response) чтобы хэштеги обрабатывались первыми
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^#\w+$'),
        handle_hashtag_query
    ), group=0)

    # Ответ на проверку (текст + файлы + локация + медиа)
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.LOCATION | filters.Document.ALL |
         filters.PHOTO | filters.VIDEO | filters.VOICE) & ~filters.COMMAND,
        handle_marker_response
    ), group=1)  # group=1 чтобы не конфликтовал с ConversationHandler

    print("✅ Montana handlers registered")


# ============================================================================
# INTEGRATION CODE FOR j3_statbot_120.py
# ============================================================================

"""
ИНТЕГРАЦИЯ С j3_statbot_120.py
==============================

1. Скопируй montana_bot/ в ту же папку где j3_statbot_120.py

2. В j3_statbot_120.py добавь импорт после других импортов:

    from montana_bot.bot_handlers import register_montana_handlers

3. В функции main() после создания application добавь:

    # Montana Verified Users (20%)
    register_montana_handlers(application)

4. Готово! Команды доступны:
    /montana       — создать Genesis Identity
    /montana_stats — статистика присутствия
    /montana_info  — информация о системе

ПРИМЕР main():

async def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN_STAT_BOT).build()

    # ... твои существующие handlers ...

    # Montana integration
    from montana_bot.bot_handlers import register_montana_handlers
    register_montana_handlers(application)

    # Run
    await application.run_polling()
"""


# ============================================================================
# NODE & BOTS CONTROL
# ============================================================================

try:
    from .node_control import (
        is_node_running, start_node, stop_node, get_node_status, get_node_logs,
        list_bots, is_bot_running, start_bot, stop_bot
    )
except ImportError:
    from node_control import (
        is_node_running, start_node, stop_node, get_node_status, get_node_logs,
        list_bots, is_bot_running, start_bot, stop_bot
    )


@owner_only
async def node_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /node — меню управления Full Node
    """
    status = get_node_status()
    running = status['running']

    keyboard = [
        [InlineKeyboardButton("▶️ Запустить Node", callback_data="node_start")] if not running else [],
        [InlineKeyboardButton("⏸ Остановить Node", callback_data="node_stop")] if running else [],
        [InlineKeyboardButton("📊 Статус", callback_data="node_status")],
        [InlineKeyboardButton("📜 Логи", callback_data="node_logs")],
        [InlineKeyboardButton("🌐 Пиры", callback_data="node_peers")],
    ]
    keyboard = [row for row in keyboard if row]  # Убрать пустые строки
    reply_markup = InlineKeyboardMarkup(keyboard)

    status_text = "🟢 Запущен" if running else "🔴 Остановлен"

    await update.message.reply_text(
        f"<b>Ɉ Montana Full Node</b>\n\n"
        f"<b>Статус:</b> {status_text}\n"
        f"<b>PID:</b> {status['pid'] if running else '—'}\n"
        f"<b>Uptime:</b> {int(status.get('uptime', 0))} сек\n"
        f"<b>CPU:</b> {status.get('cpu', 0):.1f}%\n"
        f"<b>RAM:</b> {status.get('memory', 0)} MB\n\n"
        f"Выбери действие:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )


@owner_only
async def bots_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /bots — меню управления ботами
    """
    bots = list_bots()

    text = "<b>Ɉ Montana Bots Control</b>\n\n"

    for bot in bots:
        status_icon = "🟢" if bot['running'] else "🔴"
        text += f"{status_icon} <b>{bot['name']}</b>\n"
        text += f"  PID: {bot['pid'] if bot['pid'] else '—'}\n\n"

    keyboard = []
    for bot in bots:
        if bot['running']:
            keyboard.append([InlineKeyboardButton(f"⏸ Stop {bot['name']}", callback_data=f"bot_stop_{bot['name']}")])
        else:
            keyboard.append([InlineKeyboardButton(f"▶️ Start {bot['name']}", callback_data=f"bot_start_{bot['name']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


@owner_only
async def handle_node_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок управления Node"""
    query = update.callback_query
    await query.answer()

    if query.data == "node_start":
        success, msg = start_node()
        await query.message.edit_text(
            f"<b>Запуск Full Node...</b>\n\n{msg}",
            parse_mode='HTML'
        )

    elif query.data == "node_stop":
        success, msg = stop_node()
        await query.message.edit_text(
            f"<b>Остановка Full Node...</b>\n\n{msg}",
            parse_mode='HTML'
        )

    elif query.data == "node_status":
        status = get_node_status()
        running = status['running']
        status_text = "🟢 Запущен" if running else "🔴 Остановлен"

        await query.message.edit_text(
            f"<b>📊 Montana Full Node Status</b>\n\n"
            f"<b>Статус:</b> {status_text}\n"
            f"<b>PID:</b> {status['pid'] if running else '—'}\n"
            f"<b>Uptime:</b> {int(status.get('uptime', 0))} сек\n"
            f"<b>CPU:</b> {status.get('cpu', 0):.1f}%\n"
            f"<b>RAM:</b> {status.get('memory', 0)} MB\n\n"
            f"/node — Назад",
            parse_mode='HTML'
        )

    elif query.data == "node_logs":
        logs = get_node_logs(lines=30)
        await query.message.edit_text(
            f"<b>📜 Montana Node Logs (последние 30 строк)</b>\n\n"
            f"<pre>{logs[-3000:]}</pre>\n\n"  # Telegram limit 4096
            f"/node — Назад",
            parse_mode='HTML'
        )

    elif query.data == "node_peers":
        # TODO: Реализовать через RPC
        await query.message.edit_text(
            f"<b>🌐 Peers</b>\n\n"
            f"Coming soon (требуется RPC API узла)\n\n"
            f"/node — Назад",
            parse_mode='HTML'
        )


@owner_only
async def handle_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок управления ботами"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("bot_start_"):
        bot_name = query.data.replace("bot_start_", "")
        success, msg = start_bot(bot_name)
        await query.message.edit_text(
            f"<b>Запуск {bot_name}...</b>\n\n{msg}\n\n/bots — Назад",
            parse_mode='HTML'
        )

    elif query.data.startswith("bot_stop_"):
        bot_name = query.data.replace("bot_stop_", "")
        success, msg = stop_bot(bot_name)
        await query.message.edit_text(
            f"<b>Остановка {bot_name}...</b>\n\n{msg}\n\n/bots — Назад",
            parse_mode='HTML'
        )

