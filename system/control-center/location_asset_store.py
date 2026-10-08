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

SCHEMA_VERSION = 2
PROJECT = "game1"
CATEGORIES = ("tree", "bush", "rock", "light", "fence", "decoration")
TEXTURE_SUFFIXES = (".png", ".jpg", ".jpeg")
CATEGORY_LABELS = {
    "tree": "Trees",
    "bush": "Bushes",
    "rock": "Rocks",
    "light": "Lights",
    "fence": "Fences",
    "decoration": "Decorations",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


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
        self.export()

    def connect(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS location_assets(
                    slug TEXT PRIMARY KEY,
                    name_en TEXT NOT NULL,
                    category TEXT NOT NULL,
                    model_source_path TEXT NOT NULL DEFAULT '',
                    model_prepared_path TEXT NOT NULL DEFAULT '',
                    model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,
                    model_published_sha256 TEXT NOT NULL DEFAULT '',
                    model_moderation_state TEXT NOT NULL DEFAULT '',
                    texture_source_path TEXT NOT NULL DEFAULT '',
                    texture_prepared_path TEXT NOT NULL DEFAULT '',
                    texture_sha256 TEXT NOT NULL DEFAULT '',
                    texture_asset_id TEXT,
                    texture_published_sha256 TEXT NOT NULL DEFAULT '',
                    texture_moderation_state TEXT NOT NULL DEFAULT '',
                    texture_reference_slug TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(location_assets)").fetchall()}
            if "texture_reference_slug" not in columns:
                connection.execute(
                    "ALTER TABLE location_assets ADD COLUMN texture_reference_slug TEXT NOT NULL DEFAULT ''"
                )
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

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

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
        if not row.get("model_source_path") or not row.get("texture_source_path"):
            return "INCOMPLETE"
        model_current = bool(
            str(row.get("model_asset_id") or "")
            and str(row.get("model_published_sha256") or "") == str(row.get("model_sha256") or "")
        )
        texture_current = self._texture_current(row)
        if model_current and texture_current:
            return "PUBLISHED"
        has_own_publication = bool(str(row.get("model_asset_id") or "")) or bool(
            not str(row.get("texture_reference_slug") or "") and str(row.get("texture_asset_id") or "")
        )
        if has_own_publication:
            return "UPDATE_AVAILABLE"
        return "LOCAL_ONLY"

    def _raw_get(self, slug: str) -> dict | None:
        normalized = str(slug or "").strip().lower()
        if not normalized:
            return None
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM location_assets WHERE slug=?", (normalized,)).fetchone()
        return dict(row) if row else None

    def _resolve_texture_owner(self, row: dict, rows_by_slug: dict[str, dict] | None = None) -> dict | None:
        current = dict(row)
        seen: set[str] = set()
        while True:
            slug = str(current.get("slug") or "").strip().lower()
            if slug in seen:
                return None
            seen.add(slug)
            reference = str(current.get("texture_reference_slug") or "").strip().lower()
            if not reference:
                return current
            current = (rows_by_slug or {}).get(reference) or self._raw_get(reference)
            if current is None:
                return None

    def _decorate(self, row, rows_by_slug: dict[str, dict] | None = None) -> dict:
        result = dict(row)
        owner = self._resolve_texture_owner(result, rows_by_slug)
        result["texture_owner_slug"] = str(owner.get("slug") or "") if owner else ""
        result["texture_shared"] = bool(str(result.get("texture_reference_slug") or ""))
        if owner is not None and owner.get("slug") != result.get("slug"):
            for field in (
                "texture_source_path",
                "texture_prepared_path",
                "texture_sha256",
                "texture_asset_id",
                "texture_published_sha256",
                "texture_moderation_state",
            ):
                result[field] = owner.get(field)
        result["status"] = self._status(result)
        result["category_label"] = CATEGORY_LABELS.get(result.get("category"), str(result.get("category") or ""))
        return result

    def list(self) -> list[dict]:
        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT * FROM location_assets ORDER BY category,name_en,slug"
            ).fetchall()]
        rows_by_slug = {str(row.get("slug") or ""): row for row in rows}
        return [self._decorate(row, rows_by_slug) for row in rows]

    def get(self, slug: str) -> dict | None:
        row = self._raw_get(slug)
        return self._decorate(row) if row else None

    def _archive_existing(self, path: Path, slug: str, revision: int):
        if not path.is_file():
            return
        relative = path.resolve().relative_to(self.root)
        tail = relative.parts[-2:]
        destination = self.root / "assets/reimported/location-assets" / slug / f"r{revision:04d}" / Path(*tail)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)

    def _retire_replaced_file(self, relative_path: str, slug: str, revision: int, replacements: set[Path]):
        if not relative_path:
            return
        path = (self.root / relative_path).resolve()
        if path in replacements or not path.is_file():
            return
        self._archive_existing(path, slug, revision)
        path.unlink()

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
        category = str(payload.get("category") or (old.get("category") if old else "") or "").strip().lower()
        if category not in CATEGORIES:
            raise ValueError("location asset category must be tree, bush, rock, light, fence or decoration")

        model_source = str(payload.get("modelSourcePath") or "").strip()
        texture_source = str(payload.get("textureSourcePath") or "").strip()
        texture_reference = str(payload.get("textureReferenceSlug") or "").strip().lower()
        old_reference = str(old.get("texture_reference_slug") or "").strip().lower() if old else ""
        if old is None and not model_source:
            raise ValueError("choose a location asset FBX before registration")
        if texture_source and texture_reference:
            raise ValueError("choose either a texture file or a reused registered texture, not both")

        reference_owner = None
        if texture_reference:
            if texture_reference == slug:
                raise ValueError("a location asset cannot reuse its own texture")
            reference_row = self._raw_get(texture_reference)
            if reference_row is None:
                raise ValueError(f"unknown shared texture asset: {texture_reference}")
            reference_owner = self._resolve_texture_owner(reference_row)
            if reference_owner is None or not str(reference_owner.get("texture_prepared_path") or ""):
                raise ValueError("selected shared texture has no canonical texture source")
            texture_reference = str(reference_owner.get("slug") or texture_reference)

        if old is None and not texture_source and not texture_reference:
            raise ValueError("choose a location asset PNG/JPG or reuse a registered texture before registration")
        if old is not None and old_reference and not texture_reference and not texture_source:
            raise ValueError("choose a replacement PNG/JPG or another shared texture before clearing the current shared texture")

        now = time.time()
        revision = int(old.get("revision") or 0) + 1 if old else 1
        values = {
            "model_source_path": str(old.get("model_source_path") or "") if old else "",
            "model_prepared_path": str(old.get("model_prepared_path") or "") if old else "",
            "model_sha256": str(old.get("model_sha256") or "") if old else "",
            "texture_source_path": str(old.get("texture_source_path") or "") if old else "",
            "texture_prepared_path": str(old.get("texture_prepared_path") or "") if old else "",
            "texture_sha256": str(old.get("texture_sha256") or "") if old else "",
        }
        texture_asset_id = old.get("texture_asset_id") if old else None
        texture_published_sha256 = str(old.get("texture_published_sha256") or "") if old else ""
        texture_moderation_state = str(old.get("texture_moderation_state") or "") if old else ""
        stored_reference = old_reference

        if model_source:
            source = Path(model_source).expanduser().resolve()
            if not source.is_file() or source.suffix.lower() != ".fbx":
                raise ValueError("location asset model must be an FBX file")
            source_target = self.root / "assets/source/location-assets" / category / slug / "model" / f"{slug}.fbx"
            prepared_target = self.root / "assets/prepared/location-assets" / category / slug / "model" / f"{slug}.fbx"
            for target in (source_target, prepared_target):
                target.parent.mkdir(parents=True, exist_ok=True)
                if old:
                    self._archive_existing(target, slug, int(old.get("revision") or 1))
                shutil.copy2(source, target)
            values["model_source_path"] = source_target.relative_to(self.root).as_posix()
            values["model_prepared_path"] = prepared_target.relative_to(self.root).as_posix()
            values["model_sha256"] = self._sha256(prepared_target)

        if texture_source:
            source = Path(texture_source).expanduser().resolve()
            source_suffix = source.suffix.lower()
            if not source.is_file() or source_suffix not in TEXTURE_SUFFIXES:
                raise ValueError("location asset texture must be a PNG or JPG file")
            canonical_suffix = ".jpg" if source_suffix == ".jpeg" else source_suffix
            source_target = self.root / "assets/source/location-assets" / category / slug / "textures" / f"{slug}{canonical_suffix}"
            prepared_target = self.root / "assets/prepared/location-assets" / category / slug / "textures" / f"{slug}{canonical_suffix}"
            if old:
                replacements = {source_target.resolve(), prepared_target.resolve()}
                old_revision = int(old.get("revision") or 1)
                self._retire_replaced_file(str(old.get("texture_source_path") or ""), slug, old_revision, replacements)
                self._retire_replaced_file(str(old.get("texture_prepared_path") or ""), slug, old_revision, replacements)
            for target in (source_target, prepared_target):
                target.parent.mkdir(parents=True, exist_ok=True)
                if old:
                    self._archive_existing(target, slug, int(old.get("revision") or 1))
                shutil.copy2(source, target)
            values["texture_source_path"] = source_target.relative_to(self.root).as_posix()
            values["texture_prepared_path"] = prepared_target.relative_to(self.root).as_posix()
            values["texture_sha256"] = self._sha256(prepared_target)
            if old_reference:
                texture_asset_id = None
                texture_published_sha256 = ""
                texture_moderation_state = ""
            stored_reference = ""
        elif texture_reference:
            if old and not old_reference:
                old_revision = int(old.get("revision") or 1)
                self._retire_replaced_file(str(old.get("texture_source_path") or ""), slug, old_revision, set())
                self._retire_replaced_file(str(old.get("texture_prepared_path") or ""), slug, old_revision, set())
            values["texture_source_path"] = ""
            values["texture_prepared_path"] = ""
            values["texture_sha256"] = ""
            texture_asset_id = None
            texture_published_sha256 = ""
            texture_moderation_state = ""
            stored_reference = texture_reference

        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO location_assets(
                    slug,name_en,category,
                    model_source_path,model_prepared_path,model_sha256,model_asset_id,model_published_sha256,model_moderation_state,
                    texture_source_path,texture_prepared_path,texture_sha256,texture_asset_id,texture_published_sha256,texture_moderation_state,texture_reference_slug,
                    revision,created_at,updated_at,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    slug, name_en, category,
                    values["model_source_path"], values["model_prepared_path"], values["model_sha256"],
                    old.get("model_asset_id") if old else None,
                    str(old.get("model_published_sha256") or "") if old else "",
                    str(old.get("model_moderation_state") or "") if old else "",
                    values["texture_source_path"], values["texture_prepared_path"], values["texture_sha256"],
                    texture_asset_id, texture_published_sha256, texture_moderation_state, stored_reference,
                    revision,
                    old.get("created_at") if old else now,
                    now,
                    old.get("published_at") if old else None,
                ),
            )
        self.export()
        return self.get(slug)

    def publish(self, slug: str, credentials: dict) -> dict:
        row = self.get(slug)
        if not row:
            raise ValueError(f"unknown location asset: {slug}")
        model = self.root / str(row.get("model_prepared_path") or "")
        texture = self.root / str(row.get("texture_prepared_path") or "")
        if not model.is_file():
            raise ValueError("canonical prepared location asset FBX is missing")
        if not texture.is_file():
            raise ValueError("canonical prepared location asset texture is missing")
        texture_reference = str(row.get("texture_reference_slug") or "").strip().lower()
        if texture_reference and not self._texture_current(row):
            raise ValueError(f"shared texture owner {texture_reference} must publish its texture first")

        api_key = str(credentials.get("apiKey") or "")
        creator_type = str(credentials.get("creatorType") or "")
        creator_id = str(credentials.get("creatorId") or "")
        description = str(credentials.get("description") or "game1 location asset").strip()

        if str(row.get("model_published_sha256") or "") != str(row.get("model_sha256") or ""):
            current_asset_id = str(row.get("model_asset_id") or "").strip()
            if current_asset_id:
                operation = update_model_asset(
                    model,
                    asset_id=current_asset_id,
                    display_name=row["name_en"],
                    description=description,
                    creator_type=creator_type,
                    creator_id=creator_id,
                    api_key=api_key,
                )
            else:
                operation = create_model_asset(
                    model,
                    display_name=row["name_en"],
                    description=description,
                    creator_type=creator_type,
                    creator_id=creator_id,
                    api_key=api_key,
                )
            result = wait_for_operation(operation, api_key=api_key)
            now = time.time()
            with self.connect() as connection:
                connection.execute(
                    """UPDATE location_assets
                       SET model_asset_id=?,model_published_sha256=?,model_moderation_state=?,updated_at=?,published_at=?
                       WHERE slug=?""",
                    (result.asset_id, row["model_sha256"], result.moderation_state or "", now, now, slug),
                )
                connection.execute(
                    """INSERT INTO location_asset_publications(
                        asset_slug,kind,revision,asset_id,operation_path,sha256,moderation_state,published_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (slug, "model", int(row["revision"]), result.asset_id, result.operation_path,
                     row["model_sha256"], result.moderation_state or "", now),
                )

        row = self.get(slug)
        if not texture_reference and str(row.get("texture_published_sha256") or "") != str(row.get("texture_sha256") or ""):
            current_texture_id = str(row.get("texture_asset_id") or "").strip()
            display_name = f"{row['name_en']} texture"
            if current_texture_id:
                operation = update_image_asset(
                    texture,
                    asset_id=current_texture_id,
                    display_name=display_name,
                    description=description,
                    creator_type=creator_type,
                    creator_id=creator_id,
                    api_key=api_key,
                )
            else:
                operation = create_image_asset(
                    texture,
                    display_name=display_name,
                    description=description,
                    creator_type=creator_type,
                    creator_id=creator_id,
                    api_key=api_key,
                )
            result = wait_for_operation(operation, api_key=api_key)
            now = time.time()
            with self.connect() as connection:
                connection.execute(
                    """UPDATE location_assets
                       SET texture_asset_id=?,texture_published_sha256=?,texture_moderation_state=?,updated_at=?,published_at=?
                       WHERE slug=?""",
                    (result.asset_id, row["texture_sha256"], result.moderation_state or "", now, now, slug),
                )
                connection.execute(
                    """INSERT INTO location_asset_publications(
                        asset_slug,kind,revision,asset_id,operation_path,sha256,moderation_state,published_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (slug, "texture", int(row["revision"]), result.asset_id, result.operation_path,
                     row["texture_sha256"], result.moderation_state or "", now),
                )

        self.export()
        return self.get(slug)

    def delete(self, slug: str):
        normalized = str(slug or "").strip().lower()
        if not self.get(normalized):
            return
        with self.connect() as connection:
            dependents = connection.execute(
                "SELECT slug FROM location_assets WHERE texture_reference_slug=? ORDER BY slug",
                (normalized,),
            ).fetchall()
            if dependents:
                names = ", ".join(str(row[0]) for row in dependents[:8])
                raise ValueError("texture is reused by location assets: " + names)
            connection.execute("DELETE FROM location_asset_publications WHERE asset_slug=?", (normalized,))
            connection.execute("DELETE FROM location_assets WHERE slug=?", (normalized,))
        self.export()

    def publications(self, slug: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM location_asset_publications WHERE asset_slug=? ORDER BY id DESC",
                (str(slug or "").strip().lower(),),
            ).fetchall()
        return [dict(row) for row in rows]

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
                f"\t\t\ttextureOwnerSlug = {self._lua_string(row.get('texture_owner_slug') or '')},",
                f"\t\t\ttextureShared = {str(bool(row.get('texture_shared'))).lower()},",
                "\t\t}),",
            ])
        lines.extend(["\t}),", "})", ""])
        registry_path.write_text("\n".join(lines), encoding="utf-8")
