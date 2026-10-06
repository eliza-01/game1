from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import shutil
import sqlite3
import time

from opencloud_assets import (
    create_image_asset,
    create_model_asset,
    update_image_asset,
    update_model_asset,
    wait_for_operation,
)

SCHEMA_VERSION = 1
PROJECT = "game1"
ACTIVE_KEY = "active_weapon_slug"
WEAPON_TYPES = ("1hs", "2hs", "bow")
RARITIES = ("common", "uncommon", "rare", "mythical", "legendary", "immortal")
TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
STAT_KEYS = ("Damage", "AttackSpeed")
ATTACK_RADIUS_DEFAULT = 7.0
ATTACK_RADIUS_MIN = 1.0
ATTACK_RADIUS_MAX = 420.0
ATTACK_RADIUS_STEP = 0.5
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


def slugify_english(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        raise ValueError("english name must contain latin letters or digits so a slug can be generated")
    if len(text) > 64:
        text = text[:64].rstrip("_")
    if not SLUG_RE.fullmatch(text):
        raise ValueError("generated weapon slug is invalid")
    return text


def _safe_texture_slot(path: Path) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    return (value or "texture")[:64]


class WeaponStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runtime = self.root / ".control-center"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.db = self.runtime / "game1.db"
        self._init()
        self.export()

    def connect(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS weapons(
                    slug TEXT PRIMARY KEY,
                    name_en TEXT NOT NULL,
                    name_ru TEXT NOT NULL DEFAULT '',
                    weapon_type TEXT NOT NULL,
                    rarity TEXT NOT NULL,
                    attack_radius_studs REAL NOT NULL DEFAULT 7,
                    model_source_path TEXT NOT NULL DEFAULT '',
                    model_prepared_path TEXT NOT NULL DEFAULT '',
                    model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,
                    model_published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS weapon_textures(
                    id TEXT PRIMARY KEY,
                    weapon_slug TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    prepared_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    asset_id TEXT,
                    published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL,
                    UNIQUE(weapon_slug, slot)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS weapon_stat_modifiers(
                    weapon_slug TEXT NOT NULL,
                    stat_key TEXT NOT NULL,
                    delta REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY(weapon_slug, stat_key)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS weapon_publications(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    weapon_slug TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    slot TEXT NOT NULL DEFAULT '',
                    weapon_revision INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,
                    operation_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    moderation_state TEXT,
                    published_at REAL NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_settings(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                )"""
            )
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(weapons)")}
            if "attack_radius_studs" not in columns:
                connection.execute(
                    "ALTER TABLE weapons ADD COLUMN attack_radius_studs REAL NOT NULL DEFAULT 7"
                )
            connection.execute("DELETE FROM project_settings WHERE key='test_loadout_weapon'")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def options(self):
        return {
            "weaponTypes": list(WEAPON_TYPES),
            "rarities": list(RARITIES),
            "statKeys": list(STAT_KEYS),
            "attackRadius": {
                "default": ATTACK_RADIUS_DEFAULT,
                "min": ATTACK_RADIUS_MIN,
                "max": ATTACK_RADIUS_MAX,
                "step": ATTACK_RADIUS_STEP,
            },
        }

    def active_slug(self) -> str | None:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM project_settings WHERE key=?", (ACTIVE_KEY,)).fetchone()
        value = str(row["value"] if row else "").strip()
        return value or None

    def set_active(self, slug: str):
        slug = str(slug or "").strip().lower()
        row = self.get(slug)
        if not row:
            raise ValueError(f"unknown weapon: {slug}")
        if not str(row.get("model_asset_id") or "").isdigit():
            raise ValueError("publish the weapon model before setting it as the startup weapon")
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO project_settings(key,value) VALUES(?,?)", (ACTIVE_KEY, slug))
        self.export()
        return self.snapshot()

    def clear_active(self):
        with self.connect() as connection:
            connection.execute("DELETE FROM project_settings WHERE key=?", (ACTIVE_KEY,))
        self.export()
        return self.snapshot()

    def _modifiers(self, connection, slug: str) -> dict[str, float]:
        rows = connection.execute(
            "SELECT stat_key,delta FROM weapon_stat_modifiers WHERE weapon_slug=? ORDER BY stat_key", (slug,)
        ).fetchall()
        result = {}
        for row in rows:
            value = float(row["delta"])
            if value.is_integer():
                value = int(value)
            result[str(row["stat_key"])] = value
        return result

    def _textures(self, connection, slug: str) -> list[dict]:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM weapon_textures WHERE weapon_slug=? ORDER BY slot", (slug,)
        )]

    def _status(self, row: dict, textures: list[dict]) -> str:
        if not str(row.get("model_source_path") or ""):
            return "INCOMPLETE"
        model_asset = str(row.get("model_asset_id") or "")
        model_current = bool(model_asset and str(row.get("model_published_sha256") or "") == str(row.get("model_sha256") or ""))
        textures_current = all(
            str(item.get("asset_id") or "")
            and str(item.get("published_sha256") or "") == str(item.get("sha256") or "")
            for item in textures
        )
        if model_current and textures_current:
            return "PUBLISHED"
        any_published = bool(model_asset or any(str(item.get("asset_id") or "") for item in textures))
        return "UPDATE_AVAILABLE" if any_published else "LOCAL_ONLY"

    def _decorate(self, connection, row) -> dict:
        result = dict(row)
        result["textures"] = self._textures(connection, result["slug"])
        result["stat_modifiers"] = self._modifiers(connection, result["slug"])
        result["status"] = self._status(result, result["textures"])
        result["server_storage_path"] = (
            f"ServerStorage.weapons.{result['weapon_type']}.{result['slug']}.model.{result['slug']}"
        )
        return result

    def list(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM weapons ORDER BY weapon_type,rarity,name_en,slug").fetchall()
            return [self._decorate(connection, row) for row in rows]

    def get(self, slug: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM weapons WHERE slug=?", (str(slug or "").strip().lower(),)).fetchone()
            return self._decorate(connection, row) if row else None

    def _validate_identity(self, payload: dict, old: dict | None = None) -> tuple[str, str, str, str, str]:
        name_en = str(payload.get("nameEn", old.get("name_en") if old else "") or "").strip()
        name_ru = str(payload.get("nameRu", old.get("name_ru") if old else "") or "").strip()
        if not name_en:
            raise ValueError("english weapon name is required")
        slug = str(payload.get("slug") or (old.get("slug") if old else "") or "").strip().lower()
        if not slug:
            slug = slugify_english(name_en)
        if not SLUG_RE.fullmatch(slug):
            raise ValueError("weapon slug must be lowercase snake_case")
        weapon_type = str(payload.get("weaponType", old.get("weapon_type") if old else "") or "").strip().lower()
        rarity = str(payload.get("rarity", old.get("rarity") if old else "") or "").strip().lower()
        if weapon_type not in WEAPON_TYPES:
            raise ValueError("weapon type must be 1hs, 2hs or bow")
        if rarity not in RARITIES:
            raise ValueError("rarity must be common, uncommon, rare, mythical, legendary or immortal")
        return slug, name_en, name_ru, weapon_type, rarity

    def _archive_existing(self, path: Path, slug: str, revision: int):
        if not path.is_file():
            return
        relative = path.resolve().relative_to(self.root)
        tail = relative.parts[-2:]
        destination = self.root / "assets/reimported/weapons" / slug / f"r{revision:04d}" / Path(*tail)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)

    def register(self, payload: dict) -> dict:
        incoming_slug = str(payload.get("slug") or "").strip().lower()
        old = self.get(incoming_slug) if incoming_slug else None
        slug, name_en, name_ru, weapon_type, rarity = self._validate_identity(payload, old)
        attack_radius_raw = payload.get("attackRadiusStuds", old.get("attack_radius_studs") if old else ATTACK_RADIUS_DEFAULT)
        try:
            attack_radius_studs = float(attack_radius_raw)
        except (TypeError, ValueError):
            raise ValueError("attack radius must be a number in Roblox studs")
        if not (ATTACK_RADIUS_MIN <= attack_radius_studs <= ATTACK_RADIUS_MAX):
            raise ValueError(
                f"attack radius must be between {ATTACK_RADIUS_MIN:g} and {ATTACK_RADIUS_MAX:g} studs"
            )
        attack_radius_studs = round(attack_radius_studs, 2)
        if not old:
            old = self.get(slug)
        model_source = str(payload.get("modelSourcePath") or "").strip()
        texture_paths = [str(value).strip() for value in (payload.get("texturePaths") or []) if str(value).strip()]
        if not old and not model_source:
            raise ValueError("choose a weapon FBX before registration")

        now = time.time()
        revision = int(old.get("revision") or 0) + 1 if old else 1
        model_source_path = str(old.get("model_source_path") or "") if old else ""
        model_prepared_path = str(old.get("model_prepared_path") or "") if old else ""
        model_sha256 = str(old.get("model_sha256") or "") if old else ""

        if model_source:
            source = Path(model_source).expanduser().resolve()
            if not source.is_file() or source.suffix.lower() != ".fbx":
                raise ValueError("weapon model must be an FBX file")
            source_target = self.root / "assets/source/weapons" / weapon_type / slug / "model" / f"{slug}.fbx"
            prepared_target = self.root / "assets/prepared/weapons" / weapon_type / slug / "model" / f"{slug}.fbx"
            for target in (source_target, prepared_target):
                target.parent.mkdir(parents=True, exist_ok=True)
                if old:
                    self._archive_existing(target, slug, int(old.get("revision") or 1))
                shutil.copy2(source, target)
            model_source_path = source_target.relative_to(self.root).as_posix()
            model_prepared_path = prepared_target.relative_to(self.root).as_posix()
            model_sha256 = self._sha256(prepared_target)

        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO weapons(
                    slug,name_en,name_ru,weapon_type,rarity,attack_radius_studs,model_source_path,model_prepared_path,model_sha256,
                    model_asset_id,model_published_sha256,moderation_state,revision,created_at,updated_at,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    slug, name_en, name_ru, weapon_type, rarity, attack_radius_studs, model_source_path, model_prepared_path, model_sha256,
                    old.get("model_asset_id") if old else None,
                    str(old.get("model_published_sha256") or "") if old else "",
                    str(old.get("moderation_state") or "") if old else "",
                    revision,
                    old.get("created_at") if old else now,
                    now,
                    old.get("published_at") if old else None,
                ),
            )

            modifiers = payload.get("statModifiers") or {}
            for key in STAT_KEYS:
                if key in modifiers or not old:
                    delta = float(modifiers.get(key) or 0)
                    connection.execute(
                        "INSERT OR REPLACE INTO weapon_stat_modifiers(weapon_slug,stat_key,delta) VALUES(?,?,?)",
                        (slug, key, delta),
                    )

            for raw in texture_paths:
                source = Path(raw).expanduser().resolve()
                if not source.is_file() or source.suffix.lower() not in TEXTURE_EXTENSIONS:
                    raise ValueError(f"weapon texture must be png/jpg/jpeg/webp: {source.name}")
                slot = _safe_texture_slot(source)
                texture_id = f"{slug}__{slot}"
                previous = connection.execute("SELECT * FROM weapon_textures WHERE id=?", (texture_id,)).fetchone()
                canonical_name = f"{slot}{source.suffix.lower()}"
                source_target = self.root / "assets/source/weapons" / weapon_type / slug / "textures" / canonical_name
                prepared_target = self.root / "assets/prepared/weapons" / weapon_type / slug / "textures" / canonical_name
                source_target.parent.mkdir(parents=True, exist_ok=True)
                prepared_target.parent.mkdir(parents=True, exist_ok=True)
                if previous:
                    self._archive_existing(source_target, slug, int(previous["revision"] or 1))
                    self._archive_existing(prepared_target, slug, int(previous["revision"] or 1))
                shutil.copy2(source, source_target)
                shutil.copy2(source, prepared_target)
                digest = self._sha256(prepared_target)
                texture_revision = int(previous["revision"] or 0) + 1 if previous else 1
                connection.execute(
                    """INSERT OR REPLACE INTO weapon_textures(
                        id,weapon_slug,slot,source_path,prepared_path,sha256,asset_id,published_sha256,
                        moderation_state,revision,created_at,updated_at,published_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        texture_id, slug, slot,
                        source_target.relative_to(self.root).as_posix(),
                        prepared_target.relative_to(self.root).as_posix(),
                        digest,
                        previous["asset_id"] if previous else None,
                        str(previous["published_sha256"] or "") if previous else "",
                        str(previous["moderation_state"] or "") if previous else "",
                        texture_revision,
                        previous["created_at"] if previous else now,
                        now,
                        previous["published_at"] if previous else None,
                    ),
                )

        self.export()
        return self.get(slug)

    def publish(self, slug: str, credentials: dict) -> dict:
        row = self.get(slug)
        if not row:
            raise ValueError(f"unknown weapon: {slug}")
        model = self.root / str(row.get("model_prepared_path") or "")
        if not model.is_file():
            raise ValueError("canonical prepared weapon FBX is missing")
        api_key = str(credentials.get("apiKey") or "")
        creator_type = str(credentials.get("creatorType") or "")
        creator_id = str(credentials.get("creatorId") or "")
        description = str(credentials.get("description") or "game1 weapon").strip()

        current_asset_id = str(row.get("model_asset_id") or "").strip()
        if current_asset_id:
            operation = update_model_asset(
                model, asset_id=current_asset_id, display_name=row["name_en"], description=description,
                creator_type=creator_type, creator_id=creator_id, api_key=api_key,
            )
        else:
            operation = create_model_asset(
                model, display_name=row["name_en"], description=description,
                creator_type=creator_type, creator_id=creator_id, api_key=api_key,
            )
        result = wait_for_operation(operation, api_key=api_key)
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                """UPDATE weapons SET model_asset_id=?,model_published_sha256=?,moderation_state=?,published_at=?,updated_at=?
                   WHERE slug=?""",
                (result.asset_id, row["model_sha256"], result.moderation_state or "", now, now, slug),
            )
            connection.execute(
                """INSERT INTO weapon_publications(
                    weapon_slug,kind,slot,weapon_revision,asset_id,operation_path,sha256,moderation_state,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (slug, "model", "", int(row["revision"]), result.asset_id, result.operation_path,
                 row["model_sha256"], result.moderation_state or "", now),
            )

        row = self.get(slug)
        for texture in row.get("textures") or []:
            if str(texture.get("asset_id") or "") and str(texture.get("published_sha256") or "") == str(texture.get("sha256") or ""):
                continue
            file_path = self.root / str(texture.get("prepared_path") or "")
            texture_asset = str(texture.get("asset_id") or "").strip()
            display_name = f"{row['name_en']} {texture['slot']}"
            if texture_asset:
                operation = update_image_asset(
                    file_path, asset_id=texture_asset, display_name=display_name, description=description,
                    creator_type=creator_type, creator_id=creator_id, api_key=api_key,
                )
            else:
                operation = create_image_asset(
                    file_path, display_name=display_name, description=description,
                    creator_type=creator_type, creator_id=creator_id, api_key=api_key,
                )
            result = wait_for_operation(operation, api_key=api_key)
            now = time.time()
            with self.connect() as connection:
                connection.execute(
                    """UPDATE weapon_textures SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?,updated_at=? WHERE id=?""",
                    (result.asset_id, texture["sha256"], result.moderation_state or "", now, now, texture["id"]),
                )
                connection.execute(
                    """INSERT INTO weapon_publications(
                        weapon_slug,kind,slot,weapon_revision,asset_id,operation_path,sha256,moderation_state,published_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (slug, "texture", texture["slot"], int(row["revision"]), result.asset_id,
                     result.operation_path, texture["sha256"], result.moderation_state or "", now),
                )

        self.export()
        return self.get(slug)

    def delete(self, slug: str):
        slug = str(slug or "").strip().lower()
        if not self.get(slug):
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM weapon_stat_modifiers WHERE weapon_slug=?", (slug,))
            connection.execute("DELETE FROM weapon_textures WHERE weapon_slug=?", (slug,))
            connection.execute("DELETE FROM weapon_publications WHERE weapon_slug=?", (slug,))
            connection.execute("DELETE FROM weapons WHERE slug=?", (slug,))
            current = connection.execute("SELECT value FROM project_settings WHERE key=?", (ACTIVE_KEY,)).fetchone()
            if current and str(current["value"]) == slug:
                connection.execute("DELETE FROM project_settings WHERE key=?", (ACTIVE_KEY,))
        self.export()

    def publications(self, slug: str) -> list[dict]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM weapon_publications WHERE weapon_slug=? ORDER BY id DESC", (slug,)
            )]

    def snapshot(self) -> dict:
        items = self.list()
        active = self.active_slug()
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "activeWeaponSlug": active,
            "options": self.options(),
            "items": items,
            "summary": {
                "registered": len(items),
                "published": sum(1 for item in items if item["status"] == "PUBLISHED"),
                "active": 1 if active else 0,
            },
        }

    @staticmethod
    def _lua_string(value: str) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    @staticmethod
    def _lua_number(value) -> str:
        number = float(value or 0)
        return str(int(number)) if number.is_integer() else repr(number)

    def export(self):
        snapshot = self.snapshot()
        manifest_path = self.root / "assets/manifests/weapons.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        registry_path = self.root / "src/shared/weapon/WeaponRegistry.luau"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "-- generated. do not edit by hand.",
            "return table.freeze({",
            f"\tschemaVersion = {SCHEMA_VERSION},",
            '\tproject = "game1",',
            f"\tactiveWeaponSlug = {self._lua_string(snapshot.get('activeWeaponSlug') or '')},",
            "\tweapons = table.freeze({",
        ]
        for row in snapshot["items"]:
            lines.extend([
                f"\t\t[{self._lua_string(row['slug'])}] = table.freeze({{",
                f"\t\t\tslug = {self._lua_string(row['slug'])},",
                f"\t\t\tnameEn = {self._lua_string(row['name_en'])},",
                f"\t\t\tnameRu = {self._lua_string(row['name_ru'])},",
                f"\t\t\tweaponType = {self._lua_string(row['weapon_type'])},",
                f"\t\t\trarity = {self._lua_string(row['rarity'])},",
                f"\t\t\tattackRadiusStuds = {self._lua_number(row.get('attack_radius_studs') or ATTACK_RADIUS_DEFAULT)},",
                f"\t\t\tstatus = {self._lua_string(row['status'])},",
                f"\t\t\tmodelAssetId = {self._lua_string(row.get('model_asset_id') or '')},",
                f"\t\t\tserverStoragePath = {self._lua_string(row['server_storage_path'])},",
                "\t\t\tstatModifiers = table.freeze({",
            ])
            for key, value in sorted((row.get("stat_modifiers") or {}).items()):
                lines.append(f"\t\t\t\t[{self._lua_string(key)}] = {self._lua_number(value)},")
            lines.extend(["\t\t\t}),", "\t\t\ttextures = table.freeze({"])
            for texture in row.get("textures") or []:
                lines.extend([
                    f"\t\t\t\t[{self._lua_string(texture['slot'])}] = table.freeze({{",
                    f"\t\t\t\t\tassetId = {self._lua_string(texture.get('asset_id') or '')},",
                    f"\t\t\t\t\tsha256 = {self._lua_string(texture.get('sha256') or '')},",
                    "\t\t\t\t}),",
                ])
            lines.extend(["\t\t\t}),", "\t\t}),"])
        lines.extend(["\t}),", "})", ""])
        registry_path.write_text("\n".join(lines), encoding="utf-8")
