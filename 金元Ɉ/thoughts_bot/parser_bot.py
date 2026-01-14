#!/usr/bin/env python3
"""
金元Ɉ Thoughts Parser Bot
Парсер мыслей Montana с inline клавиатурой и поиском.

@mylifethoughtsbot
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BOT_TOKEN = "REDACTED_TOKEN_2"
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "parsed"
DATA_DIR = Path(__file__).parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"
INDEX_FILE = DATA_DIR / "thoughts_index.json"

AUTHOR = "Алик Хачатрян"
TAG = "#Благаявесть"

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Entry:
    """Single thought entry."""
    timestamp: Optional[str]
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        header = f"## {self.timestamp} | {self.title}" if self.timestamp else f"## Без метки | {self.title}"
        tags_str = " ".join(self.tags) if self.tags else ""
        content = self.content
        if tags_str and tags_str not in content:
            content = f"{content}\n\n{tags_str}"
        return f"{header}\n\n{content}\n\n---\n"


@dataclass
class Post:
    """Collection of entries forming a post."""
    number: int
    title: str
    entries: list[Entry] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    source: str = "Telegram"
    published: bool = False

    def to_markdown(self) -> str:
        period = f"{self.start_time} — {self.end_time}" if self.start_time and self.end_time else datetime.now().strftime("%d.%m.%Y")

        md = f"# {self.number}. {self.title}\n\n"
        md += f"**Автор:** {AUTHOR}\n"
        md += f"**Период:** {period}\n"
        md += f"**Тег:** {TAG}\n"
        md += f"**Источник:** {self.source}\n\n"
        md += "---\n\n"

        for entry in self.entries:
            md += entry.to_markdown()

        return md

    def filename(self) -> str:
        safe_title = re.sub(r'[^\w\-]', '_', self.title.lower())
        return f"{self.number}_{safe_title}.md"


# ═══════════════════════════════════════════════════════════════════════════════
# STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

class Storage:
    """Persistent storage for sessions and index."""

    def __init__(self):
        self.sessions: dict[int, dict] = {}
        self.index: dict[str, list] = {"posts": [], "entries": []}
        self._load()

    def _load(self):
        if SESSIONS_FILE.exists():
            try:
                data = json.loads(SESSIONS_FILE.read_text())
                self.sessions = {int(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")

        if INDEX_FILE.exists():
            try:
                self.index = json.loads(INDEX_FILE.read_text())
            except Exception as e:
                logger.error(f"Failed to load index: {e}")

    def save(self):
        SESSIONS_FILE.write_text(json.dumps(self.sessions, ensure_ascii=False, indent=2))
        INDEX_FILE.write_text(json.dumps(self.index, ensure_ascii=False, indent=2))

    def get_session(self, user_id: int) -> dict:
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                "active": False,
                "post": None,
            }
        return self.sessions[user_id]

    def get_post(self, user_id: int) -> Optional[Post]:
        session = self.get_session(user_id)
        if session["post"]:
            p = session["post"]
            entries = [Entry(**e) for e in p.get("entries", [])]
            return Post(
                number=p["number"],
                title=p["title"],
                entries=entries,
                start_time=p.get("start_time"),
                end_time=p.get("end_time"),
                source=p.get("source", "Telegram"),
                published=p.get("published", False)
            )
        return None

    def set_post(self, user_id: int, post: Optional[Post]):
        session = self.get_session(user_id)
        if post:
            session["post"] = {
                "number": post.number,
                "title": post.title,
                "entries": [asdict(e) for e in post.entries],
                "start_time": post.start_time,
                "end_time": post.end_time,
                "source": post.source,
                "published": post.published,
            }
            session["active"] = True
        else:
            session["post"] = None
            session["active"] = False
        self.save()

    def add_to_index(self, post: Post, filepath: str):
        """Add post to searchable index."""
        post_entry = {
            "number": post.number,
            "title": post.title,
            "filepath": filepath,
            "entry_count": len(post.entries),
            "created": datetime.now().isoformat(),
        }
        self.index["posts"].append(post_entry)

        for entry in post.entries:
            self.index["entries"].append({
                "post_number": post.number,
                "title": entry.title,
                "content_preview": entry.content[:200],
                "timestamp": entry.timestamp,
                "tags": entry.tags,
            })
        self.save()

    def search(self, query: str) -> list[dict]:
        """Search entries by query."""
        query_lower = query.lower()
        results = []

        for entry in self.index.get("entries", []):
            if (query_lower in entry["title"].lower() or
                query_lower in entry.get("content_preview", "").lower() or
                any(query_lower in tag.lower() for tag in entry.get("tags", []))):
                results.append(entry)

        return results[:20]  # Limit results


storage = Storage()


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════

def main_keyboard() -> ReplyKeyboardMarkup:
    """Main menu keyboard."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Новый пост"), KeyboardButton("🔍 Поиск")],
            [KeyboardButton("📊 Статус"), KeyboardButton("📂 Список постов")],
        ],
        resize_keyboard=True,
    )


def post_keyboard(entry_count: int = 0) -> InlineKeyboardMarkup:
    """Keyboard for active post management."""
    buttons = [
        [
            InlineKeyboardButton("👁 Превью", callback_data="preview"),
            InlineKeyboardButton(f"📊 Записей: {entry_count}", callback_data="status"),
        ],
        [
            InlineKeyboardButton("💾 Сохранить", callback_data="save"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def entry_keyboard(entry_idx: int) -> InlineKeyboardMarkup:
    """Keyboard for managing single entry."""
    buttons = [
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{entry_idx}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{entry_idx}"),
        ],
        [
            InlineKeyboardButton("🏷 Добавить тег", callback_data=f"tag_{entry_idx}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ Нет", callback_data="cancel_action"),
        ]
    ])


def search_result_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for search results."""
    buttons = []
    for i, r in enumerate(results[:10]):
        title = r["title"][:30] + "..." if len(r["title"]) > 30 else r["title"]
        buttons.append([InlineKeyboardButton(
            f"#{r['post_number']}: {title}",
            callback_data=f"view_{r['post_number']}_{i}"
        )])
    return InlineKeyboardMarkup(buttons)


def posts_list_keyboard(posts: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for posts list."""
    buttons = []
    for p in posts[-10:]:  # Last 10 posts
        title = p["title"][:25] + "..." if len(p["title"]) > 25 else p["title"]
        buttons.append([InlineKeyboardButton(
            f"#{p['number']}: {title} ({p['entry_count']} записей)",
            callback_data=f"open_{p['number']}"
        )])
    buttons.append([InlineKeyboardButton("📝 Новый пост", callback_data="new_post")])
    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "金元Ɉ Thoughts Parser\n\n"
        "Парсер мыслей в формат Montana.\n"
        "Пересылай сообщения из канала — бот соберёт их в markdown.\n\n"
        "Команды:\n"
        "/new — начать новый пост\n"
        "/search <запрос> — поиск в записях\n"
        "/list — список постов\n"
        "/status — текущее состояние",
        reply_markup=main_keyboard()
    )


async def new_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start new post flow."""
    user_id = update.effective_user.id

    # Check if there's active post
    post = storage.get_post(user_id)
    if post:
        await update.message.reply_text(
            f"Есть активный пост: #{post.number} {post.title}\n"
            f"Записей: {len(post.entries)}\n\n"
            "Сначала сохрани или отмени его.",
            reply_markup=post_keyboard(len(post.entries))
        )
        return

    await update.message.reply_text(
        "Введи номер и название поста:\n"
        "Формат: <номер> <название>\n\n"
        "Пример: 165 Пробуждение"
    )
    context.user_data["awaiting_post_info"] = True


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Handle button presses
    if text == "📝 Новый пост":
        await new_post_start(update, context)
        return
    elif text == "🔍 Поиск":
        await update.message.reply_text("Введи поисковый запрос после /search\nПример: /search время")
        return
    elif text == "📊 Статус":
        await status(update, context)
        return
    elif text == "📂 Список постов":
        await list_posts(update, context)
        return

    # Awaiting post info?
    if context.user_data.get("awaiting_post_info"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("Формат: <номер> <название>\nПример: 165 Пробуждение")
            return

        try:
            number = int(parts[0])
        except ValueError:
            await update.message.reply_text("Номер должен быть числом.")
            return

        title = parts[1]
        post = Post(number=number, title=title)
        storage.set_post(user_id, post)
        context.user_data["awaiting_post_info"] = False

        await update.message.reply_text(
            f"✅ Пост создан: #{number} {title}\n\n"
            "Теперь пересылай сообщения из канала.\n"
            "Каждое сообщение станет записью.",
            reply_markup=post_keyboard(0)
        )
        return

    # Active post - add entry
    post = storage.get_post(user_id)
    if post:
        await add_entry(update, context, post, text)
    else:
        await update.message.reply_text(
            "Нет активного поста.\n"
            "Нажми «📝 Новый пост» или /new",
            reply_markup=main_keyboard()
        )


async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, post: Post, text: str) -> None:
    """Add entry to active post."""
    user_id = update.effective_user.id
    msg = update.message

    # Extract timestamp from forward
    timestamp = None
    if msg.forward_date:
        timestamp = msg.forward_date.strftime("%H%M")
        dt_str = msg.forward_date.strftime("%d.%m.%Y %H:%M")
        if not post.start_time or dt_str < post.start_time:
            post.start_time = dt_str
        if not post.end_time or dt_str > post.end_time:
            post.end_time = dt_str

    # Parse entry
    lines = text.split("\n")
    first_line = lines[0].strip()

    # Extract tags
    tags = re.findall(r'#\w+', text)

    # Title is first line if short, otherwise first words
    if len(first_line) < 80:
        title = first_line
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else first_line
    else:
        words = first_line.split()[:6]
        title = " ".join(words)
        if len(words) == 6:
            title += "..."
        content = text

    entry = Entry(
        timestamp=timestamp,
        title=title,
        content=content,
        tags=tags
    )

    post.entries.append(entry)
    storage.set_post(user_id, post)

    entry_idx = len(post.entries) - 1
    ts_display = timestamp if timestamp else "без метки"

    await update.message.reply_text(
        f"✅ Запись #{entry_idx + 1} добавлена\n\n"
        f"⏰ {ts_display}\n"
        f"📌 {title[:50]}...\n"
        f"🏷 {' '.join(tags) if tags else 'нет тегов'}",
        reply_markup=entry_keyboard(entry_idx)
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current status."""
    user_id = update.effective_user.id
    post = storage.get_post(user_id)

    if not post:
        await update.message.reply_text(
            "Нет активного поста.\n"
            "Нажми «📝 Новый пост» для начала.",
            reply_markup=main_keyboard()
        )
        return

    entries_list = "\n".join([
        f"  {i+1}. {e.timestamp or '----'} | {e.title[:40]}..."
        for i, e in enumerate(post.entries[-5:])
    ])

    await update.message.reply_text(
        f"📊 Статус\n\n"
        f"Пост: #{post.number} {post.title}\n"
        f"Записей: {len(post.entries)}\n"
        f"Период: {post.start_time or '?'} — {post.end_time or '?'}\n\n"
        f"Последние записи:\n{entries_list if entries_list else '(пусто)'}",
        reply_markup=post_keyboard(len(post.entries))
    )


async def list_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List saved posts."""
    posts = storage.index.get("posts", [])

    if not posts:
        # Scan directory
        for f in OUTPUT_DIR.glob("*.md"):
            match = re.match(r"(\d+)_(.+)\.md", f.name)
            if match:
                posts.append({
                    "number": int(match.group(1)),
                    "title": match.group(2).replace("_", " "),
                    "filepath": str(f),
                    "entry_count": "?",
                })

    if not posts:
        await update.message.reply_text(
            "Нет сохранённых постов.\n"
            "Нажми «📝 Новый пост» для начала.",
            reply_markup=main_keyboard()
        )
        return

    await update.message.reply_text(
        "📂 Список постов\n\n"
        "Выбери пост для просмотра:",
        reply_markup=posts_list_keyboard(posts)
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search in entries."""
    if not context.args:
        await update.message.reply_text("Использование: /search <запрос>\nПример: /search время")
        return

    query = " ".join(context.args)
    results = storage.search(query)

    # Also search in files
    for f in OUTPUT_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8").lower()
        if query.lower() in content:
            match = re.match(r"(\d+)_(.+)\.md", f.name)
            if match:
                # Check if already in results
                if not any(r.get("post_number") == int(match.group(1)) for r in results):
                    results.append({
                        "post_number": int(match.group(1)),
                        "title": f"Файл: {f.name}",
                        "content_preview": f"Найдено в файле",
                        "timestamp": None,
                        "tags": [],
                    })

    if not results:
        await update.message.reply_text(f"По запросу «{query}» ничего не найдено.")
        return

    await update.message.reply_text(
        f"🔍 Результаты поиска: «{query}»\n"
        f"Найдено: {len(results)}",
        reply_markup=search_result_keyboard(results)
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline buttons."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if data == "preview":
        post = storage.get_post(user_id)
        if post and post.entries:
            md = post.to_markdown()
            if len(md) > 3900:
                md = md[:3900] + "\n\n... (обрезано для превью)"
            await query.message.reply_text(f"```\n{md}\n```", parse_mode="Markdown")
        else:
            await query.message.reply_text("Пост пуст.")

    elif data == "save":
        post = storage.get_post(user_id)
        if post and post.entries:
            await query.message.reply_text(
                f"Сохранить пост #{post.number} {post.title}?\n"
                f"Записей: {len(post.entries)}",
                reply_markup=confirm_keyboard("save")
            )
        else:
            await query.message.reply_text("Нечего сохранять.")

    elif data == "confirm_save":
        post = storage.get_post(user_id)
        if post:
            md = post.to_markdown()
            filepath = OUTPUT_DIR / post.filename()
            filepath.write_text(md, encoding="utf-8")
            storage.add_to_index(post, str(filepath))
            storage.set_post(user_id, None)

            await query.message.reply_text(
                f"✅ Сохранено!\n\n"
                f"📄 {filepath.name}\n"
                f"📊 Записей: {len(post.entries)}\n"
                f"📁 {filepath}",
                reply_markup=main_keyboard()
            )

    elif data == "cancel":
        post = storage.get_post(user_id)
        if post:
            await query.message.reply_text(
                f"Отменить пост #{post.number}?\n"
                f"Записей будет потеряно: {len(post.entries)}",
                reply_markup=confirm_keyboard("cancel")
            )

    elif data == "confirm_cancel":
        storage.set_post(user_id, None)
        await query.message.reply_text(
            "❌ Пост отменён.",
            reply_markup=main_keyboard()
        )

    elif data == "cancel_action":
        await query.message.reply_text("Действие отменено.")

    elif data == "status":
        post = storage.get_post(user_id)
        if post:
            await query.message.reply_text(
                f"📊 Пост #{post.number}: {post.title}\n"
                f"Записей: {len(post.entries)}"
            )

    elif data == "new_post":
        context.user_data["awaiting_post_info"] = True
        await query.message.reply_text(
            "Введи номер и название поста:\n"
            "Формат: <номер> <название>\n\n"
            "Пример: 177 Новое начало"
        )

    elif data.startswith("delete_"):
        idx = int(data.split("_")[1])
        post = storage.get_post(user_id)
        if post and 0 <= idx < len(post.entries):
            entry = post.entries.pop(idx)
            storage.set_post(user_id, post)
            await query.message.reply_text(
                f"🗑 Запись удалена: {entry.title[:50]}...",
                reply_markup=post_keyboard(len(post.entries))
            )

    elif data.startswith("open_"):
        post_num = int(data.split("_")[1])
        # Find and display post
        for f in OUTPUT_DIR.glob(f"{post_num}_*.md"):
            content = f.read_text(encoding="utf-8")
            if len(content) > 3900:
                content = content[:3900] + "\n\n... (обрезано)"
            await query.message.reply_text(f"```\n{content}\n```", parse_mode="Markdown")
            break

    elif data.startswith("view_"):
        parts = data.split("_")
        post_num = int(parts[1])
        for f in OUTPUT_DIR.glob(f"{post_num}_*.md"):
            content = f.read_text(encoding="utf-8")
            if len(content) > 3900:
                content = content[:3900] + "\n\n..."
            await query.message.reply_text(f"```\n{content}\n```", parse_mode="Markdown")
            break


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Run the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("new", new_post_start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("list", list_posts))
    app.add_handler(CommandHandler("search", search))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("金元Ɉ Thoughts Parser Bot starting...")
    logger.info(f"Output dir: {OUTPUT_DIR}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
