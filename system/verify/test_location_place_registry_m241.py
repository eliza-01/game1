"""M241 · user-visible Repair/Sync journal, native Studio Undo and grouped repair."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import threading
import time
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.place_registry.journal import PlaceOperationJournal
from services.place_registry.revisions import PlaceRevisionStore
from services.place_registry.coordinator import LocationPlaceRegistry
from services.place_registry.catalog import build_catalog
from services import studio_place_registry_bridge as bridge
from api.read_world import route as read_route
from api.write_world import route as write_route
from test_location_place_registry_m240 import FakeAssets, row


class LocationPlaceRegistryM241(TestCase):
    def _revision(self, revisions):
        return revisions.add({'schemaVersion':1, 'placeId':47, 'placements':[row()]}, 'digest')['revisionId']

    def test_actions_are_durable_append_only_and_lifo_undo(self):
        with TemporaryDirectory() as tmp:
            revisions=PlaceRevisionStore(tmp)
            before=self._revision(revisions)
            journal=PlaceOperationJournal(revisions.path)
            self.assertEqual(len(list((Path(tmp)/'.control-center/backups').glob('location_place_m241_*.sqlite'))),1)
            one=journal.record(revision_id=before,place_id=47,operation_id='a'*32,
                               action='repair',selected=[{'key':'p1','slug':'stone_fence_01','name':'fence'}],
                               result={'changed':1,'undo':True})
            two=journal.record(revision_id=before,place_id=47,operation_id='b'*32,
                               action='sync',selected=[{'key':'p2','slug':'stone_fence_01','name':'fence2'}],
                               result={'changed':3,'undo':True})
            self.assertEqual([r['id'] for r in journal.page()][:2],[two,one])
            self.assertEqual([r['canUndo'] for r in journal.page()][:2],[True,False])
            with self.assertRaisesRegex(ValueError,'newer actions'):
                journal.undo_candidate(one)
            self.assertEqual(journal.undo_candidate(two)['operation_id'],'b'*32)
            journal.mark_undone(two,'b'*32)
            self.assertTrue(journal.page()[1]['canUndo'])
            self.assertEqual(journal.page()[0]['status'],'undone')
            self.assertEqual(PlaceOperationJournal(revisions.path).page()[0]['status'],'undone')
            self.assertEqual(journal.undo_candidate(one)['operation_id'],'a'*32)
            with self.assertRaises(ValueError):
                journal.mark_undone(two,'b'*32)
            with self.assertRaises(ValueError):
                journal.record(revision_id=before,place_id=47,operation_id='c'*32,
                               action='scan',selected=[],result={'changed':1,'undo':True})
            with self.assertRaises(ValueError):
                journal.record(revision_id=before,place_id=47,operation_id='c'*32,
                               action='sync',selected=[],result={'changed':-1,'undo':True})

    def test_legacy_m240_action_kept_visible_no_unsafe_undo(self):
        with TemporaryDirectory() as tmp:
            revisions=PlaceRevisionStore(tmp)
            before=self._revision(revisions)
            revisions.log_action(before,'repair',{'changed':2})
            journal=PlaceOperationJournal(revisions.path)
            past=journal.page()[0]
            self.assertEqual(past['status'],'legacy')
            self.assertFalse(past['canUndo'])
            self.assertEqual(past['affected'],2)

    def test_coordinator_records_mutation_undo_in_studio_and_requires_new_scan(self):
        with TemporaryDirectory() as tmp:
            assets=FakeAssets()
            calls=[]
            def studio(**kwargs):
                calls.append(kwargs)
                if kwargs['phase']=='scan':
                    return {'catalogDigest':kwargs['catalog']['digest'], 'scanToken':'a'*32,
                            'scan':{'schemaVersion':1,'placeId':47,'placements':[row()],'warnings':[]},
                            'inventory':[]}
                if kwargs['phase']=='undo':
                    self.assertEqual(kwargs['undo_operation_id'],'b'*32)
                    return {'result':{'changed':0,'undone':True}}
                return {'operationId':'b'*32,'result':{'changed':1,'undo':True}}
            revisions=PlaceRevisionStore(tmp)
            app=LocationPlaceRegistry(assets,revisions,studio)
            first=app.operate('scan')
            result=app.operate('repair',scan_token=first['scanToken'],keys=['p1'])
            self.assertTrue(result['journalId']>0)
            self.assertEqual(app.action_journal()[0]['selected'][0]['slug'],'stone_fence_01')
            with self.assertRaises(ValueError):
                app.operate('repair',scan_token=first['scanToken'],keys=['p1'])
            undo=app.operate('undo',action_id=result['journalId'])
            self.assertTrue(undo['undone'])
            self.assertEqual(app.action_journal()[0]['status'],'undone')
            self.assertEqual([c['phase'] for c in calls],['scan','repair','undo'])
            with self.assertRaises(ValueError):
                app.operate('undo',action_id=result['journalId'])

    def test_failed_studio_undo_does_not_forge_journal_confirmation(self):
        with TemporaryDirectory() as tmp:
            revisions=PlaceRevisionStore(tmp)
            before=self._revision(revisions)
            journal=PlaceOperationJournal(revisions.path)
            aid=journal.record(revision_id=before,place_id=47,operation_id='b'*32,
                               action='repair',selected=[],result={'changed':1,'undo':True})
            app=LocationPlaceRegistry(FakeAssets(),revisions,
                 lambda **kw:{'result':{'changed':0,'undone':False}})
            with self.assertRaisesRegex(ValueError,'did not confirm'):
                app.operate('undo',action_id=aid)
            self.assertEqual(app.action_journal()[0]['status'],'applied')

    def test_read_write_routes_are_scoped_and_preserve_old_operations(self):
        fake=mock.Mock()
        fake.action_journal.return_value=[]
        status,result=read_route(__import__('urllib.parse',fromlist=['urlparse']).urlparse(
            '/api/location-place-registry/actions?limit=15'),{'place_registry':fake},lambda:{})
        self.assertEqual(status,200)
        fake.action_journal.assert_called_once_with(15)
        fake.operate.return_value={'undone':True}
        status,result=write_route('/api/location-place-registry',lambda:{
            'phase':'undo','actionId':12},{'place_registry':fake})
        self.assertEqual(status,200)
        fake.operate.assert_called_once_with('undo',scan_token='',keys=None,action_id=12)

    def test_studio_bridge_undo_carries_only_specific_operation_identity(self):
        catalog=build_catalog(FakeAssets())
        with self.assertRaises(ValueError):
            bridge.run_place_registry_bridge(catalog=catalog,phase='undo',undo_operation_id='unsafe')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        output={}
        def server():
            output['response']=bridge.run_place_registry_bridge(
                catalog=catalog,phase='undo',undo_operation_id='b'*32,timeout_seconds=6)
        with mock.patch.object(bridge,'PORT',port):
            thread=threading.Thread(target=server,daemon=True);thread.start()
            cmd=None
            for _ in range(300):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{port}/command',
                            headers={'X-Game1-Token':bridge.TOKEN}),timeout=1) as response:
                        cmd=json.load(response)
                    break
                except (URLError,OSError):time.sleep(.01)
            self.assertIsNotNone(cmd)
            self.assertEqual(cmd['undoOperationId'],'b'*32)
            self.assertEqual(cmd['keys'],[])
            report={'project':bridge.PROJECT,'command':'location-place-registry',
                    'schemaVersion':1,'operationId':cmd['operationId'],
                    'catalogDigest':catalog['digest'],'phase':'undo',
                    'result':{'changed':0,'undone':True}}
            with urlopen(Request(f'http://127.0.0.1:{port}/place-registry-result',
                    method='POST',data=json.dumps(report).encode(),headers={
                        'X-Game1-Token':bridge.TOKEN}),timeout=2) as response:
                self.assertTrue(json.load(response)['ok'])
            thread.join(5)
        self.assertTrue(output['response']['result']['undone'])

    def test_interface_and_studio_native_undo_contract(self):
        ui=(ROOT/'system/control-center/static/place-registry.js').read_text('utf8')
        html=(ROOT/'system/control-center/static/index.html').read_text('utf8')
        commands=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryCommands.luau').read_text('utf8')
        repair=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryRepair.luau').read_text('utf8')
        sync=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistrySync.luau').read_text('utf8')
        self.assertIn('data-pr-action="repair-group"',ui)
        self.assertIn('await scan({automatic:true})',ui)
        self.assertIn('restoreViewport(position)',ui)
        self.assertIn('pr-action-log',ui)
        self.assertIn('pr-backup',html)
        self.assertLess(html.index('id="pr-backup"'),html.index('id="pr-groups"'))
        self.assertIn('GetCanUndo()',commands)
        self.assertIn('config.ChangeHistoryService:Undo()',commands)
        self.assertIn('ctx.recordingName',repair)
        self.assertIn('ctx.recordingName',sync)
        self.assertIn('session=nil',commands)
