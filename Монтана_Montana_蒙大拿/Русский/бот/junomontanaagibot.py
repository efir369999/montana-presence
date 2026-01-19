# junomontanaagibot.py
# Юнона Montana — Официальный Telegram бот протокола Montana
# Wallet система, узлы, переводы, AI диалоги

import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonWebApp, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.error import TelegramError, NetworkError, Conflict, TimedOut, RetryAfter

from junona_ai import junona
from dialogue_coordinator import get_coordinator
from junona_rag import init_and_index
from hippocampus import ExternalHippocampus
from node_crypto import get_node_crypto_system
from time_bank import get_time_bank

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

# Система криптографических кошельков узлов
node_crypto_system = get_node_crypto_system()

# TIME_BANK - банк времени Montana
time_bank = get_time_bank()

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
#                              УЗЛЫ И КОШЕЛЬКИ
# ═══════════════════════════════════════════════════════════════════════════════

async def node_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /node [адрес|alias] — показать кошелек узла"""

    if not context.args:
        # Показать все узлы
        nodes = node_crypto_system.get_all_nodes()

        display = "Ɉ\n\n**MONTANA NETWORK**\n\n"
        display += f"🌐 **Всего узлов:** {len(nodes)}\n"

        official_count = sum(1 for n in nodes if n.get('official'))
        full_count = sum(1 for n in nodes if n.get('type') == 'full')

        display += f"⭐️ **Официальных:** {official_count}\n"
        display += f"🔷 **Full nodes:** {full_count}\n\n"

        # Показываем список узлов
        for node in sorted(nodes, key=lambda x: x.get('priority', 999)):
            flag = node.get('location', '').split()[0] if node.get('location') else '🌐'
            name = node.get('node_name', 'unknown')
            address = node.get('address', '')
            display += f"{flag} **{name}** — `{address[:16]}...`\n"

        display += f"\n📊 Используй `/node <адрес>` для деталей"

        await update.message.reply_text(display, parse_mode="Markdown")
        return

    # Получить конкретный узел
    identifier = context.args[0]

    # Попробовать найти по адресу
    node = node_crypto_system.get_node_by_address(identifier)

    # Если не найден, попробовать по alias
    if not node:
        node = node_crypto_system.get_node_by_alias(identifier)

    if not node:
        await update.message.reply_text(
            f"Ɉ\n\n❌ Узел не найден: `{identifier}`\n\n"
            f"Используй криптографический адрес (mt...) или alias",
            parse_mode="Markdown"
        )
        return

    # Получаем баланс из TIME_BANK
    balance = time_bank.balance(node['address'])

    # Формируем display
    flag = node.get('location', '').split()[0] if node.get('location') else '🌐'
    location_text = node.get('location', 'Неизвестно')

    display = f"Ɉ\n\n"
    display += f"**Узел Montana:** {flag} {node.get('node_name', 'unknown').title()}\n\n"
    display += f"**Адрес:** `{node['address']}`\n"
    display += f"**Alias:** `{node.get('alias', 'нет')}`\n"
    display += f"_(криптографический адрес — защита от IP hijacking)_\n\n"

    if node.get('ip'):
        display += f"**IP:** {node['ip']} _(только для networking)_\n"

    display += f"**Локация:** {location_text}\n"
    display += f"**Тип:** {node.get('type', 'unknown').upper()}\n"
    display += f"**Владелец:** TG ID {node.get('owner', 'неизвестен')}\n"
    display += f"**Приоритет:** #{node.get('priority', '?')}\n\n"

    display += f"💰 **Баланс:** {balance} секунд\n\n"
    display += f"⚠️ Переводы только по криптографическому адресу или alias."

    await update.message.reply_text(display, parse_mode="Markdown")


async def network_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /network — показать сводку по сети"""
    # Используем /node без аргументов
    await node_cmd(update, context)


async def register_node_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /register_node <name> <location> <ip> <owner_tg_id> [type]

    Только для администратора. Регистрирует новый узел с генерацией криптографических ключей.

    Пример:
    /register_node tokyo "🇯🇵 Tokyo" 1.2.3.4 123456789 light
    """
    user_id = update.effective_user.id

    # Только владелец может регистрировать узлы
    if user_id != BOT_CREATOR_ID:
        await update.message.reply_text("⛔️ Только администратор может регистрировать узлы")
        return

    if len(context.args) < 4:
        await update.message.reply_text(
            "Использование:\n"
            "/register_node <name> <location> <ip> <owner_tg_id> [type]\n\n"
            "Пример:\n"
            "/register_node tokyo \"🇯🇵 Tokyo\" 1.2.3.4 123456789 light\n\n"
            "Параметры:\n"
            "• name — короткое имя узла\n"
            "• location — локация с флагом\n"
            "• ip — IP адрес (только для networking)\n"
            "• owner_tg_id — Telegram ID владельца\n"
            "• type — full/light/client (опционально)"
        )
        return

    node_name = context.args[0]
    location = context.args[1]
    ip_address = context.args[2]

    try:
        owner_telegram_id = int(context.args[3])
    except ValueError:
        await update.message.reply_text("❌ Owner Telegram ID должен быть числом")
        return

    node_type = context.args[4] if len(context.args) > 4 else "light"

    # Регистрируем узел с генерацией криптографических ключей
    result = node_crypto_system.register_node(
        owner_telegram_id=owner_telegram_id,
        node_name=node_name,
        location=location,
        ip_address=ip_address,
        node_type=node_type
    )

    if not result.get('success'):
        await update.message.reply_text(f"❌ Ошибка регистрации узла")
        return

    # Формируем сообщение с КРИТИЧЕСКИ ВАЖНОЙ информацией
    display = f"Ɉ\n\n"
    display += f"✅ **Узел зарегистрирован**\n\n"
    display += f"**Адрес:** `{result['address']}`\n"
    display += f"**Alias:** `{result['alias']}`\n"
    display += f"**Public Key:** `{result['public_key'][:32]}...`\n\n"
    display += f"⚠️ **КРИТИЧЕСКИ ВАЖНО:**\n"
    display += f"**Private Key:** `{result['private_key']}`\n\n"
    display += f"🔐 **СОХРАНИ PRIVATE KEY В БЕЗОПАСНОМ МЕСТЕ!**\n"
    display += f"Без него доступ к кошельку узла невозможен.\n\n"
    display += f"Владелец: TG ID {owner_telegram_id}\n"
    display += f"IP: {ip_address} _(только для networking)_"

    await update.message.reply_text(display, parse_mode="Markdown")


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance — показать свой баланс"""
    user = update.effective_user
    user_id = user.id
    address = str(user_id)

    balance = time_bank.balance(address)
    presence_info = time_bank.get(address)

    display = f"Ɉ\n\n"
    display += f"**Твой кошелек Montana**\n\n"
    display += f"**Адрес:** `{user_id}`\n"
    display += f"_(твой Telegram ID — адрес кошелька и ключ)_\n\n"
    display += f"💰 **Баланс:** {balance} секунд\n\n"

    if presence_info and presence_info.get('is_active'):
        display += f"🟢 **Присутствие:** активно\n"
        display += f"⏱️ **Секунд в T2:** {presence_info['t2_seconds']}\n\n"

    display += f"📊 **/tx** — история транзакций\n"
    display += f"💸 **/transfer <адрес> <сумма>** — перевод\n\n"
    display += f"⚠️ При смене Telegram аккаунта — переноси монеты заранее."

    await update.message.reply_text(display, parse_mode="Markdown")


async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /transfer <адрес> <сумма> — перевод между кошельками

    Поддерживает переводы:
    - Пользователь → Пользователь (telegram_id)
    - Пользователь → Узел (криптографический адрес mt... или alias)
    - Узел → Узел (требуется подпись)
    - Любые комбинации адресов

    Анонимность: публично виден только proof, адреса хэшированы
    """
    user_id = update.effective_user.id
    from_addr = str(user_id)

    if len(context.args) < 2:
        await update.message.reply_text(
            "Ɉ\n\n"
            "**Использование:**\n"
            "`/transfer <адрес> <сумма>`\n\n"
            "**Примеры:**\n"
            "• `/transfer 123456789 100` — перевод пользователю (TG ID)\n"
            "• `/transfer mta46b633d... 50` — перевод узлу (адрес)\n"
            "• `/transfer amsterdam.montana.network 50` — перевод по alias\n\n"
            "**Адрес** = Telegram ID, криптографический адрес (mt...), или alias\n"
            "**Сумма** = секунды Montana времени",
            parse_mode="Markdown"
        )
        return

    to_identifier = context.args[0]
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Сумма должна быть больше 0")
        return

    # Resolve адрес: если это alias, преобразуем в криптографический адрес
    to_addr = to_identifier

    # Проверяем если это alias узла
    if '.' in to_identifier and 'montana.network' in to_identifier:
        node = node_crypto_system.get_node_by_alias(to_identifier)
        if node:
            to_addr = node['address']
        else:
            await update.message.reply_text(
                f"Ɉ\n\n❌ Узел не найден: `{to_identifier}`",
                parse_mode="Markdown"
            )
            return
    # Или если это криптографический адрес узла (начинается с mt)
    elif to_identifier.startswith('mt'):
        node = node_crypto_system.get_node_by_address(to_identifier)
        if not node:
            await update.message.reply_text(
                f"Ɉ\n\n❌ Узел не найден: `{to_identifier}`",
                parse_mode="Markdown"
            )
            return
        to_addr = node['address']
    # Иначе это Telegram ID пользователя

    # Проверяем баланс
    balance = time_bank.balance(from_addr)
    if balance < amount:
        await update.message.reply_text(
            f"Ɉ\n\n"
            f"❌ **Недостаточно средств**\n\n"
            f"Баланс: {balance} секунд\n"
            f"Требуется: {amount} секунд",
            parse_mode="Markdown"
        )
        return

    # Выполняем перевод
    result = time_bank.send(from_addr, to_addr, amount)

    if result.get('success'):
        proof = result['proof']
        new_balance = time_bank.balance(from_addr)

        # Скрываем длинные адреса
        to_addr_display = to_addr if len(to_addr) < 20 else f"{to_addr[:16]}..."

        await update.message.reply_text(
            f"Ɉ\n\n"
            f"✅ **Перевод выполнен**\n\n"
            f"💸 Отправлено: {amount} секунд\n"
            f"📍 Адресат: `{to_addr_display}`\n"
            f"🔐 Proof: `{proof[:16]}...`\n\n"
            f"💰 Новый баланс: {new_balance} секунд\n\n"
            f"_Транзакция анонимна. Публично виден только proof._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Ошибка перевода")


async def tx_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /tx — история транзакций"""
    user_id = update.effective_user.id
    address = str(user_id)

    # Получаем личную историю
    txs = time_bank.my_txs(address, limit=10)

    if not txs:
        await update.message.reply_text(
            "Ɉ\n\n"
            "💳 **История транзакций пуста**\n\n"
            "Переводы появятся здесь после первой транзакции."
        )
        return

    display = f"Ɉ\n\n**💳 Твои транзакции**\n\n"

    for tx in txs:
        direction_icon = "📤" if tx['direction'] == "out" else "📥"
        direction_text = "Отправлено" if tx['direction'] == "out" else "Получено"

        display += f"{direction_icon} **{direction_text}**\n"
        display += f"  🔐 `{tx['proof']}`\n"
        display += f"  📅 {tx['timestamp'][:19]}\n\n"

    display += f"_Адреса анонимны. Суммы скрыты._\n\n"
    display += f"🌐 **/feed** — публичная лента TX"

    await update.message.reply_text(display, parse_mode="Markdown")


async def feed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /feed — публичная лента транзакций"""

    txs = time_bank.tx_feed(limit=15)

    if not txs:
        await update.message.reply_text(
            "Ɉ\n\n"
            "📡 **Публичная лента пуста**\n\n"
            "Транзакции появятся здесь после первого перевода."
        )
        return

    display = f"Ɉ\n\n**📡 Публичная лента Montana**\n\n"

    for tx in txs:
        display += f"🔐 `{tx['proof']}`\n"
        display += f"  📅 {tx['timestamp'][:19]} • {tx['type']}\n\n"

    display += f"_Полная анонимность: адреса хэшированы, суммы скрыты._"

    await update.message.reply_text(display, parse_mode="Markdown")


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
                     f"Теперь ты можешь общаться со мной.\n\n"
                     f"Используй **/start** чтобы увидеть свой кошелек Montana.",
                parse_mode="Markdown"
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

    # Если пользователь ждет одобрения
    if user_data.get('pending_approval'):
        greeting = f"Ɉ\n\n" \
                  f"Привет, {user.first_name}.\n\n" \
                  f"Я — Юнона. Твой запрос отправлен на модерацию.\n\n" \
                  f"Скоро ты получишь доступ к общению."
        coordinator.add_message(user_id, "junona", greeting)
        await update.message.reply_text(greeting)
        return

    # Получаем баланс
    address = str(user_id)
    balance = time_bank.balance(address)
    presence_info = time_bank.get(address)

    # Приветствие с информацией о кошельке
    greeting = f"Ɉ\n\n"
    greeting += f"Привет, {user.first_name}.\n\n"
    greeting += f"Я — Юнона. Богиня виртуального пространства Montana.\n\n"
    greeting += f"**Твой кошелек Montana**\n\n"
    greeting += f"**Адрес:** `{user_id}`\n"
    greeting += f"_(твой Telegram ID — адрес кошелька и ключ)_\n\n"
    greeting += f"💰 **Баланс:** {balance} секунд\n\n"

    if presence_info and presence_info.get('is_active'):
        greeting += f"🟢 **Присутствие:** активно\n"
        greeting += f"⏱️ **Секунд в T2:** {presence_info['t2_seconds']}\n\n"

    greeting += f"**Команды:**\n"
    greeting += f"💰 **/balance** — баланс кошелька\n"
    greeting += f"💸 **/transfer** — перевод времени\n"
    greeting += f"📊 **/tx** — история транзакций\n"
    greeting += f"🌐 **/node** — узлы Montana\n"
    greeting += f"📡 **/feed** — публичная лента\n\n"
    greeting += f"О чем хочешь поговорить?"

    coordinator.add_message(user_id, "junona", greeting)
    await update.message.reply_text(greeting, parse_mode="Markdown")


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
#                              BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

async def setup_bot_commands(application):
    """Настройка кнопки меню с командами"""
    commands = [
        BotCommand("start", "🏠 Главная — баланс и команды"),
        BotCommand("balance", "💰 Баланс кошелька"),
        BotCommand("transfer", "💸 Перевод времени"),
        BotCommand("tx", "📊 История транзакций"),
        BotCommand("feed", "📡 Публичная лента"),
        BotCommand("node", "🌐 Узлы Montana"),
        BotCommand("stream", "💬 Лента диалога"),
    ]

    await application.bot.set_my_commands(commands)
    logger.info("✅ Кнопка меню настроена")

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

    # Настройка команд и меню
    application.post_init = setup_bot_commands

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stream", stream_cmd))
    application.add_handler(CommandHandler("export", export_cmd))
    application.add_handler(CommandHandler("node", node_cmd))
    application.add_handler(CommandHandler("network", network_cmd))
    application.add_handler(CommandHandler("register_node", register_node_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("transfer", transfer_cmd))
    application.add_handler(CommandHandler("tx", tx_cmd))
    application.add_handler(CommandHandler("feed", feed_cmd))
    application.add_handler(CallbackQueryHandler(handle_chapter_choice, pattern="^chapter_"))
    application.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject)_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Ɉ Юнона — Montana Protocol Bot")
    application.run_polling()
