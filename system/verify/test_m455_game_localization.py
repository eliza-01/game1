"""M455 localization: source/consumer compatibility, complete translations and read-only authoring."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from localization.catalog import read_catalog, emit_luau, LOCALES, NAMES
from api.read_world import route as read_world


class M455Localization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = read_catalog(ROOT)
        cls.entries = {key: row for group in cls.catalog['groups'].values() for key, row in group.items()}
        cls.source_map = {row['source']: key for key, row in cls.entries.items()}

    def test_all_10_languages_have_complete_manual_translations(self):
        self.assertEqual(len(LOCALES), 10)
        self.assertEqual(set(self.catalog['locales']), set(LOCALES))
        self.assertGreaterEqual(len(self.entries), 115)
        for key, row in self.entries.items():
            self.assertEqual(set(row['translations']), set(LOCALES), key)
            self.assertTrue(all(v.strip() for v in row['translations'].values()), key)
            source_placeholders = set(re.findall(r'{([a-z_]+)}', row['source']))
            for locale, translated in row['translations'].items():
                self.assertEqual(source_placeholders, set(re.findall(r'{([a-z_]+)}', translated)), (key, locale))

    def test_authored_manifest_is_the_only_runtime_source(self):
        generated = ROOT / 'src/shared/localization/GameTextCatalog.luau'
        self.assertEqual(generated.read_text(encoding='utf-8'), emit_luau(ROOT))
        self.assertIn('GameTextCatalog', (ROOT / 'src/client/localization/LanguageState.luau').read_text())
        self.assertNotIn('game1-languages', (ROOT / 'assets/manifests/options.json').read_text())

    def test_corrupt_or_partial_translation_cannot_publish(self):
        data = json.loads(json.dumps(self.catalog))
        data['groups']['action']['action.open_door']['translations'].pop('ko-kr')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'assets/manifests/game-localization.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'missing or unknown locale'):
                read_catalog(Path(temp))

    def test_read_only_options_languages_route(self):
        status, payload = read_world(urlparse('/api/options/languages'),
                                     {'options': SimpleNamespace(root=ROOT)}, lambda: {})
        self.assertEqual(status, 200)
        self.assertEqual(payload, self.catalog)
        self.assertEqual(payload['groups']['action']['action.open_door']['translations']['de-de'], 'Tür öffnen')
        self.assertEqual(payload['groups']['hud']['hud.elevator_floor']['translations']['en-us'],
                         'Elevator · floor {floor}')

    def test_server_world_prompts_and_feedback_have_catalog_sources(self):
        critical = [
            'src/shared/world/HouseSocketContract.luau',
            'src/server/world/HousePadlockService.luau',
            'src/server/world/HouseSocketService.luau',
            'src/server/world/HouseElevatorService.luau',
            'src/server/world/HouseFireplaceService.luau',
            'src/server/world/LocationCampfireService.luau',
            'src/server/world/WindmillDoorService.luau',
        ]
        # A stable set of gameplay strings; no translation changes to server ActionText.
        for literal in (
            'Открыть дверь', 'Закрыть дверь', 'Открыть сундук', 'Разжечь огонь',
            'Убрать котел', 'Поставить котел', 'Добавить ингредиенты', 'Блюдо готовится',
            'Навесить замок · ключ', 'Нужен ключ', 'Замок снят · дверь разблокирована',
            'Сундук пока недоступен', 'Огонь разожжён', 'Ингредиенты добавлены',
        ):
            self.assertIn(literal, self.source_map)
            self.assertTrue(any(literal in (ROOT / file).read_text(encoding='utf-8') for file in critical), literal)
        self.assertIn('hud.key', self.catalog['groups']['hud'])
        self.assertIn('Language.Translate("hud.key")', (ROOT / 'src/client/world/HouseSocketPromptController.luau').read_text())
        self.assertIn('^Лифт · этаж (%d+)$',
                      (ROOT / 'src/client/world/HouseSocketPromptController.luau').read_text(encoding='utf-8'))

    def test_existing_game_consumers_have_locale_subscription_or_dictionary(self):
        consumers = [
            'src/client/world/HouseSocketPromptController.luau',
            'src/client/world/HouseFireplaceController.luau',
            'src/client/world/FloatingResourceFeedback.luau',
            'src/client/weapon/WeaponSelectionController.luau',
            'src/client/combat/HealthBarView.luau',
            'src/client/character/DeathRespawnController.luau',
        ]
        for file in consumers:
            self.assertIn('Language', (ROOT / file).read_text(encoding='utf-8'), file)
        text = (ROOT / 'src/client/localization/LanguageState.luau').read_text(encoding='utf-8')
        self.assertIn('DescendantAdded:Connect(watch)', text)
        self.assertIn('item:GetPropertyChangedSignal("Text")', text)
        self.assertIn('item.AutoLocalize = false', text)
        self.assertIn('changed:Fire(locale)', text)

    def test_server_preference_never_grants_gameplay_authority(self):
        text = (ROOT / 'src/server/localization/PlayerLanguageService.luau').read_text(encoding='utf-8')
        self.assertIn('Contract.IsSupported(value)', text)
        self.assertIn('Game1PlayerLanguage_v1', text)
        self.assertIn('selectedDuringLoad[player]', text)
        self.assertIn('pcall(function()', text)
        self.assertNotIn('CharacterService', text)
        self.assertIn('critical = false', (ROOT / 'src/server/bootstrap/ServiceCatalog.luau').read_text())

    def test_registered_world_names_are_stable_localization_keys(self):
        actors = self.catalog['groups']['actors']
        items = self.catalog['groups']['items']
        for slug in ('guard_01', 'guard_02', 'warsmith', 'gremlin'):
            self.assertIn('actors.' + slug, actors)
        for slug in ('newbie_bow', 'newbie_dagger', 'newbie_axe', 'newbie_saber_01',
                     'newbie_sword_01', 'dragon_divider', 'guards_sword_01', 'warsmiths_hummer_01'):
            self.assertIn('items.' + slug, items)


if __name__ == '__main__':
    unittest.main()
