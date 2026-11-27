"""M597 engine-free behavior and integration boundaries."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class MobileHoldHudM597(unittest.TestCase):
    def test_pure_repeat_touch_and_layout(self):
        luau = shutil.which('luau')
        lua = shutil.which('texlua') or shutil.which('lua')
        if luau:
            args = [luau, 'system/verify/mobile_hold_hud_m597.luau']
        elif lua:
            args = [lua, 'system/verify/mobile_hold_hud_m597.luau', 'lua']
        else:
            self.skipTest('Luau / Lua interpreter unavailable')
        subprocess.run(args, cwd=ROOT, check=True, timeout=15)

    def test_existing_combat_and_jump_owners(self):
        attack = read('src/client/combat/AttackController.luau')
        touch = read('src/client/character/MobileInputController.luau')
        move = read('src/client/character/MovementController.luau')
        self.assertEqual(attack.count('RunService.RenderStepped:Connect'), 1)
        self.assertEqual(attack.count('attack:FireServer({'), 2)
        self.assertEqual(attack.count('animationController.PlayAction("attack")'), 1)
        self.assertIn('if not repeatInput.IsActive() then return end', attack)
        self.assertIn('repeatInput.SetHeld("mouse", false)', attack)
        self.assertIn('repeatInput.ShouldAttempt(os.clock(), false)', attack)
        self.assertIn('if jumpRequested or (touchJumpHeld and not jumpInFlight and now >= airLockUntil and isGrounded()) then', move)
        self.assertIn('if not isGrounded() or os.clock() < airLockUntil or jumpInFlight then', move)
        self.assertIn('movementController.SetTouchJumpHeld(actions.Held(kind))', touch)
        self.assertIn('attackController.SetAttackHeld("touch", actions.Held(kind))', touch)
        self.assertIn('attackController.SetAttackHeld("touch", false)', touch)
        self.assertIn('setAutomatic(false)', touch)
        self.assertIn('if delta and #lookFingers == 0', touch)
        self.assertNotIn('FireServer', touch)
        self.assertNotIn('RunService', touch)

    def test_registered_actions_and_modal_safety(self):
        touch = read('src/client/character/MobileInputController.luau')
        registry = read('src/client/character/mobile/MobileActionRegistry.luau')
        settings = read('src/client/localization/LanguageMenuController.luau')
        slots = read('src/client/weapon/MobileWeaponSlots.luau')
        self.assertIn('ActionRegistry.SetListener', touch)
        self.assertIn('if onTap and tap and not cancelled and active() then onTap() end', touch)
        self.assertIn('button.InputBegan:Connect', registry)
        self.assertIn('fallbackTouch and not claimed[input]', registry)
        self.assertIn('ActionRegistry.Register(launcher, "Settings"', settings)
        self.assertIn('Game1SettingsInputBlocked', settings)
        self.assertIn('Game1SettingsInputBlocked', read('src/client/UiInputGuard.luau'))
        self.assertIn('ActionRegistry.Register(button, "Weapon"', slots)
        self.assertIn('{"dagger", "sword", "bigsword", "bow"}', slots)
        picker = read('src/client/weapon/WeaponSelectionController.luau')
        self.assertIn('if not PublishedDebugAccess.ClientAllowed() then return end', picker)
        self.assertIn('MobileWeaponQuickSelect', picker)
        self.assertLess(picker.index('MobileWeaponQuickSelect'), picker.index('local panel = Instance.new'))
        self.assertEqual(picker.count('selectRemote:InvokeServer(slug)'), 1)
        self.assertIn('42+math.ceil(content.X)', read('src/client/combat/WalletHud.luau'))

if __name__ == '__main__': unittest.main()
