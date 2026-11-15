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
                                 anchor_id: str = 'model', inspection_token: str = '',
                                 approve_shear: bool = False, focus_index: int = 0,
                                 focus_part_id: str = '',
                                 timeout_seconds: float = 300.0) -> dict:
    if (not isinstance(catalog, dict) or catalog.get('domain') != 'location_assets'
        or catalog.get('schemaVersion') != 1 or not isinstance(catalog.get('digest'), str)
        or not _SLUG.fullmatch(source_slug) or not _SLUG.fullmatch(target_slug)
        or source_slug == target_slug or scope not in ('selected', 'all')
        or phase not in ('preview', 'inspect', 'clear', 'focus', 'replace') or not isinstance(anchor_id, str)
        or not (anchor_id in ('model', 'geometry') or (re.fullmatch(r'mesh:[1-9][0-9]{0,6}',anchor_id) is not None))):
        raise ValueError('Invalid Location Instance Manager scope/catalog')
    if phase in ('inspect', 'clear', 'focus', 'replace') and not _GUID.fullmatch(scan_token):
        raise ValueError('Preview token required')
    if phase == 'preview' and anchor_id != 'model':
        raise ValueError('Preview must start with the target Model pivot option')
    if phase == 'preview' and scan_token:
        raise ValueError('Unexpected Preview token')
    if (not isinstance(inspection_token,str) or type(approve_shear) is not bool
        or (approve_shear and phase != 'replace')
        or (inspection_token and (phase not in ('clear', 'focus', 'replace')
                                  or not _GUID.fullmatch(inspection_token)))):
        raise ValueError('Invalid collision approval')
    if phase == 'focus':
        if (not _GUID.fullmatch(inspection_token) or type(focus_index) is not int
            or not 1 <= focus_index <= 1000 or not isinstance(focus_part_id,str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_\-]{0,63}',focus_part_id)):
            raise ValueError('Focus needs a current inspected collision warning')
    elif focus_index != 0 or focus_part_id:
        raise ValueError('Unexpected collision focus fields')
    slugs = {row['slug'] for row in catalog['items']}
    if source_slug not in slugs or target_slug not in slugs:
        raise ValueError('Source and target must be published Location Assets')
    operation_id = uuid.uuid4().hex
    command = dict(project=PROJECT, command='location-instance-replace-v4', schemaVersion=4,
                   operationId=operation_id, catalog=catalog, phase=phase,
                   sourceSlug=source_slug, targetSlug=target_slug, scope=scope,
                   scanToken=scan_token, anchorId=anchor_id,
                   inspectionToken=inspection_token, approveShear=approve_shear,
                   focusIndex=focus_index, focusPartId=focus_part_id)
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
            or type(value.get('differingVisualAxes', 0)) is not int
            or not 0 <= value.get('differingVisualAxes', 0) <= value['count']
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
                   or not (choice['id'] in ('model', 'geometry') or
                           re.fullmatch(r'mesh:[1-9][0-9]{0,6}', choice['id']))
                   for choice in value['anchorOptions'])
            or value['anchorOptions'][0]['id'] != 'model'
            or len({choice['id'] for choice in value['anchorOptions']}) != len(value['anchorOptions'])):
            # Preview is read-only. Report the response contract mismatch without
            # changing the existing strict authorization guard for Replace.
            placements = value.get('placements')
            options = value.get('anchorOptions')
            details = {
                'count': value.get('count'),
                'placementsCount': len(placements) if isinstance(placements, list) else None,
                'normalizedPivots': value.get('normalizedPivots'),
                'preservedManualSizes': value.get('preservedManualSizes'),
                'differingVisualAxes': value.get('differingVisualAxes'),
                'reassignedIds': value.get('reassignedIds'),
                'anchorIds': [option.get('id') if isinstance(option, dict) else None for option in options]
                    if isinstance(options, list) else None,
                'firstPlacement': placements[0] if isinstance(placements, list) and placements else None,
                'scanTokenFormat': bool(_GUID.fullmatch(str(value.get('scanToken', '')))),
            }
            raise StudioBridgeError('Invalid Instance Manager Preview: ' +
                                    json.dumps(details, ensure_ascii=False, default=str)[:1800])
    elif phase == 'inspect':
        details = value.get('warningDetails')
        if (not _GUID.fullmatch(str(value.get('inspectionToken', '')))
            or type(value.get('collisionParts')) is not int or not 0 <= value['collisionParts'] <= 512
            or type(value.get('warnings')) is not int
            or not isinstance(details,list) or len(details) != value['warnings']
            or any(not isinstance(item,dict) or not isinstance(item.get('path'),str)
                   or not isinstance(item.get('partId'),str)
                   or (item.get('index') is not None and
                       (type(item['index']) is not int or not 1 <= item['index'] <= value['count']))
                   or not isinstance(item.get('excessStuds'),list) or len(item['excessStuds']) != 3
                   or not isinstance(item.get('addedPercent'),list) or len(item['addedPercent']) != 3
                   or (item.get('shape') is not None and item['shape'] not in
                       ('Block','Wedge','CornerWedge','Ball','Cylinder'))
                   or (item.get('approximate') is not None and type(item['approximate']) is not bool)
                   or (item.get('reason') is not None and
                       (not isinstance(item['reason'],str) or len(item['reason']) > 256))
                   or any(type(n) not in (float,int) or n < 0 or n > 1000000
                          for n in item['excessStuds']+item['addedPercent']) for item in details)):
            raise StudioBridgeError('Invalid collision inspection response')
    elif phase == 'clear':
        if value.get('cleared') is not True:
            raise StudioBridgeError('Invalid collision preview cleanup response')
    elif phase == 'focus':
        if (value.get('focused') is not True or value.get('index') != focus_index
            or value.get('partId') != focus_part_id):
            raise StudioBridgeError('Invalid collision warning focus response')
    elif value.get('changed') != value['count']:
        raise StudioBridgeError('Incomplete Instance Manager transaction; inspect Studio and Undo')
    return value
