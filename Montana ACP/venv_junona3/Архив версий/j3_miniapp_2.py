#j3_miniapp_2

from dotenv import load_dotenv
import os
from datetime import datetime
import csv
import os
import logging
from flask import Flask, request
from queue import Queue
from telegram.ext import Application, CallbackContext, CommandHandler, ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, KeyboardButton
from pybit.unified_trading import HTTP
import time
from functools import wraps
from telegram.error import TimedOut
import re
from io import StringIO
import shutil
import warnings
import uuid
import sys
import subprocess
import uuid
import logging
import subprocess
import json
import getpass
from cryptography.fernet import Fernet
warnings.filterwarnings("ignore", message="If 'per_message=False'")

# Переключатель авторизации: True - Bitwarden, False - .env файл
USE_BITWARDEN = False  # Измените на False для использования .env

if USE_BITWARDEN:
    # Оригинальный код для Bitwarden
    def get_session_key():
        logging.info("Пожалуйста, выполните команду `bw login --raw` в другом терминале.")
        logging.info("Введите email, пароль и код 2FA, затем вставьте полученный session key ниже.")
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
        logging.info(f"Получен session key. Выполните команду `bw logout` в другом терминале.")
    except Exception as e:
        logging.info(f"Произошла ошибка: {e}")
        exit(1)

    # Получение API-ключей из Bitwarden с использованием session key
    BYBIT_API_KEY = get_api_key_from_bitwarden(session_key, "api_key_copypro")
    BYBIT_API_SECRET = get_api_key_from_bitwarden(session_key, "private_key_api_bybit_copypro_20250609_212756")
    TELEGRAM_TOKEN = get_api_key_from_bitwarden(session_key, "telegram_token_partner_20250711_001505")
    
    # Инициализация сессии Bybit с RSA
    client = HTTP(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,  # Приватный ключ RSA из Bitwarden
    rsa_authentication=True,      # Включаем RSA-аутентификацию
    testnet=False                 # Установите True для тестовой сети
)
else:
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    if not TELEGRAM_TOKEN:
        raise Exception("TELEGRAM_TOKEN не найден в .env файле. Проверьте файл и переменные.")




BOT_CREATOR_ID = 6148271304
TELEGRAM_GROUP_IDS = [-1002316863309] #-1002166580868, -1002427054698, -1002269484406


# Состояние для ConversationHandler
WAITING_FOR_DATA = 1


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


async def error_handler(update: object, context: CallbackContext) -> None:
    """Обрабатывает ошибки, возникающие при обработке обновлений."""
    logging.error(f"Произошло исключение при обработке обновления: {context.error}")
    # Если обновление связано с пользователем, отправляем сообщение
    if update and hasattr(update, 'effective_chat'):
        try:
            reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Возвращаемся в Главное меню.",
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение об ошибке пользователю: {e}")


def retry_on_timeout(max_retries=5, initial_delay=1, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except TimedOut as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    logging.warning(f"Timed out, retrying in {delay} seconds... ({retries}/{max_retries})")
                    time.sleep(delay)
                    delay *= backoff_factor
            return None
        return wrapper
    return decorator



app = Flask(__name__)

# Настройка логирования с полной датой и временем
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'  # Полная дата и время
)

# Устанавливаем уровень логирования для внешних библиотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Создаем фильтр для скрытия ненужных сообщений
class HttpxFilter(logging.Filter):
    def filter(self, record):
        return "httpx" not in record.getMessage() and "POST https://api.telegram.org" not in record.getMessage()

# Применяем фильтр к корневому логгеру
logger = logging.getLogger()
logger.addFilter(HttpxFilter())


def get_main_menu_keyboard():
    return [
        [InlineKeyboardButton("👤 Личный кабинет", callback_data='personal_cabinet')],
        [InlineKeyboardButton("🔗 Пригласить по ссылке", callback_data='generate_link')],
        [InlineKeyboardButton("🛠 Техническая поддержка", callback_data='support')]
    ]



def init_csv():
    """Создает CSV-файл с заголовками, если он не существует."""
    headers = [
        "Registration DateTime", "Telegram ID", "Junona ID", "Referral ID",
        "Junona Connected", "Exchange Registered", "Partner Level", "Referrals Sum",
        "Partner profit", "Partner withdraw",
        "Cum. Profit Share", "Started Investing on", "Recently Redeemed on", "Current Shares Held",
        "invite token"  # Новая колонка для хранения уникального токена
    ]
    if not os.path.exists('users.csv'):
        with open('users.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)


def migrate_csv_schema():
    """
    Добавляет колонки 'Partner profit', 'Partner withdraw' и 'invite token' в файл users.csv, если они отсутствуют.
    Сохраняет существующие данные, добавляя пустые значения для новых колонок в правильной позиции.
    """
    if not os.path.exists('users.csv'):
        return

    with open('users.csv', 'r', newline='') as file:
        reader = csv.reader(file)
        try:
            headers = next(reader)
            rows = [row for row in reader]
        except StopIteration:
            headers = []
            rows = []

    required_headers = [
        "Registration DateTime", "Telegram ID", "Junona ID", "Referral ID",
        "Junona Connected", "Exchange Registered", "Partner Level", "Referrals Sum",
        "Partner profit", "Partner withdraw",
        "Cum. Profit Share", "Started Investing on", "Recently Redeemed on", "Current Shares Held",
        "invite token"  # Добавляем новую колонку
    ]

    if set(headers) != set(required_headers):
        new_headers = required_headers[:]
        updated_rows = []
        for row in rows:
            updated_row = row + [''] * (len(new_headers) - len(row))
            updated_rows.append(updated_row)

        with open('users.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(new_headers)
            writer.writerows(updated_rows)




def get_partner_percentage(level):
    """
    Возвращает процент прибыли в зависимости от уровня партнера.
    Уровень 1: 10%, Уровень 2: 20%, Уровень 3: 30%, Уровень 4: 40%, Уровень 5: 50%.
    """
    percentages = {1: 0.10, 2: 0.20, 3: 0.30, 4: 0.40, 5: 0.50}
    return percentages.get(level, 0.10)

def parse_profit_share(value):
    """
    Парсит строковое значение 'Cum. Profit Share' в число, удаляя ' USDT' и запятые.
    Например, '10,000.00 USDT' -> 10000.00.
    """
    try:
        clean_value = value.replace(' USDT', '').replace(',', '')
        return float(clean_value)
    except ValueError:
        return 0.0
    


async def create_backup(context: CallbackContext):
    """Создаёт резервную копию файла users.csv с указанием даты и времени в имени и отправляет её в канал Telegram."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "Backups"  # Указываем папку Backups
    # Создаём директорию, если она не существует
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    # Формируем путь к файлу внутри папки Backups
    backup_filename = os.path.join(backup_dir, f"users_backup_{timestamp}.csv")
    channel_id = -1002829880813  # ID канала для отправки резервной копии
    try:
        shutil.copy('users.csv', backup_filename)
        logging.info(f"Резервная копия создана: {backup_filename}")
        # Отправляем файл в канал
        with open(backup_filename, 'rb') as file:
            await context.bot.send_document(chat_id=channel_id, document=file, caption=f"Резервная копия users.csv от {timestamp}")
        logging.info(f"Резервная копия отправлена в канал Users_backup: {channel_id}")
    except Exception as e:
        logging.error(f"Не удалось создать или отправить резервную копию: {e}")


async def add_user_to_csv(telegram_id, junona_id, referral_id, context: CallbackContext):
    """Добавляет данные пользователя в CSV-файл, если запись не существует, генерирует токен из 13 символов и создает резервную копию."""
    if not user_exists(telegram_id):
        registration_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        invite_token = uuid.uuid4().hex[:13]  # Генерируем уникальный токен из 13 символов
        headers = [
            "Registration DateTime", "Telegram ID", "Junona ID", "Referral ID",
            "Junona Connected", "Exchange Registered", "Partner Level", "Referrals Sum",
            "Partner profit", "Partner withdraw",
            "Cum. Profit Share", "Started Investing on", "Recently Redeemed on", "Current Shares Held",
            "invite token"
        ]
        new_row = [
            registration_time,
            str(telegram_id),
            junona_id,
            referral_id if referral_id else "None",
            "No",
            "No",
            "1",
            "0",
            "0",
            "0",
            "0",
            "",
            "",
            "0",
            invite_token  # Сохраняем токен из 13 символов
        ]
        with open('users.csv', 'a+', newline='') as file:
            file.seek(0, os.SEEK_END)
            if file.tell() > 0:
                file.seek(file.tell() - 1, os.SEEK_SET)
                last_char = file.read(1)
                if last_char != '\n':
                    file.write('\n')
            writer = csv.writer(file)
            writer.writerow(new_row)
        await create_backup(context)  # Создаем резервную копию после добавления





def calculate_referrals_sum(junona_id):
    """Вычисляет сумму 'Current Shares Held' для всех рефералов пользователя."""
    referrals = get_invitees_junona_ids(junona_id)
    total_sum = 0.0
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['Junona ID'] in referrals:
                try:
                    shares = float(row['Current Shares Held'])
                    total_sum += shares
                except ValueError:
                    continue  # Пропускаем, если значение не числовое
    return total_sum


def determine_partner_level(referrals_sum):
    """
    Определяет уровень партнера на основе суммы балансов рефералов.
    Переход на следующий уровень происходит, когда сумма превышает порог на 1 цент.
    
    :param referrals_sum: Сумма значений 'Current Shares Held' всех рефералов (float).
    :return: Уровень партнера (int).
    """
    if referrals_sum < 10000.01:
        return 1
    elif referrals_sum < 100000.01:
        return 2
    elif referrals_sum < 500000.01:
        return 3
    elif referrals_sum < 1000000.01:
        return 4
    elif referrals_sum >= 1000000.01:
        return 5
    else:
        return 1


def get_next_junona_id():
    """Генерирует следующий Junona ID на основе максимального значения в CSV."""
    if not os.path.exists('users.csv'):
        init_csv()
        return 1
    max_number = 0
    existing_ids = set()
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            junona_id = row['Junona ID']
            if junona_id.startswith('J'):
                try:
                    number = int(junona_id[1:])
                    existing_ids.add(number)
                    if number > max_number:
                        max_number = number
                except ValueError:
                    continue
    next_number = max_number + 1
    while next_number in existing_ids:
        next_number += 1
    return next_number


def get_user_data(telegram_id):
    """Возвращает данные пользователя в виде словаря по Telegram ID."""
    if not os.path.exists('users.csv'):
        init_csv()
        return {}
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    return row
            except (ValueError, KeyError):
                continue
    return {}




def user_exists(telegram_id):
    """Проверяет, существует ли запись с данным Telegram ID в CSV-файле."""
    if not os.path.exists('users.csv'):
        init_csv()
        return False
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    return True
            except (ValueError, KeyError):
                continue  # Пропускаем строки с ошибками
    return False





def update_referal_id(telegram_id, referal_id):
    """Обновляет Referral ID для пользователя с данным Telegram ID."""
    if not os.path.exists('users.csv'):
        init_csv()
        return
    rows = []
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            if int(row['Telegram ID']) == telegram_id:
                row['Referral ID'] = referal_id
            rows.append(row)
    with open('users.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_inviter_junona_id(telegram_id):
    """Возвращает Junona ID пригласившего пользователя по Telegram ID."""
    if not os.path.exists('users.csv'):
        init_csv()
        return None
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    referral_id = row['Referral ID']
                    return referral_id if referral_id != "None" else None
            except (ValueError, KeyError):
                continue  # Пропускаем строки с ошибками
    return None


def get_invitees_junona_ids(junona_id):
    """Возвращает список Junona ID пользователей, у которых указанный Junona ID является Referral ID."""
    if not os.path.exists('users.csv'):
        init_csv()
        return []
    invitees = []
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if row['Referral ID'] == junona_id:
                    invitees.append(row['Junona ID'])
            except KeyError:
                continue  # Пропускаем строки без нужных полей
    return invitees


def get_telegram_id_by_junona_id(junona_id):
    """Возвращает Telegram ID пользователя по его Junona ID."""
    if not os.path.exists('users.csv'):
        init_csv()
        return None
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if row['Junona ID'] == junona_id:
                    return int(row['Telegram ID'])
            except (ValueError, KeyError):
                continue  # Пропускаем строки с ошибками
    return None


def is_exchange_registered(telegram_id):
    """Проверяет, зарегистрирован ли пользователь на бирже."""
    if not os.path.exists('users.csv'):
        init_csv()
        return False
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    return row['Exchange Registered'] == "Yes"
            except (ValueError, KeyError):
                continue  # Пропускаем строки с ошибками
    return False



def update_exchange_registration_status(telegram_id, status):
    """Обновляет статус регистрации пользователя на бирже в CSV-файле."""
    if not os.path.exists('users.csv'):
        init_csv()
        return
    rows = []
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    row['Exchange Registered'] = status
                rows.append(row)
            except (ValueError, KeyError):
                continue  # Пропускаем некорректные строки
    with open('users.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)





@retry_on_timeout()
async def send_exchange_registration_instructions(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    user_data = get_user_data(telegram_id)
    if not user_data:
        message = "Ваш ID не найден. Пожалуйста, перезапустите бота командой /start."
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)
        return

    exchange_registered = user_data.get('Exchange Registered', 'No')
    junona_id = user_data.get('Junona ID', 'Не указано')

    # Текст с рамкой и жирным шрифтом
    important_text = (
        f"🟡 Шаг 2\n\n📝 Регистрация вашего ID на бирже.\n\n"
        f"Вам необходимо в приложении Bybit изменить Никнейм на ваш Junona ID: {junona_id}\n\n"
        "Это создает безопасную связь между Bybit и Юноной, для участия в партнерской программе и использования бота."
    )
    horizontal_line = "─" * 13
    framed_text = (
        f"{horizontal_line}\n"
        f"<b>{important_text}</b>\n"
        f"{horizontal_line}"
    )
    
    # Полное сообщение
    message = (
        "\n📝 Регистрация ID на бирже\n\n"
        f"{framed_text}\n"
        "\nℹ️ Нажмите '🔗 Ссылка на Инструкцию', чтобы узнать как поменять Никнейм на бирже Bybit.\n"
        "\nℹ️ Нажмите '✅ Никнейм изменен на Junona ID', если вы уже изменили Никнейм.\n"
    )
    
    # Базовая клавиатура
    keyboard = [
        [InlineKeyboardButton("🔗 Ссылка на Инструкцию", url='https://t.me/junona_edu/8')],
        [InlineKeyboardButton("✅ Никнейм изменен на Junona ID", callback_data='exchange_registered')]
    ]
    
    # Добавляем кнопку "Отмена регистрации", если уже зарегистрирован
    if exchange_registered == 'Yes':
        keyboard.append([InlineKeyboardButton("❌ Отмена Регистрации ID 📝", callback_data='cancel_exchange_registration')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')





def is_junona_connected(telegram_id):
    """Проверяет, подключен ли пользователь к Юноне."""
    if not os.path.exists('users.csv'):
        init_csv()
        return False
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    return row['Junona Connected'] == "Yes"
            except (ValueError, KeyError):
                continue  # Пропускаем строки с ошибками liberation
    return False



def update_junona_connection_status(telegram_id, status):
    """Обновляет статус подключения пользователя к Юноне в CSV-файле."""
    if not os.path.exists('users.csv'):
        init_csv()
        return
    rows = []
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            try:
                if int(row['Telegram ID']) == telegram_id:
                    row['Junona Connected'] = status
                rows.append(row)
            except (ValueError, KeyError):
                continue  # Пропускаем некорректные строки
    with open('users.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)




@retry_on_timeout()
async def send_junona_connection_instructions(update: Update, context: CallbackContext):
    telegram_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    user_data = get_user_data(telegram_id)
    if not user_data:
        message = "Ваш ID не найден. Пожалуйста, перезапустите бота командой /start."
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)
        return

    junona_connected = user_data.get('Junona Connected', 'No')

    # Текст с рамкой и жирным шрифтом
    important_text = "🟡 Шаг 1\n\n🔌 Подключение к стратегии Юнона."
    horizontal_line = "─" * 13
    framed_text = (
        f"{horizontal_line}\n"
        f"<b>{important_text}</b>\n"
        f"{horizontal_line}"
    )
    
    # Полное сообщение
    message = (
        "\n🔌 Подключение Юноны\n\n"
        f"{framed_text}\n"
        "\nℹ️ Нажмите '🔗 Ссылка на Инструкцию', если у вас еще нет подключения.\n"
        "\nℹ️ Нажмите '✅ Юнона подключена, подтверждаю!', если у вас во вкладке 'Активы' Bybit появился счет Копитрейдинг и в нем указана стратегия 'Junona AI'.\n"
    )
    
    # Базовая клавиатура
    keyboard = [
        [InlineKeyboardButton("🔗 Ссылка на Инструкцию", url='https://t.me/junona_edu/3')],
        [InlineKeyboardButton("✅ Юнона подключена, подтверждаю!", callback_data='junona_connected')]
    ]
    
    # Добавляем кнопку "Отмена подключения", если уже подключен
    if junona_connected == 'Yes':
        keyboard.append([InlineKeyboardButton("❌ Отмена Подключения 🔌", callback_data='cancel_junona_connection')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')


@retry_on_timeout()
async def start(update: Update, context: CallbackContext):
    """Обрабатывает команду /start, регистрирует пользователя и отправляет приветственное сообщение с кнопками."""
    telegram_id = update.message.from_user.id
    args = context.args
    invite_token = None
    admin_id = 6148271304  # ID администратора

    # Проверяем, является ли пользователь администратором
    if telegram_id == admin_id:
        # Администратор может зарегистрироваться без токена
        pass
    else:
        # Для обычных пользователей проверяем наличие токена
        if args and args[0].startswith('invite_'):
            invite_token = args[0].split('_')[1]
            if not invite_token:  # Проверяем, что токен не пустой
                await update.message.reply_text(
                    "Неверный токен приглашения. Регистрация возможна только по валидной пригласительной ссылке.\n"
                    "Основная группа --> https://t.me/junona_3/2886"
                )
                return
        else:
            await update.message.reply_text(
                "Регистрация возможна только по пригласительной ссылке.\n"
                "Основная группа --> https://t.me/junona_3/2886"
            )
            return

    # Проверяем валидность токена (только для обычных пользователей)
    if telegram_id != admin_id:
        token_exists = False
        referral_id = None
        with open('users.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['invite token'] == invite_token:
                    token_exists = True
                    referral_id = row['Junona ID']
                    break
        if not token_exists:
            await update.message.reply_text("Неверный токен приглашения.")
            return
    else:
        referral_id = None  # Администратор не имеет реферала

    user_data = get_user_data(telegram_id)
    if user_data:  # Если пользователь уже существует
        junona_id = user_data['Junona ID']
        current_referral_id = user_data['Referral ID']
        # Генерируем токен из 13 символов, если его нет или он не соответствует формату
        if 'invite token' not in user_data or not user_data['invite token'] or len(user_data['invite token']) != 13:
            invite_token = uuid.uuid4().hex[:13]
            with open('users.csv', 'r') as file:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames
                rows = list(reader)
            with open('users.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    if int(row['Telegram ID']) == telegram_id:
                        row['invite token'] = invite_token
                    writer.writerow(row)
            await create_backup(context)
        if current_referral_id == "None" and referral_id:
            update_referal_id(telegram_id, referral_id)
    else:  # Новый пользователь
        number = get_next_junona_id()
        junona_id = f"J{number:04d}"
        await add_user_to_csv(telegram_id, junona_id, referral_id if telegram_id != admin_id else "None", context)

        # Уведомление партнеру (только для обычных пользователей)
        if telegram_id != admin_id and referral_id:
            partner_telegram_id = get_telegram_id_by_junona_id(referral_id)
            if partner_telegram_id:
                try:
                    await context.bot.send_message(
                        chat_id=partner_telegram_id,
                        text=f"✅ Новый пользователь {junona_id} зарегистрировался по вашей ссылке."
                    )
                    logging.info(f"Отправлено уведомление партнеру Junona ID: {referral_id} (Telegram ID: {partner_telegram_id}) о новом пользователе Junona ID: {junona_id}")
                except Exception as e:
                    logging.error(f"Ошибка при отправке уведомления партнеру {partner_telegram_id}: {e}")

    # Приветственное сообщение
    welcome_message = (
        "Добро пожаловать в проект Юнона!\n\n"
        "Юнона - это стратегия по торговле Биткоином.\n\n"
        f"🎉 Ваш Junona ID: {junona_id}\n\n"
        "Здесь вы сможете:\n\n"
        " • Познакомиться со стратегией\n"
        " • Подключиться и настроить\n"
        " • Управлять личным кабинетом\n"
        " • Приглашать Партнеров\n"
    )

    keyboard = [
        [InlineKeyboardButton("📑 Презентация проекта", url='https://t.me/junona_edu/9')],
        [InlineKeyboardButton("📈 Результаты и Отзывы", url='https://t.me/junona_results/3')],
        [InlineKeyboardButton("📊 Статистика сделок", url='https://t.me/junona_stat/4')],
        [InlineKeyboardButton("💬 Ссылка на группу", url='https://t.me/junona_3/2886')],
        [InlineKeyboardButton("🔌 Подключение", callback_data='connect_junona')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')





async def send_referral_link(telegram_id, bot, chat_id):
    """Генерирует и отправляет реферальную ссылку пользователю с инлайн-кнопками. Обновляет старые токены или генерирует новый из 13 символов."""
    user_data = get_user_data(telegram_id)
    if user_data:
        invite_token = user_data.get('invite token', '')
        # Проверяем, существует ли токен и соответствует ли он новому формату (13 символов)
        if not invite_token or len(invite_token) != 13:
            invite_token = uuid.uuid4().hex[:13]  # Генерируем токен из 13 символов
            with open('users.csv', 'r') as file:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames
                rows = list(reader)
            with open('users.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    if int(row['Telegram ID']) == telegram_id:
                        row['invite token'] = invite_token  # Обновляем токен
                    writer.writerow(row)
            await create_backup(bot)  # Создаем резервную копию после обновления
        link = f"https://t.me/{bot.username}?start=invite_{invite_token}"
        share_url = f"https://t.me/share/url?url={link}"
        message = (
            f"\n🔗 Пригласить по ссылке\n\nВаша постоянная ссылка для приглашения партнеров в проект Юнона:\n\n"
            f"{link}\n\n"
            "Вы можете:\n"
            "- Отправить ее в Telegram.\n"
            "- Скопировать ссылку и поделиться.\n"
            "- Опубликовать ее в социальных сетях."
        )
        keyboard = [
            [InlineKeyboardButton("📤 Отправить / Скопировать ссылку", url=share_url)],
            [InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    else:
        await bot.send_message(chat_id=chat_id, text="Ваш Junona ID не найден. Пожалуйста, перезапустите бота командой /start.")






async def share_link(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    # Получаем ссылку из текста сообщения
    link = query.message.text.split(": ")[1]
    # Отправляем ссылку в чат
    await context.bot.send_message(chat_id=query.message.chat_id, text=link)



async def handle_action(update: Update, context: CallbackContext, action: str):
    if action == 'personal_cabinet':
        await personal_cabinet(update, context)
    elif action == 'generate_link':
        await invite(update, context)
    elif action == 'support':
        await support(update, context)
    elif action == 'connect_junona':
        await send_junona_connection_instructions(update, context)
    elif action == 'register_exchange':
        await send_exchange_registration_instructions(update, context)
    else:
        await update.message.reply_text("Неизвестное действие.")



async def personal_cabinet(update: Update, context: CallbackContext):
    """Обрабатывает действие personal_cabinet, отображая информацию о кабинете, статусах подключения и партнерах."""
    if update.message:
        telegram_id = update.message.from_user.id
        chat_id = update.message.chat_id
    elif update.callback_query:
        telegram_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
    else:
        return

    user_data = get_user_data(telegram_id)
    if not user_data:
        message = "Ваш ID не найден. Пожалуйста, перезапустите бота командой /start."
    else:
        junona_id = user_data.get('Junona ID', 'Не указано')
        telegram_id_display = user_data.get('Telegram ID', 'Не указано')
        junona_connected = user_data.get('Junona Connected', 'No')
        exchange_registered = user_data.get('Exchange Registered', 'No')
        partner_level = int(user_data.get('Partner Level', '1'))
        referrals_sum = user_data.get('Referrals Sum', '0')
        cum_profit_share = user_data.get('Cum. Profit Share', '0')
        started_investing = user_data.get('Started Investing on', '')
        recently_redeemed = user_data.get('Recently Redeemed on', '')
        current_shares_held = user_data.get('Current Shares Held', '0')
        partner_profit_str = user_data.get('Partner profit', '0.00') or '0.00'
        partner_withdraw_str = user_data.get('Partner withdraw', '0.00') or '0.00'
        inviter_junona_id = get_inviter_junona_id(telegram_id)
        invitees_junona_ids = get_invitees_junona_ids(junona_id)

        # Преобразуем в float для корректного отображения
        try:
            partner_profit = float(partner_profit_str.replace(',', ''))
        except ValueError:
            partner_profit = 0.00
        try:
            partner_withdraw = float(partner_withdraw_str.replace(',', ''))
        except ValueError:
            partner_withdraw = 0.00

        # Форматируем 'Current Shares Held' для "Ваш Депозит"
        if current_shares_held:
            try:
                shares_float = float(current_shares_held.replace(',', ''))
                formatted_shares = f"{shares_float:,.2f}"
            except ValueError:
                formatted_shares = "Не указано"
        else:
            formatted_shares = "Не указано"

        message = f"\n👤 Личный кабинет\n\nВаш Junona ID: {junona_id}\nВаш Telegram ID: {telegram_id_display}\n"
        message += "─────────────"
        message += "\n🔌 Статусы подключения:\n"
        message += f" {'✅' if junona_connected == 'Yes' else '❌'} Подключение к Юноне \n"
        message += f" {'✅' if exchange_registered == 'Yes' else '❌'} Регистрация ID на бирже\n"

        message += "\n📈 Финансовая информация:\n"
        message += f"Начало инвестирования: {started_investing if started_investing else 'Не указано'}\n"
        message += f"Вывод средств: {recently_redeemed if recently_redeemed else 'Не указано'}\n"
        message += f"💰 Удерживаемые доли: {formatted_shares}\n\n"

        message += "─────────────"
        message += "\n🤝 Партнеры:\n"
        if inviter_junona_id:
            message += f"Вас пригласил: {inviter_junona_id}\n\n"
        else:
            message += "У вас нет пригласившего партнера.\n"

        if invitees_junona_ids:
            invitees_count = len(invitees_junona_ids)
            invitees_list = ", ".join(invitees_junona_ids)
            message += f"Вы пригласили ({invitees_count}): {invitees_list}\n"
        else:
            message += "Вы еще никого не пригласили.\n"
        message += f"💸 Баланс партнеров: {referrals_sum}$\n"
        message += f"💰 Прибыль за приглашения: {partner_profit:.2f}$\n"
        message += f"💸 Выводы: {partner_withdraw:.2f}$\n"

        message += f"\n📊 Ваш Уровень партнера: {partner_level}\n"
        levels = [
            "1. до 10тыс.$ - 10%",
            "2. от 10тыс.$ до 100тыс.$ - 20%",
            "3. от 100тыс.$ до 500тыс.$ - 30%",
            "4. от 500тыс.$ до 1 млн$ - 40%",
            "5. более 1 млн$ - 50%"
        ]
        for i, level in enumerate(levels, start=1):
            if i <= partner_level:
                message += f"✅ {level}\n"
            else:
                message += f"❌ {level}\n"

    keyboard = [
        [InlineKeyboardButton("🔗 Пригласить по ссылке", callback_data='generate_link')],
        [InlineKeyboardButton("💸 Вывод прибыли", callback_data='withdraw_profit')],
        [InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    elif update.callback_query:
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)


def init_withdrawals_csv():
    """Создает файл withdrawals.csv с заголовками, если он не существует."""
    if not os.path.exists('withdrawals.csv'):
        with open('withdrawals.csv', 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=[
                'Request ID', 'Telegram ID', 'Junona ID', 'UID', 'Amount', 
                'Status', 'Request Time', 'Completion Time'
            ])
            writer.writeheader()


def get_next_request_id():
    """Генерирует следующий уникальный ID для заявки на основе последнего в withdrawals.csv."""
    if not os.path.exists('withdrawals.csv'):
        return 1
    with open('withdrawals.csv', 'r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if rows:
            last_id = int(rows[-1]['Request ID'])
            return last_id + 1
        return 1
    

def create_withdrawal_request(telegram_id, uid, amount):
    """Создает новую заявку на вывод в withdrawals.csv со статусом 'в обработке'."""
    request_id = get_next_request_id()
    user_data = get_user_data(telegram_id)
    junona_id = user_data.get('Junona ID', 'Не указано')
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = {
        'Request ID': request_id,
        'Telegram ID': telegram_id,
        'Junona ID': junona_id,
        'UID': uid,
        'Amount': f"{amount:.2f}",
        'Status': 'в обработке',
        'Request Time': request_time,
        'Completion Time': ''
    }
    with open('withdrawals.csv', 'a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=new_row.keys())
        if os.stat('withdrawals.csv').st_size == 0:
            writer.writeheader()
        writer.writerow(new_row)
    return request_id


def get_pending_withdrawals(telegram_id):
    """Возвращает список заявок со статусом 'в обработке' для пользователя."""
    if not os.path.exists('withdrawals.csv'):
        return []
    with open('withdrawals.csv', 'r') as file:
        reader = csv.DictReader(file)
        pending = [
            row for row in reader 
            if row['Telegram ID'] == str(telegram_id) and row['Status'] == 'в обработке'
        ]
    return pending


def get_processing_withdrawals():
    """Возвращает список всех заявок со статусом 'в обработке'."""
    if not os.path.exists('withdrawals.csv'):
        return []
    with open('withdrawals.csv', 'r') as file:
        reader = csv.DictReader(file)
        processing = [row for row in reader if row['Status'] == 'в обработке']
    return processing


def update_withdrawal_status(request_id, status):
    """Обновляет статус заявки в withdrawals.csv."""
    if not os.path.exists('withdrawals.csv'):
        return
    rows = []
    with open('withdrawals.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['Request ID'] == str(request_id):
                row['Status'] = status
                if status == 'исполнено':
                    row['Completion Time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows.append(row)
    with open('withdrawals.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def complete_withdrawal(request_id, context: CallbackContext):
    if not os.path.exists('withdrawals.csv'):
        return
    with open('withdrawals.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['Request ID'] == str(request_id):
                telegram_id = int(row['Telegram ID'])
                amount = float(row['Amount'])
                break
        else:
            return

    user_data = get_user_data(telegram_id)
    if user_data:
        partner_withdraw_str = user_data.get('Partner withdraw', '0.00') or '0.00'
        try:
            partner_withdraw = float(partner_withdraw_str.replace(',', ''))
        except ValueError:
            partner_withdraw = 0.00
        new_withdraw = partner_withdraw + amount
        await update_partner_withdraw(telegram_id, new_withdraw, context)  # Передаем context

    update_withdrawal_status(request_id, 'исполнено')
    await create_withdrawals_backup(context)
    try:
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"Ваша заявка на вывод {amount:.2f}$ исполнена."
        )
    except Exception as e:
        logging.error(f"Ошибка при уведомлении пользователя {telegram_id}: {e}")





async def cancel_withdrawal(request_id, context: CallbackContext):
    if not os.path.exists('withdrawals.csv'):
        return
    
    with open('withdrawals.csv', 'r') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        target_row = None
        for row in rows:
            if row['Request ID'] == str(request_id):
                target_row = row
                break
        if not target_row:
            return

    telegram_id = int(target_row['Telegram ID'])
    amount = float(target_row['Amount'])
    current_status = target_row['Status']

    if current_status == 'исполнено':
        user_data = get_user_data(telegram_id)
        if user_data:
            partner_withdraw_str = user_data.get('Partner withdraw', '0.00') or '0.00'
            try:
                partner_withdraw = float(partner_withdraw_str.replace(',', ''))
            except ValueError:
                partner_withdraw = 0.00
            new_withdraw = max(0.00, partner_withdraw - amount)
            await update_partner_withdraw(telegram_id, new_withdraw, context)  # Передаем context
            for row in rows:
                if row['Request ID'] == str(request_id):
                    row['Status'] = 'отменено'
                    row['Completion Time'] = ''
            with open('withdrawals.csv', 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            await create_withdrawals_backup(context)
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=f"Ваша исполненная заявка на вывод {amount:.2f}$ (ID: {request_id}) была отменена. Сумма возвращена в Partner withdraw."
                )
            except Exception as e:
                logging.error(f"Ошибка при уведомлении пользователя {telegram_id}: {e}")
    elif current_status == 'в обработке':
        for row in rows:
            if row['Request ID'] == str(request_id):
                row['Status'] = 'отменено'
        with open('withdrawals.csv', 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        await create_withdrawals_backup(context)
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"Ваша заявка на вывод {amount:.2f}$ (ID: {request_id}) отменена."
            )
        except Exception as e:
            logging.error(f"Ошибка при уведомлении пользователя {telegram_id}: {e}")
    else:
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"Заявка с ID {request_id} уже отменена или не подлежит изменению."
            )
        except Exception as e:
            logging.error(f"Ошибка при уведомлении пользователя {telegram_id}: {e}")

    



async def withdraw_profit_start(update: Update, context: CallbackContext):
    """Отображает баланс и неисполненные заявки или запрашивает UID для новой заявки."""
    if update.callback_query:
        telegram_id = update.callback_query.from_user.id
    else:
        logging.error("Callback query is None in withdraw_profit_start")
        return ConversationHandler.END

    user_data = get_user_data(telegram_id)
    if not user_data:
        await update.callback_query.message.reply_text(
            "Ваш ID не найден. Пожалуйста, перезапустите бота командой /start."
        )
        return ConversationHandler.END

    partner_profit_str = user_data.get('Partner profit', '0.00') or '0.00'
    partner_withdraw_str = user_data.get('Partner withdraw', '0.00') or '0.00'

    try:
        partner_profit = float(partner_profit_str.replace(',', ''))
    except ValueError:
        partner_profit = 0.00
    try:
        partner_withdraw = float(partner_withdraw_str.replace(',', ''))
    except ValueError:
        partner_withdraw = 0.00

    available_balance = partner_profit - partner_withdraw
    pending_requests = get_pending_withdrawals(telegram_id)

    if pending_requests:
        message = "Ваши заявки на вывод в обработке:\n"
        for req in pending_requests:
            message += (
                f"ID: {req['Request ID']}, Сумма: {req['Amount']}$, "
                f"UID: {req['UID']}, Время: {req['Request Time']}\n"
            )
        message += "\nПожалуйста, дождитесь обработки текущих заявок перед созданием новой."
        await update.callback_query.message.reply_text(message)
        return ConversationHandler.END
    else:
        if available_balance < 100:
            await update.callback_query.message.reply_text(
                "Ваш доступный баланс для вывода меньше 100$. Вывод невозможен."
            )
            return ConversationHandler.END
        message = (
            f"💸 Ваш доступный баланс для вывода прибыли за приглашения: {available_balance:.2f}$\n\n"
            "‼️ Введите Ваш UID на бирже Bybit (9 цифр)\n"
            "ℹ️ UID — это 9-значный номер в приложении Bybit:\n"
            "   • Главная → Профиль → UID рядом с аватаркой\n"
            "Пример: 123456789\n"
            "⚠️ Вводите только цифры без пробелов или символов!"
        )
        await update.callback_query.message.reply_text(message)
        return WAITING_FOR_UID
    



async def withdraw_profit_uid(update: Update, context: CallbackContext):
    """Обрабатывает ввод UID из сообщения пользователя."""
    telegram_id = update.message.from_user.id
    uid = update.message.text.strip()
    if not re.match(r'^\d{9}$', uid):
        await update.message.reply_text(
            "❌ UID должен состоять ровно из 9 цифр без пробелов или других символов.\n"
            "Пример: 123456789\n"
            "Пожалуйста, введите заново."
        )
        return WAITING_FOR_UID
    context.user_data['withdraw_uid'] = uid
    await update.message.reply_text(
        "✅ UID принят!\n"
        "‼️ Теперь введите сумму для вывода (минимум 100):\n⚠️ Вводите только цифры без пробелов или символов!"
    )
    return WAITING_FOR_AMOUNT



async def withdraw_profit_amount(update: Update, context: CallbackContext):
    """Обрабатывает сумму вывода и создает заявку со статусом 'в обработке'."""
    if not update.message.text:
        await update.message.reply_text(
            "⚠️ Пожалуйста, отправьте сумму как текстовое сообщение (например, 150.50)."
        )
        return WAITING_FOR_AMOUNT

    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Сумма должна быть числом (например, 150.50).\nПожалуйста, введите заново."
        )
        return WAITING_FOR_AMOUNT

    telegram_id = update.message.from_user.id
    user_data = get_user_data(telegram_id)
    partner_profit_str = user_data.get('Partner profit', '0.00') or '0.00'
    partner_withdraw_str = user_data.get('Partner withdraw', '0.00') or '0.00'

    try:
        partner_profit = float(partner_profit_str.replace(',', ''))
    except ValueError:
        partner_profit = 0.00
    try:
        partner_withdraw = float(partner_withdraw_str.replace(',', ''))
    except ValueError:
        partner_withdraw = 0.00

    available_balance = partner_profit - partner_withdraw

    if amount < 100:
        await update.message.reply_text(
            "❌ Минимальная сумма для вывода — 100$.\nПожалуйста, введите заново."
        )
        return WAITING_FOR_AMOUNT
    if amount > available_balance:
        await update.message.reply_text(
            f"❌ Сумма для вывода не может превышать доступный баланс ({available_balance:.2f}$).\n"
            "Пожалуйста, введите заново."
        )
        return WAITING_FOR_AMOUNT

    uid = context.user_data['withdraw_uid']
    request_id = create_withdrawal_request(telegram_id, uid, amount)
    await create_withdrawals_backup(context)  # Создаем резервную копию после добавления заявки
    junona_id = user_data.get('Junona ID', 'Не указано')

    await update.message.reply_text(
        f"✅ Создан запрос на вывод: {amount:.2f}$ на UID {uid}. ID заявки: {request_id}"
    )
    await send_withdrawal_request_info(
        context, telegram_id, junona_id, partner_profit, partner_withdraw, amount, uid, request_id
    )

    context.user_data.pop('withdraw_uid', None)
    reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
    await update.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
    return ConversationHandler.END




async def update_partner_withdraw(telegram_id, new_withdraw, context: CallbackContext):
    if not os.path.exists('users.csv'):
        return
    rows = []
    with open('users.csv', 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            if int(row['Telegram ID']) == telegram_id:
                row['Partner withdraw'] = f"{new_withdraw:.2f}"
            rows.append(row)
    with open('users.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    await create_backup(context)  # Создаем резервную копию после обновления




async def send_withdrawal_request_info(context: CallbackContext, telegram_id: int, junona_id: str, partner_profit: float, partner_withdraw: float, withdrawal_amount: float, uid: str, request_id: int = None):
    """Отправляет информацию о заявке администратору и на канал, включая ID заявки."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        f"📋 Заявка на вывод прибыли:\n\n"
        f"🆔 ID заявки: {request_id if request_id else 'Не указан'}\n"
        f"🕒 Дата и время: {current_time}\n"
        f"👤 Telegram ID: {telegram_id}\n"
        f"🔖 Junona ID: {junona_id}\n"
        f"🆔 UID: {uid}\n"
        f"💵 Сумма на вывод: {withdrawal_amount:.2f}$\n"
    )

    admin_id = 6148271304
    channel_id = -1002712429705
    try:
        await context.bot.send_message(chat_id=admin_id, text=message)
        logging.info(f"Уведомление отправлено администратору {admin_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке администратору {admin_id}: {e}")

    try:
        await context.bot.send_message(chat_id=channel_id, text=message)
        logging.info(f"Уведомление отправлено на канал {channel_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке на канал {channel_id}: {e}")


async def list_withdrawals(update: Update, context: CallbackContext):
    """Выводит список всех заявок 'в обработке' для администратора с кнопками."""
    telegram_id = update.message.from_user.id
    if telegram_id != 6148271304:  # Только для администратора
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    processing_requests = get_processing_withdrawals()
    if not processing_requests:
        await update.message.reply_text("Нет заявок на вывод в обработке.")
        return

    for req in processing_requests:
        message = (
            f"📋 Заявка на вывод:\n"
            f"🆔 ID: {req['Request ID']}\n"
            f"👤 Junona ID: {req['Junona ID']}\n"
            f"🆔 UID: {req['UID']}\n"
            f"💵 Сумма: {req['Amount']}$\n"
            f"🕒 Время заявки: {req['Request Time']}\n"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Исполнено", callback_data=f"complete_{req['Request ID']}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{req['Request ID']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=message,
            reply_markup=reply_markup
        )





async def create_withdrawals_backup(context: CallbackContext):
    """Создаёт резервную копию файла withdrawals.csv с указанием даты и времени в имени и отправляет её в канал Telegram."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "Backups"  # Указываем папку Backups
    # Создаём директорию, если она не существует
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    # Формируем путь к файлу внутри папки Backups
    backup_filename = os.path.join(backup_dir, f"withdrawals_backup_{timestamp}.csv")
    channel_id = -1002829880813  # ID канала для отправки резервной копии
    try:
        shutil.copy('withdrawals.csv', backup_filename)
        logging.info(f"Резервная копия withdrawals.csv создана: {backup_filename}")
        with open(backup_filename, 'rb') as file:
            await context.bot.send_document(chat_id=channel_id, document=file, caption=f"Резервная копия withdrawals.csv от {timestamp}")
        logging.info(f"Резервная копия withdrawals.csv отправлена в канал: {channel_id}")
    except Exception as e:
        logging.error(f"Не удалось создать или отправить резервную копию withdrawals.csv: {e}")


@retry_on_timeout()
async def send_partnership_conditions(update: Update, context: CallbackContext):
    """Отправляет информацию об условиях партнерства с оформлением в стиле шага 2 и дополнительными кнопками."""
    # Текст, который нужно выделить жирным шрифтом и заключить в рамку
    important_text = (
        "🟡 Партнер получает долю от прибыли Юноны.\n\n"
        "‼️ Доля расчитывается при начислении прибыли на счет Юноны.\n\n"
        "🧮 Например:\n"
        "У Инвестора прибыль 10,000$\n"
        "Чистая прибыль Инвестора 70% = 7,000$\n"
        "Юнона получает 30% = 3,000$\n\n"
        "Партнер 1 уровня получает 10% доли от прибыли Юноны = 300$\n"
        "Партнер 2 уровня получает 20% доли от прибыли Юноны = 600$\n"
        "Партнер 3 уровня получает 30% доли от прибыли Юноны = 900$\n"
        "Партнер 4 уровня получает 40% доли от прибыли Юноны = 1,200$\n"
        "Партнер 5 уровня получает 50% доли от прибыли Юноны = 1,500$\n\n"

        "📊 Уровень партнера определяется по сумме балансов всех приглашенных:\n"
        "Уровень 1. до 10тыс.$ - 10%\n"
        "Уровень 2. от 10тыс.$ до 100тыс.$ - 20%\n"
        "Уровень 3. от 100тыс.$ до 500тыс.$ - 30%\n"
        "Уровень 4. от 500тыс.$ до 1 млн$ - 40%\n"
        "Уровень 5. более 1 млн$ - 50%\n"
    )
    
    # Создаем рамку из символов
    horizontal_line = "─" * 13
    
    # Форматируем текст с рамкой и жирным шрифтом
    framed_text = (
        f"{horizontal_line}\n"
        f"<b>{important_text}</b>\n"
        f"{horizontal_line}"
    )
    
    # Полное сообщение
    message = (
        "\n🤝 Условия партнерства\n\n"
        f"{framed_text}\n"
    )
    
    # Клавиатура с кнопками
    keyboard = [
        [InlineKeyboardButton("🔗 Ссылка на Инструкцию", url='https://t.me/junona_edu/11')],  # Предполагаемая ссылка
        [InlineKeyboardButton("🔗 Пригласить по ссылке", callback_data='generate_link')],
        [InlineKeyboardButton("👤 Личный кабинет", callback_data='personal_cabinet')],  # Добавлена новая кнопка
        [InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')




@retry_on_timeout()
async def invite(update: Update, context: CallbackContext):
    """Обрабатывает действие invite."""
    if update.message:
        telegram_id = update.message.from_user.id
        chat_id = update.message.chat_id
    elif update.callback_query:
        telegram_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
    else:
        return

    await send_referral_link(telegram_id, context.bot, chat_id)


@retry_on_timeout()
async def support(update: Update, context: CallbackContext):
    """Обрабатывает действие support."""
    message = "\n🛠 Техническая поддержка\n\nНажмите 'Перейти в группу' и задайте свой вопрос.\nhttps://t.me/junona_3"
    keyboard = [
        [InlineKeyboardButton("🏠 Меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    elif update.callback_query:
        await context.bot.send_message(chat_id=update.callback_query.message.chat_id, text=message, reply_markup=reply_markup)



async def button_handler(update: Update, context: CallbackContext):
    """Обрабатывает нажатия кнопок, включая новые действия для предложений и отзывов."""
    query = update.callback_query
    await query.answer()

    if 'navigation_stack' not in context.user_data:
        context.user_data['navigation_stack'] = []

    if query.data in ['personal_cabinet', 'generate_link', 'support', 'connect_junona', 'register_exchange', 'partnership_conditions']:
        context.user_data['navigation_stack'].append(query.data)
        if query.data == 'connect_junona':
            await send_junona_connection_instructions(update, context)
        elif query.data == 'register_exchange':
            await send_exchange_registration_instructions(update, context)
        elif query.data == 'partnership_conditions':
            await send_partnership_conditions(update, context)
        elif query.data == 'personal_cabinet':
            await personal_cabinet(update, context)
        else:
            await handle_action(update, context, query.data)
    elif query.data == 'back':
        context.user_data['navigation_stack'] = []
        reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
        await query.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
    elif query.data == 'main_menu':
        context.user_data['navigation_stack'] = []
        reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
        await query.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
    elif query.data == 'junona_connected':
        telegram_id = query.from_user.id
        update_junona_connection_status(telegram_id, "Yes")
        await query.message.reply_text("Поздравляем!\nВы подтвердили подключение к Юноне!\n")
        await send_exchange_registration_instructions(update, context)
    elif query.data == 'exchange_registered':
        telegram_id = query.from_user.id
        update_exchange_registration_status(telegram_id, "Yes")
        user_data = get_user_data(telegram_id)
        junona_id = user_data.get('Junona ID', 'Не указано')
        await query.message.reply_text(
            f"Поздравляем!\nВы подтвердили регистрацию Junona ID: {junona_id} на бирже Bybit!\n"
        )
        await send_partnership_conditions(update, context)
    elif query.data == 'cancel_junona_connection':
        telegram_id = query.from_user.id
        update_junona_connection_status(telegram_id, "No")
        await query.message.reply_text("Подключение к Юноне отменено.")
        await personal_cabinet(update, context)
    elif query.data == 'cancel_exchange_registration':
        telegram_id = query.from_user.id
        update_exchange_registration_status(telegram_id, "No")
        await query.message.reply_text("Регистрация ID на бирже отменена.")
        await personal_cabinet(update, context)
    elif query.data.startswith('complete_'):
        request_id = query.data.split('_')[1]
        await complete_withdrawal(request_id, context)
        await query.edit_message_text(f"Заявка {request_id} исполнена.")
    elif query.data.startswith('cancel_'):
        id_str = query.data.split('_')[1]
        if id_str.isdigit():  # Проверяем, что ID — это число
            # Проверяем, является ли это заявкой на вывод
            processing_withdrawals = get_processing_withdrawals()
            if any(row['Request ID'] == id_str for row in processing_withdrawals):
                await cancel_withdrawal(id_str, context)
                await query.edit_message_text(f"Заявка {id_str} отменена.")
            else:
                # Проверяем, является ли это предложением
                processing_proposals = get_processing_proposals()
                if any(row['ID'] == id_str for row in processing_proposals):
                    await cancel_proposal(id_str, context)
                    await query.edit_message_text(f"Предложение {id_str} отменено.")
                # Проверяем, является ли это отзывом
                processing_reviews = get_processing_reviews()
                if any(row['ID'] == id_str for row in processing_reviews):
                    await cancel_review(id_str, context)
                    await query.edit_message_text(f"Отзыв {id_str} отменен.")
    elif query.data.startswith('publish_'):
        parts = query.data.split('_')
        if len(parts) == 2 and parts[0] == 'publish':
            proposal_id = parts[1]
            await publish_proposal(proposal_id, context)
            await query.edit_message_text(f"Предложение {proposal_id} опубликовано.")
        elif len(parts) == 3 and parts[0] == 'publish' and parts[1] == 'review':
            review_id = parts[2]
            await publish_review(review_id, context)
            await query.edit_message_text(f"Отзыв {review_id} опубликован.")






async def update_users_csv(data, context: CallbackContext):
    """
    Обновляет файл users.csv на основе полученных данных, находя соответствие по Junona ID.
    Пересчитывает 'Referrals Sum', 'Partner Level' и 'Partner profit', сохраняя только корректные строки.
    Создает резервную копию после обновления.
    """
    if not os.path.exists('users.csv'):
        return [], []

    with open('users.csv', 'r', newline='') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows = []
        for row in reader:
            try:
                if all(field in row for field in ['Junona ID', 'Telegram ID']):  # Проверяем обязательные поля
                    rows.append(row)
            except Exception:
                continue  # Пропускаем некорректные строки

    users_dict = {row['Junona ID']: row for row in rows}
    updated_ids = []
    not_found_ids = []

    # Обновляем данные пользователей
    for row_data in data:
        junona_id = row_data[0]
        if junona_id in users_dict:
            users_dict[junona_id]['Cum. Profit Share'] = row_data[1]
            users_dict[junona_id]['Started Investing on'] = row_data[2]
            users_dict[junona_id]['Recently Redeemed on'] = row_data[3]
            users_dict[junona_id]['Current Shares Held'] = row_data[4]
            updated_ids.append(junona_id)
        else:
            not_found_ids.append(junona_id)

    # Пересчитываем 'Referrals Sum' и 'Partner Level'
    referral_map = {}
    for row in rows:
        referral_id = row['Referral ID']
        if referral_id != "None":
            referral_map.setdefault(referral_id, []).append(row['Junona ID'])

    for row in rows:
        junona_id = row['Junona ID']
        referrals = referral_map.get(junona_id, [])
        total_sum = 0.0
        for ref_id in referrals:
            ref_row = users_dict.get(ref_id)
            if ref_row:
                try:
                    shares = float(ref_row['Current Shares Held'].replace(',', ''))
                    total_sum += shares
                except ValueError:
                    continue
        formatted_sum = f"{total_sum:,.2f}"
        row['Referrals Sum'] = formatted_sum
        row['Partner Level'] = str(determine_partner_level(total_sum))

    # Рассчитываем 'Partner profit' для всех пользователей
    for row in rows:
        junona_id = row['Junona ID']
        referrals = referral_map.get(junona_id, [])
        partner_level = int(row['Partner Level'])
        percentage = get_partner_percentage(partner_level)
        partner_profit = 0.0
        for ref_id in referrals:
            ref_row = users_dict.get(ref_id)
            if ref_row:
                profit_share = parse_profit_share(ref_row['Cum. Profit Share'])
                partner_profit += profit_share * percentage
        row['Partner profit'] = f"{partner_profit:.2f}"

    # Записываем обновленные данные
    with open('users.csv', 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    await create_backup(context)
    return updated_ids, not_found_ids







@retry_on_timeout()
async def extract_data_start(update: Update, context: CallbackContext):
    """
    При анализе скриншота извлеки текст из таблицы. 
    Выведи результат в следующем формате:
    1. Первая и последующие строки — данные строго как на скриншоте каждый символ, соответствующие заголовкам, разделённые запятой в формате csv без кавычек.
    2. Между данными из колонок, используй только одну запятую как разделитель. 
    "Извлеките текст из таблицы на скриншоте точно так, как он отображается, символ за символом. Не применяйте автокоррекцию, нормализацию или любые изменения к тексту. Обеспечьте, чтобы каждый символ, включая необычные написания или форматы, был скопирован точно."
    3. Если значение содержит запятую, заключи его в кавычки (например, "20,010.00")

    Пример вывода данных:
    Investors, Cum. Profit Share, Started Investing on, Recently Redeemed on, Current Shares Held
    J0001,0.00 USDT,2025-05-26,--,303.00
    tat***@*****,0.00 USDT,2025-05-28,--,"20,010.00"
    """
    telegram_id = update.message.from_user.id
    # Проверяем права доступа (например, только для определенного Telegram ID)
    if telegram_id != 6148271304:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Пожалуйста, отправьте данные в формате:\n"
        "Junona ID, Cum. Profit Share, Started Investing on, Recently Redeemed on, Current Shares Held\n"
        "Например:\n"
        "J0001,0.00 USDT,2025-05-26,--,303.00\n"
        "tat***@*****,\"20,010.00 USDT\",2025-05-28,--,206.36\n"
        "Обратите внимание: если значение содержит запятую (например, 20,010.00), заключите его в кавычки."
    )
    return WAITING_FOR_DATA


@retry_on_timeout()
async def extract_data_process(update: Update, context: CallbackContext):
    """
    Обрабатывает данные без заголовков, отправленные пользователем, обновляет users.csv и сообщает о результатах.
    Использует csv.reader для корректной обработки запятых внутри полей.
    После отправки сообщения о результатах отображает главное меню.
    """
    data_text = update.message.text.strip()
    if not data_text:
        await update.message.reply_text("Пожалуйста, предоставьте данные в указанном формате.\nДля отмены используйте /cancel.")
        return WAITING_FOR_DATA

    try:
        data_file = StringIO(data_text)
        reader = csv.reader(data_file, delimiter=',', quotechar='"')
        errors = []
        valid_data = []
        for row in reader:
            if not row:  # Пропускаем пустые строки
                continue
            if len(row) != 5:
                errors.append(f"Неверное количество полей в строке: {','.join(row)}. Ожидается 5 полей.")
            else:
                junona_id = row[0].strip()
                cum_profit = row[1].strip()
                started = row[2].strip()
                redeemed = row[3].strip()
                shares = row[4].strip()
                valid_data.append([junona_id, cum_profit, started, redeemed, shares])

        if errors:
            error_message = "Обнаружены ошибки в следующих строках:\n" + "\n".join(errors) + "\nПожалуйста, исправьте ошибки и отправьте данные заново. Для отмены используйте /cancel."
            await update.message.reply_text(error_message)
            return WAITING_FOR_DATA
        else:
            # Обновляем файл users.csv и получаем результаты с использованием await
            updated_ids, not_found_ids = await update_users_csv(valid_data, context)
            # Формируем сообщение для пользователя
            message = ""
            if updated_ids:
                message += "Данные успешно обновлены для следующих Junona ID:\n" + "\n".join(updated_ids) + "\n"
            if not_found_ids:
                message += "\nСледующие Junona ID не найдены в базе:\n" + "\n".join(not_found_ids) + "\n"
            if not updated_ids and not not_found_ids:
                message = "Не найдено совпадающих Junona ID для обновления."
            await update.message.reply_text(message)
            # Отправляем главное меню
            reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
            await update.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
            return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке данных: {str(e)}. Пожалуйста, проверьте формат и попробуйте снова.\nДля отмены используйте /cancel.")
        return WAITING_FOR_DATA
    

async def cancel(update: Update, context: CallbackContext):
    """
    Отменяет операцию обработки данных и завершает диалог.
    """
    await update.message.reply_text("Операция отменена.")
    return ConversationHandler.END



async def start_get_username(update: Update, context: CallbackContext):
    """Запускает команду /3, проверяет права админа и запрашивает Telegram ID."""
    telegram_id = update.message.from_user.id
    admin_id = 6148271304  # ID администратора

    # Проверка, является ли пользователь администратором
    if telegram_id != admin_id:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return ConversationHandler.END

    # Запрос Telegram ID у администратора
    await update.message.reply_text(
        "Пожалуйста, введите Telegram ID пользователя, чтобы получить его данные.\n"
        "Пример: 6148271304\n"
        "Для отмены используйте /cancel."
    )
    return WAITING_FOR_TELEGRAM_ID



async def process_telegram_id_for_username(update: Update, context: CallbackContext):
    """Обрабатывает введённый Telegram ID и получает ник, имя, фамилию и информацию о телефоне пользователя."""
    telegram_id_input = update.message.text.strip()

    # Проверка, что введено число
    if not telegram_id_input.isdigit():
        await update.message.reply_text(
            "❌ Telegram ID должен состоять только из цифр.\n"
            "Пример: 6148271304\n"
            "Пожалуйста, введите заново."
        )
        return WAITING_FOR_TELEGRAM_ID

    target_user_id = int(telegram_id_input)

    try:
        # Получаем информацию о пользователе
        user = await context.bot.get_chat(target_user_id)
        username = user.username if user.username else "Не установлен"
        first_name = user.first_name if user.first_name else "Не указано"
        last_name = user.last_name if user.last_name else "Не указано"
        
        # Формируем сообщение с данными и ссылкой на профиль
        message = (
            f"Информация о пользователе с Telegram ID {target_user_id}:\n"
            f"\ntg://user?id={target_user_id}\n\n"
            f"Ник: @{username}\n"
            f"Имя: {first_name}\n"
            f"Фамилия: {last_name}\n"
        )
        await update.message.reply_text(message, parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(
            f"❌ Не удалось получить информацию о пользователе {target_user_id}.\n"
            f"Ошибка: {str(e)}\n"
            "Возможно, пользователь не существует или не взаимодействовал с ботом."
        )

    # Возвращаем главное меню
    reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
    await update.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
    return ConversationHandler.END




def init_proposals_csv():
    """Инициализирует или обновляет файл proposals.csv, добавляя недостающие колонки с 'Suggestion' в конце."""
    expected_columns = ['ID', 'Timestamp', 'Identifier', 'Junona ID', 'Telegram ID', 'Status', 'Suggestion']
    update_csv_headers('proposals.csv', expected_columns)


def update_csv_headers(file_path, expected_columns):
    """
    Обновляет заголовки CSV-файла, добавляя недостающие колонки из expected_columns в конец.
    Сохраняет существующие данные, добавляя пустые значения для новых колонок.
    """
    if not os.path.exists(file_path):
        # Если файл не существует, создаём его с ожидаемыми заголовками
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(expected_columns)
        return

    with open(file_path, 'r', newline='') as file:
        reader = csv.reader(file)
        try:
            headers = next(reader)
        except StopIteration:
            headers = []
        rows = list(reader)

    # Определяем недостающие колонки
    missing_columns = [col for col in expected_columns if col not in headers]

    if not missing_columns:
        return

    # Обновляем заголовки, добавляя недостающие колонки в конец
    updated_headers = headers + missing_columns

    # Дополняем существующие строки пустыми значениями для новых колонок
    updated_rows = [row + [''] * len(missing_columns) for row in rows]

    # Перезаписываем файл с обновлёнными заголовками и строками
    with open(file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(updated_headers)
        writer.writerows(updated_rows)

    logging.info(f"Добавлены колонки {missing_columns} в {file_path}")

    


def get_next_proposal_id():
    """Возвращает следующий ID для предложения."""
    if not os.path.exists('proposals.csv'):
        return 1
    with open('proposals.csv', 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
        if len(rows) > 1:  # Учитываем заголовок
            last_id = int(rows[-1][0])
            return last_id + 1
        return 1
    


def add_proposal_to_csv(proposal_id, timestamp, suggestion, identifier, junona_id, telegram_id):
    """Добавляет новое предложение в файл proposals.csv со статусом 'в обработке' и колонкой 'Suggestion' в конце."""
    with open('proposals.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        # Записываем в порядке: ID, Timestamp, Identifier, Junona ID, Telegram ID, Status, Suggestion
        writer.writerow([proposal_id, timestamp, identifier, junona_id, telegram_id, 'в обработке', suggestion])


def get_processing_proposals():
    """Возвращает список всех предложений со статусом 'в обработке'."""
    if not os.path.exists('proposals.csv'):
        return []
    with open('proposals.csv', 'r') as file:
        reader = csv.DictReader(file)
        processing = [row for row in reader if row['Status'] == 'в обработке']
    return processing



def update_proposal_status(proposal_id, status):
    """Обновляет статус предложения в proposals.csv."""
    if not os.path.exists('proposals.csv'):
        logging.error("Файл proposals.csv не существует.")
        return
    rows = []
    found = False
    with open('proposals.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['ID'].strip() == str(proposal_id).strip():
                row['Status'] = status
                found = True
            rows.append(row)
    if not found:
        logging.warning(f"Предложение с ID {proposal_id} не найдено в файле.")
    with open('proposals.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



async def publish_proposal(proposal_id, context: CallbackContext):
    """Публикует предложение в группе сообщества и уведомляет пользователя о публикации."""
    group_id = -1002829880813  # ID группы для публикации
    with open('proposals.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['ID'] == str(proposal_id):
                suggestion = row['Suggestion']
                identifier = row['Identifier']
                timestamp = row['Timestamp']
                telegram_id = row['Telegram ID']  # Получаем Telegram ID пользователя
                break
        else:
            logging.error(f"Предложение с ID {proposal_id} не найдено.")
            return

    # Формируем сообщение для публикации в группе
    message = (
        f"📋 Предложение по улучшению Юноны:\n"
        f"🆔 ID: {proposal_id}\n"
        f"🕒 Время: {timestamp}\n"
        f"👥 От: {identifier}\n"
        f"📝 Текст: {suggestion}\n"
    )
    try:
        await context.bot.send_message(chat_id=group_id, text=message)
        update_proposal_status(proposal_id, 'опубликовано')
        await send_proposals_backup(context)
        logging.info(f"Предложение {proposal_id} опубликовано в группе {group_id}")

        # Уведомляем пользователя о публикации
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"✅ Ваше предложение с ID {proposal_id} было опубликовано в группе сообщества."
        )
        logging.info(f"Уведомление о публикации предложения {proposal_id} отправлено пользователю {telegram_id}")
    except Exception as e:
        logging.error(f"Ошибка при публикации предложения {proposal_id}: {e}")





async def cancel_proposal(proposal_id, context: CallbackContext):
    """Отменяет предложение, меняя статус на 'отменено', и уведомляет пользователя."""
    logging.info(f"Запуск отмены предложения с ID: {proposal_id}")
    update_proposal_status(proposal_id, 'отменено')
    await send_proposals_backup(context)
    try:
        with open('proposals.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['ID'].strip() == str(proposal_id).strip():
                    telegram_id = int(row['Telegram ID'])
                    logging.info(f"Найден пользователь с Telegram ID: {telegram_id} для предложения {proposal_id}")
                    break
            else:
                logging.error(f"Предложение с ID {proposal_id} не найдено в файле.")
                return
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"Ваше предложение с ID {proposal_id} было отменено."
        )
        logging.info(f"Предложение {proposal_id} отменено, уведомление отправлено пользователю {telegram_id}")
    except Exception as e:
        logging.error(f"Ошибка при отмене предложения {proposal_id}: {e}")



async def send_proposals_backup(context: CallbackContext):
    """Сохраняет резервную копию proposals.csv в папке Backups и отправляет её на канал резервных копий."""
    channel_id = -1002829880813  # ID канала для резервных копий
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "Backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    backup_filename = os.path.join(backup_dir, f"proposals_backup_{timestamp}.csv")
    try:
        shutil.copy('proposals.csv', backup_filename)
        logging.info(f"Резервная копия proposals.csv создана: {backup_filename}")
        with open(backup_filename, 'rb') as file:
            await context.bot.send_document(chat_id=channel_id, document=file, caption=f"Резервная копия proposals.csv от {timestamp}")
        logging.info(f"Резервная копия proposals.csv отправлена на канал: {channel_id}")
        # Файл остается в папке Backups
    except Exception as e:
        logging.error(f"Не удалось создать или отправить резервную копию proposals.csv: {e}")



async def proposal_start(update: Update, context: CallbackContext):
    """Запускает процесс сбора предложения или отображает статус последнего активного предложения."""
    telegram_id = update.message.from_user.id
    active_proposal = get_user_active_proposal(telegram_id)
    if active_proposal:
        message = (
            f"Ваше последнее активное предложение на модерации:\n"
            f"🕒 Время: {active_proposal['Timestamp']}\n"
            f"🆔 ID: {active_proposal['ID']}\n"
            f"📝 Текст: {active_proposal['Suggestion']}\n"
            "Пожалуйста, дождитесь завершения модерации перед отправкой нового предложения."
        )
        await update.message.reply_text(message)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "💡 Предложение по улучшению проекта Юнона.\n\n"
            "✍️ Пожалуйста, напишите и отправьте ваше предложение:"
        )
        return WAITING_FOR_SUGGESTION
    


async def receive_suggestion(update: Update, context: CallbackContext):
    """Получает текст предложения и запрашивает идентификатор автора, включая Junona ID в提示."""
    context.user_data['suggestion'] = update.message.text
    telegram_id = update.message.from_user.id
    user_data = get_user_data(telegram_id)
    junona_id = user_data.get('Junona ID', 'Не указано')
    
    # Модифицированный текст с Junona ID пользователя
    prompt_text = f"От кого опубликовать предложение? (вы можете указать ваш Junona ID: {junona_id}, любой ник или ваше Имя Фамилию):"
    await update.message.reply_text(prompt_text)
    return WAITING_FOR_IDENTIFIER


async def receive_identifier(update: Update, context: CallbackContext):
    """Получает идентификатор автора, сохраняет предложение со статусом 'в обработке', отправляет уведомление администратору и завершает процесс."""
    identifier = update.message.text
    telegram_id = update.message.from_user.id
    user_data = get_user_data(telegram_id)
    junona_id = user_data.get('Junona ID', 'Не указано')
    
    # Сохраняем предложение
    proposal_id = get_next_proposal_id()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    suggestion = context.user_data['suggestion']
    
    add_proposal_to_csv(proposal_id, timestamp, suggestion, identifier, junona_id, telegram_id)
    
    # Отправляем файл на канал резервных копий
    await send_proposals_backup(context)
    
    # Отправляем уведомление администратору
    await send_proposal_to_admin(proposal_id, timestamp, suggestion, identifier, junona_id, telegram_id, context)
    
    await update.message.reply_text(
        f"✅ Ваше предложение зарегистрировано под номером {proposal_id} и отправлено на модерацию. Спасибо за ваш вклад!"
    )
    
    # Очищаем user_data
    context.user_data.pop('suggestion', None)
    
    # Возвращаем главное меню
    reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
    await update.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext):
    """Отменяет текущую операцию."""
    await update.message.reply_text("Операция отменена.")
    # Очищаем user_data, если там есть данные предложения
    context.user_data.pop('suggestion', None)
    return ConversationHandler.END


def get_user_active_proposal(telegram_id):
    """Возвращает последнее активное предложение пользователя."""
    if not os.path.exists('proposals.csv'):
        return None
    with open('proposals.csv', 'r') as file:
        reader = csv.DictReader(file)
        proposals = [row for row in reader if row['Telegram ID'] == str(telegram_id) and row['Status'] == 'в обработке']
    if proposals:
        return proposals[-1]  # Возвращаем последнее предложение
    return None

async def list_proposals(update: Update, context: CallbackContext):
    """Выводит список всех предложений 'в обработке' для администратора с кнопками."""
    telegram_id = update.message.from_user.id
    if telegram_id != 6148271304:  # Только для администратора
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    processing_proposals = get_processing_proposals()
    if not processing_proposals:
        await update.message.reply_text("Нет предложений на модерации.")
        return

    for proposal in processing_proposals:
        message = (
            f"📋 Предложение:\n"
            f"🆔 ID: {proposal['ID']}\n"
            f"👤 Junona ID: {proposal['Junona ID']}\n"
            f"📝 Текст: {proposal['Suggestion']}\n"
            f"🕒 Время: {proposal['Timestamp']}\n"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅", callback_data=f"publish_{proposal['ID']}"),
                InlineKeyboardButton("❌", callback_data=f"cancel_{proposal['ID']}")  # Исправлено на cancel_<id>
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=message,
            reply_markup=reply_markup
        )

async def send_proposal_to_admin(proposal_id, timestamp, suggestion, identifier, junona_id, telegram_id, context: CallbackContext):
    """Отправляет администратору сообщение с деталями предложения и кнопками для одобрения или отклонения."""
    admin_id = 6148271304  # ID администратора
    message = (
        f"📋 Новое предложение:\n"
        f"🆔 ID: {proposal_id}\n"
        f"🕒 Время: {timestamp}\n"
        f"👤 Junona ID: {junona_id}\n"
        f"🆔 Telegram ID: {telegram_id}\n"
        f"👥 От: {identifier}\n"
        f"📝 Текст: {suggestion}\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅", callback_data=f"publish_{proposal_id}"),
            InlineKeyboardButton("❌", callback_data=f"cancel_{proposal_id}")  # Исправлено на cancel_<id>
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=message,
            reply_markup=reply_markup
        )
        logging.info(f"Уведомление о предложении {proposal_id} отправлено администратору {admin_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")



def init_reviews_csv():
    """Инициализирует или обновляет файл reviews.csv, добавляя недостающие колонки с 'Review' в конце."""
    expected_columns = ['ID', 'Timestamp', 'Identifier', 'Junona ID', 'Telegram ID', 'Status', 'Review']
    update_csv_headers('reviews.csv', expected_columns)


def get_next_review_id():
    """Возвращает следующий ID для отзыва."""
    if not os.path.exists('reviews.csv'):
        return 1
    with open('reviews.csv', 'r') as file:
        reader = csv.reader(file)
        rows = list(reader)
        if len(rows) > 1:  # Учитываем заголовок
            last_id = int(rows[-1][0])
            return last_id + 1
        return 1
    

def add_review_to_csv(review_id, timestamp, review, identifier, junona_id, telegram_id):
    """Добавляет новый отзыв в файл reviews.csv со статусом 'в обработке' и колонкой 'Review' в конце."""
    with open('reviews.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        # Записываем в порядке: ID, Timestamp, Identifier, Junona ID, Telegram ID, Status, Review
        writer.writerow([review_id, timestamp, identifier, junona_id, telegram_id, 'в обработке', review])


def get_processing_reviews():
    """Возвращает список всех отзывов со статусом 'в обработке'."""
    if not os.path.exists('reviews.csv'):
        return []
    with open('reviews.csv', 'r') as file:
        reader = csv.DictReader(file)
        processing = [row for row in reader if row['Status'] == 'в обработке']
    return processing


def update_review_status(review_id, status):
    """Обновляет статус отзыва в reviews.csv."""
    if not os.path.exists('reviews.csv'):
        logging.error("Файл reviews.csv не существует.")
        return
    rows = []
    found = False
    with open('reviews.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['ID'].strip() == str(review_id).strip():
                row['Status'] = status
                found = True
            rows.append(row)
    if not found:
        logging.warning(f"Отзыв с ID {review_id} не найден в файле.")
    with open('reviews.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logging.info(f"Файл reviews.csv обновлен, статус отзыва {review_id} изменен на '{status}'")


async def publish_review(review_id, context: CallbackContext):
    """Публикует отзыв в группе сообщества и уведомляет пользователя о публикации."""
    group_id = -1002829880813  # ID группы для публикации
    with open('reviews.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['ID'] == str(review_id):
                review = row['Review']
                identifier = row['Identifier']
                timestamp = row['Timestamp']
                telegram_id = row['Telegram ID']  # Получаем Telegram ID пользователя
                break
        else:
            logging.error(f"Отзыв с ID {review_id} не найден.")
            return

    # Формируем сообщение для публикации в группе
    message = (
        f"📋 Отзыв о проекте Юнона:\n"
        f"🆔 ID: {review_id}\n"
        f"🕒 Время: {timestamp}\n"
        f"👥 От: {identifier}\n"
        f"📝 Текст: {review}\n"
    )
    try:
        await context.bot.send_message(chat_id=group_id, text=message)
        update_review_status(review_id, 'опубликовано')
        await send_reviews_backup(context)
        logging.info(f"Отзыв {review_id} опубликован в группе {group_id}")

        # Уведомляем пользователя о публикации
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"✅ Ваш отзыв с ID {review_id} был опубликован в группе и канале сообщества."
        )
        logging.info(f"Уведомление о публикации отзыва {review_id} отправлено пользователю {telegram_id}")
    except Exception as e:
        logging.error(f"Ошибка при публикации отзыва {review_id}: {e}")



async def cancel_review(review_id, context: CallbackContext):
    """Отменяет отзыв, меняя статус на 'отменено', и уведомляет пользователя."""
    logging.info(f"Запуск отмены отзыва с ID: {review_id}")
    update_review_status(review_id, 'отменено')
    await send_reviews_backup(context)
    try:
        with open('reviews.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['ID'].strip() == str(review_id).strip():
                    telegram_id = int(row['Telegram ID'])
                    logging.info(f"Найден пользователь с Telegram ID: {telegram_id} для отзыва {review_id}")
                    break
            else:
                logging.error(f"Отзыв с ID {review_id} не найден в файле.")
                return
        await context.bot.send_message(
            chat_id=telegram_id,
            text=f"Ваш отзыв с ID {review_id} был отменен."
        )
        logging.info(f"Отзыв {review_id} отменен, уведомление отправлено пользователю {telegram_id}")
    except Exception as e:
        logging.error(f"Ошибка при отмене отзыва {review_id}: {e}")



async def send_reviews_backup(context: CallbackContext):
    """Сохраняет резервную копию reviews.csv в папке Backups и отправляет её на канал резервных копий."""
    channel_id = -1002829880813  # ID канала для резервных копий
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "Backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    backup_filename = os.path.join(backup_dir, f"reviews_backup_{timestamp}.csv")
    try:
        shutil.copy('reviews.csv', backup_filename)
        logging.info(f"Резервная копия reviews.csv создана: {backup_filename}")
        with open(backup_filename, 'rb') as file:
            await context.bot.send_document(chat_id=channel_id, document=file, caption=f"Резервная копия reviews.csv от {timestamp}")
        logging.info(f"Резервная копия reviews.csv отправлена на канал: {channel_id}")
        # Файл остается в папке Backups
    except Exception as e:
        logging.error(f"Не удалось создать или отправить резервную копию reviews.csv: {e}")




async def review_start(update: Update, context: CallbackContext):
    """Запускает процесс сбора отзыва или отображает статус последнего активного отзыва."""
    telegram_id = update.message.from_user.id
    active_review = get_user_active_review(telegram_id)
    if active_review:
        message = (
            f"Ваш последний активный отзыв на модерации:\n"
            f"🕒 Время: {active_review['Timestamp']}\n"
            f"🆔 ID: {active_review['ID']}\n"
            f"📝 Текст: {active_review['Review']}\n"
            "Пожалуйста, дождитесь завершения модерации перед отправкой нового отзыва."
        )
        await update.message.reply_text(message)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "📝 Отзыв о проекте Юнона.\n\n"
            "✍️ Пожалуйста, напишите и отправьте ваш отзыв:"
        )
        return WAITING_FOR_SUGGESTION  # Используем то же состояние, что для предложений
    

async def receive_review(update: Update, context: CallbackContext):
    """Получает текст отзыва и запрашивает идентификатор автора, включая Junona ID в提示."""
    context.user_data['review'] = update.message.text
    telegram_id = update.message.from_user.id
    user_data = get_user_data(telegram_id)
    junona_id = user_data.get('Junona ID', 'Не указано')
    
    prompt_text = f"От кого опубликовать отзыв? (вы можете указать ваш Junona ID: {junona_id}, любой ник или ваше Имя Фамилию):"
    await update.message.reply_text(prompt_text)
    return WAITING_FOR_IDENTIFIER  # Используем то же состояние, что для предложений


async def receive_review_identifier(update: Update, context: CallbackContext):
    """Получает идентификатор автора, сохраняет отзыв со статусом 'в обработке', отправляет уведомление администратору и завершает процесс."""
    identifier = update.message.text
    telegram_id = update.message.from_user.id
    user_data = get_user_data(telegram_id)
    junona_id = user_data.get('Junona ID', 'Не указано')
    
    review_id = get_next_review_id()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    review = context.user_data['review']
    
    add_review_to_csv(review_id, timestamp, review, identifier, junona_id, telegram_id)
    
    await send_reviews_backup(context)
    
    await send_review_to_admin(review_id, timestamp, review, identifier, junona_id, telegram_id, context)
    
    await update.message.reply_text(
        f"✅ Ваш отзыв зарегистрирован под номером {review_id} и отправлен на модерацию. Спасибо за ваш отзыв!"
    )
    
    context.user_data.pop('review', None)
    
    reply_markup = InlineKeyboardMarkup(get_main_menu_keyboard())
    await update.message.reply_text("Вы в Главном меню", reply_markup=reply_markup)
    return ConversationHandler.END

def get_user_active_review(telegram_id):
    """Возвращает последний активный отзыв пользователя."""
    if not os.path.exists('reviews.csv'):
        return None
    with open('reviews.csv', 'r') as file:
        reader = csv.DictReader(file)
        reviews = [row for row in reader if row['Telegram ID'] == str(telegram_id) and row['Status'] == 'в обработке']
    if reviews:
        return reviews[-1]  # Возвращаем последний отзыв
    return None


async def list_reviews(update: Update, context: CallbackContext):
    """Выводит список всех отзывов 'в обработке' для администратора с кнопками."""
    telegram_id = update.message.from_user.id
    if telegram_id != 6148271304:  # Только для администратора
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    processing_reviews = get_processing_reviews()
    if not processing_reviews:
        await update.message.reply_text("Нет отзывов на модерации.")
        return

    for review in processing_reviews:
        message = (
            f"📋 Отзыв:\n"
            f"🆔 ID: {review['ID']}\n"
            f"👤 Junona ID: {review['Junona ID']}\n"
            f"📝 Текст: {review['Review']}\n"
            f"🕒 Время: {review['Timestamp']}\n"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅", callback_data=f"publish_review_{review['ID']}"),
                InlineKeyboardButton("❌", callback_data=f"cancel_{review['ID']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=message,
            reply_markup=reply_markup
        )




async def send_review_to_admin(review_id, timestamp, review, identifier, junona_id, telegram_id, context: CallbackContext):
    """Отправляет администратору сообщение с деталями отзыва и кнопками для одобрения или отклонения."""
    admin_id = 6148271304  # ID администратора
    message = (
        f"📋 Новый отзыв:\n"
        f"🆔 ID: {review_id}\n"
        f"🕒 Время: {timestamp}\n"
        f"👤 Junona ID: {junona_id}\n"
        f"🆔 Telegram ID: {telegram_id}\n"
        f"👥 От: {identifier}\n"
        f"📝 Текст: {review}\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅", callback_data=f"publish_review_{review_id}"),
            InlineKeyboardButton("❌", callback_data=f"cancel_{review_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=message,
            reply_markup=reply_markup
        )
        logging.info(f"Уведомление о отзыве {review_id} отправлено администратору {admin_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")




async def privacy_policy(update: Update, context: CallbackContext):
    text = """Политика конфиденциальности Telegram бота @junona_partner_bot

Администрация Telegram бота @junona_partner_bot обязуется сохранять вашу конфиденциальность в Интернете. Мы уделяем большое значение охране предоставленных вами данных. Наша политика конфиденциальности основана на требованиях политик конфиденциальности Telegram и магазинов Apple и Google.

Мы не собираем и не обрабатываем персональные данные пользователей. Наш Telegram бот в целях осуществления работы сервиса использует только неперсонализированный Telegram ID.

Сбор и использование персональных данных

Мы не запрашиваем и не собираем никаких персональных данных. Все данные пользователей в нашем сервисе привязаны только к неперсонализированному Telegram ID.

Когда вы запускаете Telegram бот @junona_partner_bot, Telegram автоматически передает нам только ваш Telegram ID, который не дает нам доступа к вашей личной информации.

Хранение данных, изменение и удаление

Пользователь, предоставивший свой Telegram-ID нашему Telegram боту @junona_partner_bot имеет право на удаление своих данных, привязанных к Telegram ID, кроме информации о блокировке пользователя.

Раскрытие информации третьим лицам

Мы не продаем, не используем и не раскрываем третьим лицам какие-либо данные своих пользователей для каких-либо целей.

Предоставление информации детям

Если вы являетесь родителем или опекуном, и вы знаете, что ваши дети предоставили нам свои данные без вашего согласия, свяжитесь с нами.

Изменения в политике конфиденциальности

Telegram бот @junona_partner_bot может обновлять нашу политику конфиденциальности время от времени. Мы сообщаем о любых изменениях, разместив новую политику конфиденциальности на этой странице. Если вы оставили данные у нас, то мы оповестим вас об изменении в политике конфиденциальности при помощи бота @junona_partner_bot.

Обратная связь, заключительные положения

Связаться с администрацией Telegram бота @junona_partner_bot по вопросам, связанным с политикой конфиденциальности можно с помощью контактной информации указанной в разделе Техническая поддержка нашего бота. Если вы не согласны с данной политикой конфиденциальности, вы не можете пользоваться услугами Telegram бота @junona_partner_bot."""
    await update.message.reply_text(text)



def main():
    """Запускает бота с инициализацией CSV-файла и обработчиками команд."""
    init_csv()  # Инициализируем CSV
    migrate_csv_schema()  # Миграция схемы для добавления новых колонок
    init_proposals_csv()  # Инициализируем proposals.csv
    init_reviews_csv()  # Инициализируем reviews.csv
    logging.info("Бот запущен!")
    
    # Настройка приложения с увеличенными таймаутами
    application = Application.builder().token(TELEGRAM_TOKEN).connect_timeout(20).read_timeout(20).build()
    
    # Состояния для ConversationHandler'ов
    global WAITING_FOR_DATA, WAITING_FOR_UID, WAITING_FOR_AMOUNT, WAITING_FOR_TELEGRAM_ID, WAITING_FOR_SUGGESTION, WAITING_FOR_IDENTIFIER
    WAITING_FOR_DATA = 1
    WAITING_FOR_UID, WAITING_FOR_AMOUNT, WAITING_FOR_TELEGRAM_ID = range(2, 5)
    WAITING_FOR_SUGGESTION, WAITING_FOR_IDENTIFIER = range(5, 7)  # Состояния для предложений и отзывов

    # ConversationHandler для команды /extract_data
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('1', extract_data_start)],
        states={
            WAITING_FOR_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, extract_data_process)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    # ConversationHandler для вывода прибыли
    withdraw_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_profit_start, pattern='withdraw_profit')],
        states={
            WAITING_FOR_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_profit_uid)],
            WAITING_FOR_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_profit_amount)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    # ConversationHandler для команды /3
    get_username_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('3', start_get_username)],
        states={
            WAITING_FOR_TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_telegram_id_for_username)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    # ConversationHandler для предложений
    proposal_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('proposal', proposal_start)],
        states={
            WAITING_FOR_SUGGESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_suggestion)],
            WAITING_FOR_IDENTIFIER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_identifier)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    # ConversationHandler для отзывов
    review_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('review', review_start)],
        states={
            WAITING_FOR_SUGGESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_review)],
            WAITING_FOR_IDENTIFIER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_review_identifier)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("personal_cabinet", lambda update, context: handle_action(update, context, 'personal_cabinet')))
    application.add_handler(CommandHandler("invite", lambda update, context: handle_action(update, context, 'generate_link')))
    application.add_handler(CommandHandler("support", lambda update, context: handle_action(update, context, 'support')))
    application.add_handler(CommandHandler("connect_junona", send_junona_connection_instructions))
    application.add_handler(CommandHandler("register_exchange", send_exchange_registration_instructions))
    application.add_handler(CommandHandler("partnership_conditions", send_partnership_conditions))
    application.add_handler(CommandHandler("2", list_withdrawals))  # Список заявок на вывод
    application.add_handler(CommandHandler("4", list_proposals))  # Список предложений
    application.add_handler(CommandHandler("5", list_reviews))  # Список отзывов
    application.add_handler(CommandHandler("privacy", privacy_policy))  # Политика конфиденциальности
    application.add_handler(conv_handler)  # Для /extract_data
    application.add_handler(withdraw_conv_handler)  # Для вывода прибыли
    application.add_handler(get_username_conv_handler)  # Для /3
    application.add_handler(proposal_conv_handler)  # Для предложений
    application.add_handler(review_conv_handler)  # Для отзывов
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Настройка команд в меню бота
    async def post_init(application: Application):
        commands = [
            BotCommand("start", "🫂 Знакомство с проектом"),
            BotCommand("connect_junona", "🔌 Подключение к Юноне"),
            BotCommand("register_exchange", "📝 Регистрация ID на бирже"),
            BotCommand("partnership_conditions", "🤝 Условия партнерства"),
            BotCommand("personal_cabinet", "👤 Личный кабинет"),
            BotCommand("invite", "🔗 Пригласить по ссылке"),
            BotCommand("support", "🛠 Техническая поддержка"),
            BotCommand("proposal", "💡 Предложения"),
            BotCommand("review", "📝 Оставить отзыв"),  # Новая команда
            BotCommand("privacy", "📜 Конфиденциальность"),
        ]
        await application.bot.set_my_commands(commands)
    
    application.post_init = post_init
    



    application.run_polling()





if __name__ == '__main__':
    main()



# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 
# для Телеграм используй библиотеку python-telegram-bot Version: 22.1







