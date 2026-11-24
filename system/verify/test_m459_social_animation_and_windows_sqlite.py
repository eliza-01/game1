"""M459: social clips share one authoring/runtime pipeline; Windows backup handles close."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from animation_core.common import classify_animation, filename_rule_catalog, normalize_manual_binding
from animation_store import AnimationStore
from sqlite_connection import connect


class SocialAuthoringM459(unittest.TestCase):
    def test_social_filenames_are_symmetric_for_both_genders(self):
        for gender, expected in (
            ('male', ('waiting', 'clap', 'atk', 'victory', 'yes', 'bow', 'laugh', 'hi', 'sad', 'dance', 'no', 'sp_wait', 'unaware')),
            ('female', ('waiting', 'clap', 'atk', 'victory', 'yes', 'bow', 'laugh', 'hi', 'sad', 'dance', 'no', 'sp_wait', 'unaware')),
        ):
            rules = [x for x in filename_rule_catalog('human_' + gender) if x['scope'] == 'social']
            self.assertEqual({row['state'] for row in rules}, set(expected))
            for row in rules:
                self.assertEqual(row['canonicalFilename'], 'human_' + gender + '_social_' + row['state'] + '_01.rbxm')
                for suffix in ('.rbxm', '.rbxmx'):
                    binding = classify_animation(Path(row['canonicalFilename']).with_suffix(suffix), 'human_' + gender)
                    self.assertEqual((binding['scope'], binding['slot'], binding['variant']), ('social', row['state'], 1))
                    self.assertFalse(binding['looped'])
                    self.assertEqual(binding['priority'], 'Action')
        self.assertIsNone(classify_animation(Path('human_male_social_unknown.rbxm'), 'human_male'))
        self.assertEqual(classify_animation(Path('human_female_social_atk_01.rbxm'), 'human_female')['slot'], 'atk')
        with self.assertRaisesRegex(ValueError, 'unknown social animation slot'):
            normalize_manual_binding('social', '', 'attack')

    def test_real_store_scan_register_and_publish_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dbfile = root / '.control-center/game1.db'
            dbfile.parent.mkdir(parents=True)
            with connect(dbfile) as db:
                db.execute('CREATE TABLE characters(id TEXT PRIMARY KEY, display_name TEXT, race TEXT, gender TEXT, skeleton_signature TEXT, visual_mode TEXT)')
                db.execute('INSERT INTO characters VALUES (?,?,?,?,?,?)', ('human_male','Human Male','human','male','test-signature','assembly'))
                db.execute('INSERT INTO characters VALUES (?,?,?,?,?,?)', ('human_female','Human Female','human','female','female-signature','assembly'))
            store = AnimationStore(root)
            for gender in ('male', 'female'):
                data = store.snapshot('human_' + gender)
                self.assertIn('social', data['slotCatalog'])
                self.assertEqual(len(data['slotCatalog']['social']), 13)
                self.assertEqual(data['items'], [])
            inbox = root / 'inbox'
            inbox.mkdir()
            for name in ('human_male_social_waiting_01.rbxm', 'human_male_social_victory_01.rbxmx',
                         'human_female_social_clap_01.rbxm', 'human_female_social_atk_01.rbxm',
                         'human_female_social_victory_01.rbxmx'):
                (inbox / name).write_bytes(b'fixture animation source')
            male_review = store.preview_folder('human_male', str(inbox))
            self.assertEqual(male_review['recognized'], 5)
            self.assertEqual({row['ownerCharacterId'] for row in male_review['items']},
                             {'human_male', 'human_female'})
            male_items = [row for row in male_review['items'] if row['ownerCharacterId']=='human_male']
            male_outcome = store.register_selected('human_male', str(inbox), male_items)
            self.assertEqual(male_outcome['count'], 2)
            female_review = store.preview_folder('human_female', str(inbox))
            female_items = [row for row in female_review['items'] if row['ownerCharacterId']=='human_female']
            self.assertEqual({row['slot'] for row in female_items}, {'clap','atk','victory'})
            self.assertEqual(store.register_selected('human_female', str(inbox), female_items)['count'], 3)
            self.assertTrue((root / 'assets/source/characters/human/male/human_male/animations/social/social_waiting_01.rbxm').exists())
            clips = store.snapshot('human_male')['items']
            self.assertEqual({row['scope'] for row in clips}, {'social'})
            self.assertEqual({row['status'] for row in clips}, {'LOCAL_ONLY'})
            # Unpublished source must not be written as an executable animation.
            registry = (root / 'src/shared/character/CharacterAnimationRegistry.luau').read_text(encoding='utf8')
            self.assertIn('social = table.freeze({', registry)
            self.assertNotIn('human_male__social__waiting__01', registry)
            with store.connect() as db:
                db.execute("UPDATE animation_clips SET asset_id='123456789',published_sha256=sha256 WHERE id=?",
                           (next(c['clip_id'] for c in clips if c['slot'] == 'waiting'),))
            store.export()
            registry = (root / 'src/shared/character/CharacterAnimationRegistry.luau').read_text(encoding='utf8')
            self.assertIn('human_male__social__waiting__01', registry)
            self.assertIn('rbxassetid://123456789', registry)
            self.assertNotIn('human_male__social__victory__01', registry)
            self.assertIn('skeletonSignature = "test-signature"', registry)

    def test_m458_sqlite_backup_closing_contract(self):
        source = (ROOT / 'system/verify/test_m458_armor_gender_pair_readiness.py').read_text(encoding='utf8')
        self.assertIn('with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(dbfile)) as target:', source)
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / 'source.db'
            dst = Path(temp) / 'copy.db'
            with closing(sqlite3.connect(src)) as db:
                db.execute('CREATE TABLE t(id INTEGER)')
                db.commit()
            with closing(sqlite3.connect(src)) as origin, closing(sqlite3.connect(dst)) as target:
                origin.backup(target)
            src.unlink()
            dst.unlink()
            self.assertFalse(src.exists())

    def test_runtime_consumers_cover_social(self):
        resolver = (ROOT / 'src/client/character/animation/AnimationResolver.luau').read_text(encoding='utf8')
        stands = (ROOT / 'src/shared/character/CharacterStandAnimationCatalog.luau').read_text(encoding='utf8')
        helper = (ROOT / 'src/client/character/animation/SocialAnimationPlayback.luau').read_text(encoding='utf8')
        self.assertIn('scope == "social"', resolver)
        self.assertIn('{ "base", "emotions", "social" }', resolver)
        self.assertIn('"social"', stands)
        self.assertIn('Resolver.Resolve(character, "social", nil, slot)', helper)
        self.assertIn('Social.new(character: Model, cache: any)', helper)
        self.assertIn('function Social:Destroy()', helper)
        self.assertNotIn('FireServer', helper)


if __name__ == '__main__':
    unittest.main()
