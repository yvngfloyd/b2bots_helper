from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    bot_token: str
    owner_chat_id: int
    site_url: str
    tg_channel_url: str
    cover_file_id: str | None
    project_url: str | None
    telegram_secret_token: str | None
    admin_setup_key: str | None


    @property
    def webhook_url(self) -> str | None:
        if not self.project_url:
            return None
        return self.project_url.rstrip("/") + "/api/webhook"



def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


settings = Settings(
    bot_token=_require("BOT_TOKEN"),
    owner_chat_id=int(_require("OWNER_CHAT_ID")),
    site_url=os.getenv("SITE_URL", "https://example.com").strip() or "https://example.com",
    tg_channel_url=os.getenv("TG_CHANNEL_URL", "https://t.me/example").strip() or "https://t.me/example",
    cover_file_id=os.getenv("COVER_FILE_ID", "").strip() or None,
    project_url=os.getenv("PROJECT_URL", "").strip() or None,
    telegram_secret_token=os.getenv("TELEGRAM_SECRET_TOKEN", "").strip() or None,
    admin_setup_key=os.getenv("ADMIN_SETUP_KEY", "").strip() or None,
)
