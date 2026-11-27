from pathlib import Path
import shutil
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf8')

class MobileDebugQuick(unittest.TestCase):
    def test_actual_helpers(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('stock Lua interpreter unavailable')
        subprocess.run([lua, 'system/verify/mobile_debug_quick_m599.lua'], cwd=ROOT, check=True, timeout=15)

    def test_mobile_filter_applied_at_boot_and_layout(self):
        boot = read('src/client/init.client.luau')
        dock = read('src/client/dev/StudioDebugDock.luau')
        for key, name in [('AG','GameplayAggroController'),('TL','TestLoadoutController'),('HS','HouseSocketDebugController'),('CS','CustomScalingDebugController')]:
            self.assertLess(boot.index('if profile.slots.'+key+' ~= nil then'),boot.index('DevRoot:WaitForChild("'+name+'"'))
        self.assertIn('Profile.Resolve(Input.TouchEnabled, Access.GameplayTestEnabled())', dock)
        self.assertIn('active.slots[id]', dock)
        self.assertIn('if DebugAccess.GameplayTestEnabled() then', boot)

    def test_mobile_never_constructs_desktop_picker_or_new_remotes(self):
        controller = read('src/client/weapon/WeaponSelectionController.luau')
        mobile = read('src/client/weapon/MobileWeaponQuickSelect.luau')
        self.assertLess(controller.index('return -- no mobile WeaponMenuPanel or catalog UI'),controller.index('local launcher = makeButton'))
        self.assertEqual(controller.count('selectRemote:InvokeServer(slug)'),1)
        self.assertNotIn('Instance.new', mobile)
        self.assertNotIn('InvokeServer', mobile)
        self.assertIn('if not PublishedDebugAccess.ClientAllowed() then return end', controller)
        self.assertIn('if not Access.ServerAllowed(player)', read('src/server/weapon/WeaponSelectionService.luau'))
