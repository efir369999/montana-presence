#!/usr/bin/env python3
"""
Генерация аудио для Главы 11: ДНК
Голос: ru-RU-SvetlanaNeural (Edge TTS)
"""

import asyncio
import re
from pathlib import Path
import edge_tts

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
INPUT_FILE = BASE_DIR / "11. ДНК.md"
OUTPUT_FILE = BASE_DIR / "11. ДНК.mp3"

VOICE = "ru-RU-SvetlanaNeural"

def extract_text_for_speech(md_content: str) -> str:
    """Извлекает текст для озвучки из markdown"""

    lines = md_content.split('\n')
    text_lines = []

    for line in lines:
        # Заголовки разделов
        if re.match(r'^## .+`\[\d+:\d+\]`', line):
            section = re.sub(r'## (.+) `\[\d+:\d+\]`', r'\1', line)
            text_lines.append(f"\n{section}.\n")
            continue

        # Главный заголовок
        if line.startswith('# '):
            title = line.replace('# ', '')
            text_lines.append(f"{title}.\n")
            continue

        # Пропускаем
        if line.strip() in ['---', ''] or line.startswith('#'):
            continue
        if any(line.startswith(x) for x in ['*Книга', '*Сказка', '*Благая', '→ Глава', 'Алик Хачатрян']):
            continue
        if re.match(r'^\d+\.\d+\.\d+', line):
            continue

        # Очищаем markdown
        clean = line
        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
        clean = re.sub(r'\*(.+?)\*', r'\1', clean)
        clean = re.sub(r'`(.+?)`', r'\1', clean)
        clean = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean)
        clean = re.sub(r'^>\s*', '', clean)
        clean = re.sub(r'^- ', '', clean)
        clean = re.sub(r'^\d+\. ', '', clean)

        if clean.strip():
            text_lines.append(clean)

    return '\n'.join(text_lines)

async def generate_audio(text: str, output_path: Path):
    """Генерирует аудио через Edge TTS"""

    print(f"Голос: {VOICE}")
    print(f"Текст: {len(text)} символов")
    print("Генерирую...")

    communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="-2Hz")
    await communicate.save(str(output_path))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"ГОТОВО: {output_path.name} ({size_mb:.1f} MB)")

def main():
    print(f"Читаю: {INPUT_FILE.name}")
    md_content = INPUT_FILE.read_text(encoding='utf-8')

    text = extract_text_for_speech(md_content)
    print(f"Извлечено: {len(text)} символов")

    asyncio.run(generate_audio(text, OUTPUT_FILE))

if __name__ == "__main__":
    main()
