"""One-shot, authenticated Studio Edit-mode capture of a selected house model.

The Host Agent never infers Studio selection or writes a binding on timeout.
Only a matching command identity may return a capture to the authoring service.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
import uuid

from studio_bridge import PORT, PROJECT, TOKEN, StudioBridgeError


def capture_house_placement(house_slug: str, plot_index: int, *, timeout_seconds: float = 30.0) -> dict:
    operation_id = uuid.uuid4().hex
    command = {'command': 'house-placement-capture', 'schemaVersion': 1,
               'project': PROJECT, 'operationId': operation_id,
               'houseSlug': house_slug, 'plotIndex': plot_index}
    state = {'claimed': False, 'result': None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def respond(self, code: int, data: dict):
            encoded = json.dumps(data).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def authorized(self):
            return self.headers.get('X-Game1-Token') == TOKEN

        def do_GET(self):
            if not self.authorized():
                return self.respond(403, {'error': 'forbidden'})
            if self.path != '/command':
                return self.respond(404, {'error': 'not found'})
            if state['claimed']:
                return self.respond(409, {'error': 'command already claimed'})
            state['claimed'] = True
            self.respond(200, command)

        def do_POST(self):
            if not self.authorized():
                return self.respond(403, {'error': 'forbidden'})
            if self.path != '/house-placement-result':
                return self.respond(404, {'error': 'not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 8192:
                    raise ValueError('invalid payload size')
                result = json.loads(self.rfile.read(length).decode('utf-8'))
                if (not state['claimed'] or state['result'] is not None or not isinstance(result, dict)
                        or any(result.get(key) != val for key, val in command.items())):
                    raise ValueError('unexpected or stale Studio capture')
                state['result'] = result
                return self.respond(200, {'ok': True})
            except (ValueError, UnicodeError) as exc:
                return self.respond(400, {'error': str(exc)})

    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as exc:
        raise StudioBridgeError(f'Studio bridge port {PORT} is busy; retry after the other Studio task') from exc
    server.timeout = 0.25
    started = time.monotonic()
    claimed_at = None
    try:
        while state['result'] is None and time.monotonic() - started < timeout_seconds:
            server.handle_request()
            if state['claimed'] and claimed_at is None:
                claimed_at = time.monotonic()
            if not state['claimed'] and time.monotonic() - started >= 8:
                break
            if claimed_at is not None and time.monotonic() - claimed_at >= 12:
                break
    finally:
        server.server_close()
    if state['result'] is None:
        raise StudioBridgeError('Studio did not return a placement: select the named Model '
                                'in Workspace, leave Play mode, and ensure Game1Bridge is installed')
    if state['result'].get('error'):
        raise StudioBridgeError(str(state['result']['error']))
    return state['result']
