"""M345 transport regression, updated to M347 target-pivot semantics."""
import json
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system/control-center'
sys.path.insert(0, str(CONTROL))
from services.location_instance_manager import LocationInstanceManager
from services.studio_location_instance_bridge import run_location_instance_bridge
from services.place_registry.catalog import build_catalog
from studio_bridge import StudioBridgeError
from test_location_instance_manager_m344 import FakeAssets


class PivotChoiceM345(unittest.TestCase):
    def test_target_mesh_pivot_selection_is_transported(self):
        calls = []
        def fake_bridge(**kwargs):
            calls.append(kwargs)
            return {'count': 1, 'changed': 1, 'scanToken': 'a'*36,
                    'anchorOptions': [{'id':'model', 'label':'Model Pivot'},
                                      {'id':'mesh:1', 'label':'MeshPart 1'},
                                      {'id':'mesh:2', 'label':'MeshPart 2'}]}
        manager = LocationInstanceManager(FakeAssets(), fake_bridge)
        base = dict(sourceSlug='stone_fence_01', targetSlug='stone_fence_02',scope='all')
        manager.operate({**base,'phase':'preview','scanToken':'','anchorId':'model'})
        manager.operate({**base,'phase':'replace','scanToken':'a'*36,'anchorId':'mesh:2'})
        self.assertEqual([p['anchor_id'] for p in calls], ['model', 'mesh:2'])
        self.assertEqual([p['scope'] for p in calls], ['all','all'])

    def test_invalid_pivot_ids_rejected_before_contacting_studio(self):
        calls = []
        manager = LocationInstanceManager(FakeAssets(), lambda **kw: calls.append(kw))
        base = dict(sourceSlug='stone_fence_01',targetSlug='stone_fence_02',scope='selected',
                    phase='replace',scanToken='a'*36)
        for anchor in ('mesh:0','mesh:01','mesh:-1','mesh:', 'mesh:a','mesh:1/2',
                       'mesh:10000000','mesh:1\\0','other',None,3,{},[]):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                manager.operate({**base,'anchorId':anchor})
        with self.assertRaises(ValueError):
            manager.operate({**base,'phase':'preview','scanToken':'','anchorId':'mesh:1'})
        self.assertEqual(calls, [])

    def test_authenticated_v3_transport_passes_mesh_anchor(self):
        catalog = build_catalog(FakeAssets())
        import services.studio_location_instance_bridge as bridge
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0))
            isolated_port = reserved.getsockname()[1]
        response = {}
        token = '12345678-1234-1234-1234-123456789abc'
        with patch.object(bridge,'PORT',isolated_port):
            def run_server():
                try:
                    response['value'] = run_location_instance_bridge(
                        catalog=catalog,phase='replace',source_slug='stone_fence_01',
                        target_slug='stone_fence_02',scope='selected',scan_token=token,
                        anchor_id='mesh:2',timeout_seconds=4)
                except Exception as exc:
                    response['error'] = str(exc)
            worker = threading.Thread(target=run_server,daemon=True)
            worker.start()
            command = None
            for _ in range(40):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{isolated_port}/command',
                                  headers={'X-Game1-Token':bridge.TOKEN}),timeout=0.2) as reader:
                        command=json.load(reader)
                    break
                except Exception:
                    time.sleep(0.05)
            self.assertIsNotNone(command)
            self.assertEqual(command['anchorId'],'mesh:2')
            self.assertEqual(command['schemaVersion'],3)
            wrong = {k:command[k] for k in ('project','command','schemaVersion','operationId',
                                          'phase','sourceSlug','targetSlug','scope','anchorId')}
            wrong['catalogDigest']=catalog['digest']
            wrong['anchorId']='mesh:1'
            wrong['result']={'count':1,'changed':1}
            def send(data):
                return urlopen(Request(f'http://127.0.0.1:{isolated_port}/location-instance-result',
                                       method='POST',headers={'X-Game1-Token':bridge.TOKEN,
                                                              'Content-Type':'application/json'},
                                       data=json.dumps(data).encode()), timeout=1)
            with self.assertRaises(HTTPError) as caught:
                send(wrong)
            self.assertEqual(caught.exception.code,400)
            good = dict(wrong,anchorId='mesh:2')
            with send(good) as reader:
                self.assertEqual(json.load(reader),{'ok':True})
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(response.get('value',{}).get('changed'),1,response)

    def test_target_mesh_anchor_and_model_scale_alignment(self):
        code = (ROOT/'system/studio-plugin/modules/StudioLocationInstanceReplace.luau').read_text(encoding='utf8')
        for expected in ('local function anchorOptions(target:',
                         'local function selectedTargetAnchor(target:',
                         'local function positionAtSource(target:',
                         'sourceFrame * originalAnchorFrame:Inverse() * originalModelFrame',
                         'positionAtSource(clone,old.frame,anchorId,approved)',
                         'clone:ScaleTo(old.scale)',
                         'selectedTargetAnchor(clone,anchorId,approved)',
                         'Collision.Prepare(', 'TryBeginRecording',
                         'not current.approved[command.anchorId]'):
            self.assertIn(expected,code)
        for obsolete in ('sameBounds(', 'Visual bounds differ',
                         'local function sourceAnchor(',
                         'sourceAnchor(old,anchorId,approved)',
                         'pair.before.root:Destroy()'):
            self.assertNotIn(obsolete,code)
        self.assertIn('pcall(require, script.Parent.modules.StudioLocationInstanceReplace)',
                      (ROOT/'system/studio-plugin/Game1Bridge.server.luau').read_text(encoding='utf8'))

    def test_ui_and_plugin_share_version_and_dropdown(self):
        html=(CONTROL/'static/index.html').read_text(encoding='utf8')
        js=(CONTROL/'static/location-instance-manager.js').read_text(encoding='utf8')
        lua=(ROOT/'system/studio-plugin/Game1Bridge.server.luau').read_text(encoding='utf8')
        install=(ROOT/'system/studio-plugin/install.ps1').read_text(encoding='utf8')
        bridge=(CONTROL/'services/studio_location_instance_bridge.py').read_text(encoding='utf8')
        self.assertIn('id="li-anchor"',html)
        self.assertIn('location-instance-manager.js?v=347',html)
        self.assertIn('loadAnchors(data.anchorOptions)',js)
        self.assertIn("id('li-anchor').addEventListener('change', showChoiceStatus)",js)
        for code in (lua,install,bridge):
            self.assertIn('location-instance-replace-v3',code)
        self.assertNotIn('location-instance-replace-v1',lua)


if __name__=='__main__':
    unittest.main()
