"""Authoritative allowlist for Studio Place inventory, built from published Location Assets.

Never infer registration from Workspace names, Model attributes or categories.
"""
from __future__ import annotations

import hashlib
import json
import re

_ASSET_ID = re.compile(r'[1-9][0-9]{0,19}\Z')


def build_catalog(location_assets) -> dict:
    items = []
    for row in location_assets.snapshot()['items']:
        if row.get('status') not in ('PUBLISHED', 'UPDATE_AVAILABLE'):
            continue
        slug = str(row.get('slug') or '')
        model = str(row.get('model_asset_id') or '')
        atlas = str(row.get('texture_asset_id') or '')
        if not _ASSET_ID.fullmatch(model) or not _ASSET_ID.fullmatch(atlas):
            continue
        history = location_assets.model_publication_ids(slug)
        inventory = {str(v['modelAssetId']): v for v in location_assets.mesh_id_inventory(slug)}
        if model not in history:
            history.insert(0, model)
        items.append({
            'slug': slug, 'aliases': (location_assets.aliases_for(slug)
                                     if hasattr(location_assets, 'aliases_for') else []),
            'modelAssetId': model, 'atlasAssetId': atlas,
            'publishedSha': str(row.get('model_published_sha256') or ''),
            'surfaceMaterial': str(row.get('surfaceMaterial') or 'default'),
            'alphaEnabled': bool(row.get('alphaEnabled', False)),
            'robloxMaterial': str((row.get('materialDefinition') or {}).get('robloxMaterial') or ''),
            'rigManifest': (location_assets.rig_manifest(slug, model)
                            if hasattr(location_assets, 'rig_manifest') else None),
            'legacyStaticPublication': bool(row.get('legacyStaticPublication')),
            'needsFbxInspection': bool(row.get('needsFbxInspection')),
            'models': [{'modelAssetId': identifier,
                        'meshes': inventory.get(identifier, {}).get('meshes', [])}
                       for identifier in history],
        })
    items.sort(key=lambda a: a['slug'])
    data = {'schemaVersion': 1, 'domain': 'location_assets', 'items': items}
    # Mesh inventory is an observed cache; filling it during Scan must not
    # invalidate the immediately following repair token. Publication identity
    # and atlas bindings, not cache population, define the stable digest.
    identities = [{k: item[k] for k in ('slug', 'modelAssetId', 'atlasAssetId', 'publishedSha', 'surfaceMaterial', 'robloxMaterial', 'alphaEnabled')}
                  | {'versions': [model['modelAssetId'] for model in item['models']],
                     'aliases': item['aliases'],
                     'rigHash': (item.get('rigManifest') or {}).get('structuralHash', ''),
                     'legacyStatic': item['legacyStaticPublication'],
                     'inspectionNeeded': item['needsFbxInspection']}
                  for item in items]
    data['digest'] = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return data


def validate_report(report: dict, catalog: dict) -> list[dict]:
    """Do not store untrusted Studio data referring to another domain/asset."""
    if not isinstance(report, dict) or report.get('schemaVersion') != 1:
        raise ValueError('invalid Place Registry scan schema')
    rows = report.get('placements')
    if not isinstance(rows, list) or len(rows) > 4096:
        raise ValueError('invalid Place Registry inventory size')
    known = {r['slug'] for r in catalog['items']}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('slug') not in known:
            raise ValueError('Place Registry returned an unregistered Location Asset')
        key = row.get('key')
        if not isinstance(key, str) or not re.fullmatch(r'p[1-9][0-9]{0,4}', key) or key in seen:
            raise ValueError('invalid/duplicate scanned placement key')
        seen.add(key)
        for field in ('name', 'path', 'meshId', 'textureId', 'placementId', 'status'):
            if not isinstance(row.get(field), str) or len(row[field]) > 1200:
                raise ValueError('invalid scanned placement field: ' + field)
        for flag in ('needsMesh', 'needsTexture', 'needsStructure', 'duplicateId', 'ambiguous', 'hasModel', 'canSync'):
            if type(row.get(flag)) is not bool:
                raise ValueError('invalid scan flag: ' + flag)
        if 'structuralState' in row and row['structuralState'] not in (
                'current','legacy_import_root','missing_rig_carrier','invalid_rig_carrier',
                'multiple_rig_carriers','bone_manifest_mismatch','published_structure_mismatch',
                'repair_required','manual_review_required'):
            raise ValueError('invalid structural State')
        for flag in ('canRepair', 'requiresRepublish', 'needsCanonicalReplacement', 'needsFbxInspection'):
            if flag in row and type(row[flag]) is not bool:
                raise ValueError('invalid scan flag: ' + flag)
        if (row.get('canRepair', False) and (row.get('requiresRepublish', False)
                or row.get('structuralState', 'current') != 'current')):
            raise ValueError('noncanonical Location placement cannot authorize Repair')
        if 'needsRig' in row and type(row['needsRig']) is not bool:
            raise ValueError('invalid scan flag: needsRig')
        # Schema 1 older Studio plugins omit the new material-only flag.
        # Validate strictly when present, while allowing read-only historical scans.
        if 'needsMaterial' in row and type(row['needsMaterial']) is not bool:
            raise ValueError('invalid scan flag: needsMaterial')
        if 'needsAlpha' in row and type(row['needsAlpha']) is not bool:
            raise ValueError('invalid scan flag: needsAlpha')
        if not isinstance(row.get('issues'), list) or len(row['issues']) > 12 or any(
                not isinstance(s, str) or len(s) > 250 for s in row['issues']):
            raise ValueError('invalid diagnostic issues')
        if not isinstance(row.get('transform'), dict):
            raise ValueError('missing placement transform')
    return rows
