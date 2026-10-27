"""Pure authoring contract for Real Estate bones, sockets and rigid hinges.

This module does not infer parenting from Blender names, nor implement gameplay.
Existing legacy rigs remain loadable, even when they have no hinge marker.
"""
from __future__ import annotations

HOUSE_SOCKETS = frozenset({
    'chimney_01_socket', 'elevator_01_socket',
    'house_floor_01_spawn_01_socket', 'house_floor_02_spawn_01_socket',
    'chest_01_socket', 'land_spawn_01_socket',
})
DOOR_HINGE = 'door_01_hinge_socket'
DOOR_CHILD_SOCKETS = frozenset({
    'door_01_handle_inside_socket', 'door_01_handle_outside_socket',
    'door_01_padlock_01_socket',
})


def bone_role(part: str, name: str) -> str:
    if part == 'door' and name == DOOR_HINGE:
        return 'hinge'
    if name.endswith('_socket'):
        return 'socket'
    return 'bone'


def feature_warnings(analysis: dict) -> list[dict]:
    """Report provable inconsistencies, not absence of optional features."""
    result = []
    for mesh in analysis.get('meshes', []):
        if mesh.get('name') != 'door':
            continue
        bones = {b.get('name'): b for b in mesh.get('bones', []) if isinstance(b, dict)}
        if DOOR_HINGE not in bones:
            # Legacy door_bone rigs and non-rigged doors still import. The UI
            # labels them as legacy, without a misleading missing_door_bone.
            continue
        if bones[DOOR_HINGE].get('parent'):
            result.append({'part': 'door', 'code': 'door_hinge_not_root',
                           'message': f'{DOOR_HINGE} must be a root bone (pivot of the entire door).'})
        for child in sorted(DOOR_CHILD_SOCKETS.intersection(bones)):
            if bones[child].get('parent') != DOOR_HINGE:
                result.append({'part': 'door', 'code': 'door_socket_outside_hinge',
                               'message': f'{child} must be parented to {DOOR_HINGE}.'})
        influences = set(mesh.get('influencedBones') or [])
        if DOOR_HINGE not in influences:
            result.append({'part': 'door', 'code': 'door_hinge_unweighted',
                           'message': f'{DOOR_HINGE} must carry the rigid door mesh weights.'})
        stray = sorted((influences & DOOR_CHILD_SOCKETS))
        if stray:
            result.append({'part': 'door', 'code': 'door_socket_deforms_mesh',
                           'message': 'Interaction sockets must not deform the door: ' + ', '.join(stray)})
    return result
