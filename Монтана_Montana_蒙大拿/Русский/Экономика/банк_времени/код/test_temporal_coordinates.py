#!/usr/bin/env python3
"""
test_temporal_coordinates.py — Unit tests для temporal_coordinates.py

Montana Protocol
Тестирование конвертеров временных координат
"""

import unittest
from temporal_coordinates import (
    t2_to_tau3,
    tau3_to_year,
    tau3_to_tau4,
    t2_to_tau4,
    is_tau3_checkpoint,
    is_tau4_epoch,
    t2_remaining_to_tau3
)


class TestTemporalCoordinates(unittest.TestCase):
    """Тесты для временных координат Montana"""

    # ═══════════════════════════════════════════════════════════════════════
    #                         T2 TO TAU3 CONVERSION
    # ═══════════════════════════════════════════════════════════════════════

    def test_t2_to_tau3_genesis(self):
        """T2 #0 → τ₃ #0"""
        self.assertEqual(t2_to_tau3(0), 0)

    def test_t2_to_tau3_first_checkpoint(self):
        """T2 #2016 → τ₃ #1"""
        self.assertEqual(t2_to_tau3(2016), 1)

    def test_t2_to_tau3_second_checkpoint(self):
        """T2 #4032 → τ₃ #2"""
        self.assertEqual(t2_to_tau3(4032), 2)

    def test_t2_to_tau3_before_checkpoint(self):
        """T2 #2015 → τ₃ #0 (ещё не достигли первого чекпоинта)"""
        self.assertEqual(t2_to_tau3(2015), 0)

    def test_t2_to_tau3_after_checkpoint(self):
        """T2 #2017 → τ₃ #1 (первый чекпоинт пройден)"""
        self.assertEqual(t2_to_tau3(2017), 1)

    def test_t2_to_tau3_one_year(self):
        """T2 #52416 → τ₃ #26 (1 год)"""
        self.assertEqual(t2_to_tau3(52416), 26)

    # ═══════════════════════════════════════════════════════════════════════
    #                         TAU3 TO YEAR CONVERSION
    # ═══════════════════════════════════════════════════════════════════════

    def test_tau3_to_year_genesis(self):
        """τ₃ #0 → год 0"""
        self.assertEqual(tau3_to_year(0), 0)

    def test_tau3_to_year_first_year(self):
        """τ₃ #26 → год 1"""
        self.assertEqual(tau3_to_year(26), 1)

    def test_tau3_to_year_second_year(self):
        """τ₃ #52 → год 2"""
        self.assertEqual(tau3_to_year(52), 2)

    def test_tau3_to_year_before_first_year(self):
        """τ₃ #25 → год 0 (ещё не прошёл год)"""
        self.assertEqual(tau3_to_year(25), 0)

    # ═══════════════════════════════════════════════════════════════════════
    #                         TAU3 TO TAU4 CONVERSION
    # ═══════════════════════════════════════════════════════════════════════

    def test_tau3_to_tau4_genesis(self):
        """τ₃ #0 → τ₄ #0"""
        self.assertEqual(tau3_to_tau4(0), 0)

    def test_tau3_to_tau4_first_epoch(self):
        """τ₃ #104 → τ₄ #1 (первый халвинг)"""
        self.assertEqual(tau3_to_tau4(104), 1)

    def test_tau3_to_tau4_second_epoch(self):
        """τ₃ #208 → τ₄ #2 (второй халвинг)"""
        self.assertEqual(tau3_to_tau4(208), 2)

    def test_tau3_to_tau4_before_first_epoch(self):
        """τ₃ #103 → τ₄ #0 (ещё не достигли первого халвинга)"""
        self.assertEqual(tau3_to_tau4(103), 0)

    # ═══════════════════════════════════════════════════════════════════════
    #                         T2 TO TAU4 CONVERSION
    # ═══════════════════════════════════════════════════════════════════════

    def test_t2_to_tau4_genesis(self):
        """T2 #0 → τ₄ #0"""
        self.assertEqual(t2_to_tau4(0), 0)

    def test_t2_to_tau4_first_epoch(self):
        """T2 #209664 → τ₄ #1 (104 × 2016 = 209664)"""
        self.assertEqual(t2_to_tau4(209664), 1)

    def test_t2_to_tau4_second_epoch(self):
        """T2 #419328 → τ₄ #2"""
        self.assertEqual(t2_to_tau4(419328), 2)

    # ═══════════════════════════════════════════════════════════════════════
    #                         TAU3 CHECKPOINT CHECKS
    # ═══════════════════════════════════════════════════════════════════════

    def test_is_tau3_checkpoint_true(self):
        """T2 #2016 — это τ₃ checkpoint"""
        self.assertTrue(is_tau3_checkpoint(2016))

    def test_is_tau3_checkpoint_genesis(self):
        """T2 #0 — это τ₃ checkpoint (genesis)"""
        self.assertTrue(is_tau3_checkpoint(0))

    def test_is_tau3_checkpoint_false(self):
        """T2 #2015 — НЕ τ₃ checkpoint"""
        self.assertFalse(is_tau3_checkpoint(2015))

    def test_is_tau3_checkpoint_multiple(self):
        """Проверяем несколько чекпоинтов"""
        self.assertTrue(is_tau3_checkpoint(4032))
        self.assertTrue(is_tau3_checkpoint(6048))
        self.assertFalse(is_tau3_checkpoint(4033))

    # ═══════════════════════════════════════════════════════════════════════
    #                         TAU4 EPOCH CHECKS
    # ═══════════════════════════════════════════════════════════════════════

    def test_is_tau4_epoch_true(self):
        """τ₃ #104 — это τ₄ epoch (халвинг)"""
        self.assertTrue(is_tau4_epoch(104))

    def test_is_tau4_epoch_genesis(self):
        """τ₃ #0 — это τ₄ epoch (genesis)"""
        self.assertTrue(is_tau4_epoch(0))

    def test_is_tau4_epoch_false(self):
        """τ₃ #103 — НЕ τ₄ epoch"""
        self.assertFalse(is_tau4_epoch(103))

    def test_is_tau4_epoch_multiple(self):
        """Проверяем несколько эпох"""
        self.assertTrue(is_tau4_epoch(208))
        self.assertTrue(is_tau4_epoch(312))
        self.assertFalse(is_tau4_epoch(105))

    # ═══════════════════════════════════════════════════════════════════════
    #                         T2 REMAINING TO TAU3
    # ═══════════════════════════════════════════════════════════════════════

    def test_t2_remaining_from_genesis(self):
        """От T2 #0 до первого τ₃ осталось 2016 слайсов"""
        self.assertEqual(t2_remaining_to_tau3(0), 2016)

    def test_t2_remaining_almost_checkpoint(self):
        """От T2 #2000 до первого τ₃ осталось 16 слайсов"""
        self.assertEqual(t2_remaining_to_tau3(2000), 16)

    def test_t2_remaining_at_checkpoint(self):
        """От T2 #2016 (чекпоинт) до следующего τ₃ осталось 2016 слайсов"""
        self.assertEqual(t2_remaining_to_tau3(2016), 2016)

    def test_t2_remaining_after_checkpoint(self):
        """От T2 #2017 до следующего τ₃ осталось 2015 слайсов"""
        self.assertEqual(t2_remaining_to_tau3(2017), 2015)

    def test_t2_remaining_one_left(self):
        """От T2 #4031 до следующего τ₃ остался 1 слайс"""
        self.assertEqual(t2_remaining_to_tau3(4031), 1)

    # ═══════════════════════════════════════════════════════════════════════
    #                         EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════

    def test_large_numbers(self):
        """Тест с большими числами (100 лет)"""
        # 100 лет = 100 × 26 = 2600 τ₃
        tau3_100_years = 2600
        year = tau3_to_year(tau3_100_years)
        self.assertEqual(year, 100)

        # 2600 τ₃ = 2600 × 2016 = 5,241,600 τ₂
        t2_100_years = 5_241_600
        tau3 = t2_to_tau3(t2_100_years)
        self.assertEqual(tau3, 2600)

    def test_consistency_round_trip(self):
        """Тест консистентности: T2 → τ₃ → year"""
        # 1 год = 26 τ₃ = 52,416 τ₂
        t2 = 52416
        tau3 = t2_to_tau3(t2)
        year = tau3_to_year(tau3)

        self.assertEqual(tau3, 26)
        self.assertEqual(year, 1)

    def test_tau4_calculation_consistency(self):
        """Проверка что t2_to_tau4 работает корректно через τ₃"""
        # 1 τ₄ = 104 τ₃ = 209,664 τ₂
        t2 = 209664
        tau4_direct = t2_to_tau4(t2)

        # Через τ₃
        tau3 = t2_to_tau3(t2)
        tau4_via_tau3 = tau3_to_tau4(tau3)

        self.assertEqual(tau4_direct, 1)
        self.assertEqual(tau4_via_tau3, 1)
        self.assertEqual(tau4_direct, tau4_via_tau3)


# ═══════════════════════════════════════════════════════════════════════════
#                              RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Запускаем с verbose output
    unittest.main(verbosity=2)
