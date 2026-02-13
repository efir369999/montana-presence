#!/usr/bin/env python3
"""
Montana Protocol — Ascending Auction System
Аукцион нарастания для всех сервисов Montana.

Модель ценообразования:
- 1-й сервис: 1 Ɉ
- 2-й сервис: 2 Ɉ
- 3-й сервис: 3 Ɉ
- N-й сервис: N Ɉ (шаг 1 Ɉ)

Применяется к:
- Domains (alice@montana.network)
- VPN subscriptions
- Всем будущим сервисам
"""

import json
import threading
import fcntl
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import logging

log = logging.getLogger("montana_auction")

# ═══════════════════════════════════════════════════════════════════════════════
#                            AUCTION SERVICE TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ServiceType:
    """Типы сервисов Montana Protocol"""
    # Базовые сервисы
    DOMAIN = "domain"              # alice@montana.network
    VPN = "vpn"                    # WireGuard VPN subscription
    STORAGE = "storage"            # Future: distributed storage
    COMPUTE = "compute"            # Future: compute credits

    # Телефония и коммуникации
    PHONE_NUMBER = "phone_number"  # Виртуальный номер +montana-123456
    AUDIO_SECOND = "audio_second"  # Цена 1 секунды аудио звонка
    VIDEO_SECOND = "video_second"  # Цена 1 секунды видео звонка

    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.DOMAIN,
            cls.VPN,
            cls.STORAGE,
            cls.COMPUTE,
            cls.PHONE_NUMBER,
            cls.AUDIO_SECOND,
            cls.VIDEO_SECOND
        ]

    @classmethod
    def communication_services(cls) -> List[str]:
        """Коммуникационные сервисы (телефония, звонки)"""
        return [cls.PHONE_NUMBER, cls.AUDIO_SECOND, cls.VIDEO_SECOND]


# ═══════════════════════════════════════════════════════════════════════════════
#                            AUCTION COUNTER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

class AuctionRegistry:
    """
    Реестр счетчиков аукциона для каждого типа сервиса.
    Консенсус между 3 узлами Montana Network.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.auction_file = self.data_dir / "auction_counters.json"
        self.purchases_file = self.data_dir / "auction_purchases.json"
        self._lock = threading.Lock()
        self._ensure_files()

    def _ensure_files(self):
        """Создать файлы аукциона если не существуют"""
        if not self.auction_file.exists():
            self._save_counters({service: 0 for service in ServiceType.all()})
        if not self.purchases_file.exists():
            self._save_purchases([])

    def _load_counters(self) -> Dict[str, int]:
        """Загрузить счетчики аукциона (thread-safe)"""
        with open(self.auction_file, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data

    def _save_counters(self, counters: Dict[str, int]):
        """Сохранить счетчики аукциона (thread-safe)"""
        with open(self.auction_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(counters, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _load_purchases(self) -> List[Dict]:
        """Загрузить историю покупок"""
        with open(self.purchases_file, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data

    def _save_purchases(self, purchases: List[Dict]):
        """Сохранить историю покупок"""
        with open(self.purchases_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(purchases, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_current_price(self, service_type: str) -> int:
        """
        Получить текущую цену для следующей покупки.

        Args:
            service_type: Тип сервиса (domain, vpn, etc.)

        Returns:
            Цена в Ɉ (монетах времени)
        """
        if service_type not in ServiceType.all():
            raise ValueError(f"Unknown service type: {service_type}")

        with self._lock:
            counters = self._load_counters()
            count = counters.get(service_type, 0)
            # Следующая цена = текущий счетчик + 1
            return count + 1

    def get_total_sold(self, service_type: str) -> int:
        """
        Получить количество проданных сервисов.

        Args:
            service_type: Тип сервиса

        Returns:
            Количество проданных сервисов
        """
        if service_type not in ServiceType.all():
            raise ValueError(f"Unknown service type: {service_type}")

        with self._lock:
            counters = self._load_counters()
            return counters.get(service_type, 0)

    def purchase(
        self,
        service_type: str,
        buyer_address: str,
        service_id: str,
        amount_paid: int
    ) -> Dict:
        """
        Зарегистрировать покупку сервиса.

        Args:
            service_type: Тип сервиса (domain, vpn, etc.)
            buyer_address: Montana адрес покупателя
            service_id: Идентификатор сервиса (например, "alice" для alice@montana.network)
            amount_paid: Сумма оплаченная в Ɉ

        Returns:
            Dict с результатом покупки

        Raises:
            ValueError: Если цена не совпадает или недостаточно монет
        """
        if service_type not in ServiceType.all():
            raise ValueError(f"Unknown service type: {service_type}")

        with self._lock:
            counters = self._load_counters()
            current_count = counters.get(service_type, 0)
            expected_price = current_count + 1

            if amount_paid < expected_price:
                raise ValueError(
                    f"Insufficient payment: {amount_paid} Ɉ, expected {expected_price} Ɉ"
                )

            # Инкремент счетчика
            counters[service_type] = current_count + 1
            self._save_counters(counters)

            # Записать в историю покупок
            purchases = self._load_purchases()
            purchase = {
                "service_type": service_type,
                "service_id": service_id,
                "buyer_address": buyer_address,
                "price_paid": amount_paid,
                "purchase_number": current_count + 1,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            purchases.append(purchase)
            self._save_purchases(purchases)

            log.info(
                f"Auction purchase: {service_type} #{current_count + 1} "
                f"'{service_id}' by {buyer_address[:10]}... for {amount_paid} Ɉ"
            )

            return {
                "success": True,
                "service_type": service_type,
                "service_id": service_id,
                "price_paid": amount_paid,
                "purchase_number": current_count + 1,
                "next_price": current_count + 2
            }

    def get_purchase_history(
        self,
        service_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить историю покупок.

        Args:
            service_type: Фильтр по типу сервиса (None = все)
            limit: Максимум записей

        Returns:
            Список покупок (последние первыми)
        """
        with self._lock:
            purchases = self._load_purchases()

            if service_type:
                purchases = [p for p in purchases if p.get("service_type") == service_type]

            # Последние первыми
            purchases.reverse()
            return purchases[:limit]

    def get_stats(self) -> Dict:
        """
        Получить статистику аукциона по всем сервисам.

        Returns:
            Dict со статистикой
        """
        with self._lock:
            counters = self._load_counters()
            purchases = self._load_purchases()

            total_revenue = sum(p.get("price_paid", 0) for p in purchases)

            stats = {
                "total_services_sold": sum(counters.values()),
                "total_revenue": total_revenue,
                "services": {}
            }

            for service_type in ServiceType.all():
                count = counters.get(service_type, 0)
                next_price = count + 1
                service_purchases = [p for p in purchases if p.get("service_type") == service_type]
                revenue = sum(p.get("price_paid", 0) for p in service_purchases)

                stats["services"][service_type] = {
                    "total_sold": count,
                    "next_price": next_price,
                    "revenue": revenue,
                    "latest_purchase": service_purchases[-1] if service_purchases else None
                }

            return stats


# ═══════════════════════════════════════════════════════════════════════════════
#                            GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_auction_registry: Optional[AuctionRegistry] = None

def get_auction_registry(data_dir: Path = None) -> AuctionRegistry:
    """Получить глобальный экземпляр AuctionRegistry (singleton)"""
    global _auction_registry
    if _auction_registry is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _auction_registry = AuctionRegistry(data_dir)
    return _auction_registry


# ═══════════════════════════════════════════════════════════════════════════════
#                            DOMAIN SERVICE (Montana Name Service)
# ═══════════════════════════════════════════════════════════════════════════════

class DomainService:
    """
    Montana Name Service (MNS) — доменный слой поверх Montana Protocol.

    Домены вида: alice@montana.network → mt1234...5678
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.domains_file = self.data_dir / "domains.json"
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        """Создать файл доменов если не существует"""
        if not self.domains_file.exists():
            self._save_domains({})

    def _load_domains(self) -> Dict[str, Dict]:
        """Загрузить реестр доменов"""
        with open(self.domains_file, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data

    def _save_domains(self, domains: Dict[str, Dict]):
        """Сохранить реестр доменов"""
        with open(self.domains_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(domains, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def is_available(self, domain: str) -> bool:
        """Проверить доступность домена"""
        with self._lock:
            domains = self._load_domains()
            return domain.lower() not in domains

    def register(
        self,
        domain: str,
        owner_address: str,
        price_paid: int
    ) -> Dict:
        """
        Зарегистрировать домен через аукцион.

        Args:
            domain: Имя домена (например, "alice")
            owner_address: Montana адрес владельца
            price_paid: Цена оплаченная в Ɉ

        Returns:
            Dict с результатом регистрации
        """
        domain = domain.lower()

        # Валидация домена
        if not self._validate_domain(domain):
            raise ValueError(f"Invalid domain name: {domain}")

        with self._lock:
            domains = self._load_domains()

            if domain in domains:
                raise ValueError(f"Domain already registered: {domain}@montana.network")

            # Регистрация через аукцион
            auction = get_auction_registry(self.data_dir.parent / "data")
            result = auction.purchase(
                service_type=ServiceType.DOMAIN,
                buyer_address=owner_address,
                service_id=domain,
                amount_paid=price_paid
            )

            # Сохранить в реестре доменов
            domains[domain] = {
                "owner": owner_address,
                "registered": datetime.utcnow().isoformat() + "Z",
                "purchase_number": result["purchase_number"],
                "price_paid": price_paid
            }
            self._save_domains(domains)

            log.info(f"Domain registered: {domain}@montana.network → {owner_address[:10]}...")

            return {
                "success": True,
                "domain": f"{domain}@montana.network",
                "owner": owner_address,
                "price_paid": price_paid,
                "purchase_number": result["purchase_number"]
            }

    def lookup(self, domain: str) -> Optional[Dict]:
        """
        Найти владельца домена.

        Args:
            domain: Имя домена (alice или alice@montana.network)

        Returns:
            Dict с информацией о домене или None
        """
        # Убрать @montana.network если есть
        domain = domain.lower().replace("@montana.network", "")

        with self._lock:
            domains = self._load_domains()
            if domain in domains:
                info = domains[domain].copy()
                info["domain"] = f"{domain}@montana.network"
                return info
            return None

    def _validate_domain(self, domain: str) -> bool:
        """
        Валидация имени домена.

        Правила:
        - 3-32 символа
        - Только a-z, 0-9, дефис
        - Не начинается и не заканчивается дефисом
        """
        if not domain:
            return False
        if len(domain) < 3 or len(domain) > 32:
            return False
        if not domain[0].isalnum() or not domain[-1].isalnum():
            return False
        if not all(c.isalnum() or c == '-' for c in domain):
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#                            GLOBAL DOMAIN SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

_domain_service: Optional[DomainService] = None

def get_domain_service(data_dir: Path = None) -> DomainService:
    """Получить глобальный экземпляр DomainService (singleton)"""
    global _domain_service
    if _domain_service is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _domain_service = DomainService(data_dir)
    return _domain_service


# ═══════════════════════════════════════════════════════════════════════════════
#                      PHONE SERVICE — Virtual Phone Numbers
# ═══════════════════════════════════════════════════════════════════════════════

class PhoneService:
    """
    Montana Phone Service — виртуальные телефонные номера для аудио/видео звонков.

    Формат номера: +montana-NNNNNN (где N = sequential number)
    Пример: +montana-000001, +montana-000042

    Возможности:
    - P2P аудио звонки (WebRTC)
    - P2P видео звонки (WebRTC)
    - Оплата за секунды через аукцион
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.phone_file = self.data_dir / "phone_numbers.json"
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        """Создать файл номеров если не существует"""
        if not self.phone_file.exists():
            self._save_numbers({})

    def _load_numbers(self) -> Dict[str, Dict]:
        """Загрузить реестр номеров"""
        with open(self.phone_file, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data

    def _save_numbers(self, numbers: Dict[str, Dict]):
        """Сохранить реестр номеров"""
        with open(self.phone_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(numbers, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def format_number(self, number: int) -> str:
        """Форматировать номер: 42 → +montana-000042"""
        return f"+montana-{number:06d}"

    def is_available(self, number: int) -> bool:
        """Проверить доступность номера"""
        with self._lock:
            numbers = self._load_numbers()
            key = self.format_number(number)
            return key not in numbers

    def register(
        self,
        number: int,
        owner_address: str,
        price_paid: int
    ) -> Dict:
        """
        Зарегистрировать виртуальный номер через аукцион.

        Args:
            number: Номер (например, 42 для +montana-000042)
            owner_address: Montana адрес владельца
            price_paid: Цена оплаченная в Ɉ

        Returns:
            Dict с результатом регистрации
        """
        formatted = self.format_number(number)

        with self._lock:
            numbers = self._load_numbers()

            if formatted in numbers:
                raise ValueError(f"Phone number already registered: {formatted}")

            # Регистрация через аукцион
            auction = get_auction_registry(self.data_dir.parent / "data")
            result = auction.purchase(
                service_type=ServiceType.PHONE_NUMBER,
                buyer_address=owner_address,
                service_id=formatted,
                amount_paid=price_paid
            )

            # Сохранить в реестре номеров
            numbers[formatted] = {
                "owner": owner_address,
                "number": number,
                "registered": datetime.utcnow().isoformat() + "Z",
                "purchase_number": result["purchase_number"],
                "price_paid": price_paid,
                "audio_seconds_used": 0,
                "video_seconds_used": 0
            }
            self._save_numbers(numbers)

            log.info(f"Phone number registered: {formatted} → {owner_address[:10]}...")

            return {
                "success": True,
                "phone_number": formatted,
                "owner": owner_address,
                "price_paid": price_paid,
                "purchase_number": result["purchase_number"]
            }

    def lookup(self, number: int) -> Optional[Dict]:
        """
        Найти владельца номера.

        Args:
            number: Номер (42 или "+montana-000042")

        Returns:
            Dict с информацией о номере или None
        """
        # Поддержка обоих форматов
        if isinstance(number, str) and number.startswith("+montana-"):
            formatted = number
        else:
            formatted = self.format_number(int(number))

        with self._lock:
            numbers = self._load_numbers()
            if formatted in numbers:
                return numbers[formatted].copy()
            return None

    def record_call(
        self,
        phone_number: str,
        call_type: str,
        duration_seconds: int,
        price_per_second: int
    ) -> Dict:
        """
        Записать использование звонка.

        Args:
            phone_number: Номер телефона
            call_type: "audio" или "video"
            duration_seconds: Длительность в секундах
            price_per_second: Цена за секунду в Ɉ

        Returns:
            Dict с информацией о звонке
        """
        total_cost = duration_seconds * price_per_second

        with self._lock:
            numbers = self._load_numbers()

            if phone_number not in numbers:
                raise ValueError(f"Phone number not found: {phone_number}")

            if call_type == "audio":
                numbers[phone_number]["audio_seconds_used"] += duration_seconds
            elif call_type == "video":
                numbers[phone_number]["video_seconds_used"] += duration_seconds
            else:
                raise ValueError(f"Invalid call type: {call_type}")

            self._save_numbers(numbers)

            log.info(
                f"Call recorded: {phone_number} {call_type} {duration_seconds}s "
                f"({total_cost} Ɉ)"
            )

            return {
                "phone_number": phone_number,
                "call_type": call_type,
                "duration_seconds": duration_seconds,
                "price_per_second": price_per_second,
                "total_cost": total_cost
            }


# ═══════════════════════════════════════════════════════════════════════════════
#                            GLOBAL PHONE SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

_phone_service: Optional[PhoneService] = None

def get_phone_service(data_dir: Path = None) -> PhoneService:
    """Получить глобальный экземпляр PhoneService (singleton)"""
    global _phone_service
    if _phone_service is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _phone_service = PhoneService(data_dir)
    return _phone_service


# ═══════════════════════════════════════════════════════════════════════════════
#                      CALL PRICING — Audio & Video Second Pricing
# ═══════════════════════════════════════════════════════════════════════════════

class CallPricingService:
    """
    Аукционная модель цены за секунду аудио/видео звонков.

    Принцип: N-я секунда всех звонков стоит N Ɉ
    - 1-я секунда аудио в истории Montana = 1 Ɉ
    - 2-я секунда аудио = 2 Ɉ
    - N-я секунда аудио = N Ɉ

    Аналогично для видео (отдельный счетчик).
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.auction = get_auction_registry(data_dir)

    def get_current_audio_price(self) -> int:
        """Получить текущую цену за 1 секунду аудио"""
        return self.auction.get_current_price(ServiceType.AUDIO_SECOND)

    def get_current_video_price(self) -> int:
        """Получить текущую цену за 1 секунду видео"""
        return self.auction.get_current_price(ServiceType.VIDEO_SECOND)

    def calculate_audio_call_cost(self, duration_seconds: int) -> int:
        """
        Рассчитать стоимость аудио звонка.

        Args:
            duration_seconds: Длительность звонка в секундах

        Returns:
            Общая стоимость в Ɉ
        """
        base_price = self.get_current_audio_price()
        # Формула: сумма арифметической прогрессии
        # cost = base_price + (base_price+1) + ... + (base_price+duration-1)
        # = duration * base_price + (0+1+2+...+(duration-1))
        # = duration * base_price + duration*(duration-1)/2
        cost = duration_seconds * base_price + (duration_seconds * (duration_seconds - 1)) // 2
        return cost

    def calculate_video_call_cost(self, duration_seconds: int) -> int:
        """
        Рассчитать стоимость видео звонка.

        Args:
            duration_seconds: Длительность звонка в секундах

        Returns:
            Общая стоимость в Ɉ
        """
        base_price = self.get_current_video_price()
        cost = duration_seconds * base_price + (duration_seconds * (duration_seconds - 1)) // 2
        return cost

    def register_audio_seconds(self, seconds: int, caller_address: str) -> Dict:
        """
        Зарегистрировать использование N секунд аудио.

        Args:
            seconds: Количество секунд
            caller_address: Montana адрес звонящего

        Returns:
            Dict с результатом регистрации
        """
        total_cost = self.calculate_audio_call_cost(seconds)

        # Зарегистрировать каждую секунду в аукционе
        for i in range(seconds):
            current_price = self.auction.get_current_price(ServiceType.AUDIO_SECOND)
            self.auction.purchase(
                service_type=ServiceType.AUDIO_SECOND,
                buyer_address=caller_address,
                service_id=f"audio_{self.auction.get_total_sold(ServiceType.AUDIO_SECOND) + 1}",
                amount_paid=current_price
            )

        return {
            "service_type": "audio",
            "seconds": seconds,
            "total_cost": total_cost,
            "caller": caller_address
        }

    def register_video_seconds(self, seconds: int, caller_address: str) -> Dict:
        """
        Зарегистрировать использование N секунд видео.

        Args:
            seconds: Количество секунд
            caller_address: Montana адрес звонящего

        Returns:
            Dict с результатом регистрации
        """
        total_cost = self.calculate_video_call_cost(seconds)

        # Зарегистрировать каждую секунду в аукционе
        for i in range(seconds):
            current_price = self.auction.get_current_price(ServiceType.VIDEO_SECOND)
            self.auction.purchase(
                service_type=ServiceType.VIDEO_SECOND,
                buyer_address=caller_address,
                service_id=f"video_{self.auction.get_total_sold(ServiceType.VIDEO_SECOND) + 1}",
                amount_paid=current_price
            )

        return {
            "service_type": "video",
            "seconds": seconds,
            "total_cost": total_cost,
            "caller": caller_address
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                            GLOBAL CALL PRICING SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

_call_pricing_service: Optional[CallPricingService] = None

def get_call_pricing_service(data_dir: Path = None) -> CallPricingService:
    """Получить глобальный экземпляр CallPricingService (singleton)"""
    global _call_pricing_service
    if _call_pricing_service is None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        _call_pricing_service = CallPricingService(data_dir)
    return _call_pricing_service
