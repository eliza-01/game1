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
        if not isinstance(payload, dict) or not {'phase', 'sourceSlug', 'targetSlug', 'scope', 'scanToken', 'anchorId'} <= set(payload) or set(payload) - {'phase', 'sourceSlug', 'targetSlug', 'scope', 'scanToken', 'anchorId', 'inspectionToken', 'approveShear', 'focusIndex', 'focusPartId'}:
            raise ValueError('Instance Manager requires phase, two slugs, scope, scanToken and anchorId')
        phase, source, target, scope, token = (payload[key] for key in
            ('phase', 'sourceSlug', 'targetSlug', 'scope', 'scanToken'))
        anchor_id = payload['anchorId']
        if not isinstance(anchor_id, str) or not (anchor_id in ('model', 'geometry') or
                re.fullmatch(r'mesh:[1-9][0-9]{0,6}', anchor_id)):
            raise ValueError('Choose a valid target Pivot')
        if phase == 'preview' and anchor_id != 'model':
            raise ValueError('Preview starts with target Model Pivot')
        if phase not in ('preview', 'inspect', 'clear', 'focus', 'replace') or scope not in ('selected', 'all'):
            raise ValueError('Unsupported Instance Manager operation')
        if not isinstance(source, str) or not isinstance(target, str) or source == target:
            raise ValueError('Choose two different published Location Assets')
        if phase == 'preview' and token != '':
            raise ValueError('Preview must start a new Studio scan')
        if phase in ('inspect', 'clear', 'focus', 'replace') and (not isinstance(token, str) or len(token) != 36):
            raise ValueError('Run Preview before Replace')
        approval_token = payload.get('inspectionToken', '')
        approve_shear = payload.get('approveShear', False)
        if not isinstance(approval_token, str) or (approval_token and len(approval_token) != 36):
            raise ValueError('Invalid collision inspection token')
        if type(approve_shear) is not bool:
            raise ValueError('Collision approval must be explicit boolean')
        if approve_shear and phase != 'replace':
            raise ValueError('Oversized collision override belongs only to Replace')
        if approval_token and phase not in ('clear', 'focus', 'replace'):
            raise ValueError('Collision inspection token only belongs to inspected operations')
        focus_index = payload.get('focusIndex', 0)
        focus_part_id = payload.get('focusPartId', '')
        if phase == 'focus':
            if not approval_token or type(focus_index) is not int or not 1 <= focus_index <= 1000 \
                or not isinstance(focus_part_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', focus_part_id):
                raise ValueError('Focus requires a verified collision warning')
        elif focus_index != 0 or focus_part_id:
            raise ValueError('Focus fields are only permitted for collision warnings')
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
                                  target_slug=target, scope=scope, scan_token=token, anchor_id=anchor_id,
                                  inspection_token=approval_token, approve_shear=approve_shear,
                                  focus_index=focus_index, focus_part_id=focus_part_id)
            if not isinstance(result, dict) or type(result.get('count')) is not int:
                raise ValueError('Invalid Instance Manager Studio response')
            return result
