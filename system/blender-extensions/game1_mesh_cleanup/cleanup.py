"""Deterministic mesh cleanup mechanisms without UI or context dependencies."""

from dataclasses import dataclass
import math

import bmesh


@dataclass(frozen=True)
class CleanupStats:
    duplicate_faces_removed: int
    coincident_vertices_merged: int
    smooth_faces: int
    sharp_edges: int


def _quantized_coordinate(vertex, distance):
    return tuple(int(round(component / distance)) for component in vertex.co)


def _duplicate_faces(bm, merge_distance):
    """Return same-material, same-facing faces occupying identical coordinates."""
    grouped = {}
    duplicates = []
    for face in bm.faces:
        coordinate_key = tuple(
            sorted(_quantized_coordinate(vertex, merge_distance) for vertex in face.verts)
        )
        key = (face.material_index, len(face.verts), coordinate_key)
        candidates = grouped.setdefault(key, [])
        duplicate = next(
            (
                candidate
                for candidate in candidates
                if candidate.normal.dot(face.normal) > 0.99999
            ),
            None,
        )
        if duplicate is None:
            candidates.append(face)
        else:
            duplicates.append(face)
    return duplicates


def cleanup_mesh(mesh, merge_distance=1.0e-6, smooth_angle=math.radians(120.0)):
    """Repair one local mesh while preserving UV, material and color loop layers."""
    if merge_distance <= 0.0:
        raise ValueError("merge_distance must be positive")

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.normal_update()

        duplicate_faces = _duplicate_faces(bm, merge_distance)
        duplicate_count = len(duplicate_faces)
        if duplicate_faces:
            bmesh.ops.delete(bm, geom=duplicate_faces, context="FACES")

        vertices_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=merge_distance)
        merged_count = vertices_before - len(bm.verts)

        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.normal_update()

        for face in bm.faces:
            face.smooth = True

        sharp_edges = 0
        for edge in bm.edges:
            if len(edge.link_faces) != 2:
                edge.smooth = False
                sharp_edges += 1
                continue
            edge.smooth = edge.calc_face_angle(0.0) <= smooth_angle
            if not edge.smooth:
                sharp_edges += 1

        stats = CleanupStats(
            duplicate_faces_removed=duplicate_count,
            coincident_vertices_merged=merged_count,
            smooth_faces=len(bm.faces),
            sharp_edges=sharp_edges,
        )
        bm.to_mesh(mesh)
        mesh.update(calc_edges=True, calc_edges_loose=True)
        return stats
    finally:
        bm.free()
