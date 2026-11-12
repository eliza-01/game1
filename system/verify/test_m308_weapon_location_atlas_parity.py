"""M308 end-to-end tests: legacy → AtlasRegistry → republish → manual Studio Sync.

No Roblox / Cloud calls. Tests use real SQLite, PNG content and mocks at Cloud boundary.
"""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from arrow_store import ArrowStore
from weapon_store import WeaponStore
from services.texture_atlas_registry import AtlasRegistry
from services.weapon_atlas_index import index_existing_textures
from services.atlas_source_review import AtlasSourceReview
from services.studio_asset_sync import StudioAssetSyncService


class WeaponAtlasParity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.weapons = WeaponStore(self.root)
        self.arrows = ArrowStore(self.root)
        self.atlases = AtlasRegistry(self.root)
        self.weapons.atlases = self.atlases
        self.arrows.atlases = self.atlases
        self.fbx = self.root / 'new.fbx'
        self.fbx.write_bytes(b'FBX MOCK - publication interface test')
        self.weapons.register({'slug':'lamp_blade','nameEn':'Lamp Blade','nameRu':'',
            'weaponType':'sword','rarity':'common','modelSourcePath':str(self.fbx)})
        self.arrows.register({'slug':'steel_arrow','name':'Steel arrow',
            'modelSourcePath':str(self.fbx)})

    def png(self, filename, color):
        path = self.root / filename
        Image.new('RGBA', (32,32), color).save(path)
        return path

    def legacy_weapon(self, filename='light.png', color='red', image_id='11111'):
        img=self.png(filename,color)
        self.weapons.register({'slug':'lamp_blade','nameEn':'Lamp Blade','nameRu':'',
            'weaponType':'sword','rarity':'common','texturePaths':[str(img)]})
        with self.weapons.connect() as db:
            db.execute("UPDATE weapon_textures SET asset_id=?,published_sha256=sha256 WHERE weapon_slug='lamp_blade'",(image_id,))
        return img

    def legacy_arrow(self, filename='arrow_color.png', color='red', image_id='11111'):
        img=self.png(filename,color)
        self.arrows.register({'slug':'steel_arrow','name':'Steel arrow',
            'textureSourcePath':str(img)})
        with self.arrows.connect() as db:
            db.execute("UPDATE arrow_assets SET texture_asset_id=?,texture_published_sha256=texture_sha256 WHERE slug='steel_arrow'",(image_id,))
        return img

    def test_legacy_image_id_indexed_and_active_dot_without_cloud(self):
        self.legacy_weapon()
        report=index_existing_textures(self.root,self.atlases)
        self.assertFalse([s for s in report['skipped'] if s['key'].startswith('weapon_')], report['skipped'])
        self.assertEqual(report['selected'][0]['imageId'],'11111')
        row=self.weapons.get('lamp_blade')
        self.assertEqual(row['atlas_binding']['published_id'],'11111')
        self.assertEqual(len(row['atlas_variants']),1)
        self.assertEqual(row['atlas_variants'][0]['original_filename'],'light.png')
        self.assertTrue(row['atlas_variants'][0]['filename'].endswith('_32x32_atlas.png'))
        self.assertFalse(report['cloudPublicationPerformed'])
        self.assertFalse(report['studioSyncPerformed'])
        self.assertEqual(len(index_existing_textures(self.root,self.atlases)['selected']),0)

    def test_cross_catalog_reuses_real_published_image_id(self):
        self.legacy_weapon()
        self.legacy_arrow('arrow_glass.png','red','11111')
        report=index_existing_textures(self.root,self.atlases)
        self.assertEqual(len(report['indexed']),2)
        self.assertEqual(self.weapons.get('lamp_blade')['atlas_binding']['id'],
                         self.arrows.get('steel_arrow')['atlas_binding']['id'])
        self.assertEqual(len(self.atlases.catalog()),1)

    def test_two_weapon_textures_attached_not_chosen_arbitrarily(self):
        self.legacy_weapon('red.png','red','11111')
        other=self.png('blue.png','blue')
        self.weapons.register({'slug':'lamp_blade','nameEn':'Lamp Blade','nameRu':'',
            'weaponType':'sword','rarity':'common','texturePaths':[str(other)]})
        with self.weapons.connect() as db:
            db.execute("UPDATE weapon_textures SET asset_id=?,published_sha256=sha256 WHERE slot='blue'",('22222',))
        report=index_existing_textures(self.root,self.atlases)
        self.assertEqual(len(report['indexed']),2)
        self.assertEqual(len(self.weapons.get('lamp_blade')['atlas_variants']),2)
        self.assertIsNone(self.weapons.get('lamp_blade')['atlas_binding'])

    def test_explicit_shared_republish_creates_new_id_and_invalidates_all_consumers(self):
        self.legacy_weapon()
        self.legacy_arrow('arrow_color.png','red','11111')
        index_existing_textures(self.root,self.atlases)
        current=self.weapons.get('lamp_blade')['atlas_binding']
        self.assertEqual(current['revision'],1)
        replacement=self.png(current['filename'],'blue')
        review=AtlasSourceReview(self.atlases)
        plan=review.inspect(str(replacement))
        self.assertTrue(plan['replacementRequired'])
        self.assertFalse(plan['legacyName'])
        self.assertEqual(plan['existing']['publishedId'],'11111')
        with patch('services.texture_atlas_registry.create_image_asset', return_value='fake-op') as upload, \
             patch('services.texture_atlas_registry.wait_for_operation',return_value=SimpleNamespace(
                asset_id='33333',operation_path='fake-op',moderation_state='APPROVED')):
            result=review.publish({'sourcePath':str(replacement),'sha256':plan['sha256'],
                'expectedVariantId':plan['existing']['id'],'expectedPublishedId':'11111',
                'approveReplacement':True}, {'apiKey':'mock','creatorType':'User','creatorId':'1'})
            upload.assert_called_once()
        self.assertEqual(result['publishedAssetId'],'33333')
        self.assertEqual(self.weapons.get('lamp_blade')['atlas_binding']['published_id'],'33333')
        self.assertEqual(self.arrows.get('steel_arrow')['atlas_binding']['published_id'],'33333')
        self.assertEqual(self.atlases.binding('weapon','lamp_blade')['syncStatus'],'pending_studio_sync')
        self.assertEqual(self.atlases.binding('arrow','steel_arrow')['syncStatus'],'pending_studio_sync')
        with self.atlases.connect() as db:
            history=[x[0] for x in db.execute('SELECT image_asset_id FROM texture_atlas_publications')]
        self.assertIn('33333',history)

    def test_model_upload_only_for_changed_fbx_and_no_legacy_image_upload(self):
        self.legacy_weapon()
        self.legacy_arrow('arrow_color.png','blue','22222')
        credentials=dict(apiKey='mock',creatorType='User',creatorId='1',description='test')
        with patch('weapon_store.staged_model',return_value=__import__('contextlib').nullcontext(self.fbx)), \
             patch('weapon_store.create_model_asset',return_value='fake'), \
             patch('weapon_store.wait_for_operation',return_value=SimpleNamespace(
                 asset_id='44444',operation_path='fake',moderation_state='APPROVED')), \
             patch('weapon_store.create_image_asset') as legacy_image, \
             patch('weapon_store.update_image_asset') as legacy_update:
            result=self.weapons.publish('lamp_blade', credentials, include_legacy_textures=False)
            self.assertEqual(result['model_asset_id'],'44444')
            # An unchanged model cannot be silently re-uploaded on every click.
            with patch('weapon_store.update_model_asset') as update:
                self.weapons.publish('lamp_blade',credentials,include_legacy_textures=False)
                update.assert_not_called()
            legacy_image.assert_not_called(); legacy_update.assert_not_called()
        with patch('arrow_store.staged_model',return_value=__import__('contextlib').nullcontext(self.fbx)), \
             patch('arrow_store.create_model_asset',return_value='fake'), \
             patch('arrow_store.wait_for_operation',return_value=SimpleNamespace(
                 asset_id='55555',operation_path='fake',moderation_state='APPROVED')), \
             patch('arrow_store.create_image_asset') as legacy_image:
            result=self.arrows.publish('steel_arrow',credentials,include_legacy_textures=False)
            self.assertEqual(result['model_asset_id'],'55555')
            legacy_image.assert_not_called()

    def test_legacy_filename_review_warns_and_previews_canonical_name(self):
        path=self.png('lamp_texture.jpg.png','cyan')
        plan=AtlasSourceReview(self.atlases).inspect(str(path))
        self.assertTrue(plan['legacyName'])
        self.assertTrue(plan['expectedFilename'].endswith('_32x32_atlas.png'))
        self.assertEqual(plan['sourceName'], 'lamp_texture.jpg.png')
        self.assertTrue(path.exists(), 'review must not rename or delete original file')

    def test_model_revision_uses_existing_id_without_touching_atlas(self):
        self.legacy_weapon()
        index_existing_textures(self.root,self.atlases)
        credentials=dict(apiKey='mock',creatorType='User',creatorId='1',description='test')
        with self.weapons.connect() as db:
            db.execute("UPDATE weapons SET model_asset_id=?,model_published_sha256=model_sha256 WHERE slug=?",
                ('44444','lamp_blade'))
        new_fbx=self.root/'changed.fbx';new_fbx.write_bytes(b'new fbx revision')
        self.weapons.register({'slug':'lamp_blade','nameEn':'Lamp Blade','nameRu':'',
            'weaponType':'sword','rarity':'common','modelSourcePath':str(new_fbx)})
        with patch('weapon_store.staged_model',return_value=__import__('contextlib').nullcontext(self.fbx)), \
             patch('weapon_store.update_model_asset',return_value='update-op') as update, \
             patch('weapon_store.create_image_asset') as legacy_image, \
             patch('weapon_store.wait_for_operation',return_value=SimpleNamespace(
                  asset_id='44444',operation_path='update-op',moderation_state='APPROVED')):
            self.weapons.publish('lamp_blade',credentials,include_legacy_textures=False)
            update.assert_called_once()
            self.assertEqual(update.call_args.kwargs['asset_id'],'44444')
            legacy_image.assert_not_called()
        self.assertEqual(self.weapons.get('lamp_blade')['model_asset_id'],'44444')
        self.assertEqual(self.weapons.get('lamp_blade')['atlas_binding']['published_id'],'11111')
        with self.weapons.connect() as db:
            model_history=[x[0] for x in db.execute("SELECT asset_id FROM weapon_publications WHERE kind='model'")]
        self.assertEqual(model_history,['44444'])

    def test_attached_resolution_can_be_switched_without_cloud(self):
        self.legacy_weapon()
        index_existing_textures(self.root,self.atlases)
        low=self.root/'weapon_lamp_blade_light_16x16_atlas.png'; Image.new('RGBA',(16,16),'blue').save(low)
        # Real shared registry owns resolution variants and requires published IDs.
        variant=self.atlases.index_existing_published_image(source_path=str(low),
            atlas_key='weapon_lamp_blade_light',published_id='22222',
            expected_sha256=__import__('hashlib').sha256(low.read_bytes()).hexdigest())
        self.atlases.attach('weapon','lamp_blade',variant['id'])
        current=self.weapons.get('lamp_blade')
        selected=self.weapons.select_atlas('lamp_blade',variant['id'],current['atlas_binding']['revision'])
        self.assertEqual(selected['atlas_binding']['published_id'],'22222')
        self.assertEqual(len(selected['atlas_variants']),2)
        self.assertEqual(self.atlases.binding('weapon','lamp_blade')['syncStatus'],'pending_studio_sync')

    def test_studio_sync_is_only_explicit_and_acknowledges_binding(self):
        self.legacy_weapon()
        index_existing_textures(self.root,self.atlases)
        with self.weapons.connect() as db:
            db.execute("UPDATE weapons SET model_asset_id=?,model_published_sha256=model_sha256 WHERE slug=?",('44444','lamp_blade'))
        hits=[]
        def load_model(*args,**kwargs):
            hits.append((args,kwargs))
            return {'weaponStats':{'textures':{'applied':1}}}
        service=StudioAssetSyncService(None,self.weapons,None,None,load_model)
        self.assertEqual(hits,[])
        service.sync_weapon_to_studio('lamp_blade')
        self.assertEqual(hits[-1][1]['metadata']['textures'][0]['assetId'],'11111')
        self.assertEqual(self.atlases.binding('weapon','lamp_blade')['syncStatus'],'synced')

    def test_ui_wires_shared_location_editor_and_legacy_naming(self):
        ui=(ROOT/'system/control-center/static/weapon-atlas-picker.js').read_text()
        self.assertIn('window.game1ConsumerAtlasEditor',ui)
        self.assertIn('allowUpload:true',ui)
        self.assertIn("filePicker:'/api/files/choose-location-asset-texture'",ui)
        self.assertIn('Legacy atlas',ui)
        self.assertIn('<atlas_key>_<width>x<height>_atlas.png',ui)
        html=(ROOT/'system/control-center/static/index.html').read_text()
        self.assertIn('weapon-atlas-picker',html)
        self.assertIn('arrow-atlas-picker',html)
        self.assertIn('deco-assets.css',html)
        store=(ROOT/'system/control-center/static/asset-atlas-editor.js').read_text()
        self.assertIn('deco-atlas-dot',store)
        self.assertIn('/api/texture-atlases/publish-reviewed',store)

if __name__=='__main__':
    unittest.main()
