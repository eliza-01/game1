"""Read-only Location LOD readiness over the existing Place Registry revisions.

There is deliberately no second Studio scanner, mutable placement database or
runtime Place builder here. The authoring Place is never changed by this service.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from time import time
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock

from .location_runtime_build import RuntimePlaceBuilder, build_rows, placement_shape_problem
from .location_streaming_config import LocationStreamingConfig, settings_digest, runtime_mode, distance_profile

from .place_registry.catalog import build_catalog


class LocationLodManager:
    def __init__(self, assets, place_registry, houses=None, house_placements=None):
        self.assets = assets
        self.registry = place_registry
        self.houses = houses
        self.house_placements = house_placements
        self._verified = None  # Last scan by THIS process, not a claim about Studio edits.
        root = Path(self.registry.revisions.path).resolve().parents[1]
        self.builder = RuntimePlaceBuilder(root)
        self.streaming_config = LocationStreamingConfig(root)
        self._preflight = None
        self._build_lock = RLock()

    def read_settings(self):
        return self.streaming_config.read([row['slug'] for row in self.assets.snapshot()['items']])

    def save_settings(self, payload: dict) -> dict:
        # Persistent runtime mode overrides only. Do not mutate Studio or the saved Place.
        with self._build_lock:
            known = [row['slug'] for row in self.assets.snapshot()['items']]
            self.streaming_config.save(payload, known)
            self._preflight = None  # saved Preflight cannot authorize a different selection/profile
            return self.overview()

    def scan(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or payload:
            raise ValueError('LOD Manager Scan accepts an empty request only')
        # The authoritative inventory and the append-only snapshot are owned by
        # Place Registry. Do not make a second HTTP/Studio implementation.
        result = self.registry.operate('scan')
        revision = result['revision']['revisionId']
        self._verified = (revision, time(), self.registry.studio_mutation_counter)
        self._preflight = None
        return {'scan': {'revisionId': revision,
                         'unchanged': result['revision']['unchanged'],
                         'incomplete': result['incomplete']},
                'overview': self.overview()}

    def preflight(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or payload:
            raise ValueError('Runtime preflight accepts an empty request only')
        with self._build_lock:
            overview = self.overview()
            if not overview['snapshot'] or overview['snapshot']['freshness'] != 'SCANNED_THIS_SESSION':
                raise ValueError('Scan Place again in this session before Runtime preflight')
            settings = self.read_settings()
            rows = self.location_rows(overview, settings)
            selected_houses = self.house_selection()
            inspected = self.builder.inspect(rows, settings, selected_houses)
            token = token_urlsafe(32)
            from .house_runtime_compilation import fingerprint
            house_digest = fingerprint(selected_houses)
            self._preflight = (token, inspected['sourceSha256'], overview['snapshot']['revisionId'],
                               settings_digest(settings), house_digest)
            return {'schemaVersion': 1, 'token': token, 'snapshotRevision': overview['snapshot']['revisionId'],
                    'catalogDigest': overview['snapshot']['catalogDigest'],
                    'streamingModes': {slug: runtime_mode(settings, slug) for slug in inspected['counts']},
                    'houseModes': {slug: data['profile']['mode'] for slug,data in selected_houses.items()},
                    'assetDistances': {slug: distance_profile(settings, slug) for slug in inspected['counts']}, 'workspace': settings['workspace'],
                    **inspected, 'backupRequired': True, 'publishAllowed': False,
                    'protectedNotModified': overview['summary']['protectedExternal'],
                    'untouchedLocations': [
                        {'slug': item['slug'], 'count': item['count'],
                         'eligible': item['streamingEligible'],
                         'reason': item['streamingReason']}
                        for item in overview['items']
                        if item['count'] and item['streamingMode'] == 'off'
                    ],
                    'message': 'All scanned registered Location Asset types stream by default; explicit Off overrides remain author-controlled.'}

    def prepare(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or set(payload) != {'token'} or not isinstance(payload['token'], str):
            raise ValueError('Runtime preparation requires a preflight token')
        with self._build_lock:
            if not self._preflight or payload['token'] != self._preflight[0]:
                raise ValueError('Preflight expired; run Preflight again')
            overview = self.overview()
            settings = self.read_settings()
            if settings_digest(settings) != self._preflight[3]:
                raise ValueError('Streaming settings changed since Preflight; run it again')
            rows = self.location_rows(overview, settings)
            selected_houses = self.house_selection()
            from .house_runtime_compilation import fingerprint
            digest_houses = fingerprint(selected_houses)
            if digest_houses != self._preflight[4]:
                raise ValueError('Real Estate selection / Plot bindings changed since Preflight')
            if overview['snapshot']['revisionId'] != self._preflight[2]:
                raise ValueError('Snapshot changed; run Preflight again')
            digest = self._preflight[1]
            self._preflight = None  # One-shot, including failed builds.
            return self.builder.prepare(rows, expected_sha=digest,
                snapshot_id=overview['snapshot']['revisionId'],
                catalog_digest=overview['snapshot']['catalogDigest'], settings=settings,
                house_inputs=selected_houses)

    def reveal_build(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or set(payload) != {'buildId'}:
            raise ValueError('Runtime folder request requires buildId only')
        from .windows_explorer import reveal_folder
        reveal_folder(self.builder.completed_build_folder(payload['buildId']))
        return {'opened': True}

    def house_selection(self) -> dict:
        if not self.houses or not self.house_placements:
            return {}
        from .house_runtime_compilation import build_inputs
        return build_inputs(self.houses, self.house_placements)

    def location_rows(self, overview, settings):
        # Real Estate may be the only Runtime domain. Every registered
        # placed Location Asset uses automatic FULL unless explicitly Off.
        if not any((item['count'] or item['protectedCount']) and
                   runtime_mode(settings, item['slug']) != 'off' for item in overview['items']):
            return []
        return build_rows(overview, self.registry, settings)

    def overview(self) -> dict:
        settings = self.read_settings()
        catalog = build_catalog(self.assets)
        published = {row['slug'] for row in catalog['items']}
        assets = self.assets.snapshot()['items']
        by_slug = {r['slug']: r for r in assets}
        revisions = self.registry.revisions.page(10)
        latest = revisions[0] if revisions else None
        report = self.registry.revisions.get(latest['id']) if latest else None
        rows = report['placements'] if report else []
        protected = report.get('protected', []) if report else []
        grouped = defaultdict(list)
        external_by_slug = defaultdict(list)
        for row in rows:
            grouped[row['slug']].append(row)
        for row in protected:
            # Each external Model remains outside the Deco placement list.
            # A shared Mesh ID without an unambiguous slug remains unassigned.
            external_by_slug[row.get('slug') or ''].append(row)
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
        for slug in sorted(set(by_slug) | set(grouped) | (set(external_by_slug) - {''})):
            asset = by_slug.get(slug)
            placements = grouped[slug]
            external = external_by_slug[slug]
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
            problem_rows = [r for r in placements if (
                not r.get('placementId') or r.get('duplicateId') is True
                or r.get('ambiguous') is True or r.get('hasModel') is not True
                or r.get('needsCollision') is True or r.get('needsPhysics') is True
                or r.get('needsRecapture') is True
                or r.get('issues'))]
            for name, count in issues.items():
                counts[name] += count
            mode = settings['modes'].get(slug, 'auto')
            structural_issues = [placement_shape_problem(r) for r in placements if placement_shape_problem(r)]
            painter_ready = all(r.get('runtimeCandidate') is True for r in external)
            eligible = bool(asset and (placements or external) and asset.get('status') == 'PUBLISHED' and
                asset.get('model_asset_id') and painter_ready and not problem_rows and not structural_issues)
            reason = ('Нет размещений' if not placements and not external else
                'Не опубликован FULL' if not asset or asset.get('status') != 'PUBLISHED' or not asset.get('model_asset_id') else
                'LandscapePainter: нужен новый Scan/Sync для Runtime' if not painter_ready else
                'Ошибки Place Registry' if problem_rows else
                structural_issues[0] if structural_issues else '')
            items.append({
                'distances': distance_profile(settings, slug) if asset else None,
                'streamingMode': mode, 'resolvedStreamingMode': runtime_mode(settings, slug),
                'streamingEligible': eligible, 'streamingReason': reason,
                'slug': slug, 'category': (asset or {}).get('category') or '',
                'count': len(placements), 'runtimePainterCount':sum(r.get('runtimeCandidate') is True for r in external), 'fullStatus': (asset or {}).get('status') or 'NOT_REGISTERED',
                'fullModelId': str((asset or {}).get('model_asset_id') or ''),
                'lod1Status': lod1.get('status') or 'NOT_REGISTERED',
                'lod1ModelId': str(lod1.get('modelAssetId') or '') if lod1_active else '',
                'lod2Status': lod2.get('status') or 'NOT_SUPPORTED',
                'lod2ModelId': str(lod2.get('modelAssetId') or '') if lod2_active else '',
                'indicator': 'red' if red else 'green' if lod2_active else 'yellow',
                'issues': issues,
                'protectedCount': len(external),
                'protectedOwners': [{
                    'kind': str(r.get('kind') or ''),
                    'path': str(r.get('path') or '')[:1200],
                    'authorSlug': str(r.get('authorSlug') or '')[:128],
                    'branchStrokeId': str(r.get('branchStrokeId') or '')[:128],
                    'reason': str(r.get('reason') or '')[:250],
                    'review': r.get('review') is True,
                } for r in external[:50]],
                'problemPlacements': [{
                    'path': str(r.get('path') or '')[:1200],
                    'placementId': str(r.get('placementId') or '')[:128],
                    'hasModel': r.get('hasModel') is True,
                    'issues': [str(message)[:250] for message in r.get('issues', [])[:12]],
                } for r in problem_rows[:50]],
                'recognizedByCatalog': slug in published,
            })
        warnings = report.get('warnings', []) if report else []
        house_summaries = []
        if self.houses and self.house_placements:
            placed_counts = Counter(r['houseSlug'] for r in self.house_placements.snapshot()['items'])
            for house in self.houses.list():
                runtime = house.get('runtimeProfile') or {}
                house_summaries.append({
                    'slug':house['slug'], 'count':placed_counts.get(house['slug'],0),
                    'mode':runtime.get('mode','off'),
                    'profile': {k:runtime.get(k) for k in ('mode','revision')},
                    'fullStatus': house.get('status','NOT_REGISTERED'),
                    'lod1Status': ('PUBLISHED' if house.get('meshParts') and all(
                        (house.get('partLod1') or {}).get(part,{}).get('status') == 'PUBLISHED'
                        for part in house['meshParts']) else 'PARTIAL'),
                    'partLod1': house.get('partLod1') or {},
                    'partStreaming': house.get('partStreaming') or {},
                    'parts': [{'name':part,
                        'appearance':(house.get('meshOptions') or {}).get(part,{}).get('appearanceMode','material'),
                        'color':(house.get('meshOptions') or {}).get(part,{}).get('visualColor','#FFFFFF')}
                        for part in house.get('meshParts',[])],
                    'ready':(house.get('runtimeReadiness') or {}).get('readyForCompilation',False),
                    'warnings':(house.get('runtimeReadiness') or {}).get('warnings',[]),
                })
        return {
            'schemaVersion': 2, 'domain': 'location_assets',
            'realEstate': {'items':house_summaries, 'selected':sum(x['mode']!='off' for x in house_summaries),
                           'placements':sum(x['count'] for x in house_summaries)},
            'settings': settings, 'settingsDigest': settings_digest(settings),
            'snapshot': None if not latest else {
                'revisionId': latest['id'], 'recordedUtc': latest['recorded_utc'],
                'placeId': latest['place_id'], 'fingerprint': latest['fingerprint'],
                'catalogDigest': latest['registry_digest'],
                'catalogMatches': catalog_matches, 'freshness': freshness,
                'verifiedUtc': int(self._verified[1]) if freshness == 'SCANNED_THIS_SESSION' else None,
                'warnings': warnings[:50],
                'total': latest['total'], 'issues': latest['issues'],
            },
            'summary': {'placements': len(rows), 'typesWithPlacements': sum(bool(x) for x in grouped.values()),
                        'protectedExternal': len(protected),
                        'protectedLandscape': sum(r.get('kind') in ('landscape_attachment','landscape_structure') for r in protected),
                        'protectedPackages': sum(r.get('kind') == 'unmanaged_package' for r in protected),
                        'unassignedExternal': len(external_by_slug.get('', [])),
                        'registeredTypes': len(by_slug), 'lod1Types': sum(
                            i['lod1Status'] == 'PUBLISHED' for i in items),
                        'missingId': counts['missingId'], 'duplicateId': counts['duplicateId'],
                        'ambiguous': counts['ambiguous'], 'noModel': counts['noModel'],
                        'collisionReview': counts['collisionReview'], 'truncated': counts['truncated'],
                        'scanWarnings': len(warnings)},
            'items': items, 'revisions': [
                {'id': r['id'], 'recordedUtc': r['recorded_utc'],
                 'placeId': r['place_id'], 'total': r['total']} for r in revisions],
            'build': {'enabled': False, 'canPreflight': freshness == 'SCANNED_THIS_SESSION',
                      'sourceFile': str(self.builder.source),
                      'reason': 'Save current Studio Place as XML to the sourceFile; run Preflight. Draft is never publish-ready.',
                      'sourcePlaceMutated': False},
            'scope': 'All scanned registered Location types default to FULL streaming. LandscapePainter author-owned roots require verified runtime evidence; unknown/unpublished Workspace objects are not treated as registered assets.',
        }
