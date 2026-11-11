"""N-panel UI for Game1 mesh cleanup."""

import bpy


class GAME1MESH_PT_cleanup(bpy.types.Panel):
    bl_label = "Mesh Cleanup"
    bl_idname = "GAME1MESH_PT_cleanup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Game1"

    def draw(self, context):
        settings = context.scene.game1_mesh_cleanup
        layout = self.layout
        column = layout.column(align=True)
        column.use_property_split = True
        column.prop(settings, "merge_distance")
        column.prop(settings, "smooth_angle")
        column.prop(settings, "include_hidden")
        layout.separator()
        layout.operator("game1_mesh.repair_scene", icon="MODIFIER")
        layout.operator("game1_mesh.fix_mip_bleed", icon="IMAGE_DATA")
        layout.label(text="Mesh cleanup supports one-step Undo", icon="INFO")
        layout.label(text="Source images stay unchanged", icon="IMAGE_DATA")


def menu_func(self, context):
    self.layout.operator("game1_mesh.repair_scene", icon="MODIFIER")
