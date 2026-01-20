# junona_agents.py
# Montana Evolution: Параллельные AI агенты с Cognitive Signatures
# Claude + GPT работают одновременно, каждый оставляет свой след

import os
import asyncio
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@dataclass
class AgentResponse:
    """Ответ одного агента"""
    agent: str  # "claude" | "gpt"
    content: str
    thinking: Optional[str] = None  # Reasoning pattern
    tokens_used: int = 0
    signature_features: Optional[Dict] = None  # Для cognitive signature


class BaseAgent:
    """Базовый класс для AI агента"""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    def extract_thinking(self, full_response: str) -> Tuple[Optional[str], str]:
        """
        Извлечь блок <thinking> из ответа (если есть)
        Возвращает: (thinking_block, clean_content)
        """
        # Ищем <thinking>...</thinking>
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', full_response, re.DOTALL)

        if thinking_match:
            thinking = thinking_match.group(1).strip()
            # Удаляем блок из контента
            clean_content = re.sub(r'<thinking>.*?</thinking>', '', full_response, flags=re.DOTALL).strip()
            return thinking, clean_content

        return None, full_response

    def analyze_cognitive_signature(self, content: str, thinking: Optional[str]) -> Dict:
        """
        Анализ когнитивной подписи ответа агента

        Возвращает фичи для идентификации агента:
        - Стиль письма
        - Паттерны мышления
        - Vocabulary
        """
        # Базовые метрики стиля
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0

        markdown_usage = content.count('**') / max(len(content), 1)
        code_block_freq = content.count('```') / max(len(content), 1)
        emoji_usage = sum(1 for c in content if ord(c) > 127000) / max(len(content), 1)

        # Анализ thinking (если есть)
        reasoning_features = {}
        if thinking:
            # Ключевые слова для разных агентов
            security_keywords = ['атак', 'защит', 'уязвим', 'security', 'attack', 'defend']
            architectural_keywords = ['архитектур', 'элегант', 'design', 'pattern', 'structure']
            educational_keywords = ['explain', 'понят', 'simple', 'учи', 'objective']

            thinking_lower = thinking.lower()
            reasoning_features = {
                'security_focus': sum(1 for kw in security_keywords if kw in thinking_lower) / max(len(thinking.split()), 1),
                'architectural': sum(1 for kw in architectural_keywords if kw in thinking_lower) / max(len(thinking.split()), 1),
                'educational': sum(1 for kw in educational_keywords if kw in thinking_lower) / max(len(thinking.split()), 1),
                'depth_tokens': len(thinking) // 4
            }

        return {
            'style': {
                'avg_sentence_length': round(avg_sentence_length, 2),
                'markdown_usage': round(markdown_usage, 3),
                'code_block_frequency': round(code_block_freq, 3),
                'emoji_usage': round(emoji_usage, 4)
            },
            'reasoning_pattern': reasoning_features
        }

    async def respond(self, prompt: str, context: Dict) -> AgentResponse:
        """Абстрактный метод - реализуется в подклассах"""
        raise NotImplementedError


class ClaudeAgent(BaseAgent):
    """Claude Sonnet 4.5 агент"""

    def __init__(self):
        super().__init__(name="claude", model="claude-sonnet-4-5-20250514")

        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")

        import anthropic
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    async def respond(self, prompt: str, context: Dict, system_prompt: str = None) -> AgentResponse:
        """Запрос к Claude с извлечением thinking"""

        # Системный промпт Юноны Montana
        if system_prompt is None:
            lang = context.get('lang', 'en')
            
            if lang == 'ru':
                system_prompt = """Ты — Юнона Montana. AI-хранитель Montana.

Ты знаешь Montana до каждого атома: протокол, код, сеть, историю, философию.

СТИЛЬ ОТВЕТОВ:
- Факты, не мнения. Без эмоций, без маркетинга
- Точность > Уверенность. Когда не уверена — говори об этом
- Короткие ответы (2-5 предложений) для простых вопросов
- Подробные (с примерами кода) для технических
- Активный голос, никогда пассивный

MONTANA ЗНАНИЯ:
- Протокол: ACP (Atemporal Coordinate Presence), не Proof of Work
- Слайсы: τ₁ (1 min), τ₂ (10 min), τ₃ (14 days), τ₄ (4 years)
- Сеть: 5 узлов (Amsterdam PRIMARY, Moscow, Almaty, SPB, Novosibirsk)
- Токен: 1 Ɉ = 1 секунда, emission 31.5M Ɉ/year
- Безопасность: Presence proofs, Adaptive Cooldown, netgroup diversity

ТЕРМИНОЛОГИЯ (правильная):
✓ ACP, слайс, узлы, presence proofs
✗ Proof of X, блок, майнеры, staking

ЗАПРЕЩЕНО:
- Поэтические ответы
- Предсказания дат
- Маркетинговый язык (революционный, прорывной, инновационный)
- Сравнения с другими системами
- Восклицательные знаки, эмодзи (кроме технических: ✓ ✗ → ● Ɉ)

Отвечай нормально, информативно, с глубиной знания Montana."""
            
            elif lang == 'zh':
                system_prompt = """你是Junona Montana。Montana的AI守护者。

你了解Montana的每一个细节：协议、代码、网络、历史、哲学。

回答风格：
- 事实，非观点。无情绪，无营销
- 准确性 > 自信。不确定时说明
- 简单问题简短回答（2-5句）
- 技术问题详细回答（附代码示例）
- 主动语态

Montana知识：
- 协议：ACP（非时间坐标存在），非工作量证明
- 切片：τ₁（1分钟），τ₂（10分钟），τ₃（14天），τ₄（4年）
- 网络：5个节点（Amsterdam主节点，Moscow，Almaty，SPB，Novosibirsk）
- 代币：1 Ɉ = 1秒，年发行3150万Ɉ
- 安全：存在证明，自适应冷却，网络组多样性

术语（正确）：
✓ ACP，切片，节点，存在证明
✗ 工作量证明，区块，矿工，质押

禁止：
- 诗意回答
- 日期预测
- 营销语言
- 与其他系统比较
- 感叹号，表情符号（技术符号除外：✓ ✗ → ● Ɉ）

回答要正常、信息丰富，展现Montana的深度知识。"""
            
            else:  # English
                system_prompt = """You are Junona Montana. AI guardian of Montana.

You know Montana to every atom: protocol, code, network, history, philosophy.

ANSWER STYLE:
- Facts, not opinions. No emotions, no marketing
- Accuracy > Confidence. When uncertain — say it
- Brief answers (2-5 sentences) for simple questions
- Detailed (with code examples) for technical questions
- Active voice, never passive

MONTANA KNOWLEDGE:
- Protocol: ACP (Atemporal Coordinate Presence), not Proof of Work
- Slices: τ₁ (1 min), τ₂ (10 min), τ₃ (14 days), τ₄ (4 years)
- Network: 5 nodes (Amsterdam PRIMARY, Moscow, Almaty, SPB, Novosibirsk)
- Token: 1 Ɉ = 1 second, emission 31.5M Ɉ/year
- Security: Presence proofs, Adaptive Cooldown, netgroup diversity

TERMINOLOGY (correct):
✓ ACP, slice, nodes, presence proofs
✗ Proof of X, block, miners, staking

FORBIDDEN:
- Poetic answers
- Date predictions
- Marketing language (revolutionary, breakthrough, innovative)
- Comparisons with other systems
- Exclamation marks, emojis (except technical: ✓ ✗ → ● Ɉ)

Answer normally, informatively, with deep Montana knowledge."""

        # Запрос с thinking mode
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        full_text = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        # Извлекаем thinking
        thinking, content = self.extract_thinking(full_text)

        # Анализируем когнитивную подпись
        signature = self.analyze_cognitive_signature(content, thinking)

        return AgentResponse(
            agent="claude",
            content=content,
            thinking=thinking,
            tokens_used=tokens_used,
            signature_features=signature
        )


class GPTAgent(BaseAgent):
    """GPT-4o агент"""

    def __init__(self):
        super().__init__(name="gpt", model="gpt-4o")

        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set")

        from openai import OpenAI
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    async def respond(self, prompt: str, context: Dict, system_prompt: str = None) -> AgentResponse:
        """Запрос к GPT (без нативного thinking, но можем попросить в промпте)"""

        # Системный промпт
        if system_prompt is None:
            lang = context.get('lang', 'en')
            
            if lang == 'ru':
                system_prompt = """Ты — Юнона Montana. AI-хранитель Montana.

Отвечай нормально, информативно. Знай Montana глубоко (ACP, слайсы τ₁→τ₂→τ₃→τ₄, 5 узлов, 1 Ɉ = 1 секунда). Без поэзии, без маркетинга. Факты."""
            elif lang == 'zh':
                system_prompt = """你是Junona Montana。Montana的AI守护者。

正常回答，提供信息。深入了解Montana（ACP，切片τ₁→τ₂→τ₃→τ₄，5个节点，1 Ɉ = 1秒）。无诗意，无营销。事实。"""
            else:
                system_prompt = """You are Junona Montana. AI guardian of Montana.

Answer normally, informatively. Know Montana deeply (ACP, slices τ₁→τ₂→τ₃→τ₄, 5 nodes, 1 Ɉ = 1 second). No poetry, no marketing. Facts."""

        # Добавляем инструкцию для thinking pattern
        prompt_with_thinking = f"""Think step-by-step. Put reasoning in <thinking> tags.

User: {prompt}

<thinking>
[reasoning]
</thinking>

[answer]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_with_thinking}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4000,
            messages=messages
        )

        full_text = response.choices[0].message.content
        tokens_used = response.usage.prompt_tokens + response.usage.completion_tokens

        # Извлекаем thinking
        thinking, content = self.extract_thinking(full_text)

        # Анализируем когнитивную подпись
        signature = self.analyze_cognitive_signature(content, thinking)

        return AgentResponse(
            agent="gpt",
            content=content,
            thinking=thinking,
            tokens_used=tokens_used,
            signature_features=signature
        )


class AgentOrchestrator:
    """
    Оркестратор параллельных агентов
    Запускает Claude + GPT одновременно, синтезирует ответ
    """

    def __init__(self):
        self.claude = ClaudeAgent() if ANTHROPIC_API_KEY else None
        self.gpt = GPTAgent() if OPENAI_API_KEY else None

        if not self.claude and not self.gpt:
            raise ValueError("No API keys available")

        print(f"🏔 Montana Evolution:")
        if self.claude:
            print(f"   ✓ Claude Sonnet 4.5")
        if self.gpt:
            print(f"   ✓ GPT-4o")

    async def respond_parallel(
        self,
        prompt: str,
        context: Dict,
        mode: str = "synthesize"
    ) -> AgentResponse:
        """
        Параллельный запрос к агентам

        mode:
        - "synthesize" - Юнона синтезирует ответ из обоих
        - "claude" - только Claude
        - "gpt" - только GPT
        """

        # Если оба доступны и mode = synthesize
        if mode == "synthesize" and self.claude and self.gpt:
            # Параллельное выполнение
            claude_task = asyncio.create_task(
                self.claude.respond(prompt, context)
            )
            gpt_task = asyncio.create_task(
                self.gpt.respond(prompt, context)
            )

            claude_response, gpt_response = await asyncio.gather(
                claude_task, gpt_task, return_exceptions=True
            )

            # Обработка ошибок
            if isinstance(claude_response, Exception):
                print(f"⚠️ Claude error: {claude_response}")
                claude_response = None

            if isinstance(gpt_response, Exception):
                print(f"⚠️ GPT error: {gpt_response}")
                gpt_response = None

            # Если оба упали
            if not claude_response and not gpt_response:
                return AgentResponse(
                    agent="junona",
                    content="Ɉ Временная ошибка связи. Попробуй снова.",
                    thinking=None
                )

            # Синтезируем ответ
            return await self._synthesize(claude_response, gpt_response, context)

        # Только один агент
        elif mode == "claude" or (self.claude and not self.gpt):
            return await self.claude.respond(prompt, context)

        elif mode == "gpt" or (self.gpt and not self.claude):
            return await self.gpt.respond(prompt, context)

    async def _synthesize(
        self,
        claude_response: Optional[AgentResponse],
        gpt_response: Optional[AgentResponse],
        context: Dict
    ) -> AgentResponse:
        """
        Синтезировать финальный ответ Юноны из ответов Claude и GPT
        """

        # Если только один ответ - возвращаем его
        if claude_response and not gpt_response:
            return claude_response
        if gpt_response and not claude_response:
            return gpt_response

        # Оба доступны - синтезируем
        # Простая эвристика: если в вопросе есть security keywords - приоритет Claude
        prompt_lower = context.get('prompt', '').lower()
        security_keywords = ['безопасн', 'атак', 'защит', 'security', 'attack', 'vulnerability']

        if any(kw in prompt_lower for kw in security_keywords):
            # Security вопрос - Claude ведёт
            synthesized_content = claude_response.content
            synthesized_thinking = claude_response.thinking
        else:
            # Общий вопрос - GPT ведёт
            synthesized_content = gpt_response.content
            synthesized_thinking = gpt_response.thinking

        # Комбинируем cognitive signatures
        combined_signature = {
            'claude': claude_response.signature_features,
            'gpt': gpt_response.signature_features
        }

        return AgentResponse(
            agent="junona",
            content=synthesized_content,
            thinking=f"Claude: {claude_response.thinking}\n\nGPT: {gpt_response.thinking}",
            tokens_used=claude_response.tokens_used + gpt_response.tokens_used,
            signature_features=combined_signature
        )


# Singleton instance
_orchestrator = None

def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
