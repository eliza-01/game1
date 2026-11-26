"""M544 release seed: one territory per named species and shared reach values."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance as balance, skill_balance
from kanban_store import KanbanStore


class ZoneIdentityM544(unittest.TestCase):
    def test_names_are_exclusive_to_a_release_zone(self):
        data = balance.load()
        zones = ((1, 4), (5, 9), (10, 14), (15, 19), (20, 24), (25, 30))
        known = {}
        for i, (lo, hi) in enumerate(zones):
            for row in data['monsters']:
                if not lo <= row['level'] <= hi or not row['name']:
                    continue
                key = re.search(r'\(([^()]*)\)\s*$', row['name'])[1].casefold()
                self.assertEqual(known.setdefault(key, i), i, row['name'])
        rows = {(r['level'], r['type']): r for r in data['monsters']}
        for level in range(1, 5):
            self.assertEqual(rows[level, 'ranged']['name'], 'Мандрагора (Mandragora)')
        for level in range(15, 20):
            self.assertEqual(rows[level, 'ranged']['name'], 'Споровик (Spore Spitter)')
        spec = KanbanStore(ROOT).detail('KBN-0031')['spec']
        gardens = spec.split('## Забытые сады · LVL 15–19', 1)[1].split('\n## ', 1)[0]
        self.assertNotIn('мандрагор', gardens.casefold())
        self.assertIn('Споровик (Spore Spitter) | 15–19 | Ranged', gardens)

    def test_reach_seed_and_skilled_projection(self):
        data = balance.load()
        expected = {'sword': 9, 'dagger': 9, 'bigsword': 10, 'dualswords': 8, 'bow': 40}
        for row in data['weapons']:
            self.assertEqual(row['radius'], expected[row['type']], row['id'])
        for row in data['monsters'] + skill_balance.resolve(data):
            self.assertEqual(row['attackRange'], 10 if row['type'] == 'melee' else 40, row['id'])
        self.assertEqual(balance.OUTPUT.read_text(encoding='utf-8'), balance.render(data))


if __name__ == '__main__':
    unittest.main()
