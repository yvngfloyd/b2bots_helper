from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


APPLICATION_STATUSES = {
    "new",
    "in_progress",
    "completed",
    "abandoned",
    "contacted",
    "not_relevant",
}

USER_SORT_FIELDS = {
    "last_seen_at": "last_seen_at",
    "first_seen_at": "first_seen_at",
    "application_status": "application_status",
    "reminder_count": "reminder_count",
}


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


@dataclass(frozen=True)
class TrackedUser:
    id: int
    telegram_id: int
    username: str
    first_name: str
    last_name: str
    language_code: str
    phone: str
    source: str
    first_seen_at: str
    last_seen_at: str
    last_message_text: str
    current_step: str
    application_status: str
    is_application_completed: bool
    answers: dict[str, Any]
    answers_json: str
    reminder_count: int
    last_reminder_at: str
    is_blocked: bool
    notes: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class UserListResult:
    items: list[TrackedUser]
    total: int
    limit: int
    offset: int


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
                form_data_json TEXT,
                application_data_json TEXT
            )
            """
        )
        _ensure_tracking_columns(connection)
        _backfill_tracking_columns(connection)
        _ensure_indexes(connection)


def upsert_started_user(
    database_path: str,
    user_id: int,
    full_name: str,
    username: str | None,
    now: datetime | None = None,
) -> None:
    current_time = _to_utc(now)
    timestamp = _serialize(current_time)
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
                    reminder_count,
                    telegram_id,
                    first_name,
                    last_name,
                    first_seen_at,
                    last_seen_at,
                    application_status,
                    is_application_completed,
                    created_at,
                    updated_at_v2
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, ?, ?, ?, ?, 'new', 0, ?, ?)
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
                    form_data_json = NULL,
                    telegram_id = excluded.telegram_id,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    first_seen_at = excluded.first_seen_at,
                    last_seen_at = excluded.last_seen_at,
                    application_status = 'new',
                    is_application_completed = 0,
                    created_at = excluded.created_at,
                    updated_at_v2 = excluded.updated_at_v2
                """,
                (
                    user_id,
                    full_name,
                    username_value,
                    timestamp,
                    timestamp,
                    user_id,
                    full_name,
                    "",
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            return

        connection.execute(
            """
            UPDATE users
            SET
                full_name = ?,
                username = ?,
                updated_at = ?,
                telegram_id = COALESCE(telegram_id, ?),
                first_name = ?,
                last_seen_at = ?,
                updated_at_v2 = ?
            WHERE user_id = ?
            """,
            (full_name, username_value, timestamp, user_id, full_name, timestamp, timestamp, user_id),
        )


def upsert_user_from_telegram(
    database_path: str,
    event_user: Any,
    message_text: str | None = None,
    source: str | None = None,
    now: datetime | None = None,
) -> None:
    current_time = _to_utc(now)
    timestamp = _serialize(current_time)
    telegram_id = int(event_user.id)
    username = getattr(event_user, "username", None) or ""
    first_name = getattr(event_user, "first_name", None) or ""
    last_name = getattr(event_user, "last_name", None) or ""
    language_code = getattr(event_user, "language_code", None) or ""
    full_name = _full_name(event_user, first_name, last_name)
    existing = _get_user(database_path, telegram_id)

    with _connect(database_path) as connection:
        if existing is None:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    full_name,
                    username,
                    started_at,
                    updated_at,
                    reminder_count,
                    telegram_id,
                    first_name,
                    last_name,
                    language_code,
                    source,
                    first_seen_at,
                    last_seen_at,
                    last_message_text,
                    application_status,
                    is_application_completed,
                    answers_json,
                    created_at,
                    updated_at_v2
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 0, NULL, ?, ?)
                """,
                (
                    telegram_id,
                    full_name,
                    username,
                    timestamp,
                    timestamp,
                    telegram_id,
                    first_name,
                    last_name,
                    language_code,
                    source or "",
                    timestamp,
                    timestamp,
                    message_text,
                    timestamp,
                    timestamp,
                ),
            )
            return

        connection.execute(
            """
            UPDATE users
            SET
                full_name = ?,
                username = ?,
                updated_at = ?,
                telegram_id = COALESCE(telegram_id, ?),
                first_name = ?,
                last_name = ?,
                language_code = ?,
                source = CASE WHEN COALESCE(source, '') = '' THEN ? ELSE source END,
                last_seen_at = ?,
                last_message_text = COALESCE(?, last_message_text),
                updated_at_v2 = ?
            WHERE user_id = ?
            """,
            (
                full_name,
                username,
                timestamp,
                telegram_id,
                first_name,
                last_name,
                language_code,
                source or "",
                timestamp,
                message_text,
                timestamp,
                telegram_id,
            ),
        )


def mark_completed(
    database_path: str,
    user_id: int,
    now: datetime | None = None,
    application_data: dict[str, Any] | None = None,
) -> None:
    mark_user_application_completed(database_path, user_id, application_data or {}, now=now)


def mark_user_application_completed(
    database_path: str,
    telegram_id: int,
    answers: dict[str, Any] | None = None,
    phone: str | None = None,
    now: datetime | None = None,
) -> None:
    current_time = _to_utc(now)
    timestamp = _serialize(current_time)
    answers_json = json.dumps(answers or {}, ensure_ascii=False)
    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE users
            SET
                completed_at = ?,
                updated_at = ?,
                current_step = NULL,
                form_data_json = NULL,
                application_data_json = ?,
                answers_json = ?,
                phone = COALESCE(?, phone),
                application_status = 'completed',
                is_application_completed = 1,
                last_seen_at = ?,
                updated_at_v2 = ?
            WHERE user_id = ?
            """,
            (timestamp, timestamp, answers_json, answers_json, phone, timestamp, timestamp, telegram_id),
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
              AND COALESCE(is_application_completed, 0) = 0
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
                last_reminder_at = ?,
                reminder_count = reminder_count + 1,
                updated_at = ?,
                updated_at_v2 = ?
            WHERE user_id = ?
            """,
            (timestamp, timestamp, timestamp, timestamp, timestamp, user_id),
        )


def save_form_snapshot(
    database_path: str,
    user_id: int,
    *,
    current_step: str,
    form_data: dict[str, Any],
    now: datetime | None = None,
) -> None:
    update_user_progress(database_path, user_id, current_step=current_step, answers=form_data, now=now)


def update_user_progress(
    database_path: str,
    telegram_id: int,
    *,
    current_step: str,
    answers: dict[str, Any],
    status: str = "in_progress",
    now: datetime | None = None,
) -> None:
    _validate_status(status)
    current_time = _to_utc(now)
    timestamp = _serialize(current_time)
    answers_json = json.dumps(answers, ensure_ascii=False)
    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE users
            SET
                current_step = ?,
                form_data_json = ?,
                answers_json = ?,
                application_status = ?,
                is_application_completed = 0,
                updated_at = ?,
                updated_at_v2 = ?
            WHERE user_id = ? AND completed_at IS NULL
            """,
            (current_step, answers_json, answers_json, status, timestamp, timestamp, telegram_id),
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


def get_application_data(database_path: str, user_id: int) -> dict[str, Any] | None:
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT application_data_json
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None or row["application_data_json"] is None:
        return None

    return json.loads(str(row["application_data_json"]))


def list_users(
    database_path: str,
    *,
    search: str | None = None,
    status: str | None = None,
    completed: bool | None = None,
    source: str | None = None,
    sort_by: str = "last_seen_at",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> UserListResult:
    where_sql, params = _build_user_filters(search=search, status=status, completed=completed, source=source)
    sort_column = USER_SORT_FIELDS.get(sort_by)
    if sort_column is None:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    normalized_order = sort_order.lower()
    if normalized_order not in {"asc", "desc"}:
        raise ValueError(f"Unsupported sort order: {sort_order}")
    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))

    with _connect(database_path) as connection:
        total = int(connection.execute(f"SELECT COUNT(*) FROM users {where_sql}", params).fetchone()[0])
        rows = connection.execute(
            f"""
            SELECT *
            FROM users
            {where_sql}
            ORDER BY {sort_column} {normalized_order.upper()}, user_id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, safe_limit, safe_offset),
        ).fetchall()

    return UserListResult(
        items=[_row_to_tracked_user(row) for row in rows],
        total=total,
        limit=safe_limit,
        offset=safe_offset,
    )


def get_user_by_telegram_id(database_path: str, telegram_id: int) -> TrackedUser | None:
    with _connect(database_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE user_id = ?", (telegram_id,)).fetchone()
    return _row_to_tracked_user(row) if row is not None else None


def patch_user_admin_fields(
    database_path: str,
    telegram_id: int,
    *,
    application_status: str | None = None,
    notes: str | None = None,
    is_blocked: bool | None = None,
    now: datetime | None = None,
) -> TrackedUser | None:
    if application_status is not None:
        _validate_status(application_status)
    current_time = _to_utc(now)
    timestamp = _serialize(current_time)
    assignments = ["updated_at_v2 = ?", "updated_at = ?"]
    params: list[Any] = [timestamp, timestamp]
    if application_status is not None:
        assignments.append("application_status = ?")
        params.append(application_status)
    if notes is not None:
        assignments.append("notes = ?")
        params.append(notes)
    if is_blocked is not None:
        assignments.append("is_blocked = ?")
        params.append(1 if is_blocked else 0)
    params.append(telegram_id)

    with _connect(database_path) as connection:
        connection.execute(
            f"UPDATE users SET {', '.join(assignments)} WHERE user_id = ?",
            tuple(params),
        )

    return get_user_by_telegram_id(database_path, telegram_id)


def get_user_stats(database_path: str, now: datetime | None = None) -> dict[str, Any]:
    current_time = _to_utc(now)
    today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = current_time - timedelta(days=7)
    with _connect(database_path) as connection:
        total = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        counts = {
            status: int(
                connection.execute(
                    "SELECT COUNT(*) FROM users WHERE application_status = ?",
                    (status,),
                ).fetchone()[0]
            )
            for status in APPLICATION_STATUSES
        }
        users_today = int(
            connection.execute(
                "SELECT COUNT(*) FROM users WHERE first_seen_at >= ?",
                (_serialize(today_start),),
            ).fetchone()[0]
        )
        users_last_7_days = int(
            connection.execute(
                "SELECT COUNT(*) FROM users WHERE first_seen_at >= ?",
                (_serialize(seven_days_ago),),
            ).fetchone()[0]
        )

    completed = counts.get("completed", 0)
    conversion = round((completed / total * 100), 2) if total else 0.0
    return {
        "total_users": total,
        "new_users": counts.get("new", 0),
        "in_progress_users": counts.get("in_progress", 0),
        "completed_users": completed,
        "abandoned_users": counts.get("abandoned", 0),
        "contacted_users": counts.get("contacted", 0),
        "users_today": users_today,
        "users_last_7_days": users_last_7_days,
        "conversion_to_completed_percent": conversion,
    }


def count_users(database_path: str) -> int:
    with _connect(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
    return int(row[0])


def _build_user_filters(
    *,
    search: str | None = None,
    status: str | None = None,
    completed: bool | None = None,
    source: str | None = None,
) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        clauses.append(
            "("
            "CAST(user_id AS TEXT) LIKE ? OR "
            "username LIKE ? OR "
            "first_name LIKE ? OR "
            "last_name LIKE ? OR "
            "last_message_text LIKE ?"
            ")"
        )
        params.extend([pattern, pattern, pattern, pattern, pattern])
    if status:
        _validate_status(status)
        clauses.append("application_status = ?")
        params.append(status)
    if completed is not None:
        clauses.append("is_application_completed = ?")
        params.append(1 if completed else 0)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if not clauses:
        return "", tuple()
    return "WHERE " + " AND ".join(clauses), tuple(params)


def _connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_tracking_columns(connection: sqlite3.Connection) -> None:
    _ensure_column(connection, "users", "current_step", "TEXT")
    _ensure_column(connection, "users", "form_data_json", "TEXT")
    _ensure_column(connection, "users", "application_data_json", "TEXT")
    _ensure_column(connection, "users", "telegram_id", "INTEGER")
    _ensure_column(connection, "users", "first_name", "TEXT")
    _ensure_column(connection, "users", "last_name", "TEXT")
    _ensure_column(connection, "users", "language_code", "TEXT")
    _ensure_column(connection, "users", "phone", "TEXT")
    _ensure_column(connection, "users", "source", "TEXT")
    _ensure_column(connection, "users", "first_seen_at", "TEXT")
    _ensure_column(connection, "users", "last_seen_at", "TEXT")
    _ensure_column(connection, "users", "last_message_text", "TEXT")
    _ensure_column(connection, "users", "application_status", "TEXT NOT NULL DEFAULT 'new'")
    _ensure_column(connection, "users", "is_application_completed", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "users", "answers_json", "TEXT")
    _ensure_column(connection, "users", "last_reminder_at", "TEXT")
    _ensure_column(connection, "users", "is_blocked", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "users", "notes", "TEXT")
    _ensure_column(connection, "users", "created_at", "TEXT")
    _ensure_column(connection, "users", "updated_at_v2", "TEXT")


def _backfill_tracking_columns(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE users
        SET
            telegram_id = COALESCE(telegram_id, user_id),
            first_name = COALESCE(first_name, full_name, ''),
            last_name = COALESCE(last_name, ''),
            language_code = COALESCE(language_code, ''),
            phone = COALESCE(phone, ''),
            source = COALESCE(source, ''),
            first_seen_at = COALESCE(first_seen_at, started_at),
            last_seen_at = COALESCE(last_seen_at, updated_at),
            last_message_text = COALESCE(last_message_text, ''),
            application_status = CASE
                WHEN completed_at IS NOT NULL AND COALESCE(application_status, 'new') = 'new' THEN 'completed'
                WHEN (current_step IS NOT NULL OR form_data_json IS NOT NULL) AND COALESCE(application_status, 'new') = 'new' THEN 'in_progress'
                WHEN application_status IS NOT NULL AND application_status != '' THEN application_status
                ELSE 'new'
            END,
            is_application_completed = CASE
                WHEN completed_at IS NOT NULL THEN 1
                ELSE COALESCE(is_application_completed, 0)
            END,
            answers_json = COALESCE(answers_json, application_data_json, form_data_json),
            last_reminder_at = COALESCE(last_reminder_at, last_reminder_sent_at),
            is_blocked = COALESCE(is_blocked, 0),
            notes = COALESCE(notes, ''),
            created_at = COALESCE(created_at, started_at),
            updated_at_v2 = COALESCE(updated_at_v2, updated_at)
        """
    )


def _ensure_indexes(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_application_status ON users(application_status)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users(last_seen_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_is_application_completed ON users(is_application_completed)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_source ON users(source)")


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


def _row_to_tracked_user(row: sqlite3.Row) -> TrackedUser:
    answers_json = _clean(row["answers_json"]) or _clean(row["application_data_json"]) or _clean(row["form_data_json"])
    answers = _parse_json(answers_json) or {}
    return TrackedUser(
        id=int(row["user_id"]),
        telegram_id=int(row["telegram_id"] or row["user_id"]),
        username=_clean(row["username"]),
        first_name=_clean(row["first_name"]) or _clean(row["full_name"]),
        last_name=_clean(row["last_name"]),
        language_code=_clean(row["language_code"]),
        phone=_clean(row["phone"]),
        source=_clean(row["source"]),
        first_seen_at=_clean(row["first_seen_at"]) or _clean(row["started_at"]),
        last_seen_at=_clean(row["last_seen_at"]) or _clean(row["updated_at"]),
        last_message_text=_clean(row["last_message_text"]),
        current_step=_clean(row["current_step"]),
        application_status=_clean(row["application_status"]) or "new",
        is_application_completed=bool(row["is_application_completed"]),
        answers=answers,
        answers_json=answers_json,
        reminder_count=int(row["reminder_count"] or 0),
        last_reminder_at=_clean(row["last_reminder_at"]) or _clean(row["last_reminder_sent_at"]),
        is_blocked=bool(row["is_blocked"]),
        notes=_clean(row["notes"]),
        created_at=_clean(row["created_at"]) or _clean(row["started_at"]),
        updated_at=_clean(row["updated_at_v2"]) or _clean(row["updated_at"]),
    )


def _parse_json(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _validate_status(status: str) -> None:
    if status not in APPLICATION_STATUSES:
        raise ValueError(f"Unsupported application status: {status}")


def _full_name(event_user: Any, first_name: str, last_name: str) -> str:
    full_name = getattr(event_user, "full_name", None)
    if full_name:
        return str(full_name)
    return " ".join(part for part in (first_name, last_name) if part).strip()


def _clean(value: Any) -> str:
    return "" if value is None else str(value)


def _to_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(value: datetime) -> str:
    return _to_utc(value).isoformat(timespec="seconds")
