"""
Интеграция Proof of Presence в Telegram бота Юноны
Добавь этот код в junomontanaagibot.py
"""

# В начале файла добавить:
from proof_of_presence import ProofOfPresenceManager
from telegram.ext import Application, CommandHandler

# Создать PoP manager
pop_manager = ProofOfPresenceManager(
    base_interval_minutes=40,  # Базовый интервал 40 минут
    randomness_minutes=10       # ±10 минут (30-50 минут)
)


# ═══════════════════════════════════════════════════════════════════════════════
#                              КОМАНДЫ ДЛЯ PROOF OF PRESENCE
# ═══════════════════════════════════════════════════════════════════════════════

async def verify_presence_cmd(update, context):
    """
    /verify_presence <check_id> - Подтвердить присутствие через Face ID

    Юнона запрашивает это случайно каждые ~40 минут
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    # Регистрация если новый пользователь
    if not pop_manager.get_user_status(user_id):
        pop_manager.register_user(user_id, username)

    # Проверить аргументы
    if not context.args:
        # Показать статус
        status = pop_manager.get_user_status(user_id)
        pending = pop_manager.get_pending_checks(user_id)

        message = (
            "🏔 **Proof of Presence Status**\n\n"
            f"✅ Завершено: {status['checks_completed']}\n"
            f"❌ Провалено: {status['checks_failed']}\n"
            f"⏰ Следующая проверка: `{status['next_check']}`\n\n"
        )

        if pending:
            message += f"⚠️ **Ожидает подтверждения:** {len(pending)}\n"
            for check in pending:
                message += f"   `/verify_presence {check['check_id']}`\n"
        else:
            message += "✅ Нет ожидающих проверок"

        await update.message.reply_text(message, parse_mode="Markdown")
        return

    # Верифицировать check
    check_id = context.args[0]

    # Проверка Face ID / Touch ID (mock)
    verified = pop_manager.verify_check(user_id, check_id)

    if verified:
        status = pop_manager.get_user_status(user_id)
        next_check = status['next_check']

        await update.message.reply_text(
            "✅ **Присутствие подтверждено**\n\n"
            "📱 Face ID / Touch ID верифицирован\n"
            f"⏰ Следующая проверка: `{next_check}`\n\n"
            "Юнона Montana благодарит за подтверждение присутствия.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ **Верификация не удалась**\n\n"
            "Возможные причины:\n"
            "• Проверка истекла (5 минут)\n"
            "• Неверный check_id\n"
            "• Биометрия не зарегистрирована\n\n"
            "Попробуй снова или обратись к администратору."
        )


async def pop_status_cmd(update, context):
    """
    /pop_status - Статус Proof of Presence
    """
    user_id = update.effective_user.id

    status = pop_manager.get_user_status(user_id)

    if not status:
        await update.message.reply_text(
            "⚠️ Ты не зарегистрирован в Proof of Presence.\n"
            "Используй /verify_presence для регистрации."
        )
        return

    pending = pop_manager.get_pending_checks(user_id)

    message = (
        "🏔 **Montana Proof of Presence**\n\n"
        f"👤 Пользователь: `{status['username']}`\n"
        f"📊 Статус: `{status['status']}`\n\n"
        f"✅ Завершено: {status['checks_completed']}\n"
        f"❌ Провалено: {status['checks_failed']}\n"
        f"📅 Последняя: `{status['last_check'] or 'Нет'}`\n"
        f"⏰ Следующая: `{status['next_check']}`\n\n"
    )

    if pending:
        message += f"⚠️ **Ожидает подтверждения:** {len(pending)}\n\n"
        for check in pending:
            message += f"ID: `{check['check_id']}`\n"
            message += f"Истекает: `{check['expires_at']}`\n"
            message += f"Команда: `/verify_presence {check['check_id']}`\n\n"
    else:
        message += "✅ Нет ожидающих проверок"

    await update.message.reply_text(message, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════════
#                              BACKGROUND TASK
# ═══════════════════════════════════════════════════════════════════════════════

async def pop_notify_user(telegram_id: int, message: str):
    """
    Callback для отправки уведомлений пользователям

    Вызывается из background_checker когда нужна проверка
    """
    try:
        # Получить bot instance из application
        from telegram import Bot
        bot = Bot(token=TELEGRAM_TOKEN)  # Твой токен

        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error sending PoP notification to {telegram_id}: {e}")


async def start_pop_background_task(application: Application):
    """
    Запустить background task для автоматических проверок

    Добавь в main():
        application.job_queue.run_once(start_pop_background_task, when=1)
    """
    import asyncio

    # Создать background task
    task = asyncio.create_task(
        pop_manager.background_checker(pop_notify_user)
    )

    print("✅ Proof of Presence background checker started")


# ═══════════════════════════════════════════════════════════════════════════════
#                              РЕГИСТРАЦИЯ HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

"""
В main() добавь:

# Proof of Presence commands
application.add_handler(CommandHandler("verify_presence", verify_presence_cmd))
application.add_handler(CommandHandler("pop_status", pop_status_cmd))

# Background task
application.job_queue.run_once(
    lambda context: start_pop_background_task(context.application),
    when=1
)
"""


# ═══════════════════════════════════════════════════════════════════════════════
#                              ПРИМЕР ПОЛНОЙ ИНТЕГРАЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

async def example_main():
    """
    Пример как интегрировать в существующий бот
    """
    from telegram.ext import Application

    # Создать application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавить handlers
    application.add_handler(CommandHandler("verify_presence", verify_presence_cmd))
    application.add_handler(CommandHandler("pop_status", pop_status_cmd))

    # Запустить background task
    async def start_background(context):
        import asyncio
        asyncio.create_task(
            pop_manager.background_checker(
                lambda tid, msg: context.application.bot.send_message(tid, msg, parse_mode="Markdown")
            )
        )

    application.job_queue.run_once(start_background, when=1)

    # Запустить бота
    await application.run_polling()


if __name__ == "__main__":
    import asyncio
    from telegram.ext import Application
    import os

    # Для теста
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_JUNONA", "YOUR_TOKEN")

    print("🏔 Montana Proof of Presence Integration")
    print("="*60)
    print("Команды:")
    print("  /verify_presence <check_id> - Подтвердить присутствие")
    print("  /pop_status                 - Статус проверок")
    print("="*60)
    print("\nBackground task будет запрашивать проверки каждые ~40 минут")
    print("(случайный интервал 30-50 минут)")
    print("="*60)

    # asyncio.run(example_main())  # Раскомментируй для запуска
