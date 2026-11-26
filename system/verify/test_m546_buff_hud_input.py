"""M546: decorative buff HUD must not capture world pointer input."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class BuffHudInput(unittest.TestCase):
    def test_both_decorative_roots_opt_out_before_parenting(self):
        hud = read("src/client/combat/BuffHud.luau")
        for name in ("strip", "receipts"):
            self.assertIn(f'{name}.Active=false; {name}:SetAttribute("WorldInputPassthrough", true); {name}.Parent=gui', hud)
        self.assertIn('receipts.Size=UDim2.fromScale(1,1)', hud)
        self.assertIn('icon(receipts,row,48)', hud)
        self.assertIn('icon(strip,row,28)', hud)
        self.assertIn('label(toast,17)', hud)
        self.assertNotIn('gui:SetAttribute("WorldInputPassthrough"', hud)

    def test_existing_guard_inherits_opt_out_and_retains_menu_protection(self):
        guard = read("src/client/UiInputGuard.luau")
        self.assertIn('while current and current ~= playerGui do', guard)
        self.assertIn('current:GetAttribute("WorldInputPassthrough") == true', guard)
        self.assertIn('current = current.Parent', guard)
        self.assertIn('object.Visible and not isPassthrough(object, playerGui)', guard)
        self.assertIn('gameProcessed == true or UiInputGuard.IsWorldSuspended()', guard)
        self.assertIn('UserInputService:GetFocusedTextBox()', guard)
        camera = read("src/client/character/CameraController.luau")
        self.assertIn('UiInputGuard.BlocksWorldInput(input, gameProcessed)', camera)
        self.assertIn('Enum.MouseBehavior.LockCurrentPosition', camera)


if __name__ == "__main__":
    unittest.main()
