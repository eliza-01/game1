"""Location Assets may choose every published Atlas Registry variant, grouped by domain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from services.texture_atlas_registry import AtlasRegistry


class LocationAtlasAllSections(unittest.TestCase):
    def test_catalog_exposes_scopes_and_consumers_for_ui_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.control-center').mkdir()
            registry = AtlasRegistry(root)
            character_path = root / 'hero_face_8x8_atlas.png'
            location_path = root / 'lantern_8x8_atlas.png'
            Image.new('RGBA', (8, 8), 'red').save(character_path)
            Image.new('RGBA', (8, 8), 'blue').save(location_path)

            character = registry.register_file(str(character_path), domain='character')
            location = registry.index_existing_published_image(
                source_path=str(location_path), atlas_key='lantern', published_id='222',
                expected_sha256=hashlib.sha256(location_path.read_bytes()).hexdigest())
            with registry.connect() as db:
                db.execute('''UPDATE texture_atlas_variants SET published_id='111',
                    published_sha256=source_sha256 WHERE id=?''', (character['id'],))
            registry.bind('location_asset', 'lantern_01', location['id'])

            variants = {variant['id']: variant for family in registry.catalog_with_consumers()
                        for variant in family['variants']}
            self.assertEqual(variants[character['id']]['scopes'], ['character'])
            self.assertEqual(variants[character['id']]['consumers'], [])
            self.assertEqual(variants[location['id']]['scopes'], [])
            self.assertEqual(variants[location['id']]['consumers'], [
                {'consumer_type': 'location_asset', 'consumer_id': 'lantern_01'}])

    def test_shared_picker_renders_every_domain_as_a_section(self):
        editor = ROOT / 'system/control-center/static/asset-atlas-editor.js'
        script = f"""
const fs=require('fs');global.window={{}};global.esc=value=>String(value);
eval(fs.readFileSync({json.dumps(str(editor))},'utf8'));
const variants=[
  {{id:1,filename:'location.png',consumers:[{{consumer_type:'location_asset'}}]}},
  {{id:2,filename:'house.png',consumers:[{{consumer_type:'real_estate'}}]}},
  {{id:3,filename:'face.png',scopes:['character'],consumers:[]}},
  {{id:4,filename:'blade.png',consumers:[{{consumer_type:'weapon'}}]}},
  {{id:5,filename:'npc.png',consumers:[{{consumer_type:'npc'}}]}},
  {{id:6,filename:'free.png',consumers:[]}}
];
const grouped=window.game1ConsumerAtlasEditor.sections(variants);
if(grouped.map(v=>v.label).join('|')!=='Location Assets|Real Estate|Characters|Weapons & arrows|NPC|Shared / unused')process.exit(2);
const catalog=variants.map(v=>({{atlasKey:v.filename,variants:[{{...v,current:true,published_id:String(v.id),resolution:'8x8'}}]}}));
const state=window.game1ConsumerAtlasEditor.newState();state.picker=true;
const html=window.game1ConsumerAtlasEditor.render(state,{{catalog}});
for(let id=1;id<=6;id++)if(!html.includes(`data-ca-attach="${{id}}"`))process.exit(3);
if(!html.includes('data-ca-section="character"')||!html.includes('data-ca-section="shared"'))process.exit(4);
"""
        result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == '__main__':
    unittest.main()
