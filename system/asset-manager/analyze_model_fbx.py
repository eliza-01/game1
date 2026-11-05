"""Location FBX inspector: names, collider/glass roles and every authored bone."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from fbx_mesh_inspection import describe_mesh
from real_estate_rig_discovery import find_rig
from services.mesh_authoring_policy import is_collision_mesh, location_mesh_profile


def analyze(source):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    meshes = sorted((o for o in bpy.context.scene.objects if o.type == 'MESH'),
                    key=lambda o: (o.name.casefold(), o.name))
    if not meshes:
        raise ValueError('Location FBX contains no MESH objects')
    if len({o.name.casefold() for o in meshes}) != len(meshes):
        raise ValueError('Location FBX contains ambiguous mesh names differing only by case')
    has_collider = any(is_collision_mesh(o.name) for o in meshes)
    records = []
    for mesh in meshes:
        rig = find_rig(bpy, mesh, mesh.name)
        profile = location_mesh_profile(mesh.name, has_collider=has_collider)
        record = describe_mesh(bpy, mesh, rig, profile['role'])
        record['physics'] = profile
        records.append(record)
    linked = {entry['armature'] for entry in records if entry['armature']}
    orphaned = sorted(o.name for o in bpy.context.scene.objects
                      if o.type == 'ARMATURE' and len(o.data.bones) and o.name not in linked)
    armatures = sorted({entry['armature'] for entry in records if entry['armature']})
    return {'schemaVersion': 1, 'meshes': records, 'hasCollider': has_collider,
            'armatures': armatures, 'unassignedArmatures': orphaned}


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) != 2:
        raise ValueError('expected source.fbx report.json')
    Path(args[1]).write_text(json.dumps(analyze(Path(args[0])), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
