"""M495: authored compound offsets and replication/scroll integration contracts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
def source(path):
    return (ROOT / path).read_text(encoding='utf8')


class HairMountScrollM495(unittest.TestCase):
    def test_offsets_are_captured_before_first_mount(self):
        builder = source('src/server/character/CharacterAssemblyBuilder.luau')
        self.assertLess(builder.index('BoneModelMount.CaptureHairOffsets(group, anchor)'),
                        builder.index('BoneModelMount.Place(group, anchor,'))
        mount = source('src/shared/rig/BoneModelMount.luau')
        self.assertIn('frame:ToObjectSpace(piece.CFrame)', mount)
        self.assertIn('socketFrame * (piece:GetAttribute("Game1HairGripOffset") :: CFrame)', mount)
        self.assertLess(mount.index('if not BoneModelMount.HairReady(model) then return false end'),
                        mount.index('piece.CFrame = target'))
        self.assertIn('return found == count', mount)
        self.assertIn('local delta = socketFrame * gripFrame:Inverse()', mount)  # unchanged weapon path

    def test_hair_uses_carrier_and_primary_grip(self):
        mount = source('src/shared/rig/BoneModelMount.luau')
        follower = source('src/client/character/BoneMountedAttachmentController.luau')
        self.assertIn('local carrier = imported:FindFirstChild("rig_carrier")', mount)
        self.assertIn('carrier:FindFirstChild(boneName, true)', mount)
        self.assertIn('then BoneModelMount.FindHairBone(character, name)', follower)
        self.assertIn('root and root:FindFirstChild(gripName)', follower)
        self.assertIn('not state.bone:IsDescendantOf(character)', follower)

    def test_preview_replication_and_world_entry_gates(self):
        service = source('src/server/character/CharacterCreationPreviewService.luau')
        self.assertLess(service.index('template:SetAttribute("Game1PreviewDescendantCount"'),
                        service.index('template.Parent = self.folder'))
        preview = source('src/client/character/CharacterCreationPreviewController.luau')
        self.assertLess(preview.index('while not templateReady(template) do'), preview.index('template:Clone()'))
        self.assertIn('if not templateReady(instance) then instance:Destroy(); return false end', preview)
        self.assertLess(preview.index('if not Mounts.UpdateCharacter(instance) then'),
                        preview.index('for part, transparency in pairs(visibility)'))
        controller = source('src/client/character/CharacterCreationController.luau')
        self.assertLess(controller.index('while current() and not Mounts.HairAssemblyReady(model)'),
                        controller.index('pcall(MeshPreloader.PreloadModel, model, current'))
        self.assertIn('world hair replication incomplete; follower will retry', controller)

    def test_manual_canvas_and_material_cells(self):
        panel = source('src/client/character/CharacterCreationPanel.luau')
        self.assertIn('content.AutomaticCanvasSize = Enum.AutomaticSize.None', panel)
        self.assertIn('local position = content.CanvasPosition', panel)
        self.assertIn('height += child.Size.Y.Offset', panel)
        self.assertIn('math.clamp(position.Y, 0,', panel)
        self.assertIn('canvasConnection:Disconnect()', panel)
        controller = source('src/client/character/CharacterCreationController.luau')
        self.assertIn('controls.invalidateCanvas()', controller)
        view = source('src/client/character/CharacterCreationAppearanceView.luau')
        self.assertIn('list.Visible = true', view)
        self.assertNotIn('list.Visible = false', view)
        self.assertIn('item.Activated:Connect(function() pick(material) end)', view)

if __name__ == '__main__':
    unittest.main()
