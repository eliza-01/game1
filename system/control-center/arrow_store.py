"""Arrow model publication and ballistic speed authoring (not a second weapon store).

A versioned arrow is a cosmetic template + speed policy. Damage and collision
remain owned by the existing AttackService/BowProjectileService.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import sqlite3
import time

from model_publication_service import staged_model
from opencloud_assets import (
    create_model_asset, update_model_asset, create_image_asset,
    update_image_asset, wait_for_operation,
)

SLUG = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
SPEED_MIN, SPEED_MAX = 20.0, 500.0
AXES = ("-Z", "+Z", "+X", "-X", "+Y", "-Y")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class ArrowStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.db = self.root / ".control-center" / "game1.db"
        self.atlases = None  # shared registry injected by composition root
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS arrow_assets (
                slug TEXT PRIMARY KEY, name TEXT NOT NULL, speed REAL NOT NULL DEFAULT 145,
                forward_axis TEXT NOT NULL DEFAULT '-Z', source_path TEXT NOT NULL,
                sha256 TEXT NOT NULL, model_asset_id TEXT NOT NULL DEFAULT '',
                published_sha256 TEXT NOT NULL DEFAULT '',
                texture_path TEXT NOT NULL DEFAULT '', texture_sha256 TEXT NOT NULL DEFAULT '',
                texture_asset_id TEXT NOT NULL DEFAULT '', texture_published_sha256 TEXT NOT NULL DEFAULT '',
                moderation_state TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
                penetration_studs REAL NOT NULL DEFAULT 0.12,
                updated_at REAL NOT NULL, published_at REAL
            )""")
            # Additive authoring migration; published IDs and existing rows survive.
            columns = {item[1] for item in conn.execute('PRAGMA table_info(arrow_assets)')}
            if 'penetration_studs' not in columns:
                conn.execute('ALTER TABLE arrow_assets ADD COLUMN penetration_studs REAL NOT NULL DEFAULT 0.12')
            conn.execute("""CREATE TABLE IF NOT EXISTS arrow_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS arrow_publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL,
                kind TEXT NOT NULL, asset_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                operation_path TEXT NOT NULL, created_at REAL NOT NULL
            )""")
        self.export()

    def connect(self):
        db = sqlite3.connect(self.db)
        db.row_factory = sqlite3.Row
        return db

    def get(self, slug: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM arrow_assets WHERE slug=?", (slug,)).fetchone()
        return self.decorate(dict(row)) if row else None

    def atlas_binding(self, slug):
        if self.atlases is None:
            return None
        binding = self.atlases.binding('arrow', slug)
        if binding:
            binding['id'] = binding['variant_id']  # UI variant row identity from shared Registry
        return binding

    def select_atlas(self, slug: str, variant_id: int, expected_revision: int):
        if not self.get(slug):
            raise ValueError('unknown arrow for atlas selection')
        if self.atlases is None:
            raise ValueError('shared atlas registry is unavailable')
        self.atlases.bind('arrow', slug, variant_id, expected_revision=expected_revision)
        self.export()
        return self.get(slug)

    def clear_atlas(self, slug: str):
        if not self.get(slug):
            raise ValueError('unknown arrow')
        self.atlases.unbind('arrow', slug)
        self.export()
        return self.get(slug)

    def decorate(self, row):
        row['atlas_binding'] = self.atlas_binding(row['slug'])
        row['atlas_variants'] = self.atlases.attached_variants('arrow', row['slug']) if self.atlases else []
        published = bool(row['model_asset_id'] and row['published_sha256'] == row['sha256'])
        if row['texture_path'] and not row['atlas_binding']:
            published = published and bool(row['texture_asset_id'] and row['texture_published_sha256'] == row['texture_sha256'])
        if row['atlas_binding'] and not row['atlas_binding']['current']:
            published = False
        row['status'] = 'PUBLISHED' if published else 'UPDATE_AVAILABLE' if row['model_asset_id'] else 'LOCAL_ONLY'
        row['server_storage_path'] = f"ServerStorage.arrows.{row['slug']}.model.{row['slug']}"
        return row

    def list(self):
        with self.connect() as conn:
            rows = conn.execute('SELECT * FROM arrow_assets ORDER BY name,slug').fetchall()
        return [self.decorate(dict(row)) for row in rows]

    def active_slug(self):
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM arrow_settings WHERE key='active_arrow'").fetchone()
        return row['value'] if row else ''

    def snapshot(self):
        return dict(schemaVersion=1, project='game1', items=self.list(), activeArrowSlug=self.active_slug(),
                    options=dict(minSpeed=SPEED_MIN, maxSpeed=SPEED_MAX, forwardAxes=list(AXES)))

    def register(self, data: dict):
        slug = str(data.get('slug') or '').lower().strip()
        name = str(data.get('name') or '').strip()
        if not SLUG.fullmatch(slug) or not name:
            raise ValueError('arrow requires a name and lowercase snake_case slug')
        old = self.get(slug)
        if old and str(data.get('slug') or '') != slug:
            raise ValueError('arrow slug cannot change')
        speed = float(data.get('speed', old['speed'] if old else 145))
        if not math.isfinite(speed) or not (SPEED_MIN <= speed <= SPEED_MAX):
            raise ValueError(f'arrow speed must be between {SPEED_MIN:g} and {SPEED_MAX:g} studs/s')
        penetration = float(data.get('penetrationStuds', old['penetration_studs'] if old else 0.12))
        if not math.isfinite(penetration) or not (0 <= penetration <= 3):
            raise ValueError('arrow penetration must be 0..3 studs')
        axis = str(data.get('forwardAxis') or (old['forward_axis'] if old else '-Z'))
        if axis not in AXES:
            raise ValueError('invalid arrow forward axis')
        source = str(data.get('modelSourcePath') or '').strip()
        texture = str(data.get('textureSourcePath') or '').strip()
        if not old and not source:
            raise ValueError('choose an FBX model for the arrow')
        now = time.time()
        revision = int(old['revision']) + 1 if old else 1

        def stage(raw, extension_set, folder, name):
            incoming = Path(raw).expanduser().resolve()
            if not incoming.is_file() or incoming.suffix.lower() not in extension_set:
                raise ValueError(f'invalid arrow {folder} file')
            dest = self.root / 'assets/source/arrows' / slug / folder / (name + incoming.suffix.lower())
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_file() and sha(dest) != sha(incoming):
                backup = self.root / 'assets/reimported/arrows' / slug / f'r{revision-1:04d}' / folder / dest.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup)
            if incoming != dest:
                shutil.copy2(incoming, dest)
            return dest.relative_to(self.root).as_posix(), sha(dest)

        source_path, source_sha = (stage(source, {'.fbx'}, 'model', slug) if source else
                                   (old['source_path'], old['sha256']))
        texture_path, texture_sha = (stage(texture, {'.png', '.jpg', '.jpeg'}, 'texture', slug) if texture else
                                     (old['texture_path'], old['texture_sha256']) if old else ('', ''))
        with self.connect() as conn:
            conn.execute('''INSERT OR REPLACE INTO arrow_assets(
                slug,name,speed,forward_axis,source_path,sha256,model_asset_id,published_sha256,
                texture_path,texture_sha256,texture_asset_id,texture_published_sha256,moderation_state,
                revision,updated_at,published_at,penetration_studs) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (slug, name, speed, axis, source_path, source_sha, old['model_asset_id'] if old else '',
                 old['published_sha256'] if old else '', texture_path, texture_sha,
                 old['texture_asset_id'] if old else '', old['texture_published_sha256'] if old else '',
                 old['moderation_state'] if old else '', revision, now, old['published_at'] if old else None, penetration))
        self.export()
        return self.get(slug)

    def publish(self, slug: str, credentials: dict, *, include_legacy_textures: bool = True):
        row = self.get(slug)
        if not row:
            raise ValueError('unknown arrow')
        params = dict(creator_type=credentials['creatorType'], creator_id=credentials['creatorId'],
                      api_key=credentials['apiKey'], description=credentials.get('description') or f'Game1 arrow {slug}',
                      display_name=row['name'])
        if not row['model_asset_id'] or row['sha256'] != row['published_sha256']:
            file = self.root / row['source_path']
            if not file.is_file() or sha(file) != row['sha256']:
                raise ValueError('arrow source FBX is missing or has changed')
            with staged_model(self.root, file) as publication:
                if row['model_asset_id']:
                    operation = update_model_asset(publication, asset_id=row['model_asset_id'], **params)
                else:
                    operation = create_model_asset(publication, **params)
            result = wait_for_operation(operation, api_key=credentials['apiKey'])
            self._record(slug, 'model', result, row['sha256'])
            with self.connect() as conn:
                conn.execute('''UPDATE arrow_assets SET model_asset_id=?,published_sha256=?,moderation_state=?,published_at=? WHERE slug=?''',
                             (result.asset_id, row['sha256'], result.moderation_state or '', time.time(), slug))
            row = self.get(slug)
        if include_legacy_textures and not row.get('atlas_binding') and row['texture_path'] and (not row['texture_asset_id'] or row['texture_sha256'] != row['texture_published_sha256']):
            file = self.root / row['texture_path']
            if not file.is_file() or sha(file) != row['texture_sha256']:
                raise ValueError('arrow texture is missing or changed')
            if row['texture_asset_id']:
                operation = update_image_asset(file, asset_id=row['texture_asset_id'], **params)
            else:
                operation = create_image_asset(file, **params)
            result = wait_for_operation(operation, api_key=credentials['apiKey'])
            self._record(slug, 'texture', result, row['texture_sha256'])
            with self.connect() as conn:
                conn.execute('''UPDATE arrow_assets SET texture_asset_id=?,texture_published_sha256=? WHERE slug=?''',
                             (result.asset_id, row['texture_sha256'], slug))
        self.export()
        return self.get(slug)

    def _record(self, slug, kind, result, digest):
        with self.connect() as conn:
            conn.execute('INSERT INTO arrow_publications(slug,kind,asset_id,sha256,operation_path,created_at) VALUES(?,?,?,?,?,?)',
                         (slug,kind,result.asset_id,digest,result.operation_path,time.time()))

    def activate(self, slug):
        row = self.get(str(slug))
        if not row or row['status'] != 'PUBLISHED':
            raise ValueError('publish arrow model/texture before activating it')
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO arrow_settings(key,value) VALUES('active_arrow',?)", (slug,))
        self.export()
        return self.snapshot()

    def export(self):
        snap = self.snapshot()
        path = self.root / 'assets/manifests/arrows.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snap, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        # JSONDecode here avoids hand-rolled Luau escaping and preserves exact authoring values.
        data = {'schemaVersion': 1, 'activeArrowSlug': snap['activeArrowSlug'],
                'arrows': {r['slug']: {'slug':r['slug'], 'speed':r['speed'], 'status':r['status'],
                            'forwardAxis':r['forward_axis'], 'penetrationStuds':r['penetration_studs'],
                            'atlasVariantId':int(r['atlas_binding']['id']) if r.get('atlas_binding') else 0,
                            'textureAssetId':(r['atlas_binding']['published_id'] if r.get('atlas_binding') else r['texture_asset_id']),
                            'modelAssetId':r['model_asset_id'],
                            'serverStoragePath':r['server_storage_path']} for r in snap['items']}}
        registry = self.root / 'src/shared/weapon/ArrowRegistry.luau'
        registry.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        depth = '='
        while ']' + depth + ']' in serialized: depth += '='
        registry.write_text('-- generated from assets/manifests/arrows.json; do not edit by hand.\n'
                            'local HttpService = game:GetService("HttpService")\n'
                            + 'return table.freeze(HttpService:JSONDecode([' + depth + '['
                            + serialized + ']' + depth + ']))\n', encoding='utf-8')
