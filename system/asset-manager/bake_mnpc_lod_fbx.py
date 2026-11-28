"""Build a single posed static mesh from validated captured topology.
Reuse M634's decimation/export/round-trip inspector. No rig or animation import.
"""
import json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model_publication import clean_scene
from prepare_mnpc_lod_fbx import finish


def bake(source, output, target):
    data=json.loads(Path(source).read_text(encoding='utf-8'))
    clean_scene()
    mesh=bpy.data.meshes.new('lod1')
    mesh.from_pydata(data['vertices'],[],data['faces'])
    mesh.update()
    if mesh.validate(verbose=False) or len(mesh.polygons)!=len(data['faceUV']):
        raise ValueError('Captured topology is invalid; refusing to silently repair geometry')
    uv=mesh.uv_layers.new(name='UVMap')
    for poly, corners in zip(mesh.polygons,data['faceUV']):
        for loop, coord in zip(poly.loop_indices,corners):
            uv.data[loop].uv=coord
        poly.use_smooth=True
    obj=bpy.data.objects.new('lod1',mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    return finish(obj,Path(output),len(data['faces']),target)


if __name__=='__main__':
    source,output,report,target=sys.argv[sys.argv.index('--')+1:]
    Path(report).write_text(json.dumps(bake(source,output,int(target)),allow_nan=False),encoding='utf-8')
