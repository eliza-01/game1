"""Validated, atomic authoring for shared heat-source tuning.

One JSON source generates an immutable shared Luau value module. Control Center
never evaluates user-provided Luau or writes arbitrary project paths.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'config/mechanics/fireplace.json'
OUTPUT = ROOT / 'src/shared/world/FireplaceMechanicsTuning.luau'
FIELD_LIMITS = {
    'FuelDurationSeconds': (5, 7200),
    'EmbersDurationSeconds': (5, 7200),
    'CampfireDurationSeconds': (5, 7200),
    'CookingSecondsOnFire': (1, 3600),
    'CookingSecondsOnEmbers': (1, 3600),
    'ProgressVisibleRadius': (8, 200),
    'CampfireInteractionRadius': (2, 20),
    'CampfireAimRadius': (1, 10),
}
LOCK = RLock()


def validate(data: dict) -> dict[str, int]:
    if not isinstance(data, dict) or set(data) != set(FIELD_LIMITS):
        raise ValueError('complete Fireplace settings object required')
    result = {}
    for field, (minimum, maximum) in FIELD_LIMITS.items():
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{field} must be a number')
        if not math.isfinite(value) or int(value) != value or not minimum <= value <= maximum:
            raise ValueError(f'{field} must be an integer between {minimum} and {maximum}')
        result[field] = int(value)
    if result['CampfireAimRadius'] > result['CampfireInteractionRadius']:
        raise ValueError('CampfireAimRadius cannot exceed interaction radius')
    return result


def render_luau(settings: dict[str, int]) -> str:
    return ('-- Generated from config/mechanics/fireplace.json. Change in Mechanics UI.\n'
            '-- Keep this a pure, immutable value contract for server/client consumers.\n'
            'return table.freeze({\n'
            + ''.join(f'    {key} = {value},\n' for key, value in settings.items())
            + '})\n')


def load() -> dict[str, int]:
    with LOCK:
        data = json.loads(SOURCE.read_text(encoding='utf-8'))
        return validate(data)


def _atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', encoding='utf-8', newline='\n',
                            prefix='.fireplace_', suffix='.tmp', dir=path.parent,
                            delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def save(values: dict, expected: dict) -> dict[str, int]:
    with LOCK:
        previous = load()
        if previous != validate(expected):
            raise ValueError('Fireplace settings were changed elsewhere; refresh before saving')
        settings = validate(values)
        old_luau = OUTPUT.read_text(encoding='utf-8') if OUTPUT.exists() else None
        old_json = SOURCE.read_text(encoding='utf-8')
        try:
            _atomic(SOURCE, json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
            _atomic(OUTPUT, render_luau(settings))
        except BaseException:
            # Do not leave divergent source/runtime tuning on an IO failure.
            _atomic(SOURCE, old_json)
            if old_luau is not None:
                _atomic(OUTPUT, old_luau)
            raise
        return settings
