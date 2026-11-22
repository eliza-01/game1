"""House MeshPart streaming distances. Only LOD Manager writes these records.

Legacy authoring distances are read once during an idempotent migration. Afterward
this is the single source of truth; Real Estate stores appearance/physics only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlite_connection import connect as connect_sqlite
from real_estate.contracts import HOUSE_NAME, present_parts
from real_estate.rig_publication_policy import publication_analysis
from .location_streaming_config import DEFAULT_HYSTERESIS, shared_hysteresis

DEFAULT_LOD1 = 150
DEFAULT_HIDE = 400
HYSTERESIS = DEFAULT_HYSTERESIS  # Baseline minimum spacing for existing authored parts.
MIN_LOD1 = 20
MIN_GAP = 2 * HYSTERESIS + 1
MAX_HIDE = 10000


def validate(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {'lod1', 'hide'}:
        raise ValueError('expected per-part lod1 / hide distances')
    a, b = value['lod1'], value['hide']
    if type(a) is not int or type(b) is not int or not (MIN_LOD1 <= a < b <= MAX_HIDE):
        raise ValueError('part LOD1 / Unloaded must be integers: 20 <= LOD1 < Unloaded <= 10000')
    if a <= HYSTERESIS or b - a < MIN_GAP:
        raise ValueError('part distances must leave room for shared hysteresis')
    return {'lod1': a, 'hide': b}


def normalize_edit(value: dict, hysteresis=HYSTERESIS) -> dict:
    """UNLOADED is authoritative; project the edit onto valid runtime thresholds."""
    if not isinstance(value, dict) or set(value) != {'lod1', 'hide'}:
        raise ValueError('expected per-part lod1 / hide distances')
    a, b = value['lod1'], value['hide']
    if type(a) is not int or type(b) is not int or a < MIN_LOD1 or not 1 <= b <= MAX_HIDE:
        raise ValueError('part distances must be positive integers: LOD1 >= 20; Unloaded <= 10000')
    minimum, gap = max(MIN_LOD1, hysteresis + 1), max(MIN_GAP, 2 * hysteresis + 1)
    b = max(b, minimum + gap)
    return validate({'lod1': max(minimum, min(a, b - gap)), 'hide': b})


def ensure_schema(store):
    with store.connect() as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='real_estate_part_distances'").fetchone()
        if not exists:
            backup_dir = store.root / '.control-center' / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / ('real_estate_part_distances_pre_m414_' +
                datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
            with connect_sqlite(backup_path) as backup:
                db.backup(backup)
        db.execute("""CREATE TABLE IF NOT EXISTS real_estate_part_distances (
            house_slug TEXT NOT NULL, part_name TEXT NOT NULL,
            lod1 INTEGER NOT NULL, hide INTEGER NOT NULL, revision INTEGER NOT NULL,
            PRIMARY KEY(house_slug, part_name))""")
        # Existing rows are immutable migration outputs; no migration reruns on
        # already configured parts and no publication IDs are modified.
        for row in db.execute('SELECT slug,skeleton_json,mesh_options_json FROM real_estate'):
            slug = row['slug']
            parts = present_parts(publication_analysis(json.loads(row['skeleton_json'])))
            legacy = json.loads(row['mesh_options_json'] or '{}')
            profile = db.execute('SELECT lod1,hide FROM real_estate_streaming_profiles WHERE house_slug=?', (slug,)).fetchone()
            base_lod = int(profile['lod1']) if profile else DEFAULT_LOD1
            base_hide = int(profile['hide']) if profile else DEFAULT_HIDE
            for part in parts:
                opts = legacy.get(part) or {}
                distance = opts.get('loadDistanceStuds', 50)
                if opts.get('distanceStreaming', part == 'window_frames_glass') is True and type(distance) in (int,float) and 20 <= distance <= 1000:
                    lod1 = int(distance)
                else:
                    lod1 = base_lod
                hide = max(base_hide, lod1 + MIN_GAP)
                if hide > 10000:
                    raise ValueError(f'{slug}/{part}: historical distance cannot be migrated safely')
                db.execute("""INSERT OR IGNORE INTO real_estate_part_distances
                    (house_slug,part_name,lod1,hide,revision) VALUES (?,?,?,?,1)""",
                    (slug,part,lod1,hide))
            # One-way cleanup: after distances are copied to the authoritative
            # table, retire the old authoring fields from each part's JSON.
            # The SQLite backup above preserves the original bytes for rollback.
            if any('distanceStreaming' in entry or 'loadDistanceStuds' in entry
                   for entry in legacy.values() if isinstance(entry,dict)):
                for entry in legacy.values():
                    if isinstance(entry,dict):
                        entry.pop('distanceStreaming',None)
                        entry.pop('loadDistanceStuds',None)
                db.execute('UPDATE real_estate SET mesh_options_json=? WHERE slug=?',
                           (json.dumps(legacy,ensure_ascii=False),slug))


def describe_all(store, slug, parts):
    with store.connect() as db:
        rows = {row['part_name']: dict(row) for row in db.execute(
            'SELECT part_name,lod1,hide,revision FROM real_estate_part_distances WHERE house_slug=?', (slug,))}
    # Newly added visual meshes get a neutral default; unlike legacy values
    # these settings never come from the Real Estate appearance editor.
    h = shared_hysteresis(store.root)
    result = {}
    for part in parts:
        row = rows.get(part) or {'part_name':part, 'lod1':DEFAULT_LOD1, 'hide':DEFAULT_HIDE, 'revision':0}
        result[part] = {**row, **normalize_edit({'lod1':row['lod1'], 'hide':row['hide']}, h)}
    return result


def save(store, slug, part, value, expected_revision):
    if not isinstance(slug,str) or not HOUSE_NAME.fullmatch(slug):
        raise ValueError('invalid house type')
    house=store.get(slug)
    if not house or part not in house['meshParts']:
        raise ValueError('unknown visual MeshPart')
    value=normalize_edit(value, shared_hysteresis(store.root))
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('part distances revision required')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT revision FROM real_estate_part_distances WHERE house_slug=? AND part_name=?',
                       (slug,part)).fetchone()
        if (row['revision'] if row else 0) != expected_revision:
            raise ValueError('part LOD distances changed; refresh')
        db.execute("""INSERT INTO real_estate_part_distances
            (house_slug,part_name,lod1,hide,revision) VALUES (?,?,?,?,?)
            ON CONFLICT(house_slug,part_name) DO UPDATE SET
            lod1=excluded.lod1,hide=excluded.hide,revision=excluded.revision""",
            (slug,part,value['lod1'],value['hide'],expected_revision+1))
    store.export()
    return store.get(slug)['partStreaming'][part]
