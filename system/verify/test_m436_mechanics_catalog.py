"""M436 mechanics: real socket contracts, strict read-only source access, UI wiring."""
from __future__ import annotations
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.mechanics import route as mechanics_route
from api.read_dispatch import dispatch
from mechanics.catalog import DOMAINS, SOURCES, snapshot, permitted_source


class MechanicsM436(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = snapshot()
        cls.house = cls.catalog['domains'][0]['items']

    def test_technical_cards_are_compact_complete_and_extensible(self):
        self.assertEqual([d['id'] for d in self.catalog['domains']], ['house','npc','monster','character'])
        self.assertEqual(len(self.house), 10)
        self.assertEqual(len({card['id'] for card in self.house}), len(self.house))
        for card in self.house:
            self.assertTrue(card['summary'] and card['sections'] and card['sources'])
            self.assertTrue(card['scope'] in ('shared', 'asset'))
            for source in card['sources']:
                self.assertTrue((ROOT/source['path']).is_file(), (card['id'], source['path']))
                self.assertEqual(permitted_source(card['id'], source['id'])[0], source['path'])
        # Per NPC/monster script registration is per item, not global to the domain.
        self.assertEqual(DOMAINS[1]['items'], [])
        self.assertEqual(DOMAINS[2]['items'], [])

    def test_socket_names_and_roles_match_the_real_luau_contract(self):
        contract = (ROOT/'src/shared/world/HouseSocketContract.luau').read_text('utf-8')
        service = (ROOT/'src/server/world/HouseSocketService.luau').read_text('utf-8')
        elevator = (ROOT/'src/shared/world/HouseElevatorPolicy.luau').read_text('utf-8')
        cards = {card['id']: card for card in self.house}
        for key in ('door','padlock','elevator','floor-spawn','chest','chimney','fireplace'):
            for name in cards[key]['sockets']:
                if name.endswith('_socket') and name != 'door_01_hinge_socket':
                    self.assertIn(name, contract, (key,name))
        # Pot's attachment belongs to the placed cooking_pot_01 asset, not to a house.
        self.assertNotIn('cooking_pot_socket', cards['fireplace']['sockets'])
        self.assertIn('cooking_pot_socket', '\n'.join(
            line for section in cards['fireplace']['sections'] for line in section['lines']))
        pot_mount = (ROOT/'src/server/world/HouseSocketAssetMount.luau').read_text('utf-8')
        self.assertIn('FindFirstChild("cooking_pot_socket", true)', pot_mount)
        self.assertIn('Mount.Spawn("cooking_pot_01"',
                      (ROOT/'src/server/world/HouseFireplaceService.luau').read_text('utf-8'))
        self.assertIn('door_<NN>_hinge_socket', (ROOT/'docs/workflows/REAL_ESTATE_SOCKET_AND_PLOT_PIVOT_M373_RU.md').read_text('utf-8'))
        self.assertIn('HouseSocketInteract', service)
        self.assertIn('cooldown[player]', service)
        self.assertIn('HouseSocketContract.Definitions', cards['socket-registry']['sockets'])
        self.assertIn('houseplant_%02d', contract)
        self.assertIn('houseplant_%03d', contract)
        self.assertIn('DestinationSocket', elevator)
        self.assertIn('CameraSync.Align', (ROOT/'src/server/world/HouseElevatorService.luau').read_text('utf-8'))

    def test_only_registered_card_sources_can_be_read(self):
        status, payload = mechanics_route(urlparse('/api/mechanics'))
        self.assertEqual(status, 200)
        self.assertEqual(payload['version'], 1)
        self.assertEqual(len(payload['domains'][0]['items']), 10)
        status, payload = mechanics_route(urlparse('/api/mechanics/source?item=door&source=door-service'))
        self.assertEqual(status, 200)
        self.assertEqual(payload['path'], 'src/server/world/HouseDoorService.luau')
        self.assertIn('function Doors.Toggle', payload['content'])
        for path in (
            '/api/mechanics/source?item=door&source=socket-effects',
            '/api/mechanics/source?item=door&source=../../.env',
            '/api/mechanics/source?item=unknown&source=door-service',
            '/api/mechanics/source?item=door&source=../../../control-center/host_agent.py',
        ):
            self.assertEqual(mechanics_route(urlparse(path))[0], 404, path)
        self.assertIsNone(mechanics_route(urlparse('/api/mechanics/other')))

    def test_get_dispatch_exposes_catalog_without_other_dependencies(self):
        status, payload = dispatch(urlparse('/api/mechanics'), {}, lambda: {})
        self.assertEqual(status, 200)
        self.assertEqual(payload['domains'][0]['id'], 'house')
        status, payload = dispatch(urlparse('/api/mechanics/source?item=elevator&source=elevator-policy'), {}, lambda: {})
        self.assertEqual(status, 200)
        self.assertIn('Policy.Options', payload['content'])

    def test_cannot_read_symlink_outside_project(self):
        from tempfile import TemporaryDirectory
        from api import mechanics as api
        with TemporaryDirectory() as tmp:
            temp = Path(tmp)
            (temp/'src/server/world').mkdir(parents=True)
            target = temp/'src/server/world/HouseDoorService.luau'
            try:
                target.symlink_to(ROOT/'system/control-center/host_agent.py')
            except OSError:
                self.skipTest('symlinks unavailable')
            with patch.object(api, 'PROJECT_ROOT', temp):
                self.assertEqual(api.route(urlparse('/api/mechanics/source?item=door&source=door-service'))[0], 404)

    def test_all_ui_navigation_and_assets_are_wired(self):
        index = (ROOT/'system/control-center/static/index.html').read_text('utf-8')
        app = (ROOT/'system/control-center/static/character-assets.js').read_text('utf-8')
        view = (ROOT/'system/control-center/static/mechanics.js').read_text('utf-8')
        for needle in ('nav-mechanics', 'mechanics-view', 'mechanics-domains', 'mechanics-list', 'mechanics-refresh',
                       'mechanics.css?v=436','mechanics.js?v=436'):
            self.assertIn(needle,index)
        for needle in ('ASSET_MANAGER_VIEWS', "setView('mechanics')", "view!=='mechanics'", "window.game1MechanicsLoad"):
            self.assertIn(needle,app)
        for needle in ('/api/mechanics/source', 'encodeURIComponent', 'Кратко', 'Полная карта', 'Скрипты', 'createElement'):
            self.assertIn(needle,view)
        self.assertNotIn('innerHTML', view)
        self.assertNotIn('setInterval', view)

if __name__=='__main__':
    unittest.main()
