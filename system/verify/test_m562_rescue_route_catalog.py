"""M562 metadata roundtrip and safety contract checks (Studio visual tests separate)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from rescue_route_store import snapshot,sync

MAP='11111111-2222-3333-4444-555555555555'
A='Route_'+MAP
B='Route_22222222-2222-3333-4444-555555555555'

class RouteCatalog(unittest.TestCase):
    def test_roundtrip_delete_restore_and_old_records(self):
        old={'id':A,'points':[[0,0,0],[3,4,0]]}
        new={'id':B,'points':[[0,0,0],[0,0,6]],'name':'Лестница','catalog':'Крепость'}
        with tempfile.TemporaryDirectory() as tmp:
            body={'mapId':MAP,'placeId':0,'routes':[old,new]}
            sync(tmp,body)
            original=snapshot(tmp)
            self.assertEqual(original['maps']['0:'+MAP]['routes'][1],{**new,'lengthStuds':6})
            sync(tmp,{**body,'placeId':1})
            sync(tmp,{**body,'routes':[old]})
            self.assertEqual([r['id'] for r in snapshot(tmp)['maps']['0:'+MAP]['routes']],[A])
            self.assertEqual(len(snapshot(tmp)['maps']['1:'+MAP]['routes']),2)
            sync(tmp,body)
            self.assertEqual(snapshot(tmp)['maps']['0:'+MAP],original['maps']['0:'+MAP])

    def test_invalid_metadata_rejected_atomically(self):
        route={'id':A,'points':[[0,0,0],[0,1,0]],'name':'One','catalog':'Castle'}
        body={'mapId':MAP,'placeId':0,'routes':[route]}
        with tempfile.TemporaryDirectory() as tmp:
            sync(tmp,body)
            before=snapshot(tmp)
            for field in ('name','catalog'):
                for bad in ('','  ','x'*81,'a\nb',1,None):
                    with self.assertRaises(ValueError): sync(tmp,{**body,'routes':[{**route,field:bad}]})
                    self.assertEqual(snapshot(tmp),before)

    def test_delete_is_dock_selection_only(self):
        s=(ROOT/'system/studio-plugin/modules/StudioRescueRoutes.luau').read_text(encoding='utf-8')
        self.assertNotIn('GetService("Selection")',s)
        self.assertNotIn('Selection:Get()',s)
        delete=s.split('local deleteButton=line(',1)[1].split('local cancelDeleteButton=',1)[0]
        self.assertIn('local route=selectedRoute',delete)
        self.assertIn('assert(not draft and isRoute(route,f)',delete)
        self.assertIn('if pendingDelete~=route then',delete)
        self.assertIn('local backup=route:Clone()',delete)
        self.assertEqual(delete.count('route:Destroy()'),1)
        self.assertNotIn('f:Destroy()',delete)
        self.assertIn('route.Parent==f',s)
        self.assertIn('enabled(deleteButton,hasSelection)',s)
        self.assertIn('selectedRoute=nil; pendingDelete=nil; draft=',s)

    def test_cancel_and_restore_are_separate(self):
        s=(ROOT/'system/studio-plugin/modules/StudioRescueRoutes.luau').read_text(encoding='utf-8')
        cancel=s.split('line("Cancel draft",',1)[1].split('line("Sync Database",',1)[0]
        for forbidden in (':Destroy()', 'syncDatabase()', 'SetWaypoint', 'root(true)'):
            self.assertNotIn(forbidden,cancel)
        undo=s.split('local undoDeleteButton=',1)[1].split('local editor=',1)[0]
        self.assertIn('deleted.root==f',undo)
        self.assertIn('not f:FindFirstChild(route.Name)',undo)
        self.assertIn('route.Parent=f',undo)
        self.assertIn('syncDatabase()',undo)
        self.assertIn('RouteCatalog',s)
        self.assertIn('RouteDisplayName',s)
        self.assertIn('Color3.fromRGB(255,205,72)',s)
        self.assertIn('Resume drawing',s)

if __name__=='__main__': unittest.main()
