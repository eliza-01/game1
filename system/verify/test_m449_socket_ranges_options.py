"""M449: persisted House/Campfire USE/AIM tuning without debug-state leakage."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from options_store import OptionsStore, SOCKET_RANGE_DEFAULTS, normalize_socket_ranges


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class SocketRangesOptionsM449(unittest.TestCase):
    def test_every_exposed_socket_is_actionable_and_has_correct_aim_capability(self):
        house = source('src/shared/world/HouseSocketContract.luau')
        campfire = source('src/shared/world/CampfireSocketContract.luau')
        self.assertEqual(len(SOCKET_RANGE_DEFAULTS['house']), 9)
        for name, row in SOCKET_RANGE_DEFAULTS['house'].items():
            definition = next((line for line in house.splitlines() if f'name = "{name}"' in line), None)
            self.assertIsNotNone(definition, name)
            self.assertIn('interact = true', definition)
            self.assertEqual('aimRadius' in row, 'hoverRadius =' in definition, name)
        self.assertEqual(set(SOCKET_RANGE_DEFAULTS['campfire']), {'fire_socket'})
        self.assertIn('interact = true', campfire)
        for phantom in ('cooking_pot_01_socket', 'chimney_01_socket', 'house_floor_01_spawn_socket'):
            self.assertNotIn(phantom, json.dumps(SOCKET_RANGE_DEFAULTS))

    def test_normalize_rejects_unsafe_values_and_inactive_socket_mutations(self):
        for mutation in (
            {'house': {'unmanaged_socket': {'useRadius': 8}}},
            {'campfire': {'cooking_pot_01_socket': {'useRadius': 6}}},
            {'house': {'chest_01_socket': {'useRadius': 0}}},
            {'house': {'chest_01_socket': {'aimRadius': 32}}},
            {'house': {'chest_01_socket': {'aimRadius': 9}}},
            {'house': {'door_01_handle_inside_socket': {'aimRadius': 4}}},
            {'house': {'chest_01_socket': {'aimRadius': math.inf}}},
            {'house': {'chest_01_socket': {'useRadius': True}}},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                normalize_socket_ranges(mutation)

    def test_partial_update_retains_all_other_socket_ranges(self):
        old = normalize_socket_ranges({'house': {'chest_01_socket': {'useRadius': 9}}})
        new = normalize_socket_ranges({'house': {'fireplace_01_socket': {'aimRadius': 3.5}}},old)
        self.assertEqual(new['house']['chest_01_socket']['useRadius'], 9)
        self.assertEqual(new['house']['fireplace_01_socket']['aimRadius'],3.5)
        self.assertEqual(new['campfire'],old['campfire'])

    def test_new_store_persists_exact_values_and_generates_runtime_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = OptionsStore(root)
            data = store.update({'socketRanges': {'house': {'fireplace_01_socket': {'useRadius': 10.5, 'aimRadius': 5.5}},
                                                   'campfire': {'fire_socket': {'useRadius': 12.5, 'aimRadius': 6.5}}}})
            self.assertEqual(data['socketRanges']['campfire']['fire_socket']['useRadius'],12.5)
            self.assertEqual(OptionsStore(root).snapshot()['socketRanges'],data['socketRanges'])
            runtime = (root/'src/shared/GameOptionsRegistry.luau').read_text(encoding='utf-8')
            for marker in ('socketRanges', 'fireplace_01_socket', 'fire_socket', 'useRadius = 10.5', 'aimRadius = 6.5'):
                self.assertIn(marker,runtime)
            self.assertEqual(data['camera'],store.snapshot()['camera'])

    def test_migrates_custom_legacy_campfire_radius_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = OptionsStore(root)
            before = store.snapshot()
            before.pop('socketRanges')
            store.manifest_path.write_text(json.dumps(before),encoding='utf-8')
            path = root/'config/mechanics/fireplace.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'CampfireInteractionRadius': 14, 'CampfireAimRadius': 7}),encoding='utf-8')
            updated = OptionsStore(root).snapshot()['socketRanges']
            self.assertEqual(updated['campfire']['fire_socket'],{'useRadius':14.0,'aimRadius':7.0})
            path.write_text(json.dumps({'CampfireInteractionRadius': 19,'CampfireAimRadius':10}),encoding='utf-8')
            self.assertEqual(OptionsStore(root).snapshot()['socketRanges'],updated)

    def test_invalid_legacy_mechanics_file_does_not_block_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = OptionsStore(root)
            old = store.snapshot()
            old.pop('socketRanges')
            store.manifest_path.write_text(json.dumps(old), encoding='utf-8')
            legacy = root/'config/mechanics/fireplace.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_text('{broken JSON', encoding='utf-8')
            from contextlib import redirect_stdout
            from io import StringIO
            output = StringIO()
            with redirect_stdout(output):
                next_store = OptionsStore(root)
            self.assertIn('migration skipped',output.getvalue())
            self.assertEqual(next_store.snapshot()['socketRanges']['campfire'], SOCKET_RANGE_DEFAULTS['campfire'])

    def test_runtime_consumers_share_generated_source(self):
        house = source('src/shared/world/HouseSocketContract.luau')
        campfire = source('src/shared/world/CampfireSocketContract.luau')
        server = source('src/server/world/LocationCampfireService.luau')
        for text in (house,campfire):
            self.assertIn('GameOptionsRegistry',text)
            self.assertIn('Options.socketRanges',text)
        self.assertIn('CampfireContract.Fire.radius',server)
        self.assertIn('CampfireContract.Fire.hoverRadius',server)
        self.assertNotIn('return Config.CampfireInteractionRadius',server)
        self.assertIn('definition.radius',source('src/server/world/HouseSocketService.luau'))
        self.assertIn('definition.hoverRadius',source('src/client/world/HouseSocketPromptController.luau'))
        self.assertIn('definition.hoverRadius',source('src/client/world/HouseFireplaceController.luau'))
        html = source('system/control-center/static/index.html')
        js = source('system/control-center/static/options.js')
        self.assertIn('id="option-sockets-fields"',html)
        self.assertIn('game1SocketRangesRender()',js)
        self.assertIn('game1OptionsSave({socketRanges:change}',js)
        self.assertIn('SetTestCampfireSocketRadius', source('src/server/dev/HouseSocketDebugService.luau'))


if __name__ == '__main__':
    unittest.main()
