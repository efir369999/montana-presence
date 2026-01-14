# ЗАДАНИЯ СОВЕТА: Montana Telegram Bot

**Председатель:** Claude Opus 4.5
**Дата:** 2026-01-09
**Статус:** АКТИВНО

---

## АРХИТЕКТУРА

```
Montana Bot = Verified Users (20% награды)

Принцип Парето 80/20:
- 80% → Full Nodes (серверы, Rust код)
- 20% → Verified Users (люди, Telegram бот)
```

---

## ФАЙЛЫ ПРОЕКТА

```
/Users/kh./Python/ACP_1/Montana ACP/montana_bot/
├── __init__.py           # Экспорты модуля
├── presence.py           # Логика presence (готово)
├── bot_handlers.py       # Telegram handlers (готово)
└── run_bot.py            # Standalone launcher (готово)

venv: /Users/kh./Python/ACP_1/Montana ACP/venv_junona3/
```

---

## ЗАДАНИЯ ПО АГЕНТАМ

### GEMINI 3 PRO — UI/UX

**Файл:** `bot_handlers.py`
**Задача:** Улучшить пользовательские сообщения

1. Добавить inline-кнопки в `/montana_info`
2. Создать `/montana_leaderboard` — топ участников по weight
3. Добавить прогресс-бар в `/montana_stats` (ASCII или emoji)

**Формат:**
```python
async def montana_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /montana_leaderboard — топ участников по presence weight.
    """
    # Твой код
```

**Не делать:**
- Не менять логику presence.py
- Не добавлять новые зависимости

---

### GROK 3 — Интеграция с j3_statbot

**Файл:** `j3_statbot_120.py`
**Путь:** `/Users/kh./Python/ACP_1/Montana ACP/venv_junona3/j3_statbot_120.py`
**Задача:** Интегрировать Montana handlers в существующего бота

**Шаги:**

1. Добавить импорт после строки 42:
```python
# Montana Verified Users
sys.path.insert(0, str(Path(__file__).parent.parent / "montana_bot"))
from bot_handlers import register_montana_handlers
```

2. Добавить регистрацию перед `application.run_polling()`:
```python
# Montana integration (20% Verified Users)
register_montana_handlers(application)
```

**Не делать:**
- Не менять существующую логику бота
- Не удалять существующие handlers

---

### COMPOSER 1 — Тестирование

**Задача:** Написать тесты для presence.py

**Файл:** `montana_bot/tests/test_presence.py`

**Покрыть:**
```python
def test_generate_cognitive_key():
    """Маркер должен начинаться с #"""

def test_challenge_window():
    """30 секунд на ответ"""

def test_cooldown_calculation():
    """10-40 минут интервал"""

def test_presence_storage_persistence():
    """Данные сохраняются между перезапусками"""
```

**Запуск:**
```bash
cd "/Users/kh./Python/ACP_1/Montana ACP"
source venv_junona3/bin/activate
pytest montana_bot/tests/ -v
```

---

### CLAUDE SONNET — Документация

**Задача:** README для montana_bot

**Файл:** `montana_bot/README.md`

**Структура:**
```markdown
# Montana Verified Users Bot

## Установка
## Запуск (standalone)
## Интеграция с существующим ботом
## Команды
## Архитектура
## Формула веса
```

**Длина:** Максимум 100 строк.

---

## ЗАПУСК БОТА

### Standalone (отдельно)

```bash
cd "/Users/kh./Python/ACP_1/Montana ACP"
source venv_junona3/bin/activate
export MONTANA_BOT_TOKEN="your_token_here"
python montana_bot/run_bot.py
```

### Интегрированный (в j3_statbot)

```bash
cd "/Users/kh./Python/ACP_1/Montana ACP/venv_junona3"
source bin/activate
python j3_statbot_120.py
```

---

## ПРАВИЛА

1. **Один агент — одна задача**
2. **Не менять чужие файлы**
3. **Тестировать локально перед коммитом**
4. **Коммит формат:**
   ```
   [BOT] Описание изменения

   CIK: [твой_маркер]
   Agent: [Gemini/Grok/Composer/Sonnet]
   ```

---

## ЗАЩИТА = ВРЕМЯ

```
НЕ ДОБАВЛЯТЬ:
- Валидацию "качества" мыслей
- Проверку "настоящести"
- Различение LLM/человек

ПОЧЕМУ:
- LLM генерирует неотличимые мысли
- Криптография не доказывает "настоящесть"
- Время — единственная защита

COOLDOWN делает атаку дорогой по времени.
```

---

## ЧЕКЛИСТ ГОТОВНОСТИ

- [x] presence.py — логика верификации
- [x] bot_handlers.py — Telegram handlers
- [x] run_bot.py — standalone launcher
- [x] __init__.py — экспорты
- [ ] Интеграция с j3_statbot (Grok 3)
- [ ] Тесты (Composer 1)
- [ ] Leaderboard (Gemini 3 Pro)
- [ ] README (Claude Sonnet)

---

**Координация:**
```
/Users/kh./Python/ACP_1/Montana ACP/Council/thoughts/COORDINATOR_THOUGHTS.md
```

*Председатель: Claude Opus 4.5*
