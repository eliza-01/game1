"""Test actual JS projection on canonical Markdown, including invalid topology."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DesignMapM538(unittest.TestCase):
    def test_spec_and_map_contract(self):
        spec = (ROOT / 'docs/kanban/specs/KBN-0031.md').read_text(encoding='utf-8')
        self.assertNotRegex(spec, r'\bZ[1-8]\b')
        self.assertNotIn('```text', spec)
        rows = [line.strip('|').split('|') for line in spec.splitlines()
                if re.match(r'^\| [^|]+ \| \d+–\d+ \| [12] \| [1-4] \|', line)]
        rows = [[cell.strip() for cell in row] for row in rows]
        self.assertEqual(len(rows), 6)
        self.assertEqual([row[1] for row in rows], re.findall(r'^## .* · LVL (\d+–\d+)$', spec, re.M))
        self.assertEqual(rows[3][-1], '1–4')
        if not shutil.which('node'):
            self.skipTest('Node.js unavailable for JavaScript execution')
        js = ROOT / 'system/control-center/static/kanban-design-map.js'
        script = r'''
const assert=require('node:assert/strict');global.window={};require(process.argv[1]);
const map=window.game1KanbanDesignMap,rows=JSON.parse(process.argv[2]);
const nodes=map.parse(rows);assert.equal(nodes.length,6);
assert.equal(nodes[0].name,'Солнечная долина');assert.equal(nodes[5].name,'Драконий предел');
assert.equal(nodes[3].back,'1–4');assert.equal(new Set(nodes.map(n=>n.color)).size,6);
for(const mutate of [r=>r[1][2]=r[0][2],r=>r[1][1]='9–10',r=>r[3][5]='2–3',r=>r[5][4]='road',r=>r[0][2]='999']){
 const bad=structuredClone(rows);mutate(bad);assert.equal(map.parse(bad),null);
}
// Exercise the actual SVG renderer and keyboard/click callbacks without a browser.
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.events={};this.style={setProperty(){}};this.namespaceURI='http://www.w3.org/2000/svg';}
 append(...nodes){this.children.push(...nodes)}setAttribute(k,v){this.attrs[k]=v}addEventListener(k,v){this.events[k]=v}
}
global.document={createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)};
const selected=[];const host=map.render(rows,r=>selected.push(r));const svg=host.children[0];
const zones=svg.children.filter(e=>e.attrs.class==='kb-map-zone');assert.equal(zones.length,6);
assert.equal(svg.children.filter(e=>e.attrs.class==='kb-map-route').length,5);
assert.equal(svg.children.filter(e=>e.attrs.class==='kb-map-return').length,1);
zones[2].events.click();zones[5].events.keydown({key:'Enter',preventDefault(){}});assert.deepEqual(selected,['10–14','25–30']);
'''
        subprocess.run(['node', '-e', script, str(js), json.dumps(rows, ensure_ascii=False)], check=True)
