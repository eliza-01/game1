"""M204 contracts: visual-only Estate meshes and authored attack timeline coverage.

Uses the real timeline registry exporter on a temporary project; no modifications to
user databases, published assets, geometry or manually authored attack timings.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
sys.path.insert(0, str(ROOT / 'system/verify'))
from timeline_store import TimelineStore
from validators.registered_attack_clips import check_registered_attack_clips


class StubCharacters:
    def list(self):
        return [{'id': 'human_male', 'display_name': 'Human male', 'model_asset_id': '123'}]


class StubAnimations:
    def list_for_character(self, char_id):
        assert char_id == 'human_male'
        return [
            {'clip_id': 'human_male__weapon__1hs__attack__02', 'slot': 'attack',
             'asset_id': '456', 'name': '1hs_attack_02', 'weapon_set': '1hs', 'variant': 2}
        ]


class EmptyStore:
    def list(self):
        return []

    def list_for_monster(self, unused):
        return []


class HouseAndAttackM204(TestCase):
    def test_visual_physics_policy_is_single_writer_across_sync_paths(self):
        policy = (ROOT / 'system/studio-plugin/modules/StudioRealEstateCollisionPolicy.luau').read_text('utf8')
        # M205: physical door, glass and COL_* get Precise; other visuals Box.
        # Collision is a real authoring option rather than overridden by Sync.
        core = (ROOT / 'src/shared/world/MeshPhysicsCore.luau').read_text('utf8')
        self.assertIn('Core.Apply(mesh, not noCollide, fidelity,', policy)
        for required in (
            'mesh.CanCollide = true', 'mesh.CanCollide = false',
            'mesh.CanTouch = false', 'mesh.CanQuery = true', 'mesh.CanQuery = false',
            'mesh.CollisionFidelity = Core.Fidelity(if canCollide then "PreciseConvexDecomposition" else fidelity)',
            'mesh.DoubleSided = doubleSided',
            'PreciseConvexDecomposition = Enum.CollisionFidelity.PreciseConvexDecomposition',
            'Box = Enum.CollisionFidelity.Box',
        ):
            self.assertIn(required, core)
        self.assertIn('local preciseDefault = preciseByDefault(name)', policy)
        self.assertIn('CollectionService:AddTag(mesh, COLLIDER_TAG)', policy)
        paths = {
            'StudioRealEstateModel.luau': 'StudioRealEstateCollisionPolicy.Apply',
            'StudioRealEstatePartSync.luau': 'Collision.Apply',
            'StudioRealEstatePlacedCollisionSync.luau': 'StudioRealEstateCollisionPolicy',
        }
        for filename, required in paths.items():
            source = (ROOT / 'system/studio-plugin/modules' / filename).read_text('utf8')
            self.assertIn(required, source, filename)

    def test_published_attack_ids_have_exact_timeline_keys(self):
        timeline = (ROOT / 'src/shared/combat/AttackTimelineData.luau').read_text('utf8')
        issues = []
        check_registered_attack_clips(ROOT, issues.append, attack_timeline_data_text=timeline)
        self.assertEqual(issues, [])
        self.assertIn('["human_male__weapon__1hs__attack__02"]', timeline)
        self.assertNotIn('["human_male_weapon_1hs_attack_02"]', timeline)

    def test_seeded_male_durations_match_blender_authoring_and_presets_reviewed(self):
        manifest = json.loads((ROOT / 'assets/manifests/attack-timelines.json').read_text('utf8'))
        timeline_by_id = {row['clipId']: row for row in manifest['timelines']}
        for name in ('1hs_attack_01', '1hs_attack_02', '1hs_attack_03', 'hands_attack_01'):
            metadata = json.loads((ROOT / 'assets/authoring/animations/human_male' /
                                   ('human_male_' + name + '.animation.json')).read_text('utf8'))
            weapon, number = name.rsplit('_attack_', 1)
            key = f'human_male__weapon__{weapon}__attack__{number}'
            row = timeline_by_id[key]
            expected = (metadata['frame_end'] - metadata['frame_start']) / metadata['fps']
            self.assertAlmostEqual(row['duration'], expected, places=8)
            self.assertTrue(row['reviewRequired'], key)
            self.assertEqual(row['events'], {
                'HitStart': {'normalizedTime': 0.4},
                'HitEnd': {'normalizedTime': 0.5},
            })

    def test_generated_runtime_is_reproducible_and_review_is_visible_then_clearable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = ROOT / 'assets/manifests/attack-timelines.json'
            out = root / 'assets/manifests/attack-timelines.json'
            out.parent.mkdir(parents=True)
            out.write_bytes(src.read_bytes())
            store = TimelineStore(root, StubCharacters(), StubAnimations(), EmptyStore(), EmptyStore())
            committed = (ROOT / 'src/shared/combat/AttackTimelineData.luau').read_text('utf8')
            self.assertEqual(store.runtime_path.read_text('utf8'), committed)
            row = next(row for row in store.snapshot()['items'] if row['clipId'].endswith('attack__02'))
            self.assertTrue(row['needsReview'])
            self.assertFalse(row['configured'])
            store.save({'clipId': row['clipId'], 'duration': 1.5,
                        'events': {'HitStart': {'normalizedTime': 0.35},
                                   'HitEnd': {'normalizedTime': 0.6}}})
            after = next(r for r in store.snapshot()['items'] if r['clipId'] == row['clipId'])
            self.assertFalse(after['needsReview'])
            self.assertTrue(after['configured'])
            self.assertEqual(store._timeline_map()[row['clipId']]['events']['HitStart']['normalizedTime'], 0.35)


if __name__ == '__main__':
    import unittest
    unittest.main()
