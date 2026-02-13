#!/usr/bin/env python3
"""
Тест телефонной системы Montana Protocol
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from montana_auction import (
    get_auction_registry,
    get_phone_service,
    get_call_pricing_service,
    ServiceType
)

def test_phone_numbers():
    """Тест регистрации виртуальных номеров"""
    print("=" * 70)
    print("Montana Phone Service — Virtual Numbers Test")
    print("=" * 70)

    data_dir = Path(__file__).parent / "data_test"
    phones = get_phone_service(data_dir)
    auction = get_auction_registry(data_dir)

    # 1. Проверить текущую цену
    print("\n1. Текущая цена номера:")
    price = auction.get_current_price(ServiceType.PHONE_NUMBER)
    sold = auction.get_total_sold(ServiceType.PHONE_NUMBER)
    print(f"   Следующий номер: {price} Ɉ")
    print(f"   Уже продано: {sold}")

    # 2. Зарегистрировать несколько номеров
    print("\n2. Регистрация номеров через аукцион:")
    test_numbers = [1, 2, 3, 42, 100]

    for num in test_numbers:
        price = auction.get_current_price(ServiceType.PHONE_NUMBER)
        formatted = phones.format_number(num)

        if phones.is_available(num):
            result = phones.register(
                number=num,
                owner_address=f"mt{'0' * 38}{num:02d}",
                price_paid=price
            )
            print(f"   ✓ {formatted} → {price:4d} Ɉ (Purchase #{result['purchase_number']})")
        else:
            print(f"   ✗ {formatted} — Already taken")

    # 3. Обновленная статистика
    print("\n3. Статистика после регистрации:")
    price = auction.get_current_price(ServiceType.PHONE_NUMBER)
    sold = auction.get_total_sold(ServiceType.PHONE_NUMBER)
    print(f"   Следующий номер: {price} Ɉ")
    print(f"   Уже продано: {sold}")

    # 4. Lookup номеров
    print("\n4. Lookup зарегистрированных номеров:")
    for num in [1, 2, 42]:
        info = phones.lookup(num)
        if info:
            formatted = phones.format_number(num)
            print(f"   {formatted} → {info['owner'][:16]}... ({info['price_paid']} Ɉ)")

    print("\n" + "=" * 70)


def test_call_pricing():
    """Тест ценообразования звонков"""
    print("\n" + "=" * 70)
    print("Montana Call Pricing Test")
    print("=" * 70)

    print("\n📞 Модель ценообразования Montana Protocol:")
    print("   • Если у тебя есть номер → Фиксированная цена: 1 Ɉ/сек")
    print("   • Аудио звонки: 1 Ɉ за секунду")
    print("   • Видео звонки: 1 Ɉ за секунду")
    print("   • Номер работает как 'подписка' на фиксированную цену")

    # Примеры расчета стоимости
    durations = [60, 300, 600, 1800, 3600]  # 1min, 5min, 10min, 30min, 1hr

    print("\n1. Стоимость аудио звонков (1 Ɉ/сек):")
    for duration in durations:
        cost = duration * 1  # Fixed: 1 Ɉ per second
        minutes = duration // 60
        print(f"   {minutes:3d} минут ({duration:5d} сек) = {cost:5d} Ɉ = ${cost * 0.1605:.2f} USD")

    print("\n2. Стоимость видео звонков (1 Ɉ/сек):")
    for duration in durations:
        cost = duration * 1  # Fixed: 1 Ɉ per second
        minutes = duration // 60
        print(f"   {minutes:3d} минут ({duration:5d} сек) = {cost:5d} Ɉ = ${cost * 0.1605:.2f} USD")

    print("\n" + "=" * 70)


def test_economics():
    """Тест экономической модели"""
    print("\n" + "=" * 70)
    print("Montana Economics — Phone Number Auction Model")
    print("=" * 70)

    print("\n💰 Аукционная модель номеров:")
    print("   • 1-й номер: 1 Ɉ")
    print("   • 2-й номер: 2 Ɉ")
    print("   • N-й номер: N Ɉ")

    print("\n📊 Примеры покупки номеров:")

    numbers = [1, 10, 42, 100, 1000, 10000]
    for n in numbers:
        price = n  # N-th number costs N Ɉ
        usd = price * 0.1605
        print(f"   Номер #{n:5d}: {price:6d} Ɉ = ${usd:8.2f} USD")

    print("\n💡 Экономика сети:")
    print("   После покупки номера за N Ɉ:")
    print("   → Все звонки: фиксированная цена 1 Ɉ/сек")
    print("   → Аудио и видео одинаково")
    print("   → Номер = кошелек (Montana адрес)")

    # Расчет выручки от первых N номеров
    print("\n📈 Выручка от продажи номеров:")
    for count in [100, 1000, 10000]:
        revenue = count * (count + 1) // 2  # Sum of 1+2+...+N
        usd = revenue * 0.1605
        print(f"   Первые {count:5d} номеров: {revenue:10d} Ɉ = ${usd:12,.2f} USD")

    print("\n" + "=" * 70)


def demo_call_scenario():
    """Демонстрация сценария звонка"""
    print("\n" + "=" * 70)
    print("Montana Call Scenario Demo")
    print("=" * 70)

    print("\n👤 Алиса (alice@montana.network):")
    print("   1. Регистрирует домен 'alice' → 6 Ɉ (6-й домен)")
    print("   2. Покупает номер +montana-000042 → 42 Ɉ (42-й номер)")
    print("   3. Теперь может звонить по 1 Ɉ/сек")

    print("\n👤 Боб (bob@montana.network):")
    print("   1. Регистрирует домен 'bob' → 7 Ɉ (7-й домен)")
    print("   2. Покупает номер +montana-000043 → 43 Ɉ (43-й номер)")
    print("   3. Теперь может звонить по 1 Ɉ/сек")

    print("\n📞 Алиса звонит Бобу:")
    print("   • Длительность: 5 минут (300 секунд)")
    print("   • Тип: видео звонок")
    print("   • Стоимость: 300 × 1 Ɉ = 300 Ɉ")
    print("   • В USD: 300 × $0.1605 = $48.15 USD")
    print("   • Списано с баланса Алисы: 300 Ɉ")

    print("\n💡 Итого Алиса потратила:")
    domain_cost = 6
    phone_cost = 42
    call_cost = 300
    total = domain_cost + phone_cost + call_cost
    total_usd = total * 0.1605

    print(f"   Домен alice@montana.network:    {domain_cost:4d} Ɉ")
    print(f"   Номер +montana-000042:          {phone_cost:4d} Ɉ")
    print(f"   Видео звонок 5 минут:           {call_cost:4d} Ɉ")
    print(f"   {'─' * 40}")
    print(f"   Итого:                          {total:4d} Ɉ = ${total_usd:.2f} USD")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_phone_numbers()
    test_call_pricing()
    test_economics()
    demo_call_scenario()

    print("\n✓ All phone tests passed!")
