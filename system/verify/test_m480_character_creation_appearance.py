"""M480 regression: published, rig-checked appearance choices and creation scene."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.character_creation_settings import normalize_character_creation, DEFAULTS
from character_core.creation_appearance_export import catalog
from localization.catalog import read_catalog, emit_luau


class PreviewAssemblyM480(unittest.TestCase):
    def test_spawn_points_roundtrip_and_reject_untrusted_coordinates(self):
        defaults = normalize_character_creation({})
        self.assertEqual(set(defaults['spawnPoints']), {'male','female'})
        changed = normalize_character_creation({'spawnPoints': {
            'male': {'position': [1.5, 2, 3], 'rotationDegrees': [0, 45, 0]},
            'female': {'position': [-5, 2.1, 8], 'rotationDegrees': [0, -90, 0]},
        }}, defaults)
        self.assertEqual(changed['spawnPoints']['male']['position'][0], 1.5)
        self.assertEqual(changed['views'], defaults['views'])
        for corrupt in ({'male': {'position': [1,2,3]}},
                        {'male': {'position':[0,0,0],'rotationDegrees':[0,0,0]},
                         'female': {'position':[0,0,float('inf')], 'rotationDegrees':[0,0,0]}},
                        {}):
            with self.subTest(corrupt=corrupt), self.assertRaises(ValueError):
                normalize_character_creation({'spawnPoints': corrupt})

    def test_registry_exports_only_published_compatible_face_parts(self):
        data = json.loads((ROOT/'assets/manifests/character-creation-appearance.json').read_text(encoding='utf-8'))
        self.assertEqual(data['schemaVersion'], 1)
        self.assertEqual(set(data['archetypes']), {'human_male','human_female'})
        expected = {
            'human_male': {'hair': 3, 'eyes': 1, 'eyebrows': 1, 'head': 1},
            'human_female': {'hair': 3, 'eyes': 1, 'eyebrows': 2, 'head': 1},
        }
        for archetype, categories in data['archetypes'].items():
            for slot, count in expected[archetype].items():
                self.assertGreaterEqual(len(categories[slot]), count)
            for option in ('eyebrows','eyes'):
                for entry in categories[option]:
                    self.assertEqual(entry['left']['id'][-2:], '_l')
                    self.assertEqual(entry['right']['id'][-2:], '_r')
            self.assertTrue(all(v['part']['colorChannels'] for v in categories['hair']))
        runtime = (ROOT/'src/shared/character/CharacterCreationAppearanceRegistry.luau').read_text(encoding='utf-8')
        self.assertIn('human_common_m001_eye', runtime)
        self.assertIn('human_female_m004_hair', runtime)
        self.assertNotIn('human_common_m001_gloves', runtime)
        self.assertNotIn('human_male_m001_upper', runtime)

    def test_server_uses_authoritative_builder_and_client_only_preview(self):
        server = (ROOT/'src/server/character/CharacterCreationPreviewService.luau').read_text()
        appearance = (ROOT/'src/server/character/CharacterCreationAppearanceService.luau').read_text()
        entry = (ROOT/'src/server/character/CharacterCreationGateway.luau').read_text()
        runtime = (ROOT/'src/server/character/CharacterService.luau').read_text()
        local = (ROOT/'src/client/character/CharacterCreationPreviewController.luau').read_text()
        self.assertIn('CharacterAssemblyBuilder', server)
        self.assertIn('CharacterCreationPending', server)
        self.assertIn('self.count >= 32', server)
        self.assertIn('neutralRecipe', server)
        self.assertIn('unknown_appearance_field', appearance)
        self.assertIn('unknown_hair_channel', appearance)
        self.assertIn('local checked, problem = self.validate', entry)
        self.assertIn('self.profiles.Create', entry)
        self.assertIn('self:Stage(player, "selection")', entry)
        self.assertIn('temporaryTemplate', runtime)
        self.assertIn('preview:Bind(remotes)', runtime)
        self.assertIn('Color3.fromRGB', local)
        self.assertIn('instance:PivotTo', local)
        self.assertIn('instance.Parent = self.folder', local)
        self.assertNotIn('EntityHitboxService', local + server)

    def test_ui_is_right_aligned_and_disallows_body_armor_selection(self):
        ui = (ROOT/'src/client/character/CharacterCreationController.luau').read_text()
        view = (ROOT/'src/client/character/CharacterCreationAppearanceView.luau').read_text()
        panel = (ROOT/'src/client/character/CharacterCreationPanel.luau').read_text()
        self.assertIn('Panel.Create(gui, settings)', ui)
        self.assertIn('root.AnchorPoint = Vector2.new(1, 0.5)', panel)
        self.assertIn('root.Position = UDim2.new(1, -16', panel)
        self.assertIn('local content = Instance.new("ScrollingFrame")', panel)
        self.assertNotIn('local root = Instance.new("ScrollingFrame")', panel)
        self.assertIn('requestPreview("human_male")', ui)
        self.assertIn('requestPreview("human_female")', ui)
        self.assertIn('local group = activeTab', view)
        self.assertIn('if #entries > 1 then', view)
        self.assertNotIn('"upper"', view)
        self.assertNotIn('"lower"', view)
        self.assertNotIn('"gloves"', view)
        self.assertNotIn('"boots"', view)
        self.assertNotIn('Instance.new("Camera")', ui)

    def test_localization_all_ten_locales(self):
        c = read_catalog(ROOT)
        for k in ('creation.hair','creation.eyes','creation.eyebrows','creation.hair_color',
                  'creation.eyes_color','creation.eyebrows_color','creation.choose_gender'):
            self.assertEqual(set(c['groups']['creation'][k]['translations']), set(c['locales']))
        self.assertEqual((ROOT/'src/shared/localization/GameTextCatalog.luau').read_text(), emit_luau(ROOT))

if __name__ == '__main__':
    unittest.main()
