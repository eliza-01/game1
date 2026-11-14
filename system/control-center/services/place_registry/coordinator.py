"""Place Registry use cases: catalog → Studio scan → immutable revision → explicit repair/sync.

Must not access unrelated domains or auto-run repair during inventory. Studio
mutation is always a separate operation validated against an earlier scan token.
"""
from __future__ import annotations

from .catalog import build_catalog, validate_report
from .journal import PlaceOperationJournal
from threading import RLock


class LocationPlaceRegistry:
    def __init__(self, location_assets, revisions, studio_bridge):
        self.assets = location_assets
        self.revisions = revisions
        self.studio = studio_bridge
        self._last_scan = None
        self.journal = PlaceOperationJournal(self.revisions.path)
        self._lock = RLock()

    def revisions_page(self, limit=20):
        return self.revisions.page(limit)

    def revision(self, revision_id):
        return self.revisions.get(revision_id)

    def diff(self, before, after):
        return self.revisions.diff(before, after)

    def action_journal(self, limit=40):
        return self.journal.page(limit)

    def operate(self, phase, *, scan_token='', keys=None, action_id=None):
        # Serialized Studio operations prevent a second request from stealing
        # the one-shot Studio Bridge or racing a different scan token.
        with self._lock:
            return self._operate(phase, scan_token=scan_token, keys=keys, action_id=action_id)

    def _operate(self, phase, *, scan_token='', keys=None, action_id=None):
        catalog = build_catalog(self.assets)
        if phase == 'undo':
            candidate = self.journal.undo_candidate(action_id)
            bridge = self.studio(catalog=catalog, phase='undo',
                                 undo_operation_id=candidate['operation_id'])
            result = bridge.get('result')
            if not isinstance(result, dict) or result.get('undone') is not True:
                raise ValueError('Studio did not confirm Undo; journal unchanged')
            self._last_scan = None
            self.journal.mark_undone(action_id, candidate['operation_id'])
            return {'undone': True, 'actionId': action_id,
                    'note': 'Studio Undo выполнен; ревизия будет обновлена после Scan'}
        if phase == 'scan':
            bridge = self.studio(catalog=catalog, phase='scan')
            report = bridge.get('scan')
            if not isinstance(report, dict) or bridge.get('catalogDigest') != catalog['digest']:
                raise ValueError('invalid Studio Place Registry scan')
            records = validate_report(report, catalog)
            # The inventory loaded by Studio is reusable by per-slug DecoManager.
            # A failure to persist an inventory MUST fail visibly, not be hidden.
            incomplete = bool(report.get('warnings'))
            for item in bridge.get('inventory', []):
                slug = item.get('slug', '')
                if slug not in {r['slug'] for r in catalog['items']}:
                    raise ValueError('Studio reported Mesh IDs outside Location Assets')
                expected = {m['modelAssetId'] for a in catalog['items'] if a['slug'] == slug
                            for m in a['models']}
                versions = item.get('models', [])
                if {v.get('modelAssetId') for v in versions} != expected:
                    raise ValueError('Studio changed published history for ' + slug)
                completed = [v for v in versions if v.get('meshes')]
                if len(completed) != len(versions):
                    incomplete = True
                if completed:
                    self.assets.record_mesh_id_inventory(slug, completed)
            revision = self.revisions.add(report, catalog['digest'])
            result = {'scanToken': bridge.get('scanToken'), 'revision': revision,
                      'summary': self._summary(records), 'placements': records,
                      'warnings': report.get('warnings', []), 'incomplete': incomplete,
                      'placeId': report.get('placeId', 0)}
            self._last_scan = (result['scanToken'], catalog['digest'], revision['revisionId'], incomplete, result['placeId'], records)
            return result
        if phase not in ('repair', 'sync', 'select'):
            raise ValueError('unsupported Place Registry operation')
        if not self._last_scan or (scan_token, catalog['digest']) != self._last_scan[:2]:
            raise ValueError('Scan again: registry or Studio inventory has changed')
        if phase != 'select' and self._last_scan[3]:
            raise ValueError('Place Registry scan incomplete: some published Mesh histories are unavailable; Repair/Sync refused')
        bridge = self.studio(catalog=catalog, phase=phase, scan_token=scan_token, keys=keys)
        result = bridge.get('result')
        if not isinstance(result, dict) or type(result.get('changed')) is not int:
            raise ValueError('invalid Studio mutation result')
        if phase != 'select':
            scan = self._last_scan
            self._last_scan = None  # Even if audit persistence fails: Place may have changed.
            if not isinstance(bridge.get('operationId'), str):
                raise RuntimeError('Studio operation committed, but audit identity is missing; Scan Place before continuing')
            record_keys = set(keys or [])
            selected = [{'key': r['key'], 'slug': r['slug'], 'name': r['name']}
                        for r in scan[5] if r['key'] in record_keys]
            try:
                result['journalId'] = self.journal.record(
                    revision_id=scan[2], place_id=scan[4],
                    operation_id=bridge['operationId'], action=phase,
                    selected=selected, result=result)
            except Exception as exc:
                raise RuntimeError('Studio operation may have changed Place, but journal write failed; Scan and inspect before retry: ' + str(exc)) from exc
        return result

    @staticmethod
    def _summary(rows):
        return {'placements': len(rows), 'outdatedMesh': sum(r['needsMesh'] or r.get('needsRig', False) for r in rows),
                'outdatedTexture': sum(r['needsTexture'] for r in rows),
                'outdatedMaterial': sum(bool(r.get('needsMaterial')) for r in rows),
                'outdatedAlpha': sum(bool(r.get('needsAlpha')) for r in rows),
                'outdatedCollision': sum(bool(r.get('needsCollision')) for r in rows),
                'structure': sum(r['needsStructure'] for r in rows),
                'duplicateIds': sum(r['duplicateId'] for r in rows),
                'ambiguous': sum(r['ambiguous'] for r in rows)}
