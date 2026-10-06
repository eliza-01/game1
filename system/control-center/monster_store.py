from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import time
import unicodedata

from character_analysis import analyze_character_fbx, prepare_character_publication_fbx
from character_store import _assert_publication_skeleton_matches
from opencloud_assets import (
    create_image_asset,
    create_model_asset,
    update_image_asset,
    update_model_asset,
    wait_for_operation,
)

SCHEMA_VERSION = 1
PROJECT = "game1"
TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
STAT_KEYS = ("MaxHP", "Damage", "AttackSpeed", "RunSpeed", "CritChance")
DEFAULT_STATS = {
    "MaxHP": 100,
    "Damage": 10,
    "AttackSpeed": 100,
    "RunSpeed": 50,
    "CritChance": 0,
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


CYRILLIC_SLUG_MAP = str.maketrans({
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
    "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
    "х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
})


def slugify_english(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").strip().lower()).translate(CYRILLIC_SLUG_MAP)
    text = "".join(ch for ch in raw if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if not text:
        raise ValueError("monster name cannot generate a slug")
    text = text[:64].rstrip("_")
    if not SLUG_RE.fullmatch(text):
        raise ValueError("generated monster slug is invalid")
    return text


def _safe_texture_slot(path: Path) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    return (value or "texture")[:64]


class MonsterStore:
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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS monsters(
                    slug TEXT PRIMARY KEY,
                    name_en TEXT NOT NULL,
                    name_ru TEXT NOT NULL DEFAULT '',
                    model_source_path TEXT NOT NULL DEFAULT '',
                    model_prepared_path TEXT NOT NULL DEFAULT '',
                    model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,
                    model_published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL,
                    armature_name TEXT NOT NULL DEFAULT '',
                    bone_count INTEGER NOT NULL DEFAULT 0,
                    mesh_count INTEGER NOT NULL DEFAULT 0,
                    skeleton_signature TEXT NOT NULL DEFAULT '',
                    skeleton_structure_signature TEXT NOT NULL DEFAULT '',
                    skeleton_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS monster_textures(
                    id TEXT PRIMARY KEY,
                    monster_slug TEXT NOT NULL,
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
                    UNIQUE(monster_slug, slot)
                );
                CREATE TABLE IF NOT EXISTS monster_stats(
                    monster_slug TEXT NOT NULL,
                    stat_key TEXT NOT NULL,
                    value REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY(monster_slug, stat_key)
                );
                CREATE TABLE IF NOT EXISTS monster_publications(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monster_slug TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    slot TEXT NOT NULL DEFAULT '',
                    monster_revision INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,
                    operation_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    moderation_state TEXT,
                    published_at REAL NOT NULL
                );
                """
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def options(self) -> dict:
        return {"statKeys": list(STAT_KEYS), "defaultStats": dict(DEFAULT_STATS)}

    def _stats(self, connection, slug: str) -> dict[str, float]:
        values = dict(DEFAULT_STATS)
        for row in connection.execute(
            "SELECT stat_key,value FROM monster_stats WHERE monster_slug=? ORDER BY stat_key", (slug,)
        ):
            value = float(row["value"])
            values[str(row["stat_key"])] = int(value) if value.is_integer() else value
        return values

    def _textures(self, connection, slug: str) -> list[dict]:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM monster_textures WHERE monster_slug=? ORDER BY slot", (slug,)
        )]

    def _status(self, row: dict, textures: list[dict]) -> str:
        if not str(row.get("model_source_path") or ""):
            return "INCOMPLETE"
        model_asset = str(row.get("model_asset_id") or "")
        model_current = bool(model_asset and str(row.get("model_published_sha256") or "") == str(row.get("model_sha256") or ""))
        textures_current = all(
            str(item.get("asset_id") or "") and str(item.get("published_sha256") or "") == str(item.get("sha256") or "")
            for item in textures
        )
        if model_current and textures_current:
            return "PUBLISHED"
        any_published = bool(model_asset or any(str(item.get("asset_id") or "") for item in textures))
        return "UPDATE_AVAILABLE" if any_published else "LOCAL_ONLY"

    def _decorate(self, connection, row) -> dict:
        result = dict(row)
        result["textures"] = self._textures(connection, result["slug"])
        result["stats"] = self._stats(connection, result["slug"])
        result["status"] = self._status(result, result["textures"])
        result["server_storage_path"] = f"ServerStorage.monsters.{result['slug']}.model.{result['slug']}"
        return result

    def list(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM monsters ORDER BY name_en,slug").fetchall()
            return [self._decorate(connection, row) for row in rows]

    def get(self, slug: str) -> dict | None:
        slug = str(slug or "").strip().lower()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM monsters WHERE slug=?", (slug,)).fetchone()
            return self._decorate(connection, row) if row else None

    def _archive_existing(self, target: Path, slug: str, revision: int):
        if not target.is_file():
            return
        relative = target.relative_to(self.root)
        archive = self.root / "assets/reimported/monsters" / slug / f"r{revision:04d}" / relative.name
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(target, archive)

    @staticmethod
    def _validate_stats(payload: dict, old: dict | None) -> dict[str, float]:
        incoming = payload.get("stats") or {}
        previous = (old or {}).get("stats") or {}
        result = {}
        for key, default in DEFAULT_STATS.items():
            raw = incoming[key] if key in incoming else previous.get(key, default)
            value = float(raw)
            if key in {"MaxHP", "Damage", "AttackSpeed", "RunSpeed"} and value < 0:
                raise ValueError(f"monster {key} cannot be negative")
            if key == "CritChance" and not 0 <= value <= 100:
                raise ValueError("monster CritChance must be between 0 and 100")
            result[key] = value
        return result

    def register(self, payload: dict) -> dict:
        incoming_slug = str(payload.get("slug") or "").strip().lower()
        old = self.get(incoming_slug) if incoming_slug else None
        name_en = str(payload.get("nameEn", old.get("name_en") if old else "") or "").strip()
        name_ru = str(payload.get("nameRu", old.get("name_ru") if old else "") or "").strip()
        if not name_en:
            raise ValueError("english monster name is required")
        slug = incoming_slug or slugify_english(name_en)
        if not SLUG_RE.fullmatch(slug):
            raise ValueError("monster slug must be lowercase snake_case")
        if old is None:
            old = self.get(slug)
        model_source = str(payload.get("modelSourcePath") or "").strip()
        texture_paths = [str(value).strip() for value in (payload.get("texturePaths") or []) if str(value).strip()]
        if not old and not model_source:
            raise ValueError("choose a monster FBX before registration")
        stats = self._validate_stats(payload, old)

        now = time.time()
        revision = int(old.get("revision") or 0) + 1 if old else 1
        model_source_path = str(old.get("model_source_path") or "") if old else ""
        model_prepared_path = str(old.get("model_prepared_path") or "") if old else ""
        model_sha256 = str(old.get("model_sha256") or "") if old else ""
        analysis = json.loads(str(old.get("skeleton_json") or "{}")) if old else {}

        if model_source:
            source = Path(model_source).expanduser().resolve()
            if not source.is_file() or source.suffix.lower() != ".fbx":
                raise ValueError("monster model must be an FBX file")
            analysis = analyze_character_fbx(self.root, source)
            source_target = self.root / "assets/source/monsters" / slug / "model" / f"{slug}.fbx"
            prepared_target = self.root / "assets/prepared/monsters" / slug / "model" / f"{slug}.fbx"
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
                """INSERT OR REPLACE INTO monsters(
                    slug,name_en,name_ru,model_source_path,model_prepared_path,model_sha256,
                    model_asset_id,model_published_sha256,moderation_state,revision,created_at,updated_at,published_at,
                    armature_name,bone_count,mesh_count,skeleton_signature,skeleton_structure_signature,skeleton_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    slug, name_en, name_ru, model_source_path, model_prepared_path, model_sha256,
                    old.get("model_asset_id") if old else None,
                    str(old.get("model_published_sha256") or "") if old else "",
                    str(old.get("moderation_state") or "") if old else "",
                    revision, old.get("created_at") if old else now, now, old.get("published_at") if old else None,
                    str(analysis.get("armature") or ""), int(analysis.get("boneCount") or 0), int(analysis.get("meshCount") or 0),
                    str(analysis.get("skeletonSignature") or ""), str(analysis.get("skeletonStructureSignature") or ""),
                    json.dumps(analysis, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            for key, value in stats.items():
                connection.execute(
                    "INSERT OR REPLACE INTO monster_stats(monster_slug,stat_key,value) VALUES(?,?,?)",
                    (slug, key, value),
                )

            for raw in texture_paths:
                source = Path(raw).expanduser().resolve()
                if not source.is_file() or source.suffix.lower() not in TEXTURE_EXTENSIONS:
                    raise ValueError(f"monster texture must be png/jpg/jpeg/webp: {source.name}")
                slot = _safe_texture_slot(source)
                texture_id = f"{slug}__{slot}"
                previous = connection.execute("SELECT * FROM monster_textures WHERE id=?", (texture_id,)).fetchone()
                canonical_name = f"{slot}{source.suffix.lower()}"
                source_target = self.root / "assets/source/monsters" / slug / "textures" / canonical_name
                prepared_target = self.root / "assets/prepared/monsters" / slug / "textures" / canonical_name
                source_target.parent.mkdir(parents=True, exist_ok=True)
                prepared_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, source_target)
                shutil.copy2(source, prepared_target)
                digest = self._sha256(prepared_target)
                texture_revision = int(previous["revision"] or 0) + 1 if previous else 1
                connection.execute(
                    """INSERT OR REPLACE INTO monster_textures(
                        id,monster_slug,slot,source_path,prepared_path,sha256,asset_id,published_sha256,
                        moderation_state,revision,created_at,updated_at,published_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        texture_id, slug, slot, source_target.relative_to(self.root).as_posix(),
                        prepared_target.relative_to(self.root).as_posix(), digest,
                        previous["asset_id"] if previous else None,
                        str(previous["published_sha256"] or "") if previous else "",
                        str(previous["moderation_state"] or "") if previous else "",
                        texture_revision, previous["created_at"] if previous else now, now,
                        previous["published_at"] if previous else None,
                    ),
                )

        self.export()
        return self.get(slug)

    def publish(self, slug: str, credentials: dict) -> dict:
        row = self.get(slug)
        if not row:
            raise ValueError(f"unknown monster: {slug}")
        model = self.root / str(row.get("model_prepared_path") or "")
        if not model.is_file():
            raise ValueError("canonical prepared monster FBX is missing")
        api_key = str(credentials.get("apiKey") or "")
        creator_type = str(credentials.get("creatorType") or "")
        creator_id = str(credentials.get("creatorId") or "")
        description = str(credentials.get("description") or "game1 monster").strip()

        if not str(row.get("model_asset_id") or "") or str(row.get("model_published_sha256") or "") != str(row.get("model_sha256") or ""):
            with tempfile.TemporaryDirectory(prefix="game1-monster-publication-") as tmp:
                publication_fbx = Path(tmp) / f"{slug}.fbx"
                prepared = prepare_character_publication_fbx(self.root, model, publication_fbx)
                _assert_publication_skeleton_matches(
                    {
                        "bone_count": row.get("bone_count"),
                        "skeleton_structure_signature": row.get("skeleton_structure_signature"),
                        "skeleton_json": row.get("skeleton_json"),
                    },
                    prepared["analysis"],
                )
                current_asset_id = str(row.get("model_asset_id") or "").strip()
                common = dict(
                    display_name=row["name_en"], description=description,
                    creator_type=creator_type, creator_id=creator_id, api_key=api_key,
                )
                operation = update_model_asset(publication_fbx, asset_id=current_asset_id, **common) if current_asset_id else create_model_asset(publication_fbx, **common)
                result = wait_for_operation(operation, api_key=api_key)
            now = time.time()
            with self.connect() as connection:
                connection.execute(
                    """UPDATE monsters SET model_asset_id=?,model_published_sha256=?,moderation_state=?,published_at=?,updated_at=? WHERE slug=?""",
                    (result.asset_id, row["model_sha256"], result.moderation_state or "", now, now, slug),
                )
                connection.execute(
                    """INSERT INTO monster_publications(monster_slug,kind,slot,monster_revision,asset_id,operation_path,sha256,moderation_state,published_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (slug, "model", "", int(row["revision"]), result.asset_id, result.operation_path, row["model_sha256"], result.moderation_state or "", now),
                )

        row = self.get(slug)
        for texture in row.get("textures") or []:
            if str(texture.get("asset_id") or "") and str(texture.get("published_sha256") or "") == str(texture.get("sha256") or ""):
                continue
            file_path = self.root / str(texture.get("prepared_path") or "")
            texture_asset = str(texture.get("asset_id") or "").strip()
            common = dict(
                display_name=f"{row['name_en']} {texture['slot']}", description=description,
                creator_type=creator_type, creator_id=creator_id, api_key=api_key,
            )
            operation = update_image_asset(file_path, asset_id=texture_asset, **common) if texture_asset else create_image_asset(file_path, **common)
            result = wait_for_operation(operation, api_key=api_key)
            now = time.time()
            with self.connect() as connection:
                connection.execute(
                    "UPDATE monster_textures SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?,updated_at=? WHERE id=?",
                    (result.asset_id, texture["sha256"], result.moderation_state or "", now, now, texture["id"]),
                )
                connection.execute(
                    """INSERT INTO monster_publications(monster_slug,kind,slot,monster_revision,asset_id,operation_path,sha256,moderation_state,published_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (slug, "texture", texture["slot"], int(row["revision"]), result.asset_id, result.operation_path, texture["sha256"], result.moderation_state or "", now),
                )
        self.export()
        return self.get(slug)

    def delete(self, slug: str):
        slug = str(slug or "").strip().lower()
        if not self.get(slug):
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM monster_stats WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monster_textures WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monster_publications WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monsters WHERE slug=?", (slug,))
        self.export()

    def publications(self, slug: str) -> list[dict]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM monster_publications WHERE monster_slug=? ORDER BY id DESC", (slug,)
            )]

    def snapshot(self) -> dict:
        items = self.list()
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "options": self.options(),
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
    def _lua_number(value) -> str:
        number = float(value or 0)
        return str(int(number)) if number.is_integer() else repr(number)

    def export(self):
        snapshot = self.snapshot()
        manifest_path = self.root / "assets/manifests/monsters.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        registry_path = self.root / "src/shared/monster/MonsterRegistry.luau"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "-- generated. do not edit by hand.",
            "return table.freeze({",
            f"\tschemaVersion = {SCHEMA_VERSION},",
            '\tproject = "game1",',
            "\tmonsters = table.freeze({",
        ]
        for row in snapshot["items"]:
            lines.extend([
                f"\t\t[{self._lua_string(row['slug'])}] = table.freeze({{",
                f"\t\t\tslug = {self._lua_string(row['slug'])},",
                f"\t\t\tnameEn = {self._lua_string(row['name_en'])},",
                f"\t\t\tnameRu = {self._lua_string(row['name_ru'])},",
                f"\t\t\tstatus = {self._lua_string(row['status'])},",
                f"\t\t\tmodelAssetId = {self._lua_string(row.get('model_asset_id') or '')},",
                f"\t\t\tserverStoragePath = {self._lua_string(row['server_storage_path'])},",
                f"\t\t\tskeletonSignature = {self._lua_string(row.get('skeleton_signature') or '')},",
                "\t\t\tstats = table.freeze({",
            ])
            for key, value in row.get("stats", {}).items():
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
