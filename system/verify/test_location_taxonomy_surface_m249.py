"""M249: ordered categories and semantic/physical surface contracts."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from location_asset_store import LocationAssetStore
from services import location_asset_taxonomy as taxonomy
from services.place_registry.catalog import build_catalog


class LocationTaxonomySurfaceM249(TestCase):
    def test_groups_are_stable_singular_and_complete(self):
        self.assertEqual([group[0] for group in taxonomy.CATEGORY_GROUPS], ['flora','structure','prop'])
        self.assertEqual(taxonomy.CATEGORIES, (
            'tree','bush','flower','rock','light','fence','ladder','bridge','pillar','post',
            'prop','decoration','building'))
        opts=taxonomy.options()
        self.assertEqual(len(opts['categories']), len(set(c['id'] for c in opts['categories'])))
        self.assertEqual([len(group['categories']) for group in opts['categoryGroups']], [4,6,3])
        self.assertEqual([m['id'] for m in opts['surfaceMaterials']],list(taxonomy.MATERIAL_BY_ID))
        self.assertEqual(taxonomy.MATERIAL_BY_ID['foliage']['soundFamily'],'foliage')
        self.assertEqual(taxonomy.MATERIAL_BY_ID['wood']['robloxMaterial'],'Wood')

    def test_new_database_schema_and_material_default(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); store=LocationAssetStore(root)
            self.assertEqual(store.snapshot()['schemaVersion'],5)
            with store.connect() as db:
                columns={row[1] for row in db.execute('PRAGMA table_info(location_assets)')}
                self.assertIn('surface_material',columns)
                db.execute('''INSERT INTO location_assets(slug,name_en,category,revision,created_at,updated_at)
                    VALUES('wooden_post','Wooden Post','post',1,1,1)''')
            self.assertEqual(store.get('wooden_post')['surfaceMaterial'],'default')
            self.assertEqual(store.options()['categories'][9]['id'],'post')
            changed=store.rename_identity('wooden_post',{
                'slug':'wooden_post', 'nameEn':'Wooden Post', 'category':'post',
                'surfaceMaterial':'wood', 'destructible':False, 'expectedRevision':1})
            self.assertEqual(changed['surfaceMaterial'],'wood')
            self.assertEqual(changed['materialDefinition']['robloxMaterial'],'Wood')
            self.assertEqual(changed['materialDefinition']['soundFamily'],'wood')
            generated=(root/'src/shared/world/LocationAssetRegistry.luau').read_text('utf-8')
            self.assertIn('surfaceMaterial = "wood"',generated)
            self.assertIn('robloxMaterial = "Wood"',generated)
            self.assertIn('soundFamily = "wood"',generated)
            # Older clients do not reset a material when omitting the new field.
            renamed=store.rename_identity('wooden_post',{
                'slug':'post_01','nameEn':'Post 01', 'category':'post',
                'destructible':False,'expectedRevision':2})
            self.assertEqual(renamed['surfaceMaterial'],'wood')
            self.assertEqual(store.aliases_for('post_01'),['wooden_post'])

    def test_additive_upgrade_preserves_existing_asset_ids(self):
        import sqlite3
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=root/'.control-center';directory.mkdir()
            with sqlite3.connect(directory/'game1.db') as db:
                db.execute("""CREATE TABLE location_assets (
                    slug TEXT PRIMARY KEY,name_en TEXT NOT NULL,category TEXT NOT NULL,
                    model_path TEXT NOT NULL DEFAULT '',model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,model_published_sha256 TEXT NOT NULL DEFAULT '',
                    model_moderation_state TEXT NOT NULL DEFAULT '',destructible INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,published_at REAL,
                    mesh_options_json TEXT NOT NULL DEFAULT '{}')""")
                db.execute("""INSERT INTO location_assets(slug,name_en,category,model_asset_id,created_at,updated_at)
                    VALUES('old_fence','Old fence','fence','999991',1,1)""")
            upgraded=LocationAssetStore(root)
            self.assertEqual(upgraded.get('old_fence')['surfaceMaterial'],'default')
            self.assertEqual(upgraded.get('old_fence')['model_asset_id'],'999991')
            backups=list((root/'.control-center'/'backups').glob('location_surface_material_m249_*.sqlite'))
            self.assertEqual(len(backups),1)
            # Reopening the store is idempotent and does not create another backup.
            LocationAssetStore(root)
            self.assertEqual(len(list((root/'.control-center'/'backups').glob('location_surface_material_m249_*.sqlite'))),1)

    def test_material_validation_fails_closed(self):
        for invalid in ('Wool','fire', 'metal;DELETE', 'fluorescent', '../wood'):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                taxonomy.surface_material(invalid)
        self.assertEqual(taxonomy.surface_material(None),'default')

    def test_material_revision_invalidates_scanned_place_registry(self):
        class Fake:
            def __init__(self,material): self.material=material
            def snapshot(self): return {'items':[{'slug':'post_01','status':'PUBLISHED',
                'model_asset_id':'123','texture_asset_id':'234', 'surfaceMaterial':self.material,
                'materialDefinition':taxonomy.MATERIAL_BY_ID[self.material],
                'model_published_sha256':'sha'}]}
            def model_publication_ids(self,slug):return ['123']
            def mesh_id_inventory(self,slug):return []
        wood=build_catalog(Fake('wood'))
        metal=build_catalog(Fake('metal'))
        self.assertNotEqual(wood['digest'],metal['digest'])
        self.assertEqual(wood['items'][0]['surfaceMaterial'],'wood')
        self.assertEqual(wood['items'][0]['robloxMaterial'],'Wood')

    def test_studio_application_is_scoped_and_reversible(self):
        core=(ROOT/'src/shared/world/MeshPhysicsCore.luau').read_text('utf-8')
        loader=(ROOT/'system/studio-plugin/modules/DecoAssetLoader.luau').read_text('utf-8')
        inventory=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text('utf-8')
        sync=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistrySync.luau').read_text('utf-8')
        self.assertIn('function Core.ApplyLocationSurfaceMaterial',core)
        self.assertIn('function Core.RestoreLocationSurfaceMaterial',core)
        self.assertIn('mesh:SetAttribute("Game1LocationSurfaceMaterial", key)',core)
        self.assertIn('ApplyLocationSurfaceMaterial(model,row.surfaceMaterial',loader)
        self.assertIn('needsMaterial',inventory)
        self.assertIn('RestoreLocationSurfaceMaterial',sync)
        self.assertIn('ref.row.needsTexture or ref.row.needsMaterial',sync)
        self.assertIn('surfaceMaterial', (ROOT/'src/shared/world/LocationSurfaceMaterialResolver.luau').read_text())

    def test_category_picker_has_three_columns_and_native_select_fallback(self):
        picker=(ROOT/'system/control-center/static/location-category-picker.js').read_text()
        css=(ROOT/'system/control-center/static/location-category-picker.css').read_text()
        ui=(ROOT/'system/control-center/static/index.html').read_text()
        self.assertIn('options.categoryGroups.map',picker)
        self.assertIn('grid-auto-flow:column',css)
        self.assertIn("select.dispatchEvent(new Event('change'",picker)
        self.assertIn('location-asset-surface-material',ui)
        self.assertIn('location-category-picker.js?v=249',ui)
