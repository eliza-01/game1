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
from datetime import datetime, timezone

from opencloud_assets import create_model_asset, create_image_asset, wait_for_operation
from sqlite_connection import connect
from .contracts import identity, parse_name, prices, present_parts, validate_analysis, warnings_for_analysis
from .textures import available_textures, resolve_texture
from .fbx import inspect, prepare_publication
from .mesh_revisions import inspect_revision, save_immutable
from .publication_textures import prepare_texture, published_format
from .collision_policy import is_collision_mesh, requires_texture, default_no_collide
from services.texture_atlas_registry import AtlasRegistry, parse_filename, atlas_version, same_atlas_series


def glass_default(part: str) -> bool:
    return 'glass' in part.casefold()


def mesh_options(parts, raw: dict | None) -> dict:
    """Effective authoring flags. Legacy rows get defaults without a DB rewrite."""
    source = raw if isinstance(raw, dict) else {}
    result = {}
    for part in parts:
        entry = source.get(part)
        entry = entry if isinstance(entry, dict) else {}
        glass = entry.get('glass')
        no_collide = entry.get('noCollide')
        destructible = entry.get('destructible')
        result[part] = {
            'glass': (glass if type(glass) is bool else glass_default(part))
                     if requires_texture(part) else False,
            'noCollide': no_collide if type(no_collide) is bool else default_no_collide(part),
            'collisionMesh': is_collision_mesh(part),
            # Same authoring policy as Location Assets: solid weapon bounce by default.
            # Actual break/damage simulation is a separate future gameplay feature.
            'destructible': destructible if type(destructible) is bool and is_collision_mesh(part) else False,
        }
    return result


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
        self.atlases = (getattr(location_assets, "atlases", None) or AtlasRegistry(self.root))
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
            if 'mesh_sources_json' not in columns:
                db.execute("ALTER TABLE real_estate ADD COLUMN mesh_sources_json TEXT NOT NULL DEFAULT '{}'")
            if 'mesh_options_json' not in columns:
                db.execute("ALTER TABLE real_estate ADD COLUMN mesh_options_json TEXT NOT NULL DEFAULT '{}'")
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
        self._index_legacy_texture_publications()
        self.export()

    def _index_legacy_texture_publications(self) -> None:
        # Historical image IDs remain records, not active per-Estate bindings.
        # Conflicting IDs with the same bytes must never be silently chosen.
        records = []
        with self.connect() as db:
            for row in db.execute('SELECT slug,textures_json FROM real_estate'):
                for part, texture in json.loads(row['textures_json']).items():
                    if texture.get('reuseReference') or not texture.get('assetId'):
                        continue
                    if texture.get('sha256') != texture.get('publishedSha256'):
                        continue
                    records.append({'id': f"{row['slug']}:{part}",
                        'sha256': texture['sha256'], 'imageId': texture['assetId']})
        self.atlases.import_legacy_publications('real_estate', records)

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
                    'label': row.get('name_en') or row['slug'],
                    'slug': row['slug'],
                    'filename': row.get('texture_filename') or Path(row['texture_path']).name,
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
                    'slug': row['slug'],
                    'filename': data.get('filename') or Path(data['path']).name,
                    'group': 'estate', 'category': '', 'categoryLabel': '',
                    'path': data['path'], 'sha256': data['sha256'],
                    'assetId': str(data['assetId'])})
        # Published shared variants belong to the central atlas catalog,
        # independently of any Estate or Location Asset that selected them.
        for family in self.atlases.catalog():
            for variant in family['variants']:
                if not variant['current']:
                    continue
                choices.append({'reference': f"atlas:{variant['id']}",
                    'label': family['atlasKey'], 'slug': '',
                    'filename': variant['filename'], 'group': 'atlas',
                    'category': '', 'categoryLabel': '',
                    'path': variant['source_path'], 'sha256': variant['source_sha256'],
                    'assetId': str(variant['published_id'])})
        return choices

    @staticmethod
    def _atlas_presentation(texture: dict, catalog: dict[str, dict]) -> dict:
        """Resolve display metadata AFTER reuse references have supplied a filename.

        Versions (_01, _02) are independent families sharing a mesh atlas series.
        Never infer a published ID or a binding merely from a filename.
        """
        filename = str(texture.get('filename') or Path(texture.get('path') or '').name)
        parsed = parse_filename(filename)
        key = texture.get('atlasKey') or (parsed['atlasKey'] if parsed else '')
        family = catalog.get(key)
        base, version = atlas_version(key)
        result = dict(texture)
        result['atlasLegacyWarning'] = parsed is None
        result['atlasKey'] = key
        result['atlasVersion'] = version
        result['atlasVariants'] = family['variants'] if family else []
        # Include all resolution options from every published/registered version.
        # The currently bound variant identity is never derived from a name.
        choices = [dict(variant, atlasKey=group['atlasKey'])
                   for group in catalog.values()
                   if version and group.get('version') and group.get('baseKey') == base
                   for variant in group['variants']]
        choices.sort(key=lambda v: (int(v['version']), -int(v['width'])*int(v['height']), v['id']))
        result['atlasVersionChoices'] = choices
        return result

    def _atlas_metadata(self, slug: str, part: str, texture: dict,
                        catalog: dict[str, dict]) -> dict:
        binding = self.atlases.binding('real_estate', f'{slug}:{part}')
        result = dict(texture)
        if binding:
            result.update(path=binding['source_path'], filename=binding['filename'],
                sha256=binding['source_sha256'], assetId=binding['published_id'] or '',
                publishedSha256=binding['published_sha256'] or '',
                publicationFormat=published_format(Path(binding['source_path'])),
                atlasVariantId=binding['variant_id'], atlasKey=binding['atlas_key'],
                atlasBindingRevision=binding['revision'], atlasSyncStatus=binding['syncStatus'])
        else:
            result.update(atlasVariantId=None, atlasKey='', atlasBindingRevision=0,
                atlasSyncStatus='')
        result = self._atlas_presentation(result, catalog)
        result['atlasCurrent'] = binding['current'] if binding else None
        return result

    def select_atlas(self, slug: str, part: str, variant_id: int, expected_revision: int | None) -> dict:
        row = self.get(slug)
        if not row or part not in row['meshParts']:
            raise ValueError('unknown Real Estate mesh')
        if is_collision_mesh(part):
            raise ValueError('collision-only mesh does not use a texture atlas')
        # A mesh with a shared/local-house reference must first be given its
        # own variant choice. Only the selected mesh changes; other bindings live.
        selected = self.atlases.get_variant(variant_id)
        if not selected or not selected['current']:
            raise ValueError('select a published atlas variant')
        current_key = row['textures'][part].get('atlasKey')
        if current_key and not same_atlas_series(current_key, selected['atlas_key']):
            raise ValueError('select an atlas resolution or version from the same mesh series')
        self.atlases.bind('real_estate', f'{slug}:{part}', variant_id,
            expected_revision=expected_revision)
        # An explicit resolution choice supersedes a prior owner reference.
        # Keep the historical owned ID and source intact for rollback/audit.
        with self.connect() as db:
            old = db.execute('SELECT textures_json FROM real_estate WHERE slug=?', (slug,)).fetchone()
            textures = json.loads(old['textures_json'])
            if textures[part].get('reuseReference'):
                textures[part]['reuseReference'] = ''
                db.execute('UPDATE real_estate SET textures_json=?,updated_at=? WHERE slug=?',
                           (json.dumps(textures, ensure_ascii=False), time.time(), slug))
        self.export()
        return self.get(slug)

    def list(self):
        rows = self._raw_rows()
        references = {option['reference']: option for option in self.texture_references(rows)}
        atlas_catalog = {group['atlasKey']: group for group in self.atlases.catalog()}
        result = []
        for row in rows:
            row['skeleton'] = json.loads(row.pop('skeleton_json'))
            row['rigWarnings'] = warnings_for_analysis(row['skeleton'])
            active = present_parts(row['skeleton'])
            row['meshParts'] = list(active)
            row['meshSources'] = json.loads(row.pop('mesh_sources_json') or '{}')
            row['rigSourceHashes'] = {part: row['meshSources'].get(part, {}).get('sha256') or row['model_sha256'] for part in active}
            row['meshOptions'] = mesh_options(active, json.loads(row.pop('mesh_options_json') or '{}'))
            # Legacy records may still store door assets after the FBX is
            # replaced with a doorless house; they are publication history,
            # not active resources for the current template.
            row['textures'] = {part: data for part, data in
                json.loads(row.pop('textures_json')).items() if part in active}
            row['rigAssets'] = {part: data for part, data in
                json.loads(row.pop('model_rigs_json') or '{}').items() if part in active}
            current = {'model': all(
                row['rigAssets'].get(part, {}).get('assetId') and
                row['rigAssets'][part].get('publishedSha256') == row['rigSourceHashes'][part]
                for part in active)}
            for part in active:
                # Physics geometry has a Model Asset but never needs an Image
                # Asset. Historical texture records are preserved for audit.
                if is_collision_mesh(part):
                    row['textures'].setdefault(part, {'path':'', 'filename':'', 'sha256':'',
                        'assetId':'', 'publishedSha256':'', 'reuseReference':''})
                    current[part] = True
                    continue
                row['textures'][part] = self._atlas_metadata(row['slug'], part, row['textures'][part], atlas_catalog)
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
                        # Expose the actual shared atlas metadata for the door,
                        # without creating a second publication or binding.
                        row['textures'][part] = {**row['textures'][part], **{
                            k: owner.get(k) for k in ('filename', 'atlasVariantId', 'atlasKey',
                                'atlasBindingRevision', 'atlasSyncStatus', 'atlasVariants',
                                'atlasLegacyWarning', 'atlasVersion', 'atlasVersionChoices', 'atlasCurrent')}}
                        current[part] = bool(current['house'])
                    else:
                        owner = references.get(reference)
                        if owner:
                            effective = {**texture, 'path': owner['path'],
                                'filename': owner['filename'], 'sha256': owner['sha256'],
                                'assetId': owner['assetId'], 'publishedSha256': owner['sha256'],
                                'publicationFormat': published_format(Path(owner['path']))}
                            row['textures'][part] = self._atlas_presentation(effective, atlas_catalog)
                        current[part] = owner is not None
                else:
                    current[part] = (bool(texture['atlasCurrent']) if texture['atlasCurrent'] is not None
                        else bool(texture.get('assetId') and
                        texture.get('publishedSha256') == texture['sha256'] and
                        texture.get('publicationFormat', 'source') == published_format(Path(texture['path']))))
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
            if is_collision_mesh(part):
                if reference:
                    raise ValueError(f'{part}: collision mesh must not select a texture reference')
                continue
            if reference.startswith('atlas:'):
                try:
                    variant = self.atlases.get_variant(int(reference[6:]))
                except ValueError:
                    variant = None
                if not variant or not variant['current']:
                    raise ValueError(f'{part}: select an existing published atlas variant')
                continue
            if reference == 'mesh:house':
                if part == 'house':
                    raise ValueError('The house mesh cannot reuse its own atlas')
                continue  # Owner is the current house, not a published catalog entry.
            if reference and (reference not in catalog or reference == f'estate:{slug}:{part}'):
                raise ValueError(f'{part}: unknown or unpublished reusable texture {reference}')
        previous_options = (existing or {}).get('meshOptions', {})
        incoming_options = payload.get('meshOptions')
        merged_options = mesh_options(active, {**previous_options, **incoming_options}
            if isinstance(incoming_options, dict) else previous_options)
        texture_sources = {
            part: (resolve_texture(self.root, selections.get(part), part=part)
                   if requires_texture(part) and not chosen_refs[part] else None)
            for part in active
        }
        canonical = self.root / 'assets' / 'source' / 'real-estate' / slug
        destination_model = canonical / 'model' / f'{slug}.fbx'
        # Resolve standard-named sources once into the shared atlas catalog.
        # Reused variants are REFERENCES ONLY: no copy and no Open Cloud upload.
        atlas_selections = {}
        for part in active:
            ref = chosen_refs[part]
            if ref.startswith('atlas:'):
                atlas_selections[part] = self.atlases.get_variant(int(ref[6:]))
            elif texture_sources[part] is not None and parse_filename(texture_sources[part].name):
                atlas_selections[part] = self.atlases.register_file(str(texture_sources[part]))
        destination_textures = {
            part: canonical / 'textures' / f'{part}{path.suffix.lower()}'
            for part, path in texture_sources.items()
            if path is not None and part not in atlas_selections
        }
        model_hash = _sha(source)
        if existing and existing.get('meshSources') and raw_source and model_hash != existing['model_sha256']:
            raise ValueError('This Estate uses independent FBX mesh revisions. Replace each chosen mesh from the full FBX via Mesh source / Studio sync; whole-house replacement would overwrite their separate skeleton contracts.')
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
            if is_collision_mesh(part):
                # Store no new image binding or source for geometry-only mesh.
                # Existing Roblox image publication history is never deleted.
                texture_rows[part] = {'path':'', 'filename':'', 'sha256':'',
                    'reuseReference':'', 'assetId':'', 'publishedSha256':'',
                    'publicationFormat':''}
                continue
            if part in atlas_selections:
                variant = atlas_selections[part]
                texture_rows[part] = {'path': variant['source_path'],
                    'filename': variant['filename'], 'sha256': variant['source_sha256'],
                    'reuseReference': '',
                    # Historic fields remain for auditing; effective publication
                    # comes ONLY from the shared AtlasRegistry binding.
                    'assetId': old.get('assetId') or '',
                    'publishedSha256': old.get('publishedSha256') or '',
                    'publicationFormat': old.get('publicationFormat') or ''}
                continue
            if reference:
                # Record the shared identity, not a duplicate upload. Effective
                # Image Asset IDs are resolved from the owner on every read.
                texture_rows[part] = {'reuseReference': reference, 'path':'',
                    'sha256':'', 'assetId':'', 'publishedSha256':'', 'publicationFormat':'', 'filename':''}
                continue
            target = destination_textures[part]
            target.parent.mkdir(parents=True, exist_ok=True)
            if texture_sources[part] != target:
                shutil.copy2(texture_sources[part], target)
            # A regular edit supplies the already-canonical file again. Keep
            # the original authoring filename instead of replacing it with
            # house.png / door.jpg on every metadata-only save.
            filename = (old.get('filename') or target.name) if texture_sources[part] == target else texture_sources[part].name
            texture_rows[part] = {'path': str(target.relative_to(self.root)).replace('\\', '/'),
                'filename': filename,
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
        with self.connect() as db:
            db.execute('UPDATE real_estate SET mesh_options_json=? WHERE slug=?',
                (json.dumps(merged_options, ensure_ascii=False), slug))
        # Record binding changes only after the Estate row exists. Re-saving
        # a legacy house does not silently migrate/re-publish its texture.
        for part in active:
            if part in atlas_selections:
                self.atlases.bind('real_estate', f'{slug}:{part}',
                    atlas_selections[part]['id'], allow_unpublished=True)
            else:
                self.atlases.unbind('real_estate', f'{slug}:{part}')
        self.export()
        return self.get(slug)

    def inspect_mesh(self, slug: str, part: str, source_path: str) -> dict:
        row = self.get(slug)
        if not row or part not in row['meshParts']:
            raise ValueError('select a registered Real Estate mesh')
        source = Path(str(source_path or '')).expanduser().resolve()
        mesh = inspect_revision(self.root, source, part)
        return {'slug': slug, 'part': part, 'sourcePath': str(source),
                'mesh': mesh, 'sourceSha256': _sha(source),
                'currentSha256': row['rigSourceHashes'][part]}

    def replace_mesh(self, slug: str, part: str, source_path: str,
                     *, expected_revision: int) -> dict:
        """Replace only one named mesh; no Model or Image publication here."""
        row = self.get(slug)
        if row is None or part not in row['meshParts']:
            raise ValueError('unknown Real Estate mesh')
        if row['revision'] != expected_revision:
            raise ValueError('house changed since inspection; refresh before replacing a mesh')
        if self._pending_publication_for_house(slug):
            raise ValueError('cannot replace a mesh during an unresolved publication')
        source = Path(str(source_path or '')).expanduser().resolve()
        new_mesh = inspect_revision(self.root, source, part)
        snapshot = save_immutable(self.root, slug, part, source)
        new_skeleton = dict(row['skeleton'])
        new_skeleton['meshes'] = [new_mesh if old['name'] == part else old
                                   for old in row['skeleton']['meshes']]
        new_sources = dict(row['meshSources'])
        new_sources[part] = snapshot
        with self.connect() as db:
            cursor = db.execute("""UPDATE real_estate SET skeleton_json=?,mesh_sources_json=?,
                revision=revision+1,updated_at=? WHERE slug=? AND revision=?""",
                (json.dumps(new_skeleton, ensure_ascii=False),
                 json.dumps(new_sources, ensure_ascii=False), time.time(), slug, expected_revision))
            if cursor.rowcount != 1:
                raise ValueError('concurrent house revision change; refresh and retry')
        self.export()
        return self.get(slug)

    def _pending_publication_for_house(self, slug: str) -> bool:
        with self.connect() as db:
            return bool(db.execute("""SELECT 1 FROM real_estate_publications
                WHERE house_slug=? AND asset_id='' AND operation!='' LIMIT 1""", (slug,)).fetchone())

    def delete(self, slug: str) -> dict:
        """Retire the authoring registration, not uploaded Roblox assets or shared atlases.

        An on-disk JSON audit copy is created before database changes. Source
        FBX/PNGs remain on disk, so retirement never loses local authoring work.
        """
        row = self.get(slug)
        if not row:
            raise ValueError('unknown registered house')
        for candidate in self._raw_rows():
            if candidate['slug'] == slug:
                continue
            for part, texture in json.loads(candidate['textures_json']).items():
                if str(texture.get('reuseReference') or '').startswith(f'estate:{slug}:'):
                    raise ValueError(f"{slug} is reused by {candidate['slug']} / {part}; change the dependent texture first")
        with self.connect() as db:
            unfinished = db.execute(
                "SELECT COUNT(*) FROM real_estate_publications WHERE house_slug=? AND asset_id='' AND operation!=''",
                (slug,)).fetchone()[0]
            if unfinished:
                raise ValueError('house has an unresolved Roblox publication; resolve it before deleting')
            raw = dict(db.execute('SELECT * FROM real_estate WHERE slug=?', (slug,)).fetchone())
            publications = [dict(r) for r in db.execute(
                'SELECT * FROM real_estate_publications WHERE house_slug=? ORDER BY id', (slug,))]
        archive = self.root / '.control-center' / 'real-estate-retired'
        archive.mkdir(parents=True, exist_ok=True)
        target = archive / (slug + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        # Exclusive creation guarantees that an old archive cannot be replaced.
        with target.open('x', encoding='utf-8') as file:
            json.dump({'house': raw, 'publications': publications, 'sourceFilesPreserved': True},
                      file, ensure_ascii=False, indent=2)
        with self.connect() as db:
            db.execute('DELETE FROM real_estate_publications WHERE house_slug=?', (slug,))
            cursor = db.execute('DELETE FROM real_estate WHERE slug=?', (slug,))
            if cursor.rowcount != 1:
                raise ValueError('house changed during retirement; archive preserved')
        for part in json.loads(raw['skeleton_json']).get('meshes', []):
            if isinstance(part, dict) and isinstance(part.get('name'), str):
                self.atlases.unbind('real_estate', f"{slug}:{part['name']}")
        self.export()
        return {'ok': True, 'archived': target.relative_to(self.root).as_posix(),
                'sourceFilesPreserved': True, 'studioTemplatesUnchanged': True}

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
        if image_part is not None and is_collision_mesh(image_part):
            raise ValueError(f'{image_part}: collision geometry has no Image Asset to publish')
        description = str(credentials.get('description') or f'Game1 Real Estate {slug}')
        common = dict(display_name=slug, description=description,
                      creator_type=credentials['creatorType'], creator_id=credentials['creatorId'],
                      api_key=credentials['apiKey'])
        for part in active:
            if is_collision_mesh(part):
                continue
            reference = row['textures'][part].get('reuseReference')
            if reference == 'mesh:house':
                # 'all' publishes house before door. 'model' only needs a
                # locally available texture for Blender's rig export.
                if image_part == part and not row['publicationCurrent']['house']:
                    raise ValueError('Publish the house image first; this mesh reuses its atlas')
                continue
            if reference and not row['publicationCurrent'][part]:
                raise ValueError(f'{part} reused texture owner must publish first')
        # Once an Estate has mesh-specific sources, stage every requested
        # changed rig independently. A full-FBX edit may be published one part
        # at a time without replacing the other Model Asset IDs.
        scoped_parts = [part for part in active if (
            (force_model_part == part) or
            (force_model_part is None and scope in ('all', 'model')
             and (row['rigAssets'].get(part, {}).get('publishedSha256') != row['rigSourceHashes'][part]
                  or not row['rigAssets'].get(part, {}).get('assetId'))))]
        if row['meshSources'] and scoped_parts:
            with tempfile.TemporaryDirectory(prefix='game1-estate-mesh-revision-') as temp:
                staging = Path(temp)
                rigs = staging / 'rigs'
                for part in scoped_parts:
                    row = self.get(slug)
                    pinned = row['meshSources'].get(part) or {
                        'path':row['model_path'], 'sha256':row['model_sha256']}
                    fingerprint = pinned['sha256']
                    pinned_source = _source(self.root, pinned['path'])
                    if not pinned_source.is_file() or _sha(pinned_source) != fingerprint:
                        raise ValueError(f'{part}: immutable FBX revision source is missing or changed; refusing publication')
                    progress(f'Preparing only {part} from its authoring FBX source')
                    texture = row['textures'].get(part, {})
                    images = ({part: str(prepare_texture(self.root, part,
                        _source(self.root, texture['path']), staging))}
                        if requires_texture(part) else {})
                    selected = next(m for m in row['skeleton']['meshes'] if m['name'] == part)
                    prepare_publication(self.root, pinned_source, rigs,
                        {'schemaVersion': 1, 'meshes': [selected]}, images, only_part=part)
                    pending = self._pending_publication(slug, 'model:' + part, fingerprint)
                    if pending:
                        operation, pending_id = pending['operation'], pending['id']
                    else:
                        operation = create_model_asset(rigs / (part + '.fbx'),
                            **{**common, 'display_name':f'{slug} {part}'})
                        pending_id = self._remember_operation(slug, 'model:' + part, fingerprint, operation)
                    progress(f'Waiting for Roblox to process only {part}')
                    result = wait_for_operation(operation, api_key=credentials['apiKey'])
                    rigs_data = self.get(slug)['rigAssets']
                    rigs_data[part] = {'assetId':str(result.asset_id), 'publishedSha256':fingerprint}
                    with self.connect() as db:
                        db.execute('UPDATE real_estate SET model_rigs_json=?,model_asset_id=?,model_moderation=?,updated_at=? WHERE slug=?',
                            (json.dumps(rigs_data), rigs_data.get('house',{}).get('assetId') or row['model_asset_id'],
                             result.moderation_state or '', time.time(), slug))
                        db.execute('UPDATE real_estate_publications SET asset_id=?,published_at=? WHERE id=?',
                                   (str(result.asset_id), time.time(), pending_id))
                    self.export()
            row = self.get(slug)
            if row['publicationCurrent']['model']:
                with self.connect() as db:
                    db.execute('UPDATE real_estate SET model_published_hash=? WHERE slug=?',
                               (row['model_sha256'], slug))
                self.export()
        else:
            if (scope in ('all', 'model') and not row['publicationCurrent']['model']) or force_model_part:
                progress('Preparing ' + ' and '.join(part + ' rig' for part in active) + ' in Blender')
                with tempfile.TemporaryDirectory(prefix='game1-house-model-') as temp:
                    staging = Path(temp)
                    # Each skeleton is published as its own Roblox Model Asset;
                    # otherwise Roblox collapses both rigs under one RootPart.
                    images = {
                        part: prepare_texture(self.root, part, _source(self.root, data['path']), staging)
                        for part, data in row['textures'].items() if requires_texture(part)
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
            if is_collision_mesh(part):
                if image_part == part:
                    raise ValueError(f'{part}: collision geometry has no Image Asset to publish')
                continue
            # Refresh after each successful upload to preserve earlier progress.
            row = self.get(slug)
            if row['publicationCurrent'][part]:
                continue
            data = row['textures'][part]
            if data.get('atlasVariantId'):
                # Central publication owns the one Image Asset ID; Real Estate
                # never uploads an image already present in the catalog.
                progress(f'Publishing shared atlas for {part} (deduplicated)')
                self.atlases.ensure_published(data['atlasVariantId'], credentials, description)
                self.export()
                continue
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
            self._index_legacy_texture_publications()
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
        return {'schemaVersion': 2, 'items': rows, 'atlasCatalog': self.atlases.catalog(),
                'textureReferences':self.texture_references(), 'summary': {
            'registered': len(rows), 'published': sum(r['status'] == 'PUBLISHED' for r in rows),
            'changed': sum(r['status'] == 'UPDATE_AVAILABLE' for r in rows)}}

    def export(self):
        target = self.root / 'assets/manifests/real-estate.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
