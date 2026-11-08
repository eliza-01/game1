"""M259: the published FBX, not asset category, decides if a rig is needed."""
from __future__ import annotations

import json
import importlib.util
from types import SimpleNamespace
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/asset-manager'))
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_rig_contract import validate
from location_asset_store import LocationAssetStore
from services.location_rig_authoring import prepare_canonical_fbx
from services.mesh_authoring_policy import location_mesh_profile


IDENTITY=[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]
BONE={'name':'root','parent':'','matrix':IDENTITY}
STATIC_PARTS=[{'name':'bush','vertices':100},{'name':'col_mesh','vertices':20}]
SKINNED_PARTS=[{'name':'rig_carrier','vertices':3}]+STATIC_PARTS


def inspection(skinned=False):
    def mesh(name):
        p=location_mesh_profile(name,has_collider=True)
        return {'name':name,'vertices':3,'role':p['role'],'physics':p,
                'armature':('rig' if skinned else ''),
                'bones':([{'name':'root','parent':'','matrixLocal':IDENTITY}] if skinned else []),
                'influencedBones':(['root'] if skinned else [])}
    return {'schemaVersion':1,'meshes':[mesh('bush'),mesh('col_mesh')],
            'hasCollider':True,'armatures':['rig'] if skinned else [],
            'unassignedArmatures':[]}


class OptionalCarrierM259(TestCase):
    def test_static_manifest_is_canonical_without_any_carrier_or_bones(self):
        first=validate(STATIC_PARTS,[])
        self.assertEqual(first['schemaVersion'],2)
        self.assertEqual(first['rigKind'],'static')
        self.assertIsNone(first['carrierName'])
        self.assertEqual(first['bones'],[])
        self.assertEqual(first['structuralHash'],validate(STATIC_PARTS[::-1],[])['structuralHash'])

    def test_bones_require_carrier_and_unrigged_must_not_acquire_one(self):
        self.assertEqual(validate(SKINNED_PARTS,[BONE])['rigKind'],'skinned')
        with self.assertRaisesRegex(ValueError,'skinned.*rig_carrier'):
            validate(STATIC_PARTS,[BONE])
        with self.assertRaisesRegex(ValueError,'static.*must not contain'):
            validate(SKINNED_PARTS,[])
        with self.assertRaisesRegex(ValueError,'canonical lowercase'):
            validate([{'name':'Rig_Carrier','vertices':3}]+STATIC_PARTS,[BONE])

    def _store(self, root, analysis):
        source=root/'bush.fbx';source.write_bytes(b'original static FBX')
        atlas=root/'bush_32x32_atlas.png';Image.new('RGB',(32,32),(64,64,64)).save(atlas)
        store=LocationAssetStore(root)
        with mock.patch('location_asset_store.inspect_location_fbx',return_value=analysis):
            row=store.register({'nameEn':'Bush','slug':'bush','category':'bush',
                'modelSourcePath':str(source),'textureSourcePath':str(atlas),
                'inspectFbx':True})
        return store,row

    def test_old_static_publication_stays_current_without_v2_republish(self):
        with TemporaryDirectory() as directory:
            store,row=self._store(Path(directory),inspection())
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=?,model_published_sha256=? WHERE slug=?',
                           ('1222333444',row['model_sha256'],'bush'))
            current=store.get('bush')
            self.assertEqual(current['model_asset_id'],'1222333444')
            self.assertIsNone(current['rigManifest'])
            self.assertTrue(current['legacyStaticPublication'])
            self.assertFalse(any(m['bones'] for m in current['fbxAnalysis']['meshes']))
            with mock.patch('services.location_rig_authoring.run_report') as run:
                with self.assertRaisesRegex(ValueError,'no Bones'):
                    prepare_canonical_fbx(store,'bush',current['revision'])
                run.assert_not_called()
            self.assertEqual(store.get('bush')['model_asset_id'],'1222333444')
            self.assertEqual(store.get('bush')['model_sha256'],current['model_sha256'])

    def test_old_static_not_trusted_after_source_revision_or_unknown_analysis(self):
        with TemporaryDirectory() as directory:
            store,row=self._store(Path(directory),inspection())
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=?,model_published_sha256=? WHERE slug=?',
                           ('1222333444',row['model_sha256'],'bush'))
            self.assertTrue(store.get('bush')['legacyStaticPublication'])
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_published_sha256=? WHERE slug=?',('stale','bush'))
            self.assertFalse(store.get('bush')['legacyStaticPublication'])
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_published_sha256=? WHERE slug=?',(row['model_sha256'],'bush'))
            (Path(directory)/'assets/manifests/location-assets-fbx/bush.json').unlink()
            self.assertFalse(store.get('bush')['legacyStaticPublication'])
            self.assertTrue(store.get('bush')['needsFbxInspection'])

    def test_python_ui_policy_static_is_not_republished_for_missing_carrier(self):
        path=ROOT/'system/control-center/static/location-publication-state.js'
        code="""globalThis.window={};eval(require('fs').readFileSync(process.argv[1],'utf8'));
const row={model_path:'bush.fbx',model_asset_id:'1111',model_sha256:'same',
 model_published_sha256:'same',fbxAnalysis:{meshes:[{name:'bush',bones:[]},{name:'col_mesh',bones:[]}]}};
if (window.game1LocationPublication.needsCanonicalFbx(row))process.exit(1);
if (window.game1LocationPublication.plan(row).modelNeeded)process.exit(2);
row.fbxAnalysis.meshes[0].bones=[{name:'real_bone'}];
if (!window.game1LocationPublication.needsCanonicalFbx(row))process.exit(3);
if (!window.game1LocationPublication.plan(row).modelNeeded)process.exit(4);
row.fbxAnalysis.meshes.push({name:'rig_carrier',bones:[{name:'real_bone'}]});
if (window.game1LocationPublication.needsCanonicalFbx(row))process.exit(5);
if (window.game1LocationPublication.plan(row).modelNeeded)process.exit(6);
"""
        result=subprocess.run(['node','-e',code,str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_plugin_load_and_scan_validate_static_and_skinned_independently(self):
        base=ROOT/'system/studio-plugin/modules'
        carrier=(base/'StudioLocationRigCarrier.luau').read_text('utf-8')
        loader=(base/'DecoAssetLoader.luau').read_text('utf-8')
        inventory=(base/'StudioPlaceRegistryInventory.luau').read_text('utf-8')
        history=(base/'StudioPublishedMeshHistory.luau').read_text('utf-8')
        self.assertIn('manifest.rigKind == "static"',carrier)
        self.assertIn('function Carrier.IsCanonicalPublication',carrier)
        self.assertIn('static Location publication unexpectedly contains Bones',carrier)
        self.assertIn('if carrier then',loader)
        self.assertIn('legacyStaticPublication',loader)
        self.assertIn('CarrierRig.IsCanonicalPublication',inventory)
        self.assertIn('Carrier.IsCanonicalPublication',history)

    def test_blender_staging_inspects_unrigged_meshes_without_creating_skeleton(self):
        # Invoke the real Blender staging validator with model_publication/BPY
        # import boundaries stubbed. This tests behavior, not just source text.
        module_path=ROOT/'system/asset-manager/prepare_model_publication_fbx.py'
        fake_publication=SimpleNamespace(
            clean_scene=lambda:None,linked_meshes=lambda _:[],
            prepare_rig=lambda *a: (_ for _ in ()).throw(AssertionError('static must not prepare a rig')),
            export_model=lambda *a,**k:None,rest_snapshot=lambda x:None,
            assert_skin_complete=lambda *a:None)
        with mock.patch.dict(sys.modules,{'bpy':SimpleNamespace(),
                                           'model_publication':fake_publication}):
            spec=importlib.util.spec_from_file_location('test_static_publication_stage_m259',module_path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            objects=[SimpleNamespace(type='MESH',name='bush',data=SimpleNamespace(vertices=[1]*16)),
                     SimpleNamespace(type='MESH',name='col_mesh',data=SimpleNamespace(vertices=[1]*8))]
            manifest=module.location_manifest(objects)
            self.assertEqual(manifest['rigKind'],'static')
            self.assertEqual(manifest['bones'],[])
            self.assertEqual(len(manifest['parts']),2)

    def test_static_publication_stage_keeps_zero_bones(self):
        source=(ROOT/'system/asset-manager/prepare_model_publication_fbx.py').read_text('utf-8')
        author=(ROOT/'system/asset-manager/location_rig_authoring_fbx.py').read_text('utf-8')
        self.assertIn('Static FBX has no Bones and no carrier',source)
        self.assertNotIn('Static assets have a genuine minimal skeleton',author)
        self.assertIn('static Location can be published without rig_carrier',author)
