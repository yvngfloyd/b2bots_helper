from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


ANSWER_FIELDS = [
    ("business_type", "Ниша"),
    ("lead_source", "Источник"),
    ("current_problem", "Проблема"),
    ("main_goal", "Цель"),
    ("integration_need", "Интеграция"),
    ("launch_time", "Срок"),
    ("budget", "Бюджет"),
    ("task_description", "Описание"),
    ("contact", "Контакт"),
]


@dataclass(frozen=True)
class CrmUser:
    user_id: int
    full_name: str
    username: str
    status: str
    started_at: str
    updated_at: str
    completed_at: str
    current_step: str
    reminder_count: int
    first_reminder_sent_at: str
    last_reminder_sent_at: str
    answers: dict[str, Any]


def create_crm_test_user(database_path: str) -> int:
    user_id = -1
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as connection:
        _ensure_application_data_column(connection)
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
                current_step,
                form_data_json,
                application_data_json
            )
            VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, ?, NULL)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                started_at = excluded.started_at,
                updated_at = excluded.updated_at,
                completed_at = NULL,
                current_step = excluded.current_step,
                form_data_json = excluded.form_data_json
            """,
            (
                user_id,
                "CRM Self Test",
                "crm_self_test",
                timestamp,
                timestamp,
                "self_test",
                json.dumps({"contact": "CRM self-test row"}, ensure_ascii=False),
            ),
        )
    return user_id


def load_crm_users(database_path: str) -> list[CrmUser]:
    with _connect(database_path) as connection:
        _ensure_application_data_column(connection)
        rows = connection.execute(
            """
            SELECT
                user_id,
                full_name,
                username,
                started_at,
                updated_at,
                completed_at,
                first_reminder_sent_at,
                last_reminder_sent_at,
                reminder_count,
                current_step,
                form_data_json,
                application_data_json
            FROM users
            ORDER BY updated_at DESC, started_at DESC
            """
        ).fetchall()

    return [_row_to_crm_user(row) for row in rows]


def render_crm_html(users: list[CrmUser], database_path: str) -> str:
    completed_count = sum(1 for user in users if user.completed_at)
    active_count = len(users) - completed_count
    runtime_notice = _render_runtime_notice()
    rows_html = "\n".join(_render_user_row(user) for user in users)
    if not rows_html:
        rows_html = (
            '<tr><td class="empty" colspan="16">'
            "Пользователей пока нет. Нажмите «Тест записи», чтобы проверить, "
            "что CRM пишет именно в эту базу."
            "</td></tr>"
        )

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>B2Bots CRM</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --text: #182230;
      --muted: #667085;
      --line: #e4e7ec;
      --blue: #1684e8;
      --green: #079455;
      --amber: #b54708;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      padding: 28px 32px 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .meta, .stat-label {{
      color: var(--muted);
      font-size: 13px;
    }}
    .stats {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      margin-top: 12px;
      flex-wrap: wrap;
    }}
    .action-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 32px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      color: var(--text);
      font-weight: 650;
      font-size: 13px;
    }}
    .action-link-primary {{
      border-color: var(--blue);
      background: var(--blue);
      color: #ffffff;
    }}
    .action-link:hover {{ text-decoration: none; }}
    .stat {{
      min-width: 128px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }}
    .stat-value {{
      display: block;
      font-size: 20px;
      font-weight: 700;
    }}
    main {{ padding: 20px 32px 32px; }}
    .notice {{
      margin-bottom: 16px;
      padding: 12px 14px;
      border: 1px solid #fedf89;
      border-radius: 8px;
      background: #fffaeb;
      color: #93370d;
    }}
    .notice strong {{ color: #7a2e0e; }}
    .notice code {{
      color: #7a2e0e;
      font-weight: 650;
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      min-width: 1400px;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f2f4f7;
      color: #344054;
      font-size: 12px;
      text-transform: uppercase;
    }}
    tbody tr:hover {{ background: #f9fafb; }}
    .muted {{ color: var(--muted); }}
    .status {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      font-weight: 650;
      font-size: 12px;
    }}
    .status-done {{ color: var(--green); background: #ecfdf3; }}
    .status-active {{ color: var(--amber); background: #fffaeb; }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .long {{
      min-width: 260px;
      max-width: 360px;
      white-space: normal;
    }}
    .empty {{
      padding: 36px;
      text-align: center;
      color: var(--muted);
    }}
    @media (max-width: 760px) {{
      header {{
        display: block;
        padding: 22px 18px 16px;
      }}
      main {{ padding: 16px 18px 24px; }}
      .stats {{
        justify-content: flex-start;
        margin-top: 16px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>B2Bots CRM</h1>
      <div class="meta">База: {escape(Path(database_path).name)} · обновите страницу, чтобы подтянуть свежие данные</div>
      <div class="actions">
        <a class="action-link action-link-primary" href="/self-test">Тест записи</a>
        <a class="action-link" href="/debug">Диагностика</a>
      </div>
    </div>
    <div class="stats" aria-label="Сводка">
      <div class="stat"><span class="stat-value">{len(users)}</span><span class="stat-label">Всего пользователей: {len(users)}</span></div>
      <div class="stat"><span class="stat-value">{active_count}</span><span class="stat-label">В процессе</span></div>
      <div class="stat"><span class="stat-value">{completed_count}</span><span class="stat-label">Завершили</span></div>
    </div>
  </header>
  <main>
    {runtime_notice}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User ID</th>
            <th>Имя</th>
            <th>Username</th>
            <th>Статус</th>
            <th>Шаг</th>
            <th>Старт</th>
            <th>Обновлен</th>
            <th>Завершен</th>
            <th>Напоминаний</th>
            <th>Последнее напоминание</th>
            {''.join(f'<th>{escape(label)}</th>' for _, label in ANSWER_FIELDS)}
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>"""


def _render_runtime_notice() -> str:
    if os.getenv("BOT_TOKEN", "").strip() and os.getenv("OWNER_CHAT_ID", "").strip():
        return ""
    return (
        '<div class="notice">'
        "<strong>Локальная CRM не подключена к Telegram-боту.</strong> "
        "Эта страница читает только локальный SQLite-файл. Чтобы здесь появлялись реальные "
        "пользователи из Telegram, запускайте бота через <code>python main.py</code> "
        "с тем же <code>DATABASE_PATH</code> или открывайте CRM на Railway-домене."
        "</div>"
    )


def render_crm_debug_html(database_path: str) -> str:
    path = Path(database_path)
    absolute_path = path.resolve()
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    user_count = 0
    latest_rows: list[sqlite3.Row] = []
    error = ""

    try:
        with _connect(database_path) as connection:
            _ensure_application_data_column(connection)
            user_count = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            latest_rows = connection.execute(
                """
                SELECT user_id, full_name, username, started_at, updated_at, completed_at
                FROM users
                ORDER BY updated_at DESC, started_at DESC
                LIMIT 10
                """
            ).fetchall()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    rows_html = "\n".join(
        "<tr>"
        f"<td><code>{escape(str(row['user_id']))}</code></td>"
        f"<td>{escape(str(row['full_name']))}</td>"
        f"<td>{escape(str(row['username'] or '-'))}</td>"
        f"<td>{escape(str(row['started_at']))}</td>"
        f"<td>{escape(str(row['updated_at']))}</td>"
        f"<td>{escape(str(row['completed_at'] or '-'))}</td>"
        "</tr>"
        for row in latest_rows
    )
    if not rows_html:
        rows_html = '<tr><td colspan="6">No rows in users table</td></tr>'

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CRM Debug</title>
  <style>
    body {{ margin: 32px; font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #182230; }}
    h1 {{ margin: 0 0 18px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #e4e7ec; padding: 8px 10px; text-align: left; }}
    th {{ background: #f2f4f7; }}
    code {{ background: #f2f4f7; padding: 2px 4px; border-radius: 4px; }}
    .error {{ color: #b42318; }}
  </style>
</head>
<body>
  <h1>CRM Debug</h1>
  <p><b>Database path:</b> <code>{escape(database_path)}</code></p>
  <p><b>Absolute path:</b> <code>{escape(str(absolute_path))}</code></p>
  <p><b>Current working directory:</b> <code>{escape(os.getcwd())}</code></p>
  <p><b>Exists:</b> {exists}</p>
  <p><b>Size:</b> {size} bytes</p>
  <p><b>User rows:</b> {user_count}</p>
  {f'<p class="error"><b>Error:</b> {escape(error)}</p>' if error else ''}
  <h2>Latest rows</h2>
  <table>
    <thead>
      <tr>
        <th>User ID</th>
        <th>Name</th>
        <th>Username</th>
        <th>Started</th>
        <th>Updated</th>
        <th>Completed</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""


def _row_to_crm_user(row: sqlite3.Row) -> CrmUser:
    completed_at = _clean(row["completed_at"])
    answers = _parse_json(row["application_data_json"]) or _parse_json(row["form_data_json"]) or {}
    return CrmUser(
        user_id=int(row["user_id"]),
        full_name=_clean(row["full_name"]),
        username=_clean(row["username"]),
        status="Завершена" if completed_at else "В процессе",
        started_at=_clean(row["started_at"]),
        updated_at=_clean(row["updated_at"]),
        completed_at=completed_at,
        current_step=_clean(row["current_step"]),
        reminder_count=int(row["reminder_count"] or 0),
        first_reminder_sent_at=_clean(row["first_reminder_sent_at"]),
        last_reminder_sent_at=_clean(row["last_reminder_sent_at"]),
        answers=answers,
    )


def _render_user_row(user: CrmUser) -> str:
    status_class = "status-done" if user.completed_at else "status-active"
    username = _render_username(user.username)
    answer_cells = "".join(
        f'<td class="{_answer_cell_class(key)}">{_format_value(user.answers.get(key))}</td>'
        for key, _ in ANSWER_FIELDS
    )
    return f"""
<tr>
  <td><code>{user.user_id}</code></td>
  <td>{escape(user.full_name) or '<span class="muted">-</span>'}</td>
  <td>{username}</td>
  <td><span class="status {status_class}">{escape(user.status)}</span></td>
  <td>{_format_value(user.current_step)}</td>
  <td>{_format_value(user.started_at)}</td>
  <td>{_format_value(user.updated_at)}</td>
  <td>{_format_value(user.completed_at)}</td>
  <td>{user.reminder_count}</td>
  <td>{_format_value(user.last_reminder_sent_at)}</td>
  {answer_cells}
</tr>"""


def _render_username(username: str) -> str:
    if not username:
        return '<span class="muted">-</span>'
    escaped = escape(username)
    return f'<a href="https://t.me/{escaped}" target="_blank" rel="noreferrer">@{escaped}</a>'


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return '<span class="muted">-</span>'
    if isinstance(value, (dict, list)):
        return escape(json.dumps(value, ensure_ascii=False))
    return escape(str(value))


def _answer_cell_class(key: str) -> str:
    return "long" if key in {"task_description", "contact"} else ""


def _parse_json(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean(value: Any) -> str:
    return "" if value is None else str(value)


def _connect(database_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_application_data_column(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "application_data_json" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN application_data_json TEXT")
