"""Append-only SQLite snapshots of recognized Location placements (not an RBXL backup)."""
from __future__ import annotations

import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import time
import zlib


class PlaceRevisionStore:
    def __init__(self, root: str | Path):
        self.path = Path(root) / '.control-center' / 'location-place-revisions.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS location_place_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_utc INTEGER NOT NULL,
                    place_id INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    registry_digest TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    issues INTEGER NOT NULL,
                    payload BLOB NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_location_place_revisions_place
                    ON location_place_revisions(place_id, id DESC);
                CREATE TABLE IF NOT EXISTS location_place_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_utc INTEGER NOT NULL,
                    before_revision INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    affected INTEGER NOT NULL,
                    report TEXT NOT NULL,
                    FOREIGN KEY(before_revision) REFERENCES location_place_revisions(id)
                );
            ''')

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, report: dict, digest: str):
        # Canonical full precision; missing/duplicate IDs are preserved, not merged.
        data = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        fingerprint = hashlib.sha256(data).hexdigest()
        place_id = int(report.get('placeId') or 0)
        issue_count = sum(bool(p.get('issues')) for p in report['placements'])
        with closing(self._connect()) as db, db:
            previous = db.execute('SELECT id, fingerprint FROM location_place_revisions '
                                  'WHERE place_id=? ORDER BY id DESC LIMIT 1', (place_id,)).fetchone()
            if previous and previous['fingerprint'] == fingerprint:
                return {'revisionId': previous['id'], 'unchanged': True,
                        'recorded': False, 'fingerprint': fingerprint}
            cursor = db.execute('INSERT INTO location_place_revisions '
                                '(recorded_utc,place_id,fingerprint,registry_digest,total,issues,payload) '
                                'VALUES(?,?,?,?,?,?,?)',
                                (int(time.time()), place_id, fingerprint, digest,
                                 len(report['placements']), issue_count, zlib.compress(data, 9)))
            return {'revisionId': cursor.lastrowid, 'unchanged': False,
                    'recorded': True, 'fingerprint': fingerprint}

    def page(self, limit: int = 20):
        if type(limit) is not int or limit < 1 or limit > 100:
            raise ValueError('limit must be 1..100')
        with closing(self._connect()) as db, db:
            rows = db.execute('SELECT id, recorded_utc, place_id, fingerprint, total, issues '
                              'FROM location_place_revisions ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(v) for v in rows]

    def get(self, revision_id: int):
        if type(revision_id) is not int or revision_id < 1:
            raise ValueError('invalid revision ID')
        with closing(self._connect()) as db, db:
            row = db.execute('SELECT payload FROM location_place_revisions WHERE id=?',
                             (revision_id,)).fetchone()
        if row is None:
            raise ValueError('unknown Place revision')
        return json.loads(zlib.decompress(row['payload']))

    def diff(self, a: int, b: int):
        previous, current = self.get(a), self.get(b)
        # Placement IDs can be duplicated by Studio copy. Use path and complete
        # spatial snapshot as multiset identity, not a lossy placement-ID map.
        def entries(report):
            counter = {}
            for row in report['placements']:
                data = json.dumps(row, sort_keys=True, ensure_ascii=False)
                counter[data] = counter.get(data, 0) + 1
            return counter
        x, y = entries(previous), entries(current)
        return {'from': a, 'to': b,
                'added': sum(max(0, y[k] - x.get(k, 0)) for k in y),
                'removed': sum(max(0, x[k] - y.get(k, 0)) for k in x),
                'placeId': current.get('placeId')}

    def log_action(self, before_revision: int, action: str, report: dict):
        if action not in ('repair', 'sync') or type(before_revision) is not int or before_revision < 1:
            raise ValueError('invalid Place mutation audit')
        with closing(self._connect()) as db, db:
            db.execute('INSERT INTO location_place_actions '
                       '(recorded_utc,before_revision,action,affected,report) VALUES(?,?,?,?,?)',
                       (int(time.time()), before_revision, action,
                        int(report.get('changed') or 0), json.dumps(report, ensure_ascii=False)))
