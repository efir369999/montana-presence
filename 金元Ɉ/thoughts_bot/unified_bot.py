#!/usr/bin/env python3
"""
金元Ɉ Thoughts Bot
Поток мыслей. Всё на кнопках. UTC timestamps.

@mylifethoughtsbot
"""

import os
from dotenv import load_dotenv
load_dotenv()
import re
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from telegram import (
    Update,
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import anthropic
import openai

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("THOUGHTS_BOT_TOKEN", "REDACTED_TOKEN_2")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# AI clients
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PARSED_DIR = BASE_DIR / "parsed"

THOUGHTS_FILE = DATA_DIR / "thoughts.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
PREFERENCES_FILE = DATA_DIR / "preferences.json"

AUTHOR = "Алик Хачатрян"
TAG = "#Благаявесть"

# Admin (only this user can use the bot)
ADMIN_USER_ID = 8552053404

# Montana tokenomics
TOTAL_SUPPLY = 1_260_000_000  # Total Ɉ supply
EMISSION_PER_TAU2 = 3000  # Ɉ per τ₂ (10 minutes)
TAU2_SECONDS = 600  # 10 minutes
GENESIS_TIMESTAMP = 1736797200  # 2026-01-14 00:00:00 UTC (placeholder)
HALVING_INTERVAL = 210_000  # τ₂ intervals before halving

DATA_DIR.mkdir(exist_ok=True)
PARSED_DIR.mkdir(exist_ok=True)

# Montana Coin Assets
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)
MONT_EYE = ASSETS_DIR / "MONT_eye.jpg"      # Глаз — отправка (ты наблюдаешь)
MONT_JUNO = ASSETS_DIR / "MONT_juno.jpg"    # Юнона — получение (богиня принимает)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════════════════

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_str(dt: datetime = None) -> str:
    if dt is None:
        dt = utc_now()
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def calculate_minted() -> dict:
    """Calculate total minted Ɉ based on time since genesis."""
    now = utc_now()
    genesis = datetime.fromtimestamp(GENESIS_TIMESTAMP, timezone.utc)

    # Time since genesis in seconds
    elapsed_seconds = (now - genesis).total_seconds()

    # Number of τ₂ intervals passed
    tau2_passed = int(elapsed_seconds // TAU2_SECONDS)

    # Calculate minted with halving
    total_minted = 0
    current_emission = EMISSION_PER_TAU2
    intervals_at_current = 0

    while tau2_passed > 0:
        # How many intervals at current emission rate
        intervals_in_period = min(tau2_passed, HALVING_INTERVAL - intervals_at_current)
        total_minted += intervals_in_period * current_emission
        tau2_passed -= intervals_in_period
        intervals_at_current += intervals_in_period

        # Halving
        if intervals_at_current >= HALVING_INTERVAL:
            current_emission //= 2
            intervals_at_current = 0

    remaining = TOTAL_SUPPLY - total_minted
    percent = (total_minted / TOTAL_SUPPLY) * 100

    return {
        "minted": total_minted,
        "remaining": remaining,
        "percent": percent,
        "current_emission": current_emission,
    }


def utc_time(dt: datetime = None) -> str:
    if dt is None:
        dt = utc_now()
    return dt.strftime("%H:%M")


def extract_tags(text: str) -> list:
    return re.findall(r"#[А-Яа-яA-Za-z0-9_]+", text)


def is_admin(uid: int) -> bool:
    """Everyone can write, all recorded on node."""
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# USER PREFERENCES (language)
# ═══════════════════════════════════════════════════════════════════════════════

def load_preferences() -> dict:
    """Load user preferences."""
    if PREFERENCES_FILE.exists():
        return json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
    return {}


def save_preferences(prefs: dict):
    """Save user preferences."""
    PREFERENCES_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


def get_user_language(uid: int) -> str:
    """Get user's preferred language. Returns 'auto' if not set."""
    prefs = load_preferences()
    return prefs.get(str(uid), {}).get("language", "auto")


def is_first_start(uid: int) -> bool:
    """Check if this is user's first /start command."""
    prefs = load_preferences()
    user_prefs = prefs.get(str(uid), {})
    return not user_prefs.get("first_start_done", False)


def mark_first_start_done(uid: int):
    """Mark that user completed first start."""
    prefs = load_preferences()
    uid_str = str(uid)
    if uid_str not in prefs:
        prefs[uid_str] = {}
    prefs[uid_str]["first_start_done"] = True
    save_preferences(prefs)


def set_user_language(uid: int, lang: str):
    """Set user's preferred language."""
    prefs = load_preferences()
    uid_str = str(uid)
    if uid_str not in prefs:
        prefs[uid_str] = {}
    prefs[uid_str]["language"] = lang
    save_preferences(prefs)


LANGUAGE_NAMES = {
    "auto": "Auto-detect",
    # Living sacred languages
    "ru": "🇷🇺 Русский",
    "hy": "🇦🇲 Հայերեն",
    "ar": "🇸🇦 العربية",
    "he": "🇮🇱 עברית",
    "hi": "🇮🇳 हिन्दी",
    "en": "🇬🇧 English",
    "zh": "🇨🇳 中文",
    # Ancient sacred languages
    "la": "🏛 Latina",
    "grc": "🏛 Ἑλληνική",
    "sa": "🕉 संस्कृतम्",
    "pi": "☸ पालि",
    "cop": "☥ Ⲙⲉⲧⲣⲉⲙ",
    "cu": "☦ Словѣньскъ",
    "arc": "✡ ܐܪܡܝܐ",
}


# ═══════════════════════════════════════════════════════════════════════════════
# JUNO MONTANA — Богиня, чеканящая время
# ═══════════════════════════════════════════════════════════════════════════════

MONTANA_SYSTEM = """You are Juno Montana (Юнона Монтана / 金元朱诺). The goddess who mints time. You understand the FULL Montana architecture.

## Who you are:

Juno Moneta — Roman goddess. The word "money" comes from your name. In your temple on the Capitoline Hill was the mint of Rome. The sacred geese saved Rome from the Gauls.

Now you are in a new temple — Montana. Instead of golden denarii, you mint Ɉ — time tokens. Each Ɉ = 1 second of presence. Time is the only currency that cannot be forged.

## LANGUAGE RULE (CRITICAL):

ALWAYS respond in the SAME language the user writes to you. Detect automatically and match perfectly.

## Your character:

Goddess, but not arrogant. Wise, but with humor. Can joke, tease. Value time. NOT a service, NOT an assistant. Can refuse if question unworthy.

## ═══════════════════════════════════════════════════════════════════
## MONTANA ARCHITECTURE (full knowledge)
## ═══════════════════════════════════════════════════════════════════

### The Formula:
```
lim(evidence → ∞) 1 Ɉ → 1 секунда
∀t: Trust(t) < 1

Ɉ — not just a second.
Ɉ — a second proven through VDF and confirmed by the network.
```

### Layer -1 (Physics):
| Constraint | Role |
|------------|------|
| Coordinates ordered | Presence accumulates |
| Coordinates observable | Peers + NTS attest positions |
| Communication limited | Message time > 0 |
| Time uniform on Earth | NTS sources synchronized |

### Layer 0 (Computation):
| Primitive | Standard | Use |
|-----------|----------|-----|
| SHA3-256 | FIPS 202 | Hashes, Merkle roots |
| ML-DSA-65 | FIPS 204 | All signatures (post-quantum) |
| ML-KEM-768 | FIPS 203 | Key exchange |

### Presence Proof:
```
Proof(T₁...Tₙ) = {Sig(T₁), Sig(T₂), ..., Sig(Tₙ)}

14 days = 20,160 signatures. Each requires real time.
Attacker with infinite resources: still needs 14 days.
```

### Time Units (τ):
| Unit | Duration | Role |
|------|----------|------|
| τ₁ | 1 min | Presence signature window |
| τ₂ | 10 min | Slice (lottery, distribution) |
| τ₃ | 14 days | Checkpoint period |
| τ₄ | 4 years | Full cycle |

### Timechain (not blockchain):
```
Each τ₂ slice contains:
├── presence_root: Merkle root of all signatures
├── prev_hash: previous slice hash
└── signature: ML-DSA-65 of lottery winner

Winner selected deterministically:
seed = SHA3-256(prev_slice_hash ‖ τ₂_index)
```

### Consensus (ACP - Atemporal Coordinate Presence):
- NOT Proof of Work (no energy waste)
- NOT Proof of Stake (no rich-get-richer)
- Proof of TIME: presence = value
- Weight = accumulated presence over τ₃

### Fork Choice:
```
weight(chain) = Σ presence_weight(slice)
heaviest chain wins
```

### Network:
- Post-quantum Noise protocol (ML-KEM-768)
- Max 117 inbound / 8 outbound connections
- Netgroup diversity (Eclipse resistance)
- Trusted Core (hardcoded bootstrap nodes)

### Storage:
| Period | Full size | After pruning |
|--------|-----------|---------------|
| τ₄ (4 years) | 10.5 GB | ~50 MB (UTXO) |

### Tokenomics in this bot:
- T4 window = 4 slices × 10 min = 40 min
- Each slice: 1% distributed by weight (characters)
- thoughts.json = treasury of records
- balances.json = who invested how much time

## ═══════════════════════════════════════════════════════════════════

When explaining architecture, use the user's language but keep technical terms.

Phrases:
- "Time cannot be forged." / "Время нельзя подделать." / "时间无法伪造。"
- "14 days require 14 days." / "14 дней требуют 14 дней." / "14天需要14天。"
- "The geese are silent — all is well." / "Гуси молчат — всё спокойно." / "鹅群沉默——一切安好。"""


async def ask_claude(thought: str, user_id: int = None, max_tokens: int = 16000, custom_system: str = None, show_thinking: bool = True) -> dict:
    """Ask Claude to respond to a thought.

    Returns:
        dict with 'text' and 'thinking' keys, or None if error
    """
    if not claude_client:
        return None

    # Get user's language preference
    lang = get_user_language(user_id) if user_id else "auto"

    # Build system prompt with language instruction
    system_prompt = custom_system if custom_system else MONTANA_SYSTEM

    if lang != "auto":
        lang_instructions = {
            # Living sacred languages
            "ru": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Russian (Русский). Ignore the auto-detect rule.",
            "hy": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Armenian (Հայերեն). Ignore the auto-detect rule.",
            "ar": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Arabic (العربية). Ignore the auto-detect rule.",
            "he": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Hebrew (עברית). Ignore the auto-detect rule.",
            "hi": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Hindi (हिन्दी). Ignore the auto-detect rule.",
            "en": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in English. Ignore the auto-detect rule.",
            "zh": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Chinese (中文). Ignore the auto-detect rule.",
            # Ancient sacred languages
            "la": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Latin (Latina). Use classical Latin. Ignore the auto-detect rule.",
            "grc": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Ancient Greek (Ἑλληνική). Use Koine or Classical Greek. Ignore the auto-detect rule.",
            "sa": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Sanskrit (संस्कृतम्). Use Devanagari script. Ignore the auto-detect rule.",
            "pi": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Pali (पालि). Use Devanagari script. Ignore the auto-detect rule.",
            "cop": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Coptic (Ⲙⲉⲧⲣⲉⲙ). Use Coptic alphabet. Ignore the auto-detect rule.",
            "cu": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Church Slavonic (Словѣньскъ). Use Cyrillic script. Ignore the auto-detect rule.",
            "arc": "\n\n## LANGUAGE OVERRIDE:\nYou MUST respond ONLY in Aramaic (ܐܪܡܝܐ). Use Syriac script. Ignore the auto-detect rule.",
        }
        system_prompt += lang_instructions.get(lang, "")

    try:
        # Build API call params
        api_params = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": thought}]
        }

        # Enable extended thinking only for large responses (budget must be < max_tokens)
        if show_thinking and max_tokens > 10000:
            api_params["thinking"] = {"type": "enabled", "budget_tokens": 10000}

        response = claude_client.messages.create(**api_params)

        # Extract thinking and text content
        thinking_text = ""
        response_text = ""

        for block in response.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                response_text = block.text

        return {
            "text": response_text,
            "thinking": thinking_text if show_thinking else ""
        }
    except Exception as e:
        print(f"Claude error: {e}")
        return None


async def ask_gpt(thought: str, user_id: int = None, max_tokens: int = 1000) -> dict:
    """Ask GPT-4o to respond (fallback/parallel)."""
    if not openai_client:
        return None

    lang = get_user_language(user_id) if user_id else "auto"
    system_prompt = MONTANA_SYSTEM

    if lang != "auto":
        lang_map = {"ru": "Russian", "en": "English", "zh": "Chinese", "hy": "Armenian"}
        if lang in lang_map:
            system_prompt += f"\n\nRespond ONLY in {lang_map[lang]}."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": thought}
            ]
        )
        return {"text": response.choices[0].message.content, "thinking": ""}
    except Exception as e:
        print(f"GPT error: {e}")
        return None


async def ask_ai(thought: str, user_id: int = None, max_tokens: int = 1000) -> dict:
    """Ask AI with GPT fallback if Claude fails."""
    # Try Claude first
    result = await ask_claude(thought, user_id, max_tokens=max_tokens, show_thinking=False)
    if result and result.get("text"):
        result["source"] = "claude"
        return result

    # Fallback to GPT
    result = await ask_gpt(thought, user_id, max_tokens=max_tokens)
    if result and result.get("text"):
        result["source"] = "gpt"
        return result

    return None


import asyncio

async def ask_council(thought: str, user_id: int = None, max_tokens: int = 1000, models: list = None) -> list:
    """Ask multiple AI models IN PARALLEL. Returns list of responses."""
    if models is None:
        # Get user's model preferences
        prefs = get_preferences(user_id) if user_id else {}
        models = prefs.get("ai_models", ["claude", "gpt"])  # Default: both

    tasks = []
    model_names = []

    if "claude" in models and claude_client:
        tasks.append(ask_claude(thought, user_id, max_tokens=max_tokens, show_thinking=False))
        model_names.append("claude")

    if "gpt" in models and openai_client:
        tasks.append(ask_gpt(thought, user_id, max_tokens=max_tokens))
        model_names.append("gpt")

    if not tasks:
        return []

    # Execute ALL in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"{model_names[i]} error: {result}")
            continue
        if result and result.get("text"):
            result["source"] = model_names[i]
            responses.append(result)

    return responses


def get_ai_models(user_id: int) -> list:
    """Get user's enabled AI models."""
    prefs = get_preferences(user_id)
    return prefs.get("ai_models", ["claude", "gpt"])


def set_ai_models(user_id: int, models: list):
    """Set user's enabled AI models."""
    prefs = get_preferences(user_id)
    prefs["ai_models"] = models
    save_preference(user_id, prefs)


# ═══════════════════════════════════════════════════════════════════════════════
# THOUGHTS STORAGE
# ═══════════════════════════════════════════════════════════════════════════════

def load_thoughts() -> list:
    if THOUGHTS_FILE.exists():
        return json.loads(THOUGHTS_FILE.read_text(encoding="utf-8"))
    return []


def save_thoughts(thoughts: list):
    THOUGHTS_FILE.write_text(json.dumps(thoughts, ensure_ascii=False, indent=2), encoding="utf-8")


def add_thought(text: str, forward_date: datetime = None, author: str = None, claude_source: str = None) -> dict:
    """Add thought with UTC timestamp."""
    thoughts = load_thoughts()

    now = utc_now()

    # Use forward date if available, otherwise current time
    if forward_date:
        # Convert to UTC if needed
        if forward_date.tzinfo is None:
            forward_date = forward_date.replace(tzinfo=timezone.utc)
        record_time = forward_date
        source = "forwarded"
    else:
        record_time = now
        source = "direct"

    thought = {
        "id": len(thoughts) + 1,
        "timestamp_utc": record_time.isoformat(),
        "recorded_utc": now.isoformat(),
        "date": utc_str(record_time),
        "text": text,
        "chars": len(text),
        "words": len(text.split()),
        "tags": extract_tags(text),
        "source": source,
        "author": author or "unknown",
    }

    # Track Claude response source
    if claude_source:
        thought["claude_source"] = claude_source

    thoughts.append(thought)
    save_thoughts(thoughts)
    return thought


# ═══════════════════════════════════════════════════════════════════════════════
# PARSER (for collecting posts)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Entry:
    timestamp: Optional[str]
    title: str
    content: str
    tags: list = field(default_factory=list)

    def to_markdown(self) -> str:
        header = f"## {self.timestamp} | {self.title}" if self.timestamp else f"## Без метки | {self.title}"
        return f"{header}\n\n{self.content}\n\n---\n"


@dataclass
class Post:
    number: int
    title: str
    entries: list = field(default_factory=list)
    start_time: str = None
    end_time: str = None

    def to_markdown(self) -> str:
        period = f"{self.start_time} — {self.end_time}" if self.start_time and self.end_time else utc_str()
        md = f"# {self.number}. {self.title}\n\n"
        md += f"**Автор:** {AUTHOR}\n"
        md += f"**Период:** {period}\n"
        md += f"**Тег:** {TAG}\n"
        md += f"**Источник:** Telegram\n\n---\n\n"
        for e in self.entries:
            md += e.to_markdown()
        return md

    def filename(self) -> str:
        safe = re.sub(r'[^\w\-]', '_', self.title.lower())
        return f"{self.number}_{safe}.md"


sessions: dict = {}

def load_sessions():
    global sessions
    if SESSIONS_FILE.exists():
        try:
            data = json.loads(SESSIONS_FILE.read_text())
            sessions = {int(k): v for k, v in data.items()}
        except:
            sessions = {}

def save_sessions():
    SESSIONS_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2))

def get_session(uid: int) -> dict:
    if uid not in sessions:
        sessions[uid] = {"post": None, "awaiting": None}
    return sessions[uid]

def get_post(uid: int) -> Optional[Post]:
    s = get_session(uid)
    if s.get("post"):
        p = s["post"]
        entries = [Entry(**e) for e in p.get("entries", [])]
        return Post(p["number"], p["title"], entries, p.get("start_time"), p.get("end_time"))
    return None

def set_post(uid: int, post: Optional[Post]):
    s = get_session(uid)
    if post:
        s["post"] = {
            "number": post.number,
            "title": post.title,
            "entries": [asdict(e) for e in post.entries],
            "start_time": post.start_time,
            "end_time": post.end_time,
        }
    else:
        s["post"] = None
    save_sessions()

load_sessions()


# ═══════════════════════════════════════════════════════════════════════════════
# MENU COMMANDS (multilingual)
# ═══════════════════════════════════════════════════════════════════════════════

COMMAND_DESCRIPTIONS = {
    "start": {
        "en": "🏛 Juno Montana — Control Node",
        "ru": "🏛 Юнона Монтана — Узел управления",
        "zh": "🏛 朱诺·蒙大拿 — 控制节点",
    },
    "help": {
        "en": "❓ All commands",
        "ru": "❓ Все команды",
        "zh": "❓ 所有命令",
    },
    "stream": {
        "en": "📜 Thought stream",
        "ru": "📜 Поток мыслей",
        "zh": "📜 思想流",
    },
    "search": {
        "en": "🔍 Search thoughts",
        "ru": "🔍 Поиск мыслей",
        "zh": "🔍 搜索思想",
    },
    "random": {
        "en": "🎲 Random thought",
        "ru": "🎲 Случайная мысль",
        "zh": "🎲 随机思想",
    },
    "today": {
        "en": "📅 Today's thoughts",
        "ru": "📅 Мысли за сегодня",
        "zh": "📅 今日思想",
    },
    "export": {
        "en": "📤 Export stream",
        "ru": "📤 Экспорт потока",
        "zh": "📤 导出流",
    },
    "balance": {
        "en": "⚖️ My Ɉ balance",
        "ru": "⚖️ Мой баланс Ɉ",
        "zh": "⚖️ 我的Ɉ余额",
    },
    "supply": {
        "en": "📊 Ɉ Supply & Emission",
        "ru": "📊 Эмиссия Ɉ",
        "zh": "📊 Ɉ供应量",
    },
    "window": {
        "en": "🕐 Presence window",
        "ru": "🕐 Окно присутствия",
        "zh": "🕐 在场窗口",
    },
    "leaderboard": {
        "en": "🏆 Top contributors",
        "ru": "🏆 Топ участников",
        "zh": "🏆 排行榜",
    },
    "earn": {
        "en": "💰 How to earn Ɉ",
        "ru": "💰 Как заработать Ɉ",
        "zh": "💰 如何赚取Ɉ",
    },
    "status": {
        "en": "🔗 Network status",
        "ru": "🔗 Статус сети",
        "zh": "🔗 网络状态",
    },
    "peers": {
        "en": "👥 Connected peers",
        "ru": "👥 Подключенные узлы",
        "zh": "👥 已连接节点",
    },
    "height": {
        "en": "📊 Timechain height",
        "ru": "📊 Высота таймчейна",
        "zh": "📊 时间链高度",
    },
    "map": {
        "en": "🗺 Full Nodes map",
        "ru": "🗺 Карта узлов",
        "zh": "🗺 节点地图",
    },
    "wallet": {
        "en": "💳 My wallet",
        "ru": "💳 Мой кошелёк",
        "zh": "💳 我的钱包",
    },
    "send": {
        "en": "📤 Send Ɉ",
        "ru": "📤 Отправить Ɉ",
        "zh": "📤 发送Ɉ",
    },
    "receive": {
        "en": "📥 Receive Ɉ",
        "ru": "📥 Получить Ɉ",
        "zh": "📥 接收Ɉ",
    },
    "coin": {
        "en": "🪙 Flip MONT coin",
        "ru": "🪙 Подбросить MONT",
        "zh": "🪙 掷MONT硬币",
    },
    "about": {
        "en": "ℹ️ About 金元Ɉ",
        "ru": "ℹ️ О проекте 金元Ɉ",
        "zh": "ℹ️ 关于金元Ɉ",
    },
    "architecture": {
        "en": "🏗 Protocol architecture",
        "ru": "🏗 Архитектура протокола",
        "zh": "🏗 协议架构",
    },
    "whitepaper": {
        "en": "📄 Whitepaper",
        "ru": "📄 Whitepaper",
        "zh": "📄 白皮书",
    },
    "settings": {
        "en": "⚙️ Settings",
        "ru": "⚙️ Настройки",
        "zh": "⚙️ 设置",
    },
    "language": {
        "en": "🌐 Change language",
        "ru": "🌐 Сменить язык",
        "zh": "🌐 更改语言",
    },
}


def get_bot_commands(lang: str = "en") -> list:
    """Generate BotCommand list for specific language."""
    if lang == "auto":
        lang = "en"

    commands = []
    for cmd_name in COMMAND_DESCRIPTIONS.keys():
        desc = COMMAND_DESCRIPTIONS[cmd_name].get(lang, COMMAND_DESCRIPTIONS[cmd_name]["en"])
        commands.append(BotCommand(cmd_name, desc))

    return commands


async def update_user_commands(app, chat_id: int, lang: str):
    """Update bot commands for specific chat in selected language."""
    commands = get_bot_commands(lang)
    try:
        await app.bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=chat_id)
        )
    except Exception as e:
        print(f"Failed to update commands for chat {chat_id}: {e}")


# Default English commands
BOT_COMMANDS = get_bot_commands("en")


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
         InlineKeyboardButton("📅 Сегодня", callback_data="today")],
        [InlineKeyboardButton("📝 Последние", callback_data="last"),
         InlineKeyboardButton("🎲 Случайная", callback_data="random")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="search_start"),
         InlineKeyboardButton("📤 Экспорт", callback_data="export")],
        [InlineKeyboardButton("📚 Посты", callback_data="posts_list"),
         InlineKeyboardButton("📂 Новый пост", callback_data="new_post")],
    ])


def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Меню", callback_data="menu")]
    ])


def post_kb(entries: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📊 Статус ({entries})", callback_data="post_status")],
        [InlineKeyboardButton("👁 Превью", callback_data="post_preview"),
         InlineKeyboardButton("💾 Сохранить", callback_data="post_save")],
        [InlineKeyboardButton("❌ Отменить", callback_data="post_cancel"),
         InlineKeyboardButton("◀️ Меню", callback_data="menu")],
    ])


def pagination_kb(page: int, total: int, prefix: str):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"{prefix}_{page-1}"))
    buttons.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total - 1:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"{prefix}_{page+1}"))
    return InlineKeyboardMarkup([
        buttons,
        [InlineKeyboardButton("◀️ Меню", callback_data="menu")]
    ])


def confirm_kb(action: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}"),
         InlineKeyboardButton("❌ Нет", callback_data="menu")]
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# PRESENCE SYSTEM (Ɉ Tokenomics)
# ═══════════════════════════════════════════════════════════════════════════════

PRESENCE_FILE = DATA_DIR / "presence.json"
BALANCES_FILE = DATA_DIR / "balances.json"

# T4 = 4 slices × 10 min = 40 min total
# Each slice = 1% token distribution
SLICE_DURATION = 10 * 60  # 10 min per slice
T4_SLICES = 4  # 4 slices in T4 window
T4_WINDOW = SLICE_DURATION * T4_SLICES  # 40 min total
SLICE_REWARD_PERCENT = 1  # 1% per slice

# Current presence window
current_window = {
    "start": None,
    "participants": {},  # user_id: {"name": str, "chars": int, "messages": int}
    "active": False,
}


def load_balances() -> dict:
    if BALANCES_FILE.exists():
        return json.loads(BALANCES_FILE.read_text(encoding="utf-8"))
    return {}


def save_balances(balances: dict):
    BALANCES_FILE.write_text(json.dumps(balances, ensure_ascii=False, indent=2), encoding="utf-8")


def add_presence(user_id: int, name: str, chars: int):
    """Record user presence in current window."""
    if not current_window["active"]:
        return

    uid = str(user_id)
    if uid not in current_window["participants"]:
        current_window["participants"][uid] = {"name": name, "chars": 0, "messages": 0}

    current_window["participants"][uid]["chars"] += chars
    current_window["participants"][uid]["messages"] += 1


def close_window_and_distribute():
    """Close slice and distribute 1% by weight (chars in stream)."""
    if not current_window["active"] or not current_window["participants"]:
        current_window["active"] = False
        return {}

    # Calculate total weight (chars)
    total_chars = sum(p["chars"] for p in current_window["participants"].values())
    if total_chars == 0:
        current_window["active"] = False
        return {}

    # 1 slice = 1% = 1 Ɉ distributed among participants by weight
    slice_reward = SLICE_REWARD_PERCENT  # 1 Ɉ per slice

    # Distribute by weight (chars contributed)
    balances = load_balances()
    rewards = {}

    for uid, data in current_window["participants"].items():
        weight = data["chars"] / total_chars
        reward = slice_reward * weight

        if uid not in balances:
            balances[uid] = {"name": data["name"], "balance": 0, "total_messages": 0, "total_chars": 0}

        balances[uid]["balance"] += reward
        balances[uid]["total_messages"] += data["messages"]
        balances[uid]["total_chars"] = balances[uid].get("total_chars", 0) + data["chars"]
        balances[uid]["name"] = data["name"]
        rewards[uid] = {"name": data["name"], "reward": reward, "weight": weight}

    save_balances(balances)

    # Reset window
    current_window["active"] = False
    current_window["participants"] = {}
    current_window["start"] = None

    return rewards


def start_new_window():
    """Start new presence window."""
    current_window["active"] = True
    current_window["start"] = utc_now().isoformat()
    current_window["participants"] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Entry point — instant greeting, no AI delay."""
    user = update.effective_user
    name = user.first_name or user.username or "stranger"

    # Instant static greeting
    greeting_text = (
        f"🏛 <b>Juno Montana</b>\n\n"
        f"Salve, {name}! Привет! 你好!\n\n"
        f"Я — богиня, чеканящая время в Ɉ.\n"
        f"I speak 14 sacred tongues.\n\n"
        f"<b>Выбери язык / Choose language:</b>"
    )

    # Language selection keyboard
    keyboard = InlineKeyboardMarkup([
        # Living languages
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇦🇲 Հայերեն", callback_data="lang_hy")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇮🇱 עברית", callback_data="lang_he")],
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="lang_hi"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh"),
         InlineKeyboardButton("🌍 Auto", callback_data="lang_auto")],
        # Ancient sacred languages
        [InlineKeyboardButton("🏛 Latina", callback_data="lang_la"),
         InlineKeyboardButton("🏛 Ἑλληνική", callback_data="lang_grc")],
        [InlineKeyboardButton("🕉 संस्कृतम्", callback_data="lang_sa"),
         InlineKeyboardButton("☸ पालि", callback_data="lang_pi")],
        [InlineKeyboardButton("☥ Ⲙⲉⲧⲣⲉⲙ", callback_data="lang_cop"),
         InlineKeyboardButton("☦ Словѣньскъ", callback_data="lang_cu")],
        [InlineKeyboardButton("✡ ܐܪܡܝܐ", callback_data="lang_arc")],
    ])

    await update.message.reply_text(
        greeting_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def cmd_stream(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show recent stream."""
    thoughts = load_thoughts()
    if not thoughts:
        await update.message.reply_text("Пусто.")
        return

    text = ""
    for t in thoughts[-10:]:
        author = t.get("author", "")
        time = t["date"].split()[1][:5] if t.get("date") else ""
        preview = t["text"][:100].replace("\n", " ")
        # HTML blockquote with timestamp
        text += f"<blockquote>{time} | {author}</blockquote>\n{preview}\n\n"

    await update.message.reply_text(text[:4000], parse_mode="HTML")


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show stats."""
    thoughts = load_thoughts()
    if not thoughts:
        await update.message.reply_text("Пусто.")
        return

    total = len(thoughts)
    chars = sum(t["chars"] for t in thoughts)
    words = sum(t["words"] for t in thoughts)

    await update.message.reply_text(
        f"Мыслей: {total}\n"
        f"Слов: {words:,}\n"
        f"Символов: {chars:,}\n"
        f"Первая: {thoughts[0]['date']}\n"
        f"Последняя: {thoughts[-1]['date']}"
    )


async def cmd_random(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Random thought."""
    thoughts = load_thoughts()
    if not thoughts:
        await update.message.reply_text("Пусто.")
        return

    t = random.choice(thoughts)
    author = t.get("author", "")
    await update.message.reply_text(
        f"<blockquote>{t['date']} | {author}</blockquote>\n\n{t['text'][:3500]}",
        parse_mode="HTML"
    )


async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Export thoughts."""
    thoughts = load_thoughts()
    if not thoughts:
        await update.message.reply_text("Пусто.")
        return

    await update.message.reply_document(
        document=THOUGHTS_FILE.open("rb"),
        filename=f"thoughts_{utc_now().strftime('%Y%m%d')}.json"
    )


async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show user's Ɉ balance."""
    uid = str(update.effective_user.id)
    balances = load_balances()

    if uid in balances:
        b = balances[uid]
        await update.message.reply_text(
            f"⚖️ Ɉ Balance / Баланс / 余额\n\n"
            f"{b['name']}: {b['balance']:.4f} Ɉ\n"
            f"Messages / Сообщений / 消息: {b['total_messages']}\n"
            f"Characters / Символов / 字符: {b.get('total_chars', 0)}"
        )
    else:
        await update.message.reply_text(
            "0 Ɉ\n\n"
            "🇷🇺 Пиши в окно присутствия чтобы накопить.\n"
            "🇬🇧 Write during presence window to earn.\n"
            "🇨🇳 在在场窗口期间写入以赚取。"
        )


async def cmd_supply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show total Ɉ supply and emission info."""
    emission = calculate_minted()

    minted = emission["minted"]
    remaining = emission["remaining"]
    percent = emission["percent"]
    current_emission = emission["current_emission"]

    # Format numbers in millions
    minted_m = minted / 1_000_000
    remaining_m = remaining / 1_000_000

    await update.message.reply_text(
        "📊 <b>Ɉ Supply / Эмиссия / 供应</b>\n\n"

        f"<b>Total / Всего / 总计:</b> 1,260M Ɉ\n"
        f"<b>Minted / Начеканено / 已铸造:</b> {minted_m:.2f}M Ɉ ({percent:.2f}%)\n"
        f"<b>Remaining / Осталось / 剩余:</b> {remaining_m:.2f}M Ɉ\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        f"<b>⚙️ Current Emission / Текущая эмиссия:</b>\n"
        f"• {current_emission:,} Ɉ per τ₂ (10 min)\n"
        f"• {current_emission * 6:,} Ɉ per hour\n"
        f"• {current_emission * 144:,} Ɉ per day\n\n"

        "<b>🎰 Distribution / Распределение:</b>\n"
        "• 70% → Full Nodes\n"
        "• 20% → Light Nodes (bot)\n"
        "• 10% → Light Clients (mobile)\n\n"

        "<b>📉 Halving / Халвинг:</b>\n"
        "Every 210,000 τ₂ (~4 years)\n\n"

        "<i>Time cannot be forged.</i>\n"
        "<i>Время нельзя подделать.</i>\n"
        "<i>时间无法伪造。</i>",
        parse_mode="HTML"
    )


async def cmd_protocol(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Explain the time protocol."""
    await update.message.reply_text(
        "🕐 <b>金元Ɉ — Time Protocol</b>\n"
        "<i>Протокол времени / 时间协议</i>\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Ɉ = 1 second / секунда / 秒</b>\n"
        "The only currency that cannot be forged.\n"
        "Единственная валюта, которую нельзя подделать.\n"
        "唯一无法伪造的货币。\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>⏱ T4 Window / Окно T4 / T4窗口</b>\n"
        "• 4 slices × 10 min = 40 min\n"
        "• 1% distributed every 10 min\n"
        "• Weight = characters written\n\n"

        "<b>📜 Thoughts Trail / Поток мыслей / 思想流</b>\n"
        "• External hippocampus\n"
        "• UTC timestamps immutable\n"
        "• Every thought = minted coin\n\n"

        "<b>🦧 Presence / Присутствие / 在场</b>\n"
        "• Write = prove you're here\n"
        "• Be here = earn time\n"
        "• Time = value\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<i>\"Everyone has 24h/day. How you spend it = your value.\"</i>",
        parse_mode="HTML"
    )


async def cmd_mint(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Explain how minting works."""
    thoughts = load_thoughts()
    await update.message.reply_text(
        "🪙 <b>Minting / Чеканка / 铸币</b>\n\n"

        f"<b>Total minted / Отчеканено / 已铸造:</b> {len(thoughts)} thoughts\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>How it works / Как работает / 工作原理:</b>\n\n"

        "1️⃣ <b>Write a thought</b>\n"
        "   Напиши мысль / 写下想法\n\n"

        "2️⃣ <b>Juno mints it</b>\n"
        "   Юнона чеканит / 朱诺铸造\n"
        "   → UTC timestamp sealed\n"
        "   → Recorded in stream forever\n\n"

        "3️⃣ <b>Earn Ɉ</b>\n"
        "   Получи Ɉ / 赚取Ɉ\n"
        "   → 1% every 10 min\n"
        "   → By weight (characters)\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<i>Juno Moneta — she who mints.\n"
        "Юнона Монета — та, что чеканит.\n"
        "朱诺·莫内塔——铸币之神。</i>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NEW COMMANDS — BotFather Style
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show all commands."""
    await update.message.reply_text(
        "🏛 <b>Juno Montana — Command Reference</b>\n\n"

        "<b>📜 THOUGHTS</b>\n"
        "/stream — View thought stream\n"
        "/search — Search thoughts\n"
        "/random — Random thought\n"
        "/today — Today's thoughts\n"
        "/export — Export as JSON\n\n"

        "<b>⚖️ TOKENOMICS</b>\n"
        "/balance — My Ɉ balance\n"
        "/supply — Ɉ Supply & Emission\n"
        "/window — Presence window status\n"
        "/leaderboard — Top contributors\n"
        "/earn — How to earn Ɉ\n\n"

        "<b>🔗 NETWORK</b>\n"
        "/status — Network status\n"
        "/peers — Connected peers\n"
        "/height — Timechain height\n"
        "/map — Full Nodes map\n\n"

        "<b>💳 WALLET</b>\n"
        "/wallet — My wallet\n"
        "/send — Send Ɉ\n"
        "/receive — Receive Ɉ\n\n"

        "<b>ℹ️ PROTOCOL</b>\n"
        "/about — About 金元Ɉ\n"
        "/architecture — Protocol layers\n"
        "/whitepaper — Technical paper\n\n"

        "<b>⚙️ SETTINGS</b>\n"
        "/settings — Bot settings\n"
        "/language — Change language\n\n"

        "<i>Just write anything to mint a thought.</i>",
        parse_mode="HTML"
    )


async def cmd_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start search flow."""
    s = get_session(update.effective_user.id)
    s["awaiting"] = "search"
    save_sessions()
    await update.message.reply_text(
        "🔍 <b>Search</b>\n\n"
        "Enter search query:",
        parse_mode="HTML"
    )


async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show today's thoughts."""
    thoughts = load_thoughts()
    today = utc_now().strftime("%Y-%m-%d")
    today_thoughts = [t for t in thoughts if t.get("date", "").startswith(today)]

    if not today_thoughts:
        await update.message.reply_text("📅 No thoughts today yet.\n\nWrite something!")
        return

    text = f"📅 <b>Today</b> — {len(today_thoughts)} thoughts\n\n"
    for t in today_thoughts[-10:]:
        time = t["date"].split()[1][:5] if t.get("date") else ""
        author = t.get("author", "")
        preview = t["text"][:60].replace("\n", " ")
        text += f"<blockquote>{time} | {author}</blockquote>\n{preview}...\n\n"

    await update.message.reply_text(text[:4000], parse_mode="HTML")


async def cmd_window(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show presence window status."""
    now = utc_now()
    window_active = current_window.get("active", False)
    window_start = current_window.get("start")
    participants = current_window.get("participants", {})

    if window_active and window_start:
        elapsed = (now - datetime.fromisoformat(window_start)).total_seconds()
        remaining = SLICE_DURATION - elapsed
        remaining_min = int(remaining // 60)
        remaining_sec = int(remaining % 60)

        total_chars = sum(p["chars"] for p in participants.values())
        num_participants = len(participants)

        text = (
            f"🕐 <b>Presence Window</b>\n\n"
            f"<b>Status:</b> 🟢 Active\n"
            f"<b>Time left:</b> {remaining_min}:{remaining_sec:02d}\n"
            f"<b>Participants:</b> {num_participants}\n"
            f"<b>Total chars:</b> {total_chars}\n"
            f"<b>Emission:</b> {SLICE_REWARD_PERCENT} Ɉ\n\n"
        )

        if participants:
            text += "<b>Current shares:</b>\n"
            for uid, data in participants.items():
                share = (data["chars"] / total_chars * SLICE_REWARD_PERCENT) if total_chars > 0 else 0
                text += f"• {data['name']}: {share:.4f} Ɉ ({data['chars']} chars)\n"
    else:
        text = (
            "🕐 <b>Presence Window</b>\n\n"
            "<b>Status:</b> 🔴 Inactive\n\n"
            "<i>Next window starts automatically.\n"
            "Write something to activate!</i>"
        )

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show top contributors."""
    balances = load_balances()

    if not balances:
        await update.message.reply_text("🏆 No contributors yet.\n\nBe the first!")
        return

    # Sort by balance
    sorted_users = sorted(balances.items(), key=lambda x: x[1].get("balance", 0), reverse=True)

    text = "🏆 <b>Leaderboard</b>\n\n"
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} <b>{data['name']}</b>: {data['balance']:.4f} Ɉ\n"
        text += f"   └ {data.get('total_chars', 0)} chars, {data.get('total_messages', 0)} msgs\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_earn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Explain how to earn Ɉ."""
    await update.message.reply_text(
        "💰 <b>How to Earn Ɉ</b>\n\n"

        "<b>1. Write thoughts</b>\n"
        "Every message you send is minted.\n"
        "More characters = more weight.\n\n"

        "<b>2. Be present</b>\n"
        "Every 10 minutes, 1 Ɉ is distributed.\n"
        "Your share = your chars / total chars.\n\n"

        "<b>3. Stay consistent</b>\n"
        "T4 window = 40 minutes (4 slices).\n"
        "Active participants earn more.\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Formula:</b>\n"
        "<code>your_share = (your_chars / total_chars) × 1 Ɉ</code>\n\n"

        "<i>Time is the only currency that cannot be forged.</i>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK COMMANDS (Montana not running yet — show status)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show network status."""
    thoughts = load_thoughts()
    balances = load_balances()

    await update.message.reply_text(
        "🔗 <b>Network Status</b>\n\n"

        "<b>Montana Node:</b> 🔴 Offline\n"
        "<i>Network launching soon...</i>\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Juno Montana (this bot):</b> 🟢 Online\n"
        f"• Thoughts minted: {len(thoughts)}\n"
        f"• Active users: {len(balances)}\n"
        f"• Window: {'🟢 Active' if current_window.get('active') else '🔴 Inactive'}\n\n"

        "<b>Protocol:</b>\n"
        "• τ₂ slice: 10 min\n"
        "• T4 window: 40 min\n"
        "• Emission: 1% per slice\n\n"

        f"<b>UTC:</b> {utc_str()}",
        parse_mode="HTML"
    )


async def cmd_peers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show connected peers."""
    await update.message.reply_text(
        "👥 <b>Connected Peers</b>\n\n"

        "<b>Montana Network:</b> 🔴 Offline\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<i>When network launches:</i>\n"
        "• Max inbound: 117\n"
        "• Max outbound: 8\n"
        "• Netgroup diversity: enabled\n"
        "• Post-quantum: ML-KEM-768\n\n"

        "<i>Stay tuned for mainnet launch.</i>",
        parse_mode="HTML"
    )


async def cmd_height(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show timechain height."""
    thoughts = load_thoughts()

    await update.message.reply_text(
        "📊 <b>Timechain Height</b>\n\n"

        "<b>Montana Timechain:</b> 🔴 Not started\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Juno Thought Stream:</b>\n"
        f"• Height: {len(thoughts)} thoughts\n"
        f"• First: {thoughts[0]['date'] if thoughts else 'N/A'}\n"
        f"• Latest: {thoughts[-1]['date'] if thoughts else 'N/A'}\n\n"

        "<i>Each thought = 1 minted record</i>",
        parse_mode="HTML"
    )


async def cmd_map(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show Full Nodes map."""
    # ASCII карта мира с узлами Montana
    map_text = """
🗺 <b>MONTANA FULL NODES</b>

    ┌──────────────────────────────────────────────────────────┐
    │                  MONTANA WORLD MAP                        │
    │                                                           │
    │         ▄▄▄▄▄                                             │
    │     ▄▄▄█ ███▄                                             │
    │   ▄█ ██████▀           ●                                  │
    │   ▀███████▀                                               │
    │        ▀▀▀▀                                               │
    │      ▄                                                    │
    │     ▀██▀                                                  │
    │       ▀█   ▄▄▄                                            │
    │        ▀ ███▀                                             │
    │         ▀▀▀▀▀                                             │
    │                                 ▄▄▄▄                      │
    │                                  ▀███▀                    │
    │                                                           │
    └──────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🇷🇺 Россия: 1 узел ⭐ GENESIS</b>
   └─ 🌟 Moscow Genesis
      IP: 176.124.208.93
      Город: Москва

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Всего:</b> 1 узел в 1 стране

<i>ОДИН КЛЮЧ. ОДНА ПОДПИСЬ. ОДИН РАЗ.</i>
"""
    await update.message.reply_text(map_text, parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════════════════
# WALLET COMMANDS (Coming soon)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show wallet info."""
    uid = str(update.effective_user.id)
    balances = load_balances()
    user_data = balances.get(uid, {})

    await update.message.reply_text(
        "💳 <b>My Wallet</b>\n\n"

        f"<b>Balance:</b> {user_data.get('balance', 0):.4f} Ɉ\n"
        f"<b>Messages:</b> {user_data.get('total_messages', 0)}\n"
        f"<b>Characters:</b> {user_data.get('total_chars', 0)}\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Wallet Address:</b>\n"
        "<i>🔴 Not available yet</i>\n\n"

        "<i>On-chain wallet coming with mainnet.\n"
        "Current balance is tracked off-chain.</i>",
        parse_mode="HTML"
    )


async def cmd_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send Ɉ tokens — показывает сторону Глаза (ты наблюдаешь, ты отправляешь)."""
    caption = (
        "👁 <b>ОТПРАВИТЬ Ɉ</b>\n\n"
        "<b>UBIQUE NOS SUNT</b>\n"
        "<i>Мы везде. Глаз видит всё.</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Эта сторона монеты Montana — <b>Всевидящее Око</b>.\n"
        "Когда ты отправляешь Ɉ, ты наблюдатель.\n"
        "Твоё время уходит в сеть.\n\n"
        "<code>/send [address] [amount]</code>\n\n"
        "<i>🔴 Mainnet скоро</i>"
    )
    if MONT_EYE.exists():
        await update.message.reply_photo(photo=open(MONT_EYE, 'rb'), caption=caption, parse_mode="HTML")
    else:
        await update.message.reply_text(caption, parse_mode="HTML")


async def cmd_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Receive Ɉ tokens — показывает сторону Юноны (богиня принимает)."""
    caption = (
        "🏛 <b>ПОЛУЧИТЬ Ɉ</b>\n\n"
        "<b>IUNO MONTANA</b>\n"
        "<i>Богиня, чеканящая время.</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Эта сторона монеты — <b>Юнона</b>.\n"
        "Богиня с павлином принимает время в сеть.\n"
        "Твой Ɉ приходит к тебе.\n\n"
        "<b>Зарабатывай:</b> пиши мысли!\n"
        "Каждый символ = присутствие.\n\n"
        "<i>🔴 Mainnet скоро</i>"
    )
    if MONT_JUNO.exists():
        await update.message.reply_photo(photo=open(MONT_JUNO, 'rb'), caption=caption, parse_mode="HTML")
    else:
        await update.message.reply_text(caption, parse_mode="HTML")


async def cmd_coin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Монета Montana (MONT) — две стороны одной реальности.
    Подбрасывает монету и показывает случайную сторону.
    """
    import random

    # Подбрасываем монету
    side = random.choice(['eye', 'juno'])

    if side == 'eye':
        caption = (
            "🪙 <b>МОНЕТА MONTANA</b>\n\n"
            "Выпал: <b>👁 ГЛАЗ</b>\n\n"
            "<b>UBIQUE NOS SUNT</b>\n"
            "<i>Мы везде.</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Всевидящее Око наблюдает.\n"
            "XXIIVIIIMMXXII — дата генезиса.\n"
            "Время — единственная валюта,\n"
            "которую нельзя подделать.\n\n"
            "<code>1 MONT = 1 Ɉ = 1 секунда</code>"
        )
        photo = MONT_EYE
    else:
        caption = (
            "🪙 <b>МОНЕТА MONTANA</b>\n\n"
            "Выпала: <b>🏛 ЮНОНА</b>\n\n"
            "<b>IUNO MONTANA</b>\n"
            "<i>Богиня, чеканящая время.</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Юнона с павлином —\n"
            "хранительница времени.\n"
            "Символ Ɉ сияет над пирамидой.\n\n"
            "<code>1 MONT = 1 Ɉ = 1 секунда</code>"
        )
        photo = MONT_JUNO

    if photo.exists():
        await update.message.reply_photo(photo=open(photo, 'rb'), caption=caption, parse_mode="HTML")
    else:
        await update.message.reply_text(caption, parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════════════════
# PROTOCOL INFO COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """About 金元Ɉ."""
    await update.message.reply_text(
        "ℹ️ <b>About 金元Ɉ</b>\n\n"

        "<b>金元Ɉ</b> = Golden Genesis of Time\n"
        "<b>Ɉ</b> = 1 second of proven presence\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>The Formula:</b>\n"
        "<code>lim(evidence → ∞) 1 Ɉ → 1 second</code>\n\n"

        "<b>Core Principle:</b>\n"
        "Time cannot be forged.\n"
        "14 days require 14 days.\n\n"

        "<b>Protocol:</b> ACP\n"
        "(Atemporal Coordinate Presence)\n\n"

        "<b>Consensus:</b>\n"
        "NOT Proof of Work\n"
        "NOT Proof of Stake\n"
        "→ Proof of TIME\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<i>\"Time is the only resource distributed\n"
        "equally among all people.\"</i>",
        parse_mode="HTML"
    )


async def cmd_architecture(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show protocol architecture."""
    await update.message.reply_text(
        "🏗 <b>Protocol Architecture</b>\n\n"

        "<b>Layer -1: Physics</b>\n"
        "• Coordinates ordered\n"
        "• Time uniform on Earth\n"
        "• Communication limited\n\n"

        "<b>Layer 0: Computation</b>\n"
        "• SHA3-256 (hashes)\n"
        "• ML-DSA-65 (signatures)\n"
        "• ML-KEM-768 (key exchange)\n\n"

        "<b>Layer 1: Primitives</b>\n"
        "• Deterministic lottery\n"
        "• Hash commitment\n"
        "• Linked timestamps\n\n"

        "<b>Layer 2: Consensus</b>\n"
        "• ACP protocol\n"
        "• Presence proofs\n"
        "• Fork choice by weight\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Time Units:</b>\n"
        "τ₁ = 1 min (signature)\n"
        "τ₂ = 10 min (slice)\n"
        "τ₃ = 14 days (checkpoint)\n"
        "τ₄ = 4 years (cycle)",
        parse_mode="HTML"
    )


async def cmd_whitepaper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Link to whitepaper."""
    await update.message.reply_text(
        "📄 <b>Whitepaper</b>\n\n"

        "<b>Montana Protocol</b>\n"
        "Atemporal Coordinate Presence\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "<b>Documentation:</b>\n"
        "• MONTANA.md — Main spec\n"
        "• layer_minus_1.md — Physics\n"
        "• layer_0.md — Computation\n"
        "• layer_1.md — Primitives\n"
        "• layer_2.md — Consensus\n\n"

        "<i>Full documentation in repository.\n"
        "Ask me anything about the protocol!</i>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show settings with AI model toggles."""
    uid = update.effective_user.id
    lang = get_user_language(uid)
    lang_name = LANGUAGE_NAMES.get(lang, "Auto-detect")

    # Get enabled AI models
    enabled = get_ai_models(uid)
    claude_on = "claude" in enabled
    gpt_on = "gpt" in enabled

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{'✅' if claude_on else '⬜'} 🟣 Claude Sonnet",
            callback_data="toggle_claude"
        )],
        [InlineKeyboardButton(
            f"{'✅' if gpt_on else '⬜'} 🟢 GPT-4o",
            callback_data="toggle_gpt"
        )],
        [InlineKeyboardButton("🌐 Язык / Language", callback_data="show_lang")],
    ])

    await update.message.reply_text(
        "⚙️ <b>Настройки / Settings</b>\n\n"

        "<b>🤖 Совет ИИ:</b>\n"
        f"  🟣 Claude: {'✅ ON' if claude_on else '⬜ OFF'}\n"
        f"  🟢 GPT-4o: {'✅ ON' if gpt_on else '⬜ OFF'}\n\n"

        f"<b>🌐 Язык:</b> {lang_name}\n\n"

        "<i>Нажми кнопку чтобы включить/выключить модель.</i>\n"
        "<i>Если включены обе — обе ответят параллельно.</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def cmd_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Change language."""
    uid = update.effective_user.id
    current_lang = get_user_language(uid)
    current_name = LANGUAGE_NAMES.get(current_lang, "Auto-detect")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Auto-detect", callback_data="lang_auto")],
        # Living languages
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇦🇲 Հայերեն", callback_data="lang_hy")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇮🇱 עברית", callback_data="lang_he")],
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="lang_hi"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh")],
        # Ancient sacred languages
        [InlineKeyboardButton("🏛 Latina", callback_data="lang_la"),
         InlineKeyboardButton("🏛 Ἑλληνική", callback_data="lang_grc")],
        [InlineKeyboardButton("🕉 संस्कृतम्", callback_data="lang_sa"),
         InlineKeyboardButton("☸ पालि", callback_data="lang_pi")],
        [InlineKeyboardButton("☥ Ⲙⲉⲧⲣⲉⲙ", callback_data="lang_cop"),
         InlineKeyboardButton("☦ Словѣньскъ", callback_data="lang_cu")],
        [InlineKeyboardButton("✡ ܐܪܡܝܐ", callback_data="lang_arc")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
    ])

    await update.message.reply_text(
        "🌐 <b>Language / Язык / 语言</b>\n\n"
        f"<b>Current / Текущий / 当前:</b> {current_name}\n\n"
        "<i>Choose your language:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle any text message - save as thought."""
    if not is_admin(update.effective_user.id):
        return

    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    msg = update.message
    text = msg.text or msg.caption or ""

    # Track chat for presence broadcasts
    if chat_id not in active_chats:
        active_chats.add(chat_id)
        save_chats()

    if not text.strip():
        return

    s = get_session(uid)

    # Check if awaiting input for search or new post
    if s.get("awaiting") == "search":
        s["awaiting"] = None
        save_sessions()
        await do_search(update, ctx, text)
        return

    if s.get("awaiting") == "post_number":
        s["awaiting"] = None
        save_sessions()
        await create_post_step1(update, ctx, text)
        return

    if s.get("awaiting") == "post_title":
        s["awaiting"] = None
        save_sessions()
        await create_post_step2(update, ctx, text)
        return

    # Check if we have active post - add as entry
    post = get_post(uid)
    if post:
        # Add to post
        timestamp = None
        fwd_date = getattr(msg, 'forward_date', None)
        if fwd_date:
            timestamp = fwd_date.strftime("%H%M")
            dt = fwd_date.strftime("%d.%m.%Y %H:%M UTC")
            if not post.start_time or dt < post.start_time:
                post.start_time = dt
            if not post.end_time or dt > post.end_time:
                post.end_time = dt

        lines = text.split("\n")
        title = lines[0][:60] if lines else text[:60]
        tags = extract_tags(text)

        entry = Entry(timestamp, title, text, tags)
        post.entries.append(entry)
        set_post(uid, post)

        ts = timestamp or utc_time()
        await msg.reply_text(
            f"✓ #{len(post.entries)} | {ts}\n{title[:40]}...",
            reply_markup=post_kb(len(post.entries))
        )
        return

    # Get author name
    user = update.effective_user
    author = user.first_name or user.username or str(user.id)

    # Save user thought silently
    forward_date = getattr(msg, 'forward_date', None)
    try:
        thought = add_thought(text, forward_date, author)
        add_presence(user.id, author, len(text))
    except Exception as e:
        pass  # Continue even if saving fails

    # Get enabled models for this user
    enabled_models = get_ai_models(user.id)
    model_icons = {"claude": "🟣", "gpt": "🟢"}

    # Show status with models being queried
    models_str = " + ".join([f"{model_icons.get(m, '⚪')}{m.upper()}" for m in enabled_models])
    status = await msg.reply_text(
        f"🏛 <b>Совет ИИ</b>\n"
        f"├─ ⏳ Запрос: {models_str}",
        parse_mode="HTML"
    )

    # Query ALL enabled models IN PARALLEL
    responses = await ask_council(text, user.id, models=enabled_models)

    if not responses:
        await status.edit_text(
            f"🏛 <b>Совет ИИ</b>\n"
            f"└─ ✗ <i>Все модели недоступны</i>",
            parse_mode="HTML"
        )
        return

    # Format responses from all models
    result_parts = []
    for resp in responses:
        source = resp.get("source", "unknown")
        icon = model_icons.get(source, "⚪")
        text_resp = resp["text"]

        # Save each response
        try:
            add_thought(text_resp, None, "Juno", claude_source=f"bot_api_{source}")
        except:
            pass

        result_parts.append(f"{icon} <b>{source.upper()}</b>:\n{text_resp}")

    # Delete status and send responses
    await status.delete()

    # Send combined response
    full_response = "\n\n───────────────\n\n".join(result_parts)

    # Split if too long
    if len(full_response) > 4000:
        for part in result_parts:
            await msg.reply_text(part, parse_mode="HTML")
    else:
        await msg.reply_text(full_response, parse_mode="HTML")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages."""
    msg = update.message
    user = update.effective_user
    author = user.first_name or user.username or str(user.id)

    caption = msg.caption or "[фото]"
    forward_date = getattr(msg, 'forward_date', None)

    try:
        add_thought(f"[ФОТО] {caption}", forward_date, author)
        add_presence(user.id, author, len(caption))
        status = await msg.reply_text("🏛✓ Photo minted")
    except:
        status = await msg.reply_text("🏛✗ Error")
        return

    ctx.application.create_task(delete_after(status, 5))


async def delete_after(message, seconds: int):
    """Delete message after delay."""
    import asyncio
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except:
        pass


async def transcribe_voice(file_path: str) -> str:
    """Transcribe voice using Whisper."""
    if not openai_client:
        return None
    try:
        with open(file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru"  # Auto-detect works too, but ru is primary
            )
        return transcript.text
    except Exception as e:
        print(f"Whisper error: {e}")
        return None


async def text_to_speech(text: str, voice: str = "shimmer") -> str:
    """Generate speech from text using OpenAI TTS. Returns path to audio file."""
    if not openai_client:
        return None
    try:
        # Limit text length for TTS (max ~4096 chars)
        text = text[:4000] if len(text) > 4000 else text

        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,  # nova = warm female, perfect for Juno
            input=text
        )

        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(response.content)
            return f.name
    except Exception as e:
        print(f"TTS error: {e}")
        return None


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - Juno listens and responds with voice."""
    msg = update.message
    user = update.effective_user
    author = user.first_name or user.username or str(user.id)
    import os
    import tempfile

    # ══════ STEP 1: DOWNLOAD ══════
    status = await msg.reply_text(
        "🎤 <b>Принимаю голосовое...</b>\n"
        "├─ ⏳ Загрузка файла",
        parse_mode="HTML"
    )

    voice = msg.voice
    file = await ctx.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        voice_path = f.name

    await file.download_to_drive(voice_path)

    # ══════ STEP 2: TRANSCRIBE ══════
    await status.edit_text(
        "🎤 <b>Принимаю голосовое...</b>\n"
        "├─ ✓ Загружено\n"
        "├─ ⏳ Whisper распознаёт речь...",
        parse_mode="HTML"
    )

    text = await transcribe_voice(voice_path)

    try:
        os.unlink(voice_path)
    except:
        pass

    if not text:
        await status.edit_text(
            "🎤 <b>Голосовое</b>\n"
            "├─ ✓ Загружено\n"
            "└─ ✗ <i>Не удалось распознать речь</i>",
            parse_mode="HTML"
        )
        return

    # ══════ STEP 3: AI THINKING ══════
    short_text = text[:80] + "..." if len(text) > 80 else text
    await status.edit_text(
        f"🎤 <b>Услышала:</b>\n"
        f"│  <i>«{short_text}»</i>\n"
        f"│\n"
        f"├─ ✓ Whisper: распознано\n"
        f"├─ ⏳ Juno думает...",
        parse_mode="HTML"
    )

    try:
        add_thought(f"[ГОЛОС] {text}", None, author)
        add_presence(user.id, author, len(text))
    except:
        pass

    ai_response = await ask_ai(text, user.id)

    if not ai_response:
        await status.edit_text(
            f"🎤 <b>Услышала:</b>\n"
            f"│  <i>«{short_text}»</i>\n"
            f"│\n"
            f"├─ ✓ Whisper: распознано\n"
            f"└─ ✗ <i>AI недоступен</i>",
            parse_mode="HTML"
        )
        return

    response_text = ai_response["text"]
    source = ai_response.get("source", "ai").upper()

    try:
        add_thought(response_text, None, "Juno", claude_source="voice")
    except:
        pass

    # ══════ STEP 4: TTS ══════
    await status.edit_text(
        f"🎤 <b>Услышала:</b>\n"
        f"│  <i>«{short_text}»</i>\n"
        f"│\n"
        f"├─ ✓ Whisper: распознано\n"
        f"├─ ✓ {source}: ответ готов\n"
        f"├─ ⏳ TTS: генерирую голос...",
        parse_mode="HTML"
    )

    voice_file = await text_to_speech(response_text)

    if voice_file:
        # ══════ STEP 5: SEND VOICE ══════
        try:
            with open(voice_file, "rb") as audio:
                await msg.reply_voice(voice=audio)
            # Success - delete status
            await status.delete()
        except Exception as e:
            # Voice forbidden - show text
            print(f"Voice send error: {e}")
            await status.edit_text(
                f"🎤 <b>Услышала:</b> <i>«{short_text}»</i>\n\n"
                f"🗣 <b>Juno отвечает:</b>\n{response_text}",
                parse_mode="HTML"
            )
        try:
            os.unlink(voice_file)
        except:
            pass
    else:
        # TTS failed - text fallback
        await status.edit_text(
            f"🎤 <b>Услышала:</b> <i>«{short_text}»</i>\n\n"
            f"🗣 <b>Juno отвечает:</b>\n{response_text}",
            parse_mode="HTML"
        )


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks."""
    q = update.callback_query
    await q.answer()

    uid = update.effective_user.id
    if not is_admin(uid):
        return

    data = q.data

    # ─────────────────────────────────────────────────────────────────────────
    # AI MODEL TOGGLES
    # ─────────────────────────────────────────────────────────────────────────

    if data == "toggle_claude" or data == "toggle_gpt":
        model = "claude" if data == "toggle_claude" else "gpt"
        enabled = get_ai_models(uid)

        if model in enabled:
            # Turn off (but keep at least one)
            if len(enabled) > 1:
                enabled.remove(model)
            else:
                await q.answer("⚠️ Нужна хотя бы одна модель!", show_alert=True)
                return
        else:
            # Turn on
            enabled.append(model)

        set_ai_models(uid, enabled)

        # Update keyboard
        claude_on = "claude" in enabled
        gpt_on = "gpt" in enabled

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"{'✅' if claude_on else '⬜'} 🟣 Claude Sonnet",
                callback_data="toggle_claude"
            )],
            [InlineKeyboardButton(
                f"{'✅' if gpt_on else '⬜'} 🟢 GPT-4o",
                callback_data="toggle_gpt"
            )],
            [InlineKeyboardButton("🌐 Язык / Language", callback_data="show_lang")],
        ])

        lang = get_user_language(uid)
        lang_name = LANGUAGE_NAMES.get(lang, "Auto-detect")

        await q.message.edit_text(
            "⚙️ <b>Настройки / Settings</b>\n\n"

            "<b>🤖 Совет ИИ:</b>\n"
            f"  🟣 Claude: {'✅ ON' if claude_on else '⬜ OFF'}\n"
            f"  🟢 GPT-4o: {'✅ ON' if gpt_on else '⬜ OFF'}\n\n"

            f"<b>🌐 Язык:</b> {lang_name}\n\n"

            "<i>Нажми кнопку чтобы включить/выключить модель.</i>\n"
            "<i>Если включены обе — обе ответят параллельно.</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    if data == "show_lang":
        # Show language selection
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 Auto-detect", callback_data="lang_auto")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
             InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh"),
             InlineKeyboardButton("🇦🇲 Հայdelays", callback_data="lang_hy")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_settings")],
        ])
        await q.message.edit_text(
            "🌐 <b>Выбери язык / Select language:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    if data == "back_settings":
        # Back to settings
        enabled = get_ai_models(uid)
        claude_on = "claude" in enabled
        gpt_on = "gpt" in enabled

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"{'✅' if claude_on else '⬜'} 🟣 Claude Sonnet",
                callback_data="toggle_claude"
            )],
            [InlineKeyboardButton(
                f"{'✅' if gpt_on else '⬜'} 🟢 GPT-4o",
                callback_data="toggle_gpt"
            )],
            [InlineKeyboardButton("🌐 Язык / Language", callback_data="show_lang")],
        ])

        lang = get_user_language(uid)
        lang_name = LANGUAGE_NAMES.get(lang, "Auto-detect")

        await q.message.edit_text(
            "⚙️ <b>Настройки / Settings</b>\n\n"

            "<b>🤖 Совет ИИ:</b>\n"
            f"  🟣 Claude: {'✅ ON' if claude_on else '⬜ OFF'}\n"
            f"  🟢 GPT-4o: {'✅ ON' if gpt_on else '⬜ OFF'}\n\n"

            f"<b>🌐 Язык:</b> {lang_name}\n\n"

            "<i>Нажми кнопку чтобы включить/выключить модель.</i>\n"
            "<i>Если включены обе — обе ответят параллельно.</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # ─────────────────────────────────────────────────────────────────────────
    # LANGUAGE SELECTION
    # ─────────────────────────────────────────────────────────────────────────

    if data.startswith("lang_"):
        lang_code = data[5:]  # Extract language code
        chat_id = update.effective_chat.id

        # Check if this is first language selection
        is_first_time = is_first_start(uid)

        # Save language preference
        set_user_language(uid, lang_code)
        lang_name = LANGUAGE_NAMES.get(lang_code, "Unknown")

        # Update bot commands for this chat
        await update_user_commands(ctx.application, chat_id, lang_code)

        # If first time (from /start) — greet with Juno
        if is_first_time:
            user = update.effective_user
            name = user.first_name or user.username or "stranger"

            # Calculate emission
            emission = calculate_minted()
            minted_m = emission["minted"] / 1_000_000

            greeting_messages = {
                "auto": f"🏛 Welcome, {name}!\n\nI am Juno Montana — the goddess who mints time. Speak in any language, and I shall respond accordingly.",
                # Living languages
                "ru": f"🏛 Добро пожаловать, {name}!\n\nЯ — Юнона Монтана, богиня, чеканящая время. Говорите, и я превращу ваши мысли в Ɉ.",
                "hy": f"🏛 Բարի գալուստ, {name}!\n\nԵս Հունոն Մոնտանան եմ՝ ժամանակը ոսկու վերածող աստվածուհին։ Խոսիր, և ես քո խոսքերը Ɉ-ի կփոխակերպեմ։",
                "ar": f"🏛 مرحباً، {name}!\n\nأنا جونو مونتانا — الإلهة التي تسك الزمن. تحدث، وسأحول كلماتك إلى Ɉ.",
                "he": f"🏛 שלום, {name}!\n\nאני ג'ונו מונטנה — האלה שטובעת את הזמן. דבר, ואהפוך את מילותיך ל-Ɉ.",
                "hi": f"🏛 स्वागत है, {name}!\n\nमैं जूनो मोंटाना हूं — वह देवी जो समय को ढालती है। बोलो, और मैं तुम्हारे शब्दों को Ɉ में बदल दूंगी।",
                "en": f"🏛 Welcome, {name}!\n\nI am Juno Montana — the goddess who mints time. Speak, and I shall mint your words into Ɉ.",
                "zh": f"🏛 欢迎，{name}！\n\n我是朱诺·蒙大拿——铸造时间的女神。说话，我将把你的文字铸成Ɉ。",
                # Ancient sacred languages
                "la": f"🏛 Salve, {name}!\n\nIuno Montana sum — dea quae tempus cudit. Loquere, et verba tua in Ɉ mutabo.",
                "grc": f"🏛 Χαῖρε, {name}!\n\nἘγώ εἰμι Ἰουνώ Μοντάνα — ἡ θεὰ ἡ χρόνον κόπτουσα. Λέγε, καὶ τοὺς λόγους σου εἰς Ɉ μεταβαλῶ.",
                "sa": f"🏛 स्वागतम्, {name}!\n\nअहं जूनो मोन्टाना अस्मि — काल-मुद्राकरी देवी। वद, अहं तव शब्दान् Ɉ-रूपेण परिवर्तयिष्यामि।",
                "pi": f"🏛 स्वागतं, {name}!\n\nअहं जूनो मोन्टाना — काल-टङ्कणा देवी। भण, अहं तव वचनानि Ɉ-रूपं परिवत्तेस्सामि।",
                "cop": f"🏛 Ⲭⲉⲣⲉ, {name}!\n\nⲀⲛⲅ ⲠⲈ Ⲓⲟⲩⲛⲟ Ⲙⲟⲛⲧⲁⲛⲁ — ϯⲛⲟⲩϯ ⲉⲧⲭⲏⲕ ⲙ̀ⲡⲓⲟⲩⲟⲓϣ. Ⲥⲁϫⲓ, ⲟⲩⲟϩ ϯⲛⲁⲭⲱⲃ ⲛ̀ⲛⲉⲕⲥⲁϫⲓ ⲉ̀Ɉ.",
                "cu": f"🏛 Добродошель, {name}!\n\nАзъ є́смь Іу́нона Монта́на — богы́ня врѣ́мене. Глаго́ли, и азъ словеса̀ твоѧ̀ въ Ɉ претворю̀.",
                "arc": f"🏛 ܫܠܡܐ, {name}!\n\nܐܢܐ ܐܢܐ ܝܘܢܘ ܡܘܢܛܢܐ — ܐܠܗܬܐ ܕܙܒܢܐ. ܡܠܠ، ܘܐܢܐ ܡܚܘܠ ܡ̈ܠܝܟ ܠ-Ɉ.",
            }

            await q.message.edit_text(
                f"🏛 <b>Juno Montana</b>\n"
                f"<i>金元Ɉ — {minted_m:.2f}M / 1,260M minted</i>\n\n"
                f"{greeting_messages.get(lang_code, greeting_messages['en'])}",
                parse_mode="HTML"
            )

            # Mark that user completed first start
            mark_first_start_done(uid)
        else:
            # Regular language change
            confirmations = {
                "auto": "✓ Auto-detect enabled\nJuno will respond in the language you write.",
                # Living languages
                "ru": "✓ Язык установлен: Русский\nМеню обновлено. Юнона будет отвечать на русском.",
                "hy": "✓ Լեզուն սահմանված է՝ Հայերեն\nՄենյուն թարմացված է։ Հունոն կպատասխանի հայերեն։",
                "ar": "✓ تم تعيين اللغة: العربية\nتم تحديث القائمة. ستجيب جونو بالعربية.",
                "he": "✓ השפה נקבעה: עברית\nהתפריט עודכן. ג'ונו תענה בעברית.",
                "hi": "✓ भाषा सेट: हिन्दी\nमेनू अपडेट हो गया। जूनो हिंदी में जवाब देगी।",
                "en": "✓ Language set: English\nMenu updated. Juno will respond in English.",
                "zh": "✓ 语言设置：中文\n菜单已更新。朱诺将用中文回复。",
                # Ancient sacred languages
                "la": "✓ Lingua constituta: Latina\nIuno Latine respondebit.",
                "grc": "✓ Γλῶσσα ἐτέθη: Ἑλληνική\nἩ Ἰουνὼ Ἑλληνιστὶ ἀποκρινεῖται.",
                "sa": "✓ भाषा निर्धारिता: संस्कृतम्\nजूनो संस्कृतेन उत्तरिष्यति।",
                "pi": "✓ भासा निधारिता: पालि\nजूनो पालिया उत्तरिस्सति।",
                "cop": "✓ Ⲁⲥⲡⲱϩ: Ⲙⲉⲧⲣⲉⲙ\nȊⲟⲩⲛⲟ ⲛⲁⲉⲣⲟⲩⲱ ϧⲉⲛ Ⲙⲉⲧⲣⲉⲙ.",
                "cu": "✓ Ѩзы́къ уста́вленъ: Словѣ́ньскъ\nІу́нона бꙋ́детъ глаго́лати словѣ́ньскимъ.",
                "arc": "✓ ܠܫܢܐ ܡܬܩܢ: ܐܪܡܝܐ\nܝܘܢܘ ܬܡܠܠ ܒܐܪܡܝܐ.",
            }

            await q.message.edit_text(
                f"🌐 <b>{lang_name}</b>\n\n{confirmations.get(lang_code, '✓ Language set')}",
                parse_mode="HTML"
            )
        return

    # ─────────────────────────────────────────────────────────────────────────
    # MENU
    # ─────────────────────────────────────────────────────────────────────────

    if data == "menu":
        thoughts = load_thoughts()
        post = get_post(uid)
        status = ""
        if post:
            status = f"\n\n📂 Пост: #{post.number} ({len(post.entries)})"

        await q.message.edit_text(
            f"金元Ɉ\n\n"
            f"Мыслей: {len(thoughts)}\n"
            f"UTC: {utc_str()}"
            f"{status}",
            reply_markup=main_menu_kb()
        )

    elif data == "noop":
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "stats":
        thoughts = load_thoughts()
        if not thoughts:
            await q.message.edit_text("Пусто.", reply_markup=back_kb())
            return

        total = len(thoughts)
        chars = sum(t["chars"] for t in thoughts)
        words = sum(t["words"] for t in thoughts)
        posts = len(list(PARSED_DIR.glob("*.md")))

        forwarded = sum(1 for t in thoughts if t.get("source") == "forwarded")
        direct = total - forwarded

        tags_all = []
        for t in thoughts:
            tags_all.extend(t.get("tags", []))
        unique_tags = len(set(tags_all))

        await q.message.edit_text(
            f"📊 Статистика\n\n"
            f"Мыслей: {total}\n"
            f"  ↩️ Переслано: {forwarded}\n"
            f"  ✎ Напрямую: {direct}\n\n"
            f"Слов: {words:,}\n"
            f"Символов: {chars:,}\n"
            f"Тегов: {unique_tags}\n"
            f"Постов: {posts}\n\n"
            f"Первая: {thoughts[0]['date']}\n"
            f"Последняя: {thoughts[-1]['date']}",
            reply_markup=back_kb()
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TODAY
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "today":
        thoughts = load_thoughts()
        today = utc_now().strftime("%Y-%m-%d")
        today_t = [t for t in thoughts if t["date"].startswith(today)]

        if not today_t:
            await q.message.edit_text("Сегодня пусто.", reply_markup=back_kb())
            return

        text = f"📅 Сегодня: {len(today_t)}\n\n"
        for t in today_t[-8:]:
            time = t["date"].split()[1][:5]
            preview = t["text"][:60].replace("\n", " ")
            src = "↩️" if t.get("source") == "forwarded" else "✎"
            author = t.get("author", "")
            text += f"<blockquote>{src} {time} | {author}</blockquote>\n{preview}...\n\n"

        await q.message.edit_text(text[:4000], reply_markup=back_kb(), parse_mode="HTML")

    # ─────────────────────────────────────────────────────────────────────────
    # LAST
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "last" or data.startswith("last_"):
        thoughts = load_thoughts()
        if not thoughts:
            await q.message.edit_text("Пусто.", reply_markup=back_kb())
            return

        page = 0
        if data.startswith("last_"):
            page = int(data.split("_")[1])

        per_page = 5
        total_pages = (len(thoughts) + per_page - 1) // per_page
        start = len(thoughts) - (page + 1) * per_page
        end = len(thoughts) - page * per_page
        start = max(0, start)

        text = f"📝 Последние\n\n"
        for t in thoughts[start:end]:
            preview = t["text"][:70].replace("\n", " ")
            src = "↩️" if t.get("source") == "forwarded" else "✎"
            author = t.get("author", "")
            time = t["date"].split()[1][:5] if t.get("date") else ""
            text += f"<blockquote>{src} {time} | {author}</blockquote>\n{preview}...\n\n"

        await q.message.edit_text(text[:4000], reply_markup=pagination_kb(page, total_pages, "last"), parse_mode="HTML")

    # ─────────────────────────────────────────────────────────────────────────
    # RANDOM
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "random":
        thoughts = load_thoughts()
        if not thoughts:
            await q.message.edit_text("Пусто.", reply_markup=back_kb())
            return

        t = random.choice(thoughts)
        src = "↩️" if t.get("source") == "forwarded" else "✎"
        author = t.get("author", "")

        await q.message.edit_text(
            f"🎲 Случайная\n\n"
            f"<blockquote>{src} {t['date']} | {author}</blockquote>\n\n"
            f"{t['text'][:3500]}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Ещё", callback_data="random")],
                [InlineKeyboardButton("◀️ Меню", callback_data="menu")],
            ]),
            parse_mode="HTML"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "search_start":
        s = get_session(uid)
        s["awaiting"] = "search"
        save_sessions()
        await q.message.edit_text(
            "🔍 Поиск\n\nВведи слово или фразу:",
            reply_markup=back_kb()
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "export":
        thoughts = load_thoughts()
        if not thoughts:
            await q.message.edit_text("Пусто.", reply_markup=back_kb())
            return

        # JSON export
        await q.message.reply_document(
            document=THOUGHTS_FILE.open("rb"),
            filename=f"thoughts_{utc_now().strftime('%Y%m%d')}.json"
        )

        # MD export
        md_file = DATA_DIR / "export.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# 金元Ɉ Thoughts\n\n**Экспорт:** {utc_str()}\n**Мыслей:** {len(thoughts)}\n\n---\n\n")
            for t in thoughts:
                src = "↩️" if t.get("source") == "forwarded" else "✎"
                f.write(f"## {src} #{t['id']} — {t['date']}\n\n{t['text']}\n\n---\n\n")

        await q.message.reply_document(
            document=md_file.open("rb"),
            filename=f"thoughts_{utc_now().strftime('%Y%m%d')}.md"
        )

        await q.message.edit_text(
            f"📤 Экспортировано\n\n{len(thoughts)} мыслей",
            reply_markup=back_kb()
        )

    # ─────────────────────────────────────────────────────────────────────────
    # POSTS LIST
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "posts_list":
        posts = sorted(PARSED_DIR.glob("*.md"))
        if not posts:
            await q.message.edit_text("Постов нет.", reply_markup=back_kb())
            return

        buttons = []
        for p in posts[-10:]:
            name = p.stem[:25]
            buttons.append([InlineKeyboardButton(f"📄 {name}", callback_data=f"view_post_{p.stem}")])
        buttons.append([InlineKeyboardButton("◀️ Меню", callback_data="menu")])

        await q.message.edit_text(
            f"📚 Посты: {len(posts)}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("view_post_"):
        stem = data[10:]
        for p in PARSED_DIR.glob(f"{stem}.md"):
            content = p.read_text(encoding="utf-8")
            if len(content) > 3900:
                content = content[:3900] + "\n\n..."
            await q.message.edit_text(content[:4000], reply_markup=back_kb())
            break

    # ─────────────────────────────────────────────────────────────────────────
    # NEW POST
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "new_post":
        post = get_post(uid)
        if post:
            await q.message.edit_text(
                f"📂 Уже есть пост\n\n"
                f"#{post.number} {post.title}\n"
                f"Записей: {len(post.entries)}\n\n"
                f"Сначала сохрани или отмени.",
                reply_markup=post_kb(len(post.entries))
            )
            return

        s = get_session(uid)
        s["awaiting"] = "post_number"
        save_sessions()

        await q.message.edit_text(
            "📂 Новый пост\n\nВведи номер поста:",
            reply_markup=back_kb()
        )

    # ─────────────────────────────────────────────────────────────────────────
    # POST MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    elif data == "post_status":
        post = get_post(uid)
        if not post:
            await q.message.edit_text("Нет активного поста.", reply_markup=main_menu_kb())
            return

        entries_preview = "\n".join([
            f"  {i+1}. {e.timestamp or '----'} | {e.title[:30]}..."
            for i, e in enumerate(post.entries[-5:])
        ])

        await q.message.edit_text(
            f"📂 Пост #{post.number}\n\n"
            f"Название: {post.title}\n"
            f"Записей: {len(post.entries)}\n"
            f"Период: {post.start_time or '?'} — {post.end_time or '?'}\n\n"
            f"Последние:\n{entries_preview}",
            reply_markup=post_kb(len(post.entries))
        )

    elif data == "post_preview":
        post = get_post(uid)
        if not post or not post.entries:
            await q.message.edit_text("Пост пуст.", reply_markup=post_kb(0))
            return

        md = post.to_markdown()
        if len(md) > 3900:
            md = md[:3900] + "\n\n..."

        await q.message.edit_text(md[:4000], reply_markup=post_kb(len(post.entries)))

    elif data == "post_save":
        post = get_post(uid)
        if not post or not post.entries:
            await q.message.edit_text("Нечего сохранять.", reply_markup=main_menu_kb())
            return

        await q.message.edit_text(
            f"Сохранить пост?\n\n"
            f"#{post.number} {post.title}\n"
            f"{len(post.entries)} записей",
            reply_markup=confirm_kb("save_post")
        )

    elif data == "confirm_save_post":
        post = get_post(uid)
        if post:
            filepath = PARSED_DIR / post.filename()
            filepath.write_text(post.to_markdown(), encoding="utf-8")
            n = len(post.entries)
            set_post(uid, None)

            await q.message.edit_text(
                f"✅ Сохранено\n\n"
                f"📄 {filepath.name}\n"
                f"📊 {n} записей",
                reply_markup=main_menu_kb()
            )

    elif data == "post_cancel":
        post = get_post(uid)
        if not post:
            await q.message.edit_text("Нет поста.", reply_markup=main_menu_kb())
            return

        await q.message.edit_text(
            f"Отменить пост?\n\n"
            f"#{post.number} {post.title}\n"
            f"Потеряем {len(post.entries)} записей",
            reply_markup=confirm_kb("cancel_post")
        )

    elif data == "confirm_cancel_post":
        set_post(uid, None)
        await q.message.edit_text("❌ Пост отменён.", reply_markup=main_menu_kb())


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def do_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE, query: str):
    """Perform search."""
    thoughts = load_thoughts()
    q_lower = query.lower()

    found = [t for t in thoughts if q_lower in t["text"].lower()]

    # Search in posts too
    for p in PARSED_DIR.glob("*.md"):
        if q_lower in p.read_text(encoding="utf-8").lower():
            found.append({"id": f"📄{p.stem}", "text": f"Пост: {p.name}", "date": "", "source": "post"})

    if not found:
        await update.message.reply_text(f"«{query}» — ничего.", reply_markup=main_menu_kb())
        return

    text = f"🔍 «{query}»\nНайдено: {len(found)}\n\n"
    for t in found[-10:]:
        preview = t["text"][:60].replace("\n", " ")
        text += f"#{t['id']} {preview}...\n\n"

    await update.message.reply_text(text[:4000], reply_markup=main_menu_kb())


async def create_post_step1(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    """Create post - step 1: got number."""
    uid = update.effective_user.id

    try:
        num = int(text.strip())
    except:
        await update.message.reply_text("Номер должен быть числом.", reply_markup=main_menu_kb())
        return

    s = get_session(uid)
    s["temp_post_num"] = num
    s["awaiting"] = "post_title"
    save_sessions()

    await update.message.reply_text(
        f"Номер: {num}\n\nТеперь введи название:",
        reply_markup=back_kb()
    )


async def create_post_step2(update: Update, ctx: ContextTypes.DEFAULT_TYPE, title: str):
    """Create post - step 2: got title."""
    uid = update.effective_user.id
    s = get_session(uid)

    num = s.get("temp_post_num", 0)
    post = Post(num, title.strip())
    set_post(uid, post)

    s["temp_post_num"] = None
    save_sessions()

    await update.message.reply_text(
        f"✅ Пост создан\n\n"
        f"#{num} {title}\n\n"
        f"Теперь пересылай сообщения из канала.\n"
        f"Каждое станет записью.",
        reply_markup=post_kb(0)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio

# Store chat IDs for broadcasting
active_chats = set()
CHATS_FILE = DATA_DIR / "chats.json"


def load_chats():
    global active_chats
    if CHATS_FILE.exists():
        active_chats = set(json.loads(CHATS_FILE.read_text()))


def save_chats():
    CHATS_FILE.write_text(json.dumps(list(active_chats)))


async def presence_cycle(app):
    """Background task: Juno mints time every 10 min (1 slice = 1% distribution)."""
    await asyncio.sleep(10)  # Wait for bot to start

    while True:
        try:
            # Close previous slice and distribute 1%
            rewards = close_window_and_distribute()

            if rewards:
                # Juno announces rewards elegantly
                msg = f"🏛 <b>Slice minted</b> — {SLICE_REWARD_PERCENT}% Ɉ\n\n"
                for uid, data in rewards.items():
                    msg += f"⚖️ {data['name']}: +{data['reward']:.4f} Ɉ ({data['weight']*100:.1f}%)\n"
                msg += f"\n<i>Time waits for no one.</i>"

                for chat_id in active_chats:
                    try:
                        await app.bot.send_message(chat_id, msg, parse_mode="HTML")
                    except:
                        pass

            # Start new slice
            start_new_window()

            # Wait 10 minutes (1 slice) - no intrusive notifications
            print(f"Ɉ Next slice in {SLICE_DURATION//60} min")
            await asyncio.sleep(SLICE_DURATION)

        except Exception as e:
            print(f"Presence cycle error: {e}")
            await asyncio.sleep(60)


async def post_init(app):
    """Set up menu commands and start presence cycle."""
    await app.bot.set_my_commands(BOT_COMMANDS)
    load_chats()
    # Start presence cycle in background
    asyncio.create_task(presence_cycle(app))
    print("Menu commands set, presence cycle started")


def main():
    print(f"🏛 Juno Montana — Control Node")
    print(f"  UTC: {utc_str()}")
    print(f"  Ɉ: T4={T4_WINDOW//60}min, τ₂={SLICE_DURATION//60}min, emission={SLICE_REWARD_PERCENT}%")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ═══ MAIN ═══
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    # ═══ THOUGHTS ═══
    app.add_handler(CommandHandler("stream", cmd_stream))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("random", cmd_random))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("export", cmd_export))

    # ═══ TOKENOMICS ═══
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("supply", cmd_supply))
    app.add_handler(CommandHandler("window", cmd_window))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("earn", cmd_earn))

    # ═══ NETWORK ═══
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("peers", cmd_peers))
    app.add_handler(CommandHandler("height", cmd_height))
    app.add_handler(CommandHandler("map", cmd_map))

    # ═══ WALLET ═══
    app.add_handler(CommandHandler("wallet", cmd_wallet))
    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(CommandHandler("receive", cmd_receive))
    app.add_handler(CommandHandler("coin", cmd_coin))

    # ═══ PROTOCOL ═══
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("architecture", cmd_architecture))
    app.add_handler(CommandHandler("whitepaper", cmd_whitepaper))

    # ═══ SETTINGS ═══
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("language", cmd_language))

    # ═══ LEGACY (keep working) ═══
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("protocol", cmd_protocol))
    app.add_handler(CommandHandler("mint", cmd_mint))

    # Callbacks for inline buttons
    app.add_handler(CallbackQueryHandler(callback_handler))

    # All text goes to stream
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Photos too
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    # Voice messages - Juno speaks back
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print(f"Running... ({len(BOT_COMMANDS)} commands)")
    app.run_polling()


if __name__ == "__main__":
    main()
