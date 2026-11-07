"""Durable Location Asset Studio replacement history.

The JSONL file is a local write-ahead log and migration source. MySQL 8.4 is
the queryable source of truth. No FBX, PNG or Place bytes are stored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import threading

from services.mysql_asset_replacement_audit import (
    MySqlAssetReplacementAudit, MySqlAuditConfig,
)

SLUG = re.compile(r'^[a-z0-9][a-z0-9_]{0,63}$')
ID = re.compile(r'^[0-9]{0,20}$')
ALPHA_MODE = re.compile(r'^(?:missing|Overlay|Transparency|TintMask|Opaque)$')
INSTANCE_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
OPERATION_ID = re.compile(r'^[0-9a-f]{32}$')


class LocationAssetSyncHistory:
    def __init__(self, root: Path, database=None):
        self.path = Path(root) / '.control-center' / 'location-asset-studio-sync-history.jsonl'
        self.database = database or MySqlAssetReplacementAudit(MySqlAuditConfig.from_environment())
        self._lock = threading.RLock()
        self._legacy_imported = False

    @staticmethod
    def _validate_changes(changes: object, *, allow_empty: bool = True) -> list[dict]:
        if not isinstance(changes, list) or len(changes) > 32 or (not allow_empty and not changes):
            raise ValueError('invalid Studio ID change history size')
        validated = []
        for item in changes:
            if not isinstance(item, dict) or item.get('kind') not in (
                    'atlas', 'model_reference', 'model', 'alpha'):
                raise ValueError('invalid Studio ID change history type')
            kind = item['kind']
            old = str(item.get('oldId', ''))
            new = str(item.get('newId', ''))
            if kind == 'alpha':
                # Protocol 9 originally serialized EnumItems with tostring().
                # Normalize that installed-plugin form at the boundary so the
                # Host Agent fix is effective before Studio is restarted.
                prefix = 'Enum.AlphaMode.'
                if old.startswith(prefix):
                    old = old[len(prefix):]
                if new.startswith(prefix):
                    new = new[len(prefix):]
            count = item.get('count')
            values_valid = (ALPHA_MODE.fullmatch(old) is not None
                            and ALPHA_MODE.fullmatch(new) is not None
                            and new != 'missing') if kind == 'alpha' else (
                                ID.fullmatch(old) is not None
                                and ID.fullmatch(new) is not None and bool(new))
            if (not values_valid or type(count) is not int or not 0 < count <= 100000):
                raise ValueError('invalid Studio ID change history entry')
            validated.append({'kind': kind, 'oldId': old, 'newId': new, 'count': count})
        return validated

    @classmethod
    def _validate_instances(cls, instances: object) -> list[dict]:
        if instances is None:  # Schema 1 JSONL events predate per-instance audit.
            return []
        if not isinstance(instances, list) or len(instances) > 10000:
            raise ValueError('invalid Studio instance history size')
        validated = []
        seen = set()
        for item in instances:
            if not isinstance(item, dict):
                raise ValueError('invalid Studio instance history entry')
            instance_id = str(item.get('instanceId') or '')
            studio_path = str(item.get('studioPath') or '')
            if (not INSTANCE_ID.fullmatch(instance_id) or instance_id in seen
                    or not studio_path or len(studio_path) > 1024):
                raise ValueError('invalid Studio instance history identity')
            seen.add(instance_id)
            meshes = {}
            for key in ('meshIdsBefore','meshIdsAfter'):
                entries = item.get(key, [])
                if not isinstance(entries, list) or len(entries)>4096:
                    raise ValueError('invalid Mesh ID history entries')
                for entry in entries:
                    if (not isinstance(entry,dict) or not re.fullmatch(r'[1-9][0-9]{0,19}',str(entry.get('meshId') or ''))
                        or type(entry.get('count')) is not int or not 1 <= entry['count'] <= 4096):
                        raise ValueError('invalid Mesh ID history ID/count')
                meshes[key] = entries
            validated.append({
                'instanceId': instance_id,
                'studioPath': studio_path,
                'changes': cls._validate_changes(item.get('changes'), allow_empty=False),
                **meshes,
            })
        return validated

    @classmethod
    def _event(cls, *, slug: str, binding_revision: int, studio: dict,
               at_utc: str | None = None) -> dict:
        if not SLUG.fullmatch(slug) or type(binding_revision) is not int or binding_revision < 1:
            raise ValueError('invalid scoped Studio history identity')
        if not isinstance(studio, dict):
            raise ValueError('invalid Studio sync outcome')
        operation_id = str(studio.get('operationId') or '')
        if not OPERATION_ID.fullmatch(operation_id):
            raise ValueError('missing Studio operation identity')
        changes = cls._validate_changes(studio.get('changes'))
        instances = cls._validate_instances(studio.get('instances'))
        changed_models = int(studio['models'])
        if instances and len(instances) != changed_models:
            raise ValueError('Studio instance history count mismatch')
        return {
            'schemaVersion': 2,
            'atUtc': at_utc or datetime.now(timezone.utc).isoformat(),
            'operationId': operation_id,
            'slug': slug,
            'bindingRevision': binding_revision,
            'matchedModels': int(studio['matchedModels']),
            'changedModels': changed_models,
            'changedParts': int(studio['parts']),
            'pendingGeometry': int(studio['pendingGeometry']),
            'changes': changes,
            'instances': instances,
        }

    def _write_ahead(self, event: dict) -> None:
        encoded = (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        if len(encoded) > 2 * 1024 * 1024:
            raise ValueError('Studio ID history event exceeds limit')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('ab') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

    def _import_legacy(self) -> None:
        if self._legacy_imported:
            return
        try:
            self.database.ensure_schema()
            if self.path.is_file():
                with self.path.open('r', encoding='utf-8') as stream:
                    for line in stream:
                        if not line.strip():
                            continue
                        raw = json.loads(line)
                        event = self._event(
                            slug=str(raw.get('slug') or ''),
                            binding_revision=int(raw.get('bindingRevision') or 0),
                            studio={
                                'operationId': raw.get('operationId'),
                                'models': raw.get('changedModels'),
                                'parts': raw.get('changedParts'),
                                'matchedModels': raw.get('matchedModels'),
                                'pendingGeometry': raw.get('pendingGeometry'),
                                'changes': raw.get('changes'),
                                'instances': raw.get('instances'),
                            },
                            at_utc=str(raw.get('atUtc') or ''),
                        )
                        self.database.append(event)
        except (ValueError, RuntimeError):
            raise
        except Exception as error:
            raise RuntimeError(f'asset audit database unavailable: {error}') from error
        self._legacy_imported = True

    def prepare(self) -> None:
        with self._lock:
            self._import_legacy()

    def append(self, *, slug: str, binding_revision: int, studio: dict) -> dict:
        event = self._event(slug=slug, binding_revision=binding_revision, studio=studio)
        with self._lock:
            # WAL first: if MySQL is unavailable, evidence of the Studio-side
            # mutation survives and is imported idempotently on recovery.
            self._write_ahead(event)
            try:
                self._import_legacy()
                self.database.append(event)
            except Exception:
                # A later request must retry every WAL record, including the
                # operation whose MySQL transaction just failed.
                self._legacy_imported = False
                raise
        return event

    def page(self, slug: str, *, limit: int = 200, before: int | None = None) -> dict:
        if not SLUG.fullmatch(slug):
            raise ValueError('invalid Location Asset slug')
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('history page limit must be between 1 and 500')
        if before is not None and (type(before) is not int or before < 1):
            raise ValueError('invalid history cursor')
        with self._lock:
            try:
                self._import_legacy()
                return self.database.page(slug, limit=limit, before=before)
            except (ValueError, RuntimeError):
                raise
            except Exception as error:
                raise RuntimeError(f'asset audit database unavailable: {error}') from error

    def list(self, slug: str) -> list[dict]:
        events = []
        cursor = None
        while True:
            page = self.page(slug, limit=500, before=cursor)
            events.extend(page['events'])
            cursor = page['nextCursor']
            if cursor is None:
                return events
