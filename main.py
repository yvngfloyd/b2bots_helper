import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.handlers import router
from app.reminders import reminder_worker
from app.storage import initialize_database


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(router)

    initialize_database(settings.database_path)
    reminders_task = asyncio.create_task(reminder_worker(bot))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        reminders_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminders_task


if __name__ == "__main__":
    asyncio.run(main())
