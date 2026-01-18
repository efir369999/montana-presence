#!/usr/bin/env python3
# test_thought_detection.py
# Тестирование распознавания сырых мыслей vs вопросов

from junona_bot import is_raw_thought

# Тестовые фразы
test_cases = [
    # (текст, ожидаемый_результат, описание)
    ("Время не движется, я движусь", True, "Сырая мысль: утверждение"),
    ("Маска тяжелее лица", True, "Сырая мысль: метафора"),
    ("Все врут", True, "Сырая мысль: короткая"),
    ("Что такое ACP?", False, "Вопрос: с ?"),
    ("Как подключиться к сети", False, "Вопрос: начинается с 'как'"),
    ("Почему время = деньги", False, "Вопрос: начинается с 'почему'"),
    ("Покажи мне код", False, "Команда: покажи"),
    ("Расскажи о Montana", False, "Команда: расскажи"),
    ("Я создаю свою игру", True, "Сырая мысль: личное заявление"),
    ("Монтана - это деньги во времени", True, "Сырая мысль: определение"),
    ("где находятся узлы", False, "Вопрос: где"),
    ("Объясни протокол", False, "Команда: объясни"),
]

print("Ɉ Тест распознавания мыслей vs вопросов\n")

passed = 0
failed = 0

for text, expected, description in test_cases:
    result = is_raw_thought(text)
    status = "✓" if result == expected else "✗"

    if result == expected:
        passed += 1
    else:
        failed += 1

    result_str = "МЫСЛЬ" if result else "ВОПРОС"
    expected_str = "МЫСЛЬ" if expected else "ВОПРОС"

    print(f"{status} [{description}]")
    print(f"   Текст: \"{text}\"")
    print(f"   Результат: {result_str}, Ожидалось: {expected_str}\n")

print(f"Итого: {passed} из {len(test_cases)} тестов пройдено")

if failed > 0:
    print(f"⚠️ {failed} тестов провалились")
else:
    print("✅ Все тесты пройдены")
