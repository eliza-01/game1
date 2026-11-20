"""House LOD1 is one independent Model Asset per stable house type.

Shares the existing geometry-only Model publisher with Location LOD1. It never
changes a Plot, a house FULL publication, or any Studio instance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time

from services.model_lod_common import inspect_fbx, preserve_source, publish_geometry, sha256
from sqlite_connection import connect as connect_sqlite
from services.house_runtime_profile import validate, readiness, DEFAULT

_MAX_FBX_BYTES = 200 * 1024 * 1024


_sha = sha256


def ensure_schema(store):
    with store.connect() as db:
        existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'real_estate_lod1', 'real_estate_streaming_profiles'}.issubset(existing):
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
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_lod1_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, house_slug TEXT NOT NULL, revision INTEGER NOT NULL,
            asset_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, published_at REAL NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_streaming_profiles (
            house_slug TEXT PRIMARY KEY, mode TEXT NOT NULL, lod1 INTEGER NOT NULL,
            hide INTEGER NOT NULL, hysteresis INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1)''')


def profile(store, slug):
    validate(slug, DEFAULT)
    with store.connect() as db:
        row = db.execute('SELECT mode,lod1,hide,hysteresis,revision FROM real_estate_streaming_profiles WHERE house_slug=?', (slug,)).fetchone()
    return dict(row) if row else {**DEFAULT, 'revision': 0}


def save_profile(store, slug, values, expected_revision):
    if not store.get(slug):
        raise ValueError('register house before configuring Runtime')
    values = validate(slug, values)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('expected profile revision is required')
    lod = describe(store, slug)
    house = store.get(slug)
    result = readiness(house, values, lod)
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
            ON CONFLICT(house_slug) DO UPDATE SET mode=excluded.mode,lod1=excluded.lod1,
            hide=excluded.hide,hysteresis=excluded.hysteresis,revision=excluded.revision''',
            (slug, values['mode'], values['lod1'], values['hide'], values['hysteresis'], expected_revision+1))
    store.export()
    return profile(store, slug)


def describe(store, slug):
    validate(slug, DEFAULT)
    with store.connect() as db:
        value = db.execute('SELECT * FROM real_estate_lod1 WHERE house_slug=?', (slug,)).fetchone()
    if not value:
        return {'revision': 0, 'status': 'NOT_REGISTERED', 'sourcePath': '',
                'sourceSha256': '', 'publishedSha256': '', 'modelAssetId': '', 'moderationState': ''}
    row = dict(value)
    path = (store.root / row['source_path']).resolve()
    available = path.is_relative_to(store.root) and path.is_file() and _sha(path) == row['source_sha256']
    current_full = store._raw_get(slug) if hasattr(store, '_raw_get') else None
    if current_full is None:
        with store.connect() as db:
            current_full = db.execute('SELECT model_sha256 FROM real_estate WHERE slug=?', (slug,)).fetchone()
    full_changed = bool(current_full and current_full['model_sha256'] != row['full_source_sha256'])
    status = ('SOURCE_MISSING' if not available else 'FULL_CHANGED' if full_changed else 'PUBLISHED' if row['asset_id'] and row['source_sha256'] == row['published_sha256']
              else 'UPDATE_AVAILABLE' if row['asset_id'] else 'STAGED')
    return {'revision': row['revision'], 'status': status, 'sourcePath': row['source_path'],
            'sourceSha256': row['source_sha256'], 'publishedSha256': row['published_sha256'],
            'modelAssetId': row['asset_id'], 'moderationState': row['moderation_state']}


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
    if current['revision'] != expected_revision:
        raise ValueError('house LOD1 revision changed; refresh')
    if current['sourceSha256'] == digest and current['status'] != 'SOURCE_MISSING':
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
            revision=excluded.revision,updated_at=excluded.updated_at''',
            (slug,target.relative_to(store.root).as_posix(),digest,full_sha,expected_revision+1,time.time()))
    store.export()
    return describe(store, slug)


def publish(store, slug, expected_revision, credentials):
    validate(slug, DEFAULT)
    if not store.get(slug):
        raise ValueError('unknown house type')
    lod = describe(store, slug)
    if type(expected_revision) is not int or lod['revision'] != expected_revision:
        raise ValueError('LOD1 revision changed; reload')
    if lod['status'] == 'PUBLISHED':
        return lod
    if lod['status'] not in {'STAGED', 'UPDATE_AVAILABLE'}:
        raise ValueError('register a current LOD1 FBX first')
    path = (store.root / lod['sourcePath']).resolve()
    if not path.is_relative_to(store.root) or _sha(path) != lod['sourceSha256']:
        raise ValueError('LOD1 file changed; register again')
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
