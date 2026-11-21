"""M387: one per-house authoring contract; existing Location LOD scheduler remains authoritative."""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.house_runtime_profile import validate, readiness, DEFAULT
from real_estate.store import RealEstateStore, mesh_options
from api.real_estate import read as house_read, write as house_write

SLUG='house_level5_01'


def house(store):
    with store.connect() as db:
        db.execute('''INSERT INTO real_estate
            (slug,house_type,house_level,variant,purchase_price,min_level,sale_price,
             model_path,model_sha256,skeleton_json,textures_json,model_rigs_json,
             revision,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
             SLUG,'house',5,'01',1,1,1,'house.fbx','a'*64,
             json.dumps({'meshes':[{'name':'window_frames_glass','armature':'house_armature',
                 'bones':[{'name':'house_floor_01_spawn_socket','parent':''}], 'influencedBones':[]}]}),
             json.dumps({'window_frames_glass':{'path':'','filename':''}}),
             json.dumps({'rig_carrier':{'assetId':'123'}}),1,0,0))


class HouseRuntimeAuthoringM387(unittest.TestCase):
    def test_profile_validation_and_hysteresis(self):
        self.assertEqual(validate(SLUG,DEFAULT),DEFAULT)
        for bad in ({**DEFAULT,'mode':'lod2'}, {**DEFAULT,'lod1':True},
                    {**DEFAULT,'hide':150}, {**DEFAULT,'hysteresis':140},
                    {**DEFAULT,'newKey':'surprise'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate(SLUG,bad)
        with self.assertRaises(ValueError): validate('../escape',DEFAULT)

    def test_migration_preserves_house_and_plot_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            store=RealEstateStore(root)
            house(store)
            with store.connect() as db:
                db.execute('CREATE TABLE plot_binding_sample (plot INTEGER PRIMARY KEY, slug TEXT)')
                db.execute('INSERT INTO plot_binding_sample VALUES (39,?)',(SLUG,))
            # Repeated migration is idempotent; existing bindings remain intact.
            from services.house_lod_resource import ensure_schema
            ensure_schema(store); ensure_schema(store)
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT slug FROM plot_binding_sample WHERE plot=39').fetchone()[0],SLUG)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM real_estate').fetchone()[0],1)
            row=store.get(SLUG)
            self.assertEqual(row['lod1']['status'],'NOT_REGISTERED')
            self.assertEqual(row['runtimeProfile']['mode'],'off')
            self.assertEqual(row['partStreaming']['window_frames_glass']['lod1'],150)
            self.assertNotIn('loadDistanceStuds',row['meshOptions']['window_frames_glass'])

    def test_lod_stage_publish_profile_and_full_republication_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            store=RealEstateStore(root)
            house(store)
            fbx=root/(SLUG+'_lod1.fbx')
            fbx.write_bytes(b'Kaydara FBX Binary  \x00\x1a\x00' + b'x'*40)
            with self.assertRaisesRegex(ValueError,'per-part LOD1'):
                store.save_runtime_profile(SLUG,{**DEFAULT,'mode':'lod1'},0)
            lod=store.stage_lod1(SLUG,str(fbx),0)
            self.assertEqual(lod['status'],'STAGED')
            original = root/lod['sourcePath']
            self.assertTrue(original.is_file())
            self.assertEqual(store.stage_lod1(SLUG,str(fbx),1)['revision'],1)
            # New source bytes receive a new immutable filename; old revision survives.
            fbx.write_bytes(b'Kaydara FBX Binary  \x00\x1a\x00' + b'y'*40)
            second=store.stage_lod1(SLUG,str(fbx),1)
            self.assertNotEqual(second['sourcePath'],lod['sourcePath'])
            self.assertTrue(original.is_file())
            self.assertEqual(store.lod1_history(SLUG),[])
            lod=second
            with patch('services.model_lod_common.staged_model',return_value=nullcontext(fbx)), \
                 patch('services.model_lod_common.create_model_asset',return_value='op'), \
                 patch('services.model_lod_common.wait_for_operation',return_value=SimpleNamespace(asset_id='900123',moderation_state='APPROVED')):
                lod=store.publish_lod1(SLUG,2,{'apiKey':'test','creatorType':'Group','creatorId':'1'})
            self.assertEqual(lod['status'],'PUBLISHED')
            self.assertEqual(lod['modelAssetId'],'900123')
            self.assertEqual(store.lod1_history(SLUG)[0]['asset_id'],'900123')
            # Legacy whole-house LOD1 does NOT enable color-preserving runtime.
            with self.assertRaisesRegex(ValueError,'per-part LOD1'):
                store.save_runtime_profile(SLUG,{**DEFAULT,'mode':'lod1'},0)
            part_file=root/(SLUG+'_window_frames_glass_lod1.fbx')
            part_file.write_bytes(b'Kaydara FBX Binary  \x00\x1a\x00' + b'p'*40)
            part_lod=store.stage_part_lod1(SLUG,'window_frames_glass',str(part_file),0)
            with patch('services.house_part_lod_resource.publish_geometry',
                       return_value=SimpleNamespace(asset_id='900456',moderation_state='APPROVED')):
                part_lod=store.publish_part_lod1(SLUG,'window_frames_glass',part_lod['revision'],{})
            self.assertEqual(part_lod['status'],'PUBLISHED')
            # Per-part cutoff is owned only by LOD Manager, independent
            # of the Real Estate mesh appearance JSON.
            part_settings=store.get(SLUG)['partStreaming']['window_frames_glass']
            with self.assertRaisesRegex(ValueError,'room for shared hysteresis'):
                store.save_part_distances(SLUG,'window_frames_glass',
                                          {'lod1':160,'hide':175},part_settings['revision'])
            saved=store.save_part_distances(SLUG,'window_frames_glass',
                                            {'lod1':160,'hide':400},part_settings['revision'])
            self.assertEqual(saved['lod1'],160)
            settings=store.save_runtime_profile(SLUG,{**DEFAULT,'mode':'lod1'},0)
            self.assertEqual(settings['revision'],1)
            with self.assertRaisesRegex(ValueError,'changed'):
                store.save_runtime_profile(SLUG,{**DEFAULT,'mode':'full'},0)
            with store.connect() as db:
                db.execute('UPDATE real_estate SET model_sha256=? WHERE slug=?',('b'*64,SLUG))
            self.assertEqual(store.get(SLUG)['lod1']['status'],'FULL_CHANGED')
            self.assertFalse(store.get(SLUG)['runtimeReadiness']['readyForCompilation'])

    def test_routes_and_manifest_are_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            store=RealEstateStore(Path(directory));house(store)
            url=type('URL',(),{'path':'/api/real-estate/'+SLUG+'/lod1-history','query':''})()
            self.assertEqual(house_read(url,{'real_estate':store})[0],200)
            deps={'real_estate':store}
            path='/api/real-estate/'+SLUG+'/runtime-profile'
            payload={'profile':{**DEFAULT,'mode':'full'},'expectedRevision':0}
            self.assertEqual(house_write(path,lambda:payload,deps)[0],200)
            self.assertEqual(house_write(path,lambda:{'profile':DEFAULT},deps)[0],400)
            data=json.loads((store.root/'assets/manifests/real-estate.json').read_text())
            row=next(item for item in data['items'] if item['slug']==SLUG)
            self.assertEqual(row['runtimeProfile']['mode'],'full')
            self.assertEqual(row['runtimeProfile']['revision'],1)
            self.assertFalse(row['runtimeReadiness']['runtimeVerified'])

    def test_fixes_forcefield_distance_early_return(self):
        studio=(ROOT/'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text()
        segment=studio.split('function StudioTextureAppearance.ApplyVisual',1)[1].split('function StudioTextureAppearance.ApplyLocation',1)[0]
        self.assertNotIn('mesh.Color=color\n            return true',segment)
        self.assertIn('applied=true',segment)
        self.assertIn('StudioTextureAppearance.ApplyDistance(mesh, opts)',segment)

    def test_editor_preserves_existing_per_mesh_settings_and_no_duplicate_streamer(self):
        js=(ROOT/'system/control-center/static/real-estate.js').read_text()
        html=(ROOT/'system/control-center/static/index.html').read_text()
        client=(ROOT/'src/client/world/LocationWorldStreamer.luau').read_text()
        self.assertIn('id="real-estate-runtime-panel"',html)
        self.assertRegex(html,r'real-estate\.js\?v=385a&visual=\d+')
        self.assertNotIn('realEstateState.distance',js)
        self.assertIn('data-part-distance=\"lod1\"', (ROOT/'system/control-center/static/lod-manager.js').read_text())
        self.assertIn('/lod1-publish',(ROOT/'system/control-center/static/lod-manager.js').read_text())
        self.assertIn('LOD Manager → 02 · LOD readiness',js)
        self.assertNotIn('id="re-runtime-save"',js)
        self.assertIn('async function savePartDistances', (ROOT/'system/control-center/static/lod-manager.js').read_text())
        self.assertEqual(client.count('RunService.Heartbeat:Connect'),1)

if __name__=='__main__':unittest.main()
