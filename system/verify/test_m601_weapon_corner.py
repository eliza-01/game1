"""M601: canonical weapon binding and device-safe corner invariants."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services import game_balance


def read(path):
    return (ROOT / path).read_text(encoding='utf8')


class WeaponCornerM601(unittest.TestCase):
    def test_canonical_binding_and_projection(self):
        data = game_balance.load(ROOT)
        models = json.loads(read('assets/manifests/weapons.json'))['items']
        monsters = json.loads(read('assets/manifests/monsters.json'))['items']
        game_balance.check_bindings(data, models, monsters)
        model = next(row for row in models if row['slug'] == 'newbie_slayer_01')
        self.assertEqual(model['weapon_type'], 'bigsword')
        self.assertEqual(str(model['model_asset_id']), '72367246036941')
        binding = data['weaponBindings']['newbie_slayer_01']
        self.assertEqual(binding, 'weapon_003')
        stats = next(row for row in data['weapons'] if row['id'] == binding)
        self.assertEqual(stats['type'], model['weapon_type'])
        self.assertEqual(stats['level'], 1)
        self.assertIn('["newbie_slayer_01"] = "weapon_003"', read('src/shared/balance/BalanceRegistry.luau'))

    def test_device_safe_position_and_core_safe_scale(self):
        controller = read('src/client/weapon/WeaponSelectionController.luau')
        slots = read('src/client/weapon/MobileWeaponSlots.luau')
        layout = read('src/client/character/mobile/MobileLayout.luau')
        self.assertIn('gui.ScreenInsets = Enum.ScreenInsets.DeviceSafeInsets', controller)
        self.assertIn('gui.ClipToDeviceSafeArea = true', controller)
        self.assertIn('gui.SafeAreaCompatibility = Enum.SafeAreaCompatibility.None', controller)
        self.assertIn('else\n            gui.IgnoreGuiInset = false', controller)
        self.assertIn('GuiService:GetInsetArea(Enum.ScreenInsets.CoreUISafeInsets).Size', slots)
        self.assertIn('Layout.Resolve(size.X, size.Y).weapon', slots)
        self.assertIn('local weaponMargin = 2', layout)
        self.assertIn('Vector2.new(1, 0)', slots)
        self.assertIn('UDim2.new(1,-box.margin-', slots)
        self.assertIn('box.margin+math.floor((i-1)/2)', slots)

    def test_existing_server_authority_and_catalog_diagnostic(self):
        equip = read('src/server/weapon/WeaponEquipService.luau')
        selection = read('src/server/weapon/WeaponSelectionService.luau')
        quick = read('src/client/weapon/MobileWeaponQuickSelect.luau')
        self.assertIn('Balance.WeaponForModel(slug, model.weaponType)', equip)
        self.assertIn('if not Access.ServerAllowed(player)', selection)
        self.assertIn('WeaponEquipService.ListAvailable()', selection)
        self.assertIn('WeaponEquipService.Equip(character, slug)', selection)
        self.assertIn('if not slug then', quick)
        self.assertIn('rows = nil\n                    warn("[game1][weapon-slot] no available weapon for type:', quick)
