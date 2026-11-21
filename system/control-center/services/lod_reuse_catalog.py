"""Published LOD1 reuse catalog and immutable provenance checks.

Both Location Assets and Real Estate consume these same Open Cloud Model IDs.
No Model upload, FBX copy, Studio mutation or recursive reuse is performed.
"""
from __future__ import annotations

import re
from services.model_lod_common import sha256

_SLUG = re.compile(r"[a-z0-9][a-z0-9_]{0,63}\Z")
_DOMAINS = ("location", "house", "house_part")


def _source(stores: dict, domain: str, slug: str):
    if domain not in _DOMAINS or not isinstance(slug, str) or not (
            (_SLUG.fullmatch(slug) if domain != 'house_part' else
             len(slug.split('/')) == 2 and all(_SLUG.fullmatch(bit) for bit in slug.split('/')))):
        raise ValueError("invalid LOD1 library source")
    store = stores.get(domain)
    if store is None:
        raise ValueError("LOD1 library source unavailable")
    if domain == "location":
        from services.location_lod_resource import describe
        if not store._raw_get(slug):
            raise ValueError("LOD1 source asset no longer registered")
        lod = describe(store, slug)
    elif domain == 'house_part':
        from services.house_part_lod_resource import describe
        if '/' not in slug:
            raise ValueError('house part source needs house/part identity')
        house_slug, part = slug.split('/', 1)
        lod = describe(store, house_slug, part)
    else:
        from services.house_lod_resource import describe
        with store.connect() as db:
            exists = db.execute('SELECT 1 FROM real_estate WHERE slug=?', (slug,)).fetchone()
        if not exists:
            raise ValueError("LOD1 source house no longer registered")
        lod = describe(store, slug)
    if domain in ('location', 'house_part') and not lod.get('reuse') and lod.get('sourcePath'):
        # Published revision must still match its registered immutable source.
        candidate = (store.root / lod['sourcePath']).resolve()
        if (not candidate.is_relative_to(store.root) or not candidate.is_file()
                or sha256(candidate) != lod['sourceSha256']):
            raise ValueError('LOD1 source changed on disk; register a new revision')
    if lod['status'] != 'PUBLISHED' or lod.get('reuse'):
        raise ValueError("LOD1 source must be an original, currently published model")
    asset_id = str(lod.get('modelAssetId') or '')
    if not asset_id.isdecimal() or int(asset_id) <= 0:
        raise ValueError("LOD1 source has no valid published Roblox Model ID")
    return lod


def library(stores: dict) -> list[dict]:
    """Only locally registered, currently published original LOD1 revisions."""
    result = []
    for domain in _DOMAINS:
        store = stores.get(domain)
        if store is None:
            continue
        with store.connect() as db:
            if domain == 'house_part':
                names = [r['house_slug']+'/'+r['part_name'] for r in db.execute(
                    "SELECT house_slug,part_name FROM real_estate_part_lod1 WHERE asset_id != '' ORDER BY house_slug,part_name")]
            else:
                table, slug_column = (("location_asset_lod_resources", "asset_slug")
                                      if domain == 'location' else ("real_estate_lod1", "house_slug"))
                names = [r[0] for r in db.execute(
                    f"SELECT {slug_column} FROM {table} WHERE asset_id != '' ORDER BY {slug_column}").fetchall()]
        for slug in names:
            try:
                lod = _source(stores, domain, slug)
            except (ValueError, OSError):
                continue
            result.append({'domain': domain, 'slug': slug, 'revision': lod['revision'],
                           'modelAssetId': lod['modelAssetId']})
    return result


def confirmed_source(stores: dict, domain: str, slug: str, revision: int, asset_id: str):
    if type(revision) is not int or revision <= 0 or not isinstance(asset_id, str):
        raise ValueError('LOD1 source revision and Model ID are required')
    lod = _source(stores, domain, slug)
    if lod['revision'] != revision or lod['modelAssetId'] != asset_id:
        raise ValueError('LOD1 library source changed; refresh selection')
    return {'domain': domain, 'slug': slug, 'revision': revision,
            'modelAssetId': asset_id, 'sourceSha256': lod['sourceSha256'],
            'moderationState': lod['moderationState']}


def selection(body: dict):
    expected = {'sourceDomain', 'sourceSlug', 'sourceRevision', 'sourceModelAssetId', 'expectedRevision'}
    if not isinstance(body, dict) or set(body) != expected:
        raise ValueError('LOD1 reuse requires an exact source and revision')
    if type(body['expectedRevision']) is not int or body['expectedRevision'] < 0:
        raise ValueError('invalid target LOD1 revision')
    return body
