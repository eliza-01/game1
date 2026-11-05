"""Authoring contract for independent Real Estate physics geometry.

Name is the identity, not a material: COL_Floor, house_col, wall_COL_01.
An imported collider is a *model*, never an image consumer. Its geometry
should be authored as simple volumes; one mesh is supported but not guaranteed
to produce exact concave collisions in Roblox.
"""
from __future__ import annotations

from services.mesh_authoring_policy import (is_collision_mesh, is_glass_mesh,
    precise_by_default, normalize_fidelity, FIDELITIES)


def requires_texture(name: str) -> bool:
    return not is_collision_mesh(name)


def default_no_collide(name: str) -> bool:
    # Door and window glass are interactive/solid by default, like colliders.
    # This only supplies missing authoring flags; explicit saved values win.
    return not precise_collision_default(name)


# One authoring default for the UI, API and Studio physics policy.
COLLISION_FIDELITIES = FIDELITIES


def precise_collision_default(name: str) -> bool:
    return precise_by_default(name)


def default_collision_fidelity(name: str) -> str:
    return 'PreciseConvexDecomposition' if precise_collision_default(name) else 'Box'


def normalize_collision_fidelity(name: str, value: object, *, no_collide: bool | None = None) -> str:
    return normalize_fidelity(name, value, no_collide=no_collide is not False,
        default=default_collision_fidelity(name))
