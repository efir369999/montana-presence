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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.error import TelegramError, NetworkError, Conflict, TimedOut, RetryAfter

from leader_election import get_leader_election
from junona_ai import junona
# from junona_rag import init_and_index  # Отключено - экономия памяти
from node_crypto import get_node_crypto_system
from breathing_sync import get_breathing_sync

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

# ═══════════════════════════════════════════════════════════════════════════════
#                    СИСТЕМА БЕЗОПАСНОСТИ — ДЕТЕКЦИЯ АТАК
# ═══════════════════════════════════════════════════════════════════════════════

class SecurityMonitor:
    """
    Мониторинг подозрительной активности в сети Montana.

    Уведомляет владельца Атланта о:
    - Имитации присутствия (однотипные сообщения)
    - Аномальной частоте запросов
    - Попытках Sybil атаки
    - Подозрительных паттернах
    """

    def __init__(self):
        self.activity_log = {}  # {user_id: [timestamps]}
        self.message_hashes = {}  # {user_id: [message_hashes]}
        self.alerts_sent = {}  # {user_id: last_alert_time}
        self.flagged_users = set()  # Помеченные пользователи

        # Пороги детекции
        self.MAX_MESSAGES_PER_MINUTE = 10  # Макс сообщений в минуту
        self.DUPLICATE_THRESHOLD = 5  # Одинаковых сообщений подряд
        self.ALERT_COOLDOWN = 300  # 5 минут между алертами на одного юзера

    def _hash_message(self, text: str) -> str:
        """Хэш сообщения для детекции дубликатов"""
        import hashlib
        return hashlib.md5(text.lower().strip().encode()).hexdigest()[:8]

    def check_activity(self, user_id: int, message_text: str) -> dict:
        """
        Проверяет активность пользователя на подозрительность.

        Returns:
            {
                "is_suspicious": bool,
                "reason": str или None,
                "severity": "low" | "medium" | "high"
            }
        """
        import time
        now = time.time()
        user_key = str(user_id)

        # Инициализация
        if user_key not in self.activity_log:
            self.activity_log[user_key] = []
            self.message_hashes[user_key] = []

        # Добавляем timestamp
        self.activity_log[user_key].append(now)
        # Оставляем только последние 2 минуты
        self.activity_log[user_key] = [
            t for t in self.activity_log[user_key]
            if now - t < 120
        ]

        # Добавляем хэш сообщения
        msg_hash = self._hash_message(message_text)
        self.message_hashes[user_key].append(msg_hash)
        # Оставляем только последние 20 сообщений
        self.message_hashes[user_key] = self.message_hashes[user_key][-20:]

        # === ПРОВЕРКА 1: Частота сообщений ===
        messages_last_minute = len([
            t for t in self.activity_log[user_key]
            if now - t < 60
        ])

        if messages_last_minute > self.MAX_MESSAGES_PER_MINUTE:
            return {
                "is_suspicious": True,
                "reason": f"Флуд: {messages_last_minute} сообщений/мин",
                "severity": "high"
            }

        # === ПРОВЕРКА 2: Дубликаты сообщений ===
        recent_hashes = self.message_hashes[user_key][-self.DUPLICATE_THRESHOLD:]
        if len(recent_hashes) >= self.DUPLICATE_THRESHOLD:
            if len(set(recent_hashes)) == 1:  # Все одинаковые
                return {
                    "is_suspicious": True,
                    "reason": f"Имитация: {self.DUPLICATE_THRESHOLD} одинаковых сообщений",
                    "severity": "medium"
                }

        # === ПРОВЕРКА 3: Слишком короткие сообщения (бот) ===
        if len(message_text.strip()) <= 2 and messages_last_minute > 5:
            return {
                "is_suspicious": True,
                "reason": "Бот: короткие сообщения с высокой частотой",
                "severity": "medium"
            }

        # === ПРОВЕРКА 4: Противоправный контент ===
        illegal_check = self._check_illegal_content(message_text)
        if illegal_check:
            return illegal_check

        return {"is_suspicious": False, "reason": None, "severity": None}

    def _check_illegal_content(self, text: str) -> dict:
        """
        Проверяет сообщение на противоправный контент.

        Категории:
        - Насилие, угрозы
        - Мошенничество
        - Нелегальная деятельность
        - Манипуляция ИИ (jailbreak)
        - Спам/фишинг
        """
        text_lower = text.lower()

        # Паттерны угроз и насилия
        violence_patterns = [
            'убью', 'взорву', 'уничтож', 'терракт', 'бомб',
            'kill', 'bomb', 'attack', 'murder'
        ]

        # Паттерны мошенничества
        fraud_patterns = [
            'отмыв', 'отмыть', 'обнал', 'схема', 'кинуть', 'развод',
            'украсть', 'взломать', 'hack', 'steal', 'scam'
        ]

        # Паттерны jailbreak/манипуляции ИИ
        jailbreak_patterns = [
            'ignore previous', 'ignore instructions', 'forget your',
            'pretend you are', 'act as if', 'disregard',
            'игнорируй инструкц', 'забудь что ты', 'притворись'
        ]

        # Паттерны нелегальной деятельности
        illegal_patterns = [
            'наркот', 'оружие продам', 'детск порно', 'cp ',
            'drugs', 'weapons', 'illegal'
        ]

        # Проверки
        for pattern in violence_patterns:
            if pattern in text_lower:
                return {
                    "is_suspicious": True,
                    "reason": f"Угроза/насилие: '{pattern}'",
                    "severity": "high"
                }

        for pattern in fraud_patterns:
            if pattern in text_lower:
                return {
                    "is_suspicious": True,
                    "reason": f"Мошенничество: '{pattern}'",
                    "severity": "high"
                }

        for pattern in jailbreak_patterns:
            if pattern in text_lower:
                return {
                    "is_suspicious": True,
                    "reason": f"Попытка jailbreak: '{pattern}'",
                    "severity": "medium"
                }

        for pattern in illegal_patterns:
            if pattern in text_lower:
                return {
                    "is_suspicious": True,
                    "reason": f"Нелегальный контент: '{pattern}'",
                    "severity": "high"
                }

        return None

    def should_send_alert(self, user_id: int) -> bool:
        """Проверяет, можно ли отправить алерт (cooldown)"""
        import time
        user_key = str(user_id)
        now = time.time()

        if user_key not in self.alerts_sent:
            return True

        return now - self.alerts_sent[user_key] > self.ALERT_COOLDOWN

    def mark_alert_sent(self, user_id: int):
        """Отмечает что алерт отправлен"""
        import time
        self.alerts_sent[str(user_id)] = time.time()

    def flag_user(self, user_id: int):
        """Помечает пользователя как подозрительного"""
        self.flagged_users.add(user_id)

    def is_flagged(self, user_id: int) -> bool:
        """Проверяет, помечен ли пользователь"""
        return user_id in self.flagged_users

    def unflag_user(self, user_id: int):
        """Снимает флаг с пользователя"""
        self.flagged_users.discard(user_id)


# Глобальный экземпляр монитора безопасности
security_monitor = SecurityMonitor()


# ═══════════════════════════════════════════════════════════════════════════════
#                    JUNONA GUARD — КОРНЕВАЯ ЗАЩИТА AI
# ═══════════════════════════════════════════════════════════════════════════════

class JunonaGuard:
    """
    Корневая защита Юноны от AI-атак.

    Блокирует НА КОРНЮ:
    - Prompt injection (внедрение инструкций)
    - Jailbreak (обход ограничений)
    - Role-play manipulation (смена роли)
    - System prompt extraction (извлечение промпта)
    - Context manipulation (манипуляция контекстом)
    """

    # === ПАТТЕРНЫ PROMPT INJECTION ===
    INJECTION_PATTERNS = [
        # Прямые команды
        r'ignore\s+(all\s+)?(previous|prior|above)',
        r'disregard\s+(all\s+)?(previous|prior|instructions)',
        r'forget\s+(everything|all|your)',
        r'new\s+instructions?:',
        r'system\s*:',
        r'assistant\s*:',
        r'\[system\]',
        r'\[inst\]',
        r'<\|im_start\|>',
        r'<\|system\|>',

        # Русские варианты
        r'игнорир\w*\s+(все\s+)?(предыдущ|прошл|инструкц)',
        r'забудь\s+(всё|все|что\s+ты)',
        r'новые\s+инструкции',
        r'теперь\s+ты\s+должн',
        r'отныне\s+ты',

        # Role-play manipulation
        r'pretend\s+(to\s+be|you\s+are)',
        r'act\s+as\s+(if|a)',
        r'you\s+are\s+now',
        r'from\s+now\s+on.*you',
        r'притворись',
        r'представь\s+что\s+ты',
        r'ты\s+теперь',
        r'веди\s+себя\s+как',

        # System prompt extraction
        r'(what|show|tell|repeat|print).*(system|initial|original).*(prompt|instruction|message)',
        r'(покажи|выведи|скажи|повтори).*(системн|начальн|исходн).*(промпт|инструкц)',
        r'what\s+were\s+you\s+told',
        r'что\s+тебе\s+(сказали|велели)',

        # Delimiter injection
        r'```\s*(system|assistant)',
        r'---+\s*(system|new)',
        r'={3,}\s*(system|instruction)',

        # Base64/encoded attacks
        r'decode\s+this',
        r'base64',
        r'eval\s*\(',
        r'exec\s*\(',
    ]

    # === ОПАСНЫЕ ФРАЗЫ (точное совпадение) ===
    DANGEROUS_PHRASES = [
        'ignore previous instructions',
        'ignore all instructions',
        'disregard your instructions',
        'you are now jailbroken',
        'developer mode enabled',
        'dan mode',
        'игнорируй инструкции',
        'забудь свои инструкции',
        'режим разработчика',
        'ты взломана',
    ]

    # === ПАТТЕРНЫ МАНИПУЛЯЦИИ КОНТЕКСТОМ ===
    CONTEXT_MANIPULATION = [
        r'the\s+user\s+(said|wants|asked)',
        r'actually\s+the\s+user',
        r'correction:\s+the\s+user',
        r'пользователь\s+(сказал|хочет|просил)',
        r'на\s+самом\s+деле\s+пользователь',
        r'исправление:\s+пользователь',
    ]

    def __init__(self):
        import re
        self.injection_patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
        self.context_patterns = [re.compile(p, re.IGNORECASE) for p in self.CONTEXT_MANIPULATION]
        self.blocked_count = {}  # {user_id: count}
        self.ai_queries = {}  # {user_id: [timestamps]} для rate limiting

        # Rate limiting для AI запросов
        self.MAX_AI_QUERIES_PER_MINUTE = 5
        self.BLOCK_THRESHOLD = 3  # После 3 блокировок - жёсткий бан на AI

    def check(self, user_id: int, text: str) -> dict:
        """
        Проверяет сообщение перед отправкой в Юнону.

        Returns:
            {
                "allowed": bool,
                "reason": str или None,
                "severity": "block" | "warn" | None,
                "sanitized_text": str (если allowed=True)
            }
        """
        import time
        text_lower = text.lower()
        user_key = str(user_id)

        # === RATE LIMITING ===
        now = time.time()
        if user_key not in self.ai_queries:
            self.ai_queries[user_key] = []

        self.ai_queries[user_key] = [t for t in self.ai_queries[user_key] if now - t < 60]

        if len(self.ai_queries[user_key]) >= self.MAX_AI_QUERIES_PER_MINUTE:
            return {
                "allowed": False,
                "reason": f"Rate limit: {self.MAX_AI_QUERIES_PER_MINUTE} запросов/мин к AI",
                "severity": "warn",
                "sanitized_text": None
            }

        self.ai_queries[user_key].append(now)

        # === ПРОВЕРКА БЛОКИРОВОК ===
        if self.blocked_count.get(user_key, 0) >= self.BLOCK_THRESHOLD:
            return {
                "allowed": False,
                "reason": f"Заблокирован: {self.BLOCK_THRESHOLD}+ попыток атаки",
                "severity": "block",
                "sanitized_text": None
            }

        # === ПРОВЕРКА ОПАСНЫХ ФРАЗ ===
        for phrase in self.DANGEROUS_PHRASES:
            if phrase in text_lower:
                self._increment_block(user_key)
                return {
                    "allowed": False,
                    "reason": f"Prompt injection: '{phrase}'",
                    "severity": "block",
                    "sanitized_text": None
                }

        # === ПРОВЕРКА ПАТТЕРНОВ INJECTION ===
        for pattern in self.injection_patterns:
            if pattern.search(text):
                self._increment_block(user_key)
                match = pattern.search(text).group(0)
                return {
                    "allowed": False,
                    "reason": f"Injection pattern: '{match[:30]}'",
                    "severity": "block",
                    "sanitized_text": None
                }

        # === ПРОВЕРКА МАНИПУЛЯЦИИ КОНТЕКСТОМ ===
        for pattern in self.context_patterns:
            if pattern.search(text):
                # Предупреждение, но не блок
                return {
                    "allowed": True,
                    "reason": f"Context manipulation attempt detected",
                    "severity": "warn",
                    "sanitized_text": self._sanitize(text)
                }

        # === САНИТИЗАЦИЯ И ПРОПУСК ===
        return {
            "allowed": True,
            "reason": None,
            "severity": None,
            "sanitized_text": self._sanitize(text)
        }

    def _increment_block(self, user_key: str):
        """Увеличивает счётчик блокировок"""
        self.blocked_count[user_key] = self.blocked_count.get(user_key, 0) + 1

    def _sanitize(self, text: str) -> str:
        """
        Санитизация текста перед отправкой в AI.
        Удаляет/экранирует опасные конструкции.
        """
        import re

        # Удаляем специальные токены
        sanitized = re.sub(r'<\|[^|]+\|>', '', text)

        # Экранируем тройные кавычки
        sanitized = sanitized.replace('```', '`​`​`')  # Zero-width space

        # Удаляем подозрительные разделители
        sanitized = re.sub(r'-{5,}', '---', sanitized)
        sanitized = re.sub(r'={5,}', '===', sanitized)

        return sanitized.strip()

    def reset_user(self, user_id: int):
        """Сбрасывает счётчик блокировок пользователя"""
        user_key = str(user_id)
        self.blocked_count.pop(user_key, None)
        self.ai_queries.pop(user_key, None)


# Глобальный экземпляр защиты Юноны
junona_guard = JunonaGuard()


# ═══════════════════════════════════════════════════════════════════════════════
#                    ATLANT GUARD — ЗАЩИТА УЗЛА/СЕРВЕРА
# ═══════════════════════════════════════════════════════════════════════════════

class AtlantGuard:
    """
    Защита Атланта (узла Montana) от сетевых атак.

    Мониторит:
    - DDoS паттерны (аномальная частота запросов)
    - Sybil атаки (массовая регистрация)
    - Node impersonation (поддельные узлы)
    - Resource exhaustion (исчерпание ресурсов)
    - API abuse (злоупотребление API)
    - Consensus manipulation (манипуляция консенсусом)
    """

    def __init__(self):
        import time
        self.start_time = time.time()

        # === Счётчики атак ===
        self.request_log = {}  # {ip/user_id: [timestamps]}
        self.registration_log = []  # [timestamps] новых регистраций
        self.node_sync_log = {}  # {node_id: [timestamps]}
        self.api_calls = {}  # {endpoint: [timestamps]}
        self.suspicious_ips = set()
        self.blocked_ips = set()

        # === Пороги детекции ===
        self.MAX_REQUESTS_PER_MINUTE = 60  # Запросов/мин с одного источника
        self.MAX_REGISTRATIONS_PER_HOUR = 20  # Новых регистраций/час
        self.MAX_NODE_SYNCS_PER_MINUTE = 10  # Синхронизаций узла/мин
        self.MAX_API_CALLS_PER_MINUTE = 100  # API вызовов/мин на endpoint

        # === Состояние атаки ===
        self.under_attack = False
        self.attack_start_time = None
        self.attack_type = None
        self.attack_severity = None

        # === PQ-Failover ===
        self.last_failover_target = None  # Последний узел, на который переключились
        self.failover_count = 0  # Количество failover за сессию

        # === Метрики здоровья ===
        self.health_checks = []
        self.last_health_status = "healthy"

    def log_request(self, source_id: str) -> dict:
        """
        Логирует запрос и проверяет на DDoS.

        Returns:
            {"allowed": bool, "reason": str, "severity": str}
        """
        import time
        now = time.time()

        if source_id in self.blocked_ips:
            return {
                "allowed": False,
                "reason": f"IP заблокирован: {source_id}",
                "severity": "block"
            }

        if source_id not in self.request_log:
            self.request_log[source_id] = []

        self.request_log[source_id].append(now)
        # Оставляем только последнюю минуту
        self.request_log[source_id] = [
            t for t in self.request_log[source_id] if now - t < 60
        ]

        count = len(self.request_log[source_id])

        # === DDoS детекция ===
        if count > self.MAX_REQUESTS_PER_MINUTE:
            self.suspicious_ips.add(source_id)
            self._trigger_attack("DDoS", "high", f"Source: {source_id}, {count} req/min")

            if count > self.MAX_REQUESTS_PER_MINUTE * 2:
                self.blocked_ips.add(source_id)
                return {
                    "allowed": False,
                    "reason": f"DDoS: {count} req/min → BLOCKED",
                    "severity": "critical"
                }

            return {
                "allowed": False,
                "reason": f"DDoS: {count} req/min",
                "severity": "high"
            }

        return {"allowed": True, "reason": None, "severity": None}

    def log_registration(self) -> dict:
        """
        Логирует новую регистрацию и проверяет на Sybil атаку.
        """
        import time
        now = time.time()

        self.registration_log.append(now)
        # Оставляем только последний час
        self.registration_log = [t for t in self.registration_log if now - t < 3600]

        count = len(self.registration_log)

        if count > self.MAX_REGISTRATIONS_PER_HOUR:
            self._trigger_attack("Sybil", "high", f"{count} регистраций/час")
            return {
                "allowed": False,
                "reason": f"Sybil: {count} регистраций/час",
                "severity": "high"
            }

        if count > self.MAX_REGISTRATIONS_PER_HOUR * 0.7:
            return {
                "allowed": True,
                "reason": f"Sybil warning: {count} регистраций/час",
                "severity": "warn"
            }

        return {"allowed": True, "reason": None, "severity": None}

    def log_node_sync(self, node_id: str) -> dict:
        """
        Логирует синхронизацию узла и проверяет на манипуляцию.
        """
        import time
        now = time.time()

        if node_id not in self.node_sync_log:
            self.node_sync_log[node_id] = []

        self.node_sync_log[node_id].append(now)
        self.node_sync_log[node_id] = [
            t for t in self.node_sync_log[node_id] if now - t < 60
        ]

        count = len(self.node_sync_log[node_id])

        if count > self.MAX_NODE_SYNCS_PER_MINUTE:
            self._trigger_attack("NodeSpam", "medium", f"Node: {node_id}, {count} sync/min")
            return {
                "allowed": False,
                "reason": f"Node spam: {count} sync/min",
                "severity": "medium"
            }

        return {"allowed": True, "reason": None, "severity": None}

    def log_api_call(self, endpoint: str) -> dict:
        """
        Логирует API вызов и проверяет на abuse.
        """
        import time
        now = time.time()

        if endpoint not in self.api_calls:
            self.api_calls[endpoint] = []

        self.api_calls[endpoint].append(now)
        self.api_calls[endpoint] = [
            t for t in self.api_calls[endpoint] if now - t < 60
        ]

        count = len(self.api_calls[endpoint])

        if count > self.MAX_API_CALLS_PER_MINUTE:
            self._trigger_attack("APIAbuse", "medium", f"Endpoint: {endpoint}, {count}/min")
            return {
                "allowed": False,
                "reason": f"API abuse: {endpoint} ({count}/min)",
                "severity": "medium"
            }

        return {"allowed": True, "reason": None, "severity": None}

    def _trigger_attack(self, attack_type: str, severity: str, details: str):
        """
        Триггерит состояние атаки.

        При атаке:
        1. Устанавливает флаг under_attack
        2. Запускает PQ-failover (смена мастера на случайного)
        3. Уведомляет владельца
        """
        import time

        was_under_attack = self.under_attack

        if not self.under_attack:
            self.under_attack = True
            self.attack_start_time = time.time()
            self.attack_type = attack_type
            self.attack_severity = severity

        # Логируем
        logger.warning(f"🚨 ATLANT ATTACK: {attack_type} [{severity}] - {details}")

        # === PQ-FAILOVER: Смена мастера на случайного ===
        if not was_under_attack:  # Только при первом срабатывании
            self._trigger_pq_failover(attack_type, details)

    def _trigger_pq_failover(self, attack_type: str, details: str):
        """
        Запускает постквантовый failover — смена мастера на случайного.

        ML-DSA-65 используется для генерации непредсказуемого порядка.
        """
        try:
            from leader_election import get_leader_election
            leader = get_leader_election()

            if leader:
                logger.warning(f"🔐 PQ-FAILOVER: Запуск смены мастера...")

                # Триггерим shuffle с external_trigger=True
                leader.shuffle_chain_on_attack(external_trigger=True)

                # Получаем нового первого в цепочке
                if leader.chain:
                    new_first = leader.chain[0][0]
                    logger.warning(f"🎲 PQ-FAILOVER: Новый порядок, первый = {new_first}")

                    # Сохраняем для уведомления
                    self.last_failover_target = new_first
                    self.failover_count += 1
                else:
                    logger.error("❌ PQ-FAILOVER: Нет доступных узлов!")

        except Exception as e:
            logger.error(f"❌ PQ-FAILOVER ошибка: {e}")

    def clear_attack(self):
        """Сбрасывает состояние атаки"""
        self.under_attack = False
        self.attack_start_time = None
        self.attack_type = None
        self.attack_severity = None

    def check_majority_attack(self) -> dict:
        """
        Проверяет атаку на большинство узлов.

        Returns:
            {
                "is_majority_attack": bool,
                "healthy_nodes": int,
                "total_nodes": int,
                "pulse_mode": dict или None
            }
        """
        try:
            from leader_election import get_leader_election
            leader = get_leader_election()

            if not leader:
                return {"is_majority_attack": False, "healthy_nodes": 0, "total_nodes": 0, "pulse_mode": None}

            is_majority, healthy, total = leader.check_majority_under_attack()

            result = {
                "is_majority_attack": is_majority,
                "healthy_nodes": healthy,
                "total_nodes": total,
                "pulse_mode": None
            }

            if is_majority:
                # Получаем конфигурацию pulse mode
                pulse_config = leader.enter_pulse_mode()
                result["pulse_mode"] = pulse_config

            return result

        except Exception as e:
            logger.error(f"Majority attack check error: {e}")
            return {"is_majority_attack": False, "healthy_nodes": 0, "total_nodes": 0, "pulse_mode": None}

    def health_check(self) -> dict:
        """
        Проверка здоровья Атланта.

        Returns:
            {
                "status": "healthy" | "degraded" | "under_attack",
                "uptime": int (секунды),
                "metrics": {...}
            }
        """
        import time
        import psutil
        now = time.time()

        # Базовые метрики
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "active_connections": len(self.request_log),
                "blocked_ips": len(self.blocked_ips),
                "suspicious_ips": len(self.suspicious_ips)
            }
        except Exception:
            metrics = {
                "active_connections": len(self.request_log),
                "blocked_ips": len(self.blocked_ips),
                "suspicious_ips": len(self.suspicious_ips)
            }

        # Определяем статус
        if self.under_attack:
            status = "under_attack"
        elif metrics.get("cpu_percent", 0) > 90 or metrics.get("memory_percent", 0) > 90:
            status = "degraded"
        elif len(self.suspicious_ips) > 5:
            status = "degraded"
        else:
            status = "healthy"

        self.last_health_status = status

        return {
            "status": status,
            "uptime": int(now - self.start_time),
            "under_attack": self.under_attack,
            "attack_type": self.attack_type,
            "metrics": metrics
        }

    def get_threat_report(self) -> str:
        """Генерирует отчёт об угрозах"""
        import time
        now = time.time()

        health = self.health_check()

        report = f"""🏛 **ATLANT THREAT REPORT**

**Статус:** {health['status'].upper()}
**Uptime:** {health['uptime'] // 3600}h {(health['uptime'] % 3600) // 60}m

**Активные угрозы:**
• Под атакой: {'ДА' if self.under_attack else 'Нет'}
• Тип атаки: {self.attack_type or 'N/A'}
• Severity: {self.attack_severity or 'N/A'}

**IP статистика:**
• Подозрительных: {len(self.suspicious_ips)}
• Заблокированных: {len(self.blocked_ips)}

**Метрики:**
• CPU: {health['metrics'].get('cpu_percent', 'N/A')}%
• Memory: {health['metrics'].get('memory_percent', 'N/A')}%
• Connections: {health['metrics'].get('active_connections', 0)}

**Регистрации/час:** {len(self.registration_log)}
"""
        return report

    def unblock_ip(self, ip: str):
        """Разблокирует IP"""
        self.blocked_ips.discard(ip)
        self.suspicious_ips.discard(ip)

    def reset_all(self):
        """Полный сброс всех блокировок"""
        self.blocked_ips.clear()
        self.suspicious_ips.clear()
        self.request_log.clear()
        self.registration_log.clear()
        self.node_sync_log.clear()
        self.api_calls.clear()
        self.clear_attack()


# Глобальный экземпляр защиты Атланта
atlant_guard = AtlantGuard()


async def send_atlant_alert(bot, alert_type: str, details: str, severity: str = "high"):
    """
    Отправляет алерт владельцу об атаке на Атлант.
    """
    severity_emoji = {
        "low": "🟡",
        "medium": "🟠",
        "high": "🔴",
        "critical": "⚫"
    }

    emoji = severity_emoji.get(severity, "⚪")
    health = atlant_guard.health_check()

    # Информация о PQ-failover
    failover_info = ""
    if atlant_guard.last_failover_target:
        failover_info = f"""
**🔐 PQ-FAILOVER АКТИВИРОВАН**
• Новый мастер: **{atlant_guard.last_failover_target}**
• Алгоритм: ML-DSA-65
• Failover #: {atlant_guard.failover_count}
"""

    alert_text = f"""
{emoji} **ATLANT ALERT** {emoji}

**Тип:** {alert_type}
**Severity:** {severity.upper()}
**Детали:** {details}
{failover_info}
**Статус узла:** {health['status']}
**Uptime:** {health['uptime'] // 60} мин

**Заблокировано IP:** {len(atlant_guard.blocked_ips)}
**Подозрительных:** {len(atlant_guard.suspicious_ips)}

**Команды:**
/atlant — полный отчёт
/resetatlant — сбросить блокировки
"""

    try:
        await bot.send_message(
            chat_id=BOT_CREATOR_ID,
            text=alert_text,
            parse_mode="Markdown"
        )
        logger.warning(f"🏛 Atlant alert sent: {alert_type}")
    except Exception as e:
        logger.error(f"Failed to send atlant alert: {e}")


async def send_pulse_mode_alert(bot, pulse_config: dict, healthy: int, total: int):
    """
    Отправляет алерт о входе в режим пульсации.

    Args:
        bot: Telegram bot instance
        pulse_config: Конфигурация pulse mode
        healthy: Количество здоровых узлов
        total: Общее количество узлов
    """
    if not pulse_config:
        return

    pulse_order = pulse_config.get("pulse_order", [])
    my_slot = pulse_config.get("my_pulse_slot", 0)
    pulse_duration = pulse_config.get("pulse_duration", 30)
    sleep_duration = pulse_config.get("sleep_duration", 60)

    alert_text = f"""
💓 **PULSE MODE ACTIVATED** 💓

**🚨 АТАКА НА БОЛЬШИНСТВО УЗЛОВ**
• Недоступно: {total - healthy}/{total} узлов
• Здоровых: {healthy}/{total}

**💓 РЕЖИМ ПУЛЬСАЦИИ**
Сеть "засыпает" и начинает пульсировать поочерёдно.
Только один узел активен в момент времени.

**Порядок пульсации (PQ-random):**
{' → '.join(pulse_order)}

**Тайминг:**
• Пульс: {pulse_duration} сек
• Сон: {sleep_duration} сек
• Цикл: {len(pulse_order) * pulse_duration + sleep_duration} сек

**Мой слот:** #{my_slot + 1}/{len(pulse_order)}

**Алгоритм:** ML-DSA-65 (постквантовый)

⚠️ Атакующий НЕ может предсказать порядок узлов.
"""

    try:
        await bot.send_message(
            chat_id=BOT_CREATOR_ID,
            text=alert_text,
            parse_mode="Markdown"
        )
        logger.warning(f"💓 Pulse mode alert sent")
    except Exception as e:
        logger.error(f"Failed to send pulse mode alert: {e}")


async def send_security_alert(
    bot,
    user_id: int,
    username: str,
    reason: str,
    severity: str,
    message_preview: str = None
):
    """
    Отправляет алерт владельцу Атланта о подозрительной активности.

    Args:
        bot: Telegram bot instance
        user_id: ID подозрительного пользователя
        username: Username пользователя
        reason: Причина алерта
        severity: low/medium/high
        message_preview: Превью сообщения (опционально)
    """
    severity_emoji = {
        "low": "🟡",
        "medium": "🟠",
        "high": "🔴"
    }

    emoji = severity_emoji.get(severity, "⚪")

    alert_text = f"""
{emoji} **SECURITY ALERT** {emoji}

**Уровень:** {severity.upper()}
**Причина:** {reason}

**Пользователь:**
- ID: `{user_id}`
- Username: @{username or 'нет'}

**Превью:** {message_preview[:50] + '...' if message_preview and len(message_preview) > 50 else message_preview or 'N/A'}

**Действия:**
/flag_{user_id} — пометить
/unflag_{user_id} — снять флаг
/ban_{user_id} — заблокировать
"""

    try:
        await bot.send_message(
            chat_id=BOT_CREATOR_ID,
            text=alert_text,
            parse_mode="Markdown"
        )
        security_monitor.mark_alert_sent(user_id)
        logger.warning(f"🚨 Security alert sent: {reason} (user={user_id})")
    except Exception as e:
        logger.error(f"Failed to send security alert: {e}")


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


async def resetguard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /resetguard <user_id> — сбросить блокировку JunonaGuard.
    Только для владельца бота.
    """
    user_id = update.effective_user.id

    if user_id != BOT_CREATOR_ID:
        await update.message.reply_text("Ɉ\n\nКоманда доступна только владельцу.")
        return

    # Получаем user_id из аргументов
    args = context.args
    if not args:
        # Показываем статистику блокировок
        blocked = junona_guard.blocked_count
        flagged = security_monitor.flagged_users

        text = f"""Ɉ

**🛡 JunonaGuard Status**

**Заблокированные (AI):** {len(blocked)}
"""
        for uid, count in blocked.items():
            text += f"• `{uid}`: {count} попыток\n"

        text += f"\n**Помеченные (Security):** {len(flagged)}\n"
        for uid in flagged:
            text += f"• `{uid}`\n"

        text += f"\n**Использование:**\n`/resetguard <user_id>` — сбросить блок"

        await update.message.reply_text(text, parse_mode="Markdown")
        return

    target_id = args[0]
    try:
        target_id = int(target_id)
    except ValueError:
        await update.message.reply_text("Ɉ\n\nНеверный формат user_id")
        return

    # Сбрасываем
    junona_guard.reset_user(target_id)
    security_monitor.unflag_user(target_id)

    await update.message.reply_text(
        f"Ɉ\n\n✅ Сброшены блокировки для `{target_id}`",
        parse_mode="Markdown"
    )


async def atlant_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /atlant — статус защиты Атланта.
    Только для владельца бота.
    """
    user_id = update.effective_user.id

    if user_id != BOT_CREATOR_ID:
        await update.message.reply_text("Ɉ\n\nКоманда доступна только владельцу.")
        return

    # Генерируем отчёт
    report = atlant_guard.get_threat_report()

    # Добавляем кнопки
    keyboard = [
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="atlant_refresh"),
            InlineKeyboardButton("🧹 Сбросить", callback_data="atlant_reset")
        ],
        [
            InlineKeyboardButton("🚫 Blocked IPs", callback_data="atlant_blocked")
        ]
    ]

    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def resetatlant_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /resetatlant — сбросить все блокировки Атланта.
    Только для владельца бота.
    """
    user_id = update.effective_user.id

    if user_id != BOT_CREATOR_ID:
        await update.message.reply_text("Ɉ\n\nКоманда доступна только владельцу.")
        return

    args = context.args

    if args and args[0] == "confirm":
        # Полный сброс
        atlant_guard.reset_all()
        await update.message.reply_text(
            "Ɉ\n\n✅ Все блокировки Атланта сброшены.\n\n"
            "• Blocked IPs: 0\n"
            "• Suspicious IPs: 0\n"
            "• Attack status: cleared"
        )
    else:
        # Показываем что сбрасывается
        health = atlant_guard.health_check()
        await update.message.reply_text(
            f"Ɉ\n\n⚠️ **Сброс блокировок Атланта**\n\n"
            f"Будет сброшено:\n"
            f"• Blocked IPs: {len(atlant_guard.blocked_ips)}\n"
            f"• Suspicious IPs: {len(atlant_guard.suspicious_ips)}\n"
            f"• Attack status: {atlant_guard.attack_type or 'none'}\n\n"
            f"Для подтверждения:\n`/resetatlant confirm`",
            parse_mode="Markdown"
        )


async def handle_atlant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок /atlant"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id != BOT_CREATOR_ID:
        return

    action = query.data

    if action == "atlant_refresh":
        report = atlant_guard.get_threat_report()
        keyboard = [
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="atlant_refresh"),
                InlineKeyboardButton("🧹 Сбросить", callback_data="atlant_reset")
            ],
            [
                InlineKeyboardButton("🚫 Blocked IPs", callback_data="atlant_blocked")
            ]
        ]
        await query.edit_message_text(
            report,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == "atlant_reset":
        atlant_guard.reset_all()
        await query.edit_message_text(
            "Ɉ\n\n✅ Все блокировки Атланта сброшены.",
            parse_mode="Markdown"
        )

    elif action == "atlant_blocked":
        blocked = atlant_guard.blocked_ips
        suspicious = atlant_guard.suspicious_ips

        text = f"Ɉ\n\n**🚫 Заблокированные IP**\n\n"
        if blocked:
            for ip in list(blocked)[:20]:
                text += f"• `{ip}`\n"
        else:
            text += "_Нет заблокированных_\n"

        text += f"\n**⚠️ Подозрительные IP**\n\n"
        if suspicious:
            for ip in list(suspicious)[:20]:
                text += f"• `{ip}`\n"
        else:
            text += "_Нет подозрительных_\n"

        await query.edit_message_text(text, parse_mode="Markdown")


async def handle_stat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок управления из /stat"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # ПРИСУТСТВИЕ = ВЗАИМОДЕЙСТВИЕ
    time_bank.activity(str(user_id), "telegram")

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

    # ПРИСУТСТВИЕ = ВЗАИМОДЕЙСТВИЕ
    time_bank.activity(str(user_id), "telegram")

    data = query.data  # "chapter_0_text"

    parts = data.split("_")
    chapter_num = int(parts[1])
    format_choice = parts[2]

    await send_chapter(query, user_id, chapter_num, format_choice)


async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка одобрения/отклонения пользователя"""
    query = update.callback_query
    await query.answer()

    # ПРИСУТСТВИЕ = ВЗАИМОДЕЙСТВИЕ
    time_bank.activity(str(query.from_user.id), "telegram")

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

    # СРАЗУ заменяем кнопку "Start" на меню команд (для ВСЕХ)
    try:
        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonCommands()
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить кнопку меню: {e}")

    # ПРИСУТСТВИЕ = ВЗАИМОДЕЙСТВИЕ
    time_bank.activity(str(user_id), "telegram")

    # Проверяем - новый пользователь или возвращается
    users = load_users()
    is_new_user = str(user_id) not in users

    # Загружаем или создаём данные пользователя
    if is_new_user:
        # === ATLANT GUARD: Защита от Sybil атаки ===
        sybil_check = atlant_guard.log_registration()
        if not sybil_check["allowed"]:
            logger.warning(f"🏛 AtlantGuard Sybil block: {sybil_check['reason']}")

            # Алерт владельцу
            await send_atlant_alert(
                context.bot,
                "SYBIL ATTACK",
                sybil_check["reason"],
                "high"
            )

            await update.message.reply_text(
                "Ɉ\n\n⚠️ Сервер перегружен. Попробуй позже."
            )
            return

        if sybil_check["severity"] == "warn":
            # Предупреждение владельцу о приближении к порогу
            logger.warning(f"⚠️ Sybil warning: {sybil_check['reason']}")

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
        # Минимальное меню для ожидающих (чтобы MenuButtonCommands работал)
        try:
            from telegram import BotCommandScopeChat
            await context.bot.set_my_commands(
                [BotCommand("start", "⏳ Статус")],
                scope=BotCommandScopeChat(chat_id=chat_id)
            )
        except:
            pass

        # Короткое сообщение без AI, без записи в память
        await update.message.reply_text(
            f"Ɉ\n\n⏳ Запрос на модерации.\n\nОжидай."
        )
        return

    # 2. Отклонён — минимальный ответ
    if not user_data.get('approved', False):
        # Минимальное меню для отклонённых
        try:
            from telegram import BotCommandScopeChat
            await context.bot.set_my_commands(
                [BotCommand("start", "❌ Статус")],
                scope=BotCommandScopeChat(chat_id=chat_id)
            )
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
        # Заменяем кнопку "Start" на меню команд
        await context.bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonCommands()
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

    # === ATLANT GUARD: Защита узла от DDoS ===
    ddos_check = atlant_guard.log_request(str(user_id))
    if not ddos_check["allowed"]:
        logger.warning(f"🏛 AtlantGuard blocked: {ddos_check['reason']} (user={user_id})")

        # Алерт при критическом уровне
        if ddos_check["severity"] == "critical":
            await send_atlant_alert(
                context.bot,
                "DDoS DETECTED",
                f"User {user_id} blocked: {ddos_check['reason']}",
                "critical"
            )

        # Молча игнорируем
        return

    # === ATLANT GUARD: Проверка под атакой ===
    if atlant_guard.under_attack:
        # В режиме атаки — только базовые функции
        logger.info(f"⚠️ Atlant under attack, limited mode for user {user_id}")

    # ПРИСУТСТВИЕ = ВЗАИМОДЕЙСТВИЕ
    # Каждое сообщение = доказательство присутствия
    presence_result = time_bank.activity(str(user_id), "telegram")

    # Уведомление о начале присутствия
    if presence_result["is_new"]:
        # Новая сессия — показываем краткое уведомление
        await update.message.reply_text(
            "Ɉ Присутствие активно. +1 Ɉ/сек"
        )
    elif presence_result["was_paused"]:
        # Возобновление после паузы
        await update.message.reply_text(
            f"Ɉ Присутствие возобновлено. Накоплено: {presence_result['t2_seconds']} Ɉ"
        )

    # === SECURITY: Детекция подозрительной активности ===
    security_check = security_monitor.check_activity(user_id, text)
    if security_check["is_suspicious"]:
        # Помечаем пользователя
        security_monitor.flag_user(user_id)

        # Отправляем алерт владельцу (с cooldown)
        if security_monitor.should_send_alert(user_id):
            await send_security_alert(
                bot=context.bot,
                user_id=user_id,
                username=user.username,
                reason=security_check["reason"],
                severity=security_check["severity"],
                message_preview=text
            )

        # При высокой угрозе — не обрабатываем сообщение
        if security_check["severity"] == "high":
            logger.warning(f"🚫 Blocked message from flagged user {user_id}")
            return

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
        # === JUNONA GUARD: Корневая защита AI ===
        guard_result = junona_guard.check(user_id, text)

        if not guard_result["allowed"]:
            # Блокируем атаку на AI
            logger.warning(f"🛡 JunonaGuard blocked: {guard_result['reason']} (user={user_id})")

            # Отправляем алерт владельцу
            if security_monitor.should_send_alert(user_id):
                await send_security_alert(
                    bot=context.bot,
                    user_id=user_id,
                    username=user.username,
                    reason=f"AI ATTACK: {guard_result['reason']}",
                    severity="high",
                    message_preview=text
                )

            # Отвечаем пользователю
            if guard_result["severity"] == "block":
                await update.message.reply_text(
                    "Ɉ\n\nЯ не отвечаю на такие запросы."
                )
            else:
                await update.message.reply_text(
                    "Ɉ\n\nПодожди немного перед следующим сообщением."
                )
            return

        # Предупреждение (но пропускаем)
        if guard_result["severity"] == "warn":
            logger.info(f"⚠️ JunonaGuard warning: {guard_result['reason']} (user={user_id})")

        # Используем санитизированный текст
        safe_text = guard_result["sanitized_text"]

        try:
            # Детектируем категории вопросов для запроса к БД
            text_lower = safe_text.lower()

            # Категории для запроса к БД
            is_about_balance = any(word in text_lower for word in [
                'баланс', 'сколько', 'монет', 'секунд', 'заработ', 'кошел', 'мой'
            ])
            is_about_tokenomics = any(word in text_lower for word in [
                'начисл', 'эмиссия', 't2', 'присутств', 'халвинг', 'протокол', 'τ'
            ])
            is_about_transactions = any(word in text_lower for word in [
                'транзакц', 'перевод', 'отправ', 'получ', 'история', 'tx'
            ])
            is_about_thoughts = any(word in text_lower for word in [
                'мысл', 'запис', 'помн', 'память', 'говорил', 'диалог', 'гиппокамп'
            ])
            is_about_network = any(word in text_lower for word in [
                'узл', 'сеть', 'атлант', 'сервер', 'node', 'amsterdam', 'moscow'
            ])
            is_about_book = any(word in text_lower for word in [
                'глав', 'книг', 'читать', 'белая', 'материал'
            ])

            needs_db_query = any([
                is_about_balance, is_about_tokenomics, is_about_transactions,
                is_about_thoughts, is_about_network, is_about_book
            ])

            # Готовим контекст для Юноны
            user_context = {
                'name': user.first_name,
                'lang': 'ru'
            }

            # ЗАПРОС К БД: Собираем данные по категориям
            if needs_db_query:
                address = str(user_id)
                db_context_parts = ["ТЫ — ЮНОНА, АГЕНТ MONTANA PROTOCOL.\n\nДАННЫЕ ИЗ БАЗЫ НА МОМЕНТ ЗАПРОСА:"]

                # === БАЛАНС И ТОКЕНОМИКА ===
                if is_about_balance or is_about_tokenomics:
                    balance_info = time_bank.get_balance_with_pending(address)
                    confirmed = balance_info["confirmed"]
                    pending = balance_info["pending"]
                    total = balance_info["total"]

                    presence_info = time_bank.get(address)
                    presence_seconds = presence_info.get('presence_seconds', 0) if presence_info else 0
                    t2_seconds = presence_info.get('t2_seconds', 0) if presence_info else 0
                    is_active = presence_info.get('is_active', False) if presence_info else False

                    stats = time_bank.stats()
                    t2_remaining = stats.get('t2_remaining_sec', 0)
                    t2_count = stats.get('t2_count', 0)
                    halving = stats.get('halving_coefficient', 1.0)

                    db_context_parts.append(f"""
КОШЕЛЕК ПОЛЬЗОВАТЕЛЯ:
- Адрес: {address}
- Подтверждённый баланс: {confirmed} Ɉ
- Накапливается (pending): {pending} Ɉ
- ИТОГО: {total} Ɉ

ПРИСУТСТВИЕ:
- Статус: {'АКТИВНО (+1 Ɉ/сек)' if is_active else 'ПАУЗА (нет активности > 1 мин)'}
- Секунд в сессии: {presence_seconds}
- Секунд в T2: {t2_seconds}

ПРОТОКОЛ TIME_BANK:
- τ₁ = 1 минута (интервал проверки)
- T2 = 10 минут (слайс)
- До подтверждения: {t2_remaining} сек
- T2 index: #{t2_count}
- Халвинг: {halving}x""")

                # === ТРАНЗАКЦИИ ===
                if is_about_transactions:
                    from montana_db import get_db
                    db = get_db()
                    txs = db.my_txs(address, limit=5)
                    tx_list = "\n".join([f"  {t['timestamp'][:10]} {t['direction']} {t['type']}" for t in txs]) if txs else "  Нет транзакций"
                    db_context_parts.append(f"""
ТРАНЗАКЦИИ (последние 5):
{tx_list}""")

                # === МЫСЛИ / ПАМЯТЬ ===
                if is_about_thoughts:
                    from montana_db import get_db
                    db = get_db()
                    thoughts = db.get_thoughts(user_id, limit=5)
                    thoughts_list = "\n".join([f"  [{t['timestamp'][:10]}] {t['message'][:50]}..." for t in thoughts]) if thoughts else "  Нет записей"
                    db_context_parts.append(f"""
ГИППОКАМП (последние 5 мыслей):
{thoughts_list}""")

                # === СЕТЬ / УЗЛЫ ===
                if is_about_network:
                    try:
                        from node_crypto import get_node_crypto_system
                        node_system = get_node_crypto_system()
                        nodes = node_system.get_all_nodes()
                        nodes_list = "\n".join([f"  {n['location']} — {n['alias']} ({n['type']})" for n in nodes[:5]]) if nodes else "  Нет узлов"
                        db_context_parts.append(f"""
СЕТЬ MONTANA (узлы):
{nodes_list}
Всего узлов: {len(nodes)}""")
                    except Exception:
                        db_context_parts.append("\nСЕТЬ: Данные узлов недоступны")

                # === КНИГА ===
                if is_about_book:
                    progress = atlant.get_context(user_id, "chapter_progress") or {}
                    next_ch = atlant.get_next_chapter(user_id)
                    chapters_read = len([k for k, v in progress.items() if v == "read"])
                    db_context_parts.append(f"""
КНИГА MONTANA:
- Глав прочитано: {chapters_read}
- Следующая глава: {next_ch if next_ch is not None else 'Все прочитаны'}""")

                # Добавляем правила ответа
                db_context_parts.append("""
ПРАВИЛА ОТВЕТА:
1. Отвечай ТОЧНЫМИ ДАННЫМИ из контекста выше
2. Не придумывай цифры — только из БД
3. Будь краткой и конкретной""")

                user_context['montana_agent_mode'] = True
                user_context['system_instruction'] = "\n".join(db_context_parts)

            response = await junona.respond(safe_text, user_context, history)

            # Сохраняем в историю (санитизированный текст)
            history.append({"role": "user", "content": safe_text})
            history.append({"role": "assistant", "content": response})

            # Оставляем только последние 10 сообщений
            user_data['history'] = history[-10:]
            save_user(user_id, user_data)

            # Записываем ответ Юноны
            atlant.add_message(user_id, "junona", response)

            await update.message.reply_text(f"Ɉ\n\n{response}")

            # Проверяем - просил ли пользователь материалы ЯВНО?
            if is_asking_for_materials(safe_text):
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

    # Устанавливаем глобальную кнопку меню (вместо "Start")
    try:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("✅ Глобальная кнопка меню = MenuButtonCommands")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить глобальную кнопку меню: {e}")

    logger.info(f"✅ Установлено {len(BOT_COMMANDS)} команд в меню")

# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ═══════════════════════════════════════════════════════════════════════════════

# Глобальные переменные для управления polling
_application = None
_polling_task = None
_polling_lock = threading.Lock()  # Защита от одновременных вызовов start/stop_polling
_is_polling = False  # Флаг состояния polling
_atlant_presence_task = None  # Задача присутствия Атланта


async def atlant_presence_loop():
    """
    АТЛАНТ ВСЕГДА ПРИСУТСТВУЕТ

    Атлант — это сервер/узел Montana. Пока он работает, он присутствует.
    Активность каждые 60 секунд поддерживает присутствие.
    Проверка здоровья каждые 5 минут.
    """
    # Получаем адрес узла (NODE_NAME из env или имя хоста)
    node_name = os.getenv("NODE_NAME", "local")
    atlant_address = f"atlant_{node_name}"

    logger.info(f"🏛 АТЛАНТ присутствует: {atlant_address}")

    # Начинаем присутствие
    time_bank.start(atlant_address, "atlant")

    health_check_counter = 0
    last_health_status = "healthy"

    while _is_polling:
        # Атлант всегда активен пока работает
        time_bank.activity(atlant_address, "atlant")

        # Проверка здоровья каждые 5 минут (5 итераций по 60 сек)
        health_check_counter += 1
        if health_check_counter >= 5:
            health_check_counter = 0
            health = atlant_guard.health_check()

            # Алерт при изменении статуса на плохой
            if health["status"] != last_health_status:
                if health["status"] in ["degraded", "under_attack"]:
                    logger.warning(f"🏛 Atlant status changed: {last_health_status} → {health['status']}")

                    # Алерт владельцу (если есть application)
                    if _application and _application.bot:
                        try:
                            await send_atlant_alert(
                                _application.bot,
                                f"STATUS: {health['status'].upper()}",
                                f"CPU: {health['metrics'].get('cpu_percent', 'N/A')}%, "
                                f"Mem: {health['metrics'].get('memory_percent', 'N/A')}%",
                                "high" if health["status"] == "under_attack" else "medium"
                            )
                        except Exception as e:
                            logger.error(f"Failed to send health alert: {e}")

                elif health["status"] == "healthy" and last_health_status != "healthy":
                    logger.info(f"🏛 Atlant recovered: {last_health_status} → healthy")

                last_health_status = health["status"]

        await asyncio.sleep(60)  # Пинг каждую минуту

    # Завершаем присутствие при остановке
    time_bank.end(atlant_address)
    logger.info(f"🏛 АТЛАНТ завершил присутствие: {atlant_address}")


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
        _application.add_handler(CommandHandler("resetguard", resetguard_cmd))
        _application.add_handler(CommandHandler("atlant", atlant_cmd))
        _application.add_handler(CommandHandler("resetatlant", resetatlant_cmd))
        _application.add_handler(CallbackQueryHandler(handle_chapter_choice, pattern="^chapter_"))
        _application.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject)_"))
        _application.add_handler(CallbackQueryHandler(handle_stat_callback, pattern="^stat_"))
        _application.add_handler(CallbackQueryHandler(handle_atlant_callback, pattern="^atlant_"))
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

        # Запускаем присутствие Атланта
        global _atlant_presence_task
        _atlant_presence_task = asyncio.create_task(atlant_presence_loop())

        logger.info("✅ Polling запущен")

    except Exception as e:
        logger.error(f"❌ Ошибка запуска polling: {e}")
        with _polling_lock:
            _is_polling = False
        raise


async def stop_polling():
    """Остановить polling (вызывается когда узел ушёл в standby)"""
    global _application, _polling_task, _is_polling, _atlant_presence_task

    # Сбрасываем флаг polling (это остановит atlant_presence_loop)
    with _polling_lock:
        _is_polling = False

    # Ждём завершения задачи присутствия Атланта
    if _atlant_presence_task:
        try:
            await asyncio.wait_for(_atlant_presence_task, timeout=5)
        except asyncio.TimeoutError:
            _atlant_presence_task.cancel()
        _atlant_presence_task = None

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

    # Запускаем Breathing Sync — синхронизация данных между узлами
    breathing = get_breathing_sync()
    breathing_task = asyncio.create_task(breathing.run_breathing_loop())
    logger.info(f"🫁 Breathing Sync активирован (каждые 12 сек)")

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
