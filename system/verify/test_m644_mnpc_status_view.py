from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MnpcStatusView(unittest.TestCase):
    def test_summary_and_groups(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/mnpc_status_m644.lua'], cwd=ROOT, check=True, timeout=15)

    def test_explicit_canvas_and_separate_capture(self):
        source = (ROOT/'src/client/dev/LodDebugController.luau').read_text()
        for token in ('ScrollingEnabled=true', 'Active=true', 'ScrollingDirection=Enum.ScrollingDirection.Y',
                      'for _, row in ipairs(group.rows)', 'mnpcScroll.CanvasSize = UDim2.fromOffset(0,y)',
                      'mnpcScroll:ClearAllChildren()', 'scroll.Visible = false', 'mnpcScroll.Visible = false',
                      'renderMnpc(MnpcView.Build(snapshot,Options.MnpcDemandEnabled(),reason))'):
            self.assertIn(token,source)
        self.assertNotIn('Heartbeat:Connect', source)
        self.assertNotIn('RemoteEvent', source)
