"""M276: explicit, reversible Character atlas identity migration.

Only Character-scoped Atlas Registry rows are in scope. Geometry, Roblox Image
Asset IDs, hashes, publication history and Armor set selections remain intact.
No auto-run on application startup and no Open Cloud operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from sqlite_connection import connect
from services.texture_atlas_registry import digest, parse_filename

# Intentional mapping from the reviewed 2026-11-10 Character catalog.
# A legacy MALE head must not silently become a common/unisex appearance.
# Pinky is a distinct colorway, not a revision of the newborn/t001 texture.
CHARACTER_ATLAS_KEYS_M276 = {
    'head_01_male': 'human_male_m001_t001_head',
    'newborn_boots': 'human_common_m001_t001_boots',
    'newborn_gloves': 'human_common_m001_t001_gloves',
    'newborn_lower': 'human_common_m001_t001_lower',
    'newborn_upper': 'human_common_m001_t001_upper',
    'pinky_upper': 'human_common_m001_t002_upper',
}


@dataclass(frozen=True)
class AtlasMove:
    variant_id: int
    source_family_id: int
    old_key: str
    new_key: str
    target_family_id: int | None
    target_variant_id: int | None
    width: int
    height: int
    old_filename: str
    new_filename: str
    old_source: str
    new_source: str | None
    target_source: str | None
    sha256: str
    image_asset_id: str
    mode: str  # rename or merge


def plan(db: sqlite3.Connection) -> list[AtlasMove]:
    rows = db.execute('''SELECT v.*,f.atlas_key, f.id AS old_family_id, s.scope
        FROM texture_atlas_variants v
        JOIN texture_atlas_families f ON f.id=v.family_id
        LEFT JOIN texture_atlas_scopes s ON s.variant_id=v.id
        WHERE v.retired_at IS NULL ORDER BY v.id''').fetchall()
    by_key: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_key.setdefault(row['atlas_key'], []).append(row)
    result = []
    for old_key, new_key in CHARACTER_ATLAS_KEYS_M276.items():
        for row in by_key.get(old_key, ()):
            if row['scope'] != 'character':
                raise ValueError(f'{old_key} #{row["id"]} is not Character-scoped; no migration performed')
            existing = db.execute('SELECT id FROM texture_atlas_families WHERE atlas_key=?',
                                  (new_key,)).fetchone()
            family_id = int(existing['id']) if existing else None
            conflicting = db.execute('''SELECT * FROM texture_atlas_variants
                WHERE family_id=? AND width=? AND height=?''',
                (family_id, row['width'], row['height'])).fetchone() if family_id else None
            target_id = None
            if conflicting:
                if conflicting['retired_at'] is not None:
                    raise ValueError(f'{new_key} {row["width"]}x{row["height"]}: target was retired')
                if (conflicting['source_sha256'], conflicting['published_id'], conflicting['published_sha256']) != (
                    row['source_sha256'], row['published_id'], row['published_sha256']
                ):
                    raise ValueError(f'{old_key} -> {new_key} {row["width"]}x{row["height"]}: '
                                     'target has different content or published Image Asset ID; review manually')
                if db.execute('SELECT 1 FROM character_appearances WHERE atlas_variant_id=?',
                              (conflicting['id'],)).fetchone() and db.execute(
                                  'SELECT 1 FROM character_appearances WHERE atlas_variant_id=?',
                                  (row['id'],)).fetchone():
                    raise ValueError(f'{old_key} -> {new_key}: both variants have appearances; '
                                     'cannot merge selection identities automatically')
                target_id = int(conflicting['id'])
            for candidate_id in (row['id'], target_id):
                if candidate_id is None:
                    continue
                for table in ('texture_atlas_replacements', 'texture_atlas_pending_uploads'):
                    if db.execute(f'SELECT 1 FROM {table} WHERE variant_id=?',
                                  (candidate_id,)).fetchone():
                        raise ValueError(f'{old_key} #{candidate_id}: pending replacement/upload; finish it first')
            if family_id:
                scoped = db.execute('''SELECT DISTINCT s.scope FROM texture_atlas_scopes s
                    JOIN texture_atlas_variants v ON v.id=s.variant_id
                    WHERE v.family_id=?''', (family_id,)).fetchall()
                if any(x['scope'] != 'character' for x in scoped):
                    raise ValueError(f'{new_key}: target belongs to another section')
                non_character = db.execute('''SELECT 1 FROM texture_atlas_variants v
                    LEFT JOIN texture_atlas_scopes s ON s.variant_id=v.id
                    WHERE v.family_id=? AND s.variant_id IS NULL LIMIT 1''',
                    (family_id,)).fetchone()
                if non_character:
                    raise ValueError(f'{new_key}: target contains unscoped variants; review ownership')
            extension = Path(row['filename']).suffix.lower()
            if extension not in ('.png', '.jpg', '.jpeg'):
                raise ValueError(f'{old_key}: unsupported source extension')
            new_filename = f'{new_key}_{row["width"]}x{row["height"]}_atlas{extension}'
            if parse_filename(new_filename)['atlasKey'] != new_key:
                raise ValueError('invalid target filename: ' + new_filename)
            destination = ('assets/source/texture-atlases/' + new_key + '/' +
                           f'{row["width"]}x{row["height"]}/' + new_filename)
            result.append(AtlasMove(
                variant_id=row['id'], source_family_id=row['old_family_id'],
                old_key=old_key, new_key=new_key, target_family_id=family_id,
                target_variant_id=target_id, width=row['width'], height=row['height'],
                old_filename=row['filename'], new_filename=new_filename,
                old_source=row['source_path'], new_source=None if target_id else destination,
                target_source=conflicting['source_path'] if conflicting else None,
                sha256=row['source_sha256'], image_asset_id=str(row['published_id'] or ''),
                mode='merge' if target_id else 'rename'))
    return result


def _root_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('unsafe atlas source path outside project: ' + relative)
    return path


def _stage_sources(root: Path, entries: list[AtlasMove]) -> None:
    # Preflight every current source before copying anything. Never move/delete
    # legacy source files; old publications and backups may still refer to them.
    for item in entries:
        if item.mode == 'merge':
            # The canonical target is the survivor. Verify its source bytes too;
            # matching database hashes alone do not guarantee a usable source.
            source = _root_path(root, item.target_source)
            if not source.is_file() or digest(source) != item.sha256:
                raise ValueError(f'{item.new_key}: canonical target bytes missing or changed: {source}')
            continue
        source = _root_path(root, item.old_source)
        destination = _root_path(root, item.new_source)
        if not source.is_file() or digest(source) != item.sha256:
            raise ValueError(f'{item.old_key} {item.width}x{item.height}: stored atlas missing or changed: {source}')
        if destination.exists() and (not destination.is_file() or digest(destination) != item.sha256):
            raise ValueError(f'{item.new_key}: canonical file exists with different bytes: {destination}')
    for item in entries:
        if item.mode == 'merge':
            continue
        source = _root_path(root, item.old_source)
        destination = _root_path(root, item.new_source)
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / ('.m276-' + uuid.uuid4().hex + destination.suffix)
        try:
            shutil.copy2(source, temporary)
            if digest(temporary) != item.sha256:
                raise ValueError('atlas bytes changed during M276 copy: ' + item.old_key)
            if destination.exists():
                if digest(destination) != item.sha256:
                    raise ValueError('atlas target changed during M276: ' + item.new_key)
            else:
                temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def _archive_legacy_bindings(db: sqlite3.Connection, now: float) -> int:
    # Old character_part bindings do not belong to Armor v2. Preserve them as
    # read-only history, but do not implicitly attach atlases to new Armor sets.
    rows = db.execute("""SELECT * FROM texture_atlas_bindings
        WHERE consumer_type='character_part' AND consumer_id IN
        ('head_01_male','newborn_boots','newborn_gloves','newborn_lower','newborn_upper','pinky_upper')""").fetchall()
    for row in rows:
        db.execute('''INSERT OR IGNORE INTO character_atlas_legacy_bindings_m276
            (consumer_type,consumer_id,variant_id,revision,changed_at,synced_revision,archived_at)
            VALUES(?,?,?,?,?,?,?)''',
            (row['consumer_type'], row['consumer_id'], row['variant_id'],
             row['revision'], row['changed_at'], row['synced_revision'], now))
        db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type=? AND consumer_id=?',
                   (row['consumer_type'], row['consumer_id']))
    return len(rows)


def migrate(root: Path, *, apply: bool = False) -> dict:
    root = Path(root).resolve()
    db_path = root / '.control-center' / 'game1.db'
    if not db_path.is_file():
        raise ValueError('Atlas Registry database missing: ' + str(db_path))
    with connect(db_path) as db:
        entries = plan(db)
    summary = {
        'changes': [dict(old=e.old_key, new=e.new_key, resolution=f'{e.width}x{e.height}',
                         variantId=e.variant_id, imageAssetId=e.image_asset_id,
                         operation=e.mode, targetVariantId=e.target_variant_id) for e in entries],
        'apply': apply, 'backup': '', 'legacyBindingsArchived': 0,
    }
    if not apply or not entries:
        return summary
    # Explicit offline operation, never an implicit startup migration.
    # A hot Host Agent can race this transaction; the operator stops it first.
    _stage_sources(root, entries)
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / ('before_character_atlas_names_m276_' + uuid.uuid4().hex + '.db')
    with connect(db_path) as src, connect(backup) as dst:
        src.backup(dst)
    summary['backup'] = str(backup)
    with connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        if plan(db) != entries:
            raise ValueError('Atlas Registry changed during migration; no database changes made')
        db.execute("""CREATE TABLE IF NOT EXISTS character_atlas_name_migrations_m276 (
            variant_id INTEGER PRIMARY KEY, old_key TEXT NOT NULL, new_key TEXT NOT NULL,
            old_filename TEXT NOT NULL, new_filename TEXT NOT NULL,
            target_variant_id INTEGER NOT NULL, image_asset_id TEXT NOT NULL,
            mode TEXT NOT NULL, changed_at REAL NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS character_atlas_legacy_bindings_m276 (
            consumer_type TEXT NOT NULL, consumer_id TEXT NOT NULL,
            variant_id INTEGER NOT NULL, revision INTEGER NOT NULL,
            changed_at REAL NOT NULL, synced_revision INTEGER NOT NULL,
            archived_at REAL NOT NULL, PRIMARY KEY(consumer_type,consumer_id))""")
        now = time.time()
        for item in entries:
            if item.target_variant_id:
                target_id = item.target_variant_id
                db.execute('''INSERT OR IGNORE INTO texture_atlas_scopes(variant_id,scope)
                    VALUES(?,'character')''', (target_id,))
                db.execute('''INSERT OR IGNORE INTO texture_atlas_consumer_options
                    (consumer_type,consumer_id,variant_id,added_at)
                    SELECT consumer_type,consumer_id,?,added_at FROM texture_atlas_consumer_options
                    WHERE variant_id=?''', (target_id, item.variant_id))
                db.execute('DELETE FROM texture_atlas_consumer_options WHERE variant_id=?', (item.variant_id,))
                db.execute('UPDATE texture_atlas_bindings SET variant_id=? WHERE variant_id=?',
                           (target_id, item.variant_id))
                db.execute('UPDATE character_appearances SET atlas_variant_id=? WHERE atlas_variant_id=?',
                           (target_id, item.variant_id))
                db.execute('UPDATE texture_atlas_variants SET retired_at=? WHERE id=?',
                           (now, item.variant_id))
            else:
                if item.target_family_id:
                    target_family = item.target_family_id
                else:
                    db.execute('''INSERT OR IGNORE INTO texture_atlas_families(atlas_key,created_at)
                        VALUES(?,?)''', (item.new_key, now))
                    target_family = db.execute('SELECT id FROM texture_atlas_families WHERE atlas_key=?',
                                               (item.new_key,)).fetchone()['id']
                db.execute('''UPDATE texture_atlas_variants
                    SET family_id=?, filename=?, source_path=? WHERE id=?''',
                    (target_family, item.new_filename, item.new_source, item.variant_id))
                target_id = item.variant_id
            db.execute('''INSERT INTO character_atlas_name_migrations_m276
                (variant_id,old_key,new_key,old_filename,new_filename,target_variant_id,
                 image_asset_id,mode,changed_at) VALUES(?,?,?,?,?,?,?,?,?)''',
                (item.variant_id, item.old_key, item.new_key, item.old_filename,
                 item.new_filename, target_id, item.image_asset_id, item.mode, now))
        # Clean up no-longer-referenced old family identities. Keep any retired
        # historical rows in their original family for audit and traceability.
        for old_family_id in {i.source_family_id for i in entries}:
            db.execute('''DELETE FROM texture_atlas_families WHERE id=? AND NOT EXISTS
                (SELECT 1 FROM texture_atlas_variants WHERE family_id=?)''',
                (old_family_id, old_family_id))
        summary['legacyBindingsArchived'] = _archive_legacy_bindings(db, now)
        # Transaction commits upon successful exit; nothing else in the app
        # has to be recomputed, and Roblox assets are not touched.
    return summary
