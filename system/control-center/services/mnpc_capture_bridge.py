"""Single bounded local Studio Edit request; no filesystem or game mutation."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
import uuid

from studio_bridge import PROJECT, PORT, TOKEN, StudioBridgeError

COMMAND = 'mnpc-capture-v1'
MAX_RESULT_BYTES = 2_000_000


def capture_from_studio(payload, *, timeout_seconds=55, port=PORT):
    if payload.get('includeGeometry') and timeout_seconds == 55:
        timeout_seconds = 110  # bounded offline mesh read; not Runtime
    identity = {key: payload[key] for key in ('kind', 'slug', 'fullFingerprint', 'idleFingerprint', 'expectedRevision')}
    identity.update(project=PROJECT, command=COMMAND, schemaVersion=1, operationId=uuid.uuid4().hex)
    command = {**payload, **identity}
    claimed = False
    result = None

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(4)

        def log_message(self, *_):
            pass

        def send_json(self, code, value):
            data = json.dumps(value, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            nonlocal claimed
            if self.headers.get('X-Game1-Token') != TOKEN:
                return self.send_json(403, {'error': 'forbidden'})
            if self.path != '/command':
                return self.send_json(404, {'error': 'not found'})
            if claimed:
                return self.send_json(409, {'error': 'already claimed'})
            claimed = True
            self.send_json(200, command)

        def do_POST(self):
            nonlocal result
            if self.headers.get('X-Game1-Token') != TOKEN:
                return self.send_json(403, {'error': 'forbidden'})
            if self.path != '/mnpc-capture-result':
                return self.send_json(404, {'error': 'not found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 1 <= size <= MAX_RESULT_BYTES:
                    raise ValueError('MNPC capture result exceeds size limit')
                incoming = json.loads(self.rfile.read(size).decode('utf-8'))
                if not claimed or result is not None or not isinstance(incoming, dict) or any(incoming.get(k) != v for k, v in identity.items()):
                    raise ValueError('Stale or mismatched MNPC capture result')
            except (ValueError, OSError, TypeError) as exc:
                return self.send_json(400, {'error': str(exc)})
            result = incoming
            self.send_json(200, {'ok': True})

    try:
        server = HTTPServer(('127.0.0.1', port), Handler)
    except OSError as exc:
        raise StudioBridgeError(f'Studio Bridge port {port} busy; finish the current Studio operation') from exc
    server.timeout = .25
    start = time.monotonic()
    try:
        while result is None and time.monotonic() - start < timeout_seconds:
            server.handle_request()
            if not claimed and time.monotonic() - start >= 8:
                break
    finally:
        server.server_close()
    if result is None:
        raise StudioBridgeError('MNPC capture did not return; open Studio in Edit mode, sync Rojo and install Game1Bridge')
    if result.get('error'):
        raise StudioBridgeError(str(result['error'])[:1500])
    return result.get('capture')
