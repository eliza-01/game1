"""M254: a linked but inactive atlas can be explicitly published without rebinding."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services.location_atlas_publication import publish_pending_atlas


class DotPublicationM254(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        first=self.root/'bush_02_32x32_atlas.png'
        second=self.root/'bush_02_64x64_atlas.png'
        unrelated=self.root/'unrelated_32x32_atlas.png'
        for path,wh in ((first,32),(second,64),(unrelated,32)):
            Image.new('RGBA',(wh,wh),(10,20,30,120)).save(path)
        fbx=self.root/'bush_02.fbx';fbx.write_bytes(b'test')
        self.assets=LocationAssetStore(self.root)
        self.row=self.assets.register(dict(nameEn='Bush 02',slug='bush_02',
            category='bush',modelSourcePath=str(fbx),textureSourcePath=str(first)))
        self.pending=self.assets.atlases.adopt_file(str(second))
        self.unrelated=self.assets.atlases.adopt_file(str(unrelated))

    def test_connected_inactive_variant_publishes_without_switching_active_atlas(self):
        previous=self.assets.atlases.binding('location_asset','bush_02')
        variant_id=self.pending['id']
        def upload(chosen,creds,description):
            self.assertEqual(chosen,variant_id)
            with self.assets.connect() as db:
                db.execute('UPDATE texture_atlas_variants SET published_id=?,published_sha256=source_sha256 WHERE id=?',
                           ('788811',chosen))
            return self.assets.atlases.get_variant(chosen)
        with mock.patch.object(self.assets.atlases,'ensure_published',side_effect=upload) as called:
            out=publish_pending_atlas(self.assets,'bush_02',variant_id=variant_id,
                expected_revision=previous['revision'],credentials={'apiKey':'fake'})
        called.assert_called_once()
        self.assertEqual(out['publishedAssetId'],'788811')
        after=self.assets.atlases.binding('location_asset','bush_02')
        self.assertEqual(after['variant_id'],previous['variant_id'])
        self.assertEqual(after['revision'],previous['revision'])
        self.assertEqual(self.assets.get('bush_02')['model_asset_id'],self.row['model_asset_id'])

    def test_wrong_family_and_stale_revision_rejected_without_upload(self):
        revision=self.row['bindingRevision']
        with mock.patch.object(self.assets.atlases,'ensure_published') as upload:
            with self.assertRaisesRegex(ValueError,'not connected'):
                publish_pending_atlas(self.assets,'bush_02',variant_id=self.unrelated['id'],
                    expected_revision=revision,credentials={})
            with self.assertRaisesRegex(ValueError,'changed'):
                publish_pending_atlas(self.assets,'bush_02',variant_id=self.pending['id'],
                    expected_revision=revision+1,credentials={})
            upload.assert_not_called()
