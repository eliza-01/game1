"""M346 is superseded by M347: source Model pivot + chosen NEW asset anchor."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class TargetAnchorM347Compatibility(unittest.TestCase):
    def test_new_published_asset_supplies_the_pivot_choices(self):
        code = (ROOT/'system/studio-plugin/modules/StudioLocationInstanceReplace.luau').read_text(encoding='utf-8')
        self.assertIn('local function anchorOptions(target:',code)
        self.assertIn('return anchorOptions(template)',code)
        self.assertIn('local function selectedTargetAnchor(target:',code)
        self.assertIn('positionAtSource(clone,old.geometry.frame,anchorId,approved)',code)
        self.assertNotIn('local function sourceAnchor(',code)
        self.assertNotIn('anchorOptions(states)',code)

    def test_source_model_frame_and_source_scale_are_immutable(self):
        code = (ROOT/'system/studio-plugin/modules/StudioLocationInstanceReplace.luau').read_text(encoding='utf-8')
        for text in ('frame=root:GetPivot(), scale=root:GetScale()',
                     'anchors=meshAnchors(root)', 'not sameFrame(anchor.frame,previous.frame)',
                     'clone:ScaleTo(old.scale)', 'selectedTargetAnchor(clone,anchorId,approved)',
                     'if not unchanged(state)', 'not current.approved[command.anchorId]'):
            self.assertIn(text,code)

    def test_ui_uses_old_model_as_destination_and_new_asset_as_source(self):
        html = (ROOT/'system/control-center/static/index.html').read_text(encoding='utf-8')
        js = (ROOT/'system/control-center/static/location-instance-manager.js').read_text(encoding='utf-8')
        self.assertIn('Опорный Pivot нового ассета',html)
        self.assertIn('Pivot исходной Model',html)
        self.assertIn('Pivot новой Model',js)
        self.assertIn('Pivot исходной Model ←',js)
        self.assertIn('location-instance-manager.js?v=351',html)
        self.assertNotIn('Опорный Pivot старого экземпляра',html)

if __name__ == '__main__': unittest.main()
