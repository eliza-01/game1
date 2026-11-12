"""M311: focused editor-preview regression checks; not a Studio rendering test."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUNER = ROOT / 'system/studio-plugin/fire-tuner/fire_bone.lua'
RUNTIME = ROOT / 'src/client/world/BoneOrbController.luau'

class FireflyEditorPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tuner = TUNER.read_text(encoding='utf-8')
        cls.runtime = RUNTIME.read_text(encoding='utf-8')

    def test_selected_bone_remains_read_only(self):
        bind = self.tuner.split('local function bindSelected()',1)[1].split('selectButton.MouseButton1Click',1)[0]
        for invalid in ('createFirefly()', 'createFire()', 'createLight()', ':SetAttribute(', 'AddTag('):
            self.assertNotIn(invalid, bind)

    def test_preview_only_in_studio_edit_and_when_visible(self):
        self.assertIn('RunService:IsEdit()', self.tuner)
        self.assertIn('widget.Enabled', self.tuner)
        self.assertIn('currentOrb:GetAttribute("Enabled") == true', self.tuner)
        self.assertIn('currentOrb.Parent == currentBone', self.tuner)
        self.assertIn('Live Preview · Studio Edit', self.tuner)
        self.assertIn('previewAccumulator < 1 / 30', self.tuner)
        self.assertIn('RunService.Heartbeat:Connect', self.tuner)

    def test_preview_non_saved_and_no_duplicate_runtime_renderer(self):
        self.assertIn('part.Archivable = false', self.tuner)
        self.assertIn('light.Archivable = false', self.tuner)
        self.assertIn('part.Parent = camera', self.tuner)
        self.assertIn('part.CanCollide = false', self.tuner)
        self.assertIn('part.CanQuery = false', self.tuner)
        self.assertIn('part.Locked = true', self.tuner)
        self.assertIn('discardPreview()', self.tuner)
        self.assertIn('plugin.Unloading:Connect(function()', self.tuner)
        self.assertIn('previewConnection:Disconnect()', self.tuner)
        self.assertIn('widget:BindToClose(function()', self.tuner)
        self.assertNotIn('CollectionService:AddTag(part', self.tuner)
        self.assertNotIn('Instance.new("RopeConstraint")', self.tuner)

    def test_preview_parameters_match_in_game_controller(self):
        names=('BobFrequency','Lift','BobAmplitude','Drift','RoamRadius','RoamSpeed',
               'Radius','Brightness','Range','Color','Shadows')
        for name in names:
            with self.subTest(name=name):
                self.assertIn('orb:GetAttribute("'+name+'")', self.tuner)
                self.assertIn('attachment:GetAttribute("'+name+'")', self.runtime)
        self.assertIn('bone.TransformedWorldCFrame * orb.CFrame', self.tuner)
        self.assertIn('bone.TransformedWorldCFrame * attachment.CFrame', self.runtime)
        for suffix in ('0)', '17)', '37)'):
            self.assertIn('math.noise(seed, sampleTime, '+suffix, self.tuner)
            self.assertIn('math.noise(seed, sampleTime, '+suffix, self.runtime)

    def test_presets_and_tail_head_untouched(self):
        self.assertIn('local PRESET_KEY = "Game1_FireTuner_UserPresets_v1"', self.tuner)
        self.assertIn('local function capturePreset(name)', self.tuner)
        self.assertIn('local function applyPreset(data)', self.tuner)
        self.assertIn('Tail -> Head', self.tuner)

if __name__ == '__main__':
    unittest.main()
