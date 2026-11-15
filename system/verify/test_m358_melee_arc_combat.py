"""M358 checks: real SQLite migration, per-weapon registration and source contracts.

Geometry/victim hitboxes require Roblox Vector2/CFrame and must be validated in
Studio; no Python test is misrepresented as an actual Luau combat simulation.
"""
from __future__ import annotations

from contextlib import closing
import json
import math
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from weapon_store import WeaponStore


def src(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


class MeleeArcM358(unittest.TestCase):
    def test_real_dump_db_migration_preserves_ids_and_existing_weapon_settings(self):
        original = ROOT / '.control-center/game1.db'
        if not original.is_file():
            self.skipTest('diagnostic DB not present (works on installed project without bundled DB)')
        with tempfile.TemporaryDirectory(prefix='m358-db-') as tmp:
            project = Path(tmp)
            (project / '.control-center').mkdir()
            shutil.copy2(original, project / '.control-center/game1.db')
            # sqlite3's transaction context alone does NOT close its file handle.
            with closing(sqlite3.connect(project / '.control-center/game1.db')) as before:
                ids = dict(before.execute('SELECT slug,model_asset_id FROM weapons'))
            weapons = WeaponStore(project)
            rows = weapons.list()
            self.assertEqual(len(rows), len(ids))
            self.assertTrue(all(row['melee_arc_angle_degrees'] == 108 for row in rows))
            self.assertEqual({row['slug']: row['model_asset_id'] for row in rows}, ids)
            self.assertEqual(json.loads((project / 'assets/manifests/weapons.json').read_text())['schemaVersion'],3)
            registry = (project / 'src/shared/weapon/WeaponRegistry.luau').read_text()
            self.assertEqual(registry.count('meleeArcAngleDegrees = 108'), len(rows))
            weapons = WeaponStore(project)  # idempotent restart, unchanged IDs
            self.assertEqual({row['slug']: row['model_asset_id'] for row in weapons.list()}, ids)

    def test_weapon_specific_value_validated_and_exported(self):
        with tempfile.TemporaryDirectory(prefix='m358-weapons-') as tmp:
            project = Path(tmp)
            model = project / 'weapon.fbx'
            model.write_bytes(b'fake test model')
            store = WeaponStore(project)
            for slug,angle,kind in [('sword_one',60,'sword'),('sword_two',180,'sword'),('dagger_one',360,'dagger')]:
                store.register({'slug':slug,'nameEn':slug,'weaponType':kind,'rarity':'common',
                                'modelSourcePath':str(model),'meleeArcAngleDegrees':angle})
            self.assertEqual(store.get('sword_one')['melee_arc_angle_degrees'],60)
            self.assertEqual(store.get('sword_two')['melee_arc_angle_degrees'],180)
            self.assertEqual(store.get('dagger_one')['melee_arc_angle_degrees'],360)
            store.register({'slug':'sword_one','nameEn':'sword_one','weaponType':'sword','rarity':'common',
                            'meleeArcAngleDegrees':108})
            self.assertEqual(store.get('sword_one')['melee_arc_angle_degrees'],108)
            self.assertEqual(store.get('sword_two')['melee_arc_angle_degrees'],180)
            for bad in [-1,0,360.1,math.inf,math.nan,'unknown']:
                with self.subTest(angle=bad),self.assertRaises(ValueError):
                    store.register({'slug':'sword_one','nameEn':'sword_one','weaponType':'sword','rarity':'common',
                                    'meleeArcAngleDegrees':bad})
            self.assertIn('meleeArcAngleDegrees = 180', (project/'src/shared/weapon/WeaponRegistry.luau').read_text())

    def test_arc_owns_damage_without_client_obb_or_extra_reticle_target(self):
        attack = src('src/server/combat/AttackService.luau')
        client = src('src/client/combat/AttackController.luau')
        resolver = src('src/server/combat/AttackDamageResolver.luau')
        hitboxes = src('src/server/combat/EntityHitboxService.luau')
        query = src('src/server/combat/MeleeTargetQuery.luau')
        for module in (attack,client,resolver,query):
            self.assertNotIn('WeaponAttackVolume', module)
            self.assertNotIn('AttackWeaponPose', module)
        self.assertIn('scheduleMeleeArc(',attack)
        self.assertIn('task.delay(window.startTime',attack)
        self.assertIn('MeleeTargetQuery.Find',resolver)
        self.assertIn('query.hitTargets[model] = true',resolver)
        self.assertIn('QueryDamageablesInArc(',hitboxes)
        self.assertNotIn('table.insert(contacts, 1',resolver)
        self.assertIn('contact.model == aimed.model',resolver)
        self.assertIn('MeleeAimUpdate',attack)
        self.assertIn('MeleeAimUpdate',client)
        self.assertIn('BowHitscanService.Release(',attack)
        self.assertIn('BowAimUpdate',client)

    def test_independent_server_geometry_and_vertical_wall_filter(self):
        geometry = src('src/shared/combat/MeleeArcGeometry.luau')
        query = src('src/server/combat/MeleeTargetQuery.luau')
        for name in ('projectedHull','pointInPolygon','segmentContactInSector','insideSector'):
            self.assertIn(name,geometry)
        for field in ('minY','maxY','root.CFrame.LookVector','IsUnobstructed'):
            self.assertIn(field,query)
        self.assertIn('RespectCanCollide = true',query)
        self.assertIn('local HitboxRuntimeFrames = require(', src('src/server/combat/EntityHitboxService.luau'))
        self.assertIn('LEGACY · DEPRECATED · DO NOT USE',src('src/shared/combat/WeaponAttackVolume.luau'))


if __name__ == '__main__':
    unittest.main()
