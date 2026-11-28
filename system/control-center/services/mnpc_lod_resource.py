"""One MNPC LOD authoring owner. No entity/Studio/Runtime mutation.

The FBX resource is revision-pinned; the texture is owned by AtlasRegistry.
A published Open Cloud Model is NOT a verified Roblox MeshPart ID.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from threading import RLock
import time

from sqlite_connection import connect as connect_sqlite
from opencloud_assets import get_operation, wait_for_operation
from . import mnpc_lod_geometry as geometry
from . import mnpc_lod_prepare as preparation
from .model_lod_common import (check_revision, distances_valid, inspect_fbx,
    preserve_source, publish_geometry, sha256, verified_source)

_SLUG = re.compile(r'[a-z0-9][a-z0-9_]{0,63}\Z')
DEFAULT_PROFILE = {'enabled': False, 'full': 100, 'hide': 200, 'hysteresis': 10}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _asset_id(value):
    return isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0


def _visual_identity(row):
    if not row or row.get('status') != 'PUBLISHED' or not _asset_id(str(row.get('model_asset_id') or '')):
        raise ValueError('FULL model and its textures must be published and current')
    atlas = row.get('atlas_binding')
    if atlas:
        textures = {'variantId': atlas['variant_id'], 'imageId': atlas['published_id'],
                    'sha256': atlas['source_sha256']}
    else:
        textures = sorted([{'slot': t['slot'], 'imageId': t['asset_id'], 'sha256': t['sha256']}
                           for t in row.get('textures', [])], key=lambda t: t['slot'])
    return {'modelId': str(row['model_asset_id']), 'modelSha256': row['model_sha256'],
            'pipeline': row.get('publication_pipeline') or '', 'textures': textures}


def validate_profile(profile):
    if (not isinstance(profile, dict) or set(profile) != set(DEFAULT_PROFILE) or
            type(profile['enabled']) is not bool or
            not distances_valid((profile['full'],), profile['hide'], profile['hysteresis'], minimum=1)):
        raise ValueError('MNPC distances: FULL < Unload, gap > 2 × hysteresis, integer studs, hysteresis 0–100')
    return dict(profile)


class MnpcLodResource:
    def __init__(self, root, monsters, npcs, equipment, weapons, atlases, *, animations=None):
        self.root = Path(root).resolve()
        self.stores = {'monster': monsters, 'npc': npcs}
        self.equipment = equipment
        self.weapons = weapons
        self.atlases = atlases
        self.animations = animations or {}
        self.db = self.root / '.control-center/game1.db'
        self._lock = RLock()
        self._init()

    def connect(self):
        return connect_sqlite(self.db)

    def _init(self):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mnpc_lod1'").fetchone():
                backup = self.db.parent / 'backups' / ('before_m633_mnpc_lod_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db')
                backup.parent.mkdir(parents=True, exist_ok=True)
                with connect_sqlite(backup) as target:
                    db.backup(target)
            db.executescript('''CREATE TABLE IF NOT EXISTS mnpc_lod1 (
                kind TEXT NOT NULL, slug TEXT NOT NULL, revision INTEGER NOT NULL,
                full_fingerprint TEXT NOT NULL, source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL, geometry_json TEXT NOT NULL,
                atlas_variant_id INTEGER NOT NULL, atlas_sha256 TEXT NOT NULL,
                image_id TEXT NOT NULL DEFAULT '', model_id TEXT NOT NULL DEFAULT '',
                model_operation TEXT NOT NULL DEFAULT '', model_moderation TEXT NOT NULL DEFAULT '',
                model_pending INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL,
                PRIMARY KEY(kind,slug));
                CREATE TABLE IF NOT EXISTS mnpc_lod1_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, slug TEXT NOT NULL,
                    revision INTEGER NOT NULL, event TEXT NOT NULL, snapshot_json TEXT NOT NULL,
                    recorded_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS mnpc_lod_settings (
                    id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, profile_json TEXT NOT NULL);
                INSERT OR IGNORE INTO mnpc_lod_settings VALUES (1,0,'{}');''')

    def _actor(self, kind, slug):
        if kind not in self.stores or not isinstance(slug, str) or not _SLUG.fullmatch(slug):
            raise ValueError('Invalid MNPC kind or slug')
        row = self.stores[kind].get(slug)
        if not row:
            raise ValueError('Unknown MNPC actor')
        return row

    def _full(self, kind, row, loadouts=None):
        identity = _visual_identity(row)
        # NPC weapons are part of the authored LOD variant, not separate LOD meshes.
        if kind == 'npc':
            loadout = (loadouts if loadouts is not None else self.equipment.snapshot()['loadouts']).get(row['slug'], {})
            identity['equipment'] = {}
            for hand in ('right', 'left'):
                slug = loadout.get(hand) or ''
                if slug:
                    weapon = self.weapons.get(slug)
                    identity['equipment'][hand] = {'slug': slug, 'weaponType': (weapon or {}).get('weapon_type'),
                                                   'visual': _visual_identity(weapon)}
                else:
                    identity['equipment'][hand] = None
        return _digest(identity), identity

    @staticmethod
    def _read(db, kind, slug):
        row = db.execute('SELECT * FROM mnpc_lod1 WHERE kind=? AND slug=?', (kind, slug)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _history(db, row, event):
        db.execute('INSERT INTO mnpc_lod1_history(kind,slug,revision,event,snapshot_json,recorded_at) VALUES(?,?,?,?,?,?)',
                   (row['kind'], row['slug'], row['revision'], event, json.dumps(row, sort_keys=True), time.time()))

    def _settings(self, db):
        row = db.execute('SELECT revision,profile_json FROM mnpc_lod_settings WHERE id=1').fetchone()
        data = json.loads(row['profile_json'])
        return {'revision': row['revision'], 'defaults': validate_profile(data.get('defaults', DEFAULT_PROFILE)),
                'overrides': {key: validate_profile(value) for key, value in data.get('overrides', {}).items()}}

    def _describe(self, kind, actor, row, settings, loadouts=None):
        key = kind + ':' + actor['slug']
        item = {'kind': kind, 'slug': actor['slug'], 'name': actor['name_en'],
                'fullStatus': actor['status'], 'fullModelId': str(actor.get('model_asset_id') or ''),
                'fullRevision': actor['revision'], 'profile': settings['overrides'].get(key, settings['defaults']),
                'inherits': key not in settings['overrides'], 'revision': 0, 'status': 'NOT_REGISTERED',
                'fullFingerprint': '', 'fullIdentity': None, 'sourcePath': '', 'sourceSha256': '',
                'geometry': None, 'modelAssetId': '', 'imageAssetId': '', 'atlasVariantId': None,
                'modelOperation': '', 'moderationState': '', 'reason': '', 'runtimeReady': False,
                'alignment': None, 'alignmentStatus': 'NOT_VERIFIED'}
        try:
            item['fullFingerprint'], item['fullIdentity'] = self._full(kind, actor, loadouts)
        except ValueError as exc:
            item['status'], item['reason'] = 'FULL_UNAVAILABLE', str(exc)
        if not row:
            return item
        item.update(revision=row['revision'], sourcePath=row['source_path'], sourceSha256=row['source_sha256'],
                    geometry=json.loads(row['geometry_json']), atlasVariantId=row['atlas_variant_id'],
                    modelAssetId=row['model_id'], imageAssetId=row['image_id'],
                    modelOperation=row['model_operation'], moderationState=row['model_moderation'])
        alignment = item['geometry'].pop('alignment', None)
        if row['model_pending']:
            item.update(status='MODEL_PENDING', reason='Open Cloud operation unresolved; resume existing operation, never upload twice')
            return item
        if not item['fullFingerprint'] or row['full_fingerprint'] != item['fullFingerprint']:
            item.update(status='FULL_CHANGED', reason='FULL visual or equipped weapon changed; stage a new LOD1 revision')
            return item
        path = (self.root / row['source_path']).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            item.update(status='SOURCE_MISSING', reason='Staged FBX is missing')
            return item
        if sha256(path) != row['source_sha256']:
            item.update(status='SOURCE_CHANGED', reason='Staged FBX bytes changed; restore the immutable source')
            return item
        atlas = self.atlases.get_variant(row['atlas_variant_id'])
        if (not atlas or atlas['retired'] or atlas['source_sha256'] != row['atlas_sha256'] or
                atlas.get('replacementPending') or (row['image_id'] and (not atlas['current'] or str(atlas['published_id']) != row['image_id']))):
            item.update(status='ATLAS_CHANGED', reason='Pinned atlas changed or retired; stage a new revision')
            return item
        atlas_path = (self.root / str(atlas.get('source_path') or '')).resolve()
        if (not atlas_path.is_relative_to(self.root) or not atlas_path.is_file() or
                sha256(atlas_path) != row['atlas_sha256']):
            item.update(status='ATLAS_SOURCE_CHANGED', reason='Pinned atlas source missing or changed; restore original bytes')
            return item
        recipe = (item.get('geometry') or {}).get('preparation') or {}
        if recipe.get('mode') == 'captured_idle' and kind in self.animations:
            try:
                self._check_captured_idle(item, actor['slug'], self.animations[kind])
            except (ValueError, KeyError, TypeError):
                item.update(status='IDLE_CHANGED', reason='Baked idle is stale; capture and bake a current LOD1')
                return item
        if row['model_id'] and row['image_id']:
            item.update(status='PUBLISHED', reason='Cloud Model + Image published; Roblox MeshPart import/alignment not verified')
            from .mnpc_lod_alignment import identity
            if isinstance(alignment, dict) and alignment.get('schemaVersion') == 1 and alignment.get('identity') == identity(item):
                item.update(alignment=alignment, alignmentStatus='GEOMETRY_VERIFIED',
                            reason='Published mesh geometry aligned; native texture/visual review and Runtime integration pending')
        elif row['image_id'] or atlas['current']:
            item.update(status='ATLAS_READY', reason='Image published; Model publication pending')
        else:
            item.update(status='STAGED', reason='Static FBX and atlas source staged')
        return item

    def overview(self):
        with self._lock:
            loadouts = self.equipment.snapshot()['loadouts']
            with self.connect() as db:
                settings = self._settings(db)
                rows = {(r['kind'],r['slug']): dict(r) for r in db.execute('SELECT * FROM mnpc_lod1')}
            items = [self._describe(kind, actor, rows.get((kind, actor['slug'])), settings, loadouts)
                     for kind, store in self.stores.items() for actor in store.list()]
            return {'schemaVersion': 1, 'settings': settings, 'items': items, 'runtimeEnabled': False}

    def describe(self, kind, slug):
        actor = self._actor(kind, slug)
        with self.connect() as db:
            return self._describe(kind, actor, self._read(db, kind, slug), self._settings(db))

    def history(self, kind, slug):
        self._actor(kind, slug)
        with self.connect() as db:
            return [{'event': r['event'], 'recordedAt': r['recorded_at'], 'revision': r['revision'],
                     'modelAssetId': (snapshot := json.loads(r['snapshot_json']))['model_id'],
                     'imageAssetId': snapshot['image_id'], 'operation': snapshot['model_operation'],
                     'fullFingerprint': snapshot['full_fingerprint'], 'sourceSha256': snapshot['source_sha256']}
                    for r in db.execute('SELECT * FROM mnpc_lod1_history WHERE kind=? AND slug=? ORDER BY id DESC LIMIT 50', (kind, slug))]

    def save_settings(self, payload):
        if not isinstance(payload, dict) or set(payload) != {'expectedRevision','kind','slug','profile'}:
            raise ValueError('Invalid MNPC settings request')
        kind, slug, profile = payload['kind'], payload['slug'], payload['profile']
        is_default = kind == '' and slug == ''
        if not is_default:
            self._actor(kind, slug)
        if is_default or profile is not None:
            profile = validate_profile(profile)
        with self._lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = self._settings(db)
            check_revision(payload['expectedRevision'], settings.pop('revision'), label='MNPC settings')
            if is_default:
                settings['defaults'] = profile
            elif profile is None:
                settings['overrides'].pop(kind + ':' + slug, None)
            else:
                settings['overrides'][kind + ':' + slug] = profile
            db.execute('UPDATE mnpc_lod_settings SET revision=revision+1,profile_json=? WHERE id=1', (json.dumps(settings, sort_keys=True),))
        return self.overview()

    def prepare(self, kind, slug, payload):
        preparation.validate_request(payload)
        with self._lock:
            current = self.describe(kind, slug)
            check_revision(payload['expectedRevision'], current['revision'])
            if current['status'] == 'MODEL_PENDING':
                raise ValueError('Resolve the existing Model publication before preparation')
            if not current['fullFingerprint'] or current['fullFingerprint'] != payload['fullFingerprint']:
                raise ValueError('FULL changed; refresh and review the current assembly')
            with tempfile.TemporaryDirectory(prefix='game1-mnpc-prepare-') as tmp:
                fbx, atlas, recipe, report, digest = preparation.prepare(self.root, slug, payload, Path(tmp))
                return self.stage(kind, slug, {
                    'sourcePath': str(fbx), 'texturePath': str(atlas),
                    'expectedRevision': payload['expectedRevision'], 'fullFingerprint': payload['fullFingerprint'],
                }, recipe=recipe, prepared_report=report, prepared_sha=digest)

    def stage(self, kind, slug, payload, *, recipe=None, prepared_report=None, prepared_sha=None):
        if not isinstance(payload, dict) or set(payload) != {'sourcePath','texturePath','expectedRevision','fullFingerprint'}:
            raise ValueError('Stage requires FBX, baked texture, LOD revision and reviewed FULL fingerprint')
        expected = payload['expectedRevision']
        with self._lock:
            current = self.describe(kind, slug)
            check_revision(expected, current['revision'])
            if current['status'] == 'MODEL_PENDING':
                raise ValueError('Resolve the existing Model publication before replacing this revision')
            fingerprint = current['fullFingerprint']
            if not fingerprint or payload['fullFingerprint'] != fingerprint:
                raise ValueError('FULL changed; refresh and prepare the current visual variant')
            source, digest = inspect_fbx(payload['sourcePath'], f'{slug}_lod1.fbx')
            texture, texture_sha, w, h, ext = geometry.texture_info(payload['texturePath'])
            # One immutable source directory; no overwriting FULL or prior LOD revisions.
            target = self.root / 'assets/source/mnpc-lod' / kind / slug / digest / f'{slug}_lod1.fbx'
            if target.is_file():
                if sha256(target) != digest:
                    raise ValueError('Stored immutable LOD FBX checksum mismatch')
            else:
                preserve_source(source, target, target.parent / '_unused_backup.fbx', digest)
            # Generator already round-tripped the actual output in Blender with
            # the same M633 inspector. Only accept its report for identical bytes.
            if prepared_report is not None:
                if prepared_sha != digest or recipe is None:
                    raise ValueError('Prepared FBX checksum changed')
                report = geometry.validate(prepared_report)
            else:
                report = geometry.inspect(self.root, target)
            if sha256(target) != digest:
                raise ValueError('LOD1 FBX changed during inspection')
            if recipe is not None:
                if report['triangles'] > recipe['targetTriangles']:
                    raise ValueError('Prepared LOD1 exceeds triangle target on FBX inspection')
                report = {**report, 'preparation': recipe}
            # Use the shared atlas catalog and its publication deduplication; no LOD texture uploader.
            # A content-addressed family name avoids implicitly replacing existing FULL atlases.
            with tempfile.TemporaryDirectory(prefix='game1-mnpc-atlas-') as tmp:
                canonical = Path(tmp) / f'mnpc_{kind}_{slug[:32]}_{texture_sha[:24]}_{w}x{h}_atlas{ext}'
                preserve_source(texture, canonical, canonical.parent / '_unused_backup', texture_sha)
                atlas = self.atlases.adopt_file(str(canonical))
            if atlas['source_sha256'] != texture_sha or atlas['retired'] or atlas.get('replacementPending'):
                raise ValueError('Shared atlas did not preserve the baked texture')
            if self._full(kind, self._actor(kind, slug))[0] != fingerprint:
                raise ValueError('FULL changed during staging; refresh')
            restored = self.describe(kind, slug)
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                old = self._read(db, kind, slug)
                check_revision(expected, old['revision'] if old else 0)
                if old and old['model_pending']:
                    raise ValueError('Model publication pending')
                if (old and old['source_sha256'] == digest and old['atlas_sha256'] == texture_sha and
                        old['atlas_variant_id'] == atlas['id'] and old['full_fingerprint'] == fingerprint and
                        restored['status'] in ('STAGED','ATLAS_READY','PUBLISHED') and
                        (recipe is None or (restored.get('geometry') or {}).get('preparation') == recipe)):
                    return restored
                db.execute('''INSERT INTO mnpc_lod1(kind,slug,revision,full_fingerprint,source_path,
                    source_sha256,geometry_json,atlas_variant_id,atlas_sha256,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,slug) DO UPDATE SET
                    revision=excluded.revision,full_fingerprint=excluded.full_fingerprint,
                    source_path=excluded.source_path,source_sha256=excluded.source_sha256,
                    geometry_json=excluded.geometry_json,atlas_variant_id=excluded.atlas_variant_id,
                    atlas_sha256=excluded.atlas_sha256,image_id='',model_id='',model_operation='',
                    model_moderation='',model_pending=0,updated_at=excluded.updated_at''',
                    (kind,slug,expected+1,fingerprint,target.relative_to(self.root).as_posix(),digest,
                     json.dumps(report),atlas['id'],texture_sha,time.time()))
                self._history(db, self._read(db,kind,slug), 'STAGED')
            return self.describe(kind, slug)

    def record_alignment(self, kind, slug, expected, result):
        """Store only a validated Studio result on the current immutable revision."""
        from .mnpc_lod_alignment import identity
        with self._lock:
            current = self.describe(kind,slug)
            check_revision(expected,current['revision'])
            if current['status'] != 'PUBLISHED' or result['identity'] != identity(current):
                raise ValueError('MNPC publication changed during alignment')
            if current['alignment'] == result:
                return
            report = {**current['geometry'], 'alignment': result}
            self._change(kind,slug,expected,'GEOMETRY_ALIGNED',geometry_json=json.dumps(report,allow_nan=False))

    def _change(self, kind, slug, expected, event, **values):
        # All field names are internal literals, not supplied by the HTTP client.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._read(db, kind, slug)
            check_revision(expected, row['revision'] if row else 0)
            if event == 'MODEL_INTENT' and (row['model_pending'] or row['model_id']):
                raise ValueError('Model publication already started; refresh')
            if event in ('MODEL_OPERATION','MODEL_PUBLISHED','MODEL_REJECTED') and not row['model_pending']:
                raise ValueError('Model publication state changed; refresh')
            if event == 'ATLAS_READY' and row['image_id'] and row['image_id'] != values['image_id']:
                raise ValueError('Pinned Image ID changed; refresh')
            db.execute('UPDATE mnpc_lod1 SET ' + ','.join(f'{key}=?' for key in values) + ',updated_at=? WHERE kind=? AND slug=?',
                       (*values.values(),time.time(),kind,slug))
            self._history(db, self._read(db,kind,slug), event)

    @staticmethod
    def _check_captured_idle(current, slug, animations):
        recipe = (current.get('geometry') or {}).get('preparation') or {}
        if recipe.get('mode') == 'captured_idle':
            from .mnpc_lod_capture import idle_identity
            if animations is None or idle_identity(animations, slug)[0] != recipe['idleFingerprint']:
                raise ValueError('Baked idle changed; capture and bake a current LOD1 before publication')

    def publish(self, kind, slug, expected, credentials, *, animations=None):
        with self._lock:
            animations = animations or self.animations.get(kind)
            current = self.describe(kind, slug)
            check_revision(expected, current['revision'])
            if current['status'] == 'IDLE_CHANGED':
                raise ValueError('Baked idle changed; capture and bake a current LOD1 before publication')
            if expected == 0:
                raise ValueError('Stage LOD1 first')
            if current['status'] == 'MODEL_PENDING':
                if not current['modelOperation']:
                    raise ValueError('Model upload intent has no confirmed operation ID; inspect Open Cloud before retrying')
                # Recover an already-created operation, even if FULL became stale meanwhile.
                api_key = str(credentials.get('apiKey') or '')
                operation = get_operation(current['modelOperation'], api_key=api_key)
                if operation.get('done') is True and operation.get('error'):
                    self._change(kind,slug,expected,'MODEL_REJECTED',model_pending=0)
                    raise ValueError('Roblox rejected the Model: ' + json.dumps(operation['error'], ensure_ascii=False))
                result = wait_for_operation(current['modelOperation'], api_key=api_key)
            elif current['status'] in ('STAGED','ATLAS_READY','PUBLISHED'):
                self._check_captured_idle(current, slug, animations)
                source = verified_source(self.root, current)
                with self.connect() as db:
                    row = self._read(db,kind,slug)
                if current['status'] == 'PUBLISHED':
                    return current
                if (not str(credentials.get('apiKey') or '').strip() or
                        not _asset_id(str(credentials.get('creatorId') or '')) or
                        str(credentials.get('creatorType') or '').lower() not in ('user','group')):
                    raise ValueError('Open Cloud credentials required to publish MNPC LOD1')
                atlas = self.atlases.ensure_published(row['atlas_variant_id'], credentials, 'game1 MNPC LOD1 atlas')
                image_id = str(atlas.get('published_id') or '')
                if not atlas['current'] or atlas['source_sha256'] != row['atlas_sha256'] or not _asset_id(image_id):
                    raise ValueError('Atlas publication changed; refusing Model upload')
                if row['image_id'] and row['image_id'] != image_id:
                    raise ValueError('Pinned Image ID changed; stage a new revision')
                if not row['image_id']:
                    self._change(kind,slug,expected,'ATLAS_READY',image_id=image_id)
                # Recheck after a potentially slow atlas/Blender step. No duplicate
                # Cloud model on ambiguous errors; intent is committed before POST.
                def before():
                    fresh = self.describe(kind,slug)
                    if fresh['status'] != 'ATLAS_READY' or fresh['imageAssetId'] != image_id:
                        raise ValueError('MNPC source changed during publication preparation')
                    self._check_captured_idle(fresh, slug, animations)
                    verified_source(self.root, fresh)
                    self._change(kind,slug,expected,'MODEL_INTENT',model_pending=1,model_operation='')

                def operation(path):
                    self._change(kind,slug,expected,'MODEL_OPERATION',model_operation=str(path))

                result = publish_geometry(self.root,source,f'mnpc_{kind}_{slug}',credentials,
                    description='game1 MNPC static LOD1',before_upload=before,on_operation=operation,
                    validate_staged=geometry.validate_staged)
            else:
                raise ValueError('Stage a current LOD1 revision before publication: ' + current['status'])
            model_id = str(result.asset_id)
            if not _asset_id(model_id):
                raise ValueError('Open Cloud returned invalid Model Asset ID')
            self._change(kind,slug,expected,'MODEL_PUBLISHED',model_id=model_id,model_pending=0,
                         model_operation=str(result.operation_path),model_moderation=result.moderation_state or '')
            return self.describe(kind,slug)
