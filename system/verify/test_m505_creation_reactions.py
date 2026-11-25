"""M505: strict settings, migration and preview-only integration. Engine smoke is separate."""
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.character_creation_settings import DEFAULTS, REACTION_GROUPS, normalize_character_creation
from options_store import OptionsStore


def read(path):
    return (ROOT / path).read_text(encoding='utf8')


class CreationReactionTests(unittest.TestCase):
    def test_settings_are_bounded_and_all_groups_present(self):
        self.assertEqual(REACTION_GROUPS, ('atk','bow','clap','hi','laugh','sad','sp_wait','unaware','victory','waiting','yes'))
        default = DEFAULTS['animations']
        self.assertEqual(default['chancePercent'], 35)
        self.assertEqual(set(default['weights']), set(REACTION_GROUPS))
        for value in (-1, 101, 2.5, True, float('nan'), '35'):
            for target in ('chancePercent', 'weight'):
                changed = deepcopy(default)
                if target == 'chancePercent': changed[target] = value
                else: changed['weights']['bow'] = value
                with self.subTest(value=value, target=target), self.assertRaises(ValueError):
                    normalize_character_creation({'animations': changed})
        for key in ('bow', 'dance'):
            changed = deepcopy(default)
            if key == 'bow': changed['weights'].pop(key)
            else: changed['weights'][key] = 100
            with self.assertRaises(ValueError): normalize_character_creation({'animations': changed})

    def test_real_manifest_upgrade_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'assets/manifests'; folder.mkdir(parents=True)
            before = json.loads(read('assets/manifests/options.json'))
            before['characterCreation'].pop('animations', None)
            before['characterCreation']['spawnPoints']['male']['position'] = [1, 2, 3]
            path = folder/'options.json'; path.write_text(json.dumps(before))
            original = path.read_bytes()
            (folder/'location-assets.json').write_text(read('assets/manifests/location-assets.json'))
            store = OptionsStore(root)
            expected = deepcopy(before['characterCreation']); expected['animations'] = DEFAULTS['animations']
            self.assertEqual(store.snapshot()['characterCreation'], expected)
            backups = list(folder.glob('options.json.pre-m505-*.bak'))
            self.assertEqual(len(backups), 1); self.assertEqual(backups[0].read_bytes(), original)
            custom = deepcopy(DEFAULTS['animations']); custom['chancePercent'] = 100; custom['weights']['unaware'] = 0
            updated = store.update({'characterCreation': {'animations': custom}})
            expected['animations'] = custom
            self.assertEqual(updated['characterCreation'], expected)
            self.assertEqual(OptionsStore(root).snapshot(), updated)
            self.assertEqual(len(list(folder.glob('options.json.pre-m505-*.bak'))), 1)
            registry = (root/'src/shared/GameOptionsRegistry.luau').read_text()
            self.assertIn('chancePercent = 100', registry); self.assertIn('unaware = 0', registry)

    def test_runtime_wiring_and_lifecycle(self):
        base = 'src/client/character/'
        code = read(base+'CharacterCreationController.luau')
        self.assertIn('reactionPending[selected] = true', code)
        self.assertIn('if stage == "creation" and selected == id then preview:React(id) end', code)
        self.assertEqual(code.count('react(selected)'), 3)
        self.assertIn('function() return selected, stage == "creation" end', code)
        reaction = read(base+'CharacterCreationReactions.luau')
        self.assertIn('Merge.Rows', reaction)
        self.assertIn('group == "bow" and archetype ~= "human_female"', reaction)
        self.assertIn('rng:NextInteger(1, #entry.rows)', reaction)
        self.assertIn('track.Looped = false', reaction)
        self.assertIn('track.Ended:Connect', reaction)
        preview = read(base+'CharacterCreationPreviewController.luau')
        self.assertIn('self.reactions:Remove(previous)', preview)
        self.assertIn('self.reactions:Destroy()', preview)

    def test_compact_sections_closed_and_inputs_unique(self):
        class Parser(HTMLParser):
            def __init__(self): super().__init__(); self.sections=[]; self.ids=[]
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                if tag=='details' and 'game1-creation-subsection' in attrs.get('class',''):
                    self.sections.append(attrs)
                if 'id' in attrs: self.ids.append(attrs['id'])
        p=Parser(); p.feed(read('system/control-center/static/index.html'))
        self.assertEqual(len(p.sections), 6)
        self.assertTrue(all('open' not in s for s in p.sections))
        for key in ('chance', *REACTION_GROUPS):
            self.assertEqual(p.ids.count('option-creation-animation-'+key), 1)

if __name__ == '__main__': unittest.main()
