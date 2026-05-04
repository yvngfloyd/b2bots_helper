from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}
PRIVATE_TME_PATHS = {"joinchat", "c"}


class SubscriptionCheckStatus(str, Enum):
    SUBSCRIBED = "subscribed"
    NOT_SUBSCRIBED = "not_subscribed"
    CHECK_FAILED = "check_failed"


@dataclass(frozen=True)
class SubscriptionCheckResult:
    status: SubscriptionCheckStatus
    member_status: str = ""
    error: str = ""


def resolve_subscription_chat_id(explicit_channel_id: str, channel_url: str) -> str | None:
    explicit = explicit_channel_id.strip()
    if explicit:
        return parse_channel_id_from_url(explicit) or normalize_channel_id(explicit)
    return parse_channel_id_from_url(channel_url)


def normalize_channel_id(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("@") or cleaned.lstrip("-").isdigit():
        return cleaned
    if "/" not in cleaned and "." not in cleaned:
        return f"@{cleaned}"
    return cleaned


def parse_channel_id_from_url(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith("@") or cleaned.lstrip("-").isdigit():
        return cleaned
    if cleaned.startswith("t.me/") or cleaned.startswith("telegram.me/"):
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    host = parsed.netloc.lower().removeprefix("www.")
    if host not in {"t.me", "telegram.me"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    first_part = parts[0]
    if first_part in PRIVATE_TME_PATHS or first_part.startswith("+"):
        return None

    return f"@{first_part}"


def is_subscribed_status(status: Any) -> bool:
    value = getattr(status, "value", status)
    return str(value) in SUBSCRIBED_STATUSES


async def is_user_subscribed(bot: Any, user_id: int, chat_id: str) -> bool:
    result = await check_user_subscription(bot, user_id, chat_id)
    return result.status == SubscriptionCheckStatus.SUBSCRIBED


async def check_user_subscription(bot: Any, user_id: int, chat_id: str) -> SubscriptionCheckResult:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except Exception as error:
        logger.exception("Failed to check subscription for user_id=%s chat_id=%s", user_id, chat_id)
        return SubscriptionCheckResult(
            status=SubscriptionCheckStatus.CHECK_FAILED,
            error=str(error),
        )

    member_status = getattr(member.status, "value", member.status)
    if is_subscribed_status(member.status):
        return SubscriptionCheckResult(
            status=SubscriptionCheckStatus.SUBSCRIBED,
            member_status=str(member_status),
        )
    return SubscriptionCheckResult(
        status=SubscriptionCheckStatus.NOT_SUBSCRIBED,
        member_status=str(member_status),
    )
