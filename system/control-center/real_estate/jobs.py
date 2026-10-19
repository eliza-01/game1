"""Nonblocking Real Estate publication jobs for the local authoring Host Agent.

The service owns threading, deduplication, progress and status. RealEstateStore
remains the only owner of source files, publication operations and asset IDs.
"""
from __future__ import annotations

from threading import Lock, Thread
from time import time
from uuid import uuid4


class RealEstatePublicationJobs:
    def __init__(self, store, *, max_concurrent: int = 2):
        self.store = store
        self.max_concurrent = max_concurrent
        self._lock = Lock()
        self._latest: dict[str, dict] = {}

    @staticmethod
    def _snapshot(job: dict | None) -> dict | None:
        if job is None:
            return None
        return {field: value for field, value in job.items() if field != '_credentials'}

    def get(self, slug: str) -> dict | None:
        with self._lock:
            return self._snapshot(self._latest.get(slug))

    def start(self, slug: str, credentials: dict, *, scope: str = 'all') -> dict:
        row = self.store.get(slug)
        if row is None:
            raise ValueError('The Real Estate entry is not registered')
        image_part = scope.removeprefix('image:') if scope.startswith('image:') else scope
        if scope not in ('all', 'model') and image_part not in row['meshParts'] and not (scope.startswith('model:') and scope[6:] in row['meshParts']):
            raise ValueError('Unsupported Real Estate publication scope for this house')
        with self._lock:
            existing = self._latest.get(slug)
            if existing and existing['status'] in ('queued', 'running'):
                return {**self._snapshot(existing), 'alreadyRunning': True}
            concurrent = sum(j['status'] in ('queued', 'running') for j in self._latest.values())
            if concurrent >= self.max_concurrent:
                raise ValueError('Two Real Estate publications are already running; wait for one to finish')
            job = {'id': uuid4().hex, 'slug': slug, 'scope': scope,
                   'status': 'queued', 'step': 'Waiting to start',
                   'error': '', 'startedAt': time(), 'finishedAt': None}
            self._latest[slug] = job
        Thread(target=self._run, args=(slug, job, credentials),
               name=f'real-estate-publish-{slug}', daemon=True).start()
        return self._snapshot(job)

    def _run(self, slug: str, job: dict, credentials: dict):
        def progress(step: str):
            with self._lock:
                job['step'] = step
        with self._lock:
            job['status'] = 'running'
            job['step'] = 'Preparing publication'
        try:
            self.store.publish(slug, credentials, scope=job['scope'], on_progress=progress)
        except Exception as exc:
            # The worker must not die silently, which formerly closed the HTTP
            # socket without a JSON error and hid the step that failed.
            with self._lock:
                job['status'] = 'failed'
                job['error'] = f'{type(exc).__name__}: {exc}'
                job['finishedAt'] = time()
        else:
            with self._lock:
                job['status'] = 'succeeded'
                job['step'] = 'All requested resources are current'
                job['finishedAt'] = time()
