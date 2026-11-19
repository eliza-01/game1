"""NPC atlas reuse from five asset catalogs; no Open Cloud publishing.

Legacy published images are indexed into the existing AtlasRegistry only when
explicitly selected. The NPC binds the *same* Image ID, never a copied upload.
"""
from __future__ import annotations

from pathlib import Path
import re

from services.texture_atlas_registry import parse_filename


class NpcAtlasSources:
    GROUPS = ('npc', 'monster', 'weapon', 'location_asset', 'real_estate')

    def __init__(self, npcs, monsters, weapons, location_assets, houses):
        self.npcs = npcs
        self.monsters = monsters
        self.weapons = weapons
        self.location_assets = location_assets
        self.houses = houses
        self.atlases = location_assets.atlases

    @staticmethod
    def _entry(kind, slug, name, slot, image_id, source, sha, published_sha, variant_id=0):
        if not str(image_id or '').isdigit() or not sha or sha != published_sha:
            return None
        return {
            'kind':kind, 'slug':slug, 'name':name, 'slot':slot,
            'imageId':str(image_id), 'variantId':int(variant_id or 0),
            'filename':Path(str(source or '')).name,
            'sourcePath':str(source or ''), 'sha256':str(sha),
            'publishedSha256':str(published_sha),
        }

    def _variant_entry(self, kind, slug, name, slot, variant_id):
        variant = self.atlases.get_variant(int(variant_id or 0)) if variant_id else None
        if not variant or not variant['current']:
            return None
        return self._entry(kind, slug, name, slot, variant['published_id'],
            variant['source_path'], variant['source_sha256'], variant['published_sha256'], variant['id'])

    def _sources(self):
        groups = {key:[] for key in self.GROUPS}
        for kind, store in (('npc',self.npcs),('monster',self.monsters),('weapon',self.weapons)):
            for row in store.list():
                slug = row['slug']
                name = row.get('name_en') or slug
                binding = row.get('atlas_binding')
                if binding:
                    source = self._variant_entry(kind,slug,name,'atlas',binding['variant_id'])
                    if source: groups[kind].append(source)
                for option in row.get('atlas_variants') or []:
                    source = self._variant_entry(kind,slug,name,'atlas',option.get('id'))
                    if source: groups[kind].append(source)
                for tex in row.get('textures') or []:
                    source = self._entry(kind,slug,name,str(tex['slot']),tex.get('asset_id'),
                        tex.get('source_path'),tex.get('sha256'),tex.get('published_sha256'))
                    if source: groups[kind].append(source)
        for row in self.location_assets.list():
            slug = row['slug']; name = row.get('name_en') or slug
            source = self._variant_entry('location_asset',slug,name,'atlas',row.get('atlasVariantId'))
            if not source:
                source = self._entry('location_asset',slug,name,'atlas',row.get('texture_asset_id'),
                    row.get('texture_path'),row.get('texture_sha256'),row.get('texture_published_sha256'))
            if source: groups['location_asset'].append(source)
            for option in row.get('atlasVariants') or []:
                candidate = self._variant_entry('location_asset',slug,name,'atlas',option.get('id'))
                if candidate: groups['location_asset'].append(candidate)
        for row in self.houses.list():
            slug = row['slug']; name = row.get('name_en') or slug
            for part, tex in (row.get('textures') or {}).items():
                source = self._variant_entry('real_estate',slug,name,part,tex.get('atlasVariantId'))
                if not source:
                    source = self._entry('real_estate',slug,name,part,tex.get('assetId'),
                        tex.get('path'),tex.get('sha256'),tex.get('publishedSha256'))
                if source: groups['real_estate'].append(source)
                for option in tex.get('atlasOptions') or []:
                    candidate = self._variant_entry('real_estate',slug,name,part,option.get('id'))
                    if candidate: groups['real_estate'].append(candidate)
        # Consumer options may include several independently published resolutions.
        # Never show duplicated active/attached rows for the same model and variant.
        for kind,rows in groups.items():
            unique = {}
            for item in rows:
                unique[(item['slug'],item['slot'],item['variantId'],item['imageId'])] = item
            groups[kind] = sorted(unique.values(),key=lambda row:(row['name'].lower(),row['slot'],row['filename']))
        return groups

    def snapshot(self):
        # Expose publication identity but not absolute local filesystem paths.
        return {'groups':{kind:[{key:item[key] for key in ('kind','slug','name','slot','imageId','variantId','filename')}
                        for item in rows] for kind,rows in self._sources().items()}}

    def connect(self, payload):
        if not isinstance(payload,dict):
            raise ValueError('atlas selection must be an object')
        slug = str(payload.get('npcSlug') or '').strip().lower()
        if not self.npcs.get(slug):
            raise ValueError('register the target NPC first')
        kind = str(payload.get('sourceKind') or '')
        source_slug = str(payload.get('sourceSlug') or '')
        slot = str(payload.get('sourceSlot') or '')
        requested_variant = int(payload.get('variantId') or 0)
        if kind not in self.GROUPS:
            raise ValueError('unknown atlas source category')
        source = next((row for row in self._sources()[kind]
                       if row['slug']==source_slug and row['slot']==slot and row['variantId']==requested_variant),None)
        if source is None:
            raise ValueError('published source atlas no longer exists; refresh the picker')
        if str(payload.get('sourceImageId') or '') != source['imageId']:
            raise ValueError('source published Image ID changed; refresh the picker')
        if source['variantId']:
            variant = self.atlases.get_variant(source['variantId'])
        else:
            # Already-indexed Image IDs need no original local file, no extra
            # Atlas record, and no new upload. Reject conflicting identities.
            indexed = [v for family in self.atlases.catalog() for v in family['variants']
                       if str(v.get('published_id')) == source['imageId']]
            if indexed:
                if len(indexed) != 1 or indexed[0]['source_sha256'] != source['sha256']:
                    raise ValueError('the published Image ID has conflicting atlas metadata')
                variant = indexed[0]
            else:
                original = Path(source['sourcePath']).name
                parsed = parse_filename(original)
                fallback = re.sub(r'[^a-z0-9_]', '_', f'{kind}_{source_slug}_{slot}'.lower())[:90].strip('_')
                variant = self.atlases.index_existing_published_image(
                    source_path=source['sourcePath'],atlas_key=parsed['atlasKey'] if parsed else fallback,
                    published_id=source['imageId'],expected_sha256=source['sha256'])
        if not variant or not variant['current'] or str(variant['published_id']) != source['imageId']:
            raise ValueError('source atlas is no longer the published image')
        return self.npcs.select_atlas(slug, int(variant['id']),
            int(payload.get('expectedRevision') or 0))

    def clear(self, payload):
        if not isinstance(payload,dict):
            raise ValueError('atlas selection must be an object')
        return self.npcs.clear_atlas(str(payload.get('npcSlug') or '').strip().lower())
