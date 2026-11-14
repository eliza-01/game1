"""M342: destructive, idempotent authoring migration (no COL mesh fallback).

Must run from game1 root with Control Center stopped. The backup precedes every
SQLite/manifest write. Does not touch FBX, published Roblox Asset IDs or Plots.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path



@contextmanager
def sqlite_connection(path: Path):
    """Commit/rollback the transaction AND close the handle on every platform.

    sqlite3.Connection.__exit__ only ends the transaction; it does not close.
    Windows prevents removal of the temporary database until close() runs.
    """
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            yield connection


def import_app(root: Path) -> None:
    sys.path.insert(0, str(root / 'system' / 'control-center'))


def dumped(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def migrate(root: Path, *, dry_run: bool = False) -> dict:
    import_app(root)
    from services.retired_col_mesh import retired, strip_mesh_rows, strip_options
    from services.mesh_authoring_policy import location_mesh_profile

    real_db = root / '.control-center' / 'game1_real_estate.db'
    location_db = root / '.control-center' / 'game1.db'
    if not real_db.is_file() or not location_db.is_file():
        raise FileNotFoundError('Expected Real Estate and Location Asset SQLite databases')
    when = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = root / '.control-center' / 'backups' / ('m342_col_retirement_' + when)
    result = {'mode': 'dry-run' if dry_run else 'apply', 'houses': [], 'locations': [],
              'fbxReports': [], 'retiredPublications': 0, 'backup': str(backup)}

    def preview_real(c: sqlite3.Connection):
        c.row_factory = sqlite3.Row
        for row in c.execute('SELECT slug,skeleton_json,textures_json,model_rigs_json,mesh_options_json,mesh_sources_json FROM real_estate'):
            data = dict(row)
            analysis = json.loads(data['skeleton_json'])
            removed = [part.get('name') for part in analysis.get('meshes', []) if retired(part.get('name'))]
            updates = {'skeleton_json': dumped(strip_mesh_rows(analysis))}
            for key in ('textures_json', 'model_rigs_json', 'mesh_options_json', 'mesh_sources_json'):
                updates[key] = dumped(strip_options(json.loads(data[key] or '{}')))
            if removed or any(updates[k] != dumped(json.loads(data[k] or '{}')) for k in updates):
                result['houses'].append({'slug': data['slug'], 'removed': removed})
            if not dry_run:
                c.execute('''UPDATE real_estate SET skeleton_json=:skeleton_json,textures_json=:textures_json,
                    model_rigs_json=:model_rigs_json,mesh_options_json=:mesh_options_json,
                    mesh_sources_json=:mesh_sources_json WHERE slug=:slug''', {**updates,'slug':data['slug']})
        publications = c.execute('SELECT id, part FROM real_estate_publications').fetchall()
        removed_ids = [r['id'] for r in publications
                       if retired(str(r['part']).split(':', 1)[-1])]
        result['retiredPublications'] = len(removed_ids)
        if not dry_run:
            c.executemany('DELETE FROM real_estate_publications WHERE id=?',
                          [(identifier,) for identifier in removed_ids])

    def preview_location(c: sqlite3.Connection):
        c.row_factory = sqlite3.Row
        for row in c.execute('SELECT slug,mesh_options_json FROM location_assets'):
            options = json.loads(row['mesh_options_json'] or '{}')
            trimmed = strip_options(options)
            if options != trimmed:
                result['locations'].append({'slug': row['slug'], 'removed': sorted(set(options) - set(trimmed))})
            if not dry_run:
                c.execute('UPDATE location_assets SET mesh_options_json=? WHERE slug=?',
                          (dumped(trimmed), row['slug']))

    # Capture the set of analyses that must be edited without erasing the
    # registered FBX sourceSha256. Preserve authored geometry provenance.
    report_dir = root / 'assets' / 'manifests' / 'location-assets-fbx'
    updates = []
    for path in sorted(report_dir.glob('*.json')) if report_dir.exists() else []:
        doc = json.loads(path.read_text(encoding='utf-8'))
        analysis = doc.get('analysis')
        if not isinstance(analysis, dict) or not isinstance(analysis.get('meshes'), list):
            continue
        dropped = [m.get('name') for m in analysis['meshes'] if retired(m.get('name'))]
        new = strip_mesh_rows(analysis)
        new['hasCollider'] = False
        for mesh in new['meshes']:
            if mesh.get('name') == 'rig_carrier':
                profile = location_mesh_profile('rig_carrier', has_collider=False)
            else:
                profile = location_mesh_profile(mesh['name'], has_collider=False)
            mesh['role'], mesh['physics'] = profile['role'], profile
        if new != analysis:
            updates.append((path, {**doc, 'analysis': new}))
            result['fbxReports'].append({'file': path.name, 'removed': dropped})

    if dry_run:
        with sqlite_connection(real_db) as c: preview_real(c)
        with sqlite_connection(location_db) as c: preview_location(c)
        return result

    backup.mkdir(parents=True, exist_ok=False)
    for source in (real_db, location_db):
        with sqlite_connection(source) as original, sqlite_connection(backup / source.name) as target:
            original.backup(target)
    for source in (root / 'assets/manifests/real-estate.json',
                   root / 'assets/manifests/location-assets.json',
                   root / 'src/shared/world/LocationAssetRegistry.luau'):
        if source.is_file():
            target = backup / source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for file, _ in updates:
        target = backup / file.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    try:
        with sqlite_connection(real_db) as c:
            preview_real(c)
        with sqlite_connection(location_db) as c:
            preview_location(c)
        for file, data in updates:
            file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',encoding='utf-8')
        from real_estate.store import RealEstateStore
        from location_asset_store import LocationAssetStore
        locations = LocationAssetStore(root)
        estates = RealEstateStore(root, location_assets=locations)
        estates.export()
        locations.export()
    except Exception:
        # Abort with the backed-up data intact. Never fake a successful migration.
        raise
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    report=migrate(args.root.resolve(),dry_run=args.dry_run)
    message=json.dumps(report,ensure_ascii=False,indent=2)
    print(message)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(message+'\n',encoding='utf8')
