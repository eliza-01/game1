"""M140: one authored mesh revision, one new Model ID, isolated Studio sync."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from real_estate.store import RealEstateStore
from real_estate.studio_sync import RealEstateStudioSync
from real_estate.publication_textures import published_format
from test_real_estate_m107 import skeleton


class ScopedMeshTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        folder = self.root/'incoming'; folder.mkdir()
        self.scene = folder/'house_level1_01.fbx'; self.scene.write_bytes(b'whole-house-original')
        self.revised = folder/'restoration.fbx'; self.revised.write_bytes(b'only-one-mesh-updated')
        self.all_changed = folder/'whole-changed.fbx'; self.all_changed.write_bytes(b'whole-house-changed')
        self.house_png=folder/'house.png';self.house_png.write_bytes(b'img-house')
        self.door_png=folder/'door.png';self.door_png.write_bytes(b'img-door')
        self.store=RealEstateStore(self.root)
        with patch('real_estate.store.inspect',return_value=skeleton()):
            self.first=self.store.register({'sourcePath':str(self.scene),
                'houseType':'house','level':1,'variant':'01',
                'textures':{'house':str(self.house_png),'door':str(self.door_png)}})
        self.slug=self.first['slug']
        textures=json.loads(json.dumps(self.first['textures']))
        for part in ('house','door'):
            textures[part].update(assetId='8101' if part == 'door' else '8001',
                                  publishedSha256=textures[part]['sha256'],
                                  publicationFormat=published_format(Path(textures[part]['path'])))
        rigs={part:{'assetId':str(index),'publishedSha256':self.first['model_sha256']}
              for part,index in (('house',10001),('door',10002))}
        with self.store.connect() as db:
            db.execute('UPDATE real_estate SET model_rigs_json=?,model_asset_id=?,model_published_hash=?,textures_json=? WHERE slug=?',
                (json.dumps(rigs), '10001', self.first['model_sha256'],json.dumps(textures),self.slug))
        self.assertTrue(self.store.get(self.slug)['publicationCurrent']['model'])

    def replace(self, source=None):
        source=source or self.revised
        new = dict(next(mesh for mesh in skeleton()['meshes'] if mesh['name']=='door'))
        new['vertices'] += 23
        with patch('real_estate.store.inspect_revision',return_value=new):
            return self.store.replace_mesh(self.slug,'door',str(source),
                expected_revision=self.store.get(self.slug)['revision'])

    def test_one_mesh_update_preserves_every_other_id_and_atlas(self):
        before=self.store.get(self.slug)
        updated=self.replace()
        self.assertEqual(updated['model_sha256'],before['model_sha256'])
        self.assertEqual(updated['rigAssets'],before['rigAssets'])
        self.assertEqual(updated['textures'],before['textures'])
        self.assertTrue(updated['publicationCurrent']['house'])
        self.assertFalse(updated['publicationCurrent']['model'])
        self.assertNotEqual(updated['rigSourceHashes']['door'],before['model_sha256'])
        self.assertEqual(updated['rigSourceHashes']['house'],before['model_sha256'])
        self.assertEqual(updated['skeleton']['meshes'][1]['vertices'],
                         before['skeleton']['meshes'][1]['vertices']+23)
        stored=self.root/updated['meshSources']['door']['path']
        self.assertEqual(stored.read_bytes(),self.revised.read_bytes())
        self.assertEqual(self.store.get(self.slug)['rigSourceHashes'],updated['rigSourceHashes'])
        with self.assertRaisesRegex(ValueError,'changed since inspection'):
            self.store.replace_mesh(self.slug,'door',str(self.revised),expected_revision=before['revision'])

    def test_revise_from_whole_fbx_extracts_only_selected_part(self):
        updated=self.replace(self.all_changed)
        self.assertEqual(updated['meshSources']['door']['sha256'],updated['rigSourceHashes']['door'])
        self.assertTrue(updated['publicationCurrent']['house'])
        self.assertEqual(updated['rigAssets']['house']['assetId'],'10001')

    def test_one_new_model_id_and_targeted_sync_without_image_upload(self):
        self.replace()
        uploads=[]
        def stage(root,source,target,expected,textures,*,only_part):
            self.assertEqual(only_part,'door')
            self.assertEqual(set(textures),{'door'})
            self.assertEqual(len(expected['meshes']),1)
            self.assertEqual(expected['meshes'][0]['name'],'door')
            (target/'door.fbx').parent.mkdir(parents=True,exist_ok=True)
            (target/'door.fbx').write_bytes(b'exported-rig')
        def uploaded(path,**kw):
            uploads.append(path.stem)
            return 'operation/door'
        with patch('real_estate.store.prepare_publication',side_effect=stage), \
             patch('real_estate.store.prepare_texture',side_effect=lambda root,part,source,target:source), \
             patch('real_estate.store.create_model_asset',side_effect=uploaded), \
             patch('real_estate.store.create_image_asset',side_effect=AssertionError('image upload forbidden')), \
             patch('real_estate.store.wait_for_operation',return_value=SimpleNamespace(asset_id='90003',moderation_state='Approved')):
            done=self.store.publish(self.slug, {'apiKey':'fake','creatorType':'user','creatorId':'1'},scope='model:door')
        self.assertEqual(uploads,['door'])
        self.assertEqual(done['rigAssets']['house']['assetId'],'10001')
        self.assertEqual(done['rigAssets']['door']['assetId'],'90003')
        self.assertEqual(done['model_asset_id'],'10001')
        self.assertEqual(done['textures']['door']['assetId'],self.first['textures']['door'].get('assetId') or '8101')
        self.assertTrue(done['publicationCurrent']['model'])
        def load(asset,folders,**kwargs):
            self.assertEqual(asset,'90003')
            self.assertEqual(kwargs['metadata']['syncPart'],'door')
            self.assertEqual(kwargs['metadata']['rigAssetIds']['house'],'10001')
            return {'realEstateStats':{'bonesValidated':True,'rigsValidated':1,'texturesApplied':1}}
        result=RealEstateStudioSync(self.store,load).sync(self.slug,part='door')
        self.assertIn('studio',result)

    def test_scoped_sync_rejects_unpublished_revision(self):
        self.replace()
        with self.assertRaisesRegex(ValueError,'publish the changed mesh'):
            RealEstateStudioSync(self.store,lambda *a,**kw:None).sync(self.slug,part='door')

    def test_luau_and_ui_scoped_integration(self):
        project=json.loads((ROOT/'system/studio-plugin/plugin.project.json').read_text())
        self.assertIn('StudioRealEstatePartSync',project['tree']['modules'])
        lua=(ROOT/'system/studio-plugin/modules/StudioRealEstatePartSync.luau').read_text()
        self.assertIn('Game1RigAssetIds',lua)
        self.assertIn('run full Sync Studio first',lua)
        self.assertIn('replacement:Clone()',lua)
        ui=(ROOT/'system/control-center/static/real-estate.js').read_text()
        self.assertIn('/mesh-inspect',ui)
        self.assertIn('/mesh-source',ui)
        workflow=(ROOT/'system/control-center/static/real-estate-mesh-workflow.js').read_text(encoding='utf-8')
        self.assertIn('data-mw-sync', workflow)
        self.assertIn('realEstateSync(row.slug,part)', workflow)
        self.assertIn('workspaceModelsUpdated', workflow)

if __name__=='__main__':unittest.main()
