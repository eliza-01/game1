"""Transactional Location Asset identity rename, separate from FBX/Atlas publication.

A slug is a mutable authoring label. Published Roblox IDs and physical FBX source
paths are immutable references and are never renamed or republished here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import time

from sqlite_connection import connect as connect_sqlite
from services.location_asset_taxonomy import surface_material

_SLUG = re.compile(r'[a-z0-9][a-z0-9_]{0,63}\Z')
_CONSUMER_TABLES = ('texture_atlas_bindings', 'texture_atlas_consumer_options',
                    'texture_atlas_legacy_publications')


def aliases(store, slug: str) -> list[str]:
    with store.connect() as db:
        return [row['old_slug'] for row in db.execute(
            'SELECT old_slug FROM location_asset_slug_aliases WHERE current_slug=? ORDER BY old_slug',
            (slug,)).fetchall()]


def rename(store, old_slug: str, payload: dict) -> dict:
    old_slug = str(old_slug or '').strip().lower()
    new_slug = str(payload.get('slug') or '').strip().lower()
    if not _SLUG.fullmatch(old_slug) or not _SLUG.fullmatch(new_slug):
        raise ValueError('slug must contain only lowercase latin letters, digits and underscores (max 64)')
    if new_slug.startswith('col_') or '_col_' in new_slug or new_slug.endswith('_col'):
        raise ValueError('slug conflicts with reserved MeshPart collider naming policy')
    if not isinstance(payload.get('nameEn'), str) or not 0 < len(payload['nameEn'].strip()) <= 120:
        raise ValueError('Location Asset name must be 1..120 characters')
    name = payload['nameEn'].strip()
    category = str(payload.get('category') or '').strip().lower()
    if category not in store.options_category_ids():
        raise ValueError('invalid Location Asset category')
    if type(payload.get('destructible')) is not bool:
        raise ValueError('destructible must be boolean')
    expected = payload.get('expectedRevision')
    if type(expected) is not int or expected < 1:
        raise ValueError('expectedRevision is required for a rename')
    # A physical backup is prepared BEFORE the first identity mutation. Keep it
    # outside the transaction; it can be restored if a later export fails.
    backup_dir = store.runtime / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = backup_dir / f'location_identity_before_m242_{stamp}.sqlite'
    with store.connect() as source, connect_sqlite(backup) as target:
        source.backup(target)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT revision,surface_material FROM location_assets WHERE slug=?', (old_slug,)).fetchone()
        if current is None or current['revision'] != expected:
            raise ValueError('Location Asset changed since Edit opened; refresh before saving')
        existing = db.execute('SELECT 1 FROM location_assets WHERE slug=?', (new_slug,)).fetchone()
        alias = db.execute('SELECT current_slug FROM location_asset_slug_aliases WHERE old_slug=?',
                           (new_slug,)).fetchone()
        if new_slug != old_slug and (existing is not None or alias is not None):
            raise ValueError('new slug is already registered or reserved by an earlier rename')
        material = surface_material(payload.get('surfaceMaterial',current['surface_material']))
        now = time.time()
        db.execute('UPDATE location_assets SET slug=?,name_en=?,category=?,destructible=?,surface_material=?, '
                   'revision=revision+1,updated_at=? WHERE slug=?',
                   (new_slug,name,category,1 if payload['destructible'] else 0,material,now,old_slug))
        if old_slug != new_slug:
            for table in ('location_asset_publications', 'location_asset_mesh_id_inventory', 'location_asset_rig_manifests', 'location_asset_collision_blueprints'):
                db.execute(f'UPDATE {table} SET asset_slug=? WHERE asset_slug=?', (new_slug, old_slug))
            for table in _CONSUMER_TABLES:
                if db.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?',
                              (table,)).fetchone():
                    db.execute(f'UPDATE {table} SET consumer_id=? WHERE consumer_type=? AND consumer_id=?',
                               (new_slug, 'location_asset', old_slug))
            db.execute('UPDATE location_asset_slug_aliases SET current_slug=? WHERE current_slug=?',
                       (new_slug,old_slug))
            db.execute('INSERT INTO location_asset_slug_aliases(old_slug,current_slug,renamed_at) '
                       'VALUES(?,?,?)', (old_slug,new_slug,now))
    store.export()
    result = store.get(new_slug)
    if result is None:
        raise RuntimeError('Location Asset renamed but cannot be reloaded; restore SQLite backup')
    result['previousSlug'] = old_slug
    result['identityBackup'] = backup.relative_to(store.root).as_posix()
    return result
