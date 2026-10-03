"""Blender background entry point for deterministic game1 character rig analysis."""

import bpy
import hashlib
import json
import struct
import sys
from pathlib import Path


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.armatures, bpy.data.meshes, bpy.data.materials):
        for item in list(collection):
            collection.remove(item)


def rounded_matrix(matrix):
    return [round(value, 7) for row in matrix for value in row]


def mesh_signature(obj, group_names):
    digest = hashlib.sha256()
    digest.update(obj.name.encode("utf-8"))
    for vertex in obj.data.vertices:
        digest.update(struct.pack("<3d", *(round(float(v), 8) for v in vertex.co)))
        weights = sorted(
            (group_names.get(group.group, ""), round(float(group.weight), 8))
            for group in vertex.groups
            if group.weight > 0 and group_names.get(group.group)
        )
        digest.update(json.dumps(weights, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for polygon in obj.data.polygons:
        digest.update(struct.pack("<I", len(polygon.vertices)))
        for index in polygon.vertices:
            digest.update(struct.pack("<I", int(index)))
    return digest.hexdigest()


def analyze(path: Path):
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)

    armatures = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"),
        key=lambda obj: obj.name.casefold(),
    )
    if not armatures:
        raise RuntimeError("FBX contains no armature.")

    armature = max(armatures, key=lambda obj: len(obj.data.bones))
    bones = []
    for bone in sorted(armature.data.bones, key=lambda item: item.name.casefold()):
        bones.append(
            {
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else "",
                "matrixLocal": rounded_matrix(bone.matrix_local),
            }
        )

    if not bones:
        raise RuntimeError("Character armature contains no bones.")

    skeleton_json = json.dumps(bones, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    structure = [{"name": bone["name"], "parent": bone["parent"]} for bone in bones]
    structure_json = json.dumps(structure, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    bone_names = {bone["name"] for bone in bones}
    meshes = []
    for obj in sorted(
        (item for item in bpy.context.scene.objects if item.type == "MESH"),
        key=lambda item: item.name.casefold(),
    ):
        group_names = {group.index: group.name for group in obj.vertex_groups}
        influenced = set()
        unweighted = 0
        max_influences = 0
        for vertex in obj.data.vertices:
            active = [
                group_names[item.group]
                for item in vertex.groups
                if item.weight > 0 and group_names.get(item.group) in bone_names
            ]
            influenced.update(active)
            max_influences = max(max_influences, len(active))
            if not active:
                unweighted += 1
        meshes.append(
            {
                "name": obj.name,
                "vertices": len(obj.data.vertices),
                "influencedBones": sorted(influenced, key=str.casefold),
                "unweightedVertices": unweighted,
                "maxInfluences": max_influences,
                "meshContentSignature": mesh_signature(obj, group_names),
            }
        )

    if not meshes:
        raise RuntimeError("FBX contains an armature but no mesh.")

    influenced_meshes = sum(1 for mesh in meshes if mesh["influencedBones"])
    if influenced_meshes == 0:
        raise RuntimeError("FBX mesh is not skinned to the armature.")

    return {
        "schemaVersion": 1,
        "file": str(path),
        "armature": armature.name,
        "boneCount": len(bones),
        "meshCount": len(meshes),
        "skinnedMeshCount": influenced_meshes,
        "skeletonSignature": hashlib.sha256(skeleton_json.encode("utf-8")).hexdigest(),
        "skeletonStructureSignature": hashlib.sha256(structure_json.encode("utf-8")).hexdigest(),
        "bones": bones,
        "meshes": meshes,
    }


args = sys.argv[sys.argv.index("--") + 1 :]
if len(args) != 2:
    raise RuntimeError("usage: blender --background --python analyze_character_fbx.py -- input.fbx output.json")
source, output = map(Path, args)
output.write_text(json.dumps(analyze(source), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
