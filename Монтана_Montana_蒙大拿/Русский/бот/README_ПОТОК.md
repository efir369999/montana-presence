# Поток мыслей — Инструкция для разработчиков

## Архитектура

```
Пользователь → Telegram → junona_bot.py → is_raw_thought() → save_to_stream()
                                          ↓
                                    JUNONA_RESONATE → OpenAI/Claude
                                          ↓
                                    data/stream.jsonl
```

---

## Ключевые компоненты

### 1. Определение типа сообщения

**Функция:** `is_raw_thought(text: str) -> bool`

**Логика:**
- Мысль: короткое высказывание, утверждение, метафора
- НЕ мысль: вопрос (?), команда (покажи/расскажи), запрос информации

**Проверки:**
```python
# Не заканчивается на ?
# Не начинается с: что, как, почему, когда, где, кто
# Не начинается с: покажи, расскажи, объясни, помоги
# Не длиннее 500 символов
```

### 2. Сохранение в поток

**Функция:** `save_to_stream(user_id, username, thought, lang)`

**Формат:** JSON Lines (JSONL)
```json
{"user_id": 123, "username": "user", "timestamp": "2026-01-18T15:17:00Z", "thought": "текст", "lang": "ru"}
```

**Файл:** `data/stream.jsonl`

### 3. Резонанс Юноны

**Промпт:** `JUNONA_RESONATE`

**Принцип:**
- Отражение, не объяснение
- 1-2 предложения
- Связь с Montana (время, присутствие, Ничто)
- Без вопросов, без советов

**Примеры:**
```
Мысль: "Время течёт, а я стою"
Резонанс: "Время не течёт. Ты движешься сквозь него."

Мысль: "Все врут"
Резонанс: "Ложь — это шум. Твоё присутствие — сигнал."
```

---

## Изменения в коде

### junona_bot.py

**Добавлено:**

1. Константа `STREAM_FILE` (строка 34)
2. Функция `is_raw_thought()` (строки 210-244)
3. Функция `save_to_stream()` (строки 246-257)
4. Промпт `JUNONA_RESONATE` (строки 415-441)
5. Обработка в `handle_message()` (строки 1227-1248)

**Логика в handle_message:**
```python
if is_raw_thought(text):
    save_to_stream(...)
    response = await junona.resonate(...)
    await type_reply(response)  # Без кнопок
else:
    # Стандартная обработка вопроса
    response = await junona.guide_user(...)
    await msg.edit_text(response, reply_markup=chapter_keyboard)
```

---

## Утилиты

### view_stream.py

Просмотр последних N мыслей из потока.

```bash
# Последние 50 (по умолчанию)
python3 view_stream.py

# Последние 100
python3 view_stream.py 100
```

**Вывод:**
```
Ɉ Поток мыслей Montana (50 из 142)

[2026-01-18 15:17] @junomoneta (ru)
  Маска тяжелее лица

[2026-01-18 15:20] @junomoneta (ru)
  Время не движется, я движусь
```

### test_thought_detection.py

Тестирование логики распознавания.

```bash
python3 test_thought_detection.py
```

12 тестовых случаев для проверки корректности `is_raw_thought()`.

---

## Синхронизация с сетью

Поток синхронизируется через watchdog каждые 12 секунд:

```
Локал → Amsterdam → Moscow → Almaty → SPB → Novosibirsk
```

Файл `data/stream.jsonl` включается в синхронизацию вместе с `users.json`.

---

## Расширение

### Добавление новых языков

В `is_raw_thought()` добавить списки вопросительных слов:

```python
question_words_es = ['qué', 'cómo', 'por qué', 'cuándo', 'dónde']
```

### Экспорт потока

```python
import json
from pathlib import Path

STREAM_FILE = Path("data/stream.jsonl")

thoughts = []
with open(STREAM_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        thoughts.append(json.loads(line))

# Фильтр по пользователю
user_thoughts = [t for t in thoughts if t['user_id'] == 8552053404]

# Экспорт в Markdown
with open('my_thoughts.md', 'w', encoding='utf-8') as f:
    for t in user_thoughts:
        f.write(f"**{t['timestamp']}**\n")
        f.write(f"{t['thought']}\n\n")
```

---

## Безопасность

- **Append-only:** Поток не редактируется, только добавления
- **Immutable:** Timestamp в UTC, невозможно подделать прошлое
- **Privacy:** Username опционален (может быть "аноним")
- **Size limit:** 500 символов на мысль (защита от спама)

---

## Когнитивная подпись

> *"Стиль — мой. Ценности — мои. Структура мышления — моя."*

Поток мыслей — это когнитивная подпись пользователя:
- Не через память (что я сказал)
- Через консистентность (как я мыслю)
- Temporal evidence chain (мысли во времени)

---

Ɉ Montana
