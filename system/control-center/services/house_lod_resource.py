"""House LOD1 is one independent Model Asset per stable house type.

Shares the existing geometry-only Model publisher with Location LOD1. It never
changes a Plot, a house FULL publication, or any Studio instance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time

from services.model_lod_common import (inspect_fbx, preserve_source, publish_geometry, sha256,
    check_revision, describe_resource, verified_source, reuse_values)
from sqlite_connection import connect as connect_sqlite
from services.house_runtime_profile import validate, readiness, DEFAULT

_MAX_FBX_BYTES = 200 * 1024 * 1024


_sha = sha256


def ensure_schema(store):
    with store.connect() as db:
        existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        current_cols = ({r[1] for r in db.execute('PRAGMA table_info(real_estate_lod1)')}
                        if 'real_estate_lod1' in existing else set())
        if (not {'real_estate_lod1', 'real_estate_streaming_profiles'}.issubset(existing)
                or not {'reuse_domain','reuse_slug','reuse_revision'}.issubset(current_cols)):
            backup_dir = store.root / '.control-center' / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            target = backup_dir / ('real_estate_runtime_pre_m387_' +
                datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
            with connect_sqlite(target) as backup:
                db.backup(backup)
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_lod1 (
            house_slug TEXT PRIMARY KEY, source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL, full_source_sha256 TEXT NOT NULL,
            published_sha256 TEXT NOT NULL DEFAULT '', asset_id TEXT NOT NULL DEFAULT '',
            moderation_state TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL,
            published_at REAL, updated_at REAL NOT NULL)''')
        for name, definition in (('reuse_domain', "TEXT NOT NULL DEFAULT ''"),
                                 ('reuse_slug', "TEXT NOT NULL DEFAULT ''"),
                                 ('reuse_revision', 'INTEGER NOT NULL DEFAULT 0')):
            cols = {r[1] for r in db.execute('PRAGMA table_info(real_estate_lod1)')}
            if name not in cols:
                db.execute(f'ALTER TABLE real_estate_lod1 ADD COLUMN {name} {definition}')
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_lod1_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, house_slug TEXT NOT NULL, revision INTEGER NOT NULL,
            asset_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, published_at REAL NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_streaming_profiles (
            house_slug TEXT PRIMARY KEY, mode TEXT NOT NULL, lod1 INTEGER NOT NULL,
            hide INTEGER NOT NULL, hysteresis INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1)''')


def profile(store, slug):
    validate(slug, DEFAULT)
    with store.connect() as db:
        row = db.execute('SELECT mode,revision FROM real_estate_streaming_profiles WHERE house_slug=?', (slug,)).fetchone()
    return dict(row) if row else {**DEFAULT, 'revision': 0}


def save_profile(store, slug, values, expected_revision):
    if not store.get(slug):
        raise ValueError('register house before configuring Runtime')
    values = validate(slug, values)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('expected profile revision is required')
    house = store.get(slug)
    result = readiness(house, values, house.get('partLod1', {}))
    if values['mode'] == 'lod1':
        blockers = [warning for warning in result['warnings'] if not warning.startswith('Publish all house meshes')]
        if blockers:
            raise ValueError('; '.join(blockers))
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT revision FROM real_estate_streaming_profiles WHERE house_slug=?', (slug,)).fetchone()
        if (old['revision'] if old else 0) != expected_revision:
            raise ValueError('house runtime profile changed; reload before saving')
        db.execute('''INSERT INTO real_estate_streaming_profiles
            (house_slug,mode,lod1,hide,hysteresis,revision) VALUES(?,?,?,?,?,?)
            ON CONFLICT(house_slug) DO UPDATE SET mode=excluded.mode,revision=excluded.revision''',
            (slug, values['mode'], 150, 400, 10, expected_revision+1))
    store.export()
    return profile(store, slug)


def describe(store, slug):
    validate(slug, DEFAULT)
    with store.connect() as db:
        value = db.execute('SELECT * FROM real_estate_lod1 WHERE house_slug=?', (slug,)).fetchone()
    current_full = store._raw_get(slug) if hasattr(store, '_raw_get') else None
    if current_full is None:
        with store.connect() as db:
            current_full = db.execute('SELECT model_sha256 FROM real_estate WHERE slug=?', (slug,)).fetchone()
    full_changed = bool(value and current_full and current_full['model_sha256'] != value['full_source_sha256'])
    return describe_resource(value, store.root, full_changed=full_changed)


def history(store, slug):
    validate(slug, DEFAULT)
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT revision,asset_id,source_sha256,published_at FROM real_estate_lod1_history '
                 'WHERE house_slug=? ORDER BY id DESC LIMIT 25', (slug,))]


def stage(store, slug, source_path, expected_revision):
    validate(slug, DEFAULT)
    if not store.get(slug):
        raise ValueError('register house before staging House LOD1')
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('expected LOD1 revision is required')
    source, digest = inspect_fbx(source_path, f'{slug}_lod1.fbx')
    current = describe(store, slug)
    check_revision(expected_revision, current['revision'], label='house LOD1')
    if current['sourceSha256'] == digest and current['status'] != 'SOURCE_MISSING' and not current['reuse']:
        return current
    # Content-addressed source revisions: a stale UI request must never
    # overwrite the bytes of a previously published LOD1 revision.
    target = store.root / 'assets' / 'source' / 'real-estate' / slug / 'lod' / digest / 'lod1.fbx'
    if target.exists():
        if _sha(target) != digest:
            raise ValueError('LOD1 source checksum collision; review stored source')
    else:
        preserve_source(source, target, target.parent / '_unused_backup.fbx', digest)
    full_sha = store.get(slug)['model_sha256']
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT revision FROM real_estate_lod1 WHERE house_slug=?', (slug,)).fetchone()
        if (old['revision'] if old else 0) != expected_revision:
            raise ValueError('LOD1 changed concurrently')
        db.execute('''INSERT INTO real_estate_lod1(house_slug,source_path,source_sha256,full_source_sha256,revision,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(house_slug) DO UPDATE SET source_path=excluded.source_path,
            source_sha256=excluded.source_sha256,full_source_sha256=excluded.full_source_sha256,
            revision=excluded.revision,updated_at=excluded.updated_at,
            reuse_domain='',reuse_slug='',reuse_revision=0''',
            (slug,target.relative_to(store.root).as_posix(),digest,full_sha,expected_revision+1,time.time()))
    store.export()
    return describe(store, slug)


def publish(store, slug, expected_revision, credentials):
    validate(slug, DEFAULT)
    if not store.get(slug):
        raise ValueError('unknown house type')
    lod = describe(store, slug)
    check_revision(expected_revision, lod['revision'])
    if lod['status'] == 'PUBLISHED':
        return lod
    if lod['status'] not in {'STAGED', 'UPDATE_AVAILABLE'}:
        raise ValueError('register a current LOD1 FBX first')
    path = verified_source(store.root, lod)
    result = publish_geometry(store.root, path, slug, credentials, description='game1 house LOD1')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT revision,source_sha256,full_source_sha256 FROM real_estate_lod1 WHERE house_slug=?', (slug,)).fetchone()
        source = db.execute('SELECT model_sha256 FROM real_estate WHERE slug=?', (slug,)).fetchone()
        if (current is None or source is None or current['revision'] != expected_revision
                or current['source_sha256'] != lod['sourceSha256']
                or source['model_sha256'] != current['full_source_sha256']):
            raise RuntimeError('FULL house or LOD1 changed during publication; inspect Open Cloud asset before retrying')
        db.execute('''UPDATE real_estate_lod1 SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?
            WHERE house_slug=?''', (str(result.asset_id),lod['sourceSha256'],result.moderation_state or '',time.time(),slug))
        db.execute('INSERT INTO real_estate_lod1_history(house_slug,revision,asset_id,source_sha256,published_at) VALUES(?,?,?,?,?)',
            (slug,expected_revision,str(result.asset_id),lod['sourceSha256'],time.time()))
    store.export()
    return describe(store, slug)


def reuse(store, slug: str, source: dict, expected_revision: int) -> dict:
    validate(slug, DEFAULT)
    if not store.get(slug):
        raise ValueError('unknown house type')
    full_sha = store.get(slug)['model_sha256']
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT revision FROM real_estate_lod1 WHERE house_slug=?', (slug,)).fetchone()
        pinned = reuse_values(source, 'house', slug, expected_revision, old['revision'] if old else 0)
        db.execute('''INSERT INTO real_estate_lod1 (
            house_slug,source_path,source_sha256,full_source_sha256,published_sha256,
            asset_id,moderation_state,revision,published_at,updated_at,
            reuse_domain,reuse_slug,reuse_revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(house_slug) DO UPDATE SET
            source_path=excluded.source_path,source_sha256=excluded.source_sha256,
            full_source_sha256=excluded.full_source_sha256,
            published_sha256=excluded.published_sha256,asset_id=excluded.asset_id,
            moderation_state=excluded.moderation_state,revision=excluded.revision,
            updated_at=excluded.updated_at,published_at=excluded.published_at,
            reuse_domain=excluded.reuse_domain,reuse_slug=excluded.reuse_slug,
            reuse_revision=excluded.reuse_revision''',
            (slug,'',pinned['source_sha256'],full_sha,pinned['published_sha256'],
             pinned['asset_id'],pinned['moderation_state'],pinned['revision'],
             time.time(),time.time(),pinned['reuse_domain'],pinned['reuse_slug'],pinned['reuse_revision']))
    store.export()
    return describe(store, slug)
