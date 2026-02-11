#!/usr/bin/env python3
"""
beeple_benchmark.py — Генезис цены времени Montana

Источник: Christie's Auction, 12 марта 2021
Работа: Beeple "Everydays: The First 5000 Days"
Цена: $69,346,250
Время работы: 5000 дней

Формула: $69,346,250 ÷ 5000 дней ÷ 86400 секунд = $0.160523726(851)̅

Это GENESIS цены времени — первая публичная фиксация стоимости секунды.
"""

from decimal import Decimal, getcontext
from datetime import datetime, timezone
from typing import Dict

# Высокая точность для бесконечной дроби
getcontext().prec = 50


# ═══════════════════════════════════════════════════════════════════════════════
#                         GENESIS CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Аукцион Christie's
BEEPLE_SALE_USD = Decimal("69346250")  # $69,346,250
BEEPLE_DAYS = Decimal("5000")           # 5000 дней работы
SECONDS_PER_DAY = Decimal("86400")      # 24 * 60 * 60

# ═══════════════════════════════════════════════════════════════════════════════
#                         GENESIS TRANSACTION (ФИНАЛЬНАЯ)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Хронология:
# 1. 2021-02-16 05:58:01 UTC — Минт NFT (Token ID #40913)
# 2. 2021-03-11 15:00:00 UTC — Закрытие аукциона Christie's
# 3. 2021-03-13 03:58:XX UTC — Передача в escrow MakersPlace
# 4. 2021-03-13 05:16:XX UTC — ФИНАЛЬНАЯ передача к MetaKovan ← GENESIS
#
# Книга Монтана: "12.03.2021 05:16:XX UTC — генезис цены времени"
# (формат DD.MM.YYYY, но фактически 13 марта по UTC)

# GENESIS = финальная транзакция передачи NFT к покупателю MetaKovan
# Etherscan: Mar-13-2021 04:16:33 AM UTC
GENESIS_TIMESTAMP = "2021-03-13T04:16:33+00:00"
GENESIS_DATE = "2021-03-13"
GENESIS_TIME_UTC = "04:16:33"

# Ethereum transaction data
ETHEREUM_TX_MINT = "0x84760768c527794ede901f97973385bfc1bf2e297f7ed16f523f75412ae772b3"
ETHEREUM_TX_ESCROW = "0xa342e9de61c34900883218fe52bc9931daa1a10b6f48c506f2253c279b15e5bf"
ETHEREUM_TX_FINAL = "0x01d0967faaaf95f3e19164803a1cf1a2f96644ebfababb2b810d41a72f502d49"  # GENESIS

TOKEN_ID = 40913
BEEPLE_WALLET = "0xc6b0562605D35eE710138402B878ffe6F2E23807"
MAKERSPLACE_CONTRACT = "0x2a46f2ffd99e19a89476e2f62270e0a35bbf0756"
MAKERSPLACE_ESCROW = "0x58bf1fbeac9596fc20d87d346423d7d108c5361a"
METAKOVAN_WALLET = "0x8bb37fb0f0462bb3fc8995cf17721f8e4a399629"

# Хронология
# 1. 2021-02-16 05:58:01 UTC — Минт NFT
# 2. 2021-02-25             — Открытие аукциона Christie's
# 3. 2021-03-11 15:00 EST   — Закрытие аукциона ($69,346,250)
# 4. 2021-03-13 03:58:XX UTC — Beeple → MakersPlace escrow
# 5. 2021-03-13 04:16:33 UTC — MakersPlace → MetaKovan (GENESIS)
NFT_MINTED_DATE = "2021-02-16"
NFT_MINTED_TIMESTAMP = "2021-02-16T05:58:01+00:00"
AUCTION_OPEN_DATE = "2021-02-25"
AUCTION_CLOSE_DATE = "2021-03-11"
FINAL_TRANSFER_DATE = "2021-03-13"
FINAL_TRANSFER_TIMESTAMP = "2021-03-13T04:16:33+00:00"  # GENESIS

# Покупатель
BUYER_PSEUDONYM = "MetaKovan"
BUYER_NAME = "Vignesh Sundaresan"
BUYER_PROJECT = "Metapurse"
BUYER_COUNTRY = "Singapore"

# Характеристики NFT
NFT_DIMENSIONS = "21,069 x 21,069 pixels"
NFT_SIZE_BYTES = 319_168_313  # ~319 MB
NFT_TITLE = "Everydays: The First 5000 Days"
NFT_ARTIST = "Beeple (Mike Winkelmann)"

# Расчёт цены секунды
PRICE_PER_DAY = BEEPLE_SALE_USD / BEEPLE_DAYS
PRICE_PER_SECOND = BEEPLE_SALE_USD / (BEEPLE_DAYS * SECONDS_PER_DAY)

# Округлённое значение для UI
PRICE_PER_SECOND_ROUNDED = Decimal("0.16")


# ═══════════════════════════════════════════════════════════════════════════════
#                         GENESIS EXCHANGE RATES (12.03.2021)
# ═══════════════════════════════════════════════════════════════════════════════

# Курсы валют на момент GENESIS транзакции (13.03.2021 04:16:33 UTC)
# Формат: 1 USD = X валюты (для фиата), или 1 крипто = X USD (для крипто)

GENESIS_RATES_FIAT = {
    # Основные мировые валюты
    "USD": ("$", "US Dollar", Decimal("1.0")),
    "EUR": ("€", "Euro", Decimal("0.84")),
    "GBP": ("£", "British Pound", Decimal("0.72")),
    "JPY": ("¥", "Japanese Yen", Decimal("108.50")),
    "CHF": ("Fr", "Swiss Franc", Decimal("0.93")),

    # СНГ
    "RUB": ("₽", "Russian Ruble", Decimal("73.50")),
    "UAH": ("₴", "Ukrainian Hryvnia", Decimal("27.80")),
    "KZT": ("₸", "Kazakh Tenge", Decimal("420.00")),
    "BYN": ("Br", "Belarusian Ruble", Decimal("2.60")),
    "AMD": ("֏", "Armenian Dram", Decimal("522.00")),
    "GEL": ("₾", "Georgian Lari", Decimal("3.30")),
    "AZN": ("₼", "Azerbaijani Manat", Decimal("1.70")),
    "UZS": ("сўм", "Uzbek Som", Decimal("10500.00")),

    # Азия
    "CNY": ("¥", "Chinese Yuan", Decimal("6.50")),
    "HKD": ("HK$", "Hong Kong Dollar", Decimal("7.76")),
    "TWD": ("NT$", "Taiwan Dollar", Decimal("28.50")),
    "KRW": ("₩", "South Korean Won", Decimal("1130.00")),
    "SGD": ("S$", "Singapore Dollar", Decimal("1.34")),
    "INR": ("₹", "Indian Rupee", Decimal("72.50")),
    "THB": ("฿", "Thai Baht", Decimal("30.50")),
    "VND": ("₫", "Vietnamese Dong", Decimal("23000.00")),
    "IDR": ("Rp", "Indonesian Rupiah", Decimal("14400.00")),
    "MYR": ("RM", "Malaysian Ringgit", Decimal("4.10")),
    "PHP": ("₱", "Philippine Peso", Decimal("48.50")),

    # Ближний Восток
    "AED": ("د.إ", "UAE Dirham", Decimal("3.67")),
    "SAR": ("﷼", "Saudi Riyal", Decimal("3.75")),
    "ILS": ("₪", "Israeli Shekel", Decimal("3.30")),
    "TRY": ("₺", "Turkish Lira", Decimal("7.50")),

    # Америка
    "CAD": ("C$", "Canadian Dollar", Decimal("1.26")),
    "MXN": ("$", "Mexican Peso", Decimal("20.90")),
    "BRL": ("R$", "Brazilian Real", Decimal("5.60")),
    "ARS": ("$", "Argentine Peso", Decimal("90.50")),
    "CLP": ("$", "Chilean Peso", Decimal("720.00")),
    "COP": ("$", "Colombian Peso", Decimal("3650.00")),
    "PEN": ("S/", "Peruvian Sol", Decimal("3.65")),

    # Океания
    "AUD": ("A$", "Australian Dollar", Decimal("1.30")),
    "NZD": ("NZ$", "New Zealand Dollar", Decimal("1.40")),

    # Африка
    "ZAR": ("R", "South African Rand", Decimal("15.10")),
    "NGN": ("₦", "Nigerian Naira", Decimal("380.00")),
    "EGP": ("E£", "Egyptian Pound", Decimal("15.70")),

    # Европа (не EUR)
    "PLN": ("zł", "Polish Zloty", Decimal("3.85")),
    "CZK": ("Kč", "Czech Koruna", Decimal("22.00")),
    "SEK": ("kr", "Swedish Krona", Decimal("8.50")),
    "NOK": ("kr", "Norwegian Krone", Decimal("8.55")),
    "DKK": ("kr", "Danish Krone", Decimal("6.25")),
    "HUF": ("Ft", "Hungarian Forint", Decimal("305.00")),
    "RON": ("lei", "Romanian Leu", Decimal("4.10")),
}

GENESIS_RATES_CRYPTO = {
    # Цена в USD на 12.03.2021
    "BTC": ("₿", "Bitcoin", Decimal("57500")),
    "ETH": ("Ξ", "Ethereum", Decimal("1820")),
    "SOL": ("◎", "Solana", Decimal("14.50")),
    "BNB": ("BNB", "Binance Coin", Decimal("265")),
    "ADA": ("₳", "Cardano", Decimal("1.15")),
    "DOT": ("DOT", "Polkadot", Decimal("36.50")),
    "XRP": ("XRP", "Ripple", Decimal("0.45")),
    "DOGE": ("Ð", "Dogecoin", Decimal("0.055")),
    "LTC": ("Ł", "Litecoin", Decimal("195")),
    "LINK": ("LINK", "Chainlink", Decimal("28.50")),
}

# Расчёт цены секунды во всех валютах
SECOND_PRICE_ALL = {}

# Фиат: price_per_second * exchange_rate
for code, (symbol, name, rate) in GENESIS_RATES_FIAT.items():
    SECOND_PRICE_ALL[code] = {
        "symbol": symbol,
        "name": name,
        "price": PRICE_PER_SECOND * rate,
        "rate": rate,
        "type": "fiat"
    }

# Крипто: price_per_second / crypto_price_usd
for code, (symbol, name, price_usd) in GENESIS_RATES_CRYPTO.items():
    SECOND_PRICE_ALL[code] = {
        "symbol": symbol,
        "name": name,
        "price": PRICE_PER_SECOND / price_usd,
        "rate": price_usd,
        "type": "crypto"
    }


# ═══════════════════════════════════════════════════════════════════════════════
#                         BEEPLE BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

class BeepleBenchmark:
    """
    Генезис цены времени из аукциона Beeple.

    Книга Монтана, Глава 03:
    > "$0.16 за секунду было установлено публично.
    > На глазах у всех. Никто не заметил."
    """

    def __init__(self):
        self.sale_usd = BEEPLE_SALE_USD
        self.days = BEEPLE_DAYS
        self.genesis_time = datetime.fromisoformat(GENESIS_TIMESTAMP)

    def get_price_per_second(self, precision: int = 20) -> Decimal:
        """
        Цена секунды с заданной точностью.

        Returns:
            Decimal: $0.160523726851851851851...
        """
        getcontext().prec = precision + 10
        return self.sale_usd / (self.days * SECONDS_PER_DAY)

    def get_price_per_day(self) -> Decimal:
        """Цена дня работы."""
        return self.sale_usd / self.days  # $13,869.25

    def get_price_per_hour(self) -> Decimal:
        """Цена часа работы."""
        return self.get_price_per_day() / Decimal("24")  # $577.89

    def get_price_per_minute(self) -> Decimal:
        """Цена минуты работы."""
        return self.get_price_per_hour() / Decimal("60")  # $9.63

    def seconds_since_genesis(self) -> int:
        """Секунды с момента генезиса."""
        now = datetime.now(timezone.utc)
        delta = now - self.genesis_time
        return int(delta.total_seconds())

    def value_of_time(self, seconds: int) -> Dict[str, Decimal]:
        """
        Стоимость времени во ВСЕХ валютах (genesis rates 12.03.2021).

        Args:
            seconds: Количество секунд

        Returns:
            Dict с ценами в USD, RUB, EUR, CNY, BTC, ETH и др.
        """
        result = {"seconds": Decimal(seconds)}

        for currency, price_per_sec in SECOND_PRICE_ALL.items():
            result[currency] = price_per_sec * Decimal(seconds)

        return result

    def get_all_second_prices(self) -> Dict[str, Decimal]:
        """Цена 1 секунды во всех валютах на момент genesis."""
        return SECOND_PRICE_ALL.copy()

    def get_btc_price_per_second(self) -> Decimal:
        """Цена секунды в Bitcoin (genesis rate)."""
        return SECOND_PRICE_ALL["BTC"]

    def get_eth_price_per_second(self) -> Decimal:
        """Цена секунды в Ethereum (genesis rate)."""
        return SECOND_PRICE_ALL["ETH"]

    def format_price(self) -> str:
        """Человекочитаемый формат цены."""
        price = self.get_price_per_second(precision=15)
        return f"${price:.12f}/sec (repeating 851)"

    def get_genesis_info(self) -> Dict:
        """Полная информация о генезисе цены времени."""
        return {
            "event": "Christie's Auction - Beeple Everydays: The First 5000 Days",
            "genesis_timestamp": GENESIS_TIMESTAMP,
            "genesis_date": GENESIS_DATE,
            "genesis_time_utc": GENESIS_TIME_UTC,
            "sale_usd": float(self.sale_usd),
            "sale_eth": 42329.453,
            "days_of_work": int(self.days),
            "price_per_second_usd": float(self.get_price_per_second()),
            "price_per_second_rounded": 0.16,
            "formula": "$69,346,250 ÷ 5000 days ÷ 86400 sec = $0.160523726(851)̅",

            # Ethereum data
            "ethereum_tx_final": ETHEREUM_TX_FINAL,
            "token_id": TOKEN_ID,
            "from_wallet": MAKERSPLACE_ESCROW,
            "to_wallet": METAKOVAN_WALLET,

            # Участники
            "artist": NFT_ARTIST,
            "buyer": f"{BUYER_NAME} ({BUYER_PSEUDONYM})",
            "buyer_project": BUYER_PROJECT,
            "auction_house": "Christie's",

            "book_reference": "Книга Монтана, Глава 03. Поток"
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_second_price() -> Decimal:
    """Быстрый доступ к цене секунды."""
    return PRICE_PER_SECOND


def get_second_price_rounded() -> Decimal:
    """Округлённая цена для UI."""
    return PRICE_PER_SECOND_ROUNDED


def calculate_time_value(seconds: int) -> Decimal:
    """Стоимость N секунд в USD."""
    return PRICE_PER_SECOND * Decimal(seconds)


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    benchmark = BeepleBenchmark()

    print("=" * 60)
    print("BEEPLE BENCHMARK — Genesis цены времени")
    print("=" * 60)

    info = benchmark.get_genesis_info()
    print(f"\nСобытие: {info['event']}")
    print(f"Дата: {info['date']}")
    print(f"Сумма: ${info['sale_usd']:,.0f}")
    print(f"Дней работы: {info['days_of_work']}")

    print(f"\n--- ЦЕНА 1 СЕКУНДЫ (Genesis 12.03.2021) ---")
    prices = benchmark.get_all_second_prices()

    print("\nФиат:")
    print(f"  USD: ${float(prices['USD']):.12f}")
    print(f"  RUB: ₽{float(prices['RUB']):.6f}")
    print(f"  EUR: €{float(prices['EUR']):.6f}")
    print(f"  GBP: £{float(prices['GBP']):.6f}")
    print(f"  CNY: ¥{float(prices['CNY']):.6f}")
    print(f"  JPY: ¥{float(prices['JPY']):.4f}")

    print("\nКрипто:")
    print(f"  BTC: ₿{float(prices['BTC']):.10f}  (при BTC=$57,500)")
    print(f"  ETH: Ξ{float(prices['ETH']):.8f}   (при ETH=$1,820)")
    print(f"  SOL: ◎{float(prices['SOL']):.6f}    (при SOL=$14.50)")

    print(f"\n--- ЦЕНА ВРЕМЕНИ USD ---")
    print(f"За секунду: {benchmark.format_price()}")
    print(f"За минуту:  ${benchmark.get_price_per_minute():.2f}")
    print(f"За час:     ${benchmark.get_price_per_hour():.2f}")
    print(f"За день:    ${benchmark.get_price_per_day():.2f}")

    print(f"\n--- ПРИМЕР: 1 час твоего времени ---")
    hour_value = benchmark.value_of_time(3600)
    print(f"  USD: ${float(hour_value['USD']):.2f}")
    print(f"  RUB: ₽{float(hour_value['RUB']):.2f}")
    print(f"  BTC: ₿{float(hour_value['BTC']):.8f}")
    print(f"  ETH: Ξ{float(hour_value['ETH']):.6f}")

    print(f"\n--- СЕКУНД С ГЕНЕЗИСА ---")
    print(f"{benchmark.seconds_since_genesis():,} секунд")

    print("\n" + "=" * 60)
    print("Книга Монтана: 'Никто не заметил. Ты заметил.'")
    print("=" * 60)
