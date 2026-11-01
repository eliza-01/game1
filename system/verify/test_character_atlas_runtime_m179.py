"""Regression contracts for binding a published Image Asset at character spawn.

Studio-only behavior is checked by studio_character_atlas_binding_m179.luau.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / 'src/server/character/CharacterAssemblyBuilder.luau'
BINDER = ROOT / 'src/server/character/CharacterAtlasBinder.luau'
REGISTRY = ROOT / 'assets/manifests/character-archetypes.json'


class CharacterAtlasRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = BUILDER.read_text(encoding='utf-8')
        cls.binder = BINDER.read_text(encoding='utf-8')

    def test_builder_delegates_texture_binding_to_narrow_module(self):
        self.assertIn('require(script.Parent:WaitForChild("CharacterAtlasBinder"))', self.builder)
        self.assertIn('CharacterAtlasBinder.Apply(mesh, part.atlas_image_id)', self.builder)
        self.assertNotIn('CreateSurfaceAppearanceAsync', self.builder)
        self.assertNotIn('Content.fromUri', self.builder)

    def test_published_image_uri_uses_supported_meshpart_texture_id(self):
        self.assertIn('mesh.TextureID = "rbxassetid://" .. imageId', self.binder)
        self.assertNotIn('CreateSurfaceAppearanceAsync', self.binder)
        self.assertNotIn('CreateEditableImage', self.binder)
        self.assertNotIn('.ColorMap', self.binder)

    def test_unbound_parts_preserve_imported_material(self):
        self.assertIn('if imageId == nil or imageId == "" then', self.binder)
        self.assertIn('return false', self.binder)
        self.assertIn('if child:IsA("SurfaceAppearance") then', self.binder)
        self.assertLess(self.binder.index('mesh.TextureID = '), self.binder.index('child:Destroy()'))

    def test_bad_image_id_rejected_before_mutating_mesh(self):
        self.assertIn('imageId:match("^[1-9]%d*$")', self.binder)
        self.assertLess(self.binder.index('imageId:match('), self.binder.index('mesh.TextureID = '))

    def test_active_recipe_pins_published_upper_atlas(self):
        manifest = json.loads(REGISTRY.read_text(encoding='utf-8'))
        active = manifest['activeArchetypeId']
        archetype = next(row for row in manifest['archetypes'] if row['id'] == active)
        if archetype.get('visualMode') != 'assembly':
            self.skipTest('currently active archetype is not an assembly')
        upper = archetype['assembly']['parts']['upper']
        image_id = upper.get('atlas_image_id', '')
        self.assertTrue(image_id == '' or (image_id.isascii() and image_id.isdecimal() and int(image_id) > 0))
        self.assertIn('fingerprint', archetype['assembly'])


if __name__ == '__main__':
    unittest.main()
