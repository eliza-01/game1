"""Location Collision Studio Capture/Preview orchestration; no Place mutation."""
from __future__ import annotations

from threading import RLock

from services.location_collision_blueprint import validate, SLUG
from services.location_collision_identity import expected_versions


class LocationCollisionAuthoring:
    def __init__(self, location_assets, studio_bridge):
        self.assets = location_assets
        self.studio = studio_bridge
        self._lock = RLock()

    @staticmethod
    def _diff(before: dict | None, after: dict) -> dict:
        previous = {part['id']: part for part in (before or {}).get('parts', [])}
        latest = {part['id']: part for part in after['parts']}
        return {
            'added': sorted(latest.keys() - previous.keys()),
            'removed': sorted(previous.keys() - latest.keys()),
            'modified': sorted(key for key in previous.keys() & latest.keys()
                               if previous[key] != latest[key]),
        }

    def operate(self, slug: str, phase: str) -> dict:
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            raise ValueError('invalid Location Asset slug')
        if phase not in ('validate', 'capture', 'preview', 'clear-preview'):
            raise ValueError('unsupported Collision Studio phase')
        with self._lock:
            if self.assets.get(slug) is None:
                raise ValueError('unknown registered Location Asset')
            current = self.assets.collision_blueprint(slug)
            revision = current['revision'] if current else 0
            blueprint = current['blueprint'] if current else None
            if phase == 'preview' and not blueprint:
                raise ValueError('Capture a Collision Blueprint before Preview')
            if phase == 'preview':
                blueprint = validate(blueprint, slug=slug)
            # Preview and Capture must operate on the *published* selected asset,
            # not an arbitrary Model renamed to the target slug. Clear needs no selection.
            identity = expected_versions(self.assets, slug) if phase != 'clear-preview' else None
            report = self.studio(slug=slug, phase=phase, expected_revision=revision,
                                 blueprint=blueprint if phase == 'preview' else None,
                                 expected_versions=identity)
            if phase in ('validate', 'capture'):
                if not isinstance(report.get('blueprint'), dict):
                    raise ValueError('Studio did not provide a validated Collision Blueprint')
                proposed = validate(report['blueprint'], slug=slug)
                diff = self._diff(blueprint, proposed)
                if phase == 'capture':
                    # Optimistic revision guard: a concurrent HTTP/API edit must
                    # not be overwritten while Studio Capture was running.
                    saved = self.assets.save_collision_blueprint(slug, {
                        'expectedRevision': revision, 'blueprint': proposed})
                    return {'phase': phase, 'revision': saved['revision'],
                            'changed': saved['revision'] != revision,
                            'partCount': len(proposed['parts']), 'diff': diff}
                return {'phase': phase, 'revision': revision,
                        'partCount': len(proposed['parts']), 'diff': diff}
            return {'phase': phase, 'revision': revision,
                    'partCount': report.get('partCount', 0)}
