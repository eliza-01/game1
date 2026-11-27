"""M621: shared prototype readiness cache, metadata and late-replication contracts."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


class PrototypeReadinessCacheM621(unittest.TestCase):
    def test_readiness_cache_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable; run standalone oracle when installed')
        args = [lua, 'system/verify/lod_prototype_cache_m621.lua']
        if Path(lua).name == 'texlua':
            args.insert(1, '--luaonly')
        subprocess.run(args, cwd=ROOT, check=True, timeout=30)

    def test_cache_is_event_driven_and_has_no_runtime_scheduler(self):
        source = read('src/client/world/LodPrototypeCache.luau')
        for needle in ('ChildAdded', 'ChildRemoved', 'GetAttributeChangedSignal("Ready")',
                      'Game1LodVisualCount', 'Game1LodPublishedPivot', 'Game1LodSourceName',
                      'Size', 'CFrame', 'MeshId', 'missing', 'incomplete', 'ready', 'invalid',
                      'MAX_RETRIES = 2', 'FolderReady', 'function Cache:Destroy()',
                      'freezeMetadata', 'table.freeze(metadata)'):
            self.assertIn(needle, source)
        for forbidden in ('Heartbeat', 'Raycast', 'RemoteEvent', 'Instance.new', 'GetDescendants', 'task.spawn'):
            self.assertNotIn(forbidden, source)

    def test_streamer_uses_cached_prototypes_and_late_folder_recovery(self):
        source = read('src/client/world/LocationWorldStreamer.luau')
        self.assertIn('LodPrototypeCache.new(ReplicatedStorage, Contract.TemplateFolder, LodAssembly)', source)
        self.assertIn('prototypeCache:Resolve(', source)
        self.assertIn('prototypeCache:FolderReady()', source)
        self.assertIn('prototypeChangedConnection = prototypeCache:ConnectChanged', source)
        self.assertNotIn('WaitForChild(Contract.TemplateFolder, 30)', source)
        self.assertNotIn('cache:FindFirstChild(record.slug', source)
        self.assertIn('transition.metadata', source)
        self.assertIn('transition.force', source)
        self.assertIn('actualPrototypeGeneration', source)
        self.assertIn('record.failedAssemblyGenerations[variant] = transition.metadata and transition.metadata.generation', source)
        self.assertIn('queue:Remove(record)', source)
        self.assertIn('LocationCompositeVisual.SetEffects(record, true)', source)
        self.assertIn('function Streamer.Stop()', source)

    def test_assembly_and_composite_consumers_reuse_metadata(self):
        assembly = read('src/client/world/LocationLodAssembly.luau')
        composite = read('src/client/world/LocationCompositeVisual.luau')
        house = read('src/client/world/HouseVisualAdapter.luau')
        queue = read('src/client/world/LodTransitionQueue.luau')
        self.assertIn('function Assembly.BuildMetadata(prototype)', assembly)
        self.assertIn('metadata.sourceSize', assembly)
        self.assertIn('metadata.parts', assembly)
        self.assertIn('function Assembly.Create(prototype, targetFrame, targetParts, applyAppearance, metadata)', assembly)
        self.assertIn('metadata.childrenByName', composite)
        self.assertIn('prototypeCache:Resolve(visual.templateName, "LOD1")', house)
        self.assertIn('prototypeCache:ConnectChanged', house)
        self.assertIn('function Adapter:Destroy()', house)
        self.assertIn('metadata=metadata, force=force', queue)
        self.assertIn('variant == record.actual and not force', queue)

    def test_mechanics_catalog_exposes_new_cache_and_geometry_sources(self):
        mechanics = read('system/control-center/mechanics/lod.py')
        catalog = read('system/control-center/mechanics/catalog.py')
        self.assertIn('lod-prototype-cache', mechanics)
        self.assertIn('location-lod-assembly', mechanics)
        self.assertIn('LodPrototypeCache.luau', catalog)
        self.assertIn('LocationLodAssembly.luau', catalog)

    def test_existing_lod_regression_oracles_remain_referenced(self):
        source = read('system/verify/test_m619_static_placement_index.py')
        self.assertIn('static_placement_index_m619.lua', source)
        queue = read('system/verify/test_m620_lod_transition_queue.py')
        self.assertIn('lod_transition_queue_m620.lua', queue)
