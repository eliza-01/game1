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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import (
    SURVIVAL_WEIGHT, clean_scene, linked_meshes, rest_snapshot,
    assert_rest_unchanged, count_over_limit, prepare_rig, export_model,
)


def main(source: Path, output: Path, report_path: Path):
    source = source.resolve()
    output = output.resolve()
    report_path = report_path.resolve()
    if source == output:
        raise ValueError("publication output must differ from source")
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
    report = prepare_rig(armature, meshes)
    over_limit_after = count_over_limit(armature, meshes)
    assert_rest_unchanged(armature, before)

    export_model(output, [armature, *meshes])

    report_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "mode": "roblox-open-cloud-bone-survival",
                "armature": armature.name,
                "boneCount": len(armature.data.bones),
                "meshNames": [obj.name for obj in meshes],
                "survivalWeight": SURVIVAL_WEIGHT,
                "patchedBoneCount": report["patchedBoneCount"],
                "patchedBones": report["patchedBones"],
                "survivingBoneCount": report["survivingBoneCount"],
                "prunedVertices": report["prunedVertices"],
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
