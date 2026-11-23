"""Game Runtime flora contact VFX authoring. Strict, backward-compatible Options contract.

Resident slugs refer to immutable published Location models; only one-visual
MeshPart models are eligible for the lightweight particle template cache.
"""
from copy import deepcopy
import json
import math
import re

DEFAULTS = {
    'enabled': True,
    'leafAssetSlug': 'leaf_01',
    'residentAssets': ['leaf_01'],
    'leavesPerBurst': 8,
    'spawnRadiusStuds': 2.0,
    'spreadRadiusStuds': 5.0,
    'contactPaddingStuds': 1.25,
    'durationSeconds': 1.5,
    'cooldownSeconds': 1.5,
    'maxActiveLeaves': 32,
}

NUMBERS = {
    'leavesPerBurst': (1, 20, True),
    'spawnRadiusStuds': (0, 8, False),
    'spreadRadiusStuds': (0.5, 20, False),
    'contactPaddingStuds': (0, 5, False),
    'durationSeconds': (0.3, 4, False),
    'cooldownSeconds': (0.2, 30, False),
    'maxActiveLeaves': (8, 96, True),
}


def normalize_flora(change, base=None):
    if not isinstance(change, dict) or set(change) - set(DEFAULTS):
        raise ValueError('flora: unsupported setting')
    result = deepcopy(DEFAULTS)
    result.update(deepcopy(base or {}))
    result.update(deepcopy(change))
    if type(result['enabled']) is not bool:
        raise ValueError('flora.enabled must be a boolean')
    for key, (low, high, integer) in NUMBERS.items():
        value = result[key]
        if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high or (integer and int(value) != value):
            raise ValueError(f'flora.{key} must be {low}..{high}' + (' integer' if integer else ''))
        result[key] = int(value) if integer else float(value)
    slugs = result['residentAssets']
    if not isinstance(slugs, list) or not 1 <= len(slugs) <= 8 or len(slugs) != len(set(map(str, slugs))):
        raise ValueError('flora.residentAssets must contain 1..8 distinct asset slugs')
    for slug in slugs:
        if not isinstance(slug, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', slug):
            raise ValueError('flora.residentAssets: invalid asset slug')
    if not isinstance(result['leafAssetSlug'], str) or result['leafAssetSlug'] not in slugs:
        raise ValueError('flora.leafAssetSlug must be in residentAssets')
    if result['maxActiveLeaves'] < result['leavesPerBurst']:
        raise ValueError('flora.maxActiveLeaves must be >= leavesPerBurst')
    return result


def validate_residents(root, flora):
    """Fail closed at authoring time, not mid-session after a failed InsertService call."""
    path = root / 'assets/manifests/location-assets.json'
    if not path.is_file():
        # Independent Options-only migration fixtures may have no Location
        # catalog. Permit ONLY the immutable default; real authoring changes
        # require the published catalog for identity validation.
        if flora['residentAssets'] == DEFAULTS['residentAssets'] and flora['leafAssetSlug'] == DEFAULTS['leafAssetSlug']:
            return
        raise ValueError('flora.residentAssets: published Location catalog unavailable')
    catalog = json.loads(path.read_text(encoding='utf-8'))
    items = {row['slug']: row for row in catalog.get('items', [])}
    for slug in flora['residentAssets']:
        row = items.get(slug)
        if not row or row.get('status') != 'PUBLISHED' or not str(row.get('model_asset_id') or '').isdigit():
            raise ValueError(f'flora.residentAssets: {slug} requires a published Location Model')
        if len([mesh for mesh in row.get('fbxAnalysis', {}).get('meshes', [])
                if mesh.get('role', 'visual') == 'visual']) != 1:
            raise ValueError(f'flora.residentAssets: {slug} must be a single-MeshPart asset')
    leaf = items[flora['leafAssetSlug']]
    if leaf.get('category') != 'leaf':
        raise ValueError('flora.leafAssetSlug must reference a leaf-category asset')
