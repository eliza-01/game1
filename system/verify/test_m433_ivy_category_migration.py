"""M433 · Category options, migration and authoring/plugin consumers."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.location_asset_taxonomy import CATEGORIES


class IvyCategoryM433(TestCase):
    def test_new_category_reaches_api_editor_and_studio(self):
        with TemporaryDirectory() as tmp:
            store = LocationAssetStore(Path(tmp))
            self.assertIn('ivy', CATEGORIES)
            self.assertIn({'id': 'ivy', 'label': 'Ivy', 'group': 'flora'},
                          store.options()['categories'])
            self.assertIn('ivy', [c['id'] for c in store.options()['categoryGroups'][0]['categories']])
            with store.connect() as db:
                db.execute("""INSERT INTO location_assets
                    (slug,name_en,category,created_at,updated_at)
                    VALUES ('ivy_08','Ivy 08','ivy',1,1)""")
            self.assertEqual(store.get('ivy_08')['category_label'], 'Ivy')
            store.export()
            generated=(Path(tmp)/'src/shared/world/LocationAssetRegistry.luau').read_text('utf-8')
            self.assertIn('category = "ivy"',generated)

        manager = (ROOT/'system/studio-plugin/modules/DecoManager.luau').read_text('utf-8')
        placement = (ROOT/'system/studio-plugin/modules/DecoPlacement.luau').read_text('utf-8')
        index = (ROOT/'system/control-center/static/index.html').read_text('utf-8')
        self.assertIn('"bush", "ivy", "flower"', manager)
        self.assertIn('ivy="Ivy"', manager)
        self.assertIn('navHost.Position = UDim2.new(0, 12, 0, 213)', manager)
        self.assertIn('self.viewport.Position = UDim2.new(0, 12, 0, 261)', manager)
        self.assertIn('ivy = "Ivy"', placement)
        self.assertIn('Flora · tree · bush · ivy · flower · leaf · rock', index)

    def test_upgrade_is_idempotent_preserves_identity_published_sources_and_history(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=LocationAssetStore(root)
            slugs=('ivy_02','ivy_03','ivy_05')
            with original.connect() as db:
                for index, slug in enumerate(slugs, start=2):
                    db.execute("""INSERT INTO location_assets
                        (slug,name_en,category,model_path,model_sha256,model_asset_id,
                         model_published_sha256,revision,created_at,updated_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (slug, f'Ivy {index}', 'bush',
                         f'assets/source/location-assets/bush/{slug}/model/{slug}.fbx',
                         f'sha{index}', f'123456{index}', f'sha{index}', index, 1, 1))
                    db.execute("""INSERT INTO location_asset_publications
                        (asset_slug,kind,revision,asset_id,operation_path,sha256,published_at)
                        VALUES (?,?,?,?,?,?,?)""",
                        (slug,'model',index,f'123456{index}','kept',f'sha{index}',1))
                db.execute("""INSERT INTO location_assets
                    (slug,name_en,category,created_at,updated_at)
                    VALUES ('bush_01','Bush 01','bush',1,1),
                           ('ivy_future','Ivy Future','bush',1,1)""")
            with original.connect() as db:
                before={row['slug']: dict(row) for row in db.execute(
                    'SELECT * FROM location_assets')}
                history=[tuple(row) for row in db.execute(
                    'SELECT asset_slug,kind,revision,asset_id,sha256 FROM location_asset_publications ORDER BY id')]
            migrated=LocationAssetStore(root)
            with migrated.connect() as db:
                after={row['slug']: dict(row) for row in db.execute(
                    'SELECT * FROM location_assets')}
                self.assertEqual(history,[tuple(row) for row in db.execute(
                    'SELECT asset_slug,kind,revision,asset_id,sha256 FROM location_asset_publications ORDER BY id')])
            for slug in slugs:
                self.assertEqual(after[slug]['category'], 'ivy')
                self.assertEqual(after[slug]['revision'], before[slug]['revision']+1)
                for key in before[slug]:
                    if key not in ('category','revision','updated_at'):
                        self.assertEqual(after[slug][key],before[slug][key],(slug,key))
            for slug in ('bush_01','ivy_future'):
                self.assertEqual(after[slug], before[slug])
            backups=list((root/'.control-center/backups').glob('location_ivy_category_pre_m433_*.sqlite'))
            self.assertEqual(len(backups),1)
            from sqlite_connection import connect as sqlite_connect
            with sqlite_connect(backups[0]) as db:
                self.assertEqual(db.execute(
                    "SELECT category FROM location_assets WHERE slug='ivy_02'").fetchone()[0], 'bush')
            generated=(root/'src/shared/world/LocationAssetRegistry.luau').read_text('utf-8')
            for slug in slugs:
                self.assertIn(f'["{slug}"]',generated)
            self.assertEqual(generated.count('category = "ivy"'),3)
            LocationAssetStore(root)
            self.assertEqual(len(list((root/'.control-center/backups').glob('location_ivy_category_pre_m433_*.sqlite'))),1)
            with migrated.connect() as db:
                self.assertEqual({row['slug']: dict(row) for row in db.execute(
                    'SELECT * FROM location_assets')}, after)

    def test_empty_project_never_creates_migration_backup(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            LocationAssetStore(root)
            self.assertFalse(list((root/'.control-center/backups').glob('location_ivy_category_pre_m433_*.sqlite')))
