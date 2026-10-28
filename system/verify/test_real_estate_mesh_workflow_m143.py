"""M143: explicit, scoped workflow UI and honest Workspace sync acknowledgements."""
from pathlib import Path
import json
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
STATIC=ROOT/'system/control-center/static'
PLUGIN=ROOT/'system/studio-plugin'

class MeshWorkflowM143(unittest.TestCase):
    def test_modal_has_adjacent_replace_publish_sync_with_correct_types(self):
        js=(STATIC/'real-estate-mesh-workflow.js').read_text('utf-8')
        table=(STATIC/'real-estate.js').read_text('utf-8')
        html=(STATIC/'index.html').read_text('utf-8')
        self.assertIn('data-re-manage=', table)
        self.assertIn('realEstateMeshWorkflowOpen(', table)
        self.assertIn('real-estate-mesh-workflow.js', html)
        for control in ('data-mw-replace','data-mw-publish','data-mw-sync',
                        'data-mw-local','data-mw-save-image','data-mw-publish-image',
                        'data-mw-use-atlas','data-mw-republish-atlas'):
            self.assertIn(control,js)
        self.assertIn("realEstatePublish('model:'+part)",js)
        self.assertIn("realEstatePublish('image:'+part)",js)
        self.assertIn('Sync model · template + placed',js)
        self.assertNotIn('data-re-mesh-source=',table)
        self.assertNotIn('data-re-rig=',table)
        self.assertNotIn('republish ${esc(part)} rig',table)

    def test_picker_is_explicit_save_not_hidden_publish(self):
        js=(STATIC/'real-estate-mesh-workflow.js').read_text('utf-8')
        table=(STATIC/'real-estate.js').read_text('utf-8')
        self.assertIn('realEstateBrowseTexture(part)',js)
        self.assertIn('realEstateRegister()',js)
        self.assertIn('realEstateChooseAtlas(',js)
        self.assertNotIn('async function realEstateReplaceTexture(row,part)',table)
        self.assertIn('data-re-texture=',table)
        self.assertIn("realEstateMeshWorkflowOpen(row.slug,button.dataset.reTexture,'texture')",table)

    def test_atlas_selection_uses_persisted_binding_or_effective_image_id(self):
        js=(STATIC/'real-estate.js').read_text('utf-8')
        self.assertIn('Number(texture.atlasVariantId)===Number(variant.id)',js)
        self.assertIn('String(texture.assetId)===String(variant.published_id',js)
        self.assertIn('data-re-atlas-active',js)

    def test_no_silent_studio_success_toast_and_dismissable_notifications(self):
        js=(STATIC/'real-estate.js').read_text('utf-8')
        chars=(STATIC/'character-assets.js').read_text('utf-8')
        self.assertIn('workspaceModelsFound',js)
        self.assertIn('workspaceModelsUpdated',js)
        self.assertIn('Studio Sync diagnostics',js)
        self.assertIn('toast-close',chars)
        self.assertNotIn('toast.timer=setTimeout',chars)
        self.assertNotIn('clearTimeout(toast.timer)',chars)
        self.assertIn("aria-label','Dismiss notification",chars)
        self.assertIn('role',chars)

    def test_scoped_sync_reports_all_managed_placed_houses(self):
        partial=(PLUGIN/'modules/StudioRealEstatePartSync.luau').read_text('utf-8')
        full=(PLUGIN/'modules/StudioRealEstateModel.luau').read_text('utf-8')
        placed=(PLUGIN/'modules/StudioRealEstatePlacedVisualSync.luau').read_text('utf-8')
        for source in (partial,full):
            self.assertIn('workspaceModelsFound',source)
            self.assertIn('workspaceModelsUpdated',source)
        self.assertIn('PlacedTargets.List(slug)',partial)
        self.assertIn('replacement:Clone()',partial)
        self.assertIn('if part == "door" then placedOld:GetPivot()',partial)
        self.assertIn('Targets.List(slug)',placed)
        selector=(PLUGIN/'modules/StudioRealEstatePlacedTargets.luau').read_text('utf-8')
        self.assertIn('Game1RealEstateSlug',selector)
        self.assertIn('Game1RealEstateTemplate',selector)
        self.assertIn('candidate:PivotTo(target)',placed)
        self.assertIn('source.Name == "DoorAssembly"',placed)
        self.assertIn('StudioRealEstatePlacedVisualSync.Update(wrapper, slug, placedTargets)',full)
        project=json.loads((PLUGIN/'plugin.project.json').read_text('utf-8'))
        self.assertIn('StudioRealEstatePlacedVisualSync',project['tree']['modules'])
        installer=(PLUGIN/'install.ps1').read_text('utf-8')
        self.assertIn("'StudioRealEstatePlacedVisualSync'",installer)

    def test_javascript_syntax(self):
        node=shutil.which('node')
        if not node:self.skipTest('node unavailable')
        for name in ('real-estate.js','real-estate-mesh-workflow.js','character-assets.js'):
            result=subprocess.run([node,'--check',str(STATIC/name)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,f'{name}: {result.stderr}')

if __name__=='__main__':unittest.main()
