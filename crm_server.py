from __future__ import annotations

import argparse
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.crm import load_crm_users, render_crm_html
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
    args = parser.parse_args()

    initialize_database(args.database)
    handler_class = make_handler(args.database)
    server = ThreadingHTTPServer((args.host, args.port), handler_class)
    print(f"CRM is running at http://{args.host}:{args.port}")
    print(f"Database: {args.database}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCRM stopped")
    finally:
        server.server_close()


def make_handler(database_path: str) -> type[BaseHTTPRequestHandler]:
    class CrmRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"", "/"}:
                self._send_html(render_crm_html(load_crm_users(database_path), database_path))
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

    return CrmRequestHandler


if __name__ == "__main__":
    main()
