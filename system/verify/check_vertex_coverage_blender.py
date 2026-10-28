"""Manual Blender regression on actual house/door sources, with temporary exports.

blender --background --factory-startup --python-exit-code 1 --python <this file>
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
from model_publication import (clean_scene, prepare_rig, assert_skin_complete,
                               export_model, rest_snapshot)


def evaluated_positions(mesh):
    obj = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = obj.to_mesh()
    try:
        return [obj.matrix_world @ v.co for v in data.vertices]
    finally:
        obj.to_mesh_clear()


def check(source, part, directory):
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    mesh = bpy.data.objects[part]
    rig = mesh.find_armature()
    before = rest_snapshot(rig)
    positions = evaluated_positions(mesh)
    mesh.data.calc_loop_triangles()
    triangles = len(mesh.data.loop_triangles)
    report = prepare_rig(rig, [mesh])
    assert rest_snapshot(rig) == before
    target = directory / (part + '.fbx')
    export_model(target, [mesh, rig])
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(target), use_anim=False)
    mesh = bpy.data.objects[part]
    rig = mesh.find_armature()
    assert_skin_complete(rig, [mesh])
    after = rest_snapshot(rig)
    assert before.keys() == after.keys()
    for name, bone in before.items():
        assert bone['parent'] == after[name]['parent']
        assert max(abs(a-b) for a,b in zip(bone['matrix'], after[name]['matrix'])) < .0001
    actual = evaluated_positions(mesh)
    assert len(actual) == len(positions)
    error = max((a-b).length for a,b in zip(actual, positions))
    assert error < .0001, error
    mesh.data.calc_loop_triangles()
    assert len(mesh.data.loop_triangles) == triangles
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    return {'part': part, 'vertices': len(actual), 'triangles': triangles,
            'bones': len(after), 'maxRestGeometryDelta': error,
            'sourceUnchanged': True, 'skin': report}


row = next(r for r in json.loads((ROOT / 'assets/manifests/real-estate.json').read_text(
    encoding='utf-8'))['items'] if r['slug'] == 'house_level4_01')
with tempfile.TemporaryDirectory(prefix='game1-skin-coverage-') as directory:
    reports = [check(ROOT / row['meshSources'][part]['path'], part, Path(directory))
               for part in ('house', 'door')]
output = ROOT / 'artifacts/skin-coverage-blender-report.json'
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(reports, indent=2), encoding='utf-8')
print(json.dumps(reports))
