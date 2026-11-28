"""Host/SQLite contracts and bounded Blender worker; native test is optional."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import test_m633_mnpc_lod_authoring as m633
REPORT, ROOT = m633.REPORT, m633.ROOT
from services import mnpc_lod_prepare as prepare
from api.write_world import route
from blender_runtime import blender_executable


class Preparation(unittest.TestCase):
    # Reuse fixture, not inherited tests.
    setUp = m633.MnpcAuthoring.setUp
    new_owner = m633.MnpcAuthoring.new_owner
    payload = m633.MnpcAuthoring.payload
    stage = m633.MnpcAuthoring.stage

    def request(self, kind='monster', **overrides):
        row = self.owner.describe(kind, 'same')
        return dict(posePath=str(self.fbx),texturePath=str(self.texture),frame=1,
                    targetTriangles=1000,textureSize=128,reviewedAssembly=True,
                    expectedRevision=row['revision'],fullFingerprint=row['fullFingerprint']) | overrides

    def worker(self, root, script, args, **kwargs):
        pose, output, report, frame, target = args
        self.assertEqual(script, 'prepare_mnpc_lod_fbx.py')
        self.assertNotEqual(pose, self.fbx)
        self.assertEqual(pose.read_bytes(), self.fbx.read_bytes())
        self.assertEqual(kwargs['timeout'], 120)
        output.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\ngenerated')
        return {'schemaVersion':1,'geometry':REPORT,'inputTriangles':4000,'inputMeshes':3,'poseMode':'posed_static'}

    def test_both_kinds_stage_same_pipeline_and_keep_source(self):
        original = self.fbx.read_bytes()
        Image.new('RGBA',(512,256),(20,40,60,128)).save(self.texture)
        with patch.object(prepare,'run_report',side_effect=self.worker) as blender:
            for kind in ('monster','npc'):
                row = self.owner.prepare(kind,'same',self.request(kind))
                self.assertEqual(row['status'],'STAGED')
                self.assertEqual(row['revision'],1)
                self.assertFalse(row['runtimeReady'])
                recipe = row['geometry']['preparation']
                self.assertEqual(recipe['inputTriangles'],4000)
                self.assertEqual(recipe['outputTextureSize'],[128,64])
                atlas = self.atlases.get_variant(row['atlasVariantId'])
                with Image.open(self.root / atlas['source_path']) as image:
                    pixel=image.getpixel((20,20))
                    self.assertEqual(pixel[3],128)
                    self.assertTrue(all(abs(actual-expected)<=1 for actual,expected in zip(pixel[:3],(20,40,60))))
                self.assertEqual(len(self.owner.history(kind,'same')),1)
                self.assertEqual(self.owner.prepare(kind,'same',self.request(kind))['revision'],1)
            self.assertEqual(blender.call_count,4)
        self.assertEqual(self.fbx.read_bytes(),original)
        self.inspect.assert_not_called() # generator used identical roundtrip inspector
        self.assertFalse((self.root/'src').exists())

    def test_validation_and_stale_inputs_before_worker(self):
        with patch.object(prepare,'run_report') as blender:
            for invalid in ({'reviewedAssembly':False},{'frame':True},{'textureSize':4096},
                            {'targetTriangles':99},{'expectedRevision':2},{'fullFingerprint':'old'}):
                with self.assertRaises(ValueError):
                    self.owner.prepare('monster','same',self.request(**invalid))
            blender.assert_not_called()
        self.assertEqual(self.owner.history('monster','same'),[])

    def test_failed_generation_and_changed_full_preserve_existing_revision(self):
        prior = self.stage()
        with patch.object(prepare,'run_report',side_effect=ValueError('No embedded idle')):
            with self.assertRaisesRegex(ValueError,'No embedded idle'):
                self.owner.prepare('monster','same',self.request())
        def changed(*args,**kwargs):
            result = self.worker(*args,**kwargs)
            self.monsters.rows['same']['model_asset_id']='999'
            return result
        with patch.object(prepare,'run_report',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'FULL changed'):
                self.owner.prepare('monster','same',self.request())
        row = self.owner.describe('monster','same')
        self.assertEqual(row['revision'],prior['revision'])
        self.assertEqual(row['sourceSha256'],prior['sourceSha256'])
        self.assertEqual(row['status'],'FULL_CHANGED')
        self.assertEqual(len(self.owner.history('monster','same')),1)

    def test_report_limits_and_source_mutation(self):
        def excessive(*args,**kwargs):
            result = self.worker(*args,**kwargs)
            result['geometry'] = {**REPORT,'triangles':1001}
            return result
        with patch.object(prepare,'run_report',side_effect=excessive):
            with self.assertRaisesRegex(ValueError,'geometry budget'):
                self.owner.prepare('monster','same',self.request())
        def changed(*args,**kwargs):
            result=self.worker(*args,**kwargs)
            self.fbx.write_bytes(b'changed')
            return result
        with patch.object(prepare,'run_report',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'inputs changed'):
                self.owner.prepare('monster','same',self.request())
        self.assertEqual(self.owner.describe('monster','same')['revision'],0)

    def test_http_prepare_is_separate_from_publish(self):
        with patch.object(prepare,'run_report',side_effect=self.worker):
            status,row=route('/api/lod-manager/mnpc/npc/same/prepare',lambda:self.request('npc'),{'mnpc_lod':self.owner})
        self.assertEqual(status,200)
        self.assertEqual(row['modelAssetId'],'')
        self.assertEqual(row['imageAssetId'],'')
        status,error=route('/api/lod-manager/mnpc/npc/same/prepare',lambda:{}, {'mnpc_lod':self.owner})
        self.assertEqual(status,400)


class NativeBlender(unittest.TestCase):
    def test_static_two_piece_roundtrip(self):
        try:
            exe=blender_executable()
        except RuntimeError:
            self.skipTest('Native Blender not installed; no engine claim')
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            fixture=directory/'fixture.py'
            source=directory/'posed.fbx'
            fixture.write_text('''import bpy, sys
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for x in (-2,2):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=(x,0,1))
bpy.ops.export_scene.fbx(filepath=sys.argv[sys.argv.index('--')+1],object_types={'MESH'},bake_anim=False,add_leaf_bones=False,axis_forward='-Z',axis_up='Y')
''',encoding='utf-8')
            result=subprocess.run([str(exe),'--background','--factory-startup','--python-exit-code','1','--python',str(fixture),'--',str(source)],capture_output=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            atlas=directory/'source.png';Image.new('RGB',(256,256),'red').save(atlas)
            work=directory/'work';work.mkdir()
            output,texture,recipe,report,digest=prepare.prepare(ROOT,'example',dict(posePath=str(source),texturePath=str(atlas),frame=1,
                targetTriangles=400,textureSize=128,reviewedAssembly=True,expectedRevision=0,fullFingerprint='fixture'),work)
            self.assertTrue(output.is_file() and texture.is_file())
            self.assertEqual(recipe['inputMeshes'],2)
            self.assertEqual(report['armatures'],0)
            self.assertLessEqual(report['triangles'],400)
