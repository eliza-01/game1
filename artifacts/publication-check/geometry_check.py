import bpy,sys,json
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'system/asset-manager'))
from model_publication import clean_scene
row=next(r for r in json.loads((root/'assets/manifests/real-estate.json').read_text(encoding='utf-8'))['items'] if r['slug']=='house_level4_01')
source=root/row['meshSources']['door']['path']
def points(path):
 clean_scene();bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
 obj=bpy.data.objects['door']; deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
 try:return [tuple(ev.matrix_world@v.co) for v in mesh.vertices]
 finally:ev.to_mesh_clear()
sys.path.insert(0,str(Path.home()/'.agents/skills/blender-asset-qa/scripts'))
import qa_check
before=points(source);original_qa=qa_check.run(objects=['door'])
after=points(root/'artifacts/publication-check/part/door.fbx')
assert len(before)==len(after)
error=max(abs(a-b) for p,q in zip(before,after) for a,b in zip(p,q));assert error<0.0001,error
sys.path.insert(0,str(Path.home()/'.agents/skills/blender-asset-qa/scripts'))
import qa_check
qa=qa_check.run(objects=['door'])
report={'vertices':len(after),'maxRestGeometryDelta':error,'qa':qa,'sourceQA':original_qa}
assert original_qa['errors']==qa['errors']
assert original_qa['objects']['door']['tris']==qa['objects']['door']['tris']
(root/'artifacts/publication-check/geometry-report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
print('GEOMETRY_CHECK',len(after),error)
