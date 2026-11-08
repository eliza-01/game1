"""Explicit Blender authoring conversion: source FBX -> NEW carrier-authored FBX.

Never overwrite the artist's FBX; never create a synthetic carrier in Studio.
Usage: blender -b -t 1 --python location_rig_authoring_fbx.py -- SOURCE.fbx OUTPUT.fbx MANIFEST.json
After conversion the new FBX is the authoring source for publication.
"""
import hashlib
import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_rig_carrier import create_rig_carrier
from model_publication import (
    assert_skin_complete, clean_scene, export_model, linked_meshes, prepare_rig,
)
from location_rig_contract import CARRIER, ROOT, role, validate


def bone_rows(armature):
    return [{'name': bone.name, 'parent': bone.parent.name if bone.parent else '',
             'matrix': [round(float(v), 7) for row in bone.matrix_local for v in row]}
            for bone in armature.data.bones]


def ensure_armature(objects):
    rigs = [o for o in objects if o.type == 'ARMATURE' and len(o.data.bones)]
    if len(rigs) > 1:
        raise ValueError('multiple armatures: explicit manual authoring required')
    if rigs:
        return rigs[0]
    # This tool is exclusively for a REAL skeleton. A static Location needs no
    # carrier, and creating a dummy Bone would change the author's geometry.
    raise ValueError('FBX has no Bones; static Location can be published without rig_carrier')


def describe(objects, rig):
    return validate([{'name': obj.name, 'vertices': len(obj.data.vertices)}
                     for obj in objects if obj.type == 'MESH'], bone_rows(rig))


def main(source, output, report_path):
    source, output, report_path = (Path(p).resolve() for p in (source, output, report_path))
    if source == output or not source.is_file() or source.suffix.lower() != '.fbx':
        raise ValueError('input FBX must exist and output must be a distinct FBX')
    if output.suffix.lower() != '.fbx' or output.exists():
        raise ValueError('authoring output must be a new, nonexisting .fbx')
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    objects = [o for o in bpy.context.scene.objects if o.type in {'MESH', 'ARMATURE'}]
    if not any(o.type == 'MESH' and role(o.name) == 'visual' for o in objects):
        raise ValueError('no visual geometry')
    if any(o.name == ROOT for o in objects):
        raise ValueError('source contains RootPart; manual authoring cleanup required')
    carrier = [o for o in objects if o.name.casefold() == CARRIER]
    if len(carrier) > 1:
        raise ValueError('duplicate rig_carrier')
    rig = ensure_armature(objects)
    if not carrier:
        create_rig_carrier(rig)
    objects = sorted((o for o in bpy.context.scene.objects if o.type in {'MESH', 'ARMATURE'}), key=lambda o: o.name)
    # The new carrier belongs to this authoring FBX. It is not a staging-only
    # Roblox MeshPart, and is never synthesized while placing a model.
    manifest = describe(objects, rig)
    # The original FBX may contain partial visual skin (e.g. unweighted vertices).
    # Canonical authoring, unlike publication staging, may normalize that skin.
    # Reuse Character's tested planner on this NEW FBX revision only; the
    # registered source is never modified and no Studio repair is performed.
    skin_report = prepare_rig(rig, linked_meshes(rig))
    export_model(output, objects, no_textures=True)
    # Validate a real FBX round-trip before returning the authored file.
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(output), use_anim=False)
    published_objects = [o for o in bpy.context.scene.objects if o.type in {'MESH', 'ARMATURE'}]
    rigs = [o for o in published_objects if o.type == 'ARMATURE' and len(o.data.bones)]
    if len(rigs) != 1:
        raise ValueError('export lost canonical armature')
    reopened = describe(published_objects, rigs[0])
    assert_skin_complete(rigs[0], linked_meshes(rigs[0]))
    if reopened['boneHash'] != manifest['boneHash'] or reopened['inventoryHash'] != manifest['inventoryHash']:
        raise ValueError('FBX round-trip changed carrier or Bone inventory')
    reopened['sourceSha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    reopened['skinPreparation'] = skin_report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(reopened, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:]
    if len(argv) != 3:
        raise ValueError('expected SOURCE.fbx OUTPUT.fbx MANIFEST.json')
    main(*argv)
