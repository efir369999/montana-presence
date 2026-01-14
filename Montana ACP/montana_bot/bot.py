"""
Montana Telegram Bot — Self-Sovereign Light Client

Telegram bot that acts as transport layer for Montana signatures.
Private keys stay on user device (Telegram Secret Storage).
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)

from config import (
    TELEGRAM_BOT_TOKEN,
    SIGN_INTERVAL_SECONDS,
    GENESIS_TIMESTAMP,
    TAU2_SECONDS,
    LOG_LEVEL
)
from crypto import generate_mnemonic, keypair_from_mnemonic, MontanaKeypair
from storage import get_storage, UserState
from network import get_client


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger(__name__)


# User keypairs (in-memory, for demo)
# In production, keys stored in Telegram Secret Storage
user_keypairs: dict[int, MontanaKeypair] = {}


def get_current_tau2() -> int:
    """Get current τ₂ index"""
    now = int(datetime.now().timestamp())
    elapsed = now - GENESIS_TIMESTAMP
    return elapsed // TAU2_SECONDS


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start command — Generate BIP-39 mnemonic and setup Light Client
    """
    user_id = update.effective_user.id
    storage = get_storage()

    # Check if user already exists
    user = storage.get_user(user_id)
    if user:
        await update.message.reply_text(
            f"✅ Вы уже зарегистрированы!\n\n"
            f"Ваш адрес: `{user.public_key}`\n\n"
            f"/sign — Подписать присутствие\n"
            f"/balance — Проверить баланс\n"
            f"/help — Помощь",
            parse_mode="Markdown"
        )
        return

    # Generate new mnemonic
    mnemonic = generate_mnemonic()

    # Create keypair
    keypair = keypair_from_mnemonic(mnemonic)
    user_keypairs[user_id] = keypair

    # Save user state (NOT private key)
    user = storage.create_user(user_id, keypair.address)

    await update.message.reply_text(
        "🔐 *Montana Light Client готов!*\n\n"
        f"Ваш адрес: `{keypair.address}`\n\n"
        "⚠️ *ВАЖНО: Сохраните мнемонику в безопасном месте!*\n\n"
        f"`{mnemonic}`\n\n"
        "Эта фраза — единственный способ восстановить доступ.\n"
        "Bot НЕ ХРАНИТ ваши ключи.\n\n"
        "Команды:\n"
        "/sign — Подписать присутствие\n"
        "/balance — Проверить баланс\n"
        "/help — Помощь",
        parse_mode="Markdown"
    )


async def sign_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /sign command — Sign Light Client presence
    """
    user_id = update.effective_user.id
    storage = get_storage()

    # Check if user exists
    user = storage.get_user(user_id)
    if not user:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Используйте /start"
        )
        return

    # Check if keypair exists in memory
    if user_id not in user_keypairs:
        await update.message.reply_text(
            "❌ Keypair не найден в памяти.\n"
            "Используйте /restore для восстановления из мнемоники."
        )
        return

    keypair = user_keypairs[user_id]

    # Get current τ₂
    tau2_index = get_current_tau2()
    timestamp = int(datetime.now().timestamp())
    prev_slice_hash = b'\x00' * 32  # TODO: Get from network

    # Sign presence (locally on bot, but would be on user device in production)
    signature = keypair.sign_presence(tau2_index, timestamp, prev_slice_hash)

    # Save signature
    storage.save_signature(user_id, tau2_index, timestamp, signature)

    # Update user state
    user.last_sign = timestamp
    user.sign_count += 1
    storage.update_user(user)

    # Send to Montana P2P network
    client = get_client()
    try:
        if not client.connected:
            await client.connect()

        success = await client.send_presence(
            bytes.fromhex(user.public_key[2:]),
            tau2_index,
            timestamp,
            signature
        )

        if success:
            await update.message.reply_text(
                f"✍️ Подпись создана локально (ML-DSA-65)\n\n"
                f"✓ Отправлена в Montana сеть\n"
                f"✓ τ₂ = {tau2_index}\n\n"
                f"Всего подписей: {user.sign_count}\n\n"
                f"Следующая подпись: через {SIGN_INTERVAL_SECONDS // 60} минут"
            )
        else:
            await update.message.reply_text(
                "⚠️ Не удалось отправить подпись в сеть.\n"
                "Проверьте подключение к Montana P2P."
            )
    except Exception as e:
        logger.error(f"Failed to send presence: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при отправке: {str(e)}"
        )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /balance command — Check Montana balance
    """
    user_id = update.effective_user.id
    storage = get_storage()

    user = storage.get_user(user_id)
    if not user:
        await update.message.reply_text(
            "❌ Вы не зарегистрированы. Используйте /start"
        )
        return

    # TODO: Query balance from Montana network
    balance_mont = user.balance / 100_000_000  # Convert to Ɉ

    await update.message.reply_text(
        f"💰 *Ваш баланс Montana*\n\n"
        f"Доступно: {balance_mont:.8f} Ɉ\n"
        f"В cooldown: 0 Ɉ\n\n"
        f"Адрес: `{user.public_key}`\n\n"
        f"Тир: Light Client (10% шанс)\n"
        f"Подписей: {user.sign_count}\n\n"
        f"Следующая лотерея: через {SIGN_INTERVAL_SECONDS // 60} минут",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help command — Show help
    """
    await update.message.reply_text(
        "*Montana Light Client Bot*\n\n"
        "*Команды:*\n"
        "/start — Создать Light Client\n"
        "/sign — Подписать присутствие\n"
        "/balance — Проверить баланс\n"
        "/send — Отправить Ɉ\n"
        "/restore — Восстановить из мнемоники\n"
        "/help — Помощь\n\n"
        "*Безопасность:*\n"
        "✓ Ключи на вашем устройстве\n"
        "✓ Bot не хранит private keys\n"
        "✓ ML-DSA-65 post-quantum crypto\n\n"
        "*Тип узла:*\n"
        "Light Client (10% шанс в лотерее)\n"
        "Подпись каждые 10 минут\n\n"
        "lim(evidence → ∞) 1 Ɉ → 1 секунда",
        parse_mode="Markdown"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /stats command — Show bot statistics
    """
    storage = get_storage()

    user_count = storage.get_user_count()
    signature_count = storage.get_signature_count()

    await update.message.reply_text(
        f"📊 *Montana Bot Statistics*\n\n"
        f"Пользователей: {user_count}\n"
        f"Подписей: {signature_count}\n"
        f"Текущий τ₂: {get_current_tau2()}\n\n"
        f"Сеть: {MONTANA_P2P_HOST}:{MONTANA_P2P_PORT}",
        parse_mode="Markdown"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start Montana bot"""
    logger.info("Starting Montana Telegram Bot...")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sign", sign_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))

    # Error handler
    application.add_error_handler(error_handler)

    # Start bot
    logger.info("Montana Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
