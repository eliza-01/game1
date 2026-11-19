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
    def test_all_sync_paths_preserve_place_identity_and_managed_visuals(self):
        targets = (STUDIO/'modules/StudioRealEstatePlacedTargets.luau').read_text('utf-8')
        self.assertIn('workspace:GetDescendants()', targets)
        self.assertIn('Game1RealEstateSlug', targets)
        self.assertIn('if not nested then', targets)
        self.assertIn('root:SetAttribute("Game1RealEstateTemplate", nil)', targets)
        part = (STUDIO/'modules/StudioRealEstatePartSync.luau').read_text('utf-8')
        visual = (STUDIO/'modules/StudioRealEstatePlacedVisualSync.luau').read_text('utf-8')
        full = (STUDIO/'modules/StudioRealEstateModel.luau').read_text('utf-8')
        for module in (part, visual, full):
            self.assertIn('StudioRealEstatePlacedTargets', module)
            self.assertNotIn('root:GetAttribute("Game1RealEstateTemplate") ~= true', module)
        self.assertIn('for _, root in PlacedTargets.List(slug)', part)
        self.assertIn('local placedTargets = PlacedTargets.List(slug)', full)
        self.assertIn('StudioRealEstatePlacedVisualSync.Update(wrapper, slug, placedTargets)', full)
        self.assertIn('RetiredCleanup.CleanEstate(root)', full)
        self.assertIn('refreshPlaced(slug, imageAssets, imageAlpha, meshOptions, placedTargets)', full)
        self.assertIn('Targets.MarkPlaced(root)', visual)
        self.assertIn('PlacedTargets.MarkPlaced(root)', part)
        self.assertIn('workspaceModelsFound = placedFound', part)
        self.assertIn('workspaceModelsFound = visualFound', full)
        self.assertIn('placedSyncVersion = 2', part)
        self.assertIn('placedSyncVersion = 3', full)
        self.assertIn('source.Name == "DoorAssembly"', visual)
        self.assertIn('managedChildren(root, true)', visual)
        self.assertIn('RigSwap.Prepare(root, oldRigs, newRigs', visual)
        self.assertNotIn('Bone.Transform =', part + visual)
        self.assertIn('existingPart(root, part)', part)
        self.assertIn('replacement:Clone()', part)
        self.assertIn('placedIds[part] = tostring(assetId)', part)

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
const start=src.indexOf('async function realEstateSync(slug, part=null, {throwOnError=false}={})');
const end=src.indexOf('async function realEstatePublish(',start);
assert(start>0 && end>start);
const notices=[];
let payload={};
const context={
  window:{game1StudioSync:{run:async()=>({studio:{realEstateStats:payload}})}},
  realEstateRows:()=>[{slug:'house_level4_01'}],
  toast:(message,error)=>notices.push({message,error:!!error}),
  $:()=>({hidden:false,innerHTML:''}),
  esc:x=>String(x),
};
vm.createContext(context);
vm.runInContext(src.slice(start,end)+';globalThis.invoke=realEstateSync',context);
(async()=>{
  payload={placedSyncVersion:3,workspaceModelsFound:2,workspaceModelsUpdated:2,rigWarnings:[]};
  assert(await context.invoke('house_level4_01'));
  assert.equal(notices.at(-1).error,false);
  assert.match(notices.at(-1).message,/placed houses 2\/2/);
  payload={placedSyncVersion:3,workspaceModelsFound:0,workspaceModelsUpdated:0,rigWarnings:[]};
  assert(await context.invoke('house_level4_01'));
  assert.equal(notices.at(-1).error,true);
  assert.match(notices.at(-1).message,/NO matching placed houses/);
  payload={placedSyncVersion:3,workspaceModelsFound:2,workspaceModelsUpdated:1,rigWarnings:[]};
  assert(await context.invoke('house_level4_01'));
  assert.equal(notices.at(-1).error,true);
  payload=null; // a malformed response is rejected; the server rejects stale versions
  assert.equal(await context.invoke('house_level4_01'),null);
  assert.equal(notices.at(-1).error,true);
  assert.match(notices.at(-1).message,/missing Real Estate statistics/);
})().catch(e=>{console.error(e);process.exit(1)})
'''
        result = subprocess.run([node, '-e', program], cwd=STATIC,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
