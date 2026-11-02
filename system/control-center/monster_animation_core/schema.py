"""Monster/NPC animation SQLite schema, migrations and canonical file normalization."""
from __future__ import annotations


from pathlib import Path
import json
import shutil
import time
from animation_retirement import retire_legacy_orphans
from npc_animation_taxonomy import default_compatibility, validate_compatibility

class MonsterAnimationSchemaMixin:
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
                    asset_id TEXT,
                    published_sha256 TEXT NOT NULL DEFAULT '',
                    moderation_state TEXT NOT NULL DEFAULT '',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    content_updated_at REAL NOT NULL DEFAULT 0,
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
                    published_at REAL NOT NULL,
                    asset_version_id TEXT NOT NULL DEFAULT '',
                    version_create_time TEXT NOT NULL DEFAULT '',
                    manual_verified INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            clip_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_clips)")}
            if "source_sha256" not in clip_columns:
                connection.execute("ALTER TABLE monster_animation_clips ADD COLUMN source_sha256 TEXT NOT NULL DEFAULT ''")
            if "content_updated_at" not in clip_columns:
                connection.execute("ALTER TABLE monster_animation_clips ADD COLUMN content_updated_at REAL NOT NULL DEFAULT 0")
            connection.execute("UPDATE monster_animation_clips SET source_sha256=sha256 WHERE source_sha256='' OR source_sha256 IS NULL")
            connection.execute("UPDATE monster_animation_clips SET content_updated_at=updated_at WHERE content_updated_at<=0")
            publication_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_publications)")}
            if "asset_version_id" not in publication_columns:
                connection.execute("ALTER TABLE monster_animation_publications ADD COLUMN asset_version_id TEXT NOT NULL DEFAULT ''")
            if "version_create_time" not in publication_columns:
                connection.execute("ALTER TABLE monster_animation_publications ADD COLUMN version_create_time TEXT NOT NULL DEFAULT ''")
            if "manual_verified" not in publication_columns:
                connection.execute("ALTER TABLE monster_animation_publications ADD COLUMN manual_verified INTEGER NOT NULL DEFAULT 0")
            binding_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_bindings)")}
            if "playback_speed_percent" not in binding_columns:
                connection.execute(
                    "ALTER TABLE monster_animation_bindings ADD COLUMN playback_speed_percent INTEGER NOT NULL DEFAULT 100"
                )
            self._migrate_combat_idle(connection)
            if self.kind == "npc":
                self._migrate_npc_categories(connection)
                self._migrate_npc_compatibility(connection)
            # Previous Remove left published clips without any binding. Archive
            # those before a Scan Folder can associate an old Asset ID again.
            retire_legacy_orphans(connection, self.kind)
        self._normalize_source_only_files()

    @staticmethod
    def _migrate_npc_categories(connection):
        """Replace old uniqueness (actor,slot,variant) with (actor,set,slot,variant).

        Existing IDs, animation asset IDs and publication histories are retained.
        """
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_bindings)")}
        if "weapon_set" in columns:
            return
        connection.execute("""CREATE TABLE monster_animation_bindings_m67(
            id TEXT PRIMARY KEY, monster_slug TEXT NOT NULL, slot TEXT NOT NULL,
            variant INTEGER NOT NULL DEFAULT 0, clip_id TEXT NOT NULL,
            weight INTEGER NOT NULL DEFAULT 100,
            playback_speed_percent INTEGER NOT NULL DEFAULT 100,
            looped INTEGER NOT NULL DEFAULT 0, priority TEXT NOT NULL DEFAULT 'Movement',
            created_at REAL NOT NULL, updated_at REAL NOT NULL,
            weapon_set TEXT NOT NULL DEFAULT '1hs', disarm INTEGER NOT NULL DEFAULT 0,
            UNIQUE(monster_slug,weapon_set,slot,variant)
        )""")
        connection.execute("""INSERT INTO monster_animation_bindings_m67(
            id,monster_slug,slot,variant,clip_id,weight,playback_speed_percent,
            looped,priority,created_at,updated_at,weapon_set,disarm)
            SELECT id,monster_slug,slot,variant,clip_id,weight,playback_speed_percent,
            looped,priority,created_at,updated_at,'1hs',0
            FROM monster_animation_bindings""")
        connection.execute("DROP TABLE monster_animation_bindings")
        connection.execute("ALTER TABLE monster_animation_bindings_m67 RENAME TO monster_animation_bindings")

    @staticmethod
    def _migrate_npc_compatibility(connection) -> None:
        """Nullable explicit override; NULL keeps the subtype's default.

        No existing publication, clip ID or binding ID changes. A type rename
        automatically adopts the new default only when no override was authored.
        """
        cols = {str(row[1]) for row in connection.execute("PRAGMA table_info(monster_animation_bindings)")}
        if "compatible_sets" not in cols:
            connection.execute("ALTER TABLE monster_animation_bindings ADD COLUMN compatible_sets TEXT")

    @staticmethod
    def _compatible_for_binding(row: dict) -> list[str]:
        explicit = row.get("compatible_sets")
        if explicit is None:
            return default_compatibility(str(row.get("weapon_set") or "1hs"))
        return validate_compatibility(json.loads(str(explicit)))

    def _normalize_source_only_files(self) -> None:
        """Keep canonical monster animation metadata bound to assets/source only."""
        updates = []
        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT id,source_path,prepared_path,sha256,source_sha256 FROM monster_animation_clips"
            )]
            for row in rows:
                canonical = str(row.get("source_path") or row.get("prepared_path") or "").replace("\\", "/")
                canonical = canonical.replace("assets/prepared/", "assets/source/")
                source = self.root / canonical
                if not canonical or not source.is_file():
                    continue
                digest = self._sha256(source)
                if (
                    str(row.get("source_path") or "") != canonical
                    or str(row.get("prepared_path") or "") != canonical
                    or str(row.get("sha256") or "") != digest
                    or str(row.get("source_sha256") or "") != digest
                ):
                    updates.append((canonical, canonical, digest, digest, time.time(), str(row["id"])))
            if updates:
                connection.executemany(
                    "UPDATE monster_animation_clips SET source_path=?,prepared_path=?,sha256=?,source_sha256=?,updated_at=? WHERE id=?",
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
