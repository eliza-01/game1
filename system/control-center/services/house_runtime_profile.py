"""Per-house visual-streaming authoring contract.

This is configuration, not a second streamer. The common LocationWorldStreamer
will eventually consume the compiled house rows. Server collision/socket/door
ownership is unaffected by these visual-only distances.
"""
from __future__ import annotations

from real_estate.contracts import HOUSE_NAME
DEFAULT = {'mode': 'off', 'lod1': 150, 'hide': 400, 'hysteresis': 10}
MODES = ('off', 'full', 'lod1')


def validate(slug: str, value: dict) -> dict:
    if not isinstance(slug, str) or not HOUSE_NAME.fullmatch(slug):
        raise ValueError('invalid house type')
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise ValueError('expected house mode / lod1 / hide / hysteresis')
    if value['mode'] not in MODES:
        raise ValueError('invalid house streaming mode')
    a, b, h = (value[name] for name in ('lod1', 'hide', 'hysteresis'))
    if any(type(v) is not int for v in (a,b,h)) or not (20 <= a < b <= 10000 and 0 <= h <= 100
        and a > h and b - a > 2 * h):
        raise ValueError('House LOD1 / Hide distances need valid hysteresis (20 <= LOD1 < Hide <= 10000)')
    return {key: value[key] for key in DEFAULT}


def readiness(house: dict, settings: dict, lod1: dict) -> dict:
    """Report authoring blockers without claiming unsupported runtime readiness."""
    warnings = []
    if house['status'] != 'PUBLISHED':
        warnings.append('Publish all house meshes and atlases before Runtime build')
    for part in house.get('meshParts', []):
        options = house.get('meshOptions', {}).get(part, {})
        if options.get('distanceStreaming') is True and options.get('loadDistanceStuds', 50) >= settings['lod1'] and settings['mode'] == 'lod1':
            warnings.append(f'{part}: FULL distance must be below house LOD1 ({settings["lod1"]} studs)')
    if settings['mode'] == 'lod1' and lod1.get('status') != 'PUBLISHED':
        warnings.append('Publish House LOD1 before selecting FULL / LOD1')
    # A source Place must be compiled and Studio-verified before the profile is
    # capable of freeing instances; saved metadata is never a publish approval.
    return {'readyForCompilation': not warnings and settings['mode'] != 'off',
            'runtimeVerified': False, 'warnings': warnings}
