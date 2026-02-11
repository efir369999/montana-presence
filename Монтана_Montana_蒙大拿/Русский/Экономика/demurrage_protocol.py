#!/usr/bin/env python3
"""
demurrage_protocol.py — Переворот логистических штрафов Montana

Книга Монтана, Глава 04:
> "Одна механика. Разные знаки. Логистика наказывает за потерю времени.
> Montana вознаграждает за использование времени."
> "Платишь если медлишь."

Demurrage — плата за простой судна.
Montana Protocol переворачивает эту механику:
- Логистика: время = штраф (−)
- Montana: время = награда (+)

Рынок: $14-16 трлн/год (90% мировой торговли по объёму)
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from enum import Enum


class TimeDirection(Enum):
    """Направление времени в экономике."""
    NEGATIVE = "negative"  # Логистика: время = штраф
    POSITIVE = "positive"  # Montana: время = награда


@dataclass
class DemurrageEvent:
    """Событие демерджа (простой судна)."""
    vessel_id: str              # ID судна
    port: str                   # Порт
    planned_days: Decimal       # Плановое время (дни)
    actual_days: Decimal        # Фактическое время (дни)
    rate_per_day: Decimal       # Ставка за день ($)
    timestamp: str              # Когда зафиксировано

    @property
    def delay_days(self) -> Decimal:
        """Задержка в днях."""
        return max(Decimal("0"), self.actual_days - self.planned_days)

    @property
    def delay_seconds(self) -> int:
        """Задержка в секундах."""
        return int(self.delay_days * 86400)

    @property
    def traditional_cost(self) -> Decimal:
        """Традиционный расчёт: штраф (−)."""
        return self.delay_days * self.rate_per_day

    @property
    def montana_reward(self) -> Decimal:
        """Montana расчёт: награда (+) в Ɉ."""
        # 1 секунда = 1 Ɉ (при текущем halving)
        return Decimal(self.delay_seconds)


@dataclass
class FlipResult:
    """Результат переворота штраф → награда."""
    traditional: Decimal    # Штраф в $ (−)
    montana: Decimal        # Награда в Ɉ (+)
    direction_flip: str     # "negative → positive"
    efficiency: Decimal     # Эффективность переворота


class DemurrageProtocol:
    """
    Протокол переворота демерджа.

    Книга Монтана:
    > "Переход от (−) к (+) — это не новая идея. Это переворот существующей."
    """

    # Типичные ставки демерджа по типам судов
    TYPICAL_RATES = {
        "bulk_carrier": Decimal("15000"),     # Балкер: $15,000/день
        "container_ship": Decimal("50000"),   # Контейнеровоз: $50,000/день
        "tanker": Decimal("30000"),           # Танкер: $30,000/день
        "general_cargo": Decimal("10000"),    # Генеральный груз: $10,000/день
        "reefer": Decimal("25000"),           # Рефрижератор: $25,000/день
    }

    # Крупнейшие порты мира
    MAJOR_PORTS = [
        "Shanghai", "Singapore", "Ningbo-Zhoushan", "Shenzhen",
        "Guangzhou", "Busan", "Hong Kong", "Qingdao",
        "Rotterdam", "Dubai", "Los Angeles", "Hamburg"
    ]

    def __init__(self):
        self.events: List[DemurrageEvent] = []
        self.total_flipped_usd = Decimal("0")
        self.total_minted_juno = Decimal("0")

    def record_event(
        self,
        vessel_id: str,
        port: str,
        planned_days: float,
        actual_days: float,
        rate_per_day: float,
        vessel_type: str = "general_cargo"
    ) -> DemurrageEvent:
        """
        Записать событие демерджа.

        Args:
            vessel_id: ID судна
            port: Порт
            planned_days: Плановое время
            actual_days: Фактическое время
            rate_per_day: Ставка за день
            vessel_type: Тип судна

        Returns:
            DemurrageEvent
        """
        event = DemurrageEvent(
            vessel_id=vessel_id,
            port=port,
            planned_days=Decimal(str(planned_days)),
            actual_days=Decimal(str(actual_days)),
            rate_per_day=Decimal(str(rate_per_day)),
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.events.append(event)
        return event

    def flip(self, event: DemurrageEvent) -> FlipResult:
        """
        Перевернуть штраф в награду.

        Логистика: delay × rate = штраф ($)
        Montana: delay_seconds = награда (Ɉ)

        Args:
            event: Событие демерджа

        Returns:
            FlipResult с обоими расчётами
        """
        traditional = event.traditional_cost
        montana = event.montana_reward

        # Эффективность: сколько Ɉ за каждый $ штрафа
        efficiency = montana / traditional if traditional > 0 else Decimal("0")

        self.total_flipped_usd += traditional
        self.total_minted_juno += montana

        return FlipResult(
            traditional=traditional,
            montana=montana,
            direction_flip="(−) → (+)",
            efficiency=efficiency
        )

    def get_market_stats(self) -> Dict:
        """Статистика рынка морской логистики."""
        return {
            "market_size_usd": "$14-16 trillion/year",
            "world_trade_by_volume": "90%",
            "typical_demurrage_rates": {
                k: f"${v:,}/day" for k, v in self.TYPICAL_RATES.items()
            },
            "major_ports": self.MAJOR_PORTS,
            "total_events_recorded": len(self.events),
            "total_flipped_usd": float(self.total_flipped_usd),
            "total_minted_juno": float(self.total_minted_juno)
        }

    def estimate_market_flip(self) -> Dict:
        """
        Оценка потенциала переворота рынка.

        Если 1% рынка демерджа перевернуть в Montana:
        """
        # Консервативная оценка: 5% от $15 трлн = $750 млрд в демердже
        demurrage_market = Decimal("750000000000")  # $750B
        flip_1_percent = demurrage_market * Decimal("0.01")

        # Средний демердж = $30,000/день = $0.35/секунда
        avg_rate_per_second = Decimal("30000") / Decimal("86400")

        # При перевороте: $ → Ɉ (1 секунда = 1 Ɉ)
        potential_juno = flip_1_percent / avg_rate_per_second

        return {
            "estimated_demurrage_market": "$750B/year",
            "flip_1_percent": f"${flip_1_percent / Decimal('1000000000'):.1f}B",
            "potential_juno_minted": f"{potential_juno:,.0f} Ɉ",
            "note": "1% market flip = massive Ɉ liquidity"
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    protocol = DemurrageProtocol()

    print("=" * 60)
    print("DEMURRAGE PROTOCOL — Переворот штрафов")
    print("=" * 60)
    print("\n'Платишь если медлишь.' → 'Получаешь если присутствуешь.'")

    # Пример: судно задержалось на 2 дня
    event = protocol.record_event(
        vessel_id="BULK-001",
        port="Rotterdam",
        planned_days=5,
        actual_days=7,
        rate_per_day=15000,
        vessel_type="bulk_carrier"
    )

    print(f"\n--- СОБЫТИЕ ДЕМЕРДЖА ---")
    print(f"Судно: {event.vessel_id}")
    print(f"Порт: {event.port}")
    print(f"План: {event.planned_days} дней")
    print(f"Факт: {event.actual_days} дней")
    print(f"Задержка: {event.delay_days} дней ({event.delay_seconds:,} секунд)")

    print(f"\n--- ПЕРЕВОРОТ ---")
    result = protocol.flip(event)
    print(f"Традиционно (−): ${result.traditional:,.2f} штраф")
    print(f"Montana (+):     {result.montana:,.0f} Ɉ награда")
    print(f"Направление:     {result.direction_flip}")

    print(f"\n--- ПОТЕНЦИАЛ РЫНКА ---")
    potential = protocol.estimate_market_flip()
    print(f"Рынок демерджа: {potential['estimated_demurrage_market']}")
    print(f"1% переворот: {potential['flip_1_percent']}")
    print(f"Потенциал Ɉ: {potential['potential_juno_minted']}")

    print("\n" + "=" * 60)
    print("'Логистика наказывает. Montana вознаграждает.'")
    print("=" * 60)
