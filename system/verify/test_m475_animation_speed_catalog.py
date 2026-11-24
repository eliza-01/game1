"""M475: every published animation is discoverable, including male weapon run.

Editor browsing is not the same as creating a per-clip stat override. The
runtime is keyed by asset ID and must also honor overrides for social clips.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from animation_speed_scaling_store import AnimationSpeedScalingStore


class PublishedAnimationSpeedCatalogM475(unittest.TestCase):
    def test_all_published_character_variants_and_shared_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for source in ROOT.glob('assets/manifests/*-animations.json'):
                target = base / 'assets/manifests' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            store = AnimationSpeedScalingStore(base)
            catalog = store.snapshot()['catalog']
            self.assertEqual(len(catalog), len({row['assetId'] for row in catalog}))
            self.assertGreater(len(catalog), 0)
            males = [row for row in catalog if row['kind'] == 'character' and row['subject'] == 'human_male'
                     and row['scope'] == 'weapon' and row['channel'] == 'run']
            self.assertTrue({'1hs', 'bow', 'hands'}.issubset({row['weaponSet'] for row in males}))
            for row in males:
                self.assertTrue(row['assetId'].isdigit())
                self.assertEqual(row['variant'], 1)
            shared = [row for row in catalog if row['subject'] == 'human_common']
            self.assertTrue(shared)
            self.assertTrue(all(row['availableFor'] == ['human_male', 'human_female'] for row in shared))
            # Published custom scaling remains one entry per ID, not one for each consumer.
            override = store.save_custom({'assetId': males[0]['assetId'], 'stat': 'RunSpeed', 'unitsPerPercent': 3.5})
            self.assertEqual(override['customScaling'][0]['assetId'], males[0]['assetId'])
            self.assertEqual(override['customScaling'][0]['unitsPerPercent'], 3.5)

    def test_browser_catalog_finds_male_run_and_common_variants(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        manifest = json.loads((ROOT / 'assets/manifests/character-animations.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'assets/manifests').mkdir(parents=True)
            (base / 'assets/manifests/character-animations.json').write_text(json.dumps(manifest), encoding='utf-8')
            store = AnimationSpeedScalingStore(base)
            catalog = store.catalog()
            filename = base / 'catalog.json'
            filename.write_text(json.dumps(catalog), encoding='utf-8')
            javascript = r'''
const fs = require('fs');
const assert = require('assert');
const api = require(process.argv[2]);
const catalog = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const run = api.visible(catalog, {kind:'character', search:'male run'});
assert(['hands','bow','1hs'].every(item=>run.some(x=>x.weaponSet===item)));
assert(run.every(x=>x.subject === 'human_male'));
const common = api.visible(catalog, {subject:'human_female', search:'common social laugh 02'});
assert(common.some(x=>x.subject === 'human_common' && x.variant === 2));
const specific = api.visible(catalog, {search:'human_male weapon bow run 01'});
assert(specific.some(x=>x.weaponSet==='bow' && x.subject==='human_male'));
assert(api.visible(catalog, {search:'female run'}).every(x=>x.subject !== 'human_male'));
const pages = api.page(api.visible(catalog, {kind:'character'}), 99, 24);
assert(pages.rows.length > 0 && pages.number < pages.pages);
console.log('m475 published catalog search passed');
'''
            script = base / 'test.cjs'
            script.write_text(javascript, encoding='utf-8')
            result = subprocess.run([node, str(script), str(ROOT / 'system/control-center/static/animation-speed-catalog.js'), str(filename)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_social_playback_consumes_asset_id_custom_scaling(self):
        lua = (ROOT / 'src/client/character/animation/SocialAnimationPlayback.luau').read_text(encoding='utf-8')
        self.assertIn('AnimationSpeedScaling.ResolveScaleForAnimation(', lua)
        self.assertIn('self.character, "social", descriptor.animationId', lua)
        self.assertNotIn('track:Play(0.12)\n', lua)
        html = (ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8')
        self.assertIn('animation-speed-catalog.js', html)
        self.assertIn('custom-scaling-kind', html)
        self.assertIn('custom-scaling-subject', html)


if __name__ == '__main__':
    unittest.main()
