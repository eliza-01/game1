"""Pure, versioned Location rig manifest policy (no Blender / Roblox dependency).

The authoring and publication tools both use this contract. Mesh asset IDs are
resolved *after* Open Cloud publication by Studio, not guessed from Model IDs.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

SCHEMA_VERSION = 2
CARRIER = 'rig_carrier'
ROOT = 'RootPart'


def role(name: str) -> str:
    lower = name.casefold()
    if lower == CARRIER:
        return 'rig_carrier'
    if lower == 'col_mesh' or lower.startswith('col_'):
        return 'collider'
    return 'visual'


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def validate(parts: list[dict], bones: list[dict], *, source_sha256: str = '') -> dict:
    """Refuse incomplete authoring geometry and return a deterministic manifest.

    Caller must supply the entire bone tree, including its parent and rest frame
    for *every* bone; unique names are intentionally required across this rig.
    """
    if not isinstance(parts, list) or not parts or not isinstance(bones, list):
        raise ValueError('Location rig requires authored MeshParts and a bone inventory')
    names = [p['name'] for p in parts]
    if any(not isinstance(n, str) or not n or n == ROOT for n in names):
        raise ValueError('RootPart and empty part names are forbidden in Location authoring')
    if len(names) != len(set(n.casefold() for n in names)):
        raise ValueError('duplicate MeshPart names in Location rig')
    if any(name.casefold() == CARRIER and name != CARRIER for name in names):
        raise ValueError('rig_carrier MeshPart name must use canonical lowercase spelling')
    carriers = [p for p in parts if role(p['name']) == 'rig_carrier']
    skinned = bool(bones)
    if skinned:
        if len(carriers) != 1 or not isinstance(carriers[0].get('vertices'), int) or carriers[0]['vertices'] < 3:
            raise ValueError('skinned Location requires exactly one real, nonempty rig_carrier')
    elif carriers:
        raise ValueError('static Location without Bones must not contain rig_carrier')
    if len([p for p in parts if role(p['name']) == 'visual']) < 1:
        raise ValueError('Location asset requires at least one visual MeshPart')
    bone_names = [b['name'] for b in bones]
    if len(bone_names) != len(set(bone_names)):
        raise ValueError('duplicate Bone names in Location rig')
    lookup = {b['name']: b for b in bones}
    for bone in bones:
        if not isinstance(bone.get('name'), str):
            raise ValueError('invalid Bone name')
        parent = bone.get('parent', '')
        if parent and (parent not in lookup or parent == bone['name']):
            raise ValueError('invalid Bone parent: ' + bone['name'])
        frame = bone.get('matrix')
        if not isinstance(frame, list) or len(frame) != 16 or any(
            not isinstance(n, (int, float)) for n in frame):
            raise ValueError('invalid Bone bind/rest matrix: ' + bone['name'])
        visited = {bone['name']}
        while parent:
            if parent in visited:
                raise ValueError('Bone parent cycle: ' + bone['name'])
            visited.add(parent)
            parent = lookup[parent].get('parent', '')
    normalized_parts = [{'name': p['name'], 'role': role(p['name']),
                         'vertices': p['vertices']} for p in parts]
    normalized_parts.sort(key=lambda p: p['name'])
    normalized_bones = sorted(bones, key=lambda b: b['name'])
    structural = {'parts': normalized_parts, 'bones': normalized_bones}
    return {'schemaVersion': SCHEMA_VERSION, 'parts': normalized_parts,
            'bones': normalized_bones, 'rigKind': 'skinned' if skinned else 'static',
            'carrierName': CARRIER if skinned else None,
            'sourceSha256': source_sha256,
            'structuralHash': canonical_hash(structural),
            'inventoryHash': canonical_hash(normalized_parts),
            'boneHash': canonical_hash(normalized_bones)}
