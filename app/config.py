from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import PurePosixPath

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    bot_token: str
    owner_chat_id: int
    site_url: str
    tg_channel_url: str
    require_subscription: bool = False
    subscription_channel_id: str = ""
    cover_file_id: str = ""
    database_path: str = "bot_data.sqlite3"
    first_reminder_hours: int = 1
    reminder_repeat_days: int = 3
    reminder_check_seconds: int = 300
    crm_enabled: bool = False
    crm_host: str = "127.0.0.1"
    crm_port: int = 8080
    crm_username: str = ""
    crm_password: str = ""
    admin_token: str = ""


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def resolve_crm_port(port_env: str | None, crm_port_env: str | None, default: int = 8080) -> int:
    value = (port_env or "").strip() or (crm_port_env or "").strip()
    if not value:
        return default
    return int(value)


def resolve_database_path(database_path_env: str | None, railway_volume_mount_path: str | None) -> str:
    explicit_path = (database_path_env or "").strip()
    volume_path = (railway_volume_mount_path or "").strip()
    if volume_path and explicit_path in {"", "bot_data.sqlite3", "./bot_data.sqlite3"}:
        return str(PurePosixPath(volume_path) / "bot_data.sqlite3")

    if explicit_path:
        return explicit_path

    return "bot_data.sqlite3"


settings = Settings(
    bot_token=_get_required_env("BOT_TOKEN"),
    owner_chat_id=int(_get_required_env("OWNER_CHAT_ID")),
    site_url=os.getenv("SITE_URL", "").strip() or "https://example.com",
    tg_channel_url=os.getenv("TG_CHANNEL_URL", "").strip() or "https://t.me/example",
    require_subscription=parse_bool(os.getenv("REQUIRE_SUBSCRIPTION"), default=False),
    subscription_channel_id=os.getenv("SUBSCRIPTION_CHANNEL_ID", "").strip(),
    cover_file_id=os.getenv("COVER_FILE_ID", "").strip(),
    database_path=resolve_database_path(
        os.getenv("DATABASE_PATH"),
        os.getenv("RAILWAY_VOLUME_MOUNT_PATH"),
    ),
    first_reminder_hours=int(os.getenv("FIRST_REMINDER_HOURS", "1")),
    reminder_repeat_days=int(os.getenv("REMINDER_REPEAT_DAYS", "3")),
    reminder_check_seconds=int(os.getenv("REMINDER_CHECK_SECONDS", "300")),
    crm_enabled=parse_bool(os.getenv("CRM_ENABLED"), default=False),
    crm_host=os.getenv("CRM_HOST", "").strip() or "127.0.0.1",
    crm_port=resolve_crm_port(os.getenv("PORT"), os.getenv("CRM_PORT")),
    crm_username=os.getenv("CRM_USERNAME", "").strip(),
    crm_password=os.getenv("CRM_PASSWORD", "").strip(),
    admin_token=os.getenv("ADMIN_TOKEN", "").strip(),
)
