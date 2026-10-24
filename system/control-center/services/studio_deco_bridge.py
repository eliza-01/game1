"""Single-operation Studio Bridge request for refreshing placed Location Assets.

Transport only. The Studio DecoManager owns the asset registry and material
refresh; Host Agent never writes placement data or SQLite during sync.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
import uuid

from studio_bridge import PORT, PROJECT, TOKEN, StudioBridgeError


def run_deco_refresh_bridge(*, timeout_seconds: float = 75.0,
                            slug: str = '', binding_revision: int | None = None) -> dict:
    operation_id = uuid.uuid4().hex
    command = {
        "project": PROJECT,
        "command": "deco-refresh",
        "schemaVersion": 1,
        "operationId": operation_id,
    }
    if slug:
        if not isinstance(binding_revision, int) or binding_revision < 1:
            raise ValueError('targeted deco refresh needs binding revision')
        command.update(schemaVersion=2, targetSlug=slug, bindingRevision=binding_revision)
    state = {"claimed": False, "result": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def send_json(self, status: int, data: dict) -> None:
            encoded = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def authorized(self) -> bool:
            return self.headers.get("X-Game1-Token") == TOKEN

        def do_GET(self):
            if not self.authorized():
                return self.send_json(403, {"error": "forbidden"})
            if self.path != "/command":
                return self.send_json(404, {"error": "not found"})
            if state["claimed"]:
                return self.send_json(409, {"error": "already claimed"})
            state["claimed"] = True
            self.send_json(200, command)

        def do_POST(self):
            if not self.authorized():
                return self.send_json(403, {"error": "forbidden"})
            if self.path != "/deco-refresh-result":
                return self.send_json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 8192:
                    raise ValueError("invalid result payload length")
                incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                if (not isinstance(incoming, dict)
                        or incoming.get("project") != PROJECT
                        or incoming.get("command") != "deco-refresh"
                        or incoming.get("schemaVersion") != command["schemaVersion"]
                        or incoming.get("operationId") != operation_id
                        or (slug and (incoming.get("targetSlug") != slug
                                      or incoming.get("bindingRevision") != binding_revision))):
                    raise ValueError("invalid deco-refresh result identity")
                if not state["claimed"]:
                    raise ValueError("command has not been claimed")
                if state["result"] is not None:
                    raise ValueError("result already submitted")
                state["result"] = incoming
                self.send_json(200, {"ok": True})
            except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})

    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        raise StudioBridgeError(f"studio bridge port {PORT} is unavailable: {exc}") from exc
    server.timeout = 0.25
    try:
        started = time.monotonic()
        deadline = started + max(1.0, float(timeout_seconds))
        while state["result"] is None and time.monotonic() < deadline:
            server.handle_request()
            if not state["claimed"] and time.monotonic() - started >= 8.0:
                break
    finally:
        server.server_close()
    if state["result"] is None:
        raise StudioBridgeError(
            "Studio did not complete Location Assets sync; ensure Studio is open, "
            "Game1Bridge M118 is installed, Studio is not in Play mode, "
            "and HTTP Requests are enabled"
        )
    result = state["result"]
    if result.get("error"):
        raise StudioBridgeError(f"DecoManager refresh failed: {result['error']}")
    values = {}
    for field in ("models", "parts", "registryItems"):
        value = result.get(field)
        if type(value) is not int or value < 0:
            raise StudioBridgeError(f"invalid Studio deco-refresh result field: {field}")
        values[field] = value
    if slug:
        values.update(targetSlug=slug, bindingRevision=binding_revision,
                      matchedModels=int(result.get('matchedModels', 0)))
    return values
