"""Blender entry: inspect the required house and optional door with any bones."""
import bpy
import json
import sys
from pathlib import Path

# Blender --python does not guarantee that the script directory is on sys.path.
# Resolve adjacent helper modules explicitly, just as the publication entrypoint does.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_estate_rig_discovery import find_mesh, find_rig
from real_estate_import_rigs import restore_authored_rigs
from model_publication import assert_skin_complete
from real_estate_part_placement import inspect_placements
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from fbx_mesh_inspection import describe_mesh
from services.retired_col_mesh import retired


def analyze(source, only_part=None, extract=False):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    restore_authored_rigs(bpy, source)
    meshes = []
    if only_part is None and any(obj.type == 'MESH' and obj.name == 'rig_carrier'
                                 for obj in bpy.context.scene.objects):
        raise RuntimeError('rig_carrier is a publication-only technical mesh; remove it from author FBX')
    present = [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH'
               and not retired(obj.name) and obj.name != 'rig_carrier']
    expected = [only_part] if only_part is not None else sorted(
        present, key=lambda name: (name != 'house', name.casefold(), name))
    if not present and only_part != 'rig_carrier':
        raise RuntimeError('Real Estate FBX contains no visible Mesh objects')
    if only_part is not None and retired(only_part):
        raise RuntimeError('COL_ mesh is retired; author collision with Roblox Parts')
    if only_part is not None and only_part != 'rig_carrier' and only_part not in present:
        raise RuntimeError(f"Expected mesh {only_part} is absent; found: {', '.join(present)}")
    if only_part is not None and not extract and (present != ([] if only_part == 'rig_carrier' else [only_part])):
        raise RuntimeError(f"Expected only staged mesh {only_part}; found: {', '.join(present)}.")
    if len({name.casefold() for name in present}) != len(present):
        raise RuntimeError("FBX contains mesh names that differ only by case.")
    from real_estate_part_placement import inspect_origin_placements
    armatures = [obj for obj in bpy.context.scene.objects
                 if obj.type == 'ARMATURE' and obj.name.casefold() == 'house_armature']
    if len(armatures) != 1 and only_part is None:
        raise RuntimeError('New Real Estate FBX requires one house_armature')
    placements = inspect_origin_placements(armatures[0],
                    [find_mesh(bpy, name) for name in expected if name != 'rig_carrier']) if len(armatures) == 1 else {}
    for name in expected:
        if name == 'rig_carrier':
            continue
        mesh = find_mesh(bpy, name)
        rig = find_rig(bpy, mesh, name)
        record = describe_mesh(bpy, mesh, rig)
        if name in placements:
            record['authoredPlacement'] = placements[name]
        meshes.append(record)
    # In staged inspection preserve the carrier's distinct Bone ownership,
    # while never treating it as an authored visual mesh.
    if only_part is not None:
        carriers = [obj for obj in bpy.context.scene.objects
                    if obj.type == 'MESH' and obj.name == 'rig_carrier']
        if len(carriers) > 1:
            raise RuntimeError('Published Real Estate rig has duplicate rig_carrier')
        if carriers:
            carrier = carriers[0]
            meshes.append(describe_mesh(bpy, carrier, find_rig(bpy, carrier, 'rig_carrier')))
        if only_part == 'rig_carrier' and len(carriers) != 1:
            raise RuntimeError('Independent socket Model Asset has no rig_carrier')
    if only_part is None:
        from real_estate.rig_publication_policy import publication_analysis
        meshes = publication_analysis({'meshes': meshes,
            'houseArmatureBones': [{'name': bone.name,
                                   'parent': bone.parent.name if bone.parent else '',
                                   'matrixLocal': [float(v) for row in bone.matrix_local for v in row]}
                                  for bone in armatures[0].data.bones]})['meshes']
    # Additional authored armatures are not mandatory Real Estate meshes.
    # Report unlinked ones rather than failing inspection or silently hiding them.
    registered = {entry['armature'] for entry in meshes if entry['armature']}
    orphaned = [obj.name for obj in bpy.context.scene.objects
                if obj.type == 'ARMATURE' and len(obj.data.bones) and obj.name not in registered]
    return {'schemaVersion': 1, 'meshes': meshes, 'unassignedArmatures': orphaned}


args = sys.argv[sys.argv.index('--') + 1:]
if len(args) not in (2, 3, 4):
    raise RuntimeError('usage: blender ... -- source.fbx analysis.json [mesh_name]')
Path(args[1]).write_text(json.dumps(analyze(Path(args[0]), args[2] if len(args) >= 3 else None, len(args) == 4 and args[3] == "extract"), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
