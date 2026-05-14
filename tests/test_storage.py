from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.storage import (
    APPLICATION_STATUSES,
    _is_postgres_database,
    _first_value,
    _postgres_sql,
    count_users,
    database_backend_name,
    display_database_location,
    get_application_data,
    get_form_snapshot,
    get_due_reminders,
    get_user_by_telegram_id,
    get_user_stats,
    initialize_database,
    list_users,
    mark_completed,
    mark_reminder_sent,
    mark_user_application_completed,
    patch_user_admin_fields,
    save_form_snapshot,
    update_user_progress,
    upsert_started_user,
    upsert_user_from_telegram,
)


class DatabaseBackendTests(unittest.TestCase):
    def test_detects_postgres_database_urls(self) -> None:
        self.assertTrue(_is_postgres_database("postgres://user:pass@host/db"))
        self.assertTrue(_is_postgres_database("postgresql://user:pass@host/db"))
        self.assertFalse(_is_postgres_database("bot_data.sqlite3"))

    def test_translates_sqlite_placeholders_for_postgres(self) -> None:
        self.assertEqual(
            _postgres_sql("SELECT * FROM users WHERE user_id = ? AND username = ?"),
            "SELECT * FROM users WHERE user_id = %s AND username = %s",
        )

    def test_displays_postgres_location_without_password(self) -> None:
        self.assertEqual(
            display_database_location("postgresql://user:secret@host.railway.internal:5432/railway"),
            "postgresql://***@host.railway.internal:5432/railway",
        )

    def test_database_backend_name_describes_selected_backend(self) -> None:
        self.assertEqual(database_backend_name("postgresql://user:secret@host/db"), "PostgreSQL")
        self.assertEqual(database_backend_name("bot_data.sqlite3"), "SQLite")

    def test_first_value_supports_dict_rows_and_tuple_rows(self) -> None:
        self.assertEqual(_first_value({"count": 3}), 3)
        self.assertEqual(_first_value((4,)), 4)


class StorageReminderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.database_path = str(Path(self.tmpdir.name) / "bot.sqlite3")
        initialize_database(self.database_path)
        self.now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)

    def test_started_user_is_due_after_first_delay(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)

        self.assertEqual(count_users(self.database_path), 1)

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

    def test_form_snapshot_round_trips_current_step_and_answers(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)
        save_form_snapshot(
            self.database_path,
            101,
            current_step="task_description",
            form_data={
                "history": [0, 1, 2],
                "business_type": "Услуги",
                "lead_source": "Telegram",
            },
            now=self.now + timedelta(minutes=10),
        )

        snapshot = get_form_snapshot(self.database_path, 101)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.current_step, "task_description")
        self.assertEqual(snapshot.form_data["history"], [0, 1, 2])
        self.assertEqual(snapshot.form_data["business_type"], "Услуги")

    def test_completed_user_loses_resume_snapshot_and_keeps_application_data(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)
        save_form_snapshot(
            self.database_path,
            101,
            current_step="budget",
            form_data={"history": [0, 1, 2, 3, 4, 5, 6]},
            now=self.now + timedelta(minutes=10),
        )
        mark_completed(
            self.database_path,
            101,
            self.now + timedelta(minutes=20),
            application_data={"business_type": "Услуги", "contact": "@alice"},
        )

        self.assertIsNone(get_form_snapshot(self.database_path, 101))
        self.assertEqual(
            get_application_data(self.database_path, 101),
            {"business_type": "Услуги", "contact": "@alice"},
        )


class UserTrackingStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.database_path = str(Path(self.tmpdir.name) / "bot.sqlite3")
        initialize_database(self.database_path)
        self.now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)

    def user(self, user_id: int = 101, username: str | None = "alice") -> SimpleNamespace:
        return SimpleNamespace(
            id=user_id,
            username=username,
            first_name="Alice",
            last_name="Smith",
            full_name="Alice Smith",
            language_code="ru",
        )

    def test_upsert_user_from_telegram_creates_and_updates_profile(self) -> None:
        upsert_user_from_telegram(
            self.database_path,
            self.user(),
            message_text="/start",
            source="start",
            now=self.now,
        )
        upsert_user_from_telegram(
            self.database_path,
            self.user(username="alice_new"),
            message_text="hello",
            now=self.now + timedelta(minutes=5),
        )

        user = get_user_by_telegram_id(self.database_path, 101)

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.telegram_id, 101)
        self.assertEqual(user.username, "alice_new")
        self.assertEqual(user.first_name, "Alice")
        self.assertEqual(user.last_name, "Smith")
        self.assertEqual(user.language_code, "ru")
        self.assertEqual(user.source, "start")
        self.assertEqual(user.first_seen_at, "2026-05-11T12:00:00+00:00")
        self.assertEqual(user.last_seen_at, "2026-05-11T12:05:00+00:00")
        self.assertEqual(user.last_message_text, "hello")
        self.assertEqual(user.application_status, "new")

    def test_progress_completion_reminder_and_admin_patch_update_tracking_fields(self) -> None:
        upsert_user_from_telegram(self.database_path, self.user(), now=self.now)

        update_user_progress(
            self.database_path,
            101,
            current_step="budget",
            answers={"business_type": "Услуги", "budget": "10-30"},
            now=self.now + timedelta(minutes=1),
        )
        mark_reminder_sent(self.database_path, 101, self.now + timedelta(hours=1))
        mark_user_application_completed(
            self.database_path,
            101,
            answers={"business_type": "Услуги", "contact": "+79990000000"},
            phone="+79990000000",
            now=self.now + timedelta(hours=2),
        )
        patch_user_admin_fields(
            self.database_path,
            101,
            application_status="contacted",
            notes="Позвонить завтра",
            is_blocked=True,
            now=self.now + timedelta(hours=3),
        )

        user = get_user_by_telegram_id(self.database_path, 101)

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.current_step, "")
        self.assertTrue(user.is_application_completed)
        self.assertEqual(user.application_status, "contacted")
        self.assertEqual(user.answers["contact"], "+79990000000")
        self.assertEqual(user.phone, "+79990000000")
        self.assertEqual(user.reminder_count, 1)
        self.assertEqual(user.last_reminder_at, "2026-05-11T13:00:00+00:00")
        self.assertTrue(user.is_blocked)
        self.assertEqual(user.notes, "Позвонить завтра")

    def test_list_users_search_filters_sort_and_pagination(self) -> None:
        upsert_user_from_telegram(self.database_path, self.user(101, "alice"), message_text="need crm", source="organic", now=self.now)
        update_user_progress(self.database_path, 101, current_step="budget", answers={"budget": "10-30"}, now=self.now + timedelta(minutes=2))
        upsert_user_from_telegram(self.database_path, self.user(202, "bob"), message_text="other", source="ads", now=self.now + timedelta(minutes=1))
        mark_user_application_completed(self.database_path, 202, answers={"contact": "@bob"}, now=self.now + timedelta(minutes=3))

        result = list_users(
            self.database_path,
            search="crm",
            status="in_progress",
            completed=False,
            sort_by="last_seen_at",
            sort_order="desc",
            limit=10,
            offset=0,
        )

        self.assertEqual(result.total, 1)
        self.assertEqual([user.telegram_id for user in result.items], [101])

        completed = list_users(self.database_path, completed=True)

        self.assertEqual([user.telegram_id for user in completed.items], [202])

    def test_stats_count_statuses_and_conversion(self) -> None:
        upsert_user_from_telegram(self.database_path, self.user(101, "alice"), now=self.now)
        update_user_progress(self.database_path, 101, current_step="budget", answers={}, now=self.now)
        upsert_user_from_telegram(self.database_path, self.user(202, "bob"), now=self.now)
        mark_user_application_completed(self.database_path, 202, answers={}, now=self.now)
        upsert_user_from_telegram(self.database_path, self.user(303, "cara"), now=self.now - timedelta(days=8))
        patch_user_admin_fields(self.database_path, 303, application_status="abandoned", now=self.now)

        stats = get_user_stats(self.database_path, now=self.now)

        self.assertEqual(stats["total_users"], 3)
        self.assertEqual(stats["in_progress_users"], 1)
        self.assertEqual(stats["completed_users"], 1)
        self.assertEqual(stats["abandoned_users"], 1)
        self.assertEqual(stats["users_today"], 2)
        self.assertEqual(stats["users_last_7_days"], 2)
        self.assertEqual(stats["conversion_to_completed_percent"], 33.33)

    def test_rejects_invalid_admin_status(self) -> None:
        upsert_user_from_telegram(self.database_path, self.user(), now=self.now)

        self.assertNotIn("bad", APPLICATION_STATUSES)
        with self.assertRaises(ValueError):
            patch_user_admin_fields(self.database_path, 101, application_status="bad")


if __name__ == "__main__":
    unittest.main()
