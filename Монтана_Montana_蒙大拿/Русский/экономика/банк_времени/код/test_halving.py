#!/usr/bin/env python3
"""
test_halving.py — Unit tests для halving.py

Montana Protocol
Тестирование механизма халвинга эмиссии
"""

import unittest
from halving import halving_coefficient


class TestHalving(unittest.TestCase):
    """Тесты для механизма халвинга Montana"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         BASIC HALVING
    # ═══════════════════════════════════════════════════════════════════════

    def test_halving_tau4_0(self):
        """τ₄ = 0: коэффициент 1.0 (первые 4 года)"""
        self.assertEqual(halving_coefficient(0), 1.0)

    def test_halving_tau4_1(self):
        """τ₄ = 1: коэффициент 0.5 (4-8 лет)"""
        self.assertEqual(halving_coefficient(1), 0.5)

    def test_halving_tau4_2(self):
        """τ₄ = 2: коэффициент 0.25 (8-12 лет)"""
        self.assertEqual(halving_coefficient(2), 0.25)

    def test_halving_tau4_3(self):
        """τ₄ = 3: коэффициент 0.125 (12-16 лет)"""
        self.assertEqual(halving_coefficient(3), 0.125)

    def test_halving_tau4_4(self):
        """τ₄ = 4: коэффициент 0.0625 (16-20 лет)"""
        self.assertEqual(halving_coefficient(4), 0.0625)

    # ═══════════════════════════════════════════════════════════════════════
    #                         EXTENDED TIMELINE
    # ═══════════════════════════════════════════════════════════════════════

    def test_halving_tau4_10(self):
        """τ₄ = 10: коэффициент ~0.0009765625 (40-44 года)"""
        expected = 1.0 / (2 ** 10)
        self.assertEqual(halving_coefficient(10), expected)
        self.assertAlmostEqual(halving_coefficient(10), 0.0009765625, places=10)

    def test_halving_tau4_20(self):
        """τ₄ = 20: очень малый коэффициент (80-84 года)"""
        expected = 1.0 / (2 ** 20)
        self.assertEqual(halving_coefficient(20), expected)
        self.assertAlmostEqual(halving_coefficient(20), 9.5367431640625e-07, places=15)

    def test_halving_tau4_50(self):
        """τ₄ = 50: экстремально малый коэффициент (200-204 года)"""
        expected = 1.0 / (2 ** 50)
        self.assertEqual(halving_coefficient(50), expected)

    # ═══════════════════════════════════════════════════════════════════════
    #                         EMISSION CALCULATION
    # ═══════════════════════════════════════════════════════════════════════

    def test_emission_calculation_tau4_0(self):
        """Эмиссия для 100 участников, 600 сек каждый, τ₄ = 0"""
        participants = 100
        seconds_per_participant = 600
        total_seconds = participants * seconds_per_participant

        coef = halving_coefficient(0)
        emission = total_seconds * coef

        self.assertEqual(emission, 60_000)  # 100 × 600 × 1.0

    def test_emission_calculation_tau4_1(self):
        """Эмиссия для 100 участников, 600 сек каждый, τ₄ = 1"""
        participants = 100
        seconds_per_participant = 600
        total_seconds = participants * seconds_per_participant

        coef = halving_coefficient(1)
        emission = total_seconds * coef

        self.assertEqual(emission, 30_000)  # 100 × 600 × 0.5

    def test_emission_calculation_tau4_2(self):
        """Эмиссия для 100 участников, 600 сек каждый, τ₄ = 2"""
        participants = 100
        seconds_per_participant = 600
        total_seconds = participants * seconds_per_participant

        coef = halving_coefficient(2)
        emission = total_seconds * coef

        self.assertEqual(emission, 15_000)  # 100 × 600 × 0.25

    # ═══════════════════════════════════════════════════════════════════════
    #                         COMPARISON WITH BITCOIN
    # ═══════════════════════════════════════════════════════════════════════

    def test_bitcoin_like_progression(self):
        """Проверка что прогрессия халвинга как у Bitcoin"""
        # Bitcoin: 50 → 25 → 12.5 → 6.25 → 3.125
        # Montana: 1.0 → 0.5 → 0.25 → 0.125 → 0.0625

        btc_rewards = [50, 25, 12.5, 6.25, 3.125]
        montana_coefs = [halving_coefficient(i) for i in range(5)]

        # Нормализуем Bitcoin к Montana (делим на 50)
        btc_normalized = [r / 50 for r in btc_rewards]

        for btc_norm, montana in zip(btc_normalized, montana_coefs):
            self.assertAlmostEqual(btc_norm, montana, places=10)

    # ═══════════════════════════════════════════════════════════════════════
    #                         PROPERTIES
    # ═══════════════════════════════════════════════════════════════════════

    def test_halving_monotonic_decrease(self):
        """Коэффициент монотонно убывает"""
        coefficients = [halving_coefficient(i) for i in range(10)]

        for i in range(len(coefficients) - 1):
            self.assertGreater(coefficients[i], coefficients[i + 1])

    def test_halving_never_zero(self):
        """Коэффициент никогда не равен нулю"""
        for tau4 in range(100):
            coef = halving_coefficient(tau4)
            self.assertGreater(coef, 0)

    def test_halving_never_negative(self):
        """Коэффициент никогда не отрицательный"""
        for tau4 in range(100):
            coef = halving_coefficient(tau4)
            self.assertGreaterEqual(coef, 0)

    def test_halving_approaches_zero(self):
        """Коэффициент стремится к нулю при больших τ₄"""
        coef_100 = halving_coefficient(100)
        self.assertLess(coef_100, 1e-30)  # Очень близко к нулю

    def test_halving_exact_division_by_two(self):
        """Каждый следующий коэффициент ровно в 2 раза меньше"""
        for tau4 in range(10):
            coef_current = halving_coefficient(tau4)
            coef_next = halving_coefficient(tau4 + 1)

            self.assertAlmostEqual(coef_current / 2, coef_next, places=15)

    # ═══════════════════════════════════════════════════════════════════════
    #                         PRACTICAL SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════

    def test_single_user_emission(self):
        """Один пользователь, 600 секунд присутствия"""
        seconds = 600

        # τ₄ = 0
        emission_0 = seconds * halving_coefficient(0)
        self.assertEqual(emission_0, 600)

        # τ₄ = 1
        emission_1 = seconds * halving_coefficient(1)
        self.assertEqual(emission_1, 300)

        # τ₄ = 2
        emission_2 = seconds * halving_coefficient(2)
        self.assertEqual(emission_2, 150)

    def test_ten_users_emission(self):
        """10 пользователей, 600 секунд каждый"""
        total_seconds = 10 * 600  # 6000

        # τ₄ = 0
        emission_0 = total_seconds * halving_coefficient(0)
        self.assertEqual(emission_0, 6_000)

        # τ₄ = 1
        emission_1 = total_seconds * halving_coefficient(1)
        self.assertEqual(emission_1, 3_000)

    def test_thousand_users_emission(self):
        """1000 пользователей, 600 секунд каждый"""
        total_seconds = 1000 * 600  # 600,000

        # τ₄ = 0
        emission_0 = total_seconds * halving_coefficient(0)
        self.assertEqual(emission_0, 600_000)

        # τ₄ = 1
        emission_1 = total_seconds * halving_coefficient(1)
        self.assertEqual(emission_1, 300_000)

    # ═══════════════════════════════════════════════════════════════════════
    #                         EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════

    def test_halving_float_precision(self):
        """Проверка точности float для больших tau4"""
        # Для очень больших tau4 может возникнуть underflow
        coef_1000 = halving_coefficient(1000)

        # Должно быть очень близко к нулю, но не точно ноль из-за float precision
        self.assertGreaterEqual(coef_1000, 0)

        # Может быть 0.0 из-за underflow — это ожидаемо для tau4 > ~1000
        if coef_1000 > 0:
            self.assertLess(coef_1000, 1e-300)

    def test_halving_formula_consistency(self):
        """Проверка что формула 1/(2^n) работает корректно"""
        for tau4 in range(20):
            coef = halving_coefficient(tau4)
            expected = 1.0 / (2 ** tau4)

            self.assertEqual(coef, expected)

    # ═══════════════════════════════════════════════════════════════════════
    #                         FUTURE PROJECTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def test_100_years_projection(self):
        """Проекция на 100 лет (25 халвингов)"""
        # 100 лет ÷ 4 года = 25 халвингов
        tau4_100_years = 25
        coef = halving_coefficient(tau4_100_years)

        expected = 1.0 / (2 ** 25)
        self.assertEqual(coef, expected)
        self.assertAlmostEqual(coef, 2.9802322387695312e-08, places=15)

    def test_200_years_projection(self):
        """Проекция на 200 лет (50 халвингов)"""
        tau4_200_years = 50
        coef = halving_coefficient(tau4_200_years)

        expected = 1.0 / (2 ** 50)
        self.assertEqual(coef, expected)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
