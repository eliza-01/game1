"""M344: domain contract and Studio protocol regressions for whole-Model replacement."""
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
import socket
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system' / 'control-center'
sys.path.insert(0, str(CONTROL))
from services.location_instance_manager import LocationInstanceManager
from services.studio_location_instance_bridge import run_location_instance_bridge
from services.place_registry.catalog import build_catalog
from api.write_world import route as write_world


class FakeAssets:
    def snapshot(self):
        return {'items': [{'slug': slug, 'status':'PUBLISHED', 'model_asset_id':str(mid),
                           'model_published_sha256': 'a'*64, 'appearanceMode':'material',
                           'visualMaterial':'Slate', 'visualColor':'#7C7C7C'}
                          for slug, mid in [('stone_fence_01',12345),('stone_fence_02',67890)]]}

    def model_publication_ids(self, slug):
        return ['12345'] if slug=='stone_fence_01' else ['67890']

    def mesh_id_inventory(self, slug):
        return [{'modelAssetId': self.model_publication_ids(slug)[0],
                 'meshes':[{'meshId':'4567', 'count':1,'visualNames':[slug]}]}]

    def aliases_for(self, slug): return []
    def rig_manifest(self, slug, model): return None


class LocationInstanceManagerM344(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.manager=LocationInstanceManager(FakeAssets(), self.fake_bridge)

    def fake_bridge(self, **data):
        self.calls.append(data)
        return {'count':1,'scanToken':'f'*8+'-'+'f'*4+'-'+'f'*4+'-'+'f'*4+'-'+'f'*12,
                'placements':[{'name':'test','path':'Workspace.test','placementId':'f'*36, 'newPlacementId':'f'*36}],
                'reassignedIds':0, 'anchorOptions':[{'id':'model','label':'Model Pivot'}]}

    def test_only_explicit_published_slugs_and_scopes(self):
        base={'phase':'preview','sourceSlug':'stone_fence_01',
              'targetSlug':'stone_fence_02','scope':'selected','scanToken':'','anchorId':'model'}
        result=self.manager.operate(base)
        self.assertEqual(result['count'],1)
        self.assertEqual(self.calls[0]['catalog']['domain'],'location_assets')
        self.assertEqual(self.calls[0]['target_slug'],'stone_fence_02')
        self.assertEqual(self.calls[0]['anchor_id'],'model')
        for variant in ({**base,'sourceSlug':'unknown'}, {**base,'targetSlug':'unknown'},
                        {**base,'sourceSlug':'stone_fence_02'}, {**base,'scope':'workspace'},
                        {**base,'scanToken':'fake'}, {**base,'phase':'delete'},
                        {**base,'phase':'replace'}, {**base,'ignored':123}):
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.manager.operate(variant)
        self.assertEqual(len(self.calls),1)

    def test_api_routes_only_scoped_instance_manager_request(self):
        data={'phase':'preview','sourceSlug':'stone_fence_01','targetSlug':'stone_fence_02',
              'scope':'all','scanToken':'','anchorId':'model'}
        status, result = write_world('/api/location-instance-manager', lambda:data,
                                      {'location_instance_manager': self.manager})
        self.assertEqual(status,200)
        self.assertEqual(result['studio']['count'],1)
        status, result = write_world('/api/location-instance-manager', lambda:{'phase':'delete'},
                                      {'location_instance_manager': self.manager})
        self.assertEqual(status,400)
        self.assertIn('error',result)

    def test_studio_bridge_validates_scope_before_listening(self):
        catalog=build_catalog(FakeAssets())
        args={'catalog':catalog,'phase':'preview','source_slug':'stone_fence_01',
              'target_slug':'stone_fence_02','scope':'selected','anchor_id':'model'}
        for change in ({'phase':'delete'},{'scope':'all_place'},{'source_slug':'unknown'},
                       {'target_slug':'stone_fence_01'},{'phase':'replace'},
                       {'scan_token':'fake'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                run_location_instance_bridge(**{**args,**change},timeout_seconds=0.01)

    def test_authenticated_bridge_command_and_response(self):
        catalog=build_catalog(FakeAssets())
        token='12345678-1234-1234-1234-123456789abc'
        response={}
        def run_server():
            try:
                response['value']=run_location_instance_bridge(
                    catalog=catalog,phase='preview',source_slug='stone_fence_01',
                    target_slug='stone_fence_02',scope='selected',timeout_seconds=4)
            except Exception as exc:
                response['error']=str(exc)
        import services.studio_location_instance_bridge as bridge
        # Never bind the live Studio Bridge port during a developer's test run.
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            isolated_port = reserved.getsockname()[1]
        with patch.object(bridge, 'PORT', isolated_port):
            worker=threading.Thread(target=run_server,daemon=True)
            worker.start()
            command=None
            for _ in range(30):
                try:
                    request=Request(f'http://127.0.0.1:{isolated_port}/command',
                                    headers={'X-Game1-Token':bridge.TOKEN})
                    with urlopen(request,timeout=0.2) as reader: command=json.load(reader)
                    break
                except Exception:
                    time.sleep(0.05)
            self.assertIsNotNone(command)
            self.assertEqual(command['command'],'location-instance-replace-v3')
            self.assertEqual(command['anchorId'],'model')
            self.assertEqual(command['catalog']['digest'],catalog['digest'])
            result={k:command[k] for k in ('project','command','schemaVersion','operationId','phase','sourceSlug','targetSlug','scope','anchorId')}
            result['catalogDigest']=catalog['digest']
            result['result']={'count':1,'scanToken':token,'reassignedIds':0,'placements':[
                {'name':'fence','path':'Workspace.fence','placementId':token, 'newPlacementId':token}],
                'anchorOptions':[{'id':'model','label':'Model Pivot'},
                                 {'id':'mesh:1','label':'MeshPart 1 · fence'}]}
            request=Request(f'http://127.0.0.1:{isolated_port}/location-instance-result',method='POST',
                            headers={'X-Game1-Token':bridge.TOKEN,'Content-Type':'application/json'},
                            data=json.dumps(result).encode('utf-8'))
            with urlopen(request,timeout=1) as reader: self.assertEqual(json.load(reader),{'ok':True})
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(response.get('value',{}).get('count'),1,response)

    def test_ui_in_location_assets_bottom_and_compact(self):
        markup = (CONTROL/'static/index.html').read_text(encoding='utf-8')
        section = markup[markup.index('<div id="location-assets-view"'):markup.index('<div id="place-registry-view"')]
        self.assertIn('id="location-asset-editor-panel"', section)
        self.assertIn('id="location-new-registration-body" hidden', section)
        self.assertIn('id="location-asset-slug"', section)
        self.assertIn('id="li-scope"', section)
        self.assertGreater(section.index('id="location-instance-manager"'),
                           section.index('id="location-collision-panel"'))
        self.assertIn('location-instance-manager.js?v=347', markup)
        self.assertIn('id="li-anchor"', section)

    def test_luau_replaces_whole_model_without_touching_authoring(self):
        path=ROOT/'system/studio-plugin/modules/StudioLocationInstanceReplace.luau'
        script=path.read_text(encoding='utf-8')
        for method in ('TryBeginRecording','FinishRecording','loadPublished',
                       'StampPublishedModel','Collision.Prepare','Collision.Commit',
                       'positionAtSource(clone,old.frame,anchorId,approved)','"selected"','"all"','anchorOptions'):
            self.assertIn(method,script)
        self.assertNotIn('sameBounds',script)
        self.assertNotIn('Visual bounds differ',script)
        self.assertNotIn('PivotOffset =',script)
        self.assertNotIn('SetPrimaryPartCFrame',script)
        self.assertIn('StudioLocationInstanceReplace',
             (ROOT/'system/studio-plugin/plugin.project.json').read_text(encoding='utf-8'))
        main=(ROOT/'system/studio-plugin/Game1Bridge.server.luau').read_text(encoding='utf-8')
        self.assertIn('pcall(require, script.Parent.modules.StudioLocationInstanceReplace)',main)
        self.assertIn('elseif data.command == "location-place-registry"',main)


if __name__=='__main__':unittest.main()
