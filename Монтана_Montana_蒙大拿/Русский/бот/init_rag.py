#!/usr/bin/env python3
# init_rag.py
# Скрипт первичной индексации базы знаний Montana для Юноны

import sys
from pathlib import Path

# Добавляем директорию бота в путь
BOT_DIR = Path(__file__).parent
sys.path.insert(0, str(BOT_DIR))

from junona_rag import get_rag

def main():
    print("🧠 Инициализация базы знаний Юноны")
    print("=" * 60)

    rag = get_rag()

    if not rag.collection or not rag.embedder:
        print("❌ RAG не инициализирован. Проверьте зависимости:")
        print("   pip install chromadb sentence-transformers")
        sys.exit(1)

    print(f"\n📊 Текущее состояние:")
    print(f"   Документов в базе: {rag.collection.count()}")

    force = "--force" in sys.argv or "-f" in sys.argv

    if force:
        print("\n🔄 Запуск полной переиндексации...")
    else:
        print("\n🔄 Запуск инкрементальной индексации...")
        print("   (используйте --force для полной переиндексации)")

    print()
    rag.index(force=force)

    print("\n✅ Индексация завершена успешно")
    print(f"📊 Итого документов: {rag.collection.count()}")

    # Тест поиска
    print("\n🔍 Тестовый поиск:")
    test_queries = [
        "что такое Montana",
        "время как валюта",
        "симуляция реальности"
    ]

    for query in test_queries:
        results = rag.search(query, n_results=2)
        if results:
            print(f"\n  Запрос: '{query}'")
            for r in results[:1]:
                source = Path(r['source']).name
                preview = r['content'][:100].replace('\n', ' ')
                print(f"    ✓ [{r['score']:.2f}] {source}")
                print(f"      {preview}...")

    print("\n✨ База знаний готова к использованию")

if __name__ == "__main__":
    main()
