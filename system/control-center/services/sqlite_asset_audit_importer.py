"""Idempotently project all existing SQLite publication histories into MySQL."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
import threading
import re


@dataclass(frozen=True)
class PublicationSpec:
    database: str
    table: str
    domain: str
    key_column: str
    asset_id_column: str
    asset_type: str
    slot_columns: tuple[str, ...] = ()
    sha_column: str = ''
    operation_column: str = ''
    revision_column: str = ''
    published_column: str = 'published_at'
    event_kind: str = 'publication'


SPECS = (
    PublicationSpec('game1.db', 'character_publications', 'character',
                    'character_id', 'asset_id', 'model',
                    sha_column='sha256', operation_column='operation_path',
                    revision_column='character_revision'),
    PublicationSpec('game1.db', 'animation_publications', 'character_animation',
                    'clip_id', 'asset_id', 'animation',
                    sha_column='sha256', operation_column='operation_path',
                    revision_column='clip_revision'),
    PublicationSpec('game1.db', 'weapon_publications', 'weapon',
                    'weapon_slug', 'asset_id', 'from_kind', ('kind', 'slot'),
                    'sha256', 'operation_path', 'weapon_revision'),
    PublicationSpec('game1.db', 'monster_publications', 'monster',
                    'monster_slug', 'asset_id', 'from_kind', ('kind', 'slot'),
                    'sha256', 'operation_path', 'monster_revision'),
    PublicationSpec('game1.db', 'monster_animation_publications', 'monster_animation',
                    'clip_id', 'asset_id', 'animation',
                    sha_column='sha256', operation_column='operation_path',
                    revision_column='clip_revision'),
    PublicationSpec('game1.db', 'location_asset_publications', 'location_asset',
                    'asset_slug', 'asset_id', 'from_kind', ('kind',),
                    'sha256', 'operation_path', 'revision'),
    PublicationSpec('game1.db', 'texture_atlas_publications', 'texture_atlas',
                    'variant_id', 'image_asset_id', 'image',
                    sha_column='sha256', operation_column='operation_path'),
    PublicationSpec('game1.db', 'texture_atlas_legacy_publications', 'texture_atlas_legacy',
                    'consumer_id', 'image_asset_id', 'image', ('consumer_type',),
                    'source_sha256', published_column='imported_at', event_kind='legacy_import'),
    PublicationSpec('game1.db', 'character_component_publications', 'character_component',
                    'component_id', 'asset_id', 'model', ('kind',),
                    operation_column='operation_path', revision_column='revision'),
    PublicationSpec('game1.db', 'character_model_assignments', 'character',
                    'target_character_id', 'asset_id', 'model', ('source_character_id',),
                    published_column='assigned_at', event_kind='assignment'),
    PublicationSpec('game1_npcs.db', 'monster_publications', 'npc',
                    'monster_slug', 'asset_id', 'from_kind', ('kind', 'slot'),
                    'sha256', 'operation_path', 'monster_revision'),
    PublicationSpec('game1_npcs.db', 'monster_animation_publications', 'npc_animation',
                    'clip_id', 'asset_id', 'animation',
                    sha_column='sha256', operation_column='operation_path',
                    revision_column='clip_revision'),
    PublicationSpec('game1_real_estate.db', 'real_estate_publications', 'real_estate',
                    'house_slug', 'asset_id', 'model', ('part',),
                    'sha256', 'operation'),
)


class SqliteAssetAuditImporter:
    """Read-only importer; never modifies source authoring databases."""

    def __init__(self, root: Path, repository):
        self.root = Path(root).resolve()
        self.repository = repository
        self._lock = threading.RLock()

    @staticmethod
    def _tables(connection) -> set[str]:
        return {str(row[0]) for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}

    @staticmethod
    def _asset_type(spec: PublicationSpec, row: dict) -> str:
        if spec.asset_type != 'from_kind':
            return spec.asset_type
        kind = str(row.get('kind') or '').lower()
        return 'model' if kind == 'model' else 'image'

    @staticmethod
    def _at_utc(value) -> str:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()

    @staticmethod
    def _operation_id(source_system: str, source_record: str) -> str:
        return sha256(f'{source_system}:{source_record}'.encode('utf-8')).hexdigest()[:32]

    def _events(self, spec: PublicationSpec) -> list[dict]:
        path = self.root / '.control-center' / spec.database
        if not path.is_file():
            return []
        with closing(sqlite3.connect(path)) as connection:
            connection.row_factory = sqlite3.Row
            if spec.table not in self._tables(connection):
                return []
            columns = {str(row[1]) for row in connection.execute(
                f'PRAGMA table_info("{spec.table}")')}
            required = {'id', spec.key_column, spec.asset_id_column, spec.published_column}
            if not required.issubset(columns):
                missing = ', '.join(sorted(required - columns))
                raise RuntimeError(f'{spec.database}/{spec.table} audit columns missing: {missing}')
            rows = [dict(row) for row in connection.execute(
                f'SELECT * FROM "{spec.table}" ORDER BY id')]
        previous_by_identity: dict[tuple[str, str, str], str] = {}
        events = []
        for row in rows:
            asset_id = str(row.get(spec.asset_id_column) or '')
            if not asset_id.isdigit():
                continue
            key = str(row.get(spec.key_column) or '')
            slot = ':'.join(str(row.get(column) or '') for column in spec.slot_columns)
            asset_type = self._asset_type(spec, row)
            identity = (key, slot, asset_type)
            previous = previous_by_identity.get(identity, '')
            previous_by_identity[identity] = asset_id
            source_system = f'sqlite:{spec.database}:{spec.table}'
            source_record = str(row['id'])
            revision = int(row.get(spec.revision_column) or 0) if spec.revision_column else 0
            metadata = {'revision': revision}
            if row.get('moderation_state') is not None:
                metadata['moderationState'] = str(row.get('moderation_state') or '')
            events.append({
                'operationId': self._operation_id(source_system, source_record),
                'atUtc': self._at_utc(row[spec.published_column]),
                'eventKind': spec.event_kind,
                'assetDomain': spec.domain,
                'assetKey': key,
                'assetSlot': slot,
                'assetType': asset_type,
                'sourceSystem': source_system,
                'sourceRecord': source_record,
                'sourceSha256': str(row.get(spec.sha_column) or '') if spec.sha_column else '',
                'operationPath': str(row.get(spec.operation_column) or '') if spec.operation_column else '',
                'bindingRevision': revision,
                'assetId': asset_id,
                'previousAssetId': previous,
                'metadata': metadata,
            })
        return events

    def sync_all(self) -> dict:
        with self._lock:
            try:
                self.repository.ensure_schema()
                scanned = 0
                sources = []
                for spec in SPECS:
                    events = self._events(spec)
                    if hasattr(self.repository, 'append_publications'):
                        self.repository.append_publications(events)
                    else:
                        for event in events:
                            self.repository.append_publication(event)
                    scanned += len(events)
                    sources.append({'database': spec.database, 'table': spec.table,
                                    'events': len(events)})
                return {'scanned': scanned, 'sources': sources}
            except (ValueError, RuntimeError):
                raise
            except Exception as error:
                raise RuntimeError(f'asset audit database unavailable: {error}') from error

    def page(self, *, domain: str = '', key: str = '', event_kind: str = '',
             limit: int = 200, before: int | None = None) -> dict:
        if domain and not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', domain):
            raise ValueError('invalid asset audit domain')
        if len(key) > 255 or any(ord(character) < 32 for character in key):
            raise ValueError('invalid asset audit key')
        if event_kind and not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', event_kind):
            raise ValueError('invalid asset audit event kind')
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('asset audit page limit must be between 1 and 500')
        if before is not None and (type(before) is not int or before < 1):
            raise ValueError('invalid asset audit cursor')
        self.sync_all()
        try:
            return self.repository.page_all(
                domain=domain, key=key, event_kind=event_kind,
                limit=limit, before=before)
        except (ValueError, RuntimeError):
            raise
        except Exception as error:
            raise RuntimeError(f'asset audit database unavailable: {error}') from error
