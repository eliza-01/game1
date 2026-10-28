"""Shared staging lifetime, failure isolation and source immutability."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from model_publication_service import staged_model


class SharedPublicationStagingTests(unittest.TestCase):
    def test_staged_file_exists_during_upload_and_is_cleaned_afterward(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.fbx'
            source.write_bytes(b'artist source')
            def prepare(command, **kwargs):
                original, target, report = map(Path, command[-3:])
                self.assertEqual(original, source.resolve())
                self.assertNotEqual(target, source)
                self.assertEqual(kwargs['timeout'], 240)
                target.write_bytes(b'prepared skin')
                report.write_text(json.dumps({'schemaVersion':1,'restTransformsChanged':False}))
                return SimpleNamespace(returncode=0)
            with patch('model_publication_service.blender_executable',return_value=Path('blender')), patch('model_publication_service.subprocess.run',side_effect=prepare):
                with staged_model(root,source) as result:
                    self.assertEqual(result.read_bytes(),b'prepared skin')
                self.assertFalse(result.exists())
            self.assertEqual(source.read_bytes(),b'artist source')

    def test_failed_preparation_never_yields_an_upload_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source.fbx'; source.write_bytes(b'source')
            failure=SimpleNamespace(returncode=1,stderr='lost rest transform',stdout='')
            with patch('model_publication_service.blender_executable',return_value=Path('blender')), patch('model_publication_service.subprocess.run',return_value=failure):
                with self.assertRaisesRegex(ValueError,'lost rest transform'):
                    with staged_model(root,source):
                        self.fail('upload must not execute')
            self.assertEqual(source.read_bytes(),b'source')

    def test_all_blender_entrypoints_use_shared_mechanism(self):
        for name in ('character','real_estate','model'):
            source=(ROOT/f'system/asset-manager/prepare_{name}_publication_fbx.py').read_text(encoding='utf-8')
            self.assertIn('from model_publication import',source)
            self.assertNotIn('bpy.ops.export_scene.fbx',source)
            self.assertNotIn('plan_publication_weights(',source)
        for domain in ('location_asset','weapon'):
            source=(ROOT/f'system/control-center/{domain}_store.py').read_text(encoding='utf-8')
            self.assertIn('with staged_model(self.root, model) as publication:',source)


if __name__ == '__main__': unittest.main()
