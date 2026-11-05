"""M235: shared mesh pivot matching for multi-part Location Asset rigs.

Source-contract guard: executing CFrame/Bone operations requires Studio. Do not
mistake these checks for an Edit Mode geometry/transform smoke test.
"""
import json
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


class LocationAnchorM235(TestCase):
    @staticmethod
    def source(name):
        return (MODULES / name).read_text(encoding='utf-8')

    def test_shared_resolver_is_packaged_and_called_by_both_domains(self):
        project = json.loads((ROOT / 'system/studio-plugin/plugin.project.json').read_text('utf-8'))
        self.assertEqual(project['tree']['modules']['StudioAuthoringMeshAnchor']['$path'],
                         'modules/StudioAuthoringMeshAnchor.luau')
        deco = self.source('DecoPlacedAssetSync.luau')
        house = self.source('StudioRealEstateHouseFrame.luau')
        self.assertIn('require(script.Parent.StudioPublishedMeshHistory)', deco)
        self.assertIn('require(script.Parent.StudioAuthoringMeshAnchor)', house)
        self.assertIn('History.Provenance(model,previousPublished)', deco)
        self.assertNotIn('MeshAnchor.Match(', deco)
        self.assertIn('MeshAnchor.FindUniqueNamed(root, "house")', house)
        self.assertNotIn('unique MeshPart name required', deco)
        self.assertIn('StudioManagedRigSwap', deco)
        self.assertIn('stage:PivotTo(frame * stage:GetPivot())', deco)

    def test_multi_mesh_matches_choose_consistent_authoring_frame(self):
        code = self.source('StudioAuthoringMeshAnchor.luau')
        self.assertIn('if #matches == 1 then', code)
        self.assertIn('if count > support then', code)
        self.assertIn('if not winner or support < 2 then', code)
        self.assertIn('match.old:GetPivot() * match.new:GetPivot():Inverse()', code)
        self.assertIn('sameFrame(transform, other)', code)
        # A multi-mesh rig can have 2+ matching parts. A majority of matching
        # authoring frames is accepted, rather than the old exactly-one rule.
        self.assertNotIn('if #matches ~= 1 then', code)
        self.assertIn('return match.old, match.new, match.newPath', code)

    def test_colliding_names_do_not_guess_part_index(self):
        code = self.source('StudioAuthoringMeshAnchor.luau')
        self.assertIn('indexed[key] = false', code)
        self.assertIn('uniqueIndex(old, before, true)', code)
        self.assertIn('uniqueIndex(published, after, true)', code)
        self.assertIn('if #matches == 0 then', code)
        self.assertIn('uniqueIndex(old, before, false)', code)
        self.assertIn('no uniquely matching MeshPart path/name', code)
        self.assertIn('multiple MeshPart authoring pivots disagree', code)
        self.assertNotIn('table.sort(before', code)

    def test_retained_anchor_or_primary_part_precedes_heuristic(self):
        code = self.source('StudioAuthoringMeshAnchor.luau')
        self.assertIn('retainedPath ~= nil and type(retainedPath) ~= "string"', code)
        self.assertLess(code.index('if retainedPath and retainedPath ~= "" then\n        for _, match'),
                        code.index('local primary = old.PrimaryPart'))
        self.assertLess(code.index('local primary = old.PrimaryPart'),
                        code.index('if #matches == 1 then'))
        deco = self.source('DecoPlacedAssetSync.luau')
        self.assertIn('History.Provenance(model,previousPublished)', deco)
        self.assertIn('RigSwap.Prepare(model, previousChildren, nextChildren,', deco)
        self.assertNotIn('MeshAnchor.Match(', deco)
        self.assertIn('oldAnchorPath = model:GetAttribute("Game1DecoAuthoringAnchorPath")', deco)
        self.assertIn('model:SetAttribute("Game1DecoAuthoringAnchorPath", item.oldAnchorPath)', deco)

    def test_placed_root_is_not_replaced_and_audit_continues(self):
        deco = self.source('DecoPlacedAssetSync.luau')
        for unsafe in ('ApplyMesh(', 'model:Destroy()', 'model:PivotTo(', 'previous:Destroy()'):
            self.assertNotIn(unsafe, deco)
        self.assertLess(deco.index('RigSwap.Prepare(model, previousChildren, nextChildren,'),
                        deco.index('RigSwap.Commit(item.swap)'))
        self.assertIn('RigSwap.Rollback(item.swap)', deco)
        self.assertIn('Game1DecoSyncHistory', deco)
        self.assertIn('Game1DecoAssetSlug', deco)
