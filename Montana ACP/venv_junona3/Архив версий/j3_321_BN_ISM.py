# j3_321_BN_ISM.py

import keyring
import websocket
import json
import ccxt
import os
import time
import threading
from datetime import datetime, timedelta
# from dotenv import load_dotenv
import csv
import pandas as pd
from pathlib import Path
import numpy as np
import talib
import requests
from binance.client import Client
import math



def log_event(event):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"📌 {timestamp} | {event}")



BINANCE_API_KEY = keyring.get_password("binance_api_key", "TG_bot")
BINANCE_SECRET_KEY = keyring.get_password("binance_api_secret", "TG_bot")

# load_dotenv()
# API_KEY = os.getenv("BINANCE_API_KEY")
# API_SECRET = os.getenv("BINANCE_API_SECRET")
# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Добавляем загрузку TELEGRAM_TOKEN


# Подключаем Binance через ccxt (изолированная маржа)
binance = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
    'enableRateLimit': True,  # Включаем ограничение частоты запросов
    'options': {
        'defaultType': 'margin',  # Указываем маржинальный счет
    },
})


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
    'AVAILABLE_BALANCE': 60000,  # Начальный баланс для бэктеста (в USD)
    'IMPULSE_ENTRY_PERCENT': 99,  # Процент от доступного баланса для импульсных сделок
    'AVERAGING_ENTRY_PERCENTS': [1, 3, 5, 7, 18, 25, 41],  # Проценты для усредняющих сделок
    'WITHDRAW_PERCENT': 20.0,  # Процент вывода части чистой прибыли (по умолчанию 5%)

    'BULL_LONG': {'LEVERAGE': 5,},
    'BULL_SHORT': {'LEVERAGE': 5,},

    'BEAR_SHORT': {'LEVERAGE': 5,}
}


ANALYSIS_TIMEFRAME = '1h'  # Таймфрейм для обновления данных о сделках (например, '1m', '5m', '1h', '1d', '1w')

GLOBAL_TIMEFRAME = '1w'  # Глобальный таймфрейм по умолчанию — 1 неделя



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
last_orderbook_data = None
last_orderbook_message_time = time.time()
long_averaging_trades_count = 0
short_averaging_trades_count = 0
fear_greed_data = None
next_rsi_update_time = None
current_rsi = None
current_sma_rsi = None
initial_candles_loaded = False  # Флаг для отслеживания первоначальной загрузки свечей
previous_mid_price = 0
bull_long_trades_count = 0
bull_short_trades_count = 0



# Путь к CSV-файлу
SCRIPT_NAME = os.path.basename(__file__)
# CSV_FILE = Path(f"trade_history_{SCRIPT_NAME.split('.')[0]}.csv")
CSV_FILE = Path(f"trade_history.csv")
df_trades = None  # Глобальная переменная для хранения DataFrame с историей сделок




def manage_liquidation_price():
    global next_liquidation_update_time, client, symbol, ANALYSIS_TIMEFRAME, MIN_DELTA_LIQUIDATION_LONG, MIN_DELTA_LIQUIDATION_SHORT

    current_time = datetime.now()
    if next_liquidation_update_time is None or current_time >= next_liquidation_update_time:
        for attempt in range(3):  # Попытки получения данных
            try:
                # Получаем данные о маржинальном счете
                account = client.get_isolated_margin_account(symbol=symbol)
                if 'assets' not in account or not account['assets']:
                    raise ValueError("Нет данных о маржинальном счете")
                position = account['assets'][0]
                base_asset = position.get('baseAsset', {})
                quote_asset = position.get('quoteAsset', {})

                net_asset = float(base_asset.get('netAsset', 0))
                borrowed_btc = float(base_asset.get('borrowed', 0))

                # Определяем направление сделки и размер позиции
                if net_asset > 0.0001:
                    direction = 'LONG'
                    size = net_asset
                elif borrowed_btc > 0.0001:
                    direction = 'SHORT'
                    size = borrowed_btc
                else:
                    log_event("⚪ Нет позиций для управления рисками")
                    return

                # Получаем цену ликвидации
                liquidation_price = float(position.get('liquidatePrice', 0))
                if liquidation_price == 0:
                    log_event("⚠️ Цена ликвидации не доступна или равна нулю")
                    return

                # Получаем текущую рыночную цену
                ticker = client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])

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
                    CLOSE_PERCENT = 5.0  # По умолчанию 5%
                    
                    # Рассчитываем объем для закрытия как процент от текущего размера позиции
                    close_amount = size * (CLOSE_PERCENT / 100)
                    
                    # Проверяем минимальный объем для закрытия
                    MIN_CLOSE_AMOUNT = 0.0001  # Минимальный объем для закрытия
                    if close_amount < MIN_CLOSE_AMOUNT:
                        close_amount = MIN_CLOSE_AMOUNT
                    
                    # Округляем объем с учетом точности символа
                    precision = get_symbol_precision(symbol)
                    close_amount = round(close_amount, precision)
                    
                    log_event(f"Рассчитан объем для закрытия: {close_amount:.8f} BTC")
                    
                    # Частичное закрытие позиции
                    close_all_trades(reason=f"delta_control_{direction.lower()}", position_value=close_amount)
                else:
                    log_event(f"Дельта {delta_percent:.2f}% >= {min_delta}%, коррекция не требуется")

                # Определяем тип рынка
                market_type = get_market_type(current_time)
                if market_type is None:
                    log_event("⚠️ Тип рынка не определён")
                    return

                # Определяем тип сделки
                if market_type == 'bull':
                    trade_type = 'BULL_LONG' if direction == 'LONG' else 'BULL_SHORT'
                elif market_type == 'bear':
                    trade_type = 'BEAR_SHORT' if direction == 'SHORT' else None
                if not trade_type:
                    log_event(f"⚠️ Неожиданное направление {direction} для рынка {market_type}")
                    return

                leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE', 1)

                # Обновляем время следующего обновления
                next_liquidation_update_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)
                break  # Успешное выполнение, выходим из цикла попыток
            except Exception as e:
                log_event(f"⚠️ Ошибка при управлении рисками (попытка {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)  # Пауза перед повторной попыткой
                else:
                    log_event("⚠️ Не удалось получить данные после 3 попыток")
                    next_liquidation_update_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)




def transfer_to_cross_and_spot(amount, symbol="BTCUSDT", asset="USDT"):
    try:
        # Шаг 1: Перевод с изолированной маржи на кросс-маржу
        log_event(f"Попытка перевести {amount} {asset} с изолированной маржи ({symbol}) на кросс-маржу")
        params_to_cross = {
            "type": "ISOLATEDMARGIN_MARGIN",  # Из изолированной маржи на кросс-маржу
            "asset": asset,
            "amount": str(amount),
            "fromSymbol": symbol
        }
        response_cross = client.universal_transfer(**params_to_cross)
        log_event(f"Успешный перевод на кросс-маржу: {response_cross}")

        # Шаг 2: Пауза 10 секунд
        log_event("Ожидание 10 секунд перед переводом на спотовый счет...")
        time.sleep(10)

        # Шаг 3: Перевод с кросс-маржи на спотовый счет
        log_event(f"Попытка перевести {amount} {asset} с кросс-маржи на спотовый счет")
        params_to_spot = {
            "type": "MARGIN_MAIN",  # Из кросс-маржи на спот
            "asset": asset,
            "amount": str(amount)
        }
        response_spot = client.universal_transfer(**params_to_spot)
        log_event(f"Успешный перевод на спотовый счет: {response_spot}")

        return response_cross, response_spot

    except Exception as e:
        log_event(f"Ошибка при переводе: {e}")
        raise





def get_active_trades_from_exchange(client, symbol='BTCUSDT'):
    try:
        # Получаем данные о маржинальном счёте
        account = client.get_isolated_margin_account(symbol=symbol)
        log_event(f"📊 Получена информация о маржинальном счете: {account}")
        position = account['assets'][0]
        base_asset = position['baseAsset']
        quote_asset = position['quoteAsset']
        log_event(f"📈 Базовый актив (BTC): {base_asset}")
        log_event(f"📉 Котируемый актив (USDT): {quote_asset}")

        # Информация о займах
        log_event(f"💸 Займ BTC: borrowed={base_asset['borrowed']}, interest={base_asset['interest']}, free={base_asset['free']}")
        log_event(f"💸 Займ USDT: borrowed={quote_asset['borrowed']}, interest={quote_asset['interest']}, free={quote_asset['free']}")

        net_asset = float(base_asset['netAsset'])
        borrowed_btc = float(base_asset['borrowed'])

        # Определяем направление и размер позиции
        if net_asset > 0.0001:
            direction = 'LONG'
            size = net_asset
            log_event(f"🟢 Обнаружена активная лонг-позиция: размер={size:.8f} BTC")
        elif borrowed_btc > 0.0001:
            direction = 'SHORT'
            size = borrowed_btc
            log_event(f"🟢 Обнаружена активная шорт-позиция: размер={size:.8f} BTC")
        else:
            log_event("⚪ Нет активных позиций")
            return []

        # Получаем цену ликвидации
        try:
            liquidation_price = float(position.get('liquidatePrice', 0))
            log_event(f"💥 Цена ликвидации: {liquidation_price:.2f}")
        except (ValueError, TypeError) as e:
            log_event(f"⚠️ Ошибка при получении 'liquidatePrice': {e}")
            liquidation_price = None

        # Получаем текущую рыночную цену
        ticker = client.get_symbol_ticker(symbol=symbol)
        current_price = float(ticker['price'])
        log_event(f"📈 Текущая цена: {current_price:.2f}")



        # Формируем данные о сделке без цены входа и времени
        trade_data = {
            'direction': direction,
            'size': size,
            'liquidation_price': liquidation_price,
            'entry_price': None,  # Цена входа не используется
            'entry_time': None    # Время входа не используется
        }
        log_event(f"📝 Итоговые данные о сделке: {trade_data}")
        return [trade_data]

    except Exception as e:
        log_event(f"⚠️ Ошибка при получении активных сделок с биржи: {e}")
        return []





def sync_active_trades():
    global active_trades, next_trade_id, df_trades, CSV_FILE, current_trade_type, previous_rsi, previous_sma_rsi, current_rsi, current_sma_rsi, initial_candles_loaded, next_rsi_update_time

    log_event("🔄 Начало синхронизации активных сделок с биржи")
    exchange_trades = get_active_trades_from_exchange(client)
    log_event(f"📊 Получено {len(exchange_trades)} активных сделок с биржи: {exchange_trades}")
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

        # Формируем полный тип сделки на основе текущего рынка
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

        # Генерируем новый trade_id
        trade_id = next_trade_id
        next_trade_id += 1
        log_event(f"📝 Новая сделка ID {trade_id}")

        # Создаём запись о сделке без entry_price и entry_time
        trade_record = {
            'id': trade_id,
            'direction': full_direction,
            'entry_price': None,  # Цена входа не доступна
            'entry_time': None,   # Время входа не доступно
            'current_price': None,
            'current_pnl': 0,
            'current_pnl_percent': 0,
            'size': size,
            'value': None,  # Поскольку нет entry_price, value не рассчитывается
            'leverage': TRADING_CONFIG.get(full_direction, {}).get('LEVERAGE', 1),
            'commission_open': 0,  # Комиссия не рассчитывается без entry_price
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
        log_event(f"📝 Сделка добавлена в active_trades: {trade_record}")

        current_trade_type = full_direction
        log_event(f"📈 Установлен текущий тип сделки: {current_trade_type}")

        # Обновление df_trades
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
            'Entry_Time': pd.NaT,  # Время входа не доступно
            'Exit_Time': pd.NaT,
            'Trade_Duration': '',
            'Hours': np.nan,
            'Entry_Price': np.nan,  # Цена входа не доступна
            'Exit_Price': np.nan,
            'Position_Size': float(size),
            'Position_Value': np.nan,  # Значение не рассчитывается
            'Leverage': float(TRADING_CONFIG.get(full_direction, {}).get('LEVERAGE', 1)),
            'Net_PnL_USDT': np.nan,
            'Net_PnL_Percent': np.nan,
            'Balance': float(get_available_balance()),
            'Withdraw': np.nan
        }
        df_trades = pd.concat([df_trades, pd.DataFrame([new_row])], ignore_index=True)
        log_event(f"📝 Добавлена новая запись в df_trades: {new_row}")

        if CSV_FILE.exists():
            df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
            log_event(f"💾 История сделок сохранена в {CSV_FILE}")

        log_event(f"📈 Синхронизирована сделка: {full_direction}")
    else:
        log_event("⚪ Нет активных сделок для синхронизации")




def get_symbol_precision(symbol):
    """Получает точность для торговой пары из информации о символе."""
    try:
        exchange_info = client.get_exchange_info()
        symbol_info = next(item for item in exchange_info['symbols'] if item['symbol'] == symbol)
        lot_size_filter = next(filter for filter in symbol_info['filters'] if filter['filterType'] == 'LOT_SIZE')
        step_size = float(lot_size_filter['stepSize'])
        precision = int(round(-math.log(step_size, 10), 0))
        return precision
    except Exception as e:
        log_event(f"Ошибка при получении информации о символе: {e}")
        return 5



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



def fetch_fear_greed_data(filename="fear_greed_index.csv"):
    url = "https://api.alternative.me/fng/?limit=0"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()['data']
        # Сохранение данных в CSV
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Date', 'Value', 'Classification'])
            for entry in data:
                timestamp = int(entry['timestamp'])
                date = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')
                value = entry['value']
                classification = entry.get('value_classification', 'Unknown')
                writer.writerow([date, value, classification])
        print(f"Данные успешно сохранены в {filename}")
        return data
    except requests.RequestException as e:
        print(f"Ошибка при запросе данных: {e}")
        return []




# Функция загрузки данных индекса страха и жадности
def load_fear_greed_data():
    global fear_greed_data
    fear_greed_file = Path("fear_greed_index.csv")
    if fear_greed_file.exists():
        fear_greed_data = pd.read_csv(fear_greed_file, parse_dates=['Date'], dayfirst=True)
        fear_greed_data['Date'] = pd.to_datetime(fear_greed_data['Date'], format='%d/%m/%Y')
        fear_greed_data = fear_greed_data.sort_values(by='Date')
        log_event("📝 Данные индекса страха и жадности загружены из файла")
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

    


def get_available_balance():
    try:
        # Получаем максимальную сумму, доступную для перевода с изолированной маржи BTCUSDT
        max_transferable = client.get_max_margin_transfer(
            asset='USDT',
            isolatedSymbol='BTCUSDT',
            type='ISOLATED_MARGIN_TO_SPOT'  # Направление перевода
        )
        # Извлекаем максимально доступный баланс из ответа API
        available_usdt = float(max_transferable['amount'])
        return available_usdt
        
    except Exception as e:
        log_event(f"⚠️ Ошибка при получении баланса: {e}")
        return 0




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
        print(f"Не удалось записать в файл ошибок: {e}")



def initialize_csv():
    global df_trades, CSV_FILE
    headers = [
        'Trade_ID', 'Status', 'Direction', 'Entry_Time', 'Exit_Time', 'Trade_Duration', 'Hours',
        'Entry_Price', 'Exit_Price', 'Position_Size', 'Position_Value',
        'Leverage', 'Net_PnL_USDT', 'Net_PnL_Percent', 'Balance', 'Withdraw'
    ]
    
    # Определение типов данных для столбцов
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
        CSV_FILE = Path("trade_history.csv")
        if CSV_FILE.exists():
            # Загружаем CSV с правильными типами данных
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
            print("📝 CSV файл загружен в DataFrame")
        else:
            # Создаём пустой DataFrame с правильными типами
            df_trades = pd.DataFrame({col: pd.Series(dtype=dtypes[col]) for col in headers})
            df_trades.to_csv(CSV_FILE, index=False)
            print("📝 Создан новый файл CSV с заголовками")
    else:
        df_trades = None
        CSV_FILE = None
        print("📝 Запись сделок отключена")




def parse_timeframe(timeframe):
    """Преобразует строку таймфрейма в объект timedelta."""
    if timeframe.endswith('m'):
        return timedelta(minutes=int(timeframe[:-1]))
    elif timeframe.endswith('h'):
        return timedelta(hours=int(timeframe[:-1]))
    elif timeframe.endswith('d'):
        return timedelta(days=int(timeframe[:-1]))
    elif timeframe.endswith('w'):
        return timedelta(weeks=int(timeframe[:-1]))
    else:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")
    


def get_candles(symbol, timeframe, limit, retries=5, delay=5):
    """Получает свечные данные с Binance (спот) с повторными попытками."""
    for attempt in range(retries):
        try:
            binance.options['defaultType'] = 'spot'
            candles = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
            if len(candles) >= limit:
                return candles
            else:
                log_event(f"⚠️ Загружено {len(candles)} свечей, требуется {limit}. Повторная попытка...")
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении свечей (попытка {attempt + 1}/{retries}): {e}")
        time.sleep(delay)
    log_event(f"⚠️ Не удалось получить достаточное количество свечей после {retries} попыток")
    return []




def get_completed_candles_close(symbol, timeframe, current_time, retries=3, delay=5):
    interval = timeframe  # Предполагается, что timeframe уже в формате Binance ('1m', '1h', '1d')
    tf_delta = parse_timeframe(timeframe)  # Длительность свечи в виде timedelta
    end_time = int(current_time.timestamp() * 1000)  # Текущее время в миллисекундах для API
    limit = 1000  # Максимальное количество свечей за один запрос (лимит Binance)

    for attempt in range(retries):
        try:
            # Запрос свечных данных через python-binance
            candles = client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                endTime=end_time
            )
            closes = []
            for candle in candles:
                candle_start = datetime.fromtimestamp(candle[0] / 1000)  # Время начала свечи
                candle_end = candle_start + tf_delta  # Время окончания свечи
                if current_time >= candle_end:  # Фильтруем только завершённые свечи
                    closes.append(float(candle[4]))  # Добавляем цену закрытия
            return closes
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении свечей (попытка {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)  # Задержка перед следующей попыткой
            else:
                log_event("⚠️ Не удалось получить свечи после всех попыток")
                return []  # Возвращаем пустой список при неудаче



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
    log_event("----------------------------------------------|")
    log_event("------- Изолированная маржа [BTC/USDT] -------|")
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



def on_orderbook_message(ws, message):
    global previous_mid_price, last_price_indicator, last_orderbook_data, last_orderbook_message_time, next_rsi_update_time, current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi, initial_candles_loaded, next_analysis_time, next_liquidation_update_time
    
    last_orderbook_message_time = time.time()
    data = json.loads(message)
    last_orderbook_data = data

    # Извлечение лучшей цены покупки и продажи
    if 'bids' in data and data['bids'] and 'asks' in data and data['asks']:
        best_bid = float(data['bids'][0][0])
        best_ask = float(data['asks'][0][0])
        mid_price = (best_bid + best_ask) / 2
    else:
        mid_price = 0
        log_event("⚠️ Не удалось получить данные книги ордеров")
        return
    
    current_time = datetime.now()
    
    # Проверка, наступило ли время обновления по закрытию свечи ANALYSIS_TIMEFRAME
    if next_analysis_time is None or current_time >= next_analysis_time:
        # Логирование рыночных данных
        log_market_data(mid_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_candles, get_fear_greed_value, get_available_balance)
        display_position()
        manage_liquidation_price()

        next_analysis_time = get_next_candle_end_time(current_time, ANALYSIS_TIMEFRAME)

        # Добавление обратного отсчёта после отображения сделок
        log_event("----------------------------------------------|")
        log_event(f"⏳ ({ANALYSIS_TIMEFRAME}) Обновление данных: {next_analysis_time}")

    # Инициализация RSI и SMA RSI при первом запуске
    if not initial_candles_loaded:
        closes = get_completed_candles_close(symbol, GLOBAL_TIMEFRAME, current_time)
        if len(closes) >= RSI_PERIOD:
            rsi_values = talib.RSI(np.array(closes), timeperiod=RSI_PERIOD)
            if len(rsi_values) >= SMA_RSI_PERIOD:
                sma_rsi_values = talib.SMA(rsi_values, timeperiod=SMA_RSI_PERIOD)
                current_rsi = rsi_values[-1]
                current_sma_rsi = sma_rsi_values[-1]
                previous_rsi = rsi_values[-2] if len(rsi_values) >= 2 else None
                previous_sma_rsi = sma_rsi_values[-2] if len(sma_rsi_values) >= 2 else None
            else:
                current_rsi = rsi_values[-1]
                current_sma_rsi = None
                log_event("⚠️ Недостаточно значений RSI для SMA RSI при инициализации")
            initial_candles_loaded = True
        else:
            log_event(f"⚠️ Недостаточно свечей для инициализации: {len(closes)} из {RSI_PERIOD}")
    
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
        
        # Обновление времени следующего расчёта RSI
        if next_rsi_update_time is None:
            next_rsi_update_time = get_next_candle_end_time(current_time, GLOBAL_TIMEFRAME)
        else:
            tf_delta = parse_timeframe(GLOBAL_TIMEFRAME)
            next_rsi_update_time += tf_delta
        
        # Вызов check_signals и логирование сразу после обновления RSI
        if current_rsi is not None and current_sma_rsi is not None:
            check_signals(mid_price)
            log_market_data(mid_price, previous_mid_price, last_price_indicator, current_time, current_rsi, current_sma_rsi, symbol, GLOBAL_TIMEFRAME, get_candles, get_fear_greed_value, get_available_balance)
            display_position()
            manage_liquidation_price()
            log_event("----------------------------------------------|")
            log_event(f"⏳ ({GLOBAL_TIMEFRAME}) Обновление свечи: {next_rsi_update_time}")

    previous_mid_price = mid_price




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


    # Отображение всех активных сделок
    log_event("----------------------------------------------|")
    log_event("-------------- Проверка сигнала --------------|")
    log_event("----------------------------------------------|")



def open_trade(trade_type, entry_price, position_value=None, trailing_status=None):
    global next_trade_id, active_trades, df_trades, trades_lock, MAX_ACTIVE_TRADES, TRADING_CONFIG, CSV_FILE, current_trade_type, client, symbol

    start_time = time.time()

    with trades_lock:
        # Проверка лимита активных сделок
        log_event(f"Пауза 5 секунд перед открытием новой сделки")
        time.sleep(5)
        if len(active_trades) >= MAX_ACTIVE_TRADES:
            log_event("⚠️ Достигнут лимит активных сделок")
            return

        # Получение доступного баланса
        available_balance = get_available_balance()
        log_event(f" Доступный баланс: {available_balance}")

        # Установка значения позиции, если не указано
        if position_value is None:
            if trade_type in ["BULL_LONG", "BULL_SHORT", "BEAR_SHORT"]:
                position_value = (available_balance * TRADING_CONFIG['IMPULSE_ENTRY_PERCENT']) / 100
            else:
                log_event(f"⚠️ Неизвестный тип сделки: {trade_type}")
                return


        # Получение информации о символе для точности
        try:
            exchange_info = client.get_exchange_info()
            symbol_info = next(item for item in exchange_info['symbols'] if item['symbol'] == symbol)
            lot_size_filter = next(filter for filter in symbol_info['filters'] if filter['filterType'] == 'LOT_SIZE')
            step_size = float(lot_size_filter['stepSize'])
            precision = int(round(-math.log(step_size, 10), 0))
        except Exception as e:
            log_event(f"Ошибка при получении информации о символе: {e}")
            return

        # Определение плеча для типа сделки
        leverage = TRADING_CONFIG.get(trade_type, {}).get('LEVERAGE', 1)
        log_event(f"Плечо для {trade_type}: {leverage}x")

        # Минимальные размеры ордера
        min_order_size_btc = 0.0001  # Минимальный объем в BTC
        min_order_size_usdt = 10.0   # Минимальный объем в USDT

    # Обработка шорт-сделок
        if 'SHORT' in trade_type:
            log_event(f"Открытие шорт-сделки: {trade_type}")

            # Рассчитываем количество BTC для продажи с учетом плеча
            amount_btc = ((position_value * leverage) / entry_price) * 0.9
            amount_btc = round(amount_btc, precision)

            # Проверка минимального размера ордера
            if amount_btc < min_order_size_btc:
                log_event(f"⚠️ Объем сделки {amount_btc:.6f} BTC меньше минимального {min_order_size_btc} BTC")
                return
            if (amount_btc * entry_price) < min_order_size_usdt:
                log_event(f"⚠️ Стоимость сделки {amount_btc * entry_price:.2f} USDT меньше минимальной {min_order_size_usdt} USDT")
                return

            # Займ BTC для шорт-позиции
            try:
                log_event(f"Запрос на займ BTC: {amount_btc:.8f} BTC")
                loan = client.create_margin_loan(
                    asset='BTC',
                    amount=str(amount_btc),
                    isIsolated='TRUE',
                    symbol=symbol
                )
                log_event("Займ BTC успешно создан!")
            except Exception as e:
                log_event(f"Ошибка при создании займа BTC: {e}")
                return

            # Отправка ордера на продажу (шорт)
            try:
                log_event(f"Отправка шорт-ордера на продажу {amount_btc:.{precision}f} BTC")
                order = client.create_margin_order(
                    symbol=symbol,
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=str(amount_btc),
                    isIsolated='TRUE'
                )
                log_event("Шорт-ордер успешно выполнен!")
            except Exception as e:
                log_event(f"Ошибка при отправке шорт-ордера: {e}")
                return

        # Обработка лонг-сделок 
        elif 'LONG' in trade_type:
            log_event(f"Открытие лонг-сделки: {trade_type}")
            

            # Получаем текущую цену BTC
            ticker = client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            log_event(f"Текущая цена BTC: {current_price:.2f} USDT")

            # Рассчитываем общий размер позиции с учетом плеча
            position_size_usdt = (available_balance * leverage) * 0.9
            log_event(f"Размер позиции: {position_size_usdt:.2f} USDT")

            # Рассчитываем количество BTC
            quantity_btc = position_size_usdt / current_price
            amount_btc = round(quantity_btc, 5)
            log_event(f"Объем для сделки: {amount_btc:.5f} BTC")


            # Займ USDT для лонг-позиции, если требуется плечо
            if leverage > 1:
                loan_amount = (position_size_usdt - available_balance) * 1.1 # С запасом 1.1%
                if loan_amount > 0:
                    loan_amount = round(loan_amount, 8)
                    try:
                        log_event(f"Запрос на займ USDT: {loan_amount:.8f} USDT")
                        loan = client.create_margin_loan(
                            asset='USDT',
                            amount=str(loan_amount),
                            isIsolated='TRUE',
                            symbol=symbol
                        )
                        log_event("Займ USDT успешно создан!")
                    except Exception as e:
                        log_event(f"Ошибка при создании займа USDT: {e}")
                        return
                else:
                    log_event("Достаточно средств, займ USDT не требуется")
            else:
                log_event("Плечо 1x, займ USDT не нужен")

            time.sleep(5)  # Пауза для обработки займа

            # Отправка ордера на покупку (лонг)
            try:
                log_event(f"Отправка лонг-ордера на покупку {amount_btc:.{precision}f} BTC")
                order = client.create_margin_order(
                    symbol=symbol,
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=str(amount_btc),
                    isIsolated='TRUE'
                )
                log_event("Лонг-ордер успешно выполнен!")
            except Exception as e:
                log_event(f"Ошибка при отправке лонг-ордера: {e}")
                return

        else:
            log_event(f"⚠️ Неизвестный тип сделки: {trade_type}")
            return

        # Регистрация сделки
        current_trade_id = next_trade_id
        next_trade_id += 1
        entry_time = datetime.now()
        entry_time_str = entry_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        commission_open = position_value * (TRADING_CONFIG['COMMISSION_RATE'] / 100)

        new_trade = {
            'id': current_trade_id,
            'direction': trade_type,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'entry_time_str': entry_time_str,
            'current_price': entry_price,
            'size': amount_btc,
            'value': position_value,
            'leverage': leverage,
            'commission_open': commission_open,
            'status': 'open',
            'trailing_active': False if trailing_status is None else trailing_status,
            'max_price': entry_price,
        }
        active_trades[entry_time_str] = new_trade
        current_trade_type = trade_type

        # Логирование и запись в CSV
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
                'Entry_Price': float(entry_price),
                'Exit_Price': np.nan,
                'Position_Size': float(amount_btc),
                'Position_Value': float(position_value),
                'Leverage': float(leverage),
                'Net_PnL_USDT': np.nan,
                'Net_PnL_Percent': np.nan,
                'Balance': float(current_balance),
                'Withdraw': np.nan
            }
            # Проверка на пустоту или NaN перед объединением
            if df_trades is None or df_trades.empty or df_trades.isna().all().all():
                df_trades = pd.DataFrame([new_row])
            else:
                df_trades = pd.concat([df_trades, pd.DataFrame([new_row])], ignore_index=True)
            try:
                if not CSV_FILE.exists():
                    df_trades.to_csv(CSV_FILE, index=False, float_format='%.2f')
                else:
                    with open(CSV_FILE, 'a', newline='') as f:
                        pd.DataFrame([new_row]).to_csv(f, header=False, index=False, float_format='%.2f')
            except Exception as e:
                log_event(f"Ошибка при записи в CSV: {e}")





def close_all_trades(reason, exit_time=None, force_close=False, position_value=None):
    global df_trades, active_trades, trades_lock, TRADING_CONFIG, CSV_FILE, bull_long_trades_count, bull_short_trades_count, current_trade_type, client, symbol, current_market_type, last_orderbook_data

    start_time = time.time()
    trades_to_close = []

    with trades_lock:
        if not active_trades:
            log_event("⚪ Нет активных сделок для закрытия")
            return

        if exit_time is None:
            exit_time = datetime.now()
        exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        try:
            ticker = client.get_symbol_ticker(symbol='BTCUSDT')
            current_price = float(ticker['price'])
        except Exception as e:
            log_event(f"⚠️ Ошибка получения текущей цены: {e}")
            current_price = None

        for entry_time_str in list(active_trades.keys()):
            trade = active_trades[entry_time_str]
            exit_price = current_price if current_price else trade.get('current_price', 0)
            direction = trade['direction']

            # Получаем информацию о маржинальном счете для определения долга
            try:
                margin_account = client.get_isolated_margin_account(symbol=symbol)
                btc_asset = next(asset for asset in margin_account['assets'] if asset['symbol'] == symbol)['baseAsset']
                usdt_asset = next(asset for asset in margin_account['assets'] if asset['symbol'] == symbol)['quoteAsset']
                borrowed_btc = float(btc_asset['borrowed'])
                interest_btc = float(btc_asset['interest'])
                total_debt_btc = borrowed_btc + interest_btc
                borrowed_usdt = float(usdt_asset['borrowed'])
                interest_usdt = float(usdt_asset['interest'])
                total_debt_usdt = borrowed_usdt + interest_usdt
            except Exception as e:
                log_event(f"⚠️ Ошибка при получении данных о маржинальном счете: {e}")
                continue

            # Определяем объём для закрытия с учетом различий для лонг и шорт
            if position_value is not None:
                if 'SHORT' in direction:
                    # Для шорта закрываем часть от общего долга total_debt_btc
                    amount_to_close = min(position_value, total_debt_btc)
                    log_event(f"Частичное закрытие шорт: объем {amount_to_close:.8f} BTC (из долга {total_debt_btc:.8f} BTC)")
                elif 'LONG' in direction:
                    # Для лонга закрываем часть от размера позиции trade['size']
                    amount_to_close = min(position_value, trade['size'])
                    log_event(f"Частичное закрытие лонг: объем {amount_to_close:.8f} BTC (из позиции {trade['size']:.8f} BTC)")
            else:
                if 'SHORT' in direction:
                    amount_to_close = total_debt_btc
                    log_event(f"Полное закрытие шорт: объем {amount_to_close:.8f} BTC")
                elif 'LONG' in direction:
                    amount_to_close = trade['size']
                    log_event(f"Полное закрытие лонг: объем {amount_to_close:.8f} BTC")

            try:
                # Получаем точность для символа
                exchange_info = client.get_exchange_info()
                symbol_info = next(item for item in exchange_info['symbols'] if item['symbol'] == symbol)
                lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
                step_size = float(lot_size_filter['stepSize'])
                precision = int(round(-math.log(step_size, 10), 0))

                # Симметричное закрытие для шорт и лонг
                if 'SHORT' in direction:
                    log_event(f"Закрытие шорт-сделки: {direction}, объем: {amount_to_close:.8f} BTC, цена: {exit_price:.2f} USDT")
                    
                    # Рассчитываем Q для покупки с учетом комиссии
                    Q = amount_to_close / (1 - TRADING_CONFIG['COMMISSION_RATE'] / 100)
                    n = math.ceil(Q / step_size)
                    Q_to_buy = n * step_size
                    Q_to_buy_str = f"{Q_to_buy:.{precision}f}"
                    
                    # Покупка BTC для закрытия шорта
                    buy_order = client.create_margin_order(
                        symbol=symbol,
                        side=Client.SIDE_BUY,
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=Q_to_buy_str,
                        isIsolated='TRUE'
                    )

                    log_event(f"Пауза 15 секунд перед погашением задолженности BTC")
                    time.sleep(15)
                    
                    # Погашение долга BTC
                    margin_account = client.get_isolated_margin_account(symbol=symbol)
                    btc_asset = next(asset for asset in margin_account['assets'] if asset['symbol'] == symbol)['baseAsset']
                    free_btc = float(btc_asset['free'])
                    repay_amount = min(free_btc, amount_to_close)
                    repay_amount_str = f"{repay_amount:.{precision}f}"
                    repay = client.repay_margin_loan(
                        asset='BTC',
                        amount=repay_amount_str,
                        isIsolated='TRUE',
                        symbol=symbol
                    )
                    log_event(f"Шорт: Погашено {repay_amount_str} BTC из {total_debt_btc:.8f} BTC")

                elif 'LONG' in direction:
                    log_event(f"Закрытие лонг-сделки: {direction}, объем: {amount_to_close:.8f} BTC, цена: {exit_price:.2f} USDT")
                    
                    # Продажа BTC для закрытия лонга
                    Q_to_sell = amount_to_close
                    n = math.floor(Q_to_sell / step_size)
                    Q_to_sell = n * step_size
                    Q_to_sell_str = f"{Q_to_sell:.{precision}f}"
                    
                    sell_order = client.create_margin_order(
                        symbol=symbol,
                        side=Client.SIDE_SELL,
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=Q_to_sell_str,
                        isIsolated='TRUE'
                    )
                    
                    log_event(f"Пауза 15 секунд перед погашением задолженности USDT")
                    time.sleep(15)
                    
                    # Погашение долга USDT, если есть
                    margin_account = client.get_isolated_margin_account(symbol=symbol)
                    usdt_asset = next(asset for asset in margin_account['assets'] if asset['symbol'] == symbol)['quoteAsset']
                    free_usdt = float(usdt_asset['free'])
                    borrowed_usdt = float(usdt_asset['borrowed'])
                    interest_usdt = float(usdt_asset['interest'])
                    total_debt_usdt = borrowed_usdt + interest_usdt
                    repay_amount = min(free_usdt, total_debt_usdt)
                    repay_amount_str = f"{repay_amount:.8f}"
                    if total_debt_usdt > 0 and repay_amount > 0:
                        repay = client.repay_margin_loan(
                            asset='USDT',
                            amount=repay_amount_str,
                            isIsolated='TRUE',
                            symbol=symbol
                        )
                        log_event(f"Лонг: Погашено {repay_amount_str} USDT")
                    else:
                        log_event("Лонг: Долга USDT нет или сумма для погашения равна 0")

                else:
                    log_event(f"⚠️ Неизвестный тип сделки: {direction}")
                    continue

                # Расчёт длительности только если entry_time доступен
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

                # Расчёт комиссии только если entry_price доступен
                commission_open = 0
                if entry_price is not None:
                    commission_open = trade.get('commission_open', 0) * (amount_to_close / trade['size']) if trade['size'] > 0 else 0
                commission_close = amount_to_close * exit_price * (TRADING_CONFIG['COMMISSION_RATE'] / 100) if exit_price else 0
                total_commission = commission_open + commission_close

                # Расчёт PNL только если entry_price доступен
                net_pnl = 0
                net_pnl_percent = 0
                if entry_price is not None and exit_price > 0:
                    if 'SHORT' in direction:
                        pnl = (entry_price - exit_price) * amount_to_close * leverage
                    elif 'LONG' in direction:
                        pnl = (exit_price - entry_price) * amount_to_close * leverage
                    net_pnl = pnl - total_commission
                    net_pnl_percent = (net_pnl / (trade['value'] * (amount_to_close / trade['size']))) * 100 if trade['size'] > 0 and trade.get('value') else 0
                else:
                    log_event("⚠️ Цена входа отсутствует, PNL не рассчитывается")

                # Перевод прибыли на спот (только для полного закрытия)
                withdraw_amount = 0.0
                if position_value is None and net_pnl > 0:
                    withdraw_amount = net_pnl * (TRADING_CONFIG['WITHDRAW_PERCENT'] / 100)
                    if withdraw_amount >= 0.02:
                        try:
                            available_balance = get_available_balance()
                            if available_balance >= withdraw_amount:
                                transfer_to_cross_and_spot(withdraw_amount, "BTCUSDT", "USDT")
                                log_event(f"Переведено {withdraw_amount:.2f} USDT на спотовый счет")
                            else:
                                log_event(f"Недостаточно средств: {available_balance:.2f} < {withdraw_amount:.2f}")
                                withdraw_amount = 0.0
                        except Exception as e:
                            log_event(f"Ошибка при переводе: {e}")
                            withdraw_amount = 0.0
                    else:
                        log_event(f"Сумма для перевода {withdraw_amount:.2f} USDT < 0.02")
                        withdraw_amount = 0.0

                # Обновление позиции
                if position_value is not None:
                    if 'SHORT' in direction:
                        # Для шорта обновляем размер долга
                        trade['size'] = total_debt_btc - amount_to_close
                        if trade['size'] <= 0:
                            del active_trades[entry_time_str]
                            log_event(f"Позиция {direction} полностью закрыта после частичного закрытия")
                        else:
                            log_event(f"Оставшийся долг шорт: {trade['size']:.8f} BTC")
                    elif 'LONG' in direction:
                        # Для лонга обновляем размер позиции
                        trade['size'] -= amount_to_close
                        if trade['size'] <= 0:
                            del active_trades[entry_time_str]
                            log_event(f"Позиция {direction} полностью закрыта после частичного закрытия")
                        else:
                            log_event(f"Оставшийся размер лонг: {trade['size']:.8f} BTC")
                    if trade.get('value'):
                        trade['value'] *= (trade['size'] / (trade['size'] + amount_to_close)) if trade['size'] + amount_to_close > 0 else 0
                    trade['commission_open'] = trade.get('commission_open', 0) - commission_open if entry_price is not None else 0
                    if trade['size'] > 0:
                        log_event(f"Пауза 15 секунд для пересчета цены ликвидации")
                        time.sleep(15)
                        manage_liquidation_price()
                else:
                    del active_trades[entry_time_str]
                    log_event(f"Позиция {direction} полностью закрыта")

                # Обновление счетчиков сделок для открытия обратной сделки на Бычьем рынке
                if direction == 'BULL_LONG':
                    bull_long_trades_count += 1
                elif direction == 'BULL_SHORT':
                    bull_short_trades_count += 1

                trades_to_close.append({
                    'entry_time': entry_time,
                    'trade_id': trade['id'],
                    'exit_time': exit_time,
                    'duration': duration_str,
                    'duration_hours': duration_hours,
                    'exit_price': exit_price,
                    'entry_price': entry_price,
                    'position_size': amount_to_close,
                    'position_value': trade.get('value', 0) * (amount_to_close / trade['size']) if trade['size'] > 0 and entry_price is not None else 0,
                    'leverage': leverage,
                    'net_pnl': net_pnl,
                    'net_pnl_percent': net_pnl_percent,
                    'direction': direction,
                    'withdraw_amount': withdraw_amount
                })

            except Exception as e:
                log_event(f"⚠️ Ошибка при закрытии {direction}: {e}")
                continue

        # Сброс счетчиков и открытие обратной сделки только при полном закрытии
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

    # Обновление CSV
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
                # Проверка на пустоту или NaN перед объединением
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
    with trades_lock:
        if not active_trades:
            log_event("⚪ Нет активных позиций")
            return

        # Получаем данные о маржинальном счёте
        try:
            account = client.get_isolated_margin_account(symbol=symbol)
            position = account['assets'][0]
            base_asset = position['baseAsset']  # BTC
            quote_asset = position['quoteAsset']  # USDT
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении данных о маржинальном счете: {e}")
            return

        # Извлекаем балансы и задолженности
        btc_balance = float(base_asset['free']) + float(base_asset['locked'])  # Свободный + заблокированный BTC
        btc_borrowed = float(base_asset['borrowed'])  # Задолженность BTC
        usdt_balance = float(quote_asset['free']) + float(quote_asset['locked'])  # Свободный + заблокированный USDT
        usdt_borrowed = float(quote_asset['borrowed'])  # Задолженность USDT

        # Получаем текущую рыночную цену BTC
        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
        except Exception as e:
            log_event(f"⚠️ Ошибка при получении текущей цены: {e}")
            current_price = 0

        # Пересчитываем BTC баланс в USDT
        btc_balance_usdt = btc_balance * current_price if current_price > 0 else 0
        btc_borrowed_balance_usdt = btc_borrowed * current_price if current_price > 0 else 0

        # Получаем тип сделки и размер плеча
        trade = list(active_trades.values())[0]
        direction = trade['direction']
        leverage = trade.get('leverage', 1)

        # Определяем эмодзи в зависимости от типа сделки
        emoji = '🟢' if 'LONG' in direction.upper() else '🔴' if 'SHORT' in direction.upper() else ''

        # Получаем цену ликвидации
        liquidation_price = float(position.get('liquidatePrice', 0))

        # Рассчитываем дельту только если цены доступны
        delta_percent = None
        if current_price > 0 and liquidation_price > 0:
            if 'LONG' in direction.upper():
                delta_percent = (current_price - liquidation_price) / current_price * 100
            elif 'SHORT' in direction.upper():
                delta_percent = (liquidation_price - current_price) / current_price * 100

        # Вывод информации
        log_event("----------------------------------------------|")
        log_event("------------------ ПОЗИЦИЯ -------------------|")
        log_event("----------------------------------------------|")
        log_event(f"{emoji} {direction} | Плечо: {leverage}x")
        log_event(f"💰 BTC баланс: {btc_balance:.8f} BTC (≈ {btc_balance_usdt:.2f} USDT)")
        log_event(f"💸 BTC задолженность: {btc_borrowed:.8f} BTC (≈ {btc_borrowed_balance_usdt:.2f} USDT)")
        log_event(f"💰 USDT баланс: {usdt_balance:.2f} USDT")
        log_event(f"💸 USDT задолженность: {usdt_borrowed:.2f} USDT")
        log_event(f"💥 Ликвидация: {'--' if liquidation_price <= 0 else f'{liquidation_price:.2f}'} USDT | Дельта: {'--' if delta_percent is None else f'{delta_percent:.2f}%'}")
        log_event("----------------------------------------------|")



# ★ Запуск WebSocket ★
def start_websocket(url, on_message_func):
    """Запускает WebSocket для реального времени."""
    while True:
        try:
            ws = websocket.WebSocketApp(url, on_message=on_message_func)
            ws.run_forever(ping_interval=5, ping_timeout=3)
        except Exception as e:
            error_msg = f"Ошибка WebSocket ({url}): {e}. Перезапуск через 3 секунды..."
            log_event(f"⚠️ {error_msg}")
            log_to_error_file(error_msg)
            time.sleep(3)




def run():
    """Запускает скрипт в реальном режиме, включая синхронизацию активных сделок и запуск WebSocket."""
    global next_trade_id, RSI_PERIOD, SMA_RSI_PERIOD, fear_greed_data, next_rsi_update_time, current_rsi, current_sma_rsi, previous_rsi, previous_sma_rsi


    # Загрузка и сохранение данных индекса страха и жадности
    fear_greed_data = fetch_fear_greed_data()
    if not fear_greed_data:
        print("Не удалось получить данные индекса страха и жадности")
    
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
    ticker = client.get_symbol_ticker(symbol='BTCUSDT')
    current_price = float(ticker['price'])

    # Задаём размер позиции
    position_value = get_available_balance()

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

    # close_amount = 0.0001
    # log_event(f"Рассчитан объем для закрытия: {close_amount:.8f} BTC")
    # # Передаём объем в функцию закрытия через position_value
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



    # Запуск WebSocket для реального режима
    threading.Thread(
        target=start_websocket,
        args=("wss://stream.binance.com:9443/ws/btcusdt@depth10@100ms", on_orderbook_message),
        daemon=True
    ).start()



# Основной цикл для реального режима
    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        initialize_csv()
        run()
    except Exception as e:
        error_msg = f"Ошибка выполнения скрипта: {e}"
        print(error_msg)
        with open("error_log.txt", "a", encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {error_msg}\n")
        raise  



# Говори по Русски! 



# Интегрируй изменения в эту версию и напиши ПОЛНОСТЬЮ только функции с изменениями 

