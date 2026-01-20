# junomontanaagibot.py
# Юнона Montana — Официальный Telegram бот протокола Montana
# Wallet система, узлы, переводы, AI диалоги
#
# ═══════════════════════════════════════════════════════════════════════════════
# ОБНОВЛЕНИЕ КОМАНД МЕНЮ БОТА
# ═══════════════════════════════════════════════════════════════════════════════
# 1. Все команды меню хранятся в константе BOT_COMMANDS (строка ~41)
# 2. При изменении команд в BOT_COMMANDS:
#    - Просто напиши /start боту от владельца (BOT_CREATOR_ID)
#    - Команды автоматически обновятся для всех пользователей
# 3. Владелец бота: /start всегда принудительно обновляет ВСЕ команды
# 4. Остальные: /start обновляет команды только для их чата
# 5. При запуске бота - всегда принудительное обновление всех команд
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
import logging
import asyncio
import threading
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

from leader_election import get_leader_election
from junona_ai import junona
# from junona_rag import init_and_index  # Отключено - экономия памяти
from node_crypto import get_node_crypto_system

# АТЛАНТ — Гиппокамп Montana (единая система памяти)
from hippocampus import get_atlant
from agent_crypto import get_agent_crypto_system
from time_bank import get_time_bank

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA")
BOT_CREATOR_ID = 8552053404
BOT_CREATOR_USERNAME = "@junomoneta"  # Ник владельца для уведомлений

# ═══════════════════════════════════════════════════════════════════════════════
# КОМАНДЫ МЕНЮ БОТА
# ВАЖНО: При изменении команд напиши /start боту для обновления меню
# ═══════════════════════════════════════════════════════════════════════════════
BOT_COMMANDS = [
    BotCommand("start", "🏔 Поговорить с Юноной"),
    BotCommand("balance", "💰 Баланс кошелька"),
    BotCommand("transfer", "💸 Перевод времени"),
    BotCommand("tx", "📜 История транзакций"),
    BotCommand("feed", "📡 Публичная лента"),
    BotCommand("node", "🌐 Узлы Montana"),
    BotCommand("stream", "💬 Поток мыслей"),
]

# Расширенное меню для владельца (BOT_CREATOR_ID)
BOT_COMMANDS_OWNER = BOT_COMMANDS + [
    BotCommand("stat", "👑 Статистика"),
    BotCommand("register_node", "➕ Регистрация узла"),
]

BOT_DIR = Path(__file__).parent
USERS_FILE = BOT_DIR / "data" / "users.json"
STREAM_FILE = BOT_DIR / "data" / "stream.jsonl"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

# АТЛАНТ — Гиппокамп Montana (единая система памяти)
# Держит память: диалоги, мысли, контекст
atlant = get_atlant()

# Система криптографических кошельков узлов
node_crypto_system = get_node_crypto_system()

# Система криптографии агентов Montana (ML-DSA-65)
agent_crypto_system = get_agent_crypto_system()

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


async def check_user_approved(update: Update, user_id: int) -> bool:
    """
    Проверка авторизации пользователя.

    Возвращает True если пользователь одобрен.
    Если не одобрен — отправляет сообщение и возвращает False.

    SECURITY: Все команды ДОЛЖНЫ вызывать эту функцию в начале.
    """
    # Владелец бота всегда одобрен
    if user_id == BOT_CREATOR_ID:
        return True

    user_data = get_user(user_id)

    if user_data.get('approved', False):
        return True

    # Не одобрен — отправляем отказ
    if user_data.get('pending_approval', False):
        await update.message.reply_text(
            "Ɉ\n\n⏳ Твой запрос на модерации.\n\nСкоро получишь ответ."
        )
    else:
        await update.message.reply_text(
            "Ɉ\n\n❌ Доступ не предоставлен."
        )

    return False


# ═══════════════════════════════════════════════════════════════════════════════
#                              ПОТОК МЫСЛЕЙ (АТЛАНТ)
# ═══════════════════════════════════════════════════════════════════════════════
# Все функции памяти перенесены в hippocampus/atlant.py
# Атлант — Гиппокамп Montana. Держит память сети.

async def stream_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stream — показать свои последние мысли (Атлант)"""
    user = update.effective_user
    user_id = user.id

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

    # Загружаем мысли через Атланта
    thoughts = atlant.get_thoughts(user_id, limit=10)

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
        date = t.timestamp[:10] if t.timestamp else ""
        time = t.timestamp[11:16] if t.timestamp else ""
        lines.append(f"[{date} {time}]")
        lines.append(f"  {t.content}")
        lines.append("")

    lines.append("Для экспорта в файл: /export")

    await update.message.reply_text("\n".join(lines))


async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /export — экспортировать мысли в MD файл (Атлант)"""
    user = update.effective_user
    user_id = user.id
    username = user.username or "аноним"

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

    # Проверяем есть ли мысли
    thoughts = atlant.get_thoughts(user_id, limit=10)

    if not thoughts:
        await update.message.reply_text(
            "Ɉ Твой поток мыслей пуст.\n"
            "Напиши мне мысль — я сохраню её."
        )
        return

    # Экспорт через Атланта
    markdown = atlant.export_markdown(user_id)

    # Отправляем как файл
    from io import BytesIO
    file_content = markdown.encode('utf-8')
    file_obj = BytesIO(file_content)
    file_obj.name = f"память_{username}_{datetime.now().strftime('%Y%m%d')}.md"

    stats = atlant.thought_stats(user_id)

    await update.message.reply_document(
        document=file_obj,
        filename=file_obj.name,
        caption=f"Ɉ Твоя память Montana ({stats['total']} записей)\n\n🏛 Атлант — Гиппокамп Montana"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#                              УЗЛЫ И КОШЕЛЬКИ
# ═══════════════════════════════════════════════════════════════════════════════

async def node_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /node [адрес|alias] — показать кошелек узла"""
    user_id = update.effective_user.id

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

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
    """Команда /balance — показать свой баланс (confirmed + pending)"""
    user = update.effective_user
    user_id = user.id

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

    address = str(user_id)

    # Получаем баланс с pending
    balance_info = time_bank.get_balance_with_pending(address)
    confirmed = balance_info["confirmed"]
    pending = balance_info["pending"]
    total = balance_info["total"]

    # Информация о присутствии
    presence_info = time_bank.get(address)

    display = f"Ɉ\n\n"
    display += f"**Твой кошелек Montana**\n\n"
    display += f"**Адрес:** `{user_id}`\n"
    display += f"_(твой Telegram ID — адрес кошелька и ключ)_\n\n"

    # Отображаем баланс с pending
    display += f"💰 **Баланс:** {confirmed} Ɉ\n"

    if pending > 0:
        display += f"⏳ **Накапливается:** +{pending} Ɉ\n"
        display += f"{'─' * 25}\n"
        display += f"💎 **Всего:** {total} Ɉ\n\n"

        # Показываем когда подтвердится
        stats = time_bank.stats()
        t2_remaining = stats.get("t2_remaining_sec", 0)
        t2_minutes = t2_remaining // 60
        t2_seconds = t2_remaining % 60
        display += f"⏱ Следующее подтверждение через {t2_minutes}:{t2_seconds:02d}\n\n"
    else:
        display += f"\n"

    if presence_info and presence_info.get('is_active'):
        display += f"🟢 **Присутствие:** активно\n\n"

    display += f"📊 **/stats** — статистика сети Montana\n"
    display += f"📜 **/tx** — история транзакций\n"
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

    # SECURITY: Проверка авторизации — КРИТИЧНО для переводов
    if not await check_user_approved(update, user_id):
        return

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

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

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
    user_id = update.effective_user.id

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

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


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика сети Montana (токеномика)"""
    user_id = update.effective_user.id

    # SECURITY: Проверка авторизации
    if not await check_user_approved(update, user_id):
        return

    # Получаем статистику из TIME_BANK
    stats = time_bank.stats()

    # Временные координаты
    tau3_count = stats["tau3_count"]
    tau4_count = stats["tau4_count"]
    current_year = stats["current_year"]
    halving_coef = stats["halving_coefficient"]

    # Текущий T2
    t2_count = stats["t2_count"]
    t2_elapsed = stats["t2_elapsed_sec"]
    t2_remaining = stats["t2_remaining_sec"]
    t2_to_next_tau3 = stats["t2_to_next_tau3"]

    # Активность
    active_presence = stats["active_presence"]
    wallets_count = stats["wallets"]

    # Форматируем вывод
    display = f"Ɉ\n\n"
    display += f"**📊 Montana Protocol — Статистика**\n\n"

    # Temporal Coordinates
    display += f"**⏱ Временные Координаты**\n"
    display += f"├ τ₂ (текущий slice): #{t2_count}\n"
    display += f"├ τ₃ (checkpoints): #{tau3_count}\n"
    display += f"├ τ₄ (epoch): #{tau4_count}\n"
    display += f"└ Год Montana: {current_year}\n\n"

    # Halving
    display += f"**💰 Эмиссия**\n"
    display += f"├ Коэффициент халвинга: {halving_coef}×\n"
    display += f"└ 1 секунда присутствия = {halving_coef} Ɉ\n\n"

    # Следующие события
    display += f"**⏳ Следующие события**\n"
    t2_min = t2_remaining // 60
    t2_sec = t2_remaining % 60
    display += f"├ Следующий τ₂: через {t2_min}:{t2_sec:02d}\n"
    display += f"└ До τ₃ checkpoint: {t2_to_next_tau3} слайсов\n\n"

    # Сеть
    display += f"**🌐 Сеть**\n"
    display += f"├ Активное присутствие: {active_presence}\n"
    display += f"└ Всего кошельков: {wallets_count}\n\n"

    display += f"_Montana Protocol v{stats['version']}_"

    await update.message.reply_text(display, parse_mode="Markdown")


async def check_node_online(ip: str, timeout: float = 2.0) -> bool:
    """Проверка узла онлайн через TCP порт 22"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, 22))
        sock.close()
        return result == 0
    except:
        return False


async def stat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stat — статистика бота (только для владельца)"""
    user_id = update.effective_user.id

    # Проверка что это владелец
    if user_id != BOT_CREATOR_ID:
        await update.message.reply_text("Ɉ\n\nКоманда доступна только владельцу бота.")
        return

    # Показываем что работаем
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Загружаем пользователей
    users = load_users()
    total_users = len(users)

    # Считаем одобренных и ожидающих
    approved_count = sum(1 for u in users.values() if u.get('approved', False))
    pending_count = sum(1 for u in users.values() if u.get('pending_approval', False))

    # Статистика по времени
    from datetime import datetime
    now = datetime.now()

    # Читаем stream для статистики мыслей
    thought_count = 0
    if STREAM_FILE.exists():
        try:
            with open(STREAM_FILE, 'r', encoding='utf-8') as f:
                thought_count = sum(1 for _ in f)
        except:
            pass

    # Статистика по транзакциям
    tx_count = len(time_bank.tx_feed(limit=10000))

    # Статистика по узлам с проверкой онлайн
    nodes = node_crypto_system.get_all_nodes()
    official_nodes = [n for n in nodes if n.get('official', False)]

    # Проверяем статус каждого узла
    node_statuses = []
    for node in official_nodes:
        ip = node.get('ip', '')
        is_online = await check_node_online(ip) if ip else False
        node_statuses.append({
            'name': node.get('node_name', 'unknown'),
            'location': node.get('location', ''),
            'ip': ip,
            'online': is_online,
            'priority': node.get('priority', 99)
        })

    # Сортируем по priority
    node_statuses.sort(key=lambda x: x['priority'])

    online_count = sum(1 for n in node_statuses if n['online'])

    # Формируем ответ
    display = f"Ɉ\n\n"
    display += f"**📊 Статистика Montana Protocol**\n\n"

    display += f"**👥 Пользователи**\n"
    display += f"├ Всего: **{total_users}**\n"
    display += f"├ Одобрено: **{approved_count}**\n"
    display += f"└ Ожидают: **{pending_count}**\n\n"

    display += f"**💰 Time Bank**\n"
    display += f"└ Транзакций: **{tx_count}**\n\n"

    display += f"**🌐 Узлы Montana** ({online_count}/{len(node_statuses)} online)\n"
    for ns in node_statuses:
        status = "🟢" if ns['online'] else "🔴"
        display += f"{status} **{ns['name']}** {ns['location']}\n"
        display += f"    └ `{ns['ip']}`\n"

    display += f"\n**💭 Поток мыслей**\n"
    display += f"└ Записей: **{thought_count}**\n\n"

    # Список последних 5 пользователей
    if users:
        display += f"**👤 Последние пользователи**\n"
        user_items = list(users.items())[-5:]
        for uid, udata in reversed(user_items):
            name = udata.get('first_name', 'Unknown')
            username = udata.get('username', '')
            status = "✅" if udata.get('approved') else "⏳"
            display += f"{status} {name}"
            if username:
                display += f" (@{username})"
            display += f" • `{uid}`\n"

    display += f"\n_Montana Protocol v1.0 • {now.strftime('%Y-%m-%d %H:%M')}_"

    # Кнопки управления
    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="stat_refresh"),
            InlineKeyboardButton("📋 Логи", callback_data="stat_logs")
        ],
        [
            InlineKeyboardButton("🔄 Синхр. узлы", callback_data="stat_sync_nodes"),
            InlineKeyboardButton("📡 Пинг всех", callback_data="stat_ping_all")
        ],
        [
            InlineKeyboardButton("👥 Все пользователи", callback_data="stat_users")
        ]
    ]

    await update.message.reply_text(
        display,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_stat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок управления из /stat"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id != BOT_CREATOR_ID:
        return

    action = query.data

    if action == "stat_refresh":
        # Обновляем статистику
        await query.message.delete()
        # Создаем фейковый update для вызова stat_cmd
        await stat_cmd(update, context)

    elif action == "stat_logs":
        # Показываем реальные логи с текущего сервера
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

        import subprocess
        try:
            result = subprocess.run(
                ["journalctl", "-u", "junona", "-n", "20", "--no-pager", "-o", "short"],
                capture_output=True, text=True, timeout=5
            )
            logs = result.stdout.strip()
            if len(logs) > 3500:
                logs = logs[-3500:]

            # Получаем имя текущего узла
            node_name = os.getenv("NODE_NAME", "unknown")

            await query.message.reply_text(
                f"Ɉ\n\n📋 **Логи {node_name}** (последние 20):\n\n"
                f"```\n{logs}\n```",
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.message.reply_text(
                f"Ɉ\n\n⚠️ Не удалось получить логи: {e}"
            )

    elif action == "stat_sync_nodes":
        # Перезагружаем узлы из файла
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

        # Принудительно сбрасываем синглтон и перечитываем nodes.json
        import node_crypto
        node_crypto._node_crypto_system = None
        global node_crypto_system
        node_crypto_system = get_node_crypto_system()

        nodes = node_crypto_system.get_all_nodes()
        official = [n for n in nodes if n.get('official', False)]

        node_list = "\n".join([f"• {n.get('node_name')} ({n.get('location')})" for n in official])

        await query.message.reply_text(
            f"Ɉ\n\n🔄 **Узлы перезагружены**\n\n"
            f"Загружено: {len(official)} official узлов\n\n"
            f"{node_list}",
            parse_mode="Markdown"
        )

    elif action == "stat_ping_all":
        # Пингуем все узлы
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

        nodes = node_crypto_system.get_all_nodes()
        official_nodes = [n for n in nodes if n.get('official', False)]

        results = []
        for node in official_nodes:
            ip = node.get('ip', '')
            name = node.get('node_name', 'unknown')
            is_online = await check_node_online(ip) if ip else False
            status = "🟢" if is_online else "🔴"
            results.append(f"{status} {name}: {ip}")

        await query.message.reply_text(
            f"Ɉ\n\n📡 **Пинг узлов:**\n\n" + "\n".join(results),
            parse_mode="Markdown"
        )

    elif action == "stat_users":
        # Показываем всех пользователей с кнопками управления
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

        users = load_users()
        if not users:
            await query.message.reply_text("Ɉ\n\n👥 Нет пользователей.")
            return

        display = "Ɉ\n\n**👥 Все пользователи:**\n\n"

        # Создаём кнопки для каждого пользователя
        keyboard = []
        for uid, udata in users.items():
            name = udata.get('first_name', 'Unknown')
            username = udata.get('username', '')
            is_approved = udata.get('approved', False)
            is_pending = udata.get('pending_approval', False)

            if is_approved:
                status = "✅"
                btn_text = f"🚫 {name}"
                btn_action = f"stat_revoke_{uid}"
            elif is_pending:
                status = "⏳"
                btn_text = f"✅ {name}"
                btn_action = f"stat_approve_{uid}"
            else:
                status = "❌"
                btn_text = f"✅ {name}"
                btn_action = f"stat_approve_{uid}"

            user_line = f"{status} **{name}**"
            if username:
                user_line += f" @{username}"
            user_line += f" `{uid}`\n"
            display += user_line

            keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_action)])

        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="stat_refresh")])

        await query.message.reply_text(
            display,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action.startswith("stat_revoke_"):
        # Отзыв верификации
        target_uid = action.replace("stat_revoke_", "")
        users = load_users()
        if target_uid in users:
            users[target_uid]['approved'] = False
            users[target_uid]['pending_approval'] = False
            save_users(users)
            name = users[target_uid].get('first_name', target_uid)
            await query.message.reply_text(f"Ɉ\n\n🚫 **{name}** отключён от Юноны.")
        else:
            await query.message.reply_text("Ɉ\n\n⚠️ Пользователь не найден.")

    elif action.startswith("stat_approve_"):
        # Одобрение пользователя
        target_uid = action.replace("stat_approve_", "")
        users = load_users()
        if target_uid in users:
            users[target_uid]['approved'] = True
            users[target_uid]['pending_approval'] = False
            save_users(users)
            name = users[target_uid].get('first_name', target_uid)
            await query.message.reply_text(f"Ɉ\n\n✅ **{name}** одобрен.")
        else:
            await query.message.reply_text("Ɉ\n\n⚠️ Пользователь не найден.")


# ═══════════════════════════════════════════════════════════════════════════════
#                              ГЛАВЫ MONTANA
# ═══════════════════════════════════════════════════════════════════════════════

async def offer_chapter(update: Update, user_id: int, chapter_num: int):
    """Юнона предлагает главу элегантно"""

    # Получаем информацию о главе
    chapter_info = atlant.get_chapter_files(chapter_num)
    if not chapter_info:
        return

    # Записываем что предложили главу
    atlant.offer_chapter(user_id, chapter_num)

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
    atlant.set_preference(user_id, "format", format_choice)

    # Получаем файлы
    chapter_info = atlant.get_chapter_files(chapter_num)
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
    atlant.set_context(user_id, "waiting_for", "impression")
    atlant.set_context(user_id, "current_chapter", chapter_num)


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
    chat_id = update.effective_chat.id

    # Команды меню будут установлены ПОСЛЕ проверки авторизации

    # Проверяем - новый пользователь или возвращается
    users = load_users()
    is_new_user = str(user_id) not in users

    # Загружаем или создаём данные пользователя
    if is_new_user:
        # Новый пользователь — создаём запись
        user_data = {
            'first_name': user.first_name,
            'username': user.username,
            'history': [],
            'approved': user_id == BOT_CREATOR_ID,  # Владелец одобрен автоматически
            'pending_approval': user_id != BOT_CREATOR_ID  # Новые ждут одобрения
        }
        save_user(user_id, user_data)
    else:
        # Возвращающийся пользователь — загружаем существующие данные
        user_data = get_user(user_id)
        # Обновляем только имя/username (могли измениться)
        user_data['first_name'] = user.first_name
        user_data['username'] = user.username
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

    # SECURITY: Проверка авторизации ПЕРЕД любыми действиями
    logger.info(f"🔐 AUTH CHECK user={user_id}: pending={user_data.get('pending_approval')}, approved={user_data.get('approved')}")

    # 1. Ожидает одобрения — минимальный ответ без AI
    if user_data.get('pending_approval'):
        # Убираем все команды для неавторизованных
        try:
            from telegram import BotCommandScopeChat
            await context.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
        except:
            pass

        # Короткое сообщение без AI, без записи в память
        await update.message.reply_text(
            f"Ɉ\n\n⏳ Запрос на модерации.\n\nОжидай."
        )
        return

    # 2. Отклонён — минимальный ответ
    if not user_data.get('approved', False):
        try:
            from telegram import BotCommandScopeChat
            await context.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
        except:
            pass

        await update.message.reply_text("Ɉ\n\n❌ Доступ закрыт.")
        return

    # ✅ ОДОБРЕН — устанавливаем меню команд
    try:
        from telegram import BotCommandScopeChat
        # Принудительный сброс старого меню
        await context.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
        # Владелец получает расширенное меню с /stat и /register_node
        commands = BOT_COMMANDS_OWNER if user_id == BOT_CREATOR_ID else BOT_COMMANDS
        await context.bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=chat_id)
        )
        logger.info(f"✅ Меню установлено для {user_id} ({'OWNER' if user_id == BOT_CREATOR_ID else 'user'}): {len(commands)} команд")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить меню: {e}")

    # Показываем "печатает..." только одобренным
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Юнона приветствует пользователя через AI
    try:
        # Получаем ответ от Юноны
        response = await junona.welcome_guest(user_data)

        # Сохраняем в историю координатора
        atlant.add_message(user_id, "user", "/start")
        atlant.add_message(user_id, "junona", response)

        # Отправляем ответ
        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        # Fallback если AI недоступна
        greeting = f"Приветствую тебя, {user.first_name}! Я очень рада, что ты решил присоединиться ко мне в этом виртуальном пространстве. Надеюсь, ты чувствуешь себя здесь уютно и комфортно.\n\nО чем хочешь поговорить?"
        atlant.add_message(user_id, "junona", greeting)
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

    # SECURITY: Проверка что пользователь есть в базе
    users = load_users()
    if str(user_id) not in users:
        # Совсем новый пользователь — не отвечаем, направляем на /start
        await update.message.reply_text(
            f"Ɉ\n\n👋 Привет!\n\nНажми /start чтобы начать."
        )
        return

    user_data = users[str(user_id)]

    # SECURITY: Проверка одобрения — только approved=True могут общаться
    if not user_data.get('approved', False):
        if user_data.get('pending_approval', False):
            # Молча игнорируем — уже знает что на модерации
            return
        else:
            # Отклонён — молча игнорируем
            return

    history = user_data.get('history', [])

    # Используем детектор новизны гиппокампа
    is_thought = atlant.is_thought(text)

    # Сохраняем в поток только если это мысль
    if is_thought:
        atlant.save_thought(user_id, text, username=user.username or "аноним")
        logger.info(f"💭 {user.first_name}: {text[:50]}...")

    # Записываем все сообщения в координатор
    atlant.add_message(user_id, "user", text)

    # Проверяем контекст - может ждем впечатления о главе?
    ctx = atlant.get_context(user_id)
    if ctx.get("waiting_for") == "impression":
        current_chapter = ctx.get("current_chapter")
        if current_chapter is not None:
            # Пользователь делится впечатлением
            atlant.complete_chapter(user_id, current_chapter,
                                        atlant.get_preference(user_id, "format", "text"),
                                        impression=text)

            atlant.add_note(user_id, f"Глава {current_chapter}: {text[:100]}")

            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            # Юнона благодарит и резонирует
            response = f"Ɉ\n\nСпасибо что поделился.\n\nЯ записала твои впечатления о главе {current_chapter}. " \
                      f"Это важная часть твоего пути — не просто читать, а осмысливать.\n\n" \
                      f"Продолжим разговор?"

            atlant.add_message(user_id, "junona", response)
            await update.message.reply_text(response)
            return

    # Показываем "печатает..." как в обычном чате
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Юнона отвечает
    if junona:
        try:
            # Детектируем вопросы о начислениях/балансе/статистике
            text_lower = text.lower()
            is_about_money = any(word in text_lower for word in [
                'начисл', 'баланс', 'сколько', 'монет', 'секунд', 'заработ',
                'получ', 'время', 'эмиссия', 't2', 'присутств'
            ])

            # Готовим контекст для Юноны
            user_context = {
                'name': user.first_name,
                'lang': 'ru'
            }

            # Если вопрос о начислениях - добавляем точные данные
            if is_about_money:
                address = str(user_id)
                balance = time_bank.balance(address)
                presence_info = time_bank.get(address)

                user_context['montana_agent_mode'] = True
                user_context['user_balance'] = balance
                user_context['emission_rate'] = 15000  # Ɉ в секунду за T2
                user_context['t2_seconds'] = presence_info.get('t2_seconds', 0) if presence_info else 0
                user_context['is_active'] = presence_info.get('is_active', False) if presence_info else False

                # Добавляем инструкцию для Юноны отвечать как агент Montana с точными цифрами
                user_context['system_instruction'] = (
                    "Ты агент Montana Protocol. Отвечай точными цифрами из контекста. "
                    f"Баланс пользователя: {balance} секунд. "
                    f"Эмиссия T2: 15000 Ɉ. "
                    f"Секунд в T2: {user_context['t2_seconds']}. "
                    "Не используй общие фразы - только точные данные."
                )

            response = await junona.respond(text, user_context, history)

            # Сохраняем в историю
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": response})

            # Оставляем только последние 10 сообщений
            user_data['history'] = history[-10:]
            save_user(user_id, user_data)

            # Записываем ответ Юноны
            atlant.add_message(user_id, "junona", response)

            await update.message.reply_text(f"Ɉ\n\n{response}")

            # Проверяем - просил ли пользователь материалы ЯВНО?
            if is_asking_for_materials(text):
                # Пользователь явно попросил материалы - предлагаем следующую главу
                next_chapter = atlant.get_next_chapter(user_id)
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

def kill_existing_bot_processes():
    """
    Проверяет и останавливает все запущенные процессы бота.

    Предотвращает конфликт getUpdates при запуске нового экземпляра.
    """
    import subprocess
    import signal

    try:
        # Находим все процессы junomontanaagibot.py
        ps_output = subprocess.check_output(['ps', 'aux'], text=True)
        lines = ps_output.split('\n')

        killed_count = 0
        for line in lines:
            if 'junomontanaagibot.py' in line and 'grep' not in line:
                # Извлекаем PID
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        # Не убиваем себя
                        if pid != os.getpid():
                            os.kill(pid, signal.SIGKILL)
                            killed_count += 1
                            logger.info(f"🗑 Остановлен старый процесс бота: PID {pid}")
                    except (ValueError, ProcessLookupError):
                        pass

        if killed_count > 0:
            logger.info(f"✅ Остановлено {killed_count} старых процессов бота")
            # Даём время на очистку Telegram API (getUpdates session)
            import time
            logger.info("⏳ Ожидание освобождения Telegram API (10 сек)...")
            time.sleep(10)
        else:
            logger.debug("✓ Нет старых процессов бота")

    except Exception as e:
        logger.warning(f"⚠️ Ошибка проверки процессов: {e}")


async def setup_bot_commands(application, force=False):
    """
    Настройка кнопки меню с командами

    Args:
        application: Telegram application
        force: Если True, принудительно удаляет все старые команды перед установкой новых
    """
    from telegram import BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators

    if force:
        # Удаляем команды для всех scope принудительно
        scopes = [
            BotCommandScopeDefault(),
            BotCommandScopeAllPrivateChats(),
            BotCommandScopeAllGroupChats(),
            BotCommandScopeAllChatAdministrators()
        ]

        for scope in scopes:
            try:
                await application.bot.delete_my_commands(scope=scope)
                logger.info(f"🗑 Команды принудительно удалены для scope: {scope}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить команды для scope {scope}: {e}")

    # Устанавливаем команды из константы BOT_COMMANDS
    await application.bot.set_my_commands(BOT_COMMANDS)
    logger.info(f"✅ Установлено {len(BOT_COMMANDS)} команд в меню")

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

# Глобальные переменные для управления polling
_application = None
_polling_task = None
_polling_lock = threading.Lock()  # Защита от одновременных вызовов start/stop_polling
_is_polling = False  # Флаг состояния polling


async def start_polling():
    """Запустить polling (вызывается когда узел стал мастером)"""
    global _application, _polling_task, _is_polling

    # Проверяем что не запущен уже
    with _polling_lock:
        if _is_polling:
            logger.warning("⚠️ Polling уже запущен, пропускаем...")
            return

    try:
        # Останавливаем предыдущий если был
        await stop_polling()

        # КРИТИЧЕСКИ ВАЖНО: Ждем освобождения Telegram API
        logger.info("⏳ Ожидание освобождения Telegram API (15 сек)...")
        await asyncio.sleep(15)

        # Инициализация RAG базы знаний - ОТКЛЮЧЕНО ДЛЯ ЭКОНОМИИ ПАМЯТИ
        # try:
        #     logger.info("🧠 Инициализация базы знаний Montana...")
        #     init_and_index(background=True)
        # except Exception as e:
        #     logger.warning(f"⚠️ RAG инициализация: {e}")

        # Создаём application
        _application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        _application.add_error_handler(error_handler)

        # Инициализируем для принудительной очистки Telegram API
        await _application.initialize()

        # КРИТИЧЕСКИ ВАЖНО: Сбрасываем любые активные getUpdates сессии
        try:
            logger.info("🧹 Очистка старых Telegram API сессий...")
            # Удаляем webhook (если был)
            await _application.bot.delete_webhook(drop_pending_updates=True)
            # Делаем одноразовый getUpdates с timeout=1 чтобы сбросить очередь
            await _application.bot.get_updates(offset=-1, timeout=1)
            logger.info("✅ Telegram API сессии очищены")
        except Exception as e:
            logger.warning(f"⚠️ Очистка API: {e}")

        # Handlers
        _application.add_handler(CommandHandler("start", start))
        _application.add_handler(CommandHandler("stream", stream_cmd))
        _application.add_handler(CommandHandler("export", export_cmd))
        _application.add_handler(CommandHandler("node", node_cmd))
        _application.add_handler(CommandHandler("network", network_cmd))
        _application.add_handler(CommandHandler("register_node", register_node_cmd))
        _application.add_handler(CommandHandler("balance", balance_cmd))
        _application.add_handler(CommandHandler("transfer", transfer_cmd))
        _application.add_handler(CommandHandler("tx", tx_cmd))
        _application.add_handler(CommandHandler("feed", feed_cmd))
        _application.add_handler(CommandHandler("stats", stats_cmd))
        _application.add_handler(CommandHandler("stat", stat_cmd))
        _application.add_handler(CallbackQueryHandler(handle_chapter_choice, pattern="^chapter_"))
        _application.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject)_"))
        _application.add_handler(CallbackQueryHandler(handle_stat_callback, pattern="^stat_"))
        _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Настройка команд меню и запуск
        await setup_bot_commands(_application, force=True)
        await _application.start()
        await _application.updater.start_polling(
            drop_pending_updates=True,  # Сбрасываем старую сессию getUpdates
            allowed_updates=['message', 'callback_query']
        )

        # Устанавливаем флаг что polling запущен
        with _polling_lock:
            _is_polling = True

        logger.info("✅ Polling запущен")

    except Exception as e:
        logger.error(f"❌ Ошибка запуска polling: {e}")
        with _polling_lock:
            _is_polling = False
        raise


async def stop_polling():
    """Остановить polling (вызывается когда узел ушёл в standby)"""
    global _application, _polling_task, _is_polling

    # Сбрасываем флаг polling
    with _polling_lock:
        _is_polling = False

    if _application:
        try:
            logger.info("🛑 Останавливаем polling...")

            if _application.updater and _application.updater.running:
                await _application.updater.stop()

            if _application.running:
                await _application.stop()

            await _application.shutdown()
            _application = None

            logger.info("✅ Polling остановлен")

        except Exception as e:
            logger.warning(f"⚠️ Ошибка остановки polling: {e}")
            _application = None


async def run_with_3mirror():
    """
    Запуск бота с 3-Mirror Leader Election.

    Архитектура из 003_ТРОЙНОЕ_ЗЕРКАЛО.md:
    - Цепочка узлов: Amsterdam → Moscow → Almaty → SPB → Novosibirsk
    - Я мастер если ВСЕ узлы ДО меня в цепочке мертвы
    - Активная проверка каждые 5 секунд
    - Failover < 10 секунд
    """
    # Останавливаем старые процессы бота перед запуском
    kill_existing_bot_processes()

    leader = get_leader_election()

    logger.info(f"🏔 Montana 3-Mirror Leader Election")
    logger.info(f"📍 Узел: {leader.my_name} (позиция {leader.my_position})")
    logger.info(f"🔗 Цепочка: {' → '.join([n[0] for n in leader.chain])}")

    # Запускаем leader election loop
    await leader.run_leader_loop(
        on_become_master=start_polling,
        on_become_standby=stop_polling
    )


if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN_JUNONA not set")
        exit(1)

    logger.info("Ɉ Юнона — Montana Protocol Bot")

    # Запускаем с 3-Mirror Leader Election
    try:
        asyncio.run(run_with_3mirror())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка по Ctrl+C")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        exit(1)
