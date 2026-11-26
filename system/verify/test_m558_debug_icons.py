"""M558 removes obsolete debug RPCs and retains a compact icon-only dock."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[2]
def read(path): return (ROOT/path).read_text(encoding='utf-8')

class DebugIconsM558(unittest.TestCase):
    def test_retired_tools_and_runtime_overrides_are_absent(self):
        forbidden=('MovementDebugController','MovementDebugService','MonsterDebugController','MonsterDebugService',
                   'GetMovementDebugCatalog','ApplyMovementDebug','SetMovementDebugMonsterMode',
                   'GetMonsterDebugCatalog','ApplyMonsterDebug','MovementDebugRunSpeedOverride',
                   'Game1MonsterDebugLocomotionMode','DebugUnitsPerPercentAttribute','MovementDebugAnimationRatioChanged')
        for path in (ROOT/'src').rglob('*.luau'):
            for token in forbidden:
                self.assertNotIn(token,path.read_text(encoding='utf-8'),str(path))
        for name in ('MovementDebug','MonsterDebug'):
            self.assertFalse((ROOT/f'src/client/dev/{name}Controller.luau').exists())
            self.assertFalse((ROOT/f'src/server/dev/{name}Service.luau').exists())

    def test_eight_unique_glyphs_and_no_text_overwrite(self):
        dock=read('src/client/dev/StudioDebugDock.luau')
        icons=read('src/client/dev/StudioDebugIcons.luau')
        slots=re.findall(r'(\w+) = (\d+)',re.search(r'local slots = \{([^}]+)\}',dock)[1])
        expected=['TL','CS','HS','CD','HP','UI','GP','AG']
        self.assertEqual(slots,list(zip(expected,map(str,range(8)))))
        self.assertIn('local SLOT_COUNT = 8',dock)
        masks=re.findall(r'(\w+) = \{ label = "([^"]+)", rows = \{(.*?)\n    \} \}',icons,re.S)
        self.assertEqual([m[0] for m in masks],expected)
        for _,_,rows in masks:
            pixels=re.findall(r'"([.#]+)"',rows)
            self.assertEqual(len(pixels),24)
            self.assertTrue(all(len(row)==24 for row in pixels))
            self.assertGreater(sum(row.count('#') for row in pixels),40)
        self.assertEqual(len({m[2] for m in masks}),8)
        self.assertIn('launcher.Text = ""',icons)
        self.assertIn('canvas.Active = false',icons)
        self.assertIn('paintIcon(if open then ACCENT else TEXT)',dock)
        self.assertNotIn('toggle.Text = "CS"',read('src/client/dev/CustomScalingDebugController.luau'))

    def test_remaining_gameplay_and_authoring_paths(self):
        init=read('src/client/init.client.luau')
        boot=read('src/server/bootstrap/ServiceCatalog.luau')
        for name in ('TestLoadout','GameplayTest','GameplayAggro','CustomScalingDebug','HouseSocketDebug','CameraDebug','HealthUiDebug','UiPresentationDebug'):
            self.assertIn(name+'Controller',init)
        for name in ('TestLoadout','GameplayTest','GameplayAggro','CustomScalingDebug','HouseSocketDebug','MonsterAI','MonsterSpawner'):
            self.assertIn(name+'Service',boot)
        self.assertIn('DebugOverrides.ClipRule',read('src/shared/animation/AnimationSpeedScaling.luau'))
        self.assertIn('MonsterLocomotionMode", "Walk"',read('src/server/monster/MonsterInitialAttributes.luau'))
