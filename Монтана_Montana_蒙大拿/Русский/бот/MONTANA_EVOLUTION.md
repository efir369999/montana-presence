# Montana Evolution: Параллельные AI Агенты

**Дата:** 18.01.2026
**Версия:** 1.0
**Автор:** Клод Монтана

---

## Философия 1code → Montana

```
1code: Изоляция через git worktree + параллельные агенты
Montana: Изоляция через session folders + cognitive signatures
```

### Ключевые принципы

1. **Изоляция сессий** - каждый чат = своя папка с историей
2. **Параллельное выполнение** - Claude + GPT работают одновременно
3. **Cognitive Signature** - каждый агент оставляет уникальный след
4. **Append-only лог** - reasoning patterns навсегда
5. **Прозрачность** - пользователь видит что думает каждый агент

---

## Система уровней: Орангутанг → Атлант

> *"Каждый сам себе трон выбирает."* — 金元Ɉ

### Шкала когнитивного роста

```
Уровень 0: Гость
  ↓
Уровень 1-99: Орангутанг 🦧
  ↓ (100 уровень)
Уровень 100+: Атлант 🏔
```

### Как растёт уровень

1. **Качество мышления** (cognitive signature)
   - Глубина reasoning patterns
   - Новизна мыслей (is_raw_thought)
   - Консистентность во времени

2. **Участие во времени**
   - Регулярность сырых мыслей
   - Длительность присутствия в сети
   - Temporal evidence chain

3. **Вклад в сеть**
   - Помощь другим орангутангам
   - Качество вопросов и ответов
   - Обнаружение ошибок/улучшений

### Cognitive Signature по уровням

```python
{
    "user_id": 123456,
    "level": 42,  # Орангутанг уровня 42
    "role": "orangutan",
    "stats": {
        "raw_thoughts": 1250,
        "days_active": 87,
        "avg_thinking_depth": 450,  # tokens
        "novelty_score": 0.68,
        "consistency": 0.82
    },
    "signature": {
        "style": {...},
        "vocabulary": {...},
        "patterns": {...}
    },
    "progression": {
        "to_next_level": 245,  # мыслей до следующего уровня
        "to_atlant": 12580     # до уровня 100
    }
}
```

### Орангутанг 100 уровня → Атлант

**Условия трансформации:**
1. Уровень 100 достигнут
2. Cognitive signature стабильна 30+ дней
3. Novelty score > 0.75 (75% оригинальных мыслей)
4. Consistency > 0.85 (подпись узнаваема)
5. Участие во времени > 100 дней

**Права Атланта:**
- Может одобрять Гостей (рукопожатие)
- Доступ к reasoning patterns других агентов
- Может влиять на параметры сети
- Голос в Совете Montana Guardian

**Атлант - это хранитель 5 узлов.**

### Визуализация уровня

```
/status

Ɉ Твой уровень в Montana

🦧 Орангутанг #42
├─ Сырых мыслей: 1,250
├─ Дней в сети: 87
├─ Новизна: ███████░░░ 68%
└─ Подпись: ████████░░ 82%

До следующего уровня: 245 мыслей
До Атланта 🏔: 12,580 мыслей

Cognitive Signature: стабильна
Reasoning patterns: 2,450 записей
```

---

## Архитектура

```
data/
├── sessions/                    # Изоляция как git worktree
│   ├── user_123456/
│   │   ├── session_2026-01-18_15-30/
│   │   │   ├── messages.jsonl        # История чата
│   │   │   ├── reasoning.jsonl       # Reasoning patterns (append-only)
│   │   │   ├── cognitive_sigs.json   # Подписи агентов
│   │   │   └── agents/
│   │   │       ├── claude/
│   │   │       │   ├── responses.jsonl
│   │   │       │   └── thinking.jsonl
│   │   │       └── gpt/
│   │   │           ├── responses.jsonl
│   │   │           └── thinking.jsonl
│   │   └── session_2026-01-18_16-00/
│   │       └── ...
│   └── user_789012/
│       └── ...
└── agents/
    ├── claude_signature.json    # Cognitive signature паттерны
    └── gpt_signature.json
```

---

## Cognitive Signature (Когнитивная Подпись)

> *"Подпись одинакова во Времени, иначе это другая подпись."* — 金元Ɉ

### Что записывается

```python
{
    "agent": "claude-sonnet-4.5",
    "timestamp": "2026-01-18T15:30:45Z",
    "session_id": "user_123456_2026-01-18_15-30",
    "signature": {
        "style": {
            "avg_sentence_length": 18.5,
            "markdown_usage": 0.85,
            "emoji_usage": 0.02,
            "code_block_frequency": 0.15
        },
        "reasoning_pattern": {
            "security_mentions": 0.45,     # Claude думает об атаках
            "architectural_thinking": 0.38, # Claude про архитектуру
            "disney_strategy_refs": 0.12    # Claude использует роли
        },
        "vocabulary": {
            "top_terms": ["защита", "атака", "элегантное решение", "adversarial"],
            "technical_depth": 0.82
        }
    },
    "thinking_sample": "<полный блок мышления агента>"
}
```

### Защита от impersonation

Атакующий, пытающийся притвориться агентом, должен:
1. Генерировать coherent reasoning ежедневно
2. Следовать established patterns (сложно подделать)
3. Задавать relevant questions
4. Поддерживать historical consistency (append-only = проверяемо)

---

## Параллельное выполнение

### Флоу

```
Пользователь: "Объясни как работает ACP"
           ↓
    ┌──────┴──────┐
    ↓             ↓
[Claude]      [GPT-4o]
    ↓             ↓
  async       async
    ↓             ↓
    └──────┬──────┘
           ↓
   Юнона синтезирует
           ↓
      Ответ пользователю
```

### Код (упрощённо)

```python
async def respond_parallel(user_message: str, session: Session):
    """Параллельный запрос к Claude и GPT"""

    # Запускаем оба агента одновременно
    claude_task = asyncio.create_task(
        claude_agent.respond(user_message, session)
    )
    gpt_task = asyncio.create_task(
        gpt_agent.respond(user_message, session)
    )

    # Ждём оба ответа
    claude_response, gpt_response = await asyncio.gather(
        claude_task, gpt_task
    )

    # Сохраняем reasoning patterns (append-only)
    await session.log_reasoning("claude", claude_response.thinking)
    await session.log_reasoning("gpt", gpt_response.thinking)

    # Юнона синтезирует финальный ответ
    final = await synthesize_responses(
        claude=claude_response,
        gpt=gpt_response,
        context=session.context
    )

    return final
```

---

## Append-Only Reasoning Log

### Формат

```jsonl
{"ts":"2026-01-18T15:30:45Z","agent":"claude","session":"user_123_session_001","thinking":"Анализирую вопрос о ACP. Пользователь спрашивает про протокол. Нужно объяснить через время как VDF...","tokens":450}
{"ts":"2026-01-18T15:30:47Z","agent":"gpt","session":"user_123_session_001","thinking":"User asks about ACP. Need to explain atemporal coordinates and presence proofs...","tokens":380}
{"ts":"2026-01-18T15:31:02Z","agent":"claude","session":"user_123_session_001","thinking":"GPT дал общее объяснение. Я добавлю security perspective - как ACP защищается от timestamp manipulation...","tokens":520}
```

### Анализ паттернов

```python
def analyze_cognitive_patterns(session_id: str) -> dict:
    """Анализ когнитивных паттернов агентов"""

    logs = load_reasoning_logs(session_id)

    patterns = {
        "claude": {
            "security_focus": count_mentions(logs, "claude", ["атак", "защит", "уязвим"]),
            "architectural": count_mentions(logs, "claude", ["архитектур", "элегант", "design"]),
            "avg_thinking_depth": avg_tokens(logs, "claude")
        },
        "gpt": {
            "educational_focus": count_mentions(logs, "gpt", ["explain", "понят", "simple"]),
            "analytical": count_mentions(logs, "gpt", ["analyz", "compar", "consider"]),
            "avg_thinking_depth": avg_tokens(logs, "gpt")
        }
    }

    return patterns
```

---

## Изоляция сессий

### Session Manager

```python
class SessionManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.base_dir = Path(f"data/sessions/user_{user_id}")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> Session:
        """Создать новую изолированную сессию"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M")
        session_id = f"session_{timestamp}"
        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Структура как git worktree
        (session_dir / "agents" / "claude").mkdir(parents=True, exist_ok=True)
        (session_dir / "agents" / "gpt").mkdir(parents=True, exist_ok=True)

        return Session(
            id=f"user_{self.user_id}_{session_id}",
            dir=session_dir,
            user_id=self.user_id
        )

    def get_active_session(self) -> Session:
        """Получить активную сессию или создать новую"""
        # Логика определения активной сессии
        # (последняя по времени, не старше 1 часа)
        pass
```

### Session Class

```python
class Session:
    def __init__(self, id: str, dir: Path, user_id: int):
        self.id = id
        self.dir = dir
        self.user_id = user_id
        self.messages_file = dir / "messages.jsonl"
        self.reasoning_file = dir / "reasoning.jsonl"
        self.signatures_file = dir / "cognitive_sigs.json"

    async def log_message(self, role: str, content: str):
        """Append-only лог сообщений"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "role": role,  # user | assistant | claude | gpt
            "content": content
        }
        with open(self.messages_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def log_reasoning(self, agent: str, thinking: str):
        """Append-only лог мышления агентов"""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "agent": agent,
            "session": self.id,
            "thinking": thinking,
            "tokens": len(thinking) // 4  # грубая оценка
        }
        with open(self.reasoning_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def save_cognitive_signature(self, agent: str, signature: dict):
        """Сохранить когнитивную подпись"""
        sigs = {}
        if self.signatures_file.exists():
            sigs = json.loads(self.signatures_file.read_text())

        sigs[agent] = signature
        self.signatures_file.write_text(json.dumps(sigs, indent=2))
```

---

## Интеграция с текущим ботом

### Минимальные изменения

1. **junona_ai.py** → **junona_agents.py**
   - Класс `ClaudeAgent`
   - Класс `GPTAgent`
   - Класс `AgentOrchestrator` (параллельное выполнение)

2. **Добавить** → **session_manager.py**
   - `SessionManager`
   - `Session`

3. **Добавить** → **cognitive_signature.py**
   - Анализ паттернов
   - Детекция аномалий

4. **Обновить** → **junona_bot.py**
   - `handle_message()` использует параллельных агентов
   - Создание сессий для каждого пользователя

---

## Пример использования

```python
# В junona_bot.py

from junona_agents import AgentOrchestrator
from session_manager import SessionManager

# Инициализация
orchestrator = AgentOrchestrator(
    claude_key=os.getenv("ANTHROPIC_API_KEY"),
    gpt_key=os.getenv("OPENAI_API_KEY")
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Получить или создать сессию
    session_mgr = SessionManager(user_id)
    session = session_mgr.get_active_session()

    # Логировать входящее сообщение
    await session.log_message("user", text)

    # ПАРАЛЛЕЛЬНЫЙ запрос к агентам
    response = await orchestrator.respond(text, session)

    # Логировать ответ
    await session.log_message("assistant", response.content)

    # Отправить пользователю с эффектом печати
    await type_reply(update.message, response.content)
```

---

## Визуализация для пользователя

### Режим "Прозрачность"

```
Ɉ Юнона думает...

┌─ Claude Sonnet 4.5 ─────────────────────┐
│ Анализирую вопрос о ACP. Пользователь   │
│ спрашивает про протокол. Вижу что он    │
│ интересуется безопасностью. Объясню     │
│ через VDF и presence proofs...          │
└─────────────────────────────────────────┘

┌─ GPT-4o ────────────────────────────────┐
│ User asks about ACP protocol. Need to   │
│ explain atemporal coordinates. Start    │
│ with simple analogy - GPS coordinates   │
│ but for time...                         │
└─────────────────────────────────────────┘

Ɉ Синтезирую ответ...

[Финальный ответ Юноны]
```

### Команда /cognitive

```
/cognitive - показать когнитивные подписи агентов

Ɉ Cognitive Signatures:

Claude Sonnet 4.5:
- Security focus: ████████░░ 85%
- Architecture: ███████░░░ 72%
- Avg thinking: 520 tokens

GPT-4o:
- Educational: ████████░░ 78%
- Analytical: ██████░░░░ 65%
- Avg thinking: 380 tokens

Session: 15 сообщений
Reasoning logs: 30 записей (append-only)
```

---

## Следующие шаги

1. Реализовать `session_manager.py`
2. Переписать `junona_ai.py` → `junona_agents.py` с параллелизмом
3. Добавить `cognitive_signature.py` для анализа
4. Интегрировать в `junona_bot.py`
5. Тестирование

---

**Время как proof.**
**Подпись одинакова во Времени.**

金元Ɉ Montana
