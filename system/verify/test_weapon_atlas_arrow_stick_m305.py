"""M305 regressions: Arrow penetration, stuck models and shared atlas IDs."""
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from arrow_store import ArrowStore
from weapon_store import WeaponStore
from services.texture_atlas_registry import AtlasRegistry
from services.studio_asset_sync import StudioAssetSyncService

class SharedWeaponAtlasTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.root = root
        self.weapons = WeaponStore(root)
        self.arrows = ArrowStore(root)
        self.atlases = AtlasRegistry(root)
        self.weapons.atlases = self.atlases
        self.arrows.atlases = self.atlases
        with self.atlases.connect() as db:
            db.execute('INSERT INTO texture_atlas_families(id,atlas_key,created_at) VALUES(1,?,1)', ('lamp_01',))
            db.execute('''INSERT INTO texture_atlas_variants(
                id,family_id,width,height,filename,original_filename,source_path,
                source_sha256,uses_alpha,published_id,published_sha256,moderation_state,created_at)
                VALUES(1,1,1024,1024,?,?,?,?,0,?,?,?,1)''',
                ('lamp_01_1024x1024_atlas.png','lamp_01_1024x1024_atlas.png',
                 'assets/source/atlas/lamp.png','abcd','1234567','abcd','APPROVED'))
        fb = root / 'arrow.fbx'; fb.write_bytes(b'; Mock FBX only')
        self.arrow = self.arrows.register({'name':'test','slug':'test','modelSourcePath':str(fb),
                                          'penetrationStuds':0.3})
        self.weapon = self.weapons.register({'slug':'blade','nameEn':'Blade','nameRu':'',
            'weaponType':'sword','rarity':'common','modelSourcePath':str(fb)})

    def test_bind_shared_atlas_and_export_without_upload(self):
        arrow = self.arrows.select_atlas('test',1,0)
        weapon = self.weapons.select_atlas('blade',1,0)
        self.assertEqual(arrow['atlas_binding']['published_id'],'1234567')
        self.assertEqual(weapon['atlas_binding']['id'],1)
        with self.assertRaisesRegex(ValueError,'stale'):
            self.arrows.select_atlas('test',1,0)
        self.assertIn('textureAssetId', (self.root/'src/shared/weapon/ArrowRegistry.luau').read_text())
        self.assertIn('atlasVariantId', (self.root/'src/shared/weapon/WeaponRegistry.luau').read_text())
        self.assertEqual(self.atlases.binding('arrow','test')['syncStatus'],'pending_studio_sync')
        self.assertEqual(self.atlases.binding('weapon','blade')['syncStatus'],'pending_studio_sync')
        self.assertIsNone(self.arrows.clear_atlas('test')['atlas_binding'])
        self.assertIsNone(self.weapons.clear_atlas('blade')['atlas_binding'])

    def test_arrow_depth_validation_without_republication(self):
        self.assertEqual(self.arrow['penetration_studs'],0.3)
        with self.assertRaisesRegex(ValueError,'penetration'):
            self.arrows.register({'name':'test','slug':'test','penetrationStuds':5})
        with self.arrows.connect() as db:
            db.execute('UPDATE arrow_assets SET model_asset_id=?,published_sha256=? WHERE slug=?',
                       ('123456',self.arrow['sha256'],'test'))
        self.arrows.register({'name':'test','slug':'test','penetrationStuds':0.05})
        self.assertEqual(self.arrows.get('test')['status'],'PUBLISHED')
        self.assertIn('"penetrationStuds":0.05', (self.root/'src/shared/weapon/ArrowRegistry.luau').read_text())

    def test_gameplay_arrow_follows_landscape_and_no_fixed_depth(self):
        server=(ROOT/'src/server/combat/BowHitscanService.luau').read_text()
        client=(ROOT/'src/client/combat/BowShotVisualController.luau').read_text()
        factory=(ROOT/'src/shared/combat/ArrowVisualFactory.luau').read_text()
        self.assertIn('localContact = if part',server)
        self.assertIn('Instance.new("WeldConstraint")',client)
        self.assertIn('Factory.ContactFrame(',client)
        self.assertIn('visual.Parent = sway',client)
        self.assertNotIn('direction.Unit * 0.55',client)
        self.assertIn('item.Transparency',factory)

    def test_shared_atlas_studio_sync_is_explicit_and_checked(self):
        self.arrows.select_atlas('test',1,0)
        self.weapons.select_atlas('blade',1,0)
        with self.arrows.connect() as db:
            db.execute('UPDATE arrow_assets SET model_asset_id=?,published_sha256=? WHERE slug=?',
                       ('123456',self.arrow['sha256'],'test'))
        with self.weapons.connect() as db:
            db.execute('UPDATE weapons SET model_asset_id=?,model_published_sha256=? WHERE slug=?',
                       ('654321',self.weapon['model_sha256'],'blade'))
        calls=[]
        def studio_load(asset_id,destination,**kwargs):
            calls.append((asset_id,destination,kwargs))
            return {'weaponStats': {'textures': {'applied': 1}},'destination':'ServerStorage.test'}
        service=StudioAssetSyncService(None,self.weapons,None,None,studio_load,arrows=self.arrows)
        self.assertEqual(len(calls),0)  # binding NEVER triggers Studio load
        service.sync_arrow_to_studio('test')
        self.assertEqual(calls[-1][2]['metadata']['textures'][0]['assetId'],'1234567')
        service.sync_weapon_to_studio('blade')
        self.assertEqual(calls[-1][2]['metadata']['textures'][0]['assetId'],'1234567')
        self.assertEqual(self.atlases.binding('arrow','test')['syncStatus'],'synced')
        self.assertEqual(self.atlases.binding('weapon','blade')['syncStatus'],'synced')

    def test_missing_studio_texture_application_never_marked_synced(self):
        self.arrows.select_atlas('test',1,0)
        with self.arrows.connect() as db:
            db.execute('UPDATE arrow_assets SET model_asset_id=?,published_sha256=? WHERE slug=?',
                       ('123456',self.arrow['sha256'],'test'))
        def studio_load(*args,**kwargs):
            return {'weaponStats': {'textures': {'applied': 0}}}
        service=StudioAssetSyncService(None,self.weapons,None,None,studio_load,arrows=self.arrows)
        with self.assertRaisesRegex(ValueError, 'no MeshPart received'):
            service.sync_arrow_to_studio('test')
        self.assertEqual(self.atlases.binding('arrow','test')['syncStatus'],'pending_studio_sync')

    def test_fire_tuner_any_bone_presets_and_direction(self):
        tuner=(ROOT/'system/studio-plugin/fire-tuner/fire_bone.lua').read_text()
        self.assertNotIn('if bone.Name ~= "fire_bone"',tuner)
        self.assertIn('CFrame.Angles(math.pi, 0, 0)',tuner)
        self.assertIn('plugin:SetSetting(PRESET_KEY',tuner)
        self.assertIn('plugin:GetSetting(PRESET_KEY)',tuner)
        install=(ROOT/'system/studio-plugin/install.ps1').read_text()
        self.assertNotIn('fire-tuner\\fire_bone.lua', install)
        self.assertTrue((ROOT/'system/studio-plugin/install-fire-tuner.ps1').is_file())
        self.assertFalse((ROOT/'system/studio-plugin/recover-fire-tuner.ps1').exists())
        registry=(self.root/'src/shared/weapon/WeaponRegistry.luau').read_text()
        self.assertIn('statModifiers = table.freeze({',registry)
        # atlasVariantId must be an asset-level field, outside statModifiers.
        self.weapons.select_atlas('blade',1,0)
        registry=(self.root/'src/shared/weapon/WeaponRegistry.luau').read_text()
        self.assertIn('}),\n\t\t\tatlasVariantId = 1,\n\t\t\ttextures',registry)

    def test_no_unrequested_autopublishing(self):
        js=(ROOT/'system/control-center/static/weapon-atlas-picker.js').read_text()
        self.assertIn('/api/texture-atlases',js)
        self.assertIn('window.game1ConsumerAtlasEditor',js)
        self.assertIn('/api/texture-atlases/consumer-choice',(ROOT/'system/control-center/static/asset-atlas-editor.js').read_text())
        self.assertNotIn('/publish',js)
        self.assertNotIn('/sync',js)
        self.assertIn('confirm(', (ROOT/'system/control-center/static/arrow-assets.js').read_text())

if __name__ == '__main__': unittest.main()
