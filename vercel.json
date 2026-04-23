from __future__ import annotations

from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.handlers import build_dispatcher

bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dp
    dp = await build_dispatcher()
    yield
    await bot.session.close()


app = FastAPI(title="B2Bots Helper API", lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "message": "B2Bots Helper webhook is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/setup-webhook")
async def setup_webhook(key: str):
    if settings.admin_setup_key and key != settings.admin_setup_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not settings.webhook_url:
        raise HTTPException(status_code=400, detail="PROJECT_URL is required to set webhook")

    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.telegram_secret_token,
        allowed_updates=dp.resolve_used_update_types() if dp else None,
        drop_pending_updates=True,
    )
    return {"ok": True, "webhook_url": settings.webhook_url}


@app.get("/delete-webhook")
async def delete_webhook(key: str):
    if settings.admin_setup_key and key != settings.admin_setup_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    await bot.delete_webhook(drop_pending_updates=False)
    return {"ok": True}


@app.get("/webhook-info")
async def webhook_info(key: str):
    if settings.admin_setup_key and key != settings.admin_setup_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    info = await bot.get_webhook_info()
    return info.model_dump()


@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.telegram_secret_token:
        if x_telegram_bot_api_secret_token != settings.telegram_secret_token:
            raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    update = Update.model_validate(data)

    if dp is None:
        raise HTTPException(status_code=500, detail="Dispatcher is not initialized")

    await dp.feed_update(bot=bot, update=update)
    return JSONResponse({"ok": True})
