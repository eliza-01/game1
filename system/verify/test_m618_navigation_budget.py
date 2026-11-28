from pathlib import Path
import json, hashlib, shutil, subprocess, sys, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore, normalize_monster_ai

def read(p): return (ROOT/p).read_text(encoding='utf-8')

class NavigationBudgetM618(unittest.TestCase):
    def test_queue(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua: self.skipTest('Lua CLI unavailable')
        subprocess.run([lua,'system/verify/navigation_budget_m618.lua'],cwd=ROOT,check=True,timeout=15)
        subprocess.run([lua,'system/verify/navigation_consumers_m618.lua'],cwd=ROOT,check=True,timeout=15)

    def test_only_native_admission_and_protected_navigation(self):
        paths=[p.relative_to(ROOT).as_posix() for p in (ROOT/'src/server').rglob('*.luau') if ':ComputeAsync(' in p.read_text(encoding='utf-8')]
        self.assertEqual(paths,['src/server/actor/NavigationScheduler.luau'])
        # M629 adds explicit pose attachment/readiness only; M629 tests guard action timing.
        hashes=json.loads(read('system/verify/ai_protected_m617.json'))
        for path,digest in hashes.items():
            if path.endswith(('MonsterChaseNavigation.luau','ActorChaseNavigator.luau','MonsterSpawnerService.luau','MonsterRigBuilder.luau',
                              'MonsterCombatPresentation.luau','MonsterAttackExecutor.luau','MonsterSkillCast.luau')): continue
            self.assertEqual(hashlib.sha256(read(path).encode()).hexdigest(),digest,path)
        for path in ('monster/MonsterChaseNavigation','actor/ActorChaseNavigator'):
            s=read('src/server/'+path+'.luau')
            for token in ('Budget.Request','Budget.Cancel','Budget.Take','Budget.IsStale','Budget.UpdateQueued','Budget.Dispose'):
                self.assertIn(token,s)
        scheduler=read('src/server/actor/NavigationScheduler.luau')
        self.assertNotIn('MoveTo(',scheduler)
        self.assertNotIn('Heartbeat',scheduler)
        self.assertIn('NavigationBudget.Pump()',read('src/server/actor/ActorAIScheduler.luau'))

    def test_options_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=OptionsStore(Path(tmp))
            original=store.snapshot()['monsterAi']
            self.assertEqual(original['navigationBudget'],{'concurrent':2,'startsPerSecond':8})
            new=store.update({'monsterAi':{'navigationBudget':{'concurrent':3,'startsPerSecond':12}}})['monsterAi']
            self.assertEqual(new['adaptiveLod'],original['adaptiveLod'])
            self.assertEqual(new['experimentalNavigation'],original['experimentalNavigation'])
            self.assertEqual(store.snapshot()['monsterAi']['navigationBudget'],{'concurrent':3,'startsPerSecond':12})
            self.assertIn('startsPerSecond = 12,',store.registry_path.read_text())
        for key,value in [('concurrent',0),('concurrent',9),('concurrent',True),('startsPerSecond',31),('startsPerSecond',1.5)]:
            with self.assertRaises(ValueError): normalize_monster_ai({'navigationBudget':{key:value}})
