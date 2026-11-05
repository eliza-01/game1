"""M238: Studio Select is read-only, COL has no atlas, authoring defaults are single-sided."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from collections import defaultdict
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import TestCase, mock
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import studio_deco_bridge as bridge
from services.mesh_authoring_policy import mesh_defaults, normalize_mesh_options
from real_estate.store import mesh_options as estate_options
from api.write_world import route
from services.location_asset_sync_history import LocationAssetSyncHistory


class StudioSelectM238(TestCase):
    @staticmethod
    def read(relative):
        return (ROOT / relative).read_text('utf8')

    def test_defaults_off_and_explicit_true_preserved_both_domains(self):
        for domain in ('estate', 'location'):
            with self.subTest(domain=domain):
                self.assertFalse(mesh_defaults('visual', domain=domain)['doubleSided'])
                self.assertFalse(normalize_mesh_options('visual', {}, domain=domain)['doubleSided'])
                self.assertTrue(normalize_mesh_options('visual', {'doubleSided':True}, domain=domain)['doubleSided'])
        self.assertFalse(estate_options(['house'], {})['house']['doubleSided'])
        self.assertTrue(estate_options(['house'], {'house':{'doubleSided':True}})['house']['doubleSided'])
        shared = self.read('src/shared/world/MeshPhysicsCore.luau')
        self.assertIn('then raw.doubleSided else false', shared)
        self.assertIn('mesh.DoubleSided = false', shared)

    def test_collision_geometry_has_no_texture_in_scan_and_apply(self):
        scan = self.read('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        apply = self.read('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        loader = self.read('system/studio-plugin/modules/DecoAssetLoader.luau')
        self.assertIn('textureApplicable = not MeshPhysics.IsCollider(part.Name)', scan)
        self.assertIn('textureCurrent=not textureApplicable', scan)
        self.assertIn('needsTexture=not textureCurrent', scan)
        self.assertIn('if Physics.IsCollider(part.Name)', apply)
        self.assertIn('descendant.TextureID = ""', loader)
        self.assertIn('if surface then surface:Destroy() end', loader)
        self.assertNotIn('selection:Set(selected)', scan)

    def test_select_is_explicit_read_only_and_does_not_acknowledge_atlas(self):
        class Atlas:
            def __init__(self): self.marked = []
            def binding(self, *_): return {'variant_id':1, 'revision':2}
            def mark_synced(self, *args): self.marked.append(args)
        class Assets:
            def __init__(self): self.atlases = Atlas()
            def get(self, slug):
                return {'slug':slug,'status':'PUBLISHED','bindingRevision':2,
                        'model_asset_id':'12345','texture_asset_id':'999'}
        assets = Assets()
        answer = {'selectedName':'legacy_tree','selectedPath':'Workspace.Old.legacy_tree','selectedCount':1}
        bridge_fn = mock.Mock(return_value=answer)
        history = mock.Mock()
        deps = defaultdict(lambda:None, {'location_assets':assets,
            'location_asset_sync_history':history,'sync_location_assets_to_studio':bridge_fn})
        payload = {'slug':'old_tree','phase':'select','scanToken':'1'*32,'partKeys':['p2']}
        status, response = route('/api/location-assets/studio-sync',lambda:payload,deps)
        self.assertEqual((status, response['studio']), (200, answer))
        bridge_fn.assert_called_once_with(slug='old_tree',binding_revision=2,
            model_asset_id='12345',atlas_asset_id='999',phase='select',
            scan_token='1'*32, part_keys=['p2'])
        history.append.assert_not_called()
        self.assertEqual(assets.atlases.marked, [])

    def test_attach_is_audited_but_does_not_mark_texture_synced(self):
        class Atlas:
            def __init__(self): self.marked=[]
            def binding(self,*_): return {'variant_id':1,'revision':2}
            def mark_synced(self,*args): self.marked.append(args)
        class Assets:
            def __init__(self): self.atlases=Atlas()
            def get(self,slug):
                return {'slug':slug,'status':'PUBLISHED','bindingRevision':2,
                        'model_asset_id':'12345','texture_asset_id':'999'}
            def export(self): pass
        assets=Assets()
        event={'kind':'model_reference','oldId':'','newId':'12340','count':1}
        legacy={'models':1,'parts':0,'matchedModels':1,'modelReferences':1,
                'pendingGeometry':1,'geometryUpdated':0,'meshPartsUpdated':0,
                'registryItems':0,'replacedModels':0,'changes':[event],
                'instances':[{'instanceId':'legacy1','studioPath':'Workspace.Trees.old',
                    'changes':[event],'meshIdsBefore':[{'meshId':'445','count':1}],
                    'meshIdsAfter':[{'meshId':'445','count':1}]}],
                'fullySynced':False}
        history=mock.Mock()
        bridge_fn=mock.Mock(return_value=legacy)
        deps=defaultdict(lambda:None, {'location_assets':assets,
            'location_asset_sync_history':history,'sync_location_assets_to_studio':bridge_fn})
        payload={'slug':'old_tree','phase':'attach','scanToken':'1'*32,'partKey':'p2'}
        status,response=route('/api/location-assets/studio-sync',lambda:payload,deps)
        self.assertEqual(status,200,response)
        self.assertFalse(response['studio']['fullySynced'])
        history.append.assert_called_once_with(slug='old_tree',binding_revision=2,studio=legacy)
        self.assertEqual(assets.atlases.marked,[])
        bridge_fn.assert_called_once_with(slug='old_tree',binding_revision=2,
            model_asset_id='12345',atlas_asset_id='999',phase='attach',
            scan_token='1'*32,part_key='p2')

    def test_link_history_accepts_immutable_old_model_id_without_texture_publish(self):
        class Audit:
            def __init__(self): self.events=[]
            def ensure_schema(self): pass
            def append(self,event): self.events.append(event)
            def page(self,slug,*,limit,before=None):
                return {'events':self.events[:limit],'nextCursor':None}
        event={'kind':'model_reference','oldId':'','newId':'135618055671248','count':1}
        instance={'instanceId':'legacy-tree-01','studioPath':'Workspace.Plots.01.christmas_tree',
                  'changes':[event], 'meshIdsBefore':[{'meshId':'78750137914383','count':1}],
                  'meshIdsAfter':[{'meshId':'78750137914383','count':1}]}
        with TemporaryDirectory() as directory:
            db=Audit()
            history=LocationAssetSyncHistory(Path(directory), database=db)
            result=history.append(slug='christmas_tree',binding_revision=2,
                studio={'operationId':'a'*32,'models':1,'matchedModels':1,'parts':0,
                        'pendingGeometry':1,'changes':[event],'instances':[instance]})
            self.assertEqual(result['changes'],[event])
            self.assertEqual(result['instances'][0]['meshIdsBefore'][0]['meshId'], '78750137914383')
            self.assertEqual(db.events[0]['slug'],'christmas_tree')

    def test_link_preflight_uses_exact_immutable_history_and_no_rig_swap(self):
        history=self.read('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        manager=self.read('system/studio-plugin/modules/DecoManager.luau')
        sync=self.read('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        self.assertIn('Inventory.MatchesInventory(model,version)',history)
        self.assertIn('hasForeignOwnership(model, workspace)',history)
        self.assertIn('legacyCandidates[key]={root=legacyRoot',history)
        link=manager.split('function DecoManager:attachHistoricalMeshSync(',1)[1].split(
            'function DecoManager:refreshRegistry(',1)[0]
        self.assertIn('DecoPlacedAssetSync.VerifyLegacyModel(model,oldPublished)',link)
        self.assertIn('History.MatchesInventory(model,History.Describe(candidate.modelId,oldPublished))',link)
        self.assertIn('self.ChangeHistoryService:SetWaypoint',link)
        self.assertIn('for _, name in ipairs(fields) do pcall(function()model:SetAttribute(name,previous[name])end) end',link)
        self.assertNotIn('RigSwap.Commit(',link)
        self.assertIn('History.VerifyChildren(oldPublished, rigChildren(model))',sync)

    def test_select_phase_bridge_roundtrip_and_token_validation(self):
        args = dict(slug='old_tree',binding_revision=2,model_asset_id='12345',
                    atlas_asset_id='999',phase='select',scan_token='1'*32)
        for bad in ('','evil','p0','p99999'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                bridge.run_deco_refresh_bridge(**args,part_keys=[bad])
        with socket.socket() as available:
            available.bind(('127.0.0.1', 0))
            port = available.getsockname()[1]
        reply = {}
        def worker():
            try: reply['data'] = bridge.run_deco_refresh_bridge(**args,part_keys=['p2'],timeout_seconds=5)
            except Exception as exc: reply['error'] = str(exc)
        with mock.patch.object(bridge,'PORT',port):
            thread = threading.Thread(target=worker,daemon=True)
            thread.start()
            command = None
            for _ in range(150):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{port}/command',
                           headers={'X-Game1-Token':bridge.TOKEN}), timeout=1) as response:
                        command=json.load(response)
                    break
                except (URLError, OSError): time.sleep(.01)
            self.assertIsNotNone(command)
            self.assertEqual((command['schemaVersion'],command['phase'],command['partKeys']),(9,'select',['p2']))
            self.assertNotIn('selectedKeys',command)
            incoming = {'project':bridge.PROJECT,'command':'deco-refresh','schemaVersion':9,
                'operationId':command['operationId'],'targetSlug':'old_tree','bindingRevision':2,
                'phase':'select','selectedName':'legacy_tree','selectedPath':'Workspace.Old.legacy_tree','selectedCount':1}
            with urlopen(Request(f'http://127.0.0.1:{port}/deco-refresh-result',
                   data=json.dumps(incoming).encode(),method='POST',headers={
                   'X-Game1-Token':bridge.TOKEN,'Content-Type':'application/json'}),timeout=2) as response:
                self.assertTrue(json.load(response)['ok'])
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertNotIn('error',reply)
        self.assertEqual(reply['data']['selectedPath'],'Workspace.Old.legacy_tree')

    def test_plugin_selection_scoped_to_one_scan_without_consuming_token(self):
        manager = self.read('system/studio-plugin/modules/DecoManager.luau')
        commands = self.read('system/studio-plugin/modules/StudioDecoSyncCommands.luau')
        select = manager.split('function DecoManager:selectMeshSyncPart(',1)[1].split(
            'function DecoManager:attachHistoricalMeshSync(',1)[0]
        self.assertIn('preview.token ~= scanToken',select)
        self.assertIn('self.Selection:Set(selected)',select)
        self.assertNotIn('self.meshSyncPreview=nil',select)
        self.assertNotIn('RigSwap.',select)
        self.assertIn('command.phase=="select"', commands)
        self.assertIn('schemaVersion~=9', commands)

if __name__ == '__main__':
    import unittest
    unittest.main()
