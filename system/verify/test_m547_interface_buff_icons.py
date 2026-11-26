"""M547: the Interface / Skills / Buffs preview shares the runtime HUD source."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class InterfaceBuffIcons(unittest.TestCase):
    def test_generated_catalog_and_runtime_source(self):
        subprocess.run([sys.executable, str(ROOT / 'system/tools/build_buff_icon_catalog.py'), '--check'], check=True)
        catalog = json.loads((ROOT / 'system/control-center/static/buff-icons/catalog.json').read_text())
        self.assertEqual([row['effect'] for row in catalog['tiles']], ['might', 'earth', 'life', 'wind'])
        self.assertEqual([row['color'] for row in catalog['tiles']], ['#ae66f5', '#f0524c', '#fad34b', '#5fcaf5'])
        hud = (ROOT / 'src/client/combat/BuffHud.luau').read_text()
        self.assertIn('ipairs(row.iconMask)', hud)
        self.assertNotIn('local MASKS', hud)
        self.assertIn('row.color', hud)

    def test_interface_sections_and_existing_monsters(self):
        html = (ROOT / 'system/control-center/static/index.html').read_text()
        js = (ROOT / 'system/control-center/static/interface-icons.js').read_text()
        for item in ('interface-nav-monsters', 'interface-nav-buffs', 'interface-monsters-panel', 'interface-buffs-panel', 'monster-icon-atlas-preview', 'buff-icon-preview'):
            self.assertEqual(html.count(f'id="{item}"'), 1)
        self.assertIn('Interface / Skills', html)
        self.assertIn('Skills / Buffs', html)
        self.assertIn('monster-icons/catalog.json', js)
        self.assertIn('buff-icons/catalog.json', js)
        self.assertIn('tile.mask.forEach', js)
        self.assertIn('tile.color', js)


if __name__ == '__main__':
    unittest.main()
