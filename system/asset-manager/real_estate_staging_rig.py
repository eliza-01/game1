"""Isolate one mesh's bone ownership without editing the shared authoring rig."""
from contextlib import contextmanager


@contextmanager
def isolated_rig(bpy, mesh, source, retained):
    """Preserve the source's identity/rest space in a disposable FBX rig copy."""
    expected = {bone['name']: bone for bone in retained}
    before = {bone.name: bone.matrix_local.copy() for bone in source.data.bones}
    if not set(expected).issubset(before):
        raise ValueError('Publication requested bones absent from the source rig')
    for bone in expected.values():
        if bone.get('parent') and bone['parent'] not in expected:
            raise ValueError('Publication must retain every ancestor of a weighted bone')
    world = mesh.matrix_world.copy()
    source_name = source.name
    old_parent, parent_type, parent_bone = mesh.parent, mesh.parent_type, mesh.parent_bone
    parent_inverse = mesh.matrix_parent_inverse.copy()
    modifiers = [mod for mod in mesh.modifiers if mod.type == 'ARMATURE']
    targets = [(mod, mod.object) for mod in modifiers]
    created_modifier = None
    clone = source.copy()
    clone.data = source.data.copy()
    data = clone.data
    bpy.context.scene.collection.objects.link(clone)
    try:
        clone.parent = None
        clone.matrix_world = source.matrix_world.copy()
        # Independent files keep the registered armature name. Temporarily
        # release it in this background staging scene, never in the .blend.
        source.name = '__game1_source_' + source_name
        clone.name = source_name
        bpy.ops.object.select_all(action='DESELECT')
        clone.select_set(True)
        bpy.context.view_layer.objects.active = clone
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            for bone in list(clone.data.edit_bones):
                if bone.name not in expected:
                    clone.data.edit_bones.remove(bone)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        for name, bone in expected.items():
            actual = clone.data.bones[name]
            if (actual.parent.name if actual.parent else '') != (bone.get('parent') or ''):
                raise RuntimeError('Staging changed bone hierarchy: ' + name)
            if max(abs(x-y) for a,b in zip(before[name], actual.matrix_local) for x,y in zip(a,b)) > 1e-4:
                raise RuntimeError('Staging changed bone rest transform: ' + name)
        if mesh.parent == source:
            mesh.parent = clone
            mesh.matrix_world = world
        for mod in modifiers:
            if mod.object == source:
                mod.object = clone
        if not any(mod.object == clone for mod in modifiers):
            created_modifier = mesh.modifiers.new(name='Game1RealEstateRig', type='ARMATURE')
            created_modifier.object = clone
        bpy.context.view_layer.update()
        yield clone
    finally:
        for mod, target in targets:
            mod.object = target
        if created_modifier is not None:
            mesh.modifiers.remove(created_modifier)
        mesh.parent = old_parent
        mesh.parent_type = parent_type
        mesh.parent_bone = parent_bone
        mesh.matrix_parent_inverse = parent_inverse
        mesh.matrix_world = world
        bpy.data.objects.remove(clone, do_unlink=True)
        if data.users == 0:
            bpy.data.armatures.remove(data)
        source.name = source_name
        bpy.context.view_layer.update()
