"""M257 supersedes legacy wrapper Repair: placement topology comes from published FBX."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
REPAIR=ROOT/'system/studio-plugin/modules/StudioPlaceRegistryRepair.luau'

class IdentityRepairOnly(unittest.TestCase):
    def test_repair_never_wraps_visual_or_moves_primary_part(self):
        src=REPAIR.read_text('utf-8')
        self.assertNotIn('Instance.new("Model")',src)
        self.assertNotIn('part.Parent=root',src)
        self.assertNotIn('restoreCol',src)
        self.assertNotIn('CarrierMigration',src)
        self.assertIn('model:GetPivot() ~= before.pivot',src)
        self.assertIn('model.PrimaryPart ~= before.primary',src)
    def test_repair_is_undo_recorded_and_rootpart_is_blocked(self):
        src=REPAIR.read_text('utf-8')
        self.assertIn('Импортный RootPart — требуется перепубликация FBX',src)
        self.assertIn('FinishRecording(recording, Enum.FinishRecordingOperation.Cancel)',src)
        self.assertIn('FinishRecording(recording,',src)

if __name__=='__main__': unittest.main()
