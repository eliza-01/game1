"""M481: authored spawn parity and right-side responsive creation UI contracts."""
import json
import tempfile
import shutil
import math
import re
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore
from services.character_creation_settings import DEFAULTS,normalize_character_creation
from migrations.m481_creation_scene_points import migrate,POINTS

class CreationSceneM481(unittest.TestCase):
    def test_authored_spawns_exact_and_distinct(self):
        self.assertEqual(POINTS['male']['position'],[179.449,-314.025,176.096])
        self.assertEqual(POINTS['female']['position'],[177.64,-314.025,167.78])
        self.assertAlmostEqual(POINTS['male']['rotationDegrees'][1],-35.501)
        self.assertAlmostEqual(POINTS['female']['rotationDegrees'][1],-93.433)
        self.assertGreater(math.dist(POINTS['male']['position'],POINTS['female']['position']),8)

    def test_migration_updates_registry_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'assets/manifests').mkdir(parents=True)
            source=json.loads((ROOT/'assets/manifests/options.json').read_text())
            source['characterCreation'].pop('spawnPoints',None)
            source['characterCreation'].pop('useStudioSpawnMarkers',None)
            source['characterCreation']['desktopPanelWidthPx']=340
            source['characterCreation']['mobilePanelWidthPx']=290
            (root/'assets/manifests/options.json').write_text(json.dumps(source),encoding='utf8')
            result=migrate(root)
            self.assertEqual(result['spawnPoints'],POINTS)
            self.assertFalse(result['useStudioSpawnMarkers'])
            self.assertEqual(result['desktopPanelWidthPx'],460)
            self.assertEqual(result['mobilePanelWidthPx'],330)
            registry=(root/'src/shared/GameOptionsRegistry.luau').read_text()
            for literal in ('spawnPoints = table.freeze({','useStudioSpawnMarkers = false',
                '179.449','-314.025','176.096','177.64','167.78','-93.433'):
                self.assertIn(literal,registry)
            backups=list((root/'assets/manifests').glob('options.json.pre-m481-*.bak'))
            self.assertEqual(len(backups),1)
            self.assertEqual(migrate(root),result)
            self.assertEqual(len(list((root/'assets/manifests').glob('options.json.pre-m481-*.bak'))),1)

    def test_migration_does_not_overwrite_authored_point(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'assets/manifests').mkdir(parents=True)
            data=json.loads((ROOT/'assets/manifests/options.json').read_text())
            data['characterCreation']['spawnPoints']={
              'male':{'position':[123.0, -10.0, 8.0],'rotationDegrees':[0.0, 4.0, 0.0]},
              'female':{'position':[0.0,0.0,0.0],'rotationDegrees':[0.0,0.0,0.0]}}
            (root/'assets/manifests/options.json').write_text(json.dumps(data),encoding='utf8')
            result=migrate(root)
            self.assertEqual(result['spawnPoints']['male']['position'],[123.0,-10.0,8.0])
            self.assertEqual(result['spawnPoints']['female'],POINTS['female'])

    def test_preview_has_fail_closed_placement_and_no_unbounded_fallback(self):
        code=(ROOT/'src/client/character/CharacterCreationPreviewController.luau').read_text()
        self.assertIn('if not target or not other then',code)
        self.assertIn('Male/Female spawn points overlap',code)
        self.assertIn('instance:PivotTo(target)',code)
        self.assertNotIn('local p = row.position or {0, 0, 0}',code)
        self.assertIn('point:GetPivot()',code)

    def test_presentation_splits_navigation_and_scrollable_content(self):
        shell=(ROOT/'src/client/character/CharacterCreationPanel.luau').read_text()
        controller=(ROOT/'src/client/character/CharacterCreationController.luau').read_text()
        content=(ROOT/'src/client/character/CharacterCreationAppearanceView.luau').read_text()
        self.assertIn('root.AnchorPoint = Vector2.new(1, 0.5)',shell)
        self.assertIn('local content = Instance.new("ScrollingFrame")',shell)
        self.assertIn('footer.AnchorPoint = Vector2.new(0, 1)',shell)
        self.assertIn('root.Name = "CharacterCreationPanel"',shell)
        self.assertIn('activeTab = nil',controller)
        self.assertIn('Panel.UpdateTabs',controller)
        self.assertIn('controls.tabs[category].Activated',controller)
        self.assertIn('while previewRequestBusy do',controller)
        self.assertIn('previewRequestBusy = false',controller)
        self.assertIn('local group = activeTab', content)
        for taboo in ('"upper"','"lower"','"gloves"','"boots"'):
            self.assertNotIn(taboo,content)

    def test_existing_options_and_categories_preserved(self):
        options=json.loads((ROOT/'assets/manifests/options.json').read_text())
        self.assertTrue(options['characterCreation']['enabled'])
        self.assertEqual(len(options['characterCreation']['views']),5)
        for group in ('healthUi','flora','socketRanges','rotations'):
            self.assertIn(group,options)

if __name__=='__main__': unittest.main()
