import bpy
import bmesh
import json

def collection_path(collection):
    paths=[]
    def walk(current, path):
        if current == collection:
            paths.append('/'.join(path+[current.name]))
        for child in current.children:
            walk(child,path+[current.name])
    walk(bpy.context.scene.collection,[])
    return paths

def mesh_islands(mesh):
    bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
    unseen=set(bm.verts);count=0;sizes=[]
    while unseen:
        seed=unseen.pop();stack=[seed];size=1
        while stack:
            v=stack.pop()
            for e in v.link_edges:
                other=e.other_vert(v)
                if other in unseen:
                    unseen.remove(other);stack.append(other);size+=1
        count+=1;sizes.append(size)
    bm.free();return count,sorted(sizes,reverse=True)

def obj_info(ob):
    base={
        'name':ob.name,'type':ob.type,'parent':ob.parent.name if ob.parent else '',
        'parent_type':ob.parent_type if ob.parent else '',
        'collections':[c.name for c in ob.users_collection],
        'location':[round(v,5) for v in ob.location],
        'rotation':[round(v,5) for v in ob.rotation_euler],
        'scale':[round(v,5) for v in ob.scale],
    }
    if ob.type=='ARMATURE':
        base.update(data=ob.data.name,bones=len(ob.data.bones),roots=[b.name for b in ob.data.bones if not b.parent],
                    children=[c.name for c in ob.children])
    elif ob.type=='MESH':
        islands,sizes=mesh_islands(ob.data)
        base.update(data=ob.data.name,data_users=ob.data.users,vertices=len(ob.data.vertices),
                    polygons=len(ob.data.polygons),triangles=sum(len(p.vertices)-2 for p in ob.data.polygons),
                    islands=islands,island_vertex_counts=sizes,
                    materials=[m.name if m else '' for m in ob.data.materials],
                    modifiers=[{'name':m.name,'type':m.type,'object':getattr(m,'object',None).name if getattr(m,'object',None) else ''} for m in ob.modifiers],
                    vertex_groups=[g.name for g in ob.vertex_groups],
                    shape_keys=[k.name for k in ob.data.shape_keys.key_blocks] if ob.data.shape_keys else [],
                    uv_layers=[u.name for u in ob.data.uv_layers])
    return base

interesting=[]
tokens=('human','female','male','eye','brow','head','upper','lower','glove','boot','hair')
for ob in bpy.data.objects:
    if any(t in ob.name.lower() for t in tokens):interesting.append(obj_info(ob))

collections=[]
for c in bpy.data.collections:
    if any(t in c.name.lower() for t in tokens):
        collections.append({'name':c.name,'paths':collection_path(c),'children':[x.name for x in c.children],
                            'direct_objects':[o.name for o in c.objects],
                            'all_objects':[o.name for o in c.all_objects]})

print(json.dumps({
    'file':bpy.data.filepath,'scene':bpy.context.scene.name,
    'version':list(bpy.app.version),'mode':bpy.context.mode,
    'active':bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
    'selected':[o.name for o in bpy.context.selected_objects],
    'collections':collections,'objects':interesting,
},ensure_ascii=False,indent=2))
