"""M71: NPC continuous attack presentation and common Character/NPC speed rules.

These tests cover migration / saved settings and static runtime contracts. Actual
Animator timing and collision behavior require Studio Play validation.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from animation_speed_scaling_store import AnimationSpeedScalingStore, DEFAULT_PAYLOAD


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8-sig")


class NpcAttackLoopAndSharedSpeedTests(unittest.TestCase):
    def test_existing_character_scaling_is_migrated_once_without_losing_values(self):
        with tempfile.TemporaryDirectory(prefix="game1-m71-speed-") as tmp:
            root = Path(tmp)
            manifest = root / "assets/manifests/animation-speed-scaling.json"
            manifest.parent.mkdir(parents=True)
            original = deepcopy(DEFAULT_PAYLOAD)
            original["profiles"][0]["rules"][0]["unitsPerPercent"] = 1.73
            original["profiles"][0]["rules"][1]["unitsPerPercent"] = 3.25
            original["profiles"][0]["rules"][2]["unitsPerPercent"] = 5.5
            original["profiles"][0]["rules"][3]["unitsPerPercent"] = 2.12
            original["profiles"][0]["targetType"] = "character"
            original["profiles"][0]["targetId"] = "human_female"
            original["profiles"][0]["displayName"] = "Human Female"
            manifest.write_text(json.dumps(original), encoding="utf-8")
            store = AnimationSpeedScalingStore(root)
            payload = store.snapshot()
            shared = next(p for p in payload["profiles"] if p["targetType"] == "humanoid")
            self.assertEqual(shared["targetId"], "all")
            self.assertEqual([r["unitsPerPercent"] for r in shared["rules"]], [1.73, 3.25, 5.5, 2.12])
            self.assertEqual(len(payload["legacyProfiles"]), 1)
            store_again = AnimationSpeedScalingStore(root)
            self.assertEqual(store_again.snapshot(), payload)
            store.update({"targetType": "humanoid", "targetId": "all", "channel": "attack", "unitsPerPercent": 7.25})
            updated = store.snapshot()
            self.assertEqual(next(p for p in updated["profiles"] if p["targetType"] == "monster"), original["profiles"][1])
            self.assertIn('unitsPerPercent = 7.25', (root / "src/shared/animation/AnimationSpeedScalingRegistry.luau").read_text())
            self.assertEqual(updated["legacyProfiles"][0], original["profiles"][0])

    def test_shared_runtime_target_covers_character_and_npc_except_monsters(self):
        runtime = source("src/shared/animation/AnimationSpeedScaling.luau")
        registry = source("src/shared/animation/AnimationSpeedScalingRegistry.luau")
        manifest = json.loads(source("assets/manifests/animation-speed-scaling.json"))
        policy = source("src/shared/animation/AnimationScalingPolicy.luau")
        self.assertIn('return "humanoid", "all"', policy)
        self.assertIn('kind == "character" or kind == "npc"', policy)
        self.assertIn('return "monster"', policy)
        self.assertIn('["humanoid"]', registry)
        self.assertIn('["monster"]', registry)
        profile = next(p for p in manifest["profiles"] if p["targetType"] == "humanoid")
        self.assertEqual({r["channel"]: r["stat"] for r in profile["rules"]}, {
            "walk": "RunSpeed", "run": "RunSpeed", "combat_idle": "AttackSpeed", "attack": "AttackSpeed"
        })
        self.assertFalse(any(p["targetType"] == "character" for p in manifest["profiles"]))
        self.assertIn('Characters and NPCs', source("system/control-center/static/animation-speed.js"))

    def test_attack_remains_one_animation_while_target_stays_within_range(self):
        ai = source("src/server/npc/NpcCombatAIService.luau")
        presentation = source("src/server/npc/NpcAnimationService.luau")
        attack = ai.split('local function beginAttack(', 1)[1].split('local function tickAgent(', 1)[0]
        completion = attack.split('task.delay(math.max(0, duration - elapsed)', 1)[1]
        continuous = completion.split('elseif agent.target == target and attackReady(agent, target) then', 1)[1].split('else', 1)[0]
        self.assertIn('beginAttack(agent, target, true)', continuous)
        self.assertNotIn('EndAttack()', continuous)
        self.assertIn('agent.presentation.ContinueAttack(percent)', attack)
        self.assertIn('local clip = Tracks.Load(animator, row, true)', presentation)
        self.assertIn('Tracks.Play(entity, currentAttack, "attack", nil, speedPercent)', presentation)
        self.assertIn('if combatActive then', presentation.replace('elseif combatActive then', 'if combatActive then'))
        self.assertNotIn('GetAttributeChangedSignal("InCombat")', presentation)
        self.assertIn('SetCombatActive(true)', ai)
        self.assertIn('SetCombatActive(false)', ai)
        self.assertIn('agent.returnAfterAttack = true', attack)
        self.assertIn('agent.targetKilledAt = os.clock()', attack)
        self.assertIn('if hit then', ai)

    def test_monster_ai_and_character_animation_controller_still_use_common_runtime(self):
        monster = source("src/server/monster/MonsterAIService.luau")
        character = source("src/client/character/animation/CharacterAnimationController.luau")
        npc_tracks = source("src/server/npc/NpcAnimationTracks.luau")
        self.assertIn('AnimationSpeedScaling.ResolveForAnimation', character)
        self.assertIn('AnimationSpeedScaling.ResolveScaleForAnimation', monster)
        self.assertIn('AnimationSpeedScaling.ResolveForModel(entity, channel)', npc_tracks)
        self.assertIn('locomotion:Play(NpcMovementPolicy.ModeFor("Peace"))', source("src/server/npc/NpcAnimationService.luau"))
        self.assertIn('locomotion:Play(NpcMovementPolicy.ModeFor("Combat"))', source("src/server/npc/NpcAnimationService.luau"))
        self.assertIn('Tracks.Play(self.entity, clip, channel)', source("src/server/npc/NpcLocomotionPresentation.luau"))
        self.assertIn('AttackTimelineConfig.ResolveRuntime(row.clipId, percent)', source("src/server/npc/NpcCombatAIService.luau"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
