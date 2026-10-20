"""Read-only authoring SQLite audit with optional online, consistent backups.

Does not open any project database for writes or perform migrations.
Use --backup-dir to write complete SQLite backups into a separate directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASES = (
    'game1.db',
    'game1_real_estate.db',
    'game1_npcs.db',
    'newplace.db',
)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def audit_database(path: Path, *, backup_dir: Path | None = None,
                   require_m115: bool = False) -> tuple[int, str]:
    """Audit using a read-only connection; optionally back up via SQLite API."""
    if not path.is_file():
        print(f'{path.name}: missing (skipped)')
        return 0, ''
    # SQLite URI mode=ro refuses data writes; query_only is defense in depth.
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only = ON')
        integrity = connection.execute('PRAGMA integrity_check').fetchall()
        violations = connection.execute('PRAGMA foreign_key_check').fetchall()
        if integrity != [('ok',)] or violations:
            raise RuntimeError(f'{path.name}: integrity={integrity}, foreign-key violations={violations}')
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        digest = hashlib.sha256()
        total = 0
        for name in tables:
            sql = 'SELECT * FROM ' + _quote_identifier(name) + ' ORDER BY rowid'
            cursor = connection.execute(sql)
            columns = [description[0] for description in cursor.description]
            count = 0
            for row in cursor:
                values = [value.hex() if isinstance(value, bytes) else value for value in row]
                digest.update(json.dumps((name, values), ensure_ascii=False,
                                         separators=(',', ':'), default=str).encode('utf-8'))
                digest.update(b'\n')
                count += 1
            total += count
            # M116 never adds or changes SQLite columns. M115's optional provenance
            # field should already exist in Location Assets after initialization.
            if require_m115 and name == 'location_assets' and 'texture_filename' not in columns:
                raise RuntimeError('game1.db: expected M115 texture_filename column is missing')
        if backup_dir is not None:
            backup_dir.mkdir(parents=True, exist_ok=True)
            dest = backup_dir / path.name
            if dest.exists():
                raise FileExistsError(f'refusing to overwrite existing backup: {dest}')
            with closing(sqlite3.connect(dest)) as backup:
                connection.backup(backup)
            with closing(sqlite3.connect(dest.resolve().as_uri() + '?mode=ro', uri=True)) as verify:
                if verify.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise RuntimeError(f'backup integrity failed: {dest}')
        print(f'{path.name}: OK | tables={len(tables)} | rows={total} | data_sha256={digest.hexdigest()}')
        return total, digest.hexdigest()
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=PROJECT_ROOT, help='game1 project root')
    parser.add_argument('--backup-dir', type=Path, help='create SQLite online backups here')
    parser.add_argument('--require-m115', action='store_true',
                        help='require the M115 texture_filename schema column')
    args = parser.parse_args()
    root = args.root.resolve() / '.control-center'
    if not root.is_dir():
        parser.error(f'not found: {root}')
    for name in DATABASES:
        audit_database(root / name, backup_dir=args.backup_dir, require_m115=args.require_m115)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
