"""Shared Blender rig_carrier authoring for Character and skinned Location FBX.

This is source-FBX authoring, never a Roblox Studio repair or hidden publication
fallback. Both domains use the same tiny, bone-weighted triangle geometry and
armature binding; domain-specific rig validation belongs to their callers.
"""
import bpy
from mathutils import Vector


def create_rig_carrier(armature):
    if armature.type != 'ARMATURE' or not armature.data.bones:
        raise ValueError('rig_carrier requires an existing armature with Bones')
    if any(obj.type == 'MESH' and obj.name.casefold() == 'rig_carrier'
           for obj in bpy.context.scene.objects):
        raise ValueError('rig_carrier already exists in Blender scene')
    vertices = []
    faces = []
    for bone in armature.data.bones:
        point = bone.head_local
        start = len(vertices)
        # Character's original tested geometry: one nondegenerate triangle per Bone.
        vertices.extend((tuple(point), tuple(point + Vector((.001, 0, 0))),
                         tuple(point + Vector((0, .001, 0)))))
        faces.append((start, start + 1, start + 2))
    data = bpy.data.meshes.new('rig_carrier')
    data.from_pydata(vertices, [], faces)
    data.update()
    carrier = bpy.data.objects.new('rig_carrier', data)
    bpy.context.scene.collection.objects.link(carrier)
    carrier.parent = armature
    carrier.matrix_world = armature.matrix_world.copy()
    for index, bone in enumerate(armature.data.bones):
        carrier.vertex_groups.new(name=bone.name).add(
            [index * 3, index * 3 + 1, index * 3 + 2], 1.0, 'REPLACE')
    modifier = carrier.modifiers.new('rig_bind', 'ARMATURE')
    modifier.object = armature
    return carrier
