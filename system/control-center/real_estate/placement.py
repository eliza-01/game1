"""Authoritative authoring bindings for (plot, registered house) placement.

No player ownership or runtime spawning occurs here. Studio supplies a measured
Model pivot/scale; this repository verifies, versions and persists it. Plot-local
CFrame survives legitimate map editing and is the intended runtime contract.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid

from sqlite_connection import connect

SCHEMA_VERSION = 1  # unchanged CFrame capture protocol; anchored is additive metadata
PLOT_COUNT = 50


def _cframe(raw, field: str) -> list[float]:
    if not isinstance(raw, list) or len(raw) != 12:
        raise ValueError(f'{field} must contain 12 CFrame components')
    if any(type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 10_000_000
           for value in raw):
        raise ValueError(f'{field} contains an invalid CFrame component')
    result = [float(value) for value in raw]
    # Roblox GetComponents: position xyz, then orthonormal 3x3 rotation.
    rows = [result[3:6], result[6:9], result[9:12]]
    for index in range(3):
        if abs(sum(v*v for v in rows[index]) - 1.0) > 0.01:
            raise ValueError(f'{field} rotation is not normalized')
        for other in range(index + 1, 3):
            if abs(sum(a*b for a, b in zip(rows[index], rows[other]))) > 0.01:
                raise ValueError(f'{field} rotation axes are not orthogonal')
    return result


def validate_capture(capture: dict, house_slug: str, plot_index: int) -> dict:
    if not isinstance(capture, dict):
        raise ValueError('Studio placement capture is missing')
    if capture.get('houseSlug') != house_slug or capture.get('plotIndex') != plot_index:
        raise ValueError('Studio placement does not match the selected house and plot')
    if capture.get('schemaVersion') != SCHEMA_VERSION:
        raise ValueError('Studio placement schema version is not supported')
    if capture.get('plotVolume') not in (
        f'plot_{plot_index:02d}_volume', f'plot_{plot_index}_volume'
    ):
        raise ValueError('Studio plot volume identity does not match the selected plot')
    # Never save two contradictory placements. The plot-local transform is
    # authoritative for future purchase placement; world is the authoring audit.
    world = _cframe(capture.get('worldCFrame'), 'worldCFrame')
    plot = _cframe(capture.get('plotCFrame'), 'plotCFrame')
    local = _cframe(capture.get('localCFrame'), 'localCFrame')
    for row in range(3):
        expected_position = plot[row] + sum(plot[3 + row*3 + k] * local[k] for k in range(3))
        if abs(expected_position - world[row]) > 0.05:
            raise ValueError('world and plot-local placements do not agree')
        for column in range(3):
            expected_axis = sum(plot[3 + row*3 + k] * local[3 + k*3 + column]
                                for k in range(3))
            if abs(expected_axis - world[3 + row*3 + column]) > 0.01:
                raise ValueError('world and plot-local rotations do not agree')
    scale = capture.get('scale')
    if type(scale) not in (int, float) or not math.isfinite(scale) or not 0.001 <= scale <= 1000:
        raise ValueError('Studio Model scale must be finite and positive')
    return {
        'worldCFrame': world,
        'plotCFrame': plot,
        'localCFrame': local,
        'scale': float(scale),
        'plotVolume': capture['plotVolume'],
    }


class RealEstatePlacementStore:
    def __init__(self, root: Path, houses):
        self.root = root.resolve()
        self.houses = houses
        self.db = self.root / '.control-center' / 'game1_real_estate.db'
        with connect(self.db) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS real_estate_placements (
                plot_index INTEGER NOT NULL CHECK(plot_index BETWEEN 1 AND 50),
                house_slug TEXT NOT NULL,
                plot_volume TEXT NOT NULL,
                world_cframe_json TEXT NOT NULL,
                plot_cframe_json TEXT NOT NULL,
                local_cframe_json TEXT NOT NULL,
                model_scale REAL NOT NULL CHECK(model_scale > 0),
                revision INTEGER NOT NULL DEFAULT 1,
                anchored INTEGER NOT NULL DEFAULT 1 CHECK(anchored IN (0,1)),
                updated_at REAL NOT NULL,
                PRIMARY KEY(plot_index, house_slug)
            )''')
            # Additive migration for pre-M224 placement databases. Existing houses start anchored.
            cols = {row[1] for row in db.execute("PRAGMA table_info(real_estate_placements)")}
            if "anchored" not in cols:
                # Use SQLite's online backup API before this one-time migration;
                # raw copying an open WAL database would not be reliable.
                backups = self.db.parent / 'backups'
                backups.mkdir(parents=True, exist_ok=True)
                backup_path = backups / f'before_placement_anchor_m224_{uuid.uuid4().hex}.db'
                with connect(backup_path) as backup:
                    db.backup(backup)
                db.execute("ALTER TABLE real_estate_placements ADD COLUMN anchored INTEGER NOT NULL DEFAULT 1 CHECK(anchored IN (0,1))")
            # Deleting a house must retire only its placement bindings.
            db.execute('''CREATE TRIGGER IF NOT EXISTS real_estate_placements_house_delete
                AFTER DELETE ON real_estate BEGIN
                DELETE FROM real_estate_placements WHERE house_slug=OLD.slug;
                END''')
        self.export()

    def snapshot(self) -> dict:
        # Deleted houses may have archival records, never offer them for placement.
        with connect(self.db) as db:
            rows = [dict(item) for item in db.execute(
                'SELECT p.* FROM real_estate_placements p '
                'JOIN real_estate h ON h.slug=p.house_slug '
                'ORDER BY p.plot_index,p.house_slug')]
        return {'schemaVersion': SCHEMA_VERSION, 'plotCount': PLOT_COUNT,
                'items': [self._present(row) for row in rows]}

    @staticmethod
    def _present(row: dict) -> dict:
        return {'plotIndex': row['plot_index'], 'houseSlug': row['house_slug'],
                'plotVolume': row['plot_volume'], 'worldCFrame': json.loads(row['world_cframe_json']),
                'plotCFrame': json.loads(row['plot_cframe_json']),
                'localCFrame': json.loads(row['local_cframe_json']),
                'scale': row['model_scale'], 'revision': row['revision'],
                'anchored': bool(row['anchored']),
                'updatedAt': row['updated_at']}

    def get(self, house_slug: str, plot_index: int) -> dict | None:
        if type(plot_index) is not int or not 1 <= plot_index <= PLOT_COUNT:
            raise ValueError('plot must be an integer between 1 and 50')
        with connect(self.db) as db:
            row = db.execute('''SELECT p.* FROM real_estate_placements p
                JOIN real_estate h ON h.slug=p.house_slug
                WHERE p.house_slug=? AND p.plot_index=?''',
                (house_slug, plot_index)).fetchone()
        return self._present(dict(row)) if row else None

    def bind(self, house_slug: str, plot_index: int, capture: dict) -> dict:
        if not isinstance(house_slug, str) or not house_slug or self.houses.get(house_slug) is None:
            raise ValueError('choose a registered house before binding a plot')
        if type(plot_index) is not int or not 1 <= plot_index <= PLOT_COUNT:
            raise ValueError('plot must be an integer between 1 and 50')
        data = validate_capture(capture, house_slug, plot_index)
        now = time.time()
        with connect(self.db) as db:
            db.execute('''INSERT INTO real_estate_placements (
                plot_index,house_slug,plot_volume,world_cframe_json,plot_cframe_json,
                local_cframe_json,model_scale,revision,updated_at)
                VALUES (?,?,?,?,?,?,?,1,?)
                ON CONFLICT(plot_index,house_slug) DO UPDATE SET
                plot_volume=excluded.plot_volume,
                world_cframe_json=excluded.world_cframe_json,
                plot_cframe_json=excluded.plot_cframe_json,
                local_cframe_json=excluded.local_cframe_json,
                model_scale=excluded.model_scale,
                revision=real_estate_placements.revision+1,
                updated_at=excluded.updated_at''', (
                plot_index, house_slug, data['plotVolume'],
                json.dumps(data['worldCFrame']), json.dumps(data['plotCFrame']),
                json.dumps(data['localCFrame']), data['scale'], now))
            row = dict(db.execute('SELECT * FROM real_estate_placements '
                                  'WHERE plot_index=? AND house_slug=?', (plot_index, house_slug)).fetchone())
        self.export()
        return self._present(row)

    def set_anchored(self, targets: list[dict], anchored: bool) -> int:
        """Persist authoring flags after Studio confirms the requested mutation.

        Only exact, existing plot×house bindings are writable. The geometric
        binding revision remains unchanged because its transform did not change.
        """
        if type(anchored) is not bool or not isinstance(targets, list):
            raise ValueError('invalid anchor state or targets')
        seen = set()
        for pair in targets:
            if not isinstance(pair, dict):
                raise ValueError('invalid placement target')
            slug, plot = pair.get('houseSlug'), pair.get('plotIndex')
            if not isinstance(slug, str) or not slug or type(plot) is not int or not 1 <= plot <= PLOT_COUNT:
                raise ValueError('invalid placement target')
            if (slug, plot) in seen:
                raise ValueError('duplicate placement target')
            seen.add((slug, plot))
        changed = 0
        with connect(self.db) as db:
            # Guard against stale UI/snapshot and removed rows.
            for slug, plot in seen:
                if not db.execute('SELECT 1 FROM real_estate_placements WHERE house_slug=? AND plot_index=?',
                                  (slug, plot)).fetchone():
                    raise ValueError('placement bindings changed; refresh and retry')
            for slug, plot in sorted(seen):
                changed += db.execute('UPDATE real_estate_placements SET anchored=? '
                    'WHERE house_slug=? AND plot_index=? AND anchored<>?',
                    (int(anchored), slug, plot, int(anchored))).rowcount
        if changed:
            self.export()
        return changed

    def export(self) -> None:
        """Atomic, deterministic authoring manifest for a future purchase service."""
        target = self.root / 'assets' / 'manifests' / 'real-estate-placements.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.snapshot(), indent=2, ensure_ascii=False, sort_keys=True) + '\n'
        path = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=target.parent,
                                             prefix='.placement-', suffix='.tmp',
                                             delete=False, newline='\n') as out:
                path = Path(out.name)
                out.write(payload)
            os.replace(path, target)
        finally:
            if path is not None and path.exists():
                path.unlink()
