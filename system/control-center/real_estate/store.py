"""Real Estate registry, canonical source preservation and Open Cloud publishing.

An Estate owns one published Model Asset per authored mesh and its image source.
This authoring store does not implement property ownership or runtime placement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from opencloud_assets import create_model_asset, create_image_asset, wait_for_operation
from sqlite_connection import connect
from .contracts import identity, parse_name, prices, present_parts, validate_analysis, warnings_for_analysis
from .textures import available_textures, resolve_texture
from .fbx import inspect, prepare_publication
from .publication_textures import prepare_texture, published_format


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError('registered source path escapes the project root')
    return path


class RealEstateStore:
    def __init__(self, root: Path, *, location_assets=None):
        self.root = root.resolve()
        self.location_assets = location_assets
        self.db = self.root / '.control-center' / 'game1_real_estate.db'
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS real_estate (
                slug TEXT PRIMARY KEY, house_type TEXT NOT NULL, house_level INTEGER NOT NULL,
                variant TEXT NOT NULL, purchase_price INTEGER NOT NULL DEFAULT 1,
                min_level INTEGER NOT NULL DEFAULT 1, sale_price INTEGER NOT NULL DEFAULT 1,
                model_path TEXT NOT NULL, model_sha256 TEXT NOT NULL, skeleton_json TEXT NOT NULL,
                textures_json TEXT NOT NULL, model_asset_id TEXT NOT NULL DEFAULT '',
                model_published_hash TEXT NOT NULL DEFAULT '', model_moderation TEXT NOT NULL DEFAULT '',
                revision INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL, updated_at REAL NOT NULL
            )''')
            db.execute('''CREATE TABLE IF NOT EXISTS real_estate_publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT, house_slug TEXT NOT NULL,
                part TEXT NOT NULL, asset_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                operation TEXT NOT NULL, published_at REAL NOT NULL
            )''')
            columns = {column[1] for column in db.execute('PRAGMA table_info(real_estate)')}
            if 'model_rigs_json' not in columns:
                db.execute("ALTER TABLE real_estate ADD COLUMN model_rigs_json TEXT NOT NULL DEFAULT '{}'")
            # M107 v2: old model_published_hash stored a bundle fingerprint of
            # FBX + both texture files. Migrate ONCE to the model-only hash.
            # An old fingerprint cannot reveal whether an earlier unpublished
            # FBX replacement occurred: baseline the currently registered FBX
            # and let all subsequent replacements be tracked exactly.
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version < 2:
                db.execute("UPDATE real_estate SET model_published_hash=model_sha256 "
                           "WHERE model_asset_id != '' AND model_published_hash != ''")
                db.execute('PRAGMA user_version = 2')
        self.export()

    def connect(self):
        return connect(self.db)

    def _raw_rows(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM real_estate ORDER BY slug')]

    def texture_references(self, raw_rows=None) -> list[dict]:
        """Published texture owners. This is shared authoring data, not copied Image IDs."""
        raw_rows = self._raw_rows() if raw_rows is None else raw_rows
        choices = []
        if self.location_assets is not None:
            for row in self.location_assets.list():
                if not row.get('texture_asset_id') or not row.get('texture_path'):
                    continue
                if str(row.get('texture_published_sha256') or '') != str(row.get('texture_sha256') or ''):
                    continue
                # Location Store resolves shared assets to their canonical owner.
                choices.append({'reference': 'location:' + row['slug'],
                    'label': f"{row.get('name_en') or row['slug']} · {row['slug']}",
                    'group': 'location', 'category': str(row.get('category') or 'other'),
                    'categoryLabel': str(row.get('category_label') or row.get('category') or 'Other'),
                    'path': row['texture_path'], 'sha256': row['texture_sha256'],
                    'assetId': str(row['texture_asset_id'])})
        for row in raw_rows:
            active = present_parts(json.loads(row['skeleton_json']))
            for part, data in json.loads(row['textures_json']).items():
                if part not in active or data.get('reuseReference') or not data.get('assetId') or not data.get('path'):
                    continue
                if data.get('publishedSha256') != data.get('sha256'):
                    continue
                if data.get('publicationFormat', 'source') != published_format(Path(data['path'])):
                    continue
                choices.append({'reference': f"estate:{row['slug']}:{part}",
                    'label': f"{row['slug']} / {part}",
                    'group': 'estate', 'category': '', 'categoryLabel': '',
                    'path': data['path'], 'sha256': data['sha256'],
                    'assetId': str(data['assetId'])})
        return choices

    def list(self):
        rows = self._raw_rows()
        references = {option['reference']: option for option in self.texture_references(rows)}
        result = []
        for row in rows:
            row['skeleton'] = json.loads(row.pop('skeleton_json'))
            row['rigWarnings'] = warnings_for_analysis(row['skeleton'])
            active = present_parts(row['skeleton'])
            row['meshParts'] = list(active)
            # Legacy records may still store door assets after the FBX is
            # replaced with a doorless house; they are publication history,
            # not active resources for the current template.
            row['textures'] = {part: data for part, data in
                json.loads(row.pop('textures_json')).items() if part in active}
            row['rigAssets'] = {part: data for part, data in
                json.loads(row.pop('model_rigs_json') or '{}').items() if part in active}
            current = {'model': all(
                row['rigAssets'].get(part, {}).get('assetId') and
                row['rigAssets'][part].get('publishedSha256') == row['model_sha256']
                for part in active)}
            for part in active:
                texture = row['textures'][part]
                reference = texture.get('reuseReference')
                if reference:
                    if reference == 'mesh:house' and part != 'house':
                        # Intra-house dependency: the atlas may be a local file,
                        # selected BEFORE either resource is registered or uploaded.
                        # Resolve against the effective house texture on each read,
                        # never copy an Image Asset ID into the stored door record.
                        owner = row['textures']['house']
                        if owner.get('path'):
                            row['textures'][part] = {**texture, **{
                                key: owner.get(key, '') for key in
                                ('path', 'sha256', 'assetId', 'publishedSha256', 'publicationFormat')}}
                        current[part] = bool(current['house'])
                    else:
                        owner = references.get(reference)
                        if owner:
                            row['textures'][part] = {**texture, **{
                                'path':owner['path'], 'sha256':owner['sha256'],
                                'assetId':owner['assetId'], 'publishedSha256':owner['sha256'],
                                'publicationFormat':published_format(Path(owner['path']))}}
                        current[part] = owner is not None
                else:
                    current[part] = bool(texture.get('assetId') and
                        texture.get('publishedSha256') == texture['sha256'] and
                        texture.get('publicationFormat', 'source') == published_format(Path(texture['path'])))
            row['publicationCurrent'] = current
            row['status'] = ('PUBLISHED' if all(current.values()) else
                             'LOCAL_ONLY' if not row['model_asset_id'] and
                             not any(row['textures'][part].get('assetId') for part in active)
                             else 'UPDATE_AVAILABLE')
            result.append(row)
        return result

    def get(self, slug: str):
        return next((item for item in self.list() if item['slug'] == slug), None)

    def inspect(self, source_path: str) -> dict:
        source = Path(str(source_path or '')).expanduser().resolve()
        defaults = parse_name(source.stem + '.fbx')
        analysis = inspect(self.root, source)
        return {**defaults, 'sourcePath': str(source), 'analysis': analysis,
                'warnings': warnings_for_analysis(analysis),
                'textures': available_textures(source.parent)}

    def register(self, payload: dict):
        value = identity(payload)
        value.update(prices(payload))
        slug = value['slug']
        existing_slug = str(payload.get('existingSlug') or '').strip().lower()
        if existing_slug and existing_slug != slug:
            raise ValueError('changing identity of a registered house requires a new registration')
        existing = self.get(existing_slug or slug)
        if self.get(slug) and not existing_slug:
            raise ValueError('house already registered; select it to edit')
        raw_source = str(payload.get('sourcePath') or '').strip()
        if not raw_source and not existing:
            raise ValueError('choose a Real Estate FBX')
        source = Path(raw_source).expanduser().resolve() if raw_source else _source(self.root, existing['model_path'])
        if not source.is_file() or source.suffix.lower() != '.fbx':
            raise ValueError('invalid Real Estate FBX')
        analysis = inspect(self.root, source) if raw_source else existing['skeleton']
        if raw_source:
            validate_analysis(analysis)
            warnings = warnings_for_analysis(analysis)
            if warnings and payload.get('acceptWarnings') is not True:
                raise ValueError('This FBX has optional rig warnings. Review them and confirm before registering the house.')
        selections = payload.get('textures')
        references = payload.get('textureReferences') or {}
        if not isinstance(selections, dict) or not isinstance(references, dict):
            raise ValueError('choose a file or published reusable texture for each present mesh')
        active = present_parts(analysis)
        catalog = {option['reference']:option for option in self.texture_references()}
        chosen_refs = {part: str(references.get(part) or '').strip() for part in active}
        for part, reference in chosen_refs.items():
            if reference == 'mesh:house':
                if part == 'house':
                    raise ValueError('The house mesh cannot reuse its own atlas')
                continue  # Owner is the current house, not a published catalog entry.
            if reference and (reference not in catalog or reference == f'estate:{slug}:{part}'):
                raise ValueError(f'{part}: unknown or unpublished reusable texture {reference}')
        texture_sources = {
            part: (resolve_texture(self.root, selections.get(part), part=part)
                   if not chosen_refs[part] else None)
            for part in active
        }
        canonical = self.root / 'assets' / 'source' / 'real-estate' / slug
        destination_model = canonical / 'model' / f'{slug}.fbx'
        destination_textures = {
            part: canonical / 'textures' / f'{part}{path.suffix.lower()}'
            for part, path in texture_sources.items() if path is not None
        }
        model_hash = _sha(source)
        texture_hashes = {part: _sha(path) for part, path in texture_sources.items() if path is not None}
        # Prevent overwriting canonical source with a different mesh hierarchy silently.
        source_change = not existing or existing['model_sha256'] != model_hash
        now = time.time()
        canonical.mkdir(parents=True, exist_ok=True)
        destination_model.parent.mkdir(parents=True, exist_ok=True)
        if source_change:
            if source != destination_model:
                shutil.copy2(source, destination_model)
        texture_rows = {}
        for part in active:
            old = (existing or {}).get('textures', {}).get(part, {})
            reference = chosen_refs[part]
            if reference:
                # Record the shared identity, not a duplicate upload. Effective
                # Image Asset IDs are resolved from the owner on every read.
                texture_rows[part] = {'reuseReference': reference, 'path':'',
                    'sha256':'', 'assetId':'', 'publishedSha256':'', 'publicationFormat':''}
                continue
            target = destination_textures[part]
            target.parent.mkdir(parents=True, exist_ok=True)
            if texture_sources[part] != target:
                shutil.copy2(texture_sources[part], target)
            texture_rows[part] = {'path': str(target.relative_to(self.root)).replace('\\', '/'),
                'sha256': texture_hashes[part],
                'reuseReference':'',
                # Preserve old public Asset ID until the replacement upload
                # succeeds. The hash/format mismatch marks it as pending.
                'assetId': old.get('assetId', '') if not old.get('reuseReference') else '',
                'publishedSha256': old.get('publishedSha256', '') if not old.get('reuseReference') else '',
                'publicationFormat': old.get('publicationFormat', '') if not old.get('reuseReference') else ''}
        model_rel = str(destination_model.relative_to(self.root)).replace('\\', '/')
        row = (slug, value['houseType'], value['level'], value['variant'],
            value['purchasePrice'], value['minLevel'], value['salePrice'], model_rel, model_hash,
            json.dumps(analysis, ensure_ascii=False), json.dumps(texture_rows, ensure_ascii=False),
            existing['model_asset_id'] if existing else '',
            existing['model_published_hash'] if existing else '',
            existing['model_moderation'] if existing else '',
            int(existing['revision']) + 1 if existing else 1,
            existing['created_at'] if existing else now, now)
        with self.connect() as db:
            db.execute('''INSERT INTO real_estate (
                slug,house_type,house_level,variant,purchase_price,min_level,sale_price,
                model_path,model_sha256,skeleton_json,textures_json,model_asset_id,
                model_published_hash,model_moderation,revision,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(slug) DO UPDATE SET
                house_type=excluded.house_type,house_level=excluded.house_level,variant=excluded.variant,
                purchase_price=excluded.purchase_price,min_level=excluded.min_level,
                sale_price=excluded.sale_price,model_path=excluded.model_path,
                model_sha256=excluded.model_sha256,skeleton_json=excluded.skeleton_json,
                textures_json=excluded.textures_json,model_asset_id=excluded.model_asset_id,
                model_published_hash=excluded.model_published_hash,model_moderation=excluded.model_moderation,
                revision=excluded.revision,updated_at=excluded.updated_at''', row)
        self.export()
        return self.get(slug)

    def publish(self, slug: str, credentials: dict, *, scope: str = 'all', on_progress=None):
        """Create new Asset IDs for only the requested changed resources.

        Model and both Image assets have independent version fingerprints.
        No Roblox asset is updated in place. Failed uploads leave previously
        published IDs and their hashes intact, and successful operations are
        recorded immediately so a retry never republishes completed parts.
        """
        # Use image:<mesh> for names that happen to equal reserved scopes.
        # Keep bare house/door names for older M108/M109 callers.
        if not isinstance(scope, str):
            raise ValueError('publication scope must be a string')
        def progress(message):
            if on_progress is not None:
                on_progress(message)
        row = self.get(slug)
        if not row:
            raise ValueError('unknown registered house')
        active = tuple(row['meshParts'])
        image_part = (scope[len('image:'):] if scope.startswith('image:') else
                      scope if scope not in ('all', 'model') else None)
        # Explicit recovery for a Roblox Model Asset whose bones were culled on
        # import. The existing source FBX/hash stays canonical; only one rig is
        # re-exported and assigned a fresh Model Asset ID after upload succeeds.
        force_model_part = scope[len('model:'):] if scope.startswith('model:') else None
        if force_model_part is not None:
            if force_model_part not in active:
                raise ValueError(f'Invalid publication scope: {force_model_part} mesh is absent from this house')
        elif scope not in ('all', 'model') and image_part not in active:
            raise ValueError(f'Invalid publication scope: {image_part} mesh is absent from this house')
        description = str(credentials.get('description') or f'Game1 Real Estate {slug}')
        common = dict(display_name=slug, description=description,
                      creator_type=credentials['creatorType'], creator_id=credentials['creatorId'],
                      api_key=credentials['apiKey'])
        for part in active:
            reference = row['textures'][part].get('reuseReference')
            if reference == 'mesh:house':
                # 'all' publishes house before door. 'model' only needs a
                # locally available texture for Blender's rig export.
                if image_part == part and not row['publicationCurrent']['house']:
                    raise ValueError('Publish the house image first; this mesh reuses its atlas')
                continue
            if reference and not row['publicationCurrent'][part]:
                raise ValueError(f'{part} reused texture owner must publish first')
        if (scope in ('all', 'model') and not row['publicationCurrent']['model']) or force_model_part:
            progress('Preparing ' + ' and '.join(part + ' rig' for part in active) + ' in Blender')
            with tempfile.TemporaryDirectory(prefix='game1-house-model-') as temp:
                staging = Path(temp)
                # Each skeleton is published as its own Roblox Model Asset;
                # otherwise Roblox collapses both rigs under one RootPart.
                images = {
                    part: prepare_texture(self.root, part, _source(self.root, data['path']), staging)
                    for part, data in row['textures'].items()
                }
                rigs = staging / 'rigs'
                prepare_publication(self.root, _source(self.root, row['model_path']), rigs,
                    row['skeleton'], {part: str(path) for part, path in images.items()})
                for part in active:
                    if force_model_part is not None and part != force_model_part:
                        continue
                    row = self.get(slug)
                    saved = row['rigAssets'].get(part, {})
                    if force_model_part is None and saved.get('assetId') and saved.get('publishedSha256') == row['model_sha256']:
                        continue  # Retry after partial success must not duplicate assets.
                    kind = 'model:'+part
                    progress(f'Publishing {part} rig · Roblox Open Cloud')
                    pending = self._pending_publication(slug, kind, row['model_sha256'])
                    if pending:
                        operation = pending['operation']
                        pending_id = pending['id']
                    else:
                        operation = create_model_asset(rigs / f'{part}.fbx',
                            **{**common, 'display_name':f'{slug} {part}'})
                        pending_id = self._remember_operation(slug, kind, row['model_sha256'], operation)
                    progress(f'Waiting for Roblox to process {part} rig')
                    result = wait_for_operation(operation, api_key=credentials['apiKey'])
                    model_rigs = row['rigAssets']
                    model_rigs[part] = {'assetId':str(result.asset_id),
                                        'publishedSha256':row['model_sha256']}
                    now = time.time()
                    with self.connect() as db:
                        db.execute('UPDATE real_estate SET model_rigs_json=?,model_asset_id=?,model_moderation=?,updated_at=? WHERE slug=?',
                            (json.dumps(model_rigs), model_rigs.get('house',{}).get('assetId') or row['model_asset_id'],
                             result.moderation_state or '', now, slug))
                        db.execute('UPDATE real_estate_publications SET asset_id=?,published_at=? WHERE id=?',
                            (str(result.asset_id), now, pending_id))
                    self.export()
            row = self.get(slug)
            if row['publicationCurrent']['model']:
                with self.connect() as db:
                    db.execute('UPDATE real_estate SET model_published_hash=? WHERE slug=?',
                               (row['model_sha256'], slug))
                self.export()
        for part in active:
            if scope != 'all' and image_part != part:
                continue
            # Refresh after each successful upload to preserve earlier progress.
            row = self.get(slug)
            if row['publicationCurrent'][part]:
                continue
            data = row['textures'][part]
            if data.get('reuseReference'):
                raise ValueError(f'{part} reused texture owner must publish first')
            progress(f'Preparing {part} image')
            with tempfile.TemporaryDirectory(prefix=f'game1-house-{part}-') as temp:
                image = prepare_texture(self.root, part, _source(self.root, data['path']), Path(temp))
                progress(f'Publishing {part} image · Roblox Open Cloud')
                pending = self._pending_publication(slug, part, data['sha256'])
                if pending:
                    operation = pending['operation']
                    pending_id = pending['id']
                else:
                    operation = create_image_asset(image, display_name=f'{slug} {part}',
                        description=description, creator_type=credentials['creatorType'],
                        creator_id=credentials['creatorId'], api_key=credentials['apiKey'])
                    pending_id = self._remember_operation(slug, part, data['sha256'], operation)
                progress(f'Waiting for Roblox to process {part} image')
                result = wait_for_operation(operation, api_key=credentials['apiKey'])
            textures = row['textures']
            textures[part] = {**data, 'assetId': result.asset_id,
                              'publishedSha256': data['sha256'],
                              'publicationFormat': published_format(Path(data['path']))}
            now = time.time()
            with self.connect() as db:
                db.execute('UPDATE real_estate SET textures_json=?,updated_at=? WHERE slug=?',
                    (json.dumps(textures, ensure_ascii=False), now, slug))
                db.execute('UPDATE real_estate_publications SET asset_id=?,published_at=? WHERE id=?',
                           (str(result.asset_id), now, pending_id))
            self.export()
        return self.get(slug)

    def _pending_publication(self, slug: str, part: str, sha256: str):
        """Recover a submitted Roblox operation after polling or a process failure."""
        with self.connect() as db:
            record = db.execute(
                'SELECT id,operation FROM real_estate_publications '
                "WHERE house_slug=? AND part=? AND sha256=? AND asset_id='' "
                'ORDER BY id DESC LIMIT 1', (slug, part, sha256)).fetchone()
            return dict(record) if record is not None else None

    def _remember_operation(self, slug: str, part: str, sha256: str, operation: str) -> int:
        # Persist BEFORE polling. A retry resumes this operation, never creates
        # another asset merely because Open Cloud polling was interrupted.
        with self.connect() as db:
            cursor = db.execute(
                'INSERT INTO real_estate_publications(house_slug,part,asset_id,sha256,operation,published_at) '
                "VALUES(?,?,'',?,?,?)", (slug, part, sha256, operation, time.time()))
            return int(cursor.lastrowid)

    def publications(self, slug: str):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM real_estate_publications WHERE house_slug=? ORDER BY id DESC', (slug,))]

    def snapshot(self):
        rows = self.list()
        return {'schemaVersion': 2, 'items': rows,
                'textureReferences':self.texture_references(), 'summary': {
            'registered': len(rows), 'published': sum(r['status'] == 'PUBLISHED' for r in rows),
            'changed': sum(r['status'] == 'UPDATE_AVAILABLE' for r in rows)}}

    def export(self):
        target = self.root / 'assets/manifests/real-estate.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
