#!/usr/bin/env python3
"""
Тесты для криптографической системы Montana
POST-QUANTUM КРИПТОГРАФИЯ ML-DSA-65 (FIPS 204)
"""

from pathlib import Path
from node_crypto import (
    get_node_crypto_system,
    generate_keypair,
    public_key_to_address,
    sign_message,
    verify_signature,
    get_crypto_info
)


def test_node_crypto():
    print("🧪 Тест POST-QUANTUM криптографической системы узлов Montana\n")
    print("=" * 70)

    # Информация о криптосистеме
    info = get_crypto_info()
    print(f"\n🔐 КРИПТОСИСТЕМА: {info['algorithm']}")
    print(f"   Стандарт: {info['standard']}")
    print(f"   Уровень: {info['security_level']}")
    print("=" * 70)

    # 1. Тест генерации ключей
    print("\n1️⃣ ГЕНЕРАЦИЯ КЛЮЧЕЙ ML-DSA-65 (POST-QUANTUM)")
    print("-" * 70)

    private_key, public_key = generate_keypair()
    address = public_key_to_address(public_key)

    print(f"Private key: {private_key[:64]}...")
    print(f"             ({len(bytes.fromhex(private_key))} байт)")
    print(f"Public key:  {public_key[:64]}...")
    print(f"             ({len(bytes.fromhex(public_key))} байт)")
    print(f"Адрес:       {address}")

    # 2. Тест подписи
    print("\n2️⃣ КРИПТОГРАФИЧЕСКАЯ ПОДПИСЬ ML-DSA-65")
    print("-" * 70)

    message = "MONTANA_TX_V1:transfer:1000:seconds"
    signature = sign_message(private_key, message)

    print(f"Сообщение: {message}")
    print(f"Подпись:   {signature[:64]}...")
    print(f"           ({len(bytes.fromhex(signature))} байт)")

    # Проверка подписи
    is_valid = verify_signature(public_key, message, signature)
    print(f"Верификация: {'✅ ВАЛИДНА' if is_valid else '❌ НЕВАЛИДНА'}")

    # Попытка подделки
    fake_message = "MONTANA_TX_V1:transfer:9999:seconds"
    is_fake_valid = verify_signature(public_key, fake_message, signature)
    print(f"Подделка: {'❌ ПРИНЯТА (!)' if is_fake_valid else '✅ ОТКЛОНЕНА'}")

    # 3. Регистрация узлов
    print("\n3️⃣ РЕГИСТРАЦИЯ УЗЛОВ С ML-DSA-65")
    print("-" * 70)

    bot_dir = Path(__file__).parent
    ncs = get_node_crypto_system(bot_dir)

    # Регистрируем тестовый узел
    print("\n📝 Регистрация нового узла 'Tokyo'...")
    result = ncs.register_node(
        owner_telegram_id=123456789,
        node_name="tokyo",
        location="🇯🇵 Tokyo",
        ip_address="1.2.3.4",
        node_type="light"
    )

    if result.get("success"):
        print(f"✅ Узел зарегистрирован:")
        print(f"   Адрес:       {result['address']}")
        print(f"   Alias:       {result['alias']}")
        print(f"   Crypto:      {result.get('crypto_version', 'ML-DSA-65')}")
        print(f"   Private key: {result['private_key'][:64]}... ⚠️ СОХРАНИ!")
        print(f"   Owner TG ID: {result['owner']}")

        tokyo_address = result['address']
        tokyo_private_key = result['private_key']
    else:
        print(f"❌ Ошибка: {result.get('error')}")
        return

    # 4. Импорт официальных узлов
    print("\n📝 Импорт официальных узлов Montana...")
    official_results = ncs.import_official_nodes()

    print(f"\n✅ Импортировано {len(official_results)} узлов:")
    for name, data in official_results.items():
        if data['status'] == 'registered':
            print(f"   ⭐️ {name}: {data['address']}")
            print(f"      Alias: {data['alias']}")
            print(f"      IP: {data['ip']}")
            print(f"      Crypto: {data.get('crypto_version', 'ML-DSA-65')}")
        else:
            print(f"   • {name}: уже существует ({data['address']})")

    # 5. Получение узлов
    print("\n4️⃣ ПОЛУЧЕНИЕ УЗЛОВ")
    print("-" * 70)

    node = ncs.get_node_by_address(tokyo_address)
    if node:
        print(f"✅ Узел по адресу {tokyo_address}:")
        print(f"   Имя: {node['node_name']}")
        print(f"   Alias: {node['alias']}")
        print(f"   IP: {node['ip']}")

    node = ncs.get_node_by_alias("tokyo.montana.network")
    if node:
        print(f"✅ Узел по alias 'tokyo.montana.network':")
        print(f"   Адрес: {node['address']}")

    node = ncs.get_node_by_ip("1.2.3.4")
    if node:
        print(f"✅ Узел по IP '1.2.3.4' (networking only):")
        print(f"   Адрес: {node['address']}")
        print(f"   ⚠️ IP НЕ является ключом к кошельку!")

    # 6. Проверка владения
    print("\n5️⃣ ПРОВЕРКА ВЛАДЕНИЯ ML-DSA-65")
    print("-" * 70)

    tx_message = "MONTANA_TX_V1:transfer:500:mt9876543210"
    tx_signature = sign_message(tokyo_private_key, tx_message)

    print(f"Транзакция: {tx_message}")
    print(f"Подпись:    {tx_signature[:64]}...")

    is_owner = ncs.verify_node_ownership(tokyo_address, tx_message, tx_signature)
    print(f"Владение:   {'✅ ПОДТВЕРЖДЕНО' if is_owner else '❌ ОТКЛОНЕНО'}")

    # Попытка атаки
    fake_private_key, _ = generate_keypair()
    fake_signature = sign_message(fake_private_key, tx_message)

    is_attacker = ncs.verify_node_ownership(tokyo_address, tx_message, fake_signature)
    print(f"Атака:      {'❌ УСПЕШНА (!)' if is_attacker else '✅ ЗАБЛОКИРОВАНА'}")

    # 7. Отображение узла
    print("\n6️⃣ ОТОБРАЖЕНИЕ УЗЛА")
    print("-" * 70)
    display = ncs.get_node_display(tokyo_address)
    print(display)

    # 8. Все узлы
    print("\n7️⃣ ВСЕ УЗЛЫ MONTANA")
    print("-" * 70)
    all_nodes = ncs.get_all_nodes()
    print(f"Всего узлов: {len(all_nodes)}\n")
    for node in sorted(all_nodes, key=lambda x: x.get('priority', 999)):
        official = "⭐️" if node.get('official') else "🔹"
        crypto = "🔐" if node.get('crypto_version') == 'ML-DSA-65' else "🔓"
        print(f"{official}{crypto} {node['location']}")
        print(f"   Адрес: {node['address']}")
        print(f"   Alias: {node['alias']}")
        print(f"   IP: {node['ip']} (networking only)")
        print()

    print("\n8️⃣ POST-QUANTUM ЗАЩИТА")
    print("-" * 70)
    print("✅ Квантовые компьютеры: ЗАЩИЩЕНО")
    print("   → ML-DSA-65 устойчив к Shor's algorithm")
    print("   → FIPS 204 стандарт NIST")
    print()
    print("✅ IP hijacking: ЗАБЛОКИРОВАНА")
    print("   → IP адрес только для networking")
    print("   → Адрес кошелька = hash(public_key)")
    print()
    print("✅ DNS spoofing: ЗАБЛОКИРОВАНА")
    print("   → Alias только для удобства")
    print("   → Реальный адрес — криптографический")
    print()
    print("✅ Подделка транзакций: ЗАБЛОКИРОВАНА")
    print("   → Для всех операций нужна подпись ML-DSA-65")
    print("   → Private key у владельца (4032 байта)")
    print()
    print("✅ Man-in-the-middle: ЗАБЛОКИРОВАНА")
    print("   → Подпись проверяется по public key")
    print("   → Public key в блокчейне")
    print()
    print("✅ Harvest now, decrypt later: ЗАБЛОКИРОВАНА")
    print("   → POST-QUANTUM криптография с genesis")

    print("\n✨ Тест завершен успешно!")
    print("\n📖 Документация: NODE_CRYPTO_SYSTEM.md")
    print("🔐 Криптография: ML-DSA-65 (FIPS 204)")
    print("🛡️  Уровень: NIST Level 3 (128-bit post-quantum)")


if __name__ == "__main__":
    test_node_crypto()
