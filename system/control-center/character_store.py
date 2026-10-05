from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import shutil
import sqlite3
import time
import tempfile

from character_analysis import analyze_character_fbx, prepare_character_fbx
from opencloud_assets import create_model_asset, update_model_asset, wait_for_operation

SCHEMA_VERSION = 3
PROJECT = "game1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ACTIVE_KEY = "active_character_archetype_id"
RACES = ("human",)
GENDERS = ("male", "female")


class CharacterStore:
    def __init__(self, root: Path):
        self.root = root
        self.runtime = root / ".control-center"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.db = self.runtime / "game1.db"
        self._init()
        self.export()

    def connect(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _columns(connection, table: str) -> set[str]:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}

    @staticmethod
    def _ensure_column(connection, table: str, name: str, declaration: str):
        if name not in CharacterStore._columns(connection, table):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def _init(self):
        with self.connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS characters(
                  id TEXT PRIMARY KEY,
                  display_name TEXT NOT NULL,
                  source_path TEXT NOT NULL DEFAULT '',
                  prepared_path TEXT NOT NULL DEFAULT '',
                  sha256 TEXT NOT NULL DEFAULT '',
                  model_asset_id TEXT,
                  status TEXT NOT NULL DEFAULT 'INCOMPLETE',
                  revision INTEGER NOT NULL DEFAULT 1,
                  created_at REAL NOT NULL,
                  updated_at REAL NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS project_settings(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL DEFAULT ''
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS character_publications(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  character_id TEXT NOT NULL,
                  character_revision INTEGER NOT NULL,
                  asset_id TEXT NOT NULL,
                  operation_path TEXT NOT NULL,
                  sha256 TEXT NOT NULL,
                  moderation_state TEXT,
                  published_at REAL NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS character_model_assignments(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  target_character_id TEXT NOT NULL,
                  source_character_id TEXT NOT NULL,
                  asset_id TEXT NOT NULL DEFAULT '',
                  assigned_at REAL NOT NULL
                )"""
            )
            self._ensure_column(connection, "characters", "race", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "gender", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "armature_name", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "bone_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "characters", "mesh_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "characters", "skeleton_signature", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "skeleton_structure_signature", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "skeleton_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(connection, "characters", "published_sha256", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "moderation_state", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "published_at", "REAL")

    def options(self):
        return {"races": list(RACES), "genders": list(GENDERS)}

    def list(self):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM characters ORDER BY race,gender,id")]

    def get(self, character_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM characters WHERE id=?", (character_id,)).fetchone()
            return dict(row) if row else None

    def active_id(self):
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM project_settings WHERE key=?", (ACTIVE_KEY,)).fetchone()
            value = str(row["value"]).strip() if row else ""
            return value or None

    def set_active(self, character_id):
        character_id = str(character_id or "").strip().lower()
        row = self.get(character_id)
        if not row:
            raise ValueError(f"unknown character archetype: {character_id}")
        if not str(row.get("model_asset_id") or "").strip():
            raise ValueError("publish the character model before activating it")
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO project_settings(key,value) VALUES(?,?)",
                (ACTIVE_KEY, character_id),
            )
        self.export()
        return self.snapshot()

    def clear_active(self):
        with self.connect() as connection:
            connection.execute("DELETE FROM project_settings WHERE key=?", (ACTIVE_KEY,))
        self.export()
        return self.snapshot()

    @staticmethod
    def _identity(data, old=None) -> tuple[str, str, str, str]:
        race = str(data.get("race", old.get("race") if old else "") or "").strip().lower()
        gender = str(data.get("gender", old.get("gender") if old else "") or "").strip().lower()
        if race not in RACES:
            raise ValueError("race must be selected from the registered race pool: " + ", ".join(RACES))
        if gender not in GENDERS:
            raise ValueError("gender must be male or female")
        default_id = f"{race}_{gender}"
        character_id = str(data.get("id", old.get("id") if old else default_id) or default_id).strip().lower()
        if not ID_RE.fullmatch(character_id):
            raise ValueError("id must match [a-z0-9][a-z0-9_-]{0,63}")
        display_name = str(data.get("displayName", old.get("display_name") if old else "") or "").strip()
        if not display_name:
            display_name = f"{race.title()} {gender.title()}"
        return character_id, display_name, race, gender

    def _identity_conflict(self, character_id: str, race: str, gender: str):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM characters WHERE race=? AND gender=? AND id<>?",
                (race, gender, character_id),
            ).fetchone()
        if row:
            raise ValueError(f"{race}/{gender} is already registered as {row['id']}")

    @staticmethod
    def _status(row: dict) -> str:
        source = str(row.get("source_path") or "")
        asset_id = str(row.get("model_asset_id") or "")
        sha = str(row.get("sha256") or "")
        published_sha = str(row.get("published_sha256") or "")
        if not source or not str(row.get("race") or "") or not str(row.get("gender") or ""):
            return "INCOMPLETE"
        if not asset_id:
            return "REGISTERED"
        if sha and published_sha and sha == published_sha:
            return "PUBLISHED"
        return "CHANGED"

    def register(self, data):
        expected_existing_id = str(data.get("existingId") or "").strip().lower()
        seed_old = self.get(expected_existing_id) if expected_existing_id else None
        character_id, display_name, race, gender = self._identity(data, seed_old)

        if expected_existing_id:
            if not seed_old:
                raise ValueError(f"unknown archetype revision target: {expected_existing_id}")
            if character_id != expected_existing_id:
                raise ValueError("save archetype identity before registering a model revision")
            old = seed_old
        else:
            old = self.get(character_id)
            if old:
                raise ValueError(
                    f"archetype {character_id} already exists; select that row to register a new model revision"
                )

        self._identity_conflict(character_id, race, gender)

        raw_source = str(data.get("sourcePath", "")).strip()
        if not raw_source and not old:
            raise ValueError("choose an FBX with a skinned armature before registering the character")

        source = str(old.get("source_path") or "") if old else ""
        prepared = str(old.get("prepared_path") or "") if old else ""
        sha = str(old.get("sha256") or "") if old else ""
        analysis = json.loads(str(old.get("skeleton_json") or "{}")) if old else {}

        created_files: list[Path] = []
        if raw_source:
            source_file = Path(raw_source).expanduser()
            if not source_file.is_absolute():
                source_file = (self.root / source_file).resolve()
            if not source_file.is_file() or source_file.suffix.lower() != ".fbx":
                raise ValueError(f"select a valid character FBX: {source_file}")

            relative = Path("characters") / race / gender / character_id / "model" / source_file.name
            source_target = self.root / "assets" / "source" / relative
            prepared_target = self.root / "assets" / "prepared" / relative
            source_digest = hashlib.sha256(source_file.read_bytes()).hexdigest()

            with tempfile.TemporaryDirectory(prefix="game1-character-prepare-") as tmp:
                prepared_candidate = Path(tmp) / source_file.name
                prepare_character_fbx(self.root, source_file, prepared_candidate)
                analysis = analyze_character_fbx(self.root, prepared_candidate)
                prepared_digest = hashlib.sha256(prepared_candidate.read_bytes()).hexdigest()

                revision_stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
                for label, destination, incoming, digest in (
                    ("source", source_target, source_file, source_digest),
                    ("prepared", prepared_target, prepared_candidate, prepared_digest),
                ):
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        existing = hashlib.sha256(destination.read_bytes()).hexdigest()
                        if existing != digest:
                            archive = (
                                self.root
                                / "assets"
                                / "reimported"
                                / "characters"
                                / race
                                / gender
                                / character_id
                                / revision_stamp
                                / label
                                / destination.name
                            )
                            archive.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(destination, archive)
                            destination.unlink()
                        else:
                            continue
                    shutil.copy2(incoming, destination)
                    created_files.append(destination)

            source = source_target.relative_to(self.root).as_posix()
            prepared = prepared_target.relative_to(self.root).as_posix()
            sha = prepared_digest

        now = time.time()
        revision = (int(old["revision"]) + 1) if old else 1
        created_at = old["created_at"] if old else now
        values = {
            "id": character_id,
            "display_name": display_name,
            "race": race,
            "gender": gender,
            "source_path": source,
            "prepared_path": prepared,
            "sha256": sha,
            "model_asset_id": old.get("model_asset_id") if old else None,
            "published_sha256": str(old.get("published_sha256") or "") if old else "",
            "moderation_state": str(old.get("moderation_state") or "") if old else "",
            "published_at": old.get("published_at") if old else None,
            "armature_name": str(analysis.get("armature") or ""),
            "bone_count": int(analysis.get("boneCount") or 0),
            "mesh_count": int(analysis.get("meshCount") or 0),
            "skeleton_signature": str(analysis.get("skeletonSignature") or ""),
            "skeleton_structure_signature": str(analysis.get("skeletonStructureSignature") or ""),
            "skeleton_json": json.dumps(analysis, ensure_ascii=False, separators=(",", ":")),
            "revision": revision,
            "created_at": created_at,
            "updated_at": now,
        }
        values["status"] = self._status(values)

        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO characters(
                  id,display_name,race,gender,source_path,prepared_path,sha256,model_asset_id,
                  status,revision,created_at,updated_at,armature_name,bone_count,mesh_count,
                  skeleton_signature,skeleton_structure_signature,skeleton_json,published_sha256,
                  moderation_state,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    values["id"], values["display_name"], values["race"], values["gender"],
                    values["source_path"], values["prepared_path"], values["sha256"], values["model_asset_id"],
                    values["status"], values["revision"], values["created_at"], values["updated_at"],
                    values["armature_name"], values["bone_count"], values["mesh_count"],
                    values["skeleton_signature"], values["skeleton_structure_signature"], values["skeleton_json"],
                    values["published_sha256"], values["moderation_state"], values["published_at"],
                ),
            )
        self.export()
        return self.get(character_id)

    def assign_model(self, target_character_id: str, source_character_id: str):
        target_id = str(target_character_id or "").strip().lower()
        source_id = str(source_character_id or "").strip().lower()
        target = self.get(target_id)
        source = self.get(source_id)
        if not target:
            raise ValueError(f"unknown target archetype: {target_id}")
        if not source:
            raise ValueError(f"unknown source archetype: {source_id}")
        if target_id == source_id:
            return target

        source_path = self.root / str(source.get("source_path") or "")
        prepared_path = self.root / str(source.get("prepared_path") or "")
        if not source_path.is_file() or not prepared_path.is_file():
            raise ValueError("selected registered model is missing its canonical source/prepared files")

        race = str(target.get("race") or "")
        gender = str(target.get("gender") or "")
        target_source = self.root / "assets/source/characters" / race / gender / target_id / "model" / source_path.name
        target_prepared = self.root / "assets/prepared/characters" / race / gender / target_id / "model" / prepared_path.name
        revision_stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())

        def archive_old(stored_path: str, label: str):
            value = str(stored_path or "").strip()
            if not value:
                return
            old_path = (self.root / value).resolve()
            if not old_path.is_file():
                return
            if old_path in {source_path.resolve(), prepared_path.resolve()}:
                return
            archive = (
                self.root
                / "assets/reimported/characters"
                / race
                / gender
                / target_id
                / revision_stamp
                / "model-reassignment"
                / label
                / old_path.name
            )
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                shutil.copy2(old_path, archive)

        archive_old(str(target.get("source_path") or ""), "source")
        archive_old(str(target.get("prepared_path") or ""), "prepared")

        for incoming, destination in ((source_path, target_source), (prepared_path, target_prepared)):
            destination.parent.mkdir(parents=True, exist_ok=True)
            if incoming.resolve() == destination.resolve():
                continue
            if destination.exists():
                incoming_sha = hashlib.sha256(incoming.read_bytes()).hexdigest()
                destination_sha = hashlib.sha256(destination.read_bytes()).hexdigest()
                if incoming_sha != destination_sha:
                    archive = (
                        self.root
                        / "assets/reimported/characters"
                        / race
                        / gender
                        / target_id
                        / revision_stamp
                        / "model-reassignment"
                        / "replaced"
                        / destination.name
                    )
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, archive)
            shutil.copy2(incoming, destination)

        now = time.time()
        values = {
            "source_path": target_source.relative_to(self.root).as_posix(),
            "prepared_path": target_prepared.relative_to(self.root).as_posix(),
            "sha256": str(source.get("sha256") or ""),
            "model_asset_id": source.get("model_asset_id"),
            "published_sha256": str(source.get("published_sha256") or ""),
            "moderation_state": str(source.get("moderation_state") or ""),
            "published_at": source.get("published_at"),
            "armature_name": str(source.get("armature_name") or ""),
            "bone_count": int(source.get("bone_count") or 0),
            "mesh_count": int(source.get("mesh_count") or 0),
            "skeleton_signature": str(source.get("skeleton_signature") or ""),
            "skeleton_structure_signature": str(source.get("skeleton_structure_signature") or ""),
            "skeleton_json": str(source.get("skeleton_json") or "{}"),
        }
        status_probe = {**target, **values}
        status = self._status(status_probe)
        with self.connect() as connection:
            connection.execute(
                """UPDATE characters SET
                   source_path=?,prepared_path=?,sha256=?,model_asset_id=?,published_sha256=?,
                   moderation_state=?,published_at=?,armature_name=?,bone_count=?,mesh_count=?,
                   skeleton_signature=?,skeleton_structure_signature=?,skeleton_json=?,status=?,
                   revision=revision+1,updated_at=? WHERE id=?""",
                (
                    values["source_path"], values["prepared_path"], values["sha256"], values["model_asset_id"],
                    values["published_sha256"], values["moderation_state"], values["published_at"],
                    values["armature_name"], values["bone_count"], values["mesh_count"],
                    values["skeleton_signature"], values["skeleton_structure_signature"], values["skeleton_json"],
                    status, now, target_id,
                ),
            )
            connection.execute(
                "INSERT INTO character_model_assignments(target_character_id,source_character_id,asset_id,assigned_at) VALUES(?,?,?,?)",
                (target_id, source_id, str(source.get("model_asset_id") or ""), now),
            )

        for stored_path, replacement in (
            (str(target.get("source_path") or ""), target_source),
            (str(target.get("prepared_path") or ""), target_prepared),
        ):
            if not stored_path:
                continue
            old_path = (self.root / stored_path).resolve()
            if old_path == replacement.resolve() or old_path in {source_path.resolve(), prepared_path.resolve()}:
                continue
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                pass

        self.export()
        return self.get(target_id)

    def publish(self, character_id: str, publication: dict):
        character_id = str(character_id or "").strip().lower()
        row = self.get(character_id)
        if not row:
            raise ValueError(f"unknown character archetype: {character_id}")
        prepared = self.root / str(row.get("prepared_path") or "")
        if not prepared.is_file():
            raise ValueError("canonical prepared FBX is missing; re-register the model")

        api_key = str(publication.get("apiKey") or "").strip()
        creator_type = str(publication.get("creatorType") or "").strip().lower()
        creator_id = str(publication.get("creatorId") or "").strip()
        description = str(publication.get("description") or "game1 character model").strip()
        current_asset_id = str(row.get("model_asset_id") or "").strip()

        if current_asset_id:
            operation = update_model_asset(
                prepared,
                asset_id=current_asset_id,
                display_name=row["display_name"],
                description=description,
                creator_type=creator_type,
                creator_id=creator_id,
                api_key=api_key,
            )
        else:
            operation = create_model_asset(
                prepared,
                display_name=row["display_name"],
                description=description,
                creator_type=creator_type,
                creator_id=creator_id,
                api_key=api_key,
            )

        result = wait_for_operation(operation, api_key=api_key)
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                """UPDATE characters SET model_asset_id=?,published_sha256=?,moderation_state=?,published_at=?,updated_at=?
                   WHERE id=?""",
                (result.asset_id, row["sha256"], result.moderation_state or "", now, now, character_id),
            )
            connection.execute(
                """INSERT INTO character_publications(
                     character_id,character_revision,asset_id,operation_path,sha256,moderation_state,published_at
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    character_id,
                    int(row["revision"]),
                    result.asset_id,
                    result.operation_path,
                    row["sha256"],
                    result.moderation_state or "",
                    now,
                ),
            )
            updated = connection.execute("SELECT * FROM characters WHERE id=?", (character_id,)).fetchone()
            updated_dict = dict(updated)
            connection.execute("UPDATE characters SET status=? WHERE id=?", (self._status(updated_dict), character_id))
        self.export()
        return self.get(character_id)

    def publications(self, character_id: str):
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM character_publications WHERE character_id=? ORDER BY id DESC",
                    (character_id,),
                )
            ]

    def delete(self, character_id):
        character_id = str(character_id or "").strip().lower()
        with self.connect() as connection:
            connection.execute("DELETE FROM characters WHERE id=?", (character_id,))
            connection.execute("DELETE FROM character_publications WHERE character_id=?", (character_id,))
            connection.execute("DELETE FROM character_model_assignments WHERE target_character_id=? OR source_character_id=?", (character_id, character_id))
            connection.execute("DELETE FROM project_settings WHERE key=? AND value=?", (ACTIVE_KEY, character_id))
        self.export()

    def runtime_selection(self):
        active_id = self.active_id()
        if not active_id:
            return {"mode": "bootstrap", "activeArchetypeId": None, "reason": "no active archetype selected"}
        row = self.get(active_id)
        if not row:
            return {"mode": "bootstrap", "activeArchetypeId": None, "reason": "active archetype is missing"}
        asset_id = str(row.get("model_asset_id") or "").strip()
        if not asset_id:
            return {
                "mode": "bootstrap",
                "activeArchetypeId": active_id,
                "reason": "active archetype has no published model asset id",
            }
        return {
            "mode": "registered",
            "activeArchetypeId": active_id,
            "displayName": row["display_name"],
            "race": row.get("race") or "",
            "gender": row.get("gender") or "",
            "modelAssetId": asset_id,
        }

    def snapshot(self):
        return {
            "schemaVersion": SCHEMA_VERSION,
            "items": self.list(),
            "activeArchetypeId": self.active_id(),
            "runtime": self.runtime_selection(),
            "options": self.options(),
        }

    def export(self):
        rows = []
        for row in self.list():
            try:
                analysis = json.loads(str(row.get("skeleton_json") or "{}"))
            except Exception:
                analysis = {}
            rows.append(
                {
                    "id": row["id"],
                    "displayName": row["display_name"],
                    "race": row.get("race") or "",
                    "gender": row.get("gender") or "",
                    "status": self._status(row),
                    "revision": row["revision"],
                    "model": {
                        "sourcePath": row["source_path"],
                        "preparedPath": row["prepared_path"],
                        "sha256": row["sha256"],
                        "assetId": row["model_asset_id"],
                        "publishedSha256": row.get("published_sha256") or "",
                        "moderationState": row.get("moderation_state") or "",
                    },
                    "skeleton": {
                        "armature": row.get("armature_name") or "",
                        "boneCount": int(row.get("bone_count") or 0),
                        "meshCount": int(row.get("mesh_count") or 0),
                        "signature": row.get("skeleton_signature") or "",
                        "structureSignature": row.get("skeleton_structure_signature") or "",
                        "bones": analysis.get("bones") or [],
                    },
                }
            )

        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "racePool": list(RACES),
            "genderPool": list(GENDERS),
            "activeArchetypeId": self.active_id(),
            "archetypes": rows,
        }
        manifest = self.root / "assets/manifests/character-archetypes.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        def lua(value):
            if value is None:
                return "nil"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            return json.dumps(str(value), ensure_ascii=False)

        lines = [
            "-- generated. do not edit by hand.",
            "return table.freeze({",
            f"\tschemaVersion = {SCHEMA_VERSION},",
            '\tproject = "game1",',
            f"\tactiveArchetypeId = {lua(self.active_id())},",
            "\tarchetypes = {",
        ]
        for row in rows:
            model = row["model"]
            skeleton = row["skeleton"]
            lines += [
                "\t\ttable.freeze({",
                f'\t\t\tid = {lua(row["id"])},',
                f'\t\t\tdisplayName = {lua(row["displayName"])},',
                f'\t\t\trace = {lua(row["race"])},',
                f'\t\t\tgender = {lua(row["gender"])},',
                f'\t\t\tstatus = {lua(row["status"])},',
                f'\t\t\trevision = {row["revision"]},',
                "\t\t\tmodel = table.freeze({",
                f'\t\t\t\tassetId = {lua(model["assetId"])},',
                f'\t\t\t\tsourcePath = {lua(model["sourcePath"])},',
                f'\t\t\t\tsha256 = {lua(model["sha256"])},',
                "\t\t\t}),",
                "\t\t\tskeleton = table.freeze({",
                f'\t\t\t\tarmature = {lua(skeleton["armature"])},',
                f'\t\t\t\tboneCount = {skeleton["boneCount"]},',
                f'\t\t\t\tmeshCount = {skeleton["meshCount"]},',
                f'\t\t\t\tsignature = {lua(skeleton["signature"])},',
                "\t\t\t}),",
                "\t\t}),",
            ]
        lines += ["\t},", "})", ""]
        (self.root / "src/shared/character").mkdir(parents=True, exist_ok=True)
        (self.root / "src/shared/character/CharacterRegistry.luau").write_text("\n".join(lines), encoding="utf-8")
        return payload
