


# j3_458_BB

from dotenv import load_dotenv
import os
import time
import threading
from datetime import datetime, timedelta, timezone
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
import gc




symbol = 'BTCUSDT'
MAX_ACTIVE_TRADES = 1
previous_rsi = None
previous_sma_rsi = None
current_trade_type = None
next_analysis_time = None # Время следующего обновления данных о сделках
active_trades = {} # Словарь для хранения всех активных сделок по их ID
next_trade_id = 1 # Счетчик для генерации уникальных ID сделок
trades_lock = threading.RLock() # Блокировка для безопасного обновления списка сделок
last_price_indicator = ""
fear_greed_data = None
next_rsi_update_time = None
current_rsi = None
current_sma_rsi = None
previous_mid_price = 0
bull_long_trades_count = 0
previous_stoch_k = None
previous_stoch_d = None
current_stoch_k = None
current_stoch_d = None
previous_williams_r_overbought = None
current_williams_r_overbought = None
previous_williams_r_oversold = None
current_williams_r_oversold = None
next_global_update_time = None
df_trades = None # Глобальная переменная для хранения DataFrame с историей сделок
market_periods = []
current_market_type = None
next_market_change = None

# Определение имени скрипта для динамических путей
script_name = os.path.basename(__file__).split('.')[0]

# Путь к CSV-файлу
CSV_FILE = Path(f"trades_bybit_{script_name}.csv")

# Путь к файлу ошибок WebSocket
ERROR_LOG_FILE = Path(f"errors_{script_name}.log")


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



def setup_logging():
    """
    Настраивает логирование с выводом временных меток в UTC.
    Логи записываются в файл logs.txt и выводятся в консоль.
    """
    class UTCFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            utc_time = datetime.fromtimestamp(record.created, tz=timezone.utc)
            if datefmt:
                return utc_time.strftime(datefmt)
            return utc_time.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Удаляем все существующие обработчики, чтобы избежать дублирования
    if logger.handlers:
        logger.handlers.clear()
    # Создаем файловый обработчик с динамическим именем
    file_handler = logging.FileHandler(f'logs_{script_name}.txt', encoding='utf-8')
    file_handler.setFormatter(UTCFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    # Создаем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(UTCFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    # Вызываем функцию очистки логов при запуске
    cleanup_logs()




def cleanup_logs():
    try:
        with open(f'logs_{script_name}.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if not lines:
            return
        now = get_server_time()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        cutoff_date = now - timedelta(days=14)
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if cutoff_date.tzinfo is None:
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
        filtered_lines = []
        current_date = None
        for line in lines:
            try:
                timestamp_str = line.split(' - ')[0]
                log_date = pd.to_datetime(timestamp_str, format='%Y-%m-%d %H:%M:%S,%f', utc=True)
                if log_date.tzinfo is None:
                    log_date = log_date.replace(tzinfo=timezone.utc)
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
            with open(f'logs_{script_name}.txt', 'w', encoding='utf-8') as f:
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
        globals()['last_log_day'] = get_server_time().date()
    timestamp = get_server_time()
    current_day = timestamp.date()
    # Проверяем смену суток
    if current_day != last_log_day:
        cleanup_logs()
        globals()['last_log_day'] = current_day
    logging.info(f"{event}")


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
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,  # Приватный ключ RSA из Bitwarden
        rsa_authentication=False,      # Включаем RSA-аутентификацию
        testnet=False
    )



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



TRADING_CONFIG = { # True / False
'ENABLE_BULL_LONG': True,
'ENABLE_BULL_SHORT': False,
'ENABLE_BEAR_SHORT': True,
'ENABLE_BEAR_LONG': True,
'COMMISSION_RATE': 0.05,
'ENABLE_LOGGING': True,

'BULL_LONG': {'LEVERAGE': 5.0, 'ENTRY_PERCENT': 90},
'BULL_SHORT': {'LEVERAGE': 1.0, 'ENTRY_PERCENT': 90},
'BEAR_SHORT': {'LEVERAGE': 5.0, 'ENTRY_PERCENT': 90},
'BEAR_LONG': {'LEVERAGE': 1.0, 'ENTRY_PERCENT': 90},
'MAX_ACTIVE_TRADES': 1,

'ENABLE_BULL_MARKET': True,
'ENABLE_BULL_RSI': True,
'ENABLE_BULL_STOCHRSI': True,
'ENABLE_BULL_WILLIAMS_OVERBOUGHT': True,
'ENABLE_BULL_WILLIAMS_OVERSOLD': True,
'ENABLE_BULL_FEAR_GREED': True,

'ENABLE_BEAR_MARKET': True,
'ENABLE_BEAR_RSI': False,
'ENABLE_BEAR_STOCHRSI': False,
'ENABLE_BEAR_WILLIAMS_OVERBOUGHT': True,
'ENABLE_BEAR_WILLIAMS_OVERSOLD': True,
'ENABLE_BEAR_FEAR_GREED': False,
}


ANALYSIS_TIMEFRAME = '1h'
GLOBAL_TIMEFRAME = '1w'

MIN_DELTA_LIQUIDATION_LONG = 10.0 # Минимальная дельта для лонг-позиций
MIN_DELTA_LIQUIDATION_SHORT = 10.0 # Минимальная дельта для шорт-позиций


# Параметры для bull
BULL_RSI_PERIOD = 20
BULL_SMA_RSI_PERIOD = 40
BULL_STOCHRSI_K_PERIOD = 18 
BULL_STOCHRSI_D_PERIOD = 28 
BULL_STOCHRSI_RSI_PERIOD = 14 
BULL_STOCHRSI_STOCH_PERIOD = 20 
BULL_WILLIAMS_OVERBOUGHT_PERIOD = 14
BULL_WILLIAMS_OVERBOUGHT_LEVEL = -1.0
BULL_WILLIAMS_OVERBOUGHT_SOURCE = 'Close'  # 'Open' или 'Close'
BULL_WILLIAMS_OVERSOLD_PERIOD = 20
BULL_WILLIAMS_OVERSOLD_LEVEL = -84.8
BULL_WILLIAMS_OVERSOLD_SOURCE = 'Close'  # 'Open' или 'Close'
BULL_FEAR_GREED_LOW = 9



# Параметры для bear
BEAR_RSI_PERIOD = 16
BEAR_SMA_RSI_PERIOD = 11
BEAR_STOCHRSI_K_PERIOD = 15
BEAR_STOCHRSI_D_PERIOD = 5
BEAR_STOCHRSI_RSI_PERIOD = 14
BEAR_STOCHRSI_STOCH_PERIOD = 14
BEAR_WILLIAMS_OVERBOUGHT_PERIOD = 6
BEAR_WILLIAMS_OVERBOUGHT_LEVEL = -18.0
BEAR_WILLIAMS_OVERBOUGHT_SOURCE = 'Close'  # 'Open' или 'Close'
BEAR_WILLIAMS_OVERSOLD_PERIOD = 17
BEAR_WILLIAMS_OVERSOLD_LEVEL = -90.0
BEAR_WILLIAMS_OVERSOLD_SOURCE = 'Open'  # 'Open' или 'Close'
BEAR_FEAR_GREED_HIGH = 52





def load_historical_data(symbol, timeframe='1w', start_time=None, end_time=None):
    interval = get_bybit_interval(timeframe)
    if start_time is None:
        start_time = datetime(2009, 1, 1, tzinfo=timezone.utc)
    start_ms = int(start_time.timestamp() * 1000)
    if end_time is None:
        end_time = get_server_time()
    end_ms = int(end_time.timestamp() * 1000)
    all_candles = []
    while start_ms < end_ms:
        response = client.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            start=start_ms,
            limit=1000
        )
        if response['retCode'] != 0:
            log_event(f"⚠️ Ошибка загрузки исторических данных: {response['retMsg']}")
            break
        candles = response['result']['list']
        if not candles:
            break
        all_candles.extend(candles)
        last_time = int(candles[0][0])
        start_ms = last_time + 1
    if not all_candles:
        log_event("⚠️ Нет исторических данных для загрузки")
        return pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close'])
    df = pd.DataFrame([{
        'time': pd.to_datetime(int(c[0]), unit='ms', utc=True),
        'open': float(c[1]),
        'high': float(c[2]),
        'low': float(c[3]),
        'close': float(c[4])
    } for c in all_candles])
    df = df.sort_values('time')
    df.set_index('time', inplace=True)
    return df



def calculate_market_periods(df):
    global market_periods
    halvings = [
        datetime(2024, 4, 20, 0, 9, 27, tzinfo=timezone.utc),
    ]
    market_periods = []
    cycle = 4 # Текущий цикл для последнего халвинга
    halving = halvings[0]
    log_event(f"🔄 Обработка цикла {cycle}, дата халвинга: {halving.strftime('%Y-%m-%d')}")
  
    # Ограниченный диапазон для загрузки данных: 100 недель до и 10 после халвинга
    start_time = halving - timedelta(weeks=100)
    end_time = halving + timedelta(weeks=10)
    df_cycle = load_historical_data(symbol, '1w', start_time=start_time, end_time=end_time)
  
    weekday = halving.weekday()
    if weekday == 0:
        monday_after = halving.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        days_to_monday = 7 - weekday
        monday_after = (halving + timedelta(days=days_to_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        i_halving = df_cycle.index.get_loc(monday_after)
    except KeyError:
        return
    i_74 = i_halving - 74
    i_78 = i_halving - 78
    if i_74 < 0 or i_78 < 0:
        log_event(f"⚠️ Индексы за пределами данных для цикла {cycle}, пропуск")
        return
    low_74 = df_cycle.iloc[i_74]['low']
    low_78 = df_cycle.iloc[i_78]['low']
    if low_74 < low_78:
        bottom_i = i_74
    else:
        bottom_i = i_78
    bottom_date = df_cycle.index[bottom_i]
    peak_date = bottom_date + timedelta(weeks=152)
    change_to_bear = peak_date + timedelta(weeks=1)
    bear_change = change_to_bear + timedelta(weeks=52)
    market_periods.append({'cycle': cycle, 'type': 'bull', 'start': bottom_date, 'change': change_to_bear})
    market_periods.append({'cycle': cycle, 'type': 'bear', 'start': change_to_bear, 'change': bear_change})
    for period in market_periods:
        end = period['change'] - timedelta(days=7)
        type_en = period['type']
        start_str = period['start'].strftime('%Y-%m-%d %H:%M:%S')
        end_str = end.strftime('%Y-%m-%d %H:%M:%S')
        change_str = period['change'].strftime('%Y-%m-%d %H:%M:%S')
        log_event(f"📊 {type_en.upper()} цикл {period['cycle']}: {start_str} - {end_str}, смена {change_str}")
    del df_cycle  # Очистка датафрейма после использования
    gc.collect()  # Принудительный сбор мусора для освобождения памяти



def get_market_type(date):
    if TEST_MODE:
        if date >= TEST_NEXT_CHANGE:
            return 'bear' if TEST_MARKET_TYPE == 'bull' else 'bull'
        else:
            return TEST_MARKET_TYPE
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    date_day = date.date()
    if not market_periods:
        log_event("⚠️ Нет периодов рынка для определения типа")
        return None
    for period in market_periods:
        start_day = period['start'].date()
        change_day = period['change'].date()
        if start_day <= date_day < change_day:
            market = period['type']
            if (market == 'bull' and TRADING_CONFIG.get('ENABLE_BULL_MARKET', True)) or \
               (market == 'bear' and TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True)):
                return market
            else:
                return None
    log_event("⚠️ Тип рынка не найден для указанной даты")
    return None



def get_next_market_change_date(current_date):
    if TEST_MODE:
        current_type = get_market_type(current_date)
        next_change = TEST_NEXT_CHANGE if current_date < TEST_NEXT_CHANGE else None
        return current_type, next_change
    if current_date.tzinfo is None:
        current_date = current_date.replace(tzinfo=timezone.utc)
    date_day = current_date.date()
    if not market_periods:
        log_event("⚠️ Нет периодов рынка для определения смены")
        return None, None
    for period in market_periods:
        start_day = period['start'].date()
        change_day = period['change'].date()
        if start_day <= date_day < change_day:
            return period['type'], period['change']
    log_event("⚠️ Не найдена дата смены рынка")
    return None, None




# Обновление пути к файлу с данными свечей для включения новых параметров и типа рынка
def get_market_data_file(market_type):
    if market_type == 'bull':
        return Path(f"market_data_bull_{script_name}.csv")
    elif market_type == 'bear':
        return Path(f"market_data_bear_{script_name}.csv")
    else:
        raise ValueError(f"Неподдерживаемый тип рынка: {market_type}")



def get_current_price_with_retries(client, symbol, max_retries=5, delay=5):
    for attempt in range(max_retries):
        try:
            ticker = client.get_tickers(category="linear", symbol=symbol)
            if ticker['retCode'] != 0:
                raise ValueError(f"Ошибка API: {ticker['retMsg']}")
            current_price = float(ticker['result']['list'][0]['lastPrice'])
            return current_price
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении текущей цены (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))  # Экспоненциальная задержка
            else:
                log_event("⚠️ Не удалось получить текущую цену после всех попыток")
                return None
            


def get_available_balance(max_retries=5, delay=5):
    for attempt in range(max_retries):
        try:
            balance = client.get_wallet_balance(accountType="UNIFIED")
            if balance['retCode'] == 0:
                usdt_balance = next((coin for coin in balance['result']['list'][0]['coin'] if coin['coin'] == 'USDT'), None)
                if usdt_balance:
                    return float(usdt_balance['walletBalance'])
                else:
                    log_event("⚠️ USDT не найден в балансе")
                    return 0
            else:
                raise ValueError(f"Ошибка API: {balance['retMsg']}")
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении баланса (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить баланс после всех попыток")
                return 0




def get_active_trades_from_exchange(client, symbol='BTCUSDT', max_retries=5, delay=5):
    for attempt in range(max_retries):
        try:
            # Получаем данные о позициях (замена Binance get_isolated_margin_account)
            account = client.get_positions(category="linear", symbol=symbol)
            get_available_balance()
            position = account['result']['list'][0]
            net_asset = float(position['size'])
            borrowed_btc = float(position['size']) if position['side'] == 'Sell' else 0.0
            if position['side'] == 'Buy':
                direction = 'LONG'
                size = net_asset
                log_event(f"🟢 Обнаружена активная Лонг-позиция: размер={size:.8f} BTC")
            elif position['side'] == 'Sell':
                direction = 'SHORT'
                size = borrowed_btc
                log_event(f"🟢 Обнаружена активная Шорт-позиция: размер={size:.8f} BTC")
            else:
                log_event("⚪ Нет активных позиций")
                return []

            # Получаем цену ликвидации с проверкой на пустое значение
            liq_price_str = position.get('liqPrice', '')
            if liq_price_str == '':
                liquidation_price = None
                log_event("⚪ Цена ликвидации отсутствует")
            else:
                try:
                    liquidation_price = float(liq_price_str)
                    log_event(f"💥 Цена ликвидации: {liquidation_price:.2f}")
                except ValueError as e:
                    liquidation_price = None
                    log_event(f"⚠️ Ошибка преобразования 'liqPrice' в float: {e}")

            # Получаем текущую рыночную цену
            current_price = get_current_price_with_retries(client, symbol)
            
            # Формируем данные о сделке без цены входа и времени (логика осталась прежней)
            trade_data = {
                'direction': direction,
                'size': size,
                'liquidation_price': liquidation_price,
            }
            return [trade_data]

        except Exception as e:
            log_event(f"⚠️ Ошибка при получении активных сделок (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить активные сделки после всех попыток")
                return []



def sync_active_trades():
    global active_trades, next_trade_id, df_trades, CSV_FILE, current_trade_type, previous_rsi, previous_sma_rsi, current_rsi, current_sma_rsi, next_rsi_update_time
    global current_market_type  # Используем глобальную переменную
    log_event("🔄 Начало синхронизации активных сделок с биржи")
    exchange_trades = get_active_trades_from_exchange(client)
    active_trades.clear()
    current_time = get_server_time()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    if current_market_type is None:
        log_event("⚠️ Тип рынка не определён при синхронизации")
        return
    if exchange_trades:
        trade = exchange_trades[0]
        direction = trade['direction']
        size = trade['size']
        liquidation_price = trade['liquidation_price']
        # Формируем полный тип сделки на основе текущего рынка
        full_direction = None
        if current_market_type == 'bull':
            if direction == 'LONG':
                full_direction = 'BULL_LONG'
            elif direction == 'SHORT':
                full_direction = 'BULL_SHORT'
        elif current_market_type == 'bear':
            if direction == 'SHORT':
                full_direction = 'BEAR_SHORT'
            elif direction == 'LONG':
                full_direction = 'BEAR_LONG'
        if full_direction is None:
            log_event(f"⚠️ Неожиданное направление {direction} для рынка {current_market_type}. Сделка не синхронизирована.")
            return
        if not TRADING_CONFIG[f'ENABLE_{full_direction}']:
            log_event(f"⚠️ Синхронизация {full_direction} отключена в конфигурации")
            return
        log_event(f"📈 Полный тип сделки: {full_direction}")
        # Генерируем новый trade_id
        trade_id = next_trade_id
        next_trade_id += 1
        log_event(f"📝 Новая сделка ID {trade_id}")
        # Создаём запись о сделке без entry_price и entry_time
        trade_record = {
            'id': trade_id,
            'direction': full_direction,
            'entry_price': None, # Цена входа не доступна
            'entry_time': None, # Время входа не доступно
            'current_price': None,
            'current_pnl': 0,
            'current_pnl_percent': 0,
            'size': size,
            'value': None, # Поскольку нет entry_price, value не рассчитывается
            'leverage': TRADING_CONFIG.get(full_direction, {}).get('LEVERAGE', 1),
            'commission_open': 0, # Комиссия не рассчитывается без entry_price
            'net_pnl': 0,
            'net_pnl_percent': 0,
            'status': 'open',
            'trailing_active': False,
            'max_price': None,
            'liquidation_price': liquidation_price,
        }
        # Используем текущий timestamp как ключ
        entry_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        active_trades[entry_time_str] = trade_record
        log_event(f"📝 Сделка добавлена в active_trades")
        current_trade_type = full_direction
        log_event(f"📈 Установлен текущий тип сделки: {current_trade_type}")
        # Обновление df_trades
        if df_trades is None:
            df_trades = pd.DataFrame(columns=[
                'Trade_ID', 'Status', 'Direction', 'Entry_Time', 'Exit_Time', 'Trade_Duration', 'Hours',
                'Entry_Price', 'Exit_Price', 'Position_Size', 'Position_Value',
                'Leverage', 'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'Withdraw'
            ])
            df_trades['Entry_Time'] = pd.Series(dtype='datetime64[ns, UTC]')
            df_trades['Exit_Time'] = pd.Series(dtype='datetime64[ns, UTC]')
            df_trades['Trade_Duration'] = pd.Series(dtype=str)
            df_trades['Hours'] = pd.Series(dtype=float)
            log_event("📝 Создан новый DataFrame для df_trades")
        new_row = {
            'Trade_ID': str(trade_id),
            'Status': 'open',
            'Direction': full_direction,
            'Entry_Time': pd.NaT, # Время входа не доступно
            'Exit_Time': pd.NaT,
            'Trade_Duration': '',
            'Hours': np.nan,
            'Entry_Price': np.nan, # Цена входа не доступна
            'Exit_Price': np.nan,
            'Position_Size': float(size),
            'Position_Value': np.nan, # Значение не рассчитывается
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
    global client, symbol, MIN_DELTA_LIQUIDATION_LONG, MIN_DELTA_LIQUIDATION_SHORT
    global current_market_type  # Используем глобальную переменную
    for attempt in range(3): # Попытки получения данных
        try:
            # Получаем данные о позиции через Bybit API
            position_response = client.get_positions(category="linear", symbol=symbol)
            if position_response['retCode'] != 0:
                raise ValueError(f"Ошибка API: {position_response['retMsg']}")
            positions = position_response['result']['list']
            if not positions:
                log_event("⚪ Нет позиций для управления рисками")
                return
            position = positions[0] # Предполагаем одну позицию на символ
            size = float(position['size'])
            side = position['side']
            direction = 'LONG' if side == 'Buy' else 'SHORT'
            # Получаем цену ликвидации с проверкой на пустое значение
            liq_price_str = position.get('liqPrice', '')
            if liq_price_str == '':
                log_event("⚪ Нет цены ликвидации")
                return
            liquidation_price = float(liq_price_str)
            # Получаем текущую рыночную цену
            current_price = get_current_price_with_retries(client, symbol)
            # Рассчитываем дельту до ликвидации
            if direction == 'LONG':
                delta_percent = (current_price - liquidation_price) / current_price * 100
                min_delta = MIN_DELTA_LIQUIDATION_LONG
            else:
                delta_percent = (liquidation_price - current_price) / current_price * 100
                min_delta = MIN_DELTA_LIQUIDATION_SHORT
            if delta_percent < min_delta:
                log_event(f"⚠️ Дельта {delta_percent:.2f}% < {min_delta}%, требуется частичное закрытие {direction}-позиции")
          
                # Процент от позиции для закрытия
                CLOSE_PERCENT = 5.0 # По умолчанию 5%
          
                # Рассчитываем объем для закрытия как процент от текущего размера позиции
                close_amount = size * (CLOSE_PERCENT / 100)
          
                # Проверяем минимальный объем для закрытия
                MIN_CLOSE_AMOUNT = 0.001 # Минимальный объем для закрытия
                if close_amount < MIN_CLOSE_AMOUNT:
                    close_amount = MIN_CLOSE_AMOUNT
          
                # Округляем объем с учетом точности символа
                close_amount = round(close_amount, 3)
          
                log_event(f"Рассчитан объем для закрытия: {close_amount:.8f} BTC")
          
                # Частичное закрытие позиции
                close_all_trades(reason=f"delta_control_{direction.lower()}", position_value=close_amount)
                time.sleep(2) # Пауза для обновления после закрытия
                # Проверяем новую дельту после закрытия
                position_response = client.get_positions(category="linear", symbol=symbol)
                if position_response['retCode'] != 0:
                    log_event(f"⚠️ Ошибка API после закрытия: {position_response['retMsg']}")
                    return
                positions = position_response['result']['list']
                if positions:
                    position = positions[0]
                    liq_price_str = position.get('liqPrice', '')
                    if liq_price_str:
                        liquidation_price = float(liq_price_str)
                        if direction == 'LONG':
                            delta_percent = (current_price - liquidation_price) / current_price * 100
                        else:
                            delta_percent = (liquidation_price - current_price) / current_price * 100
                        log_event(f"Дельта после частичного закрытия: {delta_percent:.2f}%")
            else:
                # Расчёт критической цены для коррекции
                critical_price = None
                if liquidation_price > 0:
                    if direction == 'LONG':
                        critical_price = liquidation_price / (1 - min_delta / 100)
                    else:
                        critical_price = liquidation_price / (1 + min_delta / 100)
                if critical_price is not None:
                    log_event(f"Уровень мин. дельты: {critical_price:,.2f} USDT")
                log_event(f"Дельта {delta_percent:.2f}% >= {min_delta}%, коррекция не требуется")
            # Определяем тип сделки
            if current_market_type == 'bull':
                trade_type = 'BULL_LONG' if direction == 'LONG' else None
            elif current_market_type == 'bear':
                trade_type = 'BEAR_SHORT' if direction == 'SHORT' else None
            if not trade_type:
                log_event(f"⚠️ Неожиданное направление {direction} для рынка {current_market_type}")
                return
            leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE', 1)
            break # Успешное выполнение, выходим из цикла попыток
        except Exception as e:
            log_event(f"⚠️ Ошибка при управлении рисками (попытка {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5) # Пауза перед повторной попыткой
            else:
                log_event("⚠️ Не удалось получить данные после 3 попыток")



def fetch_fear_greed_data(filename=f"fear_greed_index_{script_name}.csv", max_retries=5, delay=5):
    url = "https://api.alternative.me/fng/?limit=21"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.json()['data']
            data = response.json()['data']
            with open(filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Date', 'Value', 'Classification'])
                for entry in data:
                    timestamp = int(entry['timestamp'])
                    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None).strftime('%d/%m/%Y')
                    value = entry['value']
                    classification = entry.get('value_classification', 'Unknown')
                    writer.writerow([date, value, classification])
            return data
        except requests.RequestException as e:
            log_event(f"⚠️ Ошибка при запросе данных (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить данные индекса после всех попыток")
                return []


def load_fear_greed_data():
    global fear_greed_data
    fear_greed_file = Path(f"fear_greed_index_{script_name}.csv")
    if fear_greed_file.exists():
        fear_greed_data = pd.read_csv(fear_greed_file, parse_dates=['Date'], dayfirst=True)
        fear_greed_data['Date'] = pd.to_datetime(fear_greed_data['Date'], format='%d/%m/%Y', utc=True)
        if fear_greed_data['Date'].dt.tz is None:
            fear_greed_data['Date'] = fear_greed_data['Date'].dt.tz_localize('UTC')
        fear_greed_data = fear_greed_data.sort_values(by='Date')
    else:
        fear_greed_data = pd.DataFrame(columns=['Date', 'Value'])
        log_event("⚠️ Файл fear_greed_index.csv не найден, создан пустой DataFrame")
    return fear_greed_data


def get_fear_greed_value(date, timeframe=GLOBAL_TIMEFRAME):
    global fear_greed_data
    if fear_greed_data is None or fear_greed_data.empty:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    # Преобразуем таймфрейм в количество дней
    timeframe_days = get_timeframe_days(timeframe)
    if timeframe_days <= 1:
        # Для таймфрейма ≤ 1 дня возвращаем данные за предыдущий день
        target_date = date - timedelta(days=1)
    else:
        # Для таймфрейма > 1 дня определяем дату начала предыдущей свечи
        target_date = date - timedelta(days=timeframe_days)
        # Корректируем дату на понедельник
        days_to_monday = target_date.weekday() # 0 = понедельник, 6 = воскресенье
        if days_to_monday != 0:
            target_date = target_date - timedelta(days=days_to_monday)
    # Приводим дату к началу дня (00:00:00)
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if target_date.tzinfo is None:
        target_date = target_date.replace(tzinfo=timezone.utc)
    # Ищем данные за target_date в fear_greed_data
    filtered = fear_greed_data[fear_greed_data['Date'] == target_date]
    if not filtered.empty:
        return filtered.iloc[0]['Value']
    return None


def initialize_market_data_file(market_type):
    MARKET_DATA_FILE = get_market_data_file(market_type)
    headers = ['time', 'open', 'high', 'low', 'close', 'RSI', 'RSI-based MA', 'StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold']
    if not MARKET_DATA_FILE.exists():
        with open(MARKET_DATA_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        log_event(f"📝 Создан новый файл {MARKET_DATA_FILE} с заголовками")
    else:
        # Проверяем и добавляем новые столбцы, если их нет
        df = pd.read_csv(MARKET_DATA_FILE)
        new_columns = ['StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold']
        for col in new_columns:
            if col not in df.columns:
                df[col] = np.nan
                log_event(f"🆕 Добавлен столбец '{col}' в существующий файл {MARKET_DATA_FILE}")
        df.to_csv(MARKET_DATA_FILE, index=False)
        log_event(f"📁 Файл {MARKET_DATA_FILE} обновлён с новыми столбцами")
    

def load_market_data(market_type):
    global current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi
    global current_stoch_k, current_stoch_d, previous_stoch_k, previous_stoch_d
    global current_williams_r_overbought, previous_williams_r_overbought
    global current_williams_r_oversold, previous_williams_r_oversold
    MARKET_DATA_FILE = get_market_data_file(market_type)
    try:
        if MARKET_DATA_FILE.exists():
            df = pd.read_csv(
                MARKET_DATA_FILE,
                parse_dates=['time'],
                date_format='%Y-%m-%d %H:%M:%S'
            )
            # Приведение типов данных к float64 для всех числовых столбцов (для совместимости с TALib)
            numeric_cols = ['open', 'high', 'low', 'close', 'RSI', 'RSI-based MA', 'StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype(np.float64)
            # Проверка и приведение столбца time к datetime64[ns, UTC] aware
            df['time'] = pd.to_datetime(df['time'], errors='coerce', utc=True)
            df = df.dropna(subset=['time']) # Удаляем строки с некорректными датами
            df = df.sort_values(by='time')
            df = df.tail(242)
     
            # Установка глобальных значений всегда
            if len(df) >= 2:
                previous_rsi = df['RSI'].iloc[-2]
                current_rsi = df['RSI'].iloc[-1]
                previous_sma_rsi = df['RSI-based MA'].iloc[-2]
                current_sma_rsi = df['RSI-based MA'].iloc[-1]
         
                previous_stoch_k = df['StochRSI_K'].iloc[-2]
                current_stoch_k = df['StochRSI_K'].iloc[-1]
                previous_stoch_d = df['StochRSI_D'].iloc[-2]
                current_stoch_d = df['StochRSI_D'].iloc[-1]
         
                previous_williams_r_overbought = df['Williams_R_Overbought'].iloc[-2]
                current_williams_r_overbought = df['Williams_R_Overbought'].iloc[-1]
         
                previous_williams_r_oversold = df['Williams_R_Oversold'].iloc[-2]
                current_williams_r_oversold = df['Williams_R_Oversold'].iloc[-1]
         
            else:
                # Инициализация NaN для всех, если данных мало
                current_rsi = current_sma_rsi = previous_rsi = previous_sma_rsi = np.nan
                current_stoch_k = current_stoch_d = previous_stoch_k = previous_stoch_d = np.nan
                current_williams_r_overbought = previous_williams_r_overbought = np.nan
                current_williams_r_oversold = previous_williams_r_oversold = np.nan
                log_event("🗑️ Файл MARKET_DATA пустой, загружаю данные для расчета индикаторов. ")
            return df
        else:
            log_event(f"⚠️ Файл {MARKET_DATA_FILE} не найден, создан пустой DataFrame")
            # Инициализация NaN для всех индикаторов
            current_rsi = current_sma_rsi = previous_rsi = previous_sma_rsi = np.nan
            current_stoch_k = current_stoch_d = previous_stoch_k = previous_stoch_d = np.nan
            current_williams_r_overbought = previous_williams_r_overbought = np.nan
            current_williams_r_oversold = previous_williams_r_oversold = np.nan
            return pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'RSI', 'RSI-based MA', 'StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold'])
    except Exception as e:
        log_event(f"⚠️ Ошибка при загрузке данных из {MARKET_DATA_FILE}: {e}")
        # Инициализация NaN в случае ошибки
        current_rsi = current_sma_rsi = previous_rsi = previous_sma_rsi = np.nan
        current_stoch_k = current_stoch_d = previous_stoch_k = previous_stoch_d = np.nan
        current_williams_r_overbought = previous_williams_r_overbought = np.nan
        current_williams_r_oversold = previous_williams_r_oversold = np.nan
        return pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'RSI', 'RSI-based MA', 'StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold'])



def save_market_data(df, market_type):
    MARKET_DATA_FILE = get_market_data_file(market_type)
    try:
        df = df.tail(9).copy()
        # Преобразование числовых столбцов в float64 для точности расчётов
        numeric_cols = ['open', 'high', 'low', 'close', 'RSI', 'RSI-based MA', 'StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(np.float64)
        # Приводим time к UTC aware, если оно timezone-aware
        if 'time' in df.columns and df['time'].dt.tz is not None:
            df['time'] = df['time'].dt.tz_convert('UTC')
        # Форматируем время в строковый формат без временной зоны
        df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        # Убеждаемся, что все столбцы присутствуют
        required_cols = ['time', 'open', 'high', 'low', 'close', 'RSI', 'RSI-based MA', 'StochRSI_K', 'StochRSI_D', 'Williams_R_Overbought', 'Williams_R_Oversold']
        for col in required_cols:
            if col not in df.columns:
                df[col] = np.nan
        df = df[required_cols]
        df.to_csv(MARKET_DATA_FILE, index=False)
    except Exception as e:
        log_event(f"⚠️ Ошибка при сохранении данных в {MARKET_DATA_FILE}: {e}")




def get_timeframe_days(timeframe):
    if timeframe.endswith('m'):  # минутный таймфрейм
        minutes = int(timeframe[:-1])
        return minutes / 1440.0  # возвращаем долю дня (в сутках 1440 минут)
    elif timeframe.endswith('h'):  # часовой таймфрейм
        hours = int(timeframe[:-1])
        return hours / 24.0  # возвращаем долю дня (в сутках 24 часа)
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
        return "down" # Пересечение сверху вниз
    elif previous_rsi < previous_sma_rsi and current_rsi > current_sma_rsi:
        return "up" # Пересечение снизу вверх
    return None
    

def check_stoch_crossing(current_k, current_d):
    """Определяет, произошло ли пересечение %K и %D Stochastic RSI (down для сигнала закрытия лонг, up для шорт)."""
    global previous_stoch_k, previous_stoch_d
    if previous_stoch_k is None or previous_stoch_d is None:
        return None
    if previous_stoch_k > previous_stoch_d and current_k < current_d:
        return "down" # Пересечение сверху вниз
    elif previous_stoch_k < previous_stoch_d and current_k > current_d:
        return "up" # Пересечение снизу вверх
    return None



def check_williams_overbought(market_type):
    """Проверяет overbought для Williams %R (для закрытия лонг-позиций или открытия шорт)."""
    global current_williams_r_overbought
    level = BULL_WILLIAMS_OVERBOUGHT_LEVEL if market_type == 'bull' else BEAR_WILLIAMS_OVERBOUGHT_LEVEL
    if current_williams_r_overbought is not None and current_williams_r_overbought >= level:
        return True # Overbought, сигнал
    return False


def check_williams_oversold(market_type):
    """Проверяет oversold для Williams %R (для открытия лонг-позиций или закрытия шорт)."""
    global current_williams_r_oversold
    level = BULL_WILLIAMS_OVERSOLD_LEVEL if market_type == 'bull' else BEAR_WILLIAMS_OVERSOLD_LEVEL
    if current_williams_r_oversold is not None and current_williams_r_oversold <= level:
        return True # Oversold, сигнал
    return False


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
        'Entry_Time': 'datetime64[ns, UTC]',
        'Exit_Time': 'datetime64[ns, UTC]',
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
                dtype={col: dtypes[col] for col in headers if col not in ['Entry_Time', 'Exit_Time']}
            )
            # Принудительно парсим даты с utc=True и обработкой ошибок
            df_trades['Entry_Time'] = pd.to_datetime(df_trades['Entry_Time'], utc=True, errors='coerce')
            df_trades['Exit_Time'] = pd.to_datetime(df_trades['Exit_Time'], utc=True, errors='coerce')
            missing_cols = [col for col in headers if col not in df_trades.columns]
            for col in missing_cols:
                df_trades[col] = pd.Series(dtype=dtypes[col])
            df_trades = df_trades[headers]
            # Безопасное приведение Position_Size к числу, если это строка
            df_trades['Position_Size'] = pd.to_numeric(df_trades['Position_Size'], errors='coerce')
            df_trades = df_trades.tail(30)  # Ограничение до 30 строк
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


def update_market_data_on_candle_close(symbol, timeframe, current_time, limit=242, end_time=None):
    global client, BULL_RSI_PERIOD, BULL_SMA_RSI_PERIOD, BULL_STOCHRSI_K_PERIOD, BULL_STOCHRSI_D_PERIOD, BULL_STOCHRSI_RSI_PERIOD, BULL_STOCHRSI_STOCH_PERIOD, BULL_WILLIAMS_OVERBOUGHT_PERIOD, BULL_WILLIAMS_OVERSOLD_PERIOD
    global BEAR_RSI_PERIOD, BEAR_SMA_RSI_PERIOD, BEAR_STOCHRSI_K_PERIOD, BEAR_STOCHRSI_D_PERIOD, BEAR_STOCHRSI_RSI_PERIOD, BEAR_STOCHRSI_STOCH_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_PERIOD, BEAR_WILLIAMS_OVERSOLD_PERIOD
    global current_market_type # Используем глобальную переменную
    if current_market_type is None:
        log_event("⚠️ Тип рынка не определён")
        return
    df_market = load_market_data(current_market_type) # Используем глобальную вместо вызова
    interval = get_bybit_interval(timeframe)
    tf_delta = parse_timeframe(timeframe)
    tf_delta_ms = int(tf_delta.total_seconds() * 1000)
    # Определяем начало текущей свечи
    current_candle_start = get_current_candle_start_time(current_time, timeframe)
    # Точный end_time как конец последней закрытой свечи (или кастомный)
    if end_time is None:
        end_time = current_candle_start - timedelta(microseconds=1)
    end_time_ms = int(end_time.timestamp() * 1000)
    # Точный start_time как начало limit-й предыдущей свечи
    start_time = current_candle_start - limit * tf_delta
    start_time_ms = int(start_time.timestamp() * 1000)
    # Проверка корректности диапазона времени
    if start_time_ms >= end_time_ms:
        log_event("⚠️ Некорректный диапазон времени: start_time_ms >= end_time_ms, корректируем start_time_ms")
        start_time_ms = int((current_candle_start - limit * tf_delta).timestamp() * 1000)
    max_retries = 5
    delay = 5
    candles = None
    for attempt in range(max_retries):
        try:
            response = client.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                start=start_time_ms,
                end=end_time_ms,
                limit=limit
            )
            if response['retCode'] != 0:
                raise ValueError(f"Ошибка API: {response['retMsg']}")
            candles = response['result']['list']
            break
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении свечей (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                log_event("⚠️ Не удалось получить свечи после всех попыток")
                return
    if not candles:
        log_event("⚠️ Нет закрытых свечей для актуализации")
        return
    new_rows = []
    for candle in candles:
        candle_time = pd.to_datetime(int(candle[0]), unit='ms', utc=True)
        new_data = {
            'time': candle_time,
            'open': float(candle[1]),
            'high': float(candle[2]),
            'low': float(candle[3]),
            'close': float(candle[4])
        }
        new_rows.append(new_data)
    if not new_rows:
        log_event("📝 Нет новых данных для добавления")
        return
    new_df = pd.DataFrame(new_rows)
    # Удаляем старые записи в диапазоне запрошенных свечей
    if not df_market.empty:
        min_time = new_df['time'].min()
        max_time = new_df['time'].max()
        df_market = df_market[(df_market['time'] < min_time) | (df_market['time'] > max_time)]
    # Добавляем свежие данные с проверкой на пустой df_market для избежания FutureWarning
    if df_market.empty:
        df_market = new_df
    else:
        df_market = pd.concat([df_market, new_df], ignore_index=True)
    df_market = df_market.sort_values(by='time').drop_duplicates(subset=['time'])
    # Универсальный расчет индикаторов с выбором параметров по типу рынка
    closes_np = df_market['close'].values.astype(np.float64)
    highs_np = df_market['high'].values.astype(np.float64)
    lows_np = df_market['low'].values.astype(np.float64)
    opens_np = df_market['open'].values.astype(np.float64) # Добавлен массив для opens
    rsi_period = BULL_RSI_PERIOD if current_market_type == 'bull' else BEAR_RSI_PERIOD
    sma_rsi_period = BULL_SMA_RSI_PERIOD if current_market_type == 'bull' else BEAR_SMA_RSI_PERIOD
    stochrsi_k_period = BULL_STOCHRSI_K_PERIOD if current_market_type == 'bull' else BEAR_STOCHRSI_K_PERIOD
    stochrsi_d_period = BULL_STOCHRSI_D_PERIOD if current_market_type == 'bull' else BEAR_STOCHRSI_D_PERIOD
    stochrsi_rsi_period = BULL_STOCHRSI_RSI_PERIOD if current_market_type == 'bull' else BEAR_STOCHRSI_RSI_PERIOD
    stochrsi_stoch_period = BULL_STOCHRSI_STOCH_PERIOD if current_market_type == 'bull' else BEAR_STOCHRSI_STOCH_PERIOD
    williams_overbought_period = BULL_WILLIAMS_OVERBOUGHT_PERIOD if current_market_type == 'bull' else BEAR_WILLIAMS_OVERBOUGHT_PERIOD
    williams_oversold_period = BULL_WILLIAMS_OVERSOLD_PERIOD if current_market_type == 'bull' else BEAR_WILLIAMS_OVERSOLD_PERIOD
    williams_overbought_source = BULL_WILLIAMS_OVERBOUGHT_SOURCE if current_market_type == 'bull' else BEAR_WILLIAMS_OVERBOUGHT_SOURCE
    williams_oversold_source = BULL_WILLIAMS_OVERSOLD_SOURCE if current_market_type == 'bull' else BEAR_WILLIAMS_OVERSOLD_SOURCE
    # RSI (всегда рассчитывается)
    if len(closes_np) >= rsi_period:
        rsi = talib.RSI(closes_np, timeperiod=rsi_period)
        df_market['RSI'] = rsi.astype(np.float64)
        if len(rsi) >= sma_rsi_period:
            sma_rsi = talib.SMA(rsi, timeperiod=sma_rsi_period)
            df_market['RSI-based MA'] = sma_rsi.astype(np.float64)
        else:
            df_market['RSI-based MA'] = np.full(len(rsi), np.nan, dtype=np.float64)
    else:
        df_market['RSI'] = np.full(len(closes_np), np.nan, dtype=np.float64)
        df_market['RSI-based MA'] = np.full(len(closes_np), np.nan, dtype=np.float64)
    # Stochastic RSI (всегда рассчитывается)
    if len(closes_np) >= stochrsi_rsi_period:
        fastk, fastd = talib.STOCHRSI(
            closes_np,
            timeperiod=stochrsi_rsi_period,
            fastk_period=stochrsi_stoch_period,
            fastd_period=stochrsi_k_period,
            fastd_matype=0
        )
        df_market['StochRSI_K'] = fastd.astype(np.float64)
        if len(fastd) >= stochrsi_d_period:
            df_market['StochRSI_D'] = talib.SMA(fastd, timeperiod=stochrsi_d_period).astype(np.float64)
        else:
            df_market['StochRSI_D'] = np.full(len(fastd), np.nan, dtype=np.float64)
    else:
        df_market['StochRSI_K'] = np.full(len(closes_np), np.nan, dtype=np.float64)
        df_market['StochRSI_D'] = np.full(len(closes_np), np.nan, dtype=np.float64)
    # Williams %R overbought (всегда рассчитывается)
    if len(df_market) >= williams_overbought_period:
        source_overbought_np = opens_np if williams_overbought_source == 'Open' else closes_np
        df_market['Williams_R_Overbought'] = talib.WILLR(highs_np, lows_np, source_overbought_np, timeperiod=williams_overbought_period).astype(np.float64)
    else:
        df_market['Williams_R_Overbought'] = np.full(len(df_market), np.nan, dtype=np.float64)
    # Williams %R oversold (всегда рассчитывается)
    if len(df_market) >= williams_oversold_period:
        source_oversold_np = opens_np if williams_oversold_source == 'Open' else closes_np
        df_market['Williams_R_Oversold'] = talib.WILLR(highs_np, lows_np, source_oversold_np, timeperiod=williams_oversold_period).astype(np.float64)
    else:
        df_market['Williams_R_Oversold'] = np.full(len(df_market), np.nan, dtype=np.float64)
    del closes_np, highs_np, lows_np, opens_np
    save_market_data(df_market, current_market_type)





def get_current_candle_start_time(current_time, timeframe):
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    tf_delta = parse_timeframe(timeframe)
    if timeframe.endswith('m') or timeframe.endswith('h'):
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc) # Naive datetime
        remainder = (current_time - epoch) % tf_delta
        start_time = current_time - remainder
    elif timeframe.endswith('d'):
        start_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeframe.endswith('w'):
        weekday = current_time.weekday()
        days_to_monday = weekday % 7 # Предполагаем, что неделя начинается в понедельник (0)
        start_time = (current_time - timedelta(days=days_to_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeframe.endswith('M'):
        start_time = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return start_time





def get_current_candle_end_time(current_time, timeframe):
    """Нужна для расчетов on_orderbook_message. Вычисляет время окончания текущей свечи для заданного таймфрейма."""
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    tf_delta = parse_timeframe(timeframe)
    if timeframe.endswith('m') or timeframe.endswith('h'):
        start_time = current_time - (current_time - datetime(1970, 1, 1, tzinfo=timezone.utc)) % tf_delta
        end_time = start_time + tf_delta
    elif timeframe.endswith('d'):
        end_time = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif timeframe.endswith('w'):
        weekday = current_time.weekday()
        days_to_sunday = (6 - weekday) % 7
        end_time = (current_time + timedelta(days=days_to_sunday)).replace(hour=23, minute=59, second=59, microsecond=999999)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    return end_time





def get_next_candle_end_time(current_time, timeframe):
    """Определяет время окончания следующей свечи для заданного таймфрейма."""
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    tf_delta = parse_timeframe(timeframe)
    if timeframe.endswith('m') or timeframe.endswith('h'):
        start_time = current_time - (current_time - datetime(1970,1,1, tzinfo=timezone.utc)) % tf_delta
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
    if next_end.tzinfo is None:
        next_end = next_end.replace(tzinfo=timezone.utc)
    return next_end



def log_market_data(mid_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_fear_greed_value, get_available_balance):
    global current_stoch_k, current_stoch_d, current_williams_r_overbought, current_williams_r_oversold
    global current_market_type  # Используем глобальную переменную
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
    log_event("---------------| Юнона 3 BYBIT |--------------|")
    log_event("------- Изолированная маржа [BTC/USDT] -------|")
    log_event("----------------------------------------------|")
    log_event(f"Таймфрейм: {GLOBAL_TIMEFRAME}, Данные: {ANALYSIS_TIMEFRAME}")
    log_event("----------------------------------------------|")
    log_event(f"Рыночная цена: {mid_price:,.1f}{price_indicator} ")
    current_time = get_server_time()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    df_market = load_market_data(current_market_type)  # Используем глобальную вместо повторного вызова
    current_candle_start = get_current_candle_start_time(current_time, GLOBAL_TIMEFRAME)
    end_datetime = current_candle_start - timedelta(microseconds=1)
    if not df_market.empty:
        df_filtered = df_market[df_market['time'] < end_datetime].sort_values(by='time', ascending=False)
        if len(df_filtered) >= 1:
            last_closed_candle = df_filtered.iloc[0]
            last_open = last_closed_candle['open']
            last_close = last_closed_candle['close']
            candle_time = last_closed_candle['time'].strftime('%Y-%m-%d %H:%M:%S')
            log_event(f"Последняя свеча: {candle_time}")
            log_event(f"Открытие: {last_open:,.2f}, Закрытие: {last_close:,.2f}")
        else:
            log_event("Открытие и Закрытие: недостаточно данных в файле за предыдущую закрытую свечу")
    else:
        log_event("Открытие и Закрытие: файл market_data.csv пуст или недоступен")
    if current_rsi is not None and current_sma_rsi is not None:
        sma_rsi_delta = current_rsi - current_sma_rsi
        log_event(f"RSI: {current_rsi:.2f} | SMA RSI: {current_sma_rsi:.2f} | {sma_rsi_delta:.2f}")
    else:
        log_event("RSI и SMA RSI: недостаточно данных")
    # Вывод StochRSI
    if current_stoch_k is not None and current_stoch_d is not None:
        log_event(f"StochRSI K: {current_stoch_k:.2f} | D: {current_stoch_d:.2f}")
    else:
        log_event("StochRSI: недостаточно данных")
    # Вывод Williams %R overbought и oversold
    if current_williams_r_overbought is not None:
        log_event(f"Williams %R Overbought: {current_williams_r_overbought:.2f}")
    else:
        log_event("Williams %R Overbought: недостаточно данных")
    if current_williams_r_oversold is not None:
        log_event(f"Williams %R Oversold: {current_williams_r_oversold:.2f}")
    else:
        log_event("Williams %R Oversold: недостаточно данных")
    fear_greed_value = get_fear_greed_value(current_time)
    if fear_greed_value is not None:
        log_event(f"Индекс страха и жадности: {fear_greed_value}")
    else:
        log_event("Индекс страха и жадности: данные недоступны")
    available_balance = get_available_balance()
    log_event(f"Доступный баланс: {available_balance:,.2f} USDT")
    log_event("----------------------------------------------|")



def check_signals(current_price):
    global current_trade_type, previous_rsi, previous_sma_rsi, last_market_type, current_rsi, current_sma_rsi
    global previous_stoch_k, previous_stoch_d, current_stoch_k, current_stoch_d
    global previous_williams_r_overbought, current_williams_r_overbought
    global previous_williams_r_oversold, current_williams_r_oversold
    global BULL_WILLIAMS_OVERBOUGHT_LEVEL, BULL_WILLIAMS_OVERSOLD_LEVEL, BEAR_WILLIAMS_OVERBOUGHT_LEVEL, BEAR_WILLIAMS_OVERSOLD_LEVEL
    global current_market_type # Используем глобальную переменную
    with trades_lock:
        current_time = get_server_time()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        if current_market_type is None:
            log_event("⚠️ Тип рынка не определён для текущей даты")
            return
        # Получаем значение индекса страха и жадности
        fear_greed_value = get_fear_greed_value(current_time)
        if fear_greed_value is None:
            log_event("⚠️ Нет данных индекса страха для текущей даты. Работаем только по RSI.")
        # Проверяем пересечение RSI и SMA RSI напрямую на globals (как в бэктесте после импорта после импорта)
        crossing = check_rsi_crossing(current_rsi, current_sma_rsi)
        # Проверяем пересечение StochRSI K/D напрямую на globals
        stoch_crossing = check_stoch_crossing(current_stoch_k, current_stoch_d)
        # Логика для бычьего рынка
        if current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_MARKET']:
            if not active_trades:
                # Открытие bull long: RSI вверх
                if TRADING_CONFIG['ENABLE_BULL_LONG'] and TRADING_CONFIG['ENABLE_BULL_RSI'] and crossing == "up":
                    log_event(f"📈 Сигнал на открытие BULL_LONG: Пересечение RSI вверх")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_LONG', current_price, position_value)
                # Открытие bull long: перепроданность Williams
                if TRADING_CONFIG['ENABLE_BULL_LONG'] and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD'] and current_williams_r_oversold <= BULL_WILLIAMS_OVERSOLD_LEVEL:
                    log_event(f"📈 Сигнал на открытие BULL_LONG: Перепроданность Williams %R")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_LONG', current_price, position_value)
                # Открытие bull long: индекс страха
                if TRADING_CONFIG['ENABLE_BULL_LONG'] and TRADING_CONFIG['ENABLE_BULL_FEAR_GREED'] and fear_greed_value is not None and fear_greed_value <= BULL_FEAR_GREED_LOW:
                    log_event(f"📈 Сигнал на открытие BULL_LONG: Низкий индекс страха ({fear_greed_value})")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_LONG', current_price, position_value)
                # Открытие bull long: StochRSI вверх (новое условие)
                if TRADING_CONFIG['ENABLE_BULL_LONG'] and TRADING_CONFIG['ENABLE_BULL_STOCHRSI'] and stoch_crossing == "up":
                    log_event(f"📈 Сигнал на открытие BULL_LONG: Пересечение StochRSI вверх")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_LONG', current_price, position_value)
                # Открытие bull short: RSI вниз
                if TRADING_CONFIG['ENABLE_BULL_SHORT'] and TRADING_CONFIG['ENABLE_BULL_RSI'] and crossing == "down":
                    log_event(f"📉 Сигнал на открытие BULL_SHORT: Пересечение RSI вниз")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_SHORT', current_price, position_value)
                # Открытие bull short: перекупленность Williams
                if TRADING_CONFIG['ENABLE_BULL_SHORT'] and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT'] and current_williams_r_overbought >= BULL_WILLIAMS_OVERBOUGHT_LEVEL:
                    log_event(f"📉 Сигнал на открытие BULL_SHORT: Перекупленность Williams %R")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_SHORT', current_price, position_value)
                # Открытие bull short: высокий индекс жадности
                if TRADING_CONFIG['ENABLE_BULL_SHORT'] and TRADING_CONFIG['ENABLE_BULL_FEAR_GREED'] and fear_greed_value is not None and fear_greed_value >= BULL_FEAR_GREED_HIGH:
                    log_event(f"📉 Сигнал на открытие BULL_SHORT: Высокий индекс жадности ({fear_greed_value})")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_SHORT', current_price, position_value)
                # Открытие bull short: StochRSI вниз (новое условие)
                if TRADING_CONFIG['ENABLE_BULL_SHORT'] and TRADING_CONFIG['ENABLE_BULL_STOCHRSI'] and stoch_crossing == "down":
                    log_event(f"📉 Сигнал на открытие BULL_SHORT: Пересечение StochRSI вниз")
                    position_value = (get_available_balance() * TRADING_CONFIG['BULL_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BULL_SHORT', current_price, position_value)
            else:
                if current_trade_type == 'BULL_LONG':
                    # Закрытие bull long: RSI вниз
                    if TRADING_CONFIG['ENABLE_BULL_RSI'] and crossing == "down":
                        log_event(f"🔄 Закрытие BULL_LONG: Пересечение RSI вниз")
                        close_all_trades("rsi_down", force_close=True)
                    # Закрытие bull long: стохастик вниз
                    if TRADING_CONFIG['ENABLE_BULL_STOCHRSI'] and stoch_crossing == "down":
                        log_event(f"🔄 Закрытие BULL_LONG: Пересечение StochRSI вниз")
                        close_all_trades("stoch_down", force_close=True)
                    # Закрытие bull long: перекупленность по Williams
                    if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT'] and current_williams_r_overbought >= BULL_WILLIAMS_OVERBOUGHT_LEVEL:
                        log_event(f"🔄 Закрытие BULL_LONG: Перекупленность Williams %R")
                        close_all_trades("williams_overbought", force_close=True)
                elif current_trade_type == 'BULL_SHORT':
                    # Закрытие bull short: RSI вверх
                    if TRADING_CONFIG['ENABLE_BULL_RSI'] and crossing == "up":
                        log_event(f"🔄 Закрытие BULL_SHORT: Пересечение RSI вверх")
                        close_all_trades("rsi_up", force_close=True)
                    # Закрытие bull short: стохастик вверх
                    if TRADING_CONFIG['ENABLE_BULL_STOCHRSI'] and stoch_crossing == "up":
                        log_event(f"🔄 Закрытие BULL_SHORT: Пересечение StochRSI вверх")
                        close_all_trades("stoch_up", force_close=True)
                    # Закрытие bull short: перепроданность по Williams
                    if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD'] and current_williams_r_oversold <= BULL_WILLIAMS_OVERSOLD_LEVEL:
                        log_event(f"🔄 Закрытие BULL_SHORT: Перепроданность Williams %R")
                        close_all_trades("williams_oversold", force_close=True)
        # Логика для медвежьего рынка
        elif current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_MARKET']:
            if not active_trades:
                # Открытие bear short: RSI вниз
                if TRADING_CONFIG['ENABLE_BEAR_SHORT'] and TRADING_CONFIG['ENABLE_BEAR_RSI'] and crossing == "down":
                    log_event(f"📉 Сигнал на открытие BEAR_SHORT: Пересечение RSI вниз")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_SHORT', current_price, position_value)
                # Открытие bear short: перекупленность Williams
                if TRADING_CONFIG['ENABLE_BEAR_SHORT'] and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT'] and current_williams_r_overbought >= BEAR_WILLIAMS_OVERBOUGHT_LEVEL:
                    log_event(f"📉 Сигнал на открытие BEAR_SHORT: Перекупленность Williams %R")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_SHORT', current_price, position_value)
                # Открытие bear short: индекс страха
                if TRADING_CONFIG['ENABLE_BEAR_SHORT'] and TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED'] and fear_greed_value is not None and fear_greed_value >= BEAR_FEAR_GREED_HIGH:
                    log_event(f"📉 Сигнал на открытие BEAR_SHORT: Высокий индекс страха ({fear_greed_value})")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_SHORT', current_price, position_value)
                # Открытие bear short: StochRSI вниз (новое условие)
                if TRADING_CONFIG['ENABLE_BEAR_SHORT'] and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI'] and stoch_crossing == "down":
                    log_event(f"📉 Сигнал на открытие BEAR_SHORT: Пересечение StochRSI вниз")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_SHORT']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_SHORT', current_price, position_value)
                # Открытие bear long: RSI вверх
                if TRADING_CONFIG['ENABLE_BEAR_LONG'] and TRADING_CONFIG['ENABLE_BEAR_RSI'] and crossing == "up":
                    log_event(f"📈 Сигнал на открытие BEAR_LONG: Пересечение RSI вверх")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_LONG', current_price, position_value)
                # Открытие bear long: перепроданность Williams
                if TRADING_CONFIG['ENABLE_BEAR_LONG'] and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD'] and current_williams_r_oversold <= BEAR_WILLIAMS_OVERSOLD_LEVEL:
                    log_event(f"📈 Сигнал на открытие BEAR_LONG: Перепроданность Williams %R")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_LONG', current_price, position_value)
                # Открытие bear long: низкий индекс страха
                if TRADING_CONFIG['ENABLE_BEAR_LONG'] and TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED'] and fear_greed_value is not None and fear_greed_value <= BEAR_FEAR_GREED_LOW:
                    log_event(f"📈 Сигнал на открытие BEAR_LONG: Низкий индекс страха ({fear_greed_value})")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_LONG', current_price, position_value)
                # Открытие bear long: StochRSI вверх (новое условие)
                if TRADING_CONFIG['ENABLE_BEAR_LONG'] and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI'] and stoch_crossing == "up":
                    log_event(f"📈 Сигнал на открытие BEAR_LONG: Пересечение StochRSI вверх")
                    position_value = (get_available_balance() * TRADING_CONFIG['BEAR_LONG']['ENTRY_PERCENT']) / 100
                    open_trade('BEAR_LONG', current_price, position_value)
            else:
                if current_trade_type == 'BEAR_SHORT':
                    # Закрытие bear short: RSI вверх
                    if TRADING_CONFIG['ENABLE_BEAR_RSI'] and crossing == "up":
                        log_event(f"🔄 Закрытие BEAR_SHORT: Пересечение RSI вверх")
                        close_all_trades("rsi_up", force_close=True)
                    # Закрытие bear short: стохастик вверх (обратное пересечение)
                    if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI'] and stoch_crossing == "up":
                        log_event(f"🔄 Закрытие BEAR_SHORT: Пересечение StochRSI вверх")
                        close_all_trades("stoch_up", force_close=True)
                    # Закрытие bear short: перепроданность по Williams
                    if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD'] and current_williams_r_oversold <= BEAR_WILLIAMS_OVERSOLD_LEVEL:
                        log_event(f"🔄 Закрытие BEAR_SHORT: Перепроданность Williams %R")
                        close_all_trades("williams_oversold", force_close=True)
                elif current_trade_type == 'BEAR_LONG':
                    # Закрытие bear long: RSI вниз
                    if TRADING_CONFIG['ENABLE_BEAR_RSI'] and crossing == "down":
                        log_event(f"🔄 Закрытие BEAR_LONG: Пересечение RSI вниз")
                        close_all_trades("rsi_down", force_close=True)
                    # Закрытие bear long: стохастик вниз
                    if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI'] and stoch_crossing == "down":
                        log_event(f"🔄 Закрытие BEAR_LONG: Пересечение StochRSI вниз")
                        close_all_trades("stoch_down", force_close=True)
                    # Закрытие bear long: перекупленность по Williams
                    if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT'] and current_williams_r_overbought >= BEAR_WILLIAMS_OVERBOUGHT_LEVEL:
                        log_event(f"🔄 Закрытие BEAR_LONG: Перекупленность Williams %R")
                        close_all_trades("williams_overbought", force_close=True)
        manage_liquidation_price()
        # Отображение всех активных сделок
        log_event("----------------------------------------------|")
        log_event("-------------- Проверка сигнала --------------|")
        log_event("----------------------------------------------|")


def open_trade(trade_type, entry_price, position_value=None, trailing_status=None):
    global next_trade_id, active_trades, df_trades, trades_lock, MAX_ACTIVE_TRADES, TRADING_CONFIG, CSV_FILE, current_trade_type, client, symbol
    start_time = time.time()
    max_retries = 5
    delay = 5
    with trades_lock:
        log_event(f"Пауза 5 секунд перед открытием новой сделки")
        time.sleep(5)
        if not TRADING_CONFIG[f'ENABLE_{trade_type}']:
            log_event(f"⚠️ Открытие {trade_type} отключено в конфигурации")
            return
        if len(active_trades) >= MAX_ACTIVE_TRADES:
            log_event("⚠️ Достигнут лимит активных сделок")
            return
        available_balance = get_available_balance()
        log_event(f" Доступный баланс: {available_balance}")
        if position_value is None:
            if trade_type in TRADING_CONFIG:
                position_value = (available_balance * TRADING_CONFIG[trade_type]['ENTRY_PERCENT']) / 100
            else:
                log_event(f"⚠️ Неизвестный тип сделки: {trade_type}")
                return
        # Retry для получения информации о символе
        for attempt in range(max_retries):
            try:
                symbol_info = client.get_instruments_info(category="linear", symbol=symbol)
                if symbol_info['retCode'] != 0:
                    raise ValueError(f"Ошибка API: {symbol_info['retMsg']}")
                instrument = symbol_info['result']['list'][0]
                qty_step = float(instrument['lotSizeFilter']['qtyStep'])
                precision = int(round(-math.log(qty_step, 10), 0))
                break
            except Exception as e:
                log_event(f"⚠️ Ошибка получения информации о символе (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))
                else:
                    log_event("⚠️ Не удалось получить информацию о символе")
                    return
        leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE', 1)
        log_event(f"Плечо для {trade_type}: {leverage}x")
        # Retry для установки плеча
        for attempt in range(max_retries):
            try:
                position_response = client.get_positions(category="linear", symbol=symbol)
                if position_response['retCode'] == 0 and position_response['result']['list']:
                    current_leverage = float(position_response['result']['list'][0]['leverage'])
                    if current_leverage == leverage:
                        log_event(f"✅ Плечо уже установлено на {leverage}x")
                    else:
                        client.set_leverage(
                            category="linear",
                            symbol=symbol,
                            buyLeverage=str(leverage),
                            sellLeverage=str(leverage)
                        )
                        log_event(f"✅ Плечо установлено на {leverage}x для {trade_type}")
                else:
                    client.set_leverage(
                        category="linear",
                        symbol=symbol,
                        buyLeverage=str(leverage),
                        sellLeverage=str(leverage)
                    )
                    log_event(f"✅ Плечо установлено на {leverage}x для {trade_type}")
                break
            except Exception as e:
                if "leverage not modified" in str(e):
                    log_event(f"⚠️ Плечо не изменено, так как уже установлено на {leverage}x")
                    break
                else:
                    log_event(f"⚠️ Ошибка установки плеча (попытка {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))
                    else:
                        log_event("⚠️ Не удалось установить плечо")
                        return
        min_order_qty = float(instrument['lotSizeFilter']['minOrderQty'])
        current_price = get_current_price_with_retries(client, symbol)
        amount_btc = ((position_value * leverage) / current_price) * 0.9
        amount_btc = math.floor(amount_btc * (10 ** precision)) / (10 ** precision)
        log_event(f"Размер ордера: {amount_btc} BTC")
        if amount_btc < min_order_qty:
            log_event(f"⚠️ Объем сделки {amount_btc:.6f} BTC меньше минимального {min_order_qty} BTC")
            return
        if 'LONG' in trade_type:
            side = 'Buy'
        elif 'SHORT' in trade_type:
            side = 'Sell'
        else:
            log_event(f"⚠️ Неизвестный тип сделки: {trade_type}")
            return
        # Retry для размещения ордера
        for attempt in range(max_retries):
            try:
                order = client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=side,
                    orderType="Market",
                    qty=str(amount_btc),
                    reduceOnly=False,
                    marginMode="ISOLATED"
                )
                if order['retCode'] != 0:
                    raise ValueError(f"Ошибка API: {order['retMsg']}")
                log_event(f"✅ Ордер успешно размещен: {order}")
                break
            except Exception as e:
                log_event(f"⚠️ Ошибка размещения ордера (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))
                else:
                    log_event("⚠️ Не удалось разместить ордер")
                    return
        current_trade_id = next_trade_id
        next_trade_id += 1
        entry_time = get_server_time()
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
            df_trades = df_trades.tail(30)
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
        current_time = get_server_time()
        log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_fear_greed_value, get_available_balance)
        display_position()




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
    

def set_leverage(symbol, leverage, direction):
    try:
        response = client.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage)
        )
        if response['retCode'] != 0:
            raise ValueError(f"Ошибка API: {response['retMsg']}")
        log_event(f"✅ Плечо установлено на {leverage:.2f}x для {direction}")
        time.sleep(6)
    except Exception as e:
        log_event(f"⚠️ Размер плеча минимальный")
        log_event(f"Пауза 5 секунд для пересчета цены ликвидации")
        time.sleep(5)
        manage_liquidation_price()


def adjust_leverage_after_partial_close(direction, min_delta):
    global client, symbol, MIN_DELTA_LIQUIDATION_LONG, MIN_DELTA_LIQUIDATION_SHORT
    # Получаем текущие данные о позиции
    position_response = client.get_positions(category="linear", symbol=symbol)
    if position_response['retCode'] != 0:
        log_event(f"⚠️ Ошибка API: {position_response['retMsg']}")
        return
    positions = position_response['result']['list']
    if not positions:
        log_event("⚪ Нет активных позиций для управления рисками")
        return
    position = positions[0]
    current_leverage = float(position['leverage'])
    liq_price_str = position.get('liqPrice', '')
    if liq_price_str == '':
        log_event("⚪ Нет цены ликвидации")
        return
    liquidation_price = float(liq_price_str)
    # Получаем текущую рыночную цену
    current_price = get_current_price_with_retries(client, symbol)
    # Рассчитываем дельту маржи
    if direction == 'LONG':
        delta_percent = (current_price - liquidation_price) / current_price * 100
    else:
        delta_percent = (liquidation_price - current_price) / current_price * 100
    log_event(f"Текущая дельта: {delta_percent:.2f}% (минимальная: {min_delta}%)")
    # Устанавливаем минимальное плечо (обычно 1x на Bybit)
    min_leverage = 1.0
    leverage_step = 0.6 # Шаг уменьшения плеча
    # Цикл уменьшения плеча
    while delta_percent < min_delta and current_leverage > min_leverage:
        new_leverage = max(current_leverage - leverage_step, min_leverage)
        set_leverage(symbol, new_leverage, direction)
        time.sleep(2) # Пауза для обновления данных на бирже
        # Обновляем данные о позиции
        position_response = client.get_positions(category="linear", symbol=symbol)
        if position_response['retCode'] != 0:
            log_event(f"⚠️ Ошибка API: {position_response['retMsg']}")
            break
        positions = position_response['result']['list']
        if not positions:
            log_event("⚪ Позиция закрыта")
            break
        position = positions[0]
        current_leverage = float(position['leverage'])
        liq_price_str = position.get('liqPrice', '')
        if liq_price_str == '':
            log_event("⚪ Нет цены ликвидации после обновления")
            break
        liquidation_price = float(liq_price_str)
        # Пересчитываем дельту
        if direction == 'LONG':
            delta_percent = (current_price - liquidation_price) / current_price * 100
        else:
            delta_percent = (liquidation_price - current_price) / current_price * 100
        log_event(f"Новое плечо: {current_leverage}x, новая дельта: {delta_percent:.2f}%")
        if delta_percent >= min_delta:
            log_event(f"✅ Дельта достигла {delta_percent:.2f}%, что >= {min_delta}%. Остановка уменьшения плеча.")
            break
        elif current_leverage <= min_leverage:
            log_event(f"⚠️ Плечо достигло минимального значения {min_leverage}x, но дельта все еще {delta_percent:.2f}% < {min_delta}%.")
            break


def close_all_trades(reason, exit_time=None, force_close=False, position_value=None):
    global df_trades, active_trades, trades_lock, TRADING_CONFIG, CSV_FILE, bull_long_trades_count, current_trade_type, client, symbol, current_market_type
    start_time = time.time()
    trades_to_close = []
    max_retries = 5
    delay = 5
    with trades_lock:
        if not active_trades:
            log_event("⚪ Нет активных сделок для закрытия")
            return
        if exit_time is None:
            exit_time = get_server_time()
        exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        current_price = get_current_price_with_retries(client, symbol)
        # Retry для получения текущих позиций
        for attempt in range(max_retries):
            try:
                position_response = client.get_positions(category="linear", symbol=symbol)
                if position_response['retCode'] != 0:
                    raise ValueError(f"Ошибка API: {position_response['retMsg']}")
                positions = position_response['result']['list']
                if not positions:
                    log_event("⚪ Нет активных позиций для закрытия")
                    return
                position = positions[0]
                size = float(position['size'])
                side = position['side']
                direction = 'LONG' if side == 'Buy' else 'SHORT'
                break
            except Exception as e:
                log_event(f"⚠️ Ошибка получения позиции (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))
                else:
                    log_event("⚠️ Не удалось получить данные позиции")
                    return
        symbol_info = get_symbol_info(symbol)
        if symbol_info is None:
            log_event("⚠️ Не удалось получить информацию о символе")
            return
        min_order_qty = symbol_info['min_order_qty']
        precision = symbol_info['precision']
        if position_value is not None:
            amount_to_close = min(position_value, size)
            if amount_to_close < min_order_qty:
                amount_to_close = min_order_qty
            amount_to_close = math.floor(amount_to_close * (10 ** precision)) / (10 ** precision)
            amount_to_close = min(amount_to_close, size)
            log_event(f"Частичное закрытие {direction}: объем {amount_to_close:.8f} BTC")
        else:
            amount_to_close = size
            log_event(f"Полное закрытие {direction}: объем {amount_to_close:.8f} BTC")
        close_side = 'Sell' if direction == 'LONG' else 'Buy'
        # Retry для размещения ордера на закрытие
        for attempt in range(max_retries):
            try:
                order = client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    orderType="Market",
                    qty=str(amount_to_close),
                    reduceOnly=True
                )
                if order['retCode'] != 0:
                    raise ValueError(f"Ошибка API: {order['retMsg']}")
                log_event(f"✅ Ордер на закрытие успешно размещен: {order}")
                break
            except Exception as e:
                log_event(f"⚠️ Ошибка закрытия позиции (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))
                else:
                    log_event("⚠️ Не удалось закрыть позицию")
                    return
        # Пауза для исполнения ордера на бирже
        time.sleep(2)
        # Получаем актуальный остаток позиции напрямую с биржи
        for attempt in range(max_retries):
            try:
                position_response = client.get_positions(category="linear", symbol=symbol)
                if position_response['retCode'] != 0:
                    raise ValueError(f"Ошибка API: {position_response['retMsg']}")
                positions = position_response['result']['list']
                if not positions:
                    new_size = 0.0
                else:
                    new_size = float(positions[0]['size'])
                break
            except Exception as e:
                log_event(f"⚠️ Ошибка получения обновленной позиции (попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (2 ** attempt))
                else:
                    log_event("⚠️ Не удалось получить обновленные данные позиции")
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
                # Обновляем trade['size'] на основе данных с биржи
                if new_size > 0:
                    trade['size'] = new_size
                    log_event(f"Оставшийся размер позиции: {new_size:.8f} BTC")
                    if trade.get('value') is not None:
                        trade['value'] *= (new_size / size)
                        trade['commission_open'] -= commission_open * (amount_to_close / size)
                    min_delta = MIN_DELTA_LIQUIDATION_LONG if direction == 'LONG' else MIN_DELTA_LIQUIDATION_SHORT
                    adjust_leverage_after_partial_close(direction, min_delta)
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
            log_event("🔄 Все сделки закрыты. Счетчики активных сделок сброшены.")
    if TRADING_CONFIG['ENABLE_LOGGING'] and CSV_FILE is not None:
        if df_trades is None:
            df_trades = pd.DataFrame(columns=[
                'Trade_ID', 'Status', 'Direction', 'Entry_Time', 'Exit_Time', 'Trade_Duration', 'Hours',
                'Entry_Price', 'Exit_Price', 'Position_Size', 'Position_Value',
                'Leverage', 'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'Withdraw'
            ])
            df_trades['Entry_Time'] = pd.Series(dtype='datetime64[ns, UTC]')
            df_trades['Exit_Time'] = pd.Series(dtype='datetime64[ns, UTC]')
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
                if position_value is not None and new_size > 0:
                    open_row = df_trades.loc[mask].copy()
                    open_row['Status'] = 'open'
                    open_row['Position_Size'] = new_size
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
            df_trades = df_trades.tail(30)
        try:
            df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
            log_event(f"💾 История сделок обновлена в {CSV_FILE}")
        except Exception as e:
            log_event(f"⚠️ Ошибка при записи в CSV: {e}")
    # Пауза для обновления данных на бирже
    time.sleep(2)
    # Вызов отображения позиции после закрытия сделки
    current_time = get_server_time()
    log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_fear_greed_value, get_available_balance)
    display_position()



def display_position():
    with trades_lock:
        if not active_trades:
            log_event("⚪ Нет активных позиций")
            return
        try:
            position_response = client.get_positions(category="linear", symbol=symbol)
            if position_response['retCode'] != 0:
                log_event(f"⚠️ Ошибка API: {position_response['retMsg']}")
                return
            position = position_response['result']['list'][0]
            size = float(position['size'])
            side = position['side']
            entry_price = float(position['avgPrice'])
          
            # Обработка liquidation_price
            liq_price_str = position.get('liqPrice', '')
            if liq_price_str:
                try:
                    liquidation_price = float(liq_price_str)
                except ValueError:
                    log_event(f"⚠️ Ошибка преобразования 'liqPrice' в float: '{liq_price_str}'")
                    liquidation_price = None
            else:
                liquidation_price = None
          
            leverage = float(position['leverage'])
            realized_pnl = float(position.get('curRealisedPnl', 0))  # Реализованная прибыль
            unrealized_pnl = float(position.get('unrealisedPnl', 0))  # Нереализованная прибыль
            total_profit = realized_pnl + unrealized_pnl  # Текущая прибыль
            position_value = float(position.get('positionValue', 0)) # Стоимость позиции в USDT
            # Получаем текущую цену
            current_price = get_current_price_with_retries(client, symbol)
            # Определяем полное направление на основе рынка и side
            if current_market_type == 'bull':
                full_direction = 'BULL_LONG' if side == 'Buy' else 'BULL_SHORT'
            elif current_market_type == 'bear':
                full_direction = 'BEAR_LONG' if side == 'Buy' else 'BEAR_SHORT'
            else:
                full_direction = 'UNKNOWN'
            # Рассчитываем дельту
            delta_percent = None
            if current_price > 0 and liquidation_price is not None and liquidation_price > 0:
                if 'LONG' in full_direction:
                    delta_percent = (current_price - liquidation_price) / current_price * 100
                else:
                    delta_percent = (liquidation_price - current_price) / current_price * 100
            # Рассчитываем размер позиции в долларах
            size_usd = size * current_price
            # Определяем индикаторы для каждого типа прибыли
            realized_indicator = "🟢" if realized_pnl >= 0 else "🔴"
            unrealized_indicator = "🟢" if unrealized_pnl >= 0 else "🔴"
            total_indicator = "🟢" if total_profit >= 0 else "🔴"
            # Вывод информации
            log_event("----------------------------------------------|")
            log_event("--------------| ПОЗИЦИЯ НА BYBIT |------------|")
            log_event("----------------------------------------------|")
            log_event(f"{'💹' if 'LONG' in full_direction else '🔻'} {full_direction} | 💸 Вход: {entry_price:,.2f} USDT | Плечо: {leverage}x ")
            log_event(f"💰 Объем: {size:,.4f} BTC ({size_usd:,.2f} USDT)")
            if liquidation_price is not None:
                log_event(f"🔹 Ликвидация: {liquidation_price:,.2f} USDT | Дельта: {delta_percent:.2f}%" if delta_percent is not None else f"🔹 Ликвидация: {liquidation_price:,.2f} USDT | Дельта: --")
            else:
                log_event("🔹 Ликвидация: -- | Дельта: --")
            log_event(f"{realized_indicator} Реализованная прибыль: {realized_pnl:,.2f}$")
            log_event(f"{unrealized_indicator} Не реализованная прибыль: {unrealized_pnl:,.2f}$")
            log_event(f"{total_indicator} Текущая прибыль: {total_profit:,.2f}$")
            log_event("----------------------------------------------|")
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении данных о позиции BYBIT: {e}")


def run():
    global next_trade_id, fear_greed_data, next_rsi_update_time, current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi, next_analysis_time, previous_mid_price, last_price_indicator
    global current_stoch_k, current_stoch_d, previous_stoch_k, previous_stoch_d
    global current_williams_r_overbought, current_williams_r_oversold, previous_williams_r_overbought, previous_williams_r_oversold, next_global_update_time
    global last_fear_greed_update, last_market_type
    global current_market_type, next_market_change
    global TEST_MODE, TEST_MARKET_TYPE, TEST_NEXT_CHANGE
    # --- НЕ УДАЛЯТЬ ЭТОТ БЛОК ТЕСТИРОВАНИЯ!!! ---
    TEST_MODE = False  # Установите True / False для активации тестового режима
    # TEST_MARKET_TYPE = 'bull'  # Задайте тип рынка вручную ('bull' или 'bear')
    # TEST_NEXT_CHANGE = datetime(2025, 9, 29, 16, 44, 0, tzinfo=timezone.utc)  # Задайте дату и время смены рынка вручную
    # --- Конец блока тестового режима ---
    if TEST_MODE:
        log_event(f"🧪 Тестовый режим активен: Тип рынка = {TEST_MARKET_TYPE}, Смена = {TEST_NEXT_CHANGE}")
    setup_logging()
    calculate_market_periods(None)
    current_time = get_server_time()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_market_type = get_market_type(current_time)
    _, next_market_change = get_next_market_change_date(current_time)
    if current_market_type is not None:
        log_event(f"📈 Текущий тип рынка: {current_market_type}")
        if next_market_change is not None:
            log_event(f"🔄 Дата следующей смены рынка: {next_market_change.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            log_event("⚠️ Дата смены рынка не определена")
        initialize_market_data_file(current_market_type)
    else:
        log_event("⚠️ Тип рынка не определён при запуске, пропуск инициализации файла market_data")
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
    initialize_csv()
    sync_active_trades()
    current_price = get_current_price_with_retries(client, symbol)
    log_event(f"📈 Текущая цена: {current_price:.2f}")
    ###################################################################################################
    # НЕ УДАЛЯТЬ ЭТОТ БЛОК ТЕСТИРОВАНИЯ!!!
    # Тестировние входа и выхода из сделок
    # #Задаём размер позиции
    position_value = (get_available_balance() * TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']) / 100
    # open_trade('BULL_LONG', current_price, position_value)
    # log_event(f"Пауза 10 секунд перед закрытием")
    # time.sleep(10)
    # close_all_trades("rsi_down", force_close=True)
    # Открываем сделку 'BEAR_SHORT' для медвежьего рынка
    # open_trade('BEAR_SHORT', current_price, position_value)
    # log_event("Пауза 10 секунд перед закрытием")
    # time.sleep(10)
    # close_all_trades("rsi_up", force_close=True)
    ######### --- Конец блока тестового режима ---    
    # # Инициализация времени следующего обновления данных о сделках
    current_time = get_server_time()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    next_analysis_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)
    next_rsi_update_time = get_next_candle_end_time(current_time, GLOBAL_TIMEFRAME)
    next_global_update_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)
    # Обновление файла market_data.csv и пересчёт индикаторов при запуске, аналогично обновлению свечи
    update_market_data_on_candle_close(symbol, GLOBAL_TIMEFRAME, current_time)
    # Первоначальный расчет всех индикаторов из файла
    market_type = get_market_type(current_time)
    df_market = load_market_data(current_market_type)
    # Загрузка и сохранение данных индекса страха и жадности
    fear_greed_data = fetch_fear_greed_data()
    if not fear_greed_data:
        log_event("Не удалось получить данные индекса страха и жадности")
    # Загрузка данных индекса страха и жадности
    fear_greed_data = load_fear_greed_data()
    log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_fear_greed_value, get_available_balance)
    display_position()
    manage_liquidation_price()
    next_analysis_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)
    log_event("----------------------------------------------|")
    log_event(f"⏳ ({ANALYSIS_TIMEFRAME}) Обновление данных: {next_analysis_time}")
    last_market_type = current_market_type
    while True:
        try:
            current_time = get_server_time()
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
            if next_global_update_time is None or current_time >= next_global_update_time:
                current_price = get_current_price_with_retries(client, symbol)
                log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_fear_greed_value, get_available_balance)
                display_position()
                manage_liquidation_price()
                next_global_update_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)
                log_event("----------------------------------------------|")
                log_event(f"⏳ ({ANALYSIS_TIMEFRAME}) Обновление данных: {next_global_update_time}")
            # Проверка смены типа рынка только по времени смены
            if next_market_change and current_time >= next_market_change:
                log_event(f"🔄 Обнаружена смена рынка по времени на {current_time}")
                current_market_type = get_market_type(current_time)
                _, next_market_change = get_next_market_change_date(current_time)
                if last_market_type != current_market_type:
                    log_event(f"🔄 Смена типа рынка с {last_market_type} на {current_market_type}. Закрытие всех сделок.")
                    close_all_trades(f"market_type_change_to_{current_market_type}", force_close=True)
                    last_market_type = current_market_type
                    initialize_market_data_file(current_market_type)
                    update_market_data_on_candle_close(symbol, GLOBAL_TIMEFRAME, current_time)
                    df_market = load_market_data(current_market_type)
                    if not active_trades:
                        if current_market_type == 'bull':
                            position_value = (get_available_balance() * TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']) / 100
                            log_event(f"📈 Сигнал на открытие BULL_LONG по смене рынка")
                            open_trade('BULL_LONG', current_price, position_value)
                        elif current_market_type == 'bear':
                            position_value = (get_available_balance() * TRADING_CONFIG['BEAR_SHORT']['ENTRY_PERCENT']) / 100
                            log_event(f"📉 Сигнал на открытие BEAR_SHORT по смене рынка")
                            open_trade('BEAR_SHORT', current_price, position_value)
            if next_rsi_update_time is None or current_time >= next_rsi_update_time:
                current_price = get_current_price_with_retries(client, symbol)
                update_market_data_on_candle_close(symbol, GLOBAL_TIMEFRAME, current_time)
                df_market = load_market_data(current_market_type)
                fear_greed_data = fetch_fear_greed_data()
                if not fear_greed_data:
                    log_event("Не удалось получить данные индекса страха и жадности")
                fear_greed_data = load_fear_greed_data()
                if current_rsi is not None and current_sma_rsi is not None and current_stoch_k is not None and current_stoch_d is not None and current_williams_r_overbought is not None and current_williams_r_oversold is not None:
                    check_signals(current_price)
                    log_market_data(current_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_fear_greed_value, get_available_balance)
                    display_position()
                    manage_liquidation_price()
                next_rsi_update_time = get_next_candle_end_time(current_time, GLOBAL_TIMEFRAME)
                log_event("----------------------------------------------|")
                log_event(f"⏳ ({GLOBAL_TIMEFRAME}) Обновление свечи: {next_rsi_update_time}")
                # Лог текущего типа и смены без повторного вызова
                if current_market_type and next_market_change:
                    log_event(f"🔄 Тип рынка: {current_market_type}, смена: {next_market_change.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                else:
                    log_event("⚠️ Не удалось определить тип рынка или дату смены")
            time_to_next_analysis = (next_global_update_time - current_time).total_seconds()
            time_to_next_global = (next_rsi_update_time - current_time).total_seconds()
            time_to_next = min(time_to_next_analysis, time_to_next_global)
            time.sleep(max(time_to_next, 1))
        except Exception as e:
            log_event(f"⚠️ Ошибка в основном цикле: {e}")
            time.sleep(2)


if __name__ == "__main__":
    try:
        initialize_csv()
        run()
    except Exception as e:
        error_msg = f"Ошибка выполнения скрипта: {e}"
        log_event(error_msg)
        with open(f"error_log_{script_name}.txt", "a", encoding='utf-8') as f:
            f.write(f"{datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')} | {error_msg}\n")
        raise


# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 
# Пиши каждую функцию кода в отдельном блоке для удобного копирования, перед каждым блоком конкретное описание изменений в коде
# Свое описание пиши строго за границами блока с кодом
# Используй только официальные библиотеки pybit Version: 5.10.1
