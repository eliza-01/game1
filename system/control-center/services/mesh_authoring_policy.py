"""Visual-mesh physics authoring. Dedicated COL geometry was retired in M342."""
from __future__ import annotations
from services.retired_col_mesh import retired

FIDELITIES = ('Box', 'Hull', 'Default', 'PreciseConvexDecomposition')


def is_location_carrier(name: str) -> bool:
    return isinstance(name, str) and name.casefold() == 'rig_carrier'


def is_collision_mesh(name: str) -> bool:
    """Input quarantine only, never a publishable mesh role."""
    return retired(name)


def is_glass_mesh(name: str) -> bool:
    return isinstance(name, str) and 'glass' in name.casefold()


def normalize_fidelity(name: str, value: object, *, no_collide: bool, default: str) -> str:
    if value is not None and (not isinstance(value, str) or value not in FIDELITIES):
        raise ValueError(f'{name}: invalid CollisionFidelity; choose {", ".join(FIDELITIES)}')
    return value or default


def mesh_defaults(name: str, *, has_collider: bool = False, domain: str = 'estate') -> dict:
    # Location visual physics remains user-configurable. Estate visual geometry
    # is non-collidable by default until an independent Part blueprint exists.
    return {'glass': is_glass_mesh(name), 'noCollide': domain != 'location',
            'collisionFidelity': 'Box', 'doubleSided': False}


def normalize_mesh_options(name: str, raw: dict | None, *, has_collider: bool = False,
                           domain: str = 'estate') -> dict:
    defaults = mesh_defaults(name, domain=domain)
    if raw is not None and not isinstance(raw, dict):
        raise ValueError(f'{name}: mesh settings must be an object')
    entry = raw or {}
    for key in ('noCollide', 'doubleSided', 'glass'):
        if key in entry and type(entry[key]) is not bool:
            raise ValueError(f'{name}: {key} must be a boolean')
    no_collide = entry.get('noCollide', defaults['noCollide'])
    return {'glass': entry.get('glass', defaults['glass']), 'noCollide': no_collide,
            'collisionFidelity': normalize_fidelity(name, entry.get('collisionFidelity'),
                no_collide=no_collide, default='Box'),
            'doubleSided': entry.get('doubleSided', defaults['doubleSided'])}


def normalize_location_options(analysis: dict, raw: dict | None) -> dict:
    meshes = [m['name'] for m in analysis['meshes']
              if not is_location_carrier(m['name']) and not retired(m['name'])]
    if raw is not None and not isinstance(raw, dict):
        raise ValueError('meshOptions must be an object')
    raw = {name: value for name, value in (raw or {}).items() if not retired(name)}
    unknown = set(raw) - set(meshes)
    if unknown:
        raise ValueError('meshOptions references missing FBX meshes: ' + ', '.join(sorted(unknown)))
    return {name: normalize_mesh_options(name, raw.get(name), domain='location') for name in meshes}


def location_mesh_profile(name: str, *, has_collider: bool) -> dict:
    if is_location_carrier(name):
        return {'role':'carrier', 'canCollide':False, 'canQuery':False,
                'canTouch':False, 'doubleSided':False,
                'collisionFidelity':'Box', 'physicsOnly':True}
    glass = is_glass_mesh(name)
    return {'role':'glass' if glass else 'visual',
            'canCollide': True if glass else None,
            'canQuery': True if glass else None,
            'canTouch': False, 'doubleSided': False,
            'collisionFidelity':'Box' if glass else None, 'physicsOnly':False}
