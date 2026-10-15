"""M90: module ownership, spawn ordering, and behavior-preserving source contracts."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
MONSTER = ROOT / "src/server/monster"


def read(name):
    return (MONSTER / (name + ".luau")).read_text(encoding="utf-8")


class MonsterModuleBoundaryTests(unittest.TestCase):
    def test_all_modules_have_named_apis_and_no_circular_spawner_dependency(self):
        spawner = read("MonsterSpawnerService")
        for name in ("MonsterRigBuilder", "MonsterSpawnGeometry", "MonsterAnimationTrackFactory", "MonsterInitialAttributes"):
            source = read(name)
            self.assertIn('WaitForChild("' + name + '")', spawner)
            self.assertIn("return table.freeze(" + name + ")", source)
            self.assertNotIn('WaitForChild("MonsterSpawnerService")', source)
            self.assertNotIn('require(script.Parent:WaitForChild("MonsterAIService"))', source)
        self.assertNotIn('Instance.new("Humanoid")', spawner)
        self.assertNotIn('animator:LoadAnimation(', spawner)
        self.assertNotIn('Workspace:Raycast(', spawner)

    def test_rig_build_order_and_identity_policy(self):
        spawner, rig = read("MonsterSpawnerService"), read("MonsterRigBuilder")
        ordered = [
            'MonsterRigBuilder.PrepareVisual(model)',
            'MonsterRigBuilder.EnsureRuntimeAnimationRoot(visual)',
            'spawnGeometry:RandomSpawnPoint(record)',
            'MonsterRigBuilder.GroundAlign(model, surface, yaw)',
            'MonsterInitialAttributes.Apply(model, definition, record, instanceId)',
            'MonsterRigBuilder.CreateNavigationRig(model, visual, visualRoot, surface, yaw)',
            'EntityHitboxService.Attach(model, visual)',
            'MonsterAnimationTrackFactory.Load(',
        ]
        self.assertEqual(sorted(map(spawner.index, ordered)), list(map(spawner.index, ordered)))
        for required in (
            'animationRoot.Name = "RootBone"',
            'animationRoot.CFrame = CFrame.identity',
            'bone.CFrame = animationRoot.CFrame:Inverse() * authoredMeshLocal',
            'ActorCollisionPolicy.Assign(navigationRoot)',
            'root.Name = "RootCollider"',
            'visualWeld.Part1 = visualRoot',
            'humanoid.HipHeight = NAVIGATION_HIP_HEIGHT',
            'navigationRoot:SetNetworkOwner(nil)',
        ):
            self.assertIn(required, rig)

    def test_geometry_maintains_shared_rng_and_raycast_contract(self):
        spawner, geometry = read("MonsterSpawnerService"), read("MonsterSpawnGeometry")
        self.assertEqual(spawner.count('Random.new()'), 1)
        self.assertIn('MonsterSpawnGeometry.new(spawnRandom, ensureMonstersFolder)', spawner)
        self.assertIn('spawnRandom:NextNumber(0, total)', spawner)
        self.assertIn('spawnRandom:NextNumber(0.35, 1.35)', read('MonsterWanderController'))
        self.assertIn('self.random:NextNumber(0, math.pi * 2)', geometry)
        self.assertIn('math.sqrt(self.random:NextNumber(0, 1)) * radius', geometry)
        self.assertIn('self.random:NextNumber(0, maximumLength)', geometry)
        self.assertIn('params.FilterDescendantsInstances = { self.ensureMonstersFolder() }', geometry)
        self.assertIn('params.RespectCanCollide = false', geometry)
        self.assertIn('Workspace:Raycast(origin, Vector3.new(0, -GROUND_RAY_LENGTH, 0), params)', geometry)
        self.assertIn('maximumLength = math.min(maximumLength, distanceToCenter)', geometry)
        self.assertIn('spawnGeometry:ChooseWanderTarget(', read('MonsterWanderController'))

    def test_clip_selection_priority_and_oneshot_are_unchanged(self):
        clips, spawner = read("MonsterAnimationTrackFactory"), read("MonsterSpawnerService")
        self.assertIn('publishedRows(profile, "idle")', clips)
        self.assertIn('if role == "base" and not idleTrack then', clips)
        self.assertIn('firstPublishedTrack(profile, "combat_idle") or firstPublishedTrack(profile, "idle")', clips)
        self.assertIn('firstPublishedTrack(profile, "walk") or firstPublishedTrack(profile, "run")', clips)
        self.assertIn('firstPublishedTrack(profile, "run") or firstPublishedTrack(profile, "walk")', clips)
        self.assertIn('loadAnimationTrack(animator, deathRow, false)', clips)
        self.assertIn('track.Looped = looped', clips)
        self.assertIn('track.Priority = animationPriority(row.priority)', clips)
        self.assertIn('watch(entry, idleTrack.DidLoop, function()', spawner)
        self.assertIn('watch(entry, choice.track.Ended, function()', spawner)
        self.assertIn('DeathAnimationPolicy.LatchVisibleTerminalPose', read('MonsterDeathLifecycle'))

    def test_attributes_still_separate_authored_and_runtime_behavior(self):
        attrs = read("MonsterInitialAttributes")
        for key in ('MonsterAuthoredAggressive', 'MonsterAuthoredAggroRadius', 'MonsterAuthoredAttackRadius',
                    'MonsterAggressive', 'MonsterAggroRadius', 'MonsterAttackRadius', 'MonsterCombatActive',
                    'MonsterAttackPursuitActive', 'CombatUntilServerTime', 'Game1MonsterRuntime'):
            self.assertIn('SetAttribute("' + key + '"', attrs)
        self.assertIn('finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)', attrs)
        self.assertNotIn('AnimationTrack', attrs)


if __name__ == "__main__":
    unittest.main()
