"""Prepare independent present Real Estate rigs. Do not modify source FBX."""
import bpy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import prepare_rig, export_model
from real_estate_rig_discovery import find_mesh, find_rig
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from real_estate.collision_policy import is_collision_mesh


def main(source, output, texture_config, selected_part=None):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    reports = {}
    rigs = {}
    authored = [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if selected_part is None and 'house' not in authored:
        raise RuntimeError('The FBX must contain a mesh named house')
    if selected_part is not None and selected_part not in authored:
        raise RuntimeError('Selected mesh ' + selected_part + ' not present in the FBX')
    parts = (selected_part,) if selected_part else tuple(sorted(authored, key=lambda name: (name != 'house', name.casefold(), name)))
    for part in parts:
        mesh = find_mesh(bpy, part)
        rig = find_rig(bpy, mesh, part)
        if part == 'house' and (not rig or rig.name.casefold() != 'house_armature'):
            raise RuntimeError('Required house_armature is missing or not assigned to mesh house.')
        rig_name = rig.name if rig else ''
        rigs[part] = rig
        # Interaction bones are optional. Preserve every bone if present, but
        # do not synthesize dummy bones for meshes with no rig / empty rig.
        bones = list(rig.data.bones) if rig else []
        if bones:
            if not any(mod.type == 'ARMATURE' and mod.object == rig for mod in mesh.modifiers):
                mod = mesh.modifiers.new(name='Game1RealEstateRig', type='ARMATURE')
                mod.object = rig
            reports[part] = prepare_rig(rig, [mesh])
        else:
            reports[part] = {'status': 'no_bones', 'preservedBones': 0}
        # Collision geometry is published as a Model Asset only. Never attach
        # a fake image / atlas merely to get a physics mesh through Open Cloud.
        if is_collision_mesh(part):
            mesh.data.materials.clear()
            continue
        image = bpy.data.images.load(str(texture_config[part]), check_existing=True)
        material = bpy.data.materials.new(name=f'Game1_{part}')
        material.use_nodes = True
        nodes = material.node_tree.nodes
        shader = nodes.get('Principled BSDF')
        texture_node = nodes.new('ShaderNodeTexImage')
        texture_node.image = image
        material.node_tree.links.new(texture_node.outputs['Color'], shader.inputs['Base Color'])
        mesh.data.materials.clear()
        mesh.data.materials.append(material)
    # Roblox merges independent armatures in a single Model Asset into one
    # RootPart. Publish each mesh/armature pair as a SEPARATE Model Asset.
    output.mkdir(parents=True, exist_ok=True)
    for part in parts:
        mesh = find_mesh(bpy, part)
        rig = rigs[part]
        objects = [mesh, rig] if rig and len(rig.data.bones) else [mesh]
        export_model(output / f'{part}.fbx', objects, embed_textures=True)
    return {'schemaVersion': 2, 'parts': reports, 'textureMode': 'embedded',
            'rigAssets': {part: f'{part}.fbx' for part in parts}}

args = sys.argv[sys.argv.index('--') + 1:]
if len(args) not in (4, 5):
    raise RuntimeError('usage: blender ... -- source.fbx target.fbx textures.json report.json')
report = main(Path(args[0]), Path(args[1]), json.loads(Path(args[2]).read_text(encoding='utf-8')), args[4] if len(args) == 5 else None)
Path(args[3]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
