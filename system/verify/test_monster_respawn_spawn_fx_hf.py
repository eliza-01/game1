"""Monster respawn/fade/ground-rise regression + SQLite migration round trip.

Roblox TweenService and physics still require an in-Studio Play smoke test.
"""
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
import monster_store

MONSTER = ROOT / "src/server/monster"


class MonsterRespawnSpawnFxTests(unittest.TestCase):
    def test_one_expired_death_timer_creates_at_most_one_monster(self):
        population = (MONSTER / "MonsterPopulationController.luau").read_text()
        spawner = (MONSTER / "MonsterSpawnerService.luau").read_text()
        self.assertIn("entry.diedAt = os.clock()", spawner)
        self.assertIn("population:ScheduleRespawn(state, entry.diedAt)", spawner)
        self.assertIn("local elapsed = if diedAt then math.max(0, os.clock() - diedAt) else 0", population)
        self.assertIn("local remaining = math.max(0, delaySeconds - elapsed)", population)
        timer = population.split("task.delay(remaining, function()", 1)[1].split("end)\n", 1)[0]
        self.assertIn("if liveCount(state) + state.creating < target then", timer)
        self.assertIn("spawnReserved(state)", timer)
        self.assertIn('state.creating += 1', population)
        self.assertIn('local ok, result = pcall(spawnOne, state)', population)
        self.assertIn('state.creating -= 1', population)
        self.assertNotIn("fill(state)", timer)
        self.assertNotIn("while ", timer)
        self.assertEqual(population.count("task.delay("), 1)
        self.assertIn("releaseInstance(state, model, false, true)", spawner)

    def test_reveal_gate_cleanup_and_no_gameplay_ownership(self):
        fx = (MONSTER / "MonsterSpawnPresentation.luau").read_text()
        spawner = (MONSTER / "MonsterSpawnerService.luau").read_text()
        ai = (MONSTER / "MonsterAIService.luau").read_text()
        self.assertIn('TweenService:Create(item.instance, info, {Transparency = item.original})', fx)
        self.assertIn('TweenService:Create(navigationRoot, info, {CFrame = raisedCFrame})', fx)
        self.assertIn('if riseFromGround then', fx)
        self.assertIn('local raisedCFrame = finishCFrame + Vector3.new(0, RISE_CLEARANCE_STUDS, 0)', fx)
        self.assertIn('MonsterSpawnPresentation.Prepare(model, visual, navigationRoot, humanoid, riseFromGround)', spawner)
        self.assertIn('releaseToGravity(onReady)', fx)
        self.assertIn('navigationRoot.AssemblyLinearVelocity = Vector3.zero', fx)
        self.assertIn('humanoid:ChangeState(Enum.HumanoidStateType.Freefall)', fx)
        self.assertIn('RunService.Heartbeat:Wait()', fx)
        self.assertIn('humanoid.FloorMaterial ~= Enum.Material.Air', fx)
        self.assertIn('navigationRoot.Anchored = oldAnchored', fx)
        self.assertIn('navigationRoot.CanCollide = oldCanCollide', fx)
        self.assertIn('navigationRoot.CanQuery = oldCanQuery', fx)
        self.assertIn('model:SetAttribute("Damageable", true)', fx)
        self.assertIn('model:SetAttribute("MonsterSpawning", false)', fx)
        # Do not allow combat/wander until AFTER restoring terrain collision and releasing anchor.
        self.assertLess(fx.index('navigationRoot.CanCollide = oldCanCollide'), fx.index('humanoid:ChangeState(Enum.HumanoidStateType.Freefall)'))
        self.assertLess(fx.index('RunService.Heartbeat:Wait()'), fx.index('finish(onReady)\n                        return'))
        self.assertLess(fx.index('model:SetAttribute("MonsterSpawning", false)'), fx.index('onReady()'))
        self.assertIn('tostring(model:GetAttribute("LifeState") or "") == "Alive"', fx)
        self.assertIn('entry.spawnPresentation:Cancel()', spawner)
        self.assertLess(spawner.index('MonsterSpawnPresentation.Prepare('), spawner.index('EntityHitboxService.Attach('))
        self.assertLess(spawner.index('spawnPresentation:Start('), spawner.index('wanderController:Start(state, model, entry)'))
        self.assertIn('if agent.model:GetAttribute("MonsterSpawning") == true then\n            continue', ai)
        for forbidden in ('MonsterRegistry', 'MonsterSpawnerService', 'DeathLifecycle', 'MonsterAIService', 'Instance.new('):
            self.assertNotIn(forbidden, fx)

    def test_fixed_1_5_second_descent_preserves_ground_contact_gate(self):
        fx = (MONSTER / "MonsterSpawnPresentation.luau").read_text()
        self.assertIn('local RISE_CLEARANCE_STUDS = 1.25', fx)
        self.assertIn('local LANDING_SECONDS = 1.5', fx)
        self.assertIn('TweenInfo.new(LANDING_SECONDS, Enum.EasingStyle.Sine, Enum.EasingDirection.Out)', fx)
        self.assertIn('TweenService:Create(navigationRoot, landingInfo, {CFrame = finishCFrame})', fx)
        self.assertIn('local playbackState = landingTween.Completed:Wait()', fx)
        self.assertIn('playbackState ~= Enum.PlaybackState.Completed or not active()', fx)
        self.assertNotIn('SOFT_LANDING_MIN_SPEED', fx)
        self.assertNotIn('SOFT_LANDING_MAX_SPEED', fx)
        self.assertNotIn('SOFT_LANDING_SPEED_PER_STUD', fx)
        self.assertNotIn('SOFT_LANDING_SLOWDOWN', fx)
        self.assertIn('local SETTLE_CONFIRM_SECONDS = 0.12', fx)
        self.assertIn('local VERTICAL_SPEED_TOLERANCE = 0.2', fx)
        self.assertIn('local MAX_FALL_SECONDS = 4.0', fx)
        self.assertIn('settledSince ~= nil and os.clock() - settledSince >= SETTLE_CONFIRM_SECONDS', fx)
        self.assertLess(fx.index('local playbackState = landingTween.Completed:Wait()'), fx.index('releaseToGravity(onReady)'))
        self.assertLess(fx.index('navigationRoot.CanCollide = oldCanCollide'), fx.index('humanoid:ChangeState(Enum.HumanoidStateType.Freefall)'))
        self.assertLess(fx.index('navigationRoot.Anchored = oldAnchored'), fx.index('local settledSince: number? = nil'))
        self.assertIn('navigationRoot.CFrame = finishCFrame', fx)

    def test_legacy_db_migrates_and_existing_rows_default_off(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db_path = root / '.control-center/game1.db'
            db_path.parent.mkdir(parents=True)
            with closing(sqlite3.connect(db_path)) as db:
                db.execute('CREATE TABLE monster_behavior (monster_slug TEXT PRIMARY KEY, aggressive INTEGER NOT NULL DEFAULT 0, aggro_radius_studs REAL NOT NULL DEFAULT 16, attack_radius_studs REAL NOT NULL DEFAULT 3)')
                db.execute('INSERT INTO monster_behavior VALUES (?,?,?,?)', ('legacy', 1, 18, 4))
                db.commit()
            store = monster_store.MonsterStore(root)
            with closing(store.connect()) as db:
                columns = {r[1] for r in db.execute('PRAGMA table_info(monster_behavior)')}
                self.assertIn('rise_from_ground', columns)
                behavior = store._behavior(db, 'legacy')
                self.assertEqual(behavior['aggroRadiusStuds'], 18)
                self.assertFalse(behavior['riseFromGround'])
            store._init()  # idempotent migration
            self.assertFalse(store._validate_behavior({'behavior': {}}, None)['riseFromGround'])
            self.assertTrue(store._validate_behavior({'behavior': {'riseFromGround': True}}, None)['riseFromGround'])

    def test_registration_round_trip_and_generated_registry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'monster.fbx'
            source.write_bytes(b'fake-fbx-with-mocked-analysis')
            with patch.object(monster_store, 'analyze_character_fbx', return_value={
                'armature': 'test', 'boneCount': 1, 'meshCount': 1,
                'skeletonSignature': 'sig', 'skeletonStructureSignature': 'struct',
            }):
                store = monster_store.MonsterStore(root)
                payload = {
                    'slug': 'test_monster', 'nameEn': 'Test Monster',
                    'modelSourcePath': str(source), 'behavior': {'riseFromGround': True},
                }
                row = store.register(payload)
                self.assertTrue(row['behavior']['riseFromGround'])
                self.assertEqual(row['status'], 'LOCAL_ONLY')
                self.assertIn('riseFromGround = true', (root / 'src/shared/monster/MonsterRegistry.luau').read_text())
                # Metadata editing doesn't change the asset hash or require republishing.
                new_payload = {**payload, 'modelSourcePath': '', 'behavior': {'riseFromGround': False}}
                updated = store.register(new_payload)
                self.assertFalse(updated['behavior']['riseFromGround'])
                self.assertEqual(updated['model_sha256'], row['model_sha256'])
                self.assertIn('riseFromGround = false', (root / 'src/shared/monster/MonsterRegistry.luau').read_text())

    def test_ui_uses_per_monster_metadata_and_does_not_touch_spawn_records(self):
        html = (ROOT / 'system/control-center/static/index.html').read_text()
        js = (ROOT / 'system/control-center/static/monster-assets.js').read_text()
        self.assertIn('id="monster-behavior-rise-from-ground"', html)
        self.assertIn("behavior.riseFromGround===true", js)
        self.assertIn("riseFromGround:$('monster-behavior-rise-from-ground').checked", js)
        self.assertNotIn('riseFromGround', (ROOT / 'system/control-center/static/monster-spawns.js').read_text())
        self.assertNotIn('riseFromGround', (ROOT / 'system/control-center/static/npc-assets.js').read_text())


if __name__ == '__main__':
    unittest.main()
