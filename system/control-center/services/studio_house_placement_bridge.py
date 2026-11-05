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


def _request_house_placement(house_slug: str, plot_index: int, *, action: str,
                             placement: dict | None = None, anchored: bool | None = None,
                             targets: list[dict] | None = None, timeout_seconds: float = 30.0) -> dict:
    if action not in ('capture', 'place', 'clear', 'anchors', 'place_all', 'clear_all'):
        raise ValueError('unknown house placement action')
    operation_id = uuid.uuid4().hex
    command = {'command': 'house-placement-capture-v2' if action == 'capture' else 'house-placement-preview-v4',
               'schemaVersion': 2 if action == 'capture' else 4,
               'project': PROJECT, 'operationId': operation_id,
               'houseSlug': house_slug, 'plotIndex': plot_index}
    if action != 'capture':
        command['action'] = action
        if placement is not None:
            command['placement'] = placement
        if action in ('anchors', 'place_all', 'clear_all'):
            if not isinstance(targets, list) or len(targets) > 250:
                raise ValueError('invalid batch targets')
            command['targets'] = targets
        if action == 'anchors':
            if type(anchored) is not bool:
                raise ValueError('invalid anchor command')
            command['anchored'] = anchored
    identity = {key: command[key] for key in ('command', 'schemaVersion', 'project', 'operationId',
                                                'houseSlug', 'plotIndex')}
    if action != 'capture':
        identity['action'] = action
    if action == 'anchors':
        identity['anchored'] = anchored
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
                        or any(result.get(key) != val for key, val in identity.items())):
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
            if claimed_at is not None and time.monotonic() - claimed_at >= (70 if action in ('anchors', 'place_all', 'clear_all') else 12):
                break
    finally:
        server.server_close()
    if state['result'] is None:
        raise StudioBridgeError('Studio did not complete house placement ' + action +
                                ': check Edit mode, installed Game1Bridge, and the Studio Output')
    if state['result'].get('error'):
        raise StudioBridgeError(str(state['result']['error']))
    return state['result']


def capture_house_placement(house_slug: str, plot_index: int, *, timeout_seconds: float = 30.0) -> dict:
    return _request_house_placement(house_slug, plot_index, action='capture', timeout_seconds=timeout_seconds)


def preview_house_placement(house_slug: str, plot_index: int, action: str,
                            placement: dict | None = None, *, timeout_seconds: float = 30.0) -> dict:
    if action == 'place' and not isinstance(placement, dict):
        raise ValueError('a saved house-to-plot binding is required before Place')
    if action == 'place' and type(placement.get('anchored')) is not bool:
        raise ValueError('saved binding must have an explicit anchored boolean')
    # M208 bindings contain valid plot-relative transforms but no measured
    # house MeshPart anchor. They are supported via the original Model-pivot
    # placement mode, not silently upgraded to M229's exact house-pivot mode.
    if action == 'place' and placement.get('houseAnchorLocalCFrame') is not None and (
            not isinstance(placement['houseAnchorLocalCFrame'], list)
            or len(placement['houseAnchorLocalCFrame']) != 12):
        raise ValueError('invalid saved house-anchor CFrame')
    result = _request_house_placement(house_slug, plot_index, action=action,
                                      placement=placement, timeout_seconds=timeout_seconds)
    # A stale plugin must never return an apparently successful Place while
    # silently leaving every part anchored. This is a verified *postcondition*,
    # not just an echoed input field.
    if action == 'place' and (result.get('status') != 'placed'
        or type(result.get('anchored')) is not bool
        or result['anchored'] is not placement['anchored']
        or type(result.get('anchoredPartsVerified')) is not int
        or result['anchoredPartsVerified'] < 1):
        raise StudioBridgeError('Studio did not verify house Anchored state; '
                                'install the latest Game1Bridge plugin and retry on a Place copy')
    return result


def anchor_house_placements(targets: list[dict], anchored: bool, *, timeout_seconds: float = 90.0) -> dict:
    """Single Studio Undo operation for a scoped set of authored previews."""
    if type(anchored) is not bool or not isinstance(targets, list) or len(targets) > 250:
        raise ValueError('invalid anchor request')
    # A dedicated action rides the existing authenticated placement bridge.
    return _request_house_placement('*', 0, action='anchors', targets=targets,
                                    anchored=anchored, timeout_seconds=timeout_seconds)


def bulk_house_placements(house_slug: str | None, action: str,
                          bindings: list[dict] | None = None, *, timeout_seconds: float = 90.0) -> dict:
    """One authenticated Studio command / one Undo recording for the whole batch.

    The HTTP caller cannot supply transforms. All placement data is read from
    the saved Placement Store before this function is called.
    """
    if action == 'place_all':
        if (type(house_slug) is not str or not house_slug or
                any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in house_slug)):
            raise ValueError('invalid registered house slug')
        if not isinstance(bindings, list) or not 1 <= len(bindings) <= 50:
            raise ValueError('Place all requires 1–50 saved bindings')
        targets = []
        seen = set()
        for binding in bindings:
            if not isinstance(binding, dict) or binding.get('houseSlug') != house_slug:
                raise ValueError('inconsistent house binding')
            plot = binding.get('plotIndex')
            if type(plot) is not int or not 1 <= plot <= 50 or plot in seen:
                raise ValueError('duplicate or invalid plot binding')
            if type(binding.get('anchored')) is not bool:
                raise ValueError('binding anchored must be a boolean')
            if not isinstance(binding.get('localCFrame'), list) or len(binding['localCFrame']) != 12:
                raise ValueError('binding is missing relative CFrame')
            if binding.get('houseAnchorLocalCFrame') is not None and (
                    not isinstance(binding['houseAnchorLocalCFrame'], list)
                    or len(binding['houseAnchorLocalCFrame']) != 12):
                raise ValueError('invalid saved house-anchor CFrame')
            seen.add(plot)
            targets.append(binding)
        targets.sort(key=lambda binding: binding['plotIndex'])
        slug = house_slug
    elif action == 'clear_all':
        if bindings is not None:
            raise ValueError('Clear all does not accept browser-supplied targets')
        targets = []
        slug = '*'
    else:
        raise ValueError('invalid house placement batch action')
    result = _request_house_placement(slug, 0, action=action, targets=targets,
                                      timeout_seconds=timeout_seconds)
    expected = 'placed_all' if action == 'place_all' else 'cleared_all'
    if (result.get('status') != expected or type(result.get('changed')) is not int
            or result['changed'] < 0 or (action == 'place_all' and
            (result['changed'] != len(targets) or
             type(result.get('anchoredPartsVerified')) is not int or
             result['anchoredPartsVerified'] < len(targets)))):
        raise StudioBridgeError('Studio did not verify the full house placement batch; '
                                'reinstall Game1Bridge and inspect the test Place')
    return result
