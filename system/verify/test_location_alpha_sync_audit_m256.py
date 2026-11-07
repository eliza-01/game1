"""M256: Alpha-only Studio Sync must survive the durable audit boundary."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))

from services.location_asset_sync_history import LocationAssetSyncHistory


class MemoryAudit:
    def __init__(self):
        self.events = []

    def ensure_schema(self):
        return None

    def append(self, event):
        if not any(row['operationId'] == event['operationId'] for row in self.events):
            self.events.append(event)

    def page(self, slug, *, limit, before=None):
        rows = [row for row in reversed(self.events) if row['slug'] == slug]
        return {'events': rows[:limit], 'nextCursor': None}


class LocationAlphaSyncAuditM256(unittest.TestCase):
    def report(self, old='Overlay', new='Opaque'):
        change = {'kind': 'alpha', 'oldId': old, 'newId': new, 'count': 1}
        return {
            'operationId': 'a' * 32,
            'models': 1,
            'parts': 1,
            'matchedModels': 1,
            'pendingGeometry': 0,
            'changes': [change],
            'instances': [{
                'instanceId': 'placed_stone_01',
                'studioPath': 'Workspace.placed_stone_01',
                'changes': [change],
            }],
        }

    def test_alpha_policy_change_is_written_to_wal_and_database(self):
        with TemporaryDirectory() as directory:
            database = MemoryAudit()
            history = LocationAssetSyncHistory(Path(directory), database=database)
            event = history.append(
                slug='stone_pillar_01', binding_revision=2, studio=self.report())
            self.assertEqual(event['changes'][0], {
                'kind': 'alpha', 'oldId': 'Overlay', 'newId': 'Opaque', 'count': 1})
            self.assertEqual(database.events[0]['instances'][0]['changes'], event['changes'])
            self.assertIn('"kind":"alpha"', history.path.read_text(encoding='utf-8'))

    def test_missing_surface_can_transition_to_transparency(self):
        with TemporaryDirectory() as directory:
            history = LocationAssetSyncHistory(Path(directory), database=MemoryAudit())
            event = history.append(slug='bush_01', binding_revision=3,
                                   studio=self.report('missing', 'Transparency'))
            self.assertEqual(event['changes'][0]['oldId'], 'missing')

    def test_installed_plugin_enum_prefix_is_normalized_for_compatibility(self):
        with TemporaryDirectory() as directory:
            history = LocationAssetSyncHistory(Path(directory), database=MemoryAudit())
            event = history.append(slug='stone_pillar_01', binding_revision=2,
                studio=self.report('Enum.AlphaMode.Overlay', 'Enum.AlphaMode.Opaque'))
            self.assertEqual(event['changes'][0]['oldId'], 'Overlay')
            self.assertEqual(event['changes'][0]['newId'], 'Opaque')

    def test_unbounded_alpha_values_are_rejected(self):
        with TemporaryDirectory() as directory:
            history = LocationAssetSyncHistory(Path(directory), database=MemoryAudit())
            for old, new in (
                    ('Overlay', 'missing'),
                    ('Overlay', 'arbitrary')):
                with self.subTest(old=old, new=new):
                    with self.assertRaisesRegex(ValueError, 'history entry'):
                        history.append(slug='stone_pillar_01', binding_revision=2,
                                       studio=self.report(old, new))

    def test_studio_emits_enum_name_not_tostring_prefix(self):
        source = (ROOT / 'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text(
            encoding='utf-8')
        self.assertIn('if change.mode then change.mode.Name else "missing"', source)
        self.assertNotIn('if change.mode then tostring(change.mode) else "missing"', source)


if __name__ == '__main__':
    unittest.main()
