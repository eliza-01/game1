"""M422 regression: NPC combat should not enter Humanoid knockdown on release.

This validates the server transition contract, not simulated Roblox physics.
The M421 client log demonstrated guard_02 FallingDown before combat, then
root height 2.80 -> 1.00 when unanchored, recovering after a few seconds.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class NpcFallingDownM422(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rig = read("src/server/actor/MnpcNavigationShell.luau")
        cls.ai = read("src/server/npc/NpcCombatAIService.luau")

    def test_no_knockdown_for_npc_navigation_body(self):
        for state in ("FallingDown", "Ragdoll"):
            self.assertIn(
                f"humanoid:SetStateEnabled(Enum.HumanoidStateType.{state}, false)",
                self.rig,
            )
        self.assertIn("local HIP_HEIGHT = 1.8", self.rig)
        self.assertIn("humanoid.HipHeight = HIP_HEIGHT", self.rig)
        self.assertIn('ActorCollisionPolicy.Assign(root, kind)', self.rig)
        self.assertIn('if kind == "NPC" then', self.rig)
        self.assertIn('root.CanQuery = false', self.rig)
        self.assertIn('root.CanTouch = false', self.rig)

    def test_released_root_resumes_running_before_navigation(self):
        transition = self.ai.split("local function pinAtRest(", 1)[1].split("local function clearTarget(", 1)[0]
        self.assertIn("agent.root.Anchored = pin", transition)
        self.assertIn('agent.root:SetNetworkOwner(nil)', transition)
        self.assertIn('agent.humanoid:ChangeState(Enum.HumanoidStateType.Running)', transition)
        self.assertLess(
            transition.index('agent.root.Anchored = pin'),
            transition.index('agent.humanoid:ChangeState(Enum.HumanoidStateType.Running)'),
        )
        self.assertIn('if not pin then', transition)
        self.assertIn('agent.root.AssemblyLinearVelocity = Vector3.zero', transition)
        self.assertNotIn('root.CFrame =', transition)
        self.assertNotIn('HipHeight =', transition)

    def test_fix_is_shared_by_both_guards_not_a_species_special_case(self):
        self.assertIn('pinAtRest(agent, false)', self.ai)
        self.assertIn('pinAtRest(agent, true)', self.ai)
        for src in (self.rig, self.ai):
            self.assertNotIn('guard_02', src)
            self.assertNotIn('guard_01', src)
        self.assertIn('humanoid.BreakJointsOnDeath = false', self.rig)
        self.assertIn('humanoid.HealthDisplayType', self.rig)


if __name__ == "__main__":
    unittest.main()
