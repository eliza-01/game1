"""Source integration contracts; actual weighted chooser: Studio smoke M508."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / 'src/client/character'


class ReactionHistory(unittest.TestCase):
    def test_history_is_group_based_and_reweighted(self):
        source = (CLIENT / 'CharacterCreationReactions.luau').read_text(encoding='utf8')
        choose = source.split('function Reactions.Choose(', 1)[1].split('function Reactions.Remember', 1)[0]
        self.assertIn('if recent then\n        total = 0', choose)
        self.assertIn('if not table.find(recent, entry.group) then total += entry.weight end', choose)
        self.assertIn('if recent and table.find(recent, entry.group) then continue end', choose)
        self.assertIn('if total <= 0 then return nil, nil end', choose)
        self.assertIn('entry.rows[rng:NextInteger(1, #entry.rows)], entry.group', choose)
        self.assertIn('if #recent > 2 then table.remove(recent, 1) end', source)

    def test_history_shared_across_models_and_committed_after_play(self):
        source = (CLIENT / 'CharacterCreationReactions.luau').read_text(encoding='utf8')
        play = source.split('function Reactions:Play(', 1)[1].split('function Reactions:Destroy()', 1)[0]
        self.assertIn('random, self.recent)', play)
        self.assertIn('if not clip or not group or not animator then return end', play)
        self.assertLess(play.index('if not played then self:Remove(model); return end'),
                        play.index('Reactions.Remember(self.recent, group)'))
        self.assertNotIn('recent', source.split('function Reactions:Remove(', 1)[1].split('function Reactions:Play', 1)[0])
        self.assertIn('table.clear(self.recent)', source.split('function Reactions:Destroy()', 1)[1])

    def test_gender_and_tab_actions_reuse_preview_ready_gate(self):
        source = (CLIENT / 'CharacterCreationController.luau').read_text(encoding='utf8')
        for gender in ('male', 'female'):
            block = source.split(f'{gender}.Activated:Connect(function()', 1)[1].split('    end)', 1)[0]
            self.assertIn(f'local changed = selected ~= "human_{gender}"', block)
            self.assertIn(f'if changed then react("human_{gender}") end', block)
            self.assertLess(block.index('refresh(); showStage()'), block.index('then react('))
        tabs = source.split('for _, key in ipairs(Panel.Categories) do', 1)[1].split('local function readSelection()', 1)[0]
        self.assertIn('activeTab = if activeTab == category then nil else category', tabs)
        self.assertIn('refresh(); showStage()\n            react(selected)', tabs)
        self.assertIn('if ready[id] and currentPreview then currentPreview:React(id)', source)
        self.assertIn('if stage == "creation" and selected == id then preview:React(id) end', source)


if __name__ == '__main__': unittest.main()
