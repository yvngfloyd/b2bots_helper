from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    bot_token: str
    owner_chat_id: int
    site_url: str
    tg_channel_url: str
    support_username: str
    cover_file_id: str | None
    bot_title: str



def get_settings() -> Settings:
    bot_token = os.getenv('BOT_TOKEN', '').strip()
    owner_chat_id_raw = os.getenv('OWNER_CHAT_ID', '').strip()
    site_url = os.getenv('SITE_URL', 'https://example.com').strip()
    tg_channel_url = os.getenv('TG_CHANNEL_URL', 'https://t.me/example').strip()
    support_username = os.getenv('SUPPORT_USERNAME', '@b2bots').strip()
    cover_file_id = os.getenv('COVER_FILE_ID', '').strip() or None
    bot_title = os.getenv('BOT_TITLE', 'B2Bots Helper').strip()

    if not bot_token:
        raise ValueError('BOT_TOKEN is not set')
    if not owner_chat_id_raw:
        raise ValueError('OWNER_CHAT_ID is not set')

    try:
        owner_chat_id = int(owner_chat_id_raw)
    except ValueError as exc:
        raise ValueError('OWNER_CHAT_ID must be an integer') from exc

    return Settings(
        bot_token=bot_token,
        owner_chat_id=owner_chat_id,
        site_url=site_url,
        tg_channel_url=tg_channel_url,
        support_username=support_username,
        cover_file_id=cover_file_id,
        bot_title=bot_title,
    )
