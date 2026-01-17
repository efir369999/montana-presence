# junona_navigation.py
# 无_Nothing_无_金元Ɉ 层次结构导航
# 朱诺引导：创世 → 哲学 → 代码

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from pathlib import Path
import os

# ═══════════════════════════════════════════════════════════════════════════════
#                              项目结构
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_STRUCTURE = {
    "root": {
        "name": "无_Nothing_无_金元Ɉ",
        "emoji": "♾️",
        "description": "根。协议作者。",
        "children": ["montana"]
    },
    "montana": {
        "name": "蒙大拿_Montana_蒙大拿",
        "emoji": "🏔️",
        "description": "蒙大拿协议——时间即共识。",
        "path": "蒙大拿_Montana_蒙大拿",
        "children": ["genesis", "council", "philosophy", "cognitive", "protocol", "crypto", "network", "economics"]
    },

    # ═══════════════════════════════════════════════════════════════════════════
    #                              沉浸路径
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. 创世——一切的开始
    "genesis": {
        "name": "创世_Genesis_创世",
        "emoji": "🌅",
        "description": "开始。创造历史。认知创世。",
        "path": "蒙大拿_Montana_蒙大拿/创世_Genesis_创世",
        "order": 1,
        "stage": "开始",
        "files": [
            "COGNITIVE_GENESIS_2026-01-09.md",
            "GENESIS_PROOF_2026-01-09.md",
            "GENESIS_SIGNATURE.md",
            "README.md"
        ],
        "children": []
    },

    # 2. 理事会——治理（创世之后）
    "council": {
        "name": "理事会_Council_理事会",
        "emoji": "👥",
        "description": "蒙大拿守护理事会。AI模型作为顾问。",
        "path": "蒙大拿_Montana_蒙大拿/理事会_Council_理事会",
        "order": 2,
        "stage": "治理",
        "files": [
            "SECURITY_COUNCIL_MEETING.md",
            "JUNONA_WHITEPAPER.md",
            "JOIN_COUNCIL_PROMPT.md"
        ],
        "children": ["anthropic", "google", "openai", "xai", "cursor"]
    },

    # 3. 哲学——理解的第一步
    "philosophy": {
        "name": "哲学（哲学）",
        "emoji": "📚",
        "description": "蒙大拿哲学。信任、身份、存在。",
        "path": "蒙大拿_Montana_蒙大拿/中文/哲学",
        "order": 3,
        "stage": "哲学",
        "files": [
            "哲学白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 4. 认知系统
    "cognitive": {
        "name": "认知（认知）",
        "emoji": "🧠",
        "description": "认知签名。通过思想的身份。",
        "path": "蒙大拿_Montana_蒙大拿/中文/认知",
        "order": 4,
        "stage": "哲学",
        "files": [
            "认知白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 5. ACP协议——代码开始
    "protocol": {
        "name": "协议（ACP协议）",
        "emoji": "📋",
        "description": "异步共识协议。时间即共识。",
        "path": "蒙大拿_Montana_蒙大拿/中文/协议",
        "order": 5,
        "stage": "代码",
        "files": [
            "ACP白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 6. 密码学
    "crypto": {
        "name": "加密（密码学）",
        "emoji": "🔐",
        "description": "后量子密码学。SHA3、ML-DSA。",
        "path": "蒙大拿_Montana_蒙大拿/中文/加密",
        "order": 6,
        "stage": "代码",
        "files": [
            "加密白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 7. P2P网络
    "network": {
        "name": "网络（P2P网络）",
        "emoji": "🌐",
        "description": "P2P网络。日蚀保护。Gossip协议。",
        "path": "蒙大拿_Montana_蒙大拿/中文/网络",
        "order": 7,
        "stage": "代码",
        "files": [
            "P2P白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 8. 经济
    "economics": {
        "name": "经济（经济学）",
        "emoji": "💰",
        "description": "代币经济学 金元Ɉ。发行。分配。",
        "path": "蒙大拿_Montana_蒙大拿/中文/经济",
        "order": 8,
        "stage": "代码",
        "files": [
            "经济白皮书.md",
            "src/lib.rs"
        ],
        "children": []
    },

    # 理事会子部分
    "anthropic": {
        "name": "Anthropic (Claude)",
        "emoji": "🟤",
        "path": "蒙大拿_Montana_蒙大拿/理事会_Council_理事会/Anthropic",
        "children": []
    },
    "google": {
        "name": "Google (Gemini)",
        "emoji": "🔵",
        "path": "蒙大拿_Montana_蒙大拿/理事会_Council_理事会/Google",
        "children": []
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "emoji": "🟢",
        "path": "蒙大拿_Montana_蒙大拿/理事会_Council_理事会/OpenAI",
        "children": []
    },
    "xai": {
        "name": "xAI (Grok)",
        "emoji": "⚪",
        "path": "蒙大拿_Montana_蒙大拿/理事会_Council_理事会/xAI",
        "children": []
    },
    "cursor": {
        "name": "Cursor (Composer)",
        "emoji": "🟣",
        "path": "蒙大拿_Montana_蒙大拿/理事会_Council_理事会/Cursor",
        "children": []
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
#                              键盘
# ═══════════════════════════════════════════════════════════════════════════════

def get_navigation_keyboard(current_node: str = "root") -> InlineKeyboardMarkup:
    """为当前节点生成导航键盘。"""
    node = PROJECT_STRUCTURE.get(current_node, PROJECT_STRUCTURE["root"])
    buttons = []

    # 子元素按钮
    children = node.get("children", [])
    for child_id in children:
        child = PROJECT_STRUCTURE.get(child_id, {})
        emoji = child.get("emoji", "📁")
        name = child.get("name", child_id)
        stage = child.get("stage", "")

        # 添加阶段标签
        label = f"{emoji} {name}"
        if stage:
            label = f"{emoji} {name}"

        buttons.append([InlineKeyboardButton(label, callback_data=f"nav_{child_id}")])

    # 如果不在根目录，显示"返回"按钮
    if current_node != "root":
        buttons.append([InlineKeyboardButton("⬅️ 返回", callback_data="nav_back")])

    # 主菜单按钮
    buttons.append([InlineKeyboardButton("🏠 菜单", callback_data="main_menu")])

    return InlineKeyboardMarkup(buttons)


def get_main_navigation_keyboard() -> InlineKeyboardMarkup:
    """主导航菜单——朱诺的沉浸路径。"""
    buttons = [
        # 标题
        [InlineKeyboardButton("═══ 朱诺之路 ═══", callback_data="nav_info")],

        # 1. 创世——开始
        [InlineKeyboardButton("🌅 创世——开始", callback_data="nav_genesis")],

        # 2. 理事会——创世之后
        [InlineKeyboardButton("👥 理事会——治理", callback_data="nav_council")],

        # 分隔符
        [InlineKeyboardButton("─── 哲学 ───", callback_data="nav_info")],

        # 3-4. 哲学
        [InlineKeyboardButton("📚 哲学", callback_data="nav_philosophy"),
         InlineKeyboardButton("🧠 认知", callback_data="nav_cognitive")],

        # 分隔符
        [InlineKeyboardButton("─── 代码 ───", callback_data="nav_info")],

        # 5-6. 协议和密码学
        [InlineKeyboardButton("📋 ACP协议", callback_data="nav_protocol"),
         InlineKeyboardButton("🔐 密码学", callback_data="nav_crypto")],

        # 7-8. 网络和经济
        [InlineKeyboardButton("🌐 P2P网络", callback_data="nav_network"),
         InlineKeyboardButton("💰 经济", callback_data="nav_economics")],

        # 主菜单
        [InlineKeyboardButton("🏠 主菜单", callback_data="main_menu")]
    ]

    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════════════════════════════════════════
#                              消息
# ═══════════════════════════════════════════════════════════════════════════════

def get_node_message(node_id: str) -> str:
    """为节点生成消息。"""
    node = PROJECT_STRUCTURE.get(node_id, {})

    emoji = node.get("emoji", "📁")
    name = node.get("name", node_id)
    description = node.get("description", "")
    path = node.get("path", "")
    stage = node.get("stage", "")
    files = node.get("files", [])
    order = node.get("order", 0)

    # 构建消息
    message = f"{emoji} *{name}*\n\n"

    if stage:
        message += f"📍 阶段：*{stage}*\n"

    if order:
        message += f"🔢 顺序：{order}/8\n"

    if description:
        message += f"\n{description}\n"

    if path:
        message += f"\n📂 `{path}/`\n"

    if files:
        message += f"\n📄 *文件：*\n"
        for f in files[:5]:  # 显示最多5个文件
            message += f"  • `{f}`\n"
        if len(files) > 5:
            message += f"  • _...还有 {len(files) - 5} 个_\n"

    return message


def get_welcome_message() -> str:
    """导航欢迎消息。"""
    return """♾️ *无\_Nothing\_无\_金元Ɉ*

欢迎来到蒙大拿协议导航。

*朱诺的沉浸路径：*

1️⃣ 🌅 *创世*——开始
2️⃣ 👥 *理事会*——治理

─── 哲学 ───
3️⃣ 📚 *哲学*——信任、身份、存在
4️⃣ 🧠 *认知*——思想签名

─── 代码 ───
5️⃣ 📋 *ACP协议*——时间即共识
6️⃣ 🔐 *密码学*——SHA3、ML-DSA
7️⃣ 🌐 *P2P网络*——日蚀保护
8️⃣ 💰 *经济*——代币 金元Ɉ

_选择一个部分沉浸：_
"""


# ═══════════════════════════════════════════════════════════════════════════════
#                              处理器
# ═══════════════════════════════════════════════════════════════════════════════

# 每个用户的导航历史
navigation_history = {}

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理导航按钮点击。"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data

    # 初始化用户历史
    if user_id not in navigation_history:
        navigation_history[user_id] = ["root"]

    if callback_data == "nav_info":
        # 信息按钮——不做任何事
        return

    if callback_data == "nav_back":
        # 返回
        if len(navigation_history[user_id]) > 1:
            navigation_history[user_id].pop()
        current = navigation_history[user_id][-1]
    elif callback_data.startswith("nav_"):
        # 导航到节点
        node_id = callback_data[4:]  # 移除 "nav_"
        navigation_history[user_id].append(node_id)
        current = node_id
    else:
        current = "root"

    # 生成消息和键盘
    if current == "root":
        message = get_welcome_message()
        keyboard = get_main_navigation_keyboard()
    else:
        message = get_node_message(current)
        node = PROJECT_STRUCTURE.get(current, {})
        if node.get("children"):
            keyboard = get_navigation_keyboard(current)
        else:
            # 终端节点——显示返回按钮
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ 返回", callback_data="nav_back")],
                [InlineKeyboardButton("🏠 朱诺之路", callback_data="nav_root")]
            ])

    try:
        await query.edit_message_text(
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        # 如果编辑失败，发送新消息
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


async def start_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """命令 /navigate——启动导航。"""
    user_id = update.effective_user.id
    navigation_history[user_id] = ["root"]

    await update.message.reply_text(
        text=get_welcome_message(),
        parse_mode="Markdown",
        reply_markup=get_main_navigation_keyboard()
    )


# ═══════════════════════════════════════════════════════════════════════════════
#                              集成
# ═══════════════════════════════════════════════════════════════════════════════

def register_navigation_handlers(application):
    """在Telegram应用程序中注册导航处理器。"""
    from telegram.ext import CommandHandler

    # 命令 /navigate
    application.add_handler(CommandHandler("navigate", start_navigation))
    application.add_handler(CommandHandler("nav", start_navigation))
    application.add_handler(CommandHandler("路径", start_navigation))

    # 导航按钮处理器
    application.add_handler(CallbackQueryHandler(handle_navigation, pattern="^nav_"))


# ═══════════════════════════════════════════════════════════════════════════════
#                              测试
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("层次结构 无_NOTHING_无_金元Ɉ")
    print("=" * 60)
    print()
    print(get_welcome_message().replace("*", "").replace("_", "").replace("`", ""))
    print()
    print("要与机器人集成，请添加：")
    print("  from junona_navigation import register_navigation_handlers")
    print("  register_navigation_handlers(application)")
