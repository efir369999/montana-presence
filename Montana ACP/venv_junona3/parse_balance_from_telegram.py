#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для парсинга исторических балансов из Telegram канала.
Использует авторизацию пользователя для получения сообщений из канала.
Извлекает дату публикации и поле "Текущий баланс" или "Total Balance".
"""

import os
import re
import csv
from datetime import datetime, timezone
from dotenv import load_dotenv
from telethon.sync import TelegramClient
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Загружаем переменные окружения
load_dotenv()

# Telegram API credentials (получите на https://my.telegram.org)
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')

# Номер телефона для авторизации (в международном формате, например: +79991234567)
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')

# ID канала для парсинга
CHANNEL_ID = -1002316863309

# Файл для сохранения результатов (простой CSV с 2 колонками)
OUTPUT_FILE = "parsed_balances_simple.csv"


def parse_balance_from_message(message_text):
    """
    Парсит текст сообщения и извлекает текущий баланс.

    Ищет паттерны:
    - "Текущий баланс: 12345.67$"
    - "🔹 Текущий баланс: 12,345.67$"
    - "Total Balance: 12345.67$"

    Returns:
        float or None: Баланс или None если не найден
    """
    if not message_text:
        return None

    # Паттерны для поиска баланса
    patterns = [
        r'Текущий баланс:\s*\*?\s*([\d,]+\.?\d*)\$',  # "Текущий баланс: 12345.67$"
        r'🔹\s*Текущий баланс:\s*\*?\s*([\d,]+\.?\d*)\$',  # "🔹 Текущий баланс: 12345.67$"
        r'Total Balance:\s*\*?\s*([\d,]+\.?\d*)\$',  # "Total Balance: 12345.67$"
    ]

    for pattern in patterns:
        match = re.search(pattern, message_text)
        if match:
            balance_str = match.group(1).replace(',', '')  # Убираем запятые из чисел
            try:
                balance = float(balance_str)
                return balance
            except ValueError:
                continue

    return None


def fetch_balances_from_telegram(client, channel_id, limit=1000):
    """
    Получает сообщения из Telegram канала через пользовательский аккаунт и извлекает балансы.

    Args:
        client: TelegramClient (авторизован как пользователь)
        channel_id: ID канала
        limit: Максимальное количество сообщений для обработки

    Returns:
        list: Список словарей с датой и балансом
    """
    balances = []

    try:
        # Получаем сообщения из канала
        logging.info(f"Получение сообщений из канала {channel_id}...")
        messages = client.get_messages(channel_id, limit=limit)

        logging.info(f"Найдено {len(messages)} сообщений. Начинаем парсинг...")

        for message in messages:
            if not message or not message.text:
                continue

            # Парсим баланс из текста
            balance = parse_balance_from_message(message.text)

            if balance is not None:
                # Получаем дату публикации (конвертируем в UTC)
                message_date = message.date
                if message_date.tzinfo is None:
                    message_date = message_date.replace(tzinfo=timezone.utc)
                else:
                    message_date = message_date.astimezone(timezone.utc)

                balances.append({
                    'date': message_date,
                    'balance': balance,
                    'message_id': message.id
                })

                logging.info(f"✅ Найден баланс: {balance:.2f}$ на {message_date.strftime('%Y-%m-%d %H:%M:%S')}")

        logging.info(f"Всего найдено балансов: {len(balances)}")

    except Exception as e:
        logging.error(f"Ошибка при получении сообщений: {e}", exc_info=True)

    return balances


def save_balances_to_simple_csv(balances, output_file=OUTPUT_FILE):
    """
    Сохраняет распарсенные балансы в простой CSV с двумя колонками: дата и баланс.

    Args:
        balances: Список словарей с датой и балансом
        output_file: Путь к выходному файлу
    """
    # Сортируем по дате (от старых к новым)
    balances_sorted = sorted(balances, key=lambda x: x['date'])

    # Группируем по дням (берем последний баланс за каждый день)
    daily_balances = {}
    for item in balances_sorted:
        date_only = item['date'].date()
        # Берем последнее сообщение за день
        if date_only not in daily_balances or item['date'] > daily_balances[date_only]['date']:
            daily_balances[date_only] = item

    # Создаем записи для CSV
    csv_entries = []
    for _, item in sorted(daily_balances.items()):
        entry = {
            "Date": item['date'].strftime('%Y-%m-%d'),
            "Balance": round(item['balance'], 2)
        }
        csv_entries.append(entry)

    # Сохраняем в CSV
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Date", "Balance"])
        writer.writeheader()
        writer.writerows(csv_entries)

    logging.info(f"✅ Сохранено {len(csv_entries)} ежедневных балансов в {output_file}")

    # Показываем превью первых 5 записей
    if csv_entries:
        logging.info("\n📊 Превью данных (первые 5 записей):")
        for entry in csv_entries[:5]:
            logging.info(f"   {entry['Date']}: {entry['Balance']:.2f}$")
        if len(csv_entries) > 5:
            logging.info(f"   ... и еще {len(csv_entries) - 5} записей")


def main():
    """
    Основная функция скрипта.
    """
    # Проверяем наличие API credentials
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logging.error("❌ Не указаны TELEGRAM_API_ID и TELEGRAM_API_HASH в .env файле.")
        logging.info("\n📝 Как получить API credentials (займет 2 минуты):")
        logging.info("   1. Откройте https://my.telegram.org")
        logging.info("   2. Войдите с вашим номером телефона")
        logging.info("   3. Перейдите в 'API Development Tools'")
        logging.info("   4. Создайте приложение (любое название)")
        logging.info("   5. Скопируйте API ID и API Hash")
        logging.info("\n   Добавьте в .env файл:")
        logging.info("   TELEGRAM_API_ID=ваш_api_id")
        logging.info("   TELEGRAM_API_HASH=ваш_api_hash")
        logging.info("   TELEGRAM_PHONE=+ваш_номер_телефона")
        return

    if not TELEGRAM_PHONE:
        logging.error("❌ Не указан TELEGRAM_PHONE в .env файле.")
        logging.info("💡 Добавьте номер телефона в .env: TELEGRAM_PHONE=+79991234567")
        return

    try:
        # Создаем клиент Telegram с авторизацией пользователя
        logging.info("🔌 Подключение к Telegram как пользователь...")

        # Используем API ID/Hash + номер телефона пользователя
        with TelegramClient('user_session', int(TELEGRAM_API_ID), TELEGRAM_API_HASH) as client:
            # Авторизуемся с номером телефона
            client.start(phone=TELEGRAM_PHONE)
            logging.info("✅ Успешно авторизованы в Telegram")

            # Проверяем информацию о пользователе
            me = client.get_me()
            logging.info(f"👤 Пользователь: @{me.username if me.username else 'без username'} ({me.first_name})")

            # Получаем балансы из канала
            balances = fetch_balances_from_telegram(client, CHANNEL_ID, limit=1000)

            if not balances:
                logging.warning("⚠️ Балансы не найдены в сообщениях канала.")
                logging.info("💡 Убедитесь, что:")
                logging.info("   1. Вы являетесь участником канала")
                logging.info("   2. ID канала указан правильно: -1002316863309")
                logging.info("   3. В сообщениях канала есть паттерны 'Текущий баланс' или 'Total Balance'")
                return

            # Сохраняем в простой CSV (только дата и баланс)
            save_balances_to_simple_csv(balances, OUTPUT_FILE)

            logging.info(f"\n🎉 Парсинг завершен успешно!")
            logging.info(f"📁 Результаты сохранены в: {OUTPUT_FILE}")

    except Exception as e:
        logging.error(f"❌ Ошибка при выполнении скрипта: {e}", exc_info=True)


if __name__ == '__main__':
    print("=" * 70)
    print("📊 Парсер балансов из Telegram канала")
    print("=" * 70)
    print()

    main()
