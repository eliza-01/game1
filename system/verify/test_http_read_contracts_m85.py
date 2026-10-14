"""Real loopback HTTP requests through the extracted Host Agent Handler.

No production SQLite or Roblox services are imported: handlers are extracted
from the current host_agent.py with injected fake application dependencies.
"""
import ast
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from types import MappingProxyType
import sys
import threading
import unittest
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api.read_dispatch import dispatch


class FakeRepository:
    def __init__(self, name):
        self.name = name
        self.db = Path('/sandbox/game1.db')
        self.fail = False
        self.calls = []

    def snapshot(self, *args):
        self.calls.append(('snapshot', args))
        if self.fail:
            raise ValueError('test read failure')
        return {'repository': self.name, 'selected': args[0] if args else None}

    def active_id(self):
        return 'human_female'

    def publications(self, ident):
        return [{'id': ident, 'repository': self.name}]

    def editor_state(self, session):
        return {'sessionId': session}

    def register(self, payload):
        self.calls.append(('register', payload))
        return {'saved': payload}

    def delete_binding(self, name):
        self.calls.append(('delete', name))
        return {'removed': name}


class HostApiContractsM85(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'system/control-center/host_agent.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Handler')
        repositories = {key: FakeRepository(key) for key in (
            'store', 'animations', 'weapons', 'monsters', 'monster_animations',
            'npcs', 'npc_animations', 'npc_equipment', 'location_assets',
            'npc_spawns', 'monster_spawns', 'animation_speed_scaling',
            'options_store', 'timelines', 'locations'
        )}
        cls.repositories = repositories
        namespace = {
            'BaseHTTPRequestHandler': BaseHTTPRequestHandler,
            'json': json, 'urlparse': urlparse, 'unquote': unquote, 'token': 'test-token',
            'dispatch_read_request': dispatch,
            'control_agent_build': 'm85-contract', 'ROOT': ROOT,
            'publication_config': lambda: {'configured': True},
        }
        namespace.update(repositories)
        namespace['READ_SOURCES'] = MappingProxyType({
            'characters': repositories['store'], 'animations': repositories['animations'],
            'weapons': repositories['weapons'], 'monsters': repositories['monsters'],
            'monster_animations': repositories['monster_animations'], 'npcs': repositories['npcs'],
            'npc_animations': repositories['npc_animations'], 'npc_equipment': repositories['npc_equipment'],
            'location_assets': repositories['location_assets'], 'npc_spawns': repositories['npc_spawns'],
            'monster_spawns': repositories['monster_spawns'],
            'animation_speed_scaling': repositories['animation_speed_scaling'],
            'options': repositories['options_store'], 'timelines': repositories['timelines'],
            'locations': repositories['locations'],
            'publication_config': namespace['publication_config'],
        })
        namespace['read_host_info'] = lambda: {
            'build': 'm85-contract', 'project': 'game1', 'projectRoot': str(ROOT),
            'db': str(repositories['store'].db),
            'publication': namespace['publication_config'](),
        }
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'host_agent.py', 'exec'), namespace)
        class QuietHandler(namespace['Handler']):
            def log_message(self, *_):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, url, payload=None, authorized=True):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            headers = {'Content-Type': 'application/json'}
            if authorized:
                headers['X-Control-Token'] = 'test-token'
            conn.request(method, url, body=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_auth_and_unknown_path(self):
        self.assertEqual(self.request('GET', '/api/characters', authorized=False), (401, {'error': 'unauthorized'}))
        self.assertEqual(self.request('GET', '/api/unknown'), (404, {'error': 'not found'}))
        self.assertEqual(self.request('POST', '/api/weapons', authorized=False)[0], 401)
        self.assertEqual(self.request('DELETE', '/api/characters/test', authorized=False)[0], 401)

    def test_all_read_catalog_endpoints_are_preserved(self):
        entries = (
            '/api/characters', '/api/animations', '/api/weapons',
            '/api/monsters', '/api/monster-animations', '/api/npcs',
            '/api/npc-animations', '/api/location-assets', '/api/npc-equipment',
            '/api/npc-spawns', '/api/monster-spawns', '/api/animation-speed-scaling',
            '/api/options', '/api/timelines', '/api/locations',
            '/api/timelines/editor-state?session=edit-1', '/api/agent/info',
        )
        for path in entries:
            with self.subTest(path=path):
                status, payload = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertIsInstance(payload, dict)
        for path in ('/api/npcs/abc/publications', '/api/monsters/abc/publications',
                     '/api/weapons/abc/publications', '/api/location-assets/abc/publications',
                     '/api/characters/abc/publications'):
            status, payload = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertEqual(payload['items'][0]['id'], 'abc')

    def test_filter_publication_and_read_errors(self):
        status, value = self.request('GET', '/api/animations?character=TestHero')
        self.assertEqual((status, value['selected']), (200, 'testhero'))
        self.assertEqual(value['publication']['configured'], True)
        status, value = self.request('GET', '/api/animations')
        self.assertEqual(value['selected'], 'human_female')
        self.assertEqual(status, 200)
        self.repositories['options_store'].fail = True
        try:
            self.assertEqual(self.request('GET', '/api/options'), (400, {'error': 'test read failure'}))
        finally:
            self.repositories['options_store'].fail = False

    def test_legacy_write_endpoints_still_dispatch(self):
        status, payload = self.request('POST', '/api/characters', {'id': 'example'})
        self.assertEqual((status, payload), (200, {'saved': {'id': 'example'}}))
        status, payload = self.request('DELETE', '/api/npc-animation-bindings/b-001')
        self.assertEqual((status, payload), (200, {'removed': 'b-001'}))


if __name__ == '__main__':
    unittest.main()
