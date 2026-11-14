"""Real Estate visual mesh physics defaults (M342).

COL_* is retired; it is only detected by services.retired_col_mesh during
FBX filtering and migration. Solid visual meshes are explicitly configured.
"""
from __future__ import annotations
from services.mesh_authoring_policy import FIDELITIES, normalize_fidelity


def requires_texture(name: str) -> bool:
    return True


def default_no_collide(name: str) -> bool:
    return True  # all static visual house geometry defaults non-colliding

COLLISION_FIDELITIES = FIDELITIES


def default_collision_fidelity(name: str) -> str:
    return 'Box'


def normalize_collision_fidelity(name: str, value: object, *, no_collide: bool | None = None) -> str:
    return normalize_fidelity(name, value, no_collide=no_collide is not False, default='Box')
