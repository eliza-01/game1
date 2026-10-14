"""M79 guard: the NPC idle-stance insertion must not crash on a valid clip row.

Lua table.insert(t, position, value) requires a numeric second argument.
The M77 regression passed Python tests but aborted the Roblox server on the
first published NPC idle because table.insert(result, row, 1) was inverted.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class NpcIdleRowsM79Tests(unittest.TestCase):
    def test_idle_base_insert_uses_numeric_position(self):
        adapter = (ROOT / "src/server/npc/NpcAnimationTracks.luau").read_text(encoding="utf-8")
        idle_block = adapter.split('if slot == "idle" then', 1)[1].split('if slot == "death" then', 1)[0]
        self.assertRegex(idle_block, r'table\.insert\(result,\s*1,\s*row\)')
        self.assertNotRegex(idle_block, r'table\.insert\(result,\s*row,\s*1\)')
        self.assertIn('table.insert(result, row)', idle_block)  # All compatible specials retained.
        self.assertIn('baseFound = true', idle_block)  # One preferred base stance.

    def test_debug_services_remain_in_server_startup(self):
        startup = (ROOT / "src/server/init.server.luau").read_text(encoding="utf-8")
        self.assertIn('CustomScalingDebugService")).Start()', startup)
        self.assertIn('MonsterDebugService.Start()', startup)


if __name__ == "__main__":
    unittest.main()
