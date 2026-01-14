"""
Telegram Channel Reader — получает все текстовые посты из канала

Экспорт в JSON (для обработки) и Markdown (для чтения)
"""

import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Message

# Telegram API credentials (получить на https://my.telegram.org)
API_ID = os.getenv("TELEGRAM_API_ID", "")
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME = "channel_reader"

# Канал для чтения
CHANNEL_USERNAME = "mylifethoughts369"


async def get_all_text_posts(client: TelegramClient, channel: str) -> list[dict]:
    """Получить все текстовые посты из канала"""
    posts = []

    entity = await client.get_entity(channel)
    print(f"Читаю канал: {entity.title}")
    print(f"ID: {entity.id}")

    async for message in client.iter_messages(entity):
        if isinstance(message, Message) and message.text:
            posts.append({
                "id": message.id,
                "date": message.date.isoformat(),
                "date_human": message.date.strftime("%Y-%m-%d %H:%M:%S"),
                "text": message.text,
                "views": message.views or 0,
                "forwards": message.forwards or 0,
                "replies": message.replies.replies if message.replies else 0
            })

    return posts


def save_json(posts: list[dict], channel: str):
    """Сохранить в JSON"""
    filename = f"{channel}_posts.json"

    export_data = {
        "channel": f"@{channel}",
        "exported_at": datetime.now().isoformat(),
        "total_posts": len(posts),
        "posts": list(reversed(posts))  # От старых к новым
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"JSON: {filename}")
    return filename


def save_markdown(posts: list[dict], channel: str):
    """Сохранить в Markdown"""
    filename = f"{channel}_posts.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# @{channel}\n\n")
        f.write(f"**Экспорт:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Постов:** {len(posts)}\n\n")
        f.write("---\n\n")

        for post in reversed(posts):  # От старых к новым
            f.write(f"## {post['date_human']}\n\n")
            f.write(f"*ID: {post['id']} | Views: {post['views']} | Forwards: {post['forwards']}*\n\n")
            f.write(post['text'])
            f.write("\n\n---\n\n")

    print(f"Markdown: {filename}")
    return filename


def get_credentials():
    """Получить или запросить API credentials"""
    api_id = API_ID or os.getenv("TELEGRAM_API_ID")
    api_hash = API_HASH or os.getenv("TELEGRAM_API_HASH")

    if api_id and api_hash:
        return int(api_id), api_hash

    print("=" * 50)
    print("НАСТРОЙКА TELEGRAM API")
    print("=" * 50)
    print()
    print("1. Открой: https://my.telegram.org")
    print("2. Войди по номеру телефона")
    print("3. Нажми 'API development tools'")
    print("4. Создай приложение (любое название)")
    print("5. Скопируй api_id и api_hash")
    print()

    api_id = input("Введи api_id (число): ").strip()
    api_hash = input("Введи api_hash (строка): ").strip()

    if not api_id or not api_hash:
        print("Ошибка: нужны оба значения")
        return None, None

    return int(api_id), api_hash


async def main():
    api_id, api_hash = get_credentials()
    if not api_id:
        return

    client = TelegramClient(SESSION_NAME, api_id, api_hash)

    async with client:
        print(f"Подключение к Telegram...")

        posts = await get_all_text_posts(client, CHANNEL_USERNAME)

        print(f"\nНайдено {len(posts)} текстовых постов\n")

        # Сохранить в оба формата
        save_json(posts, CHANNEL_USERNAME)
        save_markdown(posts, CHANNEL_USERNAME)

        # Статистика
        total_views = sum(p['views'] for p in posts)
        total_forwards = sum(p['forwards'] for p in posts)

        print(f"\nСтатистика:")
        print(f"  Всего постов: {len(posts)}")
        print(f"  Всего просмотров: {total_views:,}")
        print(f"  Всего репостов: {total_forwards:,}")

        # Последние 3 поста
        print(f"\nПоследние 3 поста:")
        print("-" * 40)
        for post in posts[:3]:
            preview = post['text'][:80] + "..." if len(post['text']) > 80 else post['text']
            preview = preview.replace('\n', ' ')
            print(f"[{post['date_human']}] {preview}")


if __name__ == "__main__":
    asyncio.run(main())
