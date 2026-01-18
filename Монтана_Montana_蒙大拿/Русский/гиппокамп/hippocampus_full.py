#!/usr/bin/env python3
"""
Внешний Гиппокамп Montana — ПОЛНАЯ РЕАЛИЗАЦИЯ
==============================================

Фаза 1: Production ✓
- Детектор новизны
- Pattern separation
- Консолидация

Фаза 2: Улучшения
- RAG интеграция (семантический поиск)
- Визуализация плотности кодирования
- Экспорт в Markdown/PDF
- Музыкальные якоря
- Геолокация

Фаза 3: Масштабирование
- Multi-user память
- Shared memories
- Cross-reference между координатами

Использование:
    python hippocampus_full.py --help
"""

import json
import hashlib
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Set
from collections import defaultdict
import argparse
import re

# Опциональные зависимости
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False


# ═══════════════════════════════════════════════════════════════════════════════
#                              МОДЕЛИ ДАННЫХ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Coordinate:
    """
    Координата в 4D пространстве памяти

    4 якоря:
    1. Дигитальный (thought) — текст мысли
    2. Временной (timestamp) — UTC метка
    3. Пространственный (location) — GPS
    4. Аудиальный (music) — музыка момента
    """
    id: str                              # Уникальный ID (hash)
    user_id: int                         # Кто
    username: str                        # @username
    timestamp: str                       # Когда (UTC ISO)
    thought: str                         # Что (текст)
    lang: str = "ru"                     # Язык

    # Дополнительные якоря
    location: Optional[str] = None       # GPS: "55.7558,37.6173"
    location_name: Optional[str] = None  # "Москва, Красная площадь"
    music_track: Optional[str] = None    # "Hans Zimmer - Time"
    music_id: Optional[str] = None       # Spotify/Shazam ID
    image_url: Optional[str] = None      # Визуальный якорь

    # Метаданные
    tags: List[str] = field(default_factory=list)           # #теги
    references: List[str] = field(default_factory=list)     # Ссылки на другие координаты
    shared_with: List[int] = field(default_factory=list)    # Расшарено с user_ids
    is_public: bool = False                                  # Публичная память

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Генерация уникального ID на основе содержимого"""
        content = f"{self.user_id}:{self.timestamp}:{self.thought}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Coordinate':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserMemory:
    """Профиль памяти пользователя"""
    user_id: int
    username: str
    total_thoughts: int = 0
    first_thought: Optional[str] = None
    last_thought: Optional[str] = None
    density_per_day: float = 0.0
    top_tags: List[str] = field(default_factory=list)
    connected_users: List[int] = field(default_factory=list)  # Через shared memories


# ═══════════════════════════════════════════════════════════════════════════════
#                              ВНЕШНИЙ ГИППОКАМП
# ═══════════════════════════════════════════════════════════════════════════════

class ExternalHippocampus:
    """
    Внешний Гиппокамп Montana — Полная реализация

    Эмулирует биологическую память с критическим улучшением:
    ПЕРЕЖИВАЕТ СМЕРТЬ НОСИТЕЛЯ
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Файлы данных
        self.stream_file = self.data_dir / "stream.jsonl"
        self.index_file = self.data_dir / "index.json"
        self.users_file = self.data_dir / "users.json"
        self.shared_file = self.data_dir / "shared.jsonl"
        self.references_file = self.data_dir / "references.json"

        # RAG (если доступен)
        self.chroma_client = None
        self.collection = None
        self.embedder = None
        if HAS_CHROMADB:
            self._init_rag()

        # Кэши
        self._index_cache: Dict[str, Coordinate] = {}
        self._user_cache: Dict[int, UserMemory] = {}
        self._references_cache: Dict[str, Set[str]] = defaultdict(set)

        # Загружаем индексы
        self._load_index()
        self._load_references()

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 1: ЯДРО
    # ═══════════════════════════════════════════════════════════════════════════

    def is_raw_thought(self, text: str) -> bool:
        """
        Детектор новизны — определяет мысль vs вопрос/команда
        """
        text = text.strip()

        if len(text) > 500 or len(text) < 5:
            return False

        if text.endswith("?"):
            return False

        # Вопросительные слова
        question_words = [
            'что', 'как', 'почему', 'зачем', 'когда', 'где', 'кто',
            'what', 'how', 'why', 'when', 'where', 'who',
            '什么', '怎么', '为什么', '何时', '哪里', '谁'
        ]

        # Команды
        commands = [
            'покажи', 'расскажи', 'объясни', 'помоги', 'найди',
            'show', 'tell', 'explain', 'help', 'find',
            '/start', '/help', '/stream', '/export', '/search'
        ]

        text_lower = text.lower()
        first_word = text_lower.split()[0] if text_lower.split() else ""

        if first_word in question_words or first_word in commands:
            return False

        return True

    def save(
        self,
        user_id: int,
        username: str,
        thought: str,
        lang: str = "ru",
        location: Optional[str] = None,
        location_name: Optional[str] = None,
        music_track: Optional[str] = None,
        music_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = False
    ) -> Coordinate:
        """
        Pattern Separation — сохранить мысль как координату
        """
        # Автоизвлечение тегов
        if tags is None:
            tags = self._extract_tags(thought)

        # Создаём координату
        coord = Coordinate(
            id="",  # Будет сгенерирован
            user_id=user_id,
            username=username,
            timestamp=datetime.utcnow().isoformat() + "Z",
            thought=thought,
            lang=lang,
            location=location,
            location_name=location_name,
            music_track=music_track,
            music_id=music_id,
            tags=tags,
            is_public=is_public
        )

        # Автоматический cross-reference
        refs = self._find_references(coord)
        coord.references = refs

        # Сохраняем в stream (append-only)
        with open(self.stream_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(coord.to_dict(), ensure_ascii=False) + "\n")

        # Обновляем индекс
        self._index_cache[coord.id] = coord
        self._save_index()

        # Обновляем references
        for ref_id in refs:
            self._references_cache[ref_id].add(coord.id)
        self._save_references()

        # Добавляем в RAG
        if self.collection:
            self._add_to_rag(coord)

        return coord

    def get(self, coord_id: str) -> Optional[Coordinate]:
        """Получить координату по ID"""
        return self._index_cache.get(coord_id)

    def get_user_stream(self, user_id: int, limit: int = 100) -> List[Coordinate]:
        """Получить мысли пользователя"""
        coords = [c for c in self._index_cache.values() if c.user_id == user_id]
        coords.sort(key=lambda x: x.timestamp)
        return coords[-limit:]

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 2: RAG ПОИСК
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_rag(self):
        """Инициализация RAG системы"""
        try:
            self.chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.data_dir / "chroma"),
                anonymized_telemetry=False
            ))
            self.collection = self.chroma_client.get_or_create_collection(
                name="hippocampus",
                metadata={"hnsw:space": "cosine"}
            )

            if HAS_EMBEDDINGS:
                self.embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        except Exception as e:
            print(f"RAG init failed: {e}")
            self.collection = None

    def _add_to_rag(self, coord: Coordinate):
        """Добавить координату в RAG"""
        if not self.collection:
            return

        try:
            # Создаём embedding
            if self.embedder:
                embedding = self.embedder.encode(coord.thought).tolist()
                self.collection.add(
                    ids=[coord.id],
                    embeddings=[embedding],
                    documents=[coord.thought],
                    metadatas=[{
                        "user_id": coord.user_id,
                        "timestamp": coord.timestamp,
                        "tags": ",".join(coord.tags)
                    }]
                )
            else:
                # Без embeddings — просто документы
                self.collection.add(
                    ids=[coord.id],
                    documents=[coord.thought],
                    metadatas=[{
                        "user_id": coord.user_id,
                        "timestamp": coord.timestamp,
                        "tags": ",".join(coord.tags)
                    }]
                )
        except Exception as e:
            print(f"RAG add failed: {e}")

    def search(
        self,
        query: str,
        user_id: Optional[int] = None,
        limit: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Coordinate]:
        """
        Семантический поиск по памяти
        """
        # Пробуем RAG поиск
        if self.collection and self.embedder:
            try:
                where_filter = {}
                if user_id:
                    where_filter["user_id"] = user_id

                query_embedding = self.embedder.encode(query).tolist()
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where=where_filter if where_filter else None
                )

                coord_ids = results['ids'][0] if results['ids'] else []
                coords = [self._index_cache[cid] for cid in coord_ids if cid in self._index_cache]

                # Дополнительная фильтрация
                if from_date:
                    coords = [c for c in coords if c.timestamp[:10] >= from_date]
                if to_date:
                    coords = [c for c in coords if c.timestamp[:10] <= to_date]
                if tags:
                    coords = [c for c in coords if any(t in c.tags for t in tags)]

                return coords
            except Exception as e:
                print(f"RAG search failed: {e}")

        # Fallback: простой текстовый поиск
        return self._simple_search(query, user_id, limit, from_date, to_date, tags)

    def _simple_search(
        self,
        query: str,
        user_id: Optional[int] = None,
        limit: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Coordinate]:
        """Простой текстовый поиск"""
        query_lower = query.lower()
        results = []

        for coord in self._index_cache.values():
            if user_id and coord.user_id != user_id:
                continue
            if from_date and coord.timestamp[:10] < from_date:
                continue
            if to_date and coord.timestamp[:10] > to_date:
                continue
            if tags and not any(t in coord.tags for t in tags):
                continue

            if query_lower in coord.thought.lower():
                results.append(coord)

        return results[:limit]

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 2: ВИЗУАЛИЗАЦИЯ
    # ═══════════════════════════════════════════════════════════════════════════

    def plot_density(
        self,
        user_id: Optional[int] = None,
        period: str = "month",
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Визуализация плотности кодирования памяти

        Args:
            user_id: Фильтр по пользователю
            period: day, week, month, year, all
            output_path: Путь для сохранения PNG
        """
        if not HAS_MATPLOTLIB:
            return "matplotlib не установлен. pip install matplotlib"

        coords = list(self._index_cache.values())
        if user_id:
            coords = [c for c in coords if c.user_id == user_id]

        if not coords:
            return "Нет данных для визуализации"

        # Группируем по дням
        daily_counts = defaultdict(int)
        for coord in coords:
            date = coord.timestamp[:10]
            daily_counts[date] += 1

        # Сортируем
        dates = sorted(daily_counts.keys())
        counts = [daily_counts[d] for d in dates]

        # Фильтруем по периоду
        now = datetime.now()
        if period == "week":
            cutoff = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        elif period == "month":
            cutoff = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        elif period == "year":
            cutoff = (now - timedelta(days=365)).strftime('%Y-%m-%d')
        else:
            cutoff = "1970-01-01"

        filtered_dates = [d for d in dates if d >= cutoff]
        filtered_counts = [daily_counts[d] for d in filtered_dates]

        if not filtered_dates:
            return "Нет данных за выбранный период"

        # Строим график
        fig, ax = plt.subplots(figsize=(12, 6))

        x_dates = [datetime.strptime(d, '%Y-%m-%d') for d in filtered_dates]
        ax.bar(x_dates, filtered_counts, color='#4A90D9', alpha=0.8)
        ax.plot(x_dates, filtered_counts, color='#2C5282', linewidth=2, marker='o', markersize=4)

        ax.set_xlabel('Дата', fontsize=12)
        ax.set_ylabel('Количество мыслей', fontsize=12)
        ax.set_title(f'Плотность кодирования памяти Montana\nПериод: {period}', fontsize=14)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)

        # Добавляем статистику
        total = sum(filtered_counts)
        avg = total / len(filtered_counts) if filtered_counts else 0
        max_val = max(filtered_counts) if filtered_counts else 0

        stats_text = f'Всего: {total} | Среднее: {avg:.1f}/день | Макс: {max_val}'
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

        # Сохраняем или показываем
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            return output_path
        else:
            output_path = self.data_dir / f"density_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            return str(output_path)

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 2: ЭКСПОРТ
    # ═══════════════════════════════════════════════════════════════════════════

    def export_markdown(
        self,
        user_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        include_metadata: bool = True
    ) -> str:
        """Экспорт в Markdown"""
        coords = self._filter_coords(user_id, from_date, to_date)

        if not coords:
            return "# Поток мыслей Montana\n\nПусто."

        username = coords[0].username if coords else "unknown"

        lines = [
            f"# Поток мыслей @{username}",
            "",
            f"**Всего мыслей:** {len(coords)}",
            f"**Период:** {coords[0].timestamp[:10]} — {coords[-1].timestamp[:10]}",
            "",
            "---",
            ""
        ]

        current_date = None
        for coord in coords:
            date = coord.timestamp[:10]
            time = coord.timestamp[11:16]

            if date != current_date:
                current_date = date
                lines.append(f"## {date}")
                lines.append("")

            lines.append(f"### [{time}] {coord.thought[:50]}...")
            lines.append("")
            lines.append(f"> {coord.thought}")
            lines.append("")

            if include_metadata:
                if coord.tags:
                    lines.append(f"**Теги:** {', '.join(coord.tags)}")
                if coord.location_name:
                    lines.append(f"**Место:** {coord.location_name}")
                if coord.music_track:
                    lines.append(f"**Музыка:** {coord.music_track}")
                if coord.references:
                    lines.append(f"**Связи:** {len(coord.references)} координат")
                lines.append("")

        lines.extend([
            "---",
            "",
            f"*Экспорт: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            "金元Ɉ Montana — Внешний гиппокамп"
        ])

        return "\n".join(lines)

    def export_pdf(
        self,
        user_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """Экспорт в PDF"""
        if not HAS_FPDF:
            return None

        coords = self._filter_coords(user_id, from_date, to_date)
        if not coords:
            return None

        username = coords[0].username if coords else "unknown"

        pdf = FPDF()
        pdf.add_page()

        # Заголовок
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f'Поток мыслей @{username}', ln=True, align='C')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, f'Всего: {len(coords)} мыслей', ln=True, align='C')
        pdf.ln(10)

        # Мысли
        pdf.set_font('Arial', '', 11)
        current_date = None

        for coord in coords:
            date = coord.timestamp[:10]
            time = coord.timestamp[11:16]

            if date != current_date:
                current_date = date
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, date, ln=True)
                pdf.set_font('Arial', '', 11)

            # Используем ASCII-совместимый текст
            thought_ascii = coord.thought.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 8, f"[{time}] {thought_ascii}")
            pdf.ln(2)

        # Сохраняем
        if not output_path:
            output_path = self.data_dir / f"thoughts_{username}_{datetime.now().strftime('%Y%m%d')}.pdf"

        pdf.output(str(output_path))
        return str(output_path)

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 2: МУЗЫКАЛЬНЫЕ ЯКОРЯ
    # ═══════════════════════════════════════════════════════════════════════════

    def add_music_anchor(
        self,
        coord_id: str,
        track_name: str,
        track_id: Optional[str] = None,
        source: str = "manual"  # manual, spotify, shazam
    ) -> bool:
        """
        Добавить музыкальный якорь к координатемузыкальный якорь к координате

        Музыка = машина времени. Каждый повтор трека = телепорт назад.
        """
        coord = self._index_cache.get(coord_id)
        if not coord:
            return False

        coord.music_track = track_name
        coord.music_id = track_id

        self._save_index()
        return True

    def get_by_music(self, track_name: str) -> List[Coordinate]:
        """Найти все координаты с определённым треком"""
        track_lower = track_name.lower()
        return [
            c for c in self._index_cache.values()
            if c.music_track and track_lower in c.music_track.lower()
        ]

    def get_soundtrack(self, user_id: int) -> List[Dict]:
        """Получить саундтрек пользователя — все треки из памяти"""
        coords = [c for c in self._index_cache.values() if c.user_id == user_id and c.music_track]

        # Группируем по трекам
        tracks = defaultdict(list)
        for coord in coords:
            tracks[coord.music_track].append(coord.timestamp)

        # Сортируем по частоте
        result = []
        for track, timestamps in sorted(tracks.items(), key=lambda x: -len(x[1])):
            result.append({
                "track": track,
                "count": len(timestamps),
                "first": min(timestamps),
                "last": max(timestamps)
            })

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 2: ГЕОЛОКАЦИЯ
    # ═══════════════════════════════════════════════════════════════════════════

    def add_location(
        self,
        coord_id: str,
        lat: float,
        lon: float,
        name: Optional[str] = None
    ) -> bool:
        """Добавить геолокацию к координате"""
        coord = self._index_cache.get(coord_id)
        if not coord:
            return False

        coord.location = f"{lat},{lon}"
        coord.location_name = name

        self._save_index()
        return True

    def get_by_location(
        self,
        lat: float,
        lon: float,
        radius_km: float = 1.0
    ) -> List[Coordinate]:
        """Найти координаты рядом с местом"""
        results = []

        for coord in self._index_cache.values():
            if not coord.location:
                continue

            try:
                c_lat, c_lon = map(float, coord.location.split(','))
                dist = self._haversine(lat, lon, c_lat, c_lon)
                if dist <= radius_km:
                    results.append(coord)
            except:
                continue

        return results

    def get_places(self, user_id: int) -> List[Dict]:
        """Получить все места пользователя"""
        coords = [c for c in self._index_cache.values() if c.user_id == user_id and c.location_name]

        places = defaultdict(list)
        for coord in coords:
            places[coord.location_name].append(coord.timestamp)

        result = []
        for place, timestamps in sorted(places.items(), key=lambda x: -len(x[1])):
            result.append({
                "place": place,
                "count": len(timestamps),
                "first": min(timestamps),
                "last": max(timestamps)
            })

        return result

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Расстояние между точками в км"""
        from math import radians, cos, sin, asin, sqrt

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Радиус Земли в км

        return c * r

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 3: MULTI-USER
    # ═══════════════════════════════════════════════════════════════════════════

    def get_all_users(self) -> List[UserMemory]:
        """Получить всех пользователей с их статистикой"""
        user_coords = defaultdict(list)

        for coord in self._index_cache.values():
            user_coords[coord.user_id].append(coord)

        users = []
        for user_id, coords in user_coords.items():
            coords.sort(key=lambda x: x.timestamp)

            # Собираем теги
            all_tags = []
            for c in coords:
                all_tags.extend(c.tags)
            tag_counts = defaultdict(int)
            for tag in all_tags:
                tag_counts[tag] += 1
            top_tags = sorted(tag_counts.keys(), key=lambda x: -tag_counts[x])[:5]

            # Плотность
            if len(coords) >= 2:
                first = datetime.fromisoformat(coords[0].timestamp.replace("Z", ""))
                last = datetime.fromisoformat(coords[-1].timestamp.replace("Z", ""))
                days = max(1, (last - first).days)
                density = len(coords) / days
            else:
                density = len(coords)

            # Связанные пользователи
            connected = set()
            for c in coords:
                connected.update(c.shared_with)

            users.append(UserMemory(
                user_id=user_id,
                username=coords[0].username if coords else "unknown",
                total_thoughts=len(coords),
                first_thought=coords[0].timestamp if coords else None,
                last_thought=coords[-1].timestamp if coords else None,
                density_per_day=round(density, 2),
                top_tags=top_tags,
                connected_users=list(connected)
            ))

        return users

    def get_global_stats(self) -> Dict:
        """Глобальная статистика гиппокампа"""
        coords = list(self._index_cache.values())

        if not coords:
            return {"total": 0}

        users = set(c.user_id for c in coords)
        tags = defaultdict(int)
        for c in coords:
            for tag in c.tags:
                tags[tag] += 1

        return {
            "total_coordinates": len(coords),
            "total_users": len(users),
            "total_shared": len([c for c in coords if c.shared_with]),
            "total_public": len([c for c in coords if c.is_public]),
            "top_tags": sorted(tags.items(), key=lambda x: -x[1])[:10],
            "first_memory": min(c.timestamp for c in coords),
            "last_memory": max(c.timestamp for c in coords)
        }

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 3: SHARED MEMORIES
    # ═══════════════════════════════════════════════════════════════════════════

    def share(self, coord_id: str, with_user_id: int) -> bool:
        """Поделиться координатой с другим пользователем"""
        coord = self._index_cache.get(coord_id)
        if not coord:
            return False

        if with_user_id not in coord.shared_with:
            coord.shared_with.append(with_user_id)
            self._save_index()

            # Записываем в shared log
            share_entry = {
                "coord_id": coord_id,
                "from_user": coord.user_id,
                "to_user": with_user_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            with open(self.shared_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(share_entry, ensure_ascii=False) + "\n")

        return True

    def make_public(self, coord_id: str) -> bool:
        """Сделать координату публичной"""
        coord = self._index_cache.get(coord_id)
        if not coord:
            return False

        coord.is_public = True
        self._save_index()
        return True

    def get_shared_with_me(self, user_id: int) -> List[Coordinate]:
        """Получить координаты, которыми поделились со мной"""
        return [
            c for c in self._index_cache.values()
            if user_id in c.shared_with
        ]

    def get_public_stream(self, limit: int = 100) -> List[Coordinate]:
        """Получить публичный поток"""
        public = [c for c in self._index_cache.values() if c.is_public]
        public.sort(key=lambda x: x.timestamp, reverse=True)
        return public[:limit]

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ФАЗА 3: CROSS-REFERENCE
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_tags(self, text: str) -> List[str]:
        """Извлечь теги из текста"""
        # #теги
        hashtags = re.findall(r'#(\w+)', text)

        # Ключевые слова Montana
        keywords = ['время', 'память', 'монтана', 'юнона', 'гиппокамп', 'координата',
                   'time', 'memory', 'montana', 'juno', 'hippocampus', 'coordinate']

        text_lower = text.lower()
        found_keywords = [kw for kw in keywords if kw in text_lower]

        return list(set(hashtags + found_keywords))

    def _find_references(self, coord: Coordinate) -> List[str]:
        """Найти связанные координаты"""
        references = []

        # По тегам
        if coord.tags:
            for other in self._index_cache.values():
                if other.id == coord.id:
                    continue
                if any(tag in other.tags for tag in coord.tags):
                    references.append(other.id)

        # По похожести текста (простая эвристика)
        words = set(coord.thought.lower().split())
        if len(words) >= 3:
            for other in self._index_cache.values():
                if other.id == coord.id:
                    continue
                other_words = set(other.thought.lower().split())
                common = words & other_words
                if len(common) >= 3:
                    if other.id not in references:
                        references.append(other.id)

        return references[:10]  # Максимум 10 связей

    def link(self, coord_id_1: str, coord_id_2: str) -> bool:
        """Создать связь между координатами вручную"""
        coord1 = self._index_cache.get(coord_id_1)
        coord2 = self._index_cache.get(coord_id_2)

        if not coord1 or not coord2:
            return False

        if coord_id_2 not in coord1.references:
            coord1.references.append(coord_id_2)
        if coord_id_1 not in coord2.references:
            coord2.references.append(coord_id_1)

        self._references_cache[coord_id_1].add(coord_id_2)
        self._references_cache[coord_id_2].add(coord_id_1)

        self._save_index()
        self._save_references()
        return True

    def get_related(self, coord_id: str, depth: int = 1) -> List[Coordinate]:
        """Получить связанные координаты (с глубиной)"""
        coord = self._index_cache.get(coord_id)
        if not coord:
            return []

        visited = {coord_id}
        current_level = set(coord.references)
        all_related = []

        for _ in range(depth):
            next_level = set()
            for ref_id in current_level:
                if ref_id in visited:
                    continue
                visited.add(ref_id)

                ref_coord = self._index_cache.get(ref_id)
                if ref_coord:
                    all_related.append(ref_coord)
                    next_level.update(ref_coord.references)

            current_level = next_level

        return all_related

    def get_graph(self, user_id: Optional[int] = None) -> Dict:
        """Получить граф связей для визуализации"""
        coords = list(self._index_cache.values())
        if user_id:
            coords = [c for c in coords if c.user_id == user_id]

        nodes = []
        edges = []

        for coord in coords:
            nodes.append({
                "id": coord.id,
                "label": coord.thought[:30] + "...",
                "timestamp": coord.timestamp,
                "tags": coord.tags
            })

            for ref_id in coord.references:
                if ref_id in self._index_cache:
                    edges.append({
                        "from": coord.id,
                        "to": ref_id
                    })

        return {"nodes": nodes, "edges": edges}

    # ═══════════════════════════════════════════════════════════════════════════
    #                              ВСПОМОГАТЕЛЬНЫЕ
    # ═══════════════════════════════════════════════════════════════════════════

    def _filter_coords(
        self,
        user_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Coordinate]:
        """Фильтрация координат"""
        coords = list(self._index_cache.values())

        if user_id:
            coords = [c for c in coords if c.user_id == user_id]
        if from_date:
            coords = [c for c in coords if c.timestamp[:10] >= from_date]
        if to_date:
            coords = [c for c in coords if c.timestamp[:10] <= to_date]

        coords.sort(key=lambda x: x.timestamp)
        return coords

    def _load_index(self):
        """Загрузить индекс из файла"""
        if self.stream_file.exists():
            with open(self.stream_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            coord = Coordinate.from_dict(data)
                            self._index_cache[coord.id] = coord
                        except:
                            continue

    def _save_index(self):
        """Сохранить индекс (перезаписать stream)"""
        with open(self.stream_file, "w", encoding="utf-8") as f:
            for coord in sorted(self._index_cache.values(), key=lambda x: x.timestamp):
                f.write(json.dumps(coord.to_dict(), ensure_ascii=False) + "\n")

    def _load_references(self):
        """Загрузить граф связей"""
        if self.references_file.exists():
            try:
                with open(self.references_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._references_cache[k] = set(v)
            except:
                pass

    def _save_references(self):
        """Сохранить граф связей"""
        data = {k: list(v) for k, v in self._references_cache.items()}
        with open(self.references_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Внешний Гиппокамп Montana — Полная реализация",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Команды')

    # search
    search_parser = subparsers.add_parser('search', help='Поиск по памяти')
    search_parser.add_argument('query', help='Поисковый запрос')
    search_parser.add_argument('--user', type=int, help='Фильтр по user_id')
    search_parser.add_argument('--limit', type=int, default=10)

    # export
    export_parser = subparsers.add_parser('export', help='Экспорт в Markdown')
    export_parser.add_argument('--user', type=int, help='Фильтр по user_id')
    export_parser.add_argument('--from', dest='from_date', help='С даты')
    export_parser.add_argument('--to', dest='to_date', help='По дату')
    export_parser.add_argument('--output', '-o', help='Файл для сохранения')

    # plot
    plot_parser = subparsers.add_parser('plot', help='Визуализация плотности')
    plot_parser.add_argument('--user', type=int, help='Фильтр по user_id')
    plot_parser.add_argument('--period', default='month', choices=['day', 'week', 'month', 'year', 'all'])
    plot_parser.add_argument('--output', '-o', help='Файл PNG')

    # stats
    subparsers.add_parser('stats', help='Глобальная статистика')

    # users
    subparsers.add_parser('users', help='Список пользователей')

    # graph
    graph_parser = subparsers.add_parser('graph', help='Граф связей (JSON)')
    graph_parser.add_argument('--user', type=int)

    args = parser.parse_args()

    hip = ExternalHippocampus()

    if args.command == 'search':
        results = hip.search(args.query, user_id=args.user, limit=args.limit)
        print(f"Ɉ Найдено: {len(results)} координат\n")
        for coord in results:
            print(f"[{coord.timestamp[:16]}] {coord.thought[:60]}...")
            if coord.tags:
                print(f"  Теги: {', '.join(coord.tags)}")
            print()

    elif args.command == 'export':
        md = hip.export_markdown(
            user_id=args.user,
            from_date=args.from_date,
            to_date=args.to_date
        )
        if args.output:
            Path(args.output).write_text(md, encoding='utf-8')
            print(f"✓ Сохранено в {args.output}")
        else:
            print(md)

    elif args.command == 'plot':
        result = hip.plot_density(
            user_id=args.user,
            period=args.period,
            output_path=args.output
        )
        print(f"✓ График: {result}")

    elif args.command == 'stats':
        stats = hip.get_global_stats()
        print("Ɉ Статистика Внешнего Гиппокампа")
        print()
        print(f"  Всего координат:    {stats.get('total_coordinates', 0)}")
        print(f"  Пользователей:      {stats.get('total_users', 0)}")
        print(f"  Shared:             {stats.get('total_shared', 0)}")
        print(f"  Public:             {stats.get('total_public', 0)}")
        print()
        if stats.get('top_tags'):
            print("  Топ теги:")
            for tag, count in stats['top_tags'][:5]:
                print(f"    #{tag}: {count}")

    elif args.command == 'users':
        users = hip.get_all_users()
        print(f"Ɉ Пользователи ({len(users)})\n")
        for user in users:
            print(f"  @{user.username} (ID: {user.user_id})")
            print(f"    Мыслей: {user.total_thoughts}")
            print(f"    Плотность: {user.density_per_day}/день")
            if user.top_tags:
                print(f"    Теги: {', '.join(user.top_tags)}")
            print()

    elif args.command == 'graph':
        graph = hip.get_graph(user_id=args.user)
        print(json.dumps(graph, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
