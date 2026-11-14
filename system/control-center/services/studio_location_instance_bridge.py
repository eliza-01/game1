"""Authenticated one-shot transport for Location Instance Manager commands."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from studio_bridge import PORT, PROJECT, TOKEN, StudioBridgeError
import json
import re
import time
import uuid


_SLUG = re.compile(r'[a-z0-9][a-z0-9_]{0,63}\Z')
_GUID = re.compile(r'[0-9a-fA-F-]{36}\Z')


def run_location_instance_bridge(*, catalog: dict, phase: str, source_slug: str,
                                 target_slug: str, scope: str, scan_token: str = '',
                                 anchor_id: str = 'model',
                                 timeout_seconds: float = 300.0) -> dict:
    if (not isinstance(catalog, dict) or catalog.get('domain') != 'location_assets'
        or catalog.get('schemaVersion') != 1 or not isinstance(catalog.get('digest'), str)
        or not _SLUG.fullmatch(source_slug) or not _SLUG.fullmatch(target_slug)
        or source_slug == target_slug or scope not in ('selected', 'all')
        or phase not in ('preview', 'replace') or not isinstance(anchor_id, str)
        or not (anchor_id == 'model' or (re.fullmatch(r'mesh:[1-9][0-9]{0,6}',anchor_id) is not None))):
        raise ValueError('Invalid Location Instance Manager scope/catalog')
    if phase == 'replace' and not _GUID.fullmatch(scan_token):
        raise ValueError('Preview token required')
    if phase == 'preview' and anchor_id != 'model':
        raise ValueError('Preview must start with the target Model pivot option')
    if phase == 'preview' and scan_token:
        raise ValueError('Unexpected Preview token')
    slugs = {row['slug'] for row in catalog['items']}
    if source_slug not in slugs or target_slug not in slugs:
        raise ValueError('Source and target must be published Location Assets')
    operation_id = uuid.uuid4().hex
    command = dict(project=PROJECT, command='location-instance-replace-v4', schemaVersion=4,
                   operationId=operation_id, catalog=catalog, phase=phase,
                   sourceSlug=source_slug, targetSlug=target_slug, scope=scope,
                   scanToken=scan_token, anchorId=anchor_id)
    state = {'claimed': False, 'result': None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def send_json(self, code, value):
            data = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
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
                return self.send_json(409, {'error': 'claimed'})
            state['claimed'] = True
            return self.send_json(200, command)

        def do_POST(self):
            if not self.authorized():
                return self.send_json(403, {'error': 'forbidden'})
            if self.path != '/location-instance-result':
                return self.send_json(404, {'error': 'not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 1_500_000:
                    raise ValueError('Invalid Studio response size')
                result = json.loads(self.rfile.read(length).decode('utf-8'))
                if (not state['claimed'] or state['result'] is not None or not isinstance(result, dict)
                    or any(result.get(key) != command[key] for key in
                           ('project', 'command', 'schemaVersion', 'operationId', 'phase',
                            'sourceSlug', 'targetSlug', 'scope', 'anchorId'))
                    or result.get('catalogDigest') != catalog['digest']):
                    raise ValueError('Stale or mismatched Instance Manager response')
                state['result'] = result
                self.send_json(200, {'ok': True})
            except (ValueError, UnicodeError, TypeError) as error:
                self.send_json(400, {'error': str(error)})

    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as error:
        raise StudioBridgeError(f'Studio Bridge port {PORT} is busy: {error}') from error
    server.timeout = 0.25
    try:
        started = time.monotonic()
        while state['result'] is None and time.monotonic() - started < timeout_seconds:
            server.handle_request()
            if not state['claimed'] and time.monotonic() - started >= 10:
                break
    finally:
        server.server_close()
    result = state['result']
    if result is None:
        raise StudioBridgeError('Studio did not complete Instance Manager request; check Game1Bridge Output/Edit mode')
    if result.get('error'):
        raise StudioBridgeError(str(result['error'])[:1000])
    value = result.get('result')
    if not isinstance(value, dict) or type(value.get('count')) is not int or not 0 <= value['count'] <= 1000:
        raise StudioBridgeError('Invalid Studio Instance Manager result')
    if phase == 'preview':
        if (not _GUID.fullmatch(str(value.get('scanToken', '')))
            or not isinstance(value.get('placements'), list)
            or len(value['placements']) != value['count']
            or type(value.get('normalizedPivots')) is not int
            or not 0 <= value['normalizedPivots'] <= value['count']
            or type(value.get('preservedManualSizes')) is not int
            or not 0 <= value['preservedManualSizes'] <= value['count']
            or any(type(place.get(field)) is not bool for place in value['placements']
                   for field in ('legacyPivot','manualSize'))
            or type(value.get('reassignedIds')) is not int
            or not 0 <= value['reassignedIds'] <= value['count']
            or any(not isinstance(place,dict) or not isinstance(place.get('name'),str)
                   or not isinstance(place.get('path'),str)
                   or not isinstance(place.get('placementId'),str)
                   or not _GUID.fullmatch(str(place.get('newPlacementId','')))
                   for place in value['placements'])
            or sum(place['placementId'] != place['newPlacementId']
                   for place in value['placements']) != value['reassignedIds']
            or not isinstance(value.get('anchorOptions'), list)
            or not value['anchorOptions']
            or any(not isinstance(choice, dict) or not isinstance(choice.get('id'), str)
                   or not isinstance(choice.get('label'), str)
                   or not (choice['id'] == 'model' or
                           re.fullmatch(r'mesh:[1-9][0-9]{0,6}', choice['id']))
                   for choice in value['anchorOptions'])
            or value['anchorOptions'][0]['id'] != 'model'
            or len({choice['id'] for choice in value['anchorOptions']}) != len(value['anchorOptions'])):
            raise StudioBridgeError('Invalid Instance Manager Preview')
    elif value.get('changed') != value['count']:
        raise StudioBridgeError('Incomplete Instance Manager transaction; inspect Studio and Undo')
    return value
