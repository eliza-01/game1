"""M378: Real Estate's Blender --python entrypoint must find sibling helpers.

Blender does not promise that the script directory is in sys.path. Run the
entrypoint in an isolated Python subprocess with fake Blender API modules to
exercise the actual imports without requiring a Blender installation.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / 'system/asset-manager/prepare_real_estate_publication_fbx.py'
HELPER = ROOT / 'system/asset-manager/blender_rig_carrier.py'

# Mock ONLY the bpy runtime and downstream publication services; do not mock
# blender_rig_carrier. Its real file must be imported by the entrypoint.
_ISOLATED_BLENDER_BOOTSTRAP = r'''
import pathlib
import sys
import types

script = pathlib.Path(sys.argv[1]).resolve()
helper = script.parent / 'blender_rig_carrier.py'
assert str(script.parent) not in sys.path, 'test not isolated'

def fake_module(name, **members):
    module = types.ModuleType(name)
    module.__dict__.update(members)
    sys.modules[name] = module
    return module

class StopAfterImports(Exception):
    pass

def refuse_scene_mutation(**_kwargs):
    raise StopAfterImports()

bpy = fake_module('bpy')
bpy.ops = types.SimpleNamespace(object=types.SimpleNamespace(select_all=refuse_scene_mutation))
fake_module('mathutils', Vector=object)
fake_module('model_publication', prepare_rig=None, export_model=None)
fake_module('real_estate_rig_discovery', find_mesh=None, find_rig=None)
fake_module('real_estate_import_rigs', restore_authored_rigs=None)
fake_module('real_estate_staging_rig', isolated_rig=None)
services = fake_module('services')
services.__path__ = []
fake_module('services.retired_col_mesh', retired=None)
real_estate = fake_module('real_estate')
real_estate.__path__ = []
fake_module('real_estate.rig_publication_policy', publish_bones_for_mesh=None, publication_analysis=None, carrier_bones=None, validate_visual_weights=None)

pathlib.Path('textures.json').write_text('{}', encoding='utf-8')
sys.argv = ['blender', '--', 'source.fbx', 'output', 'textures.json', 'report.json']
try:
    exec(compile(script.read_bytes(), str(script), 'exec'), {
        '__name__': '__main__', '__file__': str(script)
    })
except StopAfterImports:
    pass
else:
    raise AssertionError('Publication entrypoint did not reach the Blender scene boundary')

carrier = sys.modules.get('blender_rig_carrier')
assert carrier is not None, 'Shared rig carrier was never imported'
assert pathlib.Path(carrier.__file__).resolve() == helper, carrier.__file__
assert callable(carrier.create_rig_carrier)
print('M378: Blender sibling rig_carrier loaded')
'''


class RealEstateBlenderBootstrapTests(unittest.TestCase):
    def test_blender_imports_adjacent_carrier_without_cwd_or_pythonpath(self):
        self.assertTrue(ENTRYPOINT.is_file())
        self.assertTrue(HELPER.is_file())
        with tempfile.TemporaryDirectory(prefix='m378-isolated-blender-') as cwd:
            # -I discards PYTHONPATH and the current working directory. This
            # reproduces the import boundary of Blender --python.
            result = subprocess.run(
                [sys.executable, '-I', '-c', _ISOLATED_BLENDER_BOOTSTRAP, str(ENTRYPOINT)],
                cwd=cwd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=20,
                env={**os.environ, 'PYTHONUTF8': '1'},
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('M378: Blender sibling rig_carrier loaded', result.stdout)


if __name__ == '__main__':
    unittest.main()
