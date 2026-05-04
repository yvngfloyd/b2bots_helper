from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.handlers import resolve_application_user


class ApplicationUserTests(unittest.TestCase):
    def test_callback_user_overrides_bot_message_author(self) -> None:
        bot_user = SimpleNamespace(id=999, username="bot", full_name="Helper Bot")
        human_user = SimpleNamespace(id=101, username="alice", full_name="Alice")
        message = SimpleNamespace(from_user=bot_user)

        self.assertIs(resolve_application_user(message, human_user), human_user)

    def test_message_user_is_used_when_no_callback_user_exists(self) -> None:
        human_user = SimpleNamespace(id=101, username="alice", full_name="Alice")
        message = SimpleNamespace(from_user=human_user)

        self.assertIs(resolve_application_user(message), human_user)


if __name__ == "__main__":
    unittest.main()
