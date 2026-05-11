from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path

from app.crm import create_crm_test_user, load_crm_users, render_crm_debug_html, render_crm_html
from crm_server import (
    _api_export_users_csv,
    _api_export_users_list,
    _api_export_users_tsv,
    _api_export_users_xlsx,
    _api_list_users,
    _tracked_user_to_dict,
    is_authorized,
)
from app.storage import (
    get_user_by_telegram_id,
    initialize_database,
    mark_completed,
    mark_reminder_sent,
    save_form_snapshot,
    upsert_user_from_telegram,
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
        self.assertIn("/debug", html)
        self.assertIn("/self-test", html)
        self.assertIn("/api/users", html)
        self.assertIn("автообновление каждые 7 секунд", html)

    def test_render_crm_html_warns_when_local_crm_is_not_connected_to_bot_runtime(self) -> None:
        with patch.dict("os.environ", {"BOT_TOKEN": "", "OWNER_CHAT_ID": ""}):
            html = render_crm_html([], self.database_path)

        self.assertIn("Локальная CRM не подключена к Telegram-боту", html)
        self.assertIn("python main.py", html)

    def test_render_crm_html_warns_when_railway_database_is_not_on_volume(self) -> None:
        with patch.dict(
            "os.environ",
            {"BOT_TOKEN": "123:abc", "OWNER_CHAT_ID": "1", "RAILWAY_ENVIRONMENT": "production"},
        ):
            html = render_crm_html([], "bot_data.sqlite3")

        self.assertIn("База Railway не на persistent Volume", html)
        self.assertIn("/data/bot_data.sqlite3", html)

    def test_render_debug_html_shows_database_path_and_latest_users(self) -> None:
        upsert_started_user(self.database_path, 101, "Alice", "alice", self.now)

        html = render_crm_debug_html(self.database_path)

        self.assertIn("CRM Debug", html)
        self.assertIn("bot.sqlite3", html)
        self.assertIn("User rows", html)
        self.assertIn("Alice", html)

    def test_create_crm_test_user_writes_to_same_database(self) -> None:
        created_id = create_crm_test_user(self.database_path)

        users = load_crm_users(self.database_path)

        self.assertEqual(created_id, -1)
        self.assertEqual(users[0].user_id, -1)
        self.assertEqual(users[0].full_name, "CRM Self Test")

    def test_api_list_users_returns_paginated_items(self) -> None:
        user = type(
            "TelegramUser",
            (),
            {
                "id": 303,
                "username": "charlie",
                "first_name": "Charlie",
                "last_name": "Lead",
                "full_name": "Charlie Lead",
                "language_code": "ru",
            },
        )()
        upsert_user_from_telegram(self.database_path, user, message_text="/start", source="ads", now=self.now)
        save_form_snapshot(
            self.database_path,
            303,
            current_step="budget",
            form_data={"business_type": "B2B", "budget": "50+"},
            now=self.now + timedelta(minutes=2),
        )

        payload = _api_list_users(
            self.database_path,
            {"search": ["charlie"], "status": ["in_progress"], "limit": ["10"]},
        )

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["telegram_id"], 303)
        self.assertEqual(payload["items"][0]["application_status"], "in_progress")
        self.assertEqual(payload["items"][0]["last_message_text"], "/start")

    def test_api_user_detail_includes_parsed_answers(self) -> None:
        upsert_started_user(self.database_path, 404, "Dana", "dana", self.now)
        mark_completed(
            self.database_path,
            404,
            self.now + timedelta(minutes=10),
            application_data={"business_type": "Retail", "contact": "@dana"},
        )

        user = get_user_by_telegram_id(self.database_path, 404)
        self.assertIsNotNone(user)
        payload = _tracked_user_to_dict(user, include_parsed_answers=True)

        self.assertEqual(payload["application_status"], "completed")
        self.assertEqual(payload["answers"]["contact"], "@dana")

    def test_api_export_users_csv_contains_user_columns(self) -> None:
        upsert_started_user(self.database_path, 505, "Eve", "eve", self.now)

        csv_body = _api_export_users_csv(self.database_path, {})

        self.assertIn("telegram_id,username,telegram_url,first_name", csv_body)
        self.assertIn("505,eve,https://t.me/eve,Eve", csv_body)

    def test_api_export_users_tsv_contains_tabular_rows(self) -> None:
        upsert_started_user(self.database_path, 606, "Frank", "frank", self.now)

        tsv_body = _api_export_users_tsv(self.database_path, {})

        self.assertIn("telegram_id\tusername\ttelegram_url\tfirst_name", tsv_body)
        self.assertIn("606\tfrank\thttps://t.me/frank\tFrank", tsv_body)

    def test_api_export_users_xlsx_is_valid_workbook(self) -> None:
        import zipfile
        from io import BytesIO

        upsert_started_user(self.database_path, 707, "Grace", "grace", self.now)

        workbook = _api_export_users_xlsx(self.database_path, {})

        with zipfile.ZipFile(BytesIO(workbook)) as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("telegram_id", sheet)
        self.assertIn("grace", sheet)
        self.assertIn("https://t.me/grace", sheet)

    def test_api_export_users_list_contains_plain_clickable_links(self) -> None:
        upsert_started_user(self.database_path, 808, "Helen", "helen", self.now)
        upsert_started_user(self.database_path, 909, "No Username", None, self.now + timedelta(minutes=1))

        list_body = _api_export_users_list(self.database_path, {})

        self.assertIn("https://t.me/helen", list_body)
        self.assertIn("808", list_body)
        self.assertIn("909 | No Username | username отсутствует", list_body)


class CrmAuthTests(unittest.TestCase):
    def test_auth_is_open_when_credentials_are_missing(self) -> None:
        self.assertTrue(is_authorized(None, "", ""))
        self.assertTrue(is_authorized(None, "admin", ""))
        self.assertFalse(is_authorized(None, "", "", "secret"))

    def test_auth_accepts_bearer_admin_token(self) -> None:
        self.assertTrue(is_authorized("Bearer secret", "", "", "secret"))
        self.assertTrue(is_authorized("Bearer secret", "admin", "pass", "secret"))

    def test_auth_accepts_matching_basic_header(self) -> None:
        self.assertTrue(is_authorized("Basic YWRtaW46cGFzcw==", "admin", "pass"))

    def test_auth_accepts_session_cookie_created_after_basic_login(self) -> None:
        self.assertTrue(is_authorized(None, "admin", "pass", cookie_header="B2BOTS_CRM_AUTH=YWRtaW46cGFzcw=="))

    def test_auth_rejects_missing_or_wrong_header(self) -> None:
        self.assertFalse(is_authorized(None, "admin", "pass"))
        self.assertFalse(is_authorized("Basic YWRtaW46d3Jvbmc=", "admin", "pass"))


if __name__ == "__main__":
    unittest.main()
