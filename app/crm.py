from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


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
            '<tr><td class="empty" colspan="12">'
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
    .toolbar {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    input, select, textarea {{
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      color: var(--text);
      padding: 7px 10px;
      font: inherit;
    }}
    input[type="search"] {{ min-width: 260px; }}
    button {{
      min-height: 32px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      color: var(--text);
      cursor: pointer;
      font: inherit;
      font-weight: 650;
      padding: 6px 10px;
    }}
    button:hover {{ border-color: #98a2b3; }}
    .sort-button {{
      border: 0;
      border-radius: 0;
      background: transparent;
      color: inherit;
      padding: 0;
      text-transform: uppercase;
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
    .status-new {{ color: #175cd3; background: #eff8ff; }}
    .status-muted {{ color: #475467; background: #f2f4f7; }}
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: rgb(16 24 40 / 44%);
      z-index: 10;
    }}
    .modal-backdrop.open {{ display: flex; }}
    .modal {{
      width: min(760px, 100%);
      max-height: calc(100vh - 48px);
      overflow: auto;
      border-radius: 8px;
      background: #ffffff;
      box-shadow: 0 20px 48px rgb(16 24 40 / 22%);
    }}
    .modal header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 20px;
    }}
    .modal-body {{ padding: 18px 20px 20px; }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 18px;
      margin-bottom: 16px;
    }}
    .detail-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .answers {{
      display: grid;
      gap: 8px;
      margin: 12px 0 16px;
    }}
    .answer-row {{
      display: grid;
      grid-template-columns: 170px minmax(0, 1fr);
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px solid var(--line);
    }}
    .modal-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
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
      .detail-grid, .answer-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>B2Bots CRM</h1>
      <div class="meta">База: {escape(Path(database_path).name)} · автообновление каждые 7 секунд</div>
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
    <div class="toolbar" aria-label="Фильтры пользователей">
      <input id="search" type="search" placeholder="Поиск: username, имя, ID, сообщение">
      <select id="status-filter">
        <option value="">Все статусы</option>
        <option value="new">Новый</option>
        <option value="in_progress">В процессе</option>
        <option value="completed">Завершил</option>
        <option value="abandoned">Брошено</option>
        <option value="contacted">Связались</option>
        <option value="not_relevant">Не подходит</option>
      </select>
      <select id="completed-filter">
        <option value="">Все заявки</option>
        <option value="true">Завершенные</option>
        <option value="false">Не завершенные</option>
      </select>
      <input id="source-filter" type="search" placeholder="Источник">
      <a class="action-link export-link" data-export="csv" href="/api/users/export.csv">CSV</a>
      <a class="action-link export-link" data-export="tsv" href="/api/users/export.tsv">TSV</a>
      <a class="action-link export-link" data-export="xlsx" href="/api/users/export.xlsx">Excel</a>
      <span class="meta" id="refresh-state">Загрузка...</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Telegram ID</th>
            <th>Username</th>
            <th>Имя</th>
            <th>Статус</th>
            <th>Completed</th>
            <th>Current step</th>
            <th>Source</th>
            <th><button class="sort-button" data-sort="reminder_count">Reminder count</button></th>
            <th><button class="sort-button" data-sort="first_seen_at">First seen</button></th>
            <th><button class="sort-button" data-sort="last_seen_at">Last seen</button></th>
            <th>Last message</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="users-body">
          {rows_html}
        </tbody>
      </table>
    </div>
    <div class="modal-backdrop" id="user-modal" role="dialog" aria-modal="true">
      <section class="modal">
        <header>
          <h2 id="modal-title">Пользователь</h2>
          <button type="button" id="modal-close">Закрыть</button>
        </header>
        <div class="modal-body" id="modal-body"></div>
      </section>
    </div>
  </main>
  {_render_crm_script()}
</body>
</html>"""


def _render_crm_script() -> str:
    return r"""<script>
(() => {
  const labels = {
    new: "Новый",
    in_progress: "В процессе",
    completed: "Завершил",
    abandoned: "Брошено",
    contacted: "Связались",
    not_relevant: "Не подходит",
  };
  const badgeClasses = {
    new: "status-new",
    in_progress: "status-active",
    completed: "status-done",
    abandoned: "status-muted",
    contacted: "status-done",
    not_relevant: "status-muted",
  };
  const answerLabels = {
    business_type: "Ниша",
    lead_source: "Источник",
    current_problem: "Проблема",
    main_goal: "Цель",
    integration_need: "Интеграция",
    launch_time: "Срок",
    budget: "Бюджет",
    task_description: "Описание",
    contact: "Контакт",
  };
  const state = {
    sortBy: "last_seen_at",
    sortOrder: "desc",
    limit: 50,
    offset: 0,
    selectedUser: null,
  };
  const body = document.querySelector("#users-body");
  const refreshState = document.querySelector("#refresh-state");
  const modal = document.querySelector("#user-modal");
  const modalBody = document.querySelector("#modal-body");
  const modalTitle = document.querySelector("#modal-title");

  function authHeaders(extra = {}) {
    const token = window.localStorage.getItem("B2BOTS_ADMIN_TOKEN") || "";
    return token ? {...extra, Authorization: `Bearer ${token}`} : extra;
  }

  function value(id) {
    return document.querySelector(id).value.trim();
  }

  function params() {
    const query = new URLSearchParams({
      sort_by: state.sortBy,
      sort_order: state.sortOrder,
      limit: String(state.limit),
      offset: String(state.offset),
    });
    const search = value("#search");
    const status = value("#status-filter");
    const completed = value("#completed-filter");
    const source = value("#source-filter");
    if (search) query.set("search", search);
    if (status) query.set("status", status);
    if (completed) query.set("completed", completed);
    if (source) query.set("source", source);
    return query;
  }

  function syncExportLinks() {
    const query = params().toString();
    document.querySelectorAll(".export-link").forEach((link) => {
      const format = link.dataset.export;
      link.href = `/api/users/export.${format}?${query}`;
    });
  }

  async function api(path, options = {}) {
    const url = new URL(path, window.location.href);
    url.username = "";
    url.password = "";
    const response = await fetch(url.toString(), {
      ...options,
      credentials: "same-origin",
      headers: authHeaders(options.headers || {}),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }

  async function loadUsers() {
    try {
      syncExportLinks();
      const [users, stats] = await Promise.all([
        api(`/api/users?${params().toString()}`),
        api("/api/users/stats"),
      ]);
      renderStats(stats);
      renderRows(users.items);
      refreshState.textContent = `Обновлено: ${new Date().toLocaleTimeString("ru-RU")}`;
    } catch (error) {
      refreshState.textContent = "Не удалось загрузить данные";
      console.error(error);
    }
  }

  function renderStats(stats) {
    const values = document.querySelectorAll(".stat-value");
    const labelsEls = document.querySelectorAll(".stat-label");
    if (values[0]) values[0].textContent = stats.total_users;
    if (labelsEls[0]) labelsEls[0].textContent = `Всего пользователей: ${stats.total_users}`;
    if (values[1]) values[1].textContent = stats.in_progress_users;
    if (values[2]) values[2].textContent = stats.completed_users;
  }

  function renderRows(items) {
    if (!items.length) {
      body.innerHTML = '<tr><td class="empty" colspan="12">Пользователей пока нет. Как только кто-то нажмет /start, он появится здесь.</td></tr>';
      return;
    }
    body.innerHTML = items.map((user) => {
      const username = user.username
        ? `<a href="https://t.me/${escapeHtml(user.username)}" target="_blank" rel="noreferrer">@${escapeHtml(user.username)}</a>`
        : '<span class="muted">-</span>';
      const status = labels[user.application_status] || user.application_status || "Новый";
      const statusClass = badgeClasses[user.application_status] || "status-muted";
      return `<tr>
        <td><code>${user.telegram_id}</code></td>
        <td>${username}</td>
        <td>${escapeHtml(fullName(user)) || '<span class="muted">-</span>'}</td>
        <td><span class="status ${statusClass}">${escapeHtml(status)}</span></td>
        <td>${user.is_application_completed ? "Да" : "Нет"}</td>
        <td>${format(user.current_step)}</td>
        <td>${format(user.source)}</td>
        <td>${user.reminder_count || 0}</td>
        <td>${format(user.first_seen_at)}</td>
        <td>${format(user.last_seen_at)}</td>
        <td class="long">${format(user.last_message_text)}</td>
        <td>
          <button type="button" data-action="open" data-id="${user.telegram_id}">Открыть</button>
          <button type="button" data-action="copy-id" data-id="${user.telegram_id}">ID</button>
          ${user.username ? `<button type="button" data-action="copy-username" data-username="${escapeHtml(user.username)}">@</button>` : ""}
          <button type="button" data-action="contacted" data-id="${user.telegram_id}">Связались</button>
        </td>
      </tr>`;
    }).join("");
  }

  async function openUser(id) {
    const user = await api(`/api/users/${id}`);
    state.selectedUser = user;
    modalTitle.textContent = `Пользователь ${user.telegram_id}`;
    const answers = user.answers || {};
    const answersHtml = Object.keys(answers).length
      ? Object.entries(answers).map(([key, val]) => `<div class="answer-row"><b>${escapeHtml(answerLabels[key] || key)}</b><span>${format(val)}</span></div>`).join("")
      : '<div class="muted">Ответов пока нет</div>';
    modalBody.innerHTML = `
      <div class="detail-grid">
        ${detail("Telegram ID", user.telegram_id)}
        ${detail("Username", user.username ? `@${user.username}` : "")}
        ${detail("Имя", fullName(user))}
        ${detail("Язык", user.language_code)}
        ${detail("Телефон", user.phone)}
        ${detail("Источник", user.source)}
        ${detail("Статус", labels[user.application_status] || user.application_status)}
        ${detail("Текущий шаг", user.current_step)}
        ${detail("Первый визит", user.first_seen_at)}
        ${detail("Последний визит", user.last_seen_at)}
        ${detail("Напоминаний", user.reminder_count)}
        ${detail("Последнее напоминание", user.last_reminder_at)}
      </div>
      <h3>Ответы</h3>
      <div class="answers">${answersHtml}</div>
      <label><span class="detail-label">Последнее сообщение</span><textarea id="last-message" rows="2" readonly>${escapeHtml(user.last_message_text || "")}</textarea></label>
      <label><span class="detail-label">Заметки</span><textarea id="notes" rows="4">${escapeHtml(user.notes || "")}</textarea></label>
      <div class="modal-actions">
        <button type="button" data-modal-action="contacted">Связались</button>
        <button type="button" data-modal-action="not_relevant">Не подходит</button>
        <button type="button" data-modal-action="blocked">Заблокировать</button>
        <button type="button" data-modal-action="save-notes">Сохранить заметки</button>
      </div>
    `;
    modal.classList.add("open");
  }

  function detail(label, raw) {
    return `<div><span class="detail-label">${escapeHtml(label)}</span><b>${format(raw)}</b></div>`;
  }

  async function patchUser(id, payload) {
    const user = await api(`/api/users/${id}`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    await loadUsers();
    if (modal.classList.contains("open")) await openUser(user.telegram_id);
  }

  function fullName(user) {
    return [user.first_name, user.last_name].filter(Boolean).join(" ");
  }

  function format(raw) {
    if (raw === null || raw === undefined || raw === "") return '<span class="muted">-</span>';
    if (typeof raw === "object") return escapeHtml(JSON.stringify(raw));
    return escapeHtml(String(raw));
  }

  function escapeHtml(raw) {
    return String(raw).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
  }

  let debounceTimer = null;
  document.querySelectorAll("#search, #source-filter").forEach((field) => {
    field.addEventListener("input", () => {
      window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(loadUsers, 250);
    });
  });
  document.querySelectorAll("#status-filter, #completed-filter").forEach((field) => field.addEventListener("change", loadUsers));
  document.querySelectorAll(".sort-button").forEach((button) => {
    button.addEventListener("click", () => {
      const nextSort = button.dataset.sort;
      state.sortOrder = state.sortBy === nextSort && state.sortOrder === "desc" ? "asc" : "desc";
      state.sortBy = nextSort;
      loadUsers();
    });
  });
  body.addEventListener("click", async (event) => {
    const target = event.target.closest("button");
    if (!target) return;
    if (target.dataset.action === "open") await openUser(target.dataset.id);
    if (target.dataset.action === "copy-id") await navigator.clipboard.writeText(target.dataset.id);
    if (target.dataset.action === "copy-username") await navigator.clipboard.writeText(`@${target.dataset.username}`);
    if (target.dataset.action === "contacted") await patchUser(target.dataset.id, {application_status: "contacted"});
  });
  modalBody.addEventListener("click", async (event) => {
    const target = event.target.closest("button");
    if (!target || !state.selectedUser) return;
    const id = state.selectedUser.telegram_id;
    if (target.dataset.modalAction === "contacted") await patchUser(id, {application_status: "contacted"});
    if (target.dataset.modalAction === "not_relevant") await patchUser(id, {application_status: "not_relevant"});
    if (target.dataset.modalAction === "blocked") await patchUser(id, {is_blocked: true});
    if (target.dataset.modalAction === "save-notes") await patchUser(id, {notes: document.querySelector("#notes").value});
  });
  document.querySelector("#modal-close").addEventListener("click", () => modal.classList.remove("open"));
  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.classList.remove("open");
  });
  loadUsers();
  window.setInterval(loadUsers, 7000);
})();
</script>"""


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
    return f"""
<tr>
  <td><code>{user.user_id}</code></td>
  <td>{username}</td>
  <td>{escape(user.full_name) or '<span class="muted">-</span>'}</td>
  <td><span class="status {status_class}">{escape(user.status)}</span></td>
  <td>{'Да' if user.completed_at else 'Нет'}</td>
  <td>{_format_value(user.current_step)}</td>
  <td><span class="muted">-</span></td>
  <td>{user.reminder_count}</td>
  <td>{_format_value(user.started_at)}</td>
  <td>{_format_value(user.updated_at)}</td>
  <td class="long">{_format_value(user.answers.get('task_description'))}</td>
  <td><button type="button" data-action="open" data-id="{user.user_id}">Открыть</button></td>
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
