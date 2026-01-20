#!/usr/bin/env python3
"""
adaptive_cooldown.py
Montana Protocol — Adaptive Cooldown

Защита от Sybil-атак через адаптивный период ожидания.
Cooldown рассчитывается на основе медианы регистраций за τ₃ (14 дней).

Alejandro Montana
Montana Protocol v1.0
Январь 2026
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import statistics

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CooldownConstants:
    """Константы Adaptive Cooldown"""

    # Временные единицы (в τ₂ слайсах, 1 τ₂ = 10 минут)
    TAU2_DURATION_SEC: int = 10 * 60           # τ₂ = 10 минут = 600 сек
    TAU3_IN_TAU2: int = 2016                   # τ₃ = 14 дней = 2016 τ₂

    # Границы cooldown (в τ₂)
    COOLDOWN_MIN_TAU2: int = 144               # Минимум: 1 день = 144 τ₂
    COOLDOWN_MID_TAU2: int = 1008              # Медиана: 7 дней = 1008 τ₂
    COOLDOWN_MAX_TAU2: int = 25920             # Максимум: 180 дней = 25920 τ₂

    # Границы cooldown (в днях) для удобства
    COOLDOWN_MIN_DAYS: int = 1
    COOLDOWN_MID_DAYS: int = 7
    COOLDOWN_MAX_DAYS: int = 180

    # Сглаживание
    SMOOTH_WINDOWS: int = 4                    # 4 × τ₃ = 56 дней
    MAX_CHANGE_PERCENT: int = 20               # ±20% за τ₃

    # Genesis
    DEFAULT_COOLDOWN_TAU2: int = 144           # Genesis cooldown: 1 день


CONSTANTS = CooldownConstants()


# ═══════════════════════════════════════════════════════════════════════════════
#                              ADAPTIVE COOLDOWN
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RegistrationRecord:
    """Запись о регистрации узла"""
    tau2_index: int                            # Индекс τ₂ регистрации
    address: str                               # Адрес узла (mt...)
    tier: int = 1                              # Уровень узла (1-4)
    timestamp: float = field(default_factory=time.time)


class AdaptiveCooldown:
    """
    Adaptive Cooldown — динамическая защита от Sybil-атак

    Механизм:
    1. Считаем регистрации за последний τ₃ (14 дней)
    2. Вычисляем медиану за 4 τ₃ (56 дней) для сглаживания
    3. Cooldown = f(current_count / median)
    4. Rate limit: ±20% изменения за τ₃

    Формула:
        ratio = current_count / smoothed_median

        if ratio <= 1.0:
            cooldown = MIN + ratio × (MID - MIN)
        else:
            cooldown = MID + (ratio - 1.0) × (MAX - MID)

    Защита от атак:
        - Spike manipulation: 56-дневное сглаживание
        - Fast pump: ±20% rate limit
        - Sybil при низкой нагрузке: минимум 1 день
        - Sybil при спайке: до 180 дней
    """

    def __init__(self):
        # История регистраций по τ₃
        self._registrations: Dict[int, List[RegistrationRecord]] = {}

        # История медиан по τ₃ и tier
        self._median_history: Dict[Tuple[int, int], int] = {}

        # Текущий cooldown по tier
        self._current_cooldown: Dict[int, int] = {
            1: CONSTANTS.DEFAULT_COOLDOWN_TAU2,
            2: CONSTANTS.DEFAULT_COOLDOWN_TAU2,
            3: CONSTANTS.DEFAULT_COOLDOWN_TAU2,
            4: CONSTANTS.DEFAULT_COOLDOWN_TAU2,
        }

        # Счётчик τ₂
        self._current_tau2: int = 0

        logger.info("AdaptiveCooldown инициализирован")
        logger.info(f"  MIN: {CONSTANTS.COOLDOWN_MIN_DAYS} дней")
        logger.info(f"  MID: {CONSTANTS.COOLDOWN_MID_DAYS} дней")
        logger.info(f"  MAX: {CONSTANTS.COOLDOWN_MAX_DAYS} дней")

    def _tau3_index(self, tau2: int) -> int:
        """Получить индекс τ₃ для данного τ₂"""
        return tau2 // CONSTANTS.TAU3_IN_TAU2

    def register_node(self, address: str, tier: int = 1) -> int:
        """
        Зарегистрировать новый узел

        Args:
            address: Адрес узла (mt...)
            tier: Уровень узла (1-4)

        Returns:
            Cooldown в τ₂ (сколько τ₂ ждать до активации)
        """
        tau3_idx = self._tau3_index(self._current_tau2)

        # Создать запись
        record = RegistrationRecord(
            tau2_index=self._current_tau2,
            address=address,
            tier=tier
        )

        # Добавить в историю
        if tau3_idx not in self._registrations:
            self._registrations[tau3_idx] = []
        self._registrations[tau3_idx].append(record)

        # Получить текущий cooldown для tier
        cooldown = self._current_cooldown.get(tier, CONSTANTS.DEFAULT_COOLDOWN_TAU2)

        logger.info(f"Регистрация: {address[:20]}... tier={tier} cooldown={cooldown} τ₂")

        return cooldown

    def get_registrations_count(self, tau3_index: int, tier: int = None) -> int:
        """
        Количество регистраций за τ₃

        Args:
            tau3_index: Индекс τ₃
            tier: Фильтр по tier (None = все)

        Returns:
            Количество регистраций
        """
        records = self._registrations.get(tau3_index, [])
        if tier is None:
            return len(records)
        return sum(1 for r in records if r.tier == tier)

    def _compute_smoothed_median(self, current_tau3: int, tier: int) -> int:
        """
        Вычислить сглаженную медиану за 4 τ₃ (56 дней)

        Args:
            current_tau3: Текущий индекс τ₃
            tier: Уровень узла

        Returns:
            Сглаженная медиана регистраций
        """
        medians = []

        for i in range(CONSTANTS.SMOOTH_WINDOWS):
            tau3_idx = current_tau3 - i
            if tau3_idx < 0:
                continue

            # Получить сохранённую медиану или вычислить
            key = (tau3_idx, tier)
            if key in self._median_history:
                medians.append(self._median_history[key])
            else:
                count = self.get_registrations_count(tau3_idx, tier)
                if count > 0:
                    medians.append(count)

        if not medians:
            return 1  # Избежать деления на 0

        return max(1, int(statistics.mean(medians)))

    def _calculate_raw_cooldown(self, current_count: int, median: int) -> int:
        """
        Рассчитать cooldown по формуле

        Args:
            current_count: Текущее количество регистраций
            median: Сглаженная медиана

        Returns:
            Cooldown в τ₂
        """
        if median == 0:
            median = 1

        ratio = current_count / median

        if ratio <= 1.0:
            # MIN → MID (линейно)
            cooldown = CONSTANTS.COOLDOWN_MIN_TAU2 + ratio * (
                CONSTANTS.COOLDOWN_MID_TAU2 - CONSTANTS.COOLDOWN_MIN_TAU2
            )
        else:
            # MID → MAX (линейно)
            cooldown = CONSTANTS.COOLDOWN_MID_TAU2 + (ratio - 1.0) * (
                CONSTANTS.COOLDOWN_MAX_TAU2 - CONSTANTS.COOLDOWN_MID_TAU2
            )

        # Ограничить границами
        return int(max(CONSTANTS.COOLDOWN_MIN_TAU2,
                      min(CONSTANTS.COOLDOWN_MAX_TAU2, cooldown)))

    def _apply_rate_limit(self, raw_cooldown: int, previous_cooldown: int) -> int:
        """
        Применить rate limiting (±20% за τ₃)

        Args:
            raw_cooldown: Рассчитанный cooldown
            previous_cooldown: Предыдущий cooldown

        Returns:
            Cooldown с учётом rate limit
        """
        max_change = (previous_cooldown * CONSTANTS.MAX_CHANGE_PERCENT) // 100

        if raw_cooldown > previous_cooldown:
            return min(raw_cooldown, previous_cooldown + max_change)
        else:
            return max(raw_cooldown, previous_cooldown - max_change)

    def on_tau3_end(self, tau3_index: int):
        """
        Обработка завершения τ₃ — пересчёт cooldown

        Args:
            tau3_index: Индекс завершившегося τ₃
        """
        logger.info(f"═══ τ₃ #{tau3_index} завершён ═══")

        for tier in range(1, 5):
            # Текущее количество регистраций
            current_count = self.get_registrations_count(tau3_index, tier)

            # Сохранить медиану
            self._median_history[(tau3_index, tier)] = max(1, current_count)

            # Сглаженная медиана
            smoothed_median = self._compute_smoothed_median(tau3_index, tier)

            # Рассчитать cooldown
            raw_cooldown = self._calculate_raw_cooldown(current_count, smoothed_median)

            # Применить rate limit
            previous = self._current_cooldown.get(tier, CONSTANTS.DEFAULT_COOLDOWN_TAU2)
            new_cooldown = self._apply_rate_limit(raw_cooldown, previous)

            # Сохранить
            self._current_cooldown[tier] = new_cooldown

            logger.info(f"  Tier {tier}: count={current_count} median={smoothed_median} "
                       f"cooldown={new_cooldown} τ₂ ({new_cooldown // 144} дней)")

    def advance_tau2(self):
        """Продвинуть счётчик τ₂"""
        self._current_tau2 += 1

        # Проверить завершение τ₃
        if self._current_tau2 % CONSTANTS.TAU3_IN_TAU2 == 0:
            tau3_idx = self._tau3_index(self._current_tau2) - 1
            self.on_tau3_end(tau3_idx)

    def get_cooldown(self, tier: int = 1) -> int:
        """
        Получить текущий cooldown для tier

        Args:
            tier: Уровень узла (1-4)

        Returns:
            Cooldown в τ₂
        """
        return self._current_cooldown.get(tier, CONSTANTS.DEFAULT_COOLDOWN_TAU2)

    def get_cooldown_days(self, tier: int = 1) -> float:
        """
        Получить текущий cooldown в днях

        Args:
            tier: Уровень узла (1-4)

        Returns:
            Cooldown в днях
        """
        tau2 = self.get_cooldown(tier)
        return tau2 / 144  # 144 τ₂ = 1 день

    def is_in_cooldown(self, registration_tau2: int, tier: int = 1) -> bool:
        """
        Проверить, находится ли узел в cooldown

        Args:
            registration_tau2: τ₂ индекс регистрации
            tier: Уровень узла

        Returns:
            True если узел ещё в cooldown
        """
        cooldown = self.get_cooldown(tier)
        return (self._current_tau2 - registration_tau2) < cooldown

    def cooldown_remaining(self, registration_tau2: int, tier: int = 1) -> int:
        """
        Оставшийся cooldown в τ₂

        Args:
            registration_tau2: τ₂ индекс регистрации
            tier: Уровень узла

        Returns:
            Оставшиеся τ₂ (0 если cooldown завершён)
        """
        cooldown = self.get_cooldown(tier)
        elapsed = self._current_tau2 - registration_tau2
        return max(0, cooldown - elapsed)

    def get_stats(self) -> Dict:
        """Статистика Adaptive Cooldown"""
        current_tau3 = self._tau3_index(self._current_tau2)

        return {
            "current_tau2": self._current_tau2,
            "current_tau3": current_tau3,
            "cooldowns": {
                f"tier_{t}": {
                    "tau2": self._current_cooldown[t],
                    "days": round(self._current_cooldown[t] / 144, 2)
                }
                for t in range(1, 5)
            },
            "registrations_current_tau3": self.get_registrations_count(current_tau3),
            "constants": {
                "min_days": CONSTANTS.COOLDOWN_MIN_DAYS,
                "mid_days": CONSTANTS.COOLDOWN_MID_DAYS,
                "max_days": CONSTANTS.COOLDOWN_MAX_DAYS,
                "smooth_windows": CONSTANTS.SMOOTH_WINDOWS,
                "rate_limit_percent": CONSTANTS.MAX_CHANGE_PERCENT
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                              SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_adaptive_cooldown: Optional[AdaptiveCooldown] = None


def get_adaptive_cooldown() -> AdaptiveCooldown:
    """Получить singleton экземпляр AdaptiveCooldown"""
    global _adaptive_cooldown
    if _adaptive_cooldown is None:
        _adaptive_cooldown = AdaptiveCooldown()
    return _adaptive_cooldown


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("═" * 60)
    print("  Montana Adaptive Cooldown")
    print("═" * 60)

    cooldown = get_adaptive_cooldown()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "stats":
            stats = cooldown.get_stats()
            print(f"\nТекущий τ₂: {stats['current_tau2']}")
            print(f"Текущий τ₃: {stats['current_tau3']}")
            print(f"\nCooldowns:")
            for tier, data in stats['cooldowns'].items():
                print(f"  {tier}: {data['days']} дней ({data['tau2']} τ₂)")

        elif cmd == "register":
            address = sys.argv[2] if len(sys.argv) > 2 else "mt_test_address"
            tier = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            cd = cooldown.register_node(address, tier)
            print(f"\nЗарегистрирован: {address}")
            print(f"Tier: {tier}")
            print(f"Cooldown: {cd} τ₂ ({cd // 144} дней)")

        elif cmd == "simulate":
            # Симуляция нагрузки
            print("\nСимуляция: 100 регистраций за τ₃...")
            for i in range(100):
                cooldown.register_node(f"mt_sim_{i:04d}", tier=1)

            print("Завершение τ₃...")
            cooldown._current_tau2 = CONSTANTS.TAU3_IN_TAU2
            cooldown.on_tau3_end(0)

            stats = cooldown.get_stats()
            print(f"\nНовый cooldown tier_1: {stats['cooldowns']['tier_1']['days']} дней")

        elif cmd == "test":
            print("\n[TEST] Тестирование формулы cooldown...")

            # Тест 1: ratio = 0.5 (ниже медианы)
            raw = cooldown._calculate_raw_cooldown(50, 100)
            days = raw / 144
            print(f"  ratio=0.5: {days:.1f} дней (ожидается ~4 дня)")

            # Тест 2: ratio = 1.0 (на медиане)
            raw = cooldown._calculate_raw_cooldown(100, 100)
            days = raw / 144
            print(f"  ratio=1.0: {days:.1f} дней (ожидается 7 дней)")

            # Тест 3: ratio = 2.0 (выше медианы)
            raw = cooldown._calculate_raw_cooldown(200, 100)
            days = raw / 144
            print(f"  ratio=2.0: {days:.1f} дней (ожидается ~94 дня)")

            # Тест 4: rate limit
            limited = cooldown._apply_rate_limit(1000, 144)
            print(f"\n[TEST] Rate limit: 1000 → {limited} (max +20% от 144)")

            print("\n✅ Тесты завершены")

        else:
            print(f"Неизвестная команда: {cmd}")

    else:
        print("""
Использование:
  python adaptive_cooldown.py stats     — статистика
  python adaptive_cooldown.py register <addr> [tier]  — регистрация
  python adaptive_cooldown.py simulate  — симуляция нагрузки
  python adaptive_cooldown.py test      — тесты формулы

Константы:
  MIN:     1 день (144 τ₂)
  MID:     7 дней (1008 τ₂)
  MAX:     180 дней (25920 τ₂)
  Smooth:  4 × τ₃ (56 дней)
  Rate:    ±20% за τ₃
        """)
