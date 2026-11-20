"""M389: per-mesh opaque atlas cleanup and verified Studio Sync completion.

These tests guard the Studio source contracts. Actual Roblox Instance behavior
requires an Edit-mode smoke test after installing the current Game1Bridge.
"""
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / 'system/studio-plugin/modules'


def source(name: str) -> str:
    return (MODULES / name).read_text(encoding='utf-8')


class M389LocationSurfaceCleanup(TestCase):
    def test_shared_policy_removes_all_stale_opaque_surfaces(self):
        shared = source('StudioTextureAppearance.luau')
        self.assertIn('for _, child in ipairs(mesh:GetChildren()) do', shared)
        self.assertIn('if child:IsA("SurfaceAppearance") then', shared)
        self.assertIn('local function removeSurfaces(mesh: MeshPart): boolean', shared)
        self.assertIn('removeSurfaces(mesh)\n        return true', shared)
        self.assertIn('if mesh.TextureID == uri and #allSurfaces == 0 then return false end', shared)
        self.assertIn('if not enabled then\n        return removeSurfaces(mesh)', shared)
        self.assertIn('if mesh.TextureID=="" and #allSurfaces==0', shared)
        self.assertIn('return #allSurfaces == 0', shared)
        self.assertIn('return #allSurfaces == 1', shared)

    def test_atomic_rollback_restores_all_original_surface_children(self):
        shared = source('StudioTextureAppearance.luau')
        self.assertIn('for _, appearance in ipairs(surfaces(mesh)) do', shared)
        self.assertIn('surfaceCopies=copies', shared)
        self.assertIn('for _, surface in ipairs(snapshot.surfaceCopies) do', shared)
        self.assertIn('pcall(StudioTextureAppearance.Restore,snapshot)', shared)
        self.assertIn('for _, extra in ipairs(allSurfaces) do', shared)

    def test_shared_is_current_and_new_publication_assert_final_policy(self):
        visual = source('StudioLocationVisualAppearance.luau')
        self.assertIn('Texture.AlphaCurrent(mesh, false)', visual)
        self.assertIn('Texture.AlphaCurrent(mesh, alpha)', visual)
        self.assertIn('function Visual.AssertCurrent(mesh: MeshPart, row: any)', visual)
        self.assertIn('if visual(mesh) and not Visual.IsCurrent(mesh, row)', visual)
        self.assertIn('Visual.AssertCurrent(item :: MeshPart,row)', visual)
        self.assertIn('Visual.ApplyModel(model,row)', source('DecoAssetLoader.luau'))

    def test_both_explicit_sync_paths_assert_written_appearance(self):
        direct = source('DecoPlacedAssetSync.luau')
        registry = source('StudioPlaceRegistrySync.luau')
        self.assertIn('Visual.AssertCurrent(change.part, row)', direct)
        self.assertIn('Visual.AssertCurrent(change.mesh, row)', direct)
        self.assertIn('Visual.AssertCurrent(change.mesh,row)', registry)
        self.assertIn('local setting=Visual.Settings(change.mesh,row)', registry)
        self.assertIn('if setting.appearanceMode=="material" then', registry)
        self.assertIn('Texture.ApplyAlpha(change.mesh,setting.alphaEnabled==true', registry)
        # Recheck scope: intentionally never modify unmanaged Workspace meshes.
        self.assertIn('and not chosenParts[part] then continue', direct)
        self.assertIn('if not ref.row.canSync or not ref.root then', registry)
