#!/usr/bin/env python3
"""
Генерация аудио с умной фильтрацией для Благаявести
Голос: Svetlana (Microsoft edge-tts - бесплатный)
Умная обработка: римские числа → текст, ссылки → описание, единый поток
"""

import os
import re
import asyncio
import edge_tts
from pathlib import Path

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"
AUDIO_DIR = Path(__file__).parent / "audio_smart"
AUDIO_DIR.mkdir(exist_ok=True)

# Голос Microsoft Svetlana (бесплатный)
VOICE = "ru-RU-SvetlanaNeural"
# Настройки: скорость немного медленнее для вдумчивого чтения
RATE = "-5%"  # Чуть медленнее обычного для философского текста
PITCH = "+0Hz"  # Нормальная высота


def convert_roman_to_text(text: str) -> str:
    """Конвертирует римские цифры в текст (Часть I → Часть первая, I. → убирает)"""

    # Маппинг римских цифр (в порядке от длинных к коротким для правильной замены)
    roman_map = {
        'XII': 'двенадцатая',
        'XI': 'одиннадцатая',
        'VIII': 'восьмая',
        'VII': 'седьмая',
        'VI': 'шестая',
        'IV': 'четвёртая',
        'IX': 'девятая',
        'III': 'третья',
        'II': 'вторая',
        'V': 'пятая',
        'X': 'десятая',
        'I': 'первая'
    }

    # Сначала убираем римские цифры из заголовков типа "I. Название" → "Название"
    # (это подразделы, не нужно озвучивать их нумерацию)
    for roman in roman_map.keys():
        # Паттерн: римская цифра с точкой в начале или после пробелов
        text = re.sub(rf'^\s*{roman}\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(rf'\n\s*{roman}\.\s+', '\n', text)

    # Затем заменяем в контексте "Часть X", "Глава X", "Акт X" и т.д.
    for roman, word in roman_map.items():
        # С заглавной буквы (Часть I → Часть первая, Глава I → Глава первая)
        text = re.sub(rf'\b(Часть|Глава|Акт|День)\s+{roman}\b',
                     rf'\1 {word}', text, flags=re.IGNORECASE)

    return text


def convert_numbers_to_text_smart(text: str) -> str:
    """Умная конвертация цифр в текст там, где это улучшает чтение"""

    # Даты: 9 января 2026 → девятого января две тысячи двадцать шестого года
    date_pattern = r'(\d+)\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})'

    def replace_date(match):
        day, month, year = match.groups()
        day_text = num_to_ordinal(int(day))
        year_text = year_to_text(int(year))
        return f"{day_text} {month} {year_text} года"

    text = re.sub(date_pattern, replace_date, text)

    # Годы отдельно (2026 → две тысячи двадцать шестой)
    year_pattern = r'\b(20\d{2})\b'
    text = re.sub(year_pattern, lambda m: year_to_text(int(m.group(1))), text)

    # Маленькие числа в тексте (1-20) → текст
    small_num_pattern = r'\b(\d{1,2})\b'

    def replace_small_num(match):
        num = int(match.group(1))
        if 1 <= num <= 20:
            return num_to_text(num)
        return match.group(0)

    text = re.sub(small_num_pattern, replace_small_num, text)

    return text


def num_to_text(num: int) -> str:
    """Конвертирует число в текст (1 → один)"""
    nums = {
        1: 'один', 2: 'два', 3: 'три', 4: 'четыре', 5: 'пять',
        6: 'шесть', 7: 'семь', 8: 'восемь', 9: 'девять', 10: 'десять',
        11: 'одиннадцать', 12: 'двенадцать', 13: 'тринадцать', 14: 'четырнадцать',
        15: 'пятнадцать', 16: 'шестнадцать', 17: 'семнадцать', 18: 'восемнадцать',
        19: 'девятнадцать', 20: 'двадцать'
    }
    return nums.get(num, str(num))


def num_to_ordinal(num: int) -> str:
    """Конвертирует число в порядковое (1 → первого)"""
    ordinals = {
        1: 'первого', 2: 'второго', 3: 'третьего', 4: 'четвёртого', 5: 'пятого',
        6: 'шестого', 7: 'седьмого', 8: 'восьмого', 9: 'девятого', 10: 'десятого',
        11: 'одиннадцатого', 12: 'двенадцатого', 13: 'тринадцатого', 14: 'четырнадцатого',
        15: 'пятнадцатого', 16: 'шестнадцатого', 17: 'семнадцатого', 18: 'восемнадцатого',
        19: 'девятнадцатого', 20: 'двадцатого', 21: 'двадцать первого',
        31: 'тридцать первого'
    }
    return ordinals.get(num, str(num))


def year_to_text(year: int) -> str:
    """Конвертирует год в текст (2026 → две тысячи двадцать шестой)"""
    if 2000 <= year <= 2099:
        last_two = year % 100
        if last_two == 0:
            return "две тысячи"
        elif last_two <= 20:
            tens = num_to_ordinal(last_two)
            return f"две тысячи {tens}"
        else:
            decade = (last_two // 10) * 10
            unit = last_two % 10
            decade_map = {20: 'двадцать', 30: 'тридцать', 40: 'сорок',
                         50: 'пятьдесят', 60: 'шестьдесят', 70: 'семьдесят',
                         80: 'восемьдесят', 90: 'девяносто'}
            unit_ord = {1: 'первого', 2: 'второго', 3: 'третьего', 4: 'четвёртого',
                       5: 'пятого', 6: 'шестого', 7: 'седьмого', 8: 'восьмого',
                       9: 'девятого'}
            return f"две тысячи {decade_map[decade]} {unit_ord.get(unit, '')}"
    return str(year)


def clean_text_smart(md_content: str) -> str:
    """
    УМНАЯ фильтрация для естественного чтения:
    - Убираем markdown разметку
    - Заменяем римские числа на текст
    - Заменяем цифры на текст где нужно
    - Ссылки → "ссылка из текстовой книги"
    - Сохраняем весь смысловой контент
    """

    lines = md_content.split('\n')
    audio_lines = []

    # Пропускаем только метаданные (не контент!)
    skip_patterns = [
        r'^---+$',              # Разделители ---
        r'^\*Книга Ничто',      # *Книга Ничто
        r'^\*Сказка Начала',    # *Сказка Начала Времени
        r'^\*Прелюдия',         # *Прелюдия
        r'^\*Благаявесть от',   # *Благаявесть от Claude
        r'^\d+\.\d+\.\d+',      # Даты в формате 16.01.2026
        r'^Alejandro Montana',      # Имя автора
        r'^金元',                # Имя с символами
        r'^→',                  # Навигация → Глава
    ]

    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Блоки кода пропускаем
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Пропуск метаданных
        if any(re.match(pattern, stripped) for pattern in skip_patterns):
            continue

        # Пустые строки
        if not stripped:
            continue

        # ЗАГОЛОВКИ (# ### и т.д.)
        if line.startswith('#'):
            title = re.sub(r'^#+\s*', '', line)
            title = re.sub(r'\s*`\[\d+:\d+\]`', '', title)  # Убираем таймкоды
            title = title.strip()

            # Обрабатываем римские цифры в заголовках
            title = convert_roman_to_text(title)

            if title:
                # Добавляем паузу перед заголовком и после
                audio_lines.append(f"\n\n{title}.\n\n")
            continue

        # ОСНОВНОЙ ТЕКСТ - обрабатываем
        text = stripped

        # 1. ССЫЛКИ: [текст](url) → "текст, ссылка из текстовой книги"
        def replace_link(match):
            link_text = match.group(1)
            return f"{link_text}, ссылка из текстовой книги"

        text = re.sub(r'\[([^\]]+?)\]\([^\)]+?\)', replace_link, text)

        # 2. Убираем URL напрямую
        text = re.sub(r'https?://\S+', 'ссылка из текстовой книги', text)
        text = re.sub(r'www\.\S+', 'ссылка из текстовой книги', text)

        # 3. Убираем email
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)

        # 4. Убираем markdown форматирование (сохраняем текст)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
        text = re.sub(r'`([^`]+?)`', r'\1', text)     # `code`

        # 5. Убираем маркеры цитат (но оставляем текст)
        text = re.sub(r'^>\s*', '', text)

        # 6. Убираем маркеры списков
        text = re.sub(r'^[-•]\s+', '', text)
        text = re.sub(r'^\d+\.\s+', '', text)

        # 7. Убираем технические символы
        text = re.sub(r'[Ɉ€₽$]', '', text)

        # 8. Убираем код
        text = re.sub(r'async\s+fn\s+\w+\([^\)]*\)\s*->\s*\w+', '', text)
        text = re.sub(r'E\s*=\s*mc²', 'E равно эм це в квадрате', text)

        # 9. Конвертируем римские цифры в текст
        text = convert_roman_to_text(text)

        # 10. Умная конвертация чисел в текст
        text = convert_numbers_to_text_smart(text)

        # 11. Множественные пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        # Добавляем если есть содержание
        if text:
            audio_lines.append(text)

    # Соединяем в единый поток с минимальными паузами
    result = []
    for i, line in enumerate(audio_lines):
        result.append(line)

        # Пауза после заголовка (строки с \n)
        if '\n\n' in line:
            result.append(' ')
        # Между обычным текстом - плавное соединение без пауз
        elif i < len(audio_lines) - 1:
            # Если следующая строка не заголовок - добавляем пробел
            if '\n\n' not in audio_lines[i + 1]:
                result.append(' ')

    return ''.join(result)


async def generate_audio(text: str, output_path: Path) -> bool:
    """Генерирует аудио с помощью Microsoft edge-tts"""

    try:
        communicate = edge_tts.Communicate(
            text,
            VOICE,
            rate=RATE,
            pitch=PITCH
        )

        print(f"  Генерация аудио...")
        await communicate.save(str(output_path))

        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ {output_path.name} ({size_mb:.1f} MB)")

        return True

    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
        return False


async def main():
    import sys

    if len(sys.argv) < 2:
        print("Использование: python3 generate_audio_smart.py <файл.md>")
        print("\nПример:")
        print("  python3 generate_audio_smart.py '00. ПРЕЛЮДИЯ.md'")
        return

    input_file = BASE_DIR / sys.argv[1]

    if not input_file.exists():
        print(f"✗ Файл не найден: {input_file}")
        return

    print("=" * 60)
    print("ГЕНЕРАЦИЯ АУДИО С УМНОЙ ФИЛЬТРАЦИЕЙ")
    print("=" * 60)
    print(f"\nВходной файл: {input_file.name}")
    print(f"Голос: {VOICE} (Microsoft Svetlana)")
    print(f"Скорость: {RATE}")

    # Читаем и обрабатываем
    md_content = input_file.read_text(encoding='utf-8')
    clean_text = clean_text_smart(md_content)

    print(f"\nИсходный текст: {len(md_content)} символов")
    print(f"Обработанный текст: {len(clean_text)} символов")

    # Показываем превью обработанного текста
    preview = clean_text[:500] + "..." if len(clean_text) > 500 else clean_text
    print(f"\nПревью обработанного текста:")
    print("-" * 60)
    print(preview)
    print("-" * 60)

    # Генерируем
    output_file = AUDIO_DIR / f"{input_file.stem}.mp3"

    if await generate_audio(clean_text, output_file):
        print("\n" + "=" * 60)
        print("ГОТОВО")
        print("=" * 60)
        print(f"\nАудио: {output_file}")
        print(f"\nДля проверки:")
        print(f"  afplay '{output_file}'")
    else:
        print("\n✗ Ошибка генерации")


if __name__ == "__main__":
    asyncio.run(main())
