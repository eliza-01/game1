"""Scoped Location Find/Sync must expose and apply MeshPart physics drift."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system' / 'control-center'
if str(CONTROL) not in sys.path:
    sys.path.insert(0, str(CONTROL))

from services.location_studio_sync_verification import classify_scan
from services.location_asset_sync_history import LocationAssetSyncHistory


def report(*, current: bool) -> dict:
    return {
        'mode': 'current' if current else 'physics',
        'unmanagedMeshParts': 0,
        'meshPending': 0,
        'texturePending': 0,
        'alphaPending': 0,
        'physicsPending': 0 if current else 1,
        'geometryPending': 0,
        'parts': [{
            'managed': True,
            'meshCurrent': True,
            'textureCurrent': True,
            'alphaCurrent': True,
            'physicsCurrent': current,
            'needsMesh': False,
            'needsTexture': False,
            'needsAlpha': False,
            'needsPhysics': not current,
            'republishRequired': False,
            'needsFbxInspection': False,
            'needsCanonicalReplacement': False,
        }],
    }


class ScopedLocationPhysicsSyncTest(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding='utf-8')

    def test_physics_only_drift_is_pending_not_current(self):
        self.assertEqual(classify_scan(report(current=False)), 'pending')
        self.assertEqual(classify_scan(report(current=True)), 'current')

    def test_scan_reports_exact_actual_and_expected_policy(self):
        core = self.source('src/shared/world/MeshPhysicsCore.luau')
        scan = self.source('system/studio-plugin/modules/StudioPublishedMeshHistory.luau')
        self.assertIn('function Core.LocationPhysicsStatus', core)
        self.assertIn('mesh.CollisionFidelity == Core.Fidelity(fidelity)', core)
        for field in ('canCollide', 'canQuery', 'canTouch', 'doubleSided',
                      'collisionFidelity', 'expectedCollisionFidelity'):
            self.assertIn(field, core)
        self.assertIn('MeshPhysics.LocationPhysicsStatus(part,row.meshOptions)', scan)
        self.assertIn('needsPhysics=physics~=nil and not physics.current', scan)
        self.assertIn('physicsPending=physicsPending', scan)

    def test_physics_only_selection_is_authorized_applied_and_verified(self):
        manager = self.source('system/studio-plugin/modules/DecoManager.luau')
        sync = self.source('system/studio-plugin/modules/DecoPlacedAssetSync.luau')
        ui = self.source('system/control-center/static/location-asset-workflow.js')
        bridge = self.source('system/control-center/services/studio_deco_bridge.py')
        self.assertIn('or entry.row.needsAlpha or entry.row.needsPhysics', manager)
        self.assertIn('chosenPhysics[entry.part]=true', sync)
        self.assertIn('Physics.ApplyLocationModel(model, item.physicsNames, row.meshOptions)', sync)
        self.assertIn('Physics.LocationNeedsPhysics(part,row.meshOptions)', sync)
        self.assertIn('Location physics Sync failed:', sync)
        self.assertIn('p.needsMesh||p.needsTexture||p.needsAlpha||p.needsPhysics', ui)
        self.assertIn("physics?'Sync Physics':'Sync'", ui)
        self.assertIn("'physicsUpdated'", bridge)

    def test_physics_change_is_valid_durable_audit(self):
        changes = LocationAssetSyncHistory._validate_changes([
            {'kind': 'physics', 'oldId': 'previous',
             'newId': 'registered', 'count': 3}
        ], allow_empty=False)
        self.assertEqual(changes[0]['kind'], 'physics')
        with self.assertRaises(ValueError):
            LocationAssetSyncHistory._validate_changes([
                {'kind': 'physics', 'oldId': 'unknown',
                 'newId': 'registered', 'count': 1}
            ], allow_empty=False)


if __name__ == '__main__':
    unittest.main()
