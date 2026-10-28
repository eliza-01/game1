"""Background staging for static or rigged model assets (location assets/weapons)."""
import json
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_publication import clean_scene, linked_meshes, prepare_rig, export_model, rest_snapshot


def snapshot():
    return {o.name: rest_snapshot(o) for o in bpy.context.scene.objects if o.type == 'ARMATURE'}


def main(source, output, report_path):
    if source.resolve() == output.resolve():
        raise ValueError('publication output must differ from source')
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    objects = sorted((o for o in bpy.context.scene.objects if o.type in {'MESH', 'ARMATURE'}),
                     key=lambda o: o.name)
    if not any(o.type == 'MESH' for o in objects):
        raise ValueError('Model FBX has no mesh')
    before = snapshot()
    reports = {}
    for rig in objects:
        if rig.type == 'ARMATURE' and len(rig.data.bones):
            reports[rig.name] = prepare_rig(rig, linked_meshes(rig))
    export_model(output, objects, embed_textures=True)
    # Round-trip the actual staged file, not just the pre-export Python objects.
    clean_scene()
    bpy.ops.import_scene.fbx(filepath=str(output), use_anim=False)
    after = snapshot()
    if before.keys() != after.keys():
        raise ValueError('publication changed armatures')
    for name, bones in before.items():
        if bones.keys() != after[name].keys():
            raise ValueError(f'publication changed bone set: {name}')
        rig = bpy.data.objects[name]
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
    report_path.write_text(json.dumps({'schemaVersion': 1, 'rigs': reports,
                                      'restTransformsChanged': False}), encoding='utf-8')


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    if len(args) != 3:
        raise ValueError('expected source.fbx output.fbx report.json')
    main(*map(Path, args))
