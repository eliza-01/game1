"""M570: existing spawn parameters are editable, not placement or identity of the zone."""
import unittest
from pathlib import Path
from test_m560_studio_monster_spawns import StudioSpawnTests

ROOT = Path(__file__).resolve().parents[2]

class DatabaseSpawnEditing(unittest.TestCase):
    setUp = StudioSpawnTests.setUp

    def saved(self, **changes):
        return self.store.studio_apply({**self.payload, **changes})['record']

    def update(self, r, **changes):
        return {'spawnId': r['spawnId'], 'expectedUpdatedAtUtc': r['updatedAtUtc'], 'changes': changes}

    def test_edit_and_restore_mode(self):
        a = self.saved(homeRadiusStuds=77)
        saved = self.store.database_update({'updates':[self.update(a, maxAlive=7, deathChase=True, aggressive=False, respawnSeconds=5)]})['records'][0]
        self.assertEqual(saved['position'], a['position'])
        self.assertEqual(saved['placeId'], a['placeId'])
        self.assertEqual(saved['createdAtUtc'], a['createdAtUtc'])
        self.assertEqual(saved['homeRadiusStuds'], 77)
        self.assertTrue(saved['deathChase'])
        self.assertEqual(saved['maxAlive'], 7)
        self.assertIn('"maxAlive":7', self.store.registry_path.read_text())
        self.assertEqual(self.store.studio_catalog()['records'][0], saved)
        with self.assertRaises(ValueError):
            self.store.studio_apply({**self.payload, 'expectedUpdatedAtUtc':a['updatedAtUtc']})
        result = self.store.database_update({'updates':[self.update(saved, deathChase=False)]})['records'][0]
        self.assertFalse(result['deathChase'])
        self.assertEqual(result['homeRadiusStuds'],77)

    def test_batch_rejects_partial_and_placement_edits(self):
        a = self.saved()
        b = self.saved(spawnId='spawn-987654321abc')
        before = self.store.manifest_path.read_bytes(), self.store.registry_path.read_bytes()
        for bad in ({'position':{'x':1}}, {'maxAlive':0}, {'deathChase':1}, {'spawnRadius':None}, {'balanceId':'missing'}, {'enabled':'true'}):
            with self.assertRaises(ValueError):
                self.store.database_update({'updates':[self.update(a, maxAlive=8),self.update(b,**bad)]})
            self.assertEqual(before,(self.store.manifest_path.read_bytes(),self.store.registry_path.read_bytes()))
        stale = self.update(b, maxAlive=9); stale['expectedUpdatedAtUtc']='stale'
        with self.assertRaises(ValueError): self.store.database_update({'updates':[self.update(a,maxAlive=8),stale]})
        self.assertEqual(before,(self.store.manifest_path.read_bytes(),self.store.registry_path.read_bytes()))

    def test_legacy_stays_legacy_until_explicit_identity_change(self):
        manifest=self.store._load()
        a=self.store._validate({**self.payload,'balanceId':None,'monsterSlug':'gremlin'})
        manifest['records'][a['spawnId']]=a; self.store._commit(manifest)
        saved=self.store.database_update({'updates':[self.update(a,maxAlive=4)]})['records'][0]
        self.assertEqual(saved['monsterSlug'],'gremlin')
        self.assertNotIn('balanceId',saved)
        converted=self.store.database_update({'updates':[self.update(saved,balanceId=self.toad['id'])]})['records'][0]
        self.assertEqual(converted['balanceId'],self.toad['id'])
        self.assertEqual(converted['monsterSlug'],'')

    def test_ui_has_guarded_drafts_and_edit_endpoint(self):
        ui=(ROOT/'system/control-center/static/game-balance.js').read_text()
        for token in ('spawnChanges','expectedUpdatedAtUtc','/api/monster-spawns/database-update','leash.hidden=draft.deathChase','!spawnChanges.size','spawnChanges.clear()'):
            self.assertIn(token,ui)
        self.assertIn('/api/monster-spawns/database-update',(ROOT/'system/control-center/api/write_world.py').read_text())
