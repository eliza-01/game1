"""M128: Props category survives registration, filters and Studio registry export."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from location_asset_store import CATEGORIES, LocationAssetStore


class LocationAssetPropsCategoryTests(unittest.TestCase):
    def test_props_registration_and_generated_registry(self):
        with tempfile.TemporaryDirectory(prefix="game1-m128-") as temp:
            root = Path(temp)
            model = root / "prop_test.fbx"
            model.write_bytes(b"sample FBX for contract test")
            atlas = root / "prop_kit_64x64_atlas.png"
            Image.new("RGBA", (64, 64), (190, 110, 70, 255)).save(atlas)
            store = LocationAssetStore(root)

            categories = store.options()["categories"]
            self.assertEqual(categories[-1], {"id": "prop", "label": "Props"})
            self.assertEqual([row["id"] for row in categories], list(CATEGORIES))

            row = store.register({
                "nameEn": "Lantern Prop",
                "category": "prop",
                "modelSourcePath": str(model),
                "textureSourcePath": str(atlas),
            })
            self.assertEqual(row["category"], "prop")
            self.assertEqual(row["category_label"], "Props")
            self.assertEqual(row["status"], "LOCAL_ONLY")
            self.assertEqual(row["atlasFamily"], "prop_kit")
            self.assertTrue((root / row["model_path"]).is_file())
            self.assertIn("/prop/lantern_prop/", row["model_path"])

            snapshot = store.snapshot()
            self.assertEqual(snapshot["items"][0]["category"], "prop")
            registry = (root / "src/shared/world/LocationAssetRegistry.luau").read_text(encoding="utf-8")
            self.assertIn('category = "prop"', registry)

    def test_existing_categories_stay_available(self):
        self.assertEqual(CATEGORIES[:-1], (
            "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building"
        ))


if __name__ == "__main__":
    unittest.main()
