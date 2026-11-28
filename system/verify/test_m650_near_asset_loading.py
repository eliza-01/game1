from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NearAssetLoadingM650(unittest.TestCase):
    def test_real_pure_modules(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/lod_asset_loading_m650.lua'], cwd=ROOT, check=True, timeout=30)

    def test_shared_loader_and_production_entrypoints(self):
        def read(name): return (ROOT/name).read_text(encoding='utf-8')
        streamer = read('src/client/world/LocationWorldStreamer.luau')
        loader = read('src/client/AssetMeshPreloader.luau')
        service = read('src/server/world/LocationLodTemplateService.luau')
        self.assertIn('LodAssetReadiness.new(AssetMeshPreloader.PreloadVisual', streamer)
        self.assertIn('loadInProgress, function(record)', streamer)
        self.assertIn('table.insert(objects, model)', loader)
        self.assertIn('return preload(collect(bundle), current, nil, true)', loader)
        self.assertEqual(loader.count('ContentProvider:PreloadAsync('), 1)
        self.assertFalse((ROOT/'src/client/character/CharacterCreationMeshPreloader.luau').exists())
        for name in ('CharacterCreationPreviewController','CharacterCreationController','CharacterCreationAssetPrewarm'):
            self.assertIn('script.Parent.Parent:WaitForChild("AssetMeshPreloader")', read('src/client/character/'+name+'.luau'))
        self.assertIn('StagePlan.Build(manifest, Registry, Contract.Variants', service)
        self.assertIn('cache:SetAttribute("StagingComplete", true)', service)
        self.assertIn('stagingFolder:GetAttribute("StagingComplete")', streamer)
        self.assertEqual(streamer.count('RunService.Heartbeat:Connect'), 1)
        self.assertNotIn('RemoteEvent', streamer)
