"""M463: social_sad is a gender-symmetric one-shot, distinct from facial emotions.sad."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from animation_core.common import (
    EMOTION_SLOT_CATALOG, SOCIAL_SLOT_CATALOG, classify_animation,
    filename_rule_catalog, normalize_manual_binding, social_slots_for,
)
from animation_store import AnimationStore
from sqlite_connection import connect


class SocialSadM463(unittest.TestCase):
    def test_social_sad_has_both_genders_and_does_not_override_facial_sad(self):
        self.assertIn('sad', {r['slot'] for r in EMOTION_SLOT_CATALOG})
        sad = next(r for r in SOCIAL_SLOT_CATALOG if r['slot'] == 'sad')
        self.assertEqual((sad['group'], sad['priority'], sad['looped'], sad['variants']),
                         ('social', 'Action', False, True))
        for gender in ('male', 'female'):
            character = 'human_' + gender
            self.assertIn('sad', {r['slot'] for r in social_slots_for(character, gender)})
            rules = {(r['scope'], r['state']): r for r in filename_rule_catalog(character)}
            self.assertEqual(rules[('social', 'sad')]['canonicalFilename'],
                             f'{character}_social_sad_01.rbxm')
            self.assertNotEqual(rules[('social', 'sad')]['canonicalFilename'],
                                rules[('emotions', 'sad')]['canonicalFilename'])
            for extension in ('.rbxm', '.rbxmx'):
                binding = classify_animation(Path(f'{character}_social_sad_01{extension}'), character)
                self.assertEqual((binding['scope'], binding['slot'], binding['variant']),
                                 ('social', 'sad', 1))
                self.assertEqual((binding['looped'], binding['priority']), (False, 'Action'))
            self.assertEqual(normalize_manual_binding('social', '', 'sad')['slot'], 'sad')

    def test_local_sad_is_not_published_until_asset_id_assigned(self):
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
            incoming = root / 'incoming'
            incoming.mkdir()
            for gender in ('male', 'female'):
                character = 'human_' + gender
                (incoming / f'{character}_social_sad_01.rbxm').write_bytes(character.encode())
                preview = store.preview_folder(character, str(incoming))
                owned = [row for row in preview['items'] if row['ownerCharacterId'] == character]
                self.assertEqual([(r['scope'], r['slot']) for r in owned],
                                 [('social', 'sad')])
                self.assertEqual(store.register_selected(character, str(incoming), owned)['count'], 1)
                self.assertEqual(store.snapshot(character)['items'][0]['status'], 'LOCAL_ONLY')
            registry_path = root / 'src/shared/character/CharacterAnimationRegistry.luau'
            registry = registry_path.read_text(encoding='utf8')
            self.assertNotIn('human_male__social__sad__01', registry)
            self.assertNotIn('human_female__social__sad__01', registry)
            with store.connect() as connection:
                for gender, aid in (('male', '111111'), ('female', '222222')):
                    clip = store.snapshot('human_' + gender)['items'][0]
                    connection.execute('UPDATE animation_clips SET asset_id=?,published_sha256=sha256 WHERE id=?',
                                       (aid, clip['clip_id']))
            store.export()
            registry = registry_path.read_text(encoding='utf8')
            for gender, aid in (('male', '111111'), ('female', '222222')):
                self.assertIn(f'human_{gender}__social__sad__01', registry)
                self.assertIn('rbxassetid://' + aid, registry)


if __name__ == '__main__':
    unittest.main()
