"""Explicit Studio-only replacement of placed Location Asset instances.

The immutable published Location catalog is the allowlist. The service does not
write publication metadata, SQLite, or the Place. Studio owns its Undo history.
"""
from __future__ import annotations

from threading import RLock
import re
from .place_registry.catalog import build_catalog


class LocationInstanceManager:
    def __init__(self, assets, bridge):
        self._assets = assets
        self._bridge = bridge
        self._lock = RLock()

    def operate(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or set(payload) != {'phase', 'sourceSlug', 'targetSlug', 'scope', 'scanToken', 'anchorId'}:
            raise ValueError('Instance Manager requires phase, two slugs, scope, scanToken and anchorId')
        phase, source, target, scope, token = (payload[key] for key in
            ('phase', 'sourceSlug', 'targetSlug', 'scope', 'scanToken'))
        anchor_id = payload['anchorId']
        if not isinstance(anchor_id, str) or not (anchor_id == 'model' or
                re.fullmatch(r'mesh:[1-9][0-9]{0,6}', anchor_id)):
            raise ValueError('Choose a valid target Pivot')
        if phase == 'preview' and anchor_id != 'model':
            raise ValueError('Preview starts with target Model Pivot')
        if phase not in ('preview', 'replace') or scope not in ('selected', 'all'):
            raise ValueError('Unsupported Instance Manager operation')
        if not isinstance(source, str) or not isinstance(target, str) or source == target:
            raise ValueError('Choose two different published Location Assets')
        if phase == 'preview' and token != '':
            raise ValueError('Preview must start a new Studio scan')
        if phase == 'replace' and (not isinstance(token, str) or len(token) != 36):
            raise ValueError('Run Preview before Replace')
        with self._lock:
            catalog = build_catalog(self._assets)
            slugs = {item['slug'] for item in catalog['items']}
            if source not in slugs or target not in slugs:
                raise ValueError('Both assets must have published Location Models')
            published = {row['slug'] for row in self._assets.snapshot()['items']
                         if row.get('status') == 'PUBLISHED'}
            if target not in published:
                raise ValueError('Publish the target Location Asset before replacing instances')
            result = self._bridge(catalog=catalog, phase=phase, source_slug=source,
                                  target_slug=target, scope=scope, scan_token=token, anchor_id=anchor_id)
            if not isinstance(result, dict) or type(result.get('count')) is not int:
                raise ValueError('Invalid Instance Manager Studio response')
            return result
