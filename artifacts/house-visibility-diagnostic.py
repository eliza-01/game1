import bpy,sys,json
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'system/asset-manager'))
from model_publication import prepare_rig
row=next(x for x in json.loads((root/'assets/manifests/real-estate.json').read_text(encoding='utf-8'))['items'] if x['slug']=='house_level4_01')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=str(root/row['meshSources']['house']['path']),use_anim=False)
mesh=bpy.data.objects['house'];rig=bpy.data.objects['house_armature']
def stats():
 names={b.name for b in rig.data.bones};groups={g.index:g.name for g in mesh.vertex_groups if g.name in names}
 covered={v.index for v in mesh.data.vertices if any(g.group in groups and g.weight>1e-8 for g in v.groups)}
 return {'vertices':len(mesh.data.vertices),'weighted':len(covered),'unweighted':len(mesh.data.vertices)-len(covered),'faces':len(mesh.data.polygons),'fullyWeightedFaces':sum(all(i in covered for i in p.vertices) for p in mesh.data.polygons),'bones':len(names),'dimensions':list(mesh.dimensions)}
before=stats();report=prepare_rig(rig,[mesh]);after=stats()
print('DIAGNOSTIC',json.dumps({'before':before,'after':after,'report':report}))
