"""Client integration contracts; engine touch delivery remains a device test."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

ROUTER = read('src/client/character/MobileInputController.luau')
VIEW = read('src/client/character/mobile/MobileControlsView.luau')
LAYOUT = read('src/client/character/mobile/MobileLayout.luau')
PROMPT = read('src/client/world/HouseSocketPromptController.luau')

class MobileControlsM432(unittest.TestCase):
    def test_one_input_owner_no_frame_work(self):
        for source in (ROUTER, VIEW, LAYOUT):
            for forbidden in ('RunService', 'RenderStepped', 'Heartbeat', 'task.wait', 'FireServer', 'Humanoid:Move', 'CameraType'):
                self.assertNotIn(forbidden, source)
        for call in ('movementController.RequestJump()', 'attackController.RequestAttack()', 'cameraController.ToggleAutoAim()', 'cameraController.PinchZoom(pinchGap, currentGap)', 'cameraController.RotateTouch(current - previous)'):
            self.assertEqual(ROUTER.count(call), 1)
        self.assertIn('if axis ~= left.axis then', ROUTER)
        self.assertIn('if left.input then return end', ROUTER)
        self.assertIn('UiInputGuard.BlocksWorldInput(input, gameProcessed)', ROUTER)
        self.assertIn('if current == previous then return end', ROUTER)

    def test_reset_paths_and_character_lifecycle(self):
        for event in ('TouchEnded:Connect(function(input) endTouch(input, false) end)', 'WindowFocusReleased:Connect(resetTouch)', 'TextBoxFocused:Connect(refreshVisibility)', 'MenuOpened:Connect', 'MenuClosed:Connect', 'CharacterRemoving:Connect', 'CharacterAdded:Connect(bindCharacter)', 'Enum.UserInputState.Cancel'):
            self.assertIn(event, ROUTER)
        self.assertIn('character:GetAttribute("LifeState") == "Alive"', ROUTER)
        self.assertIn('model:GetAttributeChangedSignal("LifeState"):Connect(refreshVisibility)', ROUTER)
        self.assertIn('movementController.SetTouchMovement(Vector2.zero, false)', ROUTER)
        self.assertIn('connection:Disconnect()', ROUTER)
        self.assertIn('table.clear(lookPositions)', ROUTER)
        self.assertIn('gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(relayout)', ROUTER)
        self.assertIn('gui:GetPropertyChangedSignal("AbsolutePosition"):Connect(relayout)', ROUTER)

    def test_safe_coordinates_and_passive_stick(self):
        self.assertIn('Enum.ScreenInsets.CoreUISafeInsets', VIEW)
        self.assertIn('position - gui.AbsolutePosition', ROUTER)
        self.assertIn('position - gui.AbsolutePosition', VIEW)
        self.assertIn('pad.Active = false', VIEW)
        self.assertIn('pad:SetAttribute("WorldInputPassthrough", true)', VIEW)
        self.assertIn('left.center = position', ROUTER)
        self.assertIn('pinchLocked = true', ROUTER)
        self.assertIn('if #lookFingers == 1 and not pinchLocked then', ROUTER)
        self.assertIn('left.pad.BackgroundTransparency = 0.78', VIEW)

    def test_weapon_and_aim_presentation_are_event_driven(self):
        self.assertIn('cameraController.AutoAimChanged(view.SetAim)', ROUTER)
        self.assertIn('view.SetAutomatic(enabled)', ROUTER)
        self.assertIn('function result.SetAutomatic', VIEW)
        for icon in ('AttackSlash', 'LeftArrow', 'ReticleRing'):
            self.assertIn(icon, VIEW)

    def test_context_dock_uses_same_selection_and_server(self):
        self.assertIn('local touch = UiSettings.ActiveDevice() == "mobile"', PROMPT)
        self.assertIn('MobileLayout.Context(gui.AbsoluteSize.X, gui.AbsoluteSize.Y, panelHeight)', PROMPT)
        self.assertIn('if not selected or selected.Parent ~= socket then return end', PROMPT)
        self.assertEqual(PROMPT.count('RunService.Heartbeat:Connect'), 1)
        self.assertEqual(PROMPT.count('remote:FireServer(socket, key)'), 1)
        self.assertIn('gui = Instance.new("ScreenGui")', PROMPT)
        self.assertIn('background.Position = UDim2.new(1, -22 + cfg.offsetXPx, 0.5, cfg.offsetYPx)', PROMPT)
        self.assertIn('prompt.KeyboardKeyCode.Name', PROMPT)
        self.assertIn('if visible[socket] and visibleSignature[socket] == state then return end', PROMPT)

    def test_desktop_weapon_menu_and_mobile_shortcuts_are_separate(self):
        picker = read('src/client/weapon/WeaponSelectionController.luau')
        self.assertLess(picker.index('MobileWeaponQuickSelect'), picker.index('local panel = Instance.new'))
        self.assertIn('return -- no mobile WeaponMenuPanel or catalog UI', picker)
        self.assertIn('math.min(365, math.max(218, desktop.Y - 158))', picker)
        self.assertIn('gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize)', picker)
        self.assertEqual(picker.count('selectRemote:InvokeServer(slug)'), 1)

if __name__ == '__main__':
    unittest.main()
