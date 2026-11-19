"""Prepare independent present Real Estate rigs. Do not modify source FBX."""
import bpy
import json
import sys
from pathlib import Path
from contextlib import nullcontext
# Blender --python does not add the entrypoint directory to sys.path.
# Bootstrap sibling helpers before importing the shared rig_carrier builder.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_rig_carrier import create_rig_carrier
from model_publication import prepare_rig, export_model
from real_estate_rig_discovery import find_mesh, find_rig
from real_estate_import_rigs import restore_authored_rigs
from real_estate_staging_rig import isolated_rig
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from services.retired_col_mesh import retired
from real_estate.rig_publication_policy import publish_bones_for_mesh, publication_analysis, carrier_bones, validate_visual_weights


def main(source, output, texture_config, selected_part=None):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    restore_authored_rigs(bpy, source)
    reports = {}
    output.mkdir(parents=True, exist_ok=True)
    authored = [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH' and not retired(obj.name)]
    if not authored:
        raise RuntimeError('The FBX must contain at least one visual mesh')
    if selected_part is not None and retired(selected_part):
        raise RuntimeError('retired COL mesh is not publishable')
    if selected_part is not None and selected_part != 'rig_carrier' and selected_part not in authored:
        raise RuntimeError('Selected mesh ' + selected_part + ' not present in the FBX')
    parts = (selected_part,) if selected_part else ('rig_carrier', *sorted(authored, key=lambda name: (name.casefold(), name)))
    source_manifests = []
    for name in authored:
        obj = find_mesh(bpy, name)
        source_rig = find_rig(bpy, obj, name)
        bone_names = {b.name for b in source_rig.data.bones} if source_rig else set()
        index_names = {g.index:g.name for g in obj.vertex_groups if g.name in bone_names}
        used = {index_names[g.group] for v in obj.data.vertices for g in v.groups
                if g.weight > 0 and g.group in index_names}
        source_manifests.append({'name':name,'armature':source_rig.name if source_rig else '',
            'bones':[{'name':b.name,'parent':b.parent.name if b.parent else ''}
                     for b in source_rig.data.bones] if source_rig else [],
            'influencedBones':sorted(used)})
    for original in source_manifests:
        if original['armature'] and original['armature'].casefold() != 'house_armature':
            raise RuntimeError(original['name'] + ': new house publication requires only house_armature; '
                               'remove legacy independent armatures in Blender')
    house_rigs = [obj for obj in bpy.context.scene.objects if
                  obj.type == 'ARMATURE' and obj.name.casefold() == 'house_armature']
    if len(house_rigs) != 1:
        raise RuntimeError('House publication requires exactly one house_armature')
    house_rig = house_rigs[0]
    policy = publication_analysis({'meshes': source_manifests,
        'houseArmatureBones': [{'name': b.name, 'parent': b.parent.name if b.parent else ''}
                               for b in house_rig.data.bones]})
    validate_visual_weights(policy)
    by_name = {entry['name']:entry for entry in policy['meshes']}
    for part in parts:
        if part == 'rig_carrier':
            # Publish the ONLY static socket hierarchy in its own Model Asset.
            # A mixed FBX lets Roblox attach Bones under an arbitrary visual
            # MeshPart (observed with chimney_01_socket on chimney).
            retained = carrier_bones(policy)
            carrier = create_rig_carrier(house_rig)
            try:
                with isolated_rig(bpy, carrier, house_rig, retained) as rig:
                    reports[part] = prepare_rig(rig, [carrier])
                    export_model(output / 'rig_carrier.fbx', [carrier, rig],
                                 no_textures=True)
            finally:
                bpy.data.objects.remove(carrier, do_unlink=True)
            continue
        source_mesh = find_mesh(bpy, part)
        specification = by_name[part]
        retained = publish_bones_for_mesh(specification)
        # Every published part shares the ACTUAL authored armature pivot. Bake
        # transforms into a disposable copy of vertex coordinates; do not use
        # geometry bounds/centres to reconstruct them later in Roblox Studio.
        original_name = source_mesh.name
        source_mesh.name = '__game1_staging_source_' + original_name
        mesh = source_mesh.copy()
        mesh.data = source_mesh.data.copy()
        bpy.context.scene.collection.objects.link(mesh)
        mesh.name = original_name
        authored_world = source_mesh.matrix_world.copy()
        mesh.parent = None
        mesh.matrix_world = authored_world
        source_to_house = house_rig.matrix_world.inverted() @ authored_world
        mesh.data.transform(source_to_house)
        mesh.matrix_world = house_rig.matrix_world.copy()
        if part != mesh.name:
            raise RuntimeError('Publication changed visual MeshPart identity')
        try:
            _material(mesh, part, texture_config)
            if retained:
                rig = find_rig(bpy, source_mesh, part) or house_rig
                with isolated_rig(bpy, mesh, rig, retained) as staged_rig:
                    reports[part] = prepare_rig(staged_rig, [mesh])
                    export_model(output / f'{part}.fbx', [mesh, staged_rig],
                                 embed_textures=True)
            else:
                for modifier in list(mesh.modifiers):
                    if modifier.type == 'ARMATURE':
                        mesh.modifiers.remove(modifier)
                reports[part] = {'status': 'static_mesh', 'preservedBones': 0}
                export_model(output / f'{part}.fbx', [mesh], embed_textures=True)
        finally:
            data = mesh.data
            bpy.data.objects.remove(mesh, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
            source_mesh.name = original_name
    return {'schemaVersion': 3, 'parts': reports, 'textureMode': 'embedded',
            'rigAssets': {part: f'{part}.fbx' for part in parts}}


def _material(mesh, part, texture_config):
    if not texture_config.get(part):
        # Roblox Material + Color is applied by Studio, not baked into FBX.
        # A staged model without an image is intentional and valid.
        return
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
