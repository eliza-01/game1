"""M485: floor route authority, stage ownership, lifecycle / scene wiring.

The standalone Luau test executes the pure router when the Luau CLI is installed.
Engine streaming, input and GUI are checked separately in Studio Play.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding='utf-8')

class FloorAndCharacterSceneM485(unittest.TestCase):
    def test_floor_policy_behavior_in_luau(self):
        cli = shutil.which('luau')
        if not cli:
            self.skipTest('Luau CLI unavailable; run standalone test on a Luau installation')
        subprocess.run([cli, 'system/verify/house_elevator_floor_m485.luau'], cwd=ROOT, check=True, timeout=20)

    def test_floor_refs_and_both_validation_paths(self):
        floor = source('src/shared/world/HouseElevatorFloor.luau')
        registry = source('src/server/world/HouseSocketService.luau')
        server = source('src/server/world/HouseElevatorService.luau')
        client = source('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('reference.Value = socket', floor)
        self.assertIn('count ~= folder:GetAttribute("FloorCount")', floor)
        self.assertEqual(floor.count('Policy.CurrentFloor(root.Position.Y, heights, root.Size.Y * 0.5)'), 2)
        self.assertIn('ElevatorFloor.BindPrompt(prompt, entry.sockets)', registry)
        self.assertLess(server.index('Floor.FromSockets(root, sockets) ~= floor'), server.index('character:PivotTo(targetFrame)'))
        self.assertEqual(client.count('ElevatorFloor.AllowsPrompt(prompt, root)'), 3)
        self.assertIn('ElevatorFloor.FromPrompt(prompt, root)', source('src/client/dev/HouseSocketDebugController.luau'))

    def test_selection_camera_and_preview_share_server_declared_scene(self):
        scene = source('src/shared/character/CharacterSelectionScene.luau')
        stream = source('src/server/character/CharacterCreationStreamingService.luau')
        client = source('src/client/character/CharacterCreationController.luau')
        camera = source('src/client/character/CameraController.luau')
        preview = source('src/client/character/CharacterCreationPreviewController.luau')
        self.assertIn('if not cameraFrame or not previewFrame', scene)
        self.assertIn('player:SetAttribute("Game1CharacterSelectionScene", anchors ~= nil)', stream)
        self.assertIn('player:AddReplicationFocus(selection)', stream)
        self.assertIn('player:RemoveReplicationFocus(selection)', stream)
        self.assertIn('player:GetAttribute("Game1CharacterSelectionScene")', client)
        self.assertIn('stage, isCurrent, selectionAnchors)', client)
        self.assertIn('settings.transitionSeconds, selectionAnchors)', client)
        self.assertIn('target = anchors.camera', camera)
        self.assertIn('return anchors.preview', preview)

    def test_stale_responses_and_handoff(self):
        client = source('src/client/character/CharacterCreationController.luau')
        gateway = source('src/server/character/CharacterCreationGateway.luau')
        camera = source('src/client/character/CameraController.luau')
        preview = source('src/client/character/CharacterCreationPreviewController.luau')
        self.assertIn('if epoch ~= token or leaving then return end', client)
        self.assertIn('if not ready[selected] or not sceneReady then return end', client)
        self.assertIn('while epoch == token and not CameraController.ClearCreationView()', client)
        self.assertIn('character ~= localPlayer.Character then return false', camera)
        self.assertIn('setCameraOrbit(camera, root)', camera)
        self.assertIn('if isCurrent and not isCurrent() then return false end', preview)
        self.assertEqual(gateway.count('return self:Request(player, function()'), 3)
        self.assertIn('self.busy[player] = nil', gateway)
        self.assertIn('self.nextRequest[player] = nil', gateway)

    def test_ui_and_input_gate(self):
        panel = source('src/client/character/CharacterCreationPanel.luau')
        controller = source('src/client/character/CharacterCreationController.luau')
        guard = source('src/client/UiInputGuard.luau')
        self.assertNotIn('ToggleFace', panel)
        self.assertIn('local face = activeTab ~= nil', controller)
        self.assertIn('parent:GetPropertyChangedSignal("AbsoluteSize")', panel)
        self.assertIn('local portrait = mobile and viewport.X < viewport.Y', panel)
        self.assertIn('if not archetype then Language.Translate("creation.loading_profile")', panel)
        self.assertIn('views.selectionCaption.Visible = archetype ~= nil', panel)
        self.assertIn('views.selectionLevel.Visible = archetype ~= nil', panel)
        for value in ('true', 'false'):
            self.assertIn(f'SetAttribute("Game1CharacterSceneInputBlocked", {value})', controller)
        self.assertIn('UiInputGuard.IsWorldSuspended()', guard)
        for path in ('character/MovementController.luau', 'character/MobileInputController.luau',
                     'combat/AttackController.luau', 'world/HouseSocketPromptController.luau'):
            self.assertIn('UiInputGuard.IsWorldSuspended()', source('src/client/' + path))

if __name__ == '__main__': unittest.main()
