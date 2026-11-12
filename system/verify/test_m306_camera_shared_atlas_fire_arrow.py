"""M306: camera authoring, native arrow sticking, read-only Fire selection, shared atlases."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore
from services.camera_settings import normalize_camera, DEFAULT_CAMERA
from services.texture_atlas_registry import AtlasRegistry
from weapon_store import WeaponStore
from arrow_store import ArrowStore
from api import read_world

class CameraOptionsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.store=OptionsStore(self.root)

    def test_additive_migration_preserves_existing_values(self):
        saved=self.store.snapshot();self.assertEqual(saved['camera'],DEFAULT_CAMERA)
        saved['combat']['stateDurationSeconds']=37.5
        saved['characterAnimations']['deathPlaybackPercent']=70
        saved.pop('camera');saved.pop('cameraPresets');saved.pop('activeCameraPreset')
        self.store.manifest_path.write_text(json.dumps(saved))
        migrated=OptionsStore(self.root).snapshot()
        self.assertEqual(migrated['combat']['stateDurationSeconds'],37.5)
        self.assertEqual(migrated['characterAnimations']['deathPlaybackPercent'],70)
        self.assertEqual(migrated['camera'],DEFAULT_CAMERA)
        self.assertIn('cursorY = 0.5',self.store.registry_path.read_text())

    def test_draft_does_not_save_and_presets_are_explicit(self):
        before=self.store.manifest_path.read_bytes()
        preview={**DEFAULT_CAMERA,'distance':13.25,'cursorX':0.62}
        response=self.store.preview_camera(preview)
        self.assertFalse(response['saved'])
        self.assertEqual(self.store.manifest_path.read_bytes(),before)
        self.assertEqual(self.store.snapshot()['camera']['distance'],10)
        self.assertEqual(self.store.snapshot_with_debug()['cameraDebugDraft']['cursorX'],0.62)
        self.store.update({'camera':preview,'cameraPresetAction':'save','cameraPresetName':'Mobile close'})
        self.assertEqual(self.store.snapshot()['camera']['distance'],13.25)
        self.assertEqual(self.store.snapshot()['cameraPresets'][0]['name'],'Mobile close')
        self.store.update({'camera':{**DEFAULT_CAMERA}})
        self.assertEqual(self.store.snapshot()['camera']['distance'],10)
        self.store.update({'cameraPresetAction':'apply','cameraPresetName':'Mobile close'})
        self.assertEqual(self.store.snapshot()['camera']['distance'],13.25)
        self.store.update({'cameraPresetAction':'delete','cameraPresetName':'Mobile close'})
        self.assertFalse(self.store.snapshot()['cameraPresets'])

    def test_validation_rejects_unknown_keys_nan_and_invalid_presets(self):
        for wrong in ({**DEFAULT_CAMERA,'cursorX':3}, {**DEFAULT_CAMERA,'distance':float('nan')},
                      {**DEFAULT_CAMERA,'invalid':1}, {**DEFAULT_CAMERA,'cursorX':'0.4'}):
            with self.assertRaises(ValueError):normalize_camera(wrong)
        with self.assertRaises(ValueError):self.store.preview_camera({'cursorX':0.3,'bogus':42})
        with self.assertRaises(ValueError):self.store.update({'cameraPresetAction':'save','cameraPresetName':'bad/dir'})

    def test_get_draft_only_through_read_api(self):
        self.store.preview_camera({**DEFAULT_CAMERA,'distance':17})
        status, payload=read_world.route(type('URL',(),{'path':'/api/options'})(), {'options':self.store}, lambda:{})
        self.assertEqual(status,200)
        self.assertEqual(payload['cameraDebugDraft']['distance'],17)
        self.assertEqual(self.store.snapshot()['camera']['distance'],10)

class SharedAtlasTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        (self.root/'.control-center').mkdir(parents=True)
        self.atlases=AtlasRegistry(self.root)
        self.weapons=WeaponStore(self.root);self.weapons.atlases=self.atlases
        self.arrows=ArrowStore(self.root);self.arrows.atlases=self.atlases

    def test_index_existing_weapon_id_and_bind_same_atlas_to_arrow(self):
        image=self.root/'original_weapon_atlas.png'
        Image.new('RGBA',(128,128),(95,120,180,255)).save(image)
        sha=hashlib.sha256(image.read_bytes()).hexdigest()
        v=self.atlases.index_existing_published_image(source_path='original_weapon_atlas.png',
            atlas_key='weapon_longbow_main',published_id='136789123456',expected_sha256=sha)
        self.assertEqual(v['published_id'],'136789123456')
        self.assertTrue(v['current']);self.assertEqual(v['resolution'],'128x128')
        self.assertEqual(self.atlases.index_existing_published_image(source_path='original_weapon_atlas.png',
            atlas_key='weapon_longbow_main',published_id='136789123456',expected_sha256=sha)['id'],v['id'])
        fb=self.root/'arrow.fbx';fb.write_bytes(b'; source')
        arrow=self.arrows.register({'name':'test','slug':'test','modelSourcePath':str(fb)})
        weapon=self.weapons.register({'slug':'blade','nameEn':'Blade','weaponType':'sword','rarity':'common','modelSourcePath':str(fb)})
        self.atlases.attach('arrow','test',v['id'])
        self.atlases.attach('weapon','blade',v['id'])
        self.assertIn(v['id'], [x['id'] for x in self.arrows.get('test')['atlas_variants']])
        self.assertIn(v['id'], [x['id'] for x in self.weapons.get('blade')['atlas_variants']])
        self.assertEqual(self.arrows.select_atlas('test',v['id'],0)['atlas_binding']['published_id'],'136789123456')
        self.assertEqual(self.weapons.select_atlas('blade',v['id'],0)['atlas_binding']['published_id'],'136789123456')

    def test_source_must_match_existing_published_image(self):
        p=self.root/'test.png';Image.new('RGB',(64,64),(125,80,100)).save(p)
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'differs'):
            self.atlases.index_existing_published_image(source_path='test.png',atlas_key='weapon_blade',
                published_id='12345',expected_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'missing'):
            self.atlases.index_existing_published_image(source_path='../other.png',atlas_key='weapon_blade',
                published_id='12345',expected_sha256=sha)

class StudioSourceContracts(unittest.TestCase):
    def text(self,path):return (ROOT/path).read_text(encoding='utf-8')
    def test_fire_bone_binding_never_creates_defaults(self):
        lua=self.text('system/studio-plugin/fire-tuner/fire_bone.lua')
        selected=lua.split('local function bindSelected()',1)[1].split('selectButton.MouseButton1Click',1)[0]
        self.assertIn('findEffect(currentBone, "Fire")',selected)
        self.assertIn('findEffect(currentBone, "PointLight")',selected)
        self.assertNotIn('createFire()',selected)
        self.assertNotIn('createLight()',selected)
        self.assertIn('plugin:SetSetting(PRESET_KEY',lua)
        self.assertIn('CFrame.Angles(math.pi, 0, 0)',lua)

    def test_impact_uses_native_weld_on_props_bone_local_on_animated_rigs(self):
        source=self.text('src/server/combat/ArrowImpactAttachment.luau')
        self.assertIn('Instance.new("WeldConstraint")',source)
        self.assertIn('weld.Part0 = hitPart',source)
        self.assertIn('bone.TransformedWorldCFrame',source)
        self.assertIn('RunService.Heartbeat:Connect(update)',source)
        self.assertIn('connection:Disconnect()',source)
        bow=self.text('src/server/combat/BowProjectileService.luau')
        self.assertIn('ArrowImpactAttachment.Attach(visual, hitInstance, entity, boneName)',bow)
        self.assertIn('ArrowVisualFactory.ContactFrame',bow)

    def test_camera_one_authoritative_controller_and_manual_persistence(self):
        cam=self.text('src/client/character/CameraController.luau')
        self.assertIn('function CameraController.ApplyDebug',cam)
        self.assertIn('function CameraController.GetAimRay',cam)
        aim=self.text('src/client/combat/AimPoseController.luau')
        self.assertIn('CameraController.GetAimRay()',aim)
        debug=self.text('src/client/dev/CameraDebugController.luau')
        self.assertIn('StudioDebugDock.ButtonPosition("CD")',debug)
        self.assertIn('remote:FireServer(values)',debug)
        bridge=self.text('system/studio-plugin/modules/StudioCameraDraftBridge.luau')
        self.assertIn('/api/options/camera-draft',bridge)
        self.assertNotIn('/api/options"',bridge)
        options=self.text('system/control-center/static/options.js')
        self.assertIn('option-camera-draft-import',options)
        self.assertIn('option-camera-save',options)
        self.assertIn('cameraPresetAction',options)

    def test_same_shared_atlas_editor_rendered_for_weapons_and_arrows(self):
        picker=self.text('system/control-center/static/weapon-atlas-picker.js')
        self.assertIn('window.game1ConsumerAtlasEditor',picker)
        self.assertNotIn('data-ca-choice=',picker)
        shared=self.text('system/control-center/static/asset-atlas-editor.js')
        self.assertIn('deco-atlas-dots',shared)
        self.assertIn('allowUpload',shared)
        self.assertIn('consumerType:kind',picker)
        self.assertIn('kind===\'arrow\'',picker)

if __name__=='__main__':unittest.main()
