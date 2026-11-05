"""Shared FBX mesh roles and physics authoring contract for every asset domain.

Roblox requires PreciseConvexDecomposition whenever CanCollide=true (M207).
Box is the default only for non-colliding meshes. The same rules drive
Real Estate registration, Location inspection, Studio and Runtime.
"""
from __future__ import annotations
import re

_COLLIDER = re.compile(r'(?:^|_)col(?:_|$)', re.IGNORECASE)
FIDELITIES = ('Box', 'Hull', 'Default', 'PreciseConvexDecomposition')


def is_collision_mesh(name: str) -> bool:
    return isinstance(name, str) and bool(_COLLIDER.search(name))


def is_glass_mesh(name: str) -> bool:
    return isinstance(name, str) and 'glass' in name.casefold() and not is_collision_mesh(name)


def precise_by_default(name: str) -> bool:
    lower = str(name).casefold()
    return is_collision_mesh(name) or lower == 'door' or lower.startswith('door_') or is_glass_mesh(name)


def normalize_fidelity(name: str, value: object, *, no_collide: bool, default: str) -> str:
    if value is not None and (not isinstance(value, str) or value not in FIDELITIES):
        raise ValueError(f'{name}: invalid CollisionFidelity; choose {", ".join(FIDELITIES)}')
    return 'PreciseConvexDecomposition' if not no_collide else (value or default)


def mesh_defaults(name: str, *, has_collider: bool = False, domain: str = "estate") -> dict:
    """Shared defaults. A dedicated COL makes every other mesh visual-only."""
    collider = is_collision_mesh(name)
    glass = is_glass_mesh(name)
    # Location FBX without a COL keeps a solid authored visual by default;
    # Real Estate retains its visual/door defaults. Same normalization method.
    no_collide = (not collider if has_collider else
                  False if domain == 'location' else not precise_by_default(name))
    return {'glass': glass, 'noCollide': no_collide,
            'collisionFidelity': 'Box' if no_collide else 'PreciseConvexDecomposition',
            'doubleSided': True, 'collisionMesh': collider}


def normalize_mesh_options(name: str, raw: dict | None, *, has_collider: bool = False,
                           domain: str = 'estate') -> dict:
    defaults = mesh_defaults(name, has_collider=has_collider, domain=domain)
    if raw is not None and not isinstance(raw, dict):
        raise ValueError(f'{name}: mesh settings must be an object')
    entry = raw or {}
    for key in ('noCollide', 'doubleSided', 'glass'):
        if key in entry and type(entry[key]) is not bool:
            raise ValueError(f'{name}: {key} must be a boolean')
    no_collide = entry.get('noCollide', defaults['noCollide'])
    return {'glass': (entry.get('glass', defaults['glass']) if not defaults['collisionMesh'] else False),
            'noCollide': no_collide,
            'collisionFidelity': normalize_fidelity(name, entry.get('collisionFidelity'),
                no_collide=no_collide, default=defaults['collisionFidelity']),
            'doubleSided': entry.get('doubleSided', defaults['doubleSided']),
            'collisionMesh': defaults['collisionMesh']}


def normalize_location_options(analysis: dict, raw: dict | None) -> dict:
    """Reject stale/unknown mesh names and derive collision fidelity on the server."""
    meshes = [m['name'] for m in analysis['meshes']]
    if raw is not None and not isinstance(raw, dict):
        raise ValueError('meshOptions must be an object')
    raw = raw or {}
    unknown = set(raw) - set(meshes)
    if unknown:
        raise ValueError('meshOptions references missing FBX meshes: ' + ', '.join(sorted(unknown)))
    return {name: normalize_mesh_options(name, raw.get(name),
        has_collider=bool(analysis['hasCollider']), domain='location') for name in meshes}


def location_mesh_profile(name: str, *, has_collider: bool) -> dict:
    """Inspector defaults. Explicit authoring overrides are stored separately."""
    flags = mesh_defaults(name, has_collider=has_collider)
    collider = flags['collisionMesh']
    glass = flags['glass']
    if collider:
        return {'role':'collider', 'canCollide': True, 'canQuery': True,
                'canTouch': False, 'doubleSided': True,
                'collisionFidelity':'PreciseConvexDecomposition', 'physicsOnly':True}
    if has_collider:
        return {'role':'glass' if glass else 'visual', 'canCollide': False,
                'canQuery': False, 'canTouch': False, 'doubleSided': True,
                'collisionFidelity': 'Box', 'physicsOnly':False}
    return {'role':'glass' if glass else 'visual',
            'canCollide': True if glass else None,
            'canQuery': True if glass else None,
            'canTouch': False, 'doubleSided': True,
            'collisionFidelity':'PreciseConvexDecomposition' if glass else None,
            'physicsOnly':False}
