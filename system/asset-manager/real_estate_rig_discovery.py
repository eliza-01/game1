"""Identify each Real Estate mesh's own armature from FBX object relationships.

Names are hints, not a requirement. An unrigged mesh is valid.
"""


def find_mesh(bpy, part):
    matches = [obj for obj in bpy.context.scene.objects
               if obj.type == 'MESH' and obj.name.casefold() == part.casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"FBX needs a mesh named '{part}' (found {len(matches)}). Check Blender's Outliner.")
    return matches[0]


def find_rig(bpy, mesh, part):
    linked = [mod.object for mod in mesh.modifiers
              if mod.type == 'ARMATURE' and mod.object is not None]
    if mesh.parent is not None and mesh.parent.type == 'ARMATURE':
        linked.append(mesh.parent)
    unique = []
    for rig in linked:
        if all(other.name != rig.name for other in unique):
            unique.append(rig)
    if len(unique) > 1:
        raise RuntimeError(f"'{part}' references more than one armature. Use one armature per mesh.")
    if unique:
        return unique[0]
    # A similarly named armature is NOT a link. In particular, a separate
    # chest/door rig in the same Blender scene must never be adopted by name.
    return None
