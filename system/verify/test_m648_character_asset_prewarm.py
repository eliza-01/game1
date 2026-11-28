from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class CharacterWarmM648(unittest.TestCase):
    def test_real_plan_and_service(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        source = read('src/server/character/CharacterCreationAssetWarmService.luau')
        source = source.replace('remotes: Folder, loadAsset: (number) -> Model?', 'remotes, loadAsset')
        source = source.replace('player: Player, index: any', 'player, index')
        source = re.sub(r': \{\[(?:string|number)\]: (?:string|number|any)\}', '', source)
        source = source.replace(': {MeshPart}', '')
        source = re.sub(r'(\w+) \+= (.+)', r'\1 = \1 + \2', source)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'warm.lua'; path.write_text(source, encoding='utf-8')
            plan = read('src/server/character/CharacterCreationWarmPlan.luau')
            plan = re.sub(r': (?:any|string)(?=[,)\s])', '', plan)
            plan_path = Path(temp) / 'plan.lua'; plan_path.write_text(plan, encoding='utf-8')
            subprocess.run([lua, str(ROOT/'system/verify/character_warm_m648.lua'), str(ROOT), str(path), str(plan_path)], check=True, timeout=15)

    def test_real_client_warm_cancellation_and_replica_timeout(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        source = read('src/client/character/CharacterCreationAssetPrewarm.luau')
        source = source.replace('remote: RemoteFunction, current: () -> boolean): boolean', 'remote, current)')
        source = source.replace('alive(): boolean', 'alive()').replace(': {MeshPart}', '').replace(': Instance?', '').replace(' :: MeshPart', '')
        source = source.replace('tostring(if type(response) == "table" then response.error else response)', 'tostring(type(response) == "table" and response.error or response)')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'warm_client.lua'; path.write_text(source, encoding='utf-8')
            subprocess.run([lua, str(ROOT/'system/verify/character_warm_client_m648.lua'), str(path)], check=True, timeout=15)

    def test_bootstrap_and_foreground_priority(self):
        controller = read('src/client/character/CharacterCreationController.luau')
        branch = controller[controller.index('bootstrapPending = {human_male = true, human_female = true}'):]
        self.assertLess(branch.index('requestPreview("human_male")'), branch.index('AssetPrewarm.Run'))
        self.assertLess(branch.index('requestPreview("human_female")'), branch.index('AssetPrewarm.Run'))
        self.assertIn('next(bootstrapPending) ~= nil', branch)
        self.assertIn('revisions.human_male == maleRevision', branch)
        self.assertNotIn('VariantPrewarm', controller)
        self.assertNotIn('warmProgress', controller)
        self.assertFalse((ROOT/'src/client/character/CharacterCreationVariantPrewarm.luau').exists())
        preloader = read('src/client/character/CharacterCreationMeshPreloader.luau')
        self.assertIn('if background and activeCount > 0 then return nil end', preloader)
        self.assertIn('return preload(collect(model), isCurrent, onProgress, false)', preloader)
        self.assertIn('preload(queue, current, nil, true)', preloader)
        self.assertEqual(preloader.count('ContentProvider:PreloadAsync('), 1)

    def test_server_boundary_and_cache(self):
        service = read('src/server/character/CharacterCreationAssetWarmService.luau')
        self.assertNotIn('CharacterAssemblyBuilder', service)
        self.assertNotIn('PreviewService', service)
        self.assertIn('loadAsset(record.assetId)', service)
        self.assertIn('copy:ClearAllChildren()', service)
        self.assertIn('count + #staged >= MAX_SOURCES', service)
        self.assertIn('retryAt[index]', service)
        server = read('src/server/character/CharacterService.luau')
        self.assertIn('AssetWarmService.Bind(remotes', server)
        self.assertIn('assetLoading[cacheKey] = nil', server)
        client = read('src/client/character/CharacterCreationAssetPrewarm.luau')
        self.assertIn('Preloader.PreloadResources(sources, response.images, alive)', client)
        self.assertIn('source:IsA("MeshPart")', client)
        self.assertIn('if not alive() then return false end', client)
        self.assertNotIn('CharacterCreationPreview', client)
