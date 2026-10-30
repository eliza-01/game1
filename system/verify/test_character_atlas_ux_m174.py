"""M174: Character atlas scoping, publication safety, and UI contracts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.texture_atlas_registry import AtlasRegistry
from character_core.atlas_authoring import CharacterAtlasAuthoring


class CharacterAtlasUXM174(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.root.joinpath('incoming').mkdir()
        self.root.joinpath('.control-center').mkdir()
        self.registry = AtlasRegistry(self.root)
        self.components = SimpleNamespace(root=self.root, atlases=self.registry, export=mock.Mock())
        self.flow = CharacterAtlasAuthoring(self.components)

    def image(self, filename, color='red', size=(32, 32)):
        path = self.root/'incoming'/filename
        Image.new('RGB', size, color).save(path)
        return path

    def credentials(self, _):
        return {'apiKey':'test', 'creatorType':'User', 'creatorId':'1'}

    def publish(self, data, asset):
        with mock.patch('services.texture_atlas_registry.create_image_asset', return_value='operations/test') as upload, \
             mock.patch('services.texture_atlas_registry.wait_for_operation', return_value=SimpleNamespace(
                 asset_id=str(asset),operation_path='operations/test',moderation_state='Approved')):
            answer = self.flow.publish({
                'sourcePath':data['sourcePath'],'sha256':data['sha256'],
                'expectedVariantId':data['existing']['id'] if data['existing'] else 0,
                'expectedPublishedId':data['existing']['publishedId'] if data['existing'] else '',
                'approveReplacement':True}, self.credentials)
        return answer, upload

    def test_character_catalog_excludes_location_and_real_estate_atlases(self):
        location = self.image('structures_01_32x32_atlas.png')
        self.registry.register_file(str(location))
        character = self.image('human_face_01_32x32_atlas.png')
        self.assertEqual(self.registry.catalog(domain='character'), [])
        preview = self.flow.inspect(str(character))
        self.assertTrue(preview['valid'])
        self.assertTrue(preview['newPreview'].startswith('data:image/png;base64,'))
        self.publish(preview, 10001)
        groups = self.registry.catalog(domain='character')
        self.assertEqual([g['atlasKey'] for g in groups], ['human_face_01'])
        self.assertEqual(len(self.registry.catalog()), 2)
        self.assertEqual(self.components.export.call_count, 1)

    def test_cross_section_name_collision_refused_without_registering(self):
        path = self.image('structures_01_32x32_atlas.png')
        self.registry.register_file(str(path))
        inspection = self.flow.inspect(str(path))
        self.assertFalse(inspection['valid'])
        self.assertIn('another section', inspection['reason'])
        with self.assertRaisesRegex(ValueError, 'another section'):
            self.registry.register_file(str(path), domain='character')
        self.assertEqual(self.registry.catalog(domain='character'), [])

    def test_filename_bad_or_dimensions_mismatch_prevents_registration(self):
        invalid = self.image('face.png')
        report = self.flow.inspect(str(invalid))
        self.assertFalse(report['valid'])
        self.assertEqual(report['expectedFilename'], 'face_32x32_atlas.png')
        bad_size = self.image('face_64x64_atlas.png')
        report = self.flow.inspect(str(bad_size))
        self.assertFalse(report['valid'])
        self.assertEqual(report['expectedFilename'], 'face_32x32_atlas.png')
        self.assertEqual(self.registry.catalog(), [])

    def test_new_and_replacement_use_distinct_ids_and_require_approval(self):
        path = self.image('face_32x32_atlas.png')
        preview = self.flow.inspect(str(path))
        first, upload = self.publish(preview, 10001)
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(first['publishedAssetId'], '10001')
        self.assertTrue(self.flow.inspect(str(path))['unchanged'])
        self.image(path.name, color='green')
        replacement = self.flow.inspect(str(path))
        self.assertTrue(replacement['replacementRequired'])
        self.assertEqual(replacement['existing']['publishedId'], '10001')
        self.assertTrue(replacement['oldPreview'].startswith('data:image/png;base64,'))
        request = dict(sourcePath=replacement['sourcePath'],sha256=replacement['sha256'],
                       expectedVariantId=replacement['existing']['id'],expectedPublishedId='10001')
        with self.assertRaisesRegex(ValueError, 'approval'):
            self.flow.publish(request,self.credentials)
        with self.assertRaisesRegex(ValueError, 'changed since preview'):
            self.flow.publish({**request,'sha256':'stale','approveReplacement':True},self.credentials)
        self.assertEqual(self.registry.get_variant(replacement['existing']['id'])['published_id'],'10001')
        second, upload = self.publish(replacement,10002)
        self.assertEqual(upload.call_count,1)
        self.assertEqual(second['previousAssetId'],'10001')
        self.assertEqual(second['publishedAssetId'],'10002')
        self.assertEqual(self.registry.get_variant(replacement['existing']['id'])['published_id'],'10002')
        with mock.patch('services.texture_atlas_registry.create_image_asset') as duplicate:
            self.flow.publish({**request,'expectedPublishedId':'10002','approveReplacement':True}, self.credentials)
            duplicate.assert_not_called()

    def test_location_registration_cannot_replace_character_scoped_variant(self):
        path = self.image('face_32x32_atlas.png')
        self.registry.register_file(str(path), domain='character')
        with self.assertRaisesRegex(ValueError, 'belongs to Characters'):
            self.registry.register_file(str(path))

    def test_ui_exposes_sort_table_modal_scoped_picker_and_editor_jump(self):
        static = ROOT/'system/control-center/static'
        html = (static/'index.html').read_text()
        js = (static/'character-components.js').read_text()
        atlas = (static/'character-atlas-ui.js').read_text()
        assembly = (static/'character-assemblies.js').read_text()
        for value in ('data-cp-sort="id"', 'data-cp-sort="slot"', 'data-cp-sort="set_id"',
                      'id="cp-atlas-dialog"', 'id="cp-atlas-rows"'):
            self.assertIn(value,html)
        self.assertIn('✓ published',js)
        self.assertIn('cp-health-warning',js)
        self.assertIn('/api/files/choose-character-atlas',atlas)
        self.assertNotIn('cp-atlas-pending',html)
        self.assertNotIn('cp-atlas-publish',html)
        self.assertIn('scrollIntoView',assembly)
        self.assertIn('ca-part-icon',assembly)

if __name__=='__main__':
    import unittest
    unittest.main()
