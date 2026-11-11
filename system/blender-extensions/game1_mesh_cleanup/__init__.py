"""Game1 one-click mesh cleanup extension."""

import bpy

from . import operators, ui


CLASSES = (
    operators.GAME1MESH_PG_settings,
    operators.GAME1MESH_OT_repair_scene,
    operators.GAME1MESH_OT_fix_mip_bleed,
    ui.GAME1MESH_PT_cleanup,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.game1_mesh_cleanup = bpy.props.PointerProperty(
        type=operators.GAME1MESH_PG_settings
    )
    bpy.types.VIEW3D_MT_object.append(ui.menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(ui.menu_func)
    del bpy.types.Scene.game1_mesh_cleanup
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
