#!/usr/bin/env python3
"""
ais_oracle.py — Децентрализованный оракул морских данных Montana

Книга Монтана, Глава 04:
> "Они построили трубу. Мы пускаем по ней время."
> "MarineTraffic + Montana = время судна конвертируется в Ɉ автоматически."
> "AIS-сигналы транслируются открыто на VHF-частотах.
> Любой с AIS-приёмником может их собирать."

AIS (Automatic Identification System) — международный стандарт.
Суда транслируют свою позицию, курс, скорость на VHF-частотах.
Инфраструктура уже построена — миллиарды $ инвестиций.

Montana использует эту инфраструктуру как оракул времени:
время судна в порту → Ɉ
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from enum import Enum
import hashlib


class VesselStatus(Enum):
    """Статус судна по AIS."""
    UNDERWAY = 0          # В пути
    AT_ANCHOR = 1         # На якоре
    NOT_UNDER_COMMAND = 2  # Без управления
    MOORED = 5            # Пришвартовано
    AGROUND = 6           # На мели


class OracleSource(Enum):
    """Источники данных AIS."""
    MARINE_TRAFFIC = "marinetraffic.com"
    VESSEL_FINDER = "vesselfinder.com"
    FLEET_MON = "fleetmon.com"
    SPIRE = "spire.com"
    KPLER = "kpler.com"
    AIS_HUB = "aishub.net"  # Открытая сеть


@dataclass
class AISMessage:
    """Сообщение AIS от судна."""
    mmsi: str               # Maritime Mobile Service Identity (9 цифр)
    imo: str                # IMO номер судна
    name: str               # Название судна
    latitude: float         # Широта
    longitude: float        # Долгота
    speed: float            # Скорость (узлы)
    course: float           # Курс (градусы)
    status: VesselStatus    # Статус
    timestamp: str          # Время получения
    source: OracleSource    # Источник данных

    def to_hash(self) -> str:
        """Hash сообщения для верификации."""
        data = f"{self.mmsi}:{self.timestamp}:{self.latitude}:{self.longitude}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class PortStay:
    """Пребывание судна в порту."""
    vessel_mmsi: str
    vessel_name: str
    port_name: str
    arrival: str            # ISO timestamp
    departure: Optional[str] = None  # None = ещё в порту
    messages: List[str] = field(default_factory=list)  # Hashes AIS сообщений

    @property
    def duration_seconds(self) -> int:
        """Длительность пребывания в секундах."""
        arr = datetime.fromisoformat(self.arrival.replace('Z', '+00:00'))

        if self.departure:
            dep = datetime.fromisoformat(self.departure.replace('Z', '+00:00'))
        else:
            dep = datetime.now(timezone.utc)

        return int((dep - arr).total_seconds())

    @property
    def juno_earned(self) -> Decimal:
        """Заработанные Ɉ за присутствие."""
        # 1 секунда = 1 Ɉ (при текущем halving)
        return Decimal(self.duration_seconds)


class AISOracle:
    """
    Децентрализованный оракул морских данных.

    Книга Монтана:
    > "#Сованаглобус может быть децентрализованным оракулом АПИ:
    > Маринтрафик и остальных VesselFinder, FleetMon, Spire, Kpler, AISHub."
    """

    # VHF частоты AIS (международные)
    AIS_FREQUENCIES = {
        "AIS1": "161.975 MHz",  # Channel 87B
        "AIS2": "162.025 MHz",  # Channel 88B
    }

    def __init__(self):
        self.sources: Dict[OracleSource, bool] = {s: False for s in OracleSource}
        self.messages: List[AISMessage] = []
        self.port_stays: Dict[str, PortStay] = {}  # key = mmsi:port

    def register_source(self, source: OracleSource) -> None:
        """Зарегистрировать источник данных."""
        self.sources[source] = True

    def receive_ais(self, message: AISMessage) -> str:
        """
        Получить AIS сообщение.

        Args:
            message: AIS сообщение

        Returns:
            Hash сообщения
        """
        msg_hash = message.to_hash()
        self.messages.append(message)

        # Если судно пришвартовано — начать отсчёт времени
        if message.status == VesselStatus.MOORED:
            self._track_port_stay(message)

        return msg_hash

    def _track_port_stay(self, message: AISMessage) -> None:
        """Отслеживать пребывание в порту."""
        # Определить порт по координатам (упрощённо)
        port = self._detect_port(message.latitude, message.longitude)
        if not port:
            return

        key = f"{message.mmsi}:{port}"

        if key not in self.port_stays:
            # Новое прибытие
            self.port_stays[key] = PortStay(
                vessel_mmsi=message.mmsi,
                vessel_name=message.name,
                port_name=port,
                arrival=message.timestamp
            )

        # Добавить сообщение как доказательство
        self.port_stays[key].messages.append(message.to_hash())

    def _detect_port(self, lat: float, lon: float) -> Optional[str]:
        """Определить порт по координатам (упрощённо)."""
        # Основные порты мира (примерные координаты)
        PORTS = {
            "Rotterdam": (51.9, 4.5),
            "Singapore": (1.3, 103.8),
            "Shanghai": (31.2, 121.5),
            "Dubai": (25.0, 55.0),
            "Los Angeles": (33.7, -118.3),
        }

        for port_name, (port_lat, port_lon) in PORTS.items():
            # Простая проверка близости (0.5 градуса)
            if abs(lat - port_lat) < 0.5 and abs(lon - port_lon) < 0.5:
                return port_name

        return None

    def finalize_port_stay(self, mmsi: str, port: str, departure: str) -> PortStay:
        """
        Завершить пребывание в порту.

        Args:
            mmsi: MMSI судна
            port: Название порта
            departure: Время отхода

        Returns:
            Завершённый PortStay
        """
        key = f"{mmsi}:{port}"

        if key not in self.port_stays:
            raise ValueError(f"Port stay not found: {key}")

        self.port_stays[key].departure = departure
        return self.port_stays[key]

    def get_oracle_status(self) -> Dict:
        """Статус оракула."""
        active_sources = [s.value for s, active in self.sources.items() if active]

        return {
            "active_sources": active_sources,
            "total_sources": len(OracleSource),
            "messages_received": len(self.messages),
            "active_port_stays": len([p for p in self.port_stays.values() if not p.departure]),
            "completed_port_stays": len([p for p in self.port_stays.values() if p.departure]),
            "ais_frequencies": self.AIS_FREQUENCIES,
            "protocol": "Decentralized oracle for maritime time"
        }

    def calculate_total_juno(self) -> Decimal:
        """Суммарные Ɉ за все пребывания."""
        total = Decimal("0")
        for stay in self.port_stays.values():
            total += stay.juno_earned
        return total


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    oracle = AISOracle()

    print("=" * 60)
    print("AIS ORACLE — Децентрализованный оракул времени")
    print("=" * 60)
    print("\n'Они построили трубу. Мы пускаем по ней время.'")

    # Регистрируем источники
    oracle.register_source(OracleSource.MARINE_TRAFFIC)
    oracle.register_source(OracleSource.VESSEL_FINDER)
    oracle.register_source(OracleSource.AIS_HUB)

    print("\n--- ИСТОЧНИКИ ДАННЫХ ---")
    for source in OracleSource:
        status = "АКТИВЕН" if oracle.sources[source] else "—"
        print(f"  {source.value}: {status}")

    # Симуляция: судно прибыло в Rotterdam
    print("\n--- СИМУЛЯЦИЯ: Судно в Rotterdam ---")

    msg = AISMessage(
        mmsi="244123456",
        imo="9123456",
        name="BALTIC TRADER",
        latitude=51.9,
        longitude=4.5,
        speed=0.0,
        course=0.0,
        status=VesselStatus.MOORED,
        timestamp="2026-01-30T10:00:00+00:00",
        source=OracleSource.MARINE_TRAFFIC
    )

    msg_hash = oracle.receive_ais(msg)
    print(f"AIS получен: {msg.name}")
    print(f"Порт: Rotterdam")
    print(f"Статус: ПРИШВАРТОВАНО")
    print(f"Hash: {msg_hash[:16]}...")

    # Симуляция: прошло 2 дня, судно уходит
    stay = oracle.finalize_port_stay(
        mmsi="244123456",
        port="Rotterdam",
        departure="2026-02-01T10:00:00+00:00"
    )

    print(f"\n--- РЕЗУЛЬТАТ ПРЕБЫВАНИЯ ---")
    print(f"Судно: {stay.vessel_name}")
    print(f"Порт: {stay.port_name}")
    print(f"Прибытие: {stay.arrival}")
    print(f"Отход: {stay.departure}")
    print(f"Длительность: {stay.duration_seconds:,} секунд")
    print(f"Заработано: {stay.juno_earned:,} Ɉ")

    print("\n--- ЧАСТОТЫ AIS ---")
    for name, freq in oracle.AIS_FREQUENCIES.items():
        print(f"  {name}: {freq}")

    print("\n" + "=" * 60)
    print("'MarineTraffic + Montana = время → Ɉ'")
    print("=" * 60)
