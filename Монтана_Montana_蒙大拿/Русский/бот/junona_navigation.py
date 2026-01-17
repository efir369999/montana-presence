# junona_navigation.py
# Навигация по иерархии Ничто_Nothing_无_金元Ɉ
# Юнона погружает: Генезис → Философия → Код

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from pathlib import Path
import os

# ═══════════════════════════════════════════════════════════════════════════════
#                              СТРУКТУРА ПРОЕКТА
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_STRUCTURE = {
    "root": {
        "name": "Ничто_Nothing_无_金元Ɉ",
        "emoji": "♾️",
        "description": "Корень. Автор протокола.",
        "children": ["montana"]
    },
    "montana": {
        "name": "Монтана_Montana_蒙大拿",
        "emoji": "🏔️",
        "description": "Протокол Montana — время как консенсус.",
        "path": "Монтана_Montana_蒙大拿",
        "children": ["genesis", "council", "philosophy", "cognitive", "protocol", "crypto", "network", "economics"]
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              ПУТЬ ПОГРУЖЕНИЯ
    # ═══════════════════════════════════════════════════════════════════════════
    
    # 1. ГЕНЕЗИС — Начало всего
    "genesis": {
        "name": "Генезис_Genesis_创世",
        "emoji": "🌅",
        "description": "Начало. История создания. Когнитивный генезис.",
        "path": "Монтана_Montana_蒙大拿/Генезис_Genesis_创世",
        "order": 1,
        "stage": "НАЧАЛО",
        "files": [
            "COGNITIVE_GENESIS_2026-01-09.md",
            "GENESIS_PROOF_2026-01-09.md",
            "GENESIS_SIGNATURE.md",
            "README.md"
        ],
        "children": []
    },
    
    # 2. СОВЕТ — Управление (сразу после Генезиса)
    "council": {
        "name": "Совет_Council_理事会",
        "emoji": "👥",
        "description": "Montana Guardian Council. AI-модели как советники.",
        "path": "Монтана_Montana_蒙大拿/Совет_Council_理事会",
        "order": 2,
        "stage": "УПРАВЛЕНИЕ",
        "files": [
            "SECURITY_COUNCIL_MEETING.md",
            "JUNONA_WHITEPAPER.md",
            "JOIN_COUNCIL_PROMPT.md"
        ],
        "children": ["anthropic", "google", "openai", "xai", "cursor"]
    },
    
    # 3. ФИЛОСОФИЯ — Первый шаг в понимании
    "philosophy": {
        "name": "philosophy (Философия)",
        "emoji": "📚",
        "description": "Философия Montana. Trust, Identity, Presence.",
        "path": "Монтана_Montana_蒙大拿/en_English_英语/philosophy",
        "order": 3,
        "stage": "ФИЛОСОФИЯ",
        "files": [
            "PHILOSOPHY_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },
    
    # 4. КОГНИТИВНАЯ СИСТЕМА
    "cognitive": {
        "name": "cognitive (Когнитивная)",
        "emoji": "🧠",
        "description": "Когнитивные подписи. Идентичность через мысли.",
        "path": "Монтана_Montana_蒙大拿/en_English_英语/cognitive",
        "order": 4,
        "stage": "ФИЛОСОФИЯ",
        "files": [
            "COGNITIVE_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },
    
    # 5. ПРОТОКОЛ ACP — Код начинается
    "protocol": {
        "name": "协议 (Протокол ACP)",
        "emoji": "📋",
        "description": "Asynchronous Consensus Protocol. Время как консенсус.",
        "path": "Монтана_Montana_蒙大拿/zh_Chinese_中文/协议",
        "order": 5,
        "stage": "КОД",
        "files": [
            "ACP_白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },
    
    # 6. КРИПТОГРАФИЯ
    "crypto": {
        "name": "加密 (Криптография)",
        "emoji": "🔐",
        "description": "Пост-квантовая криптография. SHA3, ML-DSA.",
        "path": "Монтана_Montana_蒙大拿/zh_Chinese_中文/加密",
        "order": 6,
        "stage": "КОД",
        "files": [
            "加密_白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },
    
    # 7. P2P СЕТЬ
    "network": {
        "name": "сеть (P2P Сеть)",
        "emoji": "🌐",
        "description": "P2P сеть. Eclipse protection. Gossip протокол.",
        "path": "Монтана_Montana_蒙大拿/ru_Russian_俄语/сеть",
        "order": 7,
        "stage": "КОД",
        "files": [
            "P2P_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },
    
    # 8. ЭКОНОМИКА
    "economics": {
        "name": "экономика (Экономика)",
        "emoji": "💰",
        "description": "Токеномика 金元Ɉ. Эмиссия. Распределение.",
        "path": "Монтана_Montana_蒙大拿/ru_Russian_俄语/экономика",
        "order": 8,
        "stage": "КОД",
        "files": [
            "金元_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },
    
    # Подразделы Совета
    "anthropic": {
        "name": "Anthropic (Claude)",
        "emoji": "🟤",
        "path": "Монтана_Montana_蒙大拿/Совет_Council_理事会/Anthropic",
        "children": []
    },
    "google": {
        "name": "Google (Gemini)",
        "emoji": "🔵",
        "path": "Монтана_Montana_蒙大拿/Совет_Council_理事会/Google",
        "children": []
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "emoji": "🟢",
        "path": "Монтана_Montana_蒙大拿/Совет_Council_理事会/OpenAI",
        "children": []
    },
    "xai": {
        "name": "xAI (Grok)",
        "emoji": "⚪",
        "path": "Монтана_Montana_蒙大拿/Совет_Council_理事会/xAI",
        "children": []
    },
    "cursor": {
        "name": "Cursor (Composer)",
        "emoji": "🟣",
        "path": "Монтана_Montana_蒙大拿/Совет_Council_理事会/Cursor",
        "children": []
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
#                              КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════════════════════════

def get_navigation_keyboard(current_node: str = "root") -> InlineKeyboardMarkup:
    """Генерирует клавиатуру навигации для текущего узла."""
    node = PROJECT_STRUCTURE.get(current_node, PROJECT_STRUCTURE["root"])
    buttons = []
    
    # Кнопки дочерних элементов
    children = node.get("children", [])
    for child_id in children:
        child = PROJECT_STRUCTURE.get(child_id, {})
        emoji = child.get("emoji", "📁")
        name = child.get("name", child_id)
        stage = child.get("stage", "")
        
        # Добавляем метку этапа
        label = f"{emoji} {name}"
        if stage:
            label = f"{emoji} {name}"
        
        buttons.append([InlineKeyboardButton(label, callback_data=f"nav_{child_id}")])
    
    # Кнопка "Назад" если не в корне
    if current_node != "root":
        buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="nav_back")])
    
    # Кнопка главного меню
    buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(buttons)


def get_main_navigation_keyboard() -> InlineKeyboardMarkup:
    """Главное меню навигации — путь погружения Юноны."""
    buttons = [
        # Заголовок
        [InlineKeyboardButton("═══ ПУТЬ ЮНОНЫ ═══", callback_data="nav_info")],
        
        # 1. Генезис — Начало
        [InlineKeyboardButton("🌅 Генезис — НАЧАЛО", callback_data="nav_genesis")],
        
        # 2. Совет — сразу после Генезиса
        [InlineKeyboardButton("👥 Совет — УПРАВЛЕНИЕ", callback_data="nav_council")],
        
        # Разделитель
        [InlineKeyboardButton("─── ФИЛОСОФИЯ ───", callback_data="nav_info")],
        
        # 3-4. Философия
        [InlineKeyboardButton("📚 Философия", callback_data="nav_philosophy"),
         InlineKeyboardButton("🧠 Когнитивная", callback_data="nav_cognitive")],
        
        # Разделитель
        [InlineKeyboardButton("─── КОД ───", callback_data="nav_info")],
        
        # 5-6. Протокол и Криптография
        [InlineKeyboardButton("📋 Протокол ACP", callback_data="nav_protocol"),
         InlineKeyboardButton("🔐 Криптография", callback_data="nav_crypto")],
        
        # 7-8. Сеть и Экономика
        [InlineKeyboardButton("🌐 Сеть P2P", callback_data="nav_network"),
         InlineKeyboardButton("💰 Экономика", callback_data="nav_economics")],
        
        # Главное меню
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════════════════════════════════════════
#                              СООБЩЕНИЯ
# ═══════════════════════════════════════════════════════════════════════════════

def get_node_message(node_id: str) -> str:
    """Генерирует сообщение для узла."""
    node = PROJECT_STRUCTURE.get(node_id, {})
    
    emoji = node.get("emoji", "📁")
    name = node.get("name", node_id)
    description = node.get("description", "")
    path = node.get("path", "")
    stage = node.get("stage", "")
    files = node.get("files", [])
    order = node.get("order", 0)
    
    # Формируем сообщение
    message = f"{emoji} *{name}*\n\n"
    
    if stage:
        message += f"📍 Этап: *{stage}*\n"
    
    if order:
        message += f"🔢 Порядок: {order}/8\n"
    
    if description:
        message += f"\n{description}\n"
    
    if path:
        message += f"\n📂 `{path}/`\n"
    
    if files:
        message += f"\n📄 *Файлы:*\n"
        for f in files[:5]:  # Показываем до 5 файлов
            message += f"  • `{f}`\n"
        if len(files) > 5:
            message += f"  • _...и ещё {len(files) - 5}_\n"
    
    return message


def get_welcome_message() -> str:
    """Приветственное сообщение навигации."""
    return """♾️ *Ничто\_Nothing\_无\_金元Ɉ*

Добро пожаловать в навигацию по протоколу Montana.

*Путь погружения Юноны:*

1️⃣ 🌅 *Генезис* — НАЧАЛО
2️⃣ 👥 *Совет* — УПРАВЛЕНИЕ

─── ФИЛОСОФИЯ ───
3️⃣ 📚 *Философия* — Trust, Identity, Presence
4️⃣ 🧠 *Когнитивная* — Подписи мыслей

─── КОД ───
5️⃣ 📋 *Протокол ACP* — Время как консенсус
6️⃣ 🔐 *Криптография* — SHA3, ML-DSA
7️⃣ 🌐 *Сеть P2P* — Eclipse protection
8️⃣ 💰 *Экономика* — Токен 金元Ɉ

_Выберите раздел для погружения:_
"""


# ═══════════════════════════════════════════════════════════════════════════════
#                              ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════════════════════════

# История навигации для каждого пользователя
navigation_history = {}

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия кнопок навигации."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    # Инициализируем историю пользователя
    if user_id not in navigation_history:
        navigation_history[user_id] = ["root"]
    
    if callback_data == "nav_info":
        # Информационная кнопка — ничего не делаем
        return
    
    if callback_data == "nav_back":
        # Возврат назад
        if len(navigation_history[user_id]) > 1:
            navigation_history[user_id].pop()
        current = navigation_history[user_id][-1]
    elif callback_data.startswith("nav_"):
        # Переход к узлу
        node_id = callback_data[4:]  # Убираем "nav_"
        navigation_history[user_id].append(node_id)
        current = node_id
    else:
        current = "root"
    
    # Генерируем сообщение и клавиатуру
    if current == "root":
        message = get_welcome_message()
        keyboard = get_main_navigation_keyboard()
    else:
        message = get_node_message(current)
        node = PROJECT_STRUCTURE.get(current, {})
        if node.get("children"):
            keyboard = get_navigation_keyboard(current)
        else:
            # Конечный узел — показываем кнопку назад
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="nav_back")],
                [InlineKeyboardButton("🏠 Путь Юноны", callback_data="nav_root")]
            ])
    
    try:
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


async def start_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /navigate — запуск навигации."""
    user_id = update.effective_user.id
    navigation_history[user_id] = ["root"]
    
    await update.message.reply_text(
        text=get_welcome_message(),
        parse_mode="Markdown",
        reply_markup=get_main_navigation_keyboard()
    )


# ═══════════════════════════════════════════════════════════════════════════════
#                              ИНТЕГРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

def register_navigation_handlers(application):
    """Регистрирует обработчики навигации в приложении Telegram."""
    from telegram.ext import CommandHandler
    
    # Команда /navigate
    application.add_handler(CommandHandler("navigate", start_navigation))
    application.add_handler(CommandHandler("nav", start_navigation))
    application.add_handler(CommandHandler("путь", start_navigation))
    
    # Обработчик кнопок навигации
    application.add_handler(CallbackQueryHandler(handle_navigation, pattern="^nav_"))


# ═══════════════════════════════════════════════════════════════════════════════
#                              ТЕСТ
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("ИЕРАРХИЯ НИЧТО_NOTHING_无_金元Ɉ")
    print("=" * 60)
    print()
    print(get_welcome_message().replace("*", "").replace("_", "").replace("`", ""))
    print()
    print("Для интеграции в бота добавьте:")
    print("  from junona_navigation import register_navigation_handlers")
    print("  register_navigation_handlers(application)")
