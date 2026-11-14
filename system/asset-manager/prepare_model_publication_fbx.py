"""Background staging for static or rigged model assets (location assets/weapons)."""
import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import clean_scene, linked_meshes, prepare_rig, export_model, rest_snapshot
from model_publication import assert_skin_complete
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from location_rig_contract import CARRIER, ROOT, role, validate as validate_location_rig
from services.retired_col_mesh import retired


def snapshot():
    return {o.name: rest_snapshot(o) for o in bpy.context.scene.objects if o.type == 'ARMATURE'}


def location_manifest(objects):
    meshes = [obj for obj in objects if obj.type == 'MESH']
    rigs = [obj for obj in objects if obj.type == 'ARMATURE' and len(obj.data.bones)]
    if len(rigs) > 1:
        raise ValueError('Location publication contains multiple skeletons')
    rig = rigs[0] if rigs else None
    carrier = [obj for obj in meshes if obj.name.casefold() == CARRIER]
    if any(obj.name == ROOT for obj in objects):
        raise ValueError('Location publication contains forbidden RootPart')
    if any(obj.type == 'ARMATURE' and obj != rig for obj in objects):
        raise ValueError('Location publication contains unexpected armature objects')
    bones = ([{'name': bone.name, 'parent': bone.parent.name if bone.parent else '',
               'matrix': [round(float(v), 7) for row in bone.matrix_local for v in row]}
              for bone in rig.data.bones] if rig else [])
    output = validate_location_rig(
        [{'name': mesh.name, 'vertices': len(mesh.data.vertices)} for mesh in meshes], bones)
    if rig:
        if carrier[0] not in linked_meshes(rig):
            raise ValueError('skinned rig_carrier must be bound to its authored armature')
        groups = {group.name for group in carrier[0].vertex_groups}
        if not {bone['name'] for bone in bones} <= groups:
            raise ValueError('rig_carrier does not weight every canonical Bone')
    # Static FBX has no Bones and no carrier. The staging process never invents either.
    return output


def visual_skin(objects):
    # No publication operation may silently rewrite artist visual weights.
    result = {}
    for obj in objects:
        if obj.type != 'MESH' or role(obj.name) != 'visual':
            continue
        names = {group.index: group.name for group in obj.vertex_groups}
        result[obj.name] = [[(names[g.group], round(float(g.weight), 7))
                             for g in vertex.groups] for vertex in obj.data.vertices]
    return result


def main(source, output, report_path, texture_mode="embedded"):
    if texture_mode not in ("embedded", "geometry_only"):
        raise ValueError("unsupported model publication texture mode")
    if source.resolve() == output.resolve():
        raise ValueError('publication output must differ from source')
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    if texture_mode == 'geometry_only':
        for obj in list(bpy.context.scene.objects):
            if obj.type == 'MESH' and retired(obj.name):
                bpy.data.objects.remove(obj, do_unlink=True)
    objects = sorted((o for o in bpy.context.scene.objects if o.type in {'MESH', 'ARMATURE'}),
                     key=lambda o: o.name)
    if not any(o.type == 'MESH' for o in objects):
        raise ValueError('Model FBX has no mesh')
    is_location = texture_mode == 'geometry_only'
    if is_location:
        location_manifest(objects)  # Validate source; its mesh inventory may evolve on export.
    original_weights = visual_skin(objects) if is_location else None
    before = snapshot()
    reports = {}
    for rig in objects:
        if rig.type == 'ARMATURE' and len(rig.data.bones):
            if is_location:
                # Location's explicit canonical FBX authoring already prepared
                # the skin. Publishing must only validate it, NEVER rewrite
                # visible artist weights in the temporary upload copy.
                assert_skin_complete(rig, linked_meshes(rig))
                reports[rig.name] = {'status': 'validated_authored_skin'}
            else:
                reports[rig.name] = prepare_rig(rig, linked_meshes(rig))
    if is_location and original_weights != visual_skin(objects):
        raise ValueError('Location publication would alter artist visual skin weights')
    if texture_mode == "geometry_only":
        # Location Atlas is an independent publication. The staged FBX MUST
        # contain neither embedded bitmap bytes nor image/material references.
        # Only alter the disposable Blender scene, never the artist source.
        for obj in objects:
            if obj.type == "MESH":
                obj.data.materials.clear()
    export_model(output, objects, embed_textures=(texture_mode == "embedded"),
                 no_textures=(texture_mode == "geometry_only"))
    # Round-trip the actual staged file, not just the pre-export Python objects.
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(output), use_anim=False)
    after = snapshot()
    published = location_manifest(list(bpy.context.scene.objects)) if is_location else None
    # An FBX round-trip may split visual meshes or change vertex counts.
    # The published manifest describes the ACTUAL staged FBX revision.
    # Rig continuity and skin integrity are checked below, independently.
    remaining_material_slots = sum(len(obj.data.materials) for obj in bpy.context.scene.objects
        if obj.type == "MESH")
    if texture_mode == "geometry_only" and remaining_material_slots:
        raise ValueError("geometry-only publication retained material/texture references")
    if before.keys() != after.keys():
        raise ValueError('publication changed armatures')
    for name, bones in before.items():
        if bones.keys() != after[name].keys():
            raise ValueError(f'publication changed bone set: {name}')
        rig = bpy.data.objects[name]
        assert_skin_complete(rig, linked_meshes(rig))
        influenced = set()
        for mesh in linked_meshes(rig):
            groups = {g.index: g.name for g in mesh.vertex_groups if g.name in bones}
            for vertex in mesh.data.vertices:
                weights = [g for g in vertex.groups if g.group in groups and g.weight > 0]
                if len(weights) > 4:
                    raise ValueError('publication exceeds four bone influences')
                influenced.update(groups[g.group] for g in weights)
        if set(bones) - influenced:
            raise ValueError(f'publication lost bone influences: {name}')
        for bone, old in bones.items():
            new = after[name][bone]
            if old['parent'] != new['parent'] or any(
                abs(a-b) > 0.0001 for a,b in zip(old['matrix'], new['matrix'])
            ):
                raise ValueError(f'publication changed rest pose: {name}/{bone}')
    report_path.write_text(json.dumps({'schemaVersion': 2 if is_location else 1, 'rigs': reports,
                                      'restTransformsChanged': False,
                                      'textureMode': texture_mode,
                                      'materialSlots': remaining_material_slots,
                                      'locationRigManifest': published}), encoding='utf-8')


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) not in (3, 4):
        raise ValueError('expected source.fbx output.fbx report.json [texture_mode]')
    main(*map(Path, args[:3]), *(args[3:] or ["embedded"]))
