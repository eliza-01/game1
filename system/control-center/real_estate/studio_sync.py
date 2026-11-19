"""Sync published Real Estate templates using the existing Game1Bridge model-load command."""
from pathlib import Path
from .contracts import present_parts
from .rig_publication_policy import publish_bones_for_mesh
from .rig_publication_policy import primary_part, carrier_bones
from services.texture_alpha import texture_binding

# Only the server validates Studio protocol compatibility. The browser renders
# a successful response and must not maintain its own competing version gate.
REQUIRED_PLACED_SYNC_VERSION = 3


class RealEstateStudioSync:
    def __init__(self, store, load_model):
        self.store = store
        self.load_model = load_model

    def sync(self, slug: str, *, part: str | None = None) -> dict:
        row = self.store.get(slug)
        if not row:
            raise ValueError('unknown registered house')
        if part is not None and part not in row['meshParts']:
            raise ValueError('unknown mesh for targeted Studio Sync')
        if part is None and row['status'] != 'PUBLISHED':
            raise ValueError('publish all changed house assets before syncing to Studio')
        rigs = row.get('rigAssets') or {}
        parts = present_parts(row['skeleton'])
        if part is not None and (not rigs.get(part, {}).get('assetId') or
                rigs[part].get('publishedSha256') != row['rigPublicationHashes'][part]):
            raise ValueError('publish the changed mesh Model Asset before targeted Studio Sync')
        if not all(rigs.get(p, {}).get('assetId') and
                   rigs[p].get('publishedSha256') == row['rigPublicationHashes'][p]
                   for p in ('rig_carrier', *parts)):
            raise ValueError('Republish independent rig_carrier and all changed visual Model Assets before Studio Sync')
        primary = 'rig_carrier'
        # A targeted update must rebuild the shared carrier assembly, not
        # swap one MeshPart and leave orphaned connections.
        part = None
        visual_options = row.get('meshOptions') or {}
        metadata = {
            'primaryPart': primary,
            'expectedCarrierBones': [bone['name'] for bone in carrier_bones(row['skeleton'])],
            # Project-authored pivot is independent of whether a visual mesh is named 'house'.
            'houseAuthoringVersion': 4,
            'doorParts': {
                mesh['name']: True for mesh in row['skeleton']['meshes']
                if 'door_01_hinge_socket' in (mesh.get('influencedBones') or [])
            },
            'syncPart': '',
            'houseSlug': row['slug'],
            'rigAssetIds': {part: str(rigs[part]['assetId']) for part in ('rig_carrier', *parts)},
            'doorModelAssetId': rigs.get('door', {}).get('assetId', ''),  # legacy Studio integration
            'houseLevel': row['house_level'],
            'purchasePrice': row['purchase_price'],
            'minLevel': row['min_level'],
            'salePrice': row['sale_price'],
            'expectedMeshes': {
                part['name']: [bone['name'] for bone in publish_bones_for_mesh(part)]
                for part in row['skeleton']['meshes']
            },
            # These offsets belong to the authored FBX revision. They are
            # omitted for legacy/standalone mesh revisions lacking a house frame.
            'authoredPlacements': {
                mesh['name']: mesh['authoredPlacement']
                for mesh in row['skeleton']['meshes']
                if isinstance(mesh.get('authoredPlacement'), dict)
            },
            'meshOptions': visual_options,
            'textures': [
                texture_binding(name, data['assetId'], getattr(self.store, 'root', None),
                    data.get('path') or '',
                    alpha_enabled=visual_options.get(name, {}).get('alphaEnabled', False))
                for name, data in row['textures'].items()
                if visual_options.get(name, {}).get('appearanceMode', 'atlas') == 'atlas' and data.get('assetId')
            ],
        }
        result = self.load_model(
            str(rigs[primary]['assetId']), ['real_estate', row['slug'], 'model'],
            wrapper_name=row['slug'], placement_mode='real-estate-rig', metadata=metadata,
        )
        stats = result.get('realEstateStats')
        actual_version = stats.get('placedSyncVersion') if isinstance(stats, dict) else None
        if actual_version != REQUIRED_PLACED_SYNC_VERSION:
            raise ValueError(
                'Game1Bridge Real Estate placed-sync protocol mismatch: '
                f'expected v{REQUIRED_PLACED_SYNC_VERSION}, got {actual_version!r}. '
                'Install the current Studio plugin and restart Roblox Studio.'
            )
        if stats.get('bonesValidated') is not True:
            raise ValueError('Studio did not confirm all published Real Estate mesh rigs')
        if stats.get('rigsValidated') != len(parts) + 1:
            raise ValueError('Studio failed to validate the expected Real Estate rigs')
        if stats.get('texturesApplied') != sum(
                visual_options.get(p, {}).get('appearanceMode', 'atlas') == 'atlas' for p in parts):
            raise ValueError('Studio did not apply the expected published house textures')
        # Acknowledgement belongs to this consumer, not to the atlas itself;
        # one house sync must not mark another house as synchronized.
        for part_name in parts:
            texture = row['textures'][part_name]
            if texture.get('atlasVariantId') and texture.get('atlasBindingRevision'):
                self.store.atlases.mark_synced('real_estate', f'{slug}:{part_name}',
                    texture['atlasBindingRevision'])
        return {'realEstate': self.store.get(slug), 'studio': result}
