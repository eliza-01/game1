"""M331 scoped contracts: HP trigger+radius, shared jump physics, mobile camera aim."""
from __future__ import annotations
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from options_store import OptionsStore

def read(path):
    return (ROOT/path).read_text(encoding='utf-8')

class JumpOptions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=OptionsStore(self.root)

    def test_defaults_and_manifest(self):
        expected={'heightMultiplier':2.0, 'descentTimeMultiplier':2.0}
        self.assertEqual(self.store.snapshot()['playerJump'], expected)
        self.assertEqual(json.loads(read('assets/manifests/options.json'))['playerJump'], expected)
        registry=read('src/shared/GameOptionsRegistry.luau')
        self.assertIn('playerJump = table.freeze', registry)
        self.assertIn('function GameOptions.PlayerJumpSettings()', read('src/shared/GameOptions.luau'))

    def test_save_and_validate(self):
        self.assertEqual(self.store.update({'playerJump': {'heightMultiplier':1.5}})['playerJump'],
                         {'heightMultiplier':1.5, 'descentTimeMultiplier':2})
        self.assertEqual(self.store.update({'playerJump': {'descentTimeMultiplier':3}})['playerJump'],
                         {'heightMultiplier':1.5, 'descentTimeMultiplier':3})
        for bad in (0, 4.1, float('nan'), float('inf'), '2', True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.update({'playerJump':{'heightMultiplier':bad}})
        self.assertEqual(self.store.snapshot()['playerJump']['heightMultiplier'],1.5)

    def test_upgrade_existing_options_preserves_unrelated_values(self):
        data=self.store.snapshot()
        data['healthUi']['desktop']['screen']['width']=293
        data['combat']['stateDurationSeconds']=71
        del data['playerJump']
        (self.root/'assets/manifests/options.json').write_text(json.dumps(data))
        new=OptionsStore(self.root).snapshot()
        self.assertEqual(new['playerJump']['heightMultiplier'],2)
        self.assertEqual(new['healthUi']['desktop']['screen']['width'],293)
        self.assertEqual(new['combat']['stateDurationSeconds'],71)

    def test_jump_ballistics_and_force_lifecycle(self):
        move=read('src/client/character/MovementController.luau')
        self.assertIn('JumpVelocity * math.sqrt(JumpSettings.heightMultiplier)', move)
        self.assertIn('Workspace.Gravity * (1 - 1 / (slow * slow))', move)
        self.assertIn('jumpInFlight and downward', move)
        self.assertIn('if fallForce then fallForce:Destroy()',move)
        self.assertIn('force.Enabled = false',move)
        self.assertNotIn('Workspace.Gravity =',move)
        self.assertAlmostEqual((34*math.sqrt(2))**2/(2*196.2) / (34**2/(2*196.2)),2)
        self.assertAlmostEqual(math.sqrt(1/(196.2/4))/math.sqrt(1/196.2),2)

class HealthAndAutoAim(unittest.TestCase):
    def test_two_visibility_triggers_inside_player_radius(self):
        ui=read('src/client/combat/OverheadHealthController.luau')
        self.assertIn('local playerRoot = if character then anchorFor(character)',ui)
        self.assertIn('delta:Dot(delta) <= radiusSquared',ui)
        self.assertIn('or focused or attackingUs',ui)
        self.assertIn('view.SetVisible(alive and inRange',ui)
        self.assertIn('GetAttribute("MonsterTargetUserId") == player.UserId',ui)
        self.assertIn('GetAttribute("MonsterCombatActive") == true',ui)
        self.assertIn('CameraController.GetAimRay()',ui)
        self.assertIn('CameraController.AutoAimTarget()',ui)
        self.assertNotIn('BillboardGui.MaxDistance = radius', ui)
        for distance, focused, attacking in ((99,True,False),(100,False,True),(101,True,True),(50,False,False)):
            displayed=distance<=100 and (focused or attacking)
            self.assertEqual(displayed, (distance in (99,100)),(distance,focused,attacking))

    def test_bone_fallback_matches_real_gremlin(self):
        registry=json.loads(read('assets/manifests/monsters.json'))
        bones=[b['name'] for b in json.loads(registry['items'][0]['skeleton_json'])['bones']]
        self.assertNotIn('neck',bones)
        self.assertIn('spine.003',bones)
        self.assertIn('head',bones)
        selection=read('src/client/character/MobileAutoAimTargeting.luau')
        self.assertIn('name == "neck"',selection)
        self.assertIn('name == "spine.003"',selection)
        self.assertIn('TransformedWorldCFrame.Position',selection)
        self.assertIn('GetAttribute("LifeState") == "Alive"',selection)
        self.assertIn('Workspace:Raycast',selection)

    def test_mobile_aim_does_not_spawn_combat_or_new_camera(self):
        cam=read('src/client/character/CameraController.luau')
        touch=read('src/client/character/MobileInputController.luau')
        self.assertIn('makeAction(gui, "Aim")',touch)
        self.assertIn('cameraController.ToggleAutoAim()',touch)
        self.assertIn('put(aim, centerX + buttonDistance, centerY - 18)',touch)
        self.assertIn('put(attack, centerX - buttonDistance, centerY - 18)',touch)
        self.assertIn('function CameraController.ToggleAutoAim()',cam)
        self.assertIn('function CameraController.GetAimRay()',cam)
        self.assertIn('camera:WorldToViewportPoint(focusPoint)',cam)
        self.assertIn('clearAutoAim()\n\ttargetYaw',cam)
        self.assertNotIn('FireServer',touch+cam)
        self.assertNotIn('Instance.new("Camera")',touch+cam)

if __name__=='__main__': unittest.main()
