from __future__ import annotations

import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.keyboards import subscription_required_keyboard
from app.subscription import is_subscribed_status, resolve_subscription_chat_id


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


if __name__ == "__main__":
    unittest.main()
