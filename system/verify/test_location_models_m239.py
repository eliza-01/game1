"""M239: published Mesh provenance, safe Studio bulk Select, library presentation."""
from __future__ import annotations

import json
import socket
import sqlite3
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from api.write_world import route
from services import studio_deco_bridge as bridge

class M239(TestCase):
    def test_library_displays_only_published_visual_mesh_ids(self):
        with TemporaryDirectory() as directory:
            db=Path(directory)/'asset.db'
            with sqlite3.connect(db) as cx:
                cx.execute('CREATE TABLE location_assets(slug TEXT,category TEXT,name_en TEXT,model_asset_id TEXT)')
                cx.execute('CREATE TABLE location_asset_mesh_id_inventory(asset_slug TEXT,model_asset_id TEXT,meshes_json TEXT)')
                cx.executemany('INSERT INTO location_assets VALUES(?,?,?,?)',[
                    ('birch_01','tree','Birch','200'),('oak','tree','Oak','250')])
                cx.executemany('INSERT INTO location_asset_mesh_id_inventory VALUES(?,?,?)',[
                    ('birch_01','200',json.dumps([
                        {'meshId':'111','count':1,'visualNames':['birch_01']},
                        {'meshId':'222','count':1,'visualNames':[]},
                        {'meshId':'333','count':1,'visualNames':['branches']}])) ,
                    ('birch_01','100',json.dumps([{'meshId':'444','count':1,'visualNames':['old']}])) ,
                    ('oak','250',json.dumps([{'meshId':'555','count':1}]))])
            store=LocationAssetStore.__new__(LocationAssetStore)
            store.connect=lambda:sqlite3.connect(db)
            # sqlite Row needed for the normal shared Store.list projection.
            def connection():
                cx=sqlite3.connect(db);cx.row_factory=sqlite3.Row;return cx
            store.connect=connection
            store.atlases=mock.Mock(catalog=lambda:[])
            store._decorate=lambda row,*_:row
            records=store.list()
            self.assertEqual(records[0]['publishedVisualMeshes'],[
                {'meshId':'111','name':'birch_01'},{'meshId':'333','name':'branches'}])
            self.assertEqual(records[1]['publishedVisualMeshes'],[],
                'M238 cache without names cannot be guessed from old Model IDs')

    def test_bulk_studio_selection_read_only_route(self):
        class Assets:
            def __init__(self):self.atlases=mock.Mock(binding=lambda *_:{'revision':2})
            def get(self,slug):return {'slug':slug,'status':'PUBLISHED','bindingRevision':2,
                'model_asset_id':'12345','texture_asset_id':'999'}
        assets=Assets()
        transport=mock.Mock(return_value={'selectedCount':3,'selectedName':'','selectedPath':''})
        history=mock.Mock()
        deps=defaultdict(lambda:None,{'location_assets':assets,'sync_location_assets_to_studio':transport,
            'location_asset_sync_history':history})
        status,result=route('/api/location-assets/studio-sync',lambda:{
            'slug':'oak','phase':'select','scanToken':'a'*32,'partKeys':['p1','p3','p5']},deps)
        self.assertEqual(status,200,result)
        self.assertEqual(result['studio']['selectedCount'],3)
        transport.assert_called_once_with(slug='oak',binding_revision=2,model_asset_id='12345',
            atlas_asset_id='999',phase='select',scan_token='a'*32,part_keys=['p1','p3','p5'])
        history.append.assert_not_called()
        assets.atlases.mark_synced.assert_not_called()

    def test_bridge_rejects_duplicate_and_invalid_keys(self):
        kwargs={'slug':'oak','binding_revision':2,'model_asset_id':'12345',
            'atlas_asset_id':'999','phase':'select','scan_token':'a'*32}
        for keys in (None,[],['p1','p1'],['p0'],['p50000'],['x'],['p1',23]):
            with self.subTest(keys=keys),self.assertRaises(ValueError):
                bridge.run_deco_refresh_bridge(**kwargs,part_keys=keys)

    def test_transport_bulk_selection_one_http_roundtrip(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        outcome={}
        def worker():
            try:
                outcome['result']=bridge.run_deco_refresh_bridge(
                    timeout_seconds=4,slug='oak',binding_revision=2,model_asset_id='12345',
                    atlas_asset_id='999',phase='select',scan_token='a'*32,part_keys=['p1','p3','p5'])
            except Exception as exc:outcome['error']=exc
        with mock.patch.object(bridge,'PORT',port):
            thread=threading.Thread(target=worker,daemon=True);thread.start()
            command=None
            for _ in range(150):
                try:
                    with urlopen(Request(f'http://127.0.0.1:{port}/command',
                         headers={'X-Game1-Token':bridge.TOKEN}),timeout=1) as response:
                        command=json.load(response)
                    break
                except (URLError,OSError):time.sleep(.01)
            self.assertIsNotNone(command)
            self.assertEqual((command['schemaVersion'],command['phase'],command['partKeys']),
                             (9,'select',['p1','p3','p5']))
            payload={'project':bridge.PROJECT,'command':'deco-refresh','schemaVersion':9,
                'operationId':command['operationId'],'targetSlug':'oak','bindingRevision':2,
                'phase':'select','selectedCount':3,'selectedName':'','selectedPath':''}
            with urlopen(Request(f'http://127.0.0.1:{port}/deco-refresh-result',
                method='POST',data=json.dumps(payload).encode(),headers={
                    'X-Game1-Token':bridge.TOKEN,'Content-Type':'application/json'}),timeout=2) as response:
                self.assertTrue(json.load(response)['ok'])
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertNotIn('error',outcome)
        self.assertEqual(outcome['result']['selectedCount'],3)

    def test_api_contract_requires_model_grouping_metadata(self):
        text=(ROOT/'system/control-center/services/studio_deco_bridge.py').read_text('utf8')
        luau=(ROOT/'system/studio-plugin/modules/StudioPublishedMeshHistory.luau').read_text('utf8')
        manager=(ROOT/'system/studio-plugin/modules/DecoManager.luau').read_text('utf8')
        self.assertIn("'modelPath'",text)
        self.assertIn("'isCollider'",text)
        self.assertIn('modelPath=string.sub(container:GetFullName(),1,240)',luau)
        self.assertIn('self.Selection:Set(selected)',manager)
        self.assertNotIn('RigSwap.Commit(',manager.split('function DecoManager:selectMeshSyncPart(',1)[1].split('function DecoManager:attachHistoricalMeshSync',1)[0])

if __name__=='__main__':
    import unittest
    unittest.main()
