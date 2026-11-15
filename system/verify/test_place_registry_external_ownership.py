"""Regression contract: LandscapePainter/Package models cannot become Deco placements."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services.place_registry.catalog import validate_report
OWNERS=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryExternalOwners.luau').read_text(encoding='utf-8')
SCAN=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryInventory.luau').read_text(encoding='utf-8')
BRIDGE=(ROOT/'system/studio-plugin/modules/StudioPlaceRegistryCommands.luau').read_text(encoding='utf-8')

class TestExternalOwnerInventory(unittest.TestCase):
    def test_strong_owner_identity_not_paths_or_mesh_ids(self):
        for evidence in ('LandscapeAuthoringTool', 'Game1LandscapePainter', 'LandscapeAssetSlug',
                         'PackageLink', 'FindFirstChildOfClass', 'StudioPlaceRegistryExternalOwners'):
            self.assertIn(evidence, OWNERS + SCAN)
        self.assertIn('if external then', SCAN)
        self.assertIn('continue', SCAN.split('if external then',1)[1].split('local eligible=',1)[0])
        self.assertIn('protected=scan.protected', BRIDGE)
        self.assertIn('externalSeen[external.model]', SCAN)
        self.assertNotIn('SetAttribute(', OWNERS)
        self.assertNotIn(':Destroy()', OWNERS)

    def test_validator_rejects_forged_protected_rows(self):
        catalog={'items':[{'slug':'lantern_03'}]}
        row={'kind':'landscape_attachment','slug':'lantern_03',
             'name':'lantern_03_abc','path':'Workspace.some.lantern_03_abc',
             'ownerPath':'Workspace.some.lantern_03_abc','authorSlug':'lantern_03',
             'branchStrokeId':'uuid-branch','anchorKind':'stem',
             'reason':'LandscapePainter authored attachment',
             'review':False,'protectedFromRuntime':True}
        def valid(data):return validate_report({'schemaVersion':1,'placements':[],'protected':data},catalog)
        self.assertEqual(valid([row]),[])
        for key, value in [('kind','foreign'),('slug','unregistered'),('path',''),
                           ('protectedFromRuntime',False),('review','no'),('authorSlug','')]:
            bad=dict(row);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): valid([bad])
        # Incomplete authoring metadata must remain protected and visible for
        # review, not make the entire Place Scan fail.
        incomplete=dict(row,authorSlug='',review=True,reason='Owner metadata incomplete')
        self.assertEqual(valid([incomplete]),[])
        with self.assertRaises(ValueError): valid([row,row])
        with self.assertRaises(ValueError): valid('not a list')
        # Old snapshots from earlier Studio bridge versions are accepted read-only.
        self.assertEqual(validate_report({'schemaVersion':1,'placements':[]},catalog),[])

if __name__=='__main__':unittest.main()
