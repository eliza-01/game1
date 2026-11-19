"""M371+M372: arbitrary static visual meshes, authored pivot, explicit alpha."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.contracts import validate_analysis, warnings_for_analysis, parse_name
from real_estate.rig_publication_policy import publication_analysis, publish_bones_for_mesh
from real_estate.store import RealEstateStore, mesh_options
from real_estate.studio_sync import RealEstateStudioSync


def authored():
    bones = [
        {'name': 'houseplant_01', 'parent': '', 'matrixLocal': [0] * 16},
        {'name': 'door_01_hinge_socket', 'parent': '', 'matrixLocal': [0] * 16},
        {'name': 'door_01_handle_inside_socket', 'parent': 'door_01_hinge_socket', 'matrixLocal': [0] * 16},
        {'name': 'door_01_padlock_01_inside_socket', 'parent': 'door_01_hinge_socket', 'matrixLocal': [0] * 16},
        {'name': 'door_01_padlock_01_outside_socket', 'parent': 'door_01_hinge_socket', 'matrixLocal': [0] * 16},
    ]
    def part(name, influenced=()):
        return {'name': name, 'armature': 'house_armature', 'vertices': 16,
                'bones': copy.deepcopy(bones), 'influencedBones': list(influenced),
                'authoredPlacement': {'version': 3,
                    'centerInPivot': [0., 1., 0.], 'size': [2., 2., 2.]}}
    return {'schemaVersion': 1, 'meshes': [part('roof'), part('plants'),
        part('door', ('door_01_hinge_socket',)),
        part('door_handles', ('door_01_hinge_socket',))]}


class HouseMaterialContract(unittest.TestCase):
    def test_authoring_revision_filename_keeps_original_house_identity(self):
        self.assertEqual(parse_name('house_level5_01_remesh.fbx'),
            {'houseType': 'house', 'level': 5, 'variant': '01'})

    def test_new_house_has_no_reserved_house_mesh_and_stable_socket_carrier(self):
        source = authored()
        original = copy.deepcopy(source)
        validate_analysis(source)
        self.assertFalse(warnings_for_analysis(source))
        projected = publication_analysis(source)
        self.assertEqual(projected['primaryPart'], 'rig_carrier')
        self.assertEqual(source, original)
        by_name = {entry['name']: entry for entry in projected['meshes']}
        self.assertEqual(by_name['plants']['publicationBones'], [])
        self.assertEqual([x['name'] for x in projected['carrierBones']], ['houseplant_01'])
        self.assertEqual(by_name['roof']['publicationBones'], [])
        self.assertIn('door_01_hinge_socket', [x['name'] for x in by_name['door']['publicationBones']])
        self.assertIn('door_01_hinge_socket', [x['name'] for x in by_name['door_handles']['publicationBones']])
        self.assertFalse({'door_01_padlock_01_inside_socket', 'door_01_padlock_01_outside_socket'}.intersection(
            x['name'] for x in by_name['plants']['publicationBones']))

    def test_unlinked_static_mesh_can_carry_sockets_without_authoring_skin(self):
        source = authored()
        for mesh in source['meshes']:
            if mesh['name'] in ('roof', 'plants'):
                mesh['armature'] = ''
                mesh['bones'] = []
        original = copy.deepcopy(source)
        projected = publication_analysis(source)
        self.assertEqual(projected['primaryPart'], 'rig_carrier')
        carrier = next(m for m in projected['meshes'] if m['name'] == 'plants')
        self.assertFalse(carrier['generatedCarrierRig'])
        self.assertEqual(carrier['armature'], '')
        self.assertEqual(carrier['publicationBones'], [])
        self.assertEqual([b['name'] for b in projected['carrierBones']], ['houseplant_01'])
        self.assertEqual(original, source)

    def test_no_atlas_uses_native_material(self):
        options = mesh_options(('plants', 'walls_outside'), None)
        self.assertEqual(options['plants']['appearanceMode'], 'material')
        self.assertEqual(options['plants']['visualMaterial'], 'SmoothPlastic')
        self.assertEqual(options['walls_outside']['visualColor'], '#FFFFFF')
        self.assertFalse(options['plants']['alphaEnabled'])

    def test_opaque_atlas_and_explicit_alpha_modes(self):
        options = mesh_options(('plants', 'roof'), {
            'plants': {'appearanceMode': 'atlas', 'alphaEnabled': True},
            'roof': {'appearanceMode': 'material', 'visualMaterial': 'Wood', 'visualColor': '#AA8844'},
        })
        self.assertTrue(options['plants']['alphaEnabled'])
        self.assertEqual(options['roof']['visualMaterial'], 'Wood')
        self.assertEqual(options['roof']['visualColor'], '#AA8844')
        with self.assertRaisesRegex(ValueError, 'requires an atlas'):
            mesh_options(('roof',), {'roof': {'appearanceMode': 'material', 'alphaEnabled': True}})
        with self.assertRaisesRegex(ValueError, 'visualColor'):
            mesh_options(('roof',), {'roof': {'visualColor': '#FFFFFFAA'}})

    def test_existing_atlas_bindings_stay_atlas_until_migrated(self):
        options = mesh_options(('house', 'door', 'roof'), None, ('house', 'door'))
        self.assertEqual(options['house']['appearanceMode'], 'atlas')
        self.assertEqual(options['door']['appearanceMode'], 'atlas')
        self.assertEqual(options['roof']['appearanceMode'], 'material')

    def test_store_can_register_house_without_any_atlas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'house_level5_01.fbx'
            source.write_bytes(b'FBX mocked for registration test')
            store = RealEstateStore(root)
            with patch('real_estate.store.inspect', return_value=authored()):
                row = store.register({'sourcePath': str(source),
                    'houseType': 'house', 'level': 5, 'variant': '01',
                    'purchasePrice': 10, 'minLevel': 1, 'salePrice': 5,
                    'textures': {}, 'textureReferences': {}})
            self.assertEqual(row['meshParts'], ['door', 'door_handles', 'plants', 'roof'])
            self.assertTrue(all(row['publicationCurrent'][part] for part in row['meshParts']))
            self.assertTrue(all(not row['textures'][part].get('assetId') for part in row['meshParts']))
            self.assertEqual(row['status'], 'LOCAL_ONLY')
            store_reopened = RealEstateStore(root)
            reopened = store_reopened.get('house_level5_01')
            self.assertEqual(reopened['meshOptions']['roof']['appearanceMode'], 'material')

    def test_studio_manifest_uses_primary_and_only_selected_atlases(self):
        row = {
            'slug': 'house_level5_01', 'house_level': 5, 'purchase_price': 10,
            'min_level': 1, 'sale_price': 5, 'status': 'PUBLISHED',
            'meshParts': ['roof','plants','door','door_handles'],
            'skeleton': publication_analysis(authored()),
            'rigAssets': {p: {'assetId': str(i), 'publishedSha256': 'hash'}
                          for i,p in enumerate(('rig_carrier','roof','plants','door','door_handles'),start=100)},
            'rigSourceHashes': {p: 'hash' for p in ('roof','plants','door','door_handles')},
            'rigPublicationHashes': {p: 'hash' for p in ('rig_carrier','roof','plants','door','door_handles')},
            'textures': {p: {'assetId': '12345' if p=='plants' else '', 'atlasVariantId': None}
                         for p in ('roof','plants','door','door_handles')},
            'meshOptions': mesh_options(('roof','plants','door','door_handles'),
                {'plants': {'appearanceMode': 'atlas', 'alphaEnabled': True}}),
        }
        calls = []
        def loader(asset_id, args, **options):
            calls.append((asset_id, options['metadata']))
            return {'realEstateStats': {'bonesValidated': True, 'rigsValidated': 5,
                'texturesApplied': 1, 'placedSyncVersion': 3}}
        sync = RealEstateStudioSync(SimpleNamespace(root=Path('/'), get=lambda _: row), loader)
        sync.sync(row['slug'])
        loaded_id, meta = calls[0]
        self.assertEqual(meta['primaryPart'], 'rig_carrier')
        self.assertEqual(loaded_id, '100')
        self.assertEqual(meta['rigAssetIds']['rig_carrier'], '100')
        self.assertEqual(meta['expectedCarrierBones'], ['houseplant_01'])
        self.assertEqual(meta['doorParts'], {'door': True, 'door_handles': True})
        self.assertEqual([entry['slot'] for entry in meta['textures']], ['plants'])
        self.assertEqual(meta['meshOptions']['roof']['appearanceMode'], 'material')
        self.assertEqual(meta['authoredPlacements']['roof']['version'], 3)

    def test_luau_applies_surface_only_for_transparency_and_supports_native_material(self):
        common = (ROOT / 'system/studio-plugin/modules/StudioTextureAppearance.luau').read_text(encoding='utf8')
        studio = (ROOT / 'system/studio-plugin/modules/StudioRealEstateAppearance.luau').read_text(encoding='utf8')
        self.assertIn('if usesAlpha ~= true then', common)
        self.assertIn('if surface then surface:Destroy() end', common)
        self.assertIn('function StudioTextureAppearance.ApplyMaterial(', common)
        self.assertIn('return Texture.ApplyVisual(', studio)
        self.assertIn('Texture.ApplyVisual(mesh,settings', studio)
        self.assertIn('if not enabled then return appearance==nil end', common)


if __name__ == '__main__':
    unittest.main()
