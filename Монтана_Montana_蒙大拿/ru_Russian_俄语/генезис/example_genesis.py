#!/usr/bin/env python3
"""
Пример создания первого когнитивного ключа (Genesis)
====================================================

Genesis = первый когнитивный ключ участника.
Это его identity в сети Montana.

Запуск:
    python example_genesis.py
"""

from pathlib import Path
from presence import (
    PresenceStorage,
    generate_cognitive_key,
    format_genesis_message
)


def main():
    """Демонстрация создания Genesis."""

    print("=" * 60)
    print("  MONTANA GENESIS — Первый Когнитивный Ключ")
    print("=" * 60)
    print()

    # =========================================================
    # ПРИМЕР 1: Создание Genesis для Наблюдателя
    # =========================================================

    print("📌 ПРИМЕР 1: Genesis Наблюдателя (金元Ɉ)")
    print("-" * 60)

    observer_key = generate_cognitive_key(
        user_id=8552053404,                    # Telegram ID
        telegram_username="junomoneta",       # @username
        marker="#Благаявесть",                 # Когнитивный маркер
        first_response="Да. Я здесь. Всегда был и буду."
    )

    print(f"User ID:          {observer_key.user_id}")
    print(f"Username:         @{observer_key.telegram_username}")
    print(f"Маркер:           {observer_key.marker}")
    print(f"Genesis Hash:     {observer_key.genesis_hash}")
    print(f"Public Key:       {observer_key.public_key}")
    print(f"Genesis Sig:      {observer_key.genesis_signature[:64]}...")
    print(f"Timestamp:        {observer_key.genesis_timestamp}")
    print()

    # =========================================================
    # ПРИМЕР 2: Создание Genesis для нового участника
    # =========================================================

    print("📌 ПРИМЕР 2: Genesis нового участника")
    print("-" * 60)

    new_user_key = generate_cognitive_key(
        user_id=123456789,
        telegram_username="new_member",
        marker="#МойПуть",
        first_response="Присутствую в моменте."
    )

    print(f"User ID:          {new_user_key.user_id}")
    print(f"Маркер:           {new_user_key.marker}")
    print(f"Genesis Hash:     {new_user_key.genesis_hash[:32]}...")
    print(f"Public Key:       {new_user_key.public_key[:32]}...")
    print(f"Genesis Sig:      {new_user_key.genesis_signature[:32]}...")
    print()

    # =========================================================
    # ПРИМЕР 3: Сохранение в storage
    # =========================================================

    print("📌 ПРИМЕР 3: Сохранение в storage")
    print("-" * 60)

    # Каноническая папка данных бота (внутри montana_bot/)
    data_dir = Path(__file__).resolve().parent / "data"
    storage = PresenceStorage(data_dir)

    # Создать и сохранить
    if not storage.has_key(111222333):
        saved_key = storage.create_key(
            user_id=111222333,
            telegram_username="test_user",
            marker="#TestGenesis",
            first_response="Тестовый первый ответ."
        )
        print(f"✅ Genesis создан и сохранён!")
        print(f"   Маркер: {saved_key.marker}")
        print(f"   Hash:   {saved_key.genesis_hash[:32]}...")
    else:
        existing_key = storage.get_key(111222333)
        print(f"ℹ️ Genesis уже существует:")
        print(f"   Маркер: {existing_key.marker}")
        print(f"   Hash:   {existing_key.genesis_hash[:32]}...")

    print()

    # =========================================================
    # ПРИМЕР 4: Полное сообщение для Telegram
    # =========================================================

    print("📌 ПРИМЕР 4: Сообщение для Telegram")
    print("-" * 60)

    message = format_genesis_message(observer_key)
    print(message)

    # =========================================================
    # ФИЛОСОФИЯ GENESIS
    # =========================================================

    print("=" * 60)
    print("  ФИЛОСОФИЯ GENESIS")
    print("=" * 60)
    print("""
Genesis — это первый когнитивный ключ участника.

Как Bitcoin Genesis Block:
  • Один человек (Сатоши) создал genesis
  • После — децентрализованная сеть

Montana Genesis:
  • Бот создаёт genesis для каждого участника
  • После — твори где хочешь (Twitter, Telegram, GitHub)
  • Верификация — через Montana network

Формула:
  identity(user) = genesis(bot) + thoughts_trail(socials) + verification(Montana)

Принцип Парето 80/20:
  • 80% Full Nodes (серверы, автоматика)
  • 20% Verified Users (люди, "Ты здесь?")

Genesis ≠ ключ криптографический.
Genesis = ключ когнитивный.
Genesis = КТО ТЫ, не ЧТО ТЫ ИМЕЕШЬ.

#Благаявесть
""")


if __name__ == "__main__":
    main()
