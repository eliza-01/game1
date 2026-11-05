"""M234 consumer-choice contract: one active binding, multiple selectable variants."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.texture_atlas_registry import AtlasRegistry
from services.atlas_source_review import AtlasSourceReview


class SharedConsumerAtlasM234(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'.control-center').mkdir()
        self.registry=AtlasRegistry(self.root)
        self.assets=self.root/'inputs';self.assets.mkdir()

    def variant(self,name,color):
        path=self.assets/name
        Image.new('RGB',(8,8),color).save(path)
        v=self.registry.register_file(str(path))
        with self.registry.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=? WHERE id=?',
                       (str(1000000+v['id']),v['source_sha256'],v['id']))
        return self.registry.get_variant(v['id'])

    def test_attach_and_select_does_not_publish_or_change_other_consumer(self):
        first=self.variant('pine_8x8_atlas.png','green')
        other=self.variant('birch_8x8_atlas.png','white')
        self.registry.bind('location_asset','tree_a',first['id'])
        self.registry.bind('location_asset','tree_b',first['id'])
        before=self.registry.binding('location_asset','tree_b')
        self.registry.attach('location_asset','tree_a',other['id'])
        self.assertEqual(self.registry.binding('location_asset','tree_a')['variant_id'],first['id'])
        self.assertEqual({v['id'] for v in self.registry.attached_variants('location_asset','tree_a')},
                         {first['id'],other['id']})
        self.registry.bind('location_asset','tree_a',other['id'],expected_revision=1)
        self.assertEqual(self.registry.binding('location_asset','tree_a')['variant_id'],other['id'])
        self.assertEqual(self.registry.binding('location_asset','tree_b'),before)
        self.assertEqual({v['id'] for v in AtlasRegistry(self.root).attached_variants('location_asset','tree_a')}, {first['id'],other['id']})

    def test_review_normalizes_webp_with_png_suffix_without_registry_write(self):
        source=self.assets/'pine_8x8_atlas.png'
        Image.new('RGB',(8,8),'green').save(source,format='WEBP',quality=100)
        reviewed=AtlasSourceReview(self.registry).inspect(str(source))
        self.assertTrue(reviewed['valid'])
        self.assertEqual(reviewed['filename'],'pine_8x8_atlas.png')
        self.assertTrue(reviewed['newPreview'].startswith('data:image/png;base64,'))
        self.assertEqual(self.registry.catalog(),[])

    def test_review_canonicalizes_legacy_image_basename(self):
        source=self.assets/'spruce.png'
        Image.new('RGB',(8,8),'green').save(source)
        reviewed=AtlasSourceReview(self.registry).inspect(str(source))
        self.assertEqual(reviewed['filename'],'spruce_8x8_atlas.png')
        self.assertFalse(reviewed['replacementRequired'])
        self.assertEqual(self.registry.catalog(),[])

    def test_shared_real_estate_consumer_and_location_are_independent(self):
        v=self.variant('pine_8x8_atlas.png','green')
        self.registry.bind('real_estate','house_01:glass',v['id'])
        self.registry.attach('location_asset','tree_01',v['id'])
        self.assertIsNone(self.registry.binding('location_asset','tree_01'))
        self.assertEqual(len(self.registry.attached_variants('location_asset','tree_01')),1)
        self.registry.unbind('location_asset','tree_01')
        self.assertEqual(len(self.registry.attached_variants('location_asset','tree_01')),0)
        self.assertEqual(self.registry.binding('real_estate','house_01:glass')['variant_id'],v['id'])

    def test_preview_is_read_only_and_requires_explicit_approval(self):
        v=self.variant('pine_8x8_atlas.png','green')
        rev=self.root/'new';rev.mkdir()
        replacement=rev/'pine_8x8_atlas.png'
        Image.new('RGB',(8,8),'red').save(replacement)
        review=AtlasSourceReview(self.registry)
        result=review.inspect(str(replacement))
        self.assertTrue(result['valid'])
        self.assertEqual(result['existing']['publishedId'],v['published_id'])
        self.assertTrue(result['replacementRequired'])
        self.assertTrue(result['oldPreview'].startswith('data:image/png;base64,'))
        self.assertTrue(result['newPreview'].startswith('data:image/png;base64,'))
        self.assertFalse(self.registry.get_variant(v['id'])['replacementPending'])
        request={'sourcePath':str(replacement),'sha256':result['sha256'],
                 'expectedVariantId':v['id'],'expectedPublishedId':v['published_id']}
        with self.assertRaisesRegex(ValueError,'approval'):
            review.publish(request,{})
        with self.assertRaisesRegex(ValueError,'changed since preview'):
            review.publish({**request,'sha256':'0'*64,'approveReplacement':True},{})
        self.assertFalse(self.registry.get_variant(v['id'])['replacementPending'])

    def test_committed_publication_reports_export_failure_without_false_retry(self):
        from api.write_world import route
        from api.write_dispatch import _requires_asset_audit
        class FakeAtlasSourceReview:
            def __init__(self, registry):
                self.registry = registry
            def publish(self, payload, credentials):
                return {'publishedAssetId':'301','variant':{'id':7},'unchanged':False}
        def failed_export():
            raise OSError('write access denied')
        deps={name:None for name in ('deco_layouts','locations','monster_spawns',
            'npc_place_spawn','npc_register_spawn','npc_spawns','options_store',
            'request_active_studio_save','run_timeline_editor_bridge',
            'sync_monster_to_studio','timelines')}
        deps.update(location_assets=SimpleNamespace(atlases=self.registry,export=failed_export),
                    real_estate=SimpleNamespace(export=lambda:None),
                    publication_credentials=lambda _: {'apiKey':'unused'})
        with patch('api.write_world.AtlasSourceReview', FakeAtlasSourceReview):
            status,response=route('/api/texture-atlases/publish-reviewed',
                lambda:{'sourcePath':'example.png'},deps)
        self.assertEqual(status,200)
        self.assertEqual(response['publishedAssetId'],'301')
        self.assertIn('write access denied',response['exportWarnings'][0])
        self.assertTrue(_requires_asset_audit('/api/texture-atlases/publish-reviewed'))

    def test_ui_both_editors_reuse_component_and_single_scoped_sync(self):
        base=ROOT/'system/control-center/static'
        la=(base/'location-asset-workflow.js').read_text()
        re=(base/'real-estate-mesh-workflow.js').read_text()
        shared=(base/'asset-atlas-editor.js').read_text()
        for ui in (la,re):
            self.assertIn('window.game1ConsumerAtlasEditor.render',ui)
            self.assertIn('window.game1ConsumerAtlasEditor.wire',ui)
            self.assertIn('Sync Model + Atlas · Studio',ui)
            self.assertNotIn('Save image source',ui)
            self.assertNotIn('see notification',ui)
        self.assertIn('preview-source',shared)
        self.assertIn('publish-reviewed',shared)
        self.assertIn('data-ca-choice',shared)
        self.assertIn('data-ca-approval',shared)
        self.assertNotIn('StudioSync.run',shared)
        self.assertIn('Publish and Apply',la)
        self.assertIn('asset-apply-ready',la)

if __name__=='__main__':unittest.main()
