"""M460: all social actions are shared semantics with per-gender animation assets."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from animation_store import AnimationStore
from sqlite_connection import connect
from animation_core.common import (
    SOCIAL_SLOT_CATALOG, classify_animation, filename_rule_catalog,
    normalize_manual_binding, social_slots_for,
)


class SocialGenderParityM460(unittest.TestCase):
    def test_all_social_slots_have_distinct_male_and_female_source_names(self):
        canonical = {item['slot'] for item in SOCIAL_SLOT_CATALOG}
        self.assertEqual(canonical, {'waiting_a', 'clap', 'atk', 'victory', 'yes', 'bow', 'laugh', 'hi', 'sad'})
        names = set()
        for gender in ('male', 'female'):
            character_id = 'human_' + gender
            slots = {item['slot'] for item in social_slots_for(character_id, gender)}
            self.assertEqual(slots, canonical)
            rules = [r for r in filename_rule_catalog(character_id) if r['scope'] == 'social']
            self.assertEqual({r['state'] for r in rules}, canonical)
            for item in rules:
                filename = item['canonicalFilename']
                self.assertNotIn(filename, names)
                names.add(filename)
                self.assertEqual(filename, f'{character_id}_social_{item["state"]}.rbxm')
                clip = classify_animation(Path(filename), character_id)
                self.assertEqual((clip['scope'], clip['slot'], clip['variant']),
                                 ('social', item['state'], 0))
                self.assertFalse(clip['looped'])
                self.assertEqual(clip['priority'], 'Action')
                self.assertEqual(normalize_manual_binding('social', '', item['state'])['slot'], item['state'])
        self.assertEqual(len(names), 2 * len(canonical))

    def test_published_male_and_female_clips_keep_independent_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / '.control-center' / 'game1.db'
            db.parent.mkdir(parents=True)
            with connect(db) as connection:
                connection.execute(
                    'CREATE TABLE characters(id TEXT PRIMARY KEY, display_name TEXT, race TEXT, '
                    'gender TEXT, skeleton_signature TEXT, visual_mode TEXT)'
                )
                for gender in ('male', 'female'):
                    connection.execute('INSERT INTO characters VALUES (?,?,?,?,?,?)',
                                       ('human_' + gender, 'Human ' + gender, 'human',
                                        gender, gender + '-rig', 'assembly'))
            store = AnimationStore(root)
            folder = root / 'incoming'
            folder.mkdir()
            for gender in ('male', 'female'):
                for slot in ('atk', 'victory'):
                    (folder / f'human_{gender}_social_{slot}.rbxm').write_bytes(
                        f'{gender}:{slot}'.encode('ascii'))
            for gender in ('male', 'female'):
                character = 'human_' + gender
                review = store.preview_folder(character, str(folder))
                self.assertEqual({r['slot'] for r in review['items']}, {'atk', 'victory'})
                self.assertEqual(store.register_selected(character, str(folder), review['items'])['count'], 2)
                clips = store.snapshot(character)['items']
                self.assertEqual({r['status'] for r in clips}, {'LOCAL_ONLY'})
                with store.connect() as connection:
                    for index, clip in enumerate(clips):
                        # Simulates publication metadata, not a real Roblox upload.
                        asset_id = str((1 if gender == 'male' else 2) * 100000 + index)
                        connection.execute(
                            'UPDATE animation_clips SET asset_id=?,published_sha256=sha256 WHERE id=?',
                            (asset_id, clip['clip_id']))
            store.export()
            registry = (root / 'src/shared/character/CharacterAnimationRegistry.luau').read_text(encoding='utf8')
            for gender in ('male', 'female'):
                for slot in ('atk', 'victory'):
                    self.assertIn(f'human_{gender}__social__{slot}__00', registry)
            for animation_id in ('100000', '100001', '200000', '200001'):
                self.assertIn('rbxassetid://' + animation_id, registry)

    def test_new_social_actions_inherit_both_genders_without_exceptions(self):
        # A future catalog entry must not require modifications to a gender whitelist.
        novel = {'group': 'social', 'slot': 'test_new_social', 'label': 'test',
                 'looped': False, 'priority': 'Action', 'variants': False}
        SOCIAL_SLOT_CATALOG.append(novel)
        try:
            for gender in ('male', 'female'):
                self.assertIn('test_new_social',
                              {item['slot'] for item in social_slots_for('human_' + gender, gender)})
                self.assertIn('test_new_social',
                              {item['state'] for item in filename_rule_catalog('human_' + gender)
                               if item['scope'] == 'social'})
        finally:
            SOCIAL_SLOT_CATALOG.pop()


if __name__ == '__main__':
    unittest.main()
