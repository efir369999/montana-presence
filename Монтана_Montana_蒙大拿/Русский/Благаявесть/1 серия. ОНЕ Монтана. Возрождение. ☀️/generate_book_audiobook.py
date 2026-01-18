#!/usr/bin/env python3
"""
Montana Episode 1 Book Format Audiobook Generator
Генерация аудиокниги из форматированной версии серии
"""

import os
import re
from pathlib import Path
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment
from pydub.effects import normalize, speedup

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Голоса Montana (Вечные актеры) - РУССКИЕ ГОЛОСА
VOICE_CAST = {
    "НАРРАТОР": {
        "name": "Aleksandr (RU)",
        "voice_id": "gD1IexrzCvsXPHUuT0s3",  # Русский мужской голос
        "description": "Warm Russian narrator"
    },
    "ОНЕ": {
        "name": "Mikhail (RU)",
        "voice_id": "flq6f7yk4E4fJM5XTYuZ",  # Глубокий русский голос
        "description": "Deep Russian voice"
    },
    "CLAUDE": {
        "name": "Aleksandr (RU)",
        "voice_id": "gD1IexrzCvsXPHUuT0s3",  # Тот же что нарратор
        "description": "Warm Russian narrator"
    },
    "#К": {
        "name": "Polina (RU)",
        "voice_id": "2qVHM0cCKYd8wTPGMEBd",  # Женский русский голос
        "description": "Playful Russian female"
    }
}

# Пути
SCRIPT_DIR = Path(__file__).parent
BOOK_FILE = SCRIPT_DIR / "1 серия. ОНЕ Монтана. Возрождение. ☀️.md"
OUTPUT_DIR = SCRIPT_DIR / "аудиокнига" / "book"
TEMP_DIR = OUTPUT_DIR / "temp_ru"
FINAL_OUTPUT = OUTPUT_DIR / "Montana_Episode_01_Book_RU_Slow.mp3"

# ElevenLabs настройки
MODEL_ID = "eleven_multilingual_v2"
PAUSE_BETWEEN_SPEAKERS = 800  # ms
PAUSE_BETWEEN_SCENES = 1500   # ms
PAUSE_SHORT = 500             # ms для внутренних пауз

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def number_to_russian_text(number_str):
    """Конвертирует числа в текст для лучшего произношения"""

    # Словари для конвертации
    units = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
             "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
    tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
    hundreds = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]

    try:
        num = int(number_str)

        # Специальные случаи
        if num == 0:
            return "ноль"

        # Годы (2005, 2019, 2026 и т.д.)
        if 1900 <= num <= 2100:
            if num == 2005:
                return "две тысячи пятый год"
            elif num == 2019:
                return "две тысячи девятнадцатый год"
            elif num == 2026:
                return "две тысячи двадцать шестой год"
            else:
                # Общий случай для годов
                thousands = num // 1000
                remainder = num % 1000
                result = []

                if thousands == 1:
                    result.append("одна тысяча")
                elif thousands == 2:
                    result.append("две тысячи")

                if remainder > 0:
                    if remainder < 10:
                        result.append(units[remainder])
                    elif remainder < 20:
                        result.append(teens[remainder - 10])
                    elif remainder < 100:
                        t = remainder // 10
                        u = remainder % 10
                        result.append(tens[t])
                        if u > 0:
                            result.append(units[u])
                    else:
                        h = remainder // 100
                        remainder = remainder % 100
                        result.append(hundreds[h])
                        if remainder > 0:
                            if remainder < 10:
                                result.append(units[remainder])
                            elif remainder < 20:
                                result.append(teens[remainder - 10])
                            else:
                                t = remainder // 10
                                u = remainder % 10
                                result.append(tens[t])
                                if u > 0:
                                    result.append(units[u])

                return " ".join(result) + " год"

        # Обычные числа (1-99)
        if num < 10:
            return units[num]
        elif num < 20:
            return teens[num - 10]
        elif num < 100:
            t = num // 10
            u = num % 10
            return tens[t] + (" " + units[u] if u > 0 else "")

        # Для остальных случаев возвращаем как есть
        return number_str

    except ValueError:
        return number_str

def preprocess_text_for_speech(text):
    """Предобработка текста для лучшего произношения"""

    # Конвертируем годы и числа
    def replace_number(match):
        return number_to_russian_text(match.group(0))

    # Заменяем годы (4-значные числа)
    text = re.sub(r'\b(19|20)\d{2}\b', replace_number, text)

    # Заменяем двузначные числа
    text = re.sub(r'\b\d{1,2}\b', replace_number, text)

    # Специальные замены для лучшего произношения
    replacements = {
        "18.01.2026": "восемнадцатое января две тысячи двадцать шестого года",
        "КВО 018": "КВО ноль восемнадцать",
        "18:18": "восемнадцать восемнадцать",
        "17:02": "семнадцать ноль два",
        "20:00": "двадцать ноль ноль",
        "08:38:27": "восемь тридцать восемь двадцать семь",
        "00:00": "ноль ноль ноль ноль",
        "$250": "двести пятьдесят долларов",
        "$69": "шестьдесят девять долларов",
        "$1.1": "один и один десятых",
        "VDF": "ВДФ",
        "NPC": "эн пи си",
        "AI": "ай ай",
        "NFT": "эн эф ти",
        "13 этаж": "тринадцатый этаж",
        "18 этаж": "восемнадцатый этаж",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

# ============================================================================
# ПАРСИНГ
# ============================================================================

def parse_book_script(md_file):
    """Парсит форматированный сценарий книги"""

    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    dialogues = []
    current_speaker = None
    current_scene = None

    lines = content.split('\n')

    for line in lines:
        line = line.strip()

        # Пропускаем пустые строки
        if not line:
            continue

        # Пропускаем технический раздел
        if "## ТЕХНИЧЕСКАЯ ИНФОРМАЦИЯ" in line:
            break

        # Детектируем сцену
        if line.startswith("## СЦ.") or line.startswith("## ОТКРЫТИЕ") or line.startswith("## ФИНАЛ"):
            current_scene = line.replace("##", "").strip()
            continue

        # Детектируем спикера
        speaker_match = re.match(r'\*\*([А-ЯA-Z#]+):\*\*', line)
        if speaker_match:
            current_speaker = speaker_match.group(1)
            continue

        # Пропускаем визуальные ремарки (но сохраняем эмоциональные)
        if line.startswith("*(Визуал:"):
            continue

        # Пропускаем разделители
        if line == "---":
            continue

        # Пропускаем заголовки
        if line.startswith("#"):
            continue

        # Обрабатываем текст
        if current_speaker and line:
            # Удаляем визуальные ремарки из середины текста
            text = re.sub(r'\*\(Визуал:[^)]+\)\*', '', line)

            # Сохраняем эмоциональные ремарки но убираем скобки для чтения
            # *(Поёт)* → читается как есть
            # *(Пауза)* → вставляем паузу
            # *(Смеётся)* → читается как есть

            if "*(Пауза)*" in text:
                # Добавляем специальный маркер паузы
                dialogues.append((current_speaker, "[ПАУЗА]"))
                text = text.replace("*(Пауза)*", "")

            # Убираем пустые ремарки
            text = text.strip()

            if text:
                dialogues.append((current_speaker, text))

    return dialogues

# ============================================================================
# ГЕНЕРАЦИЯ АУДИО
# ============================================================================

def generate_audio_segment(speaker, text, index):
    """Генерирует аудио фрагмент для одной реплики"""

    # Специальная обработка пауз
    if text == "[ПАУЗА]":
        return None

    voice_info = VOICE_CAST.get(speaker)
    if not voice_info:
        print(f"   ⚠️  Неизвестный спикер: {speaker}, пропускаем")
        return None

    voice_name = voice_info["name"]
    output_file = TEMP_DIR / f"{index:04d}_{speaker}_{voice_name}.mp3"

    # Если уже существует, пропускаем
    if output_file.exists():
        print(f"   ✅ Уже существует: {output_file.name}")
        return str(output_file)

    # Убираем markdown форматирование
    clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    clean_text = re.sub(r'\*([^*]+)\*', r'\1', clean_text)  # *italic*

    # Предобработка для лучшего произношения
    clean_text = preprocess_text_for_speech(clean_text)

    # Показываем превью
    preview = clean_text[:60] + "..." if len(clean_text) > 60 else clean_text
    print(f"   🎙️  [{index}] {speaker} ({voice_name}): {preview}")

    try:
        client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

        audio_generator = client.text_to_speech.convert(
            voice_id=voice_info["voice_id"],
            text=clean_text,
            model_id=MODEL_ID
        )

        # Сохраняем
        with open(output_file, 'wb') as f:
            for chunk in audio_generator:
                f.write(chunk)

        print(f"   ✅ Сохранено: {output_file.name}")
        return str(output_file)

    except Exception as e:
        print(f"   ❌ Ошибка генерации: {e}")
        return None

def combine_audio_segments(segment_files, dialogues, output_file):
    """Объединяет все аудио фрагменты в единый файл"""

    print("\n🎬 Объединение аудио фрагментов...")

    combined = AudioSegment.silent(duration=0)
    prev_speaker = None
    scene_change_indices = []

    # Находим индексы смены сцен (когда НАРРАТОР читает название сцены)
    for i, (speaker, text) in enumerate(dialogues):
        if speaker == "НАРРАТОР" and any(x in text for x in ["СЦ.", "ОТКРЫТИЕ", "ФИНАЛ", "Возврат к началу", "Архитектура Montana"]):
            scene_change_indices.append(i)

    for i, segment_file in enumerate(segment_files):
        if segment_file is None:
            # Пауза
            combined += AudioSegment.silent(duration=PAUSE_SHORT)
            continue

        try:
            segment = AudioSegment.from_mp3(segment_file)
            segment = normalize(segment)

            # Замедляем на 15% (скорость 0.85)
            # Метод: уменьшаем frame_rate, затем восстанавливаем с исходным
            slow_segment = segment._spawn(segment.raw_data, overrides={
                "frame_rate": int(segment.frame_rate * 0.85)
            })
            segment = slow_segment.set_frame_rate(segment.frame_rate)

            speaker = dialogues[i][0]

            # Пауза между сменой сцены
            if i in scene_change_indices and i > 0:
                combined += AudioSegment.silent(duration=PAUSE_BETWEEN_SCENES)
            # Пауза между разными спикерами
            elif prev_speaker and prev_speaker != speaker:
                combined += AudioSegment.silent(duration=PAUSE_BETWEEN_SPEAKERS)
            # Короткая пауза между фразами одного спикера
            elif prev_speaker and prev_speaker == speaker:
                combined += AudioSegment.silent(duration=PAUSE_SHORT)

            combined += segment
            prev_speaker = speaker

            if (i + 1) % 10 == 0:
                print(f"   Обработано: {i + 1}/{len(segment_files)} фрагментов")

        except Exception as e:
            print(f"   ⚠️  Ошибка загрузки {segment_file}: {e}")
            continue

    # Экспортируем
    print(f"\n💾 Экспорт финального файла: {output_file}")
    combined.export(
        output_file,
        format="mp3",
        bitrate="192k",
        tags={
            "artist": "Montana Productions",
            "album": "ОНЕ Монтана - Серия 1",
            "title": "Возрождение (Book Version)",
            "date": "2026"
        }
    )

    duration_min = len(combined) / 1000 / 60
    size_mb = output_file.stat().st_size / 1024 / 1024

    print(f"\n✅ Готово!")
    print(f"   📊 Длительность: {duration_min:.1f} минут")
    print(f"   📦 Размер: {size_mb:.1f} MB")
    print(f"   📁 Файл: {output_file}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*80)
    print("🎭 MONTANA BOOK AUDIOBOOK GENERATOR")
    print("   1 серия. ОНЕ Монтана. Возрождение. ☀️ (Book Version)")
    print("="*80)

    # Создаем директории
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Проверяем API ключ
    if not os.getenv("ELEVEN_API_KEY"):
        print("❌ ELEVEN_API_KEY не установлен!")
        return

    # 1. Парсинг
    print(f"\n📖 Парсинг: {BOOK_FILE.name}")
    dialogues = parse_book_script(BOOK_FILE)
    print(f"   ✅ Извлечено фрагментов: {len(dialogues)}")

    # Статистика
    print("\n📊 Статистика по спикерам:")
    speaker_counts = {}
    for speaker, _ in dialogues:
        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

    for speaker, count in sorted(speaker_counts.items()):
        voice_name = VOICE_CAST.get(speaker, {}).get("name", "Unknown")
        print(f"   {speaker:20} ({voice_name:10}): {count:3} фрагментов")

    # 2. Генерация аудио
    print("\n🎙️  Генерация аудио фрагментов:")
    print("="*80)

    segment_files = []
    for i, (speaker, text) in enumerate(dialogues):
        segment_file = generate_audio_segment(speaker, text, i)
        segment_files.append(segment_file)

    # 3. Объединение
    combine_audio_segments(segment_files, dialogues, FINAL_OUTPUT)

    print("\n" + "="*80)
    print("🎉 ЗАВЕРШЕНО!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
