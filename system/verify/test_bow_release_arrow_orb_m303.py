"""M303: arrow publication registry, release policy and bone-effect contracts.

Structural checks are not a Roblox physics/Studio Play simulation.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from arrow_store import ArrowStore


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class ArrowStoreTests(unittest.TestCase):
    def test_register_export_validate_and_activate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fb = root / 'bolt.fbx'
            fb.write_bytes(b'; FBX 7.4.0 mock -- no Cloud publish')
            store = ArrowStore(root)
            self.assertEqual(store.list(), [])
            item = store.register({'name':'Test arrow', 'slug':'test_arrow', 'speed':180,
                                   'forwardAxis':'+X', 'modelSourcePath':str(fb)})
            self.assertEqual(item['status'], 'LOCAL_ONLY')
            self.assertEqual(item['speed'], 180)
            with self.assertRaisesRegex(ValueError, 'publish'):
                store.activate('test_arrow')
            with self.assertRaisesRegex(ValueError, 'speed'):
                store.register({'name':'Test arrow','slug':'test_arrow','speed':999})
            with self.assertRaisesRegex(ValueError, 'axis'):
                store.register({'name':'Test arrow','slug':'test_arrow','forwardAxis':'BAD'})
            source_path = root / item['source_path']
            self.assertEqual(source_path.read_bytes(),fb.read_bytes())
            with store.connect() as conn:
                conn.execute('UPDATE arrow_assets SET model_asset_id=?, published_sha256=? WHERE slug=?',
                             ('123456789',item['sha256'],'test_arrow'))
            self.assertEqual(store.get('test_arrow')['status'], 'PUBLISHED')
            store.activate('test_arrow')
            registry = read_reg(root / 'assets/manifests/arrows.json')
            self.assertEqual(registry['activeArrowSlug'],'test_arrow')
            self.assertIn('"speed":180.0', (root / 'src/shared/weapon/ArrowRegistry.luau').read_text())
            self.assertIn('ServerStorage.arrows.test_arrow.model.test_arrow',
                          (root / 'src/shared/weapon/ArrowRegistry.luau').read_text())
            # Changing speed is configuration, does not demand FBX republishing.
            store.register({'name':'Test arrow','slug':'test_arrow','speed':220})
            self.assertEqual(store.get('test_arrow')['status'], 'PUBLISHED')
            self.assertEqual(store.snapshot()['activeArrowSlug'],'test_arrow')


def read_reg(path):
    return json.loads(path.read_text(encoding='utf-8'))


class BowIntegrationTests(unittest.TestCase):
    def test_bow_uses_release_not_hit_window(self):
        policy = read('src/shared/combat/BowProjectileConfig.luau')
        self.assertIn('ReleaseEvent = "Release"', policy)
        data = read_reg(ROOT / 'assets/manifests/attack-timelines.json')
        bows = [row for row in data['timelines'] if 'bow' in row['clipId']]
        self.assertTrue(bows, 'Expected authored bow timeline')
        self.assertTrue(all(set(row['events'])=={'Release'} for row in bows))
        server = read('src/server/combat/AttackService.luau')
        self.assertIn('local damageWindow = if isBow then nil', server)
        self.assertIn('BowHitscanService.Release(', server)
        client = read('src/client/combat/AttackController.luau')
        self.assertIn('if isBow then nil else CharacterAttackWindow.Resolve', client)

    def test_visible_arrow_is_model_not_hit_authority(self):
        factory=read('src/shared/combat/ArrowVisualFactory.luau')
        client=read('src/client/combat/BowShotVisualController.luau')
        hitscan=read('src/server/combat/BowHitscanService.luau')
        self.assertIn('template:Clone()',factory)
        self.assertIn('Game1ArrowTemplates',factory)
        self.assertIn('Enum.Material.Wood',factory)
        self.assertIn('visual:PivotTo(frame * correction)',factory)
        self.assertIn('child.CanQuery = false',factory)
        self.assertIn('Factory.Create(',client)
        self.assertIn('Factory.Place(',client)
        self.assertIn('EntityHitboxService.RaycastAimRegions(',hitscan)
        self.assertIn('DamageService.Apply(',hitscan)
        self.assertIn('LandscapeSwayService.Impact(',hitscan)
        self.assertNotIn('Heartbeat:Connect',hitscan)

    def test_landscape_server_uses_game1_root(self):
        sway = read('src/server/world/LandscapeSwayService.luau')
        self.assertIn('FindFirstChild("RootCollider")', sway)
        self.assertIn('"impact", model, direction.Unit', sway)

    def test_user_fire_tuner_is_never_overwritten(self):
        # The old Plugins.rar is not authoritative for locally authored presets.
        installer = read('system/studio-plugin/install.ps1')
        self.assertNotIn("$FireInstalled=", installer)
        self.assertNotIn("$FireSource=", installer)
        self.assertNotIn("Install-VerifiedBundle -Source $FireSource", installer)
        # Explicit Fire Tuner installation must not be hidden in Game1Bridge.
        plugin = read('system/studio-plugin/fire-tuner/fire_bone.lua')
        installer = read('system/studio-plugin/install-fire-tuner.ps1')
        self.assertIn('PRESET_KEY', plugin)
        self.assertIn('Tail -> Head', plugin)
        self.assertIn('Game1FireDirection', plugin)
        self.assertIn('Copy-Item -LiteralPath $destination -Destination $backup', installer)
        self.assertFalse((ROOT / 'system/studio-plugin/recover-fire-tuner.ps1').exists())

    def test_orb_runtime_and_bone_effects_are_independent_of_fire_tuner(self):
        shared = read('system/studio-plugin/modules/StudioPlacedRigBoneEffects.luau')
        self.assertIn('item:IsA("Fire")',shared)
        self.assertIn('BoneOrbController', read('src/client/init.client.luau'))
        controller = read('src/client/world/BoneOrbController.luau')
        self.assertIn('CollectionService:GetTagged(TAG)',controller)
        self.assertIn('MAX_ACTIVE = 32',controller)
        self.assertIn('bone.TransformedWorldCFrame',controller)
        self.assertIn('part.Anchored = true',controller)


if __name__ == '__main__':
    unittest.main()
