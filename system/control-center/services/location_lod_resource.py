"""Independent Location Asset LOD1 authoring and Open Cloud publication.

No Studio/Place mutation, no implicit FULL publication, and no additional
client payload until a future World Streaming implementation consumes the ID.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import time

from model_publication_service import staged_model
from opencloud_assets import create_model_asset, wait_for_operation
from sqlite_connection import connect as connect_sqlite

_SLUG = re.compile(r'[a-z0-9][a-z0-9_]{0,63}\Z')
_KIND = 'lod1'
_MAX_FBX_BYTES = 200 * 1024 * 1024


def _identity(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        raise ValueError('invalid Location Asset slug')
    return slug


def ensure_schema(store) -> None:
    """Additive schema; pre-upgrade snapshot if the table does not exist."""
    with store.connect() as db:
        found = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='location_asset_lod_resources'").fetchone()
        if not found:
            backup_dir = store.runtime / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / ('location_lod_before_' +
                datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
            with connect_sqlite(backup) as snapshot:
                db.backup(snapshot)
        db.execute('''CREATE TABLE IF NOT EXISTS location_asset_lod_resources(
            asset_slug TEXT NOT NULL,
            kind TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            published_sha256 TEXT NOT NULL DEFAULT '',
            asset_id TEXT NOT NULL DEFAULT '',
            moderation_state TEXT NOT NULL DEFAULT '',
            revision INTEGER NOT NULL,
            updated_at REAL NOT NULL,
            published_at REAL,
            PRIMARY KEY(asset_slug,kind)
        )''')


def describe(store, slug: str) -> dict:
    slug = _identity(slug)
    with store.connect() as db:
        row = db.execute('SELECT * FROM location_asset_lod_resources WHERE asset_slug=? AND kind=?',
                         (slug, _KIND)).fetchone()
    if row is None:
        return {'kind': _KIND, 'revision': 0, 'status': 'NOT_REGISTERED',
                'sourcePath': '', 'sourceSha256': '', 'publishedSha256': '',
                'modelAssetId': '', 'moderationState': ''}
    row = dict(row)
    source = (store.root / row['source_path']).resolve()
    available = source.is_file() and source.is_relative_to(store.root)
    status = ('SOURCE_MISSING' if not available else
              'PUBLISHED' if row['asset_id'] and row['source_sha256'] == row['published_sha256'] else
              'UPDATE_AVAILABLE' if row['asset_id'] else 'STAGED')
    return {'kind': _KIND, 'revision': int(row['revision']), 'status': status,
            'sourcePath': row['source_path'], 'sourceSha256': row['source_sha256'],
            'publishedSha256': row['published_sha256'], 'modelAssetId': row['asset_id'],
            'moderationState': row['moderation_state']}


def history(store, slug: str, limit: int = 20) -> list[dict]:
    _identity(slug)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('invalid LOD history limit')
    with store.connect() as db:
        rows = db.execute('''SELECT revision,asset_id,sha256,moderation_state,published_at
            FROM location_asset_publications WHERE asset_slug=? AND kind=?
            ORDER BY id DESC LIMIT ?''', (slug, _KIND, limit)).fetchall()
    return [dict(row) for row in rows]


def stage(store, slug: str, source_path: str, expected_revision: int) -> dict:
    """Register an independent FBX revision without publishing anything."""
    slug = _identity(slug)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('expected LOD1 revision is required')
    full = store._raw_get(slug)
    if not full:
        raise ValueError('unknown Location Asset')
    source = Path(str(source_path or '')).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != '.fbx':
        raise ValueError('choose a valid LOD1 FBX source')
    expected_name = f'{slug}_lod1.fbx'
    if source.name != expected_name:
        raise ValueError(f'LOD1 filename must be {expected_name}; rename the source FBX before registration')
    if not 0 < source.stat().st_size <= _MAX_FBX_BYTES:
        raise ValueError('LOD1 FBX file is empty or exceeds 200 MB')
    # File picker can return renamed files. Reject non-FBX payloads before
    # recording a new authoring revision (deep geometry checks occur on publish).
    with source.open('rb') as stream:
        header = stream.read(4096)
    if not (header.startswith(b'Kaydara FBX Binary') or b'FBXHeaderExtension' in header):
        raise ValueError('LOD1 source is not a recognizable binary or ASCII FBX')
    sha = store._sha256(source)
    current = describe(store, slug)
    if current['revision'] != expected_revision:
        raise ValueError('LOD1 changed since editor opened; refresh')
    if current['sourceSha256'] == sha and current['status'] != 'SOURCE_MISSING':
        return current  # Idempotent: keep publication and revision.
    # The source is immutable per authoring revision and never shares the FULL FBX.
    target = (store.root / 'assets/source/location-assets' /
              str(full['category']) / slug / 'lod' / 'lod1.fbx')
    target.parent.mkdir(parents=True, exist_ok=True)
    if source != target.resolve():
        if target.is_file():
            archive = (store.root / 'assets/reimported/location-assets' / slug /
                       f'lod1_r{expected_revision:04d}' / 'lod1.fbx')
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                shutil.copy2(target, archive)
        staged = target.with_name(target.name + '.tmp')
        try:
            shutil.copy2(source, staged)
            if store._sha256(staged) != sha:
                raise RuntimeError('LOD1 copy checksum mismatch')
            staged.replace(target)
        finally:
            staged.unlink(missing_ok=True)
    relative = target.relative_to(store.root).as_posix()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision FROM location_asset_lod_resources WHERE asset_slug=? AND kind=?',
                         (slug, _KIND)).fetchone()
        if (int(row['revision']) if row else 0) != expected_revision:
            raise ValueError('LOD1 revision changed during stage; refresh')
        db.execute('''INSERT INTO location_asset_lod_resources(
            asset_slug,kind,source_path,source_sha256,revision,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(asset_slug,kind) DO UPDATE SET
            source_path=excluded.source_path,source_sha256=excluded.source_sha256,
            revision=excluded.revision,updated_at=excluded.updated_at''',
            (slug, _KIND, relative, sha, expected_revision + 1, time.time()))
    store.export()
    return describe(store, slug)


def publish(store, slug: str, expected_revision: int, credentials: dict) -> dict:
    slug = _identity(slug)
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError('expected LOD1 revision required')
    full = store._raw_get(slug)
    if not full:
        raise ValueError('unknown Location Asset')
    data = describe(store, slug)
    if data['revision'] != expected_revision:
        raise ValueError('LOD1 revision changed; refresh')
    if data['status'] == 'PUBLISHED':
        return data  # Never republish identical bytes implicitly.
    if data['status'] not in {'STAGED', 'UPDATE_AVAILABLE'}:
        raise ValueError('stage a valid LOD1 FBX before publication')
    path = (store.root / data['sourcePath']).resolve()
    if not path.is_relative_to(store.root) or store._sha256(path) != data['sourceSha256']:
        raise ValueError('LOD1 source changed; stage it again')
    api_key = str(credentials.get('apiKey') or '')
    with staged_model(store.root, path, texture_mode='geometry_only') as publication:
        operation = create_model_asset(
            publication, display_name=f'{slug}_lod1',
            description=str(credentials.get('description') or 'game1 location LOD1'),
            creator_type=str(credentials.get('creatorType') or ''),
            creator_id=str(credentials.get('creatorId') or ''), api_key=api_key)
    result = wait_for_operation(operation, api_key=api_key)
    now = time.time()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision,source_sha256 FROM location_asset_lod_resources '
                         'WHERE asset_slug=? AND kind=?', (slug, _KIND)).fetchone()
        if (row is None or row['revision'] != expected_revision or
                row['source_sha256'] != data['sourceSha256']):
            raise RuntimeError('LOD1 changed during upload. New asset was published; '
                               'record its ID manually from Open Cloud before retrying.')
        db.execute('''UPDATE location_asset_lod_resources SET asset_id=?,published_sha256=?,
            moderation_state=?,published_at=? WHERE asset_slug=? AND kind=?''',
            (str(result.asset_id), data['sourceSha256'], result.moderation_state or '',
             now, slug, _KIND))
        db.execute('''INSERT INTO location_asset_publications(
            asset_slug,kind,revision,asset_id,operation_path,sha256,moderation_state,published_at)
            VALUES(?,?,?,?,?,?,?,?)''',
            (slug, _KIND, expected_revision, str(result.asset_id), result.operation_path,
             data['sourceSha256'], result.moderation_state or '', now))
    store.export()
    return describe(store, slug)
