from __future__ import annotations

import http.server
import json
import time

PROJECT = "game1"
PORT = 43137
TOKEN = "Game1StudioBridgeV1"


class StudioBridgeError(RuntimeError):
    pass


def run_model_load_bridge(
    asset_id: str,
    destination_folders: list[str],
    *,
    wrapper_name: str,
    placement_mode: str = "character-controller",
    metadata: dict | None = None,
    timeout_seconds: float = 75.0,
) -> dict:
    command = {
        "command": "model-load",
        "schemaVersion": 1,
        "project": PROJECT,
        "assetId": str(asset_id),
        "destinationFolders": [str(part) for part in destination_folders],
        "replaceExisting": True,
        "placementMode": str(placement_mode),
        "wrapperName": str(wrapper_name),
        "metadata": dict(metadata or {}),
    }
    result: dict | None = None
    command_claimed = False
    command_claimed_at: float | None = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args) -> None:
            return

        def _authorized(self) -> bool:
            return self.headers.get("X-Game1-Token") == TOKEN

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            nonlocal command_claimed, command_claimed_at
            if not self._authorized():
                self._json(403, {"ok": False})
                return
            if self.path != "/command":
                self._json(404, {"ok": False})
                return
            if command_claimed:
                self._json(409, {"ok": False, "reason": "command-already-claimed"})
                return
            command_claimed = True
            command_claimed_at = time.monotonic()
            self._json(200, command)

        def do_POST(self) -> None:
            nonlocal result
            if not self._authorized():
                self._json(403, {"ok": False})
                return
            if self.path != "/model-load-result":
                self._json(404, {"ok": False})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                if incoming.get("command") != "model-load" or incoming.get("project") != PROJECT:
                    raise ValueError("unexpected studio bridge result identity")
                result = incoming
                self._json(200, {"ok": True})
            except Exception as exc:
                self._json(400, {"ok": False, "error": str(exc)})

    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        raise StudioBridgeError(f"studio bridge port {PORT} is unavailable: {exc}") from exc

    server.timeout = 0.25
    started_at = time.monotonic()
    deadline = started_at + max(0.01, float(timeout_seconds))
    try:
        while result is None and time.monotonic() < deadline:
            server.handle_request()
            now = time.monotonic()
            if command_claimed_at is None and now - started_at >= 8.0:
                break
            if command_claimed_at is not None and now - command_claimed_at >= 60.0:
                break
    finally:
        server.server_close()

    if result is None:
        if command_claimed:
            raise StudioBridgeError(
                "the game1 studio plugin accepted the model load command but did not return a result; check studio output"
            )
        raise StudioBridgeError(
            "no model load command was received by the game1 studio plugin; stop play/run, install the updated plugin, and restart studio"
        )
    if result.get("error"):
        raise StudioBridgeError(f"studio model load failed: {result['error']}")
    return result
