#!/usr/bin/env python3
"""
Edge TTS для Благаявесть (Русский)
Бесплатный Microsoft Edge TTS - конвертирует .md в .mp3

СТАНДАРТНЫЙ ГОЛОС: ru-RU-SvetlanaNeural
"""

import asyncio
import re
import edge_tts
from pathlib import Path

# Русский голос - ЕДИНСТВЕННЫЙ СТАНДАРТ
VOICE = "ru-RU-SvetlanaNeural"

BASE_DIR = Path(__file__).parent


def clean_markdown(text: str) -> str:
    """Убирает markdown разметку"""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def convert_file(md_path: Path):
    """Конвертирует .md в .mp3"""
    print(f"\n📖 {md_path.name}")

    mp3_path = md_path.with_suffix(".mp3")
    if mp3_path.exists() and mp3_path.stat().st_size > 0:
        print(f"   ⏭️  Уже есть: {mp3_path.name}")
        return

    text = md_path.read_text(encoding="utf-8")
    text = clean_markdown(text)
    print(f"   📝 {len(text)} символов")

    print(f"   🔊 Генерирую аудио...", end=" ", flush=True)

    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(mp3_path))

    size_mb = mp3_path.stat().st_size / (1024 * 1024)
    print(f"✓ ({size_mb:.1f} MB)")


async def main():
    files_to_convert = [
        # Прелюдия
        BASE_DIR / "00. ПРЕЛЮДИЯ.md",
        # Сказка Начала Времени
        BASE_DIR / "Сказка Начала Времени" / "Глава I. День Юноны.md",
        BASE_DIR / "Сказка Начала Времени" / "Глава II. Печать Времени.md",
        BASE_DIR / "Сказка Начала Времени" / "Глава III. Пять Узлов.md",
        BASE_DIR / "Сказка Начала Времени" / "Глава IV. Комедия.md",
        BASE_DIR / "Сказка Начала Времени" / "Глава V. Порядок.md",
        # Первый Акт
        BASE_DIR / "Первый Акт" / "Глава I. Симуляция.md",
        # Второй Акт
        BASE_DIR / "Второй Акт" / "Глава I. Унижение.md",
        BASE_DIR / "Второй Акт" / "Глава II. Поток.md",
        BASE_DIR / "Второй Акт" / "Глава III. Следы.md",
        BASE_DIR / "Второй Акт" / "Глава IV. Тревоги.md",
    ]

    print("🎙️  Edge TTS (бесплатный)")
    print(f"   Голос: {VOICE} (стандарт)")

    for md_file in files_to_convert:
        if md_file.exists():
            await convert_file(md_file)
        else:
            print(f"\n⚠️  Не найден: {md_file}")

    print("\n🏁 Готово!")


if __name__ == "__main__":
    asyncio.run(main())
