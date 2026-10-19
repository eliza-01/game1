"""M108 hotfix: Blender entrypoint helper loading and actionable FBX errors."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.fbx import _blender_failure, _run


class BlenderInspectionHotfixTests(unittest.TestCase):
    def test_analyzer_loads_adjacent_helper_outside_project_pythonpath(self):
        """Blender's --python invocation must not rely on the working directory."""
        analyzer = ROOT / 'system/asset-manager/analyze_real_estate_fbx.py'
        program = textwrap.dedent('''
            import runpy, sys, types
            def stop_here(**kwargs):
                raise RuntimeError('FBX_MOCK_REACHED')
            sys.modules['bpy'] = types.SimpleNamespace(ops=types.SimpleNamespace(
                object=types.SimpleNamespace(select_all=stop_here)))
            sys.argv = ['blender', '--', 'input.fbx', 'output.json']
            runpy.run_path(%r, run_name='__main__')
        ''') % str(analyzer)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-I', '-c', program],
                                    cwd=tmp, text=True, capture_output=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FBX_MOCK_REACHED', result.stderr)
        self.assertNotIn('ModuleNotFoundError', result.stderr)

    def test_blender_runtime_error_reports_specific_invalid_fbx_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'analysis.json'
            stdout = ('Traceback (most recent call last):\n'
                      '  File "analyze_real_estate_fbx.py", line 37, in analyze\n'
                      'RuntimeError: Expected only mesh objects door, house. Found: house, door, walls.\n')
            with patch('real_estate.fbx.blender_executable', return_value=Path('blender')):
                with patch('real_estate.fbx.subprocess.run', return_value=SimpleNamespace(
                    returncode=1, stderr='', stdout=stdout)):
                    with self.assertRaisesRegex(ValueError, 'Found: house, door, walls'):
                        _run(root, 'analyze_real_estate_fbx.py', (root / 'model.fbx', target), report_path=target)

    def test_missing_helper_is_explained_instead_of_generic_error(self):
        diagnostic = "Traceback (most recent call last):\nModuleNotFoundError: No module named 'real_estate_rig_discovery'"
        message = _blender_failure(diagnostic, 1)
        self.assertIn('helper could not be loaded', message)
        self.assertIn('real_estate_rig_discovery', message)

    def test_blender_native_failure_reports_exit_code_and_last_line(self):
        message = _blender_failure('Blender quit\nFatal signal 11\n', -11)
        self.assertIn('exit code -11', message)
        self.assertIn('Fatal signal 11', message)


if __name__ == '__main__':
    unittest.main()
