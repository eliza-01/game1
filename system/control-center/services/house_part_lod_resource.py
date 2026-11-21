"""Per-MeshPart house LOD1 resources using the one shared Model LOD publisher.

A house is not an LOD model: wall, roof, chimney, etc. each pin an immutable
published Model ID. Their material/atlas/color belongs to the house's FULL
visual descriptor, never to the shared geometry prototype.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import time

from services.model_lod_common import (check_revision, describe_resource,
    inspect_fbx, preserve_source, publish_geometry, reuse_values, verified_source)
from sqlite_connection import connect as connect_sqlite
from real_estate.contracts import HOUSE_NAME

_PART = re.compile(r'[a-zA-Z0-9_]{1,100}\Z')


def _check(store, slug: str, part: str) -> dict:
    if not isinstance(slug, str) or not HOUSE_NAME.fullmatch(slug) or not isinstance(part, str) or not _PART.fullmatch(part):
        raise ValueError('invalid house or visual MeshPart')
    house = store.get(slug)
    if not house or part not in house['meshParts']:
        raise ValueError('house MeshPart is not present in current FULL model')
    return house


def ensure_schema(store) -> None:
    with store.connect() as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='real_estate_part_lod1'").fetchone()
        if not exists:
            backup_dir = store.root / '.control-center' / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            target = backup_dir / ('real_estate_part_lod_pre_m412_' +
                datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
            with connect_sqlite(target) as backup:
                db.backup(backup)
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_part_lod1 (
            house_slug TEXT NOT NULL, part_name TEXT NOT NULL,
            source_path TEXT NOT NULL DEFAULT '', source_sha256 TEXT NOT NULL DEFAULT '',
            full_source_sha256 TEXT NOT NULL DEFAULT '', published_sha256 TEXT NOT NULL DEFAULT '',
            asset_id TEXT NOT NULL DEFAULT '', moderation_state TEXT NOT NULL DEFAULT '',
            revision INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL DEFAULT 0,
            published_at REAL, reuse_domain TEXT NOT NULL DEFAULT '',
            reuse_slug TEXT NOT NULL DEFAULT '', reuse_revision INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(house_slug,part_name))''')
        db.execute('''CREATE TABLE IF NOT EXISTS real_estate_part_lod1_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, house_slug TEXT NOT NULL,
            part_name TEXT NOT NULL, revision INTEGER NOT NULL,
            asset_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            published_at REAL NOT NULL)''')


def describe_all(store, slug: str, parts: list[str], source_hashes: dict) -> dict:
    with store.connect() as db:
        rows = {r['part_name']:r for r in db.execute('SELECT * FROM real_estate_part_lod1 WHERE house_slug=?', (slug,))}
    return {part: describe_resource(rows.get(part), store.root,
        full_changed=bool(rows.get(part) and rows[part]['full_source_sha256'] != source_hashes.get(part)))
        for part in parts}


def describe(store, slug: str, part: str) -> dict:
    house = _check(store, slug, part)
    return house['partLod1'][part]


def stage(store, slug: str, part: str, path: str, expected: int) -> dict:
    house = _check(store,slug,part)
    # A part's FBX may use a different asset slug, but it must unambiguously
    # match the part being authored and cannot be a random source file.
    source, digest = inspect_fbx(path, f'{slug}_{part}_lod1.fbx')
    current = house['partLod1'][part]
    check_revision(expected, current['revision'], label='house part LOD1')
    if current['sourceSha256'] == digest and current['status'] != 'SOURCE_MISSING' and not current['reuse']:
        return current
    target = store.root / 'assets' / 'source' / 'real-estate' / slug / 'lod' / part / digest / 'lod1.fbx'
    preserve_source(source, target, target.parent / '_unused_backup.fbx', digest)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT revision FROM real_estate_part_lod1 WHERE house_slug=? AND part_name=?', (slug,part)).fetchone()
        check_revision(expected, old['revision'] if old else 0)
        db.execute('''INSERT INTO real_estate_part_lod1 (
            house_slug,part_name,source_path,source_sha256,full_source_sha256,
            revision,updated_at) VALUES (?,?,?,?,?,?,?) ON CONFLICT(house_slug,part_name)
            DO UPDATE SET source_path=excluded.source_path,source_sha256=excluded.source_sha256,
            full_source_sha256=excluded.full_source_sha256,revision=excluded.revision,
            updated_at=excluded.updated_at,reuse_domain='',reuse_slug='',reuse_revision=0''',
            (slug,part,target.relative_to(store.root).as_posix(),digest,
             house['rigSourceHashes'][part],expected+1,time.time()))
    store.export()
    return describe(store,slug,part)


def publish(store, slug: str, part: str, expected: int, credentials: dict) -> dict:
    house=_check(store,slug,part)
    current=house['partLod1'][part]
    check_revision(expected,current['revision'])
    if current['status']=='PUBLISHED':return current
    if current['status'] not in ('STAGED','UPDATE_AVAILABLE'):
        raise ValueError('stage a current per-part LOD1 FBX first')
    source=verified_source(store.root,current)
    result=publish_geometry(store.root,source,slug+'_'+part,credentials,description='game1 house part LOD1')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT revision,source_sha256,full_source_sha256 FROM real_estate_part_lod1 WHERE house_slug=? AND part_name=?',(slug,part)).fetchone()
        if not old or old['revision']!=expected or old['source_sha256']!=current['sourceSha256'] or old['full_source_sha256']!=house['rigSourceHashes'][part]:
            raise RuntimeError('house part changed during Open Cloud publication; inspect result before retrying')
        db.execute('''UPDATE real_estate_part_lod1 SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?
            WHERE house_slug=? AND part_name=?''',
            (str(result.asset_id),current['sourceSha256'],result.moderation_state or '',time.time(),slug,part))
        db.execute('''INSERT INTO real_estate_part_lod1_history(house_slug,part_name,revision,asset_id,source_sha256,published_at)
            VALUES(?,?,?,?,?,?)''',(slug,part,expected,str(result.asset_id),current['sourceSha256'],time.time()))
    store.export()
    return describe(store,slug,part)


def reuse(store, slug: str, part: str, source: dict, expected: int) -> dict:
    house=_check(store,slug,part)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT revision FROM real_estate_part_lod1 WHERE house_slug=? AND part_name=?',(slug,part)).fetchone()
        pinned=reuse_values(source,'house_part',slug+'/'+part,expected,old['revision'] if old else 0)
        db.execute('''INSERT INTO real_estate_part_lod1 (
            house_slug,part_name,source_path,source_sha256,full_source_sha256,
            published_sha256,asset_id,moderation_state,revision,published_at,
            updated_at,reuse_domain,reuse_slug,reuse_revision)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(house_slug,part_name) DO UPDATE SET
            source_path=excluded.source_path,source_sha256=excluded.source_sha256,
            full_source_sha256=excluded.full_source_sha256,
            published_sha256=excluded.published_sha256,asset_id=excluded.asset_id,
            moderation_state=excluded.moderation_state,revision=excluded.revision,
            published_at=excluded.published_at,updated_at=excluded.updated_at,
            reuse_domain=excluded.reuse_domain,reuse_slug=excluded.reuse_slug,
            reuse_revision=excluded.reuse_revision''',
            (slug,part,'',pinned['source_sha256'],house['rigSourceHashes'][part],
             pinned['published_sha256'],pinned['asset_id'],pinned['moderation_state'],
             pinned['revision'],time.time(),time.time(),pinned['reuse_domain'],
             pinned['reuse_slug'],pinned['reuse_revision']))
    store.export()
    return describe(store,slug,part)
