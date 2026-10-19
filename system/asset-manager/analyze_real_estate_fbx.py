"""Blender entry: inspect the required house and optional door with any bones."""
import bpy
import json
import sys
from pathlib import Path

# Blender --python does not guarantee that the script directory is on sys.path.
# Resolve adjacent helper modules explicitly, just as the publication entrypoint does.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_estate_rig_discovery import find_mesh, find_rig


def analyze(source, only_part=None):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    meshes = []
    present = [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH']
    expected = [only_part] if only_part is not None else sorted(
        present, key=lambda name: (name != 'house', name.casefold(), name))
    if not present or (only_part is None and 'house' not in present):
        raise RuntimeError(f"Required mesh house is missing. Found: {', '.join(present) or 'none'}.")
    if only_part is not None and (present != [only_part]):
        raise RuntimeError(f"Expected only staged mesh {only_part}; found: {', '.join(present)}.")
    if len({name.casefold() for name in present}) != len(present):
        raise RuntimeError("FBX contains mesh names that differ only by case.")
    for name in expected:
        mesh = find_mesh(bpy, name)
        rig = find_rig(bpy, mesh, name)
        if name == 'house' and (not rig or rig.name.casefold() != 'house_armature'):
            raise RuntimeError('Required house_armature is missing or not assigned to mesh house.')
        rig_name = rig.name if rig else ''
        bones = [{
            'name': b.name,
            'parent': b.parent.name if b.parent else '',
            'matrixLocal': [round(float(v), 7) for row in b.matrix_local for v in row],
        } for b in sorted(rig.data.bones, key=lambda b: b.name.casefold())] if rig else []
        group_names = {group.index: group.name for group in mesh.vertex_groups}
        influences = sorted({group_names.get(group.group) for v in mesh.data.vertices for group in v.groups
                             if group.weight > 0 and group_names.get(group.group) in {b['name'] for b in bones}})
        meshes.append({'name': name, 'armature': rig_name, 'vertices': len(mesh.data.vertices),
                       'bones': bones, 'influencedBones': influences})
    # Additional authored armatures are not mandatory Real Estate meshes.
    # Report unlinked ones rather than failing inspection or silently hiding them.
    registered = {entry['armature'] for entry in meshes if entry['armature']}
    orphaned = [obj.name for obj in bpy.context.scene.objects
                if obj.type == 'ARMATURE' and len(obj.data.bones) and obj.name not in registered]
    return {'schemaVersion': 1, 'meshes': meshes, 'unassignedArmatures': orphaned}


args = sys.argv[sys.argv.index('--') + 1:]
if len(args) not in (2, 3):
    raise RuntimeError('usage: blender ... -- source.fbx analysis.json [mesh_name]')
Path(args[1]).write_text(json.dumps(analyze(Path(args[0]), args[2] if len(args) == 3 else None), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
