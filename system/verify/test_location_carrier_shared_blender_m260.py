"""M260 regression: one Character/Location carrier authoring helper and visible failure."""
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'system/asset-manager'


class V(tuple):
    def __add__(self, other):
        return V(a + b for a, b in zip(self, other))


class CarrierTest(TestCase):
    def test_both_domains_use_one_authored_carrier_implementation(self):
        character = (ASSETS / 'character_components_fbx.py').read_text('utf8')
        location = (ASSETS / 'location_rig_authoring_fbx.py').read_text('utf8')
        for source in (character, location):
            self.assertIn('from blender_rig_carrier import create_rig_carrier', source)
            self.assertIn('create_rig_carrier(', source)
            self.assertNotIn("bpy.data.meshes.new('rig_carrier')", source)
        self.assertNotIn('def add_carrier(', location)
        self.assertIn('sys.path.insert(0, str(Path(__file__).resolve().parent))', location)

    def test_location_blender_entrypoint_resolves_shared_helpers_without_cwd_or_pythonpath(self):
        # Blender --python does not guarantee the script directory is in sys.path.
        # In this separate interpreter, explicitly omit it and stub Blender APIs;
        # all our own modules must resolve from the entrypoint's injected path.
        script = '''import runpy,sys,types
from pathlib import Path
p=Path(sys.argv[1]).resolve()
sys.path=[x for x in sys.path if Path(x or '.').resolve()!=p.parent]
for module in ('model_publication','location_rig_contract','blender_rig_carrier'):
    sys.modules.pop(module,None)
bpy=types.ModuleType('bpy'); sys.modules['bpy']=bpy
mathutils=types.ModuleType('mathutils');mathutils.Vector=lambda value:value
sys.modules['mathutils']=mathutils
loaded=runpy.run_path(str(p),run_name='m260_import_test')
assert callable(loaded['main'])
assert callable(loaded['create_rig_carrier'])
import model_publication
assert Path(model_publication.__file__).parent.resolve()==p.parent
'''
        result = subprocess.run([sys.executable, '-I', '-c', script,
            str(ASSETS / 'location_rig_authoring_fbx.py')], cwd=str(ROOT),
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shared_carrier_has_character_geometry_and_every_bone_is_weighted(self):
        bones = [SimpleNamespace(name='root', head_local=V((0, 0, 0))),
                 SimpleNamespace(name='leaf', head_local=V((1, 2, 3)))]
        calls = []
        mesh_data = SimpleNamespace(from_pydata=lambda verts, edges, faces: calls.append(
            (list(verts), list(edges), list(faces))), update=lambda:None)
        groups = {}
        def group(name):
            group = SimpleNamespace(add=lambda ids, weight, mode: groups.setdefault(name, (
                ids, weight, mode)))
            return group
        modifier = SimpleNamespace(object=None)
        carrier = SimpleNamespace(name='rig_carrier', type='MESH', parent=None, matrix_world=None,
            vertex_groups=SimpleNamespace(new=lambda name:group(name)),
            modifiers=SimpleNamespace(new=lambda *_:modifier))
        rig = SimpleNamespace(type='ARMATURE', data=SimpleNamespace(bones=bones),
            matrix_world=SimpleNamespace(copy=lambda:'world'))
        bpy = ModuleType('bpy')
        bpy.context = SimpleNamespace(scene=SimpleNamespace(objects=[], collection=SimpleNamespace(
            objects=SimpleNamespace(link=lambda obj:None))))
        bpy.data = SimpleNamespace(meshes=SimpleNamespace(new=lambda name:mesh_data),
                                   objects=SimpleNamespace(new=lambda name,data:carrier))
        mathutils = ModuleType('mathutils'); mathutils.Vector = V
        spec = importlib.util.spec_from_file_location('m260_blender_carrier',
            ASSETS/'blender_rig_carrier.py')
        helper = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {'bpy':bpy, 'mathutils':mathutils}):
            spec.loader.exec_module(helper)
            actual = helper.create_rig_carrier(rig)
            self.assertIs(actual,carrier)
            self.assertIs(actual.parent,rig)
            self.assertEqual(actual.matrix_world,'world')
            self.assertIs(modifier.object,rig)
            self.assertEqual(len(calls),1)
            self.assertEqual(len(calls[0][0]),6)
            self.assertEqual(len(calls[0][2]),2)
            self.assertEqual(groups['root'],([0,1,2],1.0,'REPLACE'))
            self.assertEqual(groups['leaf'],([3,4,5],1.0,'REPLACE'))
            bpy.context.scene.objects.append(carrier)
            with self.assertRaisesRegex(ValueError,'already exists'):
                helper.create_rig_carrier(rig)
            with self.assertRaisesRegex(ValueError,'existing armature'):
                helper.create_rig_carrier(SimpleNamespace(type='ARMATURE',data=SimpleNamespace(bones=[])))

    def test_ui_error_visible_and_busy_state_always_finishes(self):
        source=(ROOT/'system/control-center/static/location-asset-workflow.js').read_text('utf8')
        self.assertIn('finally{state.busy=false;state.operationLabel=\'\';render();}',source)
        self.assertIn('role="alert"',source)
        self.assertIn('state.error?0:scrollBody',source)
        self.assertIn("state.tab!=='publish'",source)
        self.assertNotIn("state.tab!=='model'",source)
        self.assertIn('Preserve the original publication failure',source)
