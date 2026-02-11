#!/usr/bin/env python3
"""
three_mirrors.py — Три зеркала легитимности Montana

Книга Монтана, Глава 03:
> "「三つの鏡」(Mitsu no Kagami — 'Три зеркала') — эссе Акутагавы Рюноскэ"
> "Аматэрасу не доказывала, что отражение — её. Она просто узнала."
> "Легитимность = признание + узнавание + верифицируемость во времени. Всё три есть."

Три зеркала:
1. Признание (Recognition) — я признаю это своим
2. Узнавание (Identification) — другие узнают мой стиль
3. Верифицируемость (Verification) — timestamps подтверждают
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum
import hashlib


class MirrorStatus(Enum):
    """Статус проверки зеркала."""
    PASSED = "passed"       # Проверка пройдена
    FAILED = "failed"       # Проверка не пройдена
    PENDING = "pending"     # Ожидает проверки


@dataclass
class MirrorCheck:
    """Результат проверки одного зеркала."""
    mirror_name: str
    status: MirrorStatus
    evidence: str
    checked_at: str
    confidence: float  # 0.0 - 1.0


@dataclass
class LegitimacyResult:
    """Полный результат проверки легитимности."""
    recognition: MirrorCheck    # Зеркало 1: Признание
    identification: MirrorCheck # Зеркало 2: Узнавание
    verification: MirrorCheck   # Зеркало 3: Верифицируемость

    @property
    def is_legitimate(self) -> bool:
        """Легитимно только если ВСЕ три зеркала пройдены."""
        return (
            self.recognition.status == MirrorStatus.PASSED and
            self.identification.status == MirrorStatus.PASSED and
            self.verification.status == MirrorStatus.PASSED
        )

    @property
    def total_confidence(self) -> float:
        """Общая уверенность (произведение)."""
        return (
            self.recognition.confidence *
            self.identification.confidence *
            self.verification.confidence
        )

    def to_dict(self) -> dict:
        return {
            "is_legitimate": self.is_legitimate,
            "total_confidence": self.total_confidence,
            "mirrors": {
                "recognition": {
                    "status": self.recognition.status.value,
                    "evidence": self.recognition.evidence,
                    "confidence": self.recognition.confidence
                },
                "identification": {
                    "status": self.identification.status.value,
                    "evidence": self.identification.evidence,
                    "confidence": self.identification.confidence
                },
                "verification": {
                    "status": self.verification.status.value,
                    "evidence": self.verification.evidence,
                    "confidence": self.verification.confidence
                }
            }
        }


class ThreeMirrors:
    """
    Система проверки легитимности через три зеркала.

    Книга Монтана:
    > "Ты смотришь на поток #174 и узнаёшь себя. Это и есть работа зеркала."
    """

    def __init__(self):
        self.checks_history: List[LegitimacyResult] = []

    def check_recognition(
        self,
        author_id: str,
        content_hash: str,
        author_confirms: bool,
        evidence: str = ""
    ) -> MirrorCheck:
        """
        Зеркало 1: Признание.

        Автор признаёт контент своим?

        Args:
            author_id: ID автора
            content_hash: Hash контента
            author_confirms: Автор подтверждает?
            evidence: Доказательство (подпись, заявление)

        Returns:
            MirrorCheck с результатом
        """
        return MirrorCheck(
            mirror_name="Recognition (Признание)",
            status=MirrorStatus.PASSED if author_confirms else MirrorStatus.FAILED,
            evidence=evidence or f"Author {author_id} {'confirms' if author_confirms else 'denies'} content {content_hash[:8]}",
            checked_at=datetime.now(timezone.utc).isoformat(),
            confidence=1.0 if author_confirms else 0.0
        )

    def check_identification(
        self,
        content_hash: str,
        recognizers: List[Tuple[str, float]],
        min_recognizers: int = 1,
        min_avg_confidence: float = 0.5
    ) -> MirrorCheck:
        """
        Зеркало 2: Узнавание.

        Другие узнают стиль автора?

        Args:
            content_hash: Hash контента
            recognizers: Список (узел_id, confidence) тех, кто узнал стиль
            min_recognizers: Минимум узнавших
            min_avg_confidence: Минимальная средняя уверенность

        Returns:
            MirrorCheck с результатом
        """
        if not recognizers:
            return MirrorCheck(
                mirror_name="Identification (Узнавание)",
                status=MirrorStatus.FAILED,
                evidence="No recognizers",
                checked_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0
            )

        avg_confidence = sum(c for _, c in recognizers) / len(recognizers)
        passed = len(recognizers) >= min_recognizers and avg_confidence >= min_avg_confidence

        return MirrorCheck(
            mirror_name="Identification (Узнавание)",
            status=MirrorStatus.PASSED if passed else MirrorStatus.FAILED,
            evidence=f"{len(recognizers)} recognizers, avg_confidence={avg_confidence:.2f}",
            checked_at=datetime.now(timezone.utc).isoformat(),
            confidence=avg_confidence
        )

    def check_verification(
        self,
        content_hash: str,
        timestamps: List[str],
        expected_author_pattern: bool = True
    ) -> MirrorCheck:
        """
        Зеркало 3: Верифицируемость.

        Timestamps подтверждают авторство?

        Args:
            content_hash: Hash контента
            timestamps: Список временных меток
            expected_author_pattern: Паттерн соответствует автору?

        Returns:
            MirrorCheck с результатом
        """
        if not timestamps:
            return MirrorCheck(
                mirror_name="Verification (Верифицируемость)",
                status=MirrorStatus.FAILED,
                evidence="No timestamps",
                checked_at=datetime.now(timezone.utc).isoformat(),
                confidence=0.0
            )

        # Проверяем что timestamps валидны и в правильном порядке
        try:
            parsed = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in timestamps]
            is_ordered = all(parsed[i] <= parsed[i+1] for i in range(len(parsed)-1))
        except Exception:
            is_ordered = False

        passed = is_ordered and expected_author_pattern

        return MirrorCheck(
            mirror_name="Verification (Верифицируемость)",
            status=MirrorStatus.PASSED if passed else MirrorStatus.FAILED,
            evidence=f"{len(timestamps)} timestamps, ordered={is_ordered}, pattern_match={expected_author_pattern}",
            checked_at=datetime.now(timezone.utc).isoformat(),
            confidence=1.0 if passed else 0.3
        )

    def check_legitimacy(
        self,
        author_id: str,
        content_hash: str,
        author_confirms: bool,
        recognizers: List[Tuple[str, float]],
        timestamps: List[str],
        expected_pattern: bool = True
    ) -> LegitimacyResult:
        """
        Полная проверка легитимности через три зеркала.

        Args:
            author_id: ID автора
            content_hash: Hash контента
            author_confirms: Автор подтверждает?
            recognizers: Кто узнал стиль
            timestamps: Временные метки
            expected_pattern: Паттерн соответствует?

        Returns:
            LegitimacyResult с результатами всех трёх зеркал
        """
        recognition = self.check_recognition(
            author_id, content_hash, author_confirms
        )
        identification = self.check_identification(
            content_hash, recognizers
        )
        verification = self.check_verification(
            content_hash, timestamps, expected_pattern
        )

        result = LegitimacyResult(
            recognition=recognition,
            identification=identification,
            verification=verification
        )

        self.checks_history.append(result)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mirrors = ThreeMirrors()

    print("=" * 60)
    print("THREE MIRRORS — Три зеркала легитимности")
    print("=" * 60)
    print("\n'Легитимность = признание + узнавание + верифицируемость'")

    # Пример: проверка потока мыслей #174
    content_hash = hashlib.sha256(b"stream_174_content").hexdigest()

    print("\n--- ПРОВЕРКА ПОТОКА #174 ---")

    result = mirrors.check_legitimacy(
        author_id="alejandro",
        content_hash=content_hash,
        author_confirms=True,  # Автор признаёт
        recognizers=[
            ("mama", 1.0),     # Мама узнаёт стиль
            ("dato", 0.95),    # Дато: "вот именно"
            ("ilya", 0.7),     # Илья менее уверен
        ],
        timestamps=[
            "2026-01-10T11:25:00+00:00",
            "2026-01-10T15:30:00+00:00",
            "2026-01-10T22:20:00+00:00",
        ],
        expected_pattern=True
    )

    print(f"\n1. ПРИЗНАНИЕ: {result.recognition.status.value}")
    print(f"   {result.recognition.evidence}")

    print(f"\n2. УЗНАВАНИЕ: {result.identification.status.value}")
    print(f"   {result.identification.evidence}")

    print(f"\n3. ВЕРИФИЦИРУЕМОСТЬ: {result.verification.status.value}")
    print(f"   {result.verification.evidence}")

    print(f"\n--- ИТОГ ---")
    print(f"Легитимно: {'✓ ДА' if result.is_legitimate else '✗ НЕТ'}")
    print(f"Общая уверенность: {result.total_confidence:.2%}")

    # Пример: попытка подделки
    print("\n\n--- ПОПЫТКА ПОДДЕЛКИ ---")

    fake_result = mirrors.check_legitimacy(
        author_id="imposter",
        content_hash=hashlib.sha256(b"fake_content").hexdigest(),
        author_confirms=True,  # Самозванец "признаёт"
        recognizers=[],        # Никто не узнаёт стиль!
        timestamps=["2026-01-10T11:25:00+00:00"],
        expected_pattern=False  # Паттерн не соответствует
    )

    print(f"\n1. ПРИЗНАНИЕ: {fake_result.recognition.status.value}")
    print(f"2. УЗНАВАНИЕ: {fake_result.identification.status.value} ← ПРОВАЛ")
    print(f"3. ВЕРИФИЦИРУЕМОСТЬ: {fake_result.verification.status.value} ← ПРОВАЛ")

    print(f"\n--- ИТОГ ---")
    print(f"Легитимно: {'✓ ДА' if fake_result.is_legitimate else '✗ НЕТ'}")
    print(f"Общая уверенность: {fake_result.total_confidence:.2%}")

    print("\n" + "=" * 60)
    print("'Аматэрасу не доказывала. Она просто узнала.'")
    print("=" * 60)
