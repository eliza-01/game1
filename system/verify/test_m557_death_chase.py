"""Death Chase data, territory boundary and Options drag contracts (Studio play still required)."""
from copy import deepcopy
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as balance

def read(path): return (ROOT/path).read_text(encoding='utf8')

class DeathChase(unittest.TestCase):
    def test_default_and_species_validation(self):
        data=balance.load()
        self.assertEqual(len(data['monsters']),70)
        self.assertTrue(all(type(row['deathChase']) is bool for row in data['monsters']))
        rows=[row for row in data['monsters'] if row['nameEn']=='Toad']
        self.assertGreater(len(rows),1)
        for row in rows: row['deathChase']=False
        balance.validate(data)
        rows[0]['deathChase']=True
        with self.assertRaisesRegex(ValueError,'species'): balance.validate(data)
        for row in rows: row['deathChase']=True
        balance.validate(data)
        rows[0]['deathChase']=1
        with self.assertRaisesRegex(ValueError,'Death Chase'): balance.validate(data)
    def test_territory_in_runtime_and_attack_guard(self):
        p=read('src/server/monster/MonsterDeathChasePolicy.luau')
        for token in ('PointToObjectSpace(point)','math.abs(p.X) <= size.X/2','math.abs(p.Z) <= size.Z/2','CollectionService:GetTagged(TAG)','if frame ~= nil then return end','if not Policy.IsBound(model) then return true end','record.testKind ~= "zone"'):
            self.assertIn(token,p)
        ai=read('src/server/monster/MonsterAIService.luau')
        self.assertIn('if DeathChase.UsesHomeLeash(agent.model) then',ai)
        self.assertIn('elseif not Navigation.IsBlockedRetreating(agent) and HomeLeash.NoDamageTimeout(',ai)
        self.assertIn('TargetPolicy.AllowsTarget(agent, agent.target)',ai)
        self.assertIn('DeathChase.AllowsPosition(agent.model, root.Position)',read('src/server/monster/MonsterTargetPolicy.luau'))
        self.assertIn('not TargetPolicy.AllowsTarget(agent, target)',read('src/server/monster/MonsterAttackExecutor.luau'))
        self.assertIn('zoneFrame=box.top,zoneSize=Vector3.new(box.size.X,64,box.size.Z)',read('src/server/dev/GameplayTestLayout.luau'))
        self.assertIn('testZoneFrame = if slot then slot.zoneFrame else nil',read('src/server/dev/GameplayTestArena.luau'))
    def test_catalogue_and_ui(self):
        d=balance.load()
        self.assertEqual({s['id'] for s in d['skills'] if s['effect'] in ('might','haste','earth','life','wind')},{'skill_might_d','skill_earth_d','skill_life_d','skill_wind_d'})
        self.assertEqual(len(d['skilledMonsters']),6)
        self.assertTrue(all(s['skillId'] in {x['id'] for x in d['skills']} for p in d['skilledMonsters'] for s in p['skills']))
        js=read('system/control-center/static/game-balance.js')
        self.assertIn("{monsters:'Monsters',skills:'Skills',weapons:'Weapons',levels:'Levels'",js)
        self.assertIn("key==='aggressive'||key==='deathChase'",js)
        options=read('system/control-center/static/options.js')
        self.assertNotIn('game1-option-order',options)
        for token in ('game1-option-drag','pointerdown','pointermove','pointerup','pointercancel','localStorage.setItem(key','parent.insertBefore(node,before?target:target.nextSibling)'):
            self.assertIn(token,options)
        self.assertNotIn('summary::after',read('system/control-center/static/m337-options.css'))
