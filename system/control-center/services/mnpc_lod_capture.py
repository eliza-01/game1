"""Revision-pinned pose/assembly snapshot, not a geometry bake or publication.

Studio reports frames in the canonical navigation-root coordinate system. The
next worker must use these exact IDs/frames to resolve geometry and textures.
Never consume stale captures as the current FULL. No new registry or migration.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from .mnpc_capture_bridge import capture_from_studio, MAX_RESULT_BYTES
from .model_lod_common import check_revision
from .mnpc_lod_bake import validate_pieces


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def asset_id(value, *, optional=False):
    if optional and value == '':
        return value
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', value):
        raise ValueError('Invalid captured Roblox asset ID')
    return value


def idle_identity(animations, slug):
    rows = animations.list_for_monster(slug)
    # Pin all published base idle choices; the Studio runtime adapter selects
    # the effective one with the real mounted equipment context.
    candidates = [{'clipId': row['clip_id'], 'assetId': asset_id(str(row['asset_id'])),
                   'sha256': row['sha256'], 'bindingId': row['binding_id'],
                   'weaponSet': row.get('weaponSet', ''), 'compatibleWith': row.get('compatibleWith', []),
                   'sourceNpc': row.get('sourceNpc', ''), 'looped': row['looped']}
                  for row in rows if row['slot'] == 'idle' and row['status'] == 'PUBLISHED' and row['looped']]
    candidates.sort(key=lambda row: row['bindingId'])
    if not 1 <= len(candidates) <= 64:
        raise ValueError('Publish a current looping base idle animation first')
    return digest(candidates), candidates


def _numbers(value, n, *, limit=100000):
    if not isinstance(value, list) or len(value) != n or any(type(v) not in (int, float) or abs(v) > limit or not math.isfinite(v) for v in value):
        raise ValueError('Invalid numeric capture frame/vector')
    return value


def _frame(value):
    v = _numbers(value, 12)
    axes = [v[3:6], v[6:9], v[9:12]]
    dot = lambda a,b: sum(x*y for x,y in zip(a,b))
    if any(abs(dot(a,b) - (1 if i == j else 0)) > .002 for i,a in enumerate(axes) for j,b in enumerate(axes)):
        raise ValueError('Captured CFrame is not orthonormal')
    a,b,c = axes
    det = a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    if abs(det-1) > .002:
        raise ValueError('Captured CFrame is not a proper rotation')
    return v


def _path(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 1024 or any(not 1 <= len(p) <= 128 or p in ('.','..') for p in value.split('/')):
        raise ValueError('Invalid captured hierarchy path')
    return value


def _texture_ids(visual):
    rows = visual['textures']
    if isinstance(rows, dict):
        rows = [rows]
    return {asset_id(str(t['imageId'])) for t in rows if t.get('imageId')}


def validate_capture(capture, full, candidates):
    if not isinstance(capture, dict) or set(capture) not in ({'animationId','clipId','weaponSet','pose','meshes','bones'}, {'animationId','clipId','weaponSet','pose','meshes','bones','geometry'}):
        raise ValueError('Invalid Studio MNPC capture contract')
    animation_id = asset_id(capture['animationId'])
    if not isinstance(capture['weaponSet'], str) or len(capture['weaponSet']) > 40:
        raise ValueError('Invalid captured equipment context')
    matched = [row for row in candidates if row['assetId'] == animation_id and row['clipId'] == capture['clipId']]
    if not matched or not any(not row['weaponSet'] or capture['weaponSet'] in row['compatibleWith'] for row in matched):
        raise ValueError('Studio selected a stale or incompatible idle animation')
    pose = capture['pose']
    if not isinstance(pose, dict) or set(pose) != {'mode','duration','time','animatedBones'} or pose['mode'] != 'authored_keyframe':
        raise ValueError('MNPC capture requires a complete authored idle keyframe')
    duration, instant = _numbers([pose['duration'],pose['time']],2,limit=3600)
    if not 0 < instant <= duration or type(pose['animatedBones']) is not int or not 1 <= pose['animatedBones'] <= 512:
        raise ValueError('Invalid captured idle time or animated bone count')
    allowed = {'body': _texture_ids(full)}
    for hand, row in full.get('equipment', {}).items():
        if row:
            allowed[hand] = _texture_ids(row['visual'])
    meshes, bones = capture['meshes'], capture['bones']
    if not isinstance(meshes, list) or not 1 <= len(meshes) <= 64 or not isinstance(bones, list) or not pose['animatedBones'] <= len(bones) <= 512:
        raise ValueError('MNPC capture exceeds assembly mesh/bone budget')
    seen, owners = set(), set()
    for mesh in meshes:
        if not isinstance(mesh, dict) or set(mesh) != {'path','owner','meshId','textureId','colorMap','normalMap','roughnessMap','metalnessMap','frame','size','meshSize','color','material','transparency'}:
            raise ValueError('Invalid captured mesh record')
        path, owner = _path(mesh['path']), mesh['owner']
        if path in seen or owner not in allowed:
            raise ValueError('Duplicate mesh or unexpected equipment in capture')
        seen.add(path); owners.add(owner)
        asset_id(mesh['meshId'])
        for key in ('textureId','colorMap','normalMap','roughnessMap','metalnessMap'):
            image = asset_id(mesh[key], optional=True)
            if key in ('textureId','colorMap') and image and image not in allowed[owner]:
                raise ValueError('Captured texture differs from registered atlas; Sync Model + Atlas first')
        _frame(mesh['frame'])
        if any(v <= 0 for key in ('size','meshSize') for v in _numbers(mesh[key],3)):
            raise ValueError('Captured mesh size must be positive')
        if any(not 0 <= v <= 1 for v in _numbers(mesh['color'],3) + _numbers([mesh['transparency']],1)):
            raise ValueError('Invalid mesh color/transparency')
        if not isinstance(mesh['material'],str) or not 1 <= len(mesh['material']) <= 64:
            raise ValueError('Invalid mesh material')
    if owners != set(allowed):
        raise ValueError('Capture omitted the body or registered equipment')
    for bone in bones:
        if not isinstance(bone,dict) or set(bone) != {'path','owner','name','rest','posed','localTransform'}:
            raise ValueError('Invalid captured bone record')
        path = _path(bone['path'])
        if path in seen or bone['owner'] not in allowed or bone['name'] != path.split('/')[-1]:
            raise ValueError('Duplicate or invalid captured bone identity')
        seen.add(path)
        for key in ('rest','posed','localTransform'):
            _frame(bone[key])
    if sum(b['owner'] == 'body' for b in bones) < pose['animatedBones']:
        raise ValueError('Capture omitted animated body bones')
    if 'geometry' in capture:
        validate_pieces(capture['geometry'], meshes)
    return capture


def _file(owner, kind, slug):
    # The domain resource validates kind/slug first. Resolve under owned cache.
    owner._actor(kind, slug)
    return owner.root / '.control-center/mnpc-lod-capture' / kind / (slug + '.json')


def summary(owner, kind, slug, animations):
    path = _file(owner,kind,slug)
    if not path.is_file():
        return {'status':'NOT_CAPTURED'}
    try:
        if path.stat().st_size > MAX_RESULT_BYTES:
            raise ValueError('Capture exceeds size budget')
        stored = json.loads(path.read_text(encoding='utf-8'))
        current = owner.describe(kind,slug)
        idle, candidates = idle_identity(animations,slug)
        if stored['fullFingerprint'] != current['fullFingerprint'] or stored['idleFingerprint'] != idle:
            return {'status':'STALE'}
        if stored['schemaVersion'] != 1 or stored['kind'] != kind or stored['slug'] != slug or stored['fullIdentity'] != current['fullIdentity'] or stored['captureSha256'] != digest(stored['capture']):
            raise ValueError('Capture identity/checksum mismatch')
        capture = validate_capture(stored['capture'],current['fullIdentity'],candidates)
        result = {'status':'CAPTURED','captureSha256':stored['captureSha256'],'animationId':capture['animationId'],
                'meshCount':len(capture['meshes']),'boneCount':len(capture['bones']), 'pose':capture['pose']}
        if 'geometry' in capture:
            result.update(geometryReady=True, triangleCount=sum(len(p['triangles']) for p in capture['geometry']))
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return {'status':'INVALID'}


def capture(owner, kind, slug, payload, animations, *, bridge=None):
    if not isinstance(payload,dict) or set(payload) not in ({'expectedRevision','fullFingerprint','phase'}, {'expectedRevision','fullFingerprint','phase','includeGeometry'}):
        raise ValueError('Capture requires current FULL fingerprint, LOD revision and idle phase')
    if 'includeGeometry' in payload and type(payload['includeGeometry']) is not bool:
        raise ValueError('includeGeometry must be boolean')
    phase = _numbers([payload['phase']],1,limit=1)[0]
    if not 0 < phase < 1:
        raise ValueError('Idle capture phase must be between 0 and 1')
    with owner._lock:
        current = owner.describe(kind,slug)
        check_revision(payload['expectedRevision'],current['revision'])
        if not current['fullFingerprint'] or payload['fullFingerprint'] != current['fullFingerprint']:
            raise ValueError('FULL changed; refresh and sync Model + Atlas')
        if current['status'] == 'MODEL_PENDING':
            raise ValueError('Resolve pending LOD publication before capture')
        idle, candidates = idle_identity(animations,slug)
        full = current['fullIdentity']
        command = dict(kind=kind, slug=slug, expectedRevision=current['revision'],fullFingerprint=current['fullFingerprint'],
                       idleFingerprint=idle, modelId=full['modelId'], phase=phase,
                       equipment={hand:{'slug':row['slug'],'modelId':row['visual']['modelId']} for hand,row in full.get('equipment',{}).items() if row},
                       idles=candidates)
        if payload.get('includeGeometry'):
            command['includeGeometry'] = True
        raw = (bridge or capture_from_studio)(command)
        validated = validate_capture(raw,full,candidates)
        if payload.get('includeGeometry') and 'geometry' not in validated:
            raise ValueError('Studio plugin does not support geometry capture; install latest Game1Bridge')
        latest = owner.describe(kind,slug)
        check_revision(current['revision'],latest['revision'])
        if latest['fullFingerprint'] != current['fullFingerprint'] or idle_identity(animations,slug)[0] != idle:
            raise ValueError('FULL/equipment/idle changed during Studio capture; retry')
        data = dict(schemaVersion=1,kind=kind,slug=slug,fullFingerprint=current['fullFingerprint'],idleFingerprint=idle,
                    fullIdentity=full,requestedPhase=phase,createdAt=datetime.now(timezone.utc).isoformat(),capture=validated,
                    captureSha256=digest(validated))
        encoded = json.dumps(data,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',', ':')).encode('utf-8')
        if len(encoded) > MAX_RESULT_BYTES:
            raise ValueError('Capture file exceeds size budget')
        target = _file(owner,kind,slug)
        target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stream:
            temp = Path(stream.name)
            try:
                stream.write(encoded)
            except BaseException:
                stream.close(); temp.unlink(missing_ok=True); raise
        try:
            os.replace(temp,target)
        finally:
            temp.unlink(missing_ok=True)
        return summary(owner,kind,slug,animations)
