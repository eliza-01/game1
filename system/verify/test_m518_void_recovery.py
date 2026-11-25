from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]

def read(path): return (ROOT / path).read_text(encoding='utf8')

class VoidRecovery(unittest.TestCase):
    def test_server_only_and_death_gate(self):
        source = read('src/server/character/CharacterVoidRecovery.luau')
        self.assertIn('RunService.Heartbeat:Connect', source)
        self.assertIn('character:GetAttribute("LifeState") ~= "Alive"', source)
        self.assertIn('Workspace.FallenPartsDestroyHeight', source)
        self.assertIn('local TEST_DROP = 48', source)
        self.assertIn('local DESTROY_MARGIN = 80', source)
        self.assertIn('if not missing and root.Position.Y >', source)
        self.assertIn('record.busy = true', source)
        self.assertNotIn('RemoteEvent', source)

    def test_existing_spawn_and_test_cleanup(self):
        service = read('src/server/character/CharacterService.luau')
        self.assertIn('VoidRecovery.Watch(player, character, testFrame)', service)
        self.assertIn('VoidRecovery.Start(function(player: Player)', service)
        self.assertIn('local replacement = CharacterService.Respawn(player, archetype)', service)
        self.assertIn('or player:GetAttribute("CharacterCreationStatus") == "world")', service)
        test = read('src/server/dev/GameplayTestService.luau')
        self.assertIn('player.CharacterRemoving:Connect(function(character)', test)
        self.assertIn('clearGroup(s) -- also cancels a group', test)
