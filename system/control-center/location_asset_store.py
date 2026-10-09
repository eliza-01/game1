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
    update_model_asset,
    wait_for_operation,
)

SCHEMA_VERSION = 4
PROJECT = "game1"
CATEGORIES = ("tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building")
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
                    model_path TEXT NOT NULL DEFAULT '',
                    model_sha256 TEXT NOT NULL DEFAULT '',
                    model_asset_id TEXT,
                    model_published_sha256 TEXT NOT NULL DEFAULT '',
                    model_moderation_state TEXT NOT NULL DEFAULT '',
                    texture_path TEXT NOT NULL DEFAULT '',
                    texture_sha256 TEXT NOT NULL DEFAULT '',
                    texture_asset_id TEXT,
                    texture_published_sha256 TEXT NOT NULL DEFAULT '',
                    texture_moderation_state TEXT NOT NULL DEFAULT '',
                    texture_reference_slug TEXT NOT NULL DEFAULT '',
                    destructible INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(location_assets)").fetchall()}
            required = {
                "slug", "name_en", "category", "model_path", "model_sha256", "model_asset_id",
                "model_published_sha256", "model_moderation_state", "texture_path", "texture_sha256",
                "texture_asset_id", "texture_published_sha256", "texture_moderation_state",
                "texture_reference_slug", "destructible", "revision", "created_at", "updated_at", "published_at",
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
            # Before m51 Location Assets updated changed images in-place. Roblox image
            # consumers can keep serving the old image for that Asset ID, so a replacement
            # texture must have a fresh publication identity. Detect those rows from
            # publication history and make them pending for one clean republish.
            legacy_texture_updates = connection.execute(
                """SELECT la.slug
                   FROM location_assets AS la
                   JOIN location_asset_publications AS publication
                     ON publication.asset_slug=la.slug
                    AND publication.kind='texture'
                    AND publication.asset_id=la.texture_asset_id
                   WHERE COALESCE(la.texture_reference_slug,'')=''
                     AND COALESCE(la.texture_asset_id,'')<>''
                   GROUP BY la.slug,la.texture_asset_id
                   HAVING COUNT(DISTINCT publication.sha256)>1"""
            ).fetchall()
            if legacy_texture_updates:
                now = time.time()
                connection.executemany(
                    """UPDATE location_assets
                       SET texture_asset_id=NULL,texture_published_sha256='',texture_moderation_state='',updated_at=?
                       WHERE slug=?""",
                    [(now, str(row["slug"])) for row in legacy_texture_updates],
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
        if not row.get("model_path") or not row.get("texture_path"):
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
        result["destructible"] = bool(result.get("destructible"))
        if owner is not None and owner.get("slug") != result.get("slug"):
            for field in (
                "texture_path",
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
        destructible = parse_bool(payload.get("destructible"), bool(old.get("destructible")) if old else False)
        if category not in CATEGORIES:
            raise ValueError("location asset category must be tree, bush, rock, light, fence, decoration, ladder, flower or building")

        selected_model = str(payload.get("modelSourcePath") or "").strip()
        selected_texture = str(payload.get("textureSourcePath") or "").strip()
        texture_reference = str(payload.get("textureReferenceSlug") or "").strip().lower()
        old_reference = str(old.get("texture_reference_slug") or "").strip().lower() if old else ""
        if old is None and not selected_model:
            raise ValueError("choose a location asset FBX before registration")
        if selected_texture and texture_reference:
            raise ValueError("choose either a texture file or a reused registered texture, not both")

        reference_owner = None
        if texture_reference:
            if texture_reference == slug:
                raise ValueError("a location asset cannot reuse its own texture")
            reference_row = self._raw_get(texture_reference)
            if reference_row is None:
                raise ValueError(f"unknown shared texture asset: {texture_reference}")
            reference_owner = self._resolve_texture_owner(reference_row)
            if reference_owner is None or not str(reference_owner.get("texture_path") or ""):
                raise ValueError("selected shared texture has no canonical texture source")
            texture_reference = str(reference_owner.get("slug") or texture_reference)

        if old is None and not selected_texture and not texture_reference:
            raise ValueError("choose a location asset PNG/JPG or reuse a registered texture before registration")
        if old is not None and old_reference and not texture_reference and not selected_texture:
            raise ValueError("choose a replacement PNG/JPG or another shared texture before clearing the current shared texture")

        now = time.time()
        revision = int(old.get("revision") or 0) + 1 if old else 1
        values = {
            "model_path": str(old.get("model_path") or "") if old else "",
            "model_sha256": str(old.get("model_sha256") or "") if old else "",
            "texture_path": str(old.get("texture_path") or "") if old else "",
            "texture_sha256": str(old.get("texture_sha256") or "") if old else "",
        }
        texture_asset_id = old.get("texture_asset_id") if old else None
        texture_published_sha256 = str(old.get("texture_published_sha256") or "") if old else ""
        texture_moderation_state = str(old.get("texture_moderation_state") or "") if old else ""
        stored_reference = old_reference

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

        if selected_texture:
            selected = Path(selected_texture).expanduser().resolve()
            source_suffix = selected.suffix.lower()
            if not selected.is_file() or source_suffix not in TEXTURE_SUFFIXES:
                raise ValueError("location asset texture must be a PNG or JPG file")
            canonical_suffix = ".jpg" if source_suffix == ".jpeg" else source_suffix
            canonical_target = self.root / "assets/source/location-assets" / category / slug / "textures" / f"{slug}{canonical_suffix}"
            if old:
                replacements = {canonical_target.resolve()}
                old_revision = int(old.get("revision") or 1)
                self._retire_replaced_file(str(old.get("texture_path") or ""), slug, old_revision, replacements)
            canonical_target.parent.mkdir(parents=True, exist_ok=True)
            if old:
                self._archive_existing(canonical_target, slug, int(old.get("revision") or 1))
            shutil.copy2(selected, canonical_target)
            values["texture_path"] = canonical_target.relative_to(self.root).as_posix()
            values["texture_sha256"] = self._sha256(canonical_target)
            old_texture_sha256 = str(old.get("texture_sha256") or "") if old else ""
            texture_replaced = old is None or bool(old_reference) or values["texture_sha256"] != old_texture_sha256
            if texture_replaced:
                # A changed Location Asset texture is a new Roblox Image asset, never
                # an in-place update of the previous image id. This keeps Studio/DecoManager
                # deterministic and lets shared-texture consumers follow the new owner id.
                texture_asset_id = None
                texture_published_sha256 = ""
                texture_moderation_state = ""
            stored_reference = ""
        elif texture_reference:
            if old and not old_reference:
                old_revision = int(old.get("revision") or 1)
                self._retire_replaced_file(str(old.get("texture_path") or ""), slug, old_revision, set())
            values["texture_path"] = ""
            values["texture_sha256"] = ""
            texture_asset_id = None
            texture_published_sha256 = ""
            texture_moderation_state = ""
            stored_reference = texture_reference

        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO location_assets(
                    slug,name_en,category,
                    model_path,model_sha256,model_asset_id,model_published_sha256,model_moderation_state,
                    texture_path,texture_sha256,texture_asset_id,texture_published_sha256,texture_moderation_state,texture_reference_slug,destructible,
                    revision,created_at,updated_at,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    slug, name_en, category,
                    values["model_path"], values["model_sha256"],
                    old.get("model_asset_id") if old else None,
                    str(old.get("model_published_sha256") or "") if old else "",
                    str(old.get("model_moderation_state") or "") if old else "",
                    values["texture_path"], values["texture_sha256"],
                    texture_asset_id, texture_published_sha256, texture_moderation_state, stored_reference, 1 if destructible else 0,
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
        model = self.root / str(row.get("model_path") or "")
        texture = self.root / str(row.get("texture_path") or "")
        if not model.is_file():
            raise ValueError("canonical Location Asset FBX is missing")
        if not texture.is_file():
            raise ValueError("canonical Location Asset texture is missing")
        texture_reference = str(row.get("texture_reference_slug") or "").strip().lower()
        if texture_reference and not self._texture_current(row):
            raise ValueError(f"shared texture owner {texture_reference} must publish its texture first")

        api_key = str(credentials.get("apiKey") or "")
        creator_type = str(credentials.get("creatorType") or "")
        creator_id = str(credentials.get("creatorId") or "")
        base_description = str(credentials.get("description") or "game1 location asset").strip()
        description = base_description or "game1 location asset"
        asset_name = str(row.get("name_en") or "").strip()
        if asset_name and asset_name.casefold() not in description.casefold():
            description = f"{description} · {asset_name}"

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
            display_name = f"{row['name_en']} texture"
            # Dirty owned textures always publish as a new Roblox Image asset. Image
            # replacement is identity-changing for Location Assets by design.
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
                f"\t\t\tdestructible = {str(bool(row.get('destructible'))).lower()},",
                "\t\t}),",
            ])
        lines.extend(["\t}),", "})", ""])
        registry_path.write_text("\n".join(lines), encoding="utf-8")
