"""One-shot M452 Location building retirement, with full SQLite recovery.

Run from project root after applying the patch:
  python system/control-center/migrations/m452_buildings_keep_two.py

Does NOT delete source FBXs, cloud assets, places, or other asset categories.
Never runs automatically during Control Center startup.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'system/control-center'))

KEEP = frozenset({'smithy_01', 'windmill_02'})
RETIRE = ('weapon_shop', 'windmill_01', 'smithy')
EXPECTED = KEEP | set(RETIRE)


def snapshot_db(db: Path, backup: Path) -> None:
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)


def migrate(root: Path = ROOT) -> dict:
    root = root.resolve()
    db = root / '.control-center/game1.db'
    if not db.is_file():
        raise ValueError(f'authoring database does not exist: {db}')
    with closing(sqlite3.connect(db)) as connection:
        rows = connection.execute('SELECT slug,category FROM location_assets WHERE category=?', ('building',)).fetchall()
    buildings = {slug for slug, _ in rows}
    if not KEEP.issubset(buildings):
        raise ValueError(f'expected retained buildings missing: {sorted(KEEP - buildings)}')
    if buildings - EXPECTED:
        raise ValueError(f'unreviewed building(s); refusing broad deletion: {sorted(buildings - EXPECTED)}')
    if buildings == KEEP:
        return {'ok': True, 'alreadyMigrated': True, 'remaining': sorted(KEEP)}

    directory = root / '.control-center/backups' / (
        'm452_buildings_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    directory.mkdir(parents=True, exist_ok=False)
    snapshot_db(db, directory / 'game1.db')
    for relative in ('assets/manifests/location-assets.json',
                     'src/shared/world/LocationAssetRegistry.luau'):
        path = root / relative
        if path.is_file():
            saved = directory / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)

    from location_asset_store import LocationAssetStore
    store = LocationAssetStore(root)
    removed = []
    for slug in RETIRE:
        if slug in buildings:
            result = store.delete(slug)
            removed.append({'slug': slug, 'archive': result.get('archived')})
    # Old aliases must not resolve deleted registrations back into Runtime.
    with store.connect() as connection:
        for slug in RETIRE:
            connection.execute('DELETE FROM location_asset_slug_aliases WHERE old_slug=? OR current_slug=?',
                               (slug, slug))
    store.export()
    with store.connect() as connection:
        actual = {row[0] for row in connection.execute(
            'SELECT slug FROM location_assets WHERE category=?', ('building',))}
    if actual != KEEP:
        raise RuntimeError(f'M452 postcondition failed: {sorted(actual)}')
    report = {'ok': True, 'remaining': sorted(actual), 'retired': removed,
              'backup': directory.relative_to(root).as_posix(),
              'cloudAssetsDeleted': False, 'workspaceChanged': False,
              'sourceFilesDeleted': False}
    (directory / 'migration-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                                     encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(migrate(), ensure_ascii=False, indent=2))
