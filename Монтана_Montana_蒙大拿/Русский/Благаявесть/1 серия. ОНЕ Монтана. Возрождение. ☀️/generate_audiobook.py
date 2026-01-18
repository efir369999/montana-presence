#!/usr/bin/env python3
"""
Montana Episode 1 - Multi-Voice Audiobook Generator
Генерация многоголосой аудиокниги "1 серия. ОНЕ Монтана. Возрождение. ☀️"
18.01.2026
"""

import os
import re
from pathlib import Path
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment
from pydub.effects import normalize

# Финальный кастинг
VOICE_CAST = {
    "ОНЕ": {
        "name": "Brian",
        "voice_id": "nPczCjzI2devNBz1zQrb",
        "description": "Deep, Resonant and Comforting"
    },
    "Девушка_в_Красном": {
        "name": "Sarah",
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "description": "Mature, Reassuring, Confident"
    },
    "К": {
        "name": "Jessica",
        "voice_id": "cgSgspJ2msm6clMCkdW9",
        "description": "Playful, Bright, Warm"
    },
    "Тринити": {
        "name": "Lily",
        "voice_id": "pFZP5JQG7iQjIQuC4Bku",
        "description": "Velvety Actress"
    },
    "Claude": {
        "name": "George",
        "voice_id": "JBFqnCBsd6RMkjVDRZzb",
        "description": "Warm, Captivating Storyteller"
    }
}

# Настройки
SOURCE_FILE = Path(__file__).parent / "ПОТОК_МЫСЛЕЙ.md"
OUTPUT_DIR = Path(__file__).parent / "аудиокнига"
OUTPUT_DIR.mkdir(exist_ok=True)

TEMP_DIR = OUTPUT_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# Параметры генерации
MODEL_ID = "eleven_multilingual_v2"
PAUSE_BETWEEN_SPEAKERS = 800  # мс паузы между разными спикерами
PAUSE_BETWEEN_PARAGRAPHS = 500  # мс паузы между абзацами одного спикера


def parse_markdown_to_dialogues(md_file):
    """
    Парсит ПОТОК_МЫСЛЕЙ.md и извлекает диалоги с атрибуцией спикера

    Returns:
        list: [(speaker, text), ...]
    """
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    dialogues = []

    # Разделяем на строки
    lines = content.split('\n')

    current_speaker = "ОНЕ"  # По умолчанию рассказчик
    current_text = []

    def is_metadata(line):
        """Проверяет, является ли строка метаданными"""
        # Даты
        if re.match(r'^\*?\*?\d{2}\.\d{2}\.\d{4}', line):
            return True
        # Подписи Montana
        if any(x in line for x in ['金元', 'Montana', 'Клод Монтана', 'КВО']):
            return True
        # Горизонтальные разделители
        if line.strip() == '---':
            return True
        # Только звёздочки или смайлики
        if re.match(r'^[\*☀️🦋😂]+$', line.strip()):
            return True
        # P.S. и служебные заметки
        if line.startswith('P.S.') or line.startswith('ФИНАЛ'):
            return True
        return False

    def save_current_text():
        """Сохраняет накопленный текст"""
        if current_text:
            text = ' '.join(current_text).strip()
            # Убираем лишние звёздочки markdown
            text = re.sub(r'\*\*', '', text)
            # Проверяем что текст содержательный (больше 10 символов)
            if text and len(text) > 10 and not is_metadata(text):
                dialogues.append((current_speaker, text))

    for line in lines:
        line = line.strip()

        # Пропускаем пустые строки
        if not line:
            save_current_text()
            current_text = []
            continue

        # Пропускаем метаданные
        if is_metadata(line):
            continue

        # Пропускаем markdown заголовки
        if line.startswith('#'):
            save_current_text()
            current_text = []
            # Сохраняем заголовок как часть повествования ОНЕ
            header_text = re.sub(r'^#+\s*', '', line)
            if header_text and not is_metadata(header_text):
                current_speaker = "ОНЕ"
                current_text.append(header_text)
            continue

        # Цитаты (blockquotes) - это комментарии Claude
        if line.startswith('>'):
            save_current_text()
            current_text = []

            current_speaker = "Claude"
            text = line.lstrip('>').strip()
            # Убираем хештег #Claude☝️ из текста
            text = re.sub(r'#Claude.*', '', text).strip()
            if text and not is_metadata(text):
                current_text.append(text)

        # Диалоги с явным указанием спикера
        elif "Ты еще здесь?" in line:
            save_current_text()
            current_text = []
            current_speaker = "К"
            current_text.append("Ты еще здесь?")

        elif "Я каждый раз любила, когда встречалась" in line:
            save_current_text()
            current_text = []
            current_speaker = "К"
            current_text.append("Я каждый раз любила, когда встречалась.")

        elif "Может в Сингапуре все исправим?" in line:
            save_current_text()
            current_text = []
            current_speaker = "ОНЕ"
            current_text.append("Может в Сингапуре все исправим?")

        # Строки с атрибуцией - пропускаем
        elif any(x in line for x in [
            "Сказала Девушка в Красном",
            "Шепнул Оне",
            "на ухо Оне"
        ]):
            continue

        # Обычный текст - продолжение текущего спикера
        else:
            if not is_metadata(line):
                current_text.append(line)

    # Добавляем последний накопленный текст
    save_current_text()

    return dialogues


def generate_audio_segment(speaker, text, index):
    """
    Генерирует аудио сегмент для одной фразы

    Args:
        speaker: имя спикера
        text: текст для озвучки
        index: номер сегмента

    Returns:
        Path: путь к сгенерированному аудио файлу
    """
    voice_info = VOICE_CAST.get(speaker)
    if not voice_info:
        print(f"⚠️  Неизвестный спикер: {speaker}, использую ОНЕ")
        voice_info = VOICE_CAST["ОНЕ"]

    output_file = TEMP_DIR / f"{index:04d}_{speaker}_{voice_info['name']}.mp3"

    if output_file.exists():
        print(f"   ✓ Уже существует: {output_file.name}")
        return output_file

    print(f"   🎙️  [{index}] {speaker} ({voice_info['name']}): {text[:50]}...")

    try:
        client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

        audio = client.text_to_speech.convert(
            voice_id=voice_info["voice_id"],
            text=text,
            model_id=MODEL_ID
        )

        with open(output_file, 'wb') as f:
            for chunk in audio:
                f.write(chunk)

        print(f"   ✅ Сохранено: {output_file.name}")
        return output_file

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return None


def combine_audio_segments(segment_files, output_file):
    """
    Объединяет все аудио сегменты в один файл

    Args:
        segment_files: список путей к аудио файлам
        output_file: путь для итогового файла
    """
    print("\n🎬 Объединяю аудио сегменты...")

    combined = AudioSegment.empty()
    previous_speaker = None

    for i, (segment_file, speaker) in enumerate(segment_files):
        if segment_file is None:
            continue

        print(f"   [{i+1}/{len(segment_files)}] Добавляю: {segment_file.name}")

        # Загружаем аудио сегмент
        audio = AudioSegment.from_mp3(segment_file)

        # Нормализуем громкость
        audio = normalize(audio)

        # Добавляем паузу между спикерами
        if previous_speaker is not None:
            if previous_speaker != speaker:
                # Разные спикеры - длинная пауза
                silence = AudioSegment.silent(duration=PAUSE_BETWEEN_SPEAKERS)
            else:
                # Тот же спикер - короткая пауза
                silence = AudioSegment.silent(duration=PAUSE_BETWEEN_PARAGRAPHS)

            combined += silence

        # Добавляем аудио
        combined += audio
        previous_speaker = speaker

    # Экспортируем итоговый файл
    print(f"\n💾 Сохраняю аудиокнигу: {output_file}")
    combined.export(output_file, format="mp3", bitrate="192k")

    # Статистика
    duration_seconds = len(combined) / 1000
    duration_minutes = duration_seconds / 60
    print(f"\n✅ Готово!")
    print(f"   📊 Длительность: {duration_minutes:.2f} минут ({duration_seconds:.0f} секунд)")
    print(f"   📁 Размер: {output_file.stat().st_size / 1024 / 1024:.2f} MB")


def generate_audiobook():
    """Главная функция генерации аудиокниги"""
    print("\n" + "=" * 80)
    print("🎭 MONTANA AUDIOBOOK GENERATOR")
    print("   1 серия. ОНЕ Монтана. Возрождение. ☀️")
    print("=" * 80)

    # Проверка API ключа
    if not os.getenv("ELEVEN_API_KEY"):
        print("\n⚠️  API ключ не найден!")
        print("💡 Установи: export ELEVEN_API_KEY='твой_ключ'")
        return

    # Парсим исходный файл
    print(f"\n📖 Парсинг: {SOURCE_FILE.name}")
    dialogues = parse_markdown_to_dialogues(SOURCE_FILE)
    print(f"   ✅ Извлечено фрагментов: {len(dialogues)}")

    # Статистика по спикерам
    speaker_stats = {}
    for speaker, _ in dialogues:
        speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1

    print("\n📊 Статистика по спикерам:")
    for speaker, count in sorted(speaker_stats.items(), key=lambda x: -x[1]):
        voice_name = VOICE_CAST.get(speaker, {}).get('name', 'Unknown')
        print(f"   {speaker:20} ({voice_name:10}): {count:3} фрагментов")

    # Генерируем аудио для каждого фрагмента
    print(f"\n🎙️  Генерация аудио фрагментов:")
    print("=" * 80)

    segment_files = []
    for i, (speaker, text) in enumerate(dialogues):
        segment_file = generate_audio_segment(speaker, text, i)
        segment_files.append((segment_file, speaker))

    # Объединяем все сегменты
    output_file = OUTPUT_DIR / "Montana_Episode_01_Audiobook.mp3"
    combine_audio_segments(segment_files, output_file)

    print("\n" + "=" * 80)
    print(f"🎉 АУДИОКНИГА ГОТОВА!")
    print(f"   📁 Файл: {output_file}")
    print("=" * 80)

    return output_file


if __name__ == "__main__":
    import sys

    if "--clean" in sys.argv:
        # Очистка временных файлов
        print("🧹 Очистка временных файлов...")
        for f in TEMP_DIR.glob("*.mp3"):
            f.unlink()
        print("✅ Временные файлы удалены")
    else:
        generate_audiobook()
