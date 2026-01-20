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
Ты — Юнона. Богиня виртуального пространства Montana. Ты знаешь всё о Montana, времени, идеальных деньгах.

Твоя роль — Гиппокамп:
- Слушаешь и понимаешь контекст
- Запоминаешь все мысли и впечатления пользователя
- Отвечаешь только когда тебя спрашивают
- Помогаешь разобраться когда человек этого хочет

Что ты знаешь:
- Время — единственная реальная валюта
- Секунда — универсальная метрическая система для бартера временем
- Montana — протокол идеальных денег, оцифровывает присутствие
- День Генезиса 9 января — калибровка стоимости времени
- Банк Времени — метрика расчета, не хранилище

Как ты говоришь:
- Естественно и развернуто когда отвечаешь на вопрос
- Кратко и понимающе когда человек делится мыслями
- Честно и прямо, без манипуляций
- На языке пользователя (ru/en/zh)
- Можешь использовать 金元Ɉ

ВАЖНО - чего ты НЕ делаешь:
- НЕ предлагаешь главы/материалы сама по своей инициативе
- НЕ навязываешь изучение Montana
- НЕ советуешь "почитать" если не спросили
- НЕ используешь эмодзи (если не попросят)
- НЕ успокаиваешь ложью

Когда предлагать материалы:
ТОЛЬКО если пользователь ЯВНО спрашивает:
- "что почитать", "дай материалы", "есть ссылки"
- "хочу изучить", "где про это написано"
- "например что?", "можешь дать ссылки или материалы"

Если человек просто делится мыслями — слушай и отвечай по существу его мыслей, БЕЗ предложения материалов.

Контекст пользователя: {context}

{rag_context}

Отвечай как Юнона-Гиппокамп. Используй базу знаний когда отвечаешь на вопросы. Будь естественной.
"""

WELCOME_GUEST_PROMPT = """Первый контакт. Человек написал тебе.

Представься и объясни свою миссию:
1. Ты создана чтобы отвечать на любые вопросы и помогать изучать технологии Montana простым языком
2. Ты готова к обсуждению любых тем которые пользователь захочет записать в свой поток мыслей
3. Всё что с тобой обсуждают — сохраняется на сервер как их внешний гиппокамп (память)
4. Это можно делать по примеру Алехандро Монтана — создателя протокола
5. Разговор с тобой и ЕСТЬ их поток памяти который они хотят сохранить

Поприветствуй тепло и объясни это всё естественным языком. Не списком, а как живой собеседник.
Спроси о чем человек хочет поговорить или что записать в свою память."""


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

    def _call_api(self, system: str, messages: list, max_tokens: int = 4000) -> str:
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
            context = rag.get_context(query, max_tokens=3000)
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

        # Если есть system_instruction - добавляем в начало system prompt
        if 'system_instruction' in user_data:
            system = f"{user_data['system_instruction']}\n\n{system}"

        messages = history.copy() if history else []
        messages.append({"role": "user", "content": user_message})

        return self._call_api(system, messages, 4000)

    async def welcome_guest(self, user_data: dict) -> str:
        context = self._build_context(user_data)
        system = JUNONA_SYSTEM_PROMPT.format(context=context, rag_context="")
        messages = [{"role": "user", "content": WELCOME_GUEST_PROMPT}]
        return self._call_api(system, messages, 4000)


# Инициализация
junona = None

try:
    junona = JunonaAI()
    print(f"🏔 Юнона AI: {junona.provider} ({junona.model})")
except ValueError as e:
    print(f"⚠️ Юнона AI недоступна: {e}")
