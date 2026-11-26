"""Studio owns authoring; Database stores level-specific spawn records."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance as balance
from monster_spawn_store import MonsterSpawnStore, REQUIRED_ANIMATION_SLOTS

class Models:
    def __init__(self):
        self.rows = {'gremlin': {'slug': 'gremlin', 'name_en': 'Gremlin', 'status': 'PUBLISHED', 'model_asset_id': '123'}}
    def get(self, slug): return self.rows.get(slug)
    def list(self): return list(self.rows.values())

class Clips:
    def list_for_monster(self, slug):
        return [{'slot': slot, 'status': 'PUBLISHED'} for slot in REQUIRED_ANIMATION_SLOTS]

class StudioSpawnTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = balance.load(ROOT)
        self.data['monsterBindings'] = {'gremlin': 'monster_001'}
        self.source = self.root / 'config/balance/gameplay.json'
        self.source.parent.mkdir(parents=True)
        self.source.write_text(json.dumps(self.data), encoding='utf8')
        output = self.root / "src/shared/balance/BalanceRegistry.luau"
        output.parent.mkdir(parents=True)
        output.write_text(balance.render(self.data), encoding="utf8")
        self.models = Models()
        def bridge(*args, **kwargs): self.fail('Studio authoring must not call reverse bridge')
        self.store = MonsterSpawnStore(self.root, self.models, Clips(), bridge)
        self.toad = next(r for r in self.data['monsters'] if r['nameEn'] == 'Toad')
        self.payload = {'action': 'apply', 'spawnId': 'spawn-123456789abc', 'balanceId': self.toad['id'],
                        'placeId': 42, 'position': {'x': 10, 'y': 1, 'z': -20}}
    def test_catalog_all_database_rows_and_no_proxy(self):
        catalog = self.store.studio_catalog()
        rows = [r for group in catalog['species'] for r in group['levels']]
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in self.data['monsters']})
        self.assertEqual(len(rows), 70)
        self.assertFalse(next(r for r in rows if r['id'] == self.toad['id'])['ready'])
        self.assertTrue(next(r for r in rows if r['nameEn'] == 'Gremlin')['ready'])
    def test_apply_edit_delete_and_pending_resolution(self):
        before = self.source.read_bytes()
        saved = self.store.studio_apply(self.payload)['record']
        self.assertEqual(saved['level'], self.toad['level'])
        self.assertEqual(saved['aggroRadiusStuds'], self.toad['aggroRadiusStuds'])
        self.assertEqual((saved['spawnRadius'], saved['maxAlive'], saved['respawnSeconds']), (15, 3, 10))
        self.assertFalse(saved['readiness']['ready'])
        with self.assertRaises(ValueError): self.store.studio_apply({**self.payload, 'spawnId': self.payload['spawnId'].upper()})
        update = {**self.payload, 'expectedUpdatedAtUtc': saved['updatedAtUtc'], 'aggressive': False,
                  'aggroRadiusStuds': 0, 'deathChase': True, 'maxAlive': 4}
        with self.assertRaises(ValueError): self.store.studio_apply({**update, 'placeId': 43})
        saved = self.store.studio_apply(update)['record']
        self.assertFalse(saved['aggressive']); self.assertEqual(saved['aggroRadiusStuds'], 0)
        self.assertTrue(saved['deathChase']); self.assertEqual(saved['maxAlive'], 4)
        registry = self.store.registry_path.read_text()
        self.assertIn('"balanceId":"' + self.toad['id'] + '"', registry)
        self.assertIn('"deathChase":true', registry)
        self.models.rows['toad'] = {'slug': 'toad', 'name_en': 'Toad', 'status': 'PUBLISHED', 'model_asset_id': '456'}
        self.assertTrue(self.store.studio_catalog()['records'][0]['readiness']['ready'])
        with self.assertRaises(ValueError): self.store.studio_apply(update)
        self.store.studio_apply({**update, 'action': 'delete', 'expectedUpdatedAtUtc': saved['updatedAtUtc']})
        self.assertEqual(self.store.studio_catalog()['records'], [])
        self.assertEqual(self.source.read_bytes(), before)
    def test_invalid_records_are_not_saved(self):
        for patch in ({'balanceId': 'missing'}, {'maxAlive': 0}, {'aggressive': 'false'},
                      {'deathChase': 1}, {'enabled': 'true'}, {'spawnRadius': -1}, {'respawnSeconds': -1}):
            with self.assertRaises(ValueError): self.store.studio_apply({**self.payload, **patch})
        self.assertEqual(self.store.studio_catalog()['records'], [])

if __name__ == '__main__': unittest.main()
