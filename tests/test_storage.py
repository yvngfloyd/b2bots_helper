from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.storage import (
    get_due_reminders,
    initialize_database,
    mark_completed,
    mark_reminder_sent,
    upsert_started_user,
)


class StorageReminderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.database_path = str(Path(self.tmpdir.name) / "bot.sqlite3")
        initialize_database(self.database_path)
        self.now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)

    def test_started_user_is_due_after_first_delay(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)

        due = get_due_reminders(
            self.database_path,
            self.now + timedelta(hours=1, seconds=1),
            first_delay=timedelta(hours=1),
            repeat_delay=timedelta(days=3),
        )

        self.assertEqual([user.user_id for user in due], [101])
        self.assertEqual(due[0].reminder_count, 0)

    def test_completed_user_is_not_due(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)
        mark_completed(self.database_path, 101, self.now + timedelta(minutes=20))

        due = get_due_reminders(
            self.database_path,
            self.now + timedelta(hours=2),
            first_delay=timedelta(hours=1),
            repeat_delay=timedelta(days=3),
        )

        self.assertEqual(due, [])

    def test_repeat_reminder_waits_for_repeat_delay(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)
        mark_reminder_sent(self.database_path, 101, self.now + timedelta(hours=1))

        too_early = get_due_reminders(
            self.database_path,
            self.now + timedelta(days=2),
            first_delay=timedelta(hours=1),
            repeat_delay=timedelta(days=3),
        )
        due = get_due_reminders(
            self.database_path,
            self.now + timedelta(days=4),
            first_delay=timedelta(hours=1),
            repeat_delay=timedelta(days=3),
        )

        self.assertEqual(too_early, [])
        self.assertEqual([user.user_id for user in due], [101])
        self.assertEqual(due[0].reminder_count, 1)

    def test_repeated_start_does_not_postpone_pending_first_reminder(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)
        upsert_started_user(self.database_path, 101, "Alice Updated", "alice2", self.now + timedelta(minutes=50))

        due = get_due_reminders(
            self.database_path,
            self.now + timedelta(hours=1, seconds=1),
            first_delay=timedelta(hours=1),
            repeat_delay=timedelta(days=3),
        )

        self.assertEqual([user.user_id for user in due], [101])
        self.assertEqual(due[0].full_name, "Alice Updated")
        self.assertEqual(due[0].username, "alice2")


if __name__ == "__main__":
    unittest.main()
