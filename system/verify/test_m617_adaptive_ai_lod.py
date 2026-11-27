"""M617 cadence changes only; real Lua queue/policy and Options round trip."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, tempfile, unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore, normalize_monster_ai

def read(path): return (ROOT/path).read_text(encoding='utf-8')

class AdaptiveAIM617(unittest.TestCase):
    def test_runtime_policy_and_queue(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Lua CLI unavailable')
        subprocess.run([lua,'system/verify/ai_activity_m617.lua'],cwd=ROOT,check=True,timeout=15)

    def test_options_migration_and_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=OptionsStore(Path(tmp))
            old=store.update({'monsterAi':{'experimentalNavigation':{'searchDistance':80,'runtimeEnabled':True}}})
            old['monsterAi'].pop('adaptiveLod')
            store.manifest_path.write_text(json.dumps(old),encoding='utf-8')
            store=OptionsStore(Path(tmp))
            self.assertEqual(store.snapshot()['monsterAi']['adaptiveLod'],{'enabled':False,'dormantSeconds':2})
            new=store.update({'monsterAi':{'adaptiveLod':{'enabled':True,'dormantSeconds':1}}})
            self.assertEqual(new['monsterAi']['experimentalNavigation'],old['monsterAi']['experimentalNavigation'])
            self.assertEqual(store.snapshot()['monsterAi']['adaptiveLod'],{'enabled':True,'dormantSeconds':1})
            self.assertIn('dormantSeconds = 1,',store.registry_path.read_text())
        for invalid in (True,0,2.1,float('nan'),'2'):
            with self.assertRaises(ValueError): normalize_monster_ai({'adaptiveLod':{'dormantSeconds':invalid}})
        with self.assertRaises(ValueError): normalize_monster_ai({'adaptiveLod':{'enabled':1}})

    def test_ui_and_signal_cleanup(self):
        ui=read('system/control-center/static/index.html'); js=read('system/control-center/static/options.js')
        for key in ('option-ai-lod-enabled','option-ai-lod-seconds','option-ai-lod-save'):
            self.assertIn(f'id="{key}"',ui); self.assertIn(key,js)
        for path,cleanup in (('monster/MonsterAgentLifecycle','agent.lifecycleConnections'),('npc/NpcCombatAIService','agent.activityConnections')):
            s=read('src/server/'+path+'.luau')
            self.assertIn('if Activity.Enabled then',s); self.assertIn('Scheduler.Wake(agent)',s)
            self.assertIn('Scheduler.Remove(agent)',s); self.assertIn(cleanup,s); self.assertIn('connection:Disconnect()',s)
        self.assertNotIn('Raycast(',read('src/server/actor/ActorActivityPolicy.luau'))

    def test_protected_navigation_and_decisions(self):
        # These hashes describe M616, not a second runtime implementation.
        hashes=json.loads(read('system/verify/ai_protected_m617.json'))
        # M618 deliberately changes only the Legacy and NPC native path adapters.
        # Keep the historical M616 hashes, not a re-baselined pursuit fixture.
        for path,expected in hashes.items():
            if path in ('src/server/monster/MonsterChaseNavigation.luau', 'src/server/actor/ActorChaseNavigator.luau'):
                continue
            self.assertEqual(hashlib.sha256(read(path).encode()).hexdigest(),expected,path)
