from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.handlers import (
    QUESTIONS,
    build_start_owner_notification,
    process_choice,
    process_contact_method,
    resolve_application_user,
)
from app.keyboards import contact_methods
from app.states import LeadForm


class FakeFormState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.state = None

    async def update_data(self, **kwargs: object) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict[str, object]:
        return self.data

    async def set_state(self, state: object) -> None:
        self.state = state


class FakeMessage:
    photo = None
    from_user = None

    def __init__(self) -> None:
        self.edited_text = ""
        self.reply_markup = None

    async def edit_text(self, text: str, reply_markup: object | None = None) -> None:
        self.edited_text = text
        self.reply_markup = reply_markup

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.edited_text = text
        self.reply_markup = reply_markup


class LeadFormQuestionTests(unittest.IsolatedAsyncioTestCase):
    def test_budget_question_asks_whether_user_is_ready_to_allocate_budget(self) -> None:
        budget_question = next(question for question in QUESTIONS if question["key"] == "budget")

        self.assertEqual(budget_question["question"], "7/8. Готовы ли выделить бюджет?")
        self.assertEqual(budget_question["options"], ["Да", "Нет"])

    def test_contact_method_has_only_username_and_other_contact(self) -> None:
        self.assertEqual(contact_methods, ["Оставить свой user", "Написать другой контакт"])

    async def test_budget_choice_goes_directly_to_contact_without_text_question(self) -> None:
        state = FakeFormState()
        message = FakeMessage()
        callback = SimpleNamespace(
            data="budget:1",
            from_user=SimpleNamespace(id=101, username="alice"),
            message=message,
            answer=AsyncMock(),
        )

        with patch("app.handlers.track_callback_user", new=AsyncMock()), patch(
            "app.handlers.save_current_form_snapshot",
            new=AsyncMock(),
        ):
            await process_choice(callback, state)

        self.assertIs(state.state, LeadForm.contact_method)
        self.assertEqual(state.data["budget"], "Да")
        self.assertEqual(message.edited_text, "8/8. Как удобно с вами связаться?")

    async def test_missing_username_prompts_for_manual_contact(self) -> None:
        state = FakeFormState()
        message = FakeMessage()
        callback = SimpleNamespace(
            data="contact_method:1",
            from_user=SimpleNamespace(id=101, username=None),
            message=message,
            answer=AsyncMock(),
        )

        with patch("app.handlers.track_callback_user", new=AsyncMock()), patch(
            "app.handlers.save_current_form_snapshot",
            new=AsyncMock(),
        ), patch("app.handlers.finalize_application", new=AsyncMock()) as finalize:
            await process_contact_method(callback, state)

        self.assertIs(state.state, LeadForm.manual_contact)
        self.assertIn("не указан username", message.edited_text)
        finalize.assert_not_awaited()

    async def test_existing_username_finalizes_application(self) -> None:
        state = FakeFormState()
        message = FakeMessage()
        callback = SimpleNamespace(
            data="contact_method:1",
            from_user=SimpleNamespace(id=101, username="alice"),
            message=message,
            answer=AsyncMock(),
        )

        with patch("app.handlers.track_callback_user", new=AsyncMock()), patch(
            "app.handlers.finalize_application",
            new=AsyncMock(),
        ) as finalize:
            await process_contact_method(callback, state)

        finalize.assert_awaited_once()
        self.assertEqual(finalize.await_args.args[2], "@alice")


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

    def test_start_notification_includes_database_diagnostics(self) -> None:
        user = SimpleNamespace(id=101, username=None, full_name="Alice")

        text = build_start_owner_notification(user, database_path="bot_data.sqlite3", users_count=2)

        self.assertIn("User ID:</b> <code>101</code>", text)
        self.assertIn("Username:</b> не указан", text)
        self.assertIn("CRM users:</b> <code>2</code>", text)
        self.assertIn("DB:</b> <code>bot_data.sqlite3</code>", text)


if __name__ == "__main__":
    unittest.main()
