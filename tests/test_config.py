from __future__ import annotations

import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("OWNER_CHAT_ID", "123456")

from app.config import parse_bool


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


if __name__ == "__main__":
    unittest.main()
