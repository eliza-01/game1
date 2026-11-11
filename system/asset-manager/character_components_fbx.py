"""Read a modular FBX; optionally extract each component without animation export.

Runs only in an isolated Blender process. Never opens or saves the artist .blend.
"""
import bpy
import hashlib
import json
import struct
import sys
from pathlib import Path

# The same slot vocabulary as Control Center; Blender runs in a separate Python.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-center"))
from blender_rig_carrier import create_rig_carrier
from model_publication import normalize_existing_component_skin
from character_core.part_names import parse_part, parse_hair_extra, rigid_pivot_mount_for_part


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


def export_rigid_pivot_mesh(source, path, extras=()):
    """Export a rigid hairstyle as ONE FBX without changing the artist scene.

    Each object retains its own world transform/pivot. Roblox stores the
    root-to-extra relationship, not an artificial second hair_mount.
    """
    originals = [(obj, obj.name, obj.matrix_world.copy()) for obj in (source, *extras)]
    clones = []
    try:
        # Free canonical names first (Blender otherwise appends .001 to copies).
        for index, (obj, _, _) in enumerate(originals):
            obj.name = f'game1_export_reference_{index}'
        for obj, name, world in originals:
            clone = obj.copy()
            clone.data = obj.data.copy()
            bpy.context.scene.collection.objects.link(clone)
            clone.name = name
            clone.parent = None
            clone.matrix_world = world
            clones.append(clone)
        export(path, clones)
    finally:
        for clone in clones:
            bpy.data.objects.remove(clone, do_unlink=True)
        for obj, name, _ in originals:
            obj.name = name


def main(source, report_path, output_dir=None, *, rig_only=False):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source),use_anim=False)
    rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    meshes = sorted((o for o in bpy.context.scene.objects if o.type == 'MESH'), key=lambda o: o.name)
    if not meshes and not rig_only:
        raise ValueError('FBX requires at least one component mesh')
    extras_by_root = {}
    roots = []
    for obj in meshes:
        extra = parse_hair_extra(obj.name)
        if extra:
            extras_by_root.setdefault(extra['root_id'], []).append(obj)
        else:
            roots.append(obj)
    if rigs:
        mesh_names = {o.name for o in roots}
        main_rigs = [r for r in rigs if r.name.removesuffix('_armature') not in mesh_names]
        if len(main_rigs) != 1:
            raise ValueError('FBX must contain one main <profile>_armature; accessory rigs use <part>_armature')
        primary = main_rigs[0]
        armature_name = primary.name
    else:
        if rig_only:
            raise ValueError('FBX does not contain a rig')
        # Reusable rigid hair may be exported on its own, without forcing the
        # artist to add an unrelated armature to the hair collection.
        if not roots or any(parse_part(obj.name)['slot'] != 'hair' for obj in roots):
            raise ValueError('FBX without armature may contain only rigid hair')
        parsed_roots = [parse_part(obj.name) for obj in roots]
        profiles = {p['rig_profile_id'] for p in parsed_roots}
        # Gendered rigid hair targets its gendered rig when exported alone.
        # A `common` hair without an Armature targets the shared rig; do not
        # guess which gendered bind profile should own it.
        gender_profiles = {p['gender'] for p in parsed_roots}
        if len(profiles) != 1 or len(gender_profiles) != 1:
            raise ValueError('rigless hair FBX must target one rig profile and gender')
        primary = None
        gender = next(iter(gender_profiles))
        armature_name = (next(iter(profiles)) + (('_' + gender) if gender != 'common' else '') + '_armature')
    for rig in rigs:
        rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    parts=[]
    part_errors=[]
    for root, items in extras_by_root.items():
        if root not in {obj.name for obj in roots}:
            part_errors.append({'name': root, 'message': root + ': orphan extra without hair root'})
    # Reject malformed extras instead of allowing partial registration of a
    # hair root with missing accessory geometry.
    for obj in meshes:
        if '_hair_extra_' in obj.name and not parse_hair_extra(obj.name):
            raise ValueError(obj.name + ': use <hair_root>_extra_01..99')
    for o in (() if rig_only else roots):
        try:
            # Validate names before mesh preparation; one rejected part must not
            # hide independent, valid parts elsewhere in the same FBX.
            parsed = parse_part(o.name)
            targets=[m.object for m in o.modifiers if m.type=='ARMATURE' and m.object]
            if not o.data.vertices or not o.data.polygons:
                raise ValueError(f'{o.name}: empty mesh')
            # Only rigid hair is permitted without an Armature modifier. The
            # artist-authored object pivot is its mount point; do not infer one
            # from the geometry bounds or invent a skinning influence.
            pivot_mount = rigid_pivot_mount_for_part(o.name) if not targets else ''
            rigid_hair = bool(pivot_mount)
            extras = sorted(extras_by_root.get(o.name, []), key=lambda obj: obj.name)
            if extras and not rigid_hair:
                raise ValueError(o.name + ': extra MeshParts require rigid pivot hair')
            extra_rows = []
            for extra in extras:
                if not extra.data.vertices or not extra.data.polygons:
                    raise ValueError(extra.name + ': empty extra mesh')
                if any(mod.type == 'ARMATURE' for mod in extra.modifiers):
                    raise ValueError(extra.name + ': rigid hair extra cannot have Armature')
                if any(g.weight > 1e-8 for v in extra.data.vertices for g in v.groups):
                    raise ValueError(extra.name + ': rigid hair extra cannot have deform weights')
                extra_rows.append(dict(name=extra.name, content_sha256=content_hash(extra),
                                       vertices=len(extra.data.vertices),
                                       triangles=sum(len(poly.vertices)-2 for poly in extra.data.polygons)))
            if rigid_hair:
                if any(mod.type=='ARMATURE' for mod in o.modifiers):
                    raise ValueError(f'{o.name}: incomplete Armature modifier')
                if any(g.weight>1e-8 for v in o.data.vertices for g in v.groups):
                    raise ValueError(f'{o.name}: rigid hair cannot have deform weights')
                if primary is not None and not any(b.name==pivot_mount for b in primary.data.bones):
                    raise ValueError(f'{o.name}: main rig requires {pivot_mount}')
                owner=None
                used=set()
                prepared_skin = {'normalized_vertices': 0}
                attachment=pivot_mount
                attachment_mode='pivot'
            else:
                if primary is None:
                    raise ValueError(o.name + ': skinned part requires an armature')
                if len(targets)!=1 or targets[0] not in rigs:
                    raise ValueError(f'{o.name}: one Armature modifier is required')
                owner=targets[0]
                if owner!=primary and owner.name!=o.name+'_armature':
                    raise ValueError(f'{o.name}: accessory rig must use the part name')
                prepared_skin = normalize_existing_component_skin(owner, o)
                used = set(prepared_skin['used_bones'])
                attachment='hair_mount' if owner!=primary else ''
                attachment_mode='socket' if attachment else ''
                if attachment and not any(b.name==attachment for b in primary.data.bones):
                    raise ValueError('accessory requires hair_mount on the main rig')
            combined_hash = content_hash(o)
            if extra_rows:
                combined_hash = hashlib.sha256(json.dumps(
                    {'root': combined_hash, 'extras': [(item['name'], item['content_sha256']) for item in extra_rows]},
                    sort_keys=True).encode()).hexdigest()
            row=dict(name=o.name,armature=owner.name if owner else '',content_sha256=combined_hash,
                vertices=len(o.data.vertices),triangles=sum(len(p.vertices)-2 for p in o.data.polygons),
                used_bones=sorted(used),normalized_vertices=prepared_skin['normalized_vertices'],
                skeleton=skeleton(owner) if owner else [],
                attachment=attachment,attachment_mode=attachment_mode,extras=extra_rows,
                materials=[m.name if m else '' for m in o.data.materials])
            parts.append(row)
        except ValueError as exc:
            part_errors.append({'name': o.name, 'message': str(exc)})
            continue
        if output_dir:
            if rigid_hair:
                export_rigid_pivot_mesh(o, output_dir/(o.name+'.fbx'), extras)
                continue
            # A skinned component carries only influencing bones and ancestors.
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
    if part_errors and not parts and not rig_only:
        raise ValueError('; '.join(error['message'] for error in part_errors))
    if output_dir and primary is not None:
        # Persistent invisible carrier, independent of every replaceable mesh.
        # All weights are on helper triangles, never on visible components.
        carrier = create_rig_carrier(primary)
        export(output_dir/'rig.fbx',[primary,carrier])
    report_path.write_text(json.dumps(dict(schema_version=2,armature=armature_name,rig_present=primary is not None,bones=skeleton(primary) if primary else [],parts=parts,part_errors=part_errors),indent=2),encoding='utf8')


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    main(Path(args[0]),Path(args[1]),
         Path(args[2]) if len(args)>2 and args[2]!='--rig-only' else None,
         rig_only='--rig-only' in args[2:])
