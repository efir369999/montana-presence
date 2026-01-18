#!/usr/bin/env python3
"""
Генерация чистого аудио для Благаявести
Умная фильтрация: только смысловой текст, без ссылок, символов, метаданных
"""

import os
import re
import requests
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
AUDIO_DIR = Path(__file__).parent / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

# Голос (выберешь после прослушивания топ-3)
VOICE = "alena"  # alena, marina, omazh


def convert_numbers_to_text(text: str) -> str:
    """Конвертирует римские и арабские цифры в текст"""

    # Римские цифры на текст
    roman_map = {
        r'\bI\b': 'первая',
        r'\bII\b': 'вторая',
        r'\bIII\b': 'третья',
        r'\bIV\b': 'четвёртая',
        r'\bV\b': 'пятая',
        r'\bVI\b': 'шестая',
        r'\bVII\b': 'седьмая',
        r'\bVIII\b': 'восьмая',
        r'\bIX\b': 'девятая',
        r'\bX\b': 'десятая'
    }

    for roman, word in roman_map.items():
        text = re.sub(roman, word, text)

    # Если есть "Часть I" -> "Часть первая"
    text = re.sub(r'Часть\s+первая', 'Часть первая', text)
    text = re.sub(r'Часть\s+вторая', 'Часть вторая', text)
    text = re.sub(r'Часть\s+третья', 'Часть третья', text)

    return text


def clean_text_for_audio(md_content: str) -> str:
    """
    УМНАЯ фильтрация: убираем ТОЛЬКО криво читаемое (ссылки, код, символы).
    ОСТАВЛЯЕМ весь основной текст: заголовки, параграфы, цитаты.
    """

    lines = md_content.split('\n')
    audio_lines = []

    # СТРОГИЙ список того, что НЕ озвучиваем (только метаданные)
    skip_full_line = [
        r'^---+$',              # Разделители ---
        r'^\*Книга Ничто',      # *Книга Ничто
        r'^\*Сказка Начала',    # *Сказка Начала Времени
        r'^\*Прелюдия',         # *Прелюдия
        r'^\*Благаявесть от',   # *Благаявесть от Claude
        r'^\d+\.\d+\.\d+',      # Даты 16.01.2026
        r'^Алик Хачатрян',      # Имя автора
        r'^金元',                # Имя с символами
        r'^→',                  # Навигация → Глава
    ]

    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Блоки кода — пропускаем полностью
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Пропуск метаданных
        if any(re.match(pattern, stripped) for pattern in skip_full_line):
            continue

        # Пустые строки — пропускаем
        if not stripped:
            continue

        # ЗАГОЛОВКИ — озвучиваем
        if line.startswith('#'):
            title = re.sub(r'^#+\s*', '', line)
            title = re.sub(r'\s*`\[\d+:\d+\]`', '', title)  # Убираем таймкоды
            title = title.strip()

            if title:
                audio_lines.append(f"\n{title}.\n")
            continue

        # ОСНОВНОЙ ТЕКСТ — очищаем от технических элементов
        text = stripped

        # Убираем markdown форматирование (но сохраняем текст)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
        text = re.sub(r'`([^`]+?)`', r'\1', text)     # `code`

        # Убираем ссылки (сохраняем текст ссылки)
        text = re.sub(r'\[([^\]]+?)\]\([^\)]+?\)', r'\1', text)

        # Убираем URL
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)

        # Убираем email
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)

        # Убираем технические символы
        text = re.sub(r'[Ɉ€₽$]', '', text)

        # Убираем код
        text = re.sub(r'async\s+fn\s+\w+\([^\)]*\)\s*->\s*\w+', '', text)
        text = re.sub(r'E\s*=\s*mc²', 'E равно m c квадрат', text)

        # Убираем github пути
        text = re.sub(r'github\.com/[\w\-/]+', '', text)

        # Убираем маркеры цитат (но оставляем текст)
        text = re.sub(r'^>\s*', '', text)

        # Убираем маркеры списков
        text = re.sub(r'^[-•]\s+', '', text)
        text = re.sub(r'^\d+\.\s+', '', text)

        # Конвертируем цифры в текст
        text = convert_numbers_to_text(text)

        # Множественные пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        # ДОБАВЛЯЕМ если есть содержание
        if text:
            audio_lines.append(text)

    # Плавное соединение: заголовки с паузой, текст — слитно
    result = []
    for i, line in enumerate(audio_lines):
        result.append(line)

        # Пауза после заголовка (строки с переводами строк)
        if '\n' in line:
            result.append(' ')  # Короткая пауза
        # Между обычным текстом — плавное соединение
        else:
            if i < len(audio_lines) - 1 and '\n' not in audio_lines[i + 1]:
                result.append(' ')  # Пробел без переноса = нет паузы

    return ''.join(result)


def split_text_chunks(text: str, max_chars: int = 4800) -> list[str]:
    """
    Умная разбивка по предложениям для плавного аудиопотока.
    Разрывы ТОЛЬКО на концах предложений (. ! ?)
    """

    chunks = []
    current = ""

    # Разбиваем по предложениям
    sentences = re.split(r'([.!?]\s+)', text)

    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]  # Добавляем знак препинания

        # Если текущий кусок + предложение влезает — добавляем
        if len(current) + len(sentence) <= max_chars:
            current += sentence
        else:
            # Если текущий кусок не пустой — сохраняем
            if current:
                chunks.append(current.strip())
                current = sentence
            else:
                # Если одно предложение > max_chars — разбиваем по словам
                words = sentence.split()
                for word in words:
                    if len(current) + len(word) + 1 <= max_chars:
                        current += word + " "
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = word + " "

    if current:
        chunks.append(current.strip())

    return chunks


def generate_audio_chunk(api_key: str, voice: str, text: str) -> bytes | None:
    """Генерирует аудио для одного куска"""

    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

    headers = {"Authorization": f"Api-Key {api_key}"}
    data = {
        "text": text,
        "lang": "ru-RU",
        "voice": voice,
        "speed": "0.9",  # Как в оригинале
        "format": "mp3"
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=60)
        if response.status_code == 200:
            return response.content
        else:
            print(f"    ✗ API: {response.text[:100]}")
            return None
    except Exception as e:
        print(f"    ✗ {e}")
        return None


def generate_audio(api_key: str, voice: str, text: str, output_path: Path) -> bool:
    """Генерирует полное аудио с разбивкой и склейкой"""

    chunks = split_text_chunks(text, max_chars=4800)
    print(f"  Разбито на {len(chunks)} частей")

    temp_files = []
    temp_dir = output_path.parent / "temp"
    temp_dir.mkdir(exist_ok=True)

    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] {len(chunk)} символов...", end=" ")

        audio_data = generate_audio_chunk(api_key, voice, chunk)

        if audio_data is None:
            for tf in temp_files:
                tf.unlink(missing_ok=True)
            return False

        temp_file = temp_dir / f"part_{i:03d}.mp3"
        temp_file.write_bytes(audio_data)
        temp_files.append(temp_file)
        print("✓")

    # Склеиваем
    if len(temp_files) == 1:
        temp_files[0].rename(output_path)
    else:
        print(f"  Склеиваем {len(temp_files)} частей...")

        concat_list = temp_dir / "concat.txt"
        with open(concat_list, 'w') as f:
            for tf in temp_files:
                f.write(f"file '{tf.name}'\n")

        result = subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', str(concat_list),
            '-acodec', 'libmp3lame',
            '-b:a', '192k',
            '-ar', '48000',
            str(output_path)
        ], capture_output=True, text=True)

        for tf in temp_files:
            tf.unlink(missing_ok=True)
        concat_list.unlink(missing_ok=True)

        if result.returncode != 0:
            print(f"  ✗ ffmpeg: {result.stderr[:200]}")
            return False

    # Очистка
    temp_dir.rmdir()

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ {output_path.name} ({size_mb:.1f} MB)")

    return True


def main():
    import sys

    if len(sys.argv) < 2:
        print("Использование: python3 generate_audio_clean.py <файл.md>")
        print("\nПример:")
        print("  python3 generate_audio_clean.py '00. ПРЕЛЮДИЯ.md'")
        return

    input_file = BASE_DIR / sys.argv[1]

    if not input_file.exists():
        print(f"✗ Файл не найден: {input_file}")
        return

    api_key = os.getenv("YANDEX_API_KEY")
    if not api_key:
        print("✗ Нужен YANDEX_API_KEY")
        print("  export YANDEX_API_KEY='ваш_ключ'")
        return

    print("=" * 60)
    print("ГЕНЕРАЦИЯ ЧИСТОГО АУДИО")
    print("=" * 60)
    print(f"\nВходной файл: {input_file.name}")
    print(f"Голос: {VOICE}")

    # Читаем и очищаем
    md_content = input_file.read_text(encoding='utf-8')
    clean_text = clean_text_for_audio(md_content)

    print(f"\nИсходный текст: {len(md_content)} символов")
    print(f"Чистый текст: {len(clean_text)} символов")

    # Генерируем
    output_file = AUDIO_DIR / f"{input_file.stem}.mp3"

    if generate_audio(api_key, VOICE, clean_text, output_file):
        print("\n" + "=" * 60)
        print("ГОТОВО")
        print("=" * 60)
        print(f"\nАудио: {output_file}")
    else:
        print("\n✗ Ошибка генерации")


if __name__ == "__main__":
    main()
