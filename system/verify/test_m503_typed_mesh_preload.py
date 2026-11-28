"""Regression guards for the M501 raw mesh URI/type mismatch."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TypedMeshPreload(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / 'src/client/AssetMeshPreloader.luau').read_text(encoding='utf8')

    def test_fetch_passes_typed_instance_not_uri(self):
        self.assertIn('request = typedRequest(item)', self.source)
        self.assertIn('ContentProvider:PreloadAsync({request}', self.source)
        self.assertNotIn('PreloadAsync, ContentProvider, {id}', self.source)
        self.assertNotIn('GetAssetFetchStatus, ContentProvider, id', self.source)
        self.assertIn('local copy = source:Clone()', self.source)
        self.assertIn('copy:ClearAllChildren()', self.source)
        self.assertIn('copy.TextureID = ""', self.source)
        self.assertIn('Instance.new("Decal")', self.source)
        self.assertIn('decal.Texture = item.id', self.source)

    def test_cache_is_typed_and_only_confirmed_success(self):
        self.assertIn('(if geometry then "mesh:" else "image:") .. value', self.source)
        self.assertIn('if ok and callbackSeen and success then\n            loaded[key] = true', self.source)
        self.assertIn('failureStatus or "no fetch callback"', self.source)
        self.assertIn('failedUntil[key] = os.clock() + 2', self.source)
        self.assertIn('if request then request:Destroy() end', self.source)
        self.assertIn('elseif item.geometry then geometryReady = false end', self.source)

    def test_no_raw_pbr_requests(self):
        for property_name in ('ColorMap', 'MetalnessMap', 'NormalMap', 'RoughnessMap'):
            self.assertNotIn('object.' + property_name, self.source)


if __name__ == '__main__':
    unittest.main()
