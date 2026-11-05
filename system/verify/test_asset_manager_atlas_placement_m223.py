"""M223: Atlas retirement is transactional; plot preview requests use saved bindings."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from types import SimpleNamespace
import sqlite3
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.texture_atlas_registry import AtlasRegistry
from services.sqlite_asset_audit_importer import SqliteAssetAuditImporter
from api import real_estate as estate_api


class AtlasRetirementM223(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / '.control-center').mkdir()
        (self.root / 'images').mkdir()
        self.store = AtlasRegistry(self.root)

    def create(self, name, size, image_id):
        path = self.root / 'images' / f'{name}_{size}x{size}_atlas.png'
        Image.new('RGB', (size, size), (size, 20, 30)).save(path)
        row = self.store.register_file(str(path))
        with self.store.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       (str(image_id), row['id']))
        return self.store.get_variant(row['id'])

    def test_auto_closest_same_family_rebinds_all_consumers_and_keeps_history(self):
        old = self.create('pine_01', 16, 1101)
        replacement = self.create('pine_01', 32, 2202)
        unrelated = self.create('rock_01', 16, 3303)
        self.store.bind('location_asset', 'pine_01', old['id'])
        self.store.bind('real_estate', 'house_level1_01:house', old['id'])
        self.store.bind('character_part', 'head_01:head', old['id'])
        plan = self.store.retirement_plan(old['id'])
        self.assertEqual(plan['suggestedReplacementId'], replacement['id'])
        self.assertEqual(len(plan['consumers']), 3)
        result = self.store.retire_variant(old['id'], token=plan['token'], auto_closest=True)
        self.assertEqual(result['consumersRebound'], 3)
        self.assertTrue(result['studioSyncRequired'])
        self.assertEqual(result['replacementVariantId'], replacement['id'])
        self.assertEqual(self.store.get_variant(old['id'])['published_id'], '1101')
        self.assertTrue(self.store.get_variant(old['id'])['retired'])
        for consumer_type, consumer in [('location_asset', 'pine_01'),
                                        ('real_estate', 'house_level1_01:house'),
                                        ('character_part', 'head_01:head')]:
            binding = self.store.binding(consumer_type, consumer)
            self.assertEqual(binding['variant_id'], replacement['id'])
            self.assertEqual(binding['revision'], 2)
            self.assertEqual(binding['syncStatus'], 'pending_studio_sync')
        catalog_ids = {v['id'] for f in self.store.catalog() for v in f['variants']}
        self.assertEqual(catalog_ids, {replacement['id'], unrelated['id']})
        with self.store.connect() as db:
            old_retirement = db.execute('SELECT * FROM texture_atlas_retirements').fetchone()
        self.assertEqual(old_retirement['variant_id'], old['id'])
        # M217/MySQL audit imports immutable original and replacement Image IDs;
        # the SQLite authoring database is not modified by the importer.
        history = SqliteAssetAuditImporter(self.root, mock.MagicMock())._atlas_binding_migration_events()
        self.assertEqual(len(history), 3)
        self.assertTrue(all(event['previousAssetId'] == '1101' and
                            event['assetId'] == '2202' for event in history))
        self.assertEqual({event['assetKey'] for event in history},
                         {'pine_01', 'house_level1_01', 'head_01'})
        self.assertEqual({event['assetSlot'] for event in history}, {'', 'house', 'head'})
        self.assertTrue((self.root / old['source_path']).exists())
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.store.bind('location_asset', 'another', old['id'])
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.store.register_file(str(self.root / 'images/pine_01_16x16_atlas.png'))

    def test_requires_replacement_for_used_atlas_and_prevents_stale_confirmation(self):
        old = self.create('a', 16, 100)
        next_one = self.create('b', 16, 200)
        self.store.bind('location_asset', 'first', old['id'])
        preview = self.store.retirement_plan(old['id'])
        self.assertIsNone(preview['suggestedReplacementId'])
        with self.assertRaisesRegex(ValueError, 'replacement first'):
            self.store.retire_variant(old['id'], token=preview['token'])
        with self.assertRaisesRegex(ValueError, 'same family'):
            self.store.retire_variant(old['id'], token=preview['token'], auto_closest=True)
        self.store.bind('location_asset', 'second', old['id'])
        with self.assertRaisesRegex(ValueError, 'refresh'):
            self.store.retire_variant(old['id'], token=preview['token'], replacement_variant_id=next_one['id'])
        self.assertFalse(self.store.get_variant(old['id'])['retired'])
        fresh = self.store.retirement_plan(old['id'])
        result = self.store.retire_variant(old['id'], token=fresh['token'], replacement_variant_id=next_one['id'])
        self.assertEqual(result['consumersRebound'], 2)

    def test_unbound_atlas_can_be_retired_without_replacement(self):
        old = self.create('unused', 16, 100)
        plan = self.store.retirement_plan(old['id'])
        result = self.store.retire_variant(old['id'], token=plan['token'])
        self.assertEqual(result['consumersRebound'], 0)
        self.assertFalse(result['studioSyncRequired'])
        with self.assertRaisesRegex(ValueError, 'unknown active'):
            self.store.retirement_plan(old['id'])

    def test_pre_existing_registry_schema_migrates_without_losing_publications(self):
        existing = self.create('legacy', 16, 456)
        # Reopening installs the additive schema, leaving existing registration untouched.
        again = AtlasRegistry(self.root)
        self.assertEqual(again.get_variant(existing['id'])['published_id'], '456')
        with again.connect() as db:
            columns = {row[1] for row in db.execute('PRAGMA table_info(texture_atlas_variants)')}
        self.assertIn('retired_at', columns)


class PlacementPreviewM223(TestCase):
    def test_preview_route_does_not_accept_browser_transforms(self):
        binding = {'plotIndex': 39, 'houseSlug': 'house_level3_01', 'scale': 1.25,
                   'localCFrame': [5, 0, 3, 1, 0, 0, 0, 1, 0, 0, 0, 1], 'revision': 2}
        house = SimpleNamespace(get=lambda slug: {'slug': slug} if slug == 'house_level3_01' else None)
        placements = SimpleNamespace(get=mock.Mock(return_value=binding))
        calls = []
        def preview(slug, plot, action, saved):
            calls.append((slug, plot, action, saved))
            return {'status': 'placed'}
        deps = {'real_estate': house, 'real_estate_placements': placements,
                'preview_house_placement': preview}
        status, result = estate_api.write('/api/real-estate/placements/preview', lambda: {
            'houseSlug': 'house_level3_01', 'plotIndex': 39, 'action': 'place',
            'localCFrame': [999] * 12}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(result['studio']['status'], 'placed')
        self.assertEqual(calls, [('house_level3_01', 39, 'place', binding)])
        calls.clear()
        status, result = estate_api.write('/api/real-estate/placements/preview', lambda: {
            'houseSlug': 'house_level3_01', 'plotIndex': 39, 'action': 'clear'}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(calls[0][2], 'clear')

    def test_studio_place_preview_never_destroys_unmanaged_objects(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioHousePlacementPreview.luau').read_text()
        self.assertIn('Game1PlotHousePreview', source)
        self.assertIn('GetAttribute("Game1PlotHousePreview") ~= true', source)
        self.assertIn('plotFolder', source)
        self.assertIn('ChangeHistoryService:TryBeginRecording', source)
        self.assertIn('local desiredRoot = volume.CFrame * CFrame.new(table.unpack(components))', source)
        self.assertIn('HouseFrame.Align(clone, house, desiredHouse', source)
        self.assertIn('houseAnchorLocalCFrame', source)
        self.assertLess(source.index('HouseFrame.Align(clone, house, desiredHouse'),
                        source.index('for _, previous in ipairs(plan.previous) do'))
        self.assertIn('Studio Edit Mode', source)

    def test_sidebar_and_atlas_are_separate_sections(self):
        static = ROOT / 'system/control-center/static'
        html = (static / 'index.html').read_text()
        self.assertIn('id="nav-atlas"', html)
        self.assertIn('id="atlas-view"', html)
        self.assertIn('id="re-placement-prev"', html)
        self.assertIn('id="re-placement-next"', html)
        self.assertIn('id="atlas-library-dialog"', html)
        self.assertIn('game1.assetManager.sectionOrder.v1', (static/'asset-section-order.js').read_text())
        self.assertIn('data-placement-action', (static/'real-estate-placement.js').read_text())
