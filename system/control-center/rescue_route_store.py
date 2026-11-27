"""Read-only Database projection of a Studio Place's authored rescue polylines.

The Place is authoritative for runtime. The mirror cannot write back to it.
A full snapshot is explicit and scoped by the Place's persistent map UUID.
"""
import json
import math
import re
import threading
import os
import tempfile
from pathlib import Path

_LOCK = threading.RLock()
_UUID = re.compile(r"[0-9a-fA-F-]{36}\Z")


def snapshot(root):
    path = Path(root) / 'assets/manifests/rescue-routes.json'
    with _LOCK:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schemaVersion': 1, 'maps': {}}


def sync(root, payload):
    if not isinstance(payload, dict) or set(payload) != {'mapId', 'placeId', 'routes'}:
        raise ValueError('Invalid rescue route snapshot')
    map_id, place_id, routes = payload['mapId'], payload['placeId'], payload['routes']
    if routes == {}:  # Roblox JSONEncode empty table compatibility
        routes = []
    if not isinstance(map_id, str) or not _UUID.fullmatch(map_id):
        raise ValueError('Invalid rescue map ID')
    if type(place_id) is not int or place_id < 0 or not isinstance(routes, list) or len(routes) > 512:
        raise ValueError('Invalid place or route count')
    clean = []
    ids = set()
    edges = 0
    for route in routes:
        if not isinstance(route, dict) or not {'id', 'points'} <= set(route) <= {'id', 'points', 'name', 'catalog'}:
            raise ValueError('Invalid route')
        key, points = route['id'], route['points']
        if not isinstance(key, str) or not re.fullmatch(r'Route_[0-9a-fA-F-]{36}', key) or key in ids:
            raise ValueError('Invalid or duplicate route ID')
        ids.add(key)
        if not isinstance(points, list) or not 2 <= len(points) <= 256:
            raise ValueError('Expected 2–256 points')
        for p in points:
            if not isinstance(p, list) or len(p) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1000000 for n in p):
                raise ValueError('Invalid point coordinates')
        edges += len(points)-1
        if edges > 2048:
            raise ValueError('Maximum 2048 edges per map')
        length = sum(math.dist(a,b) for a,b in zip(points, points[1:]))
        record = {'id':key,'points':points,'lengthStuds':round(length,3)}
        for field in ('name', 'catalog'):
            if field in route:
                value = route[field]
                if not isinstance(value, str) or not value.strip() or len(value) > 80 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                    raise ValueError(f'Invalid route {field}')
                record[field] = value.strip()
        clean.append(record)
    path = Path(root) / 'assets/manifests/rescue-routes.json'
    with _LOCK:
        data = snapshot(root)
        data['maps'][f'{place_id}:{map_id}'] = {'placeId':place_id,'mapId':map_id,'routes':clean}
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.rescue-routes-', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as handle:
                json.dump(data,handle,ensure_ascii=False,indent=2); handle.write('\n')
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    return {'ok': True, 'routes':len(clean),'edges':edges}
