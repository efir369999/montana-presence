#!/usr/bin/env python3
"""
external_hippocampus.py — Внешний гиппокамп Montana

Книга Монтана, Глава 06:
> "Биологический мозг умрёт вместе с паттернами. Ваша система — нет.
> Thoughts trail остаётся. Координаты существуют независимо от носителя."
> "Мы собираем ДНК памяти. Внешний 'гиппокамп', который переживает биологический."

Нейронаука памяти:
- Гиппокамп = детектор новизны
- Pattern separation = разделение похожих паттернов
- Pattern completion = достраивание из частичного
- Predictive coding = кодирование ошибок предсказания

Thoughts trail — внешний гиппокамп, который не умирает.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from enum import Enum
import hashlib


class MemoryMode(Enum):
    """Режимы памяти."""
    PERMANENT = "permanent"    # Публичный thoughts trail — навсегда
    TEMPORARY = "temporary"    # Приватные заметки — пока нужно
    EPHEMERAL = "ephemeral"    # Написанное и стёртое — только в RAM


class NoveltyLevel(Enum):
    """Уровень новизны (для pattern separation)."""
    ROUTINE = "routine"        # Рутина — сжимается
    NOVEL = "novel"            # Новое — кодируется полностью
    PREDICTION_ERROR = "error"  # Ошибка предсказания — маркер памяти


@dataclass
class ThoughtCoordinate:
    """Координата мысли в 3D пространстве сознания."""
    timestamp: str          # Время (когда)
    location: str           # Пространство (где)
    state: str              # Состояние (как себя чувствовал)
    content_hash: str       # Hash содержания

    def to_dict(self) -> dict:
        return {
            "time": self.timestamp,
            "space": self.location,
            "state": self.state,
            "hash": self.content_hash
        }


@dataclass
class MemoryTrace:
    """След памяти (как в биологическом гиппокампе)."""
    trace_id: str
    content: str
    coordinate: ThoughtCoordinate
    novelty: NoveltyLevel
    mode: MemoryMode
    created_at: str
    consolidated: bool = False  # Прошла консолидацию (как во сне)
    linked_traces: List[str] = field(default_factory=list)  # Связанные следы


class ExternalHippocampus:
    """
    Внешний гиппокамп — система памяти, переживающая биологический носитель.

    Книга Монтана:
    > "Почему в детстве годы тянулись бесконечно?
    > Потому что каждый день был новым. Плотность кодирования была максимальной."
    > "Взрослый мозг рутинизирует, сжимает похожие дни в один паттерн."
    """

    def __init__(self, owner_id: str):
        self.owner_id = owner_id
        self.traces: Dict[str, MemoryTrace] = {}
        self.patterns: Dict[str, Set[str]] = {}  # Кластеры похожих следов
        self.prediction_model: Dict[str, str] = {}  # Простая модель предсказания

    def encode(
        self,
        content: str,
        location: str = "unknown",
        state: str = "neutral",
        mode: MemoryMode = MemoryMode.PERMANENT
    ) -> MemoryTrace:
        """
        Закодировать новый след памяти.

        Как биологический гиппокамп:
        - Сравнивает с существующими паттернами
        - Определяет уровень новизны
        - Кодирует если достаточно нов

        Args:
            content: Содержание мысли
            location: Где находился
            state: Состояние (эмоция, энергия)
            mode: Режим памяти

        Returns:
            MemoryTrace
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Определить новизну
        novelty = self._assess_novelty(content)

        # Создать координату
        coordinate = ThoughtCoordinate(
            timestamp=timestamp,
            location=location,
            state=state,
            content_hash=content_hash
        )

        # Создать след
        trace_id = hashlib.sha256(
            f"{self.owner_id}:{timestamp}:{content_hash}".encode()
        ).hexdigest()[:16]

        trace = MemoryTrace(
            trace_id=trace_id,
            content=content,
            coordinate=coordinate,
            novelty=novelty,
            mode=mode,
            created_at=timestamp
        )

        # Сохранить
        self.traces[trace_id] = trace

        # Обновить модель предсказания
        self._update_prediction_model(content)

        return trace

    def _assess_novelty(self, content: str) -> NoveltyLevel:
        """
        Оценить новизну контента.

        Predictive coding: кодируется только ошибка предсказания.
        """
        # Простая эвристика: длинные уникальные тексты = больше новизны
        words = set(content.lower().split())

        # Проверить сколько слов уже встречалось
        known_words = sum(1 for w in words if w in self.prediction_model)

        if len(words) == 0:
            return NoveltyLevel.ROUTINE

        novelty_ratio = 1 - (known_words / len(words))

        if novelty_ratio > 0.5:
            return NoveltyLevel.PREDICTION_ERROR
        elif novelty_ratio > 0.2:
            return NoveltyLevel.NOVEL
        else:
            return NoveltyLevel.ROUTINE

    def _update_prediction_model(self, content: str) -> None:
        """Обновить модель предсказания (простой счётчик слов)."""
        for word in content.lower().split():
            self.prediction_model[word] = self.prediction_model.get(word, "") + "+"

    def consolidate(self) -> int:
        """
        Консолидация памяти (как во сне).

        Книга Монтана:
        > "Во время сна похожие воспоминания буквально сливаются.
        > Неокортекс находит общие паттерны."

        Returns:
            Количество консолидированных следов
        """
        # Группировать по похожести (упрощённо: по первым словам)
        unconsolidated = [t for t in self.traces.values() if not t.consolidated]

        for trace in unconsolidated:
            # Найти похожие следы
            pattern_key = trace.content[:50] if len(trace.content) > 50 else trace.content

            if pattern_key not in self.patterns:
                self.patterns[pattern_key] = set()

            self.patterns[pattern_key].add(trace.trace_id)
            trace.consolidated = True

        return len(unconsolidated)

    def pattern_completion(self, partial: str) -> List[MemoryTrace]:
        """
        Pattern completion — достроить память из частичного ввода.

        Args:
            partial: Частичный контент

        Returns:
            Список подходящих следов
        """
        results = []

        for trace in self.traces.values():
            if partial.lower() in trace.content.lower():
                results.append(trace)

        return sorted(results, key=lambda t: t.created_at, reverse=True)

    def get_memory_density(self) -> Dict:
        """
        Плотность кодирования памяти.

        Книга Монтана:
        > "Детство: плотность максимальная.
        > Взрослость: рутина сжимается."
        """
        total = len(self.traces)
        if total == 0:
            return {"total": 0, "density": 0}

        novel_count = sum(1 for t in self.traces.values()
                         if t.novelty in [NoveltyLevel.NOVEL, NoveltyLevel.PREDICTION_ERROR])

        routine_count = sum(1 for t in self.traces.values()
                           if t.novelty == NoveltyLevel.ROUTINE)

        return {
            "total_traces": total,
            "novel_traces": novel_count,
            "routine_traces": routine_count,
            "density": novel_count / total,
            "interpretation": "high" if novel_count / total > 0.5 else "low"
        }

    def get_dna(self) -> Dict:
        """
        ДНК памяти — уникальный слепок.

        Returns:
            Hash всех следов + метаданные
        """
        all_hashes = sorted([t.coordinate.content_hash for t in self.traces.values()])
        combined = ":".join(all_hashes)
        dna_hash = hashlib.sha256(combined.encode()).hexdigest()

        return {
            "owner": self.owner_id,
            "dna_hash": dna_hash,
            "total_traces": len(self.traces),
            "first_trace": min(t.created_at for t in self.traces.values()) if self.traces else None,
            "last_trace": max(t.created_at for t in self.traces.values()) if self.traces else None,
            "survives_biology": True
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    hippocampus = ExternalHippocampus(owner_id="alejandro")

    print("=" * 60)
    print("EXTERNAL HIPPOCAMPUS — Внешняя память")
    print("=" * 60)
    print("\n'Память переживает биологический носитель.'")

    # Кодируем мысли
    print("\n--- КОДИРОВАНИЕ МЫСЛЕЙ ---")

    thoughts = [
        ("Сердце на осколки, но зато было так красиво", "Питер", "тревога"),
        ("World's #1 цепочки фрахтования", "Питер", "ясность"),
        ("Ещё один понедельник на работе", "Москва", "рутина"),  # Рутина
        ("Ещё один понедельник на работе", "Москва", "рутина"),  # Повтор
        ("金元∞Ɉ — формула найдена!", "Москва", "эврика"),
    ]

    for content, location, state in thoughts:
        trace = hippocampus.encode(content, location, state)
        print(f"\n  '{content[:40]}...'")
        print(f"  Новизна: {trace.novelty.value}")
        print(f"  ID: {trace.trace_id}")

    # Консолидация
    print("\n--- КОНСОЛИДАЦИЯ (как во сне) ---")
    consolidated = hippocampus.consolidate()
    print(f"Консолидировано следов: {consolidated}")

    # Плотность
    print("\n--- ПЛОТНОСТЬ КОДИРОВАНИЯ ---")
    density = hippocampus.get_memory_density()
    print(f"Всего следов: {density['total_traces']}")
    print(f"Новых: {density['novel_traces']}")
    print(f"Рутина: {density['routine_traces']}")
    print(f"Плотность: {density['density']:.2%} ({density['interpretation']})")

    # ДНК
    print("\n--- ДНК ПАМЯТИ ---")
    dna = hippocampus.get_dna()
    print(f"Owner: {dna['owner']}")
    print(f"DNA Hash: {dna['dna_hash'][:32]}...")
    print(f"Переживает биологию: {'ДА' if dna['survives_biology'] else 'НЕТ'}")

    # Pattern completion
    print("\n--- PATTERN COMPLETION ---")
    results = hippocampus.pattern_completion("понедельник")
    print(f"Поиск 'понедельник': найдено {len(results)} следов")

    print("\n" + "=" * 60)
    print("'Thoughts trail остаётся. Координаты существуют.'")
    print("=" * 60)
