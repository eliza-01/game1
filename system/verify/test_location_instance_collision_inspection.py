"""M352 collision approval is snapshot-bound, explicit and scoped to Instance Manager.

Studio's actual 3-D overlay and ChangeHistoryService require an Edit-mode smoke test.
"""
from pathlib import Path
import json
import re
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system/control-center'
sys.path.insert(0, str(CONTROL))
from services.location_instance_manager import LocationInstanceManager
from services.place_registry.catalog import build_catalog
from services.studio_location_instance_bridge import run_location_instance_bridge
from studio_bridge import StudioBridgeError
from test_location_instance_manager_m344 import FakeAssets


def source(relative):
    return (ROOT / relative).read_text(encoding='utf8')


class CollisionInspectionContract(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.manager = LocationInstanceManager(FakeAssets(), lambda **kw:
            self.commands.append(kw) or {'count': 1})
        self.base = dict(sourceSlug='stone_fence_01', targetSlug='stone_fence_02',
                         scope='selected', anchorId='model', scanToken='1'*8+'-'+'2'*4+'-'+'3'*4+'-'+'4'*4+'-'+'5'*12)

    def test_requires_explicit_inspection_phase_and_boolean_approval(self):
        for phase in ('inspect', 'clear', 'replace'):
            self.manager.operate({**self.base, 'phase': phase})
        self.assertEqual([call['phase'] for call in self.commands], ['inspect', 'clear', 'replace'])
        self.assertTrue(all(call['approve_shear'] is False for call in self.commands))
        with self.assertRaises(ValueError):
            self.manager.operate({**self.base, 'phase': 'inspect', 'approveShear': True})
        with self.assertRaises(ValueError):
            self.manager.operate({**self.base, 'phase': 'replace', 'approveShear': 'true'})
        with self.assertRaises(ValueError):
            self.manager.operate({**self.base, 'phase': 'replace', 'inspectionToken': 'bogus'})
        with self.assertRaises(ValueError):
            self.manager.operate({**self.base, 'phase': 'clear', 'scanToken': ''})
        self.manager.operate({**self.base, 'phase': 'replace',
                             'inspectionToken': self.base['scanToken'], 'approveShear': True})
        self.assertTrue(self.commands[-1]['approve_shear'])
        self.assertEqual(self.commands[-1]['inspection_token'], self.base['scanToken'])

    def test_collision_math_preserves_strict_default_everywhere_else(self):
        part = source('system/studio-plugin/modules/StudioLocationCollisionParts.luau')
        transform = source('system/studio-plugin/modules/StudioLocationCollisionTransform.luau')
        replace = source('system/studio-plugin/modules/StudioLocationInstanceReplace.luau')
        overlay = source('system/studio-plugin/modules/StudioLocationInstanceCollisionPreview.luau')
        self.assertIn('Transform.Part(anchor, recipe)', part)
        self.assertIn('Transform.Part(anchor, recipe, true)', part)
        self.assertIn('if excessive and allowExcessive ~= true', transform)
        self.assertIn('if #transaction.warnings > 0 then transaction.sha else nil', part)
        self.assertIn('root:GetAttribute(APPROVED) == sha', part)
        self.assertIn('transaction.oldApproval', part)
        self.assertIn('current.inspectedToken', replace)
        self.assertIn('current.inspectedFingerprint', replace)
        self.assertIn('collisionFingerprint(stage)', replace)
        self.assertIn('CollisionPreview.IsVisible(config.Workspace,overlay)', replace)
        self.assertIn('GetPropertyChangedSignal("CurrentCamera")', overlay)
        self.assertIn('connection:Disconnect()', overlay)
        self.assertIn('if not ghost or not camera or not ghost.Parent then return false end', overlay)
        self.assertIn('Studio camera unavailable for collision preview', overlay)
        self.assertIn('copy.CanCollide = false', overlay)
        self.assertIn('copy.CanQuery = false', overlay)
        self.assertIn('copy.CanTouch = false', overlay)
        self.assertIn('ghost.Parent = camera', overlay)
        self.assertIn('visual.CanCollide = false', overlay)
        self.assertIn('MAX_PARTS = 512', overlay)
        self.assertIn('session = nil', replace)
        self.assertIn('click Show collision preview again', replace)
        self.assertIn('current.inspectedToken = nil', replace)
        self.assertIn('Keep the session until staging and Undo have both succeeded', replace)
        self.assertIn('CollisionPreview.Clear(overlay)', replace)
        self.assertIn('ChangeHistoryService:TryBeginRecording', replace)

    def test_transport_accepts_valid_inspect_result_and_rejects_corruption(self):
        import services.studio_location_instance_bridge as bridge
        catalog = build_catalog(FakeAssets())
        guid = self.base['scanToken']
        for corrupt in (False, True):
            results = {}
            with socket.socket() as reserved:
                reserved.bind(('127.0.0.1', 0))
                port = reserved.getsockname()[1]
            def listen():
                try:
                    results['value'] = run_location_instance_bridge(
                        catalog=catalog, phase='inspect', source_slug='stone_fence_01',
                        target_slug='stone_fence_02', scope='selected',
                        scan_token=guid, anchor_id='geometry', timeout_seconds=4)
                except Exception as e:
                    results['error'] = e
            with patch.object(bridge,'PORT',port):
                worker=threading.Thread(target=listen,daemon=True);worker.start()
                command=None
                for _ in range(40):
                    try:
                        with urlopen(Request(f'http://127.0.0.1:{port}/command',
                                headers={'X-Game1-Token':bridge.TOKEN}),timeout=.2) as r:
                            command=json.load(r)
                        break
                    except Exception:
                        time.sleep(.025)
                self.assertIsNotNone(command)
                self.assertEqual(command['phase'],'inspect')
                payload={k:command[k] for k in ('project','command','schemaVersion','operationId',
                    'phase','sourceSlug','targetSlug','scope','anchorId')}
                payload['catalogDigest']=catalog['digest']
                payload['result']={'count':1,'inspectionToken': guid,'collisionParts':1,
                   'warnings':1,'warningDetails':[{'path':'Workspace.fence','partId':'wall',
                   'excessStuds':[1.5,0,0],'addedPercent':[18.0,0,0]}]}
                if corrupt:payload['result']['warningDetails'][0]['addedPercent']=[-2.0,0,0]
                req=Request(f'http://127.0.0.1:{port}/location-instance-result',method='POST',
                    headers={'X-Game1-Token':bridge.TOKEN,'Content-Type':'application/json'},
                    data=json.dumps(payload).encode('utf8'))
                with urlopen(req,timeout=2) as r:self.assertEqual(json.load(r),{'ok':True})
                worker.join(timeout=4)
            self.assertFalse(worker.is_alive())
            if corrupt:self.assertIsInstance(results.get('error'),StudioBridgeError)
            else:self.assertEqual(results.get('value'),payload['result'])

    def test_ui_wires_preview_confirmation_and_preview_clear(self):
        html=source('system/control-center/static/index.html')
        js=source('system/control-center/static/location-instance-manager.js')
        for field in ('li-inspect','li-clear-preview','li-collision-approval',
                      'li-approve-shear','li-collision-warnings'):
            self.assertIn(f'id="{field}"',html)
        self.assertIn("await send('inspect',state.preview.token)",js)
        self.assertIn("await send('replace',p.token,i.token,id('li-approve-shear').checked)",js)
        self.assertIn("send('clear',state.preview.token,state.inspected.token)",js)
        self.assertIn('state.inspected=null;',js)
        self.assertIn('3D-предпросмотр потерян',js)
        self.assertIn('const unchanged=catalogKey(state.assets)===catalogKey(nextAssets)',js)
        self.assertIn('if(!unchanged)reset()',js)
        self.assertIn('i.anchor!==id(\'li-anchor\').value',js)
        mapping=json.loads(source('system/studio-plugin/plugin.project.json'))
        self.assertIn('StudioLocationInstanceCollisionPreview',mapping['tree']['modules'])
        self.assertIn("'StudioLocationInstanceCollisionPreview'",
                      source('system/studio-plugin/install.ps1'))

if __name__=='__main__':unittest.main()
