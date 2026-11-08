"""M237: bounded per-part scan contract and partial-sync acknowledgement."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import socket
import sys
import threading
import time
from unittest import TestCase, mock
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import studio_deco_bridge as bridge
from api.write_world import route


class MeshpartM237(TestCase):
    @staticmethod
    def source(path):
        return (ROOT / path).read_text('utf-8')

    def test_collider_texture_is_not_an_atlas_binding(self):
        scan = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        loader = self.source('system/studio-plugin/modules/DecoAssetLoader.luau')
        self.assertIn('not MeshPhysics.IsCollider(part.Name)', scan)
        self.assertIn('textureCurrent=not textureApplicable', scan)
        self.assertIn('not Carrier.IsCarrier(part) and not Physics.IsCollider(part.Name)', sync)
        self.assertIn('descendant.TextureID = ""', loader)
        self.assertIn('StudioTextureAppearance.ApplyLocation(descendant, uri, alphaEnabled)', loader)

    def test_selective_rig_scope_and_one_use_preview(self):
        manager = self.source('system/studio-plugin/modules/DecoManager.luau')
        sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        commands = self.source('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        self.assertIn('self.meshSyncPreview=nil -- one-time token', manager)
        self.assertIn('scanned.partByKey[key]', manager)
        self.assertIn('wholeRig[entry.root]=true', manager)
        self.assertIn('if chosenRoots[root] then table.insert(placed,root)', sync)
        self.assertIn('if not geometry and not chosenParts[part] then continue end', sync)
        self.assertIn('RigSwap.Commit(item.swap)', sync)
        self.assertIn('command.selectedKeys', commands)
        self.assertIn('"parts","expectedMeshIds"', commands)

    def test_bridge_returns_independent_ids_and_nonselectable_external_rows(self):
        with socket.socket() as socket_:
            socket_.bind(('127.0.0.1', 0))
            port = socket_.getsockname()[1]
        report = {
            'project': bridge.PROJECT, 'command': 'deco-refresh',
            'schemaVersion': 9, 'targetSlug': 'oak_tree',
            'bindingRevision': 3, 'phase': 'scan',
            'scanToken': 'a'*32, 'mode': 'texture',
            'foundMeshParts': 2, 'managedMeshParts': 1,
            'unmanagedMeshParts': 1, 'managedModels': 1,
            'texturePending': 1, 'meshPending': 0, 'geometryPending': 0,
            'inventory': [{'modelAssetId':'12345','meshes':[{'meshId':'444', 'count':1}]}],
            'expectedMeshIds': ['444'],
            'parts': [
                {'key':'p1','name':'visual','path':'Workspace.Trees.oak.col_mesh',
                 'modelPath':'Workspace.Trees.oak','modelName':'oak','isCollider':False,'instanceId':'tree1','meshId':'444','textureId':'333','colorMapId':'',
                 'hasSurface':False,'textureApplicable':True,'attachable':False,'historicalModelId':'','managed':True,'meshCurrent':True,
                 'textureCurrent':False,'needsMesh':False,'needsTexture':True},
                {'key':'p2','name':'old_visual','path':'Workspace.Other.col_mesh',
                 'modelPath':'Workspace.Other','modelName':'Other','isCollider':False,'instanceId':'','meshId':'222','textureId':'333','colorMapId':'',
                 'hasSurface':False,'textureApplicable':True,'attachable':False,'historicalModelId':'','managed':False,'meshCurrent':False,
                 'textureCurrent':False,'needsMesh':False,'needsTexture':True},
            ],
        }
        outcome = {}
        def worker():
            try:
                outcome['result'] = bridge.run_deco_refresh_bridge(
                    timeout_seconds=4, slug='oak_tree', binding_revision=3,
                    model_asset_id='12345', atlas_asset_id='999',
                    phase='scan',model_history=['12345'])
            except Exception as exc:
                outcome['error'] = exc
        with mock.patch.object(bridge,'PORT',port):
            thread = threading.Thread(target=worker,daemon=True)
            thread.start()
            command = None
            for _ in range(150):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{port}/command',
                                         headers={'X-Game1-Token':bridge.TOKEN}),timeout=1) as response:
                        command=json.load(response)
                    break
                except (URLError, OSError):
                    time.sleep(.01)
            self.assertIsNotNone(command)
            self.assertEqual(command['modelAssetId'],'12345')
            incoming = dict(report, operationId=command['operationId'])
            with urlopen(Request(f'http://127.0.0.1:{port}/deco-refresh-result',
                                 data=json.dumps(incoming).encode(),method='POST',headers={
                                 'X-Game1-Token':bridge.TOKEN,
                                 'Content-Type':'application/json'}),timeout=2) as reply:
                self.assertTrue(json.load(reply)['ok'])
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertNotIn('error',outcome)
        self.assertEqual(outcome['result']['parts'][0]['textureId'],'333')
        self.assertFalse(outcome['result']['parts'][0]['textureCurrent'])
        self.assertFalse(outcome['result']['parts'][1]['managed'])
        self.assertEqual(outcome['result']['expectedMeshIds'],['444'])

    def test_backend_does_not_mark_atlas_synced_on_partial_selection(self):
        class Atlas:
            def __init__(self): self.marked=[]
            def binding(self,*_): return {'variant_id':1,'revision':2}
            def mark_synced(self,*args): self.marked.append(args)
        class Assets:
            def __init__(self): self.atlases=Atlas()
            def get(self, slug):
                return {'slug':slug,'status':'PUBLISHED','bindingRevision':2,
                        'model_asset_id':'12345','texture_asset_id':'999'}
            def export(self): return None
        assets=Assets()
        result={'operationId':'a'*32,'targetSlug':'oak_tree','models':0,'parts':1,
                'matchedModels':1,'modelReferences':0,'pendingGeometry':0,
                'geometryUpdated':0,'meshPartsUpdated':0,'replacedModels':0,
                'registryItems':1,'changes':[],'instances':[],'fullySynced':False}
        write=mock.Mock(return_value=result)
        history=mock.Mock()
        deps=defaultdict(lambda:None, {'location_assets':assets,
              'location_asset_sync_history':history,
              'sync_location_assets_to_studio':write})
        payload={'slug':'oak_tree','phase':'replace','scanToken':'1'*32,
                 'selectedKeys':['p1']}
        status,reply=route('/api/location-assets/studio-sync',lambda:payload,deps)
        self.assertEqual(status,200,reply)
        self.assertEqual(assets.atlases.marked,[])
        write.assert_called_once_with(slug='oak_tree',binding_revision=2,
            model_asset_id='12345',atlas_asset_id='999',phase='replace',
            scan_token='1'*32,selected_keys=['p1'])
        write.return_value=dict(result,fullySynced=True)
        status,reply=route('/api/location-assets/studio-sync',lambda:payload,deps)
        self.assertEqual(status,200,reply)
        self.assertEqual(len(assets.atlases.marked),1)

    def test_selected_keys_are_bounded_and_distinct(self):
        args={'slug':'oak_tree','binding_revision':3,'model_asset_id':'12345',
              'atlas_asset_id':'999','phase':'replace','scan_token':'1'*32}
        for keys in (None, [], ['p1','p1'], ['p0'], ['evil'], ['p40960']):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                bridge.run_deco_refresh_bridge(**args, selected_keys=keys)

if __name__ == '__main__':
    import unittest
    unittest.main()
