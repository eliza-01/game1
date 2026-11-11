"""Headless smoke test run by Blender, not Python's standalone interpreter."""

import importlib.util
from pathlib import Path
import sys

import bpy


extension_root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "game1_mesh_cleanup.cleanup", extension_root / "cleanup.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


mesh = bpy.data.meshes.new("cleanup_test")
mesh.from_pydata(
    [
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
    ],
    [],
    [(0, 1, 2), (3, 4, 5)],
)
stats = module.cleanup_mesh(mesh)
assert stats.duplicate_faces_removed == 1, stats
assert stats.coincident_vertices_merged == 0, stats
assert len(mesh.polygons) == 1
assert len(mesh.vertices) == 3
print("GAME1_MESH_CLEANUP_TEST=PASS")
