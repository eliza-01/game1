"""Disposable Blender scene: flatten a reviewed posed FULL assembly to one LOD1.

No Roblox animation conversion here. A skinned source must have an explicitly
selected embedded animation frame. Already-static posed assemblies are allowed.
All surfaces use an explicitly supplied common UV atlas; never infer materials.
"""
from pathlib import Path
import json
import math
import re
import sys
import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import clean_scene, export_model
from analyze_mnpc_lod_fbx import analyze
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from services.retired_col_mesh import retired


def technical(name):
    name = re.sub(r'\.\d{3}$', '', name.casefold())
    return retired(name) or name in {'rig_carrier', 'rootpart', 'humanoidrootpart', 'rootcollider', 'hitbox', 'hitboxes'}


def finish(merged, output, original_triangles, target):
    merged.name = 'lod1'
    merged.data.name = 'lod1'
    for group in list(merged.vertex_groups):
        merged.vertex_groups.remove(group)
    tri = merged.modifiers.new('Triangulate', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=tri.name)
    if original_triangles > target:
        decimate = merged.modifiers.new('LOD1 collapse', 'DECIMATE')
        decimate.ratio = target / original_triangles
        decimate.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=decimate.name)
    merged.data.calc_loop_triangles()
    if not 1 <= len(merged.data.loop_triangles) <= target:
        raise ValueError('Decimation could not meet triangle target without an empty mesh; choose a higher target')
    if not len(merged.data.uv_layers) == 1:
        raise ValueError('Decimation lost the shared atlas UV')
    export_model(output, [merged], no_textures=True)
    report = analyze(output)  # same inspector as M633, actual FBX round-trip
    if report['triangles'] > target:
        raise ValueError('FBX round-trip exceeds triangle target')
    return report


def prepare(source, output, frame, target):
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=True, use_image_search=False)
    scene = bpy.context.scene
    objects = list(scene.objects)
    rigs = [o for o in objects if o.type == 'ARMATURE']
    if rigs:
        # An armature with no action is commonly an unposed model FBX. Do not
        # silently produce a T-pose. Only an explicitly selected native FBX frame.
        if len(bpy.data.actions) != len(rigs):
            raise ValueError('Ambiguous embedded FBX actions; export one reviewed pose or one action per rig')
        for rig in rigs:
            action = rig.animation_data.action if rig.animation_data else None
            if action is None or not action.frame_range[0] <= frame <= action.frame_range[1]:
                raise ValueError(f'{rig.name}: no embedded action at frame {frame}; supply a posed assembly, not the rest FBX')
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    visual = [o for o in objects if o.type == 'MESH' and not technical(o.name)]
    if not visual or len(visual) > 64:
        raise ValueError('Expected 1–64 visible assembly meshes')
    copies = []
    original_triangles = 0
    # Freeze all evaluated meshes before deleting any source object. Use world
    # space coordinates and keep the authored scene origin (no bbox centering).
    for obj in visual:
        evaluated = obj.evaluated_get(depsgraph)
        if len(obj.data.polygons) > 500000:
            raise ValueError(f'{obj.name}: source polygon count exceeds preparation cap')
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        if len(mesh.uv_layers) != 1 or not len(mesh.polygons):
            raise ValueError(f'{obj.name}: exactly one authored UV map and nonempty geometry required')
        uv = mesh.uv_layers[0]
        uv.name = 'UVMap'
        if any(not all(math.isfinite(float(x)) and -1e-5 <= x <= 1.00001 for x in loop.uv) for loop in uv.data):
            raise ValueError(f'{obj.name}: UV outside the shared atlas [0,1]')
        mesh.transform(evaluated.matrix_world)
        if evaluated.matrix_world.to_3x3().determinant() < 0:
            mesh.flip_normals()
        mesh.calc_loop_triangles()
        original_triangles += len(mesh.loop_triangles)
        if original_triangles > 500000:
            raise ValueError('Posed assembly exceeds 500000 triangle preparation cap')
        mesh.materials.clear()
        # All UVs already reference the supplied assembled atlas. Material
        # slots cannot leak stale FBX texture references into the output.
        for poly in mesh.polygons:
            poly.material_index = 0
        copy = bpy.data.objects.new('lod_piece', mesh)
        scene.collection.objects.link(copy)
        copy.matrix_world = Matrix.Identity(4)
        copies.append(copy)
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in copies:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    if len(copies) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    report = finish(merged, output, original_triangles, target)
    return {'schemaVersion': 1, 'geometry': report, 'inputTriangles': original_triangles,
            'inputMeshes': len(visual), 'poseMode': 'embedded_frame' if rigs else 'posed_static'}


if __name__ == '__main__':
    source, output, report, frame, target = sys.argv[sys.argv.index('--') + 1:]
    result = prepare(Path(source), Path(output), int(frame), int(target))
    Path(report).write_text(json.dumps(result, allow_nan=False), encoding='utf-8')
