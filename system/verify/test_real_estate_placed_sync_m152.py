"""M152: a Workspace template clone is a placed house; no silent 0/0 success."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT/'system/studio-plugin'
STATIC = ROOT/'system/control-center/static'


class PlacedStudioSyncM152(unittest.TestCase):
    def test_all_sync_paths_use_workspace_identity_not_copied_template_flag(self):
        targets = (STUDIO/'modules/StudioRealEstatePlacedTargets.luau').read_text('utf-8')
        self.assertIn('workspace:GetDescendants()', targets)
        self.assertIn('Game1RealEstateSlug', targets)
        self.assertNotIn('and root:GetAttribute("Game1RealEstateTemplate") ~= true', targets)
        self.assertIn('root:SetAttribute("Game1RealEstateTemplate", nil)', targets)
        self.assertIn('if not nested then', targets)
        partial = (STUDIO/'modules/StudioRealEstatePartSync.luau').read_text('utf-8')
        visual = (STUDIO/'modules/StudioRealEstatePlacedVisualSync.luau').read_text('utf-8')
        collision = (STUDIO/'modules/StudioRealEstatePlacedCollisionSync.luau').read_text('utf-8')
        full = (STUDIO/'modules/StudioRealEstateModel.luau').read_text('utf-8')
        for source in (partial, visual, collision, full):
            self.assertIn('StudioRealEstatePlacedTargets', source)
        for source in (partial, visual, collision, full):
            self.assertNotIn('root:GetAttribute("Game1RealEstateTemplate") ~= true', source)
        self.assertIn('for _, root in PlacedTargets.List(slug)', partial)
        self.assertIn('local placedTargets = PlacedTargets.List(slug)', full)
        self.assertIn('StudioRealEstatePlacedVisualSync.Update(wrapper, slug, placedTargets)', full)
        self.assertIn('StudioRealEstatePlacedCollisionSync.Update(wrapper, slug, placedTargets)', full)
        self.assertIn('refreshPlaced(slug, imageAssets, imageAlpha, meshOptions, placedTargets)', full)
        self.assertIn('Targets.MarkPlaced(root)', visual)
        self.assertIn('PlacedTargets.MarkPlaced(root)', partial)
        self.assertIn('workspaceModelsFound = placedFound', partial)
        self.assertIn('workspaceModelsFound = visualFound', full)
        self.assertIn('placedSyncVersion = 2', partial)
        self.assertIn('placedSyncVersion = 2', full)
        self.assertIn('local target = if part == "door" then placedOld:GetPivot()', partial)
        self.assertIn('source.Name == "DoorAssembly"', visual)
        self.assertNotIn('Bone.Transform =', partial + visual)
        # A door-only sync must preserve all unrelated rigs, not replace house.
        self.assertIn('existingPart(root, part)', partial)
        self.assertIn('replacement:Clone()', partial)
        self.assertIn('placedIds[part] = tostring(assetId)', partial)

    def test_plugin_installer_bundle_declares_shared_targets(self):
        manifest = json.loads((STUDIO/'plugin.project.json').read_text('utf-8'))
        self.assertEqual(manifest['tree']['modules']['StudioRealEstatePlacedTargets']['$path'],
                         'modules/StudioRealEstatePlacedTargets.luau')
        installer = (STUDIO/'install.ps1').read_text('utf-8')
        self.assertIn("'StudioRealEstatePlacedTargets'", installer)

    def test_ui_handles_no_placements_stale_bridge_and_partial_updates(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js unavailable')
        program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('real-estate.js','utf8');
const start=src.indexOf('async function realEstateSync(slug, part=null)');
const end=src.indexOf('async function realEstatePublish(',start);
assert(start>0 && end>start);
const body=src.slice(start,end);
const notices=[];
let payload={};
const context={
  realEstateRows:()=>[{slug:'house_level4_01'}],
  toast:(message,error)=>notices.push({message,error:!!error}),
  request:async()=>({studio:{realEstateStats:payload}}),
  $:()=>({hidden:false,innerHTML:''}),
  esc:x=>String(x),
  URL,encodeURIComponent
};
vm.createContext(context);
vm.runInContext(body+';globalThis.invoke=realEstateSync',context);
(async()=>{
  payload={placedSyncVersion:2,workspaceModelsFound:2,workspaceModelsUpdated:2,rigWarnings:[]};
  assert(await context.invoke('house_level4_01'));
  assert.equal(notices.at(-1).error,false);
  assert.match(notices.at(-1).message,/placed houses 2\/2/);
  payload={placedSyncVersion:2,workspaceModelsFound:0,workspaceModelsUpdated:0,rigWarnings:[]};
  assert(await context.invoke('house_level4_01'));
  assert.equal(notices.at(-1).error,true);
  assert.match(notices.at(-1).message,/NO matching placed houses/);
  payload={placedSyncVersion:2,workspaceModelsFound:2,workspaceModelsUpdated:1,rigWarnings:[]};
  assert(await context.invoke('house_level4_01'));
  assert.equal(notices.at(-1).error,true);
  payload={workspaceModelsFound:0,workspaceModelsUpdated:0};
  assert.equal(await context.invoke('house_level4_01'),null);
  assert.equal(notices.at(-1).error,true);
  assert.match(notices.at(-1).message,/outdated/);
})().catch(e=>{console.error(e);process.exit(1)})
'''
        result = subprocess.run([node, '-e', program], cwd=STATIC,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
