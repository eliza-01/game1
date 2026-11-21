"""Location Asset LOD1: own FBX publication or reuse of a published Model ID.

No Studio/Place mutation and no implicit FULL publication. The existing
Runtime Builder / LocationWorldStreamer consumes the pinned published ID.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import time

from services.model_lod_common import (inspect_fbx, preserve_source, publish_geometry,
    check_revision, describe_resource, verified_source, reuse_values)
from sqlite_connection import connect as connect_sqlite

_SLUG = re.compile(r'[a-z0-9][a-z0-9_]{0,63}\Z')
_KIND = 'lod1'


def _identity(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        raise ValueError('invalid Location Asset slug')
    return slug


def ensure_schema(store) -> None:
    """Additive schema; pre-upgrade snapshot if the table does not exist."""
    with store.connect() as db:
        found = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='location_asset_lod_resources'").fetchone()
        columns = ({r[1] for r in db.execute('PRAGMA table_info(location_asset_lod_resources)')}
                   if found else set())
        if not found or not {'reuse_domain','reuse_slug','reuse_revision'}.issubset(columns):
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
        for name, definition in (('reuse_domain', "TEXT NOT NULL DEFAULT ''"),
                                 ('reuse_slug', "TEXT NOT NULL DEFAULT ''"),
                                 ('reuse_revision', 'INTEGER NOT NULL DEFAULT 0')):
            existing = {r[1] for r in db.execute('PRAGMA table_info(location_asset_lod_resources)')}
            if name not in existing:
                db.execute(f'ALTER TABLE location_asset_lod_resources ADD COLUMN {name} {definition}')


def describe(store, slug: str) -> dict:
    slug = _identity(slug)
    with store.connect() as db:
        row = db.execute('SELECT * FROM location_asset_lod_resources WHERE asset_slug=? AND kind=?',
                         (slug, _KIND)).fetchone()
    return describe_resource(row, store.root, kind=_KIND)


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
    source, sha = inspect_fbx(source_path, f'{slug}_lod1.fbx')
    current = describe(store, slug)
    check_revision(expected_revision, current['revision'])
    if current['sourceSha256'] == sha and current['status'] != 'SOURCE_MISSING' and not current['reuse']:
        return current  # Idempotent: keep publication and revision.
    # The source is immutable per authoring revision and never shares the FULL FBX.
    target = (store.root / 'assets/source/location-assets' /
              str(full['category']) / slug / 'lod' / 'lod1.fbx')
    archive = (store.root / 'assets/reimported/location-assets' / slug /
               f'lod1_r{expected_revision:04d}' / 'lod1.fbx')
    preserve_source(source, target, archive, sha)
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
            revision=excluded.revision,updated_at=excluded.updated_at,
            reuse_domain='',reuse_slug='',reuse_revision=0''',
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
    check_revision(expected_revision, data['revision'])
    if data['status'] == 'PUBLISHED':
        return data  # Never republish identical bytes implicitly.
    if data['status'] not in {'STAGED', 'UPDATE_AVAILABLE'}:
        raise ValueError('stage a valid LOD1 FBX before publication')
    path = verified_source(store.root, data, digest=store._sha256)
    result = publish_geometry(store.root, path, slug, credentials,
                              description='game1 location LOD1')
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


def reuse(store, slug: str, source: dict, expected_revision: int) -> dict:
    # Pin an existing verified Open Cloud LOD1, not a mutable source record.
    slug = _identity(slug)
    if not store._raw_get(slug):
        raise ValueError('unknown Location Asset')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT revision FROM location_asset_lod_resources WHERE asset_slug=? AND kind=?',
                         (slug, _KIND)).fetchone()
        pinned = reuse_values(source, 'location', slug, expected_revision, old['revision'] if old else 0)
        db.execute('''INSERT INTO location_asset_lod_resources (
            asset_slug,kind,source_path,source_sha256,published_sha256,asset_id,
            moderation_state,revision,updated_at,published_at,reuse_domain,reuse_slug,reuse_revision)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(asset_slug,kind) DO UPDATE SET
            source_path=excluded.source_path,source_sha256=excluded.source_sha256,
            published_sha256=excluded.published_sha256,asset_id=excluded.asset_id,
            moderation_state=excluded.moderation_state,revision=excluded.revision,
            updated_at=excluded.updated_at,published_at=excluded.published_at,
            reuse_domain=excluded.reuse_domain,reuse_slug=excluded.reuse_slug,
            reuse_revision=excluded.reuse_revision''',
            (slug,_KIND,'',pinned['source_sha256'],pinned['published_sha256'],
             pinned['asset_id'],pinned['moderation_state'],pinned['revision'],
             time.time(),time.time(),pinned['reuse_domain'],pinned['reuse_slug'],pinned['reuse_revision']))
    store.export()
    return describe(store,slug)
