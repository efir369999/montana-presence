# knowledge/__init__.py
# База знаний Юноны — разбита по папкам/темам
# Юнона загружает только релевантную секцию

from .price import KNOWLEDGE_PRICE
from .economy import KNOWLEDGE_ECONOMY
from .network import KNOWLEDGE_NETWORK
from .bot import KNOWLEDGE_BOT
from .code import KNOWLEDGE_CODE
from .thoughts import KNOWLEDGE_THOUGHTS
from .connect import KNOWLEDGE_CONNECT
from .base import KNOWLEDGE_BASE
from .hippocampus import KNOWLEDGE_HIPPOCAMPUS

# Ключевые слова для определения темы
TOPIC_KEYWORDS = {
    'price': ['цена', 'стоит', 'стоимость', 'рубл', 'доллар', '$', 'секунд', 'beeple', 'сколько', 'дорого', 'дёшево'],
    'economy': ['τ', 'tau', 'тау', 'эмисси', 'emission', 'координат', 'слайс', 'чекпоинт', 'эпох', '金元', 'ɉ'],
    'network': ['p2p', 'узел', 'node', 'соединени', 'eclipse', 'затмени', 'бакет', 'inbound', 'outbound', 'netgroup'],
    'bot': ['роль', 'атлант', 'орангутан', 'гость', 'рукопожат', 'handshake', 'заявк', 'вступ', 'клан'],
    'code': ['функци', 'def ', 'class ', 'import', 'код', 'handler', 'callback', 'промпт', 'prompt', 'state', 'keyboard'],
    'thoughts': ['мысл', 'благаявесть', 'генезис', 'когнитивн', 'подпись', 'любовь', 'унижени', 'эксперимент', '172', '173', '174'],
    'connect': ['подключ', 'api', 'токен', 'token', 'botfather', 'синхрониз', '.env', 'сервер', 'ip'],
    'hippocampus': ['гиппокамп', 'hippocampus', 'памят', 'memory', 'поток', 'stream', 'паттерн', 'pattern', 'новизн', 'дефрагмент', 'консолидац', 'днк', 'dna', 'внешний', 'external', 'биолог', 'детектор'],
}

def detect_topic(message: str) -> list:
    """Определяет темы вопроса по ключевым словам"""
    message_lower = message.lower()
    topics = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                if topic not in topics:
                    topics.append(topic)
                break

    # Если ничего не нашли — базовые знания
    if not topics:
        topics = ['base']

    return topics

def get_knowledge(message: str) -> str:
    """Возвращает релевантные знания для вопроса"""
    topics = detect_topic(message)

    knowledge_map = {
        'price': KNOWLEDGE_PRICE,
        'economy': KNOWLEDGE_ECONOMY,
        'network': KNOWLEDGE_NETWORK,
        'bot': KNOWLEDGE_BOT,
        'code': KNOWLEDGE_CODE,
        'thoughts': KNOWLEDGE_THOUGHTS,
        'connect': KNOWLEDGE_CONNECT,
        'base': KNOWLEDGE_BASE,
        'hippocampus': KNOWLEDGE_HIPPOCAMPUS,
    }

    # Собираем знания по темам (макс 3 темы)
    parts = []
    for topic in topics[:3]:
        if topic in knowledge_map:
            parts.append(knowledge_map[topic])

    return "\n\n".join(parts)
