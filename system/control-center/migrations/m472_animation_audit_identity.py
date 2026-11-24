"""Restore immutable Character Animation audit identity after M470 renaming.

M470 changed animation_publications.clip_id from __00 to __01. MySQL already
owns those publication operation IDs under their original asset keys. Never
rewrite or delete audit history: preserve the original keys in a SQLite-owned,
append-only provenance table, then let the read-only importer project them.

The first recovery requires M470's verified pre-migration SQLite backup.
All subsequent publications are recorded automatically by a SQLite trigger.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from sqlite_connection import connect


def _rows(path: Path) -> dict[int, dict]:
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='animation_publications'").fetchone():
            raise ValueError('animation_publications table is missing: ' + str(path))
        return {int(row['id']): dict(row) for row in db.execute(
            'SELECT id,clip_id,asset_id,operation_path FROM animation_publications')}


def migrate(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    dbfile = root / '.control-center/game1.db'
    if not dbfile.is_file():
        raise ValueError('character database is missing: ' + str(dbfile))
    current = _rows(dbfile)
    with connect(dbfile) as db:
        table_present = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='animation_publication_audit_keys'").fetchone() is not None
        recorded = ({int(row['publication_id']): dict(row)
                     for row in db.execute('SELECT * FROM animation_publication_audit_keys')}
                    if table_present else {})
    for identifier, history in recorded.items():
        publication = current.get(identifier)
        if publication is None or (str(history['asset_id']), str(history['operation_path'])) != (
                str(publication['asset_id']), str(publication['operation_path'])):
            raise ValueError('audit provenance conflict: publication ' + str(identifier))
    missing = {identifier for identifier in current if identifier not in recorded}
    original = {}
    # M470's retained snapshot is the only authoritative source of identity
    # before its in-place clip_id migration. Select the oldest valid snapshot.
    archives = sorted((root / '.control-center/backups').glob('m470_animation_versions_*.db'))
    for archive in archives:
        try:
            previous = _rows(archive)
        except (ValueError, sqlite3.DatabaseError):
            continue
        if not previous or not set(previous).issubset(current):
            continue
        for identifier, row in previous.items():
            newer = current[identifier]
            if (str(row['asset_id']), str(row['operation_path'])) != (
                    str(newer['asset_id']), str(newer['operation_path'])):
                raise ValueError('m470 backup identity differs from live publication ' + str(identifier))
        original = previous
        break
    # Without provenance, existing published rows may have a new key already
    # imported under the old identity. Refuse to invent keys in that case.
    if missing and not recorded and not original:
        raise ValueError('m470 pre-migration backup missing; cannot safely recover immutable animation audit keys')
    for identifier in missing:
        if identifier in original:
            old = original[identifier]
            if (str(old['asset_id']), str(old['operation_path'])) != (
                    str(current[identifier]['asset_id']), str(current[identifier]['operation_path'])):
                raise ValueError('m470 backup changed publication identity ' + str(identifier))
    if not missing and table_present:
        print('m472: animation audit keys already canonical; no changes')
        return {'added': 0, 'total': len(recorded)}

    # Back up before the first SQLite modification. No MySQL table is changed.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = root / '.control-center/backups' / ('m472_before_audit_identity_' + stamp + '.db')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with connect(dbfile) as source, connect(backup) as destination:
        source.backup(destination)
    with connect(dbfile) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS animation_publication_audit_keys (
            publication_id INTEGER PRIMARY KEY, asset_key TEXT NOT NULL,
            asset_id TEXT NOT NULL, operation_path TEXT NOT NULL)''')
        for identifier in sorted(missing):
            current_row = current[identifier]
            original_key = str(original.get(identifier, current_row)['clip_id'])
            db.execute('''INSERT INTO animation_publication_audit_keys
                (publication_id,asset_key,asset_id,operation_path) VALUES(?,?,?,?)''',
                (identifier, original_key, str(current_row['asset_id']), str(current_row['operation_path'])))
        db.execute('''CREATE TRIGGER IF NOT EXISTS animation_publication_audit_key_on_insert
            AFTER INSERT ON animation_publications
            BEGIN
                INSERT INTO animation_publication_audit_keys
                    (publication_id,asset_key,asset_id,operation_path)
                VALUES (NEW.id, NEW.clip_id, NEW.asset_id, NEW.operation_path);
            END''')
    print('m472: preserved', len(missing), 'publication audit identities; sqlite backup:', backup)
    return {'added': len(missing), 'total': len(current)}


if __name__ == '__main__':
    migrate()
