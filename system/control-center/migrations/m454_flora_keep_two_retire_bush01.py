"""M454: retire reviewed Flora registrations; preserve shared atlas identities.

Explicit operator action, never run on application startup. Only registered
Location Assets are removed; original FBX, atlas files, cloud publications and
Workspace placements are not deleted. Full SQLite and registry backups precede
any mutation. Re-running after success is a no-op.
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

KEEP_TREES = frozenset({'christmas_tree_01', 'thuja_02'})
RETIRE_TREES = frozenset({'big_tree_01', 'birch_01', 'birch_02', 'blossom_tree_01'})
RETIRE_BUSHES = frozenset({'bush_01'})


def snapshot_db(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(target)) as backup:
        origin.backup(backup)


def migrate(root: Path = ROOT) -> dict:
    root = root.resolve()
    db = root / '.control-center/game1.db'
    if not db.is_file():
        raise ValueError(f'authoring SQLite missing: {db}')
    with closing(sqlite3.connect(db)) as connection:
        rows = connection.execute("SELECT slug,category FROM location_assets WHERE category IN ('tree','bush')").fetchall()
    by_category = {
        category: {slug for slug, found_category in rows if found_category == category}
        for category in ('tree', 'bush')
    }
    trees = by_category['tree']
    if not KEEP_TREES.issubset(trees):
        raise ValueError(f'retained trees missing: {sorted(KEEP_TREES - trees)}')
    if trees - KEEP_TREES - RETIRE_TREES:
        raise ValueError(f'unreviewed trees, refusing deletion: {sorted(trees - KEEP_TREES - RETIRE_TREES)}')
    # bush_02 and any other bushes are outside this migration's scope.
    retire = sorted((trees & RETIRE_TREES) | (by_category['bush'] & RETIRE_BUSHES))
    if not retire:
        return {'ok': True, 'alreadyMigrated': True, 'retainedTrees': sorted(KEEP_TREES),
                'remainingBushes': sorted(by_category['bush'])}

    backup_dir = root / '.control-center/backups' / (
        'm454_flora_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup_dir.mkdir(parents=True, exist_ok=False)
    snapshot_db(db, backup_dir / 'game1.db')
    for relative in ('assets/manifests/location-assets.json',
                     'src/shared/world/LocationAssetRegistry.luau'):
        source = root / relative
        if source.is_file():
            dest = backup_dir / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)

    from location_asset_store import LocationAssetStore
    store = LocationAssetStore(root)
    removed = []
    for slug in retire:
        record = store.delete(slug)
        removed.append({'slug': slug, 'archive': record.get('archived')})
    with store.connect() as connection:
        for slug in retire:
            connection.execute('DELETE FROM location_asset_slug_aliases WHERE old_slug=? OR current_slug=?',
                               (slug, slug))
    store.export()
    with store.connect() as connection:
        actual = connection.execute("SELECT slug,category FROM location_assets WHERE category IN ('tree','bush')").fetchall()
    remaining_trees = {slug for slug, category in actual if category == 'tree'}
    remaining_bushes = {slug for slug, category in actual if category == 'bush'}
    if remaining_trees != KEEP_TREES or 'bush_01' in remaining_bushes:
        raise RuntimeError('M454 flora postcondition failed; restore from SQLite backup')
    result = {'ok': True, 'retired': removed, 'retainedTrees': sorted(remaining_trees),
              'remainingBushes': sorted(remaining_bushes),
              'backup': backup_dir.relative_to(root).as_posix(),
              'cloudAssetsDeleted': False, 'workspaceChanged': False,
              'sourceFilesDeleted': False, 'sharedAtlasVariantsPreserved': True}
    (backup_dir / 'migration-report.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(migrate(), ensure_ascii=False, indent=2))
