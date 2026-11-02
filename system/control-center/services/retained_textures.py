"""Published texture identities retained after their model registration is retired.

Legacy owner references remain resolvable. No Roblox upload or atlas variant is
created, and the author's source image is never copied or deleted here.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from sqlite_connection import connect


class RetainedTextures:
    def __init__(self, root: Path):
        self.db = Path(root) / '.control-center' / 'game1.db'
        with connect(self.db) as db:
            table_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='retained_shared_textures'").fetchone()
            if not table_exists and self.db.is_file():
                backup_dir = self.db.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_file = backup_dir / ('before_m199_shared_retirement_' + uuid.uuid4().hex + '.db')
                with connect(backup_file) as target:
                    db.backup(target)
            db.execute('''CREATE TABLE IF NOT EXISTS retained_shared_textures (
                reference TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL,
                retained_at REAL NOT NULL)''')

    def get(self, reference: str) -> dict | None:
        with connect(self.db) as db:
            row = db.execute('SELECT snapshot_json FROM retained_shared_textures WHERE reference=?',
                             (reference,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, prefix: str = '') -> list[tuple[str, dict]]:
        with connect(self.db) as db:
            rows = db.execute('SELECT reference,snapshot_json FROM retained_shared_textures '
                              'WHERE substr(reference,1,length(?))=? ORDER BY reference', (prefix, prefix)).fetchall()
        return [(r[0], json.loads(r[1])) for r in rows]

    def retain(self, reference: str, snapshot: dict) -> None:
        if not reference.startswith(('estate:', 'location:')):
            raise ValueError('unsupported retained texture reference')
        # Never replace an already-retired publication identity.
        with connect(self.db) as db:
            db.execute('INSERT OR IGNORE INTO retained_shared_textures '
                       '(reference,snapshot_json,retained_at) VALUES (?,?,?)',
                       (reference, json.dumps(snapshot, ensure_ascii=False), time.time()))
