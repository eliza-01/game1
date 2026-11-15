"""Read-only Location LOD readiness over the existing Place Registry revisions.

There is deliberately no second Studio scanner, mutable placement database or
runtime Place builder here. The authoring Place is never changed by this service.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from time import time

from .place_registry.catalog import build_catalog


class LocationLodManager:
    def __init__(self, assets, place_registry):
        self.assets = assets
        self.registry = place_registry
        self._verified = None  # Last scan by THIS process, not a claim about Studio edits.

    def scan(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or payload:
            raise ValueError('LOD Manager Scan accepts an empty request only')
        # The authoritative inventory and the append-only snapshot are owned by
        # Place Registry. Do not make a second HTTP/Studio implementation.
        result = self.registry.operate('scan')
        revision = result['revision']['revisionId']
        self._verified = (revision, time(), self.registry.studio_mutation_counter)
        return {'scan': {'revisionId': revision,
                         'unchanged': result['revision']['unchanged'],
                         'incomplete': result['incomplete']},
                'overview': self.overview()}

    def overview(self) -> dict:
        catalog = build_catalog(self.assets)
        published = {row['slug'] for row in catalog['items']}
        assets = self.assets.snapshot()['items']
        by_slug = {r['slug']: r for r in assets}
        revisions = self.registry.revisions.page(10)
        latest = revisions[0] if revisions else None
        report = self.registry.revisions.get(latest['id']) if latest else None
        rows = report['placements'] if report else []
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['slug']].append(row)
        catalog_matches = bool(latest and latest['registry_digest'] == catalog['digest'])
        if not latest:
            freshness = 'NO_SNAPSHOT'
        elif not catalog_matches:
            freshness = 'CATALOG_CHANGED'
        elif (self._verified and self._verified[0] == latest['id']
              and self._verified[2] == self.registry.studio_mutation_counter):
            freshness = 'SCANNED_THIS_SESSION'
        else:
            freshness = 'NOT_LIVE_VERIFIED'
        counts = Counter()
        items = []
        for slug in sorted(set(by_slug) | set(grouped)):
            asset = by_slug.get(slug)
            placements = grouped[slug]
            lod1 = (asset or {}).get('lod1') or {}
            lod2 = (asset or {}).get('lod2') or {}
            lod1_active = lod1.get('status') == 'PUBLISHED' and bool(lod1.get('modelAssetId'))
            lod2_active = lod2.get('status') == 'PUBLISHED' and bool(lod2.get('modelAssetId'))
            red = not lod1_active
            issues = {
                'missingId': sum(not r.get('placementId') for r in placements),
                'duplicateId': sum(r.get('duplicateId') is True for r in placements),
                'ambiguous': sum(r.get('ambiguous') is True for r in placements),
                'noModel': sum(r.get('hasModel') is not True for r in placements),
                'collisionReview': sum(r.get('needsCollision') is True or
                                       r.get('needsRecapture') is True for r in placements),
                'truncated': sum(any('512' in msg for msg in r.get('issues', []))
                                 for r in placements),
            }
            for name, count in issues.items():
                counts[name] += count
            items.append({
                'slug': slug, 'category': (asset or {}).get('category') or '',
                'count': len(placements), 'fullStatus': (asset or {}).get('status') or 'NOT_REGISTERED',
                'fullModelId': str((asset or {}).get('model_asset_id') or ''),
                'lod1Status': lod1.get('status') or 'NOT_REGISTERED',
                'lod1ModelId': str(lod1.get('modelAssetId') or '') if lod1_active else '',
                'lod2Status': lod2.get('status') or 'NOT_SUPPORTED',
                'lod2ModelId': str(lod2.get('modelAssetId') or '') if lod2_active else '',
                'indicator': 'red' if red else 'green' if lod2_active else 'yellow',
                'issues': issues,
                'recognizedByCatalog': slug in published,
            })
        warnings = report.get('warnings', []) if report else []
        return {
            'schemaVersion': 1, 'domain': 'location_assets',
            'snapshot': None if not latest else {
                'revisionId': latest['id'], 'recordedUtc': latest['recorded_utc'],
                'placeId': latest['place_id'], 'fingerprint': latest['fingerprint'],
                'catalogDigest': latest['registry_digest'],
                'catalogMatches': catalog_matches, 'freshness': freshness,
                'verifiedUtc': int(self._verified[1]) if freshness == 'SCANNED_THIS_SESSION' else None,
                'warnings': warnings[:50],
                'total': latest['total'], 'issues': latest['issues'],
            },
            'summary': {'placements': len(rows), 'typesWithPlacements': len(grouped),
                        'registeredTypes': len(by_slug), 'lod1Types': sum(
                            i['lod1Status'] == 'PUBLISHED' for i in items),
                        'missingId': counts['missingId'], 'duplicateId': counts['duplicateId'],
                        'ambiguous': counts['ambiguous'], 'noModel': counts['noModel'],
                        'collisionReview': counts['collisionReview'], 'truncated': counts['truncated'],
                        'scanWarnings': len(warnings)},
            'items': items, 'revisions': [
                {'id': r['id'], 'recordedUtc': r['recorded_utc'],
                 'placeId': r['place_id'], 'total': r['total']} for r in revisions],
            'build': {'enabled': False, 'reason': 'Runtime Place builder and verified backup are not implemented',
                      'sourcePlaceMutated': False},
            'scope': 'Published Location Mesh IDs recognized by Place Registry only; unknown/unpublished Workspace objects are not inventoried',
        }
