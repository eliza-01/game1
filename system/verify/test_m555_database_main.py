"""Shared skill catalogue, one Database draft and canonical D shop settings."""
from pathlib import Path
from copy import deepcopy
import json, sys, tempfile, unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance as balance, skill_balance as skills

def read(path): return (ROOT/path).read_text(encoding='utf8')

class DatabaseMain(unittest.TestCase):
    def setUp(self): self.data=balance.load()
    def test_shared_effects_and_current_profile_ids(self):
        rows={row['id']:row for row in self.data['skills']}
        self.assertEqual({row['owner'] for row in rows.values()},{'shared'})
        self.assertEqual(set(skills.SHOP_BUFFS),{'skill_might_d','skill_earth_d','skill_life_d','skill_wind_d'})
        for effect in ('might','earth','life','wind'):
            row=rows['skill_'+effect+'_d'];self.assertEqual(row['effect'],effect)
            self.assertGreater(row['power'],0);self.assertGreater(row['duration'],0)
        self.assertNotIn('skill_might',rows);self.assertNotIn('skill_haste',rows)
        self.assertEqual(len(self.data['skilledMonsters']),6)
        # The shared variants may be assigned to a monster without ownership restrictions.
        for identity in skills.SHOP_BUFFS:
            draft=deepcopy(self.data);draft['skilledMonsters'][0]['skills']=[dict(skillId=identity,downgrade=True,trigger='expired',hpBelow=50)]
            balance.validate(draft);self.assertGreater(skills.resolve(draft)[0]['damage'],0)
        draft=deepcopy(self.data);draft['skills']=[s for s in draft['skills'] if s['id']!='skill_earth_d']
        with self.assertRaises(ValueError): balance.validate(draft)
        draft=deepcopy(self.data);next(s for s in draft['skills'] if s['id']=='skill_earth_d')['effect']='wind'
        with self.assertRaises(ValueError): balance.validate(draft)
    def test_one_revision_can_save_skill_and_monster_changes(self):
        d=deepcopy(self.data);next(s for s in d['skills'] if s['id']=='skill_might_d').update(power=22,duration=900,cooldown=901)
        for m in d['monsters']:
            if m['nameEn']=='Toad': m['aggroRadiusStuds']=21
        weapons={w['id']:w for w in d['weapons']}
        models=[{'slug':slug,'weapon_type':weapons[identity]['type']} for slug,identity in d['weaponBindings'].items()]
        monsters=[{'slug':slug} for slug in d['monsterBindings']]
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'gameplay.json';output=Path(directory)/'BalanceRegistry.luau'
            source.write_text(json.dumps(self.data),encoding='utf8');output.write_text(balance.render(self.data),encoding='utf8')
            with patch.object(balance,'SOURCE',source),patch.object(balance,'OUTPUT',output):
                revision=balance.digest(self.data);balance.save(d,revision,models,monsters)
                self.assertEqual(balance.load(),d)
                self.assertEqual(output.read_text(encoding='utf8'),balance.render(d))
                with self.assertRaisesRegex(ValueError,'changed elsewhere'):balance.save(self.data,revision,models,monsters)
    def test_navigation_and_single_save_owner(self):
        html=read('system/control-center/static/index.html');main=read('system/control-center/static/game-balance.js');editor=read('system/control-center/static/skill-editor.js')
        self.assertIn('>Main</button>',html);self.assertNotIn('id="nav-skills"',html);self.assertNotIn('id="skills-save"',html);self.assertNotIn('id="skilled-save"',html)
        self.assertIn("target='main'",main);self.assertIn("skills:'Skills'",main);self.assertIn('window.game1RenderSkills',main)
        self.assertIn("[['buff','Buff'],['debuff','Debuff'],['monster','Monster'],['character','Character']]",editor)
        self.assertNotIn("request('/api/balance'",editor);self.assertIn('snapshot.revision',main)
        self.assertIn('skilled-monsters-editor',editor);self.assertNotIn('skilled-monsters-disclosure',html)
    def test_runtime_uses_catalogue_and_shared_stat_consumers(self):
        definitions=read('src/shared/combat/BuffDefinitions.luau');effects=read('src/server/combat/SkillEffects.luau')
        self.assertIn('Balance.Skill("skill_"..icon.effect.."_d")',definitions)
        self.assertNotIn('duration=600',definitions);self.assertNotIn('power=20',definitions)
        self.assertIn('BaseMaxHP',effects);self.assertIn('Healing.Restore(target,entry.power)',effects);self.assertIn('SkillRunSpeedBonus',effects)
        self.assertIn('SkillRunSpeedBonus',read('src/server/monster/MonsterChaseNavigation.luau'))
        self.assertIn('AttackSpeedPercent',read('src/server/character/CharacterStatsService.luau'))

if __name__=='__main__': unittest.main()
