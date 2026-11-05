"""Shared Blender mesh/armature report for Real Estate and Location Assets.

Invoked inside Blender only. No mutation of FBX/mesh weights/pivots.
"""
from __future__ import annotations


def describe_mesh(bpy, mesh, rig, role=None):
    bones = [{
        'name': b.name,
        'parent': b.parent.name if b.parent else '',
        'matrixLocal': [round(float(v), 7) for row in b.matrix_local for v in row],
    } for b in sorted(rig.data.bones, key=lambda bone: bone.name.casefold())] if rig else []
    named = {bone['name'] for bone in bones}
    groups = {group.index: group.name for group in mesh.vertex_groups}
    influenced = sorted({groups.get(vgroup.group)
                         for vertex in mesh.data.vertices for vgroup in vertex.groups
                         if vgroup.weight > 0 and groups.get(vgroup.group) in named})
    entry = {'name': mesh.name, 'armature': rig.name if rig else '',
             'vertices': len(mesh.data.vertices), 'bones': bones, 'influencedBones': influenced}
    if role is not None:
        entry['role'] = role
    return entry
