"""M69 regression contracts: NPC retaliation, durable migration, actor collision and safe dump."""
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from monster_store import MonsterStore


def source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


class M69Tests(unittest.TestCase):
    def test_npc_return_configuration_and_monster_isolation(self):
        with tempfile.TemporaryDirectory(prefix="m69-npc-") as temp:
            root = Path(temp)
            npc = MonsterStore(root, kind="npc")
            monster = MonsterStore(root, kind="monster")
            self.assertNotIn("aggressive", npc.options()["defaultBehavior"])
            self.assertIn("aggressive", monster.options()["defaultBehavior"])
            with npc.connect() as conn:
                conn.execute("""INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,
                  model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature)
                  VALUES('town_guard','Town Guard','assets/source/npcs/town_guard/model/guard.fbx',
                  '123','sha','sha',0,0,'sig')""")
            payload = dict(slug="town_guard", nameEn="Town Guard", behavior=dict(
                retaliateWhenAttacked=True, pursuitRadiusStuds=19, attackRadiusStuds=4.5,
                returnDelaySeconds=10.5))
            result = npc.register(payload)
            self.assertEqual(result["behavior"]["returnDelaySeconds"], 10.5)
            self.assertTrue(npc.get("town_guard")["behavior"]["retaliateWhenAttacked"])
            registry = source_from(root, "src/shared/npc/NpcRegistry.luau")
            self.assertIn("retaliateWhenAttacked = true", registry)
            self.assertIn("pursuitRadiusStuds = 19", registry)
            self.assertIn("returnDelaySeconds = 10.5", registry)
            self.assertEqual(monster.list(), [])
            with self.assertRaises(ValueError):
                npc.register(dict(payload, behavior=dict(payload["behavior"], returnDelaySeconds=10.25)))
            with self.assertRaises(ValueError):
                npc.register(dict(payload, behavior=dict(payload["behavior"], returnDelaySeconds=-1)))

    def test_legacy_npc_behavior_migrated_without_auto_aggro(self):
        with tempfile.TemporaryDirectory(prefix="m69-migration-") as temp:
            root=Path(temp)
            npc = MonsterStore(root, kind="npc")
            with npc.connect() as conn:
                conn.execute("""INSERT INTO monster_behavior(monster_slug,aggressive,aggro_radius_studs,attack_radius_studs)
                    VALUES('old_guard',1,24,3)""")
                conn.execute("""UPDATE monster_behavior SET retaliate_when_attacked=1 WHERE monster_slug='old_guard'""")
                # Simulate the older schema before migration, retain legacy data in a new database.
            db = root / '.control-center' / 'game1_npcs.db'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("ALTER TABLE monster_behavior RENAME TO monster_behavior_new")
                conn.execute("""CREATE TABLE monster_behavior(monster_slug TEXT PRIMARY KEY,
                    aggressive INTEGER NOT NULL DEFAULT 0, aggro_radius_studs REAL NOT NULL DEFAULT 16,
                    attack_radius_studs REAL NOT NULL DEFAULT 3)""")
                conn.execute("INSERT INTO monster_behavior SELECT monster_slug,aggressive,aggro_radius_studs,attack_radius_studs FROM monster_behavior_new")
                conn.execute("DROP TABLE monster_behavior_new")
            migrated=MonsterStore(root,kind='npc')
            with migrated.connect() as conn:
                row=conn.execute("SELECT * FROM monster_behavior WHERE monster_slug='old_guard'").fetchone()
            self.assertEqual(row['retaliate_when_attacked'],1)
            self.assertEqual(row['return_delay_seconds'],10)
            self.assertEqual(row['aggro_radius_studs'],24)

    def test_damage_notification_and_no_proximity_acquisition(self):
        damage=source('src/server/combat/DamageService.luau')
        ai=source('src/server/npc/NpcCombatAIService.luau')
        self.assertIn('ActorDamageSignals.Publish(attacker, target, normalizedRawDamage, finalDamage, killed)', damage)
        self.assertIn('DamageSignals.Event:Connect(onDamage)', ai)
        self.assertNotIn('Queries.ClosestPlayer(', ai)
        self.assertIn('Queries.Distance(agent.home.Position, root.Position) <= agent.pursuitRadius', ai)
        self.assertNotIn('rng:NextInteger(0, halfSteps) / 2', ai)
        self.assertIn('agent.recovery:Begin(agent.targetKilledAt or os.clock())', ai)
        self.assertIn('NpcMovementPolicy.RecoverySeconds', ai)
        self.assertIn('agent.root.CFrame = agent.home', ai)
        self.assertIn('startReturn(agent, true)', ai)

    def test_single_collision_policy_and_stationary_npc(self):
        policy=source('src/server/actor/ActorCollisionPolicy.luau')
        self.assertIn('CollisionGroupSetCollidable(GROUP, GROUP, true)', policy)
        self.assertIn('root.CanCollide = true', policy)
        for path,root in [('src/server/character/CharacterRigService.luau','navigationRoot'),
                          ('src/server/monster/MonsterRigBuilder.luau','navigationRoot'),
                          ('src/server/npc/NpcRigFactory.luau','root')]:
            self.assertIn('ActorCollisionPolicy.Assign('+root+')',source(path))
        self.assertIn('pinAtRest(agent, true)',source('src/server/npc/NpcCombatAIService.luau'))

    def test_type_weight_fields_and_dump_binary_metadata(self):
        css=source('system/control-center/static/asset-manager.css')
        self.assertIn('field-sizing: content',css)
        self.assertIn('.animation-table-wrap select[data-set]',css)
        bat=source('dump_game1_diag_no_models.bat')
        self.assertIn("'.png', '.jpg', '.jpeg'",bat)
        self.assertIn("'.env.local'",bat)
        self.assertIn('texture_or_image',bat)
        self.assertIn('model_files.json',bat)


def source_from(root,path):
    return (root/path).read_text(encoding='utf-8')

if __name__=='__main__':
    unittest.main(verbosity=2)
