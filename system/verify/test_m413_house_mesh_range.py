"""M413: Real Estate source/published fingerprints and independent Test Loadout range."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class HouseMeshRangeM413(unittest.TestCase):
    def test_real_estate_workflow_uses_published_fingerprint(self):
        workflow = (ROOT/'system/control-center/static/real-estate-mesh-workflow.js').read_text(encoding='utf-8')
        self.assertIn('row.rigPublicationHashes?.[part]', workflow)
        self.assertNotIn('rig.publishedSha256===row.rigSourceHashes', workflow)
        self.assertIn("realEstatePublish('model:'+part)", workflow)

    def test_source_is_acknowledged_only_after_correct_mesh_revision_committed(self):
        ui = (ROOT/'system/control-center/static/real-estate.js').read_text(encoding='utf-8')
        self.assertIn('saved?.meshSources?.[part]?.sha256!==preview.sourceSha256', ui)
        self.assertIn('saved?.rigSourceHashes?.[part]!==preview.sourceSha256', ui)
        self.assertIn('result.job.scope!==scope', ui)

    def test_range_is_client_only_and_does_not_affect_combat(self):
        path = ROOT/'src/client/dev/DebugRangeCylinder.luau'
        source = path.read_text(encoding='utf-8')
        self.assertIn('local HEIGHT = 200', source)
        self.assertIn('cylinder.Transparency = 0.6', source)
        self.assertIn('Enum.PartType.Cylinder', source)
        for term in ['CanCollide = false', 'CanTouch = false', 'CanQuery = false',
                     'RunService.RenderStepped:Connect', 'CFrame.Angles(0, 0, math.rad(90))',
                     'self._part.Parent = nil']:
            self.assertIn(term, source)
        for forbidden in ['InvokeServer', 'FireServer', 'GetDescendants()', 'RemoteEvent']:
            self.assertNotIn(forbidden, source)
        loadout = (ROOT/'src/client/dev/TestLoadoutController.luau').read_text(encoding='utf-8')
        self.assertIn('local rangeSteps = {-50, -10, -5, 5, 10, 50}', loadout)
        self.assertIn('rangeBox.FocusLost:Connect', loadout)
        self.assertIn('rangePreview:SetVisible(rangeVisible)', loadout)
        self.assertIn('rangePreview:Destroy()', loadout)

    def test_real_estate_js_behaviour(self):
        result = subprocess.run(['node','system/verify/real_estate_mesh_publication_m413.js'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+'\n'+result.stderr)

if __name__ == '__main__':
    unittest.main()
