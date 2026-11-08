"""M267 regression contracts: placed Bone effects survive Location rig replacements.

Studio Play/Edit-mode is still required to validate Roblox's actual Bone,
ParticleEmitter, PointLight and transactional Undo behavior.
"""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


class LocationBoneEffectsM267(unittest.TestCase):
    def source(self, name):
        return (MODULES / name).read_text(encoding='utf-8')

    def test_portability_is_bone_local_effect_or_approved_attachment(self):
        source = self.source('StudioPlacedRigBoneEffects.luau')
        leaf = source.split('local function isLeafEffect(', 1)[1].split('\nend', 1)[0]
        eligibility = source.split('function BoneEffects.IsPortable(', 1)[1].split('\nend', 1)[0]
        self.assertIn('not item.Parent:IsA("Bone")', eligibility)
        self.assertIn('if isLeafEffect(item) then return true end', eligibility)
        self.assertIn('if item.ClassName ~= "Attachment" then return false end', eligibility)
        self.assertIn('for _, child in ipairs(item:GetChildren()) do', eligibility)
        self.assertIn('Bone inherits Attachment', source)
        self.assertIn('if not isLeafEffect(child) then return false end', eligibility)
        self.assertIn('#item:GetChildren() == 0', leaf)
        for kind in ('ParticleEmitter', 'PointLight', 'SpotLight', 'SurfaceLight'):
            self.assertIn('item:IsA("' + kind + '")', leaf)
        for unsafe in ('MeshPart', 'BasePart', 'Trail', 'Beam', 'Script', 'Weld', 'Motor6D'):
            self.assertNotIn('item:IsA("' + unsafe + '")', leaf)
        # No nested Attachment or child Script: only one level of leaf effects.
        self.assertNotIn('item:IsA("Attachment")', leaf)

    def test_attachment_is_copied_as_unit_with_transform_and_children(self):
        source = self.source('StudioPlacedRigBoneEffects.luau')
        method = source.split('function BoneEffects.CopyToIncoming(', 1)[1].split('\nend', 1)[0]
        self.assertIn('if BoneEffects.IsPortable(item) then', method)
        self.assertIn('nodeCount += 1 + #item:GetChildren()', method)
        self.assertIn('local clone = item:Clone()', method)
        self.assertIn('clone.Parent = destination', method)
        self.assertNotIn('for _, effect in ipairs(item:GetChildren())', method)
        self.assertIn('only top-level', source.lower())

    def test_historical_geometry_still_fails_closed_for_unknown_descendants(self):
        history = self.source('StudioPublishedMeshHistory.luau')
        body = history.split('function Inventory.VerifyChildren(', 1)[1].split('\nend', 1)[0]
        self.assertIn('local expectedTree = signatures(oldChildren)', body)
        self.assertIn('local actualTree = signatures(children)', body)
        self.assertIn('if actualTree[path] ~= count then', body)
        self.assertIn('unverified placed rig descendant; no Place geometry modified', body)
        self.assertIn('BoneEffects.IsPortable(item)', body)
        self.assertIn('item:IsA("SurfaceAppearance")', body)
        # MeshPart provenance and exact physical-part inventory are unchanged.
        self.assertIn('actualMeshes[mid] ~= count', body)
        self.assertIn('actualOtherParts[className] ~= count', body)

    def test_effects_cloned_on_staged_bone_not_moved_from_live_place(self):
        source = self.source('StudioPlacedRigBoneEffects.luau')
        method = source.split('function BoneEffects.CopyToIncoming(', 1)[1].split('\nend', 1)[0]
        self.assertLess(method.index('if #portable == 0 then return 0 end'),
                        method.index('local oldBones = bones(outgoing)'))
        self.assertIn('local newBones = bones(incoming)', method)
        self.assertIn('local key = boneKey(parent)', method)
        self.assertIn('if not destination then', method)
        self.assertIn('if destination:FindFirstChild(item.Name) then', method)
        self.assertIn('local clone = item:Clone()', method)
        self.assertIn('clone.Parent = destination', method)
        self.assertNotIn('item.Parent = destination', method)
        self.assertIn('MAX_EFFECTS_PER_RIG', method)
        self.assertIn('nodeCount > MAX_EFFECTS_PER_RIG', method)
        self.assertIn('table.concat(names, "\\0")', source)

    def test_scoped_and_registry_sync_copy_effects_before_transaction(self):
        for name, proof, prepare in (
            ('DecoPlacedAssetSync.luau', 'History.VerifyChildren(previousPublished,previousChildren)',
             'RigSwap.Prepare(model, previousChildren, rigChildren(stage),'),
            ('StudioPlaceRegistrySync.luau', 'History.VerifyChildren(previous,oldParts)',
             'RigSwap.Prepare(root,oldParts,rigChildren(stage),'),
        ):
            with self.subTest(sync=name):
                source = self.source(name)
                self.assertIn('require(script.Parent.StudioPlacedRigBoneEffects)', source)
                self.assertLess(source.index(proof), source.index('BoneEffects.CopyToIncoming('))
                self.assertLess(source.index('BoneEffects.CopyToIncoming('), source.index(prepare))
                self.assertIn('RigSwap.Rollback(', source)
                self.assertIn('RigSwap.Finalize(', source)

    def test_plugin_contains_effect_module_and_installer_checks(self):
        project = json.loads((ROOT/'system/studio-plugin/plugin.project.json').read_text('utf-8'))
        self.assertEqual(project['tree']['modules']['StudioPlacedRigBoneEffects']['$path'],
                         'modules/StudioPlacedRigBoneEffects.luau')
        install = (ROOT/'system/studio-plugin/install.ps1').read_text('utf-8')
        self.assertIn("'StudioPlacedRigBoneEffects'", install)
        source = self.source('StudioPlacedRigBoneEffects.luau')
        self.assertIn('return table.freeze(BoneEffects)', source)


if __name__ == '__main__':
    unittest.main()
