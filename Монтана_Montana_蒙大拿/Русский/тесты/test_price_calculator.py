#!/usr/bin/env python3
"""
test_price_calculator.py — Unit tests для price_calculator.py

Montana Protocol
Тестирование ценового калькулятора и якоря Beeple
"""

import sys
import os
import unittest
from datetime import datetime, timezone

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../экономика/банк_времени/код'))
from price_calculator import (
    BeepleAnchor,
    mta_to_usd,
    usd_to_mta,
    seconds_to_usd,
    usd_to_seconds,
    days_to_usd,
    usd_to_days,
    get_anchor_info,
    format_price,
    PizzaDayCalculator
)


class TestBeepleAnchorConstants(unittest.TestCase):
    """Тесты констант якоря Beeple"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         BEEPLE ANCHOR CONSTANTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_sale_price(self):
        """Цена продажи Beeple NFT"""
        self.assertEqual(BeepleAnchor.SALE_PRICE_USD, 69_346_250.00)

    def test_total_days(self):
        """Количество дней работы"""
        self.assertEqual(BeepleAnchor.TOTAL_DAYS, 5000)

    def test_sale_date(self):
        """Дата продажи"""
        self.assertEqual(BeepleAnchor.SALE_DATE, "2021-03-11")

    def test_usd_per_day(self):
        """USD за день работы"""
        expected = BeepleAnchor.SALE_PRICE_USD / BeepleAnchor.TOTAL_DAYS
        self.assertAlmostEqual(BeepleAnchor.USD_PER_DAY, expected, places=2)
        self.assertAlmostEqual(BeepleAnchor.USD_PER_DAY, 13869.25, places=2)

    def test_usd_per_hour(self):
        """USD за час работы"""
        expected = BeepleAnchor.USD_PER_DAY / 24
        self.assertAlmostEqual(BeepleAnchor.USD_PER_HOUR, expected, places=2)
        self.assertAlmostEqual(BeepleAnchor.USD_PER_HOUR, 577.885, places=2)

    def test_usd_per_minute(self):
        """USD за минуту работы"""
        expected = BeepleAnchor.USD_PER_HOUR / 60
        self.assertAlmostEqual(BeepleAnchor.USD_PER_MINUTE, expected, places=2)
        self.assertAlmostEqual(BeepleAnchor.USD_PER_MINUTE, 9.6314, places=2)

    def test_usd_per_second(self):
        """USD за секунду работы"""
        expected = BeepleAnchor.USD_PER_MINUTE / 60
        self.assertAlmostEqual(BeepleAnchor.USD_PER_SECOND, expected, places=4)
        self.assertAlmostEqual(BeepleAnchor.USD_PER_SECOND, 0.1605, places=4)

    def test_mta_per_second(self):
        """MTA за секунду"""
        self.assertEqual(BeepleAnchor.MTA_PER_SECOND, 1.0)

    def test_usd_per_mta(self):
        """USD за 1 MTA"""
        self.assertEqual(BeepleAnchor.USD_PER_MTA, BeepleAnchor.USD_PER_SECOND)


class TestMTAtoUSD(unittest.TestCase):
    """Тесты конвертации MTA → USD"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         MTA TO USD
    # ═══════════════════════════════════════════════════════════════════════

    def test_mta_to_usd_one_second(self):
        """1 MTA (1 секунда) → USD"""
        result = mta_to_usd(1.0)
        self.assertAlmostEqual(result, 0.1605, places=4)

    def test_mta_to_usd_ten_minutes(self):
        """600 MTA (10 минут) → USD"""
        result = mta_to_usd(600)
        expected = 600 * BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)
        self.assertAlmostEqual(result, 96.3, places=1)

    def test_mta_to_usd_one_hour(self):
        """3600 MTA (1 час) → USD"""
        result = mta_to_usd(3600)
        expected = 3600 * BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)
        self.assertAlmostEqual(result, 577.8, places=1)

    def test_mta_to_usd_one_day(self):
        """86400 MTA (1 день) → USD"""
        result = mta_to_usd(86400)
        expected = 86400 * BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)
        self.assertAlmostEqual(result, 13869.2, places=1)

    def test_mta_to_usd_zero(self):
        """0 MTA → $0"""
        result = mta_to_usd(0)
        self.assertEqual(result, 0.0)

    def test_mta_to_usd_large_number(self):
        """1,000,000 MTA → USD"""
        result = mta_to_usd(1_000_000)
        expected = 1_000_000 * BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)


class TestUSDtoMTA(unittest.TestCase):
    """Тесты конвертации USD → MTA"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         USD TO MTA
    # ═══════════════════════════════════════════════════════════════════════

    def test_usd_to_mta_one_second_price(self):
        """$0.1605 → 1 MTA"""
        result = usd_to_mta(0.1605)
        self.assertAlmostEqual(result, 1.0, places=2)

    def test_usd_to_mta_one_hundred(self):
        """$100 → MTA"""
        result = usd_to_mta(100)
        expected = 100 / BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)
        self.assertAlmostEqual(result, 623.0, places=0)

    def test_usd_to_mta_zero(self):
        """$0 → 0 MTA"""
        result = usd_to_mta(0)
        self.assertEqual(result, 0.0)

    def test_usd_to_mta_roundtrip(self):
        """Roundtrip: MTA → USD → MTA"""
        original = 1000.0
        converted = mta_to_usd(original)
        back = usd_to_mta(converted)
        self.assertAlmostEqual(back, original, places=2)


class TestSecondsConversion(unittest.TestCase):
    """Тесты конвертации секунд"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         SECONDS CONVERSION
    # ═══════════════════════════════════════════════════════════════════════

    def test_seconds_to_usd_one(self):
        """1 секунда → USD"""
        result = seconds_to_usd(1)
        self.assertAlmostEqual(result, 0.1605, places=4)

    def test_seconds_to_usd_sixty(self):
        """60 секунд (1 минута) → USD"""
        result = seconds_to_usd(60)
        expected = 60 * BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)

    def test_seconds_to_usd_ten_minutes(self):
        """600 секунд (10 минут) → USD"""
        result = seconds_to_usd(600)
        self.assertAlmostEqual(result, 96.3, places=1)

    def test_usd_to_seconds_one_second_price(self):
        """$0.1605 → 1 секунда"""
        result = usd_to_seconds(0.1605)
        self.assertAlmostEqual(result, 1.0, places=2)

    def test_usd_to_seconds_one_hundred(self):
        """$100 → секунды"""
        result = usd_to_seconds(100)
        expected = 100 / BeepleAnchor.USD_PER_SECOND
        self.assertAlmostEqual(result, expected, places=2)

    def test_seconds_roundtrip(self):
        """Roundtrip: секунды → USD → секунды"""
        original = 3600  # 1 час
        converted = seconds_to_usd(original)
        back = usd_to_seconds(converted)
        self.assertAlmostEqual(back, original, places=2)


class TestDaysConversion(unittest.TestCase):
    """Тесты конвертации дней"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         DAYS CONVERSION
    # ═══════════════════════════════════════════════════════════════════════

    def test_days_to_usd_one(self):
        """1 день → USD"""
        result = days_to_usd(1)
        self.assertAlmostEqual(result, BeepleAnchor.USD_PER_DAY, places=2)
        self.assertAlmostEqual(result, 13869.25, places=2)

    def test_days_to_usd_5000(self):
        """5000 дней → USD (полная работа Beeple)"""
        result = days_to_usd(5000)
        self.assertAlmostEqual(result, BeepleAnchor.SALE_PRICE_USD, places=2)

    def test_days_to_usd_fractional(self):
        """0.5 дня → USD"""
        result = days_to_usd(0.5)
        expected = BeepleAnchor.USD_PER_DAY * 0.5
        self.assertAlmostEqual(result, expected, places=2)

    def test_usd_to_days_one_day_price(self):
        """$13,869.25 → 1 день"""
        result = usd_to_days(13869.25)
        self.assertAlmostEqual(result, 1.0, places=2)

    def test_usd_to_days_full_sale(self):
        """$69.3M → 5000 дней"""
        result = usd_to_days(BeepleAnchor.SALE_PRICE_USD)
        self.assertAlmostEqual(result, 5000, places=2)

    def test_days_roundtrip(self):
        """Roundtrip: дни → USD → дни"""
        original = 365  # 1 год
        converted = days_to_usd(original)
        back = usd_to_days(converted)
        self.assertAlmostEqual(back, original, places=2)


class TestAnchorInfo(unittest.TestCase):
    """Тесты получения информации о якоре"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         ANCHOR INFO
    # ═══════════════════════════════════════════════════════════════════════

    def test_get_anchor_info_structure(self):
        """Структура информации о якоре"""
        info = get_anchor_info()

        self.assertIsInstance(info, dict)
        self.assertIn("sale_price_usd", info)
        self.assertIn("total_days", info)
        self.assertIn("sale_date", info)
        self.assertIn("usd_per_second", info)
        self.assertIn("usd_per_minute", info)
        self.assertIn("usd_per_hour", info)
        self.assertIn("usd_per_day", info)
        self.assertIn("mta_per_second", info)
        self.assertIn("usd_per_mta", info)

    def test_get_anchor_info_values(self):
        """Значения в информации о якоре"""
        info = get_anchor_info()

        self.assertEqual(info["sale_price_usd"], 69_346_250.00)
        self.assertEqual(info["total_days"], 5000)
        self.assertEqual(info["sale_date"], "2021-03-11")
        self.assertAlmostEqual(info["usd_per_second"], 0.1605, places=4)
        self.assertEqual(info["mta_per_second"], 1.0)


class TestFormatPrice(unittest.TestCase):
    """Тесты форматирования цены"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         FORMAT PRICE
    # ═══════════════════════════════════════════════════════════════════════

    def test_format_price_usd(self):
        """Форматирование в USD"""
        result = format_price(96.31, "USD")
        self.assertEqual(result, "$96.31 USD")

    def test_format_price_mta(self):
        """Форматирование в MTA"""
        usd_amount = 0.1605  # 1 MTA
        result = format_price(usd_amount, "MTA")
        self.assertIn("MTA", result)
        self.assertIn("1.00", result)

    def test_format_price_large_number(self):
        """Форматирование большого числа"""
        result = format_price(13869.25, "USD")
        self.assertEqual(result, "$13869.25 USD")

    def test_format_price_zero(self):
        """Форматирование нуля"""
        result = format_price(0.0, "USD")
        self.assertEqual(result, "$0.00 USD")


class TestPizzaDayCalculator(unittest.TestCase):
    """Тесты Pizza Day механизма"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         PIZZA DAY MECHANISM
    # ═══════════════════════════════════════════════════════════════════════

    def test_is_pizza_day_true(self):
        """22 мая — это Pizza Day"""
        pizza_day = datetime(2025, 5, 22, tzinfo=timezone.utc)
        result = PizzaDayCalculator.is_pizza_day(pizza_day)
        self.assertTrue(result)

    def test_is_pizza_day_false(self):
        """23 мая — НЕ Pizza Day"""
        not_pizza_day = datetime(2025, 5, 23, tzinfo=timezone.utc)
        result = PizzaDayCalculator.is_pizza_day(not_pizza_day)
        self.assertFalse(result)

    def test_is_pizza_day_different_year(self):
        """Pizza Day в другом году"""
        pizza_day_2030 = datetime(2030, 5, 22, tzinfo=timezone.utc)
        result = PizzaDayCalculator.is_pizza_day(pizza_day_2030)
        self.assertTrue(result)

    def test_days_until_pizza_day_before(self):
        """Дней до Pizza Day (до 22 мая)"""
        date = datetime(2025, 5, 1, tzinfo=timezone.utc)
        result = PizzaDayCalculator.days_until_pizza_day(date)
        self.assertEqual(result, 21)  # 22 - 1 = 21 день

    def test_days_until_pizza_day_after(self):
        """Дней до Pizza Day (после 22 мая)"""
        date = datetime(2025, 6, 1, tzinfo=timezone.utc)
        result = PizzaDayCalculator.days_until_pizza_day(date)

        # Должно быть ~355 дней до следующего 22 мая
        self.assertGreater(result, 300)
        self.assertLess(result, 366)

    def test_days_until_pizza_day_on_pizza_day(self):
        """Дней до Pizza Day в сам Pizza Day"""
        pizza_day = datetime(2025, 5, 22, tzinfo=timezone.utc)
        result = PizzaDayCalculator.days_until_pizza_day(pizza_day)

        # В сам Pizza Day — 0 дней до него (или 365 до следующего)
        # Зависит от времени суток
        self.assertIn(result, [0, 365])

    def test_recalculate_anchor(self):
        """Пересчёт якоря с новыми значениями"""
        new_price = 100_000_000  # $100M
        new_days = 10_000

        result = PizzaDayCalculator.recalculate_anchor(new_price, new_days)

        self.assertEqual(result["sale_price_usd"], new_price)
        self.assertEqual(result["total_days"], new_days)
        self.assertAlmostEqual(result["usd_per_day"], 10_000, places=2)
        self.assertAlmostEqual(result["usd_per_second"], 0.1157, places=4)

    def test_recalculate_anchor_doubles_price(self):
        """Пересчёт с удвоенной ценой"""
        original_price = BeepleAnchor.SALE_PRICE_USD
        doubled_price = original_price * 2

        result = PizzaDayCalculator.recalculate_anchor(doubled_price, BeepleAnchor.TOTAL_DAYS)

        # USD/секунда должен удвоиться
        expected_usd_per_sec = BeepleAnchor.USD_PER_SECOND * 2
        self.assertAlmostEqual(result["usd_per_second"], expected_usd_per_sec, places=4)


class TestConsistency(unittest.TestCase):
    """Тесты консистентности расчётов"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         CONSISTENCY
    # ═══════════════════════════════════════════════════════════════════════

    def test_seconds_equals_mta(self):
        """1 секунда = 1 MTA"""
        seconds_value = seconds_to_usd(1)
        mta_value = mta_to_usd(1)
        self.assertAlmostEqual(seconds_value, mta_value, places=4)

    def test_day_to_seconds_consistency(self):
        """86400 секунд = 1 день"""
        usd_from_seconds = seconds_to_usd(86400)
        usd_from_days = days_to_usd(1)
        self.assertAlmostEqual(usd_from_seconds, usd_from_days, places=2)

    def test_beeple_calculation_consistency(self):
        """$69.3M / 5000 дней / 86400 сек = $0.1605/сек"""
        calculated = BeepleAnchor.SALE_PRICE_USD / BeepleAnchor.TOTAL_DAYS / 86400
        self.assertAlmostEqual(calculated, BeepleAnchor.USD_PER_SECOND, places=4)

    def test_all_units_consistent(self):
        """Все единицы согласованы"""
        # 1 день = 24 часа = 1440 минут = 86400 секунд
        day_price = BeepleAnchor.USD_PER_DAY
        hour_price = BeepleAnchor.USD_PER_HOUR * 24
        minute_price = BeepleAnchor.USD_PER_MINUTE * 1440
        second_price = BeepleAnchor.USD_PER_SECOND * 86400

        self.assertAlmostEqual(day_price, hour_price, places=2)
        self.assertAlmostEqual(day_price, minute_price, places=2)
        self.assertAlmostEqual(day_price, second_price, places=2)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
