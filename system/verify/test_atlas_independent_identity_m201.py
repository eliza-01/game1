"""M201: atlas display derives from atlas keys, not the first owning model."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from real_estate.store import RealEstateStore
from services.shared_asset_retirement import SharedAssetRetirement
from services.atlas_identity import display_identity


class AtlasIndependentIdentityM201(unittest.TestCase):
    def test_filename_is_identity_not_model_slug(self):
        self.assertEqual(display_identity('structures_01_2048x1024_atlas.png'),
                         {'atlasKey': 'structures_01', 'atlasName': 'structures',
                          'atlasVersion': '01', 'atlasResolution': '2048×1024'})
        self.assertEqual(display_identity('wall_torch_01.jpg')['atlasKey'], 'wall_torch_01')
        self.assertEqual(display_identity('massive_01_20000x20000_atlas.png')['atlasKey'],
                         'massive_01_20000x20000')

    @unittest.skipUnless(shutil.which('node'), 'Node required for shared atlas presentation checks')
    def test_cross_section_atlas_identity_and_reuse(self):
        process = subprocess.run(
            [shutil.which('node'), str(ROOT / 'system/verify/atlas_independent_identity_m201.js')],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_retirement_impact_exposes_source_filename_without_changing_asset_id(self):
        with TemporaryDirectory(prefix='game1-atlas-identity-m201-') as folder:
            root = Path(folder)
            source = root / 'structures_01_32x32_atlas.png'
            Image.new('RGB', (32, 32), (45, 75, 90)).save(source)
            model = root / 'example.fbx'
            model.write_bytes(b'test FBX')
            locations = LocationAssetStore(root)
            owner = locations.register({'slug': 'torch_a', 'nameEn': 'Torch A', 'category': 'light',
                                        'modelSourcePath': str(model), 'textureSourcePath': str(source)})
            with locations.atlases.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           ('987654321', owner['atlasVariantId']))
            locations.register({'slug': 'torch_b', 'nameEn': 'Torch B', 'category': 'light',
                                'modelSourcePath': str(model), 'textureReferenceSlug': 'torch_a'})
            estate = RealEstateStore(root, location_assets=locations)
            plan = SharedAssetRetirement(estate, locations).plan('location', 'torch_a')
            # Published owner links are migrated to direct Atlas Registry bindings.
            self.assertEqual(plan['dependentCount'], 0)
            self.assertEqual(locations.atlases.binding('location_asset', 'torch_b')['published_id'], '987654321')
            self.assertEqual(plan['sharedAtlasUses'][0]['assetId'], '987654321')
            self.assertEqual(plan['sharedAtlasUses'][0]['uses'],
                             [{'dependent': 'location:torch_b', 'part': 'texture'}])
            owner_node = next(n for n in plan['nodes'] if n['slug'] == 'torch_a')
            self.assertEqual(owner_node['textureFilename'], source.name)
            self.assertEqual(owner_node['textureId'], '987654321')
            self.assertEqual(owner_node['atlasKey'], 'structures_01')


if __name__ == '__main__':
    unittest.main()
