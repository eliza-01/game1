"""M130: House mesh visual options and safe retirement of registry entries."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.delete_entities import route as delete_route
from api.real_estate import write
from real_estate.store import RealEstateStore, glass_default
from real_estate.studio_sync import RealEstateStudioSync
from test_real_estate_m107 import skeleton


class RealEstateM130(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.incoming = self.root / 'incoming'
        self.incoming.mkdir()
        self.fbx = self.incoming / 'house_level2_01.fbx'
        self.fbx.write_bytes(b'model')
        self.texture = self.incoming / 'house.webp'
        self.texture.write_bytes(b'RIFFxxxxWEBP')
        self.store = RealEstateStore(self.root)

    @staticmethod
    def skeleton():
        data = skeleton()
        for part in ('front_glass', 'glass_panel', 'restoration', 'repair'):
            data['meshes'].append({'name': part, 'armature': '', 'vertices': 12,
                                    'bones': [], 'influencedBones': []})
        return data

    def register(self, slug_variant='01', options=None):
        source = self.fbx if slug_variant == '01' else self.incoming / f'house_level2_{slug_variant}.fbx'
        source.write_bytes(b'model'+slug_variant.encode())
        payload = {'houseType':'house','level':2,'variant':slug_variant,
                   'sourcePath':str(source), 'textures':{'house':str(self.texture)},
                   'textureReferences':{p:'mesh:house' for p in ('door','front_glass','glass_panel','restoration','repair')}}
        if options is not None: payload['meshOptions'] = options
        with mock.patch('real_estate.store.inspect', return_value=self.skeleton()):
            return self.store.register(payload)

    def test_glass_defaults_and_non_glass_legacy_mesh(self):
        self.assertTrue(glass_default('GLASS'))
        self.assertTrue(glass_default('glass_window'))
        self.assertFalse(glass_default('restoration'))
        house = self.register()
        self.assertTrue(house['meshOptions']['glass_panel']['glass'])
        self.assertTrue(house['meshOptions']['front_glass']['glass'])
        self.assertFalse(house['meshOptions']['house']['glass'])
        self.assertFalse(house['meshOptions']['repair']['glass'])
        self.assertFalse(house['meshOptions']['restoration']['glass'])
        saved = RealEstateStore(self.root).get(house['slug'])
        self.assertEqual(house['meshOptions'], saved['meshOptions'])

    def test_checkbox_can_override_and_survive_existing_house_edit(self):
        house = self.register(options={'front_glass':{'glass':False},'house':{'glass':True}})
        self.assertFalse(house['meshOptions']['front_glass']['glass'])
        self.assertTrue(house['meshOptions']['house']['glass'])
        edited = self.store.register({'existingSlug':house['slug'], 'sourcePath':'',
            'houseType':'house','level':2,'variant':'01',
            'textures':{'house':house['textures']['house']['path']},
            'textureReferences':{p:'mesh:house' for p in ('door','front_glass','glass_panel','restoration','repair')},
            'meshOptions':{'front_glass':{'glass':True},'house':{'glass':False}}})
        self.assertTrue(edited['meshOptions']['front_glass']['glass'])
        self.assertFalse(edited['meshOptions']['house']['glass'])
        self.assertTrue(edited['meshOptions']['glass_panel']['glass'])
        self.assertEqual(edited['status'], 'LOCAL_ONLY')

    def test_studio_receives_mesh_options(self):
        house = self.register()
        with self.store.connect() as db:
            rigs={part:{'assetId':str(i+5000),'publishedSha256':house['model_sha256']}
                  for i,part in enumerate(house['meshParts'])}
            textures = json.loads(db.execute('SELECT textures_json FROM real_estate').fetchone()[0])
            textures['house']['assetId']='8001'
            textures['house']['publishedSha256']=textures['house']['sha256']
            textures['house']['publicationFormat']='png'  # test bypass: fix effective format below
            from real_estate.publication_textures import published_format
            textures['house']['publicationFormat']=published_format(Path(textures['house']['path']))
            db.execute('UPDATE real_estate SET model_rigs_json=?, model_asset_id=?, model_published_hash=?, textures_json=?',
                       (json.dumps(rigs),rigs['house']['assetId'],house['model_sha256'],json.dumps(textures)))
        calls=[]
        def load(*args,**kwargs):
            calls.append(kwargs['metadata'])
            return {'realEstateStats':{'bonesValidated':True,'rigsValidated':len(house['meshParts']),'texturesApplied':len(house['meshParts'])},'destination':'test'}
        RealEstateStudioSync(self.store,load).sync(house['slug'])
        self.assertTrue(calls[0]['meshOptions']['glass_panel']['glass'])

    def test_delete_preserves_files_and_publication_history(self):
        house=self.register()
        with self.store.connect() as db:
            db.execute("INSERT INTO real_estate_publications(house_slug,part,asset_id,sha256,operation,published_at) VALUES(?,?,?,?,?,?)",
                       (house['slug'],'house','9001','sha','op',123))
        output = self.store.delete(house['slug'])
        self.assertTrue(output['ok'])
        self.assertTrue(output['studioTemplatesUnchanged'])
        self.assertIsNone(self.store.get(house['slug']))
        self.assertTrue((self.root/house['model_path']).is_file())
        archived = json.loads((self.root / output['archived']).read_text('utf8'))
        self.assertEqual(archived['publications'][0]['asset_id'],'9001')
        self.assertEqual(self.store.publications(house['slug']),[])

    def test_delete_blocks_dependent_house(self):
        house=self.register()
        other=self.register('02')
        with self.store.connect() as db:
            raw=db.execute('SELECT textures_json FROM real_estate WHERE slug=?', (other['slug'],)).fetchone()[0]
            textures=json.loads(raw)
            textures['house']['reuseReference']=f"estate:{house['slug']}:house"
            db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?', (json.dumps(textures),other['slug']))
        with self.assertRaisesRegex(ValueError,'reused by'):
            self.store.delete(house['slug'])
        self.assertIsNotNone(self.store.get(house['slug']))

    def test_delete_http_checks_running_job(self):
        self.register()
        deps={'real_estate':self.store, 'real_estate_publications':mock.Mock()}
        deps['real_estate_publications'].get.return_value={'status':'running'}
        status,out=delete_route('/api/real-estate/house_level2_01',lambda:{},deps)
        self.assertEqual(status,400)
        self.assertIn('running',out['error'])
        deps['real_estate_publications'].get.return_value=None
        status,out=delete_route('/api/real-estate/house_level2_01',lambda:{},deps)
        self.assertEqual(status,200)
        self.assertTrue(out['sourceFilesPreserved'])

    def test_real_estate_registration_syncs_glass_changes_when_published(self):
        house=self.register()
        params={'existingSlug':house['slug'],'sourcePath':'','houseType':'house','level':2,'variant':'01',
                'textures':{'house':house['textures']['house']['path']},
                'textureReferences':{p:'mesh:house' for p in ('door','front_glass','glass_panel','restoration','repair')},
                'meshOptions':{'glass_panel':{'glass':False}}}
        with self.store.connect() as db:
            rigs={part:{'assetId':str(i+5000),'publishedSha256':house['model_sha256']}
                  for i,part in enumerate(house['meshParts'])}
            textures=json.loads(db.execute('SELECT textures_json FROM real_estate').fetchone()[0])
            textures['house']['assetId']='8001'
            textures['house']['publishedSha256']=textures['house']['sha256']
            from real_estate.publication_textures import published_format
            textures['house']['publicationFormat']=published_format(Path(textures['house']['path']))
            db.execute('UPDATE real_estate SET model_rigs_json=?,model_asset_id=?,model_published_hash=?,textures_json=?',
                (json.dumps(rigs),rigs['house']['assetId'],house['model_sha256'],json.dumps(textures)))
        sync=mock.Mock(return_value={'studio':{}})
        status,result=write('/api/real-estate',lambda:params,{'real_estate':self.store,'sync_real_estate_to_studio':sync})
        self.assertEqual(status,200)
        self.assertEqual(result['studioSyncStatus'],'synced')
        sync.assert_called_once_with(house['slug'])
        self.assertFalse(result['meshOptions']['glass_panel']['glass'])
