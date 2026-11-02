"""Read-only architecture checks reject new model/owner-based publication paths."""
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/verify'))
from validators.atlas_independence import check_atlas_independence

class IndependentAtlasArchitecture(TestCase):
    def test_canonical_project_does_not_recreate_owner_links(self):
        errors=[]
        check_atlas_independence(ROOT,errors.append)
        self.assertEqual(errors,[])

    def test_model_store_cannot_publish_images_directly(self):
        target=ROOT/'system/control-center/real_estate/store.py'
        original=Path.read_text
        def modified(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            return value+'\ncreate_image_asset(dummy)\n' if path==target else value
        errors=[]
        with patch.object(Path,'read_text',modified):
            check_atlas_independence(ROOT,errors.append)
        self.assertTrue(any('estate cannot own image publication' in value for value in errors))

    def test_location_store_cannot_reintroduce_owner_retention(self):
        target=ROOT/'system/control-center/location_asset_store.py'
        original=Path.read_text
        def modified(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            return value+'\nretained_textures.retain(1)\n' if path==target else value
        errors=[]
        with patch.object(Path,'read_text',modified):
            check_atlas_independence(ROOT,errors.append)
        self.assertTrue(any('location cannot own image publication' in value for value in errors))
