"""M156: FBX replacement keeps authored house pivot, not geometry centre."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[2]
PLUG=ROOT/'system/studio-plugin'
MODULES=PLUG/'modules'

class PivotSyncM156(unittest.TestCase):
    def test_shared_author_pivot_resolver_is_registered(self):
        helper=(MODULES/'StudioRealEstateHouseFrame.luau').read_text('utf-8')
        self.assertIn('target:GetPivot() * source:GetPivot():Inverse()',helper)
        self.assertIn('targetPivot * sourceAnchor:GetPivot():Inverse()',helper)
        self.assertIn('rig:PivotTo(offset * rig:GetPivot())',helper)
        self.assertIn('authored house pivot could not be aligned',helper)
        self.assertNotIn('source.CFrame',helper)
        self.assertNotIn('target.CFrame',helper)
        project=json.loads((PLUG/'plugin.project.json').read_text())
        self.assertEqual(project['tree']['modules']['StudioRealEstateHouseFrame']['$path'],
                         'modules/StudioRealEstateHouseFrame.luau')
        self.assertIn("'StudioRealEstateHouseFrame'",(PLUG/'install.ps1').read_text())

    def test_targeted_swap_aligns_old_to_new_template_and_placed(self):
        src=(MODULES/'StudioRealEstatePartSync.luau').read_text('utf-8')
        self.assertIn('HouseFrame.Align(imported, mesh, oldHouse:GetPivot(), "template house")',src)
        self.assertIn('HouseFrame.Align(staged, stagedHouse, oldHouse:GetPivot(), "placed house")',src)
        self.assertIn('HouseFrame.Relative(referenceHouse, placed)',src)
        self.assertNotIn('placed.CFrame * referenceHouse.CFrame:Inverse()',src)
        self.assertIn('if part == "door" then placedOld:GetPivot()',src)

    def test_full_and_collision_sync_share_author_origin(self):
        full=(MODULES/'StudioRealEstateModel.luau').read_text('utf-8')
        visual=(MODULES/'StudioRealEstatePlacedVisualSync.luau').read_text('utf-8')
        collision=(MODULES/'StudioRealEstatePlacedCollisionSync.luau').read_text('utf-8')
        self.assertIn('HouseFrame.Align(wrapper, meshes.house, previousHouse:GetPivot()',full)
        self.assertIn('HouseFrame.Relative(sourceHouse, placedHouse)',visual)
        self.assertIn('HouseFrame.Relative(referenceHouse, placedHouse)',collision)
        for source in (visual,collision):
            self.assertNotIn('placedHouse.CFrame *',source)
        self.assertIn('placed visual house origin would shift',visual)

    def test_house_keeps_static_physics_but_door_is_unchanged(self):
        physics=(MODULES/'StudioRealEstateCollisionPolicy.luau').read_text('utf-8')
        self.assertIn('if string.lower(name) == "house" then',physics)
        self.assertIn('mesh.Anchored = true',physics)
        self.assertNotIn('if string.lower(name) == "door"',physics)

if __name__=='__main__': unittest.main()
