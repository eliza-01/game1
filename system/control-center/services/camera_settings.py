"""Shared authoring validation for camera options and Studio debug drafts.

All values are screen-normalized or in Roblox studs/degrees. No camera runtime
logic, HTTP, plugin APIs or filesystem dependencies belong here.
"""
from __future__ import annotations

import math

DEFAULT_CAMERA = {
    'targetHeight': 5.5,
    'distance': 10.0,
    'pitchDegrees': -12.0,
    'characterX': 0.5,
    'characterY': 0.5,
    'cursorX': 0.5,
    'cursorY': 0.5,
}
CAMERA_LIMITS = {
    'targetHeight': (0, 12),
    'distance': (4, 18),
    'pitchDegrees': (-65, 60),
    'characterX': (0.2, 0.8),
    'characterY': (0.2, 0.8),
    'cursorX': (0.1, 0.9),
    'cursorY': (0.1, 0.9),
}


def normalize_camera(data: dict, *, base: dict | None = None) -> dict:
    if not isinstance(data, dict):
        raise ValueError('camera settings must be an object')
    extras = set(data) - set(DEFAULT_CAMERA)
    if extras:
        raise ValueError('unknown camera fields: ' + ', '.join(sorted(extras)))
    result = {**DEFAULT_CAMERA, **(base or {}), **data}
    for key, (low, high) in CAMERA_LIMITS.items():
        if type(result[key]) not in (float, int):
            raise ValueError(f'camera {key} must be a number')
        value = float(result[key])
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'camera {key} must be within {low}..{high}')
        result[key] = round(value, 5)
    return result
