"""Unified house skeleton: independent publication ownership and compatibility."""
import copy
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from real_estate.rig_publication_policy import publish_bones_for_mesh, publication_analysis
from real_estate.contracts import assert_rig_survived, warnings_for_analysis


def entry(part, influences=()):
    parents = {
        'land_spawn_01_socket': '', 'chest_01_socket': '',
        'door_01_hinge_socket': '',
        'door_01_handle_inside_socket': 'door_01_hinge_socket',
        'door_01_handle_outside_socket': 'door_01_hinge_socket',
        'door_01_padlock_01_socket': 'door_01_hinge_socket',
        'door_extra_tip': 'door_01_padlock_01_socket',
    }
    return {'name': part, 'armature': 'house_armature', 'vertices': 100,
            'bones': [{'name': name, 'parent': parent, 'matrixLocal': list(range(16))}
                      for name, parent in parents.items()],
            'influencedBones': list(influences)}


class UnifiedHouseRig(unittest.TestCase):
    def test_api_projects_current_ownership_without_changing_authored_bones(self):
        authored = {'schemaVersion': 1, 'meshes': [entry('house'), entry('door', ['door_01_hinge_socket'])]}
        snapshot = copy.deepcopy(authored)
        response = publication_analysis(authored)
        self.assertEqual(authored, snapshot)
        self.assertEqual(len(response['meshes'][0]['publicationBones']), 2)
        self.assertEqual(len(response['meshes'][1]['publicationBones']), 5)
        self.assertEqual(len(response['meshes'][1]['bones']), 7)

    @unittest.skipUnless(shutil.which('node'), 'Node required for UI behavior test')
    def test_ui_uses_server_projection_for_unified_rig(self):
        projected = publication_analysis({'meshes': [entry('house'), entry('door', ['door_01_hinge_socket'])]})
        code = r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const ctx=vm.createContext({window:{},localStorage:{getItem(){return null},setItem(){}},
 $(){return {addEventListener(){}}},request(){},toast(){},esc(value){return String(value??'')}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const source=JSON.parse(process.argv[2]);
const actual=source.meshes.map(p=>vm.runInContext('realEstatePublishedBones',ctx)(p).length);
assert.deepEqual(actual,[2,5]);
'''
        result = subprocess.run([shutil.which('node'), '-e', code,
            str(ROOT/'system/control-center/static/real-estate.js'), json.dumps(projected)],
            capture_output=True, text=True, encoding='utf8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_house_and_door_own_disjoint_bones_without_mutating_manifest(self):
        house, door = entry('house'), entry('door', ['door_01_hinge_socket'])
        before = copy.deepcopy([house, door])
        house_names = {b['name'] for b in publish_bones_for_mesh(house)}
        door_names = {b['name'] for b in publish_bones_for_mesh(door)}
        self.assertEqual(house_names, {'land_spawn_01_socket', 'chest_01_socket'})
        self.assertEqual(house_names & door_names, set())
        self.assertEqual(house_names | door_names, {b['name'] for b in house['bones']})
        self.assertIn('door_extra_tip', door_names)
        self.assertEqual([house, door], before)

    def test_static_parts_drop_bones_and_skinned_parts_keep_ancestors(self):
        for name in ('col_mesh', 'restoration', 'window_frames_glass', 'structures_01'):
            self.assertEqual(publish_bones_for_mesh(entry(name)), [])
        kept = publish_bones_for_mesh(entry('moving_handle', ['door_extra_tip']))
        self.assertEqual({b['name'] for b in kept}, {
            'door_01_hinge_socket', 'door_01_padlock_01_socket', 'door_extra_tip'})

    def test_unified_door_has_no_separate_armature_warning(self):
        warnings = warnings_for_analysis({'meshes': [entry('house'), entry('door', ['door_01_hinge_socket'])]})
        self.assertEqual(warnings, [])

    def test_staged_subset_is_checked_for_names_parents_and_rest(self):
        source = entry('door', ['door_01_hinge_socket'])
        actual = copy.deepcopy(source)
        actual['bones'] = publish_bones_for_mesh(actual)
        actual['influencedBones'] = [b['name'] for b in actual['bones']]
        assert_rig_survived({'meshes': [source]}, {'meshes': [actual]}, 'door')
        broken = copy.deepcopy(actual)
        broken['bones'][1]['matrixLocal'][12] += 1
        with self.assertRaisesRegex(ValueError, 'rest pose'):
            assert_rig_survived({'meshes': [source]}, {'meshes': [broken]}, 'door')
        with self.assertRaisesRegex(ValueError, 'changed bone names'):
            assert_rig_survived({'meshes': [source]}, {'meshes': [source]}, 'door')

    def test_reject_house_weighted_to_door_and_cyclic_ancestors(self):
        with self.assertRaisesRegex(ValueError, 'house geometry'):
            publish_bones_for_mesh(entry('house', ['door_01_hinge_socket']))
        cyclic = entry('door', ['door_01_hinge_socket'])
        next(b for b in cyclic['bones'] if b['name'] == 'door_01_hinge_socket')['parent'] = 'door_extra_tip'
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            publish_bones_for_mesh(cyclic)

    def test_legacy_separate_rigs_remain_supported(self):
        legacy = entry('door', ['door_01_hinge_socket'])
        legacy['armature'] = 'door_armature'
        self.assertEqual(publish_bones_for_mesh(legacy), legacy['bones'])
        no_door = entry('house')
        no_door['bones'] = no_door['bones'][:2]
        self.assertEqual(publish_bones_for_mesh(no_door), no_door['bones'])


if __name__ == '__main__':
    unittest.main()
