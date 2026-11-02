from __future__ import annotations

from pathlib import Path
import sqlite3
import time

# Re-export legacy module constants and skeleton validator for existing consumers.
from character_core.archetype_contract import (
    SCHEMA_VERSION, PROJECT, STAT_KEYS, DEFAULT_STATS, ID_RE,
    ACTIVE_KEY, RACES, GENDERS, CHARACTER_PUBLICATION_PIPELINE,
)
from character_core.model_workflow import CharacterModelWorkflowMixin, _assert_publication_skeleton_matches
from character_core.registry_export import CharacterRegistryExportMixin


class CharacterStore(CharacterModelWorkflowMixin, CharacterRegistryExportMixin):
    def __init__(self, root: Path):
        self.assemblies = None
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
                """CREATE TABLE IF NOT EXISTS character_stats(
                  character_id TEXT NOT NULL,
                  stat_key TEXT NOT NULL,
                  value REAL NOT NULL DEFAULT 0,
                  PRIMARY KEY(character_id, stat_key)
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
            self._ensure_column(connection, "characters", "publication_pipeline", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "model_replacement_pending", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "characters", "moderation_state", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "characters", "published_at", "REAL")

    def options(self):
        return {"races": list(RACES), "genders": list(GENDERS), "statKeys": list(STAT_KEYS), "defaultStats": dict(DEFAULT_STATS)}

    @staticmethod
    def _number(value):
        number = float(value)
        return int(number) if number.is_integer() else number

    def _stats(self, connection, character_id: str) -> dict:
        values = dict(DEFAULT_STATS)
        for row in connection.execute(
            "SELECT stat_key,value FROM character_stats WHERE character_id=? ORDER BY stat_key", (character_id,)
        ):
            values[str(row["stat_key"])] = self._number(row["value"])
        return values

    def _decorate(self, connection, row):
        if row is None:
            return None
        result = dict(row)
        result["stats"] = self._stats(connection, str(result["id"]))
        if result.get('visual_mode') == 'assembly' and self.assemblies:
            return self.assemblies.decorate(result)
        return result

    def list(self):
        with self.connect() as connection:
            return [self._decorate(connection, row) for row in connection.execute("SELECT * FROM characters ORDER BY race,gender,id")]

    def get(self, character_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM characters WHERE id=?", (character_id,)).fetchone()
            return self._decorate(connection, row)

    @staticmethod
    def _validate_stats(payload: dict, previous: dict | None = None) -> dict:
        incoming = payload.get("stats") if isinstance(payload, dict) else None
        incoming = incoming if isinstance(incoming, dict) else payload if isinstance(payload, dict) else {}
        old = (previous or {}).get("stats") or {}
        result = {}
        for key, default in DEFAULT_STATS.items():
            raw = incoming[key] if key in incoming else old.get(key, default)
            value = float(raw)
            if key == "Level" and value < 1:
                raise ValueError("character Level must be at least 1")
            if key in {"MaxHP", "Damage", "Defense", "AttackSpeed", "RunSpeed"} and value < 0:
                raise ValueError(f"character {key} cannot be negative")
            if key == "CritChance" and not 0 <= value <= 100:
                raise ValueError("character CritChance must be between 0 and 100")
            result[key] = value
        return result

    def set_stats(self, character_id: str, payload: dict):
        row = self.get(character_id)
        if not row:
            raise ValueError(f"unknown character archetype: {character_id}")
        if row.get('visual_mode') == 'assembly':
            raise ValueError('edit starting stats in the assembly editor')
        stats = self._validate_stats(payload, row)
        with self.connect() as connection:
            for key, value in stats.items():
                connection.execute(
                    "INSERT OR REPLACE INTO character_stats(character_id,stat_key,value) VALUES(?,?,?)",
                    (character_id, key, value),
                )
            connection.execute("UPDATE characters SET updated_at=? WHERE id=?", (time.time(), character_id))
        self.export()
        return self.snapshot()

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
        if row.get('visual_mode') == 'assembly':
            if not row.get('assembly_resolved', {}).get('ready'):
                raise ValueError('publish all selected assembly dependencies before activating it')
        elif not str(row.get("model_asset_id") or "").strip():
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
        if row.get('visual_mode') == 'assembly':
            return row.get('status') or 'ASSEMBLY_DRAFT'
        source = str(row.get("source_path") or "")
        asset_id = str(row.get("model_asset_id") or "")
        sha = str(row.get("sha256") or "")
        published_sha = str(row.get("published_sha256") or "")
        published_pipeline = str(row.get("publication_pipeline") or "")
        if not source or not str(row.get("race") or "") or not str(row.get("gender") or ""):
            return "INCOMPLETE"
        if not asset_id:
            return "REGISTERED"
        if (
            sha
            and published_sha
            and sha == published_sha
            and published_pipeline == CHARACTER_PUBLICATION_PIPELINE
        ):
            return "PUBLISHED"
        return "CHANGED"
