"""M633 contracts with actual SQLite/Atlas Registry; Blender and Cloud are doubles."""
from contextlib import contextmanager
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.mnpc_lod_resource import MnpcLodResource, DEFAULT_PROFILE
from services import mnpc_lod_geometry as geometry
from services.texture_atlas_registry import AtlasRegistry
from api.read_world import route as read_world
from api.write_world import route as write_world

REPORT = dict(schemaVersion=1, meshName='lod1', meshes=1, armatures=0,
              vertices=48, triangles=64, boundsMin=[-1,-1,0], boundsMax=[1,1,3])
CREDS = dict(apiKey='fake', creatorId='1', creatorType='User')


def actor(slug, model_id):
    return dict(slug=slug, name_en=slug, status='PUBLISHED', revision=3,
                model_asset_id=model_id, model_sha256='a'*64,
                textures=[dict(slot='body', asset_id='901', sha256='b'*64)])


class Actors:
    def __init__(self, *rows):
        self.rows = {row['slug']:row for row in rows}
    def get(self, slug):
        return copy.deepcopy(self.rows.get(slug))
    def list(self):
        return [self.get(slug) for slug in self.rows]


class MnpcAuthoring(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'.control-center').mkdir()
        self.monsters = Actors(actor('same', '101'))
        self.npcs = Actors(actor('same', '202'))
        self.weapons = Actors({**actor('sword','303'), 'weapon_type':'sword'})
        self.loadouts = {'same': {'right':'sword','left':''}}
        self.equipment = SimpleNamespace(snapshot=lambda:{'loadouts':copy.deepcopy(self.loadouts)})
        self.atlases = AtlasRegistry(self.root)
        self.owner = self.new_owner()
        self.fbx = self.root/'same_lod1.fbx'
        self.fbx.write_bytes(b'; FBX 7.4.0\nFBXHeaderExtension: {}\nstatic lod1')
        self.texture = self.root/'baked.png'
        Image.new('RGB',(16,16),'green').save(self.texture)
        self.inspect = patch('services.mnpc_lod_geometry.inspect', return_value=REPORT).start()
        self.addCleanup(patch.stopall)

    def new_owner(self):
        return MnpcLodResource(self.root,self.monsters,self.npcs,self.equipment,self.weapons,self.atlases)

    def payload(self, kind, **kwargs):
        row=self.owner.describe(kind,'same')
        return dict(sourcePath=str(self.fbx),texturePath=str(self.texture),expectedRevision=row['revision'],
                    fullFingerprint=row['fullFingerprint'],**kwargs)

    def stage(self,kind='monster'):
        return self.owner.stage(kind,'same',self.payload(kind))

    @contextmanager
    def staged(self, root, source, **kwargs):
        self.assertEqual(kwargs['texture_mode'],'geometry_only')
        kwargs['report_receiver'].update(locationRigManifest={'rigKind':'static','bones':[],
            'parts':[{'name':'lod1','role':'visual','vertices':48}]})
        yield source

    def cloud(self, model_wait=None):
        for module, name, value in (
            ('services.texture_atlas_registry','create_image_asset','operations/image'),
            ('services.texture_atlas_registry','wait_for_operation',SimpleNamespace(asset_id='501',operation_path='operations/image',moderation_state='Approved')),
            ('services.model_lod_common','create_model_asset','operations/model'),
        ):
            setattr(self, name if module.endswith('model_lod_common') else 'image_'+name,
                    patch(module+'.'+name,return_value=value).start())
        patch('services.model_lod_common.staged_model',self.staged).start()
        model_result=SimpleNamespace(asset_id='601',operation_path='operations/model',moderation_state='Approved')
        if model_wait is None:
            patch('services.model_lod_common.wait_for_operation',return_value=model_result).start()
        else:
            patch('services.model_lod_common.wait_for_operation',side_effect=model_wait).start()
        return model_result

    def test_catalog_kind_identity_and_additive_backup(self):
        items=self.owner.overview()['items']
        self.assertEqual([(r['kind'],r['slug']) for r in items],[('monster','same'),('npc','same')])
        self.assertNotEqual(items[0]['fullFingerprint'],items[1]['fullFingerprint'])
        self.assertFalse(self.owner.overview()['runtimeEnabled'])
        self.assertTrue(list((self.root/'.control-center/backups').glob('before_m633*')))
        self.new_owner()
        self.assertEqual(len(list((self.root/'.control-center/backups').glob('before_m633*'))),1)

    def test_shared_stage_idempotence_and_persistence(self):
        original=self.monsters.get('same')
        m=self.stage(); n=self.stage('npc')
        self.assertEqual((m['status'],n['status']),('STAGED','STAGED'))
        self.assertNotEqual(m['sourcePath'],n['sourcePath'])
        self.assertEqual(self.stage()['revision'],1)
        self.assertEqual(self.new_owner().describe('npc','same')['revision'],1)
        self.assertEqual(self.monsters.get('same'),original)
        self.assertEqual(len(self.owner.history('monster','same')),1)
        self.assertEqual(self.atlases.get_variant(m['atlasVariantId'])['source_sha256'],
                         self.atlases.get_variant(n['atlasVariantId'])['source_sha256'])
        self.assertFalse((self.root/'src').exists())

    def test_stale_full_and_equipment_without_gameplay_false_positive(self):
        m=self.stage(); n=self.stage('npc')
        self.monsters.rows['same'].update(revision=4,stats={'MaxHP':300})
        self.assertEqual(self.owner.describe('monster','same')['fullFingerprint'],m['fullFingerprint'])
        self.weapons.rows['sword']['model_sha256']='c'*64
        self.assertEqual(self.owner.describe('npc','same')['status'],'FULL_CHANGED')
        self.assertEqual(self.owner.describe('monster','same')['status'],'STAGED')
        self.loadouts['same']={'right':'','left':''}
        self.assertNotEqual(self.owner.describe('npc','same')['fullFingerprint'],n['fullFingerprint'])
        self.monsters.rows['same']['model_asset_id']='404'
        self.assertEqual(self.owner.describe('monster','same')['status'],'FULL_CHANGED')
        self.assertEqual(self.stage()['revision'],2)

    def test_stage_rejects_cas_and_malformed_geometry_or_image(self):
        payload=self.payload('monster');payload['fullFingerprint']='stale'
        with self.assertRaisesRegex(ValueError,'FULL changed'):
            self.owner.stage('monster','same',payload)
        self.inspect.side_effect=ValueError('armature present')
        with self.assertRaisesRegex(ValueError,'armature'):
            self.stage()
        self.inspect.side_effect=None
        self.texture.write_bytes(b'fake PNG')
        with self.assertRaises(ValueError):self.stage()
        self.assertEqual(self.owner.describe('monster','same')['revision'],0)
        self.assertEqual(self.owner.history('monster','same'),[])
        for bad in ({**REPORT,'meshes':2},{**REPORT,'armatures':1},{**REPORT,'triangles':0},
                    {**REPORT,'boundsMin':[0,0,float('nan')]}):
            with self.assertRaises(ValueError):geometry.validate(bad)
        self.assertEqual(geometry.validate(REPORT),REPORT)

    def test_publication_reuses_atlas_catalog_and_has_no_runtime_ready_flag(self):
        self.stage(); self.stage('npc'); self.cloud()
        m=self.owner.publish('monster','same',1,CREDS)
        n=self.owner.publish('npc','same',1,CREDS)
        self.assertEqual((m['status'],m['modelAssetId'],m['imageAssetId']),('PUBLISHED','601','501'))
        self.assertEqual(n['status'],'PUBLISHED')
        self.assertFalse(m['runtimeReady']); self.assertFalse(n['runtimeReady'])
        self.assertEqual(self.image_create_image_asset.call_count,1)
        self.assertEqual(self.create_model_asset.call_count,2)
        self.assertEqual(self.owner.publish('monster','same',1,{})['status'],'PUBLISHED')
        self.assertEqual(self.create_model_asset.call_count,2)
        self.assertEqual([h['event'] for h in self.owner.history('monster','same')],
                         ['MODEL_PUBLISHED','MODEL_OPERATION','MODEL_INTENT','ATLAS_READY','STAGED'])

    def test_partial_publication_resumes_without_duplicate_upload(self):
        self.stage(); result=self.cloud(model_wait=TimeoutError('not done yet'))
        with self.assertRaises(TimeoutError):self.owner.publish('monster','same',1,CREDS)
        pending=self.new_owner().describe('monster','same')
        self.assertEqual((pending['status'],pending['imageAssetId'],pending['modelOperation']),
                         ('MODEL_PENDING','501','operations/model'))
        with self.assertRaisesRegex(ValueError,'Resolve'):self.stage()
        with patch('services.mnpc_lod_resource.get_operation',return_value={'done':True}), \
             patch('services.mnpc_lod_resource.wait_for_operation',return_value=result):
            self.monsters.rows['same']['model_asset_id']='404'
            self.assertEqual(self.new_owner().publish('monster','same',1,CREDS)['status'],'FULL_CHANGED')
        self.assertEqual(self.create_model_asset.call_count,1)
        self.assertEqual(self.image_create_image_asset.call_count,1)
        self.assertEqual(self.owner.history('monster','same')[0]['modelAssetId'],'601')

    def test_source_or_atlas_change_fail_closed(self):
        staged=self.stage()
        (self.root/staged['sourcePath']).write_bytes(b'wrong bytes')
        self.assertEqual(self.owner.describe('monster','same')['status'],'SOURCE_CHANGED')
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):
            self.owner.publish('monster','same',1,CREDS)
        (self.root/staged['sourcePath']).write_bytes(self.fbx.read_bytes())
        with self.atlases.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET retired_at=1 WHERE id=?',(staged['atlasVariantId'],))
        self.assertEqual(self.owner.describe('monster','same')['status'],'ATLAS_CHANGED')

    def test_profiles_and_routes(self):
        deps={'mnpc_lod':self.owner}
        status,view=read_world(urlsplit('/api/lod-manager/mnpc'),deps,{})
        self.assertEqual(status,200)
        self.assertEqual(view['settings']['defaults'],DEFAULT_PROFILE)
        profile={**DEFAULT_PROFILE,'enabled':True,'full':120,'hide':240}
        payload={'expectedRevision':0,'kind':'','slug':'','profile':profile}
        status,view=write_world('/api/lod-manager/mnpc/settings',lambda:payload,deps)
        self.assertEqual(status,200)
        self.assertEqual(view['items'][0]['profile'],profile)
        self.assertFalse(view['runtimeEnabled'])
        self.assertEqual(write_world('/api/lod-manager/mnpc/settings',lambda:payload,deps)[0],400)
        payload.update(expectedRevision=1,kind='npc',slug='same',profile={**profile,'hide':125})
        self.assertEqual(write_world('/api/lod-manager/mnpc/settings',lambda:payload,deps)[0],400)
        payload['profile']={**profile,'full':140}
        self.assertEqual(write_world('/api/lod-manager/mnpc/settings',lambda:payload,deps)[0],200)
        self.assertFalse(self.owner.describe('npc','same')['inherits'])
        payload.update(expectedRevision=2,profile=None)
        self.assertEqual(write_world('/api/lod-manager/mnpc/settings',lambda:payload,deps)[0],200)
        self.assertTrue(self.owner.describe('npc','same')['inherits'])
        self.assertEqual(write_world('/api/lod-manager/mnpc/monster/same/stage',lambda:self.payload('monster'),deps)[0],200)
        self.assertEqual(read_world(urlsplit('/api/lod-manager/mnpc/monster/same/history'),deps,{})[1]['items'][0]['event'],'STAGED')
        self.assertEqual(write_world('/api/lod-manager/mnpc/monster/same/publish',lambda:{},deps)[0],400)


if __name__=='__main__':unittest.main()
