"""M68 contracts: NPC combat is a configurable server actor, not weapon-volume melee."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from monster_store import MonsterStore


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class NpcCombatTests(unittest.TestCase):
    def test_registry_behavior_round_trip_and_monster_isolation(self):
        with tempfile.TemporaryDirectory(prefix="game1-m68-") as tmp:
            root = Path(tmp)
            npcs = MonsterStore(root, kind="npc")
            monsters = MonsterStore(root, kind="monster")
            with npcs.connect() as conn:
                conn.execute("""INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,
                  model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature)
                  VALUES('generic_npc','Generic NPC','assets/source/npcs/generic_npc/model/generic_npc.fbx',
                  '123','sha','sha',0,0,'sig')""")
            payload = {
                "slug": "generic_npc", "nameEn": "Generic NPC",
                "stats": {"MaxHP": 150, "Damage": 17, "AttackSpeed": 120, "RunSpeed": 50, "CritChance": 10},
                "behavior": {"retaliateWhenAttacked": True, "pursuitRadiusStuds": 19, "attackRadiusStuds": 4.5, "returnDelaySeconds": 10.5},
            }
            row = npcs.register(payload)
            self.assertTrue(row["behavior"]["retaliateWhenAttacked"])
            self.assertEqual(row["behavior"]["attackRadiusStuds"], 4.5)
            self.assertEqual(npcs.get("generic_npc")["behavior"]["pursuitRadiusStuds"], 19)
            exported = (root / "src/shared/npc/NpcRegistry.luau").read_text(encoding="utf-8")
            self.assertIn("retaliateWhenAttacked = true", exported)
            self.assertIn("pursuitRadiusStuds = 19", exported)
            self.assertIn("returnDelaySeconds = 10.5", exported)
            self.assertEqual(monsters.list(), [])

    def test_asset_manager_accepts_npc_retaliation(self):
        api = source("system/control-center/host_agent.py")
        html = source("system/control-center/static/index.html")
        js = source("system/control-center/static/npc-assets.js")
        self.assertIn('npcs.register(self.body())', api)
        self.assertNotIn('npcs.register({**self.body(), "behavior":', api)
        self.assertIn('id="npc-behavior-retaliate" type="checkbox"', html)
        self.assertIn('id="npc-behavior-pursuit-radius" type="number"', html)
        self.assertIn('id="npc-behavior-return-delay" type="number"', html)
        self.assertIn("behavior:{retaliateWhenAttacked:$('npc-behavior-retaliate').checked", js)

    def test_no_new_weapon_attachment_or_volume_hit_path(self):
        ai = source("src/server/npc/NpcCombatAIService.luau")
        equip = source("src/server/npc/NpcEquipmentService.luau")
        attach = source("src/client/weapon/WeaponAttachmentController.luau")
        self.assertIn('DamageService.Apply(agent.model, target', ai)
        self.assertIn('attackCanConnect(agent, target)', ai)
        self.assertIn('Queries.Visible(', ai)
        self.assertNotIn('WeaponAttackVolume', ai)
        self.assertNotIn('WeaponEquipService', ai)
        self.assertNotIn('NpcWeaponDisarmed', ai)
        self.assertIn('WeaponEquipService.EquipVisual(', equip)
        self.assertIn('updateWeapon(npc, weapon)', attach)
        self.assertNotIn('LocalTransparencyModifier', attach)

    def test_mobile_rig_preserves_authored_bones_and_death_equipment(self):
        rig = source("src/server/npc/NpcRigFactory.luau")
        ai = source("src/server/npc/NpcCombatAIService.luau")
        spawner = source("src/server/npc/NpcSpawnerService.luau")
        animation = source("src/server/npc/NpcAnimationService.luau")
        self.assertIn('root.Name = "HumanoidRootPart"', rig)
        self.assertIn('root.Anchored = false', rig)
        self.assertIn('ActorCollisionPolicy.Assign(root)', rig)
        self.assertIn('humanoid.HipHeight = 1.8', rig)
        self.assertNotIn('Instance.new("Bone")', rig)
        self.assertIn('NpcCombatAIService.Bind(entity, root, presentation)', spawner)
        self.assertIn('NpcCombatAIService.Unbind(entity)', spawner)
        self.assertIn('agent.serial += 1', ai)
        self.assertIn('agent.navigator:Destroy()', ai)
        self.assertIn('idle:Stop()', animation)
        self.assertIn('weaponPresentation:Destroy()', animation)
        self.assertNotIn('Unequip(', animation)
        self.assertNotIn('Unequip(', spawner)

    def test_idle_special_transition_restored(self):
        config = source("src/shared/npc/NpcAnimationConfig.luau")
        tracks = source("src/server/npc/NpcAnimationTracks.luau")
        idle = source("src/server/npc/NpcIdlePresentation.luau")
        self.assertIn('SpecialExitBlendSeconds = 0.15', config)
        self.assertIn('clip.track.Stopped:Connect', idle)
        self.assertIn('Tracks.SecondsRemaining(special)', idle)
        self.assertLess(idle.index('self:_playBase(fade)'), idle.index('Tracks.Stop(finished, fade)'))
        self.assertIn('clip.playbackSpeed = speed', tracks)

    def test_actor_components_owned_by_separate_modules(self):
        navigator = source("src/server/actor/ActorChaseNavigator.luau")
        queries = source("src/server/actor/ActorCombatTargeting.luau")
        ai = source("src/server/npc/NpcCombatAIService.luau")
        self.assertIn('PathfindingService:CreatePath', navigator)
        self.assertIn('task.spawn(function()', navigator)
        self.assertIn('ActorCombatTargeting.ClosestPlayer', queries)
        self.assertIn('RunService.Heartbeat:Connect', ai)
        self.assertIn('TICK_SECONDS = 0.1', ai)
        self.assertIn('local timeline = row and AttackTimelineConfig.ResolveRuntime', ai)


if __name__ == "__main__":
    unittest.main(verbosity=2)
