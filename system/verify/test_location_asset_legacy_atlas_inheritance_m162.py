"""M162: legacy followers resolve their owner's Atlas Registry publication.

A legacy reference is a live relationship, not a snapshot of the owner's stale
location_assets.texture_asset_id columns. No Roblox uploads or DB migration.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import json
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from api.write_world import route


class SharedAtlasLegacyFollowerM162(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / 'source'
        source.mkdir()
        self.fbx = source / 'model.fbx'
        self.fbx.write_bytes(b'example model')
        self.atlas_file = source / 'structures_01_32x32_atlas.png'
        Image.new('RGB', (32, 32), (80, 90, 100)).save(self.atlas_file)
        self.loc = LocationAssetStore(self.root)
        self.owner_slug = 'stone_fence_01'
        self.followers = ('stone_fence_pillar_01', 'wooden_fence_01',
                          'wooden_fence_pillar_01', 'stone_ladder_01')
        self.owner = self.loc.register({'slug': self.owner_slug,
            'nameEn': 'Stone Fence 01', 'category': 'fence',
            'modelSourcePath': str(self.fbx), 'textureSourcePath': str(self.atlas_file)})
        self.variant = self.owner['atlasVariantId']
        for slug in self.followers:
            self.loc.register({'slug': slug, 'nameEn': slug, 'category': 'fence',
                'modelSourcePath': str(self.fbx), 'textureReferenceSlug': self.owner_slug})
        with self.loc.connect() as db:
            db.execute('''UPDATE location_assets SET model_asset_id=?,
                model_published_sha256=model_sha256''', ('1234567890',))
            db.execute('''UPDATE texture_atlas_variants SET published_id=?,
                published_sha256=source_sha256 WHERE id=?''', ('119920676388867',self.variant))
        # Owner's raw texture publication fields are intentionally empty.
        self.assertIsNone(self.loc._raw_get(self.owner_slug)['texture_asset_id'])
        self.assertEqual(self.loc._raw_get(self.followers[0])['texture_reference_slug'], self.owner_slug)

    def test_all_legacy_followers_are_published_without_new_image_or_binding(self):
        rows = {r['slug']: r for r in self.loc.list()}
        for slug in (self.owner_slug, *self.followers):
            with self.subTest(slug=slug):
                row = rows[slug]
                self.assertEqual(row['status'], 'PUBLISHED')
                self.assertEqual(row['atlasVariantId'], self.variant)
                self.assertEqual(row['texture_asset_id'], '119920676388867')
                self.assertEqual(row['texture_filename'], 'structures_01_32x32_atlas.png')
                self.assertEqual(row['studioSyncStatus'], 'pending_studio_sync')
                self.assertEqual(row['atlasBindingSourceSlug'], self.owner_slug)
                self.assertEqual(row['texture_shared'], slug != self.owner_slug)
                if slug != self.owner_slug:
                    self.assertEqual(row['texture_owner_slug'], self.owner_slug)
                    self.assertEqual(row['texture_reference_slug'], self.owner_slug)
                    self.assertIsNone(self.loc.atlases.binding('location_asset', slug))
        with mock.patch('location_asset_store.create_image_asset') as upload:
            for slug in self.followers:
                self.loc.publish(slug,{})
            upload.assert_not_called()
        self.loc.export()
        manifest = json.loads((self.root / 'assets/manifests/location-assets.json').read_text())
        self.assertEqual(manifest['summary']['changed'],0)
        self.assertEqual(manifest['summary']['published'],5)
        registry = (self.root / 'src/shared/world/LocationAssetRegistry.luau').read_text()
        self.assertEqual(registry.count('textureAssetId = "119920676388867"'),5)

    def test_followers_inherit_owner_binding_changes_and_sync_state(self):
        second_file = self.atlas_file.with_name('structures_01_64x64_atlas.png')
        Image.new('RGB', (64,64), (100,100,100)).save(second_file)
        second = self.loc.atlases.register_file(str(second_file))
        with self.loc.connect() as db:
            db.execute('''UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256
                WHERE id=?''',('998877665544',second['id']))
        self.loc.select_atlas(self.owner_slug,second['id'],expected_revision=1)
        for slug in self.followers:
            row = self.loc.get(slug)
            self.assertEqual(row['texture_asset_id'],'998877665544')
            self.assertEqual(row['atlasVariantId'],second['id'])
            self.assertEqual(row['bindingRevision'],2)
            self.assertEqual(row['status'],'PUBLISHED')
        self.loc.atlases.mark_synced('location_asset',self.owner_slug,2)
        self.assertTrue(all(self.loc.get(slug)['studioSyncStatus']=='synced' for slug in self.followers))

    def test_targeted_sync_on_follower_refreshes_all_before_ack(self):
        revisions = self.loc.atlases.active_revisions('location_asset')
        bridge = mock.Mock(return_value={'models':5,'parts':5,'registryItems':5})
        deps = dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines',
            'publication_credentials'))
        deps.update(location_assets=self.loc,sync_location_assets_to_studio=bridge)
        status,payload = route('/api/location-assets/studio-sync',
                               lambda:{'slug':self.followers[0]},deps)
        self.assertEqual(status,200,payload)
        bridge.assert_called_once_with()
        self.assertEqual(payload['studio']['models'],5)
        self.assertEqual(revisions,{self.owner_slug:1})
        self.assertEqual(self.loc.get(self.owner_slug)['studioSyncStatus'],'synced')
        self.assertEqual(self.loc.get(self.followers[1])['studioSyncStatus'],'synced')
        self.assertIsNone(self.loc.atlases.binding('location_asset',self.followers[0]))

    def test_sync_failure_does_not_acknowledge_or_publish(self):
        deps = dict.fromkeys(('deco_layouts','locations','monster_spawns','npc_place_spawn',
            'npc_register_spawn','npc_spawns','options_store','request_active_studio_save',
            'run_timeline_editor_bridge','sync_monster_to_studio','timelines',
            'publication_credentials'))
        deps.update(location_assets=self.loc, sync_location_assets_to_studio=mock.Mock(
            side_effect=RuntimeError('Studio unavailable')))
        status,payload = route('/api/location-assets/studio-sync',
                               lambda:{'slug':self.followers[0]},deps)
        self.assertEqual(status,400,payload)
        self.assertEqual(self.loc.get(self.followers[0])['studioSyncStatus'],'pending_studio_sync')
        self.assertIn('Studio unavailable', payload['error'])

    def test_explicit_binding_on_follower_overrides_legacy_owner(self):
        second_file = self.atlas_file.with_name('new_32x32_atlas.png')
        Image.new('RGB',(32,32),(20,30,40)).save(second_file)
        second = self.loc.atlases.register_file(str(second_file))
        with self.loc.connect() as db:
            db.execute('''UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256
                WHERE id=?''', ('777777777',second['id']))
        self.loc.select_atlas(self.followers[0],second['id'],expected_revision=0)
        self.assertEqual(self.loc.get(self.followers[0])['texture_asset_id'],'777777777')
        self.assertFalse(self.loc.get(self.followers[0])['texture_shared'])
        self.assertEqual(self.loc.get(self.followers[1])['texture_asset_id'],'119920676388867')

    def test_ui_preserves_legacy_owner_selection_for_save(self):
        js = (ROOT/'system/control-center/static/deco-assets.js').read_text(encoding='utf-8')
        self.assertIn("row?.texture_shared ? (row.texture_reference_slug || '') : ''",js)
        self.assertIn('if (row.atlasVariantId && row.slug !== decoAssetState.textureReferenceSlug) continue;',js)
