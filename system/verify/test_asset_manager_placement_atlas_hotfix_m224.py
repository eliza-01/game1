"""M224: persistent anchoring, scoped Studio calls and grouped Atlas library."""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from api import real_estate as estate_api
from real_estate.placement import RealEstatePlacementStore
from services.texture_atlas_registry import AtlasRegistry
from PIL import Image


def cf(x=0):
    return [x, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]


class PlacementAnchorM224(TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        db = root / '.control-center/game1_real_estate.db'
        db.parent.mkdir()
        with sqlite3.connect(db) as conn:
            conn.execute('CREATE TABLE real_estate (slug TEXT PRIMARY KEY)')
            conn.executemany('INSERT INTO real_estate(slug) VALUES(?)', [('house_a',), ('house_b',)])
        self.root = root
        self.db = db
        self.houses = SimpleNamespace(get=lambda slug: {'slug': slug} if slug in ('house_a', 'house_b') else None)
        self.store = RealEstatePlacementStore(root, self.houses)
        self.capture = lambda slug, plot: {
            'schemaVersion': 2, 'houseSlug': slug, 'plotIndex': plot,
            'plotVolume': f'plot_{plot:02d}_volume', 'worldCFrame': cf(5),
            'plotCFrame': cf(), 'localCFrame': cf(5), 'scale': 1.0,
            'houseAnchorLocalCFrame': cf(), 'houseAnchorWorldCFrame': cf(5),
        }
        self.store.bind('house_a', 1, self.capture('house_a', 1))
        self.store.bind('house_a', 2, self.capture('house_a', 2))
        self.store.bind('house_b', 1, self.capture('house_b', 1))

    def test_single_and_all_anchor_stick_on_rebind_and_reopen(self):
        targets = [{'houseSlug': 'house_a', 'plotIndex': 1}]
        self.assertEqual(self.store.set_anchored(targets, False), 1)
        self.assertFalse(self.store.get('house_a', 1)['anchored'])
        self.assertTrue(self.store.get('house_b', 1)['anchored'])
        rebound = self.store.bind('house_a', 1, self.capture('house_a', 1))
        self.assertFalse(rebound['anchored'])
        all_targets = [{'houseSlug': x['houseSlug'], 'plotIndex': x['plotIndex']}
                       for x in self.store.snapshot()['items']]
        self.assertEqual(self.store.set_anchored(all_targets, False), 2)
        self.assertEqual(self.store.set_anchored(all_targets, False), 0)
        reopened = RealEstatePlacementStore(self.root, self.houses)
        self.assertTrue(all(not x['anchored'] for x in reopened.snapshot()['items']))
        manifest = json.loads((self.root/'assets/manifests/real-estate-placements.json').read_text())
        self.assertTrue(all(not x['anchored'] for x in manifest['items']))
        self.assertEqual(self.store.set_anchored(all_targets, True), 3)

    def test_migrate_existing_database_without_cframe_loss(self):
        saved = self.store.get('house_a', 1)
        with sqlite3.connect(self.db) as conn:
            conn.execute('ALTER TABLE real_estate_placements RENAME TO old_placements')
            conn.execute('''CREATE TABLE real_estate_placements AS SELECT
                plot_index, house_slug, plot_volume, world_cframe_json, plot_cframe_json,
                local_cframe_json, model_scale, revision, updated_at FROM old_placements''')
            conn.execute('DROP TABLE old_placements')
        # This emulates the old columns, not migration of existing SQLite triggers.
        migrated = RealEstatePlacementStore(self.root, self.houses)
        self.assertTrue(migrated.get('house_a', 1)['anchored'])
        self.assertEqual(migrated.get('house_a', 1)['localCFrame'], saved['localCFrame'])
        self.assertEqual(len(list((self.db.parent/'backups').glob('before_placement_anchor_m224_*.db'))), 1)

    def test_studio_before_database_and_only_saved_targets(self):
        calls = []
        def studio(targets, anchored):
            calls.append((targets, anchored))
            return {'status': 'anchored', 'changed': 1}
        deps = {'real_estate': self.houses, 'real_estate_placements': self.store,
                'anchor_house_placements': studio}
        status, result = estate_api.write('/api/real-estate/placements/anchors', lambda: {
            'scope': 'one', 'houseSlug': 'house_a', 'plotIndex': 1, 'anchored': False,
            'targets': [{'houseSlug': 'house_b', 'plotIndex': 1}]}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(calls, [([{'houseSlug': 'house_a', 'plotIndex': 1}], False)])
        self.assertFalse(self.store.get('house_a', 1)['anchored'])
        self.assertTrue(self.store.get('house_b', 1)['anchored'])
        deps['anchor_house_placements'] = mock.Mock(side_effect=RuntimeError('Studio unavailable'))
        status, response = estate_api.write('/api/real-estate/placements/anchors', lambda: {
            'scope': 'all', 'anchored': False}, deps)
        self.assertNotEqual(status, 200)
        self.assertTrue(self.store.get('house_b', 1)['anchored'])
        deps['anchor_house_placements'] = studio
        status, result = estate_api.write('/api/real-estate/placements/anchors', lambda: {
            'scope': 'all', 'anchored': False}, deps)
        self.assertEqual(status, 200)
        self.assertEqual(len(calls[-1][0]), 3)
        self.assertTrue(all(not x['anchored'] for x in self.store.snapshot()['items']))
        for invalid in (0, 51, True, '01'):
            status, _ = estate_api.write('/api/real-estate/placements/anchors', lambda: {
                'scope': 'one', 'houseSlug': 'house_a', 'plotIndex': invalid, 'anchored': False}, deps)
            self.assertEqual(status, 400)

    def test_plugin_source_is_scoped_and_place_not_blocked_by_previous_preview(self):
        source = (ROOT/'system/studio-plugin/modules/StudioHousePlacementPreview.luau').read_text()
        self.assertIn('Game1PlotHouseAnchored', source)
        self.assertIn('for _, part in ipairs(model:GetDescendants())', source)
        self.assertIn('setAndVerifyAnchored(clone, binding.anchored)', source)
        self.assertIn('part.Anchored = anchored', source)
        self.assertIn('previousPreviews', source)
        self.assertNotIn('Clear it first', source)
        self.assertIn('previous:Destroy()', source)
        self.assertIn('ChangeHistoryService:TryBeginRecording', source)
        ui = (ROOT/'system/control-center/static/real-estate-placement.js').read_text()
        self.assertNotIn('!confirm(', ui)
        self.assertIn("game1PlacementSetAnchored('all'", ui)


class AtlasGroupingM224(TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        (root / 'images').mkdir()
        (root / '.control-center').mkdir()
        self.store = AtlasRegistry(root)
        self.root = root

    def add(self, name, size, image_id):
        path = self.root / 'images' / f'{name}_{size}x{size}_atlas.png'
        Image.new('RGB', (size, size)).save(path)
        item = self.store.register_file(str(path))
        with self.store.connect() as conn:
            conn.execute('UPDATE texture_atlas_variants SET published_id=?, published_sha256=source_sha256 WHERE id=?',
                         (str(image_id), item['id']))
        return item['id']

    def test_one_variant_many_consumers_and_family_first_replacement(self):
        old = self.add('pine', 16, 123)
        new = self.add('pine', 32, 456)
        unrelated = self.add('rock', 16, 777)
        self.store.bind('location_asset', 'pine_tree_a', old)
        self.store.bind('real_estate', 'house_1:roof', old)
        grouped = self.store.catalog_with_consumers()
        entries = {v['id']: v for family in grouped for v in family['variants']}
        self.assertEqual(len(entries), 3)
        self.assertEqual({c['consumer_id'] for c in entries[old]['consumers']},
                         {'pine_tree_a', 'house_1:roof'})
        self.assertEqual(entries[new]['consumers'], [])
        plan = self.store.retirement_plan(old)
        self.assertEqual(plan['candidates'][0]['id'], new)
        self.assertEqual(plan['suggestedReplacementId'], new)
        self.assertTrue(any(x['id'] == unrelated for x in plan['candidates']))

    def test_explicit_delete_is_archive_and_stub_disabled(self):
        html = (ROOT/'system/control-center/static/index.html').read_text()
        js = (ROOT/'system/control-center/static/atlas-library.js').read_text()
        self.assertIn('>Delete atlas</button>', html)
        self.assertIn('id="atlas-library-sync-closest" type="button" disabled', html)
        self.assertIn('node(\'atlas-library-replacement\').value = plan.suggestedReplacementId', js)
        self.assertIn('names(v).map(esc)', js)

class PlacementAnchorBridgeM224(TestCase):
    def test_authenticated_bridge_echoes_anchor_identity(self):
        import threading
        import time
        from urllib.request import Request, urlopen
        from studio_bridge import PORT, TOKEN
        from services.studio_house_placement_bridge import anchor_house_placements
        observed = []
        errors = []
        def simulated_studio():
            try:
                base = f'http://127.0.0.1:{PORT}'
                for _ in range(120):
                    try:
                        with urlopen(Request(base+'/command', headers={'X-Game1-Token': TOKEN}), timeout=1) as resp:
                            cmd = json.load(resp)
                        break
                    except OSError:
                        time.sleep(.025)
                else:
                    raise AssertionError('Bridge never served command')
                observed.append(cmd)
                self.assertEqual(cmd['command'], 'house-placement-preview-v3')
                self.assertEqual(cmd['schemaVersion'], 3)
                self.assertEqual(cmd['action'], 'anchors')
                self.assertEqual(cmd['targets'], [{'houseSlug': 'house_a', 'plotIndex': 1}])
                self.assertIs(cmd['anchored'], False)
                with urlopen(Request(base+'/house-placement-result',
                         data=json.dumps({**cmd, 'status': 'anchored', 'changed': 1}).encode(),
                         headers={'X-Game1-Token': TOKEN, 'Content-Type':'application/json'},
                         method='POST'), timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=simulated_studio, daemon=True)
        worker.start()
        result = anchor_house_placements([{'houseSlug': 'house_a', 'plotIndex': 1}], False,
                                         timeout_seconds=6)
        worker.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(result['changed'], 1)
        self.assertEqual(len(observed), 1)
