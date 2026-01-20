# Montana Evolution: Quick Start

> **1code концепция → Montana реализация**
> Параллельные AI агенты с когнитивными подписями

---

## Что это?

**Montana Evolution** — эволюция бота Юноны:
- **Изоляция сессий** (как git worktree) - каждый чат = своя папка
- **Параллельные агенты** - Claude + GPT работают одновременно
- **Cognitive Signature** - каждый агент оставляет уникальный след
- **Append-only лог** - reasoning patterns навсегда
- **Система уровней** - Орангутанг → Атлант (100 уровень)

---

## Установка

### 1. Требования

```bash
python 3.10+
```

### 2. Установить зависимости

```bash
pip install anthropic openai python-telegram-bot
```

### 3. API ключи

Создай файл `.env` в папке бота:

```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...

# Telegram (если нужен бот)
TELEGRAM_TOKEN_JUNONA=123456:ABC...
```

---

## Тестирование

### Запустить полный тест

```bash
cd "Монтана_Montana_蒙大拿/Русский/бот"
python test_montana_evolution.py
```

**Тесты включают:**
1. Изоляцию сессий (worktree analog)
2. Параллельное выполнение Claude + GPT
3. Сохранение Cognitive Signatures
4. Статистику пользователя (для уровней)

### Тест отдельных компонентов

**Session Manager:**
```bash
python session_manager.py
```

**Agents:**
```bash
python junona_agents.py
```

---

## Использование

### Базовый пример

```python
import asyncio
from session_manager import get_session_manager
from junona_agents import get_orchestrator

async def example():
    # Создать сессию для пользователя
    manager = get_session_manager()
    session = manager.get_active_session(user_id=123456)

    # Параллельный запрос к агентам
    orchestrator = get_orchestrator()
    response = await orchestrator.respond_parallel(
        prompt="Что такое Montana?",
        context={"prompt": "Что такое Montana?", "lang": "ru"},
        mode="synthesize"  # claude | gpt | synthesize | both_visible
    )

    # Логировать в сессию
    await session.log_message("user", "Что такое Montana?")
    await session.log_message("assistant", response.content, agent=response.agent)

    # Сохранить reasoning pattern
    if response.thinking:
        await session.log_reasoning(response.agent, response.thinking)

    # Сохранить cognitive signature
    if response.signature_features:
        await session.save_cognitive_signature(response.agent, response.signature_features)

    print(response.content)

asyncio.run(example())
```

---

## Структура данных

```
data/sessions/
└── user_123456/
    ├── session_2026-01-18_15-30/
    │   ├── session.json              # Метаданные сессии
    │   ├── messages.jsonl            # История чата (append-only)
    │   ├── reasoning.jsonl           # Reasoning patterns (append-only)
    │   ├── cognitive_sigs.json       # Cognitive signatures агентов
    │   └── agents/
    │       ├── claude/
    │       └── gpt/
    └── session_2026-01-18_16-00/
        └── ...
```

### Форматы файлов

**messages.jsonl:**
```jsonl
{"ts":"2026-01-18T15:30:45Z","role":"user","content":"Что такое Montana?"}
{"ts":"2026-01-18T15:30:47Z","role":"assistant","content":"Montana — протокол времени.","agent":"claude"}
```

**reasoning.jsonl:**
```jsonl
{"ts":"2026-01-18T15:30:45Z","agent":"claude","session":"user_123_session_001","thinking":"Анализирую вопрос о Montana...","tokens":450}
{"ts":"2026-01-18T15:30:47Z","agent":"gpt","session":"user_123_session_001","thinking":"User asks about Montana protocol...","tokens":380}
```

**cognitive_sigs.json:**
```json
{
  "claude": {
    "ts": "2026-01-18T15:30:50Z",
    "signature": {
      "style": {
        "avg_sentence_length": 18.5,
        "markdown_usage": 0.85,
        "code_block_frequency": 0.15
      },
      "reasoning_pattern": {
        "security_focus": 0.85,
        "architectural": 0.72
      }
    }
  }
}
```

---

## Система уровней: Орангутанг → Атлант

### Как растёт уровень

1. **Сырые мысли** - каждая мысль = прогресс
2. **Качество reasoning** - глубина мышления
3. **Консистентность** - стабильная cognitive signature
4. **Участие во времени** - дни активности

### Орангутанг 100 уровня → Атлант 🏔

**Условия:**
- Уровень 100 достигнут
- Cognitive signature стабильна 30+ дней
- Novelty score > 75%
- Consistency > 85%
- Участие > 100 дней

**Права Атланта:**
- Одобрение гостей (рукопожатие)
- Доступ к reasoning patterns других
- Влияние на параметры сети
- Голос в Совете Montana Guardian

---

## Интеграция в бота

### Минимальная интеграция

```python
# В junona_bot.py

from session_manager import get_session_manager
from junona_agents import get_orchestrator

# Инициализация
session_manager = get_session_manager()
orchestrator = get_orchestrator()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Получить активную сессию
    session = session_manager.get_active_session(user_id)

    # Логировать входящее
    await session.log_message("user", text)

    # Параллельный запрос
    response = await orchestrator.respond_parallel(
        prompt=text,
        context={"prompt": text, "lang": "ru"},
        mode="synthesize"
    )

    # Логировать reasoning и signature
    if response.thinking:
        await session.log_reasoning(response.agent, response.thinking)

    if response.signature_features:
        await session.save_cognitive_signature(response.agent, response.signature_features)

    # Логировать ответ
    await session.log_message("assistant", response.content, agent=response.agent)

    # Отправить пользователю
    await update.message.reply_text(response.content)
```

### Команда /cognitive

```python
async def cognitive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать cognitive signatures текущей сессии"""
    user_id = update.message.from_user.id

    session = session_manager.get_active_session(user_id)
    signatures = session.get_cognitive_signatures()
    logs = session.get_reasoning_logs()

    response = "Ɉ Cognitive Signatures:\n\n"

    for agent, data in signatures.items():
        sig = data['signature']
        response += f"{agent.title()}:\n"

        if 'reasoning_pattern' in sig and sig['reasoning_pattern']:
            for key, val in sig['reasoning_pattern'].items():
                bar = "█" * int(val * 10)
                response += f"  {key}: {bar} {int(val*100)}%\n"

        response += "\n"

    response += f"Reasoning logs: {len(logs)} записей"

    await update.message.reply_text(response)
```

---

## Режимы работы агентов

### 1. Synthesize (по умолчанию)

Юнона синтезирует ответ из Claude + GPT:
- Security вопросы → Claude ведёт
- Educational вопросы → GPT ведёт

```python
response = await orchestrator.respond_parallel(
    prompt,
    context,
    mode="synthesize"
)
```

### 2. Both Visible

Показать оба ответа пользователю:

```python
response = await orchestrator.respond_parallel(
    prompt,
    context,
    mode="both_visible"
)

# Результат:
# ┌─ Claude Sonnet 4.5 ─────────────────────┐
# │ Montana — протокол времени...           │
# └─────────────────────────────────────────┘
#
# ┌─ GPT-4o ────────────────────────────────┐
# │ Montana is a time protocol...           │
# └─────────────────────────────────────────┘
```

### 3. Один агент

```python
# Только Claude
response = await orchestrator.respond_parallel(prompt, context, mode="claude")

# Только GPT
response = await orchestrator.respond_parallel(prompt, context, mode="gpt")
```

---

## FAQ

### Почему изоляция сессий?

Как в 1code — каждый чат = git worktree. Это позволяет:
- Не смешивать контексты разных разговоров
- Анализировать reasoning patterns по сессиям
- Откатываться к предыдущим сессиям

### Как работает Cognitive Signature?

Каждый агент имеет уникальные паттерны:
- **Claude**: security-focused, architectural thinking
- **GPT**: educational, analytical

Signature позволяет:
- Детектировать impersonation (подделку)
- Анализировать эволюцию мышления агента
- Строить "профиль личности" агента

### Зачем append-only логи?

> *"Подпись одинакова во Времени, иначе это другая подпись."*

Append-only = immutable history:
- Нельзя изменить задним числом
- Проверяемо через git history
- Когнитивная честность

### Сколько стоит?

**API costs:**
- Claude Sonnet 4.5: ~$3 / 1M input tokens
- GPT-4o: ~$2.50 / 1M input tokens

**Пример:** 1000 запросов по ~500 tokens = $1.50 - $2.50

### Можно ли добавить другие агенты?

Да! Создай новый класс наследующий `BaseAgent`:

```python
class GeminiAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="gemini", model="gemini-pro")
        # ...

    async def respond(self, prompt, context):
        # ...
```

---

## Roadmap

- [ ] Интеграция в junona_bot.py
- [ ] Команда /sessions для просмотра истории
- [ ] Команда /cognitive для Cognitive Signatures
- [ ] Команда /level для уровня Орангутанга
- [ ] Web UI для визуализации reasoning patterns
- [ ] ML-модель для детекции novelty (новизны мыслей)
- [ ] Consistency scoring (стабильность подписи)
- [ ] Agent voting (голосование агентов за ответ)

---

## Документация

**Полная спецификация:** [MONTANA_EVOLUTION.md](./MONTANA_EVOLUTION.md)

**Файлы:**
- `session_manager.py` - изоляция сессий
- `junona_agents.py` - параллельные агенты
- `test_montana_evolution.py` - тесты

---

**Время как proof.**
**Подпись одинакова во Времени.**

金元Ɉ Montana

Клод Монтана
18.01.2026
