"""M258: user-initiated canonical source conversion before model upload."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
from location_asset_store import LocationAssetStore
from services.location_rig_authoring import prepare_canonical_fbx
from services.mesh_authoring_policy import normalize_location_options, location_mesh_profile


def inspection(carrier=False):
    def row(name):
        profile=location_mesh_profile(name,has_collider=True)
        bone={'name':'root', 'parent':'', 'matrixLocal':[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]}
        return {'name':name, 'vertices':3, 'armature':'armature', 'bones':[bone],
                'influencedBones':['root'], 'role':profile['role'], 'physics':profile}
    return {'schemaVersion':1,'meshes':([row('rig_carrier')] if carrier else [])+
            [row('lantern'), row('col_mesh')], 'hasCollider':True,
            'armatures':['armature'], 'unassignedArmatures':[]}


class AuthoringM258(TestCase):
    def setup_store(self, root):
        source=root/'lantern.fbx';source.write_bytes(b'old source FBX')
        atlas=root/'lantern_32x32_atlas.png';Image.new('RGBA',(32,32),(255,255,255,255)).save(atlas)
        store=LocationAssetStore(root)
        with mock.patch('location_asset_store.inspect_location_fbx',return_value=inspection()):
            asset=store.register({'nameEn':'Lantern', 'slug':'lantern', 'category':'light',
                                 'modelSourcePath':str(source),'textureSourcePath':str(atlas),
                                 'inspectFbx':True})
        return store, asset

    def fake_blender(self, root, script, args, *, report_path, label):
        self.assertEqual(script,'location_rig_authoring_fbx.py')
        source, generated, report = args
        self.assertIn(b'old source FBX',source.read_bytes())
        generated.write_bytes(b'genuine separate Blender-authored FBX')
        from location_rig_contract import validate
        bones=[{'name':'root','parent':'','matrix':[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]}]
        parts=[{'name':'rig_carrier','vertices':3}, {'name':'lantern','vertices':3},
               {'name':'col_mesh','vertices':3}]
        manifest=validate(parts,bones)
        manifest['sourceSha256']=hashlib.sha256(generated.read_bytes()).hexdigest()
        report.write_text(json.dumps(manifest),encoding='utf-8')
        return manifest

    def test_conversion_persists_authored_source_and_archives_old_without_changing_atlas_or_model_id(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);store,before=self.setup_store(root)
            with mock.patch('services.location_rig_authoring.run_report',side_effect=self.fake_blender), \
                 mock.patch('services.location_rig_authoring.inspect_fbx',return_value=inspection(True)), \
                 mock.patch('location_asset_store.inspect_location_fbx',return_value=inspection(True)):
                result=prepare_canonical_fbx(store,'lantern',before['revision'])
            after=store.get('lantern')
            self.assertEqual(result['resourceKind'],'ModelSource')
            self.assertEqual(after['revision'],before['revision']+1)
            self.assertEqual(after['model_asset_id'],before['model_asset_id'])
            self.assertEqual(after['texture_asset_id'],before['texture_asset_id'])
            self.assertEqual(after['atlasVariantId'],before['atlasVariantId'])
            self.assertNotEqual(after['model_sha256'],before['model_sha256'])
            self.assertEqual((root/after['model_path']).read_bytes(), b'genuine separate Blender-authored FBX')
            self.assertEqual((root/result['authoredSource']).read_bytes(),b'genuine separate Blender-authored FBX')
            archived=list((root/'assets/reimported/location-assets/lantern').rglob('lantern.fbx'))
            self.assertEqual(len(archived),1)
            self.assertEqual(archived[0].read_bytes(),b'old source FBX')
            self.assertEqual(len(list((root/'assets/authoring/location-assets/lantern').glob('*.manifest.json'))),1)
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM location_asset_publications').fetchone()[0],0)

    def test_stale_revision_or_blender_failure_does_not_touch_registration(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);store,before=self.setup_store(root)
            with mock.patch('services.location_rig_authoring.run_report') as stage:
                with self.assertRaisesRegex(ValueError,'changed'):
                    prepare_canonical_fbx(store,'lantern',before['revision']+1)
                stage.assert_not_called()
            with mock.patch('services.location_rig_authoring.run_report',side_effect=ValueError('broken bones')):
                with self.assertRaisesRegex(ValueError,'broken bones'):
                    prepare_canonical_fbx(store,'lantern',before['revision'])
            self.assertEqual(store.get('lantern')['revision'],before['revision'])
            self.assertEqual((root/before['model_path']).read_bytes(),b'old source FBX')

    def test_canonical_source_is_not_reauthored(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);store,before=self.setup_store(root)
            with mock.patch.object(store,'get',wraps=store.get) as get:
                # use actual inspect to add carrier via mock only for decorated analysis
                original=get('lantern');original['fbxAnalysis']=inspection(True)
                with mock.patch.object(store,'get',return_value=original), \
                     mock.patch('services.location_rig_authoring.run_report') as stage:
                    with self.assertRaisesRegex(ValueError,'already contains rig_carrier'):
                        prepare_canonical_fbx(store,'lantern',before['revision'])
                    stage.assert_not_called()

    def test_carrier_is_not_editable_physics_or_collide(self):
        analysis=inspection(True)
        self.assertEqual(location_mesh_profile('rig_carrier',has_collider=False)['role'],'carrier')
        self.assertFalse(location_mesh_profile('rig_carrier',has_collider=False)['canCollide'])
        self.assertEqual(set(normalize_location_options(analysis,{})),{'lantern','col_mesh'})
        with self.assertRaisesRegex(ValueError,'missing FBX meshes'):
            normalize_location_options(analysis,{'rig_carrier':{'noCollide':False}})

    def test_ui_marks_current_sha_with_legacy_source_as_publication_pending(self):
        path=ROOT/'system/control-center/static/location-publication-state.js'
        expression="""globalThis.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));
const row={model_path:'lantern.fbx', model_asset_id:'4321',
 model_sha256:'same',model_published_sha256:'same',
 fbxAnalysis:{meshes:[{name:'lantern',bones:[{name:'root'}]},{name:'col_mesh',bones:[]}]}};
if (!window.game1LocationPublication.plan(row).modelNeeded)process.exit(1);
row.fbxAnalysis.meshes.push({name:'rig_carrier',bones:[{name:'root'}]});
if (window.game1LocationPublication.plan(row).modelNeeded)process.exit(2);
"""
        check=subprocess.run(['node','-e',expression,str(path)],capture_output=True,text=True)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_failed_registration_restores_canonical_fbx(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);store,before=self.setup_store(root)
            original=store.register
            def failed_register(*args,**kwargs):
                canonical=root/before['model_path']
                canonical.write_bytes(b'partially copied new source')
                raise ValueError('metadata cannot commit')
            with mock.patch('services.location_rig_authoring.run_report',side_effect=self.fake_blender), \
                 mock.patch('services.location_rig_authoring.inspect_fbx',return_value=inspection(True)), \
                 mock.patch.object(store,'register',side_effect=failed_register):
                with self.assertRaisesRegex(ValueError,'metadata cannot commit'):
                    prepare_canonical_fbx(store,'lantern',before['revision'])
            self.assertEqual((root/before['model_path']).read_bytes(),b'old source FBX')
            self.assertEqual(store.get('lantern')['revision'],before['revision'])

    def test_ui_prepares_before_publish_without_changing_real_estate(self):
        workflow=(ROOT/'system/control-center/static/location-asset-workflow.js').read_text('utf-8')
        self.assertIn('prepare-canonical-fbx',workflow)
        self.assertIn("stage('model','Публикуем Model",workflow)
        self.assertLess(workflow.index("await prepareAuthoredRigIfMissing(label=>stage"),workflow.index("stage('model','Публикуем Model"))
        self.assertIn('rig_carrier', (ROOT/'system/control-center/static/mesh-authoring.js').read_text('utf-8'))
