"""Resolve a selected Location Model against saved, published visual Mesh IDs.

Do not authorize Collision Capture by a Model name, display slug, or editable
Roblox attribute. The complete visual-mesh multiset must match a recorded
publication and be unambiguous among registered Location Assets.
"""
from __future__ import annotations

import json
import re

_MESH_ID = re.compile(r"[1-9][0-9]{0,19}\Z")


def _signature(meshes: object) -> tuple[tuple[str, int], ...]:
    if not isinstance(meshes, list) or len(meshes) > 4096:
        return ()
    signature = {}
    for mesh in meshes:
        if not isinstance(mesh, dict):
            return ()
        mesh_id = str(mesh.get('meshId') or '')
        count = mesh.get('count')
        names = mesh.get('visualNames')
        if (not _MESH_ID.fullmatch(mesh_id) or type(count) is not int
                or not 1 <= count <= 4096 or not isinstance(names, list)):
            return ()
        if names:  # Excludes old COL meshes and the rig carrier.
            if mesh_id in signature:
                return ()
            signature[mesh_id] = count
    return tuple(sorted(signature.items()))


def expected_versions(store, slug: str) -> list[dict]:
    current = store.get(slug)
    if not current:
        raise ValueError('unknown registered Location Asset')
    if not current.get('model_asset_id'):
        raise ValueError('Collision Capture requires a published Location Model')

    own = {}
    with store.connect() as db:
        rows = db.execute('SELECT asset_slug, model_asset_id, meshes_json '
                          'FROM location_asset_mesh_id_inventory').fetchall()
    # A signature shared with another registered asset cannot identify which
    # asset is selected, even when the selected object has a copied slug stamp.
    owners = {}
    for row in rows:
        try:
            signature = _signature(json.loads(row['meshes_json']))
        except (ValueError, TypeError):
            continue
        if not signature:
            continue
        asset_slug = str(row['asset_slug'])
        owners.setdefault(signature, set()).add(asset_slug)
        if asset_slug == slug:
            own[signature] = str(row['model_asset_id'])

    if not own:
        raise ValueError('No published visual Mesh ID inventory for this Location Asset; '
                         'run Place Registry Scan / refresh published model inventory first')
    ambiguous = [sig for sig in own if owners[sig] != {slug}]
    if ambiguous:
        raise ValueError('Published visual Mesh IDs also identify another Location Asset; '
                         'Collision Capture requires unambiguous model provenance')

    return [{'modelAssetId': own[signature],
             'meshes': [{'meshId': mesh_id, 'count': count} for mesh_id, count in signature]}
            for signature in sorted(own)]
