# j3_368_BN

import keyring
import time
import threading
from datetime import datetime, timedelta
import csv
import pandas as pd
from pathlib import Path
import numpy as np
import talib
import requests
import math
from pybit.unified_trading import HTTP
import logging
import subprocess
import json
import getpass
from cryptography.fernet import Fernet
from binance.client import Client
from binance.exceptions import BinanceAPIException


def setup_logging():
    # Создаем логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Удаляем все существующие обработчики, чтобы избежать дублирования
    if logger.handlers:
        logger.handlers.clear()

    # Создаем файловый обработчик
    file_handler = logging.FileHandler('logs.txt', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # Создаем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    # Вызываем функцию очистки логов при запуске
    cleanup_logs()


def cleanup_logs():
    try:
        with open('logs.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            return

        now = datetime.now()
        cutoff_date = now - timedelta(days=14)
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)

        filtered_lines = []
        current_date = None

        for line in lines:
            try:
                timestamp_str = line.split(' - ')[0]
                log_date = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                log_day_start = log_date.replace(hour=0, minute=0, second=0, microsecond=0)

                # Проверяем, сменились ли сутки с последней проверкой
                if current_date != log_day_start:
                    current_date = log_day_start

                if log_day_start >= cutoff_date:
                    filtered_lines.append(line)
            except (ValueError, IndexError):
                # Пропускаем строки с некорректным форматом
                continue

        # Если была очистка, переписываем файл
        if len(filtered_lines) < len(lines):
            with open('logs.txt', 'w', encoding='utf-8') as f:
                f.writelines(filtered_lines)
            log_event("🧹 Очищены старые записи из logs.txt")
    except FileNotFoundError:
        # Если файла нет, он будет создан автоматически обработчиком
        pass
    except Exception as e:
        # Логируем ошибку в консоль, так как файл может быть недоступен
        print(f"Ошибка при очистке логов: {e}")


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

BINANCE_API_KEY = keyring.get_password("binance_api_key", "TG_bot")
BINANCE_SECRET_KEY = keyring.get_password("binance_api_secret", "TG_bot")


# Инициализация клиента (предполагается, что API_KEY и API_SECRET загружены)
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_SECRET_KEY)


# Путь к файлу ошибок WebSocket
ERROR_LOG_FILE = Path("errors.log")


# Определение типов данных для столбцов CSV
CSV_DTYPES = {
    'Trade_ID': str,
    'Status': str,
    'Direction': str,
    'Entry_Time': str,
    'Exit_Time': str,
    'Trade_Duration': str,
    'Entry_Price': float,
    'Exit_Price': float,
    'Take_Profit': float,
    'Position_Size': float,
    'Position_Value': float,
    'Leverage': float,
    'PnL_USDT': float,
    'PnL_Percent': float,
    'Commission_USDT': float,
    'Net_PnL_USDT': float,
    'Net_PnL_Percent': float,
    'Withdraw': float  # Новая колонка для суммы вывода
}


# Глобальные торговые параметры
TRADING_CONFIG = {
    'ENABLE_LONG': True,
    'ENABLE_SHORT': True,
    'COMMISSION_RATE': 0.05,
    'ENABLE_LOGGING': True,
    'IMPULSE_ENTRY_PERCENT': 90,  # Процент от доступного баланса для импульсных сделок

    'BULL_LONG': {'LEVERAGE': 3.0,},
    'BULL_SHORT': {'LEVERAGE': 3.0,},

    'BEAR_SHORT': {'LEVERAGE': 3.0,}
}


ANALYSIS_TIMEFRAME = '1h'

GLOBAL_TIMEFRAME = '1w'  


MIN_DELTA_LIQUIDATION_LONG = 10.0  # Минимальная дельта для лонг-позиций
MIN_DELTA_LIQUIDATION_SHORT = 10.0 # Минимальная дельта для шорт-позиций

# Глобальные переменные для RSI и SMA RSI (добавлены в начало файла после импортов)
RSI_PERIOD = 22
SMA_RSI_PERIOD = 19



symbol = 'BTCUSDT'
MAX_ACTIVE_TRADES = 1
previous_rsi = None
previous_sma_rsi = None
current_trade_type = None
next_analysis_time = None  # Время следующего обновления данных о сделках
next_liquidation_update_time = None
active_trades = {}  # Словарь для хранения всех активных сделок по их ID
next_trade_id = 1  # Счетчик для генерации уникальных ID сделок
trades_lock = threading.RLock()  # Блокировка для безопасного обновления списка сделок
last_trade_time = 0  # Время последней открытой сделки (в секундах)
last_price_indicator = ""
long_averaging_trades_count = 0
short_averaging_trades_count = 0
fear_greed_data = None
next_rsi_update_time = None
current_rsi = None
current_sma_rsi = None
previous_mid_price = 0
bull_long_trades_count = 0
bull_short_trades_count = 0




# Путь к CSV-файлу
CSV_FILE = Path(f"trade_history.csv")
df_trades = None  # Глобальная переменная для хранения DataFrame с историей сделок


# Константы для определения циклов рынка
START_DATE = datetime(2015, 1, 12)  # Начальная дата
CYCLE_LENGTH = 1428  # Длина цикла в днях (152 недели бычьего + 52 недели медвежьего = 204 недели)
BULL_DAYS = 1064    # Длина бычьего рынка в днях (152 недели * 7 дней)

def get_market_type(date):
    delta = date - START_DATE
    delta_days = delta.days
    if delta_days < 0:
        return None  # Дата до начальной точки, обработка не требуется
    cycle_position = delta_days % CYCLE_LENGTH
    if cycle_position < BULL_DAYS:
        return 'bull'
    else:
        return 'bear'



def get_current_price_with_retries(client, symbol, max_retries=5, delay=5):
    """Получает текущую цену с повторными попытками через Binance Futures API."""
    for attempt in range(max_retries):
        try:
            ticker = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            return current_price
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при получении текущей цены (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # Экспоненциальная задержка
            else:
                log_event("⚠️ Не удалось получить текущую цену после всех попыток")
                return None
            


def get_available_balance(max_retries=5, delay=5):
    """Получает доступный баланс фьючерсного счёта в USDT через Binance Futures API."""
    for attempt in range(max_retries):
        try:
            balance = client.futures_account_balance()
            usdt_balance = next((item for item in balance if item['asset'] == 'USDT'), None)
            if usdt_balance:
                return float(usdt_balance['balance'])
            else:
                log_event("⚠️ USDT не найден в балансе")
                return 0
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при получении баланса (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить баланс после всех попыток")
                return 0



def get_active_trades_from_exchange(client, symbol='BTCUSDT', max_retries=5, delay=5):
    """Получает активные позиции с Binance Futures с повторными попытками."""
    for attempt in range(max_retries):
        try:
            positions = client.futures_position_information(symbol=symbol)
            active_positions = [pos for pos in positions if float(pos['positionAmt']) != 0]
            if not active_positions:
                log_event("⚪ Нет активных позиций")
                return []
            position = active_positions[0]
            direction = 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'
            size = abs(float(position['positionAmt']))
            liquidation_price = float(position['liquidationPrice'])
            trade_data = {
                'direction': direction,
                'size': size,
                'liquidation_price': liquidation_price,
            }
            return [trade_data]
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при получении активных сделок (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить активные сделки после всех попыток")
                return []


def sync_active_trades():
    """Синхронизирует активные сделки с данными от Binance Futures."""
    global active_trades, next_trade_id, df_trades, CSV_FILE, current_trade_type, previous_rsi, previous_sma_rsi, current_rsi, current_sma_rsi, initial_candles_loaded, next_rsi_update_time

    log_event("🔄 Начало синхронизации активных сделок с биржи")
    exchange_trades = get_active_trades_from_exchange(client)
    active_trades.clear()
    log_event("🗑️ Локальный список active_trades очищен")

    current_time = datetime.now()
    current_market_type = get_market_type(current_time)
    if current_market_type is None:
        log_event("⚠️ Тип рынка не определён при синхронизации")
        return
    log_event(f"📅 Текущий тип рынка: {current_market_type}")

    if exchange_trades:
        trade = exchange_trades[0]
        direction = trade['direction']
        size = trade['size']
        liquidation_price = trade['liquidation_price']

        if current_market_type == 'bull':
            if direction == 'LONG':
                full_direction = 'BULL_LONG'
            elif direction == 'SHORT':
                full_direction = 'BULL_SHORT'
        elif current_market_type == 'bear':
            if direction == 'SHORT':
                full_direction = 'BEAR_SHORT'
            else:
                full_direction = direction
        else:
            full_direction = direction
        log_event(f"📈 Полный тип сделки: {full_direction}")

        trade_id = next_trade_id
        next_trade_id += 1
        log_event(f"📝 Новая сделка ID {trade_id}")

        trade_record = {
            'id': trade_id,
            'direction': full_direction,
            'entry_price': None,
            'entry_time': None,
            'current_price': None,
            'current_pnl': 0,
            'current_pnl_percent': 0,
            'size': size,
            'value': None,
            'leverage': TRADING_CONFIG.get(full_direction, {}).get('LEVERAGE', 1),
            'commission_open': 0,
            'net_pnl': 0,
            'net_pnl_percent': 0,
            'status': 'open',
            'trailing_active': False,
            'max_price': None,
            'liquidation_price': liquidation_price,
        }

        entry_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        active_trades[entry_time_str] = trade_record
        log_event(f"📝 Сделка добавлена в active_trades")

        current_trade_type = full_direction
        log_event(f"📈 Установлен текущий тип сделки: {current_trade_type}")

        if df_trades is None:
            df_trades = pd.DataFrame(columns=[
                'Trade_ID', 'Status', 'Direction', 'Entry_Time', 'Exit_Time', 'Trade_Duration', 'Hours',
                'Entry_Price', 'Exit_Price', 'Position_Size', 'Position_Value',
                'Leverage', 'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'Withdraw'
            ])
            df_trades['Entry_Time'] = pd.Series(dtype='datetime64[ns]')
            df_trades['Exit_Time'] = pd.Series(dtype='datetime64[ns]')
            df_trades['Trade_Duration'] = pd.Series(dtype=str)
            df_trades['Hours'] = pd.Series(dtype=float)
            log_event("📝 Создан новый DataFrame для df_trades")

        new_row = {
            'Trade_ID': str(trade_id),
            'Status': 'open',
            'Direction': full_direction,
            'Entry_Time': pd.NaT,
            'Exit_Time': pd.NaT,
            'Trade_Duration': '',
            'Hours': np.nan,
            'Entry_Price': np.nan,
            'Exit_Price': np.nan,
            'Position_Size': float(size),
            'Position_Value': np.nan,
            'Leverage': float(TRADING_CONFIG.get(full_direction, {}).get('LEVERAGE', 1)),
            'Net_PnL_USDT': np.nan,
            'Net_PnL_Percent': np.nan,
            'Balance': float(get_available_balance()),
            'Withdraw': np.nan
        }
        df_trades = pd.concat([df_trades, pd.DataFrame([new_row])], ignore_index=True)
        log_event(f"📝 Добавлена новая запись в df_trades")

        if CSV_FILE.exists():
            df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
            log_event(f"💾 История сделок сохранена в {CSV_FILE}")

        log_event(f"📈 Синхронизирована сделка: {full_direction}")
    else:
        log_event("⚪ Нет активных сделок для синхронизации")


def manage_liquidation_price():
    """Управляет ценой ликвидации, частично закрывая позицию при необходимости."""
    global client, symbol, MIN_DELTA_LIQUIDATION_LONG, MIN_DELTA_LIQUIDATION_SHORT

    for attempt in range(3):
        try:
            positions = client.futures_position_information(symbol=symbol)
            active_positions = [pos for pos in positions if float(pos['positionAmt']) != 0]
            if not active_positions:
                log_event("⚪ Нет позиций для управления рисками")
                return
            position = active_positions[0]
            size = abs(float(position['positionAmt']))
            direction = 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'
            liquidation_price = float(position['liquidationPrice'])
            current_price = get_current_price_with_retries(client, symbol)

            if direction == 'LONG':
                delta_percent = (current_price - liquidation_price) / current_price * 100
                min_delta = MIN_DELTA_LIQUIDATION_LONG
            else:
                delta_percent = (liquidation_price - current_price) / current_price * 100
                min_delta = MIN_DELTA_LIQUIDATION_SHORT

            if delta_percent < min_delta:
                log_event(f"⚠️ Дельта {delta_percent:.2f}% < {min_delta}%, требуется частичное закрытие {direction}-позиции")
                CLOSE_PERCENT = 5.0
                close_amount = size * (CLOSE_PERCENT / 100)
                MIN_CLOSE_AMOUNT = 0.001
                if close_amount < MIN_CLOSE_AMOUNT:
                    close_amount = MIN_CLOSE_AMOUNT
                close_amount = round(close_amount, 3)
                close_all_trades(reason=f"delta_control_{direction.lower()}", position_value=close_amount)
            else:
                log_event(f"Дельта {delta_percent:.2f}% >= {min_delta}%, коррекция не требуется")

            current_time = datetime.now()
            market_type = get_market_type(current_time)
            if market_type is None:
                log_event("⚠️ Тип рынка не определён")
                return

            if market_type == 'bull':
                trade_type = 'BULL_LONG' if direction == 'LONG' else 'BULL_SHORT'
            elif market_type == 'bear':
                trade_type = 'BEAR_SHORT' if direction == 'SHORT' else None
            if not trade_type:
                log_event(f"⚠️ Неожиданное направление {direction} для рынка {market_type}")
                return

            break
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при управлении рисками (попытка {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                log_event("⚠️ Не удалось получить данные после 3 попыток")




# Константы для определения циклов рынка
START_DATE = datetime(2015, 1, 12)  # Начальная дата
CYCLE_LENGTH = 1428  # Длина цикла в днях (152 недели бычьего + 52 недели медвежьего = 204 недели)
BULL_DAYS = 1064    # Длина бычьего рынка в днях (152 недели * 7 дней)

def get_market_type(date):
    delta = date - START_DATE
    delta_days = delta.days
    if delta_days < 0:
        return None  # Дата до начальной точки, обработка не требуется
    cycle_position = delta_days % CYCLE_LENGTH
    if cycle_position < BULL_DAYS:
        return 'bull'
    else:
        return 'bear'



def fetch_fear_greed_data(filename="fear_greed_index.csv", max_retries=5, delay=5):
    url = "https://api.alternative.me/fng/?limit=0"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()['data']
            with open(filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Date', 'Value', 'Classification'])
                for entry in data:
                    timestamp = int(entry['timestamp'])
                    date = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')
                    value = entry['value']
                    classification = entry.get('value_classification', 'Unknown')
                    writer.writerow([date, value, classification])
            log_event("Данные индекса Страха и Жадности сохранены.")
            return data
        except requests.RequestException as e:
            log_event(f"⚠️ Ошибка при запросе данных (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить данные индекса после всех попыток")
                return []




# Функция загрузки данных индекса страха и жадности
def load_fear_greed_data():
    global fear_greed_data
    fear_greed_file = Path("fear_greed_index.csv")
    if fear_greed_file.exists():
        fear_greed_data = pd.read_csv(fear_greed_file, parse_dates=['Date'], dayfirst=True)
        fear_greed_data['Date'] = pd.to_datetime(fear_greed_data['Date'], format='%d/%m/%Y')
        fear_greed_data = fear_greed_data.sort_values(by='Date')
    else:
        fear_greed_data = pd.DataFrame(columns=['Date', 'Value'])
        log_event("⚠️ Файл fear_greed_index.csv не найден, создан пустой DataFrame")
    return fear_greed_data




def get_fear_greed_value(date, timeframe=GLOBAL_TIMEFRAME):
    global fear_greed_data
    if fear_greed_data is None or fear_greed_data.empty:
        return None

    # Преобразуем таймфрейм в количество дней
    timeframe_days = get_timeframe_days(timeframe)

    if timeframe_days <= 1:
        # Для таймфрейма ≤ 1 дня возвращаем данные за предыдущий день
        target_date = date - timedelta(days=1)
    else:
        # Для таймфрейма > 1 дня определяем первый день последней завершенной свечи
        days_since_start = (date - START_DATE).days
        completed_periods = days_since_start // timeframe_days
        if completed_periods <= 0:
            return None  # Нет завершенной прошлой свечи
        previous_candle = completed_periods - 1
        target_date = START_DATE + timedelta(days=previous_candle * timeframe_days)

    # Приводим дату к началу дня (00:00:00)
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Ищем данные за target_date в fear_greed_data
    filtered = fear_greed_data[fear_greed_data['Date'] == target_date]
    if not filtered.empty:
        return filtered.iloc[0]['Value']
    return None



def get_timeframe_days(timeframe):
    if timeframe.endswith('m'):  # минутный таймфрейм
        minutes = int(timeframe[:-1])
        return minutes / 1440.0  # возвращаем долю дня (в сутках 1440 минут)
    elif timeframe.endswith('d'):  # дневной таймфрейм
        return int(timeframe[:-1])  # извлекаем число дней
    elif timeframe.endswith('w'):  # недельный таймфрейм
        return int(timeframe[:-1]) * 7  # переводим недели в дни
    else:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")



def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.2f} сек"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f} мин"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.2f} ч"
    else:
        days = seconds / 86400
        return f"{days:.2f} дн"



def check_rsi_crossing(current_rsi, current_sma_rsi):
    """Определяет, произошло ли пересечение RSI и SMA RSI."""
    global previous_rsi, previous_sma_rsi
    if previous_rsi is None or previous_sma_rsi is None:
        return None
    if previous_rsi > previous_sma_rsi and current_rsi < current_sma_rsi:
        return "down"  # Пересечение сверху вниз
    elif previous_rsi < previous_sma_rsi and current_rsi > current_sma_rsi:
        return "up"    # Пересечение снизу вверх
    return None
    


def log_to_error_file(message):
    """Записывает сообщение об ошибке в файл websocket_errors.log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    error_message = f"{timestamp} | {message}\n"
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(error_message)
    except Exception as e:
        log_event(f"Не удалось записать в файл ошибок: {e}")


def initialize_csv():
    global df_trades, CSV_FILE
    headers = [
        'Trade_ID', 'Status', 'Direction', 'Entry_Time', 'Exit_Time', 'Trade_Duration', 'Hours',
        'Entry_Price', 'Exit_Price', 'Position_Size', 'Position_Value',
        'Leverage', 'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'Withdraw'
    ]
    
    dtypes = {
        'Trade_ID': str,
        'Status': str,
        'Direction': str,
        'Entry_Time': 'datetime64[ns]',
        'Exit_Time': 'datetime64[ns]',
        'Trade_Duration': str,
        'Hours': float,
        'Entry_Price': float,
        'Exit_Price': float,
        'Position_Size': float,
        'Position_Value': float,
        'Leverage': float,
        'Net_PnL_USDT': float,
        'Net_PnL_Percent': float,
        'Balance': float,
        'Withdraw': float
    }
    
    if TRADING_CONFIG['ENABLE_LOGGING']:
        if CSV_FILE.exists():
            df_trades = pd.read_csv(
                CSV_FILE,
                parse_dates=['Entry_Time', 'Exit_Time'],
                date_format='%Y-%m-%d %H:%M:%S.%f',
                dtype={col: dtypes[col] for col in headers if col not in ['Entry_Time', 'Exit_Time']}
            )
            missing_cols = [col for col in headers if col not in df_trades.columns]
            for col in missing_cols:
                df_trades[col] = pd.Series(dtype=dtypes[col])
            df_trades = df_trades[headers]
            # Безопасное приведение Position_Size к числу, если это строка
            df_trades['Position_Size'] = pd.to_numeric(df_trades['Position_Size'], errors='coerce')
            log_event("📝 CSV файл загружен в DataFrame")
        else:
            df_trades = pd.DataFrame({col: pd.Series(dtype=dtypes[col]) for col in headers})
            df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
            log_event("📝 Создан новый файл CSV с заголовками")
    else:
        df_trades = None
        CSV_FILE = None
        log_event("📝 Запись сделок отключена")



# Функция для преобразования таймфрейма в строковый формат Bybit
def get_bybit_interval(timeframe):
    """Преобразует таймфрейм в формат interval для Bybit."""
    mapping = {
        '1m': '1',
        '5m': '5',
        '15m': '15',
        '30m': '30',
        '1h': '60',
        '2h': '120',
        '4h': '240',
        '6h': '360',
        '12h': '720',
        '1d': 'D',
        '1w': 'W',
        '1M': 'M'  # Месяц
    }
    if timeframe not in mapping:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")
    return mapping[timeframe]



# Функция для преобразования таймфрейма в timedelta
def parse_timeframe(timeframe):
    """Преобразует строковый таймфрейм в объект timedelta."""
    if timeframe.endswith('m'):
        return timedelta(minutes=int(timeframe[:-1]))
    elif timeframe.endswith('h'):
        return timedelta(hours=int(timeframe[:-1]))
    elif timeframe.endswith('d'):
        return timedelta(days=1)
    elif timeframe.endswith('w'):
        return timedelta(weeks=1)
    elif timeframe.endswith('M'):
        return timedelta(days=30)  # Приблизительно для месяца
    else:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")


def get_candles(symbol, timeframe, limit, retries=5, delay=5):
    """Получает свечные данные с Binance Futures с повторными попытками."""
    for attempt in range(retries):
        try:
            klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit)
            if len(klines) >= limit:
                formatted_candles = [
                    [int(kline[0]), float(kline[1]), float(kline[2]), float(kline[3]), float(kline[4]), float(kline[5])]
                    for kline in klines
                ]
                return formatted_candles
            else:
                log_event(f"⚠️ Загружено {len(klines)} свечей, требуется {limit}. Повторная попытка...")
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при получении свечей (попытка {attempt + 1}/{retries}): {e}")
        time.sleep(delay)
    log_event(f"⚠️ Не удалось получить достаточное количество свечей после {retries} попыток")
    return []


def get_completed_candles_close(symbol, timeframe, current_time, retries=5, delay=5):
    """Получает цены закрытия завершённых свечей с Binance Futures."""
    tf_delta = parse_timeframe(timeframe)
    end_time = int(current_time.timestamp() * 1000)
    limit = 1000
    for attempt in range(retries):
        try:
            klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit, endTime=end_time)
            closes = []
            for kline in klines:
                candle_start = datetime.fromtimestamp(int(kline[0]) / 1000)
                candle_end = candle_start + tf_delta
                if current_time >= candle_end:
                    closes.append(float(kline[4]))
                else:
                    break
            return closes
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при получении свечей (попытка {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить свечи после всех попыток")
                return []



# Время окончания текущей свечи
def get_current_candle_end_time(current_time, timeframe):
    """Нужна для расчетов on_orderbook_message. Вычисляет время окончания текущей свечи для заданного таймфрейма."""
    tf_delta = parse_timeframe(timeframe)
    if timeframe.endswith('m') or timeframe.endswith('h'):
        start_time = current_time - (current_time - datetime(1970, 1, 1)) % tf_delta
        end_time = start_time + tf_delta
    elif timeframe.endswith('d'):
        end_time = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif timeframe.endswith('w'):
        weekday = current_time.weekday()
        days_to_sunday = (6 - weekday) % 7
        end_time = (current_time + timedelta(days=days_to_sunday)).replace(hour=23, minute=59, second=59, microsecond=999999)
    return end_time




# Время окончания следующей свечи
def get_next_candle_end_time(current_time, timeframe):
    """Определяет время окончания следующей свечи для заданного таймфрейма."""
    tf_delta = parse_timeframe(timeframe)
    if timeframe.endswith('m') or timeframe.endswith('h'):
        start_time = current_time - (current_time - datetime(1970,1,1)) % tf_delta
        next_end = start_time + tf_delta
    elif timeframe.endswith('d'):
        next_end = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        if current_time >= next_end:
            next_end += tf_delta
    elif timeframe.endswith('w'):
        weekday = current_time.weekday()
        days_to_sunday = (6 - weekday) % 7
        next_sunday = current_time + timedelta(days=days_to_sunday)
        next_end = next_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
        if current_time >= next_end:
            next_end += tf_delta
    return next_end




def log_market_data(mid_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_candles, get_fear_greed_value, get_available_balance):
    price_change = mid_price - previous_mid_price
    price_indicator = last_price_indicator
    if previous_mid_price != 0:
        if price_change >= 0.1:
            price_indicator = " 🟢"
            last_price_indicator = price_indicator
        elif price_change <= -0.1:
            price_indicator = " 🔴"
            last_price_indicator = price_indicator
    
    log_event("----------------------------------------------|")
    log_event("-----------------| Юнона 3 |------------------|")
    log_event("-----------------| BINANCE |------------------|")
    log_event("---------- Кросс-маржа [BTC/USDT] ------------|")
    log_event("----------------------------------------------|")
    log_event(f"Период RSI = {RSI_PERIOD}, SMA RSI = {SMA_RSI_PERIOD}")
    log_event(f"Таймфрейм: {GLOBAL_TIMEFRAME}, Данные: {ANALYSIS_TIMEFRAME}")
    log_event("----------------------------------------------|")
    log_event(f"Рыночная цена: {mid_price:.1f}{price_indicator}                     ")
    
    candles = get_candles(symbol, GLOBAL_TIMEFRAME, 2)
    if len(candles) >= 2:
        last_closed_candle = candles[-2]
        last_open = last_closed_candle[1]
        last_close = last_closed_candle[4]
        log_event(f"Открытие: {last_open:.2f}, Закрытие: {last_close:.2f}")
    
    if current_rsi is not None and current_sma_rsi is not None:
        sma_rsi_delta = current_rsi - current_sma_rsi
        log_event(f"RSI: {current_rsi:.2f} | SMA RSI: {current_sma_rsi:.2f} | {sma_rsi_delta:.2f}")
    else:
        log_event("RSI и SMA RSI: недостаточно данных")
    
    fear_greed_value = get_fear_greed_value(current_time)
    if fear_greed_value is not None:
        log_event(f"Индекс страха и жадности: {fear_greed_value}")
    else:
        log_event("Индекс страха и жадности: данные недоступны")
    
    available_balance = get_available_balance()
    log_event(f"Доступный баланс: {available_balance:.2f} USDT")
    log_event("----------------------------------------------|")







def check_signals(current_price):
    global current_trade_type, previous_rsi, previous_sma_rsi, last_market_type, current_rsi, current_sma_rsi

    with trades_lock:
        current_time = datetime.now()
        current_market_type = get_market_type(current_time)
        if current_market_type is None:
            log_event("⚠️ Тип рынка не определен для текущей даты")
            return

        # Проверка смены типа рынка
        if 'last_market_type' not in globals():
            globals()['last_market_type'] = current_market_type
        elif last_market_type != current_market_type:
            log_event(f"🔄 Смена типа рынка с {last_market_type} на {current_market_type}. Закрытие всех сделок.")
            close_all_trades(f"market_type_change_to_{current_market_type}", force_close=True)
            globals()['last_market_type'] = current_market_type

        # Получаем значение индекса страха и жадности
        fear_greed_value = get_fear_greed_value(current_time)
        if fear_greed_value is None:
            log_event("⚠️ Нет данных индекса страха для текущей даты. Работаем только по RSI.")

        rsi = current_rsi
        sma_rsi = current_sma_rsi

        if rsi is None or sma_rsi is None:
            log_event("⚠️ Недостаточно данных для вычисления RSI и SMA RSI")
            return

        # Проверяем пересечение RSI и SMA RSI
        crossing = check_rsi_crossing(rsi, sma_rsi)

        # Логика для бычьего рынка
        if current_market_type == 'bull':
            if not active_trades:
                if (fear_greed_value is not None and fear_greed_value <= 26) or crossing == "up":
                    log_event(f"📈 Открытие новой лонг импульсной сделки (BULL_LONG)")
                    position_value = (get_available_balance() * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
                    open_trade('BULL_LONG', current_price, position_value)
                    current_trade_type = 'BULL_LONG'
                elif crossing == "down":
                    log_event(f"📉 Открытие новой шорт импульсной сделки (BULL_SHORT)")
                    position_value = (get_available_balance() * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
                    open_trade('BULL_SHORT', current_price, position_value)
                    current_trade_type = 'BULL_SHORT'
            else:
                if current_trade_type == 'BULL_LONG':
                    if crossing == "down":
                        log_event(f"🔄 Закрытие лонг импульсной сделки (BULL_LONG): Пересечение RSI и SMA RSI вниз")
                        close_all_trades("rsi_down", force_close=True)

                elif current_trade_type == 'BULL_SHORT':
                    if (fear_greed_value is not None and fear_greed_value <= 26) or crossing == "up":
                        log_event(f"🔄 Закрытие шорт импульсной сделки (BULL_SHORT): Условие для открытия лонга")
                        close_all_trades("long_open_condition", force_close=True)


        # Логика для медвежьего рынка
        elif current_market_type == 'bear':
            if not active_trades:
                if (fear_greed_value is not None and fear_greed_value >= 52) or crossing == "down":
                    log_event(f"📉 Открытие новой шорт импульсной сделки (BEAR_SHORT)")
                    position_value = (get_available_balance() * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
                    open_trade('BEAR_SHORT', current_price, position_value)
                    current_trade_type = 'BEAR_SHORT'
            else:
                if current_trade_type == 'BEAR_SHORT':
                    if crossing == "up":
                        log_event(f"🔄 Закрытие шорт импульсной сделки (BEAR_SHORT): Пересечение RSI и SMA RSI вверх")
                        close_all_trades("rsi_up", force_close=True)
                        current_trade_type = None

    manage_liquidation_price()

    # Отображение всех активных сделок
    log_event("----------------------------------------------|")
    log_event("-------------- Проверка сигнала --------------|")
    log_event("----------------------------------------------|")




def open_trade(trade_type, entry_price, position_value=None, trailing_status=None):
    """Открывает новую сделку на Binance Futures с изолированной маржой."""
    global next_trade_id, active_trades, df_trades, trades_lock, MAX_ACTIVE_TRADES, TRADING_CONFIG, CSV_FILE, current_trade_type, client, symbol

    start_time = time.time()
    max_retries = 5
    delay = 5

    with trades_lock:
        log_event(f"Пауза 5 секунд перед открытием новой сделки")
        time.sleep(5)
        if len(active_trades) >= MAX_ACTIVE_TRADES:
            log_event("⚠️ Достигнут лимит активных сделок")
            return

        available_balance = get_available_balance()
        log_event(f" Доступный баланс: {available_balance}")

        if position_value is None:
            if trade_type in ["BULL_LONG", "BULL_SHORT", "BEAR_SHORT"]:
                position_value = (available_balance * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
            else:
                log_event(f"⚠️ Неизвестный тип сделки: {trade_type}")
                return

        symbol_info = client.futures_exchange_info()
        for s in symbol_info['symbols']:
            if s['symbol'] == symbol:
                precision = s['quantityPrecision']
                break
        else:
            log_event(f"⚠️ Символ {symbol} не найден")
            return

        leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE', 1)
        log_event(f"Плечо для {trade_type}: {leverage}x")

        # Установка плеча и типа маржи удалена, так как они задаются вручную на бирже

        current_price = get_current_price_with_retries(client, symbol)
        amount_btc = (position_value * leverage) / current_price
        amount_btc = round(amount_btc, precision)

        side = 'BUY' if 'LONG' in trade_type else 'SELL'

        try:
            order = client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=amount_btc
            )
            log_event(f"✅ Ордер успешно размещен: {order}")
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка размещения ордера: {e}")
            return

        current_trade_id = next_trade_id
        next_trade_id += 1
        entry_time = datetime.now()
        entry_time_str = entry_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        commission_open = position_value * (TRADING_CONFIG['COMMISSION_RATE'] / 100)

        new_trade = {
            'id': current_trade_id,
            'direction': trade_type,
            'entry_price': current_price,
            'entry_time': entry_time,
            'entry_time_str': entry_time_str,
            'current_price': current_price,
            'size': amount_btc,
            'value': position_value,
            'leverage': leverage,
            'commission_open': commission_open,
            'status': 'open',
            'trailing_active': False if trailing_status is None else trailing_status,
            'max_price': current_price,
        }
        active_trades[entry_time_str] = new_trade
        current_trade_type = trade_type

        if TRADING_CONFIG['ENABLE_LOGGING'] and CSV_FILE is not None:
            current_balance = get_available_balance()
            new_row = {
                'Trade_ID': str(current_trade_id),
                'Status': 'open',
                'Direction': trade_type,
                'Entry_Time': entry_time,
                'Exit_Time': pd.NaT,
                'Trade_Duration': '',
                'Hours': np.nan,
                'Entry_Price': float(current_price),
                'Exit_Price': np.nan,
                'Position_Size': float(amount_btc),
                'Position_Value': float(position_value),
                'Leverage': float(leverage),
                'Net_PnL_USDT': np.nan,
                'Net_PnL_Percent': np.nan,
                'Balance': float(current_balance),
                'Withdraw': np.nan
            }
            if df_trades is None or df_trades.empty or df_trades.isna().all().all():
                df_trades = pd.DataFrame([new_row])
            else:
                df_trades = pd.concat([df_trades, pd.DataFrame([new_row])], ignore_index=True)
            try:
                df_trades['Position_Size'] = df_trades['Position_Size'].map('{:.3f}'.format, na_action='ignore')
                if not CSV_FILE.exists():
                    df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
                else:
                    with open(CSV_FILE, 'a', newline='') as f:
                        formatted_row = new_row.copy()
                        formatted_row['Position_Size'] = '{:.3f}'.format(new_row['Position_Size'])
                        pd.DataFrame([formatted_row]).to_csv(f, header=False, index=False, float_format='%.2f')
            except Exception as e:
                log_event(f"Ошибка при записи в CSV: {e}")




def get_symbol_info(symbol):
    try:
        symbol_info = client.get_instruments_info(category="linear", symbol=symbol)
        if symbol_info['retCode'] != 0:
            raise ValueError(f"Ошибка API: {symbol_info['retMsg']}")
        instrument = symbol_info['result']['list'][0]
        min_order_qty = float(instrument['lotSizeFilter']['minOrderQty'])
        qty_step = float(instrument['lotSizeFilter']['qtyStep'])
        precision = int(round(-math.log(qty_step, 10), 0))
        return {
            'min_order_qty': min_order_qty,
            'qty_step': qty_step,
            'precision': precision
        }
    except Exception as e:
        log_event(f"Ошибка при получении информации о символе: {e}")
        return None
    



def close_all_trades(reason, exit_time=None, force_close=False, position_value=None):
    """Закрывает все активные сделки или их часть на Binance Futures."""
    global df_trades, active_trades, trades_lock, TRADING_CONFIG, CSV_FILE, bull_long_trades_count, bull_short_trades_count, current_trade_type, client, symbol, current_market_type

    start_time = time.time()
    trades_to_close = []
    max_retries = 5
    delay = 5

    with trades_lock:
        if not active_trades:
            log_event("⚪ Нет активных сделок для закрытия")
            return

        if exit_time is None:
            exit_time = datetime.now()
        exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        current_price = get_current_price_with_retries(client, symbol)

        positions = client.futures_position_information(symbol=symbol)
        active_positions = [pos for pos in positions if float(pos['positionAmt']) != 0]
        if not active_positions:
            log_event("⚪ Нет активных позиций для закрытия")
            return
        position = active_positions[0]
        size = abs(float(position['positionAmt']))
        direction = 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'

        symbol_info = client.futures_exchange_info()
        for s in symbol_info['symbols']:
            if s['symbol'] == symbol:
                precision = s['quantityPrecision']
                break
        else:
            log_event(f"⚠️ Символ {symbol} не найден")
            return

        if position_value is not None:
            amount_to_close = min(position_value, size)
            amount_to_close = round(amount_to_close, precision)
            log_event(f"Частичное закрытие {direction}: объем {amount_to_close:.8f} BTC")
        else:
            amount_to_close = size
            log_event(f"Полное закрытие {direction}: объем {amount_to_close:.8f} BTC")

        close_side = 'SELL' if direction == 'LONG' else 'BUY'

        try:
            order = client.futures_create_order(
                symbol=symbol,
                side=close_side,
                type='MARKET',
                quantity=amount_to_close
            )
            log_event(f"✅ Ордер на закрытие успешно размещен: {order}")
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка закрытия позиции: {e}")
            return

        for entry_time_str in list(active_trades.keys()):
            trade = active_trades[entry_time_str]
            if trade['direction'].endswith(direction):
                entry_time = trade.get('entry_time')
                duration_str = None
                duration_hours = None
                if entry_time is not None:
                    duration_seconds = (exit_time - entry_time).total_seconds()
                    duration_str = format_duration(duration_seconds)
                    duration_hours = duration_seconds / 3600
                else:
                    log_event("⚠️ Время входа отсутствует, длительность не рассчитывается")

                entry_price = trade.get('entry_price')
                leverage = trade.get('leverage', 1)

                if trade.get('value') is not None:
                    commission_open = trade.get('commission_open', 0)
                    commission_close = (amount_to_close / trade['size']) * trade['value'] * (TRADING_CONFIG['COMMISSION_RATE'] / 100) if trade['size'] > 0 else 0
                    total_commission = commission_open + commission_close

                    net_pnl = 0
                    net_pnl_percent = 0
                    if entry_price is not None and current_price is not None and current_price > 0:
                        if 'SHORT' in direction:
                            pnl = (entry_price - current_price) * amount_to_close * leverage
                        elif 'LONG' in direction:
                            pnl = (current_price - entry_price) * amount_to_close * leverage
                        net_pnl = pnl - total_commission
                        net_pnl_percent = (net_pnl / trade['value']) * 100 if trade['value'] > 0 else 0
                else:
                    log_event("⚠️ Значение 'value' отсутствует, комиссия и PNL не рассчитываются")
                    commission_open = 0
                    commission_close = 0
                    total_commission = 0
                    net_pnl = 0
                    net_pnl_percent = 0

                remaining_size = 0
                if position_value is not None and amount_to_close < size:
                    trade['size'] -= amount_to_close
                    remaining_size = trade['size']
                    if trade['size'] <= 0:
                        del active_trades[entry_time_str]
                        log_event(f"Позиция {direction} полностью закрыта после частичного закрытия")
                    else:
                        log_event(f"Оставшийся размер позиции: {trade['size']:.8f} BTC")
                        if trade.get('value') is not None:
                            trade['value'] *= (trade['size'] / (trade['size'] + amount_to_close))
                            trade['commission_open'] -= commission_open * (amount_to_close / (trade['size'] + amount_to_close))
                        min_delta = MIN_DELTA_LIQUIDATION_LONG if direction == 'LONG' else MIN_DELTA_LIQUIDATION_SHORT
                        log_event(f"Пауза 5 секунд для пересчета цены ликвидации")
                        time.sleep(5)
                        manage_liquidation_price()
                else:
                    del active_trades[entry_time_str]
                    log_event(f"Позиция {direction} полностью закрыта")

                trades_to_close.append({
                    'entry_time': entry_time,
                    'trade_id': trade['id'],
                    'exit_time': exit_time,
                    'duration': duration_str,
                    'duration_hours': duration_hours,
                    'exit_price': current_price,
                    'entry_price': entry_price,
                    'position_size': amount_to_close,
                    'position_value': trade.get('value', 0),
                    'leverage': leverage,
                    'net_pnl': net_pnl,
                    'net_pnl_percent': net_pnl_percent,
                    'direction': trade['direction'],
                    'withdraw_amount': 0
                })

        if position_value is None:
            current_trade_type = None
            bull_long_trades_count = 0
            bull_short_trades_count = 0
            log_event("🔄 Все сделки закрыты. Счетчики активных сделок сброшены.")

            current_market_type = get_market_type(datetime.now())
            if current_market_type == 'bull' and current_price is not None and trades_to_close:
                last_trade_direction = trades_to_close[-1]['direction']
                position_value = (get_available_balance() * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
                if last_trade_direction == 'BULL_LONG':
                    log_event(f"📉 Открытие шорт-сделки (BULL_SHORT), цена: {current_price:.2f}")
                    open_trade('BULL_SHORT', current_price, position_value)
                    current_trade_type = 'BULL_SHORT'
                elif last_trade_direction == 'BULL_SHORT':
                    log_event(f"📈 Открытие лонг-сделки (BULL_LONG), цена: {current_price:.2f}")
                    open_trade('BULL_LONG', current_price, position_value)
                    current_trade_type = 'BULL_LONG'

    if TRADING_CONFIG['ENABLE_LOGGING'] and CSV_FILE is not None:
        if df_trades is None:
            df_trades = pd.DataFrame(columns=[
                'Trade_ID', 'Status', 'Direction', 'Entry_Time', 'Exit_Time', 'Trade_Duration', 'Hours',
                'Entry_Price', 'Exit_Price', 'Position_Size', 'Position_Value',
                'Leverage', 'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'Withdraw'
            ])
            df_trades['Entry_Time'] = pd.Series(dtype='datetime64[ns]')
            df_trades['Exit_Time'] = pd.Series(dtype='datetime64[ns]')
            df_trades['Trade_Duration'] = pd.Series(dtype=str)
            df_trades['Hours'] = pd.Series(dtype=float)

        for trade_data in trades_to_close:
            mask = (df_trades['Trade_ID'] == str(trade_data['trade_id'])) & (df_trades['Status'] == 'open')
            if mask.any():
                df_trades.loc[mask, 'Status'] = reason
                df_trades.loc[mask, 'Exit_Time'] = trade_data['exit_time']
                df_trades.loc[mask, 'Trade_Duration'] = trade_data['duration'] if trade_data['duration'] is not None else ''
                df_trades.loc[mask, 'Hours'] = trade_data['duration_hours'] if trade_data['duration_hours'] is not None else np.nan
                df_trades.loc[mask, 'Exit_Price'] = trade_data['exit_price']
                df_trades.loc[mask, 'Net_PnL_USDT'] = trade_data['net_pnl']
                df_trades.loc[mask, 'Net_PnL_Percent'] = trade_data['net_pnl_percent']
                df_trades.loc[mask, 'Withdraw'] = trade_data['withdraw_amount'] if trade_data['withdraw_amount'] > 0 else np.nan
                df_trades.loc[mask, 'Balance'] = get_available_balance()
                if position_value is not None and amount_to_close < size and remaining_size > 0:
                    open_row = df_trades.loc[mask].copy()
                    open_row['Status'] = 'open'
                    open_row['Position_Size'] = remaining_size
                    open_row['Exit_Time'] = pd.NaT
                    open_row['Trade_Duration'] = ''
                    open_row['Hours'] = np.nan
                    open_row['Exit_Price'] = np.nan
                    open_row['Net_PnL_USDT'] = np.nan
                    open_row['Net_PnL_Percent'] = np.nan
                    open_row['Withdraw'] = np.nan
                    df_trades = pd.concat([df_trades, open_row], ignore_index=True)
            else:
                new_row = {
                    'Trade_ID': str(trade_data['trade_id']),
                    'Status': reason,
                    'Direction': trade_data['direction'],
                    'Entry_Time': trade_data['entry_time'] if trade_data['entry_time'] is not None else pd.NaT,
                    'Exit_Time': trade_data['exit_time'],
                    'Trade_Duration': trade_data['duration'] if trade_data['duration'] is not None else '',
                    'Hours': trade_data['duration_hours'] if trade_data['duration_hours'] is not None else np.nan,
                    'Entry_Price': trade_data['entry_price'] if trade_data['entry_price'] is not None else np.nan,
                    'Exit_Price': trade_data['exit_price'],
                    'Position_Size': trade_data['position_size'],
                    'Position_Value': trade_data['position_value'],
                    'Leverage': trade_data['leverage'],
                    'Net_PnL_USDT': trade_data['net_pnl'],
                    'Net_PnL_Percent': trade_data['net_pnl_percent'],
                    'Withdraw': trade_data['withdraw_amount'] if trade_data['withdraw_amount'] > 0 else np.nan,
                    'Balance': get_available_balance()
                }
                if df_trades.empty or df_trades.isna().all().all():
                    df_trades = pd.DataFrame([new_row])
                else:
                    df_trades = pd.concat([df_trades, pd.DataFrame([new_row])], ignore_index=True)
        try:
            df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
            log_event(f"💾 История сделок обновлена в {CSV_FILE}")
        except Exception as e:
            log_event(f"⚠️ Ошибка при записи в CSV: {e}")


def display_position():
    """Отображает информацию о текущей позиции на Binance Futures."""
    with trades_lock:
        if not active_trades:
            log_event("⚪ Нет активных позиций")
            return

        try:
            position_response = client.futures_position_information(symbol=symbol)
            active_positions = [pos for pos in position_response if float(pos['positionAmt']) != 0]
            if not active_positions:
                log_event("⚪ Нет активных позиций")
                return
            position = active_positions[0]
            size = abs(float(position['positionAmt']))
            direction = 'LONG' if float(position['positionAmt']) > 0 else 'SHORT'
            entry_price = float(position['entryPrice'])
            liquidation_price = float(position['liquidationPrice'])
            
            # Определение типа сделки на основе направления и типа рынка
            current_time = datetime.now()
            market_type = get_market_type(current_time)
            if market_type == 'bull':
                trade_type = 'BULL_LONG' if direction == 'LONG' else 'BULL_SHORT'
            elif market_type == 'bear':
                trade_type = 'BEAR_SHORT' if direction == 'SHORT' else None
            else:
                trade_type = None
            
            # Получение плеча из TRADING_CONFIG
            leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE') if trade_type else None
            if leverage is None:
                log_event("⚠️ Не удалось определить плечо для текущей позиции")
                leverage = 'Неизвестно'

            current_price = get_current_price_with_retries(client, symbol)

            delta_percent = None
            if current_price > 0 and liquidation_price > 0:
                if direction == 'LONG':
                    delta_percent = (current_price - liquidation_price) / current_price * 100
                else:
                    delta_percent = (liquidation_price - current_price) / current_price * 100

            log_event("----------------------------------------------|")
            log_event("------------------ ПОЗИЦИЯ -------------------|")
            log_event("----------------------------------------------|")
            log_event(f"{'🟢' if direction == 'LONG' else '🔴'} {direction} | Плечо: {leverage}x")
            log_event(f"💰 Размер позиции: {size:.8f} BTC")
            log_event(f"💸 Цена входа: {entry_price:.2f} USDT")
            log_event(f"💥 Ликвидация: {'--' if liquidation_price <= 0 else f'{liquidation_price:.2f}'} USDT | Дельта: {'--' if delta_percent is None else f'{delta_percent:.2f}%'}")
            log_event("----------------------------------------------|")
        except BinanceAPIException as e:
            log_event(f"⚠️ Ошибка при получении данных о позиции: {e}")
        except Exception as e:
            log_event(f"⚠️ Неожиданная ошибка в display_position: {e}")



def run():
    global next_trade_id, RSI_PERIOD, SMA_RSI_PERIOD, fear_greed_data, next_rsi_update_time, current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi, next_analysis_time, previous_mid_price, last_price_indicator
    
    # Настройка логирования
    setup_logging()

    # Загрузка и сохранение данных индекса страха и жадности
    fear_greed_data = fetch_fear_greed_data()
    if not fear_greed_data:
        log_event("Не удалось получить данные индекса страха и жадности")
    
    # Загрузка данных индекса страха и жадности
    fear_greed_data = load_fear_greed_data()
    
    # Проверка и инициализация счетчика ID сделок из CSV
    if CSV_FILE is not None and CSV_FILE.exists():
        try:
            df = pd.read_csv(CSV_FILE)
            if not df.empty and 'Trade_ID' in df.columns:
                df['Trade_ID'] = pd.to_numeric(df['Trade_ID'], errors='coerce')
                max_id = df['Trade_ID'].max()
                if pd.isna(max_id):
                    next_trade_id = 1
                else:
                    next_trade_id = int(max_id) + 1
                log_event(f"📝 Инициализация счетчика ID сделок: {next_trade_id}")
        except Exception as e:
            log_event(f"⚠️ Ошибка при инициализации счетчика ID: {e}")
    else:
        next_trade_id = 1



    # Инициализация CSV
    initialize_csv()
    # Синхронизация активных сделок при запуске в реальном режиме
    sync_active_trades()


###################################################################################################
    # Тестировние входа и выхода из сделок
    
    # Получаем текущую цену
    current_price = get_current_price_with_retries(client, symbol)
    log_event(f"📈 Текущая цена: {current_price:.2f}")

    #Задаём размер позиции
    position_value = (get_available_balance() * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
    
    # open_trade('BULL_LONG', current_price, position_value)
    # log_event(f"Пауза 10 секунд перед закрытием")
    # time.sleep(10)
    # close_all_trades("rsi_down", force_close=True)


    # open_trade('BULL_SHORT', current_price, position_value)
    # log_event(f"Пауза 10 секунд перед закрытием")
    # time.sleep(10)
    # close_all_trades("long_open_condition", force_close=True)


    # open_trade('BULL_LONG', current_price, position_value)
    # log_event(f"Пауза 10 секунд перед закрытием")
    # time.sleep(10)
    # close_all_trades("rsi_down", force_close=True)



    # close_amount = 0.001
    # log_event(f"Рассчитан объем для закрытия: {close_amount:.8f} BTC")
    # close_all_trades(reason="delta_control_long", position_value=close_amount)



    # Открываем сделку 'BEAR_SHORT' для медвежьего рынка
    # open_trade('BEAR_SHORT', current_price, position_value)
    # log_event("Пауза 10 секунд перед закрытием")
    # time.sleep(10)
    # close_all_trades("rsi_up", force_close=True)

###################################################################################################

    # Инициализация времени следующего обновления данных о сделках
    current_time = datetime.now()
    next_analysis_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)
    next_rsi_update_time = get_next_candle_end_time(current_time, GLOBAL_TIMEFRAME)

    # Первоначальный расчет RSI и SMA RSI
    closes = get_completed_candles_close(symbol, GLOBAL_TIMEFRAME, current_time)
    if len(closes) >= RSI_PERIOD:
        rsi = talib.RSI(np.array(closes), timeperiod=RSI_PERIOD)
        if len(rsi) >= SMA_RSI_PERIOD:
            sma_rsi = talib.SMA(rsi, timeperiod=SMA_RSI_PERIOD)
            if len(rsi) >= 2:
                previous_rsi = rsi[-2]
                current_rsi = rsi[-1]
                previous_sma_rsi = sma_rsi[-2]
                current_sma_rsi = sma_rsi[-1]

    # Логирование рыночных данных
    fear_greed_data = fetch_fear_greed_data()
    if not fear_greed_data:
        log_event("Не удалось получить данные индекса страха и жадности")
    fear_greed_data = load_fear_greed_data()
    log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_candles, get_fear_greed_value, get_available_balance)
    display_position()
    manage_liquidation_price()
    next_analysis_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)

    # Добавление обратного отсчёта после отображения сделок
    log_event("----------------------------------------------|")
    log_event(f"⏳ ({ANALYSIS_TIMEFRAME}) Обновление данных: {next_analysis_time}")


    while True:
        try:
            current_time = datetime.now()

            # Обновление по ANALYSIS_TIMEFRAME   
            if next_analysis_time is None or current_time >= next_analysis_time:
                current_price = get_current_price_with_retries(client, symbol)
                # Логирование рыночных данных
                fear_greed_data = fetch_fear_greed_data()
                if not fear_greed_data:
                    log_event("Не удалось получить данные индекса страха и жадности")
                fear_greed_data = load_fear_greed_data()
                log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_candles, get_fear_greed_value, get_available_balance)
                display_position()
                manage_liquidation_price()

                next_analysis_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)

                # Добавление обратного отсчёта после отображения сделок
                log_event("----------------------------------------------|")
                log_event(f"⏳ ({ANALYSIS_TIMEFRAME}) Обновление данных: {next_analysis_time}")


            # Обновление RSI и SMA RSI при завершении свечи GLOBAL_TIMEFRAME
            if next_rsi_update_time is None or current_time >= next_rsi_update_time:
                closes = get_completed_candles_close(symbol, GLOBAL_TIMEFRAME, current_time)
                if len(closes) >= RSI_PERIOD:
                    rsi_values = talib.RSI(np.array(closes), timeperiod=RSI_PERIOD)
                    if len(rsi_values) >= SMA_RSI_PERIOD:
                        sma_rsi_values = talib.SMA(rsi_values, timeperiod=SMA_RSI_PERIOD)
                        previous_rsi = current_rsi
                        current_rsi = rsi_values[-1]
                        previous_sma_rsi = current_sma_rsi
                        current_sma_rsi = sma_rsi_values[-1]
                    else:
                        previous_rsi = current_rsi
                        current_rsi = rsi_values[-1]
                        current_sma_rsi = None
                        log_event("⚠️ Недостаточно значений RSI для расчёта SMA RSI")
                else:
                    current_rsi = None
                    current_sma_rsi = None
                    log_event("⚠️ Недостаточно свечей для расчёта RSI")
                
                
                # Вызов check_signals и логирование сразу после обновления RSI
                if current_rsi is not None and current_sma_rsi is not None:

                    check_signals(current_price)
                    log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_candles, get_fear_greed_value, get_available_balance)
                    display_position()
                    manage_liquidation_price()

                    next_rsi_update_time = get_next_candle_end_time(current_time, GLOBAL_TIMEFRAME)

                log_event("----------------------------------------------|")
                log_event(f"⏳ ({GLOBAL_TIMEFRAME}) Обновление свечи: {next_rsi_update_time}")

            # Вычисление времени до следующего обновления данных
            time_to_next_analysis = (next_analysis_time - current_time).total_seconds()
            
            # Спящий режим до ближайшего обновления данных
            time.sleep(max(time_to_next_analysis, 1))

        except Exception as e:
            log_event(f"⚠️ Ошибка в основном цикле: {e}")
            time.sleep(5)  # Пауза перед повторной попыткой


if __name__ == "__main__":
    try:
        initialize_csv()
        run()
    except Exception as e:
        error_msg = f"Ошибка выполнения скрипта: {e}"
        log_event(error_msg)
        with open("error_log.txt", "a", encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {error_msg}\n")
        raise  



# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 
# Используй только официальную библиотеку python-binance 1.0.29
