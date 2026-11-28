"""Character component capture plan. One default + single-slot variations,
never the Cartesian product; reuse the MNPC authenticated bridge/compiler.
"""
from __future__ import annotations

import hashlib
import json
from . import hitbox_asset_registry as registry
from .hitbox_asset_authoring import capture_from_studio

GROUPS = ('hair', 'head', 'eyes', 'eyebrows')
SLOTS = {'hair': ('hair',), 'head': ('head',), 'eyes': ('eye_l', 'eye_r'),
         'eyebrows': ('eyebrow_l', 'eyebrow_r')}
HUMANS = ('human_male', 'human_female')


def identity(part):
    return {'id': part['id'], 'asset_id': str(part['asset_id']), 'revision': part['revision']}


def plan(row, catalog):
    assembly = row['assembly']
    base = assembly['parts']
    rig = identity(assembly['rig'])
    variants = []
    seen = set()

    def add(parts, selection=None):
        resolved = {slot: identity(part) for slot, part in parts.items()}
        key = json.dumps(resolved, sort_keys=True)
        if key in seen:
            return
        seen.add(key)
        variants.append({'base': selection is None, 'selection': selection or {}, 'rig': rig, 'parts': resolved})

    add(base)
    if catalog is None:
        return variants
    defaults = {}
    for group in GROUPS:
        items = catalog[group]
        if not items:
            raise ValueError(f'{row["id"]}: no published {group} choices')
        default = (base.get(SLOTS[group][0]) or {}).get('id', '')
        if group in ('eyes', 'eyebrows'):
            default = default.removesuffix('_l')
        defaults[group] = default or items[0]['id']

    def selected_parts(selection):
        parts = dict(base)
        for group in GROUPS:
            item = next((i for i in catalog[group] if i['id'] == selection[group]), None)
            if item is None:
                raise ValueError(f'{row["id"]}: missing selected {group}')
            if group in ('hair', 'head'):
                if group != 'head' or item['id'] != base.get('head', {}).get('id'):
                    parts[group] = item['part']
            else:
                left, right = SLOTS[group]
                parts[left], parts[right] = item['left'], item['right']
        return parts

    add(selected_parts(defaults), defaults)
    for group in GROUPS:
        for item in catalog[group]:
            selection = {**defaults, group: item['id']}
            add(selected_parts(selection), selection)
    if len(variants) > 32:
        raise ValueError('Character capture plan exceeds 32 assemblies; split authoring plan')
    return variants


def command_for(slug, root=registry.ROOT):
    if not isinstance(slug, str) or not slug:
        raise ValueError('Character id required')
    paths = [root / 'assets/manifests' / name for name in
             ('character-archetypes.json', 'character-creation-appearance.json')]
    blobs = [path.read_bytes() for path in paths]
    archetypes, choices = (json.loads(blob.decode('utf-8-sig')) for blob in blobs)
    row = next((row for row in archetypes['archetypes'] if row['id'] == slug and
                row['status'] == 'ASSEMBLY_READY' and row['assembly']['ready']), None)
    if not row:
        raise ValueError('Publish Character assembly first')
    catalog = choices['archetypes'].get(slug) if slug in HUMANS else None
    if slug in HUMANS and catalog is None:
        raise ValueError('Character appearance catalog unavailable')
    variants = plan(row, catalog)
    fingerprint = hashlib.sha256(b'\0'.join(blobs)).hexdigest()
    return {'kind': 'character', 'slug': slug, 'modelId': str(row['assembly']['rig']['asset_id']),
            'fullFingerprint': fingerprint, 'assemblyFingerprint': row['assembly']['fingerprint'], 'variants': variants}


def _equal(a, b):
    # The same captured component may occur in several detached assemblies.
    # Ignore only roundoff in bounds; differing signatures remain distinct.
    if type(a) in (int, float) and type(b) in (int, float):
        return abs(a-b) <= 1e-5
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x,y) for x,y in zip(a,b))
    return a == b


def capture(slug, *, bridge=None, destination=registry.REGISTRY, root=registry.ROOT):
    command = command_for(slug, root)
    raw = (bridge or capture_from_studio)(command)
    if not isinstance(raw, dict) or raw.get('schemaVersion') != 2 or raw.get('variants') != len(command['variants']):
        raise ValueError('Incomplete Character capture')
    entries = {}
    for row in registry.sequence(raw.get('entries')):
        normalized = registry.normalize({'schemaVersion': 2, 'entries': [row]})['entries'][0]
        key = normalized['key']
        if not key.startswith('component|') or f'|identity:{slug}|head:' not in key:
            raise ValueError('Capture belongs to a different Character')
        ident = (key, normalized['signature'])
        if ident in entries and not _equal(entries[ident], normalized):
            raise ValueError('Conflicting component oracle captures')
        entries.setdefault(ident, normalized)
    if command_for(slug, root) != command:
        raise ValueError('Character publication changed during capture; refresh and retry')
    total = registry.replace_character_components(slug, {'schemaVersion': 2, 'entries': list(entries.values())}, destination)
    return {'status': 'CAPTURED', 'variants': len(command['variants']), 'components': len(entries),
            'entries': total, 'nativeCoverage': 'NOT_RUN'}
