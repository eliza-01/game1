"""M219: targeted library-row UX, shared sync client and non-destructive contract."""
from pathlib import Path
from subprocess import run
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


class LocationAssetUIM219(TestCase):
    def read(self, name):
        return (STATIC / name).read_text(encoding='utf-8')

    def test_library_buttons_use_their_own_slug_not_form_selection(self):
        source = self.read('deco-assets.js')
        self.assertIn('data-deco-sync type="button"', source)
        self.assertIn("tr.querySelector('[data-deco-sync]').onclick = () => decoAssetSyncStudio(row.slug)", source)
        self.assertIn("tr.querySelector('[data-select]').onclick = () => decoAssetEditOpen(row.slug)", source)
        self.assertIn("window.game1StudioSync.run('location', slug)", source)
        self.assertNotIn("$('sync-location-assets')", source)
        self.assertNotIn('decoAssetRetrySync', source)
        self.assertNotIn('await decoAssetSyncStudio(row.slug)', source.split('async function decoAssetChooseAtlasVariant', 1)[1].split('function decoAssetUseCategory',1)[0])

    def test_edit_is_a_dedicated_real_resource_workflow_not_a_moved_registration_form(self):
        source = self.read('deco-assets.js')
        editor = self.read('location-asset-workflow.js')
        self.assertIn('window.game1LocationAssetWorkflow.open(slug)', source)
        self.assertNotIn('decoAssetEditorAnchor', source)
        self.assertNotIn("appendChild(panel)", source)
        self.assertIn("window.game1AssetWorkflowDialog", editor)
        self.assertIn("shell.tabs(tabs,state.tab", editor)
        self.assertIn('shell.step(name,description', editor)
        for action in ('save-identity','choose-fbx','apply-model','sync'):
            self.assertIn(action, editor)
        self.assertIn('window.game1ConsumerAtlasEditor.render', editor)
        self.assertNotIn('Save image source',editor)
        self.assertNotIn("buttons('publish-image'",editor)
        self.assertIn('id="location-asset-editor-panel"', self.read('index.html'))
        self.assertIn('new-only', source)

    def test_common_dispatch_used_by_house_and_deco(self):
        self.assertIn("window.game1StudioSync.run('real-estate',slug,{part})", self.read('real-estate.js'))
        self.assertIn("window.game1StudioSync.run('location', slug)", self.read('deco-assets.js'))
        html = self.read('index.html')
        self.assertLess(html.index('studio-sync.js?v='), html.index('deco-assets.js?v='))
        self.assertLess(html.index('asset-workflow-dialog.js?v='), html.index('real-estate-mesh-workflow.js?v='))
        self.assertNotIn('sync selected asset IDs', html)

    def test_studio_sync_still_never_replaces_placed_models(self):
        source = (ROOT / 'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text(encoding='utf-8')
        self.assertIn('workspace:GetDescendants()', source)
        self.assertIn('descendant:GetAttribute(SLUG) == slug', source)
        self.assertIn('DecoPlacedAssetSync.RefreshIds(', (ROOT / 'system/studio-plugin/modules/DecoManager.luau').read_text(encoding='utf-8'))
        for forbidden in ('LoadAssetAsync(', '.MeshId =', 'previous:Destroy()', 'model:Destroy()'):
            self.assertNotIn(forbidden, source)

    def test_executable_client_dispatch(self):
        process = run(['node', str(ROOT / 'system/verify/location_assets_editor_sync_m219.js')],
                      text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
