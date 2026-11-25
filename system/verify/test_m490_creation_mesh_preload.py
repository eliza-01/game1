from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def src(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

class CreationMeshPreloadM490(unittest.TestCase):
    def test_preloader_collects_mesh_and_surface_assets(self):
        code = src('src/client/character/CharacterCreationMeshPreloader.luau')
        self.assertIn('local ContentProvider = game:GetService("ContentProvider")', code)
        self.assertIn('object:IsA("MeshPart")', code)
        self.assertIn('push(bucket, object.MeshId)', code)
        self.assertIn('push(bucket, object.TextureID)', code)
        self.assertIn('object:IsA("SurfaceAppearance")', code)
        self.assertIn('ContentProvider.PreloadAsync', code)
        self.assertIn('loaded[id] = true', code)

    def test_preview_waits_for_preload_before_parenting(self):
        code = src('src/client/character/CharacterCreationPreviewController.luau')
        self.assertIn('local MeshPreloader = require(script.Parent:WaitForChild("CharacterCreationMeshPreloader"))', code)
        preload = code.index('if not MeshPreloader.PreloadModel(instance, isCurrent, onPreloadProgress) then')
        parent = code.index('instance.Parent = self.folder')
        self.assertLess(preload, parent)

    def test_panel_has_progress_overlay_and_runner(self):
        code = src('src/client/character/CharacterCreationPanel.luau')
        self.assertIn('local function buildStickman(parent: Instance): Frame', code)
        self.assertIn('progressTrack.Name = "ProgressTrack"', code)
        self.assertIn('function Panel.SetLoading(views: any, busy: boolean, message: string, progress: number)', code)
        self.assertIn('views.overlayRunner.Position', code)

    def test_controller_bootstrap_tracks_initial_preview_loading(self):
        code = src('src/client/character/CharacterCreationController.luau')
        self.assertIn('local bootstrapPending: {[string]: boolean} = {}', code)
        self.assertIn('Language.Translate("creation.loading_appearance_assets")', code)
        self.assertIn('markBootstrapDone(id)', code)
        self.assertIn('bootstrapPending = {human_male = true, human_female = true}', code)

if __name__ == '__main__':
    unittest.main()
