import bpy
import json

def info(ob):
    d={'name':ob.name,'type':ob.type,'data':ob.data.name if ob.data else '',
       'parent':ob.parent.name if ob.parent else '',
       'collections':[c.name for c in ob.users_collection],
       'children':[c.name for c in ob.children]}
    if ob.type=='ARMATURE':
        d['bones']=len(ob.data.bones);d['roots']=[b.name for b in ob.data.bones if not b.parent]
    if ob.type=='MESH':
        d['verts']=len(ob.data.vertices);d['tris']=sum(len(p.vertices)-2 for p in ob.data.polygons)
        d['armatures']=[m.object.name if m.object else '' for m in ob.modifiers if m.type=='ARMATURE']
        d['materials']=[m.name if m else '' for m in ob.data.materials]
        d['groups']=[g.name for g in ob.vertex_groups]
    return d

armatures=[info(o) for o in bpy.data.objects if o.type=='ARMATURE']
core=[info(o) for o in bpy.data.objects if o.name.lower().startswith(('human_','male_','female_','eyes_','eyebrows_','head_','newborn_')) and o.type in {'MESH','ARMATURE'}]
collections=[]
for c in bpy.data.collections:
    names=[o.name for o in c.objects]
    if any('human' in x.lower() or 'male' in x.lower() or 'female' in x.lower() for x in [c.name,*names]):
        collections.append({'name':c.name,'children':[x.name for x in c.children],'direct':names})
print(json.dumps({'file':bpy.data.filepath,'armatures':armatures,'core_objects':core,'collections':collections},ensure_ascii=False,indent=2))
