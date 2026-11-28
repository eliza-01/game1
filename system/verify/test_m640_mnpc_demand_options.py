"""Persisted shared MNPC demand option; no Place/Command Bar override."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, normalize_mnpc_demand


class MnpcDemandOptions(unittest.TestCase):
    def test_migrate_save_restart_and_disable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = OptionsStore(root)
            old = store.update({'monsterAi': {'noDamageReturnSeconds': 41}})
            del old['mnpcDemand']
            store.manifest_path.write_text(json.dumps(old), encoding='utf-8')
            store = OptionsStore(root)
            self.assertEqual(store.snapshot()['mnpcDemand'], {'enabled': False})
            self.assertEqual(store.snapshot()['monsterAi'], old['monsterAi'])
            for value in (True, False):
                saved = store.update({'mnpcDemand': {'enabled': value}})
                self.assertEqual(saved['mnpcDemand'], {'enabled': value})
                self.assertEqual(saved['monsterAi'], old['monsterAi'])
                store = OptionsStore(root)
                self.assertEqual(store.snapshot()['mnpcDemand'], {'enabled': value})
                self.assertIn('mnpcDemand = table.freeze({\n\t\tenabled = ' + str(value).lower(), store.registry_path.read_text())
                store.update({'combat': {'stateDurationSeconds': 7}})
                self.assertEqual(store.snapshot()['mnpcDemand']['enabled'], value)

    def test_invalid_values_do_not_save(self):
        for invalid in (None, True, [], {'enabled': 1}, {'enabled': 'true'}, {'enabled': None}, {'other': True}):
            with self.assertRaises(ValueError):
                normalize_mnpc_demand(invalid)
        with tempfile.TemporaryDirectory() as tmp:
            store = OptionsStore(Path(tmp))
            before = store.manifest_path.read_bytes(), store.registry_path.read_bytes()
            with self.assertRaises(ValueError):
                store.update({'mnpcDemand': {'enabled': 'true'}})
            self.assertEqual(before, (store.manifest_path.read_bytes(), store.registry_path.read_bytes()))

    def test_ui_and_runtime_contract(self):
        read = lambda p: (ROOT / p).read_text(encoding='utf-8')
        html = read('system/control-center/static/index.html')
        js = read('system/control-center/static/options.js')
        for key in ('option-mnpc-demand-enabled', 'option-mnpc-demand-save'):
            self.assertEqual(html.count(f'id="{key}"'), 1)
            self.assertIn(key, js)
        self.assertIn('data-option-section="mnpc-lod"', html)
        self.assertIn('options.js?v=640', html)
        self.assertIn('data.mnpcDemand?.enabled===true', js)
        self.assertIn("{mnpcDemand:{enabled:$('option-mnpc-demand-enabled').checked}}", js)
        self.assertIn('return (Registry.mnpcDemand or {}).enabled == true', read('src/shared/GameOptions.luau'))
        self.assertRegex(read('src/shared/GameOptionsRegistry.luau'), r'mnpcDemand = table\.freeze\(\{\s+enabled = (true|false),')
        demand = read('src/server/actor/MnpcDemandLifecycle.luau')
        self.assertIn('require(Shared:WaitForChild("GameOptions"))', demand)
        self.assertIn('return GameOptions.MnpcDemandEnabled()', demand)
        self.assertNotIn('Game1MnpcDemandEnabled', demand)


if __name__ == '__main__':
    unittest.main()
