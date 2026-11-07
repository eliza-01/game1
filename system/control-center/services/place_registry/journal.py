"""Append-only Studio mutation journal with explicit LIFO undo eligibility.

The Studio ChangeHistoryService is the *only* executor of Undo. This database
records actions and their confirmation, it never replays Place geometry from
JSON snapshots. Existing M240 history is retained in its original table.
"""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import re
import sqlite3
import time

_OPERATION_ID = re.compile(r'^[0-9a-f]{32}$')


class PlaceOperationJournal:
    def __init__(self, revision_db_path: str | Path):
        self.path = Path(revision_db_path)
        with closing(self._connect()) as db, db:
            existing = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                  "AND name='location_place_operation_journal'").fetchone()
            if existing is None and self.path.exists():
                # Additive migration, but preserve the original SQLite file as
                # required by game1 before modifying its schema.
                backup_dir = self.path.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / f'location_place_m241_{time.time_ns()}.sqlite'
                with closing(sqlite3.connect(backup)) as target, target:
                    db.backup(target)
            db.execute('''CREATE TABLE IF NOT EXISTS location_place_operation_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_utc INTEGER NOT NULL,
                place_id INTEGER NOT NULL,
                before_revision INTEGER NOT NULL,
                operation_id TEXT NOT NULL UNIQUE,
                action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'applied',
                affected INTEGER NOT NULL,
                selected_json TEXT NOT NULL,
                report_json TEXT NOT NULL,
                undone_utc INTEGER
            )''')
            db.execute('''CREATE INDEX IF NOT EXISTS idx_location_place_operations_place
                          ON location_place_operation_journal(place_id,id DESC)''')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def record(self, *, revision_id: int, place_id: int, operation_id: str,
               action: str, selected: list[dict], result: dict) -> int:
        if action not in ('repair', 'sync') or not isinstance(operation_id, str) or not _OPERATION_ID.fullmatch(operation_id):
            raise ValueError('Invalid Studio operation identity; journal refused')
        if type(result.get('changed')) is not int or result['changed'] < 0:
            raise ValueError('Invalid Studio mutation result')
        status = 'applied' if result['changed'] > 0 and result.get('undo') is True else 'no_changes'
        with closing(self._connect()) as db, db:
            cursor = db.execute('''INSERT INTO location_place_operation_journal
                (recorded_utc,place_id,before_revision,operation_id,action,status,affected,selected_json,report_json)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (int(time.time()), int(place_id), int(revision_id), operation_id, action,
                 status, result['changed'], json.dumps(selected, ensure_ascii=False),
                 json.dumps(result, ensure_ascii=False)))
            return cursor.lastrowid

    def page(self, limit: int = 40):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Journal page limit must be 1..100')
        with closing(self._connect()) as db, db:
            rows = db.execute('''SELECT * FROM location_place_operation_journal
                                 ORDER BY id DESC LIMIT ?''', (limit,)).fetchall()
            # Legacy M240 journal entries stay visible, but cannot be matched
            # against a particular Studio ChangeHistoryService recording.
            legacy = db.execute('''SELECT a.id,a.recorded_utc,a.before_revision,a.action,a.affected,a.report,
                                          r.place_id FROM location_place_actions a
                                          JOIN location_place_revisions r ON r.id=a.before_revision
                                          ORDER BY a.id DESC LIMIT ?''', (limit,)).fetchall()
        last_applied = next((v['id'] for v in rows if v['status'] == 'applied'), None)
        items=[]
        for r in rows:
            selected = json.loads(r['selected_json'])
            items.append({'id':r['id'], 'recordedUtc':r['recorded_utc'],
                          'placeId':r['place_id'], 'beforeRevision':r['before_revision'],
                          'action':r['action'], 'status':r['status'], 'affected':r['affected'],
                          'selected':selected, 'report':json.loads(r['report_json']),
                          'canUndo':r['id'] == last_applied,
                          'undoneUtc':r['undone_utc']})
        for r in legacy:
            items.append({'id':'legacy-'+str(r['id']), 'recordedUtc':r['recorded_utc'],
                          'placeId':r['place_id'], 'beforeRevision':r['before_revision'],
                          'action':r['action'], 'status':'legacy', 'affected':r['affected'],
                          'selected':[], 'report':json.loads(r['report']), 'canUndo':False})
        items.sort(key=lambda r: (r['recordedUtc'], str(r['id'])), reverse=True)
        return items[:limit]

    def undo_candidate(self, action_id: int) -> dict:
        if type(action_id) is not int or action_id < 1:
            raise ValueError('Invalid journal action ID')
        with closing(self._connect()) as db, db:
            row = db.execute('''SELECT * FROM location_place_operation_journal
                                WHERE id=?''', (action_id,)).fetchone()
            last = db.execute('''SELECT id FROM location_place_operation_journal
                                 WHERE status='applied' ORDER BY id DESC LIMIT 1''').fetchone()
        if row is None or row['status'] != 'applied' or last is None or last['id'] != action_id:
            raise ValueError('Undo must follow Studio history order; undo newer actions first')
        return {'id':row['id'], 'operation_id':row['operation_id'], 'place_id':row['place_id']}

    def mark_undone(self, action_id: int, operation_id: str):
        with closing(self._connect()) as db, db:
            updated = db.execute('''UPDATE location_place_operation_journal
                    SET status='undone',undone_utc=? WHERE id=? AND operation_id=? AND status='applied' ''',
                    (int(time.time()), action_id, operation_id))
            if updated.rowcount != 1:
                raise ValueError('Undo journal state conflict; run Scan to reconcile')
