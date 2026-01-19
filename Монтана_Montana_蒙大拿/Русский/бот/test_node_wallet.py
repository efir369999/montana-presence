#!/usr/bin/env python3
# Тест системы кошельков узлов

from pathlib import Path
from node_wallet import get_node_wallet_system

def main():
    print("🧪 Тест системы кошельков узлов Montana\n")
    print("=" * 60)

    # Инициализация
    bot_dir = Path(__file__).parent
    nws = get_node_wallet_system(bot_dir)

    print("\n✅ Система инициализирована")

    # Показать все узлы
    print("\n📊 Сводка по сети:")
    print("-" * 60)
    summary = nws.get_network_summary()
    print(summary)

    # Показать Amsterdam узел
    print("\n\n🇳🇱 Детали Amsterdam узла:")
    print("-" * 60)
    amsterdam_display = nws.get_node_display("72.56.102.240")
    print(amsterdam_display)

    # Добавить тестовую транзакцию
    print("\n\n💰 Добавляем тестовую транзакцию...")
    success = nws.add_transaction(
        "72.56.102.240",
        100.5,
        "reward",
        "Награда за валидацию блоков"
    )
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")

    # Показать обновленный кошелек
    print("\n📈 Обновленный кошелек Amsterdam:")
    print("-" * 60)
    amsterdam_display = nws.get_node_display("72.56.102.240")
    print(amsterdam_display)

    # Тест регистрации нового узла
    print("\n\n➕ Регистрация тестового узла...")
    result = nws.register_node(
        "1.2.3.4",
        "test_tokyo",
        "🇯🇵 Tokyo Test",
        "Test Operator",
        "light"
    )

    if "error" in result:
        print(f"❌ Ошибка: {result['error']}")
    else:
        print("✅ Узел зарегистрирован:")
        print(nws.get_node_display("1.2.3.4"))

    print("\n\n✨ Тест завершен")

if __name__ == "__main__":
    main()
