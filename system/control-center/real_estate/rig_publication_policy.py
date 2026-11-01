"""Pure per-mesh rig ownership policy for Real Estate publication.

The authored house_armature may contain house sockets and the door hinge chain.
House sockets belong to house, the hinge subtree to door; publishing copies into unrelated static
meshes adds redundant, independently prunable bones to Roblox. A mesh with
actual bone influences still needs its own rig, and a separately authored rig
is never silently dropped.
"""
from __future__ import annotations

from .rig_features import DOOR_HINGE


def _with_ancestors(names: set[str], bones: dict) -> set[str]:
    retained = set()
    for name in names:
        chain = set()
        while name:
            if name in chain or name not in bones:
                raise ValueError('Real Estate skeleton has a cyclic or missing bone parent')
            chain.add(name)
            retained.add(name)
            name = bones[name].get('parent') or ''
    return retained


def _door_chain(bones: dict) -> set[str]:
    retained = {DOOR_HINGE}
    while True:
        expanded = retained | {name for name, bone in bones.items()
                               if bone.get('parent') in retained}
        if expanded == retained:
            return retained
        retained = expanded


def publication_analysis(analysis: dict) -> dict:
    """Expose the current policy to UI without persisting derived bone lists."""
    return {**analysis, 'meshes': [
        {**mesh, 'publicationBones': publish_bones_for_mesh(mesh)}
        for mesh in analysis.get('meshes', [])
    ]}


def publish_bones_for_mesh(entry: dict) -> list[dict]:
    """Required bones for this independent Roblox Model Asset.

    The full FBX authoring manifest is retained in the registry. The policy
    narrows each mesh to its owned bones and any actual skin dependencies.
    Legacy independent armatures retain their original complete bone lists.
    """
    bones = entry.get('bones') or []
    common = str(entry.get('armature') or '').casefold() == 'house_armature'
    by_name = {bone['name']: bone for bone in bones}
    # A unified authoring skeleton is split by ownership only in temporary
    # publication copies. Keep the registration manifest and original rig intact.
    if common and DOOR_HINGE in by_name:
        door = _door_chain(by_name)
        influences = set(entry.get('influencedBones') or [])
        if not influences.issubset(by_name):
            raise ValueError('Real Estate skin references bones absent from its rig')
        if entry.get('name') == 'house':
            if influences & door:
                raise ValueError('house geometry must not be weighted to door bones')
            retained = _with_ancestors(set(by_name) - door, by_name)
            if retained & door:
                raise ValueError('House socket must not be a child of the door hinge')
        elif entry.get('name') == 'door':
            retained = _with_ancestors(door | influences, by_name)
        else:
            retained = _with_ancestors(influences, by_name)
        return [bone for bone in bones if bone['name'] in retained]
    if (entry.get('name') != 'house'
            and common
            and not entry.get('influencedBones')):
        return []
    return bones
