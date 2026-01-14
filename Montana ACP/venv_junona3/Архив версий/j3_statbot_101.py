#j3_statbot_101


import os
import logging
import json
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, KeyboardButton
from pathlib import Path
import matplotlib.pyplot as plt
import asyncio
import csv
from collections import defaultdict
import matplotlib.dates as mdates
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
        cleanup_logs()
        globals()['last_log_day'] = current_day
    
    logging.info(f"{event}")


def get_session_key():
    print("Пожалуйста, выполните команду `bw login --raw` в другом терминале.")
    print("Введите email, пароль и код 2FA, затем вставьте полученный session key ниже.")
    session_key = getpass.getpass("Session key: ").strip()
    if not session_key:
        raise Exception("Session key не введён")
    return session_key


def get_api_key_from_bitwarden(session_key, item_name):
    """
    Получает элемент (например, API-ключ) из Bitwarden по имени элемента.
    """
    cmd = ["bw", "get", "item", item_name, "--session", session_key]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        log_event(f"Ошибка при получении {item_name}: {stderr}")
        raise Exception(f"Не удалось получить {item_name} из Bitwarden")
    item = json.loads(stdout)
    return item['notes']

# Выполняем вход и получаем session key
try:
    session_key = get_session_key()
    print(f"Получен session key. Выполните команду `bw logout` в другом терминале.")
except Exception as e:
    print(f"Произошла ошибка: {e}")
    exit(1)

# Получение API-ключей из Bitwarden с использованием session key
BYBIT_API_KEY = get_api_key_from_bitwarden(session_key, "api_key_copypro")
BYBIT_API_SECRET = get_api_key_from_bitwarden(session_key, "private_key_api_bybit_copypro_20250609_212756")


# Инициализация сессии Bybit с RSA
client = HTTP(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,  # Приватный ключ RSA из Bitwarden
    rsa_authentication=True,      # Включаем RSA-аутентификацию
    testnet=False                 # Установите True для тестовой сети
)



TELEGRAM_TOKEN = get_api_key_from_bitwarden(session_key, "telegram_token_stat_20250711_001626")



USERS_FILE = Path("stat_bot_users.json")
BOT_CREATOR_ID = 6148271304
TELEGRAM_GROUP_IDS = [-1002316863309] #-1002166580868, -1002427054698, -1002269484406
AUTHORIZED_IDS = [6148271304, 5249406291]

# Функция для проверки, авторизован ли пользователь
def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_IDS

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

# Функция для добавления нового пользователя в список
def add_user(chat_id, telegram_username=None, telegram_id=None, referrer_id=None):
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
            "referrer_id": referrer_id  # Если нет реферала, оставляем None
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

# Кнопки Меню
def get_main_menu_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Кабинет", callback_data="account")],
        [InlineKeyboardButton("🔄 Статистика", callback_data="refresh_data"),
         InlineKeyboardButton("📈 Логи", callback_data="logs")],
        [InlineKeyboardButton("🤝 Партнеры", callback_data="partners_program"),
         InlineKeyboardButton("🤖 Боты", callback_data="create_bot")],
        [InlineKeyboardButton("💰 Депозит", callback_data="deposit_history"),
         InlineKeyboardButton("📩 Поддержка", callback_data="support")]
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

    if not is_authorized(chat_id):
        await update.message.reply_text(
            "⛔ Вы не авторизованы.\n"
            "Сообщите об этом в группу поддержки @tglamers"
        )
        return  

    args = context.args
    referrer_id = args[0] if args and args[0].isdigit() else None

    add_user(chat_id, telegram_username=user.username, telegram_id=user.id, referrer_id=referrer_id)

    # Отправляем одно сообщение с инлайн-кнопками и кнопкой "Меню"
    await update.message.reply_text(
        'Добро пожаловать в сеть #1!\n'
        'Ваш Телеграм ID зарегистрирован.\n',
        parse_mode="Markdown",
        reply_markup=get_main_menu_buttons()  # Инлайн-кнопки для выбора действий
    )

    # Отправляем отдельное сообщение с кнопкой "Меню" для удобства
    await update.message.reply_text(
        "Используйте кнопку 🏠 Меню для навигации.",
        reply_markup=get_reply_keyboard()  # Обычная кнопка "Меню" внизу
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


def get_account_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Edit Referrer", callback_data="edit_referrer")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ])

def get_connect_bybit_buttons(oauth_url):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Connect ByBit", url=oauth_url)],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ])

def get_edit_referrer_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="account")]
    ])

def get_partners_program_buttons(referral_link):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Share Referral Link", switch_inline_query=referral_link)],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ])


# Обработчик для инлайн-кнопок
async def inline_generic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback_data = query.data  # Получаем callback_data
    user_id = query.from_user.id  # Telegram ID пользователя
    chat_id = query.message.chat_id

    # Главное меню
    if callback_data == "main_menu":
        await query.edit_message_text(
            text="Выберите действие в Меню",
            reply_markup=get_main_menu_buttons()
        )
        return

    # Обработка кнопки "Логи"
    if callback_data == "logs":
        await query.answer()
        logs_file_path = "logs.txt"
        if os.path.exists(logs_file_path):
            try:
                with open(logs_file_path, "rb") as file:
                    await context.bot.send_document(chat_id=chat_id, document=file, caption="📂 Файл логов")
            except Exception as e:
                logging.error(f"Ошибка при отправке файла логов: {e}")
                await query.edit_message_text(
                    text="❌ Произошла ошибка при отправке файла логов. Пожалуйста, попробуйте позже.",
                    reply_markup=get_main_menu_buttons()
                )
        else:
            await query.edit_message_text(
                text="❌ Файл логов не найден.",
                reply_markup=get_main_menu_buttons()
            )
        return


# ======================================================================


def process_csv_orders(orders, max_length=4096):
    """
    Преобразует список ордеров, прочитанных из CSV, в список текстовых сообщений.
    Если итоговое сообщение превышает лимит (4096 символов), оно разбивается на несколько частей.
    """
    messages = []
    current_message = ""
    for order in orders:
        try:
            symbol = order["Symbol"]
            side = order["Side"]
            qty = float(order["Quantity"]) if order["Quantity"] != "" else 0.0
            price = float(order["Price"]) if order["Price"] != "" else 0.0
            total = float(order["Total"]) if order["Total"] != "" else 0.0
            order_time = order["Time"]
            apple = "🍏" if side.upper() == "BUY" else "🍎"
            order_text = f"*{apple} {side}: {order_time}*\n {symbol}: {qty:.3f} x {price:.1f} = {total:.2f}$ \n"
            
            # Если добавление нового ордера превысит лимит, сохраняем накопленный текст и начинаем новый блок
            if len(current_message) + len(order_text) > max_length:
                messages.append(current_message)
                current_message = order_text
            else:
                current_message += order_text
        except Exception as e:
            logging.error(f"Ошибка при обработке ордера {order}: {e}")
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
                    except Exception as e:
                        logging.error(f"Ошибка при отправке в группу {group_id}: {e}")
            # Сохраняем данные о последней отправленной сделке в LAST_SENT_FILE
            if new_last_time:
                with open(LAST_SENT_FILE, "w") as f:
                    json.dump({
                        "time": new_last_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "trade_id": new_last_id
                    }, f)
        else:
            logging.info("Новых ордеров не обнаружено.")

    except Exception as e:
        logging.error(f"Ошибка при проверке новых ордеров: {e}")
        await context.bot.send_message(chat_id=BOT_CREATOR_ID, text=f"Ошибка при проверке новых ордеров: {e}")

# ======================================================================

# Функция для отправки статистики
async def send_updates_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        # Обновляем и сохраняем статистику перед отправкой
        save_stat()

        # Расчет количества дней торговли
        start_date = datetime(2024, 9, 1, tzinfo=timezone.utc)
        current_date = datetime.now(UTC)
        delta_days = (current_date - start_date).days + 1

        message = f"\n*Стратегия Юнона* \n\nКоличество дней работы: *{delta_days}*  \n(дата начала: {start_date.strftime('%d.%m.%Y')})\n\n"

        # Добавляем информацию о балансе с Bybit
        balance_response = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        balances = balance_response.get('result', {}).get('list', [{}])[0].get('coin', [])
        total_balance = 0.0
        for asset in balances:
            if asset['coin'] == 'USDT':
                total_balance = float(asset['walletBalance'])
                break

        positions_response = client.get_positions(category="linear", settleCoin="USDT")
        positions = positions_response.get('result', {}).get('list', [])
        open_positions = [p for p in positions if float(p['size']) != 0]

        message += "📊 *Текущая позиция:*\n"
        for pos in open_positions:
            symbol = pos['symbol']
            volume = float(pos['size'])
            entry_price = float(pos['avgPrice'])
            current_price = float(pos['markPrice'])
            liquidation_price = float(pos['liqPrice'])
            unrealized_pnl = float(pos['unrealisedPnl'])
            position_size = volume * current_price

            liquidation_diff_percentage = ((liquidation_price - current_price) / current_price) * 100 if current_price != 0 else 0

            message += (f"• {symbol}: объем. {volume:.3f} BTC ({position_size:,.2f}$)\n"
                        f"  Цена входа: {entry_price:,.1f}\n"
                        f"  Текущая цена: {current_price:,.1f}\n"
                        f"  Цена ликвидации: {liquidation_price:,.1f} ({liquidation_diff_percentage:+.2f}%)\n")

        initial_deposit_date = datetime(2024, 9, 1, tzinfo=timezone.utc)
        total_balance_with_pnl = total_balance + unrealized_pnl  # Учитываем unrealized PnL

        total_days = (datetime.now(timezone.utc) - initial_deposit_date).days
        average_daily_profit_dollars = total_balance_with_pnl / total_days if total_days > 0 else 0
        average_daily_profit_percent = (average_daily_profit_dollars / total_balance * 100) if total_balance != 0 else 0
        average_monthly_profit_dollars = average_daily_profit_dollars * 30
        average_monthly_profit_percent = average_daily_profit_percent * 30

        _, cumulative_net_realized_profit = load_existing_trades_and_cumulative_net()
        total_profit = cumulative_net_realized_profit + unrealized_pnl

        message += f"\n💰 *Прибыль:*"
        message += f"\n🔹 Реализованная прибыль: {cumulative_net_realized_profit:,.2f}$"
        message += f"\n🔹 Не реализованная прибыль: {unrealized_pnl:,.2f}$"
        message += f"\n🔹 Текущая прибыль: {total_profit:,.2f}$\n"

        message += f"\n💰 *Кошелек:*\n"
        message += f"*🔹 Текущий баланс: {total_balance_with_pnl:,.2f}$*\n"

        message += "*\n💸 Детали прибыли:*\n"
        message += f"• Средняя прибыль за 1 день: {average_daily_profit_dollars:,.2f}$ ({average_daily_profit_percent:,.2f}%)\n"
        message += f"• Средняя прибыль за 30 дней: {average_monthly_profit_dollars:,.2f}$ ({average_monthly_profit_percent:,.2f}%)\n\n"

        # Создаем инлайн кнопки (ссылку адаптируем, если нужно; пока оставляем как есть, но для Bybit можно изменить на Bybit-ссылку)
        keyboard = [
            [InlineKeyboardButton("📎 Прямая ссылка на статистику", url='https://bybit.onelink.me/EhY6/ulk0gd3u')]  # Замените на реальную Bybit-ссылку
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown', reply_markup=reply_markup)
        
        # Отправляем файл с историей сделок (CSV)
        if os.path.exists(STAT_FILE):
            with open(STAT_FILE, "rb") as file:
                await context.bot.send_document(chat_id=user_id, document=file, caption="📂 Файл статистики")
        else:
            logging.error(f"Файл {STAT_FILE} не найден.")

    except Exception as e:
        logging.error(f"Ошибка при отправке обновления пользователю {user_id}: {e}")

# -----------------------------------

# Функция для отправки обновлений всем пользователям
async def send_updates(context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    for user_id in users:
        await send_updates_to_user(context, user_id)


# Функция для отправки обновлений в группы
async def send_group_updates(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Начало отправки обновлений в группы...")  # Лог начала выполнения

    # Цикл по всем группам из списка TELEGRAM_GROUP_IDS
    for group_id in TELEGRAM_GROUP_IDS:
        try:
            logging.info(f"Попытка отправки обновления в группу {group_id}...")  # Лог перед отправкой
            await send_updates_to_user(context, group_id)  # Отправка данных в группу
            logging.info(f"Обновление успешно отправлено в группу {group_id}.")  # Лог успешной отправки
        except Exception as e:
            logging.error(f"Ошибка при отправке обновления в группу {group_id}: {e}")  # Лог ошибки

    logging.info("Завершение отправки обновлений в группы.")  # Лог завершения выполнения

# =================== MODULE: Binance PnL Stat ===================

# Файл для сохранения истории сделок
STAT_FILE = "junona_stat.csv"

# Дата начала стратегии (1 сентября 2024)
START_DATE = datetime(2024, 9, 1, tzinfo=timezone.utc)

# Общий набор столбцов – для сделок/income и snapshot (snapshot данные будут интегрированы в существующие столбцы)
FIELDNAMES = [
    "Trade ID", "Time", "Symbol", "Side", "Price", "Quantity", "Total",
    "Fee", "Fee Asset", "Role", "Realized Profit", "Net Realized Profit",
    "Cumulative Net Realized Profit", "Stat Type", "Transfer Amount",
    "walletBalance", "marginBalance", "markPrice", "calculatedPnL"
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
                existing_trades.add(row["Trade ID"])
                
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
            # Запрос истории торгов (executions) на Bybit
            trade_response = client.get_executions(
                category="linear",
                startTime=start_time,
                endTime=interval_end,
                limit=200  # Максимум 200 записей за запрос
            )
            trade_data = trade_response.get('result', {}).get('list', [])
            if trade_data:
                for trade in trade_data:
                    trade_id = trade.get('execId', '')  # Используем execId как Trade ID
                    if trade_id not in existing_ids:
                        realized_pnl = float(trade.get('closedPnl', 0))  # Закрытый PnL
                        fee = float(trade.get('execFee', 0))
                        net_realized_pnl = realized_pnl - fee
                        entry = {
                            "Trade ID": trade_id,
                            "Time": datetime.fromtimestamp(int(trade.get('execTime', 0)) / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                            "Symbol": trade.get('symbol', 'N/A'),
                            "Side": trade.get('side', 'N/A'),
                            "Price": float(trade.get('execPrice', 0)),
                            "Quantity": float(trade.get('execQty', 0)),
                            "Total": float(trade.get('execValue', 0)),
                            "Fee": fee,
                            "Fee Asset": trade.get('feeCurrency', 'N/A'),
                            "Role": "",
                            "Realized Profit": realized_pnl,
                            "Net Realized Profit": net_realized_pnl,
                            "Cumulative Net Realized Profit": None,
                            "Stat Type": trade.get('execType', 'N/A'), # Trade или Funding
                            "Transfer Amount": "",
                            "walletBalance": "",
                            "marginBalance": "",
                            "markPrice": "",
                            "calculatedPnL": ""
                        }
                        new_entries.append(entry)
                        existing_ids.add(trade_id)
            else:
                logging.info("Нет новых сделок за этот интервал.")

            # Запрос истории транзакций (income: funding, transfer) на Bybit
            income_response = client.get_transaction_log(
                category="linear",
                startTime=start_time,
                endTime=interval_end,
                limit=100
            )
            income_data = income_response.get('result', {}).get('list', [])
            if income_data:
                for inc in income_data:
                    income_type = inc.get('transactionType', '')
                    if income_type not in ["SETTLEMENT", "TRANSFER"]:
                        continue
                    income_id = inc.get('transactionId', '')
                    if income_id and income_id not in existing_ids:
                        income_val = float(inc.get('change', 0))
                        if income_type == "TRANSFER":
                            transfer_amount = income_val
                            net_profit_value = 0.0
                        else:
                            transfer_amount = ""
                            net_profit_value = income_val
                        entry = {
                            "Trade ID": income_id,
                            "Time": datetime.fromtimestamp(int(inc.get('transactionTime', 0)) / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                            "Symbol": inc.get('coin', 'N/A'),
                            "Side": "",
                            "Price": "",
                            "Quantity": "",
                            "Total": "",
                            "Fee": "",
                            "Fee Asset": inc.get('coin', 'N/A'),
                            "Role": "",
                            "Realized Profit": "",
                            "Net Realized Profit": net_profit_value,
                            "Cumulative Net Realized Profit": None,
                            "Stat Type": income_type,
                            "Transfer Amount": transfer_amount,
                            "walletBalance": "",
                            "marginBalance": "",
                            "markPrice": "",
                            "calculatedPnL": ""
                        }
                        new_entries.append(entry)
                        existing_ids.add(income_id)
            else:
                logging.info("Нет новых income-событий за этот интервал.")

            start_time += interval
            time.sleep(0.5)
        except Exception as e:
            logging.error(f"Ошибка при запросе истории: {e}")
            break

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
            entry["Cumulative Net Realized Profit"] = last_cumulative_net

    file_exists = os.path.exists(STAT_FILE)
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




# =================== END Binance PnL Stat ===================
if __name__ == '__main__':

    # Создаем приложение Telegram
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("show_users", show_users_command))

    # Обработчики текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^🏠 Меню$'), main_menu))

    # Обработчики инлайн-кнопок
    application.add_handler(CallbackQueryHandler(inline_refresh_data, pattern="^refresh_data$"))
    application.add_handler(CallbackQueryHandler(inline_generic, pattern="^(account|wallet|partners_program|create_bot|connect_bybit|support|logs)$"))
    application.add_handler(CallbackQueryHandler(group_update_callback, pattern="^group_update$"))
    application.add_handler(CommandHandler("123", send_group_update_command))      
  
    
    # Планировщик задач
    job_queue = application.job_queue

    # Задача для отправки обновлений пользователям
    moscow_time = pytz.timezone("Europe/Moscow")
    job_queue.run_daily(send_group_updates, time=dt.time(hour=21, minute=36, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=3, minute=6, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=9, minute=6, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=15, minute=6, tzinfo=moscow_time))
    job_queue.run_daily(check_and_send_orders, time=dt.time(hour=21, minute=6, tzinfo=moscow_time))


    # Запускаем бота
    application.run_polling()


# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 
# Используй только официальные библиотеки pybit Version: 5.10.1


