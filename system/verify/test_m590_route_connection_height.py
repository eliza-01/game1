"""Options -> generated registry -> graph connection height contract."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_monster_ai

KEY = 'routeConnectionHeight'


class RouteConnectionHeightM590(unittest.TestCase):
    def test_migration_save_and_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = OptionsStore(root)
            original = store.update({'monsterAi': {'noDamageReturnSeconds': 88,
                'experimentalNavigation': {'searchDistance': 80, 'stuckReturnSeconds': 20}}})
            nav = original['monsterAi']['experimentalNavigation']
            nav.pop(KEY, None)
            store.manifest_path.write_text(json.dumps(original), encoding='utf-8')
            store = OptionsStore(root)
            migrated = store.snapshot()['monsterAi']
            self.assertEqual(migrated['noDamageReturnSeconds'], 88)
            self.assertEqual(migrated['experimentalNavigation'], {**nav, KEY: 2})
            self.assertIn('routeConnectionHeight = 2,', store.registry_path.read_text())
            store.update({'monsterAi': {'experimentalNavigation': {KEY: 4.5}}})
            self.assertEqual(OptionsStore(root).snapshot()['monsterAi']['experimentalNavigation'], {**nav, KEY: 4.5})
            self.assertIn('routeConnectionHeight = 4.5,', store.registry_path.read_text())

    def test_validation_and_ui_contract(self):
        for val in (-.1, 100.1, True, float('nan'), float('inf'), '2'):
            with self.subTest(val=val), self.assertRaises(ValueError):
                normalize_monster_ai({'experimentalNavigation': {KEY: val}})
        for val in (0, 2, 4.5, 100):
            self.assertEqual(normalize_monster_ai({'experimentalNavigation': {KEY: val}})['experimentalNavigation'][KEY], val)
        self.assertIn('routeConnectionHeight:2', (ROOT/'system/control-center/static/options.js').read_text())
        self.assertIn('id="option-nav-routeConnectionHeight"', (ROOT/'system/control-center/static/index.html').read_text())
        self.assertIn('math.clamp(finite(source.routeConnectionHeight, 2), 0, 100)', (ROOT/'src/shared/GameOptions.luau').read_text())
