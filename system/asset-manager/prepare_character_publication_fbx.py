"""Blender background entry point for Roblox-safe character publication FBX.

The canonical/source FBX is never modified. This temporary publication copy only
strengthens bone influences that are likely to be treated as zero/near-zero by
Roblox's automated Model FBX importer. Bone rest transforms and hierarchy are
snapshotted and verified unchanged before export.
"""

import bpy
import json
import sys
from pathlib import Path

SURVIVAL_WEIGHT = 0.05
COMPARE_EPSILON = 1e-6
POSITIVE_EPSILON = 1e-8
ROBLOX_MAX_INFLUENCES = 4


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


def strengthen_weak_bones(armature, meshes):
    bones = list(armature.data.bones)
    bone_names = {bone.name for bone in bones}
    max_weight = {bone.name: 0.0 for bone in bones}
    vertex_cache = []

    for mesh_obj in meshes:
        index_to_name = {
            group.index: group.name
            for group in mesh_obj.vertex_groups
            if group.name in bone_names
        }
        for vertex in mesh_obj.data.vertices:
            weights = active_bone_weights(mesh_obj, vertex, index_to_name)
            for bone_name, weight in weights.items():
                if weight > max_weight[bone_name]:
                    max_weight[bone_name] = weight
            vertex_cache.append(
                {
                    "mesh": mesh_obj,
                    "vertex": vertex,
                    "weights": weights,
                    "world": mesh_obj.matrix_world @ vertex.co,
                }
            )

    weak_bones = [
        bone for bone in bones
        if max_weight[bone.name] + COMPARE_EPSILON < SURVIVAL_WEIGHT
    ]
    patched = []

    for bone in bones:
        bone.use_deform = True

    for bone in weak_bones:
        candidates = []
        bone_world = armature.matrix_world @ bone.head_local
        for item in vertex_cache:
            weights = item["weights"]
            already_present = bone.name in weights and weights[bone.name] > POSITIVE_EPSILON
            positive_count = len(weights)
            fits = positive_count <= ROBLOX_MAX_INFLUENCES if already_present else positive_count < ROBLOX_MAX_INFLUENCES
            group = item["mesh"].vertex_groups.get(bone.name)
            unlocked = group is None or not group.lock_weight
            if fits and unlocked:
                # Prefer the vertex that already carries this bone's tiny service
                # influence; otherwise use the nearest safe vertex to the bone head.
                candidates.append(
                    (
                        0 if already_present else 1,
                        (item["world"] - bone_world).length_squared,
                        item,
                    )
                )
        if not candidates:
            raise RuntimeError(
                f"no <=4-influence vertex is available to preserve bone {bone.name!r}"
            )
        _, _, chosen = min(candidates, key=lambda value: (value[0], value[1]))
        mesh_obj = chosen["mesh"]
        group = mesh_obj.vertex_groups.get(bone.name)
        if group is None:
            group = mesh_obj.vertex_groups.new(name=bone.name)
        group.add([chosen["vertex"].index], SURVIVAL_WEIGHT, "REPLACE")
        chosen["weights"][bone.name] = SURVIVAL_WEIGHT
        patched.append(
            {
                "bone": bone.name,
                "mesh": mesh_obj.name,
                "vertex": int(chosen["vertex"].index),
                "previousMaxWeight": max_weight[bone.name],
                "publicationWeight": SURVIVAL_WEIGHT,
            }
        )

    return patched


def main(source: Path, output: Path, report_path: Path):
    source = source.resolve()
    output = output.resolve()
    report_path = report_path.resolve()
    if not source.is_file() or source.suffix.lower() != ".fbx":
        raise RuntimeError("character publication preparation requires an FBX file")

    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)

    armatures = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"),
        key=lambda obj: obj.name.casefold(),
    )
    if not armatures:
        raise RuntimeError("FBX contains no armature")
    armature = max(armatures, key=lambda obj: len(obj.data.bones))
    meshes = linked_meshes(armature)
    if not meshes:
        raise RuntimeError("FBX armature has no linked skinned mesh")

    before = rest_snapshot(armature)
    over_limit_before = count_over_limit(armature, meshes)
    patched = strengthen_weak_bones(armature, meshes)
    over_limit_after = count_over_limit(armature, meshes)
    assert_rest_unchanged(armature, before)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in [armature, *meshes]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(output),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        bake_anim=False,
        add_leaf_bones=False,
        use_armature_deform_only=False,
        axis_forward="-Z",
        axis_up="Y",
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        use_space_transform=True,
        bake_space_transform=False,
    )
    if not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError("publication FBX was not written")

    report_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "mode": "roblox-open-cloud-bone-survival",
                "armature": armature.name,
                "boneCount": len(armature.data.bones),
                "meshNames": [obj.name for obj in meshes],
                "survivalWeight": SURVIVAL_WEIGHT,
                "patchedBoneCount": len(patched),
                "patchedBones": patched,
                "verticesOverFourBefore": over_limit_before,
                "verticesOverFourAfter": over_limit_after,
                "restTransformsChanged": False,
                "fbxScaleMode": "FBX_SCALE_UNITS",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


args = sys.argv[sys.argv.index("--") + 1 :]
if len(args) != 3:
    raise RuntimeError(
        "usage: blender --background --python prepare_character_publication_fbx.py -- input.fbx output.fbx report.json"
    )
source, output, report = map(Path, args)
main(source, output, report)
