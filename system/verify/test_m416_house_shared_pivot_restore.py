"""M416: restore only one house part; fail closed on non-canonical static FBX."""
from __future__ import annotations

from contextlib import closing
import json
import hashlib
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.publication_restore import restore_visual_part
from real_estate.rig_publication_policy import publication_fingerprint

SLUG = 'house_level5_01'
PART = 'walls_outside'
ORIGINAL_SHA = hashlib.sha256(b'original house fbx').hexdigest()
REPLACEMENT_SHA = 'b' * 64
OLD_ID = '76514050293314'
NEW_ID = '94992567240003'


def make_db(path: Path, original: bool):
    entry = {'name': PART, 'armature': 'house_armature' if original else '',
             'bones': [], 'vertices': 118 if original else 119,
             'authoredPlacement': {'version': 3, 'centerInPivot': [-4, 19, 4], 'size': [30, 32, 25]}}
    other = {'name': 'roof', 'armature': 'house_armature', 'bones': []}
    rigs = {PART: {'assetId': OLD_ID if original else NEW_ID,
                   'publishedSha256': publication_fingerprint(ORIGINAL_SHA if original else REPLACEMENT_SHA,
                                                               carrier=False)},
            'roof': {'assetId': '888', 'publishedSha256': 'roof-hash'}}
    sources = {} if original else {PART: {'path': 'assets/walls_outside.fbx', 'sha256': REPLACEMENT_SHA}}
    with closing(sqlite3.connect(path)) as db:
        db.execute('create table real_estate (slug text primary key, model_path text, model_sha256 text, '
                   'skeleton_json text, model_rigs_json text, mesh_sources_json text, revision integer, updated_at real)')
        db.execute('create table real_estate_publications (house_slug text, part text, asset_id text)')
        db.execute('insert into real_estate values (?,?,?,?,?,?,?,0)',
                   (SLUG, 'assets/whole_house.fbx', ORIGINAL_SHA,
                    json.dumps({'schemaVersion': 1, 'meshes': [entry, other]}),
                    json.dumps(rigs), json.dumps(sources), 12 if original else 31))
        db.execute('insert into real_estate_publications values(?,?,?)', (SLUG, 'model:' + PART, OLD_ID))
        db.execute('insert into real_estate_publications values(?,?,?)', (SLUG, 'model:' + PART, NEW_ID))
        db.commit()


class HouseSharedPivotRestoreM416(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.root = Path(self.folder.name).resolve()
        (self.root / '.control-center' / 'backups').mkdir(parents=True)
        self.active = self.root / '.control-center' / 'game1_real_estate.db'
        self.snapshot = self.root / '.control-center' / 'backups' / 'before.sqlite'
        (self.root / 'assets').mkdir()
        (self.root / 'assets' / 'whole_house.fbx').write_bytes(b'original house fbx')
        make_db(self.active, False)
        make_db(self.snapshot, True)

    def tearDown(self):
        self.folder.cleanup()

    def restore(self, **changes):
        args = dict(slug=SLUG, part=PART,
                    snapshot='.control-center/backups/before.sqlite',
                    current_id=NEW_ID, restore_id=OLD_ID)
        args.update(changes)
        with patch('real_estate.store.RealEstateStore') as store:
            result = restore_visual_part(self.root, **args)
            if result['changed']:
                store.assert_called_once_with(self.root)
        return result

    def test_only_target_part_returns_to_historical_published_model(self):
        result = self.restore()
        self.assertTrue(result['changed'])
        self.assertTrue((self.root / result['backup']).is_file())
        with closing(sqlite3.connect(self.active)) as db:
            row = db.execute('select skeleton_json,model_rigs_json,mesh_sources_json,revision '
                             'from real_estate where slug=?', (SLUG,)).fetchone()
            entries = json.loads(row[0])['meshes']
            rigs = json.loads(row[1])
            self.assertEqual(entries[0]['armature'], 'house_armature')
            self.assertEqual(entries[1]['name'], 'roof')
            self.assertEqual(rigs[PART]['assetId'], OLD_ID)
            self.assertEqual(rigs['roof']['assetId'], '888')
            self.assertNotIn(PART, json.loads(row[2]))
            self.assertEqual(row[3], 32)
            self.assertEqual(db.execute('select count(*) from real_estate_publications').fetchone()[0], 2)
        self.assertFalse(self.restore()['changed'])

    def test_reference_provenance_is_not_bypassed(self):
        with self.assertRaisesRegex(ValueError, 'reference must be'):
            self.restore(snapshot='../before.sqlite')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.restore(restore_id='999999')
        with self.assertRaisesRegex(ValueError, 'changed since inspection'):
            self.restore(current_id='11111')
        with closing(sqlite3.connect(self.snapshot)) as db:
            db.execute('update real_estate set model_sha256=? where slug=?', ('c' * 64, SLUG))
            db.commit()
        with self.assertRaisesRegex(ValueError, 'fingerprint changed'):
            self.restore()

    def test_shared_pivot_preflight_preserves_mesh_cframe_without_using_mesh_centre(self):
        text = (ROOT / 'system/studio-plugin/modules/StudioRealEstatePartPlacement.luau').read_text()
        method = text.split('function Placement.AlignOrigin(', 1)[1].split('function Placement.Align(', 1)[0]
        self.assertNotIn('if displacement > tolerance then', method)
        self.assertNotIn('mesh.Position', method)
        self.assertIn('local originalFrame = mesh.CFrame', method)
        self.assertIn('mesh.PivotOffset = originalFrame:ToObjectSpace(housePivot)', method)
        self.assertIn('Placement.SamePivot(mesh:GetPivot(), housePivot)', method)
        self.assertNotIn('mesh.CFrame =', method)
        self.assertNotIn('rig:PivotTo(', method)
        self.assertIn('not Placement.SamePivot(mesh.CFrame, originalFrame)', method)
        self.assertNotIn('CFrame.new(delta)', method)

    def test_repair_does_not_change_location_mesh_runtime_or_other_references(self):
        source = (ROOT / 'system/control-center/real_estate/publication_restore.py').read_text()
        self.assertNotIn('delete from real_estate_publications', source.lower())
        self.assertNotIn('update real_estate_placements', source.lower())
        self.assertNotIn('update real_estate_part_distances', source.lower())
        self.assertIn('model_rigs_json=?,mesh_sources_json=?,revision=revision+1', source)


if __name__ == '__main__':
    unittest.main()
