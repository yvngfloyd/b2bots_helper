from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.tracking import track_user_safely


class TrackingTests(unittest.TestCase):
    def test_tracking_helper_does_not_raise_when_storage_fails(self) -> None:
        user = SimpleNamespace(id=777)

        with patch("app.tracking.upsert_user_from_telegram", side_effect=RuntimeError("db down")), patch(
            "app.tracking.logger"
        ):
            track_user_safely(user, message_text="/start", source="start")


if __name__ == "__main__":
    unittest.main()
