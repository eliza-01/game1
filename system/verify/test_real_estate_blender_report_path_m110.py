"""M110: rig-name arguments must not be mistaken for Blender report paths."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate import fbx
from test_real_estate_m107 import skeleton


class RealEstateBlenderReportTests(unittest.TestCase):
    def test_two_rig_export_and_followup_inspection_with_trailing_part_names(self):
        with tempfile.TemporaryDirectory(prefix='m110-real-estate-') as temp:
            base = Path(temp)
            source = base / 'source.fbx'
            source.write_bytes(b'fixture; no real Blender needed')
            dest = base / 'prepared'
            observed = []
            validated = []

            def emulate_blender(argv, **kwargs):
                self.assertIn('--', argv)
                cli = argv[argv.index('--') + 1:]
                name = Path(argv[argv.index('--python') + 1]).name
                observed.append((name, cli))
                if name == 'prepare_real_estate_publication_fbx.py':
                    self.assertEqual(len(cli), 4)
                    self.assertEqual(Path(cli[0]), source)
                    self.assertEqual(Path(cli[1]), dest)
                    for part in ('house', 'door'):
                        (dest / f'{part}.fbx').write_bytes(b'fixture')
                    report_file = Path(cli[3])
                    report_file.write_text(json.dumps({'schemaVersion': 2, 'rigAssets':{'house':'house.fbx','door':'door.fbx'}}), encoding='utf-8')
                elif name == 'analyze_real_estate_fbx.py':
                    self.assertEqual(len(cli), 3)
                    self.assertIn(cli[-1], ('house', 'door'))
                    self.assertEqual(Path(cli[0]).stem, cli[-1])
                    report_file = Path(cli[1])
                    report_file.write_text(json.dumps({'part': cli[-1]}), encoding='utf-8')
                else:
                    self.fail(f'Unexpected Blender script {name}')
                return SimpleNamespace(returncode=0, stderr='', stdout='')

            with patch('real_estate.fbx.blender_executable', return_value=Path('blender')), \
                 patch('real_estate.fbx.subprocess.run', side_effect=emulate_blender), \
                 patch('real_estate.contracts.assert_rig_survived',
                       side_effect=lambda expected, actual, part: validated.append((part, actual['part']))):
                result = fbx.prepare_publication(base, source, dest, skeleton(),
                                                 {'house': str(base/'a.png'), 'door': str(base/'b.png')})

            self.assertEqual(result['schemaVersion'], 2)
            self.assertEqual(validated, [('house', 'house'), ('door', 'door')])
            self.assertEqual([name for name, _ in observed], [
                'prepare_real_estate_publication_fbx.py',
                'analyze_real_estate_fbx.py', 'analyze_real_estate_fbx.py'])

    def test_missing_json_report_yields_readable_error(self):
        with tempfile.TemporaryDirectory(prefix='m110-real-estate-') as temp:
            directory = Path(temp)
            source = directory / 'source.fbx'
            source.write_bytes(b'fixture')
            with patch('real_estate.fbx.blender_executable', return_value=Path('blender')), \
                 patch('real_estate.fbx.subprocess.run',
                       return_value=SimpleNamespace(returncode=0, stderr='', stdout='')):
                with self.assertRaisesRegex(ValueError, 'JSON report'):
                    fbx.inspect(directory, source)


if __name__ == '__main__':
    unittest.main()
