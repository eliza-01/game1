"""M348U: Studio selection hygiene (source-contract regression; not a Studio runtime test)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class CollisionSelectionM348U(unittest.TestCase):
    def test_generated_items_are_skipped_and_never_captured(self):
        source = (ROOT/'system/studio-plugin/modules/StudioLocationCollisionAuthoring.luau').read_text(encoding='utf-8')
        start = source.index('local function selectedModel(')
        end = source.index('local function acceptableId', start)
        method = source[start:end]
        self.assertIn('local picked = selection:Get()', method)
        self.assertIn('ignoredGenerated += 1', method)
        self.assertIn('item:GetAttribute("Game1LocationCollisionOwned") == true', method)
        self.assertIn('item.Name:sub(1, 17) == "__Game1Collision_"', method)
        self.assertIn('elseif item:IsA("BasePart") and (', method)
        self.assertNotIn('error("Do not Capture generated __Game1Collision_', method)
        self.assertIn('table.insert(parts, item)', method)
        self.assertIn('if needParts and (#parts < 1 or #parts > MAX_PARTS)', method)
        self.assertIn('Studio Selection:Get() returned %d objects', method)
        self.assertNotIn('root:GetDescendants()', method)
        self.assertNotIn('selection:Set(', method)

    def test_no_fallback_to_generated_when_no_authored_parts(self):
        source = (ROOT/'system/studio-plugin/modules/StudioLocationCollisionAuthoring.luau').read_text(encoding='utf-8')
        self.assertIn('Select the Location Model together with 1..256 ORIGINAL collision Parts.', source)
        self.assertIn('return root, parts, ignoredGenerated', source)
        self.assertIn('ignoredGenerated = ignoredGenerated', source)
        self.assertIn('return {blueprint = capture(model, parts, command)', source)

if __name__ == '__main__':
    unittest.main()
