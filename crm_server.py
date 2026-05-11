from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import threading
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from xml.sax.saxutils import escape as xml_escape

from app.crm import create_crm_test_user, load_crm_users, render_crm_debug_html, render_crm_html
from app.storage import (
    TrackedUser,
    get_user_by_telegram_id,
    get_user_stats,
    initialize_database,
    list_users,
    patch_user_admin_fields,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_DATABASE_PATH = "bot_data.sqlite3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Local B2Bots CRM")
    parser.add_argument(
        "--host",
        default=os.getenv("CRM_HOST", DEFAULT_HOST),
        help=f"Host to bind. Default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CRM_PORT", str(DEFAULT_PORT))),
        help=f"Port to bind. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH),
        help=f"SQLite database path. Default: {DEFAULT_DATABASE_PATH}",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("CRM_USERNAME", ""),
        help="Optional basic auth username.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("CRM_PASSWORD", ""),
        help="Optional basic auth password.",
    )
    parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_TOKEN", ""),
        help="Optional bearer token for admin API/frontend routes.",
    )
    args = parser.parse_args()

    server = create_crm_server(
        args.database,
        args.host,
        args.port,
        username=args.username,
        password=args.password,
        admin_token=args.admin_token,
    )
    print(f"CRM is running at http://{args.host}:{args.port}")
    print(f"Database: {args.database}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCRM stopped")
    finally:
        server.server_close()


def create_crm_server(
    database_path: str,
    host: str,
    port: int,
    *,
    username: str = "",
    password: str = "",
    admin_token: str = "",
) -> ThreadingHTTPServer:
    initialize_database(database_path)
    handler_class = make_handler(database_path, username=username, password=password, admin_token=admin_token)
    return ThreadingHTTPServer((host, port), handler_class)


def start_crm_server(
    database_path: str,
    host: str,
    port: int,
    *,
    username: str = "",
    password: str = "",
    admin_token: str = "",
) -> ThreadingHTTPServer:
    server = create_crm_server(
        database_path,
        host,
        port,
        username=username,
        password=password,
        admin_token=admin_token,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def make_handler(
    database_path: str,
    *,
    username: str = "",
    password: str = "",
    admin_token: str = "",
) -> type[BaseHTTPRequestHandler]:
    class CrmRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not is_authorized(
                self.headers.get("Authorization"),
                username,
                password,
                admin_token,
                self.headers.get("Cookie"),
            ):
                self._request_auth()
                return

            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query = parse_qs(parsed_url.query)

            if path == "/api/users":
                try:
                    self._send_json(_api_list_users(database_path, query))
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/users/stats":
                self._send_json(get_user_stats(database_path))
                return
            if path == "/api/users/export.csv":
                try:
                    self._send_csv(_api_export_users_csv(database_path, query), "b2bots-users.csv")
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/users/export.tsv":
                try:
                    self._send_table_text(_api_export_users_tsv(database_path, query), "text/tab-separated-values", "b2bots-users.tsv")
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/users/export.xlsx":
                try:
                    self._send_xlsx(_api_export_users_xlsx(database_path, query), "b2bots-users.xlsx")
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/users/export.list.txt":
                try:
                    self._send_table_text(_api_export_users_list(database_path, query), "text/plain", "b2bots-users-list.txt")
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            if path.startswith("/api/users/"):
                telegram_id = _parse_telegram_id(path)
                if telegram_id is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                    return
                user = get_user_by_telegram_id(database_path, telegram_id)
                if user is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "User not found")
                    return
                self._send_json(_tracked_user_to_dict(user, include_parsed_answers=True))
                return

            if path in {"", "/"}:
                self._send_html(render_crm_html(load_crm_users(database_path), database_path))
                return
            if path == "/debug":
                self._send_html(render_crm_debug_html(database_path))
                return
            if path == "/self-test":
                create_crm_test_user(database_path)
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", "/debug")
                self.end_headers()
                return
            if path == "/health":
                self._send_text("ok")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_PATCH(self) -> None:
            if not is_authorized(
                self.headers.get("Authorization"),
                username,
                password,
                admin_token,
                self.headers.get("Cookie"),
            ):
                self._request_auth()
                return

            path = urlparse(self.path).path
            if not path.startswith("/api/users/"):
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

            telegram_id = _parse_telegram_id(path)
            if telegram_id is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

            try:
                payload = self._read_json_body()
                user = patch_user_admin_fields(
                    database_path,
                    telegram_id,
                    application_status=payload.get("application_status"),
                    notes=payload.get("notes"),
                    is_blocked=payload.get("is_blocked"),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            if user is None:
                self.send_error(HTTPStatus.NOT_FOUND, "User not found")
                return
            self._send_json(_tracked_user_to_dict(user, include_parsed_answers=True))

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            if username and password:
                cookie_value = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
                self.send_header("Set-Cookie", f"B2BOTS_CRM_AUTH={cookie_value}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(payload)

        def _send_text(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, body: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_csv(self, body: str, filename: str) -> None:
            payload = body.encode("utf-8-sig")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_table_text(self, body: str, content_type: str, filename: str) -> None:
            payload = body.encode("utf-8-sig")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_xlsx(self, body: bytes, filename: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw_body = self.rfile.read(length).decode("utf-8")
            parsed = json.loads(raw_body)
            if not isinstance(parsed, dict):
                raise ValueError("Request body must be a JSON object")
            return parsed

        def _request_auth(self) -> None:
            payload = b"Authentication required"
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="B2Bots CRM"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return CrmRequestHandler


def is_authorized(
    header: str | None,
    username: str,
    password: str,
    admin_token: str = "",
    cookie_header: str | None = None,
) -> bool:
    if admin_token and header == f"Bearer {admin_token}":
        return True
    if not username or not password:
        return not admin_token
    expected = f"{username}:{password}"
    expected_cookie = base64.b64encode(expected.encode("utf-8")).decode("ascii")
    if cookie_header and f"B2BOTS_CRM_AUTH={expected_cookie}" in cookie_header:
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.removeprefix("Basic ").strip()).decode("utf-8")
    except Exception:
        return False
    return decoded == expected


def _api_list_users(database_path: str, query: dict[str, list[str]]) -> dict[str, object]:
    result = list_users(
        database_path,
        search=_query_value(query, "search"),
        status=_query_value(query, "status"),
        completed=_query_bool(query, "completed"),
        source=_query_value(query, "source"),
        sort_by=_query_value(query, "sort_by") or "last_seen_at",
        sort_order=_query_value(query, "sort_order") or "desc",
        limit=_query_int(query, "limit", 50),
        offset=_query_int(query, "offset", 0),
    )
    return {
        "items": [_tracked_user_to_dict(user) for user in result.items],
        "total": result.total,
        "limit": result.limit,
        "offset": result.offset,
    }


def _api_export_users_csv(database_path: str, query: dict[str, list[str]]) -> str:
    rows = _export_user_rows(database_path, query)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _api_export_users_tsv(database_path: str, query: dict[str, list[str]]) -> str:
    rows = _export_user_rows(database_path, query)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _api_export_users_list(database_path: str, query: dict[str, list[str]]) -> str:
    rows = _export_user_rows(database_path, query)
    lines = []
    for row in rows:
        telegram_id = row["telegram_id"]
        name = " ".join(str(row[key]).strip() for key in ("first_name", "last_name") if str(row[key]).strip())
        display_name = name or "-"
        username = str(row["username"]).strip()
        if username:
            lines.append(f"{telegram_id} | {display_name} | @{username} | {row['telegram_url']}")
        else:
            lines.append(f"{telegram_id} | {display_name} | username отсутствует")
    return "\n".join(lines) + ("\n" if lines else "")


def _api_export_users_xlsx(database_path: str, query: dict[str, list[str]]) -> bytes:
    rows = _export_user_rows(database_path, query)
    table = [EXPORT_COLUMNS, *[[row[column] for column in EXPORT_COLUMNS] for row in rows]]
    sheet_xml = _build_xlsx_sheet(table)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _xlsx_content_types())
        archive.writestr("_rels/.rels", _xlsx_root_rels())
        archive.writestr("xl/workbook.xml", _xlsx_workbook())
        archive.writestr("xl/_rels/workbook.xml.rels", _xlsx_workbook_rels())
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


EXPORT_COLUMNS = [
    "telegram_id",
    "username",
    "telegram_url",
    "first_name",
    "last_name",
    "phone",
    "source",
    "application_status",
    "is_application_completed",
    "current_step",
    "reminder_count",
    "first_seen_at",
    "last_seen_at",
    "last_message_text",
    "notes",
    "answers_json",
]


def _export_user_rows(database_path: str, query: dict[str, list[str]]) -> list[dict[str, object]]:
    result = list_users(
        database_path,
        search=_query_value(query, "search"),
        status=_query_value(query, "status"),
        completed=_query_bool(query, "completed"),
        source=_query_value(query, "source"),
        sort_by=_query_value(query, "sort_by") or "last_seen_at",
        sort_order=_query_value(query, "sort_order") or "desc",
        limit=500,
        offset=0,
    )
    return [
        {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "telegram_url": _telegram_url(user.username),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "source": user.source,
            "application_status": user.application_status,
            "is_application_completed": user.is_application_completed,
            "current_step": user.current_step,
            "reminder_count": user.reminder_count,
            "first_seen_at": user.first_seen_at,
            "last_seen_at": user.last_seen_at,
            "last_message_text": user.last_message_text,
            "notes": user.notes,
            "answers_json": user.answers_json,
        }
        for user in result.items
    ]


def _telegram_url(username: str) -> str:
    clean_username = username.strip().lstrip("@")
    return f"https://t.me/{clean_username}" if clean_username else ""


def _build_xlsx_sheet(rows: list[list[object]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_xlsx_column_name(column_index)}{row_index}"
            text = xml_escape("" if value is None else str(value))
            cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{text}</t></is></c>')
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        f'{"".join(row_xml)}'
        '</sheetData>'
        '</worksheet>'
    )


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""


def _xlsx_root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _xlsx_workbook() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Users" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""


def _xlsx_workbook_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""


def _tracked_user_to_dict(user: TrackedUser, *, include_parsed_answers: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "phone": user.phone,
        "source": user.source,
        "first_seen_at": user.first_seen_at,
        "last_seen_at": user.last_seen_at,
        "last_message_text": user.last_message_text,
        "current_step": user.current_step,
        "application_status": user.application_status,
        "is_application_completed": user.is_application_completed,
        "answers_json": user.answers_json,
        "reminder_count": user.reminder_count,
        "last_reminder_at": user.last_reminder_at,
        "is_blocked": user.is_blocked,
        "notes": user.notes,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
    if include_parsed_answers:
        payload["answers"] = user.answers
    return payload


def _parse_telegram_id(path: str) -> int | None:
    raw_id = path.removeprefix("/api/users/").strip("/")
    if not raw_id or "/" in raw_id:
        return None
    try:
        return int(raw_id)
    except ValueError:
        return None


def _query_value(query: dict[str, list[str]], key: str) -> str | None:
    value = query.get(key, [""])[0].strip()
    return value or None


def _query_bool(query: dict[str, list[str]], key: str) -> bool | None:
    value = _query_value(query, key)
    if value is None:
        return None
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {key}: {value}")


def _query_int(query: dict[str, list[str]], key: str, default: int) -> int:
    value = _query_value(query, key)
    if value is None:
        return default
    return int(value)


if __name__ == "__main__":
    main()
