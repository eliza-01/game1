from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from static_paths import resolve_static_file
import json
import mimetypes
import os

AGENT = os.environ.get("CONTROL_AGENT_URL", "http://host.docker.internal:43821")
TOKEN = os.environ.get("CONTROL_TOKEN", "Game1LocalControlV1")
STATIC = Path(__file__).resolve().parent / "static"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.proxy()
        path = resolve_static_file(STATIC, self.path)
        if path is None:
            self.send_error(404)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        # Local editor UI must never reuse scripts from a previous Docker image.
        # The container is rebuilt by control-center.ps1 after source updates.
        if path.suffix.lower() in {".html", ".css", ".js"}:
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.proxy()

    def do_DELETE(self):
        self.proxy()

    def proxy(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))) if self.command in ("POST", "PUT", "PATCH") else None
        req = Request(
            AGENT + self.path,
            data=body,
            method=self.command,
            headers={"X-Control-Token": TOKEN, "Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=190) as response:
                data = response.read()
                status = response.status
        except HTTPError as error:
            data = error.read()
            status = error.code
        except Exception as error:
            data = json.dumps({"error": str(error)}).encode()
            status = 502
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("WEB_PORT", "8080"))), Handler).serve_forever()
