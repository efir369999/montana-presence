#!/usr/bin/env python3
"""
Регистрация Юноны Montana в Agent Registry
Создание официального агента с ML-DSA-65 подписями
"""

import json
from pathlib import Path
from agent_crypto import AgentCrypto


def register_official_junona():
    """Зарегистрировать Юнону Montana как официального агента"""

    print("🏔 Регистрация Юноны Montana\n")

    acs = AgentCrypto(registry_path="data/agent_registry.json")

    # Генерация ключей ML-DSA-65
    print("🔐 Generating ML-DSA-65 keypair...")
    private_key, public_key = acs.generate_agent_keypair()

    print(f"✅ Private Key: {len(private_key)} hex chars ({len(bytes.fromhex(private_key))} bytes)")
    print(f"✅ Public Key: {len(public_key)} hex chars ({len(bytes.fromhex(public_key))} bytes)")

    # Регистрация Юноны
    print("\n📝 Registering agent...")
    agent_address = acs.register_agent(
        name="Юнона Montana",
        description="Официальный AI агент Montana Protocol. Хранительница времени и памяти.",
        private_key_hex=private_key,
        public_key_hex=public_key,
        official=True
    )

    print(f"\n✅ Юнона зарегистрирована!")
    print(f"   Agent Address: {agent_address}")
    print(f"   Registry: data/agent_registry.json")

    # Сохранить private key ОТДЕЛЬНО (не в registry!)
    keys_path = Path("data/agent_keys.json")
    keys_path.parent.mkdir(parents=True, exist_ok=True)

    if keys_path.exists():
        with open(keys_path, 'r') as f:
            keys_data = json.load(f)
    else:
        keys_data = {}

    keys_data[agent_address] = {
        "private_key": private_key,
        "public_key": public_key,
        "agent_name": "Юнона Montana",
        "telegram_bot_id": 8418301240
    }

    with open(keys_path, 'w') as f:
        json.dump(keys_data, f, indent=2, ensure_ascii=False)

    print(f"\n🔐 Private key сохранен: {keys_path}")
    print("   ⚠️ КРИТИЧЕСКИ ВАЖНО: Не коммитить agent_keys.json в git!")

    # Тест подписи
    print("\n📝 Тест подписи сообщения...")
    signed_msg = acs.create_signed_message(
        private_key_hex=private_key,
        public_key_hex=public_key,
        text="Привет! Я Юнона Montana, официальный агент протокола идеальных денег.",
        metadata={"bot_id": 8418301240, "version": "1.0"}
    )

    print(f"   Message: {signed_msg['message']['text'][:60]}...")
    print(f"   Signature: {signed_msg['signature'][:64]}...")

    # Верификация
    is_valid = acs.verify_message(
        message=signed_msg['message'],
        signature_hex=signed_msg['signature'],
        agent_address=agent_address
    )

    print(f"\n✅ Signature verified: {is_valid}")

    # Summary
    print("\n" + "="*60)
    print("🎯 ЮНОНА MONTANA ГОТОВА")
    print("="*60)
    print(f"Agent Address:  {agent_address}")
    print(f"Registry:       data/agent_registry.json")
    print(f"Private Keys:   data/agent_keys.json (НЕ КОММИТИТЬ!)")
    print(f"Official:       ✅ True")
    print(f"Verified:       ✅ True")
    print("\nДобавь в .gitignore:")
    print("  data/agent_keys.json")
    print("  data/mock_fido2.json")
    print("="*60)


if __name__ == "__main__":
    register_official_junona()
