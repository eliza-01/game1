from __future__ import annotations

from pathlib import Path
import hashlib
import shutil
import sqlite3

from .common import (
    ANIMATION_EXTENSIONS, BASE_SLOT_CATALOG, BOW_EXTRA_SLOTS, MAX_SCAN_FILES, NAMING_EXAMPLES, PROJECT, filename_rule_catalog,
    SCHEMA_VERSION, WEAPON_SETS, WEAPON_SLOT_CATALOG, _binding_id, _canonical_file_stem,
    _catalog_for_weapon, _clip_id, _now, classify_animation, normalize_manual_binding,
)


class AnimationStorageMixin:
    def connect(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS animation_profiles(
                    character_id TEXT PRIMARY KEY,
                    skeleton_signature TEXT NOT NULL DEFAULT '',
                    scan_root TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS animation_clips(
                    id TEXT PRIMARY KEY,
                    character_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    prepared_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    asset_id TEXT,
                    published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    published_at REAL
                );
                CREATE TABLE IF NOT EXISTS animation_bindings(
                    id TEXT PRIMARY KEY,
                    character_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    weapon_set TEXT NOT NULL DEFAULT '',
                    slot TEXT NOT NULL,
                    variant INTEGER NOT NULL DEFAULT 0,
                    clip_id TEXT NOT NULL,
                    weight INTEGER NOT NULL DEFAULT 100,
                    looped INTEGER NOT NULL DEFAULT 0,
                    priority TEXT NOT NULL DEFAULT 'Movement',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(character_id, scope, weapon_set, slot, variant)
                );
                CREATE TABLE IF NOT EXISTS animation_publications(
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

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _sync_character_profiles(self) -> None:
        now = _now()
        with self.connect() as connection:
            characters = connection.execute(
                "SELECT id,skeleton_signature FROM characters ORDER BY id"
            ).fetchall()
            for character in characters:
                character_id = str(character["id"] or "").strip().lower()
                if not character_id:
                    continue
                skeleton = str(character["skeleton_signature"] or "")
                existing = connection.execute(
                    "SELECT character_id,skeleton_signature FROM animation_profiles WHERE character_id=?",
                    (character_id,),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO animation_profiles(character_id,skeleton_signature,scan_root,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (character_id, skeleton, "", now, now),
                    )
                elif str(existing["skeleton_signature"] or "") != skeleton:
                    connection.execute(
                        "UPDATE animation_profiles SET skeleton_signature=?,updated_at=? WHERE character_id=?",
                        (skeleton, now, character_id),
                    )

    def _character(self, character_id: str) -> dict:
        character_id = str(character_id or "").strip().lower()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM characters WHERE id=?", (character_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown character archetype: {character_id}")
        return dict(row)

    def _profile(self, character_id: str) -> dict:
        character = self._character(character_id)
        now = _now()
        skeleton = str(character.get("skeleton_signature") or "")
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM animation_profiles WHERE character_id=?", (character_id,)).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO animation_profiles(character_id,skeleton_signature,scan_root,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (character_id, skeleton, "", now, now),
                )
            elif str(row["skeleton_signature"] or "") != skeleton:
                connection.execute(
                    "UPDATE animation_profiles SET skeleton_signature=?,updated_at=? WHERE character_id=?",
                    (skeleton, now, character_id),
                )
        with self.connect() as connection:
            return dict(connection.execute("SELECT * FROM animation_profiles WHERE character_id=?", (character_id,)).fetchone())

    def character_usage(self, character_id: str) -> dict:
        character_id = str(character_id or "").strip().lower()
        with self.connect() as connection:
            clips = int(connection.execute("SELECT COUNT(*) FROM animation_clips WHERE character_id=?", (character_id,)).fetchone()[0])
            bindings = int(connection.execute("SELECT COUNT(*) FROM animation_bindings WHERE character_id=?", (character_id,)).fetchone()[0])
        return {"characterId": character_id, "clips": clips, "bindings": bindings}

    def delete_empty_profile(self, character_id: str) -> None:
        usage = self.character_usage(character_id)
        if usage["clips"] or usage["bindings"]:
            raise ValueError(
                f"cannot delete character {character_id}: animation profile still owns "
                f"{usage['clips']} clip(s) and {usage['bindings']} binding(s)"
            )
        with self.connect() as connection:
            connection.execute("DELETE FROM animation_profiles WHERE character_id=?", (str(character_id or "").strip().lower(),))
        self.export()

    def _is_managed_animation_path(self, path: Path) -> bool:
        for root in (self.root / "assets/source/characters", self.root / "assets/prepared/characters"):
            try:
                path.relative_to(root.resolve())
                return True
            except ValueError:
                pass
        return False

    def _canonical_paths(self, character: dict, binding: dict, suffix: str) -> tuple[Path, Path]:
        race = str(character.get("race") or "")
        gender = str(character.get("gender") or "")
        character_id = str(character.get("id") or "")
        scope = binding["scope"]
        weapon_set = binding["weaponSet"]
        slot = binding["slot"]
        variant = int(binding["variant"])
        stem = _canonical_file_stem(scope, weapon_set, slot, variant)
        if scope == "base":
            relative = Path("characters") / race / gender / character_id / "animations" / "base" / f"{stem}{suffix}"
        else:
            relative = Path("characters") / race / gender / character_id / "animations" / "weapons" / weapon_set / f"{stem}{suffix}"
        return self.root / "assets/source" / relative, self.root / "assets/prepared" / relative

    def _register_source(self, connection, character: dict, source: Path, binding: dict, now: float) -> tuple[str, dict]:
        character_id = str(character.get("id") or "")
        clip_id = _clip_id(character_id, binding["scope"], binding["weaponSet"], binding["slot"], int(binding["variant"]))
        binding_id = _binding_id(character_id, binding["scope"], binding["weaponSet"], binding["slot"], int(binding["variant"]))
        source_path, prepared_path = self._canonical_paths(character, binding, source.suffix.lower())
        source_path.parent.mkdir(parents=True, exist_ok=True)
        prepared_path.parent.mkdir(parents=True, exist_ok=True)
        sha = self._sha256(source)
        old = connection.execute("SELECT * FROM animation_clips WHERE id=?", (clip_id,)).fetchone()
        old_dict = dict(old) if old else None
        same = bool(old_dict and str(old_dict.get("sha256") or "") == sha)

        if not same:
            shutil.copy2(source, source_path)
            shutil.copy2(source, prepared_path)
        elif not source_path.is_file() or not prepared_path.is_file():
            shutil.copy2(source, source_path)
            shutil.copy2(source, prepared_path)

        relative_source = source_path.relative_to(self.root).as_posix()
        relative_prepared = prepared_path.relative_to(self.root).as_posix()
        clip_name = _canonical_file_stem(binding["scope"], binding["weaponSet"], binding["slot"], int(binding["variant"]))
        if old_dict is None:
            connection.execute(
                """INSERT INTO animation_clips(
                    id,character_id,name,source_path,prepared_path,sha256,asset_id,published_sha256,
                    moderation_state,revision,created_at,updated_at,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (clip_id, character_id, clip_name, relative_source, relative_prepared, sha, None, "", "", 1, now, now, None),
            )
            outcome = "created"
        else:
            revision = int(old_dict.get("revision") or 1) + (0 if same else 1)
            connection.execute(
                """UPDATE animation_clips SET name=?,source_path=?,prepared_path=?,sha256=?,revision=?,updated_at=? WHERE id=?""",
                (clip_name, relative_source, relative_prepared, sha, revision, now, clip_id),
            )
            outcome = "unchanged" if same else "changed"

        connection.execute(
            """INSERT INTO animation_bindings(
                id,character_id,scope,weapon_set,slot,variant,clip_id,weight,looped,priority,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(character_id,scope,weapon_set,slot,variant) DO UPDATE SET
                clip_id=excluded.clip_id,
                looped=excluded.looped,
                priority=excluded.priority,
                updated_at=excluded.updated_at""",
            (
                binding_id,
                character_id,
                binding["scope"],
                binding["weaponSet"],
                binding["slot"],
                int(binding["variant"]),
                clip_id,
                100,
                1 if binding["looped"] else 0,
                binding["priority"],
                now,
                now,
            ),
        )
        return outcome, {"filename": source.name, "clipId": clip_id, **binding}

    def assign_file(self, character_id: str, source_path: str, scope: str, weapon_set: str, slot: str, variant: int = 0) -> dict:
        character = self._character(character_id)
        profile = self._profile(character_id)
        source = Path(str(source_path or "")).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in ANIMATION_EXTENSIONS:
            raise ValueError("choose an existing .rbxm/.rbxmx animation file")
        if self._is_managed_animation_path(source):
            raise ValueError("managed animation files cannot be manually re-imported")
        scan_root = str(profile.get("scan_root") or "").strip()
        if scan_root:
            try:
                source.relative_to(Path(scan_root).resolve())
            except ValueError as error:
                raise ValueError("manual assignment must use a file from the current scan folder") from error

        binding = normalize_manual_binding(scope, weapon_set, slot, variant)
        now = _now()
        with self.connect() as connection:
            outcome, imported = self._register_source(connection, character, source, binding, now)
            connection.execute(
                "UPDATE animation_profiles SET skeleton_signature=?,updated_at=? WHERE character_id=?",
                (str(character.get("skeleton_signature") or ""), now, character_id),
            )
        self.export()
        return {"characterId": character_id, "outcome": outcome, "item": imported}

    def scan_folder(self, character_id: str, folder: str) -> dict:
        character = self._character(character_id)
        self._profile(character_id)
        root = Path(str(folder or "")).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("choose an existing animation folder")

        files = sorted(
            [
                path.resolve()
                for path in root.rglob("*")
                if path.is_file()
                and path.suffix.lower() in ANIMATION_EXTENSIONS
                and not self._is_managed_animation_path(path.resolve())
            ],
            key=lambda path: path.as_posix().casefold(),
        )
        if len(files) > MAX_SCAN_FILES:
            raise ValueError(f"animation scan found more than {MAX_SCAN_FILES} files; choose a narrower folder")

        recognized = []
        unassigned = []
        coordinate_sources: dict[tuple, Path] = {}
        for path in files:
            classification = classify_animation(path, character_id)
            if classification is None:
                unassigned.append({"path": str(path), "filename": path.name, "reason": "name does not match a registered semantic slot"})
                continue
            coordinate = (
                classification["scope"],
                classification["weaponSet"],
                classification["slot"],
                int(classification["variant"]),
            )
            if coordinate in coordinate_sources:
                raise ValueError(
                    "animation scan is ambiguous: "
                    + f"{coordinate_sources[coordinate].name} and {path.name} map to "
                    + "/".join(str(part) for part in coordinate if str(part) != "")
                )
            coordinate_sources[coordinate] = path
            recognized.append((path, classification))

        imported = []
        unchanged = 0
        changed = 0
        created = 0
        now = _now()
        with self.connect() as connection:
            for source, binding in recognized:
                outcome, item = self._register_source(connection, character, source, binding, now)
                if outcome == "created":
                    created += 1
                elif outcome == "changed":
                    changed += 1
                else:
                    unchanged += 1
                imported.append(item)

            connection.execute(
                "UPDATE animation_profiles SET scan_root=?,skeleton_signature=?,updated_at=? WHERE character_id=?",
                (str(root), str(character.get("skeleton_signature") or ""), now, character_id),
            )

        self.export()
        return {
            "characterId": character_id,
            "rootPath": str(root),
            "filesScanned": len(files),
            "recognized": len(recognized),
            "created": created,
            "changed": changed,
            "unchanged": unchanged,
            "unassigned": unassigned,
            "items": imported,
        }

    @staticmethod
    def _status(row: dict) -> str:
        source = str(row.get("prepared_path") or "")
        if not source:
            return "MISSING"
        asset = str(row.get("asset_id") or "")
        if not asset:
            return "LOCAL_ONLY"
        if str(row.get("published_sha256") or "") == str(row.get("sha256") or ""):
            return "PUBLISHED"
        return "CHANGED"

    def list_for_character(self, character_id: str) -> list[dict]:
        self._profile(character_id)
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT b.id AS binding_id,b.character_id,b.scope,b.weapon_set,b.slot,b.variant,b.clip_id,b.weight,b.looped,b.priority,
                          c.name,c.source_path,c.prepared_path,c.sha256,c.asset_id,c.published_sha256,
                          c.moderation_state,c.revision,c.published_at
                   FROM animation_bindings b JOIN animation_clips c ON c.id=b.clip_id
                   WHERE b.character_id=?
                   ORDER BY CASE b.scope WHEN 'base' THEN 0 ELSE 1 END,b.weapon_set,b.slot,b.variant""",
                (character_id,),
            ).fetchall()
        result = []
        for raw in rows:
            row = dict(raw)
            row["status"] = self._status(row)
            row["looped"] = bool(row.get("looped"))
            row["animationId"] = f"rbxassetid://{row['asset_id']}" if str(row.get("asset_id") or "").isdigit() else ""
            result.append(row)
        return result

    def snapshot(self, character_id: str | None = None) -> dict:
        with self.connect() as connection:
            characters = [dict(row) for row in connection.execute("SELECT id,display_name,race,gender,skeleton_signature FROM characters ORDER BY race,gender,id")]
        selected = str(character_id or "").strip().lower()
        if not selected and characters:
            selected = str(characters[0]["id"])
        items = self.list_for_character(selected) if selected else []
        profile = self._profile(selected) if selected else None
        character = next((row for row in characters if row["id"] == selected), None)
        compatible = bool(profile and character and str(profile.get("skeleton_signature") or "") == str(character.get("skeleton_signature") or ""))
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "characterId": selected,
            "characters": characters,
            "profile": profile,
            "skeletonCompatible": compatible,
            "weaponSets": list(WEAPON_SETS),
            "namingExamples": list(NAMING_EXAMPLES),
            "filenameRules": filename_rule_catalog(selected),
            "slotCatalog": {
                "base": BASE_SLOT_CATALOG,
                "weapon": {weapon_set: list(_catalog_for_weapon(weapon_set).values()) for weapon_set in WEAPON_SETS},
            },
            "items": items,
            "summary": {
                "registered": len(items),
                "published": sum(row["status"] == "PUBLISHED" for row in items),
                "localOnly": sum(row["status"] == "LOCAL_ONLY" for row in items),
                "changed": sum(row["status"] == "CHANGED" for row in items),
            },
        }

    def clip(self, clip_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT b.id AS binding_id,b.character_id,b.scope,b.weapon_set,b.slot,b.variant,b.clip_id,b.weight,b.looped,b.priority,
                          c.name,c.source_path,c.prepared_path,c.sha256,c.asset_id,c.published_sha256,
                          c.moderation_state,c.revision,c.published_at
                   FROM animation_bindings b JOIN animation_clips c ON c.id=b.clip_id WHERE c.id=?""",
                (clip_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"unknown animation clip: {clip_id}")
        value = dict(row)
        value["status"] = self._status(value)
        value["looped"] = bool(value.get("looped"))
        return value

    def set_weight(self, binding_id: str, weight: int) -> dict:
        weight = max(1, min(10000, int(weight)))
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM animation_bindings WHERE id=?", (binding_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown animation binding: {binding_id}")
            connection.execute("UPDATE animation_bindings SET weight=?,updated_at=? WHERE id=?", (weight, _now(), binding_id))
            character_id = str(row["character_id"])
        self.export()
        return self.snapshot(character_id)

    def delete_binding(self, binding_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM animation_bindings WHERE id=?", (binding_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown animation binding: {binding_id}")
            character_id = str(row["character_id"])
            clip_id = str(row["clip_id"])
            connection.execute("DELETE FROM animation_bindings WHERE id=?", (binding_id,))
            other = connection.execute("SELECT 1 FROM animation_bindings WHERE clip_id=? LIMIT 1", (clip_id,)).fetchone()
            if other is None:
                connection.execute("DELETE FROM animation_clips WHERE id=?", (clip_id,))
        self.export()
        return self.snapshot(character_id)
