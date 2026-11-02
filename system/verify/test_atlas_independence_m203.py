"""Atlas identity and publication are independent of all authoring model slugs."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from real_estate.store import RealEstateStore
from services.shared_asset_retirement import SharedAssetRetirement
from test_real_estate_m107 import skeleton


class AtlasIndependenceM203(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.model=self.root/'sample.fbx'
        self.model.write_bytes(b'fake FBX source')
        self.image=self.root/'restoration_01_32x32_atlas.png'
        Image.new('RGBA',(32,32),(14,24,34,127)).save(self.image)
        self.location=LocationAssetStore(self.root)
        self.estate=RealEstateStore(self.root, location_assets=self.location)

    def light(self, slug, variant=None):
        data={'slug':slug,'nameEn':slug,'category':'light',
              'modelSourcePath':str(self.model)}
        data.update({'atlasVariantId':variant} if variant else {'textureSourcePath':str(self.image)})
        return self.location.register(data)

    def house(self, variant='01'):
        with mock.patch('real_estate.store.inspect',return_value=skeleton()):
            return self.estate.register({'houseType':'house','level':5,'variant':variant,
                'sourcePath':str(self.model),'textures':{'house':str(self.image)},
                'textureReferences':{'door':'same:house'}})

    def published(self, variant_id, asset_id):
        with self.location.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       (asset_id,variant_id))

    def test_new_models_share_atlas_without_ownership(self):
        first=self.light('old_owner')
        second=self.light('new_follower',first['atlasVariantId'])
        house=self.house()
        self.assertEqual({first['atlasVariantId'],second['atlasVariantId'],
                          house['textures']['door']['atlasVariantId']},{first['atlasVariantId']})
        self.published(first['atlasVariantId'],'99900220')
        plan=SharedAssetRetirement(self.estate,self.location).plan('location','old_owner')
        self.assertEqual(plan['dependentCount'],0)
        SharedAssetRetirement(self.estate,self.location).execute('location','old_owner',token=plan['token'])
        after=self.location.get('new_follower')
        self.assertEqual(after['texture_asset_id'],'99900220')
        self.assertEqual(self.estate.get(house['slug'])['textures']['door']['assetId'],'99900220')
        with self.location.connect() as db:
            self.assertFalse(db.execute('SELECT 1 FROM sqlite_master WHERE name="retained_shared_textures"').fetchone())
        self.assertEqual(self.light('old_owner',first['atlasVariantId'])['slug'],'old_owner')
        again=RealEstateStore(self.root,location_assets=LocationAssetStore(self.root))
        self.assertEqual(again.get(house['slug'])['textures']['door']['assetId'],'99900220')

    def legacy_columns(self):
        # Emulate the exact owner-era SQLite layout before the M203 upgrade.
        with self.location.connect() as db:
            for name, definition in (
                ('texture_path', "TEXT NOT NULL DEFAULT ''"),
                ('texture_filename', "TEXT NOT NULL DEFAULT ''"),
                ('texture_sha256', "TEXT NOT NULL DEFAULT ''"),
                ('texture_asset_id', 'TEXT'),
                ('texture_published_sha256', "TEXT NOT NULL DEFAULT ''"),
                ('texture_moderation_state', "TEXT NOT NULL DEFAULT ''"),
                ('texture_reference_slug', "TEXT NOT NULL DEFAULT ''"),
            ):
                db.execute(f'ALTER TABLE location_assets ADD COLUMN {name} {definition}')

    def test_unpublished_owner_era_reference_migrates_without_upload(self):
        first=self.light('old_lamp')
        second=self.light('other_lamp',first['atlasVariantId'])
        self.legacy_columns()
        with self.location.connect() as db:
            db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type="location_asset"')
            db.execute('''UPDATE location_assets SET texture_path=?,texture_filename=?,texture_sha256=?,
                texture_asset_id=NULL,texture_published_sha256='' WHERE slug='old_lamp' ''',
                (str(self.image.relative_to(self.root)),self.image.name,first['texture_sha256']))
            db.execute('''UPDATE location_assets SET texture_reference_slug='old_lamp',
                texture_path='',texture_filename='',texture_sha256='' WHERE slug='other_lamp' ''')
        fresh_loc=LocationAssetStore(self.root)
        with mock.patch('services.texture_atlas_registry.create_image_asset',side_effect=AssertionError('network upload')):
            fresh_est=RealEstateStore(self.root,location_assets=fresh_loc)
        self.assertEqual(fresh_loc.get('old_lamp')['atlasVariantId'],
                         fresh_loc.get('other_lamp')['atlasVariantId'])
        self.assertFalse(fresh_loc.get('other_lamp')['texture_asset_id'])
        with fresh_loc.connect() as db:
            self.assertNotIn('texture_reference_slug', {r[1] for r in db.execute('PRAGMA table_info(location_assets)')})
        self.assertNotIn('texture_owner_slug',fresh_est.location_assets.get('other_lamp'))

    def test_deleted_owner_snapshots_keep_published_identity(self):
        first=self.light('old_deleted')
        self.published(first['atlasVariantId'],'75000002')
        consumer=self.light('follower',first['atlasVariantId'])
        self.legacy_columns()
        with self.location.connect() as db:
            db.execute('''CREATE TABLE retained_shared_textures (
                reference TEXT PRIMARY KEY,snapshot_json TEXT NOT NULL,created_at REAL NOT NULL)''')
            db.execute('INSERT INTO retained_shared_textures VALUES (?,?,0)',
                       ('location:old_deleted',json.dumps({
                        'texture_path':self.image.relative_to(self.root).as_posix(),
                        'texture_filename':self.image.name,'texture_sha256':first['texture_sha256'],
                        'texture_published_sha256':first['texture_sha256'],
                        'texture_asset_id':'75000002'})))
            db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type="location_asset" AND consumer_id="old_deleted"')
            db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type="location_asset" AND consumer_id="follower"')
            db.execute('DELETE FROM location_assets WHERE slug="old_deleted"')
            db.execute('UPDATE location_assets SET texture_reference_slug="old_deleted" WHERE slug="follower"')
        loc=LocationAssetStore(self.root)
        RealEstateStore(self.root,location_assets=loc)
        self.assertEqual(loc.get('follower')['texture_asset_id'],'75000002')
        with loc.connect() as db:
            self.assertFalse(db.execute('SELECT 1 FROM sqlite_master WHERE name="retained_shared_textures"').fetchone())
        self.assertEqual(loc.register({'slug':'old_deleted','nameEn':'reborn','category':'light',
            'modelSourcePath':str(self.model),'atlasVariantId':loc.get('follower')['atlasVariantId']})['slug'],'old_deleted')

    def test_source_name_independent_of_model_slug_and_webp(self):
        self.light('owner_one')
        file=self.root/'wooden_post_kit.webp'
        Image.new('RGBA',(16,32),(1,2,3,64)).save(file,'WEBP')
        made=self.location.register({'slug':'some_tree','nameEn':'Tree','category':'tree',
            'modelSourcePath':str(self.model),'textureSourcePath':str(file)})
        self.assertEqual(made['atlasFamily'],'wooden_post_kit')
        self.assertTrue((self.root/made['texture_path']).is_file())
        self.assertTrue(made['texture_path'].endswith('.png'))

    def test_model_registration_never_stages_atlas_replacement(self):
        self.light('first')
        changed=self.root/'incoming'/'restoration_01_32x32_atlas.png'
        changed.parent.mkdir()
        Image.new('RGBA',(32,32),(255,0,0,255)).save(changed)
        with self.assertRaisesRegex(ValueError,'replace/republish'):
            self.location.register({'slug':'second','nameEn':'Second','category':'light',
                'modelSourcePath':str(self.model),'textureSourcePath':str(changed)})
        self.assertFalse(self.location.atlases.get_variant(1)['replacementPending'])

    def test_registry_sources_archived_out_of_old_model_slug(self):
        first = self.light('house_level4_01')
        old = self.root/'assets/source/location-assets/light/house_level4_01/texture/restoration_01_32x32_atlas.png'
        old.parent.mkdir(parents=True)
        old.write_bytes(self.image.read_bytes())
        with self.location.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET source_path=? WHERE id=?',
                (old.relative_to(self.root).as_posix(),first['atlasVariantId']))
        RealEstateStore(self.root, location_assets=LocationAssetStore(self.root))
        variant = self.location.atlases.get_variant(first['atlasVariantId'])
        self.assertTrue(variant['source_path'].startswith('assets/source/texture-atlases/'))
        self.assertEqual((self.root/variant['source_path']).read_bytes(), self.image.read_bytes())
        self.assertTrue(old.is_file())

    def test_repeat_migration_is_idempotent(self):
        first = self.light('estate_origin')
        RealEstateStore(self.root, location_assets=LocationAssetStore(self.root))
        after = LocationAssetStore(self.root)
        RealEstateStore(self.root, location_assets=after)
        self.assertEqual(after.get('estate_origin')['atlasVariantId'], first['atlasVariantId'])
        with after.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM texture_atlas_bindings WHERE consumer_id=?',
                ('estate_origin',)).fetchone()[0], 1)

    def test_migration_fails_closed_when_old_source_is_missing(self):
        self.legacy_columns()
        with self.location.connect() as db:
            db.execute('''INSERT INTO location_assets(slug,name_en,category,model_path,model_sha256,
                destructible,revision,created_at,updated_at,texture_path,texture_filename,texture_sha256)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('broken','broken','light','','',0,1,1,1,
                 'assets/source/location-assets/no-image.png','no-image.png','0'*64))
        loc = LocationAssetStore(self.root)
        with self.assertRaisesRegex(ValueError,'source missing'):
            RealEstateStore(self.root, location_assets=loc)
        with loc.connect() as db:
            self.assertIn('texture_path', {r[1] for r in db.execute('PRAGMA table_info(location_assets)')})

    def test_distinct_published_ids_for_same_bytes_do_not_merge(self):
        import hashlib
        digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.legacy_columns()
        for slug, asset_id in [('a','77112233'),('b','88445566')]:
            with self.location.connect() as db:
                db.execute('''INSERT INTO location_assets(slug,name_en,category,model_path,model_sha256,
                    destructible,revision,created_at,updated_at,texture_path,texture_filename,
                    texture_sha256,texture_asset_id,texture_published_sha256)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (slug,slug,'light','','',0,1,1,1,self.image.relative_to(self.root).as_posix(),
                     self.image.name,digest,asset_id,digest))
        loc = LocationAssetStore(self.root)
        RealEstateStore(self.root, location_assets=loc)
        self.assertEqual({loc.get('a')['texture_asset_id'],loc.get('b')['texture_asset_id']},
                         {'77112233','88445566'})
        self.assertNotEqual(loc.get('a')['atlasVariantId'],loc.get('b')['atlasVariantId'])

    def test_unpublished_shared_variant_is_visible_without_cascade(self):
        first = self.light('temp_one')
        self.light('temp_two', first['atlasVariantId'])
        plan = SharedAssetRetirement(self.estate, self.location).plan('location', 'temp_one')
        self.assertEqual(plan['dependentCount'], 0)
        self.assertEqual(plan['sharedAtlasUses'][0]['variantId'], first['atlasVariantId'])
        self.assertFalse(plan['sharedAtlasUses'][0]['assetId'])
        self.assertEqual(plan['sharedAtlasUses'][0]['uses'],
                         [{'dependent':'location:temp_two','part':'texture'}])

    def test_retired_estate_source_stays_independent_after_slug_reuse(self):
        import hashlib
        original = self.house()
        target_slug = original['slug']
        self.published(original['textures']['house']['atlasVariantId'], '6223445566')
        sha = hashlib.sha256(self.image.read_bytes()).hexdigest()
        with self.location.connect() as db:
            db.execute('''CREATE TABLE retained_shared_textures(
                reference TEXT PRIMARY KEY,snapshot_json TEXT NOT NULL,created_at REAL NOT NULL)''')
            db.execute('INSERT INTO retained_shared_textures VALUES (?,?,0)',
                       ('estate:house_level4_01:restoration',json.dumps({
                           'path':self.image.relative_to(self.root).as_posix(),
                           'filename':self.image.name,'sha256':sha,'publishedSha256':sha,
                           'assetId':'6223445566'})))
            db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type=? AND consumer_id=?',
                       ('real_estate',target_slug+':door'))
        with self.estate.connect() as db:
            row=db.execute('SELECT textures_json FROM real_estate WHERE slug=?',(target_slug,)).fetchone()
            data=json.loads(row['textures_json'])
            data['door']={'reuseReference':'estate:house_level4_01:restoration',
                          'path':'','filename':'','sha256':'','assetId':'','publishedSha256':''}
            db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?',
                       (json.dumps(data), target_slug))
        new_location=LocationAssetStore(self.root)
        migrated=RealEstateStore(self.root,location_assets=new_location)
        after=migrated.get(target_slug)['textures']['door']
        self.assertEqual(after['assetId'],'6223445566')
        self.assertTrue(after['atlasVariantId'])
        self.assertEqual(new_location.atlases.get_variant(after['atlasVariantId'])['published_id'],'6223445566')
        with mock.patch('real_estate.store.inspect',return_value=skeleton()):
            new=migrated.register({'houseType':'house','level':4,'variant':'01',
                'sourcePath':str(self.model),'textures':{'house':str(self.image)},
                'textureReferences':{'door':'same:house'}})
        self.assertEqual(new['slug'],'house_level4_01')
        self.assertEqual(migrated.get(target_slug)['textures']['door']['assetId'],'6223445566')

    def test_location_publication_never_uploads_already_published_shared_atlas(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        first=self.light('published_one')
        self.published(first['atlasVariantId'],'5588990011')
        second=self.light('published_two',first['atlasVariantId'])
        @contextmanager
        def staged(_root, source):
            yield source
        credentials={'creatorType':'user','creatorId':'1','apiKey':'test-key'}
        with mock.patch('location_asset_store.staged_model',side_effect=staged), \
             mock.patch('location_asset_store.create_model_asset',return_value='operation:model') as create_model, \
             mock.patch('location_asset_store.wait_for_operation',return_value=SimpleNamespace(
                 asset_id='12345678',operation_path='operation:model',moderation_state='Approved')), \
             mock.patch('services.texture_atlas_registry.create_image_asset',side_effect=AssertionError('duplicate PNG upload')):
            result=self.location.publish('published_two',credentials)
        create_model.assert_called_once()
        self.assertEqual(result['model_asset_id'],'12345678')
        self.assertEqual(result['texture_asset_id'],'5588990011')
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(self.location.get('published_one')['texture_asset_id'],'5588990011')

    def test_deleting_older_house_keeps_independent_variants_and_model_slugs(self):
        original=self.house()
        same_variant=original['textures']['door']['atlasVariantId']
        old_slug=original['slug']
        another=self.light('shared_deco',same_variant)
        self.published(same_variant,'4400221133')
        result=self.estate.delete(old_slug)
        self.assertTrue(result['sourceFilesPreserved'])
        self.assertEqual(self.location.get(another['slug'])['texture_asset_id'],'4400221133')
        self.assertEqual(self.location.atlases.get_variant(same_variant)['published_id'],'4400221133')
        with mock.patch('real_estate.store.inspect',return_value=skeleton()):
            renewed=self.estate.register({'houseType':'house','level':5,'variant':'01',
                'sourcePath':str(self.model),'textures':{'house':str(self.image)},
                'textureReferences':{'door':'same:house'}})
        self.assertEqual(renewed['slug'],old_slug)
        self.assertEqual(renewed['textures']['door']['atlasVariantId'],same_variant)
