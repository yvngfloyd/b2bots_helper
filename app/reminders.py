from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.storage import get_due_reminders, mark_reminder_sent

logger = logging.getLogger(__name__)

REMINDER_MESSAGES = [
    (
        "Напоминаю про заявку на B2Bots Helper. "
        "Можно ответить на вопросы за пару минут, и мы подскажем подходящий сценарий бота."
    ),
    (
        "Вы начинали заявку, но не дошли до конца. "
        "Если автоматизация все еще актуальна, можно спокойно продолжить."
    ),
    (
        "Легкое напоминание: заявка по боту еще не завершена. "
        "Когда будет удобно, нажмите кнопку и продолжите."
    ),
]


async def reminder_worker(bot: Bot) -> None:
    first_delay = timedelta(hours=settings.first_reminder_hours)
    repeat_delay = timedelta(days=settings.reminder_repeat_days)

    while True:
        await send_due_reminders(bot, first_delay=first_delay, repeat_delay=repeat_delay)
        await asyncio.sleep(settings.reminder_check_seconds)


async def send_due_reminders(
    bot: Bot,
    *,
    first_delay: timedelta,
    repeat_delay: timedelta,
) -> None:
    users = get_due_reminders(
        settings.database_path,
        first_delay=first_delay,
        repeat_delay=repeat_delay,
    )

    for user in users:
        text = REMINDER_MESSAGES[user.reminder_count % len(REMINDER_MESSAGES)]
        try:
            await bot.send_message(
                chat_id=user.user_id,
                text=text,
                reply_markup=_reminder_keyboard().as_markup(),
            )
        except Exception:
            logger.exception("Failed to send reminder to user_id=%s", user.user_id)
            continue

        mark_reminder_sent(settings.database_path, user.user_id)


def _reminder_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="Заполнить заявку", callback_data="form:start")
    builder.adjust(1)
    return builder
