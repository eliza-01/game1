from __future__ import annotations

from model_publication_service import staged_model

from pathlib import Path
import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone

from sqlite_connection import connect as connect_sqlite
from services.texture_alpha import texture_uses_alpha
from services import location_asset_rename
from services.location_fbx_inspection import inspect as inspect_location_fbx
from services.mesh_authoring_policy import normalize_location_options
from services.texture_atlas_registry import AtlasRegistry, parse_filename

from opencloud_assets import (
    create_model_asset,
    wait_for_operation,
)

SCHEMA_VERSION = 4
PROJECT = "game1"
CATEGORIES = ("tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop")
TEXTURE_SUFFIXES = (".png", ".jpg", ".jpeg")
CATEGORY_LABELS = {
    "tree": "Trees",
    "bush": "Bushes",
    "rock": "Rocks",
    "light": "Lights",
    "fence": "Fences",
    "decoration": "Decorations",
    "ladder": "Ladders",
    "flower": "Flowers",
    "building": "Buildings",
    "prop": "Props",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("destructible must be a boolean")


def slugify_english(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        raise ValueError("asset name must contain latin letters or digits so a slug can be generated")
    if len(text) > 64:
        text = text[:64].rstrip("_")
    if not SLUG_RE.fullmatch(text):
        raise ValueError("generated location asset slug is invalid")
    return text


class LocationAssetStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runtime = self.root / ".control-center"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.db = self.runtime / "game1.db"
        self._init()
        self.atlases = AtlasRegistry(self.root)
        self._index_legacy_texture_publications()
        with self.connect() as db:
            columns = {r[1] for r in db.execute('PRAGMA table_info(location_assets)')}
            unfinished = bool('texture_path' in columns)  # upgrade before projections
        if not unfinished:
            self.export()

    def connect(self):
        # Shared closing connection commits/rolls back AND releases the file handle.
        # sqlite3.Connection.__exit__ alone leaves the database open on Windows.
        return connect_sqlite(self.db)

    def _init(self):
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS location_assets(
                    slug TEXT PRIMARY KEY,
                    name_en TEXT NOT NULL,
                    category TEXT NOT NULL,
                    model_path TEXT NOT NULL DEFAULT '',
                    model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,
                    model_published_sha256 TEXT NOT NULL DEFAULT '',
                    model_moderation_state TEXT NOT NULL DEFAULT '',
                    destructible INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(location_assets)").fetchall()}
            required = {
                'slug','name_en','category','model_path','model_sha256',
                'model_asset_id','model_published_sha256','model_moderation_state',
                'destructible','revision','created_at','updated_at','published_at',
            }
            if not required.issubset(columns):
                missing = ", ".join(sorted(required - columns))
                raise RuntimeError(f"Location Asset database schema is incomplete after migration: {missing}")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS location_asset_publications(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_slug TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,
                    operation_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    moderation_state TEXT NOT NULL DEFAULT '',
                    published_at REAL NOT NULL
                )"""
            )
            connection.execute("""CREATE TABLE IF NOT EXISTS location_asset_mesh_id_inventory(
                asset_slug TEXT NOT NULL,
                model_asset_id TEXT NOT NULL,
                meshes_json TEXT NOT NULL,
                observed_at REAL NOT NULL,
                PRIMARY KEY(asset_slug,model_asset_id)
            )""")
            if 'mesh_options_json' not in columns:
                # Capture a consistent SQLite snapshot before the additive migration.
                # Do not mix the backup with the authoring source/assets.
                import sqlite3
                backup_dir = self.runtime / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / ('location_mesh_options_m232_' +
                    datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
                with sqlite3.connect(str(backup)) as saved:
                    connection.backup(saved)
                connection.execute("ALTER TABLE location_assets ADD COLUMN mesh_options_json TEXT NOT NULL DEFAULT '{}'")
            connection.execute("""CREATE TABLE IF NOT EXISTS location_asset_slug_aliases(
                old_slug TEXT PRIMARY KEY,
                current_slug TEXT NOT NULL,
                renamed_at REAL NOT NULL
            )""")
            # Owner-era texture columns remain readable only until the M203
            # atlas migration drops them; never mutate old Image Asset IDs.

    def _index_legacy_texture_publications(self) -> None:
        # Import history into the shared registry without renaming files or
        # changing any published Roblox identity. Conflicts remain pending.
        with self.connect() as connection:
            columns = {r[1] for r in connection.execute('PRAGMA table_info(location_assets)')}
            if not {'texture_sha256','texture_asset_id','texture_published_sha256'} <= columns:
                return
            rows = connection.execute("""SELECT slug,texture_sha256,texture_asset_id
                FROM location_assets WHERE texture_sha256=texture_published_sha256
                AND texture_asset_id IS NOT NULL""").fetchall()
        self.atlases.import_legacy_publications('location_asset', [
            {'id':r['slug'],'sha256':r['texture_sha256'],'imageId':r['texture_asset_id']}
            for r in rows])

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def options_category_ids() -> tuple[str, ...]:
        return CATEGORIES

    def aliases_for(self, slug: str) -> list[str]:
        return location_asset_rename.aliases(self, slug)

    def rename_identity(self, old_slug: str, payload: dict) -> dict:
        return location_asset_rename.rename(self, old_slug, payload)

    def options(self) -> dict:
        return {
            "categories": [
                {"id": category, "label": CATEGORY_LABELS[category]}
                for category in CATEGORIES
            ]
        }

    @staticmethod
    def _texture_current(row: dict) -> bool:
        return bool(
            str(row.get("texture_asset_id") or "")
            and str(row.get("texture_published_sha256") or "") == str(row.get("texture_sha256") or "")
        )

    def _status(self, row: dict) -> str:
        model_current = bool(row.get('model_asset_id') and
            row.get('model_published_sha256') == row.get('model_sha256'))
        if not row.get('model_path') or not row.get('atlasVariantId'):
            return 'INCOMPLETE'
        if model_current and self._texture_current(row):
            return 'PUBLISHED'
        return 'UPDATE_AVAILABLE' if row.get('model_asset_id') else 'LOCAL_ONLY'

    def _raw_get(self, slug: str) -> dict | None:
        normalized = str(slug or "").strip().lower()
        if not normalized:
            return None
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM location_assets WHERE slug=?", (normalized,)).fetchone()
        return dict(row) if row else None

    def _analysis_path(self, slug: str) -> Path:
        if not SLUG_RE.fullmatch(str(slug)):
            raise ValueError('invalid Location Asset slug for FBX analysis')
        return self.root / 'assets/manifests/location-assets-fbx' / f'{slug}.json'

    def _fbx_analysis(self, row: dict) -> dict | None:
        path = self._analysis_path(row['slug'])
        if not path.is_file():
            for alias in reversed(self.aliases_for(row['slug'])):
                candidate = self._analysis_path(alias)
                if candidate.is_file():
                    path = candidate
                    break
            else:
                return None
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if (document.get('sourceSha256') != row.get('model_sha256')
                or not isinstance(document.get('analysis'), dict)):
            return None
        return document['analysis']

    def _save_fbx_analysis(self, slug: str, sha: str, analysis: dict) -> None:
        destination = self._analysis_path(slug)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {'schemaVersion': 1, 'slug': slug, 'sourceSha256': sha,
                   'analysis': analysis}
        staged = destination.with_suffix('.tmp')
        staged.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        staged.replace(destination)

    def inspect_source_fbx(self, source_path: str) -> dict:
        """Pure preview matching Real Estate /inspect. No registration or uploads."""
        source = Path(str(source_path or '')).expanduser().resolve()
        analysis = inspect_location_fbx(self.root, source)
        return {'sourcePath':str(source), 'name':source.stem,
                'analysis':analysis, 'meshOptions':normalize_location_options(analysis, {})}

    def inspect_registered_fbx(self, slug: str) -> dict:
        """Explicit inspection of a pre-M231 canonical FBX (no asset revision)."""
        row = self._raw_get(slug)
        if not row:
            raise ValueError('unknown Location Asset')
        source = self.root / str(row['model_path'])
        if not source.is_file() or self._sha256(source) != row['model_sha256']:
            raise ValueError('canonical FBX missing or changed; save a new revision first')
        analysis = inspect_location_fbx(self.root, source)
        # Another tab may have registered a new revision during inspection.
        current = self._raw_get(slug)
        if not current or current['model_sha256'] != row['model_sha256']:
            raise ValueError('FBX revision changed during inspection; retry')
        self._save_fbx_analysis(slug, row['model_sha256'], analysis)
        self.export()
        return self.get(slug)

    def _decorate(self, row, rows_by_slug=None, atlas_catalog=None) -> dict:
        """Only a direct binding determines the effective image publication."""
        result = dict(row)
        result['fbxAnalysis'] = self._fbx_analysis(result)
        try:
            stored_options = json.loads(result.pop('mesh_options_json', '{}') or '{}')
            result['meshOptions'] = stored_options if isinstance(stored_options, dict) else {}
        except (ValueError, TypeError):
            result['meshOptions'] = {}

        atlas_catalog = self.atlases.catalog() if atlas_catalog is None else atlas_catalog
        binding = self.atlases.binding('location_asset', str(result.get('slug') or ''))
        result['destructible'] = bool(result.get('destructible'))
        for field, default in (('texture_path',''),('texture_filename',''),('texture_sha256',''),
                               ('texture_asset_id',None),('texture_published_sha256',''),
                               ('texture_moderation_state',''),('texture_reference_slug','')):
            result.setdefault(field,default)
        if binding:
            result.update(texture_path=binding['source_path'],
                texture_filename=binding['original_filename'],
                texture_sha256=binding['source_sha256'],
                texture_asset_id=binding['published_id'],
                texture_published_sha256=binding['published_sha256'],
                texture_moderation_state=binding['moderation_state'],
                atlasVariantId=binding['variant_id'],
                atlasFamily=binding['atlas_key'],
                atlasResolution=binding['resolution'],
                bindingRevision=binding['revision'],
                studioSyncStatus=binding['syncStatus'],
                atlasVariants=self.atlases.attached_variants('location_asset', result['slug']))
        result.setdefault('atlasVariants', self.atlases.attached_variants('location_asset', result['slug']))
        result['textureUsesAlpha'] = (texture_uses_alpha(self.root, str(result.get('texture_path') or ''))
                                       if binding and binding['current'] else None)
        result['atlasLegacyWarning'] = bool(binding and not parse_filename(result['texture_filename']))
        result['status'] = self._status(result)
        result['category_label'] = CATEGORY_LABELS.get(result.get('category'), str(result.get('category') or ''))
        return result

    def list(self) -> list[dict]:
        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT * FROM location_assets ORDER BY category,name_en,slug"
            ).fetchall()]
        rows_by_slug = {str(row.get("slug") or ""): row for row in rows}
        atlas_catalog = self.atlases.catalog()
        decorated = [self._decorate(row, rows_by_slug, atlas_catalog) for row in rows]
        # Read-only library presentation: reuse the scan inventory already in SQLite.
        # No Roblox asset loads, no inference from names in an FBX.
        with self.connect() as db:
            inventories = db.execute('SELECT asset_slug,model_asset_id,meshes_json '
                'FROM location_asset_mesh_id_inventory').fetchall()
        by_version = {(record['asset_slug'],str(record['model_asset_id'])):
            json.loads(record['meshes_json']) for record in inventories}
        for item in decorated:
            item['publishedVisualMeshes'] = [
                {'meshId':entry['meshId'],'name':name}
                for entry in by_version.get((item['slug'],str(item.get('model_asset_id') or '')),[])
                for name in entry.get('visualNames',[])
            ]
        return decorated

    def get(self, slug: str) -> dict | None:
        row = self._raw_get(slug)
        return self._decorate(row) if row else None

    def _archive_existing(self, path: Path, slug: str, revision: int):
        """Archive replaced MODEL FBX; never retire Atlas Registry files."""
        if not path.is_file():
            return
        relative = path.resolve().relative_to(self.root)
        destination = self.root / 'assets/reimported/location-assets' / slug / f'r{revision:04d}' / Path(*relative.parts[-2:])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)

    def register(self, payload: dict) -> dict:
        incoming_slug = str(payload.get("slug") or "").strip().lower()
        old = self._raw_get(incoming_slug) if incoming_slug else None
        name_en = str(payload.get("nameEn") or (old.get("name_en") if old else "") or "").strip()
        if not name_en:
            raise ValueError("location asset name is required")
        slug = incoming_slug or (str(old.get("slug") or "") if old else "") or slugify_english(name_en)
        if not SLUG_RE.fullmatch(slug):
            raise ValueError("location asset slug must be lowercase snake_case")
        if old is None:
            old = self._raw_get(slug)
        if old is None:
            with self.connect() as db:
                if db.execute('SELECT 1 FROM location_asset_slug_aliases WHERE old_slug=?',
                              (slug,)).fetchone():
                    raise ValueError('slug belongs to a renamed Location Asset; reserved for history')
        # Registration and editing have separate authoring contracts. A stale
        # editor must never accidentally create a new asset or overwrite an
        # unrelated slug that somebody registered in another tab.
        if payload.get('createOnly') and old is not None:
            raise ValueError('asset already registered; open Edit instead')
        if payload.get('editOnly') and old is None:
            raise ValueError('asset no longer registered; refresh the library')
        expected = payload.get('expectedRevision')
        if expected is not None and (old is None or type(expected) is not int or
                                     int(old['revision']) != expected):
            raise ValueError('Location Asset changed since Edit opened; refresh before saving')
        category = str(payload.get("category") or (old.get("category") if old else "") or "").strip().lower()
        destructible = parse_bool(payload.get("destructible"), bool(old.get("destructible")) if old else False)
        if category not in CATEGORIES:
            raise ValueError("location asset category must be one of: " + ", ".join(CATEGORIES))

        selected_model = str(payload.get("modelSourcePath") or "").strip()
        inspected = None
        if payload.get('inspectFbx') is True:
            if not selected_model:
                raise ValueError('FBX inspection requires a selected model file')
            candidate = Path(selected_model).expanduser().resolve()
            if not candidate.is_file() or candidate.suffix.casefold() != '.fbx':
                raise ValueError('choose a valid Location Asset FBX')
            inspected = inspect_location_fbx(self.root, candidate)
        # Physics authoring is explicit. Old registrations retain their original
        # model behavior until the operator saves per-mesh controls.
        option_source = payload.get('meshOptions')
        prior_options = json.loads(old.get('mesh_options_json') or '{}') if old else {}
        if option_source is not None and inspected is None:
            inspected = self._fbx_analysis(old) if old else None
            if inspected is None:
                raise ValueError('Analyze the FBX before saving per-mesh physics')
        effective_options = (normalize_location_options(inspected, option_source)
            if option_source is not None else
            normalize_location_options(inspected, prior_options) if inspected and prior_options else prior_options)
        selected_texture = str(payload.get('textureSourcePath') or '').strip()
        atlas_variant_id = int(payload.get('atlasVariantId') or 0)
        if payload.get('textureReferenceSlug'):
            raise ValueError('select an independent Atlas Registry variant, not a model owner')
        if selected_texture and atlas_variant_id:
            raise ValueError('choose either an atlas file or registered variant')
        if selected_texture:
            atlas_variant_id = self.atlases.adopt_file(selected_texture)['id']
        if not atlas_variant_id and old:
            binding = self.atlases.binding('location_asset', slug)
            atlas_variant_id = int(binding['variant_id']) if binding else 0
        if not atlas_variant_id or not self.atlases.get_variant(atlas_variant_id):
            raise ValueError('select an independent atlas variant or PNG/JPG source')
        if old is None and not selected_model:
            raise ValueError('choose a location asset FBX before registration')

        now = time.time()
        revision = int(old.get("revision") or 0) + 1 if old else 1
        # Model rows do not store authoritative atlas paths/IDs.
        values = {'model_path': str(old.get('model_path') or '') if old else '',
                  'model_sha256': str(old.get('model_sha256') or '') if old else ''}
        texture_filename = ''
        texture_asset_id = None
        texture_published_sha256 = ''
        texture_moderation_state = ''
        stored_reference = ''

        # Legacy API callers that omit inspectFbx can analyze the registered
        # canonical source later; all Asset Manager writes request inspection.
        if selected_model:
            selected = Path(selected_model).expanduser().resolve()
            if not selected.is_file() or selected.suffix.lower() != ".fbx":
                raise ValueError("location asset model must be an FBX file")
            canonical_target = self.root / "assets/source/location-assets" / category / slug / "model" / f"{slug}.fbx"
            canonical_target.parent.mkdir(parents=True, exist_ok=True)
            if old:
                self._archive_existing(canonical_target, slug, int(old.get("revision") or 1))
            shutil.copy2(selected, canonical_target)
            values["model_path"] = canonical_target.relative_to(self.root).as_posix()
            values["model_sha256"] = self._sha256(canonical_target)

        with self.connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO location_assets (
                slug,name_en,category,model_path,model_sha256,model_asset_id,
                model_published_sha256,model_moderation_state,destructible,
                revision,created_at,updated_at,published_at,mesh_options_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (slug,name_en,category,values['model_path'],values['model_sha256'],
             old.get('model_asset_id') if old else None,
             str(old.get('model_published_sha256') or '') if old else '',
             str(old.get('model_moderation_state') or '') if old else '',
             1 if destructible else 0,revision,old.get('created_at') if old else now,
             now,old.get('published_at') if old else None,
             json.dumps(effective_options, ensure_ascii=False, sort_keys=True)))
        self.atlases.bind('location_asset', slug, atlas_variant_id, allow_unpublished=True)
        if inspected is not None:
            self._save_fbx_analysis(slug, values['model_sha256'], inspected)
        self.export()
        return self.get(slug)

    def select_atlas(self, slug: str, variant_id: int, expected_revision: int | None) -> dict:
        if not self._raw_get(slug):
            raise ValueError('unknown location asset')
        self.atlases.bind("location_asset", slug, variant_id, expected_revision=expected_revision)
        self.export()
        return self.get(slug)

    def publish(self, slug: str, credentials: dict, *, scope: str = 'changed',
                force_model: bool = False) -> dict:
        '''Publish selected resources independently with immutable Model IDs.

        Publishing a changed FBX creates a new Model Asset ID (as in Real
        Estate), never updates the old published version in place. The old ID
        remains active until Roblox confirms success. Atlas publication is
        delegated to the shared Atlas Registry and never changes the FBX.
        '''
        if scope not in ('changed', 'model', 'atlas'):
            raise ValueError('publication scope must be changed, model, or atlas')
        if force_model and scope != 'model':
            raise ValueError('force model publication requires model scope')
        row = self.get(slug)
        if not row:
            raise ValueError(f'unknown location asset: {slug}')
        model = self.root / str(row.get('model_path') or '')
        atlas_binding = self.atlases.binding('location_asset', slug)
        if scope in ('changed', 'model') and not model.is_file():
            raise ValueError('canonical Location Asset FBX is missing')
        if scope in ('changed', 'atlas'):
            if atlas_binding is None:
                raise ValueError('independent atlas binding missing')
            texture = self.root / str(row.get('texture_path') or '')
            if not texture.is_file():
                raise ValueError('canonical Location Asset texture is missing')
        api_key = str(credentials.get('apiKey') or '')
        creator_type = str(credentials.get('creatorType') or '')
        creator_id = str(credentials.get('creatorId') or '')
        description = str(credentials.get('description') or 'game1 location asset').strip() or 'game1 location asset'
        asset_name = str(row.get('name_en') or '').strip()
        if asset_name and asset_name.casefold() not in description.casefold():
            description = f'{description} · {asset_name}'

        needs_model = (str(row.get('model_published_sha256') or '') !=
                       str(row.get('model_sha256') or ''))
        if scope in ('changed', 'model') and (needs_model or force_model):
            # NEVER update_model_asset: versioned publication and the M217 audit
            # must retain an immutable chain of previous -> new Model IDs.
            # No embedded textures: the independent Atlas Registry alone publishes Image IDs.
            with staged_model(self.root, model, texture_mode="geometry_only") as publication:
                operation = create_model_asset(
                    publication, display_name=row['name_en'], description=description,
                    creator_type=creator_type, creator_id=creator_id, api_key=api_key)
            result = wait_for_operation(operation, api_key=api_key)
            now = time.time()
            with self.connect() as connection:
                connection.execute('''UPDATE location_assets
                    SET model_asset_id=?,model_published_sha256=?,model_moderation_state=?,
                        updated_at=?,published_at=? WHERE slug=?''',
                    (result.asset_id, row['model_sha256'], result.moderation_state or '', now, now, slug))
                connection.execute('''INSERT INTO location_asset_publications(
                    asset_slug,kind,revision,asset_id,operation_path,sha256,moderation_state,published_at
                ) VALUES(?,?,?,?,?,?,?,?)''',
                    (slug, 'model', int(row['revision']), result.asset_id, result.operation_path,
                     row['model_sha256'], result.moderation_state or '', now))

        if scope in ('changed', 'atlas') and atlas_binding is not None and not atlas_binding['current']:
            self.atlases.ensure_published(atlas_binding['variant_id'], credentials, description)

        self.export()
        return self.get(slug)

    def delete(self, slug: str, *, retain_shared: bool | None = None):
        """Retire the model registration, never the underlying published image.

        Atlas Registry entries and published Image Asset IDs survive.
        """
        normalized = str(slug or "").strip().lower()
        row = self.get(normalized)
        if not row:
            return {'ok': True}
        # Atlas variants have no model owner. Only this consumer is removed.
        with self.connect() as connection:
            raw = dict(connection.execute('SELECT * FROM location_assets WHERE slug=?', (normalized,)).fetchone())
            history = [dict(item) for item in connection.execute(
                'SELECT * FROM location_asset_publications WHERE asset_slug=? ORDER BY id',
                (normalized,))]
        archive = self.root / '.control-center' / 'location-assets-retired'
        archive.mkdir(parents=True, exist_ok=True)
        target = archive / (normalized + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        with target.open('x', encoding='utf-8') as file:
            json.dump({'asset': raw, 'publications': history, 'sourceFilesPreserved': True},
                      file, ensure_ascii=False, indent=2)
        with self.connect() as connection:
            connection.execute("DELETE FROM location_asset_publications WHERE asset_slug=?", (normalized,))
            connection.execute("DELETE FROM location_asset_mesh_id_inventory WHERE asset_slug=?", (normalized,))
            connection.execute("DELETE FROM location_assets WHERE slug=?", (normalized,))
        self.atlases.unbind('location_asset', normalized)
        self.export()
        return {'ok': True, 'sharedTextureRetained': True,
                'archived': target.relative_to(self.root).as_posix(),
                'sourceFilesPreserved': True}

    def publications(self, slug: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM location_asset_publications WHERE asset_slug=? ORDER BY id DESC",
                (str(slug or "").strip().lower(),),
            ).fetchall()
        return [dict(row) for row in rows]

    def model_publication_ids(self, slug: str) -> list[str]:
        """The immutable published Model Asset IDs; never infer MeshPart IDs from them."""
        if not SLUG_RE.fullmatch(slug):
            raise ValueError('invalid Location Asset slug')
        with self.connect() as db:
            rows = db.execute("SELECT asset_id FROM location_asset_publications "
                              "WHERE asset_slug=? AND kind='model' ORDER BY id DESC", (slug,)).fetchall()
        ids = list(dict.fromkeys(str(row['asset_id']) for row in rows))
        current = self.get(slug)
        if current and current.get('model_asset_id'):
            value = str(current['model_asset_id'])
            if value not in ids:
                ids.insert(0, value)
        return ids[:48]

    def record_mesh_id_inventory(self, slug: str, records: list[dict]) -> None:
        """Cache Studio-observed MeshPart IDs per immutable published Model version."""
        if not SLUG_RE.fullmatch(slug) or not isinstance(records, list) or len(records) > 48:
            raise ValueError('invalid MeshPart inventory')
        import re as _re
        observed = set()
        prepared = []
        for record in records:
            model_id = str(record.get('modelAssetId') or '')
            if not _re.fullmatch(r'[1-9][0-9]{0,19}', model_id) or model_id in observed:
                raise ValueError('invalid/duplicate published Model ID')
            observed.add(model_id)
            meshes = record.get('meshes')
            if not isinstance(meshes, list) or len(meshes) > 4096:
                raise ValueError('invalid MeshPart inventory size')
            mesh_ids = set()
            for item in meshes:
                mesh_id = str(item.get('meshId') or '')
                count = item.get('count')
                if (not _re.fullmatch(r'[1-9][0-9]{0,19}', mesh_id)
                        or mesh_id in mesh_ids or type(count) is not int or not 1 <= count <= 4096):
                    raise ValueError('invalid MeshPart ID or count')
                mesh_ids.add(mesh_id)
                names = item.get('visualNames', [])
                if (not isinstance(names,list) or len(names)>4096 or
                    any(not isinstance(name,str) or not 1 <= len(name) <= 128 for name in names) or
                    len(set(names)) != len(names)):
                    raise ValueError('invalid published visual MeshPart names')
            prepared.append((slug, model_id, json.dumps(meshes, separators=(',', ':')), time.time()))
        with self.connect() as db:
            db.executemany("INSERT INTO location_asset_mesh_id_inventory"
                           "(asset_slug,model_asset_id,meshes_json,observed_at) VALUES(?,?,?,?) "
                           "ON CONFLICT(asset_slug,model_asset_id) DO UPDATE SET "
                           "meshes_json=excluded.meshes_json,observed_at=excluded.observed_at", prepared)

    def mesh_id_inventory(self, slug: str) -> list[dict]:
        if not SLUG_RE.fullmatch(slug):
            raise ValueError('invalid Location Asset slug')
        with self.connect() as db:
            records = db.execute('SELECT model_asset_id,meshes_json FROM location_asset_mesh_id_inventory '
                                 'WHERE asset_slug=? ORDER BY observed_at DESC LIMIT 48', (slug,)).fetchall()
        return [{'modelAssetId': str(row['model_asset_id']), 'meshes': json.loads(row['meshes_json'])}
                for row in records]

    def snapshot(self) -> dict:
        items = self.list()
        with self.connect() as db:
            aliases = {row['old_slug']: row['current_slug'] for row in db.execute(
                'SELECT old_slug,current_slug FROM location_asset_slug_aliases ORDER BY old_slug')}
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "options": self.options(),
            "aliases": aliases,
            "atlases": self.atlases.catalog(),
            "items": items,
            "summary": {
                "registered": len(items),
                "published": sum(1 for item in items if item["status"] == "PUBLISHED"),
                "changed": sum(1 for item in items if item["status"] == "UPDATE_AVAILABLE"),
            },
        }

    @staticmethod
    def _lua_string(value: str) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    @staticmethod
    def _lua_value(value) -> str:
        if isinstance(value, dict):
            return 'table.freeze({' + ','.join('['+json.dumps(str(k))+']=' +
                LocationAssetStore._lua_value(v) for k,v in sorted(value.items())) + '})'
        if type(value) is bool:
            return 'true' if value else 'false'
        if value is None:
            return 'nil'
        return json.dumps(value, ensure_ascii=False)

    def export(self):
        snapshot = self.snapshot()
        manifest_path = self.root / "assets/manifests/location-assets.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        registry_path = self.root / "src/shared/world/LocationAssetRegistry.luau"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "-- generated. do not edit by hand.",
            "return table.freeze({",
            f"\tschemaVersion = {SCHEMA_VERSION},",
            '\tproject = "game1",',
            "\tassets = table.freeze({",
        ]
        for row in snapshot["items"]:
            lines.extend([
                f"\t\t[{self._lua_string(row['slug'])}] = table.freeze({{",
                f"\t\t\tslug = {self._lua_string(row['slug'])},",
                f"\t\t\tname = {self._lua_string(row['name_en'])},",
                f"\t\t\tcategory = {self._lua_string(row['category'])},",
                f"\t\t\tstatus = {self._lua_string(row['status'])},",
                f"\t\t\tmodelAssetId = {self._lua_string(row.get('model_asset_id') or '')},",
                f"\t\t\ttextureAssetId = {self._lua_string(row.get('texture_asset_id') or '')},",
                ("\t\t\ttextureUsesAlpha = " + (
                    "nil" if row.get('textureUsesAlpha') is None else
                    str(row['textureUsesAlpha']).lower()) + ","),
                f"\t\t\tatlasVariantId = {int(row.get('atlasVariantId') or 0)},",
                f"\t\t\tbindingRevision = {int(row.get('bindingRevision') or 0)},",
                f"\t\t\tdestructible = {str(bool(row.get('destructible'))).lower()},",
                f"\t\t\tmeshOptions = {self._lua_value(row.get('meshOptions') or {})},",
                "\t\t}),",
            ])
        lines.extend(["\t}),", "\taliases = table.freeze({"])
        for old_slug, new_slug in sorted(snapshot.get('aliases', {}).items()):
            lines.append(f"\t\t[{self._lua_string(old_slug)}] = {self._lua_string(new_slug)},")
        lines.extend(["\t}),", "})", ""])
        registry_path.write_text("\n".join(lines), encoding="utf-8")
