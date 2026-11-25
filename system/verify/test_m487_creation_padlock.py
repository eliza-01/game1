"""M487 regression: canonical eye pair, UI lifecycle and full-model socket contract."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def source(path):
    return (ROOT / path).read_text(encoding='utf8')


class CreationPadlockM487(unittest.TestCase):
    def test_eye_payload_behavior(self):
        cli = shutil.which('luau')
        if not cli:
            self.skipTest('Luau CLI unavailable; run character_eye_colors_m487.luau separately')
        subprocess.run([cli, 'system/verify/character_eye_colors_m487.luau'], cwd=ROOT, check=True, timeout=20)

    def test_eye_pair_consumers_and_profile_upgrade(self):
        c = source('src/client/character/CharacterCreationController.luau')
        v = source('src/client/character/CharacterCreationAppearanceView.luau')
        p = source('src/client/character/CharacterCreationPreviewController.luau')
        a = source('src/server/character/CharacterCreationAppearanceService.luau')
        g = source('src/server/character/CharacterCreationGateway.luau')
        s = source('src/server/character/CharacterCreationProfileStore.luau')
        self.assertIn('eyes = EyeColors.Defaults(parts)', c)
        self.assertIn('temporary[group] = table.clone(temporary[group] or {})', c)
        self.assertIn('values.colors[group][channel] = value', c)
        self.assertIn('if #entries == 0 then return end', v)
        self.assertIn('if #entries > 1 then', v)
        self.assertIn('local current = selected.colors.eyes[side]', v)
        self.assertIn('if slot == "eye_l" then color = eyes.l', p)
        self.assertIn('elseif slot == "eye_r" then color = eyes.r', p)
        self.assertIn('EyeColors.Normalize(colors.eyes, EyeColors.Defaults(row.assembly.parts))', a)
        self.assertIn('recipe.parts[slot].color = eyes[side]', a)
        self.assertEqual(g.count('self.profiles.SetValidatedAppearance('), 4)
        self.assertNotIn('appearance = existing.appearance, persisted', g)
        self.assertIn('record.appearance = appearance', s)
        self.assertIn('writeRecord(player, record, false)', s)

    def test_overlay_spans_enter_and_camera_handoff(self):
        c = source('src/client/character/CharacterCreationController.luau')
        action = c.split('enter.Activated:Connect(function()')[1].split('local function sync()')[0]
        self.assertIn('submitting = true', action)
        self.assertLess(action.index('submitting = true'), action.index('Request.Invoke(remote'))
        self.assertIn('submitting = false', action)
        sync = c.split('local function sync()')[1]
        self.assertIn('submitting = not active', sync)
        self.assertLess(sync.index('while epoch == token and not CameraController.ClearCreationView()'),
                        sync.index('Panel.SetSubmitting(controls, false, "")'))
        self.assertIn('if leaving or (submitting and stage == "selection") then "creation.entering_world"', c)

    def test_mount_resolves_whole_model_and_rejects_ambiguous_grips(self):
        m = source('src/shared/rig/AuthoredPropSocketMount.luau')
        adapter = source('src/server/world/HouseSocketAssetMount.luau')
        self.assertIn('model:GetDescendants()', m)
        self.assertIn('item:IsDescendantOf(reference)', m)
        self.assertIn('conflicting_visual_grips', m)
        self.assertIn('missing_authored_grip', m)
        self.assertIn('matches(frame(hole), targetFrame)', m)
        self.assertIn('AuthoredPropSocketMount.Align(model, sourceSocket, target)', adapter)
        self.assertNotIn('reference:FindFirstChild(sourceSocket', adapter)


if __name__ == '__main__':
    unittest.main()
