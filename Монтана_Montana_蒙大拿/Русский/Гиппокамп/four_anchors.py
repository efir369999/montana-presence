#!/usr/bin/env python3
"""
four_anchors.py — Система четырёх якорей Montana

Книга Монтана, Глава 06:
> "Визуальный якорь — изображение момента"
> "Пространственно-временной якорь — GPS + timestamp"
> "Аудиальный якорь — музыка, которая играла"
> "Дигитальный якорь — текст + контекст"

Четыре координаты для любой точки памяти.
Якоря работают вместе для надёжной верификации.

Дополнительно: Totem Protocol
> "Парный тотем. Два человека знают одинаковую деталь о физическом предмете."
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum
import hashlib


class AnchorType(Enum):
    """Типы якорей."""
    VISUAL = "visual"               # Изображение, скриншот
    SPATIOTEMPORAL = "spatiotemporal"  # GPS + timestamp
    AUDIO = "audio"                 # Саундтрек момента
    DIGITAL = "digital"             # Текст + контекст


@dataclass
class Anchor:
    """Якорь памяти."""
    anchor_type: AnchorType
    reference: str          # Ссылка или данные
    description: str        # Описание
    created_at: str
    verified: bool = False

    def to_hash(self) -> str:
        data = f"{self.anchor_type.value}:{self.reference}:{self.created_at}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class Totem:
    """
    Тотем — парный физический объект для верификации.

    Книга Монтана:
    > "Как в 'Начале'. Волчок Кобба — предмет, который знает только он."
    > "Парный тотем. Два человека знают одинаковую деталь."
    """
    totem_id: str
    object_description: str     # "Красные мокасины"
    secret_detail: str          # Деталь, которую знают только двое
    owner_a: str               # Первый владелец
    owner_b: str               # Второй владелец
    created_at: str

    def verify(self, detail_guess: str) -> bool:
        """Верифицировать через секретную деталь."""
        return detail_guess.lower().strip() == self.secret_detail.lower().strip()


@dataclass
class MemoryPoint:
    """Точка памяти с четырьмя якорями."""
    point_id: str
    visual: Optional[Anchor] = None
    spatiotemporal: Optional[Anchor] = None
    audio: Optional[Anchor] = None
    digital: Optional[Anchor] = None
    totems: List[str] = field(default_factory=list)  # ID тотемов

    @property
    def anchor_count(self) -> int:
        """Количество установленных якорей."""
        count = 0
        if self.visual:
            count += 1
        if self.spatiotemporal:
            count += 1
        if self.audio:
            count += 1
        if self.digital:
            count += 1
        return count

    @property
    def is_fully_anchored(self) -> bool:
        """Все четыре якоря установлены."""
        return self.anchor_count == 4


class FourAnchorsSystem:
    """
    Система четырёх якорей для координат памяти.

    Книга Монтана:
    > "Одинаковые трэки в сэте — это переходы в координатах памяти."
    > "Когда ты слушаешь с временной точкой контекста в тексте,
    > тогда ты узнаёшь координату."
    """

    def __init__(self):
        self.memory_points: Dict[str, MemoryPoint] = {}
        self.totems: Dict[str, Totem] = {}
        self.audio_map: Dict[str, List[str]] = {}  # track → [point_ids]

    def create_memory_point(self, description: str = "") -> MemoryPoint:
        """Создать новую точку памяти."""
        point_id = hashlib.sha256(
            f"{datetime.now().isoformat()}:{description}".encode()
        ).hexdigest()[:16]

        point = MemoryPoint(point_id=point_id)
        self.memory_points[point_id] = point
        return point

    def set_visual_anchor(
        self,
        point_id: str,
        image_url: str,
        description: str = ""
    ) -> Anchor:
        """
        Установить визуальный якорь.

        Args:
            point_id: ID точки памяти
            image_url: URL или путь к изображению
            description: Описание

        Returns:
            Anchor
        """
        anchor = Anchor(
            anchor_type=AnchorType.VISUAL,
            reference=image_url,
            description=description or "Visual moment capture",
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.memory_points[point_id].visual = anchor
        return anchor

    def set_spatiotemporal_anchor(
        self,
        point_id: str,
        latitude: float,
        longitude: float,
        timestamp: str = None
    ) -> Anchor:
        """
        Установить пространственно-временной якорь.

        Args:
            point_id: ID точки памяти
            latitude: Широта
            longitude: Долгота
            timestamp: ISO timestamp (если None — текущее время)

        Returns:
            Anchor
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        reference = f"{latitude},{longitude}@{ts}"

        anchor = Anchor(
            anchor_type=AnchorType.SPATIOTEMPORAL,
            reference=reference,
            description=f"Location: {latitude}, {longitude}",
            created_at=ts
        )

        self.memory_points[point_id].spatiotemporal = anchor
        return anchor

    def set_audio_anchor(
        self,
        point_id: str,
        track_name: str,
        artist: str = "",
        url: str = ""
    ) -> Anchor:
        """
        Установить аудиальный якорь.

        Книга Монтана:
        > "Музыка как машина времени."

        Args:
            point_id: ID точки памяти
            track_name: Название трека
            artist: Исполнитель
            url: Ссылка на трек

        Returns:
            Anchor
        """
        reference = f"{artist} - {track_name}" if artist else track_name
        if url:
            reference += f" ({url})"

        anchor = Anchor(
            anchor_type=AnchorType.AUDIO,
            reference=reference,
            description="Soundtrack of the moment",
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.memory_points[point_id].audio = anchor

        # Добавить в audio map для поиска
        track_key = track_name.lower()
        if track_key not in self.audio_map:
            self.audio_map[track_key] = []
        self.audio_map[track_key].append(point_id)

        return anchor

    def set_digital_anchor(
        self,
        point_id: str,
        text: str,
        context: str = ""
    ) -> Anchor:
        """
        Установить дигитальный якорь.

        Args:
            point_id: ID точки памяти
            text: Текст
            context: Контекст (откуда, зачем)

        Returns:
            Anchor
        """
        anchor = Anchor(
            anchor_type=AnchorType.DIGITAL,
            reference=text[:500],  # Первые 500 символов
            description=context or "Digital text anchor",
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.memory_points[point_id].digital = anchor
        return anchor

    def create_totem(
        self,
        object_description: str,
        secret_detail: str,
        owner_a: str,
        owner_b: str
    ) -> Totem:
        """
        Создать парный тотем.

        Args:
            object_description: Описание объекта ("Красные мокасины")
            secret_detail: Секретная деталь
            owner_a: Первый владелец
            owner_b: Второй владелец

        Returns:
            Totem
        """
        totem_id = hashlib.sha256(
            f"{object_description}:{owner_a}:{owner_b}".encode()
        ).hexdigest()[:16]

        totem = Totem(
            totem_id=totem_id,
            object_description=object_description,
            secret_detail=secret_detail,
            owner_a=owner_a,
            owner_b=owner_b,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.totems[totem_id] = totem
        return totem

    def find_by_track(self, track_name: str) -> List[MemoryPoint]:
        """
        Найти точки памяти по треку.

        Книга Монтана:
        > "Одинаковые трэки в сэте — это переходы в координатах памяти."

        Args:
            track_name: Название трека

        Returns:
            Список точек памяти с этим треком
        """
        track_key = track_name.lower()
        point_ids = self.audio_map.get(track_key, [])
        return [self.memory_points[pid] for pid in point_ids if pid in self.memory_points]

    def get_anchor_status(self, point_id: str) -> Dict:
        """Статус якорей для точки памяти."""
        point = self.memory_points.get(point_id)
        if not point:
            return {"error": "Point not found"}

        return {
            "point_id": point_id,
            "visual": point.visual is not None,
            "spatiotemporal": point.spatiotemporal is not None,
            "audio": point.audio is not None,
            "digital": point.digital is not None,
            "anchor_count": point.anchor_count,
            "fully_anchored": point.is_fully_anchored,
            "totems": len(point.totems)
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    system = FourAnchorsSystem()

    print("=" * 60)
    print("FOUR ANCHORS SYSTEM — Система якорей памяти")
    print("=" * 60)
    print("\n'Четыре координаты для любой точки памяти.'")

    # Создаём точку памяти
    point = system.create_memory_point("День Юноны")

    print(f"\n--- СОЗДАНА ТОЧКА ПАМЯТИ ---")
    print(f"ID: {point.point_id}")

    # Устанавливаем якоря
    print("\n--- УСТАНОВКА ЯКОРЕЙ ---")

    # 1. Визуальный
    system.set_visual_anchor(
        point.point_id,
        "https://t.me/mylifethoughts369/338",
        "Скриншот момента"
    )
    print("✓ Визуальный якорь установлен")

    # 2. Пространственно-временной
    system.set_spatiotemporal_anchor(
        point.point_id,
        latitude=55.7558,
        longitude=37.6173
    )
    print("✓ Пространственно-временной якорь установлен")

    # 3. Аудиальный
    system.set_audio_anchor(
        point.point_id,
        "I'm ready to go through hell with you",
        "Unknown Artist"
    )
    print("✓ Аудиальный якорь установлен")

    # 4. Дигитальный
    system.set_digital_anchor(
        point.point_id,
        "Это День Юноны сегодня точно",
        "Глава 06, Книга Монтана"
    )
    print("✓ Дигитальный якорь установлен")

    # Статус
    print("\n--- СТАТУС ЯКОРЕЙ ---")
    status = system.get_anchor_status(point.point_id)
    print(f"Визуальный: {'✓' if status['visual'] else '✗'}")
    print(f"Пространственно-временной: {'✓' if status['spatiotemporal'] else '✗'}")
    print(f"Аудиальный: {'✓' if status['audio'] else '✗'}")
    print(f"Дигитальный: {'✓' if status['digital'] else '✗'}")
    print(f"Полностью закреплено: {'ДА' if status['fully_anchored'] else 'НЕТ'}")

    # Тотем
    print("\n--- СОЗДАНИЕ ТОТЕМА ---")
    totem = system.create_totem(
        object_description="Красные мокасины",
        secret_detail="красный",
        owner_a="alejandro",
        owner_b="mama"
    )
    print(f"Тотем: {totem.object_description}")
    print(f"Владельцы: {totem.owner_a} ↔ {totem.owner_b}")

    # Верификация
    print("\n--- ВЕРИФИКАЦИЯ ТОТЕМА ---")
    test_answer = "красный"
    verified = totem.verify(test_answer)
    print(f"Вопрос: 'А мокасины какого у тебя цвета?'")
    print(f"Ответ: '{test_answer}'")
    print(f"Результат: {'✓ ВЕРИФИЦИРОВАНО' if verified else '✗ ПРОВАЛ'}")

    print("\n" + "=" * 60)
    print("'Парный тотем. Два человека. Одна деталь.'")
    print("=" * 60)
