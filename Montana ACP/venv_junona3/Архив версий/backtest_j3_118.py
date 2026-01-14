
# backtest_j4_118


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




TRADING_CONFIG = {
    'ENABLE_BULL_LONG': True,
    'ENABLE_BULL_SHORT': False, #False
    'ENABLE_BEAR_SHORT': True,
    'COMMISSION_RATE': 0.05 / 100,
    'ENABLE_LOGGING': True,
    'IMPULSE_ENTRY_PERCENT': 99,
    'BULL_LONG': {'LEVERAGE': 1.0},
    'BULL_SHORT': {'LEVERAGE': 1.0},
    'BEAR_SHORT': {'LEVERAGE': 1.0},
    'MIN_DELTA_LIQUIDATION_LONG': 10.0,
    'MIN_DELTA_LIQUIDATION_SHORT': 10.0,
    'MAX_ACTIVE_TRADES': 1
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
previous_williams_r = None  # Добавлено для Williams %R
current_williams_r = None  # Добавлено для Williams %R

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

# Глобальные параметры стратегии 
RSI_PERIOD = 14
SMA_RSI_PERIOD = 38

STOCHRSI_K_PERIOD = 102  # Smooth K
STOCHRSI_D_PERIOD = 14  # Smooth D

STOCHRSI_RSI_PERIOD = 14  # RSI Length
STOCHRSI_STOCH_PERIOD = 14  # Stochastic Length

WILLIAMS_PERIOD = 13  # Добавлено: период для Williams %R
WILLIAMS_OVERBOUGHT_LEVEL = -1.06  # Добавлено: уровень overbought для закрытия лонг (например, -1.19)



GLOBAL_TIMEFRAME = '1w'
DATA_FILE = Path("1W_2009_2025.csv")

BACKTEST_START_DATE = datetime(2018, 1, 1, tzinfo=pytz.UTC)  # datetime(2023, 1, 1, tzinfo=pytz.UTC) или None для использования всего диапазона
BACKTEST_END_DATE = datetime(2025, 9, 1, tzinfo=pytz.UTC)    # datetime(2024, 12, 31, tzinfo=pytz.UTC) или None для использования всего диапазона



ENABLE_OPTIMIZATION = False  # True / False

RSI_MIN = 14
RSI_MAX = 14
RSI_STEP = 1

SMA_MIN = 38
SMA_MAX = 38
SMA_STEP = 1

STOCHRSI_K_MIN = 102
STOCHRSI_K_MAX = 102
STOCHRSI_K_STEP = 1

STOCHRSI_D_MIN = 14
STOCHRSI_D_MAX = 14
STOCHRSI_D_STEP = 1

STOCHRSI_RSI_MIN = 14
STOCHRSI_RSI_MAX = 14
STOCHRSI_RSI_STEP = 1

STOCHRSI_STOCH_MIN = 14
STOCHRSI_STOCH_MAX = 14
STOCHRSI_STOCH_STEP = 1

WILLIAMS_PERIOD_MIN = 5  # Добавлено: мин. период для оптимизации Williams %R
WILLIAMS_PERIOD_MAX = 50  # Добавлено: макс. период
WILLIAMS_PERIOD_STEP = 1  # Добавлено: шаг

WILLIAMS_LEVEL_MIN = -3.0  # Добавлено: мин. уровень overbought
WILLIAMS_LEVEL_MAX = -0.01   # Добавлено: макс. уровень (до 0, так как Williams %R от -100 до 0)
WILLIAMS_LEVEL_STEP = 0.01 # Добавлено: шаг 0.01

TF_MIN = 1
TF_MAX = 1
TF_STEP = 1


# Глобальные переменные для бэктеста
current_balance = INITIAL_BALANCE
df_trades = None
last_market_type = None


def reset_globals():
    global current_balance, active_trades, trades_history, previous_rsi, previous_sma_rsi, current_rsi, current_sma_rsi, next_trade_id, current_trade_type, pending_action, df_trades, last_market_type, fear_greed_data
    global previous_stoch_k, previous_stoch_d, current_stoch_k, current_stoch_d
    global previous_williams_r, current_williams_r  # Добавлено
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
    previous_williams_r = None  # Добавлено
    current_williams_r = None  # Добавлено
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
    # Нет необходимости в "up" для текущей стратегии, но можно добавить для полноты
    # elif previous_stoch_k < previous_stoch_d and current_k > current_d:
    #     return "up"
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
                'Entry_Williams_R': float(current_williams_r) if current_williams_r is not None else np.nan,  # Добавлено
                'Entry_Fear_Greed': float(fear_greed_value) if fear_greed_value is not None else np.nan,
                'Reason_Close': np.nan,
                'Exit_Time': pd.NaT,
                'Exit_RSI': np.nan,
                'Exit_SMA_RSI': np.nan,
                'Exit_Stoch_K': np.nan,
                'Exit_Stoch_D': np.nan,
                'Exit_Williams_R': np.nan,  # Добавлено
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
                df_trades.loc[mask, 'Exit_Williams_R'] = float(current_williams_r) if current_williams_r is not None else np.nan  # Добавлено
                df_trades.loc[mask, 'Exit_Fear_Greed'] = float(fear_greed_value) if fear_greed_value is not None else np.nan
                df_trades.loc[mask, 'Trade_Duration'] = duration_str
                df_trades.loc[mask, 'Hours'] = duration_hours
                df_trades.loc[mask, 'Exit_Price'] = float(exit_price)
                df_trades.loc[mask, 'Net_PnL_USDT'] = float(net_pnl)
                df_trades.loc[mask, 'Net_PnL_Percent'] = float(net_pnl_percent)
                df_trades.loc[mask, 'Balance'] = float(current_balance)
                df_trades.loc[mask, 'PnL_Type'] = 'Profit' if net_pnl > 0 else 'Loss'
            else:
                logger.warning(f"Не найдена открытая запись для сделки ID={trade_id} в df_trades")
        except Exception as e:
            logger.error(f"Ошибка в simulate_close_trade: {e}")




            

def check_signals(current_time, current_price, rsi, sma_rsi, stoch_k, stoch_d, williams_r):  # Добавлен параметр williams_r
    """
    Проверяет торговые сигналы на основе RSI, SMA RSI, Stochastic RSI и Williams %R.
    """
    global current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi, current_trade_type, pending_action, last_market_type
    global current_stoch_k, current_stoch_d, previous_stoch_k, previous_stoch_d
    global current_williams_r, previous_williams_r  # Добавлено
    try:
        previous_rsi = current_rsi
        previous_sma_rsi = current_sma_rsi
        current_rsi = rsi
        current_sma_rsi = sma_rsi
        previous_stoch_k = current_stoch_k
        previous_stoch_d = current_stoch_d
        current_stoch_k = stoch_k
        current_stoch_d = stoch_d
        previous_williams_r = current_williams_r  # Добавлено
        current_williams_r = williams_r  # Добавлено
        rsi_crossing = check_rsi_crossing(current_rsi, current_sma_rsi)
        stoch_crossing = check_stoch_crossing(current_stoch_k, current_stoch_d)
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
        if current_market_type == 'bull':
            if not active_trades:
                rsi_triggered = rsi_crossing == "up" and TRADING_CONFIG.get('ENABLE_BULL_LONG', True)
                if rsi_triggered:
                    logger.info("Сигнал на открытие BULL_LONG, установка pending_action")
                    pending_action = "open_BULL_LONG"
                rsi_triggered = rsi_crossing == "down" and TRADING_CONFIG.get('ENABLE_BULL_SHORT', True)
                if rsi_triggered:
                    logger.info("Сигнал на открытие BULL_SHORT, установка pending_action")
                    pending_action = "open_BULL_SHORT"
            else:
                if current_trade_type == 'BULL_LONG':
                    # Проверка сигнала StochRSI для закрытия (если раньше RSI)
                    if stoch_crossing == "down" and rsi_crossing != "down":
                        logger.info("Сигнал на закрытие BULL_LONG по StochRSI вниз, установка pending_action")
                        pending_action = "stoch_down"
                    # Сигнал RSI (если не сработал StochRSI)
                    if rsi_crossing == "down":
                        logger.info("Сигнал на закрытие BULL_LONG по RSI вниз, установка pending_action")
                        pending_action = "rsi_down"
                    # Добавлено: Сигнал Williams %R для закрытия лонг при достижении overbought
                    if current_williams_r >= WILLIAMS_OVERBOUGHT_LEVEL:
                        logger.info("Сигнал на закрытие BULL_LONG по Williams %R overbought, установка pending_action")
                        pending_action = "williams_overbought"
                elif current_trade_type == 'BULL_SHORT':
                    rsi_triggered = rsi_crossing == "up"
                    if rsi_triggered:
                        logger.info("Сигнал на закрытие BULL_SHORT по RSI вверх, установка pending_action")
                        pending_action = "rsi_up"
        elif current_market_type == 'bear':
            if not active_trades:
                rsi_triggered = rsi_crossing == "down" and TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True)
                if rsi_triggered:
                    logger.info("Сигнал на открытие BEAR_SHORT, установка pending_action")
                    pending_action = "open_BEAR_SHORT"
            else:
                if current_trade_type == 'BEAR_SHORT':
                    rsi_triggered = rsi_crossing == "up"
                    if rsi_triggered:
                        logger.info("Сигнал на закрытие BEAR_SHORT по RSI вверх, установка pending_action")
                        pending_action = "rsi_up"
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
            elif last_trade_direction in ['BULL_SHORT', 'BEAR_SHORT'] and TRADING_CONFIG.get('ENABLE_BULL_LONG', True):
                logger.info(f"📈 Разворот на бычьем рынке: Открытие BULL_LONG по цене {current_price:.2f}")
                simulate_open_trade('BULL_LONG', current_price, exit_time, f'{reason}_reverse')
        elif current_market_type == 'bear':
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
    loss_months, loss_months_percent, loss_months_pnl
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
        "",
        f"GLOBAL_TIMEFRAME: {GLOBAL_TIMEFRAME}",
        f"RSI_PERIOD: {RSI_PERIOD}",
        f"SMA_RSI_PERIOD: {SMA_RSI_PERIOD}",
        f"STOCHRSI_K_PERIOD: {STOCHRSI_K_PERIOD}",
        f"STOCHRSI_D_PERIOD: {STOCHRSI_D_PERIOD}",
        f"WILLIAMS_PERIOD: {WILLIAMS_PERIOD}",  # Добавлено
        f"WILLIAMS_OVERBOUGHT_LEVEL: {WILLIAMS_OVERBOUGHT_LEVEL:.2f}",  # Добавлено
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
        f"Всего месяцев: {total_months}",
        f"Прибыльные месяцы: {profitable_months} ({profitable_months_percent:.2f}%) ({profitable_months_pnl:,.2f} USD)",
        f"Убыточные месяцы: {loss_months} ({loss_months_percent:,.2f}%) ({loss_months_pnl:,.2f} USD)",
        f"Чистая прибыль: {(total_pnl / INITIAL_BALANCE * 100):,.2f}% ({total_pnl:,.2f} USD)",
        "",
        f"Минимальный баланс: {min_balance:,.2f} USD ({min_balance_percent:,.2f}%)",
        f"Максимальный баланс: {max_balance:,.2f} USD ({max_balance_percent:,.2f}%)",
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
    """ Выполняет перебор параметров RSI, SMA, Stochastic RSI и Williams %R для нахождения оптимальной комбинации по максимальному проценту прибыльных сделок. """
    import sys
    from datetime import datetime, timedelta
    import time
    import numpy as np  # Добавлено для np.arange
    global RSI_PERIOD, SMA_RSI_PERIOD, STOCHRSI_RSI_PERIOD, STOCHRSI_STOCH_PERIOD, STOCHRSI_K_PERIOD, STOCHRSI_D_PERIOD, ENABLE_OPTIMIZATION
    global WILLIAMS_PERIOD, WILLIAMS_OVERBOUGHT_LEVEL  # Добавлено
    # Списки для топ-1 по критериям (расширены для новых параметров)
    top_win_percent = [] # (win_percent, rsi, sma, stoch_rsi, stoch, k, d, wp, wl, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, profit_per_day_percent)
    top_profit_day_percent = []
    top_prof_months_percent = []
    original_level = logger.level
    logger.setLevel(logging.ERROR)
    SCRIPT_NAME = 'backtest_j4_94'
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    opt_log_file = logs_dir / f'{SCRIPT_NAME}_optimization_log.txt'
    # Открываем файл для логов оптимизации
    with open(opt_log_file, 'w', encoding='utf-8') as opt_log:
        # Расчет общего количества комбинаций
        num_rsi = len(range(RSI_MIN, RSI_MAX + 1, RSI_STEP))
        num_sma = len(range(SMA_MIN, SMA_MAX + 1, SMA_STEP))
        num_stoch_rsi = len(range(STOCHRSI_RSI_MIN, STOCHRSI_RSI_MAX + 1, STOCHRSI_RSI_STEP))
        num_stoch = len(range(STOCHRSI_STOCH_MIN, STOCHRSI_STOCH_MAX + 1, STOCHRSI_STOCH_STEP))
        num_k = len(range(STOCHRSI_K_MIN, STOCHRSI_K_MAX + 1, STOCHRSI_K_STEP))
        num_d = len(range(STOCHRSI_D_MIN, STOCHRSI_D_MAX + 1, STOCHRSI_D_STEP))
        num_wp = len(range(WILLIAMS_PERIOD_MIN, WILLIAMS_PERIOD_MAX + 1, WILLIAMS_PERIOD_STEP))  # Добавлено
        num_wl = len(np.arange(WILLIAMS_LEVEL_MIN, WILLIAMS_LEVEL_MAX + WILLIAMS_LEVEL_STEP, WILLIAMS_LEVEL_STEP))  # Добавлено
        total_combinations = num_rsi * num_sma * num_stoch_rsi * num_stoch * num_k * num_d * num_wp * num_wl  # Добавлено умножение
        current_comb = 0
        start_time = datetime.now()
        # Функция display_top вынесена за циклы
        def display_top(top_list, title):
            if top_list:
                print(f"\n!!!!!!!! Текущий топ-1 по {title}:")
                opt_log.write(f"\n!!!!!!!! Текущий топ-1 по {title}:\n")
                score, r, s, sr, st, sk, sd, wp, wl, pnl, nt, wt, _, _, _, _, pdp = top_list[0]  # Добавлено wp, wl
                msg1 = f"RSI_PERIOD={r}, SMA_RSI_PERIOD={s}, STOCHRSI_RSI_PERIOD={sr}, STOCHRSI_STOCH_PERIOD={st}, STOCHRSI_K_PERIOD={sk}, STOCHRSI_D_PERIOD={sd}, WILLIAMS_PERIOD={wp}, WILLIAMS_OVERBOUGHT_LEVEL={wl:.2f}"
                msg2 = f"Процент: {score:.2f}% (прибыль в день: {pdp:.2f}%)"
                msg3 = f"Общая прибыль: {pnl:,.2f} USD (сумма сделок: {nt})"
                print(msg1)
                print(msg2)
                print(msg3)
                opt_log.write(msg1 + '\n')
                opt_log.write(msg2 + '\n')
                opt_log.write(msg3 + '\n')
            else:
                msg = f"Текущий топ-1 по {title}: ещё не найден"
                print(msg)
                opt_log.write(msg + '\n')
        for rsi in range(RSI_MIN, RSI_MAX + 1, RSI_STEP):
            for sma in range(SMA_MIN, SMA_MAX + 1, SMA_STEP):
                for stoch_rsi in range(STOCHRSI_RSI_MIN, STOCHRSI_RSI_MAX + 1, STOCHRSI_RSI_STEP):
                    for stoch in range(STOCHRSI_STOCH_MIN, STOCHRSI_STOCH_MAX + 1, STOCHRSI_STOCH_STEP):
                        for k in range(STOCHRSI_K_MIN, STOCHRSI_K_MAX + 1, STOCHRSI_K_STEP):
                            for d in range(STOCHRSI_D_MIN, STOCHRSI_D_MAX + 1, STOCHRSI_D_STEP):
                                for williams_period in range(WILLIAMS_PERIOD_MIN, WILLIAMS_PERIOD_MAX + 1, WILLIAMS_PERIOD_STEP):  # Добавлено
                                    for williams_level in np.arange(WILLIAMS_LEVEL_MIN, WILLIAMS_LEVEL_MAX + WILLIAMS_LEVEL_STEP, WILLIAMS_LEVEL_STEP):  # Добавлено
                                        current_comb += 1
                                        # Вывод текущих топ-1 по каждому критерию
                                        display_top(top_win_percent, "проценту прибыльных сделок")
                                        display_top(top_profit_day_percent, "прибыли в день")
                                        display_top(top_prof_months_percent, "проценту прибыльных месяцев")
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
                                        msg_comb = f"\nОбработка комбинации: RSI_PERIOD={rsi}, SMA_RSI_PERIOD={sma}, STOCHRSI_RSI_PERIOD={stoch_rsi}, STOCHRSI_STOCH_PERIOD={stoch}, STOCHRSI_K_PERIOD={k}, STOCHRSI_D_PERIOD={d}, WILLIAMS_PERIOD={williams_period}, WILLIAMS_OVERBOUGHT_LEVEL={williams_level:.2f}"
                                        print(msg_comb)
                                        opt_log.write(msg_comb + '\n')
                                        RSI_PERIOD = rsi
                                        SMA_RSI_PERIOD = sma
                                        STOCHRSI_RSI_PERIOD = stoch_rsi
                                        STOCHRSI_STOCH_PERIOD = stoch
                                        STOCHRSI_K_PERIOD = k
                                        STOCHRSI_D_PERIOD = d
                                        WILLIAMS_PERIOD = williams_period  # Добавлено
                                        WILLIAMS_OVERBOUGHT_LEVEL = williams_level  # Добавлено
                                        reset_globals()
                                        pnl, total_days, win_trades, num_trades, prof_months_percent = run_backtest()
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
                                        msg_result = f"Результат для комбинации: Процент прибыльных сделок={win_percent:.2f}%, Общая прибыль={pnl:.2f} USD, Прибыль в день: {profit_per_day_percent:.2f}% ({profit_per_day:.2f} USD), Процент прибыльных месяцев: {prof_months_percent:.2f}%"
                                        print(msg_result)
                                        opt_log.write(msg_result + '\n')
                                        # Обновление топ-1 для win_percent
                                        top_win_percent.append((win_percent, rsi, sma, stoch_rsi, stoch, k, d, williams_period, williams_level, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, profit_per_day_percent))  # Добавлено williams_period, williams_level
                                        top_win_percent = sorted(top_win_percent, key=lambda x: x[0], reverse=True)[:1]
                                        # Обновление топ-1 для profit_per_day_percent
                                        top_profit_day_percent.append((profit_per_day_percent, rsi, sma, stoch_rsi, stoch, k, d, williams_period, williams_level, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, profit_per_day_percent))  # Добавлено
                                        top_profit_day_percent = sorted(top_profit_day_percent, key=lambda x: x[0], reverse=True)[:1]
                                        # Обновление топ-1 для prof_months_percent
                                        top_prof_months_percent.append((prof_months_percent, rsi, sma, stoch_rsi, stoch, k, d, williams_period, williams_level, pnl, num_trades, win_trades, loss_trades, win_pnl, loss_pnl, loss_percent, profit_per_day_percent))  # Добавлено
                                        top_prof_months_percent = sorted(top_prof_months_percent, key=lambda x: x[0], reverse=True)[:1]
    logger.setLevel(original_level)
    # Вывод финальных топ-1 в конце оптимизации
    with open(opt_log_file, 'a', encoding='utf-8') as opt_log:
        print("\nФинальные топ-1:")
        opt_log.write("\nФинальные топ-1:\n")
        display_top(top_win_percent, "проценту прибыльных сделок")
        display_top(top_profit_day_percent, "прибыли в день")
        display_top(top_prof_months_percent, "проценту прибыльных месяцев")
    if top_win_percent or top_profit_day_percent or top_prof_months_percent:
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
        # Расчёт RSI и SMA_RSI на полном датасете с использованием talib
        df['RSI'] = talib.RSI(df['close'].values, timeperiod=RSI_PERIOD)
        df['SMA_RSI'] = talib.SMA(df['RSI'].values, timeperiod=SMA_RSI_PERIOD)
        # Расчёт Stochastic RSI (для соответствия TradingView)
        fastk, fastd = talib.STOCHRSI(
            df['close'].values,
            timeperiod=STOCHRSI_RSI_PERIOD,
            fastk_period=STOCHRSI_STOCH_PERIOD,
            fastd_period=STOCHRSI_K_PERIOD,
            fastd_matype=0
        )
        df['StochRSI_K'] = fastd # Сглаженная %K
        df['StochRSI_D'] = talib.SMA(df['StochRSI_K'].values, timeperiod=STOCHRSI_D_PERIOD) # %D как SMA(%K, D)
        # Добавлено: Расчёт Williams %R на полном датасете
        df['Williams_R'] = talib.WILLR(df['high'].values, df['low'].values, df['close'].values, timeperiod=WILLIAMS_PERIOD)
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
        times = df_combined.index
        rsi_values = df_combined['RSI'].values
        sma_rsi_values = df_combined['SMA_RSI'].values
        stoch_k_values = df_combined['StochRSI_K'].values
        stoch_d_values = df_combined['StochRSI_D'].values
        williams_r_values = df_combined['Williams_R'].values  # Добавлено
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
            'Entry_RSI', 'Entry_SMA_RSI', 'Entry_Stoch_K', 'Entry_Stoch_D', 'Entry_Williams_R', 'Entry_Fear_Greed',  # Добавлено Entry_Williams_R
            'Reason_Close', 'Exit_Time',
            'Exit_RSI', 'Exit_SMA_RSI', 'Exit_Stoch_K', 'Exit_Stoch_D', 'Exit_Williams_R', 'Exit_Fear_Greed',  # Добавлено Exit_Williams_R
            'Trade_Duration', 'Hours', 'Entry_Price', 'Exit_Price',
            'Position_Size', 'Position_Value', 'Leverage',
            'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'PnL_Type'
        ]
        dtypes = {
            'Trade_ID': str, 'Direction': str,
            'Reason_Open': str,
            'Entry_Time': 'datetime64[ns, UTC]',
            'Entry_RSI': float, 'Entry_SMA_RSI': float, 'Entry_Stoch_K': float, 'Entry_Stoch_D': float,
            'Entry_Williams_R': float,  # Добавлено
            'Entry_Fear_Greed': float,
            'Reason_Close': str,
            'Exit_Time': 'datetime64[ns, UTC]',
            'Exit_RSI': float, 'Exit_SMA_RSI': float, 'Exit_Stoch_K': float, 'Exit_Stoch_D': float,
            'Exit_Williams_R': float,  # Добавлено
            'Exit_Fear_Greed': float,
            'Trade_Duration': str, 'Hours': float,
            'Entry_Price': float, 'Exit_Price': float,
            'Position_Size': float, 'Position_Value': float,
            'Leverage': float, 'Net_PnL_USDT': float,
            'Net_PnL_Percent': float, 'Balance': float,
            'PnL_Type': str
        }
        df_trades = pd.DataFrame({col: pd.Series(dtype=dtypes[col]) for col in headers})
        for i in range(start_idx, len(closes)):
            current_time = times[i]
            current_open = opens[i]
            current_close = closes[i]
            rsi = rsi_values[i]
            sma_rsi = sma_rsi_values[i]
            stoch_k = stoch_k_values[i]
            stoch_d = stoch_d_values[i]
            williams_r = williams_r_values[i]  # Добавлено
            if np.isnan(rsi) or np.isnan(sma_rsi) or np.isnan(stoch_k) or np.isnan(stoch_d) or np.isnan(williams_r):  # Добавлено проверка на nan для Williams
                if not ENABLE_OPTIMIZATION:
                    logger.warning(f"Пропуск итерации {i}: RSI={rsi}, SMA_RSI={sma_rsi}, Stoch_K={stoch_k}, Stoch_D={stoch_d}, Williams_R={williams_r}")
                continue
            if not ENABLE_OPTIMIZATION:
                logger.debug(f"Обработка итерации {i}: Время={current_time}, Открытие={current_open:.2f}, Закрытие={current_close:.2f}, RSI={rsi:.2f}, SMA_RSI={sma_rsi:.2f}, Stoch_K={stoch_k:.2f}, Stoch_D={stoch_d:.2f}, Williams_R={williams_r:.2f}")
            # Проверка сигнала по индексу страха в начале свечи и выполнение действия на open
            fear_greed_value = get_fear_greed_value(current_time)
            if fear_greed_value is not None:
                current_market_type = get_market_type(current_time)
                if current_market_type == 'bull':
                    if not active_trades:
                        if fear_greed_value <= 26 and TRADING_CONFIG.get('ENABLE_BULL_LONG', True):
                            logger.info(f"Сигнал на открытие BULL_LONG по fear, выполнение на цене {current_open:.2f}")
                            simulate_open_trade('BULL_LONG', current_open, current_time, 'fear_low')
                    elif current_trade_type == 'BULL_SHORT':
                        if fear_greed_value <= 26:
                            logger.info(f"Сигнал на закрытие BULL_SHORT по fear, выполнение на цене {current_open:.2f}")
                            close_all_trades_sim("fear_low", current_time, current_open)
                elif current_market_type == 'bear':
                    if not active_trades:
                        if fear_greed_value >= 52 and TRADING_CONFIG.get('ENABLE_BEAR_SHORT', True):
                            logger.info(f"Сигнал на открытие BEAR_SHORT по fear, выполнение на цене {current_open:.2f}")
                            simulate_open_trade('BEAR_SHORT', current_open, current_time, 'fear_high')
            # Затем обработать отложенное действие по RSI
            if pending_action:
                # Проверка соответствия current_time с данными свечи
                if current_time not in df_combined.index:
                    logger.warning(f"Время {current_time} не найдено в df_combined, пропуск действия")
                    pending_action = None
                    continue
                if pending_action == "open_BULL_LONG":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_LONG по цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_LONG', current_open, current_time, 'rsi_up')
                elif pending_action == "open_BULL_SHORT":
                    logger.info(f"Выполнение отложенного действия: Открытие BULL_SHORT по цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BULL_SHORT', current_open, current_time, 'rsi_down')
                elif pending_action == "open_BEAR_SHORT":
                    logger.info(f"Выполнение отложенного действия: Открытие BEAR_SHORT по цене {current_open:.2f} на время {current_time}")
                    simulate_open_trade('BEAR_SHORT', current_open, current_time, 'rsi_down')
                elif pending_action in ["rsi_down", "rsi_up", "stoch_down", "williams_overbought"]:  # Добавлено williams_overbought
                    logger.info(f"Выполнение отложенного действия: Закрытие позиции ({pending_action}) по цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim(pending_action, current_time, current_open)
                elif pending_action == "market_type_change":
                    logger.info(f"Выполнение отложенного действия: Закрытие по смене рынка по цене {current_open:.2f} на время {current_time}")
                    close_all_trades_sim("market_type_change", current_time, current_open)
                pending_action = None
            # Затем проверить сигналы на текущей свече (RSI, StochRSI и Williams %R)
            check_signals(current_time, current_close, rsi, sma_rsi, stoch_k, stoch_d, williams_r)  # Добавлено williams_r
            if not ENABLE_OPTIMIZATION and i % 100 == 0:
                logger.info(
                    f"Прогресс: Итерация {i}/{len(closes)}, Время: {current_time}, "
                    f"Открытие: {current_open:.2f}, Закрытие: {current_close:.2f}, RSI: {rsi:.2f}, SMA_RSI: {sma_rsi:.2f}, "
                    f"Stoch_K: {stoch_k:.2f}, Stoch_D: {stoch_d:.2f}, Williams_R: {williams_r:.2f}, "  # Добавлено Williams_R в лог
                    f"Баланс: {current_balance:.2f} USDT, Активных сделок: {len(active_trades)}"
                )
        if not ENABLE_OPTIMIZATION:
            logger.info("Завершение цикла обработки данных")
            logger.info(f"Финальный баланс: {current_balance:.2f} USDT")
        # Расчёт итоговых метрик на основе только закрытых сделок
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
            # Расчёт прибыльных и убыточных месяцев
            if 'Exit_Time' in closed_trades.columns and closed_trades['Exit_Time'].notna().any():
                # Проверка и преобразование типов данных в Exit_Time перед группировкой
                if not pd.api.types.is_datetime64tz_dtype(closed_trades['Exit_Time']):
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
                loss_months, loss_months_percent, loss_months_pnl
            )
            logger.info("Бэктест успешно завершён")
        return total_pnl, total_days, win_trades, num_trades, profitable_months_percent
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









