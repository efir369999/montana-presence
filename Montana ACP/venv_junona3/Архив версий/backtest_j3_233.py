



# backtest_j3_232


import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
import logging
import math
import threading
from pathlib import Path
import pytz
import re
import requests
import csv
import time
import sys
from datetime import datetime, timedelta
import time
import numpy as np
from itertools import product
import locale



# Глобальные переменные для бэктеста
INITIAL_BALANCE = 10000.0
current_balance = INITIAL_BALANCE
SYMBOL = 'BTCUSDT'
active_trades = {}
trades_history = []
previous_rsi = None
previous_sma_rsi = None
current_rsi = None
current_sma_rsi = None
next_trade_id = 1
trades_lock = threading.RLock()
current_trade_type = None
pending_action = None
pending_fear_greed = None  # Добавлена для хранения значения индекса страха на момент сигнала
fear_greed_data = None # Добавлена для индекса страха
previous_stoch_k = None
previous_stoch_d = None
current_stoch_k = None
current_stoch_d = None
previous_williams_r_overbought = None # Переименовано для ясности (ранее previous_williams_r)
current_williams_r_overbought = None # Переименовано (ранее current_williams_r)
previous_williams_r_oversold = None # Новый: для oversold
current_williams_r_oversold = None # Новый: для oversold
df_trades = None
last_market_type = None
pending_market_change_time = None 
market_periods_model1 = []
market_periods_model2 = []


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

GLOBAL_TIMEFRAME = '1w'
DATA_FILE = Path("1W_2009_2025.csv")



TRADING_CONFIG = { # True / False
    'ENABLE_BULL_LONG': True,
    'ENABLE_BULL_SHORT': False,
    'ENABLE_BEAR_SHORT': True,
    'ENABLE_BEAR_LONG': True,
    'COMMISSION_RATE': 0.05 / 100,
    'ENABLE_LOGGING': True,
    'BULL_LONG': {'LEVERAGE': 1.0, 'ENTRY_PERCENT': 99},
    'BULL_SHORT': {'LEVERAGE': 1.0, 'ENTRY_PERCENT': 99},
    'BEAR_SHORT': {'LEVERAGE': 1.0, 'ENTRY_PERCENT': 99},
    'BEAR_LONG': {'LEVERAGE': 1.0, 'ENTRY_PERCENT': 99},
    'MIN_DELTA_LIQUIDATION_LONG': 10.0,
    'MIN_DELTA_LIQUIDATION_SHORT': 10.0,
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


# Параметры для bull
BULL_RSI_PERIOD = 20
BULL_SMA_RSI_PERIOD = 40
BULL_STOCHRSI_K_PERIOD = 18 
BULL_STOCHRSI_D_PERIOD = 29
BULL_STOCHRSI_RSI_PERIOD = 20 
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



# Cycle 2 - 4 total
BACKTEST_START_DATE = datetime(2015, 1, 12, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
BACKTEST_END_DATE = datetime(2025, 9, 1, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона

# Cycle 2 bull
# BACKTEST_START_DATE = datetime(2015, 1, 12, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2017,12, 18, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона

# Cycle 2 bear
# BACKTEST_START_DATE = datetime(2017, 12, 18, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2018,12, 24, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона


# Cycle 3 bull
# BACKTEST_START_DATE = datetime(2018, 12, 10, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2021, 11, 15, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона

# Cycle 3 bear
# BACKTEST_START_DATE = datetime(2021, 11, 15, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2022, 11, 14, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона


# Cycle 4 bull
# BACKTEST_START_DATE = datetime(2022, 11, 8, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2026,11, 7, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона


ENABLE_OPTIMIZATION = False  # True / False


# Параметры оптимизации для bull
BULL_RSI_MIN = 20
BULL_RSI_MAX = 20
BULL_RSI_STEP = 1
BULL_SMA_MIN = 40
BULL_SMA_MAX = 40
BULL_SMA_STEP = 1

BULL_STOCHRSI_K_MIN = 18
BULL_STOCHRSI_K_MAX = 18
BULL_STOCHRSI_K_STEP = 1
BULL_STOCHRSI_D_MIN = 29
BULL_STOCHRSI_D_MAX = 29
BULL_STOCHRSI_D_STEP = 1
BULL_STOCHRSI_RSI_MIN = 20
BULL_STOCHRSI_RSI_MAX = 20
BULL_STOCHRSI_RSI_STEP = 1
BULL_STOCHRSI_STOCH_MIN = 20
BULL_STOCHRSI_STOCH_MAX = 20
BULL_STOCHRSI_STOCH_STEP = 1

BULL_WILLIAMS_OVERBOUGHT_PERIOD_MIN = 14
BULL_WILLIAMS_OVERBOUGHT_PERIOD_MAX = 14
BULL_WILLIAMS_OVERBOUGHT_PERIOD_STEP = 1
BULL_WILLIAMS_OVERBOUGHT_LEVEL_MIN = -1.0
BULL_WILLIAMS_OVERBOUGHT_LEVEL_MAX = -1.0
BULL_WILLIAMS_OVERBOUGHT_LEVEL_STEP = 1

BULL_WILLIAMS_OVERSOLD_PERIOD_MIN = 20
BULL_WILLIAMS_OVERSOLD_PERIOD_MAX = 20
BULL_WILLIAMS_OVERSOLD_PERIOD_STEP = 1
BULL_WILLIAMS_OVERSOLD_LEVEL_MIN = -84.8
BULL_WILLIAMS_OVERSOLD_LEVEL_MAX = -84.8
BULL_WILLIAMS_OVERSOLD_LEVEL_STEP = 1

BULL_FEAR_GREED_LOW_MIN = 9
BULL_FEAR_GREED_LOW_MAX = 9
BULL_FEAR_GREED_LOW_STEP = 1



# Параметры оптимизации для bear
BEAR_RSI_MIN = 16
BEAR_RSI_MAX = 16
BEAR_RSI_STEP = 1
BEAR_SMA_MIN = 11
BEAR_SMA_MAX = 11
BEAR_SMA_STEP = 1

BEAR_STOCHRSI_K_MIN = 15
BEAR_STOCHRSI_K_MAX = 15
BEAR_STOCHRSI_K_STEP = 1
BEAR_STOCHRSI_D_MIN = 5
BEAR_STOCHRSI_D_MAX = 5
BEAR_STOCHRSI_D_STEP = 1
BEAR_STOCHRSI_RSI_MIN = 14
BEAR_STOCHRSI_RSI_MAX = 14
BEAR_STOCHRSI_RSI_STEP = 1
BEAR_STOCHRSI_STOCH_MIN = 14
BEAR_STOCHRSI_STOCH_MAX = 14
BEAR_STOCHRSI_STOCH_STEP = 1

BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MIN = 6
BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MAX = 6
BEAR_WILLIAMS_OVERBOUGHT_PERIOD_STEP = 1
BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MIN = -18.0
BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MAX = -18.0
BEAR_WILLIAMS_OVERBOUGHT_LEVEL_STEP = 1

BEAR_WILLIAMS_OVERSOLD_PERIOD_MIN = 17
BEAR_WILLIAMS_OVERSOLD_PERIOD_MAX = 17
BEAR_WILLIAMS_OVERSOLD_PERIOD_STEP = 1
BEAR_WILLIAMS_OVERSOLD_LEVEL_MIN = -91.0
BEAR_WILLIAMS_OVERSOLD_LEVEL_MAX = -91.0
BEAR_WILLIAMS_OVERSOLD_LEVEL_STEP = 1


BEAR_FEAR_GREED_HIGH_MIN = 52
BEAR_FEAR_GREED_HIGH_MAX = 52
BEAR_FEAR_GREED_HIGH_STEP = 2





# Константы для определения циклов рынка
START_DATE = datetime(2015, 1, 12, tzinfo=pytz.UTC)  # Начальная дата, теперь tz-aware
CYCLE_LENGTH = 1428  # Длина цикла в днях (152 недели бычьего + 52 недели медвежьего = 204 недели)
BULL_DAYS = 1064  # Длина бычьего рынка в днях (152 недели * 7 дней)



def model1_get_market_type(date):
    if date.tzinfo is None:
        date = date.replace(tzinfo=pytz.UTC)
    delta = date - START_DATE
    delta_days = delta.days
    if delta_days < 0:
        return None
    cycle_position = delta_days % CYCLE_LENGTH
    if cycle_position < BULL_DAYS:
        market = 'bull'
    else:
        market = 'bear'
    if (market == 'bull' and TRADING_CONFIG.get('ENABLE_BULL_MARKET', True)) or \
       (market == 'bear' and TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True)):
        return market
    else:
        return None


def model1_calculate_periods(df):
    global market_periods_model1
    market_periods_model1 = []
    current_date = START_DATE
    cycle_num = 1
    while current_date < df.index[-1] + timedelta(days=CYCLE_LENGTH):
        # Bull период: BULL_DAYS дней
        bull_end = current_date + timedelta(days=BULL_DAYS)
        # Корректировка на понедельник для начала
        weekday = current_date.weekday()
        if weekday != 0:
            days_to_monday = 7 - weekday
            current_date += timedelta(days=days_to_monday)
        market_periods_model1.append({'cycle': cycle_num, 'type': 'bull', 'start': current_date, 'change': bull_end})
        # Bear период: остаток цикла
        bear_end = bull_end + timedelta(days=CYCLE_LENGTH - BULL_DAYS)
        market_periods_model1.append({'cycle': cycle_num, 'type': 'bear', 'start': bull_end, 'change': bear_end})
        current_date = bear_end
        cycle_num += 1
    # Вывод в логи для модели 1
    for period in market_periods_model1:
        end = period['change'] - timedelta(days=7)
        type_en = period['type']
        start_str = period['start'].strftime('%d %B %Y')
        end_str = end.strftime('%d %B %Y')
        change_str = period['change'].strftime('%d %B %Y')
        logger.info(f"Model1: {type_en} {period['cycle']} ({start_str} - {end_str}) смена {change_str}")



def model2_get_market_type(date):
    if date.tzinfo is None:
        date = date.replace(tzinfo=pytz.UTC)
    for period in market_periods_model2:
        if period['start'] <= date < period['change']:
            market = period['type']
            if (market == 'bull' and TRADING_CONFIG.get('ENABLE_BULL_MARKET', True)) or \
               (market == 'bear' and TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True)):
                return market
            else:
                return None
    return None


def model2_calculate_periods(df):
    global market_periods_model2
    halvings = [
        datetime(2012, 11, 28, 15, 24, 38, tzinfo=pytz.UTC),
        datetime(2016, 7, 9, 16, 46, 13, tzinfo=pytz.UTC),
        datetime(2020, 5, 11, 19, 23, 43, tzinfo=pytz.UTC),
        datetime(2024, 4, 20, 0, 9, 27, tzinfo=pytz.UTC),
    ]
    market_periods_model2 = []
    for idx in range(1, len(halvings)):
        cycle = idx + 1
        halving = halvings[idx]
        weekday = halving.weekday()
        if weekday == 0:
            monday_after = halving.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            days_to_monday = 7 - weekday
            monday_after = (halving + timedelta(days=days_to_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            i_halving = df.index.get_loc(monday_after)
        except KeyError:
            logger.warning(f"Понедельник после халвинга {monday_after} не найден в данных, пропуск цикла {cycle}")
            continue
        i_74 = i_halving - 74
        i_78 = i_halving - 78
        if i_74 < 0 or i_78 < 0:
            logger.warning(f"Индексы за пределами данных для цикла {cycle}, пропуск")
            continue
        low_74 = df.iloc[i_74]['low']
        low_78 = df.iloc[i_78]['low']
        if low_74 < low_78:
            bottom_i = i_74
        else:
            bottom_i = i_78
        bottom_date = df.index[bottom_i]
        peak_date = bottom_date + timedelta(weeks=152)
        change_to_bear = peak_date + timedelta(weeks=1)
        bear_change = change_to_bear + timedelta(weeks=52)
        market_periods_model2.append({'cycle': cycle, 'type': 'bull', 'start': bottom_date, 'change': change_to_bear})
        market_periods_model2.append({'cycle': cycle, 'type': 'bear', 'start': change_to_bear, 'change': bear_change})
    if market_periods_model2:
        market_periods_model2.insert(0, {'cycle': 1, 'type': 'bear', 'start': datetime(2013, 11, 25, tzinfo=pytz.UTC), 'change': market_periods_model2[0]['start']})
    for period in market_periods_model2:
        end = period['change'] - timedelta(days=7)
        type_en = period['type']
        start_str = period['start'].strftime('%d %B %Y')
        end_str = end.strftime('%d %B %Y')
        change_str = period['change'].strftime('%d %B %Y')
        logger.info(f"Model2: {type_en} {period['cycle']} ({start_str} - {end_str}) смена {change_str}")



def hybrid_get_market_type_and_changes(date):
    type1 = model1_get_market_type(date)
    type2 = model2_get_market_type(date)
    if type1 == type2 and type1 is not None:
        current_type = type1
    else:
        current_type = None
    # Нахождение даты смены для модели 1
    change1 = None
    for period in market_periods_model1:
        if period['start'] <= date < period['change']:
            change1 = period['change']
            break
    # Нахождение даты смены для модели 2
    change2 = None
    for period in market_periods_model2:
        if period['start'] <= date < period['change']:
            change2 = period['change']
            break
    if change1 is None or change2 is None:
        return current_type, None, None
    close_change_date = min(change1, change2)
    open_change_date = max(change1, change2)
    if change1 == change2:
        open_change_date = close_change_date + timedelta(days=7)
    return current_type, close_change_date, open_change_date


def reset_globals():
    global current_balance, active_trades, trades_history, previous_rsi, previous_sma_rsi, current_rsi, current_sma_rsi, next_trade_id, current_trade_type, pending_action, df_trades, last_market_type, fear_greed_data
    global previous_stoch_k, previous_stoch_d, current_stoch_k, current_stoch_d
    global previous_williams_r_overbought, current_williams_r_overbought # Переименовано
    global previous_williams_r_oversold, current_williams_r_oversold # Добавлено
    current_balance = INITIAL_BALANCE
    active_trades = {}
    trades_history = []
    previous_rsi = None
    previous_sma_rsi = None
    current_rsi = None
    current_sma_rsi = None
    previous_stoch_k = None
    previous_stoch_d = None
    current_stoch_k = None
    current_stoch_d = None
    previous_williams_r_overbought = None # Переименовано
    current_williams_r_overbought = None # Переименовано
    previous_williams_r_oversold = None # Добавлено
    current_williams_r_oversold = None # Добавлено
    next_trade_id = 1
    current_trade_type = None
    pending_action = None
    df_trades = None
    last_market_type = None
    fear_greed_data = None # Добавлена инициализация



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
            return data
        except requests.RequestException as e:
            logger.error(f"⚠️ Ошибка при запросе данных (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                logger.error("⚠️ Не удалось получить данные индекса после всех попыток")
                return []


def load_fear_greed_data():
    """
    Загружает данные индекса страха и жадности из файла fear_greed_index.csv.
    """
    global fear_greed_data
    fear_greed_file = Path("fear_greed_index.csv")
    current_date = datetime(2025, 9, 1, tzinfo=pytz.UTC).date()  # Фиксированная текущая дата из контекста

    need_fetch = True
    if fear_greed_file.exists():
        try:
            fear_greed_data = pd.read_csv(fear_greed_file, parse_dates=['Date'], dayfirst=True)
            fear_greed_data['Date'] = pd.to_datetime(fear_greed_data['Date'], format='%d/%m/%Y', errors='coerce')
            fear_greed_data['Date'] = fear_greed_data['Date'].dt.tz_localize('UTC')  # Добавлено для tz-aware в UTC
            if not fear_greed_data.empty:
                max_date = fear_greed_data['Date'].max().date()
                if max_date >= current_date:
                    need_fetch = False
                    logger.info("Данные индекса страха и жадности актуальны, загрузка из файла")
                else:
                    logger.info("Данные индекса страха и жадности неактуальны, выполняется обновление")
            else:
                logger.info("Файл существует, но пуст, выполняется fetch")
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных индекса страха: {e}")
            fear_greed_data = pd.DataFrame(columns=['Date', 'Value', 'Classification'])

    if need_fetch:
        fetch_fear_greed_data()
        # Перезагрузка после fetch
        if fear_greed_file.exists():
            try:
                fear_greed_data = pd.read_csv(fear_greed_file, parse_dates=['Date'], dayfirst=True)
                fear_greed_data['Date'] = pd.to_datetime(fear_greed_data['Date'], format='%d/%m/%Y', errors='coerce')
                fear_greed_data['Date'] = fear_greed_data['Date'].dt.tz_localize('UTC')
                logger.info("Данные индекса страха и жадности обновлены и загружены")
            except Exception as e:
                logger.error(f"Ошибка при перезагрузке данных после fetch: {e}")
                fear_greed_data = pd.DataFrame(columns=['Date', 'Value', 'Classification'])
        else:
            logger.error("Файл fear_greed_index.csv не создан после fetch, создан пустой DataFrame")
            fear_greed_data = pd.DataFrame(columns=['Date', 'Value', 'Classification'])

    fear_greed_data = fear_greed_data.sort_values(by='Date')
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
        # Для таймфрейма > 1 дня определяем дату начала предыдущей свечи
        target_date = date - timedelta(days=timeframe_days)
        # Корректируем дату на понедельник
        days_to_monday = target_date.weekday() # 0 = понедельник, 6 = воскресенье
        if days_to_monday != 0:
            target_date = target_date - timedelta(days=days_to_monday)
    # Приводим дату к началу дня (00:00:00)
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    # Ищем данные строго за target_date
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


def load_data():
    """ Загружает исторические данные """
    try:
        if not DATA_FILE.exists():
            logger.error(f"Файл данных {DATA_FILE} не найден!")
            raise FileNotFoundError(f"Файл {DATA_FILE} не найден")
        df = pd.read_csv(DATA_FILE)
        df['time'] = pd.to_datetime(df['time'], utc=True)  # Явно указываем UTC
        df.set_index('time', inplace=True)
        df = df.sort_index()  # Обеспечиваем хронологический порядок
        return df
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        return None



def check_rsi_crossing(current_rsi, current_sma_rsi):
    """
    Проверяет пересечение RSI и SMA RSI.
    """
    global previous_rsi, previous_sma_rsi
    if previous_rsi is None or previous_sma_rsi is None:
        return None
    if previous_rsi > previous_sma_rsi and current_rsi < current_sma_rsi:
        return "down"
    elif previous_rsi < previous_sma_rsi and current_rsi > current_sma_rsi:
        return "up"
    return None




def check_stoch_crossing(current_k, current_d):
    """
    Проверяет пересечение %K и %D Stochastic RSI.
    """
    global previous_stoch_k, previous_stoch_d
    if previous_stoch_k is None or previous_stoch_d is None:
        return None
    if previous_stoch_k > previous_stoch_d and current_k < current_d:
        return "down"
    elif previous_stoch_k < previous_stoch_d and current_k > current_d:
        return "up"
    return None





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



def simulate_open_trade(trade_type, entry_price, entry_time, reason_open):
    """
    Симулирует открытие торговой позиции.
    """
    global next_trade_id, active_trades, current_balance, current_trade_type, df_trades
    with trades_lock:
        try:
            if len(active_trades) >= TRADING_CONFIG['MAX_ACTIVE_TRADES']:
                logger.warning("Достигнут лимит активных сделок")
                return
            # Получение индивидуального процента входа для типа сделки
            entry_percent = TRADING_CONFIG[trade_type].get('ENTRY_PERCENT', 100)
            # Расчёт объёма позиции на основе текущего баланса
            position_value = (current_balance * entry_percent / 100)
            # Проверка на достаточность баланса
            if position_value <= 0 or current_balance < 100:
                logger.warning(f"Недостаточный баланс: {current_balance:.2f} USDT, сделка отклонена")
                return
            leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE', 1.0)
            size = (position_value * leverage) / entry_price
            # Проверка на корректность size
            if size <= 0:
                logger.warning(f"Некорректное количество BTC: {size:.6f}, сделка отклонена")
                return
            commission_open = (size * entry_price) * TRADING_CONFIG['COMMISSION_RATE']
            # Проверка на достаточность баланса для маржи и комиссии
            if current_balance < position_value + commission_open:
                logger.warning(f"Недостаточно средств для маржи и комиссии: {position_value + commission_open:.2f} USDT, сделка отклонена")
                return
            trade_id = next_trade_id
            next_trade_id += 1
            # Убедимся, что entry_time tz-aware
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=pytz.UTC)
            trade = {
                'id': trade_id,
                'direction': trade_type,
                'entry_price': entry_price,
                'entry_time': entry_time,
                'position_size': size,
                'position_value': position_value,
                'leverage': leverage,
                'commission_open': commission_open,
                'status': 'open'
            }
            active_trades[trade_id] = trade
            current_trade_type = trade_type
            current_balance -= position_value + commission_open
            logger.info(
                f"Открыта сделка {trade_type}: ID={trade_id}, Цена входа={entry_price:.2f}, "
                f"Размер={size:.6f} BTC, Маржа={position_value:.2f} USDT (процент входа={entry_percent}%), "
                f"Баланс после открытия={current_balance:.2f} USDT"
            )
            # Получаем значение индекса страха при открытии
            fear_greed_value = get_fear_greed_value(entry_time)
            # Добавление записи в df_trades при открытии с динамическими ключами
            new_row = {
                'Trade_ID': str(trade_id),
                'Direction': trade_type,
                'Reason_Open': reason_open,
                'Entry_Time': entry_time,
                'Reason_Close': np.nan,
                'Exit_Time': pd.NaT,
                'Trade_Duration': '',
                'Hours': np.nan,
                'Entry_Price': float(entry_price),
                'Exit_Price': np.nan,
                'Position_Size': float(size),
                'Position_Value': float(position_value),
                'Leverage': float(leverage),
                'Net_PnL_USDT': np.nan,
                'Net_PnL_Percent': np.nan,
                'Drawdown_USDT': np.nan,
                'Drawdown_Percent': np.nan,
                'Balance': float(current_balance),
                'PnL_Type': np.nan
            }
            # Добавление индикаторных ключей только если соответствующие колонки существуют (т.е. индикатор включен)
            if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_RSI']) or \
               (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_RSI']):
                new_row.update({
                    'Entry_RSI': float(current_rsi) if current_rsi is not None else np.nan,
                    'Entry_SMA_RSI': float(current_sma_rsi) if current_sma_rsi is not None else np.nan,
                    'Exit_RSI': np.nan,
                    'Exit_SMA_RSI': np.nan
                })
            if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or \
               (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
                new_row.update({
                    'Entry_Stoch_K': float(current_stoch_k) if current_stoch_k is not None else np.nan,
                    'Entry_Stoch_D': float(current_stoch_d) if current_stoch_d is not None else np.nan,
                    'Exit_Stoch_K': np.nan,
                    'Exit_Stoch_D': np.nan
                })
            if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']) or \
               (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']):
                new_row.update({
                    'Entry_Williams_R_Overbought': float(current_williams_r_overbought) if current_williams_r_overbought is not None else np.nan,
                    'Exit_Williams_R_Overbought': np.nan
                })
            if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']) or \
               (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']):
                new_row.update({
                    'Entry_Williams_R_Oversold': float(current_williams_r_oversold) if current_williams_r_oversold is not None else np.nan,
                    'Exit_Williams_R_Oversold': np.nan
                })
            if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']) or \
               (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']):
                new_row.update({
                    'Entry_Fear_Greed': float(fear_greed_value) if fear_greed_value is not None else np.nan,
                    'Exit_Fear_Greed': np.nan
                })
            df_trades = pd.concat([df_trades, pd.DataFrame([new_row])], ignore_index=True)
        except Exception as e:
            logger.error(f"Ошибка в simulate_open_trade: {e}")




def simulate_close_trade(trade_id, exit_price, exit_time, reason, partial=False, close_percent=100):
    """
    Симулирует закрытие торговой позиции.
    """
    global active_trades, current_balance, current_trade_type, df_trades
    with trades_lock:
        try:
            if trade_id not in active_trades:
                logger.warning(f"Сделка ID={trade_id} не найдена в активных сделках")
                return
            trade = active_trades[trade_id]
            direction = trade['direction']
            entry_price = trade['entry_price']
            size = trade['position_size'] * (close_percent / 100) if partial else trade['position_size']
            position_value = trade['position_value'] * (close_percent / 100) if partial else trade['position_value']
            leverage = trade['leverage']
            commission_open = trade['commission_open'] * (close_percent / 100) if partial else trade['commission_open']
            # Проверка на корректность size и position_value
            if size <= 0 or position_value <= 0:
                logger.error(f"Некорректные значения: size={size}, position_value={position_value} для сделки ID={trade_id}")
                return
            # Расчёт drawdown
            if 'LONG' in direction:
                min_price = trade.get('min_price', entry_price)
                drawdown_usdt = max(0, (entry_price - min_price) * size)
            elif 'SHORT' in direction:
                max_price = trade.get('max_price', entry_price)
                drawdown_usdt = max(0, (max_price - entry_price) * size)
            else:
                drawdown_usdt = 0
            drawdown_percent = (drawdown_usdt / position_value) * 100 if position_value > 0 else 0
            # Расчёт PNL (без лишнего leverage, так как size уже учитывает leverage)
            if 'LONG' in direction:
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size
            commission_close = (size * exit_price) * TRADING_CONFIG['COMMISSION_RATE']
            net_pnl = pnl - commission_open - commission_close
            net_pnl_percent = (net_pnl / position_value) * 100 if position_value > 0 else 0
            # Обновление баланса
            current_balance += position_value + pnl - commission_close
            # Убедимся, что exit_time tz-aware
            if exit_time.tzinfo is None:
                exit_time = exit_time.replace(tzinfo=pytz.UTC)
            duration_seconds = (exit_time - trade['entry_time']).total_seconds()
            duration_str = format_duration(duration_seconds)
            duration_hours = duration_seconds / 3600
            logger.info(
                f"Закрыта сделка ID={trade_id} ({direction}): PNL={net_pnl:.2f} USDT, "
                f"Причина={reason}, Длительность={duration_hours:.2f} часов"
            )
            # Обновление активной сделки при частичном закрытии
            if partial:
                active_trades[trade_id]['position_size'] -= size
                active_trades[trade_id]['position_value'] -= position_value
                active_trades[trade_id]['commission_open'] -= commission_open
                if active_trades[trade_id]['position_size'] <= 0:
                    del active_trades[trade_id]
                    current_trade_type = None
            else:
                del active_trades[trade_id]
                current_trade_type = None
            # Получаем значение индекса страха при закрытии
            fear_greed_value = get_fear_greed_value(exit_time)
            # Обновление записи в df_trades при закрытии с динамическими ключами
            mask = (df_trades['Trade_ID'] == str(trade_id)) & (df_trades['Reason_Close'].isna())
            if mask.any():
                df_trades.loc[mask, 'Reason_Close'] = reason
                df_trades.loc[mask, 'Exit_Time'] = exit_time
                df_trades.loc[mask, 'Trade_Duration'] = duration_str
                df_trades.loc[mask, 'Hours'] = duration_hours
                df_trades.loc[mask, 'Exit_Price'] = float(exit_price)
                df_trades.loc[mask, 'Net_PnL_USDT'] = float(net_pnl)
                df_trades.loc[mask, 'Net_PnL_Percent'] = float(net_pnl_percent)
                df_trades.loc[mask, 'Drawdown_USDT'] = float(drawdown_usdt)
                df_trades.loc[mask, 'Drawdown_Percent'] = float(drawdown_percent)
                df_trades.loc[mask, 'Balance'] = float(current_balance)
                df_trades.loc[mask, 'PnL_Type'] = 'Profit' if net_pnl > 0 else 'Loss'
                # Обновление индикаторных ключей только если соответствующие колонки существуют
                if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_RSI']) or \
                   (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_RSI']):
                    df_trades.loc[mask, 'Exit_RSI'] = float(current_rsi) if current_rsi is not None else np.nan
                    df_trades.loc[mask, 'Exit_SMA_RSI'] = float(current_sma_rsi) if current_sma_rsi is not None else np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or \
                   (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
                    df_trades.loc[mask, 'Exit_Stoch_K'] = float(current_stoch_k) if current_stoch_k is not None else np.nan
                    df_trades.loc[mask, 'Exit_Stoch_D'] = float(current_stoch_d) if current_stoch_d is not None else np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']) or \
                   (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']):
                    df_trades.loc[mask, 'Exit_Williams_R_Overbought'] = float(current_williams_r_overbought) if current_williams_r_overbought is not None else np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']) or \
                   (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']):
                    df_trades.loc[mask, 'Exit_Williams_R_Oversold'] = float(current_williams_r_oversold) if current_williams_r_oversold is not None else np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']) or \
                   (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']):
                    df_trades.loc[mask, 'Exit_Fear_Greed'] = float(fear_greed_value) if fear_greed_value is not None else np.nan
            else:
                logger.warning(f"Не найдена открытая запись для сделки ID={trade_id} в df_trades")
        except Exception as e:
            logger.error(f"Ошибка в simulate_close_trade: {e}")



def check_signals(current_time, current_price, rsi, sma_rsi, stoch_k, stoch_d, williams_r_overbought, williams_r_oversold):
    """
    Проверяет торговые сигналы на основе RSI, SMA RSI, Stochastic RSI и Williams %R.
    """
    global current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi, current_trade_type, pending_action, last_market_type
    global current_stoch_k, current_stoch_d, previous_stoch_k, previous_stoch_d
    global current_williams_r_overbought, previous_williams_r_overbought
    global current_williams_r_oversold, previous_williams_r_oversold
    try:
        current_market_type = hybrid_get_market_type_and_changes(current_time)[0]
        if current_market_type is None:
            return # Игнорируем выключенный тип рынка
        last_market_type = current_market_type
        # Получаем значение индекса страха и жадности
        fear_greed_value = get_fear_greed_value(current_time)
        if fear_greed_value is None:
            logger.warning("⚠️ Нет данных индекса страха для текущей даты. Работаем только по RSI.")
        # Обновление глобальных переменных только для включенных индикаторов
        if (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_RSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_RSI']):
            previous_rsi = current_rsi
            previous_sma_rsi = current_sma_rsi
            current_rsi = rsi
            current_sma_rsi = sma_rsi
        if (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
            previous_stoch_k = current_stoch_k
            previous_stoch_d = current_stoch_d
            current_stoch_k = stoch_k
            current_stoch_d = stoch_d
        if (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']):
            previous_williams_r_overbought = current_williams_r_overbought
            current_williams_r_overbought = williams_r_overbought
        if (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']):
            previous_williams_r_oversold = current_williams_r_oversold
            current_williams_r_oversold = williams_r_oversold
        # Вычисление пересечений только если индикаторы включены
        rsi_crossing = None
        if (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_RSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_RSI']):
            rsi_crossing = check_rsi_crossing(current_rsi, current_sma_rsi)
        stoch_crossing = None
        if (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
            stoch_crossing = check_stoch_crossing(current_stoch_k, current_stoch_d)
        # Основная логика сигналов
        if current_market_type == 'bull':
            if not active_trades:
                if rsi_crossing == "up" and TRADING_CONFIG.get('ENABLE_BULL_LONG', True) and TRADING_CONFIG['ENABLE_BULL_RSI']:
                    logger.info("Сигнал на открытие BULL_LONG по RSI, установка pending_action")
                    pending_action = "open_BULL_LONG_rsi"
                if rsi_crossing == "down" and TRADING_CONFIG.get('ENABLE_BULL_SHORT', True) and TRADING_CONFIG['ENABLE_BULL_RSI']:
                    logger.info("Сигнал на открытие BULL_SHORT по RSI, установка pending_action")
                    pending_action = "open_BULL_SHORT_rsi"
                # НЕ УДАЛЯТЬ! Проверить логику
                # Проверка StochRSI для открытия BULL_LONG
                if (stoch_crossing == "up" and
                    TRADING_CONFIG.get('ENABLE_BULL_LONG', True) and
                    TRADING_CONFIG['ENABLE_BULL_STOCHRSI']):
                    logger.info("Сигнал на открытие BULL_LONG по StochRSI вверх, установка pending_action")
                    pending_action = "open_BULL_LONG_stoch"
                # Проверка StochRSI для открытия BULL_SHORT
                if (stoch_crossing == "down" and
                    TRADING_CONFIG.get('ENABLE_BULL_SHORT', True) and
                    TRADING_CONFIG['ENABLE_BULL_STOCHRSI']):
                    logger.info("Сигнал на открытие BULL_SHORT по StochRSI вниз, установка pending_action")
                    pending_action = "open_BULL_SHORT_stoch"
                # Проверка Williams %R oversold с защитой от None и np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_LONG', True) and
                    TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD'] and
                    current_williams_r_oversold is not None and
                    not np.isnan(current_williams_r_oversold) and
                    current_williams_r_oversold <= BULL_WILLIAMS_OVERSOLD_LEVEL):
                    logger.info("Сигнал на открытие BULL_LONG по Williams %R oversold, установка pending_action")
                    pending_action = "open_BULL_LONG_oversold"
                # Проверка Williams %R overbought для открытия BULL_SHORT с защитой от None и np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_SHORT', True) and
                    TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT'] and
                    current_williams_r_overbought is not None and
                    not np.isnan(current_williams_r_overbought) and
                    current_williams_r_overbought >= BULL_WILLIAMS_OVERBOUGHT_LEVEL):
                    logger.info("Сигнал на открытие BULL_SHORT по Williams %R overbought, установка pending_action")
                    pending_action = "open_BULL_SHORT_overbought"
            else:
                if current_trade_type == 'BULL_LONG':
                    # Проверка сигнала StochRSI для закрытия (если раньше RSI)
                    if stoch_crossing == "down" and rsi_crossing != "down" and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
                        logger.info("Сигнал на закрытие BULL_LONG по StochRSI вниз, установка pending_action")
                        pending_action = "stoch_down"
                    # Сигнал RSI (если не сработал StochRSI)
                    if rsi_crossing == "down" and TRADING_CONFIG['ENABLE_BULL_RSI']:
                        logger.info("Сигнал на закрытие BULL_LONG по RSI вниз, установка pending_action")
                        pending_action = "rsi_down"
                    # Проверка Williams %R overbought с защитой от None и np.nan
                    if (TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT'] and
                        current_williams_r_overbought is not None and
                        not np.isnan(current_williams_r_overbought) and
                        current_williams_r_overbought >= BULL_WILLIAMS_OVERBOUGHT_LEVEL):
                        logger.info("Сигнал на закрытие BULL_LONG по Williams %R overbought, установка pending_action")
                        pending_action = "williams_overbought"
                elif current_trade_type == 'BULL_SHORT':
                    if rsi_crossing == "up" and TRADING_CONFIG['ENABLE_BULL_RSI']:
                        logger.info("Сигнал на закрытие BULL_SHORT по RSI вверх, установка pending_action")
                        pending_action = "rsi_up"
                    # Проверка Williams %R oversold с защитой от None и np.nan
                    if (TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD'] and
                        current_williams_r_oversold is not None and
                        not np.isnan(current_williams_r_oversold) and
                        current_williams_r_oversold <= BULL_WILLIAMS_OVERSOLD_LEVEL):
                        logger.info("Сигнал на закрытие BULL_SHORT по Williams %R oversold, установка pending_action")
                        pending_action = "close_BULL_SHORT_oversold"
        elif current_market_type == 'bear':
            if not active_trades:
                if rsi_crossing == "down" and TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True) and TRADING_CONFIG['ENABLE_BEAR_RSI']:
                    logger.info("Сигнал на открытие BEAR_SHORT по RSI, установка pending_action")
                    pending_action = "open_BEAR_SHORT_rsi"
                if rsi_crossing == "up" and TRADING_CONFIG.get('ENABLE_BEAR_LONG', True) and TRADING_CONFIG['ENABLE_BEAR_RSI']:
                    logger.info("Сигнал на открытие BEAR_LONG по RSI, установка pending_action")
                    pending_action = "open_BEAR_LONG_rsi"
                # Проверка StochRSI для открытия BEAR_SHORT
                if (stoch_crossing == "down" and
                    TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True) and
                    TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
                    logger.info("Сигнал на открытие BEAR_SHORT по StochRSI вниз, установка pending_action")
                    pending_action = "open_BEAR_SHORT_stoch"
                # Проверка StochRSI для открытия BEAR_LONG
                if (stoch_crossing == "up" and
                    TRADING_CONFIG.get('ENABLE_BEAR_LONG', True) and
                    TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
                    logger.info("Сигнал на открытие BEAR_LONG по StochRSI вверх, установка pending_action")
                    pending_action = "open_BEAR_LONG_stoch"
                # Проверка Williams %R overbought с защитой от None и np.nan
                if (TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True) and
                    TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT'] and
                    current_williams_r_overbought is not None and
                    not np.isnan(current_williams_r_overbought) and
                    current_williams_r_overbought >= BEAR_WILLIAMS_OVERBOUGHT_LEVEL):
                    logger.info("Сигнал на открытие BEAR_SHORT по Williams %R overbought, установка pending_action")
                    pending_action = "open_BEAR_SHORT_overbought"
                # Проверка Williams %R oversold с защитой от None и np.nan
                if (TRADING_CONFIG.get('ENABLE_BEAR_LONG', True) and
                    TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD'] and
                    current_williams_r_oversold is not None and
                    not np.isnan(current_williams_r_oversold) and
                    current_williams_r_oversold <= BEAR_WILLIAMS_OVERSOLD_LEVEL):
                    logger.info("Сигнал на открытие BEAR_LONG по Williams %R oversold, установка pending_action")
                    pending_action = "open_BEAR_LONG_oversold"
            else:
                if current_trade_type == 'BEAR_SHORT':
                    if rsi_crossing == "up" and TRADING_CONFIG['ENABLE_BEAR_RSI']:
                        logger.info("Сигнал на закрытие BEAR_SHORT по RSI вверх, установка pending_action")
                        pending_action = "rsi_up"
                    if stoch_crossing == "up" and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
                        logger.info("Сигнал на закрытие BEAR_SHORT по StochRSI вверх, установка pending_action")
                        pending_action = "stoch_up"
                    # Проверка Williams %R oversold с защитой от None и np.nan
                    if (TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD'] and
                        current_williams_r_oversold is not None and
                        not np.isnan(current_williams_r_oversold) and
                        current_williams_r_oversold <= BEAR_WILLIAMS_OVERSOLD_LEVEL):
                        logger.info("Сигнал на закрытие BEAR_SHORT по Williams %R oversold, установка pending_action")
                        pending_action = "close_BEAR_SHORT_oversold"
                elif current_trade_type == 'BEAR_LONG':
                    if rsi_crossing == "down" and TRADING_CONFIG['ENABLE_BEAR_RSI']:
                        logger.info("Сигнал на закрытие BEAR_LONG по RSI вниз, установка pending_action")
                        pending_action = "rsi_down"
                    if stoch_crossing == "down" and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
                        logger.info("Сигнал на закрытие BEAR_LONG по StochRSI вниз, установка pending_action")
                        pending_action = "stoch_down"
                    # Проверка Williams %R overbought с защитой от None и np.nan
                    if (TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT'] and
                        current_williams_r_overbought is not None and
                        not np.isnan(current_williams_r_overbought) and
                        current_williams_r_overbought >= BEAR_WILLIAMS_OVERBOUGHT_LEVEL):
                        logger.info("Сигнал на закрытие BEAR_LONG по Williams %R overbought, установка pending_action")
                        pending_action = "williams_overbought"
    except Exception as e:
        logger.error(f"Ошибка в check_signals: {e}")



def close_all_trades_sim(reason, exit_time, current_price, with_reverse=True):
    global active_trades, current_balance, current_trade_type
    with trades_lock:
        if not active_trades:
            logger.info("⚪ Нет активных сделок для закрытия")
        else:
            last_trade_direction = next(iter(active_trades.values()))['direction'] if active_trades else None
            for trade_id in list(active_trades.keys()):
                simulate_close_trade(trade_id, current_price, exit_time, reason)
            current_trade_type = None
            logger.info(f"📊 Закрыты все активные сделки по причине '{reason}', последний тип: {last_trade_direction}")
        if with_reverse and reason != "market_type_change":
            current_market_type = hybrid_get_market_type_and_changes(exit_time)[0]
            if current_market_type == 'bull':
                if last_trade_direction == 'BULL_LONG' and TRADING_CONFIG.get('ENABLE_BULL_SHORT', True):
                    logger.info(f"📉 Разворот на бычьем рынке: Открытие BULL_SHORT по цене {current_price:.2f}")
                    simulate_open_trade('BULL_SHORT', current_price, exit_time, f'{reason}_reverse')
                elif last_trade_direction in ['BULL_SHORT', 'BEAR_SHORT', 'BEAR_LONG'] and TRADING_CONFIG.get('ENABLE_BULL_LONG', True):
                    logger.info(f"📈 Разворот на бычьем рынке: Открытие BULL_LONG по цене {current_price:.2f}")
                    simulate_open_trade('BULL_LONG', current_price, exit_time, f'{reason}_reverse')
            elif current_market_type == 'bear':
                if last_trade_direction == 'BEAR_LONG' and TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True):
                    logger.info(f"📉 Разворот на медвежьем рынке: Открытие BEAR_SHORT по цене {current_price:.2f}")
                    simulate_open_trade('BEAR_SHORT', current_price, exit_time, f'{reason}_reverse')
                elif last_trade_direction in ['BEAR_SHORT', 'BULL_SHORT', 'BULL_LONG'] and TRADING_CONFIG.get('ENABLE_BEAR_LONG', True):
                    logger.info(f"📈 Разворот на медвежьем рынке: Открытие BEAR_LONG по цене {current_price:.2f}")
                    simulate_open_trade('BEAR_LONG', current_price, exit_time, f'{reason}_reverse')
        elif reason == "market_type_change" and with_reverse:
            current_market_type = hybrid_get_market_type_and_changes(exit_time)[0]
            if current_market_type == 'bull':
                if TRADING_CONFIG.get('ENABLE_BULL_LONG', True):
                    logger.info(f"📈 Разворот на бычьем рынке: Открытие BULL_LONG по цене {current_price:.2f}")
                    simulate_open_trade('BULL_LONG', current_price, exit_time, 'market_type_change')
                elif TRADING_CONFIG.get('ENABLE_BULL_SHORT', True):
                    logger.info(f"📉 Разворот на бычьем рынке: Открытие BULL_SHORT по цене {current_price:.2f}")
                    simulate_open_trade('BULL_SHORT', current_price, exit_time, 'market_type_change')
                else:
                    logger.warning("Нет включенных стратегий для bull, пропуск открытия")
            elif current_market_type == 'bear':
                if TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True):
                    logger.info(f"📉 Разворот на медвежьем рынке: Открытие BEAR_SHORT по цене {current_price:.2f}")
                    simulate_open_trade('BEAR_SHORT', current_price, exit_time, 'market_type_change')
                elif TRADING_CONFIG.get('ENABLE_BEAR_LONG', True):
                    logger.info(f"📈 Разворот на медвежьем рынке: Открытие BEAR_LONG по цене {current_price:.2f}")
                    simulate_open_trade('BEAR_LONG', current_price, exit_time, 'market_type_change')
                else:
                    logger.warning("Нет включенных стратегий для bear, пропуск открытия")


                    
def print_backtest_results(
    start_date, end_date, total_days, num_trades, total_pnl, win_trades, loss_trades,
    avg_duration, start_price, end_price, price_change_percent, min_balance, max_balance,
    trades_per_day, profit_per_day, profit_per_day_percent,
    trades_per_week, profit_per_week, profit_per_week_percent,
    trades_per_month, profit_per_month, profit_per_month_percent,
    win_pnl, loss_pnl, total_months,
    profitable_months, profitable_months_percent, profitable_months_pnl,
    loss_months, loss_months_percent, loss_months_pnl,
    min_drawdown_percent=0.0, min_drawdown_id=None,
    max_drawdown_percent=0.0, max_drawdown_id=None,
    min_drawdown_bull_percent=0.0, min_drawdown_id_bull=None,
    max_drawdown_bull_percent=0.0, max_drawdown_id_bull=None,
    min_drawdown_bear_percent=0.0, min_drawdown_id_bear=None,
    max_drawdown_bear_percent=0.0, max_drawdown_id_bear=None
):
    """
    Выводит результаты бэктеста в терминал в требуемом формате.
    """
    logger.setLevel(logging.INFO)
    # Проверка на nan и замена на 0.0
    total_pnl = 0.0 if np.isnan(total_pnl) else total_pnl
    profit_per_day = 0.0 if np.isnan(profit_per_day) else profit_per_day
    profit_per_day_percent = 0.0 if np.isnan(profit_per_day_percent) else profit_per_day_percent
    profit_per_week = 0.0 if np.isnan(profit_per_week) else profit_per_week
    profit_per_week_percent = 0.0 if np.isnan(profit_per_week_percent) else profit_per_week_percent
    profit_per_month = 0.0 if np.isnan(profit_per_month) else profit_per_month
    profit_per_month_percent = 0.0 if np.isnan(profit_per_month_percent) else profit_per_month_percent
    profitable_months_pnl = 0.0 if np.isnan(profitable_months_pnl) else profitable_months_pnl
    loss_months_pnl = 0.0 if np.isnan(loss_months_pnl) else loss_months_pnl
    min_balance = 0.0 if np.isnan(min_balance) else min_balance
    max_balance = 0.0 if np.isnan(max_balance) else max_balance
    if np.isnan(total_pnl):
        logger.warning("Общая чистая прибыль равна nan, заменено на 0.0")
    # Расчёт процентов
    win_percent = (win_trades / num_trades * 100) if num_trades > 0 else 0.0
    loss_percent = (loss_trades / num_trades * 100) if num_trades > 0 else 0.0
    min_balance_percent = ((min_balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100) if INITIAL_BALANCE > 0 else 0.0
    max_balance_percent = ((max_balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100) if INITIAL_BALANCE > 0 else 0.0
    # Расчет количества сделок по типам рынков для проверки участия
    num_trades_bull = num_trades if num_trades > 0 and max_drawdown_bull_percent != 0.0 and TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) else 0 # Приближенная проверка по наличию просадки и флагу
    num_trades_bear = num_trades if num_trades > 0 and max_drawdown_bear_percent != 0.0 and TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) else 0
    # Формируем строки результатов в требуемом формате
    results = [
        "РЕЗУЛЬТАТЫ БЭКТЕСТА",
        "",
        "------------- ПАРАМЕТРЫ СТРАТЕГИИ ------------|",
        f"INITIAL_BALANCE: {INITIAL_BALANCE:,.2f} USD",
        f"ENABLE_BULL_LONG: {TRADING_CONFIG['ENABLE_BULL_LONG']}",
        f"BULL_LONG: LEVERAGE: {TRADING_CONFIG['BULL_LONG']['LEVERAGE']}, ENTRY_PERCENT: {TRADING_CONFIG['BULL_LONG']['ENTRY_PERCENT']}",
        f"ENABLE_BULL_SHORT: {TRADING_CONFIG['ENABLE_BULL_SHORT']}",
        f"BULL_SHORT: LEVERAGE: {TRADING_CONFIG['BULL_SHORT']['LEVERAGE']}, ENTRY_PERCENT: {TRADING_CONFIG['BULL_SHORT']['ENTRY_PERCENT']}",
        f"ENABLE_BEAR_SHORT: {TRADING_CONFIG['ENABLE_BEAR_SHORT']}",
        f"BEAR_SHORT: LEVERAGE: {TRADING_CONFIG['BEAR_SHORT']['LEVERAGE']}, ENTRY_PERCENT: {TRADING_CONFIG['BEAR_SHORT']['ENTRY_PERCENT']}",
        f"ENABLE_BEAR_LONG: {TRADING_CONFIG['ENABLE_BEAR_LONG']}",
        f"BEAR_LONG: LEVERAGE: {TRADING_CONFIG['BEAR_LONG']['LEVERAGE']}, ENTRY_PERCENT: {TRADING_CONFIG['BEAR_LONG']['ENTRY_PERCENT']}",
        f"ENABLE_BULL_MARKET: {TRADING_CONFIG['ENABLE_BULL_MARKET']}", # Новая строка
        f"ENABLE_BEAR_MARKET: {TRADING_CONFIG['ENABLE_BEAR_MARKET']}", # Новая строка
        "",
        f"GLOBAL_TIMEFRAME: {GLOBAL_TIMEFRAME}",
        "",
    ]
    # Условный вывод параметров BULL
    if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
        results += [
            "------------- BULL ПАРАМЕТРЫ ------------|",
            f"ENABLE_BULL_RSI: {TRADING_CONFIG['ENABLE_BULL_RSI']}",
            f" BULL_RSI_PERIOD: {BULL_RSI_PERIOD}",
            f" BULL_SMA_RSI_PERIOD: {BULL_SMA_RSI_PERIOD}",
            f"ENABLE_BULL_STOCHRSI: {TRADING_CONFIG['ENABLE_BULL_STOCHRSI']}",
            f" BULL_STOCHRSI_K_PERIOD: {BULL_STOCHRSI_K_PERIOD}",
            f" BULL_STOCHRSI_D_PERIOD: {BULL_STOCHRSI_D_PERIOD}",
            f" BULL_STOCHRSI_RSI_PERIOD: {BULL_STOCHRSI_RSI_PERIOD}",
            f" BULL_STOCHRSI_STOCH_PERIOD: {BULL_STOCHRSI_STOCH_PERIOD}",
            f"ENABLE_BULL_WILLIAMS_OVERBOUGHT: {TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']}",
            f" BULL_WILLIAMS_OVERBOUGHT_PERIOD: {BULL_WILLIAMS_OVERBOUGHT_PERIOD}",
            f" BULL_WILLIAMS_OVERBOUGHT_LEVEL: {BULL_WILLIAMS_OVERBOUGHT_LEVEL:.2f}",
            f" BULL_WILLIAMS_OVERBOUGHT_SOURCE: {BULL_WILLIAMS_OVERBOUGHT_SOURCE}", # Новый вывод
            f"ENABLE_BULL_WILLIAMS_OVERSOLD: {TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']}",
            f" BULL_WILLIAMS_OVERSOLD_PERIOD: {BULL_WILLIAMS_OVERSOLD_PERIOD}",
            f" BULL_WILLIAMS_OVERSOLD_LEVEL: {BULL_WILLIAMS_OVERSOLD_LEVEL:.2f}",
            f" BULL_WILLIAMS_OVERSOLD_SOURCE: {BULL_WILLIAMS_OVERSOLD_SOURCE}", # Новый вывод
            f"ENABLE_BULL_FEAR_GREED: {TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']}",
            f" BULL_FEAR_GREED_LOW: {BULL_FEAR_GREED_LOW}",
            "",
        ]
    # Условный вывод параметров BEAR
    if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
        results += [
            "------------- BEAR ПАРАМЕТРЫ ------------|",
            f"ENABLE_BEAR_RSI: {TRADING_CONFIG['ENABLE_BEAR_RSI']}",
            f" BEAR_RSI_PERIOD: {BEAR_RSI_PERIOD}",
            f" BEAR_SMA_RSI_PERIOD: {BEAR_SMA_RSI_PERIOD}",
            f"ENABLE_BEAR_STOCHRSI: {TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']}",
            f" BEAR_STOCHRSI_K_PERIOD: {BEAR_STOCHRSI_K_PERIOD}",
            f" BEAR_STOCHRSI_D_PERIOD: {BEAR_STOCHRSI_D_PERIOD}",
            f" BEAR_STOCHRSI_RSI_PERIOD: {BEAR_STOCHRSI_RSI_PERIOD}",
            f" BEAR_STOCHRSI_STOCH_PERIOD: {BEAR_STOCHRSI_STOCH_PERIOD}",
            f"ENABLE_BEAR_WILLIAMS_OVERBOUGHT: {TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']}",
            f" BEAR_WILLIAMS_OVERBOUGHT_PERIOD: {BEAR_WILLIAMS_OVERBOUGHT_PERIOD}",
            f" BEAR_WILLIAMS_OVERBOUGHT_LEVEL: {BEAR_WILLIAMS_OVERBOUGHT_LEVEL:.2f}",
            f" BEAR_WILLIAMS_OVERBOUGHT_SOURCE: {BEAR_WILLIAMS_OVERBOUGHT_SOURCE}", # Новый вывод
            f"ENABLE_BEAR_WILLIAMS_OVERSOLD: {TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']}",
            f" BEAR_WILLIAMS_OVERSOLD_PERIOD: {BEAR_WILLIAMS_OVERSOLD_PERIOD}",
            f" BEAR_WILLIAMS_OVERSOLD_LEVEL: {BEAR_WILLIAMS_OVERSOLD_LEVEL:.2f}",
            f" BEAR_WILLIAMS_OVERSOLD_SOURCE: {BEAR_WILLIAMS_OVERSOLD_SOURCE}", # Новый вывод
            f"ENABLE_BEAR_FEAR_GREED: {TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']}",
            f" BEAR_FEAR_GREED_HIGH: {BEAR_FEAR_GREED_HIGH}",
            "----------------------------------------------|",
        ]
    results += [
        f"Файл данных: {DATA_FILE.name}",
        "----------------------------------------------|",
        "------------- РЕЗУЛЬТАТЫ БЭКТЕСТА ------------|",
        "----------------------------------------------|",
        f"{start_date.strftime('%Y-%m-%d %H:%M:%S')} --> {end_date.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Всего дней: {total_days}",
        f"Цена BTC {start_price:,.2f} USD --> {end_price:,.2f} USD ({price_change_percent:,.2f}%)",
        "",
        f"Всего сделок: {num_trades}",
        f"Прибыльные сделки: {win_trades} ({win_percent:,.2f}%) ({win_pnl:,.2f} USD)",
        f"Убыточные сделки: {loss_trades} ({loss_percent:,.2f}%) ({loss_pnl:,.2f} USD)",
        "",
    ]
    # Добавление строк для просадок bull, если рынок включен и есть сделки
    if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and num_trades_bull > 0:
        results.append(f"BULL - Максимальная просадка: {max_drawdown_bull_percent:,.2f}% ({max_drawdown_id_bull})" if max_drawdown_id_bull else f"Бычий рынок - Максимальная просадка: {max_drawdown_bull_percent:,.2f}%")
    # Добавление строк для просадок bear, если рынок включен и есть сделки
    if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and num_trades_bear > 0:
        results.append(f"BEAR - Максимальная просадка: {max_drawdown_bear_percent:,.2f}% ({max_drawdown_id_bear})" if max_drawdown_id_bear else f"Медвежий рынок - Максимальная просадка: {max_drawdown_bear_percent:,.2f}%")
    if num_trades_bull == 0 and num_trades_bear == 0:
        results.append("Нет сделок по типам рынков для расчета просадок")
    results += [
        "",
        f"Чистая прибыль: {(total_pnl / INITIAL_BALANCE * 100):,.2f}% ({total_pnl:,.2f} USD)",
        "",
        "----------------------------------------------|",
        f"Среднее количество сделок в день: {trades_per_day:,.2f}",
        f"Средняя прибыль в день: {profit_per_day:,.2f} USD",
        f"Средняя прибыль в день (%): {profit_per_day_percent:,.2f}%",
        "----------------------------------------------|",
        f"Среднее количество сделок в неделю: {trades_per_week:,.2f}",
        f"Средняя прибыль в неделю: {profit_per_week:,.2f} USD",
        f"Средняя прибыль в неделю (%): {profit_per_week_percent:,.2f}%",
        "----------------------------------------------|",
        f"Среднее количество сделок в месяц: {trades_per_month:,.2f}",
        f"Средняя прибыль в месяц: {profit_per_month:,.2f} USD",
        f"Средняя прибыль в месяц (%): {profit_per_month_percent:,.2f}%",
        "----------------------------------------------|",
    ]
    for line in results:
        print(line)




def optimize_params():
    """ Выполняет перебор параметров RSI, SMA, Stochastic RSI, Williams %R и Fear & Greed для нахождения оптимальной комбинации по максимальному проценту прибыльных сделок. """
    global BULL_RSI_PERIOD, BULL_SMA_RSI_PERIOD, BULL_STOCHRSI_RSI_PERIOD, BULL_STOCHRSI_STOCH_PERIOD, BULL_STOCHRSI_K_PERIOD, BULL_STOCHRSI_D_PERIOD, ENABLE_OPTIMIZATION
    global BULL_WILLIAMS_OVERBOUGHT_PERIOD, BULL_WILLIAMS_OVERBOUGHT_LEVEL
    global BULL_WILLIAMS_OVERSOLD_PERIOD, BULL_WILLIAMS_OVERSOLD_LEVEL
    global BEAR_RSI_PERIOD, BEAR_SMA_RSI_PERIOD, BEAR_STOCHRSI_RSI_PERIOD, BEAR_STOCHRSI_STOCH_PERIOD, BEAR_STOCHRSI_K_PERIOD, BEAR_STOCHRSI_D_PERIOD
    global BEAR_WILLIAMS_OVERBOUGHT_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_LEVEL
    global BEAR_WILLIAMS_OVERSOLD_PERIOD, BEAR_WILLIAMS_OVERSOLD_LEVEL
    global BULL_FEAR_GREED_LOW, BEAR_FEAR_GREED_HIGH
    # Списки для топ-1 по критериям (расширены для новых параметров Fear & Greed), для просадок - топ-3
    top_win_percent = [] # (win_percent, bull_rsi, bull_sma, bull_sk, bull_sd, bull_sr, bull_st, bull_wp_ob, bull_wl_ob, bull_wp_os, bull_wl_os, bull_fear_low, bear_rsi, bear_sma, bear_sk, bear_sd, bear_sr, bear_st, bear_wp_ob, bear_wl_ob, bear_wp_os, bear_wl_os, bear_fear_high, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, max_drawdown_percent, win_percent, profit_per_day_percent)
    top_profit_day_percent = []
    top_max_drawdown = [] # (max_drawdown_percent, bull_rsi, ..., profit_per_day_percent) - категория по максимальной просадке, топ-3
    original_level = logger.level
    logger.setLevel(logging.ERROR)
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    # Генерация имени CSV-файла для таблицы оптимизации
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    opt_csv_file = logs_dir / f'optimization_{timestamp}.csv'
    # Буфер для данных оптимизации и счетчик для периодического сохранения
    optimization_buffer = []
    buffer_save_interval = 50 # Сохранять каждые 50 комбинаций
    first_save = True
    # Динамическое формирование списка колонок на основе включенных флагов
    columns_order = [
        'Номер комбинации',
        'Процент прибыльных сделок',
        'Максимальная просадка',
        'Прибыль в день',
        'Количество сделок',
        'Прибыльные сделки',
        'Убыточные сделки',
        'Общая прибыль',
        'Общая прибыль %'
    ]
    # Добавление колонок для bull, если рынок включен
    if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
        if TRADING_CONFIG['ENABLE_BULL_RSI']:
            columns_order.extend(['BULL_RSI_PERIOD', 'BULL_SMA_RSI_PERIOD'])
        if TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
            columns_order.extend(['BULL_STOCHRSI_K_PERIOD', 'BULL_STOCHRSI_D_PERIOD', 'BULL_STOCHRSI_RSI_PERIOD', 'BULL_STOCHRSI_STOCH_PERIOD'])
        if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']:
            columns_order.extend(['BULL_WILLIAMS_OVERBOUGHT_PERIOD', 'BULL_WILLIAMS_OVERBOUGHT_LEVEL'])
        if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
            columns_order.extend(['BULL_WILLIAMS_OVERSOLD_PERIOD', 'BULL_WILLIAMS_OVERSOLD_LEVEL'])
        if TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']:
            columns_order.append('BULL_FEAR_GREED_LOW')
    # Добавление колонок для bear, если рынок включен
    if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
        if TRADING_CONFIG['ENABLE_BEAR_RSI']:
            columns_order.extend(['BEAR_RSI_PERIOD', 'BEAR_SMA_RSI_PERIOD'])
        if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
            columns_order.extend(['BEAR_STOCHRSI_K_PERIOD', 'BEAR_STOCHRSI_D_PERIOD', 'BEAR_STOCHRSI_RSI_PERIOD', 'BEAR_STOCHRSI_STOCH_PERIOD'])
        if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']:
            columns_order.extend(['BEAR_WILLIAMS_OVERBOUGHT_PERIOD', 'BEAR_WILLIAMS_OVERBOUGHT_LEVEL'])
        if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
            columns_order.extend(['BEAR_WILLIAMS_OVERSOLD_PERIOD', 'BEAR_WILLIAMS_OVERSOLD_LEVEL'])
        if TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']:
            columns_order.append('BEAR_FEAR_GREED_HIGH')
    # Динамическое формирование диапазонов для product только для включенных индикаторов и рынков
    ranges = []
    # Для bull, если рынок включен
    if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
        if TRADING_CONFIG['ENABLE_BULL_RSI']:
            ranges.append(range(BULL_RSI_MIN, BULL_RSI_MAX + 1, BULL_RSI_STEP))
            ranges.append(range(BULL_SMA_MIN, BULL_SMA_MAX + 1, BULL_SMA_STEP))
        if TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
            ranges.append(range(BULL_STOCHRSI_K_MIN, BULL_STOCHRSI_K_MAX + 1, BULL_STOCHRSI_K_STEP))
            ranges.append(range(BULL_STOCHRSI_D_MIN, BULL_STOCHRSI_D_MAX + 1, BULL_STOCHRSI_D_STEP))
            ranges.append(range(BULL_STOCHRSI_RSI_MIN, BULL_STOCHRSI_RSI_MAX + 1, BULL_STOCHRSI_RSI_STEP))
            ranges.append(range(BULL_STOCHRSI_STOCH_MIN, BULL_STOCHRSI_STOCH_MAX + 1, BULL_STOCHRSI_STOCH_STEP))
        if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']:
            ranges.append(range(BULL_WILLIAMS_OVERBOUGHT_PERIOD_MIN, BULL_WILLIAMS_OVERBOUGHT_PERIOD_MAX + 1, BULL_WILLIAMS_OVERBOUGHT_PERIOD_STEP))
            ranges.append(np.arange(BULL_WILLIAMS_OVERBOUGHT_LEVEL_MIN, BULL_WILLIAMS_OVERBOUGHT_LEVEL_MAX + BULL_WILLIAMS_OVERBOUGHT_LEVEL_STEP, BULL_WILLIAMS_OVERBOUGHT_LEVEL_STEP))
        if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
            ranges.append(range(BULL_WILLIAMS_OVERSOLD_PERIOD_MIN, BULL_WILLIAMS_OVERSOLD_PERIOD_MAX + 1, BULL_WILLIAMS_OVERSOLD_PERIOD_STEP))
            ranges.append(np.arange(BULL_WILLIAMS_OVERSOLD_LEVEL_MIN, BULL_WILLIAMS_OVERSOLD_LEVEL_MAX + BULL_WILLIAMS_OVERSOLD_LEVEL_STEP, BULL_WILLIAMS_OVERSOLD_LEVEL_STEP))
        if TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']:
            ranges.append(range(BULL_FEAR_GREED_LOW_MIN, BULL_FEAR_GREED_LOW_MAX + 1, BULL_FEAR_GREED_LOW_STEP))
    # Для bear, если рынок включен
    if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
        if TRADING_CONFIG['ENABLE_BEAR_RSI']:
            ranges.append(range(BEAR_RSI_MIN, BEAR_RSI_MAX + 1, BEAR_RSI_STEP))
            ranges.append(range(BEAR_SMA_MIN, BEAR_SMA_MAX + 1, BEAR_SMA_STEP))
        if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
            ranges.append(range(BEAR_STOCHRSI_K_MIN, BEAR_STOCHRSI_K_MAX + 1, BEAR_STOCHRSI_K_STEP))
            ranges.append(range(BEAR_STOCHRSI_D_MIN, BEAR_STOCHRSI_D_MAX + 1, BEAR_STOCHRSI_D_STEP))
            ranges.append(range(BEAR_STOCHRSI_RSI_MIN, BEAR_STOCHRSI_RSI_MAX + 1, BEAR_STOCHRSI_RSI_STEP))
            ranges.append(range(BEAR_STOCHRSI_STOCH_MIN, BEAR_STOCHRSI_STOCH_MAX + 1, BEAR_STOCHRSI_STOCH_STEP))
        if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']:
            ranges.append(range(BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MIN, BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MAX + 1, BEAR_WILLIAMS_OVERBOUGHT_PERIOD_STEP))
            ranges.append(np.arange(BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MIN, BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MAX + BEAR_WILLIAMS_OVERBOUGHT_LEVEL_STEP, BEAR_WILLIAMS_OVERBOUGHT_LEVEL_STEP))
        if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
            ranges.append(range(BEAR_WILLIAMS_OVERSOLD_PERIOD_MIN, BEAR_WILLIAMS_OVERSOLD_PERIOD_MAX + 1, BEAR_WILLIAMS_OVERSOLD_PERIOD_STEP))
            ranges.append(np.arange(BEAR_WILLIAMS_OVERSOLD_LEVEL_MIN, BEAR_WILLIAMS_OVERSOLD_LEVEL_MAX + BEAR_WILLIAMS_OVERSOLD_LEVEL_STEP, BEAR_WILLIAMS_OVERSOLD_LEVEL_STEP))
        if TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']:
            ranges.append(range(BEAR_FEAR_GREED_HIGH_MIN, BEAR_FEAR_GREED_HIGH_MAX + 1, BEAR_FEAR_GREED_HIGH_STEP))
    # Расчет total_combinations динамически
    total_combinations = 1
    for r in ranges:
        total_combinations *= len(r)
    if total_combinations == 1:
        print("Нет параметров для оптимизации (все индикаторы или рынки выключены). Пропуск оптимизации.")
        return
    # Генерация комбинаций только для включенных диапазонов
    param_combinations = product(*ranges)
    current_comb = 0
    start_time = datetime.now()
    # Функция display_top (адаптирована для топ-3 в категории просадок, стохастик: K, D, RSI, Stoch)
    def display_top(top_list, title):
        if top_list:
            n_to_show = 1 # Для всех теперь топ-1, включая просадку
            print(f"\n!!!!!!!! Текущий топ-{n_to_show} по {title}:")
            for idx, item in enumerate(top_list[:n_to_show], 1):
                score, br, bs, bsk, bsd, bsr, bst, bwp_ob, bwl_ob, bwp_os, bwl_os, bfl, er, es, esk, esd, esr, est, ewp_ob, ewl_ob, ewp_os, ewl_os, efh, pnl, nt, wt, _, _, _, _, mdd, win_p, pdp = item
                # Условный вывод для bull
                msg1 = f" {idx}. BULL: "
                if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
                    if TRADING_CONFIG['ENABLE_BULL_RSI']:
                        msg1 += f"RSI_PERIOD={br}, SMA_RSI_PERIOD={bs}, "
                    if TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
                        msg1 += f"STOCHRSI_K_PERIOD={bsk}, STOCHRSI_D_PERIOD={bsd}, STOCHRSI_RSI_PERIOD={bsr}, STOCHRSI_STOCH_PERIOD={bst}, "
                    if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']:
                        msg1 += f"WILLIAMS_OVERBOUGHT_PERIOD={bwp_ob}, WILLIAMS_OVERBOUGHT_LEVEL={bwl_ob:.2f}, "
                    if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
                        msg1 += f"WILLIAMS_OVERSOLD_PERIOD={bwp_os}, WILLIAMS_OVERSOLD_LEVEL={bwl_os:.2f}, "
                    if TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']:
                        msg1 += f"FEAR_GREED_LOW={bfl}"
                    if msg1.endswith(", "):
                        msg1 = msg1.rstrip(", ") # Удаление лишней запятой
                else:
                    msg1 += "Нет включенных параметров для bull рынка"
                # Условный вывод для bear
                msg2 = f" BEAR: "
                if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
                    if TRADING_CONFIG['ENABLE_BEAR_RSI']:
                        msg2 += f"RSI_PERIOD={er}, SMA_RSI_PERIOD={es}, "
                    if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
                        msg2 += f"STOCHRSI_K_PERIOD={esk}, STOCHRSI_D_PERIOD={esd}, STOCHRSI_RSI_PERIOD={esr}, STOCHRSI_STOCH_PERIOD={est}, "
                    if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']:
                        msg2 += f"WILLIAMS_OVERBOUGHT_PERIOD={ewp_ob}, WILLIAMS_OVERBOUGHT_LEVEL={ewl_ob:.2f}, "
                    if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
                        msg2 += f"WILLIAMS_OVERSOLD_PERIOD={ewp_os}, WILLIAMS_OVERSOLD_LEVEL={ewl_os:.2f}, "
                    if TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']:
                        msg2 += f"FEAR_GREED_HIGH={efh}"
                    if msg2.endswith(", "):
                        msg2 = msg2.rstrip(", ") # Удаление лишней запятой
                else:
                    msg2 += "Нет включенных параметров для bear рынка"
                if title == "прибыли в день":
                    msg3 = f" Процент прибыльных сделок: {win_p:.2f}% (лучший % прибыли в день: {score:.2f}%)"
                elif title == "проценту прибыльных сделок":
                    msg3 = f" Лучший % прибыльных сделок: {score:.2f}% (прибыль в день при равенстве: {pdp:.2f}%)"
                elif title == "максимальной просадке":
                    msg3 = f" Процент прибыльных сделок: {win_p:.2f}%\n Лучшая Максимальная просадка: {round(score, 2):.2f}% (прибыль в день при равенстве: {pdp:.2f}%)"
                else:
                    msg3 = f" Процент прибыльных сделок: {score:.2f}% (прибыль в день: {pdp:.2f}%)"
                msg4 = f" Максимальная просадка: {round(mdd, 2):.2f}%, Общая прибыль: {pnl:,.2f} USD (сумма сделок: {nt})"
                print(msg1)
                print(msg2)
                print(msg3)
                print(msg4)
        else:
            msg = f"Текущий топ по {title}: ещё не найден"
            print(msg)
    for comb in param_combinations:
        # Динамическая распаковка comb с индексом для присвоения только включенным параметрам
        idx = 0
        # Для bull
        if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
            if TRADING_CONFIG['ENABLE_BULL_RSI']:
                BULL_RSI_PERIOD = comb[idx]
                idx += 1
                BULL_SMA_RSI_PERIOD = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
                BULL_STOCHRSI_K_PERIOD = comb[idx]
                idx += 1
                BULL_STOCHRSI_D_PERIOD = comb[idx]
                idx += 1
                BULL_STOCHRSI_RSI_PERIOD = comb[idx]
                idx += 1
                BULL_STOCHRSI_STOCH_PERIOD = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']:
                BULL_WILLIAMS_OVERBOUGHT_PERIOD = comb[idx]
                idx += 1
                BULL_WILLIAMS_OVERBOUGHT_LEVEL = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
                BULL_WILLIAMS_OVERSOLD_PERIOD = comb[idx]
                idx += 1
                BULL_WILLIAMS_OVERSOLD_LEVEL = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']:
                BULL_FEAR_GREED_LOW = comb[idx]
                idx += 1
        # Для bear
        if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
            if TRADING_CONFIG['ENABLE_BEAR_RSI']:
                BEAR_RSI_PERIOD = comb[idx]
                idx += 1
                BEAR_SMA_RSI_PERIOD = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
                BEAR_STOCHRSI_K_PERIOD = comb[idx]
                idx += 1
                BEAR_STOCHRSI_D_PERIOD = comb[idx]
                idx += 1
                BEAR_STOCHRSI_RSI_PERIOD = comb[idx]
                idx += 1
                BEAR_STOCHRSI_STOCH_PERIOD = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']:
                BEAR_WILLIAMS_OVERBOUGHT_PERIOD = comb[idx]
                idx += 1
                BEAR_WILLIAMS_OVERBOUGHT_LEVEL = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
                BEAR_WILLIAMS_OVERSOLD_PERIOD = comb[idx]
                idx += 1
                BEAR_WILLIAMS_OVERSOLD_LEVEL = comb[idx]
                idx += 1
            if TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']:
                BEAR_FEAR_GREED_HIGH = comb[idx]
                idx += 1
        current_comb += 1
        # Вывод текущих топ по каждому критерию
        display_top(top_win_percent, "проценту прибыльных сделок")
        display_top(top_profit_day_percent, "прибыли в день")
        display_top(top_max_drawdown, "максимальной просадке")
        # Вывод прогресса оптимизации
        elapsed = (datetime.now() - start_time).total_seconds()
        avg_time_per_comb = elapsed / current_comb if current_comb > 0 else 0
        remaining_combs = total_combinations - current_comb
        remaining_time_sec = avg_time_per_comb * remaining_combs
        remaining_hours = int(remaining_time_sec // 3600)
        remaining_min = int((remaining_time_sec % 3600) // 60)
        estimated_end_time = datetime.now() + timedelta(seconds=remaining_time_sec)
        msg_progress1 = f"\nПрогресс оптимизации: {current_comb}/{total_combinations} комбинаций выполнено."
        msg_progress2 = f"Оставшееся время: {remaining_hours} часов {remaining_min} минут."
        msg_progress3 = f"Предполагаемое время завершения: {estimated_end_time.strftime('%Y-%m-%d %H:%M')}"
        print(msg_progress1)
        print(msg_progress2)
        print(msg_progress3)
        # Обработка текущей комбинации с условным выводом msg_comb
        msg_comb = "\nОбработка комбинации:"
        # Для bull
        msg_comb += " BULL: "
        if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
            if TRADING_CONFIG['ENABLE_BULL_RSI']:
                msg_comb += f"RSI_PERIOD={BULL_RSI_PERIOD}, SMA_RSI_PERIOD={BULL_SMA_RSI_PERIOD}, "
            if TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
                msg_comb += f"STOCHRSI_K_PERIOD={BULL_STOCHRSI_K_PERIOD}, STOCHRSI_D_PERIOD={BULL_STOCHRSI_D_PERIOD}, STOCHRSI_RSI_PERIOD={BULL_STOCHRSI_RSI_PERIOD}, STOCHRSI_STOCH_PERIOD={BULL_STOCHRSI_STOCH_PERIOD}, "
            if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']:
                msg_comb += f"WILLIAMS_OVERBOUGHT_PERIOD={BULL_WILLIAMS_OVERBOUGHT_PERIOD}, WILLIAMS_OVERBOUGHT_LEVEL={BULL_WILLIAMS_OVERBOUGHT_LEVEL:.2f}, "
            if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
                msg_comb += f"WILLIAMS_OVERSOLD_PERIOD={BULL_WILLIAMS_OVERSOLD_PERIOD}, WILLIAMS_OVERSOLD_LEVEL={BULL_WILLIAMS_OVERSOLD_LEVEL:.2f}, "
            if TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']:
                msg_comb += f"FEAR_GREED_LOW={BULL_FEAR_GREED_LOW}"
            if msg_comb.endswith(", "):
                msg_comb = msg_comb.rstrip(", ") # Удаление лишней запятой
        else:
            msg_comb += "Нет включенных параметров для bull рынка"
        # Для bear
        msg_comb += " | BEAR: "
        if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
            if TRADING_CONFIG['ENABLE_BEAR_RSI']:
                msg_comb += f"RSI_PERIOD={BEAR_RSI_PERIOD}, SMA_RSI_PERIOD={BEAR_SMA_RSI_PERIOD}, "
            if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
                msg_comb += f"STOCHRSI_K_PERIOD={BEAR_STOCHRSI_K_PERIOD}, STOCHRSI_D_PERIOD={BEAR_STOCHRSI_D_PERIOD}, STOCHRSI_RSI_PERIOD={BEAR_STOCHRSI_RSI_PERIOD}, STOCHRSI_STOCH_PERIOD={BEAR_STOCHRSI_STOCH_PERIOD}, "
            if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']:
                msg_comb += f"WILLIAMS_OVERBOUGHT_PERIOD={BEAR_WILLIAMS_OVERBOUGHT_PERIOD}, WILLIAMS_OVERBOUGHT_LEVEL={BEAR_WILLIAMS_OVERBOUGHT_LEVEL:.2f}, "
            if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
                msg_comb += f"WILLIAMS_OVERSOLD_PERIOD={BEAR_WILLIAMS_OVERSOLD_PERIOD}, WILLIAMS_OVERSOLD_LEVEL={BEAR_WILLIAMS_OVERSOLD_LEVEL:.2f}, "
            if TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']:
                msg_comb += f"FEAR_GREED_HIGH={BEAR_FEAR_GREED_HIGH}"
            if msg_comb.endswith(", "):
                msg_comb = msg_comb.rstrip(", ") # Удаление лишней запятой
        else:
            msg_comb += "Нет включенных параметров для bear рынка"
        print(msg_comb)
        reset_globals()
        pnl, total_days, win_trades, num_trades, max_drawdown_percent = run_backtest()
        profit_per_day = pnl / total_days if total_days > 0 else 0.0
        profit_per_day_percent = (profit_per_day / INITIAL_BALANCE) * 100 if INITIAL_BALANCE > 0 else 0.0
        win_percent = (win_trades / num_trades * 100) if num_trades > 0 else 0.0
        loss_trades = num_trades - win_trades
        loss_percent = (loss_trades / num_trades * 100) if num_trades > 0 else 0.0
        if df_trades is not None and not df_trades.empty:
            closed_trades = df_trades[df_trades['Reason_Close'].notna()]
            if not closed_trades.empty:
                win_pnl = closed_trades[closed_trades['Net_PnL_USDT'] > 0]['Net_PnL_USDT'].sum()
                loss_pnl = closed_trades[closed_trades['Net_PnL_USDT'] <= 0]['Net_PnL_USDT'].sum()
            else:
                win_pnl = 0.0
                loss_pnl = 0.0
        else:
            logger.warning(f"df_trades не инициализирован или пуст для комбинации")
            win_pnl = 0.0
            loss_pnl = 0.0
            num_trades = 0
            win_trades = 0
            loss_trades = 0
        # Расчёт общей прибыли в процентах
        total_pnl_percent = (pnl / INITIAL_BALANCE * 100) if INITIAL_BALANCE > 0 else 0.0
        # Округление MDD до 2 знаков для топ по просадке
        mdd_rounded = round(max_drawdown_percent, 2)
        msg_result = f"Результат для комбинации: Процент прибыльных сделок={win_percent:.2f}%, Общая прибыль={pnl:.2f} USD, Прибыль в день: {profit_per_day_percent:.2f}% ({profit_per_day:.2f} USD), Максимальная просадка (округленная): {mdd_rounded:.2f}%"
        print(msg_result)
        # Сбор данных в буфер для CSV, только для колонок в columns_order
        row_data = {
            'Номер комбинации': current_comb,
            'Процент прибыльных сделок': round(win_percent, 2),
            'Максимальная просадка': round(max_drawdown_percent, 2),
            'Прибыль в день': round(profit_per_day_percent, 2),
            'Количество сделок': num_trades,
            'Прибыльные сделки': win_trades,
            'Убыточные сделки': loss_trades,
            'Общая прибыль': pnl,
            'Общая прибыль %': total_pnl_percent
        }
        # Добавление значений для bull, если соответствующие колонки в columns_order
        if 'BULL_RSI_PERIOD' in columns_order:
            row_data['BULL_RSI_PERIOD'] = BULL_RSI_PERIOD
        if 'BULL_SMA_RSI_PERIOD' in columns_order:
            row_data['BULL_SMA_RSI_PERIOD'] = BULL_SMA_RSI_PERIOD
        if 'BULL_STOCHRSI_K_PERIOD' in columns_order:
            row_data['BULL_STOCHRSI_K_PERIOD'] = BULL_STOCHRSI_K_PERIOD
        if 'BULL_STOCHRSI_D_PERIOD' in columns_order:
            row_data['BULL_STOCHRSI_D_PERIOD'] = BULL_STOCHRSI_D_PERIOD
        if 'BULL_STOCHRSI_RSI_PERIOD' in columns_order:
            row_data['BULL_STOCHRSI_RSI_PERIOD'] = BULL_STOCHRSI_RSI_PERIOD
        if 'BULL_STOCHRSI_STOCH_PERIOD' in columns_order:
            row_data['BULL_STOCHRSI_STOCH_PERIOD'] = BULL_STOCHRSI_STOCH_PERIOD
        if 'BULL_WILLIAMS_OVERBOUGHT_PERIOD' in columns_order:
            row_data['BULL_WILLIAMS_OVERBOUGHT_PERIOD'] = BULL_WILLIAMS_OVERBOUGHT_PERIOD
        if 'BULL_WILLIAMS_OVERBOUGHT_LEVEL' in columns_order:
            row_data['BULL_WILLIAMS_OVERBOUGHT_LEVEL'] = BULL_WILLIAMS_OVERBOUGHT_LEVEL
        if 'BULL_WILLIAMS_OVERSOLD_PERIOD' in columns_order:
            row_data['BULL_WILLIAMS_OVERSOLD_PERIOD'] = BULL_WILLIAMS_OVERSOLD_PERIOD
        if 'BULL_WILLIAMS_OVERSOLD_LEVEL' in columns_order:
            row_data['BULL_WILLIAMS_OVERSOLD_LEVEL'] = round(BULL_WILLIAMS_OVERSOLD_LEVEL, 2)
        if 'BULL_FEAR_GREED_LOW' in columns_order:
            row_data['BULL_FEAR_GREED_LOW'] = BULL_FEAR_GREED_LOW
        # Добавление значений для bear, если соответствующие колонки в columns_order
        if 'BEAR_RSI_PERIOD' in columns_order:
            row_data['BEAR_RSI_PERIOD'] = BEAR_RSI_PERIOD
        if 'BEAR_SMA_RSI_PERIOD' in columns_order:
            row_data['BEAR_SMA_RSI_PERIOD'] = BEAR_SMA_RSI_PERIOD
        if 'BEAR_STOCHRSI_K_PERIOD' in columns_order:
            row_data['BEAR_STOCHRSI_K_PERIOD'] = BEAR_STOCHRSI_K_PERIOD
        if 'BEAR_STOCHRSI_D_PERIOD' in columns_order:
            row_data['BEAR_STOCHRSI_D_PERIOD'] = BEAR_STOCHRSI_D_PERIOD
        if 'BEAR_STOCHRSI_RSI_PERIOD' in columns_order:
            row_data['BEAR_STOCHRSI_RSI_PERIOD'] = BEAR_STOCHRSI_RSI_PERIOD
        if 'BEAR_STOCHRSI_STOCH_PERIOD' in columns_order:
            row_data['BEAR_STOCHRSI_STOCH_PERIOD'] = BEAR_STOCHRSI_STOCH_PERIOD
        if 'BEAR_WILLIAMS_OVERBOUGHT_PERIOD' in columns_order:
            row_data['BEAR_WILLIAMS_OVERBOUGHT_PERIOD'] = BEAR_WILLIAMS_OVERBOUGHT_PERIOD
        if 'BEAR_WILLIAMS_OVERBOUGHT_LEVEL' in columns_order:
            row_data['BEAR_WILLIAMS_OVERBOUGHT_LEVEL'] = BEAR_WILLIAMS_OVERBOUGHT_LEVEL
        if 'BEAR_WILLIAMS_OVERSOLD_PERIOD' in columns_order:
            row_data['BEAR_WILLIAMS_OVERSOLD_PERIOD'] = BEAR_WILLIAMS_OVERSOLD_PERIOD
        if 'BEAR_WILLIAMS_OVERSOLD_LEVEL' in columns_order:
            row_data['BEAR_WILLIAMS_OVERSOLD_LEVEL'] = BEAR_WILLIAMS_OVERSOLD_LEVEL
        if 'BEAR_FEAR_GREED_HIGH' in columns_order:
            row_data['BEAR_FEAR_GREED_HIGH'] = BEAR_FEAR_GREED_HIGH
        optimization_buffer.append(row_data)
        # Периодическое сохранение буфера в CSV
        if len(optimization_buffer) >= buffer_save_interval:
            df_buffer = pd.DataFrame(optimization_buffer)
            # Форматирование колонок с запятыми как разделителями тысяч и округлением до 2 знаков
            df_buffer['Общая прибыль'] = df_buffer['Общая прибыль'].apply(lambda x: f"{x:,.2f}")
            df_buffer['Общая прибыль %'] = df_buffer['Общая прибыль %'].apply(lambda x: f"{x:,.2f}")
            df_buffer['Процент прибыльных сделок'] = df_buffer['Процент прибыльных сделок'].apply(lambda x: f"{x:.2f}")
            df_buffer['Максимальная просадка'] = df_buffer['Максимальная просадка'].apply(lambda x: f"{x:.2f}")
            df_buffer['Прибыль в день'] = df_buffer['Прибыль в день'].apply(lambda x: f"{x:.2f}")
            if 'BULL_WILLIAMS_OVERSOLD_LEVEL' in df_buffer.columns:
                df_buffer['BULL_WILLIAMS_OVERSOLD_LEVEL'] = df_buffer['BULL_WILLIAMS_OVERSOLD_LEVEL'].apply(lambda x: f"{x:.2f}")
            # Установка порядка колонок
            df_buffer = df_buffer[columns_order]
            df_buffer.to_csv(opt_csv_file, mode='a', header=first_save, index=False)
            if first_save:
                first_save = False
            optimization_buffer = [] # Очистка буфера после сохранения
            logger.info(f"Сохранено {buffer_save_interval} комбинаций в {opt_csv_file}")
        # Обновление топ-1 для win_percent (изменена сортировка: при равенстве win_percent выбирается по profit_per_day_percent desc)
        top_win_percent.append((win_percent, BULL_RSI_PERIOD, BULL_SMA_RSI_PERIOD, BULL_STOCHRSI_K_PERIOD, BULL_STOCHRSI_D_PERIOD, BULL_STOCHRSI_RSI_PERIOD, BULL_STOCHRSI_STOCH_PERIOD, BULL_WILLIAMS_OVERBOUGHT_PERIOD, BULL_WILLIAMS_OVERBOUGHT_LEVEL, BULL_WILLIAMS_OVERSOLD_PERIOD, BULL_WILLIAMS_OVERSOLD_LEVEL, BULL_FEAR_GREED_LOW, BEAR_RSI_PERIOD, BEAR_SMA_RSI_PERIOD, BEAR_STOCHRSI_K_PERIOD, BEAR_STOCHRSI_D_PERIOD, BEAR_STOCHRSI_RSI_PERIOD, BEAR_STOCHRSI_STOCH_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_LEVEL, BEAR_WILLIAMS_OVERSOLD_PERIOD, BEAR_WILLIAMS_OVERSOLD_LEVEL, BEAR_FEAR_GREED_HIGH, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, max_drawdown_percent, win_percent, profit_per_day_percent))
        top_win_percent = sorted(top_win_percent, key=lambda x: (x[0], x[32]), reverse=True)[:1]
        # Обновление топ-1 для profit_per_day_percent (расширено)
        top_profit_day_percent.append((profit_per_day_percent, BULL_RSI_PERIOD, BULL_SMA_RSI_PERIOD, BULL_STOCHRSI_K_PERIOD, BULL_STOCHRSI_D_PERIOD, BULL_STOCHRSI_RSI_PERIOD, BULL_STOCHRSI_STOCH_PERIOD, BULL_WILLIAMS_OVERBOUGHT_PERIOD, BULL_WILLIAMS_OVERBOUGHT_LEVEL, BULL_WILLIAMS_OVERSOLD_PERIOD, BULL_WILLIAMS_OVERSOLD_LEVEL, BULL_FEAR_GREED_LOW, BEAR_RSI_PERIOD, BEAR_SMA_RSI_PERIOD, BEAR_STOCHRSI_K_PERIOD, BEAR_STOCHRSI_D_PERIOD, BEAR_STOCHRSI_RSI_PERIOD, BEAR_STOCHRSI_STOCH_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_LEVEL, BEAR_WILLIAMS_OVERSOLD_PERIOD, BEAR_WILLIAMS_OVERSOLD_LEVEL, BEAR_FEAR_GREED_HIGH, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, max_drawdown_percent, win_percent, profit_per_day_percent))
        top_profit_day_percent = sorted(top_profit_day_percent, key=lambda x: x[0], reverse=True)[:1]
        # Обновление топ-1 для max_drawdown_percent (используется округленное значение; категория: по возрастанию MDD, при равенстве по убыванию win_percent, при равенстве win_percent по убыванию profit_per_day_percent)
        top_max_drawdown.append((mdd_rounded, BULL_RSI_PERIOD, BULL_SMA_RSI_PERIOD, BULL_STOCHRSI_K_PERIOD, BULL_STOCHRSI_D_PERIOD, BULL_STOCHRSI_RSI_PERIOD, BULL_STOCHRSI_STOCH_PERIOD, BULL_WILLIAMS_OVERBOUGHT_PERIOD, BULL_WILLIAMS_OVERBOUGHT_LEVEL, BULL_WILLIAMS_OVERSOLD_PERIOD, BULL_WILLIAMS_OVERSOLD_LEVEL, BULL_FEAR_GREED_LOW, BEAR_RSI_PERIOD, BEAR_SMA_RSI_PERIOD, BEAR_STOCHRSI_K_PERIOD, BEAR_STOCHRSI_D_PERIOD, BEAR_STOCHRSI_RSI_PERIOD, BEAR_STOCHRSI_STOCH_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_LEVEL, BEAR_WILLIAMS_OVERSOLD_PERIOD, BEAR_WILLIAMS_OVERSOLD_LEVEL, BEAR_FEAR_GREED_HIGH, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, mdd_rounded, win_percent, profit_per_day_percent))
        top_max_drawdown = sorted(top_max_drawdown, key=lambda x: (x[0], -x[31], -x[32]), reverse=False)[:1]
    # Сохранение оставшегося буфера в конце
    if optimization_buffer:
        df_buffer = pd.DataFrame(optimization_buffer)
        # Форматирование колонок с запятыми как разделителями тысяч и округлением до 2 знаков
        df_buffer['Общая прибыль'] = df_buffer['Общая прибыль'].apply(lambda x: f"{x:,.2f}")
        df_buffer['Общая прибыль %'] = df_buffer['Общая прибыль %'].apply(lambda x: f"{x:,.2f}")
        df_buffer['Процент прибыльных сделок'] = df_buffer['Процент прибыльных сделок'].apply(lambda x: f"{x:.2f}")
        df_buffer['Максимальная просадка'] = df_buffer['Максимальная просадка'].apply(lambda x: f"{x:.2f}")
        df_buffer['Прибыль в день'] = df_buffer['Прибыль в день'].apply(lambda x: f"{x:.2f}")
        if 'BULL_WILLIAMS_OVERSOLD_LEVEL' in df_buffer.columns:
            df_buffer['BULL_WILLIAMS_OVERSOLD_LEVEL'] = df_buffer['BULL_WILLIAMS_OVERSOLD_LEVEL'].apply(lambda x: f"{x:.2f}")
        # Установка порядка колонок
        df_buffer = df_buffer[columns_order]
        df_buffer.to_csv(opt_csv_file, mode='a', header=first_save, index=False)
        logger.info(f"Сохранено оставшееся {len(optimization_buffer)} комбинаций в {opt_csv_file}")
    logger.setLevel(original_level)
    # Вывод финальных топов в конце оптимизации
    print("\nФинальные топы:")
    display_top(top_win_percent, "проценту прибыльных сделок")
    display_top(top_profit_day_percent, "прибыли в день")
    display_top(top_max_drawdown, "максимальной просадке")
    if top_win_percent or top_profit_day_percent or top_max_drawdown:
        ENABLE_OPTIMIZATION = False
    else:
        msg_no_params = "Не удалось найти оптимальные параметры."
        print(msg_no_params)



def run_backtest():
    """ Запускает бэктест стратегии на исторических данных. """
    global current_balance, df_trades, pending_action, last_market_type
    try:
        if not ENABLE_OPTIMIZATION:
            logger.info("Начало бэктеста")
        # Загрузка и сохранение данных индекса страха и жадности
        load_fear_greed_data()
        df = load_data()
        if df is None:
            if not ENABLE_OPTIMIZATION:
                logger.error("Данные не загружены, завершение бэктеста")
            return 0.0, 1, 0, 0, 0.0
        # Расчёт индикаторов условно для bull параметров только если рынок включен
        if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True):
            if TRADING_CONFIG['ENABLE_BULL_RSI']:
                df['BULL_RSI'] = talib.RSI(df['close'].values, timeperiod=BULL_RSI_PERIOD)
                df['BULL_SMA_RSI'] = talib.SMA(df['BULL_RSI'].values, timeperiod=BULL_SMA_RSI_PERIOD)
            if TRADING_CONFIG['ENABLE_BULL_STOCHRSI']:
                bull_fastk, bull_fastd = talib.STOCHRSI(
                    df['close'].values,
                    timeperiod=BULL_STOCHRSI_RSI_PERIOD,
                    fastk_period=BULL_STOCHRSI_STOCH_PERIOD,
                    fastd_period=BULL_STOCHRSI_K_PERIOD,
                    fastd_matype=0
                )
                df['BULL_StochRSI_K'] = bull_fastd
                df['BULL_StochRSI_D'] = talib.SMA(df['BULL_StochRSI_K'].values, timeperiod=BULL_STOCHRSI_D_PERIOD)
            if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']:
                bull_ob_source = df['open'].values if BULL_WILLIAMS_OVERBOUGHT_SOURCE == 'Open' else df['close'].values
                df['BULL_Williams_R_Overbought'] = talib.WILLR(df['high'].values, df['low'].values, bull_ob_source, timeperiod=BULL_WILLIAMS_OVERBOUGHT_PERIOD)
            if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
                bull_os_source = df['open'].values if BULL_WILLIAMS_OVERSOLD_SOURCE == 'Open' else df['close'].values
                df['BULL_Williams_R_Oversold'] = talib.WILLR(df['high'].values, df['low'].values, bull_os_source, timeperiod=BULL_WILLIAMS_OVERSOLD_PERIOD)
        # Расчёт индикаторов условно для bear параметров только если рынок включен
        if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True):
            if TRADING_CONFIG['ENABLE_BEAR_RSI']:
                df['BEAR_RSI'] = talib.RSI(df['close'].values, timeperiod=BEAR_RSI_PERIOD)
                df['BEAR_SMA_RSI'] = talib.SMA(df['BEAR_RSI'].values, timeperiod=BEAR_SMA_RSI_PERIOD)
            if TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']:
                bear_fastk, bear_fastd = talib.STOCHRSI(
                    df['close'].values,
                    timeperiod=BEAR_STOCHRSI_RSI_PERIOD,
                    fastk_period=BEAR_STOCHRSI_STOCH_PERIOD,
                    fastd_period=BEAR_STOCHRSI_K_PERIOD,
                    fastd_matype=0
                )
                df['BEAR_StochRSI_K'] = bear_fastd
                df['BEAR_StochRSI_D'] = talib.SMA(df['BEAR_StochRSI_K'].values, timeperiod=BEAR_STOCHRSI_D_PERIOD)
            if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']:
                bear_ob_source = df['open'].values if BEAR_WILLIAMS_OVERBOUGHT_SOURCE == 'Open' else df['close'].values
                df['BEAR_Williams_R_Overbought'] = talib.WILLR(df['high'].values, df['low'].values, bear_ob_source, timeperiod=BEAR_WILLIAMS_OVERBOUGHT_PERIOD)
            if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
                bear_os_source = df['open'].values if BEAR_WILLIAMS_OVERSOLD_SOURCE == 'Open' else df['close'].values
                df['BEAR_Williams_R_Oversold'] = talib.WILLR(df['high'].values, df['low'].values, bear_os_source, timeperiod=BEAR_WILLIAMS_OVERSOLD_PERIOD)
        # Фильтрация данных по заданному периоду бэктеста после расчёта индикаторов
        if BACKTEST_START_DATE is not None:
            df = df[df.index >= BACKTEST_START_DATE]
        if BACKTEST_END_DATE is not None:
            df = df[df.index <= BACKTEST_END_DATE]
        # Теперь df содержит все необходимые данные
        df_combined = df.copy()
        if df_combined.empty:
            if not ENABLE_OPTIMIZATION:
                logger.error("После фильтрации получен пустой DataFrame")
            return 0.0, 1, 0, 0, 0.0
        opens = df_combined['open'].values
        closes = df_combined['close'].values
        lows = df_combined['low'].values
        highs = df_combined['high'].values
        times = df_combined.index
        bull_rsi_values = df_combined.get('BULL_RSI', pd.Series(np.nan, index=df_combined.index)).values
        bull_sma_rsi_values = df_combined.get('BULL_SMA_RSI', pd.Series(np.nan, index=df_combined.index)).values
        bull_stoch_k_values = df_combined.get('BULL_StochRSI_K', pd.Series(np.nan, index=df_combined.index)).values
        bull_stoch_d_values = df_combined.get('BULL_StochRSI_D', pd.Series(np.nan, index=df_combined.index)).values
        bull_williams_r_overbought_values = df_combined.get('BULL_Williams_R_Overbought', pd.Series(np.nan, index=df_combined.index)).values
        bull_williams_r_oversold_values = df_combined.get('BULL_Williams_R_Oversold', pd.Series(np.nan, index=df_combined.index)).values
        bear_rsi_values = df_combined.get('BEAR_RSI', pd.Series(np.nan, index=df_combined.index)).values
        bear_sma_rsi_values = df_combined.get('BEAR_SMA_RSI', pd.Series(np.nan, index=df_combined.index)).values
        bear_stoch_k_values = df_combined.get('BEAR_StochRSI_K', pd.Series(np.nan, index=df_combined.index)).values
        bear_stoch_d_values = df_combined.get('BEAR_StochRSI_D', pd.Series(np.nan, index=df_combined.index)).values
        bear_williams_r_overbought_values = df_combined.get('BEAR_Williams_R_Overbought', pd.Series(np.nan, index=df_combined.index)).values
        bear_williams_r_oversold_values = df_combined.get('BEAR_Williams_R_Oversold', pd.Series(np.nan, index=df_combined.index)).values
        if len(closes) == 0 or len(times) == 0:
            if not ENABLE_OPTIMIZATION:
                logger.error("Данные пусты или некорректны")
            return 0.0, 1, 0, 0, 0.0
        # Начальный индекс для анализа после фильтрации
        start_idx = 0
        if start_idx >= len(times):
            if not ENABLE_OPTIMIZATION:
                logger.error("Недостаточно данных для начала симуляции.")
            return 0.0, 1, 0, 0, 0.0
        if not ENABLE_OPTIMIZATION:
            logger.info(f"Начальный индекс для анализа: {start_idx}")
        # Динамическая инициализация headers и dtypes на основе включенных индикаторов
        headers = [
            'Trade_ID', 'Direction', 'Reason_Open', 'Entry_Time',
            'Reason_Close', 'Exit_Time',
            'Trade_Duration', 'Hours', 'Entry_Price', 'Exit_Price',
            'Position_Size', 'Position_Value', 'Leverage',
            'Net_PnL_USDT', 'Net_PnL_Percent',
            'Drawdown_USDT', 'Drawdown_Percent',
            'Balance', 'PnL_Type'
        ]
        dtypes = {
            'Trade_ID': str, 'Direction': str,
            'Reason_Open': str,
            'Entry_Time': 'datetime64[ns, UTC]',
            'Reason_Close': str,
            'Exit_Time': 'datetime64[ns, UTC]',
            'Trade_Duration': str, 'Hours': float,
            'Entry_Price': float, 'Exit_Price': float,
            'Position_Size': float, 'Position_Value': float,
            'Leverage': float, 'Net_PnL_USDT': float,
            'Net_PnL_Percent': float,
            'Drawdown_USDT': float, 'Drawdown_Percent': float,
            'Balance': float,
            'PnL_Type': str
        }
        # Добавление колонок для RSI, если включен хотя бы для одного рынка
        if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_RSI']) or \
           (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_RSI']):
            headers.extend(['Entry_RSI', 'Entry_SMA_RSI', 'Exit_RSI', 'Exit_SMA_RSI'])
            dtypes.update({'Entry_RSI': float, 'Entry_SMA_RSI': float, 'Exit_RSI': float, 'Exit_SMA_RSI': float})
        # Добавление колонок для StochRSI, если включен хотя бы для одного рынка
        if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or \
           (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']):
            headers.extend(['Entry_Stoch_K', 'Entry_Stoch_D', 'Exit_Stoch_K', 'Exit_Stoch_D'])
            dtypes.update({'Entry_Stoch_K': float, 'Entry_Stoch_D': float, 'Exit_Stoch_K': float, 'Exit_Stoch_D': float})
        # Добавление колонок для Williams %R Overbought, если включен хотя бы для одного рынка
        if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']) or \
           (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']):
            headers.extend(['Entry_Williams_R_Overbought', 'Exit_Williams_R_Overbought'])
            dtypes.update({'Entry_Williams_R_Overbought': float, 'Exit_Williams_R_Overbought': float})
        # Добавление колонок для Williams %R Oversold, если включен хотя бы для одного рынка
        if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']) or \
           (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']):
            headers.extend(['Entry_Williams_R_Oversold', 'Exit_Williams_R_Oversold'])
            dtypes.update({'Entry_Williams_R_Oversold': float, 'Exit_Williams_R_Oversold': float})
        # Добавление колонок для Fear & Greed, если включен хотя бы для одного рынка
        if (TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) and TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']) or \
           (TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) and TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']):
            headers.extend(['Entry_Fear_Greed', 'Exit_Fear_Greed'])
            dtypes.update({'Entry_Fear_Greed': float, 'Exit_Fear_Greed': float})
        # Инициализация df_trades с динамическими колонками
        df_trades = pd.DataFrame({col: pd.Series(dtype=dtypes[col]) for col in headers})
        model1_calculate_periods(df)
        model2_calculate_periods(df)
        for i in range(start_idx, len(closes)):
            current_time = times[i]
            current_open = opens[i]
            current_close = closes[i]
            current_market_type, close_change_date, open_change_date = hybrid_get_market_type_and_changes(current_time)
            # Immediate обработка смены типа рынка
            if close_change_date is not None and current_time >= close_change_date and last_market_type != current_market_type:
                logger.info(f"Смена типа рынка на {current_time} (с {last_market_type} на {current_market_type}) по min дате")
                close_all_trades_sim("market_type_change", current_time, current_open, with_reverse=False)
                pending_action = None # Очистка отложенного действия от предыдущего рынка
                pending_fear_greed = None # Очистка, если используется
                # Сброс переменных индикаторов
                global previous_rsi, previous_sma_rsi, current_rsi, current_sma_rsi
                global previous_stoch_k, previous_stoch_d, current_stoch_k, current_stoch_d
                global previous_williams_r_overbought, current_williams_r_overbought
                global previous_williams_r_oversold, current_williams_r_oversold
                previous_rsi = None
                previous_sma_rsi = None
                current_rsi = None
                current_sma_rsi = None
                previous_stoch_k = None
                previous_stoch_d = None
                current_stoch_k = None
                current_stoch_d = None
                previous_williams_r_overbought = None
                current_williams_r_overbought = None
                previous_williams_r_oversold = None
                current_williams_r_oversold = None
                logger.info("Сброшены все переменные индикаторов (RSI, StochRSI, Williams %R) для нового типа рынка")
            if open_change_date is not None and current_time >= open_change_date:
                close_all_trades_sim("market_type_change", current_time, current_open, with_reverse=True)
            # Проверка соответствия current_time с данными свечи
            if current_time not in df_combined.index:
                logger.warning(f"Время {current_time} не найдено в df_combined, пропуск действия")
                # Обновление last_market_type в конце, даже при пропуске
                last_market_type = current_market_type
                continue
            # Обработка отложенного действия (убраны market_change)
            if pending_action:
                if pending_action == "open_BULL_LONG_rsi":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_LONG по RSI на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_LONG', current_open, current_time, 'rsi_cross_up')
                elif pending_action == "open_BULL_LONG_oversold":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_LONG по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_LONG', current_open, current_time, 'williams_oversold')
                elif pending_action == "open_BULL_SHORT_rsi":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_SHORT по RSI на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_SHORT', current_open, current_time, 'rsi_cross_down')
                # НЕ УДАЛЯТЬ! Проверить логику. 
                elif pending_action == "open_BULL_LONG_stoch":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_LONG по StochRSI вверх на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_LONG', current_open, current_time, 'stoch_cross_up')
                elif pending_action == "open_BULL_SHORT_stoch":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_SHORT по StochRSI вниз на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_SHORT', current_open, current_time, 'stoch_cross_down')
                elif pending_action == "open_BULL_SHORT_overbought":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_SHORT по Williams overbought на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_SHORT', current_open, current_time, 'williams_overbought')
                elif pending_action == "open_BEAR_SHORT_rsi":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_SHORT по RSI на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_SHORT', current_open, current_time, 'rsi_cross_down')
                elif pending_action == "open_BEAR_LONG_rsi":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_LONG по RSI на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_LONG', current_open, current_time, 'rsi_cross_up')
                elif pending_action == "open_BEAR_SHORT_overbought":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_SHORT по Williams overbought на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_SHORT', current_open, current_time, 'williams_overbought')
                elif pending_action == "open_BEAR_LONG_oversold":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_LONG по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_LONG', current_open, current_time, 'williams_oversold')
                elif pending_action == "open_BEAR_SHORT_stoch":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_SHORT по StochRSI вниз на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_SHORT', current_open, current_time, 'stoch_cross_down')
                elif pending_action == "open_BEAR_LONG_stoch":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_LONG по StochRSI вверх на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_LONG', current_open, current_time, 'stoch_cross_up')
                elif pending_action in ["rsi_down", "rsi_up", "stoch_down", "stoch_up", "williams_overbought"]:
                    logger.info(f"Выполнение отложенного действия: Закрытие позиции ({pending_action}) по цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim(pending_action, current_time, current_open)
                elif pending_action == "close_BULL_SHORT_oversold":
                    logger.info(f"Выполнение отложенного действия: Закрытие BULL_SHORT по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim('williams_oversold', current_time, current_open)
                elif pending_action == "close_BEAR_SHORT_oversold":
                    logger.info(f"Выполнение отложенного действия: Закрытие BEAR_SHORT по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim('williams_oversold', current_time, current_open)
                pending_action = None
            # Проверка на свечу смены для пропуска Fear & Greed
            market_change_detected = last_market_type != current_market_type
            if current_market_type is None:
                last_market_type = current_market_type
                continue
            if current_market_type == 'bull':
                rsi = bull_rsi_values[i]
                sma_rsi = bull_sma_rsi_values[i]
                stoch_k = bull_stoch_k_values[i]
                stoch_d = bull_stoch_d_values[i]
                williams_r_overbought = bull_williams_r_overbought_values[i]
                williams_r_oversold = bull_williams_r_oversold_values[i]
            elif current_market_type == 'bear':
                rsi = bear_rsi_values[i]
                sma_rsi = bear_sma_rsi_values[i]
                stoch_k = bear_stoch_k_values[i]
                stoch_d = bear_stoch_d_values[i]
                williams_r_overbought = bear_williams_r_overbought_values[i]
                williams_r_oversold = bear_williams_r_oversold_values[i]
            else:
                rsi = np.nan
                sma_rsi = np.nan
                stoch_k = np.nan
                stoch_d = np.nan
                williams_r_overbought = np.nan
                williams_r_oversold = np.nan
            need_rsi = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_RSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_RSI'])
            need_stoch = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI'])
            need_williams_ob = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT'])
            need_williams_os = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD'])
            if (need_rsi and (np.isnan(rsi) or np.isnan(sma_rsi))) or \
               (need_stoch and (np.isnan(stoch_k) or np.isnan(stoch_d))) or \
               (need_williams_ob and np.isnan(williams_r_overbought)) or \
               (need_williams_os and np.isnan(williams_r_oversold)):
                if not ENABLE_OPTIMIZATION:
                    logger.warning(f"Пропуск итерации {i}: Недостаточно данных для включенных индикаторов (RSI={need_rsi}, Stoch={need_stoch}, Williams_OB={need_williams_ob}, Williams_OS={need_williams_os})")
                last_market_type = current_market_type
                continue
            if not ENABLE_OPTIMIZATION:
                logger.debug(f"Обработка итерации {i}: Время={current_time}, Открытие={current_open:.2f}, Закрытие={current_close:.2f}, RSI={rsi:.2f}, SMA_RSI={sma_rsi:.2f}, Stoch_K={stoch_k:.2f}, Stoch_D={stoch_d:.2f}, Williams_R_Overbought={williams_r_overbought:.2f}, Williams_R_Oversold={williams_r_oversold:.2f}")
            fear_greed_value = get_fear_greed_value(current_time)
            if fear_greed_value is not None and current_market_type is not None and not market_change_detected:
                if current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']:
                    if not active_trades:
                        if fear_greed_value <= BULL_FEAR_GREED_LOW and TRADING_CONFIG.get('ENABLE_BULL_LONG', True):
                            logger.info(f"Сигнал на открытие BULL_LONG по fear, выполнение на цене {current_open:.2f}")
                            simulate_open_trade('BULL_LONG', current_open, current_time, 'fear_low')
                    elif current_trade_type == 'BULL_SHORT':
                        if fear_greed_value <= BULL_FEAR_GREED_LOW:
                            logger.info(f"Сигнал на закрытие BULL_SHORT по fear, выполнение на цене {current_open:.2f}")
                            close_all_trades_sim("fear_low", current_time, current_open)
                elif current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']:
                    if not active_trades:
                        if fear_greed_value >= BEAR_FEAR_GREED_HIGH and TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True):
                            logger.info(f"Сигнал на открытие BEAR_SHORT по fear, выполнение на цене {current_open:.2f}")
                            simulate_open_trade('BEAR_SHORT', current_open, current_time, 'fear_high')
                    elif current_trade_type == 'BEAR_LONG':
                        if fear_greed_value >= BEAR_FEAR_GREED_HIGH:
                            logger.info(f"Сигнал на закрытие BEAR_LONG по fear, выполнение на цене {current_open:.2f}")
                            close_all_trades_sim("fear_high", current_time, current_open)
            check_signals(current_time, current_close, rsi, sma_rsi, stoch_k, stoch_d, williams_r_overbought, williams_r_oversold)
            for trade_id, trade in active_trades.items():
                if 'LONG' in trade['direction']:
                    trade['min_price'] = min(trade.get('min_price', trade['entry_price']), lows[i])
                elif 'SHORT' in trade['direction']:
                    trade['max_price'] = max(trade.get('max_price', trade['entry_price']), highs[i])
            last_market_type = current_market_type
            if not ENABLE_OPTIMIZATION and i % 100 == 0:
                logger.info(
                    f"Прогресс: Итерация {i}/{len(closes)}, Время: {current_time}, "
                    f"Открытие: {current_open:.2f}, Активных сделок: {len(active_trades)}"
                )
        if not ENABLE_OPTIMIZATION:
            logger.info("Завершение цикла обработки данных")
            logger.info(f"Финальный баланс: {current_balance:.2f} USDT")
        closed_trades = df_trades[df_trades['Reason_Close'].notna()].copy()
        if closed_trades.empty:
            if not ENABLE_OPTIMIZATION:
                logger.warning("Нет закрытых сделок, все метрики будут равны 0")
            total_pnl = 0.0
            num_trades = 0
            win_trades = 0
            loss_trades = 0
            avg_duration = 0.0
            win_pnl = 0.0
            loss_pnl = 0.0
            total_months = 0
            profitable_months = 0
            profitable_months_percent = 0.0
            profitable_months_pnl = 0.0
            loss_months = 0
            loss_months_percent = 0.0
            loss_months_pnl = 0.0
            min_balance = INITIAL_BALANCE
            max_balance = INITIAL_BALANCE
            min_drawdown_percent = 0.0
            min_drawdown_id = None
            max_drawdown_percent = 0.0
            max_drawdown_id = None
            min_drawdown_bull_percent = 0.0
            min_drawdown_id_bull = None
            max_drawdown_bull_percent = 0.0
            max_drawdown_id_bull = None
            min_drawdown_bear_percent = 0.0
            min_drawdown_id_bear = None
            max_drawdown_bear_percent = 0.0
            max_drawdown_id_bear = None
        else:
            total_pnl = closed_trades['Net_PnL_USDT'].sum()
            num_trades = len(closed_trades)
            win_trades = (closed_trades['Net_PnL_USDT'] > 0).sum()
            loss_trades = num_trades - win_trades
            avg_duration = closed_trades['Hours'].mean() if not closed_trades['Hours'].empty else 0.0
            win_pnl = closed_trades[closed_trades['Net_PnL_USDT'] > 0]['Net_PnL_USDT'].sum()
            loss_pnl = closed_trades[closed_trades['Net_PnL_USDT'] <= 0]['Net_PnL_USDT'].sum()
            closed_balances = closed_trades['Balance']
            min_balance = closed_balances.min() if not closed_balances.empty else INITIAL_BALANCE
            max_balance = closed_balances.max() if not closed_balances.empty else INITIAL_BALANCE
            min_drawdown_percent = closed_trades['Drawdown_Percent'].min() if not closed_trades['Drawdown_Percent'].empty else 0.0
            min_drawdown_id = closed_trades.loc[closed_trades['Drawdown_Percent'].idxmin(), 'Trade_ID'] if not closed_trades.empty else None
            max_drawdown_percent = closed_trades['Drawdown_Percent'].max() if not closed_trades['Drawdown_Percent'].empty else 0.0
            max_drawdown_id = closed_trades.loc[closed_trades['Drawdown_Percent'].idxmax(), 'Trade_ID'] if not closed_trades.empty else None
            bull_trades = closed_trades[closed_trades['Direction'].str.startswith('BULL')] if TRADING_CONFIG.get('ENABLE_BULL_MARKET', True) else pd.DataFrame()
            bear_trades = closed_trades[closed_trades['Direction'].str.startswith('BEAR')] if TRADING_CONFIG.get('ENABLE_BEAR_MARKET', True) else pd.DataFrame()
            if not bull_trades.empty:
                min_drawdown_bull_percent = bull_trades['Drawdown_Percent'].min() if not bull_trades['Drawdown_Percent'].empty else 0.0
                min_drawdown_id_bull = bull_trades.loc[bull_trades['Drawdown_Percent'].idxmin(), 'Trade_ID'] if not bull_trades.empty else None
                max_drawdown_bull_percent = bull_trades['Drawdown_Percent'].max() if not bull_trades['Drawdown_Percent'].empty else 0.0
                max_drawdown_id_bull = bull_trades.loc[bull_trades['Drawdown_Percent'].idxmax(), 'Trade_ID'] if not bull_trades.empty else None
            else:
                min_drawdown_bull_percent = 0.0
                min_drawdown_id_bull = None
                max_drawdown_bull_percent = 0.0
                max_drawdown_id_bull = None
            if not bear_trades.empty:
                min_drawdown_bear_percent = bear_trades['Drawdown_Percent'].min() if not bear_trades['Drawdown_Percent'].empty else 0.0
                min_drawdown_id_bear = bear_trades.loc[bear_trades['Drawdown_Percent'].idxmin(), 'Trade_ID'] if not bear_trades.empty else None
                max_drawdown_bear_percent = bear_trades['Drawdown_Percent'].max() if not bear_trades['Drawdown_Percent'].empty else 0.0
                max_drawdown_id_bear = bear_trades.loc[bear_trades['Drawdown_Percent'].idxmax(), 'Trade_ID'] if not bear_trades.empty else None
            else:
                min_drawdown_bear_percent = 0.0
                min_drawdown_id_bear = None
                max_drawdown_bear_percent = 0.0
                max_drawdown_id_bear = None
            if 'Exit_Time' in closed_trades.columns and closed_trades['Exit_Time'].notna().any():
                if not isinstance(closed_trades['Exit_Time'].dtype, pd.DatetimeTZDtype):
                    logger.warning(f"Некорректный тип данных в Exit_Time: {closed_trades['Exit_Time'].dtype}. Первые несколько значений: {closed_trades['Exit_Time'].head().to_list()}. Пытаемся преобразовать")
                    closed_trades['Exit_Time'] = pd.to_datetime(closed_trades['Exit_Time'], errors='coerce', utc=True)
                if not ENABLE_OPTIMIZATION:
                    logger.debug(f"Exit_Time в closed_trades после преобразования: {closed_trades['Exit_Time'].to_list()}")
                if closed_trades['Exit_Time'].notna().any():
                    closed_trades['Month'] = closed_trades['Exit_Time'].dt.tz_localize(None).dt.to_period('M')
                    monthly_pnl = closed_trades.groupby('Month')['Net_PnL_USDT'].sum()
                    total_months = len(monthly_pnl)
                    profitable_months = (monthly_pnl > 0).sum()
                    profitable_months_percent = (profitable_months / total_months * 100) if total_months > 0 else 0.0
                    profitable_months_pnl = monthly_pnl[monthly_pnl > 0].sum() if not monthly_pnl.empty else 0.0
                    loss_months = (monthly_pnl <= 0).sum()
                    loss_months_percent = (loss_months / total_months * 100) if total_months > 0 else 0.0
                    loss_months_pnl = monthly_pnl[monthly_pnl <= 0].sum() if not monthly_pnl.empty else 0.0
                else:
                    logger.warning("После преобразования Exit_Time все значения NaT")
                    total_months = 0
                    profitable_months = 0
                    profitable_months_percent = 0.0
                    profitable_months_pnl = 0.0
                    loss_months = 0
                    loss_months_percent = 0.0
                    loss_months_pnl = 0.0
            else:
                logger.warning("Exit_Time отсутствует или все значения NaT")
                total_months = 0
                profitable_months = 0
                profitable_months_percent = 0.0
                profitable_months_pnl = 0.0
                loss_months = 0
                loss_months_percent = 0.0
                loss_months_pnl = 0.0
        start_date = times[start_idx]
        end_date = times[-1]
        total_days = (end_date - start_date).days if (end_date - start_date).days > 0 else 1
        start_price = closes[start_idx]
        end_price = closes[-1]
        price_change_percent = ((end_price - start_price) / start_price) * 100 if start_price != 0 else 0
        trades_per_day = num_trades / total_days if total_days > 0 else 0
        profit_per_day = total_pnl / total_days if total_days > 0 else 0
        profit_per_day_percent = (profit_per_day / INITIAL_BALANCE) * 100 if INITIAL_BALANCE > 0 else 0
        trades_per_week = trades_per_day * 7
        profit_per_week = profit_per_day * 7
        profit_per_week_percent = profit_per_day_percent * 7
        trades_per_month = trades_per_day * 30
        profit_per_month = profit_per_day * 30
        profit_per_month_percent = profit_per_day_percent * 30
        if not ENABLE_OPTIMIZATION:
            df_trades.to_csv('backtest_trades.csv', index=False, float_format='%.2f')
            logger.info("Таблица сделок сохранена в backtest_trades.csv")
            logger.info("Вывод результатов бэктеста в терминал")
            print_backtest_results(
                start_date, end_date, total_days, num_trades, total_pnl,
                win_trades, loss_trades, avg_duration, start_price, end_price,
                price_change_percent, min_balance, max_balance, trades_per_day,
                profit_per_day, profit_per_day_percent, trades_per_week,
                profit_per_week, profit_per_week_percent, trades_per_month,
                profit_per_month, profit_per_month_percent,
                win_pnl, loss_pnl, total_months,
                profitable_months, profitable_months_percent, profitable_months_pnl,
                loss_months, loss_months_percent, loss_months_pnl,
                min_drawdown_percent, min_drawdown_id,
                max_drawdown_percent, max_drawdown_id,
                min_drawdown_bull_percent, min_drawdown_id_bull,
                max_drawdown_bull_percent, max_drawdown_id_bull,
                min_drawdown_bear_percent, min_drawdown_id_bear,
                max_drawdown_bear_percent, max_drawdown_id_bear
            )
            logger.info("Бэктест успешно завершён")
        return total_pnl, total_days, win_trades, num_trades, max_drawdown_percent
    except Exception as e:
        if not ENABLE_OPTIMIZATION:
            logger.error(f"Ошибка при выполнении бэктеста: {e}")
        SCRIPT_NAME = 'backtest_j4_94'
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        error_log_file = logs_dir / f'{SCRIPT_NAME}_backtest_error_log.txt'
        with open(error_log_file, "a", encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Ошибка бэктеста: {e}\n")
        return 0.0, 1, 0, 0, 0.0



if __name__ == "__main__":
    df = load_data()
    if ENABLE_OPTIMIZATION:
        optimize_params()
    else:
        run_backtest()


# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями
# Пиши каждую функцию кода в отдельном блоке для удобного копирования, перед каждым блоком конкретное описание изменений в коде
# Свое описание пиши строго за границами блока с кодом









