from __future__ import annotations

import argparse
import base64
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.crm import load_crm_users, render_crm_debug_html, render_crm_html
from app.storage import initialize_database


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
    args = parser.parse_args()

    server = create_crm_server(
        args.database,
        args.host,
        args.port,
        username=args.username,
        password=args.password,
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
) -> ThreadingHTTPServer:
    initialize_database(database_path)
    handler_class = make_handler(database_path, username=username, password=password)
    return ThreadingHTTPServer((host, port), handler_class)


def start_crm_server(
    database_path: str,
    host: str,
    port: int,
    *,
    username: str = "",
    password: str = "",
) -> ThreadingHTTPServer:
    server = create_crm_server(
        database_path,
        host,
        port,
        username=username,
        password=password,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def make_handler(
    database_path: str,
    *,
    username: str = "",
    password: str = "",
) -> type[BaseHTTPRequestHandler]:
    class CrmRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not is_authorized(self.headers.get("Authorization"), username, password):
                self._request_auth()
                return

            path = urlparse(self.path).path
            if path in {"", "/"}:
                self._send_html(render_crm_html(load_crm_users(database_path), database_path))
                return
            if path == "/debug":
                self._send_html(render_crm_debug_html(database_path))
                return
            if path == "/health":
                self._send_text("ok")
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_text(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _request_auth(self) -> None:
            payload = b"Authentication required"
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="B2Bots CRM"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return CrmRequestHandler


def is_authorized(header: str | None, username: str, password: str) -> bool:
    if not username or not password:
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header.removeprefix("Basic ").strip()).decode("utf-8")
    except Exception:
        return False
    expected = f"{username}:{password}"
    return decoded == expected


if __name__ == "__main__":
    main()
