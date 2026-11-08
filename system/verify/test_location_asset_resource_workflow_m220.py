"""M220 registration and publishing; M221 geometry uses a guarded in-place operation."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock
import sys

from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
sys.path.insert(0,str(ROOT/'system/asset-manager'))
from location_asset_store import LocationAssetStore
from location_rig_contract import validate


class M220LocationResourceWorkflow(TestCase):
    def setUp(self):
        directory=TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.model=self.root/'pine.fbx'
        self.model.write_bytes(b'FBX revision 1')
        self.texture=self.root/'pine_32x32_atlas.png'
        Image.new('RGBA',(32,32),(20,60,90,255)).save(self.texture)
        self.store=LocationAssetStore(self.root)
        self.row=self.store.register({
            'slug':'pine_01','nameEn':'Pine 01','category':'tree',
            'modelSourcePath':str(self.model),'textureSourcePath':str(self.texture),
            'createOnly':True,
        })
        self.credentials={'creatorType':'user','creatorId':'1','apiKey':'fake'}
        # Shared atlas already published. No model workflow may reupload it.
        with self.store.connect() as db:
            db.execute('''UPDATE texture_atlas_variants
                SET published_id='90001',published_sha256=source_sha256
                WHERE id=?''',(self.row['atlasVariantId'],))

    def model_publish(self, asset_ids):
        @contextmanager
        def staged(root,model, *, texture_mode="embedded", report_receiver=None):
            self.assertIsNotNone(report_receiver)
            frame=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
            report_receiver["locationRigManifest"]=validate(
                [{"name":"rig_carrier","vertices":3},{"name":"pine_01","vertices":15}],
                [{"name":"root","parent":"","matrix":frame}])
            self.assertEqual(texture_mode, "geometry_only")
            self.assertEqual(Path(model).suffix,'.fbx')
            yield model
        ids=iter(asset_ids)
        operations=[]
        def upload(*args,**kwargs):
            operations.append(kwargs)
            return 'fake-operation'
        def wait(*args,**kwargs):
            return SimpleNamespace(asset_id=next(ids),operation_path='fake-operation',moderation_state='Approved')
        return mock.patch.multiple('location_asset_store',staged_model=staged,
            create_model_asset=upload,wait_for_operation=wait),operations

    def test_new_only_registration_and_revision_preconditions(self):
        with self.assertRaisesRegex(ValueError,'already registered'):
            self.store.register({'slug':'pine_01','nameEn':'Overwritten','category':'tree','createOnly':True,
                                 'atlasVariantId':self.row['atlasVariantId']})
        with self.assertRaisesRegex(ValueError,'no longer registered'):
            self.store.register({'slug':'missing_asset','nameEn':'Missing','category':'tree',
                                 'editOnly':True,'atlasVariantId':self.row['atlasVariantId']})
        saved=self.store.register({'slug':'pine_01','nameEn':'Pine Updated','category':'tree',
            'editOnly':True,'expectedRevision':self.row['revision'],
            'atlasVariantId':self.row['atlasVariantId']})
        self.assertEqual(saved['name_en'],'Pine Updated')
        with self.assertRaisesRegex(ValueError,'changed since Edit opened'):
            self.store.register({'slug':'pine_01','nameEn':'Stale edit','category':'tree',
                'editOnly':True,'expectedRevision':self.row['revision'],
                'atlasVariantId':self.row['atlasVariantId']})

    def test_model_and_atlas_scope_have_no_cross_publication(self):
        publication,operations=self.model_publish(['11111','22222','33333'])
        with publication, mock.patch('services.texture_atlas_registry.create_image_asset',
                                     side_effect=AssertionError('no image upload expected')):
            first=self.store.publish('pine_01',self.credentials,scope='model')
            self.assertEqual(first['model_asset_id'],'11111')
            self.assertEqual(first['texture_asset_id'],'90001')
            self.assertEqual(self.store.publish('pine_01',self.credentials,scope='model')['model_asset_id'],'11111')
            self.store.publish('pine_01',self.credentials,scope='model',force_model=True)
            self.model.write_bytes(b'FBX revision 2')
            changed=self.store.register({'slug':'pine_01','category':'tree','nameEn':'Pine 01',
                'modelSourcePath':str(self.model),'editOnly':True,'atlasVariantId':self.row['atlasVariantId']})
            self.assertEqual(changed['model_asset_id'],'22222')
            self.assertEqual(changed['status'],'UPDATE_AVAILABLE')
            final=self.store.publish('pine_01',self.credentials,scope='model')
            self.assertEqual(final['model_asset_id'],'33333')
            self.assertEqual(final['texture_asset_id'],'90001')
            self.store.publish('pine_01',self.credentials,scope='atlas')
        self.assertEqual(len(operations),3)
        self.assertEqual([p['asset_id'] for p in self.store.publications('pine_01')],
                         ['33333','22222','11111'])

    def test_publication_failure_does_not_lose_old_id(self):
        publication,_=self.model_publish(['55100'])
        with publication:
            self.store.publish('pine_01',self.credentials,scope='model')
        self.model.write_bytes(b'FBX revision changed')
        self.store.register({'slug':'pine_01','nameEn':'Pine 01','category':'tree',
            'modelSourcePath':str(self.model),'atlasVariantId':self.row['atlasVariantId'],
            'editOnly':True})
        with mock.patch('location_asset_store.staged_model',side_effect=RuntimeError('Roblox rejected upload')):
            with self.assertRaisesRegex(RuntimeError,'Roblox rejected'):
                self.store.publish('pine_01',self.credentials,scope='model')
        self.assertEqual(self.store.get('pine_01')['model_asset_id'],'55100')
        self.assertEqual(len(self.store.publications('pine_01')),1)

    def test_invalid_publication_scope_fails_before_upload(self):
        with mock.patch('location_asset_store.create_model_asset') as upload:
            with self.assertRaisesRegex(ValueError,'scope'):
                self.store.publish('pine_01',self.credentials,scope='global')
            with self.assertRaisesRegex(ValueError,'requires model'):
                self.store.publish('pine_01',self.credentials,scope='atlas',force_model=True)
            upload.assert_not_called()

    def test_studio_luau_contract_stays_non_destructive(self):
        plugin=(ROOT/'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text(encoding='utf-8')
        for forbidden in ('LoadAssetAsync(', '.MeshId =', 'previous:Destroy()', 'model:Destroy()'):
            self.assertNotIn(forbidden,plugin)
        self.assertIn('Game1DecoAssetSlug',plugin)
