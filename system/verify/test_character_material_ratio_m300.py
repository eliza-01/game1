"""M300: recipe-level per-part materials and Studio movement ratio overrides."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
def load(name):return (ROOT/name).read_text(encoding='utf-8')

class MaterialsAndRatioM300(unittest.TestCase):
    def test_material_choices_are_shared(self):
        py=load('system/control-center/character_core/assemblies.py')
        js=load('system/control-center/static/character-assemblies.js')
        for material in ('Glass','Metal','SmoothPlastic','Plaster','Slate','Sandstone',
                         'Sand','Cardboard','Rubber','Limestone','Granite'):
            self.assertIn(repr(material),py)
            self.assertIn("'"+material+"'",js)
        self.assertIn('part_materials=selected_materials',py)
        self.assertIn('record[\'material\']=selected_materials[slot]',py)
    def test_parts_receive_runtime_material_without_pivot_changes(self):
        source=load('src/server/character/CharacterAssemblyBuilder.luau')
        self.assertIn('mesh.Material = selected',source)
        self.assertIn('visual.Material = selected',source)
        self.assertNotIn('mesh.PivotOffset =',source)
    def test_selects_are_editable_and_persisted(self):
        source=load('system/control-center/static/character-assemblies.js')
        self.assertIn("control.onchange=()=>{update();autoSaveMaterial();};",source)
        self.assertIn('part_materials:Object.fromEntries',source)
        self.assertIn('fillMaterials(r.part_materials||{})',source)
    def test_debug_units_win_over_custom_clips_only_for_locomotion(self):
        source=load('src/shared/animation/AnimationSpeedScaling.luau')
        self.assertIn('debugUnitsPerPercent ~= nil and (normalizedChannel == "run" or normalizedChannel == "walk")',source)
        self.assertNotIn('debugUnitsPerPercent ~= nil and not isCustom',source)
    def test_debug_updates_playing_tracks(self):
        source=load('src/server/dev/MovementDebugService.luau')
        self.assertIn('GetPlayingAnimationTracks()',source)
        self.assertIn('local scale = AnimationSpeedScaling.ResolveScaleForAnimation',source)
        self.assertIn('item.track:AdjustSpeed(actualSpeed)',source)
    def test_speed_ui_is_compact(self):
        source=load('system/control-center/static/animation-speed.js')
        self.assertIn('animation-speed-compact',source)
        self.assertNotIn('animation-speed-readonly',source)

if __name__=='__main__':unittest.main()
