"""M277: explicit removal of retired Character v1 active records.

Read-only unless --apply. The published Roblox assets and historical audit tables
are untouched. A complete SQLite backup is created before the transaction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time
import uuid

from sqlite_connection import connect

LEGACY_PARTS = frozenset({
    'eyebrows_01', 'eyes_01', 'eyes_01_spiral',
    'hair_01_common', 'hair_02_common', 'hair_03_common', 'head_01_male',
    'newborn_boots', 'newborn_gloves', 'newborn_lower', 'newborn_upper',
})
LEGACY_CHARACTER_IDS = frozenset({'human_female', 'human_male'})


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _animation_rows(db: sqlite3.Connection, character_ids: list[str]) -> dict[str, list[dict]]:
    """Extract only animation records owned by the retiring character identities."""
    tables = ('animation_profiles', 'animation_clips', 'animation_bindings', 'animation_clip_documents')
    result = {table: [] for table in tables}
    if not character_ids or not all(_table_exists(db, t) for t in tables[:3]):
        return result
    markers = ','.join('?' for _ in character_ids)
    for table in tables[:3]:
        result[table] = [dict(row) for row in db.execute(
            f'SELECT * FROM {table} WHERE character_id IN ({markers})', character_ids)]
    clip_ids = [row['id'] for row in result['animation_clips']]
    clip_keys = set(clip_ids)
    for row in result['animation_bindings']:
        if row['clip_id'] not in clip_keys:
            raise ValueError('retired animation binding refers to a clip owned by another profile: ' + str(row['clip_id']))
    if clip_ids and _table_exists(db, 'animation_clip_documents'):
        docs_markers = ','.join('?' for _ in clip_ids)
        result['animation_clip_documents'] = [dict(row) for row in db.execute(
            f'SELECT * FROM animation_clip_documents WHERE clip_id IN ({docs_markers})', clip_ids)]
    return result


def plan(db: sqlite3.Connection) -> dict:
    db.row_factory = sqlite3.Row
    rows = [dict(row) for row in db.execute('SELECT * FROM character_component_records')]
    candidates = [r for r in rows if r['kind'] == 'part' and r['id'] in LEGACY_PARTS]
    for row in candidates:
        if row['rig_id'] != 'human' or row['mesh_family_id']:
            raise ValueError(row['id'] + ': a legacy ID is now an active v2 resource; stop and review')
    unknown_old = [r['id'] for r in rows if r['kind'] == 'part' and not r['mesh_family_id'] and r['id'] not in LEGACY_PARTS]
    if unknown_old:
        raise ValueError('unreviewed legacy part(s): ' + ', '.join(sorted(unknown_old)))
    parts = sorted(r['id'] for r in candidates)
    rigs = [r for r in rows if r['kind'] == 'rig' and r['id'] == 'human']
    if rigs and any(r['rig_id'] == 'human' and r['id'] not in parts and r['kind'] == 'part' for r in rows):
        raise ValueError('cannot retire human rig: active parts still reference it')
    # Only reviewed historical character IDs may be deleted; keep all v2 recipes.
    characters = []
    for row in db.execute('SELECT id,visual_mode,assembly_json FROM characters'):
        if row['visual_mode'] == 'assembly':
            try: version = json.loads(row['assembly_json']).get('schema_version')
            except (TypeError, ValueError): version = None
            if version == 2:
                continue
        if row['id'] not in LEGACY_CHARACTER_IDS:
            raise ValueError('unreviewed old character: ' + row['id'])
        characters.append(row['id'])
    characters.sort()
    armor_uses = [r['mesh_part_id'] for r in db.execute('SELECT mesh_part_id FROM armor_piece_variants')
                  if r['mesh_part_id'] in parts]
    if armor_uses:
        raise ValueError('Armor v2 references retired geometry: ' + ', '.join(sorted(set(armor_uses))))
    for row in db.execute("SELECT key,value FROM project_settings WHERE key IN ('default_character_assembly_id','studio_admin_assembly_id')"):
        if row['value'] in characters:
            raise ValueError(row['key'] + ' selects a retired character; reselect the v2 recipe first')
    sets = [r['id'] for r in db.execute('SELECT id FROM character_component_sets')
            if r['id'] == 'newborn']
    animations = _animation_rows(db, characters)
    return dict(parts=parts, rigs=[r['id'] for r in rigs], characters=characters, component_sets=sets,
                retired_animation_counts={table: len(rows) for table, rows in animations.items()},
                historical_publications_retained=True, published_roblox_assets_unchanged=True)


def migrate(root: Path, apply: bool = False) -> dict:
    root = root.resolve()
    source = root / '.control-center' / 'game1.db'
    if not source.is_file():
        raise ValueError('database is missing: ' + str(source))
    with connect(source) as db:
        db.row_factory = sqlite3.Row
        summary = plan(db)
        if not apply or not any(summary[k] for k in ('parts','rigs','characters','component_sets')):
            return dict(**summary, applied=False, backup=None)
        backup = source.parent / 'backups' / ('before_character_catalog_m277_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8] + '.db')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with connect(backup) as archived:
            db.backup(archived)
        db.execute('BEGIN IMMEDIATE')
        if plan(db) != summary:
            raise ValueError('Character Catalog changed; retry with a new preview')
        # Retire the old animation *profiles*, not just the character records.
        # Their bind skeletons are unrelated to the newly registered rig, and
        # reusing human_female without retiring clips would silently play
        # animations authored for a different skeleton.
        animation_records = _animation_rows(db, summary['characters'])
        if any(animation_records.values()):
            db.execute('''CREATE TABLE IF NOT EXISTS character_retired_animation_records_m277 (
                source_table TEXT NOT NULL, source_id TEXT NOT NULL,
                record_json TEXT NOT NULL, retired_at REAL NOT NULL,
                PRIMARY KEY(source_table,source_id))''')
            for table in ('animation_clip_documents','animation_bindings','animation_clips','animation_profiles'):
                for record in animation_records[table]:
                    row_id = str(record.get('id') or record.get('character_id') or
                                 (str(record.get('clip_id')) + ':' + str(record.get('animation_sha256'))))
                    db.execute('INSERT OR IGNORE INTO character_retired_animation_records_m277 VALUES(?,?,?,?)',
                               (table, row_id, json.dumps(record, ensure_ascii=False), time.time()))
                    if table == 'animation_clip_documents':
                        db.execute('DELETE FROM animation_clip_documents WHERE clip_id=? AND animation_sha256=?',
                                   (record['clip_id'], record['animation_sha256']))
                    elif table == 'animation_profiles':
                        db.execute('DELETE FROM animation_profiles WHERE character_id=?', (record['character_id'],))
                    else:
                        db.execute(f'DELETE FROM {table} WHERE id=?', (record['id'],))
        # Remove only active catalog rows. The original published IDs remain in
        # component history/publication audit and in the full SQLite backup.
        for item in summary['parts']:
            db.execute("DELETE FROM character_component_records WHERE kind='part' AND id=?", (item,))
        for item in summary['rigs']:
            db.execute("DELETE FROM character_component_records WHERE kind='rig' AND id=?", (item,))
        for item in summary['component_sets']:
            db.execute('DELETE FROM character_component_sets WHERE id=?', (item,))
        for item in summary['characters']:
            db.execute('DELETE FROM character_stats WHERE character_id=?', (item,))
            db.execute('DELETE FROM character_assembly_history WHERE character_id=?', (item,))
            db.execute('DELETE FROM character_model_assignments WHERE target_character_id=? OR source_character_id=?', (item, item))
            db.execute('DELETE FROM characters WHERE id=?', (item,))
        db.execute("DELETE FROM project_settings WHERE key='active_character_archetype_id'")
        db.commit()
        return dict(**summary, applied=True, backup=str(backup))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='mutate database after backup (default is preview)')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        print(json.dumps(migrate(args.root, args.apply), ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, 'M277 Character cleanup blocked: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
