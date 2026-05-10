from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.crm import load_crm_users, render_crm_html
from app.storage import (
    initialize_database,
    mark_completed,
    mark_reminder_sent,
    save_form_snapshot,
    upsert_started_user,
)


class CrmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.database_path = str(Path(self.tmpdir.name) / "bot.sqlite3")
        initialize_database(self.database_path)
        self.now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)

    def test_load_crm_users_returns_active_and_completed_users_with_answers(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)
        save_form_snapshot(
            self.database_path,
            101,
            current_step="budget",
            form_data={"business_type": "Услуги", "budget": "10-30"},
            now=self.now + timedelta(minutes=5),
        )
        mark_reminder_sent(self.database_path, 101, self.now + timedelta(hours=1))

        upsert_started_user(self.database_path, 202, "Bob", None, self.now + timedelta(minutes=1))
        mark_completed(
            self.database_path,
            202,
            self.now + timedelta(minutes=20),
            application_data={"business_type": "Продажи", "contact": "+79990000000"},
        )

        users = load_crm_users(self.database_path)

        self.assertEqual([user.user_id for user in users], [101, 202])
        self.assertEqual(users[0].status, "В процессе")
        self.assertEqual(users[0].answers["budget"], "10-30")
        self.assertEqual(users[0].reminder_count, 1)
        self.assertEqual(users[1].status, "Завершена")
        self.assertEqual(users[1].answers["contact"], "+79990000000")

    def test_render_crm_html_contains_table_and_escapes_user_data(self) -> None:
        upsert_started_user(self.database_path, 101, "<Alice>", "alice", self.now)
        users = load_crm_users(self.database_path)

        html = render_crm_html(users, self.database_path)

        self.assertIn("<table", html)
        self.assertIn("&lt;Alice&gt;", html)
        self.assertIn("Всего пользователей: 1", html)
        self.assertIn("bot.sqlite3", html)


if __name__ == "__main__":
    unittest.main()
