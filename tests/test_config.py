from __future__ import annotations

import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.config import (
    is_railway_runtime,
    parse_bool,
    resolve_owner_chat_ids,
    resolve_crm_enabled,
    resolve_crm_host,
    resolve_crm_port,
    resolve_database_location,
    resolve_database_path,
)


class ConfigParsingTests(unittest.TestCase):
    def test_parse_bool_accepts_common_true_values(self) -> None:
        self.assertTrue(parse_bool("1"))
        self.assertTrue(parse_bool("true"))
        self.assertTrue(parse_bool("yes"))
        self.assertTrue(parse_bool("on"))

    def test_parse_bool_accepts_common_false_values(self) -> None:
        self.assertFalse(parse_bool("0", default=True))
        self.assertFalse(parse_bool("false", default=True))
        self.assertFalse(parse_bool("no", default=True))
        self.assertFalse(parse_bool("off", default=True))

    def test_parse_bool_uses_default_for_empty_or_unknown_values(self) -> None:
        self.assertFalse(parse_bool(""))
        self.assertTrue(parse_bool("", default=True))
        self.assertTrue(parse_bool("later", default=True))

    def test_resolve_owner_chat_ids_keeps_owner_and_default_extra_admin(self) -> None:
        self.assertEqual(resolve_owner_chat_ids("123456", ""), (123456, 5768086346))

    def test_resolve_owner_chat_ids_adds_comma_separated_admins_without_duplicates(self) -> None:
        self.assertEqual(
            resolve_owner_chat_ids("123456", "222, 5768086346, 123456"),
            (123456, 222, 5768086346),
        )

    def test_resolve_crm_port_prefers_railway_port(self) -> None:
        self.assertEqual(resolve_crm_port("12345", "8080"), 12345)

    def test_resolve_crm_port_uses_crm_port_without_railway_port(self) -> None:
        self.assertEqual(resolve_crm_port("", "8080"), 8080)

    def test_is_railway_runtime_detects_railway_env(self) -> None:
        self.assertTrue(is_railway_runtime("", "production"))

    def test_is_railway_runtime_detects_railway_port(self) -> None:
        self.assertTrue(is_railway_runtime("12345", ""))

    def test_is_railway_runtime_ignores_local_env(self) -> None:
        self.assertFalse(is_railway_runtime("", ""))

    def test_resolve_crm_enabled_defaults_on_for_railway(self) -> None:
        self.assertTrue(resolve_crm_enabled(None, is_railway=True))

    def test_resolve_crm_enabled_defaults_off_locally(self) -> None:
        self.assertFalse(resolve_crm_enabled(None, is_railway=False))

    def test_resolve_crm_enabled_allows_explicit_false_on_railway(self) -> None:
        self.assertFalse(resolve_crm_enabled("false", is_railway=True))

    def test_resolve_crm_host_binds_publicly_on_railway(self) -> None:
        self.assertEqual(resolve_crm_host(None, is_railway=True), "0.0.0.0")

    def test_resolve_crm_host_keeps_loopback_locally(self) -> None:
        self.assertEqual(resolve_crm_host(None, is_railway=False), "127.0.0.1")

    def test_resolve_crm_host_prefers_explicit_value(self) -> None:
        self.assertEqual(resolve_crm_host("127.0.0.1", is_railway=True), "127.0.0.1")

    def test_resolve_database_path_prefers_explicit_path(self) -> None:
        self.assertEqual(resolve_database_path("custom.sqlite3", "/data"), "custom.sqlite3")

    def test_resolve_database_path_uses_railway_volume_for_default_path(self) -> None:
        self.assertEqual(resolve_database_path("bot_data.sqlite3", "/data"), "/data/bot_data.sqlite3")

    def test_resolve_database_path_uses_railway_volume_when_available(self) -> None:
        self.assertEqual(resolve_database_path("", "/data"), "/data/bot_data.sqlite3")

    def test_resolve_database_path_uses_data_mount_when_railway_volume_env_is_missing(self) -> None:
        self.assertEqual(
            resolve_database_path("", "", data_mount_exists=lambda path: path == "/data"),
            "/data/bot_data.sqlite3",
        )

    def test_resolve_database_path_moves_default_relative_path_to_data_mount(self) -> None:
        self.assertEqual(
            resolve_database_path("bot_data.sqlite3", "", data_mount_exists=lambda path: path == "/data"),
            "/data/bot_data.sqlite3",
        )

    def test_resolve_database_path_keeps_explicit_persistent_path(self) -> None:
        self.assertEqual(resolve_database_path("/data/custom.sqlite3", ""), "/data/custom.sqlite3")

    def test_resolve_database_path_falls_back_to_local_sqlite(self) -> None:
        self.assertEqual(resolve_database_path("", ""), "bot_data.sqlite3")

    def test_resolve_database_location_prefers_database_url(self) -> None:
        self.assertEqual(
            resolve_database_location(
                "postgresql://user:pass@host:5432/db",
                "/data/bot_data.sqlite3",
                "/data",
            ),
            "postgresql://user:pass@host:5432/db",
        )

    def test_resolve_database_location_falls_back_to_sqlite_path(self) -> None:
        self.assertEqual(
            resolve_database_location(
                "",
                "",
                "/data",
                data_mount_exists=lambda path: False,
            ),
            "/data/bot_data.sqlite3",
        )

    def test_settings_reads_admin_token(self) -> None:
        from app.config import Settings

        settings = Settings(
            bot_token="123:abc",
            owner_chat_id=1,
            owner_chat_ids=(1, 2),
            site_url="",
            tg_channel_url="",
            admin_token="secret",
        )

        self.assertEqual(settings.admin_token, "secret")


if __name__ == "__main__":
    unittest.main()
