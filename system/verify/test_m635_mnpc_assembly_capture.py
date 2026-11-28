"""Real Host persistence/HTTP; Studio engine remains a separate smoke gate."""
import copy
import json
import socket
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import test_m633_mnpc_lod_authoring as m633
from services import mnpc_lod_capture as owner, mnpc_capture_bridge as transport
from api.write_world import route as write_world
from api.read_world import route as read_world
from studio_bridge import TOKEN

F = [0,0,0,1,0,0,0,1,0,0,0,1]


def clip(kind):
    return dict(clip_id='idle', asset_id='543', sha256='c'*64,binding_id='binding-idle',
                slot='idle',status='PUBLISHED',looped=True,weaponSet='1hs' if kind=='npc' else '',
                compatibleWith=['1hs'] if kind=='npc' else [],sourceNpc='same' if kind=='npc' else '')


def mesh(hand):
    return dict(path=f'{hand}/mesh',owner=hand,meshId='400',textureId='901',colorMap='',
                normalMap='',roughnessMap='',metalnessMap='',frame=F[:],size=[1,2,3],meshSize=[1,2,3],
                color=[1,1,1],material='Plastic',transparency=0)


def response(command):
    return dict(animationId='543',clipId='idle',weaponSet='1hs' if command['kind']=='npc' else '',
                pose=dict(mode='authored_keyframe',duration=2,time=.7,animatedBones=1),
                meshes=[mesh('body')]+[mesh(hand) for hand in command['equipment']],
                bones=[dict(path='body/mesh/spine',owner='body',name='spine',rest=F[:],posed=F[:],localTransform=F[:])])


class Capture(unittest.TestCase):
    setUp = m633.MnpcAuthoring.setUp
    new_owner = m633.MnpcAuthoring.new_owner
    payload = m633.MnpcAuthoring.payload
    stage = m633.MnpcAuthoring.stage

    def request(self, kind='monster', **extra):
        r = self.owner.describe(kind,'same')
        return dict(expectedRevision=r['revision'],fullFingerprint=r['fullFingerprint'],phase=.35) | extra

    def animations(self, kind):
        rows = [clip(kind)]
        return SimpleNamespace(rows=rows,list_for_monster=lambda slug:copy.deepcopy(rows))

    def test_capture_shared_for_both_types_and_reopened_from_disk(self):
        for kind in ('monster','npc'):
            with self.subTest(kind=kind):
                anim=self.animations(kind)
                def bridge(command):
                    self.assertEqual(command['kind'],kind)
                    self.assertEqual(command['equipment'],{'right':{'slug':'sword','modelId':'303'}} if kind=='npc' else {})
                    self.assertEqual(command['phase'],.35)
                    return response(command)
                result=owner.capture(self.owner,kind,'same',self.request(kind),anim,bridge=bridge)
                self.assertEqual(result['status'],'CAPTURED')
                self.assertEqual(result['meshCount'],2 if kind=='npc' else 1)
                self.assertEqual(result,owner.summary(self.new_owner(),kind,'same',anim))
                self.assertEqual(self.owner.describe(kind,'same')['revision'],0)
                self.assertEqual(self.owner.history(kind,'same'),[])
        self.inspect.assert_not_called()

    def test_failed_capture_keeps_previous_snapshot_and_lod(self):
        anim=self.animations('monster'); self.stage()
        good=owner.capture(self.owner,'monster','same',self.request(),anim,bridge=response)
        path=owner._file(self.owner,'monster','same'); before=path.read_bytes()
        for modify in (lambda r:r['meshes'][0].update(textureId='909'),
                       lambda r:r['pose'].update(time=3),lambda r:r['bones'][0]['posed'].__setitem__(3,2),
                       lambda r:r.update(animationId='999'),lambda r:r['meshes'].append(mesh('body'))):
            def bad(command):
                r=response(command);modify(r);return r
            with self.assertRaises(ValueError):
                owner.capture(self.owner,'monster','same',self.request(),anim,bridge=bad)
            self.assertEqual(path.read_bytes(),before)
        self.assertEqual(owner.summary(self.owner,'monster','same',anim),good)
        self.assertEqual(self.owner.describe('monster','same')['revision'],1)
        self.assertEqual(len(self.owner.history('monster','same')),1)

    def test_stale_capture_and_inflight_idle_equipment_change(self):
        anim=self.animations('npc')
        owner.capture(self.owner,'npc','same',self.request('npc'),anim,bridge=response)
        path=owner._file(self.owner,'npc','same'); before=path.read_bytes()
        def changed(command):
            anim.rows[0]['asset_id']='999';return response(command)
        with self.assertRaisesRegex(ValueError,'changed during'):
            owner.capture(self.owner,'npc','same',self.request('npc'),anim,bridge=changed)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(owner.summary(self.owner,'npc','same',anim)['status'],'STALE')
        anim.rows[0]['asset_id']='543'
        def removed(command):
            self.loadouts['same']['right']='';return response(command)
        with self.assertRaisesRegex(ValueError,'changed during'):
            owner.capture(self.owner,'npc','same',self.request('npc'),anim,bridge=removed)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(owner.summary(self.owner,'npc','same',anim)['status'],'STALE')

    def test_missing_equipment_and_invalid_input_rejected(self):
        anim=self.animations('npc')
        for payload in (self.request('npc',phase=True),self.request('npc',phase=0),
                        self.request('npc',expectedRevision=1),self.request('npc',fullFingerprint='old')):
            with self.assertRaises(ValueError):
                owner.capture(self.owner,'npc','same',payload,anim,bridge=lambda _:self.fail('invalid input reached Studio'))
        with self.assertRaisesRegex(ValueError,'omitted'):
            owner.capture(self.owner,'npc','same',self.request('npc'),anim,
                          bridge=lambda c:{**response(c),'meshes':[mesh('body')]})
        anim.rows[0]['status']='CHANGED'
        with self.assertRaisesRegex(ValueError,'base idle'):
            owner.capture(self.owner,'npc','same',self.request('npc'),anim,bridge=response)

    def test_read_write_routes_and_corrupted_capture(self):
        anim=self.animations('monster'); deps={'mnpc_lod':self.owner,'monster_animations':anim}
        path='/api/lod-manager/mnpc/monster/same/capture'
        self.assertEqual(read_world(urlsplit(path),deps,{})[1],{'status':'NOT_CAPTURED'})
        with patch.object(owner,'capture_from_studio',side_effect=response):
            status,result=write_world(path,self.request,deps)
        self.assertEqual(status,200);self.assertEqual(result['status'],'CAPTURED')
        self.assertEqual(read_world(urlsplit(path),deps,{})[1],result)
        stored=owner._file(self.owner,'monster','same'); data=json.loads(stored.read_text());data['capture']['meshes'][0]['meshId']='999'
        stored.write_text(json.dumps(data))
        self.assertEqual(read_world(urlsplit(path),deps,{})[1],{'status':'INVALID'})

    def test_real_local_bridge_rejects_wrong_operation_and_token(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        params=dict(kind='monster',slug='same',fullFingerprint='full',idleFingerprint='idle',expectedRevision=0,equipment={},idles=[])
        returned=[];errors=[]
        def serve():
            try:returned.append(transport.capture_from_studio(params,timeout_seconds=5,port=port))
            except Exception as exc:errors.append(exc)
        t=threading.Thread(target=serve);t.start()
        base=f'http://127.0.0.1:{port}'
        def get(token):
            with urlopen(Request(base+'/command',headers={'X-Game1-Token':token}),timeout=1) as r:return json.load(r)
        def post(body):
            with urlopen(Request(base+'/mnpc-capture-result',data=json.dumps(body).encode(),headers={'X-Game1-Token':TOKEN}),timeout=1) as r:return json.load(r)
        try:
            for _ in range(20):
                try:
                    get('bad');self.fail('unauthorized')
                except HTTPError as e:self.assertEqual(e.code,403);e.close();break
                except URLError:time.sleep(.05)
            command=get(TOKEN)
            with self.assertRaises(HTTPError) as claim:get(TOKEN)
            self.assertEqual(claim.exception.code,409);claim.exception.close()
            with self.assertRaises(HTTPError) as stale:post({**command,'operationId':'wrong','capture':{}})
            self.assertEqual(stale.exception.code,400);stale.exception.close()
            self.assertTrue(post({**command,'capture':response(command)})['ok'])
        finally:t.join(6)
        self.assertEqual(errors,[]);self.assertEqual(returned,[response(command)])

    def test_plugin_boundary(self):
        root=m633.ROOT
        plugin=root/'system/studio-plugin'
        manifest=json.loads((plugin/'plugin.project.json').read_text())['tree']['modules']
        for name in ('StudioMnpcCaptureCommand','StudioMnpcAssemblyCapture','StudioMnpcIdlePose'):
            self.assertTrue((plugin/manifest[name]['$path']).is_file())
        s=(plugin/'modules/StudioMnpcAssemblyCapture.luau').read_text()
        for token in ('template:Clone()', 'NpcAnimationRigBinding', 'MonsterRigBuilder', 'EquipVisual', 'Preview.RefreshAccessories', 'assembly:Destroy()', 'sequence:Destroy()', 'RootFrame', 'TransformedWorldCFrame'):
            self.assertIn(token,s)
        for token in ('.Parent = Workspace', '.Parent = game', 'Instance.new("Animator")','SetNetworkOwner',':Publish('):
            self.assertNotIn(token,s)
        pose=(plugin/'modules/StudioMnpcIdlePose.luau').read_text()
        self.assertIn('if sample.time == selected then',pose)
        self.assertNotIn(':Lerp(',pose)
        self.assertIn('no complete nonzero authored keyframe',pose)

if __name__=='__main__':unittest.main()
