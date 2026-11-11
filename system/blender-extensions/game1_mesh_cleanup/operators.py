"""Scene-scoped operator for the Game1 mesh cleanup extension."""

import math

import bpy

from .cleanup import cleanup_mesh
from .image_bleed import create_mip_safe_copies


class GAME1MESH_PG_settings(bpy.types.PropertyGroup):
    merge_distance: bpy.props.FloatProperty(
        name="Merge distance",
        description="Maximum distance for coincident vertices",
        default=1.0e-6,
        min=1.0e-8,
        soft_max=1.0e-4,
        precision=7,
        unit="LENGTH",
    )
    smooth_angle: bpy.props.FloatProperty(
        name="Smooth angle",
        description="Keep edges sharper than this angle hard",
        default=math.radians(120.0),
        min=0.0,
        max=math.pi,
        subtype="ANGLE",
    )
    include_hidden: bpy.props.BoolProperty(
        name="Include hidden",
        description="Process hidden Mesh objects in the active scene",
        default=False,
    )


def _scene_materials(context, include_hidden):
    return {
        material
        for obj in context.scene.objects
        if obj.type == "MESH" and (include_hidden or obj.visible_get())
        for material in obj.data.materials
        if material is not None
    }


class GAME1MESH_OT_repair_scene(bpy.types.Operator):
    """Repair exact duplicate faces, coincident seams and normals on all scene meshes"""

    bl_idname = "game1_mesh.repair_scene"
    bl_label = "Repair All Scene Meshes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene) and any(
            obj.type == "MESH" for obj in context.scene.objects
        )

    def execute(self, context):
        settings = context.scene.game1_mesh_cleanup
        active_object = context.view_layer.objects.active
        restore_edit_mode = bool(active_object and active_object.mode == "EDIT")
        if restore_edit_mode:
            bpy.ops.object.mode_set(mode="OBJECT")

        meshes = []
        seen = set()
        skipped_shape_keys = 0
        skipped_linked = 0
        for obj in context.scene.objects:
            if obj.type != "MESH":
                continue
            if not settings.include_hidden and not obj.visible_get():
                continue
            mesh = obj.data
            if mesh in seen:
                continue
            seen.add(mesh)
            if mesh.library is not None or not mesh.is_editable:
                skipped_linked += 1
                continue
            if mesh.shape_keys is not None:
                skipped_shape_keys += 1
                continue
            meshes.append(mesh)

        totals = {
            "duplicate_faces_removed": 0,
            "coincident_vertices_merged": 0,
            "smooth_faces": 0,
            "sharp_edges": 0,
        }
        errors = []
        try:
            for mesh in meshes:
                try:
                    stats = cleanup_mesh(
                        mesh,
                        merge_distance=settings.merge_distance,
                        smooth_angle=settings.smooth_angle,
                    )
                    for field in totals:
                        totals[field] += getattr(stats, field)
                except Exception as exc:  # isolate one malformed mesh from the scene
                    errors.append(f"{mesh.name}: {exc}")
        finally:
            if restore_edit_mode and active_object is not None:
                context.view_layer.objects.active = active_object
                active_object.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")

        if errors:
            self.report({"WARNING"}, f"Skipped {len(errors)} failed meshes; see Console")
            for error in errors:
                print(f"Game1 Mesh Cleanup: {error}")

        self.report(
            {"INFO"},
            (
                f"Meshes {len(meshes)}; duplicate faces "
                f"{totals['duplicate_faces_removed']}; merged vertices "
                f"{totals['coincident_vertices_merged']}; skipped shape keys "
                f"{skipped_shape_keys}; linked {skipped_linked}"
            ),
        )
        return {"FINISHED"}


class GAME1MESH_OT_fix_mip_bleed(bpy.types.Operator):
    """Create mip-safe alpha-atlas copies and rewire scene materials"""

    bl_idname = "game1_mesh.fix_mip_bleed"
    bl_label = "Mip Bleed Only"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene) and any(
            obj.type == "MESH" for obj in context.scene.objects
        )

    def execute(self, context):
        settings = context.scene.game1_mesh_cleanup
        materials = _scene_materials(context, settings.include_hidden)
        stats = create_mip_safe_copies(materials)
        self.report(
            {"INFO"},
            (
                f"Mip-safe images {stats.images_created}; "
                f"image nodes rewired {stats.nodes_rewired}"
            ),
        )
        return {"FINISHED"}
