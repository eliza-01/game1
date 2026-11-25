"""M482: idempotently extend Character Creation visual options.

Keeps authored scenes, camera points, material overrides and unrelated options.
Backup of the original manifest is created before first upgrade; the existing
OptionsStore writer is the only generator of GameOptionsRegistry.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore
from services.character_creation_settings import DEFAULTS


def migrate(root: Path = ROOT):
    root = Path(root)
    manifest = root / 'assets/manifests/options.json'
    payload = json.loads(manifest.read_text(encoding='utf-8'))
    creation = payload.get('characterCreation') or {}
    upgrade = any(name not in creation for name in ('colorPresets', 'materialChoices'))
    if upgrade:
        backup = manifest.with_name('options.json.pre-m482-'
            + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.bak')
        backup.write_bytes(manifest.read_bytes())
        print('m482: options backup: ' + str(backup))
    store = OptionsStore(root)
    result = store.snapshot()['characterCreation']
    for field in ('colorPresets', 'materialChoices'):
        assert field in result and result[field], 'missing creation option ' + field
    registry = (root / 'src/shared/GameOptionsRegistry.luau').read_text(encoding='utf-8')
    assert 'colorPresets = table.freeze({' in registry
    assert 'materialChoices = table.freeze({' in registry
    print('m482: character creation visual options ready; pre-existing values retained')
    return result

if __name__ == '__main__':
    migrate()
