from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.storage import get_due_reminders, mark_reminder_sent

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "reminders"
REMINDER_IMAGE_PATHS = [
    ASSETS_DIR / "reminder_1.jpg",
    ASSETS_DIR / "reminder_2.jpg",
    ASSETS_DIR / "reminder_3.jpg",
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
        image_path = reminder_image_path(user.reminder_count)
        try:
            await bot.send_photo(
                chat_id=user.user_id,
                photo=FSInputFile(image_path),
                reply_markup=make_reminder_keyboard(user.reminder_count).as_markup(),
            )
        except Exception:
            logger.exception("Failed to send reminder to user_id=%s", user.user_id)
            continue

        mark_reminder_sent(settings.database_path, user.user_id)


def reminder_image_path(reminder_count: int) -> Path:
    return REMINDER_IMAGE_PATHS[reminder_count % len(REMINDER_IMAGE_PATHS)]


def make_reminder_keyboard(reminder_count: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    if reminder_count == 1:
        builder.button(text="Продолжить", callback_data="reminder:continue")
        builder.button(text="Заполнить заново", callback_data="form:restart")
    else:
        builder.button(text="Заполнить заявку", callback_data="form:start")

    builder.adjust(1)
    return builder
