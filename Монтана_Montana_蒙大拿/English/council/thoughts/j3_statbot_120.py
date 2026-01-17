


#j3_statbot_120



from dotenv import load_dotenv
import os
import logging
import json
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, KeyboardButton
from telegram.error import TelegramError, NetworkError, Conflict, TimedOut, RetryAfter, Forbidden, BadRequest
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import asyncio
import csv
from collections import defaultdict
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from io import BytesIO
import mplfinance as mpf
import pandas as pd
from urllib.parse import urlencode
from flask import Flask, request
import requests
import shutil
import pytz
import numpy as np
import hmac
import hashlib
from urllib.parse import urlencode
import time
from datetime import datetime, timedelta, UTC, timezone
import datetime as dt 
from pybit.unified_trading import HTTP
import getpass
import subprocess



# Устанавливаем уровень логирования для httpx или urllib3
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
app = Flask(__name__)

class HttpxFilter(logging.Filter):
    def filter(self, record):
        return "httpx" not in record.getMessage() and "POST https://api.telegram.org" not in record.getMessage()

# Применяем фильтр к логгеру
logger = logging.getLogger()
logger.addFilter(HttpxFilter())

def log_event(event):
    global last_log_day
    
    # Инициализируем last_log_day, если он ещё не определён
    if 'last_log_day' not in globals():
        globals()['last_log_day'] = datetime.now().date()
    
    timestamp = datetime.now()
    current_day = timestamp.date()
    
    # Проверяем смену суток
    if current_day != last_log_day:
        globals()['last_log_day'] = current_day
    
    logging.info(f"{event}")

def get_server_time():
    try:
        response = client.get_server_time()
        if response['retCode'] == 0:
            server_time_ms = int(response['result']['timeSecond']) * 1000
            return datetime.fromtimestamp(server_time_ms / 1000, tz=timezone.utc)
        else:
            log_event(f"⚠️ Ошибка получения времени сервера: {response['retMsg']}")
            return datetime.now(timezone.utc)
    except Exception as e:
        # log_event(f"⚠️ Ошибка при получении времени сервера: {e}")  # Комментируем, чтобы избежать рекурсии если log_event вызывает это
        return datetime.now(timezone.utc)



# Переключатель авторизации: True - Bitwarden, False - .env файл
USE_BITWARDEN = True  # Измените на False для использования .env

if USE_BITWARDEN:
    # Оригинальный код для Bitwarden с улучшениями
    def get_session_key():
        logging.info("Пожалуйста, выполните команду `bw login --raw` в другом терминале.")
        logging.info("Введите email, пароль и код 2FA, затем вставьте полученный session key ниже.")
        logging.info("Если Bitwarden CLI не установлен, установите его: https://bitwarden.com/help/cli/")
        max_attempts = 3
        for attempt in range(max_attempts):
            session_key = getpass.getpass("Session key: ").strip()
            if session_key:
                return session_key
            else:
                logging.info(f"Session key не введён (попытка {attempt + 1}/{max_attempts}). Повторите ввод.")
        raise Exception("Session key не введён после нескольких попыток")

    def get_api_key_from_bitwarden(session_key, item_name):
        """
        Получает элемент (например, API-ключ) из Bitwarden по имени элемента.
        """
        cmd = ["bw", "get", "item", item_name, "--session", session_key]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=30)  # Добавлено ограничение времени для избежания зависаний
            if process.returncode != 0:
                error_msg = f"Ошибка при получении {item_name}: Код возврата {process.returncode}. Stderr: {stderr.strip()}. Stdout: {stdout.strip()}"
                log_event(error_msg)
                if process.returncode == 127:
                    log_event("⚠️ Bitwarden CLI не установлен на сервере. Установите его: https://bitwarden.com/help/cli/")
                if any(word in stderr.lower() for word in ['connection', 'network', 'timeout', 'dns']):
                    log_event("⚠️ Возможная проблема с соединением к Bitwarden. Проверьте интернет, firewall или VPN на сервере.")
                raise Exception(f"Не удалось получить {item_name} из Bitwarden: {stderr.strip()}")
            if not stdout.strip():
                log_event(f"Пустой вывод при получении {item_name} из Bitwarden")
                raise Exception(f"Не удалось получить {item_name} из Bitwarden: пустой ответ")
            item = json.loads(stdout)
            return item['notes']
        except subprocess.TimeoutExpired:
            process.kill()
            log_event(f"Таймаут при получении {item_name} из Bitwarden. Проверьте соединение.")
            raise Exception(f"Таймаут при получении {item_name} из Bitwarden")
        except json.JSONDecodeError as json_err:
            log_event(f"Ошибка парсинга JSON при получении {item_name}: {json_err}. Вывод: {stdout}")
            raise Exception(f"Ошибка парсинга ответа Bitwarden для {item_name}")

    # Выполняем вход и получаем session key
    try:
        session_key = get_session_key()
        logging.info(f"Получен session key. Выполните команду `bw logout` в другом терминале.")
    except Exception as e:
        logging.info(f"Произошла ошибка: {e}")
        exit(1)

    # Получение API-ключей из Bitwarden с использованием session key
    BYBIT_API_KEY = get_api_key_from_bitwarden(session_key, "api_key_copypro")
    BYBIT_API_SECRET = get_api_key_from_bitwarden(session_key, "private_key_api_bybit_copypro_20250609_212756")
    TELEGRAM_TOKEN_STAT_BOT = get_api_key_from_bitwarden(session_key, "telegram_token_stat_20250711_001626")

    # Проверка на успешность получения ключей
    if not BYBIT_API_KEY or not BYBIT_API_SECRET:
        log_event("⚠️ Один из API-ключей не получен из Bitwarden. Проверьте установку Bitwarden CLI и сессию.")
        exit(1)

    # Логирование для отладки (без полного показа ключей)
    log_event(f"Получен API_KEY: {BYBIT_API_KEY[:5]}... (длина: {len(BYBIT_API_KEY)})")
    log_event(f"Получен API_SECRET: {BYBIT_API_SECRET[:5]}... (длина: {len(BYBIT_API_SECRET)})")

    # Инициализация сессии Bybit с RSA
    client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,  # Приватный ключ RSA из Bitwarden
        rsa_authentication=True,      # Включаем RSA-аутентификацию
        testnet=False                 # Установите True для тестовой сети
    )

    # Проверка расхождения времени (после создания client)
    server_time = get_server_time()
    local_time = datetime.now(timezone.utc)
    time_diff = abs((server_time - local_time).total_seconds())
    if time_diff > 60:
        log_event(f"⚠️ Расхождение времени: локальное {local_time}, сервер Bybit {server_time} (разница {time_diff:.0f} сек). Это может вызвать ошибки с токенами Bitwarden. Синхронизируйте время сервера (NTP).")
else:
    load_dotenv()
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
    BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')
    TELEGRAM_TOKEN_STAT_BOT = os.getenv('TELEGRAM_TOKEN_STAT_BOT')
    
    client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,  # Приватный ключ RSA из Bitwarden
        rsa_authentication=False,      # Включаем RSA-аутентификацию
        testnet=False
    )








USERS_FILE = Path("stat_bot_users.json")
BOT_CREATOR_ID = 8552053404
TELEGRAM_GROUP_IDS = [-1002316863309] #-1002166580868, -1002427054698, -1002269484406
BACKUP_CHANNEL_ID = -1002829880813



# Глобальная переменная для хранения текущего баланса с учетом PnL
current_total_balance_with_pnl = None

# Функция для проверки, авторизован ли пользователь
def is_authorized(user_id: int) -> bool:
    if user_id == BOT_CREATOR_ID:
        return True
    users = load_users()
    user_data = users.get(str(user_id), {})
    return user_data.get('authorized', False)


# ═══════════════════════════════════════════════════════════════════════════════
# 🏔 MONTANA CLAN AUTHORIZATION SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

# Состояния для ConversationHandler
CLAN_WAITING_LETTER = 1
CLAN_WAITING_INVITER = 2

# Хранилище pending запросов на вход в клан
pending_clan_requests = {}

# 🏔 MONTANA: Определение языка пользователя (только 3: RU/EN/ZH)
def detect_user_language(user) -> str:
    """Определяет язык: ru, en или zh"""
    lang_code = getattr(user, 'language_code', 'en') or 'en'
    lang_code = lang_code.lower()[:2]
    if lang_code in ['ru', 'uk', 'be', 'kk']:
        return 'ru'
    elif lang_code in ['zh', 'ja', 'ko']:
        return 'zh'
    return 'en'

# 🏔 MONTANA: Тексты на 3 языках
JUNONA_TEXTS = {
    'welcome_clan': {
        'ru': "🏔 *Привет, {name}!*\n\nТы в Клане Montana.\n\n金元Ɉ _Время — деньги буквально._",
        'en': "🏔 *Hello, {name}!*\n\nYou are in Montana Clan.\n\n金元Ɉ _Time is money literally._",
        'zh': "🏔 *你好，{name}！*\n\n你在Montana部落里。\n\n金元Ɉ _时间就是金钱。_"
    },
    'welcome_guest': {
        'ru': "🏔 *Привет!*\n\nЯ — Юнона, AI-хранитель Montana.\nТы ещё не в Клане.\n\n👇 *Вступить:*",
        'en': "🏔 *Hello!*\n\nI am Junona, AI guardian of Montana.\nYou are not in the Clan yet.\n\n👇 *Join:*",
        'zh': "🏔 *你好！*\n\n我是朱诺娜，Montana的AI守护者。\n你还不在部落里。\n\n👇 *加入：*"
    },
    'join_btn': {
        'ru': "🏔 Вступить в Клан",
        'en': "🏔 Join the Clan",
        'zh': "🏔 加入部落"
    },
    'join_form': {
        'ru': "📝 *ЗАЯВКА В КЛАН MONTANA*\n\nРасскажи о себе:\n• Кто ты?\n• Откуда?\n• Почему Montana?\n\n_Можешь прикрепить фото или локацию._",
        'en': "📝 *MONTANA CLAN APPLICATION*\n\nTell us about yourself:\n• Who are you?\n• Where from?\n• Why Montana?\n\n_You can attach a photo or location._",
        'zh': "📝 *MONTANA部落申请*\n\n介绍一下你自己：\n• 你是谁？\n• 来自哪里？\n• 为什么选择Montana？\n\n_你可以附上照片或位置。_"
    },
    'menu_btn': {'ru': "🏠 Меню", 'en': "🏠 Menu", 'zh': "🏠 菜单"},
    'status_btn': {'ru': "📊 Статус сети", 'en': "📊 Network Status", 'zh': "📊 网络状态"}
}

def get_text(key: str, lang: str, **kwargs) -> str:
    """Получает текст на нужном языке"""
    texts = JUNONA_TEXTS.get(key, {})
    text = texts.get(lang, texts.get('en', key))
    return text.format(**kwargs) if kwargs else text

async def get_full_user_profile(bot, user) -> dict:
    """Получает максимально полную информацию о пользователе"""
    profile = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'language_code': getattr(user, 'language_code', None),
        'is_premium': getattr(user, 'is_premium', False),
        'is_bot': user.is_bot,
        'photo_file_id': None,
        'bio': None,
    }

    # Получаем фото профиля
    try:
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            profile['photo_file_id'] = photos.photos[0][0].file_id
    except Exception as e:
        logging.warning(f"Не удалось получить фото профиля: {e}")

    # Получаем полный профиль с био (через Chat)
    try:
        chat = await bot.get_chat(user.id)
        profile['bio'] = getattr(chat, 'bio', None)
    except Exception as e:
        logging.warning(f"Не удалось получить био: {e}")

    return profile


def format_clan_request_card(profile: dict, inviter_info: dict, letter: str) -> str:
    """Форматирует красивую карточку запроса на вход в клан"""

    # Статусы
    premium_status = "✅ Да" if profile.get('is_premium') else "❌ Нет"
    bot_status = "🤖 Да" if profile.get('is_bot') else "👤 Нет"

    # Имя пользователя
    full_name = profile.get('first_name', '')
    if profile.get('last_name'):
        full_name += f" {profile['last_name']}"

    # Username со ссылкой
    username_display = f"@{profile['username']}" if profile.get('username') else "не указан"
    user_link = f"tg://user?id={profile['id']}"

    # Пригласитель
    inviter_username = f"@{inviter_info.get('username')}" if inviter_info.get('username') else "не указан"
    inviter_link = f"tg://user?id={inviter_info.get('id')}" if inviter_info.get('id') else "#"

    # Био (обрезаем если длинное)
    bio = profile.get('bio') or "не указано"
    if len(bio) > 100:
        bio = bio[:97] + "..."

    # Письмо (обрезаем если длинное)
    letter_display = letter if len(letter) <= 500 else letter[:497] + "..."

    # Время запроса
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    card = f"""
🔐 *ЗАПРОС НА ВХОД В КЛАН MONTANA*
{'═' * 35}

👤 [{full_name}]({user_link})
🆔 `{profile['id']}`

{'─' * 35}
📋 *ДАННЫЕ ПОЛЬЗОВАТЕЛЯ*
{'─' * 35}

📝 Username: {username_display}
👤 Имя: {profile.get('first_name') or 'N/A'}
👥 Фамилия: {profile.get('last_name') or 'N/A'}
🌐 Язык: {profile.get('language_code') or 'N/A'}
📖 Био: _{bio}_
✨ Premium: {premium_status}
🤖 Бот: {bot_status}
📅 Запрос: {request_time}

{'─' * 35}
👥 *ПРИГЛАСИТЕЛЬ*
{'─' * 35}

🔗 Ник: [{inviter_username}]({inviter_link})
🆔 ID: `{inviter_info.get('id', 'N/A')}`

{'─' * 35}
✉️ *ПИСЬМО АТЛАНТУ*
{'─' * 35}

_{letter_display}_

{'═' * 35}
"""
    return card


async def start_clan_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс вступления в клан"""
    user = update.message.from_user
    args = context.args

    # Проверяем есть ли ID пригласителя
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "🏔 *ВХОД В КЛАН MONTANA*\n\n"
            "Чтобы войти в клан, тебе нужен *пригласитель* (Атлант или член клана).\n\n"
            "Попроси ссылку-приглашение у члена клана или напиши:\n"
            "`/join ID_ПРИГЛАСИТЕЛЯ`\n\n"
            "_Без пригласителя вход невозможен._",
            parse_mode="Markdown"
        )
        return

    inviter_id = int(args[0])

    # Проверяем существует ли пригласитель
    try:
        inviter_chat = await context.bot.get_chat(inviter_id)
        inviter_info = {
            'id': inviter_id,
            'username': inviter_chat.username,
            'first_name': inviter_chat.first_name
        }
    except Exception:
        await update.message.reply_text(
            "❌ *Пригласитель не найден*\n\n"
            "ID пригласителя неверный или пользователь не существует.",
            parse_mode="Markdown"
        )
        return

    # Сохраняем данные в pending
    pending_clan_requests[user.id] = {
        'inviter': inviter_info,
        'state': CLAN_WAITING_LETTER
    }

    inviter_display = f"@{inviter_info['username']}" if inviter_info.get('username') else inviter_info.get('first_name', 'Unknown')

    await update.message.reply_text(
        f"🏔 *ВСТУПЛЕНИЕ В КЛАН MONTANA*\n\n"
        f"👥 Твой пригласитель: *{inviter_display}*\n\n"
        f"{'─' * 30}\n\n"
        f"✉️ *Напиши письмо Атланту*\n\n"
        f"В письме обязательно укажи:\n\n"
        f"1️⃣ *Кто тебя пригласил* и как вы знакомы\n\n"
        f"2️⃣ *Чем ты можешь усилить клан*\n"
        f"   Какие у тебя навыки, опыт, ресурсы?\n\n"
        f"3️⃣ *Какие дыры/слабости видишь*\n"
        f"   Что можешь доказать и закрыть?\n\n"
        f"{'─' * 30}\n\n"
        f"_Атлант прочитает и примет решение._\n"
        f"_Напиши своё письмо следующим сообщением:_",
        parse_mode="Markdown"
    )

    return CLAN_WAITING_LETTER


async def process_clan_letter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает письмо пользователя и отправляет запрос Атланту"""
    user = update.message.from_user
    letter = update.message.text

    if user.id not in pending_clan_requests:
        return

    request_data = pending_clan_requests[user.id]
    inviter_info = request_data['inviter']

    # Получаем полный профиль
    profile = await get_full_user_profile(context.bot, user)

    # Форматируем карточку
    card_text = format_clan_request_card(profile, inviter_info, letter)

    # Кнопки принятия/отклонения
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ПРИНЯТЬ В КЛАН", callback_data=f"clan_accept_{user.id}"),
        ],
        [
            InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"clan_deny_{user.id}")
        ]
    ])

    # Отправляем Атланту (владельцу бота)
    try:
        # Если есть фото - отправляем с фото
        if profile.get('photo_file_id'):
            await context.bot.send_photo(
                chat_id=BOT_CREATOR_ID,
                photo=profile['photo_file_id'],
                caption=card_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=BOT_CREATOR_ID,
                text=card_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )

        # Сохраняем данные запроса
        pending_clan_requests[user.id]['letter'] = letter
        pending_clan_requests[user.id]['profile'] = profile

        await update.message.reply_text(
            "✅ *Запрос отправлен!*\n\n"
            "Атлант получил твоё письмо и данные.\n"
            "Ожидай решения. Тебе придёт уведомление.\n\n"
            "_🏔 Клан Montana_",
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.error(f"Ошибка отправки запроса в клан: {e}")
        await update.message.reply_text(
            "❌ Ошибка отправки запроса. Попробуй позже."
        )

    # Очищаем состояние
    del pending_clan_requests[user.id]
    return -1  # Завершаем conversation


async def handle_clan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает callback'и клана"""
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    callback_data = query.data
    lang = detect_user_language(user)

    # 🏔 Кнопка "Вступить в клан" — начинает процесс заявки
    if callback_data == "clan_join_request":
        await query.answer()
        pending_clan_requests[user_id] = {
            'state': CLAN_WEB_WAITING_INFO,
            'source': 'button'
        }
        await query.message.reply_text(
            get_text('join_form', lang),
            parse_mode="Markdown"
        )
        return

    # Только создатель бота может принимать/отклонять
    if user_id != BOT_CREATOR_ID:
        await query.answer("⛔ Только Атлант может принимать решения", show_alert=True)
        return

    if callback_data.startswith("clan_accept_"):
        target_id = int(callback_data.split("_")[2])

        # Авторизуем пользователя
        users = load_users()
        if str(target_id) not in users:
            users[str(target_id)] = {"authorized": True, "clan_member": True}
        else:
            users[str(target_id)]["authorized"] = True
            users[str(target_id)]["clan_member"] = True
        save_users(users)

        await query.answer("✅ Принят в клан!")
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ *ПРИНЯТ В КЛАН MONTANA*",
            parse_mode="Markdown"
        ) if query.message.caption else await query.edit_message_text(
            text=query.message.text + "\n\n✅ *ПРИНЯТ В КЛАН MONTANA*",
            parse_mode="Markdown"
        )

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="🏔 *ДОБРО ПОЖАЛОВАТЬ В КЛАН MONTANA!*\n\n"
                     "✅ Атлант принял тебя в клан.\n\n"
                     "Теперь ты *Орангутанг* — член клана Montana.\n"
                     "Пока ты с нами — время капает тебе.\n\n"
                     "_20% вероятность получить Ɉ_\n\n"
                     "Используй /start для начала работы.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя: {e}")

    elif callback_data.startswith("clan_deny_"):
        target_id = int(callback_data.split("_")[2])

        await query.answer("❌ Отклонено")
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ *ОТКЛОНЕНО*",
            parse_mode="Markdown"
        ) if query.message.caption else await query.edit_message_text(
            text=query.message.text + "\n\n❌ *ОТКЛОНЕНО*",
            parse_mode="Markdown"
        )

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ *Запрос отклонён*\n\n"
                     "Атлант не принял тебя в клан.\n"
                     "Ты можешь попробовать позже или найти другого пригласителя.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя: {e}")


# 🏔 WEB CLAN JOIN - Вступление через сайт
CLAN_WEB_WAITING_INFO = 10

async def start_web_clan_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс вступления в клан через веб-сайт"""
    user = update.message.from_user

    # Сохраняем состояние
    pending_clan_requests[user.id] = {
        'state': CLAN_WEB_WAITING_INFO,
        'source': 'web'
    }

    await update.message.reply_text(
        f"🏔 *ДОБРО ПОЖАЛОВАТЬ В КЛАН MONTANA*\n\n"
        f"Привет, *{user.first_name}*!\n\n"
        f"Ты пришёл с сайта Montana. Чтобы вступить в Клан, "
        f"расскажи о себе Атланту.\n\n"
        f"{'─' * 30}\n\n"
        f"📝 *Напиши заявку:*\n\n"
        f"• Кто ты и чем занимаешься?\n"
        f"• Как узнал о Montana?\n"
        f"• Чем можешь усилить Клан?\n"
        f"• Какие навыки/ресурсы есть?\n\n"
        f"{'─' * 30}\n\n"
        f"_Можешь также отправить фото или геолокацию._\n"
        f"_Атлант рассмотрит заявку и примет решение._",
        parse_mode="Markdown"
    )


async def process_web_clan_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает заявку на вступление через веб"""
    user = update.message.from_user

    if user.id not in pending_clan_requests:
        return False

    request_data = pending_clan_requests[user.id]
    if request_data.get('state') != CLAN_WEB_WAITING_INFO:
        return False

    # Собираем информацию
    profile = await get_full_user_profile(context.bot, user)

    # Текст заявки
    application_text = ""
    photo_file_id = None
    location_text = None

    if update.message.text:
        application_text = update.message.text
    elif update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
        application_text = update.message.caption or "[Фото без текста]"
    elif update.message.location:
        loc = update.message.location
        location_text = f"📍 {loc.latitude}, {loc.longitude}"
        application_text = f"[Геолокация отправлена]\n{location_text}"

    # Формируем карточку заявки
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    full_name = profile.get('first_name', '')
    if profile.get('last_name'):
        full_name += f" {profile['last_name']}"

    username_display = f"@{profile['username']}" if profile.get('username') else "не указан"
    user_link = f"tg://user?id={profile['id']}"
    premium_status = "✅ Premium" if profile.get('is_premium') else ""
    bio = profile.get('bio') or "не указано"

    card = f"""
🏔 *ЗАЯВКА НА ВСТУПЛЕНИЕ В КЛАН*
{'═' * 35}
📍 Источник: *Веб-сайт Montana*

👤 [{full_name}]({user_link})
🆔 `{profile['id']}`

{'─' * 35}
📋 *ДАННЫЕ*
{'─' * 35}

📝 Username: {username_display}
🌐 Язык: {profile.get('language_code') or 'N/A'}
📖 Био: _{bio[:80]}{'...' if len(bio) > 80 else ''}_
{premium_status}
📅 Запрос: {request_time}
{location_text or ''}

{'─' * 35}
✉️ *ЗАЯВКА*
{'─' * 35}

_{application_text[:500]}{'...' if len(application_text) > 500 else ''}_

{'═' * 35}
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ПРИНЯТЬ В КЛАН", callback_data=f"clan_accept_{user.id}")],
        [InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"clan_deny_{user.id}")]
    ])

    try:
        # Отправляем Атланту
        if profile.get('photo_file_id') or photo_file_id:
            await context.bot.send_photo(
                chat_id=BOT_CREATOR_ID,
                photo=photo_file_id or profile['photo_file_id'],
                caption=card,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=BOT_CREATOR_ID,
                text=card,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )

        await update.message.reply_text(
            "✅ *Заявка отправлена!*\n\n"
            "Атлант получил твою заявку.\n"
            "Ожидай решения — тебе придёт уведомление.\n\n"
            "_🏔 Клан Montana_",
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.error(f"Ошибка отправки веб-заявки: {e}")
        await update.message.reply_text("❌ Ошибка отправки. Попробуй позже.")

    # Очищаем состояние
    del pending_clan_requests[user.id]
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# END MONTANA CLAN AUTHORIZATION SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════


# Команда для отображения списка пользователей
async def show_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Проверяем, является ли пользователь создателем бота
    if chat_id != BOT_CREATOR_ID:
        await update.message.reply_text("⛔ This command is not available for you.")
        return

    # Загружаем список пользователей
    users = load_users()
    if users:
        message = "📋 *List of Users:*\n"
        for chat_id, user_info in users.items():
            if chat_id != "last_user_number":  # Пропускаем счётчик
                message += f"🔢 User #{user_info['user_number']}:\n"
                message += f"   👤 Chat ID: `{chat_id}`\n"
                message += f"   🔗 Username: @{user_info.get('telegram_username', 'N/A')}\n"
                message += f"   🆔 Telegram ID: `{user_info.get('telegram_id', 'N/A')}`\n"
                message += "-" * 20 + "\n"
    else:
        message = "No users found."

    # Отправляем сообщение с информацией
    await update.message.reply_text(message, parse_mode="Markdown")




# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Функция для загрузки пользователей из файла
def load_users():
    if USERS_FILE.exists():
        with open(USERS_FILE, "r") as file:
            try:
                data = json.load(file)
                if isinstance(data, dict):
                    return data  # Убедимся, что возвращается словарь
                else:
                    logging.warning("Users file content is not a dictionary. Resetting to an empty dictionary.")
                    return {}
            except json.JSONDecodeError:
                logging.error("Users file is not a valid JSON. Resetting to an empty dictionary.")
                return {}
    return {}  # Если файла нет, возвращаем пустой словарь

# Функция для сохранения пользователей в файл
def save_users(users):
    with open(USERS_FILE, "w") as file:
        json.dump(users, file, indent=4)

# Функция для удаления пользователя из файла
def remove_user(chat_id):
    """
    Удаляет пользователя из файла пользователей.
    """
    users = load_users()
    chat_id_str = str(chat_id)
    if chat_id_str in users:
        del users[chat_id_str]
        save_users(users)
        logging.info(f"Пользователь {chat_id} удален из файла пользователей.")
        return True
    return False

# Функция для добавления нового пользователя в список
def add_user(chat_id, telegram_username=None, telegram_id=None, referrer_id=None, authorized=False):
    users = load_users()

    # Проверяем, есть ли пользователь уже в базе
    if str(chat_id) not in users:
        # Если пользователь новый, увеличиваем счётчик уникальных номеров
        last_user_number = users.get("last_user_number", 0)  # Получаем последний номер
        user_number = last_user_number + 1  # Увеличиваем на 1

        # Добавляем нового пользователя
        users[str(chat_id)] = {
            "user_number": user_number,
            "telegram_username": telegram_username,
            "telegram_id": telegram_id,
            "referrer_id": referrer_id,
            "authorized": authorized
        }

        # Обновляем последний номер пользователя
        users["last_user_number"] = user_number
    else:
        # Если пользователь уже существует, обновляем его данные
        if telegram_username:
            users[str(chat_id)]["telegram_username"] = telegram_username
        if telegram_id:
            users[str(chat_id)]["telegram_id"] = telegram_id
        if referrer_id and users[str(chat_id)].get("referrer_id") is None:
            users[str(chat_id)]["referrer_id"] = referrer_id
        if authorized:
            users[str(chat_id)]["authorized"] = True

    # Сохраняем изменения в файл
    save_users(users)


# Обновление клавиатуры (реплай-кнопка)
def get_reply_keyboard():
    return ReplyKeyboardMarkup(
        [['🏠 Меню']], 
        resize_keyboard=True,
        one_time_keyboard=False
    )

# Функция для обработки команды /123, которая отправляет group_update
async def send_group_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Проверяем, является ли пользователь создателем бота
    if chat_id != BOT_CREATOR_ID:
        await update.message.reply_text("⛔ У вас нет прав на выполнение этой команды.")
        return

    try:
        await send_group_updates(context)
        await update.message.reply_text("✅ Обновление успешно отправлено в группы.")
    except Exception as e:
        logging.error(f"Ошибка при отправке обновления в группы: {e}")
        await update.message.reply_text("❌ Ошибка при отправке обновления в группы.")


# Команда /248 — ручной запуск ежедневного snapshot баланса
async def save_daily_balance_snapshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Только создатель бота
    if chat_id != BOT_CREATOR_ID:
        await update.message.reply_text("⛔ У вас нет прав на выполнение этой команды.")
        return

    try:
        result = await save_daily_balance_snapshot(context)

        if isinstance(result, dict):
            status = result.get("status")
            if status == "saved":
                bal = result.get("balance")
                t = result.get("time")
                await update.message.reply_text(f"✅ Snapshot баланса сохранён: {bal:.2f}$ ({t} UTC)")
                return
            if status == "exists":
                date = result.get("date", "")
                suffix = f" ({date})" if date else ""
                await update.message.reply_text(f"ℹ️ Snapshot баланса уже сохранён сегодня{suffix}.")
                return
            if status == "error":
                msg = result.get("message") or result.get("exception") or "Неизвестная ошибка"
                await update.message.reply_text(f"❌ Ошибка при сохранении snapshot баланса: {msg}")
                return

        # Fallback на случай, если функция вернула None
        await update.message.reply_text("✅ Команда выполнена (подробности — в логах).")
    except Exception as e:
        logging.error(f"Ошибка при ручном сохранении snapshot баланса: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при выполнении команды.")

# Кнопки Меню
def get_main_menu_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Статистика", callback_data="refresh_data"),
         InlineKeyboardButton("📈 Сделки", callback_data="trades")]
    ])

# =================================================================================================

async def group_update_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        # Отправка обновлений в группы
        await send_group_updates(context)

        # Обновляем сообщение только для пользователя, нажавшего кнопку
        await query.edit_message_text(
            text="Group updates have been successfully sent.",
            reply_markup=get_main_menu_buttons()
        )
    except Exception as e:
        logging.error(f"Error during group update: {e}")
        await query.edit_message_text(
            text="An error occurred while sending group updates. Please try again later.",
            reply_markup=get_main_menu_buttons()
        )


# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.message.from_user
    args = context.args
    lang = detect_user_language(user)

    # 🏔 MONTANA CLAN: Обработка join_clan из веб-сайта
    if args and args[0] == 'join_clan':
        await start_web_clan_join(update, context)
        return

    # 🏔 ПРОВЕРКА: Пользователь в клане?
    is_clan_member = is_authorized(chat_id)

    if is_clan_member:
        # ✅ В КЛАНЕ — показываем персональное меню
        add_user(chat_id, telegram_username=user.username, telegram_id=user.id, authorized=True)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text('status_btn', lang), callback_data="refresh_data")],
            [InlineKeyboardButton(get_text('menu_btn', lang), callback_data="main_menu")]
        ])

        await update.message.reply_text(
            get_text('welcome_clan', lang, name=user.first_name or 'Узел'),
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        # ❌ НЕ В КЛАНЕ — предлагаем вступить
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text('join_btn', lang), callback_data="clan_join_request")]
        ])

        await update.message.reply_text(
            get_text('welcome_guest', lang),
            parse_mode="Markdown",
            reply_markup=keyboard
        )



# Основное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    inline_menu = get_main_menu_buttons()  # Инлайн-кнопки для главного меню

    # Формируем текст сообщения
    menu_text = (
        "🏠 *Меню*\n\n"
        "Выберите пункт Меню:"
    )

    # Отправляем сообщение с текстом и кнопками
    await context.bot.send_message(
        chat_id=chat_id,
        text=menu_text,
        parse_mode="Markdown",  # Поддержка форматирования Markdown
        reply_markup=inline_menu  # Кнопки находятся под текстом
    )


# Инлайн-кнопка для обновления данных в боте для пользователя
async def inline_refresh_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    # Отправляем сообщение о загрузке данных
    loading_message = await context.bot.send_message(chat_id=chat_id, text="⏳ Загрузка данных...")

    try:
        # Выполняем обновление данных
        await send_updates_to_user(context, chat_id)

        # Удаляем сообщение о загрузке данных
        await loading_message.delete()

    except Exception as e:
        logging.error(f"Error during data refresh for user {chat_id}: {e}")

        # Удаляем сообщение о загрузке данных
        await loading_message.delete()

        # Сообщаем об ошибке
        await query.edit_message_text(
            text="❌ An error occurred while refreshing data. Please try again later.",
            reply_markup=get_main_menu_buttons()
        )




# Обработчик для инлайн-кнопок
async def inline_generic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback_data = query.data  # Получаем callback_data
    user_id = query.from_user.id  # Telegram ID пользователя
    chat_id = query.message.chat_id

    # Обработка авторизации
    if callback_data.startswith("auth_"):
        if user_id != BOT_CREATOR_ID:
            await query.answer("Только создатель бота может авторизовывать пользователей.", show_alert=True)
            return
        
        if callback_data.startswith("auth_allow_"):
            target_id = int(callback_data.split("_")[2])
            users = load_users()
            if str(target_id) not in users:
                users[str(target_id)] = {"authorized": True}
            else:
                users[str(target_id)]["authorized"] = True
            save_users(users)
            await query.answer("✅ Пользователь авторизован")
            await query.edit_message_text("✅ Пользователь авторизован")
            await context.bot.send_message(chat_id=target_id, text="✅ Вы авторизованы! Используйте /start для начала работы.")
        elif callback_data.startswith("auth_deny_"):
            await query.answer("❌ Авторизация отклонена")
            await query.edit_message_text("❌ Авторизация отклонена")
        return

    # Главное меню
    if callback_data == "main_menu":
        await query.edit_message_text(
            text="Выберите действие в Меню",
            reply_markup=get_main_menu_buttons()
        )
        return

    # Обработка кнопки "Сделки"
    if callback_data == "trades":
        await query.answer()
        try:
            trades_message = get_last_3_trades()
            if trades_message:
                await query.edit_message_text(
                    text=trades_message,
                    parse_mode='Markdown',
                    reply_markup=get_main_menu_buttons()
                )
            else:
                await query.edit_message_text(
                    text="❌ Сделки не найдены.",
                    reply_markup=get_main_menu_buttons()
                )
        except Exception as e:
            logging.error(f"Ошибка при получении сделок: {e}")
            await query.edit_message_text(
                text="❌ Произошла ошибка при получении сделок. Пожалуйста, попробуйте позже.",
                reply_markup=get_main_menu_buttons()
            )
        return


# ======================================================================


def group_trades(entries):
    """
    Универсальная функция группировки:
    - Trade: по времени до минут, символу и направлению
    - Closed Position, Settlement, Transfer: без изменений
    - Funding: НЕ сохраняется (уже включен в closedPnl)
    """
    # Разделяем записи по типам
    trade_entries = []
    other_entries = []  # Closed Position, Settlement, Transfer (Funding исключен)

    for entry in entries:
        stat_type = entry.get("Stat Type", "")
        if stat_type == "Trade" and entry.get("Side") and entry.get("Side") != "":
            trade_entries.append(entry)
        else:
            # НЕ группируем: Closed Position, Settlement, Transfer
            other_entries.append(entry)

    if not trade_entries:
        return entries
    
    # Группируем сделки по времени (до минут), символу и направлению
    grouped_orders = defaultdict(lambda: {
        'qty': 0.0, 
        'total': 0.0, 
        'fee': 0.0,
        'realized_profit': 0.0,
        'net_realized_profit': 0.0,
        'side': '', 
        'symbol': '', 
        'time_key': '',
        'time_full': '',
        'trade_ids': []
    })
    
    for entry in trade_entries:
        try:
            symbol = entry.get("Symbol", "")
            side = entry.get("Side", "")
            qty = float(entry.get("Quantity", 0)) if entry.get("Quantity", "") != "" else 0.0
            total = float(entry.get("Total", 0)) if entry.get("Total", "") != "" else 0.0
            fee = float(entry.get("Fee", 0)) if entry.get("Fee", "") != "" else 0.0
            realized_profit = float(entry.get("Realized Profit", 0)) if entry.get("Realized Profit", "") != "" else 0.0
            net_realized_profit = float(entry.get("Net Realized Profit", 0)) if entry.get("Net Realized Profit", "") != "" else 0.0
            order_time = entry.get("Time", "")
            trade_id = entry.get("Trade ID", "")
            
            # Обрезаем время до минут (формат: 'YYYY-MM-DD HH:MM')
            try:
                time_obj = datetime.strptime(order_time, '%Y-%m-%d %H:%M:%S')
                time_key = time_obj.strftime('%Y-%m-%d %H:%M')
                time_full = f"{time_key}:00"  # Время для сохранения в CSV
            except:
                # Если не удалось распарсить, используем первые 16 символов (до минут)
                time_key = order_time[:16] if len(order_time) >= 16 else order_time
                time_full = time_key
            
            # Ключ для группировки: время до минут + символ + направление
            group_key = (time_key, symbol, side)
            
            # Суммируем объемы и итоги
            grouped_orders[group_key]['qty'] += qty
            grouped_orders[group_key]['total'] += total
            grouped_orders[group_key]['fee'] += fee
            grouped_orders[group_key]['realized_profit'] += realized_profit
            grouped_orders[group_key]['net_realized_profit'] += net_realized_profit
            grouped_orders[group_key]['side'] = side
            grouped_orders[group_key]['symbol'] = symbol
            grouped_orders[group_key]['time_key'] = time_key
            grouped_orders[group_key]['time_full'] = time_full
            if trade_id:
                grouped_orders[group_key]['trade_ids'].append(trade_id)
            
        except Exception as e:
            logging.error(f"Ошибка при обработке сделки {entry}: {e}")

    # Формируем сгруппированные записи
    grouped_entries = []

    # Сортируем по времени для правильного порядка
    sorted_groups = sorted(grouped_orders.items(), key=lambda x: x[1]['time_key'])
    
    for (time_key, symbol, side), group_data in sorted_groups:
        try:
            total_qty = group_data['qty']
            total_sum = group_data['total']
            # Рассчитываем средневзвешенную цену
            avg_price = total_sum / total_qty if total_qty > 0 else 0.0
            
            # Сохраняем все Trade ID из группы через запятую, чтобы избежать дублирования
            trade_id = ",".join(group_data['trade_ids']) if group_data['trade_ids'] else ""
            
            # Создаем сгруппированную запись с полной структурой
            # Применяем округление: Quantity - 4 знака, остальные числовые - 2 знака
            grouped_entry = {
                "Trade ID": trade_id,
                "Time": group_data['time_full'],
                "Symbol": group_data['symbol'],
                "Side": group_data['side'],
                "Price": round(avg_price, 2),
                "Quantity": round(total_qty, 4),
                "Total": round(total_sum, 2),
                "Fee": round(group_data['fee'], 2),
                "Realized Profit": round(group_data['realized_profit'], 2),
                "Net Realized Profit": round(group_data['net_realized_profit'], 2),
                "Cumulative Net Realized Profit": None,  # Будет рассчитано позже
                "Stat Type": "Trade",
                "Balance": ""
            }
            grouped_entries.append(grouped_entry)
        except Exception as e:
            logging.error(f"Ошибка при формировании сгруппированной записи для группы {(time_key, symbol, side)}: {e}")

    # Объединяем сгруппированные Trade сделки с остальными событиями (Closed Position, Settlement, Transfer)
    all_entries = grouped_entries + other_entries

    return all_entries


def get_last_3_trades():
    """
    Читает CSV файл со сделками, группирует их по времени до минут,
    символу и направлению, и возвращает 3 последние сделки.
    """
    stat_file = "junona_stat.csv"
    if not os.path.exists(stat_file):
        return None
    
    # Читаем все сделки из CSV
    orders = []
    with open(stat_file, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Фильтруем только сделки типа "Trade"
            if row.get("Stat Type") == "Trade" and row.get("Side") and row.get("Side") != "":
                orders.append(row)
    
    if not orders:
        return None
    
    # Группируем сделки используя универсальную функцию
    grouped_orders = group_trades(orders)
    
    # Фильтруем только Trade записи (убираем income-события, если они есть)
    trade_groups = [g for g in grouped_orders if g.get("Stat Type") == "Trade"]
    
    if not trade_groups:
        return None
    
    # Сортируем по времени (от старых к новым) и берем 3 последние
    sorted_groups = sorted(trade_groups, key=lambda x: x.get("Time", ""))
    last_3_groups = sorted_groups[-3:] if len(sorted_groups) >= 3 else sorted_groups
    
    # Формируем сообщение
    message = "📈 *Последние 3 сделки:*\n\n"
    
    for group in last_3_groups:
        try:
            total_qty = float(group.get("Quantity", 0))
            total_sum = float(group.get("Total", 0))
            avg_price = float(group.get("Price", 0))
            side = group.get("Side", "")
            symbol = group.get("Symbol", "")
            display_time = group.get("Time", "")
            
            apple = "🍏" if side.upper() == "BUY" else "🍎"
            message += f"*{apple} {side}: {display_time}*\n"
            message += f"{symbol}: {total_qty:.3f} x {avg_price:.1f} = {total_sum:.2f}$\n\n"
        except Exception as e:
            logging.error(f"Ошибка при формировании сообщения для группы {group}: {e}")
    
    return message


def process_csv_orders(orders, max_length=4096):
    """
    Преобразует список ордеров, прочитанных из CSV, в список текстовых сообщений.
    Ордера группируются по времени до минут, символу и направлению.
    Если итоговое сообщение превышает лимит (4096 символов), оно разбивается на несколько частей.
    """
    # Группируем ордера используя универсальную функцию
    grouped_orders = group_trades(orders)
    
    # Фильтруем только Trade записи
    trade_groups = [g for g in grouped_orders if g.get("Stat Type") == "Trade"]
    
    # Формируем сообщения из сгруппированных ордеров
    messages = []
    current_message = ""
    
    # Сортируем по времени для правильного порядка вывода
    sorted_groups = sorted(trade_groups, key=lambda x: x.get("Time", ""))
    
    for group in sorted_groups:
        try:
            total_qty = float(group.get("Quantity", 0))
            total_sum = float(group.get("Total", 0))
            avg_price = float(group.get("Price", 0))
            side = group.get("Side", "")
            symbol = group.get("Symbol", "")
            display_time = group.get("Time", "")
            
            apple = "🍏" if side.upper() == "BUY" else "🍎"
            order_text = f"*{apple} {side}: {display_time}*\n {symbol}: {total_qty:.3f} x {avg_price:.1f} = {total_sum:.2f}$ \n"
            
            # Если добавление нового ордера превысит лимит, сохраняем накопленный текст и начинаем новый блок
            if len(current_message) + len(order_text) > max_length:
                messages.append(current_message)
                current_message = order_text
            else:
                current_message += order_text
        except Exception as e:
            logging.error(f"Ошибка при формировании сообщения для группы {group}: {e}")
    
    if current_message:
        messages.append(current_message)
    return messages


async def check_and_send_orders(context: ContextTypes.DEFAULT_TYPE):
    try:
        # 1. Обновляем файл статистики
        save_stat()

        # 2. Загружаем данные о последней отправленной сделке (время и Trade ID)
        last_sent_time = None
        last_sent_id = None
        LAST_SENT_FILE = "last_sent_info.json"
        if os.path.exists(LAST_SENT_FILE):
            with open(LAST_SENT_FILE, "r") as f:
                try:
                    last_info = json.load(f)
                    last_sent_time = datetime.strptime(last_info.get("time"), '%Y-%m-%d %H:%M:%S')
                    last_sent_id = last_info.get("trade_id")
                except Exception as e:
                    logging.error(f"Ошибка при разборе данных из {LAST_SENT_FILE}: {e}")

        new_orders = []
        # Для обновления данных о последней отправленной сделке будем хранить максимальные значения
        new_last_time = last_sent_time
        new_last_id = last_sent_id

        # 3. Читаем обновлённый CSV-файл и отбираем сделки типа "Trade",
        #    которые произошли после ранее отправленной (по времени, а при равенстве — по Trade ID)
        if os.path.exists(STAT_FILE):
            with open(STAT_FILE, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Stat Type"] == "Trade":
                        try:
                            trade_time = datetime.strptime(row["Time"], '%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logging.error(f"Ошибка при разборе времени ордера: {e}")
                            continue

                        trade_id = row["Trade ID"]

                        include = False
                        if last_sent_time is None:
                            include = True
                        else:
                            if trade_time > last_sent_time:
                                include = True
                            elif trade_time == last_sent_time:
                                try:
                                    if trade_id > last_sent_id:
                                        include = True
                                except Exception as e:
                                    logging.error(f"Ошибка при сравнении Trade ID: {e}")
                                    include = True  # Если сравнить не удалось — отправляем ордер для безопасности

                        if include:
                            new_orders.append(row)
                            # Обновляем новые данные о последней отправке:
                            if new_last_time is None or trade_time > new_last_time:
                                new_last_time = trade_time
                                new_last_id = trade_id
                            elif new_last_time is not None and trade_time == new_last_time:
                                try:
                                    if trade_id > new_last_id:
                                        new_last_id = trade_id
                                except Exception as e:
                                    logging.error(f"Ошибка при обновлении Trade ID: {e}")

        # 4. Если найдены новые сделки, формируем сообщения и отправляем их в указанные группы
        if new_orders:
            orders_messages = process_csv_orders(new_orders)
            for group_id in TELEGRAM_GROUP_IDS:
                for msg in orders_messages:
                    try:
                        await context.bot.send_message(chat_id=group_id, text=msg, parse_mode='Markdown')
                    except NetworkError as e:
                        logging.error(f"Сетевая ошибка при отправке в группу {group_id}: {e}")
                    except TelegramError as e:
                        logging.error(f"Ошибка Telegram API при отправке в группу {group_id}: {e}")
                    except Exception as e:
                        logging.error(f"Ошибка при отправке в группу {group_id}: {e}")
            # Сохраняем данные о последней отправленной сделке в LAST_SENT_FILE
            if new_last_time:
                try:
                    with open(LAST_SENT_FILE, "w") as f:
                        json.dump({
                            "time": new_last_time.strftime('%Y-%m-%d %H:%M:%S'),
                            "trade_id": new_last_id
                        }, f)
                except Exception as e:
                    logging.error(f"Ошибка при сохранении данных о последней отправке: {e}")
        else:
            logging.info("Новых ордеров не обнаружено.")

    except NetworkError as e:
        logging.error(f"Сетевая ошибка при проверке новых ордеров: {e}")
        try:
            await context.bot.send_message(chat_id=BOT_CREATOR_ID, text=f"⚠️ Сетевая ошибка при проверке новых ордеров: {e}")
        except Exception:
            pass
    except TelegramError as e:
        logging.error(f"Ошибка Telegram API при проверке новых ордеров: {e}")
    except Exception as e:
        logging.error(f"Ошибка при проверке новых ордеров: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=BOT_CREATOR_ID, text=f"⚠️ Ошибка при проверке новых ордеров: {e}")
        except Exception:
            pass


async def send_updates_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        # Обновляем и сохраняем статистику перед отправкой
        save_stat()
        
        # Получаем данные о балансе и позициях с Bybit ДО отправки графиков
        try:
            balance_response = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
            if balance_response.get('retCode') != 0:
                logging.error(f"Ошибка получения баланса от Bybit: {balance_response.get('retMsg', 'Unknown error')}")
                raise Exception(f"Bybit API error: {balance_response.get('retMsg', 'Unknown error')}")
            balances = balance_response.get('result', {}).get('list', [{}])[0].get('coin', [])
            total_balance = 0.0
            for asset in balances:
                if asset['coin'] == 'USDT':
                    total_balance = float(asset['walletBalance'])
                    break
        except Exception as e:
            logging.error(f"Ошибка при получении баланса от Bybit: {e}")
            raise
        
        try:
            positions_response = client.get_positions(category="linear", settleCoin="USDT")
            if positions_response.get('retCode') != 0:
                logging.error(f"Ошибка получения позиций от Bybit: {positions_response.get('retMsg', 'Unknown error')}")
                raise Exception(f"Bybit API error: {positions_response.get('retMsg', 'Unknown error')}")
            positions = positions_response.get('result', {}).get('list', [])
            open_positions = [p for p in positions if float(p['size']) != 0]
            # Суммируем реализованную прибыль по всем позициям
            realized_pnl = sum(float(p.get('curRealisedPnl', 0)) for p in positions)
            # Суммируем нереализованную прибыль по открытым позициям
            unrealized_pnl = sum(float(p['unrealisedPnl']) for p in open_positions)
            # Рассчитываем начальную маржу для открытых позиций
            total_initial_margin = sum((float(p['avgPrice']) * float(p['size'])) / float(p['leverage']) if float(p['leverage']) > 0 else 0 for p in open_positions)
        except Exception as e:
            logging.error(f"Ошибка при получении позиций от Bybit: {e}")
            raise
        
        # Вычисляем total_balance_with_pnl и сохраняем в глобальную переменную
        global current_total_balance_with_pnl
        current_total_balance_with_pnl = total_balance + unrealized_pnl  # Учитываем суммарный unrealized PnL
        
        # Отправляем график реализованной прибыли ПЕРВЫМ (если есть данные)
        try:
            profit_chart = generate_cumulative_profit_chart()
            if profit_chart:
                await context.bot.send_photo(chat_id=user_id, photo=profit_chart)
        except Exception as e:
            logging.error(f"Ошибка при отправке графика реализованной прибыли пользователю {user_id}: {e}", exc_info=True)
        
        # Отправляем график баланса ВТОРЫМ (если есть snapshot'ы) с текущим балансом онлайн
        try:
            chart = generate_balance_chart(current_balance=current_total_balance_with_pnl)
            if chart:
                await context.bot.send_photo(chat_id=user_id, photo=chart)
        except Exception as e:
            logging.error(f"Ошибка при отправке графика баланса пользователю {user_id}: {e}", exc_info=True)
        
        # Расчет количества дней торговли
        start_date = datetime(2024, 9, 1, tzinfo=timezone.utc)
        current_date = datetime.now(UTC)
        delta_days = (current_date - start_date).days + 1
        message = f"\n*Стратегия Юнона* \n\nКоличество дней работы: *{delta_days}* \n(дата начала: {start_date.strftime('%d.%m.%Y')})\n\n"
        
        # Рассчитываем % для каждого PNL
        # realized_pnl_percent = (realized_pnl / total_initial_margin * 100) if total_initial_margin > 0 else 0.0
        unrealized_pnl_percent = (unrealized_pnl / total_initial_margin * 100) if total_initial_margin > 0 else 0.0
        total_profit = realized_pnl + unrealized_pnl
        # total_pnl_percent = (total_profit / total_initial_margin * 100) if total_initial_margin > 0 else 0.0
        # Определяем индикаторы для каждого типа прибыли
        realized_indicator = "🟢" if realized_pnl >= 0 else "🔴"
        unrealized_indicator = "🟢" if unrealized_pnl >= 0 else "🔴"
        total_indicator = "🟢" if total_profit >= 0 else "🔴"
        message += "📊 *Текущая позиция:*\n"
        for pos in open_positions:
            symbol = pos['symbol']
            volume = float(pos['size'])
            entry_price = float(pos['avgPrice'])
            current_price = float(pos['markPrice'])
            liquidation_price = float(pos['liqPrice'])
            position_size = volume * current_price
            liquidation_diff_percentage = ((liquidation_price - current_price) / current_price) * 100 if current_price != 0 else 0
            # Получаем направление позиции и плечо из API
            side = pos.get('side', '')
            leverage = float(pos.get('leverage', 1))
            position_direction = "💹 Лонг" if side == "Buy" else "🔻 Шорт" if side == "Sell" else "❓ Неизвестно"
            message += (f" {position_direction} ({symbol}) ({leverage}x)\n"
                        f" 💰 Объем: {volume:.3f} BTC ({position_size:,.2f}$)\n"
                        f" 💵 Цена входа: {entry_price:,.1f}\n"
                        f" 💸 Текущая цена: {current_price:,.1f}\n"
                        f" 💥 Цена ликвидации: {liquidation_price:,.1f} ({liquidation_diff_percentage:+.2f}%)\n")
        initial_deposit_date = datetime(2024, 9, 1, tzinfo=timezone.utc)
        total_balance_with_pnl = current_total_balance_with_pnl  # Используем уже вычисленное значение
        total_days = (datetime.now(timezone.utc) - initial_deposit_date).days
        
        # Получаем последнее значение кумулятивной реализованной прибыли из файла статистики
        cumulative_realized_profit = get_last_cumulative_profit()
        

        message += f"\n💰 *Прибыль:*"
        message += f"\n{realized_indicator} Реализованная: {realized_pnl:,.2f}$"
        message += f"\n{unrealized_indicator} Не реализованная: {unrealized_pnl:,.2f}$ ({unrealized_pnl_percent:.2f}%)"
        message += f"\n{total_indicator} Общая: {total_profit:,.2f}$ \n"
        message += f"\n💰 *Кошелек:*\n"
        message += f"*🔹 Текущий баланс: {total_balance_with_pnl:,.2f}$*\n"
        keyboard = [
            [InlineKeyboardButton("📎 Прямая ссылка на статистику", url='https://bybit.onelink.me/EhY6/9v7jcaw0')]  # Замените на реальную Bybit-ссылку
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Обработка сетевых ошибок при отправке сообщений
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown', reply_markup=reply_markup)
        except (Forbidden, BadRequest) as e:
            # Пользователь заблокировал бота, чат не найден или доступ запрещен
            logging.warning(f"Пользователь {user_id} недоступен: {type(e).__name__} - {e}")
            # Удаляем пользователя из файла, если это не группа
            if user_id not in TELEGRAM_GROUP_IDS:
                remove_user(user_id)
                logging.info(f"Пользователь {user_id} удален из файла пользователей из-за недоступности.")
            raise
        except NetworkError as e:
            logging.error(f"Сетевая ошибка при отправке сообщения пользователю {user_id}: {e}")
            raise
        except TelegramError as e:
            logging.error(f"Ошибка Telegram API при отправке сообщения пользователю {user_id}: {e}")
            raise
        
        # Отправляем файл с историей сделок (CSV)
        if os.path.exists(STAT_FILE):
            try:
                with open(STAT_FILE, "rb") as file:
                    await context.bot.send_document(chat_id=user_id, document=file, caption="📂 Файл статистики")
            except (Forbidden, BadRequest) as e:
                # Пользователь недоступен - уже обработано выше, но логируем для файла
                logging.warning(f"Пользователь {user_id} недоступен при отправке файла: {type(e).__name__} - {e}")
            except NetworkError as e:
                logging.error(f"Сетевая ошибка при отправке файла пользователю {user_id}: {e}")
            except TelegramError as e:
                logging.error(f"Ошибка Telegram API при отправке файла пользователю {user_id}: {e}")
        else:
            logging.error(f"Файл {STAT_FILE} не найден.")
    except (Forbidden, BadRequest) as e:
        # Пользователь недоступен - уже обработано выше
        logging.warning(f"Пользователь {user_id} недоступен: {type(e).__name__} - {e}")
        # Удаляем пользователя из файла, если это не группа
        if user_id not in TELEGRAM_GROUP_IDS:
            remove_user(user_id)
            logging.info(f"Пользователь {user_id} удален из файла пользователей из-за недоступности.")
    except NetworkError as e:
        logging.error(f"Сетевая ошибка при отправке обновления пользователю {user_id}: {e}")
    except TelegramError as e:
        logging.error(f"Ошибка Telegram API при отправке обновления пользователю {user_id}: {e}")
    except Exception as e:
        logging.error(f"Ошибка при отправке обновления пользователю {user_id}: {e}", exc_info=True)

# -----------------------------------

# Функция для отправки обновлений всем пользователям
async def send_updates(context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    # Создаем копию списка ключей, чтобы можно было безопасно удалять пользователей во время итерации
    user_ids = [uid for uid in users.keys() if uid != "last_user_number"]
    for user_id_str in user_ids:
        try:
            user_id = int(user_id_str)
            await send_updates_to_user(context, user_id)
        except ValueError:
            # Пропускаем некорректные ID
            logging.warning(f"Некорректный ID пользователя: {user_id_str}")
            continue
        except (Forbidden, BadRequest):
            # Пользователь уже удален в send_updates_to_user
            continue


# Функция для получения последнего значения кумулятивной реализованной прибыли из файла статистики
def get_last_cumulative_profit(stat_file: str | None = None) -> float:
    """
    Возвращает последнее значение кумулятивной реализованной прибыли из CSV файла.
    Если файл не существует или данных нет, возвращает 0.0.
    """
    stat_file = stat_file or STAT_FILE
    if not os.path.exists(stat_file):
        return 0.0
    try:
        df = pd.read_csv(stat_file)
        if "Cumulative Net Realized Profit" not in df.columns:
            return 0.0
        
        # Фильтруем записи, где Cumulative Net Realized Profit не пустое
        df = df[df["Cumulative Net Realized Profit"].notna()].copy()
        df = df[df["Cumulative Net Realized Profit"] != ""].copy()
        df = df[df["Cumulative Net Realized Profit"].astype(str).str.strip() != "None"].copy()
        
        if df.empty:
            return 0.0
        
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df["Cumulative Net Realized Profit"] = pd.to_numeric(df["Cumulative Net Realized Profit"], errors="coerce")
        df = df.dropna(subset=["Time", "Cumulative Net Realized Profit"]).sort_values("Time")
        
        if df.empty:
            return 0.0
        
        # Возвращаем последнее значение
        last_profit = float(df["Cumulative Net Realized Profit"].iloc[-1])
        return last_profit
    except Exception as e:
        logging.error(f"Ошибка при получении последнего значения кумулятивной прибыли: {e}", exc_info=True)
        return 0.0


# --- График реализованной прибыли из junona_stat.csv ---
def generate_cumulative_profit_chart(stat_file: str | None = None) -> BytesIO | None:
    stat_file = stat_file or STAT_FILE
    if not os.path.exists(stat_file):
        return None
    try:
        df = pd.read_csv(stat_file)
        if "Time" not in df.columns or "Cumulative Net Realized Profit" not in df.columns:
            return None
        
        # Фильтруем записи, где Cumulative Net Realized Profit не пустое
        # Убираем записи с пустыми значениями, NaN, пустыми строками и строкой "None"
        df = df[df["Cumulative Net Realized Profit"].notna()].copy()
        df = df[df["Cumulative Net Realized Profit"] != ""].copy()
        df = df[df["Cumulative Net Realized Profit"].astype(str).str.strip() != "None"].copy()
        
        if df.empty:
            return None
        
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df["Cumulative Net Realized Profit"] = pd.to_numeric(df["Cumulative Net Realized Profit"], errors="coerce")
        df = df.dropna(subset=["Time", "Cumulative Net Realized Profit"]).sort_values("Time")
        
        if df.empty:
            return None

        x = df["Time"]
        y = df["Cumulative Net Realized Profit"].to_numpy()
        
        # Добавляем текущую дату для динамической шкалы
        first_date = x.iloc[0]
        if hasattr(first_date, 'tz') and first_date.tz is not None:
            current_date = pd.Timestamp.now(tz='UTC')
        else:
            current_date = pd.Timestamp(datetime.now())
        
        # Добавляем текущую точку к данным для правильного отображения на шкале
        x_with_current = pd.concat([x, pd.Series([current_date])], ignore_index=True)
        y_with_current = np.append(y, float(y[-1]))  # Используем последнее значение прибыли

        fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")

        # Строим график с учетом текущей даты, чтобы последнее значение было видно
        ax.plot(x_with_current, y_with_current, color="#00a000", linewidth=3)
        ax.grid(True, linestyle="--", color="white", alpha=0.35, linewidth=0.8)

        for sp in ax.spines.values():
            sp.set_color("white")

        fmt = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
        ax.yaxis.set_major_formatter(fmt)
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")

        ax2 = ax.twinx()
        for sp in ax2.spines.values():
            sp.set_color("white")
        ax2.yaxis.set_major_formatter(fmt)
        ax2.tick_params(axis="y", colors="white")

        # Динамическая шкала дат с отступом справа
        span_days = max(1, int((x_with_current.iloc[-1] - x_with_current.iloc[0]).days))
        # Добавляем отступ справа (10% от диапазона)
        date_pad = span_days * 0.1
        x_min = x_with_current.iloc[0]
        x_max = x_with_current.iloc[-1] + pd.Timedelta(days=date_pad)
        
        # Устанавливаем границы по оси X с отступом
        ax.set_xlim(x_min, x_max)
        
        # Создаем деления дат, начиная с текущей даты как последнего деления
        step = max(7, int(round(span_days / 8)) or 1)
        # Нормализуем даты (убираем время, оставляем только дату)
        try:
            current_date_only = pd.Timestamp(current_date.date())
            start_date = pd.Timestamp(x_min.date())
        except (AttributeError, TypeError):
            # Если не удалось нормализовать, используем как есть
            current_date_only = current_date
            start_date = x_min
        
        # Начинаем с текущей даты как последнего деления и идем назад
        date_ticks = [current_date_only]
        tick_date = current_date_only - pd.Timedelta(days=step)
        
        # Добавляем деления назад с шагом до первой даты
        while tick_date >= start_date:
            date_ticks.append(tick_date)
            tick_date -= pd.Timedelta(days=step)
        
        # Сортируем деления по возрастанию (от первой даты к текущей)
        date_ticks.sort()
        
        ax.set_xticks(date_ticks)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", color="white")

        # Динамическая шкала стоимости с отступом сверху
        ymin, ymax = float(np.nanmin(y_with_current)), float(np.nanmax(y_with_current))
        y_range = ymax - ymin
        # Добавляем отступ сверху (15% от диапазона), чтобы последнее значение было между делениями
        # Это обеспечит появление нового деления на шкале
        y_pad_top = y_range * 0.15 if y_range > 0 else max(1.0, abs(ymax) * 0.02) if ymax != 0 else 1.0
        y_pad_bottom = y_range * 0.05 if y_range > 0 else max(1.0, abs(ymin) * 0.02) if ymin != 0 else 1.0
        ax.set_ylim(ymin - y_pad_bottom, ymax + y_pad_top)
        ax2.set_ylim(ax.get_ylim())

        ax.set_xlabel("Дата", color="white")
        ax.set_ylabel("Реализованная прибыль (USDT)", color="white")
        ax2.set_ylabel("Реализованная прибыль (USDT)", color="white")

        # Используем текущую дату для отображения в заголовке (current_date уже определен выше)
        d0 = x.iloc[0].strftime("%d.%m.%Y")
        d1 = current_date.strftime("%d.%m.%Y")  # Текущая дата формирования графика
        days = (current_date.date() - x.iloc[0].date()).days + 1
        last_profit = float(y[-1])
        
        # Максимум и минимум за последние 5 месяцев
        last_date = x.iloc[-1]
        five_months_ago = last_date - pd.DateOffset(months=5)
        df_last_5m = df[df["Time"] >= five_months_ago]
        if not df_last_5m.empty:
            max_5m = float(df_last_5m["Cumulative Net Realized Profit"].max())
            min_5m = float(df_last_5m["Cumulative Net Realized Profit"].min())
            minmax_text = f"{days} дней (с {d0})  |  Макс за 5 мес: {max_5m:,.0f} USDT  |  Мин за 5 мес: {min_5m:,.0f} USDT"
        else:
            minmax_text = f"{days} дней (с {d0})"
        
        fig.suptitle(
            f"Реализованная прибыль Юноны  |  Дата: {d1}  |  Текущая прибыль: {last_profit:,.0f} USDT\n{minmax_text}",
            color="white",
            fontsize=12,
            y=0.98,
            ha="center",
        )

        # Добавляем текст с последним значением справа от последней точки
        last_x = x_with_current.iloc[-1]
        last_y = float(y_with_current[-1])
        # Отступ вверх на 3% от текущего значения
        y_offset = last_y * 0.03
        # Отступ вправо на 0.5% от диапазона по X
        x_offset_days = (x_max - x_min).days * 0.005
        ax.text(
            last_x + pd.Timedelta(days=x_offset_days),
            last_y + y_offset,
            f"{last_y:,.0f}",
            color="white",
            fontsize=10,
            fontweight='bold',
            va="bottom",
            ha="left"
        )

        fig.tight_layout(rect=[0, 0, 1, 0.95])
        buf = BytesIO()
        buf.name = "junona_cumulative_profit.png"
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logging.error(f"Ошибка генерации графика реализованной прибыли: {e}", exc_info=True)
        return None


# --- График баланса из junona_stat.csv (в стиле примера) ---
def generate_balance_chart(stat_file: str | None = None, current_balance: float | None = None) -> BytesIO | None:
    stat_file = stat_file or STAT_FILE
    if not os.path.exists(stat_file):
        return None
    try:
        df = pd.read_csv(stat_file)
        if "Time" not in df.columns or "Balance" not in df.columns:
            return None
        if "Stat Type" in df.columns:
            df = df[df["Stat Type"].eq("Balance")].copy()
        else:
            df = df.copy()
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
        df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")
        df = df.dropna(subset=["Time", "Balance"]).sort_values("Time")
        if df.empty:
            return None

        x = df["Time"]
        y = df["Balance"].to_numpy()
        
        # Если передан текущий баланс онлайн, используем его вместо последнего значения из файла
        if current_balance is not None:
            last_bal = float(current_balance)
        else:
            # Используем глобальную переменную, если она установлена
            global current_total_balance_with_pnl
            if current_total_balance_with_pnl is not None:
                last_bal = float(current_total_balance_with_pnl)
            else:
                last_bal = float(y[-1])
        
        # Добавляем текущий баланс как последнюю точку на график
        # Проверяем формат timezone дат из CSV и приводим текущее время к тому же формату
        first_time = x.iloc[0]
        if hasattr(first_time, 'tz') and first_time.tz is not None:
            # Если даты имеют timezone, используем текущее время с UTC timezone
            current_time = pd.Timestamp.now(tz='UTC')
        else:
            # Если даты без timezone, используем текущее время без timezone
            # Используем datetime.now() и преобразуем в pandas Timestamp без timezone
            current_time = pd.Timestamp(datetime.now())
        
        # Добавляем текущую точку к данным графика
        x_with_current = pd.concat([x, pd.Series([current_time])], ignore_index=True)
        y_with_current = np.append(y, last_bal)

        fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")

        ax.plot(x_with_current, y_with_current, color="#00a000", linewidth=3)
        ax.grid(True, linestyle="--", color="white", alpha=0.35, linewidth=0.8)

        for sp in ax.spines.values():
            sp.set_color("white")

        fmt = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
        ax.yaxis.set_major_formatter(fmt)
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")

        ax2 = ax.twinx()
        for sp in ax2.spines.values():
            sp.set_color("white")
        ax2.yaxis.set_major_formatter(fmt)
        ax2.tick_params(axis="y", colors="white")

        # Динамическая шкала дат с отступом справа
        span_days = max(1, int((x_with_current.iloc[-1] - x_with_current.iloc[0]).days))
        # Добавляем отступ справа (10% от диапазона), чтобы последнее значение было между делениями
        date_pad = span_days * 0.1
        x_min = x_with_current.iloc[0]
        x_max = x_with_current.iloc[-1] + pd.Timedelta(days=date_pad)
        
        # Устанавливаем границы по оси X с отступом
        ax.set_xlim(x_min, x_max)
        
        # Создаем деления дат, начиная с текущей даты как последнего деления
        step = max(7, int(round(span_days / 8)) or 1)
        # Нормализуем даты (убираем время, оставляем только дату)
        try:
            current_date_only = pd.Timestamp(current_time.date())
            start_date = pd.Timestamp(x_min.date())
        except (AttributeError, TypeError):
            # Если не удалось нормализовать, используем как есть
            current_date_only = current_time
            start_date = x_min
        
        # Начинаем с текущей даты как последнего деления и идем назад
        date_ticks = [current_date_only]
        tick_date = current_date_only - pd.Timedelta(days=step)
        
        # Добавляем деления назад с шагом до первой даты
        while tick_date >= start_date:
            date_ticks.append(tick_date)
            tick_date -= pd.Timedelta(days=step)
        
        # Сортируем деления по возрастанию (от первой даты к текущей)
        date_ticks.sort()
        
        ax.set_xticks(date_ticks)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", color="white")

        # Динамическая шкала стоимости с отступом сверху
        ymin, ymax = float(np.nanmin(y_with_current)), float(np.nanmax(y_with_current))
        y_range = ymax - ymin
        # Добавляем отступ сверху (10% от диапазона), чтобы последнее значение было между делениями
        y_pad_top = y_range * 0.1 if y_range > 0 else max(1.0, abs(ymax) * 0.02) if ymax != 0 else 1.0
        y_pad_bottom = y_range * 0.05 if y_range > 0 else max(1.0, abs(ymin) * 0.02) if ymin != 0 else 1.0
        ax.set_ylim(ymin - y_pad_bottom, ymax + y_pad_top)
        ax2.set_ylim(ax.get_ylim())

        ax.set_xlabel("Дата", color="white")
        ax.set_ylabel("Баланс (USDT)", color="white")
        ax2.set_ylabel("Баланс (USDT)", color="white")

        d0, d1 = x_with_current.iloc[0].strftime("%d.%m.%Y"), x_with_current.iloc[-1].strftime("%d.%m.%Y")
        days = (x_with_current.iloc[-1].date() - x_with_current.iloc[0].date()).days + 1
        # last_bal уже установлен выше (из current_balance или глобальной переменной)
        
        # Максимум и минимум за последние 5 месяцев (из исходных данных CSV, без текущей точки)
        last_date = x.iloc[-1]
        five_months_ago = last_date - pd.DateOffset(months=5)
        df_last_5m = df[df["Time"] >= five_months_ago]
        if not df_last_5m.empty:
            max_5m = float(df_last_5m["Balance"].max())
            min_5m = float(df_last_5m["Balance"].min())
            minmax_text = f"{days} дней (с {d0})  |  Макс за 5 мес: {max_5m:,.0f} USDT  |  Мин за 5 мес: {min_5m:,.0f} USDT"
        else:
            minmax_text = f"{days} дней (с {d0})"
        
        fig.suptitle(
            f"Баланс Юноны  |  Дата: {d1}  |  Текущий баланс: {last_bal:,.0f} USDT\n{minmax_text}",
            color="white",
            fontsize=12,
            y=0.98,
            ha="center",
        )

        # Добавляем текст с последним значением справа от последней точки
        last_x = x_with_current.iloc[-1]
        last_y = float(y_with_current[-1])
        # Отступ вверх на 3% от текущего значения
        y_offset = last_y * 0.03
        # Отступ вправо на 0.5% от диапазона по X
        x_offset_days = (x_max - x_min).days * 0.005
        ax.text(
            last_x + pd.Timedelta(days=x_offset_days),
            last_y + y_offset,
            f"{last_y:,.0f}",
            color="white",
            fontsize=10,
            fontweight='bold',
            va="bottom",
            ha="left"
        )

        fig.tight_layout(rect=[0, 0, 1, 0.95])
        buf = BytesIO()
        buf.name = "junona_balance.png"
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logging.error(f"Ошибка генерации графика баланса: {e}", exc_info=True)
        return None


async def create_stat_backup(context: ContextTypes.DEFAULT_TYPE):
    """Создаёт резервную копию файла junona_stat.csv с указанием даты и времени в имени и отправляет её в канал Telegram."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "Backups"  # Указываем папку Backups
    # Создаём директорию, если она не существует
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    # Формируем путь к файлу внутри папки Backups
    backup_filename = os.path.join(backup_dir, f"junona_stat_backup_{timestamp}.csv")
    try:
        if os.path.exists(STAT_FILE):
            shutil.copy(STAT_FILE, backup_filename)
            logging.info(f"Резервная копия создана: {backup_filename}")
            # Отправляем файл в канал
            with open(backup_filename, 'rb') as file:
                await context.bot.send_document(chat_id=BACKUP_CHANNEL_ID, document=file, caption=f"Резервная копия junona_stat.csv от {timestamp}")
            logging.info(f"Резервная копия отправлена в канал: {BACKUP_CHANNEL_ID}")
        else:
            logging.error(f"Файл {STAT_FILE} не найден для создания резервной копии")
    except Exception as e:
        logging.error(f"Не удалось создать или отправить резервную копию: {e}")

# Функция для отправки обновлений в группы
async def send_group_updates(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Начало отправки обновлений в группы...")  # Лог начала выполнения
    # Цикл по всем группам из списка TELEGRAM_GROUP_IDS
    for group_id in TELEGRAM_GROUP_IDS:
        try:
            logging.info(f"Попытка отправки обновления в группу {group_id}...")  # Лог перед отправкой
            await send_updates_to_user(context, group_id)  # Отправка данных в группу (график уже включен)
            logging.info(f"Обновление успешно отправлено в группу {group_id}.")  # Лог успешной отправки
            # Если файл отправлен в канал для бэкапов, создаём резервную копию
            if group_id == BACKUP_CHANNEL_ID:
                await create_stat_backup(context)
        except Exception as e:
            logging.error(f"Ошибка при отправке обновления в группу {group_id}: {e}")  # Лог ошибки

    logging.info("Завершение отправки обновлений в группы.")  # Лог завершения выполнения




# Файл для сохранения истории сделок
STAT_FILE = "junona_stat.csv"


# Дата начала загрузки данных
START_DATE = datetime(2024, 9, 1, tzinfo=timezone.utc)

# Общий набор столбцов – для сделок/income и snapshot (snapshot данные будут интегрированы в существующие столбцы)
FIELDNAMES = [
    "Time", "Symbol", "Side", "Price", "Quantity", "Total",
    "Fee", "Realized Profit", "Net Realized Profit",
    "Cumulative Net Realized Profit", "Stat Type", "Balance", "Trade ID"
]


def load_existing_trades_and_cumulative_net():
    """
    Считывает CSV-файл, возвращает:
      - existing_trades: множество уже сохранённых ID сделок,
      - last_cumulative_net: последнее накопленное значение Cumulative Net Realized Profit.
    Если файл отсутствует или пуст, возвращаем пустое множество и 0.0.
    """
    existing_trades = set()
    last_cumulative_net = 0.0

    if os.path.exists(STAT_FILE):
        with open(STAT_FILE, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            # Проверяем, есть ли нужные колонки
            has_cum_net_column = ("Cumulative Net Realized Profit" in reader.fieldnames)
            
            for row in reader:
                # Собираем ID сделок
                # Разбиваем Trade ID если они через запятую (для сгруппированных сделок)
                trade_id_value = row.get("Trade ID", "")
                if trade_id_value:
                    # Разбиваем по запятой и добавляем все ID
                    trade_ids = [tid.strip() for tid in trade_id_value.split(",") if tid.strip()]
                    for tid in trade_ids:
                        existing_trades.add(tid)
                
                # Если в файле уже есть колонка Cumulative Net Realized Profit,
                # то обновляем last_cumulative_net на значение из последней строки
                if has_cum_net_column and row["Cumulative Net Realized Profit"]:
                    try:
                        cnrp = float(row["Cumulative Net Realized Profit"])
                        last_cumulative_net = cnrp
                    except ValueError:
                        pass

    return existing_trades, last_cumulative_net



def get_last_saved_timestamp():
    """
    Извлекает максимальную временную метку из сохранённого CSV-файла.
    Если файла нет или данные отсутствуют, возвращает START_DATE.
    """
    last_timestamp = int(START_DATE.timestamp() * 1000)
    if os.path.exists(STAT_FILE):
        with open(STAT_FILE, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    trade_time = datetime.strptime(row["Time"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    ts = int(trade_time.timestamp() * 1000)
                    if ts > last_timestamp:
                        last_timestamp = ts
                except Exception as e:
                    logging.error(f"Ошибка при разборе времени: {e}")
    return last_timestamp


async def save_daily_balance_snapshot(context: ContextTypes.DEFAULT_TYPE = None):
    """
    Сохраняет текущий баланс кошелька как ежедневный snapshot в CSV.
    Использует API Bybit для получения баланса и unrealized PnL.
    """
    try:
        # Получаем баланс через API Bybit
        balance_response = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")

        if balance_response.get('retCode') != 0:
            msg = balance_response.get('retMsg')
            logging.error(f"Ошибка получения баланса: {msg}")
            return {"status": "error", "message": msg}

        balances = balance_response.get('result', {}).get('list', [{}])[0].get('coin', [])
        total_balance = 0.0

        for asset in balances:
            if asset['coin'] == 'USDT':
                total_balance = float(asset['walletBalance'])
                break

        # Получаем позиции для расчета unrealized PnL
        positions_response = client.get_positions(category="linear", settleCoin="USDT")
        if positions_response.get('retCode') != 0:
            msg = positions_response.get('retMsg')
            logging.error(f"Ошибка получения позиций: {msg}")
            return {"status": "error", "message": msg}

        positions = positions_response.get('result', {}).get('list', [])
        open_positions = [p for p in positions if float(p['size']) != 0]
        unrealized_pnl = sum(float(p['unrealisedPnl']) for p in open_positions)

        # Общий баланс с учетом нереализованной прибыли
        total_balance_with_pnl = total_balance + unrealized_pnl

        # Текущее время
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        # Создаем запись snapshot
        snapshot_entry = {
            "Time": current_time,
            "Symbol": "",
            "Side": "",
            "Price": "",
            "Quantity": "",
            "Total": "",
            "Fee": "",
            "Realized Profit": "",
            "Net Realized Profit": "",
            "Cumulative Net Realized Profit": "",
            "Stat Type": "Balance",
            "Balance": round(total_balance_with_pnl, 2),
            "Trade ID": f"balance_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        }

        # Проверяем, не был ли уже сохранен баланс сегодня
        today_date = datetime.now(timezone.utc).date()
        balance_exists = False

        if os.path.exists(STAT_FILE):
            with open(STAT_FILE, mode="r", newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get("Stat Type") == "Balance":
                        try:
                            row_date = datetime.strptime(row["Time"], '%Y-%m-%d %H:%M:%S').date()
                            if row_date == today_date:
                                balance_exists = True
                                logging.info(f"Баланс на {today_date} уже сохранен.")
                                break
                        except Exception as e:
                            logging.error(f"Ошибка при проверке даты: {e}")

        # Если баланс уже сохранен сегодня — ничего не делаем
        if balance_exists:
            return {"status": "exists", "date": str(today_date)}

        # Если баланс еще не сохранен сегодня - сохраняем
        if not balance_exists:
            file_exists = os.path.exists(STAT_FILE)

            # Проверяем перенос строки в конце файла
            if file_exists and os.path.getsize(STAT_FILE) > 0:
                with open(STAT_FILE, mode="rb+") as file:
                    file.seek(-1, 2)
                    last_char = file.read(1)
                    if last_char != b'\n':
                        file.write(b'\n')

            with open(STAT_FILE, mode="a", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(snapshot_entry)

            logging.info(f"✅ Сохранен ежедневный баланс: {total_balance_with_pnl:.2f}$ на {current_time}")
            return {"status": "saved", "balance": float(total_balance_with_pnl), "time": current_time}

    except Exception as e:
        logging.error(f"Ошибка при сохранении ежедневного баланса: {e}", exc_info=True)
        return {"status": "error", "exception": str(e)}


def save_stat():
    existing_ids, last_cumulative_net = load_existing_trades_and_cumulative_net()
    logging.info(f"Загружено уже сохранённых записей: {len(existing_ids)} шт.")
    logging.info(f"Последнее накопленное значение Cumulative Net Realized Profit: {last_cumulative_net}")

    new_entries = []
    # Обработка сделок и income-событий
    start_time = get_last_saved_timestamp() - 60 * 1000  # с небольшим запасом (в мс)
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    interval = 7 * 24 * 60 * 60 * 1000  # 7 дней в мс

    while start_time < end_time:
        try:
            interval_end = start_time + interval
            if interval_end > end_time:
                interval_end = end_time

            logging.info(
                f"Запрос сделок/доходов с {datetime.fromtimestamp(start_time / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} "
                f"до {datetime.fromtimestamp(interval_end / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # ===== БЛОК 1: Получение закрытых позиций (НОВЫЙ) =====
            try:
                cursor = None
                while True:
                    # Формируем параметры запроса
                    params = {
                        "category": "linear",
                        "startTime": start_time,
                        "endTime": interval_end,
                        "limit": 100
                    }
                    if cursor:
                        params["cursor"] = cursor

                    closed_pnl_response = client.get_closed_pnl(**params)

                    # Проверяем код ответа от API
                    if closed_pnl_response.get('retCode') != 0:
                        error_msg = closed_pnl_response.get('retMsg', 'Unknown error')
                        logging.error(f"Ошибка API Bybit при запросе закрытых позиций: {error_msg} (retCode: {closed_pnl_response.get('retCode')})")
                        break

                    closed_pnl_list = closed_pnl_response.get('result', {}).get('list', [])

                    if closed_pnl_list:
                        for closed_pos in closed_pnl_list:
                            # Извлекаем данные из закрытой позиции
                            symbol = closed_pos.get('symbol', 'N/A')
                            closed_time = int(closed_pos.get('updatedTime', 0))
                            closed_pnl = float(closed_pos.get('closedPnl', 0))
                            closed_size = float(closed_pos.get('closedSize', 0))
                            avg_exit_price = float(closed_pos.get('avgExitPrice', 0))
                            avg_entry_price = float(closed_pos.get('avgEntryPrice', 0))

                            # Создаем уникальный ID для закрытой позиции
                            # Используем orderId если есть, иначе комбинацию полей
                            closed_id = closed_pos.get('orderId', '')
                            if not closed_id:
                                closed_id = f"closed_{symbol}_{closed_time}"

                            if closed_id not in existing_ids:
                                # Определяем направление закрытия позиции
                                if avg_exit_price > avg_entry_price:
                                    side = "Close Long"  # Прибыльное закрытие лонга
                                elif avg_exit_price < avg_entry_price:
                                    side = "Close Short"  # Прибыльное закрытие шорта
                                else:
                                    side = "Close"  # Закрытие без прибыли

                                entry = {
                                    "Time": datetime.fromtimestamp(closed_time / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                                    "Symbol": symbol,
                                    "Side": side,
                                    "Price": round(avg_exit_price, 2),
                                    "Quantity": round(closed_size, 4),
                                    "Total": round(closed_size * avg_exit_price, 2),
                                    "Fee": 0.0,  # Комиссии уже включены в closedPnl
                                    "Realized Profit": round(closed_pnl, 2),
                                    "Net Realized Profit": round(closed_pnl, 2),  # Fees уже вычтены Bybit
                                    "Cumulative Net Realized Profit": None,  # Будет рассчитано позже
                                    "Stat Type": "Closed Position",
                                    "Balance": "",
                                    "Trade ID": closed_id
                                }
                                new_entries.append(entry)
                                existing_ids.add(closed_id)
                    else:
                        logging.info("Нет новых закрытых позиций за этот интервал.")

                    # Проверяем есть ли следующая страница
                    cursor = closed_pnl_response.get('result', {}).get('nextPageCursor', '')
                    if not cursor:
                        break
                    time.sleep(0.2)  # Пауза между страницами

            except Exception as e:
                logging.error(f"Ошибка при запросе закрытых позиций: {e}", exc_info=True)
                # Продолжаем выполнение, но пропускаем этот интервал
                start_time += interval
                time.sleep(0.5)
                continue

            # ===== БЛОК 2: Запрос истории торгов (executions) на Bybit =====
            try:
                cursor = None
                while True:
                    # Формируем параметры запроса
                    params = {
                        "category": "linear",
                        "startTime": start_time,
                        "endTime": interval_end,
                        "limit": 200
                    }
                    if cursor:
                        params["cursor"] = cursor

                    trade_response = client.get_executions(**params)

                    # Проверяем код ответа от API
                    if trade_response.get('retCode') != 0:
                        error_msg = trade_response.get('retMsg', 'Unknown error')
                        logging.error(f"Ошибка API Bybit при запросе истории торгов: {error_msg} (retCode: {trade_response.get('retCode')})")
                        break

                    trade_data = trade_response.get('result', {}).get('list', [])
                    if trade_data:
                        for trade in trade_data:
                            trade_id = trade.get('execId', '')  # Используем execId как Trade ID
                            exec_type = trade.get('execType', 'N/A')

                            # ПРОПУСКАЕМ Funding записи (они уже включены в closedPnl)
                            if exec_type == 'Funding':
                                continue

                            if trade_id not in existing_ids:
                                fee = float(trade.get('execFee', 0))
                                # Trade executions - только информация о сделке, без прибыли
                                # Применяем округление: Quantity - 4 знака, остальные числовые - 2 знака
                                entry = {
                                    "Time": datetime.fromtimestamp(int(trade.get('execTime', 0)) / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                                    "Symbol": trade.get('symbol', 'N/A'),
                                    "Side": trade.get('side', 'N/A'),
                                    "Price": round(float(trade.get('execPrice', 0)), 2),
                                    "Quantity": round(float(trade.get('execQty', 0)), 4),
                                    "Total": round(float(trade.get('execValue', 0)), 2),
                                    "Fee": round(fee, 2),
                                    "Realized Profit": "",  # Trade executions не содержат realized profit
                                    "Net Realized Profit": "",  # Trade executions не содержат net realized profit
                                    "Cumulative Net Realized Profit": None,
                                    "Stat Type": exec_type,  # Trade (Funding исключен выше)
                                    "Balance": "",
                                    "Trade ID": trade_id
                                }
                                new_entries.append(entry)
                                existing_ids.add(trade_id)
                    else:
                        logging.info("Нет новых сделок за этот интервал.")

                    # Проверяем есть ли следующая страница
                    cursor = trade_response.get('result', {}).get('nextPageCursor', '')
                    if not cursor:
                        break
                    time.sleep(0.2)  # Пауза между страницами
            except Exception as e:
                logging.error(f"Ошибка при запросе истории торгов: {e}", exc_info=True)
                # Продолжаем выполнение, но пропускаем этот интервал
                start_time += interval
                time.sleep(0.5)
                continue

            start_time += interval
            time.sleep(0.5)
        except Exception as e:
            logging.error(f"Критическая ошибка при запросе истории: {e}", exc_info=True)
            # Прерываем цикл только при критических ошибках
            break

    # Группируем сделки типа "Trade" используя универсальную функцию
    new_entries = group_trades(new_entries)
    
    # Сортируем все записи по времени
    try:
        new_entries.sort(key=get_sort_time)
    except Exception as e:
        logging.error(f"Ошибка сортировки записей: {e}")

    # Обновляем накопленный итог для записей сделок и income
    for entry in new_entries:
        if entry["Time"] and entry["Stat Type"] != "Snapshot":
            try:
                value = float(entry["Net Realized Profit"]) if entry["Net Realized Profit"] != "" else 0.0
            except Exception as e:
                logging.error(f"Ошибка преобразования значения: {e}")
                value = 0.0
            last_cumulative_net += value
            # Округляем Cumulative Net Realized Profit до 4 знаков после запятой
            entry["Cumulative Net Realized Profit"] = round(last_cumulative_net, 2)

    file_exists = os.path.exists(STAT_FILE)
    
    # Проверяем, заканчивается ли файл переносом строки
    # Если нет - добавляем его, чтобы новые данные записывались с новой строки
    if file_exists and os.path.getsize(STAT_FILE) > 0:
        with open(STAT_FILE, mode="rb+") as file:
            file.seek(-1, 2)  # Переходим к последнему байту файла
            last_char = file.read(1)
            if last_char != b'\n':
                file.write(b'\n')
    
    with open(STAT_FILE, mode="a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_entries)

    logging.info(f"✅ Сохранено {len(new_entries)} новых записей в {STAT_FILE}.")



def get_sort_time(entry):
    """
    Возвращает время события для сортировки (из поля "Time").
    """
    time_str = entry["Time"]
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime.min


# Глобальный обработчик ошибок для Telegram бота
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает ошибки, возникающие при обработке обновлений Telegram.
    """
    error = context.error
    
    # Логируем ошибку с подробной информацией
    if isinstance(error, Conflict):
        logging.error(f"⚠️ Конфликт: запущено несколько экземпляров бота. Убедитесь, что запущен только один экземпляр.")
        logging.error(f"Детали ошибки: {error}")
    elif isinstance(error, NetworkError):
        logging.error(f"⚠️ Сетевая ошибка при работе с Telegram API: {error}")
        logging.error(f"Тип ошибки: {type(error).__name__}")
    elif isinstance(error, RetryAfter):
        logging.warning(f"⚠️ Превышен лимит запросов. Telegram требует подождать {error.retry_after} секунд.")
    elif isinstance(error, TimedOut):
        logging.error(f"⚠️ Таймаут при запросе к Telegram API: {error}")
    elif isinstance(error, TelegramError):
        logging.error(f"⚠️ Ошибка Telegram API: {error}")
    else:
        logging.error(f"⚠️ Необработанное исключение: {error}", exc_info=error)
    
    # Если обновление связано с пользователем, пытаемся отправить сообщение об ошибке
    if update and hasattr(update, 'effective_chat'):
        try:
            error_message = "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
            
            # Для конфликтов отправляем более информативное сообщение
            if isinstance(error, Conflict):
                error_message = "⚠️ Обнаружен конфликт: возможно, запущено несколько экземпляров бота."
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_message,
                reply_markup=get_main_menu_buttons()
            )
        except Exception as e:
            logging.error(f"⚠️ Не удалось отправить сообщение об ошибке пользователю: {e}")




if __name__ == '__main__':

    # Создаем приложение Telegram
    application = ApplicationBuilder().token(TELEGRAM_TOKEN_STAT_BOT).build()

    # Добавляем глобальный обработчик ошибок
    application.add_error_handler(error_handler)

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("show_users", show_users_command))

    # 🏔 MONTANA CLAN - Команда /join для вступления в клан
    application.add_handler(CommandHandler("join", start_clan_join))

    # 🏔 MONTANA CLAN - Обработка письма от pending пользователей
    async def letter_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id in pending_clan_requests:
            state = pending_clan_requests[user_id].get('state')
            if state == CLAN_WAITING_LETTER:
                await process_clan_letter(update, context)
                return
            elif state == CLAN_WEB_WAITING_INFO:
                await process_web_clan_application(update, context)
                return
        # Если не pending - пропускаем, чтобы другие handlers обработали
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, letter_handler), group=1)

    # 🏔 MONTANA CLAN - Обработка фото и локации для веб-заявок
    async def web_clan_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        if user_id in pending_clan_requests and pending_clan_requests[user_id].get('state') == CLAN_WEB_WAITING_INFO:
            await process_web_clan_application(update, context)
    application.add_handler(MessageHandler(filters.PHOTO, web_clan_media_handler), group=1)
    application.add_handler(MessageHandler(filters.LOCATION, web_clan_media_handler), group=1)

    # Обработчики текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^🏠 Меню$'), main_menu))

    # Обработчики инлайн-кнопок
    application.add_handler(CallbackQueryHandler(inline_refresh_data, pattern="^refresh_data$"))
    application.add_handler(CallbackQueryHandler(inline_generic, pattern="^(trades|main_menu)$"))
    application.add_handler(CallbackQueryHandler(inline_generic, pattern="^auth_"))

    # 🏔 MONTANA CLAN - Обработка решений Атланта (принять/отклонить)
    application.add_handler(CallbackQueryHandler(handle_clan_callback, pattern="^clan_"))
    application.add_handler(CallbackQueryHandler(group_update_callback, pattern="^group_update$"))
    application.add_handler(CommandHandler("123", send_group_update_command))      
    application.add_handler(CommandHandler("248", save_daily_balance_snapshot_command))
  
    
    # Планировщик задач
    job_queue = application.job_queue

    # Задача для отправки обновлений пользователям
    moscow_time = pytz.timezone("Europe/Moscow")
    job_queue.run_daily(send_group_updates, time=dt.time(hour=21, minute=36, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=3, minute=6, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=9, minute=6, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=15, minute=6, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=21, minute=6, tzinfo=moscow_time))

    # Ежедневное сохранение баланса кошелька
    job_queue.run_daily(save_daily_balance_snapshot, time=dt.time(hour=23, minute=59, tzinfo=moscow_time))

    # Ежедневная резервная копия файла статистики
    job_queue.run_daily(create_stat_backup, time=dt.time(hour=21, minute=36, tzinfo=moscow_time))

    # Запускаем бота
    application.run_polling()


# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 
# Используй только официальные библиотеки pybit Version: 5.10.1


