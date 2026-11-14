"""Prepare independent present Real Estate rigs. Do not modify source FBX."""
import bpy
import json
import sys
from pathlib import Path
from contextlib import nullcontext
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import prepare_rig, export_model
from real_estate_rig_discovery import find_mesh, find_rig
from real_estate_import_rigs import restore_authored_rigs
from real_estate_staging_rig import isolated_rig
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from services.retired_col_mesh import retired
from real_estate.rig_publication_policy import publish_bones_for_mesh


def main(source, output, texture_config, selected_part=None):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    restore_authored_rigs(bpy, source)
    reports = {}
    output.mkdir(parents=True, exist_ok=True)
    authored = [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH' and not retired(obj.name)]
    if selected_part is None and 'house' not in authored:
        raise RuntimeError('The FBX must contain a mesh named house')
    if selected_part is not None and retired(selected_part):
        raise RuntimeError('retired COL mesh is not publishable')
    if selected_part is not None and selected_part not in authored:
        raise RuntimeError('Selected mesh ' + selected_part + ' not present in the FBX')
    parts = (selected_part,) if selected_part else tuple(sorted(authored, key=lambda name: (name != 'house', name.casefold(), name)))
    for part in parts:
        mesh = find_mesh(bpy, part)
        rig = find_rig(bpy, mesh, part)
        if part == 'house' and (not rig or rig.name.casefold() != 'house_armature'):
            raise RuntimeError('Required house_armature is missing or not assigned to mesh house.')
        rig_name = rig.name if rig else ''
        # Interaction bones are optional. Preserve every bone if present, but
        # do not synthesize dummy bones for meshes with no rig / empty rig.
        bones = list(rig.data.bones) if rig else []
        authored_influences = set()
        if bones:
            bone_names = {bone.name for bone in bones}
            group_names = {group.index: group.name for group in mesh.vertex_groups
                           if group.name in bone_names}
            authored_influences = {group_names.get(group.group)
                                   for vertex in mesh.data.vertices for group in vertex.groups
                                   if group.weight > 0 and group.group in group_names}
        retained = publish_bones_for_mesh({
            'name': part, 'armature': rig_name,
            'bones': [{'name': b.name, 'parent': b.parent.name if b.parent else ''}
                      for b in bones],
            'influencedBones': sorted(authored_influences),
        })
        if not retained:
            # Detach only in this disposable staging scene. A static part does
            # not own a copy of the shared house/door sockets.
            original_world = mesh.matrix_world.copy()
            if mesh.parent is not None and mesh.parent.type == 'ARMATURE':
                mesh.parent = None
                mesh.matrix_world = original_world
            for modifier in list(mesh.modifiers):
                if modifier.type == 'ARMATURE':
                    mesh.modifiers.remove(modifier)
            if any(abs(float(a) - float(b)) > 1e-4
                   for left, right in zip(original_world, mesh.matrix_world)
                   for a, b in zip(left, right)):
                raise RuntimeError(f'{part}: removing redundant shared rig moved the mesh')
        context = isolated_rig(bpy, mesh, rig, retained) if retained else nullcontext(None)
        with context as rig:
            reports[part] = (prepare_rig(rig, [mesh]) if rig else
                             {'status': 'static_mesh', 'preservedBones': 0})
            _material(mesh, part, texture_config)
            objects = [mesh, rig] if rig else [mesh]
            export_model(output / f'{part}.fbx', objects, embed_textures=True)
    return {'schemaVersion': 2, 'parts': reports, 'textureMode': 'embedded',
            'rigAssets': {part: f'{part}.fbx' for part in parts}}


def _material(mesh, part, texture_config):
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


args = sys.argv[sys.argv.index('--') + 1:]
if len(args) not in (4, 5):
    raise RuntimeError('usage: blender ... -- source.fbx target.fbx textures.json report.json')
report = main(Path(args[0]), Path(args[1]), json.loads(Path(args[2]).read_text(encoding='utf-8')), args[4] if len(args) == 5 else None)
Path(args[3]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
