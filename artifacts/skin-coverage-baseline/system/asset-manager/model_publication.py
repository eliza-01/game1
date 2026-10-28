"""Shared Blender mechanism for every Roblox Model FBX publication.

Only staging scenes may call this module. Source FBX and artist scenes stay intact.
The policy matches character publication: all authored bones get >=5% coverage
on at least one vertex; at most four influences. Rest transforms never change.
"""
import bpy
from pathlib import Path
from bone_weight_survival import MAX_INFLUENCES, SURVIVAL_WEIGHT, plan_publication_weights

POSITIVE_EPSILON = 1e-8
ROBLOX_MAX_INFLUENCES = MAX_INFLUENCES

def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.armatures, bpy.data.meshes, bpy.data.materials):
        for item in list(collection):
            collection.remove(item)


def linked_meshes(armature):
    result = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        linked = obj.parent == armature
        if not linked:
            linked = any(
                mod.type == "ARMATURE" and getattr(mod, "object", None) == armature
                for mod in obj.modifiers
            )
        if linked:
            result.append(obj)
    return sorted(result, key=lambda obj: obj.name.casefold())


def rest_snapshot(armature):
    snapshot = {}
    for bone in armature.data.bones:
        snapshot[bone.name] = {
            "parent": bone.parent.name if bone.parent else "",
            "head": tuple(float(v) for v in bone.head_local),
            "tail": tuple(float(v) for v in bone.tail_local),
            "matrix": tuple(float(v) for row in bone.matrix_local for v in row),
        }
    return snapshot


def assert_rest_unchanged(armature, before):
    after = rest_snapshot(armature)
    if before.keys() != after.keys():
        raise RuntimeError("publication preparation changed the bone set")
    for name, old in before.items():
        new = after[name]
        if old["parent"] != new["parent"]:
            raise RuntimeError(f"publication preparation changed parent of bone {name!r}")
        for field in ("head", "tail", "matrix"):
            if any(abs(a - b) > 1e-10 for a, b in zip(old[field], new[field])):
                raise RuntimeError(
                    f"publication preparation changed rest transform of bone {name!r} ({field})"
                )


def active_bone_weights(mesh_obj, vertex, index_to_name):
    result = {}
    for membership in vertex.groups:
        bone_name = index_to_name.get(membership.group)
        if bone_name is None:
            continue
        weight = float(membership.weight)
        if weight > POSITIVE_EPSILON:
            result[bone_name] = weight
    return result


def count_over_limit(armature, meshes):
    bone_names = {bone.name for bone in armature.data.bones}
    total = 0
    for mesh_obj in meshes:
        index_to_name = {
            group.index: group.name
            for group in mesh_obj.vertex_groups
            if group.name in bone_names
        }
        for vertex in mesh_obj.data.vertices:
            weights = active_bone_weights(mesh_obj, vertex, index_to_name)
            if len(weights) > ROBLOX_MAX_INFLUENCES:
                total += 1
    return total


def prepare_publication_weights(armature, meshes):
    bones = list(armature.data.bones)
    names = {bone.name for bone in bones}
    heads = {
        bone.name: tuple(armature.matrix_world @ bone.head_local)
        for bone in bones
    }
    vertices = []
    for mesh in meshes:
        group_names = {
            group.index: group.name for group in mesh.vertex_groups
            if group.name in names
        }
        for vertex in mesh.data.vertices:
            weights = active_bone_weights(mesh, vertex, group_names)
            vertices.append({
                'mesh': mesh.name,
                'index': vertex.index,
                'object': mesh,
                'position': tuple(mesh.matrix_world @ vertex.co),
                'original': weights,
                'weights': dict(weights),
            })

    report = plan_publication_weights(heads, vertices)
    for bone in bones:
        bone.use_deform = True
    for vertex in vertices:
        old = vertex['original']
        new = vertex['weights']
        if old == new:
            continue
        mesh = vertex['object']
        index = vertex['index']
        # Remove dropped influences, including the fifth/seventh FBX weight.
        # Never touch non-armature vertex groups.
        for name in old.keys() - new.keys():
            group = mesh.vertex_groups.get(name)
            if group:
                group.remove([index])
        for name, weight in new.items():
            group = mesh.vertex_groups.get(name)
            if group is None:
                group = mesh.vertex_groups.new(name=name)
            if not old.get(name) or abs(old[name] - weight) > 1e-7:
                group.add([index], weight, 'REPLACE')
    if count_over_limit(armature, meshes) != 0:
        raise RuntimeError('publication skin still exceeds four influences per vertex')
    return report


def prepare_rig(armature, meshes):
    before = rest_snapshot(armature)
    if not meshes:
        raise ValueError(f"Armature {armature.name} has no linked mesh")
    report = prepare_publication_weights(armature, meshes)
    assert_rest_unchanged(armature, before)
    return report


def export_model(output, objects, *, embed_textures=False):
    """One export contract for characters, estates and other model assets."""
    output = Path(output)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.export_scene.fbx(
        filepath=str(output), use_selection=True, object_types={"ARMATURE", "MESH"},
        bake_anim=False, add_leaf_bones=False, use_armature_deform_only=False,
        axis_forward="-Z", axis_up="Y", global_scale=1.0,
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        use_space_transform=True, bake_space_transform=False,
        path_mode="COPY" if embed_textures else "AUTO", embed_textures=embed_textures,
    )
    if result != {'FINISHED'} or not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError("publication FBX was not written")
