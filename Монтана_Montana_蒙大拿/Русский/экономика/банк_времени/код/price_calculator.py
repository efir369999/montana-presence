#!/usr/bin/env python3
"""
price_calculator.py — Расчёт цены Montana

Montana Protocol
Якорь Beeple: $69.3M / 5000 дней = $0.1605/сек
"""

from typing import Optional
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════
#                         КОНСТАНТЫ BEEPLE ANCHOR
# ═══════════════════════════════════════════════════════════════════════════

class BeepleAnchor:
    """
    Якорь Beeple — фиксация цены Montana через продажу Beeple NFT

    История:
    - 11 марта 2021: Beeple "Everydays: The First 5000 Days" продан за $69.3M
    - Расчёт: $69.3M / 5000 дней = $13,860/день = $0.1605/сек

    Этот якорь связывает Montana с реальным миром через исторический момент
    """

    # Genesis фиксация
    SALE_PRICE_USD = 69_346_250.00      # Цена продажи Beeple NFT в USD
    TOTAL_DAYS = 5000                   # Количество дней в работе
    SALE_DATE = "2021-03-11"            # Дата продажи

    # Вычисленные константы
    USD_PER_DAY = SALE_PRICE_USD / TOTAL_DAYS         # $13,869.25/день
    USD_PER_HOUR = USD_PER_DAY / 24                   # $577.885/час
    USD_PER_MINUTE = USD_PER_HOUR / 60                # $9.6314/минута
    USD_PER_SECOND = USD_PER_MINUTE / 60              # $0.1605/секунда

    # Соотношение Montana:USD
    # 1 секунда Montana = 1 MTA
    # 1 MTA = $0.1605
    MTA_PER_SECOND = 1.0
    USD_PER_MTA = USD_PER_SECOND


# ═══════════════════════════════════════════════════════════════════════════
#                         PRICE CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════

def mta_to_usd(mta_amount: float) -> float:
    """
    Конвертировать Montana в USD

    Args:
        mta_amount: Количество MTA (секунды)

    Returns:
        Эквивалент в USD

    Example:
        >>> mta_to_usd(600)  # 10 минут
        96.3
    """
    return mta_amount * BeepleAnchor.USD_PER_MTA


def usd_to_mta(usd_amount: float) -> float:
    """
    Конвертировать USD в Montana

    Args:
        usd_amount: Количество USD

    Returns:
        Эквивалент в MTA (секунды)

    Example:
        >>> usd_to_mta(0.1605)  # $0.1605
        1.0
    """
    return usd_amount / BeepleAnchor.USD_PER_MTA


def seconds_to_usd(seconds: int) -> float:
    """
    Конвертировать секунды присутствия в USD

    Args:
        seconds: Количество секунд

    Returns:
        Эквивалент в USD

    Example:
        >>> seconds_to_usd(600)  # 10 минут
        96.3
    """
    return seconds * BeepleAnchor.USD_PER_SECOND


def usd_to_seconds(usd_amount: float) -> float:
    """
    Конвертировать USD в секунды присутствия

    Args:
        usd_amount: Количество USD

    Returns:
        Эквивалент в секундах

    Example:
        >>> usd_to_seconds(96.3)  # $96.3
        600.0
    """
    return usd_amount / BeepleAnchor.USD_PER_SECOND


def days_to_usd(days: float) -> float:
    """
    Конвертировать дни работы в USD

    Args:
        days: Количество дней

    Returns:
        Эквивалент в USD

    Example:
        >>> days_to_usd(1)  # 1 день
        13869.25
    """
    return days * BeepleAnchor.USD_PER_DAY


def usd_to_days(usd_amount: float) -> float:
    """
    Конвертировать USD в дни работы

    Args:
        usd_amount: Количество USD

    Returns:
        Эквивалент в днях

    Example:
        >>> usd_to_days(13869.25)  # $13,869.25
        1.0
    """
    return usd_amount / BeepleAnchor.USD_PER_DAY


def get_anchor_info() -> dict:
    """
    Получить информацию о якоре Beeple

    Returns:
        {
            "sale_price_usd": 69346250.0,
            "total_days": 5000,
            "sale_date": "2021-03-11",
            "usd_per_second": 0.1605,
            "usd_per_minute": 9.6314,
            "usd_per_hour": 577.885,
            "usd_per_day": 13869.25,
            "mta_per_second": 1.0,
            "usd_per_mta": 0.1605
        }
    """
    return {
        "sale_price_usd": BeepleAnchor.SALE_PRICE_USD,
        "total_days": BeepleAnchor.TOTAL_DAYS,
        "sale_date": BeepleAnchor.SALE_DATE,
        "usd_per_second": BeepleAnchor.USD_PER_SECOND,
        "usd_per_minute": BeepleAnchor.USD_PER_MINUTE,
        "usd_per_hour": BeepleAnchor.USD_PER_HOUR,
        "usd_per_day": BeepleAnchor.USD_PER_DAY,
        "mta_per_second": BeepleAnchor.MTA_PER_SECOND,
        "usd_per_mta": BeepleAnchor.USD_PER_MTA
    }


def format_price(usd_amount: float, currency: str = "USD") -> str:
    """
    Форматировать цену для отображения

    Args:
        usd_amount: Сумма в USD
        currency: Валюта (USD, EUR, RUB, etc.)

    Returns:
        Отформатированная строка

    Example:
        >>> format_price(96.31)
        "$96.31 USD"
    """
    if currency == "USD":
        return f"${usd_amount:.2f} USD"
    elif currency == "MTA":
        mta = usd_to_mta(usd_amount)
        return f"{mta:.2f} MTA"
    else:
        return f"{usd_amount:.2f} {currency}"


# ═══════════════════════════════════════════════════════════════════════════
#                         PIZZA DAY MECHANISM
# ═══════════════════════════════════════════════════════════════════════════

class PizzaDayCalculator:
    """
    Pizza Day механизм — переоценка якоря через Pizza Day

    История:
    - 22 мая 2010: 10,000 BTC = 2 пиццы ($25)
    - 22 мая 2021: 10,000 BTC = $390M

    Механизм:
    - Каждый Pizza Day (22 мая) можно переоценить якорь
    - Старый якорь: Beeple $69.3M / 5000 дней
    - Новый якорь: актуальная оценка творческой работы
    """

    PIZZA_DAY_MONTH = 5   # Май
    PIZZA_DAY_DAY = 22    # 22-е число

    @staticmethod
    def is_pizza_day(date: datetime = None) -> bool:
        """
        Проверить, является ли дата Pizza Day

        Args:
            date: Дата для проверки (по умолчанию сегодня)

        Returns:
            True если 22 мая
        """
        if date is None:
            date = datetime.now(timezone.utc)

        return (date.month == PizzaDayCalculator.PIZZA_DAY_MONTH and
                date.day == PizzaDayCalculator.PIZZA_DAY_DAY)

    @staticmethod
    def days_until_pizza_day(date: datetime = None) -> int:
        """
        Сколько дней до следующего Pizza Day

        Args:
            date: Дата отсчёта (по умолчанию сегодня)

        Returns:
            Количество дней до 22 мая
        """
        if date is None:
            date = datetime.now(timezone.utc)

        current_year = date.year
        pizza_day_this_year = datetime(
            current_year,
            PizzaDayCalculator.PIZZA_DAY_MONTH,
            PizzaDayCalculator.PIZZA_DAY_DAY,
            tzinfo=timezone.utc
        )

        if date > pizza_day_this_year:
            # Pizza Day уже прошёл в этом году, считаем до следующего
            pizza_day_next_year = datetime(
                current_year + 1,
                PizzaDayCalculator.PIZZA_DAY_MONTH,
                PizzaDayCalculator.PIZZA_DAY_DAY,
                tzinfo=timezone.utc
            )
            delta = pizza_day_next_year - date
        else:
            # Pizza Day ещё не прошёл в этом году
            delta = pizza_day_this_year - date

        return delta.days

    @staticmethod
    def recalculate_anchor(new_sale_price: float, new_total_days: int) -> dict:
        """
        Пересчитать якорь с новыми значениями

        Args:
            new_sale_price: Новая цена продажи (USD)
            new_total_days: Новое количество дней работы

        Returns:
            Новые константы якоря

        Example:
            >>> PizzaDayCalculator.recalculate_anchor(100_000_000, 10_000)
            {"usd_per_second": 0.1157, ...}
        """
        usd_per_day = new_sale_price / new_total_days
        usd_per_hour = usd_per_day / 24
        usd_per_minute = usd_per_hour / 60
        usd_per_second = usd_per_minute / 60

        return {
            "sale_price_usd": new_sale_price,
            "total_days": new_total_days,
            "usd_per_day": usd_per_day,
            "usd_per_hour": usd_per_hour,
            "usd_per_minute": usd_per_minute,
            "usd_per_second": usd_per_second,
            "mta_per_second": 1.0,
            "usd_per_mta": usd_per_second
        }


# ═══════════════════════════════════════════════════════════════════════════
#                              EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    'BeepleAnchor',
    'mta_to_usd',
    'usd_to_mta',
    'seconds_to_usd',
    'usd_to_seconds',
    'days_to_usd',
    'usd_to_days',
    'get_anchor_info',
    'format_price',
    'PizzaDayCalculator'
]


# ═══════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🏔 Montana Price Calculator")
    print("=" * 60)

    # Показать якорь
    print("\n📍 Якорь Beeple:")
    print(f"   Цена продажи: ${BeepleAnchor.SALE_PRICE_USD:,.2f}")
    print(f"   Количество дней: {BeepleAnchor.TOTAL_DAYS}")
    print(f"   Дата продажи: {BeepleAnchor.SALE_DATE}")
    print(f"\n   USD/секунда: ${BeepleAnchor.USD_PER_SECOND:.4f}")
    print(f"   USD/минута: ${BeepleAnchor.USD_PER_MINUTE:.4f}")
    print(f"   USD/час: ${BeepleAnchor.USD_PER_HOUR:.2f}")
    print(f"   USD/день: ${BeepleAnchor.USD_PER_DAY:,.2f}")

    # Примеры конвертации
    print("\n💰 Примеры конвертации:")
    print(f"   600 сек (10 мин) = {format_price(seconds_to_usd(600))}")
    print(f"   3600 сек (1 час) = {format_price(seconds_to_usd(3600))}")
    print(f"   86400 сек (1 день) = {format_price(seconds_to_usd(86400))}")

    print(f"\n   $100 = {usd_to_seconds(100):.0f} секунд ({usd_to_seconds(100)/60:.1f} минут)")
    print(f"   $1000 = {usd_to_seconds(1000):.0f} секунд ({usd_to_seconds(1000)/3600:.1f} часов)")

    # Pizza Day
    print("\n🍕 Pizza Day Mechanism:")
    print(f"   Сегодня Pizza Day? {PizzaDayCalculator.is_pizza_day()}")
    print(f"   Дней до Pizza Day: {PizzaDayCalculator.days_until_pizza_day()}")

    print("\n✅ Калькулятор готов!")
