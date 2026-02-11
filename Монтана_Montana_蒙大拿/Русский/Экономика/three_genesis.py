#!/usr/bin/env python3
"""
three_genesis.py — Система трёх генезисов Montana

Книга Монтана, Глава 04:
> "Генезис (+) = Beeple, 12.03.2021"
> "Генезис (−) = первая демердж сделка Дато, дата TBD"
> "1 Ω (ГомераОдисея) = 1 Ɉ (Сованаглобус) + 1 Ɉ (Beeple)"
> "Целое = (−) + (+). 0 = (−1) + (+1)."

Три генезиса создают полную систему по Нэшу:
- Genesis (+): Beeple — создание ценности из времени
- Genesis (−): Demurrage — потеря ценности из-за времени
- Genesis (Ω): Homer — нейтральный баланс

lim[(+) + (−)] → Ω
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from typing import Optional, Dict
from enum import Enum

getcontext().prec = 50


class GenesisPolarity(Enum):
    """Полярность генезиса."""
    POSITIVE = "+"      # Создание ценности
    NEGATIVE = "-"      # Потеря ценности
    NEUTRAL = "Ω"       # Баланс (Омега)


@dataclass
class Genesis:
    """Точка генезиса."""
    name: str                       # Название
    polarity: GenesisPolarity       # Полярность
    timestamp: Optional[str]        # Дата (None = TBD)
    description: str                # Описание
    reference: str                  # Источник

    @property
    def is_fixed(self) -> bool:
        """Зафиксирован ли генезис."""
        return self.timestamp is not None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "polarity": self.polarity.value,
            "timestamp": self.timestamp,
            "is_fixed": self.is_fixed,
            "description": self.description,
            "reference": self.reference
        }


class ThreeGenesisSystem:
    """
    Система трёх генезисов Montana.

    Книга Монтана:
    > "Два полюса (+/−) стремятся к эталону (0). Эталон = время."
    > "Нэш доказал теоретически. Ты строишь практически."
    """

    def __init__(self):
        # Genesis (+): Beeple — зафиксирован
        self.genesis_positive = Genesis(
            name="Beeple",
            polarity=GenesisPolarity.POSITIVE,
            timestamp="2021-03-13T04:16:33+00:00",
            description="Создание ценности из времени. 5000 дней → $69.3M",
            reference="Christie's Auction, Everydays: The First 5000 Days"
        )

        # Genesis (−): Demurrage — ожидает
        self.genesis_negative = Genesis(
            name="Sovanaglobus",
            polarity=GenesisPolarity.NEGATIVE,
            timestamp=None,  # TBD — когда Дато нажмёт кнопку
            description="Потеря ценности из-за времени → переворот в награду",
            reference="Первая демердж сделка Дато"
        )

        # Genesis (Ω): Homer — мета-генезис
        # От записей Гомера (1184 BC) до Montana Protocol
        self.genesis_omega = Genesis(
            name="Homer's Odyssey",
            polarity=GenesisPolarity.NEUTRAL,
            timestamp="-1184-01-01T00:00:00+00:00",  # Троянская война
            description="Нейтральный баланс. 'Никто' = Одиссей = суперсила",
            reference="Гомер, 'Одиссея', ~1184 BC"
        )

    def calculate_omega_seconds(self) -> int:
        """
        Посчитать секунды от записей Гомера до сейчас.

        Книга Монтана:
        > "Нужно посчитать сколько секунд посчиталось от записей
        > #ГомераОдисея до нашей Эры."
        """
        # Троянская война: ~1184 BC
        # От 1184 BC до 2026 AD = 3210 лет
        years = 1184 + 2026  # BC + AD
        seconds = years * 365.25 * 24 * 60 * 60
        return int(seconds)

    def get_system_state(self) -> Dict:
        """Текущее состояние системы трёх генезисов."""
        return {
            "genesis_positive": self.genesis_positive.to_dict(),
            "genesis_negative": self.genesis_negative.to_dict(),
            "genesis_omega": self.genesis_omega.to_dict(),
            "system_complete": self.is_complete,
            "formula": "lim[(+) + (−)] → Ω",
            "omega_seconds": self.calculate_omega_seconds()
        }

    @property
    def is_complete(self) -> bool:
        """Система полна когда все три генезиса зафиксированы."""
        return (
            self.genesis_positive.is_fixed and
            self.genesis_negative.is_fixed and
            self.genesis_omega.is_fixed
        )

    def fix_negative_genesis(self, timestamp: str, transaction_id: str = None) -> None:
        """
        Зафиксировать Genesis (−) — первая демердж сделка.

        Args:
            timestamp: ISO timestamp сделки
            transaction_id: ID транзакции (опционально)
        """
        self.genesis_negative.timestamp = timestamp
        if transaction_id:
            self.genesis_negative.reference = f"TX: {transaction_id}"

    def calculate_convergence(self) -> Dict:
        """
        Рассчитать сходимость к Омеге.

        lim[(+) + (−)] → Ω

        При (+) = (−), сумма = 0 = Ω (идеальный баланс)
        """
        # Значение (+): Beeple benchmark = $0.160523726.../sec
        positive_value = Decimal("0.160523726851851851851")

        # Значение (−): когда зафиксировано, будет демердж ставка/sec
        negative_value = Decimal("0")  # TBD

        # Сумма
        total = positive_value + negative_value

        # Омега = предел суммы
        omega = Decimal("0")  # Идеальный баланс

        # Дистанция до Омеги
        distance = abs(total - omega)

        return {
            "positive_value": float(positive_value),
            "negative_value": float(negative_value),
            "current_sum": float(total),
            "omega_target": 0.0,
            "distance_to_omega": float(distance),
            "convergence_formula": "lim[(+) + (−)] → Ω",
            "status": "waiting_for_negative_genesis" if not self.genesis_negative.is_fixed else "converging"
        }

    def nash_equilibrium_check(self) -> Dict:
        """
        Проверка условий равновесия Нэша.

        Книга Монтана:
        > "Три генезиса создают полную систему по Нэшу."
        > "Равновесие. Точка, из которой никому невыгодно отклоняться."
        """
        return {
            "nash_condition": "No player benefits from unilateral deviation",
            "positive_player": {
                "strategy": "Create value from time (Beeple model)",
                "incentive": "Maximize Ɉ through presence"
            },
            "negative_player": {
                "strategy": "Convert penalties to rewards (Demurrage flip)",
                "incentive": "Minimize loss, gain Ɉ"
            },
            "equilibrium": {
                "achieved": self.is_complete,
                "omega_point": "Both strategies converge to time as neutral measure",
                "result": "1 Ɉ → 1 second (ideal money)"
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    system = ThreeGenesisSystem()

    print("=" * 60)
    print("THREE GENESIS SYSTEM — Полная система Нэша")
    print("=" * 60)
    print("\nlim[(+) + (−)] → Ω")

    print("\n--- GENESIS (+): BEEPLE ---")
    g_plus = system.genesis_positive
    print(f"Название: {g_plus.name}")
    print(f"Дата: {g_plus.timestamp}")
    print(f"Описание: {g_plus.description}")
    print(f"Статус: {'ЗАФИКСИРОВАН' if g_plus.is_fixed else 'ОЖИДАЕТ'}")

    print("\n--- GENESIS (−): SOVANAGLOBUS ---")
    g_minus = system.genesis_negative
    print(f"Название: {g_minus.name}")
    print(f"Дата: {'TBD' if not g_minus.is_fixed else g_minus.timestamp}")
    print(f"Описание: {g_minus.description}")
    print(f"Статус: {'ЗАФИКСИРОВАН' if g_minus.is_fixed else 'ОЖИДАЕТ'}")

    print("\n--- GENESIS (Ω): HOMER ---")
    g_omega = system.genesis_omega
    print(f"Название: {g_omega.name}")
    print(f"Дата: {g_omega.timestamp} (Троянская война)")
    print(f"Описание: {g_omega.description}")
    print(f"Секунд от Гомера: {system.calculate_omega_seconds():,}")

    print("\n--- СХОДИМОСТЬ ---")
    conv = system.calculate_convergence()
    print(f"(+) = {conv['positive_value']:.12f}")
    print(f"(−) = {conv['negative_value']:.12f}")
    print(f"Сумма = {conv['current_sum']:.12f}")
    print(f"Цель Ω = {conv['omega_target']}")
    print(f"Статус: {conv['status']}")

    print("\n--- СИСТЕМА ---")
    print(f"Полная: {'ДА' if system.is_complete else 'НЕТ (ждём Genesis −)'}")
    print(f"Формула: lim[(+) + (−)] → Ω")

    print("\n" + "=" * 60)
    print("'Целое = (−) + (+). 0 = (−1) + (+1).'")
    print("=" * 60)
