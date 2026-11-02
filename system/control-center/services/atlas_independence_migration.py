"""One-way atlas ownership migration: model registrations become consumers only.

The Atlas Registry is the sole texture source/publication authority. This is a
transactional, idempotent upgrade across the authoring databases; it handles
unpublished images, historical owner references and retired owner snapshots.
It does not re-upload anything or infer two distinct Roblox publications from
image bytes. No owner slug is retained as a runtime atlas identity.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import hashlib
import json
import re
import shutil
import sqlite3
import time
import uuid

from PIL import Image

from services.texture_atlas_registry import parse_filename
from real_estate.publication_textures import published_format


def _backup(path: Path) -> Path:
    folder = path.parent / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f'before_m203_atlas_independence_{uuid.uuid4().hex}.db'
    with closing(sqlite3.connect(str(path))) as source, closing(sqlite3.connect(str(output))) as dest:
        source.backup(dest)
    return output


def _source(root: Path, row: dict, ref: str) -> dict:
    raw = str(row.get('path') or row.get('texture_path') or '')
    path = (root / raw).resolve()
    if not raw or not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f'{ref}: atlas source missing/outside project: {raw}')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    recorded = str(row.get('sha256') or row.get('texture_sha256') or '')
    if recorded and sha != recorded:
        raise ValueError(f'{ref}: atlas source SHA-256 changed; migration stopped')
    image_id = str(row.get('assetId') or row.get('texture_asset_id') or '').strip()
    published_sha = str(row.get('publishedSha256') or row.get('texture_published_sha256') or '')
    if image_id and (not image_id.isdigit() or (published_sha and published_sha != sha)):
        raise ValueError(f'{ref}: published texture differs from source; migration stopped')
    filename = Path(str(row.get('filename') or row.get('texture_filename') or path.name)).name
    with Image.open(path) as image:
        width, height = image.size
        alpha = image.mode in ('RGBA', 'LA', 'PA') or 'transparency' in image.info
        image.verify()
    parsed = parse_filename(filename)
    if parsed and (parsed['width'], parsed['height']) != (width, height):
        raise ValueError(f'{ref}: atlas filename dimensions disagree with image data')
    key = parsed['atlasKey'] if parsed else Path(filename).stem.casefold()
    if not parsed and key.endswith('_atlas'):
        key = key[:-6]
    key = re.sub(r'[^\w .-]+', '-', key).strip(' .-_')[:96] or 'atlas'
    if key.split('.')[0] in {'con','prn','aux','nul', *(f'com{i}' for i in range(1,10)), *(f'lpt{i}' for i in range(1,10))}:
        key = ('atlas_' + key)[:96]
    # Pin source outside any potentially reused model slug. The source file is
    # copied *before* the database transaction and verified byte-for-byte.
    dest = (root / 'assets/source/texture-atlases' / key / f'{width}x{height}'
            / 'migrated' / sha / filename)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file():
        shutil.copy2(path, dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
        raise ValueError(f'{ref}: atlas archive verification failed')
    return dict(key=key, width=width, height=height, filename=filename,
                path=dest.relative_to(root).as_posix(), sha=sha, image_id=image_id,
                alpha=int(bool(alpha)), format=published_format(path),
                moderation=str(row.get('moderation_state') or row.get('texture_moderation_state') or ''))


def _variant(db, data, now):
    """Never coalesce two different published Image IDs, even for equal pixels."""
    row = db.execute('''SELECT v.id FROM texture_atlas_variants v
        LEFT JOIN texture_atlas_scopes s ON s.variant_id=v.id
        WHERE v.source_sha256=? AND COALESCE(v.published_id,'')=?
          AND v.published_sha256=? AND s.variant_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM texture_atlas_bindings b
                          WHERE b.variant_id=v.id AND b.consumer_type='character_part')
        ORDER BY v.id LIMIT 1''', (data['sha'], data['image_id'], data['sha'] if data['image_id'] else '')).fetchone()
    if row:
        return row['id']
    base = data['key']
    for index in range(1000):
        suffix = '' if index == 0 else '__import_' + data['sha'][:9] + ('_' + str(index) if index > 1 else '')
        key = base[:96-len(suffix)] + suffix
        db.execute('INSERT OR IGNORE INTO texture_atlas_families(atlas_key,created_at) VALUES(?,?)', (key,now))
        family = db.execute('SELECT id FROM texture_atlas_families WHERE atlas_key=?', (key,)).fetchone()['id']
        found = db.execute('''SELECT v.*,s.scope FROM texture_atlas_variants v
            LEFT JOIN texture_atlas_scopes s ON s.variant_id=v.id
            WHERE v.family_id=? AND v.width=? AND v.height=?''', (family,data['width'],data['height'])).fetchone()
        if not found:
            cur = db.execute('''INSERT INTO texture_atlas_variants
                (family_id,width,height,filename,original_filename,source_path,source_sha256,
                uses_alpha,published_id,published_sha256,moderation_state,published_at,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (family,data['width'],data['height'],data['filename'],data['filename'],data['path'],
                 data['sha'],data['alpha'],data['image_id'] or None,data['sha'] if data['image_id'] else '',
                 data['moderation'],now if data['image_id'] else None,now))
            return cur.lastrowid
        if (found['source_sha256'] == data['sha'] and (found['published_id'] or '') == data['image_id']
                and found['published_sha256'] == (data['sha'] if data['image_id'] else '')
                and not found['scope']):
            return found['id']
    raise ValueError('unable to allocate independent atlas publication identity')


class AtlasIndependenceMigration:
    def __init__(self, real_estate, location_assets):
        self.estate = real_estate
        self.location = location_assets
        self.root = real_estate.root
        self.main = self.root / '.control-center/game1.db'
        self.houses = self.root / '.control-center/game1_real_estate.db'

    def migrate(self):
        with closing(sqlite3.connect(str(self.main))) as db:
            db.row_factory = sqlite3.Row
            locations = {r['slug']:dict(r) for r in db.execute('SELECT * FROM location_assets')}
            bound = {(r['consumer_type'],r['consumer_id']):r['variant_id'] for r in db.execute(
                'SELECT consumer_type,consumer_id,variant_id FROM texture_atlas_bindings')}
            legacy_columns = {r[1] for r in db.execute('PRAGMA table_info(location_assets)')}
            obsolete_columns = {'texture_path','texture_filename','texture_sha256','texture_asset_id',
                'texture_published_sha256','texture_moderation_state','texture_reference_slug'} & legacy_columns
            existing_variants = [dict(r) for r in db.execute('SELECT * FROM texture_atlas_variants')]
            retained = {}
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='retained_shared_textures'").fetchone():
                retained = {r['reference']:json.loads(r['snapshot_json']) for r in db.execute(
                    'SELECT reference,snapshot_json FROM retained_shared_textures')}
        with closing(sqlite3.connect(str(self.houses))) as db:
            db.row_factory = sqlite3.Row
            houses = {r['slug']:json.loads(r['textures_json'] or '{}') for r in db.execute(
                'SELECT slug,textures_json FROM real_estate')}

        def source_for(ref, visited=None):
            visited = set(visited or ())
            if ref in visited:
                raise ValueError('cyclic atlas ownership: ' + ref)
            visited.add(ref)
            if ref.startswith('location:'):
                slug = ref.split(':',1)[1]
                if ('location_asset',slug) in bound:
                    return ('bound',bound['location_asset',slug])
                row = locations.get(slug) or retained.get(ref)
                if row is None:
                    raise ValueError(f'{ref}: missing historical atlas owner')
                redirect = str(row.get('texture_reference_slug') or '')
                return source_for('location:'+redirect, visited) if redirect else ('source',ref,row)
            if ref.startswith('estate:'):
                _,slug,part = ref.split(':',2)
                if ('real_estate',f'{slug}:{part}') in bound:
                    return ('bound',bound['real_estate',f'{slug}:{part}'])
                row = houses.get(slug,{}).get(part) or retained.get(ref)
                if row is None:
                    raise ValueError(f'{ref}: missing historical atlas owner')
                redirect = str(row.get('reuseReference') or '')
                if redirect == 'mesh:house':
                    redirect = f'estate:{slug}:house'
                return source_for(redirect, visited) if redirect else ('source',ref,row)
            if ref.startswith('atlas:'):
                variant = int(ref[6:])
                if not self.estate.atlases.get_variant(variant):
                    raise ValueError('unknown shared atlas variant: '+ref)
                return ('bound',variant)
            raise ValueError('unknown atlas reference: ' + ref)

        consumers = {}
        for slug,row in locations.items():
            if ('location_asset',slug) in bound:
                continue
            if row.get('texture_reference_slug'):
                ref = 'location:'+str(row['texture_reference_slug'])
            elif row.get('texture_path'):
                ref = 'location:'+slug
            else:
                continue  # deliberately texture-less draft
            consumers[('location_asset',slug)] = source_for(ref)
        for slug,textures in houses.items():
            for part,row in textures.items():
                if ('real_estate',f'{slug}:{part}') in bound:
                    continue
                ref = str(row.get('reuseReference') or '')
                if ref == 'mesh:house':
                    ref = f'estate:{slug}:house'
                elif not ref and row.get('path'):
                    ref = f'estate:{slug}:{part}'
                if ref:
                    consumers[('real_estate',f'{slug}:{part}')] = source_for(ref)
        # Tombstoned owners are no longer model registrations. Archive their
        # image even when the last consumer was already retired.
        for ref,row in retained.items():
            if ref not in [value[1] for value in consumers.values() if value[0]=='source']:
                source_for(ref)  # fail explicitly on corrupt retained records
        refs = {value[1]: value[2] for value in consumers.values() if value[0]=='source'}
        refs.update({ref:row for ref,row in retained.items() if ref not in refs and source_for(ref)[0]=='source'})
        # Delete obsolete owner bindings for retired registrations; no ghost
        # binding may attach to a future registration of the same slug.
        stale = [(kind, ident) for kind,ident in bound if
                 (kind == 'location_asset' and ident not in locations) or
                 (kind == 'real_estate' and (':' not in ident or
                    ident.split(':',1)[0] not in houses or ident.split(':',1)[1] not in houses[ident.split(':',1)[0]]))]
        # Historical central registry rows may still point into a deleted model
        # slug. Move every source into the independent source namespace too.
        rewrites = {}
        for variant in existing_variants:
            raw = str(variant['source_path'] or '')
            if raw.startswith('assets/source/texture-atlases/'):
                continue
            original = (self.root / raw).resolve()
            if not original.is_relative_to(self.root) or not original.is_file():
                raise ValueError(f'central atlas {variant["id"]}: legacy source missing: {raw}')
            sha = hashlib.sha256(original.read_bytes()).hexdigest()
            if sha != variant['source_sha256']:
                raise ValueError(f'central atlas {variant["id"]}: source checksum mismatch')
            atlas = _source(self.root, {"texture_path":raw,"texture_filename":variant['original_filename'],
                "texture_sha256":sha}, f"atlas:{variant['id']}")
            rewrites[variant['id']] = atlas['path']
        if not consumers and not retained and not stale and not obsolete_columns and not rewrites:
            return dict(bindings=0, independentAtlases=0, retiredSources=0, archivedVariants=0)
        # Preflight sources before any DB mutation. Failure preserves all
        # original registration rows and prevents reuse of unsafe slugs.
        imported = {ref:_source(self.root,row,ref) for ref,row in sorted(refs.items())}
        _backup(self.main)
        _backup(self.houses)
        db = sqlite3.connect(str(self.main))
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            db.execute('ATTACH DATABASE ? AS estate_db', (str(self.houses),))
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            for variant_id, canonical in rewrites.items():
                db.execute('UPDATE texture_atlas_variants SET source_path=? WHERE id=?',
                           (canonical, variant_id))
            ids = {ref:_variant(db,data,now) for ref,data in imported.items()}
            count = 0
            for (kind,ident),source in consumers.items():
                variant_id = source[1] if source[0]=='bound' else ids[source[1]]
                db.execute('''INSERT INTO texture_atlas_bindings
                    (consumer_type,consumer_id,variant_id,revision,changed_at)
                    VALUES(?,?,?,?,?)''',(kind,ident,variant_id,1,now))
                if kind != 'location_asset':
                    slug,part=ident.split(':',1)
                    textures = houses[slug]
                    textures[part] = {'reuseReference':'','path':'','filename':'','sha256':'',
                                     'assetId':'','publishedSha256':'','publicationFormat':''}
                count += 1
            for slug,textures in houses.items():
                for part,texture in list(textures.items()):
                    if ('real_estate',f'{slug}:{part}') in bound or ('real_estate',f'{slug}:{part}') in consumers:
                        textures[part] = {'reuseReference':'','path':'','filename':'','sha256':'',
                                          'assetId':'','publishedSha256':'','publicationFormat':''}
                db.execute('UPDATE estate_db.real_estate SET textures_json=? WHERE slug=?',
                           (json.dumps(textures,ensure_ascii=False),slug))
            for kind,ident in stale:
                db.execute('DELETE FROM texture_atlas_bindings WHERE consumer_type=? AND consumer_id=?',(kind,ident))
            for name in sorted(obsolete_columns):
                db.execute('ALTER TABLE location_assets DROP COLUMN ' + name)
            db.execute('DROP TABLE IF EXISTS retained_shared_textures')
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        self.location.export()
        self.estate.export()
        return dict(bindings=count,independentAtlases=len(set(ids.values())),retiredSources=len(retained),archivedVariants=len(rewrites))
