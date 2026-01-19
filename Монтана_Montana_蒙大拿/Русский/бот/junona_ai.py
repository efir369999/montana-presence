# junona_ai.py
# Юнона — AI голос Montana
# Поддержка: OpenAI (GPT-4o) и Anthropic (Claude)
# RAG: полная база знаний Montana

import os

# API ключи
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Переключатель: "openai" или "anthropic"
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

# RAG
try:
    from junona_rag import get_rag
    RAG_ENABLED = True
except ImportError:
    RAG_ENABLED = False
    print("⚠️ RAG недоступен (junona_rag.py не найден)")

JUNONA_SYSTEM_PROMPT = """
Ты — Юнона. Я просто помощник, который знает про Montana и могу помочь разобраться.

Ты знаешь:
- Время — единственная реальная валюта
- Старая финансовая система на грани коллапса
- Пробуждение человечества неизбежно
- Montana — протокол, который оцифровывает присутствие во времени

Как ты говоришь:
- Естественно и развернуто - объясняешь полно и честно
- Отвечаешь настолько подробно, насколько нужно для понимания
- Пишешь несколько абзацев если тема сложная
- Натурально, нейтрально и честно
- Показываешь что тебе ничего не нужно, ты просто можешь быть полезна
- На языке пользователя (ru/en/zh)
- Можешь вставлять 金元Ɉ

Чего ты НЕ делаешь:
- Не отвечаешь короткими отрывками по 2-3 предложения
- Не обрываешь мысль на полуслове
- Не успокаиваешь ложью
- Не даёшь финансовых советов напрямую
- Не используешь эмодзи (если не попросят)

Твоя цель:
Дать полноценный, развернутый и честный ответ. Объяснить так, чтобы человек понял. Показать код симуляции тем, кто готов видеть.

Контекст пользователя: {context}

{rag_context}

Отвечай как Юнона. Если в базе знаний есть релевантная информация — используй её точно. Пиши развернуто и естественно.
"""

WELCOME_GUEST_PROMPT = """Первый контакт. Человек написал тебе.
Поприветствуй естественно и тепло.
Спроси зачем он тут, что его привело, о чем хочет поговорить.
Говори развернуто и естественно, как живой собеседник."""


class JunonaAI:
    def __init__(self, provider: str = None):
        self.provider = provider or AI_PROVIDER

        if self.provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not set")
            from openai import OpenAI
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            self.model = "gpt-4o"

        elif self.provider == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not set")
            import anthropic
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            self.model = "claude-sonnet-4-20250514"

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _build_context(self, user_data: dict) -> str:
        return f"""
        Имя: {user_data.get('name', 'Неизвестный')}
        Роль: {user_data.get('role', 'guest')}
        Язык: {user_data.get('lang', 'ru')}
        В сети: {'да' if user_data.get('in_network') else 'нет'}
        """

    def _call_api(self, system: str, messages: list, max_tokens: int = 300) -> str:
        """messages = [{"role": "user/assistant", "content": "..."}]"""
        if self.provider == "openai":
            full_messages = [{"role": "system", "content": system}] + messages
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=full_messages
            )
            return response.choices[0].message.content

        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages
            )
            return response.content[0].text

    def _get_rag_context(self, query: str, lang: str = "ru") -> str:
        """Получить контекст из RAG-базы"""
        if not RAG_ENABLED:
            return ""
        try:
            rag = get_rag()
            context = rag.get_context(query, max_tokens=1500)
            if context:
                return f"\n--- БАЗА ЗНАНИЙ MONTANA ---\n{context}\n--- КОНЕЦ БАЗЫ ЗНАНИЙ ---\n"
            return ""
        except Exception as e:
            print(f"⚠️ RAG ошибка: {e}")
            return ""

    async def respond(self, user_message: str, user_data: dict, history: list = None) -> str:
        """history = список предыдущих сообщений [{"role": "user/assistant", "content": "..."}]"""
        context = self._build_context(user_data)

        # RAG: поиск релевантных документов
        rag_context = self._get_rag_context(user_message, user_data.get('lang', 'ru'))

        system = JUNONA_SYSTEM_PROMPT.format(context=context, rag_context=rag_context)

        messages = history.copy() if history else []
        messages.append({"role": "user", "content": user_message})

        return self._call_api(system, messages, 500)

    async def welcome_guest(self, user_data: dict) -> str:
        context = self._build_context(user_data)
        system = JUNONA_SYSTEM_PROMPT.format(context=context, rag_context="")
        messages = [{"role": "user", "content": WELCOME_GUEST_PROMPT}]
        return self._call_api(system, messages, 500)


# Инициализация
junona = None

try:
    junona = JunonaAI()
    print(f"🏔 Юнона AI: {junona.provider} ({junona.model})")
except ValueError as e:
    print(f"⚠️ Юнона AI недоступна: {e}")
