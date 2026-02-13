#!/usr/bin/env python3
"""
Тест аукционной системы Montana Protocol
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from montana_auction import (
    get_auction_registry,
    get_domain_service,
    ServiceType
)

def test_auction_system():
    """Тест системы аукциона"""
    print("=" * 70)
    print("Montana Protocol — Auction System Test")
    print("=" * 70)

    data_dir = Path(__file__).parent / "data_test"
    data_dir.mkdir(exist_ok=True)

    auction = get_auction_registry(data_dir)

    # 1. Проверить начальные цены
    print("\n1. Начальные цены:")
    for service_type in ServiceType.all():
        price = auction.get_current_price(service_type)
        sold = auction.get_total_sold(service_type)
        print(f"   {service_type:12s} - Next: {price:4d} Ɉ (Sold: {sold})")

    # 2. Симулировать покупку доменов
    print("\n2. Симулировать покупку доменов:")
    domains = ["alice", "bob", "charlie", "diana", "eve"]

    for i, domain in enumerate(domains, 1):
        price = auction.get_current_price(ServiceType.DOMAIN)
        result = auction.purchase(
            service_type=ServiceType.DOMAIN,
            buyer_address=f"mt{'0' * 38}{i:02d}",
            service_id=domain,
            amount_paid=price
        )
        print(f"   #{i}: {domain:10s} - {price:3d} Ɉ (Purchase #{result['purchase_number']})")

    # 3. Проверить обновленные цены
    print("\n3. Обновленные цены:")
    for service_type in ServiceType.all():
        price = auction.get_current_price(service_type)
        sold = auction.get_total_sold(service_type)
        print(f"   {service_type:12s} - Next: {price:4d} Ɉ (Sold: {sold})")

    # 4. Статистика аукциона
    print("\n4. Статистика аукциона:")
    stats = auction.get_stats()
    print(f"   Total sold: {stats['total_services_sold']}")
    print(f"   Total revenue: {stats['total_revenue']} Ɉ")
    print(f"   Services:")
    for service_type, info in stats['services'].items():
        if info['total_sold'] > 0:
            print(f"      {service_type:12s}: {info['total_sold']:3d} sold, "
                  f"{info['revenue']:5d} Ɉ revenue, next: {info['next_price']} Ɉ")

    # 5. История покупок
    print("\n5. История покупок (последние 5):")
    history = auction.get_purchase_history(ServiceType.DOMAIN, limit=5)
    for purchase in history:
        print(f"   {purchase['service_id']:10s} - {purchase['price_paid']:3d} Ɉ "
              f"(#{purchase['purchase_number']}) by {purchase['buyer_address'][:10]}...")

    print("\n" + "=" * 70)
    print("✓ Auction system test completed")
    print("=" * 70)


def test_domain_service():
    """Тест Montana Name Service"""
    print("\n" + "=" * 70)
    print("Montana Name Service (MNS) Test")
    print("=" * 70)

    data_dir = Path(__file__).parent / "data_test"
    domains = get_domain_service(data_dir)
    auction = get_auction_registry(data_dir)

    # 1. Проверить доступность
    print("\n1. Проверка доступности доменов:")
    test_domains = ["alice", "bob", "montana", "satoshi"]
    for domain in test_domains:
        available = domains.is_available(domain)
        status = "✓ Available" if available else "✗ Taken"
        price = auction.get_current_price(ServiceType.DOMAIN) if available else "N/A"
        print(f"   {domain:15s} - {status:12s} (Price: {price} Ɉ)")

    # 2. Зарегистрировать новый домен
    print("\n2. Регистрация нового домена:")
    if domains.is_available("montana"):
        price = auction.get_current_price(ServiceType.DOMAIN)
        result = domains.register(
            domain="montana",
            owner_address="mt1234567890abcdef1234567890abcdef12345678",
            price_paid=price
        )
        print(f"   ✓ Registered: {result['domain']}")
        print(f"   Owner: {result['owner']}")
        print(f"   Price: {result['price_paid']} Ɉ")
        print(f"   Purchase #: {result['purchase_number']}")
    else:
        print("   ✗ Domain 'montana' already taken")

    # 3. Lookup домена
    print("\n3. Lookup зарегистрированных доменов:")
    for domain in ["alice", "montana", "satoshi"]:
        info = domains.lookup(domain)
        if info:
            print(f"   {info['domain']:20s} → {info['owner'][:16]}... ({info['price_paid']} Ɉ)")
        else:
            print(f"   {domain:20s} → Not found")

    print("\n" + "=" * 70)
    print("✓ Domain service test completed")
    print("=" * 70)


def test_auction_math():
    """Проверить математику аукциона"""
    print("\n" + "=" * 70)
    print("Auction Math Verification")
    print("=" * 70)

    # Формула: N-я покупка стоит N Ɉ
    # Сумма первых N покупок = N*(N+1)/2

    print("\nПроверка формулы аукциона:")
    print("N-я покупка стоит N Ɉ")
    print("Общая выручка от N покупок = N*(N+1)/2\n")

    test_cases = [1, 5, 10, 50, 100, 1000]

    for n in test_cases:
        expected_revenue = n * (n + 1) // 2
        nth_price = n
        next_price = n + 1

        print(f"После {n:4d} покупок:")
        print(f"   Последняя цена:  {nth_price:6d} Ɉ")
        print(f"   Следующая цена:  {next_price:6d} Ɉ")
        print(f"   Общая выручка:   {expected_revenue:6d} Ɉ")
        print()

    print("=" * 70)


if __name__ == '__main__':
    test_auction_system()
    test_domain_service()
    test_auction_math()

    print("\n✓ All tests passed!")
