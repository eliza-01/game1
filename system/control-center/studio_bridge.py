from __future__ import annotations

import http.server
import json
import re
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


def run_monster_spawn_bridge(
    action: str,
    *,
    operation_id: str,
    spawn_id: str = "",
    monster_slug: str = "",
    monster_name: str = "",
    map_key: str = "main",
    place_id: int = 0,
    position: dict | None = None,
    yaw_degrees: float = 0,
    spawn_radius: float = 0,
    max_alive: int = 1,
    enabled: bool = True,
    records: list[dict] | None = None,
    timeout_seconds: float = 45.0,
) -> dict:
    command = {
        "command": "monster-spawn",
        "schemaVersion": 1,
        "project": PROJECT,
        "action": str(action),
        "operationId": str(operation_id),
        "spawnId": str(spawn_id),
        "monsterSlug": str(monster_slug),
        "monsterName": str(monster_name),
        "mapKey": str(map_key),
        "placeId": int(place_id or 0),
        "position": position,
        "yawDegrees": float(yaw_degrees or 0),
        "spawnRadius": float(spawn_radius or 0),
        "maxAlive": int(max_alive or 1),
        "enabled": bool(enabled),
        "records": list(records or []),
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
            if self.path != "/monster-spawn-result":
                self._json(404, {"ok": False})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                if incoming.get("command") != "monster-spawn" or incoming.get("project") != PROJECT:
                    raise ValueError("unexpected monster spawn bridge result identity")
                if str(incoming.get("operationId") or "") != str(operation_id):
                    raise ValueError("unexpected monster spawn operation id")
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
            if command_claimed_at is not None and now - command_claimed_at >= max(10.0, float(timeout_seconds) - 1):
                break
    finally:
        server.server_close()

    if result is None:
        if command_claimed:
            raise StudioBridgeError("the game1 Studio plugin accepted the Monster Spawn command but did not return a result")
        raise StudioBridgeError("no Monster Spawn command was received; install the updated Game1Bridge plugin and restart Studio")
    if result.get("error"):
        raise StudioBridgeError(f"Studio Monster Spawn command failed: {result['error']}")
    return result


def run_timeline_editor_bridge(session: dict, event_catalog: list[dict], timeout_seconds: float = 75.0) -> dict:
    command = {
        "command": "timeline-editor",
        "schemaVersion": 1,
        "project": PROJECT,
        "sessionId": str(session.get("sessionId") or ""),
        "subjectType": str(session.get("subjectType") or ""),
        "subjectId": str(session.get("subjectId") or ""),
        "subjectName": str(session.get("subjectName") or ""),
        "clipId": str(session.get("clipId") or ""),
        "clipName": str(session.get("clipName") or ""),
        "modelAssetId": str(session.get("modelAssetId") or ""),
        "animationAssetId": str(session.get("animationAssetId") or ""),
        "duration": float(session.get("duration") or 0),
        "events": dict(session.get("events") or {}),
        "eventCatalog": list(event_catalog or []),
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
            if self.path != "/timeline-editor-result":
                self._json(404, {"ok": False})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                if incoming.get("command") != "timeline-editor" or incoming.get("project") != PROJECT:
                    raise ValueError("unexpected timeline editor result identity")
                if str(incoming.get("sessionId") or "") != str(command["sessionId"]):
                    raise ValueError("unexpected timeline editor session id")
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
            raise StudioBridgeError("the game1 Studio plugin accepted the timeline editor command but did not finish opening it")
        raise StudioBridgeError("no timeline editor command was received; install the updated Game1Bridge plugin and restart Studio")
    if result.get("error"):
        raise StudioBridgeError(f"Studio timeline editor failed: {result['error']}")
    return result


def run_location_authoring_bridge(
    action: str,
    *,
    operation_id: str,
    location_id: str = "",
    name: str = "",
    place_id: int = 0,
    points: list[dict] | None = None,
    records: list[dict] | None = None,
    timeout_seconds: float = 45.0,
) -> dict:
    """Run one polygon Location authoring operation in Studio Edit mode."""
    action = str(action or "").strip().lower()
    if action not in {"draw", "upsert", "select", "delete", "sync"}:
        raise StudioBridgeError(f"unsupported Location authoring action: {action}")
    operation_id = str(operation_id or "").strip()
    if not operation_id:
        raise StudioBridgeError("Location authoring operation id is required")
    if action != "sync" and not re.fullmatch(r"location-[a-z0-9-]{12,64}", str(location_id or "")):
        raise StudioBridgeError("Location authoring location id is invalid")

    command = {
        "command": "location-authoring",
        "schemaVersion": 1,
        "project": PROJECT,
        "action": action,
        "operationId": operation_id,
        "locationId": str(location_id or ""),
        "name": str(name or ""),
        "placeId": int(place_id or 0),
        "points": points if isinstance(points, list) else [],
        "records": records if isinstance(records, list) else [],
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
            if self.path != "/location-authoring-result":
                self._json(404, {"ok": False})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                if incoming.get("command") != "location-authoring" or incoming.get("project") != PROJECT:
                    raise ValueError("unexpected Location authoring bridge result identity")
                if str(incoming.get("operationId") or "") != operation_id:
                    raise ValueError("unexpected Location authoring operation id")
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
            if command_claimed_at is not None and now - command_claimed_at >= max(10.0, float(timeout_seconds) - 1):
                break
    finally:
        server.server_close()

    if result is None:
        if command_claimed:
            raise StudioBridgeError("the game1 Studio plugin accepted the Location command but did not return a result")
        raise StudioBridgeError("no Location command was received; install the updated Game1Bridge plugin and restart Studio")
    if result.get("error"):
        raise StudioBridgeError(f"Studio Location command failed: {result['error']}")
    return result
