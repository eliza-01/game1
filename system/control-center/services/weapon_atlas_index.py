"""Opt-in, metadata-only migration of existing published weapon/arrow images.

No Open Cloud calls and no Studio Sync. A single historical Image ID may
become the active shared binding, retaining precisely the same Roblox Image ID.
The shared AtlasRegistry is the sole writer of new atlas variants.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from services.texture_atlas_registry import parse_filename


def index_existing_textures(root: Path, atlases, *, kind_filter: str = '', slug_filter: str = '') -> dict:
    db = sqlite3.connect(root / '.control-center/game1.db')
    db.row_factory = sqlite3.Row
    try:
        entries = []
        for r in db.execute('''SELECT weapon_slug,slot,source_path,sha256,asset_id,published_sha256
            FROM weapon_textures ORDER BY weapon_slug,slot'''):
            row = dict(r)
            entries.append(('weapon', row['weapon_slug'],
                            f"weapon_{row['weapon_slug']}_{row['slot']}", row['source_path'],
                            row['asset_id'], row['sha256'], row['published_sha256']))
        for r in db.execute('''SELECT slug,texture_path,texture_sha256,texture_asset_id,texture_published_sha256
            FROM arrow_assets ORDER BY slug'''):
            row = dict(r)
            entries.append(('arrow', row['slug'], f"arrow_{row['slug']}", row['texture_path'],
                            row['texture_asset_id'], row['texture_sha256'], row['texture_published_sha256']))
    finally:
        db.close()
    result = {'indexed':[], 'attached':[], 'selected':[], 'skipped':[], 'studioSyncPerformed':False,
              'cloudPublicationPerformed':False}
    # One previous image means one unambiguous active variant. Multiple local
    # slots are connected as choices, never silently reduced to one texture.
    counts = {}
    for kind, slug, *_ in entries:
        counts[(kind, slug)] = counts.get((kind, slug), 0) + 1
    for kind, slug, raw_key, source, image_id, sha, published_sha in entries:
        if (kind_filter and kind != kind_filter) or (slug_filter and slug != slug_filter):
            continue
        # Canonically named sources must retain their atlas family identity;
        # legacy names get a stable owner-scoped fallback to avoid collisions.
        parsed = parse_filename(Path(source).name) if source else None
        key = parsed['atlasKey'] if parsed else re.sub(r'[^a-z0-9_]', '_',raw_key.lower())[:91]
        if not source or not image_id or not sha or sha != published_sha:
            result['skipped'].append({'key':key,'reason':'no current published image'})
            continue
        try:
            variant = atlases.index_existing_published_image(
                source_path=source,atlas_key=key,published_id=str(image_id),
                expected_sha256=str(sha))
            if str(variant['published_id']) != str(image_id):
                raise ValueError('indexed atlas does not match original Image Asset ID')
            atlases.attach(kind, slug, int(variant['id']))
            result['attached'].append({'kind':kind, 'slug':slug, 'variantId':variant['id']})
            # This only records the image that is ALREADY active in the legacy
            # asset. Do not select arbitrarily when there are several slots.
            if counts[(kind, slug)] == 1 and not atlases.binding(kind, slug):
                atlases.bind(kind, slug, int(variant['id']), expected_revision=0)
                result['selected'].append({'kind':kind, 'slug':slug, 'imageId':str(image_id)})
            result['indexed'].append({'key':key,'id':variant['id'],
                                      'imageId':variant['published_id'],
                                      'resolution':variant['resolution']})
        except (ValueError, OSError, sqlite3.Error) as error:
            result['skipped'].append({'key':key,'reason':str(error)})
    return result
