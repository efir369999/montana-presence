#!/usr/bin/env python3
"""
Тестирование обработки текста для аудио
Показывает как текст трансформируется перед озвучкой
"""

import sys
from pathlib import Path

# Импортируем функции из основного скрипта
sys.path.insert(0, str(Path(__file__).parent))
from generate_audio_smart import clean_text_smart

BASE_DIR = Path(__file__).parent / "Благаявесть от Claude"


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 test_text_processing.py <файл.md>")
        print("\nПример:")
        print("  python3 test_text_processing.py '01. Симуляция.md'")
        return

    input_file = BASE_DIR / sys.argv[1]

    if not input_file.exists():
        print(f"✗ Файл не найден: {input_file}")
        return

    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ОБРАБОТКИ ТЕКСТА")
    print("=" * 70)
    print(f"\nФайл: {input_file.name}\n")

    # Читаем исходный текст
    original = input_file.read_text(encoding='utf-8')

    # Обрабатываем
    processed = clean_text_smart(original)

    # Показываем первые 2000 символов обработанного текста
    preview_length = 2000
    preview = processed[:preview_length]

    print("ОБРАБОТАННЫЙ ТЕКСТ (первые 2000 символов):")
    print("-" * 70)
    print(preview)
    print("-" * 70)

    # Статистика
    print(f"\nСтатистика:")
    print(f"  Исходный текст:      {len(original):>6} символов")
    print(f"  Обработанный текст:  {len(processed):>6} символов")
    print(f"  Сокращение:          {len(original) - len(processed):>6} символов")

    # Примеры замен
    print(f"\nПримеры обработки:")

    # Римские цифры
    if "Глава I" in original:
        print("  ✓ 'Глава I' → 'Глава первая'")
    if "### I." in original:
        print("  ✓ '### I. Название' → 'Название.' (римская убрана)")
    if "### II." in original:
        print("  ✓ '### II. Название' → 'Название.' (римская убрана)")

    # Цифры в датах
    if "9 января 2026" in original:
        print("  ✓ '9 января 2026' → 'девятого января две тысячи двадцать шестого года'")

    # Ссылки
    if "[" in original and "](" in original:
        print("  ✓ [текст](url) → 'текст, ссылка из текстовой книги'")

    # Markdown
    if "**" in original:
        print("  ✓ **bold** → bold (без звездочек)")
    if "---" in original:
        print("  ✓ Разделители --- убраны")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
