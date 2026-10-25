"""Sync published Real Estate templates using the existing Game1Bridge model-load command."""
from pathlib import Path
from .contracts import present_parts
from services.texture_alpha import texture_binding


class RealEstateStudioSync:
    def __init__(self, store, load_model):
        self.store = store
        self.load_model = load_model

    def sync(self, slug: str) -> dict:
        row = self.store.get(slug)
        if not row:
            raise ValueError('unknown registered house')
        if row['status'] != 'PUBLISHED':
            raise ValueError('publish all changed house assets before syncing to Studio')
        rigs = row.get('rigAssets') or {}
        parts = present_parts(row['skeleton'])
        if not all(rigs.get(part, {}).get('assetId') for part in parts):
            raise ValueError('publish each present Real Estate Model Asset before Studio Sync')
        metadata = {
            'houseSlug': row['slug'],
            'rigAssetIds': {part: str(rigs[part]['assetId']) for part in parts},
            'doorModelAssetId': rigs.get('door', {}).get('assetId', ''),  # legacy Studio integration
            'houseLevel': row['house_level'],
            'purchasePrice': row['purchase_price'],
            'minLevel': row['min_level'],
            'salePrice': row['sale_price'],
            'expectedMeshes': {
                part['name']: [bone['name'] for bone in part['bones']]
                for part in row['skeleton']['meshes']
            },
            'textures': [
                texture_binding(name, data['assetId'], getattr(self.store, 'root', None), data.get('path') or '')
                for name, data in row['textures'].items()
            ],
        }
        result = self.load_model(
            str(rigs['house']['assetId']), ['real_estate', row['slug'], 'model'],
            wrapper_name=row['slug'], placement_mode='real-estate-rig', metadata=metadata,
        )
        if result.get('realEstateStats', {}).get('bonesValidated') is not True:
            raise ValueError('Studio did not confirm all published Real Estate mesh rigs')
        if result.get('realEstateStats', {}).get('rigsValidated') != len(parts):
            raise ValueError('Studio failed to validate the expected Real Estate rigs')
        if result.get('realEstateStats', {}).get('texturesApplied') != len(parts):
            raise ValueError('Studio did not apply the expected published house textures')
        # Acknowledgement belongs to this consumer, not to the atlas itself;
        # one house sync must not mark another house as synchronized.
        for part in parts:
            texture = row['textures'][part]
            if texture.get('atlasVariantId') and texture.get('atlasBindingRevision'):
                self.store.atlases.mark_synced('real_estate', f'{slug}:{part}',
                    texture['atlasBindingRevision'])
        return {'realEstate': self.store.get(slug), 'studio': result}
