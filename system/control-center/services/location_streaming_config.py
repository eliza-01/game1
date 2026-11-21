"""Project-owned Location visual LOD overrides and Roblox Workspace streaming profile.

One configuration feeds the UI, offline Place compiler and runtime manifest.
Changing it never edits the open Studio Place or publishes anything.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

from services.model_lod_common import distances_valid
import re
import tempfile

DEFAULT_SETTINGS = {
    'schemaVersion': 1,
    'modes': {'stone_fence_02': 'lod1', 'stone_pillar_03': 'lod1'},
    'distances': {'lod1': 120, 'lod2': 260, 'hide': 400, 'hysteresis': 12},
    'workspace': {
        'streamingEnabled': True,
        'minRadius': 64, 'targetRadius': 1024,
        'modelStreamingBehavior': 'Improved',
        'streamingIntegrityMode': 'PauseOutsideLoadedArea',
        'streamOutBehavior': 'Opportunistic',
    },
}
# Auto is the default for all registered Location Assets present in a Scan.
# Explicit modes override the default, not a whitelist for Runtime coverage.
MODES = ('auto', 'off', 'full', 'lod1', 'lod2')


def runtime_mode(settings: dict, slug: str) -> str:
    """Resolve published type policy; rig/effects never change selection rules."""
    mode = settings['modes'].get(slug, 'auto')
    return 'full' if mode == 'auto' else mode
WORLD_ENUMS = {
    'modelStreamingBehavior': ('Default', 'Legacy', 'Improved'),
    'streamingIntegrityMode': ('Default', 'Disabled', 'MinimumRadiusPause', 'PauseOutsideLoadedArea'),
    'streamOutBehavior': ('Default', 'LowMemory', 'Opportunistic'),
}


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {'schemaVersion', 'modes', 'distances', 'workspace'} or settings['schemaVersion'] != 1:
        raise ValueError('Invalid location streaming settings version/fields')
    modes = settings['modes']
    if not isinstance(modes, dict) or len(modes) > 100:
        raise ValueError('Invalid Location Asset selection')
    for slug, mode in modes.items():
        if not isinstance(slug, str) or not re.fullmatch('[a-z0-9][a-z0-9_]{0,63}', slug) or mode not in MODES:
            raise ValueError('Invalid Location Asset selection: ' + str(slug)[:80])
    distances = settings['distances']
    if not isinstance(distances, dict) or set(distances) != {'lod1', 'lod2', 'hide', 'hysteresis'}:
        raise ValueError('Expected LOD1 / LOD2 / Hide / Hysteresis distances')
    if any(type(distances[k]) is not int or not (0 <= distances[k] <= 10000) for k in distances):
        raise ValueError('LOD distances must be integer studs, between 0 and 10000')
    first, second, hide, h = (distances[k] for k in ('lod1', 'lod2', 'hide', 'hysteresis'))
    if not distances_valid((first, second), hide, h, minimum=16):
        raise ValueError('Require 16 <= LOD1 < LOD2 < Hide, with enough space for hysteresis')
    world = settings['workspace']
    if not isinstance(world, dict) or set(world) != set(DEFAULT_SETTINGS['workspace']):
        raise ValueError('Invalid Workspace streaming property list')
    if type(world['streamingEnabled']) is not bool:
        raise ValueError('Workspace StreamingEnabled must be boolean')
    for key, bounds in (('minRadius',(32,512)), ('targetRadius',(96,4096))):
        if type(world[key]) is not int or not (bounds[0] <= world[key] <= bounds[1]):
            raise ValueError(f'Workspace {key} must be between {bounds[0]} and {bounds[1]} studs')
    if world['targetRadius'] <= world['minRadius']:
        raise ValueError('Workspace StreamingTargetRadius must exceed StreamingMinRadius')
    for key, choices in WORLD_ENUMS.items():
        if world[key] not in choices:
            raise ValueError('Invalid Workspace ' + key)
    return settings


def settings_digest(settings):
    return hashlib.sha256(json.dumps(validate_settings(settings), sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


class LocationStreamingConfig:
    def __init__(self, root):
        self.path = Path(root) / 'config' / 'location_streaming.json'

    def read(self):
        if not self.path.exists():
            return copy.deepcopy(DEFAULT_SETTINGS)
        value = json.loads(self.path.read_text(encoding='utf-8'))
        return validate_settings(value)

    def save(self, patch, known_slugs):
        if not isinstance(patch, dict) or not patch or set(patch) - {'modes', 'distances', 'workspace'}:
            raise ValueError('Expected modes / distances / workspace settings')
        known = set(known_slugs)
        current = copy.deepcopy(self.read())
        for section, values in patch.items():
            if not isinstance(values, dict):
                raise ValueError(section + ' must be an object')
            if section == 'modes':
                if set(values) - known:
                    raise ValueError('Unknown registered Location Asset: ' + ', '.join(sorted(set(values) - known)))
            elif set(values) != set(current[section]):
                raise ValueError('Save all ' + section + ' fields together')
            current[section].update(values)
        validate_settings(current)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.location_streaming_', suffix='.tmp', dir=str(self.path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(current, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return current
