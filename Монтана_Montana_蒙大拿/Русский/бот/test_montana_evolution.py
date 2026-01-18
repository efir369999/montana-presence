#!/usr/bin/env python3
# test_montana_evolution.py
# Тест Montana Evolution: параллельные агенты + cognitive signatures

import asyncio
import sys
from pathlib import Path

# Добавляем текущую папку в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from session_manager import SessionManager, get_session_manager
from junona_agents import AgentOrchestrator, get_orchestrator


async def test_session_isolation():
    """Тест 1: Изоляция сессий (git worktree analog)"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Изоляция сессий")
    print("="*60)

    manager = get_session_manager()

    # Создаём 2 сессии для одного пользователя
    user_id = 123456

    session1 = manager.create_session(user_id)
    print(f"\n✓ Сессия 1 создана: {session1.id}")
    print(f"  Папка: {session1.dir}")

    await session1.log_message("user", "Что такое Montana?")
    await session1.log_message("assistant", "Montana — протокол времени.", agent="claude")

    session2 = manager.create_session(user_id)
    print(f"\n✓ Сессия 2 создана: {session2.id}")
    print(f"  Папка: {session2.dir}")

    await session2.log_message("user", "Как работает ACP?")

    # Проверяем изоляцию
    messages1 = session1.get_messages()
    messages2 = session2.get_messages()

    print(f"\n📊 Результаты:")
    print(f"   Сессия 1: {len(messages1)} сообщений")
    print(f"   Сессия 2: {len(messages2)} сообщений")
    print(f"   ✓ Сессии изолированы: {session1.id != session2.id}")

    return manager


async def test_parallel_agents():
    """Тест 2: Параллельное выполнение Claude + GPT"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Параллельные агенты")
    print("="*60)

    orchestrator = get_orchestrator()

    prompt = "Объясни концепцию ACP в Montana простыми словами"
    context = {"prompt": prompt, "lang": "ru"}

    print(f"\n🔄 Запрос: {prompt}")
    print(f"⏳ Запускаю Claude + GPT параллельно...\n")

    import time
    start = time.time()

    # Режим "оба видимы" для демонстрации
    response = await orchestrator.respond_parallel(
        prompt,
        context,
        mode="synthesize"  # или "both_visible" чтобы видеть оба ответа
    )

    elapsed = time.time() - start

    print(f"✓ Ответ получен за {elapsed:.2f}с")
    print(f"  Агент: {response.agent}")
    print(f"  Токенов: {response.tokens_used}\n")

    print("─" * 60)
    print(response.content)
    print("─" * 60)

    return response


async def test_cognitive_signatures(manager: SessionManager, response):
    """Тест 3: Cognitive Signatures"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Cognitive Signatures")
    print("="*60)

    # Создаём сессию и сохраняем cognitive signatures
    user_id = 123456
    session = manager.get_active_session(user_id)

    # Логируем reasoning patterns
    if response.thinking:
        await session.log_reasoning(
            agent=response.agent,
            thinking=response.thinking,
            metadata={"test": True}
        )

    # Сохраняем cognitive signature
    if response.signature_features:
        await session.save_cognitive_signature(
            agent=response.agent,
            signature=response.signature_features
        )

    # Читаем обратно
    signatures = session.get_cognitive_signatures()

    print(f"\n🖋️ Cognitive Signatures сохранены:")
    for agent, data in signatures.items():
        print(f"\n   Агент: {agent}")
        print(f"   Timestamp: {data['ts']}")

        sig = data['signature']
        if 'style' in sig:
            print(f"   Стиль:")
            for key, val in sig['style'].items():
                print(f"      {key}: {val}")

        if 'reasoning_pattern' in sig and sig['reasoning_pattern']:
            print(f"   Reasoning patterns:")
            for key, val in sig['reasoning_pattern'].items():
                print(f"      {key}: {val}")

    # Reasoning logs
    logs = session.get_reasoning_logs()
    print(f"\n💭 Reasoning logs: {len(logs)} записей")

    if logs:
        latest = logs[-1]
        print(f"   Последний: {latest['agent']} ({latest['tokens']} tokens)")
        print(f"   Thinking: {latest['thinking'][:100]}...")


async def test_user_stats(manager: SessionManager):
    """Тест 4: Статистика пользователя (для уровней Орангутанга)"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Статистика пользователя")
    print("="*60)

    user_id = 123456
    stats = manager.get_user_stats(user_id)

    print(f"\n🦧 Пользователь #{user_id}:")
    print(f"   Сессий: {stats['sessions']}")
    print(f"   Всего сообщений: {stats['total_messages']}")
    print(f"   Сырых мыслей: {stats['raw_thoughts']}")
    print(f"   Reasoning логов: {stats['reasoning_logs']}")
    print(f"   Дней активности: {stats['days_active']}")

    # Эмуляция расчёта уровня
    level = min(99, stats['raw_thoughts'] // 10)  # 1 уровень за 10 мыслей
    to_next = 10 - (stats['raw_thoughts'] % 10)
    to_atlant = 1000 - stats['raw_thoughts']  # 1000 мыслей до Атланта

    print(f"\n   Уровень: Орангутанг #{level}")
    print(f"   До следующего уровня: {to_next} мыслей")
    print(f"   До Атланта 🏔: {to_atlant} мыслей")


async def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("  MONTANA EVOLUTION: Тесты")
    print("  Параллельные агенты + Cognitive Signatures")
    print("="*60)

    try:
        # Тест 1: Изоляция сессий
        manager = await test_session_isolation()

        # Тест 2: Параллельные агенты
        response = await test_parallel_agents()

        # Тест 3: Cognitive Signatures
        await test_cognitive_signatures(manager, response)

        # Тест 4: Статистика пользователя
        await test_user_stats(manager)

        print("\n" + "="*60)
        print("  ✓ Все тесты пройдены!")
        print("="*60)

        print("\n📁 Данные сохранены в:")
        print(f"   {Path(__file__).parent / 'data' / 'sessions'}")

        print("\n💡 Следующий шаг:")
        print("   Интегрировать в junona_bot.py")
        print("   Команда: /cognitive для просмотра подписей\n")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
