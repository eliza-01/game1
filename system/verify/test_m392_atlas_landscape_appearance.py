"""M392: retired atlas names are reusable; Painter attachments are appearance-only."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import sys
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.texture_atlas_registry import AtlasRegistry
from services.place_registry.catalog import validate_report


class AtlasKeyReuse(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.control-center').mkdir()
        self.store = AtlasRegistry(self.root)
        self.source = self.root / 'lantern_03_16x16_atlas.png'

    def put(self, color):
        Image.new('RGB', (16, 16), color).save(self.source)

    def test_retirement_reuse_preserves_publication_and_creates_new_variant(self):
        self.put('red')
        old = self.store.register_file(str(self.source))
        with self.store.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       ('139928560438135', old['id']))
        self.store.retire_variant(old['id'], token=self.store.retirement_plan(old['id'])['token'])
        self.put('green')
        latest = self.store.register_file(str(self.source))
        self.assertNotEqual(old['id'], latest['id'])
        self.assertNotEqual(old['source_path'], latest['source_path'])
        self.assertTrue((self.root / old['source_path']).exists())
        self.assertTrue((self.root / latest['source_path']).exists())
        self.assertTrue(self.store.get_variant(old['id'])['retired'])
        self.assertEqual(self.store.get_variant(old['id'])['published_id'], '139928560438135')
        self.assertEqual(self.store.catalog()[0]['variants'][0]['id'], latest['id'])
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.store.bind('location_asset', 'lantern_03', old['id'])
        with self.store.connect() as db:
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(AtlasRegistry(self.root).get_variant(latest['id'])['id'], latest['id'])

    def test_unique_active_resolution_and_idempotent_registration(self):
        self.put('red')
        original = self.store.register_file(str(self.source))
        self.assertEqual(original['id'], self.store.register_file(str(self.source))['id'])
        self.put('green')
        replacement = self.store.register_file(str(self.source))
        self.assertEqual(original['id'], replacement['id'])
        self.assertTrue(replacement['replacementPending'])

    def test_migrate_unconditional_unique_without_losing_history(self):
        # Restore an actual legacy UNIQUE layout in an isolated fresh SQLite DB.
        with self.store.connect() as db:
            db.execute('DROP INDEX ux_texture_atlas_active_resolution')
            # A schema copy like historical M223, on which the active index
            # cannot be created until the old unique table has been retired.
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('ALTER TABLE texture_atlas_variants RENAME TO atlas_m392_temporary')
            db.execute('''CREATE TABLE texture_atlas_variants (
                id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL,
                width INTEGER NOT NULL,height INTEGER NOT NULL,
                filename TEXT NOT NULL,original_filename TEXT NOT NULL,
                source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,
                uses_alpha INTEGER NOT NULL,published_id TEXT,
                published_sha256 TEXT NOT NULL DEFAULT '',
                moderation_state TEXT NOT NULL DEFAULT '',
                published_at REAL,created_at REAL NOT NULL,retired_at REAL,
                UNIQUE(family_id,width,height))''')
            db.execute('DROP TABLE atlas_m392_temporary')
        self.put('red')
        first = self.store.register_file(str(self.source))
        with self.store.connect() as db:
            db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                       ('555', first['id']))
        AtlasRegistry(self.root)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT published_id FROM texture_atlas_variants WHERE id=?',
                                        (first['id'],)).fetchone()[0], '555')
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertTrue(any(row['name']=='ux_texture_atlas_active_resolution'
                                for row in db.execute('PRAGMA index_list(texture_atlas_variants)')))
        self.assertTrue(list((self.root / '.control-center/backups').glob('before_atlas_key_reuse_m392_*.db')))


class PainterAppearanceContract(unittest.TestCase):
    def test_reject_forged_external_authority(self):
        catalog = {'items': [{'slug': 'lantern_03'}]}
        base = {'kind':'landscape_attachment','slug':'lantern_03','key':'x1',
                'name':'lantern_03_123','path':'Workspace.Game1LandscapeDecor.Attachments.lantern_03_123',
                'ownerPath':'Workspace.Game1LandscapeDecor.Attachments.lantern_03_123',
                'authorSlug':'lantern_03','branchStrokeId':'b1','anchorKind':'stem',
                'reason':'LandscapePainter authored attachment','review':False,
                'protectedFromRuntime':True,'canSync':True,'needsTexture':True}
        report = {'schemaVersion': 1,'placements':[],'protected':[base]}
        self.assertEqual(validate_report(report,catalog),[])
        for change in ({'kind':'landscape_structure'}, {'review':True}, {'slug':''},
                       {'authorSlug':'unrelated'}, {'needsTexture':False}, {'key':''}):
            modified = dict(base,**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_report({**report,'protected':[modified]},catalog)

    def test_painter_sync_is_appearance_only_and_reuses_shared_binder(self):
        plugin = ROOT / 'system/studio-plugin/modules'
        scan = (plugin/'StudioPlaceRegistryInventory.luau').read_text(encoding='utf-8')
        sync = (plugin/'StudioPlaceRegistrySync.luau').read_text(encoding='utf-8')
        js = (ROOT/'system/control-center/static/place-registry.js').read_text(encoding='utf-8')
        self.assertIn('History.MatchesInventory(external.model,version)', scan)
        self.assertIn('ref.external', sync)
        branch = sync.split('if item.external then',1)[1].split('elseif item.swap',1)[0]
        self.assertIn('Visual.Apply(snapshot.mesh,row)', branch)
        self.assertIn('Visual.AssertCurrent(snapshot.mesh,row)', branch)
        for forbidden in ('RigSwap.Commit','Destroy()', 'SetAttribute("Landscape'):
            self.assertNotIn(forbidden, branch)
        self.assertIn('LandscapePainter attachments', js)
        self.assertIn('...eligibleExternal().map(p=>p.key)', js)


if __name__ == '__main__':
    unittest.main()
