#!/usr/bin/env python3
"""
sovanaglobus.py — Uber для океана (Sovanaglobus Protocol)

Книга Монтана, Глава 04:
> "Бот делает убер между всеми участниками цепочки фрахтования морских.
> (Грузовладельцев, Судовладельцев, Агентов и тд)"
> "Uber убрал диспетчера такси. #Сованаглобус убирает посредника в фрахте."
> "#Сованаглобус = протокол, не продукт.
> Как Bitcoin Core — бесплатный софт."

Sovanaglobus — это ПРОТОКОЛ, не платформа:
- P2P фрахтование без брокера
- Любые валюты (полная совместимость с фиатом)
- Общий язык измерения — время
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set
from enum import Enum
import hashlib


class ParticipantType(Enum):
    """Типы участников рынка фрахта."""
    CARGO_OWNER = "cargo_owner"       # Грузовладелец
    SHIP_OWNER = "ship_owner"         # Судовладелец
    AGENT = "agent"                    # Агент
    PORT = "port"                      # Порт
    BROKER = "broker"                  # Брокер (устраняется)


class CargoType(Enum):
    """Типы грузов."""
    BULK = "bulk"           # Навалочный (зерно, уголь)
    CONTAINER = "container"  # Контейнерный
    TANKER = "tanker"        # Наливной (нефть, газ)
    GENERAL = "general"      # Генеральный
    REEFER = "reefer"        # Рефрижераторный


@dataclass
class Participant:
    """Участник протокола."""
    node_id: str                    # Montana node ID
    participant_type: ParticipantType
    name: str
    montana_address: str            # mt... адрес
    accepted_currencies: List[str] = field(default_factory=lambda: ["USD", "EUR", "Ɉ"])

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "type": self.participant_type.value,
            "name": self.name,
            "address": self.montana_address,
            "currencies": self.accepted_currencies
        }


@dataclass
class FreightRequest:
    """Запрос на фрахт (от грузовладельца)."""
    request_id: str
    cargo_owner: str          # node_id грузовладельца
    cargo_type: CargoType
    origin_port: str
    destination_port: str
    volume: str               # "50,000 MT" / "500 TEU"
    laydays: str              # Период погрузки
    currency: str             # Предпочтительная валюта
    created_at: str

    def to_hash(self) -> str:
        data = f"{self.request_id}:{self.cargo_owner}:{self.origin_port}:{self.destination_port}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class FreightOffer:
    """Предложение фрахта (от судовладельца)."""
    offer_id: str
    request_id: str           # К какому запросу
    ship_owner: str           # node_id судовладельца
    vessel_name: str
    vessel_imo: str
    rate: Decimal             # Ставка
    currency: str             # Валюта ставки
    eta: str                  # Ожидаемое прибытие
    created_at: str

    def to_hash(self) -> str:
        data = f"{self.offer_id}:{self.ship_owner}:{self.rate}:{self.currency}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class FreightContract:
    """Контракт фрахтования (P2P, без брокера)."""
    contract_id: str
    request_id: str
    offer_id: str
    cargo_owner: str
    ship_owner: str
    rate: Decimal
    currency: str
    time_value_juno: Decimal   # Эквивалент в Ɉ
    signed_at: str
    status: str = "active"

    def to_hash(self) -> str:
        data = f"{self.contract_id}:{self.cargo_owner}:{self.ship_owner}:{self.signed_at}"
        return hashlib.sha256(data.encode()).hexdigest()


class SovanaglobusProtocol:
    """
    Протокол P2P фрахтования.

    Книга Монтана:
    > "Все пользуются какой хотят валютой, также как и у Убера.
    > Полная привязка к фиатной системе через тех кто уже в Логистике."
    > "Даём ей общий язык измерения."
    """

    VERSION = "0.1.0"

    # Рынок морского фрахта
    MARKET_SIZE = "$14-16 trillion/year"
    WORLD_TRADE_SHARE = "90% by volume"

    def __init__(self):
        self.participants: Dict[str, Participant] = {}
        self.requests: Dict[str, FreightRequest] = {}
        self.offers: Dict[str, FreightOffer] = {}
        self.contracts: Dict[str, FreightContract] = {}

    def register_participant(
        self,
        node_id: str,
        participant_type: ParticipantType,
        name: str,
        montana_address: str,
        currencies: List[str] = None
    ) -> Participant:
        """
        Зарегистрировать участника в протоколе.

        Args:
            node_id: Montana node ID
            participant_type: Тип участника
            name: Название компании
            montana_address: mt... адрес
            currencies: Принимаемые валюты

        Returns:
            Participant
        """
        participant = Participant(
            node_id=node_id,
            participant_type=participant_type,
            name=name,
            montana_address=montana_address,
            accepted_currencies=currencies or ["USD", "EUR", "Ɉ"]
        )
        self.participants[node_id] = participant
        return participant

    def create_request(
        self,
        cargo_owner_id: str,
        cargo_type: CargoType,
        origin: str,
        destination: str,
        volume: str,
        laydays: str,
        currency: str = "USD"
    ) -> FreightRequest:
        """
        Создать запрос на фрахт.

        Args:
            cargo_owner_id: node_id грузовладельца
            cargo_type: Тип груза
            origin: Порт погрузки
            destination: Порт выгрузки
            volume: Объём
            laydays: Период погрузки
            currency: Валюта

        Returns:
            FreightRequest
        """
        if cargo_owner_id not in self.participants:
            raise ValueError(f"Participant not registered: {cargo_owner_id}")

        request_id = hashlib.sha256(
            f"{cargo_owner_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        request = FreightRequest(
            request_id=request_id,
            cargo_owner=cargo_owner_id,
            cargo_type=cargo_type,
            origin_port=origin,
            destination_port=destination,
            volume=volume,
            laydays=laydays,
            currency=currency,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.requests[request_id] = request
        return request

    def submit_offer(
        self,
        ship_owner_id: str,
        request_id: str,
        vessel_name: str,
        vessel_imo: str,
        rate: float,
        currency: str,
        eta: str
    ) -> FreightOffer:
        """
        Подать предложение на запрос.

        Args:
            ship_owner_id: node_id судовладельца
            request_id: ID запроса
            vessel_name: Название судна
            vessel_imo: IMO номер
            rate: Ставка
            currency: Валюта
            eta: Ожидаемое прибытие

        Returns:
            FreightOffer
        """
        if request_id not in self.requests:
            raise ValueError(f"Request not found: {request_id}")

        offer_id = hashlib.sha256(
            f"{ship_owner_id}:{request_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        offer = FreightOffer(
            offer_id=offer_id,
            request_id=request_id,
            ship_owner=ship_owner_id,
            vessel_name=vessel_name,
            vessel_imo=vessel_imo,
            rate=Decimal(str(rate)),
            currency=currency,
            eta=eta,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.offers[offer_id] = offer
        return offer

    def match_and_sign(
        self,
        request_id: str,
        offer_id: str
    ) -> FreightContract:
        """
        Сопоставить и подписать контракт (P2P, без брокера).

        Args:
            request_id: ID запроса
            offer_id: ID предложения

        Returns:
            FreightContract
        """
        request = self.requests.get(request_id)
        offer = self.offers.get(offer_id)

        if not request or not offer:
            raise ValueError("Request or offer not found")

        if offer.request_id != request_id:
            raise ValueError("Offer does not match request")

        contract_id = hashlib.sha256(
            f"{request_id}:{offer_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Конвертация в Ɉ (через Beeple benchmark)
        # $0.16/sec = базовая ставка
        # Примерная конверсия: rate / 0.16 * estimated_voyage_seconds
        estimated_days = 14  # Типичный рейс
        time_value = offer.rate / Decimal("0.16") * Decimal(estimated_days * 86400)

        contract = FreightContract(
            contract_id=contract_id,
            request_id=request_id,
            offer_id=offer_id,
            cargo_owner=request.cargo_owner,
            ship_owner=offer.ship_owner,
            rate=offer.rate,
            currency=offer.currency,
            time_value_juno=time_value,
            signed_at=datetime.now(timezone.utc).isoformat()
        )

        self.contracts[contract_id] = contract
        return contract

    def get_protocol_stats(self) -> Dict:
        """Статистика протокола."""
        return {
            "version": self.VERSION,
            "market_size": self.MARKET_SIZE,
            "world_trade_share": self.WORLD_TRADE_SHARE,
            "participants": len(self.participants),
            "active_requests": len(self.requests),
            "active_offers": len(self.offers),
            "signed_contracts": len(self.contracts),
            "broker_eliminated": True,
            "common_measure": "Time (Ɉ)"
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    protocol = SovanaglobusProtocol()

    print("=" * 60)
    print("SOVANAGLOBUS — Uber для океана")
    print("=" * 60)
    print("\n'Протокол, не продукт. Как Bitcoin Core.'")

    # Регистрация участников
    print("\n--- РЕГИСТРАЦИЯ УЧАСТНИКОВ ---")

    cargo_owner = protocol.register_participant(
        node_id="node_cargo_001",
        participant_type=ParticipantType.CARGO_OWNER,
        name="Grain Trading LLC",
        montana_address="mt1234567890abcdef1234567890abcdef12345678"
    )
    print(f"Грузовладелец: {cargo_owner.name}")

    ship_owner = protocol.register_participant(
        node_id="node_ship_001",
        participant_type=ParticipantType.SHIP_OWNER,
        name="Baltic Shipping Co",
        montana_address="mtabcdef1234567890abcdef1234567890abcdef12"
    )
    print(f"Судовладелец: {ship_owner.name}")

    # Запрос на фрахт
    print("\n--- ЗАПРОС НА ФРАХТ ---")

    request = protocol.create_request(
        cargo_owner_id="node_cargo_001",
        cargo_type=CargoType.BULK,
        origin="Novorossiysk",
        destination="Rotterdam",
        volume="50,000 MT",
        laydays="01-05 Feb 2026",
        currency="USD"
    )
    print(f"ID: {request.request_id}")
    print(f"Маршрут: {request.origin_port} → {request.destination_port}")
    print(f"Груз: {request.cargo_type.value}, {request.volume}")

    # Предложение от судовладельца
    print("\n--- ПРЕДЛОЖЕНИЕ ---")

    offer = protocol.submit_offer(
        ship_owner_id="node_ship_001",
        request_id=request.request_id,
        vessel_name="MV BALTIC PRIDE",
        vessel_imo="9876543",
        rate=450000,
        currency="USD",
        eta="2026-02-01"
    )
    print(f"Судно: {offer.vessel_name}")
    print(f"Ставка: ${offer.rate:,.0f}")

    # P2P контракт (без брокера!)
    print("\n--- P2P КОНТРАКТ (БЕЗ БРОКЕРА) ---")

    contract = protocol.match_and_sign(request.request_id, offer.offer_id)
    print(f"Contract ID: {contract.contract_id}")
    print(f"Ставка: ${contract.rate:,.0f} ({contract.currency})")
    print(f"Эквивалент в Ɉ: {contract.time_value_juno:,.0f}")
    print(f"Брокер: НЕТ (P2P)")

    # Статистика
    print("\n--- СТАТИСТИКА ПРОТОКОЛА ---")
    stats = protocol.get_protocol_stats()
    print(f"Рынок: {stats['market_size']}")
    print(f"Доля мировой торговли: {stats['world_trade_share']}")
    print(f"Участников: {stats['participants']}")
    print(f"Брокер устранён: {'ДА' if stats['broker_eliminated'] else 'НЕТ'}")
    print(f"Общая мера: {stats['common_measure']}")

    print("\n" + "=" * 60)
    print("'Uber убрал диспетчера. Sovanaglobus убирает брокера.'")
    print("=" * 60)
