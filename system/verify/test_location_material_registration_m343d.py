"""M343D: atlasless Location Asset registration, independent visual and audio materials.

Python/JS contracts; Roblox Studio execution is covered by acceptance checks, not mocked here.
"""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from location_asset_store import LocationAssetStore
from services.location_visual_appearance import BASEPART_MATERIALS, validated
from services.place_registry.catalog import build_catalog
from services.location_asset_sync_history import LocationAssetSyncHistory
from services.studio_deco_bridge import run_deco_refresh_bridge


class LocationMaterialM343D(TestCase):
    def test_new_material_registration_requires_no_atlas_or_image_id(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'untouched.fbx'
            source.write_bytes(b'illustrative FBX bytes; no FBX analysis requested')
            store = LocationAssetStore(root)
            asset = store.register({'nameEn': 'Stone Marker', 'slug': 'stone_marker_01',
                'category': 'prop', 'modelSourcePath': str(source), 'appearanceMode': 'material',
                'visualMaterial': 'Granite', 'visualColor': '#97A0B9',
                'surfaceMaterial': 'wood', 'destructible': False})
            self.assertEqual(asset['appearanceMode'], 'material')
            self.assertEqual(asset['status'], 'LOCAL_ONLY')
            self.assertEqual((asset['visualMaterial'], asset['visualColor']), ('Granite', '#97A0B9'))
            self.assertEqual(asset['surfaceMaterial'], 'wood')
            self.assertEqual(asset['materialDefinition']['soundFamily'], 'wood')
            self.assertFalse(asset['texture_asset_id'])
            self.assertEqual(asset['atlasVariants'], [])
            self.assertIsNone(store.atlases.binding('location_asset', 'stone_marker_01'))
            self.assertEqual(asset['bindingRevision'], 1)
            with store.connect() as db:
                db.execute("UPDATE location_assets SET model_asset_id=?,model_published_sha256=model_sha256 WHERE slug=?",
                           ('123456789', 'stone_marker_01'))
            store.export()
            published = store.get('stone_marker_01')
            self.assertEqual(published['status'], 'PUBLISHED')
            c = build_catalog(store)
            self.assertEqual([item['slug'] for item in c['items']], ['stone_marker_01'])
            self.assertEqual(c['items'][0]['atlasAssetId'], '')
            self.assertEqual(c['items'][0]['appearanceMode'], 'material')
            self.assertEqual(c['items'][0]['visualMaterial'], 'Granite')
            generated = (root / 'src/shared/world/LocationAssetRegistry.luau').read_text(encoding='utf-8')
            self.assertIn('visualMaterial = "Granite"', generated)
            self.assertIn('visualColor = "#97A0B9"', generated)
            self.assertIn('surfaceMaterial = "wood"', generated)
            self.assertIn('textureAssetId = ""', generated)

    def test_existing_atlas_data_keeps_old_defaults_and_requires_image(self):
        with TemporaryDirectory() as tmp:
            store = LocationAssetStore(Path(tmp))
            with store.connect() as db:
                db.execute("INSERT INTO location_assets(slug,name_en,category,model_path,model_asset_id,"
                           "revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                           ('old_atlas','Old Atlas','prop','legacy.fbx','98765',1,1,1))
            old = store.get('old_atlas')
            self.assertEqual(old['appearanceMode'], 'atlas')
            self.assertEqual(old['visualMaterial'], 'SmoothPlastic')
            self.assertEqual(old['visualColor'], '#FFFFFF')
            self.assertNotEqual(old['status'], 'PUBLISHED')
            self.assertEqual(build_catalog(store)['items'], [])

    def test_visual_validation_supports_basepart_palette_but_rejects_terrain_only(self):
        self.assertGreaterEqual(len(BASEPART_MATERIALS), 40)
        self.assertIn('SmoothPlastic', BASEPART_MATERIALS)
        self.assertIn('WoodPlanks', BASEPART_MATERIALS)
        self.assertIn('CeramicTiles', BASEPART_MATERIALS)
        self.assertNotIn('Water', BASEPART_MATERIALS)
        self.assertNotIn('Air', BASEPART_MATERIALS)
        self.assertEqual(validated('material','WoodPlanks','#ab12ef'), ('material','WoodPlanks','#AB12EF'))
        for mode, material, color in [('wrong','Metal','#FFFFFF'),('material','Air','#FFFFFF'),
                                      ('material','ForceField','#FFFFFF'),('material','SmoothPlastic','red'),
                                      ('material','SmoothPlastic','#abcd')]:
            with self.subTest(mode=mode, material=material, color=color), self.assertRaises(ValueError):
                validated(mode, material, color)

    def test_audit_accepts_short_material_color_without_mysql_schema_change(self):
        self.assertEqual(LocationAssetSyncHistory._validate_changes([{
            'kind':'appearance', 'oldId':'123456789',
            'newId':'SmoothPlastic#FFFFFF', 'count':1,
        }])[0]['newId'], 'SmoothPlastic#FFFFFF')
        for bad in ('SmoothPlastic:#FFFFFF', 'SmoothPlastic#FFFFFF00', 'Wood#GGGGGG'):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                LocationAssetSyncHistory._validate_changes([{
                    'kind':'appearance','oldId':'','newId':bad,'count':1}])

    def test_studio_transport_fails_closed_before_http(self):
        arguments = dict(slug='stone_marker_01',binding_revision=1,
                         model_asset_id='12345',atlas_asset_id='',appearance_mode='material')
        with self.assertRaises(ValueError):
            run_deco_refresh_bridge(**dict(arguments,model_asset_id=''))
        with self.assertRaises(ValueError):
            run_deco_refresh_bridge(**dict(arguments,atlas_asset_id='123'))
        with self.assertRaises(ValueError):
            run_deco_refresh_bridge(**dict(arguments,appearance_mode='atlas'))

    def test_studio_sync_separates_sound_and_appearance_and_legacy_registry(self):
        root=ROOT
        studio=(root/'system/studio-plugin/modules/StudioLocationVisualAppearance.luau').read_text(encoding='utf-8')
        core=(root/'src/shared/world/MeshPhysicsCore.luau').read_text(encoding='utf-8')
        placer=(root/'system/studio-plugin/modules/StudioPlaceRegistrySync.luau').read_text(encoding='utf-8')
        inventory=(root/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text(encoding='utf-8')
        manager=(root/'system/studio-plugin/modules/DecoManager.luau').read_text(encoding='utf-8')
        self.assertIn('mesh.TextureID=""', studio)
        self.assertIn('mesh.Material=material', studio)
        self.assertIn('mesh.Color=color', studio)
        self.assertIn('child:Destroy()', studio)
        section=core.split('function Core.ApplyLocationSurfaceMaterial',1)[1].split('\nend',1)[0]
        self.assertNotIn('mesh.Material=', section)
        self.assertIn('Game1LocationSurfaceMaterial', section)
        self.assertIn('Visual.Apply(change.mesh,row)',placer)
        self.assertIn('Visual.IsCurrent(visualPart',inventory)
        self.assertIn('row.appearanceMode=="material"',manager)
        project=(root/'system/studio-plugin/plugin.project.json').read_text(encoding='utf-8')
        self.assertIn('StudioLocationVisualAppearance',project)
        self.assertIn('StudioPlotsVisibility',project)
        self.assertIn('StudioPlaceRegistryInventory',project)

    def test_registration_editor_exposes_choice_before_register(self):
        html=(ROOT/'system/control-center/static/index.html').read_text(encoding='utf-8')
        js=(ROOT/'system/control-center/static/deco-assets.js').read_text(encoding='utf-8')
        self.assertIn('id="location-asset-appearance-mode"',html)
        self.assertIn('id="location-asset-visual-material"',html)
        self.assertIn('id="location-asset-visual-color"',html)
        self.assertIn("$('location-asset-appearance-mode').value = 'material'",js)
        self.assertIn("payload.appearanceMode==='atlas'",js)
        self.assertIn('visualMaterials',js)

    def test_studio_inventory_respects_atlas_alpha_and_default_sound_reset(self):
        source = (ROOT / 'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text(encoding='utf-8')
        self.assertIn('alphaEnabled=entry.alphaEnabled', source)
        self.assertIn('prior ~= nil and prior ~= "default"', source)
        self.assertIn('if prior ~= entry.material', source)

    def test_form_controls_live_inside_location_registration_panel(self):
        from html.parser import HTMLParser
        class Inspector(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.parents = {}
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag not in ('input','img','br','hr','meta','link','source','area','col'):
                    self.stack.append((tag,attrs.get('id')))
                if attrs.get('id'):
                    self.parents[attrs['id']] = tuple(k for _,k in self.stack if k)
            def handle_endtag(self, tag):
                for idx in range(len(self.stack)-1,-1,-1):
                    if self.stack[idx][0]==tag:
                        del self.stack[idx:]
                        break
        parser = Inspector()
        parser.feed((ROOT/'system/control-center/static/index.html').read_text(encoding='utf-8'))
        for field in ('location-asset-appearance-mode', 'location-asset-visual-material',
                      'location-asset-visual-color', 'location-asset-surface-material'):
            self.assertIn('location-asset-editor-panel', parser.parents[field])

    def test_material_settings_update_without_republishing_model(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/'mesh.fbx'
            src.write_bytes(b'illustrative FBX bytes')
            store=LocationAssetStore(root)
            row=store.register({'slug':'my_tree_01','nameEn':'My Tree','category':'tree',
                'modelSourcePath':str(src),'surfaceMaterial':'wood',
                'appearanceMode':'material','visualMaterial':'Wood','visualColor':'#123456'})
            with store.connect() as db:
                db.execute('UPDATE location_assets SET model_asset_id=?, model_published_sha256=model_sha256 WHERE slug=?',
                           ('81234567','my_tree_01'))
            initial=store.get('my_tree_01')
            self.assertEqual(initial['status'],'PUBLISHED')
            edited=store.register({'slug':'my_tree_01','nameEn':'My Tree','category':'tree',
                'editOnly':True,'expectedRevision':initial['revision'],
                'surfaceMaterial':'stone','appearanceMode':'material',
                'visualMaterial':'Granite','visualColor':'#AABBCC'})
            self.assertEqual(edited['status'],'PUBLISHED')
            self.assertEqual(edited['model_asset_id'], initial['model_asset_id'])
            self.assertEqual(edited['surfaceMaterial'],'stone')
            self.assertEqual(edited['visualMaterial'],'Granite')
            self.assertEqual(edited['visualColor'],'#AABBCC')
            self.assertGreater(edited['bindingRevision'], initial['bindingRevision'])
