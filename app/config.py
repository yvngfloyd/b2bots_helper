import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    bot_token: str
    owner_chat_id: int
    site_url: str
    tg_channel_url: str
    subscription_channel_id: str = ""
    cover_file_id: str = ""
    database_path: str = "bot_data.sqlite3"
    first_reminder_hours: int = 1
    reminder_repeat_days: int = 3
    reminder_check_seconds: int = 300


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
    subscription_channel_id=os.getenv("SUBSCRIPTION_CHANNEL_ID", "").strip(),
    cover_file_id=os.getenv("COVER_FILE_ID", "").strip(),
    database_path=os.getenv("DATABASE_PATH", "").strip() or "bot_data.sqlite3",
    first_reminder_hours=int(os.getenv("FIRST_REMINDER_HOURS", "1")),
    reminder_repeat_days=int(os.getenv("REMINDER_REPEAT_DAYS", "3")),
    reminder_check_seconds=int(os.getenv("REMINDER_CHECK_SECONDS", "300")),
)
