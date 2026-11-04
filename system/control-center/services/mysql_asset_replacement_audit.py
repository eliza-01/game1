"""MySQL 8.4 persistence for immutable asset replacement audit events."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import threading


@dataclass(frozen=True)
class MySqlAuditConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> 'MySqlAuditConfig':
        return cls(
            host=os.environ.get('GAME1_ASSET_AUDIT_HOST', '127.0.0.1'),
            port=int(os.environ.get('GAME1_ASSET_AUDIT_PORT', '43823')),
            database=os.environ.get('GAME1_ASSET_AUDIT_DATABASE', 'game1_asset_audit'),
            user=os.environ.get('GAME1_ASSET_AUDIT_USER', 'game1_audit'),
            password=os.environ.get('GAME1_ASSET_AUDIT_PASSWORD', 'Game1LocalAuditOnly'),
        )


class MySqlAssetReplacementAudit:
    """Normalized, append-only audit repository with lazy migrations."""

    def __init__(self, config: MySqlAuditConfig, migration_root: Path | None = None):
        self.config = config
        self.migration_root = migration_root or (
            Path(__file__).resolve().parents[1] / 'migrations' / 'asset_audit_mysql')
        self._schema_ready = False
        self._lock = threading.RLock()

    def _connect(self):
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as error:
            raise RuntimeError(
                'MySQL audit driver is missing; install system/control-center/requirements-host.txt'
            ) from error
        return pymysql.connect(
            host=self.config.host, port=self.config.port, user=self.config.user,
            password=self.config.password, database=self.config.database,
            charset='utf8mb4', autocommit=False, cursorclass=DictCursor,
            connect_timeout=3, read_timeout=10, write_timeout=10,
        )

    @staticmethod
    def _statements(source: str) -> list[str]:
        return [statement.strip() for statement in source.split(';') if statement.strip()]

    def ensure_schema(self) -> None:
        with self._lock:
            if self._schema_ready:
                return
            migrations = sorted(self.migration_root.glob('*.sql'))
            if not migrations:
                raise RuntimeError('MySQL asset audit migrations are missing')
            connection = self._connect()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS asset_audit_schema_migrations (
                            migration_name VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                            source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                            applied_at_utc DATETIME(6) NOT NULL,
                            PRIMARY KEY (migration_name)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                    """)
                    for path in migrations:
                        source = path.read_text(encoding='utf-8')
                        digest = sha256(source.encode('utf-8')).hexdigest()
                        cursor.execute(
                            'SELECT source_sha256 FROM asset_audit_schema_migrations '
                            'WHERE migration_name=%s', (path.name,))
                        applied = cursor.fetchone()
                        if applied:
                            if applied['source_sha256'] != digest:
                                raise RuntimeError(f'applied MySQL audit migration changed: {path.name}')
                            continue
                        for statement in self._statements(source):
                            cursor.execute(statement)
                        cursor.execute(
                            'INSERT INTO asset_audit_schema_migrations '
                            '(migration_name, source_sha256, applied_at_utc) VALUES (%s,%s,%s)',
                            (path.name, digest, datetime.now(timezone.utc).replace(tzinfo=None)))
                connection.commit()
                self._schema_ready = True
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _mysql_time(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    def _append_with_cursor(self, cursor, event: dict, changes: list[dict],
                            instances: list[dict]) -> bool:
        cursor.execute(
                    'SELECT audit_id, asset_domain, asset_key FROM asset_replacement_operations '
                    'WHERE operation_id=%s OR (source_system=%s AND source_record=%s) '
                    'LIMIT 1 FOR UPDATE',
                    (event['operationId'], event['sourceSystem'], event['sourceRecord']))
        existing = cursor.fetchone()
        if existing:
            if (existing['asset_domain'] != event['assetDomain']
                    or existing['asset_key'] != event['assetKey']):
                raise ValueError('audit operation identity belongs to a different asset')
            return False
        cursor.execute("""
            INSERT INTO asset_replacement_operations
            (operation_id, occurred_at_utc, event_kind, asset_domain, asset_key,
             asset_slot, asset_type, source_system, source_record, source_sha256,
             operation_path, metadata_json, binding_revision, matched_instances,
             changed_instances, changed_parts, pending_geometry)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            event['operationId'], self._mysql_time(event['atUtc']), event['eventKind'],
            event['assetDomain'], event['assetKey'], event.get('assetSlot', ''),
            event['assetType'], event['sourceSystem'], event['sourceRecord'],
            event.get('sourceSha256', ''), event.get('operationPath', ''),
            json.dumps(event.get('metadata', {}), ensure_ascii=False, separators=(',', ':')),
            event.get('bindingRevision', 0), event.get('matchedModels', 0),
            event.get('changedModels', 0), event.get('changedParts', 0),
            event.get('pendingGeometry', 0),
        ))
        audit_id = cursor.lastrowid
        for ordinal, change in enumerate(changes):
            cursor.execute("""
                INSERT INTO asset_replacement_changes
                (operation_audit_id, change_ordinal, change_kind, old_asset_id,
                 new_asset_id, changed_count) VALUES (%s,%s,%s,%s,%s,%s)
            """, (audit_id, ordinal, change['kind'], change['oldId'],
                  change['newId'], change['count']))
        for instance_ordinal, instance in enumerate(instances):
            cursor.execute("""
                INSERT INTO asset_replacement_instances
                (operation_audit_id, instance_ordinal, instance_id, studio_path)
                VALUES (%s,%s,%s,%s)
            """, (audit_id, instance_ordinal, instance['instanceId'], instance['studioPath']))
            for change_ordinal, change in enumerate(instance['changes']):
                cursor.execute("""
                    INSERT INTO asset_replacement_instance_changes
                    (operation_audit_id, instance_ordinal, change_ordinal, change_kind,
                     old_asset_id, new_asset_id, changed_count)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (audit_id, instance_ordinal, change_ordinal, change['kind'],
                      change['oldId'], change['newId'], change['count']))
        return True

    def _append_operation(self, event: dict, changes: list[dict],
                          instances: list[dict]) -> None:
        self.ensure_schema()
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                self._append_with_cursor(cursor, event, changes, instances)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def append(self, event: dict) -> None:
        """Compatibility adapter for detailed Location Asset Studio Sync."""
        operation = {
            **event,
            'eventKind': 'studio_sync',
            'assetDomain': 'location_asset',
            'assetKey': event['slug'],
            'assetSlot': '',
            'assetType': 'studio_reference',
            'sourceSystem': 'studio_bridge',
            'sourceRecord': event['operationId'],
            'sourceSha256': '',
            'operationPath': '',
            'metadata': {'schemaVersion': event.get('schemaVersion', 2)},
        }
        self._append_operation(operation, event['changes'], event.get('instances', []))

    def append_publication(self, event: dict) -> None:
        change = {
            'kind': 'asset_publication',
            'oldId': event.get('previousAssetId', ''),
            'newId': event['assetId'],
            'count': 1,
        }
        self._append_operation(event, [change], [])

    def append_publications(self, events: list[dict]) -> int:
        """Import one SQLite snapshot in a single transaction."""
        self.ensure_schema()
        connection = self._connect()
        inserted = 0
        try:
            with connection.cursor() as cursor:
                for event in events:
                    change = {
                        'kind': 'asset_publication',
                        'oldId': event.get('previousAssetId', ''),
                        'newId': event['assetId'],
                        'count': 1,
                    }
                    inserted += int(self._append_with_cursor(cursor, event, [change], []))
            connection.commit()
            return inserted
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _iso_utc(value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()

    def page_all(self, *, domain: str = '', key: str = '', event_kind: str = '',
                 limit: int, before: int | None = None) -> dict:
        self.ensure_schema()
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                filters = []
                params: list[object] = []
                if domain:
                    filters.append('asset_domain=%s')
                    params.append(domain)
                if key:
                    filters.append('asset_key=%s')
                    params.append(key)
                if event_kind:
                    filters.append('event_kind=%s')
                    params.append(event_kind)
                if before is not None:
                    filters.append('audit_id < %s')
                    params.append(before)
                where = ' AND '.join(filters) if filters else '1=1'
                cursor.execute(
                    f'SELECT * FROM asset_replacement_operations WHERE {where} '
                    'ORDER BY audit_id DESC LIMIT %s', (*params, limit + 1))
                rows = cursor.fetchall()
                has_more = len(rows) > limit
                rows = rows[:limit]
                events = []
                for row in rows:
                    audit_id = row['audit_id']
                    cursor.execute(
                        'SELECT change_kind, old_asset_id, new_asset_id, changed_count '
                        'FROM asset_replacement_changes WHERE operation_audit_id=%s '
                        'ORDER BY change_ordinal', (audit_id,))
                    changes = [{
                        'kind': item['change_kind'], 'oldId': item['old_asset_id'],
                        'newId': item['new_asset_id'], 'count': item['changed_count'],
                    } for item in cursor.fetchall()]
                    cursor.execute(
                        'SELECT instance_ordinal, instance_id, studio_path '
                        'FROM asset_replacement_instances WHERE operation_audit_id=%s '
                        'ORDER BY instance_ordinal', (audit_id,))
                    instances = []
                    for instance in cursor.fetchall():
                        cursor.execute(
                            'SELECT change_kind, old_asset_id, new_asset_id, changed_count '
                            'FROM asset_replacement_instance_changes '
                            'WHERE operation_audit_id=%s AND instance_ordinal=%s '
                            'ORDER BY change_ordinal', (audit_id, instance['instance_ordinal']))
                        instances.append({
                            'instanceId': instance['instance_id'],
                            'studioPath': instance['studio_path'],
                            'changes': [{
                                'kind': item['change_kind'], 'oldId': item['old_asset_id'],
                                'newId': item['new_asset_id'], 'count': item['changed_count'],
                            } for item in cursor.fetchall()],
                        })
                    events.append({
                        'schemaVersion': 2,
                        'atUtc': self._iso_utc(row['occurred_at_utc']),
                        'operationId': row['operation_id'],
                        'eventKind': row['event_kind'],
                        'assetDomain': row['asset_domain'],
                        'assetKey': row['asset_key'],
                        'assetSlot': row['asset_slot'],
                        'assetType': row['asset_type'],
                        'sourceSystem': row['source_system'],
                        'sourceRecord': row['source_record'],
                        'sourceSha256': row['source_sha256'],
                        'operationPath': row['operation_path'],
                        'metadata': json.loads(row['metadata_json']) if isinstance(row['metadata_json'], str) else row['metadata_json'],
                        'slug': row['asset_key'],
                        'bindingRevision': row['binding_revision'],
                        'matchedModels': row['matched_instances'],
                        'changedModels': row['changed_instances'],
                        'changedParts': row['changed_parts'],
                        'pendingGeometry': row['pending_geometry'],
                        'changes': changes, 'instances': instances,
                    })
                return {
                    'events': events,
                    'nextCursor': rows[-1]['audit_id'] if has_more and rows else None,
                }
        finally:
            connection.close()

    def page(self, slug: str, *, limit: int, before: int | None = None) -> dict:
        return self.page_all(domain='location_asset', key=slug, event_kind='studio_sync',
                             limit=limit, before=before)
