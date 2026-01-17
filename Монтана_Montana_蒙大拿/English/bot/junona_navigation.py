# junona_navigation.py
# Navigation through the Nothing_Nothing_无_金元Ɉ hierarchy
# Juno guides: Genesis → Philosophy → Code

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from pathlib import Path
import os

# ═══════════════════════════════════════════════════════════════════════════════
#                              PROJECT STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_STRUCTURE = {
    "root": {
        "name": "Nothing_Nothing_无_金元Ɉ",
        "emoji": "♾️",
        "description": "Root. Protocol author.",
        "children": ["montana"]
    },
    "montana": {
        "name": "Montana_Montana_蒙大拿",
        "emoji": "🏔️",
        "description": "Montana Protocol — time as consensus.",
        "path": "Montana_Montana_蒙大拿",
        "children": ["genesis", "council", "philosophy", "cognitive", "protocol", "crypto", "network", "economics"]
    },

    # ═══════════════════════════════════════════════════════════════════════════
    #                              IMMERSION PATH
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. GENESIS — The Beginning
    "genesis": {
        "name": "Genesis_Genesis_创世",
        "emoji": "🌅",
        "description": "Beginning. Creation history. Cognitive genesis.",
        "path": "Montana_Montana_蒙大拿/Genesis_Genesis_创世",
        "order": 1,
        "stage": "BEGINNING",
        "files": [
            "COGNITIVE_GENESIS_2026-01-09.md",
            "GENESIS_PROOF_2026-01-09.md",
            "GENESIS_SIGNATURE.md",
            "README.md"
        ],
        "children": []
    },

    # 2. COUNCIL — Governance (right after Genesis)
    "council": {
        "name": "Council_Council_理事会",
        "emoji": "👥",
        "description": "Montana Guardian Council. AI models as advisors.",
        "path": "Montana_Montana_蒙大拿/Council_Council_理事会",
        "order": 2,
        "stage": "GOVERNANCE",
        "files": [
            "SECURITY_COUNCIL_MEETING.md",
            "JUNONA_WHITEPAPER.md",
            "JOIN_COUNCIL_PROMPT.md"
        ],
        "children": ["anthropic", "google", "openai", "xai", "cursor"]
    },

    # 3. PHILOSOPHY — First step to understanding
    "philosophy": {
        "name": "philosophy (Philosophy)",
        "emoji": "📚",
        "description": "Montana philosophy. Trust, Identity, Presence.",
        "path": "Montana_Montana_蒙大拿/English/philosophy",
        "order": 3,
        "stage": "PHILOSOPHY",
        "files": [
            "PHILOSOPHY_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 4. COGNITIVE SYSTEM
    "cognitive": {
        "name": "cognitive (Cognitive)",
        "emoji": "🧠",
        "description": "Cognitive signatures. Identity through thoughts.",
        "path": "Montana_Montana_蒙大拿/English/cognitive",
        "order": 4,
        "stage": "PHILOSOPHY",
        "files": [
            "COGNITIVE_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 5. ACP PROTOCOL — Code begins
    "protocol": {
        "name": "protocol (ACP Protocol)",
        "emoji": "📋",
        "description": "Asynchronous Consensus Protocol. Time as consensus.",
        "path": "Montana_Montana_蒙大拿/English/protocol",
        "order": 5,
        "stage": "CODE",
        "files": [
            "ACP_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 6. CRYPTOGRAPHY
    "crypto": {
        "name": "crypto (Cryptography)",
        "emoji": "🔐",
        "description": "Post-quantum cryptography. SHA3, ML-DSA.",
        "path": "Montana_Montana_蒙大拿/English/crypto",
        "order": 6,
        "stage": "CODE",
        "files": [
            "CRYPTO_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 7. P2P NETWORK
    "network": {
        "name": "network (P2P Network)",
        "emoji": "🌐",
        "description": "P2P network. Eclipse protection. Gossip protocol.",
        "path": "Montana_Montana_蒙大拿/English/network",
        "order": 7,
        "stage": "CODE",
        "files": [
            "P2P_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 8. ECONOMICS
    "economics": {
        "name": "economics (Economics)",
        "emoji": "💰",
        "description": "Tokenomics 金元Ɉ. Emission. Distribution.",
        "path": "Montana_Montana_蒙大拿/English/economics",
        "order": 8,
        "stage": "CODE",
        "files": [
            "ECONOMICS_WHITEPAPER.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # Council subsections
    "anthropic": {
        "name": "Anthropic (Claude)",
        "emoji": "🟤",
        "path": "Montana_Montana_蒙大拿/Council_Council_理事会/Anthropic",
        "children": []
    },
    "google": {
        "name": "Google (Gemini)",
        "emoji": "🔵",
        "path": "Montana_Montana_蒙大拿/Council_Council_理事会/Google",
        "children": []
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "emoji": "🟢",
        "path": "Montana_Montana_蒙大拿/Council_Council_理事会/OpenAI",
        "children": []
    },
    "xai": {
        "name": "xAI (Grok)",
        "emoji": "⚪",
        "path": "Montana_Montana_蒙大拿/Council_Council_理事会/xAI",
        "children": []
    },
    "cursor": {
        "name": "Cursor (Composer)",
        "emoji": "🟣",
        "path": "Montana_Montana_蒙大拿/Council_Council_理事会/Cursor",
        "children": []
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
#                              KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════

def get_navigation_keyboard(current_node: str = "root") -> InlineKeyboardMarkup:
    """Generates navigation keyboard for current node."""
    node = PROJECT_STRUCTURE.get(current_node, PROJECT_STRUCTURE["root"])
    buttons = []

    # Child element buttons
    children = node.get("children", [])
    for child_id in children:
        child = PROJECT_STRUCTURE.get(child_id, {})
        emoji = child.get("emoji", "📁")
        name = child.get("name", child_id)
        stage = child.get("stage", "")

        # Add stage label
        label = f"{emoji} {name}"
        if stage:
            label = f"{emoji} {name}"

        buttons.append([InlineKeyboardButton(label, callback_data=f"nav_{child_id}")])

    # "Back" button if not at root
    if current_node != "root":
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="nav_back")])

    # Main menu button
    buttons.append([InlineKeyboardButton("🏠 Menu", callback_data="main_menu")])

    return InlineKeyboardMarkup(buttons)


def get_main_navigation_keyboard() -> InlineKeyboardMarkup:
    """Main navigation menu — Juno's immersion path."""
    buttons = [
        # Header
        [InlineKeyboardButton("═══ JUNO'S PATH ═══", callback_data="nav_info")],

        # 1. Genesis — Beginning
        [InlineKeyboardButton("🌅 Genesis — BEGINNING", callback_data="nav_genesis")],

        # 2. Council — right after Genesis
        [InlineKeyboardButton("👥 Council — GOVERNANCE", callback_data="nav_council")],

        # Separator
        [InlineKeyboardButton("─── PHILOSOPHY ───", callback_data="nav_info")],

        # 3-4. Philosophy
        [InlineKeyboardButton("📚 Philosophy", callback_data="nav_philosophy"),
         InlineKeyboardButton("🧠 Cognitive", callback_data="nav_cognitive")],

        # Separator
        [InlineKeyboardButton("─── CODE ───", callback_data="nav_info")],

        # 5-6. Protocol and Cryptography
        [InlineKeyboardButton("📋 ACP Protocol", callback_data="nav_protocol"),
         InlineKeyboardButton("🔐 Cryptography", callback_data="nav_crypto")],

        # 7-8. Network and Economics
        [InlineKeyboardButton("🌐 P2P Network", callback_data="nav_network"),
         InlineKeyboardButton("💰 Economics", callback_data="nav_economics")],

        # Main menu
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]

    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════════════════════════════════════════
#                              MESSAGES
# ═══════════════════════════════════════════════════════════════════════════════

def get_node_message(node_id: str) -> str:
    """Generates message for node."""
    node = PROJECT_STRUCTURE.get(node_id, {})

    emoji = node.get("emoji", "📁")
    name = node.get("name", node_id)
    description = node.get("description", "")
    path = node.get("path", "")
    stage = node.get("stage", "")
    files = node.get("files", [])
    order = node.get("order", 0)

    # Build message
    message = f"{emoji} *{name}*\n\n"

    if stage:
        message += f"📍 Stage: *{stage}*\n"

    if order:
        message += f"🔢 Order: {order}/8\n"

    if description:
        message += f"\n{description}\n"

    if path:
        message += f"\n📂 `{path}/`\n"

    if files:
        message += f"\n📄 *Files:*\n"
        for f in files[:5]:  # Show up to 5 files
            message += f"  • `{f}`\n"
        if len(files) > 5:
            message += f"  • _...and {len(files) - 5} more_\n"

    return message


def get_welcome_message() -> str:
    """Navigation welcome message."""
    return """♾️ *Nothing\_Nothing\_无\_金元Ɉ*

Welcome to Montana protocol navigation.

*Juno's Immersion Path:*

1️⃣ 🌅 *Genesis* — BEGINNING
2️⃣ 👥 *Council* — GOVERNANCE

─── PHILOSOPHY ───
3️⃣ 📚 *Philosophy* — Trust, Identity, Presence
4️⃣ 🧠 *Cognitive* — Thought signatures

─── CODE ───
5️⃣ 📋 *ACP Protocol* — Time as consensus
6️⃣ 🔐 *Cryptography* — SHA3, ML-DSA
7️⃣ 🌐 *P2P Network* — Eclipse protection
8️⃣ 💰 *Economics* — Token 金元Ɉ

_Select a section to immerse:_
"""


# ═══════════════════════════════════════════════════════════════════════════════
#                              HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

# Navigation history for each user
navigation_history = {}

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles navigation button presses."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data

    # Initialize user history
    if user_id not in navigation_history:
        navigation_history[user_id] = ["root"]

    if callback_data == "nav_info":
        # Info button — do nothing
        return

    if callback_data == "nav_back":
        # Go back
        if len(navigation_history[user_id]) > 1:
            navigation_history[user_id].pop()
        current = navigation_history[user_id][-1]
    elif callback_data.startswith("nav_"):
        # Navigate to node
        node_id = callback_data[4:]  # Remove "nav_"
        navigation_history[user_id].append(node_id)
        current = node_id
    else:
        current = "root"

    # Generate message and keyboard
    if current == "root":
        message = get_welcome_message()
        keyboard = get_main_navigation_keyboard()
    else:
        message = get_node_message(current)
        node = PROJECT_STRUCTURE.get(current, {})
        if node.get("children"):
            keyboard = get_navigation_keyboard(current)
        else:
            # End node — show back button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="nav_back")],
                [InlineKeyboardButton("🏠 Juno's Path", callback_data="nav_root")]
            ])

    try:
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        # If edit failed, send new message
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


async def start_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /navigate — start navigation."""
    user_id = update.effective_user.id
    navigation_history[user_id] = ["root"]

    await update.message.reply_text(
        text=get_welcome_message(),
        parse_mode="Markdown",
        reply_markup=get_main_navigation_keyboard()
    )


# ═══════════════════════════════════════════════════════════════════════════════
#                              INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def register_navigation_handlers(application):
    """Registers navigation handlers in Telegram application."""
    from telegram.ext import CommandHandler

    # Command /navigate
    application.add_handler(CommandHandler("navigate", start_navigation))
    application.add_handler(CommandHandler("nav", start_navigation))
    application.add_handler(CommandHandler("path", start_navigation))

    # Navigation button handler
    application.add_handler(CallbackQueryHandler(handle_navigation, pattern="^nav_"))


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("HIERARCHY NOTHING_NOTHING_无_金元Ɉ")
    print("=" * 60)
    print()
    print(get_welcome_message().replace("*", "").replace("_", "").replace("`", ""))
    print()
    print("To integrate with bot add:")
    print("  from junona_navigation import register_navigation_handlers")
    print("  register_navigation_handlers(application)")
