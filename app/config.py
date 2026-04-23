import os
from dataclasses import dataclass


@dataclass
class Settings:
    bot_token: str
    owner_chat_id: int
    site_url: str
    tg_channel_url: str
    cover_file_id: str = ""


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


settings = Settings(
    bot_token=_get_required_env("BOT_TOKEN"),
    owner_chat_id=int(_get_required_env("OWNER_CHAT_ID")),
    site_url=os.getenv("SITE_URL", "").strip() or "https://example.com",
    tg_channel_url=os.getenv("TG_CHANNEL_URL", "").strip() or "https://t.me/example",
    cover_file_id=os.getenv("COVER_FILE_ID", "").strip(),
)
