"""Offline tests for the shared FBX skin limit and NPC Studio skeleton contract."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/asset-manager"))
sys.path.insert(0, str(ROOT / "system/control-center"))
from bone_weight_survival import MAX_INFLUENCES, SURVIVAL_WEIGHT, plan_publication_weights
from monster_store import MonsterStore, NPC_PUBLICATION_PIPELINE


class BoneSurvivalTests(unittest.TestCase):
    def test_prunes_five_and_seven_influences_preserving_every_bone(self):
        # Covers the over-limit topology found in the registered NPC metadata.
        heads = {f"bone_{n}": (n * 0.1, 0, 0) for n in range(12)}
        vertices = [
            {"position": (index * 0.1, 0, 0), "mesh": "body", "index": index,
             "weights": {f"bone_{n}": 1 / 7 for n in range(7)}}
            for index in range(30)
        ]
        before = [dict(vertex["weights"]) for vertex in vertices]
        report = plan_publication_weights(heads, vertices)
        self.assertEqual(report['verticesOverFourBefore'], 30)
        self.assertEqual(report['verticesOverFourAfter'], 0)
        self.assertEqual(report['survivingBoneCount'], len(heads))
        self.assertTrue(any(vertex['weights'] != orig for vertex, orig in zip(vertices, before)))
        self.assertTrue(all(len(row['weights']) <= MAX_INFLUENCES for row in vertices))
        for name in heads:
            self.assertTrue(any(vertex['weights'].get(name, 0) >= SURVIVAL_WEIGHT for vertex in vertices), name)

    def test_retains_existing_skin_when_four_or_fewer(self):
        heads = {'a': (0, 0, 0), 'b': (1, 0, 0)}
        vertices = [
            {'position': (0, 0, 0), 'weights': {'a': 0.7, 'b': 0.3}},
            {'position': (1, 0, 0), 'weights': {'b': 1}},
        ]
        report = plan_publication_weights(heads, vertices)
        self.assertEqual(report['patchedBoneCount'], 0)
        self.assertAlmostEqual(vertices[0]['weights']['a'], .7)
        self.assertAlmostEqual(vertices[0]['weights']['b'], .3)

    def test_fails_closed_if_no_safe_vertex_exists(self):
        heads = {f'b{i}': (0, 0, 0) for i in range(6)}
        vertices = [
            {'position': (0, 0, 0), 'weights': {f'b{i}': 0.25 for i in range(4)}}
        ]
        with self.assertRaisesRegex(ValueError, 'no safe'):
            plan_publication_weights(heads, vertices)

    def test_existing_npc_requires_new_model_publication_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MonsterStore(Path(tmp), kind='npc')
            with store.connect() as db:
                db.execute('''INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,
                    model_asset_id,model_published_sha256,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?)''',
                    ('npc_one', 'NPC One', 'assets/source/npcs/npc_one/model/npc_one.fbx',
                     'same-sha', '123', 'same-sha', 1.0, 1.0))
            self.assertTrue(store.get('npc_one')['publicationUpgradeAvailable'])
            with store.connect() as db:
                db.execute('UPDATE monsters SET publication_pipeline=? WHERE slug=?',
                           (NPC_PUBLICATION_PIPELINE, 'npc_one'))
            self.assertFalse(store.get('npc_one')['publicationUpgradeAvailable'])

    def test_studio_checks_authored_bones_before_replacing_template(self):
        plugin = (ROOT / 'system/studio-plugin/modules/StudioModelLoadCommands.luau').read_text(encoding='utf-8')
        host = (ROOT / 'system/control-center/services/studio_asset_sync.py').read_text(encoding='utf-8')
        self.assertIn('assertExpectedBones(importedRig, metadata.expectedBones)', plugin)
        section = plugin[plugin.index('local function placeMonsterRig'):]
        self.assertLess(section.index('assertExpectedBones('), section.index('previousRig.Name = "ImportedRig_Previous"'))
        self.assertIn('"expectedBones": [', host)


if __name__ == '__main__':
    unittest.main(verbosity=2)
