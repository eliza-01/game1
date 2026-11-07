"""Shared, content-verified atlas catalog. No consumer/model-specific publication IDs.

First consumer: Location Assets. All publication ownership lives on a variant;
consumer bindings contain only variant identity and an optimistic revision.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import threading
import tempfile
import time
import unicodedata
import uuid

from PIL import Image, UnidentifiedImageError

from sqlite_connection import connect as connect_sqlite
from services.texture_alpha import texture_uses_alpha
from opencloud_assets import create_image_asset, wait_for_operation

_NAME = re.compile(r"^(?P<key>[^\/\\:*?\"<>|\x00-\x1f]{1,96})_(?P<w>[1-9][0-9]*)x(?P<h>[1-9][0-9]*)_atlas\.(?P<ext>png|jpg|jpeg)$", re.I)
_SAFE_KEY = re.compile(r"^[\w][\w .-]{0,95}$", re.UNICODE)
_WINDOWS_RESERVED = {'con','prn','aux','nul', *(f'com{i}' for i in range(1,10)), *(f'lpt{i}' for i in range(1,10))}
_UPLOAD_LOCK = threading.RLock()
_ATLAS_VERSION = re.compile(r'^(?P<base>.+)_(?P<version>[0-9]{2,})$')


def atlas_version(key: str) -> tuple[str, str]:
    """Atlas revision is the rightmost _01/_02 suffix, not image resolution.

    Family identity still includes the revision. Legacy unversioned Location
    Assets remain valid, and no existing atlas IDs are re-keyed by this view.
    """
    match = _ATLAS_VERSION.fullmatch(str(key or ''))
    return (match['base'], match['version']) if match else (str(key or ''), '')


def same_atlas_series(current: str, candidate: str) -> bool:
    """Allow a deliberate Real Estate atlas revision change, not any family."""
    if current == candidate:
        return True
    current_base, current_version = atlas_version(current)
    candidate_base, candidate_version = atlas_version(candidate)
    return bool(current_version and candidate_version and current_base == candidate_base)



def parse_filename(name: str) -> dict | None:
    """Parse from right; a legacy name is None, not an exception."""
    if Path(str(name)).name != name:
        return None
    m = _NAME.fullmatch(str(name))
    if not m:
        return None
    w, h = int(m['w']), int(m['h'])
    if w > 16384 or h > 16384:
        raise ValueError('atlas dimensions must not exceed 16384 pixels')
    key = unicodedata.normalize('NFKC', m['key']).strip().casefold()
    if not _SAFE_KEY.fullmatch(key) or key.split('.')[0] in _WINDOWS_RESERVED:
        return None
    base, version = atlas_version(key)
    return {'atlasKey': key, 'baseKey': base, 'version': version, 'width': w, 'height': h,
            'extension': m['ext'].lower(), 'filename': str(name)}


def canonical_atlas_filename(path: Path, native_format: str, width: int, height: int) -> str:
    """One atlas filename contract for legacy registration and reviewed publication."""
    extension = '.png' if native_format in ('PNG', 'WEBP') else '.jpg'
    parsed = parse_filename(path.name)
    if parsed:
        accepted = {'.png'} if extension == '.png' else {'.jpg', '.jpeg'}
        return path.name if path.suffix.lower() in accepted else path.with_suffix(extension).name
    stem = path.stem
    if stem.casefold().endswith('_atlas'):
        stem = stem[:-6]
    stem = unicodedata.normalize('NFKC', stem).casefold()
    stem = re.sub(r'[^\w .-]+', '-', stem).strip(' .-_')[:96] or 'atlas'
    if stem.split('.')[0] in _WINDOWS_RESERVED:
        stem = ('atlas_' + stem)[:96]
    return f'{stem}_{width}x{height}_atlas{extension}'


def convert_webp_atlas_to_png(source: Path, destination: Path) -> None:
    """Shared lossless pixel decode; never copy WEBP bytes into a .png file."""
    with Image.open(source) as image:
        image.load()
        mode = 'RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB'
        image.convert(mode).save(destination, 'PNG')


def image_metadata(path: Path, parsed: dict) -> bool:
    try:
        with Image.open(path) as img:
            if img.format not in {'PNG', 'JPEG'}:
                raise ValueError('texture must be a real PNG or JPEG file')
            if img.size != (parsed['width'], parsed['height']):
                raise ValueError(f"atlas filename says {parsed['width']}x{parsed['height']}, "
                                 f"but image is {img.width}x{img.height}")
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f'cannot read atlas image: {exc}') from exc
    # Preserve unknown rather than silently changing alpha semantics.
    return bool(texture_uses_alpha(path.parent, path.name))


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


class AtlasRegistry:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.db = self.root / '.control-center/game1.db'
        with self.connect() as db:
            # M174 is an additive schema change. Keep a one-time online backup
            # of the existing DB before the first creation of the scope table.
            existing_scope = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='texture_atlas_scopes'").fetchone()
            if not existing_scope and self.db.is_file():
                backup_dir = self.db.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_file = backup_dir / ('before_character_atlas_scope_' + uuid.uuid4().hex + '.db')
                with connect_sqlite(backup_file) as target:
                    db.backup(target)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS texture_atlas_families (
                    id INTEGER PRIMARY KEY, atlas_key TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS texture_atlas_variants (
                    id INTEGER PRIMARY KEY,
                    family_id INTEGER NOT NULL REFERENCES texture_atlas_families(id),
                    width INTEGER NOT NULL CHECK(width>0), height INTEGER NOT NULL CHECK(height>0),
                    filename TEXT NOT NULL, original_filename TEXT NOT NULL,
                    source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                    uses_alpha INTEGER NOT NULL,
                    published_id TEXT, published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    published_at REAL, created_at REAL NOT NULL,
                    UNIQUE(family_id,width,height));
                CREATE TABLE IF NOT EXISTS texture_atlas_replacements (
                    variant_id INTEGER PRIMARY KEY REFERENCES texture_atlas_variants(id),
                    source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                    uses_alpha INTEGER NOT NULL, staged_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS texture_atlas_pending_uploads (
                    variant_id INTEGER PRIMARY KEY REFERENCES texture_atlas_variants(id),
                    source_sha256 TEXT NOT NULL,
                    operation_path TEXT NOT NULL DEFAULT '', started_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS texture_atlas_publications (
                    id INTEGER PRIMARY KEY, variant_id INTEGER NOT NULL REFERENCES texture_atlas_variants(id),
                    image_asset_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    operation_path TEXT NOT NULL, moderation_state TEXT NOT NULL,
                    published_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS texture_atlas_legacy_publications (
                    id INTEGER PRIMARY KEY, consumer_type TEXT NOT NULL,
                    consumer_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                    image_asset_id TEXT NOT NULL, imported_at REAL NOT NULL,
                    UNIQUE(consumer_type,consumer_id,source_sha256,image_asset_id));
                CREATE INDEX IF NOT EXISTS ix_legacy_atlas_sha
                    ON texture_atlas_legacy_publications(source_sha256);
                CREATE TABLE IF NOT EXISTS texture_atlas_scopes (
                    variant_id INTEGER PRIMARY KEY REFERENCES texture_atlas_variants(id),
                    scope TEXT NOT NULL CHECK(scope IN ('character')));
                CREATE TABLE IF NOT EXISTS texture_atlas_bindings (
                    consumer_type TEXT NOT NULL,
                    consumer_id TEXT NOT NULL,
                    variant_id INTEGER NOT NULL REFERENCES texture_atlas_variants(id),
                    revision INTEGER NOT NULL DEFAULT 1,
                    changed_at REAL NOT NULL,
                    synced_revision INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(consumer_type,consumer_id));
            ''')
            # Preserve publication history and immutable IDs when an atlas is retired.
            columns = {row[1] for row in db.execute('PRAGMA table_info(texture_atlas_variants)')}
            if 'retired_at' not in columns:
                backup_dir = self.db.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                with connect_sqlite(backup_dir / ('before_atlas_retirement_m223_' + uuid.uuid4().hex + '.db')) as target:
                    db.backup(target)
                db.execute('ALTER TABLE texture_atlas_variants ADD COLUMN retired_at REAL')
            db.execute('''CREATE TABLE IF NOT EXISTS texture_atlas_retirements (
                id INTEGER PRIMARY KEY,
                variant_id INTEGER NOT NULL,
                replacement_variant_id INTEGER,
                consumer_snapshot_json TEXT NOT NULL,
                retired_at REAL NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS texture_atlas_binding_migrations (
                id INTEGER PRIMARY KEY,
                retirement_id INTEGER NOT NULL REFERENCES texture_atlas_retirements(id),
                consumer_type TEXT NOT NULL,
                consumer_id TEXT NOT NULL,
                old_image_id TEXT NOT NULL,
                new_image_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                changed_at REAL NOT NULL)''')

        # M234: a consumer may offer several published atlases, but exactly
        # one remains the active Studio/runtime binding. Preserve existing IDs.
        with self.connect() as db:
            present = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='texture_atlas_consumer_options'").fetchone()
            if not present and self.db.is_file():
                backup_dir = self.db.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                with connect_sqlite(backup_dir / ('before_atlas_options_m234_' + uuid.uuid4().hex + '.db')) as backup:
                    db.backup(backup)
            db.execute("""CREATE TABLE IF NOT EXISTS texture_atlas_consumer_options (
                consumer_type TEXT NOT NULL, consumer_id TEXT NOT NULL,
                variant_id INTEGER NOT NULL REFERENCES texture_atlas_variants(id),
                added_at REAL NOT NULL,
                PRIMARY KEY (consumer_type,consumer_id,variant_id))""")

    def connect(self):
        return connect_sqlite(self.db)

    def import_legacy_publications(self, consumer_type: str, records: list[dict]) -> int:
        """Historical metadata import; never rewrites published IDs or live bindings."""
        imported = 0
        with self.connect() as db:
            for record in records:
                ident = str(record.get('id') or '')
                sha = str(record.get('sha256') or '')
                image_id = str(record.get('imageId') or '')
                if not ident or len(sha) != 64 or not image_id.isdigit():
                    continue
                cur = db.execute('''INSERT OR IGNORE INTO texture_atlas_legacy_publications
                    (consumer_type,consumer_id,source_sha256,image_asset_id,imported_at)
                    VALUES(?,?,?,?,?)''', (consumer_type,ident,sha,image_id,time.time()))
                imported += cur.rowcount
        return imported

    def get_variant(self, variant_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute('''SELECT v.*, f.atlas_key, r.source_sha256 AS replacement_sha256
                FROM texture_atlas_variants v
                JOIN texture_atlas_families f ON f.id=v.family_id
                LEFT JOIN texture_atlas_replacements r ON r.variant_id=v.id
                WHERE v.id=?''', (int(variant_id),)).fetchone()
        return self._variant(dict(row)) if row else None

    @staticmethod
    def _variant(row: dict) -> dict:
        row['retired'] = row.get('retired_at') is not None
        row['current'] = bool(not row['retired'] and row.get('published_id') and row['published_sha256'] == row['source_sha256'])
        row['replacementPending'] = bool(row.get('replacement_sha256') and row['replacement_sha256'] != row['source_sha256'])
        row['uses_alpha'] = bool(row.get('uses_alpha'))
        row['resolution'] = f"{row['width']}x{row['height']}"
        row['baseKey'], row['version'] = atlas_version(row['atlas_key'])
        return row

    def character_variant_ids(self) -> set[int]:
        """Explicit Character ownership plus existing Character bindings (legacy)."""
        with self.connect() as db:
            rows = db.execute("""SELECT variant_id FROM texture_atlas_scopes WHERE scope='character'
                UNION SELECT variant_id FROM texture_atlas_bindings WHERE consumer_type='character_part'""")
            return {int(row[0]) for row in rows}

    def catalog(self, search: str = '', *, domain: str | None = None) -> list[dict]:
        search = str(search or '').strip().lower()
        allowed = self.character_variant_ids() if domain == 'character' else None
        with self.connect() as db:
            rows = db.execute('''SELECT v.*, f.atlas_key, r.source_sha256 AS replacement_sha256
                FROM texture_atlas_variants v
                JOIN texture_atlas_families f ON f.id=v.family_id
                LEFT JOIN texture_atlas_replacements r ON r.variant_id=v.id
                WHERE v.retired_at IS NULL
                ORDER BY f.atlas_key, v.width*v.height DESC, v.width DESC, v.height DESC, v.id''').fetchall()
        result: dict[str, dict] = {}
        for row in rows:
            item = self._variant(dict(row))
            if allowed is not None and item['id'] not in allowed:
                continue
            if search and search not in item['atlas_key'] and search not in item['filename'].lower():
                continue
            group = result.setdefault(item['atlas_key'], {
                'atlasKey': item['atlas_key'], 'baseKey': item['baseKey'],
                'version': item['version'], 'variants': []})
            group['variants'].append(item)
        return list(result.values())

    def catalog_with_consumers(self, search: str = '') -> list[dict]:
        """Library view: one variant row, all consumer identities attached once.

        Consumer lookup is batched, avoiding a separate query for each atlas.
        The core catalog contract stays unchanged for existing workflows.
        """
        families = self.catalog(search)
        variants = {v['id']: v for f in families for v in f['variants']}
        with self.connect() as db:
            rows = db.execute('''SELECT variant_id,consumer_type,consumer_id
                FROM texture_atlas_bindings ORDER BY consumer_type,consumer_id''').fetchall()
        for variant in variants.values():
            variant['consumers'] = []
        for row in rows:
            variant = variants.get(row['variant_id'])
            if variant is not None:
                variant['consumers'].append({'consumer_type': row['consumer_type'],
                                             'consumer_id': row['consumer_id']})
        return families

    def binding(self, consumer_type: str, consumer_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute('''SELECT b.revision, b.synced_revision, b.changed_at,
                v.id AS variant_id, v.family_id, v.width, v.height, v.filename,
                v.original_filename, v.source_path, v.source_sha256, v.uses_alpha,
                v.published_id, v.published_sha256, v.moderation_state, v.published_at,
                f.atlas_key FROM texture_atlas_bindings b
                JOIN texture_atlas_variants v ON b.variant_id=v.id
                JOIN texture_atlas_families f ON f.id=v.family_id
                WHERE b.consumer_type=? AND b.consumer_id=?''', (consumer_type,consumer_id)).fetchone()
        if not row:
            return None
        result = self._variant(dict(row))
        result['syncStatus'] = ('synced' if result['synced_revision'] >= result['revision'] else 'pending_studio_sync')
        return result

    def consumers(self, variant_id: int) -> list[dict]:
        """All consumers of this published atlas resolution."""
        with self.connect() as db:
            rows = db.execute('''SELECT consumer_type,consumer_id,revision FROM texture_atlas_bindings
                WHERE variant_id=? ORDER BY consumer_type,consumer_id''', (int(variant_id),)).fetchall()
        return [dict(row) for row in rows]

    def retirement_plan(self, variant_id: int) -> dict:
        # Impact preview: retain publication/audit records.
        variant = self.get_variant(variant_id)
        if not variant or variant['retired']:
            raise ValueError('unknown active atlas variant')
        consumers = self.consumers(variant_id)
        with self.connect() as db:
            pending = db.execute('SELECT 1 FROM texture_atlas_pending_uploads WHERE variant_id=?', (variant_id,)).fetchone()
            staged = db.execute('SELECT 1 FROM texture_atlas_replacements WHERE variant_id=?', (variant_id,)).fetchone()
        if pending or staged or variant['replacementPending']:
            raise ValueError('resolve pending atlas upload or source replacement before retirement')
        candidates = [candidate for family in self.catalog() for candidate in family['variants']
                      if candidate['id'] != variant_id and candidate['current']]
        candidates.sort(key=lambda item: (0 if item['atlas_key'] == variant['atlas_key']
                                          else 1 if item['baseKey'] == variant['baseKey'] else 2,
                                          abs(item['width']*item['height']-variant['width']*variant['height']),
                                          item['atlas_key'], item['id']))
        # Automatic quality selection is safe ONLY within the same atlas key.
        # A similarly sized image of a different object is not a valid substitute.
        similar = [item for item in candidates if item['atlas_key'] == variant['atlas_key']]
        similar.sort(key=lambda v: (abs(math.log2((v['width'] * v['height']) /
                                  (variant['width'] * variant['height']))),
                                  abs(v['width']-variant['width']) + abs(v['height']-variant['height']), v['id']))
        suggested = similar[0]['id'] if similar else None
        identity = {'variantId': variant_id, 'publishedId': variant['published_id'],
                    'sourceSha256': variant['source_sha256'],
                    'consumers': [{'type': x['consumer_type'], 'id': x['consumer_id'],
                                   'revision': x['revision']} for x in consumers],
                    'candidates': [(v['id'], v['published_id'], v['source_sha256']) for v in candidates]}
        token = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return {'variant': variant, 'consumers': consumers, 'candidates': candidates,
                'suggestedReplacementId': suggested, 'token': token}

    def retire_variant(self, variant_id: int, *, token: str,
                       replacement_variant_id: int | None = None,
                       auto_closest: bool = False) -> dict:
        # Retire transactionally with stale-preview protection.
        # No original image bytes or historical publications are deleted.
        plan = self.retirement_plan(variant_id)
        if not token or token != plan['token']:
            raise ValueError('atlas uses changed; refresh the deletion warning')
        if auto_closest and replacement_variant_id is not None:
            raise ValueError('choose either automatic or manual replacement')
        target = plan['suggestedReplacementId'] if auto_closest else replacement_variant_id
        if target is not None and (type(target) is not int or target == variant_id or
                not any(item['id'] == target for item in plan['candidates'])):
            raise ValueError('replacement must be a different, current published atlas')
        if auto_closest and target is None:
            raise ValueError('no published atlas in the same family at another resolution')
        if plan['consumers'] and target is None:
            raise ValueError('this atlas is in use; choose a replacement first')
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('''SELECT published_id,source_sha256,retired_at
                FROM texture_atlas_variants WHERE id=?''', (variant_id,)).fetchone()
            actual = [dict(row) for row in db.execute('''SELECT consumer_type,consumer_id,revision
                FROM texture_atlas_bindings WHERE variant_id=? ORDER BY consumer_type,consumer_id''', (variant_id,))]
            # Publication/source replacement can start while the confirmation
            # modal is open. Recheck both under the same write lock.
            in_flight = db.execute('''SELECT 1 FROM texture_atlas_pending_uploads WHERE variant_id=?''',
                                   (variant_id,)).fetchone()
            staged_source = db.execute('''SELECT 1 FROM texture_atlas_replacements WHERE variant_id=?''',
                                       (variant_id,)).fetchone()
            if (not current or current['retired_at'] is not None or
                current['published_id'] != plan['variant']['published_id'] or
                current['source_sha256'] != plan['variant']['source_sha256'] or
                actual != plan['consumers'] or in_flight or staged_source):
                raise ValueError('atlas changed while reviewing; refresh and try again')
            if target is not None:
                replacement = db.execute('''SELECT published_id,source_sha256,published_sha256,retired_at
                    FROM texture_atlas_variants WHERE id=?''', (target,)).fetchone()
                selected = next(item for item in plan['candidates'] if item['id'] == target)
                if (not replacement or replacement['retired_at'] is not None or not replacement['published_id']
                        or replacement['source_sha256'] != replacement['published_sha256']
                        or str(replacement['published_id']) != str(selected['published_id'])
                        or replacement['source_sha256'] != selected['source_sha256']):
                    raise ValueError('replacement atlas changed; refresh and confirm again')
                db.execute('''UPDATE texture_atlas_bindings SET variant_id=?,revision=revision+1,
                    changed_at=? WHERE variant_id=?''', (target, now, variant_id))
            db.execute('UPDATE texture_atlas_variants SET retired_at=? WHERE id=?', (now, variant_id))
            cursor = db.execute('''INSERT INTO texture_atlas_retirements
                (variant_id,replacement_variant_id,consumer_snapshot_json,retired_at)
                VALUES(?,?,?,?)''', (variant_id, target, json.dumps(actual, sort_keys=True), now))
            if target is not None:
                for consumer in actual:
                    db.execute('''INSERT INTO texture_atlas_binding_migrations
                        (retirement_id,consumer_type,consumer_id,old_image_id,new_image_id,revision,changed_at)
                        VALUES(?,?,?,?,?,?,?)''', (
                        cursor.lastrowid, consumer['consumer_type'], consumer['consumer_id'],
                        str(current['published_id'] or ''), str(replacement['published_id']),
                        consumer['revision'] + 1, now))
        return {'retiredVariantId': variant_id, 'replacementVariantId': target,
                'consumersRebound': len(actual), 'studioSyncRequired': bool(actual),
                'sourceFilesPreserved': True}

    def adopt_file(self, source_path: str, *, domain: str = 'location') -> dict:
        """Bring a new image into Atlas Registry, never a model-owned PNG.

        Model registration cannot implicitly replace an existing atlas. A
        different image requires an explicit Registry republish operation.
        """
        path = Path(str(source_path)).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            raise ValueError('select a PNG/JPG/WebP atlas file')
        # The native image format, not the filename extension, determines how
        # the source must be staged. Blender/export tools can leave WebP bytes
        # inside a .png file; copying those bytes into a .png registry source
        # later makes register_file reject an otherwise decodable texture.
        try:
            with Image.open(path) as image:
                native_format = image.format
                width, height = image.size
                if native_format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise ValueError('texture must be a real PNG or JPEG file, or a WebP image '
                                     f'(detected {native_format or "unknown"} in {path.name})')
                if width > 16384 or height > 16384:
                    raise ValueError('atlas dimensions must not exceed 16384 pixels')
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f'cannot read atlas image {path.name}: {exc}') from exc
        # Never save PNG bytes under a JPEG suffix or vice versa. WebP is
        # decoded losslessly to PNG; existing PNG/JPEG bytes are left intact.
        filename = canonical_atlas_filename(path, native_format, width, height)
        key = parse_filename(filename)['atlasKey']
        with tempfile.TemporaryDirectory(prefix='game1-atlas-register-') as temporary:
            staged = Path(temporary) / filename
            if native_format == 'WEBP':
                try:
                    convert_webp_atlas_to_png(path, staged)
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                    raise ValueError(f'cannot convert WebP atlas {path.name} to PNG: {exc}') from exc
            else:
                shutil.copy2(path, staged)
            sha = digest(staged)
            with self.connect() as db:
                existing = db.execute('''SELECT v.id,v.source_sha256,v.retired_at FROM texture_atlas_variants v
                    JOIN texture_atlas_families f ON f.id=v.family_id
                    WHERE f.atlas_key=? AND v.width=? AND v.height=?''',
                    (key, width, height)).fetchone()
            if existing:
                if existing['retired_at'] is not None:
                    raise ValueError('this atlas resolution was retired; use a new atlas key')
                if existing['source_sha256'] != sha:
                    raise ValueError(f'{key} {width}x{height}: another image exists; '
                                     'replace/republish explicitly in Atlas Registry')
                return self.get_variant(existing['id'])
            return self.register_file(str(staged), domain=domain)

    def register_file(self, source_path: str, *, domain: str = 'location') -> dict:
        if domain not in ('location', 'character'):
            raise ValueError('unsupported atlas registration domain')
        path = Path(str(source_path)).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
            raise ValueError('select a PNG/JPG atlas file')
        parsed = parse_filename(path.name)
        if not parsed:
            raise ValueError('new atlas filename must follow <atlas_key>_<width>x<height>_atlas.png')
        alpha = image_metadata(path, parsed)
        sha = digest(path)
        with _UPLOAD_LOCK:
            with self.connect() as db:
                now = time.time()
                db.execute('INSERT OR IGNORE INTO texture_atlas_families(atlas_key,created_at) VALUES(?,?)',
                           (parsed['atlasKey'], now))
                family_id = db.execute('SELECT id FROM texture_atlas_families WHERE atlas_key=?',
                                       (parsed['atlasKey'],)).fetchone()[0]
                existing = db.execute('SELECT id,source_sha256,retired_at FROM texture_atlas_variants WHERE family_id=? AND width=? AND height=?',
                                      (family_id, parsed['width'], parsed['height'])).fetchone()
                if existing:
                    if existing['retired_at'] is not None:
                        raise ValueError('this atlas resolution was retired; use a new atlas key')
                    variant_id = existing['id']
                    claimed = db.execute('SELECT scope FROM texture_atlas_scopes WHERE variant_id=?',
                                         (variant_id,)).fetchone()
                    character_bound = db.execute("""SELECT 1 FROM texture_atlas_bindings
                        WHERE variant_id=? AND consumer_type='character_part' LIMIT 1""", (variant_id,)).fetchone()
                    if domain == 'character' and not (claimed and claimed['scope'] == 'character') and not character_bound:
                        raise ValueError('this atlas name/resolution belongs to another section; choose a unique Character atlas name')
                    if domain != 'character' and claimed and claimed['scope'] == 'character':
                        raise ValueError('this atlas belongs to Characters; choose another atlas name')
                    unresolved = db.execute('SELECT 1 FROM texture_atlas_pending_uploads WHERE variant_id=?',
                                            (variant_id,)).fetchone()
                    if existing['source_sha256'] == sha:
                        if not unresolved:
                            db.execute('DELETE FROM texture_atlas_replacements WHERE variant_id=?', (variant_id,))
                        db.commit()
                        return self.get_variant(variant_id)
                    if unresolved:
                        raise ValueError('previous atlas upload is unresolved; cannot replace its source')
                    # Content-addressed archive. Do not overwrite the old version.
                    directory = (self.root / 'assets/source/texture-atlases' / parsed['atlasKey']
                                 / f"{parsed['width']}x{parsed['height']}" / 'revisions' / sha)
                    directory.mkdir(parents=True, exist_ok=True)
                    destination = directory / parsed['filename']
                    if destination.is_file() and digest(destination) != sha:
                        raise ValueError('stored replacement source checksum mismatch')
                    if not destination.exists():
                        shutil.copy2(path, destination)
                    db.execute('''INSERT INTO texture_atlas_replacements
                        (variant_id,source_path,source_sha256,uses_alpha,staged_at) VALUES (?,?,?,?,?)
                        ON CONFLICT(variant_id) DO UPDATE SET source_path=excluded.source_path,
                        source_sha256=excluded.source_sha256,uses_alpha=excluded.uses_alpha,
                        staged_at=excluded.staged_at''',
                        (variant_id,destination.relative_to(self.root).as_posix(),sha,int(alpha),now))
                    db.commit()
                    return self.get_variant(variant_id)
                directory = self.root / 'assets/source/texture-atlases' / parsed['atlasKey'] / f"{parsed['width']}x{parsed['height']}"
                directory.mkdir(parents=True, exist_ok=True)
                destination = directory / parsed['filename']
                if destination.exists() and digest(destination) != sha:
                    raise ValueError('atlas source destination already has different pixels')
                if not destination.exists():
                    # Never overwrite a stored source, including on repeat registration.
                    shutil.copy2(path, destination)
                rel = destination.relative_to(self.root).as_posix()
                cursor = db.execute('''INSERT INTO texture_atlas_variants (
                    family_id,width,height,filename,original_filename,source_path,
                    source_sha256,uses_alpha,created_at) VALUES (?,?,?,?,?,?,?,?,?)''',
                    (family_id,parsed['width'],parsed['height'],parsed['filename'],path.name,
                     rel,sha,int(alpha),now))
                variant_id = cursor.lastrowid
                if domain == 'character':
                    db.execute('INSERT INTO texture_atlas_scopes(variant_id,scope) VALUES(?,?)',
                               (variant_id, 'character'))
            return self.get_variant(variant_id)

    def attached_variants(self, consumer_type: str, consumer_id: str) -> list[dict]:
        """Shared picker collection; current family variants stay visible for legacy consumers."""
        active = self.binding(consumer_type, consumer_id)
        with self.connect() as db:
            rows = db.execute("""SELECT v.id FROM texture_atlas_variants v
                LEFT JOIN texture_atlas_consumer_options o ON o.variant_id=v.id
                    AND o.consumer_type=? AND o.consumer_id=?
                WHERE v.retired_at IS NULL AND (o.variant_id IS NOT NULL
                    OR v.family_id=(SELECT family_id FROM texture_atlas_variants WHERE id=?))
                ORDER BY v.width*v.height DESC,v.id""",
                (consumer_type, consumer_id, int(active['variant_id']) if active else -1)).fetchall()
        return [variant for r in rows if (variant:=self.get_variant(r['id'])) is not None]

    def attach(self, consumer_type: str, consumer_id: str, variant_id: int) -> list[dict]:
        """Offer a published atlas without changing the effective Image ID or Studio."""
        variant = self.get_variant(variant_id)
        if not variant or not variant['current']:
            raise ValueError('choose a published atlas variant')
        if not consumer_type or not consumer_id:
            raise ValueError('atlas consumer required')
        with self.connect() as db:
            db.execute("""INSERT OR IGNORE INTO texture_atlas_consumer_options
                (consumer_type,consumer_id,variant_id,added_at) VALUES(?,?,?,?)""",
                (consumer_type,consumer_id,int(variant_id),time.time()))
        return self.attached_variants(consumer_type,consumer_id)

    def bind(self, consumer_type: str, consumer_id: str, variant_id: int, *, expected_revision: int | None = None,
             allow_unpublished: bool = False) -> dict:
        with self.connect() as db:
            db.execute('PRAGMA foreign_keys=ON')
            if not consumer_type or not consumer_id:
                raise ValueError('atlas binding consumer identity is required')
            variant = db.execute('SELECT id,published_id,published_sha256,source_sha256 FROM texture_atlas_variants WHERE id=?',
                                 (int(variant_id),)).fetchone()
            if not variant:
                raise ValueError('unknown atlas variant')
            if db.execute('SELECT retired_at FROM texture_atlas_variants WHERE id=?', (int(variant_id),)).fetchone()[0] is not None:
                raise ValueError('retired atlas cannot be selected')
            if not allow_unpublished and (not variant['published_id'] or variant['published_sha256'] != variant['source_sha256']):
                raise ValueError('atlas variant must be published before selecting it')
            old = db.execute('SELECT variant_id,revision FROM texture_atlas_bindings WHERE consumer_type=? AND consumer_id=?', (consumer_type,consumer_id)).fetchone()
            revision = int(old['revision']) if old else 0
            if expected_revision is not None and int(expected_revision) != revision:
                raise ValueError('stale atlas binding revision; refresh the asset list')
            db.execute("""INSERT OR IGNORE INTO texture_atlas_consumer_options
                (consumer_type,consumer_id,variant_id,added_at) VALUES(?,?,?,?)""",
                (consumer_type,consumer_id,int(variant_id),time.time()))
            if old and old['variant_id'] == int(variant_id):
                return self.binding(consumer_type,consumer_id)
            db.execute('''INSERT INTO texture_atlas_bindings(consumer_type,consumer_id,variant_id,revision,changed_at)
                VALUES(?,?,?,?,?) ON CONFLICT(consumer_type,consumer_id) DO UPDATE SET
                variant_id=excluded.variant_id, revision=excluded.revision, changed_at=excluded.changed_at''',
                (consumer_type,consumer_id,int(variant_id),revision+1,time.time()))
        return self.binding(consumer_type,consumer_id)

    def unbind(self, consumer_type: str, consumer_id: str) -> None:
        with self.connect() as db:
            db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type=? AND consumer_id=?',
                       (consumer_type, consumer_id))
            db.execute('DELETE FROM texture_atlas_consumer_options WHERE consumer_type=? AND consumer_id=?',
                       (consumer_type, consumer_id))

    def active_revisions(self, consumer_type: str, consumer_id: str | None = None) -> dict[str, int]:
        with self.connect() as db:
            if consumer_id:
                rows = db.execute('SELECT consumer_id,revision FROM texture_atlas_bindings WHERE consumer_type=? AND consumer_id=?', (consumer_type,consumer_id))
            else:
                rows = db.execute('SELECT consumer_id,revision FROM texture_atlas_bindings WHERE consumer_type=?', (consumer_type,))
            return {row[0]: row[1] for row in rows}

    def mark_synced(self, consumer_type: str, consumer_id: str, revision: int) -> bool:
        with self.connect() as db:
            cur = db.execute('''UPDATE texture_atlas_bindings SET synced_revision=?
                WHERE consumer_type=? AND consumer_id=? AND revision=? AND synced_revision<?''',
                (int(revision),consumer_type,consumer_id,int(revision),int(revision)))
            return cur.rowcount > 0

    def mark_all_synced(self, consumer_type: str, revisions: dict[str, int]) -> None:
        for consumer_id, revision in revisions.items():
            self.mark_synced(consumer_type, consumer_id, revision)

    def publish_initial(self, variant_id: int, credentials: dict, description: str) -> dict:
        """Publish only a never-published variant; never replace a shared atlas.

        Enforce the invariant under the SAME upload lock as ensure_published,
        avoiding a race between checking current ID and the actual upload.
        """
        with _UPLOAD_LOCK:
            variant = self.get_variant(variant_id)
            if not variant or variant['retired']:
                raise ValueError('atlas variant is unavailable')
            if variant.get('published_id'):
                raise ValueError('atlas already has an Image ID; use explicit shared atlas review for replacement')
            if variant.get('replacementPending'):
                raise ValueError('shared atlas replacement requires explicit review')
            return self.ensure_published(variant_id, credentials, description)

    def ensure_published(self, variant_id: int, credentials: dict, description: str) -> dict:
        """Publish a new variant or a replacement as a NEW Roblox Image Asset ID.

        No image reimport. Previously published IDs and sources remain in history.
        All consumers move to the new ID only after a successful publication.
        """
        with _UPLOAD_LOCK:
            variant = self.get_variant(variant_id)
            if not variant:
                raise ValueError('unknown atlas variant')
            if variant['retired']:
                raise ValueError('retired atlas cannot be published')
            with self.connect() as db:
                replacement = db.execute('SELECT * FROM texture_atlas_replacements WHERE variant_id=?',
                                         (variant_id,)).fetchone()
                pending = db.execute('SELECT 1 FROM texture_atlas_pending_uploads WHERE variant_id=?',
                                     (variant_id,)).fetchone()
            if pending:
                raise ValueError('atlas publication is unresolved; inspect Open Cloud operation before retrying (upload blocked)')
            if variant['current'] and not replacement:
                return variant

            new_path = replacement['source_path'] if replacement else variant['source_path']
            new_sha = replacement['source_sha256'] if replacement else variant['source_sha256']
            path = (self.root / new_path).resolve()
            if not path.is_relative_to(self.root) or not path.is_file() or digest(path) != new_sha:
                raise ValueError('atlas source missing or changed; refusing to publish')
            # Deduplicate genuinely identical bytes, never by matching filename.
            with self.connect() as db:
                ids = {r[0] for r in db.execute('''SELECT published_id FROM texture_atlas_variants
                    WHERE source_sha256=? AND published_sha256=? AND published_id IS NOT NULL''', (new_sha,new_sha))}
                ids |= {r[0] for r in db.execute('''SELECT image_asset_id
                    FROM texture_atlas_legacy_publications WHERE source_sha256=?''', (new_sha,))}
                if len(ids) > 1:
                    raise ValueError('legacy atlas publication conflict: multiple Image Asset IDs for identical bytes; choose canonical ID explicitly before continuing (no upload performed)')
                adopted = next(iter(ids)) if ids else None
            if adopted:
                operation_path, moderation = 'reuse:published-sha256', ''
            else:
                if not (credentials.get('apiKey') and credentials.get('creatorType') and credentials.get('creatorId')):
                    raise ValueError('Open Cloud credentials required to publish an atlas')
                # Persist upload intent before contacting Roblox. Never retry an
                # ambiguous upload until reconciled by its operation ID.
                with self.connect() as db:
                    db.execute('INSERT INTO texture_atlas_pending_uploads(variant_id,source_sha256,started_at) VALUES(?,?,?)',
                               (variant_id,new_sha,time.time()))
                op = create_image_asset(path, display_name=variant['atlas_key'] + ' atlas ' + variant['resolution'],
                    description=description, creator_type=str(credentials.get('creatorType') or ''),
                    creator_id=str(credentials.get('creatorId') or ''), api_key=str(credentials.get('apiKey') or ''))
                with self.connect() as db:
                    db.execute('UPDATE texture_atlas_pending_uploads SET operation_path=? WHERE variant_id=?',
                               (str(op),variant_id))
                result = wait_for_operation(op, api_key=str(credentials.get('apiKey') or ''))
                adopted, operation_path, moderation = result.asset_id, result.operation_path, result.moderation_state or ''
            if not str(adopted).isdigit() or int(adopted) <= 0:
                raise ValueError('Open Cloud returned an invalid Image Asset ID')
            if replacement and str(adopted) == str(variant['published_id']):
                raise ValueError('replacement must receive a different Roblox Image Asset ID')
            with self.connect() as db:
                now = time.time()
                if replacement:
                    db.execute('''UPDATE texture_atlas_variants SET source_path=?,source_sha256=?,uses_alpha=?,
                        published_id=?,published_sha256=?,moderation_state=?,published_at=? WHERE id=?''',
                        (new_path,new_sha,int(replacement['uses_alpha']),str(adopted),new_sha,moderation,now,variant_id))
                    # Updating a shared variant invalidates every consumer's
                    # acknowledgement, in Location Assets AND Real Estate.
                    db.execute('''UPDATE texture_atlas_bindings SET revision=revision+1,changed_at=?
                        WHERE variant_id=?''', (now,variant_id))
                    db.execute('DELETE FROM texture_atlas_replacements WHERE variant_id=?', (variant_id,))
                else:
                    db.execute('''UPDATE texture_atlas_variants SET published_id=?,published_sha256=?,
                        moderation_state=?,published_at=? WHERE id=?''',
                        (str(adopted),new_sha,moderation,now,variant_id))
                db.execute('''INSERT INTO texture_atlas_publications
                    (variant_id,image_asset_id,sha256,operation_path,moderation_state,published_at)
                    VALUES(?,?,?,?,?,?)''',
                    (variant_id,str(adopted),new_sha,operation_path,moderation,now))
                db.execute('DELETE FROM texture_atlas_pending_uploads WHERE variant_id=?', (variant_id,))
            return self.get_variant(variant_id)
