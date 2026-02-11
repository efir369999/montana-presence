#!/usr/bin/env python3
"""
temporal_value_scale.py — Шкала цены времени от Big Bang до сейчас

Книга Монтана, Глава 05:
> "Big Bang → #ГомераОдисея → #Ценность金 → #Бипл → Now"
> "Христос дал точку отсчёта для веры. Beeple дал точку отсчёта для цены времени."
> "BC = Before Beeple. AD = After Debut. День 1 = 12.03.2021 AD."

Шкала показывает как менялась "цена" секунды через историю:
- От бесконечно малой (Big Bang)
- К первым символическим значениям (Homer, 金)
- К Genesis (Beeple = $0.16/sec)
- К настоящему (цена растёт с evidence)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from typing import List, Dict, Optional

getcontext().prec = 50


@dataclass
class TimePoint:
    """Точка на шкале времени."""
    name: str                   # Название события
    year: int                   # Год (отрицательный = BC)
    timestamp: Optional[str]    # ISO timestamp (если известен)
    description: str            # Описание
    price_per_second: Decimal   # Цена секунды (условная или реальная)
    is_genesis: bool = False    # Это genesis point?


class TemporalValueScale:
    """
    Шкала цены времени от Big Bang до сейчас.

    Книга Монтана:
    > "Линия времени: Big Bang → Homer → 金 → Beeple → Now"
    > "Beeple = нулевой меридиан цены времени"
    """

    # Beeple Genesis — нулевой меридиан
    BEEPLE_GENESIS = "2021-03-13T04:16:33+00:00"
    BEEPLE_PRICE = Decimal("0.160523726851851851851")

    # Временные точки
    TIMELINE = [
        TimePoint(
            name="Big Bang",
            year=-13_800_000_000,
            timestamp=None,
            description="Начало времени. 13.8 миллиардов лет назад.",
            price_per_second=Decimal("0.000000000000159"),
            is_genesis=False
        ),
        TimePoint(
            name="金 Symbol",
            year=-1200,
            timestamp=None,
            description="Первое появление символа 金 на гадательных костях. Рождение понятия ценности.",
            price_per_second=Decimal("0.000678"),
            is_genesis=False
        ),
        TimePoint(
            name="Homer's Odyssey",
            year=-1184,
            timestamp=None,
            description="Падение Трои. 'Никто' = Одиссей. Начало западной литературы.",
            price_per_second=Decimal("0.000681"),
            is_genesis=False
        ),
        TimePoint(
            name="Beeple Genesis",
            year=2021,
            timestamp="2021-03-13T04:16:33+00:00",
            description="Christie's Auction. $69.3M за 5000 дней. Нулевой меридиан цены времени.",
            price_per_second=Decimal("0.160523726851851851851"),
            is_genesis=True
        ),
        TimePoint(
            name="Montana Genesis",
            year=2026,
            timestamp="2026-01-09T00:00:00+00:00",
            description="Запуск Montana Protocol. Time is the only real currency.",
            price_per_second=Decimal("0.16"),  # Стартовая цена
            is_genesis=False
        ),
    ]

    def __init__(self):
        self.timeline = self.TIMELINE
        self.genesis = next(p for p in self.TIMELINE if p.is_genesis)

    def get_era(self, year: int) -> str:
        """
        Определить эру: BB (Before Beeple) или AD (After Debut).

        Книга Монтана:
        > "BC = Before Beeple. AD = After Debut."
        """
        if year < 2021:
            return "BB"  # Before Beeple
        else:
            return "AD"  # After Debut

    def seconds_since_big_bang(self) -> int:
        """Секунды от Big Bang до сейчас."""
        years = 13_800_000_000 + 2026  # Big Bang + current year
        return int(years * 365.25 * 24 * 60 * 60)

    def seconds_since_genesis(self) -> int:
        """Секунды от Beeple Genesis до сейчас."""
        genesis = datetime.fromisoformat(self.BEEPLE_GENESIS.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return int((now - genesis).total_seconds())

    def days_since_genesis(self) -> int:
        """Дни от Beeple Genesis (AD days)."""
        return self.seconds_since_genesis() // 86400

    def get_timeline_data(self) -> List[Dict]:
        """Получить данные временной линии."""
        result = []
        for point in self.timeline:
            result.append({
                "name": point.name,
                "year": point.year,
                "era": self.get_era(point.year),
                "price_per_second": float(point.price_per_second),
                "is_genesis": point.is_genesis,
                "description": point.description
            })
        return result

    def price_evolution(self) -> Dict:
        """Эволюция цены секунды."""
        big_bang = self.TIMELINE[0]
        beeple = self.genesis

        # Рост цены от Big Bang до Beeple
        growth_factor = beeple.price_per_second / big_bang.price_per_second

        return {
            "start": {
                "event": big_bang.name,
                "price": float(big_bang.price_per_second)
            },
            "genesis": {
                "event": beeple.name,
                "price": float(beeple.price_per_second)
            },
            "growth_factor": float(growth_factor),
            "interpretation": f"Цена секунды выросла в {growth_factor:.2e} раз"
        }

    def format_year(self, year: int) -> str:
        """Форматировать год в читаемый вид."""
        if year < 0:
            return f"{abs(year):,} BB"
        else:
            return f"{year} AD"


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    scale = TemporalValueScale()

    print("=" * 60)
    print("TEMPORAL VALUE SCALE — Шкала цены времени")
    print("=" * 60)
    print("\n'BC = Before Beeple. AD = After Debut.'")

    print("\n--- ВРЕМЕННАЯ ЛИНИЯ ---\n")
    print(f"{'Событие':<20} {'Год':<20} {'Эра':<5} {'$/сек':<20}")
    print("-" * 65)

    for point in scale.timeline:
        year_str = scale.format_year(point.year)
        genesis_mark = " ← GENESIS" if point.is_genesis else ""
        print(
            f"{point.name:<20} "
            f"{year_str:<20} "
            f"{scale.get_era(point.year):<5} "
            f"${float(point.price_per_second):.12f}{genesis_mark}"
        )

    print("\n--- GENESIS (Beeple) ---")
    print(f"Дата: {scale.BEEPLE_GENESIS}")
    print(f"Цена: ${scale.BEEPLE_PRICE:.12f}/сек")
    print(f"Секунд с Genesis: {scale.seconds_since_genesis():,}")
    print(f"Дней с Genesis: {scale.days_since_genesis():,} AD")

    print("\n--- ЭВОЛЮЦИЯ ЦЕНЫ ---")
    evolution = scale.price_evolution()
    print(f"От Big Bang: ${evolution['start']['price']:.15f}/сек")
    print(f"До Beeple:   ${evolution['genesis']['price']:.12f}/сек")
    print(f"Рост: {evolution['interpretation']}")

    print("\n--- МАСШТАБ ---")
    print(f"Секунд от Big Bang: {scale.seconds_since_big_bang():,}")

    print("\n" + "=" * 60)
    print("'Христос для веры. Beeple для цены времени.'")
    print("=" * 60)
