"""Single-operation Studio Bridge request for refreshing placed Location Assets.

Transport only. The Studio DecoManager owns the asset registry and material
refresh; Host Agent never writes placement data or SQLite during sync.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
import uuid
import re

from studio_bridge import PORT, PROJECT, TOKEN, StudioBridgeError


def run_deco_refresh_bridge(*, timeout_seconds: float = 75.0,
                            slug: str, binding_revision: int,
                            model_asset_id: str, atlas_asset_id: str,
                            phase: str = 'scan', scan_token: str = '',
                            selected_keys: list[str] | None = None, part_key: str = '',
                            part_keys: list[str] | None = None,
                            model_history: list[str] | None = None,
                            model_mesh_inventory: list[dict] | None = None) -> dict:
    """Protocol 9: scan, read-only bulk Model selection, explicit replace."""
    if not re.fullmatch(r'[a-z0-9][a-z0-9_]{0,63}', str(slug)):
        raise ValueError('Location Asset Studio Sync requires one valid slug')
    if type(binding_revision) is not int or binding_revision < 1:
        raise ValueError('invalid Location Asset binding revision')
    for identifier in (model_asset_id, atlas_asset_id):
        if not re.fullmatch(r'[1-9][0-9]{0,19}', str(identifier)):
            raise ValueError('a published Model and Atlas Asset ID are required')
    if phase not in ('scan','select','attach','replace'):
        raise ValueError('Studio Sync phase must be scan, select, attach or replace')
    if phase == 'scan':
        if (not isinstance(model_history, list) or not 1 <= len(model_history) <= 48
                or len(set(model_history)) != len(model_history)
                or str(model_asset_id) not in model_history
                or any(not re.fullmatch(r'[1-9][0-9]{0,19}', str(mid)) for mid in model_history)):
            raise ValueError('invalid Model publication ID history')
    else:
        if not re.fullmatch(r'[0-9a-fA-F-]{32,36}', scan_token):
            raise ValueError('explicit Find in Studio is required before Select/Replace')
        if phase == 'select' and (not isinstance(part_keys,list) or not 1 <= len(part_keys) <= 4096
                or len(set(str(key) for key in part_keys))!=len(part_keys)
                or any(not isinstance(key,str) or not re.fullmatch(r'p[1-9][0-9]{0,3}',key)
                       for key in part_keys)):
            raise ValueError('Select in Studio requires unique scanned MeshPart keys')
        if phase == 'attach' and not re.fullmatch(r'p[1-9][0-9]{0,3}', part_key):
            raise ValueError('Link requires a scanned MeshPart key')
        if phase == 'replace' and (not isinstance(selected_keys, list) or not 1 <= len(selected_keys) <= 4096
                or len(set(selected_keys)) != len(selected_keys)
                or any(not isinstance(k, str) or not re.fullmatch(r'p[1-9][0-9]{0,3}', k)
                       for k in selected_keys)):
            raise ValueError('explicit bounded managed MeshPart selection is required')
    operation_id = uuid.uuid4().hex
    command = {
        'project': PROJECT,
        'command': 'deco-refresh',
        'schemaVersion': 9,
        'operationId': operation_id,
        'targetSlug': slug,
        'bindingRevision': binding_revision,
        'modelAssetId': model_asset_id,
        'atlasAssetId': atlas_asset_id,
        'phase': phase,
        **({'modelHistory':model_history, 'modelMeshInventory':model_mesh_inventory or []}
           if phase=='scan' else {'scanToken':scan_token,'partKeys':part_keys}
           if phase=='select' else {'scanToken':scan_token,'partKey':part_key}
           if phase=='attach' else {'scanToken':scan_token,'selectedKeys':selected_keys}),
    }
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
                # Per-instance audit records are intentionally returned to the
                # Host Agent. Keep the request bounded without truncating them.
                if length < 1 or length > 2 * 1024 * 1024:
                    raise ValueError("invalid result payload length")
                incoming = json.loads(self.rfile.read(length).decode("utf-8"))
                if (not isinstance(incoming, dict)
                        or incoming.get("project") != PROJECT
                        or incoming.get("command") != "deco-refresh"
                        or incoming.get("schemaVersion") != command["schemaVersion"]
                        or incoming.get("operationId") != operation_id
                        or incoming.get("targetSlug") != slug
                        or incoming.get("bindingRevision") != binding_revision
                        or incoming.get("phase") != phase):
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
    values = {'operationId': operation_id, 'targetSlug': slug,
              'bindingRevision': binding_revision, 'phase': phase}
    if phase == 'select':
        name = result.get('selectedName')
        path = result.get('selectedPath')
        count = result.get('selectedCount')
        if (type(count) is not int or not 1 <= count <= len(part_keys or [])
                or not isinstance(name,str) or len(name)>128
                or not isinstance(path,str) or len(path)>1024
                or (count==1 and (not name or not path))
                or (count>1 and (name or path))):
            raise StudioBridgeError('invalid Studio selection result')
        return dict(values, selectedCount=count, selectedName=name, selectedPath=path)
    if phase == 'scan':
        mode = result.get('mode')
        token = str(result.get('scanToken') or '')
        if mode not in ('texture','mesh','texture_mesh','alpha','current') or not re.fullmatch(r'[0-9a-fA-F-]{32,36}', token):
            raise StudioBridgeError('invalid Studio ID scan result')
        for key in ('foundMeshParts','managedMeshParts','unmanagedMeshParts',
                    'managedModels','texturePending','geometryPending'):
            value = result.get(key)
            if type(value) is not int or not 0 <= value <= 4096:
                raise StudioBridgeError('invalid Studio scan field: ' + key)
            values[key] = value
        inventory = result.get('inventory')
        if not isinstance(inventory,list) or not 1 <= len(inventory) <= 48:
            raise StudioBridgeError('invalid published Mesh ID inventory')
        expected = result.get('expectedMeshIds')
        if (not isinstance(expected, list) or len(expected)>4096
                or any(not isinstance(v,str) or not re.fullmatch(r'[1-9][0-9]{0,19}',v) for v in expected)
                or len(set(expected))!=len(expected)):
            raise StudioBridgeError('invalid current Model Mesh IDs')
        parts = result.get('parts')
        if not isinstance(parts, list) or len(parts)>4096 or len(parts)!=values['foundMeshParts']:
            raise StudioBridgeError('invalid per-part Studio scan report')
        managed=0
        texture_pending=0
        mesh_pending=0
        alpha_pending=0
        for index, part in enumerate(parts, 1):
            if not isinstance(part, dict) or part.get('key') != f'p{index}':
                raise StudioBridgeError('invalid Studio MeshPart report identity')
            if (not isinstance(part.get('name'), str) or not 1 <= len(part['name']) <= 128
                    or not isinstance(part.get('path'), str) or not 1 <= len(part['path']) <= 240
                    or not isinstance(part.get('modelName'),str) or not 1 <= len(part['modelName']) <= 128
                    or not isinstance(part.get('modelPath'),str) or not 1 <= len(part['modelPath']) <= 240
                    or any(not isinstance(part.get(k),bool) for k in
                           ('managed','meshCurrent','textureCurrent','needsMesh','needsTexture','hasSurface','textureApplicable','attachable','isCollider'))):
                raise StudioBridgeError('invalid Studio MeshPart report fields')
            for field in ('meshId','textureId','colorMapId','instanceId','historicalModelId'):
                val=part.get(field)
                if not isinstance(val,str) or len(val)>128:
                    raise StudioBridgeError('invalid Studio MeshPart ID: '+field)
            # M250: accept older Studio scans without Alpha fields, but validate
            # every Alpha flag sent by an Alpha-aware Studio plugin.
            for flag in ('needsAlpha', 'alphaCurrent', 'alphaEnabled'):
                if flag in part and type(part[flag]) is not bool:
                    raise StudioBridgeError('invalid Studio MeshPart Alpha flag: ' + flag)
            if ('needsAlpha' in part and 'alphaCurrent' in part
                    and part['needsAlpha'] == part['alphaCurrent']):
                raise StudioBridgeError('inconsistent Studio MeshPart Alpha state')
            if not part['textureApplicable'] and part.get('needsAlpha', False):
                raise StudioBridgeError('COL MeshPart must not require Alpha Sync')
            if part['attachable'] and (part['managed'] or not re.fullmatch(r'[1-9][0-9]{0,19}',part['historicalModelId'])):
                raise StudioBridgeError('invalid historical Model linking candidate')
            if part['isCollider'] and part['textureApplicable']:
                raise StudioBridgeError('COL MeshPart must not have atlas state')
            if not part['textureApplicable'] and (part['needsTexture'] or not part['textureCurrent']
                                                  or part['textureId'] or part['colorMapId'] or part['hasSurface']):
                raise StudioBridgeError('collision geometry must not have atlas state')
            if part['managed']:
                managed+=1
                if not part['textureCurrent']: texture_pending+=1
                if part['needsMesh']: mesh_pending+=1
                if part.get('needsAlpha', False): alpha_pending+=1
            elif part['needsMesh']:
                raise StudioBridgeError('unmanaged MeshPart must not be sync eligible')
        if managed!=values['managedMeshParts'] or texture_pending!=values['texturePending']:
            raise StudioBridgeError('Studio per-part report count mismatch')
        if mesh_pending!=result.get('meshPending'):
            raise StudioBridgeError('Studio mesh count mismatch')
        reported_alpha = result.get('alphaPending', 0)
        if (type(reported_alpha) is not int or not 0 <= reported_alpha <= 4096
                or reported_alpha != alpha_pending):
            raise StudioBridgeError(
                f'Studio alpha count mismatch: reported={reported_alpha!r}, '
                f'computed={alpha_pending}, managed={managed}'
            )
        if mode == 'alpha' and (alpha_pending == 0 or texture_pending or values['geometryPending']):
            raise StudioBridgeError('inconsistent Studio Alpha-only scan mode')
        values.update(mode=mode, scanToken=token, inventory=inventory,
                      expectedMeshIds=expected,parts=parts,meshPending=mesh_pending,
                      alphaPending=alpha_pending)
        return values
    if type(result.get('fullySynced')) is not bool:
        raise StudioBridgeError('invalid partial-sync acknowledgement')
    values['fullySynced'] = result['fullySynced']
    for field in ('models', 'parts', 'matchedModels', 'modelReferences',
                  'pendingGeometry', 'geometryUpdated', 'meshPartsUpdated', 'registryItems', 'replacedModels'):
        value = result.get(field)
        if type(value) is not int or value < 0:
            raise StudioBridgeError(f'invalid Studio deco-refresh result field: {field}')
        values[field] = value
    if (values['replacedModels'] != 0 or values['models'] > values['matchedModels']
            or values['geometryUpdated'] > values['models']):
        raise StudioBridgeError('unsafe Location Asset Studio model replacement result')
    changes = result.get('changes')
    if not isinstance(changes, list) or len(changes) > 32:
        raise StudioBridgeError('invalid Studio Location Asset ID change log')
    values['changes'] = changes
    instances = result.get('instances')
    if not isinstance(instances, list) or len(instances) > 10000:
        raise StudioBridgeError('invalid Studio Location Asset instance audit log')
    validated_instances = []
    seen_instances = set()
    for item in instances:
        if not isinstance(item, dict):
            raise StudioBridgeError('invalid Studio Location Asset instance audit entry')
        instance_id = str(item.get('instanceId') or '')
        studio_path = str(item.get('studioPath') or '')
        item_changes = item.get('changes')
        if (not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', instance_id)
                or not studio_path or len(studio_path) > 1024
                or instance_id in seen_instances
                or not isinstance(item_changes, list) or not item_changes
                or len(item_changes) > 32):
            raise StudioBridgeError('invalid Studio Location Asset instance audit entry')
        seen_instances.add(instance_id)
        meshes = {}
        for key in ('meshIdsBefore', 'meshIdsAfter'):
            parts = item.get(key, [])
            if not isinstance(parts,list) or len(parts)>4096:
                raise StudioBridgeError('invalid audited Mesh ID inventory')
            for entry in parts:
                if (not isinstance(entry,dict)
                    or not re.fullmatch(r'[1-9][0-9]{0,19}',str(entry.get('meshId') or ''))
                    or type(entry.get('count')) is not int or not 1 <= entry['count'] <= 4096):
                    raise StudioBridgeError('invalid audited Mesh ID entry')
            meshes[key] = parts
        validated_instances.append({
            **meshes,
            'instanceId': instance_id,
            'studioPath': studio_path,
            'changes': item_changes,
        })
    if len(validated_instances) != values['models']:
        raise StudioBridgeError('Studio Location Asset instance audit count mismatch')
    values['instances'] = validated_instances
    return values
