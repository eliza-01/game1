"""M440 regressions: camera pointer pass-through and canonical fireplace visuals.

These structural tests are intentionally independent of any Roblox asset load:
Studio Play must still validate the authored carrier/head positions and visuals.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


class M440FireplaceVisualMountCamera(unittest.TestCase):
    def test_decorative_feedback_cannot_block_right_mouse_camera(self):
        prompts = source('src/client/world/HouseSocketPromptController.luau')
        camera = source('src/client/character/CameraController.luau')
        guard = source('src/client/UiInputGuard.luau')
        self.assertRegex(prompts, r'gui.Name = "Game1HouseFeedback"\s*--[^\n]*\n\s*--[^\n]*\n\s*gui:SetAttribute\("WorldInputPassthrough", true\)')
        # M444 moved resource feedback from the fullscreen ScreenGui to
        # per-event, head-anchored BillboardGuis with no pointer capture.
        resources = source('src/client/world/FloatingResourceFeedback.luau')
        self.assertIn('ResourceFeedback.Show(payload.items)', prompts)
        self.assertIn('billboard.Active = false', resources)
        self.assertIn('billboard:SetAttribute("WorldInputPassthrough", true)', resources)
        self.assertIn('WorldInputPassthrough', guard)
        self.assertIn('UiInputGuard.BlocksWorldInput(input, gameProcessed)', camera)

    def test_bottom_status_has_no_fullscreen_pointer_capture(self):
        presenter = source('src/client/world/HouseFireplaceController.luau')
        dock = source('src/client/world/InformativeWindowDock.luau')
        self.assertIn('InfoDock.Get()', presenter)
        self.assertIn('gui = Instance.new("ScreenGui")', dock)
        self.assertIn('panel = Instance.new("Frame")', dock)
        self.assertIn('panel.Position = UDim2.new(0.5, 0, 1, -24)', dock)
        self.assertIn('collapse.Activated:Connect', dock)
        self.assertIn('restore.Activated:Connect', dock)
        self.assertNotIn('Instance.new("BillboardGui")', presenter + dock)
        self.assertIn('panel.Size = UDim2.new(0.9, 0, 0, 92)', dock)
        self.assertNotIn('WorldInputPassthrough', dock)

    def test_mounted_published_models_use_canonical_authored_pivot(self):
        mount = source('src/server/world/HouseSocketAssetMount.luau')
        self.assertIn('local imported = children[1] :: Model', mount)
        self.assertIn('model.PrimaryPart = carrier', mount)
        self.assertIn('model.PrimaryPart = onlyVisual', mount)
        self.assertIn('SpawnOrientation.Upright(socketFrame, fromBone, 0)', mount)
        self.assertIn('BoneModelMount.CreateGrip(reference,', mount)
        self.assertIn('BoneModelMount.Place(model, grip, targetFrame)', mount)
        self.assertIn('actual.Position - targetFrame.Position', mount)
        self.assertNotIn('SocketFacing.FullFrame(socketFrame, fromBone)', mount)
        self.assertNotIn('GetBoundingBox', mount)
        self.assertNotIn('Instance.new("Part")', mount)

    def test_registered_appearance_is_applied_without_republishing(self):
        mount = source('src/server/world/HouseSocketAssetMount.luau')
        visuals = source('src/server/world/EnvironmentAssetVisuals.luau')
        registry = source('src/shared/world/LocationAssetRegistry.luau')
        self.assertIn('Visuals.ApplyModel(model, definition)', mount)
        self.assertIn('definition.meshOptions[mesh.Name]', visuals)
        for slug, material, color in (
            ('firewood_01', 'Wood', '#755A51'),
            ('embers_01', 'CrackedLava', '#C90D0D'),
            ('cooking_pot_01', 'Plastic', '#FFFFFF'),
        ):
            self.assertIn(f'["{slug}"] = table.freeze({{', registry)
            match = re.search(r'\["' + re.escape(slug) + r'"\] = table.freeze\(\{(.*?)\n\s*\}\),', registry, re.S)
            self.assertIsNotNone(match, slug)
            self.assertIn(f'["visualMaterial"]="{material}"', match.group(1))
            self.assertIn(f'["visualColor"]="{color}"', match.group(1))
        self.assertIn('mode=="material_atlas"', visuals)

    def test_fire_and_steam_originate_at_head_and_emit_world_up(self):
        server = source('src/server/world/HouseFireplaceService.luau')
        bonefire = source('src/client/world/BoneFireController.luau')
        self.assertIn('Game1FireDirectionFireplace', server)
        self.assertIn('anchor.CFrame = socketFrame.Rotation:Inverse()', server)
        self.assertIn('local ANCHOR_NAME = "Game1FireDirection"', bonefire)
        self.assertIn('anchor.CFrame = getFrame(socket).Rotation:Inverse()', server)
        self.assertIn('steam.EmissionDirection = Enum.NormalId.Top', server)

    def test_no_fuel_charged_when_model_cannot_be_mounted(self):
        server = source('src/server/world/HouseFireplaceService.luau')
        self.assertRegex(server, r'if not startFire\(state\) then[\s\S]*?return\s*end\s*notify\(player, \{kind = "resource"')
        self.assertIn('if not instance or not potSocket then return false end', server)


if __name__ == '__main__':
    unittest.main()
