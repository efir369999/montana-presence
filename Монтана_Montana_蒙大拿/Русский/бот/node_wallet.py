#!/usr/bin/env python3
# node_wallet.py
# Система кошельков для узлов Montana
# IP адрес = адрес кошелька узла

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List

# ═══════════════════════════════════════════════════════════════════════════════
#                              УЗЛЫ MONTANA СЕТИ
# ═══════════════════════════════════════════════════════════════════════════════

# Официальные узлы Montana
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
#                              СИСТЕМА КОШЕЛЬКОВ УЗЛОВ
# ═══════════════════════════════════════════════════════════════════════════════

class NodeWalletSystem:
    """
    Система кошельков для узлов Montana

    Концепция:
    - IP адрес узла = адрес кошелька
    - Каждый узел имеет выделенный IP
    - IP = ключ + адрес одновременно
    - Узлы могут быть: full, light, client
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "nodes"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nodes_file = self.data_dir / "registered_nodes.json"
        self.wallets_file = self.data_dir / "node_wallets.json"

        # Инициализация официальных узлов
        self._init_official_nodes()

    def _init_official_nodes(self):
        """Инициализировать официальные узлы Montana"""
        nodes = self._load_nodes()
        wallets = self._load_wallets()

        for node_name, node_info in MONTANA_NODES.items():
            node_ip = node_info["ip"]

            # Регистрируем узел если его нет
            if node_ip not in nodes:
                nodes[node_ip] = {
                    "name": node_name,
                    "ip": node_ip,
                    "location": node_info["location"],
                    "type": node_info["type"],
                    "operator": node_info["operator"],
                    "priority": node_info["priority"],
                    "official": True,
                    "registered_at": datetime.now(timezone.utc).isoformat()
                }

            # Создаем кошелек если его нет
            if node_ip not in wallets:
                wallets[node_ip] = {
                    "address": node_ip,  # IP = адрес кошелька
                    "balance": 0,        # Баланс в секундах
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "transactions": []
                }

        self._save_nodes(nodes)
        self._save_wallets(wallets)

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
        ip: str,
        node_name: str,
        location: str,
        operator: str,
        node_type: str = "light"
    ) -> dict:
        """
        Зарегистрировать новый узел

        Args:
            ip: IP адрес узла (станет адресом кошелька)
            node_name: Имя узла
            location: Локация (например "🇷🇺 Moscow")
            operator: Оператор узла
            node_type: Тип узла (full, light, client)

        Returns:
            Информация о зарегистрированном узле с кошельком
        """
        nodes = self._load_nodes()
        wallets = self._load_wallets()

        # Проверка существования
        if ip in nodes:
            return {"error": "Node already registered", "node": nodes[ip]}

        # Регистрация узла
        node_data = {
            "name": node_name,
            "ip": ip,
            "location": location,
            "type": node_type,
            "operator": operator,
            "official": False,
            "priority": len(nodes) + 10,  # После официальных
            "registered_at": datetime.now(timezone.utc).isoformat()
        }

        nodes[ip] = node_data

        # Создание кошелька
        wallet_data = {
            "address": ip,  # IP = адрес кошелька
            "balance": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "transactions": []
        }

        wallets[ip] = wallet_data

        self._save_nodes(nodes)
        self._save_wallets(wallets)

        return {
            "success": True,
            "node": node_data,
            "wallet": wallet_data
        }

    def get_node_info(self, ip: str) -> Optional[dict]:
        """Получить информацию об узле"""
        nodes = self._load_nodes()
        return nodes.get(ip)

    def get_node_wallet(self, ip: str) -> Optional[dict]:
        """Получить кошелек узла"""
        wallets = self._load_wallets()
        return wallets.get(ip)

    def get_all_nodes(self) -> List[dict]:
        """Получить все зарегистрированные узлы"""
        nodes = self._load_nodes()
        return list(nodes.values())

    def add_transaction(
        self,
        node_ip: str,
        amount: float,
        tx_type: str,
        description: str
    ) -> bool:
        """
        Добавить транзакцию в кошелек узла

        Args:
            node_ip: IP адрес узла
            amount: Сумма в секундах (может быть отрицательной)
            tx_type: Тип транзакции (reward, fee, transfer)
            description: Описание транзакции
        """
        wallets = self._load_wallets()

        if node_ip not in wallets:
            return False

        wallet = wallets[node_ip]

        # Создаем транзакцию
        transaction = {
            "amount": amount,
            "type": tx_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balance_before": wallet["balance"],
            "balance_after": wallet["balance"] + amount
        }

        # Обновляем баланс
        wallet["balance"] += amount
        wallet["transactions"].append(transaction)

        self._save_wallets(wallets)
        return True

    def get_node_display(self, ip: str) -> str:
        """
        Получить отображение узла с кошельком для бота

        Формат аналогичен пользовательскому:
        - IP = адрес кошелька
        - Показываем баланс
        - Объясняем что IP = ключ + адрес
        """
        node = self.get_node_info(ip)
        wallet = self.get_node_wallet(ip)

        if not node or not wallet:
            return "Узел не найден"

        display = f"Ɉ\n\n"
        display += f"**Узел Montana:** {node['location']}\n\n"
        display += f"**Адрес кошелька:** `{ip}`\n"
        display += f"_(выделенный IP адрес — одновременно адрес кошелька и ключ)_\n\n"
        display += f"**Тип:** {node['type'].upper()} NODE\n"
        display += f"**Оператор:** {node['operator']}\n"
        display += f"**Приоритет:** #{node['priority']}\n\n"
        display += f"💰 **Баланс:** {wallet['balance']:.2f} секунд\n\n"

        if wallet['transactions']:
            display += f"📊 **Последние транзакции:**\n"
            for tx in wallet['transactions'][-3:]:
                sign = "+" if tx['amount'] >= 0 else ""
                display += f"  • {sign}{tx['amount']:.2f}s — {tx['description']}\n"

        display += f"\n⚠️ При смене IP адреса — переноси монеты заранее."

        return display

    def get_network_summary(self) -> str:
        """Получить сводку по всей сети узлов"""
        nodes = self.get_all_nodes()
        wallets = self._load_wallets()

        total_nodes = len(nodes)
        official_nodes = sum(1 for n in nodes if n.get('official', False))
        full_nodes = sum(1 for n in nodes if n.get('type') == 'full')
        total_balance = sum(w['balance'] for w in wallets.values())

        summary = f"Ɉ\n\n"
        summary += f"**MONTANA NETWORK**\n\n"
        summary += f"🌐 **Всего узлов:** {total_nodes}\n"
        summary += f"⭐️ **Официальных:** {official_nodes}\n"
        summary += f"🔷 **Full nodes:** {full_nodes}\n"
        summary += f"💰 **Общий баланс сети:** {total_balance:.2f} секунд\n\n"
        summary += f"**Узлы:**\n"

        for node in sorted(nodes, key=lambda x: x.get('priority', 999)):
            wallet = wallets.get(node['ip'], {})
            balance = wallet.get('balance', 0)
            official = "⭐️" if node.get('official') else "🔹"
            summary += f"{official} {node['location']} — `{node['ip']}` — {balance:.0f}s\n"

        return summary


# ═══════════════════════════════════════════════════════════════════════════════
#                              ГЛОБАЛЬНЫЙ ИНСТАНС
# ═══════════════════════════════════════════════════════════════════════════════

_node_wallet_system = None

def get_node_wallet_system(data_dir: Path = None) -> NodeWalletSystem:
    """Получить глобальную систему кошельков узлов"""
    global _node_wallet_system
    if _node_wallet_system is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _node_wallet_system = NodeWalletSystem(data_dir)
    return _node_wallet_system
