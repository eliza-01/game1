"""M343: Location Assets versioned Part-only Collision Blueprint contract."""
from __future__ import annotations

import copy
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_collision_blueprint import validate
from location_asset_store import LocationAssetStore
import location_asset_store as location_store_module
from api.read_world import route as read_route


def sample():
    return {'schemaVersion':1, 'pivot':'Model:GetPivot()', 'parts':[
        {'id':'wall_01', 'name':'Wall 01', 'shape':'Block', 'size':[10,5,0.5],
         'localCFrame':[2.0,0.0,0.0,1,0,0,0,1,0,0,0,1],
         'collisionGroup':'Default','canQuery':True,'canTouch':False},
        {'id':'stairs_02', 'name':'Stairs', 'shape':'Wedge', 'size':[2,2,5],
         'localCFrame':[0,1,0,0,-1,0,1,0,0,0,0,1],
         'collisionGroup':'Default','canQuery':True,'canTouch':False},
    ]}


class CollisionBlueprintM343(unittest.TestCase):
    def test_normalized_parts_sorted_and_original_preserved(self):
        value=sample()
        original=copy.deepcopy(value)
        result=validate(value,slug='stone_fence_01')
        self.assertEqual(value, original)
        self.assertEqual([part['id'] for part in result['parts']], ['stairs_02','wall_01'])

    def test_reject_nonprimitive_and_duplicate(self):
        value=sample();value['parts'][0]['shape']='MeshPart'
        with self.assertRaisesRegex(ValueError, 'shape'):
            validate(value,slug='stone_fence_01')
        value=sample();value['parts'][1]['id']='wall_01'
        with self.assertRaisesRegex(ValueError, 'Part ID'):
            validate(value,slug='stone_fence_01')

    def test_reject_bad_transform_and_size(self):
        value=sample();value['parts'][0]['localCFrame'][3]=2.0
        with self.assertRaisesRegex(ValueError, 'orthonormal'):
            validate(value,slug='stone_fence_01')
        value=sample();value['parts'][0]['localCFrame'][3]=-1.0
        with self.assertRaisesRegex(ValueError, 'mirrored'):
            validate(value,slug='stone_fence_01')
        value=sample();value['parts'][0]['size']=[0,1,1]
        with self.assertRaisesRegex(ValueError, 'positive'):
            validate(value,slug='stone_fence_01')

    def test_explicit_pivot_and_bounded_recipe(self):
        value=sample();value['pivot']='Workspace:Something'
        with self.assertRaisesRegex(ValueError, 'pivot'):
            validate(value,slug='stone_fence_01')
        value=sample();value['parts']*=129
        with self.assertRaisesRegex(ValueError, '1..256'):
            validate(value,slug='stone_fence_01')

    def test_real_sqlite_revisions_idempotency_and_http_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            store=LocationAssetStore(root)
            with store.connect() as db:
                db.execute('INSERT INTO location_assets(slug,name_en,category,created_at,updated_at) '
                           'VALUES(?,?,?,?,?)', ('stone_fence_01','Stone Fence','fence',0.0,0.0))
            first=store.save_collision_blueprint('stone_fence_01',
                {'expectedRevision':0,'blueprint':sample()})
            self.assertEqual(first['revision'],1)
            self.assertEqual(len(first['blueprint']['parts']),2)
            repeat=store.save_collision_blueprint('stone_fence_01',
                {'expectedRevision':1,'blueprint':sample()})
            self.assertEqual(repeat['revision'],1)
            with self.assertRaisesRegex(ValueError,'changed since Capture'):
                store.save_collision_blueprint('stone_fence_01',
                    {'expectedRevision':0,'blueprint':sample()})
            changed=sample();changed['parts'][0]['size'][0]=11
            second=store.save_collision_blueprint('stone_fence_01',
                {'expectedRevision':1,'blueprint':changed})
            self.assertEqual(second['revision'],2)
            self.assertEqual(store.get('stone_fence_01')['collisionBlueprintRevision'],2)
            self.assertEqual(store.get('stone_fence_01')['collisionBlueprintPartCount'],2)
            status, data=read_route(type('URL',(),{'path':'/api/location-assets/stone_fence_01/collision-blueprint','query':''})(),
                                   {'location_assets':store},lambda:{})
            self.assertEqual(status,200)
            self.assertEqual(data['revision'],2)
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM location_asset_collision_blueprints').fetchone()[0],2)

    def test_rename_and_retirement_preserve_collision_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            store=LocationAssetStore(root)
            with store.connect() as db:
                db.execute('INSERT INTO location_assets(slug,name_en,category,created_at,updated_at) '
                           'VALUES(?,?,?,?,?)', ('stone_fence_01','Stone Fence','fence',0.0,0.0))
            store.save_collision_blueprint('stone_fence_01',
                 {'expectedRevision':0,'blueprint':sample()})
            renamed=store.rename_identity('stone_fence_01', {'slug':'stone_fence_new',
                'nameEn':'Stone Fence', 'category':'fence', 'destructible':False,
                'expectedRevision':1})
            self.assertEqual(renamed['collisionBlueprintRevision'],1)
            self.assertIsNone(store.collision_blueprint('stone_fence_01'))
            retired=store.delete('stone_fence_new')
            self.assertTrue(retired['sourceFilesPreserved'])
            import json
            archive=json.loads((root/retired['archived']).read_text(encoding='utf-8'))
            self.assertEqual(len(archive['collisionBlueprints']),1)
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM location_asset_collision_blueprints').fetchone()[0],0)

    def test_unknown_asset_and_invalid_update_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store=LocationAssetStore(Path(temp))
            with self.assertRaisesRegex(ValueError, 'unknown Location Asset'):
                store.save_collision_blueprint('not_registered',
                    {'expectedRevision':0,'blueprint':sample()})
            with self.assertRaisesRegex(ValueError,'invalid Collision Blueprint request'):
                store.save_collision_blueprint('stone_fence_01',
                    {'expectedRevision':0,'blueprint':sample(),'ignore':True})


    def test_first_run_schema_backup_connections_are_closed(self):
        """Every additive schema snapshot must release its Windows file handle."""
        recorded = {}
        real_connect = location_store_module.connect_sqlite

        def tracked_connect(path):
            connection = real_connect(path)
            name = Path(path).name
            if Path(path).parent.name == 'backups' and name.startswith('location_'):
                recorded[name] = connection
            return connection

        with tempfile.TemporaryDirectory() as temp:
            with patch.object(location_store_module, 'connect_sqlite', side_effect=tracked_connect):
                LocationAssetStore(Path(temp))
            prefixes = (
                'location_rig_manifest_m256_',
                'location_mesh_options_m232_',
                'location_surface_material_m249_',
                'location_alpha_m250_',
            )
            for prefix in prefixes:
                with self.subTest(backup=prefix):
                    matches = [conn for name, conn in recorded.items() if name.startswith(prefix)]
                    self.assertEqual(len(matches), 1, 'schema backup must use closing connection')
                    with self.assertRaises(sqlite3.ProgrammingError):
                        matches[0].execute('SELECT 1')



if __name__ == '__main__':
    unittest.main()
