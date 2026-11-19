"""M367: cross-NPC published animation linking and source ownership invariants."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore
from api.write_animations import route


class ConnectExistingAnimationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='game1-m367-')
        self.root = Path(self.temp.name)
        actors = MonsterStore(self.root, kind='npc')
        with actors.connect() as db:
            for slug, rig in (('donor', 'rig-a'), ('target', 'rig-b'), ('third', 'rig-a')):
                db.execute('''INSERT INTO monsters(slug,name_en,model_source_path,model_sha256,
                  model_asset_id,model_published_sha256,created_at,updated_at,skeleton_signature,skeleton_structure_signature)
                  VALUES(?,?,?,?,?,?,?,?,?,?)''',
                  (slug, slug.title(), f'assets/source/npcs/{slug}/model.fbx', 'sha', '123', 'sha',
                   0, 0, 'rig-contract', rig))
        self.store = MonsterAnimationStore(self.root, kind='npc')
        self.inbox = self.root / 'inbox'
        self.inbox.mkdir()
        for filename in ('donor_base_idle.rbxm','donor_1hs_attack_01.rbxm','donor_1hs_attack_02.rbxm'):
            (self.inbox / filename).write_bytes(filename.encode())
        self.store.scan_folder('donor', str(self.inbox))
        with self.store.connect() as db:
            db.execute("UPDATE monster_animation_clips SET asset_id='123456',published_sha256=sha256 WHERE monster_slug='donor'")
        self.store.export()
        self.source = self.store.snapshot('donor')['items']

    def tearDown(self):
        self.temp.cleanup()

    def select(self, slot, variant=0):
        return next(row for row in self.source if row['slot']==slot and row['variant']==variant)

    def connect(self, *rows, target='target'):
        return self.store.connect_existing(target, 'donor', [row['binding_id'] for row in rows])

    def test_published_clip_shared_without_copy_and_runtime_export(self):
        idle, attack = self.select('idle'), self.select('attack', 1)
        result = self.connect(idle, attack)
        self.assertEqual(result['connected'], 2)
        target = self.store.snapshot('target')
        self.assertEqual(target['summary']['published'], 2)
        for row in target['items']:
            self.assertTrue(row['linked'])
            self.assertEqual(row['sourceNpc'], 'donor')
            self.assertEqual(row['status'], 'PUBLISHED')
            self.assertEqual(row['asset_id'], '123456')
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM monster_animation_clips').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM monster_animation_publications').fetchone()[0], 0)
        registry = (self.root/'src/shared/npc/NpcAnimationRegistry.luau').read_text(encoding='utf-8')
        self.assertIn('["target"] = table.freeze({', registry)
        self.assertIn('rbxassetid://123456', registry)
        self.assertEqual({row['clip_id'] for row in target['items']},
                         {idle['clip_id'], attack['clip_id']})
        manifest = json.loads((self.root/'assets/manifests/npc-animations.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(row['monster_slug']=='target' for row in manifest['bindings']), 2)
        self.store = MonsterAnimationStore(self.root, kind='npc')
        self.assertEqual(self.store.snapshot('target')['summary']['published'], 2)

    def test_independent_binding_options_and_other_consumers(self):
        row = self.select('attack', 1)
        self.connect(row)
        linked = self.store.snapshot('target')['items'][0]
        self.store.set_animation_options(linked['binding_id'],['unarmed'],35,False)
        self.assertEqual(self.store.snapshot('target')['items'][0]['compatibleWith'], ['unarmed'])
        self.assertEqual(self.store.snapshot('target')['items'][0]['weight'], 35)
        self.assertEqual(next(r for r in self.store.snapshot('donor')['items'] if r['binding_id']==row['binding_id'])['weight'], 100)
        self.connect(row,target='third')
        self.assertEqual(len(self.store.connected_dependents('donor')),2)

    def test_conflict_is_atomic_and_never_overwrites_existing(self):
        idle, attack = self.select('idle'), self.select('attack',1)
        self.connect(idle)
        with self.assertRaisesRegex(ValueError,'already has'):
            self.connect(attack, idle)
        self.assertEqual(len(self.store.snapshot('target')['items']), 1)
        with self.assertRaisesRegex(ValueError,'distinct'):
            self.store.connect_existing('target','donor',[attack['binding_id']]*2)
        with self.assertRaisesRegex(ValueError,'two different'):
            self.store.connect_existing('donor','donor',[idle['binding_id']])
        with self.assertRaisesRegex(ValueError,'unknown'):
            self.store.connect_existing('absent','donor',[idle['binding_id']])
        with self.assertRaisesRegex(ValueError,'missing'):
            self.store.connect_existing('third','donor',['invented'])

    def test_local_or_changed_clip_cannot_link(self):
        row = self.select('idle')
        with self.store.connect() as db:
            db.execute('UPDATE monster_animation_clips SET published_sha256=? WHERE id=?',('different',row['clip_id']))
        with self.assertRaisesRegex(ValueError,'changed'):
            self.connect(row)
        with self.store.connect() as db:
            db.execute('UPDATE monster_animation_clips SET asset_id=NULL WHERE id=?',(row['clip_id'],))
        with self.assertRaisesRegex(ValueError,'unpublished'):
            self.connect(row)

    def test_source_delete_blocked_until_all_dependents_disconnected(self):
        idle = self.select('idle')
        self.connect(idle)
        self.connect(idle, target='third')
        with self.assertRaisesRegex(ValueError, 'connected by NPC'):
            self.store.delete_binding(idle['binding_id'])
        with self.assertRaisesRegex(ValueError, 'disconnect'):
            self.store.delete_profile('donor')
        for slug in ('target','third'):
            link=self.store.snapshot(slug)['items'][0]
            with self.assertRaisesRegex(ValueError,'cannot be renamed'):
                self.store.rename_npc_binding(link['binding_id'],'base',f'{slug}_base_idle.rbxm')
            self.store.delete_binding(link['binding_id'])
            self.assertEqual(self.store.snapshot(slug)['items'],[])
        self.assertEqual(self.store.snapshot('donor')['summary']['published'],3)
        self.store.delete_binding(idle['binding_id'])
        self.assertNotIn(idle['clip_id'],{row['clip_id'] for row in self.store.snapshot('donor')['items']})
        self.store.delete_profile('donor')

    def test_scan_target_creates_local_clip_not_modifying_donor(self):
        idle=self.select('idle')
        self.connect(idle)
        (self.inbox/'target_base_idle.rbxm').write_bytes(b'local different animation')
        donor_before = next(row for row in self.store.snapshot('donor')['items'] if row['clip_id']==idle['clip_id'])
        self.store.scan_folder('target',str(self.inbox))
        destination=self.store.snapshot('target')['items'][0]
        self.assertFalse(destination['linked'])
        self.assertNotEqual(destination['clip_id'],idle['clip_id'])
        self.assertEqual(destination['status'],'LOCAL_ONLY')
        self.assertEqual(self.store.snapshot('donor')['summary']['published'],3)
        self.assertEqual(next(row for row in self.store.snapshot('donor')['items'] if row['clip_id']==idle['clip_id'])['sha256'],donor_before['sha256'])

    def test_source_publication_updates_propagate_without_reconnect(self):
        idle = self.select('idle')
        self.connect(idle)
        with self.store.connect() as db:
            db.execute('UPDATE monster_animation_clips SET asset_id=? WHERE id=?',
                       ('987654321', idle['clip_id']))
        self.store.export()
        result = self.store.snapshot('target')['items'][0]
        self.assertEqual(result['asset_id'], '987654321')
        self.assertEqual(result['clip_id'], idle['clip_id'])
        self.assertIn('rbxassetid://987654321',
                      (self.root/'src/shared/npc/NpcAnimationRegistry.luau').read_text(encoding='utf-8'))

    def test_http_route_connect_wires_server_store(self):
        selected=self.select('idle')
        deps={'animation_speed_scaling':None,'animations':None,'monster_animations':None,
              'npc_animations':self.store,'publication_credentials':None}
        payload={'targetNpc':'target','sourceNpc':'donor','bindingIds':[selected['binding_id']]}
        status, result = route('/api/npc-animations/connect',lambda:payload,deps)
        self.assertEqual(status,200)
        self.assertEqual(result['connected'],1)
        status, err=route('/api/npc-animations/connect',lambda:payload,deps)
        self.assertEqual(status,400)
        self.assertIn('already has',err['error'])

    def test_monster_store_does_not_expose_npc_links(self):
        MonsterStore(self.root, kind='monster')
        other=MonsterAnimationStore(self.root, kind='monster')
        with self.assertRaisesRegex(ValueError,'only supported for NPCs'):
            other.connect_existing('target','donor',['a'])


if __name__ == '__main__':
    unittest.main()
