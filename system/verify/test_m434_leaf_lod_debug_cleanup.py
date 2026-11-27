"""M434: new Flora leaf category, and no runtime Studio LOD debug HUD."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from location_asset_store import LocationAssetStore
from services import location_asset_taxonomy as taxonomy


def source(path):
    return (ROOT / path).read_text('utf-8')


class LeafAndLodDebugM434(TestCase):
    def test_leaf_is_first_class_category_across_all_consumers(self):
        self.assertEqual(taxonomy.CATEGORY_GROUPS[0][2],
                         ('tree', 'bush', 'ivy', 'flower', 'leaf', 'rock'))
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = LocationAssetStore(root)
            options = store.options()
            category = {'id': 'leaf', 'label': 'Leaf', 'group': 'flora'}
            self.assertIn(category, options['categories'])
            self.assertIn(category, options['categoryGroups'][0]['categories'])
            with store.connect() as db:
                db.execute("""INSERT INTO location_assets(slug,name_en,category,created_at,updated_at)
                    VALUES('leaf_01','Leaf 01','leaf',1,1),('flower_01','Flower 01','flower',1,1)""")
            self.assertEqual(store.get('leaf_01')['category_label'], 'Leaf')
            self.assertEqual(store.get('flower_01')['category'], 'flower')
            store.export()
            registry = (root / 'src/shared/world/LocationAssetRegistry.luau').read_text('utf-8')
            self.assertIn('category = "leaf"', registry)
        manager = source('system/studio-plugin/modules/DecoManager.luau')
        placement = source('system/studio-plugin/modules/DecoPlacement.luau')
        self.assertIn('"ivy", "flower", "leaf", "rock"', manager)
        self.assertIn('leaf="Leaf"', manager)
        self.assertIn('leaf = "Leaves"', placement)
        self.assertIn('Flora · tree · bush · ivy · flower · leaf · rock',
                      source('system/control-center/static/index.html'))

    def test_retired_lod_debug_no_longer_runs_or_recomputes_counters(self):
        project = json.loads(source('default.project.json'))
        self.assertNotIn('Game1LodProbeClient', project['tree']['StarterPlayer']['StarterPlayerScripts'])
        self.assertFalse((ROOT / 'src/lod-probe').exists())
        self.assertFalse((ROOT / 'src/client/world/LocationLodStudioProbe.luau').exists())
        streamer = source('src/client/world/LocationWorldStreamer.luau')
        self.assertNotIn('Game1RuntimeLodStatus', streamer)
        self.assertNotIn('Studio LOD preview |', streamer)
        self.assertNotIn('makeStatus()', streamer)
        self.assertNotIn(':Stats()', streamer)
        for path in ('src/client/world/StudioLodPreviewAdapter.luau',
                     'src/client/world/HouseVisualAdapter.luau'):
            self.assertNotIn('function Adapter:Stats(', source(path))
        self.assertEqual(streamer.count('RunService.Heartbeat:Connect'), 1)
        self.assertIn('preview:Resolve(cameraPosition)', streamer)
        self.assertIn('preview:Step(MAX_CHANGES_PER_TICK)', streamer)
        self.assertIn('houseAdapter:Observe(record, previousDesired, queue)', streamer)
        self.assertNotIn('houseAdapter:Step(', streamer)
        self.assertIn('LodThresholdCache.Resolve(record, cameraPosition, Policy, cameraChanged)', streamer)
        self.assertIn('warn("[game1][LOD] template staging incomplete;', streamer)
        self.assertIn('Policy.ResolveHouse(', source('src/client/world/StudioLodPreviewAdapter.luau'))
