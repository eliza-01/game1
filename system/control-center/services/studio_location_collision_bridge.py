"""One-shot Studio Edit-mode transport for explicitly selected Location collision authoring.

The command/result pair is tied to an opaque operation ID and asset slug.
This transport never writes SQLite or scans the user's Workspace.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
import uuid

from studio_bridge import PORT, PROJECT, TOKEN, StudioBridgeError


COMMAND = 'location-collision-authoring-v1'
PHASES = frozenset({'validate', 'capture', 'preview', 'clear-preview'})


def run_location_collision_bridge(*, slug: str, phase: str, expected_revision: int,
                                  blueprint: dict | None = None,
                                  expected_versions: list[dict] | None = None,
                                  timeout_seconds: float = 35.0) -> dict:
    if phase not in PHASES or not isinstance(slug, str) or not slug or type(expected_revision) is not int:
        raise ValueError('invalid Location Collision Studio request')
    if phase == 'preview' and not isinstance(blueprint, dict):
        raise ValueError('Preview requires a saved Collision Blueprint')
    if phase != 'preview' and blueprint is not None:
        raise ValueError('Only Preview may carry a saved Collision Blueprint')
    if phase != 'clear-preview' and (not isinstance(expected_versions, list) or not expected_versions):
        raise ValueError('Published visual Mesh ID inventory required for Collision Capture')
    if phase == 'clear-preview' and expected_versions is not None:
        raise ValueError('Clear Preview must not carry selected-model identities')
    operation_id = uuid.uuid4().hex
    command = {'project': PROJECT, 'command': COMMAND, 'schemaVersion': 1,
               'operationId': operation_id, 'slug': slug, 'phase': phase,
               'expectedRevision': expected_revision}
    if blueprint is not None:
        command['blueprint'] = blueprint
    if expected_versions is not None:
        command['expectedVersions'] = expected_versions
    identity = {key: command[key] for key in
                ('project', 'command', 'schemaVersion', 'operationId', 'slug', 'phase', 'expectedRevision')}
    state = {'claimed': False, 'result': None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def send_json(self, code: int, payload: dict):
            data = json.dumps(payload).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            return self.headers.get('X-Game1-Token') == TOKEN

        def do_GET(self):
            if not self.authorized():
                return self.send_json(403, {'error': 'forbidden'})
            if self.path != '/command':
                return self.send_json(404, {'error': 'not found'})
            if state['claimed']:
                return self.send_json(409, {'error': 'already claimed'})
            state['claimed'] = True
            return self.send_json(200, command)

        def do_POST(self):
            if not self.authorized():
                return self.send_json(403, {'error': 'forbidden'})
            if self.path != '/location-collision-result':
                return self.send_json(404, {'error': 'not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 400_000:
                    raise ValueError('invalid Collision Capture result size')
                response = json.loads(self.rfile.read(length).decode('utf-8'))
                if (not state['claimed'] or state['result'] is not None
                        or not isinstance(response, dict)
                        or any(response.get(key) != expected for key, expected in identity.items())):
                    raise ValueError('stale or mismatched Collision Capture response')
                state['result'] = response
                return self.send_json(200, {'ok': True})
            except (UnicodeError, ValueError, TypeError) as error:
                return self.send_json(400, {'error': str(error)})

    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as error:
        raise StudioBridgeError(f'Studio Bridge port {PORT} busy; wait for current Studio operation') from error
    server.timeout = 0.25
    try:
        started = time.monotonic()
        claimed_at = None
        while state['result'] is None and time.monotonic() - started < timeout_seconds:
            server.handle_request()
            if state['claimed'] and claimed_at is None:
                claimed_at = time.monotonic()
            if not state['claimed'] and time.monotonic() - started >= 10:
                break
            if claimed_at is not None and time.monotonic() - claimed_at >= 20:
                break
    finally:
        server.server_close()
    if state['result'] is None:
        raise StudioBridgeError('Studio did not return Collision Authoring result; '
                                'check Edit mode, Game1Bridge version and Studio Output')
    if state['result'].get('error'):
        raise StudioBridgeError(str(state['result']['error'])[:800])
    return state['result']
