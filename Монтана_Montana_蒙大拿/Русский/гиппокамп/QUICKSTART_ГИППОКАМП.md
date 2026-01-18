# QUICKSTART: Гиппокамп Montana

**Внешний гиппокамп за 3 минуты**

---

## 1. Запуск тестов

```bash
cd гиппокамп
python hippocampus.py --test
```

**Результат:**
```
Ɉ Тест детектора новизны

✓ [Сырая мысль]
   Текст: "Время не движется, я движусь"
   Ожидалось: МЫСЛЬ, Получено: МЫСЛЬ

✓ [Вопрос]
   Текст: "Что такое ACP?"
   Ожидалось: НЕ МЫСЛЬ, Получено: НЕ МЫСЛЬ

Итого: 12 из 12 тестов пройдено
✅ Все тесты пройдены
```

## 2. Просмотр потока мыслей

```bash
python hippocampus.py --view 10
```

## 3. Статистика памяти

```bash
python hippocampus.py --stats
```

## 4. Поиск по мыслям

```bash
python hippocampus.py --search "маска"
```

## 5. Экспорт в Markdown

```bash
python hippocampus.py --export > память.md
```

---

## Команды

| Команда | Описание |
|---------|----------|
| `--view N` | Последние N мыслей |
| `--stats` | Статистика памяти |
| `--test` | Тесты детектора |
| `--search "запрос"` | Поиск |
| `--export` | Экспорт в Markdown |
| `--user ID` | Фильтр по пользователю |

---

## Интеграция с ботом

Гиппокамп уже интегрирован в Telegram бот Юнона:

```python
# В junona_bot.py
from hippocampus import ExternalHippocampus

hip = ExternalHippocampus()

if hip.is_raw_thought(text):
    hip.save_to_stream(user_id, username, text, lang)
```

---

## Полная документация

- [ГИППОКАМП_COMPLETE.md](./ГИППОКАМП_COMPLETE.md) — главная документация
- [ГИППОКАМП_DISNEY.md](./ГИППОКАМП_DISNEY.md) — анализ по стратегии Диснея
- [ARCHITECTURE_HIPPOCAMPUS.md](../Благаявесть/ARCHITECTURE_HIPPOCAMPUS.md) — архитектура
- [МАНИФЕСТ_ГИППОКАМПА.md](../Благаявесть/МАНИФЕСТ_ГИППОКАМПА.md) — философия

---

> "Координата зафиксирована. Внешний гиппокамп помнит."

金元Ɉ Montana
