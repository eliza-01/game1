from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_store import CharacterStore

control_agent_build = "game1-m2-characters-001"
root = Path(__file__).resolve().parents[2]
port = int(os.environ.get("CONTROL_AGENT_PORT", "43821"))
token = os.environ.get("CONTROL_TOKEN", "Game1LocalControlV1")
store = CharacterStore(root)


class Handler(BaseHTTPRequestHandler):
    def out(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        return self.headers.get("X-Control-Token") == token

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        if self.path == "/api/agent/info":
            return self.out(
                200,
                {
                    "build": control_agent_build,
                    "project": "game1",
                    "projectRoot": str(root),
                    "db": str(store.db),
                },
            )
        if self.path == "/api/characters":
            return self.out(200, store.snapshot())
        return self.out(404, {"error": "not found"})

    def do_POST(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        if self.path == "/api/characters":
            try:
                return self.out(200, store.put(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        prefix = "/api/characters/"
        suffix = "/activate"
        if self.path.startswith(prefix) and self.path.endswith(suffix):
            character_id = self.path[len(prefix) : -len(suffix)].strip("/")
            try:
                return self.out(200, store.set_active(character_id))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if self.path == "/api/characters/active/clear":
            return self.out(200, store.clear_active())
        return self.out(404, {"error": "not found"})

    def do_DELETE(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        prefix = "/api/characters/"
        if self.path.startswith(prefix):
            store.delete(self.path[len(prefix) :])
            return self.out(200, {"ok": True})
        return self.out(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print("[host-agent]", fmt % args)


if __name__ == "__main__":
    print(f"[game1] control agent http://127.0.0.1:{port} · {root}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
