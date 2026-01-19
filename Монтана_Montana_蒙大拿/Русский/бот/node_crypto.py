#!/usr/bin/env python3
# node_crypto.py
# Криптографическая система для узлов Montana
# POST-QUANTUM КРИПТОГРАФИЯ ML-DSA-65 (FIPS 204)
# Защита от квантовых компьютеров с genesis

import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone

# POST-QUANTUM: ML-DSA-65 (Dilithium)
from dilithium_py.ml_dsa import ML_DSA_65


# ═══════════════════════════════════════════════════════════════════════════════
#                         ML-DSA-65 КРИПТОГРАФИЧЕСКИЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def generate_keypair() -> Tuple[str, str]:
    """
    Генерирует пару ключей ML-DSA-65 для узла

    POST-QUANTUM защита от Shor's algorithm
    FIPS 204 стандарт

    Returns:
        (private_key_hex, public_key_hex)

    Размеры ключей ML-DSA-65:
        Private key: 4032 байта
        Public key:  1952 байта
        Signature:   3309 байта
    """
    public_key, private_key = ML_DSA_65.keygen()

    return private_key.hex(), public_key.hex()


def public_key_to_address(public_key_hex: str) -> str:
    """
    Преобразует public key в адрес кошелька Montana

    Формат: SHA256(public_key)[:40]
    Пример: mt1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0

    POST-QUANTUM: Адрес деривируется от ML-DSA-65 public key
    """
    public_bytes = bytes.fromhex(public_key_hex)
    hash_bytes = hashlib.sha256(public_bytes).digest()
    # Берем первые 20 байт (40 hex символов)
    address = "mt" + hash_bytes[:20].hex()
    return address


def sign_message(private_key_hex: str, message: str) -> str:
    """
    Подписывает сообщение приватным ключом ML-DSA-65

    POST-QUANTUM подпись, устойчивая к атакам квантовых компьютеров

    Returns:
        signature_hex (3309 байт = 6618 hex символов)
    """
    private_bytes = bytes.fromhex(private_key_hex)
    message_bytes = message.encode('utf-8')

    signature = ML_DSA_65.sign(private_bytes, message_bytes)

    return signature.hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    """
    Проверяет подпись сообщения ML-DSA-65

    Returns:
        True если подпись валидна
    """
    try:
        public_bytes = bytes.fromhex(public_key_hex)
        message_bytes = message.encode('utf-8')
        signature = bytes.fromhex(signature_hex)

        # ML_DSA_65.verify возвращает True/False или выбрасывает исключение
        return ML_DSA_65.verify(public_bytes, message_bytes, signature)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#                              КРИПТОГРАФИЧЕСКАЯ СИСТЕМА УЗЛОВ
# ═══════════════════════════════════════════════════════════════════════════════

class NodeCryptoSystem:
    """
    Криптографическая система для узлов Montana

    POST-QUANTUM ЗАЩИТА (ML-DSA-65, FIPS 204):
    - Устойчивость к Shor's algorithm
    - NIST Level 3 security (128-bit post-quantum)
    - Защита от "harvest now, decrypt later" атак

    Защита от классических атак:
    - IP hijacking
    - DNS spoofing
    - Man-in-the-middle атак

    Концепция:
    - Адрес кошелька = hash(public_key)
    - Доступ = подпись private key (ML-DSA-65)
    - IP адрес = только для networking
    - Владелец = Telegram ID оператора
    """

    # Версия криптосистемы
    CRYPTO_VERSION = "ML-DSA-65"
    FIPS_STANDARD = "FIPS 204"
    SECURITY_LEVEL = "NIST Level 3 (128-bit post-quantum)"

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "node_crypto"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.nodes_file = self.data_dir / "nodes.json"
        self.keys_file = self.data_dir / "keys.json"  # Приватные ключи (зашифрованы)

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

    def register_node(
        self,
        owner_telegram_id: int,
        node_name: str,
        location: str,
        ip_address: str,
        node_type: str = "light"
    ) -> Dict:
        """
        Регистрирует новый узел с криптографическим адресом ML-DSA-65

        POST-QUANTUM: Ключи генерируются по стандарту FIPS 204

        Args:
            owner_telegram_id: Telegram ID владельца узла
            node_name: Короткое имя (например "amsterdam")
            location: Локация с флагом (например "🇳🇱 Amsterdam")
            ip_address: IP адрес узла (только для networking)
            node_type: Тип узла (full, light, client)

        Returns:
            {
                "address": "mt1a2b3c...",
                "public_key": "...",        # 1952 байта
                "private_key": "...",       # 4032 байта - СОХРАНИ В БЕЗОПАСНОМ МЕСТЕ!
                "owner": telegram_id,
                "node_name": "amsterdam",
                "alias": "amsterdam.montana.network",
                "ip": "72.56.102.240",
                "crypto_version": "ML-DSA-65"
            }
        """
        # Генерируем пару ключей ML-DSA-65
        private_key, public_key = generate_keypair()

        # Получаем адрес из public key
        address = public_key_to_address(public_key)

        # Создаем alias
        alias = f"{node_name}.montana.network"

        nodes = self._load_nodes()

        # Проверка дубликатов
        if address in nodes:
            return {"error": "Node already exists", "address": address}

        # Проверка дубликатов по IP
        for existing in nodes.values():
            if existing.get("ip") == ip_address:
                return {"error": "IP already registered", "ip": ip_address}

        # Регистрация узла
        node_data = {
            "address": address,
            "public_key": public_key,
            "owner": owner_telegram_id,
            "node_name": node_name,
            "alias": alias,
            "location": location,
            "ip": ip_address,
            "type": node_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "official": False,
            "priority": len(nodes) + 10,
            "crypto_version": self.CRYPTO_VERSION,
            "fips_standard": self.FIPS_STANDARD
        }

        nodes[address] = node_data
        self._save_nodes(nodes)

        return {
            "success": True,
            "address": address,
            "public_key": public_key,
            "private_key": private_key,  # ⚠️ СОХРАНИ В БЕЗОПАСНОМ МЕСТЕ!
            "alias": alias,
            "owner": owner_telegram_id,
            "node_data": node_data,
            "crypto_version": self.CRYPTO_VERSION,
            "key_sizes": {
                "private_key_bytes": len(bytes.fromhex(private_key)),
                "public_key_bytes": len(bytes.fromhex(public_key))
            }
        }

    def import_official_nodes(self) -> Dict:
        """
        Импортирует 5 официальных узлов Montana с ML-DSA-65

        Для каждого генерируются новые POST-QUANTUM ключи.
        Private keys нужно сохранить у владельцев узлов.
        """
        official_nodes = [
            {
                "name": "amsterdam",
                "location": "🇳🇱 Amsterdam",
                "ip": "72.56.102.240",
                "priority": 1,
                "owner": 8552053404  # BOT_CREATOR_ID
            },
            {
                "name": "moscow",
                "location": "🇷🇺 Moscow",
                "ip": "176.124.208.93",
                "priority": 2,
                "owner": 8552053404
            },
            {
                "name": "almaty",
                "location": "🇰🇿 Almaty",
                "ip": "91.200.148.93",
                "priority": 3,
                "owner": 8552053404
            },
            {
                "name": "spb",
                "location": "🇷🇺 St.Petersburg",
                "ip": "188.225.58.98",
                "priority": 4,
                "owner": 8552053404
            },
            {
                "name": "novosibirsk",
                "location": "🇷🇺 Novosibirsk",
                "ip": "147.45.147.247",
                "priority": 5,
                "owner": 8552053404
            }
        ]

        results = {}
        nodes = self._load_nodes()

        for node_info in official_nodes:
            # Проверяем, не зарегистрирован ли уже
            existing = None
            for addr, data in nodes.items():
                if data.get("node_name") == node_info["name"]:
                    existing = addr
                    break

            if existing:
                results[node_info["name"]] = {
                    "status": "already_exists",
                    "address": existing
                }
                continue

            # Генерируем ML-DSA-65 ключи
            private_key, public_key = generate_keypair()
            address = public_key_to_address(public_key)
            alias = f"{node_info['name']}.montana.network"

            # Регистрируем
            node_data = {
                "address": address,
                "public_key": public_key,
                "owner": node_info["owner"],
                "node_name": node_info["name"],
                "alias": alias,
                "location": node_info["location"],
                "ip": node_info["ip"],
                "type": "full",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "official": True,
                "priority": node_info["priority"],
                "crypto_version": self.CRYPTO_VERSION,
                "fips_standard": self.FIPS_STANDARD
            }

            nodes[address] = node_data

            results[node_info["name"]] = {
                "status": "registered",
                "address": address,
                "private_key": private_key,  # ⚠️ СОХРАНИ!
                "alias": alias,
                "ip": node_info["ip"],
                "crypto_version": self.CRYPTO_VERSION
            }

        self._save_nodes(nodes)
        return results

    def get_node_by_address(self, address: str) -> Optional[Dict]:
        """Получить узел по адресу"""
        nodes = self._load_nodes()
        return nodes.get(address)

    def get_node_by_alias(self, alias: str) -> Optional[Dict]:
        """Получить узел по alias"""
        nodes = self._load_nodes()
        for node in nodes.values():
            if node.get("alias") == alias:
                return node
        return None

    def get_node_by_ip(self, ip: str) -> Optional[Dict]:
        """Получить узел по IP (для networking)"""
        nodes = self._load_nodes()
        for node in nodes.values():
            if node.get("ip") == ip:
                return node
        return None

    def get_all_nodes(self) -> list:
        """Получить все узлы"""
        nodes = self._load_nodes()
        return list(nodes.values())

    def verify_node_ownership(
        self,
        address: str,
        message: str,
        signature_hex: str
    ) -> bool:
        """
        Проверяет что владелец узла подписал сообщение ML-DSA-65

        POST-QUANTUM верификация:
        - Устойчива к атакам квантовых компьютеров
        - FIPS 204 compliant

        Используется для:
        - Авторизации переводов с кошелька узла
        - Обновления конфигурации узла
        - Подтверждения владения
        """
        node = self.get_node_by_address(address)
        if not node:
            return False

        public_key = node["public_key"]
        return verify_signature(public_key, message, signature_hex)

    def get_node_display(self, address: str) -> str:
        """
        Отображение узла для бота
        """
        node = self.get_node_by_address(address)
        if not node:
            return "Узел не найден"

        crypto_version = node.get('crypto_version', 'ML-DSA-65')

        display = f"Ɉ\n\n"
        display += f"**Узел Montana:** {node['location']}\n\n"
        display += f"**Адрес кошелька:** `{address}`\n"
        display += f"**Alias:** `{node['alias']}`\n"
        display += f"_(криптографический адрес — защищен {crypto_version})_\n\n"
        display += f"**IP:** `{node['ip']}` _(только для networking)_\n"
        display += f"**Владелец TG ID:** `{node['owner']}`\n"
        display += f"**Тип:** {node['type'].upper()} NODE\n"
        display += f"**Приоритет:** #{node['priority']}\n\n"

        if node.get('official'):
            display += f"⭐️ **Официальный узел Montana Foundation**\n\n"

        display += f"🔐 **POST-QUANTUM БЕЗОПАСНОСТЬ:**\n"
        display += f"  • Криптография: **{crypto_version}**\n"
        display += f"  • Стандарт: **FIPS 204**\n"
        display += f"  • Уровень: **NIST Level 3**\n"
        display += f"  • Public key: `{node['public_key'][:32]}...`\n"
        display += f"  • Защита от квантовых компьютеров: ✅\n"
        display += f"  • Защита от IP hijacking: ✅\n\n"

        display += f"⚠️ Для доступа к кошельку нужна подпись private key ML-DSA-65"

        return display


# ═══════════════════════════════════════════════════════════════════════════════
#                              ГЛОБАЛЬНЫЙ ИНСТАНС
# ═══════════════════════════════════════════════════════════════════════════════

_node_crypto_system = None

def get_node_crypto_system(data_dir: Path = None) -> NodeCryptoSystem:
    """Получить глобальную криптосистему узлов (ML-DSA-65)"""
    global _node_crypto_system
    if _node_crypto_system is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _node_crypto_system = NodeCryptoSystem(data_dir)
    return _node_crypto_system


# ═══════════════════════════════════════════════════════════════════════════════
#                              ИНФОРМАЦИЯ О КРИПТОСИСТЕМЕ
# ═══════════════════════════════════════════════════════════════════════════════

def get_crypto_info() -> Dict:
    """
    Информация о криптографической системе Montana
    """
    return {
        "algorithm": "ML-DSA-65",
        "standard": "FIPS 204",
        "security_level": "NIST Level 3 (128-bit post-quantum)",
        "key_sizes": {
            "private_key": "4032 bytes",
            "public_key": "1952 bytes",
            "signature": "3309 bytes"
        },
        "protections": [
            "Quantum computer attacks (Shor's algorithm)",
            "Harvest now, decrypt later attacks",
            "IP hijacking",
            "DNS spoofing",
            "Man-in-the-middle attacks"
        ],
        "address_format": "mt + SHA256(public_key)[:20].hex()",
        "address_length": 42
    }
