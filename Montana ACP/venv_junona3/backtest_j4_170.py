

# backtest_j4_170


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


TRADING_CONFIG = {
    'ENABLE_BULL_LONG': True,
    'ENABLE_BULL_SHORT': False, #False
    'ENABLE_BEAR_SHORT': True,
    'ENABLE_BEAR_LONG': False,
    'COMMISSION_RATE': 0.05 / 100,
    'ENABLE_LOGGING': True,
    'IMPULSE_ENTRY_PERCENT': 99,
    'BULL_LONG': {'LEVERAGE': 1.0},
    'BULL_SHORT': {'LEVERAGE': 1.0},
    'BEAR_SHORT': {'LEVERAGE': 1.0},
    'BEAR_LONG': {'LEVERAGE': 1.0},
    'MIN_DELTA_LIQUIDATION_LONG': 10.0,
    'MIN_DELTA_LIQUIDATION_SHORT': 10.0,
    'MAX_ACTIVE_TRADES': 1,
    'ENABLE_BULL_RSI': True,
    'ENABLE_BULL_STOCHRSI': True,
    'ENABLE_BULL_WILLIAMS_OVERBOUGHT': True,
    'ENABLE_BULL_WILLIAMS_OVERSOLD': True,
    'ENABLE_BULL_FEAR_GREED': True,

    'ENABLE_BEAR_RSI': True,
    'ENABLE_BEAR_STOCHRSI': True,
    'ENABLE_BEAR_WILLIAMS_OVERBOUGHT': True,
    'ENABLE_BEAR_WILLIAMS_OVERSOLD': True,
    'ENABLE_BEAR_FEAR_GREED': True,
}



# Константы для определения циклов рынка
START_DATE = datetime(2015, 1, 12, tzinfo=pytz.UTC)  # Начальная дата, теперь tz-aware
CYCLE_LENGTH = 1428  # Длина цикла в днях (152 недели бычьего + 52 недели медвежьего = 204 недели)
BULL_DAYS = 1064  # Длина бычьего рынка в днях (152 недели * 7 дней)


def get_market_type(date):
    # Убедимся, что входная дата tz-aware; если нет, добавим UTC
    if date.tzinfo is None:
        date = date.replace(tzinfo=pytz.UTC)
    delta = date - START_DATE
    delta_days = delta.days
    if delta_days < 0:
        return None  # Дата до начальной точки, обработка не требуется
    cycle_position = delta_days % CYCLE_LENGTH
    if cycle_position < BULL_DAYS:
        return 'bull'
    else:
        return 'bear'


# Глобальные переменные для бэктеста
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

INITIAL_BALANCE = 10000.0
SYMBOL = 'BTCUSDT'

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


# Параметры для bull
BULL_RSI_PERIOD = 20
BULL_SMA_RSI_PERIOD = 40
BULL_STOCHRSI_K_PERIOD = 20  # Smooth K
BULL_STOCHRSI_D_PERIOD = 48  # Smooth D
BULL_STOCHRSI_RSI_PERIOD = 10  # RSI Length
BULL_STOCHRSI_STOCH_PERIOD = 16  # Stochastic Length
BULL_WILLIAMS_OVERBOUGHT_PERIOD = 14
BULL_WILLIAMS_OVERBOUGHT_LEVEL = -1.0
BULL_WILLIAMS_OVERSOLD_PERIOD = 12
BULL_WILLIAMS_OVERSOLD_LEVEL = -85.8
BULL_FEAR_GREED_LOW = 26

# Параметры для bear
BEAR_RSI_PERIOD = 10
BEAR_SMA_RSI_PERIOD = 45
BEAR_STOCHRSI_K_PERIOD = 20  # Smooth K
BEAR_STOCHRSI_D_PERIOD = 48  # Smooth D
BEAR_STOCHRSI_RSI_PERIOD = 10  # RSI Length
BEAR_STOCHRSI_STOCH_PERIOD = 16  # Stochastic Length
BEAR_WILLIAMS_OVERBOUGHT_PERIOD = 6
BEAR_WILLIAMS_OVERBOUGHT_LEVEL = -13.0
BEAR_WILLIAMS_OVERSOLD_PERIOD = 18
BEAR_WILLIAMS_OVERSOLD_LEVEL = -93.30
BEAR_FEAR_GREED_HIGH = 52




# Cycle 2 - 4 total
BACKTEST_START_DATE = datetime(2018, 1, 1, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
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
# BACKTEST_START_DATE = datetime(2021, 11, 8, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2022, 11, 14, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона


# Cycle 4 bull
# BACKTEST_START_DATE = datetime(2022, 11, 8, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
# BACKTEST_END_DATE = datetime(2026,11, 7, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона


ENABLE_OPTIMIZATION = True  # True / False

# Параметры оптимизации для bull
BULL_RSI_MIN = 10
BULL_RSI_MAX = 20
BULL_RSI_STEP = 1
BULL_SMA_MIN = 20
BULL_SMA_MAX = 40
BULL_SMA_STEP = 1

BULL_STOCHRSI_K_MIN = 20
BULL_STOCHRSI_K_MAX = 20
BULL_STOCHRSI_K_STEP = 2
BULL_STOCHRSI_D_MIN = 48
BULL_STOCHRSI_D_MAX = 48
BULL_STOCHRSI_D_STEP = 2
BULL_STOCHRSI_RSI_MIN = 10
BULL_STOCHRSI_RSI_MAX = 10
BULL_STOCHRSI_RSI_STEP = 2
BULL_STOCHRSI_STOCH_MIN = 16
BULL_STOCHRSI_STOCH_MAX = 16
BULL_STOCHRSI_STOCH_STEP = 2

BULL_WILLIAMS_OVERBOUGHT_PERIOD_MIN = 14
BULL_WILLIAMS_OVERBOUGHT_PERIOD_MAX = 14
BULL_WILLIAMS_OVERBOUGHT_PERIOD_STEP = 1
BULL_WILLIAMS_OVERBOUGHT_LEVEL_MIN = -1.0
BULL_WILLIAMS_OVERBOUGHT_LEVEL_MAX = -1.0
BULL_WILLIAMS_OVERBOUGHT_LEVEL_STEP = 1

BULL_WILLIAMS_OVERSOLD_PERIOD_MIN = 12
BULL_WILLIAMS_OVERSOLD_PERIOD_MAX = 12
BULL_WILLIAMS_OVERSOLD_PERIOD_STEP = 1
BULL_WILLIAMS_OVERSOLD_LEVEL_MIN = -86.8
BULL_WILLIAMS_OVERSOLD_LEVEL_MAX = -86.8
BULL_WILLIAMS_OVERSOLD_LEVEL_STEP = 1

BULL_FEAR_GREED_LOW_MIN = 26
BULL_FEAR_GREED_LOW_MAX = 26
BULL_FEAR_GREED_LOW_STEP = 1

# Параметры оптимизации для bear
BEAR_RSI_MIN = 10
BEAR_RSI_MAX = 10
BEAR_RSI_STEP = 1
BEAR_SMA_MIN = 45
BEAR_SMA_MAX = 45
BEAR_SMA_STEP = 1

BEAR_STOCHRSI_K_MIN = 20
BEAR_STOCHRSI_K_MAX = 20
BEAR_STOCHRSI_K_STEP = 2
BEAR_STOCHRSI_D_MIN = 48
BEAR_STOCHRSI_D_MAX = 48
BEAR_STOCHRSI_D_STEP = 2
BEAR_STOCHRSI_RSI_MIN = 10
BEAR_STOCHRSI_RSI_MAX = 10
BEAR_STOCHRSI_RSI_STEP = 2
BEAR_STOCHRSI_STOCH_MIN = 16
BEAR_STOCHRSI_STOCH_MAX = 16
BEAR_STOCHRSI_STOCH_STEP = 2

BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MIN = 6
BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MAX = 6
BEAR_WILLIAMS_OVERBOUGHT_PERIOD_STEP = 1
BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MIN = -13.0
BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MAX = -13.0
BEAR_WILLIAMS_OVERBOUGHT_LEVEL_STEP = 1
BEAR_WILLIAMS_OVERSOLD_PERIOD_MIN = 18
BEAR_WILLIAMS_OVERSOLD_PERIOD_MAX = 18
BEAR_WILLIAMS_OVERSOLD_PERIOD_STEP = 1
BEAR_WILLIAMS_OVERSOLD_LEVEL_MIN = -93.30
BEAR_WILLIAMS_OVERSOLD_LEVEL_MAX = -93.30
BEAR_WILLIAMS_OVERSOLD_LEVEL_STEP = 1

BEAR_FEAR_GREED_HIGH_MIN = 52
BEAR_FEAR_GREED_HIGH_MAX = 52
BEAR_FEAR_GREED_HIGH_STEP = 2


# Глобальные переменные для бэктеста
current_balance = INITIAL_BALANCE
df_trades = None
last_market_type = None


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
        # Для таймфрейма > 1 дня определяем понедельник последней завершенной свечи
        days_since_start = (date - START_DATE).days
        completed_periods = days_since_start // timeframe_days
        if completed_periods <= 0:
            return None  # Нет завершенной прошлой свечи
        previous_candle = completed_periods - 1
        target_date = START_DATE + timedelta(days=previous_candle * timeframe_days)
        # Корректируем дату на понедельник
        days_to_monday = target_date.weekday()  # 0 = понедельник, 6 = воскресенье
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



def simulate_open_trade(trade_type, entry_price, entry_time, reason_open, balance_percent=TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']):
    """
    Симулирует открытие торговой позиции.
    """
    global next_trade_id, active_trades, current_balance, current_trade_type, df_trades
    with trades_lock:
        try:
            if len(active_trades) >= TRADING_CONFIG['MAX_ACTIVE_TRADES']:
                logger.warning("Достигнут лимит активных сделок")
                return
            # Расчёт объёма позиции на основе текущего баланса
            position_value = (current_balance * balance_percent / 100)
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
                f"Размер={size:.6f} BTC, Маржа={position_value:.2f} USDT, "
                f"Баланс после открытия={current_balance:.2f} USDT"
            )
            # Получаем значение индекса страха при открытии
            fear_greed_value = get_fear_greed_value(entry_time)
            # Добавление записи в df_trades при открытии
            new_row = {
                'Trade_ID': str(trade_id),
                'Direction': trade_type,
                'Reason_Open': reason_open,
                'Entry_Time': entry_time,
                'Entry_RSI': float(current_rsi) if current_rsi is not None else np.nan,
                'Entry_SMA_RSI': float(current_sma_rsi) if current_sma_rsi is not None else np.nan,
                'Entry_Stoch_K': float(current_stoch_k) if current_stoch_k is not None else np.nan,
                'Entry_Stoch_D': float(current_stoch_d) if current_stoch_d is not None else np.nan,
                'Entry_Williams_R_Overbought': float(current_williams_r_overbought) if current_williams_r_overbought is not None else np.nan,
                'Entry_Williams_R_Oversold': float(current_williams_r_oversold) if current_williams_r_oversold is not None else np.nan,
                'Entry_Fear_Greed': float(fear_greed_value) if fear_greed_value is not None else np.nan,
                'Reason_Close': np.nan,
                'Exit_Time': pd.NaT,
                'Exit_RSI': np.nan,
                'Exit_SMA_RSI': np.nan,
                'Exit_Stoch_K': np.nan,
                'Exit_Stoch_D': np.nan,
                'Exit_Williams_R_Overbought': np.nan,
                'Exit_Williams_R_Oversold': np.nan,
                'Exit_Fear_Greed': np.nan,
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
            # Обновление записи в df_trades при закрытии
            mask = (df_trades['Trade_ID'] == str(trade_id)) & (df_trades['Reason_Close'].isna())
            if mask.any():
                df_trades.loc[mask, 'Reason_Close'] = reason
                df_trades.loc[mask, 'Exit_Time'] = exit_time
                df_trades.loc[mask, 'Exit_RSI'] = float(current_rsi) if current_rsi is not None else np.nan
                df_trades.loc[mask, 'Exit_SMA_RSI'] = float(current_sma_rsi) if current_sma_rsi is not None else np.nan
                df_trades.loc[mask, 'Exit_Stoch_K'] = float(current_stoch_k) if current_stoch_k is not None else np.nan
                df_trades.loc[mask, 'Exit_Stoch_D'] = float(current_stoch_d) if current_stoch_d is not None else np.nan
                df_trades.loc[mask, 'Exit_Williams_R_Overbought'] = float(current_williams_r_overbought) if current_williams_r_overbought is not None else np.nan
                df_trades.loc[mask, 'Exit_Williams_R_Oversold'] = float(current_williams_r_oversold) if current_williams_r_oversold is not None else np.nan
                df_trades.loc[mask, 'Exit_Fear_Greed'] = float(fear_greed_value) if fear_greed_value is not None else np.nan
                df_trades.loc[mask, 'Trade_Duration'] = duration_str
                df_trades.loc[mask, 'Hours'] = duration_hours
                df_trades.loc[mask, 'Exit_Price'] = float(exit_price)
                df_trades.loc[mask, 'Net_PnL_USDT'] = float(net_pnl)
                df_trades.loc[mask, 'Net_PnL_Percent'] = float(net_pnl_percent)
                df_trades.loc[mask, 'Drawdown_USDT'] = float(drawdown_usdt)
                df_trades.loc[mask, 'Drawdown_Percent'] = float(drawdown_percent)
                df_trades.loc[mask, 'Balance'] = float(current_balance)
                df_trades.loc[mask, 'PnL_Type'] = 'Profit' if net_pnl > 0 else 'Loss'
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
        current_market_type = get_market_type(current_time)
        if current_market_type is None:
            logger.warning("Тип рынка не определён для текущей даты")
            return
        # Проверка смены типа рынка
        if last_market_type is not None and last_market_type != current_market_type:
            logger.info(f"Смена типа рынка с {last_market_type} на {current_market_type}. Установка pending_action для закрытия всех сделок.")
            pending_action = "market_type_change"
            last_market_type = current_market_type
            return # Выходим, чтобы обработать закрытие перед новыми сигналами
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
                # Проверка Williams %R oversold с защитой от None и np.nan
                if (TRADING_CONFIG.get('ENABLE_BULL_LONG', True) and 
                    TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD'] and 
                    current_williams_r_oversold is not None and 
                    not np.isnan(current_williams_r_oversold) and 
                    current_williams_r_oversold <= BULL_WILLIAMS_OVERSOLD_LEVEL):
                    logger.info("Сигнал на открытие BULL_LONG по Williams %R oversold, установка pending_action")
                    pending_action = "open_BULL_LONG_oversold"
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





def close_all_trades_sim(reason, exit_time, current_price):
    """
    Симулирует закрытие всех активных позиций с разворотом на основе сигналов RSI и отдельно при смене типа рынка.
    """
    global active_trades, current_balance, current_trade_type
    with trades_lock:
        if not active_trades:
            logger.info("⚪ Нет активных сделок для закрытия")
            return
        # Запоминаем direction последней сделки перед закрытием (предполагаем одну активную)
        last_trade_direction = next(iter(active_trades.values()))['direction'] if active_trades else None
        for trade_id in list(active_trades.keys()):
            simulate_close_trade(trade_id, current_price, exit_time, reason)
        current_trade_type = None
        # Логика разворота сделок после закрытия
        current_market_type = get_market_type(exit_time)
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
            if reason == "market_type_change" and TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True):
                logger.info(f"📉 Разворот на медвежьем рынке: Открытие BEAR_SHORT по цене {current_price:.2f}")
                simulate_open_trade('BEAR_SHORT', current_price, exit_time, 'market_type_change')



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
    max_drawdown_percent=0.0, max_drawdown_id=None
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
    # Формируем строки результатов в требуемом формате
    results = [
        "РЕЗУЛЬТАТЫ БЭКТЕСТА",
        "",
        "------------- ПАРАМЕТРЫ СТРАТЕГИИ ------------|",
        f"INITIAL_BALANCE: {INITIAL_BALANCE:,.2f} USD",
        f"ENABLE_BULL_LONG: {TRADING_CONFIG['ENABLE_BULL_LONG']}",
        f"BULL_LONG: LEVERAGE: {TRADING_CONFIG['BULL_LONG']['LEVERAGE']}",
        f"ENABLE_BULL_SHORT: {TRADING_CONFIG['ENABLE_BULL_SHORT']}",
        f"BULL_SHORT: LEVERAGE: {TRADING_CONFIG['BULL_SHORT']['LEVERAGE']}",
        f"ENABLE_BEAR_SHORT: {TRADING_CONFIG['ENABLE_BEAR_SHORT']}",
        f"BEAR_SHORT: LEVERAGE: {TRADING_CONFIG['BEAR_SHORT']['LEVERAGE']}",
        f"ENABLE_BEAR_LONG: {TRADING_CONFIG['ENABLE_BEAR_LONG']}",
        f"BEAR_LONG: LEVERAGE: {TRADING_CONFIG['BEAR_LONG']['LEVERAGE']}",
        "",
        f"GLOBAL_TIMEFRAME: {GLOBAL_TIMEFRAME}",
        "",
        "------------- BULL ПАРАМЕТРЫ ------------|",
        f"ENABLE_BULL_RSI: {TRADING_CONFIG['ENABLE_BULL_RSI']}",
        f"  BULL_RSI_PERIOD: {BULL_RSI_PERIOD}",
        f"  BULL_SMA_RSI_PERIOD: {BULL_SMA_RSI_PERIOD}",
        f"ENABLE_BULL_STOCHRSI: {TRADING_CONFIG['ENABLE_BULL_STOCHRSI']}",
        f"  BULL_STOCHRSI_K_PERIOD: {BULL_STOCHRSI_K_PERIOD}",
        f"  BULL_STOCHRSI_D_PERIOD: {BULL_STOCHRSI_D_PERIOD}",
        f"  BULL_STOCHRSI_RSI_PERIOD: {BULL_STOCHRSI_RSI_PERIOD}",
        f"  BULL_STOCHRSI_STOCH_PERIOD: {BULL_STOCHRSI_STOCH_PERIOD}",
        f"ENABLE_BULL_WILLIAMS_OVERBOUGHT: {TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']}",
        f"  BULL_WILLIAMS_OVERBOUGHT_PERIOD: {BULL_WILLIAMS_OVERBOUGHT_PERIOD}",
        f"  BULL_WILLIAMS_OVERBOUGHT_LEVEL: {BULL_WILLIAMS_OVERBOUGHT_LEVEL:.2f}",
        f"ENABLE_BULL_WILLIAMS_OVERSOLD: {TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']}",
        f"  BULL_WILLIAMS_OVERSOLD_PERIOD: {BULL_WILLIAMS_OVERSOLD_PERIOD}",
        f"  BULL_WILLIAMS_OVERSOLD_LEVEL: {BULL_WILLIAMS_OVERSOLD_LEVEL:.2f}",
        f"ENABLE_BULL_FEAR_GREED: {TRADING_CONFIG['ENABLE_BULL_FEAR_GREED']}",
        f"  BULL_FEAR_GREED_LOW: {BULL_FEAR_GREED_LOW}",
        "",
        "------------- BEAR ПАРАМЕТРЫ ------------|",
        f"ENABLE_BEAR_RSI: {TRADING_CONFIG['ENABLE_BEAR_RSI']}",
        f"  BEAR_RSI_PERIOD: {BEAR_RSI_PERIOD}",
        f"  BEAR_SMA_RSI_PERIOD: {BEAR_SMA_RSI_PERIOD}",
        f"ENABLE_BEAR_STOCHRSI: {TRADING_CONFIG['ENABLE_BEAR_STOCHRSI']}",
        f"  BEAR_STOCHRSI_K_PERIOD: {BEAR_STOCHRSI_K_PERIOD}",
        f"  BEAR_STOCHRSI_D_PERIOD: {BEAR_STOCHRSI_D_PERIOD}",
        f"  BEAR_STOCHRSI_RSI_PERIOD: {BEAR_STOCHRSI_RSI_PERIOD}",
        f"  BEAR_STOCHRSI_STOCH_PERIOD: {BEAR_STOCHRSI_STOCH_PERIOD}",
        f"ENABLE_BEAR_WILLIAMS_OVERBOUGHT: {TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT']}",
        f"  BEAR_WILLIAMS_OVERBOUGHT_PERIOD: {BEAR_WILLIAMS_OVERBOUGHT_PERIOD}",
        f"  BEAR_WILLIAMS_OVERBOUGHT_LEVEL: {BEAR_WILLIAMS_OVERBOUGHT_LEVEL:.2f}",
        f"ENABLE_BEAR_WILLIAMS_OVERSOLD: {TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']}",
        f"  BEAR_WILLIAMS_OVERSOLD_PERIOD: {BEAR_WILLIAMS_OVERSOLD_PERIOD}",
        f"  BEAR_WILLIAMS_OVERSOLD_LEVEL: {BEAR_WILLIAMS_OVERSOLD_LEVEL:.2f}",
        f"ENABLE_BEAR_FEAR_GREED: {TRADING_CONFIG['ENABLE_BEAR_FEAR_GREED']}",
        f"  BEAR_FEAR_GREED_HIGH: {BEAR_FEAR_GREED_HIGH}",
        "----------------------------------------------|",
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
        f"Минимальная просадка: {min_drawdown_percent:,.2f}% ({min_drawdown_id})" if min_drawdown_id else f"Минимальная просадка: {min_drawdown_percent:,.2f}%",
        f"Максимальная просадка: {max_drawdown_percent:,.2f}% ({max_drawdown_id})" if max_drawdown_id else f"Максимальная просадка: {max_drawdown_percent:,.2f}%",
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
    import sys
    from datetime import datetime, timedelta
    import time
    import numpy as np
    from itertools import product # Добавлено для генерации комбинаций
    global BULL_RSI_PERIOD, BULL_SMA_RSI_PERIOD, BULL_STOCHRSI_RSI_PERIOD, BULL_STOCHRSI_STOCH_PERIOD, BULL_STOCHRSI_K_PERIOD, BULL_STOCHRSI_D_PERIOD, ENABLE_OPTIMIZATION
    global BULL_WILLIAMS_OVERBOUGHT_PERIOD, BULL_WILLIAMS_OVERBOUGHT_LEVEL
    global BULL_WILLIAMS_OVERSOLD_PERIOD, BULL_WILLIAMS_OVERSOLD_LEVEL
    global BEAR_RSI_PERIOD, BEAR_SMA_RSI_PERIOD, BEAR_STOCHRSI_RSI_PERIOD, BEAR_STOCHRSI_STOCH_PERIOD, BEAR_STOCHRSI_K_PERIOD, BEAR_STOCHRSI_D_PERIOD
    global BEAR_WILLIAMS_OVERBOUGHT_PERIOD, BEAR_WILLIAMS_OVERBOUGHT_LEVEL
    global BEAR_WILLIAMS_OVERSOLD_PERIOD, BEAR_WILLIAMS_OVERSOLD_LEVEL
    global BULL_FEAR_GREED_LOW, BEAR_FEAR_GREED_HIGH
    # Списки для топ-1 по критериям (расширены для новых параметров Fear & Greed)
    top_win_percent = [] # (win_percent, bull_rsi, bull_sma, bull_sr, bull_st, bull_sk, bull_sd, bull_wp_ob, bull_wl_ob, bull_wp_os, bull_wl_os, bull_fear_low, bear_rsi, bear_sma, bear_sr, bear_st, bear_sk, bear_sd, bear_wp_ob, bear_wl_ob, bear_wp_os, bear_wl_os, bear_fear_high, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, win_percent, profit_per_day_percent)
    top_profit_day_percent = []
    top_max_drawdown = [] # (max_drawdown_percent, bull_rsi, ..., profit_per_day_percent) - категория по максимальной просадке
    original_level = logger.level
    logger.setLevel(logging.ERROR)
    SCRIPT_NAME = 'backtest_j4_94'
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    opt_log_file = logs_dir / f'{SCRIPT_NAME}_optimization_log.txt'
    # Открываем файл для логов оптимизации
    with open(opt_log_file, 'w', encoding='utf-8') as opt_log:
        # Генерация диапазонов для bull и bear
        bull_rsi_range = range(BULL_RSI_MIN, BULL_RSI_MAX + 1, BULL_RSI_STEP)
        bull_sma_range = range(BULL_SMA_MIN, BULL_SMA_MAX + 1, BULL_SMA_STEP)
        bull_stoch_rsi_range = range(BULL_STOCHRSI_RSI_MIN, BULL_STOCHRSI_RSI_MAX + 1, BULL_STOCHRSI_RSI_STEP)
        bull_stoch_range = range(BULL_STOCHRSI_STOCH_MIN, BULL_STOCHRSI_STOCH_MAX + 1, BULL_STOCHRSI_STOCH_STEP)
        bull_k_range = range(BULL_STOCHRSI_K_MIN, BULL_STOCHRSI_K_MAX + 1, BULL_STOCHRSI_K_STEP)
        bull_d_range = range(BULL_STOCHRSI_D_MIN, BULL_STOCHRSI_D_MAX + 1, BULL_STOCHRSI_D_STEP)
        bull_wp_ob_range = range(BULL_WILLIAMS_OVERBOUGHT_PERIOD_MIN, BULL_WILLIAMS_OVERBOUGHT_PERIOD_MAX + 1, BULL_WILLIAMS_OVERBOUGHT_PERIOD_STEP)
        bull_wl_ob_range = np.arange(BULL_WILLIAMS_OVERBOUGHT_LEVEL_MIN, BULL_WILLIAMS_OVERBOUGHT_LEVEL_MAX + BULL_WILLIAMS_OVERBOUGHT_LEVEL_STEP, BULL_WILLIAMS_OVERBOUGHT_LEVEL_STEP)
        bull_wp_os_range = range(BULL_WILLIAMS_OVERSOLD_PERIOD_MIN, BULL_WILLIAMS_OVERSOLD_PERIOD_MAX + 1, BULL_WILLIAMS_OVERSOLD_PERIOD_STEP)
        bull_wl_os_range = np.arange(BULL_WILLIAMS_OVERSOLD_LEVEL_MIN, BULL_WILLIAMS_OVERSOLD_LEVEL_MAX + BULL_WILLIAMS_OVERSOLD_LEVEL_STEP, BULL_WILLIAMS_OVERSOLD_LEVEL_STEP)
        bull_fear_low_range = range(BULL_FEAR_GREED_LOW_MIN, BULL_FEAR_GREED_LOW_MAX + 1, BULL_FEAR_GREED_LOW_STEP)
        bear_rsi_range = range(BEAR_RSI_MIN, BEAR_RSI_MAX + 1, BEAR_RSI_STEP)
        bear_sma_range = range(BEAR_SMA_MIN, BEAR_SMA_MAX + 1, BEAR_SMA_STEP)
        bear_stoch_rsi_range = range(BEAR_STOCHRSI_RSI_MIN, BEAR_STOCHRSI_RSI_MAX + 1, BEAR_STOCHRSI_RSI_STEP)
        bear_stoch_range = range(BEAR_STOCHRSI_STOCH_MIN, BEAR_STOCHRSI_STOCH_MAX + 1, BEAR_STOCHRSI_STOCH_STEP)
        bear_k_range = range(BEAR_STOCHRSI_K_MIN, BEAR_STOCHRSI_K_MAX + 1, BEAR_STOCHRSI_K_STEP)
        bear_d_range = range(BEAR_STOCHRSI_D_MIN, BEAR_STOCHRSI_D_MAX + 1, BEAR_STOCHRSI_D_STEP)
        bear_wp_ob_range = range(BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MIN, BEAR_WILLIAMS_OVERBOUGHT_PERIOD_MAX + 1, BEAR_WILLIAMS_OVERBOUGHT_PERIOD_STEP)
        bear_wl_ob_range = np.arange(BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MIN, BEAR_WILLIAMS_OVERBOUGHT_LEVEL_MAX + BEAR_WILLIAMS_OVERBOUGHT_LEVEL_STEP, BEAR_WILLIAMS_OVERBOUGHT_LEVEL_STEP)
        bear_wp_os_range = range(BEAR_WILLIAMS_OVERSOLD_PERIOD_MIN, BEAR_WILLIAMS_OVERSOLD_PERIOD_MAX + 1, BEAR_WILLIAMS_OVERSOLD_PERIOD_STEP)
        bear_wl_os_range = np.arange(BEAR_WILLIAMS_OVERSOLD_LEVEL_MIN, BEAR_WILLIAMS_OVERSOLD_LEVEL_MAX + BEAR_WILLIAMS_OVERSOLD_LEVEL_STEP, BEAR_WILLIAMS_OVERSOLD_LEVEL_STEP)
        bear_fear_high_range = range(BEAR_FEAR_GREED_HIGH_MIN, BEAR_FEAR_GREED_HIGH_MAX + 1, BEAR_FEAR_GREED_HIGH_STEP)
  
        # Генерация всех комбинаций с product (добавлены bull_fear_low и bear_fear_high)
        param_combinations = product(
            bull_rsi_range, bull_sma_range, bull_stoch_rsi_range, bull_stoch_range, bull_k_range, bull_d_range,
            bull_wp_ob_range, bull_wl_ob_range, bull_wp_os_range, bull_wl_os_range, bull_fear_low_range,
            bear_rsi_range, bear_sma_range, bear_stoch_rsi_range, bear_stoch_range, bear_k_range, bear_d_range,
            bear_wp_ob_range, bear_wl_ob_range, bear_wp_os_range, bear_wl_os_range, bear_fear_high_range
        )
        total_combinations = (len(bull_rsi_range) * len(bull_sma_range) * len(bull_stoch_rsi_range) * len(bull_stoch_range) * len(bull_k_range) * len(bull_d_range) *
                              len(bull_wp_ob_range) * len(bull_wl_ob_range) * len(bull_wp_os_range) * len(bull_wl_os_range) * len(bull_fear_low_range) *
                              len(bear_rsi_range) * len(bear_sma_range) * len(bear_stoch_rsi_range) * len(bear_stoch_range) * len(bear_k_range) * len(bear_d_range) *
                              len(bear_wp_ob_range) * len(bear_wl_ob_range) * len(bear_wp_os_range) * len(bear_wl_os_range) * len(bear_fear_high_range))
        current_comb = 0
        start_time = datetime.now()
        # Функция display_top (расширена для новых параметров)
        def display_top(top_list, title):
            if top_list:
                print(f"\n!!!!!!!! Текущий топ-1 по {title}:")
                opt_log.write(f"\n!!!!!!!! Текущий топ-1 по {title}:\n")
                score, br, bs, bsr, bst, bsk, bsd, bwp_ob, bwl_ob, bwp_os, bwl_os, bfl, er, es, esr, est, esk, esd, ewp_ob, ewl_ob, ewp_os, ewl_os, efh, pnl, nt, wt, _, _, _, _, win_p, pdp = top_list[0]
                msg1 = f"BULL: RSI_PERIOD={br}, SMA_RSI_PERIOD={bs}, STOCHRSI_RSI_PERIOD={bsr}, STOCHRSI_STOCH_PERIOD={bst}, STOCHRSI_K_PERIOD={bsk}, STOCHRSI_D_PERIOD={bsd}, "
                msg1 += f"WILLIAMS_OVERBOUGHT_PERIOD={bwp_ob}, WILLIAMS_OVERBOUGHT_LEVEL={bwl_ob:.2f}, WILLIAMS_OVERSOLD_PERIOD={bwp_os}, WILLIAMS_OVERSOLD_LEVEL={bwl_os:.2f}, FEAR_GREED_LOW={bfl}"
                msg2 = f"BEAR: RSI_PERIOD={er}, SMA_RSI_PERIOD={es}, STOCHRSI_RSI_PERIOD={esr}, STOCHRSI_STOCH_PERIOD={est}, STOCHRSI_K_PERIOD={esk}, STOCHRSI_D_PERIOD={esd}, "
                msg2 += f"WILLIAMS_OVERBOUGHT_PERIOD={ewp_ob}, WILLIAMS_OVERBOUGHT_LEVEL={ewl_ob:.2f}, WILLIAMS_OVERSOLD_PERIOD={ewp_os}, WILLIAMS_OVERSOLD_LEVEL={ewl_os:.2f}, FEAR_GREED_HIGH={efh}"
                if title == "прибыли в день":
                    msg3 = f"Процент: {win_p:.2f}% (прибыль в день: {score:.2f}%)"
                elif title == "проценту прибыльных сделок":
                    msg3 = f"Процент прибыльных сделок: {score:.2f}% (прибыль в день при равенстве: {pdp:.2f}%)"
                elif title == "максимальной просадке":
                    msg3 = f"Максимальная просадка: {score:.2f}% (прибыль в день при равенстве: {pdp:.2f}%)"
                else:
                    msg3 = f"Процент: {score:.2f}% (прибыль в день: {pdp:.2f}%)"
                msg4 = f"Общая прибыль: {pnl:,.2f} USD (сумма сделок: {nt})"
                print(msg1)
                print(msg2)
                print(msg3)
                print(msg4)
                opt_log.write(msg1 + '\n')
                opt_log.write(msg2 + '\n')
                opt_log.write(msg3 + '\n')
                opt_log.write(msg4 + '\n')
            else:
                msg = f"Текущий топ-1 по {title}: ещё не найден"
                print(msg)
                opt_log.write(msg + '\n')
        for comb in param_combinations:
            (bull_rsi, bull_sma, bull_stoch_rsi, bull_stoch, bull_k, bull_d, bull_williams_overbought_period, bull_williams_overbought_level, bull_williams_oversold_period, bull_williams_oversold_level, bull_fear_low,
             bear_rsi, bear_sma, bear_stoch_rsi, bear_stoch, bear_k, bear_d, bear_williams_overbought_period, bear_williams_overbought_level, bear_williams_oversold_period, bear_williams_oversold_level, bear_fear_high) = comb
            current_comb += 1
            # Вывод текущих топ-1 по каждому критерию
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
            opt_log.write(msg_progress1 + '\n')
            opt_log.write(msg_progress2 + '\n')
            opt_log.write(msg_progress3 + '\n')
            # Обработка текущей комбинации
            msg_comb = f"\nОбработка комбинации: BULL: RSI_PERIOD={bull_rsi}, SMA_RSI_PERIOD={bull_sma}, STOCHRSI_RSI_PERIOD={bull_stoch_rsi}, STOCHRSI_STOCH_PERIOD={bull_stoch}, STOCHRSI_K_PERIOD={bull_k}, STOCHRSI_D_PERIOD={bull_d}, "
            msg_comb += f"WILLIAMS_OVERBOUGHT_PERIOD={bull_williams_overbought_period}, WILLIAMS_OVERBOUGHT_LEVEL={bull_williams_overbought_level:.2f}, WILLIAMS_OVERSOLD_PERIOD={bull_williams_oversold_period}, WILLIAMS_OVERSOLD_LEVEL={bull_williams_oversold_level:.2f}, FEAR_GREED_LOW={bull_fear_low} | "
            msg_comb += f"BEAR: RSI_PERIOD={bear_rsi}, SMA_RSI_PERIOD={bear_sma}, STOCHRSI_RSI_PERIOD={bear_stoch_rsi}, STOCHRSI_STOCH_PERIOD={bear_stoch}, STOCHRSI_K_PERIOD={bear_k}, STOCHRSI_D_PERIOD={bear_d}, "
            msg_comb += f"WILLIAMS_OVERBOUGHT_PERIOD={bear_williams_overbought_period}, WILLIAMS_OVERBOUGHT_LEVEL={bear_williams_overbought_level:.2f}, WILLIAMS_OVERSOLD_PERIOD={bear_williams_oversold_period}, WILLIAMS_OVERSOLD_LEVEL={bear_williams_oversold_level:.2f}, FEAR_GREED_HIGH={bear_fear_high}"
            print(msg_comb)
            opt_log.write(msg_comb + '\n')
            BULL_RSI_PERIOD = bull_rsi
            BULL_SMA_RSI_PERIOD = bull_sma
            BULL_STOCHRSI_RSI_PERIOD = bull_stoch_rsi
            BULL_STOCHRSI_STOCH_PERIOD = bull_stoch
            BULL_STOCHRSI_K_PERIOD = bull_k
            BULL_STOCHRSI_D_PERIOD = bull_d
            BULL_WILLIAMS_OVERBOUGHT_PERIOD = bull_williams_overbought_period
            BULL_WILLIAMS_OVERBOUGHT_LEVEL = bull_williams_overbought_level
            BULL_WILLIAMS_OVERSOLD_PERIOD = bull_williams_oversold_period
            BULL_WILLIAMS_OVERSOLD_LEVEL = bull_williams_oversold_level
            BULL_FEAR_GREED_LOW = bull_fear_low
            BEAR_RSI_PERIOD = bear_rsi
            BEAR_SMA_RSI_PERIOD = bear_sma
            BEAR_STOCHRSI_RSI_PERIOD = bear_stoch_rsi
            BEAR_STOCHRSI_STOCH_PERIOD = bear_stoch
            BEAR_STOCHRSI_K_PERIOD = bear_k
            BEAR_STOCHRSI_D_PERIOD = bear_d
            BEAR_WILLIAMS_OVERBOUGHT_PERIOD = bear_williams_overbought_period
            BEAR_WILLIAMS_OVERBOUGHT_LEVEL = bear_williams_overbought_level
            BEAR_WILLIAMS_OVERSOLD_PERIOD = bear_williams_oversold_period
            BEAR_WILLIAMS_OVERSOLD_LEVEL = bear_williams_oversold_level
            BEAR_FEAR_GREED_HIGH = bear_fear_high
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
            msg_result = f"Результат для комбинации: Процент прибыльных сделок={win_percent:.2f}%, Общая прибыль={pnl:.2f} USD, Прибыль в день: {profit_per_day_percent:.2f}% ({profit_per_day:.2f} USD), Максимальная просадка: {max_drawdown_percent:.2f}%"
            print(msg_result)
            opt_log.write(msg_result + '\n')
            # Обновление топ-1 для win_percent (изменена сортировка: при равенстве win_percent выбирается по profit_per_day_percent desc)
            top_win_percent.append((win_percent, bull_rsi, bull_sma, bull_stoch_rsi, bull_stoch, bull_k, bull_d, bull_williams_overbought_period, bull_williams_overbought_level, bull_williams_oversold_period, bull_williams_oversold_level, bull_fear_low, bear_rsi, bear_sma, bear_stoch_rsi, bear_stoch, bear_k, bear_d, bear_williams_overbought_period, bear_williams_overbought_level, bear_williams_oversold_period, bear_williams_oversold_level, bear_fear_high, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, win_percent, profit_per_day_percent))
            top_win_percent = sorted(top_win_percent, key=lambda x: (x[0], x[31]), reverse=True)[:1]
            # Обновление топ-1 для profit_per_day_percent (расширено)
            top_profit_day_percent.append((profit_per_day_percent, bull_rsi, bull_sma, bull_stoch_rsi, bull_stoch, bull_k, bull_d, bull_williams_overbought_period, bull_williams_overbought_level, bull_williams_oversold_period, bull_williams_oversold_level, bull_fear_low, bear_rsi, bear_sma, bear_stoch_rsi, bear_stoch, bear_k, bear_d, bear_williams_overbought_period, bear_williams_overbought_level, bear_williams_oversold_period, bear_williams_oversold_level, bear_fear_high, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, win_percent, profit_per_day_percent))
            top_profit_day_percent = sorted(top_profit_day_percent, key=lambda x: x[0], reverse=True)[:1]
            # Обновление топ-1 для max_drawdown_percent (категория: по возрастанию max_drawdown_percent, при равенстве по убыванию profit_per_day_percent)
            top_max_drawdown.append((max_drawdown_percent, bull_rsi, bull_sma, bull_stoch_rsi, bull_stoch, bull_k, bull_d, bull_williams_overbought_period, bull_williams_overbought_level, bull_williams_oversold_period, bull_williams_oversold_level, bull_fear_low, bear_rsi, bear_sma, bear_stoch_rsi, bear_stoch, bear_k, bear_d, bear_williams_overbought_period, bear_williams_overbought_level, bear_williams_oversold_period, bear_williams_oversold_level, bear_fear_high, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, win_percent, profit_per_day_percent))
            top_max_drawdown = sorted(top_max_drawdown, key=lambda x: (x[0], -x[31]), reverse=False)[:1]
    logger.setLevel(original_level)
    # Вывод финальных топ-1 в конце оптимизации
    with open(opt_log_file, 'a', encoding='utf-8') as opt_log:
        print("\nФинальные топ-1:")
        opt_log.write("\nФинальные топ-1:\n")
        display_top(top_win_percent, "проценту прибыльных сделок")
        display_top(top_profit_day_percent, "прибыли в день")
        display_top(top_max_drawdown, "максимальной просадке")
    if top_win_percent or top_profit_day_percent or top_max_drawdown:
        ENABLE_OPTIMIZATION = False
    else:
        msg_no_params = "Не удалось найти оптимальные параметры."
        print(msg_no_params)
        with open(opt_log_file, 'a', encoding='utf-8') as opt_log:
            opt_log.write(msg_no_params + '\n')



def run_backtest():
    """ Запускает бэктест стратегии на исторических данных. """
    global current_balance, df_trades, pending_action
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
        # Расчёт индикаторов условно для bull параметров на полном датасете
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
            df['BULL_Williams_R_Overbought'] = talib.WILLR(df['high'].values, df['low'].values, df['close'].values, timeperiod=BULL_WILLIAMS_OVERBOUGHT_PERIOD)
        if TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']:
            df['BULL_Williams_R_Oversold'] = talib.WILLR(df['high'].values, df['low'].values, df['close'].values, timeperiod=BULL_WILLIAMS_OVERSOLD_PERIOD)
        # Расчёт индикаторов условно для bear параметров на полном датасете
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
            df['BEAR_Williams_R_Overbought'] = talib.WILLR(df['high'].values, df['low'].values, df['close'].values, timeperiod=BEAR_WILLIAMS_OVERBOUGHT_PERIOD)
        if TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD']:
            df['BEAR_Williams_R_Oversold'] = talib.WILLR(df['high'].values, df['low'].values, df['close'].values, timeperiod=BEAR_WILLIAMS_OVERSOLD_PERIOD)
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
        # Инициализация df_trades
        headers = [
            'Trade_ID', 'Direction', 'Reason_Open', 'Entry_Time',
            'Entry_RSI', 'Entry_SMA_RSI', 'Entry_Stoch_K', 'Entry_Stoch_D',
            'Entry_Williams_R_Overbought', 'Entry_Williams_R_Oversold', 'Entry_Fear_Greed',
            'Reason_Close', 'Exit_Time',
            'Exit_RSI', 'Exit_SMA_RSI', 'Exit_Stoch_K', 'Exit_Stoch_D',
            'Exit_Williams_R_Overbought', 'Exit_Williams_R_Oversold', 'Exit_Fear_Greed',
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
            'Entry_RSI': float, 'Entry_SMA_RSI': float, 'Entry_Stoch_K': float, 'Entry_Stoch_D': float,
            'Entry_Williams_R_Overbought': float,
            'Entry_Williams_R_Oversold': float,
            'Entry_Fear_Greed': float,
            'Reason_Close': str,
            'Exit_Time': 'datetime64[ns, UTC]',
            'Exit_RSI': float, 'Exit_SMA_RSI': float, 'Exit_Stoch_K': float, 'Exit_Stoch_D': float,
            'Exit_Williams_R_Overbought': float,
            'Exit_Williams_R_Oversold': float,
            'Exit_Fear_Greed': float,
            'Trade_Duration': str, 'Hours': float,
            'Entry_Price': float, 'Exit_Price': float,
            'Position_Size': float, 'Position_Value': float,
            'Leverage': float, 'Net_PnL_USDT': float,
            'Net_PnL_Percent': float,
            'Drawdown_USDT': float, 'Drawdown_Percent': float,
            'Balance': float,
            'PnL_Type': str
        }
        df_trades = pd.DataFrame({col: pd.Series(dtype=dtypes[col]) for col in headers})
        for i in range(start_idx, len(closes)):
            current_time = times[i]
            current_open = opens[i]
            current_close = closes[i]
            current_market_type = get_market_type(current_time)
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
            # Определяем, какие индикаторы нужны для текущего рынка
            need_rsi = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_RSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_RSI'])
            need_stoch = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_STOCHRSI']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_STOCHRSI'])
            need_williams_ob = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERBOUGHT']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERBOUGHT'])
            need_williams_os = (current_market_type == 'bull' and TRADING_CONFIG['ENABLE_BULL_WILLIAMS_OVERSOLD']) or (current_market_type == 'bear' and TRADING_CONFIG['ENABLE_BEAR_WILLIAMS_OVERSOLD'])
            # Пропуск только если nan в нужных индикаторах
            if (need_rsi and (np.isnan(rsi) or np.isnan(sma_rsi))) or \
               (need_stoch and (np.isnan(stoch_k) or np.isnan(stoch_d))) or \
               (need_williams_ob and np.isnan(williams_r_overbought)) or \
               (need_williams_os and np.isnan(williams_r_oversold)):
                if not ENABLE_OPTIMIZATION:
                    logger.warning(f"Пропуск итерации {i}: Недостаточно данных для включенных индикаторов (RSI={need_rsi}, Stoch={need_stoch}, Williams_OB={need_williams_ob}, Williams_OS={need_williams_os})")
                continue
            if not ENABLE_OPTIMIZATION:
                logger.debug(f"Обработка итерации {i}: Время={current_time}, Открытие={current_open:.2f}, Закрытие={current_close:.2f}, RSI={rsi:.2f}, SMA_RSI={sma_rsi:.2f}, Stoch_K={stoch_k:.2f}, Stoch_D={stoch_d:.2f}, Williams_R_Overbought={williams_r_overbought:.2f}, Williams_R_Oversold={williams_r_oversold:.2f}")
            # Проверка сигнала по индексу страха в начале свечи и выполнение действия на open
            fear_greed_value = get_fear_greed_value(current_time)
            if fear_greed_value is not None:
                current_market_type = get_market_type(current_time)
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
            else:
                logger.warning("⚠️ Нет данных индекса страха для текущей даты. Работаем только по RSI.")
            # Затем обработать отложенное действие по RSI
            if pending_action:
                # Проверка соответствия current_time с данными свечи
                if current_time not in df_combined.index:
                    logger.warning(f"Время {current_time} не найдено в df_combined, пропуск действия")
                    pending_action = None
                    continue
                if pending_action == "open_BULL_LONG_rsi":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_LONG по RSI на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_LONG', current_open, current_time, 'rsi_cross_up')
                elif pending_action == "open_BULL_LONG_oversold":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_LONG по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_LONG', current_open, current_time, 'williams_oversold')
                elif pending_action == "open_BULL_SHORT_rsi":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_SHORT по RSI на цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_SHORT', current_open, current_time, 'rsi_cross_down')
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
                elif pending_action in ["rsi_down", "rsi_up", "stoch_down", "stoch_up", "williams_overbought"]:
                    logger.info(f"Выполнение отложенного действия: Закрытие позиции ({pending_action}) по цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim(pending_action, current_time, current_open)
                elif pending_action == "close_BULL_SHORT_oversold":
                    logger.info(f"Выполнение отложенного действия: Закрытие BULL_SHORT по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim('williams_oversold', current_time, current_open)
                elif pending_action == "close_BEAR_SHORT_oversold":
                    logger.info(f"Выполнение отложенного действия: Закрытие BEAR_SHORT по Williams oversold на цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim('williams_oversold', current_time, current_open)
                elif pending_action == "market_type_change":
                    logger.info(f"Выполнение отложенного действия: Закрытие по смене рынка по цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim("market_type_change", current_time, current_open)
                pending_action = None
            # Затем проверить сигналы на текущей свече (RSI, StochRSI и Williams %R)
            check_signals(current_time, current_close, rsi, sma_rsi, stoch_k, stoch_d, williams_r_overbought, williams_r_oversold) # Добавлено передача двух williams
            # Обновление min/max цен для расчёта просадки в активных сделках
            for trade_id, trade in active_trades.items():
                if 'LONG' in trade['direction']:
                    trade['min_price'] = min(trade.get('min_price', trade['entry_price']), lows[i])
                elif 'SHORT' in trade['direction']:
                    trade['max_price'] = max(trade.get('max_price', trade['entry_price']), highs[i])
            if not ENABLE_OPTIMIZATION and i % 100 == 0:
                logger.info(
                    f"Прогресс: Итерация {i}/{len(closes)}, Время: {current_time}, "
                    f"Открытие: {current_open:.2f}, Закрытие: {current_close:.2f}, RSI: {rsi:.2f}, SMA_RSI: {sma_rsi:.2f}, "
                    f"Stoch_K: {stoch_k:.2f}, Stoch_D: {stoch_d:.2f}, Williams_R_Overbought: {williams_r_overbought:.2f}, Williams_R_Oversold: {williams_r_oversold:.2f}, "
                    f"Баланс: {current_balance:.2f} USDT, Активных сделок: {len(active_trades)}"
                )
        if not ENABLE_OPTIMIZATION:
            logger.info("Завершение цикла обработки данных")
            logger.info(f"Финальный баланс: {current_balance:.2f} USDT")
        # Расчёт итоговых метрик на основе только закрытых сделок (без изменений)
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
        else:
            total_pnl = closed_trades['Net_PnL_USDT'].sum()
            num_trades = len(closed_trades)
            win_trades = (closed_trades['Net_PnL_USDT'] > 0).sum()
            loss_trades = num_trades - win_trades
            avg_duration = closed_trades['Hours'].mean() if not closed_trades['Hours'].empty else 0.0
            win_pnl = closed_trades[closed_trades['Net_PnL_USDT'] > 0]['Net_PnL_USDT'].sum()
            loss_pnl = closed_trades[closed_trades['Net_PnL_USDT'] <= 0]['Net_PnL_USDT'].sum()
            # Расчет min и max баланса только по закрытым сделкам
            closed_balances = closed_trades['Balance']
            min_balance = closed_balances.min() if not closed_balances.empty else INITIAL_BALANCE
            max_balance = closed_balances.max() if not closed_balances.empty else INITIAL_BALANCE
            # Расчёт минимальной и максимальной просадки в процентах и соответствующих ID сделок
            min_drawdown_percent = closed_trades['Drawdown_Percent'].min() if not closed_trades['Drawdown_Percent'].empty else 0.0
            min_drawdown_id = closed_trades.loc[closed_trades['Drawdown_Percent'].idxmin(), 'Trade_ID'] if not closed_trades.empty else None
            max_drawdown_percent = closed_trades['Drawdown_Percent'].max() if not closed_trades['Drawdown_Percent'].empty else 0.0
            max_drawdown_id = closed_trades.loc[closed_trades['Drawdown_Percent'].idxmax(), 'Trade_ID'] if not closed_trades.empty else None
            # Расчёт прибыльных и убыточных месяцев
            if 'Exit_Time' in closed_trades.columns and closed_trades['Exit_Time'].notna().any():
                # Проверка и преобразование типов данных в Exit_Time перед группировкой
                if not isinstance(closed_trades['Exit_Time'].dtype, pd.DatetimeTZDtype):
                    logger.warning(f"Некорректный тип данных в Exit_Time: {closed_trades['Exit_Time'].dtype}. Первые несколько значений: {closed_trades['Exit_Time'].head().to_list()}. Пытаемся преобразовать")
                    closed_trades['Exit_Time'] = pd.to_datetime(closed_trades['Exit_Time'], errors='coerce', utc=True)
                # Логирование для диагностики
                if not ENABLE_OPTIMIZATION:
                    logger.debug(f"Exit_Time в closed_trades после преобразования: {closed_trades['Exit_Time'].to_list()}")
                # Повторная проверка после преобразования
                if closed_trades['Exit_Time'].notna().any():
                    # Удаление временной зоны перед преобразованием в Period
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
        # Расчёт периода бэктеста и дней
        start_date = times[start_idx]
        end_date = times[-1]
        total_days = (end_date - start_date).days if (end_date - start_date).days > 0 else 1
        # Изменение цены BTC
        start_price = closes[start_idx]
        end_price = closes[-1]
        price_change_percent = ((end_price - start_price) / start_price) * 100 if start_price != 0 else 0
        # Средние показатели
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
            # Сохранение таблицы сделок в CSV
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
                max_drawdown_percent, max_drawdown_id
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
    if ENABLE_OPTIMIZATION:
        optimize_params()
    else:
        run_backtest()


# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями
# Пиши каждую функцию кода в отдельном блоке для удобного копирования, перед каждым блоком конкретное описание изменений в коде
# Свое описание пиши строго за границами блока с кодом









