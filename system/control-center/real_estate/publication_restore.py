"""Guarded restore of one Real Estate visual Model reference from a DB snapshot.

Keeps Roblox publication audit and every unrelated part intact.  Studio Place is
not modified here: the operator must run Sync entire house after the restore.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
import json
import hashlib
from pathlib import Path
import sqlite3
import time
import uuid

from .rig_publication_policy import publication_fingerprint


def _safe_db(root: Path, relative_path: str) -> Path:
    db = (root / relative_path).resolve()
    if not db.is_relative_to(root) or not db.is_file() or db.suffix.lower() not in ('.sqlite', '.db'):
        raise ValueError('restore reference must be an existing project-local SQLite snapshot')
    return db


def _record(connection: sqlite3.Connection, slug: str) -> dict:
    row = connection.execute('select * from real_estate where slug=?', (slug,)).fetchone()
    if not row:
        raise ValueError('house does not exist in both authoring databases')
    return dict(row)


def _part_mesh(row: dict, part: str) -> dict:
    source = json.loads(row['skeleton_json'])
    matches = [mesh for mesh in source['meshes'] if mesh.get('name') == part]
    if len(matches) != 1:
        raise ValueError('requested part is missing or ambiguous in authoring skeleton')
    return matches[0]


def restore_visual_part(root: Path, *, slug: str, part: str,
                        snapshot: str, current_id: str, restore_id: str) -> dict:
    """CAS restore with an SQLite backup and an append-only publication history.

    Only the requested skeleton mesh, its standalone source and its published
    rigAsset ID are reverted.  Never revert an entire house from an older DB.
    """
    root = Path(root).resolve()
    if not slug or not part or not str(current_id).isdigit() or not str(restore_id).isdigit():
        raise ValueError('house, part and both numeric Model Asset IDs are required')
    old_db = _safe_db(root, snapshot)
    active_db = root / '.control-center' / 'game1_real_estate.db'
    if old_db == active_db or not active_db.is_file():
        raise ValueError('restore requires a separate historical authoring database')
    with closing(sqlite3.connect(old_db)) as old:
        old.row_factory = sqlite3.Row
        reference = _record(old, slug)
    current = sqlite3.connect(active_db, timeout=10)
    current.row_factory = sqlite3.Row
    try:
        # Do not move authoring origin, FBX source or any of the other parts.
        current_row = _record(current, slug)
        if current_row['model_sha256'] != reference['model_sha256']:
            raise ValueError('original house FBX fingerprint changed; restore refused')
        original_source = (root / reference['model_path']).resolve()
        if not original_source.is_relative_to(root) or not original_source.is_file():
            raise ValueError('original house source FBX unavailable; restore refused')
        if hashlib.sha256(original_source.read_bytes()).hexdigest() != reference['model_sha256']:
            raise ValueError('original house source FBX no longer matches the verified publication')
        current_mesh = _part_mesh(current_row, part)
        restored_mesh = _part_mesh(reference, part)
        rig_current = json.loads(current_row['model_rigs_json'])
        rig_reference = json.loads(reference['model_rigs_json'])
        source_current = json.loads(current_row['mesh_sources_json'] or '{}')
        source_reference = json.loads(reference['mesh_sources_json'] or '{}')
        previous = rig_current.get(part, {})
        selected = rig_reference.get(part, {})
        if selected.get('assetId') != str(restore_id):
            raise ValueError('restore ID does not match the selected historical snapshot')
        reference_source = source_reference.get(part, {}).get('sha256') or reference['model_sha256']
        if selected.get('publishedSha256') != publication_fingerprint(reference_source, carrier=False):
            raise ValueError('historical Model ID and source fingerprint disagree')
        if previous.get('assetId') == str(restore_id) and current_mesh == restored_mesh and (
                source_current.get(part) == source_reference.get(part)):
            return {'changed': False, 'house': slug, 'part': part, 'assetId': str(restore_id)}
        if previous.get('assetId') != str(current_id):
            raise ValueError('authoring reference changed since inspection; refusing restore')
        if current_row['model_path'] != reference['model_path']:
            raise ValueError('original FBX identity changed')
        if (not str(restore_id).isdigit() or not any(r[0] == str(restore_id)
                for r in current.execute('select asset_id from real_estate_publications '
                                         'where house_slug=? and part=?', (slug, 'model:' + part)))):
            raise ValueError('historical Model ID absent from append-only publication history')
        # Consistent SQLite backup before updating one row. Its location is
        # returned to the caller for recovery; never overwrite a prior backup.
        backup_folder = root / '.control-center' / 'backups'
        backup_folder.mkdir(parents=True, exist_ok=True)
        backup_name = ('real_estate_before_part_restore_' +
                       datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid.uuid4().hex + '.sqlite')
        backup = backup_folder / backup_name
        with closing(sqlite3.connect(backup)) as copy:
            current.backup(copy)
        updated_skeleton = json.loads(current_row['skeleton_json'])
        updated_skeleton['meshes'] = [restored_mesh if mesh['name'] == part else mesh
                                      for mesh in updated_skeleton['meshes']]
        rig_current[part] = selected
        if part in source_reference:
            source_current[part] = source_reference[part]
        else:
            source_current.pop(part, None)
        current.execute('begin immediate')
        changed = current.execute('''update real_estate set skeleton_json=?,
            model_rigs_json=?,mesh_sources_json=?,revision=revision+1,updated_at=?
            where slug=? and revision=? and model_rigs_json=?''',
            (json.dumps(updated_skeleton, ensure_ascii=False),
             json.dumps(rig_current, ensure_ascii=False),
             json.dumps(source_current, ensure_ascii=False), time.time(), slug,
             current_row['revision'], current_row['model_rigs_json']))
        if changed.rowcount != 1:
            current.rollback()
            raise ValueError('house revision changed while preparing restore')
        current.commit()
    finally:
        current.close()
    # The authoring export is only a derived manifest; old source and all
    # recorded Roblox publication operations remain untouched.
    from .store import RealEstateStore
    RealEstateStore(root).export()
    return {'changed': True, 'house': slug, 'part': part,
            'previousAssetId': str(current_id), 'assetId': str(restore_id),
            'backup': backup.relative_to(root).as_posix(),
            'studioNeedsSync': True}
