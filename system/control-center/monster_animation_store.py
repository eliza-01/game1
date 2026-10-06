from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import shutil
import sqlite3
import time

from opencloud_assets import create_animation_asset, wait_for_operation

SCHEMA_VERSION = 1
PROJECT = "game1"
MAX_SCAN_FILES = 5000
ANIMATION_EXTENSIONS = {".rbxm", ".rbxmx"}
SLOT_CATALOG = [
    {"group": "stance", "slot": "idle", "state": "idle", "role": "base", "label": "idle · base", "looped": True, "priority": "Idle", "variants": False},
    {"group": "stance", "slot": "idle_special", "state": "idle", "role": "special", "label": "idle · special", "looped": False, "priority": "Idle", "variants": True},
    {"group": "movement", "slot": "walk", "state": "walk", "role": "base", "label": "walk", "looped": True, "priority": "Movement", "variants": False},
    {"group": "movement", "slot": "run", "state": "run", "role": "base", "label": "run", "looped": True, "priority": "Movement", "variants": False},
    {"group": "combat", "slot": "combat_idle", "state": "combat_idle", "role": "base", "label": "combat idle", "looped": True, "priority": "Idle", "variants": False},
    {"group": "combat", "slot": "attack", "state": "attack", "role": "variant", "label": "attack", "looped": False, "priority": "Action", "variants": True},
    {"group": "life", "slot": "death", "state": "death", "role": "base", "label": "death", "looped": False, "priority": "Action", "variants": False},
]
SLOT_BY_NAME = {row["slot"]: row for row in SLOT_CATALOG}


def _safe_token(value: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
    return re.sub(r"_+", "_", value)


def _parse_variant(value: str) -> tuple[str, int]:
    match = re.match(r"^(.*?)(?:_([0-9]{1,3}))?$", value)
    if not match:
        return value, 0
    return match.group(1), int(match.group(2) or 0)


def classify(path: Path, slug: str) -> dict | None:
    stem = _safe_token(path.stem)
    prefix = _safe_token(slug) + "_"
    if prefix and stem.startswith(prefix):
        stem = stem[len(prefix):]
    body, variant = _parse_variant(stem)
    aliases = {
        "idle": "idle",
        "wait": "idle",
        "wait_idle": "idle",
        "idle_special": "idle_special",
        "special_idle": "idle_special",
        "sp_wait": "idle_special",
        "walk": "walk",
        "run": "run",
        "attack": "attack",
        "atk": "attack",
        "combat_idle": "combat_idle",
        "attack_wait": "combat_idle",  # legacy filename compatibility only
        "atkwait": "combat_idle",
        "death": "death",
        "dead": "death",
        "die": "death",
    }
    slot = aliases.get(body)
    if not slot:
        special_idle = re.fullmatch(r"(?:spwait|idlespecial)0*([0-9]+)", body)
        if special_idle:
            slot = "idle_special"
            variant = max(1, int(special_idle.group(1)))
    if not slot:
        atk = re.fullmatch(r"atk0*([0-9]+)", body)
        if atk:
            slot = "attack"
            variant = max(1, int(atk.group(1)))
    if slot not in SLOT_BY_NAME:
        return None
    definition = SLOT_BY_NAME[slot]
    if definition.get("variants"):
        variant = max(1, variant)
    else:
        variant = 0
    return {"slot": slot, "variant": variant, **definition}


def filename_rules(slug: str) -> list[dict]:
    prefix = _safe_token(slug)
    rows = []
    for definition in SLOT_CATALOG:
        variant = 1 if definition.get("variants") else 0
        suffix = f"_{variant:02d}" if variant else ""
        rows.append({
            **definition,
            "state": definition.get("state") or definition["slot"],
            "variantPattern": "01..n" if definition.get("variants") else "",
            "canonicalFilename": f"{prefix}_{definition['slot']}{suffix}.rbxm" if prefix else f"{definition['slot']}{suffix}.rbxm",
        })
    return rows


class MonsterAnimationStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runtime = self.root / ".control-center"
        self.db = self.runtime / "game1.db"
        self._init()
        self._sync_profiles()
        self.export()

    def connect(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS monster_animation_profiles(
                    monster_slug TEXT PRIMARY KEY,
                    skeleton_signature TEXT NOT NULL DEFAULT '',
                    scan_root TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS monster_animation_clips(
                    id TEXT PRIMARY KEY,
                    monster_slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    prepared_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL DEFAULT '',
                    duplicate_first_frame_at_end INTEGER NOT NULL DEFAULT 0,
                    asset_id TEXT,
                    published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL
                );
                CREATE TABLE IF NOT EXISTS monster_animation_bindings(
                    id TEXT PRIMARY KEY,
                    monster_slug TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    variant INTEGER NOT NULL DEFAULT 0,
                    clip_id TEXT NOT NULL,
                    weight INTEGER NOT NULL DEFAULT 100,
                    playback_speed_percent INTEGER NOT NULL DEFAULT 100,
                    looped INTEGER NOT NULL DEFAULT 0,
                    priority TEXT NOT NULL DEFAULT 'Movement',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(monster_slug, slot, variant)
                );
                CREATE TABLE IF NOT EXISTS monster_animation_publications(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clip_id TEXT NOT NULL,
                    clip_revision INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,
                    operation_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    moderation_state TEXT,
                    published_at REAL NOT NULL
                );
                """
            )
            clip_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_clips)")}
            if "source_sha256" not in clip_columns:
                connection.execute("ALTER TABLE monster_animation_clips ADD COLUMN source_sha256 TEXT NOT NULL DEFAULT ''")
            if "duplicate_first_frame_at_end" not in clip_columns:
                connection.execute("ALTER TABLE monster_animation_clips ADD COLUMN duplicate_first_frame_at_end INTEGER NOT NULL DEFAULT 0")
            connection.execute("UPDATE monster_animation_clips SET source_sha256=sha256 WHERE source_sha256='' OR source_sha256 IS NULL")
            binding_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_bindings)")}
            if "playback_speed_percent" not in binding_columns:
                connection.execute(
                    "ALTER TABLE monster_animation_bindings ADD COLUMN playback_speed_percent INTEGER NOT NULL DEFAULT 100"
                )
            self._migrate_combat_idle(connection)
        self._restore_prepared_files()

    def _restore_prepared_files(self) -> None:
        """Undo legacy physical seam transforms; prepared animation bytes mirror source."""
        updates = []
        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT id,source_path,prepared_path,sha256,source_sha256 FROM monster_animation_clips"
            )]
            for row in rows:
                source = self.root / str(row.get("source_path") or "")
                prepared = self.root / str(row.get("prepared_path") or "")
                if not source.is_file():
                    continue
                source_sha = self._sha256(source)
                prepared_sha = self._sha256(prepared) if prepared.is_file() else ""
                if prepared_sha != source_sha:
                    prepared.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, prepared)
                if str(row.get("sha256") or "") != source_sha or str(row.get("source_sha256") or "") != source_sha:
                    updates.append((source_sha, source_sha, time.time(), str(row["id"])))
            if updates:
                connection.executemany(
                    "UPDATE monster_animation_clips SET sha256=?,source_sha256=?,updated_at=? WHERE id=?",
                    updates,
                )

    def _migrate_combat_idle(self, connection) -> None:
        """Move the old attack_wait storage coordinate to the canonical combat_idle state."""
        legacy_rows = connection.execute(
            "SELECT id,monster_slug,variant,clip_id FROM monster_animation_bindings WHERE slot='attack_wait'"
        ).fetchall()
        for row in legacy_rows:
            slug = str(row["monster_slug"])
            variant = int(row["variant"] or 0)
            old_clip_id = str(row["clip_id"])
            new_clip_id = f"monster__{slug}__combat_idle__{variant:02d}"
            new_binding_id = "binding__" + new_clip_id
            conflict = connection.execute(
                "SELECT id FROM monster_animation_bindings WHERE monster_slug=? AND slot='combat_idle' AND variant=?",
                (slug, variant),
            ).fetchone()
            if conflict is not None:
                connection.execute("DELETE FROM monster_animation_bindings WHERE id=?", (str(row["id"]),))
                if not connection.execute("SELECT 1 FROM monster_animation_bindings WHERE clip_id=? LIMIT 1", (old_clip_id,)).fetchone():
                    connection.execute("DELETE FROM monster_animation_publications WHERE clip_id=?", (old_clip_id,))
                    connection.execute("DELETE FROM monster_animation_clips WHERE id=?", (old_clip_id,))
                continue

            clip = connection.execute("SELECT id FROM monster_animation_clips WHERE id=?", (old_clip_id,)).fetchone()
            target_clip = connection.execute("SELECT id FROM monster_animation_clips WHERE id=?", (new_clip_id,)).fetchone()
            if clip is not None and target_clip is None:
                connection.execute("UPDATE monster_animation_publications SET clip_id=? WHERE clip_id=?", (new_clip_id, old_clip_id))
                connection.execute("UPDATE monster_animation_clips SET id=?,name='combat_idle' WHERE id=?", (new_clip_id, old_clip_id))
                old_clip_id = new_clip_id
            connection.execute(
                "UPDATE monster_animation_bindings SET id=?,slot='combat_idle',clip_id=?,updated_at=? WHERE id=?",
                (new_binding_id, old_clip_id, time.time(), str(row["id"])),
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _sync_profiles(self):
        now = time.time()
        with self.connect() as connection:
            for monster in connection.execute("SELECT slug,skeleton_signature FROM monsters ORDER BY slug"):
                slug = str(monster["slug"])
                skeleton = str(monster["skeleton_signature"] or "")
                existing = connection.execute("SELECT * FROM monster_animation_profiles WHERE monster_slug=?", (slug,)).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO monster_animation_profiles(monster_slug,skeleton_signature,scan_root,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (slug, skeleton, "", now, now),
                    )
                elif str(existing["skeleton_signature"] or "") != skeleton:
                    connection.execute(
                        "UPDATE monster_animation_profiles SET skeleton_signature=?,updated_at=? WHERE monster_slug=?",
                        (skeleton, now, slug),
                    )

    def _monster(self, slug: str) -> dict:
        slug = str(slug or "").strip().lower()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM monsters WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise ValueError(f"unknown monster: {slug}")
        return dict(row)

    def _profile(self, slug: str) -> dict:
        self._monster(slug)
        self._sync_profiles()
        with self.connect() as connection:
            return dict(connection.execute("SELECT * FROM monster_animation_profiles WHERE monster_slug=?", (slug,)).fetchone())

    def usage(self, slug: str) -> dict:
        with self.connect() as connection:
            clips = int(connection.execute("SELECT COUNT(*) FROM monster_animation_clips WHERE monster_slug=?", (slug,)).fetchone()[0])
            bindings = int(connection.execute("SELECT COUNT(*) FROM monster_animation_bindings WHERE monster_slug=?", (slug,)).fetchone()[0])
        return {"monsterSlug": slug, "clips": clips, "bindings": bindings}

    def delete_profile(self, slug: str):
        with self.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM monster_animation_clips WHERE monster_slug=?", (slug,))]
            for clip_id in ids:
                connection.execute("DELETE FROM monster_animation_publications WHERE clip_id=?", (clip_id,))
            connection.execute("DELETE FROM monster_animation_bindings WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monster_animation_clips WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monster_animation_profiles WHERE monster_slug=?", (slug,))
        self.export()

    def _managed(self, path: Path) -> bool:
        for root in (self.root / "assets/source/monsters", self.root / "assets/prepared/monsters"):
            try:
                path.relative_to(root.resolve())
                return True
            except ValueError:
                pass
        return False

    def _register(self, connection, slug: str, source: Path, binding: dict, now: float) -> tuple[str, dict]:
        slot = binding["slot"]
        variant = int(binding["variant"])
        suffix = f"_{variant:02d}" if variant else ""
        stem = f"{slot}{suffix}"
        clip_id = f"monster__{slug}__{slot}__{variant:02d}"
        binding_id = "binding__" + clip_id
        relative = Path("monsters") / slug / "animations" / f"{stem}{source.suffix.lower()}"
        source_target = self.root / "assets/source" / relative
        prepared_target = self.root / "assets/prepared" / relative
        source_target.parent.mkdir(parents=True, exist_ok=True)
        prepared_target.parent.mkdir(parents=True, exist_ok=True)
        source_sha = self._sha256(source)
        old = connection.execute("SELECT * FROM monster_animation_clips WHERE id=?", (clip_id,)).fetchone()
        old_dict = dict(old) if old else None
        previous_source_sha = str((old_dict or {}).get("source_sha256") or (old_dict or {}).get("sha256") or "")
        same_source = bool(old_dict and previous_source_sha == source_sha)
        if not same_source or not source_target.is_file():
            shutil.copy2(source, source_target)
        if not same_source or not prepared_target.is_file():
            shutil.copy2(source_target, prepared_target)
        digest = self._sha256(prepared_target)
        if old_dict is None:
            connection.execute(
                """INSERT INTO monster_animation_clips(id,monster_slug,name,source_path,prepared_path,sha256,source_sha256,duplicate_first_frame_at_end,asset_id,published_sha256,moderation_state,revision,created_at,updated_at,published_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (clip_id, slug, stem, source_target.relative_to(self.root).as_posix(), prepared_target.relative_to(self.root).as_posix(), digest, source_sha, 0, None, "", "", 1, now, now, None),
            )
            outcome = "created"
        else:
            content_changed = str(old_dict.get("sha256") or "") != digest
            revision = int(old_dict.get("revision") or 1) + (1 if content_changed else 0)
            connection.execute(
                "UPDATE monster_animation_clips SET name=?,source_path=?,prepared_path=?,sha256=?,source_sha256=?,revision=?,updated_at=? WHERE id=?",
                (stem, source_target.relative_to(self.root).as_posix(), prepared_target.relative_to(self.root).as_posix(), digest, source_sha, revision, now, clip_id),
            )
            outcome = "changed" if content_changed else "unchanged"
        connection.execute(
            """INSERT INTO monster_animation_bindings(id,monster_slug,slot,variant,clip_id,weight,looped,priority,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(monster_slug,slot,variant) DO UPDATE SET clip_id=excluded.clip_id,looped=excluded.looped,priority=excluded.priority,updated_at=excluded.updated_at""",
            (binding_id, slug, slot, variant, clip_id, 100, 1 if binding["looped"] else 0, binding["priority"], now, now),
        )
        return outcome, {"filename": source.name, "clipId": clip_id, **binding}

    def scan_folder(self, slug: str, folder: str) -> dict:
        monster = self._monster(slug)
        self._profile(slug)
        root = Path(str(folder or "")).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("choose an existing monster animation folder")
        files = sorted(
            [path.resolve() for path in root.rglob("*") if path.is_file() and path.suffix.lower() in ANIMATION_EXTENSIONS and not self._managed(path.resolve())],
            key=lambda path: path.as_posix().casefold(),
        )
        if len(files) > MAX_SCAN_FILES:
            raise ValueError(f"monster animation scan found more than {MAX_SCAN_FILES} files; choose a narrower folder")
        recognized, unassigned = [], []
        coordinates = {}
        for path in files:
            binding = classify(path, slug)
            if binding is None:
                unassigned.append({"path": str(path), "filename": path.name, "reason": "name does not match a monster animation state"})
                continue
            coordinate = (binding["slot"], int(binding["variant"]))
            if coordinate in coordinates:
                raise ValueError(f"monster animation scan is ambiguous: {coordinates[coordinate].name} and {path.name} map to {coordinate[0]} {coordinate[1]:02d}")
            coordinates[coordinate] = path
            recognized.append((path, binding))
        created = changed = unchanged = 0
        imported = []
        now = time.time()
        with self.connect() as connection:
            for source, binding in recognized:
                outcome, item = self._register(connection, slug, source, binding, now)
                created += outcome == "created"
                changed += outcome == "changed"
                unchanged += outcome == "unchanged"
                imported.append(item)
            connection.execute(
                "UPDATE monster_animation_profiles SET scan_root=?,skeleton_signature=?,updated_at=? WHERE monster_slug=?",
                (str(root), str(monster.get("skeleton_signature") or ""), now, slug),
            )
        self.export()
        return {
            "monsterSlug": slug, "rootPath": str(root), "filesScanned": len(files), "recognized": len(imported),
            "created": created, "changed": changed, "unchanged": unchanged, "items": imported, "unassigned": unassigned,
        }

    def assign_file(self, slug: str, source_path: str, slot: str, variant: int = 0) -> dict:
        self._monster(slug)
        profile = self._profile(slug)
        source = Path(str(source_path or "")).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in ANIMATION_EXTENSIONS:
            raise ValueError("choose an existing .rbxm/.rbxmx monster animation")
        scan_root = str(profile.get("scan_root") or "")
        if scan_root:
            try:
                source.relative_to(Path(scan_root).resolve())
            except ValueError as exc:
                raise ValueError("manual assignment must use a file from the current scan folder") from exc
        slot = _safe_token(slot)
        if slot not in SLOT_BY_NAME:
            raise ValueError(f"unknown monster animation state: {slot}")
        definition = SLOT_BY_NAME[slot]
        variant = max(1, int(variant or 0)) if definition.get("variants") else 0
        binding = {"slot": slot, "variant": variant, **definition}
        now = time.time()
        with self.connect() as connection:
            outcome, item = self._register(connection, slug, source, binding, now)
        self.export()
        return {"monsterSlug": slug, "outcome": outcome, "item": item}

    @staticmethod
    def _status(row: dict) -> str:
        asset = str(row.get("asset_id") or "")
        if not asset:
            return "LOCAL_ONLY"
        return "PUBLISHED" if str(row.get("published_sha256") or "") == str(row.get("sha256") or "") else "CHANGED"

    def list_for_monster(self, slug: str) -> list[dict]:
        if not slug:
            return []
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT b.id AS binding_id,b.monster_slug,b.slot,b.variant,b.clip_id,b.weight,b.looped,b.priority,
                          c.name,c.source_path,c.prepared_path,c.sha256,c.source_sha256,c.duplicate_first_frame_at_end,c.asset_id,c.published_sha256,c.moderation_state,c.revision,c.published_at
                   FROM monster_animation_bindings b JOIN monster_animation_clips c ON c.id=b.clip_id
                   WHERE b.monster_slug=? ORDER BY b.slot,b.variant""",
                (slug,),
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            definition = SLOT_BY_NAME.get(str(value.get("slot") or ""), {})
            value["state"] = str(definition.get("state") or value.get("slot") or "")
            value["role"] = str(definition.get("role") or "base")
            value["status"] = self._status(value)
            value["looped"] = bool(value.get("looped"))
            value["duplicate_first_frame_at_end"] = bool(value.get("duplicate_first_frame_at_end"))
            result.append(value)
        return result

    def snapshot(self, slug: str | None = None) -> dict:
        with self.connect() as connection:
            monsters = [dict(row) for row in connection.execute("SELECT slug,name_en,skeleton_signature FROM monsters ORDER BY name_en,slug")]
        selected = str(slug or "").strip().lower()
        if not selected and monsters:
            selected = str(monsters[0]["slug"])
        items = self.list_for_monster(selected) if selected else []
        profile = self._profile(selected) if selected else None
        monster = next((row for row in monsters if row["slug"] == selected), None)
        compatible = bool(profile and monster and str(profile.get("skeleton_signature") or "") == str(monster.get("skeleton_signature") or ""))
        return {
            "schemaVersion": SCHEMA_VERSION, "project": PROJECT, "monsterSlug": selected, "monsters": monsters,
            "profile": profile, "skeletonCompatible": compatible, "slotCatalog": SLOT_CATALOG,
            "filenameRules": filename_rules(selected), "items": items,
            "summary": {
                "registered": len(items), "published": sum(row["status"] == "PUBLISHED" for row in items),
                "localOnly": sum(row["status"] == "LOCAL_ONLY" for row in items), "changed": sum(row["status"] == "CHANGED" for row in items),
            },
        }

    def set_duplicate_first_frame(self, clip_id: str, enabled: bool) -> dict:
        # Runtime presentation flag only. Never mutate source/prepared animation
        # bytes, publication checksum, revision, or permanent Roblox asset id.
        with self.connect() as connection:
            raw = connection.execute("SELECT monster_slug FROM monster_animation_clips WHERE id=?", (clip_id,)).fetchone()
            if not raw:
                raise ValueError(f"unknown monster animation clip: {clip_id}")
            connection.execute(
                "UPDATE monster_animation_clips SET duplicate_first_frame_at_end=?,updated_at=? WHERE id=?",
                (1 if enabled else 0, time.time(), clip_id),
            )
            slug = str(raw["monster_slug"])
        self.export()
        return self.snapshot(slug)

    def set_weight(self, binding_id: str, weight: int) -> dict:
        weight = max(1, min(10000, int(weight)))
        with self.connect() as connection:
            row = connection.execute("SELECT monster_slug FROM monster_animation_bindings WHERE id=?", (binding_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown monster animation binding: {binding_id}")
            connection.execute("UPDATE monster_animation_bindings SET weight=?,updated_at=? WHERE id=?", (weight, time.time(), binding_id))
            slug = str(row["monster_slug"])
        self.export()
        return self.snapshot(slug)

    def delete_binding(self, binding_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT monster_slug,clip_id FROM monster_animation_bindings WHERE id=?", (binding_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown monster animation binding: {binding_id}")
            slug, clip_id = str(row["monster_slug"]), str(row["clip_id"])
            connection.execute("DELETE FROM monster_animation_bindings WHERE id=?", (binding_id,))
            still = int(connection.execute("SELECT COUNT(*) FROM monster_animation_bindings WHERE clip_id=?", (clip_id,)).fetchone()[0])
            if still == 0:
                connection.execute("DELETE FROM monster_animation_clips WHERE id=? AND (asset_id IS NULL OR asset_id='')", (clip_id,))
        self.export()
        return self.snapshot(slug)

    def publish_clip(self, clip_id: str, credentials: dict) -> dict:
        with self.connect() as connection:
            raw = connection.execute("SELECT * FROM monster_animation_clips WHERE id=?", (clip_id,)).fetchone()
        if not raw:
            raise ValueError(f"unknown monster animation clip: {clip_id}")
        row = dict(raw)
        path = self.root / str(row.get("prepared_path") or "")
        if not path.is_file():
            raise ValueError("registered monster animation file is missing")
        asset_id = str(row.get("asset_id") or "").strip()
        if asset_id:
            if str(row.get("published_sha256") or "") == str(row.get("sha256") or ""):
                return row
            raise ValueError("monster animation changed after publication; preserve the permanent animation asset id and use a version update workflow")
        operation = create_animation_asset(
            path,
            display_name=str(row.get("name") or clip_id),
            description=str(credentials.get("description") or "game1 monster animation"),
            creator_type=str(credentials["creatorType"]), creator_id=str(credentials["creatorId"]), api_key=str(credentials["apiKey"]),
        )
        result = wait_for_operation(operation, api_key=str(credentials["apiKey"]))
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                "UPDATE monster_animation_clips SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?,updated_at=? WHERE id=?",
                (result.asset_id, row["sha256"], result.moderation_state or "", now, now, clip_id),
            )
            connection.execute(
                """INSERT INTO monster_animation_publications(clip_id,clip_revision,asset_id,operation_path,sha256,moderation_state,published_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (clip_id, int(row.get("revision") or 1), result.asset_id, result.operation_path, row["sha256"], result.moderation_state or "", now),
            )
        self.export()
        return {**row, "asset_id": result.asset_id, "published_sha256": row["sha256"], "status": "PUBLISHED"}

    def publish_missing(self, slug: str, credentials: dict) -> dict:
        queue = [row for row in self.list_for_monster(slug) if row["status"] == "LOCAL_ONLY"]
        published, failed = [], []
        for row in queue:
            try:
                published.append(self.publish_clip(str(row["clip_id"]), credentials))
            except Exception as exc:
                failed.append({"clipId": row["clip_id"], "name": row["name"], "error": str(exc)})
                break
        return {"requested": len(queue), "published": published, "failed": failed, "snapshot": self.snapshot(slug)}

    def export(self):
        with self.connect() as connection:
            profiles = [dict(row) for row in connection.execute("SELECT * FROM monster_animation_profiles ORDER BY monster_slug")]
            clips = [dict(row) for row in connection.execute("SELECT * FROM monster_animation_clips ORDER BY monster_slug,name")]
            bindings = [dict(row) for row in connection.execute("SELECT * FROM monster_animation_bindings ORDER BY monster_slug,slot,variant")]
        for row in clips:
            row["status"] = self._status(row)
        manifest_bindings = [{key: value for key, value in row.items() if key != "playback_speed_percent"} for row in bindings]
        payload = {"schemaVersion": SCHEMA_VERSION, "project": PROJECT, "slotCatalog": SLOT_CATALOG, "profiles": profiles, "clips": clips, "bindings": manifest_bindings}
        manifest = self.root / "assets/manifests/monster-animations.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        clips_by_id = {str(row["id"]): row for row in clips if str(row.get("asset_id") or "").isdigit()}
        profiles_map = {str(row["monster_slug"]): {"skeletonSignature": str(row.get("skeleton_signature") or ""), "slots": {}} for row in profiles}
        for binding in bindings:
            clip = clips_by_id.get(str(binding["clip_id"]))
            if not clip:
                continue
            internal_slot = str(binding["slot"])
            definition = SLOT_BY_NAME.get(internal_slot, {})
            state = str(definition.get("state") or internal_slot)
            role = str(definition.get("role") or "base")
            profile = profiles_map.setdefault(str(binding["monster_slug"]), {"skeletonSignature": "", "slots": {}})
            profile["slots"].setdefault(state, []).append({
                "clipId": str(clip["id"]), "assetId": str(clip["asset_id"]), "animationId": "rbxassetid://" + str(clip["asset_id"]),
                "sourceSlot": internal_slot, "role": role, "variant": int(binding["variant"]), "weight": int(binding["weight"]),
                "looped": bool(binding["looped"]), "priority": str(binding["priority"]),
                "duplicateFirstFrameAtEnd": bool(clip.get("duplicate_first_frame_at_end")),
            })
        for profile in profiles_map.values():
            for rows in profile["slots"].values():
                rows.sort(key=lambda row: row["variant"])
        q = lambda value: json.dumps(str(value), ensure_ascii=False)
        lines = ["-- generated. do not edit by hand.", "return table.freeze({", f"\tschemaVersion = {SCHEMA_VERSION},", '\tproject = "game1",', "\tprofiles = table.freeze({"]
        for slug in sorted(profiles_map):
            profile = profiles_map[slug]
            lines += [f"\t\t[{q(slug)}] = table.freeze({{", f"\t\t\tskeletonSignature = {q(profile['skeletonSignature'])},", "\t\t\tslots = table.freeze({"]
            for slot in sorted(profile["slots"]):
                lines.append(f"\t\t\t\t[{q(slot)}] = table.freeze({{")
                for row in profile["slots"][slot]:
                    lines += [
                        "\t\t\t\t\ttable.freeze({",
                        f"\t\t\t\t\t\tclipId = {q(row['clipId'])},",
                        f"\t\t\t\t\t\tassetId = {q(row['assetId'])},",
                        f"\t\t\t\t\t\tanimationId = {q(row['animationId'])},",
                        f"\t\t\t\t\t\tsourceSlot = {q(row['sourceSlot'])},",
                        f"\t\t\t\t\t\trole = {q(row['role'])},",
                        f"\t\t\t\t\t\tvariant = {row['variant']},",
                        f"\t\t\t\t\t\tweight = {row['weight']},",
                        f"\t\t\t\t\t\tlooped = {'true' if row['looped'] else 'false'},",
                        f"\t\t\t\t\t\tpriority = {q(row['priority'])},",
                        f"\t\t\t\t\t\tduplicateFirstFrameAtEnd = {'true' if row['duplicateFirstFrameAtEnd'] else 'false'},",
                        "\t\t\t\t\t}),",
                    ]
                lines.append("\t\t\t\t}),")
            lines += ["\t\t\t}),", "\t\t}),"]
        lines += ["\t}),", "})", ""]
        target = self.root / "src/shared/monster/MonsterAnimationRegistry.luau"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines), encoding="utf-8")
