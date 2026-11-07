"""M253: registered but unpublished Location Atlas is publishable without re-choosing a file."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from api.write_world import route
from services.location_atlas_publication import publish_pending_atlas


class FirstPublicationM253(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        image = self.root / 'bush_02_32x32_atlas.png'
        Image.new('RGBA', (32,32), (40,100,70,127)).save(image)
        self.model = self.root / 'bush_02.fbx'
        self.model.write_bytes(b'test source; publication never reads this file')
        self.assets = LocationAssetStore(self.root)
        self.row = self.assets.register(dict(
            nameEn='Bush 02', slug='bush_02', category='bush',
            modelSourcePath=str(self.model),textureSourcePath=str(image)))
        self.id = self.row['atlasVariantId']
        self.original_model = self.row['model_asset_id']

    def fake_publish(self, variant_id, creds, description):
        self.assertEqual(variant_id,self.id)
        self.assertIn('bush_02',description)
        self.assertTrue(creds.get('apiKey'))
        with self.assets.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       ('899911',variant_id))
        return self.assets.atlases.get_variant(variant_id)

    def test_new_registration_pending_and_first_publication_does_not_publish_model(self):
        fresh = self.assets.get('bush_02')
        self.assertFalse(fresh['texture_asset_id'])
        self.assertFalse(self.assets.atlases.get_variant(self.id)['current'])
        with mock.patch.object(self.assets.atlases,'ensure_published',side_effect=self.fake_publish) as upload:
            response=publish_pending_atlas(self.assets,'bush_02',variant_id=self.id,
                expected_revision=fresh['bindingRevision'],credentials={'apiKey':'test'})
            upload.assert_called_once()
        self.assertEqual(response['publishedAssetId'],'899911')
        self.assertEqual(response['resourceKind'],'Atlas')
        self.assertTrue(response['studioSyncRequired'])
        self.assertEqual(self.assets.get('bush_02')['model_asset_id'],self.original_model)
        self.assertEqual(self.assets.get('bush_02')['texture_asset_id'],'899911')
        with self.assertRaisesRegex(ValueError,'already has an Image ID'):
            self.assets.atlases.publish_initial(self.id,{},'must not republish')

    def test_wrong_consumer_and_stale_binding_never_upload(self):
        with mock.patch.object(self.assets.atlases,'ensure_published') as upload:
            for slug,variant,rev in [('another',self.id,self.row['bindingRevision']),
                                     ('bush_02',self.id+10,self.row['bindingRevision']),
                                     ('bush_02',self.id,self.row['bindingRevision']+1)]:
                with self.subTest(slug=slug,variant=variant,rev=rev), self.assertRaises(ValueError):
                    publish_pending_atlas(self.assets,slug,variant_id=variant,
                        expected_revision=rev,credentials={})
            upload.assert_not_called()

    def test_export_failure_after_upload_returns_warning_not_retry_error(self):
        with mock.patch.object(self.assets.atlases,'ensure_published',side_effect=self.fake_publish):
            response=publish_pending_atlas(self.assets,'bush_02',variant_id=self.id,
                expected_revision=self.row['bindingRevision'],credentials={'apiKey':'test'},
                exports=[('Test',mock.Mock(side_effect=OSError('disk full')))])
        self.assertIn('disk full',response['exportWarnings'][0])
        self.assertEqual(response['publishedAssetId'],'899911')

    def test_http_route_contract_and_payload_validation(self):
        deps=dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
                'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
                'run_timeline_editor_bridge','sync_monster_to_studio','timelines'))
        deps.update(location_assets=self.assets,real_estate=mock.Mock(),
                    publication_credentials=lambda _description:{'apiKey':'test'})
        url='/api/location-assets/bush_02/publish-pending-atlas'
        payload={'variantId':self.id,'expectedRevision':self.row['bindingRevision']}
        with mock.patch.object(self.assets.atlases,'ensure_published',side_effect=self.fake_publish):
            status,response=route(url,lambda:payload,deps)
        self.assertEqual(status,200,response)
        self.assertEqual(response['publishedAssetId'],'899911')
        self.assertEqual(response['resourceKind'],'Atlas')
        for invalid in ({'variantId':str(self.id),'expectedRevision':1},
                        {'variantId':self.id,'expectedRevision':'1'},
                        {'variantId':True,'expectedRevision':1}):
            status,_=route(url,lambda invalid=invalid:invalid,deps)
            self.assertEqual(status,400)
        status,response=route(url,lambda:payload,deps)
        self.assertEqual(status,400)
        self.assertIn('already has an Image ID',response['error'])

    def test_client_workflow_has_explicit_publication_stages(self):
        ui=(ROOT/'system/control-center/static/location-asset-workflow.js').read_text('utf8')
        server=(ROOT/'system/control-center/api/write_dispatch.py').read_text('utf8')
        self.assertIn("state.tab='publish'",ui)
        self.assertIn("action==='publish-ready'",ui)
        self.assertIn('publish-pending-atlas',ui)
        self.assertIn('result.resourceKind',ui)
        self.assertIn('onOpenPublish',ui)
        self.assertIn('upload', (ROOT/'system/control-center/services/texture_atlas_registry.py').read_text('utf8'))
        self.assertIn('publish-pending-atlas',server)


if __name__ == '__main__':
    import unittest
    unittest.main()
