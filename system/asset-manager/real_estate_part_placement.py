"""Authored mesh bounds in the house frame, shared across independent FBX parts.

The Roblox Model Asset importer can recenter meshes uploaded separately.  The
FBX author's *geometry-centre* offsets must be retained in the registration
manifest so Studio can restore the complete house assembly after LoadAssetAsync.
No asset or Blender source geometry is modified here.
"""
from __future__ import annotations

from math import isfinite


def _roblox(vector):
    """Convert a Blender house-local vector (Z up) to Roblox axes (Y up)."""
    x, y, z = vector
    # Roblox import of our FBX contract mirrors X and maps Blender Y to Roblox Z.
    # Verified against house, door and hinge world coordinates in Studio.
    return (-float(x), float(z), float(y))


def _bounds(points):
    coordinates = [tuple(float(v) for v in point) for point in points]
    if len(coordinates) < 2 or any(len(point) != 3 or not all(isfinite(v) for v in point)
                                   for point in coordinates):
        raise ValueError('Real Estate geometry bounds contain invalid coordinates')
    lower = tuple(min(point[axis] for point in coordinates) for axis in range(3))
    upper = tuple(max(point[axis] for point in coordinates) for axis in range(3))
    center = tuple((lower[i] + upper[i]) * 0.5 for i in range(3))
    size = tuple(upper[i] - lower[i] for i in range(3))
    if any(s <= 1e-5 for s in size):
        raise ValueError('Real Estate mesh has an unusable geometry bounding box')
    return center, size


def placement(house_corners, mesh_corners):
    """Record mesh AABB relative to the *house mesh AABB*, not the FBX origin.

    Corners supplied by Blender must already be in house-mesh coordinates.
    Coordinates are saved in the same axis convention as a Roblox MeshPart.
    """
    house_center, _ = _bounds(house_corners)
    center, size = _bounds(mesh_corners)
    offset = tuple(center[i] - house_center[i] for i in range(3))
    return {
        'version': 2,
        'centerInHouse': [round(value, 6) for value in _roblox(offset)],
        'size': [round(size[0], 6), round(size[2], 6), round(size[1], 6)],
    }


def inspect_placements(house, meshes):
    """Use Blender world matrices to resolve parented meshes into house space.

    Unsupported angled or mirrored mesh-local axes are omitted rather than
    fabricating a placement.  Those FBX assets retain legacy Sync behaviour.
    """
    inverse = house.matrix_world.inverted_safe()

    def corners(mesh):
        # Roblox imports surface geometry, dropping loose vertices and wires.
        # Blender bound_box includes those discarded points: using it records
        # a different size/centre from the actual published MeshPart.
        used = {index for face in mesh.data.polygons for index in face.vertices}
        if not used:
            raise ValueError(f'{mesh.name}: no surface faces for authored placement')
        transform = inverse @ mesh.matrix_world
        return [transform @ mesh.data.vertices[index].co for index in sorted(used)]

    house_corners = corners(house)
    output = {}
    for mesh in meshes:
        relative = inverse @ mesh.matrix_world
        axes = relative.to_3x3().normalized()
        if any(abs(axes[row][col] - (1.0 if row == col else 0.0)) > 1e-4
               for row in range(3) for col in range(3)):
            continue
        output[mesh.name] = placement(house_corners, corners(mesh))
    return output
