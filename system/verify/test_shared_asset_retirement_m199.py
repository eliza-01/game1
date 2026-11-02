"""M199: shared images outlive their first model registration.

No network publication, FBX parsing or Studio runtime involved. These are real
SQLite-backed stores, not replacements of the deletion methods under test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from real_estate.store import RealEstateStore
from real_estate.publication_textures import published_format
from services.shared_asset_retirement import SharedAssetRetirement
from api.read_world import route as read_world
from api.write_dispatch import dispatch_post
from test_real_estate_m107 import skeleton
from urllib.parse import urlparse


class SharedAssetRetirementM199(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        folder = self.root / 'incoming'
        folder.mkdir()
        self.model = folder / 'test.fbx'
        self.model.write_bytes(b'FBX mock')
        self.image = folder / 'structure_01_32x32_atlas.png'
        self.legacy_image = folder / 'legacy_house_texture.png'
        Image.new('RGB', (32,32), (12,23,34)).save(self.legacy_image)
        Image.new('RGB', (32,32), (44,55,66)).save(self.image)
        self.loc = LocationAssetStore(self.root)
        self.estate = RealEstateStore(self.root, location_assets=self.loc)
        self.service = SharedAssetRetirement(self.estate, self.loc)

    def register_location(self, slug, owner=None):
        data = {'slug': slug, 'nameEn': slug, 'category': 'building', 'modelSourcePath': str(self.model)}
        if owner:
            data['textureReferenceSlug'] = owner
        else:
            data['textureSourcePath'] = str(self.image)
        return self.loc.register(data)

    def publish_location_atlas(self, row, asset_id='123456789'):
        with self.loc.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       (asset_id, row['atlasVariantId']))

    def register_house(self, variant='01', ref='', *, legacy=False, consumer_part='house'):
        fbx = self.root / 'incoming' / f'house_level5_{variant}.fbx'
        fbx.write_bytes(b'House mock ' + variant.encode())
        payload = {'houseType': 'house', 'level': 5, 'variant': variant,
                   'sourcePath': str(fbx), 'textures': {'house': str(self.legacy_image if legacy else self.image)},
                   'textureReferences': {'door': 'mesh:house'}}
        with mock.patch('real_estate.store.inspect', return_value=skeleton()):
            house = self.estate.register(payload)
        if ref:
            with self.estate.connect() as db:
                textures = json.loads(db.execute('SELECT textures_json FROM real_estate WHERE slug=?',
                                                 (house['slug'],)).fetchone()[0])
                textures[consumer_part]['reuseReference'] = ref
                db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?',
                           (json.dumps(textures), house['slug']))
        return self.estate.get(house['slug'])

    def publish_house_owned_texture(self, row, asset_id='99001234'):
        variant = row['textures']['house'].get('atlasVariantId')
        if variant:
            with self.loc.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           (asset_id, variant))
            return
        with self.estate.connect() as db:
            textures = json.loads(db.execute('SELECT textures_json FROM real_estate WHERE slug=?',
                                             (row['slug'],)).fetchone()[0])
            texture = textures['house']
            texture['assetId'] = asset_id
            texture['publishedSha256'] = texture['sha256']
            texture['publicationFormat'] = published_format(Path(texture['path']))
            db.execute('UPDATE real_estate SET textures_json=? WHERE slug=?',
                       (json.dumps(textures), row['slug']))

    def test_location_owner_removed_but_legacy_followers_keep_published_image(self):
        owner = self.register_location('owner_wall')
        self.publish_location_atlas(owner)
        self.register_location('second_wall', 'owner_wall')
        before = self.loc.get('second_wall')
        self.assertEqual(before['texture_asset_id'], '123456789')
        plan = self.service.plan('location','owner_wall')
        self.assertEqual(plan['dependentCount'], 1)
        result = self.service.execute('location','owner_wall',token=plan['token'])
        self.assertEqual(result['mode'], 'preserve')
        self.assertIsNone(self.loc.get('owner_wall'))
        fresh = LocationAssetStore(self.root)
        follower = fresh.get('second_wall')
        self.assertEqual(follower['texture_asset_id'], '123456789')
        self.assertEqual(follower['texture_owner_slug'], 'owner_wall')
        self.assertTrue((self.root / follower['texture_path']).is_file())
        self.assertEqual(fresh.atlases.binding('location_asset','owner_wall')['published_id'],'123456789')

    def test_house_owner_removed_but_dependent_door_keeps_same_image_id(self):
        owner = self.register_house('01')
        self.publish_house_owned_texture(owner)
        follower = self.register_house('02',f'estate:{owner["slug"]}:house', consumer_part='door')
        before = self.estate.get(follower['slug'])['textures']['door']
        self.assertEqual(before['assetId'],'99001234')
        impact = self.service.plan('estate', owner['slug'])
        self.assertEqual(impact['dependentCount'], 1)
        self.assertEqual(impact['relations'][0]['part'],'door')
        self.assertEqual(impact['relations'][0]['ownerPart'],'house')
        self.service.execute('estate',owner['slug'],token=impact['token'])
        self.assertIsNone(self.estate.get(owner['slug']))
        fresh = RealEstateStore(self.root, location_assets=LocationAssetStore(self.root))
        after = fresh.get(follower['slug'])['textures']['door']
        self.assertEqual(after['assetId'],'99001234')
        self.assertEqual(after['reuseReference'],f'estate:{owner["slug"]}:house')
        self.assertTrue((self.root / after['path']).is_file())

    def test_non_atlas_legacy_house_texture_preserved_after_retirement(self):
        owner = self.register_house('01', legacy=True)
        self.publish_house_owned_texture(owner, '88112233')
        follower = self.register_house('02', f'estate:{owner["slug"]}:house', consumer_part='door')
        self.assertEqual(self.estate.get(follower['slug'])['textures']['door']['assetId'], '88112233')
        self.service.execute('estate', owner['slug'])
        fresh = RealEstateStore(self.root, location_assets=LocationAssetStore(self.root))
        texture = fresh.get(follower['slug'])['textures']['door']
        self.assertEqual(texture['assetId'], '88112233')
        self.assertTrue((self.root / texture['path']).is_file())
        self.assertEqual(texture['filename'], 'legacy_house_texture.png')

    def test_retired_owner_slug_is_reserved_to_avoid_rebinding_old_consumers(self):
        owner = self.register_location('old_owner')
        self.publish_location_atlas(owner)
        self.register_location('follower', 'old_owner')
        self.service.execute('location', 'old_owner')
        with self.assertRaisesRegex(ValueError, 'reserved'):
            self.register_location('old_owner')
        self.assertEqual(self.loc.get('follower')['texture_asset_id'], '123456789')

    def test_location_owner_referenced_by_house_survives_retirement(self):
        loc = self.register_location('old_lamp')
        self.publish_location_atlas(loc,'66778899')
        house = self.register_house('01', 'location:old_lamp')
        self.assertEqual(self.estate.get(house['slug'])['textures']['house']['assetId'],'66778899')
        impact=self.service.plan('location','old_lamp')
        self.assertEqual(impact['dependentCount'],1)
        self.service.execute('location','old_lamp')
        estate = RealEstateStore(self.root, location_assets=LocationAssetStore(self.root))
        texture = estate.get(house['slug'])['textures']['house']
        self.assertEqual(texture['assetId'],'66778899')
        self.assertEqual(texture['reuseReference'],'location:old_lamp')

    def test_delete_all_removes_transitive_dependents_only_after_confirmation(self):
        owner=self.register_location('owner_a')
        self.publish_location_atlas(owner)
        self.register_location('follower_b','owner_a')
        house=self.register_house('01','location:follower_b')
        impact=self.service.plan('location','owner_a')
        self.assertEqual(impact['dependentCount'],2)
        self.assertEqual([n['slug'] for n in impact['nodes']],
                         [house['slug'],'follower_b','owner_a'])
        with self.assertRaisesRegex(ValueError,'dependencies changed'):
            self.service.execute('location','owner_a',mode='all')
        with self.assertRaisesRegex(ValueError,'dependencies changed'):
            self.service.execute('location','owner_a',mode='all',token='stale')
        self.assertIsNotNone(self.loc.get('owner_a'))
        result=self.service.execute('location','owner_a',mode='all',token=impact['token'])
        self.assertEqual(len(result['deleted']),3)
        self.assertIsNone(self.loc.get('owner_a'))
        self.assertIsNone(self.loc.get('follower_b'))
        self.assertIsNone(self.estate.get(house['slug']))
        self.assertTrue(self.image.is_file())

    def test_api_preview_and_explicit_retire_without_deleting_source(self):
        self.register_location('old_rock')
        deps={'real_estate':self.estate,'location_assets':self.loc}
        status,impact=read_world(urlparse('/api/asset-retirement/impact?kind=location&slug=old_rock'),
                                 deps,lambda:{})
        self.assertEqual(status,200)
        status,out=dispatch_post('/api/asset-retirement/execute',lambda:{'kind':'location','slug':'old_rock',
            'mode':'preserve','token':impact['token']},deps)
        self.assertEqual(status,200)
        self.assertTrue(out['sourceFilesPreserved'])
        self.assertTrue((self.root / out['deleted'][0]['archive']).is_file())
        self.assertTrue(self.image.is_file())
