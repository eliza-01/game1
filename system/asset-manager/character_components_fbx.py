"""Read a modular FBX; optionally extract each component without animation export.

Runs only in an isolated Blender process. Never opens or saves the artist .blend.
"""
import bpy
import hashlib
import json
import struct
import sys
from pathlib import Path
from mathutils import Vector


def matrix(m):
    return [round(float(x), 7) for row in m for x in row]


def skeleton(rig):
    # Canonical root-space matrices include object scale/rotation; two exports
    # cannot accidentally pass compatibility with different armature transforms.
    return [dict(name=b.name, parent=b.parent.name if b.parent else '',
                 matrix=matrix(rig.matrix_world @ b.matrix_local))
            for b in sorted(rig.data.bones, key=lambda b:b.name)]


def content_hash(obj):
    h=hashlib.sha256()
    h.update(json.dumps(matrix(obj.matrix_world)).encode())
    names={g.index:g.name for g in obj.vertex_groups}
    for v in obj.data.vertices:
        h.update(struct.pack('<3d', *(round(float(x),7) for x in v.co)))
        h.update(json.dumps(sorted((names[g.group],round(g.weight,7)) for g in v.groups if g.weight>0)).encode())
    for p in obj.data.polygons:
        h.update(json.dumps([list(p.vertices),p.material_index,p.use_smooth]).encode())
    for uv in obj.data.uv_layers:
        h.update(uv.name.encode())
        for item in uv.data:h.update(struct.pack('<2d', *(round(float(x),7) for x in item.uv)))
    h.update(json.dumps([(m.name,list(m.diffuse_color),m.roughness,m.metallic) if m else None
                         for m in obj.data.materials]).encode())
    return h.hexdigest()


def export(path, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'ARMATURE','MESH'},
        bake_anim=False,add_leaf_bones=False,use_armature_deform_only=False,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,path_mode='STRIP')


def main(source, report_path, output_dir=None):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source),use_anim=False)
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    meshes=sorted((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:o.name)
    if not rigs or not meshes:raise ValueError('FBX requires a rig and at least one component mesh')
    mesh_names={o.name for o in meshes}
    main_rigs=[r for r in rigs if r.name.removesuffix('_armature') not in mesh_names]
    if len(main_rigs)!=1:raise ValueError('FBX must contain one main <profile>_armature; accessory rigs use <part>_armature')
    primary=main_rigs[0]
    for r in rigs:r.data.pose_position='REST'
    bpy.context.view_layer.update()
    parts=[]
    for o in meshes:
        targets=[m.object for m in o.modifiers if m.type=='ARMATURE' and m.object]
        if len(targets)!=1 or targets[0] not in rigs:raise ValueError(f'{o.name}: one Armature modifier is required')
        owner=targets[0]
        if owner!=primary and owner.name!=o.name+'_armature':raise ValueError(f'{o.name}: accessory rig must use the part name')
        bones={b.name for b in owner.data.bones};groups={g.index:g.name for g in o.vertex_groups}
        used=set()
        if not o.data.vertices or not o.data.polygons:raise ValueError(f'{o.name}: empty mesh')
        for v in o.data.vertices:
            weights=[(groups[g.group],float(g.weight)) for g in v.groups if g.weight>1e-8 and groups[g.group] in bones]
            if not weights or len(weights)>4 or abs(sum(w for _,w in weights)-1)>1e-4:
                raise ValueError(f'{o.name}: vertex {v.index} requires 1–4 normalized rig weights')
            used.update(n for n,_ in weights)
        row=dict(name=o.name,armature=owner.name,content_sha256=content_hash(o),vertices=len(o.data.vertices),
            triangles=sum(len(p.vertices)-2 for p in o.data.polygons),used_bones=sorted(used),
            skeleton=skeleton(owner),attachment='hair_mount' if owner!=primary else '',materials=[m.name if m else '' for m in o.data.materials])
        if owner!=primary and not any(b.name=='hair_mount' for b in primary.data.bones):
            raise ValueError('accessory requires hair_mount on the main rig')
        parts.append(row)
        if output_dir:
            # A component carries only its influencing bones and ancestors.
            # Unrelated face/helper weights are never inserted into visible mesh.
            keep=set(used)
            for name in list(keep):
                b=owner.data.bones[name].parent
                while b:keep.add(b.name);b=b.parent
            clone=owner.copy();clone.data=owner.data.copy();bpy.context.scene.collection.objects.link(clone)
            original_name=owner.name;owner.name='source_reference_rig';clone.name=original_name
            mesh=o.copy();mesh.data=o.data.copy();bpy.context.scene.collection.objects.link(mesh)
            mesh_name=o.name;o.name='source_reference_mesh';mesh.name=mesh_name
            mesh.parent=clone;mesh.matrix_world=o.matrix_world.copy()
            for mod in mesh.modifiers:
                if mod.type=='ARMATURE':mod.object=clone
            bpy.ops.object.select_all(action='DESELECT');clone.select_set(True);bpy.context.view_layer.objects.active=clone
            bpy.ops.object.mode_set(mode='EDIT')
            for b in list(clone.data.edit_bones):
                if b.name not in keep:clone.data.edit_bones.remove(b)
            bpy.ops.object.mode_set(mode='OBJECT')
            export(output_dir/(mesh_name+'.fbx'),[clone,mesh])
            bpy.data.objects.remove(mesh,do_unlink=True);bpy.data.objects.remove(clone,do_unlink=True)
            owner.name=original_name;o.name=mesh_name
    if output_dir:
        # Persistent invisible carrier, independent of every replaceable mesh.
        # All weights are on helper triangles, never on visible components.
        verts=[];faces=[]
        for b in primary.data.bones:
            p=b.head_local;start=len(verts)
            verts.extend([tuple(p),tuple(p+Vector((.001,0,0))),tuple(p+Vector((0,.001,0)))])
            faces.append((start,start+1,start+2))
        data=bpy.data.meshes.new('rig_carrier');data.from_pydata(verts,[],faces)
        carrier=bpy.data.objects.new('rig_carrier',data);bpy.context.scene.collection.objects.link(carrier)
        carrier.parent=primary;carrier.matrix_world=primary.matrix_world.copy()
        for i,b in enumerate(primary.data.bones):carrier.vertex_groups.new(name=b.name).add([i*3,i*3+1,i*3+2],1,'REPLACE')
        mod=carrier.modifiers.new('rig_bind','ARMATURE');mod.object=primary
        export(output_dir/'rig.fbx',[primary,carrier])
    report_path.write_text(json.dumps(dict(schema_version=1,armature=primary.name,bones=skeleton(primary),parts=parts),indent=2),encoding='utf8')


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    main(Path(args[0]),Path(args[1]),Path(args[2]) if len(args)>2 else None)
