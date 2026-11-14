"""M343B regression: Location collision authoring never touches Place/Plots."""
from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.location_collision_authoring import LocationCollisionAuthoring
from services import studio_location_collision_bridge as transport
from api.read_world import route as read_route
from api.write_world import route as write_route


BLUEPRINT = {'schemaVersion': 1, 'pivot': 'Model:GetPivot()', 'parts': [
    {'id':'wall_01','name':'wall_01','shape':'Block','size':[4,5,0.3],
     'localCFrame':[0,1,0,1,0,0,0,1,0,0,0,1],
     'collisionGroup':'Default','canQuery':True,'canTouch':False}
]}


def registered_store(root):
    store = LocationAssetStore(root)
    with store.connect() as db:
        db.execute('INSERT INTO location_assets(slug,name_en,category,model_asset_id,created_at,updated_at) '
                   'VALUES(?,?,?,?,?,?)', ('stone_fence_01', 'Stone Fence', 'fence', '555', 0.0, 0.0))
        db.execute('INSERT INTO location_asset_mesh_id_inventory '
                   '(asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?)',
                   ('stone_fence_01','555',json.dumps([{'meshId':'139744616815788',
                       'count':1,'visualNames':['stone_fence_01']}]),1.0))
    return store


class LocationCollisionStudioM343B(unittest.TestCase):
    def test_validate_capture_revisions_diff_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = registered_store(Path(tmp))
            calls = []

            def studio(**kwargs):
                calls.append(kwargs)
                if kwargs['phase'] in ('validate','capture'):
                    return {'blueprint': json.loads(json.dumps(BLUEPRINT))}
                return {'partCount':len((kwargs.get('blueprint') or {}).get('parts',[]))}

            service = LocationCollisionAuthoring(store,studio)
            view=service.operate('stone_fence_01','validate')
            self.assertEqual(view['revision'],0)
            self.assertEqual(view['diff']['added'],['wall_01'])
            self.assertIsNone(store.collision_blueprint('stone_fence_01'))
            result=service.operate('stone_fence_01','capture')
            self.assertTrue(result['changed'])
            self.assertEqual(result['revision'],1)
            again=service.operate('stone_fence_01','capture')
            self.assertFalse(again['changed'])
            self.assertEqual(again['revision'],1)
            self.assertEqual(service.operate('stone_fence_01','preview')['partCount'],1)
            self.assertEqual(calls[-1]['expected_revision'],1)
            self.assertEqual(calls[-1]['blueprint']['parts'][0]['id'],'wall_01')
            self.assertEqual(service.operate('stone_fence_01','clear-preview')['partCount'],0)
            self.assertEqual(store.collision_blueprint_history('stone_fence_01')[0]['partCount'],1)
            self.assertEqual(len(store.collision_blueprint_history('stone_fence_01')),1)

            status, data=read_route(type('URL',(),{'path':'/api/location-assets/stone_fence_01/collision-history','query':'limit=10'})(),
                                    {'location_assets':store},lambda:{})
            self.assertEqual(status,200)
            self.assertEqual(data['history'][0]['revision'],1)

    def test_failed_studio_and_race_never_override_blueprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=registered_store(Path(tmp))
            def malformed(**_kwargs):
                return {'blueprint':{'schemaVersion':1,'pivot':'Model:GetPivot()','parts':[
                    {**BLUEPRINT['parts'][0], 'shape':'MeshPart'}]}}
            service=LocationCollisionAuthoring(store,malformed)
            with self.assertRaisesRegex(ValueError,'shape'):
                service.operate('stone_fence_01','capture')
            self.assertIsNone(store.collision_blueprint('stone_fence_01'))
            with self.assertRaisesRegex(ValueError,'Capture'):
                service.operate('stone_fence_01','preview')
            with self.assertRaisesRegex(ValueError,'unknown registered'):
                service.operate('invalid_asset','capture')

            def racing(**kwargs):
                store.save_collision_blueprint(kwargs['slug'],
                    {'expectedRevision':kwargs['expected_revision'],'blueprint':BLUEPRINT})
                return {'blueprint': BLUEPRINT}
            service=LocationCollisionAuthoring(store,racing)
            with self.assertRaisesRegex(ValueError,'changed since Capture'):
                service.operate('stone_fence_01','capture')
            self.assertEqual(store.collision_blueprint('stone_fence_01')['revision'],1)

    def test_api_explicit_phase_only_and_real_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=registered_store(Path(tmp))
            service=LocationCollisionAuthoring(store,lambda **kw: {'blueprint':BLUEPRINT})
            route_deps={'location_collision_authoring':service}
            status, result=write_route('/api/location-assets/stone_fence_01/collision-studio',
                                      lambda:{'phase':'capture'},route_deps)
            self.assertEqual(status,200)
            self.assertEqual(result['studio']['revision'],1)
            status, result=write_route('/api/location-assets/stone_fence_01/collision-studio',
                                      lambda:{'phase':'capture','unrelated':True},route_deps)
            self.assertEqual(status,400)
            status, result=write_route('/api/location-assets/stone_fence_01/collision-studio',
                                      lambda:{'phase':'place'},route_deps)
            self.assertEqual(status,400)

    def test_http_transport_authorizes_and_rejects_bad_identity(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        result={}
        def run():
            try:
                result['data']=transport.run_location_collision_bridge(
                    slug='stone_fence_01', phase='capture', expected_revision=4,
                    expected_versions=[{'modelAssetId':'555',
                        'meshes':[{'meshId':'139744616815788','count':1}]}],
                    timeout_seconds=7)
            except Exception as exc:
                result['error']=exc
        with patch.object(transport,'PORT',port):
            thread=threading.Thread(target=run,daemon=True)
            thread.start()
            url=f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    with urlopen(Request(url+'/command',headers={'X-Game1-Token':transport.TOKEN}), timeout=1) as req:
                        command=json.load(req)
                    break
                except OSError:
                    time.sleep(0.02)
            else:
                self.fail('Studio transport did not start')
            self.assertEqual(command['slug'],'stone_fence_01')
            self.assertEqual(command['expectedRevision'],4)
            self.assertEqual(command['expectedVersions'][0]['meshes'][0]['meshId'],
                             '139744616815788')
            def post(payload,token=transport.TOKEN):
                req=Request(url+'/location-collision-result',
                    data=json.dumps(payload).encode(),headers={'X-Game1-Token':token,'Content-Type':'application/json'},
                    method='POST')
                return urlopen(req,timeout=2)
            bad={**command,'operationId':'other','blueprint':BLUEPRINT}
            with self.assertRaises(HTTPError) as failure:
                post(bad)
            self.assertEqual(failure.exception.code,400)
            with self.assertRaises(HTTPError) as failure:
                post({**command,'blueprint':BLUEPRINT},'wrong')
            self.assertEqual(failure.exception.code,403)
            with post({**command,'blueprint':BLUEPRINT}) as answer:
                self.assertEqual(answer.status,200)
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertNotIn('error',result)
            self.assertEqual(result['data']['blueprint'],BLUEPRINT)

    def test_studio_module_is_optional_and_no_place_or_mesh_collision(self):
        root=ROOT/'system/studio-plugin'
        manifest=json.loads((root/'plugin.project.json').read_text(encoding='utf-8'))
        self.assertIn('StudioLocationCollisionAuthoring',manifest['tree']['modules'])
        plugin=(root/'Game1Bridge.server.luau').read_text(encoding='utf-8')
        studio=(root/'modules/StudioLocationCollisionAuthoring.luau').read_text(encoding='utf-8')
        self.assertIn('pcall(require, script.Parent.modules.StudioLocationCollisionAuthoring)',plugin)
        self.assertIn('StudioPlotsVisibility.new',plugin)
        self.assertIn('StudioPlaceRegistryCommands',plugin)
        self.assertIn('location-collision-authoring-v1',plugin)
        self.assertNotIn('CollisionAuthoring must contain',studio)
        self.assertNotIn('if part.CanCollide then',studio)
        self.assertIn('selectedModel(config.Selection, workspaceRef, command, requiresParts)',studio)
        self.assertIn('sameInventory(root, version)',studio)
        self.assertIn('table.insert(parts, item)',studio)
        self.assertIn('ghost.CanCollide = false',studio)
        self.assertIn('ghost.CanQuery = false',studio)
        self.assertIn('ghost.CanTouch = false',studio)
        self.assertIn('not root:IsDescendantOf(workspaceRef)',studio)
        self.assertNotIn('root:IsDescendantOf(container)',studio)
        self.assertNotIn('SetAttribute("Game1DecoPlacement',studio)
        self.assertNotIn('Destroy() -- place',studio)
        self.assertIn('pcall(controller.dispose)',plugin)
        self.assertIn('pcall(collisionController.handle, data)',plugin)
        self.assertLess(plugin.index('local handlePlaceRegistry ='), plugin.index('local collisionModuleOk'))

    def test_ui_wiring_and_no_physics_preview(self):
        root=ROOT/'system/control-center/static'
        page=(root/'index.html').read_text(encoding='utf-8')
        js=(root/'location-collision.js').read_text(encoding='utf-8')
        for name in ('location-collision-validate','location-collision-capture',
                     'location-collision-preview','location-collision-clear',
                     'location-collision-asset','location-collision-status'):
            self.assertIn(f'id="{name}"',page)
        self.assertIn('location-collision.js?v=3431',page)
        self.assertIn('collision-studio',js)
        self.assertIn('collision-history',js)
        self.assertIn('window.game1LocationCollisionSelect',js)
        self.assertIn('location-collision-panel',page)
        from html.parser import HTMLParser
        class DivScope(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack=[]
                self.parents={}
            def handle_starttag(self, tag, attrs):
                if tag == 'div':
                    identity=dict(attrs).get('id') or ''
                    self.parents[identity]=tuple(self.stack)
                    self.stack.append(identity)
            def handle_endtag(self, tag):
                if tag == 'div' and self.stack:
                    self.stack.pop()
        parsed=DivScope()
        parsed.feed(page)
        self.assertIn('location-assets-view',parsed.parents['location-collision-panel'])
        self.assertNotIn('location-assets-view',parsed.parents['place-registry-view'])


if __name__ == '__main__':
    unittest.main()
