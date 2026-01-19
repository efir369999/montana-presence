#!/usr/bin/env python3
# node_wallet.py
# Система кошельков для узлов Montana
# POST-QUANTUM КРИПТОГРАФИЯ ML-DSA-65 (FIPS 204)
# Криптографический адрес = hash(public_key), НЕ IP

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List

# POST-QUANTUM криптосистема
from node_crypto import (
    generate_keypair,
    public_key_to_address,
    sign_message,
    verify_signature,
    get_crypto_info
)


# ═══════════════════════════════════════════════════════════════════════════════
#                              УЗЛЫ MONTANA СЕТИ
# ═══════════════════════════════════════════════════════════════════════════════

# Официальные узлы Montana (IP только для networking)
MONTANA_NODES = {
    "amsterdam": {
        "ip": "72.56.102.240",
        "priority": 1,
        "location": "🇳🇱 Amsterdam",
        "type": "full",
        "operator": "Montana Foundation"
    },
    "moscow": {
        "ip": "176.124.208.93",
        "priority": 2,
        "location": "🇷🇺 Moscow",
        "type": "full",
        "operator": "Montana Foundation"
    },
    "almaty": {
        "ip": "91.200.148.93",
        "priority": 3,
        "location": "🇰🇿 Almaty",
        "type": "full",
        "operator": "Montana Foundation"
    },
    "spb": {
        "ip": "188.225.58.98",
        "priority": 4,
        "location": "🇷🇺 St.Petersburg",
        "type": "full",
        "operator": "Montana Foundation"
    },
    "novosibirsk": {
        "ip": "147.45.147.247",
        "priority": 5,
        "location": "🇷🇺 Novosibirsk",
        "type": "full",
        "operator": "Montana Foundation"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
#                     СИСТЕМА КОШЕЛЬКОВ УЗЛОВ (ML-DSA-65)
# ═══════════════════════════════════════════════════════════════════════════════

class NodeWalletSystem:
    """
    Система кошельков для узлов Montana

    POST-QUANTUM КРИПТОГРАФИЯ (ML-DSA-65, FIPS 204):
    - Адрес кошелька = mt + SHA256(public_key)[:20].hex()
    - Ключи = ML-DSA-65 (устойчивы к квантовым компьютерам)
    - IP адрес = ТОЛЬКО для networking, НЕ для идентификации

    Концепция:
    - Узел владеет криптографическим адресом (mt...)
    - Для доступа нужен private key (4032 байта)
    - IP может меняться — адрес кошелька НЕ меняется
    - Защита от IP hijacking, DNS spoofing, MITM
    """

    # Версия системы
    VERSION = "2.0.0-ML-DSA-65"

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "nodes"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nodes_file = self.data_dir / "registered_nodes.json"
        self.wallets_file = self.data_dir / "node_wallets.json"
        self.keys_file = self.data_dir / "node_private_keys.json"  # ⚠️ СЕКРЕТНО

    def _load_nodes(self) -> dict:
        """Загрузить зарегистрированные узлы"""
        if self.nodes_file.exists():
            with open(self.nodes_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_nodes(self, nodes: dict):
        """Сохранить узлы"""
        with open(self.nodes_file, 'w', encoding='utf-8') as f:
            json.dump(nodes, f, indent=2, ensure_ascii=False)

    def _load_wallets(self) -> dict:
        """Загрузить кошельки узлов"""
        if self.wallets_file.exists():
            with open(self.wallets_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_wallets(self, wallets: dict):
        """Сохранить кошельки"""
        with open(self.wallets_file, 'w', encoding='utf-8') as f:
            json.dump(wallets, f, indent=2, ensure_ascii=False)

    def register_node(
        self,
        owner_telegram_id: int,
        node_name: str,
        location: str,
        ip_address: str,
        node_type: str = "light"
    ) -> dict:
        """
        Зарегистрировать новый узел с POST-QUANTUM криптографией

        ПРОЦЕДУРА ГЕНЕРАЦИИ:
        1. Генерируется пара ключей ML-DSA-65 (FIPS 204)
        2. Из public key вычисляется адрес кошелька (mt...)
        3. Private key ДОЛЖЕН быть сохранен владельцем
        4. IP адрес используется ТОЛЬКО для networking

        Args:
            owner_telegram_id: Telegram ID владельца
            node_name: Имя узла (например "tokyo")
            location: Локация (например "🇯🇵 Tokyo")
            ip_address: IP адрес (для networking, НЕ для идентификации)
            node_type: Тип узла (full, light, client)

        Returns:
            Полная информация с ИНСТРУКЦИЯМИ по ключам
        """
        nodes = self._load_nodes()
        wallets = self._load_wallets()

        # Проверка дубликата IP
        for addr, node in nodes.items():
            if node.get("ip") == ip_address:
                return {
                    "error": "IP already registered",
                    "ip": ip_address,
                    "existing_address": addr
                }

        # ═══════════════════════════════════════════════════════════════════
        # ГЕНЕРАЦИЯ POST-QUANTUM КЛЮЧЕЙ ML-DSA-65
        # ═══════════════════════════════════════════════════════════════════

        print("\n" + "═" * 60)
        print("   ГЕНЕРАЦИЯ POST-QUANTUM КЛЮЧЕЙ ML-DSA-65")
        print("═" * 60)

        private_key, public_key = generate_keypair()
        address = public_key_to_address(public_key)
        alias = f"{node_name}.montana.network"

        print(f"\n✅ Ключи сгенерированы по стандарту FIPS 204")
        print(f"   • Private key: {len(bytes.fromhex(private_key))} байт")
        print(f"   • Public key:  {len(bytes.fromhex(public_key))} байт")

        # Проверка уникальности адреса
        if address in nodes:
            return {"error": "Address collision (impossible)", "address": address}

        # Регистрация узла
        node_data = {
            "address": address,
            "public_key": public_key,
            "owner": owner_telegram_id,
            "name": node_name,
            "alias": alias,
            "ip": ip_address,
            "location": location,
            "type": node_type,
            "official": False,
            "priority": len(nodes) + 10,
            "crypto_version": "ML-DSA-65",
            "fips_standard": "FIPS 204",
            "registered_at": datetime.now(timezone.utc).isoformat()
        }

        nodes[address] = node_data

        # Создание кошелька
        wallet_data = {
            "address": address,
            "balance": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "transactions": []
        }

        wallets[address] = wallet_data

        self._save_nodes(nodes)
        self._save_wallets(wallets)

        # ═══════════════════════════════════════════════════════════════════
        # ИНСТРУКЦИИ ПО БЕЗОПАСНОСТИ КЛЮЧЕЙ
        # ═══════════════════════════════════════════════════════════════════

        instructions = self._generate_key_instructions(
            address=address,
            private_key=private_key,
            public_key=public_key,
            alias=alias,
            location=location
        )

        print(instructions)

        return {
            "success": True,
            "address": address,
            "public_key": public_key,
            "private_key": private_key,  # ⚠️ СОХРАНИ НЕМЕДЛЕННО!
            "alias": alias,
            "owner": owner_telegram_id,
            "node_data": node_data,
            "wallet": wallet_data,
            "crypto_info": get_crypto_info(),
            "instructions": instructions,
            "key_sizes": {
                "private_key_bytes": len(bytes.fromhex(private_key)),
                "public_key_bytes": len(bytes.fromhex(public_key))
            }
        }

    def _generate_key_instructions(
        self,
        address: str,
        private_key: str,
        public_key: str,
        alias: str,
        location: str
    ) -> str:
        """Генерирует инструкции по работе с ключами"""

        return f"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 УЗЕЛ MONTANA ЗАРЕГИСТРИРОВАН 🔐
                      POST-QUANTUM КРИПТОГРАФИЯ ML-DSA-65
═══════════════════════════════════════════════════════════════════════════════

📍 ЛОКАЦИЯ: {location}
🏷️  ALIAS: {alias}

═══════════════════════════════════════════════════════════════════════════════
                           АДРЕС КОШЕЛЬКА
═══════════════════════════════════════════════════════════════════════════════

{address}

Это ваш постоянный адрес. Он НЕ зависит от IP адреса.
Вы можете менять IP — адрес кошелька останется прежним.

═══════════════════════════════════════════════════════════════════════════════
                    ⚠️  ПРИВАТНЫЙ КЛЮЧ (СОХРАНИ!) ⚠️
═══════════════════════════════════════════════════════════════════════════════

{private_key}

⚠️  КРИТИЧЕСКИ ВАЖНО:

1. СОХРАНИ этот ключ СЕЙЧАС в безопасном месте
2. Это ЕДИНСТВЕННАЯ возможность получить ключ
3. Мы НЕ храним приватные ключи
4. Потеря ключа = потеря доступа к кошельку НАВСЕГДА

📌 РЕКОМЕНДАЦИИ ПО ХРАНЕНИЮ:
   • Запиши на бумагу и храни в сейфе
   • Используй password manager (1Password, Bitwarden)
   • Сделай backup на зашифрованном USB
   • НИКОГДА не отправляй по email/мессенджерам
   • НИКОМУ не показывай

═══════════════════════════════════════════════════════════════════════════════
                         PUBLIC KEY (можно показывать)
═══════════════════════════════════════════════════════════════════════════════

{public_key[:64]}...
(всего {len(bytes.fromhex(public_key))} байт)

Public key можно безопасно показывать — он нужен для верификации
ваших подписей другими участниками сети.

═══════════════════════════════════════════════════════════════════════════════
                         🛡️  ЗАЩИТА ML-DSA-65
═══════════════════════════════════════════════════════════════════════════════

✅ Стандарт: FIPS 204 (NIST)
✅ Уровень безопасности: NIST Level 3 (128-bit post-quantum)
✅ Защита от квантовых компьютеров (Shor's algorithm)
✅ Защита от "harvest now, decrypt later" атак
✅ Защита от IP hijacking (адрес не зависит от IP)
✅ Защита от DNS spoofing
✅ Защита от MITM атак

═══════════════════════════════════════════════════════════════════════════════
                         📋 ЧТО ДЕЛАТЬ ДАЛЬШЕ
═══════════════════════════════════════════════════════════════════════════════

1. СОХРАНИ приватный ключ ПРЯМО СЕЙЧАС
2. Проверь что он сохранился правильно
3. Удали его из этого вывода/лога
4. Настрой свой узел для работы в сети Montana

Для подписи транзакций используй:
   from node_crypto import sign_message
   signature = sign_message(private_key, message)

Для верификации:
   from node_crypto import verify_signature
   valid = verify_signature(public_key, message, signature)

═══════════════════════════════════════════════════════════════════════════════
                    Ɉ MONTANA — POST-QUANTUM FROM GENESIS
═══════════════════════════════════════════════════════════════════════════════
"""

    def get_node_by_address(self, address: str) -> Optional[dict]:
        """Получить узел по криптографическому адресу (mt...)"""
        nodes = self._load_nodes()
        return nodes.get(address)

    def get_node_by_ip(self, ip: str) -> Optional[dict]:
        """Получить узел по IP (для networking)"""
        nodes = self._load_nodes()
        for node in nodes.values():
            if node.get("ip") == ip:
                return node
        return None

    def get_node_by_alias(self, alias: str) -> Optional[dict]:
        """Получить узел по alias"""
        nodes = self._load_nodes()
        for node in nodes.values():
            if node.get("alias") == alias:
                return node
        return None

    def get_node_wallet(self, address: str) -> Optional[dict]:
        """Получить кошелек узла по адресу"""
        wallets = self._load_wallets()
        return wallets.get(address)

    def get_all_nodes(self) -> List[dict]:
        """Получить все зарегистрированные узлы"""
        nodes = self._load_nodes()
        return list(nodes.values())

    def add_transaction(
        self,
        address: str,
        amount: float,
        tx_type: str,
        description: str,
        signature: str = None
    ) -> bool:
        """
        Добавить транзакцию в кошелек узла

        Args:
            address: Криптографический адрес узла (mt...)
            amount: Сумма в секундах (может быть отрицательной)
            tx_type: Тип транзакции (reward, fee, transfer)
            description: Описание транзакции
            signature: ML-DSA-65 подпись (для исходящих транзакций)
        """
        wallets = self._load_wallets()

        if address not in wallets:
            return False

        wallet = wallets[address]

        # Создаем транзакцию
        transaction = {
            "amount": amount,
            "type": tx_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balance_before": wallet["balance"],
            "balance_after": wallet["balance"] + amount,
            "signature": signature[:32] + "..." if signature else None
        }

        # Обновляем баланс
        wallet["balance"] += amount
        wallet["transactions"].append(transaction)

        self._save_wallets(wallets)
        return True

    def verify_transaction(
        self,
        address: str,
        message: str,
        signature: str
    ) -> bool:
        """
        Верифицировать транзакцию по ML-DSA-65 подписи

        Args:
            address: Адрес отправителя (mt...)
            message: Сообщение транзакции
            signature: Подпись ML-DSA-65
        """
        node = self.get_node_by_address(address)
        if not node:
            return False

        public_key = node.get("public_key")
        if not public_key:
            return False

        return verify_signature(public_key, message, signature)

    def get_node_display(self, address: str) -> str:
        """
        Получить отображение узла с кошельком для бота
        """
        node = self.get_node_by_address(address)
        wallet = self.get_node_wallet(address)

        if not node or not wallet:
            return "Узел не найден"

        crypto_version = node.get('crypto_version', 'ML-DSA-65')

        display = f"Ɉ\n\n"
        display += f"**Узел Montana:** {node['location']}\n\n"
        display += f"**Адрес кошелька:** `{address}`\n"
        display += f"**Alias:** `{node.get('alias', 'N/A')}`\n"
        display += f"_(криптографический адрес — защищен {crypto_version})_\n\n"
        display += f"**IP:** `{node['ip']}` _(только для networking)_\n"
        display += f"**Владелец TG ID:** `{node.get('owner', 'N/A')}`\n"
        display += f"**Тип:** {node['type'].upper()} NODE\n"
        display += f"**Приоритет:** #{node.get('priority', 'N/A')}\n\n"

        if node.get('official'):
            display += f"⭐️ **Официальный узел Montana Foundation**\n\n"

        display += f"💰 **Баланс:** {wallet['balance']:.2f} секунд\n\n"

        if wallet['transactions']:
            display += f"📊 **Последние транзакции:**\n"
            for tx in wallet['transactions'][-3:]:
                sign = "+" if tx['amount'] >= 0 else ""
                display += f"  • {sign}{tx['amount']:.2f}s — {tx['description']}\n"
            display += "\n"

        display += f"🔐 **POST-QUANTUM БЕЗОПАСНОСТЬ:**\n"
        display += f"  • Криптография: **{crypto_version}**\n"
        display += f"  • Стандарт: **{node.get('fips_standard', 'FIPS 204')}**\n"
        display += f"  • Защита от квантовых компьютеров: ✅\n\n"

        display += f"⚠️ Адрес НЕ зависит от IP. Смена IP — кошелек остается."

        return display

    def get_network_summary(self) -> str:
        """Получить сводку по всей сети узлов"""
        nodes = self.get_all_nodes()
        wallets = self._load_wallets()

        total_nodes = len(nodes)
        official_nodes = sum(1 for n in nodes if n.get('official', False))
        full_nodes = sum(1 for n in nodes if n.get('type') == 'full')
        pq_nodes = sum(1 for n in nodes if n.get('crypto_version') == 'ML-DSA-65')
        total_balance = sum(w['balance'] for w in wallets.values())

        summary = f"Ɉ\n\n"
        summary += f"**MONTANA NETWORK**\n"
        summary += f"_POST-QUANTUM FROM GENESIS_\n\n"
        summary += f"🌐 **Всего узлов:** {total_nodes}\n"
        summary += f"⭐️ **Официальных:** {official_nodes}\n"
        summary += f"🔷 **Full nodes:** {full_nodes}\n"
        summary += f"🔐 **ML-DSA-65 nodes:** {pq_nodes}\n"
        summary += f"💰 **Общий баланс сети:** {total_balance:.2f} секунд\n\n"
        summary += f"**Узлы:**\n"

        for node in sorted(nodes, key=lambda x: x.get('priority', 999)):
            wallet = wallets.get(node.get('address', ''), {})
            balance = wallet.get('balance', 0)
            official = "⭐️" if node.get('official') else "🔹"
            pq = "🔐" if node.get('crypto_version') == 'ML-DSA-65' else "🔓"
            addr = node.get('address', node.get('ip', 'N/A'))[:16] + "..."
            summary += f"{official}{pq} {node['location']} — `{addr}` — {balance:.0f}s\n"

        return summary


# ═══════════════════════════════════════════════════════════════════════════════
#                              ГЛОБАЛЬНЫЙ ИНСТАНС
# ═══════════════════════════════════════════════════════════════════════════════

_node_wallet_system = None

def get_node_wallet_system(data_dir: Path = None) -> NodeWalletSystem:
    """Получить глобальную систему кошельков узлов (ML-DSA-65)"""
    global _node_wallet_system
    if _node_wallet_system is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _node_wallet_system = NodeWalletSystem(data_dir)
    return _node_wallet_system
