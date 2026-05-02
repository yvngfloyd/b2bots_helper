from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReminderUser:
    user_id: int
    full_name: str
    username: str
    reminder_count: int


@dataclass(frozen=True)
class FormSnapshot:
    current_step: str
    form_data: dict[str, Any]


def initialize_database(database_path: str) -> None:
    path = Path(database_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                first_reminder_sent_at TEXT,
                last_reminder_sent_at TEXT,
                reminder_count INTEGER NOT NULL DEFAULT 0,
                current_step TEXT,
                form_data_json TEXT
            )
            """
        )
        _ensure_column(connection, "users", "current_step", "TEXT")
        _ensure_column(connection, "users", "form_data_json", "TEXT")


def upsert_started_user(
    database_path: str,
    user_id: int,
    full_name: str,
    username: str | None,
    now: datetime | None = None,
) -> None:
    current_time = _to_utc(now)
    existing = _get_user(database_path, user_id)
    username_value = username or ""

    with _connect(database_path) as connection:
        if existing is None or existing["completed_at"] is not None:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    full_name,
                    username,
                    started_at,
                    updated_at,
                    completed_at,
                    first_reminder_sent_at,
                    last_reminder_sent_at,
                    reminder_count
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    username = excluded.username,
                    started_at = excluded.started_at,
                    updated_at = excluded.updated_at,
                    completed_at = NULL,
                    first_reminder_sent_at = NULL,
                    last_reminder_sent_at = NULL,
                    reminder_count = 0,
                    current_step = NULL,
                    form_data_json = NULL
                """,
                (
                    user_id,
                    full_name,
                    username_value,
                    _serialize(current_time),
                    _serialize(current_time),
                ),
            )
            return

        connection.execute(
            """
            UPDATE users
            SET full_name = ?, username = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (full_name, username_value, _serialize(current_time), user_id),
        )


def mark_completed(database_path: str, user_id: int, now: datetime | None = None) -> None:
    current_time = _to_utc(now)
    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE users
            SET completed_at = ?, updated_at = ?, current_step = NULL, form_data_json = NULL
            WHERE user_id = ?
            """,
            (_serialize(current_time), _serialize(current_time), user_id),
        )


def get_due_reminders(
    database_path: str,
    now: datetime | None = None,
    *,
    first_delay: timedelta,
    repeat_delay: timedelta,
) -> list[ReminderUser]:
    current_time = _to_utc(now)
    first_threshold = current_time - first_delay
    repeat_threshold = current_time - repeat_delay

    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT user_id, full_name, username, reminder_count
            FROM users
            WHERE completed_at IS NULL
              AND (
                (first_reminder_sent_at IS NULL AND started_at <= ?)
                OR
                (first_reminder_sent_at IS NOT NULL AND last_reminder_sent_at <= ?)
              )
            ORDER BY started_at ASC
            """,
            (_serialize(first_threshold), _serialize(repeat_threshold)),
        ).fetchall()

    return [
        ReminderUser(
            user_id=int(row["user_id"]),
            full_name=str(row["full_name"]),
            username=str(row["username"]),
            reminder_count=int(row["reminder_count"]),
        )
        for row in rows
    ]


def mark_reminder_sent(database_path: str, user_id: int, now: datetime | None = None) -> None:
    current_time = _to_utc(now)
    timestamp = _serialize(current_time)
    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE users
            SET
                first_reminder_sent_at = COALESCE(first_reminder_sent_at, ?),
                last_reminder_sent_at = ?,
                reminder_count = reminder_count + 1,
                updated_at = ?
            WHERE user_id = ?
            """,
            (timestamp, timestamp, timestamp, user_id),
        )


def save_form_snapshot(
    database_path: str,
    user_id: int,
    *,
    current_step: str,
    form_data: dict[str, Any],
    now: datetime | None = None,
) -> None:
    current_time = _to_utc(now)
    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE users
            SET current_step = ?, form_data_json = ?, updated_at = ?
            WHERE user_id = ? AND completed_at IS NULL
            """,
            (
                current_step,
                json.dumps(form_data, ensure_ascii=False),
                _serialize(current_time),
                user_id,
            ),
        )


def get_form_snapshot(database_path: str, user_id: int) -> FormSnapshot | None:
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT current_step, form_data_json
            FROM users
            WHERE user_id = ? AND completed_at IS NULL
            """,
            (user_id,),
        ).fetchone()

    if row is None or row["current_step"] is None or row["form_data_json"] is None:
        return None

    return FormSnapshot(
        current_step=str(row["current_step"]),
        form_data=json.loads(str(row["form_data_json"])),
    )


def _connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _get_user(database_path: str, user_id: int) -> sqlite3.Row | None:
    with _connect(database_path) as connection:
        return connection.execute(
            "SELECT completed_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def _to_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(value: datetime) -> str:
    return _to_utc(value).isoformat(timespec="seconds")
