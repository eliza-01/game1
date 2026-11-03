"""M210: upper-body bridge selection follows actual registered rig topology.

These are source and authored-skeleton contract checks; real Bone.Transform
blending and track loading still require a Roblox Studio Play test.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / 'assets/manifests/character-archetypes.json').read_text(encoding='utf-8'))
ANIMATION = ROOT / 'src/client/character/animation'
BRIDGE = (ANIMATION / 'CharacterUpperBodyRig.luau').read_text(encoding='utf-8')
COMPOSER = (ANIMATION / 'AttackUpperBodyComposer.luau').read_text(encoding='utf-8')
CONTROLLER = (ANIMATION / 'CharacterAnimationController.luau').read_text(encoding='utf-8')
AIM = (ROOT / 'src/client/combat/AimPoseController.luau').read_text(encoding='utf-8')
INPUT = (ROOT / 'src/client/combat/AttackController.luau').read_text(encoding='utf-8')
MOVEMENT = (ROOT / 'src/client/character/MovementController.luau').read_text(encoding='utf-8')


def authored_bridge(archetype):
    bones = {row['name']: row.get('parent', '') for row in archetype['skeleton']['bones']}
    spine = lambda name: bool(re.fullmatch(r'spine(?:[._]\d+)?', name.lower()))
    candidates = [name for name, parent in bones.items()
                  if spine(name) and spine(parent) and not spine(bones[parent])]
    assert len(candidates) == 1, (archetype['id'], candidates)
    return bones, candidates[0]


class CharacterAttackLocomotionM210(unittest.TestCase):
    def test_both_registered_rigs_have_single_safe_upper_body_bridge(self):
        arches = {row['id']: row for row in MANIFEST['archetypes']}
        self.assertIn('human_male', arches)
        self.assertIn('human_female', arches)
        expected = {'human_female': 'spine.001', 'human_male': 'spine_02'}
        for archetype_id, bridge_name in expected.items():
            bones, bridge = authored_bridge(arches[archetype_id])
            with self.subTest(character=archetype_id):
                self.assertEqual(bridge, bridge_name)
                self.assertTrue(any(parent == bridge for parent in bones.values()))
                # Every leg/pelvis branch must be disjoint from the chosen bridge.
                for name in bones:
                    if not any(token in name.lower() for token in
                               ('pelvis', 'hip', 'thigh', 'shin', 'calf', 'foot', 'toe', 'leg')):
                        continue
                    ancestor = name
                    while ancestor and ancestor != bridge:
                        ancestor = bones.get(ancestor, '')
                    self.assertNotEqual(ancestor, bridge, name)

    def test_bridge_is_selected_by_hierarchy_with_lower_body_safety(self):
        self.assertIn('^spine[._]%d+$', BRIDGE)
        self.assertIn('if isSpineBone(parent)', BRIDGE)
        self.assertIn('if not isSpineBone(grandparent)', BRIDGE)
        self.assertIn('multiple upper-body spine branches found', BRIDGE)
        self.assertIn('hasLowerBodyDescendants(candidate)', BRIDGE)
        self.assertNotIn('if archetype == "human_male"', BRIDGE)

    def test_composition_and_aim_share_same_bridge_policy(self):
        self.assertIn('CharacterUpperBodyRig.ResolveBridge(visual)', COMPOSER)
        self.assertIn('CharacterUpperBodyRig.ResolveBridge(visual)', AIM)
        self.assertNotIn('FindFirstChild("spine.001", true)', COMPOSER)
        self.assertNotIn('PREFERRED_SPINE_NAMES', AIM)
        self.assertIn('RunService.PreSimulation:Connect(step)', COMPOSER)
        self.assertIn('AimPoseController.StepAfterExternalPose(deltaTime)', COMPOSER)

    def test_attack_never_falls_back_to_full_body_when_composer_fails(self):
        self.assertIn('if slot == "attack" then nil else cache:Get(descriptor)', CONTROLLER)
        self.assertIn('if not composedTrack then', CONTROLLER)
        self.assertIn('return nil', CONTROLLER.split('if not composedTrack then', 1)[1].split('track = composedTrack', 1)[0])
        self.assertNotIn('using full-body fallback', CONTROLLER)
        self.assertIn('if not action then', INPUT)  # No AttackIntent on failure

    def test_live_legs_stay_on_locomotion_when_moving_or_stopping(self):
        self.assertIn('attackLowerBodyActive = true', CONTROLLER)
        self.assertIn('return "combat_idle"', CONTROLLER)
        self.assertIn('return if configuredMode == "walk" then "walk" else "run"', CONTROLLER)
        self.assertIn('GetAttributeChangedSignal(attribute):Connect(refreshLoop)', CONTROLLER)
        self.assertIn('character:SetAttribute("AnimationAttackLowerBodySlot", slot)', CONTROLLER)
        self.assertIn('AnimationAttackBridgeBone', CONTROLLER)
        self.assertIn('AttackUpperBodyComposer.GetBridgeName()', CONTROLLER)
        self.assertIn('character:SetAttribute("MovementState", derivedMovement)', MOVEMENT)
        self.assertIn('movementController.BeginAttackMovement', INPUT)

    def test_load_wait_does_not_consume_gameplay_attack_window(self):
        self.assertIn('local actionStartedAt = os.clock()', CONTROLLER)
        self.assertIn('actionStartedAt + runtimeDuration', CONTROLLER)
        self.assertIn('attackComposePending = true', CONTROLLER)
        self.assertIn('currentActionToken == pendingToken and not lifeTransition', CONTROLLER)
        self.assertIn('if stillValid and not stillValid() then', COMPOSER)
        self.assertIn('attack preparation cancelled during animation load', COMPOSER)


if __name__ == '__main__':
    unittest.main()
