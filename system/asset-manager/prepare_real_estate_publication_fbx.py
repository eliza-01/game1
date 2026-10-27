"""Prepare independent present Real Estate rigs. Do not modify source FBX."""
import bpy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bone_weight_survival import plan_publication_weights
from real_estate_skin_policy import check_rigid_hinge, HINGE
from real_estate_rig_discovery import find_mesh, find_rig
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from real_estate.collision_policy import is_collision_mesh


def main(source, output, texture_config):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    reports = {}
    rigs = {}
    authored = [obj.name for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if 'house' not in authored:
        raise RuntimeError('The FBX must contain a mesh named house')
    parts = tuple(sorted(authored, key=lambda name: (name != 'house', name.casefold(), name)))
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
            for bone in bones:
                bone.use_deform = True
            if not any(mod.type == 'ARMATURE' and mod.object == rig for mod in mesh.modifiers):
                mod = mesh.modifiers.new(name='Game1RealEstateRig', type='ARMATURE')
                mod.object = rig
            before = {bone.name: (bone.parent.name if bone.parent else '',
                        tuple(float(v) for row in bone.matrix_local for v in row)) for bone in bones}
            root_bone = next((b.name for b in bones if b.parent is None), None)
            if root_bone is None:
                raise RuntimeError(f'{part}: the armature has no root bone. Check the bone hierarchy in Blender.')
            names = {b.name for b in bones}
            by_index = {g.index: g.name for g in mesh.vertex_groups if g.name in names}
            vertices = []
            for vertex in mesh.data.vertices:
                weights = {by_index[g.group]: float(g.weight) for g in vertex.groups
                           if g.group in by_index and g.weight > 0}
                if not weights and not (part == 'door' and HINGE in names):
                    weights = {root_bone: 1.0}
                vertices.append({'object': mesh, 'index': vertex.index, 'mesh': mesh.name,
                                 'position': tuple(mesh.matrix_world @ vertex.co), 'weights': weights})
            if part == 'door' and HINGE in names:
                # The authored door is a rigid 1.0 hinge skin. Do NOT borrow
                # visible vertices to keep child sockets alive on import.
                # All sockets remain in the FBX bone tree; staged round-trip
                # and Studio-side checks verify that they really survive.
                report = check_rigid_hinge([v['weights'] for v in vertices], names)
            else:
                heads = {b.name: tuple(rig.matrix_world @ b.head_local) for b in bones}
                # Legacy/unweighted non-door rigs still need import anchors.
                # This modifies only the temporary staged export, never the
                # artist's canonical FBX file or Blender project.
                report = plan_publication_weights(
                    heads, vertices, min_covered_vertices=3,
                    minimum_weight=0.20, anchor_weight=0.30,
                )
                for v in vertices:
                    for group in mesh.vertex_groups:
                        if group.name in names:
                            group.remove([v['index']])
                    for name, weight in v['weights'].items():
                        group = mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
                        group.add([v['index']], weight, 'REPLACE')
            after = {bone.name: (bone.parent.name if bone.parent else '',
                        tuple(float(v) for row in bone.matrix_local for v in row)) for bone in bones}
            if before != after:
                raise RuntimeError(f'{rig_name} rest pose changed')
            reports[part] = report
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
        bpy.ops.object.select_all(action='DESELECT')
        mesh = find_mesh(bpy, part)
        rig = rigs[part]
        mesh.select_set(True)
        if rig and len(rig.data.bones):
            rig.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        target = output / f'{part}.fbx'
        bpy.ops.export_scene.fbx(filepath=str(target), use_selection=True,
            object_types={'MESH','ARMATURE'}, bake_anim=False, add_leaf_bones=False,
            use_armature_deform_only=False, axis_forward='-Z', axis_up='Y', global_scale=1.0,
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            use_space_transform=True, bake_space_transform=False,
            path_mode='COPY', embed_textures=True)
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f'Real Estate {part} FBX was not written')
    return {'schemaVersion': 2, 'parts': reports, 'textureMode': 'embedded',
            'rigAssets': {part: f'{part}.fbx' for part in parts}}

args = sys.argv[sys.argv.index('--') + 1:]
if len(args) != 4:
    raise RuntimeError('usage: blender ... -- source.fbx target.fbx textures.json report.json')
report = main(Path(args[0]), Path(args[1]), json.loads(Path(args[2]).read_text(encoding='utf-8')))
Path(args[3]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
