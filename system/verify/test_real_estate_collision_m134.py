"""M134: collision-only geometry reuses the Estate model pipeline, not image publishing."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.collision_policy import is_collision_mesh, requires_texture, default_no_collide
from real_estate.store import RealEstateStore, mesh_options
from real_estate.studio_sync import RealEstateStudioSync
from test_real_estate_m107 import skeleton


class RealEstateColliderM134(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'house_level4_01.fbx'
        self.source.write_bytes(b'model')
        self.image = self.root / 'house.png'
        self.image.write_bytes(b'png fake test bytes')
        self.store = RealEstateStore(self.root)

    def scene(self):
        value = skeleton()
        value['meshes'].append({'name':'house_col','armature':'','vertices':64,
                                'bones':[], 'influencedBones':[]})
        return value

    def register(self, **more):
        payload = {'houseType':'house','level':4,'variant':'01', 'sourcePath':str(self.source),
                   'textures':{'house':str(self.image)},
                   'textureReferences':{'door':'mesh:house'}, **more}
        with mock.patch('real_estate.store.inspect', return_value=self.scene()):
            return self.store.register(payload)

    def test_name_classification_is_token_based_and_case_insensitive(self):
        for name in ('COL_Floor','house_col','wall_COL_01','col_stairs','HOUSE_COL'):
            self.assertTrue(is_collision_mesh(name),name)
            self.assertFalse(requires_texture(name))
            self.assertFalse(default_no_collide(name))
        for name in ('house','restoration','door','column','cologne','window_frames_glass'):
            self.assertFalse(is_collision_mesh(name),name)
            self.assertTrue(requires_texture(name))
            self.assertTrue(default_no_collide(name))

    def test_options_default_and_explicit_overrides(self):
        opts=mesh_options(['house','window_frames_glass','house_col'], {})
        self.assertTrue(opts['house']['noCollide'])
        self.assertTrue(opts['window_frames_glass']['glass'])
        self.assertFalse(opts['house_col']['glass'])
        self.assertFalse(opts['house_col']['noCollide'])
        self.assertTrue(opts['house_col']['collisionMesh'])
        modified=mesh_options(['house','house_col'], {'house':{'noCollide':False},'house_col':{'noCollide':True}})
        self.assertFalse(modified['house']['noCollide'])
        self.assertTrue(modified['house_col']['noCollide'])

    def test_registration_without_col_texture_survives_restart(self):
        row=self.register()
        self.assertIn('house_col',row['meshParts'])
        self.assertEqual(row['textures']['house_col']['assetId'],'')
        self.assertEqual(row['textures']['house_col']['path'],'')
        self.assertTrue(row['publicationCurrent']['house_col'])
        self.assertFalse(row['meshOptions']['house_col']['noCollide'])
        self.assertTrue(row['meshOptions']['house']['noCollide'])
        self.assertEqual(row['status'],'LOCAL_ONLY')
        again=RealEstateStore(self.root).get(row['slug'])
        self.assertEqual(row['meshOptions'],again['meshOptions'])
        self.assertEqual(row['model_sha256'],again['model_sha256'])

    def test_collider_image_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'collision mesh must not select a texture reference'):
            self.register(textureReferences={'door':'mesh:house','house_col':'mesh:house'})

    def test_col_checkbox_can_be_changed_without_model_or_image_republish(self):
        row=self.register()
        edited=self.store.register({'houseType':'house','level':4,'variant':'01',
            'existingSlug':row['slug'], 'sourcePath':'',
            'textures':{'house':row['textures']['house']['path']},
            'textureReferences':{'door':'mesh:house'},
            'meshOptions':{'house':{'noCollide':False},'house_col':{'noCollide':True}}})
        self.assertFalse(edited['meshOptions']['house']['noCollide'])
        self.assertTrue(edited['meshOptions']['house_col']['noCollide'])
        self.assertEqual(edited['model_sha256'],row['model_sha256'])
        self.assertEqual(edited['textures']['house']['assetId'],row['textures']['house']['assetId'])

    def test_publishing_models_skips_collider_image_and_sync_payload(self):
        row=self.register()
        assets=iter([9001,9002,9003,9004])
        def fake_prepare(root,model,dst,expected,textures):
            dst.mkdir(parents=True, exist_ok=True)
            self.assertNotIn('house_col',textures)
            for part in row['meshParts']:
                (dst/f'{part}.fbx').write_bytes(b'exported')
        with mock.patch('real_estate.store.prepare_publication',side_effect=fake_prepare), \
            mock.patch('real_estate.store.create_model_asset',return_value='op-model') as model_api, \
            mock.patch('real_estate.store.create_image_asset',return_value='op-image') as image_api, \
            mock.patch('real_estate.store.wait_for_operation',side_effect=lambda *a,**kw:SimpleNamespace(asset_id=next(assets),moderation_state='Approved')):
            published=self.store.publish(row['slug'],{'apiKey':'fake','creatorType':'User','creatorId':'1'},scope='model')
            self.assertEqual(model_api.call_count,len(row['meshParts']))
            self.assertEqual(image_api.call_count,0)
        self.assertEqual(published['textures']['house_col']['assetId'],'')
        with self.assertRaisesRegex(ValueError,'no Image Asset'):
            self.store.publish(row['slug'], {'apiKey':'fake','creatorType':'User','creatorId':'1'},scope='image:house_col')
        # Set only the house Image ready; the door reuses that image.
        with self.store.connect() as db:
            tex=json.loads(db.execute('SELECT textures_json FROM real_estate').fetchone()[0])
            tex['house']['assetId']='5555'
            tex['house']['publishedSha256']=tex['house']['sha256']
            from real_estate.publication_textures import published_format
            tex['house']['publicationFormat']=published_format(Path(tex['house']['path']))
            db.execute('UPDATE real_estate SET textures_json=?,model_published_hash=?',
                (json.dumps(tex),row['model_sha256']))
        calls=[]
        def load(*args,**kwargs):
            calls.append(kwargs['metadata'])
            return {'realEstateStats':{'bonesValidated':True,
                'rigsValidated':len(row['meshParts']),'texturesApplied':len(row['meshParts'])-1}}
        synced=RealEstateStudioSync(self.store,load).sync(row['slug'])
        self.assertEqual(synced['realEstate']['status'],'PUBLISHED')
        self.assertEqual({x['slot'] for x in calls[0]['textures']},{'house','door'})
        self.assertFalse(calls[0]['meshOptions']['house_col']['noCollide'])

    def test_studio_plugin_contract_and_blender_export(self):
        plugin=(ROOT/'system/studio-plugin/modules/StudioRealEstateModel.luau').read_text('utf8')
        policy=(ROOT/'system/studio-plugin/modules/StudioRealEstateCollisionPolicy.luau').read_text('utf8')
        prepare=(ROOT/'system/asset-manager/prepare_real_estate_publication_fbx.py').read_text('utf8')
        manifest=(ROOT/'system/studio-plugin/plugin.project.json').read_text('utf8')
        installer=(ROOT/'system/studio-plugin/install.ps1').read_text('utf8')
        self.assertIn('StudioRealEstateCollisionPolicy.Apply',plugin)
        self.assertIn('CanQuery = true',policy)
        self.assertIn('mesh.Transparency = 1',policy)
        self.assertIn('CollisionFidelity.PreciseConvexDecomposition',policy)
        self.assertIn('if is_collision_mesh(part):',prepare)
        self.assertIn('StudioRealEstateCollisionPolicy',manifest)
        self.assertIn('StudioRealEstateCollisionPolicy',installer)
        self.assertIn('StudioRealEstatePlacedCollisionSync',manifest)
        self.assertIn('StudioRealEstatePlacedCollisionSync',installer)
        self.assertIn('workspaceCollisionRigsUpdated',plugin)


if __name__=='__main__':
    import unittest
    unittest.main()
