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
    return not is_collision_mesh(name) and str(name).casefold() not in (
        'door', 'window_frames_glass',
    )
