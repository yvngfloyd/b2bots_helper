from __future__ import annotations

import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.keyboards import subscription_required_keyboard
from app.subscription import (
    SubscriptionCheckStatus,
    check_user_subscription,
    is_subscribed_status,
    resolve_subscription_chat_id,
)


class SubscriptionGateTests(unittest.TestCase):
    def test_public_tme_link_resolves_to_channel_username(self) -> None:
        self.assertEqual(resolve_subscription_chat_id("", "https://t.me/b2bots"), "@b2bots")
        self.assertEqual(resolve_subscription_chat_id("", "https://t.me/b2bots/"), "@b2bots")
        self.assertEqual(resolve_subscription_chat_id("", "https://telegram.me/b2bots"), "@b2bots")

    def test_explicit_subscription_channel_id_wins(self) -> None:
        self.assertEqual(resolve_subscription_chat_id("@b2bots_private", "https://t.me/b2bots"), "@b2bots_private")
        self.assertEqual(resolve_subscription_chat_id("-1001234567890", "https://t.me/b2bots"), "-1001234567890")
        self.assertEqual(resolve_subscription_chat_id("https://t.me/b2bots_private", "https://t.me/b2bots"), "@b2bots_private")

    def test_private_invite_links_cannot_be_used_for_membership_check(self) -> None:
        self.assertIsNone(resolve_subscription_chat_id("", "https://t.me/+abcdef"))
        self.assertIsNone(resolve_subscription_chat_id("", "https://t.me/joinchat/abcdef"))

    def test_subscription_statuses_match_telegram_membership(self) -> None:
        self.assertTrue(is_subscribed_status("member"))
        self.assertTrue(is_subscribed_status("administrator"))
        self.assertTrue(is_subscribed_status("creator"))
        self.assertFalse(is_subscribed_status("left"))
        self.assertFalse(is_subscribed_status("kicked"))

    def test_subscription_keyboard_has_channel_and_check_buttons(self) -> None:
        keyboard = subscription_required_keyboard("https://t.me/b2bots", "subscription:check:start")
        rows = keyboard.inline_keyboard

        self.assertEqual(rows[0][0].text, "Подписаться на канал")
        self.assertEqual(rows[0][0].url, "https://t.me/b2bots")
        self.assertEqual(rows[1][0].text, "Проверить подписку")
        self.assertEqual(rows[1][0].callback_data, "subscription:check:start")


class SubscriptionCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_member_status_returns_subscribed(self) -> None:
        result = await check_user_subscription(FakeBot("member"), 101, "@b2bots")

        self.assertEqual(result.status, SubscriptionCheckStatus.SUBSCRIBED)
        self.assertEqual(result.member_status, "member")

    async def test_left_status_returns_not_subscribed(self) -> None:
        result = await check_user_subscription(FakeBot("left"), 101, "@b2bots")

        self.assertEqual(result.status, SubscriptionCheckStatus.NOT_SUBSCRIBED)
        self.assertEqual(result.member_status, "left")

    async def test_api_error_returns_check_failed_not_not_subscribed(self) -> None:
        with self.assertLogs("app.subscription", level="ERROR"):
            result = await check_user_subscription(FailingBot(RuntimeError("chat not found")), 101, "@b2bots")

        self.assertEqual(result.status, SubscriptionCheckStatus.CHECK_FAILED)
        self.assertIn("chat not found", result.error)


class FakeMember:
    def __init__(self, status: str) -> None:
        self.status = status


class FakeBot:
    def __init__(self, status: str) -> None:
        self.status = status

    async def get_chat_member(self, chat_id: str, user_id: int) -> FakeMember:
        return FakeMember(self.status)


class FailingBot:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def get_chat_member(self, chat_id: str, user_id: int) -> FakeMember:
        raise self.error


if __name__ == "__main__":
    unittest.main()
