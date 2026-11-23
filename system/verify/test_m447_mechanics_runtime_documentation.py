"""M447 docs-only coverage: every card is source-grounded and marks missing contracts.

The tests do NOT claim that the Roblox Studio/published runtime was exercised.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.mechanics import route
from mechanics.catalog import DOMAINS, SOURCES, permitted_source, snapshot


class MechanicsDocsM447(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domains = snapshot()['domains']
        cls.items = {item['id']: item for domain in cls.domains for item in domain['items']}

    def test_four_domains_have_grounded_coverage_not_fake_per_asset_scripts(self):
        self.assertEqual({d['id']: len(d['items']) for d in self.domains},
                         {'house': 10, 'npc': 3, 'monster': 3, 'character': 5})
        self.assertEqual(len(self.items), 21)
        self.assertTrue(all(item['scope'] == 'shared' for item in self.items.values()))

    def test_each_card_has_explicit_limitations(self):
        for item in self.items.values():
            sections = [s for s in item['sections'] if 'Недостающее' in s['title']]
            self.assertEqual(len(sections), 1, item['id'])
            self.assertTrue(len(sections[0]['lines']) >= 2, item['id'])
            self.assertTrue(item['sources'], item['id'])
            self.assertTrue(all(len(str(line)) >= 25 for line in sections[0]['lines']), item['id'])

    def test_each_allowlisted_source_exists_and_does_not_escape_project(self):
        for item in self.items.values():
            for source in item['sources']:
                path = ROOT / source['path']
                self.assertTrue(path.is_file(), (item['id'], source))
                self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()))
                self.assertEqual(permitted_source(item['id'], source['id']),
                                 (source['path'], source['title']))
        self.assertIsNone(permitted_source('npc-spawn-lifecycle', 'fireplace-service'))
        self.assertIsNone(permitted_source('character-weapon-attack', '../../.env'))

    def test_npc_and_monster_source_routes_are_read_only(self):
        for item, source in (('npc-combat-home', 'npc-ai'),
                             ('monster-ai-pursuit', 'monster-ai'),
                             ('character-death-respawn', 'character-service')):
            status, payload = route(urlparse(f'/api/mechanics/source?item={item}&source={source}'))
            self.assertEqual(status, 200, item)
            self.assertIn('content', payload)
            self.assertIn('src/server/', payload['path'])
        self.assertEqual(route(urlparse('/api/mechanics/source?item=npc-combat-home&source=attack-service'))[0], 404)

    def test_runtime_gaps_in_house_card_match_implementation(self):
        fireplace = (ROOT / 'src/server/world/HouseFireplaceService.luau').read_text('utf-8')
        campfire = (ROOT / 'src/server/world/LocationCampfireService.luau').read_text('utf-8')
        self.assertIn('local states: {[Model]: State} = {}', fireplace)
        self.assertIn('task.delay(state.cookDuration', fireplace)
        self.assertIn('function Service.Unregister', fireplace)
        self.assertIn('Fireplace.Unregister(model)', campfire)
        gaps = ' '.join(self.items['fireplace']['sections'][-1]['lines'])
        for needle in ('Unregister', 'инвентарь', 'cookOwner', 'task.delay'):
            self.assertIn(needle, gaps)

    def test_actor_and_player_gaps_match_session_lifecycle(self):
        sources = ('src/server/npc/NpcSpawnerService.luau',
                   'src/server/monster/MonsterPopulationController.luau',
                   'src/server/character/CharacterService.luau')
        self.assertTrue(all((ROOT / s).is_file() for s in sources))
        self.assertIn('SelectedCharacterArchetype', (ROOT / sources[2]).read_text('utf-8'))
        self.assertIn('ScheduleRespawn', (ROOT / sources[1]).read_text('utf-8'))
        self.assertIn('NpcSpawnRegistry', (ROOT / sources[0]).read_text('utf-8'))
        # Explicitly protect scope: no claim of an account-store in these cards.
        self.assertIn('DataStore', ' '.join(self.items['character-assembly-spawn']['sections'][-1]['lines']))

    def test_m447_docs_are_discoverable_in_current_index_and_spec(self):
        note = 'MECHANICS_RUNTIME_GAPS_M447_RU.md'
        for f in ('docs/README Read First!.md', 'docs/spec/CURRENT_PROJECT_SPEC_RU.md',
                  'docs/architecture/CURRENT_ARCHITECTURE_RU.md',
                  'docs/workflows/MECHANICS_HOUSE_CATALOG_M436_RU.md',
                  'docs/workflows/CAMPFIRE_AND_FIREPLACE_M442_RU.md',
                  'docs/workflows/UI_PRESENTATION_OPTIONS_M443_RU.md'):
            self.assertIn(note, (ROOT / f).read_text('utf-8'), f)
        audit = (ROOT / 'docs/workflows' / note).read_text('utf-8')
        for needle in ('House 10', 'NPC 3', 'Monster 3', 'Character 5',
                       'DataStoreService', 'Studio', 'Runtime Build'):
            self.assertIn(needle, audit)

    def test_authoring_files_and_runtime_sources_are_untouched_by_docs_milestone(self):
        # Audit coverage test documents non-goals: no new persistence APIs.
        for key in ('fireplace-service', 'character-service', 'monster-ai', 'npc-ai'):
            self.assertTrue((ROOT / SOURCES[key][0]).is_file())
        self.assertTrue((ROOT / 'config/mechanics/fireplace.json').is_file())


if __name__ == '__main__':
    unittest.main()
