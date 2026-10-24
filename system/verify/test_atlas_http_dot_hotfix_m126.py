"""M126 regression tests: PUT proxy + deterministic compact atlas dots.

No production network, Roblox or database changes are used by these tests.
"""
from __future__ import annotations

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import TestCase, mock
import importlib.util
import json
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system' / 'control-center'


class AtlasHttpProxyM126(TestCase):
    def test_put_atlas_binding_is_forwarded_unchanged(self):
        sys.path.insert(0, str(CONTROL))
        spec = importlib.util.spec_from_file_location('m126_web_server', CONTROL / 'web_server.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        received = []

        class AgentResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def read(self):
                return b'{"bindingRevision":4,"texture_asset_id":"123"}'

        def forward(req, timeout):
            received.append((req.get_method(), req.full_url, req.data, req.get_header('X-control-token'), timeout))
            return AgentResponse()

        class QuietHandler(module.Handler):
            def log_message(self, *_):
                pass

        with mock.patch.object(module, 'urlopen', side_effect=forward):
            server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                data = json.dumps({'variantId': 12, 'expectedRevision': 3}).encode()
                conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    conn.request('PUT', '/api/location-assets/wooden_post_01/atlas-binding', body=data,
                                 headers={'Content-Type':'application/json'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())['bindingRevision'], 4)
                finally:
                    conn.close()
                self.assertEqual(len(received), 1)
                method, url, body, auth, timeout = received[0]
                self.assertEqual(method, 'PUT')
                self.assertTrue(url.endswith('/api/location-assets/wooden_post_01/atlas-binding'))
                self.assertEqual(json.loads(body), {'variantId':12,'expectedRevision':3})
                self.assertEqual(auth, module.TOKEN)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class AtlasDotsM126(TestCase):
    def test_ui_orders_gold_first_by_pixel_count_not_registry_order(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is not available')
        js = CONTROL / 'static' / 'deco-assets.js'
        snippet = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const src = fs.readFileSync(process.argv[1], 'utf8');
const start = src.indexOf('function decoAtlasDots(row) {');
const end = src.indexOf('\nasync function decoAssetChooseAtlasVariant', start);
assert(start > -1 && end > start);
const context = {
  decoAssetState: { atlasBusy: false },
  DECO_ATLAS_COLORS: ['#d9ac43','#a47bdf','#4f95ee','#54b991','#939ba8'],
  esc: (value) => String(value),
};
vm.runInNewContext(src.slice(start, end), context);
const original = [
  {id:10,width:64,height:128,filename:'kit_64x128_atlas.png',resolution:'64x128',current:true},
  {id:20,width:256,height:64,filename:'kit_256x64_atlas.png',resolution:'256x64',current:true},
  {id:30,width:128,height:256,filename:'kit_128x256_atlas.png',resolution:'128x256',current:true},
];
const html = context.decoAtlasDots({atlasVariants:original,atlasVariantId:20});
assert.deepStrictEqual([...html.matchAll(/data-atlas-variant="(\d+)"/g)].map(x => Number(x[1])), [30,20,10]);
assert.deepStrictEqual([...html.matchAll(/--dot-color:(#[0-9a-f]{6})/g)].map(x => x[1]), ['#d9ac43','#a47bdf','#4f95ee']);
assert(html.includes('kit_128x256_atlas.png · 128x256'));
assert(html.includes('kit_256x64_atlas.png · 256x64'));
assert(html.includes('is-active'));
assert.deepStrictEqual(original.map(x=>x.id),[10,20,30]); // no in-place changes
'''
        subprocess.run([node, '-e', snippet, str(js)], check=True, capture_output=True, text=True, timeout=12)

    def test_click_targets_remain_available_and_dots_are_smaller(self):
        js = (CONTROL/'static'/'deco-assets.js').read_text(encoding='utf-8')
        css = (CONTROL/'static'/'deco-assets.css').read_text(encoding='utf-8')
        self.assertIn("method: 'PUT'", js)
        self.assertIn('data-atlas-variant', js)
        self.assertIn('width:14px; height:14px;', css)
        self.assertIn('width:7px; height:7px;', css)
        self.assertNotIn('outline-offset:1px', css)
