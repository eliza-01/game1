"""M213: source image signatures, not file extensions, control Atlas adoption."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
import sys

from PIL import Image, features

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class RealEstateAtlasSourceFormatM213(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.fbx = self.root / 'house_level2_01.fbx'
        self.fbx.write_bytes(b'FBX test fixture')
        self.store = RealEstateStore(self.root)
        self.source = self.root / 'house_level2_01_32x32_atlas.png'

    def register(self):
        with mock.patch('real_estate.store.inspect', return_value=skeleton()):
            return self.store.register({
                'houseType': 'house', 'level': 2, 'variant': '01',
                'sourcePath': str(self.fbx),
                'textures': {'house': str(self.source)},
                'textureReferences': {'door': 'same:house'},
            })

    def test_webp_image_under_png_name_is_canonicalized_to_true_png(self):
        if not features.check('webp'):
            self.skipTest('Pillow WebP support unavailable')
        Image.new('RGBA', (32, 32), (20, 30, 40, 80)).save(self.source, format='WEBP', lossless=True)
        original = self.source.read_bytes()
        row = self.register()
        house = row['textures']['house']
        saved = self.root / house['path']
        with Image.open(saved) as decoded:
            self.assertEqual(decoded.format, 'PNG')
            self.assertEqual(decoded.size, (32, 32))
            self.assertEqual(decoded.getpixel((0, 0)), (20, 30, 40, 80))
        with Image.open(self.source) as original_decoded:
            self.assertEqual(original_decoded.format, 'WEBP')
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(house['atlasVariantId'], row['textures']['door']['atlasVariantId'])
        self.assertEqual(self.store.atlases.get_variant(house['atlasVariantId'])['source_path'], house['path'])
        self.assertFalse(house['atlasCurrent'])
        self.assertEqual(house['atlasKey'], 'house_level2_01')

    def test_real_png_is_copied_byte_for_byte_and_adopt_is_idempotent(self):
        Image.new('RGB', (32, 32), (40, 50, 60)).save(self.source, format='PNG')
        data = self.source.read_bytes()
        row = self.register()
        self.assertEqual((self.root / row['textures']['house']['path']).read_bytes(), data)
        existing = self.store.atlases.adopt_file(str(self.source))
        self.assertEqual(existing['id'], row['textures']['house']['atlasVariantId'])

    def test_jpeg_bytes_under_png_name_store_as_jpeg_with_matching_extension(self):
        Image.new('RGB', (32, 32), (40, 50, 60)).save(self.source, format='JPEG')
        row = self.register()
        stored = self.root / row['textures']['house']['path']
        self.assertEqual(stored.suffix, '.jpg')
        with Image.open(stored) as image:
            self.assertEqual(image.format, 'JPEG')
        self.assertEqual(stored.read_bytes(), self.source.read_bytes())

    def test_gif_disguised_as_png_is_rejected_without_mutation(self):
        Image.new('RGB', (32, 32), (60, 40, 20)).save(self.source, format='GIF')
        with self.assertRaisesRegex(ValueError, 'house: texture must be a real PNG or JPEG file.*detected GIF'):
            self.register()
        self.assertIsNone(self.store.get('house_level2_01'))
        self.assertEqual(self.store.atlases.catalog(), [])

    def test_unreadable_png_reports_validation_error_not_uncaught_pillow_error(self):
        self.source.write_bytes(b'this is not an image')
        with self.assertRaisesRegex(ValueError, 'house: cannot read atlas image'):
            self.register()
        self.assertIsNone(self.store.get('house_level2_01'))
