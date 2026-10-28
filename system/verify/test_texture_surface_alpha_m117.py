"""M117: source-derived alpha + one binding contract across authoring contexts."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.texture_alpha import texture_uses_alpha, texture_binding
from services.studio_asset_sync import StudioAssetSyncService
from real_estate.studio_sync import RealEstateStudioSync
from location_asset_store import LocationAssetStore


def text(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


class SurfaceAlphaM117Tests(unittest.TestCase):
    def test_nonopaque_png_rgb_opaque_alpha_palette_and_webp(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new('RGB', (2, 2), (100, 50, 40)).save(root / 'rgb.png')
            Image.new('RGBA', (2, 2), (100, 50, 40, 255)).save(root / 'opaque.png')
            rgba = Image.new('RGBA', (2, 2), (100, 50, 40, 255))
            rgba.putpixel((0, 0), (100, 50, 40, 0))
            rgba.save(root / 'alpha.png')
            rgba.save(root / 'alpha.webp', lossless=True)
            pal = Image.new('P', (2, 2))
            pal.putpalette([0, 0, 0, 255, 255, 255] + [0] * 762)
            pal.putpixel((0, 0), 1)
            pal.info['transparency'] = 1
            pal.save(root / 'palette.png')
            self.assertFalse(texture_uses_alpha(root, 'rgb.png'))
            self.assertFalse(texture_uses_alpha(root, 'opaque.png'))
            self.assertTrue(texture_uses_alpha(root, 'alpha.png'))
            self.assertTrue(texture_uses_alpha(root, 'alpha.webp'))
            self.assertTrue(texture_uses_alpha(root, 'palette.png'))
            self.assertIsNone(texture_uses_alpha(root, 'missing.png'))
            self.assertIsNone(texture_uses_alpha(root, '../outside.png'))
            self.assertIsNone(texture_uses_alpha(root, 'missing.xyz'))
            self.assertNotIn('usesAlpha', texture_binding('body', '55', root, 'alpha.png',
                registered_sha256='new', published_sha256='old'))
            # Reused filenames retain the same content-based alpha regardless of slot.
            self.assertTrue(texture_uses_alpha(root, './alpha.png'))
            Image.new('RGBA', (2, 2), (100, 50, 40, 255)).save(root / 'alpha.png')
            self.assertFalse(texture_uses_alpha(root, 'alpha.png'))

    def test_location_reference_metadata_and_no_db_mutation(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            location = LocationAssetStore(root)
            # Source/canonical files omitted in diagnostic dumps, but metadata
            # must distinguish unknown from opaque rather than lying.
            missing = {'slug': 'tree', 'texture_path': 'assets/missing.png',
                       'texture_reference_slug': '', 'destructible': 0}
            result = location._decorate(missing)
            self.assertIsNone(result['textureUsesAlpha'])
            self.assertIn('textureUsesAlpha', text('system/control-center/location_asset_store.py'))
            self.assertIn('textureUsesAlpha', text('src/server/world/EnvironmentAssetVisuals.luau'))
            Image.new('RGBA', (1, 1), (30, 0, 0, 0)).save(root / 'leaf.png')
            owner = {**missing, 'slug': 'owner', 'texture_path': 'leaf.png',
                     'texture_asset_id': '55', 'texture_sha256': 'abc',
                     'texture_published_sha256': 'abc'}
            borrower = {**missing, 'slug': 'borrower', 'texture_reference_slug': 'owner'}
            decorated = location._decorate(borrower, {'owner': owner})
            self.assertEqual(decorated['texture_owner_slug'], 'owner')
            self.assertTrue(decorated['textureUsesAlpha'])
            location.export()  # generation is repeatable, does not mutate the DB
            self.assertIn('textureUsesAlpha', text('system/control-center/location_asset_store.py'))

    def test_location_generated_registry_preserves_published_alpha(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.png'
            Image.new('RGBA', (2, 1), (10, 30, 30, 100)).save(source)
            fake_fbx = root / 'house.fbx'
            fake_fbx.write_bytes(b'ignored-fbx-in-store-only-test')
            store = LocationAssetStore(root)
            store.register({'nameEn': 'Cutout Test', 'category': 'building',
                            'modelSourcePath': str(fake_fbx), 'textureSourcePath': str(source)})
            initial = store.get('cutout_test')
            self.assertIsNone(initial['textureUsesAlpha'])  # not published yet
            with store.connect() as connection:
                connection.execute('UPDATE location_assets SET texture_asset_id=?, texture_published_sha256=? WHERE slug=?',
                                   ('1234', initial['texture_sha256'], 'cutout_test'))
            store.export()
            published = store.get('cutout_test')
            self.assertTrue(published['textureUsesAlpha'])
            manifest = json.loads((root / 'assets/manifests/location-assets.json').read_text(encoding='utf-8'))
            self.assertTrue(manifest['items'][0]['textureUsesAlpha'])
            registry = (root / 'src/shared/world/LocationAssetRegistry.luau').read_text(encoding='utf-8')
            self.assertIn('textureUsesAlpha = true', registry)
            with store.connect() as connection:
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(connection.execute('SELECT texture_asset_id FROM location_assets').fetchone()[0], '1234')

    def test_sync_weapons_monsters_npcs_and_legacy_unknown(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new('RGBA', (2, 2), (80, 40, 20, 100)).save(root / 'cutout.png')
            entries = [{'slot': 'body', 'asset_id': '123', 'source_path': 'cutout.png'},
                       {'slot': 'unknown', 'asset_id': '456', 'source_path': 'missing.png'}]
            item = {'slug': 'sample', 'model_asset_id': '789', 'textures': entries,
                    'skeleton_json': '{"bones":[]}', 'storage_type': 'swords'}
            class Store:
                def __init__(self): self.root = root
                def get(self, _slug): return item
            one = Store()
            sent = []
            def load(*args, **kwargs):
                sent.append(kwargs['metadata'])
                return {'monsterStats': {'textures': {'applied': 2}},
                        'rigStats': {'baseParts': 1, 'bones': 1, 'boneNames': ['root']}}
            service = StudioAssetSyncService(None, one, one, one, load)
            service.sync_weapon_to_studio('sample')
            self.assertEqual([True, None], [t.get('usesAlpha') for t in sent[-1]['textures']])
            for kind in ('monster', 'npc'):
                service.sync_monster_to_studio('sample', kind=kind)
                self.assertEqual([True, None], [t.get('usesAlpha') for t in sent[-1]['textures']])

    def test_estate_per_slot_metadata(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new('RGBA', (1, 1), (10, 10, 10, 120)).save(root / 'house.png')
            class Store:
                def __init__(self): self.root = root
                def get(self, _slug):
                    return {'slug': 'one', 'status': 'PUBLISHED', 'skeleton': {
                        'meshes': [{'name': 'house', 'bones': []}]},
                        'textures': {'house': {'path': 'house.png', 'assetId': '33'}},
                        'rigAssets': {'house': {'assetId': '44'}}, 'house_level': 1,
                        'purchase_price': 1, 'min_level': 1, 'sale_price': 1}
            observed = []
            def load(*args, **kwargs):
                observed.append(kwargs['metadata'])
                return {'realEstateStats': {'bonesValidated': True, 'rigsValidated': 1, 'texturesApplied': 1}}
            RealEstateStudioSync(Store(), load).sync('one')
            self.assertEqual(observed[0]['textures'], [{'slot': 'house', 'assetId': '33', 'usesAlpha': True}])

    def test_studio_contracts_no_legacy_direct_texture_assignments(self):
        studio = text('system/studio-plugin/modules/StudioTextureAppearance.luau')
        self.assertIn('surface.ColorMap = uri', studio)
        self.assertIn('surface.AlphaMode = desiredMode', studio)
        self.assertIn('mesh.TextureID = uri', studio)
        self.assertIn('not modeKnown or surface.AlphaMode == desiredMode', studio)
        self.assertIn('Enum.AlphaMode.Transparency', studio)
        self.assertIn('Enum.AlphaMode.Overlay', studio)
        for file in ['StudioModelLoadCommands', 'StudioRealEstateModel', 'DecoAssetLoader', 'DecoPlacedAssetSync']:
            contents = text('system/studio-plugin/modules/' + file + '.luau')
            self.assertIn('StudioTextureAppearance.Apply(', contents, file)
            self.assertNotIn('.TextureID = "rbxassetid://"', contents, file)
        self.assertIn('StudioTextureAppearance', text('system/studio-plugin/plugin.project.json'))
        runtime = text('src/server/world/EnvironmentAssetVisuals.luau')
        self.assertIn('mesh.TextureID = uri', runtime)
        self.assertIn('FindFirstChildOfClass("SurfaceAppearance")', runtime)
        self.assertNotIn('surface.ColorMap = uri', runtime)
        self.assertNotIn('surface.AlphaMode = targetMode', runtime)


if __name__ == '__main__':
    unittest.main()
