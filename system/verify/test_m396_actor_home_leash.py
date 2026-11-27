"""M396: per-spawn leash + shared confirmed-damage inactivity for hostile NPC/monsters."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from monster_store import MonsterStore
from monster_spawn_store import MonsterSpawnStore


def src(path):
    return (ROOT / path).read_text(encoding='utf-8')


class M396Tests(unittest.TestCase):
    def test_existing_spawn_records_migrate_with_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for kind in ('monster', 'npc'):
                manifest = root / 'assets' / 'manifests' / f'{kind}-spawns.json'
                manifest.parent.mkdir(parents=True, exist_ok=True)
                record = {'spawnId': 'spawn-' + 'a'*12, 'monsterSlug':'gremlin',
                          'position':{'x':1,'y':-42,'z':3},'spawnRadius':15,
                          'maxAlive':3, 'respawnSeconds':10}
                manifest.write_text(json.dumps({'schemaVersion':1, 'project':'game1',
                                                'records':{record['spawnId']:record}}), encoding='utf-8')
                original = manifest.read_bytes()
                store = MonsterSpawnStore(root, None, None, None, kind=kind)
                migrated = store._load()['records'][record['spawnId']]
                self.assertEqual(migrated['homeRadiusStuds'], 16 if kind=='npc' else 150)
                self.assertEqual(migrated['position'],record['position'])
                self.assertEqual(migrated['spawnRadius'],15)
                backup = manifest.with_suffix('.m396.backup.json')
                self.assertEqual(backup.read_bytes(),original)
                digest = manifest.read_bytes()
                MonsterSpawnStore(root, None, None, None, kind=kind)
                self.assertEqual(manifest.read_bytes(),digest)
                self.assertEqual(backup.read_bytes(),original)
                # Separate NPC/monster serializers use the same normalized leash key.
                self.assertIn('homeRadiusStuds', (root/'src/server' / kind / ('NpcSpawnRegistry.luau' if kind=='npc' else 'MonsterSpawnRegistry.luau')).read_text())

    def test_migration_preserves_former_species_radius_for_existing_spawns(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for kind, former in [('npc', 70), ('monster', 220)]:
                actors=MonsterStore(root, kind=kind)
                with actors.connect() as conn:
                    if kind == 'monster':
                        conn.execute("ALTER TABLE monster_behavior ADD COLUMN pursuit_radius_studs REAL NOT NULL DEFAULT 150")
                    conn.execute("INSERT OR REPLACE INTO monster_behavior(monster_slug,aggressive,aggro_radius_studs,attack_radius_studs,pursuit_radius_studs) VALUES (?,?,?,?,?)" if kind=='monster' else
                                 "INSERT OR REPLACE INTO monster_behavior(monster_slug,aggressive,aggro_radius_studs,attack_radius_studs) VALUES (?,?,?,?)",
                                 ('guard', 0, 70, 3, former) if kind=='monster' else ('guard', 0, former, 3))
                manifest=root/'assets/manifests'/f'{kind}-spawns.json'
                record={'spawnId':'spawn-'+ 'b'*12,'monsterSlug':'guard','position':{'x':10,'y':12,'z':15}}
                manifest.parent.mkdir(parents=True,exist_ok=True)
                manifest.write_text(json.dumps({'schemaVersion':1,'project':'game1','records':{record['spawnId']:record}}))
                migrated=MonsterSpawnStore(root,actors,None,None,kind=kind)
                self.assertEqual(migrated._load()['records'][record['spawnId']]['homeRadiusStuds'],former)

    def test_home_leash_is_per_spawn_and_does_not_invalidate_marker_geometry(self):
        source={'spawnId':'spawn-'+'a'*12,'monsterSlug':'gremlin','mapKey':'main','placeId':0,
                'position':{'x':1,'y':2,'z':3}, 'yawDegrees':90,'respawnSeconds':10,
                'homeRadiusStuds':80, 'spawnRadius':15, 'maxAlive':3}
        for npc in (False, True):
            a=MonsterSpawnStore._core(source,npc=npc)
            self.assertEqual(a['homeRadiusStuds'],80)
            if npc:
                self.assertNotIn('spawnRadius',a)
                self.assertNotIn('maxAlive',a)
            with tempfile.TemporaryDirectory() as td:
                store=MonsterSpawnStore(Path(td),None,None,None,kind='npc' if npc else 'monster')
                self.assertEqual(store._fingerprint(source), store._fingerprint({**source,'homeRadiusStuds':200}))

    def test_species_behavior_no_longer_contains_pursuit_radius(self):
        with tempfile.TemporaryDirectory() as td:
            for kind in ('monster','npc'):
                store=MonsterStore(Path(td),kind=kind)
                behavior=store._validate_behavior({},None)
                self.assertNotIn('pursuitRadiusStuds',behavior)
                self.assertNotIn('returnDelaySeconds',behavior)
                self.assertIn('attackRadiusStuds',behavior)
        ui=src('system/control-center/static/index.html')
        self.assertNotIn('id="monster-behavior-pursuit-radius"',ui)
        self.assertNotIn('id="npc-behavior-pursuit-radius"',ui)
        self.assertNotIn('id="npc-behavior-return-delay"',ui)
        self.assertNotIn('id="monster-spawn-home-radius"',ui)
        self.assertIn('homeRadiusStuds',(ROOT/'system/studio-plugin/modules/StudioMonsterSpawnAuthoring.luau').read_text(encoding='utf-8'))
        self.assertIn('id="npc-spawn-home-radius"',ui)
        self.assertNotIn('pursuitRadiusStuds', src('src/shared/npc/NpcRegistry.luau'))
        self.assertNotIn('pursuitRadiusStuds', src('src/shared/monster/MonsterRegistry.luau'))

    def test_both_ais_use_same_damage_timeout_and_spawn_leash(self):
        policy=src('src/server/actor/ActorHomeLeash.luau')
        monster=src('src/server/monster/MonsterAIService.luau')
        npc=src('src/server/npc/NpcCombatAIService.luau')
        self.assertIn('dx * dx + dz * dz > radius * radius', policy)
        self.assertIn('now - lastDamageAt >= timeout',policy)
        for ai in (monster,npc):
            self.assertIn('HomeLeash.NoDamageTimeout(',ai)
            self.assertIn('GameOptions.HostileNoDamageReturnSeconds()',ai)
            if ai == monster:
                self.assertIn('DeathChase.AllowsPursuitPosition(',ai)
                self.assertIn('HomeLeash.Outside(',src('src/server/monster/MonsterDeathChasePolicy.luau'))
            else:
                self.assertIn('HomeLeash.Outside(',ai)
            self.assertIn('lastDamageAt = os.clock()',ai)
            self.assertNotIn('pursuitRadius',ai)
        self.assertIn('if attempted <= 0 or killed', monster)
        self.assertIn('if applied > 0 then agent.lastDamageAt', npc)
        self.assertIn('agent.resetAtHome()',npc)
        self.assertIn('release(state, entity, false)',src('src/server/npc/NpcSpawnerService.luau'))

    def test_npc_single_position_population_unaffected(self):
        spawn=src('src/server/npc/NpcSpawnerService.luau')
        self.assertIn('if next(state.instances) == nil then',spawn)
        self.assertIn('spawnPosition(record)',spawn)
        self.assertIn('if state.active then state.fill() end',spawn)
        self.assertNotIn('record.spawnRadius',spawn)
        self.assertNotIn('record.maxAlive',spawn)
        self.assertIn('NpcCombatAIService.Unbind(entity)',spawn)
        self.assertIn('EntityHitboxService.Detach(entity)',spawn)


if __name__=='__main__':
    unittest.main()
