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

import re
import tempfile
from threading import RLock
from .model_lod_common import distances_valid

DEFAULT_DISTANCES = {'lod1': 120, 'lod2': 260, 'hide': 400}
DEFAULT_HYSTERESIS = 10
DEFAULT_SETTINGS = {
    'schemaVersion': 2,
    'modes': {'stone_fence_02': 'lod1', 'stone_pillar_03': 'lod1'},
    'assetDistances': {},
    'hysteresis': DEFAULT_HYSTERESIS,
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


def distance_profile(settings, slug):
    # Defaults are an initialization value, never a mutable shared profile.
    return normalize_distances(settings['assetDistances'].get(slug, DEFAULT_DISTANCES),
                               runtime_mode(settings, slug), settings['hysteresis'])


def _distance_fields(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_DISTANCES):
        raise ValueError('Expected LOD1 / LOD2 / Hide distances')
    if any(type(v) is not int or not 1 <= v <= 10000 for v in value.values()):
        raise ValueError('LOD distances must be integer studs, between 1 and 10000')


def normalize_distances(value, mode, h):
    _distance_fields(value)
    result = dict(value)
    minimum, gap = max(16, h + 1), 2 * h + 1
    active = ['lod1', 'lod2'] if mode == 'lod2' else ['lod1'] if mode == 'lod1' else []
    result['hide'] = max(result['hide'], minimum + gap * len(active))
    ceiling = result['hide']
    for index in reversed(range(len(active))):
        key = active[index]
        result[key] = max(minimum + index * gap, min(result[key], ceiling - gap))
        ceiling = result[key]
    return result


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {'schemaVersion', 'modes', 'assetDistances', 'workspace', 'hysteresis'} or settings['schemaVersion'] != 2:
        raise ValueError('Invalid location streaming settings version/fields')
    if type(settings['hysteresis']) is not int or not 0 <= settings['hysteresis'] <= 100:
        raise ValueError('Hysteresis must be an integer from 0 to 100')
    modes = settings['modes']
    if not isinstance(modes, dict) or len(modes) > 5000:
        raise ValueError('Invalid Location Asset selection')
    for slug, mode in modes.items():
        if not isinstance(slug, str) or not re.fullmatch('[a-z0-9][a-z0-9_]{0,63}', slug) or mode not in MODES:
            raise ValueError('Invalid Location Asset selection: ' + str(slug)[:80])
    profiles = settings['assetDistances']
    if not isinstance(profiles, dict) or len(profiles) > 5000:
        raise ValueError('Invalid Location Asset distances')
    for slug, profile in profiles.items():
        if not isinstance(slug, str) or not re.fullmatch('[a-z0-9][a-z0-9_]{0,63}', slug):
            raise ValueError('Invalid Location Asset slug')
        mode, h = runtime_mode(settings, slug), settings['hysteresis']
        if normalize_distances(profile, mode, h) != profile:
            raise ValueError(f'{slug}: invalid LOD distances / hysteresis')
        steps = (profile['lod1'], profile['lod2']) if mode == 'lod2' else (profile['lod1'],) if mode == 'lod1' else ()
        if steps and not distances_valid(steps, profile['hide'], h, minimum=16):
            raise ValueError(f'{slug}: invalid LOD transition intervals')
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
        self._lock = RLock()

    def read(self, known_slugs=None):
        with self._lock:
            value = (json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists()
                     else copy.deepcopy(DEFAULT_SETTINGS))
            if value.get('schemaVersion') == 1:
                if known_slugs is None:
                    raise ValueError('Registered assets required to migrate LOD settings')
                old = value.pop('distances')
                value['hysteresis'] = old.pop('hysteresis')
                _distance_fields(old)
                value['schemaVersion'] = 2
                value['assetDistances'] = {slug: normalize_distances(old, runtime_mode(value, slug), value['hysteresis'])
                                           for slug in set(known_slugs) | set(value['modes'])}
                validate_settings(value)
                self._write(value)
            validate_settings(value)
            missing = set(known_slugs or ()) - set(value['assetDistances'])
            if missing:
                for slug in missing:
                    value['assetDistances'][slug] = distance_profile(value, slug)
                validate_settings(value)
                self._write(value)
            return value

    def save(self, patch, known_slugs):
        with self._lock:
            return self._save(patch, set(known_slugs))

    def _save(self, patch, known):
        if not isinstance(patch, dict) or not patch or set(patch) - {'modes', 'assetDistances', 'workspace', 'hysteresis'}:
            raise ValueError('Expected modes / assetDistances / hysteresis / workspace settings')
        current = copy.deepcopy(self.read(known))
        for section, values in patch.items():
            if section == 'hysteresis':
                if type(values) is not int or not 0 <= values <= 100:
                    raise ValueError('Hysteresis must be an integer from 0 to 100')
                current[section] = values
                continue
            if not isinstance(values, dict):
                raise ValueError(section + ' must be an object')
            if section in ('modes', 'assetDistances'):
                if set(values) - known:
                    raise ValueError('Unknown registered Location Asset: ' + ', '.join(sorted(set(values) - known)))
            elif set(values) != set(current[section]):
                raise ValueError('Save all ' + section + ' fields together')
            current[section].update(values)
        for slug in set(current['assetDistances']) | set(patch.get('modes', {})):
            current['assetDistances'][slug] = distance_profile(current, slug)
        validate_settings(current)
        self._write(current)
        return current

    def _write(self, current):
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


def shared_hysteresis(root):
    """Read the one project-wide band, including before the one-time migration."""
    path = Path(root) / 'config' / 'location_streaming.json'
    if not path.exists():
        return DEFAULT_HYSTERESIS
    data = json.loads(path.read_text(encoding='utf-8'))
    h = data['distances']['hysteresis'] if data.get('schemaVersion') == 1 else data['hysteresis']
    if type(h) is not int or not 0 <= h <= 100:
        raise ValueError('Invalid shared hysteresis')
    return h
