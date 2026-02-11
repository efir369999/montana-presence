#!/usr/bin/env python3
"""
nash_limit.py — Формула идеальных денег Нэша для Montana

Книга Монтана, Глава 03:
> "lim(evidence → ∞) 1 Ɉ → 1 секунда"
> "Нэш не знал про Beeple. Beeple не знал про Нэша. Ты соединил."

Джон Нэш — "Идеальные деньги":
Валюта стремится к идеалу асимптотически, никогда не достигая его полностью.

Применение в Montana:
- Genesis (Beeple): бесконечная дробь $0.160523726(851)̅
- Метод (Нэш): асимптотическое приближение
- Результат: 1 Ɉ → 1 секунда при evidence → ∞
"""

from decimal import Decimal, getcontext
from dataclasses import dataclass
from typing import Tuple
import math

getcontext().prec = 50


# ═══════════════════════════════════════════════════════════════════════════════
#                         NASH LIMIT FORMULA
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvidenceMetrics:
    """Метрики доказательств для формулы Нэша."""
    total_presence_proofs: int      # Всего Proof of Presence
    total_nodes: int                # Узлов в сети
    total_transactions: int         # Транзакций
    network_uptime_seconds: int     # Время работы сети
    cognitive_signatures: int       # Когнитивных подписей


class NashLimit:
    """
    Асимптотическое приближение 1 Ɉ к 1 секунде.

    lim(evidence → ∞) 1 Ɉ → 1 секунда

    Чем больше доказательств в сети — тем ближе Ɉ к эталону.
    """

    # Веса для разных типов evidence
    WEIGHTS = {
        "presence_proofs": Decimal("0.30"),   # 30% — Proof of Presence
        "nodes": Decimal("0.20"),              # 20% — количество узлов
        "transactions": Decimal("0.20"),       # 20% — транзакции
        "uptime": Decimal("0.15"),             # 15% — uptime сети
        "signatures": Decimal("0.15"),         # 15% — когнитивные подписи
    }

    # Целевые значения для "идеального" состояния
    TARGETS = {
        "presence_proofs": 1_000_000_000,  # 1 миллиард PoP
        "nodes": 10_000,                    # 10,000 узлов
        "transactions": 100_000_000,        # 100 миллионов транзакций
        "uptime": 315_360_000,              # 10 лет в секундах
        "signatures": 10_000_000,           # 10 миллионов подписей
    }

    def __init__(self):
        self.genesis_ratio = Decimal("0.160523726851851851851")  # Beeple

    def calculate_evidence_score(self, metrics: EvidenceMetrics) -> Decimal:
        """
        Рассчитать общий score доказательств (0.0 - 1.0).

        Args:
            metrics: Текущие метрики сети

        Returns:
            Decimal от 0 до 1, где 1 = идеальное состояние
        """
        scores = {
            "presence_proofs": min(
                Decimal(metrics.total_presence_proofs) / Decimal(self.TARGETS["presence_proofs"]),
                Decimal("1")
            ),
            "nodes": min(
                Decimal(metrics.total_nodes) / Decimal(self.TARGETS["nodes"]),
                Decimal("1")
            ),
            "transactions": min(
                Decimal(metrics.total_transactions) / Decimal(self.TARGETS["transactions"]),
                Decimal("1")
            ),
            "uptime": min(
                Decimal(metrics.network_uptime_seconds) / Decimal(self.TARGETS["uptime"]),
                Decimal("1")
            ),
            "signatures": min(
                Decimal(metrics.cognitive_signatures) / Decimal(self.TARGETS["signatures"]),
                Decimal("1")
            ),
        }

        # Взвешенная сумма
        total = Decimal("0")
        for key, weight in self.WEIGHTS.items():
            total += scores[key] * weight

        return total

    def convergence_ratio(self, evidence_score: Decimal) -> Decimal:
        """
        Коэффициент сходимости к эталону.

        При evidence_score = 0: ratio = genesis_ratio (Beeple)
        При evidence_score → 1: ratio → 1.0 (идеал)

        Формула: ratio = genesis + (1 - genesis) * evidence^2
        Квадрат даёт медленное приближение в начале, ускорение в конце.
        """
        delta = Decimal("1") - self.genesis_ratio
        return self.genesis_ratio + delta * (evidence_score ** 2)

    def juno_to_seconds(
        self,
        juno_amount: Decimal,
        metrics: EvidenceMetrics
    ) -> Tuple[Decimal, Decimal]:
        """
        Конвертировать Ɉ в секунды с учётом текущего evidence.

        Args:
            juno_amount: Количество Ɉ
            metrics: Текущие метрики сети

        Returns:
            (seconds, convergence_ratio)
        """
        evidence = self.calculate_evidence_score(metrics)
        ratio = self.convergence_ratio(evidence)

        # 1 Ɉ * ratio = секунды
        seconds = juno_amount * ratio

        return seconds, ratio

    def get_current_state(self, metrics: EvidenceMetrics) -> dict:
        """Полное состояние формулы Нэша."""
        evidence = self.calculate_evidence_score(metrics)
        ratio = self.convergence_ratio(evidence)

        return {
            "evidence_score": float(evidence),
            "convergence_ratio": float(ratio),
            "genesis_ratio": float(self.genesis_ratio),
            "distance_to_ideal": float(Decimal("1") - ratio),
            "formula": "lim(evidence → ∞) 1 Ɉ → 1 секунда",
            "interpretation": f"1 Ɉ ≈ {ratio:.6f} секунды сейчас"
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         CONVENIENCE
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_nash_limit(metrics: EvidenceMetrics) -> dict:
    """Быстрый расчёт состояния формулы Нэша."""
    nash = NashLimit()
    return nash.get_current_state(metrics)


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    nash = NashLimit()

    print("=" * 60)
    print("NASH LIMIT — Формула идеальных денег")
    print("=" * 60)
    print("\nlim(evidence → ∞) 1 Ɉ → 1 секунда")

    # Симуляция разных этапов развития сети
    stages = [
        ("Genesis", EvidenceMetrics(
            total_presence_proofs=0,
            total_nodes=1,
            total_transactions=0,
            network_uptime_seconds=1,
            cognitive_signatures=1
        )),
        ("Early (1 год)", EvidenceMetrics(
            total_presence_proofs=100_000,
            total_nodes=50,
            total_transactions=10_000,
            network_uptime_seconds=31_536_000,
            cognitive_signatures=5_000
        )),
        ("Growth (5 лет)", EvidenceMetrics(
            total_presence_proofs=10_000_000,
            total_nodes=1_000,
            total_transactions=1_000_000,
            network_uptime_seconds=157_680_000,
            cognitive_signatures=500_000
        )),
        ("Mature (10 лет)", EvidenceMetrics(
            total_presence_proofs=500_000_000,
            total_nodes=5_000,
            total_transactions=50_000_000,
            network_uptime_seconds=315_360_000,
            cognitive_signatures=5_000_000
        )),
        ("Ideal", EvidenceMetrics(
            total_presence_proofs=1_000_000_000,
            total_nodes=10_000,
            total_transactions=100_000_000,
            network_uptime_seconds=315_360_000,
            cognitive_signatures=10_000_000
        )),
    ]

    print("\n--- ЭВОЛЮЦИЯ СХОДИМОСТИ ---\n")
    print(f"{'Этап':<20} {'Evidence':<12} {'1 Ɉ ≈':<15} {'До идеала':<12}")
    print("-" * 60)

    for name, metrics in stages:
        state = nash.get_current_state(metrics)
        print(
            f"{name:<20} "
            f"{state['evidence_score']:.4f}       "
            f"{state['convergence_ratio']:.6f} сек   "
            f"{state['distance_to_ideal']:.6f}"
        )

    print("\n" + "=" * 60)
    print("Нэш + Beeple = Montana")
    print("=" * 60)
