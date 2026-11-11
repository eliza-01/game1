"""M290 runtime UI/authority integration checks. Roblox Play/device remain manual."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def read(rel):
    return (ROOT / rel).read_text(encoding="utf8")

class PlaytestWeaponMobilePlotsM290(unittest.TestCase):
    def test_weapon_selection_uses_authoritative_equip_and_not_debug_respawn(self):
        service = read('src/server/weapon/WeaponSelectionService.luau')
        equip = read('src/server/weapon/WeaponEquipService.luau')
        test = read('src/server/dev/TestLoadoutService.luau')
        self.assertIn('WeaponEquipService.ListAvailable()', service)
        self.assertIn('WeaponEquipService.Equip(character, slug)', service)
        self.assertIn('WeaponEquipService.Unequip(character)', service)
        self.assertIn('Game1PlaytestWeaponChosen', service)
        self.assertIn('player.Character', service)
        self.assertIn('Config.CooldownSeconds', service)
        self.assertNotIn('CharacterService.Respawn', service)
        self.assertNotIn('ApplyTestLoadout', service)
        self.assertNotIn('GetTestLoadoutCatalog', service)
        self.assertIn('if started or not RunService:IsStudio() then', test)
        self.assertIn('Game1PlaytestWeaponChosen', equip)

    def test_live_menu_reuses_server_catalog(self):
        ui = read('src/client/weapon/WeaponSelectionController.luau')
        init = read('src/client/init.client.luau')
        bootstrap = read('src/server/bootstrap/ServiceCatalog.luau')
        self.assertIn('GetWeaponSelectionCatalog', ui)
        self.assertIn('SelectWeapon', ui)
        self.assertIn('WeaponSelectionController.Start()', init)
        self.assertIn('WaitForChild("WeaponSelectionService")).Start()', bootstrap)
        self.assertIn('WeaponMenuToggle', ui)
        self.assertIn('Unarmed', ui)
        self.assertNotIn('FireServer(', ui)

    def test_touch_sticks_and_action_graphics(self):
        ui = read('src/client/character/MobileInputController.luau')
        self.assertIn('inner.Visible = false', ui)
        self.assertIn('stick.thumb.Visible = true', ui)
        self.assertIn('stick.thumb.Visible = false', ui)
        self.assertIn('button.Text = ""', ui)
        self.assertIn('"Blade"', ui)
        self.assertIn('"Body"', ui)
        self.assertNotIn('"КАМЕРА"', ui)
        self.assertNotIn('"БЕГ"', ui)
        self.assertNotIn('"ПРЫЖОК"', ui)
        self.assertNotIn('"УДАР"', ui)
        self.assertIn('movementController.SetTouchMovement', ui)
        self.assertIn('cameraController.SetTouchLookAxis', ui)
        self.assertIn('attackController.RequestAttack()', ui)

    def test_touch_prompt_uses_existing_server_validation(self):
        ui = read('src/client/world/HouseSocketPromptController.luau')
        server = read('src/server/world/HouseSocketService.luau')
        self.assertIn('local touch = UserInputService.TouchEnabled', ui)
        self.assertIn('local action = Instance.new("TextButton")', ui)
        self.assertIn('action.Activated:Connect(function()', ui)
        self.assertIn('requestAction(prompt)', ui)
        self.assertIn('requestAction(matching)', ui)
        self.assertIn('HouseSocketInteract', ui)
        self.assertIn('handleInteraction(house, socket.Name, player, key)', server)
        self.assertIn('allowedDistance', server)
        self.assertIn('if key ~= "E" and key ~= "F" then return end', server)

    def test_plot_marker_visibility_scoped_to_authoring_volume_or_numbers(self):
        hide = read('src/server/world/PlotMarkerVisibilityService.luau')
        self.assertIn('plotIndex(part.Parent)', hide)
        self.assertIn('plot_%02d_volume', hide)
        self.assertIn('Numbers_1-50', hide)
        self.assertIn('instance.CanCollide = false', hide)
        self.assertIn('instance.Transparency = 1', hide)
        self.assertNotIn(':Destroy()', hide)
        self.assertNotIn('Workspace.Plots:ClearAllChildren()', hide)
        self.assertIn('WaitForChild("PlotMarkerVisibilityService")).Start()', read('src/server/bootstrap/ServiceCatalog.luau'))

if __name__ == '__main__': unittest.main()
