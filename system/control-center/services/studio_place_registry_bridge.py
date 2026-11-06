"""One-shot authenticated Studio Bridge transport for Location Place Registry.

No persistence, business rules or filesystem writes in this module.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import time
import uuid

from studio_bridge import PORT, PROJECT, TOKEN, StudioBridgeError


def run_place_registry_bridge(*, catalog: dict, phase: str, scan_token: str = '',
                              keys: list[str] | None = None, undo_operation_id: str = '',
                              timeout_seconds: float = 240) -> dict:
    if phase not in ('scan', 'repair', 'sync', 'select', 'undo'):
        raise ValueError('unknown Place Registry operation')
    if not isinstance(catalog, dict) or catalog.get('domain') != 'location_assets':
        raise ValueError('Place Registry requires Location Assets allowlist')
    if phase not in ('scan', 'undo'):
        if not re.fullmatch(r'[0-9a-fA-F-]{32,36}', scan_token):
            raise ValueError('Scan the Place before applying changes')
        if not isinstance(keys, list) or not 1 <= len(keys) <= 4096 or len(set(keys)) != len(keys) or any(
                not isinstance(key, str) or not re.fullmatch(r'p[1-9][0-9]{0,4}', key) for key in keys):
            raise ValueError('select explicit scanned placement keys')
    if phase == 'undo' and not re.fullmatch(r'[0-9a-f]{32}', undo_operation_id):
        raise ValueError('Unknown Studio recording for Undo')
    operation_id = uuid.uuid4().hex
    command = {'project': PROJECT, 'command': 'location-place-registry',
               'schemaVersion': 1, 'operationId': operation_id, 'phase': phase,
               'catalog': catalog, 'scanToken': scan_token, 'keys': keys or [],
               'undoOperationId': undo_operation_id if phase == 'undo' else ''}
    state = {'claimed': False, 'result': None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def send_json(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
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
            if self.path != '/place-registry-result':
                return self.send_json(404, {'error': 'not found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 1 <= size <= 5 * 1024 * 1024:
                    raise ValueError('invalid Place Registry response size')
                report = json.loads(self.rfile.read(size))
                if (not state['claimed'] or state['result'] is not None or
                    not isinstance(report, dict) or report.get('project') != PROJECT or
                    report.get('command') != command['command'] or
                    report.get('schemaVersion') != 1 or
                    report.get('operationId') != operation_id or
                    report.get('phase') != phase or report.get('catalogDigest') != catalog['digest']):
                    raise ValueError('Place Registry command identity mismatch')
                state['result'] = report
                return self.send_json(200, {'ok': True})
            except (ValueError, UnicodeError, json.JSONDecodeError) as err:
                return self.send_json(400, {'error': str(err)})

    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as err:
        raise StudioBridgeError(f'Studio Bridge port {PORT} unavailable: {err}') from err
    server.timeout = 0.25
    try:
        started = time.monotonic()
        while state['result'] is None and time.monotonic() - started < timeout_seconds:
            server.handle_request()
            if not state['claimed'] and time.monotonic() - started > 9:
                break
    finally:
        server.server_close()
    if state['result'] is None:
        raise StudioBridgeError('Studio did not complete Place Registry operation; '
                                'open Studio Edit mode, install the latest Game1Bridge, enable HTTP Requests')
    result = state['result']
    if result.get('error'):
        raise StudioBridgeError(str(result['error'])[:700])
    return result
