"""M462: new social actions are gender-symmetric and use one runtime registry."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from animation_core.common import (
    SOCIAL_SLOT_CATALOG, classify_animation, filename_rule_catalog,
    normalize_manual_binding, social_slots_for,
)
from animation_store import AnimationStore
from sqlite_connection import connect

EXPECTED = {'waiting', 'clap', 'atk', 'victory', 'yes', 'bow', 'laugh', 'hi', 'sad', 'dance', 'no', 'sp_wait', 'unaware'}
ADDED = {'yes', 'bow', 'laugh', 'hi'}


class SocialActionsM462(unittest.TestCase):
    def test_one_shot_catalog_and_filename_aliases_for_both_genders(self):
        self.assertEqual({r['slot'] for r in SOCIAL_SLOT_CATALOG}, EXPECTED)
        for gender in ('male', 'female'):
            character = 'human_' + gender
            self.assertEqual({r['slot'] for r in social_slots_for(character, gender)}, EXPECTED)
            rules = {r['state']: r for r in filename_rule_catalog(character) if r['scope'] == 'social'}
            self.assertEqual(set(rules), EXPECTED)
            for slot in ADDED | {'clap'}:
                self.assertEqual(rules[slot]['canonicalFilename'], f'{character}_social_{slot}_01.rbxm')
                for ext in ('.rbxm', '.rbxmx'):
                    binding = classify_animation(Path(f'{character}_social_{slot}_01{ext}'), character)
                    self.assertEqual((binding['scope'], binding['slot'], binding['variant']),
                                     ('social', slot, 1))
                    self.assertEqual((binding['looped'], binding['priority']), (False, 'Action'))
                manual = normalize_manual_binding('social', '', slot)
                self.assertEqual((manual['slot'], manual['variant']), (slot, 1))

    def test_registration_and_published_registry_are_per_gender(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / '.control-center/game1.db'
            db.parent.mkdir(parents=True)
            with connect(db) as connection:
                connection.execute('CREATE TABLE characters(id TEXT PRIMARY KEY, display_name TEXT, race TEXT, '
                                   'gender TEXT, skeleton_signature TEXT, visual_mode TEXT)')
                for gender in ('male', 'female'):
                    connection.execute('INSERT INTO characters VALUES (?,?,?,?,?,?)',
                                       ('human_' + gender, 'human ' + gender, 'human', gender,
                                        gender + '-rig', 'assembly'))
            store = AnimationStore(root)
            inbox = root / 'incoming'
            inbox.mkdir()
            for gender in ('male', 'female'):
                character = 'human_' + gender
                for slot in ADDED:
                    (inbox / f'{character}_social_{slot}_01.rbxm').write_bytes(
                        f'{gender}:{slot}'.encode('utf8'))
                review = store.preview_folder(character, str(inbox))
                owned = [item for item in review['items'] if item['ownerCharacterId'] == character]
                self.assertEqual({item['slot'] for item in owned}, ADDED)
                self.assertEqual(store.register_selected(character, str(inbox), owned)['count'], 4)
                self.assertEqual({item['status'] for item in store.snapshot(character)['items']}, {'LOCAL_ONLY'})
            registry_path = root / 'src/shared/character/CharacterAnimationRegistry.luau'
            registry = registry_path.read_text(encoding='utf8')
            for gender in ('male', 'female'):
                for slot in ADDED:
                    self.assertNotIn(f'human_{gender}__social__{slot}__01', registry)
            # Emulate *metadata* of an approved asset (no actual Roblox upload).
            with store.connect() as connection:
                for gender in ('male', 'female'):
                    for index, clip in enumerate(store.snapshot('human_' + gender)['items']):
                        connection.execute('UPDATE animation_clips SET asset_id=?,published_sha256=sha256 WHERE id=?',
                                           (str((1 if gender == 'male' else 2) * 100000 + index), clip['clip_id']))
            store.export()
            registry = registry_path.read_text(encoding='utf8')
            for gender in ('male', 'female'):
                for slot in ADDED:
                    self.assertIn(f'human_{gender}__social__{slot}__01', registry)
            self.assertIn('rbxassetid://100000', registry)
            self.assertIn('rbxassetid://200000', registry)

    def test_client_resolves_social_from_registry_without_hardcoded_slot_whitelist(self):
        source = (ROOT / 'src/client/character/animation/SocialAnimationPlayback.luau').read_text(encoding='utf8')
        self.assertIn('Resolver.Resolve(character, "social", nil, slot)', source)
        self.assertNotIn('slot ~= "waiting_01"', source)
        self.assertIn('track.Looped = false', source)


if __name__ == '__main__':
    unittest.main()
