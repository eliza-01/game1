"""M548: faster onboarding, reward-only notifications and local Options order."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import game_balance
from kanban_store import KanbanStore

def read(path): return (ROOT/path).read_text(encoding='utf8')

class LevelUpM548(unittest.TestCase):
    def test_two_first_monsters_and_registry(self):
        data=game_balance.load()
        for level,reward in enumerate((30,36,42,48),1):
            self.assertEqual([m['xp'] for m in data['monsters'] if m['level']==level],[reward,reward])
        self.assertEqual(data['levels'][0]['xpNext'],60)
        self.assertEqual(data['levels'][1]['hp']-data['levels'][0]['hp'],20)
        self.assertEqual(data['monsters'][4]['xp'],54)
        self.assertEqual(game_balance.OUTPUT.read_text(),game_balance.render(data))
        self.assertIn('LVL 2 после двух LVL 1',KanbanStore(ROOT).detail('KBN-0031')['spec'])

    def test_earned_only_and_resolved_delta(self):
        view=read('src/server/character/CharacterProgressionView.luau')
        self.assertLess(view.index('Stats.SetProgressionLevel'),view.index('Feedback.PublishLevelUp'))
        self.assertIn('earned == true and level > previousLevel',view)
        self.assertIn('- previousHP',view);self.assertIn('- previousATK',view)
        service=read('src/server/character/CharacterProgressionService.luau')
        self.assertIn('publish(player, attacker, xp, gold, true)',service)
        self.assertIn('publish(player, character, xp, gold)',service)
        loadout=read('src/server/dev/GameplayTestLoadout.luau')
        apply,reward=loadout.split('function Loadout.Reward')
        self.assertIn('ProgressionView.Publish(character, selection.xp, selection.gold)',apply)
        self.assertIn('ProgressionView.Publish(character, selection.xp, selection.gold, true)',reward)
        self.assertIn('GameplayGuideTrial',reward)
        feedback=read('src/server/combat/CombatFeedbackService.luau')
        self.assertIn('kind = "level-up", target = character',feedback)
        self.assertIn('payload.kind == "level-up"',read('src/client/combat/CombatFeedbackController.luau'))

    def test_presentation_passes_input_and_cleans_up(self):
        ui=read('src/client/combat/LevelUpPresentation.luau')
        for token in ('payload.target ~= character','WorldInputPassthrough", true','UDim2.fromScale(.5,.5)','Enum.NormalId.Bottom','Vector3.new(0, -3, 0)','Debris:AddItem(attachment','gui:Destroy()','payload.hpGain','payload.attackGain'):
            self.assertIn(token,ui)
        self.assertNotIn('OnServerEvent',ui)

    def test_option_order_stable_and_local(self):
        html=read('system/control-center/static/index.html')
        sections=re.findall(r'class="game1-option-section" data-option-section="([^"]+)"',html)
        self.assertEqual(len(sections),13);self.assertEqual(len(set(sections)),13)
        js=read('system/control-center/static/options.js').split('// M548',1)[1]
        for token in ('localStorage.getItem(key)','localStorage.setItem(key','parent.insertBefore','event.preventDefault()','event.stopPropagation()','...byKey.keys()'):
            self.assertIn(token,js)
        self.assertNotIn('innerHTML',js);self.assertNotIn('/api/options',js)
