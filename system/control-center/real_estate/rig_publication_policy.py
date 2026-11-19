"""Derive publishable bone ownership from a single authored house_armature.

Only temporary independent publication FBX copies receive pruned bone lists.
The author's rest rig, socket names, geometry and skinning are untouched.
"""
from __future__ import annotations

import hashlib

# Invalidate pre-M377 published IDs even when source FBX bytes are unchanged.
PUBLICATION_SCHEMA = 'house-independent-carrier-v4'


def publication_fingerprint(source_sha: str, *, carrier: bool) -> str:
    role = 'independent-carrier' if carrier else 'visual'
    return hashlib.sha256(f'{PUBLICATION_SCHEMA}:{role}:{source_sha}'.encode('utf-8')).hexdigest()


from .rig_features import DOOR_HINGE
from services.retired_col_mesh import strip_mesh_rows


def _with_ancestors(names: set[str], bones: dict) -> set[str]:
    kept = set()
    for name in names:
        seen = set()
        while name:
            if name in seen or name not in bones:
                raise ValueError('Real Estate skeleton has a cyclic or missing bone parent')
            seen.add(name)
            kept.add(name)
            name = bones[name].get('parent') or ''
    return kept


def _door_chain(bones: dict) -> set[str]:
    kept = {DOOR_HINGE}
    while True:
        expanded = kept | {name for name, bone in bones.items() if bone.get('parent') in kept}
        if expanded == kept:
            return kept
        kept = expanded


def primary_part(analysis: dict) -> str:
    """Deterministic visual identity only. This part never owns the house rig."""
    meshes = strip_mesh_rows(analysis).get('meshes', [])
    if not meshes:
        raise ValueError('Real Estate requires at least one visual mesh')
    return min((str(m['name']) for m in meshes), key=lambda name: (name.casefold(), name))


def carrier_bones(analysis: dict) -> list[dict]:
    """Sockets belong exclusively to an independent technical Model Asset."""
    meshes = strip_mesh_rows(analysis).get('meshes', [])
    linked = [m for m in meshes if
              str(m.get('armature') or '').casefold() == 'house_armature' and m.get('bones')]
    bones = linked[0]['bones'] if linked else analysis.get('houseArmatureBones', [])
    if not bones:
        raise ValueError('Real Estate requires house_armature Bones')
    return publish_bones_for_mesh({
        'name': 'rig_carrier', 'armature': 'house_armature',
        'bones': bones, 'influencedBones': [],
        'socketCarrier': True, 'doorSocketOwner': False,
    })


def door_socket_owner(analysis: dict) -> str | None:
    meshes = strip_mesh_rows(analysis).get('meshes', [])
    moving = [m['name'] for m in meshes if DOOR_HINGE in (m.get('influencedBones') or [])]
    if not moving:
        return None
    return 'door' if 'door' in moving else min(moving, key=str.casefold)


def publication_analysis(analysis: dict) -> dict:
    """Project the full multi-mesh registry to deterministic per-part manifests."""
    current = strip_mesh_rows(analysis)
    primary = primary_part(current)
    door = door_socket_owner(current)
    source_rigs = [m for m in current['meshes'] if
                   str(m.get('armature') or '').casefold() == 'house_armature']
    canonical_bones = (source_rigs[0]['bones'] if source_rigs
                       else current.get('houseArmatureBones', []))
    if not canonical_bones:
        raise ValueError('Real Estate requires an authored house_armature skeleton')
    entries = []
    for mesh in current['meshes']:
        # No visual Model Asset may contain the technical socket carrier.
        scoped = {**mesh,
                  'socketCarrier': False, 'doorSocketOwner': mesh['name'] == door,
                  'generatedCarrierRig': False}
        scoped['publicationBones'] = publish_bones_for_mesh(scoped)
        entries.append(scoped)
    return {**analysis, 'primaryPart': 'rig_carrier', 'doorSocketOwner': door,
            'carrierBones': carrier_bones(current), 'meshes': entries}



def validate_visual_weights(analysis: dict) -> None:
    """Only run on a new publication, not on historical catalog reads."""
    for mesh in analysis.get('meshes', []):
        influences = set(mesh.get('influencedBones') or [])
        if influences and influences != {DOOR_HINGE}:
            raise ValueError(mesh['name'] + ': static mesh has bone weights; only '
                             + DOOR_HINGE + ' is allowed on moving door/handles')


def publish_bones_for_mesh(entry: dict) -> list[dict]:
    bones = entry.get('bones') or []
    common = str(entry.get('armature') or '').casefold() == 'house_armature'
    by_name = {b['name']: b for b in bones}
    influences = set(entry.get('influencedBones') or [])
    if not influences.issubset(by_name):
        raise ValueError('Real Estate skin references bones absent from its rig')
    if not common:
        return bones  # Published legacy independent armatures are not migrated.
    door = _door_chain(by_name) if DOOR_HINGE in by_name else set()
    # Historical direct callers (before ownership flags were projected) kept
    # the whole authored rig on non-door weighted custom parts. Preserve that
    # behavior; new publication_analysis always supplies explicit flags.
    if ('socketCarrier' not in entry and 'doorSocketOwner' not in entry
            and influences and entry.get('name') not in ('house', 'door')
            and not (influences & door)):
        return bones
    # Backward compatibility for direct calls with original legacy entries.
    carrier = entry.get('socketCarrier', entry.get('name') == 'house')
    owner = entry.get('doorSocketOwner', entry.get('name') == 'door')
    if carrier:
        if influences & door:
            raise ValueError('house geometry/static socket carrier cannot have weights to a moving door')
        kept = _with_ancestors(set(by_name) - door, by_name)
        if kept & door:
            raise ValueError('static socket bone must not be under door hinge')
        if not kept and by_name:
            kept = _with_ancestors({DOOR_HINGE}, by_name)
    elif influences:
        kept = _with_ancestors(influences, by_name)
        if owner:
            kept |= _with_ancestors(door, by_name)
    else:
        kept = set()
    return [bone for bone in bones if bone['name'] in kept]
