"""M458: armor set pair coverage and real-rig validation, no forced republish."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.armor_readiness import describe_set


def fixture():
    pieces = [
        dict(slot='upper', id='starter_upper', variants={
            'female': dict(meshPartId='female_upper', appearanceId='atlas_1')
        }),
        dict(slot='boots', id='starter_boots', variants={
            'unisex': dict(meshPartId='common_boots', appearanceId='atlas_2')
        }),
    ]
    meshes = [
        dict(id='female_upper', slot='upper', allowedGenders=['female'],
             model_asset_id='111', revision=1, published_revision=1),
        dict(id='male_upper', slot='upper', allowedGenders=['male'],
             model_asset_id='222', revision=1, published_revision=1),
        dict(id='common_boots', slot='boots', allowedGenders=['male', 'female'],
             model_asset_id='333', revision=1, published_revision=1),
    ]
    appearances = [dict(id='atlas_1', atlas_variant_id=1), dict(id='atlas_2', atlas_variant_id=2)]
    atlases = [dict(id=1, current=True, replacementPending=False, published_id='1234'),
               dict(id=2, current=True, replacementPending=False, published_id='5678')]
    return dict(pieces=pieces), meshes, appearances, atlases


class ArmorPairCoverageM458(unittest.TestCase):
    def test_female_only_is_draft_but_common_boots_cover_both(self):
        report = describe_set(*fixture())
        self.assertFalse(report['complete'])
        self.assertEqual(report['genders']['male']['assigned'], 1)
        self.assertEqual(report['genders']['female']['assigned'], 2)
        self.assertEqual(report['genders']['male']['missing'], [{'slot':'upper','reason':'variant'}])
        self.assertTrue(report['slots']['boots']['male']['ready'])
        self.assertEqual(report['slots']['boots']['male']['source'], 'unisex')

    def test_male_counterpart_makes_complete(self):
        data = fixture()
        data[0]['pieces'][0]['variants']['male'] = dict(meshPartId='male_upper',appearanceId='atlas_1')
        report = describe_set(*data)
        self.assertTrue(report['complete'])
        self.assertEqual(report['genders']['male']['assigned'], 2)
        self.assertEqual(report['genders']['female']['assigned'], 2)

    def test_incomplete_explicit_override_does_not_fall_back_to_unisex(self):
        data = fixture()
        data[0]['pieces'][1]['variants']['male'] = dict(meshPartId=None, appearanceId=None)
        report = describe_set(*data)
        self.assertEqual(report['slots']['boots']['male']['reason'], 'mesh')
        self.assertEqual(report['slots']['boots']['female']['source'], 'unisex')

    def test_missing_texture_and_unpublished_mesh_are_not_ready(self):
        data = fixture()
        data[0]['pieces'][0]['variants']['male'] = dict(meshPartId='male_upper',appearanceId=None)
        self.assertEqual(describe_set(*data)['slots']['upper']['male']['reason'], 'appearance')
        data[0]['pieces'][0]['variants']['male']['appearanceId']='atlas_1'
        data[1][1]['published_revision']=0
        self.assertEqual(describe_set(*data)['slots']['upper']['male']['reason'], 'mesh_publication')
        data[1][1]['published_revision']=1
        data[3][0]['replacementPending']=True
        self.assertEqual(describe_set(*data)['slots']['upper']['male']['reason'], 'atlas_publication')

    def test_gender_policy_and_missing_appearance_detection(self):
        data=fixture()
        data[1][2]['allowedGenders']=['female']
        self.assertEqual(describe_set(*data)['slots']['boots']['male']['reason'], 'mesh_compatibility')
        data[1][2]['allowedGenders']=['male','female']
        data[2][0]['id']='renamed'
        self.assertEqual(describe_set(*data)['slots']['upper']['female']['reason'], 'appearance')

    def test_report_is_pure_and_does_not_require_always_four_slots(self):
        data=fixture()
        before=copy.deepcopy(data)
        describe_set(*data)
        self.assertEqual(data,before)
        self.assertTrue(describe_set({'pieces':[]},[],[],[])['complete'])


if __name__ == '__main__':
    unittest.main()

class ArmorSnapshotRigContractM458(unittest.TestCase):
    def test_snapshot_rig_report_matches_authoritative_resolver(self):
        # Use a detached SQLite copy; never modify the working author's assets.
        import sqlite3
        import tempfile
        from contextlib import closing
        from character_core.components import CharacterComponents
        from character_core.armor import ArmorCatalog

        project = Path(__file__).resolve().parents[2]
        source = project / '.control-center/game1.db'
        if not source.is_file():
            self.skipTest('No authoring database in this checkout')
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            dbfile = root / '.control-center/game1.db'
            dbfile.parent.mkdir(parents=True)
            # sqlite3.Connection as a context manager commits but NEVER closes.
            # Windows cannot unlink game1.db until BOTH backup handles close.
            with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(dbfile)) as target:
                origin.backup(target)
            armor = ArmorCatalog(CharacterComponents(root))
            for row in armor.snapshot()['sets']:
                for status in row['rigReadiness']:
                    _, missing = armor.resolve(row['id'], status['gender'], status['rigId'])
                    self.assertEqual(status['ready'], not missing)
                    self.assertEqual(status['missing'], missing)
