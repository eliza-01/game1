"""M184: independent Real Estate assets retain their common house-space frame."""
import importlib.util
import json
import sys
from types import SimpleNamespace
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / 'system/asset-manager'
MODULES = ROOT / 'system/studio-plugin/modules'

spec = importlib.util.spec_from_file_location('real_estate_part_placement', ASSET / 'real_estate_part_placement.py')
placement_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(placement_module)


def cube(midpoint, halfsize):
    return [(midpoint[0] + dx * halfsize[0], midpoint[1] + dy * halfsize[1], midpoint[2] + dz * halfsize[2])
            for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]


class RealEstateAuthoredPlacementM184(unittest.TestCase):
    def test_door_keeps_measured_authoring_offset_not_a_constant(self):
        # Measured bounds in the supplied house_level5_01.fbx (local FBX axes).
        house = cube((0.0451698303, 0.0179243088, 21.64680481),
                     (18.97814941, 20.31032658, 21.64680481))
        door = cube((2.49234812, 7.5063405, 10.13221073),
                    (2.89707096, 0.61879778, 3.96436024))
        result = placement_module.placement(house, door)
        self.assertEqual(result['version'], 2)
        self.assertAlmostEqual(result['centerInHouse'][0], -2.447178, places=4)
        self.assertAlmostEqual(result['centerInHouse'][1], -11.514594, places=4)
        self.assertAlmostEqual(result['centerInHouse'][2], 7.488416, places=4)
        self.assertAlmostEqual(result['size'][1], 7.928720, places=4)
        self.assertAlmostEqual(result['size'][2], 1.237596, places=4)
        # Changing the authored door pose changes the recovered placement;
        # there is no house-level-specific correction.
        shifted = cube((2.49234812, 7.5063405, 14.13221073),
                       (2.89707096, 0.61879778, 3.96436024))
        self.assertAlmostEqual(placement_module.placement(house, shifted)['centerInHouse'][1],
                               result['centerInHouse'][1] + 4, places=4)

    def test_relative_frame_zero_for_house_and_rejects_invalid_bounds(self):
        corners = cube((12, -3, 22), (9, 5, 20))
        self.assertEqual(placement_module.placement(corners, corners)['centerInHouse'], [0, 0, 0])
        with self.assertRaisesRegex(ValueError, 'invalid coordinates'):
            placement_module.placement(corners, [(1, 2, 3), (float('nan'), 2, 3)])
        with self.assertRaisesRegex(ValueError, 'unusable'):
            placement_module.placement(corners, cube((1, 1, 1), (1, 0, 1)))

    def test_analysis_persists_author_frame_and_sync_forwards_stored_data(self):
        inspection = (ASSET / 'analyze_real_estate_fbx.py').read_text('utf-8')
        self.assertIn('inspect_placements(', inspection)
        self.assertIn("record['authoredPlacement'] = placements[name]", inspection)
        sync = (ROOT / 'system/control-center/real_estate/studio_sync.py').read_text('utf-8')
        self.assertIn("mesh['authoredPlacement']", sync)
        self.assertIn("'authoredPlacements'", sync)
        self.assertNotIn('sourcePath', sync)

    def test_sync_payload_carries_author_geometry_without_modifying_published_assets(self):
        sys.path.insert(0, str(ROOT / 'system/control-center'))
        from real_estate.studio_sync import RealEstateStudioSync
        house = {'name': 'house', 'armature': 'house_armature', 'bones': [],
                 'authoredPlacement': {'version': 2, 'centerInHouse': [0, 0, 0],
                                       'size': [38, 43, 41]}}
        door = {'name': 'door', 'armature': 'door_armature', 'bones': [],
                'authoredPlacement': {'version': 2, 'centerInHouse': [-2.44, -11.51, 7.48],
                                      'size': [5.79, 7.93, 1.24]}}
        row = {'status': 'PUBLISHED', 'slug': 'house_level5_01',
               'rigAssets': {'house': {'assetId': '111'}, 'door': {'assetId': '222'}},
               'skeleton': {'meshes': [house, door]}, 'house_level': 5,
               'purchase_price': 1, 'min_level': 1, 'sale_price': 1,
               'textures': {'house': {'assetId': '3'}, 'door': {'assetId': '4'}}}
        calls = []
        def fake_load(*args, **kwargs):
            calls.append(kwargs['metadata'])
            return {'realEstateStats': {'bonesValidated': True, 'rigsValidated': 2,
                                        'texturesApplied': 2}}
        RealEstateStudioSync(SimpleNamespace(get=lambda slug: row), fake_load).sync(row['slug'])
        self.assertEqual(calls[0]['authoredPlacements']['door'], door['authoredPlacement'])
        self.assertEqual(calls[0]['rigAssetIds'], {'house': '111', 'door': '222'})
        self.assertEqual(row['rigAssets']['door']['assetId'], '222')

    def test_studio_full_and_partial_share_bounded_position_restoration(self):
        module = (MODULES / 'StudioRealEstatePartPlacement.luau').read_text('utf-8')
        self.assertIn('house.CFrame:PointToWorldSpace(center * ratio)', module)
        self.assertIn('rig:PivotTo(CFrame.new(delta) * rig:GetPivot())', module)
        self.assertIn('if authored == nil or authoredHouse == nil then', module)
        self.assertIn('published mesh dimensions differ from authored FBX', module)
        full = (MODULES / 'StudioRealEstateModel.luau').read_text('utf-8')
        partial = (MODULES / 'StudioRealEstatePartSync.luau').read_text('utf-8')
        self.assertIn('PartPlacement.Align(rig, mesh, meshes.house,', full)
        self.assertIn('PartPlacement.Align(imported, mesh, anchor,', partial)
        self.assertLess(full.index('PartPlacement.Align('), full.index('assembly.WorldPivot'))
        self.assertLess(partial.index('PartPlacement.Align('), partial.index('assembly.WorldPivot'))
        plugin = json.loads((ROOT / 'system/studio-plugin/plugin.project.json').read_text('utf-8'))
        self.assertEqual(plugin['tree']['modules']['StudioRealEstatePartPlacement']['$path'],
                         'modules/StudioRealEstatePartPlacement.luau')
        self.assertIn("'StudioRealEstatePartPlacement'", (ROOT / 'system/studio-plugin/install.ps1').read_text('utf-8'))


if __name__ == '__main__':
    unittest.main()
