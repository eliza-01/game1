"""M232: contract-level tests for Estate/Location shared FBX authoring.

Mock Blender rather than claiming Studio Play was exercised. Real assets remain
on disk in actual project; these tests use only isolated tmp directories.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.mesh_authoring_policy import (mesh_defaults, normalize_mesh_options,
    normalize_location_options, location_mesh_profile)
from real_estate.collision_policy import normalize_collision_fidelity


def inspection():
    meshes=[]
    for name in ('visual', 'window_glass', 'col_mesh'):
        physics=location_mesh_profile(name, has_collider=True)
        meshes.append({'name':name, 'armature':'Armature' if name=='visual' else '',
                       'vertices':12, 'role':physics['role'], 'physics':physics,
                       'bones':([{'name':'root','parent':'','matrixLocal':[1.0]*16}]
                           if name=='visual' else []),
                       'influencedBones':['root'] if name=='visual' else []})
    return {'schemaVersion':1,'hasCollider':True,'meshes':meshes,
            'armatures':['Armature'],'unassignedArmatures':[]}


class LocationAuthoringM232(unittest.TestCase):
    def test_precise_for_every_collidable_mesh_in_both_domains(self):
        for name in ('col_mesh','Visual','glass','door'):
            flags=normalize_mesh_options(name,{'noCollide':False,'collisionFidelity':'Box'},
                has_collider=True,domain='location')
            self.assertEqual(flags['collisionFidelity'],'PreciseConvexDecomposition')
            self.assertEqual(normalize_collision_fidelity(name,'Box',no_collide=False),
                             'PreciseConvexDecomposition')
        self.assertEqual(normalize_mesh_options('visual',{'noCollide':True},
            has_collider=True,domain='location')['collisionFidelity'],'Box')
        self.assertEqual(mesh_defaults('col_mesh',has_collider=True,domain='location')['collisionFidelity'],
                         'PreciseConvexDecomposition')

    def test_collision_defaults_and_validation(self):
        defaults=normalize_location_options(inspection(),{})
        self.assertEqual(defaults['col_mesh']['noCollide'],False)
        self.assertEqual(defaults['col_mesh']['collisionFidelity'],'PreciseConvexDecomposition')
        self.assertEqual(defaults['visual']['collisionFidelity'],'Box')
        self.assertEqual(defaults['window_glass']['glass'],True)
        self.assertEqual(defaults['visual']['doubleSided'],False)
        self.assertEqual(mesh_defaults('tree',has_collider=False,domain='location')['noCollide'],False)
        for wrong in ({'not_in_fbx':{}},{'visual':{'noCollide':'false'}},
                      {'visual':{'collisionFidelity':'Bad'}},{'visual':'bad'}):
            with self.assertRaises(ValueError): normalize_location_options(inspection(),wrong)

    @staticmethod
    def _fixture(root):
        source=root/'campfire.fbx'; source.write_bytes(b'fake fbX data')
        atlas=root/'campfire_64x64_atlas.png'; Image.new('RGBA',(64,64),(1,2,3,255)).save(atlas)
        return source,atlas

    def test_preview_is_read_only_and_registration_persists_per_mesh(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,atlas=self._fixture(root);store=LocationAssetStore(root)
            with mock.patch('location_asset_store.inspect_location_fbx', return_value=inspection()):
                inspected=store.inspect_source_fbx(str(source))
                self.assertEqual(inspected['name'],'campfire')
                self.assertEqual(len(inspected['analysis']['meshes']),3)
                self.assertEqual(store.list(),[])
                flags=inspected['meshOptions']
                flags['visual']['noCollide']=False
                saved=store.register({'nameEn':'Campfire','category':'prop',
                    'modelSourcePath':str(source),'textureSourcePath':str(atlas),
                    'inspectFbx':True,'createOnly':True,'meshOptions':flags})
            self.assertEqual(saved['meshOptions']['visual']['collisionFidelity'],
                             'PreciseConvexDecomposition')
            self.assertEqual(saved['meshOptions']['col_mesh']['collisionFidelity'],
                             'PreciseConvexDecomposition')
            self.assertEqual(saved['fbxAnalysis']['armatures'],['Armature'])
            with store.connect() as db:
                row=db.execute('SELECT mesh_options_json FROM location_assets WHERE slug=?',('campfire',)).fetchone()
            self.assertIn('PreciseConvexDecomposition',row[0])
            lua=(root/'src/shared/world/LocationAssetRegistry.luau').read_text()
            self.assertIn('meshOptions = table.freeze(',lua)
            self.assertIn('col_mesh',lua)

    def test_save_settings_does_not_replace_model_id_or_fbx(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,atlas=self._fixture(root);store=LocationAssetStore(root)
            with mock.patch('location_asset_store.inspect_location_fbx', return_value=inspection()):
                old=store.register({'nameEn':'Campfire','category':'prop',
                    'modelSourcePath':str(source),'textureSourcePath':str(atlas),
                    'inspectFbx':True})
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=? WHERE slug=?',('12345',old['slug']))
            new=store.register({'slug':old['slug'],'nameEn':old['name_en'],
                    'category':old['category'],'editOnly':True,'expectedRevision':old['revision'],
                    'meshOptions':{'col_mesh':{'noCollide':False,'collisionFidelity':'Hull'}}})
            self.assertEqual(new['model_sha256'],old['model_sha256'])
            self.assertEqual(new['model_asset_id'],'12345')
            self.assertEqual(new['meshOptions']['col_mesh']['collisionFidelity'],
                             'PreciseConvexDecomposition')
            self.assertEqual(new['revision'],old['revision']+1)

    def test_legacy_database_migrates_with_backup_and_no_automatic_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); runtime=root/'.control-center';runtime.mkdir()
            db=sqlite3.connect(runtime/'game1.db')
            db.execute('''CREATE TABLE location_assets (slug TEXT PRIMARY KEY, name_en TEXT NOT NULL,
                category TEXT NOT NULL, model_path TEXT NOT NULL DEFAULT '',model_sha256 TEXT NOT NULL DEFAULT '',
                model_asset_id TEXT,model_published_sha256 TEXT NOT NULL DEFAULT '',
                model_moderation_state TEXT NOT NULL DEFAULT '',destructible INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                published_at REAL)''')
            db.execute("INSERT INTO location_assets(slug,name_en,category,created_at,updated_at) VALUES('oak','Oak','tree',1,2)")
            db.commit();db.close()
            store=LocationAssetStore(root)
            self.assertEqual(store.get('oak')['meshOptions'],{})
            self.assertTrue(list((runtime/'backups').glob('location_mesh_options_m232_*.sqlite')))

    @unittest.skipUnless(shutil.which('node'), 'Node.js needed for browser inspection test')
    def test_choose_fbx_renders_mesh_roles_skeleton_and_physics_before_save(self):
        """Exercise actual form handler, not just static presence of JS selectors."""
        script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=Object.create(null);
function $(id){return elements[id]??(elements[id]={value:'',textContent:'',innerHTML:'',
    hidden:false,options:[],querySelectorAll(){return []},addEventListener(){}});}
const inspection=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const calls=[];
async function request(url){
  calls.push(url);
  if(url==='/api/files/choose-location-asset-model')return {path:'C:/Assets/campfirte_01.fbx'};
  if(url==='/api/location-assets/inspect')return {
    sourcePath:'C:/Assets/campfirte_01.fbx',name:'campfirte_01',analysis:inspection};
  throw new Error('Unexpected API: '+url);
}
const ctx=vm.createContext({$,esc:s=>String(s??''),window:{},request,toast(){},
   localStorage:{getItem(){return null},setItem(){},removeItem(){}},console});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),ctx);
(async()=>{
 await vm.runInContext('decoAssetChooseModel()',ctx);
 assert.deepEqual(calls,['/api/files/choose-location-asset-model','/api/location-assets/inspect']);
 assert.equal($('location-asset-name').value,'campfirte 01');
 assert.equal($('location-asset-slug').value,'campfirte_01');
 const html=$('location-asset-fbx-preview').innerHTML;
 for(const name of ['visual','window_glass','col_mesh'])assert.ok(html.includes(name),name);
 assert.match(html,/Armature/);assert.match(html,/root/);
 assert.match(html,/Precise \(convex decomposition\)/);
 assert.match(html,/No Collide/);assert.match(html,/DoubleSided/);
 const options=vm.runInContext('decoAssetState.meshOptions',ctx);
 assert.equal(options.visual.collisionFidelity,'Box');
 assert.equal(options.col_mesh.collisionFidelity,'PreciseConvexDecomposition');
})().catch(err=>{console.error(err);process.exitCode=1;});
"""
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'analysis.json';report.write_text(json.dumps(inspection()))
            result=subprocess.run([shutil.which('node'),'-e',script,
                str(ROOT/'system/control-center/static/mesh-authoring.js'),
                str(ROOT/'system/control-center/static/deco-assets.js'),str(report)],
                capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_shared_adapters_and_ui_are_connected(self):
        core=(ROOT/'src/shared/world/MeshPhysicsCore.luau').read_text()
        loader=(ROOT/'system/studio-plugin/modules/DecoAssetLoader.luau').read_text()
        sync=(ROOT/'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text()
        service=(ROOT/'src/server/world/EnvironmentAssetService.luau').read_text()
        ui=(ROOT/'system/control-center/static/real-estate.js').read_text()
        location=(ROOT/'system/control-center/static/location-asset-workflow.js').read_text()
        registration=(ROOT/'system/control-center/static/deco-assets.js').read_text()
        route=(ROOT/'system/control-center/api/write_world.py').read_text()
        self.assertIn('Core.Apply(mesh, not noCollide, fidelity, doublesided)',core)
        self.assertIn('if canCollide then "PreciseConvexDecomposition" else fidelity',core)
        self.assertIn('MeshPhysics.ApplyLocationModel(model, nil, row.meshOptions)',loader)
        self.assertIn('Physics.ApplyLocationModel(model, allowedNames, row.meshOptions)',sync)
        self.assertIn('definition.meshOptions',service)
        self.assertIn('window.game1MeshAuthoring.controls(',ui)
        self.assertIn('window.game1MeshAuthoring.inspectionView(',location)
        self.assertIn('decoAssetInspectSource(chosen.path)',registration)
        self.assertIn("if path == '/api/location-assets/inspect':",route)


if __name__ == '__main__':unittest.main()
