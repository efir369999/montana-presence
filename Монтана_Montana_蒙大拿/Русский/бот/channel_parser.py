# channel_parser.py
# Парсинг канала @mylifesound369 для отслеживания Благаявести

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import asyncio

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#                              КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

CHANNEL_USERNAME = "@mylifesound369"
BOT_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BOT_DIR / "knowledge" / "blagayavest"
CHANNEL_DATA_FILE = BOT_DIR / "data" / "channel_posts.json"

# Создать директории
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
CHANNEL_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
#                              PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class ChannelParser:
    """Парсер канала @mylifesound369 для Благаявести"""

    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.channel = CHANNEL_USERNAME
        self.last_checked_id = self._load_last_id()

    def _load_last_id(self) -> int:
        """Загрузить ID последнего проверенного поста"""
        if CHANNEL_DATA_FILE.exists():
            try:
                with open(CHANNEL_DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_checked_id', 0)
            except:
                return 0
        return 0

    def _save_last_id(self, message_id: int):
        """Сохранить ID последнего проверенного поста"""
        data = {'last_checked_id': message_id, 'updated_at': datetime.utcnow().isoformat()}
        with open(CHANNEL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def get_channel_posts(self, limit: int = 100) -> List[Dict]:
        """
        Получить последние посты из канала

        Note: Telegram Bot API не позволяет читать каналы без прав админа.
        Используем альтернативный метод через getChatHistory или telethon
        """
        posts = []

        try:
            # Попытка получить информацию о канале
            chat = await self.bot.get_chat(self.channel)
            logger.info(f"Channel info: {chat.title}")

            # Bot API не позволяет читать историю без прав
            # Нужно использовать Telethon или MTProto
            logger.warning("Bot API ограничен для чтения каналов. Используйте Telethon.")

        except TelegramError as e:
            logger.error(f"Ошибка доступа к каналу: {e}")

        return posts

    def parse_book_post(self, text: str) -> Optional[Dict]:
        """
        Парсинг поста с частью книги

        Формат:
        Книга 1, Глава X: Название
        Текст...
        """
        if not text:
            return None

        # Проверка ключевых слов
        if any(keyword in text.lower() for keyword in ['книга', 'глава', 'благаявесть', 'монтана']):
            # Извлечь структурированные данные
            lines = text.split('\n')

            # Попытка найти заголовок
            title = None
            chapter = None

            for line in lines[:5]:  # Первые 5 строк
                if 'глава' in line.lower():
                    # Попытка извлечь номер главы
                    import re
                    match = re.search(r'глава\s*(\d+)', line.lower())
                    if match:
                        chapter = int(match.group(1))
                    title = line.strip()
                    break

            return {
                'title': title or "Без названия",
                'chapter': chapter,
                'text': text,
                'type': 'book_part'
            }

        return None

    def save_to_knowledge(self, post_data: Dict):
        """Сохранить пост в базу знаний"""
        chapter = post_data.get('chapter', 0)
        title = post_data.get('title', 'unknown')

        # Создать имя файла
        filename = f"chapter_{chapter:02d}.md" if chapter else f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = KNOWLEDGE_DIR / filename

        # Сохранить
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {post_data['title']}\n\n")
            f.write(f"**Глава:** {chapter}\n" if chapter else "")
            f.write(f"**Дата:** {datetime.now().isoformat()}\n\n")
            f.write(f"---\n\n")
            f.write(post_data['text'])

        logger.info(f"Сохранено в базу знаний: {filepath}")

    async def check_new_posts(self) -> List[Dict]:
        """Проверить новые посты и сохранить части книги"""
        new_posts = []

        # Получить посты
        posts = await self.get_channel_posts()

        # Обработать новые
        for post in posts:
            if post['id'] > self.last_checked_id:
                parsed = self.parse_book_post(post.get('text', ''))
                if parsed:
                    parsed['message_id'] = post['id']
                    parsed['date'] = post.get('date')

                    # Сохранить в знания
                    self.save_to_knowledge(parsed)
                    new_posts.append(parsed)

                # Обновить last_id
                self.last_checked_id = max(self.last_checked_id, post['id'])

        # Сохранить last_id
        if new_posts:
            self._save_last_id(self.last_checked_id)

        return new_posts

# ═══════════════════════════════════════════════════════════════════════════════
#                              TELETHON ALTERNATIVE
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from telethon import TelegramClient
    from telethon.tl.functions.messages import GetHistoryRequest
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("Telethon не установлен. Используйте: pip install telethon")

class TelethonChannelParser:
    """Парсер канала через Telethon (MTProto API)"""

    def __init__(self, api_id: int, api_hash: str, session_name: str = "junona"):
        if not TELETHON_AVAILABLE:
            raise ImportError("Telethon не установлен")

        self.client = TelegramClient(session_name, api_id, api_hash)
        self.channel = CHANNEL_USERNAME
        self.last_checked_id = self._load_last_id()

    def _load_last_id(self) -> int:
        """Загрузить ID последнего проверенного поста"""
        if CHANNEL_DATA_FILE.exists():
            try:
                with open(CHANNEL_DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_checked_id', 0)
            except:
                return 0
        return 0

    def _save_last_id(self, message_id: int):
        """Сохранить ID последнего проверенного поста"""
        data = {'last_checked_id': message_id, 'updated_at': datetime.utcnow().isoformat()}
        with open(CHANNEL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def get_channel_posts(self, limit: int = 100) -> List[Dict]:
        """Получить последние посты из канала"""
        posts = []

        await self.client.start()

        try:
            # Получить сущность канала
            entity = await self.client.get_entity(self.channel)

            # Получить историю
            messages = await self.client.get_messages(entity, limit=limit)

            for msg in messages:
                if msg.text:
                    posts.append({
                        'id': msg.id,
                        'date': msg.date.isoformat(),
                        'text': msg.text,
                        'views': msg.views or 0
                    })

        except Exception as e:
            logger.error(f"Ошибка получения постов: {e}")

        return posts

    def parse_book_post(self, text: str) -> Optional[Dict]:
        """
        Парсинг поста с частью книги

        Паттерны:
        - Книга 1, Глава X
        - Глава X: Название
        - #благаявесть #книга1
        """
        if not text:
            return None

        # Проверка хештегов и ключевых слов
        keywords = ['книга', 'глава', 'благаявесть', 'монтана', '#книга1']
        if not any(keyword in text.lower() for keyword in keywords):
            return None

        # Извлечь структурированные данные
        import re
        lines = text.split('\n')

        title = None
        chapter = None
        book = 1  # По умолчанию книга 1

        # Ищем заголовок и номер главы
        for line in lines[:10]:
            # Паттерн: Глава X
            match = re.search(r'[Гг]лава\s*(\d+)', line)
            if match:
                chapter = int(match.group(1))
                title = line.strip()

            # Паттерн: Книга X
            match = re.search(r'[Кк]нига\s*(\d+)', line)
            if match:
                book = int(match.group(1))

        if chapter or any(kw in text.lower() for kw in keywords):
            return {
                'book': book,
                'chapter': chapter,
                'title': title or "Без названия",
                'text': text,
                'type': 'book_part'
            }

        return None

    def save_to_knowledge(self, post_data: Dict):
        """Сохранить пост в базу знаний"""
        book = post_data.get('book', 1)
        chapter = post_data.get('chapter', 0)

        # Создать структуру директорий
        book_dir = KNOWLEDGE_DIR / f"book_{book}"
        book_dir.mkdir(parents=True, exist_ok=True)

        # Имя файла
        if chapter:
            filename = f"chapter_{chapter:02d}.md"
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"post_{timestamp}.md"

        filepath = book_dir / filename

        # Сохранить
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Книга {book}")
            if chapter:
                f.write(f", Глава {chapter}")
            if post_data.get('title') and post_data['title'] != "Без названия":
                f.write(f": {post_data['title']}")
            f.write(f"\n\n")

            f.write(f"**Источник:** {CHANNEL_USERNAME}\n")
            f.write(f"**Дата:** {datetime.now().isoformat()}\n\n")
            f.write(f"---\n\n")
            f.write(post_data['text'])

        logger.info(f"✓ Сохранено: {filepath}")

        # Индексация в RAG
        try:
            from junona_rag import get_rag
            rag = get_rag()
            rag.index(force=False)  # Инкрементальная индексация
            logger.info(f"✓ Проиндексировано в RAG")
        except Exception as e:
            logger.warning(f"⚠️ RAG индексация не удалась: {e}")

        # Синхронизация с узлами Montana
        self.sync_to_nodes(filepath)

        return filepath

    def sync_to_nodes(self, filepath: Path):
        """Синхронизировать файл со всеми узлами Montana"""
        import subprocess

        # Узлы Montana (из montana_api.py)
        NODES = {
            "amsterdam": "72.56.102.240",
            "moscow": "176.124.208.93",
            "almaty": "91.200.148.93",
            "spb": "188.225.58.98",
            "novosibirsk": "147.45.147.247"
        }

        # Относительный путь от корня бота
        relative_path = filepath.relative_to(BOT_DIR)

        for node_name, node_ip in NODES.items():
            try:
                # rsync файла на узел
                remote_path = f"root@{node_ip}:/root/junona_bot/{relative_path}"

                result = subprocess.run(
                    ['rsync', '-av', str(filepath), remote_path],
                    capture_output=True,
                    timeout=5
                )

                if result.returncode == 0:
                    logger.info(f"  → {node_name}: синхронизировано")
                else:
                    logger.warning(f"  → {node_name}: ошибка ({result.returncode})")

            except subprocess.TimeoutExpired:
                logger.warning(f"  → {node_name}: timeout")
            except Exception as e:
                logger.warning(f"  → {node_name}: {e}")

    async def check_new_posts(self) -> List[Dict]:
        """Проверить новые посты и сохранить части книги"""
        new_posts = []

        # Получить посты
        posts = await self.get_channel_posts()

        max_id = self.last_checked_id

        # Обработать новые
        for post in posts:
            if post['id'] > self.last_checked_id:
                parsed = self.parse_book_post(post.get('text', ''))
                if parsed:
                    parsed['message_id'] = post['id']
                    parsed['date'] = post.get('date')

                    # Сохранить в знания
                    filepath = self.save_to_knowledge(parsed)
                    parsed['filepath'] = str(filepath)

                    new_posts.append(parsed)

                max_id = max(max_id, post['id'])

        # Сохранить last_id
        if new_posts:
            self._save_last_id(max_id)
            self.last_checked_id = max_id

        return new_posts

    async def close(self):
        """Закрыть клиент"""
        await self.client.disconnect()

# ═══════════════════════════════════════════════════════════════════════════════
#                              HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_parser(use_telethon: bool = True):
    """
    Получить парсер канала

    Args:
        use_telethon: Использовать Telethon (MTProto) вместо Bot API

    Returns:
        ChannelParser or TelethonChannelParser
    """
    if use_telethon and TELETHON_AVAILABLE:
        # Telethon требует API credentials
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")

        if api_id and api_hash:
            return TelethonChannelParser(int(api_id), api_hash)
        else:
            logger.warning("TELEGRAM_API_ID и TELEGRAM_API_HASH не установлены. Используйте Bot API.")

    # Fallback на Bot API
    bot_token = os.getenv("TELEGRAM_TOKEN_JUNONA")
    return ChannelParser(bot_token)

def list_knowledge_files() -> List[Dict]:
    """Список всех файлов в базе знаний"""
    files = []

    if KNOWLEDGE_DIR.exists():
        for filepath in sorted(KNOWLEDGE_DIR.rglob("*.md")):
            # Читать метаданные из файла
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                title = lines[0].replace('#', '').strip() if lines else filepath.name

            files.append({
                'path': str(filepath),
                'name': filepath.name,
                'title': title,
                'size': filepath.stat().st_size,
                'modified': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
            })

    return files

# ═══════════════════════════════════════════════════════════════════════════════
#                              CLI INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Тестовый запуск парсера"""
    import sys

    parser = get_parser(use_telethon=True)

    print("🏔 Montana Channel Parser")
    print(f"   Канал: {CHANNEL_USERNAME}")
    print(f"   База знаний: {KNOWLEDGE_DIR}")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        print("Проверка новых постов...")
        new_posts = await parser.check_new_posts()

        if new_posts:
            print(f"\n✓ Найдено новых частей книги: {len(new_posts)}\n")
            for post in new_posts:
                print(f"  • Книга {post.get('book', 1)}, Глава {post.get('chapter', '?')}")
                print(f"    {post.get('title', 'Без названия')}")
                print(f"    → {post.get('filepath', '')}")
                print()
        else:
            print("✓ Новых частей не найдено")

    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        print("База знаний Благаявести:\n")
        files = list_knowledge_files()

        if files:
            for f in files:
                print(f"  • {f['title']}")
                print(f"    {f['path']}")
                print()
        else:
            print("  База знаний пуста")

    else:
        print("Использование:")
        print("  python channel_parser.py check  — проверить новые посты")
        print("  python channel_parser.py list   — показать базу знаний")

    # Закрыть подключение
    if hasattr(parser, 'close'):
        await parser.close()

if __name__ == '__main__':
    asyncio.run(main())
