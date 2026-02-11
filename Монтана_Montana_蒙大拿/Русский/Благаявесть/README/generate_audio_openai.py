#!/usr/bin/env python3
"""
Генерация живого аудио через OpenAI TTS для Клан Монтана 📕
Голос: onyx (глубокий), nova (женский), alloy (нейтральный)
Модель: tts-1-hd (высокое качество)

Использование:
  python3 generate_audio_openai.py <путь_к_файлу.md> [голос]

Голоса: onyx (по умолчанию), nova, alloy, echo, fable, shimmer

API ключ берётся из macOS Keychain (montana/OPENAI_API_KEY)
"""

import os
import re
import sys
import subprocess
import tempfile
from pathlib import Path


# === НАСТРОЙКИ ===
MODEL = "tts-1-hd"
DEFAULT_VOICE = "onyx"
MAX_CHUNK_CHARS = 4000  # OpenAI limit 4096, с запасом
RESPONSE_FORMAT = "mp3"


def get_api_key() -> str:
    """Получает OpenAI API ключ из macOS Keychain"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "montana",
             "-s", "OPENAI_API_KEY", "-w"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key

    print("✗ OPENAI_API_KEY не найден ни в keychain, ни в env")
    sys.exit(1)


def clean_text_for_audio(md_content: str) -> str:
    """Очистка markdown → чистый текст для озвучки"""

    lines = md_content.split('\n')
    audio_lines = []

    skip_patterns = [
        r'^---+$',
        r'^\*«Клан Монтана',
        r'^\*«Книга Монтана',
        r'^\*Мысль\s',
        r'^\*День\s',
        r'^\*До первого',
        r'^\*Благаявесть',
        r'^\*«Красная',
        r'^\*«Первая',
        r'^\d+\.\d+\.\d+',
        r'^Alejandro',
        r'^Алехандро',
        r'^Клод Монтана',
        r'^金元',
        r'^⾦元',
        r'^→',
        r'^#\w+',
        r'^\|',
        r'^Найдёмся\.$',
    ]

    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if any(re.match(p, stripped) for p in skip_patterns):
            continue

        if not stripped:
            continue

        # Заголовки → текст с паузой
        if line.startswith('#'):
            title = re.sub(r'^#+\s*', '', line).strip()
            title = re.sub(r'\s*`\[\d+:\d+\]`', '', title)
            if title:
                audio_lines.append(f"\n{title}.\n")
            continue

        text = stripped

        # Markdown → текст
        text = re.sub(r'\[([^\]]+?)\]\([^\)]+?\)', r'\1', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`([^`]+?)`', r'\1', text)
        text = re.sub(r'^>\s*', '', text)
        text = re.sub(r'^[-•]\s+', '', text)
        text = re.sub(r'[Ɉ]', '', text)
        text = text.replace('📕', '')
        text = re.sub(r'\s+', ' ', text).strip()

        if text:
            audio_lines.append(text)

    return '\n'.join(audio_lines)


def split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Разбивает текст на куски по границам предложений"""

    sentences = re.split(r'(?<=[.!?…»])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if not sentence.strip():
            continue

        if len(current) + len(sentence) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


def generate_chunk_audio(client, text: str, voice: str, output_path: Path) -> bool:
    """Генерирует аудио для одного куска текста"""
    try:
        response = client.audio.speech.create(
            model=MODEL,
            voice=voice,
            input=text,
            response_format=RESPONSE_FORMAT
        )
        response.stream_to_file(str(output_path))
        return True
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        return False


def concatenate_mp3(chunk_files: list[Path], output_path: Path) -> bool:
    """Склеивает mp3 файлы через ffmpeg"""
    if len(chunk_files) == 1:
        chunk_files[0].rename(output_path)
        return True

    # Создаём список файлов для ffmpeg
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for cf in chunk_files:
            f.write(f"file '{cf}'\n")
        list_file = f.name

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_file, "-c", "copy", str(output_path)],
            capture_output=True, text=True
        )
        return result.returncode == 0
    finally:
        os.unlink(list_file)
        for cf in chunk_files:
            if cf.exists():
                cf.unlink()


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 generate_audio_openai.py <файл.md> [голос]")
        print("\nГолоса: onyx (default), nova, alloy, echo, fable, shimmer")
        print("\nПример:")
        print("  python3 generate_audio_openai.py '01. Симуляция.md'")
        print("  python3 generate_audio_openai.py '01. Симуляция.md' nova")
        return

    # Путь к файлу
    arg_path = Path(sys.argv[1])
    if arg_path.is_absolute():
        input_file = arg_path
    else:
        input_file = Path.cwd() / arg_path
    input_file = input_file.resolve()

    if not input_file.exists():
        print(f"✗ Файл не найден: {input_file}")
        return

    # Голос
    voice = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_VOICE
    valid_voices = ["onyx", "nova", "alloy", "echo", "fable", "shimmer"]
    if voice not in valid_voices:
        print(f"✗ Неизвестный голос: {voice}")
        print(f"  Доступные: {', '.join(valid_voices)}")
        return

    # API ключ
    api_key = get_api_key()

    # Импорт OpenAI
    try:
        from openai import OpenAI
    except ImportError:
        print("✗ openai не установлен. Установите: pip install openai")
        return

    client = OpenAI(api_key=api_key)

    print("=" * 60)
    print("ГЕНЕРАЦИЯ ЖИВОГО АУДИО — OpenAI TTS")
    print("=" * 60)
    print(f"\nФайл: {input_file.name}")
    print(f"Модель: {MODEL}")
    print(f"Голос: {voice}")

    # Читаем и очищаем
    md_content = input_file.read_text(encoding='utf-8')
    clean_text = clean_text_for_audio(md_content)

    print(f"\nИсходный текст: {len(md_content)} символов")
    print(f"Очищенный текст: {len(clean_text)} символов")

    # Разбиваем на куски
    chunks = split_into_chunks(clean_text)
    print(f"Кусков для генерации: {len(chunks)}")

    # Оценка стоимости: $24 за 1M символов (tts-1-hd)
    total_chars = sum(len(c) for c in chunks)
    cost = total_chars / 1_000_000 * 24
    print(f"Общий объём: {total_chars} символов")
    print(f"Ориентировочная стоимость: ${cost:.3f}")

    # Оценка длительности (~150 слов/мин)
    word_count = len(clean_text.split())
    est_minutes = word_count / 150
    print(f"Слов: {word_count}")
    print(f"Ожидаемая длительность: ~{est_minutes:.1f} мин")

    print(f"\nГенерация...")

    # Генерируем куски
    chunk_files = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for i, chunk in enumerate(chunks):
            chunk_file = tmpdir / f"chunk_{i:03d}.mp3"
            print(f"  [{i+1}/{len(chunks)}] {len(chunk)} символов...", end=" ")

            if generate_chunk_audio(client, chunk, voice, chunk_file):
                chunk_files.append(chunk_file)
                size_kb = chunk_file.stat().st_size / 1024
                print(f"OK ({size_kb:.0f} KB)")
            else:
                print("ОШИБКА")
                return

        # Склеиваем
        output_file = input_file.parent / f"{input_file.stem}.mp3"
        print(f"\nСклеивание {len(chunk_files)} кусков...")

        if concatenate_mp3(chunk_files, output_file):
            size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"✓ {output_file.name} ({size_mb:.1f} MB)")

            # Длительность через ffprobe
            try:
                result = subprocess.run(
                    ['ffprobe', '-i', str(output_file), '-show_entries',
                     'format=duration', '-v', 'quiet', '-of', 'csv=p=0'],
                    capture_output=True, text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    dur = float(result.stdout.strip())
                    print(f"✓ Длительность: {dur/60:.1f} мин ({dur:.0f} сек)")
            except FileNotFoundError:
                pass

            print(f"\n{'=' * 60}")
            print("ГОТОВО")
            print(f"{'=' * 60}")
            print(f"\nАудио: {output_file}")
            print(f"\nПрослушать:")
            print(f"  afplay '{output_file}'")
        else:
            print("✗ Ошибка склеивания. Установлен ли ffmpeg?")


if __name__ == "__main__":
    main()
