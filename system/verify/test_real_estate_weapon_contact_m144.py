"""M144: collider authoring flag is distinct from physical collision and image publishing."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore, mesh_options
from test_real_estate_m107 import skeleton


class RealEstateWeaponContactM144(unittest.TestCase):
    def test_legacy_defaults_and_strict_boolean(self):
        options = mesh_options(['house', 'door', 'col_mesh', 'house_col'], {})
        self.assertFalse(options['col_mesh']['destructible'])
        self.assertFalse(options['house_col']['destructible'])
        self.assertFalse(options['col_mesh']['noCollide'])
        self.assertTrue(options['house']['noCollide'])
        self.assertFalse(options['house']['destructible'])
        choices = mesh_options(['col_mesh', 'house'], {
            'col_mesh': {'destructible': True, 'noCollide': False},
            'house': {'destructible': True},
        })
        self.assertTrue(choices['col_mesh']['destructible'])
        self.assertFalse(choices['house']['destructible'])
        self.assertFalse(mesh_options(['col_mesh'], {'col_mesh': {'destructible': 'false'}})['col_mesh']['destructible'])
        self.assertFalse(mesh_options(['col_mesh'], {'col_mesh': {'destructible': 1}})['col_mesh']['destructible'])

    def test_destructible_saved_and_reloaded_without_republication(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'house_level4_01.fbx'
            source.write_bytes(b'test model')
            texture = root/'house.png'
            texture.write_bytes(b'fake-image')
            store = RealEstateStore(root)
            analysis = skeleton()
            analysis['meshes'].append({'name': 'col_mesh', 'armature': '',
                'vertices': 24, 'bones': [], 'influencedBones': []})
            with mock.patch('real_estate.store.inspect', return_value=analysis):
                first = store.register({'houseType':'house', 'level':4, 'variant':'01',
                    'sourcePath':str(source), 'textures':{'house':str(texture)},
                    'textureReferences':{'door':'mesh:house'}})
            self.assertFalse(first['meshOptions']['col_mesh']['destructible'])
            changed = store.register({'houseType':'house', 'level':4, 'variant':'01',
                'sourcePath':'', 'existingSlug':first['slug'],
                'textures':{'house':first['textures']['house']['path']},
                'textureReferences':{'door':'mesh:house'},
                'meshOptions':{'col_mesh':{'destructible':True}}})
            self.assertTrue(changed['meshOptions']['col_mesh']['destructible'])
            self.assertFalse(changed['meshOptions']['col_mesh']['noCollide'])
            self.assertEqual(changed['model_sha256'], first['model_sha256'])
            self.assertEqual(changed['rigAssets'], first['rigAssets'])
            self.assertEqual(changed['textures']['house']['assetId'], first['textures']['house']['assetId'])
            reloaded = RealEstateStore(root).get(first['slug'])
            self.assertTrue(reloaded['meshOptions']['col_mesh']['destructible'])

    def test_policy_does_not_change_physics_when_destructible(self):
        studio = (ROOT/'system/studio-plugin/modules/StudioRealEstateCollisionPolicy.luau').read_text(encoding='utf-8')
        self.assertIn('"Game1RealEstateDestructible"', studio)
        self.assertIn('settings.destructible == true', studio)
        self.assertIn('CollectionService:AddTag(mesh, COLLIDER_TAG)', studio)
        self.assertIn('mesh.CanCollide = true', studio)
        self.assertIn('mesh.CanQuery = true', studio)
        self.assertIn('mesh.Transparency = 1', studio)
        self.assertIn('Game1RealEstatePhysicsOnly', studio)

    def test_weapon_blocking_uses_tagged_authoring_without_full_workspace_scan_each_swing(self):
        index = (ROOT/'src/server/combat/RealEstateEnvironmentTargets.luau').read_text(encoding='utf-8')
        bounce = (ROOT/'src/server/combat/WeaponEnvironmentCollision.luau').read_text(encoding='utf-8')
        self.assertIn('CollectionService:GetTagged(TAG)', index)
        self.assertIn('CollectionService:GetInstanceAddedSignal(TAG)', index)
        self.assertIn('part:GetAttribute("Game1RealEstateDestructible") ~= true', index)
        self.assertIn('part.CanQuery', index)
        self.assertIn('function Targets.GetBlockingSnapshot()', index)
        self.assertIn('function Targets.ResolvePart(', index)
        self.assertIn('RealEstateEnvironmentTargets.GetBlockingSnapshot()', bounce)
        self.assertIn('RealEstateEnvironmentTargets.ResolvePart(part)', bounce)
        self.assertIn('EnvironmentAssetService.GetRegisteredSnapshot()', bounce)
        self.assertIn('EnvironmentAssetService.ResolvePart(part)', bounce)

    def test_checkbox_badge_and_persistence_contract(self):
        ui=(ROOT/'system/control-center/static/real-estate.js').read_text(encoding='utf-8')
        self.assertIn('real-estate-destructible-', ui)
        self.assertIn('destructible:realEstateIsCollider(part)', ui)
        self.assertIn('Destructible · no bounce', ui)
        self.assertIn('Solid · bounce', ui)
        sync=(ROOT/'system/control-center/real_estate/studio_sync.py').read_text(encoding='utf-8')
        self.assertIn("'meshOptions': row.get('meshOptions') or {}", sync)

if __name__ == '__main__': unittest.main()
