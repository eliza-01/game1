"""M123: NPC publication timeline and authored-height spawn regression contracts."""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from monster_store import MonsterStore


class NpcPublicationChronologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='game1-m123-npc-')
        self.root = Path(self.temp.name)
        self.npcs = MonsterStore(self.root, kind='npc')
        self.monsters = MonsterStore(self.root, kind='monster')

    def tearDown(self):
        self.temp.cleanup()

    def create_actor(self, store, slug, name, published=None, updated=1):
        with store.connect() as db:
            db.execute(
                'INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,model_sha256,'
                'model_published_sha256,created_at,updated_at,published_at) VALUES(?,?,?,?,?,?,?,?,?)',
                (slug, name, 'assets/source/model.fbx', '123' if published else None,
                 'sha', 'sha' if published else '', 1.0, updated, published),
            )

    def publish_event(self, slug, at, kind='model'):
        with self.npcs.connect() as db:
            db.execute(
                'INSERT INTO monster_publications(monster_slug,kind,slot,monster_revision,'
                'asset_id,operation_path,sha256,moderation_state,published_at) '
                'VALUES(?,?,?,?,?,?,?,?,?)',
                (slug, kind, '' if kind == 'model' else 'atlas', 1, '123', 'test',
                 'sha', '', at),
            )

    def test_chronological_order_uses_publication_not_name_or_edit_date(self):
        self.create_actor(self.npcs, 'alpha', 'Alpha', 100, updated=900)
        self.create_actor(self.npcs, 'bravo', 'Bravo', 200, updated=10)
        self.create_actor(self.npcs, 'charlie', 'Charlie', None, updated=1000)
        self.publish_event('alpha', 100)
        self.publish_event('bravo', 200)
        rows = self.npcs.list()
        self.assertEqual([row['slug'] for row in rows], ['bravo', 'alpha', 'charlie'])
        self.assertEqual([row['last_published_at'] for row in rows], [200.0, 100.0, None])
        self.assertEqual([row['published_at'] for row in rows], [200.0, 100.0, None])
        self.assertEqual(self.npcs.get('alpha')['model_asset_id'], '123')

    def test_texture_republication_reorders_without_overwriting_model_date(self):
        self.create_actor(self.npcs, 'alpha', 'Alpha', 100)
        self.create_actor(self.npcs, 'bravo', 'Bravo', 200)
        self.publish_event('alpha', 100)
        self.publish_event('bravo', 200)
        self.publish_event('alpha', 300, kind='texture')
        self.assertEqual([x['slug'] for x in self.npcs.list()], ['alpha', 'bravo'])
        self.assertEqual(self.npcs.list()[0]['last_published_at'], 300)
        self.assertEqual(self.npcs.get('alpha')['published_at'], 100)
        with self.npcs.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM monster_publications').fetchone()[0], 3)

    def test_old_npc_without_publication_journal_falls_back_and_monsters_unchanged(self):
        self.create_actor(self.npcs, 'legacy', 'Legacy', 42)
        self.assertEqual(self.npcs.list()[0]['last_published_at'], 42)
        self.create_actor(self.monsters, 'z_monster', 'Z monster', 30)
        self.create_actor(self.monsters, 'a_monster', 'A monster', 50)
        self.assertEqual([r['slug'] for r in self.monsters.list()], ['a_monster', 'z_monster'])
        self.assertNotIn('last_published_at', self.monsters.list()[0])

    def test_schema_and_existing_publication_ids_remain_untouched(self):
        self.create_actor(self.npcs, 'alpha', 'Alpha', 12)
        self.publish_event('alpha', 12)
        with self.npcs.connect() as db:
            schema_before = db.execute('SELECT sql FROM sqlite_master WHERE type="table" ORDER BY name').fetchall()
            rows_before = db.execute('SELECT id,asset_id,published_at FROM monster_publications').fetchall()
        self.npcs.list()
        with self.npcs.connect() as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('SELECT sql FROM sqlite_master WHERE type="table" ORDER BY name').fetchall(), schema_before)
            self.assertEqual(db.execute('SELECT id,asset_id,published_at FROM monster_publications').fetchall(), rows_before)

    def test_browser_displays_timestamp_and_bumps_cache(self):
        js = (ROOT / 'system/control-center/static/npc-assets.js').read_text(encoding='utf-8')
        html = (ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8')
        self.assertIn('npcPublishedTime(row.last_published_at)', js)
        self.assertIn('<td><small>${esc(npcPublishedTime(row.last_published_at))}</small></td>', js)
        self.assertIn('<th>published at</th>', html)
        self.assertIn('<b>last published</b>', js)
        self.assertIn('npc-assets.js?v=5', html)
        # Run the actual formatter, with a narrow Node VM context independent of the DOM.
        formatter = re.search(r'function npcPublishedTime\(value\)\{[^\n]+\}', js)
        self.assertIsNotNone(formatter)
        script = formatter.group() + '''\nif(npcPublishedTime(null)!=='not published')throw Error('missing date');
if(npcPublishedTime(0)!=='not published')throw Error('zero date');
const value=npcPublishedTime(1791867381.949);
if(!value.match(/\\d{2}.*\\d{2}.*\\d{4}/))throw Error('incorrect date '+value);
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class NpcUndergroundPlacementContracts(unittest.TestCase):
    def test_spawn_coordinates_remain_exact_without_raycast_or_radius(self):
        spawner = (ROOT / 'src/server/npc/NpcSpawnerService.luau').read_text(encoding='utf-8')
        self.assertIn('local function spawnPosition(record: any): Vector3', spawner)
        self.assertIn('finite(point.y, 0)', spawner)
        self.assertIn('NpcRigFactory.Create(entity, spawnPosition(record)', spawner)
        self.assertNotIn('Workspace:Raycast', spawner)
        self.assertNotIn('NpcSpawnSurface', spawner)
        self.assertFalse((ROOT / 'src/server/npc/NpcSpawnSurface.luau').exists())
        self.assertIn('if next(state.instances) == nil then', spawner)
        self.assertNotIn('state.record.maxAlive', spawner)

    def test_plugin_markers_distinguish_npc_from_monster(self):
        plugin = (ROOT / 'system/studio-plugin/modules/StudioActorSpawnCommands.luau').read_text(encoding='utf-8')
        self.assertIn('if kind == "monster" then', plugin)
        self.assertIn('if kind == "monster" and radius > 0.01 then', plugin)
        self.assertIn('if kind == "npc" then', plugin)
        self.assertIn('text.Text = string.format("%s\\n%s%s"', plugin)


if __name__ == '__main__':
    unittest.main()
