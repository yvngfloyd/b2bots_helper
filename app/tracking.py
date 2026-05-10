from __future__ import annotations

import logging
from typing import Any

from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.storage import upsert_user_from_telegram

logger = logging.getLogger(__name__)


def track_user_safely(event_user: Any, *, message_text: str | None = None, source: str | None = None) -> None:
    if event_user is None:
        return
    try:
        upsert_user_from_telegram(
            settings.database_path,
            event_user,
            message_text=message_text,
            source=source,
        )
    except Exception:
        logger.exception("Failed to track Telegram user user_id=%s", getattr(event_user, "id", "unknown"))


async def track_message_user(message: Message, *, source: str | None = None) -> None:
    track_user_safely(
        message.from_user,
        message_text=message.text,
        source=source,
    )


async def track_callback_user(callback: CallbackQuery, *, source: str | None = None) -> None:
    track_user_safely(
        callback.from_user,
        message_text=callback.data,
        source=source,
    )
