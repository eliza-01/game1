from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import shutil
import sqlite3
import time

SCHEMA_VERSION = 2
PROJECT = "game1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ACTIVE_KEY = "active_character_archetype_id"


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
                  status TEXT NOT NULL DEFAULT 'ARCHETYPE_ONLY',
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

    def list(self):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM characters ORDER BY id")]

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
        if not self.get(character_id):
            raise ValueError(f"unknown character archetype: {character_id}")
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
    def _status(source_path: str, asset_id: str | None) -> str:
        if asset_id:
            return "PUBLISHED"
        if source_path:
            return "SOURCE_ONLY"
        return "ARCHETYPE_ONLY"

    def put(self, data):
        character_id = str(data.get("id", "")).strip().lower()
        display_name = str(data.get("displayName", "")).strip()
        if not ID_RE.fullmatch(character_id):
            raise ValueError("id must match [a-z0-9][a-z0-9_-]{0,63}")
        if not display_name:
            raise ValueError("displayName is required")

        old = self.get(character_id)
        source = old["source_path"] if old else ""
        prepared = old["prepared_path"] if old else ""
        sha = old["sha256"] if old else ""

        raw_source = str(data.get("sourcePath", "")).strip()
        if raw_source:
            source_file = Path(raw_source).expanduser()
            if not source_file.is_absolute():
                source_file = (self.root / source_file).resolve()
            if not source_file.is_file():
                raise ValueError(f"sourcePath does not exist: {source_file}")
            if source_file.suffix.lower() not in {".fbx", ".obj", ".gltf", ".glb", ".rbxm", ".rbxmx"}:
                raise ValueError("character model must be FBX/OBJ/glTF/RBXM/RBXMX")
            destination = self.root / "assets" / "source" / "characters" / character_id / "model" / source_file.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_file.resolve() != destination.resolve():
                shutil.copy2(source_file, destination)
            source = destination.relative_to(self.root).as_posix()
            prepared = source
            sha = hashlib.sha256(destination.read_bytes()).hexdigest()

        asset_value = data.get("modelAssetId", old["model_asset_id"] if old else None)
        asset_id = str(asset_value or "").strip() or None
        if asset_id and not asset_id.isdigit():
            raise ValueError("modelAssetId must be numeric")

        now = time.time()
        revision = (int(old["revision"]) + 1) if old else 1
        created_at = old["created_at"] if old else now
        status = self._status(source, asset_id)

        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO characters(
                     id,display_name,source_path,prepared_path,sha256,model_asset_id,status,revision,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    character_id,
                    display_name,
                    source,
                    prepared,
                    sha,
                    asset_id,
                    status,
                    revision,
                    created_at,
                    now,
                ),
            )
        self.export()
        return self.get(character_id)

    def delete(self, character_id):
        character_id = str(character_id or "").strip().lower()
        with self.connect() as connection:
            connection.execute("DELETE FROM characters WHERE id=?", (character_id,))
            connection.execute(
                "DELETE FROM project_settings WHERE key=? AND value=?",
                (ACTIVE_KEY, character_id),
            )
        self.export()

    def runtime_selection(self):
        active_id = self.active_id()
        if not active_id:
            return {
                "mode": "bootstrap",
                "activeArchetypeId": None,
                "reason": "no active archetype selected",
            }

        row = self.get(active_id)
        if not row:
            return {
                "mode": "bootstrap",
                "activeArchetypeId": None,
                "reason": "active archetype is missing",
            }

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
            "modelAssetId": asset_id,
        }

    def snapshot(self):
        return {
            "items": self.list(),
            "activeArchetypeId": self.active_id(),
            "runtime": self.runtime_selection(),
        }

    def export(self):
        rows = []
        for row in self.list():
            rows.append(
                {
                    "id": row["id"],
                    "displayName": row["display_name"],
                    "status": row["status"],
                    "revision": row["revision"],
                    "model": {
                        "sourcePath": row["source_path"],
                        "preparedPath": row["prepared_path"],
                        "sha256": row["sha256"],
                        "assetId": row["model_asset_id"],
                    },
                }
            )

        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
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
            lines += [
                "\t\ttable.freeze({",
                f'\t\t\tid = {lua(row["id"])},',
                f'\t\t\tdisplayName = {lua(row["displayName"])},',
                f'\t\t\tstatus = {lua(row["status"])},',
                f'\t\t\trevision = {row["revision"]},',
                "\t\t\tmodel = table.freeze({",
                f'\t\t\t\tassetId = {lua(model["assetId"])},',
                f'\t\t\t\tsourcePath = {lua(model["sourcePath"])},',
                f'\t\t\t\tsha256 = {lua(model["sha256"])},',
                "\t\t\t}),",
                "\t\t}),",
            ]
        lines += ["\t},", "})", ""]
        (self.root / "src/shared/CharacterRegistry.luau").write_text("\n".join(lines), encoding="utf-8")
        return payload
