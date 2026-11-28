"""M637 alignment: math, current-revision SQLite contract, Studio/Blender doubles."""
import copy
import json
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen
import unittest
from unittest.mock import patch

import test_m633_mnpc_lod_authoring as m633
from services import mnpc_lod_alignment as alignment
from services import mnpc_capture_bridge as transport
from studio_bridge import TOKEN
from api.write_world import route

# Unique asymmetric points, different spans, off-origin. No bbox-only match.
REF=[[1,2,3],[2.7,2,3],[1,5.3,3],[1,2,7.9],[1.2,2.9,4.4],[1.5,3.2,6.5]]
# root=2*rotation(local)+(4,-3,7), rotation maps (x,y,z)->(z,x,y).
ACTUAL=[[(y+3)/2,(z-7)/2,(x-4)/2] for x,y,z in REF]
SIZE=[1.65,2.45,.85]


def response():
    return dict(meshId='98765432101234',size=SIZE,meshSize=SIZE,vertices=ACTUAL,triangles=64)


class AlignmentMath(unittest.TestCase):
    def test_fit_full_transform_and_duplicate_import_vertices(self):
        result=alignment.fit(REF,ACTUAL+[ACTUAL[0]],SIZE)
        for actual,expected in zip(result['rootCFrame'],[4,-3,7,0,0,1,1,0,0,0,1,0]):
            self.assertAlmostEqual(actual,expected)
        self.assertAlmostEqual(result['scale'],2)
        for actual,expected in zip(result['size'],[3.3,4.9,1.7]):self.assertAlmostEqual(actual,expected)
        self.assertLess(result['maxVertexError'],1e-9)

    def test_reject_same_bounds_wrong_geometry_mirror_anisotropy_and_symmetry(self):
        wrong=copy.deepcopy(ACTUAL);wrong[-1][0]+=.1
        for bad in (wrong,[[-x,y,z] for x,y,z in ACTUAL],[[x*1.1,y,z] for x,y,z in ACTUAL],ACTUAL[:-1],ACTUAL+[[float('nan'),0,0]]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):alignment.fit(REF,bad,SIZE)
        cube=[[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)]
        with self.assertRaisesRegex(ValueError,'ambiguous'):alignment.fit(cube,cube,[2,2,2])


class AlignmentRegistry(unittest.TestCase):
    setUp=m633.MnpcAuthoring.setUp
    new_owner=m633.MnpcAuthoring.new_owner
    payload=m633.MnpcAuthoring.payload
    stage=m633.MnpcAuthoring.stage
    cloud=m633.MnpcAuthoring.cloud
    staged=m633.MnpcAuthoring.staged

    def published(self,kind):
        # Valid M636 provenance. The source/Blender/Open Cloud parts are doubles;
        # the registry, revision, history and invalidation paths are real.
        recipe={'mode':'captured_idle','rootSpace':'roblox_navigation_studs_y_up','targetTriangles':1000,
                'idleFingerprint':'idle'}
        self.owner.stage(kind,'same',self.payload(kind),recipe=recipe)
        with patch.object(self.owner,'_check_captured_idle'):
            return self.owner.publish(kind,'same',1,m633.CREDS)

    def align(self,kind,**kwargs):
        return alignment.verify(self.owner,kind,'same',{'expectedRevision':1},
            bridge=kwargs.get('bridge',lambda cmd:response()),reference=kwargs.get('reference',lambda owner,row:REF))

    def test_both_kinds_persist_no_cloud_upload_and_revision_invalidation(self):
        self.cloud()
        for kind in ('monster','npc'):
            self.published(kind)
            result=self.align(kind)
            self.assertEqual(result['alignmentStatus'],'GEOMETRY_VERIFIED')
            self.assertEqual(result['alignment']['meshId'],response()['meshId'])
            self.assertFalse(result['runtimeReady'])
            self.assertEqual(self.new_owner().describe(kind,'same')['alignment'],result['alignment'])
            self.align(kind)
            self.assertEqual([h['event'] for h in self.owner.history(kind,'same')].count('GEOMETRY_ALIGNED'),1)
        self.assertEqual(self.create_model_asset.call_count,2)
        self.weapons.rows['sword']['model_sha256']='c'*64
        self.assertEqual(self.owner.describe('npc','same')['status'],'FULL_CHANGED')
        self.assertIsNone(self.owner.describe('npc','same')['alignment'])
        self.assertEqual(self.owner.describe('monster','same')['alignmentStatus'],'GEOMETRY_VERIFIED')
        self.fbx.write_bytes(self.fbx.read_bytes()+b'new revision')
        self.assertEqual(self.stage()['revision'],2)
        self.assertIsNone(self.owner.describe('monster','same')['alignment'])

    def test_reject_manual_and_mismatch_preserve_state(self):
        self.cloud();self.stage();self.owner.publish('monster','same',1,m633.CREDS)
        with self.assertRaisesRegex(ValueError,'captured-idle'):self.align('monster')
        self.published('npc')
        for bad in ({**response(),'meshId':'bad'},{**response(),'triangles':65},{**response(),'vertices':ACTUAL[:-1]}):
            with self.assertRaises(ValueError):self.align('npc',bridge=lambda cmd:bad)
        self.assertIsNone(self.owner.describe('npc','same')['alignment'])
        def changed(cmd):
            self.npcs.rows['same']['model_asset_id']='404'
            return response()
        with self.assertRaisesRegex(ValueError,'changed during import'):self.align('npc',bridge=changed)
        self.assertNotIn('GEOMETRY_ALIGNED',[h['event'] for h in self.owner.history('npc','same')])

    def test_api_and_reference_axes(self):
        self.cloud();row=self.published('monster')
        raw=[[x,-z,y] for x,y,z in REF]
        report={**m633.REPORT,'vertices':len(raw),'boundsMin':[min(p[i] for p in raw) for i in range(3)],
                'boundsMax':[max(p[i] for p in raw) for i in range(3)],'points':raw}
        row["geometry"].update(copy.deepcopy(alignment.geometry.validate(report)))
        with patch.object(alignment,'inspect_report',return_value=report):
            self.assertEqual(sorted(alignment.reference_points(self.owner,row)),sorted(REF))
            report['boundsMax'][0]+=1
            with self.assertRaisesRegex(ValueError,'report changed'):alignment.reference_points(self.owner,row)
        with patch.object(alignment,'reference_points',return_value=REF),patch.object(alignment,'import_from_studio',return_value=response()):
            status,result=route('/api/lod-manager/mnpc/monster/same/align',lambda:{'expectedRevision':1},{'mnpc_lod':self.owner})
        self.assertEqual(status,200,result);self.assertEqual(result['alignmentStatus'],'GEOMETRY_VERIFIED')

    def test_detached_plugin_and_registration(self):
        plugin=m633.ROOT/'system/studio-plugin'
        source=(plugin/'modules/StudioMnpcImportAlignment.luau').read_text()
        for token in ('LoadAssetAsync','CreateEditableMeshAsync','GetFaceVertices','GetVertexBones','editable:Destroy()','loaded:Destroy()'):
            self.assertIn(token,source)
        self.assertNotIn('.Parent =',source)
        manifest=json.loads((plugin/'plugin.project.json').read_text())['tree']['modules']
        for name in ('StudioMnpcImportAlignment','StudioMnpcAlignmentCommand'):
            self.assertTrue((plugin/manifest[name]['$path']).is_file())
        self.assertIn('mnpc-align-v1',(plugin/'Game1Bridge.server.luau').read_text())


class Bridge(unittest.TestCase):
    def test_import_envelope_rejects_stale_revision(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        result=[];errors=[]
        payload=dict(kind='npc',slug='same',revision=1,modelAssetId='601')
        def serve():
            try:result.append(transport.request_studio(payload,command_name='mnpc-align-v1',result_path='/mnpc-align-result',identity_keys=tuple(payload),result_key='alignment',timeout_seconds=5,port=port))
            except Exception as exc:errors.append(exc)
        t=threading.Thread(target=serve);t.start();base=f'http://127.0.0.1:{port}'
        def req(path,body=None):
            with urlopen(Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'X-Game1-Token':TOKEN}),timeout=1) as r:return json.load(r)
        try:
            for _ in range(20):
                try:command=req('/command');break
                except URLError:time.sleep(.05)
            with self.assertRaises(HTTPError) as stale:req('/mnpc-align-result',{**command,'revision':2,'alignment':response()})
            self.assertEqual(stale.exception.code,400);stale.exception.close()
            self.assertTrue(req('/mnpc-align-result',{**command,'alignment':response()})['ok'])
        finally:t.join(6)
        self.assertEqual(errors,[]);self.assertEqual(result,[response()])
