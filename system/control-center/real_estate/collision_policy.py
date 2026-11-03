"""Authoring contract for independent Real Estate physics geometry.

Name is the identity, not a material: COL_Floor, house_col, wall_COL_01.
An imported collider is a *model*, never an image consumer. Its geometry
should be authored as simple volumes; one mesh is supported but not guaranteed
to produce exact concave collisions in Roblox.
"""
from __future__ import annotations

import re

_COLLISION_TOKEN = re.compile(r"(?:^|_)col(?:_|$)", re.IGNORECASE)


def is_collision_mesh(name: str) -> bool:
    return isinstance(name, str) and bool(_COLLISION_TOKEN.search(name))


def requires_texture(name: str) -> bool:
    return not is_collision_mesh(name)


def default_no_collide(name: str) -> bool:
    # Door and window glass are interactive/solid by default, like colliders.
    # This only supplies missing authoring flags; explicit saved values win.
    return not precise_collision_default(name)


# One authoring default for the UI, API and Studio physics policy.
COLLISION_FIDELITIES = ('Box', 'Hull', 'Default', 'PreciseConvexDecomposition')


def precise_collision_default(name: str) -> bool:
    lower = str(name).casefold()
    return is_collision_mesh(lower) or lower == 'door' or lower.startswith('door_') or 'glass' in lower


def default_collision_fidelity(name: str) -> str:
    return 'PreciseConvexDecomposition' if precise_collision_default(name) else 'Box'


def normalize_collision_fidelity(name: str, value: object) -> str:
    if value is None:
        return default_collision_fidelity(name)
    if not isinstance(value, str) or value not in COLLISION_FIDELITIES:
        raise ValueError(f'{name}: invalid CollisionFidelity; choose {", ".join(COLLISION_FIDELITIES)}')
    return value
