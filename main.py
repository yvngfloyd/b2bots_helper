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
from crm_server import start_crm_server


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(router)

    initialize_database(settings.database_path)
    crm_server = None
    if settings.crm_enabled:
        crm_server = start_crm_server(
            settings.database_path,
            settings.crm_host,
            settings.crm_port,
            username=settings.crm_username,
            password=settings.crm_password,
            admin_token=settings.admin_token,
        )
        logging.info("CRM is running at http://%s:%s", settings.crm_host, settings.crm_port)

    reminders_task = asyncio.create_task(reminder_worker(bot))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        if crm_server is not None:
            crm_server.shutdown()
            crm_server.server_close()
        reminders_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminders_task


if __name__ == "__main__":
    asyncio.run(main())
