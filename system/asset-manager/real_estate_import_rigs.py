"""Normalize Blender's imported Real Estate rigs to the source FBX contract.

A nested Model(Null) armature is an *object*, not a parent bone. Blender's
importer can collapse it into the enclosing armature. Split the imported data
in memory, preserving every authored rest matrix and every mesh world matrix.
The source FBX and existing published assets remain untouched.
"""
from __future__ import annotations

from real_estate_fbx_hierarchy import authored_rigs


MATRIX_TOLERANCE = 1e-4


def _bone_order(expected, parents):
    """Use a deterministic parent-first order; reject cycles and foreign parents."""
    remaining = set(expected)
    ordered = []
    while remaining:
        ready = sorted(name for name in remaining if not parents[name] or parents[name] in ordered)
        if not ready:
            raise RuntimeError('Authored FBX rig has a cyclic or cross-armature bone parent')
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def _retain_authored_bones(bpy, rig, expected, parents):
    order = _bone_order(expected, parents)
    original = {bone.name: bone.matrix_local.copy() for bone in rig.data.bones
                if bone.name in expected}
    if set(original) != set(expected):
        raise RuntimeError(f'{rig.name}: Blender lost authored FBX bones: '
                           + ', '.join(sorted(set(expected) - set(original))))
    if (set(b.name for b in rig.data.bones) == set(expected)
            and all((rig.data.bones[name].parent.name
                     if rig.data.bones[name].parent else '') == parents[name]
                    for name in order)):
        return
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        editable = rig.data.edit_bones
        rest = {name: editable[name].matrix.copy() for name in order}
        # Unlink everything first: removing Blender's synthetic container bone
        # must not redirect the hinge's orientation or head position.
        for name in order:
            editable[name].use_connect = False
            editable[name].parent = None
        for bone in list(editable):
            if bone.name not in expected:
                editable.remove(bone)
        for name in order:
            parent = parents[name]
            if parent:
                if parent not in expected:
                    raise RuntimeError(f'{rig.name}/{name}: FBX parent {parent} is outside its armature')
                editable[name].parent = editable[parent]
            editable[name].matrix = rest[name]
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    for name, before in original.items():
        after = rig.data.bones[name].matrix_local
        if any(abs(float(a) - float(b)) > MATRIX_TOLERANCE
               for left, right in zip(before, after) for a, b in zip(left, right)):
            raise RuntimeError(f'{rig.name}/{name}: rig reconstruction changed the rest transform')
        expected_parent = parents[name]
        actual_parent = rig.data.bones[name].parent
        if (actual_parent.name if actual_parent else '') != expected_parent:
            raise RuntimeError(f'{rig.name}/{name}: rig reconstruction changed the parent')

def _restore_mesh_binding(mesh, target):
    """Rebuild the source-FBX mesh -> armature link, not just existing modifiers.

    Blender can import a nested armature's skin as a parent-only relationship.
    Once that wrong parent is removed, find_rig() would treat the mesh as
    unrigged unless we create its Armature modifier explicitly. The authored
    Skin/Cluster (or object-parent) mapping has already selected *target*.
    """
    original_world = mesh.matrix_world.copy()
    modifiers = [mod for mod in mesh.modifiers if mod.type == 'ARMATURE']
    if len(modifiers) > 1:
        raise RuntimeError(f'{mesh.name}: multiple armature modifiers after FBX import')

    if mesh.parent is not None and mesh.parent.type == 'ARMATURE' and mesh.parent != target:
        mesh.parent = None
        mesh.matrix_world = original_world

    if not modifiers:
        # Missing modifiers are expected when Blender converts nested FBX
        # armatures to bones; the FBX skin link is authoritative, not a guess
        # from the mesh name. prepare_rig() subsequently verifies weights.
        modifier = mesh.modifiers.new(name='Game1RecoveredFBXRig', type='ARMATURE')
    else:
        modifier = modifiers[0]
    modifier.object = target

    if any(abs(float(a) - float(b)) > MATRIX_TOLERANCE
           for left, right in zip(original_world, mesh.matrix_world)
           for a, b in zip(left, right)):
        raise RuntimeError(f'{mesh.name}: mesh reconstruction changed its world transform')


def restore_authored_rigs(bpy, source):
    """Restore separate armature objects before either Inspect or publication.

    No scene work is necessary for conventional non-nested FBX files. For
    nested authoring, refuse ambiguous bone/skin mappings instead of silently
    emitting a damaged model. This function is deliberately shared by both
    Blender entrypoints.
    """
    authored = authored_rigs(source)
    if not authored.nested:
        return
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
    imported = {}
    for name, bone_names in authored.bones.items():
        matches = [rig for rig in armatures
                   if bone_names.issubset({bone.name for bone in rig.data.bones})]
        if len(matches) != 1:
            raise RuntimeError(f'{name}: expected one imported armature containing its '
                               f'{len(bone_names)} FBX bones, found {len(matches)}')
        imported[name] = matches[0]

    merged = {}
    for name, rig in imported.items():
        merged.setdefault(rig.name, []).append(name)

    repaired = {}
    for source_name, groups in merged.items():
        source_rig = next(rig for rig in armatures if rig.name == source_name)
        # Prefer keeping the correct outer rig object and its original name.
        primary = source_rig.name if source_rig.name in groups else groups[0]
        if source_rig.name != primary:
            raise RuntimeError(f'FBX importer renamed {primary} to {source_rig.name}; '
                               'cannot safely recover the authored armature identity')
        for name in groups:
            if name == primary:
                repaired[name] = source_rig
                continue
            if bpy.data.objects.get(name) is not None:
                raise RuntimeError(f'Cannot recover {name}: an object already has that name')
            new_rig = bpy.data.objects.new(name, source_rig.data.copy())
            source_rig.users_collection[0].objects.link(new_rig)
            new_rig.matrix_world = source_rig.matrix_world.copy()
            repaired[name] = new_rig
        for name in groups:
            _retain_authored_bones(bpy, repaired[name], authored.bones[name], authored.parents[name])

    # FBX Skin / Cluster bindings identify the mesh's real rig, even when
    # Blender attached the mesh to the collapsed parent armature. No guessing
    # by mesh name (door, chest, etc.) and no edits to vertex weights.
    for mesh in [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']:
        owner_name = authored.mesh_rigs.get(mesh.name)
        if not owner_name:
            continue
        target = repaired.get(owner_name)
        if target is None:
            raise RuntimeError(f'{mesh.name}: authored armature {owner_name} is missing')
        _restore_mesh_binding(mesh, target)
