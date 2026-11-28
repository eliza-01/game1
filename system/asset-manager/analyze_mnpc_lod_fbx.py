"""Inspect an authored, already posed and baked MNPC LOD1 FBX.

No decimation or material conversion is performed implicitly. Blender units in
this report are diagnostic; the Roblox import/placement contract is separate.
"""
from pathlib import Path
import json
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import clean_scene


def analyze(source, *, include_points=False):
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    objects = list(bpy.context.scene.objects)
    meshes = [obj for obj in objects if obj.type == 'MESH']
    if len(meshes) != 1 or any(obj.type == 'ARMATURE' for obj in objects):
        raise ValueError('MNPC LOD1 must contain exactly one static mesh and no armature')
    mesh = meshes[0]
    if mesh.name != 'lod1':
        raise ValueError('Name the single LOD1 mesh lod1 (no technical meshes)')
    if mesh.modifiers or mesh.vertex_groups or mesh.data.shape_keys:
        raise ValueError('Apply pose/modifiers and remove skin weights and shape keys before exporting LOD1')
    if any(obj.animation_data for obj in objects):
        raise ValueError('MNPC LOD1 cannot contain animation data')
    if len(mesh.data.uv_layers) != 1 or len(mesh.data.materials) > 1:
        raise ValueError('LOD1 requires one UV map and at most one material')
    mesh.data.calc_loop_triangles()
    # Exact vertices in FBX scene axes, relative to the authored origin.
    points = [mesh.matrix_world @ vertex.co for vertex in mesh.data.vertices]
    if not points or not mesh.data.loop_triangles:
        raise ValueError('LOD1 mesh is empty')
    report = {'schemaVersion': 1, 'meshName': mesh.name, 'meshes': 1, 'armatures': 0,
            'vertices': len(points), 'triangles': len(mesh.data.loop_triangles),
            'boundsMin': [float(min(p[i] for p in points)) for i in range(3)],
            'boundsMax': [float(max(p[i] for p in points)) for i in range(3)]}
    if include_points:
        report['points'] = [list(p) for p in points]
    return report


if __name__ == '__main__':
    source, output = sys.argv[sys.argv.index('--') + 1:]
    Path(output).write_text(json.dumps(analyze(Path(source)), allow_nan=False), encoding='utf-8')
