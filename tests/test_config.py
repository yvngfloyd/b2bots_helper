from __future__ import annotations

import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.config import parse_bool, resolve_crm_port, resolve_database_path


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

    def test_resolve_crm_port_prefers_railway_port(self) -> None:
        self.assertEqual(resolve_crm_port("12345", "8080"), 12345)

    def test_resolve_crm_port_uses_crm_port_without_railway_port(self) -> None:
        self.assertEqual(resolve_crm_port("", "8080"), 8080)

    def test_resolve_database_path_prefers_explicit_path(self) -> None:
        self.assertEqual(resolve_database_path("custom.sqlite3", "/data"), "custom.sqlite3")

    def test_resolve_database_path_uses_railway_volume_for_default_path(self) -> None:
        self.assertEqual(resolve_database_path("bot_data.sqlite3", "/data"), "/data/bot_data.sqlite3")

    def test_resolve_database_path_uses_railway_volume_when_available(self) -> None:
        self.assertEqual(resolve_database_path("", "/data"), "/data/bot_data.sqlite3")

    def test_resolve_database_path_falls_back_to_local_sqlite(self) -> None:
        self.assertEqual(resolve_database_path("", ""), "bot_data.sqlite3")

    def test_settings_reads_admin_token(self) -> None:
        from app.config import Settings

        settings = Settings(bot_token="123:abc", owner_chat_id=1, site_url="", tg_channel_url="", admin_token="secret")

        self.assertEqual(settings.admin_token, "secret")


if __name__ == "__main__":
    unittest.main()
