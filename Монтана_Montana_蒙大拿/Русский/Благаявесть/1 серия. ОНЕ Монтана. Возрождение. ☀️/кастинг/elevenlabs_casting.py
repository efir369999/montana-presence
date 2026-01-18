#!/usr/bin/env python3
"""
Montana Voice Casting - ElevenLabs AI Voices
Подбор "вечных актеров" для сериала
18.01.2026
"""

import os
from elevenlabs.client import ElevenLabs
from pathlib import Path

# API ключ (установи через переменную окружения)
# export ELEVEN_API_KEY="твой_ключ_здесь"

OUTPUT_DIR = Path(__file__).parent / "образцы"
OUTPUT_DIR.mkdir(exist_ok=True)

# Тестовые фразы для каждой роли
TEST_PHRASES = {
    "ОНЕ": """Яндекс ищет данные. Google хранит данные.
Montana соединяет людей через время. Найдёмся —
потому что координаты зафиксированы.""",

    "Девушка_в_Красном": """Ты еще здесь?
Я каждый раз любила, когда встречалась.""",

    "К": """Может в Сингапуре все исправим?
Я каждый раз любила, когда встречалась.""",

    "Тринити": """Время — единственный судья,
которого нельзя подкупить.""",

    "Claude": """Montana: всё записано. Timestamp.
Пять узлов. Append-only. Изменить задним числом — невозможно."""
}

# Рекомендуемые голоса из ElevenLabs для каждой роли (с voice_id)
VOICE_CANDIDATES = {
    "ОНЕ": [
        # Мужские голоса - глубокие, философские
        ("Adam", "pNInz6obpgDQGcFmaJgB"),      # Dominant, Firm
        ("Charlie", "IKne3meq5aSn9XLyUdCD"),   # Deep, Confident, Energetic
        ("Callum", "N2lVS1w4EtoT3dr4eOWO"),    # Husky Trickster
        ("Daniel", "onwK4e9ZLuTAKqWW03F9"),    # Steady Broadcaster
        ("Brian", "nPczCjzI2devNBz1zQrb"),     # Deep, Resonant and Comforting
    ],

    "Девушка_в_Красном": [
        # Женские голоса - чувственные, эмоциональные
        ("Jessica", "cgSgspJ2msm6clMCkdW9"),   # Playful, Bright, Warm
        ("Matilda", "XrExE9yKIg1WjnnlVkGX"),   # Knowledgable, Professional
        ("Laura", "FGY2WhTYpPnrIDTdsKH5"),     # Enthusiast, Quirky Attitude
        ("Sarah", "EXAVITQu4vr4xnSDxMaL"),     # Mature, Reassuring, Confident
        ("Alice", "Xb7hH8MSUJpSbSDYk0k2"),     # Clear, Engaging Educator
    ],

    "К": [
        # Женские голоса - молодые, нежные
        ("Lily", "pFZP5JQG7iQjIQuC4Bku"),      # Velvety Actress
        ("Sarah", "EXAVITQu4vr4xnSDxMaL"),     # Mature, Reassuring, Confident
        ("Jessica", "cgSgspJ2msm6clMCkdW9"),   # Playful, Bright, Warm
        ("Laura", "FGY2WhTYpPnrIDTdsKH5"),     # Enthusiast, Quirky Attitude
        ("Alice", "Xb7hH8MSUJpSbSDYk0k2"),     # Clear, Engaging Educator
    ],

    "Тринити": [
        # Женские голоса - сильные но нежные
        ("Jessica", "cgSgspJ2msm6clMCkdW9"),   # Playful, Bright, Warm
        ("Matilda", "XrExE9yKIg1WjnnlVkGX"),   # Knowledgable, Professional
        ("Sarah", "EXAVITQu4vr4xnSDxMaL"),     # Mature, Reassuring, Confident
        ("Lily", "pFZP5JQG7iQjIQuC4Bku"),      # Velvety Actress
        ("Alice", "Xb7hH8MSUJpSbSDYk0k2"),     # Clear, Engaging Educator
    ],

    "Claude": [
        # Голоса для AI комментариев
        ("Daniel", "onwK4e9ZLuTAKqWW03F9"),    # Steady Broadcaster
        ("George", "JBFqnCBsd6RMkjVDRZzb"),    # Warm, Captivating Storyteller
        ("Harry", "SOYHLrjzK2X1ezoPC6cr"),     # Fierce Warrior
        ("Liam", "TX3LPaxmHKxFdv7VOQHJ"),      # Energetic, Social Media Creator
        ("Brian", "nPczCjzI2devNBz1zQrb"),     # Deep, Resonant and Comforting
    ]
}


def list_all_voices():
    """Показывает все доступные голоса в ElevenLabs"""
    print("\n📋 Доступные голоса ElevenLabs:\n")

    try:
        client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
        all_voices = client.voices.get_all()

        print(f"{'Имя':<20} {'ID':<30} {'Категория':<15} {'Описание'}")
        print("=" * 100)

        for voice in all_voices.voices:
            name = voice.name
            voice_id = voice.voice_id
            category = getattr(voice, 'category', 'N/A')
            labels = getattr(voice, 'labels', {})
            desc = labels.get('description', 'N/A') if labels else 'N/A'

            print(f"{name:<20} {voice_id:<30} {category:<15} {desc[:40]}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("💡 Установи API ключ: export ELEVEN_API_KEY='твой_ключ'")


def test_voice(role, voice_name, voice_id, phrase):
    """
    Тестирует голос для конкретной роли

    Args:
        role: название роли
        voice_name: имя голоса (для отображения)
        voice_id: ID голоса из ElevenLabs
        phrase: текст для озвучки
    """
    output_file = OUTPUT_DIR / f"{role}_{voice_name}.mp3"

    if output_file.exists():
        print(f"   ✓ Уже существует: {output_file.name}")
        return

    print(f"   🎙️  Генерирую: {role} - {voice_name}")

    try:
        client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

        # Генерация аудио
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            text=phrase,
            model_id="eleven_multilingual_v2"
        )

        # Сохранение в файл
        with open(output_file, 'wb') as f:
            for chunk in audio:
                f.write(chunk)

        print(f"   ✅ Сохранено: {output_file.name}")

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")


def generate_all_samples():
    """Генерирует образцы для всех кандидатов"""
    print("\n🎭 MONTANA VOICE CASTING\n")
    print("=" * 60)

    total = sum(len(candidates) for candidates in VOICE_CANDIDATES.values())
    current = 0

    for role, candidates in VOICE_CANDIDATES.items():
        print(f"\n📥 Роль: {role}")
        phrase = TEST_PHRASES.get(role, "Тестовая фраза на русском языке.")

        for voice_name, voice_id in candidates:
            current += 1
            print(f"[{current}/{total}]", end=" ")
            test_voice(role, voice_name, voice_id, phrase)

    print("\n" + "=" * 60)
    print(f"✅ Готово! Образцы в: {OUTPUT_DIR}")
    print(f"📁 Всего файлов: {len(list(OUTPUT_DIR.glob('*.mp3')))}")
    print("\n💡 Прослушай образцы и выбери лучшие голоса!")


def test_russian_support(voice_name):
    """Проверяет качество русского языка для голоса"""
    russian_test = """Здравствуйте! Это тест русского языка.
    Проверяем качество произношения, интонацию и естественность."""

    output_file = OUTPUT_DIR / f"test_russian_{voice_name}.mp3"

    print(f"🧪 Тест русского: {voice_name}")

    try:
        client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))

        audio = client.text_to_speech.convert(
            voice_id=voice_name,
            text=russian_test,
            model_id="eleven_multilingual_v2"
        )

        with open(output_file, 'wb') as f:
            for chunk in audio:
                f.write(chunk)

        print(f"✅ Сохранено: {output_file.name}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def create_casting_report():
    """Создает отчет по результатам кастинга"""
    report_file = Path(__file__).parent / "РЕЗУЛЬТАТЫ_КАСТИНГА.md"

    content = """# Результаты кастинга ElevenLabs голосов

**Дата:** 18.01.2026
**Проект:** 1 серия. ОНЕ Монтана. Возрождение. ☀️

---

## Прослушанные образцы:

### Роль: ОНЕ (Нео Монтана)
- [ ] Adam - Deep, confident
- [ ] Antoni - Well-rounded
- [ ] Arnold - Crisp, strong
- [ ] Callum - Mature, warm
- [ ] Charlie - Casual, natural

**Выбор:** _______________

---

### Роль: Девушка в Красном
- [ ] Bella - Soft, emotional
- [ ] Domi - Strong, expressive
- [ ] Elli - Emotive, young
- [ ] Rachel - Calm, pleasant
- [ ] Matilda - Warm, upbeat

**Выбор:** _______________

---

### Роль: #К (КрасноеПлатье)
- [ ] Elli - Young, sweet
- [ ] Freya - Pleasant, feminine
- [ ] Grace - Youthful, bright
- [ ] Lily - Warm, sweet
- [ ] Sarah - Soft, friendly

**Выбор:** _______________

---

### Роль: Тринити
- [ ] Charlotte - Seductive, engaging
- [ ] Domi - Strong, assertive
- [ ] Jessica - Expressive, warm
- [ ] Nicole - Confident, smooth
- [ ] Serena - Pleasant, strong

**Выбор:** _______________

---

### Роль: #Claude
- [ ] Clyde - Middle-aged
- [ ] Daniel - Deep, authoritative
- [ ] George - Raspy, articulate
- [ ] Harry - Anxious, intelligent
- [ ] Liam - Neutral, articulate

**Выбор:** _______________

---

## Финальный кастинг:

| Роль | Голос ElevenLabs | Voice ID | Примечания |
|------|------------------|----------|------------|
| ОНЕ | | | |
| Девушка в Красном | | | |
| #К | | | |
| Тринити | | | |
| #Claude | | | |

---

**Клод Монтана**
**金元Ɉ Montana**
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n📄 Создан отчет: {report_file.name}")


if __name__ == "__main__":
    import sys

    print("\n" + "=" * 60)
    print("🎙️  MONTANA VOICE CASTING - ELEVENLABS")
    print("   Вечные актеры для сериала")
    print("=" * 60)

    # Проверка API ключа
    if not os.getenv("ELEVEN_API_KEY"):
        print("\n⚠️  API ключ не найден!")
        print("💡 Установи: export ELEVEN_API_KEY='твой_ключ_здесь'")
        print("   Получи ключ на: https://elevenlabs.io\n")
        sys.exit(1)

    if "--list" in sys.argv:
        # Показать все доступные голоса
        list_all_voices()

    elif "--test" in sys.argv:
        # Тестировать конкретный голос
        if len(sys.argv) < 3:
            print("Использование: python elevenlabs_casting.py --test VoiceName")
        else:
            voice_name = sys.argv[2]
            test_russian_support(voice_name)

    elif "--generate" in sys.argv:
        # Генерировать все образцы
        generate_all_samples()
        create_casting_report()

    else:
        print("\n📋 Команды:")
        print("   --list      Показать все доступные голоса")
        print("   --generate  Сгенерировать образцы для всех кандидатов")
        print("   --test NAME Протестировать конкретный голос")
        print("\nПример:")
        print("   python elevenlabs_casting.py --generate")
